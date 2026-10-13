"""Reimbursement Batch 1: upload date-range checks and status list refresh after Save and Submit."""

import io
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "templates" / "reimbursement.html").read_text(encoding="utf-8")
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_reimbursement_batch1_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402


def _png_bytes():
    from PIL import Image
    buffer = io.BytesIO()
    Image.new('RGB', (4, 4), (255, 255, 255)).save(buffer, format='PNG')
    return buffer.getvalue()


class ReimbursementUploadRangeTests(unittest.TestCase):
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
            user = app_module.User(username='batch1_uploader', password='test-only', role='engineer', is_active=True)
            app_module.db.session.add(user)
            app_module.db.session.flush()
            app_module.db.session.add(app_module.Engineer(
                user_id=user.id, employee_id='BATCH1-001', name='Batch One Uploader', initials='BOU',
            ))
            app_module.db.session.commit()
            cls.user_id = user.id

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

    def _header_count(self):
        with self.app.app_context():
            return app_module.ReimbursementHeader.query.count()

    def _upload(self, start, end):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.user_id)
            session['_fresh'] = True
        with patch.object(app_module, 'reimbursement_receipt_upload_root', return_value=self.upload_dir), \
                patch.object(app_module, 'managed_storage_write_bytes', return_value=None):
            return client.post('/upload_reimbursement_receipt', data={
                'start': start,
                'end': end,
                'additional_receipt': '1',
                'receipt_file': (io.BytesIO(_png_bytes()), 'receipt.png'),
            }, content_type='multipart/form-data')

    def test_reversed_range_is_rejected_without_creating_a_draft(self):
        before = self._header_count()
        response = self._upload('2026-12-31', '2026-01-01')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error'], 'End date must be after start date')
        self.assertEqual(self._header_count(), before)

    def test_64_day_range_is_rejected_without_creating_a_draft(self):
        before = self._header_count()
        response = self._upload('2026-01-01', '2026-03-05')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error'], 'Date range is limited to 63 days for performance')
        self.assertEqual(self._header_count(), before)

    def test_valid_one_day_range_uploads(self):
        response = self._upload('2026-05-04', '2026-05-04')
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))


class ReimbursementStatusRefreshSourceTests(unittest.TestCase):
    def test_manual_save_refreshes_status_list(self):
        start = TEMPLATE.index("if (entry.payload.save_source === 'manual')")
        block = TEMPLATE[start:TEMPLATE.index('} else {', start)]
        self.assertIn("reimToast('Draft saved.'", block)
        self.assertIn('loadMyReimbursementStatuses();', block)

    def test_submit_success_refreshes_status_list(self):
        start = TEMPLATE.index('async function submitReimbursement')
        block = TEMPLATE[start:TEMPLATE.index("console.error('[Reimbursement] Submit failed'", start)]
        notice = block.index("is now in the manager's approval queue")
        self.assertIn('loadMyReimbursementStatuses();', block[notice:])

    def test_kept_functions(self):
        for name in ('saveReimbursementDraft', 'submitReimbursement', 'loadMyReimbursementStatuses',
                     'renderReimbursementOverlapNotice'):
            self.assertIn(f'function {name}(', TEMPLATE)
        self.assertIn("def upload_reimbursement_receipt():", (ROOT / 'app.py').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
