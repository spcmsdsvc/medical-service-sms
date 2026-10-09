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
        self.assertIn('<nav class="sidebar-nav" id="sidebar-nav" aria-label="Main">', self.layout)
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
        # The Calendar split row was removed with the sidebar reorder.
        self.assertNotIn('sidebar-calendar', self.shell_css)
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
        self.assertIn("'Calibration Center'", self.layout)
        self.assertIn('font-size: var(--shell-text-subrow);', subnav)
        self.assertIn('--shell-text-subrow: 0.84rem;', self.shell_css)

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
        self.assertIn('width: min(86vw, 320px);', mobile)
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
        self.assertIn("app-shell.css') }}?v=42", self.layout)
        assert_cache_version_at_least(self, 158, self.app_source)

    def test_icon_rail_and_docks_follow_the_shell_offset(self):
        self.assertIn('--sidebar-rail-width: 72px;', self.shell_css)
        self.assertIn('html[data-sidebar-collapsed="true"] {\n        --shell-offset: var(--sidebar-rail-width);', self.shell_css)
        for name in ('reimbursement.html', 'travel_request.html', '_liquidation_base.html'):
            page = (ROOT / 'templates' / name).read_text(encoding='utf-8')
            self.assertIn('left: var(--shell-offset, var(--sidebar-width, 240px))', page, name)
            self.assertNotIn('left: var(--sidebar-width, 240px)', page, name)

    def test_rail_labels_stay_named_and_flyouts_sit_above_sticky_headers(self):
        rail_labels = self.shell_css.split('.sidebar .sidebar-section-toggle > span {', 1)[1].split('}', 1)[0]
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
        # Each group's own subnav is the flyout, titled; no nested groups.
        for section in ('new-request', 'clients', 'reports', 'office', 'inventory', 'admin'):
            opening = self.layout.split(f'<div id="{section}-sidebar-section"', 1)[1].split('\n', 2)[1]
            self.assertIn('class="sidebar-flyout-title"', opening, section)
        self.assertNotIn('calendar-sidebar-section', self.layout)
        self.assertNotIn('sidebar-subnav-nested', self.shell_css)
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
        # A saved choice wins; with none, wide screens (1440px+) start pinned and
        # smaller ones (or a storage failure there) get the icon rail.
        self.assertIn("const pinned = stored ? stored === 'expanded' : window.innerWidth >= 1440;", self.layout)
        self.assertIn("const SIDEBAR_WIDE_PINNED_WIDTH = 1440;", self.layout)
        self.assertIn("return byWidth;", self.layout)
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
                'sidebar-toggle-desktop': {{ classList: makeClassList(), attrs: {{}}, setAttribute(name, value) {{ this.attrs[name] = value; }}, querySelector() {{ return null; }} }},
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

            // No saved choice: wide screens start pinned, smaller ones on the icon rail.
            window.innerWidth = 1500;
            assert.strictEqual(readStoredSidebarVisibility(), 'expanded');
            window.innerWidth = 1200;
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
        self.assertIn("avatar.toggleAttribute('aria-hidden', !usable);", flyouts)
        self.assertIn("{{ nav_link('/offline-tsr', 'fa-file-pen', 'Create TSR') }}", self.layout)
        self.assertIn('.mobile-nav .mobile-nav-actions a.changelog-header-button {\n    color: var(--sidebar-text);', self.shell_css)

    def test_clarify_role_label_rail_dividers_and_my_requests_icon(self):
        # The account role comes from get_display_role(), the label Settings shows.
        self.assertIn("'nav_display_role': get_display_role(current_user) if authenticated else ''", self.app_source)
        role = self.layout.split('{%- set account_role = ', 1)[1].split('%}', 1)[0]
        self.assertIn('nav_display_role', role)
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

    def test_shell_brand_mark_page_name_and_app_font(self):
        themes = (ROOT / 'static' / 'css' / 'app-themes.css').read_text(encoding='utf-8')
        self.assertIn("--app-font: 'Fira Sans', 'Segoe UI', system-ui, sans-serif;", themes)
        self.assertIn("url('../fonts/fira-sans/fira-sans-600.woff2')", themes)
        self.assertIn('font-family: var(--app-font);', self.shell_css)
        self.assertNotIn('font-family: sans-serif;', self.shell_css)
        # The mark is cropped from the logo image, never redrawn, in both headers.
        self.assertEqual(self.layout.count('<span class="shell-brand-mark" role="img" aria-label="Shimadzu"></span>'), 2)
        self.assertIn("shimadzu-philippines-logo-white.webp') no-repeat;", self.shell_css)
        self.assertIn('body.sidebar-collapsed .sidebar .sidebar-header .shell-brand-name,', self.shell_css)
        self.assertNotIn('MEDICAL SERVICE</h', self.layout)
        # The page name comes from the active sidebar link.
        self.assertIn('<title>Medical Service</title>', self.layout)
        self.assertIn('id="mobile-page-title"', self.layout)
        self.assertIn("document.title = name + ' · Medical Service';", self.layout)

    def test_sign_in_brand_rule_seals_the_shell_headers(self):
        themes = (ROOT / 'static' / 'css' / 'app-themes.css').read_text(encoding='utf-8')
        auth = (ROOT / 'static' / 'css' / 'app-auth.css').read_text(encoding='utf-8')
        self.assertIn('--brand-rule: #ee3239;', themes)
        self.assertIn('--brand-rule: var(--app-primary);', themes)
        self.assertIn('--login-rule: var(--brand-rule);', auth)
        self.assertEqual(self.shell_css.count('box-shadow: inset 0 -2px 0 var(--brand-rule);'), 2)
        self.assertNotIn('border-bottom: 1px solid rgba(255, 255, 255, 0.08);', self.shell_css)

    def test_whats_new_unread_is_a_quiet_dot_not_an_amber_button(self):
        self.assertNotIn('.changelog-header-button.has-unread {', self.shell_css)
        self.assertNotIn('font-weight: 950;', self.shell_css)
        badge = self.shell_css.split('\n.changelog-header-badge {', 1)[1].split('}', 1)[0]
        self.assertIn('width: 8px;', badge)
        self.assertIn('font-size: 0;', badge)
        # The count still reaches screen readers and the tooltip.
        self.assertIn("button.setAttribute('aria-label', accessibleLabel);", self.layout)

    def test_shell_polish_offline_tag_flyout_groups_logout_and_close_button(self):
        offline = self.shell_css.split(".offline-mode .sidebar-header::after,", 1)[1].split('}', 1)[0]
        self.assertIn('position: absolute;', offline)
        self.assertIn('bottom: -8px;', offline)
        self.assertEqual(self.layout.count('role="group" aria-label="'), 6)
        self.assertIn('role="group" aria-label="Forms"', self.layout)
        self.assertNotIn('#e8a33d', self.shell_css)
        self.assertIn('--bs-btn-hover-bg: rgba(255, 255, 255, 0.1);', self.shell_css)
        self.assertNotIn('font-weight: 800;', self.shell_css)
        self.assertNotIn('font-weight: 900;', self.shell_css)

    def test_phone_drawer_is_modal_and_offline_is_announced(self):
        drawer = self.layout.split('function setPageBehindDrawerInert(on) {', 1)[1].split('function toggleSidebarMobile()', 1)[0]
        self.assertIn("document.querySelectorAll('body > *')", drawer)
        self.assertIn("el.id === 'shell-connection-status'", drawer)
        self.assertIn('setPageBehindDrawerInert(open);', drawer)
        self.assertIn("document.activeElement === document.body", drawer)
        self.assertIn('<div id="shell-connection-status" class="visually-hidden" role="status" aria-live="polite"></div>', self.layout)
        self.assertEqual(self.layout.count('announceConnection(OFFLINE_MESSAGE);'), 2)
        self.assertIn("Create TSR still works and syncs when you're back online", self.layout)
        self.assertIn("announceConnection('Back online.');", self.layout)
        self.assertIn('id="main-content" role="main"', self.layout)

    def test_unread_is_a_soft_white_dot_on_the_bell_not_the_avatar(self):
        badge = self.shell_css.split('\n.changelog-header-badge {', 1)[1].split('}', 1)[0]
        self.assertIn('background: var(--shell-focus-ring);', badge)
        self.assertNotIn('#f0b429', self.shell_css)
        # Routine updates no longer light the account avatar (fresh critique 2026-10-09).
        self.assertNotIn('sidebar-user-avatar.has-unread', self.shell_css)
        self.assertNotIn("avatar.classList.toggle('has-unread'", self.layout)

    def test_pinned_header_is_brand_and_pin_only_with_account_tools_in_the_footer(self):
        header = self.layout.split('<div class="sidebar-header">', 1)[1].split('<div id="sidebar-resize-handle"', 1)[0]
        self.assertNotIn('appearance-header-button', header)
        self.assertNotIn('changelog-header-button', header)
        self.assertIn('sidebar-toggle-icon fa-solid fa-angles-left', header)
        self.assertIn("icon.classList.toggle('fa-angles-right', collapsed);", self.layout)
        self.assertEqual(self.layout.count('sidebar-account-tool'), 2)
        # The pinned footer has no icon tools: avatar, name or chevron open the
        # labelled account panel (fresh critique 2026-10-09).
        self.assertNotIn('.sidebar-user .sidebar-account-tool {', self.shell_css)
        self.assertIn('body:not(.sidebar-collapsed) .sidebar .sidebar-user-flyout:not(.is-flyout-open) .sidebar-logout {\n        display: none;', self.shell_css)
        self.assertIn('const canOpen = flyout => isRail() || (flyout.account && isPinnedDesktop());', self.layout)
        # The panel's rules name the body state in both modes, so in the rail they
        # still outweigh the rail's label-hiding rule (labels went missing without it).
        self.assertIn('    body.sidebar-collapsed .sidebar .is-flyout-open a > span,\n    body:not(.sidebar-collapsed) .sidebar .is-flyout-open a > span {', self.shell_css)
        self.assertIn('    body.sidebar-collapsed .sidebar .is-flyout-open a,\n    body:not(.sidebar-collapsed) .sidebar .is-flyout-open a,', self.shell_css)
        self.assertIn('<span class="sidebar-user-name" title="{{ current_user.username }}">', self.layout)
        self.assertNotIn('@container (max-width: 211px)', self.shell_css)

    def test_phone_drawer_opens_from_the_menu_side_and_bar_names_the_section(self):
        phone = self.shell_css.split('@media (max-width: 992px) {\n    /* The drawer opens under the top bar', 1)[1].split('\n}\n', 1)[0]
        self.assertIn('right: -100%;', phone)
        self.assertIn('.sidebar.active {\n        right: 0;', phone)
        self.assertIn("label.closest('.sidebar-subnav[aria-label]')", self.layout)
        self.assertIn("phoneTitle.textContent = section ? section.getAttribute('aria-label') : name;", self.layout)

    def test_shell_text_uses_one_three_step_scale(self):
        import re
        for token in ('--shell-text-row: 0.9rem;', '--shell-text-subrow: 0.84rem;', '--shell-text-micro: 0.72rem;'):
            self.assertIn(token, self.shell_css)
        label = self.shell_css.split('\n.sidebar-group-label {', 1)[1].split('}', 1)[0]
        self.assertIn('font-size: var(--shell-text-micro);', label)
        sidebar_part = self.shell_css.split('/* --- Touch device polish', 1)[0]
        stray = set(re.findall(r'font-size: (0\.(?:64|66|74|8|86)rem)', sidebar_part))
        self.assertEqual(stray, set())

    def test_rail_review_fixes_guard_marker_offline_drawer_and_captions(self):
        # Bootstrap's inline collapse is refused while the rail owns the group.
        self.assertIn("['show.bs.collapse', 'hide.bs.collapse'].forEach(type => {", self.layout)
        self.assertIn('if (event.target === flyout.panel && isRail()) event.preventDefault();', self.layout)
        # Lighter marker that still follows the accent.
        self.assertIn('--sidebar-active-marker: color-mix(in srgb, var(--app-primary) 55%, #ffffff);', self.shell_css)
        self.assertNotIn('border-left: 3px solid var(--app-primary);', self.shell_css)
        # Readable offline tag and a phone strip; the online message is cleared.
        self.assertIn("content: 'Offline · Create TSR still works';", self.shell_css)
        self.assertNotIn('font-size: .6rem;', self.shell_css)
        self.assertIn("status.textContent === 'Back online.'", self.layout)
        # Wider phone drawer with the account on top.
        self.assertIn('width: min(86vw, 320px);', self.shell_css)
        self.assertIn('.sidebar .sidebar-user {\n        order: -1;', self.shell_css)
        # Rail captions.
        self.assertIn('data-rail-caption="Forms"', self.layout)
        self.assertIn('content: attr(data-rail-caption);', self.shell_css)

    def test_critique_fixes_badge_rail_count_logout_row_and_inventory_dividers(self):
        # The count badge keeps its own size against `.sidebar a span { flex: 1 }`.
        self.assertIn('.sidebar a .sidebar-count-badge {\n    flex: 0 0 auto;', self.shell_css)
        # Rail rows have room for their captions (52px), paid for by thinner dividers.
        self.assertIn('min-height: 52px;', self.shell_css)
        self.assertIn('.sidebar-nav > .sidebar-group-label:first-child {\n        height: 0;', self.shell_css)
        # The rail shows a one-digit count instead of a bare dot.
        self.assertIn("entry.node.dataset.railCount = count > 9 ? '9+'", self.layout)
        self.assertIn('content: attr(data-rail-count);', self.shell_css)
        self.assertIn('clip: auto;\n        overflow: visible;', self.shell_css)
        # Phones: Log out is a labelled row at the drawer's foot, not beside Close.
        self.assertIn('<a href="/logout" class="sidebar-logout-row">', self.layout)
        self.assertIn('.sidebar .sidebar-user .sidebar-logout {\n        display: none;', self.shell_css)
        # Inventory: distinct brand icons, PM pages and Stock set apart.
        nav = self.layout.split('<div id="inventory-sidebar-section"', 1)[1].split('</div>\n            {% else %}', 1)[0]
        self.assertIn("'fa-x-ray', 'Genoray'", nav)
        self.assertIn("'fa-tablet-screen-button', 'Vieworks'", nav)
        self.assertEqual(nav.count('sidebar-subnav-divider'), 2)
        # The role is never cut without an ellipsis.
        self.assertIn('class="sidebar-user-role" title="{{ account_role }}"', self.layout)

    def test_critique_checklist_names_headings_guide_and_accordion(self):
        nav = self.layout.split('<nav class="sidebar-nav"', 1)[1].split('</nav>', 1)[0]
        # Point 1-2: one name per item; the caption is the label and may wrap to two lines.
        for label in ("'Documents'", "'Settings'", "'Client List'", "'My Requests'", "'Create TSR'"):
            self.assertIn(label, nav)
        for old in ("'Service Documents'", "'System Settings'", '>New Request<'):
            self.assertNotIn(old, nav)
        self.assertIn('-webkit-line-clamp: 2;', self.shell_css)
        # Point 4-5: readable captions; section headings reach screen readers.
        self.assertNotIn('--shell-text-caption', self.shell_css)
        self.assertEqual(nav.count('class="sidebar-group-label" role="heading" aria-level="2"'), 3)
        self.assertNotIn('class="sidebar-group-label" aria-hidden="true"', nav)
        # Point 7: only administrators see "Manage".
        self.assertIn("{{ 'Manage' if is_management_user else 'More' }}", nav)
        # Point 8: the unread count is capped at 9+.
        self.assertIn("const countLabel = count > 9 ? '9+'", self.layout)
        # Point 9: the menu guide, from the header (pinned), the account flyout (rail) and the drawer.
        self.assertIn('<dialog id="shell-guide"', self.layout)
        self.assertEqual(self.layout.count('onclick="openShellGuide(this)"'), 2)
        self.assertIn('body.sidebar-collapsed .shell-guide-header-button {\n    display: none;', self.shell_css)
        # Point 11: opening a group closes the others except the current page's group,
        # and a fade shows when more of the pinned menu is below.
        self.assertNotIn('data-bs-parent', nav)
        self.assertIn("if(panel === event.target || panel.querySelector('[aria-current=\"page\"]')) return;", self.layout)
        self.assertIn("nav.classList.toggle('has-more-below',", self.layout)
        self.assertIn('body:not(.sidebar-collapsed) .sidebar-nav.has-more-below {', self.shell_css)
        # The guide sits after the page's other dialogs and stays usable over the phone menu.
        self.assertGreater(self.layout.index('<dialog id="shell-guide"'), self.layout.index('Delete Schedule'))
        self.assertIn("el.id === 'shell-guide'", self.layout)
        # Point 12: thumb-sized phone avatar.
        self.assertIn('.sidebar .sidebar-user-avatar {\n        width: 44px;', self.shell_css)

    def test_fresh_critique_guide_links_and_whats_new_read_on_opening(self):
        # The Menu guide's pages are links, and its pin key matches the button.
        guide = self.layout.split('function openShellGuide(trigger){', 1)[1].split('window.openShellGuide', 1)[0]
        self.assertIn("link.href = node.getAttribute('href');", guide)
        self.assertIn('row.appendChild(linkTo(page));', guide)
        self.assertIn("'fa-angles-right' : 'fa-angles-left'", guide)
        # Opening What's New marks unread releases read after the list has loaded.
        changelog = (ROOT / 'static' / 'js' / 'app-changelog.js').read_text(encoding='utf-8')
        self.assertIn('async function markChangelogSeenOnOpen(){', changelog)
        self.assertIn("if(changelogAdminMode || previewRole || !changelogReleases.some(release => release.is_unread)) return;", changelog)
        self.assertIn("    await loadChangelog();\n    markChangelogSeenOnOpen();", changelog)
        self.assertIn("app-changelog.js') }}?v=2", (ROOT / 'templates' / 'changelog.html').read_text(encoding='utf-8'))

    def test_sidebar_order_puts_waiting_work_first_then_work_then_manage(self):
        self.assertIn("nav_link('/clients_page', 'fa-hospital', 'Clients')", self.layout)
        self.assertNotIn("'Medical Centers'", self.layout)
        nav = self.layout.split('<nav class="sidebar-nav"', 1)[1].split('</nav>', 1)[0]
        order = [
            'aria-level="2">Main</div>',
            "nav_link('/', 'fa-chart-line', 'Dashboard')",
            "nav_link('/approvals'",
            "nav_link('/accounting_center'",
            "nav_link('/timeline', 'fa-calendar-days', 'Calendar') }}\n                {{ nav_link('/offline-tsr'",
            'aria-level="2">Work</div>',
            'aria-label="Forms"',
            'aria-label="Clients"',
            'aria-label="Inventory"',
            '<div class="sidebar-subnav-divider" aria-hidden="true"></div>\n                        {{ nav_link(\'/stock_inventory\'',
            "{{ 'Manage' if is_management_user else 'More' }}</div>",
            'aria-label="Reports"',
            'aria-label="Office"',
            'aria-label="Admin"',
        ]
        positions = [nav.index(marker) for marker in order]
        self.assertEqual(positions, sorted(positions))
        for old in ('Clients &amp; Equipment', 'sidebar-subnav-nested', 'Field Operations', 'Reports &amp; Insights', 'Resources', '>Operations<', '>Records<', 'sidebar-calendar'):
            self.assertNotIn(old, nav)
        # One-link groups render the link itself.
        self.assertIn('{% if office_link_count > 1 %}', nav)
        self.assertIn('data-rail-caption="Clients"', nav)
        self.assertIn('{% if inventory_link_count > 1 %}', nav)
        self.assertIn('data-rail-caption="Inventory"', nav)
        # Captions are the labels; only two rare accounts keep short ones.
        self.assertIn("{%- set rail_caption = {'Stock Inventory': 'Stock', 'Password Settings': 'Password'}.get(label, label) -%}", self.layout)
        # Stock Inventory sits in WORK, not MAIN; only stock-only accounts keep it on top,
        # and the Stock page no longer lights up the Admin group.
        self.assertIn('{% if stock_inventory_view and stock_inventory_only_user and not hr_schedule_only_user %}', nav)
        self.assertIn("{% set admin_paths = ['/activity_page', '/settings'] %}", nav)
        # A long section name falls back to its short caption in the phone bar.
        self.assertIn('phoneTitle.textContent = toggle.dataset.railCaption;', self.layout)

    def test_phone_drawer_rows_are_thumb_sized_and_long_labels_wrap(self):
        phone = self.shell_css.split('@media (max-width: 992px) {\n    /* The drawer opens under the top bar', 1)[1].split('\n}\n', 1)[0]
        self.assertIn('--sidebar-subrow-height: 44px;', phone)
        self.assertIn('.sidebar .sidebar-nav a span,', phone)
        self.assertIn('overflow-wrap: anywhere;', phone)
        logout = phone.split('.sidebar .sidebar-logout-row {', 1)[1].split('}', 1)[0]
        self.assertIn('min-height: 48px;', logout)

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

    def test_office_group_shows_only_when_it_holds_more_than_one_link(self):
        # An engineer's only office link is Personnel: shown directly, no group.
        engineer = self._render_dashboard_as(self._make_user('layout_office_engineer', 'engineer'))
        self.assertIn('href="/engineers_page"', engineer)
        self.assertNotIn('aria-label="Office"', engineer)
        # Engineers have no Calibration Center or brand inventory: plain links.
        self.assertIn('href="/clients_page"', engineer)
        self.assertNotIn('aria-label="Clients"', engineer)
        self.assertIn('href="/offline-tsr"', engineer)
        # Two office permissions: the Office group holds both links.
        both = self._render_dashboard_as(self._make_user(
            'layout_office_both', 'accounting', po_admin_access=True, reimbursement_tracker_access=True))
        office = both.split('aria-label="Office"', 1)[1].split('</div>', 2)[1]
        self.assertIn('href="/po_details"', office)
        self.assertIn('href="/reimbursement_tracker"', office)
        # One office permission: that link alone, no group.
        one = self._render_dashboard_as(self._make_user('layout_office_one', 'accounting', po_admin_access=True))
        self.assertIn('href="/po_details"', one)
        self.assertNotIn('aria-label="Office"', one)

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
