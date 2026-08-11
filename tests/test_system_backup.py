import io
import json
import os
import pathlib
import shutil
import sqlite3
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


def save_completed_backup_state(result):
    state = app_module.empty_backup_job_state()
    state.update({
        'status': 'completed_with_warnings' if result.get('warnings') else 'completed',
        'phase': 'done',
        'phase_label': 'Backup ready',
        'percent': 100,
        'backup_complete': bool(result.get('backup_complete')),
        'database_included': bool(result.get('database_included')),
        'database_snapshot_method': result.get('database_snapshot_method', ''),
        'warning_count': len(result.get('warnings') or []),
        'warnings': result.get('warnings') or [],
        'archive': {
            'filename': result.get('filename', ''),
            'path': result.get('path', ''),
            'size_bytes': result.get('size_bytes', 0),
            'size_human': result.get('size_human', ''),
            'sha256': result.get('sha256', ''),
            'created_at': result.get('created_at', ''),
        },
    })
    app_module.save_backup_job_state(state)


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
            db_path = db_file.name
        connection = sqlite3.connect(db_path)
        connection.execute('CREATE TABLE backup_probe (value TEXT)')
        connection.execute('INSERT INTO backup_probe(value) VALUES (?)', ('bucket warning test',))
        connection.commit()
        connection.close()

        backup_root = tempfile.mkdtemp(prefix='medical_service_backup_archive_')
        state_root = tempfile.mkdtemp(prefix='medical_service_backup_state_')
        try:
            with patch.object(app_module, 'is_superadmin_user', return_value=True), \
                    patch.object(app_module, 'file_storage', UnavailableStorage()), \
                    patch.object(app_module, 'get_active_sqlite_database_path', return_value=db_path), \
                    patch.object(app_module, 'get_backup_upload_roots', return_value=[]), \
                    patch.object(app_module, 'BACKUP_ARCHIVE_DIR', backup_root), \
                    patch.object(app_module, 'RUNTIME_STATE_DIR', state_root):
                result = app_module.build_system_backup_archive('a' * 16, 'backup-test')
                save_completed_backup_state(result)
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
            response_bytes = response.data
            response.close()
            with patch.object(app_module, 'is_superadmin_user', return_value=True), \
                    patch.object(app_module, 'BACKUP_ARCHIVE_DIR', backup_root), \
                    patch.object(app_module, 'RUNTIME_STATE_DIR', state_root):
                second_response = client.get('/admin/download-backup')
                ranged_response = client.get('/admin/download-backup', headers={'Range': 'bytes=0-31'})
            self.assertEqual(second_response.status_code, 200)
            self.assertEqual(response_bytes, second_response.data)
            self.assertEqual(ranged_response.status_code, 206)
            self.assertTrue(ranged_response.headers.get('Content-Range', '').startswith('bytes 0-31/'))
            second_response.close()
            ranged_response.close()
        finally:
            os.remove(db_path)
            shutil.rmtree(backup_root, ignore_errors=True)
            shutil.rmtree(state_root, ignore_errors=True)
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

    # Locate the navigate BRANCH by its full `if (...) {` form, never by the bare
    # expression. The bare text now appears twice: the Backup Center branch tests
    # `request.mode === 'navigate'` inside its own offline fallback, so a `.find()`
    # on the expression returns that occurrence and silently compares the handler
    # against itself -- which turned one of these tests red and would have made the
    # other pass vacuously.
    NAVIGATE_BRANCH = "if (request.mode === 'navigate') {"

    def test_the_backup_center_is_network_first_and_uncached(self):
        prefixes = self.worker.split('const NETWORK_FIRST_AUTHENTICATED_PREFIXES = [')[1].split(']')[0]
        self.assertIn("'/admin/backup'", prefixes)
        branch_at = self.handler.find('NETWORK_FIRST_AUTHENTICATED_PREFIXES.some')
        download_at = self.handler.find('NETWORK_ONLY_DOWNLOAD_PREFIXES.some')
        navigate_at = self.handler.find(self.NAVIGATE_BRANCH)
        self.assertGreater(branch_at, -1)
        self.assertLess(branch_at, download_at)
        self.assertLess(branch_at, navigate_at)
        branch = self.handler[branch_at:].split('\n  }')[0]
        self.assertIn("cache: 'no-store'", branch)
        self.assertIn('return;', branch)
        self.assertNotIn('cache.put', branch)

    def test_the_backup_center_still_fails_like_the_rest_of_the_app(self):
        """A rejected fetch must not put a raw browser error page on screen.

        Before the fallback existed, opening /admin/backup offline landed on
        `chrome-error://chromewebdata/` while every other navigation in the app
        reached /offline. The API calls degrade separately, into the JSON body the
        page's own requestJson() already renders.
        """
        branch_at = self.handler.find('NETWORK_FIRST_AUTHENTICATED_PREFIXES.some')
        branch = self.handler[branch_at:].split('\n  }')[0]
        self.assertIn("caches.match('/offline')", branch)
        self.assertIn('offlineApiResponse()', branch)
        # The page fallback must be reached only for navigations; an API caller
        # getting HTML back is the defect this whole class of fix exists to stop.
        self.assertIn("request.mode === 'navigate'", branch)

    def test_it_is_matched_before_the_navigation_branch(self):
        """Ordering is the whole fix, exactly as it was for /export_."""
        network_only_at = self.handler.find('NETWORK_ONLY_DOWNLOAD_PREFIXES.some')
        navigate_at = self.handler.find(self.NAVIGATE_BRANCH)
        self.assertGreater(network_only_at, -1, 'the network-only branch is missing')
        self.assertGreater(navigate_at, -1, 'the navigate branch is missing')
        self.assertLess(network_only_at, navigate_at,
                        'authenticated downloads must be matched before the navigate branch')

    def test_the_branch_touches_no_cache_and_returns(self):
        """Positive control on the negative: prove the branch actually returns."""
        branch = self.handler.split('NETWORK_ONLY_DOWNLOAD_PREFIXES.some')[1].split('\n  }')[0]
        self.assertIn('event.respondWith(fetch(request))', branch)
        self.assertIn('return;', branch)
        for forbidden in ('caches.', 'cache.put', 'RUNTIME_CACHE', 'fieldNavigationFirst'):
            self.assertNotIn(forbidden, branch, f'the branch must not reach {forbidden}')


class BackupCenterRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = app_module.app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        with self.app.app_context():
            app_module.db.create_all()
            self.user = app_module.User(
                username=f'backup-route-{uuid.uuid4().hex[:8]}',
                password=app_module.generate_password_hash('test-password'),
                role='staff',
                is_active=True,
            )
            app_module.db.session.add(self.user)
            app_module.db.session.commit()
            self.user_id = self.user.id
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.user_id)
            session['_fresh'] = True

    def tearDown(self):
        with self.app.app_context():
            saved_user = app_module.db.session.get(app_module.User, self.user_id)
            if saved_user:
                app_module.db.session.delete(saved_user)
                app_module.db.session.commit()
            app_module.db.session.remove()

    def test_backup_center_denies_non_superadmins_with_html(self):
        with patch.object(app_module, 'is_superadmin_user', return_value=False):
            response = self.client.get('/admin/backup')
        self.assertEqual(response.status_code, 403)
        self.assertIn(b'Access denied', response.data)

    def test_download_without_archive_is_a_clear_html_404(self):
        archive_root = tempfile.mkdtemp(prefix='medical_service_backup_archive_')
        state_root = tempfile.mkdtemp(prefix='medical_service_backup_state_')
        try:
            with patch.object(app_module, 'is_superadmin_user', return_value=True), \
                    patch.object(app_module, 'BACKUP_ARCHIVE_DIR', archive_root), \
                    patch.object(app_module, 'RUNTIME_STATE_DIR', state_root):
                response = self.client.get('/admin/download-backup')
            self.assertEqual(response.status_code, 404)
            self.assertIn(b'No backup is stored', response.data)
            self.assertIn(b'Backup Center', response.data)
        finally:
            shutil.rmtree(archive_root, ignore_errors=True)
            shutil.rmtree(state_root, ignore_errors=True)

    def test_start_refuses_low_space_before_spawning_a_thread(self):
        preflight = {
            'ok': False,
            'reason': 'Not enough space to build a backup.',
            'required_human': '1 GB',
            'free_human': '1 MB',
        }
        with patch.object(app_module, 'is_superadmin_user', return_value=True), \
                patch.object(app_module, 'backup_preflight_report', return_value=preflight), \
                patch.object(app_module.threading, 'Thread') as thread:
            response = self.client.post('/admin/backup/start', json={})
        self.assertEqual(response.status_code, 507)
        self.assertIn('Not enough space', response.get_json()['message'])
        thread.assert_not_called()

    def test_preflight_reclaims_previous_archive_only_when_that_makes_space(self):
        fake_archive = {
            'filename': 'medical_service_backup_20260809_120000.zip',
            'size_bytes': 300 * 1024 * 1024,
        }
        with patch.object(app_module, 'estimate_backup_source_bytes', return_value=1024), \
                patch.object(app_module, 'current_backup_archive', return_value=fake_archive), \
                patch.object(app_module.shutil, 'disk_usage', return_value=SimpleNamespace(free=100 * 1024 * 1024)):
            report = app_module.backup_preflight_report()
        self.assertTrue(report['ok'])
        self.assertTrue(report['reclaim_existing'])

        small_archive = {**fake_archive, 'size_bytes': 100 * 1024 * 1024}
        with patch.object(app_module, 'estimate_backup_source_bytes', return_value=1024), \
                patch.object(app_module, 'current_backup_archive', return_value=small_archive), \
                patch.object(app_module.shutil, 'disk_usage', return_value=SimpleNamespace(free=1)):
            report = app_module.backup_preflight_report()
        self.assertFalse(report['ok'])
        self.assertFalse(report['reclaim_existing'])

    def test_storage_health_reports_published_archive_separately(self):
        archive_root = tempfile.mkdtemp(prefix='medical_service_backup_archive_')
        with tempfile.NamedTemporaryFile(delete=False) as db_file:
            db_path = db_file.name
        archive_path = os.path.join(archive_root, 'medical_service_backup_20260809_120000.zip')
        with open(archive_path, 'wb') as archive_file:
            archive_file.write(b'published backup')
        try:
            with patch.object(app_module, 'BACKUP_ARCHIVE_DIR', archive_root), \
                    patch.object(app_module, 'get_active_sqlite_database_path', return_value=db_path), \
                    patch.object(app_module, 'get_backup_upload_roots', return_value=[]), \
                    patch.object(app_module, 'get_bucket_migration_report', return_value={
                        'volume': {'file_count': 0, 'size_bytes': 0, 'size_human': '0 B'},
                        'bucket': {'object_count': 0, 'size_bytes': 0, 'size_human': '0 B'},
                        'connection': {'ok': False, 'message': 'not configured'},
                    }):
                report = app_module.get_storage_health_report()
            self.assertEqual(report['backup_archive']['file_count'], 1)
            self.assertEqual(report['backup_archive']['size_bytes'], len(b'published backup'))
            self.assertGreaterEqual(report['used_bytes'], len(b'published backup'))
        finally:
            try:
                os.remove(db_path)
            except OSError:
                pass
            shutil.rmtree(archive_root, ignore_errors=True)

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

    def test_manifest_write_failure_keeps_archive_and_reports_warning(self):
        """A final metadata write failure must not turn the whole build into a 500."""
        with tempfile.NamedTemporaryFile(delete=False) as db_file:
            db_path = db_file.name
        connection = sqlite3.connect(db_path)
        connection.execute('CREATE TABLE backup_probe (value TEXT)')
        connection.execute('INSERT INTO backup_probe(value) VALUES (?)', ('manifest warning test',))
        connection.commit()
        connection.close()

        backup_root = tempfile.mkdtemp(prefix='medical_service_backup_archive_')
        state_root = tempfile.mkdtemp(prefix='medical_service_backup_state_')
        original_writer = app_module.safe_zip_writestr

        def fail_manifest(zip_handle, archive_name, data, errors=None, scope='archive_member'):
            if archive_name == 'backup_manifest.json':
                app_module.record_backup_error(errors, scope, archive_name, 'manifest disk write failed')
                return False
            return original_writer(zip_handle, archive_name, data, errors, scope)

        class NoBucket:
            bucket_configured = False
            bucket_name = ''

        try:
            with patch.object(app_module, 'file_storage', NoBucket()), \
                    patch.object(app_module, 'get_active_sqlite_database_path', return_value=db_path), \
                    patch.object(app_module, 'get_backup_upload_roots', return_value=[]), \
                    patch.object(app_module, 'BACKUP_ARCHIVE_DIR', backup_root), \
                    patch.object(app_module, 'RUNTIME_STATE_DIR', state_root), \
                    patch.object(app_module, 'safe_zip_writestr', side_effect=fail_manifest):
                result = app_module.build_system_backup_archive('c' * 16, 'backup-manifest-warning')

            self.assertTrue(os.path.isfile(result['path']))
            self.assertFalse(result['backup_complete'])
            self.assertTrue(any(
                warning.get('scope') == 'archive_member'
                and warning.get('name') == 'backup_manifest.json'
                for warning in result['warnings']
            ))
            with zipfile.ZipFile(result['path']) as backup_zip:
                self.assertNotIn('backup_manifest.json', backup_zip.namelist())
        finally:
            os.remove(db_path)
            shutil.rmtree(backup_root, ignore_errors=True)
            shutil.rmtree(state_root, ignore_errors=True)

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
            db_path = db_file.name
        connection = sqlite3.connect(db_path)
        connection.execute('CREATE TABLE backup_probe (value TEXT)')
        connection.execute('INSERT INTO backup_probe(value) VALUES (?)', ('data only test',))
        connection.commit()
        connection.close()

        class NoBucket:
            bucket_configured = False
            bucket_name = ''

        backup_root = tempfile.mkdtemp(prefix='medical_service_backup_archive_')
        state_root = tempfile.mkdtemp(prefix='medical_service_backup_state_')
        try:
            with patch.object(app_module, 'is_superadmin_user', return_value=True), \
                    patch.object(app_module, 'file_storage', NoBucket()), \
                    patch.object(app_module, 'get_active_sqlite_database_path', return_value=db_path), \
                    patch.object(app_module, 'get_backup_upload_roots', return_value=[upload_root]), \
                    patch.object(app_module, 'BACKUP_ARCHIVE_DIR', backup_root), \
                    patch.object(app_module, 'RUNTIME_STATE_DIR', state_root):
                result = app_module.build_system_backup_archive('b' * 16, 'backup-scope')
                save_completed_backup_state(result)
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
            shutil.rmtree(backup_root, ignore_errors=True)
            shutil.rmtree(state_root, ignore_errors=True)
            with app.app_context():
                saved_user = app_module.db.session.get(app_module.User, user_id)
                if saved_user:
                    app_module.db.session.delete(saved_user)
                    app_module.db.session.commit()
                app_module.db.session.remove()


