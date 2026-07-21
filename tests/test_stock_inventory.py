import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class StockInventorySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.layout_source = (ROOT / 'templates' / 'layout.html').read_text(encoding='utf-8')
        cls.page_source = (ROOT / 'templates' / 'stock_inventory.html').read_text(encoding='utf-8')
        cls.dashboard_source = (ROOT / 'templates' / 'stock_inventory_dashboard.html').read_text(encoding='utf-8')
        cls.settings_source = (ROOT / 'templates' / 'settings.html').read_text(encoding='utf-8')

    def test_branch_inventory_module_and_additive_tables_exist(self):
        self.assertIn("@app.route('/stock_inventory')", self.app_source)
        self.assertIn('if not can_manage_stock_inventory()', self.app_source)
        self.assertIn("__tablename__ = 'stock_inventory_item'", self.app_source)
        self.assertIn("__tablename__ = 'stock_inventory_movement'", self.app_source)
        self.assertIn("db.UniqueConstraint('branch_code', 'scan_barcode'", self.app_source)
        self.assertIn('ensure_stock_inventory_tables()', self.app_source)
        self.assertIn('Stock Inventory</a>', self.layout_source)
        self.assertIn('{% if stock_inventory_access %}', self.layout_source)

    def test_scanner_and_transaction_controls_are_present(self):
        for marker in (
            'Scan / Enter Barcode',
            'lookupScannedBarcode',
            "event.key==='Enter'",
            "chooseStockDirection('IN')",
            "chooseStockDirection('OUT')",
            'Borrowed By',
            'Returned By',
            'movementEngineerSearch',
            'Reverse Transaction',
            'Out of Stock',
            'QTY',
        ):
            self.assertIn(marker, self.page_source)
        self.assertNotIn('Opening Quantity', self.page_source)
        self.assertNotIn('Minimum Stock', self.page_source)

    def test_api_surface_and_rules_are_present(self):
        for route in (
            "@app.route('/api/stock-inventory/summary')",
            "@app.route('/api/stock-inventory/items')",
            "@app.route('/api/stock-inventory/lookup', methods=['POST'])",
            "@app.route('/api/stock-inventory/items', methods=['POST'])",
            "@app.route('/api/stock-inventory/engineers')",
            "@app.route('/api/stock-inventory/movements', methods=['POST'])",
            "@app.route('/api/stock-inventory/movements/<int:movement_id>/reverse', methods=['POST'])",
        ):
            self.assertIn(route, self.app_source)
        self.assertIn("STOCK_IN_REASONS = {'Return', 'Restock', 'Adjustment'}", self.app_source)
        self.assertIn("'BC02': 'Cebu'", self.app_source)
        self.assertIn("'BC03': 'Davao'", self.app_source)
        self.assertIn('stock_inventory_request_branch(payload)', self.app_source)
        self.assertIn('StockInventoryItem.current_quantity >= quantity', self.app_source)
        self.assertIn("'This movement has already been reversed.'", self.app_source)

    def test_inventory_only_access_and_dashboard_are_present(self):
        for marker in ('can_manage_stock_inventory', 'stock_inventory_only', 'stock_inventory_branch_code'):
            self.assertIn(marker, self.app_source)
        self.assertIn('restrict_stock_inventory_only_accounts', self.app_source)
        self.assertIn('Stock Inventory-only view', self.settings_source)
        self.assertIn('Assigned Inventory Branch', self.settings_source)
        self.assertIn('Inventory Dashboard', self.dashboard_source)

    def test_activity_log_has_distinct_stock_category(self):
        self.assertIn("'Stock Inventory': {'icon': 'fa-barcode'", self.app_source)
        self.assertIn("if 'stock inventory' in text:", self.app_source)
        self.assertIn("return 'Stock Inventory'", self.app_source)

    def test_release_manifest_contains_stock_inventory(self):
        manifest = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))
        release = next(item for item in manifest['releases'] if item['release_key'] == '2026-07-21')
        self.assertTrue(release['is_published'])
        self.assertTrue(any(item['item_key'] == '2026-07-21-stock-inventory' for item in release['items']))


if __name__ == '__main__':
    unittest.main()
