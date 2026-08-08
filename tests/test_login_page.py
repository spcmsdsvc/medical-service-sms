import os
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]

# Pin an isolated database BEFORE importing app.py. Without this the import would
# open the real scheduler.db, which must never be touched by the test suite.
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_login_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402
from tests.sw_cache_version import assert_cache_version_at_least  # noqa: E402


class LoginSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.login_source = (ROOT / 'templates' / 'login.html').read_text(encoding='utf-8')
        cls.forgot_source = (ROOT / 'templates' / 'forgot_password.html').read_text(encoding='utf-8')
        cls.reset_source = (ROOT / 'templates' / 'reset_password.html').read_text(encoding='utf-8')
        cls.auth_css = (ROOT / 'static' / 'css' / 'app-auth.css').read_text(encoding='utf-8')

    def test_deactivated_accounts_are_reported_instead_of_failing_silently(self):
        # login_user() returns False for inactive users. The route must not ignore
        # that and redirect anyway, which previously looked like a wrong password.
        self.assertIn('logged_in = login_user(', self.app_source)
        self.assertIn('if not logged_in:', self.app_source)
        self.assertIn('This account has been deactivated.', self.app_source)

    def test_username_lookup_is_normalised(self):
        self.assertIn('def find_user_by_username(username):', self.app_source)
        self.assertIn('db.func.lower(User.username) == cleaned.lower()', self.app_source)
        self.assertIn('user_rec = find_user_by_username(username)', self.app_source)

    def test_unknown_usernames_still_run_a_hash_comparison(self):
        self.assertIn('DUMMY_PASSWORD_HASH', self.app_source)
        self.assertIn('check_password_hash(DUMMY_PASSWORD_HASH, password)', self.app_source)

    def test_rate_limiting_is_wired_without_a_global_default(self):
        self.assertIn('from flask_limiter import Limiter', self.app_source)
        self.assertIn('from flask_limiter.util import get_remote_address', self.app_source)
        self.assertIn('limiter = Limiter(', self.app_source)
        self.assertIn("@limiter.limit('10 per minute; 60 per hour', methods=['POST'])", self.app_source)
        self.assertIn('@app.errorhandler(429)', self.app_source)
        # A blanket limit across 356 routes would break offline TSR sync retries,
        # so the Limiter must never be constructed with default_limits.
        self.assertNotIn('default_limits=', self.app_source)

    def test_last_login_migration_is_additive(self):
        self.assertIn('last_login_at = db.Column(db.DateTime, nullable=True)', self.app_source)
        self.assertIn(
            "('last_login_at', \"ALTER TABLE user ADD COLUMN last_login_at DATETIME\")",
            self.app_source
        )
        self.assertNotIn('DROP COLUMN last_login_at', self.app_source)

    def test_login_inputs_are_mobile_safe(self):
        for marker in (
            'autocomplete="username"',
            'autocomplete="current-password"',
            'autocapitalize="none"',
            'autocorrect="off"',
            'spellcheck="false"',
        ):
            self.assertIn(marker, self.login_source)

    def test_password_toggle_is_a_real_button(self):
        # Per the frontend baseline: a real button, so it can never submit the form
        # and stays reachable by keyboard.
        self.assertIn('<button type="button"', self.login_source)
        self.assertIn('id="toggle-password"', self.login_source)
        self.assertIn('aria-label="Show password"', self.login_source)

    def test_login_page_has_capslock_offline_and_submit_guard(self):
        for marker in (
            'id="capslock-hint"',
            "getModifierState('CapsLock')",
            'id="offline-banner"',
            "window.addEventListener('offline'",
            'submitButton.disabled = true;',
        ):
            self.assertIn(marker, self.login_source)

    def test_login_page_uses_theme_variables_instead_of_hardcoded_pink(self):
        self.assertNotIn('#d63384', self.login_source)
        self.assertNotIn('#d63384', self.auth_css)
        self.assertIn('var(--app-surface)', self.auth_css)
        self.assertIn('var(--app-text)', self.auth_css)
        self.assertIn('--login-accent: var(--app-primary)', self.auth_css)
        self.assertIn(':root[data-app-theme="dark"]', self.auth_css)

    def test_forgot_password_link_and_pages_exist(self):
        self.assertIn("url_for('forgot_password')", self.login_source)
        self.assertIn("@app.route('/forgot_password', methods=['GET', 'POST'])", self.app_source)
        self.assertIn("@app.route('/reset_password/<token>', methods=['GET', 'POST'])", self.app_source)
        self.assertIn('name="confirm_password"', self.reset_source)
        self.assertIn('autocomplete="new-password"', self.reset_source)
        self.assertIn('Back to sign in', self.forgot_source)

    def test_reset_flow_does_not_leak_account_existence(self):
        self.assertIn('PASSWORD_RESET_GENERIC_CONFIRMATION', self.app_source)
        self.assertIn('contact your administrator', app_module.PASSWORD_RESET_GENERIC_CONFIRMATION.lower())

    def test_login_redirects_stay_no_store_but_the_page_is_storable(self):
        # The after_request guard exists to stop a 302 to /login being cached under a
        # protected URL. That must survive; only the signed-out GET becomes storable.
        self.assertIn('def prevent_login_redirect_cache(response):', self.app_source)
        self.assertIn('is_signed_out_login_page', self.app_source)
        self.assertIn('response.status_code in {301, 302, 303, 307, 308}', self.app_source)

    def test_offline_login_shell_is_cached_and_version_bumped(self):
        self.assertIn("'/login',", self.app_source)
        self.assertIn("'/static/css/app-auth.css',", self.app_source)
        # Offline login shipped at v39. Assert the floor, not the literal, so a later
        # cache bump does not break this test the way the old v35 literals did.
        assert_cache_version_at_least(self, 39, self.app_source)
        # The login document must still never be written to the runtime cache.
        self.assertIn('function isLoginLikeResponse(request, response)', self.app_source)
        self.assertIn("const cachedLogin = await shellCache.match('/login');", self.app_source)


