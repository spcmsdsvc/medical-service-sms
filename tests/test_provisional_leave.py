import base64
import os
import pathlib
import tempfile
import unittest
from datetime import date, datetime, timedelta

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
        cls.created_shift_ids = []

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

            regional_admin_user = app_module.User.query.filter_by(username='kevin').first()
            if regional_admin_user is None:
                regional_admin_user = app_module.User(
                    username='kevin',
                    password=app_module.generate_password_hash('ProvisionalTest123'),
                    role='regional_admin',
                    is_active=True,
                )
                db.session.add(regional_admin_user)
                db.session.flush()
                cls.created_user_ids.append(regional_admin_user.id)
            regional_admin_user.role = 'regional_admin'
            regional_admin_user.is_active = True

            regional_admin_engineer = app_module.Engineer.query.filter_by(
                employee_id=app_module.REGIONAL_ADMIN_EMPLOYEE_ID
            ).first()
            if not regional_admin_engineer:
                regional_admin_engineer = app_module.Engineer(
                    user_id=regional_admin_user.id,
                    employee_id=app_module.REGIONAL_ADMIN_EMPLOYEE_ID,
                    name='Provisional Test Regional Admin',
                    initials='PRA',
                    branch='Cebu',
                    signature_data=SIGNATURE,
                )
                db.session.add(regional_admin_engineer)
                db.session.flush()
                cls.created_engineer_ids.append(regional_admin_engineer.id)
            else:
                regional_admin_engineer.user_id = regional_admin_user.id
                regional_admin_engineer.branch = 'Cebu'

            regional_target_user = app_module.User(
                username='provisional_regional_target',
                password=app_module.generate_password_hash('ProvisionalTest123'),
                role='engineer',
                is_active=True,
            )
            db.session.add(regional_target_user)
            db.session.flush()
            regional_target_engineer = app_module.Engineer(
                user_id=regional_target_user.id,
                employee_id='PROV-REGIONAL-TARGET',
                name='Provisional Test Regional Engineer',
                initials='PRE',
                branch='Davao',
                signature_data=SIGNATURE,
            )
            db.session.add(regional_target_engineer)
            db.session.flush()

            cls.target_user_id = target_user.id
            cls.target_engineer_id = target_engineer.id
            cls.superuser_id = cls.superuser.id
            cls.regional_admin_user_id = regional_admin_user.id
            cls.regional_target_engineer_id = regional_target_engineer.id
            cls.created_user_ids.append(target_user.id)
            cls.created_user_ids.append(regional_target_user.id)
            cls.created_engineer_ids.extend([super_engineer.id, target_engineer.id, regional_target_engineer.id])

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
            for shift_id in cls.created_shift_ids:
                app_module.ShiftEngineer.query.filter_by(shift_id=shift_id).delete(
                    synchronize_session=False
                )
                shift = db.session.get(app_module.Shift, shift_id)
                if shift:
                    db.session.delete(shift)
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

    @staticmethod
    def _one_and_half_range(offset=0):
        """Return two weekdays with a Friday-to-Monday weekend gap."""
        start = date(2199, 1, 1) + timedelta(weeks=offset)
        while start.weekday() != 4:
            start += timedelta(days=1)
        return start.isoformat(), (start + timedelta(days=3)).isoformat()

    def _direct_shift(self, start_at, end_at, title='Existing schedule'):
        with self.app.app_context():
            row = app_module.Shift(
                title=title,
                start_time=start_at,
                end_time=end_at,
                engineer_id=self.target_engineer_id,
                status='Scheduled',
                schedule_type='service',
            )
            app_module.db.session.add(row)
            app_module.db.session.commit()
            shift_id = row.id
        self.created_shift_ids.append(shift_id)
        return shift_id

    def test_one_and_half_day_draft_preserves_both_positions_and_periods(self):
        client = self._client_as(self.target_user_id)
        cases = (
            (0, 'first', 'AM', '1.5 days (AM on first weekday)'),
            (1, 'last', 'PM', '1.5 days (PM on last weekday)'),
        )
        for offset, position, period, expected_label in cases:
            start, end = self._one_and_half_range(offset)
            response = client.post('/api/leave-requests/save', json={
                'leave_type': 'Vacation Leave',
                'start_date': start,
                'end_date': end,
                'duration_type': 'one_and_half_day',
                'half_day_period': period,
                'partial_day_position': position,
                'reason': 'Two-weekday 1.5-day workflow test.',
            })
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
            item = response.get_json()['leave_request']
            self.created_leave_ids.append(item['id'])
            self.assertEqual(item['duration_type'], 'one_and_half_day')
            self.assertEqual(item['half_day_period'], period)
            self.assertEqual(item['partial_day_position'], position)
            self.assertEqual(item['weekday_count'], 1.5)
            self.assertEqual(item['calendar_weekday_count'], 2)
            self.assertEqual(item['duration_label'], expected_label)

            with self.app.app_context():
                header = app_module.db.session.get(app_module.LeaveRequest, item['id'])
                self.assertEqual(header.duration_type, 'one_and_half_day')
                self.assertEqual(header.half_day_period, period)
                self.assertEqual(header.partial_day_position, position)

    def test_one_and_half_day_provisional_calendar_has_one_full_and_one_partial_block(self):
        start, end = self._one_and_half_range(10)
        payload = self._provisional_payload(start, end)
        payload.update({
            'duration_type': 'one_and_half_day',
            'half_day_period': 'PM',
            'partial_day_position': 'last',
        })
        response = self._client_as(self.superuser_id).post(
            '/api/leave-requests/provisional', json=payload
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        item = response.get_json()['leave_request']
        self.created_leave_ids.append(item['id'])
        self.assertEqual(item['duration_label'], '1.5 days (PM on last weekday)')

        with self.app.app_context():
            rows = sorted(
                app_module.Shift.query.filter_by(leave_request_id=item['id']).all(),
                key=lambda row: row.start_time,
            )
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0].start_time.time().strftime('%H:%M'), '08:00')
            self.assertEqual(rows[0].end_time.time().strftime('%H:%M'), '17:00')
            self.assertEqual(rows[0].title, 'Vacation Leave')
            self.assertEqual(rows[1].start_time.time().strftime('%H:%M'), '13:00')
            self.assertEqual(rows[1].end_time.time().strftime('%H:%M'), '17:00')
            self.assertEqual(rows[1].title, 'Vacation Leave (Half Day - PM)')

    def test_existing_half_day_provisional_calendar_remains_single_interval(self):
        for offset, period, expected_start, expected_end in (
            (60, 'AM', '08:00', '12:00'),
            (61, 'PM', '13:00', '17:00'),
        ):
            start, _end = self._one_and_half_range(offset)
            payload = self._provisional_payload(start, start)
            payload.update({
                'duration_type': 'half_day',
                'half_day_period': period,
            })
            response = self._client_as(self.superuser_id).post(
                '/api/leave-requests/provisional', json=payload
            )
            self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
            item = response.get_json()['leave_request']
            self.created_leave_ids.append(item['id'])
            self.assertEqual(item['duration_label'], f'0.5 day ({period})')
            with self.app.app_context():
                rows = app_module.Shift.query.filter_by(leave_request_id=item['id']).all()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0].start_time.strftime('%H:%M'), expected_start)
                self.assertEqual(rows[0].end_time.strftime('%H:%M'), expected_end)

    def test_one_and_half_day_rejects_invalid_weekday_ranges_on_both_apis(self):
        single_start, _single_end = self._one_and_half_range(20)
        more_start = date(2199, 3, 1)
        while more_start.weekday() != 0:
            more_start += timedelta(days=1)
        more_end = more_start + timedelta(days=2)
        invalid_ranges = (
            (single_start, single_start),
            (more_start.isoformat(), more_end.isoformat()),
        )
        target_client = self._client_as(self.target_user_id)
        super_client = self._client_as(self.superuser_id)
        for start, end in invalid_ranges:
            draft = target_client.post('/api/leave-requests/save', json={
                'leave_type': 'Vacation Leave',
                'start_date': start,
                'end_date': end,
                'duration_type': 'one_and_half_day',
                'half_day_period': 'AM',
                'partial_day_position': 'first',
                'reason': 'Invalid range should be rejected.',
            })
            self.assertEqual(draft.status_code, 400, draft.get_data(as_text=True))
            self.assertIn('exactly two weekdays', draft.get_json()['error'])

            provisional = self._provisional_payload(start, end)
            provisional.update({
                'duration_type': 'one_and_half_day',
                'half_day_period': 'AM',
                'partial_day_position': 'first',
            })
            plotted = super_client.post('/api/leave-requests/provisional', json=provisional)
            self.assertEqual(plotted.status_code, 400, plotted.get_data(as_text=True))
            self.assertIn('exactly two weekdays', plotted.get_json()['error'])

        missing_position = self._provisional_payload(*self._one_and_half_range(21))
        missing_position.update({
            'duration_type': 'one_and_half_day',
            'half_day_period': 'AM',
            'partial_day_position': 'middle',
        })
        response = super_client.post('/api/leave-requests/provisional', json=missing_position)
        self.assertEqual(response.status_code, 400)
        self.assertIn('first or last weekday', response.get_json()['error'])

    def test_one_and_half_day_conflicts_are_limited_to_the_requested_intervals(self):
        start, end = self._one_and_half_range(30)
        first_date = date.fromisoformat(start)
        last_date = date.fromisoformat(end)
        client = self._client_as(self.target_user_id)
        payload = {
            'start_date': start,
            'end_date': end,
            'duration_type': 'one_and_half_day',
            'half_day_period': 'PM',
            'partial_day_position': 'first',
        }

        # The first weekday's unused AM remains available for a PM partial leave.
        self._direct_shift(
            datetime.combine(first_date, datetime.min.time()) + timedelta(hours=8),
            datetime.combine(first_date, datetime.min.time()) + timedelta(hours=12),
            title='Morning-only schedule',
        )
        available = client.post('/api/leave-requests/check-conflicts', json=payload)
        self.assertEqual(available.status_code, 200, available.get_data(as_text=True))
        self.assertFalse(available.get_json()['has_conflicts'])

        # The full-day weekday blocks any overlap on that date.
        self._direct_shift(
            datetime.combine(last_date, datetime.min.time()) + timedelta(hours=8),
            datetime.combine(last_date, datetime.min.time()) + timedelta(hours=9),
            title='Full-day conflict',
        )
        full_conflict = client.post('/api/leave-requests/check-conflicts', json=payload)
        self.assertEqual(full_conflict.status_code, 200)
        self.assertTrue(full_conflict.get_json()['has_conflicts'])

        # The selected PM interval on the first weekday still blocks the request.
        self._direct_shift(
            datetime.combine(first_date, datetime.min.time()) + timedelta(hours=13),
            datetime.combine(first_date, datetime.min.time()) + timedelta(hours=14),
            title='Afternoon conflict',
        )
        partial_conflict = client.post('/api/leave-requests/check-conflicts', json=payload)
        self.assertEqual(partial_conflict.status_code, 200)
        self.assertTrue(partial_conflict.get_json()['has_conflicts'])

    def test_one_and_half_day_submit_approval_pdf_and_history_keep_duration_label(self):
        start, end = self._one_and_half_range(40)
        target_client = self._client_as(self.target_user_id)
        saved = target_client.post('/api/leave-requests/save', json={
            'leave_type': 'Sick Leave',
            'start_date': start,
            'end_date': end,
            'duration_type': 'one_and_half_day',
            'half_day_period': 'AM',
            'partial_day_position': 'first',
            'reason': 'Approved 1.5-day duration test.',
        })
        self.assertEqual(saved.status_code, 200, saved.get_data(as_text=True))
        leave_id = saved.get_json()['leave_request']['id']
        self.created_leave_ids.append(leave_id)

        submitted = target_client.post(f'/api/leave-requests/{leave_id}/submit')
        self.assertEqual(submitted.status_code, 200, submitted.get_data(as_text=True))
        approved = self._client_as(self.superuser_id).post(
            f'/api/leave-requests/{leave_id}/approve', json={'remarks': 'Approved 1.5-day test.'}
        )
        self.assertEqual(approved.status_code, 200, approved.get_data(as_text=True))
        approved_item = approved.get_json()['leave_request']
        self.assertEqual(approved_item['status'], 'Approved')
        self.assertEqual(approved_item['duration_label'], '1.5 days (AM on first weekday)')

        history = target_client.get('/api/leave-requests')
        self.assertEqual(history.status_code, 200)
        history_item = next(item for item in history.get_json()['items'] if item['id'] == leave_id)
        self.assertEqual(history_item['duration_label'], '1.5 days (AM on first weekday)')

        pdf = target_client.get(f'/download_leave_request/{leave_id}')
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.mimetype, 'application/pdf')
        self.assertTrue(pdf.data.startswith(b'%PDF'))

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

    def test_non_admin_cannot_create_provisional_leave(self):
        start, end = self._range(40)
        target_client = self._client_as(self.target_user_id)
        response = target_client.post(
            '/api/leave-requests/provisional',
            json=self._provisional_payload(start, end),
        )
        self.assertEqual(response.status_code, 403)

    def test_regional_admin_can_create_only_for_regional_engineers(self):
        start, end = self._range(440)
        regional_client = self._client_as(self.regional_admin_user_id)

        allowed = regional_client.post(
            '/api/leave-requests/provisional',
            json={**self._provisional_payload(start, end), 'engineer_id': self.regional_target_engineer_id},
        )
        self.assertEqual(allowed.status_code, 201, allowed.get_data(as_text=True))
        self.created_leave_ids.append(allowed.get_json()['leave_request']['id'])

        blocked = regional_client.post(
            '/api/leave-requests/provisional',
            json={**self._provisional_payload(self._range(460)[0], self._range(460)[1]), 'engineer_id': self.target_engineer_id},
        )
        self.assertEqual(blocked.status_code, 403, blocked.get_data(as_text=True))
        self.assertIn('Cebu or Davao', blocked.get_json().get('error', ''))

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

    def _supersede_run(self, offset, provisional_type, formal_type):
        """Plot a provisional, file a separate formal request over it, approve it."""
        start, end = self._range(offset)
        super_client = self._client_as(self.superuser_id)
        provisional = super_client.post(
            '/api/leave-requests/provisional',
            json=self._provisional_payload(start, end, leave_type=provisional_type),
        )
        self.assertEqual(provisional.status_code, 201, provisional.get_data(as_text=True))
        provisional_id = provisional.get_json()['leave_request']['id']
        self.created_leave_ids.append(provisional_id)

        target_client = self._client_as(self.target_user_id)
        draft = target_client.post('/api/leave-requests/save', json={
            'leave_type': formal_type,
            'start_date': start,
            'end_date': end,
            'duration_type': 'full_day',
            'half_day_period': None,
            'reason': 'Filed separately from the provisional plot.',
        })
        self.assertEqual(draft.status_code, 200, draft.get_data(as_text=True))
        formal_id = draft.get_json()['leave_request']['id']
        self.created_leave_ids.append(formal_id)
        submitted = target_client.post(f'/api/leave-requests/{formal_id}/submit')
        self.assertEqual(submitted.status_code, 200, submitted.get_data(as_text=True))
        approved = super_client.post(
            f'/api/leave-requests/{formal_id}/approve', json={'remarks': 'Approved.'}
        )
        self.assertEqual(approved.status_code, 200, approved.get_data(as_text=True))
        return provisional_id, formal_id, self._weekday_count(start, end)

    @staticmethod
    def _weekday_count(start_iso, end_iso):
        """_range() only spans five weekdays when it happens to start on a Monday, so the
        expected block count has to be computed rather than hardcoded."""
        start = date.fromisoformat(start_iso)
        end = date.fromisoformat(end_iso)
        days, cursor = 0, start
        while cursor <= end:
            if cursor.weekday() < 5:
                days += 1
            cursor += timedelta(days=1)
        return days

    @staticmethod
    def _replaced_notice_count():
        return app_module.SystemNotification.query.filter_by(
            title='Provisional Leave Replaced'
        ).count()

    def test_a_mismatched_supersede_names_both_leave_types(self):
        """Telling the plotter "replaced" without saying it became a different leave type
        withholds the one fact that makes the mismatch branch worth having."""
        provisional_id, _formal_id, _days = self._supersede_run(40, 'Vacation Leave', 'Sick Leave')

        with self.app.app_context():
            provisional = app_module.db.session.get(app_module.LeaveRequest, provisional_id)
            audits = app_module.LeaveRequestAudit.query.filter_by(
                leave_request_id=provisional_id, action='superseded'
            ).all()
            self.assertTrue(audits, 'no supersede audit was written')
            audit_text = ' '.join(row.remarks or '' for row in audits)
            self.assertIn('Vacation Leave', audit_text)
            self.assertIn('Sick Leave', audit_text)
            self.assertIn('Vacation Leave', provisional.approval_remarks or '')
            self.assertIn('Sick Leave', provisional.approval_remarks or '')

            notice = app_module.SystemNotification.query.filter_by(
                user_id=self.superuser_id, title='Provisional Leave Replaced'
            ).order_by(app_module.SystemNotification.id.desc()).first()
            self.assertIsNotNone(notice, 'the plotter was never notified')
            self.assertIn('Vacation Leave', notice.message or '')
            self.assertIn('Sick Leave', notice.message or '')

    def test_b_matching_supersede_is_quiet_and_still_replaces(self):
        """Positive control for the test above.

        Without this, the mismatch assertion would still pass if the notification fired
        unconditionally, and the branch would be untested.
        """
        before = None
        with self.app.app_context():
            before = self._replaced_notice_count()

        provisional_id, formal_id, weekday_count = self._supersede_run(60, 'Sick Leave', 'Sick Leave')

        with self.app.app_context():
            self.assertEqual(
                self._replaced_notice_count(), before,
                'a matching leave type must not raise the mismatch notification'
            )
            provisional = app_module.db.session.get(app_module.LeaveRequest, provisional_id)
            # The supersede itself must still happen, so the assertion above is reading
            # the mismatch branch rather than a run where nothing was superseded at all.
            self.assertEqual(provisional.status, 'Superseded')
            self.assertEqual(
                app_module.Shift.query.filter_by(leave_request_id=provisional_id).all(), []
            )
            self.assertEqual(
                len(app_module.Shift.query.filter_by(leave_request_id=formal_id).all()),
                weekday_count
            )

    def test_superseded_requests_are_counted_in_the_queue_summary(self):
        provisional_id, _formal_id, _days = self._supersede_run(80, 'Vacation Leave', 'Sick Leave')

        response = self._client_as(self.target_user_id).get(
            '/get_accounting_leave_request_queue?status=superseded'
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertIn('superseded', body['summary'])
        self.assertGreaterEqual(body['summary']['superseded'], 1)
        self.assertIn(provisional_id, [item['id'] for item in body['items']])

        # Positive control: the superseded record is not also counted as approved leave,
        # which is what folding it into the existing 'paid' bucket would have done.
        with self.app.app_context():
            approved_total = app_module.LeaveRequest.query.filter_by(
                user_id=self.target_user_id, status='Approved'
            ).count()
        self.assertEqual(body['summary']['paid'], approved_total)

    def app_module_header(self, leave_id):
        return app_module.db.session.get(app_module.LeaveRequest, leave_id)

    def test_every_rejection_carries_a_specific_reason_under_error(self):
        """The server contract half of the fix.

        Plotting provisional leave on a weekend answered "Unable to record provisional
        Leave." on screen while the server had said "The selected range contains no
        weekdays." Each rejection below is a distinct, actionable reason, and every one of
        them is set under `error` -- the key the client did not read.
        """
        client = self._client_as(self.superuser_id)
        cases = [
            ({'start_date': '2099-08-08', 'end_date': '2099-08-09'}, 'weekday'),
            ({'start_date': 'not-a-date', 'end_date': 'not-a-date'}, 'date'),
            ({'leave_type': 'Nap Leave'}, 'leave type'),
            ({'engineer_id': 99999999}, 'engineer'),
        ]
        start, end = self._range(400)
        for override, expected_fragment in cases:
            payload = self._provisional_payload(start, end)
            payload.update(override)
            response = client.post('/api/leave-requests/provisional', json=payload)
            self.assertEqual(response.status_code, 400, f'{override} was accepted')
            body = response.get_json()
            self.assertTrue(body.get('error'), f'{override} gave no reason at all')
            self.assertIn(expected_fragment.lower(), body['error'].lower())
            # Positive control on the premise: the reason really is NOT under `message`,
            # which is why reading only that key discarded it.
            self.assertIsNone(body.get('message'))

    def test_the_client_reads_the_key_the_server_actually_sets(self):
        """The cross-file half. This is the bug: two files, two conventions.

        Asserted against source because this project has no JavaScript runner for the
        inline timeline script. It checks an outcome -- that the extraction helper reads
        both keys, and that handleScheduleError() goes through it rather than reaching for
        `.message` directly -- rather than pinning how the helper is written.
        """
        timeline = (pathlib.Path(__file__).resolve().parents[1] / 'templates' / 'timeline.html').read_text(encoding='utf-8')

        helper = timeline.split('function scheduleErrorText(errorPayload){')[1].split('}')[0]
        self.assertIn('errorPayload?.message', helper)
        self.assertIn('errorPayload?.error', helper)
        self.assertLess(
            helper.find('errorPayload?.message'), helper.find('errorPayload?.error'),
            'message must be read first so nothing that works today changes',
        )

        handler = timeline.split('function handleScheduleError(errorPayload, fallbackMessage){')[1].split('\n    }')[0]
        self.assertIn('scheduleErrorText(errorPayload)', handler)
        self.assertNotIn('errorPayload?.message', handler,
                         'the handler must go through the helper, not read one key directly')

    def test_the_conflict_reason_is_also_recoverable(self):
        """The 409 is the most informative rejection and was lost the same way.

        It names the conflicting request. It carries neither `status: 'conflict'` nor
        `conflict`, so handleScheduleError()'s conflict branch does not fire either and it
        falls through to the text path -- which is why the text path had to be the fix.
        """
        client = self._client_as(self.superuser_id)
        start, end = self._range(500)
        first = client.post('/api/leave-requests/provisional', json=self._provisional_payload(start, end))
        self.assertEqual(first.status_code, 201)
        self.created_leave_ids.append(first.get_json()['leave_request']['id'])

        clash = client.post('/api/leave-requests/provisional', json=self._provisional_payload(start, end))
        self.assertEqual(clash.status_code, 409)
        body = clash.get_json()
        self.assertTrue(body.get('error'))
        self.assertIsNone(body.get('status'))
        self.assertIsNone(body.get('conflict'))
        self.assertTrue(body.get('supersedable_provisionals'))


if __name__ == '__main__':
    unittest.main()
