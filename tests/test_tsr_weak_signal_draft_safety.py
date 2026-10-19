"""Create TSR on a weak signal, Calibration Report backup retries, and draft safety on publish.

plans.md "Create TSR and Calibration Report — weak-signal save, report backup retry, faster schedule
list (3 batches)". TSR_SAFETY_ROOT points the checks at another checkout (used for the HEAD control).
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import unittest

ROOT = pathlib.Path(os.environ.get('TSR_SAFETY_ROOT') or pathlib.Path(__file__).resolve().parents[1])
TEMPLATE = ROOT / 'templates' / 'offline_tsr.html'
CAL_SCRIPT = ROOT / 'static' / 'js' / 'app-calibration-report.js'
APP = ROOT / 'app.py'


def function_source(source, name):
    """Return one top-level `function`/`async function` from the template script."""
    match = re.search(r'^(?:async )?function ' + re.escape(name) + r'\(', source, re.M)
    if not match:
        return ''
    # Skip the parameter list: defaults like `{ timeoutMs=12000 } = {}` contain braces.
    depth = 1
    index = match.end()
    while depth:
        depth += {'(': 1, ')': -1}.get(source[index], 0)
        index += 1
    depth = 0
    start = source.index('{', index)
    for index in range(start, len(source)):
        if source[index] == '{':
            depth += 1
        elif source[index] == '}':
            depth -= 1
            if depth == 0:
                return source[match.start():index + 1]
    return ''


class WeakSignalSaveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = TEMPLATE.read_text(encoding='utf-8')

    def test_health_check_takes_a_timeout_and_records_reachability(self):
        health = function_source(self.source, 'checkOfflineTSRSyncHealth')
        self.assertIn('timeoutMs=12000', health)
        self.assertIn("{ phase:'checking_connection', timeoutMs }", health)
        self.assertIn('setOfflineTSRServerReachable(true)', health)
        self.assertIn('setOfflineTSRServerReachable(error?.requiresLogin === true)', health)

    def test_online_save_pings_before_the_long_upload(self):
        submit = function_source(self.source, 'submitStandaloneTSROnline')
        ping = submit.find('await checkOfflineTSRSyncHealth({ timeoutMs:6000 })')
        upload = submit.find("fetchTSRSyncJSON('/save_offline_tsr_online'")
        self.assertGreater(ping, 0)
        self.assertGreater(upload, ping)
        # The ping sits inside the try whose catch queues retriable failures on the device.
        self.assertLess(submit.find('try{'), ping)
        self.assertIn('queueStandaloneTSROffline(payload, pdfPackage, reason', submit)

    def test_banner_says_when_the_server_cannot_be_reached(self):
        banner = function_source(self.source, 'updateOfflineTSRStatusIntelligence')
        unreachable = banner.find('offlineTSRServerReachable === false')
        self.assertGreater(unreachable, banner.find('if(!navigator.onLine)'))
        self.assertLess(unreachable, banner.find('Online mode:'))
        self.assertIn("Can't reach the server", banner)

    def test_finished_draft_cleanup_does_not_wait_on_a_dead_server(self):
        # Found in the browser check: after queueing, the account-draft delete hung the save.
        delete = function_source(self.source, 'deleteStandaloneTSRDraftOnServer')
        self.assertIn('if(!navigator.onLine || offlineTSRServerReachable === false){', delete)
        # The deletion is marked for retry before that early return, so it is postponed, not lost.
        self.assertLess(delete.find('queueStandaloneTSRServerDraftDelete(draftKey)'), delete.find('offlineTSRServerReachable === false'))
        remote = function_source(self.source, 'deleteStandaloneTSRServerDraftRemote')
        self.assertIn('setTimeout(() => controller.abort(), 15000)', remote)

    def test_reachability_is_rechecked_at_most_every_30_seconds(self):
        self.assertIn('const OFFLINE_TSR_REACHABILITY_RECHECK_MS = 30 * 1000;', self.source)
        recheck = function_source(self.source, 'recheckOfflineTSRServerReachability')
        self.assertIn('OFFLINE_TSR_REACHABILITY_RECHECK_MS', recheck)
        auto = function_source(self.source, 'scheduleOfflineTSRAutoSync')
        self.assertGreaterEqual(auto.count('recheckOfflineTSRServerReachability()'), 4)
        self.assertIn('offlineTSRServerReachable = true;', auto)


class CalibrationReportBackupRetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = TEMPLATE.read_text(encoding='utf-8')
        cls.backup = function_source(cls.source, 'backupLateCalibrationReportDraft')

    def test_backup_is_timed_and_retries_with_backoff(self):
        self.assertIn('const LATE_CALIBRATION_BACKUP_RETRY_MS = [15000, 30000, 60000, 120000];', self.source)
        self.assertIn("fetchTSRSyncJSON(`/save_calibration_report_draft/", self.backup)
        self.assertIn('timeoutMs:15000', self.backup)
        self.assertNotIn('await fetch(', self.backup)
        self.assertIn('isRetriableTSRSyncError(error)', self.backup)
        self.assertIn('LATE_CALIBRATION_BACKUP_RETRY_MS[', self.backup)

    def test_pending_backup_retries_on_focus_and_visibility(self):
        self.assertIn("window.addEventListener('focus', retryPendingLateCalibrationBackup);", self.source)
        self.assertIn("window.addEventListener('online', retryPendingLateCalibrationBackup);", self.source)
        self.assertRegex(self.source, r"visibilitychange', \(\) => \{\s*if\(document\.visibilityState === 'visible'\) retryPendingLateCalibrationBackup\(\);")

    def test_reopening_uploads_a_newer_device_copy(self):
        restore = function_source(self.source, 'restoreStandaloneLateCalibrationDraft')
        self.assertIn('reportSavedAt(candidate.payload.calibration_report) > reportSavedAt(accountCopy)', restore)
        self.assertIn('backupLateCalibrationReportDraft(targetId, candidate.payload.calibration_report)', restore)

    def test_sample_pdf_conversion_times_out_with_a_clear_message(self):
        script = CAL_SCRIPT.read_text(encoding='utf-8')
        self.assertIn('var SAMPLE_PDF_TIMEOUT_MS = 90000;', script)
        self.assertIn('new AbortController()', script)
        self.assertIn('The server took too long to make the sample PDF.', script)


class DraftSafetyTests(unittest.TestCase):
    """Publishing must never delete or hide an engineer's drafts (owner, 2026-10-19)."""

    @classmethod
    def setUpClass(cls):
        cls.source = TEMPLATE.read_text(encoding='utf-8')

    def test_storage_names_versions_and_keys_are_unchanged(self):
        for literal in (
            "const OFFLINE_TSR_DB_NAME = 'medical_service_offline_tsr_db';",
            'const OFFLINE_TSR_DB_VERSION = 1;',
            "drafts: 'tsr_drafts',",
            "queue: 'tsr_queue',",
            "attachments: 'tsr_attachments',",
            "metadata: 'tsr_metadata'",
            "const OFFLINE_TSR_QUEUE_KEY = 'medical_service_offline_tsr_queue_v1';",
            "const OFFLINE_TSR_QUEUE_BACKUP_KEY = 'medical_service_offline_tsr_queue_backup_v1';",
            "const OFFLINE_TSR_QUEUE_META_KEY = 'medical_service_offline_tsr_queue_meta_v1';",
            "const STANDALONE_TSR_KEY = 'medicalServiceStandaloneTSRDraftV1';",
            "const OFFLINE_TSR_DRAFT_PREFIX = 'standalone_tsr_draft_';",
            "const OFFLINE_TSR_ACTIVE_DRAFT_ID = 'active_standalone_tsr_draft';",
            '`${OFFLINE_TSR_DRAFT_PREFIX}late_calibration_${normalizeStandaloneTSRDraftKey(accountId)}_${normalizeStandaloneTSRDraftKey(targetId)}`',
        ):
            self.assertIn(literal, self.source)

    def test_no_new_draft_deletes_and_no_storage_wipes(self):
        # Counts as of this change; a higher count means a new way to lose a draft was added.
        limits = {
            'clearStandaloneTSRDraftLocally(': 7,
            'deleteStandaloneTSRDraft(': 2,
            'offlineTSRDBDelete(': 5,
            'removeItem(': 8,
            'deleteStandaloneTSRDraftOnServer(': 2,
            'clearStandaloneTSRDraftFromIndexedDB(': 3,
        }
        for call, limit in limits.items():
            self.assertLessEqual(self.source.count(call), limit, call)
        app_source = APP.read_text(encoding='utf-8')
        for text in (self.source, CAL_SCRIPT.read_text(encoding='utf-8'), app_source):
            self.assertNotIn('indexedDB.deleteDatabase', text)
            self.assertNotIn('localStorage.clear(', text)
            self.assertNotIn('Clear-Site-Data', text)

    @unittest.skipUnless(shutil.which('node'), 'node is required for the cleanup behaviour check')
    def test_old_draft_cleanup_only_removes_copies_the_account_holds(self):
        old = '2026-08-01T00:00:00.000Z'
        drafts = [
            {'id': 'never_backed_up', 'account_id': 'acct', 'updated_at': old},
            {'id': 'edited_after_backup', 'account_id': 'acct', 'updated_at': old, 'server_revision': 3,
             'account_backed_up_updated_at': '2026-07-30T00:00:00.000Z'},
            {'id': 'standalone_tsr_draft_late_calibration_acct_77', 'account_id': 'acct', 'updated_at': old,
             'server_revision': 2, 'account_backed_up_updated_at': old},
            {'id': 'held_by_account', 'account_id': 'acct', 'updated_at': old, 'server_revision': 4,
             'account_backed_up_updated_at': old},
            {'id': 'recent', 'account_id': 'acct', 'updated_at': '2099-01-01T00:00:00.000Z', 'server_revision': 1,
             'account_backed_up_updated_at': '2099-01-01T00:00:00.000Z'},
        ]
        script = '\n'.join([
            "const OFFLINE_TSR_DB_STORES = { drafts:'tsr_drafts' };",
            "const OFFLINE_TSR_ACTIVE_DRAFT_ID = 'active_standalone_tsr_draft';",
            "const STANDALONE_TSR_ACCOUNT_SCOPE = 'acct';",
            'const OFFLINE_TSR_OLD_DRAFT_RETENTION_DAYS = 30;',
            f'const drafts = {json.dumps(drafts)};',
            'const deleted = [];',
            'async function offlineTSRDBGetAll(){ return drafts; }',
            'async function offlineTSRDBDelete(store, id){ deleted.push(id); }',
            function_source(self.source, 'offlineTSRRecordAgeDays'),
            function_source(self.source, 'standaloneTSRDraftHeldByAccount'),
            function_source(self.source, 'cleanupOfflineTSROldDraftRecords'),
            'cleanupOfflineTSROldDraftRecords().then(() => console.log(JSON.stringify(deleted)));',
        ])
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.strip()), ['held_by_account'])

    def _reconcile(self, *, active_draft, tombstoned, options):
        """Run reconcileTSRReservationFromServer in Node; return the draft writes and page state."""
        script = '\n'.join([
            f'let standaloneCurrentDraftId = {json.dumps(active_draft)};',
            "let standaloneTSRReservationToken = 'page-token';",
            "const field = { value:'' };",
            'const document = { getElementById: () => field };',
            'const writes = [];',
            'function normalizeTSRReservationToken(value){ return String(value || "").trim(); }',
            f'function isStandaloneTSRDraftDeletionTombstoned(id){{ return {json.dumps(tombstoned)}.includes(id); }}',
            'async function saveStandaloneTSRDraftToIndexedDB(payload){ writes.push("idb:" + payload._draft_id); }',
            'function saveStandaloneTSRDraftToLocalStorageFallback(payload){ writes.push("fallback:" + payload._draft_id); }',
            function_source(self.source, 'reconcileTSRReservationFromServer'),
            "const result = { status:'success', tsr_number:'20260505-01-KM', reservation_token:'sent-token' };",
            "const source = { _draft_id:'standalone_tsr_draft_315-2026-05-05', 'tsr-complaint':'sent' };",
            f'reconcileTSRReservationFromServer(result, source, {json.dumps(options)}).then(payload => console.log(JSON.stringify({{',
            '  writes, number: field.value, token: standaloneTSRReservationToken, returned: payload && payload["tsr-number"]',
            '})));',
        ])
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout.strip())

    @unittest.skipUnless(shutil.which('node'), 'node is required for the reconcile behaviour check')
    def test_sending_a_queued_tsr_does_not_recreate_its_draft(self):
        # Fresh page (nothing open), as when the queue syncs right after a reload.
        out = self._reconcile(active_draft='', tombstoned=[], options={'persistDraft': False})
        self.assertEqual(out['writes'], [])
        self.assertEqual(out['number'], '')
        self.assertEqual(out['token'], 'page-token')
        self.assertEqual(out['returned'], '20260505-01-KM')

    @unittest.skipUnless(shutil.which('node'), 'node is required for the reconcile behaviour check')
    def test_a_deleted_draft_is_never_written_back(self):
        out = self._reconcile(active_draft='', tombstoned=['standalone_tsr_draft_315-2026-05-05'], options={})
        self.assertEqual(out['writes'], [])

    @unittest.skipUnless(shutil.which('node'), 'node is required for the reconcile behaviour check')
    def test_the_open_draft_still_keeps_its_reserved_number(self):
        out = self._reconcile(active_draft='standalone_tsr_draft_315-2026-05-05', tombstoned=[], options={})
        self.assertEqual(out['writes'], ['idb:standalone_tsr_draft_315-2026-05-05',
                                         'fallback:standalone_tsr_draft_315-2026-05-05'])
        self.assertEqual(out['number'], '20260505-01-KM')
        self.assertEqual(out['token'], 'sent-token')

    def test_queue_upload_confirms_its_number_without_touching_drafts(self):
        upload = function_source(self.source, 'uploadQueuedOfflineTSR')
        self.assertRegex(upload, r'reserveTSRNumberForDraft\(Object\.assign\(\{\}, finalizedPayload, \{[^}]*\}\), \{ persistDraft:false \}\)')
        reserve = function_source(self.source, 'reserveTSRNumberForDraft')
        self.assertIn('{ persistDraft })', reserve)
        self.assertIn('if(persistDraft) standaloneTSRReservationToken = token;', reserve)

    def test_backup_mark_is_written_only_for_the_uploaded_version(self):
        mark = function_source(self.source, 'markStandaloneTSRDraftBackedUp')
        self.assertIn("String(local.updated_at || '') !== uploadedAt", mark)
        sync = function_source(self.source, 'syncStandaloneTSRDraftToServer')
        self.assertIn('if(!result.stale_ignored) await markStandaloneTSRDraftBackedUp(record);', sync)


if __name__ == '__main__':
    unittest.main()
