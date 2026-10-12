"""Dashboard Style (plans.md): shadcn-style header, stat cards and the Visits completed chart.

Phase 1 covers the shared header and the engineer view; phase 2 the manager and hybrid view
(tiles as stat cards, the company chart). Every existing id and handler keeps working; the
charts read /get_dashboard_series.
"""

import os
import pathlib
import re
import tempfile
import unittest
from datetime import timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]

_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_dashboard_style_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402


def _read(*parts):
    return (ROOT.joinpath(*parts)).read_text(encoding='utf-8')


class DashboardStyleSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dashboard = _read('templates', 'dashboard.html')
        cls.js = _read('static', 'js', 'app-dashboard.js')
        cls.css = _read('static', 'css', 'app-dashboard.css')
        cls.app_source = _read('app.py')

    def test_header_has_a_visible_title_and_no_clock_badge(self):
        self.assertIn('<h1 class="dash-page-h1">Dashboard</h1>', self.dashboard)
        self.assertNotIn('visually-hidden">Dashboard</h1>', self.dashboard)
        self.assertNotIn('id="system-clock"', self.dashboard)
        self.assertNotIn('Welcome back', self.dashboard)
        # The subtitle date keeps the id updateClock() writes to.
        self.assertIn('<span id="current-date"></span>', self.dashboard)
        for handler in ('toggleDashboardCustomizeMode()', 'resetDashboardLayout()'):
            self.assertIn(handler, self.dashboard)

    def test_engineer_view_has_four_stat_cards_with_the_kept_ids(self):
        summary = self.dashboard.split('data-dashboard-section="engineer-summary"')[1].split('</div>\n\n')[0]
        self.assertEqual(summary.count('class="dash-stat"'), 4)
        self.assertIn('class="dash-stat" id="engineer-week"', summary)
        for element_id in ('count-my-today', 'count-my-overdue', 'count-my-pending-tsr',
                           'count-my-waiting', 'count-my-continuation', 'engineer-week',
                           'engineer-week-label', 'engineer-week-count'):
            self.assertIn(f'id="{element_id}"', summary, element_id)
        self.assertNotIn('dashboard-metric-strip', summary)

    def test_chart_section_is_registered_and_wired(self):
        self.assertIn('data-dashboard-section="engineer-activity"', self.dashboard)
        self.assertIn("'engineer-activity',", self.app_source)
        for range_days in (90, 30, 7):
            self.assertIn(f'onclick="setDashboardChartRange({range_days})"', self.dashboard)
        for function in ('function renderDashboardAreaChart(', 'function setDashboardChartRange(',
                         'function loadEngineerActivity(', 'function renderEngineerWeekBadge('):
            self.assertIn(function, self.js)
        self.assertIn('/get_dashboard_series?metric=my_completed&days=90', self.js)

    def test_saved_engineer_layouts_reset_once(self):
        # resetDashboardLayoutIfOutdated() reads the first versioned section.
        engineer = self.dashboard.split('{% if dashboard_has_engineer_profile %}')[1]
        first = re.search(r'data-dashboard-layout-version="(\d+)"', engineer)
        self.assertEqual(first.group(1), '3')

    def test_chart_motion_respects_reduced_motion(self):
        style = self.css.split('Dashboard Style (shadcn model')[1]
        self.assertIn('prefers-reduced-motion: reduce', style)
        self.assertNotIn('infinite', style)

    def test_existing_functions_survive(self):
        for function in ('updateEngineerSummaryCards', 'loadMyPendingTsrCount', 'renderEngineerWeek',
                         'loadMyDoneTasks', 'renderMyTasks', 'setWorkOrdersTab', 'openWorkOrderPanel',
                         'closeWorkOrderPanel', 'toggleDashboardCustomizeMode', 'resetDashboardLayout',
                         'toggleDashboardSection', 'setMetricValue', 'updateClock'):
            self.assertRegex(self.js, rf'function {function}\(', function)

    def test_assets_and_cache_bumped(self):
        css_version = int(re.search(r"app-dashboard\.css'\) \}\}\?v=(\d+)", self.dashboard).group(1))
        js_version = int(re.search(r"app-dashboard\.js'\) \}\}\?v=(\d+)", self.dashboard).group(1))
        self.assertGreaterEqual(css_version, 11)
        self.assertGreaterEqual(js_version, 10)
        self.assertIn('v291-dashboard-style', self.app_source)


