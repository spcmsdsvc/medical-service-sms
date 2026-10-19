"""/get_offline_tsr_schedule_options filters to the user's schedules before the heavy work (plans.md 2026-10-14, step 15)."""
import json
import os
import pathlib
import tempfile
import unittest
from datetime import datetime, time, timedelta
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import event

_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f'medical_service_tsr_options_{os.getpid()}_{uuid4().hex}.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

try:
    import app as app_module
except Exception as exc:  # pragma: no cover
    app_module = None
    APP_IMPORT_ERROR = exc
else:
    APP_IMPORT_ERROR = None


@unittest.skipIf(app_module is None, f'app import failed: {APP_IMPORT_ERROR}')
class OfflineTSRScheduleOptionsSpeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['TESTING'] = True
        db = app_module.db
        suffix = uuid4().hex[:8]
        with cls.app.app_context():
            db.create_all()
            users = [app_module.User(username=f'tsr-options-{n}-{suffix}', password='x', role='engineer', is_active=True)
                     for n in ('a', 'b')]
            db.session.add_all(users)
            db.session.flush()
            engineers = [app_module.Engineer(user_id=u.id, employee_id=f'TSR-OPT-{i}-{suffix}', name=f'Options Engineer {i}',
                                             initials=f'OE{i}', branch='Manila') for i, u in enumerate(users)]
            client = app_module.Client(name=f'TSR Options Client {suffix}')
            db.session.add_all(engineers + [client])
            db.session.flush()
            cls.user_a, cls.engineer_a, cls.engineer_b = users[0].id, engineers[0].id, engineers[1].id
            cls.client_id = client.id
            day = datetime.combine(app_module.get_manila_today(), time(8, 0))

            def add_shift(offset, engineer_id, linked=()):
                shift = app_module.Shift(title=f'Options shift {suffix}', start_time=day + timedelta(days=offset),
                                         end_time=day + timedelta(days=offset, hours=8), engineer_id=engineer_id,
                                         client_id=client.id, status='Scheduled')
                db.session.add(shift)
                db.session.flush()
                for eid in linked:
                    db.session.add(app_module.ShiftEngineer(shift_id=shift.id, engineer_id=eid))
                return shift.id

            # Shared shift linked with the higher engineer id first: the response lists them by id.
            cls.shared_shift = add_shift(0, cls.engineer_b, linked=(cls.engineer_b, cls.engineer_a))
            cls.fallback_shift = add_shift(1, cls.engineer_a)  # no ShiftEngineer rows: falls back to shift.engineer_id
            cls.other_shifts = [add_shift(2 + n, cls.engineer_b, linked=(cls.engineer_b,)) for n in range(20)]
            db.session.commit()

    def _get_as_a(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.user_a)
            session['_fresh'] = True
        calls = []
        real_resolve = app_module.resolve_shift_equipment
        count = [0]

        def counter(*_args, **_kwargs):
            count[0] += 1

        with self.app.app_context():
            engine = app_module.db.engine
        event.listen(engine, 'before_cursor_execute', counter)
        try:
            with patch.object(app_module, 'resolve_shift_equipment',
                              side_effect=lambda shift: calls.append(shift.id) or real_resolve(shift)):
                response = client.get('/get_offline_tsr_schedule_options')
        finally:
            event.remove(engine, 'before_cursor_execute', counter)
        self.assertEqual(response.status_code, 200)
        return response.get_json()['schedules'], calls, count[0]

    def test_only_own_schedules_with_same_engineer_order_and_fallback(self):
        schedules, _calls, _queries = self._get_as_a()
        by_id = {item['id']: item for item in schedules}
        self.assertEqual(set(by_id), {self.shared_shift, self.fallback_shift})
        self.assertEqual(by_id[self.shared_shift]['engineers'], sorted([self.engineer_a, self.engineer_b]))
        self.assertEqual(by_id[self.fallback_shift]['engineers'], [self.engineer_a])

    def test_equipment_is_resolved_only_for_kept_schedules(self):
        _schedules, calls, _queries = self._get_as_a()
        self.assertEqual(sorted(calls), sorted([self.shared_shift, self.fallback_shift]),
                         "Other engineers' schedules must not be resolved.")

    def test_query_count_does_not_grow_with_other_engineers_schedules(self):
        _s, _c, before = self._get_as_a()
        with self.app.app_context():
            day = datetime.combine(app_module.get_manila_today(), time(8, 0))
            extra = []
            for n in range(15):
                shift = app_module.Shift(title='Options extra', start_time=day + timedelta(days=30 + n),
                                         end_time=day + timedelta(days=30 + n, hours=8), engineer_id=self.engineer_b,
                                         client_id=self.client_id, status='Scheduled')
                app_module.db.session.add(shift)
                app_module.db.session.flush()
                app_module.db.session.add(app_module.ShiftEngineer(shift_id=shift.id, engineer_id=self.engineer_b))
                extra.append(shift.id)
            app_module.db.session.commit()
        try:
            _s, _c, after = self._get_as_a()
        finally:
            with self.app.app_context():
                app_module.ShiftEngineer.query.filter(app_module.ShiftEngineer.shift_id.in_(extra)).delete(synchronize_session=False)
                app_module.Shift.query.filter(app_module.Shift.id.in_(extra)).delete(synchronize_session=False)
                app_module.db.session.commit()
        self.assertEqual(after, before, "Query count grew with another engineer's schedules.")


