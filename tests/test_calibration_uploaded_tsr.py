"""A schedule whose TSR was uploaded (not system-made) can still take a Calibration Report."""
import io
import json
import os
import unittest
from datetime import datetime
from pathlib import Path
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
class UploadedTSRCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app_module.app.config['WTF_CSRF_ENABLED'] = False
        with app_module.app.app_context():
            app_module.db.create_all()
        cls._n = 0

    @classmethod
    def _fixture(cls, with_system_tsr=False):
        cls._n += 1
        suffix = f'uploaded-tsr-{os.getpid()}-{cls._n:03d}'
        with app_module.app.app_context():
            user = app_module.User(username=f'cal-{suffix}', password='test-password', role='engineer')
            app_module.db.session.add(user)
            app_module.db.session.flush()
            engineer = app_module.Engineer(user_id=user.id, employee_id=f'UPL-{suffix}', name='Uploaded TSR Engineer', initials='UTE')
            app_module.db.session.add(engineer)
            app_module.db.session.flush()
            shift = app_module.Shift(
                title=f'Uploaded TSR {suffix}', start_time=datetime(2026, 10, 19, 8, 0),
                end_time=datetime(2026, 10, 19, 17, 0), engineer_id=engineer.id, status='Completed',
            )
            app_module.db.session.add(shift)
            app_module.db.session.flush()
            if with_system_tsr:
                app_module.db.session.add(app_module.OnlineTsrSubmission(
                    shift_id=shift.id, status='completed', submission_token=f'tsr-{suffix}',
                    payload_json='{}', revision_no=1, is_latest=True, submitted_by_user_id=user.id,
                ))
            app_module.db.session.commit()
            return user.id, shift.id, suffix

    @staticmethod
    def _client(user_id):
        client = app_module.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def _create(self, client, shift_id, tsr_number, has_tsr_file=True):
        with patch.object(app_module, 'can_work_on_existing_schedule_shift', return_value=True), \
                patch.object(app_module, 'shift_has_tsr_file', return_value=has_tsr_file):
            return client.post(f'/calibration-report/uploaded-tsr/{shift_id}', json={'tsr_number': tsr_number})

    def test_creates_one_light_record_and_reuses_it(self):
        user_id, shift_id, suffix = self._fixture()
        client = self._client(user_id)
        first = self._create(client, shift_id, f'MAN-{suffix}')
        self.assertEqual(first.status_code, 200, first.get_json())
        second = self._create(client, shift_id, 'ignored')
        self.assertEqual(second.get_json()['submission_id'], first.get_json()['submission_id'])
        with app_module.app.app_context():
            submission = app_module.db.session.get(app_module.OnlineTsrSubmission, first.get_json()['submission_id'])
            payload = json.loads(submission.payload_json)
            self.assertEqual(submission.status, 'completed')
            self.assertEqual(submission.tsr_number, f'MAN-{suffix}')
            self.assertTrue(payload['_uploaded_tsr_carrier'])
            self.assertEqual(payload['tsr-number'], f'MAN-{suffix}')
            self.assertNotIn('_attached_file_id', payload)
            self.assertNotIn('_tsr_form_version', payload)

    def test_refuses_without_uploaded_tsr_blank_number_or_system_tsr(self):
        user_id, shift_id, suffix = self._fixture()
        client = self._client(user_id)
        self.assertEqual(self._create(client, shift_id, f'MAN-{suffix}', has_tsr_file=False).status_code, 409)
        self.assertEqual(self._create(client, shift_id, '  ').status_code, 400)
        other_user, other_shift, _ = self._fixture(with_system_tsr=True)
        self.assertEqual(self._create(self._client(other_user), other_shift, f'MAN2-{suffix}').status_code, 409)

    def test_refuses_a_tsr_number_used_by_another_tsr(self):
        user_id, shift_id, suffix = self._fixture()
        self.assertEqual(self._create(self._client(user_id), shift_id, f'DUP-{suffix}').status_code, 200)
        other_user, other_shift, _ = self._fixture()
        taken = self._create(self._client(other_user), other_shift, f'dup-{suffix}')
        self.assertEqual(taken.status_code, 409)
        self.assertIn('already used', taken.get_json()['message'])

    def test_refuses_another_engineers_schedule(self):
        _user_id, shift_id, suffix = self._fixture()
        other_user, _other_shift, _ = self._fixture()
        with patch.object(app_module, 'can_work_on_existing_schedule_shift', return_value=False):
            response = self._client(other_user).post(f'/calibration-report/uploaded-tsr/{shift_id}', json={'tsr_number': f'X-{suffix}'})
        self.assertEqual(response.status_code, 403)

    def test_late_report_uploads_to_the_light_record(self):
        user_id, shift_id, suffix = self._fixture()
        client = self._client(user_id)
        submission_id = self._create(client, shift_id, f'UP-{suffix}').get_json()['submission_id']
        token = f'calibration-token-{suffix}'
        report = {'status': 'draft', 'facility': {'name': 'Clinic'},
                  'generated': {'attachment_id': token, 'fingerprint': 'fp', 'filename': 'Calibration_Report.docx'}}
        with patch.object(app_module, 'can_work_on_existing_schedule_shift', return_value=True), \
                patch.object(app_module, 'managed_storage_write_bytes'), \
                patch.object(app_module, 'schedule_calibration_report_conversion'), \
                patch.object(app_module, 'submit_calibration_certificate_for_submission', return_value={'ok': False, 'code': 'patched'}) as submit:
            response = client.post(f'/upload_online_tsr_attachment/{submission_id}', data={
                'attachment_token': token,
                'attachment_source': 'generated_calibration_report',
                'late_calibration_report': '1',
                'calibration_report_json': json.dumps(report),
                'attachment': (io.BytesIO(b'PK-report-docx'), 'Calibration_Report.docx'),
            }, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertTrue(submit.called)
        with app_module.app.app_context():
            payload = json.loads(app_module.db.session.get(app_module.OnlineTsrSubmission, submission_id).payload_json)
            self.assertEqual(payload['calibration_report']['facility']['name'], 'Clinic')
            self.assertEqual(payload['tsr-number'], f'UP-{suffix}')

    def test_light_record_cannot_be_revised(self):
        user_id, shift_id, suffix = self._fixture()
        client = self._client(user_id)
        submission_id = self._create(client, shift_id, f'REV-{suffix}').get_json()['submission_id']
        with patch.object(app_module, 'can_work_on_existing_schedule_shift', return_value=True):
            response = client.post(f'/revise_online_tsr_submission/{submission_id}', json={'revision_reason': 'x'})
        self.assertEqual(response.status_code, 409, response.get_json())

    def test_pages_route_uploaded_tsr_schedules_and_carry_over_the_report(self):
        timeline = (ROOT / 'templates' / 'timeline.html').read_text(encoding='utf-8')
        offline = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')
        self.assertIn("}else if(isScheduleCompleted(shift)){\n        // Completed with an uploaded", timeline)
        self.assertIn('/calibration-report/uploaded-tsr/${encodeURIComponent(shift.id)}', timeline)
        self.assertIn("uploaded_tsr_carrier: payload._uploaded_tsr_carrier === true", offline)
        self.assertIn("String(record?.payload?.schedule_id || '') === shiftId", offline)
        self.assertIn("if(candidate.source === 'schedule_draft'){", offline)


if __name__ == '__main__':
    unittest.main()
