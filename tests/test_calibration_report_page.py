"""Calibration Report for a saved TSR: its own page and its account backup (plans.md, 2026-10-14).

The backup reuses the device draft key (standalone_tsr_draft_late_calibration_<user>_<submission>)
so drafts saved before this change, on the device or by the older account backup, still open.
"""
import json
import os
import pathlib
import subprocess
import tempfile
import unittest
import uuid
from datetime import datetime

from flask import g

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_calibration_report_page_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB_PATH))
os.environ.setdefault("SECRET_KEY", "calibration-report-page-tests")

import app as app_module  # noqa: E402
from tests.schema_flags import reset_schema_flags  # noqa: E402

NODE = pathlib.Path(os.environ.get('TSR_TEST_NODE') or r'C:\Users\Jonamar\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe')
TEMPLATE_PATH = os.environ.get('CAL_REPORT_TEMPLATE_PATH') or 'templates/offline_tsr.html'
TIMELINE_PATH = os.environ.get('CAL_REPORT_TIMELINE_PATH') or 'templates/timeline.html'


class CalibrationReportPageServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=True)

    def setUp(self):
        self.context = self.app.app_context()
        self.context.push()
        app_module.db.create_all()
        app_module.ensure_tsr_draft_schema()
        app_module.ensure_calibration_certificate_approval_table()

        suffix = uuid.uuid4().hex[:8]
        self.engineer = app_module.User(username=f"cal-page-eng-{suffix}", password="test", role="engineer", is_active=True)
        self.other = app_module.User(username=f"cal-page-other-{suffix}", password="test", role="engineer", is_active=True)
        self.profile = app_module.Engineer(employee_id=f"CPE-{suffix}", name="Page Engineer", initials="PE", branch="Manila")
        self.other_profile = app_module.Engineer(employee_id=f"CPO-{suffix}", name="Other Engineer", initials="OE", branch="Cebu")
        self.client_record = app_module.Client(name=f"Calibration Page Client {suffix}")
        app_module.db.session.add_all([self.engineer, self.other, self.profile, self.other_profile, self.client_record])
        app_module.db.session.flush()
        self.profile.user_id = self.engineer.id
        self.other_profile.user_id = self.other.id
        self.shift = app_module.Shift(
            title="Calibration Page", start_time=datetime(2026, 9, 30, 9, 0), end_time=datetime(2026, 9, 30, 10, 0),
            engineer_id=self.profile.id, client_id=self.client_record.id, status="Completed",
        )
        app_module.db.session.add(self.shift)
        app_module.db.session.flush()
        app_module.db.session.add(app_module.ShiftEngineer(shift_id=self.shift.id, engineer_id=self.profile.id))
        self.submission = app_module.OnlineTsrSubmission(
            shift_id=self.shift.id, tsr_number=f"TSR-CAL-PAGE-{suffix}", submitted_by_user_id=self.engineer.id,
            submitted_by_name="Page Engineer", status="completed", payload_json=json.dumps({"calibration_report": {}}),
        )
        app_module.db.session.add(self.submission)
        app_module.db.session.commit()
        self.key = f"standalone_tsr_draft_late_calibration_{self.engineer.id}_{self.submission.id}"

    def tearDown(self):
        app_module.db.session.remove()
        app_module.db.drop_all()
        reset_schema_flags(app_module)
        self.context.pop()
        try:
            TEST_DB_PATH.unlink(missing_ok=True)
        except OSError:
            pass

    def client_for(self, user):
        g.pop("_login_user", None)
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True
        return client

    def save(self, client, report):
        g.pop("_login_user", None)
        return client.post(f"/save_calibration_report_draft/{self.submission.id}", json={"calibration_report": report})

    def test_page_renders_report_only_and_old_url_redirects(self):
        client = self.client_for(self.engineer)
        page = client.get(f"/calibration-report?submission_id={self.submission.id}")
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn('offline-tsr-calibration-page', html)
        self.assertIn('window.OFFLINE_TSR_CALIBRATION_PAGE = true', html)
        self.assertIn('Complete or review the Calibration Report attached to the saved TSR.', html)

        g.pop("_login_user", None)
        missing = client.get("/calibration-report")
        self.assertEqual(missing.status_code, 302)
        self.assertTrue(missing.headers["Location"].endswith("/offline-tsr"))

        g.pop("_login_user", None)
        old = client.get(f"/offline-tsr?schedule_id={self.shift.id}&submission_id={self.submission.id}&mode=calibration_report&date=2026-09-30")
        self.assertEqual(old.status_code, 302)
        self.assertEqual(
            old.headers["Location"],
            f"/calibration-report?schedule_id={self.shift.id}&submission_id={self.submission.id}&date=2026-09-30",
        )
        g.pop("_login_user", None)
        plain = client.get("/offline-tsr")
        self.assertEqual(plain.status_code, 200)
        self.assertNotIn('offline-tsr-calibration-page', plain.get_data(as_text=True))

    def test_backup_uses_the_device_key_and_reserves_no_tsr_number(self):
        reservations = app_module.TsrNumberReservation.query.count()
        response = self.save(self.client_for(self.engineer), {"status": "draft", "updated_at": "2026-10-14T01:00:00Z", "rows": [1]})
        self.assertEqual(response.status_code, 200, response.get_json())
        row = app_module.TsrDraft.query.filter_by(user_id=self.engineer.id).one()
        self.assertEqual(row.draft_key, self.key)
        self.assertEqual(app_module.TsrNumberReservation.query.count(), reservations)

        g.pop("_login_user", None)
        drafts = self.client_for(self.engineer).get("/get_tsr_drafts").get_json()["drafts"]
        self.assertEqual(drafts, [], "report backups must not show in Continue Saved Work")

    def test_other_engineer_is_refused_and_older_copy_never_overwrites(self):
        refused = self.save(self.client_for(self.other), {"status": "draft", "updated_at": "2026-10-14T01:00:00Z"})
        self.assertEqual(refused.status_code, 403)

        client = self.client_for(self.engineer)
        self.save(client, {"status": "draft", "updated_at": "2026-10-14T02:00:00Z", "value": "newer"})
        stale = self.save(client, {"status": "draft", "updated_at": "2026-10-14T01:00:00Z", "value": "older"}).get_json()
        self.assertTrue(stale["stale_ignored"])
        self.assertEqual(stale["draft"]["calibration_report"]["value"], "newer")

    def test_tsr_draft_backup_refuses_report_keys(self):
        reservations = app_module.TsrNumberReservation.query.count()
        g.pop("_login_user", None)
        response = self.client_for(self.engineer).post("/save_tsr_draft", json={
            "draft_key": self.key, "payload": {"calibration_report": {"status": "draft"}, "schedule_id": str(self.shift.id)},
        })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error_code"], "calibration_report_own_backup")
        self.assertEqual(app_module.TsrNumberReservation.query.count(), reservations)
        self.assertEqual(app_module.TsrDraft.query.count(), 0)

    def test_existing_old_format_backup_is_returned(self):
        # Written by the older TSR-draft backup: full TSR payload, no submission field.
        app_module.db.session.add(app_module.TsrDraft(
            user_id=self.engineer.id, draft_key=self.key, revision=1,
            payload_json=json.dumps({"tsr-number": "OLD", "calibration_report": {"status": "draft", "value": "kept"}}),
        ))
        app_module.db.session.commit()
        g.pop("_login_user", None)
        result = self.client_for(self.engineer).get(f"/get_calibration_report_draft/{self.submission.id}").get_json()
        self.assertEqual(result["draft"]["calibration_report"]["value"], "kept")

    def test_uploaded_report_refuses_backup_and_upload_cleanup_removes_only_its_row(self):
        client = self.client_for(self.engineer)
        self.save(client, {"status": "draft", "updated_at": "2026-10-14T01:00:00Z"})
        app_module.db.session.add(app_module.TsrDraft(
            user_id=self.engineer.id, draft_key="standalone_tsr_draft_878-2026-09-30", revision=1, payload_json="{}",
        ))
        app_module.db.session.commit()

        self.submission.payload_json = json.dumps({"calibration_report": {"generated": {
            "file_id": 9, "source": "generated_calibration_report"}}})
        app_module.db.session.commit()
        refused = self.save(client, {"status": "final", "updated_at": "2026-10-14T03:00:00Z"})
        self.assertEqual(refused.status_code, 409)

        with self.app.test_request_context():
            app_module.login_user(self.engineer)
            app_module.delete_late_calibration_report_draft(self.submission)
        keys = {row.draft_key for row in app_module.TsrDraft.query.filter_by(user_id=self.engineer.id)}
        self.assertEqual(keys, {"standalone_tsr_draft_878-2026-09-30"})

        source = (ROOT / "app.py").read_text(encoding="utf-8")
        upload = source[source.index("def upload_online_tsr_attachment("):source.index("\n@app.route", source.index("def upload_online_tsr_attachment("))]
        self.assertEqual(upload.count("delete_late_calibration_report_draft(submission)"), 2)


