"""A returned Calibration Report is fixed on the same TSR, not through a new TSR revision."""
import io
import json
import os
import tempfile
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
class ReturnedCalibrationReportFixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with app_module.app.app_context():
            app_module.db.create_all()
        cls._n = 0

    @classmethod
    def _fixture(cls):
        cls._n += 1
        suffix = f'returned-fix-{os.getpid()}-{cls._n:03d}'
        with app_module.app.app_context():
            user = app_module.User(username=f'cal-{suffix}', password='test-password', role='engineer')
            app_module.db.session.add(user)
            app_module.db.session.flush()
            engineer = app_module.Engineer(user_id=user.id, employee_id=f'CAL-{suffix}', name='Returned Fix Engineer', initials='RFE')
            app_module.db.session.add(engineer)
            app_module.db.session.flush()
            shift = app_module.Shift(
                title=f'Returned fix {suffix}', start_time=datetime(2026, 8, 19, 8, 0),
                end_time=datetime(2026, 8, 19, 17, 0), engineer_id=engineer.id, status='Completed',
            )
            app_module.db.session.add(shift)
            app_module.db.session.flush()
            submission = app_module.OnlineTsrSubmission(
                shift_id=shift.id, status='completed', submission_token=f'tsr-{suffix}',
                payload_json=json.dumps({'tsr-equipment-model': 'Original Model', 'calibration_report': {'status': 'not_started'}}),
                revision_no=1, is_latest=True, submitted_by_user_id=user.id,
            )
            app_module.db.session.add(submission)
            app_module.db.session.commit()
            return user.id, submission.id, f'calibration-token-{suffix}'

    @staticmethod
    def _client(user_id):
        client = app_module.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    @staticmethod
    def _upload_data(token, fingerprint):
        report = {
            'status': 'draft',
            'facility': {'name': 'Fixed Facility' if 'fixed' in fingerprint else 'Original Facility'},
            'generated': {'attachment_id': token, 'fingerprint': fingerprint, 'filename': 'Calibration_Report.docx'},
        }
        return {
            'attachment_token': token,
            'attachment_source': 'generated_calibration_report',
            'late_calibration_report': '1',
            'calibration_report_json': json.dumps(report),
            'attachment': (io.BytesIO(b'PK-report-docx'), 'Calibration_Report.docx'),
        }

    def _upload(self, client, submission_id, token, fingerprint):
        with patch.object(app_module, 'is_admin_authorized', return_value=True), \
                patch.object(app_module, 'can_work_on_existing_schedule_shift', return_value=True), \
                patch.object(app_module, 'managed_storage_write_bytes'), \
                patch.object(app_module, 'schedule_calibration_report_conversion'), \
                patch.object(app_module, 'submit_calibration_certificate_for_submission', return_value={'ok': False, 'code': 'patched'}):
            return client.post(
                f'/upload_online_tsr_attachment/{submission_id}',
                data=self._upload_data(token, fingerprint),
                content_type='multipart/form-data',
            )

    def _add_approval(self, submission_id, user_id, status, fingerprint='original'):
        with app_module.app.app_context():
            submission = app_module.db.session.get(app_module.OnlineTsrSubmission, submission_id)
            approval = app_module.CalibrationCertificateApproval(
                shift_id=submission.shift_id, online_tsr_submission_id=submission.id,
                requester_user_id=user_id, revision_no=1, is_latest=True, status=status,
                report_fingerprint=fingerprint, certificate_number=f'2026-0819-CAL{submission_id}',
                mapped_data_json='{}', template_sha256='test-template',
                unsigned_artifact_path='test/certificate.pdf',
                return_remarks='Wrong kVp reading on row 2' if status == 'Returned' else None,
            )
            app_module.db.session.add(approval)
            app_module.db.session.commit()
            return approval.id

    def test_returned_report_can_be_replaced_on_the_same_tsr(self):
        user_id, submission_id, token = self._fixture()
        client = self._client(user_id)
        self.assertEqual(self._upload(client, submission_id, token, 'original').status_code, 200)
        self._add_approval(submission_id, user_id, 'Returned')
        with app_module.app.app_context():
            old_file_id = app_module.calibration_report_current_source_file_id(
                app_module.db.session.get(app_module.OnlineTsrSubmission, submission_id))

        fixed = self._upload(client, submission_id, f'{token}-fixed', 'fixed-report')

        self.assertEqual(fixed.status_code, 200, fixed.get_json())
        with app_module.app.app_context():
            submission = app_module.db.session.get(app_module.OnlineTsrSubmission, submission_id)
            payload = json.loads(submission.payload_json)
            self.assertEqual(submission.revision_no, 1)
            self.assertEqual(app_module.OnlineTsrSubmission.query.filter_by(shift_id=submission.shift_id).count(), 1)
            self.assertEqual(payload['tsr-equipment-model'], 'Original Model')
            self.assertEqual(payload['calibration_report']['facility']['name'], 'Fixed Facility')
            new_file_id = payload['_generated_calibration_report']['file_id']
            self.assertNotEqual(new_file_id, old_file_id)
            old_file = app_module.db.session.get(app_module.ShiftFile, old_file_id)
            new_file = app_module.db.session.get(app_module.ShiftFile, new_file_id)
            self.assertFalse(app_module.calibration_report_source_is_current(old_file, submission))
            self.assertTrue(app_module.calibration_report_source_is_current(new_file, submission))

    def test_pending_report_still_cannot_be_replaced(self):
        user_id, submission_id, token = self._fixture()
        client = self._client(user_id)
        self.assertEqual(self._upload(client, submission_id, token, 'original').status_code, 200)
        self._add_approval(submission_id, user_id, 'Pending')

        replacement = self._upload(client, submission_id, f'{token}-again', 'fixed-report')

        self.assertEqual(replacement.status_code, 409)
        self.assertEqual(replacement.get_json()['error_code'], 'calibration_report_already_uploaded')

    def _resubmit(self, submission_id):
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as template:
            template.write(b'%PDF-template')
        values = {name: 'value' for name in app_module.CALIBRATION_CERTIFICATE_FIELDS}
        values['Textfield'] = 'DIFFERENT-NUMBER'
        captured = {}

        def fake_values(payload, shift=None, certificate_number_override=None, catalog=None, **kwargs):
            captured['override'] = certificate_number_override
            report = payload.get('calibration_report') or {}
            return {**values, 'Textfield': certificate_number_override or values['Textfield']}, [], report

        try:
            with app_module.app.test_request_context(), \
                    patch.object(app_module, 'calibration_certificate_effective_catalog', return_value={}), \
                    patch.object(app_module, 'calibration_certificate_values', side_effect=fake_values), \
                    patch.object(app_module, 'calibration_certificate_catalog_errors', return_value=([], None)), \
                    patch.object(app_module, 'calibration_certificate_model_resolution', return_value={'source': 'catalog', 'value': 'Model', 'catalog_id': None}), \
                    patch.object(app_module, 'calibration_certificate_template_path', return_value=template.name), \
                    patch.object(app_module, 'build_calibration_certificate_pdf', return_value=(b'%PDF', None, 'new-certificate-fp')), \
                    patch.object(app_module, 'managed_storage_write_bytes'), \
                    patch.object(app_module, 'get_assigned_approvers_for_requester', return_value=[]):
                submission = app_module.db.session.get(app_module.OnlineTsrSubmission, submission_id)
                result = app_module.submit_calibration_certificate_for_submission(submission)
                approval = result.get('approval')
                return result, (approval.id, approval.status, approval.certificate_number, approval.report_fingerprint, approval.return_remarks), captured
        finally:
            os.unlink(template.name)

    def test_resubmit_puts_the_same_approval_back_to_pending_with_the_same_number(self):
        user_id, submission_id, token = self._fixture()
        self.assertEqual(self._upload(self._client(user_id), submission_id, token, 'fixed-report').status_code, 200)
        approval_id = self._add_approval(submission_id, user_id, 'Returned', fingerprint='original')

        result, (result_id, status, number, fingerprint, remarks), captured = self._resubmit(submission_id)

        self.assertTrue(result['ok'])
        self.assertTrue(result.get('resubmitted'))
        self.assertEqual(result_id, approval_id)
        self.assertEqual(status, 'Pending')
        self.assertEqual(number, f'2026-0819-CAL{submission_id}')
        self.assertEqual(captured['override'], number)
        self.assertEqual(fingerprint, 'fixed-report')
        self.assertIsNone(remarks)
        with app_module.app.app_context():
            self.assertEqual(app_module.CalibrationCertificateApproval.query.filter_by(online_tsr_submission_id=submission_id).count(), 1)
            audit = app_module.UniversalApprovalAuditTrail.query.filter_by(
                module='calibration_certificate', record_id=approval_id, action='resubmitted').first()
            self.assertIsNotNone(audit)
            self.assertEqual((audit.status_from, audit.status_to), ('Returned', 'Pending'))

    def test_unchanged_returned_report_is_not_resubmitted(self):
        user_id, submission_id, token = self._fixture()
        self.assertEqual(self._upload(self._client(user_id), submission_id, token, 'same-report').status_code, 200)
        self._add_approval(submission_id, user_id, 'Returned', fingerprint='same-report')

        result, (_id, status, *_rest), _captured = self._resubmit(submission_id)

        self.assertTrue(result['duplicate'])
        self.assertEqual(status, 'Returned')

    def test_return_notification_opens_report_only_mode(self):
        user_id, submission_id, _token = self._fixture()
        approval_id = self._add_approval(submission_id, user_id, 'Pending')
        client = self._client(user_id)
        with patch.object(app_module, 'calibration_certificate_approver_can_act', return_value=True):
            response = client.post(f'/api/calibration-certificates/{approval_id}/return', json={'remarks': 'Fix row 2'})
        self.assertEqual(response.status_code, 200, response.get_json())
        with app_module.app.app_context():
            note = app_module.SystemNotification.query.filter_by(
                module='calibration_certificate', record_id=approval_id, user_id=user_id,
            ).order_by(app_module.SystemNotification.id.desc()).first()
            self.assertIn('mode=calibration_report', note.target_url)
            self.assertIn(f'submission_id={submission_id}', note.target_url)
            self.assertNotIn('mode=correct', note.target_url)
            state = app_module.calibration_report_timeline_state_for_submission(
                app_module.db.session.get(app_module.OnlineTsrSubmission, submission_id))
            self.assertTrue(state['returned'])
            self.assertEqual(state['return_remarks'], 'Fix row 2')

    def test_pages_show_the_returned_report(self):
        timeline = (ROOT / 'templates' / 'timeline.html').read_text(encoding='utf-8')
        offline = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')
        script = (ROOT / 'static' / 'js' / 'app-calibration-report.js').read_text(encoding='utf-8')
        self.assertIn("if(shift?.calibration_report_returned) return 'Fix Calibration Report';", timeline)
        self.assertEqual(timeline.count('${calibrationReportReturnedAttrs('), 6)
        self.assertIn('button[data-calibration-returned="true"]', timeline)
        self.assertIn('id="calibration-report-returned-banner"', offline)
        self.assertIn('function onlineTSRCalibrationReportLocked()', offline)
        self.assertIn("var locked = uploaded && !returned;", script)
        self.assertIn("window.setOnlineTSRCalibrationReportReadOnly(locked);", script)


if __name__ == '__main__':
    unittest.main()
