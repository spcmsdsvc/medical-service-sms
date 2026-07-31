"""Offline schedule creation: the server contract the field queue depends on.

An engineer with no signal queues a schedule on the device and it is replayed when signal
returns. Retries are normal, not exceptional, so the thing that matters most here is that
replaying a queued schedule cannot create it twice -- including for a multi-day chain, where
a naive token would either duplicate every row or trip the unique index.
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


class OfflineScheduleSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')

    def test_creation_token_migration_is_additive(self):
        self.assertIn('ALTER TABLE shift ADD COLUMN creation_token VARCHAR(100)', self.app_source)
        self.assertIn('uq_shift_creation_token', self.app_source)
        # A destructive migration on the live schedule table would be unrecoverable.
        self.assertFalse(
            'DROP COLUMN creation_token' in self.app_source,
            'creation_token must never be dropped: the live database is SQLite and in use'
        )

    def test_replay_is_resolved_before_the_collision_check(self):
        """Ordering is load-bearing, so it is pinned.

        A queued schedule that already reached the server occupies its own slots. If the
        collision check ran first, every retry would collide with the copy it created last
        time and park a schedule that is in fact already saved.
        """
        add_shift = self.app_source.split("@app.route('/add_shift'")[1].split('\n@app.route')[0]
        token_at = add_shift.find('find_schedule_chain_by_creation_token')
        collision_at = add_shift.find('find_add_schedule_collision')
        self.assertGreater(token_at, -1, 'the replay lookup is missing')
        self.assertGreater(collision_at, -1, 'the collision check is missing')
        self.assertLess(token_at, collision_at,
                        'replay must be resolved before the collision check')

    def test_token_is_stored_on_the_first_shift_only(self):
        """On every row it would trip the unique index for a multi-day schedule."""
        self.assertIn('if first_shift is None and creation_token:', self.app_source)


class OfflineScheduleTokenTests(unittest.TestCase):
    def test_token_rules_match_the_lpr_precedent(self):
        normalize = app_module.normalize_schedule_creation_token
        self.assertEqual(normalize('a' * 16), 'a' * 16)
        self.assertEqual(normalize('sched-2026_07_31:abcdef'), 'sched-2026_07_31:abcdef')

        for rejected in ('', None, 'short', 'a' * 15, 'a' * 101, 'has space' * 3,
                         'semi;colon' * 2, "quote'" * 4):
            self.assertEqual(normalize(rejected), '', f'should reject {rejected!r}')


class OfflineScheduleReplayTests(unittest.TestCase):
    """Functional coverage: the queue replays, the server must not duplicate."""

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
            user = app_module.User.query.filter_by(username='offline_sched_engineer').first()
            if not user:
                user = app_module.User(
                    username='offline_sched_engineer', role='engineer', is_active=True,
                    password=app_module.generate_password_hash('OfflineSched123'))
                db.session.add(user)
                db.session.commit()
                cls.created_user_ids.append(user.id)

            engineer = app_module.Engineer.query.filter_by(employee_id='OFFSCHED-1').first()
            if not engineer:
                engineer = app_module.Engineer(
                    employee_id='OFFSCHED-1', name='Offline Queue Engineer',
                    initials='OQ', branch='Cebu', user_id=user.id)
                db.session.add(engineer)
                db.session.commit()
                cls.created_engineer_ids.append(engineer.id)

            # A second engineer the test account is NOT linked to, for the authorization case.
            other = app_module.Engineer.query.filter_by(employee_id='OFFSCHED-2').first()
            if not other:
                other = app_module.Engineer(
                    employee_id='OFFSCHED-2', name='Someone Else', initials='SE', branch='Cebu')
                db.session.add(other)
                db.session.commit()
                cls.created_engineer_ids.append(other.id)

            cls.user_id = user.id
            cls.engineer_id = engineer.id
            cls.other_engineer_id = other.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db = app_module.db
            for shift in app_module.Shift.query.filter(
                    app_module.Shift.title.like('OfflineQueue%')).all():
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

    def _payload(self, title, token=None, days=0, engineers=None, start_hour=9, day_offset=30):
        # Each test books its own date. Tests run alphabetically against a shared database,
        # so two fixtures on the same day/time would collide with each other and report a
        # conflict that says nothing about the code under test.
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
            'engineers': str(list(engineers if engineers is not None else [self.engineer_id])),
        }
        if token:
            data['creation_token'] = token
        return data

    def _chain(self, title):
        with self.app.app_context():
            return app_module.Shift.query.filter_by(title=title).all()

    def test_replaying_a_queued_schedule_does_not_create_it_twice(self):
        token = 'offline-sched-single-0001'
        client = self._client()

        first = client.post('/add_shift', data=self._payload('OfflineQueue single', token, day_offset=30))
        second = client.post('/add_shift', data=self._payload('OfflineQueue single', token, day_offset=30))

        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
        self.assertTrue(second.get_json().get('idempotent_replay'))
        self.assertEqual(len(self._chain('OfflineQueue single')), 1)

    def test_without_a_token_two_posts_really_do_create_two(self):
        """Positive control.

        Without this, the idempotency assertion above could pass simply because something
        else was preventing the second create.
        """
        client = self._client()
        client.post('/add_shift', data=self._payload('OfflineQueue untokened', start_hour=11, day_offset=40))
        client.post('/add_shift', data=self._payload('OfflineQueue untokened', start_hour=13, day_offset=40))

        self.assertEqual(len(self._chain('OfflineQueue untokened')), 2)

    def test_replaying_a_multi_day_chain_leaves_one_chain(self):
        """The token keys the chain. Five days replayed must stay five rows, not ten."""
        token = 'offline-sched-multiday-0001'
        client = self._client()

        first = client.post('/add_shift', data=self._payload('OfflineQueue multiday', token, days=4, day_offset=50))
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        created = self._chain('OfflineQueue multiday')
        self.assertEqual(len(created), 5)

        second = client.post('/add_shift', data=self._payload('OfflineQueue multiday', token, days=4, day_offset=50))
        self.assertEqual(second.status_code, 200)
        body = second.get_json()
        self.assertTrue(body.get('idempotent_replay'))
        self.assertEqual(len(body.get('shift_ids') or []), 5)

        after = self._chain('OfflineQueue multiday')
        self.assertEqual(len(after), 5, 'replay duplicated a multi-day chain')
        self.assertEqual(len({shift.group_id for shift in after}), 1)

        # Exactly one row carries the token, or the unique index would have refused the insert.
        with self.app.app_context():
            tokened = app_module.Shift.query.filter_by(creation_token=token).count()
        self.assertEqual(tokened, 1)

    def test_a_conflicting_queued_schedule_is_refused_and_creates_nothing(self):
        """Fatal, not retriable: 409 so the device parks the item instead of retrying."""
        client = self._client()
        client.post('/add_shift', data=self._payload('OfflineQueue occupier', start_hour=15, day_offset=60))
        self.assertEqual(len(self._chain('OfflineQueue occupier')), 1)

        clashing = self._payload('OfflineQueue clash', 'offline-sched-conflict-0001', start_hour=15, day_offset=60)
        response = client.post('/add_shift', data=clashing)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json().get('status'), 'conflict')
        self.assertEqual(self._chain('OfflineQueue clash'), [])

    def test_an_invalid_token_is_refused_rather_than_ignored(self):
        """Silently dropping a malformed token would silently drop idempotency with it."""
        client = self._client()
        response = client.post('/add_shift', data=self._payload('OfflineQueue badtoken', 'short', day_offset=70))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._chain('OfflineQueue badtoken'), [])

    def test_a_token_does_not_bypass_the_permission_check(self):
        """An engineer may only create schedules that include their own profile.

        The offline path must not become a way around that, either when creating or when
        replaying someone else's token.
        """
        client = self._client()
        response = client.post('/add_shift', data=self._payload(
            'OfflineQueue notmine', 'offline-sched-notmine-0001',
            engineers=[self.other_engineer_id], day_offset=80))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self._chain('OfflineQueue notmine'), [])


if __name__ == '__main__':
    unittest.main()
