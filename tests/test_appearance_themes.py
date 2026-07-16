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
        self.assertIn('app-appearance.js', layout)
        self.assertEqual(layout.count('appearance-header-button'), 2)
        self.assertIn('data-appearance-mode="system"', settings)
        self.assertIn('data-appearance-accent="shimadzu-red"', settings)
        self.assertIn("app-theme-changed", runtime)
        self.assertIn('[data-app-theme="dark"]', styles)
        self.assertIn('@media print', styles)

    def test_login_uses_last_device_appearance(self):
        login = (ROOT / 'templates' / 'login.html').read_text(encoding='utf-8')
        self.assertIn('medical_appearance_last', login)
        self.assertIn('app-themes.css', login)

    def test_release_manifest_contains_theme_release(self):
        manifest = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))
        release = next(item for item in manifest['releases'] if item['release_key'] == '2026-07-16')
        self.assertTrue(release['is_published'])
        self.assertEqual(len(release['items']), 3)


if __name__ == '__main__':
    unittest.main()
