import pathlib
import unittest
from datetime import date

try:
    import app as app_module
except Exception:
    app_module = None


ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / 'app.py').read_text(encoding='utf-8')
REIMBURSEMENT_TEMPLATE = (ROOT / 'templates' / 'reimbursement.html').read_text(encoding='utf-8')
EMBEDDED_LPR_TEMPLATE = (ROOT / 'templates' / '_embedded_lpr_modal.html').read_text(encoding='utf-8')
APPROVAL_TEMPLATE = (ROOT / 'templates' / 'approvals.html').read_text(encoding='utf-8')


class ReimbursementLPRIntegrationTests(unittest.TestCase):
    def test_reimbursement_is_supported_as_one_embedded_lpr_parent(self):
        self.assertIn("{'cash_advance', 'travel_request', 'reimbursement'}", APP_SOURCE)
        self.assertIn('reimbursement_id = db.Column', APP_SOURCE)
        self.assertIn('reimbursement_source_key = db.Column', APP_SOURCE)
        self.assertIn("linked_lpr_records('reimbursement', header.id)", APP_SOURCE)

    def test_submit_requires_reconciled_lpr_for_office_field_items(self):
        self.assertIn('def reimbursement_lpr_sources(header):', APP_SOURCE)
        self.assertIn('def validate_reimbursement_linked_lpr(header, lpr_header, require_header=False):', APP_SOURCE)
        self.assertIn("'lpr_required': True", APP_SOURCE)
        self.assertIn("sync_embedded_lpr_parent_signatures('reimbursement', header, 'submitted'", APP_SOURCE)
        self.assertIn("sync_embedded_lpr_parent_signatures('reimbursement', header, 'approved'", APP_SOURCE)

    def test_frontend_reviews_lpr_before_continuing_submit(self):
        self.assertIn('reimbursementOfficeFieldTotal(rowsForSubmit)', REIMBURSEMENT_TEMPLATE)
        self.assertIn('openReimbursementLprForReview(true)', REIMBURSEMENT_TEMPLATE)
        self.assertIn("embedded_lpr_parent_module = 'reimbursement'", REIMBURSEMENT_TEMPLATE)
        self.assertIn('openReimbursementLprReview', EMBEDDED_LPR_TEMPLATE)
        self.assertIn('Required subtotal:', EMBEDDED_LPR_TEMPLATE)
        self.assertIn('splitEmbeddedLprItem', EMBEDDED_LPR_TEMPLATE)

    def test_approval_and_accounting_include_the_lpr(self):
        self.assertIn("package.writestr(f'{lpr_name}.pdf'", APP_SOURCE)
        self.assertIn("payload['linked_lprs']", APP_SOURCE)
        self.assertIn('Attached LPR:', APPROVAL_TEMPLATE)

    def test_reimbursement_lpr_sources_and_group_reconciliation(self):
        if app_module is None:
            self.skipTest('Application dependencies are unavailable.')
        with app_module.app.app_context():
            header = app_module.ReimbursementHeader(
                id=91, user_id=1, start_date=date(2026, 7, 17), end_date=date(2026, 7, 17), status='Draft'
            )
            header.rows.append(app_module.ReimbursementRow(
                id=11, shift_id=77, row_date=date(2026, 7, 17), client_name='QA Medical Center',
                task_name='Field repair', remarks='Replacement cable', office_supplies=500, row_total=500
            ))
            sources = app_module.reimbursement_lpr_sources(header)
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0]['key'], 'shift:77')
            self.assertEqual(sources[0]['amount'], 500.0)
            self.assertEqual(sources[0]['description'], 'Replacement cable')

            lpr = app_module.LPRHeader(
                user_id=1, parent_module='reimbursement', reimbursement_id=91,
                branch_code='BC01', class_code='CC04', dept_code='DC03', product_code='PC23',
                intended_for='QA Medical Center', equipment='Demo unit', total_requested=500
            )
            lpr.items.extend([
                app_module.LPRItem(description='Cable', quantity=2, unit_measure='pcs', unit_price=150,
                                   line_total=300, reimbursement_source_key='shift:77'),
                app_module.LPRItem(description='Connector', quantity=2, unit_measure='pcs', unit_price=100,
                                   line_total=200, reimbursement_source_key='shift:77')
            ])
            self.assertTrue(app_module.validate_reimbursement_linked_lpr(header, lpr, require_header=True))
            lpr.items[1].line_total = 150
            with self.assertRaises(ValueError):
                app_module.validate_reimbursement_linked_lpr(header, lpr, require_header=True)


if __name__ == '__main__':
    unittest.main()
