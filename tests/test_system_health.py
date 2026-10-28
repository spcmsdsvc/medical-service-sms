"""Monitoring (plans.md "Monitoring"): Sentry data rules, /healthz and the health checker.

The canary tests plant fake client, product, email and access-key values everywhere a
leak could come from and assert none of them appears in the exact bytes Sentry would send.
"""

import os
import pathlib
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f'medical_service_health_{uuid.uuid4().hex}.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(TEST_DB_PATH))

import sentry_sdk  # noqa: E402
from sentry_sdk.transport import Transport  # noqa: E402

import app as app_module  # noqa: E402

CANARIES = ('CANARY-CLIENT-ZX81', 'CANARY-SN-4417', 'canary@example.invalid', 'AKIACANARY000')
CANARY_TEXT = ' '.join(CANARIES)
ALLOWED_EVENT_KEYS = {
    'platform', 'event_id', 'release', 'environment', 'timestamp', 'level',
    'transaction', 'exception', 'message', 'fingerprint',
}
NOW = datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)  # Manila wall-clock, as get_manila_time returns


def setUpModule():
    with app_module.app.app_context():
        app_module.db.create_all()


class RecordingTransport(Transport):
    """Keeps every envelope Sentry would send, serialized exactly as it would go out."""
    envelopes = []

    def __init__(self, options=None):
        super().__init__(options)

    def capture_envelope(self, envelope):
        RecordingTransport.envelopes.append(envelope)

    @classmethod
    def sent_bytes(cls):
        return b''.join(envelope.serialize() for envelope in cls.envelopes)

    @classmethod
    def events(cls):
        return [item.payload.json for envelope in cls.envelopes for item in envelope.items
                if item.type == 'event']


class FakeBucket:
    writes_bucket = True
    bucket_configured = True

    def __init__(self, fail=None):
        self.fail = fail
        self.objects = {}

    def upload_bytes(self, key, data, content_type=''):
        if self.fail:
            raise self.fail
        self.objects[key] = data

    def download_bytes(self, key):
        return self.objects[key]

    def delete(self, key):
        self.objects.pop(key, None)


class SentryDataRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_active_at_import = sentry_sdk.get_client().is_active()
        sentry_sdk.init(dsn='https://public@o0.ingest.sentry.io/1', transport=RecordingTransport,
                        **app_module.sentry_init_options())

    @classmethod
    def tearDownClass(cls):
        sentry_sdk.get_client().close()
        sentry_sdk.init()

    def setUp(self):
        RecordingTransport.envelopes.clear()
        app_module._system_health_failing.clear()
        self.client = app_module.app.test_client()

    def assert_no_canary(self):
        sent = RecordingTransport.sent_bytes()
        self.assertTrue(sent, 'nothing was sent, so the test proves nothing')
        for canary in CANARIES:
            self.assertNotIn(canary.encode(), sent)

    def crash_healthz_with_canaries(self):
        def crashing_view():
            secret_client = CANARY_TEXT  # noqa: F841 - a local variable that must not be sent
            raise ValueError(f'client {CANARY_TEXT} not found')

        sentry_sdk.set_user({'email': 'canary@example.invalid', 'username': 'CANARY-CLIENT-ZX81'})
        sentry_sdk.set_tag('client', 'CANARY-CLIENT-ZX81')
        sentry_sdk.set_extra('serial', 'CANARY-SN-4417')
        sentry_sdk.set_context('product', {'serial': 'CANARY-SN-4417'})
        sentry_sdk.add_breadcrumb(message=CANARY_TEXT)
        self.client.set_cookie('client', 'CANARY-CLIENT-ZX81')
        original = app_module.app.view_functions['healthz']
        app_module.app.view_functions['healthz'] = crashing_view
        try:
            self.client.get('/healthz?client=CANARY-CLIENT-ZX81', data={'serial': 'CANARY-SN-4417'},
                            headers={'X-Key': 'AKIACANARY000', 'Referer': 'https://x.test/canary@example.invalid'})
        except ValueError:
            pass
        finally:
            app_module.app.view_functions['healthz'] = original
            sentry_sdk.get_isolation_scope().clear()

    def test_sentry_is_off_without_dsn_or_with_test_db(self):
        self.assertFalse(self.client_active_at_import)

    def test_crash_sends_no_client_product_or_personal_data(self):
        self.crash_healthz_with_canaries()
        self.assert_no_canary()
        event = RecordingTransport.events()[0]
        self.assertEqual(event['exception']['values'][0]['type'], 'ValueError')
        self.assertEqual(event['transaction'], '/healthz')

    def test_events_only_carry_allowlisted_keys(self):
        self.crash_healthz_with_canaries()
        events = RecordingTransport.events()
        self.assertTrue(events)
        for event in events:
            self.assertLessEqual(set(event), ALLOWED_EVENT_KEYS)
            for value in event['exception']['values']:
                self.assertLessEqual(set(value), {'type', 'module', 'stacktrace'})
                for frame in value['stacktrace']['frames']:
                    self.assertLessEqual(set(frame), {'filename', 'function', 'module', 'lineno', 'in_app'})

    def test_filter_failure_drops_the_event(self):
        with patch.object(app_module, '_sentry_rebuild_event', side_effect=RuntimeError('boom')):
            self.assertIsNone(app_module.sentry_allowlist_event({'message': 'Bucket probe failed'}, {}))
            sentry_sdk.capture_exception(ValueError('x'))
        self.assertEqual(RecordingTransport.envelopes, [])

    def test_unlisted_message_is_dropped(self):
        sentry_sdk.capture_message(f'free text {CANARY_TEXT}')
        self.assertEqual(RecordingTransport.events(), [])

    def test_health_alert_sends_only_fixed_text(self):
        bucket = FakeBucket(fail=RuntimeError('SignatureDoesNotMatch AWSAccessKeyId AKIACANARY000'))
        with patch.object(app_module, 'file_storage', bucket), \
                patch.object(app_module, 'SYSTEM_HEALTH_CHECKS', (('bucket', app_module.system_health_bucket_ok),)):
            self.assertEqual(app_module.run_system_health_checks(), {'bucket': False})
        self.assert_no_canary()
        event = RecordingTransport.events()[0]
        self.assertEqual(event['message'], 'Bucket probe failed')
        self.assertEqual(event['level'], 'warning')
        self.assertEqual(event['fingerprint'], ['system-health', 'bucket'])

    def test_bucket_connection_error_sends_only_fixed_text(self):
        with patch.object(app_module, 'record_storage_activity'), \
                patch.object(app_module, 'bucket_connection_error_logged_at', 0):
            app_module.record_bucket_connection_error_throttled(f'denied for {CANARY_TEXT}')
        self.assert_no_canary()
        self.assertEqual(RecordingTransport.events()[0]['message'], 'Bucket connection error')


class HealthzTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def test_ok_without_login(self):
        response = self.client.get('/healthz')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), 'ok')

    def test_fail_when_database_unreachable(self):
        with patch.object(app_module, 'healthz_database_ok', return_value=False):
            response = self.client.get('/healthz')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_data(as_text=True), 'fail')


class HealthCheckTests(unittest.TestCase):
    def setUp(self):
        app_module._system_health_failing.clear()

    def run_checks(self, **results):
        checks = tuple((name, (lambda value=value: value)) for name, value in results.items())
        with patch.object(app_module, 'SYSTEM_HEALTH_CHECKS', checks), \
                patch.object(app_module, 'send_health_alert') as alert:
            app_module.run_system_health_checks()
        return alert

    def test_alerts_once_per_failure_and_once_on_recovery(self):
        self.assertEqual(self.run_checks(disk=False).call_args_list, [unittest.mock.call('disk')])
        self.assertEqual(self.run_checks(disk=False).call_count, 0)
        self.assertEqual(self.run_checks(disk=True).call_args_list,
                         [unittest.mock.call('disk', recovered=True)])
        self.assertEqual(self.run_checks(disk=True).call_count, 0)

    def test_crashing_check_fails_without_stopping_the_others(self):
        def crash():
            raise RuntimeError('boom')
        with patch.object(app_module, 'SYSTEM_HEALTH_CHECKS', (('bucket', crash), ('disk', lambda: True))), \
                patch.object(app_module, 'send_health_alert') as alert:
            self.assertEqual(app_module.run_system_health_checks(), {'bucket': False, 'disk': True})
        alert.assert_called_once_with('bucket')

    def test_bucket_probe_writes_reads_and_deletes(self):
        bucket = FakeBucket()
        with patch.object(app_module, 'file_storage', bucket):
            self.assertTrue(app_module.system_health_bucket_ok())
        self.assertEqual(bucket.objects, {})

    def test_bucket_probe_skipped_without_bucket(self):
        bucket = FakeBucket(fail=RuntimeError('should not be called'))
        bucket.bucket_configured = False
        with patch.object(app_module, 'file_storage', bucket):
            self.assertTrue(app_module.system_health_bucket_ok())

    def test_email_check_uses_brevo_quota(self):
        with patch.object(app_module, 'brevo_daily_quota_exhausted', return_value=True):
            self.assertFalse(app_module.system_health_email_ok())
        with patch.object(app_module, 'brevo_daily_quota_exhausted', return_value=False):
            self.assertTrue(app_module.system_health_email_ok())

    def backup_ok(self, state):
        with patch.object(app_module, 'daily_backup_storage_ready', return_value=True), \
                patch.object(app_module, 'load_daily_backup_state', return_value=state):
            return app_module.system_health_backup_ok(now=NOW)

    def test_backup_check(self):
        recent = (NOW - timedelta(hours=7)).isoformat()
        old = (NOW - timedelta(hours=27)).isoformat()
        self.assertTrue(self.backup_ok({'last_ok': True, 'last_error': '', 'last_run_at': recent}))
        self.assertFalse(self.backup_ok({'last_ok': True, 'last_error': '', 'last_run_at': old}))
        self.assertFalse(self.backup_ok({'last_ok': False, 'last_error': 'x', 'last_run_at': recent}))
        self.assertFalse(self.backup_ok({}))

    def test_disk_check(self):
        for percent, expected in ((89, True), (90, False), (None, True)):
            with patch.object(app_module, 'volume_disk_usage_percent', return_value=percent):
                self.assertEqual(app_module.system_health_disk_ok(), expected)

    def test_alert_is_a_no_op_when_sentry_is_off(self):
        app_module.send_health_alert('disk')  # must not raise


if __name__ == '__main__':
    unittest.main()
