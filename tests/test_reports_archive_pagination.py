import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReportsArchivePaginationSourceTests(unittest.TestCase):
    def test_archive_api_is_all_history_and_capped_at_ten_files(self):
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        route_start = source.index("@app.route('/get_tsr_archive')")
        route_end = source.index("@app.route('/preview_tsr_archive_file", route_start)
        route = source[route_start:route_end]

        self.assertNotIn('analytics_date_bounds()', route)
        self.assertIn('per_page = min(max(requested_per_page, 1), 10)', route)
        self.assertIn("'total_pages': total_pages", route)
        self.assertIn("'rows': page_rows", route)

    def test_archive_filters_are_separate_from_monitoring_dates(self):
        source = (ROOT / 'templates' / 'reports.html').read_text(encoding='utf-8')
        archive_params_start = source.index('function archiveParams(')
        archive_params_end = source.index('function currentArchiveScope', archive_params_start)
        archive_params = source[archive_params_start:archive_params_end]

        self.assertNotIn('reports-start-date', archive_params)
        self.assertNotIn('reports-end-date', archive_params)
        self.assertIn("params.set('per_page', '10')", archive_params)
        self.assertIn('Monitoring Range', source)
        self.assertIn('archive-page-indicator', source)


if __name__ == '__main__':
    unittest.main()
