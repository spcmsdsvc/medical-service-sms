"""Dashboard phase 2 -- the scheduler dispatch workbench.

The scheduler view was three overlapping read-only lists fed by two endpoints with
different date windows, sitting under a static banner. This phase collapses it to one
priority queue whose rows drive the assign/reschedule panel, filtered by counts that are
themselves buttons.
"""

import os
import pathlib
import tempfile
import unittest
from datetime import timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Pin an isolated database BEFORE importing app.py so the suite can never open the real
# scheduler.db.
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_scheduler_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402
from tests.sw_cache_version import assert_cache_version_at_least  # noqa: E402


class SchedulerDashboardSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.dashboard = (ROOT / 'templates' / 'dashboard.html').read_text(encoding='utf-8')
        cls.css = (ROOT / 'static' / 'css' / 'app-dashboard.css').read_text(encoding='utf-8')
        cls.js = (ROOT / 'static' / 'js' / 'app-dashboard.js').read_text(encoding='utf-8')

    def test_guarded_section_ids_survive(self):
        # test_dashboard_engineer.py asserts these too. Repeated here because this is the
        # phase that rewrote their interiors -- the ids are the contract, not the contents.
        for section in ('scheduler-core', 'scheduler-dispatch', 'scheduler-coordination'):
            self.assertIn(f'data-dashboard-section="{section}"', self.dashboard)

    def test_retired_banner_markup_is_gone_but_its_id_is_still_accepted(self):
        self.assertNotIn('data-dashboard-section="scheduler-final-note"', self.dashboard)
        self.assertNotIn('scheduler-final-note', self.css)
        # Accounts that saved a layout while the section existed still POST the id back,
        # and the layout endpoint rejects unknown ids.
        self.assertIn("'scheduler-final-note',", self.app_source)

    def test_duplicate_sidebar_shortcuts_are_gone(self):
        self.assertNotIn('scheduler-action-card', self.dashboard)
        self.assertNotIn('scheduler-action-grid', self.css)

    def test_scheduler_flag_no_longer_hardcodes_usernames(self):
        self.assertNotIn("'diary'", self.dashboard)
        self.assertNotIn("'hanna'", self.dashboard)
        self.assertIn('nav_is_scheduler', self.dashboard)
        self.assertIn("'nav_is_scheduler': is_scheduler_user(),", self.app_source)

    def test_counts_are_queue_filter_buttons(self):
        for count_id in ('scheduler-overdue-count', 'scheduler-unassigned-count',
                         'scheduler-waiting-count', 'scheduler-pending-tsr-count',
                         'scheduler-next7-count', 'scheduler-queue-count'):
            self.assertIn(f'id="{count_id}"', self.dashboard)

        for filter_name in ('all', 'overdue', 'unassigned', 'waiting', 'tsr'):
            self.assertIn(f'data-scheduler-filter="{filter_name}"', self.dashboard)

        # Real buttons with pressed state, never <i onclick>.
        self.assertIn('setSchedulerQueueFilter', self.js)
        strip = self.dashboard.split('id="scheduler-metric-strip"')[1].split('</div>')[0]
        self.assertNotIn('<i onclick', strip)
        self.assertIn('aria-pressed', strip)

    def test_queue_renderer_issues_no_request_of_its_own(self):
        self.assertIn('function renderSchedulerQueue', self.js)
        renderer = self.js.split('function renderSchedulerQueue')[1].split('\n    function ')[0]
        self.assertNotIn('fetch(', renderer)
        self.assertIn('scheduler-queue-clear', renderer, 'an empty state must exist')

    def test_the_three_overlapping_lists_became_one(self):
        # The separate action queue is gone; its selection role moved onto the queue rows.
        self.assertNotIn('scheduler-action-queue', self.dashboard)
        self.assertNotIn('renderSchedulerActionQueue', self.js)
        self.assertIn('selectSchedulerActionShift', self.js)
        self.assertIn('id="scheduler-dispatch-list"', self.dashboard)

    def test_scheduler_does_not_fetch_the_company_wide_open_task_list(self):
        # Schedulers pass is_admin_authorized(), so without this guard they took the admin
        # branch and downloaded every open shift to render nothing.
        loader = self.js.split('async function loadDashboard()')[1]
        loader = loader.split('function getCurrentEngineerTasks')[0]
        self.assertIn('if (dashboardSchedulerOnly)', loader)
        scheduler_branch = loader.split('if (dashboardSchedulerOnly)')[1].split('} else if')[0]
        self.assertNotIn('/get_open_tasks', scheduler_branch)
        self.assertNotIn('/get_engineers', scheduler_branch)
        # Positive control: the admin branch it now sits in front of really does fetch
        # those, so the negative assertion above is not passing on an empty slice.
        admin_branch = loader.split('} else if (dashboardAdminView)')[1].split('} else {')[0]
        self.assertIn('/get_open_tasks', admin_branch)

    def test_superseded_summary_endpoint_was_removed(self):
        self.assertNotIn("@app.route('/get_scheduler_dashboard_summary')", self.app_source)
        self.assertNotIn('/get_scheduler_dashboard_summary', self.js)
        # The replacement was dead code until this phase; it must now be wired up.
        self.assertIn("@app.route('/get_scheduler_dispatch_intelligence')", self.app_source)
        self.assertIn('/get_scheduler_dispatch_intelligence', self.js)

    def test_availability_colour_and_label_come_from_one_value(self):
        self.assertIn('function schedulerEngineerLoadLevel', self.js)
        self.assertIn('function schedulerAvailabilityLabel', self.js)

    def test_dashboard_assets_are_cached_and_version_bumped(self):
        self.assertIn("'/static/css/app-dashboard.css',", self.app_source)
        self.assertIn("'/static/js/app-dashboard.js',", self.app_source)
        assert_cache_version_at_least(self, 46, self.app_source)

    def test_extracted_js_has_no_template_syntax(self):
        self.assertNotIn('{{', self.js)
        self.assertNotIn('{%', self.js)


