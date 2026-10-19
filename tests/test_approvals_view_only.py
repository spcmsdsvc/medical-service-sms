"""Settings "Approvals view only": read every approval, decide none.

A view-only account has no approval routes. It must see every requester's records in the
Approval Center queues and details (GET), while every decision endpoint (POST) refuses it.
"""

import os
import pathlib
import tempfile
import unittest
import uuid
from datetime import timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f'medical_service_view_only_{uuid.uuid4().hex}.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402

m = app_module
db = app_module.db


class ApprovalsViewOnlySourceTests(unittest.TestCase):
    def test_settings_switch_is_rendered_and_saved(self):
        settings = (ROOT / 'templates' / 'settings.html').read_text(encoding='utf-8')
        self.assertIn("'approval-view-only-input', user.approvals_view_only, 'Approvals view only'", settings)
        save_block = settings.split('async function saveApprovalUser(userId)')[1].split('async function')[0]
        self.assertIn("approvals_view_only: Boolean(card.querySelector('.approval-view-only-input')?.checked)", save_block)

    def test_approvals_page_hides_decision_controls_for_view_only(self):
        page = (ROOT / 'templates' / 'approvals.html').read_text(encoding='utf-8')
        block = page.split('{% if approval_center_view_only %}')[1].split('{% endif %}')[0]
        for element_id in ('#approvalApproveBtn', '#approvalRejectBtn', '#approvalResendEmailBtn', '#approvalRemarks'):
            self.assertIn(element_id, block)


class ApprovalsViewOnlyWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.suffix = uuid.uuid4().hex[:10]
        cls.owned_user_ids = []

        with cls.app.app_context():
            db.create_all()
            m.ensure_approval_routing_schema()
            m.ensure_travel_request_tables()
            m.ensure_cash_advance_tables()

            def add_user(username, role='staff', **flags):
                flags.setdefault('is_active', True)
                user = m.User(
                    username=f'{username}_{cls.suffix}',
                    password=m.generate_password_hash('test-password'),
                    role=role,
                    **flags,
                )
                db.session.add(user)
                db.session.flush()
                cls.owned_user_ids.append(user.id)
                return user

            superadmin = m.User.query.filter_by(username='jonamar').first()
            if not superadmin:
                superadmin = add_user('jonamar_vo', role='superadmin')
            cls.superadmin_id = superadmin.id
            cls.viewer_id = add_user('vo_viewer', approvals_view_only=True).id
            cls.plain_id = add_user('vo_plain').id
            cls.requester_id = add_user('vo_requester').id

            today = m.get_manila_time().date()
            travel = m.TravelRequest(
                request_no=f'VO-TR-{cls.suffix}', user_id=cls.requester_id, purpose='View-only trip',
                status='Submitted', departure_date=today, return_date=today + timedelta(days=1),
            )
            cash = m.CashAdvanceHeader(
                cash_advance_no=f'VO-CA-{cls.suffix}', user_id=cls.requester_id, status='Submitted',
                amount_requested=1000,
            )
            db.session.add_all([travel, cash])
            db.session.commit()
            cls.travel_id = travel.id
            cls.cash_id = cash.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            m.TravelRequest.query.filter_by(id=cls.travel_id).delete()
            m.CashAdvanceHeader.query.filter_by(id=cls.cash_id).delete()
            for user_id in reversed(cls.owned_user_ids):
                user = db.session.get(m.User, user_id)
                if user:
                    db.session.delete(user)
            db.session.commit()
            db.session.remove()

    @classmethod
    def _client_for(cls, user_id):
        client = cls.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def _status(self, model, record_id):
        with self.app.app_context():
            return db.session.get(model, record_id).status

    def test_view_only_opens_approvals_and_plain_user_does_not(self):
        page = self._client_for(self.viewer_id).get('/approvals')
        self.assertEqual(page.status_code, 200)
        self.assertIn('View only — you cannot approve or return.', page.get_data(as_text=True))
        self.assertEqual(self._client_for(self.plain_id).get('/approvals').status_code, 302)

    def test_view_only_reads_unrouted_queues_and_details(self):
        client = self._client_for(self.viewer_id)
        queue = client.get('/get_travel_request_approval_queue').get_json()
        self.assertIn(self.travel_id, [row['id'] for row in queue.get('travel_requests', queue.get('items', []))])
        detail = client.get(f'/get_travel_request_approval/{self.travel_id}')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(client.get(f'/get_cash_advance_approval/{self.cash_id}').status_code, 200)
        ca_queue = client.get('/get_cash_advance_approval_queue').get_json()
        self.assertIn(self.cash_id, [row['id'] for row in ca_queue.get('cash_advances', ca_queue.get('items', []))])

    def test_view_only_cannot_decide(self):
        client = self._client_for(self.viewer_id)
        for url in (
            f'/approve_travel_request/{self.travel_id}',
            f'/reject_travel_request/{self.travel_id}',
            f'/approve_cash_advance/{self.cash_id}',
            f'/reject_cash_advance/{self.cash_id}',
        ):
            response = client.post(url, json={'remarks': 'view-only attempt'})
            self.assertEqual(response.status_code, 403, url)
        self.assertEqual(self._status(m.TravelRequest, self.travel_id), 'Submitted')
        self.assertEqual(self._status(m.CashAdvanceHeader, self.cash_id), 'Submitted')

    def test_settings_refuses_approver_and_view_only_together(self):
        client = self._client_for(self.superadmin_id)
        payload = {'user_id': self.plain_id, 'can_approve_requests': True, 'approvals_view_only': True, 'is_active': True}
        response = client.post('/settings/update-approval-user', json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn('view only', response.get_json()['error'])

        payload['can_approve_requests'] = False
        response = client.post('/settings/update-approval-user', json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['user']['approvals_view_only'])
        payload['approvals_view_only'] = False
        client.post('/settings/update-approval-user', json=payload)


if __name__ == '__main__':
    unittest.main()
