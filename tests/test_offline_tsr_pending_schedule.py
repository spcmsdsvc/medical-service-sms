"""Writing a TSR against a schedule that has not synced yet.

An engineer with no signal adds a schedule, does the work, and writes the TSR on site. The
schedule is still in the device queue and has no shift id, so the TSR waits behind it and is
pointed at the real shift once that schedule syncs.

Two things carry the most risk and get the most attention here. First, `/add_shift` now
returns the ids it created -- but only for a queued schedule, because an ordinary online save
must keep the response it has always had. Second, a TSR must never be posted with an
unresolved schedule: the server refuses it with a 400 the sync queue treats as fatal, so it
would park permanently with the engineer's work already written into it.
"""

import os
import pathlib
import tempfile
import unittest
from datetime import timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Pin an isolated database BEFORE importing app.py so the suite can never open the real
# scheduler.db.
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_offline_schedule_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402


class PendingScheduleServerSourceTests(unittest.TestCase):
    """Source-level guards on the route this feature changed."""

    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.add_shift = cls.app_source.split("@app.route('/add_shift'")[1].split('\n@app.route')[0]

    def test_ids_are_returned_through_one_builder(self):
        self.assertIn('def build_schedule_ids_response(', self.app_source)
        self.assertIn('build_schedule_ids_response(first_shift, created_shifts, replay=False)',
                      self.add_shift)

    def test_the_ids_response_carries_dates_beside_the_ids(self):
        """Without parallel dates a TSR for day four of a chain cannot find day four."""
        builder = self.app_source.split('def build_schedule_ids_response(')[1].split('\ndef ')[0]
        self.assertIn("'shift_ids'", builder)
        self.assertIn("'shift_dates'", builder)

    def test_the_ids_are_gated_on_a_creation_token(self):
        """An ordinary online save must keep the response shape it has always had."""
        self.assertIn('if creation_token and first_shift:', self.add_shift)

    def test_replay_is_still_resolved_before_the_collision_check(self):
        """Re-asserted here because this work edited add_shift.

        A queued schedule that already reached the server occupies its own slots, so running
        the collision check first would make every retry conflict with the copy it created
        last time.
        """
        token_at = self.add_shift.find('find_schedule_chain_by_creation_token')
        collision_at = self.add_shift.find('find_add_schedule_collision')
        # Positive control: assert both landmarks exist before comparing their order, so a
        # rename that deletes one cannot make this pass vacuously.
        self.assertGreater(token_at, -1, 'the replay lookup is missing')
        self.assertGreater(collision_at, -1, 'the collision check is missing')
        self.assertLess(token_at, collision_at)


