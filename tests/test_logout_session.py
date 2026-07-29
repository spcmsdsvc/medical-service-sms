import os
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]

# Pin an isolated database BEFORE importing app.py. Without this the import would
# open the real scheduler.db, which must never be touched by the test suite.
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_logout_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402


def deleted_cookie_names(response):
    """Cookie names the response instructs the browser to drop.

    Werkzeug expresses a deletion as Set-Cookie with an empty value plus either
    Max-Age=0 or an expiry in the past, so match on that rather than on any one
    spelling.
    """
    names = set()
    for header in response.headers.getlist('Set-Cookie'):
        name, _, remainder = header.partition('=')
        value = remainder.split(';', 1)[0]
        lowered = header.lower()
        is_deletion = (
            value == ''
            and ('max-age=0' in lowered or 'expires=thu, 01 jan 1970' in lowered)
        )
        if is_deletion:
            names.add(name.strip())
    return names


class LogoutSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')

    def test_logout_route_clears_every_sign_in_credential(self):
        # The session cookie goes with session.clear(), the remember token and the
        # PWA restore cookie each need an explicit deletion.
        self.assertIn('def clear_remember_cookie(response):', self.app_source)
        self.assertIn('    clear_remember_cookie(response)', self.app_source)
        self.assertIn('return clear_pwa_login_cookie(response)', self.app_source)

    def test_remember_cookie_name_is_read_from_config(self):
        # REMEMBER_COOKIE_NAME is overridable by environment variable, so a literal
        # here would delete the wrong cookie wherever it has been customised.
        self.assertIn("app.config.get('REMEMBER_COOKIE_NAME'", self.app_source)
        helper_start = self.app_source.index('def clear_remember_cookie(response):')
        helper_end = self.app_source.index('def restore_user_from_pwa_login_cookie', helper_start)
        helper = self.app_source[helper_start:helper_end]
        self.assertNotIn("'medical_service_remember_token'", helper)

    def test_logout_is_never_written_to_an_offline_cache(self):
        # /logout returns a redirect, and isLoginLikeResponse() refuses to cache any
        # redirected response. This fix must not change that.
        self.assertIn('if (response && response.redirected) return true;', self.app_source)
        # And the PWA restore cookie must keep skipping /logout, or it would sign the
        # user straight back in on the redirect.
        self.assertIn("if request.path == '/logout':", self.app_source)


class LogoutSessionTests(unittest.TestCase):
    """Sign in for real, sign out, and check what the browser is left holding."""

    PASSWORD = 'LogoutTest123'

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.app.config['TESTING'] = True
        # /login is rate limited at 10 per minute. Several sign-ins in one class
        # would trip it and fail for a reason none of these tests care about.
        app_module.limiter.enabled = False
        with cls.app.app_context():
            app_module.db.create_all()

    @classmethod
    def tearDownClass(cls):
        app_module.limiter.enabled = True

    @property
    def remember_cookie_name(self):
        return self.app.config.get('REMEMBER_COOKIE_NAME')

    def _make_user(self, username, is_active=True):
        with self.app.app_context():
            existing = app_module.User.query.filter_by(username=username).first()
            if existing:
                app_module.db.session.delete(existing)
                app_module.db.session.commit()

            user = app_module.User(
                username=username,
                password=app_module.generate_password_hash(self.PASSWORD),
                role='engineer',
                is_active=is_active
            )
            app_module.db.session.add(user)
            app_module.db.session.commit()
            return user.id

    def _sign_in(self, username):
        client = self.app.test_client()
        response = client.post(
            '/login',
            data={'username': username, 'password': self.PASSWORD}
        )
        self.assertEqual(response.status_code, 302)
        return client

    def test_signing_in_issues_a_remember_token(self):
        # Guards the premise of every test below: /login always passes remember=True.
        self._make_user('logout_premise_user')
        client = self._sign_in('logout_premise_user')
        self.assertIsNotNone(client.get_cookie(self.remember_cookie_name))

    def test_logout_deletes_the_remember_cookie(self):
        """The assertion that would have caught this bug.

        logout_user() sets session['_remember'] = 'clear' and leaves the deletion to
        an after_request handler; session.clear() on the next line erased the flag, so
        no deletion was ever emitted for the remember token.
        """
        self._make_user('logout_remember_user')
        client = self._sign_in('logout_remember_user')

        response = client.get('/logout')
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.remember_cookie_name, deleted_cookie_names(response))

    def test_logout_still_deletes_the_session_and_pwa_cookies(self):
        self._make_user('logout_all_cookies_user')
        client = self._sign_in('logout_all_cookies_user')

        deleted = deleted_cookie_names(client.get('/logout'))
        self.assertIn(self.app.config.get('SESSION_COOKIE_NAME'), deleted)
        self.assertIn(self.app.config.get('PWA_LOGIN_COOKIE_NAME'), deleted)

    def test_the_request_after_logout_is_unauthenticated(self):
        self._make_user('logout_next_request_user')
        client = self._sign_in('logout_next_request_user')
        self.assertEqual(client.get('/auth_status').status_code, 200)

        client.get('/logout')

        after = client.get('/auth_status')
        self.assertEqual(after.status_code, 302)
        self.assertIn('/login', after.headers.get('Location', ''))

    def test_the_remember_cookie_is_gone_from_the_client_jar(self):
        # The header assertion proves the instruction was sent; this proves a real
        # cookie jar acts on it.
        self._make_user('logout_jar_user')
        client = self._sign_in('logout_jar_user')
        self.assertIsNotNone(client.get_cookie(self.remember_cookie_name))

        client.get('/logout')

        self.assertIsNone(client.get_cookie(self.remember_cookie_name))

    def test_a_deactivated_account_cannot_ride_a_stale_token_back_in(self):
        """Deactivating an account has to dislodge an existing remember token.

        Without the fix the token outlived logout, so a deactivated user's next
        request re-authenticated them and the deactivation had no effect.
        """
        user_id = self._make_user('logout_deactivated_user')
        client = self._sign_in('logout_deactivated_user')
        client.get('/logout')

        with self.app.app_context():
            user = app_module.db.session.get(app_module.User, user_id)
            user.is_active = False
            app_module.db.session.commit()

        after = client.get('/auth_status')
        self.assertEqual(after.status_code, 302)
        self.assertIn('/login', after.headers.get('Location', ''))

    def test_logging_out_without_a_session_does_not_error(self):
        client = self.app.test_client()
        response = client.get('/logout')
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.remember_cookie_name, deleted_cookie_names(response))

    def test_logout_response_is_never_stored(self):
        self._make_user('logout_cache_header_user')
        client = self._sign_in('logout_cache_header_user')

        response = client.get('/logout')
        self.assertIn('no-store', response.headers.get('Cache-Control', ''))


if __name__ == '__main__':
    unittest.main()
