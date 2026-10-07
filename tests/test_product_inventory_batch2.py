"""Product Inventory Batch 2: desktop table fit and compact phone cards."""

import unittest

from tests.test_product_inventory_batch1 import TEMPLATE, function_body


class ProductInventoryLayoutTests(unittest.TestCase):
    def test_serial_document_links_stack(self):
        self.assertIn('.product-identity-cell .product-serial-document-actions', TEMPLATE)
        self.assertIn('flex-direction: column;', TEMPLATE)

    def test_room_column_hides_when_no_product_has_a_room(self):
        render = function_body('renderTable')
        self.assertIn("'product-room-empty'", render)
        self.assertIn('productsData.some(', render)
        self.assertIn('.product-room-empty :is(th, td):nth-child(3)', TEMPLATE)

    def test_scroll_hint_only_when_overflowing(self):
        self.assertIn("hint?.classList.toggle('is-overflowing'", function_body('updateProductTableHorizontalScroll'))
        self.assertIn('.product-table-scroll-hint.is-overflowing', TEMPLATE)
        self.assertNotIn('(min-width: 769px) and (max-width: 1600px)', TEMPLATE)

    def test_phone_cards_are_compact(self):
        cards = function_body('renderProductMobileCards')
        self.assertIn('product-mobile-head', cards)
        self.assertIn('product-mobile-meta', cards)
        self.assertNotIn('product-mobile-date-box', cards)
        self.assertNotIn('Room: ${', cards)
        self.assertNotIn("p.bsid || 'Not assigned'", cards)
        self.assertNotIn('.product-mobile-date-box', TEMPLATE)

    def test_phone_card_wrapper_uses_shell_gutter(self):
        self.assertIn('.container-fluid > .card {\n            padding: 0 !important;', TEMPLATE)


if __name__ == '__main__':
    unittest.main()
