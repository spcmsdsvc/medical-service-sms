"""Travel and Cash Advance Liquidation scan fixes (plans.md, 4 batches, 2026-10-15)."""
import pathlib
import unittest
from datetime import date, timedelta
from types import SimpleNamespace

try:
    import app as app_module
except Exception:
    app_module = None


ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / 'app.py').read_text(encoding='utf-8')
BASE = (ROOT / 'templates' / '_liquidation_base.html').read_text(encoding='utf-8')
TRAVEL = (ROOT / 'templates' / 'travel_liquidation.html').read_text(encoding='utf-8')


def block(source, start, end):
    begin = source.index(start)
    return source[begin:source.index(end, begin + len(start))]


class LiquidationUiFixTests(unittest.TestCase):
    """Batch 1."""

    def test_clear_form_is_outline_danger_with_dark_rule(self):
        self.assertIn('class="btn btn-outline-danger fw-bold" id="clearDraftTopBtn"', BASE)
        self.assertNotIn('btn-outline-warning', BASE)
        self.assertIn(':root[data-app-theme="dark"] .liq-dock .btn-outline-danger{--bs-btn-color:#f1aeb5;', BASE)

    def test_dark_amounts_and_required_text(self):
        self.assertIn(':root[data-app-theme="dark"] .liq-summary .is-shimadzu .amount,:root[data-app-theme="dark"] .liq-readiness .blocking{color:#fdba74;}', BASE)
        self.assertIn(':root[data-app-theme="dark"] .liq-summary .is-employee .amount{color:#86efac;}', BASE)

    def test_phone_taps_reach_dock_readiness_receipts_and_toasts(self):
        self.assertIn('.liq-page .btn,.liq-dock .btn,.liq-ready-btn,.liq-readiness .btn{min-height:44px;}', BASE)
        self.assertIn('.liq-chip-delete,.liq-toast button{min-width:44px;min-height:44px;}', BASE)

    def test_locked_records_hide_the_readiness_pill(self):
        buttons = block(BASE, 'function updateWorkflowButtons', '\n}')
        self.assertIn("document.getElementById('liqReadyBtn').hidden = !isEditable();", buttons)
        self.assertIn('toggleLiquidationReadiness(false)', buttons)

    def test_load_error_state(self):
        load = block(BASE, 'async function loadLiquidation', '\n}')
        self.assertIn('colspan="5"', load)
        self.assertNotIn('colspan="6"', BASE)
        self.assertIn('Unavailable', load)

    def test_new_row_date_uses_manila(self):
        modal = block(BASE, 'function openRowModal', '\n}')
        self.assertIn("timeZone: 'Asia/Manila'", modal)
        self.assertNotIn('toISOString().slice(0, 10)', modal)


class LiquidationDataSafetyTests(unittest.TestCase):
    """Batch 2."""

    @unittest.skipIf(app_module is None, 'app import unavailable')
    def test_recalculators_leave_locked_records_alone(self):
        stamp = object()
        for func in (app_module.travel_liquidation_recalculate_totals, app_module.cash_advance_liquidation_recalculate_totals):
            for status in ('Submitted', 'Approved', 'Completed'):
                record = SimpleNamespace(id=1, status=status, updated_at=stamp, cash_advance_amount=10, total_actual_expenses=7)
                self.assertIs(func(record), record)
                self.assertIs(record.updated_at, stamp)
                self.assertEqual((record.cash_advance_amount, record.total_actual_expenses), (10, 7))

    def test_travel_clear_deletes_files_after_commit_and_keeps_status(self):
        clear = block(APP_SOURCE, 'def clear_travel_liquidation', 'def travel_liquidation_submit_notification_approvers')
        self.assertLess(clear.index('db.session.commit()'), clear.index('managed_storage_delete('))
        self.assertNotIn("liquidation.status = 'Draft'", clear)
        self.assertNotIn('liquidation.approval_remarks = None', clear)
        self.assertNotIn("status_from='Draft'", clear)
        self.assertIn("'cleanup_warning'", clear)

    def test_rate_saves_are_queued_not_dropped(self):
        self.assertIn('rateSaveQueue = rateSaveQueue.then(', TRAVEL)
        self.assertNotIn("runBusy('', '', async () => {\n        const data = await liqFetch(liqUrl('save_*_currency_rate'", TRAVEL)
        rate = block(APP_SOURCE, 'def save_travel_liquidation_currency_rate', '@app.route')
        self.assertIn('Enter a USD to PHP rate above 0 for the PHP receipts.', rate)