class PasswordResetTokenTests(unittest.TestCase):
    """Functional coverage for the reset token helpers against an isolated DB."""

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.ctx = cls.app.app_context()
        cls.ctx.push()
        app_module.db.create_all()

    @classmethod
    def tearDownClass(cls):
        app_module.db.session.remove()
        cls.ctx.pop()

    def _make_user(self, username, password='initial-password', is_active=True):
        existing = app_module.User.query.filter_by(username=username).first()
        if existing:
            app_module.db.session.delete(existing)
            app_module.db.session.commit()

        user = app_module.User(
            username=username,
            password=app_module.generate_password_hash(password),
            role='engineer',
            is_active=is_active
        )
        app_module.db.session.add(user)
        app_module.db.session.commit()
        return user

    def test_username_lookup_tolerates_case_and_whitespace(self):
        self._make_user('reset_case_user')

        self.assertIsNotNone(app_module.find_user_by_username('reset_case_user'))
        self.assertIsNotNone(app_module.find_user_by_username('  reset_case_user  '))
        self.assertIsNotNone(app_module.find_user_by_username('Reset_Case_User'))
        self.assertIsNone(app_module.find_user_by_username(''))
        self.assertIsNone(app_module.find_user_by_username(None))
        self.assertIsNone(app_module.find_user_by_username('no_such_account_here'))

    def test_reset_token_round_trips(self):
        user = self._make_user('reset_token_user')
        token = app_module.build_password_reset_token(user)
        self.assertTrue(token)

        resolved = app_module.load_user_from_password_reset_token(token)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.id, user.id)

    def test_reset_token_is_single_use(self):
        user = self._make_user('reset_single_use_user')
        token = app_module.build_password_reset_token(user)
        self.assertIsNotNone(app_module.load_user_from_password_reset_token(token))

        # Changing the password changes the embedded hash marker, which retires
        # any outstanding token without needing a used-token table.
        user.password = app_module.generate_password_hash('a-brand-new-password')
        app_module.db.session.commit()

        self.assertIsNone(app_module.load_user_from_password_reset_token(token))

    def test_reset_token_rejects_tampering_and_deactivated_accounts(self):
        user = self._make_user('reset_tamper_user')
        token = app_module.build_password_reset_token(user)

        self.assertIsNone(app_module.load_user_from_password_reset_token(token + 'x'))
        self.assertIsNone(app_module.load_user_from_password_reset_token(''))
        self.assertIsNone(app_module.load_user_from_password_reset_token(None))

        user.is_active = False
        app_module.db.session.commit()
        self.assertIsNone(app_module.load_user_from_password_reset_token(token))


