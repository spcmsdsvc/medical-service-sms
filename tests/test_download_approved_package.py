"""Approvals "Download approved package": the accounting email's attachment, one download.

Travel Request and Cash Advance download their official PDF; Reimbursement and both
liquidations download the email's ZIP. Approved records only, for anyone who can read
the approval (routed approver, admin, view-only account).
"""

import io
import os
import pathlib
import tempfile
import unittest
import uuid
import zipfile
from datetime import timedelta
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f'medical_service_approved_package_{uuid.uuid4().hex}.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402

m = app_module
db = app_module.db


class DownloadApprovedPackageSourceTests(unittest.TestCase):
    def test_button_is_wired_and_not_hidden_for_view_only(self):
        page = (ROOT / 'templates' / 'approvals.html').read_text(encoding='utf-8')
        self.assertIn('id="approvalDownloadPackageBtn"', page)
        resend_block = page.split('function updateApprovalResendButton(data)')[1].split('async function')[0]
        self.assertIn('/download_approved_package/${encodeURIComponent(moduleKey)}/${recordId}', resend_block)
        view_only_block = page.split('{% if approval_center_view_only %}')[1].split('{% endif %}')[0]
        self.assertNotIn('approvalDownloadPackageBtn', view_only_block)


class DownloadApprovedPackageWorkflowTests(unittest.TestCase):
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
            m.ensure_reimbursement_accounting_columns()

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

            cls.viewer_id = add_user('pkg_viewer', approvals_view_only=True).id
            cls.plain_id = add_user('pkg_plain').id
            cls.requester_id = add_user('pkg_requester').id

            today = m.get_manila_time().date()
            travel = m.TravelRequest(
                request_no=f'PKG-TR-{cls.suffix}', user_id=cls.requester_id, purpose='Package trip',
                status='Approved', departure_date=today, return_date=today + timedelta(days=1),
            )
            travel_submitted = m.TravelRequest(
                request_no=f'PKG-TS-{cls.suffix}', user_id=cls.requester_id, purpose='Package trip',
                status='Submitted', departure_date=today, return_date=today + timedelta(days=1),
            )
            cash = m.CashAdvanceHeader(
                cash_advance_no=f'PKG-CA-{cls.suffix}', user_id=cls.requester_id, status='Approved',
                amount_requested=1000,
            )
            reimbursement = m.ReimbursementHeader(
                user_id=cls.requester_id, status='Approved',
                start_date=today - timedelta(days=7), end_date=today,
            )
            db.session.add_all([travel, travel_submitted, cash, reimbursement])
            db.session.commit()
            cls.travel_id = travel.id
            cls.travel_submitted_id = travel_submitted.id
            cls.cash_id = cash.id
            cls.reimbursement_id = reimbursement.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            m.TravelRequest.query.filter(m.TravelRequest.id.in_([cls.travel_id, cls.travel_submitted_id])).delete(
                synchronize_session=False
            )
            m.CashAdvanceHeader.query.filter_by(id=cls.cash_id).delete()
            m.ReimbursementHeader.query.filter_by(id=cls.reimbursement_id).delete()
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

    def test_travel_request_and_cash_advance_download_their_pdf(self):
        client = self._client_for(self.viewer_id)
        with mock.patch.object(m, 'build_travel_request_accounting_pdf_bytes', return_value=b'%PDF-travel') as travel_pdf:
            response = client.get(f'/download_approved_package/travel_request/{self.travel_id}')
        self.assertEqual(response.status_code, 200, response.data[:200])
        self.assertEqual(response.mimetype, 'application/pdf')
        self.assertEqual(response.data, b'%PDF-travel')
        self.assertIn('attachment', response.headers['Content-Disposition'])
        travel_pdf.assert_called_once()

        with mock.patch.object(m, 'build_cash_advance_accounting_pdf_bytes', return_value=b'%PDF-cash'):
            response = client.get(f'/download_approved_package/cash-advance/{self.cash_id}')
        self.assertEqual(response.status_code, 200, response.data[:200])
        self.assertEqual(response.data, b'%PDF-cash')

    def test_reimbursement_downloads_the_email_zip(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as package:
            package.writestr('form.pdf', b'%PDF')
        with mock.patch.object(m, 'build_reimbursement_package_zip_bytes', return_value=('pkg.zip', buffer.getvalue())):
            response = self._client_for(self.viewer_id).get(f'/download_approved_package/reimbursement/{self.reimbursement_id}')
        self.assertEqual(response.status_code, 200, response.data[:200])
        self.assertEqual(response.mimetype, 'application/zip')
        self.assertIn('pkg.zip', response.headers['Content-Disposition'])
        self.assertEqual(zipfile.ZipFile(io.BytesIO(response.data)).namelist(), ['form.pdf'])

    def test_refusals(self):
        viewer = self._client_for(self.viewer_id)
        self.assertEqual(self._client_for(self.plain_id).get(f'/download_approved_package/travel_request/{self.travel_id}').status_code, 403)
        self.assertEqual(viewer.get(f'/download_approved_package/travel_request/{self.travel_submitted_id}').status_code, 409)
        self.assertEqual(viewer.get('/download_approved_package/leave_request/1').status_code, 400)
        self.assertEqual(viewer.get('/download_approved_package/travel_request/999999999').status_code, 404)

    def test_builder_failure_is_a_500_not_a_refusal(self):
        with mock.patch.object(m, 'build_travel_request_accounting_pdf_bytes', side_effect=KeyError('boom')):
            response = self._client_for(self.viewer_id).get(f'/download_approved_package/travel_request/{self.travel_id}')
        self.assertEqual(response.status_code, 500)


if __name__ == '__main__':
    unittest.main()
