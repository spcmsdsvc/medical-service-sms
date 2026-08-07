import json
import os
import pathlib
import tempfile
import unittest

from sqlalchemy import create_engine


ROOT = pathlib.Path(__file__).resolve().parents[1]

try:
    import app as app_module
except Exception as exc:  # pragma: no cover - source checks still run without app dependencies
    app_module = None
    APP_IMPORT_ERROR = exc
else:
    APP_IMPORT_ERROR = None


class TsrDraftSyncContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.template_source = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')

    def test_server_draft_schema_and_owner_scoped_routes_exist(self):
        self.assertIn('class TsrDraft(db.Model)', self.app_source)
        self.assertIn("db.UniqueConstraint('user_id', 'draft_key'", self.app_source)
        for route in (
            "@app.route('/save_tsr_draft', methods=['POST'])",
            "@app.route('/get_tsr_drafts', methods=['GET'])",
            "@app.route('/delete_tsr_draft', methods=['POST'])",
        ):
            self.assertIn(route, self.app_source)
        route = self.app_source.split("@app.route('/delete_tsr_draft'")[1].split("@app.route('/offline_tsr_sync_ping'")[0]
        self.assertIn("filter_by(\n        user_id=getattr(current_user, 'id', None),", route)

    def test_server_projection_removes_file_values_but_keeps_typed_data(self):
        if app_module is None:
            self.skipTest(f'app dependencies unavailable: {APP_IMPORT_ERROR}')
        projected = app_module.project_tsr_draft_payload_for_server({
            'tsr-complaint': 'Power issue',
            'signatures': {'serviced': 'data:image/png;base64,signature'},
            'attachments': [{
                'name': 'receipt.png',
                'blob': 'browser-only-blob',
                'data_url': 'data:image/png;base64,large',
                'blob_id': 'draft-attachment-1',
            }],
        })
        serialized = json.dumps(projected)
        self.assertEqual(projected['tsr-complaint'], 'Power issue')
        self.assertIn('data:image/png;base64,signature', serialized)
        self.assertNotIn('browser-only-blob', serialized)
        self.assertNotIn('data:image/png;base64,large', serialized)
        self.assertIn('draft-attachment-1', serialized)

    def test_stale_device_timestamp_is_ignored(self):
        if app_module is None:
            self.skipTest(f'app dependencies unavailable: {APP_IMPORT_ERROR}')
        newer = app_module.parse_tsr_draft_device_timestamp('2026-08-07T08:00:00+00:00')
        older = app_module.parse_tsr_draft_device_timestamp('2026-08-07T07:59:59+00:00')
        self.assertIsNotNone(newer)
        self.assertLess(older, newer)
        self.assertIn('stale_ignored', self.app_source)

    def test_optional_server_metadata_does_not_slice_none(self):
        if app_module is None:
            self.skipTest(f'app dependencies unavailable: {APP_IMPORT_ERROR}')
        self.assertIsNone(app_module.tsr_draft_text(None, 40))
        self.assertEqual(app_module.tsr_draft_text('  schedule-17  ', 12), 'schedule-17')

    def test_browser_wiring_is_local_first_and_server_backed(self):
        for marker in (
            "navigator.storage.persist",
            "'/save_tsr_draft'",
            "'/get_tsr_drafts'",
            "'/delete_tsr_draft'",
            'STANDALONE_TSR_SERVER_DRAFT_DEBOUNCE_MS',
            'mergeServerStandaloneTSRDrafts',
            'server_sync_error',
            'Storage Persistence',
        ):
            self.assertIn(marker, self.template_source)
        self.assertIn('saveStandaloneTSRDraftToIndexedDB(data)', self.template_source)
        self.assertIn("serverSync:'immediate'", self.template_source)
        self.assertIn('Supporting files remain local to this device', self.app_source)

    def test_service_worker_cache_is_bumped_for_server_drafts(self):
        self.assertIn('medical-service-pwa-offline-navigation-v80-tsr-server-drafts', self.app_source)
        self.assertIn("'/offline-tsr',", self.app_source)


@unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
class TsrDraftRouteTests(unittest.TestCase):
    def test_owner_isolation_upsert_stale_and_delete_scope(self):
        fd, database_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        extension = None
        original_engine = None
        original_ready = None
        test_engine = None
        original_csrf = None
        try:
            with app_module.app.app_context():
                extension = app_module.app.extensions['sqlalchemy']
                engines = extension._app_engines[app_module.app]
                original_engine = engines[None]
                original_ready = app_module._tsr_draft_table_ready
                original_csrf = app_module.app.config.get('WTF_CSRF_ENABLED')
                app_module.app.config['WTF_CSRF_ENABLED'] = False
                test_engine = create_engine(f"sqlite:///{database_path.replace(os.sep, '/')}")
                engines[None] = test_engine
                app_module._tsr_draft_table_ready = False
                app_module.db.session.remove()
                app_module.db.create_all()
                app_module.ensure_tsr_draft_schema()
                user_one = app_module.User(username='draft-sync-owner-one', password='test-only', role='engineer', is_active=True)
                user_two = app_module.User(username='draft-sync-owner-two', password='test-only', role='engineer', is_active=True)
                app_module.db.session.add_all([user_one, user_two])
                app_module.db.session.commit()
                user_one_id = user_one.id
                user_two_id = user_two.id

            payload = {
                'draft_key': 'draft-owner-one',
                'device_updated_at': '2026-08-07T08:00:00+00:00',
                'schedule_id': '17',
                'payload': {'tsr-complaint': 'newer value', 'attachments': []},
            }
            client_one = app_module.app.test_client()
            client_two = app_module.app.test_client()
            with client_one.session_transaction() as session:
                session['_user_id'] = str(user_one_id)
                session['_fresh'] = True
            with client_two.session_transaction() as session:
                session['_user_id'] = str(user_two_id)
                session['_fresh'] = True

            first = client_one.post('/save_tsr_draft', json=payload)
            self.assertEqual(first.status_code, 200)
            second = client_one.post('/save_tsr_draft', json=dict(payload, payload={'tsr-complaint': 'older value'}, device_updated_at='2026-08-07T07:00:00+00:00'))
            self.assertEqual(second.status_code, 200)
            self.assertTrue(second.get_json()['stale_ignored'])
            self.assertEqual(second.get_json()['draft']['payload']['tsr-complaint'], 'newer value')

            self.assertEqual(client_two.get('/get_tsr_drafts').get_json()['drafts'], [])
            self.assertEqual(client_two.post('/delete_tsr_draft', json={'draft_key': 'draft-owner-one'}).status_code, 404)
            self.assertEqual(client_one.post('/delete_tsr_draft', json={'draft_key': 'draft-owner-one'}).status_code, 200)
            self.assertEqual(client_one.get('/get_tsr_drafts').get_json()['drafts'], [])
        finally:
            if extension is not None and app_module is not None:
                with app_module.app.app_context():
                    app_module.db.session.remove()
                    if original_engine is not None:
                        extension._app_engines[app_module.app][None] = original_engine
                    if original_ready is not None:
                        app_module._tsr_draft_table_ready = original_ready
                    if original_csrf is not None:
                        app_module.app.config['WTF_CSRF_ENABLED'] = original_csrf
            if test_engine is not None:
                test_engine.dispose()
            if database_path and os.path.exists(database_path):
                os.unlink(database_path)


if __name__ == '__main__':
    unittest.main()
