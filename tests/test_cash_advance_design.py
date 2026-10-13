"""Cash Advance Batches 3-4: design system and dark mode source checks."""

import os
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE_PATH = pathlib.Path(os.environ.get('CASH_ADVANCE_TEMPLATE', ROOT / 'templates' / 'cash_advance.html'))
TEMPLATE = TEMPLATE_PATH.read_text(encoding='utf-8')
STYLE = TEMPLATE[TEMPLATE.index('<style>'):TEMPLATE.index('</style>')]

KEPT_FUNCTIONS = (
    'cashEscape', 'cashToast', 'getCashCsrfToken', 'todayInputValue', 'formatMoney',
    'isCashAdvanceEditable', 'cashFileSize', 'renderCashAdvanceAttachments',
    'updateCashAttachmentSelection', 'setCashStatus', 'collectCashAdvancePayload',
    'validateCashAdvancePayload', 'parseCashJson', 'saveCashAdvanceDraft', 'submitCashAdvance',
    'applyCashAdvanceRecord', 'clearCashAdvanceForm', 'uploadCashAdvanceAttachments',
    'deleteCashAdvanceAttachment', 'deleteAllCashAdvanceAttachments', 'renderCashAdvanceList',
    'updateCashCounts', 'loadCashAdvances', 'openCashAdvance', 'renderCashAdvanceNotifications',
    'loadCashAdvanceNotifications', 'markCashAdvanceNotificationRead', 'closeCashAdvanceNotification',
    'openCashAdvanceNotification', 'markAllCashAdvanceNotificationsRead', 'deleteCashAdvanceDraft',
    'openOrCreateCashAdvanceLiquidation', 'applyCashAdvanceEditState', 'cashStatusSentence',
)
KEPT_IDS = (
    'cashAdvanceId', 'cashAdvanceNo', 'cashAdvanceStatus', 'cashNeededDate', 'cashAmountRequested',
    'cashLiquidationDays', 'cashRequestDate', 'cashPurpose', 'cashFormCard', 'cashAdvanceList',
    'cashNotificationList', 'cashAttachmentFiles', 'cashAttachmentList', 'cashAttachmentSelection',
    'cashSelectAttachmentsBtn', 'cashUploadAttachmentsBtn', 'cashDeleteAllAttachmentsBtn',
    'cashDraftCount', 'cashSubmittedCount', 'cashApprovedCount', 'cashReadyCount', 'cashRejectedCount',
    'cashStatusPill', 'cashFormStatusText', 'cashClearFormBtn', 'cashDeleteDraftBtn',
    'cashLiquidationBtn', 'cashSaveDraftBtn', 'cashSubmitBtn',
)


class CashAdvanceKeptFunctionsTests(unittest.TestCase):
    def test_kept_functions_ids_and_onclick_targets(self):
        for name in KEPT_FUNCTIONS:
            self.assertRegex(TEMPLATE, rf'(?:async )?function {name}\(', name)
        for element_id in KEPT_IDS:
            self.assertIn(f'id="{element_id}"', TEMPLATE, element_id)
        defined = set(re.findall(r'function (\w+)\(', TEMPLATE)) | {'openEmbeddedLprModal', 'openRequestRecall', 'document'}
        for target in re.findall(r'onclick="(?:event\.preventDefault\(\); )?(\w+)\(', TEMPLATE):
            self.assertIn(target, defined, target)


