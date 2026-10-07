"""PC code in reimbursement remarks: required on Submit for client-visit rows."""

import os
import pathlib
import subprocess
import tempfile
import textwrap
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "templates" / "reimbursement.html").read_text(encoding="utf-8")
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_reimbursement_pc_code_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402


def _js_block(start_token, end_token):
    start = TEMPLATE.index(start_token)
    end = TEMPLATE.index(end_token, start)
    return TEMPLATE[start:end]


class ReimbursementPcCodePageTests(unittest.TestCase):
    def test_page_functions_and_markup(self):
        for token in (
            "const REIMBURSEMENT_PC_CODES = [",
            "function getReimbursementPcCode(text)",
            "function applyReimbursementPcCode(text, code)",
            "function reimbursementRowNeedsPcCode(row)",
            "function buildReimbursementPcCodeSelect(row, rowKey)",
            "function handleReimbursementPcCodeChange(select)",
            "function focusMissingReimbursementPcCode()",
            "onchange=\"handleReimbursementPcCodeChange(this)\"",
            "pc_code_missing:",
            # Existing functions the page still relies on.
            "function handleReimbursementRemarksInput(input)",
            "function collectReimbursementRowsForSave()",
            "async function saveReimbursementDraft(silent, options)",
            "async function submitReimbursement()",
        ):
            self.assertIn(token, TEMPLATE)
        self.assertEqual(TEMPLATE.count("${buildReimbursementPcCodeSelect(row, rowKey)}"), 2)
        for code in ('PC18', 'PC19', 'PC20', 'PC21', 'PC22', 'PC23', 'PC24', 'PC26'):
            self.assertIn(f"code: '{code}'", TEMPLATE)

    def test_pc_code_helpers_and_readiness_blocker_runtime(self):
        helpers = _js_block("const REIMBURSEMENT_PC_CODES = [", "\n    function buildReimbursementPcCodeSelect")
        model = _js_block(
            "function buildReimbursementReadinessSnapshot(options)",
            "\n    function reimbursementReadinessActionMarkup",
        )
        script = textwrap.dedent(
            """
            const assert = require('assert');
            function getReimbursementPayloadRowTotal(row) {
                return Object.values(row.amounts || {}).reduce((s, v) => s + Number(v || 0), 0);
            }
            """
        ) + helpers + "\n" + model + textwrap.dedent(
            """
            assert.strictEqual(applyReimbursementPcCode('Angeles Medical Center visit', 'PC18'), 'Angeles Medical Center visit - PC18');
            assert.strictEqual(applyReimbursementPcCode('Angeles visit - PC18', 'PC20'), 'Angeles visit - PC20');
            assert.strictEqual(applyReimbursementPcCode('Angeles visit - PC18', ''), 'Angeles visit');
            assert.strictEqual(applyReimbursementPcCode('', 'PC26'), 'PC26');
            assert.strictEqual(applyReimbursementPcCode('  ', 'PC26'), 'PC26');
            assert.strictEqual(getReimbursementPcCode('visit - pc21'), 'PC21');
            assert.strictEqual(getReimbursementPcCode('visit PC25 PC250'), '');
            assert.strictEqual(getReimbursementPcCode(''), '');
            assert.strictEqual(reimbursementRowNeedsPcCode({ client: 'DDH' }), true);
            assert.strictEqual(reimbursementRowNeedsPcCode({ client: '' }), false);
            assert.strictEqual(reimbursementRowNeedsPcCode({ client: 'DDH', manual: true }), false);

            const base = { editable: true, saveState: 'saved', unsaved: false, signature: 'ready', officeFieldTotal: 0, lpr: 'not-required' };
            const missing = buildReimbursementReadinessSnapshot(Object.assign({ rows: [
                { amounts: { transpo: 100 }, pc_code_missing: true },
                { amounts: { transpo: 0 }, pc_code_missing: true }
            ] }, base));
            const pc = missing.blockers.find(item => item.id === 'pc-code');
            assert.ok(pc, 'pc-code blocker expected');
            assert.ok(pc.detail.startsWith('1 client-visit row needs'));
            assert.strictEqual(pc.action, 'focusMissingReimbursementPcCode');
            assert.strictEqual(missing.ready, false);

            const filled = buildReimbursementReadinessSnapshot(Object.assign({ rows: [
                { amounts: { transpo: 100 }, pc_code_missing: false }
            ] }, base));
            assert.ok(!filled.blockers.some(item => item.id === 'pc-code'));
            assert.strictEqual(filled.ready, true);
            """
        )
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


class ReimbursementPcCodeSubmitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.original_flags = {key: cls.app.config.get(key) for key in ('LPR_ENABLED', 'LPR_ACCEPTING_NEW')}
        cls.app.config.update(LPR_ENABLED=False, LPR_ACCEPTING_NEW=False)
        engines = cls.app.extensions['sqlalchemy']._app_engines[cls.app]
        cls.original_engine = engines[None]
        cls.test_engine = create_engine(f"sqlite:///{_TEST_DB_PATH.as_posix()}")
        engines[None] = cls.test_engine
        with cls.app.app_context():
            app_module.db.create_all()
            user = app_module.User(username='pc_code_requester', password='test-only', role='engineer', is_active=True)
            app_module.db.session.add(user)
            app_module.db.session.flush()
            engineer = app_module.Engineer(
                user_id=user.id, employee_id='PC-CODE-001', name='PC Code Requester',
                initials='PCR', branch='Manila', signature_data='requester-signature',
            )
            app_module.db.session.add(engineer)
            app_module.db.session.commit()
            cls.user_id = user.id
            cls.engineer_id = engineer.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            app_module.db.session.remove()
        cls.app.extensions['sqlalchemy']._app_engines[cls.app][None] = cls.original_engine
        cls.test_engine.dispose()
        cls.app.config.update(cls.original_flags)
        try:
            _TEST_DB_PATH.unlink()
        except FileNotFoundError:
            pass

    _next_day = 1

    def _make(self, rows):
        """rows: list of (shift_id, client_name, remarks, amount)."""
        day = date(2026, 9, ReimbursementPcCodeSubmitTests._next_day)
        ReimbursementPcCodeSubmitTests._next_day += 1
        with self.app.app_context():
            header = app_module.ReimbursementHeader(
                user_id=self.user_id, engineer_id=self.engineer_id,
                start_date=day, end_date=day, status='Draft',
            )
            app_module.db.session.add(header)
            app_module.db.session.flush()
            for shift_id, client_name, remarks, amount in rows:
                app_module.db.session.add(app_module.ReimbursementRow(
                    reimbursement_id=header.id, shift_id=shift_id, row_date=day,
                    client_name=client_name, remarks=remarks, transpo=amount, row_total=amount,
                ))
            app_module.db.session.commit()
            return SimpleNamespace(id=header.id, day=day)

    def _submit(self, header):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.user_id)
            session['_fresh'] = True
        with patch.object(app_module, 'reimbursement_engineer_has_saved_signature', return_value=True), \
                patch.object(app_module, 'get_assigned_approvers_for_requester', return_value=[]), \
                patch.object(app_module, 'clear_existing_pending_approval_notifications', return_value=None), \
                patch.object(app_module, 'create_system_notifications_for_users', return_value=None), \
                patch.object(app_module, 'send_reimbursement_notification_email_async', return_value=None):
            return client.post('/submit_reimbursement', json={
                'id': header.id, 'start': header.day.isoformat(), 'end': header.day.isoformat(),
            })

    def _status(self, header):
        with self.app.app_context():
            return app_module.db.session.get(app_module.ReimbursementHeader, header.id).status

    def test_client_visit_row_without_code_is_refused(self):
        header = self._make([(900001, 'Angeles Medical Center', 'Angeles visit', 150)])
        response = self._submit(header)
        self.assertEqual(response.status_code, 400, response.get_data(as_text=True))
        self.assertTrue(response.get_json().get('pc_code_required'))
        self.assertEqual(self._status(header), 'Draft')

    def test_client_visit_row_with_code_is_accepted(self):
        header = self._make([(900002, 'Angeles Medical Center', 'Angeles visit - PC18', 150)])
        response = self._submit(header)
        self.assertFalse((response.get_json() or {}).get('pc_code_required'), response.get_data(as_text=True))
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(self._status(header), 'Submitted')

    def test_optional_rows_do_not_block(self):
        header = self._make([
            (900003, '', 'In office', 120),                   # schedule without a medical center
            (None, '', 'Manual item', 80),                    # manual row
            (900004, 'Angeles Medical Center', 'No amount', 0),  # zero-amount client row
        ])
        response = self._submit(header)
        self.assertFalse((response.get_json() or {}).get('pc_code_required'), response.get_data(as_text=True))
        self.assertEqual(self._status(header), 'Submitted')


if __name__ == '__main__':
    unittest.main()
