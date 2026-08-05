"""Regression tests for requester-owned withdrawal of Submitted requests."""

import os
import pathlib
import tempfile
import unittest
import uuid
from datetime import date, datetime

from flask_login import login_user, logout_user
from sqlalchemy import create_engine

ROOT = pathlib.Path(__file__).resolve().parents[1]
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f'medical_service_request_recall_tests_{uuid.uuid4().hex}.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402


class RequestRecallSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.partial = (ROOT / 'templates' / '_request_recall_modal.html').read_text(encoding='utf-8')
        cls.releases = (ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8')

    def test_registry_and_endpoint_cover_only_the_approved_modules(self):
        for module in ('leave_request', 'reimbursement', 'travel_request', 'cash_advance', 'lpr'):
            self.assertIn(f"'{module}':", self.app_source)
        self.assertIn("@app.route('/api/requests/<module>/<int:record_id>/recall'", self.app_source)
        self.assertNotIn("'travel_liquidation':", self.app_source[self.app_source.index('RECALL_REQUEST_REGISTRY'):self.app_source.index('def recall_request_display_label')])
        self.assertNotIn("'cash_advance_liquidation':", self.app_source[self.app_source.index('RECALL_REQUEST_REGISTRY'):self.app_source.index('def recall_request_display_label')])
        self.assertIn("func.lower(func.trim(model.status)) == 'submitted'", self.app_source)

    def test_shared_dialog_is_present_in_every_requester_surface(self):
        for template_name in ('leave_request.html', 'reimbursement.html', 'travel_request.html', 'cash_advance.html', 'lpr.html'):
            source = (ROOT / 'templates' / template_name).read_text(encoding='utf-8')
            self.assertIn("{% include '_request_recall_modal.html' %}", source)
        for marker in ('openRequestRecall', 'submitRequestRecall', 'A reason is required'):
            self.assertIn(marker, self.partial)
        self.assertIn('2026-08-05-request-recall', self.releases)
        self.assertIn('v66-request-recall', self.app_source)


class RequestRecallWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.created_ids = []
        cls.original_engine = None
        cls.test_engine = None

        with cls.app.app_context():
            extension = cls.app.extensions['sqlalchemy']
            engines = extension._app_engines[cls.app]
            cls.original_engine = engines[None]
            cls.test_engine = create_engine(f"sqlite:///{_TEST_DB_PATH.as_posix()}")
            engines[None] = cls.test_engine
            app_module.db.create_all()
            app_module.ensure_leave_request_tables()
            app_module.ensure_cash_advance_tables()
            app_module.ensure_lpr_tables()
            app_module.ensure_universal_approval_audit_table()
            app_module.ensure_system_notification_table()

            cls.requester = app_module.User(
                username='recall_requester',
                password='test-only',
                role='engineer',
                is_active=True,
            )
            cls.other_user = app_module.User(
                username='recall_other',
                password='test-only',
                role='engineer',
                is_active=True,
            )
            app_module.db.session.add_all([cls.requester, cls.other_user])
            app_module.db.session.flush()
            cls.engineer = app_module.Engineer(
                user_id=cls.requester.id,
                employee_id='RECALL-001',
                name='Recall Requester',
                initials='RR',
                branch='Manila',
            )
            app_module.db.session.add(cls.engineer)
            app_module.db.session.commit()
            cls.requester_id = cls.requester.id
            cls.other_user_id = cls.other_user.id
            cls.engineer_id = cls.engineer.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            for module, record_id in cls.created_ids:
                entry = app_module.RECALL_REQUEST_REGISTRY[module]
                record = app_module.db.session.get(entry['model'], record_id)
                if record:
                    app_module.db.session.delete(record)
            user = app_module.db.session.get(app_module.User, cls.requester_id)
            other = app_module.db.session.get(app_module.User, cls.other_user_id)
            engineer = app_module.db.session.get(app_module.Engineer, cls.engineer_id)
            for item in (engineer, user, other):
                if item:
                    app_module.db.session.delete(item)
            app_module.db.session.commit()
            app_module.db.session.remove()
            cls.test_engine.dispose()
            app_module.app.extensions['sqlalchemy']._app_engines[cls.app][None] = cls.original_engine

    @classmethod
    def _submitted_records(cls):
        suffix = uuid.uuid4().hex[:8]
        created = {
            'leave_request': app_module.LeaveRequest(
                request_no=f'LR-20990101-{suffix}', user_id=cls.requester_id, engineer_id=cls.engineer_id,
                application_date=date(2099, 1, 1), leave_type='Vacation Leave',
                start_date=date(2099, 1, 2), end_date=date(2099, 1, 2), status='Submitted',
                submitted_at=datetime(2099, 1, 1),
            ),
            'reimbursement': app_module.ReimbursementHeader(
                user_id=cls.requester_id, engineer_id=cls.engineer_id,
                start_date=date(2099, 1, 2), end_date=date(2099, 1, 2), status='Submitted',
                submitted_at=datetime(2099, 1, 1),
            ),
            'travel_request': app_module.TravelRequest(
                request_no=f'TR-20990101-{suffix}', user_id=cls.requester_id, engineer_id=cls.engineer_id,
                purpose='Recall test travel', status='Submitted', submitted_at=datetime(2099, 1, 1),
            ),
            'cash_advance': app_module.CashAdvanceHeader(
                cash_advance_no=f'CA-20990101-{suffix}', user_id=cls.requester_id,
                request_date=date(2099, 1, 1), needed_date=date(2099, 1, 2),
                purpose='Recall test cash advance', status='Submitted', submitted_at=datetime(2099, 1, 1),
            ),
            'lpr': app_module.LPRHeader(
                lpr_no=f'LPR-20990101-{suffix}', user_id=cls.requester_id,
                request_date=date(2099, 1, 1), status='Submitted', submitted_at=datetime(2099, 1, 1),
            ),
        }
        app_module.db.session.add_all(created.values())
        app_module.db.session.commit()
        for module, record in created.items():
            cls.created_ids.append((module, record.id))
        return created

    @classmethod
    def _call_recall(cls, user_id, module, record_id, payload):
        with cls.app.test_request_context(
            f'/api/requests/{module}/{record_id}/recall',
            method='POST',
            json=payload,
        ):
            user = app_module.db.session.get(app_module.User, user_id)
            login_user(user)
            try:
                return cls.app.make_response(app_module.recall_submitted_request(module, record_id))
            finally:
                logout_user()

    def test_each_supported_module_returns_to_editable_state(self):
        with self.app.app_context():
            records = self._submitted_records()
            expected = {
                'leave_request': 'Draft',
                'reimbursement': 'Draft',
                'travel_request': 'Draft',
                'cash_advance': 'Draft',
                'lpr': 'Draft',
            }
            for module, record in records.items():
                response = self._call_recall(self.requester_id, module, record.id, {'reason': 'Correcting the submitted details.'})
                self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
                self.assertEqual(response.get_json()['status'], expected[module])
                refreshed = app_module.db.session.get(app_module.RECALL_REQUEST_REGISTRY[module]['model'], record.id)
                self.assertEqual(refreshed.status, expected[module])
                self.assertIsNone(getattr(refreshed, 'submitted_at', None))
                self.assertIsNone(getattr(refreshed, 'approved_at', None))
                self.assertIsNone(getattr(refreshed, 'approval_signature_snapshot', None))
                audit = app_module.UniversalApprovalAuditTrail.query.filter_by(
                    module=module, record_id=record.id, action='recalled'
                ).first()
                self.assertIsNotNone(audit)
                self.assertEqual(audit.status_from, 'Submitted')
                self.assertEqual(audit.status_to, expected[module])
                self.assertIn('Correcting', audit.remarks or '')

    def test_owner_reason_and_status_guards(self):
        with self.app.app_context():
            records = self._submitted_records()
            reimbursement = records['reimbursement']

            wrong_owner = self._call_recall(self.other_user_id, 'reimbursement', reimbursement.id, {'reason': 'Not mine.'})
            self.assertEqual(wrong_owner.status_code, 403)

            empty_reason = self._call_recall(self.requester_id, 'reimbursement', reimbursement.id, {'reason': '   '})
            self.assertEqual(empty_reason.status_code, 400)

            reimbursement.status = 'Draft'
            app_module.db.session.commit()
            not_submitted = self._call_recall(self.requester_id, 'reimbursement', reimbursement.id, {'reason': 'Too late.'})
            self.assertEqual(not_submitted.status_code, 409)

    def test_leave_recall_destination_contract_preserves_provisional_state(self):
        with self.app.app_context():
            provisional = app_module.LeaveRequest(
                request_no='LR-20990101-02', user_id=self.requester_id, engineer_id=self.engineer_id,
                application_date=date(2099, 1, 1), leave_type='Sick Leave',
                start_date=date(2099, 1, 2), end_date=date(2099, 1, 2), status='Submitted',
                submitted_at=datetime(2099, 1, 1), emergency_form_to_follow=True,
                provisional_created_at=datetime(2098, 12, 31),
            )
            app_module.db.session.add(provisional)
            app_module.db.session.commit()
            self.created_ids.append(('leave_request', provisional.id))
            response = self._call_recall(self.requester_id, 'leave_request', provisional.id, {'reason': 'Add the formal signature.'})
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
            self.assertEqual(response.get_json()['status'], 'Provisional')


if __name__ == '__main__':
    unittest.main()
