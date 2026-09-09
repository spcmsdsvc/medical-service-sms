"""Backfill user-facing Calibration Report PDFs from retained DOCX sources.

Dry-run is the default. Use ``--apply`` only against an explicitly selected
database/environment. The command never deletes or rewrites the source DOCX.
"""

from __future__ import annotations

import argparse
import json


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Create missing linked PDFs.')
    parser.add_argument('--force', action='store_true', help='Reconvert even valid linked PDFs.')
    parser.add_argument('--limit', type=int, default=0, help='Process at most this many source records.')
    return parser.parse_args()


def _conversion_table_exists(app_module):
    with app_module.db.engine.connect() as connection:
        return bool(connection.exec_driver_sql(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='calibration_report_conversion'"
        ).first())


def _source_candidates(app_module, limit=0):
    candidates = []
    for source_file in app_module.ShiftFile.query.order_by(
        app_module.ShiftFile.uploaded_at.asc(), app_module.ShiftFile.id.asc()
    ).all():
        if not app_module.calibration_report_filename_is_docx(
            app_module.get_shift_file_display_name(source_file)
        ):
            continue
        submission_id = app_module.clean_int(getattr(source_file, 'online_tsr_submission_id', None))
        submission = app_module.db.session.get(app_module.OnlineTsrSubmission, submission_id) if submission_id else None
        payload = app_module.parse_online_tsr_payload_json(submission)
        marker = payload.get('_generated_calibration_report') if isinstance(payload, dict) else None
        if (
            not isinstance(marker, dict) or
            marker.get('source') != 'generated_calibration_report' or
            app_module.clean_int(marker.get('file_id')) != app_module.clean_int(source_file.id)
        ):
            continue
        candidates.append(source_file)
        if limit and len(candidates) >= limit:
            break
    return candidates


def _inspect_source(app_module, source_file, table_exists):
    row = {
        'source_file_id': source_file.id,
        'filename': app_module.get_shift_file_display_name(source_file),
        'state': 'pending',
        'reason': '',
    }
    if table_exists:
        job = app_module.calibration_report_conversion_for_source(source_file.id)
        if job:
            row['state'] = job.state or 'pending'
            row['attempts'] = int(job.attempts or 0)
            row['pdf_file_id'] = job.pdf_shift_file_id
            row['last_error'] = job.last_error or ''
    else:
        row['reason'] = 'conversion state table will be created when apply mode runs'
    try:
        source_bytes = app_module._calibration_report_source_bytes(source_file)
        app_module._validate_calibration_report_docx_bytes(source_bytes)
    except FileNotFoundError as error:
        row['state'] = 'missing'
        row['reason'] = str(error)
    except Exception as error:
        row['state'] = 'corrupt'
        row['reason'] = str(error)
    return row


def main():
    args = _parse_args()
    if args.limit < 0:
        raise SystemExit('--limit must be zero or greater.')

    # Import after argument parsing so a plain --help never initializes the app.
    import app as app_module

    with app_module.app.app_context():
        table_exists = _conversion_table_exists(app_module)
        sources = _source_candidates(app_module, args.limit)
        rows = [_inspect_source(app_module, source, table_exists) for source in sources]
        summary = {
            'mode': 'apply' if args.apply else 'dry-run',
            'candidate_count': len(rows),
            'converted': 0,
            'skipped_ready': 0,
            'pending': 0,
            'failed': 0,
            'missing': 0,
            'corrupt': 0,
            'records': rows,
        }

        if args.apply:
            app_module.ensure_calibration_report_conversion_table()
            for source_file, before in zip(sources, rows):
                if before['state'] in {'missing', 'corrupt'}:
                    continue
                job = app_module.convert_calibration_report_source(source_file.id, force=args.force)
                after_state = job.state if job else 'missing'
                if after_state == 'ready' and before.get('state') != 'ready':
                    summary['converted'] += 1
                elif after_state == 'ready':
                    summary['skipped_ready'] += 1
                elif after_state == 'failed':
                    summary['failed'] += 1
                else:
                    summary['pending'] += 1
            for row in rows:
                job = app_module.calibration_report_conversion_for_source(row['source_file_id'])
                if job:
                    row.update({
                        'state': job.state or 'pending',
                        'attempts': int(job.attempts or 0),
                        'pdf_file_id': job.pdf_shift_file_id,
                        'last_error': job.last_error or '',
                    })

        for row in rows:
            state = row.get('state')
            if state == 'failed':
                summary['failed'] += 0 if args.apply else 1
            elif state == 'pending':
                summary['pending'] += 0 if args.apply else 1
            elif state == 'missing':
                summary['missing'] += 1
            elif state == 'corrupt':
                summary['corrupt'] += 1
            elif state == 'ready' and not args.apply:
                summary['skipped_ready'] += 1

        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
