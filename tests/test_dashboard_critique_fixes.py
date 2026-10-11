"""Dashboard critique fixes (plans.md, 2026-10-11).

The Impeccable critique scored the dashboard 23/40: work below the fold on phones, an
accent-coloured status badge, red zeros, rows that led nowhere, a raw table for staff
accounts and no field KPIs. These tests pin each fix.
"""

import os
import pathlib
import tempfile
import unittest
from datetime import timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Optional override so the source tests can be pointed at an older checkout to prove
# they fail without the fixes (positive control).
SOURCE_ROOT = pathlib.Path(os.environ.get('DASHBOARD_FIXES_SOURCE_ROOT') or ROOT)

_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_dashboard_fixes_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))


def _read(*parts):
    return (SOURCE_ROOT.joinpath(*parts)).read_text(encoding='utf-8')


def _block(source, start_marker, end_marker):
    return source.split(start_marker, 1)[1].split(end_marker, 1)[0]


class DashboardCritiqueSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dashboard = _read('templates', 'dashboard.html')
        cls.js = _read('static', 'js', 'app-dashboard.js')
        cls.css = _read('static', 'css', 'app-dashboard.css')

    def test_layout_controls_moved_to_the_header_and_say_account(self):
        self.assertNotIn('dashboard-personalize-toolbar', self.dashboard)
        self.assertNotIn('saved on this device', self.dashboard)
        # Dashboard Style moved them into the shadcn-style page header.
        header = _block(self.dashboard, 'class="dash-page-header', '{# RETIRED')
        self.assertIn('id="dashboard-customize-toggle"', header)
        self.assertIn('saved to your account', header)
        # Desktop-only, so they no longer push phone content down.
        self.assertIn('d-none d-md-flex', header)

    def test_reset_asks_first(self):
        reset = _block(self.js, 'function resetDashboardLayout', '\n    function ')
        self.assertIn('confirm(', reset)

    def test_page_has_an_h1_and_no_pro_only_icon(self):
        # Dashboard Style made the title visible (owner, 2026-10-11).
        self.assertIn('<h1 class="dash-page-h1">Dashboard</h1>', self.dashboard)
        self.assertNotIn('fa-hand-wave', self.dashboard)

    def test_whats_new_has_no_inline_colours_and_can_be_dismissed(self):
        section = _block(self.dashboard, '<section id="dashboard-whats-new"', '</section>')
        self.assertNotIn('#', section.split('>', 1)[0], 'no hex colours on the section tag')
        self.assertNotIn('style="width:40px', section)
        self.assertIn('id="dashboard-whats-new-dismiss"', section)
        self.assertIn('class="dashboard-whats-new-icon"', section)
        self.assertIn('.dashboard-whats-new {', self.css)

    def test_status_colours_never_use_the_accent(self):
        status = _block(self.js, 'function dashboardBootstrapStatusClass', '\n    function ')
        self.assertNotIn('bg-primary', status)
        render = _block(self.js, 'function filterAndRender', '\n    // Application Entry')
        self.assertNotIn('bg-primary', render)
        self.assertNotIn('font-size: 0.65rem', render)
        self.assertNotIn('.dashboard-status-progress { background: #e7f1ff; color: #0d6efd; }', self.css)

    def test_zero_metrics_are_not_red(self):
        strip = _block(self.dashboard, 'data-dashboard-section="engineer-summary"', '</div>\n\n')
        self.assertNotIn('dashboard-metric-value dashboard-metric-alert', strip)
        self.assertNotIn('dashboard-metric-value dashboard-metric-warn', strip)
        setter = _block(self.js, 'function setMetricValue', '\n    async function ')
        self.assertIn('Number(value) > 0', setter)

    def test_rows_open_their_week_on_the_timeline(self):
        self.assertIn('/timeline?date=', self.js)
        for renderer in ('function renderMyTasks', 'function filterAndRender',
                         'function buildDashboardTaskMobileCard', 'function renderEngineerTodayPanel'):
            body = _block(self.js, renderer, '\n    function ')
            self.assertIn('dashboardTimelineHref(', body, renderer)

    def test_past_due_rows_carry_a_text_chip(self):
        self.assertIn("day${days === 1 ? '' : 's'} late", self.js)
        for renderer in ('function renderMyTasks', 'function filterAndRender'):
            self.assertIn('dashboardLateChip(task)', _block(self.js, renderer, '\n    function '), renderer)

    def test_open_tasks_have_search_engineer_filter_and_a_sort_select(self):
        for element in ('id="open-tasks-search"', 'id="filter-engineer"', 'id="sort-mode"'):
            self.assertIn(element, self.dashboard)
        self.assertNotIn('id="sort-btn"', self.dashboard)
        # The old handler stays defined for any existing caller.
        self.assertIn('function toggleSort()', self.js)

    def test_phone_lists_are_paged(self):
        self.assertIn('DASHBOARD_MOBILE_PAGE_SIZE = 20', self.js)
        self.assertIn('dashboard-show-more', self.js)

    def test_staff_get_a_waiting_card_and_a_collapsed_table(self):
        self.assertIn('{% set dashboard_staff_landing', self.dashboard)
        self.assertIn('id="staff-waiting"', self.dashboard)
        self.assertIn("'/api/nav/pending-summary'", self.js)
        self.assertIn('{% if dashboard_has_engineer_profile or dashboard_staff_landing %}collapse', self.dashboard)

    def test_kpis_are_wired(self):
        self.assertIn('id="manager-pm-summary"', self.dashboard)
        self.assertIn('Inventory PM (Genoray, Vieworks)', self.js)
        self.assertIn('id="count-my-pending-tsr"', self.dashboard)
        self.assertIn("'/get_my_pending_tsr_count'", self.js)

    def test_off_limits_sections_keep_their_markup(self):
        """Needs Your Decision kept its markup. (The scheduler workbench was unlocked and
        rebuilt as the dispatch board -- see tests/test_dashboard_dispatch_board.py.)"""
        self.assertIn('data-dashboard-section="manager-executive"', self.dashboard)
        executive = _block(self.dashboard, 'data-dashboard-section="manager-executive"',
                           'data-dashboard-section="manager-direction"')
        self.assertIn('<h5 class="mb-0 fw-bold text-dark">', executive)
        self.assertIn('id="manager-approvals"', executive)


