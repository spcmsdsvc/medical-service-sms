"""Cash Advance Batch 1: server checks on save/submit, CSRF on attachments, draft delete, light list."""

import io
import os
import pathlib
import re
import tempfile
import unittest
from datetime import timedelta
from unittest.mock import patch

from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import create_engine, event


ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / 'app.py').read_text(encoding='utf-8')
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_cash_advance_server_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402


def _png_bytes():
    from PIL import Image
    buffer = io.BytesIO()
    Image.new('RGB', (4, 4), (255, 255, 255)).save(buffer, format='PNG')
    return buffer.getvalue()


class CashAdvanceServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        engines = cls.app.extensions['sqlalchemy']._app_engines[cls.app]
        cls.original_engine = engines[None]
        cls.test_engine = create_engine(f"sqlite:///{_TEST_DB_PATH.as_posix()}")
        engines[None] = cls.test_engine
        cls.upload_dir = tempfile.mkdtemp()
        with cls.app.app_context():
            app_module.db.create_all()
            owner = app_module.User(username='ca_owner', password='test-only', role='engineer', is_active=True)
            other = app_module.User(username='ca_other', password='test-only', role='engineer', is_active=True)
            app_module.db.session.add_all([owner, other])
            app_module.db.session.commit()
            cls.owner_id, cls.other_id = owner.id, other.id

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

    def setUp(self):
        self.app.config['WTF_CSRF_ENABLED'] = False

    def tearDown(self):
        self.app.config['WTF_CSRF_ENABLED'] = False

    # helpers
    def _client(self, user_id=None):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id or self.owner_id)
            session['_fresh'] = True
        return client

    def _csrf_client(self, user_id=None):
        """Client with CSRF on; returns (client, header token) as the page would send."""
        self.app.config['WTF_CSRF_ENABLED'] = True
        client = self._client(user_id)
        raw = 'cash-advance-test-token'
        with client.session_transaction() as session:
            session['csrf_token'] = raw
        signed = URLSafeTimedSerializer(self.app.secret_key, salt='wtf-csrf-token').dumps(raw)
        return client, {'X-CSRFToken': signed}

    def _today(self):
        with self.app.app_context():
            return app_module.get_manila_today()

    def _payload(self, **overrides):
        payload = {
            'needed_date': (self._today() + timedelta(days=3)).isoformat(),
            'amount_requested': 1500,
            'liquidation_days': 30,
            'purpose': 'Site visit',
        }
        payload.update(overrides)
        return payload

    def _make(self, status='Draft', user_id=None, **fields):
        with self.app.app_context():
            header = app_module.CashAdvanceHeader(
                user_id=user_id or self.owner_id, status=status,
                request_date=self._today(), needed_date=self._today() + timedelta(days=3),
                amount_requested=fields.pop('amount_requested', 1000), liquidation_days=30,
                purpose='Test', created_at=app_module.get_manila_time(), updated_at=app_module.get_manila_time(),
                **fields,
            )
            app_module.db.session.add(header)
            app_module.db.session.commit()
            header.cash_advance_no = f'CA-TEST-{header.id}'
            app_module.db.session.commit()
            return header.id

    def _save(self, **overrides):
        return self._client().post('/save_cash_advance', json=self._payload(**overrides))

    # save / submit
    def test_save_rejects_bad_amounts_days_and_past_date(self):
        cases = [
            ({'amount_requested': 'nan'}, 'greater than zero'),
            ({'amount_requested': 'inf'}, 'greater than zero'),
            ({'amount_requested': -5}, 'greater than zero'),
            ({'amount_requested': 20000000}, 'cannot exceed'),
            ({'liquidation_days': 'inf'}, '1 to 365'),
            ({'liquidation_days': 400}, '1 to 365'),
            ({'needed_date': (self._today() - timedelta(days=1)).isoformat()}, 'past'),
        ]
        for overrides, message in cases:
            with self.subTest(overrides=overrides):
                response = self._save(**overrides)
                self.assertEqual(response.status_code, 400, response.get_data(as_text=True))
                self.assertIn(message, response.get_json()['error'])

    def test_save_sets_request_date_on_server(self):
        response = self._save(request_date='2001-01-01')
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.get_json()['item']['request_date'], self._today().isoformat())

    def test_submit_rejects_stored_infinite_amount(self):
        record_id = self._make(amount_requested=float('inf'))
        response = self._client().post(f'/submit_cash_advance/{record_id}', json={})
        self.assertEqual(response.status_code, 400)
        self.assertIn('Correct the amount', response.get_json()['error'])

    def test_edit_wording_says_rejected(self):
        record_id = self._make(status='Submitted')
        response = self._client().post('/save_cash_advance', json=self._payload(id=record_id))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()['error'], 'Only Draft or Rejected cash advances can be edited.')

    # CSRF on the attachment routes
    def _attachment_requests(self, client, headers):
        record_id = self._make()
        with patch.object(app_module, 'cash_advance_attachment_upload_root', return_value=self.upload_dir), \
                patch.object(app_module, 'managed_storage_write_bytes', return_value=None), \
                patch.object(app_module, 'managed_storage_delete', return_value=None):
            upload = client.post(
                f'/upload_cash_advance_attachments/{record_id}', headers=headers,
                data={'attachment_files': (io.BytesIO(_png_bytes()), 'slip.png')},
                content_type='multipart/form-data')
            with self.app.app_context():
                attachment = app_module.CashAdvanceAttachment.query.filter_by(cash_advance_id=record_id).first()
            attachment_id = attachment.id if attachment else 999999
            delete_one = client.post(f'/delete_cash_advance_attachment/{attachment_id}', headers=headers)
            delete_all = client.post(f'/delete_all_cash_advance_attachments/{record_id}', headers=headers)
        return upload, delete_one, delete_all

    def test_attachment_routes_require_csrf_token(self):
        client, _ = self._csrf_client()
        for response in self._attachment_requests(client, {}):
            self.assertEqual(response.status_code, 400)

    def test_attachment_routes_accept_csrf_token(self):
        client, headers = self._csrf_client()
        for response in self._attachment_requests(client, headers):
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

    # draft delete
    def test_delete_draft_removes_record_attachments_and_linked_lprs(self):
        record_id = self._make()
        with self.app.app_context():
            app_module.ensure_lpr_tables()
            app_module.db.session.add(app_module.CashAdvanceAttachment(
                cash_advance_id=record_id, file_name='a.png', stored_filename='a.png', original_filename='a.png'))
            app_module.db.session.add(app_module.LPRHeader(
                lpr_no=f'LPR-CA-{record_id}', user_id=self.owner_id, parent_module='cash_advance', cash_advance_id=record_id))
            app_module.db.session.commit()
        client, headers = self._csrf_client()
        with patch.object(app_module, 'managed_storage_delete', return_value=None) as deleted:
            response = client.post(f'/delete_cash_advance_draft/{record_id}', headers=headers)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.get_json()['linked_lprs_removed'], 1)
        self.assertTrue(deleted.called)
        with self.app.app_context():
            self.assertIsNone(app_module.db.session.get(app_module.CashAdvanceHeader, record_id))
            self.assertEqual(app_module.CashAdvanceAttachment.query.filter_by(cash_advance_id=record_id).count(), 0)
            self.assertEqual(app_module.LPRHeader.query.filter_by(cash_advance_id=record_id).count(), 0)

    def test_delete_draft_guards(self):
        other_record = self._make(user_id=self.other_id)
        submitted = self._make(status='Submitted')
        rejected = self._make(status='Rejected')
        self.assertEqual(self._client().post(f'/delete_cash_advance_draft/{other_record}').status_code, 404)
        self.assertEqual(self._client().post(f'/delete_cash_advance_draft/{submitted}').status_code, 409)
        self.assertEqual(self._client().post(f'/delete_cash_advance_draft/{rejected}').status_code, 409)
        client, _ = self._csrf_client()
        self.assertEqual(client.post(f'/delete_cash_advance_draft/{self._make()}').status_code, 400)

    # list
    def _list_query_count(self, user_id, records):
        with self.app.app_context():
            for _ in range(records):
                self._make(user_id=user_id)
        self._client(user_id).get('/get_cash_advance_list')  # warm up one-time table checks
        statements = []
        listener = lambda *args: statements.append(args[2])  # noqa: E731
        event.listen(self.test_engine, 'before_cursor_execute', listener)
        try:
            response = self._client(user_id).get('/get_cash_advance_list')
        finally:
            event.remove(self.test_engine, 'before_cursor_execute', listener)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['count'], records)
        return len(statements), response.get_json()['items']

    def test_list_query_count_does_not_grow_and_has_no_signatures(self):
        with self.app.app_context():
            a = app_module.User(username='ca_list_a', password='test-only', role='engineer', is_active=True)
            b = app_module.User(username='ca_list_b', password='test-only', role='engineer', is_active=True)
            app_module.db.session.add_all([a, b])
            app_module.db.session.commit()
            a_id, b_id = a.id, b.id
        two, _ = self._list_query_count(a_id, 2)
        ten, items = self._list_query_count(b_id, 10)
        self.assertEqual(two, ten)
        self.assertNotIn('requester_signature_snapshot', items[0])
        for key in ('id', 'cash_advance_no', 'status', 'needed_date', 'amount_requested', 'purpose', 'editable',
                    'can_create_liquidation', 'can_open_liquidation', 'create_liquidation_url', 'liquidation_url'):
            self.assertIn(key, items[0])