class PendingScheduleDeviceSourceTests(unittest.TestCase):
    """The device contract: what must be true of the two queues' code."""

    @classmethod
    def setUpClass(cls):
        cls.module = (ROOT / 'static' / 'js' / 'app-offline-schedule.js').read_text(encoding='utf-8')
        cls.tsr = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')
        cls.timeline = (ROOT / 'templates' / 'timeline.html').read_text(encoding='utf-8')

    def test_the_schedule_module_is_loaded_on_the_create_tsr_page(self):
        """Without it window.offlineSchedule is undefined and nothing can resolve."""
        self.assertIn('js/app-offline-schedule.js', self.tsr)

    def test_the_module_is_not_loaded_on_unrelated_pages(self):
        """Positive control for the assertion above."""
        clients_page = (ROOT / 'templates' / 'clients.html').read_text(encoding='utf-8')
        self.assertNotIn('js/app-offline-schedule.js', clients_page)

    def test_the_resolved_store_was_added_behind_a_version_bump(self):
        # A new object store is only created during onupgradeneeded, so the version must move
        # or devices holding the v1 database never get the store.
        self.assertIn('DB_VERSION = 2', self.module)
        self.assertIn('contains(STORES.resolved)', self.module)

    def test_the_mapping_is_written_before_the_queue_row_is_discarded(self):
        """Ordering is the whole recovery story.

        If the row were discarded first and the mapping write then failed, a TSR waiting on
        that schedule would find the row gone and the answer missing, with no way back. This
        way a failed write leaves the item queued and the replay returns the same ids.
        """
        send_one = self.module.split('function sendOne(')[1].split('\n    function ')[0]
        record_at = send_one.find('recordResolved')
        discard_at = send_one.find('discard(item.id)')
        synced_at = send_one.find('outcome.synced += 1')
        self.assertGreater(record_at, -1, 'the mapping write is missing')
        self.assertGreater(discard_at, -1, 'the discard is missing')
        self.assertGreater(synced_at, -1, 'the success counter is missing')
        self.assertLess(record_at, discard_at, 'the mapping must be durable before the discard')
        self.assertLess(discard_at, synced_at,
                        'an item still in the queue must never be counted as synced')

    def test_the_queue_exposes_what_a_waiting_tsr_needs(self):
        for name in ('resolveToken:', 'hasQueued:', 'forgetResolved:'):
            self.assertIn(name, self.module)

    def test_a_queued_tsr_is_never_posted_with_an_unresolved_schedule(self):
        upload = self.tsr.split('async function uploadQueuedOfflineTSR(')[1].split('\nasync function ')[0]
        resolve_at = upload.find('resolveTSRQueueItemSchedule')
        post_at = upload.find('/save_offline_tsr_online')
        self.assertGreater(resolve_at, -1, 'the resolution step is missing')
        self.assertGreater(post_at, -1, 'the core save call is missing')
        self.assertLess(resolve_at, post_at,
                        'the shift must be resolved before the TSR is sent')

    def test_the_composite_runtime_id_can_no_longer_reach_the_server(self):
        """The latent bug this work had to fix on the way past.

        collectTSRData used to fall through to selectedStandaloneScheduleId, the composite
        picker id. clean_int rejects it, the 400 is fatal, and the TSR parks forever.
        """
        real_id = self.tsr.split('function getStandaloneScheduleRealId(')[1].split('\n}')[0]
        self.assertIn('/^\\d+$/', real_id, 'the real id must be numeric-only')
        self.assertIn('schedule_id:getStandaloneScheduleRealId(selectedSchedule)', self.tsr)

    def test_pending_schedules_never_reach_local_storage(self):
        """The queue is the only source of truth for what is still pending.

        A cached copy would keep offering a schedule that has since synced or been removed.
        """
        refresh = self.tsr.split('async function refreshStandaloneScheduleOptions(')[1].split('\nfunction ')[0]
        last_cache_at = refresh.rfind('cacheStandaloneScheduleOptions')
        pending_at = refresh.find('readPendingScheduleOptions')
        self.assertGreater(last_cache_at, -1, 'the cache write is missing')
        self.assertGreater(pending_at, -1, 'the pending merge is missing')
        self.assertLess(last_cache_at, pending_at,
                        'pending schedules must be merged after every cache write')

    def test_pending_options_are_appended_not_prepended(self):
        """A field regression, and the reason this test is worth its weight.

        normalizeStandaloneScheduleOptions stamps each option's _offline_uid from its ARRAY
        INDEX, and that uid is the identity a saved draft stores and later matches on. Putting
        pending schedules in front renumbers every real schedule, so a draft saved earlier stops
        matching its own schedule, falls back to a stale snapshot, and the TSR is posted against
        a shift that may no longer exist -- which is exactly what an engineer hit.
        """
        refresh = self.tsr.split('async function refreshStandaloneScheduleOptions(')[1].split('\nfunction ')[0]
        self.assertIn('schedules.concat(pendingOptions)', refresh)
        self.assertNotIn('pendingOptions.concat(schedules)', refresh)

    def test_the_option_identity_still_depends_on_index(self):
        """Positive control for the test above.

        If _offline_uid ever stops being index-derived, the append rule is no longer load-bearing
        and this whole guard should be revisited rather than silently kept.
        """
        normalize = self.tsr.split('function normalizeStandaloneScheduleOptions(')[1].split('\nfunction ')[0]
        self.assertIn('getStandaloneScheduleRuntimeId(schedule, index)', normalize)

    def test_a_missing_schedule_sends_the_engineer_back_to_the_picker(self):
        """A finished TSR must never dead-end because its schedule was deleted."""
        self.assertIn("error_code === 'schedule_missing'", self.tsr)
        self.assertIn('openStandaloneSchedulePickerModal()', self.tsr)

    def test_repointing_a_tsr_mints_a_fresh_submission_token(self):
        """Otherwise the server's cross-shift guard 409s every retry, forever."""
        apply_fn = self.tsr.split('async function applyResolvedScheduleToTSRQueueItem(')[1].split('\nasync function ')[0]
        self.assertIn('previousId !== resolvedId', apply_fn)
        self.assertIn('ensureTSRSubmissionToken', apply_fn)
        self.assertIn('server_submission_id', apply_fn)

    def test_a_tsr_that_already_tried_to_send_also_gets_a_fresh_token(self):
        """Found in the browser: a changed id is not the only case that needs one.

        An attempt whose response never came back can have created the submission server-side
        under the old token with nothing recorded on the device, so any prior send attempt at
        all has to count -- otherwise re-pointing that item 409s forever.
        """
        apply_fn = self.tsr.split('async function applyResolvedScheduleToTSRQueueItem(')[1].split('\nasync function ')[0]
        self.assertIn('sync_attempts', apply_fn)
        self.assertIn('|| hasBeenSent', apply_fn)

    def test_a_missing_queue_row_is_not_read_as_still_queued(self):
        """Found in the browser, and it defeated "a TSR is never lost".

        withStore hands back requestValue's box when a key is missing, and the box is truthy.
        Reading that as "still queued" left an orphaned TSR waiting for a schedule that was
        never coming instead of asking the engineer to pick a new one.
        """
        has_queued = self.module.split('function hasQueued(')[1].split('\n    function ')[0]
        self.assertIn('row && row.id', has_queued)
        self.assertNotIn('return Boolean(row);', has_queued)

    def test_the_pending_token_is_carried_explicitly_on_every_payload(self):
        """It must not survive only inside selectedSchedule."""
        prepare = self.tsr.split('async function prepareTSRForFinalSave(')[1].split('\nfunction ')[0]
        self.assertIn('pending_schedule_token:', prepare)
        self.assertIn('getStandaloneScheduleRealId(selectedSchedule)', prepare)

    def test_an_orphaned_tsr_is_kept_rather_than_deleted(self):
        """A TSR written in the field must never be lost with its schedule."""
        marker = self.tsr.split('async function markTSRQueueItemNeedsSchedule(')[1].split('\n}')[0]
        self.assertIn("status: 'pending'", marker)
        self.assertIn('needs_schedule: true', marker)
        self.assertIn('pickScheduleForQueuedTSR', self.tsr)

    def test_queued_cards_get_their_own_mobile_context_key(self):
        """Pending cards have no id, so without the queue id they all share one key."""
        key_fn = self.timeline.split('function buildMobileScheduleContextKey(')[1].split('\n    }')[0]
        self.assertIn('queue_id', key_fn)

    def test_create_tsr_is_reachable_from_a_queued_card(self):
        workflow = self.timeline.split('function buildPureEngineerMobileWorkflowActions(')[1].split('\n    }')[0]
        self.assertIn('shift?.queue_id', workflow)
        self.assertIn('function redirectToCreateTSRPageFromQueuedSchedule(', self.timeline)

    def test_a_queued_card_carries_the_client_and_product(self):
        """A TSR with no customer or equipment is refused after it is written."""
        merge = self.timeline.split('function mergeQueuedSchedulesIntoGrid(')[1].split('\n    }')[0]
        for field in ('client_name: row.clientName', 'product_name: row.productName',
                      'creation_token: row.id'):
            self.assertIn(field, merge)