@unittest.skipIf(app_module is None, f'app import failed: {APP_IMPORT_ERROR}')
class OfflineTSRScheduleOptionsChainTests(unittest.TestCase):
    """Multi-day chains: same coverage as the per-shift helpers, without per-day queries."""

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['TESTING'] = True
        db = app_module.db
        suffix = uuid4().hex[:8]
        with cls.app.app_context():
            db.create_all()
            users = [app_module.User(username=f'tsr-chain-{n}-{suffix}', password='x', role='engineer', is_active=True)
                     for n in ('c', 'd')]
            db.session.add_all(users)
            db.session.flush()
            engineers = [app_module.Engineer(user_id=u.id, employee_id=f'TSR-CHAIN-{i}-{suffix}', name=f'Chain Engineer {i}',
                                             initials=f'CE{i}', branch='Manila') for i, u in enumerate(users)]
            client = app_module.Client(name=f'TSR Chain Client {suffix}')
            db.session.add_all(engineers + [client])
            db.session.flush()
            cls.user_c, cls.engineer_c, cls.engineer_d = users[0].id, engineers[0].id, engineers[1].id
            cls.client_id = client.id
            cls.day = datetime.combine(app_module.get_manila_today(), time(8, 0))
            cls.shift_ids = []
            cls.add_chain(f'chain-{suffix}', 0, 5, with_override=True)
            db.session.commit()

    @classmethod
    def add_chain(cls, group_id, first_day, days, with_override=False):
        db = app_module.db
        ids = []
        for offset in range(first_day, first_day + days):
            shift = app_module.Shift(title='Chain shift', start_time=cls.day + timedelta(days=offset),
                                     end_time=cls.day + timedelta(days=offset, hours=8), engineer_id=cls.engineer_c,
                                     client_id=cls.client_id, status='Scheduled', group_id=group_id)
            db.session.add(shift)
            db.session.flush()
            for eid in (cls.engineer_d, cls.engineer_c):
                db.session.add(app_module.ShiftEngineer(shift_id=shift.id, engineer_id=eid))
            ids.append(shift.id)
        if with_override:
            override = app_module.Shift(title='Chain shift', start_time=cls.day + timedelta(days=first_day + 1, hours=2),
                                        end_time=cls.day + timedelta(days=first_day + 1, hours=6), engineer_id=cls.engineer_d,
                                        client_id=cls.client_id, status='Scheduled', parent_shift_id=ids[1],
                                        override_kind='time_override')
            db.session.add(override)
            db.session.flush()
            ids.append(override.id)
        cls.shift_ids.extend(ids)
        return ids

    def _get_as_c(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.user_c)
            session['_fresh'] = True
        count = [0]

        def counter(*_args, **_kwargs):
            count[0] += 1

        with self.app.app_context():
            engine = app_module.db.engine
        event.listen(engine, 'before_cursor_execute', counter)
        try:
            response = client.get('/get_offline_tsr_schedule_options')
        finally:
            event.remove(engine, 'before_cursor_execute', counter)
        self.assertEqual(response.status_code, 200)
        return response.get_json()['schedules'], count[0]

    def test_chain_coverage_matches_the_per_shift_helpers(self):
        schedules, _queries = self._get_as_c()
        self.assertTrue(schedules)
        with self.app.app_context():
            for item in schedules:
                shift = app_module.db.session.get(app_module.Shift, item['id'])
                linked = app_module.get_tsr_completion_linked_shifts(shift)
                expected = app_module.get_tsr_schedule_coverage_rows(shift, linked_shifts=linked)
                self.assertEqual(item['schedule_coverage'], json.loads(json.dumps(expected)))
                self.assertEqual(item['linked_schedule_count'], len(linked))
                self.assertTrue(item['is_multi_day'])
                self.assertTrue(item['is_multi_engineer'])

    def test_more_chain_days_do_not_add_queries_per_day(self):
        _s, before = self._get_as_c()
        with self.app.app_context():
            extra = self.add_chain(f'chain-extra-{uuid4().hex[:8]}', 20, 8)
            app_module.db.session.commit()
        try:
            schedules, after = self._get_as_c()
            self.assertTrue(set(extra) <= {item['id'] for item in schedules})
        finally:
            with self.app.app_context():
                app_module.ShiftEngineer.query.filter(app_module.ShiftEngineer.shift_id.in_(extra)).delete(synchronize_session=False)
                app_module.Shift.query.filter(app_module.Shift.id.in_(extra)).delete(synchronize_session=False)
                app_module.db.session.commit()
        # One more chain costs its group and override queries, not ~14 queries per day.
        self.assertLessEqual(after - before, 4, f'8 more chain days added {after - before} queries.')


if __name__ == '__main__':
    unittest.main()
