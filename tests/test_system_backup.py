import io
import json
import os
import pathlib
import tempfile
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
                    patch.object(app_module, 'get_backup_upload_roots', return_value=[]), \
                    patch.object(app_module, 'get_backup_source_paths', return_value=[]):
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


if __name__ == '__main__':
    unittest.main()
