"""Dashboard remodel phase A -- the scheduler dispatch board (ServiceTitan model).

The three stacked scheduler sections became one board: priority queue, engineer lanes,
selected schedule. Lanes are fed by a new additive `visits` list on each availability
row of /get_scheduler_coordination_tools; a queue row dropped on a lane proposes an
assignment that keeps the engineers already on the schedule, because
/scheduler_quick_assign_shift replaces the whole list.
"""

import os
import pathlib
import tempfile
import unittest
from datetime import timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Pin an isolated database BEFORE importing app.py so the suite can never open the real
# scheduler.db.
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_dispatch_board_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402


def _block(text, start_marker, end_marker):
    return text.split(start_marker, 1)[1].split(end_marker, 1)[0]


class DispatchBoardSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dashboard = (ROOT / 'templates' / 'dashboard.html').read_text(encoding='utf-8')
        cls.js = (ROOT / 'static' / 'js' / 'app-dashboard.js').read_text(encoding='utf-8')
        cls.css = (ROOT / 'static' / 'css' / 'app-dashboard.css').read_text(encoding='utf-8')
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.board = _block(cls.dashboard, 'data-dashboard-section="scheduler-board"',
                           '{% if dashboard_effective_manager_view')

    def test_board_has_the_three_regions(self):
        for region in ('scheduler-board-queue', 'scheduler-board-lanes', 'scheduler-board-selected'):
            self.assertIn(region, self.board)
        self.assertIn('grid-template-areas: "queue lanes selected"', self.css)

    def test_existing_ids_and_handlers_are_kept(self):
        for element_id in ('scheduler-risk-label', 'scheduler-metric-strip', 'scheduler-dispatch-list',
                           'scheduler-queue-caption', 'scheduler-branch-filters',
                           'scheduler-availability-strip', 'scheduler-availability-count',
                           'scheduler-selected-shift-id', 'scheduler-selected-action-label',
                           'scheduler-assign-engineers', 'scheduler-reschedule-date',
                           'scheduler-reschedule-start', 'scheduler-reschedule-end',
                           'scheduler-action-status'):
            self.assertIn(f'id="{element_id}"', self.board)
        for handler in ('setSchedulerQueueFilter(', 'setSchedulerBranchFilter(',
                        'submitSchedulerQuickAssign()', 'submitSchedulerQuickReschedule()',
                        'loadSchedulerDispatchIntelligence()', 'loadSchedulerCoordinationTools()'):
            self.assertIn(handler, self.board)
        for function in ('selectSchedulerActionShift', 'selectSchedulerEngineerForAssign',
                         'renderSchedulerAvailabilityStrip', 'submitSchedulerAction'):
            self.assertIn(f'function {function}(', self.js)

    def test_board_handlers_are_defined(self):
        for function in ('setSchedulerBoardView', 'startSchedulerQueueDrag', 'allowSchedulerLaneDrop',
                         'dropOnSchedulerLane', 'proposeSchedulerLaneAssign',
                         'confirmSchedulerLaneAssign', 'cancelSchedulerLaneAssign'):
            self.assertIn(f'function {function}(', self.js)
        self.assertIn('draggable="true"', self.js)
        self.assertIn('ondrop="dropOnSchedulerLane(', self.js)

    def test_drop_keeps_engineers_already_assigned(self):
        propose = _block(self.js, 'function proposeSchedulerLaneAssign(', '\n    }\n')
        self.assertIn('engineerIds: [...current, Number(engineerId)]', propose)
        confirm = _block(self.js, 'async function confirmSchedulerLaneAssign(', '\n    }\n')
        self.assertIn("'/scheduler_quick_assign_shift'", confirm)

    def test_keyboard_fallback_exists(self):
        self.assertIn('onclick="proposeSchedulerLaneAssign(', self.js)
        self.assertIn('id="scheduler-drop-confirm"', self.board)

    def test_layout_resets_once_for_the_new_board(self):
        self.assertIn('data-dashboard-layout-version="2"', self.board)
        self.assertIn('function resetDashboardLayoutIfOutdated(', self.js)
        self.assertIn('layoutReset.then(loadDashboardLayoutFromAccount)', self.js)
        self.assertIn("'scheduler-board',", self.app_source)

    def test_lane_blocks_use_status_colours_not_the_accent(self):
        block = _block(self.js, 'function schedulerLaneBlock(', '\n    }\n')
        self.assertIn('dashboardStatusClass(visit.status)', block)
        self.assertNotIn('bg-primary', block)