NODE_CLIENT_SCRIPT = r'''
const fs = require('fs');
const vm = require('vm');
const template = fs.readFileSync(process.argv[1], 'utf8');
const timeline = fs.readFileSync(process.argv[2], 'utf8');
function section(source, start, end){
  const first = source.indexOf(start);
  const last = source.indexOf(end, first);
  if(first < 0 || last <= first) throw new Error('section missing: ' + start);
  return source.slice(first, last);
}
const KEY = 'standalone_tsr_draft_late_calibration_20_34';

function requestFor(flag, search){
  const context = { URLSearchParams, String, window:{ OFFLINE_TSR_CALIBRATION_PAGE:flag, location:{ search } } };
  vm.createContext(context);
  vm.runInContext(section(template, 'function getOnlineTSRCalibrationRequestFromUrl(){', 'function onlineTSRCalibrationReportState('), context);
  return context.getOnlineTSRCalibrationRequestFromUrl();
}

function calendarUrl(ctx){
  const context = { URLSearchParams, String };
  vm.createContext(context);
  vm.runInContext(section(timeline, 'function buildCreateTSRPageUrlFromContext(', 'function storeCreateTSRContextForPage('), context);
  return context.buildCreateTSRPageUrlFromContext(ctx);
}

async function restore({ records=[], fallback=null, account=null }){
  const applied = [];
  const localSaves = [];
  const backups = [];
  const context = {
    console:{ warn:() => {} }, Promise, Date, String, JSON, encodeURIComponent,
    navigator:{ onLine:true },
    onlineTSRCalibrationContext:{ submission_id:34 },
    standaloneCurrentDraftId:'',
    onlineTSRCalibrationReportLocked:() => false,
    getStandaloneLateCalibrationDraftId:id => `standalone_tsr_draft_late_calibration_20_${id}`,
    loadStandaloneTSRDraftRecordsFromIndexedDB:async () => records,
    loadStandaloneTSRDraftFromLocalStorageFallback:() => fallback,
    fetch:async () => ({ ok:true, json:async () => ({ status:'success', draft:account ? { calibration_report:account } : null }) }),
    collectTSRData:() => ({}),
    prepareStandaloneLateCalibrationDraft:(data, id) => Object.assign(data, { _draft_id:KEY }),
    saveStandaloneTSRDraftLocally:async data => { localSaves.push(data._draft_id); return {}; },
    showTSRStatus:() => {},
    backupLateCalibrationReportDraft:(id, report) => backups.push(report.value),
    window:{ calibrationReport:{ apply:report => applied.push(report.value) } }
  };
  vm.createContext(context);
  vm.runInContext(section(template, 'async function loadLateCalibrationReportAccountCopy(', 'async function loadOnlineTSRCalibrationFromUrl('), context);
  const candidate = await context.restoreStandaloneLateCalibrationDraft(34);
  return { source:candidate ? (candidate.source || 'indexeddb') : null, applied, localSaves, backups };
}

async function backup(online, response){
  const statuses = [];
  const context = {
    console:{ warn:() => {} }, Promise, Date, String, JSON, Number, Object, encodeURIComponent, setTimeout, clearTimeout,
    AbortController,
    navigator:{ onLine:online },
    window:{ addEventListener:() => {} },
    document:{ addEventListener:() => {}, visibilityState:'visible' },
    isOnlineTSRCalibrationMode:() => true,
    setStandaloneTSRSaveStatus:state => statuses.push(state),
    fetch:async url => {
      const body = JSON.stringify(Object.assign({ url }, response));
      return { ok:true, status:200, redirected:false, url, text:async () => body, json:async () => JSON.parse(body) };
    }
  };
  vm.createContext(context);
  vm.runInContext(section(template, 'function makeTSRSyncError(', '// navigator.onLine only knows the radio is on.'), context);
  vm.runInContext(section(template, 'let lateCalibrationBackupTimer = null;', 'async function loadLateCalibrationReportAccountCopy('), context);
  const result = await context.backupLateCalibrationReportDraft('34', { status:'draft' }, { immediate:true });
  return { url:result.url || '', statuses };
}

function enqueueSkip(id){
  const context = { String, navigator:{ onLine:true }, STANDALONE_TSR_ACCOUNT_SCOPE:'20' };
  vm.createContext(context);
  vm.runInContext(section(template, 'function enqueueStandaloneTSRServerDraftSync(', 'function readStandaloneTSRServerDraftDeleteQueue('), context);
  return context.enqueueStandaloneTSRServerDraftSync({ id, account_id:'20', payload:{} });
}

(async () => {
  const oldDevice = { id:KEY, payload:{ calibration_report:{ value:'device-old', updated_at:'2026-09-28T08:00:00Z' } } };
  const out = {
    pageRequest:requestFor(true, '?submission_id=34'),
    oldModeRequest:requestFor(undefined, '?mode=calibration_report&submission_id=34'),
    plainRequest:requestFor(undefined, '?schedule_id=878'),
    calendarReport:calendarUrl({ shift_id:878, submission_id:34, date:'2026-09-30', mode:'calibration_report' }),
    calendarTsr:calendarUrl({ shift_id:878, date:'2026-09-30' }),
    enqueueLate:enqueueSkip(KEY),
    byKey:await restore({ records:[oldDevice] }),
    accountNewer:await restore({ records:[oldDevice], account:{ value:'account-new', updated_at:'2026-10-14T01:00:00Z' } }),
    deviceNewer:await restore({ records:[oldDevice], account:{ value:'account-old', updated_at:'2026-09-01T00:00:00Z' } }),
    clearedDevice:await restore({ account:{ value:'account-only', updated_at:'2026-09-28T08:19:00Z' } }),
    backedUp:await backup(true, { status:'success' }),
    stale:await backup(true, { status:'success', stale_ignored:true }),
    offline:await backup(false, {})
  };
  console.log(JSON.stringify(out));
})().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
'''


