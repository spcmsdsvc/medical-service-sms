"""Leave Request Batches 3 and 4: design system and dark mode (source checks)."""

import os
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGE_PATH = pathlib.Path(os.environ.get('LEAVE_PAGE_TEMPLATE') or ROOT / 'templates' / 'leave_request.html')
PAGE = PAGE_PATH.read_text(encoding='utf-8')
STYLE = PAGE.split('<style>', 1)[1].split('</style>', 1)[0]
SCRIPT = PAGE.split('<script>', 1)[1].split('</script>', 1)[0]
DARK = '\n'.join(line for line in STYLE.splitlines() if ':root[data-app-theme="dark"]' in line)


class LeaveKeptFunctionsTests(unittest.TestCase):
    def test_kept_functions_ids_and_onclick_targets(self):
        for name in ('showLeave', 'statusClass', 'applyLeave', 'checkConflicts', 'loadLeaveRequests',
                     'clearLeaveForm', 'saveLeaveDraft', 'submitLeave', 'openLeave', 'applyLeaveEditState'):
            self.assertRegex(SCRIPT, r'(?m)^(?:async )?function ' + name + r'\(', name)
        targets = set(re.findall(r'onclick="([A-Za-z_]\w*)\(', PAGE)) | set(re.findall(r'onclick=\\?"([A-Za-z_]\w*)\(', SCRIPT))
        for name in targets - {'openRequestRecall'}:
            self.assertRegex(SCRIPT, r'(?m)^(?:async )?function ' + name + r'\(', name)
        for element_id in ('leaveStatus', 'leaveList', 'leaveFormCard', 'leaveSubmitBtn', 'leaveDeleteBtn',
                           'leavePreviewBtn', 'leaveDownloadBtn', 'leaveDeleteAllBtn', 'leaveFormToFollowBtn'):
            self.assertEqual(PAGE.count(f'id="{element_id}"'), 1, element_id)


class LeaveBatch3DesignTests(unittest.TestCase):
    def test_page_header_replaces_hero(self):
        self.assertNotIn('leave-hero', PAGE)
        self.assertIn('<div class="leave-page request-page">', PAGE)
        self.assertIn("css/app-dashboard.css') }}?v=17", PAGE)
        self.assertRegex(PAGE, r'<h1 class="dash-page-h1">Leave Request[^\n]*id="leaveStatus"')
        self.assertIn('id="leaveNewRequestBtn" type="button" class="btn btn-outline-primary" onclick="clearLeaveForm()"', PAGE)
        self.assertNotRegex(STYLE, r'\.leave-page\{[^}]*max-width')

    def test_form_comes_first(self):
        self.assertLess(PAGE.index('id="leaveFormCard"'), PAGE.index('id="leaveAttachments"'))
        self.assertLess(PAGE.index('id="leaveAttachments"'), PAGE.index('id="leaveList"'))

    def test_weights_radii_and_accent(self):
        self.assertTrue(all(int(w) <= 600 for w in re.findall(r'font-weight:\s*(\d+)', STYLE)))
        self.assertEqual(set(re.findall(r'border-radius:\s*([^;}]+)', STYLE)) - {'6px', '10px', '16px', '999px'}, set())
        for value in ('#1769e0', '#168458', '#f4b400', '--app-accent', '#991b1b'):
            self.assertNotIn(value, PAGE)
        self.assertIn('.leave-status.rejected{background:#fde8ea;color:#a1121f}', STYLE)
        self.assertIn('.leave-status.provisional', STYLE)

    def test_buttons(self):
        for old in ('leave-primary', 'leave-success', 'leave-warning', 'leave-secondary'):
            self.assertNotIn(old, PAGE)
        self.assertEqual(PAGE.count('leave-btn leave-btn-primary'), 1)
        self.assertIn('id="leaveSubmitBtn" class="leave-btn leave-btn-primary"', PAGE)
        self.assertIn('id="leavePreviewBtn" class="leave-btn leave-btn-outline" type="button" onclick="previewLeave()" hidden', PAGE)
        self.assertIn('btn.hidden=!saved', SCRIPT)
        actions = PAGE[PAGE.index('<div class="leave-actions-left">'):PAGE.index('id="leaveConflictPanel"')]
        order = [actions.index(f'id="{i}"') for i in ('leaveClearBtn', 'leaveDeleteBtn', 'leaveCheckConflictsBtn',
                                                       'leavePreviewBtn', 'leaveDownloadBtn', 'leaveSaveDraftBtn', 'leaveSubmitBtn')]
        self.assertEqual(order, sorted(order))

    def test_focus_and_labels(self):
        self.assertIn('.leave-field :is(input,select,textarea):focus-visible{border-color:var(--app-primary);box-shadow:0 0 0 .25rem var(--app-focus)}', STYLE)
        self.assertIn('.leave-btn:focus-visible{', STYLE)
        for label in re.findall(r'<label(?: [^>]*)?>.*?</label>', PAGE, re.S):
            if 'for=' not in label:
                self.assertIn('<input', label)
        self.assertIn('aria-label="Download ${escapeLeave(item.filename)}"', SCRIPT)

    def test_phone_overflow_fix_and_logbook_numbers(self):
        self.assertRegex(STYLE, r'\.leave-segment\{position:relative;')
        self.assertRegex(STYLE, r'\.leave-segment input\{position:absolute;width:1px;height:1px;')
        self.assertIn('.leave-segment label{min-height:44px}', STYLE)
        self.assertIn('<span class="logbook-ref">${escapeLeave(item.request_no)}</span>', SCRIPT)



class LeaveBatch4DarkTests(unittest.TestCase):
    def test_dark_pills(self):
        self.assertIn('.leave-status{background:var(--app-surface-raised);color:var(--app-text)}', DARK)
        for variant in ('draft', 'submitted', 'approved', 'rejected', 'form-to-follow', 'provisional', 'superseded'):
            self.assertRegex(DARK, r'\.leave-status\.' + variant + r'[,{)][^{]*?\{?background:rgba\([^)]*\.16\);color:#', variant)

    def test_dark_buttons_and_segment(self):
        self.assertIn('.leave-danger{background:transparent;color:#fca5a5;border-color:rgba(248,113,113,.45)}', DARK)
        self.assertIn('.leave-segment input:checked+label{background:var(--app-surface-raised);color:var(--app-primary-text)}', DARK)

    def test_dark_blocks(self):
        self.assertIn(':is(.leave-check,.leave-notice,.leave-conflicts){background:var(--app-surface);color:var(--app-text)', DARK)
        for tone in ('.leave-notice.ok', '.leave-notice.error', '.leave-notice.info', '.leave-conflicts.good', '.leave-conflicts.bad'):
            self.assertIn(tone, DARK)


if __name__ == '__main__':
    unittest.main()
