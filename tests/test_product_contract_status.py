import unittest
from datetime import date, timedelta
from pathlib import Path

import app as app_module


ROOT = Path(__file__).resolve().parents[1]


class ProductContractStatusTests(unittest.TestCase):
    def test_status_matrix(self):
        today = date(2026, 7, 22)
        future = today + timedelta(days=1)
        expired = today - timedelta(days=1)

        self.assertEqual(
            app_module.product_contract_status(end_date=future, under_contract=True, today=today),
            'Under Contract',
        )
        self.assertEqual(
            app_module.product_contract_status(end_date=today, under_contract=False, today=today),
            'Under Warranty',
        )
        self.assertEqual(
            app_module.product_contract_status(end_date=expired, under_contract=True, today=today),
            'Expired - Under Contract',
        )
        self.assertEqual(
            app_module.product_contract_status(end_date=expired, under_contract=False, today=today),
            'Expired - No Contract',
        )
        self.assertEqual(
            app_module.product_contract_status(end_date=None, under_contract=True, today=today),
            'No Expiry Set - Under Contract',
        )
        self.assertEqual(
            app_module.product_contract_status(end_date=None, under_contract=False, today=today),
            'No Expiry Set - No Contract',
        )

    def test_contract_csv_header_detection_is_tolerant(self):
        self.assertTrue(app_module.csv_has_header(['Serial Number', 'UNDER_CONTRACT'], 'Under Contract'))
        self.assertTrue(app_module.csv_has_header(['Contract Status'], 'Contract Status'))
        self.assertFalse(app_module.csv_has_header(['Serial Number', 'End Date'], 'Contract'))

    def test_products_interface_contains_contract_controls_and_statuses(self):
        source = (ROOT / 'templates' / 'products.html').read_text(encoding='utf-8')

        self.assertIn('id="p-under-contract"', source)
        self.assertIn('Under Contract', source)
        self.assertIn('Expired - Under Contract', source)
        self.assertIn('Expired - No Contract', source)
        self.assertIn('No Expiry Set - Under Contract', source)
        self.assertIn('No Expiry Set - No Contract', source)
        self.assertIn('document.getElementById(\'p-under-contract\').checked', source)

    def test_product_migration_is_additive(self):
        source = (ROOT / 'app.py').read_text(encoding='utf-8')

        self.assertIn('ALTER TABLE product ADD COLUMN under_contract BOOLEAN DEFAULT 0 NOT NULL', source)
        self.assertIn("'under_contract': bool(p.under_contract)", source)
        self.assertIn("'computed_status': product_contract_status(p)", source)


if __name__ == '__main__':
    unittest.main()