class SchedulerDispatchIntelligenceTests(unittest.TestCase):
    """Functional coverage of the endpoint this phase switched on."""

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
        for username, role in ((cls.scheduler_username, 'superadmin'),
                               ('sched_test_engineer', 'engineer')):
            if not app_module.User.query.filter_by(username=username).first():
                db.session.add(app_module.User(
                    username=username, role=role, is_active=True,
                    password=app_module.generate_password_hash('SchedTest123')
                ))
        db.session.commit()

        engineer = app_module.Engineer.query.filter_by(employee_id='SCHED-E1').first()
        if not engineer:
            engineer = app_module.Engineer(
                employee_id='SCHED-E1', name='Queue Engineer', initials='QE', branch='Cebu'
            )
            db.session.add(engineer)
            db.session.commit()
        cls.engineer_id = engineer.id

        client = app_module.Client.query.filter_by(name='Queue Test Hospital').first()
        if not client:
            client = app_module.Client(name='Queue Test Hospital')
            db.session.add(client)
            db.session.commit()
        cls.client_id = client.id

        # Shift.engineer_id is NOT NULL, so an unassigned schedule is one with no
        # ShiftEngineer link whose engineer_id resolves to nothing --
        # get_shift_engineer_records() returns [] only when both lookups come back empty.
        # SQLite does not enforce foreign keys here, which is what makes that state
        # representable at all.
        cls.missing_engineer_id = 10_000_000

        def make_shift(title, day_offset, status, assign):
            # Checked per title, not once for the whole block: the database file lives in
            # the temp directory and survives between runs, so a partially seeded state
            # from an earlier run would otherwise skip the rest of the fixtures.
            existing = app_module.Shift.query.filter_by(title=title).first()
            if existing:
                return existing

            start = app_module.build_shift_datetime_bounds(
                today + timedelta(days=day_offset), today + timedelta(days=day_offset)
            )[0]
            shift = app_module.Shift(
                title=title, start_time=start, end_time=start + timedelta(hours=2),
                engineer_id=engineer.id if assign else cls.missing_engineer_id,
                client_id=client.id, status=status
            )
            db.session.add(shift)
            db.session.commit()
            if assign:
                db.session.add(app_module.ShiftEngineer(shift_id=shift.id, engineer_id=engineer.id))
                db.session.commit()
            return shift

        make_shift('Queue overdue visit', -4, 'In Progress', True)
        make_shift('Queue waiting visit', 2, 'Waiting for Parts', True)
        make_shift('Queue unassigned visit', 3, 'In Progress', False)
        # Qualifies for both the overdue and the unassigned bucket -- the case the queue
        # de-duplication exists for.
        make_shift('Queue overdue unassigned', -6, 'In Progress', False)

    def _scheduler_client(self):
        with self.app.app_context():
            user = app_module.User.query.filter_by(username=self.scheduler_username).first()
            user_id = user.id
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def _engineer_client(self):
        with self.app.app_context():
            user = app_module.User.query.filter_by(username='sched_test_engineer').first()
            user_id = user.id
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def test_summary_endpoint_is_gone(self):
        response = self._scheduler_client().get('/get_scheduler_dashboard_summary')
        self.assertEqual(response.status_code, 404)

    def test_refused_for_a_non_scheduler_account(self):
        response = self._engineer_client().get('/get_scheduler_dispatch_intelligence')
        self.assertEqual(response.status_code, 403)

    def test_priority_rows_carry_the_workbench_fields(self):
        response = self._scheduler_client().get('/get_scheduler_dispatch_intelligence')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()

        self.assertIn('priority_queue', payload)
        self.assertIn('priority_queue_total', payload)
        self.assertTrue(payload['priority_queue'], 'seeded data should produce a queue')

        for row in payload['priority_queue']:
            # engineer_ids prefills the quick-assign multi-select; category drives the
            # filter chips without parsing priority_reason, which is prose.
            self.assertIn('engineer_ids', row)
            self.assertIsInstance(row['engineer_ids'], list)
            self.assertIn(row.get('category'),
                          ('overdue', 'unassigned', 'waiting', 'tsr'))
            self.assertIn('priority_reason', row)

    def test_queue_holds_one_row_per_schedule(self):
        """An overdue visit with nobody assigned qualifies for two buckets.

        The buckets used to be concatenated, so that shift appeared twice in the queue.
        """
        payload = self._scheduler_client().get('/get_scheduler_dispatch_intelligence').get_json()
        ids = [row['id'] for row in payload['priority_queue']]
        self.assertEqual(len(ids), len(set(ids)), 'the queue must not repeat a schedule')

        # Positive control: the shift really is in both underlying buckets, so the
        # de-duplication above is doing work rather than passing on an empty case.
        overdue_ids = {row['id'] for row in payload['overdue_rows']}
        unassigned_ids = {row['id'] for row in payload['unassigned_rows']}
        self.assertTrue(overdue_ids & unassigned_ids,
                        'expected at least one schedule in both buckets')

    def test_unassigned_rows_report_no_engineer_ids(self):
        payload = self._scheduler_client().get('/get_scheduler_dispatch_intelligence').get_json()
        unassigned = [row for row in payload['priority_queue'] if row['category'] == 'unassigned']
        self.assertTrue(unassigned, 'seeded data should include an unassigned schedule')
        for row in unassigned:
            self.assertEqual(row['engineer_ids'], [])


if __name__ == '__main__':
    unittest.main()
