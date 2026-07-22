from pathlib import Path
import unittest

from app import get_tsr_other_assigned_engineer_names


ROOT = Path(__file__).resolve().parents[1]


class TsrAssignedEngineersLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')

    def test_single_day_team_uses_footer_not_body_coverage(self):
        self.assertIn('function shouldRenderTSRScheduleCoverage(scheduleOrData)', self.source)
        self.assertIn('function shouldRenderTSRScheduleCoverage(scheduleOrData){\n  return false;', self.source)
        self.assertIn('function buildTSRScheduleCoverageHTML(data){\n  return \'\';', self.source)
        self.assertIn('Other Assigned Engineer(s):', self.source)
        self.assertIn('function formatTSRServiceDateRange(scheduleOrData)', self.source)

    def test_screen_summary_remains_available(self):
        self.assertIn('function shouldShowTSRScheduleCoverage(scheduleOrData)', self.source)
        self.assertIn('Schedule Coverage', self.source)

    def test_backend_excludes_signer_for_single_day(self):
        rows = [{
            'date_iso': '2026-07-17',
            'engineer_names': ['Jonamar Paunil', 'Kevin Garoche', 'jonamar paunil'],
        }]
        self.assertEqual(
            get_tsr_other_assigned_engineer_names(rows, 'Jonamar Paunil'),
            ['Kevin Garoche'],
        )

    def test_backend_adds_other_engineers_for_multi_day(self):
        rows = [
            {'date_iso': '2026-07-17', 'engineer_names': ['Jonamar Paunil', 'Kevin Garoche']},
            {'date_iso': '2026-07-18', 'engineer_names': ['Jonamar Paunil', 'Kevin Garoche']},
        ]
        self.assertEqual(
            get_tsr_other_assigned_engineer_names(rows, 'Jonamar Paunil'),
            ['Kevin Garoche'],
        )

    def test_archive_preview_is_fingerprint_and_no_cache_aware(self):
        app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        self.assertIn("content_version = hashlib.sha256(pdf_bytes).hexdigest()[:20]", app_source)
        self.assertIn('`&v=${{fingerprint}}&preview_ts=${{Date.now()}}`', app_source)
        self.assertIn("'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0'", app_source)
        self.assertIn("medical-service-pwa-offline-navigation-v33-tsr-filename-template", app_source)


if __name__ == '__main__':
    unittest.main()
