import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TIMELINE = ROOT / "templates" / "timeline.html"


class TimelineGridWidthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.timeline = TIMELINE.read_text(encoding="utf-8")

    def test_desktop_grid_fills_available_width_but_keeps_minimum_columns(self):
        grid_css = self.timeline[
            self.timeline.index(".timeline-grid-table {") : self.timeline.index(
                ".timeline-scroll-hint", self.timeline.index(".timeline-grid-table {")
            )
        ]

        self.assertIn("width: 100%;", grid_css)
        self.assertNotIn("width: max-content;", grid_css)
        self.assertIn("min-width: 170px;", grid_css)
        self.assertIn("max-width: none;", grid_css)

    def test_render_grid_does_not_restore_fixed_week_pixel_width(self):
        render_start = self.timeline.index("function renderTimelineGrid")
        render_end = self.timeline.index("function syncTimelineHorizontalScroll", render_start)
        render = self.timeline[render_start:render_end]

        self.assertIn("mainGridTable.style.width = '100%';", render)
        self.assertIn("mainGridTable.style.minWidth = '1180px';", render)
        self.assertNotIn("const timelineTableWidth", render)
        self.assertNotIn("timelineTableWidth}px", render)

    def test_generated_day_cells_do_not_cap_their_width(self):
        render_start = self.timeline.index("function renderTimelineGrid")
        render_end = self.timeline.index("function syncTimelineHorizontalScroll", render_start)
        render = self.timeline[render_start:render_end]

        self.assertIn(
            '<th class="text-center" style="min-width: 170px;">',
            render,
        )
        self.assertRegex(render, r'style="min-width:170px; min-height: 100px;')
        self.assertNotIn("width: 170px; min-width: 170px; max-width: 170px", render)
        self.assertNotIn("width:170px; min-width:170px; max-width:170px", render)

    def test_forced_mobile_desktop_mode_keeps_its_intentional_fixed_width(self):
        forced_mode = self.timeline[
            self.timeline.index("body.mobile-engineer-desktop-forced .timeline-grid-table,") :
            self.timeline.index(
                "/* S5 APPROVER CALENDAR VIEW",
                self.timeline.index("body.mobile-engineer-desktop-forced .timeline-grid-table,"),
            )
        ]

        self.assertIn("min-width: 1680px !important;", forced_mode)
        self.assertIn("width: 1680px !important;", forced_mode)
        self.assertIn("min-width: 214px !important;", forced_mode)


if __name__ == "__main__":
    unittest.main()
