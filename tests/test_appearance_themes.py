import json
import re
import unittest
from pathlib import Path

from tests.sw_cache_version import assert_cache_version_at_least


ROOT = Path(__file__).resolve().parents[1]

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
        """A fixed colour on a themed surface has two contrast ratios, not one.

        The register toasts carry their tone on a left border and an icon rather than a
        tinted background -- deliberately, because an unresolved or fixed-light background
        inverts under themed text, which is the defect class this repo has shipped twice.
        But a fixed tone colour still sits on a surface that changes, so it must clear the
        WCAG 1.4.11 non-text floor of 3:1 against BOTH `--app-surface-raised` values.

        It did not. The warning tone shipped as `#fd7e14`: 5.50:1 on the dark surface and
        **2.46:1 on the light one**. Nothing was unreadable -- the message text is
        `--app-text` at 12.91:1 -- so the eye passes over it, and no existing guard could
        catch it: the repo-wide token test only sees undefined tokens, and a hardcoded
        literal is by definition defined.

        This asserts the class rather than the three current values, so it also fails if
        someone later retunes `--app-surface-raised` underneath colours that pass today.
        Success and danger clear the floor by only ~0.12 on the dark surface, so that is
        not a hypothetical.
        """
        themes = (ROOT / 'static' / 'css' / 'app-themes.css').read_text(encoding='utf-8')
        surfaces = re.findall(r'--app-surface-raised:\s*(#[0-9a-fA-F]{6})', themes)
        self.assertEqual(
            len(surfaces), 2,
            f'expected one light and one dark --app-surface-raised, found {surfaces}',
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
            for tone, colour in sorted(tones.items()):
                for surface in surfaces:
                    ratio = contrast(colour, surface)
                    self.assertGreaterEqual(
                        round(ratio, 2), 3.0,
                        f'{name}: the {tone} toast tone {colour} measures {ratio:.2f}:1 on '
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
        self.assertIn("filename='css/app-dark-pages.css') }}?v=24", layout)

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
        self.assertIn("filename='css/app-themes.css') }}?v=18", layout)

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
