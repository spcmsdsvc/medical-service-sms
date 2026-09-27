"""Focused contracts for Activity Log signal quality and reimbursement access."""

import json
import pathlib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import app as app_module


ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / 'app.py').read_text(encoding='utf-8')
ACTIVITY_TEMPLATE = (ROOT / 'templates' / 'activity.html').read_text(encoding='utf-8')
REIMBURSEMENT_TEMPLATE = (ROOT / 'templates' / 'reimbursement.html').read_text(encoding='utf-8')
RELEASES = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))


class ActivityLogClassifierTests(unittest.TestCase):
    def test_screenshot_text_is_workflow_update_success(self):
        action = (
            'Saved reimbursement draft 2026-08-04 to 2026-09-30 '
            '(37 rows, 24 removed; total PHP 18,910.00)'
        )
        self.assertEqual(app_module.classify_activity_action(action), 'Reimbursement')
        self.assertEqual(app_module.classify_activity_verb(action), 'Update')
        self.assertEqual(app_module.classify_activity_severity(action), 'success')

    def test_workflow_entity_wins_over_accounting_destination(self):
        self.assertEqual(
            app_module.classify_activity_action('Sent approved Reimbursement to Accounting'),
            'Reimbursement',
        )

    def test_csv_formula_prefixes_are_neutralized(self):
        for value in ('=SUM(A1)', '+danger', '-danger', '@formula'):
            with self.subTest(value=value):
                self.assertEqual(app_module.safe_activity_csv_cell(value), "'" + value)
        self.assertEqual(app_module.safe_activity_csv_cell('ordinary text'), 'ordinary text')

    def test_removal_rejection_and_return_are_not_failures(self):
        for action, expected_type, expected_severity in (
            ('Removed 2 worksheet rows', 'Delete', 'normal'),
            ('Rejected reimbursement #42', 'Reject', 'warning'),
            ('Returned reimbursement #42 for correction', 'Return', 'warning'),
        ):
            with self.subTest(action=action):
                self.assertEqual(app_module.classify_activity_verb(action), expected_type)
                self.assertEqual(app_module.classify_activity_severity(action), expected_severity)


class ActivityLogImplementationContractTests(unittest.TestCase):
    def test_database_query_and_legacy_routine_controls_are_present(self):
        for token in (
            "include_routine",
            "hidden_routine_count",
            "ActivityLog.timestamp >= datetime.combine(start_date, datetime.min.time())",
            "ActivityLog.timestamp < datetime.combine(end_date + timedelta(days=1), datetime.min.time())",
            "ActivityLog.timestamp.desc(), ActivityLog.id.desc()",
            "activity_group_counts(query, activity_category_expression())",
            "safe_activity_csv_cell(log.action)",
            "query = activity_scope_query(db.session.query(ActivityLog.user))",
        ):
            self.assertIn(token, APP_SOURCE)

    def test_save_source_is_sent_and_internal_saves_are_non_manual(self):
        self.assertIn("save_source: (options && options.save_source)", REIMBURSEMENT_TEMPLATE)
        self.assertIn("saveReimbursementDraft(true, { autosave: true })", REIMBURSEMENT_TEMPLATE)
        self.assertIn("saveReimbursementDraft(false, { transition: true })", REIMBURSEMENT_TEMPLATE)
        self.assertIn("saveReimbursementDraft(true, { background: true })", REIMBURSEMENT_TEMPLATE)
        self.assertIn("saveReimbursementDraft(false, { manual: true })", REIMBURSEMENT_TEMPLATE)
        self.assertIn("if header_was_created or save_source == 'manual':", APP_SOURCE)

    def test_activity_page_has_routine_toggle_and_accessible_async_states(self):
        for token in (
            'id="filter-include-routine"',
            'for="filter-include-routine"',
            'id="activity-page-status"',
            'aria-live="polite"',
            'scope="col"',
            'activityLoadController.abort()',
            'Retry',
            'Leave Request',
            'Stock Inventory',
        ):
            self.assertIn(token, ACTIVITY_TEMPLATE)

    def test_download_authorization_is_owner_or_routed_approver(self):
        header = SimpleNamespace(user_id=7)
        owner = SimpleNamespace(id=7, is_authenticated=True)
        other = SimpleNamespace(id=9, is_authenticated=True)
        self.assertTrue(app_module.can_download_reimbursement_header(header, owner))
        with patch.object(app_module, 'can_user_approve_reimbursement_header', return_value=False):
            self.assertFalse(app_module.can_download_reimbursement_header(header, other))
        with patch.object(app_module, 'can_user_approve_reimbursement_header', return_value=True):
            self.assertTrue(app_module.can_download_reimbursement_header(header, other))

    def test_release_entry_exists_and_cache_marker_is_bumped(self):
        release = next(
            item for item in RELEASES['releases']
            if item['release_key'] == '2026-09-27-activity-log-signal-quality'
        )
        self.assertTrue(release['is_published'])
        self.assertTrue(any(item['category'] == 'Activity Log' for item in release['items']))
        self.assertIn('medical-service-pwa-offline-navigation-v204-activity-log', APP_SOURCE)


if __name__ == '__main__':
    unittest.main()
