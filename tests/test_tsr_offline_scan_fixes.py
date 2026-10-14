"""Create TSR offline scan fixes (plans.md, 2026-10-14): batch 1 number safety, batch 2 honest messages.

Each test runs the real template functions in Node with stubbed browser/server calls.
Set TSR_SCAN_TEMPLATE_PATH to run them against another copy of offline_tsr.html.
"""
import json
import os
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = pathlib.Path(r"C:\Users\Jonamar\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe")


def _template():
    path = os.environ.get('TSR_SCAN_TEMPLATE_PATH') or (ROOT / 'templates' / 'offline_tsr.html')
    return pathlib.Path(path).read_text(encoding='utf-8').replace('\r\n', '\n')


def _function(source, name):
    """Source of a top-level function, from its declaration to the closing brace at column 0."""
    for prefix in (f'\nasync function {name}(', f'\nfunction {name}('):
        start = source.find(prefix)
        if start >= 0:
            end = source.index('\n}\n', start)
            return source[start + 1:end + 2]
    raise AssertionError(f'{name} not found in the template')


class TsrOfflineScanFixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not NODE.exists():
            raise unittest.SkipTest('Node runtime not available')
        cls.source = _template()

    def _run(self, script):
        result = subprocess.run([str(NODE), '-e', script], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout.strip().splitlines()[-1])

    # Batch 1 -------------------------------------------------------------

    def test_queued_final_save_does_not_release_its_reserved_number(self):
        script = _function(self.source, 'finishStandaloneTSRFinalSave') + r"""
const navigator = { onLine:false };
let standaloneTSRReservationToken = 'tsr-res-queued';
const tokensAtClear = [];
async function clearStandaloneTSRDraftLocally(){ tokensAtClear.push(standaloneTSRReservationToken); }
async function queueStandaloneTSROffline(){}
async function submitStandaloneTSROnline(){ const e = new Error('weak signal'); e.queued = true; throw e; }
function initializeBlankStandaloneTSR(){}
function resetAllInlineTSRKnowledgeSuggestions(){}
function readOfflineTSRQueue(){ return [{}]; }
function showTSRStatus(){}
function renderOfflineTSRQueuePanel(){}
async function renderStandaloneTSRDraftPanel(){}
(async () => {
  const state = { payload:{ reservation_token:'tsr-res-queued' }, pdfPackage:{ blob:{} } };
  await finishStandaloneTSRFinalSave(state);              // offline branch
  navigator.onLine = true;
  standaloneTSRReservationToken = 'tsr-res-queued';
  await finishStandaloneTSRFinalSave(state);              // err.queued branch
  console.log(JSON.stringify({ tokensAtClear }));
})().catch(e => { console.error(e); process.exit(1); });
"""
        output = self._run(script)
        self.assertEqual(output['tokensAtClear'], ['', ''],
                         'Clearing the draft after queuing must not release the queue item\'s TSR number.')

    def test_release_flush_skips_tokens_still_held_by_the_queue(self):
        script = _function(self.source, 'flushTSRReservationReleaseQueue') + r"""
const navigator = { onLine:true };
function normalizeTSRReservationToken(v){ return String(v || '').trim(); }
let stored = [{ reservation_token:'tok-queued', draft_key:'d1' }, { reservation_token:'tok-free', draft_key:'d2' }];
function readTSRReservationReleaseQueue(){ return stored.slice(); }
function writeTSRReservationReleaseQueue(v){ stored = v; }
async function loadOfflineTSRQueueStore(){ return [{ id:'q1', payload:{ tsr_reservation_token:'tok-queued' } }]; }
const released = [];
async function releaseTSRReservationRemote(item){ released.push(item.reservation_token); return { status:'success' }; }
(async () => {
  await flushTSRReservationReleaseQueue();
  console.log(JSON.stringify({ released, stored }));
})().catch(e => { console.error(e); process.exit(1); });
"""
        output = self._run(script)
        self.assertEqual(output['released'], ['tok-free'])
        self.assertEqual(output['stored'], [], 'The skipped entry is dropped from the release list.')

    def test_concurrent_sync_triggers_upload_each_item_once(self):
        block = self.source.split('async function syncOfflineTSRQueue(', 1)[1].split('\nasync function retryOfflineTSRQueueItem', 1)[0]
        helper = (_function(self.source, 'isOfflineTSRQueueItemForCurrentAccount')
                  if 'function isOfflineTSRQueueItemForCurrentAccount(' in self.source else '')
        script = helper + '\nasync function syncOfflineTSRQueue(' + block + r"""
const navigator = { onLine:true };
const window = {};
const STANDALONE_TSR_ACCOUNT_SCOPE = '16';
let offlineTSRSyncRunning = false;
const tick = () => new Promise(resolve => setTimeout(resolve, 5));
let queue = [{ id:'q1', status:'pending' }];
let uploads = 0;
const bannerFlags = [];
async function loadOfflineTSRQueueStore(){ await tick(); return queue.slice(); }
async function refreshOfflineTSRQueueStore(){}
async function saveOfflineTSRSyncMetadata(){ await tick(); }
async function checkOfflineTSRSyncHealth(){ await tick(); }
async function uploadQueuedOfflineTSR(){ uploads += 1; await tick(); return { status:'success' }; }
async function removeSyncedOfflineTSRQueueItem(current, item){ queue = queue.filter(e => e.id !== item.id); return queue; }
async function markFailedOfflineTSRQueueItem(q){ return q; }
function isOfflineTSRDuplicateOrConflictSuccess(){ return false; }
function isRealScheduleId(){ return true; }
function clearOfflineTSRSyncRetryTimer(){}
function scheduleOfflineTSRSyncRetry(){}
function renderOfflineTSRQueuePanel(){}
function updateOfflineTSRStatusIntelligence(){ bannerFlags.push(offlineTSRSyncRunning); }
function showTSRStatus(){}
(async () => {
  await Promise.all([syncOfflineTSRQueue({ silent:true }), syncOfflineTSRQueue({ silent:true })]);
  console.log(JSON.stringify({ uploads, running:offlineTSRSyncRunning, lastBanner:bannerFlags[bannerFlags.length - 1] }));
})().catch(e => { console.error(e); process.exit(1); });
"""
        output = self._run(script)
        self.assertEqual(output['uploads'], 1, 'Two sync triggers in the same tick uploaded the TSR twice.')
        self.assertFalse(output['running'])
        self.assertFalse(output['lastBanner'], 'The banner must be refreshed after the sync flag resets.')

    # Batch 2 -------------------------------------------------------------

    def test_save_draft_message_matches_the_backup_result(self):
        script = _function(self.source, 'saveStandaloneTSRLocalDraft') + r"""
const document = { getElementById(){ return null; } };
let nextResult = null;
const shown = [];
function requireStandaloneScheduleForTSRAction(){ return true; }
function collectTSRData(){ return {}; }
function resolveStandaloneTSRDraftId(){ return 'd1'; }
async function clearStandaloneTSRDraftDeletionForExplicitAction(){ return true; }
async function saveStandaloneTSRDraftLocally(){ return nextResult; }
async function renderStandaloneTSRDraftPanel(){}
function standaloneTSRServerBackupFailureText(){ return 'backup failed'; }
function isOfflineTSRStorageHealthAdmin(){ return false; }
function showTSRStatus(message, tone){ shown.push([message, tone]); }
const cases = {
  conflict:{ server_sync_result:{ status:'conflict' } },
  stale:{ server_sync_result:{ status:'success', stale_ignored:true } },
  sourceConflict:{ server_sync_result:{ pending:true, skipped:true, reason:'draft_source_conflict' } },
  pending:{ server_sync_result:{ pending:true } },
  success:{ server_sync_result:{ status:'success' } },
  unknown:{}
};
(async () => {
  const out = {};
  for(const [name, result] of Object.entries(cases)){
    nextResult = result; shown.length = 0;
    await saveStandaloneTSRLocalDraft();
    out[name] = shown[shown.length - 1];
  }
  console.log(JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });
"""
        output = self._run(script)
        for name in ('conflict', 'stale', 'sourceConflict'):
            self.assertIn('not backed up', output[name][0], name)
            self.assertEqual(output[name][1], 'warning', name)
        self.assertIn('when you are online', output['pending'][0])
        self.assertEqual(output['success'], ['Draft saved on this device and backed up to your account.', 'success'])
        self.assertEqual(output['unknown'], ['Draft saved on this device.', 'info'])

    def test_linked_schedule_question_is_asked_once_when_number_reservation_fails(self):
        script = _function(self.source, 'prepareTSRForFinalSave') + '\n' + _function(self.source, 'beginStandaloneTSRFinalPreview') + r"""
const navigator = { onLine:true };
let finalTSRPreviewBusy = false, finalTSRConfirmBusy = false, onlineTSRRevisionContext = null;
let standaloneTSRReservationToken = '';
let asked = 0, previewPayload = null;
async function chooseTSRCompletionScope(){ asked += 1; return 'current_day'; }
async function reserveTSRNumberForDraft(){ const e = new Error('Failed to fetch'); throw e; }
function isRetriableTSRSyncError(){ return true; }
async function validateTSRFinalSaveRequirements(){ return true; }
async function confirmTSRRecommendedDetailsBeforeSave(){ return true; }
function setOfflineTSRPDFBusy(){}
function showTSRStatus(){}
function showTSRFinalSaveRecovery(m){ console.error('recovery: ' + m); }
async function saveStandaloneTSRDraftLocally(){ return {}; }
function getSelectedStandaloneSchedule(){ return { id:7, linked:true }; }
function getStandaloneScheduleRealId(s){ return s?.id || ''; }
function ensureTSRSubmissionToken(v){ return v || 'sub-1'; }
function ensureTSRReservationToken(v){ return v || 'tok-1'; }
function normalizeTSRReservationToken(v){ return String(v || '').trim(); }
async function buildStandaloneTSRPDFBlobForUpload(){ return { blob:{} }; }
async function showFinalTSRPreview(payload){ previewPayload = payload; }
(async () => {
  await beginStandaloneTSRFinalPreview({ 'tsr-number':'20261014-01-JMM' });
  console.log(JSON.stringify({ asked, scope:previewPayload?.completion_scope }));
})().catch(e => { console.error(e); process.exit(1); });
"""
        output = self._run(script)
        self.assertEqual(output['asked'], 1, '"Complete Linked Schedules?" was asked twice.')
        self.assertEqual(output['scope'], 'current_day')

    def test_service_worker_cached_schedule_list_is_labelled_as_saved_copy(self):
        names = ['cacheStandaloneScheduleOptions', 'readCachedStandaloneScheduleOptions', 'refreshStandaloneScheduleOptions']
        if 'function readCachedStandaloneScheduleGeneratedAt(' in self.source:
            names.append('readCachedStandaloneScheduleGeneratedAt')
        if 'function getStandaloneScheduleCacheKey(' in self.source:
            names.append('getStandaloneScheduleCacheKey')
        script = '\n'.join(_function(self.source, name) for name in names) + r"""
const navigator = { onLine:true };
const STANDALONE_TSR_SCHEDULES_KEY = 'schedules';
const STANDALONE_TSR_ACCOUNT_SCOPE = '16';
const store = {};
const localStorage = { getItem:k => (k in store ? store[k] : null), setItem:(k, v) => { store[k] = String(v); }, removeItem:k => { delete store[k]; } };
let standaloneScheduleOptionsAreLive = false, selectedStandaloneScheduleId = '', selectedStandaloneScheduleSnapshot = null;
let standaloneScheduleOptions = [];
let generatedAt = 'G1';
async function fetch(){ return { ok:true, json:async () => ({ generated_at:generatedAt, schedules:[{ id:1 }] }) }; }
let renderedSource = '';
function renderStandaloneScheduleOptions(s, source){ renderedSource = source; }
function cacheTSRFilenameTemplate(){}
function readTimelineSnapshotSchedules(){ return []; }
async function readPendingScheduleOptions(){ return []; }
async function enrichCachedStandaloneScheduleCalibration(s){ return s; }
function renderTSRClientContactSuggestions(){}
function clearStandaloneCalibrationHistory(){}
function updateCreateTSRScheduleGate(){}
function hasStandaloneScheduleSelection(){ return false; }
function showTSRStatus(){}
(async () => {
  await refreshStandaloneScheduleOptions(false);
  const first = { source:renderedSource, live:standaloneScheduleOptionsAreLive };
  await refreshStandaloneScheduleOptions(false);          // same generated_at = the service worker's cached copy
  const replay = { source:renderedSource, live:standaloneScheduleOptionsAreLive };
  generatedAt = 'G2';
  await refreshStandaloneScheduleOptions(false);
  const fresh = { source:renderedSource, live:standaloneScheduleOptionsAreLive };
  console.log(JSON.stringify({ first, replay, fresh }));
})().catch(e => { console.error(e); process.exit(1); });
"""
        output = self._run(script)
        self.assertEqual(output['first'], {'source': 'live system data', 'live': True})
        self.assertEqual(output['replay'], {'source': 'saved offline cache', 'live': False})
        self.assertEqual(output['fresh'], {'source': 'live system data', 'live': True})

    def test_continue_draft_tones_are_info_on_success_and_warning_without_schedule(self):
        open_draft = _function(self.source, 'openStandaloneTSRDraft')
        self.assertIn("showTSRStatus(draftMessage, hasStandaloneScheduleSelection() ? 'info' : 'warning');", open_draft)

    # Batch 3 -------------------------------------------------------------

    def test_continue_draft_shows_the_selected_schedule_card(self):
        apply_draft = _function(self.source, 'applyStandaloneTSRDraftData')
        self.assertIn('renderSelectedStandaloneScheduleCard(matchedOption || null);', apply_draft)
        self.assertIn("scheduleSelect.value = selectedStandaloneScheduleId || '';", apply_draft)
        script = _function(self.source, 'renderSelectedStandaloneScheduleCard') + r"""
const classes = new Set(['d-none']);
const card = { innerHTML:'', classList:{ add:c => classes.add(c), remove:c => classes.delete(c) } };
const document = { getElementById:id => id === 'tsr-selected-schedule-card' ? card : null };
function escapeHTML(v){ return String(v ?? ''); }
function stripScheduleBillingTags(v){ return v; }
function getScheduleProductLabel(s){ return s.product_name; }
function isOnlineTSRRevisionMode(){ return false; }
function isFrancisTSRWithoutEquipmentSchedule(){ return false; }
renderSelectedStandaloneScheduleCard({ client_name:'Cebu Doctors', date_label:'Oct 14', time_start:'08:00', task:'PM', product_name:'MobileDaRt' });
const shown = { hidden:classes.has('d-none'), html:card.innerHTML };
renderSelectedStandaloneScheduleCard(null);
console.log(JSON.stringify({ shown, cleared:{ hidden:classes.has('d-none'), html:card.innerHTML } }));
"""
        output = self._run(script)
        self.assertFalse(output['shown']['hidden'])
        for text in ('Cebu Doctors', 'Oct 14', '08:00', 'PM', 'MobileDaRt'):
            self.assertIn(text, output['shown']['html'])
        self.assertEqual(output['cleared'], {'hidden': True, 'html': ''})

    def test_submitted_and_approved_calibration_notifications_open_my_calibrations(self):
        app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        for title in ("'Calibration Report & Certificate submitted'", "'Calibration Report & Certificate approved'"):
            line = next(l for l in app_source.splitlines() if title in l and 'create_system_notification' in l)
            self.assertIn("target_url=url_for('my_calibrations_page')", line, title)

    def test_unused_create_tsr_functions_are_removed(self):
        for name in ('loadStandaloneTSRDraft', 'resetStandaloneTSRForm', 'copyStandaloneTSRText'):
            self.assertNotIn(f'function {name}(', self.source, name)

    # Batch 4 -------------------------------------------------------------

    def test_schedule_cache_is_scoped_to_the_signed_in_account(self):
        names = ['cacheStandaloneScheduleOptions', 'readCachedStandaloneScheduleOptions']
        if 'function getStandaloneScheduleCacheKey(' in self.source:
            names.append('getStandaloneScheduleCacheKey')
        script = '\n'.join(_function(self.source, name) for name in names) + r"""
const STANDALONE_TSR_SCHEDULES_KEY = 'schedules';
let STANDALONE_TSR_ACCOUNT_SCOPE = '16';
const store = { schedules:JSON.stringify({ schedules:[{ id:'legacy' }] }) };
const localStorage = { getItem:k => (k in store ? store[k] : null), setItem:(k, v) => { store[k] = String(v); }, removeItem:k => { delete store[k]; } };
cacheStandaloneScheduleOptions([{ id:'mine' }], 'G1');
const own = readCachedStandaloneScheduleOptions();
STANDALONE_TSR_ACCOUNT_SCOPE = '28';
const other = readCachedStandaloneScheduleOptions();
console.log(JSON.stringify({ own, other, keys:Object.keys(store) }));
"""
        output = self._run(script)
        self.assertEqual(output['own'], [{'id': 'mine'}])
        self.assertEqual(output['other'], [], "Another account must not see this account's cached schedules.")
        self.assertEqual(output['keys'], ['schedules:16'], 'The old unscoped cache is removed on the first scoped write.')

    def test_offline_queue_syncs_only_this_accounts_and_legacy_items(self):
        self.assertIn('account_id: STANDALONE_TSR_ACCOUNT_SCOPE,', _function(self.source, 'queueStandaloneTSROffline'))
        block = self.source.split('async function syncOfflineTSRQueue(', 1)[1].split('\nasync function retryOfflineTSRQueueItem', 1)[0]
        helper = (_function(self.source, 'isOfflineTSRQueueItemForCurrentAccount')
                  if 'function isOfflineTSRQueueItemForCurrentAccount(' in self.source else '')
        script = helper + '\nasync function syncOfflineTSRQueue(' + block + r"""
const navigator = { onLine:true };
const window = {};
const STANDALONE_TSR_ACCOUNT_SCOPE = '16';
let offlineTSRSyncRunning = false;
let queue = [
  { id:'mine', status:'pending', account_id:'16' },
  { id:'legacy', status:'pending' },
  { id:'theirs', status:'pending', account_id:'28' }
];
const uploaded = [];
async function loadOfflineTSRQueueStore(){ return queue.slice(); }
async function refreshOfflineTSRQueueStore(){}
async function saveOfflineTSRSyncMetadata(){}
async function checkOfflineTSRSyncHealth(){}
async function uploadQueuedOfflineTSR(item){ uploaded.push(item.id); return { status:'success' }; }
async function removeSyncedOfflineTSRQueueItem(current, item){ queue = queue.filter(e => e.id !== item.id); return queue; }
async function markFailedOfflineTSRQueueItem(q){ return q; }
function isOfflineTSRDuplicateOrConflictSuccess(){ return false; }
function isRealScheduleId(){ return true; }
function clearOfflineTSRSyncRetryTimer(){}
function scheduleOfflineTSRSyncRetry(){}
function renderOfflineTSRQueuePanel(){}
function updateOfflineTSRStatusIntelligence(){}
function showTSRStatus(){}
(async () => {
  await syncOfflineTSRQueue({ silent:true });
  console.log(JSON.stringify({ uploaded, left:queue.map(e => e.id) }));
})().catch(e => { console.error(e); process.exit(1); });
"""
        output = self._run(script)
        self.assertEqual(output['uploaded'], ['mine', 'legacy'])
        self.assertEqual(output['left'], ['theirs'], "Another account's TSR is kept, never deleted.")

    def test_queue_panel_counts_only_this_account_and_notes_others(self):
        script = (_function(self.source, 'isOfflineTSRQueueItemForCurrentAccount') + '\n'
                  + _function(self.source, 'renderOfflineTSRQueuePanel')) + r"""
const STANDALONE_TSR_ACCOUNT_SCOPE = '16';
let offlineTSRSyncRunning = false, offlineTSRQueueLastLoadedAt = '';
const OFFLINE_TSR_QUEUE_META_KEY = 'meta';
const localStorage = { getItem:() => null };
const el = () => ({ textContent:'', innerHTML:'', classList:{ add(){}, remove(){}, toggle(){} } });
const nodes = { 'offline-tsr-queue-panel':el(), 'offline-tsr-queue-summary':el(), 'offline-tsr-queue-list':el() };
const document = { getElementById:id => nodes[id] || null };
let queue = [{ id:'theirs', status:'pending', account_id:'28' }];
function readOfflineTSRQueue(){ return queue; }
function updateOfflineTSRStatusIntelligence(){}
function getOfflineTSRSyncMetadata(){ return Promise.resolve(null); }
function formatOfflineQueueTime(v){ return String(v || ''); }
function normalizeQueuedAttachments(v){ return v || []; }
function isQueuedTSRSignatureAttachment(){ return false; }
function formatTSRFileSize(){ return ''; }
function escapeHTML(v){ return String(v ?? ''); }
renderOfflineTSRQueuePanel();
const onlyOther = nodes['offline-tsr-queue-summary'].textContent;
const onlyOtherList = nodes['offline-tsr-queue-list'].innerHTML;
queue = queue.concat([{ id:'mine', status:'pending', account_id:'16', client_name:'My Client' }]);
renderOfflineTSRQueuePanel();
console.log(JSON.stringify({ onlyOther, onlyOtherList, mixed:nodes['offline-tsr-queue-summary'].textContent,
  mixedList:nodes['offline-tsr-queue-list'].innerHTML }));
"""
        output = self._run(script)
        self.assertEqual(output['onlyOther'], 'No pending TSRs. 1 TSR from another account on this device.')
        self.assertEqual(output['onlyOtherList'], '')
        self.assertTrue(output['mixed'].startswith('1 pending TSR waiting for sync.'), output['mixed'])
        self.assertTrue(output['mixed'].endswith(' 1 TSR from another account on this device.'), output['mixed'])
        self.assertIn('My Client', output['mixedList'])
        self.assertNotIn('theirs', output['mixedList'])


if __name__ == '__main__':
    unittest.main()
