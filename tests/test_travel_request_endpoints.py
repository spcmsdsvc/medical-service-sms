"""Travel Request — Batch 2 (plans.md): HTTP tests for save, submit, delete, attachments,
restore blocks, history paging and form wording. Own temp DB and TRE-TEST- prefix.
"""
import base64
import io
import os
import pathlib
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_travel_request_endpoints_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402

PNG_1X1 = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
)
DEPARTURE = date(2031, 3, 2)


class TravelRequestEndpointTests(unittest.TestCase):
    OWNER = 'tr_endpoints_owner'
    PARTICIPANT = 'tr_endpoints_participant'
    ADMIN = 'tr_endpoints_admin'
    OTHER = 'tr_endpoints_other'
    PAGER = 'tr_endpoints_pager'
    USERNAMES = (OWNER, PARTICIPANT, ADMIN, OTHER, PAGER)
    EMPLOYEE_IDS = ('TRE-E1', 'TRE-E2')
    PREFIX = 'TRE-TEST-'

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_travel_request_tables()
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
                m.TravelRequestAttachment.query.filter_by(travel_request_id=rec.id).delete(synchronize_session=False)
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
        users = {name: m.User(username=name, role='engineer', is_active=True, password=m.generate_password_hash('Endpoints123'))
                 for name in cls.USERNAMES}
        users[cls.ADMIN].role = 'superadmin'
        db.session.add_all(users.values())
        db.session.commit()
        cls.ids = {name: user.id for name, user in users.items()}
        owner_engineer = m.Engineer(employee_id=cls.EMPLOYEE_IDS[0], name='TR Endpoints Owner', initials='TO', branch='Manila', user_id=cls.ids[cls.OWNER])
        participant_engineer = m.Engineer(employee_id=cls.EMPLOYEE_IDS[1], name='TR Endpoints Participant', initials='TP', branch='Manila', user_id=cls.ids[cls.PARTICIPANT])
        db.session.add_all([owner_engineer, participant_engineer])
        db.session.commit()
        cls.owner_engineer_id = owner_engineer.id
        now = m.get_manila_time()
        for index in range(55):
            db.session.add(m.TravelRequest(request_no=f'{cls.PREFIX}PAGE-{index:02d}', user_id=cls.ids[cls.PAGER], purpose='Paging trip',
                                           status='Draft', updated_at=now - timedelta(minutes=index)))
        db.session.commit()

    # ---------- helpers ----------
    def _client(self, username):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.ids[username])
            session['_fresh'] = True
        return client

    def _payload(self, record_id=None, days=3, amount=1500, departure=DEPARTURE):
        return {
            'id': record_id or '',
            'request_type': 'Training',
            'purpose': 'Training trip for endpoint tests',
            'training_title': 'Endpoint Training',
            'departure_date': departure.isoformat(),
            'return_date': (departure + timedelta(days=days - 1)).isoformat(),
            'currency_code': 'PHP',
            'participants': [],
            'routes': [{'from_location': 'Manila', 'to_location': 'Cebu', 'travel_type': 'Air Travel', 'route_summary': 'Manila → Cebu', 'visits': []}],
            'lines': [{'line_type': 'Meals', 'description': 'Meals', 'amount': amount, 'source_currency_code': 'PHP', 'source_amount': amount, 'exchange_rate': 1}],
        }

    def _create_draft(self, **kwargs):
        response = self._client(self.OWNER).post('/save_travel_request_draft', json=self._payload(**kwargs))
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()['travel_request']['id']

    def _record(self, record_id):
        with self.app.app_context():
            return app_module.db.session.get(app_module.TravelRequest, record_id)

    def _set(self, record_id, **fields):
        with self.app.app_context():
            rec = app_module.db.session.get(app_module.TravelRequest, record_id)
            for key, value in fields.items():
                setattr(rec, key, value)
            app_module.db.session.commit()

    def _add_participant(self, record_id):
        with self.app.app_context():
            app_module.db.session.add(app_module.TravelRequestParticipant(travel_request_id=record_id, user_id=self.ids[self.PARTICIPANT]))
            app_module.db.session.commit()

    # ---------- save ----------
    def test_save_rights(self):
        record_id = self._create_draft()
        with self.app.app_context():
            rec = app_module.db.session.get(app_module.TravelRequest, record_id)
            self.assertEqual(len(rec.routes), 1)
            self.assertEqual(float(rec.requested_amount), 1500.0)
        self.assertEqual(self._client(self.OWNER).post('/save_travel_request_draft', json=self._payload(record_id, amount=2000)).status_code, 200)
        self._add_participant(record_id)
        self.assertEqual(self._client(self.PARTICIPANT).post('/save_travel_request_draft', json=self._payload(record_id)).status_code, 200)
        self.assertEqual(self._client(self.OTHER).post('/save_travel_request_draft', json=self._payload(record_id)).status_code, 403)
        with mock.patch.object(app_module, 'is_admin_authorized', return_value=True):
            self.assertEqual(self._client(self.ADMIN).post('/save_travel_request_draft', json=self._payload(record_id)).status_code, 403)

    def test_save_refuses_non_editable_and_bad_dates(self):
        record_id = self._create_draft()
        client = self._client(self.OWNER)
        payload = self._payload(record_id)
        payload['return_date'] = (DEPARTURE - timedelta(days=1)).isoformat()
        self.assertEqual(client.post('/save_travel_request_draft', json=payload).status_code, 400)
        self._set(record_id, status='Submitted')
        self.assertEqual(client.post('/save_travel_request_draft', json=self._payload(record_id)).status_code, 409)

    def test_save_trip_limit(self):
        client = self._client(self.OWNER)
        response = client.post('/save_travel_request_draft', json=self._payload(days=91))
        self.assertEqual(response.status_code, 400)
        self.assertIn('at most 90 days', response.get_json()['error'])
        self.assertEqual(client.post('/save_travel_request_draft', json=self._payload(days=90, departure=DEPARTURE + timedelta(days=200))).status_code, 200)

    def test_save_amount_limit(self):
        record_id = self._create_draft(departure=DEPARTURE + timedelta(days=400))
        client = self._client(self.OWNER)
        response = client.post('/save_travel_request_draft', json=self._payload(record_id, amount=10_000_000.01, departure=DEPARTURE + timedelta(days=400)))
        self.assertEqual(response.status_code, 400)
        self.assertIn('cannot exceed', response.get_json()['error'])
        self.assertEqual(float(self._record(record_id).requested_amount), 1500.0)
        with self.app.app_context():
            self.assertEqual(app_module.TravelRequestLine.query.filter_by(travel_request_id=record_id).count(), 1)
        self.assertEqual(client.post('/save_travel_request_draft', json=self._payload(record_id, amount=10_000_000, departure=DEPARTURE + timedelta(days=400))).status_code, 200)
        negative = self._payload(record_id, amount=-5, departure=DEPARTURE + timedelta(days=400))
        self.assertEqual(client.post('/save_travel_request_draft', json=negative).status_code, 400)

    # ---------- submit ----------
    def test_submit_guards(self):
        departure = DEPARTURE + timedelta(days=600)
        record_id = self._create_draft(departure=departure)
        client = self._client(self.OWNER)
        self._set(record_id, return_date=None)
        self.assertEqual(client.post(f'/submit_travel_request/{record_id}').status_code, 400)
        self._set(record_id, return_date=departure + timedelta(days=90))
        response = client.post(f'/submit_travel_request/{record_id}')
        self.assertEqual(response.status_code, 400)
        self.assertIn('at most 90 days', response.get_json()['error'])
        self._set(record_id, return_date=departure + timedelta(days=2))
        response = client.post(f'/submit_travel_request/{record_id}')
        self.assertEqual(response.status_code, 428)
        self.assertTrue(response.get_json()['requires_signature'])

    # ---------- delete draft ----------
    def test_delete_draft(self):
        record_id = self._create_draft(departure=DEPARTURE + timedelta(days=800))
        self.assertEqual(self._client(self.OTHER).post(f'/delete_travel_request_draft/{record_id}').status_code, 403)
        self._set(record_id, status='Submitted')
        self.assertEqual(self._client(self.OWNER).post(f'/delete_travel_request_draft/{record_id}').status_code, 409)
        self._set(record_id, status='Draft')
        self.assertEqual(self._client(self.OWNER).post(f'/delete_travel_request_draft/{record_id}').status_code, 200)
        self.assertIsNone(self._record(record_id))

    # ---------- attachments ----------
    def test_attachments(self):
        record_id = self._create_draft(departure=DEPARTURE + timedelta(days=1000))
        client = self._client(self.OWNER)

        def upload(c, name, data):
            return c.post(f'/upload_travel_request_attachments/{record_id}', data={'attachment_files': (io.BytesIO(data), name)},
                          content_type='multipart/form-data')

        self.assertEqual(upload(client, 'note.txt', b'hello').status_code, 400)
        with mock.patch.object(app_module, 'is_admin_authorized', return_value=True):
            self.assertIn(upload(self._client(self.ADMIN), 'admin.png', PNG_1X1).status_code, (403, 409))
        self.assertEqual(upload(client, 'one.png', PNG_1X1).status_code, 200)
        self.assertEqual(upload(client, 'two.png', PNG_1X1).status_code, 200)
        with self.app.app_context():
            attachment_ids = [a.id for a in app_module.TravelRequestAttachment.query.filter_by(travel_request_id=record_id).all()]
        self.assertEqual(len(attachment_ids), 2)
        with mock.patch.object(app_module, 'is_admin_authorized', return_value=True):
            self.assertIn(self._client(self.ADMIN).post(f'/delete_travel_request_attachment/{attachment_ids[0]}').status_code, (403, 409))
        self.assertEqual(client.post(f'/delete_travel_request_attachment/{attachment_ids[0]}').status_code, 200)
        response = client.post(f'/delete_all_travel_request_attachments/{record_id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json().get('attachments', []), [])
        self._set(record_id, status='Submitted')
        self.assertIn(upload(client, 'late.png', PNG_1X1).status_code, (403, 409))

    # ---------- restore blocks ----------
    def test_restore_blocks_guards(self):
        record_id = self._create_draft(departure=DEPARTURE + timedelta(days=1200))
        response = self._client(self.OWNER).post(f'/restore_travel_blocks/{record_id}')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Only approved', response.get_json()['error'])
        self._set(record_id, status='Approved', engineer_id=self.owner_engineer_id)
        response = self._client(self.OTHER).post(f'/restore_travel_blocks/{record_id}')
        self.assertEqual(response.status_code, 400)
        self.assertIn('not authorized', response.get_json()['error'])

    # ---------- history paging ----------
    def test_history_paging(self):
        client = self._client(self.PAGER)
        first = client.get('/get_my_travel_requests').get_json()
        self.assertEqual(len(first['items']), 50)
        self.assertTrue(first['has_more'])
        second = client.get('/get_my_travel_requests?offset=50').get_json()
        self.assertEqual(len(second['items']), 5)
        self.assertFalse(second['has_more'])
        self.assertFalse({i['id'] for i in first['items']} & {i['id'] for i in second['items']})

    # ---------- form wording ----------
    def test_form_wording(self):
        record_id = self._create_draft(departure=DEPARTURE + timedelta(days=1400))
        html = self._client(self.OWNER).get(f'/preview_approved_travel_request_form/{record_id}').get_data(as_text=True)
        self.assertIn('Travel Request Form -', html)
        self.assertNotIn('Approved Travel Request Form', html)
        with self.app.app_context():
            rec = app_module.db.session.get(app_module.TravelRequest, record_id)
            self.assertEqual(app_module.travel_request_amount_label(rec), 'Requested Amount')
            rec.status = 'Approved'
            self.assertEqual(app_module.travel_request_amount_label(rec), 'Approved Amount')
            app_module.db.session.rollback()


if __name__ == '__main__':
    unittest.main()
