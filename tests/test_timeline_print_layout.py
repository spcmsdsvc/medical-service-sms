import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TIMELINE = ROOT / "templates" / "timeline.html"


class TimelinePrintLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = TIMELINE.read_text(encoding="utf-8")
        cls.print_document = source.split("let html = `", 1)[1].split("</style>", 1)[0]

    def test_print_schedule_can_start_below_header_on_first_page(self):
        print_rules = self.print_document.split("@media print", 1)[1].split("@media screen", 1)[0]

        self.assertRegex(print_rules, r"\.weekly-stack\s*\{\s*display:\s*block;")
        self.assertRegex(print_rules, r"\.week-block\s*\{[^}]*page-break-inside:\s*auto;")
        self.assertRegex(print_rules, r"\.week-block\s*\{[^}]*break-inside:\s*auto;")

    def test_screen_print_preview_keeps_its_stacked_layout(self):
        base_rules = self.print_document.split("@media print", 1)[0]

        self.assertRegex(base_rules, r"\.weekly-stack\s*\{[^}]*display:\s*flex;")
        self.assertRegex(base_rules, r"\.week-block\s*\{[^}]*page-break-inside:\s*avoid;")


if __name__ == "__main__":
    unittest.main()
