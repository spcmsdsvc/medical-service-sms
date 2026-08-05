import base64
import os
import pathlib
import tempfile
import unittest
from datetime import date, timedelta

os.environ.setdefault(
    'MEDICAL_SERVICE_TEST_DB',
    str(pathlib.Path(tempfile.gettempdir()) / 'medical_service_provisional_leave_tests.db'),
)

import app as app_module  # noqa: E402


SIGNATURE = (
    'data:image/png;base64,'
    + base64.b64encode(
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
        b'\x00\x00\x00\x0dIDAT\x08\xd7c\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff\x89\x99='
        b'\x00\x00\x00\x00IEND\xaeB`\x82'
    ).decode('ascii')
)


class ProvisionalLeaveWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.created_user_ids = []
        cls.created_engineer_ids = []
        cls.created_leave_ids = []

        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_leave_request_tables()
            db = app_module.db

            cls.superuser = app_module.User.query.filter_by(username='jonamar').first()
            if not cls.superuser:
                cls.superuser = app_module.User(
                    username='jonamar',
                    password=app_module.generate_password_hash('ProvisionalTest123'),
                    role='superadmin',
                    is_active=True,
                )
                db.session.add(cls.superuser)
                db.session.flush()
                cls.created_user_ids.append(cls.superuser.id)
            cls.superuser.role = 'superadmin'
            cls.superuser.is_active = True

            target_user = app_module.User(
                username='provisional_leave_target',
                password=app_module.generate_password_hash('ProvisionalTest123'),
                role='engineer',
                is_active=True,
            )
            super_engineer = app_module.Engineer(
                user_id=cls.superuser.id,
                employee_id='PROV-SUPER',
                name='Provisional Test Superadmin',
                initials='PTS',
                branch='Manila',
                signature_data=SIGNATURE,
            )
            target_engineer = app_module.Engineer(
                user_id=None,
                employee_id='PROV-TARGET',
                name='Provisional Test Engineer',
                initials='PTE',
                branch='Manila',
                signature_data=SIGNATURE,
            )
            db.session.add(target_user)
            db.session.flush()
            target_engineer.user_id = target_user.id
            db.session.add_all([super_engineer, target_engineer])
            db.session.flush()
            cls.target_user_id = target_user.id
            cls.target_engineer_id = target_engineer.id
            cls.superuser_id = cls.superuser.id
            cls.created_user_ids.append(target_user.id)
            cls.created_engineer_ids.extend([super_engineer.id, target_engineer.id])

            route = app_module.ApprovalRouting(
                requester_user_id=target_user.id,
                approver_user_id=cls.superuser.id,
                request_scope='leave_request',
                active=True,
            )
            db.session.add(route)
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db = app_module.db
            for leave_id in cls.created_leave_ids:
                header = db.session.get(app_module.LeaveRequest, leave_id)
                if header:
                    app_module.ShiftEngineer.query.filter(
                        app_module.ShiftEngineer.shift_id.in_(
                            [row.id for row in app_module.Shift.query.filter_by(leave_request_id=leave_id).all()]
                        )
                    ).delete(synchronize_session=False)
                    app_module.Shift.query.filter_by(leave_request_id=leave_id).delete(synchronize_session=False)
                    db.session.delete(header)
            db.session.query(app_module.ApprovalRouting).filter(
                app_module.ApprovalRouting.requester_user_id == cls.target_user_id,
                app_module.ApprovalRouting.approver_user_id == cls.superuser_id,
                app_module.ApprovalRouting.request_scope == 'leave_request',
            ).delete(synchronize_session=False)
            for engineer_id in cls.created_engineer_ids:
                engineer = db.session.get(app_module.Engineer, engineer_id)
                if engineer:
                    db.session.delete(engineer)
            for user_id in cls.created_user_ids:
                user = db.session.get(app_module.User, user_id)
                if user:
                    db.session.delete(user)
            db.session.commit()

    @classmethod
    def _client_as(cls, user_id):
        client = cls.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    @staticmethod
    def _range(offset):
        start = date(2099, 8, 2) + timedelta(days=offset)
        while start.weekday() >= 5:
            start += timedelta(days=1)
        return start.isoformat(), (start + timedelta(days=4)).isoformat()

    def _provisional_payload(self, start, end, leave_type='Vacation Leave'):
        return {
            'engineer_id': self.target_engineer_id,
            'leave_type': leave_type,
            'start_date': start,
            'end_date': end,
            'duration_type': 'full_day',
            'half_day_period': None,
            'verbal_approval_notes': 'Approved in team chat for testing.',
        }

    def test_same_record_moves_from_provisional_to_approved_without_duplicates(self):
        start, end = self._range(0)
        super_client = self._client_as(self.superuser_id)
        response = super_client.post('/api/leave-requests/provisional', json=self._provisional_payload(start, end))
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        leave_id = response.get_json()['leave_request']['id']
        self.created_leave_ids.append(leave_id)

        with self.app.app_context():
            rows = app_module.Shift.query.filter_by(leave_request_id=leave_id).all()
            self.assertEqual(len(rows), 5)
            self.assertTrue(all(row.schedule_type == 'leave_request' for row in rows))
            self.assertTrue(all(row.status == 'Pending Approval' for row in rows))

        target_client = self._client_as(self.target_user_id)
        saved = target_client.post('/api/leave-requests/save', json={
            'id': leave_id,
            'leave_type': 'Vacation Leave',
            'start_date': start,
            'end_date': end,
            'duration_type': 'full_day',
            'half_day_period': None,
            'reason': 'Planned annual leave after verbal confirmation.',
            'emergency_form_to_follow': False,
        })
        self.assertEqual(saved.status_code, 200, saved.get_data(as_text=True))
        submitted = target_client.post(f'/api/leave-requests/{leave_id}/submit')
        self.assertEqual(submitted.status_code, 200, submitted.get_data(as_text=True))

        approved = super_client.post(f'/api/leave-requests/{leave_id}/approve', json={'remarks': 'Approved.'})
        self.assertEqual(approved.status_code, 200, approved.get_data(as_text=True))

        with self.app.app_context():
            header = self.app_module_header(leave_id)
            rows = app_module.Shift.query.filter_by(leave_request_id=leave_id).all()
            self.assertEqual(header.status, 'Approved')
            self.assertEqual(len(rows), 5)
            self.assertTrue(all(row.status == 'Approved' for row in rows))

    def test_only_named_superadmin_can_create_provisional_leave(self):
        start, end = self._range(40)
        target_client = self._client_as(self.target_user_id)
        response = target_client.post(
            '/api/leave-requests/provisional',
            json=self._provisional_payload(start, end),
        )
        self.assertEqual(response.status_code, 403)

    def test_separate_formal_request_supersedes_mismatched_provisional(self):
        start, end = self._range(20)
        super_client = self._client_as(self.superuser_id)
        provisional_response = super_client.post(
            '/api/leave-requests/provisional',
            json=self._provisional_payload(start, end, leave_type='Vacation Leave'),
        )
        self.assertEqual(provisional_response.status_code, 201, provisional_response.get_data(as_text=True))
        provisional_id = provisional_response.get_json()['leave_request']['id']
        self.created_leave_ids.append(provisional_id)

        target_client = self._client_as(self.target_user_id)
        draft_response = target_client.post('/api/leave-requests/save', json={
            'leave_type': 'Sick Leave',
            'start_date': start,
            'end_date': end,
            'duration_type': 'full_day',
            'half_day_period': None,
            'reason': 'Emergency illness documented after the provisional plot.',
        })
        self.assertEqual(draft_response.status_code, 200, draft_response.get_data(as_text=True))
        formal_id = draft_response.get_json()['leave_request']['id']
        self.created_leave_ids.append(formal_id)
        submitted = target_client.post(f'/api/leave-requests/{formal_id}/submit')
        self.assertEqual(submitted.status_code, 200, submitted.get_data(as_text=True))
        approved = super_client.post(f'/api/leave-requests/{formal_id}/approve', json={'remarks': 'Approved.'})
        self.assertEqual(approved.status_code, 200, approved.get_data(as_text=True))

        with self.app.app_context():
            provisional = app_module.db.session.get(app_module.LeaveRequest, provisional_id)
            formal = app_module.db.session.get(app_module.LeaveRequest, formal_id)
            provisional_rows = app_module.Shift.query.filter_by(leave_request_id=provisional_id).all()
            formal_rows = app_module.Shift.query.filter_by(leave_request_id=formal_id).all()
            audits = app_module.LeaveRequestAudit.query.filter_by(leave_request_id=provisional_id).all()
            notifications = app_module.SystemNotification.query.filter_by(
                user_id=self.superuser_id, module='leave_request'
            ).all()
            self.assertEqual(provisional.status, 'Superseded')
            self.assertEqual(formal.status, 'Approved')
            self.assertEqual(provisional_rows, [])
            self.assertEqual(len(formal_rows), 5)
            self.assertTrue(any('approved Leave Request' in (row.remarks or '') for row in audits))
            self.assertTrue(any(item.title == 'Provisional Leave Replaced' for item in notifications))

    def app_module_header(self, leave_id):
        return app_module.db.session.get(app_module.LeaveRequest, leave_id)


if __name__ == '__main__':
    unittest.main()
