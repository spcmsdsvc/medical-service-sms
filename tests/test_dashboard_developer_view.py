"""Developer account: engineer-only dashboard (plans.md, "Developer Account").

The developer (`jonamar`) is a superadmin and a field engineer, not a manager. Their dashboard
is the plain engineer dashboard; every permission stays as it was.
"""

import os
import pathlib
import tempfile
import unittest

_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_developer_view_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402


class DeveloperEngineerOnlyDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.app.config['TESTING'] = True
        cls.created_user_ids = []
        cls.created_engineer_ids = []
        with cls.app.app_context():
            app_module.db.create_all()
            cls.developer_id = cls._user_with_profile('jonamar', 'DV')
            cls.other_admin_id = cls._user_with_profile('robert', 'RB')
            # The engineer-only dashboard follows the protected-account switch, not the name.
            developer = app_module.db.session.get(app_module.User, cls.developer_id)
            developer.is_protected_account = True
            app_module.db.session.commit()

    @classmethod
    def _user_with_profile(cls, username, initials):
        user = app_module.User.query.filter_by(username=username).first()
        if not user:
            user = app_module.User(username=username, role='superadmin', is_active=True,
                                   password=app_module.generate_password_hash('DevView123'))
            app_module.db.session.add(user)
            app_module.db.session.commit()
            cls.created_user_ids.append(user.id)
        if not getattr(user, 'engineer_profile', None):
            engineer = app_module.Engineer(name=f'{username} Dev View', employee_id=f'DV-{initials}',
                                           initials=initials, branch='Cebu', user_id=user.id)
            app_module.db.session.add(engineer)
            app_module.db.session.commit()
            cls.created_engineer_ids.append(engineer.id)
        return user.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            for engineer_id in cls.created_engineer_ids:
                engineer = app_module.db.session.get(app_module.Engineer, engineer_id)
                if engineer:
                    app_module.db.session.delete(engineer)
            for user_id in cls.created_user_ids:
                user = app_module.db.session.get(app_module.User, user_id)
                if user:
                    app_module.db.session.delete(user)
            app_module.db.session.commit()

    def _caps(self, user_id):
        with self.app.app_context():
            return app_module.get_dashboard_capabilities(app_module.db.session.get(app_module.User, user_id))

    def _client(self, user_id):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def test_developer_gets_engineer_flags_only(self):
        caps = self._caps(self.developer_id)
        self.assertTrue(caps['has_engineer_profile'])
        self.assertTrue(caps['admin_view'], 'admin shortcuts stay')
        self.assertFalse(caps['manager_view'])
        self.assertFalse(caps['hybrid_view'])

    def test_developer_dashboard_renders_work_orders_without_manager_section(self):
        body = self._client(self.developer_id).get('/').get_data(as_text=True)
        self.assertIn('data-dashboard-section="engineer-work-orders"', body)
        self.assertNotIn('data-dashboard-section="manager-executive"', body)
        self.assertNotIn('dashboard-scope-divider', body)

    def test_developer_permissions_are_unchanged(self):
        self.assertEqual(self._client(self.developer_id).get('/get_manager_overview').status_code, 200)
        with self.app.app_context():
            user = app_module.db.session.get(app_module.User, self.developer_id)
            self.assertTrue(app_module.is_manager_dashboard_user(user))
            self.assertTrue(app_module.is_admin_authorized(user))

    def test_other_admin_with_profile_keeps_hybrid_view(self):
        with self.app.app_context():
            other = app_module.db.session.get(app_module.User, self.other_admin_id)
            self.assertFalse(app_module.is_engineer_primary_user(other))
        caps = self._caps(self.other_admin_id)
        self.assertTrue(caps['manager_view'])
        self.assertTrue(caps['hybrid_view'])


if __name__ == '__main__':
    unittest.main()
