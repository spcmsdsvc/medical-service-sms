import pathlib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import app as app_module


ROOT = pathlib.Path(__file__).resolve().parents[1]


class TsrEmailPreviewCCTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.timeline_source = (ROOT / 'templates' / 'timeline.html').read_text(encoding='utf-8')
        cls.changelog_source = (ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8')

    def test_remembered_cc_accumulates_valid_unique_addresses(self):
        user = SimpleNamespace(
            is_authenticated=True,
            tsr_client_remembered_cc_json='["first@example.com"]',
        )
        remembered = app_module.remember_tsr_client_cc_emails(
            ['FIRST@example.com', 'second@example.com', 'not-an-email'],
            user=user,
        )
        self.assertEqual(remembered, ['first@example.com', 'second@example.com'])
        self.assertIn('second@example.com', user.tsr_client_remembered_cc_json)

    def test_shared_message_builder_deduplicates_cc_sources(self):
        shift = SimpleNamespace(id=17, title='Technical Checkup')
        payload = {
            'emails': ['client@example.com'],
            'manual_cc': [
                'extra@example.com',
                'system@example.com',
                'sender@example.com',
                'client@example.com',
            ],
            'attachment_manifest_signature': 'manifest-1',
        }
        fake_user = SimpleNamespace(is_authenticated=True, username='engineer')
        patches = (
            patch.object(app_module, 'current_user', fake_user),
            patch.object(app_module, 'get_tsr_files_for_shift', return_value=[{'id': 1}]),
            patch.object(app_module, 'get_tsr_email_files_for_shift', return_value=[{'id': 1}]),
            patch.object(app_module, 'get_tsr_email_attachment_manifest_signature', return_value='manifest-1'),
            patch.object(app_module, 'get_tsr_subject_package_metadata', return_value={'mixed': False, 'scenarios': ['standard']}),
            patch.object(app_module, 'build_tsr_client_email_subject', return_value='Prepared subject'),
            patch.object(app_module, 'build_tsr_client_email_bodies', return_value=('Prepared text', '<p>Prepared HTML</p>')),
            patch.object(app_module, 'append_tsr_email_correction_notice', side_effect=lambda shift, text, html: (text, html)),
            patch.object(app_module, 'get_tsr_client_system_cc_emails', return_value=['system@example.com', 'client@example.com']),
            patch.object(app_module, 'get_current_user_email_for_tsr_cc', return_value='sender@example.com'),
            patch.object(app_module, 'serialize_tsr_email_attachment', return_value={'id': 1, 'display_name': 'TSR.pdf'}),
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9], patches[10]:
            message, error, status = app_module.prepare_tsr_client_email_message(shift, payload)

        self.assertIsNone(error)
        self.assertEqual(status, 200)
        self.assertEqual(message['manual_cc'], ['extra@example.com'])
        self.assertEqual(
            message['final_cc'],
            ['system@example.com', 'sender@example.com', 'extra@example.com'],
        )

    def test_preview_ui_and_endpoints_are_present(self):
        self.assertIn('/preview_tsr_client_email_message/<int:shift_id>', self.app_source)
        self.assertIn('/api/preferences/tsr-client-remembered-cc/clear', self.app_source)
        self.assertIn('manual_cc: manualCC', self.timeline_source)
        self.assertIn('Complete Email Preview', self.timeline_source)
        self.assertIn('tsr-email-preview-frame', self.timeline_source)
        self.assertIn('tsr-manual-cc-chips', self.timeline_source)
        self.assertIn('v35-tsr-email-preview-cc', self.app_source)
        self.assertIn('2026-07-22-tsr-email-preview-cc', self.changelog_source)


if __name__ == '__main__':
    unittest.main()
