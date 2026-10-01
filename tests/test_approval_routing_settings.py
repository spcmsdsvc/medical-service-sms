"""Regression coverage for Settings > Approval Routing.

The route endpoints had no direct tests. These pin the management rules the tab relies on:
who may call them, what a save/bulk/deactivate does, the flags that mark a route nobody can
act on, and the page contract (sub-tabs, request-type labels, removed Scope field).
"""

import os
import pathlib
import tempfile
import unittest
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f'medical_service_approval_routing_{uuid.uuid4().hex}.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402


class ApprovalRoutingSettingsSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = (ROOT / 'templates' / 'settings.html').read_text(encoding='utf-8')

    def test_tab_has_three_sub_panels(self):
        for name in ('routes', 'add', 'people'):
            self.assertIn(f'data-approval-subtab="{name}"', self.settings)
            self.assertIn(f'data-approval-pane="{name}"', self.settings)

    def test_every_request_scope_has_a_label(self):
        label_block = self.settings.split('function approvalScopeLabel(scope)')[1].split('return map[scope]')[0]
        for scope in app_module.APPROVAL_REQUEST_SCOPES:
            self.assertIn(f'{scope}:', label_block, f'{scope} has no label in approvalScopeLabel')

    def test_unused_scope_field_is_gone_and_not_posted(self):
        self.assertNotIn('Scope e.g. executive', self.settings)
        self.assertNotIn('approval-scope-input', self.settings)
        save_block = self.settings.split('async function saveApprovalUser(userId)')[1].split('async function')[0]
        self.assertNotIn('approval_scope:', save_block)

    def test_user_cards_with_unsaved_edits_survive_a_reload(self):
        render_block = self.settings.split('function renderApprovalUsers()')[1].split('function filterApprovalUsers()')[0]
        self.assertIn("existing.classList.contains('is-dirty')", render_block)

    def test_copy_does_not_name_people(self):
        section = self.settings.split('data-settings-section="approval"')[1].split('data-settings-section="email-recipients"')[0]
        for name in ('Rodito', 'Anthony', 'Robert'):
            self.assertNotIn(name, section)


class ApprovalRoutingSettingsWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.suffix = uuid.uuid4().hex[:10]
        cls.owned_user_ids = []

        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_approval_routing_schema()

            def add_user(username, role='staff', **flags):
                flags.setdefault('is_active', True)
                user = app_module.User(
                    username=f'{username}_{cls.suffix}',
                    password=app_module.generate_password_hash('test-password'),
                    role=role,
                    **flags,
                )
                app_module.db.session.add(user)
                app_module.db.session.flush()
                cls.owned_user_ids.append(user.id)
                return user

            superadmin = app_module.User.query.filter_by(username='jonamar').first()
            if not superadmin:
                superadmin = app_module.User(
                    username='jonamar',
                    password=app_module.generate_password_hash('test-password'),
                    role='superadmin',
                    is_active=True,
                )
                app_module.db.session.add(superadmin)
                app_module.db.session.flush()
                cls.owned_user_ids.append(superadmin.id)

            cls.superadmin_id = superadmin.id
            cls.plain_id = add_user('route_plain').id
            cls.requester_id = add_user('route_requester').id
            cls.requester_two_id = add_user('route_requester_two').id
            cls.approver_id = add_user('route_approver', can_approve_requests=True).id
            cls.second_approver_id = add_user('route_approver_two', can_approve_requests=True).id
            cls.new_approver_id = add_user('route_new_approver').id
            cls.inactive_id = add_user('route_inactive', is_active=False).id
            cls.scoped_id = add_user('route_scoped', approval_scope='executive').id
            app_module.db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            app_module.ApprovalRouting.query.filter(
                app_module.ApprovalRouting.requester_user_id.in_(cls.owned_user_ids) |
                app_module.ApprovalRouting.approver_user_id.in_(cls.owned_user_ids)
            ).delete(synchronize_session=False)
            for user_id in reversed(cls.owned_user_ids):
                user = app_module.db.session.get(app_module.User, user_id)
                if user:
                    app_module.db.session.delete(user)
            app_module.db.session.commit()
            app_module.db.session.remove()

    def setUp(self):
        with self.app.app_context():
            app_module.ApprovalRouting.query.filter(
                app_module.ApprovalRouting.requester_user_id.in_(self.owned_user_ids)
            ).delete(synchronize_session=False)
            for user_id, can_approve, active in (
                (self.approver_id, True, True),
                (self.second_approver_id, True, True),
                (self.new_approver_id, False, True),
            ):
                user = app_module.db.session.get(app_module.User, user_id)
                user.can_approve_requests = can_approve
                user.is_active = active
            app_module.db.session.commit()
        self.client = self._client_for(self.superadmin_id)

    @classmethod
    def _client_for(cls, user_id):
        client = cls.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def _save(self, requester_id, approver_id, scope='all', client=None):
        return (client or self.client).post('/settings/save-approval-route', json={
            'requester_user_id': requester_id,
            'approver_user_id': approver_id,
            'request_scope': scope,
            'active': True,
        })

    def _route_from_data(self, route_id):
        data = self.client.get('/settings/approval-routing-data').get_json()
        return next(route for route in data['routes'] if route['id'] == route_id)

    def test_non_superadmin_is_denied_everywhere(self):
        plain = self._client_for(self.plain_id)
        self.assertNotEqual(plain.get('/settings/approval-routing-data').status_code, 200)
        for path, payload in (
            ('/settings/save-approval-route', {
                'requester_user_id': self.requester_id, 'approver_user_id': self.approver_id}),
            ('/settings/save-approval-routes-bulk', {
                'requester_user_ids': [self.requester_id], 'approver_user_id': self.approver_id}),
            ('/settings/delete-approval-route', {'route_id': 1}),
            ('/settings/delete-all-approval-routes', {'confirm_text': 'DELETE ALL ROUTES'}),
            ('/settings/update-approval-user', {'user_id': self.requester_id}),
        ):
            self.assertNotEqual(plain.post(path, json=payload).status_code, 200, path)
        with self.app.app_context():
            self.assertEqual(
                app_module.ApprovalRouting.query.filter_by(requester_user_id=self.requester_id).count(), 0
            )

    def test_single_save_creates_then_reactivates(self):
        created = self._save(self.requester_id, self.approver_id, 'reimbursement')
        self.assertEqual(created.status_code, 200)
        route = created.get_json()['route']
        self.assertTrue(route['active'])
        self.assertEqual(route['request_scope'], 'reimbursement')
        self.assertFalse(created.get_json()['approver_granted'])

        removed = self.client.post('/settings/delete-approval-route', json={'route_id': route['id']})
        self.assertEqual(removed.status_code, 200)
        self.assertFalse(removed.get_json()['route']['active'])

        again = self._save(self.requester_id, self.approver_id, 'reimbursement')
        self.assertEqual(again.get_json()['route']['id'], route['id'])
        self.assertTrue(again.get_json()['route']['active'])

    def test_single_save_rejects_self_and_inactive_accounts(self):
        self.assertEqual(self._save(self.requester_id, self.requester_id).status_code, 400)

        inactive_approver = self._save(self.requester_id, self.inactive_id)
        self.assertEqual(inactive_approver.status_code, 400)
        self.assertIn('inactive', inactive_approver.get_json()['error'].lower())

        inactive_requester = self._save(self.inactive_id, self.approver_id)
        self.assertEqual(inactive_requester.status_code, 400)
        self.assertIn('inactive', inactive_requester.get_json()['error'].lower())

        with self.app.app_context():
            self.assertFalse(app_module.db.session.get(app_module.User, self.inactive_id).can_approve_requests)

    def test_saving_a_route_grants_approval_rights_and_says_so(self):
        response = self._save(self.requester_id, self.new_approver_id)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['approver_granted'])
        with self.app.app_context():
            self.assertTrue(app_module.db.session.get(app_module.User, self.new_approver_id).can_approve_requests)

        bulk = self.client.post('/settings/save-approval-routes-bulk', json={
            'requester_user_ids': [self.requester_two_id],
            'approver_user_id': self.new_approver_id,
        })
        self.assertFalse(bulk.get_json()['approver_granted'])

    def test_bulk_adds_skips_and_preserves_other_approvers(self):
        self._save(self.requester_id, self.second_approver_id)

        first = self.client.post('/settings/save-approval-routes-bulk', json={
            'requester_user_ids': [self.requester_id, self.requester_two_id, self.approver_id, self.inactive_id],
            'approver_user_id': self.approver_id,
            'request_scope': 'all',
        })
        self.assertEqual(first.status_code, 200)
        body = first.get_json()
        self.assertEqual(body['created_count'], 2)
        self.assertEqual(body['skipped_count'], 2)
        self.assertTrue(all(item.get('reason') for item in body['skipped']))

        second = self.client.post('/settings/save-approval-routes-bulk', json={
            'requester_user_ids': [self.requester_id, self.requester_two_id],
            'approver_user_id': self.approver_id,
        })
        self.assertEqual(second.get_json()['created_count'], 0)
        self.assertEqual(second.get_json()['skipped_count'], 2)

        with self.app.app_context():
            approver_ids = {
                approver.id
                for approver in app_module.get_assigned_approvers_for_requester(self.requester_id, 'all')
            }
        self.assertEqual(approver_ids, {self.approver_id, self.second_approver_id})

    def test_deactivate_all_needs_the_confirmation_text(self):
        self._save(self.requester_id, self.approver_id)
        refused = self.client.post('/settings/delete-all-approval-routes', json={'confirm_text': 'yes'})
        self.assertEqual(refused.status_code, 400)
        with self.app.app_context():
            self.assertEqual(
                app_module.ApprovalRouting.query.filter_by(requester_user_id=self.requester_id, active=True).count(), 1
            )

        done = self.client.post('/settings/delete-all-approval-routes', json={'confirm_text': 'delete all routes'})
        self.assertEqual(done.status_code, 200)
        with self.app.app_context():
            self.assertEqual(app_module.ApprovalRouting.query.filter_by(active=True).count(), 0)

    def test_route_flags_mark_a_route_nobody_can_act_on(self):
        route_id = self._save(self.requester_id, self.approver_id).get_json()['route']['id']
        healthy = self._route_from_data(route_id)
        self.assertTrue(healthy['approver_active'])
        self.assertTrue(healthy['approver_can_approve'])
        self.assertTrue(healthy['requester_active'])

        with self.app.app_context():
            app_module.db.session.get(app_module.User, self.approver_id).can_approve_requests = False
            app_module.db.session.commit()
        self.assertFalse(self._route_from_data(route_id)['approver_can_approve'])

        with self.app.app_context():
            approver = app_module.db.session.get(app_module.User, self.approver_id)
            approver.can_approve_requests = True
            approver.is_active = False
            app_module.db.session.commit()
        stale = self._route_from_data(route_id)
        self.assertTrue(stale['active'])
        self.assertFalse(stale['approver_active'])

    def test_deactivation_audit_names_both_accounts(self):
        route_id = self._save(self.requester_id, self.approver_id, 'leave_request').get_json()['route']['id']
        self.client.post('/settings/delete-approval-route', json={'route_id': route_id})
        with self.app.app_context():
            audit = (
                app_module.ActivityLog.query
                .filter(app_module.ActivityLog.action.like('Deactivated approval route%'))
                .order_by(app_module.ActivityLog.id.desc())
                .first()
            )
            requester = app_module.db.session.get(app_module.User, self.requester_id)
            approver = app_module.db.session.get(app_module.User, self.approver_id)
            self.assertIn(requester.username, audit.action)
            self.assertIn(approver.username, audit.action)
            self.assertIn('leave_request', audit.action)

    def test_settings_save_keeps_the_stored_scope_label(self):
        kept = self.client.post('/settings/update-approval-user', json={
            'user_id': self.scoped_id, 'approval_title': 'Director', 'is_active': True,
        })
        self.assertEqual(kept.status_code, 200)
        self.assertEqual(kept.get_json()['user']['approval_scope'], 'executive')

        replaced = self.client.post('/settings/update-approval-user', json={
            'user_id': self.scoped_id, 'approval_scope': 'board', 'is_active': True,
        })
        self.assertEqual(replaced.get_json()['user']['approval_scope'], 'board')


if __name__ == '__main__':
    unittest.main()