class PendingScheduleResponseTests(unittest.TestCase):
    """Functional coverage of the ids /add_shift now hands back."""

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.app.config['TESTING'] = True
        cls.created_user_ids = []
        cls.created_engineer_ids = []

        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_shift_creation_token_column()

            db = app_module.db
            user = app_module.User.query.filter_by(username='pending_tsr_engineer').first()
            if not user:
                user = app_module.User(
                    username='pending_tsr_engineer', role='engineer', is_active=True,
                    password=app_module.generate_password_hash('PendingTSR123'))
                db.session.add(user)
                db.session.commit()
                cls.created_user_ids.append(user.id)

            engineer = app_module.Engineer.query.filter_by(employee_id='PENDTSR-1').first()
            if not engineer:
                engineer = app_module.Engineer(
                    employee_id='PENDTSR-1', name='Pending TSR Engineer',
                    initials='PT', branch='Cebu', user_id=user.id)
                db.session.add(engineer)
                db.session.commit()
                cls.created_engineer_ids.append(engineer.id)

            cls.user_id = user.id
            cls.engineer_id = engineer.id

    @classmethod
    def tearDownClass(cls):
        # Every test module pins MEDICAL_SERVICE_TEST_DB with setdefault, so the first import
        # wins and all modules share one database. Anything seeded here must be cleaned up or
        # it leaks into a sibling module's fixtures.
        with cls.app.app_context():
            db = app_module.db
            for shift in app_module.Shift.query.filter(
                    app_module.Shift.title.like('PendingTSR%')).all():
                app_module.ShiftEngineer.query.filter_by(shift_id=shift.id).delete()
                db.session.delete(shift)
            for engineer_id in cls.created_engineer_ids:
                engineer = db.session.get(app_module.Engineer, engineer_id)
                if engineer:
                    db.session.delete(engineer)
            for user_id in cls.created_user_ids:
                user = db.session.get(app_module.User, user_id)
                if user:
                    db.session.delete(user)
            db.session.commit()

    def _client(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.user_id)
            session['_fresh'] = True
        return client

    def _payload(self, title, token=None, days=0, start_hour=9, day_offset=120):
        # Each test books its own date and hour. The suite shares one database, so overlapping
        # fixtures would report a conflict that says nothing about the code under test.
        with self.app.app_context():
            today = app_module.get_manila_today()
        start = today + timedelta(days=day_offset)
        data = {
            'title': title,
            'start_date': start.isoformat(),
            'end_date': (start + timedelta(days=days)).isoformat(),
            'start_time': f'{start_hour:02d}:00',
            'end_time': f'{start_hour + 2:02d}:00',
            'include_weekends': 'true',
            'engineers': str([self.engineer_id]),
        }
        if token:
            data['creation_token'] = token
        return data, start

    def test_a_queued_schedule_gets_its_ids_on_the_first_success(self):
        """Not only on replay. This is what the device stores against the token."""
        client = self._client()
        data, start = self._payload('PendingTSR single', 'pending-tsr-single-0001', day_offset=120)
        response = client.post('/add_shift', data=data)

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_json()
        self.assertFalse(body.get('idempotent_replay'), 'a first create is not a replay')
        self.assertIn('group_id', body)
        self.assertEqual(len(body.get('shift_ids') or []), 1)
        self.assertEqual(body.get('shift_dates'), [start.isoformat()])

    def test_a_multi_day_chain_comes_back_in_date_order(self):
        """The service-date match on the device indexes dates against ids positionally."""
        client = self._client()
        data, start = self._payload('PendingTSR chain', 'pending-tsr-chain-0001', days=4,
                                    start_hour=11, day_offset=130)
        body = client.post('/add_shift', data=data).get_json()

        expected = [(start + timedelta(days=offset)).isoformat() for offset in range(5)]
        self.assertEqual(len(body.get('shift_ids') or []), 5)
        self.assertEqual(body.get('shift_dates'), expected)

    def test_a_replay_returns_the_same_ids_as_the_first_success(self):
        """This is what makes the "mapping write failed, let it replay" recovery real.

        If a replay handed back different ids, an item that failed to record its mapping would
        resolve to a different shift on the next pass.
        """
        client = self._client()
        token = 'pending-tsr-replay-0001'
        data, _ = self._payload('PendingTSR replay', token, days=2, start_hour=13, day_offset=140)

        first = client.post('/add_shift', data=data).get_json()
        second = client.post('/add_shift', data=self._payload(
            'PendingTSR replay', token, days=2, start_hour=13, day_offset=140)[0]).get_json()

        self.assertTrue(second.get('idempotent_replay'))
        self.assertEqual(first.get('shift_ids'), second.get('shift_ids'))
        self.assertEqual(first.get('shift_dates'), second.get('shift_dates'))
        self.assertEqual(first.get('group_id'), second.get('group_id'))

    def test_an_ordinary_online_save_response_is_unchanged(self):
        """Positive control for the whole of the server change.

        /add_shift is large and much-used. If the ids leaked into the untokened path this
        fails, which is the point.
        """
        client = self._client()
        data, _ = self._payload('PendingTSR online', start_hour=15, day_offset=150)
        body = client.post('/add_shift', data=data).get_json()

        self.assertEqual(body, {'status': 'success'})


