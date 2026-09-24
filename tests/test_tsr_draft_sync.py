import json
import os
import pathlib
import subprocess
import tempfile
import unittest

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
        self.assertIn("db.UniqueConstraint('user_id', 'draft_key'", self.app_source)
        for route in (
            "@app.route('/save_tsr_draft', methods=['POST'])",
            "@app.route('/get_tsr_drafts', methods=['GET'])",
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

    def test_stale_device_timestamp_is_ignored(self):
        if app_module is None:
            self.skipTest(f'app dependencies unavailable: {APP_IMPORT_ERROR}')
        newer = app_module.parse_tsr_draft_device_timestamp('2026-08-07T08:00:00+00:00')
        older = app_module.parse_tsr_draft_device_timestamp('2026-08-07T07:59:59+00:00')
        self.assertIsNotNone(newer)
        self.assertLess(older, newer)
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
        self.assertIn('stale_ignored', sync)
        self.assertIn('result?.stale_ignored', queued)
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
        self.assertIn('draft_source_conflict', local_save)

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
const standaloneTSRDraftConflictIds = new Set();
const standaloneTSRDraftRecoveryVariants = new Map();
const standaloneTSRDraftRecoveryChoices = new Map();
const OFFLINE_TSR_DB_STORES={drafts:'drafts'};
const OFFLINE_TSR_ACTIVE_DRAFT_ID='active';
let standaloneTSRServerDraftsHydrated=false;
let writes=0, uploads=0;
const local={id:'draft-divergent',source:'offline_tsr_page',updated_at:'2026-09-24T08:00:00Z',
  schedule_id:'17',tsr_number:'20260924-01-ABC',reservation_token:'reservation-one',
  payload:{_draft_id:'draft-divergent','tsr-number':'20260924-01-ABC',reservation_token:'reservation-one',
    'tsr-complaint':'device work',signatures:{serviced:'device-signature',acknowledged:''},
    attachments:[{name:'device.pdf',blob_id:'device-file'}]}};
const remote={draft_key:'draft-divergent',updated_at:'2026-09-24T08:10:00Z',device_updated_at:'2026-09-24T08:10:00Z',
  schedule_id:'17',tsr_number:'20260924-01-ABC',reservation_token:'reservation-one',
  payload:{_draft_id:'draft-divergent','tsr-number':'20260924-01-ABC',reservation_token:'reservation-one',
    'tsr-complaint':'account work',signatures:{serviced:'account-signature',acknowledged:'client-signature'},
    attachments:[{name:'account.pdf',blob_id:'account-file'}]}};
globalThis.fetch=async()=>({ok:true,json:async()=>({status:'success',drafts:[remote]})});
function flushStandaloneTSRServerDraftDeletes(){return Promise.resolve();}
function waitForStandaloneTSRLocalSaves(){return Promise.resolve();}
function readStandaloneTSRServerDraftDeleteQueue(){return [];}
function loadStandaloneTSRDraftRecordsFromIndexedDB(){return Promise.resolve([local]);}
function loadStandaloneTSRDraftFromLocalStorageFallback(){return null;}
function isStandaloneTSRDraftMeaningful(){return true;}
function enqueueStandaloneTSRServerDraftSync(){uploads++;return Promise.resolve({status:'success'});}
function offlineTSRDBPut(){writes++;return Promise.resolve();}
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

    def test_stale_backup_result_uses_unresolved_status_until_real_success(self):
        enqueue = self.template_source.split(
            'function enqueueStandaloneTSRServerDraftSync', 1
        )[1].split('function readStandaloneTSRServerDraftDeleteQueue', 1)[0]
        script = r"""
Object.defineProperty(globalThis,'navigator',{value:{onLine:true},configurable:true});
let standaloneTSRServerDraftSyncTimer=null;
let standaloneTSRServerDraftSyncChain=Promise.resolve();
const standaloneTSRDraftConflictIds=new Set();
const standaloneTSRDraftRecoveryChoices=new Map();
const standaloneTSRAccountDraftCandidates=new Map();
const standaloneTSRDraftRecoveryVariants=new Map();
const standaloneTSRSaveStatusGeneration=1;
const standaloneTSRActiveContextVersion=1;
let nextResult={status:'success',stale_ignored:true};
const states=[];
function standaloneTSRSaveStatusContextIsActive(){return true;}
function setStandaloneTSRSaveStatus(state){states.push(state);}
function syncStandaloneTSRDraftToServer(){return Promise.resolve(nextResult);}
""" + "function enqueueStandaloneTSRServerDraftSync" + enqueue + r"""
(async()=>{
  await enqueueStandaloneTSRServerDraftSync({id:'draft-status',payload:{}},{immediate:true,statusContext:{}});
  nextResult={status:'success'};
  await enqueueStandaloneTSRServerDraftSync({id:'draft-status',payload:{}},{immediate:true,statusContext:{}});
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
        assert_cache_version_at_least(self, 182, self.app_source)
        self.assertIn("'/offline-tsr',", self.app_source)

    def test_draft_recovery_release_entry_is_present(self):
        release = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))['releases'][0]
        self.assertEqual(release['release_key'], '2026-09-24-create-tsr-draft-recovery')
        self.assertEqual(release['release_date'], '2026-09-24')
        self.assertIn('Choose which copy to continue', release['items'][0]['description'])


@unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
class TsrDraftRouteTests(unittest.TestCase):
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
            self.assertEqual(second.status_code, 200)
            second_payload = second.get_json()
            self.assertTrue(second_payload['stale_ignored'])
            self.assertEqual(second_payload['draft']['payload']['tsr-complaint'], 'newer value')
            self.assertEqual(second_payload['draft']['reservation_token'], first_reservation_token)
            self.assertEqual(second_payload['draft']['tsr_number'], first_tsr_number)

            self.assertEqual(client_two.get('/get_tsr_drafts').get_json()['drafts'], [])
            self.assertEqual(client_two.post('/delete_tsr_draft', json={'draft_key': 'draft-owner-one'}).status_code, 404)
            self.assertEqual(client_one.post('/delete_tsr_draft', json={'draft_key': 'draft-owner-one'}).status_code, 200)
            self.assertEqual(client_one.get('/get_tsr_drafts').get_json()['drafts'], [])
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
