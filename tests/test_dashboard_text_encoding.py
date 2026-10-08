import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# UTF-8 punctuation that was decoded as Windows-1252 and saved again: an arrow,
# em dash and bullet showed on the dashboard as these three-character sequences.
MOJIBAKE = ('â†’', 'â€”', 'â€¢', 'â€“', 'â€™')


class DashboardTextEncodingTests(unittest.TestCase):
    def test_front_end_sources_have_no_double_encoded_punctuation(self):
        sources = sorted(
            list((ROOT / 'templates').rglob('*.html'))
            + list((ROOT / 'static' / 'js').rglob('*.js'))
            + list((ROOT / 'static' / 'css').rglob('*.css'))
        )
        offenders = [
            str(path.relative_to(ROOT))
            for path in sources
            if any(seq in path.read_text(encoding='utf-8') for seq in MOJIBAKE)
        ]
        self.assertEqual(offenders, [])
        dashboard_js = (ROOT / 'static' / 'js' / 'app-dashboard.js').read_text(encoding='utf-8')
        self.assertIn('`${startLabel} → ${endLabel}`', dashboard_js)

    def test_whats_new_bell_tile_is_themed_in_dark_mode(self):
        dashboard = (ROOT / 'templates' / 'dashboard.html').read_text(encoding='utf-8')
        dark = (ROOT / 'static' / 'css' / 'app-dark-pages.css').read_text(encoding='utf-8')
        self.assertIn('class="dashboard-whats-new-icon"', dashboard)
        self.assertIn(':root[data-app-theme="dark"] .dashboard-whats-new .dashboard-whats-new-icon {', dark)


if __name__ == '__main__':
    unittest.main()
