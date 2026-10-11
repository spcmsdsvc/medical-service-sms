"""Dashboard Style (plans.md): shadcn-style header, stat cards and the Visits completed chart.

Phase 1 covers the shared header and the engineer view. Every existing id and handler keeps
working; the chart reads /get_dashboard_series.
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


class DashboardSeriesEndpointTests(unittest.TestCase):
    ENGINEER_USER = 'dash_style_test_engineer'
    OTHER_USER = 'dash_style_test_other'
    STAFF_USER = 'dash_style_test_staff'

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

    def test_unknown_metric_is_rejected(self):
        self.assertEqual(self._get(self.ENGINEER_USER, 'metric=everything').status_code, 400)


if __name__ == '__main__':
    unittest.main()
