"""Save Final Report tells the engineer whether the certificate reached an approver (plans.md, 2026-10-15)."""
import io
import json
import os
import subprocess
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

try:
    import app as app_module
except ModuleNotFoundError as import_error:  # pragma: no cover
    app_module = None
    APP_IMPORT_ERROR = import_error
else:
    APP_IMPORT_ERROR = None

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
class LateUploadCertificateFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with app_module.app.app_context():
            app_module.db.create_all()
        cls._n = 0

    @classmethod
    def _fixture(cls, with_approval=False):
        cls._n += 1
        suffix = f'late-fb-{os.getpid()}-{cls._n:03d}'
        token = f'calibration-late-feedback-{os.getpid()}-{cls._n:03d}'
        with app_module.app.app_context():
            user = app_module.User(username=f'user-{suffix}', password='test-password', role='engineer')
            app_module.db.session.add(user)
            app_module.db.session.flush()
            engineer = app_module.Engineer(user_id=user.id, employee_id=f'LF-{suffix}', name='Late Feedback Engineer', initials='LFE')
            app_module.db.session.add(engineer)
            app_module.db.session.flush()
            shift = app_module.Shift(
                title=f'Late feedback {suffix}', start_time=datetime(2026, 10, 15, 8, 0),
                end_time=datetime(2026, 10, 15, 17, 0), engineer_id=engineer.id, status='Completed',
            )
            app_module.db.session.add(shift)
            app_module.db.session.flush()
            submission = app_module.OnlineTsrSubmission(
                shift_id=shift.id, status='completed', submission_token=f'tsr-{suffix}',
                payload_json=json.dumps({'calibration_report': {'status': 'not_started'}}),
                revision_no=1, is_latest=True, submitted_by_user_id=user.id,
            )
            app_module.db.session.add(submission)
            app_module.db.session.flush()
            approval_id = None
            if with_approval:
                approval = app_module.CalibrationCertificateApproval(
                    shift_id=shift.id, online_tsr_submission_id=submission.id,
                    requester_user_id=user.id, revision_no=1, is_latest=True, status='Pending',
                    certificate_number=f'CERT-{suffix}', mapped_data_json='{}',
                    template_sha256='test', unsigned_artifact_path='test.pdf',
                )
                app_module.db.session.add(approval)
                app_module.db.session.flush()
                approval_id = approval.id
            app_module.db.session.commit()
            return user.id, submission.id, token, approval_id

    @staticmethod
    def _client(user_id):
        client = app_module.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def _upload(self, client, submission_id, token):
        report = {'status': 'draft', 'generated': {'attachment_id': token, 'fingerprint': f'fp-{token}', 'filename': 'Calibration_Report.docx'}}
        return client.post(f'/upload_online_tsr_attachment/{submission_id}', content_type='multipart/form-data', data={
            'attachment_token': token, 'attachment_source': 'generated_calibration_report',
            'late_calibration_report': '1', 'calibration_report_json': json.dumps(report),
            'attachment': (io.BytesIO(b'late-docx'), 'Calibration_Report.docx'),
        })

    def _run(self, submit_result, approvers, uploads=1):
        user_id, submission_id, token, approval_id = self._fixture(with_approval=submit_result == 'approval')
        client = self._client(user_id)

        def submit(_submission):
            if submit_result == 'approval':
                return {'ok': True, 'approval': app_module.db.session.get(app_module.CalibrationCertificateApproval, approval_id)}
            return submit_result

        with patch.object(app_module, 'can_work_on_existing_schedule_shift', return_value=True), \
                patch.object(app_module, 'managed_storage_write_bytes'), \
                patch.object(app_module, 'schedule_calibration_report_conversion'), \
                patch.object(app_module, 'get_assigned_approvers_for_requester', return_value=approvers), \
                patch.object(app_module, 'submit_calibration_certificate_for_submission', side_effect=submit):
            responses = [self._upload(client, submission_id, token) for _ in range(uploads)]
        for response in responses:
            self.assertEqual(response.status_code, 200, response.get_json())
        return [response.get_json()['certificate'] for response in responses]

    def test_failure_reason_is_returned_on_new_upload_and_retry(self):
        failure = {'ok': False, 'code': 'catalog_validation', 'message': 'Select an exact catalog Equipment Model.'}
        first, retry = self._run(failure, approvers=[SimpleNamespace(id=1)], uploads=2)
        for certificate in (first, retry):
            self.assertEqual(certificate['status'], 'catalog_validation')
            self.assertEqual(certificate['message'], 'Select an exact catalog Equipment Model.')

    def test_pending_without_approver_is_awaiting_route(self):
        (certificate,) = self._run('approval', approvers=[])
        self.assertEqual(certificate['status'], 'awaiting_route')

    def test_pending_with_approver_stays_pending(self):
        (certificate,) = self._run('approval', approvers=[SimpleNamespace(id=1)])
        self.assertEqual(certificate['status'], 'Pending')


