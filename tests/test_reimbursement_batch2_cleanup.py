"""Reimbursement Batch 2: schedule rows filtered in SQL, unused status counts and duplicate status key removed."""

import os
import pathlib
import tempfile
import unittest
from datetime import datetime

from sqlalchemy import create_engine, event


ROOT = pathlib.Path(__file__).resolve().parents[1]
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_reimbursement_batch2_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402

APP_SOURCE = (ROOT / 'app.py').read_text(encoding='utf-8')


def _function_block(name):
    start = APP_SOURCE.index(f'def {name}(')
    end = APP_SOURCE.index('\ndef ', start + 1)
    return APP_SOURCE[start:end]


class ReimbursementScheduleRowsQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        engines = cls.app.extensions['sqlalchemy']._app_engines[cls.app]
        cls.original_engine = engines[None]
        cls.test_engine = create_engine(f"sqlite:///{_TEST_DB_PATH.as_posix()}")
        engines[None] = cls.test_engine
        db = app_module.db
        with cls.app.app_context():
            db.create_all()
            users = []
            engineers = []
            for code in ('A', 'B'):
                user = app_module.User(username=f'batch2_eng_{code}', password='test-only', role='engineer', is_active=True)
                db.session.add(user)
                db.session.flush()
                engineer = app_module.Engineer(
                    user_id=user.id, employee_id=f'BATCH2-{code}', name=f'Batch Two {code}', initials=f'B2{code}',
                )
                db.session.add(engineer)
                db.session.flush()
                users.append(user)
                engineers.append(engineer)
            cls.user_a_id = users[0].id
            a, b = engineers

            def shift(day, month, engineer_id, linked=()):
                item = app_module.Shift(
                    title='Service', start_time=datetime(2026, month, day, 9), end_time=datetime(2026, month, day, 17),
                    engineer_id=engineer_id,
                )
                db.session.add(item)
                db.session.flush()
                for linked_id in linked:
                    db.session.add(app_module.ShiftEngineer(shift_id=item.id, engineer_id=linked_id))
                return item.id

            # March: linked to A only through ShiftEngineer, owned by A, owned by A but linked to B, B only.
            cls.march_expected = [
                shift(2, 3, b.id, linked=(a.id, b.id)),
                shift(3, 3, a.id),
                shift(4, 3, a.id, linked=(b.id,)),
            ]
            cls.march_other = shift(5, 3, b.id)
            # April: the same four shifts as March, plus 6 more for B only (4 vs 10 shifts in range).
            shift(2, 4, b.id, linked=(a.id, b.id))
            shift(3, 4, a.id)
            shift(4, 4, a.id, linked=(b.id,))
            for day in range(5, 12):
                shift(day, 4, b.id, linked=(b.id,) if day % 2 else ())
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            app_module.db.session.remove()
        cls.app.extensions['sqlalchemy']._app_engines[cls.app][None] = cls.original_engine
        cls.test_engine.dispose()
        try:
            _TEST_DB_PATH.unlink()
        except FileNotFoundError:
            pass

    def _get(self, start, end):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.user_a_id)
            session['_fresh'] = True
        statements = []

        def count(conn, cursor, statement, *args):
            statements.append(statement)

        event.listen(self.test_engine, 'before_cursor_execute', count)
        try:
            response = client.get(f'/get_reimbursement_schedule_rows?start={start}&end={end}')
        finally:
            event.remove(self.test_engine, 'before_cursor_execute', count)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json(), statements

    def _shift_ids(self, payload):
        return [row.get('shift_id') or row.get('id') for row in payload['rows']]

    def test_returns_only_own_and_linked_shifts_in_order(self):
        payload, _ = self._get('2026-03-01', '2026-03-31')
        self.assertEqual(self._shift_ids(payload), self.march_expected)
        self.assertNotIn(self.march_other, self._shift_ids(payload))

    def test_query_count_does_not_grow_with_other_engineers_shifts(self):
        self._get('2026-03-01', '2026-03-31')  # warm-up: the first request runs one-time setup queries
        march, march_statements = self._get('2026-03-01', '2026-03-31')
        april, april_statements = self._get('2026-04-01', '2026-04-30')
        self.assertEqual(len(march['rows']), 3)
        self.assertEqual(len(april['rows']), 3)
        # Same three shifts for A; April has 6 more for B only. Their count must not add queries.
        self.assertEqual(len(april_statements), len(march_statements))


class ReimbursementBatch2SourceTests(unittest.TestCase):
    def test_status_counts_removed(self):
        self.assertNotIn('status_counts', _function_block('get_my_reimbursement_statuses'))

    def test_paid_key_appears_once_in_normaliser(self):
        self.assertEqual(_function_block('reimbursement_normalize_status').count("'paid': 'Paid'"), 1)


if __name__ == '__main__':
    unittest.main()