class LiquidationValidationTests(unittest.TestCase):
    """Batch 3."""

    @unittest.skipIf(app_module is None, 'app import unavailable')
    def test_row_parser_limits(self):
        parse = app_module.travel_liquidation_parse_row_payload
        ok = {'particulars': 'Taxi', 'actual_amount': 100}
        too_late = (app_module.get_manila_today() + timedelta(days=400)).isoformat()
        for bad in (
            dict(ok, expense_date='2026-13-45'),
            dict(ok, expense_date='1900-01-01'),
            dict(ok, expense_date=too_late),
            dict(ok, actual_amount=10_000_001),
            dict(ok, remarks='r' * 501),
        ):
            with self.assertRaises(ValueError, msg=str(bad)[:60]):
                parse(bad)
            with self.assertRaises(ValueError, msg=str(bad)[:60]):
                app_module.cash_advance_liquidation_parse_row_payload(bad)
        data = parse(dict(ok, expense_date='2026-06-19', remarks='r' * 500, actual_amount=10_000_000))
        self.assertEqual(data['expense_date'], date(2026, 6, 19))
        self.assertEqual(len(data['remarks']), 500)
        self.assertIsNone(parse(ok)['expense_date'])

    def test_modal_input_limits(self):
        self.assertIn('max="10000000" id="rowAmount"', BASE)
        self.assertIn('id="rowParticulars" class="form-control" maxlength="255"', BASE)
        self.assertIn('id="rowRemarks" class="form-control" maxlength="500"', BASE)

    def test_cash_advance_row_errors_are_400(self):
        for name, nxt in (('def add_cash_advance_liquidation_row(', 'def save_cash_advance_liquidation_row('),
                          ('def save_cash_advance_liquidation_row(', 'def delete_cash_advance_liquidation_row(')):
            body = block(APP_SOURCE, name, nxt)
            self.assertIn("'error': str(exc)}), 400", body)
            self.assertNotIn("'error': str(exc)}), 409", body)

    def test_submit_checks_signature_on_the_server(self):
        for name in ('def submit_travel_liquidation(', 'def submit_cash_advance_liquidation('):
            submit = block(APP_SOURCE, name, '@app.route')
            check = submit.index('if not get_liquidation_submitter_signature_data(liquidation):')
            self.assertLess(check, submit.index('try:'))
            self.assertIn('LIQUIDATION_SIGNATURE_REQUIRED_MESSAGE}), 400', submit)

    def test_delete_all_missing_record_is_404(self):
        body = block(APP_SOURCE, 'def delete_all_travel_liquidation_receipts', '@app.route')
        self.assertLess(body.index('if not liquidation:'), body.index('can_edit_travel_liquidation(liquidation)'))
        self.assertIn("not found or not accessible.'}), 404", body)

    def test_edit_gates_have_no_admin_override(self):
        travel = block(APP_SOURCE, 'def can_edit_travel_liquidation', '\ndef ')
        self.assertNotIn('is_admin_authorized()', travel)
        cash = block(APP_SOURCE, 'def can_edit_cash_advance_liquidation', '\ndef ')
        self.assertIn('cash_advance_liquidation_get_for_requester_page(liquidation_id=liquidation.id)', cash)
        self.assertNotIn('can_current_user_manage_cash_advance_liquidation(liquidation)', cash)


class LiquidationHeaderAndCleanupTests(unittest.TestCase):
    """Batch 4."""

    def test_request_page_header(self):
        self.assertIn("css/app-dashboard.css') }}?v=17", BASE)
        self.assertIn('<div class="liq-page request-page" id="liq-shell"', BASE)
        self.assertIn('<header class="dash-page-header">', BASE)
        for token in ('liq-hero', 'liq-eyebrow', '#0f5132', '#198754', '1400px', 'btn-warning'):
            self.assertNotIn(token, BASE, token)
        for element_id in ('liqTitle', 'liqStatus', 'liqSubtitle', 'previewTemplateTopBtn', 'downloadFormBtn'):
            self.assertIn(f'id="{element_id}"', BASE, element_id)

    def test_submit_is_accent_and_add_modal_is_green(self):
        self.assertIn('class="btn btn-primary fw-bold" id="submitLiquidationTopBtn"', BASE)
        self.assertIn("classList.toggle('is-add', !row)", block(BASE, 'function openRowModal', '\n}'))
        self.assertIn('#rowModal .modal-header.is-add{background:var(--bs-success);', BASE)

    def test_plain_branch_wording(self):
        self.assertIn('<div class="liq-label">Branch</div>', BASE)
        self.assertIn('From your Engineer profile.', BASE)
        self.assertNotIn("request creator's Engineer profile", BASE)

    def test_unused_routes_are_gone(self):
        for route in ('create_travel_liquidation_draft', 'create_travel_request_liquidation_draft',
                      'get_travel_liquidation_draft', 'get_travel_request_liquidation_draft',
                      'get_cash_advance_liquidation_draft', 'get_my_cash_advance_liquidation',
                      'mark_travel_request_ready_for_liquidation', 'travel_request_ready_for_liquidation'):
            self.assertNotIn(f"@app.route('/{route}/", APP_SOURCE, route)
            self.assertNotIn(f"    '/{route}',\n", APP_SOURCE, route)
        self.assertIn("@app.route('/mark_travel_completed_ready_for_liquidation/", APP_SOURCE)
        self.assertIn("@app.route('/open_travel_liquidation_excel/", APP_SOURCE)


if __name__ == '__main__':
    unittest.main()