class LoginNextTargetTests(unittest.TestCase):
    """`next` must send the user where they were going, and nowhere else.

    Bookmarking /timeline, being bounced to /login and then landing on the
    dashboard was the reported papercut. The redirect is only safe if the target
    is validated as a local path, or the fix trades a papercut for an open
    redirect.
    """

    SAFE_TARGETS = (
        '/timeline',
        '/timeline?offset=2&branch=Cebu',
        '/offline-tsr',
        '/analytics_page',
        '/',
    )

    # Each of these must be refused. The first group would take a user off this
    # site entirely; the second would be actively unhelpful to land on.
    UNSAFE_TARGETS = (
        'https://evil.example.com/steal',
        'http://evil.example.com',
        '//evil.example.com',            # protocol-relative: no scheme, still off-site
        '/\\evil.example.com',           # several browsers normalize this into a host
        '\\\\evil.example.com',
        'javascript:alert(1)',
        'data:text/html,<script>alert(1)</script>',
        '/timeline\r\nSet-Cookie: x=1',  # header smuggling via a control character
        'timeline',                      # relative, so it depends on the current path
        '',
        None,
        '/logout',                       # would undo the sign-in that just happened
        '/login',
        '/login?next=/timeline',
        '/forgot_password',
        '/reset_password/sometoken',
    )

    def test_safe_local_paths_are_accepted(self):
        for target in self.SAFE_TARGETS:
            with self.subTest(target=target):
                self.assertEqual(app_module.resolve_safe_next_target(target), target)

    def test_off_site_and_unhelpful_targets_are_refused(self):
        for target in self.UNSAFE_TARGETS:
            with self.subTest(target=target):
                self.assertEqual(app_module.resolve_safe_next_target(target), '')

    def test_a_path_that_merely_starts_with_a_blocked_name_is_still_allowed(self):
        # /logout_report is not /logout. A naive startswith() check would refuse
        # it, so the boundary is asserted explicitly.
        self.assertEqual(app_module.resolve_safe_next_target('/logout_report'), '/logout_report')
        self.assertEqual(app_module.resolve_safe_next_target('/logins'), '/logins')

    def test_an_overlong_target_is_refused(self):
        self.assertEqual(app_module.resolve_safe_next_target('/' + 'a' * 600), '')

    def test_the_route_reads_next_from_the_form_on_post_and_the_query_on_get(self):
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        self.assertIn('next_target = resolve_safe_next_target(', source)
        self.assertIn("request.form.get('next') if request.method == 'POST' else request.args.get('next')", source)
        # The validated target must win over the role default, or the papercut
        # is still there.
        self.assertIn('if next_target:', source)
        self.assertIn('response = redirect(next_target)', source)
        # And the GET must hand it to the template, or a failed first attempt
        # silently drops the destination.
        self.assertIn("render_template('login.html', next_target=next_target)", source)

    def test_the_form_carries_next_through_a_failed_attempt(self):
        login_source = (ROOT / 'templates' / 'login.html').read_text(encoding='utf-8')
        self.assertIn('name="next"', login_source)
        self.assertIn('{% if next_target %}', login_source)


class LoginNextRoundTripTests(unittest.TestCase):
    """The whole bounce-and-return journey, end to end.

    The source assertions above cannot see the one thing this depends on: the
    exact shape Flask-Login uses for `next`. It arrives percent-encoded
    (`/login?next=%2Ftimeline%3Foffset%3D2`), so if that ever changes, the
    helper would silently start refusing every real target and every user would
    quietly land on the dashboard again -- the original papercut, restored, with
    all the source-level tests still green.
    """

    PASSWORD = 'round-trip-probe-123'

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.ctx = cls.app.app_context()
        cls.ctx.push()
        app_module.db.create_all()
        cls.original_csrf = cls.app.config.get('WTF_CSRF_ENABLED')
        cls.app.config['WTF_CSRF_ENABLED'] = False

        existing = app_module.User.query.filter_by(username='login_next_probe').first()
        if existing:
            app_module.db.session.delete(existing)
            app_module.db.session.commit()
        cls.user = app_module.User(
            username='login_next_probe',
            password=app_module.generate_password_hash(cls.PASSWORD),
            role='staff',
            is_active=True,
        )
        app_module.db.session.add(cls.user)
        app_module.db.session.commit()

    @classmethod
    def tearDownClass(cls):
        # Leaving this account behind would let it drift into another module's
        # fixtures; the suite shares one database within a run.
        user = app_module.User.query.filter_by(username='login_next_probe').first()
        if user:
            app_module.db.session.delete(user)
            app_module.db.session.commit()
        if cls.original_csrf is not None:
            cls.app.config['WTF_CSRF_ENABLED'] = cls.original_csrf
        app_module.db.session.remove()
        cls.ctx.pop()

    def _sign_in(self, client, path='/login', **extra):
        data = {'username': 'login_next_probe', 'password': self.PASSWORD}
        data.update(extra)
        return client.post(path, data=data)

    def test_a_bookmarked_page_is_returned_to_after_signing_in(self):
        client = self.app.test_client()

        bounced = client.get('/timeline?offset=2&branch=Cebu')
        self.assertEqual(bounced.status_code, 302)
        location = bounced.headers.get('Location', '')
        self.assertIn('next=', location)

        # The login page must carry the destination into the form, or a single
        # mistyped password loses it.
        page = client.get(location)
        self.assertIn('name="next"', page.get_data(as_text=True))

        landed = self._sign_in(client, location, next='/timeline?offset=2&branch=Cebu')
        self.assertEqual(landed.status_code, 302)
        self.assertEqual(landed.headers.get('Location'), '/timeline?offset=2&branch=Cebu')

    def test_without_a_next_the_role_default_still_wins(self):
        # The control: proves the test above is not passing because every
        # sign-in happens to redirect somewhere.
        landed = self._sign_in(self.app.test_client())
        self.assertEqual(landed.status_code, 302)
        self.assertEqual(landed.headers.get('Location'), '/')

    def test_an_off_site_next_is_ignored_rather_than_followed(self):
        landed = self._sign_in(self.app.test_client(), next='https://evil.example.com/steal')
        self.assertEqual(landed.status_code, 302)
        self.assertEqual(landed.headers.get('Location'), '/')

    def test_a_failed_attempt_does_not_lose_the_destination(self):
        client = self.app.test_client()
        refused = client.post('/login', data={
            'username': 'login_next_probe',
            'password': 'definitely-not-the-password',
            'next': '/timeline',
        })
        self.assertEqual(refused.status_code, 200)
        self.assertIn('value="/timeline"', refused.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
