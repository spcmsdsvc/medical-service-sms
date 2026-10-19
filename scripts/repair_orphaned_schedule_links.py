"""Re-link TSRs, Calibration Reports and certificate approvals orphaned by schedule rebuilds.

Before the 2026-10-19 fix, editing a schedule's engineer team or dates deleted the schedule row and
re-added its files to a new row by filename only. Submissions, approvals and report links kept the
old (deleted) schedule id. This script finds each deleted schedule id that a TSR submission still
points at, locates the rebuilt schedule through the TSR's exact filename, and re-links everything.

Standalone (sqlite3 only, no app import, so no startup migrations run). Dry-run by default and opens
the database read-only; --apply writes everything in one transaction.

    python scripts/repair_orphaned_schedule_links.py [--db PATH] [--apply]
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta

DEFAULT_DB = '/data/scheduler.db' if os.path.exists('/data/scheduler.db') else 'scheduler.db'
SHIFT_ID_TABLES = ('shift_file', 'online_tsr_submission', 'calibration_certificate_approval',
                   'reimbursement_row', 'reimbursement_receipt', 'inventory_pm_visit')
DISK_PREFIX = re.compile(r'^shift_\d+_[0-9a-fA-F]{16}_(.+)$')


def display_name(name):
    match = DISK_PREFIX.match(name or '')
    return match.group(1) if match else (name or '')


def table_exists(conn, table):
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())


def load_payload(raw):
    try:
        payload = json.loads(raw or '{}')
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def names_of(row):
    return {name for name in (row['filename'], row['original_filename'], display_name(row['filename'])) if name}


class Plan:
    """Everything one deleted schedule id needs; built read-only, written by apply()."""

    def __init__(self, old_shift_id, submissions):
        self.old_shift_id = old_shift_id
        self.submissions = submissions
        self.new_shift_id = None
        self.status = 'deleted'
        self.reason = ''
        self.file_links = {}        # shift_file id -> submission id
        self.file_tokens = {}       # shift_file id -> upload token
        self.payloads = {}          # submission id -> new payload dict
        self.conversions = {}       # conversion id -> (source id, pdf id)
        self.notes = []

    @property
    def latest(self):
        latest = [row for row in self.submissions if row['is_latest']]
        return max(latest or self.submissions, key=lambda row: row['id'])


def find_rebuilt_shift(conn, plan):
    """Exact TSR filename on exactly one live schedule of the same client."""
    candidates = set()
    for submission in sorted(plan.submissions, key=lambda row: row['id'] != plan.latest['id']):
        payload = load_payload(submission['payload_json'])
        names = {payload.get('_attached_disk_filename'), payload.get('_attached_display_filename')} - {None, ''}
        for name in names:
            for row in conn.execute(
                'SELECT f.shift_id FROM shift_file f JOIN shift s ON s.id = f.shift_id '
                'WHERE f.filename = ? OR f.original_filename = ?', (name, name)
            ):
                candidates.add(row['shift_id'])
        if candidates:
            break
    if not candidates:
        return None, 'no live schedule holds this TSR file'
    if len(candidates) > 1:
        return None, f'TSR file is on several live schedules: {sorted(candidates)}'
    new_shift_id = candidates.pop()
    client_name = (plan.latest['client_name'] or '').strip().casefold()
    shift_client = conn.execute(
        'SELECT c.name FROM shift s LEFT JOIN client c ON c.id = s.client_id WHERE s.id = ?', (new_shift_id,)
    ).fetchone()
    if client_name and shift_client and (shift_client['name'] or '').strip().casefold() != client_name:
        return None, f'schedule #{new_shift_id} belongs to another client ({shift_client["name"]})'
    return new_shift_id, ''


def unique_file(conn, shift_id, name, owner_submission_id):
    """The one file on the schedule with this name that is unlinked or already linked to the owner."""
    if not name:
        return None, 'no filename recorded'
    rows = [
        row for row in conn.execute(
            'SELECT id, filename, original_filename, online_tsr_submission_id, upload_token '
            'FROM shift_file WHERE shift_id = ?', (shift_id,)
        )
        if name in names_of(row) or display_name(name) in names_of(row)
    ]
    rows = [row for row in rows if row['online_tsr_submission_id'] in (None, owner_submission_id)]
    if len(rows) != 1:
        return None, f'{len(rows)} matching unlinked files for {name}'
    return rows[0], ''


def build_plan(conn, plan):
    plan.new_shift_id, plan.reason = find_rebuilt_shift(conn, plan)
    if not plan.new_shift_id:
        plan.status = 'ambiguous' if 'several' in plan.reason or 'another client' in plan.reason else 'deleted'
        return plan
    latest = plan.latest
    for submission in plan.submissions:
        payload = load_payload(submission['payload_json'])
        completed = payload.get('_completed_shift_ids')
        if isinstance(completed, list):
            payload['_completed_shift_ids'] = [
                plan.new_shift_id if str(value) == str(plan.old_shift_id) else value for value in completed
            ]
        plan.payloads[submission['id']] = payload
        if submission['id'] != latest['id']:
            continue

        attached = payload.get('_attached_file_id')
        if attached and not conn.execute('SELECT 1 FROM shift_file WHERE id = ?', (attached,)).fetchone():
            tsr, reason = unique_file(conn, plan.new_shift_id, payload.get('_attached_disk_filename'), submission['id'])
            if not tsr:
                plan.status, plan.reason = 'blocked', f'TSR PDF: {reason}'
                return plan
            plan.file_links[tsr['id']] = submission['id']
            payload['_attached_file_id'] = tsr['id']

        extra_ids = payload.get('_extra_attachment_file_ids') or []
        extra_names = payload.get('_extra_attachment_filenames') or []
        if isinstance(extra_ids, list) and isinstance(extra_names, list):
            repaired = []
            for index, extra_id in enumerate(extra_ids):
                if conn.execute('SELECT 1 FROM shift_file WHERE id = ?', (extra_id,)).fetchone():
                    repaired.append(extra_id)
                    continue
                name = extra_names[index] if index < len(extra_names) else ''
                extra, reason = unique_file(conn, plan.new_shift_id, name, submission['id'])
                if extra:
                    plan.file_links[extra['id']] = submission['id']
                    repaired.append(extra['id'])
                else:
                    plan.notes.append(f'extra attachment {extra_id} not relinked ({reason})')
                    repaired.append(extra_id)
            payload['_extra_attachment_file_ids'] = repaired

        marker = payload.get('_generated_calibration_report')
        if not isinstance(marker, dict) or not marker.get('file_id'):
            continue
        if conn.execute('SELECT 1 FROM shift_file WHERE id = ?', (marker['file_id'],)).fetchone():
            continue
        docx, reason = unique_file(conn, plan.new_shift_id, marker.get('filename'), submission['id'])
        if not docx:
            plan.status, plan.reason = 'blocked', f'Calibration Report DOCX: {reason}'
            return plan
        job = conn.execute(
            'SELECT id, pdf_shift_file_id FROM calibration_report_conversion WHERE source_shift_file_id = ?',
            (marker['file_id'],)
        ).fetchone() if table_exists(conn, 'calibration_report_conversion') else None
        pdf = None
        if marker.get('pdf_filename'):
            pdf, reason = unique_file(conn, plan.new_shift_id, marker['pdf_filename'], submission['id'])
            if not pdf:
                plan.status, plan.reason = 'blocked', f'Calibration Report PDF: {reason}'
                return plan
        if not job:
            plan.notes.append('no conversion job for the old report source; PDF will be re-converted by the app')
        elif pdf is None or (job['pdf_shift_file_id'] and job['pdf_shift_file_id'] != marker.get('pdf_file_id')):
            plan.status, plan.reason = 'blocked', 'conversion job does not match the report marker'
            return plan
        else:
            plan.conversions[job['id']] = (docx['id'], pdf['id'])
        plan.file_links[docx['id']] = submission['id']
        if marker.get('upload_token') and not docx['upload_token']:
            plan.file_tokens[docx['id']] = marker['upload_token']
        if pdf is not None:
            plan.file_links[pdf['id']] = submission['id']
        new_marker = dict(marker, file_id=docx['id'], pdf_file_id=pdf['id'] if pdf is not None else marker.get('pdf_file_id'))
        payload['_generated_calibration_report'] = new_marker
        report = payload.get('calibration_report')
        generated = report.get('generated') if isinstance(report, dict) else None
        if isinstance(generated, dict):
            generated['file_id'] = new_marker['file_id']
            generated['pdf_file_id'] = new_marker['pdf_file_id']
    plan.status = 'rebuilt'
    return plan


def apply(conn, plan, now):
    old, new = plan.old_shift_id, plan.new_shift_id
    for table in SHIFT_ID_TABLES:
        if table_exists(conn, table):
            conn.execute(f'UPDATE {table} SET shift_id = ? WHERE shift_id = ?', (new, old))
    for submission_id, payload in plan.payloads.items():
        conn.execute('UPDATE online_tsr_submission SET payload_json = ? WHERE id = ?',
                     (json.dumps(payload, ensure_ascii=False), submission_id))
    for file_id, submission_id in plan.file_links.items():
        conn.execute('UPDATE shift_file SET online_tsr_submission_id = ? WHERE id = ?', (submission_id, file_id))
    for file_id, token in plan.file_tokens.items():
        conn.execute('UPDATE shift_file SET upload_token = ? WHERE id = ?', (token, file_id))
    for job_id, (source_id, pdf_id) in plan.conversions.items():
        conn.execute('UPDATE calibration_report_conversion SET source_shift_file_id = ?, pdf_shift_file_id = ?, '
                     'updated_at = ? WHERE id = ?', (source_id, pdf_id, now, job_id))
    tsr_numbers = ', '.join(sorted({row['tsr_number'] or '?' for row in plan.submissions}))
    conn.execute('INSERT INTO activity_log (user, action, timestamp) VALUES (?, ?, ?)', (
        'System',
        f'Repaired orphaned schedule links: TSR {tsr_numbers} moved from deleted schedule #{old} to #{new}',
        now,
    ))


def describe(plan):
    tsr_numbers = ', '.join(sorted({row['tsr_number'] or '?' for row in plan.submissions}))
    client = plan.latest['client_name'] or ''
    line = f'{plan.status.upper():9} schedule #{plan.old_shift_id}'
    line += f' -> #{plan.new_shift_id}' if plan.new_shift_id else ''
    line += f' | {client} | TSR {tsr_numbers} | submissions {[row["id"] for row in plan.submissions]}'
    if plan.reason:
        line += f' | {plan.reason}'
    if plan.status == 'rebuilt':
        line += f' | files relinked {sorted(plan.file_links)}'
        if plan.conversions:
            line += f' | conversion {plan.conversions}'
    for note in plan.notes:
        line += f' | note: {note}'
    return line


def run(db_path, do_apply=False, out=sys.stdout):
    uri = f'file:{db_path}' + ('' if do_apply else '?mode=ro')
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        orphans = conn.execute(
            'SELECT o.* FROM online_tsr_submission o LEFT JOIN shift s ON s.id = o.shift_id '
            'WHERE s.id IS NULL ORDER BY o.shift_id, o.id'
        ).fetchall()
        groups = {}
        for row in orphans:
            groups.setdefault(row['shift_id'], []).append(row)
        plans = [build_plan(conn, Plan(old_id, rows)) for old_id, rows in groups.items()]
        for plan in plans:
            print(describe(plan), file=out)
        orphan_approvals = conn.execute(
            'SELECT a.id, a.shift_id FROM calibration_certificate_approval a LEFT JOIN shift s ON s.id = a.shift_id '
            'WHERE s.id IS NULL'
        ).fetchall() if table_exists(conn, 'calibration_certificate_approval') else []
        covered = set(groups)
        for row in orphan_approvals:
            if row['shift_id'] not in covered:
                print(f'NOTE      approval #{row["id"]} points at deleted schedule #{row["shift_id"]} with no TSR submission', file=out)
        counts = {status: sum(1 for plan in plans if plan.status == status) for status in ('rebuilt', 'deleted', 'ambiguous', 'blocked')}
        print(f'Summary: {len(plans)} deleted schedule ids, ' + ', '.join(f'{key} {value}' for key, value in counts.items()), file=out)
        if not do_apply:
            print('Dry run: nothing written. Re-run with --apply to repair the REBUILT rows.', file=out)
            return plans
        now = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S.%f')
        with conn:
            for plan in plans:
                if plan.status == 'rebuilt':
                    apply(conn, plan, now)
        print(f'Applied: {counts["rebuilt"]} schedule ids repaired.', file=out)
        return plans
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--db', default=DEFAULT_DB)
    parser.add_argument('--apply', action='store_true', help='write the repairs (default is a read-only dry run)')
    args = parser.parse_args()
    run(args.db, do_apply=args.apply)


if __name__ == '__main__':
    main()
