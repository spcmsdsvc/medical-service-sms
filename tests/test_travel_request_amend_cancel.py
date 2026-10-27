"""Travel Request Amend and Cancel after approval (plans.md). Own temp DB and TRA-TEST- prefix."""
import os
import pathlib
import tempfile
import unittest
from contextlib import ExitStack
from datetime import date, timedelta
from unittest import mock

_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_travel_amend_cancel_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402

DEPARTURE = date(2032, 4, 5)


class TravelRequestAmendCancelTests(unittest.TestCase):
    OWNER = 'tr_amend_owner'
    PARTICIPANT = 'tr_amend_participant'
    APPROVER = 'tr_amend_approver'
    OTHER = 'tr_amend_other'
    USERNAMES = (OWNER, PARTICIPANT, APPROVER, OTHER)
    EMPLOYEE_IDS = ('TRA-E1',)

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_travel_request_tables()
            app_module.ensure_travel_liquidation_tables()
            cls._cleanup()
            cls._seed()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            cls._cleanup()

    @classmethod
    def _cleanup(cls):
        m = app_module
        db = m.db
        try:
            users = m.User.query.filter(m.User.username.in_(cls.USERNAMES)).all()
            user_ids = [u.id for u in users] or [0]
            for rec in m.TravelRequest.query.filter(m.TravelRequest.user_id.in_(user_ids)).all():
                for shift in m.Shift.query.filter_by(travel_request_id=rec.id).all():
                    m.ShiftEngineer.query.filter_by(shift_id=shift.id).delete(synchronize_session=False)
                    db.session.delete(shift)
                m.TravelLiquidationHeader.query.filter_by(travel_request_id=rec.id).delete(synchronize_session=False)
                m.TravelRequestParticipant.query.filter_by(travel_request_id=rec.id).delete(synchronize_session=False)
                db.session.delete(rec)
            for engineer in m.Engineer.query.filter(m.Engineer.employee_id.in_(cls.EMPLOYEE_IDS)).all():
                db.session.delete(engineer)
            for user in users:
                db.session.delete(user)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

    @classmethod
    def _seed(cls):
        m = app_module
        db = m.db
        users = {name: m.User(username=name, role='engineer', is_active=True, password=m.generate_password_hash('Amend12345'))
                 for name in cls.USERNAMES}
        db.session.add_all(users.values())
        db.session.commit()
        cls.ids = {name: user.id for name, user in users.items()}
        engineer = m.Engineer(employee_id=cls.EMPLOYEE_IDS[0], name='TR Amend Owner', initials='TA', branch='Manila', user_id=cls.ids[cls.OWNER])
        db.session.add(engineer)
        db.session.commit()
        cls.engineer_id = engineer.id

    def setUp(self):
        # Approval routing, signatures and email are covered elsewhere; keep them out of the way.
        self._stack = ExitStack()
        for name, value in (
            ('is_approval_center_user', True),
            ('can_user_approve_travel_request', True),
            ('approval_signature_required_response', None),
            ('get_travel_accounting_recipient_emails', []),
            ('send_travel_request_notification_email_async', None),
            ('send_travel_request_accounting_email_async', False),
        ):
            self._stack.enter_context(mock.patch.object(app_module, name, return_value=value))
        self.addCleanup(self._stack.close)

    # ---------- helpers ----------
    def _client(self, username):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.ids[username])
            session['_fresh'] = True
        return client

    def _payload(self, record_id=None, departure=DEPARTURE, days=3):
        return {
            'id': record_id or '',
            'request_type': 'Training',
            'purpose': 'Training trip for amend tests',
            'training_title': 'Amend Training',
            'departure_date': departure.isoformat(),
            'return_date': (departure + timedelta(days=days - 1)).isoformat(),
            'currency_code': 'PHP',
            'participants': [],
            'routes': [{'from_location': 'Manila', 'to_location': 'Cebu', 'travel_type': 'Air Travel', 'route_summary': 'Manila → Cebu', 'visits': []}],
            'lines': [{'line_type': 'Meals', 'description': 'Meals', 'amount': 1500, 'source_currency_code': 'PHP', 'source_amount': 1500, 'exchange_rate': 1}],
        }

    def _set(self, record_id, **fields):
        with self.app.app_context():
            rec = app_module.db.session.get(app_module.TravelRequest, record_id)
            for key, value in fields.items():
                setattr(rec, key, value)
            app_module.db.session.commit()

    def _record(self, record_id):
        with self.app.app_context():
            rec = app_module.db.session.get(app_module.TravelRequest, record_id)
            app_module.db.session.expunge(rec)
            return rec

    def _approve(self, record_id):
        self._set(record_id, status='Submitted')
        response = self._client(self.APPROVER).post(f'/approve_travel_request/{record_id}', json={'remarks': 'ok'})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    def _approved(self, departure):
        response = self._client(self.OWNER).post('/save_travel_request_draft', json=self._payload(departure=departure))
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        record_id = response.get_json()['travel_request']['id']
        self._approve(record_id)
        return record_id

    def _block_dates(self, record_id):
        with self.app.app_context():
            rows = app_module.Shift.query.filter_by(travel_request_id=record_id, schedule_type='travel').all()
            return sorted(row.start_time.date() for row in rows)

    def _post(self, username, record_id, action, reason='Trip moved'):
        return self._client(username).post(f'/api/travel-requests/{record_id}/{action}', json={'reason': reason})

    # ---------- amend ----------
    def test_amend_resubmit_approve_moves_blocks_and_keeps_converted(self):
        record_id = self._approved(DEPARTURE)
        self.assertEqual(self._block_dates(record_id), [DEPARTURE + timedelta(days=i) for i in range(3)])
        with self.app.app_context():
            converted = app_module.Shift(title='Converted service', start_time=app_module.datetime(2032, 4, 5, 8), end_time=app_module.datetime(2032, 4, 5, 17),
                                         engineer_id=self.engineer_id, status='Approved', schedule_type='service',
                                         travel_request_id=record_id, travel_block_status='converted')
            app_module.db.session.add(converted)
            app_module.db.session.commit()
            converted_id = converted.id

        response = self._post(self.OWNER, record_id, 'amend')
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        rec = self._record(record_id)
        self.assertEqual((rec.status, rec.amend_from_status), ('Amending', 'Approved'))
        self.assertTrue(response.get_json()['travel_request']['is_amendment'])

        new_departure = DEPARTURE + timedelta(days=10)
        save = self._client(self.OWNER).post('/save_travel_request_draft', json=self._payload(record_id, departure=new_departure, days=2))
        self.assertEqual(save.status_code, 200, save.get_data(as_text=True))
        with self.app.test_request_context():
            # The request's own old travel blocks (days 2-3) are not a conflict with itself;
            # the converted block on day 1 is real service work and still is.
            conflicts = app_module.find_travel_request_conflicts_for_user(
                self.ids[self.OWNER], self.engineer_id, DEPARTURE + timedelta(days=1), DEPARTURE + timedelta(days=2), exclude_request_id=record_id)
            self.assertFalse(conflicts['has_conflicts'], conflicts)

        self._approve(record_id)
        rec = self._record(record_id)
        self.assertEqual(rec.status, 'Approved')
        self.assertIsNone(rec.amend_from_status)
        self.assertEqual(self._block_dates(record_id), [new_departure, new_departure + timedelta(days=1)])
        with self.app.app_context():
            self.assertIsNotNone(app_module.db.session.get(app_module.Shift, converted_id))

    def test_funds_received_is_kept_after_reapproval(self):
        record_id = self._approved(DEPARTURE + timedelta(days=40))
        self._set(record_id, status='Funds Received', accounting_status='Funds Received', funds_received_at=app_module.get_manila_time())
        self.assertEqual(self._post(self.OWNER, record_id, 'amend').status_code, 200)
        self.assertEqual(self._record(record_id).amend_from_status, 'Funds Received')
        self._approve(record_id)
        rec = self._record(record_id)
        self.assertEqual((rec.status, rec.accounting_status), ('Funds Received', 'Funds Received'))

    def test_reject_and_withdraw_return_to_amending_and_no_delete(self):
        record_id = self._approved(DEPARTURE + timedelta(days=80))
        self.assertEqual(self._post(self.OWNER, record_id, 'amend').status_code, 200)
        self._set(record_id, status='Submitted')
        reject = self._client(self.APPROVER).post(f'/reject_travel_request/{record_id}', json={'remarks': 'Check dates'})
        self.assertEqual(reject.status_code, 200, reject.get_data(as_text=True))
        self.assertEqual(self._record(record_id).status, 'Amending')

        self._set(record_id, status='Submitted')
        recall = self._client(self.OWNER).post(f'/api/requests/travel_request/{record_id}/recall', json={'reason': 'More changes'})
        self.assertEqual(recall.status_code, 200, recall.get_data(as_text=True))
        self.assertEqual(self._record(record_id).status, 'Amending')

        self.assertEqual(self._client(self.OWNER).post(f'/delete_travel_request_draft/{record_id}').status_code, 409)

    # ---------- cancel ----------
    def test_cancel_removes_blocks_and_stops_reminders(self):
        record_id = self._approved(DEPARTURE + timedelta(days=120))
        self.assertTrue(self._block_dates(record_id))
        response = self._post(self.OWNER, record_id, 'cancel', reason='Client postponed')
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(self._record(record_id).status, 'Cancelled')
        self.assertEqual(self._block_dates(record_id), [])
        self.assertIn('Cancelled', app_module.travel_request_liquidation_reminder_terminal_statuses())
        self.assertEqual(self._post(self.OWNER, record_id, 'amend').status_code, 409)

    def test_cancel_after_funds_received_says_return_cash(self):
        record_id = self._approved(DEPARTURE + timedelta(days=160))
        self._set(record_id, status='Funds Received', funds_received_at=app_module.get_manila_time())
        response = self._post(self.OWNER, record_id, 'cancel')
        self.assertEqual(response.status_code, 200)
        self.assertIn('returned to Accounting', response.get_json()['message'])

    # ---------- refusals ----------
    def test_refusals(self):
        record_id = self._approved(DEPARTURE + timedelta(days=200))
        self.assertEqual(self._post(self.OWNER, record_id, 'amend', reason='').status_code, 400)
        self.assertEqual(self._post(self.OTHER, record_id, 'amend').status_code, 403)
        self.assertEqual(self._post(self.PARTICIPANT, record_id, 'cancel').status_code, 403)
        for status in ('Draft', 'Submitted', 'Ready for Liquidation'):
            self._set(record_id, status=status)
            self.assertEqual(self._post(self.OWNER, record_id, 'amend').status_code, 409, status)
            self.assertEqual(self._post(self.OWNER, record_id, 'cancel').status_code, 409, status)
        self._set(record_id, status='Approved')
        with self.app.app_context():
            app_module.db.session.add(app_module.TravelLiquidationHeader(travel_request_id=record_id, user_id=self.ids[self.OWNER]))
            app_module.db.session.commit()
        response = self._post(self.OWNER, record_id, 'cancel')
        self.assertEqual(response.status_code, 409)
        self.assertIn('Liquidation has started', response.get_json()['error'])


    # ---------- page ----------
    def test_list_flags_and_page_actions(self):
        record_id = self._approved(DEPARTURE + timedelta(days=240))
        items = self._client(self.OWNER).get('/get_my_travel_requests').get_json()['items']
        item = next(row for row in items if row['id'] == record_id)
        self.assertTrue(item['can_amend'])
        self.assertTrue(item['can_cancel'])

        root = pathlib.Path(__file__).resolve().parents[1] / 'templates'
        page = (root / 'travel_request.html').read_text(encoding='utf-8')
        self.assertIn("status === 'amending'", page)
        self.assertIn("openTravelAmendCancel('amend'", page)
        self.assertIn("openTravelAmendCancel('cancel'", page)
        self.assertIn("amend_started: 'Reopened for amendment'", page)
        modal = (root / '_request_recall_modal.html').read_text(encoding='utf-8')
        self.assertIn('opts.url ||', modal)
        self.assertIn("typeof opts.onSuccess === 'function'", modal)


if __name__ == '__main__':
    unittest.main()
