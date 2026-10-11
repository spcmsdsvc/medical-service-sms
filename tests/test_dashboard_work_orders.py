"""Dashboard remodel phase B: engineer work orders (plans.md, MaintainX model).

The engineer view's "Needs you today" and "My Active Tasks" became one work-order list
with status tabs, a detail panel and a "Done this week" tab fed by /get_my_done_tasks.
"""

import os
import pathlib
import re
import tempfile
import unittest
from datetime import timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Optional override so the source tests can be pointed at an older checkout to prove
# they fail without the change (positive control).
SOURCE_ROOT = pathlib.Path(os.environ.get('DASHBOARD_WORK_ORDERS_SOURCE_ROOT') or ROOT)

_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_dashboard_work_orders_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))


def _read(*parts):
    return (SOURCE_ROOT.joinpath(*parts)).read_text(encoding='utf-8')


def _block(source, start_marker, end_marker):
    return source.split(start_marker, 1)[1].split(end_marker, 1)[0]


class WorkOrderSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dashboard = _read('templates', 'dashboard.html')
        cls.js = _read('static', 'js', 'app-dashboard.js')
        cls.css = _read('static', 'css', 'app-dashboard.css')
        cls.app_source = _read('app.py')

    def test_one_work_order_section_replaces_today_and_active_tasks(self):
        self.assertIn('data-dashboard-section="engineer-work-orders"', self.dashboard)
        for retired in ('engineer-today', 'my-active-tasks'):
            self.assertNotIn(f'data-dashboard-section="{retired}"', self.dashboard)
            # Still accepted so a saved layout naming them keeps saving.
            self.assertIn(f"'{retired}',", self.app_source)
        self.assertIn("'engineer-work-orders',", self.app_source)

    def test_tabs_and_panel_markup(self):
        section = _block(self.dashboard, 'data-dashboard-section="engineer-work-orders"', '</section>')
        for tab in ('today', 'overdue', 'upcoming', 'waiting', 'done'):
            self.assertIn(f"onclick=\"setWorkOrdersTab('{tab}')\"", section)
            self.assertIn(f'id="work-orders-count-{tab}"', section)
        self.assertIn('role="tablist"', section)
        self.assertIn('id="work-order-panel"', section)
        self.assertIn('onclick="closeWorkOrderPanel()"', section)
        self.assertIn('data-dashboard-layout-version="2"', section)

    def test_list_containers_and_header_ids_are_kept(self):
        section = _block(self.dashboard, 'data-dashboard-section="engineer-work-orders"', '</section>')
        for element in ('id="my-tasks-body"', 'id="no-my-tasks"', 'id="my-tasks-mobile-list"'):
            self.assertIn(element, section)
        strip = _block(self.dashboard, 'data-dashboard-section="engineer-summary"', 'dashboard-metric-link')
        for count_id in ('count-my-today', 'count-my-overdue', 'count-my-pending-tsr',
                         'count-my-waiting', 'count-my-continuation'):
            self.assertIn(f'id="{count_id}"', strip)

    def test_existing_functions_survive(self):
        for name in ('renderMyTasks', 'renderEngineerTodayPanel', 'updateEngineerSummaryCards',
                     'filterAndRender', 'toggleSort', 'populateEngineerFilter',
                     'buildDashboardTaskMobileCard', 'loadMyPendingTsrCount'):
            self.assertRegex(self.js, rf'(async )?function {name}\(', name)

    def test_tabs_render_and_done_loads_lazily(self):
        for name in ('setWorkOrdersTab', 'loadMyDoneTasks', 'openWorkOrderPanel',
                     'closeWorkOrderPanel', 'workOrderBuckets'):
            self.assertIn(f'function {name}(', self.js, name)
        render = _block(self.js, 'function renderMyTasks', '\n    function ')
        self.assertIn('workOrdersTab', render)
        self.assertIn('loadMyDoneTasks()', render)
        # Done this week is fetched only from its own loader, never on page load.
        self.assertEqual(self.js.count("'/get_my_done_tasks'"), 1)
        self.assertIn("'/get_my_done_tasks'", _block(self.js, 'async function loadMyDoneTasks', '\n    }'))

    def test_done_work_orders_are_never_late(self):
        late = _block(self.js, 'function dashboardDaysLate', '\n    }\n')
        self.assertIn("task.status === 'Completed') return 0", late)

    def test_panel_closes_with_escape_and_returns_focus(self):
        self.assertIn("event.key === 'Escape'", self.js)
        close = _block(self.js, 'function closeWorkOrderPanel', '\n    }\n')
        self.assertIn('workOrdersReturnFocus', close)
        self.assertIn('.focus()', close)
        panel = _block(self.js, 'function openWorkOrderPanel', '\n    function ')
        self.assertIn('Open on timeline', panel)
        self.assertIn('dashboardTimelineHref(task)', panel)

    def test_panel_is_a_side_column_on_desktop_and_a_sheet_on_phones(self):
        self.assertIn('.work-orders-layout.has-panel', self.css)
        self.assertIn('@media (max-width: 991.98px)', self.css)
        self.assertIn('position: fixed;', _block(self.css, '@media (max-width: 991.98px)', '}\n'))

    def test_assets_and_service_worker_bumped(self):
        # At least the phase B versions; later phases bump them again.
        css_version = int(re.search(r"app-dashboard\.css'\) \}\}\?v=(\d+)", self.dashboard).group(1))
        js_version = int(re.search(r"app-dashboard\.js'\) \}\}\?v=(\d+)", self.dashboard).group(1))
        self.assertGreaterEqual(css_version, 8)
        self.assertGreaterEqual(js_version, 7)
        self.assertIn('v288-work-orders', self.app_source)


