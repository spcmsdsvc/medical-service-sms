import json
import inspect
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

try:
    import app as app_module
except ModuleNotFoundError as import_error:  # pragma: no cover
    app_module = None
    APP_IMPORT_ERROR = import_error
else:
    APP_IMPORT_ERROR = None


@unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
class TsrSyncReliabilityTests(unittest.TestCase):
    def test_submission_token_normalization(self):
        self.assertEqual(
            app_module.normalize_online_tsr_submission_token('tsr-1234_5678-safe'),
            'tsr-1234_5678-safe',
        )
        self.assertEqual(app_module.normalize_online_tsr_submission_token('short'), '')
        self.assertNotIn(
            '/',
            app_module.normalize_online_tsr_submission_token('tsr-1234/5678/unsafe'),
        )

    @classmethod
    def setUpClass(cls):
        with app_module.app.app_context():
            app_module.db.create_all()
        cls._fixture_number = 0

    @classmethod
    def _make_upload_fixture(cls, persisted_filename, cross_submission=False):
        cls._fixture_number += 1
        suffix = f'{cls._fixture_number:03d}'
        token = f'calibration-report-token-{suffix}'
        with app_module.app.app_context():
            user = app_module.User(
                username=f'calibration-route-user-{suffix}',
                password='test-password',
                role='engineer',
            )
            app_module.db.session.add(user)
            app_module.db.session.flush()
            engineer = app_module.Engineer(
                user_id=user.id,
                employee_id=f'CAL-ROUTE-{suffix}',
                name='Calibration Route Engineer',
                initials='CRE',
            )
            app_module.db.session.add(engineer)
            app_module.db.session.flush()
            shift = app_module.Shift(
                title=f'Calibration route fixture {suffix}',
                start_time=datetime(2026, 8, 19, 8, 0),
                end_time=datetime(2026, 8, 19, 17, 0),
                engineer_id=engineer.id,
                status='Completed',
            )
            app_module.db.session.add(shift)
            app_module.db.session.flush()
            payload = {
                'calibration_report': {
                    'status': 'draft',
                    'generated': {
                        'attachment_id': token,
                        'fingerprint': f'fixture-fingerprint-{suffix}',
                    },
                }
            }
            submission = app_module.OnlineTsrSubmission(
                shift_id=shift.id,
                status='completed',
                submission_token=f'tsr-route-{suffix}',
                payload_json=json.dumps(payload),
                revision_no=1,
                is_latest=True,
            )
            app_module.db.session.add(submission)
            app_module.db.session.flush()
            file_owner_id = submission.id
            if cross_submission:
                other_submission = app_module.OnlineTsrSubmission(
                    shift_id=shift.id,
                    status='completed',
                    submission_token=f'tsr-route-other-{suffix}',
                    payload_json=json.dumps({'calibration_report': {}}),
                    revision_no=1,
                    is_latest=False,
                )
                app_module.db.session.add(other_submission)
                app_module.db.session.flush()
                file_owner_id = other_submission.id
            file_rec = app_module.ShiftFile(
                shift_id=shift.id,
                filename=f'stored-{suffix}.bin',
                original_filename=persisted_filename,
                upload_token=token,
                online_tsr_submission_id=file_owner_id,
            )
            app_module.db.session.add(file_rec)
            app_module.db.session.commit()
            return user.id, submission.id, file_rec.id, token

    @staticmethod
    def _logged_in_client(user_id):
        client = app_module.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def test_duplicate_generated_report_rejects_persisted_non_docx_before_reclassification(self):
        user_id, submission_id, file_id, token = self._make_upload_fixture('Calibration Report.pdf')
        client = self._logged_in_client(user_id)
        with patch.object(app_module, 'is_admin_authorized', return_value=True), \
                patch.object(app_module, 'can_work_on_existing_schedule_shift', return_value=True):
            response = client.post(
                f'/upload_online_tsr_attachment/{submission_id}',
                data={'attachment_token': token, 'attachment_source': 'generated_calibration_report'},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn('must be DOCX', response.get_json()['message'])
        with app_module.app.app_context():
            submission = app_module.db.session.get(app_module.OnlineTsrSubmission, submission_id)
            file_rec = app_module.db.session.get(app_module.ShiftFile, file_id)
            generated = json.loads(submission.payload_json)['calibration_report']['generated']
            self.assertNotIn('source', generated)
            self.assertNotIn('file_id', generated)
            self.assertEqual(file_rec.original_filename, 'Calibration Report.pdf')

    def test_duplicate_generated_report_docx_retry_is_idempotent_and_reclassifies_once(self):
        user_id, submission_id, file_id, token = self._make_upload_fixture('Calibration Report.DOCX')
        client = self._logged_in_client(user_id)
        with patch.object(app_module, 'is_admin_authorized', return_value=True), \
                patch.object(app_module, 'can_work_on_existing_schedule_shift', return_value=True):
            first = client.post(
                f'/upload_online_tsr_attachment/{submission_id}',
                data={'attachment_token': token, 'attachment_source': 'generated_calibration_report'},
            )
            second = client.post(
                f'/upload_online_tsr_attachment/{submission_id}',
                data={'attachment_token': token, 'attachment_source': 'generated_calibration_report'},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(first.get_json()['duplicate'])
        self.assertTrue(second.get_json()['duplicate'])
        self.assertEqual(first.get_json()['file_id'], file_id)
        self.assertEqual(second.get_json()['file_id'], file_id)
        with app_module.app.app_context():
            submission = app_module.db.session.get(app_module.OnlineTsrSubmission, submission_id)
            generated = json.loads(submission.payload_json)['calibration_report']['generated']
            self.assertEqual(generated['source'], 'generated_calibration_report')
            self.assertEqual(generated['file_id'], file_id)

    def test_duplicate_generated_report_token_owned_by_another_submission_remains_refused(self):
        user_id, submission_id, _file_id, token = self._make_upload_fixture('Calibration Report.docx', cross_submission=True)
        client = self._logged_in_client(user_id)
        with patch.object(app_module, 'is_admin_authorized', return_value=True), \
                patch.object(app_module, 'can_work_on_existing_schedule_shift', return_value=True):
            response = client.post(
                f'/upload_online_tsr_attachment/{submission_id}',
                data={'attachment_token': token, 'attachment_source': 'generated_calibration_report'},
            )

        self.assertEqual(response.status_code, 409)
        self.assertIn('another TSR', response.get_json()['message'])
        with app_module.app.app_context():
            submission = app_module.db.session.get(app_module.OnlineTsrSubmission, submission_id)
            generated = json.loads(submission.payload_json)['calibration_report']['generated']
            self.assertNotIn('source', generated)

    def test_completed_retry_returns_existing_submission(self):
        submission = SimpleNamespace(
            id=41,
            shift_id=17,
            tsr_number='20260714-01-JD',
            submission_token='tsr-existing-token-123',
            revision_no=1,
            parent_submission_id=None,
        )
        attached_file = SimpleNamespace(id=90, filename='stored.pdf')
        payload = {
            '_attached_file_id': 90,
            '_attached_display_filename': 'TSR_existing.pdf',
            '_completed_shift_ids': [17],
            '_completion_scope': 'current_day',
            '_pdf_source': 'frontend_blob',
        }
        with patch.object(app_module, 'parse_online_tsr_payload_json', return_value=payload), \
             patch.object(app_module.db.session, 'get', return_value=attached_file), \
             patch.object(app_module, 'get_shift_file_display_name', return_value='TSR_existing.pdf'):
            result = app_module.completed_online_tsr_response(submission, duplicate=True)

        self.assertTrue(result['success'])
        self.assertTrue(result['duplicate'])
        self.assertEqual(result['submission_id'], 41)
        self.assertEqual(result['attached_file_id'], 90)
        self.assertEqual(result['completed_shift_ids'], [17])

    def test_core_save_rolls_back_instead_of_committing_pdf_error(self):
        source = inspect.getsource(app_module.save_offline_tsr_online)
        self.assertIn('db.session.rollback()', source)
        self.assertNotIn("submission.status = 'pdf_error'", source)
        self.assertIn('submission_token=submission_token', source)

    def test_supporting_attachment_limits_are_explicit(self):
        self.assertEqual(app_module.TSR_SUPPORTING_ATTACHMENT_MAX_COUNT, 10)
        self.assertEqual(app_module.TSR_SUPPORTING_ATTACHMENT_MAX_BYTES, 35 * 1024 * 1024)

    def test_generated_calibration_report_source_has_a_narrow_server_allowlist(self):
        source = inspect.getsource(app_module.upload_online_tsr_attachment)
        self.assertIn("'generated_calibration_report'", source)
        self.assertIn('Unsupported TSR attachment source.', source)
        self.assertIn('Generated Calibration Report attachments must be DOCX files.', source)


if __name__ == '__main__':
    unittest.main()
