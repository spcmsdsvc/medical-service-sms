"""My Requests — Batches A, C and D (plans.md): per-module labels, Leave tab, dialog errors, safe POSTs, cleanup.

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
        self.assertIn("['Record','Trip','Cash advance','Actual expenses','Status','Balance','Actions']", self.source)
        self.assertIn("['Record','Leave dates','Leave type','Weekdays','Status','HR handoff','Actions']", self.source)
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


ROW_RENDERERS = (
    'renderActionRows', 'renderReimbursementRows', 'renderTravelRequestRows',
    'renderCashAdvanceRows', 'renderLiquidationRows', 'renderLeaveRequestRows',
)


class MyRequestsStyleSourceTests(unittest.TestCase):
    """Batch C (plans.md): dashboard look and phone cards, same behaviour."""

    source = MyRequestsPageSourceTests.source

    def test_dashboard_styles_linked_and_hero_removed(self):
        self.assertIn("filename='css/app-dashboard.css') }}?v=15", self.source)
        for text in ('accounting-hero', 'alert alert-info', 'kpi-card', 'queue-card', 'module-tab ', 'module-badge'):
            self.assertNotIn(text, self.source, text)
        self.assertIn('class="dash-page-header"', self.source)
        self.assertIn('class="dash-page-h1">My Requests</h1>', self.source)

    def test_pill_tabs_stat_cards_and_segmented_filter(self):
        self.assertIn('class="work-orders-tabs" id="accountingModuleTabs" role="tablist"', self.source)
        tabs = _function_body(self.source, 'renderAccountingModuleTabs')
        self.assertIn('class="work-orders-tab"', tabs)
        self.assertIn('aria-selected=', tabs)
        self.assertIn('work-orders-tab-count', tabs)
        self.assertEqual(self.source.count('class="dash-stat"'), 3)
        for kpi_id in ('kpiPending', 'kpiProcessing', 'kpiPaid'):
            self.assertIn(f'class="dash-stat-num" id="{kpi_id}"', self.source)
        self.assertIn('class="dash-segment d-none" id="accountingStatusFilter"', self.source)
        self.assertEqual(self.source.count('class="dash-segment-btn'), 5)
        busy = _function_body(self.source, 'setAccountingActionBusy')
        self.assertIn('#accountingStatusFilter .dash-segment-btn', busy)
        self.assertIn('#accountingModuleTabs .work-orders-tab', busy)

    def test_tone_only_on_action_tab_above_zero(self):
        body = _function_body(self.source, 'updateSummary')
        self.assertIn("activeAccountingModule === 'action'", body)
        self.assertIn('count > 0', body)
        self.assertIn('dashboard-metric-alert', body)
        self.assertIn('dashboard-metric-warn', body)

    def test_every_row_renderer_labels_cells(self):
        helper = _function_body(self.source, 'labelQueueCells')
        self.assertIn('moduleView().headers', helper)
        self.assertIn('dataset.label', helper)
        for name in ROW_RENDERERS:
            self.assertIn('labelQueueCells();', _function_body(self.source, name), name)
        self.assertIn('td[data-label]::before', self.source)
        # app-dashboard.css hides ".table-responsive table" on phones; the page must win.
        self.assertIn('.accounting-list .table-responsive .table-accounting', self.source)

    def test_dialog_headers_are_plain(self):
        for header in re.findall(r'<div class="modal-header[^"]*"', self.source):
            for colour in ('bg-success', 'bg-primary', 'bg-warning', 'text-white'):
                self.assertNotIn(colour, header)
        self.assertNotIn('btn-close-white', self.source)
        self.assertIn('class="btn btn-primary fw-bold" id="confirmTravelCompletedBtn"', self.source)

    def test_kept_ids_and_functions_guard(self):
        for name in ('selectAccountingModule', 'setAccountingTab', 'renderActionRows', 'postAccountingAction',
                     'readAccountingJson', 'fetchAccountingWithTimeout', 'showDialogError', 'setAccountingActionBusy'):
            self.assertRegex(self.source, r'function\s+' + name + r'\s*\(', name)
        for element_id in ('accountingModuleTabs', 'activeQueueTitle', 'queueSubtitle', 'accountingAlert',
                           'accountingQueueHeaders', 'accountingQueueBody', 'kpiPaidCaption'):
            self.assertIn(f'id="{element_id}"', self.source, element_id)
        for status in ('pending', 'processing', 'paid', 'all', 'rejected'):
            self.assertIn(f'data-status="{status}"', self.source, status)


MODULE_RENDERERS = {
    'action': 'renderActionRows',
    'reimbursements': 'renderReimbursementRows',
    'travel_requests': 'renderTravelRequestRows',
    'cash_advances': 'renderCashAdvanceRows',
    'liquidations': 'renderLiquidationRows',
    'leave_requests': 'renderLeaveRequestRows',
}


def _module_view_entry(source, key):
    match = re.search(r'\n    ' + re.escape(key) + r': \{(.*?)\n    \}', source, re.S)
    return match.group(1) if match else ''


def _row_cell_count(body):
    """Cells in the renderer's data row template (the <tr> after the last colspan/heading row)."""
    rows = re.findall(r'<tr(?![^>]*action-group-row)[^>]*>(.*?)</tr>', body, re.S)
    rows = [row for row in rows if 'colspan' not in row]
    return len(re.findall(r'<td[\s>]', rows[-1])) if rows else 0


