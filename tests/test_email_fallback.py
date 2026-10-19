import base64
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import app as app_module

MAILJET_URL = 'https://api.mailjet.test/v3.1/send'
BREVO_URL = 'https://api.brevo.test/v3/smtp/email'


def fake_response(status_code, json_body=None):
    response = MagicMock()
    response.status_code = status_code
    response.text = str(json_body)
    response.json.return_value = json_body or {}
    return response


MAILJET_OK = fake_response(200, {'Messages': [{'Status': 'success'}]})


def brevo_quota(credits):
    return fake_response(200, {'plan': [{'type': 'free', 'credits': credits, 'creditsType': 'sendLimit'}]})


class EmailFallbackTests(unittest.TestCase):
    def setUp(self):
        config = {
            'EMAIL_PROVIDER': 'brevo',
            'EMAIL_NOTIFICATIONS_ENABLED': True,
            'BREVO_API_KEY': 'brevo-test',
            'BREVO_API_URL': BREVO_URL,
            'MAILJET_API_KEY': 'mj-key-test',
            'MAILJET_SECRET_KEY': 'mj-secret-test',
            'MAILJET_API_URL': MAILJET_URL,
        }
        patcher = patch.dict(app_module.app.config, config)
        patcher.start()
        self.addCleanup(patcher.stop)
        # Brevo has credits unless a test says otherwise.
        app_module._brevo_quota_exhausted_until = 0.0
        get_patcher = patch.object(app_module.requests, 'get', return_value=brevo_quota(120))
        self.quota_get = get_patcher.start()
        self.addCleanup(get_patcher.stop)

    def send(self, responses):
        with patch.object(app_module.requests, 'post', side_effect=responses) as post:
            result = app_module.send_email_notification(['a@example.com'], 'Subject', 'Text', '<p>Html</p>')
        return result, post

    def test_brevo_success_does_not_call_mailjet(self):
        (ok, _), post = self.send([fake_response(201)])
        self.assertTrue(ok)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.args[0], BREVO_URL)

    def test_brevo_quota_failure_sends_through_mailjet(self):
        (ok, message), post = self.send([fake_response(429, {'message': 'limit'}), MAILJET_OK])
        self.assertTrue(ok)
        self.assertIn('Mailjet', message)
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args.args[0], MAILJET_URL)
        self.assertEqual(post.call_args.kwargs['auth'], ('mj-key-test', 'mj-secret-test'))
        sent = post.call_args.kwargs['json']['Messages'][0]
        self.assertEqual(sent['To'], [{'Email': 'a@example.com'}])
        self.assertEqual(sent['Subject'], 'Subject')
        self.assertEqual(sent['TextPart'], 'Text')
        self.assertEqual(sent['HTMLPart'], '<p>Html</p>')

    def test_brevo_exception_sends_through_mailjet(self):
        (ok, _), post = self.send([ConnectionError('down'), MAILJET_OK])
        self.assertTrue(ok)
        self.assertEqual(post.call_args.args[0], MAILJET_URL)

    def test_attachments_and_cc_reach_mailjet(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, 'tsr.pdf')
            with open(path, 'wb') as output:
                output.write(b'%PDF-test')
            with patch.object(app_module.requests, 'post', side_effect=[fake_response(429), MAILJET_OK]) as post:
                ok, _ = app_module.send_email_with_attachments(
                    ['a@example.com'], 'Subject', 'Text',
                    attachments=[{'display_name': 'TSR.pdf', 'path': path}],
                    cc_emails=['c@example.com'],
                )
        self.assertTrue(ok)
        sent = post.call_args.kwargs['json']['Messages'][0]
        self.assertEqual(sent['Cc'], [{'Email': 'c@example.com'}])
        self.assertEqual(sent['Attachments'], [{
            'ContentType': 'application/pdf',
            'Filename': 'TSR.pdf',
            'Base64Content': base64.b64encode(b'%PDF-test').decode('ascii'),
        }])

    def test_without_mailjet_keys_returns_brevo_failure(self):
        app_module.app.config['MAILJET_API_KEY'] = None
        (ok, message), post = self.send([fake_response(429)])
        self.assertFalse(ok)
        self.assertTrue(message.startswith('Brevo failed: 429'))
        self.assertEqual(post.call_count, 1)

    def test_notifications_disabled_sends_nothing(self):
        app_module.app.config['EMAIL_NOTIFICATIONS_ENABLED'] = False
        (ok, _), post = self.send([])
        self.assertFalse(ok)
        post.assert_not_called()

    def test_brevo_with_credits_left_is_used(self):
        (ok, _), post = self.send([fake_response(201)])
        self.assertTrue(ok)
        self.assertEqual(self.quota_get.call_count, 1)
        self.assertEqual(post.call_args.args[0], BREVO_URL)

    def test_brevo_out_of_credits_goes_straight_to_mailjet(self):
        self.quota_get.return_value = brevo_quota(0)
        (ok, message), post = self.send([MAILJET_OK])
        self.assertTrue(ok)
        self.assertIn('Mailjet', message)
        self.assertEqual([call.args[0] for call in post.call_args_list], [MAILJET_URL])

        # A second email inside the recheck window does not ask Brevo again.
        (ok, _), post = self.send([MAILJET_OK])
        self.assertTrue(ok)
        self.assertEqual(self.quota_get.call_count, 1)
        self.assertEqual([call.args[0] for call in post.call_args_list], [MAILJET_URL])

    def test_quota_is_checked_again_after_the_window(self):
        self.quota_get.return_value = brevo_quota(0)
        self.send([MAILJET_OK])
        app_module._brevo_quota_exhausted_until = 0.0  # window expired
        self.quota_get.return_value = brevo_quota(300)
        (ok, _), post = self.send([fake_response(201)])
        self.assertTrue(ok)
        self.assertEqual(self.quota_get.call_count, 2)
        self.assertEqual(post.call_args.args[0], BREVO_URL)

    def test_failed_quota_check_falls_back_to_brevo(self):
        self.quota_get.return_value = fake_response(500)
        (ok, _), post = self.send([fake_response(201)])
        self.assertTrue(ok)
        self.assertEqual(post.call_args.args[0], BREVO_URL)

        self.quota_get.side_effect = ConnectionError('down')
        (ok, _), post = self.send([fake_response(429), MAILJET_OK])
        self.assertTrue(ok)
        self.assertEqual([call.args[0] for call in post.call_args_list], [BREVO_URL, MAILJET_URL])

    def test_without_mailjet_keys_quota_is_not_checked(self):
        app_module.app.config['MAILJET_SECRET_KEY'] = None
        self.send([fake_response(201)])
        self.quota_get.assert_not_called()

    def test_mailjet_error_status_is_a_failure(self):
        mailjet_error = fake_response(200, {'Messages': [{'Status': 'error'}]})
        (ok, message), _ = self.send([fake_response(429), mailjet_error])
        self.assertFalse(ok)
        self.assertIn('Mailjet failed', message)


if __name__ == '__main__':
    unittest.main()
