"""Settings -> Storage: health report additions, route permissions, dashboard warning."""

import os
import pathlib
import tempfile
import unittest
import uuid
from unittest.mock import patch

from tests.sw_cache_version import assert_cache_version_at_least

os.environ.setdefault(
    'MEDICAL_SERVICE_TEST_DB',
    str(pathlib.Path(tempfile.gettempdir()) / f'medical_service_storage_{uuid.uuid4().hex}.db'),
)

import app as app_module  # noqa: E402


ROOT = pathlib.Path(__file__).resolve().parents[1]


def bucket_report(connected=True, **counts):
    return {
        'storage': {'mode': 'bucket', 'bucket_enabled': True},
        'connection': {'ok': connected, 'message': 'Connected.' if connected else 'Timed out.'},
        'volume': {'file_count': 0, 'size_bytes': 0, 'size_human': '0 B'},
        'bucket': {'object_count': 3, 'size_bytes': 1024, 'size_human': '1.00 KB'},
        'counts': {'verified': 0, 'migrated': 0, 'pending': 0, 'missing': 0, 'conflicting': 0, 'failed': 0, **counts},
        'complete': False,
    }


class StorageSettingsTests(unittest.TestCase):

    def setUp(self):
        self.app = app_module.app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        with self.app.app_context():
            app_module.db.create_all()
            user = app_module.User(
                username=f'storage-{uuid.uuid4().hex[:8]}',
                password=app_module.generate_password_hash('test-password'),
                role='staff',
                is_active=True,
            )
            app_module.db.session.add(user)
            app_module.db.session.commit()
            self.user_id = user.id
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.user_id)
            session['_fresh'] = True

    def tearDown(self):
        with self.app.app_context():
            user = app_module.db.session.get(app_module.User, self.user_id)
            if user:
                app_module.db.session.delete(user)
                app_module.db.session.commit()
            app_module.db.session.remove()

    def _superadmin(self, value=True):
        return patch.object(app_module, 'is_superadmin_user', return_value=value)

    def _report(self, bucket, limit_bytes=10 * 1024 ** 3):
        with self.app.app_context(), \
                patch.object(app_module, 'get_bucket_migration_report', return_value=bucket), \
                patch.object(app_module, 'get_storage_limit_bytes', return_value=(limit_bytes, limit_bytes / 1024 ** 3)):
            return app_module.get_storage_health_report()

    def test_storage_routes_refuse_a_non_superadmin(self):
        with self._superadmin(False):
            self.assertEqual(self.client.get('/admin/storage-health').status_code, 403)
            self.assertEqual(self.client.get('/admin/storage-bucket/status').status_code, 403)
            self.assertEqual(self.client.post('/admin/storage-bucket/verify', json={}).status_code, 403)

    def test_overall_status_reflects_volume_and_bucket(self):
        healthy = self._report(bucket_report(migrated=2, pending=1))
        self.assertEqual(healthy['overall']['status'], 'healthy')
        self.assertEqual(healthy['bucket_unverified_count'], 3)
        self.assertEqual(healthy['bucket_issue_count'], 0)

        self.assertEqual(self._report(bucket_report(connected=False))['overall']['status'], 'warning')

        issues = self._report(bucket_report(conflicting=1, missing=1, failed=1))
        self.assertEqual(issues['overall']['status'], 'warning')
        self.assertEqual(issues['bucket_issue_count'], 3)

        # A one-byte limit puts volume usage far past 90%.
        self.assertEqual(self._report(bucket_report(), limit_bytes=1)['overall']['status'], 'critical')

    def test_dashboard_warns_superadmins_when_the_volume_is_nearly_full(self):
        with patch.object(app_module, 'backup_summary', return_value={'overdue': False, 'status': 'idle'}):
            with self._superadmin(), patch.object(app_module, 'volume_disk_usage_percent', return_value=93):
                self.assertIn(b'Storage volume is 93% full.', self.client.get('/').data)
            with self._superadmin(), patch.object(app_module, 'volume_disk_usage_percent', return_value=50):
                self.assertNotIn(b'Storage volume is', self.client.get('/').data)
            with self._superadmin(False), patch.object(app_module, 'volume_disk_usage_percent', return_value=93):
                self.assertNotIn(b'Storage volume is', self.client.get('/').data)

    def test_page_reads_one_endpoint_and_has_no_dead_bucket_code(self):
        settings_source = (ROOT / 'templates' / 'settings.html').read_text(encoding='utf-8')
        for removed in ('runBucketMigrationBatch', 'bucket-migrate-btn', 'storage-connection', 'refresh=1',
                        'loadBucketMigrationStatus'):
            self.assertNotIn(removed, settings_source)
        self.assertIn('data-settings-section="storage"', settings_source)
        self.assertIn('storage-largest-files', settings_source)
        with self._superadmin():
            self.assertEqual(self.client.get('/settings').status_code, 200)
        assert_cache_version_at_least(self, 236, (ROOT / 'app.py').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
