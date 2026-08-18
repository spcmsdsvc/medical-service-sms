"""Approval Center notification endpoint regression coverage."""

import json
import unittest

import app as app_module


class ApprovalNotificationEndpointTests(unittest.TestCase):
    """Keep malformed approval candidates from breaking either notification endpoint."""

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.previous_config = {
            key: cls.app.config.get(key)
            for key in ('TESTING', 'WTF_CSRF_ENABLED', 'PROPAGATE_EXCEPTIONS')
        }
        cls.app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=False,
            PROPAGATE_EXCEPTIONS=False,
        )
        cls.created_user_ids = []
        cls.created_header_ids = []
        cls.created_notification_ids = []
        cls.initial_routing_ids = set()
        cls.approver_was_existing = False
        cls.approver_previous_active = None

        with cls.app.app_context():
            app_module.db.create_all()
            cls._seed()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            try:
                if cls.created_notification_ids:
                    app_module.SystemNotification.query.filter(
                        app_module.SystemNotification.id.in_(cls.created_notification_ids)
                    ).delete(synchronize_session=False)
                for route in app_module.ApprovalRouting.query.all():
                    if route.id not in cls.initial_routing_ids:
                        app_module.db.session.delete(route)
                if cls.created_header_ids:
                    app_module.ReimbursementHeader.query.filter(
                        app_module.ReimbursementHeader.id.in_(cls.created_header_ids)
                    ).delete(synchronize_session=False)
                if cls.created_user_ids:
                    app_module.User.query.filter(
                        app_module.User.id.in_(cls.created_user_ids)
                    ).delete(synchronize_session=False)
                if cls.approver_was_existing and cls.approver_previous_active is not None:
                    approver = app_module.db.session.get(app_module.User, cls.approver_id)
                    if approver:
                        approver.is_active = cls.approver_previous_active
                app_module.db.session.commit()
            except Exception:
                app_module.db.session.rollback()
            finally:
                app_module.db.session.remove()

        cls.app.config.update(cls.previous_config)

    @classmethod
    def _seed(cls):
        db = app_module.db
        today = app_module.get_manila_today()
        now = app_module.as_naive_datetime(app_module.get_manila_time())

        cls.approver = app_module.User.query.filter_by(username='rodito').first()
        if not cls.approver:
            cls.approver = app_module.User(
                username='rodito',
                role='superadmin',
                is_active=True,
                password=app_module.generate_password_hash('ApprovalNotification123'),
            )
            db.session.add(cls.approver)
            db.session.flush()
            cls.created_user_ids.append(cls.approver.id)
        else:
            cls.approver_was_existing = True
            cls.approver_previous_active = cls.approver.is_active
            cls.approver.is_active = True

        requester = app_module.User(
            username='approval_notification_requester',
            role='engineer',
            is_active=True,
            password=app_module.generate_password_hash('ApprovalNotification123'),
        )
        non_approver = app_module.User(
            username='approval_notification_non_approver',
            role='engineer',
            is_active=True,
            password=app_module.generate_password_hash('ApprovalNotification123'),
            can_approve_requests=False,
        )
        db.session.add_all([requester, non_approver])
        db.session.flush()
        cls.requester_id = requester.id
        cls.non_approver_id = non_approver.id
        cls.created_user_ids.extend([requester.id, non_approver.id])

        header = app_module.ReimbursementHeader(
            user_id=requester.id,
            start_date=today,
            end_date=today,
            status='Submitted',
            submitted_at=now,
        )
        db.session.add(header)
        db.session.flush()
        cls.header_id = header.id
        cls.created_header_ids.append(header.id)

        valid = app_module.SystemNotification(
            user_id=cls.approver.id,
            module='reimbursement',
            record_id=header.id,
            title='Reimbursement submitted',
            message='Test reimbursement awaiting approval.',
            target_url='/approvals?module=reimbursement',
            is_read=False,
            metadata_json=json.dumps({'event': 'submitted'}),
            created_at=now,
        )
        incomplete = app_module.SystemNotification(
            user_id=cls.approver.id,
            module='leave_request',
            title='Leave Request awaiting approval',
            message='Legacy notification without event metadata.',
            target_url='/leave-requests',
            is_read=False,
            metadata_json=None,
            created_at=now,
        )
        unrelated = app_module.SystemNotification(
            user_id=cls.approver.id,
            module='unrelated_module',
            title='Unrelated notification',
            message='Must not be included in approval scope.',
            target_url='/dashboard',
            is_read=False,
            metadata_json=json.dumps({'event': 'submitted'}),
            created_at=now,
        )
        db.session.add_all([valid, incomplete, unrelated])
        db.session.commit()
        cls.initial_routing_ids = {
            route.id for route in app_module.ApprovalRouting.query.all()
        }
        cls.valid_notification_id = valid.id
        cls.incomplete_notification_id = incomplete.id
        cls.unrelated_notification_id = unrelated.id
        cls.approver_id = cls.approver.id
        cls.created_notification_ids.extend([
            valid.id,
            incomplete.id,
            unrelated.id,
        ])

    def setUp(self):
        with self.app.app_context():
            for notification_id in self.created_notification_ids:
                notification = app_module.db.session.get(
                    app_module.SystemNotification,
                    notification_id,
                )
                notification.is_read = False
                notification.read_at = None
            app_module.db.session.commit()

    def _client_for(self, user_id):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def test_get_returns_valid_rows_and_skips_incomplete_rows(self):
        response = self._client_for(self.approver_id).get('/get_my_approval_notifications')
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['count'], 1)
        self.assertEqual(payload['unread_count'], 1)
        self.assertEqual(
            [item['id'] for item in payload['items']],
            [self.valid_notification_id],
        )

    def test_mark_all_read_only_marks_active_approval_rows(self):
        response = self._client_for(self.approver_id).post(
            '/mark_scoped_notifications_read',
            json={'scope': 'approval'},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['updated_count'], 1)

        with self.app.app_context():
            valid = app_module.db.session.get(
                app_module.SystemNotification,
                self.valid_notification_id,
            )
            incomplete = app_module.db.session.get(
                app_module.SystemNotification,
                self.incomplete_notification_id,
            )
            unrelated = app_module.db.session.get(
                app_module.SystemNotification,
                self.unrelated_notification_id,
            )
            self.assertTrue(valid.is_read)
            self.assertFalse(incomplete.is_read)
            self.assertFalse(unrelated.is_read)

    def test_non_approver_is_denied_by_both_endpoints(self):
        client = self._client_for(self.non_approver_id)
        with self.subTest(endpoint='load'):
            response = client.get('/get_my_approval_notifications')
            self.assertEqual(response.status_code, 403)
            self.assertFalse(response.get_json()['success'])
        with self.subTest(endpoint='mark_all_read'):
            response = client.post(
                '/mark_scoped_notifications_read',
                json={'scope': 'approval'},
            )
            self.assertEqual(response.status_code, 403)
            self.assertFalse(response.get_json()['success'])


if __name__ == '__main__':
    unittest.main()
