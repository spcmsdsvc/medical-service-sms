"""Calibration Report saves after the schedule's TSR was saved (2026-10-13 incident).

Saving a TSR leaves a permanent deletion tombstone on its schedule+date draft key. A report
started later for that schedule reused the key and every save was refused, so a reload lost it.
"""
import json
import os
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = pathlib.Path(os.environ.get('TSR_TEST_NODE') or r'C:\Users\Jonamar\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe')
SCRIPT_PATH = os.environ.get('CAL_REPORT_SCRIPT_PATH') or 'static/js/app-calibration-report.js'
TEMPLATE_PATH = os.environ.get('CAL_REPORT_TEMPLATE_PATH') or 'templates/offline_tsr.html'


NODE_TEMPLATE_RELEASE_SCRIPT = r'''
const fs = require('fs');
const vm = require('vm');
const template = fs.readFileSync(process.argv[1], 'utf8');
function section(start, end){
  const first = template.indexOf(start);
  const last = template.indexOf(end, first);
  if(first < 0 || last <= first) throw new Error('section missing: ' + start);
  return template.slice(first, last);
}
const store = new Map();
const context = {
  console, Promise, Date, Math, JSON, Map,
  localStorage:{ getItem:k => store.has(k) ? store.get(k) : null, setItem:(k, v) => store.set(k, String(v)), removeItem:k => store.delete(k) },
  STANDALONE_TSR_SERVER_DELETE_KEY:'deletes',
  STANDALONE_TSR_ACCOUNT_SCOPE:'17',
  standaloneTSRDraftDeleteGenerations:new Map(),
  standaloneTSRServerDraftSyncChain:Promise.resolve(),
  standaloneCurrentDraftId:'',
  calibrationMode:false,
  onlineTSRCalibrationContext:null,
  todayISO:() => '2026-10-13',
  isOnlineTSRCalibrationMode:() => context.calibrationMode,
  hasStandaloneScheduleSelection:() => true,
  collectTSRData:() => ({ schedule_id:'878', 'tsr-service-date':'2026-09-30', calibration_report:{ status:'draft' } }),
  advanceStandaloneTSRActiveContext:() => 1
};
vm.createContext(context);
vm.runInContext([
  section('const OFFLINE_TSR_DRAFT_PREFIX =', 'function getStandaloneTSRDraftTitle(data){'),
  section('function readStandaloneTSRServerDraftDeleteQueue(){', 'function queueStandaloneTSRServerDraftDelete(id){')
].join('\n'), context);

(async () => {
  const key = 'standalone_tsr_draft_878-2026-09-30';
  // The state a saved TSR leaves behind.
  context.markStandaloneTSRDraftDeletionPending(key);
  context.markStandaloneTSRDraftDeletionConfirmed(key);
  if(!context.isStandaloneTSRDraftDeletionTombstoned(key)) throw new Error('setup: tombstone missing');
  const released = await context.releaseCalibrationReportDraftDeletion();
  const preTsrReleased = released === true && !context.isStandaloneTSRDraftDeletionTombstoned(key);

  const lateKey = 'standalone_tsr_draft_late_calibration_17_35';
  context.markStandaloneTSRDraftDeletionPending(lateKey);
  context.calibrationMode = true;
  context.onlineTSRCalibrationContext = { submission_id:35 };
  await context.releaseCalibrationReportDraftDeletion();
  const lateReleased = !context.isStandaloneTSRDraftDeletionTombstoned(lateKey);
  const sharedLateId = context.prepareStandaloneLateCalibrationDraft({}, '35')._draft_id === lateKey;
  console.log(JSON.stringify({ preTsrReleased, lateReleased, sharedLateId }));
})().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
'''

