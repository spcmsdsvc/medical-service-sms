import pathlib
import unittest

try:
    import app as app_module
except Exception:
    app_module = None


ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / 'app.py').read_text(encoding='utf-8')
BASE = (ROOT / 'templates' / '_liquidation_base.html').read_text(encoding='utf-8')
TRAVEL = (ROOT / 'templates' / 'travel_liquidation.html').read_text(encoding='utf-8')
CASH = (ROOT / 'templates' / 'cash_advance_liquidation.html').read_text(encoding='utf-8')


def block(source, start, end):
    begin = source.index(start)
    return source[begin:source.index(end, begin + len(start))]


class LiquidationServerTests(unittest.TestCase):
    def test_auto_rows_cannot_be_deleted_and_clear_reseeds_them(self):
        delete = block(APP_SOURCE, 'def delete_travel_liquidation_row', 'def upload_travel_liquidation_receipt')
        self.assertIn("getattr(row, 'travel_request_line_id', None)", delete)
        clear = block(APP_SOURCE, 'def clear_travel_liquidation', 'def travel_liquidation_submit_notification_approvers')
        self.assertIn('travel_liquidation_seed_per_diem_airfare_rows(liquidation', clear)

    def test_travel_submit_uses_liquidation_scope_and_reports_branch_errors(self):
        helper = block(APP_SOURCE, 'def travel_liquidation_submit_notification_approvers', '@app.route')
        self.assertIn("('travel_liquidation', 'travel_request', 'all')", helper)
        submit = block(APP_SOURCE, 'def submit_travel_liquidation(', '@app.route')
        self.assertIn('travel_liquidation_submit_notification_approvers(liquidation)', submit)
        self.assertIn('except ValueError as exc:', submit)

    def test_cash_advance_submit_does_not_return_approver_emails(self):
        submit = block(APP_SOURCE, 'def submit_cash_advance_liquidation(', '# F4A5C STANDALONE')
        self.assertNotIn("'email_recipients'", submit)

    @unittest.skipIf(app_module is None, 'app import unavailable')
    def test_zero_amount_rows_are_rejected(self):
        for value in ('0', '', None):
            with self.assertRaises(ValueError):
                app_module.travel_liquidation_parse_row_payload({'amount': value})
            with self.assertRaises(ValueError):
                app_module.cash_advance_liquidation_parse_row_payload({'amount': value})

    def test_cash_advance_clear_route_and_removed_aliases(self):
        self.assertIn("@app.route('/clear_cash_advance_liquidation/<int:liquidation_id>', methods=['POST'])", APP_SOURCE)
        for alias in (
            'clear_travel_liquidation_draft', 'submit_travel_liquidation_for_approval', 'remove_travel_liquidation_row',
            'attach_cash_advance_liquidation_receipt', 'open_cash_advance_liquidation_excel', 'inline_travel_liquidation_rfp',
        ):
            self.assertNotIn(f"@app.route('/{alias}/", APP_SOURCE, alias)


class LiquidationTemplateTests(unittest.TestCase):
    def test_both_pages_extend_the_shared_base(self):
        for page in (TRAVEL, CASH):
            self.assertTrue(page.startswith('{% extends "_liquidation_base.html" %}'))
        self.assertIn('{{ liq_settings|tojson }}', BASE)
        self.assertIn("LIQUIDATION_PAGE_SETTINGS['travel']", APP_SOURCE)
        self.assertIn("LIQUIDATION_PAGE_SETTINGS['cash_advance']", APP_SOURCE)

    def test_reimbursement_parity_features(self):
        for token in ('/get_my_signature', 'liqSignaturePanel', 'readinessItems', 'downloadLiquidationForm',
                      'multiple', 'liqConfirm', 'liqToast', 'liq-dock'):
            self.assertIn(token, BASE, token)

    def test_old_behaviour_and_dead_code_are_gone(self):
        pages = BASE + TRAVEL + CASH
        for token in ('saveDraftTop', 'saveDraftNotice', 'window.confirm', 'S13C', 'F4A5', 'buildTripContext',
                      'heroTripContext', 'namesFromParticipants', 'officialAmountFromSource', 'balance-card', '#064e3b'):
            self.assertNotIn(token, pages, token)

    def test_one_receipts_section_without_per_row_uploads(self):
        for token in ('Uploaded Receipts', 'all_receipts', "liqUrl('upload_*_receipts', LIQUIDATION_ID)", 'renderReceipts'):
            self.assertIn(token, BASE, token)
        for token in ('openReceiptModal', 'receiptModal', 'receiptRowId', 'data-label="Receipts"'):
            self.assertNotIn(token, BASE, token)
        for kind in ('travel', 'cash_advance'):
            upload = block(APP_SOURCE, f'def upload_{kind}_liquidation_receipt(', '@app.route')
            self.assertIn('row_id=None', upload)
            self.assertIn(f"@app.route('/upload_{kind}_liquidation_receipts/<int:liquidation_id>'", APP_SOURCE)
            self.assertNotIn(f"@app.route('/upload_{kind}_liquidation_receipt/", APP_SOURCE)
        self.assertEqual(APP_SOURCE.count("payload['all_receipts'] = ["), 2)
        approvals = (ROOT / 'templates' / 'approvals.html').read_text(encoding='utf-8')
        self.assertEqual(approvals.count('${renderLiquidationReceipts(data.all_receipts)}'), 2)
        self.assertNotIn('row.receipts', block(approvals, 'function renderLiquidationRows', 'function renderLiquidationReceipts'))

    def test_busy_buttons_are_re_enabled_after_each_action(self):
        run_busy = block(BASE, 'async function runBusy', 'function statusMeta')
        self.assertIn('btn.disabled = false', run_busy.split('finally')[1])
        self.assertIn('medical-service-pwa-offline-navigation-v245-liquidation-save-row', APP_SOURCE)

    def test_preview_stays_available_after_submit(self):
        buttons = block(BASE, 'function updateWorkflowButtons', '\n}')
        self.assertNotIn('previewTemplateTopBtn', buttons)
        self.assertNotIn('downloadFormBtn', buttons)

    def test_release_and_cache_version(self):
        self.assertIn('medical-service-pwa-offline-navigation-v240-liquidation-receipts', APP_SOURCE)
        self.assertIn('"2026-10-04-liquidation-receipts"', (ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