class PendingScheduleTSRValidationTests(unittest.TestCase):
    """The server-side guards the device now avoids must still be there.

    The client stops sending bad ids; the server keeps refusing them. Both halves matter --
    the device is not the only thing that can post to this route.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.app.config['TESTING'] = True
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')

    def test_a_composite_runtime_id_is_still_refused(self):
        """clean_int returns None for it, and the route must not accept that as an id."""
        self.assertIsNone(app_module.clean_int('12::2026-08-01::09:00-11:00::0'))
        # Positive control: a real id must still parse, or the assertion above proves nothing.
        self.assertEqual(app_module.clean_int('12'), 12)

    def test_the_missing_schedule_guard_is_still_in_place(self):
        route = self.app_source.split("@app.route('/save_offline_tsr_online'")[1].split('\n@app.route')[0]
        self.assertIn('Please select a schedule before saving online.', route)
        # The wording is allowed to improve; the guard and its machine-readable code are not.
        # It now names the id and tells the engineer to re-pick, rather than dead-ending.
        self.assertIn("'error_code': 'schedule_missing'", route)
        self.assertIn('), 404', route)
        self.assertIn('can_work_on_existing_schedule_shift', route)

    def test_the_cross_shift_token_guard_is_still_in_place(self):
        """It is why re-pointing a TSR has to mint a fresh submission token."""
        route = self.app_source.split("@app.route('/save_offline_tsr_online'")[1].split('\n@app.route')[0]
        self.assertIn('belongs to a different schedule', route)


if __name__ == '__main__':
    unittest.main()
