import io
import json
import os
import pathlib
import tempfile
import time
import unittest
import uuid
import zipfile
from types import SimpleNamespace
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f'medical_service_backup_{uuid.uuid4().hex}.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(TEST_DB_PATH))

import app as app_module  # noqa: E402


class BackupBucketHandlingTests(unittest.TestCase):
    def test_bucket_object_failures_are_reported_without_dropping_other_objects(self):
        class StubStorage:
            bucket_configured = True
            bucket_name = 'private-files'

            def test_connection(self):
                return {'ok': True, 'message': 'connected'}

            def iter_objects(self):
                yield SimpleNamespace(key='reports/kept.pdf', size=4)
                yield SimpleNamespace(key='reports/missing.pdf', size=7)
                yield SimpleNamespace(key='unmanaged/ignored.bin', size=3)

            def download_bytes(self, key):
                if key.endswith('missing.pdf'):
                    raise RuntimeError('object disappeared during backup')
                return b'kept'

        buffer = io.BytesIO()
        with patch.object(app_module, 'file_storage', StubStorage()), \
                patch.object(app_module, 'managed_storage_roots', return_value=[('reports', None)]):
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
                result = app_module.add_bucket_objects_to_backup_zip(backup_zip)

        self.assertTrue(result['connected'])
        self.assertEqual([item['key'] for item in result['objects']], ['reports/kept.pdf'])
        self.assertEqual([error['name'] for error in result['errors']], ['reports/missing.pdf'])

        with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as backup_zip:
            self.assertEqual(backup_zip.read('bucket_objects/reports/kept.pdf'), b'kept')

    def test_download_backup_returns_zip_with_manifest_when_bucket_is_unavailable(self):
        app = app_module.app
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False

        class UnavailableStorage:
            bucket_configured = True
            bucket_name = 'private-files'

            def test_connection(self):
                return {'ok': False, 'message': 'temporary bucket outage'}

        user = None
        with app.app_context():
            app_module.db.create_all()
            user = app_module.User(
                username=f'backup-test-{uuid.uuid4().hex[:8]}',
                password=app_module.generate_password_hash('test-password'),
                role='staff',
                is_active=True,
            )
            app_module.db.session.add(user)
            app_module.db.session.commit()
            user_id = user.id

        client = app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True

        with tempfile.NamedTemporaryFile(delete=False) as db_file:
            db_file.write(b'isolated backup database')
            db_path = db_file.name

        try:
            with patch.object(app_module, 'is_superadmin_user', return_value=True), \
                    patch.object(app_module, 'file_storage', UnavailableStorage()), \
                    patch.object(app_module, 'get_active_sqlite_database_path', return_value=db_path), \
                    patch.object(app_module, 'get_backup_upload_roots', return_value=[]):
                response = client.get('/admin/download-backup')

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['X-Backup-Complete'], 'false')
            with zipfile.ZipFile(io.BytesIO(response.data)) as backup_zip:
                manifest = json.loads(backup_zip.read('backup_manifest.json'))
                errors = json.loads(backup_zip.read('backup_errors.json'))
                self.assertFalse(manifest['backup_complete'])
                self.assertEqual(manifest['backup_warning_count'], 1)
                self.assertEqual(errors[0]['scope'], 'bucket_connection')
                self.assertIn(f'database/{pathlib.Path(db_path).name}', backup_zip.namelist())
            response.close()
        finally:
            os.remove(db_path)
            with app.app_context():
                saved_user = app_module.db.session.get(app_module.User, user_id)
                if saved_user:
                    app_module.db.session.delete(saved_user)
                    app_module.db.session.commit()
                app_module.db.session.remove()

    def test_slow_bucket_reads_stop_at_the_backup_budget(self):
        class SlowStorage:
            bucket_configured = True
            bucket_name = 'private-files'

            def test_connection_for_backup(self, *, timeout_seconds):
                self.connection_timeout = timeout_seconds
                return {'ok': True, 'message': 'connected'}

            def iter_objects_for_backup(self, *, timeout_seconds):
                self.list_timeout = timeout_seconds
                for index in range(100):
                    yield SimpleNamespace(key=f'reports/slow-{index}.pdf', size=4)

            def download_bytes_for_backup(self, key, *, timeout_seconds):
                time.sleep(0.01)
                return b'slow'

        buffer = io.BytesIO()
        storage = SlowStorage()
        with patch.object(app_module, 'file_storage', storage), \
                patch.object(app_module, 'managed_storage_roots', return_value=[('reports', None)]), \
                patch.object(app_module, 'BACKUP_BUCKET_DOWNLOAD_BUDGET_SECONDS', 0.03):
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
                result = app_module.add_bucket_objects_to_backup_zip(backup_zip)

        self.assertTrue(result['connected'])
        self.assertTrue(result['budget_exhausted'])
        self.assertLess(len(result['objects']), 100)
        self.assertEqual([error['scope'] for error in result['errors']], ['bucket_budget'])
        self.assertEqual(storage.connection_timeout, app_module.BACKUP_BUCKET_OPERATION_TIMEOUT_SECONDS)
        self.assertEqual(storage.list_timeout, app_module.BACKUP_BUCKET_OPERATION_TIMEOUT_SECONDS)