class CashAdvanceBatch3DesignTests(unittest.TestCase):
    def test_page_header_replaces_hero(self):
        self.assertIn('class="dash-page-header"', TEMPLATE)
        self.assertIn("css/app-dashboard.css') }}?v=17", TEMPLATE)
        self.assertNotIn('cash-hero', TEMPLATE)
        self.assertNotIn('linear-gradient', TEMPLATE)

    def test_form_comes_first(self):
        form = TEMPLATE.index('id="cashFormCard"')
        self.assertLess(form, TEMPLATE.index('id="cashNotificationCard"'))
        self.assertLess(form, TEMPLATE.index('id="cashDraftCount"'))
        self.assertLess(form, TEMPLATE.index('id="cashAdvanceList"'))
        self.assertIn('id="cashNotificationCard" hidden', TEMPLATE)
        self.assertIn('setCashNotificationCardVisible(unreadItems.length > 0)', TEMPLATE)

    def test_stat_cards(self):
        self.assertEqual(TEMPLATE.count('class="dash-stat"'), 5)
        self.assertIn('class="dash-stats cash-stats"', TEMPLATE)
        self.assertNotRegex(TEMPLATE, r'-(?:stat|kpi)-value')
        self.assertIn("classList.toggle('dashboard-metric-alert', counts.rejected > 0)", TEMPLATE)

    def test_weights_radii_and_shadows(self):
        weights = [int(w) for w in re.findall(r'font-weight:\s*(\d+)', TEMPLATE)]
        self.assertTrue(weights)
        self.assertLessEqual(max(weights), 600)
        radii = set(re.findall(r'border-radius:\s*([^;]+);', TEMPLATE))
        self.assertLessEqual(radii, {'6px', '10px', '16px', '999px', '50%'}, radii)
        self.assertNotIn('rgba(37, 99, 235', TEMPLATE)
        self.assertNotIn('#facc15', TEMPLATE)
        self.assertNotIn('cash-btn-warning', TEMPLATE)

    def test_buttons_and_focus(self):
        self.assertRegex(STYLE, r'\.cash-btn-danger,\s*\n\s*\.cash-btn-danger-outline\s*\{')
        self.assertRegex(TEMPLATE, r'class="cash-btn cash-btn-primary" id="cashSubmitBtn"')
        self.assertRegex(STYLE, r'\.cash-field input:focus-visible[^{]*\{[^}]*0 0 0 \.25rem var\(--app-focus\)')
        order = [TEMPLATE.index(f'id="{i}"') for i in ('cashClearFormBtn', 'cashDeleteDraftBtn', 'cashSaveDraftBtn', 'cashSubmitBtn')]
        self.assertEqual(order, sorted(order))

    def test_duplicates_and_logbook_numbers(self):
        self.assertIn('<input type="hidden" id="cashAdvanceStatus"', TEMPLATE)
        self.assertIn('<input type="hidden" id="cashRequestDate"', TEMPLATE)
        self.assertNotIn('<label for="cashAdvanceStatus">', TEMPLATE)
        self.assertIn('id="cashRequestDateText"', TEMPLATE)
        self.assertIn('id="cashAdvanceNo" class="logbook-ref"', TEMPLATE)
        self.assertIn('<span class="logbook-ref">${cashEscape(item.cash_advance_no', TEMPLATE)
        self.assertNotRegex(TEMPLATE, r'cash-section-title"><i ')
        self.assertNotIn('text-warning', TEMPLATE)


class CashAdvanceBatch4DarkTests(unittest.TestCase):
    DARK = ':root[data-app-theme="dark"]'

    def dark_rule(self, selector):
        return re.search(re.escape(self.DARK) + r'[^{]*' + re.escape(selector) + r'[^{]*\{', STYLE)

    def test_dark_pills(self):
        for variant in ('', '.draft', '.submitted', '.approved', '.returned'):
            self.assertTrue(self.dark_rule('.cash-status-pill' + variant), variant or 'base')

    def test_dark_buttons_and_toasts(self):
        for selector in ('.cash-btn-danger-outline', '.cash-btn-danger', '.cash-toast', '.cash-toast.ok',
                         '.cash-toast.error', '.cash-toast.warn', '.cash-toast-icon'):
            self.assertTrue(self.dark_rule(selector), selector)
        self.assertNotIn('#facc15', TEMPLATE)


if __name__ == '__main__':
    unittest.main()
