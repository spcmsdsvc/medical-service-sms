"""My Requests — Batch B (plans.md): "Needs your action" tab, Rejected tabs, sidebar badge.

Endpoint tests seed one record per rule for one user (plus another user's records) and
check the action list, the module badge and /api/nav/pending-summary. Source tests read
templates/accounting_center.html.
"""

import os
import pathlib
import re
import tempfile
import unittest
from datetime import date, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]

_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_my_requests_actions_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402

KEPT_FUNCTIONS = (
    'openPaidModal', 'confirmMarkPaid', 'openTravelCompletedConfirm', 'confirmTravelCompletedReady',
    'openCashAdvanceLiquidationCompleteModal', 'confirmCashAdvanceLiquidationComplete',
    'openTravelLiquidationCompleteModal', 'confirmTravelLiquidationComplete',
    'openCashAdvanceLiquidationDraft', 'refreshAccountingQueue', 'setAccountingModule', 'setAccountingTab',
    'fetchAccountingWithTimeout', 'postAccountingAction', 'selectAccountingModule', 'renderActionRows',
)


def _function_body(source, name):
    match = re.search(r'(?:async\s+)?function\s+' + re.escape(name) + r'\s*\(', source)
    if not match:
        return ''
    start = re.compile(r'\)\s*\{').search(source, match.end()).end() - 1  # skip `options={}` defaults
    depth = 0
    for index in range(start, len(source)):
        if source[index] == '{':
            depth += 1
        elif source[index] == '}':
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    return source[start:]


class MyRequestsActionSourceTests(unittest.TestCase):
    source = (ROOT / 'templates' / 'accounting_center.html').read_text(encoding='utf-8')

    def test_action_module_is_default(self):
        self.assertIn("let activeAccountingModule = 'action';", self.source)
        self.assertIn("let activeQueueEndpoint = '/get_accounting_action_queue';", self.source)
        self.assertRegex(self.source, r'\n    action: \{')
        self.assertIn("['Record','Type','Amount','Date','Status','What to do','Actions']", self.source)
        self.assertIn('Nothing needs you right now.', self.source)

    def test_action_buttons_map_to_existing_dialogs(self):
        body = _function_body(self.source, 'actionButton')
        for action, target in (
            ('confirm_received', 'openPaidModal('),
            ('travel_completed', 'openTravelCompletedConfirm('),
            ('complete_travel_liquidation', 'openTravelLiquidationCompleteModal('),
            ('complete_cash_advance_liquidation', 'openCashAdvanceLiquidationCompleteModal('),
            ('create_cash_advance_liquidation', 'openCashAdvanceLiquidationDraft('),
        ):
            self.assertIn(f"case '{action}':", body, action)
            self.assertIn(target, body, action)

    def test_cash_advance_lookup_matches_module(self):
        body = _function_body(self.source, 'openCashAdvanceLiquidationDraft')
        self.assertIn("row.module === 'cash_advances'", body)

    def test_rejected_tab(self):
        self.assertIn('data-status="rejected"', self.source)
        self.assertIn("const ACCOUNTING_STATUSES = ['pending','processing','paid','all','rejected'];", self.source)
        for name in ('selectAccountingModule', 'setAccountingTab', 'applyAccountingUrlParams'):
            self.assertIn('ACCOUNTING_STATUSES.includes(', _function_body(self.source, name), name)
        self.assertEqual(self.source.count("rejected: 'Rejected'"), 3)

    def test_list_loads_use_safe_reader(self):
        self.assertIn('async function readAccountingJson(res)', self.source)
        for name in ('loadAccountingModules', 'refreshAccountingQueue'):
            body = _function_body(self.source, name)
            self.assertIn('readAccountingJson(res)', body, name)
            self.assertNotIn('res.json()', body, name)

    def test_kept_functions(self):
        for name in KEPT_FUNCTIONS:
            self.assertRegex(self.source, r'function\s+' + name + r'\s*\(', name)
        self.assertIn('const ACCOUNTING_REQUEST_TIMEOUT_MS = 15000;', self.source)


