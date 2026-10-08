import os
import pathlib
import subprocess
import tempfile
import textwrap
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
        self.assertIn("app-shell.css') }}?v=14", self.layout)
        assert_cache_version_at_least(self, 158, self.app_source)

    def test_icon_rail_and_docks_follow_the_shell_offset(self):
        self.assertIn('--sidebar-rail-width: 64px;', self.shell_css)
        self.assertIn('html[data-sidebar-collapsed="true"] {\n        --shell-offset: var(--sidebar-rail-width);', self.shell_css)
        for name in ('reimbursement.html', 'travel_request.html', '_liquidation_base.html'):
            page = (ROOT / 'templates' / name).read_text(encoding='utf-8')
            self.assertIn('left: var(--shell-offset, var(--sidebar-width, 240px))', page, name)
            self.assertNotIn('left: var(--sidebar-width, 240px)', page, name)

    def test_rail_labels_stay_named_and_flyouts_sit_above_sticky_headers(self):
        rail_labels = self.shell_css.split('.sidebar .sidebar-calendar-main > span {', 1)[1].split('}', 1)[0]
        self.assertNotIn('display: none', rail_labels)
        self.assertIn('clip: rect(0 0 0 0);', rail_labels)
        desktop = self.shell_css.split('@media (min-width: 993px) {', 1)[1]
        self.assertIn('.sidebar {\n        z-index: 1045;', desktop.split('html[data-sidebar-collapsed="true"] {', 1)[0])
        self.assertNotIn('<i class="fa-solid fa-chevron-right sidebar-section-arrow"></i>', self.layout)

    def test_quiet_rows_and_one_active_signal(self):
        self.assertNotIn('border-bottom: 1px solid var(--sidebar-divider)', self.shell_css)
        self.assertIn('--sidebar-row-height: 44px;', self.shell_css)
        parent = self.shell_css.split('.sidebar-section-toggle.active {', 1)[1].split('}', 1)[0]
        self.assertNotIn('border-left', parent)
        self.assertIn('body.sidebar-collapsed .sidebar .sidebar-section-toggle.active {', self.shell_css)

    def test_rail_group_flyouts_replace_the_peek(self):
        self.assertNotIn('sidebar-peek', self.layout)
        self.assertNotIn('sidebar-peek', self.shell_css)
        self.assertIn('(function initSidebarFlyouts()', self.layout)
        self.assertIn('.sidebar-subnav.is-flyout-open', self.shell_css)
        # Each group's own subnav is the flyout, titled; Inventory is a subheading.
        for section in ('calendar', 'field-operations', 'reports-insights', 'records', 'inventory', 'admin'):
            opening = self.layout.split(f'<div id="{section}-sidebar-section"', 1)[1].split('\n', 2)[1]
            self.assertIn('class="sidebar-flyout-title"', opening, section)
        self.assertIn("nav_link('/timeline', 'fa-calendar-days', 'Calendar', extra_class='sidebar-flyout-only')", self.layout)
        self.assertIn('.is-flyout-open .sidebar-subnav-nested {\n        display: block !important;', self.shell_css)
        # The avatar opens an account flyout holding the tools the rail hides.
        self.assertIn('class="sidebar-user-avatar"\n                    aria-label="Account"', self.layout)
        account = self.layout.split('<div id="sidebar-user-flyout"', 1)[1].split('</div>', 1)[0]
        for part in ('sidebar-user-meta', 'appearance-header-button', 'changelog-header-button', 'href="/logout"'):
            self.assertIn(part, account)
        self.assertIn('id="sidebar-rail-tip"', self.layout)

    def test_rail_flyouts_open_from_keys_not_focus_and_rings_are_visible(self):
        flyouts = self.layout.split('(function initSidebarFlyouts()', 1)[1].split('})();', 1)[0]
        # Focus alone must not open a flyout, or Tab walks every link inside it.
        self.assertNotIn("addEventListener('focusin'", flyouts)
        for key in ("'ArrowRight'", "'ArrowDown'", "'ArrowUp'", "'ArrowLeft'", "'Escape'"):
            self.assertIn(key, flyouts)
        self.assertIn('if (event.detail === 0) focusItem(flyout, 0);', flyouts)
        # ArrowUp/ArrowDown also move between the rail's own icons.
        self.assertIn('const railIcons = () =>', flyouts)
        self.assertIn('icons[(index + step + icons.length) % icons.length].focus();', flyouts)
        # One light focus ring for the shell (the primary blue was 2.44:1).
        self.assertIn('--shell-focus-ring: #e2e8f0;', self.shell_css)
        ring = self.shell_css.split('.mobile-nav button:focus-visible {', 1)[1].split('}', 1)[0]
        self.assertIn('outline: 2px solid var(--shell-focus-ring) !important;', ring)
        self.assertIn('.sidebar button:focus-visible,', self.shell_css)

    def test_footer_logout_stays_an_icon_beside_the_username(self):
        css = (ROOT / 'static' / 'css' / 'app-shell.css').read_text(encoding='utf-8')
        logout = css.split('.sidebar .sidebar-logout {', 1)[1].split('}', 1)[0]
        self.assertIn('width: 34px;', logout)
        self.assertIn('padding: 0;', logout)
        self.assertIn('border-bottom: 0;', logout)

    def test_sidebar_visibility_preference_is_early_guarded_and_desktop_only(self):
        self.assertIn("medical_service_sidebar_visibility", self.layout)
        self.assertIn("document.documentElement.dataset.sidebarCollapsed", self.layout)
        self.assertIn("localStorage.getItem(SIDEBAR_VISIBILITY_STORAGE_KEY)", self.layout)
        self.assertIn("localStorage.setItem(", self.layout)
        self.assertIn("function readStoredSidebarVisibility()", self.layout)
        self.assertIn("function applySidebarVisibility(", self.layout)
        self.assertIn("function syncSidebarVisibilityForViewport()", self.layout)
        self.assertIn("window.innerWidth >= 993", self.layout)
        # Storage failures fall back to the icon rail; the head script treats only
        # an explicit 'expanded' (pinned) choice as open.
        self.assertIn("return 'collapsed';", self.layout)
        self.assertIn("stored === 'expanded' ? 'false' : 'true'", self.layout)
        self.assertIn('catch (_) {', self.layout)
        self.assertIn('aria-expanded', self.layout)
        self.assertIn('sidebar-collapsed', self.shell_css)
        self.assertIn('html[data-sidebar-collapsed="true"]', self.shell_css)

    def test_sidebar_visibility_storage_is_independent_of_width_and_mobile_focus(self):
        self.assertIn("SIDEBAR_RESIZE_STORAGE_KEY = 'medical_service_sidebar_width'", self.layout)
        self.assertIn("SIDEBAR_VISIBILITY_STORAGE_KEY = 'medical_service_sidebar_visibility'", self.layout)
        self.assertIn("reim-focus-active", (ROOT / 'templates' / 'reimbursement.html').read_text(encoding='utf-8'))
        self.assertIn("setMobileSidebar(false)", self.layout)
        self.assertIn("applySidebarVisibility(readStoredSidebarVisibility() === 'collapsed', false)", self.layout)
        self.assertNotIn("localStorage.setItem(SIDEBAR_VISIBILITY_STORAGE_KEY, 'collapsed')", self.layout)

    def test_sidebar_visibility_runtime_persists_desktop_and_ignores_mobile(self):
        helpers_start = self.layout.index(
            "const SIDEBAR_VISIBILITY_STORAGE_KEY = 'medical_service_sidebar_visibility';",
            self.layout.index('bootstrap.bundle'),
        )
        helpers_end = self.layout.index('\n        function setMobileSidebar(open)', helpers_start)
        helpers = self.layout[helpers_start:helpers_end]
        node_script = textwrap.dedent(f"""
            const assert = require('assert');
            const stored = new Map();
            let storageUnavailable = false;
            const localStorage = {{
                getItem(key) {{
                    if (storageUnavailable) throw new Error('storage unavailable');
                    return stored.has(key) ? stored.get(key) : null;
                }},
                setItem(key, value) {{
                    if (storageUnavailable) throw new Error('storage unavailable');
                    stored.set(key, String(value));
                }}
            }};
            function makeClassList() {{
                const names = new Set();
                return {{
                    add(name) {{ names.add(name); }},
                    remove(name) {{ names.delete(name); }},
                    contains(name) {{ return names.has(name); }},
                    toggle(name, enabled) {{
                        if (enabled) names.add(name); else names.delete(name);
                    }}
                }};
            }}
            const body = {{ classList: makeClassList() }};
            const sidebar = {{ classList: makeClassList() }};
            const mobileMenuButton = {{ attrs: {{}}, setAttribute(name, value) {{ this.attrs[name] = value; }} }};
            const controls = {{
                sidebar,
                'sidebar-toggle-desktop': {{ classList: makeClassList(), attrs: {{}}, setAttribute(name, value) {{ this.attrs[name] = value; }} }},
                'show-sidebar-btn': {{ classList: makeClassList(), attrs: {{}}, setAttribute(name, value) {{ this.attrs[name] = value; }} }},
                'mobile-menu-button': mobileMenuButton
            }};
            const document = {{
                body,
                documentElement: {{ dataset: {{}} }},
                getElementById(id) {{ return controls[id] || null; }}
            }};
            const window = {{ innerWidth: 1200 }};
            let mobileCloseCalls = 0;
            const mobileEvents = [];
            function setMobileSidebar(open) {{
                if (open) {{
                    sidebar.classList.add('active');
                    body.classList.add('mobile-sidebar-open');
                    mobileMenuButton.setAttribute('aria-expanded', 'true');
                    return;
                }}
                mobileCloseCalls += 1;
                mobileEvents.push('close');
                sidebar.classList.remove('active');
                body.classList.remove('mobile-sidebar-open');
                mobileMenuButton.setAttribute('aria-expanded', 'false');
            }}
            {helpers}

            // No saved choice: the 64px icon rail ('collapsed') is the default.
            assert.strictEqual(readStoredSidebarVisibility(), 'collapsed');
            syncSidebarVisibilityForViewport();
            assert.strictEqual(body.classList.contains('sidebar-collapsed'), true);
            assert.strictEqual(sidebar.inert, false, 'rail icons stay reachable');
            toggleSidebarDesktop();
            assert.strictEqual(body.classList.contains('sidebar-collapsed'), false);
            assert.strictEqual(stored.get(SIDEBAR_VISIBILITY_STORAGE_KEY), 'expanded');
            assert.strictEqual(sidebar.inert, false);
            toggleSidebarDesktop();
            assert.strictEqual(body.classList.contains('sidebar-collapsed'), true);
            assert.strictEqual(stored.get(SIDEBAR_VISIBILITY_STORAGE_KEY), 'collapsed');
            assert.strictEqual(sidebar.inert, false, 'rail icons stay reachable');

            stored.set(SIDEBAR_VISIBILITY_STORAGE_KEY, 'invalid');
            syncSidebarVisibilityForViewport();
            assert.strictEqual(body.classList.contains('sidebar-collapsed'), true);
            stored.set(SIDEBAR_VISIBILITY_STORAGE_KEY, 'expanded');
            syncSidebarVisibilityForViewport();
            assert.strictEqual(body.classList.contains('sidebar-collapsed'), false, 'pinned stays pinned');
            storageUnavailable = true;
            assert.strictEqual(readStoredSidebarVisibility(), 'collapsed');
            applySidebarVisibility(true, true);
            storageUnavailable = false;

            stored.set(SIDEBAR_VISIBILITY_STORAGE_KEY, 'collapsed');
            const preferenceBeforeMobile = stored.get(SIDEBAR_VISIBILITY_STORAGE_KEY);
            window.innerWidth = 800;
            body.classList.add('sidebar-collapsed');
            sidebar.classList.add('active');
            body.classList.add('mobile-sidebar-open');
            mobileMenuButton.setAttribute('aria-expanded', 'true');
            syncSidebarVisibilityForViewport();
            assert.strictEqual(body.classList.contains('sidebar-collapsed'), false);
            assert.strictEqual(document.documentElement.dataset.sidebarCollapsed, 'false');
            assert.strictEqual(stored.get(SIDEBAR_VISIBILITY_STORAGE_KEY), preferenceBeforeMobile);
            assert.strictEqual(sidebar.classList.contains('active'), true);
            assert.strictEqual(body.classList.contains('mobile-sidebar-open'), true);
            assert.strictEqual(mobileMenuButton.attrs['aria-expanded'], 'true');
            assert.strictEqual(mobileCloseCalls, 0);
            assert.strictEqual(sidebar.inert, false, 'open mobile drawer stays reachable');
            sidebar.classList.remove('active');
            syncSidebarInert();
            assert.strictEqual(sidebar.inert, true, 'closed mobile drawer must leave the Tab order');
            sidebar.classList.add('active');

            window.innerWidth = 1200;
            syncSidebarVisibilityForViewport();
            assert.strictEqual(sidebar.classList.contains('active'), false);
            assert.strictEqual(body.classList.contains('mobile-sidebar-open'), false);
            assert.strictEqual(mobileMenuButton.attrs['aria-expanded'], 'false');
            assert.deepStrictEqual(mobileEvents, ['close']);
            assert.strictEqual(body.classList.contains('sidebar-collapsed'), true);
            assert.strictEqual(document.documentElement.dataset.sidebarCollapsed, 'true');
            assert.strictEqual(sidebar.inert, false, 'back on desktop the rail is reachable');
        """)
        result = subprocess.run(
            ['node', '-e', node_script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_shell_polish_hover_intent_names_and_phone_bell_colour(self):
        flyouts = self.layout.split('(function initSidebarFlyouts()', 1)[1].split('})();', 1)[0]
        self.assertIn('const OPEN_DELAY = 120;', flyouts)
        # Crossing the rail from the small avatar to its panel must not close it.
        self.assertIn('if (current === flyout && !sidebar.contains(event.relatedTarget)) scheduleClose();', flyouts)
        self.assertIn("sidebar.addEventListener('pointerleave', event => {", flyouts)
        # Synthetic resize events (Calendar fires them constantly) must not close a flyout.
        self.assertIn('if (viewport === lastViewport) return;', flyouts)
        self.assertIn("avatar.toggleAttribute('aria-hidden', !isRail());", flyouts)
        self.assertIn('aria-label="Show Create TSR"', self.layout)
        self.assertIn('.mobile-nav .mobile-nav-actions a.changelog-header-button {\n    color: var(--sidebar-text);', self.shell_css)

    def test_clarify_role_label_rail_dividers_and_my_requests_icon(self):
        # The account role comes from get_display_role(), the label Settings shows.
        self.assertIn("'nav_display_role': get_display_role(current_user) if authenticated else ''", self.app_source)
        role = self.layout.split('<span class="sidebar-user-role">', 1)[1].split('</span>', 1)[0]
        self.assertIn('{{ nav_display_role }}', role)
        self.assertNotIn('Staff', role)
        self.assertIn('--sidebar-rail-divider: rgba(203, 213, 225, 0.32);', self.shell_css)
        self.assertIn('background: var(--sidebar-rail-divider);', self.shell_css)
        self.assertIn("nav_link('/accounting_center', 'fa-inbox', 'My Requests'", self.layout)
        self.assertNotIn('fa-folder-tree', self.layout)

    def test_dark_themes_lift_the_rail_off_the_page_with_an_edge(self):
        themes = (ROOT / 'static' / 'css' / 'app-themes.css').read_text(encoding='utf-8')
        amoled = themes.split(':root[data-app-theme="dark"] {', 1)[1].split('}', 1)[0]
        graphite = themes.split(':root[data-app-theme="dark"][data-app-palette="graphite"] {', 1)[1].split('}', 1)[0]
        self.assertIn('--app-sidebar: #101010;', amoled)
        self.assertNotIn('--app-sidebar: #202124;', graphite)
        self.assertIn('--app-sidebar: #292a2d;', graphite)
        self.assertIn('--sidebar-edge: rgba(255, 255, 255, 0.14);', self.shell_css)
        self.assertIn(':root[data-app-theme="dark"] .sidebar {\n        box-shadow: inset -1px 0 0 var(--sidebar-edge);', self.shell_css)
        self.assertIn('border: 1px solid var(--sidebar-edge);', self.shell_css)

    def test_phone_drawer_opens_below_the_top_bar_above_docks_with_a_backdrop(self):
        phone = self.shell_css.split('@media (max-width: 992px) {\n    /* The drawer opens under the top bar', 1)[1].split('\n}\n', 1)[0]
        self.assertIn('top: var(--mobile-nav-height, 64px);', phone)
        self.assertIn('.sidebar-header {\n        display: none;', phone)
        self.assertIn('body.mobile-sidebar-open .sidebar {\n        z-index: 1210;', phone)
        self.assertIn('body.mobile-sidebar-open .mobile-nav {\n        z-index: 1220;', phone)
        self.assertIn('body.mobile-sidebar-open .mobile-nav-backdrop {\n        display: block;', phone)
        self.assertIn('<div class="mobile-nav-backdrop no-print" aria-hidden="true"></div>', self.layout)
        drawer = self.layout.split('function setMobileSidebar(open) {', 1)[1].split('function toggleSidebarMobile()', 1)[0]
        self.assertIn("setProperty('--mobile-nav-height'", drawer)
        self.assertIn("menuButton.textContent = open ? 'Close' : 'Menu';", drawer)

    def test_mobile_drawer_uses_the_shared_navigation_boundary_for_all_close_paths(self):
        self.assertIn('function isMobileNavigationViewport()', self.layout)
        self.assertIn('return window.innerWidth < SIDEBAR_DESKTOP_BREAKPOINT;', self.layout)

        mobile_state = self.layout.split('function applyMobileState()', 1)[1].split(
            '// Smooth anchor scroll support', 1
        )[0]
        self.assertIn('isMobileNavigationViewport()', mobile_state)
        self.assertIn('const isMobile = window.innerWidth <= 768;', mobile_state)
        self.assertNotIn("sidebar.classList.remove('active')", mobile_state)
        self.assertIn('setMobileSidebar(false)', mobile_state)

        outside_click = self.layout.split('// Close sidebar when clicking outside', 1)[1].split(
            '// Auto-close mobile sidebar after nav click', 1
        )[0]
        self.assertIn('if(!isMobileNavigationViewport()) return;', outside_click)
        self.assertIn('setMobileSidebar(false)', outside_click)
        self.assertNotIn("sidebar.classList.remove('active')", outside_click)

        nav_close = self.layout.split('// Auto-close mobile sidebar after nav click', 1)[1].split(
            '// Smooth anchor scroll support', 1
        )[0]
        self.assertIn('isMobileNavigationViewport()', nav_close)
        self.assertIn('setMobileSidebar(false)', nav_close)
        self.assertNotIn("sidebar.classList.remove('active')", nav_close)

    def test_pending_summary_endpoint_is_lightweight(self):
        self.assertIn("@app.route('/api/nav/pending-summary')", self.app_source)
        endpoint = self.app_source.split('def get_nav_pending_summary(')[1].split('@app.route')[0]
        # Must count, never materialise rows: this runs on every page load.
        self.assertIn('.count()', endpoint)
        self.assertNotIn('.all()', endpoint)
        self.assertIn('apply_assigned_approver_filter', endpoint)

    def test_shell_css_is_cached_and_version_bumped(self):
        self.assertIn("'/static/css/app-shell.css',", self.app_source)
        assert_cache_version_at_least(self, 126, self.app_source)


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
