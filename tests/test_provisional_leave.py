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
