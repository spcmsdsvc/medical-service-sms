import pathlib
import unittest
from datetime import date
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from openpyxl import load_workbook

try:
    import app as app_module
except Exception as import_error:  # pragma: no cover - dependency-safe source runs
    app_module = None
    APP_IMPORT_ERROR = import_error
else:
    APP_IMPORT_ERROR = None


ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / 'app.py').read_text(encoding='utf-8')
REIMBURSEMENT_TEMPLATE = (ROOT / 'templates' / 'reimbursement.html').read_text(encoding='utf-8')


@unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
class ReimbursementTotalConsistencyTests(unittest.TestCase):
    @staticmethod
    def row(row_id, row_total=0, row_date=date(2026, 7, 1), **amounts):
        values = {
            'id': row_id,
            'row_date': row_date,
            'row_total': row_total,
            'shift_id': None,
            'client_name': '',
            'task_name': 'Manual reimbursement item',
            'product_name': '',
            'serial_number': '',
            'remarks': '',
            **{field: 0 for field in app_module.REIMBURSEMENT_EXPENSE_FIELDS},
        }
        values.update(amounts)
        return SimpleNamespace(**values)

    @staticmethod
    def header(*rows):
        return SimpleNamespace(
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
            engineer_id=None,
            user_id=None,
            rows=list(rows),
        )

    def test_component_columns_are_the_shared_source_for_categories_and_total(self):
        header = self.header(
            self.row(1, row_total=150, transpo=150),
            self.row(2, row_total=900, office_supplies=900),
        )

        summary = app_module.reimbursement_total_snapshot(header)

        self.assertEqual(summary['grand_total'], 1050.0)
        self.assertEqual(summary['component_total'], 1050.0)
        self.assertEqual(summary['row_total_total'], 1050.0)
        self.assertTrue(summary['consistent'])
        self.assertEqual(
            [(item['field'], item['amount']) for item in summary['category_totals']],
            [('transpo', 150.0), ('office_supplies', 900.0)],
        )
        self.assertEqual(app_module.reimbursement_expense_category_totals(header), summary['category_totals'])

    def test_legacy_row_total_is_preserved_under_others_misc(self):
        header = self.header(self.row(7, row_total=500))

        summary = app_module.reimbursement_total_snapshot(header)
        effective_amounts, effective_total, _, source = app_module.reimbursement_effective_row_amounts(header.rows[0])

        self.assertEqual(summary['grand_total'], 500.0)
        self.assertEqual(summary['legacy_fallback_row_count'], 1)
        self.assertFalse(summary['consistent'])
        self.assertEqual(source, 'legacy_row_total')
        self.assertEqual(effective_total, 500.0)
        self.assertEqual(effective_amounts['others_misc'], 500.0)
        self.assertEqual(effective_amounts['office_supplies'], 0.0)

    def test_nonzero_mismatch_is_reported_and_component_total_is_used(self):
        header = self.header(self.row(9, row_total=55000, office_supplies=36000))

        summary = app_module.reimbursement_total_snapshot(header)

        self.assertEqual(summary['grand_total'], 36000.0)
        self.assertEqual(summary['row_total_total'], 55000.0)
        self.assertEqual(summary['component_total'], 36000.0)
        self.assertEqual(summary['mismatch_row_count'], 1)
        self.assertFalse(summary['consistent'])
        self.assertIn('generated forms use the saved expense columns', summary['warning'])

    def test_excel_and_rfp_paths_use_the_snapshot_helpers(self):
        self.assertIn('reimbursement_effective_row_amounts(row)', APP_SOURCE)
        self.assertIn("('Row Total', f\"PHP {effective_row_total:,.2f}\")", APP_SOURCE)
        self.assertIn("return reimbursement_total_snapshot(header)['category_totals']", APP_SOURCE)
        self.assertIn("'reimbursement_total_summary': total_summary", APP_SOURCE)
        self.assertIn('applyReimbursementTotalSummary(payload)', REIMBURSEMENT_TEMPLATE)
        self.assertIn('Official saved total:', REIMBURSEMENT_TEMPLATE)
        self.assertIn("tone === 'warn' ? '#b45309'", REIMBURSEMENT_TEMPLATE)
        self.assertIn('loadedWarning', REIMBURSEMENT_TEMPLATE)

    def test_excel_materializes_totals_for_manual_items_without_recalculation(self):
        header = self.header(
            self.row(
                17,
                row_total=125.50,
                row_date=date(2026, 7, 6),
                office_supplies=125.50,
            )
        )

        with patch.object(app_module, 'current_user', SimpleNamespace(username='Engineer')):
            workbook = app_module.build_reimbursement_excel_workbook(header)

        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        worksheet = load_workbook(output, data_only=True)['Format']

        self.assertEqual(worksheet['G7'].value, 125.50)
        self.assertEqual(worksheet['G8'].value, 125.50)
        self.assertEqual(worksheet['K9'].value, 125.50)
        self.assertIsInstance(worksheet['G8'].value, (int, float))
        self.assertIsInstance(worksheet['K9'].value, (int, float))


if __name__ == '__main__':
    unittest.main()
