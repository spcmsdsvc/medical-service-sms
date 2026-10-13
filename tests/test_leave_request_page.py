"""Leave Request Batch 2: page behaviour (busy lock, read-only records, confirms, status note, notices)."""

import os
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGE_PATH = pathlib.Path(os.environ.get('LEAVE_PAGE_TEMPLATE') or ROOT / 'templates' / 'leave_request.html')
PAGE = PAGE_PATH.read_text(encoding='utf-8')
SCRIPT = PAGE.split('<script>', 1)[1].split('</script>', 1)[0]


def function_body(name):
    match = re.search(r'^(?:async )?function ' + re.escape(name) + r'\(.*$', SCRIPT, re.M)
    if not match:
        raise AssertionError(f'{name} is not defined')
    return match.group(0)


class LeavePageBehaviourTests(unittest.TestCase):
    def test_busy_lock_wraps_every_action(self):
        self.assertIn('let leaveBusy = false', SCRIPT)
        self.assertIn('leaveBusy=!!on', function_body('setLeaveBusy'))
        for name in ('saveLeaveDraft', 'submitLeave', 'recordFormToFollow', 'uploadLeaveAttachments',
                     'deleteLeaveAttachment', 'deleteAllLeaveAttachments', 'deleteLeaveDraft'):
            body = function_body(name)
            self.assertIn('if(leaveBusy', body, name)
            self.assertIn('setLeaveBusy(true', body, name)
            self.assertIn('finally{setLeaveBusy(false', body, name)
        self.assertIn('leaveJson(await fetch(\'/api/leave-requests/save\'', function_body('saveLeaveDraftCore'))
        self.assertIn('saveLeaveDraftCore(silent)', function_body('saveLeaveDraft'))
        self.assertIn('if(leaveBusy)return', function_body('openLeave'))

    def test_inner_saves_use_the_unguarded_core(self):
        for name in ('submitLeave', 'recordFormToFollow', 'uploadLeaveAttachments'):
            body = function_body(name)
            self.assertIn('saveLeaveDraftCore(true)', body, name)
            self.assertNotIn('saveLeaveDraft(true)', body, name)

    def test_form_to_follow_saves_editable_records_first(self):
        self.assertIn('!currentLeave||currentLeave.editable?await saveLeaveDraftCore(true)', function_body('recordFormToFollow'))

    def test_submit_confirms_before_saving(self):
        body = function_body('submitLeave')
        self.assertLess(body.index('confirm('), body.index('saveLeaveDraftCore'))

    def test_read_only_records_and_delete_label(self):
        body = function_body('applyLeaveEditState')
        for element_id in ('leaveSaveDraftBtn', 'leaveCheckConflictsBtn', 'leaveFormToFollowBtn', 'leaveFiles', 'leaveUploadBtn'):
            self.assertIn(f"'{element_id}'", body)
            self.assertEqual(PAGE.count(f'id="{element_id}"'), 1, element_id)
        self.assertIn("status!=='Provisional'", body)
        self.assertIn('del.hidden=!showDelete', body)
        self.assertIn("status==='Draft'?'Delete Draft':'Delete Request'", body)
        self.assertIn('applyLeaveEditState(editable,item.status)', function_body('applyLeave'))
        self.assertIn("applyLeaveEditState(true,'Draft')", function_body('clearLeaveForm'))
        self.assertIn('.leave-btn[hidden]{display:none}', PAGE)

    def test_status_note_shows_rejection_remarks(self):
        self.assertIn('id="leaveStatusNote"', PAGE)
        body = function_body('leaveStatusSentence')
        self.assertIn('item.approval_remarks', body)
        self.assertIn('item.rejected_by', body)
        for status in ('Rejected', 'Submitted', 'Approved', 'Provisional', 'Form to Follow'):
            self.assertIn(f"status==='{status}'", body)
        self.assertIn('note.textContent=sentence', function_body('renderLeaveStatusNote'))
        self.assertIn('renderLeaveStatusNote(item)', function_body('applyLeave'))

    def test_clear_confirms_unsaved_new_form(self):
        body = function_body('clearLeaveForm')
        self.assertIn("leaveFormDirty()&&!confirm('Discard the unsaved form?')", body)
        self.assertIn('if(currentLeave)return false', function_body('leaveFormDirty'))
        self.assertIn('clearLeaveForm(true)', function_body('deleteLeaveDraft'))
        self.assertIn("addEventListener('DOMContentLoaded',()=>{clearLeaveForm(true)", SCRIPT)

    def test_errors_stay_and_scroll_only_when_needed(self):
        body = function_body('showLeave')
        self.assertIn("if(type!=='error')leaveNoticeTimer=setTimeout", body)
        self.assertIn('getBoundingClientRect', body)


class LeavePageKeptFunctionsTests(unittest.TestCase):
    def test_kept_functions_are_defined(self):
        for name in (
            'csrfToken', 'escapeLeave', 'leaveJson', 'showLeave', 'localDate', 'selectedLeaveDuration',
            'selectedLeavePeriod', 'selectedLeavePartialPosition', 'payload', 'updateDurationControls',
            'updateWeekdayCount', 'updateEmergencyVisibility', 'updateEmergencyNotes', 'statusClass',
            'loadLeaveRequests', 'saveLeaveDraft', 'openLeave', 'applyLeave', 'renderAttachments', 'checkConflicts',
            'recordFormToFollow', 'submitLeave', 'previewLeave', 'downloadLeave', 'uploadLeaveAttachments',
            'deleteLeaveAttachment', 'deleteAllLeaveAttachments', 'deleteLeaveDraft', 'clearLeaveForm',
        ):
            self.assertRegex(SCRIPT, r'(?m)^(?:async )?function ' + name + r'\(', name)

    def test_every_onclick_target_is_defined(self):
        targets = set(re.findall(r'onclick="([A-Za-z_]\w*)\(', PAGE)) | set(re.findall(r'onclick="([A-Za-z_]\w*)\$\{', PAGE))
        targets |= set(re.findall(r'onclick=\\?"([A-Za-z_]\w*)\(', SCRIPT))
        self.assertTrue(targets)
        for name in targets - {'openRequestRecall'}:
            self.assertRegex(SCRIPT, r'(?m)^(?:async )?function ' + name + r'\(', name)
        self.assertIn("openRequestRecall('leave_request'", SCRIPT)
        self.assertIn("{% include '_request_recall_modal.html' %}", PAGE)

    def test_existing_ids_kept(self):
        for element_id in ('leaveStatus', 'leaveList', 'leaveFormCard', 'leaveSubmitBtn', 'leaveDeleteBtn',
                           'leavePreviewBtn', 'leaveDownloadBtn', 'leaveDeleteAllBtn', 'leaveFormToFollowBtn',
                           'leaveNotice', 'leaveConflictPanel', 'leaveAttachments'):
            self.assertEqual(PAGE.count(f'id="{element_id}"'), 1, element_id)


if __name__ == '__main__':
    unittest.main()
