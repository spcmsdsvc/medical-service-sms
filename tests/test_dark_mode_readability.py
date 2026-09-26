"""Focused dark-mode contracts for Product History and Calibration Report."""

import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class DarkModeReadabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.products = (ROOT / "templates" / "products.html").read_text(encoding="utf-8")
        cls.calibration_css = (ROOT / "static" / "css" / "app-calibration-report.css").read_text(encoding="utf-8")
        cls.offline_tsr = (ROOT / "templates" / "offline_tsr.html").read_text(encoding="utf-8")
        cls.app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        cls.releases = json.loads((ROOT / "static" / "changelog" / "releases.json").read_text(encoding="utf-8"))

    def test_product_history_has_dark_surface_and_readable_states(self):
        css = self.products
        self.assertIn(':root[data-app-theme="dark"] #productHistoryModal .product-history-visit', css)
        for token in (
            ".product-history-visit .text-muted",
            ".product-history-linked-list .btn-link",
            ".product-history-visit .badge.text-bg-light",
            ".product-history-state",
            ".product-history-visit a:focus-visible",
        ):
            self.assertIn(token, css)

    def test_calibration_editor_dark_contract_preserves_white_signature_canvas(self):
        css = self.calibration_css
        self.assertNotIn('[data-app-theme="dark"] .calibration-report-toolbar,[data-app-theme="dark"] .calibration-report-page{color:#111;}', css)
        for token in (
            '[data-app-theme="dark"] .calibration-report-page',
            '[data-app-theme="dark"] .calibration-report-section',
            '[data-app-theme="dark"] .calibration-report-field input',
            '[data-app-theme="dark"] .calibration-report-check-table',
            '[data-app-theme="dark"] .calibration-report-readonly',
            '[data-app-theme="dark"] .calibration-report-field input::placeholder',
            '[data-app-theme="dark"] .calibration-report-focal-group.is-disabled',
            '[data-app-theme="dark"] .calibration-report-signature-canvas',
            '[data-app-theme="dark"] .calibration-report-field input:focus',
        ):
            self.assertIn(token, css)
        self.assertRegex(css, r'\[data-app-theme="dark"\] \.calibration-report-signature-canvas\{[^}]*background:#fff')

    def test_calibration_css_cache_and_shell_marker_are_advanced(self):
        self.assertIn("css/app-calibration-report.css') }}?v=11", self.offline_tsr)
        self.assertIn("app-calibration-report.css?v=11", self.app_source)
        match = re.search(r"const CACHE_VERSION = 'medical-service-pwa-offline-navigation-v(\d+)-", self.app_source)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 197)
        release = next(item for item in self.releases["releases"] if item["release_key"] == "2026-09-25-dark-mode-readability")
        self.assertTrue(release["is_published"])


if __name__ == "__main__":
    unittest.main()
