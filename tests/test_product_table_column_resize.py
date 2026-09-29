"""Focused source contracts for the shared inventory table header/resize UI."""

import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ProductTableColumnResizeMarkupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "templates" / "products.html").read_text(encoding="utf-8")
        cls.header = cls.source.split("<thead", 1)[1].split("</thead>", 1)[0]

    def test_room_shifted_wrapping_and_bsid_minimum_are_explicit(self):
        self.assertIn(".product-col-bsid { width: 5rem; min-width: 7rem; }", self.source)
        self.assertRegex(
            self.source,
            r":nth-child\(1\).*?\n\s*\.product-table-wrap :is\(th, td\):nth-child\(3\).*?\n\s*\.product-table-wrap :is\(th, td\):nth-child\(4\).*?\n\s*\.product-table-wrap :is\(th, td\):nth-child\(6\).*?\n\s*\.product-table-wrap :is\(th, td\):nth-child\(7\)",
        )
        self.assertNotIn(
            ".product-table-wrap :is(th, td):nth-child(5),\n    .product-table-wrap :is(th, td):nth-child(6)",
            self.source,
        )

    def test_each_header_has_separator_after_sort_button(self):
        keys = ("serial", "name", "room", "bsid", "owner", "start", "end", "status")
        self.assertEqual(self.header.count('class="product-column-resizer"'), len(keys))
        for key in keys:
            header_match = re.search(
                rf"<th[^>]*data-column-key=\"{key}\".*?</th>", self.header, re.DOTALL
            )
            self.assertIsNotNone(header_match, key)
            markup = header_match.group(0)
            self.assertLess(markup.index("product-sort-btn"), markup.index("product-column-resizer"))
            self.assertIn('role="separator"', markup)
            self.assertIn('aria-orientation="vertical"', markup)
            self.assertIn(f'data-column-key="{key}"', markup)

    def test_resize_behavior_has_pointer_keyboard_bounds_and_refresh(self):
        for marker in (
            "PRODUCT_COLUMN_MAX_WIDTH = 640",
            "beginProductColumnResize",
            "handleProductColumnResize",
            "finishProductColumnResize",
            "ArrowLeft",
            "ArrowRight",
            "event.shiftKey ? 32 : 8",
            "getProductColumnMinWidth",
            "Math.min(PRODUCT_COLUMN_MAX_WIDTH",
            "aria-valuemin",
            "aria-valuemax",
            "aria-valuenow",
            "captureProductColumnWidths",
            "table.style.tableLayout = 'fixed'",
            "refreshProductTableLayout();",
        ):
            self.assertIn(marker, self.source, marker)

    def test_width_preferences_use_exact_inventory_keys_and_reset(self):
        for key in (
            "medicalServiceProductColumnWidthsV1",
            "medicalServiceGenorayColumnWidthsV1",
            "medicalServiceVieworksColumnWidthsV1",
        ):
            self.assertIn(key, self.source)
        for marker in (
            "restoreProductColumnWidths",
            "saveProductColumnWidths",
            "resetProductColumnWidths",
            "localStorage.getItem(PRODUCT_COLUMN_WIDTH_STORAGE_KEY)",
            "localStorage.setItem(PRODUCT_COLUMN_WIDTH_STORAGE_KEY",
            "localStorage.removeItem(PRODUCT_COLUMN_WIDTH_STORAGE_KEY)",
            'id="product-reset-widths"',
            "Reset widths",
        ):
            self.assertIn(marker, self.source, marker)

    def test_resize_controls_are_hidden_for_mobile_and_print(self):
        self.assertIn(".product-column-resizer", self.source)
        self.assertRegex(
            self.source,
            re.compile(r"@media screen and \(max-width: 768px\).*?\.product-column-resizer.*?display: none", re.DOTALL),
        )
        self.assertRegex(
            self.source,
            re.compile(r"@media print.*?\.product-column-resizer.*?display: none", re.DOTALL),
        )


if __name__ == "__main__":
    unittest.main()
