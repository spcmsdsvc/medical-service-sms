import gzip
import os
import pathlib
import shutil
import sqlite3
import tempfile
import threading
import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f'medical_service_daily_{uuid.uuid4().hex}.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(TEST_DB_PATH))

import app as app_module  # noqa: E402


NOW = datetime(2026, 10, 9, 2, 30, tzinfo=timezone.utc)  # Manila wall-clock, as get_manila_time returns


class FakeBucket:
    writes_bucket = True
    bucket_configured = True

    def __init__(self, keys=(), fail_upload=False):
        self.objects = {key: b'old' for key in keys}
        self.fail_upload = fail_upload
        self.deleted = []

    def upload_file(self, key, path, **kwargs):
        if self.fail_upload:
            raise RuntimeError('bucket unreachable')
        with open(path, 'rb') as handle:
            self.objects[key] = handle.read()

    def iter_objects(self, prefix=''):
        for key in list(self.objects):
            if key.startswith(prefix):
                yield SimpleNamespace(key=key, size=len(self.objects[key]), last_modified=None)

    def delete(self, key):
        self.deleted.append(key)
        self.objects.pop(key, None)


class DailyBackupTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix='daily-backup-test-')
        self.db_path = os.path.join(self.temp_dir, 'live.db')
        connection = sqlite3.connect(self.db_path)
        connection.execute('CREATE TABLE t (v TEXT)')
        connection.execute("INSERT INTO t VALUES ('kept')")
        connection.commit()
        connection.close()
        self.patches = [
            patch.object(app_module, 'RUNTIME_STATE_DIR', self.temp_dir),
            patch.object(app_module, 'DATABASE_PATH', self.db_path),
            patch.object(app_module, 'record_daily_backup_activity', lambda action: None),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def run_with(self, bucket):
        with patch.object(app_module, 'file_storage', bucket):
            return app_module.run_daily_database_backup(now=NOW)

    def test_run_uploads_one_valid_gzipped_database(self):
        bucket = FakeBucket()
        self.assertEqual(self.run_with(bucket), 'ok')
        key = 'system_backups/daily/medical_service_db_20261009.sqlite.gz'
        self.assertEqual(list(bucket.objects), [key])
        restored = os.path.join(self.temp_dir, 'restored.db')
        with open(restored, 'wb') as handle:
            handle.write(gzip.decompress(bucket.objects[key]))
        connection = sqlite3.connect(restored)
        self.assertEqual(connection.execute('SELECT v FROM t').fetchone()[0], 'kept')
        connection.close()
        state = app_module.load_daily_backup_state()
        self.assertTrue(state['last_ok'])
        self.assertEqual(state['last_date'], '2026-10-09')
        self.assertEqual(state['copies_kept'], 1)

    def test_prunes_only_dated_copies_older_than_30_days(self):
        prefix = 'system_backups/daily/'
        bucket = FakeBucket(keys=[
            prefix + 'medical_service_db_20260908.sqlite.gz',  # 31 days old
            prefix + 'medical_service_db_20260909.sqlite.gz',  # 30 days old
            prefix + 'medical_service_db_20261001.sqlite.gz',
            prefix + 'notes.txt',
            'reports/medical_service_db_20200101.sqlite.gz',
        ])
        self.run_with(bucket)
        self.assertEqual(bucket.deleted, [prefix + 'medical_service_db_20260908.sqlite.gz'])
        self.assertEqual(app_module.load_daily_backup_state()['copies_kept'], 3)

    def test_due_schedule(self):
        due = app_module.daily_backup_due
        self.assertFalse(due({}, NOW.replace(hour=1, minute=59)))
        self.assertTrue(due({}, NOW))
        self.assertTrue(due({'last_date': '2026-10-08', 'last_ok': True}, NOW))
        self.assertFalse(due({'last_date': '2026-10-09', 'last_ok': True}, NOW))
        self.assertTrue(due({'last_date': '2026-10-09', 'last_ok': False}, NOW))

    def test_skips_without_bucket(self):
        bucket = FakeBucket()
        bucket.writes_bucket = False
        self.assertEqual(self.run_with(bucket), 'skipped')
        self.assertEqual(bucket.objects, {})

    def test_upload_failure_is_recorded_not_raised(self):
        self.assertEqual(self.run_with(FakeBucket(fail_upload=True)), 'failed')
        state = app_module.load_daily_backup_state()
        self.assertFalse(state['last_ok'])
        self.assertIn('bucket unreachable', state['last_error'])

    def test_state_file_round_trip_and_corrupt_file(self):
        app_module.save_daily_backup_state({'last_date': '2026-10-09'})
        self.assertEqual(app_module.load_daily_backup_state(), {'last_date': '2026-10-09'})
        with open(app_module.daily_backup_state_path(), 'w', encoding='utf-8') as handle:
            handle.write('{broken')
        self.assertEqual(app_module.load_daily_backup_state(), {})

    def test_no_scheduler_thread_under_tests(self):
        self.assertFalse(app_module._daily_backup_scheduler_started)
        self.assertNotIn('daily-db-backup', [thread.name for thread in threading.enumerate()])

    def test_status_payload_and_page(self):
        with app_module.app.test_request_context('/admin/backup/status'):
            payload = app_module.backup_status_payload()
        self.assertIn('daily_backup', payload)
        self.assertFalse(payload['daily_backup']['enabled'])
        template = (ROOT / 'templates' / 'system_backup.html').read_text(encoding='utf-8')
        self.assertIn('id="backup-daily-status"', template)
        self.assertIn('payload.daily_backup', template)
        self.assertNotIn('system_backups', app_module.managed_storage_roots())


if __name__ == '__main__':
    unittest.main()
