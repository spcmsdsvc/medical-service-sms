"""Regression coverage for the reversible LPR feature switch.

The tests deliberately stay at Flask/source level.  They exercise the two
dangerous placement decisions in the plan: replay before the drain guard and
the positive reimbursement cleanup branch.  Parent approvals also run with
LPR disabled so linked rows and their PDFs prove they remain available.
"""

import io
import os
import pathlib
import re
import tempfile
import unittest
from contextlib import ExitStack
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine


ROOT = pathlib.Path(__file__).resolve().parents[1]
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_lpr_feature_switch_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

try:
    import app as app_module
except Exception as exc:  # pragma: no cover - allows source-only test runs
    app_module = None
    APP_IMPORT_ERROR = exc
else:
    APP_IMPORT_ERROR = None


class LPRFeatureSwitchSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.reimbursement_source = (ROOT / 'templates' / 'reimbursement.html').read_text(encoding='utf-8')
        cls.settings_source = (ROOT / 'templates' / 'settings.html').read_text(encoding='utf-8')

    def test_flags_default_on_and_embedded_rendering_follows_master_flag(self):
        self.assertIn("app.config['LPR_ENABLED'] = env_flag_enabled('LPR_ENABLED', default=True)", self.app_source)
        self.assertIn("app.config['LPR_ACCEPTING_NEW'] = env_flag_enabled('LPR_ACCEPTING_NEW', default=True)", self.app_source)
        self.assertIn('return lpr_enabled() and bool(app.config.get(\'LPR_ACCEPTING_NEW\', True))', self.app_source)
        self.assertIn('def require_lpr_enabled(', self.app_source)
        self.assertIn('def require_lpr_accepting_new(', self.app_source)
        self.assertIn('def lpr_unavailable_page():', self.app_source)
        self.assertIn("'lpr_accepting_new': lpr_accepting_new()", self.app_source)

    def test_the_two_silent_failure_guards_are_in_the_safe_order(self):
        save_start = self.app_source.index('def save_lpr():')
        save_end = self.app_source.index("@app.route('/submit_lpr", save_start)
        save_source = self.app_source[save_start:save_end]
        replay = save_source.index('LPRHeader.query.filter_by(creation_token=creation_token)')
        drain_guard = save_source.index('if not lpr_accepting_new():')
        self.assertLess(replay, drain_guard, 'drain guard moved above idempotent replay lookup')

        submit_start = self.app_source.index('def submit_reimbursement():')
        submit_end = self.app_source.index("@app.route('/download_reimbursement_form", submit_start)
        submit_source = self.app_source[submit_start:submit_end]
        self.assertIn('if office_field_sources and (lpr_accepting_new() or linked_lprs):', submit_source)
        self.assertIn('elif not office_field_sources and linked_lprs:', submit_source)
        self.assertNotIn('elif linked_lprs:', submit_source)

        self.assertIn('Existing linked rows remain readable while LPR is off.', self.app_source)
        self.assertIn('package.writestr(f\'{lpr_name}.pdf\'', self.app_source)
        self.assertIn('def ensure_lpr_tables():', self.app_source)

    def test_parent_and_page_templates_keep_the_feature_switch_boundaries(self):
        self.assertIn('{% if lpr_accepting_new %}', self.reimbursement_source)
        self.assertIn('{% if lpr_enabled %}lpr: \'LPR\',{% endif %}', self.settings_source)
        self.assertIn("if (request.args.get('module') or '').strip().lower() == 'lpr'", self.app_source)
        self.assertIn('approval_modules=[', self.app_source)
        self.assertIn('does not consume this list', self.app_source)


@unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
class LPRFeatureSwitchWorkflowTests(unittest.TestCase):
    LPR_ROUTE_RULES = {
        '/lpr',
        '/get_lpr_list',
        '/get_lpr/<int:lpr_id>',
        '/get_parent_lprs/<parent_module>/<int:parent_id>',
        '/prepare_reimbursement_lpr/<int:reimbursement_id>',
        '/save_embedded_lpr',
        '/delete_embedded_lpr/<int:lpr_id>',
        '/save_lpr',
        '/submit_lpr/<int:lpr_id>',
        '/preview_lpr/<int:lpr_id>',
        '/download_lpr/<int:lpr_id>',
        '/get_lpr_approval_items',
        '/get_lpr_approval_detail/<int:lpr_id>',
        '/approve_lpr/<int:lpr_id>',
        '/reject_lpr/<int:lpr_id>',
        '/upload_lpr_attachments/<int:lpr_id>',
        '/preview_lpr_attachment/<int:attachment_id>',
        '/download_lpr_attachment/<int:attachment_id>',
        '/delete_lpr_attachment/<int:attachment_id>',
        '/delete_all_lpr_attachments/<int:lpr_id>',
        '/resend_lpr_procurement_email/<int:lpr_id>',
        '/upload_embedded_lpr_attachments/<int:lpr_id>',
        '/delete_embedded_lpr_attachment/<int:attachment_id>',
        '/delete_all_embedded_lpr_attachments/<int:lpr_id>',
        '/preview_embedded_lpr_attachment/<int:attachment_id>',
        '/download_embedded_lpr_attachment/<int:attachment_id>',
        '/preview_embedded_lpr/<int:lpr_id>',
        '/download_embedded_lpr/<int:lpr_id>',
    }

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, NEW_WORKFLOWS_ENABLED=True)
        cls.original_flags = {
            key: cls.app.config.get(key)
            for key in ('LPR_ENABLED', 'LPR_ACCEPTING_NEW', 'NEW_WORKFLOWS_ENABLED')
        }
        extension = cls.app.extensions['sqlalchemy']
        engines = extension._app_engines[cls.app]
        cls.original_engine = engines[None]
        cls.test_engine = create_engine(f"sqlite:///{_TEST_DB_PATH.as_posix()}")
        engines[None] = cls.test_engine
        cls.original_lpr_ready = app_module._lpr_tables_ready
        cls.original_cash_ready = app_module._cash_advance_tables_ready
        cls.original_travel_ready = app_module._travel_request_tables_ready
        app_module._lpr_tables_ready = False

        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_lpr_tables()
            app_module.ensure_universal_approval_audit_table()
            app_module.ensure_system_notification_table()
            # db.create_all() already created the complete test schema. Mark
            # these additive live-schema helpers ready so approval requests do
            # not attempt DDL while Flask-Login holds the request transaction.
            app_module._cash_advance_tables_ready = True
            app_module._travel_request_tables_ready = True

            cls.requester = app_module.User(
                username='lpr_switch_requester', password='test-only', role='engineer', is_active=True
            )
            cls.approver = app_module.User(
                username='rodito', password='test-only', role='admin', is_active=True
            )
            app_module.db.session.add_all([cls.requester, cls.approver])
            app_module.db.session.flush()
            cls.requester_engineer = app_module.Engineer(
                user_id=cls.requester.id,
                employee_id='LPR-SWITCH-001',
                name='LPR Switch Requester',
                initials='LSR',
                branch='Manila',
                signature_data='requester-signature',
            )
            cls.approver_engineer = app_module.Engineer(
                user_id=cls.approver.id,
                employee_id='LPR-SWITCH-002',
                name='LPR Switch Approver',
                initials='LSA',
                branch='Manila',
                signature_data='approver-signature',
            )
            app_module.db.session.add_all([cls.requester_engineer, cls.approver_engineer])
            app_module.db.session.commit()
            cls.requester_id = cls.requester.id
            cls.approver_id = cls.approver.id
            cls.requester_engineer_id = cls.requester_engineer.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            app_module.db.session.remove()
        cls.app.extensions['sqlalchemy']._app_engines[cls.app][None] = cls.original_engine
        cls.test_engine.dispose()
        app_module._lpr_tables_ready = cls.original_lpr_ready
        app_module._cash_advance_tables_ready = cls.original_cash_ready
        app_module._travel_request_tables_ready = cls.original_travel_ready
        cls.app.config.update(cls.original_flags)
        try:
            _TEST_DB_PATH.unlink()
        except FileNotFoundError:
            pass

    def setUp(self):
        self.app.config.update(LPR_ENABLED=True, LPR_ACCEPTING_NEW=True, NEW_WORKFLOWS_ENABLED=True)

    def _client(self, user_id):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def _lpr_payload(self, token):
        return {
            'creation_token': token,
            'request_date': '2026-08-14',
            'branch_code': 'BC01',
            'class_code': 'CC04',
            'dept_code': 'DC03',
            'product_code': 'PC23',
            'intended_for': 'QA inventory',
            'equipment': 'Field service stock',
            'items': [{
                'description': 'SSD',
                'quantity': 1,
                'unit_measure': 'pc',
                'unit_price': 200,
            }],
        }

    def _make_lpr(self, parent_module, parent_id, total=100):
        kwargs = {
            'user_id': self.requester_id,
            'parent_module': parent_module,
            'request_date': date(2026, 8, 14),
            'lpr_no': f'LPR-20990814-{parent_module[:2].upper()}-{parent_id}',
            'branch_code': 'BC01',
            'class_code': 'CC04',
            'dept_code': 'DC03',
            'product_code': 'PC23',
            'intended_for': 'QA parent request',
            'equipment': 'QA equipment',
            'total_requested': total,
            'status': 'Draft',
        }
        if parent_module == 'travel_request':
            kwargs['travel_request_id'] = parent_id
        elif parent_module == 'cash_advance':
            kwargs['cash_advance_id'] = parent_id
        elif parent_module == 'reimbursement':
            kwargs['reimbursement_id'] = parent_id
        header = app_module.LPRHeader(**kwargs)
        header.items.append(app_module.LPRItem(
            row_index=0,
            description='QA linked item',
            quantity=1,
            unit_measure='lot',
            unit_price=total,
            line_total=total,
        ))
        app_module.db.session.add(header)
        app_module.db.session.flush()
        return header

    def _make_reimbursement(self, office_amount=500, attach_lpr=True, lpr_total=None):
        with self.app.app_context():
            header = app_module.ReimbursementHeader(
                user_id=self.requester_id,
                engineer_id=self.requester_engineer_id,
                start_date=date(2026, 8, 14),
                end_date=date(2026, 8, 14),
                status='Draft',
            )
            app_module.db.session.add(header)
            app_module.db.session.flush()
            row_total = office_amount if office_amount else 100
            row = app_module.ReimbursementRow(
                reimbursement_id=header.id,
                row_date=date(2026, 8, 14),
                remarks='QA reimbursement',
                office_supplies=office_amount,
                others_misc=0 if office_amount else 100,
                row_total=row_total,
            )
            app_module.db.session.add(row)
            app_module.db.session.flush()
            lpr_id = None
            if attach_lpr:
                lpr = self._make_lpr('reimbursement', header.id, lpr_total if lpr_total is not None else row_total)
                lpr.items[0].reimbursement_source_key = f'row:{row.id}'
                lpr.items[0].line_total = lpr_total if lpr_total is not None else row_total
                lpr_id = lpr.id
            app_module.db.session.commit()
            header_ref = SimpleNamespace(
                id=header.id,
                start_date=date(2026, 8, 14),
                end_date=date(2026, 8, 14),
            )
            lpr_ref = SimpleNamespace(id=lpr_id) if lpr_id else None
            return header_ref, lpr_ref

    def _submit_reimbursement(self, header):
        client = self._client(self.requester_id)
        with patch.object(app_module, 'reimbursement_engineer_has_saved_signature', return_value=True), \
                patch.object(app_module, 'get_assigned_approvers_for_requester', return_value=[]), \
                patch.object(app_module, 'clear_existing_pending_approval_notifications', return_value=None), \
                patch.object(app_module, 'create_system_notifications_for_users', return_value=None), \
                patch.object(app_module, 'send_reimbursement_notification_email_async', return_value=None):
            return client.post('/submit_reimbursement', json={
                'id': header.id,
                'start': header.start_date.isoformat(),
                'end': header.end_date.isoformat(),
            })

    def test_lpr_route_census_denies_every_lpr_rule_when_off(self):
        actual = {
            rule.rule for rule in self.app.url_map.iter_rules()
            if 'lpr' in rule.rule.lower() or 'parent_lprs' in rule.rule.lower()
        }
        self.assertEqual(actual, self.LPR_ROUTE_RULES)

        self.app.config['LPR_ENABLED'] = False
        client = self._client(self.requester_id)
        for rule in self.app.url_map.iter_rules():
            if rule.rule not in self.LPR_ROUTE_RULES:
                continue
            path = re.sub(
                r'<(?:[^:>]+:)?([^>]+)>',
                lambda match: 'reimbursement' if 'module' in match.group(1) else '1',
                rule.rule,
            )
            method = 'POST' if 'POST' in rule.methods else 'GET'
            response = client.open(path, method=method, json={} if method == 'POST' else None)
            self.assertEqual(response.status_code, 403, f'{method} {path} was not blocked')

        page = client.get('/lpr')
        self.assertEqual(page.status_code, 403)
        self.assertIn('Local Purchase Requisition unavailable', page.get_data(as_text=True))

    def test_off_entry_points_and_recall_are_explicitly_explained_or_denied(self):
        self.app.config['LPR_ENABLED'] = False
        approver_client = self._client(self.approver_id)
        deep_link = approver_client.get('/approvals?module=lpr&id=1')
        self.assertEqual(deep_link.status_code, 403)
        self.assertIn('Existing requests are retained', deep_link.get_data(as_text=True))

        plain_approvals = approver_client.get('/approvals')
        self.assertEqual(plain_approvals.status_code, 200)

        for response in (
            approver_client.get('/get_approval_center_items?module=lpr'),
            approver_client.get('/get_approval_audit_trail?module=lpr&id=1'),
            approver_client.post('/resend_approved_request_email', json={'module': 'lpr', 'record_id': 1}),
        ):
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.get_json().get('status'), 'disabled')

        recall = self._client(self.requester_id).post(
            '/api/requests/lpr/1/recall', json={'reason': 'Drain mode guard'}
        )
        self.assertEqual(recall.status_code, 403)
        self.assertEqual(recall.get_json().get('status'), 'disabled')

    def test_drain_replays_existing_save_before_refusing_new_creation(self):
        token = 'lpr-drain-replay-token-2026'
        first = self._client(self.requester_id).post('/save_lpr', json=self._lpr_payload(token))
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        lpr_id = first.get_json()['item']['id']

        self.app.config['LPR_ACCEPTING_NEW'] = False
        replay = self._client(self.requester_id).post('/save_lpr', json=self._lpr_payload(token))
        self.assertEqual(replay.status_code, 200, replay.get_data(as_text=True))
        self.assertTrue(replay.get_json()['idempotent_replay'])
        self.assertEqual(replay.get_json()['item']['id'], lpr_id)

        new_request = self._client(self.requester_id).post(
            '/save_lpr', json=self._lpr_payload('lpr-drain-new-token-2026')
        )
        self.assertEqual(new_request.status_code, 403)
        self.assertEqual(new_request.get_json()['status'], 'disabled')

    def test_drain_validates_existing_lpr_but_does_not_delete_it(self):
        header, lpr = self._make_reimbursement(office_amount=500, attach_lpr=True, lpr_total=400)
        self.app.config['LPR_ACCEPTING_NEW'] = False
        response = self._submit_reimbursement(header)
        self.assertEqual(response.status_code, 409, response.get_data(as_text=True))
        self.assertTrue(response.get_json().get('lpr_required'))
        with self.app.app_context():
            self.assertIsNotNone(app_module.db.session.get(app_module.LPRHeader, lpr.id))

    def test_drain_allows_office_field_submit_without_new_lpr_and_positive_cleanup_still_runs(self):
        valid_header, valid_lpr = self._make_reimbursement(office_amount=500, attach_lpr=True, lpr_total=500)
        self.app.config['LPR_ACCEPTING_NEW'] = False
        valid_response = self._submit_reimbursement(valid_header)
        self.assertEqual(valid_response.status_code, 200, valid_response.get_data(as_text=True))
        self.assertEqual(valid_response.get_json()['status'], 'Submitted')
        with self.app.app_context():
            self.assertIsNotNone(app_module.db.session.get(app_module.LPRHeader, valid_lpr.id))

        stale_header, stale_lpr = self._make_reimbursement(office_amount=0, attach_lpr=True, lpr_total=100)
        self.app.config['LPR_ENABLED'] = False
        stale_response = self._submit_reimbursement(stale_header)
        self.assertEqual(stale_response.status_code, 200, stale_response.get_data(as_text=True))
        with self.app.app_context():
            self.assertIsNone(app_module.db.session.get(app_module.LPRHeader, stale_lpr.id))

    def test_travel_and_cash_advance_approval_keep_linked_lpr_pdfs_when_off(self):
        with self.app.app_context():
            travel = app_module.TravelRequest(
                request_no='TR-LPR-SWITCH-01',
                user_id=self.requester_id,
                engineer_id=self.requester_engineer_id,
                purpose='LPR switch travel approval',
                status='Submitted',
                submitted_at=datetime(2026, 8, 14),
            )
            cash = app_module.CashAdvanceHeader(
                cash_advance_no='CA-LPR-SWITCH-01',
                user_id=self.requester_id,
                request_date=date(2026, 8, 14),
                needed_date=date(2026, 8, 15),
                purpose='LPR switch cash approval',
                amount_requested=100,
                status='Submitted',
                submitted_at=datetime(2026, 8, 14),
            )
            app_module.db.session.add_all([travel, cash])
            app_module.db.session.flush()
            travel_lpr = self._make_lpr('travel_request', travel.id, total=100)
            cash_lpr = self._make_lpr('cash_advance', cash.id, total=100)
            app_module.db.session.commit()
            travel_id = travel.id
            cash_id = cash.id
            travel_lpr_no = travel_lpr.lpr_no
            cash_lpr_no = cash_lpr.lpr_no

        self.app.config['LPR_ENABLED'] = False
        approver_client = self._client(self.approver_id)
        with ExitStack() as stack:
            stack.enter_context(patch.object(app_module, 'approval_signature_required_response', return_value=None))
            stack.enter_context(patch.object(app_module, 'record_universal_approval_audit', return_value=None))
            stack.enter_context(patch.object(app_module, 'resolve_pending_approval_notifications', return_value=None))
            stack.enter_context(patch.object(app_module, 'create_system_notifications_for_users', return_value=None))
            stack.enter_context(patch.object(app_module, 'create_system_notification', return_value=None))
            stack.enter_context(patch.object(app_module, 'add_activity_log_entry', return_value=None))
            stack.enter_context(patch.object(app_module, 'can_user_approve_travel_request', return_value=True))
            stack.enter_context(patch.object(app_module, 'create_or_get_travel_blocks_for_approved_request', return_value={
                'success': True, 'created_count': 0, 'skipped_count': 0, 'restored_dates': [],
                'skipped_dates': [], 'converted_overlap_dates': [], 'first_shift_id': None, 'group_id': None,
            }))
            stack.enter_context(patch.object(app_module, 'get_travel_accounting_recipient_emails', return_value=[]))
            stack.enter_context(patch.object(app_module, 'send_travel_request_notification_email_async', return_value=None))
            stack.enter_context(patch.object(app_module, 'send_travel_request_accounting_email_async', return_value=None))
            stack.enter_context(patch.object(app_module, 'can_user_approve_cash_advance', return_value=True))
            stack.enter_context(patch.object(app_module, 'get_cash_advance_handoff_recipient_emails', return_value=([], {
                'group_key': 'cash_advance_accounting', 'group_label': 'Cash Advance Accounting',
                'package_label': 'Cash Advance form handoff', 'attachment_label': 'Cash Advance PDF',
            })))
            stack.enter_context(patch.object(app_module, 'cash_advance_accounting_recipient_debug_counts', return_value={}))
            stack.enter_context(patch.object(app_module, 'cash_advance_add_audit', return_value=None))
            stack.enter_context(patch.object(app_module, 'send_cash_advance_notification_email_async', return_value=None))
            stack.enter_context(patch.object(app_module, 'send_cash_advance_accounting_email_async', return_value=None))

            travel_response = approver_client.post(
                f'/approve_travel_request/{travel_id}', json={'remarks': 'Approved in drain test'}
            )
            cash_response = approver_client.post(
                f'/approve_cash_advance/{cash_id}', json={'remarks': 'Approved in drain test'}
            )

        self.assertEqual(travel_response.status_code, 200, travel_response.get_data(as_text=True))
        self.assertEqual(cash_response.status_code, 200, cash_response.get_data(as_text=True))

        from pypdf import PdfReader

        with self.app.app_context():
            travel = app_module.db.session.get(app_module.TravelRequest, travel_id)
            cash = app_module.db.session.get(app_module.CashAdvanceHeader, cash_id)
            self.assertEqual(travel.status, 'Approved')
            self.assertEqual(cash.status, 'Approved')
            travel_pdf = app_module.build_travel_request_supporting_attachments_pdf_bytes(travel)
            cash_pdf = app_module.build_cash_advance_supporting_attachments_pdf_bytes(cash)
            travel_lpr_count = len(app_module.linked_lpr_records('travel_request', travel.id))
            cash_lpr_count = len(app_module.linked_lpr_records('cash_advance', cash.id))
        self.assertTrue(travel_pdf)
        self.assertTrue(cash_pdf)
        self.assertIn(travel_lpr_no, '\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(travel_pdf)).pages))
        self.assertIn(cash_lpr_no, '\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(cash_pdf)).pages))
        self.assertEqual(travel_lpr_count, 1)
        self.assertEqual(cash_lpr_count, 1)


if __name__ == '__main__':
    unittest.main()
