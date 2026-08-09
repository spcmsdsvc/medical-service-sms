"""The service worker's offline fallback for API reads must be honest.

An uncached API GET with the server unreachable used to resolve as the /offline
PAGE carrying status 200. A caller that checked `response.ok` concluded success
and then died at `res.json()` with a SyntaxError, so a device that was merely
offline reported itself as a corrupt payload -- which is how it was first
mistaken for one during the 2026-08-07 verification pass.

Verified in a real browser against a genuinely stopped server before these tests
were written: the API read returns 503 / application/json / offline:true, while a
navigation still returns the offline HTML page.
"""

import pathlib
import re
import unittest

from tests.sw_cache_version import assert_cache_version_at_least


ROOT = pathlib.Path(__file__).resolve().parents[1]


class OfflineApiFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')

    def _service_worker_source(self):
        # The worker is a raw string inside app.py, so slice it rather than
        # searching the whole module and matching unrelated server code.
        start = self.app_source.index("sw = r\"\"\"const CACHE_VERSION")
        end = self.app_source.index('"""', start + 10)
        return self.app_source[start:end]

    def test_the_api_fallback_is_a_real_error_not_the_offline_page(self):
        sw = self._service_worker_source()
        self.assertIn('function offlineApiResponse()', sw)
        self.assertIn('status: 503', sw)
        # A 200 here is the whole defect: it is what made callers believe the
        # request had succeeded.
        self.assertNotIn('status: 200', sw)

    def test_networkfirst_uses_it_and_no_longer_returns_the_offline_page(self):
        sw = self._service_worker_source()
        network_first = sw[sw.index('async function networkFirst('):sw.index('async function fieldNavigationFirst(')]
        self.assertIn('return offlineApiResponse();', network_first)
        self.assertNotIn("caches.match('/offline')", network_first)

    def test_navigations_still_fall_back_to_the_offline_page(self):
        """The positive control, and the thing most easily broken by this fix.

        A page must still get HTML. If fieldNavigationFirst ever started
        returning the JSON error, an offline field engineer would get a raw
        payload dumped in the browser instead of the offline screen.
        """
        sw = self._service_worker_source()
        field_nav = sw[sw.index('async function fieldNavigationFirst('):sw.index('async function cacheFirst(')]
        self.assertIn("return caches.match('/offline');", field_nav)
        self.assertNotIn('offlineApiResponse', field_nav)

    def test_the_body_stays_parseable_json_for_both_caller_styles(self):
        sw = self._service_worker_source()
        helper = sw[sw.index('function offlineApiResponse()'):sw.index('async function networkFirst(')]
        self.assertIn("'Content-Type': 'application/json'", helper)
        self.assertIn('offline: true', helper)
        # app-analytics.js renders `data.message`; the schedule/leave paths read
        # `error`. Both must be present or one of them shows a bare status code.
        self.assertIn('error:', helper)
        self.assertIn('message:', helper)

    def test_cache_version_bumped_so_devices_actually_receive_this(self):
        # A floor, never a pinned version -- pinning is the anti-pattern that has
        # already broken this suite twice on a required bump.
        assert_cache_version_at_least(self, 84, self.app_source)


