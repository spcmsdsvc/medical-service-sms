import os
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Pin an isolated database BEFORE importing app.py, so the suite can never open the
# real scheduler.db.
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_layout_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402
from tests.sw_cache_version import assert_cache_version_at_least  # noqa: E402


class SidebarSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.layout = (ROOT / 'templates' / 'layout.html').read_text(encoding='utf-8')
        cls.shell_css = (ROOT / 'static' / 'css' / 'app-shell.css').read_text(encoding='utf-8')

    def test_navigation_access_comes_from_server_helpers(self):
        self.assertIn('def inject_navigation_access():', self.app_source)
        for key, helper in (
            ('nav_is_admin', 'is_admin_authorized()'),
            ('nav_is_superadmin', 'is_superadmin_user()'),
            ('nav_is_approval_center_user', 'is_approval_center_user()'),
            ('nav_is_approver_only', 'is_approver_only_user()'),
            ('nav_can_access_accounting_center', 'can_access_accounting_center()'),
        ):
            self.assertIn(f"'{key}': {helper}", self.app_source)

    def test_template_no_longer_reimplements_role_logic(self):
        # The old inline flags were looser than the server and showed links that
        # redirected away. They must not come back.
        for banned in (
            "'hanna'",
            "'diary'",
            "'rodito'",
            'is_scheduler_user',
            'approval_paths',
            "current_user.role in ['superadmin', 'regional_admin']",
        ):
            self.assertNotIn(banned, self.layout)

        for injected in (
            'nav_is_admin',
            'nav_is_engineer',
            'nav_is_approval_center_user',
            'nav_is_approver_only',
            'nav_can_access_accounting_center',
        ):
            self.assertIn(injected, self.layout)

    def test_nav_links_render_through_one_macro(self):
        self.assertIn('{% macro nav_link(', self.layout)
        # Cash Advance previously had neither an active class nor aria-current.
        self.assertIn("nav_link('/cash_advance'", self.layout)
        self.assertIn('aria-current="page"', self.layout)

    def test_accessibility_landmarks_and_controls(self):
        self.assertIn('class="skip-to-content"', self.layout)
        self.assertIn('href="#main-content"', self.layout)
        self.assertIn('<nav class="sidebar-nav" aria-label="Main">', self.layout)
        self.assertIn('id="sidebar-toggle-desktop"', self.layout)
        self.assertIn('aria-controls="sidebar"', self.layout)
        # The desktop toggle used to be a bare <i> with onclick: unfocusable.
        self.assertNotIn('<i class="fa-solid fa-bars toggle-btn"', self.layout)
        self.assertIn("event.key !== 'Escape'", self.layout)
        self.assertIn("scrollIntoView({block: 'nearest'})", self.layout)

    def test_sidebar_css_is_consolidated_into_one_stylesheet(self):
        self.assertIn("css/app-shell.css", self.layout)
        # The inline <style> block that held three generations of sidebar rules is gone.
        self.assertNotIn('<style>', self.layout)
        # Each of these was previously declared three times.
        self.assertEqual(self.shell_css.count('\n.sidebar-subnav {'), 1)
        self.assertEqual(self.shell_css.count('\n.sidebar-calendar-row {'), 1)
        # Dead hardcoded pink, already overridden by app-themes.css.
        self.assertNotIn('#d63384', self.layout)
        self.assertNotIn('#d63384', self.shell_css)

    def test_sidebar_uses_theme_variables_and_flexible_rows(self):
        self.assertIn('--sidebar-hover', self.shell_css)
        self.assertIn('var(--app-primary)', self.shell_css)
        # Fixed `height: 58px` truncated long labels; rows must be able to grow.
        self.assertNotIn('height: 58px', self.shell_css)
        self.assertIn('min-height: var(--sidebar-row-height)', self.shell_css)
        # A blanket `transition: all` on body animated every property and caused
        # visible jank on theme switch. Match declarations only, not the comment
        # that explains the change.
        self.assertNotIn('\n    transition: all', self.shell_css)
        self.assertIn('transition: background-color 0.3s ease, color 0.3s ease;', self.shell_css)

    def test_long_subnav_labels_are_single_line_with_ellipsis(self):
        subnav = self.shell_css.split('\n.sidebar-subnav a {', 1)[1].split('\n}', 1)[0]
        shared_rows = self.shell_css.split('\n.sidebar a,', 1)[1].split('\n}', 1)[0]
        label = self.shell_css.split('\n.sidebar a span,', 1)[1].split('\n}', 1)[0]
        self.assertIn('padding: 0 20px 0 48px;', subnav)
        self.assertNotIn('white-space: normal;', subnav)
        self.assertNotIn('\n.sidebar-subnav a span {', self.shell_css)
        self.assertIn('white-space: nowrap;', shared_rows)
        self.assertIn('overflow: hidden;', label)
        self.assertIn('text-overflow: ellipsis;', label)
        self.assertIn("'Reimburse / Liquidation'", self.layout)
        self.assertIn("'Service Documents'", self.layout)
        self.assertIn('font-size: 0.84rem;', subnav)

    def test_sidebar_resize_handle_has_accessible_separator_contract(self):
        self.assertIn('id="sidebar-resize-handle"', self.layout)
        self.assertIn('class="sidebar-resize-handle"', self.layout)
        self.assertIn('role="separator"', self.layout)
        self.assertIn('tabindex="0"', self.layout)
        self.assertIn('aria-orientation="vertical"', self.layout)
        self.assertIn('aria-valuemin="200"', self.layout)
        self.assertIn('aria-valuemax="360"', self.layout)
        self.assertIn('aria-valuenow="240"', self.layout)

    def test_sidebar_resize_css_preserves_desktop_layout_and_mobile_cap(self):
        for token in (
            '--sidebar-width: 240px;',
            '--sidebar-width-min: 200px;',
            '--sidebar-width-max: 360px;',
            '--sidebar-width-step: 20px;',
            '--sidebar-width-default: 240px;',
        ):
            self.assertIn(token, self.shell_css)
        self.assertIn('.sidebar-resize-handle {', self.shell_css)
        self.assertIn('cursor: ew-resize;', self.shell_css)
        self.assertIn('.sidebar-resize-handle:hover', self.shell_css)
        self.assertIn('.sidebar-resize-handle:focus-visible', self.shell_css)
        self.assertIn('body.sidebar-resizing', self.shell_css)
        self.assertIn('transition: none !important;', self.shell_css)
        self.assertIn('user-select: none !important;', self.shell_css)
        self.assertIn('margin-left: var(--sidebar-width);', self.shell_css)

        mobile = self.shell_css.split('@media (max-width: 992px)', 1)[1]
        self.assertIn('width: min(82vw, 240px);', mobile)
        self.assertIn('.sidebar-resize-handle {', mobile)
        self.assertIn('display: none;', mobile)

    def test_sidebar_resize_controller_handles_bounds_persistence_and_inputs(self):
        for token in (
            "const SIDEBAR_RESIZE_STORAGE_KEY = 'medical_service_sidebar_width';",
            'const SIDEBAR_WIDTH_MIN = 200;',
            'const SIDEBAR_WIDTH_MAX = 360;',
            'const SIDEBAR_WIDTH_STEP = 20;',
            'const SIDEBAR_WIDTH_DEFAULT = 240;',
            'function clampSidebarWidth(value)',
            'Number.isFinite(parsed)',
            'localStorage.getItem(SIDEBAR_RESIZE_STORAGE_KEY)',
            'localStorage.setItem(SIDEBAR_RESIZE_STORAGE_KEY, String(normalized))',
            "setProperty('--sidebar-width', `${normalized}px`)",
            "setAttribute('aria-valuenow', String(normalized))",
            'window.innerWidth >= 993',
            "event.clientX - sidebar.getBoundingClientRect().left",
            "handle.setPointerCapture(event.pointerId)",
            'handle.releasePointerCapture(activePointerId)',
            "addEventListener('pointerdown'",
            "addEventListener('pointermove'",
            "addEventListener('pointerup'",
            "addEventListener('pointercancel'",
            "addEventListener('lostpointercapture'",
            "case 'ArrowLeft':",
            "case 'ArrowDown':",
            "case 'ArrowRight':",
            "case 'ArrowUp':",
            "case 'Home':",
            "addEventListener('dblclick'",
        ):
            self.assertIn(token, self.layout)
        self.assertIn('Math.min(', self.layout)
        self.assertIn('Math.max(SIDEBAR_WIDTH_MIN, Math.round(numeric))', self.layout)
        self.assertIn('return SIDEBAR_WIDTH_DEFAULT;', self.layout)

    def test_shell_asset_and_service_worker_versions_are_bumped(self):
        self.assertIn("app-shell.css') }}?v=3", self.layout)
        self.assertIn("medical-service-pwa-offline-navigation-v122-sidebar-resize", self.app_source)
        assert_cache_version_at_least(self, 122, self.app_source)

    def test_pending_summary_endpoint_is_lightweight(self):
        self.assertIn("@app.route('/api/nav/pending-summary')", self.app_source)
        endpoint = self.app_source.split('def get_nav_pending_summary(')[1].split('@app.route')[0]
        # Must count, never materialise rows: this runs on every page load.
        self.assertIn('.count()', endpoint)
        self.assertNotIn('.all()', endpoint)
        self.assertIn('apply_assigned_approver_filter', endpoint)

    def test_shell_css_is_cached_and_version_bumped(self):
        self.assertIn("'/static/css/app-shell.css',", self.app_source)
        assert_cache_version_at_least(self, 122, self.app_source)


