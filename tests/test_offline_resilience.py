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


class OfflineTSRStorageStrategyTests(unittest.TestCase):
    """Large TSR files must live in IndexedDB, not duplicated localStorage JSON."""

    @classmethod
    def setUpClass(cls):
        cls.tsr = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')

    def test_new_file_selection_does_not_base64_encode_photos(self):
        file_builder = self.tsr.split('async function fileToQueuedAttachment(')[1].split('\nfunction normalizeQueuedAttachments')[0]
        self.assertNotIn('blobToBase64Payload', file_builder)
        self.assertIn('blob: file', file_builder)

    def test_queue_mirror_is_metadata_only_and_backup_is_not_written(self):
        mirror = self.tsr.split('function writeOfflineTSRQueueLocalStorageFallback(')[1].split('\nasync function loadOfflineTSRQueueStore')[0]
        self.assertIn('projectOfflineTSRQueueItemForLocalStorage', mirror)
        self.assertIn('localStorage.setItem(OFFLINE_TSR_QUEUE_KEY', mirror)
        self.assertIn('localStorage.removeItem(OFFLINE_TSR_QUEUE_BACKUP_KEY)', mirror)
        self.assertNotIn('localStorage.setItem(OFFLINE_TSR_QUEUE_BACKUP_KEY', mirror)
        self.assertNotIn('JSON.stringify(normalizedQueue)', mirror)

    def test_queue_blob_failure_surfaces_without_a_base64_fallback(self):
        prepare = self.tsr.split('async function prepareOfflineTSRQueueItemBlobs(')[1].split('\nasync function resolveQueuedAttachmentDataURL')[0]
        self.assertIn("storageError.code = 'offline_storage_unavailable'", prepare)
        self.assertIn('throw storageError;', prepare)
        self.assertNotIn('Keeping data_url fallback', prepare)

    def test_offline_queue_requires_a_generated_pdf_blob(self):
        queue = self.tsr.split('async function queueStandaloneTSROffline(')[1].split('\nlet offlineTSRSyncRunning')[0]
        self.assertIn('if(!pdfPackage?.blob)', queue)
        self.assertIn("storageError.phase = 'storing_tsr_pdf'", queue)

    def test_durable_queue_failure_restores_previous_in_memory_state(self):
        persist = self.tsr.split('async function persistOfflineTSRQueueStore(')[1].split('\nasync function refreshOfflineTSRQueueStore')[0]
        self.assertIn('const previousCache = offlineTSRQueueCache', persist)
        self.assertIn('offlineTSRQueueCache = previousCache', persist)
        self.assertIn('if(requireDurable)', persist)

    def test_drafts_convert_attachments_to_blob_references(self):
        draft = self.tsr.split('async function prepareStandaloneTSRDraftPayload(')[1].split('\nasync function rehydrateStandaloneTSRDraftPayload')[0]
        self.assertIn("'draft_attachment'", draft)
        self.assertIn('payload.attachments = preparedAttachments', draft)
        fallback = self.tsr.split('function saveStandaloneTSRDraftToLocalStorageFallback(')[1].split('\nfunction loadStandaloneTSRDraftFromLocalStorageFallback')[0]
        self.assertIn('projectOfflineTSRPayloadForLocalStorage', fallback)
        self.assertNotIn('JSON.stringify(data || {})', fallback)

    def test_final_save_reports_actual_draft_recovery_result(self):
        self.assertIn('function showTSRFinalSaveRecovery(', self.tsr)
        self.assertIn("draftResult?.failed || draftResult?.source === 'none'", self.tsr)
        self.assertIn('Download PDF now', self.tsr)
        self.assertIn('attachments_not_durable', self.tsr)

    def test_storage_pressure_warning_is_available_before_writes(self):
        self.assertIn('navigator.storage.estimate()', self.tsr)
        self.assertIn('warnOfflineTSRStoragePressure', self.tsr)
        self.assertIn('await warnOfflineTSRStoragePressure();', self.tsr)

    def test_the_background_storage_check_is_throttled(self):
        """The silent call sits on the draft autosave path, which fires as the engineer types.

        navigator.storage.estimate() on every keystroke-triggered save is a cost nobody asked
        for; an explicit check must still measure every time.
        """
        warn = self.tsr.split('async function warnOfflineTSRStoragePressure(')[1].split('\nasync function ')[0]
        self.assertIn('OFFLINE_TSR_STORAGE_CHECK_INTERVAL_MS', warn)
        self.assertIn('if(silent &&', warn)
        # Positive control: the throttle must not swallow an explicit check.
        self.assertIn('offlineTSRStorageCheckedAt = checkedAt;', warn)

    def test_the_legacy_backup_is_only_dropped_after_it_has_been_read(self):
        """The load path reads that backup when the primary is empty -- that read is what
        migrates it. Removing it before then discards the only copy on a device whose
        IndexedDB came up empty."""
        mirror = self.tsr.split('function writeOfflineTSRQueueLocalStorageFallback(')[1].split('\nasync function loadOfflineTSRQueueStore')[0]
        self.assertIn('if(offlineTSRLegacyQueueRead){', mirror)
        loader = self.tsr.split('async function loadOfflineTSRQueueStore(')[1].split('\nasync function ')[0]
        self.assertIn('offlineTSRLegacyQueueRead = true;', loader)
        # Positive control: the backup must still be read on the way through.
        self.assertIn('readOfflineTSRQueueFromKey(OFFLINE_TSR_QUEUE_BACKUP_KEY)', loader)


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