class BackupDownloadIsNeverCachedTests(unittest.TestCase):
    """The backup download must not reach the service worker's navigation branch.

    The reported symptom was an admin seeing the app's own "you are offline" page while
    online. `/admin/download-backup` is a plain <a href>, so it arrives at the worker as a
    navigation; matched after the navigate branch it reached fieldNavigationFirst(), which
    caches every ok response and, when the network throws, walks a fallback chain ending at
    caches.match('/offline'). Three faults followed from one placement:

      1. an 80MB+ archive of the database and every upload written into Cache Storage,
      2. a STALE archive returned on a later attempt as if it were current, and
      3. the real error replaced by the offline page, which hid the failure entirely.

    `Cache-Control: no-store` does not help: the Cache Storage API ignores HTTP cache headers.
    """

    @classmethod
    def setUpClass(cls):
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.worker = source.split('sw = r"""')[1].split('\n"""')[0]
        cls.handler = cls.worker.split("self.addEventListener('fetch', event => {")[1]

    def test_the_backup_route_is_network_only(self):
        prefixes = self.worker.split('const NETWORK_ONLY_DOWNLOAD_PREFIXES = [')[1].split(']')[0]
        self.assertIn("'/admin/download-'", prefixes)
        self.assertIn("'/export_'", prefixes, 'the export fix must not have been dropped')

    def test_it_is_matched_before_the_navigation_branch(self):
        """Ordering is the whole fix, exactly as it was for /export_."""
        network_only_at = self.handler.find('NETWORK_ONLY_DOWNLOAD_PREFIXES.some')
        navigate_at = self.handler.find("request.mode === 'navigate'")
        self.assertGreater(network_only_at, -1, 'the network-only branch is missing')
        self.assertGreater(navigate_at, -1, 'the navigate branch is missing')
        self.assertLess(network_only_at, navigate_at,
                        'authenticated downloads must be matched before the navigate branch')

    def test_the_branch_touches_no_cache_and_returns(self):
        """Positive control on the negative: prove the branch actually returns.

        Without the `return` the request would fall through to the navigate branch anyway,
        which is the defect this guards.
        """
        branch = self.handler.split('NETWORK_ONLY_DOWNLOAD_PREFIXES.some')[1].split('\n  }')[0]
        self.assertIn('event.respondWith(fetch(request))', branch)
        self.assertIn('return;', branch)
        for forbidden in ('caches.', 'cache.put', 'RUNTIME_CACHE', 'fieldNavigationFirst'):
            self.assertNotIn(forbidden, branch, f'the branch must not reach {forbidden}')


class BackupArchiveIsDataOnlyTests(unittest.TestCase):
    """Application source is no longer archived.

    It lives in git, and including it made the archive roughly three times larger than it
    needed to be. Worse, `static` was a source path while `static/uploads` is an upload root,
    so every upload was stored twice: of an 82MB measured archive, 56MB was source and 47MB
    of that was a byte-for-byte duplicate of the uploads section.
    """

    def test_the_source_helper_is_gone(self):
        self.assertFalse(hasattr(app_module, 'get_backup_source_paths'),
                         'the source archive helper is back')

    def test_a_generated_archive_carries_no_source_tree(self):
        app = app_module.app
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False

        with app.app_context():
            app_module.db.create_all()
            user = app_module.User(
                username=f'backup-scope-{uuid.uuid4().hex[:8]}',
                password=app_module.generate_password_hash('test-password'),
                role='staff',
                is_active=True,
            )
            app_module.db.session.add(user)
            app_module.db.session.commit()
            user_id = user.id

        client = app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True

        upload_root = tempfile.mkdtemp(prefix='medical_service_backup_uploads_')
        with open(os.path.join(upload_root, 'report.pdf'), 'wb') as upload_file:
            upload_file.write(b'an uploaded report')
        with tempfile.NamedTemporaryFile(delete=False) as db_file:
            db_file.write(b'isolated backup database')
            db_path = db_file.name

        class NoBucket:
            bucket_configured = False
            bucket_name = ''

        try:
            with patch.object(app_module, 'is_superadmin_user', return_value=True), \
                    patch.object(app_module, 'file_storage', NoBucket()), \
                    patch.object(app_module, 'get_active_sqlite_database_path', return_value=db_path), \
                    patch.object(app_module, 'get_backup_upload_roots', return_value=[upload_root]):
                response = client.get('/admin/download-backup')

            self.assertEqual(response.status_code, 200)
            with zipfile.ZipFile(io.BytesIO(response.data)) as backup_zip:
                names = backup_zip.namelist()
                manifest = json.loads(backup_zip.read('backup_manifest.json'))

                self.assertFalse([name for name in names if name.startswith('source/')],
                                 'the archive still carries a source tree')
                self.assertEqual(manifest['archive_scope'], 'data_only')
                self.assertFalse(manifest['source_included'])

                # Positive control: the data that cannot be recreated is still there, so the
                # assertion above cannot pass by the backup simply being empty.
                self.assertIn(f'database/{pathlib.Path(db_path).name}', names)
                self.assertTrue([name for name in names if name.endswith('report.pdf')],
                                'uploads are missing from the archive')

                # And each upload appears exactly once.
                report_entries = [name for name in names if name.endswith('report.pdf')]
                self.assertEqual(len(report_entries), 1,
                                 f'upload archived more than once: {report_entries}')
            response.close()
        finally:
            os.remove(db_path)
            os.remove(os.path.join(upload_root, 'report.pdf'))
            os.rmdir(upload_root)
            with app.app_context():
                saved_user = app_module.db.session.get(app_module.User, user_id)
                if saved_user:
                    app_module.db.session.delete(saved_user)
                    app_module.db.session.commit()
                app_module.db.session.remove()


if __name__ == '__main__':
    unittest.main()
