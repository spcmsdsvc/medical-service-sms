"""Focused contracts for Activity Log signal quality and reimbursement access."""

import json
import pathlib
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, select

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


class ActivityLogRuleParityTests(unittest.TestCase):
    """The SQL filters and counts must classify exactly like the badges."""

    SAMPLES = (
        'Generated online TSR PDF and completed schedule scope',
        'Saved TSR draft for Davao Doctors Hospital',
        'Added calendar schedule: PM on 2026-05-22 | Client: ABC Hospital | Product: CT (123)',
        'Moved schedule #12 to 2026-06-01',
        'Removed 2 worksheet rows',
        'Sent approved Reimbursement to Accounting',
        'Marked reimbursement #4 as paid',
        'Failed to send Travel Request PDF to Accounting',
        'Returned Cash Advance Liquidation CAL-0003 for correction',
        'Submitted Leave Request LR-0007',
        'Updated stock inventory count',
        'Sent schedule email notification to Cebu team',
        'Admin forced password change for: hanna',
        'Approved Calibration Report & Certificate 2026-0604-23425',
        'Updated appearance preference: graphite / purple',
        'Exported activity log report',
        'Modified details for client: Allied Care Experts (ACE)',
        'Updated approval route for Travel Request',
        'Something unrelated happened',
    )

    def test_sql_expressions_match_python_classifiers(self):
        engine = create_engine('sqlite://')
        table = app_module.ActivityLog.__table__
        table.create(engine)
        with engine.begin() as conn:
            conn.execute(table.insert(), [
                {'user': 'Tester', 'action': action, 'timestamp': datetime(2026, 10, 3, 9, 0)}
                for action in self.SAMPLES
            ])
            rows = conn.execute(select(
                table.c.action,
                app_module.activity_category_expression(),
                app_module.activity_action_expression(),
                app_module.activity_severity_expression(),
                app_module.activity_routine_expression(),
            )).all()
        for action, category, verb, severity, routine in rows:
            with self.subTest(action=action):
                self.assertEqual(category, app_module.classify_activity_action(action))
                self.assertEqual(verb, app_module.classify_activity_verb(action))
                self.assertEqual(severity, app_module.classify_activity_severity(action))
                self.assertEqual(bool(routine), action.startswith('Updated appearance preference:'))
        self.assertEqual(rows[0][1], 'TSR')
        self.assertIn('Leave Request', app_module.ACTIVITY_CATEGORIES)
        self.assertIn('Stock Inventory', app_module.ACTIVITY_CATEGORIES)

    def test_theme_changes_are_not_logged(self):
        self.assertNotIn('log_activity(f"Updated appearance preference', APP_SOURCE)

    def test_row_dates_are_plain(self):
        log = SimpleNamespace(id=1, user='Kent', action='Added client: X', timestamp=datetime(2026, 10, 3, 9, 5))
        self.assertEqual(app_module.activity_log_to_dict(log, datetime(2026, 10, 3).date())['date'], 'Today')
        self.assertEqual(app_module.activity_log_to_dict(log, datetime(2026, 10, 4).date())['date'], 'Yesterday')
        row = app_module.activity_log_to_dict(log, datetime(2026, 10, 9).date())
        self.assertEqual((row['date'], row['time']), ('Oct 3, 2026', '9:05 AM'))


class ActivityLogImplementationContractTests(unittest.TestCase):
    def test_database_query_and_legacy_routine_controls_are_present(self):
        for token in (
            "include_routine",
            "hidden_routine_count",
            "ActivityLog.timestamp >= datetime.combine(start_date, datetime.min.time())",
            "ActivityLog.timestamp < datetime.combine(end_date + timedelta(days=1), datetime.min.time())",
            "ActivityLog.timestamp.desc(), ActivityLog.id.desc()",
            "problem_count",
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
            'history.replaceState',
            'data-label="Details"',
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
            if item['release_key'] == '2026-10-03-activity-log-simple'
        )
        self.assertTrue(release['is_published'])
        self.assertTrue(any(item['category'] == 'Activity Log' for item in release['items']))
        self.assertIn('medical-service-pwa-offline-navigation-v237-activity-log-simple', APP_SOURCE)


if __name__ == '__main__':
    unittest.main()
