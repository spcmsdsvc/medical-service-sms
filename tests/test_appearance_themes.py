import json
import os
import re
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests.sw_cache_version import assert_cache_version_at_least


ROOT = Path(__file__).resolve().parents[1]

# Pin app imports to a disposable database outside the repository. This test module only
# exercises the appearance payload helper, but importing app.py must never open scheduler.db.
_TEST_DB_PATH = Path(tempfile.gettempdir()) / f'medical_service_appearance_tests_{os.getpid()}.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402

# Tokens deliberately left undefined in app-themes.css. Every entry is a fixed brand
# colour whose fallback renders the same in both themes rather than inverting:
#   --app-table-head   navy table header matching the Excel export
#   --app-focus-ring   blue focus ring
#   --app-accent       brand blue, used for text and outlines only
#   --app-danger       brand red, only ever paired with a hardcoded #fff foreground
#   --app-danger-text  brand red used as text
# Add to this set only when the fallback is safe in BOTH themes, and say why. A token
# used as a `background:` almost never qualifies -- see the test's docstring.
UNDEFINED_TOKEN_EXEMPTIONS = {
    '--app-table-head',
    '--app-focus-ring',
    '--app-accent',
    '--app-danger',
    '--app-danger-text',
}


class AppearanceThemeSourceTests(unittest.TestCase):
    def test_every_theme_token_used_anywhere_is_actually_defined(self):
        """A misspelled custom property is invisible: it silently takes its fallback.

        This has now shipped three times, each time as a transposition of a real token:
        `--app-raised-surface` for `--app-surface-raised` on the Reimbursement Tracker,
        the same misspelling again on P.O. Details (mobile cards, and later the equipment
        picker's hover state at 1.01:1 in dark mode), and `--app-text-muted` for
        `--app-muted-text` in the request-recall modal.

        The mechanism is always the same and always one-directional. The fallback is a
        light colour chosen to look right in light mode, so light mode is perfect and only
        dark mode breaks -- a light `background:` under `var(--app-text)`, which in dark
        mode is near-white. Nothing errors and nothing logs.

        The previous guard asserted this for `reimbursement_tracker.html` alone while its
        own docstring claimed it asserted the class. It could not have caught either later
        occurrence. This one reads every template and every stylesheet, so a new page
        inherits the guard instead of having to remember it.
        """
        themes = (ROOT / 'static' / 'css' / 'app-themes.css').read_text(encoding='utf-8')
        defined = set(re.findall(r'(--app-[a-z0-9-]+)\s*:', themes))
        self.assertIn('--app-surface-raised', defined, 'token source file looks wrong')
        self.assertIn('--app-muted-text', defined, 'token source file looks wrong')

        sources = sorted(
            list((ROOT / 'templates').rglob('*.html'))
            + list((ROOT / 'static' / 'css').rglob('*.css'))
            + list((ROOT / 'static' / 'js').rglob('*.js'))
        )
        self.assertGreater(len(sources), 20, 'expected to scan the whole front end')

        offenders = {}
        seen_any_token = False
        for path in sources:
            used = set(re.findall(
                r'var\(\s*(--app-[a-z0-9-]+)',
                path.read_text(encoding='utf-8', errors='ignore'),
            ))
            seen_any_token = seen_any_token or bool(used)
            undefined = sorted(used - defined - UNDEFINED_TOKEN_EXEMPTIONS)
            if undefined:
                offenders[path.relative_to(ROOT).as_posix()] = undefined

        self.assertTrue(seen_any_token, 'scan found no theme tokens at all -- check the glob')
        self.assertEqual(
            offenders,
            {},
            'undefined theme tokens fall back silently and break dark mode: '
            f'{offenders}',
        )

    def test_toast_tone_colours_clear_the_non_text_contrast_floor_in_both_themes(self):
        """A fixed colour on a themed surface has a contrast ratio per palette.

        The register toasts carry their tone on a left border and an icon rather than a
        tinted background -- deliberately, because an unresolved or fixed-light background
        inverts under themed text, which is the defect class this repo has shipped twice.
        But a fixed tone colour still sits on a surface that changes, so it must clear the
        WCAG 1.4.11 non-text floor of 3:1 against each `--app-surface-raised` value.

        It did not. The warning tone shipped as `#fd7e14`: 5.50:1 on the dark surface and
        **2.46:1 on the light one**. Nothing was unreadable -- the message text is
        `--app-text` at 12.91:1 -- so the eye passes over it, and no existing guard could
        catch it: the repo-wide token test only sees undefined tokens, and a hardcoded
        literal is by definition defined.

        This asserts the class rather than the three current values, so it also fails if
        someone later retunes `--app-surface-raised` underneath colours that pass today.
        Graphite uses lighter success and danger tones from the late-loaded page override
        because its raised surface is intentionally brighter than the AMOLED surface.
        """
        themes = (ROOT / 'static' / 'css' / 'app-themes.css').read_text(encoding='utf-8')
        surfaces = re.findall(r'--app-surface-raised:\s*(#[0-9a-fA-F]{6})', themes)
        self.assertEqual(
            len(surfaces), 3,
            f'expected one light, AMOLED, and Graphite --app-surface-raised, found {surfaces}',
        )

        def relative_luminance(value):
            channels = [int(value.lstrip('#')[index:index + 2], 16) / 255 for index in (0, 2, 4)]
            linear = [
                channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4
                for channel in channels
            ]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

        def contrast(first, second):
            lighter, darker = sorted(
                (relative_luminance(first), relative_luminance(second)), reverse=True
            )
            return (lighter + 0.05) / (darker + 0.05)

        for name in ('reimbursement_tracker.html', 'po_details.html'):
            template = (ROOT / 'templates' / name).read_text(encoding='utf-8')
            tones = dict(re.findall(
                r'\.page-toast\.([a-z]+)\s*\{\s*border-left-color:\s*(#[0-9a-fA-F]{6})',
                template,
            ))
            self.assertEqual(
                set(tones), {'success', 'warning', 'danger'},
                f'{name}: expected three toast tones, found {sorted(tones)}',
            )
            graphite_tones = {'success': '#4ade80', 'danger': '#f87171'}
            for tone, colour in sorted(tones.items()):
                for surface_index, surface in enumerate(surfaces):
                    effective_colour = graphite_tones.get(tone, colour) if surface_index == 2 else colour
                    ratio = contrast(effective_colour, surface)
                    self.assertGreaterEqual(
                        round(ratio, 2), 3.0,
                        f'{name}: the {tone} toast tone {effective_colour} measures {ratio:.2f}:1 on '
                        f'{surface}, below the 3:1 floor for a border and icon',
                    )

    def test_shared_theme_assets_and_controls_are_present(self):
        layout = (ROOT / 'templates' / 'layout.html').read_text(encoding='utf-8')
        settings = (ROOT / 'templates' / 'settings.html').read_text(encoding='utf-8')
        runtime = (ROOT / 'static' / 'js' / 'app-appearance.js').read_text(encoding='utf-8')
        styles = (ROOT / 'static' / 'css' / 'app-themes.css').read_text(encoding='utf-8')

        self.assertIn('app-themes.css', layout)
        self.assertIn('app-dark-pages.css', layout)
        self.assertGreater(layout.index('app-dark-pages.css'), layout.index('{% block content %}'))
        self.assertIn('app-appearance.js', layout)
        self.assertEqual(layout.count('onclick="window.appAppearance && window.appAppearance.toggleQuick()"'), 2)
        self.assertIn('data-appearance-mode="system"', settings)
        self.assertIn('data-appearance-accent="shimadzu-red"', settings)
        self.assertIn("app-theme-changed", runtime)
        self.assertIn('[data-app-theme="dark"]', styles)
        self.assertIn('@media print', styles)

        app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        assert_cache_version_at_least(self, 35, app_source)
        self.assertIn("'/static/css/app-dark-pages.css'", app_source)

    def test_graphite_palette_is_shared_by_theme_layers(self):
        """Graphite has one neutral palette in both theme layers."""
        theme_css = (ROOT / 'static' / 'css' / 'app-themes.css').read_text(encoding='utf-8')
        dark_css = (ROOT / 'static' / 'css' / 'app-dark-pages.css').read_text(encoding='utf-8')

        theme_match = re.search(
            r':root\[data-app-theme="dark"\]\[data-app-palette="graphite"\]\s*\{([^}]*)\}',
            theme_css,
            re.IGNORECASE,
        )
        dark_match = re.search(
            r':root\[data-app-theme="dark"\]\[data-app-palette="graphite"\]\s*\{([^}]*)\}',
            dark_css,
            re.IGNORECASE,
        )
        self.assertIsNotNone(theme_match, 'shared theme is missing the Graphite palette block')
        self.assertIsNotNone(dark_match, 'late-loaded page theme is missing the Graphite palette block')

        expected_theme = {
            '--app-bg': '#202124',
            '--app-surface': '#292a2d',
            '--app-surface-raised': '#333438',
            '--app-input': '#202124',
            '--app-text': '#ededed',
            '--app-muted': '#b8bbc2',
            '--app-border': '#85888d',
            '--app-sidebar': '#202124',
        }
        expected_page = {
            '--dark-page': '#202124',
            '--dark-panel': '#292a2d',
            '--dark-card': '#333438',
            '--dark-input': '#202124',
            '--dark-text': '#ededed',
            '--dark-muted': '#b8bbc2',
            '--dark-border': '#85888d',
        }
        for token, colour in expected_theme.items():
            with self.subTest(layer='shared', token=token):
                self.assertRegex(theme_match.group(1).lower(), rf'{re.escape(token)}\s*:\s*{re.escape(colour)}\b')
        for token, colour in expected_page.items():
            with self.subTest(layer='late', token=token):
                self.assertRegex(dark_match.group(1).lower(), rf'{re.escape(token)}\s*:\s*{re.escape(colour)}\b')

    def test_graphite_text_and_control_contrast_contract(self):
        """Graphite text and essential boundaries clear the approved contrast floors."""
        def relative_luminance(value):
            channels = [int(value.lstrip('#')[index:index + 2], 16) / 255 for index in (0, 2, 4)]
            linear = [
                channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4
                for channel in channels
            ]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

        def contrast(first, second):
            lighter, darker = sorted(
                (relative_luminance(first), relative_luminance(second)), reverse=True
            )
            return (lighter + 0.05) / (darker + 0.05)

        for surface in ('#202124', '#292a2d', '#333438'):
            self.assertGreaterEqual(contrast('#ededed', surface), 4.5)
            self.assertGreaterEqual(contrast('#b8bbc2', surface), 4.5)
        self.assertGreaterEqual(contrast('#85888d', '#292a2d'), 3.0)
        self.assertGreaterEqual(contrast('#85888d', '#333438'), 3.0)

    def test_graphite_preference_api_and_settings_contract(self):
        app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        settings = (ROOT / 'templates' / 'settings.html').read_text(encoding='utf-8')

        self.assertIn("APPEARANCE_THEME_MODES = {'light', 'dark', 'graphite', 'system'}", app_source)
        self.assertIn("'graphite'", app_source)
        self.assertIn("effective_mode = 'dark' if mode == 'graphite'", app_source)
        self.assertIn('data-appearance-mode="graphite"', settings)
        self.assertIn("setAppearanceMode('graphite')", settings)
        self.assertIn('Graphite Dark', settings)
        self.assertIn('AMOLED Black', settings)

    def test_appearance_payload_resolves_graphite_to_bootstrap_dark(self):
        """The wire mode stays Graphite while the effective Bootstrap theme stays dark."""
        expected_effective_modes = {
            'light': 'light',
            'dark': 'dark',
            'graphite': 'dark',
            'system': 'system',
        }
        for mode, expected_effective in expected_effective_modes.items():
            with self.subTest(mode=mode):
                user = SimpleNamespace(
                    ui_theme_mode=mode,
                    ui_accent_theme='classic',
                    ui_theme_updated_at=None,
                )
                payload = app_module.appearance_preference_payload(user)
                self.assertEqual(payload['mode'], mode)
                self.assertEqual(payload['effective_mode'], expected_effective)

    def test_graphite_runtime_cycle_and_busy_guard(self):
        runtime = (ROOT / 'static' / 'js' / 'app-appearance.js').read_text(encoding='utf-8')

        self.assertIn("const QUICK_MODE_CYCLE = ['light', 'graphite', 'dark'];", runtime)
        self.assertIn('function nextQuickMode(mode)', runtime)
        self.assertIn("root.dataset.appPalette = paletteFor(state.mode);", runtime)
        self.assertIn("normalized === 'graphite'", runtime)
        self.assertIn('let quickToggleBusy = false;', runtime)
        self.assertIn('if (quickToggleBusy || state.pending)', runtime)
        self.assertIn("'Switch to Graphite Dark'", runtime)
        self.assertIn("'Switch to AMOLED Black'", runtime)
        self.assertIn("'Switch to Light'", runtime)
        self.assertIn('button.disabled = quickToggleBusy || state.pending;', runtime)

    def test_graphite_runtime_cycle_executes_in_node(self):
        runtime = (ROOT / 'static' / 'js' / 'app-appearance.js').read_text(encoding='utf-8')
        harness = textwrap.dedent(
            """
            const fs = require('fs');
            const vm = require('vm');
            const root = {dataset: {}};
            const meta = {content: ''};
            const buttons = [{title: '', disabled: false, attrs: {}, setAttribute(key, value) { this.attrs[key] = value; }}];
            global.document = {
                documentElement: root,
                querySelector(selector) {
                    return selector === 'meta[name="theme-color"]' || selector === 'meta[name="csrf-token"]' ? meta : null;
                },
                querySelectorAll(selector) {
                    return selector === '.appearance-header-button' ? buttons : [];
                },
                addEventListener() {},
            };
            Object.defineProperty(globalThis, 'navigator', {value: {onLine: true}, configurable: true});
            global.CustomEvent = class { constructor(type, init) { this.type = type; this.detail = init && init.detail; } };
            const media = {matches: false, addEventListener() {}};
            global.window = {
                __initialAppearance: {mode: 'light', accent: 'classic', userId: 42},
                matchMedia() { return media; },
                addEventListener() {},
                dispatchEvent() {},
            };
            global.fetch = async function(url, options) {
                const payload = JSON.parse(options.body);
                return {ok: true, async json() { return {success: true, mode: payload.mode, accent: payload.accent}; }};
            };
            vm.runInThisContext(%SOURCE%);
            window.appAppearance.apply('light', 'classic');
            (async function() {
                if (window.appAppearance.getState().mode !== 'light' || root.dataset.appPalette !== 'light') throw new Error('light setup failed');
                await window.appAppearance.toggleQuick();
                if (window.appAppearance.getState().mode !== 'graphite' || root.dataset.appTheme !== 'dark' || root.dataset.appPalette !== 'graphite') throw new Error('graphite step failed');
                if (buttons[0].title !== 'Switch to AMOLED Black' || meta.content !== '#202124') throw new Error(`graphite controls failed: ${buttons[0].title} / ${meta.content}`);
                await window.appAppearance.toggleQuick();
                if (window.appAppearance.getState().mode !== 'dark' || root.dataset.appPalette !== 'amoled') throw new Error('amoled step failed');
                if (buttons[0].title !== 'Switch to Light' || meta.content !== '#000000') throw new Error('amoled controls failed');
                await window.appAppearance.toggleQuick();
                if (window.appAppearance.getState().mode !== 'light' || root.dataset.appPalette !== 'light') throw new Error('cycle reset failed');
                if (buttons[0].title !== 'Switch to Graphite Dark' || meta.content !== '#2c3e50') throw new Error('light controls failed');
                media.matches = true;
                window.appAppearance.apply('system', 'classic');
                if (window.appAppearance.getState().effectiveMode !== 'dark' || root.dataset.appPalette !== 'amoled' || buttons[0].title !== 'Switch to Light') throw new Error('system dark resolution failed');
                media.matches = false;
                window.appAppearance.apply('system', 'classic');
                if (window.appAppearance.getState().effectiveMode !== 'light' || root.dataset.appPalette !== 'light' || buttons[0].title !== 'Switch to Graphite Dark') throw new Error('system light resolution failed');
            })().catch(error => { console.error(error.stack || error); process.exit(1); });
            """
        ).replace('%SOURCE%', json.dumps(runtime))
        result = subprocess.run(
            ['node', '--input-type=commonjs', '-e', harness],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_graphite_first_paint_auth_assets_and_browser_colour(self):
        runtime = (ROOT / 'static' / 'js' / 'app-appearance.js').read_text(encoding='utf-8')
        layout = (ROOT / 'templates' / 'layout.html').read_text(encoding='utf-8')
        auth_css = (ROOT / 'static' / 'css' / 'app-auth.css').read_text(encoding='utf-8')
        sources = [
            (ROOT / name).read_text(encoding='utf-8')
            for name in (
                'templates/login.html',
                'templates/forgot_password.html',
                'templates/reset_password.html',
            )
        ]

        self.assertIn("['light','graphite','dark','system']", layout)
        self.assertIn('dataset.appPalette', layout)
        self.assertIn("['light','graphite','dark','system']", sources[0])
        self.assertTrue(all('dataset.appPalette' in source for source in sources))
        self.assertIn("palette === 'graphite' ? '#202124'", runtime)
        self.assertIn("palette === 'amoled' ? '#000000'", runtime)
        self.assertIn(':root[data-app-theme="dark"][data-app-palette="graphite"]', auth_css)
        self.assertIn('--login-page-bg: #202124;', auth_css)

        self.assertIn("filename='css/app-themes.css') }}?v=21", layout)
        self.assertIn("filename='css/app-dark-pages.css') }}?v=28", layout)
        self.assertIn("filename='js/app-appearance.js') }}?v=18", layout)
        for source in sources:
            self.assertIn("filename='css/app-themes.css') }}?v=21", source)
            self.assertIn("filename='css/app-auth.css') }}?v=4", source)

    def test_graphite_release_and_cache_marker_are_current(self):
        app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        manifest = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))

        self.assertIn('medical-service-pwa-offline-navigation-v141-calendar-week-navigation', app_source)
        matches = [
            item
            for release in manifest['releases']
            for item in release.get('items', [])
            if item.get('item_key') == '2026-09-07-graphite-dark-everyone'
        ]
        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0].get('description'))

    def test_amoled_palette_is_shared_by_theme_layers(self):
        """Dark mode uses the approved true-black palette in both CSS layers."""
        theme_css = (ROOT / 'static' / 'css' / 'app-themes.css').read_text(encoding='utf-8')
        dark_css = (ROOT / 'static' / 'css' / 'app-dark-pages.css').read_text(encoding='utf-8')

        expected = {
            '--app-bg': '#000000',
            '--app-surface': '#101010',
            '--app-surface-raised': '#191919',
            '--app-text': '#ededed',
            '--app-muted': '#b0b0b0',
        }
        for token, colour in expected.items():
            with self.subTest(token=token):
                self.assertRegex(
                    theme_css,
                    rf':root\[data-app-theme="dark"\][\s\S]*?{re.escape(token)}:\s*{re.escape(colour)}\b',
                )

        dark_expected = {
            '--dark-page': '#000000',
            '--dark-panel': '#101010',
            '--dark-card': '#191919',
            '--dark-text': '#ededed',
            '--dark-muted': '#b0b0b0',
        }
        for token, colour in dark_expected.items():
            with self.subTest(token=token):
                self.assertRegex(
                    dark_css,
                    rf':root\[data-app-theme="dark"\][\s\S]*?{re.escape(token)}:\s*{re.escape(colour)}\b',
                )

    def test_amoled_text_and_control_contrast_contract(self):
        """The core text and control colors remain legible on AMOLED surfaces."""
        theme_css = (ROOT / 'static' / 'css' / 'app-themes.css').read_text(encoding='utf-8')

        def relative_luminance(value):
            channels = [int(value.lstrip('#')[index:index + 2], 16) / 255 for index in (0, 2, 4)]
            linear = [
                channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4
                for channel in channels
            ]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

        def contrast(first, second):
            lighter, darker = sorted(
                (relative_luminance(first), relative_luminance(second)), reverse=True
            )
            return (lighter + 0.05) / (darker + 0.05)

        dark_block = re.search(
            r':root\[data-app-theme="dark"\]\s*\{([^}]*)\}',
            theme_css,
        ).group(1)
        values = dict(re.findall(
            r'(--app-(?:bg|surface|surface-raised|text|muted|border)):\s*(#[0-9a-fA-F]{6})',
            dark_block,
        ))
        self.assertEqual(
            values,
            {
                '--app-bg': '#000000',
                '--app-surface': '#101010',
                '--app-surface-raised': '#191919',
                '--app-text': '#ededed',
                '--app-muted': '#b0b0b0',
                '--app-border': '#626262',
            },
        )
        for surface in ('#000000', '#101010', '#191919'):
            self.assertGreaterEqual(contrast('#ededed', surface), 4.5)
            self.assertGreaterEqual(contrast('#b0b0b0', surface), 4.5)
        self.assertGreaterEqual(contrast('#626262', '#101010'), 3.0)

    def test_amoled_runtime_and_asset_versions_are_present(self):
        runtime = (ROOT / 'static' / 'js' / 'app-appearance.js').read_text(encoding='utf-8')
        layout = (ROOT / 'templates' / 'layout.html').read_text(encoding='utf-8')
        auth_styles = (ROOT / 'static' / 'css' / 'app-auth.css').read_text(encoding='utf-8')
        auth = [
            (ROOT / name).read_text(encoding='utf-8')
            for name in ('templates/login.html', 'templates/forgot_password.html', 'templates/reset_password.html')
        ]
        self.assertIn("palette === 'amoled' ? '#000000'", runtime)
        self.assertIn('--login-page-bg: #000000;', auth_styles)
        self.assertIn("filename='css/app-themes.css') }}?v=21", layout)
        self.assertIn("filename='css/app-dark-pages.css') }}?v=28", layout)
        self.assertIn("filename='js/app-appearance.js') }}?v=18", layout)
        for source in auth:
            self.assertIn("filename='css/app-themes.css') }}?v=21", source)
            self.assertIn("filename='css/app-auth.css') }}?v=4", source)

    def test_amoled_dark_page_layer_does_not_restore_navy_neutrals(self):
        dark_css = (ROOT / 'static' / 'css' / 'app-dark-pages.css').read_text(encoding='utf-8')
        for old_colour in (
            '#0f1722', '#182333', '#202d3e', '#263549', '#111b29', '#3b4a5e', '#101925',
        ):
            self.assertNotIn(old_colour, dark_css.lower(), f'old dark neutral remains: {old_colour}')
        self.assertIn('background: var(--dark-panel) !important;', dark_css)
        self.assertIn('background: var(--dark-card) !important;', dark_css)

    def test_additional_accent_themes_are_available_across_the_app(self):
        app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        settings = (ROOT / 'templates' / 'settings.html').read_text(encoding='utf-8')
        styles = (ROOT / 'static' / 'css' / 'app-themes.css').read_text(encoding='utf-8')
        auth_styles = (ROOT / 'static' / 'css' / 'app-auth.css').read_text(encoding='utf-8')
        expected = {
            'purple': '#6d28d9',
            'pink': '#be185d',
            'teal': '#0f766e',
        }

        for accent, colour in expected.items():
            with self.subTest(accent=accent):
                self.assertIn(f"'{accent}'", app_source)
                self.assertIn(f'data-appearance-accent="{accent}"', settings)
                self.assertIn(f"setAppearanceAccent('{accent}')", settings)
                self.assertIn(f':root[data-accent-theme="{accent}"]', styles)
                self.assertIn(f'--app-primary: {colour};', styles)
                self.assertIn(f':root[data-accent-theme="{accent}"]', auth_styles)

        for name in ('layout.html', 'login.html', 'forgot_password.html', 'reset_password.html'):
            source = (ROOT / 'templates' / name).read_text(encoding='utf-8')
            for accent in expected:
                self.assertIn(f"'{accent}'", source, f'{name} does not accept {accent}')

    def test_login_uses_last_device_appearance(self):
        login = (ROOT / 'templates' / 'login.html').read_text(encoding='utf-8')
        self.assertIn('medical_appearance_last', login)
        self.assertIn('app-themes.css', login)

    def test_release_manifest_contains_theme_release(self):
        manifest = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))
        release = next(item for item in manifest['releases'] if item['release_key'] == '2026-07-16')
        self.assertTrue(release['is_published'])
        self.assertGreaterEqual(len(release['items']), 4)

    def test_dark_page_repair_covers_high_risk_surfaces(self):
        css = (ROOT / 'static' / 'css' / 'app-dark-pages.css').read_text(encoding='utf-8')
        for selector in (
            '.activity-summary-card',
            '.calendar-drop-cell',
            '.schedule-card',
            '.mobile-schedule-client',
            '.mobile-meta-row > span',
            '.dashboard-workflow-card',
            '.travel-notification-panel',
        ):
            self.assertIn(selector, css)
        self.assertIn('@media print', css)

    def test_calendar_dark_mode_preserves_schedule_categories(self):
        css = (ROOT / 'static' / 'css' / 'app-dark-pages.css').read_text(encoding='utf-8')
        timeline = (ROOT / 'templates' / 'timeline.html').read_text(encoding='utf-8')
        for selector in (
            '.schedule-card.schedule-office',
            '.schedule-card:is(.schedule-travel, .schedule-travel-request-block)',
            '.schedule-card.schedule-pullout',
            '.schedule-card.schedule-holiday',
            '.schedule-card:is(.schedule-leave, .border-danger)',
        ):
            self.assertIn(selector, css)
        self.assertIn('getScheduleSemanticClass(shift)', timeline)
        self.assertIn('--calendar-card-accent', css)

    def test_dark_mode_repairs_workflow_contrast(self):
        css = (ROOT / 'static' / 'css' / 'app-dark-pages.css').read_text(encoding='utf-8')
        layout = (ROOT / 'templates' / 'layout.html').read_text(encoding='utf-8')
        for selector in (
            '.accounting-shell .module-tab',
            '.accounting-shell .module-tab .module-title',
            '.accounting-shell .module-tab .module-desc',
            '.accounting-shell :is(.kpi-value',
            '[class*="-kpi-value"]',
            '[class*="-stat-value"]',
        ):
            self.assertIn(selector, css)
        self.assertIn("filename='css/app-dark-pages.css') }}?v=28", layout)

    def test_dark_mode_covers_native_and_custom_dropdowns(self):
        css = (ROOT / 'static' / 'css' / 'app-dark-pages.css').read_text(encoding='utf-8')
        lpr = (ROOT / 'templates' / 'lpr.html').read_text(encoding='utf-8')
        for selector in (
            ':root[data-app-theme="dark"] select,',
            'select option,',
            'select optgroup',
            'select:disabled',
            '[role="listbox"]',
            '[class*="-dropdown-menu"]',
            '.search-item, .travel-search-item',
            '.travel-equipment-toggle',
            '.tsr-category-menu',
            '.timeline-travel-suggestion-panel',
        ):
            self.assertIn(selector, css)
        self.assertIn('<select id="lprBranch">', lpr)

    def test_dark_mode_covers_attachment_and_receipt_surfaces(self):
        shared = (ROOT / 'static' / 'css' / 'app-themes.css').read_text(encoding='utf-8')
        css = (ROOT / 'static' / 'css' / 'app-dark-pages.css').read_text(encoding='utf-8')
        layout = (ROOT / 'templates' / 'layout.html').read_text(encoding='utf-8')
        for token in ('--app-input-bg:', '--app-surface-muted:', '--app-muted-text:'):
            self.assertIn(token, shared)
        for selector in (
            '.lpr-attachments',
            '.cash-attachment-panel',
            '.travel-attachment-item',
            '.reim-additional-receipts-card',
            '.tsr-attachment-package',
            '.approval-receipt-preview-modal',
            '.receipt-pill, .reim-receipt-pill',
        ):
            self.assertIn(selector, css)
        self.assertIn("filename='css/app-themes.css') }}?v=21", layout)

    def test_dark_mode_covers_system_neutral_surfaces(self):
        css = (ROOT / 'static' / 'css' / 'app-dark-pages.css').read_text(encoding='utf-8')
        for selector in (
            '.cash-signature-box, .travel-signature-box',
            '.travel-status:not(.success):not(.error)',
            '.cash-notification-list, .reim-notification-card',
            '.manager-executive-dashboard',
            '[class*="manager-"][class*="-panel"]',
            '.approval-decision-panel',
            '.product-confirm-box, .client-confirm-box, .engineer-confirm-box',
            '.email-recipient-form-panel',
            '.schedule-picker-selected',
        ):
            self.assertIn(selector, css)

    def test_dark_mode_covers_nested_light_surfaces(self):
        css = (ROOT / 'static' / 'css' / 'app-dark-pages.css').read_text(encoding='utf-8')
        for selector in (
            '#status-container, #file-container, #site-visit-flags-container',
            '#edit-scope-container, .time-planner-box',
            '.email-recipient-group-header, .email-template-header',
            '.email-template-placeholder-wrap, .email-template-preview',
            '.settings-user-filter-wrap, .settings-user-filter',
            '.reim-lifecycle-banner.draft',
            '.reim-table :is(th, td)',
            '.reim-btn-secondary, .reim-btn-danger-outline',
        ):
            self.assertIn(selector, css)

    def test_changelog_dark_contrast_and_compact_header_controls(self):
        dark_css = (ROOT / 'static' / 'css' / 'app-dark-pages.css').read_text(encoding='utf-8')
        theme_css = (ROOT / 'static' / 'css' / 'app-themes.css').read_text(encoding='utf-8')
        layout = (ROOT / 'templates' / 'layout.html').read_text(encoding='utf-8')
        for selector in (
            '.changelog-title,',
            '.changelog-subtitle, .changelog-summary',
            '.changelog-category-title',
            '.changelog-item',
        ):
            self.assertIn(selector, dark_css)
        self.assertIn('.sidebar-header .appearance-header-button {', theme_css)
        # Shell CSS moved out of layout.html's inline <style> into app-shell.css,
        # which collapsed three overlapping generations of sidebar rules into one.
        shell_css = (ROOT / 'static' / 'css' / 'app-shell.css').read_text(encoding='utf-8')
        self.assertIn('.sidebar-header .appearance-header-button,', shell_css)
        self.assertIn('.sidebar-header .changelog-header-button {', shell_css)
        self.assertIn('width: 34px;', shell_css)
        self.assertIn("css/app-shell.css", layout)


if __name__ == '__main__':
    unittest.main()