class ExportsAreNeverCachedTests(unittest.TestCase):
    """An authenticated export must never be written to or served from the runtime cache.

    /export_timeline returns DIFFERENT CONTENT FOR THE SAME URL depending on who asks -- it
    redacts job titles and equipment for an HR account and does not for an admin -- while a
    cache entry is keyed on the URL alone. A superadmin's unredacted CSV was demonstrably
    returned to a logged-in HR session on the same browser, which is the leak 5278df2 fixed
    on the server and the service worker then reintroduced.

    These are source assertions because this project has no JavaScript runner for the
    generated worker. They are written as structural outcomes -- branch ordering, and the
    absence of any cache call inside the branch -- rather than as pinned text, matching
    ServiceWorkerAssetFallbackTests above. The behavioural proof is a browser pass: seed the
    cache as an admin, sign in as HR, and confirm the redacted file comes back, online and
    with the network genuinely stopped.
    """

    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.fetch_handler = cls.source.split("self.addEventListener('fetch', event => {")[1].split('\n});')[0]

    def test_exports_are_handled_before_the_navigation_branch(self):
        """Ordering is the whole fix.

        The Export button is `window.location.href = '/export_timeline?...'`, so the request
        arrives with mode 'navigate'. If the navigate branch ran first it would reach
        fieldNavigationFirst(), which caches every ok response and serves it back whenever
        the network throws -- so the leak would survive on exactly the path a real user takes.
        """
        export_at = self.fetch_handler.find("url.pathname.startsWith('/export_')")
        navigate_at = self.fetch_handler.find("request.mode === 'navigate'")
        self.assertGreater(export_at, -1, 'the export branch is missing')
        self.assertGreater(navigate_at, -1, 'the navigate branch is missing')
        self.assertLess(export_at, navigate_at,
                        'exports must be matched before the navigation branch')

    def test_the_export_branch_touches_no_cache_at_all(self):
        branch = self.fetch_handler.split("url.pathname.startsWith('/export_')")[1].split('return;')[0]
        self.assertIn('event.respondWith(fetch(request))', branch)
        for forbidden in ('caches.', 'cache.put', 'cache.match', 'RUNTIME_CACHE',
                          'networkFirst', 'staleWhileRevalidate', 'cacheFirst',
                          'fieldNavigationFirst'):
            self.assertNotIn(forbidden, branch,
                             f'the export branch must not reach {forbidden}')

    def test_exports_reach_no_other_strategy_later_in_the_handler(self):
        """Positive control on the negative: prove the branch actually returns.

        Without the `return;` the request would fall through to staleWhileRevalidate at the
        bottom of the handler, which serves a cached copy even while online -- the exact way
        the leak was first reproduced.
        """
        after_export = self.fetch_handler.split("url.pathname.startsWith('/export_')")[1]
        self.assertRegex(after_export.split('}')[1] if '}' in after_export else after_export,
                         r'\s*return;')

    def test_the_worker_was_bumped_so_poisoned_entries_are_evicted(self):
        """A fix that leaves the old cache in place fixes nothing on existing devices.

        activate() deletes every cache whose name is not the current APP_SHELL/RUNTIME pair,
        so renaming via CACHE_VERSION is what actually drops an already-poisoned entry.
        """
        from tests.sw_cache_version import assert_cache_version_at_least
        assert_cache_version_at_least(self, 71, self.source)
        activate = self.source.split("self.addEventListener('activate'")[1].split('});')[0]
        self.assertIn('caches.delete(key)', activate)


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


