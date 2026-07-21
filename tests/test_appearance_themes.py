import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AppearanceThemeSourceTests(unittest.TestCase):
    def test_shared_theme_assets_and_controls_are_present(self):
        layout = (ROOT / 'templates' / 'layout.html').read_text(encoding='utf-8')
        settings = (ROOT / 'templates' / 'settings.html').read_text(encoding='utf-8')
        runtime = (ROOT / 'static' / 'js' / 'app-appearance.js').read_text(encoding='utf-8')
        styles = (ROOT / 'static' / 'css' / 'app-themes.css').read_text(encoding='utf-8')

        self.assertIn('app-themes.css', layout)
        self.assertIn('app-dark-pages.css', layout)
        self.assertGreater(layout.index('app-dark-pages.css'), layout.index('{% block content %}'))
        self.assertIn('app-appearance.js', layout)
        self.assertEqual(layout.count('appearance-header-button'), 2)
        self.assertIn('data-appearance-mode="system"', settings)
        self.assertIn('data-appearance-accent="shimadzu-red"', settings)
        self.assertIn("app-theme-changed", runtime)
        self.assertIn('[data-app-theme="dark"]', styles)
        self.assertIn('@media print', styles)

        app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        self.assertIn('medical-service-pwa-offline-navigation-v29-dark-inner-surfaces', app_source)
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
        self.assertIn("filename='css/app-dark-pages.css') }}?v=23", layout)

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
        self.assertIn("filename='css/app-themes.css') }}?v=17", layout)

    def test_dark_mode_covers_system_neutral_surfaces(self):
        css = (ROOT / 'static' / 'css' / 'app-dark-pages.css').read_text(encoding='utf-8')
        for selector in (
            '.cash-signature-box, .travel-signature-box',
            '.travel-status:not(.success):not(.error)',
            '.cash-notification-list, .reim-notification-card',
            '.developer-dashboard-switcher, .manager-executive-dashboard',
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


if __name__ == '__main__':
    unittest.main()
