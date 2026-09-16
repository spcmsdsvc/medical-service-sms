"""Focused contracts for faster Calendar week navigation."""

import json
import pathlib
import subprocess
import textwrap
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "templates" / "timeline.html").read_text(encoding="utf-8")
APP_SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")
APP_DARK_SOURCE = (ROOT / "static" / "css" / "app-dark-pages.css").read_text(encoding="utf-8")
RELEASES = json.loads((ROOT / "static" / "changelog" / "releases.json").read_text(encoding="utf-8"))


class TimelineWeekNavigationCacheTests(unittest.TestCase):
    def test_navigation_uses_cache_first_with_accessible_status(self):
        self.assertRegex(
            TEMPLATE,
            r'id="timeline-week-nav-status"[^>]*role="status"[^>]*aria-live="polite"',
        )
        self.assertIn("Checking for updates...", TEMPLATE)

        change_start = TEMPLATE.index("async function changeWeek(direction)")
        change_end = TEMPLATE.index("\n    function exportToExcel", change_start)
        change_block = TEMPLATE[change_start:change_end]
        self.assertIn("return navigateTimelineToWeekOffset(targetWeekOffset);", change_block)

        navigation_start = TEMPLATE.index("async function navigateTimelineToWeekOffset")
        navigation_end = TEMPLATE.index("\n\n    async function changeWeek", navigation_start)
        navigation_block = TEMPLATE[navigation_start:navigation_end]
        self.assertIn("await refreshTimelineGrid({forceRefresh: false, navigation: true});", navigation_block)
        self.assertIn("setTimelineWeekNavigationBusy(false", navigation_block)

    def test_forced_refresh_remains_default_and_navigation_preserves_cache(self):
        self.assertIn("async function refreshTimelineGrid(options={})", TEMPLATE)
        self.assertIn("const forceRefresh = options.forceRefresh !== false;", TEMPLATE)
        self.assertIn("if(forceRefresh){", TEMPLATE)
        self.assertIn("invalidateTimelineCache();", TEMPLATE)
        self.assertIn("async function loadGrid(options={})", TEMPLATE)
        self.assertIn("const forceRefresh = options.forceRefresh !== false;", TEMPLATE)
        self.assertIn("!forceRefresh && cached", TEMPLATE)

        refresh_start = TEMPLATE.index("async function refreshTimelineGrid(options={})")
        refresh_end = TEMPLATE.index("\n\n    function syncTimelineHorizontalScroll", refresh_start)
        refresh_block = TEMPLATE[refresh_start:refresh_end]
        self.assertIn("loadGrid({", refresh_block)
        self.assertIn("forceRefresh,", refresh_block)
        self.assertIn("navigation,", refresh_block)

    def test_shared_renderer_and_network_timestamp_semantics(self):
        self.assertIn("function renderTimelineGrid(data, renderOptions={})", TEMPLATE)
        self.assertIn("renderTimelineGrid(data, {", TEMPLATE)

        render_start = TEMPLATE.index("function renderTimelineGrid(data, renderOptions={})")
        render_end = TEMPLATE.index("\n\n    async function refreshTimelineGrid", render_start)
        render_block = TEMPLATE[render_start:render_end]
        self.assertIn("if(renderOptions.networkRefresh) markTimelineSuccessfulRefresh();", render_block)
        self.assertNotIn("markTimelineSuccessfulRefresh();\n    }", render_block)

    def test_generation_guards_and_same_key_request_deduplication_are_wired(self):
        for marker in (
            "let timelineDataGeneration = 0;",
            "const timelineDataRequests = new Map();",
            "function invalidateTimelineCache()",
            "function fetchTimelineDataForKey(",
            "requestGeneration !== timelineDataGeneration",
            "result.generation !== timelineDataGeneration",
            "isTimelineViewCurrent(",
        ):
            self.assertIn(marker, TEMPLATE, marker)

        preload_start = TEMPLATE.index("async function warmTimelineOfflineScheduleWindow")
        preload_end = TEMPLATE.index("\n\n\n    function applyTimelineSnapshotViewState", preload_start)
        self.assertIn("fetchTimelineDataForKey(", TEMPLATE[preload_start:preload_end])

    def test_cached_revalidation_failure_keeps_visible_week(self):
        revalidate_start = TEMPLATE.index("async function revalidateTimelineWeek(")
        revalidate_end = TEMPLATE.index("\n\nasync function loadGrid", revalidate_start)
        revalidate_block = TEMPLATE[revalidate_start:revalidate_end]
        self.assertIn("setTimelineWeekNavigationStatus('Checking for updates...'", revalidate_block)
        self.assertIn("Showing cached schedule", revalidate_block)
        self.assertIn("isTimelineViewCurrent(", revalidate_block)
        self.assertIn("renderTimelineGrid(result.data, {", revalidate_block)

    def test_request_helper_deduplicates_and_rejects_stale_generation_at_runtime(self):
        helper_start = TEMPLATE.index("function timelinePayloadIsValid(")
        helper_end = TEMPLATE.index("    function isTimelineStaleForScheduleAction", helper_start)
        helpers = TEMPLATE[helper_start:helper_end]
        node_script = textwrap.dedent(
            f"""
            const assert = require('assert');
            let timelineDataGeneration = 1;
            let timelineCache = {{}};
            const timelineDataRequests = new Map();
            const saved = [];
            let resolver = null;
            let calls = 0;
            const navigator = {{ onLine: true }};
            function buildFreshTimelineUrl(offset, branch) {{ return `/timeline?offset=${{offset}}&branch=${{branch}}`; }}
            function saveTimelineOfflineSnapshot(data, key, options) {{ saved.push({{ data, key, options }}); }}
            function shouldUseTimelineLitePayload() {{ return false; }}
            function fetchTimelineDataWithOfflineTimeout() {{
                calls += 1;
                return new Promise(resolve => {{ resolver = resolve; }});
            }}
            {helpers}
            (async function() {{
                const first = fetchTimelineDataForKey(2, 'ALL', 1);
                const second = fetchTimelineDataForKey(2, 'ALL', 1);
                assert.strictEqual(first, second, 'same-key requests must share one Promise');
                assert.strictEqual(calls, 1);
                resolver({{ ok: true, json: async () => ({{ days: [{{}}], engineers: [{{}}] }}) }});
                const result = await first;
                assert.strictEqual(result.generation, 1);
                assert.ok(timelineCache['2|ALL']);
                assert.strictEqual(saved.length, 1);

                resolver = null;
                const stalePromise = fetchTimelineDataForKey(3, 'ALL', 1);
                timelineDataGeneration = 2;
                resolver({{ ok: true, json: async () => ({{ days: [{{}}], engineers: [{{}}] }}) }});
                const stale = await stalePromise;
                assert.strictEqual(stale.generation, 1);
                assert.strictEqual(Boolean(timelineCache['3|ALL']), false, 'stale generations must not repopulate cache');
            }})().catch(error => {{ console.error(error); process.exit(1); }});
            """
        )
        result = subprocess.run(
            ["node", "-e", node_script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_current_worker_marker_and_release_are_updated(self):
        self.assertIn("medical-service-pwa-offline-navigation-v165-calendar-date-navigation", APP_SOURCE)
        matches = [
            release
            for release in RELEASES.get("releases", [])
            if release.get("release_key") == "2026-09-16-calendar-date-navigation"
        ]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].get("release_date"), "2026-09-16")
        self.assertTrue(matches[0].get("is_published"))
        self.assertTrue(any(item.get("category") == "Calendar" for item in matches[0].get("items", [])))

    def test_date_picker_has_three_surface_triggers_and_one_shared_modal(self):
        for element_id in (
            "timeline-expanded-date-picker",
            "timeline-collapsed-date-picker",
            "mobile-full-calendar-lite-date-picker",
        ):
            self.assertIn(f'id="{element_id}"', TEMPLATE)
            trigger_start = TEMPLATE.index(f'id="{element_id}"')
            trigger_tag_end = TEMPLATE.index('>', trigger_start)
            trigger_tag = TEMPLATE[trigger_start:trigger_tag_end]
            self.assertIn('data-timeline-week-nav="date"', trigger_tag)
            self.assertIn('data-timeline-date-trigger="true"', trigger_tag)
            self.assertIn('aria-haspopup="dialog"', trigger_tag)
            self.assertIn('aria-controls="timeline-date-picker-modal"', trigger_tag)
            self.assertIn('aria-label="Go to date"', trigger_tag)

        self.assertEqual(TEMPLATE.count('data-timeline-date-trigger="true"'), 3)
        self.assertEqual(TEMPLATE.count('id="timeline-date-picker-modal"'), 1)
        for marker in (
            'class="modal fade no-print timeline-date-picker-modal"',
            'role="dialog"',
            'aria-modal="true"',
            'aria-labelledby="timeline-date-picker-title"',
            'aria-describedby="timeline-date-picker-message"',
            'id="timeline-date-picker-form"',
            'type="date"',
            'id="timeline-date-picker-input"',
            'id="timeline-date-picker-error"',
            'id="timeline-date-picker-cancel"',
            'id="timeline-date-picker-submit"',
            'Go to date',
        ):
            self.assertIn(marker, TEMPLATE, marker)

    def test_date_picker_controller_reuses_offset_cache_busy_and_mobile_flow(self):
        for marker in (
            "function openTimelineDatePicker",
            "function submitTimelineDatePicker",
            "parseTimelineDateParam(rawDate)",
            "calculateTimelineWeekOffsetForDate(targetDate)",
            "function navigateTimelineToWeekOffset",
            "await refreshTimelineGrid({forceRefresh: false, navigation: true});",
            "timelineWeekNavigationBusy",
            "saveTimelineViewState();",
            "scrollMobileFullCalendarLiteToTop(true)",
            "mobileFullCalendarLiteForced = true",
        ):
            self.assertIn(marker, TEMPLATE, marker)

        controller_start = TEMPLATE.index("function openTimelineDatePicker")
        controller_end = TEMPLATE.index("\n\n    function exportToExcel", controller_start)
        controller = TEMPLATE[controller_start:controller_end]
        for marker in (
            "if(!rawDate)",
            "calculateTimelineWeekOffsetForDate(targetDate)",
            "navigateTimelineToWeekOffset(targetWeekOffset",
            "setTimelineWeekNavigationBusy(false, true)",
        ):
            self.assertIn(marker, controller, marker)
        self.assertIn("timeline-date-picker-error", TEMPLATE)

    def test_date_offset_math_handles_week_boundaries_and_year_crossing(self):
        helper_start = TEMPLATE.index("function parseTimelineDateParam(value)")
        helper_end = TEMPLATE.index("\n\n    function applyTimelineUrlDateTarget", helper_start)
        helpers = TEMPLATE[helper_start:helper_end]
        node_script = textwrap.dedent(
            f"""
            const assert = require('assert');
            const RealDate = globalThis.Date;
            const Date = class extends RealDate {{
                constructor(...args) {{
                    super(...(args.length ? args : [2026, 8, 16, 12, 0, 0, 0]));
                }}
                static now() {{ return new RealDate(2026, 8, 16, 12, 0, 0, 0).getTime(); }}
            }};
            {helpers}
            const expectOffset = (value, expected) => {{
                const parsed = parseTimelineDateParam(value);
                assert.ok(parsed, value);
                assert.strictEqual(calculateTimelineWeekOffsetForDate(parsed), expected, value);
            }};
            expectOffset('2026-09-16', 0); // Wednesday in current week.
            expectOffset('2026-09-13', -1); // Sunday belongs to prior Monday week.
            expectOffset('2026-09-14', 0); // Monday starts current week.
            expectOffset('2026-09-07', -1); // Prior week.
            expectOffset('2026-09-21', 1); // Following week.
            expectOffset('2026-01-01', -37); // Previous year boundary.
            expectOffset('2027-01-01', 15); // Following year boundary.
            assert.strictEqual(parseTimelineDateParam(''), null);
            assert.strictEqual(parseTimelineDateParam('2026-02-29'), null);
            assert.strictEqual(parseTimelineDateParam('2026-9-16'), null);
            """
        )
        result = subprocess.run(
            ["node", "-e", node_script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_date_navigation_styles_cover_responsive_print_and_dark_modes(self):
        for marker in (
            ".timeline-date-nav-trigger",
            ".timeline-date-picker-modal",
            "timeline-date-picker-input",
            "@media (max-width: 768px)",
            "@media print",
            ".timeline-week-nav-loading",
            ":focus-visible",
        ):
            self.assertIn(marker, TEMPLATE, marker)
        for marker in (
            ".timeline-date-nav-trigger",
            ".timeline-date-picker-modal",
            ".timeline-date-picker-input",
            ".timeline-date-picker-header .btn-close",
            "timeline-date-picker-error",
            ":focus-visible",
            ":disabled",
        ):
            self.assertIn(marker, APP_DARK_SOURCE, marker)

    def test_target_navigation_busy_guard_and_rollback_at_runtime(self):
        navigation_start = TEMPLATE.index("let timelineWeekNavigationBusy = false;")
        navigation_end = TEMPLATE.index("\n    function exportToExcel", navigation_start)
        navigation = TEMPLATE[navigation_start:navigation_end]
        node_script = textwrap.dedent(
            f"""
            const assert = require('assert');
            const controls = [];
            const labels = [{{ textContent: 'Current Week' }}, {{ textContent: 'Current Week' }}];
            const branch = {{ value: 'ALL' }};
            const stored = [];
            const localStorage = {{
                setItem(key, value) {{ stored.push(JSON.parse(value)); }},
                getItem() {{ return null; }}
            }};
            global.localStorage = localStorage;
            global.document = {{
                activeElement: null,
                getElementById(id) {{
                    if(id === 'branch-filter') return branch;
                    if(id === 'week-display') return labels[0];
                    if(id === 'timeline-collapsed-week-range') return labels[1];
                    return null;
                }},
                querySelectorAll() {{ return controls; }}
            }};
            global.timelineAlert = function(message) {{ global.alertMessage = message; }};
            global.renderMobileFullCalendarLite = function() {{}};
            global.scrollMobileFullCalendarLiteToTop = function() {{}};
            global.mobileFullCalendarLiteForced = false;
            global.mobileEngineerDesktopForced = false;
            global.pendingMobileFilterAfterLoad = '';
            let weekOffset = 0;
            function saveTimelineViewState() {{
                stored.push({{ weekOffset, branch: branch.value }});
            }}
            let shouldFail = false;
            let refreshCalls = 0;
            let firstRefreshResolve;
            async function refreshTimelineGrid() {{
                refreshCalls += 1;
                if(shouldFail) throw new Error('network');
                return new Promise(resolve => {{ firstRefreshResolve = resolve; }});
            }}
            {navigation}
            (async function() {{
                shouldFail = false;
                refreshCalls = 0;
                const first = navigateTimelineToWeekOffset(3);
                await Promise.resolve();
                assert.strictEqual(timelineWeekNavigationBusy, true);
                assert.strictEqual(await navigateTimelineToWeekOffset(4), false, 'busy navigation must be ignored');
                firstRefreshResolve();
                await first;
                assert.strictEqual(weekOffset, 3);
                assert.strictEqual(refreshCalls, 1);
                assert.strictEqual(stored.at(-1).weekOffset, 3);

                shouldFail = true;
                const failed = await navigateTimelineToWeekOffset(9);
                assert.strictEqual(failed, false);
                assert.strictEqual(weekOffset, 3, 'failed navigation restores the prior week');
                assert.strictEqual(stored.at(-1).weekOffset, 3, 'rollback persists the prior week');
                assert.match(global.alertMessage, /previous week remains displayed/);
                assert.strictEqual(timelineWeekNavigationBusy, false);
            }})().catch(error => {{ console.error(error); process.exit(1); }});
            """
        )
        result = subprocess.run(
            ["node", "-e", node_script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
