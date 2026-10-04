import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / 'app.py').read_text(encoding='utf-8')
TEMPLATE = (ROOT / 'templates' / 'reimbursement.html').read_text(encoding='utf-8')


def function_body(source, name):
    start = source.index(f'function {name}(')
    end = source.find('\n    function ', start + 1)
    async_end = source.find('\n    async function ', start + 1)
    ends = [value for value in (end, async_end) if value != -1]
    return source[start:min(ends) if ends else len(source)]


class ReimbursementPageCleanupTests(unittest.TestCase):
    def test_save_source_is_posted_inside_the_payload(self):
        body = function_body(TEMPLATE, 'reimbursementCaptureSaveEntry')
        payload = body[body.index('payload: {'):body.index('},', body.index('payload: {'))]
        self.assertIn('save_source', payload)

    def test_status_helpers_do_not_toast(self):
        self.assertNotIn('reimToast', function_body(TEMPLATE, 'setReimbursementDraftStatus'))
        self.assertNotIn('reimToast', function_body(TEMPLATE, 'setReimbursementSubmitNotice'))
        self.assertNotIn('style.color', function_body(TEMPLATE, 'setReimbursementDraftStatus'))

    def test_dead_code_and_clear_form_are_gone(self):
        self.assertEqual(TEMPLATE.count('function parseReimbursementJsonResponse('), 1)
        for token in (
            'reimSignatureModal', 'reimClearBtn', 'clearReimbursementForm', 'reimDeleteDraftPanel',
            'lprSavedVersion', 'renderReimbursementReceiptTools', 'uploadReimbursementReceipt(',
            'findSavedManualRow', 'reloadCurrentReimbursementDraftOnly', 'calculateRowTotal',
            "Rodito's", 'style="background:#f8fafc',
        ):
            self.assertNotIn(token, TEMPLATE, token)
        self.assertNotIn("@app.route('/clear_reimbursement_draft'", APP_SOURCE)
        self.assertNotIn("@app.route('/download_reimbursement_form'", APP_SOURCE)

    def test_categories_come_from_one_list(self):
        self.assertIn('REIMBURSEMENT_PAGE_CATEGORIES', APP_SOURCE)
        self.assertEqual(len(re.findall(r"label: 'Car Repair'|'Car Repair'", TEMPLATE)), 0)

    def test_submit_error_hides_exception_text(self):
        self.assertNotIn("f'Unable to submit reimbursement: {exc}'", APP_SOURCE)

    def test_page_loads_on_open_and_downloads_in_page(self):
        self.assertIn('renderReimbursementOverlapNotice', TEMPLATE)
        self.assertIn('URL.createObjectURL', TEMPLATE)
        self.assertNotIn('triggerReimbursementDownload', TEMPLATE)

    def test_release_and_cache_version(self):
        self.assertIn('"2026-10-04-reimbursement-cleanup"', (ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