import app as app_module  # noqa: E402


class MyDoneTasksEndpointTests(unittest.TestCase):
    ENGINEER_USER = 'work_orders_test_engineer'
    OTHER_USER = 'work_orders_test_other'
    STAFF_USER = 'work_orders_test_staff'

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
            for shift in app_module.Shift.query.filter(app_module.Shift.title.like('Work orders test %')).all():
                app_module.ShiftEngineer.query.filter_by(shift_id=shift.id).delete()
                db.session.delete(shift)
            for employee_id in ('WO-E1', 'WO-E2'):
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
    def _seed(cls):
        db = app_module.db
        today = app_module.get_manila_today()
        users = {}
        for username, role in ((cls.ENGINEER_USER, 'engineer'), (cls.OTHER_USER, 'engineer'),
                               (cls.STAFF_USER, 'staff')):
            user = app_module.User(username=username, role=role, is_active=True,
                                   password=app_module.generate_password_hash('WorkOrders123'))
            db.session.add(user)
            users[username] = user
        db.session.commit()

        mine = app_module.Engineer(employee_id='WO-E1', name='Work Orders Engineer', initials='WE',
                                   branch='Manila', user_id=users[cls.ENGINEER_USER].id)
        other = app_module.Engineer(employee_id='WO-E2', name='Work Orders Other', initials='WO',
                                    branch='Manila', user_id=users[cls.OTHER_USER].id)
        db.session.add_all([mine, other])
        client = app_module.Client.query.filter_by(name='Work Orders Test Hospital').first()
        if not client:
            client = app_module.Client(name='Work Orders Test Hospital')
            db.session.add(client)
        db.session.commit()

        def make_shift(title, day_offset, status, engineer):
            start = app_module.build_shift_datetime_bounds(
                today + timedelta(days=day_offset), today + timedelta(days=day_offset))[0] + timedelta(hours=9)
            shift = app_module.Shift(title=title, start_time=start, end_time=start + timedelta(hours=2),
                                     engineer_id=engineer.id, client_id=client.id, status=status)
            db.session.add(shift)
            db.session.commit()
            db.session.add(app_module.ShiftEngineer(shift_id=shift.id, engineer_id=engineer.id))
            db.session.commit()

        make_shift('Work orders test done today', 0, 'Completed', mine)
        make_shift('Work orders test done six days ago', -6, 'Completed', mine)
        make_shift('Work orders test done eight days ago', -8, 'Completed', mine)
        make_shift('Work orders test still open', -1, 'In Progress', mine)
        make_shift('Work orders test other engineer', -2, 'Completed', other)

    def _client_for(self, username):
        with self.app.app_context():
            user_id = app_module.User.query.filter_by(username=username).first().id
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def _titles(self, username):
        rows = self._client_for(username).get('/get_my_done_tasks').get_json()
        return [row['task'] for row in rows if row['task'].startswith('Work orders test')], rows

    def test_only_own_completed_visits_from_the_last_7_days(self):
        titles, _ = self._titles(self.ENGINEER_USER)
        self.assertEqual(titles, ['Work orders test done today', 'Work orders test done six days ago'])

    def test_never_another_engineers_visits(self):
        titles, _ = self._titles(self.OTHER_USER)
        self.assertEqual(titles, ['Work orders test other engineer'])

    def test_rows_have_the_open_task_shape_plus_tsr_state(self):
        _, rows = self._titles(self.ENGINEER_USER)
        row = next(r for r in rows if r['task'] == 'Work orders test done today')
        for key in ('id', 'task_date', 'time_start', 'time_end', 'client', 'product_name', 'serial',
                    'engineer_ids', 'engineer_names', 'status', 'has_tsr'):
            self.assertIn(key, row)
        self.assertEqual(row['status'], 'Completed')
        self.assertFalse(row['has_tsr'])
        self.assertEqual(row['time_start'], '09:00 AM')

    def test_empty_without_an_engineer_profile(self):
        self.assertEqual(self._client_for(self.STAFF_USER).get('/get_my_done_tasks').get_json(), [])

    def test_open_tasks_keep_their_keys(self):
        rows = self._client_for(self.ENGINEER_USER).get('/get_open_tasks').get_json()
        row = next(r for r in rows if r['task'] == 'Work orders test still open')
        for key in ('id', 'task_date', 'created_at', 'engineer', 'engineer_ids', 'engineer_names',
                    'client', 'client_id', 'product', 'product_name', 'product_id', 'serial', 'task', 'status'):
            self.assertIn(key, row)
        self.assertNotIn('has_tsr', row)


if __name__ == '__main__':
    unittest.main()
