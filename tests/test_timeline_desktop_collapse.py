import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TIMELINE = ROOT / "templates" / "timeline.html"
APP = ROOT / "app.py"
RELEASES = ROOT / "static" / "changelog" / "releases.json"


class TimelineDesktopCollapsibleIntroTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.timeline = TIMELINE.read_text(encoding="utf-8")
        cls.app = APP.read_text(encoding="utf-8")
        cls.releases = json.loads(RELEASES.read_text(encoding="utf-8"))

    def _intro_panel(self):
        if '<div id="timeline-collapsible-intro"' not in self.timeline:
            self.fail("collapsible intro panel is missing")
        start = self.timeline.index('<div id="timeline-collapsible-intro"')
        end = self.timeline.index(
            '    <div class="timeline-sticky-h-scroll',
            start,
        )
        return start, end, self.timeline[start:end]

    def _intro_controller(self):
        if "function setTimelineIntroCollapsed" not in self.timeline:
            self.fail("collapsible intro controller is missing")
        if "function initTimelineStickyHeaderPolish" not in self.timeline:
            self.fail("sticky header initializer is missing")
        return (
            "function setTimelineIntroCollapsed"
            + self.timeline.split("function setTimelineIntroCollapsed", 1)[1].split(
                "function initTimelineStickyHeaderPolish", 1
            )[0]
        )

    def test_accessible_toggle_starts_expanded_and_controls_panel(self):
        toggle_match = re.search(
            r'<button(?P<button>[^>]*id="timeline-intro-toggle"[^>]*)>'
            r"(?P<body>.*?)</button>",
            self.timeline,
            re.DOTALL,
        )
        self.assertIsNotNone(toggle_match, "desktop intro toggle is missing")
        if toggle_match is None:
            return
        toggle = toggle_match.group(0)
        if '<div id="timeline-collapsible-intro"' not in self.timeline:
            self.fail("collapsible intro panel is missing")
        panel_start = self.timeline.index('<div id="timeline-collapsible-intro"')

        self.assertLess(toggle_match.start(), panel_start, "toggle must be outside the panel")
        self.assertIn('type="button"', toggle)
        self.assertIn('aria-controls="timeline-collapsible-intro"', toggle)
        self.assertIn('aria-expanded="true"', toggle)
        self.assertIn('aria-label="Collapse calendar header"', toggle)
        self.assertIn("Collapse calendar header", toggle_match.group("body"))
        self.assertIn('id="timeline-intro-toggle-icon"', toggle)
        self.assertIn('id="timeline-intro-toggle-label"', toggle)

    def test_panel_contains_complete_intro_but_not_offline_or_calendar_surface(self):
        _, _, panel = self._intro_panel()

        for marker in (
            'id="timeline-freeze-toolbar"',
            'id="timeline-scheduler-toolbar-handle"',
            'id="timeline-engineer-focus-strip"',
            'id="timeline-engineer-desktop-hero"',
            'id="timeline-hybrid-desktop-hero"',
            'id="timeline-scheduler-desktop-hero"',
            'id="timeline-approver-banner"',
            'class="timeline-scroll-hint no-print"',
        ):
            self.assertIn(marker, panel, marker)

        for marker in (
            'id="offline-schedule-panel"',
            'id="offline-schedule-notice"',
            'id="timeline-sticky-h-scroll"',
            'id="timeline-scroll-wrapper"',
            'id="main-grid-table"',
            'id="timeline-bottom-scroll"',
            'class="calendar-legend',
        ):
            self.assertNotIn(marker, panel, marker)

    def test_calendar_surface_stays_after_panel_in_existing_order(self):
        _, panel_end, _ = self._intro_panel()
        positions = [
            self.timeline.index('id="timeline-sticky-h-scroll"'),
            self.timeline.index('id="timeline-scroll-wrapper"'),
            self.timeline.index('id="timeline-bottom-scroll"'),
            self.timeline.index('class="calendar-legend calendar-legend-compact'),
        ]

        self.assertTrue(all(panel_end < position for position in positions))
        self.assertEqual(positions, sorted(positions))

    def test_collapsed_utility_rail_boundary_and_control_order(self):
        row_start = self.timeline.index('<div class="timeline-intro-toggle-row')
        panel_start = self.timeline.index('<div id="timeline-collapsible-intro"')
        sticky_start = self.timeline.index('id="timeline-sticky-h-scroll"')
        rail_start = self.timeline.index('id="timeline-collapsed-utility-rail"')
        row_markup = self.timeline[row_start:panel_start]

        self.assertLess(row_start, rail_start)
        self.assertLess(rail_start, panel_start)
        self.assertLess(panel_start, sticky_start)
        self.assertIn('class="timeline-collapsed-utility-rail"', row_markup)
        self.assertIn('id="timeline-intro-toggle"', row_markup)

        rail_open = self.timeline.rfind('<div', row_start, rail_start)
        rail_end = self.timeline.index('</div>', rail_start)
        rail = self.timeline[rail_open:rail_end]
        ordered_ids = (
            'timeline-collapsed-prev-week',
            'timeline-collapsed-week-range',
            'timeline-collapsed-today',
            'timeline-collapsed-next-week',
            'timeline-collapsed-find-row',
        )
        positions = [rail.index(f'id="{element_id}"') for element_id in ordered_ids]
        self.assertEqual(positions, sorted(positions))
        toggle_start = row_start + row_markup.index('id="timeline-intro-toggle"')
        self.assertLess(rail_end, toggle_start)

    def test_collapsed_rail_reuses_navigation_focus_and_range_label_flow(self):
        rail_start = self.timeline.index('id="timeline-collapsed-utility-rail"')
        rail_open = self.timeline.rfind('<div', 0, rail_start)
        rail_end = self.timeline.index('</div>', rail_start)
        rail = self.timeline[rail_open:rail_end]

        for handler in (
            'onclick="changeWeek(-1)"',
            'onclick="changeWeek(0)"',
            'onclick="changeWeek(1)"',
            'onclick="focusLoggedInEngineerRow(true)"',
        ):
            self.assertIn(handler, rail, handler)

        labels_start = self.timeline.index('function updateTimelineRangeLabels')
        labels_end = self.timeline.index('function syncMobileTimelineData', labels_start)
        labels_flow = self.timeline[labels_start:labels_end]
        self.assertIn('timeline-collapsed-week-range', labels_flow)
        self.assertIn('current_range', labels_flow)

        controller = self._intro_controller()
        for marker in (
            "const rail = document.getElementById('timeline-collapsed-utility-rail')",
            "const collapsedWeekDisplay = document.getElementById('timeline-collapsed-week-range')",
            "rail.hidden = !shouldCollapse",
            "row.classList.toggle('timeline-intro-row-collapsed', shouldCollapse)",
        ):
            self.assertIn(marker, controller, marker)

    def test_find_my_row_is_conditionally_hidden_and_non_tabbable(self):
        find_match = re.search(
            r'<button(?P<button>[^>]*id="timeline-collapsed-find-row"[^>]*)>',
            self.timeline,
        )
        self.assertIsNotNone(find_match, "collapsed Find My Row control is missing")
        if find_match is None:
            return
        find_button = find_match.group("button")
        self.assertIn('hidden', find_button)
        self.assertIn('aria-hidden="true"', find_button)
        self.assertIn('tabindex="-1"', find_button)
        self.assertNotIn('disabled', find_button.lower())

        focus_sync_start = self.timeline.index('function syncTimelineCollapsedFindRow')
        focus_sync_end = self.timeline.index('function updateTimelineEngineerFocusStrip', focus_sync_start)
        focus_sync = self.timeline[focus_sync_start:focus_sync_end]
        for marker in (
            'isDesktopEngineerTimelineFocusAvailable()',
            'findRow.hidden = !available',
            "findRow.setAttribute('aria-hidden', String(!available))",
            'findRow.tabIndex = available ? 0 : -1',
        ):
            self.assertIn(marker, focus_sync, marker)
        self.assertIn('syncTimelineCollapsedFindRow();', self.timeline[focus_sync_end:])

    def test_collapsed_rail_controls_have_accessible_names_and_live_range(self):
        for element_id in (
            'timeline-collapsed-prev-week',
            'timeline-collapsed-today',
            'timeline-collapsed-next-week',
            'timeline-collapsed-find-row',
            'timeline-intro-toggle',
        ):
            match = re.search(
                rf'<button(?P<button>[^>]*id="{re.escape(element_id)}"[^>]*)>',
                self.timeline,
            )
            self.assertIsNotNone(match, element_id)
            if match is None:
                continue
            button = match.group("button")
            self.assertIn('type="button"', button, element_id)
            self.assertRegex(button, r'aria-label="[^"]+"', element_id)
            self.assertRegex(button, r'title="[^"]+"', element_id)

        range_match = re.search(
            r'<[^>]*id="timeline-collapsed-week-range"[^>]*>',
            self.timeline,
        )
        self.assertIsNotNone(range_match)
        if range_match is not None:
            self.assertIn('aria-live="polite"', range_match.group(0))
            self.assertIn('aria-atomic="true"', range_match.group(0))

    def test_collapsed_rail_is_compact_desktop_only_and_sticky_only_when_active(self):
        self.assertIn('.timeline-collapsed-utility-rail {', self.timeline)
        self.assertRegex(
            self.timeline,
            r'\.timeline-collapsed-utility-rail\s*\{[^}]*display:\s*none',
        )
        self.assertRegex(
            self.timeline,
            r'@media\s*\(min-width:\s*769px\)[\s\S]*?'
            r'\.timeline-intro-toggle-row\.timeline-intro-row-collapsed\s*\{'
            r'[^}]*position:\s*sticky[^}]*height:\s*42px',
        )
        self.assertRegex(
            self.timeline,
            r'\.timeline-intro-row-collapsed\s+\.timeline-collapsed-utility-rail\s*\{'
            r'[^}]*display:\s*flex',
        )
        self.assertRegex(
            self.timeline,
            r'@media\s*\(min-width:\s*769px\)\s+and\s+\(max-width:\s*980px\)',
        )

        sticky_start = self.timeline.index('function initTimelineStickyHeaderPolish')
        sticky = self.timeline[sticky_start:]
        for marker in (
            "const collapsedRail = document.getElementById('timeline-intro-toggle-row')",
            'collapsedRail.getBoundingClientRect().height',
            'const effectiveToolbarHeight = toolbarHeight + collapsedRailHeight',
            "--timeline-sticky-scrollbar-offset",
            "--timeline-grid-maxheight-offset",
        ):
            self.assertIn(marker, sticky, marker)

    def test_mobile_and_print_hide_rail_and_reset_intro_state(self):
        self.assertRegex(
            self.timeline,
            r'@media\s*\(max-width:\s*768px\)[\s\S]*?'
            r'\.timeline-collapsed-utility-rail\s*\{'
            r'[^}]*display:\s*none\s*!important',
        )
        self.assertRegex(
            self.timeline,
            r'@media\s*print\s*\{[\s\S]*?'
            r'\.timeline-collapsed-utility-rail\s*\{'
            r'[^}]*display:\s*none\s*!important',
        )
        controller = self._intro_controller()
        self.assertIn("window.matchMedia('(min-width: 769px)')", controller)
        self.assertIn('setTimelineIntroCollapsed(false, true)', controller)
        self.assertIn('syncTimelineCollapsedFindRow();', controller)


    def test_collapse_styles_are_desktop_only_and_reset_for_mobile_and_print(self):
        self.assertRegex(
            self.timeline,
            r"@media\s*\(min-width:\s*769px\)[\s\S]*?"
            r"\.timeline-intro-panel\.timeline-intro-collapsed\s*\{"
            r"[^}]*display:\s*none\s*!important",
        )
        self.assertRegex(
            self.timeline,
            r"@media\s*\(max-width:\s*768px\)[\s\S]*?"
            r"\.timeline-intro-toggle-row\s*\{"
            r"[^}]*display:\s*none\s*!important",
        )
        self.assertRegex(
            self.timeline,
            r"@media\s*\(max-width:\s*768px\)[\s\S]*?"
            r"\.timeline-intro-panel\.timeline-intro-collapsed\s*\{"
            r"[^}]*display:\s*block\s*!important",
        )
        self.assertRegex(
            self.timeline,
            r"@media\s*print\s*\{[\s\S]*?"
            r"\.timeline-intro-toggle-row\s*\{"
            r"[^}]*display:\s*none\s*!important",
        )
        self.assertRegex(
            self.timeline,
            r"@media\s*print\s*\{[\s\S]*?"
            r"\.timeline-intro-panel\.timeline-intro-collapsed\s*\{"
            r"[^}]*display:\s*block\s*!important",
        )

    def test_controller_switches_labels_icons_and_aria_state(self):
        controller = self._intro_controller()

        for marker in (
            "function setTimelineIntroCollapsed",
            "function toggleTimelineIntro",
            "function syncTimelineIntroViewport",
            "window.matchMedia('(min-width: 769px)')",
            "panel.classList.toggle('timeline-intro-collapsed', shouldCollapse)",
            "toggle.setAttribute('aria-expanded', String(!shouldCollapse))",
            "'Collapse calendar header'",
            "'Expand calendar header'",
            "'fa-chevron-up'",
            "'fa-chevron-down'",
            "window.dispatchEvent(new Event('resize'))",
            "setTimelineIntroCollapsed(false)",
        ):
            self.assertIn(marker, controller, marker)

    def test_controller_is_manual_and_does_not_persist_or_auto_hide(self):
        controller = self._intro_controller()

        self.assertNotIn("setInterval", controller)
        self.assertNotIn("window.scrollY", controller)
        self.assertNotIn("addEventListener('scroll'", controller)

    def test_collapsed_preference_is_browser_local_and_loaded_separately(self):
        self.assertIn(
            "const TIMELINE_INTRO_COLLAPSED_STORAGE_KEY = 'timelineDesktopIntroCollapsed';",
            self.timeline,
        )
        for marker in (
            "function getTimelineIntroCollapsedPreference",
            "localStorage.getItem(TIMELINE_INTRO_COLLAPSED_STORAGE_KEY)",
            "function saveTimelineIntroCollapsedPreference",
            "function setTimelineIntroCollapsed(collapsed, refreshSticky=false, persistPreference=false)",
            "if(persistPreference && isDesktop && !isPrint)",
            "saveTimelineIntroCollapsedPreference(shouldCollapse)",
            "setTimelineIntroCollapsed(getTimelineIntroCollapsedPreference())",
        ):
            self.assertIn(marker, self.timeline, marker)
        self.assertRegex(
            self.timeline,
            r"localStorage\.setItem\(\s*TIMELINE_INTRO_COLLAPSED_STORAGE_KEY",
        )

        controller = self._intro_controller()
        self.assertIn("setTimelineIntroCollapsed(shouldCollapse, true, true)", controller)
        self.assertNotIn("TIMELINE_VIEW_STATE_KEY", controller)
        self.assertNotIn("weekOffset", controller)

    def test_cache_version_and_everyone_release_are_present(self):
        self.assertIn(
            "medical-service-pwa-offline-navigation-v127-tsr-contact-suggestions",
            self.app,
        )

        release = next(
            (
                item
                for item in self.releases["releases"]
                if item.get("release_key") == "2026-09-03-timeline-collapsed-preference"
            ),
            None,
        )
        self.assertIsNotNone(release, "collapsed preference release is missing")
        if release is None:
            return
        self.assertEqual(release["release_date"], "2026-09-03")
        self.assertTrue(release["is_published"])
        self.assertTrue(release["items"])
        self.assertTrue(
            any("everyone" in item.get("audiences", []) for item in release["items"])
        )
        self.assertTrue(
            any("browser" in item.get("description", "").lower() for item in release["items"])
        )
        self.assertTrue(
            any(
                item.get("release_key") == "2026-09-03-timeline-collapsed-utility-rail"
                for item in self.releases["releases"]
            ),
            "historical utility rail release must remain",
        )


if __name__ == "__main__":
    unittest.main()