class SqliteSnapshotTests(unittest.TestCase):
    """The snapshot is the most serious correctness fix in the whole rework.

    Before it, the live database was copied as a raw file with no `-wal`/`-shm`/
    `-journal` sidecars, so a commit landing mid-copy produced a torn archive that
    looked perfectly normal until someone needed to restore it. Nothing tested
    `create_sqlite_snapshot` directly -- it was only ever exercised sideways
    through a full build, which cannot tell a consistent snapshot from a lucky one.
    """

    def setUp(self):
        self.work = pathlib.Path(tempfile.mkdtemp(prefix='snapshot_test_'))
        self.addCleanup(shutil.rmtree, self.work, True)
        self.source = self.work / 'source.db'
        connection = sqlite3.connect(self.source)
        connection.execute('CREATE TABLE widget (id INTEGER PRIMARY KEY, label TEXT)')
        connection.executemany(
            'INSERT INTO widget (label) VALUES (?)', [(f'row-{index}',) for index in range(250)]
        )
        connection.commit()
        connection.close()

    def test_the_snapshot_is_a_consistent_self_contained_database(self):
        destination = self.work / 'snapshot.db'
        result = app_module.create_sqlite_snapshot(str(self.source), str(destination))

        self.assertEqual(result['method'], 'sqlite_backup_api')
        self.assertEqual(result['quick_check'], 'ok')
        self.assertTrue(result['sha256'], 'the snapshot must be checksummed')

        # Self-contained means exactly this: no sidecar had to come with it.
        self.assertEqual(result['sidecars_included'], [])
        for suffix in ('-wal', '-shm', '-journal'):
            self.assertFalse(os.path.exists(f'{destination}{suffix}'))

        # And it must be a real, queryable database with the real rows in it.
        copy = sqlite3.connect(destination)
        self.assertEqual(copy.execute('SELECT COUNT(*) FROM widget').fetchone()[0], 250)
        self.assertEqual(copy.execute('PRAGMA quick_check').fetchone()[0], 'ok')
        copy.close()

    def test_an_unreadable_database_falls_back_to_a_raw_copy_and_says_so(self):
        """Positive control on the test above.

        Without this, `method == 'sqlite_backup_api'` could be passing because the
        function always returns that string. The fallback must also RECORD itself,
        or a degraded backup is indistinguishable from a clean one.
        """
        broken = self.work / 'broken.db'
        broken.write_bytes(b'this is emphatically not a sqlite database')
        destination = self.work / 'broken_snapshot.db'

        result = app_module.create_sqlite_snapshot(str(broken), str(destination))
        self.assertEqual(result['method'], 'raw_copy_fallback')
        self.assertTrue(result.get('error'), 'the fallback must record why it happened')
        self.assertTrue(destination.exists())

    def test_a_missing_database_raises_so_the_job_fails(self):
        """A backup without the database must never be offered as complete.

        Raising is the point: `add_path_to_backup_zip` returns 0 for a missing path
        without recording anything, which is how a green `backup_complete: true`
        could once ship with `database_included: false`.
        """
        with self.assertRaises(FileNotFoundError):
            app_module.create_sqlite_snapshot(
                str(self.work / 'not_here.db'), str(self.work / 'out.db')
            )


