"""Sign-ins, failed and blocked sign-ins, and sign-outs are written to the Activity log.

Only the login form counts as a sign-in: PWA-cookie restores must not log, and an
unknown username is logged without the text that was typed.
"""

import os
import pathlib
import tempfile
import unittest
import uuid
from unittest.mock import patch

from flask import Response

TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_signin_activity_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB_PATH))
os.environ.setdefault("SECRET_KEY", "signin-activity-tests")

import app as app_module  # noqa: E402

ActivityLog = app_module.ActivityLog
PASSWORD = 'SigninTest123'


class SigninActivityLogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        # /login is rate limited; several attempts in one class would trip it.
        app_module.limiter.enabled = False
        with cls.app.app_context():
            app_module.db.create_all()

    @classmethod
    def tearDownClass(cls):
        app_module.limiter.enabled = True

    def setUp(self):
        self.username = f'signin_{uuid.uuid4().hex[:8]}'
        self.label = self.username.capitalize()
        with self.app.app_context():
            user = app_module.User(
                username=self.username,
                password=app_module.generate_password_hash(PASSWORD),
                role='engineer',
                is_active=True,
            )
            app_module.db.session.add(user)
            app_module.db.session.commit()
            self.user_id = user.id
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            user = app_module.db.session.get(app_module.User, self.user_id)
            if user:
                app_module.db.session.delete(user)
            ActivityLog.query.filter(ActivityLog.user == self.label).delete()
            app_module.db.session.commit()
            app_module.db.session.remove()

    def rows(self, user_label=None):
        with self.app.app_context():
            return [
                (row.user, row.action)
                for row in ActivityLog.query.filter(ActivityLog.user == (user_label or self.label)).all()
            ]

    def sign_in(self, password=PASSWORD, username=None):
        return self.client.post('/login', data={'username': username or self.username, 'password': password})

    def set_active(self, value):
        with self.app.app_context():
            app_module.db.session.get(app_module.User, self.user_id).is_active = value
            app_module.db.session.commit()

    def test_successful_sign_in_is_logged_once(self):
        response = self.sign_in()
        self.assertIn(response.status_code, (302, 303))
        self.assertEqual(self.rows(), [(self.label, 'Signed in')])

    def test_wrong_password_is_logged_against_the_account(self):
        self.sign_in(password='not-the-password')
        self.assertEqual(self.rows(), [(self.label, 'Failed sign-in: wrong password')])

    def test_deactivated_account_is_logged_as_blocked(self):
        self.set_active(False)
        self.sign_in()
        self.assertEqual(self.rows(), [(self.label, 'Blocked sign-in: account deactivated')])

    def test_refused_login_is_logged_as_blocked(self):
        with patch.object(app_module, 'login_user', return_value=False):
            self.sign_in()
        self.assertEqual(self.rows(), [(self.label, 'Blocked sign-in: account cannot sign in')])

    def test_unknown_username_is_logged_without_the_typed_text(self):
        typed = f'zz-typed-{uuid.uuid4().hex}'
        with self.app.app_context():
            before = ActivityLog.query.filter(ActivityLog.action == 'Failed sign-in: unknown username').count()
        self.sign_in(username=typed)
        with self.app.app_context():
            after = ActivityLog.query.filter(ActivityLog.action == 'Failed sign-in: unknown username').count()
            leaked = ActivityLog.query.filter(
                (ActivityLog.user.ilike(f'%{typed}%')) | (ActivityLog.action.ilike(f'%{typed}%'))
            ).count()
        self.assertEqual(after - before, 1)
        self.assertEqual(leaked, 0)
        self.assertEqual(self.rows('Unknown')[-1], ('Unknown', 'Failed sign-in: unknown username'))

    def test_sign_out_is_logged(self):
        self.sign_in()
        self.client.get('/logout')
        self.assertEqual(self.rows(), [(self.label, 'Signed in'), (self.label, 'Signed out')])

    def test_logout_while_signed_out_logs_nothing(self):
        with self.app.app_context():
            before = ActivityLog.query.filter(ActivityLog.action == 'Signed out').count()
        self.client.get('/logout')
        with self.app.app_context():
            after = ActivityLog.query.filter(ActivityLog.action == 'Signed out').count()
        self.assertEqual(after, before)

    def test_pwa_cookie_restore_is_not_a_sign_in(self):
        cookie_name = self.app.config.get('PWA_LOGIN_COOKIE_NAME', 'medical_service_pwa_login')
        with self.app.test_request_context():
            user = app_module.db.session.get(app_module.User, self.user_id)
            cookie_response = app_module.set_pwa_login_cookie(Response(), user)
        header = next(h for h in cookie_response.headers.getlist('Set-Cookie') if h.startswith(cookie_name + '='))
        self.client.set_cookie(cookie_name, header.split(';', 1)[0].split('=', 1)[1])
        status = self.client.get('/auth_status')
        self.assertEqual(status.status_code, 200)
        self.assertTrue(status.get_json().get('restored_from_pwa_cookie'))
        self.assertEqual(self.rows(), [])

    def test_sign_in_texts_classify_as_security(self):
        for text in (
            'Signed in',
            'Signed out',
            'Failed sign-in: wrong password',
            'Failed sign-in: unknown username',
            'Blocked sign-in: account deactivated',
            'Blocked sign-in: account cannot sign in',
        ):
            self.assertEqual(app_module.classify_activity_action(text), 'Security', text)
            self.assertEqual(app_module.classify_activity_verb(text), 'Security', text)


if __name__ == '__main__':
    unittest.main()
