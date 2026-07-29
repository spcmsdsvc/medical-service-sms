"""Dashboard phase 3 -- the manager decision view.

The manager dashboard never mentioned approvals, which is the one job only this role can
do, and every number on it was a snapshot with no direction. This phase leads with the
decision queue, adds week-over-week movement on the metrics that can honestly carry it,
and collapses four overlapping endpoints into two.
"""

import os
import pathlib
import tempfile
import unittest
from datetime import timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Pin an isolated database BEFORE importing app.py so the suite can never open the real
# scheduler.db.
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_manager_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402
from tests.sw_cache_version import assert_cache_version_at_least  # noqa: E402


class ManagerDashboardSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.dashboard = (ROOT / 'templates' / 'dashboard.html').read_text(encoding='utf-8')
        cls.css = (ROOT / 'static' / 'css' / 'app-dashboard.css').read_text(encoding='utf-8')
        cls.js = (ROOT / 'static' / 'js' / 'app-dashboard.js').read_text(encoding='utf-8')

    def test_guarded_section_id_survives_and_new_ones_are_registered(self):
        for section in ('manager-executive', 'manager-direction', 'manager-watchlist'):
            self.assertIn(f'data-dashboard-section="{section}"', self.dashboard)
        # Unregistered ids are rejected by the layout POST handler.
        for section in ('manager-direction', 'manager-watchlist'):
            self.assertIn(f"'{section}',", self.app_source)

    def test_approvals_reach_the_manager_dashboard(self):
        """The whole point of the phase: this template had zero mentions of approvals."""
        self.assertIn('id="manager-approvals"', self.dashboard)
        self.assertIn('/approvals', self.dashboard)
        self.assertIn('loadManagerApprovals', self.js)

    def test_approvals_block_is_gated_on_being_an_approver(self):
        # is_manager_dashboard_user() also admits regional admins and the developer
        # account; without this gate they would see a panel of permanent zeros.
        self.assertIn("'is_approver': is_approver", self.app_source)
        renderer = self.js.split('function renderManagerApprovals')[1].split('\n    async function ')[0]
        self.assertIn('is_approver', renderer)
        self.assertIn("classList.add('d-none')", renderer)

    def test_four_endpoints_became_two(self):
        for retired in ('/get_manager_dashboard_summary', '/get_manager_tsr_intelligence',
                        '/get_manager_billing_visibility', '/get_manager_executive_watchlist'):
            self.assertNotIn(f"@app.route('{retired}')", self.app_source)
            self.assertNotIn(retired, self.js)
        for live in ('/get_manager_overview', '/get_manager_approvals'):
            self.assertIn(f"@app.route('{live}')", self.app_source)
            self.assertIn(live, self.js)

    def test_the_filename_billing_heuristic_is_gone(self):
        # manager_infer_shift_billing_type() string-matched shift titles and TSR filenames
        # and presented the result as a billing rate.
        self.assertNotIn('manager_infer_shift_billing_type', self.app_source)
        self.assertNotIn('billed_signal_rate', self.app_source)
        self.assertNotIn('non_billed_exposure', self.app_source)

    def test_one_waiting_definition(self):
        self.assertIn('MANAGER_WAITING_STATUSES', self.app_source)
        # Exactly one place defines it now; there used to be three.
        self.assertEqual(self.app_source.count("MANAGER_WAITING_STATUSES = {"), 1)

    def test_one_risk_verdict_not_four(self):
        for retired_badge in ('manager-tsr-risk-badge', 'manager-billing-risk-badge',
                              'manager-watchlist-risk-badge'):
            self.assertNotIn(retired_badge, self.dashboard)
        self.assertIn('id="manager-risk-label"', self.dashboard)

    def test_direction_renderer_states_the_comparison_window(self):
        renderer = self.js.split('function renderManagerDirection')[1].split('\n    function ')[0]
        self.assertNotIn('fetch(', renderer)
        self.assertIn('previous_from', renderer)

    def test_dashboard_assets_are_cached_and_version_bumped(self):
        self.assertIn("'/static/css/app-dashboard.css',", self.app_source)
        self.assertIn("'/static/js/app-dashboard.js',", self.app_source)
        assert_cache_version_at_least(self, 47, self.app_source)

    def test_extracted_js_has_no_template_syntax(self):
        self.assertNotIn('{{', self.js)
        self.assertNotIn('{%', self.js)


class ManagerEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.app.config['TESTING'] = True
        cls._previous_workflows_flag = cls.app.config.get('NEW_WORKFLOWS_ENABLED')
        cls.app.config['NEW_WORKFLOWS_ENABLED'] = True
        with cls.app.app_context():
            app_module.db.create_all()
            cls._seed()

    @classmethod
    def tearDownClass(cls):
        """Undo this module's side effects on the shared database and app config.

        Every test module pins MEDICAL_SERVICE_TEST_DB with os.environ.setdefault, so under
        `unittest discover` the first module to import wins and they all share one database
        and one Flask app. Seeding an account named APPROVAL_CENTER_MANAGER_USERNAME makes
        ensure_default_approval_routes() write an ApprovalRouting row for every user; those
        rows have a NOT NULL requester_user_id, and sibling modules that recreate users then
        trip that constraint. Left in place, this module turns 16 unrelated tests red.
        """
        cls.app.config['NEW_WORKFLOWS_ENABLED'] = cls._previous_workflows_flag
        with cls.app.app_context():
            try:
                # Routing rows first: they carry the FK that trips the constraint.
                app_module.ApprovalRouting.query.delete()
                app_module.ReimbursementHeader.query.filter_by(user_id=cls.requester_id).delete()
                app_module.db.session.commit()

                # The approver account has to go too. While a user with this username
                # exists, ensure_default_approval_routes() simply rebuilds the rows on the
                # next request a sibling module makes.
                for username in (cls.manager_username, cls.non_approver_manager,
                                 'mgr_test_engineer'):
                    user = app_module.User.query.filter_by(username=username).first()
                    if user:
                        app_module.db.session.delete(user)
                app_module.db.session.commit()
            except Exception:
                app_module.db.session.rollback()

    @classmethod
    def _seed(cls):
        db = app_module.db
        today = app_module.get_manila_today()
        now = app_module.as_naive_datetime(app_module.get_manila_time())

        # rodito is the legacy approval manager: apply_assigned_approver_filter returns the
        # unfiltered query for him. A configured approver with no routing rows sees nothing.
        cls.manager_username = app_module.APPROVAL_CENTER_MANAGER_USERNAME
        # The regional admin reaches the manager dashboard through is_admin_authorized()
        # without being an approver -- the real case that decides whether the approvals
        # block is hidden or shows a panel of permanent zeros. An approver-only account is
        # NOT a manager-dashboard user and gets 403, so it cannot stand in for this.
        cls.non_approver_manager = app_module.REGIONAL_ADMIN_USERNAME
        accounts = (
            (cls.manager_username, 'superadmin', False),
            ('mgr_test_engineer', 'engineer', False),
            (cls.non_approver_manager, 'regional_admin', False),
        )
        for username, role, can_approve in accounts:
            user = app_module.User.query.filter_by(username=username).first()
            if not user:
                user = app_module.User(
                    username=username, role=role, is_active=True,
                    password=app_module.generate_password_hash('MgrTest123')
                )
                db.session.add(user)
            user.role = role
            user.is_active = True
            if hasattr(user, 'can_approve_requests'):
                user.can_approve_requests = can_approve
        db.session.commit()

        requester = app_module.User.query.filter_by(username='mgr_test_engineer').first()
        cls.requester_id = requester.id

        # Pending approvals of different ages so the aging headline is exercised.
        existing_pending = app_module.ReimbursementHeader.query.filter_by(
            user_id=requester.id, status='Submitted').count()
        if not existing_pending:
            for days_waiting in (20, 1):
                submitted = now - timedelta(days=days_waiting)
                db.session.add(app_module.ReimbursementHeader(
                    user_id=requester.id, status='Submitted',
                    start_date=submitted.date(), end_date=submitted.date(),
                    submitted_at=submitted
                ))
            db.session.commit()

        engineer = app_module.Engineer.query.filter_by(employee_id='MGR-E1').first()
        if not engineer:
            engineer = app_module.Engineer(
                employee_id='MGR-E1', name='Manager Test Engineer', initials='MT', branch='Cebu')
            db.session.add(engineer)
            db.session.commit()
        cls.engineer_id = engineer.id

        client = app_module.Client.query.filter_by(name='Manager Test Hospital').first()
        if not client:
            client = app_module.Client(name='Manager Test Hospital')
            db.session.add(client)
            db.session.commit()
        cls.client_id = client.id

        def make_shift(title, day_offset, status):
            # Checked per title: the database file lives in the temp directory and survives
            # between runs, so a partial seed would otherwise skip later fixtures.
            existing = app_module.Shift.query.filter_by(title=title).first()
            if existing:
                return existing
            start = app_module.build_shift_datetime_bounds(
                today + timedelta(days=day_offset), today + timedelta(days=day_offset))[0]
            shift = app_module.Shift(
                title=title, start_time=start, end_time=start + timedelta(hours=2),
                engineer_id=engineer.id, client_id=client.id, status=status)
            db.session.add(shift)
            db.session.commit()
            db.session.add(app_module.ShiftEngineer(shift_id=shift.id, engineer_id=engineer.id))
            db.session.commit()
            return shift

        # Severely overdue AND blocked on parts -- qualifies for two watchlist sources.
        make_shift('Manager overdue blocked visit', -30, 'Waiting for Parts')
        make_shift('Manager overdue visit', -21, 'In Progress')
        # Flow: completed in the current week and in the previous week.
        make_shift('Manager completed this week', -2, 'Completed')
        make_shift('Manager completed last week', -9, 'Completed')
        make_shift('Manager completed last week two', -10, 'Completed')

    def _client_for(self, username):
        with self.app.app_context():
            user = app_module.User.query.filter_by(username=username).first()
            user_id = user.id
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def test_retired_endpoints_are_gone(self):
        client = self._client_for(self.manager_username)
        for retired in ('/get_manager_dashboard_summary', '/get_manager_tsr_intelligence',
                        '/get_manager_billing_visibility', '/get_manager_executive_watchlist'):
            self.assertEqual(client.get(retired).status_code, 404, retired)

    def test_refused_for_a_non_manager_account(self):
        client = self._client_for('mgr_test_engineer')
        self.assertEqual(client.get('/get_manager_overview').status_code, 403)
        self.assertEqual(client.get('/get_manager_approvals').status_code, 403)

    def test_approval_counts_respect_routing(self):
        """The legacy manager sees everything; a routed approver with no rules sees none."""
        legacy = self._client_for(self.manager_username).get('/get_manager_approvals').get_json()
        self.assertTrue(legacy['is_approver'])
        # Positive control: the fixture really does contain pending requests, so the zero
        # assertion below cannot pass just because nothing was seeded.
        self.assertGreaterEqual(legacy['counts']['pending_total'], 2)

        with self.app.app_context():
            user = app_module.User.query.filter_by(username=self.non_approver_manager).first()
            user.can_approve_requests = True
            app_module.db.session.commit()
        try:
            scoped = self._client_for(self.non_approver_manager).get('/get_manager_approvals').get_json()
            self.assertTrue(scoped['is_approver'])
            # Configured approver, but no ApprovalRouting rows, so nothing routes to them.
            self.assertEqual(scoped['counts']['pending_total'], 0)
        finally:
            with self.app.app_context():
                user = app_module.User.query.filter_by(username=self.non_approver_manager).first()
                user.can_approve_requests = False
                app_module.db.session.commit()

    def test_oldest_waiting_age_comes_from_submitted_at(self):
        payload = self._client_for(self.manager_username).get('/get_manager_approvals').get_json()
        self.assertGreaterEqual(payload['counts']['oldest_days'], 19)
        self.assertGreaterEqual(payload['counts']['aging_total'], 1)

        reimbursement = [row for row in payload['modules'] if row['key'] == 'reimbursement']
        self.assertTrue(reimbursement, 'reimbursement queue should be present')
        self.assertGreaterEqual(reimbursement[0]['oldest_days'], 19)
        self.assertEqual(reimbursement[0]['href'], '/approvals?module=reimbursement')

    def test_non_approver_manager_gets_no_approval_numbers(self):
        """The regional admin reaches this dashboard but approves nothing.

        is_approver false is what lets the page hide the block rather than render zeros
        that read as "nothing is waiting".
        """
        payload = self._client_for(self.non_approver_manager).get('/get_manager_approvals').get_json()
        self.assertFalse(payload['is_approver'])
        self.assertEqual(payload['counts']['pending_total'], 0)
        self.assertEqual(payload['modules'], [])

    def test_only_flow_metrics_carry_a_change(self):
        """Stock metrics must never get a delta.

        A shift that was overdue last week and has since been completed has left the
        overdue set, so any reconstructed historical figure is systematically low.
        """
        payload = self._client_for(self.manager_username).get('/get_manager_overview').get_json()
        metric_keys = {metric['key'] for metric in payload['direction']['metrics']}
        self.assertEqual(metric_keys, {'completed', 'scheduled', 'tsr_rate'})
        for metric in payload['direction']['metrics']:
            self.assertIn('change', metric)
        # The current-state totals live outside direction and expose no change figure.
        for stock_key in ('overdue_schedules', 'pending_tsr', 'waiting_items'):
            self.assertIn(stock_key, payload['counts'])
        self.assertNotIn('change', payload['counts'])

    def test_completed_delta_matches_the_seeded_weeks(self):
        payload = self._client_for(self.manager_username).get('/get_manager_overview').get_json()
        completed = [m for m in payload['direction']['metrics'] if m['key'] == 'completed'][0]
        # One completed 2 days ago, two completed 9 and 10 days ago.
        self.assertEqual(completed['value'], 1)
        self.assertEqual(completed['previous'], 2)
        self.assertEqual(completed['change'], -1)

    def test_watchlist_holds_one_row_per_entity(self):
        payload = self._client_for(self.manager_username).get('/get_manager_overview').get_json()
        keys = [row['key'] for row in payload['watchlist']]
        self.assertEqual(len(keys), len(set(keys)), 'the watchlist must not repeat an entity')

        # Positive control: the blocked-and-overdue shift genuinely qualifies twice, so the
        # de-duplication above is doing work rather than passing on a trivial case.
        with self.app.app_context():
            shift = app_module.Shift.query.filter_by(title='Manager overdue blocked visit').first()
            shift_key = f'shift:{shift.id}'
            self.assertEqual(shift.status, 'Waiting for Parts')
            self.assertLess(shift.start_time.date(), app_module.get_manila_today() - timedelta(days=7))
        self.assertIn(shift_key, keys)
        self.assertEqual(keys.count(shift_key), 1)

    def test_overview_reports_one_risk_verdict(self):
        payload = self._client_for(self.manager_username).get('/get_manager_overview').get_json()
        self.assertIn(payload['risk']['level'], ('stable', 'watch', 'critical'))
        self.assertTrue(payload['risk']['label'])


if __name__ == '__main__':
    unittest.main()