class DashboardLogbookSourceTests(unittest.TestCase):
    """Signal and Character (plans.md): entry dates use the shared logbook style."""

    @classmethod
    def setUpClass(cls):
        cls.dashboard = _read('templates', 'dashboard.html')
        cls.js = _read('static', 'js', 'app-dashboard.js')
        cls.css = _read('static', 'css', 'app-dashboard.css')

    def test_logbook_style_replaces_courier(self):
        self.assertNotIn('Courier', self.css)
        self.assertRegex(self.css, r'\.logbook-ref \{ font-family: ui-monospace[^}]*tabular-nums')

    def test_entry_dates_use_it(self):
        self.assertGreaterEqual(self.js.count('logbook-ref'), 4)
        self.assertNotIn('font-monospace', self.js)
        self.assertIn("css/app-dashboard.css') }}?v=16", self.dashboard)
        self.assertIn("js/app-dashboard.js') }}?v=16", self.dashboard)


class DashboardStyleManagerSourceTests(unittest.TestCase):
    """Phase 2: manager and hybrid."""

    @classmethod
    def setUpClass(cls):
        cls.dashboard = _read('templates', 'dashboard.html')
        cls.js = _read('static', 'js', 'app-dashboard.js')
        cls.app_source = _read('app.py')
        cls.manager = cls.dashboard.split('{% if dashboard_effective_manager_view and not dashboard_effective_scheduler_only %}')[1].split('SCOPE BOUNDARY')[0]

    def test_tiles_are_stat_cards_that_keep_their_filters(self):
        tiles = self.manager.split('class="manager-kpis')[1].split('\n            </div>\n')[0]
        self.assertEqual(tiles.count('class="manager-kpi dash-stat'), 5)
        for kpi in ('severe_overdue', 'aged_tsr', 'waiting'):
            self.assertIn(f'data-manager-kpi="{kpi}" aria-pressed="false" onclick="openManagerKpi(\'{kpi}\')"', tiles)
        self.assertIn('onclick="openManagerKpi(\'pm\')"', tiles)
        self.assertIn('href="/approvals" class="manager-kpi dash-stat d-none" id="manager-kpi-approvals"', tiles)
        for key in ('approvals', 'overdue', 'pending_tsr', 'waiting'):
            self.assertIn(f'id="manager-trend-{key}"', tiles)
            self.assertIn(f'id="manager-trend-line-{key}" data-default=', tiles)
        self.assertNotIn('manager-spark-', self.dashboard)
        self.assertIn('id="manager-kpi-pm-meter"', tiles)

    def test_company_chart_section_is_registered_and_wired(self):
        self.assertIn('data-dashboard-section="manager-activity"', self.manager)
        self.assertIn("'manager-activity',", self.app_source)
        for element_id in ('manager-activity-chart', 'manager-activity-sub', 'manager-activity-readout'):
            self.assertIn(f'id="{element_id}"', self.manager)
        # Overdue by age is the smaller card beside the chart.
        row = self.manager.split('data-dashboard-section="manager-activity"')[1].split('data-dashboard-section=')[0]
        self.assertIn('id="manager-overdue-age"', row)
        self.assertIn('function loadManagerActivity(', self.js)
        self.assertIn('/get_dashboard_series?metric=company_completed&days=90', self.js)

    def test_hybrid_gets_the_company_chart_only(self):
        engineer = self.dashboard.split('{% if dashboard_has_engineer_profile %}')[1]
        before_chart = engineer.split('data-dashboard-section="engineer-activity"')[0]
        self.assertIn('{% if not dashboard_effective_hybrid_view %}', before_chart.rsplit('#}', 1)[1])
        # The Done this week badge still gets the engineer's own series.
        self.assertIn('engineerSeriesPoints', self.js.split('function renderEngineerWeekBadge(')[1].split('function ')[0])

    def test_saved_manager_layouts_reset_once(self):
        self.assertRegex(self.manager, r'data-dashboard-section="manager-executive"[^>]*data-dashboard-layout-version="4"')

    def test_manager_functions_survive(self):
        for function in ('openManagerKpi', 'renderManagerTrends', 'renderManagerKpiTrend', 'renderOverdueByAge',
                         'openOverdueAge', 'renderManagerWatchlist', 'loadManagerOverview',
                         'loadManagerApprovals', 'renderManagerUpdated', 'setManagerKpiValue',
                         'setDashboardChartRange', 'renderDashboardAreaChart'):
            self.assertRegex(self.js, rf'function {function}\(', function)

    def test_assets_and_cache_bumped(self):
        css_version = int(re.search(r"app-dashboard\.css'\) \}\}\?v=(\d+)", self.dashboard).group(1))
        js_version = int(re.search(r"app-dashboard\.js'\) \}\}\?v=(\d+)", self.dashboard).group(1))
        self.assertGreaterEqual(css_version, 13)
        self.assertGreaterEqual(js_version, 12)
        self.assertIn('v292-dashboard-style-manager', self.app_source)