class BackupArtifactSweeperTests(unittest.TestCase):
    """The sweeper deletes files, so its allowlist is safety-critical."""

    def setUp(self):
        self.work = pathlib.Path(tempfile.mkdtemp(prefix='sweeper_test_'))
        self.addCleanup(shutil.rmtree, self.work, True)

    def test_the_sweeper_never_deletes_a_test_database(self):
        """This suite's own database is named `medical_service_backup_<hex>.db`.

        A broadened glob over the temp directory would therefore delete the
        database out from under a running suite, and the resulting failures would
        look like anything except their real cause. The rule is `.zip` only.
        """
        temp_root = pathlib.Path(tempfile.gettempdir())
        decoy = temp_root / f'medical_service_backup_{uuid.uuid4().hex}.db'
        decoy.write_bytes(b'pretend test database')
        # Old enough that an age check would not save it.
        os.utime(decoy, (0, 0))
        self.addCleanup(lambda: decoy.exists() and decoy.unlink())

        # The real suite DB shares the same shape; assert on it too, since that is
        # the file that actually matters.
        self.assertTrue(str(TEST_DB_PATH.name).startswith('medical_service_backup_'))

        with patch.object(app_module, 'BACKUP_ARCHIVE_DIR', str(self.work)):
            app_module.sweep_backup_artifacts()

        self.assertTrue(decoy.exists(), 'the sweeper deleted a .db file it must never touch')

    def test_the_sweeper_does_remove_a_stale_temp_archive(self):
        """Positive control: prove the sweeper is not simply inert.

        Without this, the test above would pass just as happily against a sweeper
        that had been commented out.
        """
        temp_root = pathlib.Path(tempfile.gettempdir())
        stale = temp_root / f'medical_service_backup_{uuid.uuid4().hex}.zip'
        stale.write_bytes(b'stale archive')
        os.utime(stale, (0, 0))
        self.addCleanup(lambda: stale.exists() and stale.unlink())

        with patch.object(app_module, 'BACKUP_ARCHIVE_DIR', str(self.work)):
            app_module.sweep_backup_artifacts()

        self.assertFalse(stale.exists(), 'a stale legacy .zip should have been swept')

    def test_only_the_latest_archive_is_kept(self):
        older = self.work / 'medical_service_backup_20260101_010101.zip'
        newer = self.work / 'medical_service_backup_20260102_010101.zip'
        older.write_bytes(b'older')
        newer.write_bytes(b'newer')
        os.utime(older, (time.time() - 600, time.time() - 600))

        with patch.object(app_module, 'BACKUP_ARCHIVE_DIR', str(self.work)):
            app_module.sweep_backup_artifacts()

        self.assertTrue(newer.exists(), 'the newest archive must survive')
        self.assertFalse(older.exists(), 'older archives must be reclaimed')


