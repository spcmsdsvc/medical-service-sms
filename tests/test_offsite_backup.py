import gzip
import os
import pathlib
import shutil
import sqlite3
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f'medical_service_offsite_{uuid.uuid4().hex}.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(TEST_DB_PATH))

import app as app_module  # noqa: E402


NOW = datetime(2026, 11, 4, 14, 5, tzinfo=timezone.utc)  # Manila wall-clock, as get_manila_time returns
HOURLY_KEY = 'hourly/medical_service_db_20261104_14.sqlite.gz'


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


class OffsiteBackupTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix='offsite-backup-test-')
        self.db_path = os.path.join(self.temp_dir, 'live.db')
        self.write_row('kept')
        self.offsite = FakeBucket()
        self.patches = [
            patch.object(app_module, 'RUNTIME_STATE_DIR', self.temp_dir),
            patch.object(app_module, 'DATABASE_PATH', self.db_path),
            patch.object(app_module, 'record_daily_backup_activity', lambda action: None),
            patch.object(app_module, 'offsite_storage', self.offsite),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def write_row(self, value):
        connection = sqlite3.connect(self.db_path)
        connection.execute('CREATE TABLE IF NOT EXISTS t (v TEXT)')
        connection.execute('INSERT INTO t VALUES (?)', (value,))
        connection.commit()
        connection.close()
        # A one-row insert can keep the file size, and Windows' ~16 ms clock can keep the
        # modified time, so the unchanged check would miss it; move the time on explicitly.
        info = os.stat(self.db_path)
        os.utime(self.db_path, ns=(info.st_atime_ns, info.st_mtime_ns + 1_000_000_000))

    def restored_rows(self, data):
        restored = os.path.join(self.temp_dir, f'restored-{uuid.uuid4().hex}.db')
        with open(restored, 'wb') as handle:
            handle.write(gzip.decompress(data))
        connection = sqlite3.connect(restored)
        rows = [row[0] for row in connection.execute('SELECT v FROM t ORDER BY rowid')]
        connection.close()
        return rows

    def test_hourly_uploads_one_valid_gzipped_database(self):
        self.assertEqual(app_module.run_hourly_offsite_backup(now=NOW), 'ok')
        self.assertEqual(list(self.offsite.objects), [HOURLY_KEY])
        self.assertEqual(self.restored_rows(self.offsite.objects[HOURLY_KEY]), ['kept'])
        state = app_module.load_offsite_backup_state()
        self.assertTrue(state['last_ok'])
        self.assertEqual(state['last_slot'], '20261104_14')
        self.assertEqual(state['last_key'], HOURLY_KEY)

    def test_skips_outside_the_working_window(self):
        for hour in (7, 20, 2):
            self.assertEqual(app_module.run_hourly_offsite_backup(now=NOW.replace(hour=hour)), 'outside')
        for hour in (8, 19):
            self.write_row(f'hour {hour}')
            self.assertEqual(app_module.run_hourly_offsite_backup(now=NOW.replace(hour=hour)), 'ok')
        self.assertEqual(len(self.offsite.objects), 2)

    def test_skips_a_done_slot_and_an_unchanged_database(self):
        self.assertEqual(app_module.run_hourly_offsite_backup(now=NOW), 'ok')
        self.write_row('same hour')
        self.assertEqual(app_module.run_hourly_offsite_backup(now=NOW.replace(minute=50)), 'done')
        self.assertEqual(app_module.run_hourly_offsite_backup(now=NOW + timedelta(hours=1)), 'ok')
        self.assertEqual(app_module.run_hourly_offsite_backup(now=NOW + timedelta(hours=2)), 'unchanged')
        self.assertEqual(app_module.load_offsite_backup_state()['last_slot'], '20261104_16')
        self.assertEqual(len(self.offsite.objects), 2)

    def test_uploads_again_after_a_write(self):
        app_module.run_hourly_offsite_backup(now=NOW)
        self.write_row('later')
        self.assertEqual(app_module.run_hourly_offsite_backup(now=NOW + timedelta(hours=1)), 'ok')
        newest = self.offsite.objects['hourly/medical_service_db_20261104_15.sqlite.gz']
        self.assertEqual(self.restored_rows(newest), ['kept', 'later'])

    def test_prunes_only_hourly_copies_older_than_48_hours(self):
        old = 'hourly/medical_service_db_20261102_13.sqlite.gz'     # 49 h old
        edge = 'hourly/medical_service_db_20261102_14.sqlite.gz'    # 48 h old
        daily = 'daily/medical_service_db_20261001.sqlite.gz'
        self.offsite.objects.update({old: b'old', edge: b'old', daily: b'old', 'hourly/notes.txt': b'x'})
        app_module.run_hourly_offsite_backup(now=NOW)
        self.assertEqual(self.offsite.deleted, [old])

    def test_failed_upload_is_recorded_not_raised_and_keeps_old_copies(self):
        old = 'hourly/medical_service_db_20261101_09.sqlite.gz'
        self.offsite.objects[old] = b'old'
        self.offsite.fail_upload = True
        self.assertEqual(app_module.run_hourly_offsite_backup(now=NOW), 'failed')
        self.assertEqual(self.offsite.deleted, [])
        state = app_module.load_offsite_backup_state()
        self.assertFalse(state['last_ok'])
        self.assertIn('bucket unreachable', state['last_error'])
        self.assertNotIn('last_slot', state)  # retried at the next check
        self.offsite.fail_upload = False
        self.assertEqual(app_module.run_hourly_offsite_backup(now=NOW.replace(minute=20)), 'ok')
        self.assertTrue(app_module.load_offsite_backup_state()['last_ok'])

    def run_nightly(self, railway):
        with patch.object(app_module, 'file_storage', railway):
            return app_module.run_daily_database_backup(now=NOW.replace(hour=2, minute=30))

    def test_nightly_still_reaches_railway_when_offsite_fails(self):
        self.offsite.fail_upload = True
        railway = FakeBucket()
        self.assertEqual(self.run_nightly(railway), 'ok')
        self.assertEqual(list(railway.objects), ['system_backups/daily/medical_service_db_20261104.sqlite.gz'])
        self.assertFalse(app_module.load_offsite_backup_state()['last_ok'])

    def test_nightly_reaches_offsite_when_railway_fails(self):
        self.assertEqual(self.run_nightly(FakeBucket(fail_upload=True)), 'failed')
        key = 'daily/medical_service_db_20261104.sqlite.gz'
        self.assertEqual(list(self.offsite.objects), [key])
        self.assertEqual(self.restored_rows(self.offsite.objects[key]), ['kept'])
        self.assertTrue(app_module.load_offsite_backup_state()['last_ok'])

    def test_dormant_without_variables(self):
        self.offsite.bucket_configured = False
        self.assertEqual(app_module.run_hourly_offsite_backup(now=NOW), 'skipped')
        self.assertEqual(self.run_nightly(FakeBucket()), 'ok')
        self.assertEqual(self.offsite.objects, {})
        self.assertEqual(app_module.load_offsite_backup_state(), {})
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(app_module.FileStorageBackend(env_prefix='OFFSITE_BACKUP_').bucket_configured)
        self.assertFalse(app_module._daily_backup_scheduler_started)

    def test_status_payload_and_page(self):
        app_module.run_hourly_offsite_backup(now=NOW)
        status = app_module.offsite_backup_status()
        self.assertTrue(status['last_ok'])
        self.assertTrue(status['has_run'])
        self.assertRegex(status['last_success_at'], r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$')
        self.assertTrue(status['last_size_human'])
        with app_module.app.test_request_context('/admin/backup/status'):
            payload = app_module.backup_status_payload()
        self.assertIn('offsite_backup', payload)
        self.assertNotIn('bucket', ' '.join(payload['offsite_backup']))
        template = (ROOT / 'templates' / 'system_backup.html').read_text(encoding='utf-8')
        self.assertIn('id="backup-offsite-status"', template)
        self.assertIn('payload.offsite_backup', template)


if __name__ == '__main__':
    unittest.main()