class ManagerWorkloadChartSourceTests(unittest.TestCase):
    """Manager Chart plan: visits scheduled as a comparison line on the manager chart."""

    @classmethod
    def setUpClass(cls):
        cls.dashboard = _read('templates', 'dashboard.html')
        cls.js = _read('static', 'js', 'app-dashboard.js')
        cls.app_source = _read('app.py')

    def _function(self, name):
        return self.js.split(f'function {name}(')[1].split('\n    function ')[0]

    def test_manager_loader_fetches_both_series(self):
        loader = self._function('loadManagerActivity')
        self.assertIn('metric=company_completed&days=90', loader)
        self.assertIn('metric=company_scheduled&days=90', loader)
        self.assertIn('Promise.all', loader)

    def test_chart_draws_an_optional_compare_line(self):
        chart = self._function('renderDashboardAreaChart')
        self.assertIn('options.compare', chart)
        self.assertIn('dash-chart-line is-compare', chart)
        self.assertIn('scheduled · ${values[index]} completed', chart)
        # Only the manager chart passes a comparison; the engineer chart stays one line.
        self.assertIn("prefix === 'manager-activity'", self._function('setDashboardChartRange'))

    def test_card_has_the_title_and_key(self):
        card = self.dashboard.split('data-dashboard-section="manager-activity"')[1].split('id="manager-overdue-age"')[0]
        self.assertIn('Visits — scheduled vs completed', card)
        self.assertIn('class="dash-chart-key"', card)
        self.assertIn('dash-chart-swatch is-compare', card)
        engineer = self.dashboard.split('data-dashboard-section="engineer-activity"')[1].split('</section>')[0]
        self.assertNotIn('dash-chart-key', engineer)

    def test_kept_functions_survive(self):
        for function in ('loadManagerActivity', 'loadEngineerActivity', 'setDashboardChartRange',
                         'renderDashboardAreaChart', 'groupDashboardPointsByWeek', 'openManagerKpi',
                         'renderOverdueByAge', 'loadManagerOverview'):
            self.assertRegex(self.js, rf'function {function}\(', function)

    def test_assets_and_cache_bumped(self):
        css_version = int(re.search(r"app-dashboard\.css'\) \}\}\?v=(\d+)", self.dashboard).group(1))
        js_version = int(re.search(r"app-dashboard\.js'\) \}\}\?v=(\d+)", self.dashboard).group(1))
        self.assertGreaterEqual(css_version, 14)
        self.assertGreaterEqual(js_version, 13)
        self.assertIn('v293-manager-workload-chart', self.app_source)