class SidebarRenderTests(unittest.TestCase):
    """Render the real shell through the test client.

    Source greps cannot prove that a role actually sees the right links, and the
    nav_link() macro means the hrefs no longer appear literally in the template.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            app_module.db.create_all()

    def _make_user(self, username, role, **kwargs):
        with self.app.app_context():
            existing = app_module.User.query.filter_by(username=username).first()
            if existing:
                app_module.db.session.delete(existing)
                app_module.db.session.commit()

            user = app_module.User(
                username=username,
                password=app_module.generate_password_hash('LayoutTest123'),
                role=role,
                is_active=kwargs.pop('is_active', True),
                **kwargs
            )
            app_module.db.session.add(user)
            app_module.db.session.commit()
            return user.id

    def _render_dashboard_as(self, user_id):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client.get('/', follow_redirects=True).get_data(as_text=True)

    def test_engineer_does_not_see_admin_only_links(self):
        user_id = self._make_user('layout_engineer', 'engineer')
        html = self._render_dashboard_as(user_id)
        self.assertIn('Dashboard', html)
        self.assertNotIn('/activity_page', html)
        self.assertNotIn('/analytics_page', html)

    def test_superadmin_role_without_username_allowlist_gets_no_admin_links(self):
        """The headline divergence this work fixes.

        is_superadmin_user() requires membership in SUPERADMIN_USERNAMES, but the old
        sidebar only checked `role`. An account with role='superadmin' outside that set
        saw Admin, Analytics and Personnel, then was redirected away by every one.
        """
        self.assertNotIn('layout_fake_super', app_module.SUPERADMIN_USERNAMES)
        user_id = self._make_user('layout_fake_super', 'superadmin')
        html = self._render_dashboard_as(user_id)
        self.assertNotIn('/activity_page', html)
        self.assertNotIn('/analytics_page', html)

    def test_active_link_carries_aria_current(self):
        user_id = self._make_user('layout_aria_user', 'engineer')
        html = self._render_dashboard_as(user_id)
        self.assertIn('aria-current="page"', html)
        self.assertIn('skip-to-content', html)

    def test_user_footer_replaces_the_logout_row(self):
        user_id = self._make_user('layout_footer_user', 'engineer')
        html = self._render_dashboard_as(user_id)
        self.assertIn('sidebar-user', html)
        self.assertIn('href="/logout"', html)
        self.assertIn('Engineer', html)
        self.assertNotIn('Logout (layout_footer_user)', html)

    def test_pending_summary_returns_zeros_for_a_non_approver(self):
        user_id = self._make_user('layout_plain_user', 'engineer')
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True

        response = client.get('/api/nav/pending-summary')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['approvals_pending'], 0)
        self.assertIsInstance(payload['my_requests_action'], int)


if __name__ == '__main__':
    unittest.main()