class ScheduleOptionIdentityTests(unittest.TestCase):
    """A picker option's identity must not depend on where it sits in an array.

    `normalizeStandaloneScheduleOptions` used to stamp `_offline_uid` from the array index, and
    that string is what a saved draft stores and later matches on. Any change in list
    composition renumbered every option after it and detached drafts from their schedules --
    which reached the field once already.
    """

    @classmethod
    def setUpClass(cls):
        cls.tsr = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')

    def test_identity_is_derived_from_the_schedule(self):
        builder = self.tsr.split('function buildStableScheduleOptionUid(')[1].split('\nfunction ')[0]
        for shape in ('`pending::${pendingToken}::${date}`', '`shift::${realId}::${date}`',
                      '`snap::${hashScheduleIdentity(schedule)}`'):
            self.assertIn(shape, builder)

    def test_no_call_site_passes_an_array_index(self):
        """The defect itself. A single surviving index caller reintroduces it."""
        self.assertNotIn('getStandaloneScheduleRuntimeId(schedule, index)', self.tsr)
        self.assertNotIn('getStandaloneScheduleRuntimeId(normalized, standaloneScheduleOptions.length)', self.tsr)
        runtime = self.tsr.split('function getStandaloneScheduleRuntimeId(')[1].split('\nfunction ')[0]
        self.assertNotIn('index', runtime)

    def test_a_stored_uid_is_never_trusted(self):
        """Drafts, queue items and the server's payload_json all freeze a selectedSchedule
        snapshot; reading the uid back out of one would resurrect a pre-change identity."""
        runtime = self.tsr.split('function getStandaloneScheduleRuntimeId(')[1].split('\nfunction ')[0]
        self.assertNotIn('schedule._offline_uid', runtime, 'the stored uid must never be read back')
        self.assertNotIn('return String(schedule._offline_uid)', runtime)
        self.assertIn('buildStableScheduleOptionUid(schedule)', runtime)

    def test_the_legacy_format_is_still_understood(self):
        legacy = self.tsr.split('function matchesLegacyScheduleUid(')[1].split('\nfunction ')[0]
        self.assertIn("segments[0] === 'pending'", legacy)
        self.assertIn('getStandaloneScheduleRealId(schedule)', legacy)
        # A legacy id whose date disagrees must not match a different day of the same chain.
        self.assertIn('legacyDate === scheduleDate', legacy)

    def test_comparisons_against_persisted_values_use_the_helper(self):
        """Every site where a stored selection meets a freshly computed one."""
        self.assertIn('function isSameScheduleSelection(', self.tsr)
        selected = self.tsr.split('function getSelectedStandaloneSchedule(')[1].split('\nfunction ')[0]
        self.assertIn('isSameScheduleSelection(selectedStandaloneScheduleId, item)', selected)
        # Positive control: the old exact-string comparison must be gone from that function.
        self.assertNotIn('String(getStandaloneScheduleRuntimeId(item)) === String(selectedStandaloneScheduleId)', selected)

    def test_in_progress_work_is_not_cleared_for_a_legacy_id(self):
        """The most destructive line on the page.

        A plain string test would read an old-format selection restored from a draft as a
        different schedule and wipe everything the engineer had typed, for every engineer, on
        their first re-selection after the change.
        """
        apply_fn = self.tsr.split('function applyScheduleToStandaloneTSR(')[1].split('\nfunction ')[0]
        self.assertIn('isSameScheduleSelection(selectedStandaloneScheduleId, schedule)', apply_fn)
        self.assertIn('!isSameSchedule && !awaitingScheduleRepick', apply_fn)
        # The clear must still happen for a genuinely different schedule.
        self.assertIn('clearStandaloneTSRWorkFieldsForScheduleChange();', apply_fn)

    def test_an_unmatched_draft_keeps_its_work_and_asks_for_a_schedule(self):
        apply_draft = self.tsr.split('function applyStandaloneTSRDraftData(')[1].split('\nfunction ')[0]
        self.assertIn('awaitingScheduleRepick = true', apply_draft)
        # It clears only the dead selection, never the fields.
        self.assertNotIn('clearStandaloneTSRWorkFieldsForScheduleChange', apply_draft)

    def test_a_resolved_selection_is_canonicalised_in_place(self):
        """Self-healing without a bulk rewrite: the next save persists the new format."""
        apply_draft = self.tsr.split('function applyStandaloneTSRDraftData(')[1].split('\nfunction ')[0]
        self.assertIn('selectedStandaloneScheduleId = String(getStandaloneScheduleRuntimeId(matchedOption))', apply_draft)


class ServiceWorkerCacheVersionTests(unittest.TestCase):
    def test_the_cache_version_moved_for_the_changed_shell(self):
        """/offline-tsr is precached, so devices need the new copy of the page."""
        from tests.sw_cache_version import assert_cache_version_at_least
        assert_cache_version_at_least(self, 62)


if __name__ == '__main__':
    unittest.main()