class BackupJobReconcileTests(unittest.TestCase):
    """A job whose process is gone must not leave the page spinning forever."""

    def setUp(self):
        self.work = pathlib.Path(tempfile.mkdtemp(prefix='reconcile_test_'))
        self.addCleanup(shutil.rmtree, self.work, True)
        self.state_patch = patch.object(app_module, 'RUNTIME_STATE_DIR', str(self.work))
        self.state_patch.start()
        self.addCleanup(self.state_patch.stop)

    def _write_running(self, boot_id, updated_at=None):
        state = app_module.empty_backup_job_state()
        state.update({
            'job_id': 'job-under-test',
            'boot_id': boot_id,
            'status': 'running',
            'started_at': app_module.get_manila_time().isoformat(),
        })
        app_module.save_backup_job_state(state)
        if updated_at is not None:
            stored = app_module.load_backup_job_state()
            stored['updated_at'] = updated_at
            path = app_module.backup_job_state_path()
            with open(path, 'w', encoding='utf-8') as handle:
                json.dump(stored, handle)

    def test_a_job_from_a_previous_process_is_marked_failed(self):
        """A Railway redeploy mid-build is the ordinary cause.

        `boot_id` rather than pid, because pids are reused and a reused pid would
        make a dead job look alive.
        """
        self._write_running('a-boot-id-from-a-process-that-no-longer-exists')
        state = app_module.reconcile_backup_job_state()
        self.assertEqual(state['status'], 'failed')
        self.assertIn('restart', state['message'].lower())

    def test_a_live_job_in_this_process_is_left_alone(self):
        """Positive control: reconcile must not fail every job it sees."""
        self._write_running(app_module.PROCESS_BOOT_ID)
        state = app_module.reconcile_backup_job_state()
        self.assertEqual(state['status'], 'running')

    def test_a_job_that_stopped_heartbeating_is_marked_failed(self):
        stale_timestamp = (
            app_module.get_manila_time()
            - __import__('datetime').timedelta(seconds=app_module.BACKUP_JOB_STALE_SECONDS + 120)
        ).isoformat()
        self._write_running(app_module.PROCESS_BOOT_ID, updated_at=stale_timestamp)
        state = app_module.reconcile_backup_job_state()
        self.assertEqual(state['status'], 'failed')


