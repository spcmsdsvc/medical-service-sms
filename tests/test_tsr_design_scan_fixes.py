"""Create TSR design scan fixes (plans.md, 2026-10-15): labels, contrast, wording, action bar."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


class TSRDesignScanFixes(unittest.TestCase):
    template = read("templates/offline_tsr.html")
    page_css = read("static/css/app-offline-tsr.css")
    calibration_css = read("static/css/app-calibration-report.css")
    app_source = read("app.py")

    # Batch 1
    def test_field_labels_point_at_their_fields(self):
        for field_id in (
            "tsr-customer-name", "tsr-number", "tsr-address", "tsr-requested-by", "tsr-department",
            "tsr-equipment-model", "tsr-serial-no", "tsr-complaint", "tsr-remarks",
            "tsr-document-select", "tsr-attachment-input",
        ):
            self.assertIn(f'<label for="{field_id}"', self.template, field_id)
            self.assertIn(f'id="{field_id}"', self.template, field_id)

    def test_parts_row_inputs_are_named(self):
        row = self.template[self.template.index("function addTSRPartRow"):self.template.index("function getParts")]
        for name in ("Item no.", "Part number", "Description", "Quantity", "Delivery receipt"):
            self.assertIn(f'aria-label="{name} ${{partRowPosition}}"', row, name)

    def test_schedule_button_name_starts_with_visible_text(self):
        self.assertIn('aria-label="Select Schedule from List (required)"', self.template)
        self.assertIn("</i>Select Schedule from List", self.template)

    # Batch 2
    def test_small_tags_use_the_darker_accent_text(self):
        for selector in (".offline-tsr-required-marker {", ".offline-tsr-readiness-progress {"):
            block = self.page_css[self.page_css.index(selector):]
            block = block[:block.index("}")]
            self.assertIn("color: var(--app-primary-text", block, selector)
        self.assertEqual(self.template.count("offline-tsr-count-badge"), 2)
        self.assertIn(".offline-tsr-page .offline-tsr-count-badge {", self.page_css)

    def test_dark_theme_clear_and_not_started_rules(self):
        self.assertIn(':root[data-app-theme="dark"] .offline-tsr-action-bar .btn-outline-danger {', self.page_css)
        self.assertIn(':root[data-app-theme="dark"] .calibration-report-card .calibration-report-status.muted{', self.calibration_css)

    def test_disabled_outline_buttons_follow_accent_text(self):
        block = self.page_css[self.page_css.index(".offline-tsr-action-bar .btn-outline-primary {"):]
        self.assertIn("--bs-btn-disabled-color: var(--app-primary-text", block[:block.index("}")])

    def test_disclosure_headers_are_44px(self):
        self.assertIn('<summary class="fw-bold offline-tsr-parts-summary">', self.template)
        block = self.page_css[self.page_css.index(".offline-tsr-page #standalone-tsr-drafts-disclosure > summary,"):]
        self.assertIn(".offline-tsr-page .offline-tsr-parts-summary {", block)
        self.assertIn("min-height: 44px;", block[:block.index("}")])

    def test_stylesheet_versions_are_bumped(self):
        self.assertIn("css/app-offline-tsr.css') }}?v=9", self.template)
        self.assertIn("css/app-calibration-report.css') }}?v=13", self.template)
        self.assertIn("'/static/css/app-offline-tsr.css?v=9'", self.app_source)
        self.assertIn("'/static/css/app-calibration-report.css?v=13'", self.app_source)

    # Batch 3
    def test_label_wording(self):
        for text in (
            "</i>Add Acknowledged By Signature</button>",
            "</i>Add Serviced By Signature</button>",
            "</i>Search Complaints",
            '>Customer &amp; Equipment</a>', '>Service Work</a>', '>Visit &amp; Sign-off</a>', '>Supporting Documents</a>',
            '<span class="offline-tsr-readiness-label">Serviced By Signature</span>',
            '<span class="offline-tsr-readiness-label">Acknowledged By Signature</span>',
            ">Extra Attachments</label>",
            "Parts Supplied/Recommended <span class=\"small text-muted\">(optional)</span></summary>",
            "Filled in from the schedule's equipment and locked.",
        ):
            self.assertIn(text, self.template, text)
        for gone in (
            "Add Acknowledged Signature", "Search Previous Complaints", "Offline TSR Attachments",
            ">Step 1<", "can use correction mode.</div>",
        ):
            self.assertNotIn(gone, self.template, gone)

    # Batch 4
    def test_action_bar_uses_accent_neutral_and_red(self):
        bar = self.template[self.template.index('id="offline-tsr-action-bar"'):]
        bar = bar[:bar.index("</div>\n  </div>")]
        self.assertNotIn("btn-outline-success", bar)
        self.assertNotIn("btn-outline-dark", bar)
        self.assertIn('class="btn btn-outline-primary fw-bold offline-tsr-pdf-action"', bar)

    def test_side_stripes_removed(self):
        self.assertNotRegex(self.calibration_css, r"\.calibration-report-card\{[^}]*border-left:5px")
        self.assertNotRegex(self.template, r"\.offline-tsr-storage-health\{[^}]*border-left:5px")


if __name__ == "__main__":
    unittest.main()
