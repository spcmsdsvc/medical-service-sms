import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TIMELINE = ROOT / "templates" / "timeline.html"


class TimelineProductCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = TIMELINE.read_text(encoding="utf-8")

    def test_schedule_modal_contains_read_only_coverage_strip(self):
        self.assertIn('id="product-coverage-status"', self.source)
        self.assertIn('id="product-coverage-badge"', self.source)
        self.assertIn("Product Coverage", self.source)

    def test_all_product_statuses_are_supported(self):
        for status in (
            "Under Warranty",
            "Under Contract",
            "Expired - Under Contract",
            "Expired - No Contract",
            "No Expiry Set - Under Contract",
            "No Expiry Set - No Contract",
        ):
            self.assertIn(status, self.source)

    def test_selection_and_reset_paths_refresh_coverage(self):
        self.assertIn("renderProductCoverageStatus(m);", self.source)
        self.assertIn("renderProductCoverageStatus(shift.product_id || null);", self.source)
        self.assertIn("renderProductCoverageStatus(masterProduct);", self.source)
        self.assertGreaterEqual(self.source.count("renderProductCoverageStatus(null);"), 4)

    def test_coverage_is_not_saved_as_schedule_data(self):
        self.assertNotIn("dataSet.append('under_contract'", self.source)
        self.assertNotIn('dataSet.append("under_contract"', self.source)


if __name__ == "__main__":
    unittest.main()