class DashboardStyleSchedulerSourceTests(unittest.TestCase):
    """Phase 3: scheduler dispatch board and staff landing."""

    @classmethod
    def setUpClass(cls):
        cls.dashboard = _read('templates', 'dashboard.html')
        cls.js = _read('static', 'js', 'app-dashboard.js')
        cls.app_source = _read('app.py')
        cls.board = cls.dashboard.split('data-dashboard-section="scheduler-board"')[1].split('{% if dashboard_effective_manager_view')[0]
        cls.strip = cls.board.split('id="scheduler-metric-strip"')[1].split('<div class="scheduler-board-grid">')[0]

    def test_filter_counts_are_stat_cards_that_keep_their_filters(self):
        self.assertEqual(self.strip.count('class="scheduler-metric dash-stat'), 5)
        for name in ('all', 'overdue', 'unassigned', 'waiting', 'tsr'):
            self.assertRegex(self.strip, rf'data-scheduler-filter="{name}" aria-pressed="(true|false)" onclick="setSchedulerQueueFilter\(\'{name}\'\)"')
        self.assertIn('class="scheduler-metric-static dash-stat"', self.strip)
        self.assertNotIn('dashboard-metric-divider', self.strip)
        self.assertNotIn('dash-stat-badge', self.strip)

    def test_counts_are_coloured_only_above_zero(self):
        self.assertNotIn('dashboard-metric-alert', self.strip)
        self.assertNotIn('dashboard-metric-warn', self.strip)
        renderer = self.js.split('function renderSchedulerMetrics(')[1].split('\n    function ')[0]
        for count_id in ('scheduler-overdue-count', 'scheduler-unassigned-count',
                         'scheduler-waiting-count', 'scheduler-pending-tsr-count'):
            self.assertIn(f'data-metric-tone=', self.strip.split(f'id="{count_id}"')[1].split('>')[0])
            self.assertIn(f"setMetricValue('{count_id}'", renderer)

    def test_board_heading_and_regions_take_the_card_look(self):
        head = self.board.split('id="scheduler-risk"')[0]
        self.assertIn('<h2 class="dash-card-title">Dispatch Board</h2>', head)
        self.assertIn('loadSchedulerDispatchIntelligence(); loadSchedulerCoordinationTools();', head)
        # Open calendar is the page header's primary button only.
        self.assertNotIn('href="/timeline"', head)
        for region in ('queue', 'lanes', 'selected'):
            self.assertIn(f'class="scheduler-board-{region} card dash-panel overflow-hidden"', self.board)
            self.assertIn(f'class="dash-card-title" id="scheduler-{region}-heading"', self.board)
        self.assertNotIn('shadow-sm rounded-4', self.board)

    def test_staff_landing_has_the_header_and_a_card(self):
        self.assertIn('{% set dashboard_subtitle = "What\'s waiting on you" %}', self.dashboard)
        staff = self.dashboard.split('{% if dashboard_staff_landing %}')[1].split('{% endif %}')[0]
        self.assertIn('class="dashboard-today dash-panel mb-4" id="staff-waiting"', staff)
        self.assertIn('<h2 class="dash-card-title">Waiting on you</h2>', staff)
        self.assertIn('id="staff-waiting-list"', staff)

    def test_scheduler_functions_survive(self):
        for function in ('setSchedulerBoardView', 'renderSchedulerAvailabilityStrip', 'setSchedulerQueueFilter',
                         'renderSchedulerMetrics', 'dropOnSchedulerLane', 'confirmSchedulerLaneAssign',
                         'loadSchedulerDispatchIntelligence', 'loadSchedulerCoordinationTools',
                         'setMetricValue', 'loadStaffWaiting'):
            self.assertRegex(self.js, rf'function {function}\(', function)

    def test_assets_and_cache_bumped(self):
        css_version = int(re.search(r"app-dashboard\.css'\) \}\}\?v=(\d+)", self.dashboard).group(1))
        js_version = int(re.search(r"app-dashboard\.js'\) \}\}\?v=(\d+)", self.dashboard).group(1))
        self.assertGreaterEqual(css_version, 15)
        self.assertGreaterEqual(js_version, 14)
        self.assertIn('v294-dashboard-style-scheduler', self.app_source)


