"""Focused contracts and isolated route checks for the TSR/client package."""

import json
import os
import pathlib
import tempfile
import unittest
from contextlib import contextmanager

from sqlalchemy import create_engine

from tests.sw_cache_version import assert_cache_version_at_least


ROOT = pathlib.Path(__file__).resolve().parents[1]

try:
    import app as app_module
except Exception as exc:  # pragma: no cover - source contracts still run without deps
    app_module = None
    APP_IMPORT_ERROR = exc
else:
    APP_IMPORT_ERROR = None


class TsrAutosaveClientGroupSourceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.tsr_source = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')
        cls.calibration_source = (ROOT / 'static' / 'js' / 'app-calibration-report.js').read_text(encoding='utf-8')
        cls.clients_source = (ROOT / 'templates' / 'clients.html').read_text(encoding='utf-8')

    def test_saved_versions_identify_active_calibration_reports_independently(self):
        self.assertIn('standaloneTSRDraftVersionHasCalibrationReport', self.tsr_source)
        self.assertIn('Calibration Report saved with this draft', self.tsr_source)
        self.assertIn('standaloneTSRDraftVersionHasCalibrationReport(version)', self.tsr_source)
        self.assertIn("status !== 'not_started'", self.tsr_source)

    def test_autosave_uses_900_ms_and_calibration_editor_exposes_save_state(self):
        self.assertIn('const STANDALONE_TSR_SERVER_DRAFT_DEBOUNCE_MS = 900;', self.tsr_source)
        self.assertIn('id="calibration-report-save-status"', self.tsr_source)
        self.assertIn('setSaveStatusFromTSR', self.calibration_source)
        self.assertIn('scheduleDraftSave()', self.calibration_source)
        for state in ('unsaved', 'saving', 'device-saved', 'account-backed-up', 'conflict', 'failed'):
            self.assertIn("'{}'".format(state), self.calibration_source)
        self.assertIn("serverSync:'none'", self.tsr_source)

    def test_client_group_contract_and_hr_shape(self):
        self.assertIn('group_name = db.Column(db.String(100), nullable=True)', self.app_source)
        self.assertIn('ensure_client_group_column', self.app_source)
        self.assertIn("group_name = clean_str(payload.get('group_name')) or None", self.app_source)
        self.assertIn("'group_name': clean_str(getattr(c, 'group_name', None)) or None", self.app_source)
        self.assertIn("{'id': client.id, 'name': client.name or ''}", self.app_source)
        self.assertIn('id="c-group"', self.clients_source)
        self.assertIn('id="c-group-new"', self.clients_source)
        self.assertIn('id="s-group"', self.clients_source)
        self.assertIn('group_name', self.clients_source)

    def test_client_group_picker_exposes_existing_and_new_groups(self):
        self.assertIn('id="c-group"', self.clients_source)
        self.assertIn('id="c-group-new-wrap"', self.clients_source)
        self.assertIn('id="c-group-new"', self.clients_source)
        self.assertIn('CLIENT_GROUP_ADD_NEW_VALUE', self.clients_source)
        self.assertIn('refreshClientGroupOptions', self.clients_source)
        self.assertIn('setClientGroupSelection', self.clients_source)
        self.assertIn('getSelectedClientGroupName', self.clients_source)
        self.assertIn('Please enter a new group name.', self.clients_source)
        self.assertNotIn('<datalist id="client-group-list"', self.clients_source)

    def test_cache_and_release_are_registered(self):
        assert_cache_version_at_least(self, 199, self.app_source)
        releases = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))['releases']
        release = next(item for item in releases if item['release_key'] == '2026-09-26-tsr-autosave-client-groups')
        self.assertEqual(release['release_date'], '2026-09-26')


@unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
class ClientGroupRouteTests(unittest.TestCase):
    @contextmanager
    def isolated_database(self):
        fd, database_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        extension = None
        original_engine = None
        original_group_ready = None
        original_contact_ready = None
        test_engine = None
        original_csrf = None
        added_superadmin_username = None
        try:
            with app_module.app.app_context():
                extension = app_module.app.extensions['sqlalchemy']
                engines = extension._app_engines[app_module.app]
                original_engine = engines[None]
                original_group_ready = getattr(app_module, '_client_group_column_ready', False)
                original_contact_ready = getattr(app_module, '_contact_designation_column_ready', False)
                original_csrf = app_module.app.config.get('WTF_CSRF_ENABLED')
                app_module.app.config['WTF_CSRF_ENABLED'] = False
                test_engine = create_engine(f"sqlite:///{database_path.replace(os.sep, '/')}")
                engines[None] = test_engine
                app_module._client_group_column_ready = False
                app_module._contact_designation_column_ready = False
                app_module.db.session.remove()
                app_module.db.create_all()
                app_module.ensure_client_group_column()
                suffix = pathlib.Path(database_path).stem[-10:]
                admin = app_module.User(
                    username=f'client-group-admin-{suffix}', password='test-only', role='superadmin', is_active=True
                )
                engineer = app_module.User(
                    username=f'client-group-engineer-{suffix}', password='test-only', role='engineer', is_active=True
                )
                hr = app_module.User(
                    username=f'client-group-hr-{suffix}', password='test-only', role='staff', is_active=True,
                    hr_schedule_view=True,
                )
                app_module.db.session.add_all([admin, engineer, hr])
                app_module.db.session.commit()
                added_superadmin_username = admin.username.lower()
                app_module.SUPERADMIN_USERNAMES.add(added_superadmin_username)
                user_ids = {'admin': admin.id, 'engineer': engineer.id, 'hr': hr.id}
            clients = {}
            for label, user_id in user_ids.items():
                client = app_module.app.test_client()
                with client.session_transaction() as session:
                    session['_user_id'] = str(user_id)
                    session['_fresh'] = True
                clients[label] = client
            yield clients
        finally:
            if extension is not None:
                with app_module.app.app_context():
                    app_module.db.session.remove()
                    if original_engine is not None:
                        extension._app_engines[app_module.app][None] = original_engine
                    app_module._client_group_column_ready = original_group_ready
                    app_module._contact_designation_column_ready = original_contact_ready
                    if added_superadmin_username:
                        app_module.SUPERADMIN_USERNAMES.discard(added_superadmin_username)
                    if original_csrf is not None:
                        app_module.app.config['WTF_CSRF_ENABLED'] = original_csrf
            if test_engine is not None:
                test_engine.dispose()
            if database_path and os.path.exists(database_path):
                os.unlink(database_path)

    def test_admin_group_crud_non_hr_payload_and_hr_shape(self):
        with self.isolated_database() as clients:
            created = clients['admin'].post('/add_client', json={
                'name': 'Grouped Client', 'address': 'A', 'group_name': 'North Clinics',
            })
            self.assertEqual(created.status_code, 200)
            with app_module.app.app_context():
                client = app_module.Client.query.filter_by(name='Grouped Client').first()
                self.assertEqual(client.group_name, 'North Clinics')
                client_id = client.id

            payload = next(row for row in clients['admin'].get('/get_clients').get_json() if row['id'] == client_id)
            self.assertEqual(payload['group_name'], 'North Clinics')

            updated = clients['admin'].put(f'/update_client/{client_id}', json={
                'name': 'Grouped Client', 'address': 'A', 'group_name': '',
            })
            self.assertEqual(updated.status_code, 200)
            with app_module.app.app_context():
                self.assertIsNone(app_module.db.session.get(app_module.Client, client_id).group_name)

            hr_payload = next(row for row in clients['hr'].get('/get_clients').get_json() if row['id'] == client_id)
            self.assertEqual(set(hr_payload), {'id', 'name'})

    def test_contact_only_update_cannot_change_group(self):
        with self.isolated_database() as clients:
            with app_module.app.app_context():
                record = app_module.Client(name='Protected Group Client', group_name='Keep This')
                app_module.db.session.add(record)
                app_module.db.session.commit()
                client_id = record.id

            updated = clients['engineer'].put(f'/update_client/{client_id}', json={
                'name': 'Attempted Rename', 'address': 'Attempted Address', 'group_name': 'Hacked',
                'cp1': 'Field Contact',
            })
            self.assertEqual(updated.status_code, 200)
            with app_module.app.app_context():
                record = app_module.db.session.get(app_module.Client, client_id)
                self.assertEqual(record.group_name, 'Keep This')
                self.assertEqual(record.name, 'Protected Group Client')


if __name__ == '__main__':
    unittest.main()
