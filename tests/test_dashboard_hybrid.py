"""Dashboard phase 4 -- shortcut consolidation, and retiring unreachable hybrid sections.

Phase 4 set out to redesign the hybrid admin+engineer sections and found they cannot
render: they were gated on `admin_view and not manager_view`, but is_manager_dashboard_user()
returns true for any admin-authorized non-scheduler, so every admin lands in the manager
view. The reachable part of the phase was the shortcut merge -- nine destinations were
offered fifteen times across three blocks -- and the rest was retired.
"""

import os
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Pin an isolated database BEFORE importing app.py so the suite can never open the real
# scheduler.db.
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_hybrid_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402
from tests.sw_cache_version import assert_cache_version_at_least  # noqa: E402


class HybridGateReachabilityTests(unittest.TestCase):
    """The finding that redirected this phase, pinned so it cannot be forgotten."""

    def test_the_hybrid_gate_cannot_be_satisfied(self):
        """`admin_view and not manager_view` is unsatisfiable by construction.

        is_manager_dashboard_user() returns true for `is_admin_authorized and not
        is_scheduler_user`, which is exactly what admin_view requires once schedulers are
        excluded. Any future attempt to revive those sections has to change this predicate
        first, and this test says so.
        """
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        predicate = source.split('def is_manager_dashboard_user')[1].split('\ndef ')[0]
        self.assertIn('is_admin_authorized(target) and not is_scheduler_user(target)',
                      predicate)


class HybridDashboardSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.dashboard = (ROOT / 'templates' / 'dashboard.html').read_text(encoding='utf-8')
        cls.css = (ROOT / 'static' / 'css' / 'app-dashboard.css').read_text(encoding='utf-8')
        cls.js = (ROOT / 'static' / 'js' / 'app-dashboard.js').read_text(encoding='utf-8')

    def test_unreachable_sections_and_their_endpoint_are_gone(self):
        for retired in ('needs-attention', 'team-intelligence'):
            self.assertNotIn(f'data-dashboard-section="{retired}"', self.dashboard)
            # The ids stay registered so a saved layout naming them still saves.
            self.assertIn(f"'{retired}',", self.app_source)

        for endpoint in ('/get_hybrid_overview', '/get_hybrid_dashboard_team_summary',
                         '/get_hybrid_dashboard_smart_monitoring'):
            self.assertNotIn(f"@app.route('{endpoint}')", self.app_source)
            self.assertNotIn(endpoint, self.js)

    def test_the_shortcut_block_survived_and_lists_each_destination_once(self):
        self.assertIn('data-dashboard-section="quick-admin"', self.dashboard)
        for retired in ('dashboard-mobile-quick-actions', 'dashboard-engineer-workflow'):
            self.assertNotIn(retired, self.dashboard)
            self.assertNotIn(retired, self.css)

        grid = self.dashboard.split('hybrid-shortcut-grid')[1].split('</div>\n        </div>')[0]
        for destination in ('/timeline', '/offline-tsr', '/reports_page', '/clients_page',
                            '/products_page', '/analytics_page', '/engineers_page',
                            '/activity_page'):
            self.assertEqual(grid.count(f'href="{destination}"'), 1, destination)

    def test_shortcuts_are_gated_on_who_previously_had_them(self):
        """Merging into quick-admin briefly put them behind the unreachable gate.

        engineer-workflow was gated on holding an engineer profile alone, so every engineer
        saw it. If the merged block inherits the admin/manager gate instead, engineers lose
        their shortcuts entirely.
        """
        gate = self.dashboard.split('hybrid-shortcut-grid')[0]
        gate = gate.split('{% if ')[-1]
        self.assertIn('dashboard_has_engineer_profile', gate)
        self.assertNotIn('not dashboard_effective_manager_view', gate)

    def test_admin_only_destinations_are_gated(self):
        """A pure engineer must not be offered pages that bounce them back."""
        grid = self.dashboard.split('hybrid-shortcut-grid')[1].split('</div>\n        </div>')[0]
        admin_only = grid.split('{% if dashboard_effective_admin_view %}')[1]
        for destination in ('/analytics_page', '/engineers_page', '/activity_page'):
            self.assertIn(f'href="{destination}"', admin_only)
        # Engineer-appropriate destinations stay outside that gate.
        before_gate = grid.split('{% if dashboard_effective_admin_view %}')[0]
        for destination in ('/timeline', '/reports_page', '/clients_page', '/products_page'):
            self.assertIn(f'href="{destination}"', before_gate)

    def test_directory_totals_moved_somewhere_reachable(self):
        # admin-counters used to sit behind the unreachable gate; it now renders inside the
        # manager block, which is where every admin account actually lands.
        self.assertIn('data-dashboard-section="admin-counters"', self.dashboard)
        manager_block = self.dashboard.split(
            '{% if dashboard_effective_manager_view and not dashboard_effective_scheduler_only %}')[1]
        manager_block = manager_block.split('{% if dashboard_has_engineer_profile %}')[0]
        self.assertIn('data-dashboard-section="admin-counters"', manager_block)
        for count_id in ('count-engineers', 'count-clients', 'count-products'):
            self.assertIn(f'id="{count_id}"', manager_block)

    def test_dead_hybrid_css_was_removed_but_shortcut_styles_kept(self):
        for dead in ('hybrid-risk', 'hybrid-metric', 'hybrid-attention',
                     'dashboard-needs-attention', 'dashboard-team-intelligence',
                     'dashboard-workflow-card', 'dashboard-admin-action-card',
                     'dashboard-mobile-action-card'):
            self.assertNotIn(dead, self.css)
        self.assertIn('hybrid-shortcut', self.css)
        self.assertEqual(self.css.count('{'), self.css.count('}'), 'CSS braces must balance')

    def test_dashboard_assets_are_cached_and_version_bumped(self):
        self.assertIn("'/static/css/app-dashboard.css',", self.app_source)
        self.assertIn("'/static/js/app-dashboard.js',", self.app_source)
        assert_cache_version_at_least(self, 48, self.app_source)

    def test_extracted_js_has_no_template_syntax(self):
        self.assertNotIn('{{', self.js)
        self.assertNotIn('{%', self.js)


class RetiredHybridEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            app_module.db.create_all()
            username = app_module.DEVELOPER_SUPERADMIN_USERNAME
            user = app_module.User.query.filter_by(username=username).first()
            if not user:
                user = app_module.User(
                    username=username, role='superadmin', is_active=True,
                    password=app_module.generate_password_hash('HybridTest123'))
                app_module.db.session.add(user)
                app_module.db.session.commit()
            cls.admin_username = username

    def _admin_client(self):
        with self.app.app_context():
            user_id = app_module.User.query.filter_by(username=self.admin_username).first().id
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def test_all_three_hybrid_endpoints_are_gone(self):
        client = self._admin_client()
        for endpoint in ('/get_hybrid_overview', '/get_hybrid_dashboard_team_summary',
                         '/get_hybrid_dashboard_smart_monitoring'):
            self.assertEqual(client.get(endpoint).status_code, 404, endpoint)

    def test_layout_api_still_accepts_the_retired_section_ids(self):
        client = self._admin_client()
        response = client.post('/api/preferences/dashboard-layout', json={
            'order': ['needs-attention', 'team-intelligence', 'mobile-quick-actions',
                      'engineer-workflow', 'quick-admin'],
            'hidden': []
        })
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
