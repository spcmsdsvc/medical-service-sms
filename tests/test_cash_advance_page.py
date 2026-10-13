"""Cash Advance Batch 2: page behaviour source checks (busy lock, deep link, read-only, counts, buttons)."""

import os
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE_PATH = pathlib.Path(os.environ.get('CASH_ADVANCE_TEMPLATE', ROOT / 'templates' / 'cash_advance.html'))
TEMPLATE = TEMPLATE_PATH.read_text(encoding='utf-8')


def function_body(name):
    match = re.search(rf'(?:async )?function {name}\(', TEMPLATE)
    if not match:
        raise AssertionError(f'{name} not defined')
    start = match.start()
    next_fn = re.search(r'\n    (?:async )?function \w+\(', TEMPLATE[start + 1:])
    return TEMPLATE[start:start + 1 + next_fn.start()] if next_fn else TEMPLATE[start:]


class CashAdvancePageTests(unittest.TestCase):
    def test_busy_lock_guards_each_entry_point(self):
        self.assertIn('let cashAdvanceBusy = false;', TEMPLATE)
        for name in ('saveCashAdvanceDraft', 'submitCashAdvance', 'uploadCashAdvanceAttachments', 'deleteCashAdvanceDraft'):
            body = function_body(name)
            self.assertIn('if (cashAdvanceBusy', body, name)
            self.assertIn('finally', body, name)
        # Submit and upload save through the unguarded core, so they cannot deadlock on the flag.
        self.assertIn('saveCashAdvanceDraftCore(true)', function_body('submitCashAdvanceCore'))
        self.assertIn('saveCashAdvanceDraftCore(true)', function_body('uploadCashAdvanceAttachments'))
        self.assertNotIn('cashAdvanceBusy', function_body('saveCashAdvanceDraftCore'))

    def test_deep_link_reads_cash_advance_id(self):
        self.assertRegex(TEMPLATE, r"URLSearchParams\(window\.location\.search\)\.get\('cash_advance_id'\)")
        self.assertIn('openCashAdvance(deepLinkId)', TEMPLATE)

    def test_withdraw_only_on_submitted(self):
        self.assertIn("statusKey === 'submitted' ? `<button", TEMPLATE)
        self.assertNotIn("statusKey.includes('submitted') ? `<button", TEMPLATE)

    def test_edit_state_applied_from_record_and_clear(self):
        body = function_body('applyCashAdvanceEditState')
        for field in ('cashAmountRequested', 'cashLiquidationDays', 'cashPurpose'):
            self.assertIn(field, body)
        self.assertIn('neededDate.disabled = !editable', body)
        self.assertIn("show('cashSaveDraftBtn', editable)", body)
        self.assertIn("show('cashSubmitBtn', editable)", body)
        self.assertIn('applyCashAdvanceEditState(item)', function_body('applyCashAdvanceRecord'))
        self.assertIn('applyCashAdvanceEditState(null)', function_body('clearCashAdvanceForm'))
        self.assertNotIn('lock_reason', TEMPLATE)

    def test_counts_have_rejected_bucket(self):
        self.assertIn('id="cashRejectedCount"', TEMPLATE)
        body = function_body('updateCashCounts')
        self.assertIn('counts.rejected += 1', body)
        self.assertIn("key === 'draft'", body)
        self.assertNotIn('else counts.draft += 1', body)

    def test_liquidation_button(self):
        self.assertIn('id="cashLiquidationBtn"', TEMPLATE)
        body = function_body('openOrCreateCashAdvanceLiquidation')
        self.assertIn('create_liquidation_url', body)
        self.assertIn('liquidation_url', body)
        self.assertIn('openOrCreateCashAdvanceLiquidation(${Number(item.id) || 0})', TEMPLATE)

    def test_delete_draft_and_clear_confirm(self):
        self.assertIn('id="cashDeleteDraftBtn"', TEMPLATE)
        body = function_body('deleteCashAdvanceDraft')
        self.assertIn('/delete_cash_advance_draft/', body)
        self.assertIn('window.confirm(`Delete draft', body)
        self.assertIn("show('cashDeleteDraftBtn', hasId && status === 'draft')", function_body('applyCashAdvanceEditState'))
        clear = function_body('clearCashAdvanceForm')
        self.assertIn("window.confirm('Clear the form? Unsaved changes are lost.')", clear)
        self.assertIn('function clearCashAdvanceForm(silent)', clear)

    def test_kept_functions(self):
        for name in ('cashEscape', 'cashToast', 'getCashCsrfToken', 'todayInputValue', 'formatMoney',
                     'isCashAdvanceEditable', 'cashFileSize', 'renderCashAdvanceAttachments',
                     'updateCashAttachmentSelection', 'setCashStatus', 'collectCashAdvancePayload',
                     'validateCashAdvancePayload', 'parseCashJson', 'saveCashAdvanceDraft', 'submitCashAdvance',
                     'applyCashAdvanceRecord', 'clearCashAdvanceForm', 'uploadCashAdvanceAttachments',
                     'deleteCashAdvanceAttachment', 'deleteAllCashAdvanceAttachments', 'renderCashAdvanceList',
                     'updateCashCounts', 'loadCashAdvances', 'openCashAdvance', 'renderCashAdvanceNotifications',
                     'loadCashAdvanceNotifications', 'markCashAdvanceNotificationRead',
                     'closeCashAdvanceNotification', 'openCashAdvanceNotification',
                     'markAllCashAdvanceNotificationsRead'):
            self.assertRegex(TEMPLATE, rf'(?:async )?function {name}\(', name)
        for handler in re.findall(r'onclick="([A-Za-z]\w*)\(', TEMPLATE):
            if handler in ('openEmbeddedLprModal', 'openRequestRecall', 'document'):
                continue
            self.assertRegex(TEMPLATE, rf'function {handler}\(', handler)
        for element_id in ('cashAdvanceId', 'cashAdvanceNo', 'cashAdvanceStatus', 'cashNeededDate',
                           'cashAmountRequested', 'cashLiquidationDays', 'cashRequestDate', 'cashPurpose',
                           'cashFormCard', 'cashAdvanceList', 'cashNotificationList', 'cashDraftCount',
                           'cashSubmittedCount', 'cashApprovedCount', 'cashReadyCount'):
            self.assertIn(f'id="{element_id}"', TEMPLATE)
        self.assertIn("{% include '_request_recall_modal.html' %}", TEMPLATE)


if __name__ == '__main__':
    unittest.main()