class BucketBudgetEnumerationTests(unittest.TestCase):
    """Budget exhaustion must say WHICH objects were left out.

    The old behaviour simply `break`ed, so the archive was quietly short and the
    manifest said only "budget exhausted" -- leaving whoever restores it to guess
    what is missing. Enumerating the remainder is the actual fix, and nothing
    asserted it.
    """

    def test_budget_exhaustion_enumerates_the_skipped_objects(self):
        class SlowStorage:
            bucket_configured = True
            bucket_name = 'private-files'

            def test_connection_for_backup(self, *, timeout_seconds):
                return {'ok': True, 'message': 'connected'}

            def iter_objects_for_backup(self, *, timeout_seconds):
                for index in range(40):
                    yield SimpleNamespace(key=f'reports/slow-{index}.pdf', size=4)

            def download_bytes_for_backup(self, key, *, timeout_seconds):
                time.sleep(0.01)
                return b'slow'

        buffer = io.BytesIO()
        with patch.object(app_module, 'file_storage', SlowStorage()), \
                patch.object(app_module, 'managed_storage_roots', return_value=[('reports', None)]):
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
                result = app_module.add_bucket_objects_to_backup_zip(backup_zip, budget_seconds=0.03)

        self.assertTrue(result['budget_exhausted'])
        self.assertTrue(result['skipped'], 'the skipped objects must be enumerated, not just counted')
        self.assertIn('key', result['skipped'][0])
        # Every object is either archived or named as skipped -- none may vanish.
        self.assertEqual(len(result['objects']) + len(result['skipped']), 40)

    def test_an_oversized_object_is_skipped_with_a_warning(self):
        class HugeStorage:
            bucket_configured = True
            bucket_name = 'private-files'

            def test_connection_for_backup(self, *, timeout_seconds):
                return {'ok': True, 'message': 'connected'}

            def iter_objects_for_backup(self, *, timeout_seconds):
                yield SimpleNamespace(key='reports/small.pdf', size=10)
                yield SimpleNamespace(
                    key='reports/enormous.bin',
                    size=app_module.BACKUP_BUCKET_MAX_OBJECT_BYTES + 1,
                )

            def download_bytes_for_backup(self, key, *, timeout_seconds):
                if 'enormous' in key:
                    raise AssertionError('an oversized object must never be downloaded')
                return b'small'

        buffer = io.BytesIO()
        with patch.object(app_module, 'file_storage', HugeStorage()), \
                patch.object(app_module, 'managed_storage_roots', return_value=[('reports', None)]):
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
                result = app_module.add_bucket_objects_to_backup_zip(backup_zip)

        self.assertEqual([item['key'] for item in result['objects']], ['reports/small.pdf'])
        self.assertEqual([item['key'] for item in result['skipped']], ['reports/enormous.bin'])
        self.assertIn('bucket_object_oversize', [error['scope'] for error in result['errors']])


if __name__ == '__main__':
    unittest.main()
