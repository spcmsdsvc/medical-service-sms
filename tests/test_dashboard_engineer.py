import os
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Pin an isolated database BEFORE importing app.py so the suite can never open the real
# scheduler.db.
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_dashboard_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402
from tests.sw_cache_version import assert_cache_version_at_least  # noqa: E402


class DashboardSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.dashboard = (ROOT / 'templates' / 'dashboard.html').read_text(encoding='utf-8')
        cls.css = (ROOT / 'static' / 'css' / 'app-dashboard.css').read_text(encoding='utf-8')
        cls.js = (ROOT / 'static' / 'js' / 'app-dashboard.js').read_text(encoding='utf-8')

    def test_inline_js_and_css_were_extracted(self):
        self.assertNotIn('<style>', self.dashboard)
        self.assertIn('css/app-dashboard.css', self.dashboard)
        self.assertIn('js/app-dashboard.js', self.dashboard)
        # Only the small config bootstrap should remain inline.
        self.assertIn('window.__dashboardConfig', self.dashboard)
        self.assertLess(len(self.dashboard), 120_000,
                        'dashboard.html should be far smaller after extraction')

    def test_extracted_js_has_no_template_syntax(self):
        self.assertNotIn('{{', self.js)
        self.assertNotIn('{%', self.js)
        self.assertIn('window.__dashboardConfig', self.js)

    def test_engineer_summary_is_a_strip_not_four_tiles(self):
        self.assertIn('dashboard-metric-strip', self.dashboard)
        self.assertNotIn('dashboard-engineer-summary-card', self.dashboard)
        # The count ids must survive so updateEngineerSummaryCards() keeps working.
        for count_id in ('count-my-active', 'count-my-upcoming',
                         'count-my-continuation', 'count-my-waiting'):
            self.assertIn(f'id="{count_id}"', self.dashboard)

    def test_engineer_shortcuts_are_not_duplicated(self):
        # Both blocks used to render the same five destinations, toggled by viewport.
        engineer_block = self.dashboard.split('dashboard-mobile-quick-actions')[1]
        engineer_block = engineer_block.split('dashboard-engineer-workflow')[0]
        self.assertNotIn('/offline-tsr', engineer_block)
        self.assertNotIn('/products_page', engineer_block)
        self.assertNotIn('display: none', self.css.split('.dashboard-engineer-workflow {')[2]
                         if self.css.count('.dashboard-engineer-workflow {') > 2 else '')

    def test_needs_you_today_is_built_from_loaded_data(self):
        self.assertIn('id="engineer-today-list"', self.dashboard)
        self.assertIn('function renderEngineerTodayPanel', self.js)
        # It must not introduce its own request; the phase was "show less, fetch same".
        panel = self.js.split('function renderEngineerTodayPanel')[1].split('\n    function ')[0]
        self.assertNotIn('fetch(', panel)
        self.assertIn('dashboard-today-clear', panel, 'an empty state must exist')

    def test_reference_table_starts_collapsed_for_engineers(self):
        self.assertIn('id="open-tasks-toggle"', self.dashboard)
        self.assertIn('aria-controls="open-tasks-panel"', self.dashboard)
        # The tbody id must not be reused by the wrapper.
        self.assertIn('<tbody id="open-tasks-body">', self.dashboard)

    def test_other_role_sections_are_untouched_this_phase(self):
        for section in ('scheduler-core', 'scheduler-dispatch', 'scheduler-coordination',
                        'manager-executive', 'admin-counters', 'needs-attention',
                        'team-intelligence', 'quick-admin', 'recent-activity'):
            self.assertIn(f'data-dashboard-section="{section}"', self.dashboard)

    def test_layout_preference_column_and_endpoint(self):
        self.assertIn('ui_dashboard_layout_json = db.Column(db.Text, nullable=True)', self.app_source)
        self.assertIn(
            "('ui_dashboard_layout_json', \"ALTER TABLE user ADD COLUMN ui_dashboard_layout_json TEXT\")",
            self.app_source
        )
        self.assertNotIn('DROP COLUMN ui_dashboard_layout_json', self.app_source)
        self.assertIn("@app.route('/api/preferences/dashboard-layout', methods=['GET', 'POST'])", self.app_source)
        self.assertIn('DASHBOARD_SECTION_IDS', self.app_source)

    def test_dashboard_assets_are_cached_and_version_bumped(self):
        self.assertIn("'/static/css/app-dashboard.css',", self.app_source)
        self.assertIn("'/static/js/app-dashboard.js',", self.app_source)
        assert_cache_version_at_least(self, 41, self.app_source)


class DashboardLayoutApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            app_module.db.create_all()

    def _client_for(self, username):
        with self.app.app_context():
            user = app_module.User.query.filter_by(username=username).first()
            if not user:
                user = app_module.User(
                    username=username, role='engineer', is_active=True,
                    password=app_module.generate_password_hash('DashTest123')
                )
                app_module.db.session.add(user)
                app_module.db.session.commit()
            user_id = user.id

        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def test_requires_login(self):
        response = self.app.test_client().get('/api/preferences/dashboard-layout')
        self.assertIn(response.status_code, (302, 401))

    def test_round_trips_order_and_hidden(self):
        client = self._client_for('dash_layout_user')
        response = client.post('/api/preferences/dashboard-layout', json={
            'order': ['engineer-today', 'engineer-summary', 'my-active-tasks'],
            'hidden': ['open-technical-tasks']
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['order'], ['engineer-today', 'engineer-summary', 'my-active-tasks'])
        self.assertEqual(payload['hidden'], ['open-technical-tasks'])

        # Survives a fresh request, i.e. it is stored on the account not the client.
        again = client.get('/api/preferences/dashboard-layout').get_json()
        self.assertEqual(again['order'], ['engineer-today', 'engineer-summary', 'my-active-tasks'])

    def test_rejects_unknown_section_ids(self):
        client = self._client_for('dash_reject_user')
        for bad in ({'order': ['not-a-section']}, {'hidden': ['<script>']}):
            response = client.post('/api/preferences/dashboard-layout', json=bad)
            self.assertEqual(response.status_code, 400, bad)
            self.assertFalse(response.get_json()['success'])

    def test_rejects_non_list_payloads(self):
        client = self._client_for('dash_type_user')
        response = client.post('/api/preferences/dashboard-layout', json={'order': 'engineer-summary'})
        self.assertEqual(response.status_code, 400)

    def test_deduplicates_while_preserving_order(self):
        client = self._client_for('dash_dupe_user')
        payload = client.post('/api/preferences/dashboard-layout', json={
            'order': ['engineer-today', 'engineer-summary', 'engineer-today']
        }).get_json()
        self.assertEqual(payload['order'], ['engineer-today', 'engineer-summary'])

    def test_unreadable_stored_layout_is_ignored_not_fatal(self):
        client = self._client_for('dash_corrupt_user')
        with self.app.app_context():
            user = app_module.User.query.filter_by(username='dash_corrupt_user').first()
            user.ui_dashboard_layout_json = 'not json at all'
            app_module.db.session.commit()

        response = client.get('/api/preferences/dashboard-layout')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['order'], [])


if __name__ == '__main__':
    unittest.main()
