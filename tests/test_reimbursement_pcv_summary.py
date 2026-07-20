import unittest
from datetime import date
from types import SimpleNamespace

try:
    import app as app_module
except ModuleNotFoundError as import_error:  # pragma: no cover - dependency-safe source runs
    app_module = None
    APP_IMPORT_ERROR = import_error
else:
    APP_IMPORT_ERROR = None


@unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
class ReimbursementPcvSummaryTests(unittest.TestCase):
    @staticmethod
    def row(row_id, row_date, **amounts):
        values = {
            'id': row_id,
            'row_date': row_date,
            'row_total': 0,
            'representation': 0,
            'car_repair': 0,
            'toll_fee': 0,
            'gasoline': 0,
            'transpo': 0,
            'office_supplies': 0,
            'parking': 0,
            'per_diem': 0,
            'parking_coding': 0,
            'others_misc': 0,
        }
        values.update(amounts)
        values['row_total'] = sum(float(values[field] or 0) for field in app_module.REIMBURSEMENT_EXPENSE_FIELDS)
        return SimpleNamespace(**values)

    def test_pcv_uses_period_note_and_category_totals(self):
        header = SimpleNamespace(
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
            rows=[
                self.row(1, date(2026, 7, 3), transpo=150),
                self.row(2, date(2026, 7, 4), transpo=50, per_diem=300),
                self.row(3, date(2026, 7, 5), office_supplies=900),
            ],
        )

        items = app_module.reimbursement_pcv_line_items(header)

        self.assertEqual(items[0]['is_summary'], True)
        self.assertIn('Jul 01, 2026 - Jul 31, 2026 (3 claimed days)', items[0]['particular'])
        self.assertEqual(
            [(item['particular'], item['amount']) for item in items[1:]],
            [
                ('Transpo', 200.0),
                ('Office/Field Items', 900.0),
                ('Per Diem', 300.0),
            ],
        )
        self.assertEqual(sum(float(item['amount'] or 0) for item in items), 1400.0)


if __name__ == '__main__':
    unittest.main()
