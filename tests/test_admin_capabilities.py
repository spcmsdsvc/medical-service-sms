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
import types
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
        self.assertIn('Only superadmins can choose staff types or assign account permissions.', self.source)

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

            # role='superadmin' on a username outside SUPERADMIN_USERNAMES. The three
            # Cash Advance / LPR helpers used to trust the role column alone, so this
            # account is what proves they no longer do.
            cls.role_only_user = add_user('cap_roleonly', role='superadmin')

            # The regional admin is restricted to REGIONAL_ADMIN_BRANCHES, never Manila.
            # No fixture covered them, which is how a broad capability check placed ahead
            # of their branch silently removed that restriction.
            cls.regional_admin = app_module.User.query.filter_by(username='kevin').first()
            if not cls.regional_admin:
                cls.regional_admin = app_module.User(
                    username='kevin',
                    password=app_module.generate_password_hash('test-password'),
                    role='regional_admin',
                    is_active=True,
                )
                app_module.db.session.add(cls.regional_admin)
                app_module.db.session.flush()
                cls.owned_user_ids.append(cls.regional_admin.id)
            app_module.db.session.commit()

            cls.owned_regional_profile = False
            regional_profile = app_module.Engineer.query.filter_by(
                user_id=cls.regional_admin.id
            ).first()
            if not regional_profile:
                regional_profile = app_module.Engineer(
                    user_id=cls.regional_admin.id,
                    employee_id=app_module.REGIONAL_ADMIN_EMPLOYEE_ID,
                    name='Kevin Regional Admin',
                    initials='KRA',
                    branch='Cebu',
                )
                app_module.db.session.add(regional_profile)
                app_module.db.session.flush()
                cls.created_engineer_ids.append(regional_profile.id)
                cls.owned_regional_profile = True

            manila_engineer = app_module.Engineer(
                employee_id=f'CAP-MNL-{cls.suffix}',
                name=f'Capability Manila {cls.suffix}',
                initials='CMN', branch='Manila',
            )
            cebu_engineer = app_module.Engineer(
                employee_id=f'CAP-CEB-{cls.suffix}',
                name=f'Capability Cebu {cls.suffix}',
                initials='CCB', branch='Cebu',
            )
            app_module.db.session.add_all([manila_engineer, cebu_engineer])
            app_module.db.session.flush()
            cls.created_engineer_ids.extend([manila_engineer.id, cebu_engineer.id])
            cls.manila_engineer_id = manila_engineer.id
            cls.cebu_engineer_id = cebu_engineer.id
            cls.regional_admin_id = cls.regional_admin.id
            cls.role_only_user_id = cls.role_only_user.id
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

    def _as_user(self, user_id, fn):
        """Run fn() with a real logged-in current_user, inside a request context."""
        from flask_login import login_user
        with self.app.test_request_context():
            user = app_module.db.session.get(app_module.User, user_id)
            login_user(user)
            return fn(user)

    def test_regional_admin_still_cannot_touch_manila_schedules(self):
        """The capability check must not swallow the regional admin's branch limit.

        can_manage_any_schedule() folds in is_admin_authorized(), which is true for the
        regional admin. Placed ahead of their narrower branch it returned True first and
        deleted the "Cebu and Davao only, never Manila" rule -- with no flag enabled.
        """
        manila, cebu = self.manila_engineer_id, self.cebu_engineer_id

        def check(user):
            self.assertFalse(bool(getattr(user, 'schedule_admin_access', False)))
            # Positive control: their own branches still work, so a False below is the
            # branch restriction rather than the regional admin being locked out entirely.
            self.assertTrue(app_module.can_modify_schedule_for_engineer_ids([cebu]))
            self.assertTrue(app_module.can_create_schedule_for_engineer_ids([cebu]))
            self.assertFalse(app_module.can_modify_schedule_for_engineer_ids([manila]))
            self.assertFalse(app_module.can_create_schedule_for_engineer_ids([manila]))
            self.assertFalse(app_module.can_modify_schedule_for_engineer_ids([cebu, manila]))

        self._as_user(self.regional_admin_id, check)

    def test_schedule_capability_grants_every_branch(self):
        """Positive control for the test above: the granted flag does cross branches."""
        manila, cebu = self.manila_engineer_id, self.cebu_engineer_id

        def check(_user):
            self.assertTrue(app_module.can_modify_schedule_for_engineer_ids([manila]))
            self.assertTrue(app_module.can_create_schedule_for_engineer_ids([manila]))
            self.assertTrue(app_module.can_modify_schedule_for_engineer_ids([cebu, manila]))

        self._as_user(self.schedule_user_id, check)

        def refused(_user):
            self.assertFalse(app_module.can_modify_schedule_for_engineer_ids([manila]))
            self.assertFalse(app_module.can_create_schedule_for_engineer_ids([manila]))

        self._as_user(self.plain_user_id, refused)

    def test_role_column_alone_does_not_grant_cash_advance_or_lpr_admin(self):
        """Behavioural replacement for the source-string assertion this file used to make.

        A pinned source string cannot tell you whether the rule holds; it only tells you
        the old text is gone. This exercises the predicates with a real account whose role
        column says superadmin but whose username is outside SUPERADMIN_USERNAMES.
        """
        with self.app.app_context():
            role_only = app_module.db.session.get(app_module.User, self.role_only_user_id)
            superadmin = app_module.db.session.get(app_module.User, self.superadmin_id)

            self.assertEqual(role_only.role, 'superadmin')
            self.assertNotIn(role_only.username, app_module.SUPERADMIN_USERNAMES)
            self.assertFalse(app_module.is_admin_authorized(role_only))

            stub = types.SimpleNamespace(user_id=self.superadmin_id, id=1)
            self.assertFalse(app_module.can_user_access_cash_advance(stub, role_only))
            self.assertFalse(app_module.can_user_approve_lpr(role_only, stub))
            self.assertFalse(app_module.lpr_can_manage(stub, role_only))

            # Positive control: a genuine allowlisted superadmin is still granted, so the
            # refusals above are the username gate and not a predicate that denies all.
            self.assertTrue(app_module.can_user_access_cash_advance(stub, superadmin))
            self.assertTrue(app_module.can_user_approve_lpr(superadmin, stub))

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
