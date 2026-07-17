import unittest
from types import SimpleNamespace
from unittest.mock import patch

try:
    import app as app_module
except Exception as import_error:  # pragma: no cover - dependency guard
    app_module = None
    APP_IMPORT_ERROR = import_error
else:
    APP_IMPORT_ERROR = None


@unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
class TsrLegacySnapshotSelectionTests(unittest.TestCase):
    def test_complete_replacement_requires_service_content(self):
        complete_text = ' '.join([
            'TECHNICAL SERVICE REPORT',
            'EQUIPMENT/MODEL ACTENO OPESCOPE FD',
            'SERIAL NO MQD6DBDFA006',
            'ACTIONS TAKEN INSTALLED AND TESTED SYSTEM ' * 15,
            'DATE OF SERVICE JULY 1 2026',
            'TIME STARTED 8:00 AM TIME FINISHED 5:00 PM',
        ])
        blank_text = 'TECHNICAL SERVICE REPORT ' + ('EMPTY TEMPLATE ' * 30)

        self.assertTrue(app_module.legacy_tsr_replacement_text_is_complete(complete_text))
        self.assertFalse(app_module.legacy_tsr_replacement_text_is_complete(blank_text))

    def test_policy_suppresses_primary_only_after_replacement_is_verified(self):
        shift = SimpleNamespace(id=1620)
        submission = SimpleNamespace(id=38)
        file_record = SimpleNamespace(
            id=459,
            shift_id=1620,
            filename='complete-tsr.pdf',
            original_filename='complete-tsr.pdf',
        )
        payload = {
            '_attached_file_id': 458,
            '_extra_attachment_file_ids': [459],
        }

        with patch.object(app_module, 'ensure_online_tsr_submission_table'), \
                patch.object(app_module, 'get_latest_online_tsr_submission_for_shift', return_value=submission), \
                patch.object(app_module, 'parse_online_tsr_payload_json', return_value=payload), \
                patch.object(app_module, 'get_online_tsr_missing_core_details', return_value=['Actions Taken']), \
                patch.object(app_module.db.session, 'get', return_value=file_record), \
                patch.object(app_module, 'managed_storage_read_path', return_value='complete-tsr.pdf'), \
                patch.object(app_module, 'extract_text_from_report_file', return_value='verified text'), \
                patch.object(app_module, 'legacy_tsr_replacement_text_is_complete', return_value=True):
            policy = app_module.get_legacy_incomplete_tsr_file_policy(shift)

        self.assertEqual(policy['suppressed_primary_ids'], {458})
        self.assertEqual(policy['replacement_file_ids'], {459})
        self.assertEqual(policy['missing_details'], ['Actions Taken'])

    def test_policy_keeps_primary_when_extra_pdf_is_not_complete(self):
        shift = SimpleNamespace(id=1620)
        submission = SimpleNamespace(id=38)
        file_record = SimpleNamespace(
            id=459,
            shift_id=1620,
            filename='supporting-document.pdf',
            original_filename='supporting-document.pdf',
        )
        payload = {
            '_attached_file_id': 458,
            '_extra_attachment_file_ids': [459],
        }

        with patch.object(app_module, 'ensure_online_tsr_submission_table'), \
                patch.object(app_module, 'get_latest_online_tsr_submission_for_shift', return_value=submission), \
                patch.object(app_module, 'parse_online_tsr_payload_json', return_value=payload), \
                patch.object(app_module, 'get_online_tsr_missing_core_details', return_value=['Actions Taken']), \
                patch.object(app_module.db.session, 'get', return_value=file_record), \
                patch.object(app_module, 'managed_storage_read_path', return_value='supporting-document.pdf'), \
                patch.object(app_module, 'extract_text_from_report_file', return_value='not a completed TSR'), \
                patch.object(app_module, 'legacy_tsr_replacement_text_is_complete', return_value=False):
            policy = app_module.get_legacy_incomplete_tsr_file_policy(shift)

        self.assertEqual(policy['suppressed_primary_ids'], set())
        self.assertEqual(policy['replacement_file_ids'], set())


if __name__ == '__main__':
    unittest.main()