class CashAdvanceServerSourceTests(unittest.TestCase):
    def test_dead_helpers_removed(self):
        self.assertNotIn('def cash_advance_requester_profile(', APP_SOURCE)
        self.assertNotIn('def cash_advance_user_display_name(', APP_SOURCE)

    def test_attachment_routes_not_csrf_exempt(self):
        for path in ('/upload_cash_advance_attachments/', '/delete_cash_advance_attachment/',
                     '/delete_all_cash_advance_attachments/', '/delete_cash_advance_draft/'):
            block = APP_SOURCE[APP_SOURCE.index(f"@app.route('{path}"):]
            self.assertNotIn('@csrf.exempt', block[:block.index('def ')])

    def test_kept_functions(self):
        for name in ('cash_advance_money', 'cash_advance_to_dict', 'can_user_manage_own_cash_advance',
                     'save_cash_advance', 'submit_cash_advance', 'get_cash_advance', 'get_cash_advance_list',
                     'upload_cash_advance_attachments', 'delete_cash_advance_attachment',
                     'delete_all_cash_advance_attachments', 'preview_cash_advance_attachment',
                     'download_cash_advance_attachment', 'cash_advance'):
            self.assertTrue(re.search(rf'^def {name}\(', APP_SOURCE, re.M), name)
        self.assertIn("return round(float(value or 0), 2)", APP_SOURCE)


if __name__ == '__main__':
    unittest.main()
