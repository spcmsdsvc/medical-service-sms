"""Hybrid dashboard: the ratified decision, plus phase 4's shortcut consolidation.

Phase 4 found the hybrid admin+engineer sections could not render -- they were gated on
`admin_view and not manager_view`, but is_manager_dashboard_user() is true for any
admin-authorized non-scheduler, so every admin lands in the manager view. It retired them
and left the hybrid experience itself undecided.

It is decided now: an admin who also holds an engineer profile gets the manager view with
their own work stacked beneath it, marked off by a scope divider. `rodito` is exempt as the
manager-primary account and gets the manager view alone. The developer preview switcher is
gone, so a role is verified by signing in as an account that holds it.
"""

import os
import pathlib
import re
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
    """Pins the decision, not the predicate that led to it.

    The earlier version of this test asserted a substring of is_manager_dashboard_user(),
    which froze that predicate's internals in order to protect a conclusion about the
    template. The conclusion is what matters, so assert it directly: no section may be
    gated on the combination that cannot be satisfied. The predicate is now free to change
    -- and did, when the developer preview clause was removed from it.
    """

    def test_no_section_is_gated_on_the_unsatisfiable_combination(self):
        dashboard = (ROOT / 'templates' / 'dashboard.html').read_text(encoding='utf-8')
        for gate in re.findall(r'\{%-?\s*if\s+(.+?)-?%\}', dashboard, re.DOTALL):
            if 'dashboard_effective_admin_view' not in gate:
                continue
            self.assertNotIn(
                'not dashboard_effective_manager_view', gate,
                'admin_view and not manager_view cannot be satisfied by any account: '
                'is_manager_dashboard_user() is true for every admin-authorized '
                'non-scheduler. Gate on dashboard_effective_hybrid_view instead, which is '
                'satisfiable and means exactly admin + engineer profile.'
            )

    def test_the_hybrid_flag_is_satisfiable_and_actually_used(self):
        """hybrid_view existed unused for the whole of phase 4. It has a job now."""
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        self.assertIn("'hybrid_view': engineer_sections and admin_authorized,", source)

        dashboard = (ROOT / 'templates' / 'dashboard.html').read_text(encoding='utf-8')
        gates = re.findall(r'\{%-?\s*if\s+(.+?)-?%\}', dashboard, re.DOTALL)
        self.assertTrue(
            any('dashboard_effective_hybrid_view' in gate for gate in gates),
            'the hybrid flag must gate something, or it is dead weight again'
        )


class HybridDashboardSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.dashboard = (ROOT / 'templates' / 'dashboard.html').read_text(encoding='utf-8')
        cls.css = (ROOT / 'static' / 'css' / 'app-dashboard.css').read_text(encoding='utf-8')
        cls.js = (ROOT / 'static' / 'js' / 'app-dashboard.js').read_text(encoding='utf-8')

    def test_unreachable_sections_and_their_endpoint_are_gone(self):
        for retired in ('needs-attention', 'team-intelligence', 'recent-activity'):
            self.assertNotIn(f'data-dashboard-section="{retired}"', self.dashboard)
            # The ids stay registered so a saved layout naming them still saves.
            self.assertIn(f"'{retired}',", self.app_source)

        for endpoint in ('/get_hybrid_overview', '/get_hybrid_dashboard_team_summary',
                         '/get_hybrid_dashboard_smart_monitoring'):
            self.assertNotIn(f"@app.route('{endpoint}')", self.app_source)
            self.assertNotIn(endpoint, self.js)

    def test_the_dead_activity_feed_chain_went_with_its_section(self):
        """recent-activity was the only caller of all of this.

        activity.html has its own loader against /get_activity_logs and never used any of
        these, so leaving them would be ~180 lines of unreachable code.
        """
        for dead in ('function fetchActivityLog', 'function renderMobileActivityList',
                     'function getActivityMeta', 'function formatActivityText',
                     'lastActivitySignature', "getElementById('activity-log-body')"):
            self.assertNotIn(dead, self.js)

        # /activity_page keeps its own, separate implementation.
        activity = (ROOT / 'templates' / 'activity.html').read_text(encoding='utf-8')
        self.assertIn('/get_activity_logs', activity)

    def test_the_developer_preview_switcher_is_gone(self):
        for dead in ('DEVELOPER_DASHBOARD_VIEW_OPTIONS', 'DEVELOPER_DASHBOARD_VIEW_SESSION_KEY',
                     'def get_developer_dashboard_view', 'def developer_dashboard_view_is',
                     'def is_developer_user', "@app.route('/set_developer_dashboard_view'",
                     "'/set_developer_dashboard_view',"):
            self.assertNotIn(dead, self.app_source)

        # The username constant stays -- protected passwords and get_display_role need it.
        self.assertIn("DEVELOPER_SUPERADMIN_USERNAME = 'jonamar'", self.app_source)
        # And the section id stays accepted, like every other retired section.
        self.assertIn("'developer-view-switcher',", self.app_source)

        for dead in ('developer-dashboard-switcher', 'developer-view-btn',
                     'dashboard_developer_mode', 'setDeveloperDashboardView'):
            self.assertNotIn(dead, self.dashboard)
            self.assertNotIn(dead, self.js)
            self.assertNotIn(dead, self.css)

    def test_scheduler_tools_no_longer_accept_a_preview_flag(self):
        """Removing the switcher means these are scheduler-only, with no preview bypass."""
        coordination = self.app_source.split(
            'def can_use_scheduler_coordination_tools')[1].split('\ndef ')[0]
        self.assertNotIn('developer_dashboard_view_is', coordination)
        self.assertIn('is_scheduler_user()', coordination)

    def test_the_scope_divider_is_gated_on_the_hybrid_flag_alone(self):
        """It must not inherit the engineer-profile gate: a pure engineer gets no divider."""
        before = self.dashboard.split('dashboard-scope-divider')[0]
        gate = before.split('{% if ')[-1]
        self.assertIn('dashboard_effective_hybrid_view', gate)
        self.assertNotIn('dashboard_has_engineer_profile', gate)

    def test_the_colliding_waiting_metrics_are_both_scoped_for_hybrids(self):
        """Two strips carried a bare "waiting" meaning different things on one page."""
        self.assertIn('Waiting P.O / parts{% if dashboard_effective_hybrid_view %}, '
                      'company-wide{% endif %}', self.dashboard)
        self.assertIn('{% if dashboard_effective_hybrid_view %}waiting, yours'
                      '{% else %}waiting{% endif %}', self.dashboard)

    def test_personal_sections_are_subordinated_by_class_not_by_hiding(self):
        # Each personal section carries the marker class, conditionally on the hybrid flag.
        # Asserted per section rather than by counting occurrences, so a mention in a
        # comment cannot satisfy it and adding a comment cannot break it.
        for section in ('engineer-summary', 'engineer-today', 'my-active-tasks'):
            opening_tag = self.dashboard.split(
                f'data-dashboard-section="{section}"')[0].rsplit('<div', 1)[1]
            self.assertIn('dashboard-scope-personal', opening_tag, section)
            self.assertIn('dashboard_effective_hybrid_view', opening_tag, section)
        self.assertIn('.dashboard-scope-personal', self.css)
        # engineer-today must not be collapsed away: it is real assigned work.
        today = self.dashboard.split('data-dashboard-section="engineer-today"')[1][:600]
        self.assertNotIn('d-none', today)
        self.assertNotIn('collapse', today)

    def test_the_scope_divider_has_a_dark_mode_rule(self):
        """#64748b on the dark panel measures 3.4:1, so it needs an explicit override."""
        dark = (ROOT / 'static' / 'css' / 'app-dark-pages.css').read_text(encoding='utf-8')
        self.assertIn('.dashboard-scope-divider-label', dark)

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
        assert_cache_version_at_least(self, 51, self.app_source)

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
                      'engineer-workflow', 'recent-activity', 'developer-view-switcher',
                      'quick-admin'],
            'hidden': []
        })
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

    def test_the_preview_switcher_route_is_gone(self):
        client = self._admin_client()
        response = client.post('/set_developer_dashboard_view', json={'view': 'manager'})
        self.assertEqual(response.status_code, 404)

    def test_capabilities_no_longer_expose_a_developer_view(self):
        with self.app.app_context():
            user = app_module.User.query.filter_by(username=self.admin_username).first()
            caps = app_module.get_dashboard_capabilities(user)
        self.assertNotIn('developer_view', caps)
        self.assertNotIn('developer_view_options', caps)