class LateUploadMessageSourceTests(unittest.TestCase):
    def test_save_final_report_reports_the_certificate_result(self):
        source = (ROOT / 'static' / 'js' / 'app-calibration-report.js').read_text(encoding='utf-8')
        self.assertFalse("showStatus('Calibration Report uploaded to the existing TSR. No new TSR revision was created.', 'success')" in source)
        self.assertIn('Calibration Report uploaded and sent to the approver.', source)
        self.assertIn('Calibration Report uploaded, but no approver is assigned to you. Contact admin.', source)
        self.assertIn('Calibration Report uploaded, but the certificate was not sent: ', source)
        self.assertIn("'/calibration-center'", source)
        self.assertIn("'Certificate not sent: '", source)


NODE = Path(r'C:\Users\Jonamar\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe')

# Loads the real calibration script with fake timers and a scripted late-upload handler.
NODE_RETRY_SCRIPT = r'''
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const script = fs.readFileSync(path.join(process.cwd(), 'static', 'js', 'app-calibration-report.js'), 'utf8');

function load(uploadResults){
  const statuses = [];
  const timers = [];
  const listeners = {};
  let uploads = 0;
  const context = {
    console, Blob, Uint8Array, ArrayBuffer, Promise, Date, Math, JSON, atob, btoa,
    setTimeout:(fn, delay) => { timers.push({ fn, delay }); return timers.length; },
    clearTimeout:id => { if(timers[id - 1]) timers[id - 1].cleared = true; },
    URL:{ createObjectURL:() => 'blob:test', revokeObjectURL:() => {} },
    CalibrationReportConfig:{},
    document:{ querySelector:() => null, querySelectorAll:() => [], createElement:() => ({}), addEventListener:() => {} },
    addEventListener:(name, fn) => { (listeners[name] ||= []).push(fn); },
    showTSRStatus:(message, tone) => statuses.push({ message:String(message || ''), tone }),
    collectTSRData:() => ({}),
    saveStandaloneCalibrationReport:async () => uploadResults[uploads++],
  };
  context.window = context; context.self = context; context.globalThis = context;
  vm.createContext(context);
  vm.runInContext(script, context);
  const pending = () => timers.filter(timer => !timer.cleared && !timer.ran);
  const runNext = async () => { const timer = pending()[0]; timer.ran = true; await timer.fn(); };
  return { api:context.calibrationReport, statuses, pending, runNext, listeners, uploads:() => uploads };
}

(async () => {
  const out = {};
  const describe = load([]).api.describeUploadFailure;
  out.mapping = {
    timeout: describe({ upload_error_code:'timeout' }),
    network: describe({ upload_error_code:'network_error' }),
    offline: describe({ upload_error_code:'offline' }),
    session: describe({ upload_error_code:'session_expired', requires_login:true }),
    http401: describe({ upload_error_code:'http_401' }),
    http503: describe({ upload_error_code:'http_503', upload_error:'Service unavailable.', retryable:true }),
    http400: describe({ upload_error_code:'http_400', upload_error:'The final Calibration Report payload is invalid.' }),
  };

  const timeout = { status:'local_saved', local_saved:true, upload_error_code:'timeout', retryable:true };
  const success = { status:'success', success:true, certificate:{ status:'Pending' } };
  const flow = load([timeout, success]);
  flow.api.scheduleLateUploadRetry();
  out.delays = [flow.pending()[0].delay];
  await flow.runNext();
  out.delays.push(flow.pending()[0].delay);
  await flow.runNext();
  out.retryUploads = flow.uploads();
  out.timersAfterSuccess = flow.pending().length;
  out.retryStatuses = flow.statuses.map(item => item.message);

  const online = load([success]);
  online.api.scheduleLateUploadRetry();
  (online.listeners.online || []).forEach(fn => fn());
  out.onlineDelay = online.pending().map(timer => timer.delay);

  const expired = load([{ status:'local_saved', local_saved:true, upload_error_code:'session_expired', requires_login:true }]);
  expired.api.scheduleLateUploadRetry({ immediate:true });
  await expired.runNext();
  out.timersAfterExpired = expired.pending().length;
  console.log(JSON.stringify(out));
})().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
'''


class LateUploadRetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run([str(NODE), '-e', NODE_RETRY_SCRIPT], cwd=ROOT, text=True, encoding='utf-8', capture_output=True, check=False)
        cls.error = result.stderr or result.stdout if result.returncode else ''
        cls.out = json.loads(result.stdout.strip().splitlines()[-1]) if not result.returncode else {}

    def setUp(self):
        self.assertFalse(self.error, self.error[-2000:])

    def test_each_failure_has_a_real_reason_and_retry_flag(self):
        mapping = self.out['mapping']
        self.assertEqual(mapping['timeout'], {'reason': 'The upload timed out — the connection is too weak or slow.', 'autoRetry': True})
        self.assertEqual(mapping['network'], {'reason': 'The connection dropped during the upload.', 'autoRetry': True})
        self.assertTrue(mapping['offline']['autoRetry'])
        for key in ('session', 'http401'):
            self.assertEqual(mapping[key], {'reason': 'Your session expired. Sign in again, then press Save Final Report.', 'autoRetry': False})
        self.assertEqual(mapping['http503'], {'reason': 'The server could not take the upload: Service unavailable.', 'autoRetry': True})
        self.assertEqual(mapping['http400'], {'reason': 'The final Calibration Report payload is invalid.', 'autoRetry': False})

    def test_retry_backs_off_then_stops_on_success(self):
        self.assertEqual(self.out['delays'], [30000, 60000])
        self.assertEqual(self.out['retryUploads'], 2)
        self.assertEqual(self.out['timersAfterSuccess'], 0)
        self.assertIn('Calibration Report uploaded and sent to the approver.', self.out['retryStatuses'])
        self.assertTrue(any('It will upload automatically when the connection is back.' in item for item in self.out['retryStatuses']))

    def test_back_online_retries_at_once(self):
        self.assertEqual(self.out['onlineDelay'], [0])

    def test_expired_session_does_not_retry(self):
        self.assertEqual(self.out['timersAfterExpired'], 0)


class LateUploadRetrySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = (ROOT / 'static' / 'js' / 'app-calibration-report.js').read_text(encoding='utf-8')
        cls.template = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')

    def test_when_you_are_online_text_is_gone(self):
        self.assertFalse('Retry Save Final Report when you are online.' in self.script)

    def test_upload_keeps_failure_details_and_scales_timeout(self):
        upload = self.template.split('async function saveStandaloneCalibrationReport(', 1)[1].split('\nasync function ', 1)[0]
        self.assertIn('_late_calibration_report_upload_failed = true', upload)
        self.assertIn('upload_error_code', upload)
        self.assertIn('Math.ceil(Number(blob.size || 0) / 20480) * 1000', upload)
        self.assertFalse("timeoutMs:120000 }" in upload)

    def test_reopen_resumes_retry(self):
        restore = self.template.split('async function restoreStandaloneLateCalibrationDraft(', 1)[1].split('\nasync function ', 1)[0]
        self.assertIn('_late_calibration_report_upload_failed', restore)
        self.assertIn('scheduleLateUploadRetry({ immediate:true })', restore)

    def test_save_and_retry_share_the_success_handling(self):
        save = self.script.split('async function saveFinalReport(){', 1)[1].split('  async function download(){', 1)[0]
        self.assertIn('finishLateUpload(lateResult)', save)
        self.assertIn('finishLateUpload(result)', self.script.split('async function runLateUploadRetry(){', 1)[1][:2500])


if __name__ == '__main__':
    unittest.main()