class MyRequestsBatchDSourceTests(unittest.TestCase):
    """Batch D (plans.md): form downloads, compact phone cards, action groups, starting state."""

    source = MyRequestsPageSourceTests.source

    def test_form_link_helper_used_by_every_renderer(self):
        helper = _function_body(self.source, 'formLink')
        self.assertTrue(helper, 'formLink missing')
        for route in ('/download_reimbursement_package?reimbursement_id=',
                      '/download_travel_request_form/${id}?force_download=1',
                      '/download_travel_liquidation_excel/${id}?force_download=1',
                      '/download_cash_advance_liquidation_excel/',
                      '/download_leave_request/'):
            self.assertIn(route, helper, route)
        self.assertIn('item.liquidation_id', helper)
        self.assertNotIn('target="_blank"', helper)
        for name in MODULE_RENDERERS.values():
            self.assertIn('formLink(', _function_body(self.source, name), name)
        self.assertNotIn('fa-file-zipper', self.source)

    def test_no_requester_and_headers_match_cells(self):
        for key, renderer in MODULE_RENDERERS.items():
            entry = _module_view_entry(self.source, key)
            headers = re.search(r"headers: \[(.*?)\]", entry).group(1)
            self.assertNotIn("'Requester'", headers, key)
            self.assertNotIn("'Details'", headers, key)
            self.assertEqual(headers.count("'"), 14, key)  # seven headings
            self.assertEqual(_row_cell_count(_function_body(self.source, renderer)), 7, renderer)
        self.assertNotIn('colspan="8"', self.source)

    def test_action_group_headings_and_subtitle(self):
        body = _function_body(self.source, 'renderActionRows')
        self.assertIn('class="action-group-row"', body)
        self.assertIn('scope="colgroup"', body)
        subtitle = _function_body(self.source, 'actionSubtitle')
        self.assertIn('your action', subtitle)
        self.assertIn('to confirm when received', subtitle)
        self.assertNotIn('item(s) waiting on you', self.source)
        self.assertIn('.action-group-row', self.source)

    def test_compact_phone_cards(self):
        for key in MODULE_RENDERERS:
            self.assertIn('phoneHidden: [', _module_view_entry(self.source, key), key)
        self.assertIn("'cell-phone-hidden'", _function_body(self.source, 'labelQueueCells'))
        self.assertIn('td.cell-phone-hidden{ display: none; }', self.source)

    def test_reference_trimmed(self):
        for name in ('renderTravelRequestRows', 'renderCashAdvanceRows'):
            body = _function_body(self.source, name)
            self.assertIn('refLabel !== recordLabel', body, name)
            self.assertIn('reference-purpose', body, name)
        self.assertIn('-webkit-line-clamp: 2', self.source)

    def test_starting_state_is_action_tab(self):
        markup = self.source.split('<script>')[0]
        self.assertIn('id="activeQueueTitle">Needs your action</h2>', markup)
        self.assertIn('id="kpiPendingLabel">To fix</span>', markup)
        self.assertIn('class="dash-segment d-none" id="accountingStatusFilter"', markup)
        self.assertNotIn('Waiting for payment</span>', markup)
        self.assertIn('<th>What to do</th>', markup)

    def test_kept_functions_guard(self):
        for name in ('selectAccountingModule', 'setAccountingTab', 'renderActionRows', 'actionButton',
                     'labelQueueCells', 'openPaidModal', 'openTravelCompletedConfirm',
                     'openTravelLiquidationCompleteModal', 'openCashAdvanceLiquidationCompleteModal',
                     'openCashAdvanceLiquidationDraft', 'postAccountingAction', 'readAccountingJson',
                     'fetchAccountingWithTimeout', 'showDialogError', 'setAccountingActionBusy'):
            self.assertRegex(self.source, r'function\s+' + name + r'\s*\(', name)


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