class BackupConcurrencyTests(unittest.TestCase):
    """The Procfile is the fix for the backup blocking every other user.

    A single sync worker meant one superadmin downloading a backup froze the app
    for everyone, and a build that outran the worker timeout had its worker
    killed. gthread moves the arbiter heartbeat into the accept loop, so a slow
    request no longer looks like a hung worker.
    """

    @classmethod
    def setUpClass(cls):
        cls.procfile = (ROOT / 'Procfile').read_text(encoding='utf-8')

    def test_the_web_process_can_serve_more_than_one_request_at_a_time(self):
        self.assertIn('--worker-class gthread', self.procfile)
        threads = re.search(r'--threads\s+(\d+)', self.procfile)
        self.assertIsNotNone(threads, 'gthread without --threads still serializes requests')
        self.assertGreaterEqual(int(threads.group(1)), 2)

    def test_the_timeout_leaves_room_for_a_backup_build(self):
        timeout = re.search(r'--timeout\s+(\d+)', self.procfile)
        self.assertIsNotNone(timeout)
        self.assertGreaterEqual(int(timeout.group(1)), 180)

    def test_a_single_worker_keeps_one_sqlite_writer(self):
        """Threads, not processes, on purpose.

        Two worker processes would contend on the same SQLite file with a 60s
        busy timeout. Threads share one engine and connection pool, so this
        stays a deliberate choice rather than something to 'optimise' later.
        """
        workers = re.search(r'--workers\s+(\d+)', self.procfile)
        self.assertIsNotNone(workers)
        self.assertEqual(int(workers.group(1)), 1)

    def test_streaming_was_a_decision_and_is_recorded_as_one(self):
        # Streaming was the recorded plan and was rejected on measurement. If
        # someone reverses that, this docstring should be updated with them --
        # it is the only place the trade-off is written down next to the code.
        app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        route = app_source[app_source.index("@app.route('/admin/download-backup')"):]
        route = route[:route.index('    if not is_superadmin_user():')]
        self.assertIn('Content-Length', route)
        self.assertIn('gthread', route)


class ShellTouchTargetTests(unittest.TestCase):
    """Controls in the layout shell appear on every page.

    Measured at 375px before the fix: skip link 40.6px tall, mobile-nav bell
    40px, sidebar bell 34px, sidebar hamburger 32px, and both appearance buttons
    44px tall but only 34px and 42px WIDE. Re-measured after: all 44x44, sidebar
    header overflow 0, desktop unchanged at 34/34/32.
    """

    @classmethod
    def setUpClass(cls):
        cls.shell_css = (ROOT / 'static' / 'css' / 'app-shell.css').read_text(encoding='utf-8')

    def _mobile_foundation(self):
        marker = '   SHARED MOBILE FOUNDATION'
        start = self.shell_css.index(marker)
        end = self.shell_css.index('@media print', start)
        return self.shell_css[start:end]

    def test_every_shell_control_has_a_touch_minimum(self):
        mobile = self._mobile_foundation()
        for selector in (
            '.skip-to-content',
            '.sidebar-header .changelog-header-button',
            '.sidebar-header .appearance-header-button',
            '.mobile-nav .changelog-header-button',
            '.mobile-nav .appearance-header-button',
            '.toggle-btn',
        ):
            with self.subTest(selector=selector):
                self.assertIn(selector, mobile)

    def test_the_minimum_covers_width_as_well_as_height(self):
        """A target is 44x44.

        Both appearance buttons already passed on height and failed on width,
        which is exactly the miss a height-only rule leaves behind.
        """
        mobile = self._mobile_foundation()
        block = mobile[mobile.index('.skip-to-content,\n    .sidebar-header .changelog-header-button'):]
        block = block[:block.index('}')]
        self.assertIn('min-width: var(--mobile-touch-height)', block)
        self.assertIn('min-height: var(--mobile-touch-height)', block)

    def test_the_touch_minimum_is_scoped_to_touch_widths(self):
        # Desktop keeps its compact 34/34/32 sidebar; the rule must live inside
        # the mobile media query, not at the top level.
        top_level = self.shell_css[:self.shell_css.index('   SHARED MOBILE FOUNDATION')]
        self.assertIn('width: 34px', top_level)
        self.assertNotIn('min-width: var(--mobile-touch-height)', top_level)

    def test_the_sidebar_header_may_wrap_so_the_controls_are_not_shrunk_back(self):
        # Title + three 44px controls measured 253px of content in a 240px
        # sidebar. Without wrapping, flex shrinks them under the minimum again.
        mobile = self._mobile_foundation()
        self.assertIn('.sidebar-header {', mobile)
        self.assertIn('flex-wrap: wrap;', mobile)

    def test_the_touch_height_token_is_still_44(self):
        # Everything above is expressed against this token, so it is the single
        # thing that could silently lower all of them at once.
        self.assertIn('--mobile-touch-height: 44px;', self.shell_css)


if __name__ == '__main__':
    unittest.main()
