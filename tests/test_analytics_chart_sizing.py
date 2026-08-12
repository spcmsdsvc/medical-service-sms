"""The Analytics charts must fit the phone they are read on.

The upgrade shipped a fixed 640-unit viewBox scaled with preserveAspectRatio, which needed
`min-width: 560px` on the SVG to stop <text> shrinking to roughly 6px on a phone -- and that
min-width is what made the chart frame scroll sideways at 375px with no affordance. The
approved plan had specified drawing at one user unit per CSS pixel from the measured container
width precisely so this could not happen, and that is what these pin.

There is no JavaScript runner in this suite, so the renderer assertions are source-level. Each
asserts an outcome -- that no literal canvas coordinate survives, that the scaffold sizes from
a measurement, that the resize guard compares integers -- rather than pinning how any of it is
written. The geometry itself is verified in a browser at 375px.
"""

import pathlib
import re
import unittest

from tests.sw_cache_version import assert_cache_version_at_least  # noqa: E402


ROOT = pathlib.Path(__file__).resolve().parents[1]


class AnalyticsChartSizingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = (ROOT / 'static' / 'js' / 'app-analytics.js').read_text(encoding='utf-8')
        cls.css = (ROOT / 'static' / 'css' / 'app-analytics.css').read_text(encoding='utf-8')

    def _frame_svg_rule(self):
        match = re.search(r'\.analytics-chart-frame svg \{([^}]*)\}', self.css)
        self.assertIsNotNone(match, 'the chart SVG rule is missing')
        return match.group(1)

    def test_the_chart_svg_carries_no_minimum_width(self):
        """The line that caused the scroll.

        A 560px floor inside a frame that is about 320px wide on a phone can only overflow.
        """
        self.assertNotIn('min-width', self._frame_svg_rule())

    def test_the_frame_still_contains_any_overflow(self):
        """Positive control: removing the min-width must not remove the containment.

        overflow-x: auto is the floor for a pathologically narrow viewport, not the mechanism
        -- but if it ever does overflow, it must still be the frame that scrolls and not the
        page.
        """
        frame = re.search(r'\.analytics-chart-frame \{([^}]*)\}', self.css)
        self.assertIsNotNone(frame, 'the chart frame rule is missing')
        self.assertIn('overflow-x: auto', frame.group(1))

    def test_the_scaffold_sizes_the_chart_from_a_measurement(self):
        """width and height attributes AND a matching viewBox.

        A viewBox alone scales, which is the behaviour being removed.
        """
        self.assertIn('function chartWidth(', self.js)
        self.assertIn('clientWidth', self.js)
        scaffold = self.js.split('function chartScaffold(')[1].split('\n    }')[0]
        self.assertIn('chartWidth(target)', scaffold)
        self.assertIn('width, height, viewBox:', scaffold)

    def test_no_fixed_canvas_width_survives_in_either_renderer(self):
        """The old geometry was literals against a 640-unit canvas.

        Every one of them -- the 178 bar track, the 556 count column, the 636 delta column,
        the 590 trend slot -- had to become a function of the measured width, or the chart
        would draw off the edge of a narrow container instead of scrolling inside it.
        """
        for name in ('function renderTrend(', 'function renderHorizontalChart('):
            body = self.js.split(name)[1].split('\n    function ')[0]
            for literal in ('640', '590', '556', '636', '342', '178'):
                self.assertNotIn(literal, body,
                                 f'{name} still contains the fixed coordinate {literal}')

    def test_both_renderers_read_the_width_they_were_given(self):
        """Positive control for the test above: they must still be drawing something."""
        for name in ('function renderTrend(', 'function renderHorizontalChart('):
            body = self.js.split(name)[1].split('\n    function ')[0]
            self.assertIn("svg.getAttribute('width')", body)
            self.assertIn('svgElement(', body)

    def test_a_long_label_is_cut_to_its_column_rather_than_overflowing(self):
        """SVG has no text-overflow, so an untruncated label draws over the bars."""
        self.assertIn('function truncateLabel(', self.js)
        horizontal = self.js.split('function renderHorizontalChart(')[1].split('\n    function ')[0]
        self.assertIn('truncateLabel(row.label', horizontal)

    def test_the_full_label_still_reaches_the_reader(self):
        """Positive control: truncation must not lose data.

        The row's <title> carries the untruncated label, and the hidden data table carries
        every row -- which is also what the print stylesheet reveals.
        """
        horizontal = self.js.split('function renderHorizontalChart(')[1].split('\n    function ')[0]
        self.assertIn("svgElement(\n                'title'", horizontal)
        self.assertIn('${row.label}: ${row.count}', horizontal)
        self.assertIn('addTableRow(table, [row.label', horizontal)

    def test_the_trend_thins_its_labels_rather_than_overlapping_them(self):
        """A 31-day range cannot carry 31 date labels in 320px."""
        trend = self.js.split('function renderTrend(')[1].split('\n    function ')[0]
        self.assertIn('labelStep', trend)
        self.assertIn('index % labelStep === 0', trend)

    def test_every_trend_bar_keeps_its_tooltip_when_its_label_is_thinned(self):
        """Positive control: thinning labels must not thin the data."""
        trend = self.js.split('function renderTrend(')[1].split('\n    function ')[0]
        self.assertIn("svgElement('title', {}", trend)
        self.assertIn('previous period', trend)

    def test_the_charts_redraw_when_the_container_changes_width(self):
        """Sizing from the container means a resize has to redraw."""
        self.assertIn('ResizeObserver', self.js)
        self.assertIn('observeChartResize()', self.js)

    def test_equipment_charts_join_the_resize_observer(self):
        """Hidden-tab charts must be redrawn after their panel becomes visible."""
        declaration = self.js.split('const CHART_FRAME_IDS =', 1)[1].split(';', 1)[0]
        self.assertIn('equipment-machine-chart', declaration)
        self.assertIn('equipment-model-chart', declaration)

    def test_the_resize_guard_compares_integer_widths(self):
        """The loop the plan's risk table named.

        A sub-pixel reflow would otherwise trip the observer from inside its own callback.
        chartWidth() floors, and nothing in the redraw path writes to the container's width.
        """
        observer = self.js.split('function observeChartResize(')[1].split('\n    function ')[0]
        self.assertIn('lastChartWidths[id] !== chartWidth(node)', observer)
        self.assertIn('if (!changed) return;', observer)
        self.assertIn('setTimeout', observer)
        self.assertIn('Math.floor', self.js.split('function chartWidth(')[1].split('\n    }')[0])

    def test_the_redraw_never_sets_the_width_it_measures(self):
        """Positive control for the guard: the other half of the loop.

        A chart that writes to its own container's width re-triggers the observer no matter
        how well the width comparison is guarded.
        """
        render = self.js.split('function renderScheduleCharts(')[1].split('\n    //')[0]
        self.assertNotIn('style.width', render)
        self.assertNotIn('.width =', render)

    def test_the_service_worker_was_bumped_for_the_new_assets(self):
        assert_cache_version_at_least(self, 77)


if __name__ == '__main__':
    unittest.main()
