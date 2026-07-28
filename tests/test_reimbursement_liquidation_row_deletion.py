import json
import pathlib
import unittest
from datetime import date
from types import SimpleNamespace

try:
    import app as app_module
except Exception:
    app_module = None


ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / 'app.py').read_text(encoding='utf-8')
REIMBURSEMENT_TEMPLATE = (ROOT / 'templates' / 'reimbursement.html').read_text(encoding='utf-8')
TRAVEL_LIQUIDATION_TEMPLATE = (
    ROOT / 'templates' / 'travel_liquidation.html'
).read_text(encoding='utf-8')
CASH_ADVANCE_LIQUIDATION_TEMPLATE = (
    ROOT / 'templates' / 'cash_advance_liquidation.html'
).read_text(encoding='utf-8')


class ReimbursementLiquidationRowDeletionTests(unittest.TestCase):
    def test_reimbursement_model_and_runtime_migration_include_exclusions(self):
        self.assertIn('excluded_rows_json = db.Column(db.Text, nullable=True)', APP_SOURCE)
        self.assertIn(
            'ALTER TABLE reimbursement_header ADD COLUMN excluded_rows_json TEXT',
            APP_SOURCE,
        )

    def test_reimbursement_frontend_has_delete_and_restore_controls(self):
        for expected in (
            'removeReimbursementRow',
            'restoreReimbursementRow',
            'restoreAllReimbursementRows',
            'reimRemovedRowsPanel',
            'excluded_rows: currentReimbursementExcludedRows',
        ):
            self.assertIn(expected, REIMBURSEMENT_TEMPLATE)
        self.assertIn('Calendar schedules and package receipts will not be deleted.', REIMBURSEMENT_TEMPLATE)

    def test_liquidation_pages_confirm_linked_receipt_cleanup(self):
        for template in (TRAVEL_LIQUIDATION_TEMPLATE, CASH_ADVANCE_LIQUIDATION_TEMPLATE):
            self.assertIn('Delete Expense Row', template)
            self.assertIn('linked receipt', template)
            self.assertIn('cleanup_warning', template)

    def test_liquidation_storage_cleanup_runs_after_database_commit(self):
        travel_start = APP_SOURCE.index('def delete_travel_liquidation_row')
        travel_end = APP_SOURCE.index('def upload_travel_liquidation_receipt', travel_start)
        travel_block = APP_SOURCE[travel_start:travel_end]
        self.assertLess(travel_block.index('db.session.commit()'), travel_block.index('managed_storage_delete('))

        cash_start = APP_SOURCE.index('def delete_cash_advance_liquidation_row')
        cash_end = APP_SOURCE.index('def upload_cash_advance_liquidation_receipt', cash_start)
        cash_block = APP_SOURCE[cash_start:cash_end]
        self.assertLess(cash_block.index('db.session.commit()'), cash_block.index('managed_storage_delete('))

    @unittest.skipUnless(app_module is not None, 'Application dependencies are unavailable.')
    def test_excluded_row_helpers_preserve_safe_manual_snapshot(self):
        profile = SimpleNamespace(name='Test Engineer')
        raw = [{
            'manual': True,
            'manual_key': 'manual-test-1',
            'date': '2026-07-28',
            'task': 'Field cable',
            'remarks': 'Purchased during urgent visit',
            'amounts': {'others': 250},
        }]
        with app_module.app.test_request_context('/'):
            sanitized = app_module.reimbursement_sanitize_excluded_rows(
                raw, profile, date(2026, 7, 1), date(2026, 7, 31)
            )
        self.assertEqual(len(sanitized), 1)
        self.assertEqual(sanitized[0]['manual_key'], 'manual-test-1')
        self.assertEqual(sanitized[0]['row_total'], 250)
        self.assertEqual(app_module.reimbursement_excluded_row_key(sanitized[0]), 'manual:manual-test-1')

        header = SimpleNamespace(excluded_rows_json=json.dumps(sanitized))
        self.assertEqual(app_module.reimbursement_get_excluded_rows(header), sanitized)


if __name__ == '__main__':
    unittest.main()