@unittest.skipUnless(NODE.is_file(), f'Bundled Node runtime missing: {NODE}')
class CalibrationReportPageClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run(
            [str(NODE), '-e', NODE_CLIENT_SCRIPT, str(ROOT / TEMPLATE_PATH), str(ROOT / TIMELINE_PATH)],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr or result.stdout)
        cls.out = json.loads(result.stdout.strip().splitlines()[-1])

    def test_page_flag_and_old_mode_both_request_calibration_mode(self):
        self.assertEqual(self.out['pageRequest'], {'type': 'submission', 'id': '34'})
        self.assertEqual(self.out['oldModeRequest'], {'type': 'submission', 'id': '34'})
        self.assertIsNone(self.out['plainRequest'])

    def test_calendar_opens_the_report_page(self):
        self.assertEqual(self.out['calendarReport'], '/calibration-report?schedule_id=878&submission_id=34&date=2026-09-30')
        self.assertEqual(self.out['calendarTsr'], '/offline-tsr?schedule_id=878&date=2026-09-30')

    def test_existing_drafts_still_open_after_the_update(self):
        # A device draft saved before this change is found by its key.
        self.assertEqual(self.out['byKey']['applied'], ['device-old'])
        # The older account backup restores onto a cleared device and is kept there too.
        self.assertEqual(self.out['clearedDevice']['source'], 'account')
        self.assertEqual(self.out['clearedDevice']['applied'], ['account-only'])
        self.assertEqual(self.out['clearedDevice']['localSaves'], ['standalone_tsr_draft_late_calibration_20_34'])

    def test_page_load_backup_never_sends_report_drafts_to_the_tsr_backup(self):
        self.assertEqual(self.out['enqueueLate'], {'skipped': True, 'reason': 'calibration_report_own_backup'})

    def test_create_tsr_draft_panel_skips_report_drafts(self):
        source = (ROOT / TEMPLATE_PATH).read_text(encoding='utf-8')
        panel = source[source.index('async function renderStandaloneTSRDraftPanel('):source.index('let groups = groupStandaloneTSRDraftVersions(records);')]
        self.assertIn(".filter(record => !String(record?.id || '').includes('late_calibration_'))", panel)

    def test_newer_copy_wins(self):
        self.assertEqual(self.out['accountNewer']['applied'], ['account-new'])
        self.assertEqual(self.out['deviceNewer']['applied'], ['device-old'])

    def test_reopening_sends_a_device_copy_the_account_lacks(self):
        # plans.md weak-signal plan, step 7: a newer device copy is backed up on reopen.
        self.assertEqual(self.out['deviceNewer']['backups'], ['device-old'])
        self.assertEqual(self.out['byKey']['backups'], ['device-old'])
        self.assertEqual(self.out['accountNewer']['backups'], [])
        self.assertEqual(self.out['clearedDevice']['backups'], [])

    def test_backup_posts_and_reports_status(self):
        self.assertEqual(self.out['backedUp']['url'], '/save_calibration_report_draft/34')
        self.assertEqual(self.out['backedUp']['statuses'], ['backup-in-progress', 'account-backed-up'])
        self.assertEqual(self.out['stale']['statuses'], ['backup-in-progress', 'account-backup-conflict'])
        self.assertEqual(self.out['offline']['statuses'], ['local-saved-pending'])


if __name__ == '__main__':
    unittest.main()
