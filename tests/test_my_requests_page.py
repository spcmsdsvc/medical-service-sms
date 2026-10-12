"""My Requests — Batch A (plans.md): per-module labels, Leave tab, dialog errors, safe POSTs, cleanup.

Source tests read templates/accounting_center.html; endpoint tests check the module badges
returned by /get_accounting_center_modules.
"""

import os
import pathlib
import re
import tempfile
import unittest
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parents[1]

_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_my_requests_page_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402

ACTION_FUNCTIONS = (
    'openCashAdvanceLiquidationDraft',
    'confirmTravelCompletedReady',
    'confirmCashAdvanceLiquidationComplete',
    'confirmTravelLiquidationComplete',
    'confirmMarkPaid',
)

KEPT_FUNCTIONS = (
    'openPaidModal', 'confirmMarkPaid', 'openTravelCompletedConfirm', 'confirmTravelCompletedReady',
    'openCashAdvanceLiquidationCompleteModal', 'confirmCashAdvanceLiquidationComplete',
    'openTravelLiquidationCompleteModal', 'confirmTravelLiquidationComplete',
    'openCashAdvanceLiquidationDraft', 'refreshAccountingQueue', 'setAccountingModule', 'setAccountingTab',
    'fetchAccountingWithTimeout',
)


def _function_body(source, name):
    match = re.search(r'(?:async\s+)?function\s+' + re.escape(name) + r'\s*\(', source)
    if not match:
        return ''
    start = source.index('{', match.end())
    depth = 0
    for index in range(start, len(source)):
        if source[index] == '{':
            depth += 1
        elif source[index] == '}':
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    return source[start:]


class MyRequestsPageSourceTests(unittest.TestCase):
    source = (ROOT / 'templates' / 'accounting_center.html').read_text(encoding='utf-8')

    def test_old_labels_and_dead_code_removed(self):
        for text in ('S12 My Requests', 'status-badge', 'processingModal', 'foundation ready',
                     'openProcessingModal', 'confirmMarkProcessing', 'renderComingSoonQueue',
                     'visibleAccountingModules', 'isTravelCompletionModule', 'liquidation-reminder-note'):
            self.assertNotIn(text, self.source, text)

    def test_module_view_has_every_module_and_headings(self):
        self.assertIn('const MODULE_VIEW = {', self.source)
        for key in ('reimbursements', 'travel_requests', 'cash_advances', 'liquidations', 'leave_requests'):
            self.assertRegex(self.source, r'\n    ' + key + r': \{')
        self.assertIn("['Record','Requester','Trip','Cash advance','Actual expenses','Status','Balance','Actions']", self.source)
        self.assertIn("['Record','Requester','Leave dates','Leave type','Weekdays','Status','HR handoff','Actions']", self.source)
        for kpi_id in ('kpiPendingCaption', 'kpiProcessingCaption', 'kpiPaidCaption', 'kpiPendingLabel'):
            self.assertIn(f'id="{kpi_id}"', self.source)

    def test_actions_use_safe_post_helper(self):
        self.assertIn('async function postAccountingAction(url, body={})', self.source)
        self.assertIn('Your session has expired. Please log in again.', self.source)
        for name in ACTION_FUNCTIONS:
            body = _function_body(self.source, name)
            self.assertIn('postAccountingAction(', body, name)
            self.assertNotIn('res.json()', body, name)

    def test_errors_show_inside_dialogs(self):
        self.assertEqual(self.source.count('data-dialog-error'), 5)  # four slots + the selector
        self.assertIn('function showDialogError(modalId, message)', self.source)
        self.assertIn("showDialogError('paidModal', 'Please select a received method", self.source)
        self.assertIn("methodInput.classList.toggle('is-invalid', !payment_method);", self.source)

    def test_module_switch_remembers_url(self):
        body = _function_body(self.source, 'selectAccountingModule')
        self.assertIn('history.replaceState', body)
        self.assertIn("activeAccountingModule === 'leave_requests'", self.source)

    def test_records_open_in_same_tab(self):
        for name in ('renderTravelRequestRows', 'renderCashAdvanceRows'):
            self.assertNotIn('target="_blank"', _function_body(self.source, name), name)
        leave = _function_body(self.source, 'renderLeaveRequestRows')
        self.assertIn('status-pill', leave)
        self.assertIn('action-btns', leave)

    def test_kept_functions_and_timeout(self):
        for name in KEPT_FUNCTIONS:
            self.assertRegex(self.source, r'function\s+' + name + r'\s*\(', name)
        self.assertIn('const ACCOUNTING_REQUEST_TIMEOUT_MS = 15000;', self.source)
        self.assertIn('My Requests is taking too long to respond.', self.source)


class MyRequestsModuleBadgeTests(unittest.TestCase):
    USERNAME = 'my_requests_page_test_user'
    EMPLOYEE_ID = 'MRP-E1'
    LIQUIDATION_TR_IDS = (990000101, 990000102, 990000103)

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_travel_liquidation_tables()
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
            app_module.LeaveRequest.query.filter(app_module.LeaveRequest.request_no.like('MRP-TEST-%')).delete(synchronize_session=False)
            app_module.TravelLiquidationHeader.query.filter(
                app_module.TravelLiquidationHeader.travel_request_id.in_(cls.LIQUIDATION_TR_IDS)).delete(synchronize_session=False)
            engineer = app_module.Engineer.query.filter_by(employee_id=cls.EMPLOYEE_ID).first()
            if engineer:
                db.session.delete(engineer)
            user = app_module.User.query.filter_by(username=cls.USERNAME).first()
            if user:
                db.session.delete(user)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

    @classmethod
    def _seed(cls):
        db = app_module.db
        user = app_module.User(username=cls.USERNAME, role='engineer', is_active=True,
                               password=app_module.generate_password_hash('MyRequests123'))
        db.session.add(user)
        db.session.commit()
        cls.user_id = user.id
        engineer = app_module.Engineer(employee_id=cls.EMPLOYEE_ID, name='My Requests Test', initials='MR',
                                       branch='Manila', user_id=user.id)
        db.session.add(engineer)
        db.session.commit()
        day = date(2026, 10, 1)
        statuses = ['Draft', 'Form to Follow', 'Provisional', 'Rejected', 'Submitted', 'Approved', 'Superseded']
        for index, status in enumerate(statuses):
            db.session.add(app_module.LeaveRequest(
                request_no=f'MRP-TEST-{index}', user_id=user.id, engineer_id=engineer.id,
                application_date=day, leave_type='Vacation Leave', start_date=day, end_date=day,
                weekday_count=1, status=status))
        for tr_id, status in zip(cls.LIQUIDATION_TR_IDS, ('Draft', 'Rejected', 'Completed')):
            db.session.add(app_module.TravelLiquidationHeader(travel_request_id=tr_id, user_id=user.id, status=status))
        db.session.commit()

    def _modules(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.user_id)
            session['_fresh'] = True
        response = client.get('/get_accounting_center_modules')
        self.assertEqual(response.status_code, 200)
        return {mod['key']: mod for mod in response.get_json()['modules']}

    def test_leave_badge_counts_open_leave(self):
        # Draft + Form to Follow + Provisional + Rejected + Submitted; not Approved or Superseded.
        self.assertEqual(self._modules()['leave_requests']['badge_count'], 5)

    def test_rejected_liquidation_counts_in_badge(self):
        self.assertEqual(self._modules()['liquidations']['badge_count'], 2)

    def test_travel_completion_module_hidden(self):
        self.assertNotIn('travel_completion', self._modules())


if __name__ == '__main__':
    unittest.main()