import app as app_module  # noqa: E402


class DashboardCritiqueEndpointTests(unittest.TestCase):
    ENGINEER_USER = 'fixes_test_engineer'
    OTHER_USER = 'fixes_test_other_engineer'
    STAFF_USER = 'fixes_test_staff'
    PM_BRAND = 'genoray'
    PM_SERIAL_PREFIX = 'FIXES-PM-'

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_inventory_pm_visit_table()
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
            app_module.InventoryPmVisit.query.filter(
                app_module.InventoryPmVisit.equipment_serial.like(f'{cls.PM_SERIAL_PREFIX}%')
            ).delete(synchronize_session=False)
            shifts = app_module.Shift.query.filter(app_module.Shift.title.like('Fixes test %')).all()
            for shift in shifts:
                app_module.ShiftEngineer.query.filter_by(shift_id=shift.id).delete()
                db.session.delete(shift)
            for employee_id in ('FIX-E1', 'FIX-E2'):
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
                                   password=app_module.generate_password_hash('FixesTest123'))
            db.session.add(user)
            users[username] = user
        db.session.commit()

        mine = app_module.Engineer(employee_id='FIX-E1', name='Fixes Engineer', initials='FE',
                                   branch='Manila', user_id=users[cls.ENGINEER_USER].id)
        other = app_module.Engineer(employee_id='FIX-E2', name='Fixes Other', initials='FO',
                                    branch='Manila', user_id=users[cls.OTHER_USER].id)
        db.session.add_all([mine, other])
        client = app_module.Client.query.filter_by(name='Fixes Test Hospital').first()
        if not client:
            client = app_module.Client(name='Fixes Test Hospital')
            db.session.add(client)
        db.session.commit()

        def make_shift(title, day_offset, status, engineer):
            start = app_module.build_shift_datetime_bounds(
                today + timedelta(days=day_offset), today + timedelta(days=day_offset))[0]
            shift = app_module.Shift(title=title, start_time=start, end_time=start + timedelta(hours=2),
                                     engineer_id=engineer.id, client_id=client.id, status=status)
            db.session.add(shift)
            db.session.commit()
            db.session.add(app_module.ShiftEngineer(shift_id=shift.id, engineer_id=engineer.id))
            db.session.commit()

        # Two completed visits without a TSR for this engineer, one still open (not pending
        # TSR) and one completed for another engineer (must not be counted).
        make_shift('Fixes test completed one', -3, 'Completed', mine)
        make_shift('Fixes test completed two', -10, 'Completed', mine)
        make_shift('Fixes test open', -1, 'In Progress', mine)
        make_shift('Fixes test other engineer', -2, 'Completed', other)

        # PM: this month 2 due (1 done), plus 1 overdue from an earlier day.
        month_start = today.replace(day=1)
        now = app_module.as_naive_datetime(app_module.get_manila_time())
        rows = [
            (f'{cls.PM_SERIAL_PREFIX}1', month_start, None),
            (f'{cls.PM_SERIAL_PREFIX}2', month_start, now),
            (f'{cls.PM_SERIAL_PREFIX}3', today - timedelta(days=40), None),
        ]
        for serial, target, completed in rows:
            db.session.add(app_module.InventoryPmVisit(
                brand=cls.PM_BRAND, equipment_serial=serial, target_date=target, completed_at=completed))
        db.session.commit()

    def _client_for(self, username):
        with self.app.app_context():
            user_id = app_module.User.query.filter_by(username=username).first().id
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def test_pending_tsr_counts_only_the_signed_in_engineers_visits(self):
        data = self._client_for(self.ENGINEER_USER).get('/get_my_pending_tsr_count').get_json()
        self.assertEqual(data['pending_tsr'], 2)
        other = self._client_for(self.OTHER_USER).get('/get_my_pending_tsr_count').get_json()
        self.assertEqual(other['pending_tsr'], 1)

    def test_pending_tsr_is_zero_without_an_engineer_profile(self):
        data = self._client_for(self.STAFF_USER).get('/get_my_pending_tsr_count').get_json()
        self.assertEqual(data['pending_tsr'], 0)

    def test_inventory_pm_month_summary_counts(self):
        with self.app.app_context():
            summary = app_module.inventory_pm_month_summary(app_module.get_manila_today())
            fixture = app_module.InventoryPmVisit.query.filter(
                app_module.InventoryPmVisit.equipment_serial.like(f'{self.PM_SERIAL_PREFIX}%')).count()
        self.assertEqual(fixture, 3, 'positive control: the PM fixture exists')
        # Other modules may share the database, so assert at least the fixture's share.
        self.assertGreaterEqual(summary['due_this_month'], 2)
        self.assertGreaterEqual(summary['done_this_month'], 1)
        self.assertGreaterEqual(summary['overdue'], 1)

    def test_manager_overview_carries_the_pm_block(self):
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        overview = source.split('def get_manager_overview', 1)[1].split('\ndef ', 1)[0]
        self.assertIn("'pm': inventory_pm_month_summary(today)", overview)

    def test_staff_dashboard_leads_with_waiting_items(self):
        response = self._client_for(self.STAFF_USER).get('/')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('id="staff-waiting"', html)
        self.assertIn('id="open-tasks-panel" class="collapse"', html)
        self.assertIn('data-dashboard-section="quick-admin"', html)
        self.assertIn('staffLanding: true', html)

    def test_engineer_dashboard_does_not_get_the_staff_card(self):
        html = self._client_for(self.ENGINEER_USER).get('/').get_data(as_text=True)
        self.assertNotIn('id="staff-waiting"', html)
        self.assertIn('id="count-my-pending-tsr"', html)


if __name__ == '__main__':
    unittest.main()