NODE_MODULE_SCRIPT = r'''
const fs = require('fs');
const vm = require('vm');
const statuses = [];
const listeners = {};
const order = [];
const context = {
  console, Blob, Uint8Array, ArrayBuffer, Promise, Date, Math, JSON, setTimeout, clearTimeout,
  URL:{ createObjectURL:() => 'blob:test', revokeObjectURL:() => {} },
  document:{ querySelector:() => null, querySelectorAll:() => [], createElement:() => ({}), addEventListener:() => {} },
  addEventListener:(name, handler) => { listeners[name] = handler; },
  CalibrationReportConfig:{},
  showTSRStatus:(message, tone) => statuses.push({ message, tone })
};
context.window = context; context.self = context; context.globalThis = context;
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
const api = context.calibrationReport;
let releaseResult = true;
let saveResult = { source:'offline_tsr_page' };
context.releaseCalibrationReportDraftDeletion = async () => { order.push('release'); return releaseResult; };
context.saveStandaloneTSRDraft = async () => { order.push('save'); return saveResult; };
function leaveBlocked(){
  const handler = listeners.beforeunload;
  if(typeof handler !== 'function') return null;
  let prevented = false;
  const event = { preventDefault(){ prevented = true; }, returnValue:undefined };
  handler(event);
  return prevented;
}

(async () => {
  api.apply({ status:'draft', facility:{ name:'Davao Doctors Hospital' } });
  await api.saveDraft();
  const releasedBeforeSave = order.join(',') === 'release,save';
  const leaveAfterSuccess = leaveBlocked();

  order.length = 0;
  saveResult = { id:'k', skipped:true, reason:'draft_deletion_pending' };
  await api.saveDraft();
  const tombstoneMessage = statuses.at(-1)?.message || '';
  const leaveAfterFailure = leaveBlocked();

  order.length = 0;
  releaseResult = false;
  await api.saveDraft();
  const blockedWithoutSave = order.join(',') === 'release';

  releaseResult = true;
  saveResult = { source:'offline_tsr_page' };
  await api.saveDraft();
  const leaveAfterRecovery = leaveBlocked();
  console.log(JSON.stringify({ releasedBeforeSave, leaveAfterSuccess, tombstoneMessage, leaveAfterFailure, blockedWithoutSave, leaveAfterRecovery }));
})().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
'''

NODE_REDIRECT_SCRIPT = r'''
const fs = require('fs');
const vm = require('vm');
const template = fs.readFileSync(process.argv[1], 'utf8');
const start = template.indexOf('async function redirectCalibrationHandoffToSavedTSR(){');
if(start < 0) throw new Error('redirect function missing');
const end = template.indexOf('function normalizeStandaloneScheduleOptions(', start);
function run(search, response, online=true){
  const replaced = [];
  const fetched = [];
  const context = {
    console, Promise, JSON, URLSearchParams, encodeURIComponent,
    navigator:{ onLine:online },
    sessionStorage:{ removeItem:() => {} },
    fetch:async url => { fetched.push(url); return response; },
    window:{ location:{ search, pathname:'/offline-tsr', replace:url => replaced.push(url) } }
  };
  vm.createContext(context);
  vm.runInContext(template.slice(start, end), context);
  return context.redirectCalibrationHandoffToSavedTSR().then(result => ({ result, replaced, fetched }));
}
const found = { ok:true, json:async () => ({ status:'success', submission:{ submission_id:35 } }) };
const missing = { ok:false, json:async () => ({ status:'error' }) };
(async () => {
  const saved = await run('?schedule_id=878&engineer_id=15&date=2026-09-30&open_calibration_report=1', found);
  const none = await run('?schedule_id=878&open_calibration_report=1', missing);
  const offline = await run('?schedule_id=878&open_calibration_report=1', found, false);
  const plainTsr = await run('?schedule_id=878', found);
  console.log(JSON.stringify({
    redirected:saved.result === true,
    target:saved.replaced[0] || '',
    lookup:saved.fetched[0] || '',
    noTsrStays:none.result === false && none.replaced.length === 0,
    offlineSkipsLookup:offline.result === false && offline.fetched.length === 0,
    plainCreateTsrUntouched:plainTsr.result === false && plainTsr.fetched.length === 0
  }));
})().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
'''


