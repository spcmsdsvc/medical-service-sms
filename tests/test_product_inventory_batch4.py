"""Product Inventory Batch 4: dead and duplicate code removed from products.html."""

import unittest

from tests.test_product_inventory_batch1 import TEMPLATE, function_body


class ProductInventoryCleanupTests(unittest.TestCase):
    def test_duplicate_helpers_and_unused_constant_removed(self):
        self.assertNotIn('productEscape', TEMPLATE)
        self.assertNotIn('productAlert', TEMPLATE)
        self.assertNotIn('inventoryExportUrl', TEMPLATE)

    def test_unreachable_phone_empty_state_removed(self):
        self.assertNotIn('product-mobile-empty', function_body('renderProductMobileCards'))

    def test_never_firing_owner_listener_removed(self):
        self.assertNotIn('p-cli-id', function_body('setupVieworksLinkControls'))


if __name__ == '__main__':
    unittest.main()
