"""Leave Request Batch 1: server checks on range, reason, calendar re-saves, delete, approval and list."""

import base64
import os
import pathlib
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine, event


ROOT = pathlib.Path(__file__).resolve().parents[1]
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_leave_request_server_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402
import leave_feature  # noqa: E402

LEAVE_SOURCE = pathlib.Path(leave_feature.__file__).read_text(encoding='utf-8')

SIGNATURE = (
    'data:image/png;base64,'
    + base64.b64encode(
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
        b'\x00\x00\x00\x0dIDAT\x08\xd7c\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff\x89\x99='
        b'\x00\x00\x00\x00IEND\xaeB`\x82'
    ).decode('ascii')
)


class LeaveRequestServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        engines = cls.app.extensions['sqlalchemy']._app_engines[cls.app]
        cls.original_engine = engines[None]
        cls.test_engine = create_engine(f"sqlite:///{_TEST_DB_PATH.as_posix()}")
        engines[None] = cls.test_engine
        with cls.app.app_context():
            db = app_module.db
            db.create_all()
            app_module.ensure_leave_request_tables()

            def person(username, role, employee_id):
                user = app_module.User(username=username, password='test-only', role=role, is_active=True)
                db.session.add(user)
                db.session.flush()
                engineer = app_module.Engineer(
                    user_id=user.id, employee_id=employee_id, name=username.title(),
                    initials=employee_id[-3:], branch='Manila', signature_data=SIGNATURE,
                )
                db.session.add(engineer)
                db.session.flush()
                return user.id, engineer.id

            cls.owner_id, cls.owner_engineer_id = person('lr_owner', 'engineer', 'LRS-OWN')
            cls.super_id, cls.super_engineer_id = person('jonamar', 'superadmin', 'LRS-SUP')
            cls.super2_id, _ = person('robert', 'superadmin', 'LRS-SU2')
            cls.scheduler_id, _ = person('lr_scheduler', 'staff', 'LRS-SCH')
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            app_module.db.session.remove()
        cls.app.extensions['sqlalchemy']._app_engines[cls.app][None] = cls.original_engine
        cls.test_engine.dispose()
        try:
            _TEST_DB_PATH.unlink()
        except FileNotFoundError:
            pass

    def setUp(self):
        with self.app.app_context():
            db = app_module.db
            app_module.ShiftEngineer.query.delete()
            app_module.Shift.query.delete()
            app_module.LeaveRequestAudit.query.delete()
            app_module.LeaveRequestAttachment.query.delete()
            app_module.LeaveRequest.query.delete()
            db.session.commit()

    # helpers
    def _client(self, user_id=None):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id or self.owner_id)
            session['_fresh'] = True
        return client

    def _monday(self, weeks_ahead=2):
        with self.app.app_context():
            today = app_module.get_manila_today()
        return today + timedelta(days=(7 - today.weekday()) + 7 * (weeks_ahead - 1))

    def _payload(self, start, end=None, **overrides):
        payload = {
            'leave_type': 'Sick Leave',
            'start_date': start.isoformat(),
            'end_date': (end or start).isoformat(),
            'duration_type': 'full_day',
            'reason': 'Flu.',
        }
        payload.update(overrides)
        return payload

    def _save(self, client, payload):
        return client.post('/api/leave-requests/save', json=payload)

    def _leave(self, user_id, engineer_id, status, start, end=None):
        with self.app.app_context():
            header = app_module.LeaveRequest(
                request_no=f'LR-T-{status[:3]}-{user_id}-{start.isoformat()}', user_id=user_id,
                engineer_id=engineer_id, application_date=start, leave_type='Vacation Leave',
                start_date=start, end_date=end or start, weekday_count=1, status=status, reason='Test.',
            )
            app_module.db.session.add(header)
            app_module.db.session.commit()
            return header.id

    def _shift_dates(self, leave_id):
        with self.app.app_context():
            return sorted(row.start_time.date() for row in app_module.Shift.query.filter_by(leave_request_id=leave_id).all())

    # range and reason
    def test_range_limit_on_save_provisional_and_check_conflicts(self):
        start = self._monday()
        client = self._client()
        self.assertEqual(self._save(client, self._payload(start, start + timedelta(days=65))).status_code, 400)
        self.assertEqual(self._save(client, self._payload(start, start + timedelta(days=64))).status_code, 200)
        ten_years = self._save(client, self._payload(start, start + timedelta(days=3653)))
        self.assertEqual(ten_years.status_code, 400)
        self.assertIn('65 calendar days', ten_years.get_json()['error'])

        conflicts = '/api/leave-requests/check-conflicts'
        self.assertEqual(client.post(conflicts, json=self._payload(start, start + timedelta(days=65))).status_code, 400)
        self.assertEqual(client.post(conflicts, json=self._payload(start, start + timedelta(days=64))).status_code, 200)

        super_client = self._client(self.super_id)
        provisional = dict(self._payload(start, start + timedelta(days=65)), engineer_id=self.owner_engineer_id)
        self.assertEqual(super_client.post('/api/leave-requests/provisional', json=provisional).status_code, 400)
        provisional['end_date'] = (start + timedelta(days=64)).isoformat()
        self.assertEqual(super_client.post('/api/leave-requests/provisional', json=provisional).status_code, 201)

    def test_reason_limit(self):
        start = self._monday()
        client = self._client()
        too_long = self._save(client, self._payload(start, reason='x' * 261))
        self.assertEqual(too_long.status_code, 400)
        self.assertIn('260 characters', too_long.get_json()['error'])
        self.assertEqual(self._save(client, self._payload(start, reason='x' * 260)).status_code, 200)

    # calendar re-saves
    def test_form_to_follow_resave_onto_schedule_is_blocked(self):
        first = self._monday()
        moved = first + timedelta(days=2)
        client = self._client()
        leave_id = self._save(client, self._payload(first)).get_json()['leave_request']['id']
        marked = client.post(f'/api/leave-requests/{leave_id}/form-to-follow')
        self.assertEqual(marked.status_code, 200, marked.get_data(as_text=True))
        with self.app.app_context():
            shift = app_module.Shift(
                title='System Installation', engineer_id=self.owner_engineer_id, status='Scheduled',
                start_time=datetime.combine(moved, datetime.min.time()) + timedelta(hours=9),
                end_time=datetime.combine(moved, datetime.min.time()) + timedelta(hours=12),
            )
            app_module.db.session.add(shift)
            app_module.db.session.flush()
            app_module.db.session.add(app_module.ShiftEngineer(shift_id=shift.id, engineer_id=self.owner_engineer_id))
            app_module.db.session.commit()
        response = self._save(client, dict(self._payload(moved), id=leave_id))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()['blocking_schedules'][0]['title'], 'System Installation')
        self.assertEqual(self._shift_dates(leave_id), [first])

    def test_provisional_resave_moves_calendar(self):
        first = self._monday()
        moved = first + timedelta(days=7)
        provisional = dict(self._payload(first), engineer_id=self.owner_engineer_id)
        created = self._client(self.super_id).post('/api/leave-requests/provisional', json=provisional)
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        leave_id = created.get_json()['leave_request']['id']
        self.assertEqual(self._shift_dates(leave_id), [first])
        saved = self._save(self._client(), dict(self._payload(moved), id=leave_id))
        self.assertEqual(saved.status_code, 200, saved.get_data(as_text=True))
        self.assertEqual(self._shift_dates(leave_id), [moved])

    # delete, approval, ids, HR resend
    def test_provisional_cannot_be_deleted(self):
        provisional = dict(self._payload(self._monday()), engineer_id=self.owner_engineer_id)
        leave_id = self._client(self.super_id).post('/api/leave-requests/provisional', json=provisional).get_json()['leave_request']['id']
        response = self._client().delete(f'/api/leave-requests/{leave_id}')
        self.assertEqual(response.status_code, 409)
        self.assertIn('Provisional leave cannot be deleted', response.get_json()['error'])
        self.assertEqual(len(self._shift_dates(leave_id)), 1)

    def test_superadmin_cannot_approve_own_leave(self):
        leave_id = self._leave(self.super_id, self.super_engineer_id, 'Submitted', self._monday())
        own = self._client(self.super_id)
        self.assertEqual(own.post(f'/api/leave-requests/{leave_id}/approve', json={}).status_code, 404)
        self.assertEqual(own.post(f'/api/leave-requests/{leave_id}/reject', json={'remarks': 'x'}).status_code, 404)
        detail = own.get(f'/api/leave-requests/{leave_id}')
        self.assertEqual(detail.status_code, 200)
        self.assertFalse(detail.get_json()['leave_request']['can_approve'])
        self.assertEqual(own.get(f'/download_leave_request/{leave_id}').status_code, 200)
        with patch.object(leave_feature.threading, 'Thread'):
            other = self._client(self.super2_id).post(f'/api/leave-requests/{leave_id}/approve', json={})
        self.assertEqual(other.status_code, 200, other.get_data(as_text=True))

    def test_unknown_or_foreign_id_on_save_returns_404(self):
        foreign_id = self._leave(self.super_id, self.super_engineer_id, 'Draft', self._monday())
        client = self._client()
        for leave_id in (999999, foreign_id):
            response = self._save(client, dict(self._payload(self._monday()), id=leave_id))
            self.assertEqual(response.status_code, 404)
        with self.app.app_context():
            self.assertEqual(app_module.LeaveRequest.query.filter_by(user_id=self.owner_id).count(), 0)

    def test_hr_resend_needs_approver_or_superadmin(self):
        leave_id = self._leave(self.owner_id, self.owner_engineer_id, 'Approved', self._monday())
        self.assertEqual(self._client(self.scheduler_id).post(f'/api/leave-requests/{leave_id}/resend-hr').status_code, 404)
        with patch.object(leave_feature.threading, 'Thread'):
            self.assertEqual(self._client(self.super_id).post(f'/api/leave-requests/{leave_id}/resend-hr').status_code, 200)

    # list
    def _list_query_count(self, records):
        start = self._monday()
        for index in range(records):
            self._leave(self.owner_id, self.owner_engineer_id, 'Draft', start + timedelta(days=7 * index))
        statements = []

        def listener(*args):
            statements.append(args[2])

        event.listen(self.test_engine, 'before_cursor_execute', listener)
        try:
            response = self._client().get('/api/leave-requests')
        finally:
            event.remove(self.test_engine, 'before_cursor_execute', listener)
        items = response.get_json()['items']
        self.assertEqual(len(items), records)
        return len(statements), items

    def test_list_query_count_does_not_grow(self):
        two, _ = self._list_query_count(2)
        self.setUp()
        ten, items = self._list_query_count(10)
        self.assertEqual(two, ten)
        self.assertEqual(
            set(items[0]),
            {'id', 'request_no', 'status', 'leave_type', 'date_range', 'duration_label', 'weekday_count', 'start_date', 'end_date'},
        )

    # source
    def test_dead_code_removed(self):
        self.assertNotRegex(LEAVE_SOURCE, r'(?m)^import json$')
        self.assertNotIn('is_management_user', LEAVE_SOURCE)
        self.assertNotIn('Only the employee can formally submit', LEAVE_SOURCE)

    def test_kept_routes_and_ctx_keys(self):
        for endpoint in (
            'leave_request_page', 'list_leave_requests', 'get_accounting_leave_request_queue', 'get_leave_request',
            'save_leave_request', 'create_provisional_leave_request', 'check_leave_request_conflicts',
            'mark_leave_form_to_follow', 'submit_leave_request', 'leave_request_approval_items',
            'approve_leave_request', 'reject_leave_request', 'resend_leave_request_hr', 'preview_leave_request_pdf',
            'download_leave_request_pdf', 'upload_leave_request_attachments', 'preview_leave_request_attachment',
            'download_leave_request_attachment', 'delete_leave_request_attachment',
            'delete_all_leave_request_attachments', 'delete_leave_request_draft',
        ):
            self.assertIn(endpoint, self.app.view_functions)
        for key in (
            'LeaveRequest', 'LeaveRequestAttachment', 'LeaveRequestAudit', 'ensure_leave_request_tables',
            'leave_request_attachment_upload_root', 'can_approve_leave_request', 'leave_request_to_dict',
            'update_leave_request_calendar', 'send_leave_request_hr_email_async',
        ):
            self.assertTrue(hasattr(app_module, key), key)


if __name__ == '__main__':
    unittest.main()