class DashboardSeriesEndpointTests(unittest.TestCase):
    ENGINEER_USER = 'dash_style_test_engineer'
    OTHER_USER = 'dash_style_test_other'
    STAFF_USER = 'dash_style_test_staff'
    # A real manager-dashboard account: is_regional_admin_user() is tied to this username.
    MANAGER_USER = app_module.REGIONAL_ADMIN_USERNAME

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            app_module.db.create_all()
            cls._cleanup()
            cls._seed()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            cls._cleanup()

    @classmethod
    def _cleanup(cls):
        db = app_module.db
        try:
            for shift in app_module.Shift.query.filter(app_module.Shift.title.like('Dash style test%')).all():
                app_module.ShiftEngineer.query.filter_by(shift_id=shift.id).delete()
                db.session.delete(shift)
            for shift in app_module.Shift.query.filter(app_module.Shift.title == 'Training').all():
                if any(link.engineer_id in cls._engineer_ids() for link in
                       app_module.ShiftEngineer.query.filter_by(shift_id=shift.id)):
                    app_module.ShiftEngineer.query.filter_by(shift_id=shift.id).delete()
                    db.session.delete(shift)
            for employee_id in ('DS-E1', 'DS-E2'):
                engineer = app_module.Engineer.query.filter_by(employee_id=employee_id).first()
                if engineer:
                    db.session.delete(engineer)
            if getattr(cls, 'created_manager', False):
                manager = app_module.User.query.filter_by(username=cls.MANAGER_USER).first()
                if manager:
                    db.session.delete(manager)
            for username in (cls.ENGINEER_USER, cls.OTHER_USER, cls.STAFF_USER):
                user = app_module.User.query.filter_by(username=username).first()
                if user:
                    db.session.delete(user)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

    @classmethod
    def _engineer_ids(cls):
        return {e.id for e in app_module.Engineer.query.filter(
            app_module.Engineer.employee_id.in_(['DS-E1', 'DS-E2']))}

    @classmethod
    def _seed(cls):
        db = app_module.db
        today = app_module.get_manila_today()
        cls.today = today
        users = {}
        for username, role in ((cls.ENGINEER_USER, 'engineer'), (cls.OTHER_USER, 'engineer'),
                               (cls.STAFF_USER, 'staff')):
            user = app_module.User(username=username, role=role, is_active=True,
                                   password=app_module.generate_password_hash('DashStyle123'))
            db.session.add(user)
            users[username] = user
        cls.created_manager = not app_module.User.query.filter_by(username=cls.MANAGER_USER).first()
        if cls.created_manager:
            db.session.add(app_module.User(username=cls.MANAGER_USER, role='regional_admin', is_active=True,
                                           password=app_module.generate_password_hash('DashStyle123')))
        db.session.commit()

        mine = app_module.Engineer(employee_id='DS-E1', name='Dash Style Engineer', initials='DS',
                                   branch='Manila', user_id=users[cls.ENGINEER_USER].id)
        other = app_module.Engineer(employee_id='DS-E2', name='Dash Style Other', initials='DO',
                                    branch='Manila', user_id=users[cls.OTHER_USER].id)
        db.session.add_all([mine, other])
        client = app_module.Client.query.filter_by(name='Dash Style Test Hospital').first()
        if not client:
            client = app_module.Client(name='Dash Style Test Hospital')
            db.session.add(client)
        db.session.commit()

        def make_shift(title, day_offset, status, engineer):
            day = today + timedelta(days=day_offset)
            start = app_module.build_shift_datetime_bounds(day, day)[0] + timedelta(hours=9)
            shift = app_module.Shift(title=title, start_time=start, end_time=start + timedelta(hours=2),
                                     engineer_id=engineer.id, client_id=client.id, status=status)
            db.session.add(shift)
            db.session.commit()
            db.session.add(app_module.ShiftEngineer(shift_id=shift.id, engineer_id=engineer.id))
            db.session.commit()

        make_shift('Dash style test done today', 0, 'Completed', mine)
        make_shift('Dash style test done today again', 0, 'Completed', mine)
        make_shift('Dash style test done 20 days ago', -20, 'Completed', mine)
        make_shift('Dash style test done 100 days ago', -100, 'Completed', mine)
        make_shift('Dash style test still open', -1, 'In Progress', mine)
        make_shift('Dash style test other engineer', -2, 'Completed', other)
        make_shift('Training', -3, 'Completed', mine)

    def _get(self, username, query):
        with self.app.app_context():
            user_id = app_module.User.query.filter_by(username=username).first().id
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client.get(f'/get_dashboard_series?{query}')

    def test_zero_filled_manila_days_oldest_first(self):
        payload = self._get(self.ENGINEER_USER, 'metric=my_completed&days=90').get_json()
        points = payload['points']
        self.assertEqual(len(points), 90)
        self.assertEqual(points[-1]['date'], self.today.isoformat())
        self.assertEqual(points[0]['date'], (self.today - timedelta(days=89)).isoformat())

    def test_counts_only_own_completed_service_visits(self):
        points = self._get(self.ENGINEER_USER, 'metric=my_completed&days=90').get_json()['points']
        by_date = {point['date']: point['value'] for point in points}
        self.assertEqual(by_date[self.today.isoformat()], 2)
        self.assertEqual(by_date[(self.today - timedelta(days=20)).isoformat()], 1)
        # Open visit, Training and the other engineer's visit are not counted.
        self.assertEqual(sum(by_date.values()), 3)

    def test_range_limits_the_window(self):
        points = self._get(self.ENGINEER_USER, 'metric=my_completed&days=7').get_json()['points']
        self.assertEqual(len(points), 7)
        self.assertEqual(sum(point['value'] for point in points), 2)

    def test_days_outside_the_allowed_set_fall_back_to_90(self):
        for days in ('5', '365', 'abc'):
            payload = self._get(self.ENGINEER_USER, f'metric=my_completed&days={days}').get_json()
            self.assertEqual(payload['days'], 90, days)

    def test_other_engineer_sees_only_their_own(self):
        points = self._get(self.OTHER_USER, 'metric=my_completed&days=7').get_json()['points']
        self.assertEqual(sum(point['value'] for point in points), 1)

    def test_empty_without_an_engineer_profile(self):
        points = self._get(self.STAFF_USER, 'metric=my_completed&days=30').get_json()['points']
        self.assertEqual(len(points), 30)
        self.assertEqual(sum(point['value'] for point in points), 0)

    def test_company_series_is_for_managers_only(self):
        self.assertEqual(self._get(self.ENGINEER_USER, 'metric=company_completed&days=7').status_code, 403)
        self.assertEqual(self._get(self.STAFF_USER, 'metric=company_completed&days=7').status_code, 403)

    def test_company_series_counts_every_engineer(self):
        response = self._get(self.MANAGER_USER, 'metric=company_completed&days=7')
        self.assertEqual(response.status_code, 200)
        points = response.get_json()['points']
        self.assertEqual(len(points), 7)
        by_date = {point['date']: point['value'] for point in points}
        # Shared test DB: other modules may add visits, so these are lower bounds.
        self.assertGreaterEqual(by_date[self.today.isoformat()], 2)
        self.assertGreaterEqual(by_date[(self.today - timedelta(days=2)).isoformat()], 1)

    def test_scheduled_series_is_for_managers_only(self):
        self.assertEqual(self._get(self.ENGINEER_USER, 'metric=company_scheduled&days=7').status_code, 403)
        self.assertEqual(self._get(self.STAFF_USER, 'metric=company_scheduled&days=7').status_code, 403)

    def test_scheduled_series_counts_open_visits_too(self):
        def by_date(metric):
            response = self._get(self.MANAGER_USER, f'metric={metric}&days=7')
            self.assertEqual(response.status_code, 200)
            points = response.get_json()['points']
            self.assertEqual(len(points), 7)
            return {point['date']: point['value'] for point in points}
        scheduled = by_date('company_scheduled')
        completed = by_date('company_completed')
        yesterday = (self.today - timedelta(days=1)).isoformat()
        # The seeded In Progress visit yesterday is scheduled but not completed.
        self.assertGreaterEqual(scheduled[yesterday] - completed[yesterday], 1)
        self.assertGreaterEqual(scheduled[self.today.isoformat()], 2)
        for day, value in completed.items():
            self.assertLessEqual(value, scheduled[day], day)

    def test_unknown_metric_is_rejected(self):
        self.assertEqual(self._get(self.ENGINEER_USER, 'metric=everything').status_code, 400)


if __name__ == '__main__':
    unittest.main()
