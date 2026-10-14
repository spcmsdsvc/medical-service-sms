"""My Calibrations: the engineer's own calibration reports (plans.md, 2026-10-13)."""
import json
import os
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
MARKER = '_calibration_submit_failure'


def _submission(payload):
    return SimpleNamespace(id=1, payload_json=json.dumps(payload))


def _approval(status, returned_at=None, is_latest=True):
    return SimpleNamespace(status=status, is_latest=is_latest, returned_at=returned_at, return_remarks='Fix row 2')


@unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
class MyCalibrationStatusTests(unittest.TestCase):
    def status(self, payload, approval, has_approver=True, sent=False):
        with app_module.app.app_context(), \
                patch.object(app_module, '_my_calibration_sent', return_value=sent):
            return app_module.my_calibration_status(_submission(payload), approval, has_approver=has_approver)

    def test_each_status_rule(self):
        failure = {MARKER: {'code': 'missing_values', 'message': 'Missing values: Model', 'at': '2026-10-13T09:00:00+00:00'}}
        self.assertEqual(self.status({}, None)['key'], 'draft')
        self.assertEqual(self.status(failure, None), {'key': 'failed', 'label': 'Failed to send', 'reason': 'Missing values: Model'})
        self.assertEqual(self.status({}, _approval('Pending'))['key'], 'pending')
        no_approver = self.status({}, _approval('Pending'), has_approver=False)
        self.assertEqual((no_approver['key'], no_approver['reason']), ('failed', app_module.MY_CALIBRATION_NO_APPROVER_REASON))
        self.assertEqual(self.status({}, _approval('Returned')), {'key': 'returned', 'label': 'Returned', 'reason': 'Fix row 2'})
        self.assertEqual(self.status({}, _approval('Approved'))['key'], 'approved')
        self.assertEqual(self.status({}, _approval('Approved'), sent=True)['label'], 'Sent to client')
        self.assertEqual(self.status({}, _approval('Superseded'))['key'], 'draft')
        self.assertEqual(self.status({}, _approval('Pending', is_latest=False))['key'], 'draft')

    def test_returned_shows_failed_only_when_failure_is_newer(self):
        failure = {MARKER: {'code': 'unexpected', 'message': 'x', 'at': '2026-10-13T09:00:00+00:00'}}
        older = _approval('Returned', returned_at=datetime(2026, 10, 13, 10, 0))
        newer = _approval('Returned', returned_at=datetime(2026, 10, 13, 8, 0))
        self.assertEqual(self.status(failure, older)['key'], 'returned')
        self.assertEqual(self.status(failure, newer)['key'], 'failed')


@unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
class MyCalibrationRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with app_module.app.app_context():
            app_module.db.create_all()
        cls._n = 0

    @classmethod
    def _fixture(cls, approval_status=None, payload_extra=None):
        cls._n += 1
        suffix = f'my-cal-{os.getpid()}-{cls._n:03d}'
        with app_module.app.app_context():
            user = app_module.User(username=f'mycal-{suffix}', password='test-password', role='engineer')
            app_module.db.session.add(user)
            app_module.db.session.flush()
            engineer = app_module.Engineer(user_id=user.id, employee_id=f'MC-{suffix}', name='My Cal Engineer', initials='MCE')
            app_module.db.session.add(engineer)
            app_module.db.session.flush()
            shift = app_module.Shift(
                title=f'My cal {suffix}', start_time=datetime(2026, 10, 13, 8, 0),
                end_time=datetime(2026, 10, 13, 17, 0), engineer_id=engineer.id, status='Completed',
            )
            app_module.db.session.add(shift)
            app_module.db.session.flush()
            payload = {'_generated_calibration_report': {'file_id': 999999}}
            payload.update(payload_extra or {})
            submission = app_module.OnlineTsrSubmission(
                shift_id=shift.id, status='completed', submission_token=f'tsr-{suffix}',
                payload_json=json.dumps(payload), client_name=f'Client {suffix}',
                revision_no=1, is_latest=True, submitted_by_user_id=user.id,
            )
            app_module.db.session.add(submission)
            app_module.db.session.flush()
            approval_id = None
            if approval_status:
                approval = app_module.CalibrationCertificateApproval(
                    shift_id=shift.id, online_tsr_submission_id=submission.id,
                    requester_user_id=user.id, revision_no=1, is_latest=True, status=approval_status,
                    certificate_number=f'CERT-{suffix}', mapped_data_json='{}',
                    template_sha256='test', unsigned_artifact_path='test.pdf',
                )
                app_module.db.session.add(approval)
                app_module.db.session.flush()
                approval_id = approval.id
            app_module.db.session.commit()
            return user.id, submission.id, approval_id, f'Client {suffix}'

    @staticmethod
    def _client(user_id):
        client = app_module.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def _payload(self, submission_id):
        with app_module.app.app_context():
            return app_module.parse_online_tsr_payload_json(
                app_module.db.session.get(app_module.OnlineTsrSubmission, submission_id))

    def _submit(self, user_id, submission_id, **submit_patch):
        with patch.object(app_module, 'can_work_on_existing_schedule_shift', return_value=True), \
                patch.object(app_module, 'submit_calibration_certificate_for_submission', **submit_patch):
            try:
                return self._client(user_id).post(f'/api/calibration-certificates/submit/{submission_id}')
            except RuntimeError:
                return None

    def test_failed_submit_is_recorded_and_cleared(self):
        user_id, submission_id, _, _ = self._fixture()
        response = self._submit(user_id, submission_id, return_value={'ok': False, 'code': 'missing_values', 'message': 'Model'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._payload(submission_id)[MARKER]['message'], 'Missing values: Model')

        self._submit(user_id, submission_id, side_effect=RuntimeError('boom'))
        marker = self._payload(submission_id)[MARKER]
        self.assertEqual(marker['code'], 'unexpected')
        self.assertNotIn('boom', marker['message'])

        with app_module.app.app_context():
            submission = app_module.db.session.get(app_module.OnlineTsrSubmission, submission_id)
            app_module.clear_calibration_submit_failure(submission)
            app_module.db.session.commit()
        self.assertNotIn(MARKER, self._payload(submission_id))

    def test_success_paths_clear_the_marker_before_commit(self):
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        start = source.index('def submit_calibration_certificate_for_submission(')
        body = source[start:source.index('\ndef calibration_certificate_requester_can_view(', start)]
        self.assertEqual(body.count('clear_calibration_submit_failure(submission)\n'), 2)

    def test_data_lists_only_own_reports(self):
        user_a, _, _, client_a = self._fixture('Pending')
        _, _, _, client_b = self._fixture('Returned')
        with patch.object(app_module, 'can_back_up_tsr_drafts', return_value=True), \
                patch.object(app_module, 'get_assigned_approvers_for_requester', return_value=[object()]):
            data = self._client(user_a).get('/calibration-center/data').get_json()
        names = [row['client_name'] for row in data['records']]
        self.assertIn(client_a, names)
        self.assertNotIn(client_b, names)
        self.assertEqual(data['summary']['all'], 1)
        self.assertEqual(data['records'][0]['status']['key'], 'pending')
        self.assertTrue(data['records'][0]['fix_url'].startswith('/calibration-report?'), data['records'][0]['fix_url'])

    def test_due_soon_lists_only_expiring_machines(self):
        user_id, submission_id, approval_id, client_name = self._fixture('Approved')

        def summary(approval, include_urls=True):
            return {'calibration_date': '2025-11-01', 'valid_until': '2026-11-01',
                    'status_key': self.status_key, 'status': 'Due within 1 month'}

        for self.status_key, expected in (('due_1_month', [client_name]), ('valid', [])):
            with patch.object(app_module, 'can_back_up_tsr_drafts', return_value=True), \
                    patch.object(app_module, '_my_calibration_sent', return_value=False), \
                    patch.object(app_module, '_calibration_center_record', return_value={}), \
                    patch.object(app_module, 'calibration_summary_for_approval', side_effect=summary):
                data = self._client(user_id).get('/calibration-center/data').get_json()
            self.assertEqual([item['client_name'] for item in data['due_soon']], expected)

    def test_timeline_is_owner_only(self):
        user_a, _, approval_a, _ = self._fixture('Pending')
        user_b, _, _, _ = self._fixture()
        self.assertEqual(self._client(user_a).get(f'/calibration-center/{approval_a}/timeline').status_code, 200)
        self.assertEqual(self._client(user_b).get(f'/calibration-center/{approval_a}/timeline').status_code, 403)

    def test_page_renders_for_engineer(self):
        user_id, _, _, _ = self._fixture()
        with patch.object(app_module, 'can_back_up_tsr_drafts', return_value=True):
            response = self._client(user_id).get('/calibration-center')
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('My Calibrations', html)
        self.assertIn('id="mycalActionCard"', html)
        self.assertIn('/api/calibration-certificates/submit/', html)
        self.assertEqual(response.headers.get('Cache-Control'), 'no-store, no-cache, must-revalidate, max-age=0')

    def test_page_redirects_users_without_create_tsr(self):
        user_id, _, _, _ = self._fixture()
        with patch.object(app_module, 'can_back_up_tsr_drafts', return_value=False):
            response = self._client(user_id).get('/calibration-center')
        self.assertEqual(response.status_code, 302)


@unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
class KeptFunctionsTests(unittest.TestCase):
    def test_existing_calibration_functions_still_defined(self):
        for name in (
            'submit_calibration_certificate_for_submission', 'submit_calibration_certificate',
            'get_calibration_certificate_status', 'calibration_center_page', 'calibration_center_data',
            '_calibration_center_record', 'can_access_calibration_center',
        ):
            self.assertTrue(callable(getattr(app_module, name, None)), name)


if __name__ == '__main__':
    unittest.main()
