"""Focused contracts for faster Calendar week navigation."""

import json
import pathlib
import subprocess
import textwrap
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "templates" / "timeline.html").read_text(encoding="utf-8")
APP_SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")
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
        self.assertIn("await refreshTimelineGrid({forceRefresh: false, navigation: true});", change_block)
        self.assertIn("setTimelineWeekNavigationBusy(false", change_block)

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
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_current_worker_marker_and_release_are_updated(self):
        self.assertIn("medical-service-pwa-offline-navigation-v150-mobile-navigation-inventory-stability", APP_SOURCE)
        matches = [
            release
            for release in RELEASES.get("releases", [])
            if release.get("release_key") == "2026-09-08-calendar-week-navigation"
        ]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].get("release_date"), "2026-09-08")
        self.assertTrue(matches[0].get("is_published"))
        self.assertTrue(any(item.get("category") == "Calendar" for item in matches[0].get("items", [])))


if __name__ == "__main__":
    unittest.main()