class MyRequestsActionEndpointTests(unittest.TestCase):
    USERNAME = 'my_requests_actions_user'
    OTHER_USERNAME = 'my_requests_actions_other'
    EMPLOYEE_ID = 'MRA-E1'
    PREFIX = 'MRA-TEST-'

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_travel_request_tables()
            app_module.ensure_travel_liquidation_tables()
            app_module.ensure_cash_advance_tables()
            app_module.ensure_cash_advance_liquidation_tables()
            app_module.ensure_reimbursement_payment_columns()
            cls._cleanup()
            cls._seed()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            cls._cleanup()

    @classmethod
    def _cleanup(cls):
        m = app_module
        db = m.db
        try:
            users = m.User.query.filter(m.User.username.in_([cls.USERNAME, cls.OTHER_USERNAME])).all()
            user_ids = [u.id for u in users] or [0]
            m.LeaveRequest.query.filter(m.LeaveRequest.user_id.in_(user_ids)).delete(synchronize_session=False)
            m.CashAdvanceLiquidationHeader.query.filter(m.CashAdvanceLiquidationHeader.user_id.in_(user_ids)).delete(synchronize_session=False)
            m.CashAdvanceHeader.query.filter(m.CashAdvanceHeader.user_id.in_(user_ids)).delete(synchronize_session=False)
            m.TravelLiquidationHeader.query.filter(m.TravelLiquidationHeader.user_id.in_(user_ids)).delete(synchronize_session=False)
            tr_ids = [r.id for r in m.TravelRequest.query.filter(m.TravelRequest.user_id.in_(user_ids)).all()] or [0]
            m.TravelRequestParticipant.query.filter(m.TravelRequestParticipant.travel_request_id.in_(tr_ids)).delete(synchronize_session=False)
            m.TravelRequest.query.filter(m.TravelRequest.id.in_(tr_ids)).delete(synchronize_session=False)
            m.ReimbursementHeader.query.filter(m.ReimbursementHeader.user_id.in_(user_ids)).delete(synchronize_session=False)
            for engineer in m.Engineer.query.filter_by(employee_id=cls.EMPLOYEE_ID).all():
                db.session.delete(engineer)
            for user in users:
                db.session.delete(user)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

    @classmethod
    def _seed(cls):
        m = app_module
        db = m.db
        today = m.get_manila_today()
        user = m.User(username=cls.USERNAME, role='engineer', is_active=True, password=m.generate_password_hash('Actions123'))
        other = m.User(username=cls.OTHER_USERNAME, role='engineer', is_active=True, password=m.generate_password_hash('Actions123'))
        db.session.add_all([user, other])
        db.session.commit()
        cls.user_id, cls.other_id = user.id, other.id
        engineer = m.Engineer(employee_id=cls.EMPLOYEE_ID, name='My Requests Actions', initials='MA', branch='Manila', user_id=user.id)
        db.session.add(engineer)
        db.session.commit()

        def reimbursement(owner, status, accounting=None):
            rec = m.ReimbursementHeader(user_id=owner, start_date=today, end_date=today, status=status, accounting_status=accounting)
            db.session.add(rec)
            return rec

        cls.reimb_rejected = reimbursement(user.id, 'Rejected')
        cls.reimb_approved = reimbursement(user.id, 'Approved')
        reimbursement(user.id, 'Paid', 'Paid')
        reimbursement(user.id, 'Draft')
        cls.reimb_other = reimbursement(other.id, 'Rejected')

        def travel(no, owner, status, return_date=None, funds=False):
            rec = m.TravelRequest(request_no=cls.PREFIX + no, user_id=owner, purpose='Test trip', status=status,
                                  departure_date=(return_date or today) - timedelta(days=1), return_date=return_date or today,
                                  funds_received_at=m.get_manila_time() if funds else None)
            db.session.add(rec)
            return rec

        travel('TR-REJ', user.id, 'Rejected')
        travel('TR-APP', user.id, 'Approved')
        travel('TR-OVER', user.id, 'Funds Received', today - timedelta(days=1), funds=True)
        travel('TR-FUTURE', user.id, 'Funds Received', today + timedelta(days=3), funds=True)
        tr_draft = travel('TR-DRAFT', user.id, 'Draft')
        shared = travel('TR-SHARED', other.id, 'Rejected')
        travel('TR-OTHER', other.id, 'Approved')
        db.session.commit()
        db.session.add(m.TravelRequestParticipant(travel_request_id=shared.id, user_id=user.id))

        tl_trips = [travel(f'TR-TL{i}', user.id, 'Liquidation Started') for i in range(4)]
        db.session.commit()
        for trip, status, no in zip(tl_trips, ('Returned', 'Draft', 'Approved', 'Completed'), ('RET', 'DRAFT', 'APP', 'DONE')):
            db.session.add(m.TravelLiquidationHeader(liquidation_no=cls.PREFIX + 'TL-' + no, travel_request_id=trip.id, user_id=user.id, status=status))

        def cash_advance(no, owner, status, received=False):
            rec = m.CashAdvanceHeader(cash_advance_no=cls.PREFIX + no, user_id=owner, status=status, amount_requested=1000,
                                      received_at=m.get_manila_time() if received else None)
            db.session.add(rec)
            return rec

        cash_advance('CA-REJ', user.id, 'Rejected')
        cash_advance('CA-APP', user.id, 'Approved')
        cash_advance('CA-READY', user.id, 'Ready for Liquidation', received=True)
        cash_advance('CA-DRAFT', user.id, 'Draft')
        cash_advance('CA-OTHER', other.id, 'Rejected')
        ca_liq = [cash_advance(f'CA-L{i}', user.id, 'Liquidation Draft', received=True) for i in range(3)]
        db.session.commit()
        for ca, status, no in zip(ca_liq, ('Rejected', 'Draft', 'Approved'), ('REJ', 'DRAFT', 'APP')):
            db.session.add(m.CashAdvanceLiquidationHeader(liquidation_no=cls.PREFIX + 'CAL-' + no, cash_advance_id=ca.id, user_id=user.id, status=status))

        day = date(2026, 10, 1)
        for status in ('Rejected', 'Form to Follow', 'Provisional', 'Draft', 'Submitted', 'Approved'):
            db.session.add(m.LeaveRequest(request_no=cls.PREFIX + 'LV-' + status.replace(' ', ''), user_id=user.id, engineer_id=engineer.id,
                                          application_date=day, leave_type='Vacation Leave', start_date=day, end_date=day,
                                          weekday_count=1, status=status))
        db.session.commit()
        cls.reimb_rejected_id = cls.reimb_rejected.id
        cls.reimb_approved_id = cls.reimb_approved.id
        cls.reimb_other_id = cls.reimb_other.id

    def _client(self, user_id=None):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id or self.user_id)
            session['_fresh'] = True
        return client

    def _items(self):
        response = self._client().get('/get_accounting_action_queue')
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def _by_record(self, items):
        return {item['record_no']: item for item in items}

    def test_each_rule_lands_in_its_group(self):
        items = self._by_record(self._items()['items'])
        p = self.PREFIX
        expected = {
            f'Reimbursement #{self.reimb_rejected_id}': ('fix', 'open'),
            f'Reimbursement #{self.reimb_approved_id}': ('confirm', 'confirm_received'),
            p + 'TR-REJ': ('fix', 'open'),
            p + 'TR-SHARED': ('fix', 'open'),
            p + 'TR-APP': ('confirm', 'confirm_received'),
            p + 'TR-OVER': ('next', 'travel_completed'),
            p + 'CA-REJ': ('fix', 'open'),
            p + 'CA-APP': ('confirm', 'confirm_received'),
            p + 'CA-READY': ('next', 'create_cash_advance_liquidation'),
            p + 'TL-RET': ('fix', 'open'),
            p + 'TL-DRAFT': ('next', 'open'),
            p + 'TL-APP': ('next', 'complete_travel_liquidation'),
            p + 'CAL-REJ': ('fix', 'open'),
            p + 'CAL-DRAFT': ('next', 'open'),
            p + 'CAL-APP': ('next', 'complete_cash_advance_liquidation'),
            p + 'LV-Rejected': ('fix', 'open'),
            p + 'LV-FormtoFollow': ('next', 'open'),
            p + 'LV-Provisional': ('next', 'open'),
        }
        self.assertEqual({k: (v['group'], v['action']) for k, v in items.items()}, expected)

    def test_future_trip_drafts_and_other_users_excluded(self):
        records = set(self._by_record(self._items()['items']))
        for absent in ('TR-FUTURE', 'TR-DRAFT', 'TR-OTHER', 'CA-DRAFT', 'CA-OTHER', 'TL-DONE', 'LV-Draft', 'LV-Submitted'):
            self.assertNotIn(self.PREFIX + absent, records, absent)
        self.assertNotIn(f'Reimbursement #{self.reimb_other_id}', records)

    def test_summary_badge_and_sidebar_agree(self):
        payload = self._items()
        self.assertEqual(payload['summary']['pending'], 7)
        self.assertEqual(payload['summary']['processing'], 8)
        self.assertEqual(payload['summary']['paid'], 3)  # listed, not counted
        modules = self._client().get('/get_accounting_center_modules').get_json()['modules']
        self.assertEqual(modules[0]['key'], 'action')
        self.assertEqual(modules[0]['badge_count'], 15)
        previous = self.app.config.get('NEW_WORKFLOWS_ENABLED')
        self.app.config['NEW_WORKFLOWS_ENABLED'] = True
        try:
            summary = self._client().get('/api/nav/pending-summary').get_json()
        finally:
            self.app.config['NEW_WORKFLOWS_ENABLED'] = previous
        self.assertEqual(summary['my_requests_action'], 15)

    def test_reimbursement_rejected_queue(self):
        response = self._client().get('/get_accounting_reimbursement_queue?status=rejected')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['status'], 'rejected')
        self.assertEqual([item['id'] for item in payload['items']], [self.reimb_rejected_id])


if __name__ == '__main__':
    unittest.main()
