"""Dashboard Trends -- "alive, not overloaded".

Overdue, pending TSR, waiting and approvals are states as of now and cannot be rebuilt for
past weeks, so the dashboard records them once per Manila day (DashboardDailyCount) and
the KPI tiles draw a weekly sparkline and a change vs last week from those rows. One chart
(overdue by age) sits under the tiles; engineers get a done-this-week strip.
"""

import os
import pathlib
import tempfile
import unittest
from datetime import timedelta

os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', os.path.join(tempfile.gettempdir(), 'medical_service_test.db'))

import app as app_module  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_SCOPE = 'test:trends'


class DashboardTrendHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        with cls.app.app_context():
            app_module.db.create_all()

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        app_module.DashboardDailyCount.query.filter_by(scope=TEST_SCOPE).delete()
        app_module.db.session.commit()
        self.today = app_module.get_manila_today()

    def tearDown(self):
        app_module.DashboardDailyCount.query.filter_by(scope=TEST_SCOPE).delete()
        app_module.db.session.commit()
        self.ctx.pop()

    def _seed(self, days_ago, value, metric='overdue'):
        app_module.db.session.add(app_module.DashboardDailyCount(
            day=self.today - timedelta(days=days_ago), scope=TEST_SCOPE, metric=metric, value=value))
        app_module.db.session.commit()

    def test_record_is_once_per_day(self):
        app_module.record_dashboard_daily_counts(TEST_SCOPE, {'overdue': 5}, self.today)
        app_module.record_dashboard_daily_counts(TEST_SCOPE, {'overdue': 9}, self.today)
        rows = app_module.DashboardDailyCount.query.filter_by(scope=TEST_SCOPE, day=self.today).all()
        self.assertEqual([row.value for row in rows], [5])

    def test_no_history_gives_no_delta(self):
        trend = app_module.dashboard_trend(TEST_SCOPE, 'overdue', 12, self.today)
        self.assertEqual(trend['points'], [12])
        self.assertIsNone(trend['delta'])
        self.assertEqual(trend['delta_from'], (self.today + timedelta(days=7)).isoformat())

    def test_delta_against_a_week_ago_and_weekly_points(self):
        # One row per weekly window, plus a second, older row in the newest window.
        for days_ago, value in ((28, 6), (21, 7), (14, 8), (9, 99), (7, 8)):
            self._seed(days_ago, value)
        trend = app_module.dashboard_trend(TEST_SCOPE, 'overdue', 12, self.today)
        self.assertEqual(trend['delta'], 4)
        # The 7-day window [today-7, today) holds only the 7-days-ago row; 9 days ago
        # belongs to the window before it, where it is the latest row.
        self.assertEqual(trend['points'], [6, 7, 99, 8, 12])
        self.assertEqual(trend['delta_from'], (self.today - timedelta(days=21)).isoformat())

    def test_delta_falls_back_to_six_or_eight_days(self):
        self._seed(8, 10)
        self.assertEqual(app_module.dashboard_trend(TEST_SCOPE, 'overdue', 7, self.today)['delta'], -3)

    def test_todays_row_is_not_a_point(self):
        self._seed(0, 50)
        self.assertEqual(app_module.dashboard_trend(TEST_SCOPE, 'overdue', 3, self.today)['points'], [3])


