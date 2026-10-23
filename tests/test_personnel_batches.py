"""Personnel page batches (2026-10-23): Delete, server checks, dark mode, accessibility."""

import os
import pathlib
import re
import tempfile
import unittest
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f'medical_service_personnel_batches_{uuid.uuid4().hex}.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402

TEMPLATE = ROOT / 'templates' / 'engineers.html'


class PersonnelServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.suffix = uuid.uuid4().hex[:8]
        cls.user_ids = []
        cls.engineer_ids = []
        with cls.app.app_context():
            app_module.db.create_all()
            admin = app_module.User(
                username=f'pbadmin{cls.suffix}',
                password=app_module.generate_password_hash('test-password'),
                role='superadmin',
                is_active=True,
            )
            approver = app_module.User(
                username=f'pbapprover{cls.suffix}',
                password=app_module.generate_password_hash('test-password'),
                role='approver',
                is_active=True,
            )
            app_module.db.session.add_all([admin, approver])
            app_module.db.session.commit()
            cls.admin_id, cls.approver_id = admin.id, approver.id
            cls.user_ids += [admin.id, approver.id]

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            ids = cls.user_ids
            app_module.ApprovalRouting.query.filter(app_module.or_(
                app_module.ApprovalRouting.requester_user_id.in_(ids),
                app_module.ApprovalRouting.approver_user_id.in_(ids),
            )).delete(synchronize_session=False)
            for engineer_id in cls.engineer_ids:
                engineer = app_module.db.session.get(app_module.Engineer, engineer_id)
                if engineer:
                    app_module.db.session.delete(engineer)
            app_module.db.session.flush()
            for user_id in ids:
                user = app_module.db.session.get(app_module.User, user_id)
                if user:
                    app_module.db.session.expire(user)
                    app_module.db.session.delete(user)
            app_module.db.session.commit()
            app_module.db.session.remove()

    def _client(self, user_id=None):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id or self.admin_id)
            session['_fresh'] = True
        return client

    def _add(self, **overrides):
        tag = uuid.uuid4().hex[:6]
        payload = {
            'staff_type': 'engineer',
            'employee_id': f'PB-{tag}',
            'name': f'Batch Person {tag}',
            'initials': f'B{tag[:3]}'.upper(),
            'branch': 'Manila',
            'phone': '',
            'email': '',
        }
        payload.update(overrides)
        response = self._client().post('/add_engineer', json=payload)
        if response.status_code == 200:
            with self.app.app_context():
                engineer = app_module.Engineer.query.filter_by(employee_id=payload['employee_id']).first()
                self.engineer_ids.append(engineer.id)
                self.user_ids.append(engineer.user_id)
                return response, engineer.id, engineer.user_id
        return response, None, None

    def _route(self, requester_id, approver_id):
        with self.app.app_context():
            app_module.db.session.add(app_module.ApprovalRouting(
                requester_user_id=requester_id, approver_user_id=approver_id, request_scope='all', active=True
            ))
            app_module.db.session.commit()

    # --- Batch 1: Delete ---------------------------------------------------------

    def test_delete_works_for_an_account_with_routes_and_notices(self):
        _, engineer_id, user_id = self._add()
        self._route(user_id, self.approver_id)
        with self.app.app_context():
            app_module.db.session.add(app_module.SystemNotification(
                user_id=user_id, module='leave_request', title='Test notice'
            ))
            app_module.db.session.commit()

        response = self._client().delete(f'/delete_engineer/{engineer_id}')
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True)[:300])
        with self.app.app_context():
            self.assertIsNone(app_module.db.session.get(app_module.Engineer, engineer_id))
            self.assertIsNone(app_module.db.session.get(app_module.User, user_id))
            self.assertEqual(app_module.ApprovalRouting.query.filter(app_module.or_(
                app_module.ApprovalRouting.requester_user_id == user_id,
                app_module.ApprovalRouting.approver_user_id == user_id,
            )).count(), 0)
            self.assertEqual(app_module.SystemNotification.query.filter_by(user_id=user_id).count(), 0)

    def _assert_refused(self, engineer_id, label):
        response = self._client().delete(f'/delete_engineer/{engineer_id}')
        self.assertEqual(response.status_code, 409, response.get_data(as_text=True)[:300])
        self.assertIn(label, response.get_json()['message'])
        self.assertIn('Deactivate instead', response.get_json()['message'])
        with self.app.app_context():
            self.assertIsNotNone(app_module.db.session.get(app_module.Engineer, engineer_id))

    def _with_row(self, make_row, label):
        _, engineer_id, user_id = self._add()
        with self.app.app_context():
            row = make_row(engineer_id, user_id)
            app_module.db.session.add(row)
            app_module.db.session.commit()
            model, row_id = type(row), row.id
        try:
            self._assert_refused(engineer_id, label)
        finally:
            with self.app.app_context():
                app_module.db.session.delete(app_module.db.session.get(model, row_id))
                app_module.db.session.commit()

    def test_delete_refused_with_a_leave_request(self):
        day = app_module.date(2026, 10, 26)
        self._with_row(lambda e, u: app_module.LeaveRequest(
            request_no=f'LR-PB-{uuid.uuid4().hex[:8]}', user_id=u, engineer_id=e, application_date=day,
            leave_type='vacation', start_date=day, end_date=day, weekday_count=1, status='Submitted',
        ), 'leave requests')

    def test_delete_refused_with_a_cash_advance(self):
        self._with_row(lambda e, u: app_module.CashAdvanceHeader(user_id=u, status='Draft'), 'cash advances')

    def test_delete_refused_with_an_lpr(self):
        self._with_row(lambda e, u: app_module.LPRHeader(user_id=u), 'LPRs')

    def test_delete_refused_with_a_tsr_draft(self):
        self._with_row(lambda e, u: app_module.TsrDraft(
            user_id=u, draft_key=f'pb-{uuid.uuid4().hex}', payload_json='{}'
        ), 'TSR drafts')

    def test_delete_refused_with_a_reimbursement_filed_by_the_login_only(self):
        day = app_module.date(2026, 10, 1)
        self._with_row(lambda e, u: app_module.ReimbursementHeader(
            user_id=u, engineer_id=None, start_date=day, end_date=day
        ), 'reimbursements')

    def test_delete_refused_when_they_approve_for_others(self):
        _, engineer_id, user_id = self._add()
        self._route(self.approver_id, user_id)
        self._assert_refused(engineer_id, 'people they approve for')

    # --- Batch 2: server checks --------------------------------------------------

    def test_add_refuses_unknown_branch_and_long_fields(self):
        for overrides, text in (
            ({'branch': 'Tokyo'}, 'Branch must be Manila, Cebu or Davao.'),
            ({'name': 'N' * 101}, 'Name can be up to 100 characters.'),
            ({'initials': 'ABCDEF'}, 'Initials can be up to 5 characters.'),
            ({'employee_id': 'E' * 51}, 'Employee ID can be up to 50 characters.'),
        ):
            response, _, _ = self._add(**overrides)
            self.assertEqual(response.status_code, 400, overrides)
            self.assertEqual(response.get_json()['message'], text)
        response, _, _ = self._add(branch='Davao')
        self.assertEqual(response.status_code, 200)

    def test_update_refuses_unknown_branch_and_long_initials(self):
        _, engineer_id, _ = self._add()
        with self.app.app_context():
            engineer = app_module.db.session.get(app_module.Engineer, engineer_id)
            base = {
                'employee_id': engineer.employee_id, 'name': engineer.name, 'initials': engineer.initials,
                'phone': '', 'email': '', 'branch': 'Cebu',
            }
        client = self._client()
        self.assertEqual(client.put(f'/update_engineer/{engineer_id}', json={**base, 'branch': 'Tokyo'}).status_code, 400)
        self.assertEqual(client.put(f'/update_engineer/{engineer_id}', json={**base, 'initials': 'ABCDEF'}).status_code, 400)
        self.assertEqual(client.put(f'/update_engineer/{engineer_id}', json=base).status_code, 200)


class PersonnelTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = TEMPLATE.read_text(encoding='utf-8')
        cls.css = cls.html[cls.html.index('<style>'):cls.html.index('</style>')]

    # Batch 2
    def test_reset_window_and_delete_messages(self):
        self.assertTrue("'Temporary Password'" in self.html, "'Temporary Password'")
        self.assertTrue('id="cred-modal-title"' in self.html, 'id="cred-modal-title"')
        self.assertTrue('was deleted.' in self.html, 'was deleted.')
        self.assertFalse('No engineers match your search.' in self.html, 'No engineers match your search.')
        self.assertFalse('Version 5.2.1' in self.html, 'Version 5.2.1')

    # Batch 3
    def test_page_css_uses_theme_colours_and_design_weights(self):
        self.assertFalse('#0f172a' in self.css, '#0f172a')
        self.assertFalse('Courier New' in self.css, 'Courier New')
        self.assertIsNone(re.search(r'font-weight:\s*[789]00', self.css))
        self.assertFalse('font-weight: 950' in self.css, 'font-weight: 950')
        self.assertFalse('btn-outline-warning' in self.html, 'btn-outline-warning')
        self.assertTrue('var(--app-text)' in self.css, 'var(--app-text)')

    # Batch 4
    def test_labels_and_named_windows(self):
        for field_id in ('e-staff-type', 'e-stock-inventory-branch', 'e-branch', 'e-emp-id', 'e-name',
                         'e-initials', 'e-phone', 'e-email', 'cred-username', 'cred-password'):
            self.assertTrue(f'for="{field_id}"' in self.html, f'for="{field_id}"')
        self.assertTrue('id="engModal" tabindex="-1" aria-labelledby="modal-title"' in self.html, 'id="engModal" tabindex="-1" aria-labelledby="modal-title"')
        self.assertTrue('aria-labelledby="cred-modal-title"' in self.html, 'aria-labelledby="cred-modal-title"')
        self.assertTrue('aria-label="Call ' in self.html, 'aria-label="Call ')
        self.assertTrue('aria-label="Email ' in self.html, 'aria-label="Email ')

    def test_page_header_and_safe_confirm_focus(self):
        self.assertTrue('class="dash-page-header' in self.html, 'class="dash-page-header')
        self.assertTrue('class="dash-page-h1"' in self.html, 'class="dash-page-h1"')
        self.assertTrue("tone === 'danger' ? cancelBtn : okBtn" in self.html, "tone === 'danger' ? cancelBtn : okBtn")


if __name__ == '__main__':
    unittest.main()
