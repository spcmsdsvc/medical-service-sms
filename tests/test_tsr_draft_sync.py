import json
import os
import pathlib
import re
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from datetime import timedelta

from sqlalchemy import create_engine

from tests.sw_cache_version import assert_cache_version_at_least


ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = pathlib.Path(r"C:\Users\Jonamar\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe")

try:
    import app as app_module
except Exception as exc:  # pragma: no cover - source checks still run without app dependencies
    app_module = None
    APP_IMPORT_ERROR = exc
else:
    APP_IMPORT_ERROR = None


class TsrDraftSyncContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.template_source = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')
        cls.calibration_report_source = (ROOT / 'static' / 'js' / 'app-calibration-report.js').read_text(encoding='utf-8')

    def test_server_draft_schema_and_owner_scoped_routes_exist(self):
        self.assertIn('class TsrDraft(db.Model)', self.app_source)
        self.assertIn('class TsrDraftVersion(db.Model)', self.app_source)
        self.assertIn("db.UniqueConstraint('user_id', 'draft_key'", self.app_source)
        for route in (
            "@app.route('/save_tsr_draft', methods=['POST'])",
            "@app.route('/get_tsr_drafts', methods=['GET'])",
            "@app.route('/save_tsr_draft_version', methods=['POST'])",
            "@app.route('/get_tsr_draft_history', methods=['GET'])",
            "@app.route('/delete_tsr_draft', methods=['POST'])",
        ):
            self.assertIn(route, self.app_source)
        route = self.app_source.split("@app.route('/delete_tsr_draft'")[1].split("@app.route('/offline_tsr_sync_ping'")[0]
        self.assertIn("filter_by(\n        user_id=getattr(current_user, 'id', None),", route)

    def test_server_projection_removes_file_values_but_keeps_typed_data(self):
        if app_module is None:
            self.skipTest(f'app dependencies unavailable: {APP_IMPORT_ERROR}')
        projected = app_module.project_tsr_draft_payload_for_server({
            'tsr-complaint': 'Power issue',
            'signatures': {'serviced': 'data:image/png;base64,signature'},
            'attachments': [{
                'name': 'receipt.png',
                'blob': 'browser-only-blob',
                'data_url': 'data:image/png;base64,large',
                'blob_id': 'draft-attachment-1',
            }],
        })
        serialized = json.dumps(projected)
        self.assertEqual(projected['tsr-complaint'], 'Power issue')
        self.assertIn('data:image/png;base64,signature', serialized)
        self.assertNotIn('browser-only-blob', serialized)
        self.assertNotIn('data:image/png;base64,large', serialized)
        self.assertIn('draft-attachment-1', serialized)

    def test_calibration_report_state_survives_server_projection_without_browser_blob(self):
        if app_module is None:
            self.skipTest(f'app dependencies unavailable: {APP_IMPORT_ERROR}')
        projected = app_module.project_tsr_draft_payload_for_server({
            'calibration_report': {
                'schema_version': 2,
                'status': 'draft',
                'machine': {'model': 'MobileDaRt', 'serial_number': 'SN-17'},
                'signature': {'image': 'data:image/png;base64,signature'},
                'generated': {'blob_id': 'calibration-report-abcd1234'},
            }
        })
        self.assertEqual(projected['calibration_report']['machine']['model'], 'MobileDaRt')
        self.assertIn('calibration-report-abcd1234', json.dumps(projected))
        self.assertEqual(projected['calibration_report']['signature']['image'], 'data:image/png;base64,signature')

    def test_calibration_report_cleanup_references_project_without_blob_bytes_or_readiness(self):
        if app_module is None:
            self.skipTest(f'app dependencies unavailable: {APP_IMPORT_ERROR}')
        projected = app_module.project_tsr_draft_payload_for_server({
            'calibration_report': {
                'schema_version': 2,
                'status': 'draft',
                'generated': {'fingerprint': '', 'attachment_id': '', 'blob_id': ''},
                'generated_cleanup': {'blob_ids': ['calibration-report-old-1'], 'blob': 'browser-only-blob'},
            }
        })
        report = projected['calibration_report']
        self.assertEqual(report['generated_cleanup']['blob_ids'], ['calibration-report-old-1'])
        self.assertNotIn('browser-only-blob', json.dumps(projected))
        self.assertFalse(report['generated']['attachment_id'])
        self.assertIn('generated_cleanup', self.calibration_report_source)
        self.assertIn('hasGeneratedMetadata', self.calibration_report_source)

    def test_server_conflicts_use_revision_not_device_clock_ordering(self):
        if app_module is None:
            self.skipTest(f'app dependencies unavailable: {APP_IMPORT_ERROR}')
        self.assertIsNone(app_module.normalize_tsr_draft_revision(None))
        self.assertEqual(app_module.normalize_tsr_draft_revision('3'), 3)
        route = self.app_source.split("@app.route('/save_tsr_draft'", 1)[1].split("@app.route('/get_tsr_drafts'", 1)[0]
        self.assertIn("base_revision", route)
        self.assertIn("revision_mismatch", route)
        self.assertIn('tsr_draft_conflict_response', route)
        self.assertIn("'status': 'conflict'", self.app_source)
        self.assertNotIn('incoming_timestamp < stored_timestamp', route)
        self.assertIn('stale_ignored', self.app_source)

    def test_optional_server_metadata_does_not_slice_none(self):
        if app_module is None:
            self.skipTest(f'app dependencies unavailable: {APP_IMPORT_ERROR}')
        self.assertIsNone(app_module.tsr_draft_text(None, 40))
        self.assertEqual(app_module.tsr_draft_text('  schedule-17  ', 12), 'schedule-17')

    def test_browser_wiring_is_local_first_and_server_backed(self):
        for marker in (
            "navigator.storage.persist",
            "'/save_tsr_draft'",
            "'/get_tsr_drafts'",
            "'/delete_tsr_draft'",
            'STANDALONE_TSR_SERVER_DRAFT_DEBOUNCE_MS',
            'mergeServerStandaloneTSRDrafts',
            'server_sync_error',
            'Storage Persistence',
        ):
            self.assertIn(marker, self.template_source)
        self.assertIn('saveStandaloneTSRDraftToIndexedDB(data,', self.template_source)
        self.assertIn("serverSync:'immediate'", self.template_source)
        self.assertIn('Supporting files remain local to this device', self.app_source)

    def test_divergent_account_copy_is_preserved_without_hydration_overwrite(self):
        merge = self.template_source.split(
            'async function mergeServerStandaloneTSRDrafts', 1
        )[1].split('async function refreshStandaloneTSRDraftPanel', 1)[0]
        self.assertIn('standaloneTSRAccountDraftCandidates', merge)
        self.assertIn('groupStandaloneTSRDraftVersions', merge)
        self.assertIn('rememberStandaloneTSRDraftConflict', merge)
        preserve = merge.index('if(hasDivergentCopy || standaloneTSRDraftConflictIds.has(draftKey))')
        self.assertLess(preserve, merge.index('continue;', preserve))
        self.assertLess(merge.index('continue;', preserve), merge.index('offlineTSRDBPut', preserve),
                      'A differing account copy must not replace or upload the device copy.')

    def test_same_id_localstorage_mirror_remains_a_recovery_candidate(self):
        records = self.template_source.split(
            'async function getStandaloneTSRDraftRecords', 1
        )[1].split('function getStandaloneTSRSignatureRecoveryPayload', 1)[0]
        self.assertIn("source:'localstorage'", records)
        self.assertIn('groupStandaloneTSRDraftVersions', records,
                      'Matching device mirrors may be deduplicated, differing mirrors may not.')
        self.assertNotIn('!records.some', records,
                         'The localStorage mirror must not be hidden solely because IDs match.')
        self.assertIn('records.push', records)

    def test_conflicts_are_grouped_and_require_explicit_copy_selection(self):
        panel = self.template_source.split(
            'async function renderStandaloneTSRDraftPanel', 1
        )[1].split('async function openStandaloneTSRDraft', 1)[0]
        self.assertIn('groupStandaloneTSRDraftVersions', panel)
        self.assertIn('Open this version', panel)
        self.assertIn('useStandaloneTSRDraftCopy', panel)
        self.assertIn('Choose one to open', panel)
        self.assertIn('Earlier account copy', self.template_source)
        self.assertIn("'/get_tsr_draft_history'", self.template_source)
        self.assertIn("'/save_tsr_draft_version'", self.template_source)

    def test_recovery_sources_use_plain_language(self):
        labels = self.template_source.split(
            'function standaloneTSRDraftSourceLabel', 1
        )[1].split('function rememberStandaloneTSRDraftConflict', 1)[0]
        self.assertIn("'Saved to your account'", labels)
        self.assertIn("'Saved on this device'", labels)
        for implementation_term in ('IndexedDB', 'localStorage', 'fallback storage'):
            self.assertNotIn(implementation_term, labels)

    def test_selected_copy_keeps_draft_identity_without_saving_or_finalizing(self):
        self.assertIn('async function useStandaloneTSRDraftCopy', self.template_source)
        selection = self.template_source.split(
            'async function useStandaloneTSRDraftCopy', 1
        )[1].split('\n}', 1)[0]
        for marker in (
            '_draft_id', 'reservation_token', "'tsr-number'", 'originalNumber',
            'originalReservation', 'rehydrateStandaloneTSRDraftPayload', 'applyStandaloneTSRDraftData',
        ):
            self.assertIn(marker, selection)
        for forbidden in (
            'saveStandaloneTSRDraftLocally(',
            'syncStandaloneTSRDraftToServer(',
            'submitStandaloneTSROnline(',
        ):
            self.assertNotIn(forbidden, selection)

    def test_stale_server_response_is_not_reported_as_account_backup(self):
        sync = self.template_source.split(
            'async function syncStandaloneTSRDraftToServer', 1
        )[1].split('function standaloneTSRServerBackupFailureText', 1)[0]
        queued = self.template_source.split(
            'function enqueueStandaloneTSRServerDraftSync', 1
        )[1].split('function readStandaloneTSRServerDraftDeleteQueue', 1)[0]
        self.assertIn("response.status === 409 && result.status === 'conflict'", sync)
        self.assertIn("result?.status === 'conflict'", queued)
        self.assertIn('account-backup-conflict', queued)

    def test_unresolved_conflict_blocks_background_sync_and_draft_overwrite(self):
        sync = self.template_source.split(
            'function enqueueStandaloneTSRServerDraftSync', 1
        )[1].split('function readStandaloneTSRServerDraftDeleteQueue', 1)[0]
        local_save = self.template_source.split(
            'async function saveStandaloneTSRDraftLocally(data', 1
        )[1].split('async function clearStandaloneTSRDraftLocally', 1)[0]
        self.assertIn('draft_source_conflict', sync)
        self.assertIn('!standaloneTSRDraftRecoveryChoices.has(draftId)', sync)
        self.assertNotIn('draft_source_conflict', local_save,
                         'Local editing and device saves remain usable when account versions diverge.')
        self.assertIn('saveStandaloneTSRDraftLocallyNow(context)', local_save)

    def test_server_revision_metadata_conflict_archive_and_plain_language_statuses_are_wired(self):
        request_builder = self.template_source.split(
            'function buildStandaloneTSRServerDraftRequest', 1
        )[1].split('function buildStandaloneTSRAccountDraftCandidate', 1)[0]
        sync = self.template_source.split(
            'async function syncStandaloneTSRDraftToServer', 1
        )[1].split('function standaloneTSRServerBackupFailureText', 1)[0]
        merge = self.template_source.split(
            'async function mergeServerStandaloneTSRDrafts', 1
        )[1].split('async function refreshStandaloneTSRDraftPanel', 1)[0]
        self.assertIn('base_revision', request_builder)
        self.assertIn('server_revision', self.template_source)
        self.assertIn('server_hash', self.template_source)
        self.assertIn("response.status === 409 && result.status === 'conflict'", sync)
        self.assertIn('persistStandaloneTSRDraftServerMetadata', sync)
        self.assertIn('archiveStandaloneTSRDraftVersion(candidate', merge)
        self.assertIn('Your session expired', merge)
        self.assertIn('cannot access TSR draft history', merge)
        self.assertIn('remains saved on this device', merge)

    def test_successful_final_save_still_deletes_account_draft_and_history(self):
        finish = self.template_source.split(
            'async function finishStandaloneTSRFinalSave', 1
        )[1].split('async function confirmStandaloneTSRFinalSave', 1)[0]
        delete_route = self.app_source.split("@app.route('/delete_tsr_draft'", 1)[1].split("@app.route('/release_tsr_number_reservation'", 1)[0]
        self.assertGreaterEqual(finish.count('clearStandaloneTSRDraftLocally()'), 2)
        self.assertIn('TsrDraftVersion.query.filter_by', delete_route)
        self.assertIn('history_query.delete', delete_route)

    def test_draft_deletion_fences_pending_local_and_server_saves(self):
        clear = self.template_source.split(
            'async function clearStandaloneTSRDraftLocally', 1
        )[1].split('async function getStandaloneTSRDraftRecords', 1)[0]
        delete_server = self.template_source.split(
            'async function deleteStandaloneTSRDraftOnServer', 1
        )[1].split('async function mergeServerStandaloneTSRDrafts', 1)[0]
        save_now = self.template_source.split(
            'async function saveStandaloneTSRDraftLocallyNow', 1
        )[1].split('async function saveStandaloneTSRDraftLocally', 1)[0]
        server_sync = self.template_source.split(
            'function enqueueStandaloneTSRServerDraftSync', 1
        )[1].split('function readStandaloneTSRServerDraftDeleteQueue', 1)[0]

        pending_index = clear.find('markStandaloneTSRDraftDeletionPending')
        local_wait_index = clear.find('await waitForStandaloneTSRLocalSaves()')
        server_delete_index = clear.find('deleteStandaloneTSRDraftOnServer')
        self.assertTrue(pending_index >= 0, 'Deletion must persist its tombstone first.')
        self.assertTrue(local_wait_index >= 0, 'Deletion must wait for pending device saves.')
        self.assertTrue(server_delete_index >= 0, 'Deletion must process the account copy.')
        if min(pending_index, local_wait_index, server_delete_index) >= 0:
            self.assertLess(pending_index, local_wait_index)
            self.assertLess(local_wait_index, server_delete_index)
        self.assertTrue('standaloneTSRServerDraftSyncTimerDraftId === draftKey' in delete_server,
                        'Deletion must cancel only this draft’s debounced server backup.')
        self.assertTrue('const operation = standaloneTSRServerDraftSyncChain' in delete_server and 'await operation' in delete_server,
                        'Deletion must wait for an in-flight account backup.')
        self.assertTrue('getStandaloneTSRDraftDeleteGeneration(context.draftId)' in save_now and
                        'context.deleteGeneration < currentDeleteGeneration' in save_now,
                        'A save queued before deletion must not recreate its draft.')
        if 'context.deleteGeneration < currentDeleteGeneration' in save_now:
            self.assertLess(save_now.index('context.deleteGeneration < currentDeleteGeneration'),
                            save_now.index('saveStandaloneTSRDraftToIndexedDB(data'))
        self.assertTrue('isStandaloneTSRDraftDeletionTombstoned(draftId)' in server_sync,
                        'Background account backup must honor the tombstone.')

    def test_delete_tombstones_are_durable_account_scoped_and_retryable(self):
        self.assertTrue('current_user.get_id()' in self.template_source,
                        'Delete tombstones must be scoped to the authenticated account.')
        self.assertIn("'medicalServiceStandaloneTSRServerDraftDeletesV2'", self.template_source)
        read_queue = self.template_source.split(
            'function readStandaloneTSRServerDraftDeleteQueue', 1
        )[1].split('function writeStandaloneTSRServerDraftDeleteQueue', 1)[0]
        write_queue = self.template_source.split(
            'function writeStandaloneTSRServerDraftDeleteQueue', 1
        )[1].split('function queueStandaloneTSRServerDraftDelete', 1)[0]
        flush = self.template_source.split(
            'async function flushStandaloneTSRServerDraftDeletes', 1
        )[1].split('async function deleteStandaloneTSRDraftOnServer', 1)[0]
        remote_delete = self.template_source.split(
            'async function deleteStandaloneTSRServerDraftRemote', 1
        )[1].split('function readTSRReservationReleaseQueue', 1)[0]

        self.assertTrue('STANDALONE_TSR_ACCOUNT_SCOPE' in read_queue and 'value.account_id' in read_queue,
                        'Only the signed-in account’s server deletions may be retried.')
        self.assertTrue('draft_key' in read_queue)
        self.assertTrue('localStorage.setItem(STANDALONE_TSR_SERVER_DELETE_KEY' in write_queue)
        self.assertTrue("status:'pending'" in self.template_source)
        self.assertTrue("status:'deleted'" in self.template_source)
        self.assertTrue('markStandaloneTSRDraftDeletionConfirmed' in self.template_source)
        self.assertTrue("entry.status === 'pending'" in flush)
        self.assertTrue("if(!currentTombstone || currentTombstone.status !== 'pending') continue;" in flush,
                        'A retry snapshot must not delete after an explicit action clears its tombstone.')
        self.assertTrue('markStandaloneTSRDraftDeletionConfirmed' in flush)
        self.assertTrue('if(response.status === 404)' in remote_delete)
        self.assertTrue("return { status:'success', success:true, deleted:false, not_found:true }" in remote_delete)

    def test_refresh_hides_deleted_account_copies_but_preserves_device_records(self):
        merge = self.template_source.split(
            'async function mergeServerStandaloneTSRDrafts', 1
        )[1].split('async function refreshStandaloneTSRDraftPanel', 1)[0]
        records = self.template_source.split(
            'async function getStandaloneTSRDraftRecords', 1
        )[1].split('function getStandaloneTSRSignatureRecoveryPayload', 1)[0]
        migration = self.template_source.split(
            'async function migrateStandaloneDraftLocalStorageToIndexedDB', 1
        )[1].split('function ', 1)[0]

        self.assertTrue('isStandaloneTSRDraftDeletionTombstoned(localKey)' in merge,
                        'A deleted local copy must not be uploaded during startup merge.')
        self.assertTrue('isStandaloneTSRDraftDeletionTombstoned(draftKey)' in merge,
                        'A queued account copy must not be rehydrated.')
        self.assertTrue('records.push(...indexedRecords' in records)
        self.assertTrue("source:'localstorage'" in records)
        self.assertTrue('isStandaloneTSRDraftDeletionTombstoned(candidate.id)' in records,
                        'Only stale server candidates should be hidden from recovery.')
        self.assertTrue('loadStandaloneTSRDraftFromLocalStorageFallback()' in migration)
        self.assertTrue('saveStandaloneTSRDraftToIndexedDB(fallbackDraft)' in migration)
        self.assertTrue('offlineTSRDBDelete' not in migration,
                        'Startup migration must not delete pre-existing device drafts.')
        self.assertTrue('localStorage.removeItem' not in migration,
                        'Startup migration must preserve the legacy localStorage copy.')

    def test_local_delete_verifies_indexeddb_and_localstorage_absence(self):
        clear_device = self.template_source.split(
            'async function clearStandaloneTSRDraftFromIndexedDB', 1
        )[1].split('function saveStandaloneTSRDraftToLocalStorageFallback', 1)[0]
        delete_ui = self.template_source.split(
            'async function deleteStandaloneTSRDraft(id)', 1
        )[1].split('/* =========================================================', 1)[0]

        self.assertTrue('offlineTSRDBDelete(OFFLINE_TSR_DB_STORES.drafts, targetId)' in clear_device)
        self.assertTrue('const scopedKey = getStandaloneTSRDraftFallbackKey()' in clear_device)
        self.assertTrue('localStorage.removeItem(scopedKey)' in clear_device)
        self.assertTrue('localStorage.removeItem(STANDALONE_TSR_KEY)' in clear_device)
        self.assertTrue('offlineTSRDBGet(OFFLINE_TSR_DB_STORES.drafts, targetId)' in clear_device,
                        'IndexedDB absence must be verified after the delete.')
        self.assertTrue('localStorage.getItem(scopedKey)' in clear_device,
                        'The current account localStorage mirror must be verified absent.')
        self.assertTrue('local_deleted' in clear_device)
        self.assertTrue('if(!result?.local_deleted)' in delete_ui)
        self.assertTrue('could not be confirmed' in delete_ui)
        self.assertTrue('server_delete_pending' in delete_ui)

    def test_explicit_open_and_save_can_intentionally_continue_a_tombstoned_draft(self):
        open_draft = self.template_source.split(
            'async function openStandaloneTSRDraft(id)', 1
        )[1].split('async function deleteStandaloneTSRDraft', 1)[0]
        save_draft = self.template_source.split(
            'async function saveStandaloneTSRLocalDraft()', 1
        )[1].split('async function resetStandaloneTSRForm', 1)[0]
        local_save = self.template_source.split(
            'async function saveStandaloneTSRDraftLocally(data', 1
        )[1].split('async function clearStandaloneTSRDraftLocally', 1)[0]

        self.assertTrue('clearStandaloneTSRDraftDeletionForExplicitAction' in open_draft,
                        'An engineer must be able to deliberately open a local draft.')
        if 'clearStandaloneTSRDraftDeletionForExplicitAction' in open_draft:
            self.assertLess(open_draft.index('clearStandaloneTSRDraftDeletionForExplicitAction'),
                            open_draft.index('applyStandaloneTSRDraftData'))
        self.assertTrue('clearStandaloneTSRDraftDeletionForExplicitAction' in save_draft,
                        'An engineer must be able to deliberately save after a deletion.')
        self.assertTrue('if(!deletionReleased)' in save_draft,
                        'A failed tombstone release must block the explicit save truthfully.')
        self.assertTrue("reason:'draft_deletion_pending'" in local_save,
                        'Queued background/local saves must not clear a deletion marker.')
        self.assertNotIn('clearStandaloneTSRDraftDeletionForExplicitAction', local_save,
                         'Only a deliberate open or Save Draft action may release the tombstone.')
        self.assertTrue('OFFLINE_TSR_DB_VERSION = 1' in self.template_source,
                        'Tombstones must not migrate or purge existing IndexedDB draft records.')

    def test_nonconflicting_single_copy_keeps_existing_open_action(self):
        panel = self.template_source.split(
            'async function renderStandaloneTSRDraftPanel', 1
        )[1].split('async function openStandaloneTSRDraft', 1)[0]
        self.assertIn('openStandaloneTSRDraft', panel)
        self.assertIn('group.versions.length > 1', panel)

    def test_source_grouping_and_copy_selection_keep_original_reservation_without_saving(self):
        grouping_helpers = self.template_source.split(
            'function standaloneTSRDraftComparableSignature', 1
        )[1].split('function parseOfflineTSRDate', 1)[0]
        selection = self.template_source.split(
            'async function useStandaloneTSRDraftCopy', 1
        )[1].split('async function openStandaloneTSRDraft', 1)[0]
        script = r"""
function parseOfflineTSRDate(value){const stamp=Date.parse(String(value||''));return Number.isFinite(stamp)?stamp:null;}
function getStandaloneTSRDraftTitle(){return 'Saved TSR';}
function getStandaloneTSRDraftSubtitle(){return 'Service visit';}
let standaloneTSRDraftRecoveryChoices = new Map();
let applied = null;
let saveCalls = 0;
let syncCalls = 0;
let submitCalls = 0;
const local = {
  id:'draft-recovery-one', source:'offline_tsr_page',
  recoverySourceKey:'indexeddb', recoverySourceKind:'indexeddb',
  tsr_number:'20260924-01-ABC', reservation_token:'original-reservation-token',
  updated_at:'2026-09-24T08:00:00Z',
  payload:{_draft_id:'draft-recovery-one', savedAt:'2026-09-24T08:00:00Z',
    'tsr-number':'20260924-01-ABC', reservation_token:'original-reservation-token',
    'tsr-complaint':'device copy', signatures:{serviced:'device-signature', acknowledged:''},
    attachments:[{name:'device.pdf', blob_id:'device-blob'}]}
};
const mirror = {
  id:'draft-recovery-one', source:'localstorage', recoverySourceKey:'localstorage', recoverySourceKind:'localstorage',
  updated_at:'2026-09-24T08:05:00Z',
  payload:{...local.payload, savedAt:'2026-09-24T08:05:00Z', _server_draft_attachment_count:1}
};
const account = {
  id:'draft-recovery-one', source:'server_draft', recoverySourceKey:'account', recoverySourceKind:'account',
  tsr_number:'20260924-99-XYZ', reservation_token:'different-server-token', updated_at:'2026-09-24T08:10:00Z',
  payload:{_draft_id:'draft-recovery-one', 'tsr-number':'20260924-99-XYZ', reservation_token:'different-server-token',
    'tsr-complaint':'account copy', signatures:{serviced:'account-signature', acknowledged:'client-signature'},
    attachments:[{name:'account.pdf', blob_id:'account-blob'}]}
};
const sourceRecords = [local, mirror, account];
function waitForStandaloneTSRLocalSaves(){return Promise.resolve();}
function getStandaloneTSRDraftRecords(){return Promise.resolve(sourceRecords);}
function rehydrateStandaloneTSRDraftPayload(data){return Promise.resolve({...data});}
function refreshStandaloneScheduleOptions(){return Promise.resolve();}
function applyStandaloneTSRDraftData(data){applied = data;return true;}
function setStandaloneTSRSaveStatus(){}
function showTSRStatus(){}
function renderStandaloneTSRDraftPanel(){return Promise.resolve();}
function saveStandaloneTSRDraftLocally(){saveCalls++;}
function syncStandaloneTSRDraftToServer(){syncCalls++;}
function submitStandaloneTSROnline(){submitCalls++;}
function escapeAttr(value){return String(value);}
function escapeHTML(value){return String(value);}
function normalizeQueuedAttachments(value){return value||[];}
function hasStandaloneScheduleSelection(){return true;}
function isStandaloneTSRDraftMeaningful(){return true;}
""" + "function standaloneTSRDraftComparableSignature" + grouping_helpers + "\n" + "async function useStandaloneTSRDraftCopy" + selection + r"""
(async()=>{
  const groups = groupStandaloneTSRDraftVersions(sourceRecords);
  await useStandaloneTSRDraftCopy('draft-recovery-one','account');
  console.log(JSON.stringify({
    distinctVersions:groups[0].versions.length,
    deviceSources:groups[0].versions[0].recoverySourceKeys,
    loadedComplaint:applied?.['tsr-complaint'],
    draftId:applied?._draft_id,
    tsrNumber:applied?.['tsr-number'],
    reservationToken:applied?.reservation_token,
    signatures:applied?.signatures,
    attachments:applied?.attachments,
    selected:standaloneTSRDraftRecoveryChoices.get('draft-recovery-one'),
    saveCalls,syncCalls,submitCalls
  }));
})().catch(error=>{console.error(error);process.exit(1);});
"""
        result = subprocess.run([str(NODE), '-e', script], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(output['distinctVersions'], 2)
        self.assertIn('indexeddb', output['deviceSources'])
        self.assertIn('localstorage', output['deviceSources'])
        self.assertEqual(output['loadedComplaint'], 'account copy')
        self.assertEqual(output['draftId'], 'draft-recovery-one')
        self.assertEqual(output['tsrNumber'], '20260924-01-ABC')
        self.assertEqual(output['reservationToken'], 'original-reservation-token')
        self.assertEqual(output['signatures']['serviced'], 'account-signature')
        self.assertEqual(output['attachments'][0]['blob_id'], 'account-blob')
        self.assertEqual(output['selected'], 'account')
        self.assertEqual((output['saveCalls'], output['syncCalls'], output['submitCalls']), (0, 0, 0))

    def test_merge_keeps_a_divergent_device_record_and_exposes_account_copy(self):
        helper_functions = self.template_source.split(
            'function buildStandaloneTSRAccountDraftCandidate', 1
        )[1].split('function parseOfflineTSRDate', 1)[0]
        merge = self.template_source.split(
            'async function mergeServerStandaloneTSRDrafts', 1
        )[1].split('async function refreshStandaloneTSRDraftPanel', 1)[0]
        script = r"""
function parseOfflineTSRDate(value){const stamp=Date.parse(String(value||''));return Number.isFinite(stamp)?stamp:null;}
function getStandaloneTSRDraftTitle(){return 'Saved TSR';}
function getStandaloneTSRDraftSubtitle(){return 'Service visit';}
Object.defineProperty(globalThis,'navigator',{value:{onLine:true},configurable:true});
const standaloneTSRAccountDraftCandidates = new Map();
const standaloneTSRDraftServerStates = new Map();
let standaloneTSRDraftHistoryCandidates = new Map();
let standaloneTSRDraftHistoryWarning = '';
const standaloneTSRDraftConflictIds = new Set();
const standaloneTSRDraftRecoveryVariants = new Map();
const standaloneTSRDraftRecoveryChoices = new Map();
const STANDALONE_TSR_ACCOUNT_SCOPE='current';
const OFFLINE_TSR_DB_STORES={drafts:'drafts'};
const OFFLINE_TSR_ACTIVE_DRAFT_ID='active';
let standaloneTSRServerDraftsHydrated=false;
let writes=0, uploads=0;
const local={id:'draft-divergent',account_id:'current',source:'offline_tsr_page',updated_at:'2026-09-24T08:00:00Z',
  schedule_id:'17',tsr_number:'20260924-01-ABC',reservation_token:'reservation-one',
  payload:{_draft_id:'draft-divergent','tsr-number':'20260924-01-ABC',reservation_token:'reservation-one',
    'tsr-complaint':'device work',signatures:{serviced:'device-signature',acknowledged:''},
    attachments:[{name:'device.pdf',blob_id:'device-file'}]}};
const remote={draft_key:'draft-divergent',updated_at:'2026-09-24T08:10:00Z',device_updated_at:'2026-09-24T08:10:00Z',
  schedule_id:'17',tsr_number:'20260924-01-ABC',reservation_token:'reservation-one',
  payload:{_draft_id:'draft-divergent','tsr-number':'20260924-01-ABC',reservation_token:'reservation-one',
    'tsr-complaint':'account work',signatures:{serviced:'account-signature',acknowledged:'client-signature'},
    attachments:[{name:'account.pdf',blob_id:'account-file'}]}};
globalThis.fetch=async(url)=>url==='/get_tsr_draft_history'
  ? ({ok:true,json:async()=>({status:'success',versions:[]})})
  : ({ok:true,json:async()=>({status:'success',drafts:[remote]})});
function flushStandaloneTSRServerDraftDeletes(){return Promise.resolve();}
function waitForStandaloneTSRLocalSaves(){return Promise.resolve();}
function readStandaloneTSRServerDraftDeleteQueue(){return [];}
function isStandaloneTSRDraftDeletionTombstoned(){return false;}
function loadStandaloneTSRDraftRecordsFromIndexedDB(){return Promise.resolve([local]);}
function loadStandaloneTSRDraftFromLocalStorageFallback(){return null;}
function offlineTSRDBGet(){return Promise.resolve(null);}
function saveStandaloneTSRDraftToLocalStorageFallback(){return true;}
function isStandaloneTSRDraftMeaningful(){return true;}
function enqueueStandaloneTSRServerDraftSync(){uploads++;return Promise.resolve({status:'success'});}
function offlineTSRDBPut(){writes++;return Promise.resolve();}
function persistStandaloneTSRDraftServerMetadata(){return Promise.resolve(true);}
function archiveStandaloneTSRDraftVersion(){return Promise.resolve({success:true,status:'success'});}
""" + "function buildStandaloneTSRAccountDraftCandidate" + helper_functions + "\n" + "async function mergeServerStandaloneTSRDrafts" + merge + r"""
(async()=>{
  const result=await mergeServerStandaloneTSRDrafts();
  const variants=standaloneTSRDraftRecoveryVariants.get('draft-divergent')||[];
  console.log(JSON.stringify({
    merged:result.success===true,
    writes,uploads,
    conflict:standaloneTSRDraftConflictIds.has('draft-divergent'),
    accountCandidate:standaloneTSRAccountDraftCandidates.get('draft-divergent')?.payload?.['tsr-complaint'],
    savedVariants:variants.map(item=>item.payload?.['tsr-complaint']).sort()
  }));
})().catch(error=>{console.error(error);process.exit(1);});
"""
        result = subprocess.run([str(NODE), '-e', script], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertTrue(output['merged'])
        self.assertEqual((output['writes'], output['uploads']), (0, 0))
        self.assertTrue(output['conflict'])
        self.assertEqual(output['accountCandidate'], 'account work')
        self.assertEqual(output['savedVariants'], ['account work', 'device work'])

    def test_device_drafts_stay_with_their_account_and_legacy_adoption_is_conservative(self):
        fallback_key = self.template_source.split(
            'function getStandaloneTSRDraftFallbackKey(){', 1
        )[1].split('const OFFLINE_TSR_STORAGE_HEALTH_ADMIN', 1)[0]
        identity_helpers = self.template_source.split(
            'function getStandaloneTSRDraftEngineerIdentity(record){', 1
        )[1].split('function getTSROtherAssignedEngineerNames', 1)[0]
        local_record_loader = self.template_source.split(
            'async function loadStandaloneTSRDraftRecordsFromIndexedDB', 1
        )[1].split('async function loadStandaloneTSRDraftRecordById', 1)[0]
        merge = self.template_source.split(
            'async function mergeServerStandaloneTSRDrafts', 1
        )[1].split('async function refreshStandaloneTSRDraftPanel', 1)[0]
        account_candidate = self.template_source.split(
            'function buildStandaloneTSRAccountDraftCandidate', 1
        )[1].split('function buildStandaloneTSRHistoryDraftCandidate', 1)[0]
        script = r"""
Object.defineProperty(globalThis,'navigator',{value:{onLine:true},configurable:true});
const STANDALONE_TSR_KEY='medicalServiceStandaloneTSRDraftV1';
let STANDALONE_TSR_ACCOUNT_SCOPE='current';
let LOGGED_IN_ENGINEER_NAME='Current Engineer';
const OFFLINE_TSR_DB_STORES={drafts:'drafts'};
const OFFLINE_TSR_ACTIVE_DRAFT_ID='active';
const localStorageValues=new Map();
globalThis.localStorage={
  getItem(key){return localStorageValues.has(key)?localStorageValues.get(key):null;},
  setItem(key,value){localStorageValues.set(key,String(value));},
  removeItem(key){localStorageValues.delete(key);}
};
const standaloneTSRAccountDraftCandidates=new Map();
const standaloneTSRDraftServerStates=new Map();
const standaloneTSRDraftHistoryCandidates=new Map();
const standaloneTSRDraftRecoveryVariants=new Map();
const standaloneTSRDraftConflictIds=new Set();
const standaloneTSRDraftRecoveryChoices=new Map();
const tombstones=new Set(['current:deleted-legacy']);
const dbDrafts=[
  {id:'alvin-draft',account_id:'alvin',payload:{_draft_id:'alvin-draft','tsr-serviced-by':'Alvin Mamangon','tsr-complaint':'Alvin device work'}},
  {id:'current-draft',account_id:'current',payload:{_draft_id:'current-draft','tsr-serviced-by':'Current Engineer','tsr-complaint':'Current work'}},
  {id:'deleted-legacy',payload:{_draft_id:'deleted-legacy','tsr-serviced-by':'Current Engineer','tsr-complaint':'Deleted copy'}},
  {id:'ambiguous-legacy',payload:{_draft_id:'ambiguous-legacy','tsr-serviced-by':'Alvin Mamangon','tsr-complaint':'Ambiguous copy'}},
  {id:'current-legacy',payload:{_draft_id:'current-legacy','tsr-serviced-by':' Current  Engineer ','tsr-complaint':'Recoverable current work'}}
];
let remoteDrafts=[];
let uploads=[];
let standaloneTSRServerDraftsHydrated=false;
function normalizeTSREngineerIdentity(value){return String(value||'').trim().toLowerCase().replace(/[^a-z0-9]+/g,' ').replace(/\s+/g,' ').trim();}
function isStandaloneTSRDraftDeletionTombstoned(id){return tombstones.has(`${STANDALONE_TSR_ACCOUNT_SCOPE}:${id}`);}
function isStandaloneTSRDraftMeaningful(){return true;}
function getStandaloneTSRDraftTitle(){return 'Saved TSR';}
function getStandaloneTSRDraftSubtitle(){return 'Service visit';}
function groupStandaloneTSRDraftVersions(items){return [{versions:items}];}
function standaloneTSRDraftRecordsHaveSameContent(a,b){return JSON.stringify(a?.payload)===JSON.stringify(b?.payload);}
function rememberStandaloneTSRDraftConflict(){}
function rememberStandaloneTSRDraftServerState(){}
function flushStandaloneTSRServerDraftDeletes(){return Promise.resolve();}
function readStandaloneTSRServerDraftDeleteQueue(){return [];}
function waitForStandaloneTSRLocalSaves(){return Promise.resolve();}
function offlineTSRDBGetAll(){return Promise.resolve(dbDrafts);}
async function offlineTSRDBPut(store,record){const index=dbDrafts.findIndex(item=>item.id===record.id);if(index>=0)dbDrafts[index]=record;else dbDrafts.push(record);return record;}
function loadStandaloneTSRDraftFromLocalStorageFallback(){return null;}
function persistStandaloneTSRDraftServerMetadata(){return Promise.resolve(true);}
function enqueueStandaloneTSRServerDraftSync(record){uploads.push({id:record.id,account_id:record.account_id});return Promise.resolve({status:'success'});}
function archiveStandaloneTSRDraftVersion(){return Promise.resolve({success:true});}
function setStandaloneTSRSaveStatus(){}
globalThis.fetch=async(url)=>url==='/get_tsr_draft_history'
  ? ({ok:true,json:async()=>({status:'success',versions:[]})})
  : ({ok:true,json:async()=>({status:'success',drafts:remoteDrafts})});
""" + "function getStandaloneTSRDraftFallbackKey(){" + fallback_key + "function getStandaloneTSRDraftEngineerIdentity(record){" + identity_helpers + "function getTSROtherAssignedEngineerNames(){}\n" + "async function loadStandaloneTSRDraftRecordsFromIndexedDB" + local_record_loader + "function buildStandaloneTSRAccountDraftCandidate" + account_candidate + "async function mergeServerStandaloneTSRDrafts" + merge + r"""
(async()=>{
  const sameKeyLegacyEligible=standaloneTSRDraftCanAdoptLegacy(
    {id:'remote-key-legacy',payload:{'tsr-serviced-by':'Alvin Mamangon'}},
    new Set(['remote-key-legacy'])
  );
  const ambiguousLegacyEligible=standaloneTSRDraftCanAdoptLegacy(
    {id:'unmatched-legacy',payload:{'tsr-serviced-by':'Alvin Mamangon'}},
    new Set()
  );
  const firstMerge=await mergeServerStandaloneTSRDrafts();
  const currentRows=await loadStandaloneTSRDraftRecordsFromIndexedDB();
  const accountStateAfterSwitch={
    records:currentRows.map(item=>item.id).sort(),
    uploads:uploads.slice().sort((a,b)=>a.id.localeCompare(b.id)),
    foreignCopy:dbDrafts.find(item=>item.id==='alvin-draft'),
    deletedLegacy:dbDrafts.find(item=>item.id==='deleted-legacy')
  };
  STANDALONE_TSR_ACCOUNT_SCOPE='alvin';
  LOGGED_IN_ENGINEER_NAME='Alvin Mamangon';
  const alvinRows=await loadStandaloneTSRDraftRecordsFromIndexedDB();
  remoteDrafts=[
    {draft_key:'deleted-legacy',payload:{_draft_id:'deleted-legacy','tsr-complaint':'stale account copy'}},
    {draft_key:'alvin-draft',payload:{_draft_id:'alvin-draft','tsr-complaint':'copied account data'}}
  ];
  STANDALONE_TSR_ACCOUNT_SCOPE='current';
  LOGGED_IN_ENGINEER_NAME='Current Engineer';
  const secondMerge=await mergeServerStandaloneTSRDrafts();
  console.log(JSON.stringify({
    firstMerge:firstMerge.success===true,
    secondMerge:secondMerge.success===true,
    secondMergeReason:secondMerge.reason||'',
    sameKeyLegacyEligible,
    ambiguousLegacyEligible,
    currentIds:accountStateAfterSwitch.records,
    uploadedIds:accountStateAfterSwitch.uploads.map(item=>item.id).sort(),
    uploadScopes:accountStateAfterSwitch.uploads.map(item=>item.account_id),
    alvinIds:alvinRows.map(item=>item.id).sort(),
    foreignAfterSwitch:accountStateAfterSwitch.foreignCopy.account_id,
    foreignPayload:accountStateAfterSwitch.foreignCopy.payload['tsr-complaint'],
    deletedLegacyScope:accountStateAfterSwitch.deletedLegacy.account_id||'',
    staleDeletedAccountCandidate:standaloneTSRAccountDraftCandidates.has('deleted-legacy'),
    foreignCollisionUnchanged:dbDrafts.find(item=>item.id==='alvin-draft').payload['tsr-complaint'],
    copiedAccountCandidate:standaloneTSRAccountDraftCandidates.get('alvin-draft')?.payload?.['tsr-complaint']
  }));
})().catch(error=>{console.error(error);process.exit(1);});
"""
        result = subprocess.run([str(NODE), '-e', script], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertTrue(output['firstMerge'])
        self.assertTrue(output['secondMerge'], output['secondMergeReason'])
        self.assertTrue(output['sameKeyLegacyEligible'])
        self.assertFalse(output['ambiguousLegacyEligible'])
        self.assertEqual(output['currentIds'], ['current-draft', 'current-legacy'])
        self.assertEqual(output['uploadedIds'], ['current-draft', 'current-legacy'])
        self.assertEqual(set(output['uploadScopes']), {'current'})
        self.assertEqual(output['alvinIds'], ['alvin-draft', 'ambiguous-legacy'])
        self.assertEqual(output['foreignAfterSwitch'], 'alvin')
        self.assertEqual(output['foreignPayload'], 'Alvin device work')
        self.assertEqual(output['deletedLegacyScope'], '')
        self.assertFalse(output['staleDeletedAccountCandidate'])
        self.assertEqual(output['foreignCollisionUnchanged'], 'Alvin device work')
        self.assertEqual(output['copiedAccountCandidate'], 'copied account data')

    def test_localstorage_fallback_is_separate_per_engineer_and_legacy_copy_is_preserved(self):
        fallback_key = self.template_source.split(
            'function getStandaloneTSRDraftFallbackKey(){', 1
        )[1].split('const OFFLINE_TSR_STORAGE_HEALTH_ADMIN', 1)[0]
        identity_helpers = self.template_source.split(
            'function getStandaloneTSRDraftEngineerIdentity(record){', 1
        )[1].split('function getTSROtherAssignedEngineerNames', 1)[0]
        fallback_functions = self.template_source.split(
            'function saveStandaloneTSRDraftToLocalStorageFallback(data){', 1
        )[1].split('function syncStandaloneTSRAddressFromSchedule', 1)[0]
        script = r"""
const STANDALONE_TSR_KEY='medicalServiceStandaloneTSRDraftV1';
const OFFLINE_TSR_ACTIVE_DRAFT_ID='active';
const OFFLINE_TSR_DB_STORES={drafts:'drafts'};
let STANDALONE_TSR_ACCOUNT_SCOPE='alvin';
let LOGGED_IN_ENGINEER_NAME='Alvin Mamangon';
let standaloneCurrentDraftId='';
const standaloneTSRDraftServerStates=new Map();
const standaloneTSRAccountDraftCandidates=new Map();
const storage=new Map();
globalThis.localStorage={getItem(key){return storage.has(key)?storage.get(key):null;},setItem(key,value){storage.set(key,String(value));},removeItem(key){storage.delete(key);}};
function normalizeTSREngineerIdentity(value){return String(value||'').trim().toLowerCase().replace(/[^a-z0-9]+/g,' ').replace(/\s+/g,' ').trim();}
function projectOfflineTSRPayloadForLocalStorage(data){return {...data};}
function isStandaloneTSRDraftDeletionTombstoned(){return false;}
function offlineTSRDBPut(){return Promise.resolve();}
""" + "function getStandaloneTSRDraftFallbackKey(){" + fallback_key + "function getStandaloneTSRDraftEngineerIdentity(record){" + identity_helpers + "function getTSROtherAssignedEngineerNames(){}\nfunction saveStandaloneTSRDraftToLocalStorageFallback(data){" + fallback_functions + "function syncStandaloneTSRAddressFromSchedule(){}\n" + r"""
const alvinSaved=saveStandaloneTSRDraftToLocalStorageFallback({_draft_id:'alvin-1','tsr-serviced-by':'Alvin Mamangon','tsr-complaint':'Alvin work'});
const alvinKey=getStandaloneTSRDraftFallbackKey();
STANDALONE_TSR_ACCOUNT_SCOPE='rhea';
LOGGED_IN_ENGINEER_NAME='Rhea Engineer';
const rheaBeforeSave=loadStandaloneTSRDraftFromLocalStorageFallback();
const rheaSaved=saveStandaloneTSRDraftToLocalStorageFallback({_draft_id:'rhea-1','tsr-serviced-by':'Rhea Engineer','tsr-complaint':'Rhea work'});
const rheaKey=getStandaloneTSRDraftFallbackKey();
const alvinPreserved=JSON.parse(storage.get(alvinKey))._draft_id==='alvin-1';
storage.set(STANDALONE_TSR_KEY,JSON.stringify({_draft_id:'legacy-alvin','tsr-serviced-by':'Alvin Mamangon','tsr-complaint':'Legacy Alvin work'}));
const ambiguousRead=loadStandaloneTSRDraftFromLocalStorageFallback();
const legacyKeptForOwner=storage.has(STANDALONE_TSR_KEY);
STANDALONE_TSR_ACCOUNT_SCOPE='alvin';
LOGGED_IN_ENGINEER_NAME='Alvin Mamangon';
storage.delete(getStandaloneTSRDraftFallbackKey());
const adoptedLegacy=loadStandaloneTSRDraftFromLocalStorageFallback();
console.log(JSON.stringify({
  keysDiffer:alvinKey!==rheaKey,
  alvinSaved,rheaSaved,
  rheaBeforeSave:rheaBeforeSave===null,
  alvinPreserved,
  ambiguousHidden:ambiguousRead?.['tsr-complaint']!=='Legacy Alvin work',
  legacyKeptForOwner,
  ownerRecovers:adoptedLegacy?.['tsr-complaint']==='Legacy Alvin work',
  legacyStillPresent:storage.has(STANDALONE_TSR_KEY),
  adoptedScoped:storage.has(alvinKey)
}));
"""
        result = subprocess.run([str(NODE), '-e', script], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertTrue(output['keysDiffer'])
        self.assertTrue(output['alvinSaved'] and output['rheaSaved'])
        self.assertTrue(output['rheaBeforeSave'])
        self.assertTrue(output['alvinPreserved'])
        self.assertTrue(output['ambiguousHidden'])
        self.assertTrue(output['legacyKeptForOwner'])
        self.assertTrue(output['ownerRecovers'])
        self.assertTrue(output['legacyStillPresent'])
        self.assertTrue(output['adoptedScoped'])

    def test_foreign_indexeddb_record_cannot_be_overwritten_or_deleted(self):
        save_indexed = self.template_source.split(
            'async function saveStandaloneTSRDraftToIndexedDB', 1
        )[1].split('async function loadStandaloneTSRDraftFromIndexedDB', 1)[0]
        clear_local = self.template_source.split(
            'async function clearStandaloneTSRDraftFromIndexedDB', 1
        )[1].split('function saveStandaloneTSRDraftToLocalStorageFallback', 1)[0]
        fallback_key = self.template_source.split(
            'function getStandaloneTSRDraftFallbackKey(){', 1
        )[1].split('const OFFLINE_TSR_STORAGE_HEALTH_ADMIN', 1)[0]
        identity_helpers = self.template_source.split(
            'function getStandaloneTSRDraftEngineerIdentity(record){', 1
        )[1].split('function getTSROtherAssignedEngineerNames', 1)[0]
        script = r"""
const STANDALONE_TSR_KEY='medicalServiceStandaloneTSRDraftV1';
const STANDALONE_TSR_ACCOUNT_SCOPE='rhea';
const LOGGED_IN_ENGINEER_NAME='Rhea Engineer';
const OFFLINE_TSR_DB_STORES={drafts:'drafts'};
const OFFLINE_TSR_ACTIVE_DRAFT_ID='active';
let standaloneCurrentDraftId='shared-key';
const foreignRecord={id:'shared-key',account_id:'alvin',payload:{_draft_id:'shared-key','tsr-serviced-by':'Alvin Mamangon','tsr-complaint':'Alvin original'}};
let putCount=0,deleteCount=0,buildCount=0;
function normalizeTSREngineerIdentity(value){return String(value||'').trim().toLowerCase().replace(/[^a-z0-9]+/g,' ').replace(/\s+/g,' ').trim();}
function resolveStandaloneTSRDraftId(data){return String(data?._draft_id||'new-key');}
function offlineTSRDBGet(){return Promise.resolve(foreignRecord);}
function offlineTSRDBPut(){putCount++;return Promise.resolve();}
function offlineTSRDBDelete(){deleteCount++;return Promise.resolve();}
function isIndexedDBSupported(){return true;}
function waitForStandaloneTSRLocalSaves(){return Promise.resolve();}
function adoptStandaloneTSRDraftForCurrentAccount(){return Promise.resolve(null);}
function buildOfflineTSRDraftRecord(){buildCount++;return Promise.resolve({id:'shared-key',account_id:'rhea',payload:{}});}
const storage=new Map();
globalThis.localStorage={getItem(key){return storage.has(key)?storage.get(key):null;},setItem(key,value){storage.set(key,String(value));},removeItem(key){storage.delete(key);}};
""" + "function getStandaloneTSRDraftFallbackKey(){" + fallback_key + "function getStandaloneTSRDraftEngineerIdentity(record){" + identity_helpers + "function getTSROtherAssignedEngineerNames(){}\n" + "async function saveStandaloneTSRDraftToIndexedDB" + save_indexed + "async function clearStandaloneTSRDraftFromIndexedDB" + clear_local + r"""
(async()=>{
  let rejected=false;
  try{await saveStandaloneTSRDraftToIndexedDB({_draft_id:'shared-key','tsr-complaint':'Rhea work'});}
  catch(error){rejected=true;}
  const deletion=await clearStandaloneTSRDraftFromIndexedDB('shared-key');
  console.log(JSON.stringify({
    rejected,
    buildCount,
    putCount,
    deleteCount,
    foreignScope:foreignRecord.account_id,
    foreignComplaint:foreignRecord.payload['tsr-complaint'],
    deletionConfirmedForCurrentScope:deletion.local_deleted
  }));
})().catch(error=>{console.error(error);process.exit(1);});
"""
        result = subprocess.run([str(NODE), '-e', script], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertTrue(output['rejected'])
        self.assertEqual((output['buildCount'], output['putCount'], output['deleteCount']), (0, 0, 0))
        self.assertEqual(output['foreignScope'], 'alvin')
        self.assertEqual(output['foreignComplaint'], 'Alvin original')
        self.assertTrue(output['deletionConfirmedForCurrentScope'])

    def test_draft_scope_metadata_stays_local_and_cache_release_are_updated(self):
        record_builder = self.template_source.split(
            'async function buildOfflineTSRDraftRecord', 1
        )[1].split('function buildStandaloneTSRServerDraftRequest', 1)[0]
        server_request = self.template_source.split(
            'function buildStandaloneTSRServerDraftRequest', 1
        )[1].split('function buildStandaloneTSRAccountDraftCandidate', 1)[0]
        merge = self.template_source.split(
            'async function mergeServerStandaloneTSRDrafts', 1
        )[1].split('async function refreshStandaloneTSRDraftPanel', 1)[0]
        draft_cleanup = self.template_source.split(
            'async function cleanupOfflineTSROldDraftRecords', 1
        )[1].split('async function runOfflineTSRRetentionCleanup', 1)[0]
        blob_references = self.template_source.split(
            'function collectReferencedOfflineTSRBlobIds', 1
        )[1].split('async function saveOfflineTSRCleanupMetadata', 1)[0]
        self.assertIn('account_id:STANDALONE_TSR_ACCOUNT_SCOPE', record_builder)
        self.assertIn('record?.payload', server_request)
        self.assertNotIn('account_id:', server_request.split('const payload =', 1)[1].split('return {', 1)[1])
        self.assertIn('includeOtherAccounts:true', merge)
        self.assertIn('accountId === STANDALONE_TSR_ACCOUNT_SCOPE', merge)
        self.assertIn('if(accountId || isStandaloneTSRDraftDeletionTombstoned(record.id)) continue;', merge)
        self.assertIn('localRecordsToUpload', merge)
        self.assertIn('foreignCollision', merge)
        self.assertIn('draftRecord.account_id', draft_cleanup)
        self.assertIn('record?.payload?.attachments', blob_references)

        assert_cache_version_at_least(self, 188, self.app_source)
        releases = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))['releases']
        release = next(item for item in releases if item['release_key'] == '2026-09-24-create-tsr-device-draft-account-scope')
        self.assertEqual(release['release_date'], '2026-09-24')
        self.assertIn('signed-in engineer', release['items'][0]['description'])

    def test_stale_backup_result_uses_unresolved_status_until_real_success(self):
        enqueue = self.template_source.split(
            'function enqueueStandaloneTSRServerDraftSync', 1
        )[1].split('function readStandaloneTSRServerDraftDeleteQueue', 1)[0]
        script = r"""
Object.defineProperty(globalThis,'navigator',{value:{onLine:true},configurable:true});
let standaloneTSRServerDraftSyncTimer=null;
let standaloneTSRServerDraftSyncTimerDraftId='';
let standaloneTSRServerDraftSyncChain=Promise.resolve();
const standaloneTSRDraftConflictIds=new Set();
const standaloneTSRDraftRecoveryChoices=new Map();
const standaloneTSRAccountDraftCandidates=new Map();
const standaloneTSRDraftRecoveryVariants=new Map();
const STANDALONE_TSR_ACCOUNT_SCOPE='current';
const standaloneTSRSaveStatusGeneration=1;
const standaloneTSRActiveContextVersion=1;
let nextResult={status:'success',stale_ignored:true};
const states=[];
function standaloneTSRSaveStatusContextIsActive(){return true;}
function setStandaloneTSRSaveStatus(state){states.push(state);}
function isStandaloneTSRDraftDeletionTombstoned(){return false;}
function syncStandaloneTSRDraftToServer(){return Promise.resolve(nextResult);}
""" + "function enqueueStandaloneTSRServerDraftSync" + enqueue + r"""
(async()=>{
  await enqueueStandaloneTSRServerDraftSync({id:'draft-status',account_id:'current',payload:{}},{immediate:true,statusContext:{}});
  nextResult={status:'success'};
  await enqueueStandaloneTSRServerDraftSync({id:'draft-status',account_id:'current',payload:{}},{immediate:true,statusContext:{}});
  console.log(JSON.stringify(states));
})().catch(error=>{console.error(error);process.exit(1);});
"""
        result = subprocess.run([str(NODE), '-e', script], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.strip().splitlines()[-1]), [
            'backup-in-progress', 'account-backup-conflict',
            'backup-in-progress', 'account-backed-up',
        ])

    def test_page_save_status_follows_actual_local_and_server_draft_results(self):
        local_save = self.template_source.split(
            'async function saveStandaloneTSRDraftLocally(data', 1
        )[1].split('async function clearStandaloneTSRDraftLocally', 1)[0]
        self.assertIn("setStandaloneTSRSaveStatus('saving-local'", local_save)
        self.assertIn("setStandaloneTSRSaveStatus('local-save-failed'", local_save)
        self.assertIn("setStandaloneTSRSaveStatus('local-saved-pending'", local_save)
        self.assertIn('standaloneTSRSaveStatusGeneration', local_save)
        self.assertTrue('standaloneTSRSaveStatusContextIsActive' in self.template_source,
                        'Save-state transitions must use the active draft/generation guard.')

        queued_sync = self.template_source.split(
            'function enqueueStandaloneTSRServerDraftSync', 1
        )[1].split('function readStandaloneTSRServerDraftDeleteQueue', 1)[0]
        self.assertIn('statusContext', queued_sync)
        self.assertIn("setStandaloneTSRSaveStatus('backup-in-progress'", queued_sync)
        self.assertIn('account-backed-up', queued_sync)
        self.assertIn('account-backup-failed', queued_sync)
        self.assertIn('standaloneTSRSaveStatusContextIsActive(statusContext)', queued_sync)
        self.assertLess(
            queued_sync.index('return syncStandaloneTSRDraftToServer(record)'),
            queued_sync.index("setStandaloneTSRSaveStatus('account-backed-up'"),
            'Account backup must only be reported after syncStandaloneTSRDraftToServer resolves.',
        )
        sync_result = queued_sync.split('.then(result =>', 1)[1].split('.catch(error =>', 1)[0]
        self.assertIn("result?.status === 'success'", sync_result)
        self.assertIn("setStandaloneTSRSaveStatus('local-saved-pending'", sync_result,
                      'A skipped/offline sync must not be shown as a confirmed account backup.')

        status_renderer = self.template_source.split(
            'function setStandaloneTSRSaveStatus', 1
        )[1].split('function ', 1)[0]
        self.assertIn('standaloneTSRServerBackupFailureText(details.error)', status_renderer)
        self.assertIn('attachments_not_durable', status_renderer)
        self.assertIn("source === 'localstorage'", status_renderer)
        self.assertTrue('role="status" aria-live="polite"' in self.template_source,
                        'The save-state indicator must be announced accessibly.')

    def test_save_status_rejects_stale_draft_callbacks(self):
        self.assertTrue('function standaloneTSRSaveStatusContextIsActive' in self.template_source,
                        'Save-state callbacks must have a current-draft guard.')
        guard = self.template_source.split(
            'function standaloneTSRSaveStatusContextIsActive', 1
        )[1].split('function ', 1)[0]
        self.assertIn('standaloneCurrentDraftId', guard)
        self.assertIn('standaloneTSRSaveStatusGeneration', guard)
        self.assertIn('standaloneTSRActiveContextVersion', guard)
        for reset in ('clearStandaloneTSRPage', 'resetStandaloneTSRForm', 'finishStandaloneTSRFinalSave'):
            body = self.template_source.split(f'async function {reset}', 1)[1].split('\n}', 1)[0]
            self.assertIn('initializeBlankStandaloneTSR()', body)
        reset_status = self.template_source.split(
            'function resetStandaloneTSRSaveStatus', 1
        )[1].split('function ', 1)[0]
        self.assertIn("setStandaloneTSRSaveStatus('no-changes'", reset_status)

    def test_service_worker_cache_is_bumped_for_server_drafts(self):
        """A floor, never a pinned version.

        This pinned the exact v80 string, so the next required bump failed the suite -- the
        anti-pattern section 6 of pending-work.md records this repository having already had
        to undo. The bump is a mandatory step for any APP_SHELL change; a test that punishes
        it is a test that trains people to skip it.
        """
        assert_cache_version_at_least(self, 188, self.app_source)
        self.assertIn("'/offline-tsr',", self.app_source)

    def test_draft_recovery_release_entry_is_present(self):
        releases = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))['releases']
        release = next(item for item in releases if item['release_key'] == '2026-09-24-create-tsr-draft-recovery')
        self.assertEqual(release['release_key'], '2026-09-24-create-tsr-draft-recovery')
        self.assertEqual(release['release_date'], '2026-09-24')
        self.assertIn('Choose which copy to continue', release['items'][0]['description'])
        self.assertTrue(any(item['item_key'] == '2026-09-24-tsr-draft-version-history' for item in release['items']))

    def test_draft_deletion_release_entry_is_present(self):
        releases = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))['releases']
        release = next(item for item in releases if item['release_key'] == '2026-09-24-create-tsr-draft-deletion')
        self.assertEqual(release['release_date'], '2026-09-24')
        self.assertTrue(any(
            item['item_key'] == '2026-09-24-create-tsr-draft-deletion-engineers' and
            'keeps account deletion queued' in item['description']
            for item in release['items']
        ))


@unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
class TsrDraftRouteTests(unittest.TestCase):
    @contextmanager
    def isolated_route_clients(self):
        fd, database_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        extension = None
        original_engine = None
        original_ready = None
        original_reservation_ready = None
        test_engine = None
        original_csrf = None
        try:
            with app_module.app.app_context():
                extension = app_module.app.extensions['sqlalchemy']
                engines = extension._app_engines[app_module.app]
                original_engine = engines[None]
                original_ready = app_module._tsr_draft_table_ready
                original_reservation_ready = app_module._tsr_number_reservation_table_ready
                original_csrf = app_module.app.config.get('WTF_CSRF_ENABLED')
                app_module.app.config['WTF_CSRF_ENABLED'] = False
                test_engine = create_engine(f"sqlite:///{database_path.replace(os.sep, '/')}")
                engines[None] = test_engine
                app_module._tsr_draft_table_ready = False
                app_module._tsr_number_reservation_table_ready = False
                app_module.db.session.remove()
                app_module.db.create_all()
                app_module.ensure_tsr_draft_schema()
                suffix = pathlib.Path(database_path).stem[-10:]
                user_one = app_module.User(username=f'draft-history-one-{suffix}', password='test-only', role='engineer', is_active=True)
                user_two = app_module.User(username=f'draft-history-two-{suffix}', password='test-only', role='engineer', is_active=True)
                app_module.db.session.add_all([user_one, user_two])
                app_module.db.session.commit()
                user_ids = {'one': user_one.id, 'two': user_two.id}

            clients = {}
            for label, user_id in user_ids.items():
                client = app_module.app.test_client()
                with client.session_transaction() as session:
                    session['_user_id'] = str(user_id)
                    session['_fresh'] = True
                clients[label] = client
            yield clients, user_ids
        finally:
            if extension is not None:
                with app_module.app.app_context():
                    app_module.db.session.remove()
                    if original_engine is not None:
                        extension._app_engines[app_module.app][None] = original_engine
                    if original_ready is not None:
                        app_module._tsr_draft_table_ready = original_ready
                    if original_reservation_ready is not None:
                        app_module._tsr_number_reservation_table_ready = original_reservation_ready
                    if original_csrf is not None:
                        app_module.app.config['WTF_CSRF_ENABLED'] = original_csrf
            if test_engine is not None:
                test_engine.dispose()
            if database_path and os.path.exists(database_path):
                os.unlink(database_path)

    def test_two_device_revisions_archive_replaced_current_and_stale_candidate(self):
        with self.isolated_route_clients() as (clients, user_ids):
            client_a = clients['one']
            client_b = app_module.app.test_client()
            with client_b.session_transaction() as session:
                session['_user_id'] = str(user_ids['one'])
                session['_fresh'] = True

            first = client_a.post('/save_tsr_draft', json={
                'draft_key': 'two-device-draft',
                'device_updated_at': '2026-09-24T08:00:00+08:00',
                'payload': {
                    'tsr-complaint': 'Device copies start here',
                    'signatures': {'serviced': 'signature-v1', 'acknowledged': ''},
                    'attachments': [{'name': 'inspection.jpg', 'blob_id': 'local-attachment-1'}],
                },
            })
            self.assertEqual(first.status_code, 200)
            first_body = first.get_json()
            token = first_body['reservation_token']
            number = first_body['tsr_number']
            self.assertEqual(first_body['revision'], 1)
            self.assertEqual(first_body['draft']['content_hash'], first_body['hash'])

            accepted = client_a.post('/save_tsr_draft', json={
                'draft_key': 'two-device-draft',
                'base_revision': 1,
                'device_updated_at': '2026-09-24T08:01:00+08:00',
                'payload': {
                    'tsr-complaint': 'Device A saved first',
                    'tsr-number': number,
                    'reservation_token': token,
                    'signatures': {'serviced': 'signature-v2', 'acknowledged': ''},
                    'attachments': [{'name': 'inspection.jpg', 'blob_id': 'local-attachment-1'}],
                },
            })
            self.assertEqual(accepted.status_code, 200)
            self.assertEqual(accepted.get_json()['revision'], 2)
            self.assertEqual(accepted.get_json()['history_count'], 1)

            stale = client_b.post('/save_tsr_draft', json={
                'draft_key': 'two-device-draft',
                'base_revision': 1,
                # A future device timestamp cannot make an older revision authoritative.
                'device_updated_at': '2099-01-01T00:00:00+00:00',
                'payload': {
                    'tsr-complaint': 'Device B stale copy',
                    'tsr-number': number,
                    'reservation_token': token,
                    'signatures': {'serviced': 'signature-device-b', 'acknowledged': ''},
                    'attachments': [{'name': 'inspection.jpg', 'blob_id': 'local-attachment-1'}],
                },
            })
            self.assertEqual(stale.status_code, 409)
            stale_body = stale.get_json()
            self.assertEqual(stale_body['status'], 'conflict')
            self.assertEqual(stale_body['conflict_metadata']['reason'], 'revision_mismatch')
            self.assertEqual(stale_body['draft']['payload']['tsr-complaint'], 'Device A saved first')
            self.assertEqual(stale_body['revision'], 2)
            self.assertEqual(stale_body['history_count'], 2)
            self.assertEqual(stale_body['draft']['reservation_token'], token)
            self.assertEqual(stale_body['draft']['tsr_number'], number)
            self.assertEqual(stale_body['version']['payload']['tsr-complaint'], 'Device B stale copy')
            self.assertEqual(stale_body['version']['reservation_token'], token)

            duplicate = client_b.post('/save_tsr_draft', json={
                'draft_key': 'two-device-draft', 'base_revision': 1,
                'device_updated_at': '2099-01-01T00:00:00+00:00',
                'payload': stale_body['version']['payload'],
            })
            self.assertEqual(duplicate.status_code, 409)
            self.assertTrue(duplicate.get_json()['candidate_deduplicated'])
            self.assertEqual(duplicate.get_json()['history_count'], 2)

            history = client_a.get('/get_tsr_draft_history?draft_key=two-device-draft').get_json()['versions']
            self.assertEqual(len(history), 2)
            replaced = next(item for item in history if item['source'] == 'account')
            self.assertEqual(replaced['revision'], 1)
            self.assertEqual(replaced['replaced_by_revision'], 2)
            self.assertEqual(replaced['signatures']['serviced'], 'signature-v1')
            self.assertEqual(replaced['attachment_metadata'][0]['blob_id'], 'local-attachment-1')
            self.assertEqual(clients['two'].get('/get_tsr_draft_history?draft_key=two-device-draft').get_json()['versions'], [])

    def test_archive_only_is_owner_scoped_deduplicated_and_never_replaces_current(self):
        with self.isolated_route_clients() as (clients, _user_ids):
            current = clients['one'].post('/save_tsr_draft', json={
                'draft_key': 'archive-only-draft',
                'payload': {'tsr-complaint': 'Current account copy'},
            })
            self.assertEqual(current.status_code, 200)
            current_body = current.get_json()
            candidate = {
                'draft_key': 'archive-only-draft',
                'base_revision': current_body['revision'],
                'device_updated_at': '2026-09-24T08:05:00+08:00',
                'payload': {
                    'tsr-complaint': 'Device-only alternate',
                    'tsr-number': current_body['tsr_number'],
                    'reservation_token': current_body['reservation_token'],
                    'signatures': {'serviced': 'saved-signature'},
                    'attachments': [{'name': 'machine.jpg', 'blob_id': 'local-blob-2'}],
                },
            }
            archived = clients['one'].post('/save_tsr_draft_version', json=candidate)
            self.assertEqual(archived.status_code, 200)
            self.assertTrue(archived.get_json()['archived'])
            repeated = clients['one'].post('/save_tsr_draft_version', json=candidate)
            self.assertEqual(repeated.status_code, 200)
            self.assertTrue(repeated.get_json()['deduplicated'])
            self.assertEqual(repeated.get_json()['history_count'], 1)

            current_after = clients['one'].get('/get_tsr_drafts').get_json()['drafts'][0]
            self.assertEqual(current_after['revision'], current_body['revision'])
            self.assertEqual(current_after['payload']['tsr-complaint'], 'Current account copy')
            versions = clients['one'].get('/get_tsr_draft_history?draft_key=archive-only-draft').get_json()['versions']
            self.assertEqual(len(versions), 1)
            self.assertEqual(versions[0]['source'], 'device')
            self.assertEqual(versions[0]['payload']['tsr-complaint'], 'Device-only alternate')
            self.assertEqual(clients['two'].get('/get_tsr_draft_history').get_json()['versions'], [])

    def test_history_reads_purge_after_thirty_days_and_keep_five_versions(self):
        with self.isolated_route_clients() as (clients, user_ids):
            response = clients['one'].post('/save_tsr_draft', json={
                'draft_key': 'retention-draft',
                'payload': {'tsr-complaint': 'Current stays current'},
            })
            self.assertEqual(response.status_code, 200)
            with app_module.app.app_context():
                now = app_module.get_manila_time()
                ages = [31, 6, 5, 4, 3, 2, 1]
                for index, age in enumerate(ages):
                    payload = {'tsr-complaint': f'history-{index}', '_draft_id': 'retention-draft'}
                    version, created = app_module.archive_tsr_draft_version_record(
                        user_ids['one'], 'retention-draft', payload, source='device'
                    )
                    self.assertTrue(created)
                    version.captured_at = now - timedelta(days=age)
                app_module.db.session.commit()

            result = clients['one'].get('/get_tsr_draft_history?draft_key=retention-draft')
            self.assertEqual(result.status_code, 200)
            body = result.get_json()
            self.assertEqual(len(body['versions']), 5)
            self.assertEqual(body['history_count'], 5)
            self.assertTrue(all(item['payload']['tsr-complaint'] != 'history-0' for item in body['versions']))
            self.assertTrue(all(item['payload']['tsr-complaint'] != 'history-1' for item in body['versions']))
            current = clients['one'].get('/get_tsr_drafts').get_json()['drafts'][0]
            self.assertEqual(current['payload']['tsr-complaint'], 'Current stays current')
            self.assertEqual(current['revision'], 1)

    def test_additive_schema_migrates_legacy_current_and_missing_revision_cannot_replace_it(self):
        with self.isolated_route_clients() as (clients, user_ids):
            with app_module.app.app_context():
                app_module.db.session.remove()
                engine = app_module.app.extensions['sqlalchemy']._app_engines[app_module.app][None]
                with engine.begin() as connection:
                    connection.exec_driver_sql('DROP TABLE IF EXISTS tsr_draft')
                    connection.exec_driver_sql("""
                        CREATE TABLE tsr_draft (
                            id INTEGER PRIMARY KEY,
                            user_id INTEGER NOT NULL,
                            draft_key VARCHAR(140) NOT NULL,
                            schedule_id VARCHAR(140),
                            tsr_number VARCHAR(120),
                            client_name VARCHAR(200),
                            service_date VARCHAR(40),
                            title VARCHAR(255),
                            subtitle VARCHAR(500),
                            payload_json TEXT NOT NULL,
                            attachment_count INTEGER NOT NULL DEFAULT 0,
                            device_updated_at VARCHAR(40),
                            created_at DATETIME NOT NULL,
                            updated_at DATETIME NOT NULL
                        )
                    """)
                app_module._tsr_draft_table_ready = False
                self.assertTrue(app_module.ensure_tsr_draft_schema())
                with engine.connect() as connection:
                    columns = {row[1] for row in connection.exec_driver_sql('PRAGMA table_info(tsr_draft)').fetchall()}
                self.assertTrue({'reservation_token', 'revision', 'content_hash'} <= columns)
                legacy = app_module.TsrDraft(
                    user_id=user_ids['one'],
                    draft_key='legacy-revision-draft',
                    payload_json='{"_draft_id":"legacy-revision-draft","tsr-complaint":"legacy current"}',
                    created_at=app_module.get_manila_time(),
                    updated_at=app_module.get_manila_time(),
                )
                app_module.db.session.add(legacy)
                app_module.db.session.commit()

            response = clients['one'].post('/save_tsr_draft', json={
                'draft_key': 'legacy-revision-draft',
                'device_updated_at': '2099-01-01T00:00:00+00:00',
                'payload': {'_draft_id': 'legacy-revision-draft', 'tsr-complaint': 'legacy device alternate'},
            })
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.get_json()['conflict_metadata']['reason'], 'base_revision_required')
            current = clients['one'].get('/get_tsr_drafts').get_json()['drafts'][0]
            self.assertEqual(current['payload']['tsr-complaint'], 'legacy current')
            self.assertEqual(current['revision'], 1)

    def test_owner_isolation_upsert_stale_and_delete_scope(self):
        fd, database_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        extension = None
        original_engine = None
        original_ready = None
        test_engine = None
        original_csrf = None
        try:
            with app_module.app.app_context():
                extension = app_module.app.extensions['sqlalchemy']
                engines = extension._app_engines[app_module.app]
                original_engine = engines[None]
                original_ready = app_module._tsr_draft_table_ready
                original_csrf = app_module.app.config.get('WTF_CSRF_ENABLED')
                app_module.app.config['WTF_CSRF_ENABLED'] = False
                test_engine = create_engine(f"sqlite:///{database_path.replace(os.sep, '/')}")
                engines[None] = test_engine
                app_module._tsr_draft_table_ready = False
                app_module.db.session.remove()
                app_module.db.create_all()
                app_module.ensure_tsr_draft_schema()
                user_one = app_module.User(username='draft-sync-owner-one', password='test-only', role='engineer', is_active=True)
                user_two = app_module.User(username='draft-sync-owner-two', password='test-only', role='engineer', is_active=True)
                app_module.db.session.add_all([user_one, user_two])
                app_module.db.session.commit()
                user_one_id = user_one.id
                user_two_id = user_two.id

            payload = {
                'draft_key': 'draft-owner-one',
                'device_updated_at': '2026-08-07T08:00:00+00:00',
                'schedule_id': '17',
                'payload': {'tsr-complaint': 'newer value', 'attachments': []},
            }
            client_one = app_module.app.test_client()
            client_two = app_module.app.test_client()
            with client_one.session_transaction() as session:
                session['_user_id'] = str(user_one_id)
                session['_fresh'] = True
            with client_two.session_transaction() as session:
                session['_user_id'] = str(user_two_id)
                session['_fresh'] = True

            reservation_response = client_one.post('/reserve_tsr_number', json={
                'draft_key': 'draft-owner-one',
                'service_date': '2026-08-07',
            })
            self.assertEqual(reservation_response.status_code, 200)
            reservation_payload = reservation_response.get_json()
            first_reservation_token = reservation_payload['reservation_token']
            first_tsr_number = reservation_payload['tsr_number']
            with app_module.app.app_context():
                self.assertIsNotNone(app_module.TsrNumberReservation.query.filter_by(
                    reservation_token=first_reservation_token
                ).first())

            payload['payload']['tsr-number'] = first_tsr_number
            payload['payload']['reservation_token'] = first_reservation_token
            first = client_one.post('/save_tsr_draft', json=payload)
            self.assertEqual(first.status_code, 200)
            first_payload = first.get_json()
            self.assertEqual(first_payload['reservation_token'], first_reservation_token)
            self.assertEqual(first_payload['tsr_number'], first_tsr_number)
            self.assertGreaterEqual(len(first_reservation_token), 12)
            self.assertRegex(first_tsr_number, r'^\d{8}-\d{2}-[A-Z0-9]{1,5}$')
            second = client_one.post('/save_tsr_draft', json=dict(payload, payload={'tsr-complaint': 'older value'}, device_updated_at='2026-08-07T07:00:00+00:00'))
            self.assertEqual(second.status_code, 409)
            second_payload = second.get_json()
            self.assertTrue(second_payload['stale_ignored'])
            self.assertTrue(second_payload['conflict'])
            self.assertTrue(second_payload['candidate_archived'])
            self.assertEqual(second_payload['draft']['payload']['tsr-complaint'], 'newer value')
            self.assertEqual(second_payload['draft']['reservation_token'], first_reservation_token)
            self.assertEqual(second_payload['draft']['tsr_number'], first_tsr_number)
            self.assertEqual(second_payload['draft']['revision'], 1)
            self.assertEqual(second_payload['history_count'], 1)

            self.assertEqual(client_two.get('/get_tsr_drafts').get_json()['drafts'], [])
            self.assertEqual(client_two.post('/delete_tsr_draft', json={'draft_key': 'draft-owner-one'}).status_code, 404)
            self.assertEqual(client_two.get('/get_tsr_draft_history?draft_key=draft-owner-one').get_json()['versions'], [])
            self.assertEqual(client_one.post('/delete_tsr_draft', json={'draft_key': 'draft-owner-one'}).status_code, 200)
            self.assertEqual(client_one.get('/get_tsr_drafts').get_json()['drafts'], [])
            self.assertEqual(client_one.get('/get_tsr_draft_history?draft_key=draft-owner-one').get_json()['versions'], [])
            with app_module.app.app_context():
                self.assertIsNone(app_module.TsrNumberReservation.query.filter_by(
                    reservation_token=first_reservation_token
                ).first())
        finally:
            if extension is not None and app_module is not None:
                with app_module.app.app_context():
                    app_module.db.session.remove()
                    if original_engine is not None:
                        extension._app_engines[app_module.app][None] = original_engine
                    if original_ready is not None:
                        app_module._tsr_draft_table_ready = original_ready
                    if original_csrf is not None:
                        app_module.app.config['WTF_CSRF_ENABLED'] = original_csrf
            if test_engine is not None:
                test_engine.dispose()
            if database_path and os.path.exists(database_path):
                os.unlink(database_path)

    def test_create_tsr_renders_and_inline_javascript_parses(self):
        with self.isolated_route_clients() as (clients, _user_ids):
            response = clients['one'].get('/offline-tsr')
            self.assertEqual(response.status_code, 200)
            scripts = re.findall(r'<script\b[^>]*>(.*?)</script\s*>', response.get_data(as_text=True), re.I | re.S)
            self.assertTrue(scripts, 'Create TSR should render its page scripts.')
            parsed_scripts = 0
            for source in scripts:
                if not source.strip():
                    continue
                fd, script_path = tempfile.mkstemp(suffix='.js')
                try:
                    with os.fdopen(fd, 'w', encoding='utf-8') as script_file:
                        script_file.write(source)
                    result = subprocess.run([str(NODE), '--check', script_path], cwd=ROOT, capture_output=True, text=True, check=False)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    parsed_scripts += 1
                finally:
                    if os.path.exists(script_path):
                        os.unlink(script_path)
            self.assertGreater(parsed_scripts, 0, 'At least one nonempty inline script should be checked.')


@unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
class TsrDraftAccessMatchesThePageGateTests(unittest.TestCase):
    """The page gate and the three endpoint gates must admit the same accounts.

    The original implementation gated the routes on
    `is_admin_authorized() or role == 'engineer'` while `/offline-tsr` admitted
    everyone except approver-only users, so five account shapes could open
    Create TSR and write a draft that was silently never backed up. This is the
    fifth time a page/endpoint gate mismatch has reached main, and every previous
    one was found the same way: build one account of each shape and call the
    route. See pending-work.md bug 1z.
    """

    # Each entry is the account shape from the bug's reproduction table. The
    # approver-only row is the positive control: it is the one shape that must
    # still be refused, so a gate that simply returned True everywhere fails.
    # (label, columns, may_back_up, expected endpoint status when refused)
    #
    # The refused accounts are refused by TWO different mechanisms, and the
    # status tells them apart: `can_back_up_tsr_drafts()` answers 403, while the
    # inventory-only and HR-only before_request fences redirect. Asserting the
    # exact status keeps those distinct, so a fence quietly disappearing cannot
    # be absorbed as "still refused somehow".
    ACCOUNT_SHAPES = (
        ('engineer', dict(role='engineer'), True, None),
        ('plain-staff', dict(role='staff'), True, None),
        ('scheduler', dict(role='staff', schedule_admin_access=True), True, None),
        ('personnel-admin', dict(role='staff', personnel_admin_access=True), True, None),
        ('reports-admin', dict(role='staff', reports_admin_access=True), True, None),
        ('stock-inventory', dict(role='staff', can_manage_stock_inventory=True), True, None),
        # The one shape this gate itself must refuse.
        ('approver-only', dict(role='approver', can_approve_requests=True), False, 403),
        # Fenced off from /offline-tsr entirely by their own before_request
        # guards, not by this gate. Listed so the boundary is pinned: if either
        # fence is relaxed, this test forces a deliberate decision about draft
        # backup rather than silently recreating bug 1z for a new account shape.
        ('stock-inventory-only', dict(role='staff', can_manage_stock_inventory=True, stock_inventory_only=True), False, 302),
        ('hr-schedule-only', dict(role='staff', hr_schedule_view=True), False, 302),
    )

    def test_every_account_that_can_open_create_tsr_can_back_a_draft_up(self):
        fd, database_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        extension = None
        original_engine = None
        original_ready = None
        test_engine = None
        original_csrf = None
        try:
            with app_module.app.app_context():
                extension = app_module.app.extensions['sqlalchemy']
                engines = extension._app_engines[app_module.app]
                original_engine = engines[None]
                original_ready = app_module._tsr_draft_table_ready
                original_csrf = app_module.app.config.get('WTF_CSRF_ENABLED')
                app_module.app.config['WTF_CSRF_ENABLED'] = False
                test_engine = create_engine(f"sqlite:///{database_path.replace(os.sep, '/')}")
                engines[None] = test_engine
                app_module._tsr_draft_table_ready = False
                app_module.db.session.remove()
                app_module.db.create_all()
                app_module.ensure_tsr_draft_schema()

                user_ids = {}
                for label, columns, _, _refused_status in self.ACCOUNT_SHAPES:
                    user = app_module.User(
                        username=f'draft-gate-{label}',
                        password='test-only',
                        is_active=True,
                        **columns,
                    )
                    app_module.db.session.add(user)
                    app_module.db.session.commit()
                    user_ids[label] = user.id

            for label, _, may_back_up, refused_status in self.ACCOUNT_SHAPES:
                with self.subTest(account=label):
                    client = app_module.app.test_client()
                    with client.session_transaction() as session:
                        session['_user_id'] = str(user_ids[label])
                        session['_fresh'] = True

                    page = client.get('/offline-tsr')
                    save = client.post('/save_tsr_draft', json={
                        'draft_key': f'draft-gate-{label}',
                        'device_updated_at': '2026-08-08T08:00:00+00:00',
                        'payload': {'tsr-complaint': 'gate check', 'attachments': []},
                    })
                    fetch = client.get('/get_tsr_drafts')

                    if may_back_up:
                        # The page opening while the endpoints refuse IS the bug.
                        self.assertEqual(page.status_code, 200, f'{label} cannot open Create TSR')
                        self.assertEqual(save.status_code, 200, f'{label} can write a draft that is never backed up')
                        self.assertEqual(fetch.status_code, 200, f'{label} cannot recover a backed-up draft')
                        keys = [row['draft_key'] for row in fetch.get_json()['drafts']]
                        self.assertIn(f'draft-gate-{label}', keys, f'{label} draft did not reach the server')
                    else:
                        self.assertEqual(page.status_code, 302, f'{label} should be redirected away from Create TSR')
                        self.assertEqual(save.status_code, refused_status)
                        self.assertEqual(fetch.status_code, refused_status)
        finally:
            if extension is not None and app_module is not None:
                with app_module.app.app_context():
                    app_module.db.session.remove()
                    if original_engine is not None:
                        extension._app_engines[app_module.app][None] = original_engine
                    if original_ready is not None:
                        app_module._tsr_draft_table_ready = original_ready
                    if original_csrf is not None:
                        app_module.app.config['WTF_CSRF_ENABLED'] = original_csrf
            if test_engine is not None:
                test_engine.dispose()
            if database_path and os.path.exists(database_path):
                os.unlink(database_path)

    def test_a_permanent_refusal_is_not_described_as_temporary(self):
        """The 403 message must not tell the user to wait for a retry.

        This is the half of bug 1z that kept it unreported: the user was told
        the backup was "temporarily unavailable and will retry", so nobody
        raised it.
        """
        source = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')
        self.assertIn('function standaloneTSRServerBackupFailureText(', source)
        self.assertIn('standaloneTSRServerBackupFailureText(result.server_sync_error)', source)
        # The status is what separates the three outcomes; without branching on
        # it the function is just the old single message with extra steps.
        self.assertIn("error?.httpStatus === 403", source)
        self.assertIn("error?.httpStatus === 401", source)
        # The temporary wording must survive for the case where it is true.
        self.assertIn('temporarily unavailable and will retry', source)


if __name__ == '__main__':
    unittest.main()