class ManagerPrimaryExemptionTests(unittest.TestCase):
    """rodito is the manager, so he gets the manager dashboard and nothing stacked on it.

    Every other admin+engineer account keeps the hybrid stack. The exemption is presentation
    only -- see test_the_exemption_does_not_touch_the_real_capability below, which is the
    property that keeps this from quietly changing his permissions.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.app.config['TESTING'] = True
        cls.username = 'rodito'
        cls.created_engineer_ids = []
        cls.created_user_ids = []

        with cls.app.app_context():
            app_module.db.create_all()
            user = app_module.User.query.filter_by(username=cls.username).first()
            if not user:
                user = app_module.User(
                    username=cls.username, role='superadmin', is_active=True,
                    password=app_module.generate_password_hash('ManagerPrimary123'))
                app_module.db.session.add(user)
                app_module.db.session.commit()
                cls.created_user_ids.append(user.id)

            # He must genuinely hold an engineer profile, or the assertions below would pass
            # for the wrong reason -- an account with no profile gets no engineer sections
            # regardless of the exemption.
            if not getattr(user, 'engineer_profile', None):
                engineer = app_module.Engineer(
                    name='Rodito Manager Primary', employee_id='MP-0001',
                    initials='MP', branch='Cebu', user_id=user.id)
                app_module.db.session.add(engineer)
                app_module.db.session.commit()
                cls.created_engineer_ids.append(engineer.id)
            cls.user_id = user.id

    @classmethod
    def tearDownClass(cls):
        # Seeding APPROVAL_CENTER_MANAGER_USERNAME makes ensure_default_approval_routes()
        # write an ApprovalRouting row per user, whose NOT NULL requester FK then breaks
        # sibling modules sharing this database. Deleting the rows alone is not enough --
        # the app rebuilds them on the next request while the username exists.
        with cls.app.app_context():
            app_module.ApprovalRouting.query.delete()
            for engineer_id in cls.created_engineer_ids:
                engineer = app_module.db.session.get(app_module.Engineer, engineer_id)
                if engineer:
                    app_module.db.session.delete(engineer)
            for user_id in cls.created_user_ids:
                user = app_module.db.session.get(app_module.User, user_id)
                if user:
                    app_module.db.session.delete(user)
            app_module.db.session.commit()

    def _capabilities(self):
        with self.app.app_context():
            user = app_module.db.session.get(app_module.User, self.user_id)
            return app_module.get_dashboard_capabilities(user)

    def test_he_really_does_hold_an_engineer_profile(self):
        """Positive control. Without this the exemption assertions prove nothing."""
        with self.app.app_context():
            user = app_module.db.session.get(app_module.User, self.user_id)
            self.assertIsNotNone(getattr(user, 'engineer_profile', None))

    def test_he_is_manager_primary_and_gets_no_engineer_sections(self):
        with self.app.app_context():
            user = app_module.db.session.get(app_module.User, self.user_id)
            self.assertTrue(app_module.is_manager_primary_user(user))

        caps = self._capabilities()
        self.assertTrue(caps['manager_view'])
        self.assertFalse(caps['has_engineer_profile'])
        self.assertFalse(caps['hybrid_view'], 'no scope divider for a manager-primary account')

    def test_the_exemption_does_not_touch_the_real_capability(self):
        """The safety property: presentation changes, authority does not.

        has_engineer_profile() is what engineer tools, permissions and schedule assignment
        consult. If the exemption ever reaches it, rodito silently loses engineer access.
        """
        with self.app.app_context():
            user = app_module.db.session.get(app_module.User, self.user_id)
            self.assertTrue(app_module.has_engineer_profile(user))

    def test_his_rendered_dashboard_carries_no_personal_sections(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.user_id)
            session['_fresh'] = True

        body = client.get('/').get_data(as_text=True)
        for section in ('engineer-summary', 'engineer-today', 'my-active-tasks'):
            self.assertNotIn(f'data-dashboard-section="{section}"', body, section)
        self.assertNotIn('dashboard-scope-divider', body)
        # The manager view itself must still be there.
        self.assertIn('data-dashboard-section="manager-executive"', body)

    def test_another_admin_with_a_profile_still_gets_the_hybrid_stack(self):
        """The exemption must be the named account only, not every manager-ish admin."""
        with self.app.app_context():
            self.assertEqual(app_module.MANAGER_PRIMARY_USERNAMES, {'rodito'})
            self.assertIn('robert', app_module.MANAGER_USERNAMES)
            self.assertNotIn('robert', app_module.MANAGER_PRIMARY_USERNAMES)


if __name__ == '__main__':
    unittest.main()
