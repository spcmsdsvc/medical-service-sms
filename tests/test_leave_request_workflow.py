import json
import pathlib
import unittest

from leave_feature import leave_request_cc_group_for_branch


ROOT = pathlib.Path(__file__).resolve().parents[1]


class LeaveRequestSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.feature_source = (ROOT / 'leave_feature.py').read_text(encoding='utf-8')
        cls.page_source = (ROOT / 'templates' / 'leave_request.html').read_text(encoding='utf-8')
        cls.timeline_source = (ROOT / 'templates' / 'timeline.html').read_text(encoding='utf-8')
        cls.approval_source = (ROOT / 'templates' / 'approvals.html').read_text(encoding='utf-8')
        cls.settings_source = (ROOT / 'templates' / 'settings.html').read_text(encoding='utf-8')

    def test_page_navigation_and_official_template_exist(self):
        self.assertTrue((ROOT / 'forms' / 'Leave Form.pdf').exists())
        self.assertIn('href="/leave_request"', (ROOT / 'templates' / 'layout.html').read_text(encoding='utf-8'))
        for marker in ('Save Draft', 'Check Conflicts', 'Submit for Approval', 'Record Form to Follow', 'Supporting Attachments'):
            self.assertIn(marker, self.page_source)

    def test_additive_models_and_storage_are_present(self):
        for marker in (
            "__tablename__ = 'leave_request'",
            "__tablename__ = 'leave_request_attachment'",
            "__tablename__ = 'leave_request_audit'",
            "STORAGE_PREFIX_LEAVE_REQUESTS = 'leave_requests'",
            'leave_request_id = db.Column',
        ):
            self.assertIn(marker, self.feature_source if '__tablename__' in marker else self.app_source)

    def test_emergency_calendar_lifecycle_is_duplicate_safe(self):
        for marker in (
            "header.status = 'Form to Follow'",
            "update_calendar(header, 'Pending Approval')",
            "update_calendar(header, 'Approved')",
            "update_calendar(header, 'Unapproved / Rejected')",
            "Shift.query.filter_by(leave_request_id=header.id)",
        ):
            self.assertIn(marker, self.feature_source)
        self.assertIn('Leave Request calendar entries cannot be deleted from Calendar.', self.app_source)
        self.assertIn('Leave Request calendar entries are managed from the Leave Request page.', self.app_source)

    def test_signature_conflict_and_approval_guards_are_present(self):
        self.assertIn('get_user_signature_snapshot(current_user)', self.feature_source)
        self.assertIn("get_assigned_approvers_for_requester(header.user_id, 'leave_request')", self.feature_source)
        self.assertIn('Approval blocked because a new Calendar conflict was found.', self.feature_source)
        self.assertIn("header.user_id != current_user.id", self.feature_source)

    def test_leave_creation_is_strictly_self_service(self):
        self.assertIn('header.user_id == target.id', self.feature_source)
        self.assertIn('Leave Requests can only be created for the logged-in employee.', self.feature_source)
        self.assertIn('LeaveRequest.query.filter_by(user_id=current_user.id)', self.feature_source)
        self.assertNotIn('leaveEngineer', self.page_source)
        self.assertNotIn('leave_can_create_for_others', self.page_source)

    def test_hr_email_settings_and_requester_cc_are_present(self):
        for marker in ('leave_request_hr', 'leave_request_cc', 'leave_request_cc_cebu_davao', 'leave_request_hr_subject'):
            self.assertIn(marker, self.app_source)
        self.assertIn('requester_email(header)', self.feature_source)
        self.assertIn('requester_leave_cc_route(header)', self.feature_source)
        self.assertIn("return 'leave_request_cc_cebu_davao', 'Cebu/Davao'", self.feature_source)
        self.assertIn("return 'leave_request_cc', 'Manila/Main'", self.feature_source)
        self.assertIn('cc_emails=cc_emails', self.feature_source)
        self.assertIn("leave_request: 'Leave Request'", self.settings_source)

    def test_leave_cc_routing_uses_requester_branch(self):
        for branch in ('Cebu', 'Davao', 'BC02', 'BC03', 'Cebu Branch', 'Davao Branch'):
            self.assertEqual(leave_request_cc_group_for_branch(branch)[0], 'leave_request_cc_cebu_davao')
        for branch in ('Manila', 'Main', 'BC01', '', None):
            self.assertEqual(leave_request_cc_group_for_branch(branch)[0], 'leave_request_cc')

    def test_approval_center_and_my_requests_integration(self):
        self.assertIn("moduleKey !== 'leave_request'", self.approval_source)
        self.assertIn('openLeaveApprovalDetail', self.approval_source)
        self.assertIn("activeAccountingModule === 'leave_requests'", (ROOT / 'templates' / 'accounting_center.html').read_text(encoding='utf-8'))
        self.assertIn("'key': 'leave_requests'", self.app_source)

    def test_calendar_leave_types_and_form_to_follow_entry(self):
        self.assertIn('Leave Without Pay', self.timeline_source)
        self.assertIn('openLeaveFormToFollowFromCalendar', self.timeline_source)
        self.assertIn('leave_request_id', self.timeline_source)

    def test_calendar_legacy_leave_is_historical_only(self):
        self.assertIn('updateLegacyLeaveOptionForDate', self.timeline_source)
        self.assertIn("startDate < timelineTodayISO()", self.timeline_source)
        self.assertIn('block_new_calendar_leave_for_current_or_future', self.app_source)
        self.assertIn('must be submitted through Leave Request', self.app_source)

    def test_release_manifest_contains_leave_request(self):
        manifest = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))
        release = next(item for item in manifest['releases'] if item['release_key'] == '2026-07-21')
        self.assertTrue(any(item['item_key'] == '2026-07-21-leave-request' for item in release['items']))

    def test_startup_schema_and_activity_log_classification_are_registered(self):
        self.assertIn('ensure_leave_request_tables()', self.app_source)
        self.assertIn("'Leave Request': {'icon': 'fa-calendar-minus'", self.app_source)
        self.assertIn("if 'leave request' in text or 'form to follow' in text or 'lr-' in text", self.app_source)


if __name__ == '__main__':
    unittest.main()
