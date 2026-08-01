"""Offline features must survive the connection an engineer actually has.

Two failures this pins, both of which lost work in the field rather than degrading:

1. A phone showing bars with an unreachable server. navigator.onLine reports a live radio, so
   the TSR save took the online path, the TSR-number fetch threw, the preview never opened and
   nothing was queued. The schedule queue has handled weak signal since 709106c; this is the
   TSR side catching up.

2. A service worker version bump. Assets carry a ?v= cache-buster and the cache key includes
   the query, while activate() deletes every older cache. A device that updated and then lost
   signal asked for a URL that had never been stored, cacheFirst threw with no fallback, and
   app-offline-schedule.js failed to load -- silently removing offline schedule creation,
   because the save gate gives no message when window.offlineSchedule is missing.
"""

import os
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_offline_schedule_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))


class ServiceWorkerAssetFallbackTests(unittest.TestCase):
    """A cache-busted asset must still load offline."""

    @classmethod
    def setUpClass(cls):
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.cache_first = source.split('async function cacheFirst(request) {')[1].split('\nasync function ')[0]

    def test_a_network_failure_is_caught(self):
        """Without this the script tag simply fails and the feature vanishes silently."""
        self.assertIn('catch (err)', self.cache_first)

    def test_a_version_bumped_asset_falls_back_to_the_precached_copy(self):
        self.assertIn('ignoreSearch: true', self.cache_first)

    def test_the_fallback_never_pre_empts_the_network(self):
        """Ordering is load-bearing in the other direction.

        If the version-agnostic match ran first, a bumped asset would keep serving the old
        copy to an online device forever -- which is the whole reason the ?v= exists.
        """
        fetch_at = self.cache_first.find('await fetch(request)')
        fallback_at = self.cache_first.find('ignoreSearch: true')
        self.assertGreater(fetch_at, -1, 'the network attempt is missing')
        self.assertGreater(fallback_at, -1, 'the fallback is missing')
        self.assertLess(fetch_at, fallback_at,
                        'the network must be tried before the version-agnostic fallback')

    def test_an_asset_that_was_never_cached_still_fails(self):
        """The fallback must not turn a genuinely missing asset into a silent success."""
        self.assertIn('throw err;', self.cache_first)

    def test_the_offline_module_is_precached_under_its_bare_path(self):
        """The fallback only works because the precache holds the unversioned URL."""
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        self.assertIn("'/static/js/app-offline-schedule.js',", source)


class WeakSignalTSRSaveTests(unittest.TestCase):
    """A live radio and a dead server must queue, not lose the TSR."""

    @classmethod
    def setUpClass(cls):
        cls.tsr = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')

    def test_a_failed_number_assignment_falls_back_to_queueing(self):
        self.assertIn('buildOfflineShapedPayload', self.tsr)
        self.assertIn('queuedForWeakSignal = true', self.tsr)

    def test_only_connection_failures_fall_back(self):
        """A refusal the server actually meant must still stop and be shown.

        Falling back on every error would hide a rejected TSR number or a permission failure
        behind a queued item that can never sync.
        """
        self.assertIn('if(!isRetriableTSRSyncError(prepareError)) throw prepareError;', self.tsr)

    def test_the_engineer_is_told_it_was_queued(self):
        """Silently queueing a TSR the engineer believes was saved online is worse than failing."""
        self.assertIn('(!navigator.onLine || queuedForWeakSignal) && !isRevision', self.tsr)

    def test_the_offline_shape_is_built_in_one_place(self):
        """Both the offline and weak-signal paths must produce an identical payload.

        Two copies of this construction is how the pending-schedule token got dropped from one
        of them before.
        """
        self.assertEqual(
            self.tsr.count('const buildOfflineShapedPayload = async () => {'), 1,
            'the offline payload shape should have exactly one builder'
        )
        preview = self.tsr.split('const buildOfflineShapedPayload')[1].split('payload.submission_token =')[0]
        self.assertIn('pending_schedule_token:', preview)
        self.assertIn('getStandaloneScheduleRealId(selectedSchedule)', preview)


class ShellPrecacheTests(unittest.TestCase):
    """The app shell is the last-resort offline fallback, so what goes in it matters."""

    @classmethod
    def setUpClass(cls):
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.precache = source.split('async function precacheShellEntry(cache, url) {')[1].split('\nself.addEventListener')[0]
        cls.install = source.split("self.addEventListener('install'")[1].split('});')[0]

    def test_a_login_page_is_never_stored_as_a_protected_route(self):
        """Install was the one write path that did not check this.

        A worker installing while the session is invalid stored the login page under /timeline
        and /offline-tsr, and offline navigation falls back to the shell.
        """
        self.assertIn('isLoginLikeResponse(request, response)', self.precache)

    def test_login_itself_is_still_cached(self):
        """The signed-out copy of /login is the one login page worth keeping."""
        self.assertIn("url !== '/login'", self.precache)

    def test_cross_origin_assets_still_use_cache_add(self):
        """An explicit fetch of a CDN asset is opaque with ok === false, so it would be
        skipped and bootstrap would stop being available offline."""
        self.assertIn("if (!url.startsWith('/')) return cache.add(url);", self.precache)

    def test_install_goes_through_the_guarded_helper(self):
        self.assertIn('precacheShellEntry(cache, url)', self.install)
        self.assertNotIn('cache.add(url)', self.install)


class OfflineQueueUnwrapTests(unittest.TestCase):
    """A missing IndexedDB record must never read as present."""

    @classmethod
    def setUpClass(cls):
        cls.module = (ROOT / 'static' / 'js' / 'app-offline-schedule.js').read_text(encoding='utf-8')

    def test_the_result_box_is_unwrapped_by_tag(self):
        """The old test was `result.value !== undefined`, so a keyed get() that missed handed
        back the box -- and a box is truthy."""
        self.assertIn('__isResultBox', self.module)
        self.assertNotIn('result.value !== undefined ? result.value : result', self.module)

    def test_the_box_is_tagged_where_it_is_created(self):
        request_value = self.module.split('function requestValue(request) {')[1].split('\n    }')[0]
        self.assertIn('__isResultBox: true', request_value)


class SilentOfflineSaveTests(unittest.TestCase):
    """A save that cannot happen must say so."""

    @classmethod
    def setUpClass(cls):
        cls.timeline = (ROOT / 'templates' / 'timeline.html').read_text(encoding='utf-8')

    def test_a_failed_offline_save_is_reported(self):
        """saveShift() runs from an inline onclick with no catch, so the old rethrow became an
        unhandled rejection and the button appeared to do nothing at all."""
        self.assertIn('describeUnavailableOfflineSave', self.timeline)
        save_shift = self.timeline.split('async function saveShift() {')[1].split('\n    /**')[0]
        self.assertNotIn('throw networkError;', save_shift)

    def test_each_deliberate_exclusion_is_named(self):
        """Engineer-only and create-only are decisions from 709106c, not defects. The engineer
        still has to be told which one they hit."""
        describe = self.timeline.split('function describeUnavailableOfflineSave(')[1].split('\n    }')[0]
        self.assertIn('isEditingExisting', describe)
        self.assertIn('!isEngineer', describe)
        self.assertIn('isSupported()', describe)


class ServiceWorkerCacheVersionTests(unittest.TestCase):
    def test_the_cache_version_moved_for_the_changed_shell(self):
        """/offline-tsr is precached, so devices need the new copy of the page."""
        from tests.sw_cache_version import assert_cache_version_at_least
        assert_cache_version_at_least(self, 59)


if __name__ == '__main__':
    unittest.main()
