import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import patch

try:
    import app as app_module
except ModuleNotFoundError as import_error:  # pragma: no cover
    app_module = None
    APP_IMPORT_ERROR = import_error
else:
    APP_IMPORT_ERROR = None


@unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
class TsrSyncReliabilityTests(unittest.TestCase):
    def test_submission_token_normalization(self):
        self.assertEqual(
            app_module.normalize_online_tsr_submission_token('tsr-1234_5678-safe'),
            'tsr-1234_5678-safe',
        )
        self.assertEqual(app_module.normalize_online_tsr_submission_token('short'), '')
        self.assertNotIn(
            '/',
            app_module.normalize_online_tsr_submission_token('tsr-1234/5678/unsafe'),
        )

    def test_completed_retry_returns_existing_submission(self):
        submission = SimpleNamespace(
            id=41,
            shift_id=17,
            tsr_number='20260714-01-JD',
            submission_token='tsr-existing-token-123',
            revision_no=1,
            parent_submission_id=None,
        )
        attached_file = SimpleNamespace(id=90, filename='stored.pdf')
        payload = {
            '_attached_file_id': 90,
            '_attached_display_filename': 'TSR_existing.pdf',
            '_completed_shift_ids': [17],
            '_completion_scope': 'current_day',
            '_pdf_source': 'frontend_blob',
        }
        with patch.object(app_module, 'parse_online_tsr_payload_json', return_value=payload), \
             patch.object(app_module.db.session, 'get', return_value=attached_file), \
             patch.object(app_module, 'get_shift_file_display_name', return_value='TSR_existing.pdf'):
            result = app_module.completed_online_tsr_response(submission, duplicate=True)

        self.assertTrue(result['success'])
        self.assertTrue(result['duplicate'])
        self.assertEqual(result['submission_id'], 41)
        self.assertEqual(result['attached_file_id'], 90)
        self.assertEqual(result['completed_shift_ids'], [17])

    def test_core_save_rolls_back_instead_of_committing_pdf_error(self):
        source = inspect.getsource(app_module.save_offline_tsr_online)
        self.assertIn('db.session.rollback()', source)
        self.assertNotIn("submission.status = 'pdf_error'", source)
        self.assertIn('submission_token=submission_token', source)

    def test_supporting_attachment_limits_are_explicit(self):
        self.assertEqual(app_module.TSR_SUPPORTING_ATTACHMENT_MAX_COUNT, 10)
        self.assertEqual(app_module.TSR_SUPPORTING_ATTACHMENT_MAX_BYTES, 35 * 1024 * 1024)


if __name__ == '__main__':
    unittest.main()
