"""Dashboard remodel phase C -- manager KPI tiles (ServiceTitan model).

The manager view opens with one row of clickable numbers. The tiles reuse the existing
count ids, so loadManagerOverview() and renderManagerApprovals() fill them unchanged, and
three of them filter What Needs Attention to one type. With no filter the watchlist
renders exactly as before.
"""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ManagerKpiSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.dashboard = (ROOT / 'templates' / 'dashboard.html').read_text(encoding='utf-8')
        cls.css = (ROOT / 'static' / 'css' / 'app-dashboard.css').read_text(encoding='utf-8')
        cls.js = (ROOT / 'static' / 'js' / 'app-dashboard.js').read_text(encoding='utf-8')
        start = cls.dashboard.index('{% if dashboard_effective_manager_view and not dashboard_effective_scheduler_only %}')
        cls.manager_block = cls.dashboard[start:cls.dashboard.index('SCOPE BOUNDARY', start)]

    def _function(self, name):
        return self.js.split(f'function {name}(')[1].split('\n    function ')[0].split('\n    async function ')[0]

    def test_tile_row_leads_the_manager_view(self):
        self.assertIn('class="manager-kpis', self.manager_block)
        tiles = self.manager_block.index('class="manager-kpis')
        for later in ('id="manager-approvals-grid"', 'id="manager-risk"', 'data-dashboard-section="manager-direction"',
                      'data-dashboard-section="manager-watchlist"', 'data-dashboard-section="admin-counters"'):
            self.assertLess(tiles, self.manager_block.index(later), later)

    def test_existing_count_ids_live_in_the_tiles(self):
        tiles = self.manager_block.split('class="manager-kpis')[1].split('</div>')[0]
        for count_id in ('manager-approvals-total', 'manager-overdue-count',
                         'manager-pending-tsr-count', 'manager-waiting-count', 'manager-kpi-pm'):
            self.assertIn(f'id="{count_id}"', tiles)
        # Each id still exists exactly once on the page.
        for count_id in ('manager-approvals-total', 'manager-overdue-count', 'manager-pending-tsr-count',
                         'manager-waiting-count', 'manager-open-count'):
            self.assertEqual(self.dashboard.count(f'id="{count_id}"'), 1, count_id)

    def test_tiles_link_and_filter(self):
        tiles = self.manager_block.split('class="manager-kpis')[1].split('</div>')[0]
        self.assertRegex(tiles, r'<a href="/approvals"[^>]*id="manager-kpi-approvals"')
        for kpi in ('severe_overdue', 'aged_tsr', 'waiting', 'pm'):
            self.assertIn(f"openManagerKpi('{kpi}')", tiles)
        self.assertIn('function openManagerKpi(', self.js)

    def test_watchlist_filter_is_optional_and_default_unchanged(self):
        self.assertRegex(self.js, r'function renderManagerWatchlist\(data, type\)')
        renderer = self._function('renderManagerWatchlist')
        # No type: the server's list as sent.
        self.assertIn("filter ? ", renderer)
        self.assertIn('watchlist_by_type', renderer)
        self.assertIn('id="manager-watchlist-filter"', self.manager_block)

    def test_zero_tiles_stay_neutral(self):
        setter = self._function('setManagerKpiValue')
        self.assertIn("'is-zero'", setter)
        self.assertIn('.manager-kpi.is-alert:not(.is-zero)', self.css)
        self.assertIn('.manager-kpi.is-warn:not(.is-zero)', self.css)

    def test_approvals_tile_follows_the_approver_gate(self):
        renderer = self._function('renderManagerApprovals')
        self.assertIn('manager-kpi-approvals', renderer)

    def test_overview_payload_carries_the_filter_data(self):
        self.assertIn("'watchlist_by_type':", self.app_source)
        self.assertIn("'watchlist_type_totals':", self.app_source)
        self.assertIn('watchlist_type_totals', self._function('renderManagerWatchlist'))
        self.assertIn("'severe_age_days': MANAGER_SEVERE_AGE_DAYS", self.app_source)

    def test_manager_layout_resets_once(self):
        self.assertRegex(self.manager_block,
                         r'data-dashboard-section="manager-executive"[^>]*data-dashboard-layout-version="4"')

    def test_kept_functions_still_defined(self):
        for name in ('loadManagerOverview', 'loadManagerApprovals', 'renderManagerApprovals',
                     'renderManagerPmSummary', 'renderManagerWatchlist', 'renderManagerRisk',
                     'renderManagerDirection', 'toggleDashboardSection'):
            self.assertTrue(re.search(rf'function {name}\(', self.js), name)

    def test_assets_and_cache_bumped(self):
        # At least, not equal: later dashboard work bumps these again.
        css_version = int(re.search(r"app-dashboard\.css'\) \}\}\?v=(\d+)", self.dashboard).group(1))
        js_version = int(re.search(r"app-dashboard\.js'\) \}\}\?v=(\d+)", self.dashboard).group(1))
        self.assertGreaterEqual(css_version, 9)
        self.assertGreaterEqual(js_version, 8)
        self.assertIn('-v289-manager-kpis', self.app_source)


if __name__ == '__main__':
    unittest.main()