class DashboardTrendEndpointTests(unittest.TestCase):
    # Superadmin needs a SUPERADMIN_USERNAMES name: the owner's account, a superadmin who is
    # also an engineer and not an approver -- the view this plan was written for.
    username = 'jonamar'

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            app_module.db.create_all()
            user = app_module.User.query.filter_by(username=cls.username).first()
            cls.created_user = user is None
            if not user:
                user = app_module.User(username=cls.username, role='superadmin', is_active=True,
                                       password=app_module.generate_password_hash('TrendTest123'))
                app_module.db.session.add(user)
            user.role = 'superadmin'
            user.is_active = True
            if hasattr(user, 'can_approve_requests'):
                user.can_approve_requests = False
            app_module.db.session.commit()
            cls.user_id = user.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            try:
                app_module.DashboardDailyCount.query.filter(
                    app_module.DashboardDailyCount.scope.in_(['all', f'user:{cls.user_id}'])).delete(
                    synchronize_session=False)
                user = app_module.User.query.filter_by(username=cls.username).first()
                if user and cls.created_user:
                    app_module.db.session.delete(user)
                app_module.db.session.commit()
            except Exception:
                app_module.db.session.rollback()

    def _client(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.user_id)
            session['_fresh'] = True
        return client

    def test_overview_records_company_counts_and_sends_trends(self):
        payload = self._client().get('/get_manager_overview').get_json()
        self.assertEqual(set(payload['trends']), {'overdue', 'pending_tsr', 'waiting'})
        self.assertEqual(payload['trends']['overdue']['points'][-1], payload['counts']['overdue_schedules'])
        with self.app.app_context():
            today = app_module.get_manila_today()
            metrics = {row.metric for row in app_module.DashboardDailyCount.query.filter_by(day=today, scope='all')}
        self.assertEqual(metrics, {'overdue', 'pending_tsr', 'waiting'})

    def test_branch_filtered_overview_gets_no_company_trend(self):
        payload = self._client().get('/get_manager_overview?branch=Cebu').get_json()
        self.assertEqual(payload['trends'], {})

    def test_overdue_by_age_adds_up(self):
        payload = self._client().get('/get_manager_overview').get_json()
        buckets = payload['overdue_by_age']
        self.assertEqual([bucket['key'] for bucket in buckets], ['1_6', '7_14', '15_30', '31_plus'])
        self.assertEqual(sum(bucket['count'] for bucket in buckets), payload['counts']['overdue_schedules'])
        for bucket in buckets:
            self.assertLessEqual(len(bucket['rows']), 20)

    def test_non_approver_writes_no_approvals_row(self):
        payload = self._client().get('/get_manager_approvals').get_json()
        self.assertFalse(payload['is_approver'])
        self.assertNotIn('trends', payload)
        with self.app.app_context():
            self.assertEqual(app_module.DashboardDailyCount.query.filter_by(scope=f'user:{self.user_id}').count(), 0)


class DashboardTrendSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.dashboard = (ROOT / 'templates' / 'dashboard.html').read_text(encoding='utf-8')
        cls.css = (ROOT / 'static' / 'css' / 'app-dashboard.css').read_text(encoding='utf-8')
        cls.js = (ROOT / 'static' / 'js' / 'app-dashboard.js').read_text(encoding='utf-8')

    def test_tiles_carry_trend_slots_and_keep_their_ids(self):
        for key in ('approvals', 'overdue', 'pending_tsr', 'waiting'):
            self.assertEqual(self.dashboard.count(f'id="manager-trend-{key}"'), 1, key)
            self.assertEqual(self.dashboard.count(f'id="manager-spark-{key}"'), 1, key)
        self.assertIn('id="manager-kpi-pm-meter"', self.dashboard)
        for kept in ('manager-approvals-total', 'manager-overdue-count', 'manager-pending-tsr-count',
                     'manager-waiting-count', 'manager-kpi-pm'):
            self.assertEqual(self.dashboard.count(f'id="{kept}"'), 1, kept)

    def test_one_chart_under_the_tiles(self):
        tiles = self.dashboard.index('class="manager-kpis')
        chart = self.dashboard.index('id="manager-overdue-age"')
        self.assertLess(tiles, chart)
        self.assertLess(chart, self.dashboard.index('id="manager-approvals"'))
        self.assertIn('function openOverdueAge(', self.js)
        self.assertIn("openManagerKpi(`age:${key}`)", self.js)

    def test_engineer_week_strip(self):
        # Dashboard Style turned the week bars into the Done this week stat card.
        self.assertIn('id="engineer-week-count"', self.dashboard)
        self.assertIn('function renderEngineerWeek(', self.js)
        self.assertIn('renderEngineerWeek();', self.js.split('async function loadMyDoneTasks(')[1].split('\n    function ')[0])

    def test_motion_respects_reduced_motion(self):
        self.assertIn('prefers-reduced-motion: reduce', self.css)
        self.assertIn("matchMedia('(prefers-reduced-motion: reduce)')", self.js)
        # The refresh pulse runs three times, never forever.
        self.assertNotIn('infinite', self.css.split('DASHBOARD TRENDS')[1])

    def test_existing_functions_survive(self):
        for name in ('openManagerKpi', 'loadManagerOverview', 'loadManagerApprovals', 'renderManagerApprovals',
                     'renderManagerWatchlist', 'renderManagerPmSummary', 'setManagerKpiValue',
                     'loadMyDoneTasks', 'renderMyTasks', 'setWorkOrdersTab', 'updateEngineerSummaryCards'):
            self.assertRegex(self.js, rf'function {name}\(', name)

    def test_snapshot_model_exists(self):
        self.assertIn('class DashboardDailyCount(db.Model):', self.app_source)
        self.assertIn("name='uq_dashboard_daily_count'", self.app_source)


if __name__ == '__main__':
    unittest.main()