NODE_HANDOFF_REOPEN_SCRIPT = r'''
const fs = require('fs');
const vm = require('vm');
const template = fs.readFileSync(process.argv[1], 'utf8');
const start = template.indexOf('async function openCalibrationReportHandoff(createCalibrationReport){');
if(start < 0) throw new Error('handoff reopen function missing');
const end = template.indexOf('function normalizeStandaloneScheduleOptions(', start);
async function run(record, openResult){
  const calls = [];
  const context = {
    console, Promise, String,
    collectTSRData:() => ({}),
    resolveStandaloneTSRDraftId:() => 'standalone_tsr_draft_878-2026-09-30',
    loadStandaloneTSRDraftRecordById:async () => record,
    openStandaloneTSRDraft:async id => { calls.push('open:' + id); return openResult; }
  };
  vm.createContext(context);
  vm.runInContext(template.slice(start, end), context);
  await context.openCalibrationReportHandoff(() => calls.push('create'));
  return calls.join(',');
}
(async () => {
  const saved = { payload:{ calibration_report:{ status:'draft' } } };
  console.log(JSON.stringify({
    savedReopened:await run(saved, undefined),
    conflictStops:await run(saved, false),
    noDraftCreates:await run(null, undefined),
    notStartedCreates:await run({ payload:{ calibration_report:{ status:'not_started' } } }, undefined)
  }));
})().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
'''


def run_node(script, target):
    result = subprocess.run([str(NODE), '-e', script, str(ROOT / target)], cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return json.loads(result.stdout.strip().splitlines()[-1])


@unittest.skipUnless(NODE.is_file(), f'Bundled Node runtime missing: {NODE}')
class CalibrationReportTombstoneTests(unittest.TestCase):
    def test_deliberate_report_actions_release_the_saved_tsr_tombstone(self):
        payload = run_node(NODE_TEMPLATE_RELEASE_SCRIPT, TEMPLATE_PATH)
        self.assertTrue(payload['preTsrReleased'], 'pre-TSR report key stayed tombstoned')
        self.assertTrue(payload['lateReleased'], 'late report key stayed tombstoned')
        self.assertTrue(payload['sharedLateId'])

    def test_save_draft_releases_first_names_the_cause_and_guards_leaving(self):
        payload = run_node(NODE_MODULE_SCRIPT, SCRIPT_PATH)
        self.assertTrue(payload['releasedBeforeSave'])
        self.assertFalse(payload['leaveAfterSuccess'])
        self.assertIn('older deleted draft is blocking it', payload['tombstoneMessage'])
        self.assertIn('Keep this page open', payload['tombstoneMessage'])
        self.assertTrue(payload['leaveAfterFailure'])
        self.assertTrue(payload['blockedWithoutSave'])
        self.assertFalse(payload['leaveAfterRecovery'])

    def test_report_handoff_opens_against_an_existing_saved_tsr(self):
        payload = run_node(NODE_REDIRECT_SCRIPT, TEMPLATE_PATH)
        self.assertTrue(payload['redirected'])
        self.assertEqual(payload['lookup'], '/get_latest_online_tsr_for_shift/878')
        self.assertTrue(payload['target'].startswith('/calibration-report?'), payload['target'])
        self.assertNotIn('mode=', payload['target'])
        self.assertIn('submission_id=35', payload['target'])
        self.assertNotIn('open_calibration_report', payload['target'])
        self.assertTrue(payload['noTsrStays'])
        self.assertTrue(payload['offlineSkipsLookup'])
        self.assertTrue(payload['plainCreateTsrUntouched'])

    def test_calendar_handoff_reopens_the_report_saved_on_this_device(self):
        payload = run_node(NODE_HANDOFF_REOPEN_SCRIPT, TEMPLATE_PATH)
        self.assertEqual(payload['savedReopened'], 'open:standalone_tsr_draft_878-2026-09-30,create')
        self.assertEqual(payload['conflictStops'], 'open:standalone_tsr_draft_878-2026-09-30',
                         'a blank report must not open while two saved copies await a choice')
        self.assertEqual(payload['noDraftCreates'], 'create')
        self.assertEqual(payload['notStartedCreates'], 'create')

    def test_load_chain_checks_for_saved_tsr_before_the_pre_tsr_handoff(self):
        source = (ROOT / TEMPLATE_PATH).read_text(encoding='utf-8')
        chain = source.split('return loadOnlineTSRRevisionFromUrl();', 1)[1]
        self.assertIn('await redirectCalibrationHandoffToSavedTSR()', chain)
        self.assertLess(chain.index('await redirectCalibrationHandoffToSavedTSR()'),
                        chain.index('applyCreateTSRHandoffToStandaloneTSR()'))


if __name__ == '__main__':
    unittest.main()