class DispatchBoardEndpointTests(unittest.TestCase):
    TITLE_PREFIX = 'Board test '

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            app_module.db.create_all()
            cls._seed()

    @classmethod
    def _seed(cls):
        db = app_module.db
        today = app_module.get_manila_today()

        cls.scheduler_username = sorted(app_module.SCHEDULER_USERNAMES)[0]
        if not app_module.User.query.filter_by(username=cls.scheduler_username).first():
            db.session.add(app_module.User(
                username=cls.scheduler_username, role='superadmin', is_active=True,
                password=app_module.generate_password_hash('BoardTest123')
            ))
            db.session.commit()

        def engineer(employee_id, name):
            row = app_module.Engineer.query.filter_by(employee_id=employee_id).first()
            if not row:
                row = app_module.Engineer(employee_id=employee_id, name=name, initials=name[:2].upper(), branch='Cebu')
                db.session.add(row)
                db.session.commit()
            return row

        cls.lane_engineer = engineer('BOARD-E1', 'Lane Engineer').id
        cls.other_engineer = engineer('BOARD-E2', 'Other Engineer').id

        client = app_module.Client.query.filter_by(name='Board Test Hospital').first()
        if not client:
            client = app_module.Client(name='Board Test Hospital')
            db.session.add(client)
            db.session.commit()

        def make_shift(suffix, day_offset, status, engineer_id):
            title = cls.TITLE_PREFIX + suffix
            if app_module.Shift.query.filter_by(title=title).first():
                return
            start = app_module.build_shift_datetime_bounds(
                today + timedelta(days=day_offset), today + timedelta(days=day_offset)
            )[0] + timedelta(hours=9)
            shift = app_module.Shift(title=title, start_time=start, end_time=start + timedelta(hours=2),
                                     engineer_id=engineer_id, client_id=client.id, status=status)
            db.session.add(shift)
            db.session.commit()
            db.session.add(app_module.ShiftEngineer(shift_id=shift.id, engineer_id=engineer_id))
            db.session.commit()

        make_shift('today', 0, 'In Progress', cls.lane_engineer)
        make_shift('in three days', 3, 'Waiting for Parts', cls.lane_engineer)
        make_shift('in eight days', 8, 'In Progress', cls.lane_engineer)
        make_shift('two days ago', -2, 'In Progress', cls.lane_engineer)
        make_shift('completed today', 0, 'Completed', cls.lane_engineer)
        make_shift('other engineer today', 0, 'In Progress', cls.other_engineer)

    @classmethod
    def tearDownClass(cls):
        # Modules share one test database per run; the "completed today" fixture would
        # otherwise be counted by the manager dashboard's weekly completion tests.
        with cls.app.app_context():
            shifts = app_module.Shift.query.filter(app_module.Shift.title.like(cls.TITLE_PREFIX + '%')).all()
            for shift in shifts:
                app_module.ShiftEngineer.query.filter_by(shift_id=shift.id).delete()
                app_module.db.session.delete(shift)
            app_module.db.session.commit()

    def _scheduler_client(self):
        with self.app.app_context():
            user_id = app_module.User.query.filter_by(username=self.scheduler_username).first().id
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def _lane(self, payload, engineer_id):
        return next(row for row in payload['availability'] if row['engineer_id'] == engineer_id)

    def test_lanes_hold_the_engineers_open_visits_for_the_next_seven_days(self):
        response = self._scheduler_client().get('/get_scheduler_coordination_tools')
        self.assertEqual(response.status_code, 200)
        lane = self._lane(response.get_json(), self.lane_engineer)

        titles = {visit['task'] for visit in lane['visits'] if visit['task'].startswith(self.TITLE_PREFIX)}
        self.assertEqual(titles, {self.TITLE_PREFIX + 'today', self.TITLE_PREFIX + 'in three days'})
        for visit in lane['visits']:
            for key in ('id', 'date', 'time_start', 'time_end', 'client', 'status', 'engineer_ids'):
                self.assertIn(key, visit)

    def test_lanes_never_carry_another_engineers_visit(self):
        payload = self._scheduler_client().get('/get_scheduler_coordination_tools').get_json()
        lane = self._lane(payload, self.lane_engineer)
        self.assertNotIn(self.TITLE_PREFIX + 'other engineer today', {visit['task'] for visit in lane['visits']})
        other = self._lane(payload, self.other_engineer)
        self.assertIn(self.TITLE_PREFIX + 'other engineer today', {visit['task'] for visit in other['visits']})

    def test_existing_availability_keys_are_unchanged(self):
        payload = self._scheduler_client().get('/get_scheduler_coordination_tools').get_json()
        lane = self._lane(payload, self.lane_engineer)
        for key in ('engineer_id', 'name', 'initials', 'branch', 'today_tasks', 'next_7_days',
                    'open_tasks', 'overdue', 'waiting_items', 'availability', 'availability_label'):
            self.assertIn(key, lane)
        for key in ('assignable_engineers', 'unassigned_rows', 'action_rows', 'branches'):
            self.assertIn(key, payload)

    def test_board_start_is_the_manila_date(self):
        payload = self._scheduler_client().get('/get_scheduler_coordination_tools').get_json()
        with self.app.app_context():
            self.assertEqual(payload['board_start'], app_module.get_manila_today().isoformat())


if __name__ == '__main__':
    unittest.main()
