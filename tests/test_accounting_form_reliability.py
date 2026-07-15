import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class AccountingFormReliabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.reimbursement_source = (ROOT / 'templates' / 'reimbursement.html').read_text(encoding='utf-8')

    def test_travel_pdf_replaces_php_marker_for_usd(self):
        self.assertIn("if currency_code == 'USD':", self.app_source)
        self.assertIn("draw_text(281, y, 'USD'", self.app_source)
        self.assertIn('draw_money_row(457, airfare)', self.app_source)
        self.assertIn('draw_money_row(388, total_amount, bold=True)', self.app_source)

    def test_manual_item_snapshots_live_worksheet_before_render(self):
        self.assertIn('function snapshotCurrentReimbursementWorksheetRows()', self.reimbursement_source)
        snapshot_call = self.reimbursement_source.index('const preservedRows = snapshotCurrentReimbursementWorksheetRows();')
        render_call = self.reimbursement_source.index('renderReimbursementRows(rows);', snapshot_call)
        self.assertLess(snapshot_call, render_call)
        self.assertIn('amounts: amounts,', self.reimbursement_source)
        self.assertIn("remarks: payloadRow.remarks || ''", self.reimbursement_source)


if __name__ == '__main__':
    unittest.main()
