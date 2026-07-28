import os
import pathlib
import tempfile
import unittest
from datetime import date

from flask_login import login_user, logout_user
from sqlalchemy import create_engine

try:
    import app as app_module
except Exception:
    app_module = None


ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / 'app.py').read_text(encoding='utf-8')
REIMBURSEMENT_TEMPLATE = (
    ROOT / 'templates' / 'reimbursement.html'
).read_text(encoding='utf-8')


class ReimbursementRangeReuseTests(unittest.TestCase):
    def test_frontend_opens_history_by_record_id(self):
        self.assertIn('openReimbursementStatusRecord', REIMBURSEMENT_TEMPLATE)
        self.assertIn('openLegacyReimbursementRange', REIMBURSEMENT_TEMPLATE)
        self.assertIn('reimbursement_id: currentReimbursementId || null', REIMBURSEMENT_TEMPLATE)
        self.assertIn('Historical ${currentReimbursementStatus} record opened by ID.', REIMBURSEMENT_TEMPLATE)
        self.assertIn('const claimedShiftIds = new Set(', REIMBURSEMENT_TEMPLATE)
        self.assertNotIn('openReimbursementStatusRange(', REIMBURSEMENT_TEMPLATE)

    def test_backend_uses_editable_range_discovery_and_exact_claims(self):
        self.assertIn('def reimbursement_find_editable_header', APP_SOURCE)
        self.assertIn('def reimbursement_find_owned_header_by_id', APP_SOURCE)
        self.assertIn('def reimbursement_claim_conflicts_for_rows', APP_SOURCE)
        self.assertIn('def reimbursement_lock_claim_schedules', APP_SOURCE)
        self.assertIn('reimbursement_lock_claim_schedules(claim_rows)', APP_SOURCE)
        claimed_start = APP_SOURCE.index('def reimbursement_claimed_schedule_scope_for_user')
        claimed_end = APP_SOURCE.index('def reimbursement_row_to_dict', claimed_start)
        claimed_block = APP_SOURCE[claimed_start:claimed_end]
        self.assertNotIn('receipt_claim_exists', claimed_block)

    @unittest.skipUnless(app_module is not None, 'Application dependencies are unavailable.')
    def test_locked_range_does_not_replace_editable_record_and_zero_rows_do_not_claim(self):
        file_handle, database_path = tempfile.mkstemp(suffix='.db')
        os.close(file_handle)
        try:
            with app_module.app.app_context():
                extension = app_module.app.extensions['sqlalchemy']
                engines = extension._app_engines[app_module.app]
                original_engine = engines[None]
                test_engine = create_engine(f"sqlite:///{database_path.replace(os.sep, '/')}")
                try:
                    engines[None] = test_engine
                    app_module.db.create_all()

                    user = app_module.User(
                        username='range-reuse-engineer',
                        password='test-only',
                        role='engineer'
                    )
                    app_module.db.session.add(user)
                    app_module.db.session.flush()
                    engineer = app_module.Engineer(
                        user_id=user.id,
                        employee_id='RANGE-REUSE-1',
                        name='Range Reuse Engineer',
                        initials='RR'
                    )
                    app_module.db.session.add(engineer)
                    app_module.db.session.flush()

                    approved = app_module.ReimbursementHeader(
                        user_id=user.id,
                        engineer_id=engineer.id,
                        start_date=date(2026, 7, 1),
                        end_date=date(2026, 7, 31),
                        status='Approved'
                    )
                    draft = app_module.ReimbursementHeader(
                        user_id=user.id,
                        engineer_id=engineer.id,
                        start_date=date(2026, 7, 1),
                        end_date=date(2026, 7, 31),
                        status='Draft'
                    )
                    app_module.db.session.add_all([approved, draft])
                    app_module.db.session.flush()
                    app_module.db.session.add_all([
                        app_module.ReimbursementRow(
                            reimbursement_id=approved.id,
                            shift_id=101,
                            row_date=date(2026, 7, 13),
                            transpo=150,
                            row_total=150
                        ),
                        app_module.ReimbursementRow(
                            reimbursement_id=approved.id,
                            shift_id=102,
                            row_date=date(2026, 7, 14),
                            row_total=0
                        )
                    ])
                    app_module.db.session.commit()

                    with app_module.app.test_request_context('/reimbursement'):
                        login_user(user)
                        editable = app_module.reimbursement_find_editable_header(
                            date(2026, 7, 1),
                            date(2026, 7, 31)
                        )
                        self.assertEqual(editable.id, draft.id)

                        claimed = app_module.reimbursement_claimed_schedule_scope_for_user(
                            engineer,
                            date(2026, 7, 1),
                            date(2026, 7, 31)
                        )
                        self.assertEqual(claimed['shift_ids'], {101})
                        self.assertNotIn(102, claimed['shift_ids'])
                        logout_user()

                finally:
                    app_module.db.session.remove()
                    engines[None] = original_engine
                    test_engine.dispose()
        finally:
            if os.path.exists(database_path):
                os.unlink(database_path)


if __name__ == '__main__':
    unittest.main()
