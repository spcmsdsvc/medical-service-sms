"""Regression coverage for grantable admin-surface capabilities.

These tests deliberately use an isolated database. The capabilities are narrower than
system administration, so the important assertions are endpoint-level: a grantee can use
the surface they were given, cannot use the other two, and cannot grant permissions back
through Add Personnel.
"""

import json
import os
import pathlib
import tempfile
import unittest
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f'medical_service_admin_capabilities_{uuid.uuid4().hex}.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402


class AdminCapabilitySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.layout = (ROOT / 'templates' / 'layout.html').read_text(encoding='utf-8')
        cls.settings = (ROOT / 'templates' / 'settings.html').read_text(encoding='utf-8')
        cls.engineers = (ROOT / 'templates' / 'engineers.html').read_text(encoding='utf-8')
        cls.timeline = (ROOT / 'templates' / 'timeline.html').read_text(encoding='utf-8')
        cls.releases = json.loads(
            (ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8')
        )

    def test_flags_migration_resolver_and_settings_controls_exist(self):
        for marker in (
            'personnel_admin_access = db.Column(db.Boolean, default=False, nullable=False)',
            'reports_admin_access = db.Column(db.Boolean, default=False, nullable=False)',
            'schedule_admin_access = db.Column(db.Boolean, default=False, nullable=False)',
            'def ensure_user_admin_capability_columns():',
            'def can_administer_personnel(user=None):',
            'def can_view_admin_reports(user=None):',
            'def can_manage_any_schedule(user=None):',
            'personnel_admin_access',
            'reports_admin_access',
            'schedule_admin_access',
            'function toggleAdminCapability(input)',
        ):
            self.assertIn(marker, self.source + self.settings)

    def test_scope_guards_and_escalation_boundaries_are_source_visible(self):
        self.assertIn('if not can_administer_personnel()', self.source)
        self.assertIn('if not can_view_admin_reports()', self.source)
        self.assertIn('can_manage_any_schedule(target)', self.source)
        self.assertIn('Only superadmins can choose staff types or assign account permissions.', self.source)
        self.assertIn("if not is_admin_authorized(): return jsonify({'message': 'Denied'}), 403", self.source)

        for function_name in ('can_user_access_cash_advance', 'lpr_can_manage', 'can_user_approve_lpr'):
            function_body = self.source.split(f'def {function_name}(', 1)[1].split('\ndef ', 1)[0]
            self.assertIn('is_admin_authorized', function_body)
            self.assertNotIn("role in {'superadmin', 'regional_admin'}", function_body)

    def test_release_manifest_has_the_capability_update(self):
        release = next(item for item in self.releases['releases'] if item['release_key'] == '2026-08-05')
        self.assertTrue(any(
            item['item_key'] == '2026-08-05-grantable-admin-capabilities'
            for item in release['items']
        ))


class AdminCapabilityWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.suffix = uuid.uuid4().hex[:10]
        cls.owned_user_ids = []
        cls.created_engineer_ids = []

        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_user_admin_capability_columns()

            def add_user(username, role='staff', **flags):
                user = app_module.User(
                    username=f'{username}_{cls.suffix}',
                    password=app_module.generate_password_hash('test-password'),
                    role=role,
                    is_active=True,
                    **flags,
                )
                app_module.db.session.add(user)
                app_module.db.session.flush()
                cls.owned_user_ids.append(user.id)
                return user

            cls.superadmin = app_module.User.query.filter_by(username='jonamar').first()
            if not cls.superadmin:
                cls.superadmin = app_module.User(
                    username='jonamar',
                    password=app_module.generate_password_hash('test-password'),
                    role='superadmin',
                    is_active=True,
                )
                app_module.db.session.add(cls.superadmin)
                app_module.db.session.flush()
                cls.owned_user_ids.append(cls.superadmin.id)

            cls.personnel_user = add_user('cap_personnel', personnel_admin_access=True)
            cls.reports_user = add_user('cap_reports', reports_admin_access=True)
            cls.schedule_user = add_user('cap_schedule', schedule_admin_access=True)
            cls.plain_user = add_user('cap_plain')
            cls.approver_user = add_user('cap_approver', role='approver', can_approve_requests=True)
            app_module.db.session.commit()

            cls.superadmin_id = cls.superadmin.id
            cls.personnel_user_id = cls.personnel_user.id
            cls.reports_user_id = cls.reports_user.id
            cls.schedule_user_id = cls.schedule_user.id
            cls.plain_user_id = cls.plain_user.id
            cls.approver_user_id = cls.approver_user.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            for engineer_id in reversed(cls.created_engineer_ids):
                engineer = app_module.db.session.get(app_module.Engineer, engineer_id)
                if engineer:
                    app_module.db.session.delete(engineer)
            for user_id in reversed(cls.owned_user_ids):
                user = app_module.db.session.get(app_module.User, user_id)
                if user:
                    app_module.db.session.delete(user)
            app_module.db.session.commit()
            app_module.db.session.remove()

    @classmethod
    def _client_for(cls, user_id):
        client = cls.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def test_each_capability_opens_only_its_intended_surface(self):
        with self.app.app_context():
            self.assertTrue(app_module.is_admin_authorized(self.superadmin))
            self.assertTrue(app_module.can_administer_personnel(self.superadmin))
            self.assertTrue(app_module.can_view_admin_reports(self.superadmin))
            self.assertTrue(app_module.can_manage_any_schedule(self.superadmin))
            self.assertFalse(app_module.can_administer_personnel(
                app_module.db.session.get(app_module.User, self.plain_user_id)
            ))
            self.assertFalse(app_module.can_view_admin_reports(
                app_module.db.session.get(app_module.User, self.plain_user_id)
            ))
            self.assertFalse(app_module.can_manage_any_schedule(
                app_module.db.session.get(app_module.User, self.plain_user_id)
            ))

        personnel = self._client_for(self.personnel_user_id)
        self.assertEqual(personnel.get('/engineers_page').status_code, 200)
        self.assertEqual(personnel.get('/export_engineers').status_code, 200)
        self.assertEqual(personnel.get('/reports_page').status_code, 302)
        self.assertEqual(personnel.get('/timeline').status_code, 302)

        reports = self._client_for(self.reports_user_id)
        self.assertEqual(reports.get('/reports_page').status_code, 200)
        self.assertEqual(reports.get('/analytics_page').status_code, 200)
        self.assertEqual(reports.get('/get_reports_summary').status_code, 200)
        self.assertEqual(reports.get('/export_reports_summary').status_code, 200)
        self.assertEqual(reports.get('/engineers_page').status_code, 302)
        self.assertEqual(reports.get('/timeline').status_code, 302)

        schedule = self._client_for(self.schedule_user_id)
        self.assertEqual(schedule.get('/timeline').status_code, 200)
        self.assertEqual(schedule.get('/get_timeline_data?offset=0&branch=ALL').status_code, 200)
        self.assertEqual(schedule.get('/engineers_page').status_code, 302)
        self.assertEqual(schedule.get('/reports_page').status_code, 302)

        plain = self._client_for(self.plain_user_id)
        self.assertEqual(plain.get('/engineers_page').status_code, 302)
        self.assertEqual(plain.get('/reports_page').status_code, 302)
        self.assertEqual(plain.get('/timeline').status_code, 302)
        self.assertEqual(plain.get('/get_timeline_data?offset=0&branch=ALL').status_code, 403)

    def test_superadmin_can_grant_flags_and_audit_old_and_new_values(self):
        client = self._client_for(self.superadmin_id)
        response = client.post(
            '/settings/update-approval-user',
            json={
                'user_id': self.personnel_user_id,
                'personnel_admin_access': True,
                'reports_admin_access': False,
                'schedule_admin_access': False,
                'is_active': True,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['user']['personnel_admin_access'])

        with self.app.app_context():
            audit = (
                app_module.ActivityLog.query
                .filter(app_module.ActivityLog.action.ilike('%approval user settings%'))
                .order_by(app_module.ActivityLog.id.desc())
                .first()
            )
            self.assertIsNotNone(audit)
            # The first save is intentionally unchanged for this flag. It should not be
            # listed as changed; this catches noisy audit records.
            self.assertNotIn('personnel_admin_access:', audit.action)

        response = client.post(
            '/settings/update-approval-user',
            json={
                'user_id': self.personnel_user_id,
                'personnel_admin_access': False,
                'reports_admin_access': True,
                'schedule_admin_access': False,
                'is_active': True,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['user']['reports_admin_access'])

        with self.app.app_context():
            audit = (
                app_module.ActivityLog.query
                .filter(app_module.ActivityLog.action.ilike('%approval user settings%'))
                .order_by(app_module.ActivityLog.id.desc())
                .first()
            )
            self.assertIn('personnel_admin_access: True -> False', audit.action)
            self.assertIn('reports_admin_access: False -> True', audit.action)

            target = app_module.db.session.get(app_module.User, self.personnel_user_id)
            target.personnel_admin_access = False
            target.reports_admin_access = False
            app_module.db.session.commit()

    def test_restricted_combinations_and_personnel_escalation_are_blocked(self):
        with self.app.app_context():
            target = app_module.db.session.get(app_module.User, self.personnel_user_id)
            _values, error = app_module.resolve_staff_permission_request(
                {'personnel_admin_access': True, 'hr_schedule_view': True}, target
            )
            self.assertIn('HR Schedule View', error)

            _values, error = app_module.resolve_staff_permission_request(
                {'reports_admin_access': True, 'approver_only': True}, target
            )
            self.assertIn('Approver-only view', error)

            _values, error = app_module.resolve_staff_permission_request(
                {'schedule_admin_access': True, 'stock_inventory_only': True}, target
            )
            self.assertIn('Stock Inventory-only view', error)

        client = self._client_for(self.personnel_user_id)
        denied_response = client.post(
            '/add_engineer',
            json={
                'staff_type': 'hr',
                'name': f'Escalation Attempt {self.suffix}',
                'personnel_admin_access': True,
            },
        )
        self.assertEqual(denied_response.status_code, 403)

        plain_response = client.post(
            '/add_engineer',
            json={
                'staff_type': 'engineer',
                'employee_id': f'CAP-{self.suffix}',
                'name': f'Capability Test Engineer {self.suffix}',
                'initials': 'CTE',
                'branch': 'Cebu',
                'phone': '',
                'email': '',
            },
        )
        self.assertEqual(plain_response.status_code, 200)
        with self.app.app_context():
            created_user = app_module.User.query.filter_by(
                username=plain_response.get_json()['username']
            ).first()
            self.assertIsNotNone(created_user)
            created_engineer = app_module.Engineer.query.filter_by(user_id=created_user.id).first()
            self.assertIsNotNone(created_engineer)
            self.created_engineer_ids.append(created_engineer.id)
            self.owned_user_ids.append(created_user.id)


if __name__ == '__main__':
    unittest.main()
