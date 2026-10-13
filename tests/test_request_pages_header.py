"""Request Pages plan: one header, header button placement and page width on
Travel Request, Cash Advance, Reimbursement and Leave Request (source checks)."""

import os
import pathlib
import re
import unittest


ROOT = pathlib.Path(os.environ.get('REQUEST_PAGES_ROOT', pathlib.Path(__file__).resolve().parents[1]))
CSS = (ROOT / 'static' / 'css' / 'app-dashboard.css').read_text(encoding='utf-8')
PAGES = {
    name: (ROOT / 'templates' / f'{name}.html').read_text(encoding='utf-8')
    for name in ('travel_request', 'cash_advance', 'reimbursement', 'leave_request')
}
WRAPPERS = {'travel_request': 'travel-page', 'cash_advance': 'cash-page', 'reimbursement': 'reim-page', 'leave_request': 'leave-page'}
KEPT_FUNCTIONS = {
    'travel_request': ('startNewTravelRequest', 'submitTravelRequest'),
    'cash_advance': ('clearCashAdvanceForm', 'saveCashAdvanceDraft', 'submitCashAdvance'),
    'reimbursement': (
        'expandReimbursementRangeCard', 'collapseReimbursementRangeCard',
        'applyReimbursementStatusUi', 'loadReimbursementRows',
    ),
    'leave_request': ('clearLeaveForm', 'saveLeaveDraft', 'submitLeave'),
}


def page_style(source):
    return source[source.index('<style>'):source.index('</style>')]


class RequestPagesHeaderTests(unittest.TestCase):
    def test_shared_request_page_rule_exists_once(self):
        self.assertEqual(CSS.count('.request-page {'), 1)
        self.assertRegex(CSS, r'\.request-page \{[^}]*max-width:\s*1220px')
        self.assertRegex(
            CSS,
            r'\.request-page \.dash-page-header \{[^}]*flex-direction:\s*column;[^}]*align-items:\s*flex-start',
        )

    def test_each_page_uses_request_page_and_no_local_width(self):
        for name, source in PAGES.items():
            wrapper = WRAPPERS[name]
            with self.subTest(page=name):
                self.assertIn(f'<div class="{wrapper} request-page">', source)
                self.assertIn("css/app-dashboard.css') }}?v=17", source)
                self.assertIn('class="dash-page-header', source)
                for rule in re.findall(rf'\.{wrapper}\s*\{{[^}}]*\}}', page_style(source)):
                    self.assertNotIn('max-width', rule)

    def test_dark_theme_does_not_paint_page_wrappers(self):
        dark = (ROOT / 'static' / 'css' / 'app-dark-pages.css').read_text(encoding='utf-8')
        for wrapper in WRAPPERS.values():
            with self.subTest(wrapper=wrapper):
                self.assertNotRegex(dark, rf'\.{wrapper}\s*[,)]')

    def test_reimbursement_header_chip_and_new_period(self):
        source = PAGES['reimbursement']
        self.assertNotIn('reim-hero', source)
        self.assertIn('id="reimStatusChip" class="reim-status-chip draft"', source)
        self.assertIn('id="reimNewPeriodBtn" onclick="expandReimbursementRangeCard(true)"', source)
        self.assertIn("statusChip.className = `reim-status-chip ${normalized}`", source)
        self.assertIn('body.reim-focus-active .reim-page-header', source)

    def test_kept_functions_and_onclick_handlers_defined(self):
        for name, source in PAGES.items():
            defined = set(re.findall(r'function\s+([A-Za-z_$][\w$]*)\s*\(', source))
            with self.subTest(page=name):
                for fn in KEPT_FUNCTIONS[name]:
                    self.assertIn(fn, defined)
                for handler in re.findall(r'onclick="([A-Za-z_$][\w$]*)\(', source):
                    if handler in ('document', 'event', 'window', 'this'):
                        continue
                    self.assertTrue(
                        handler in defined or re.search(rf'window\.{handler}\s*=', source) or handler in (
                            'openEmbeddedLprModal', 'openRequestRecall',
                        ),
                        f'{name}: {handler} not defined',
                    )


if __name__ == '__main__':
    unittest.main()
