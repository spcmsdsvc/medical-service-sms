"""Regression contracts for independent TSR people and offline draft saves."""

import json
import os
import pathlib
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4


ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = pathlib.Path(r'C:\Users\Jonamar\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe')
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f'medical_service_tsr_followup_{os.getpid()}_{uuid4().hex}.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

try:
    import app as app_module
except Exception as exc:  # pragma: no cover - source contracts remain useful without imports
    app_module = None
    APP_IMPORT_ERROR = exc
else:
    APP_IMPORT_ERROR = None


class TsrOfflineFollowupSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.tsr_source = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')
        cls.timeline_source = (ROOT / 'templates' / 'timeline.html').read_text(encoding='utf-8')
        cls.release_source = (ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8')

    def _helper_body(self, signature, next_signature):
        return self.app_source.split(signature, 1)[1].split(next_signature, 1)[0]

    def _save_segment(self):
        marker = 'function captureStandaloneTSRLocalSaveContext('
        if marker not in self.tsr_source:
            self.skipTest('ordered local-save helpers are not present in the unchanged source')
        idb_start = self.tsr_source.index('async function saveStandaloneTSRDraftToIndexedDB(')
        idb_end = self.tsr_source.index('\nasync function loadStandaloneTSRDraftFromIndexedDB', idb_start)
        start = self.tsr_source.index(marker)
        end = self.tsr_source.index('\nasync function clearStandaloneTSRDraftLocally', start)
        return self.tsr_source[idb_start:idb_end] + '\n' + self.tsr_source[start:end]

    def _run_node_json(self, script):
        result = subprocess.run(
            [str(NODE), '-e', script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout.strip())

    def _node_save_harness(self, write_body, call_body):
        segment = self._save_segment()
        script = f"""
let standaloneCurrentDraftId = 'draft-1';
let standaloneTSRReservationToken = '';
let standaloneTSRActiveContextVersion = 1;
let standaloneTSRSaveStatusGeneration = 0;
let offlineTSRAttachments = [];
let standaloneTSRLocalSaveChain = Promise.resolve();
const OFFLINE_TSR_DB_STORES = {{ drafts: 'drafts' }};
const STANDALONE_TSR_ACCOUNT_SCOPE = 'test-account';
const STANDALONE_TSR_ACTIVE_DRAFT_ID = 'active';
const navigator = {{ onLine: false }};
const localStorage = {{
  value: null,
  setItem(key, value) {{ this.value = JSON.parse(value); }},
  removeItem() {{ this.value = null; }},
  getItem() {{ return this.value ? JSON.stringify(this.value) : null; }}
}};
function resolveStandaloneTSRDraftId(data) {{ return String(data?._draft_id || 'draft-1'); }}
function normalizeTSRReservationToken(value) {{ return String(value || '').replace(/[^A-Za-z0-9_-]+/g, '').slice(0, 120); }}
function getStandaloneTSRDraftTitle() {{ return 'TSR draft'; }}
function getStandaloneTSRDraftSubtitle() {{ return 'TSR'; }}
function advanceStandaloneTSRActiveContext() {{ standaloneTSRActiveContextVersion += 1; }}
function normalizeQueuedAttachments(value) {{ return Array.isArray(value) ? value : []; }}
function setStandaloneTSRSaveStatus() {{ return true; }}
function isStandaloneTSRDraftMeaningful() {{ return true; }}
function isQueuedTSRSignatureAttachment() {{ return false; }}
function projectOfflineTSRPayloadForLocalStorage(value) {{ return Object.assign({{}}, value || {{}}); }}
function warnOfflineTSRStoragePressure() {{ return Promise.resolve({{ available:true }}); }}
function offlineTSRDBGet() {{ return Promise.resolve(null); }}
let stored = null;
let writes = [];
{write_body}
function saveStandaloneTSRDraftToLocalStorageFallback(data) {{ localStorage.value = JSON.parse(JSON.stringify(data)); return true; }}
function enqueueStandaloneTSRServerDraftSync() {{ return {{ skipped:true, reason:'disabled' }}; }}
{segment}
(async()=>{{
  {call_body}
}})().catch(error => {{ console.error(error); process.exit(1); }});
"""
        return self._run_node_json(script)

    @unittest.skipUnless(NODE.exists(), f'Node runtime unavailable at {NODE}')
    def test_overlapping_local_saves_keep_latest_signed_snapshot(self):
        write_body = """
const delays = [40, 0];
function buildOfflineTSRDraftRecord(data) {
  return Promise.resolve({ id:data._draft_id, payload:Object.assign({}, data) });
}
function offlineTSRDBPut(store, value) {
  const index = writes.length;
  writes.push({ id:value.id, acknowledged:value.payload.signatures.acknowledged });
  return new Promise(resolve => setTimeout(() => { stored = JSON.parse(JSON.stringify(value)); resolve(value.id); }, delays[index] || 0));
}
"""
        call_body = """
const first = saveStandaloneTSRDraftLocally({ _draft_id:'draft-1', signatures:{ serviced:'engineer', acknowledged:'' }, attachments:[] }, { serverSync:'none' });
const second = saveStandaloneTSRDraftLocally({ _draft_id:'draft-1', signatures:{ serviced:'engineer', acknowledged:'client-signature' }, attachments:[] }, { serverSync:'none' });
await Promise.all([first, second]);
console.log(JSON.stringify({ writes, storedSignature:stored?.payload?.signatures?.acknowledged, mirrorSignature:localStorage.value?.signatures?.acknowledged }));
"""
        output = self._node_save_harness(write_body, call_body)
        self.assertEqual(output['writes'][0]['acknowledged'], '')
        self.assertEqual(output['writes'][1]['acknowledged'], 'client-signature')
        self.assertEqual(output['storedSignature'], 'client-signature')
        self.assertEqual(output['mirrorSignature'], 'client-signature')

    @unittest.skipUnless(NODE.exists(), f'Node runtime unavailable at {NODE}')
    def test_failed_local_write_recovers_and_allows_next_signed_save(self):
        write_body = """
const warnDelays = [40, 0];
let warnCount = 0;
warnOfflineTSRStoragePressure = function() {
  const delay = warnDelays[warnCount++] || 0;
  return new Promise(resolve => setTimeout(() => resolve({ available:true }), delay));
};
function buildOfflineTSRDraftRecord(data) {
  return Promise.resolve({ id:data._draft_id, payload:Object.assign({}, data) });
}
function offlineTSRDBPut(store, value) {
  const index = writes.length;
  writes.push({ id:value.id, acknowledged:value.payload.signatures.acknowledged });
  return new Promise((resolve, reject) => setTimeout(() => {
    if(index === 0) reject(new Error('controlled local write failure'));
    else { stored = JSON.parse(JSON.stringify(value)); resolve(value.id); }
  }, index === 0 ? 0 : 0));
}
"""
        call_body = """
const first = saveStandaloneTSRDraftLocally({ _draft_id:'draft-1', signatures:{ serviced:'engineer', acknowledged:'' }, attachments:[] }, { serverSync:'none' });
const second = saveStandaloneTSRDraftLocally({ _draft_id:'draft-1', signatures:{ serviced:'engineer', acknowledged:'client-signature' }, attachments:[] }, { serverSync:'none' });
await Promise.all([first, second]);
console.log(JSON.stringify({ writes, storedSignature:stored?.payload?.signatures?.acknowledged, mirrorSignature:localStorage.value?.signatures?.acknowledged }));
"""
        output = self._node_save_harness(write_body, call_body)
        self.assertEqual(len(output['writes']), 2)
        self.assertEqual(output['storedSignature'], 'client-signature')
        self.assertEqual(output['mirrorSignature'], 'client-signature')

    @unittest.skipUnless(NODE.exists(), f'Node runtime unavailable at {NODE}')
    def test_saved_draft_reopen_restores_both_signatures(self):
        apply_draft = (
            'function applyStandaloneTSRDraftData(data){'
            + self.tsr_source.split('function applyStandaloneTSRDraftData(data){', 1)[1]
            .split('\nfunction setOnlineTSRRevisionContext', 1)[0]
        )
        write_body = """
function buildOfflineTSRDraftRecord(data) {
  return Promise.resolve({ id:data._draft_id, payload:Object.assign({}, data) });
}
function offlineTSRDBPut(store, value) { stored = JSON.parse(JSON.stringify(value)); return Promise.resolve(value.id); }
"""
        call_body = f"""
const fields = {{
  'tsr-requested-by': {{ id:'tsr-requested-by', value:'Requester' }},
  'tsr-acknowledged-by': {{ id:'tsr-acknowledged-by', value:'Acknowledged' }},
  'tsr-contact-no': {{ id:'tsr-contact-no', value:'100' }},
  'tsr-email-add': {{ id:'tsr-email-add', value:'client@example.test' }}
}};
const document = {{
  querySelectorAll() {{ return Object.values(fields); }},
  getElementById(id) {{
    if(!fields[id]) fields[id] = {{ id, value:'', innerHTML:'', classList:{{ add(){{}}, remove(){{}}, toggle(){{}} }} }};
    return fields[id];
  }}
}};
const window = {{ calibrationReport: {{ apply(){{}} }} }};
let signatureData = {{ serviced:'engineer-signature', acknowledged:'client-signature' }};
let standaloneTSRAutosavePaused = false;
let selectedStandaloneScheduleId = '';
let selectedStandaloneScheduleSnapshot = null;
let standaloneScheduleOptions = [];
let awaitingScheduleRepick = false;
let standaloneDocuments = [];
function isSameScheduleSelection() {{ return false; }}
function renderTSRClientContactSuggestions() {{}}
function renderTSRScheduleCoveragePanel() {{}}
function normalizeQueuedAttachments(value) {{ return Array.isArray(value) ? value : []; }}
function addTSRPartRow() {{}}
function setFieldValue(id, value) {{ if(fields[id]) fields[id].value = value || ''; }}
function renderDocs() {{}}
function renderTSRAttachments() {{}}
function updateSignatureStatuses() {{}}
function toggleTSROtherCategory() {{}}
function setStandaloneScheduleLockedFields() {{}}
function hasStandaloneScheduleSelection() {{ return false; }}
function updateCreateTSRScheduleGate() {{}}
const LOGGED_IN_ENGINEER_NAME = 'Engineer';
{apply_draft}
await saveStandaloneTSRDraftLocally({{ _draft_id:'draft-1', signatures:signatureData, attachments:[] }}, {{ serverSync:'none' }});
signatureData = {{ serviced:'', acknowledged:'' }};
applyStandaloneTSRDraftData(stored.payload);
console.log(JSON.stringify({{ restored:signatureData, stored:stored.payload.signatures }}));
"""
        output = self._node_save_harness(write_body, call_body)
        self.assertEqual(output['restored'], {
            'serviced': 'engineer-signature',
            'acknowledged': 'client-signature',
        })
        self.assertEqual(output['stored'], output['restored'])

    @unittest.skipUnless(NODE.exists(), f'Node runtime unavailable at {NODE}')
    def test_late_save_for_another_draft_cannot_replace_active_form_state(self):
        write_body = """
function buildOfflineTSRDraftRecord(data) {
  return new Promise(resolve => setTimeout(() => resolve({ id:data._draft_id, payload:Object.assign({}, data) }), 35));
}
function offlineTSRDBPut(store, value) { stored = JSON.parse(JSON.stringify(value)); return Promise.resolve(value.id); }
"""
        call_body = """
const pending = saveStandaloneTSRDraftLocally({ _draft_id:'draft-1', signatures:{ serviced:'engineer', acknowledged:'old-client' }, attachments:[{ name:'old.jpg' }] }, { serverSync:'none' });
setTimeout(() => {
  standaloneTSRActiveContextVersion = 2;
  standaloneCurrentDraftId = 'draft-2';
  offlineTSRAttachments = [{ name:'new.jpg' }];
}, 5);
await pending;
console.log(JSON.stringify({ activeDraftId:standaloneCurrentDraftId, attachments:offlineTSRAttachments }));
"""
        output = self._node_save_harness(write_body, call_body)
        self.assertEqual(output['activeDraftId'], 'draft-2')
        self.assertEqual(output['attachments'], [{ 'name':'new.jpg' }])

    def test_contact_capture_source_uses_acknowledger_or_neutral_name(self):
        auto = self._helper_body(
            'def auto_capture_tsr_client_contact_from_payload(shift, payload):',
            '\ndef save_tsr_payload_contact_to_medical_center(shift, payload, source_label=\'online_tsr\'):',
        )
        direct = self._helper_body(
            'def save_tsr_payload_contact_to_medical_center(shift, payload, source_label=\'online_tsr\'):',
            '\ndef repair_recent_online_tsr_contacts_for_medical_centers',
        )
        for helper in (auto, direct):
            contact_name = (
                helper.split('raw_contact_name = (', 1)[1]
                if 'raw_contact_name = (' in helper
                else helper.split('contact_name = (', 1)[1]
            ).split('contact_phone', 1)[0]
            self.assertIn("clean_str(payload.get('tsr-acknowledged-by'))", contact_name)
            self.assertIn("'TSR Contact'", contact_name)
            self.assertNotIn("payload.get('tsr-requested-by')", contact_name)

    def test_timeline_exposes_late_calibration_report_shortcuts(self):
        for marker in (
            "online_tsr_submission_id",
            "calibration_report_state",
            "redirectToCalibrationReportFromSchedule",
            "context.mode = 'calibration_report'",
            "Add Calibration Report",
            "Finish Calibration Report",
            "View Calibration Report",
        ):
            self.assertIn(marker, self.app_source + self.timeline_source)
        for marker in (
            'openTimelineSummaryCalibrationReport',
            'openMobileFullCalendarLiteCalibrationReportAction',
            'schedule-card-action-tsr',
            'mobile-sticky-offline-tsr',
            'canOpenCalibrationReportForSchedule',
        ):
            self.assertIn(marker, self.timeline_source)
        legacy_gate = self.timeline_source.split('function canOpenCalibrationReportForSchedule', 1)[1].split('function getCalibrationReportTimelineLabel', 1)[0]
        self.assertIn('getScheduleOnlineTSRSubmissionId(shift)', legacy_gate)

    def test_timeline_exposes_pre_submission_calibration_report_shortcuts(self):
        gate = self.timeline_source.split(
            'function canOpenCalibrationReportForSchedule', 1
        )[1].split('function getCalibrationReportTimelineLabel', 1)[0]
        self.assertIn('hasScheduleTSREquipmentAssignment(shift)', gate)
        self.assertIn('if(!submissionId) return true;', gate)
        self.assertIn('pending_sync', gate)
        self.assertIn('queue_id', gate)

        route = self.timeline_source.split(
            'function redirectToCalibrationReportFromSchedule', 1
        )[1].split('function openOfflineTSRDraftFromShiftModal', 1)[0]
        self.assertIn('context.open_calibration_report = true', route)
        self.assertIn("context.mode = 'calibration_report'", route)
        self.assertIn('context.submission_id = submissionId', route)

    def test_create_tsr_preserves_pre_submission_calibration_handoff_and_order(self):
        context = self.tsr_source.split(
            'function normalizeStandaloneCreateTSRContext', 1
        )[1].split('function getStandaloneCreateTSRHandoffContext', 1)[0]
        self.assertIn('open_calibration_report', context)

        url_context = self.tsr_source.split(
            'function getStandaloneCreateTSRHandoffContext', 1
        )[1].split('function findStandaloneScheduleFromCreateTSRContext', 1)[0]
        self.assertIn('open_calibration_report', url_context)

        url_builder = self.timeline_source.split(
            'function buildCreateTSRPageUrlFromContext', 1
        )[1].split('function storeCreateTSRContextForPage', 1)[0]
        self.assertIn('open_calibration_report', url_builder)

        handoff = self.tsr_source.split(
            'function applyCreateTSRHandoffToStandaloneTSR', 1
        )[1].split('function normalizeStandaloneScheduleOptions', 1)[0]
        self.assertIn('calibrationReport', handoff)
        self.assertIn('.create', handoff)
        self.assertLess(
            handoff.index('applyScheduleToStandaloneTSR(schedule, true)'),
            handoff.index('.create'),
        )
        self.assertIn('findStandaloneScheduleFromCreateTSRContext(context)', handoff)
        self.assertIn('openCalibrationReport\n    ? (targetScheduleId', handoff)
        self.assertIn(
            ': (findStandaloneScheduleFromCreateTSRContext(context) || ensureStandaloneScheduleOptionFromContext(context))',
            handoff,
        )

    @unittest.skipUnless(NODE.exists(), f'Node runtime unavailable at {NODE}')
    def test_pre_submission_calibration_gate_runtime_matrix(self):
        gate_start = self.timeline_source.index('function canOpenCalibrationReportForSchedule')
        gate_end = self.timeline_source.index('function getCalibrationReportTimelineLabel', gate_start)
        gate = self.timeline_source[gate_start:gate_end]
        url_start = self.timeline_source.index('function buildCreateTSRPageUrlFromContext')
        url_end = self.timeline_source.index('function storeCreateTSRContextForPage', url_start)
        url_builder = self.timeline_source[url_start:url_end]
        script = """
function getScheduleOnlineTSRSubmissionId(shift){ return Number(shift?.online_tsr_submission_id || 0) || 0; }
function hasScheduleTSRAttachment(shift){ return Number(shift?.service_file_delivery?.categories?.tsr?.total_count || 0) > 0 || (shift?.file_details || []).some(file => Boolean(file?.is_tsr)); }
function hasScheduleTSREquipmentAssignment(shift){ const source = String(shift?.equipment_source || '').trim().toLowerCase(); return Boolean(shift && shift.client_id && String(shift.product_id || '').trim() && String(shift.product_name || '').trim() && ['product', 'genoray', 'vieworks'].includes(source) && shift.equipment_available !== false); }
""" + gate + url_builder + """
const base = { id:42, client_id:7, product_id:'SN-42', product_name:'Flexavision F3', equipment_source:'product', equipment_available:true };
const cases = {
  pre_submission: canOpenCalibrationReportForSchedule({...base}),
  pre_submission_manual_tsr: canOpenCalibrationReportForSchedule({...base, file_details:[{is_tsr:true}]}),
  submitted_with_tsr: canOpenCalibrationReportForSchedule({...base, online_tsr_submission_id:9, file_details:[{is_tsr:true}]}),
  submitted_without_tsr: canOpenCalibrationReportForSchedule({...base, online_tsr_submission_id:9}),
  queued: canOpenCalibrationReportForSchedule({...base, pending_sync:true, queue_id:'q-1'}),
  no_equipment: canOpenCalibrationReportForSchedule({...base, product_id:'', product_name:''}),
  hr_redacted: canOpenCalibrationReportForSchedule({...base, client_id:null, product_id:null, product_name:''}),
  pre_url: buildCreateTSRPageUrlFromContext({ shift_id:42, date:'2026-09-25', open_calibration_report:true }),
  submitted_url: buildCreateTSRPageUrlFromContext({ shift_id:42, submission_id:9, mode:'calibration_report' })
};
console.log(JSON.stringify(cases));
"""
        output = self._run_node_json(script)
        self.assertEqual(output['pre_submission'], True)
        self.assertEqual(output['pre_submission_manual_tsr'], True)
        self.assertEqual(output['submitted_with_tsr'], True)
        self.assertEqual(output['submitted_without_tsr'], False)
        self.assertEqual(output['queued'], False)
        self.assertEqual(output['no_equipment'], False)
        self.assertEqual(output['hr_redacted'], False)
        self.assertIn('open_calibration_report=1', output['pre_url'])
        self.assertNotIn('mode=calibration_report', output['pre_url'])
        self.assertIn('mode=calibration_report', output['submitted_url'])
        self.assertNotIn('open_calibration_report', output['submitted_url'])

    @unittest.skipUnless(NODE.exists(), f'Node runtime unavailable at {NODE}')
    def test_pre_submission_handoff_opens_only_after_safe_schedule_binding(self):
        normalize_start = self.tsr_source.index('function normalizeStandaloneCreateTSRContext')
        normalize_end = self.tsr_source.index('function getStandaloneCreateTSRHandoffContext', normalize_start)
        context_start = normalize_end
        context_end = self.tsr_source.index('function findStandaloneScheduleFromCreateTSRContext', context_start)
        handoff_start = self.tsr_source.index('function applyCreateTSRHandoffToStandaloneTSR')
        handoff_end = self.tsr_source.index('function normalizeStandaloneScheduleOptions', handoff_start)
        real_id_start = self.tsr_source.index('function getStandaloneScheduleRealId')
        real_id_end = self.tsr_source.index('function normalizeStandaloneCreateTSRContext', real_id_start)
        script = """
const events = [];
const sessionStorage = { getItem(){ return null; }, removeItem(){ events.push('context-removed'); } };
const window = { location:{ search:'?schedule_id=42&open_calibration_report=1' }, calibrationReport:{ create(){ events.push('create'); } } };
const document = { getElementById(){ return { value:'' }; } };
const LOGGED_IN_ENGINEER_NAME = 'Engineer';
const LOGGED_IN_ENGINEER_INITIALS = 'EN';
let standaloneScheduleOptions = [];
let selectedStandaloneScheduleId = '';
let calibrationReportHandoffOpened = false;
function isScheduleEquipmentAssignable(schedule){ return Boolean(schedule?.client_id && schedule?.product_id && schedule?.product_name && schedule?.equipment_available !== false); }
function getStandaloneScheduleRuntimeId(schedule){ return String(schedule?.id || ''); }
function applyScheduleToStandaloneTSR(schedule){ events.push('apply:' + schedule.id); }
function showTSRStatus(message){ events.push('status:' + message); }
""" + self.tsr_source[real_id_start:real_id_end] + self.tsr_source[normalize_start:normalize_end] + self.tsr_source[context_start:context_end] + self.tsr_source[handoff_start:handoff_end] + """
function resetContext(){ events.splice(0, events.length); calibrationReportHandoffOpened = false; selectedStandaloneScheduleId = ''; }
const good = { id:42, client_id:7, product_id:'SN-42', product_name:'Flexavision F3', equipment_available:true };
standaloneScheduleOptions = [good];
const success = applyCreateTSRHandoffToStandaloneTSR();
const successEvents = events.slice();
resetContext();
standaloneScheduleOptions = [];
const missing = applyCreateTSRHandoffToStandaloneTSR();
const missingEvents = events.slice();
resetContext();
standaloneScheduleOptions = [{...good, id:99}];
const stale = applyCreateTSRHandoffToStandaloneTSR();
const staleEvents = events.slice();
resetContext();
standaloneScheduleOptions = [{...good, product_id:'', product_name:''}];
const unassignable = applyCreateTSRHandoffToStandaloneTSR();
const unassignableEvents = events.slice();
console.log(JSON.stringify({ success, successEvents, missing, missingEvents, stale, staleEvents, unassignable, unassignableEvents }));
"""
        output = self._run_node_json(script)
        self.assertTrue(output['success'])
        self.assertEqual(output['successEvents'][0], 'apply:42')
        self.assertIn('context-removed', output['successEvents'])
        self.assertEqual(output['successEvents'].count('create'), 1)
        self.assertLess(output['successEvents'].index('apply:42'), output['successEvents'].index('create'))
        self.assertTrue(output['missing'])
        self.assertTrue(output['stale'])
        self.assertTrue(output['unassignable'])
        self.assertNotIn('create', output['missingEvents'])
        self.assertNotIn('create', output['staleEvents'])
        self.assertNotIn('create', output['unassignableEvents'])

    def test_create_tsr_contains_calibration_only_upload_contract(self):
        for marker in (
            "isOnlineTSRCalibrationMode",
            "loadOnlineTSRCalibrationFromUrl",
            "saveStandaloneCalibrationReport",
            "late_calibration_report",
            "calibration_report_json",
        ):
            self.assertIn(marker, self.tsr_source)

    def test_requester_email_capture_remains_available(self):
        auto = self._helper_body(
            'def auto_capture_tsr_client_contact_from_payload(shift, payload):',
            '\ndef save_tsr_payload_contact_to_medical_center(shift, payload, source_label=\'online_tsr\'):',
        )
        email_block = auto.split('email_candidates =', 1)[1].split("if not email_candidates", 1)[0]
        self.assertIn("payload.get('tsr-requested-by')", email_block)
        self.assertIn("payload.get('tsr_requested_by')", email_block)

    def test_local_save_has_ordered_snapshot_and_reopen_barrier(self):
        for marker in (
            'let standaloneTSRLocalSaveChain = Promise.resolve();',
            'function captureStandaloneTSRLocalSaveContext(',
            'function waitForStandaloneTSRLocalSaves()',
            'saveStandaloneTSRDraftLocallyNow',
            'serverSync',
        ):
            self.assertIn(marker, self.tsr_source)
        save_fn = self.tsr_source.split('async function saveStandaloneTSRDraftLocally', 1)[1].split(
            '\nasync function clearStandaloneTSRDraftLocally', 1
        )[0]
        self.assertIn('standaloneTSRLocalSaveChain', save_fn)
        self.assertIn('captureStandaloneTSRLocalSaveContext', save_fn)
        open_fn = self.tsr_source.split('async function openStandaloneTSRDraft', 1)[1].split(
            '\nasync function deleteStandaloneTSRDraft', 1
        )[0]
        self.assertIn('await waitForStandaloneTSRLocalSaves()', open_fn)
        self.assertLess(open_fn.index('await waitForStandaloneTSRLocalSaves()'), open_fn.index('loadStandaloneTSRDraftRecordById'))

    def test_worker_and_release_are_bumped_for_followup(self):
        self.assertIn(
            "medical-service-pwa-offline-navigation-v158-calibration-center",
            self.app_source,
        )
        self.assertIn(
            "medical-service-pwa-offline-navigation-v199-client-group-picker",
            self.app_source,
        )
        self.assertIn('2026-09-25-pre-submission-calibration-report', self.release_source)
        self.assertIn('2026-09-08-tsr-offline-draft-save-order', self.release_source)
        self.assertIn('Service Requested By and Acknowledged By', self.release_source)

    def test_equipment_first_picker_and_server_contract(self):
        self.assertIn("medical-service-pwa-offline-navigation-v174-equipment-first-tsr", self.app_source)
        self.assertIn('def validate_tsr_shift_equipment(shift):', self.app_source)
        self.assertIn("'reason': 'equipment_client_mismatch'", self.app_source)
        ensure_body = self.app_source.split('def ensure_product_from_tsr_payload(shift, payload):', 1)[1].split(
            '\ndef get_online_tsr_missing_core_details', 1
        )[0]
        self.assertNotIn('Product(', ensure_body)
        self.assertNotIn('_equipment_inventory_create_requested', self.tsr_source)
        self.assertIn('function isScheduleEquipmentAssignable(schedule)', self.tsr_source)
        self.assertIn('equipment_available', self.tsr_source)
        self.assertIn('Unavailable — select equipment on Calendar first', self.tsr_source)
        self.assertIn('function hasScheduleTSREquipmentAssignment(shift)', self.timeline_source)
        self.assertIn('data-create-tsr-button', self.timeline_source)
        self.assertIn('redirectToCreateTSRPageFromQueuedSchedule', self.timeline_source)
        self.assertIn('Select equipment on Calendar first before creating a TSR.', self.timeline_source)
        self.assertIn('2026-09-23-equipment-first-tsr', self.release_source)


class TsrOfflineFollowupBackendTests(unittest.TestCase):
    """The real capture helpers must not turn requester-only payloads into acknowledgers."""

    @classmethod
    def setUpClass(cls):
        cls.client_template = dict(
            id=701,
            name='Followup Client',
            contact_person_1='', contact_number_1='', email_address_1='',
            contact_person_2='', contact_number_2='', email_address_2='',
            contact_person_3='', contact_number_3='', email_address_3='',
        )

    def _run_capture(self, helper_name, include_acknowledger=False):
        if app_module is None:
            self.skipTest(f'app dependencies unavailable: {APP_IMPORT_ERROR}')
        client = SimpleNamespace(**self.client_template)
        shift = SimpleNamespace(id=801, client_id=client.id)
        contact_query = Mock()
        contact_query.filter_by.return_value.order_by.return_value.all.return_value = []
        added = []
        payload = {
            'tsr-requested-by': 'Requester Only',
            'tsr-email-add': 'requester@example.test',
            'tsr-contact-no': '555-0100',
        }
        expected_name = 'TSR Contact'
        if include_acknowledger:
            payload['tsr-acknowledged-by'] = 'Acknowledged Person'
            expected_name = 'Acknowledged Person'
        with app_module.app.app_context(), \
                patch.object(app_module.Contact, 'query', contact_query), \
                patch.object(app_module.db.session, 'get', return_value=client), \
                patch.object(app_module.db.session, 'add', side_effect=added.append), \
                patch.object(app_module.db.session, 'flush', return_value=None), \
                patch.object(app_module, 'current_user', SimpleNamespace(username='followup-test')):
            result = getattr(app_module, helper_name)(shift, payload)

        contacts = [item for item in added if isinstance(item, app_module.Contact)]
        self.assertEqual(result, ['requester@example.test'])
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0].name, expected_name)
        self.assertEqual(contacts[0].email, 'requester@example.test')

    def test_auto_capture_uses_neutral_name_for_requester_only_payload(self):
        self._run_capture('auto_capture_tsr_client_contact_from_payload')

    def test_direct_capture_uses_neutral_name_for_requester_only_payload(self):
        self._run_capture('save_tsr_payload_contact_to_medical_center')

    def test_auto_capture_uses_acknowledger_when_requester_differs(self):
        self._run_capture('auto_capture_tsr_client_contact_from_payload', include_acknowledger=True)

    def test_direct_capture_uses_acknowledger_when_requester_differs(self):
        self._run_capture('save_tsr_payload_contact_to_medical_center', include_acknowledger=True)


if __name__ == '__main__':
    unittest.main()
