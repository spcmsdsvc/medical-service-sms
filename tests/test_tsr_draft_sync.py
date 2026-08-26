import json
import os
import pathlib
import tempfile
import unittest

from sqlalchemy import create_engine

from tests.sw_cache_version import assert_cache_version_at_least


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
        cls.calibration_report_source = (ROOT / 'static' / 'js' / 'app-calibration-report.js').read_text(encoding='utf-8')

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

    def test_calibration_report_state_survives_server_projection_without_browser_blob(self):
        if app_module is None:
            self.skipTest(f'app dependencies unavailable: {APP_IMPORT_ERROR}')
        projected = app_module.project_tsr_draft_payload_for_server({
            'calibration_report': {
                'schema_version': 2,
                'status': 'draft',
                'machine': {'model': 'MobileDaRt', 'serial_number': 'SN-17'},
                'signature': {'image': 'data:image/png;base64,signature'},
                'generated': {'blob_id': 'calibration-report-abcd1234'},
            }
        })
        self.assertEqual(projected['calibration_report']['machine']['model'], 'MobileDaRt')
        self.assertIn('calibration-report-abcd1234', json.dumps(projected))
        self.assertEqual(projected['calibration_report']['signature']['image'], 'data:image/png;base64,signature')

    def test_calibration_report_cleanup_references_project_without_blob_bytes_or_readiness(self):
        if app_module is None:
            self.skipTest(f'app dependencies unavailable: {APP_IMPORT_ERROR}')
        projected = app_module.project_tsr_draft_payload_for_server({
            'calibration_report': {
                'schema_version': 2,
                'status': 'draft',
                'generated': {'fingerprint': '', 'attachment_id': '', 'blob_id': ''},
                'generated_cleanup': {'blob_ids': ['calibration-report-old-1'], 'blob': 'browser-only-blob'},
            }
        })
        report = projected['calibration_report']
        self.assertEqual(report['generated_cleanup']['blob_ids'], ['calibration-report-old-1'])
        self.assertNotIn('browser-only-blob', json.dumps(projected))
        self.assertFalse(report['generated']['attachment_id'])
        self.assertIn('generated_cleanup', self.calibration_report_source)
        self.assertIn('hasGeneratedMetadata', self.calibration_report_source)

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
        """A floor, never a pinned version.

        This pinned the exact v80 string, so the next required bump failed the suite -- the
        anti-pattern section 6 of pending-work.md records this repository having already had
        to undo. The bump is a mandatory step for any APP_SHELL change; a test that punishes
        it is a test that trains people to skip it.
        """
        assert_cache_version_at_least(self, 80, self.app_source)
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


@unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
class TsrDraftAccessMatchesThePageGateTests(unittest.TestCase):
    """The page gate and the three endpoint gates must admit the same accounts.

    The original implementation gated the routes on
    `is_admin_authorized() or role == 'engineer'` while `/offline-tsr` admitted
    everyone except approver-only users, so five account shapes could open
    Create TSR and write a draft that was silently never backed up. This is the
    fifth time a page/endpoint gate mismatch has reached main, and every previous
    one was found the same way: build one account of each shape and call the
    route. See pending-work.md bug 1z.
    """

    # Each entry is the account shape from the bug's reproduction table. The
    # approver-only row is the positive control: it is the one shape that must
    # still be refused, so a gate that simply returned True everywhere fails.
    # (label, columns, may_back_up, expected endpoint status when refused)
    #
    # The refused accounts are refused by TWO different mechanisms, and the
    # status tells them apart: `can_back_up_tsr_drafts()` answers 403, while the
    # inventory-only and HR-only before_request fences redirect. Asserting the
    # exact status keeps those distinct, so a fence quietly disappearing cannot
    # be absorbed as "still refused somehow".
    ACCOUNT_SHAPES = (
        ('engineer', dict(role='engineer'), True, None),
        ('plain-staff', dict(role='staff'), True, None),
        ('scheduler', dict(role='staff', schedule_admin_access=True), True, None),
        ('personnel-admin', dict(role='staff', personnel_admin_access=True), True, None),
        ('reports-admin', dict(role='staff', reports_admin_access=True), True, None),
        ('stock-inventory', dict(role='staff', can_manage_stock_inventory=True), True, None),
        # The one shape this gate itself must refuse.
        ('approver-only', dict(role='approver', can_approve_requests=True), False, 403),
        # Fenced off from /offline-tsr entirely by their own before_request
        # guards, not by this gate. Listed so the boundary is pinned: if either
        # fence is relaxed, this test forces a deliberate decision about draft
        # backup rather than silently recreating bug 1z for a new account shape.
        ('stock-inventory-only', dict(role='staff', can_manage_stock_inventory=True, stock_inventory_only=True), False, 302),
        ('hr-schedule-only', dict(role='staff', hr_schedule_view=True), False, 302),
    )

    def test_every_account_that_can_open_create_tsr_can_back_a_draft_up(self):
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

                user_ids = {}
                for label, columns, _, _refused_status in self.ACCOUNT_SHAPES:
                    user = app_module.User(
                        username=f'draft-gate-{label}',
                        password='test-only',
                        is_active=True,
                        **columns,
                    )
                    app_module.db.session.add(user)
                    app_module.db.session.commit()
                    user_ids[label] = user.id

            for label, _, may_back_up, refused_status in self.ACCOUNT_SHAPES:
                with self.subTest(account=label):
                    client = app_module.app.test_client()
                    with client.session_transaction() as session:
                        session['_user_id'] = str(user_ids[label])
                        session['_fresh'] = True

                    page = client.get('/offline-tsr')
                    save = client.post('/save_tsr_draft', json={
                        'draft_key': f'draft-gate-{label}',
                        'device_updated_at': '2026-08-08T08:00:00+00:00',
                        'payload': {'tsr-complaint': 'gate check', 'attachments': []},
                    })
                    fetch = client.get('/get_tsr_drafts')

                    if may_back_up:
                        # The page opening while the endpoints refuse IS the bug.
                        self.assertEqual(page.status_code, 200, f'{label} cannot open Create TSR')
                        self.assertEqual(save.status_code, 200, f'{label} can write a draft that is never backed up')
                        self.assertEqual(fetch.status_code, 200, f'{label} cannot recover a backed-up draft')
                        keys = [row['draft_key'] for row in fetch.get_json()['drafts']]
                        self.assertIn(f'draft-gate-{label}', keys, f'{label} draft did not reach the server')
                    else:
                        self.assertEqual(page.status_code, 302, f'{label} should be redirected away from Create TSR')
                        self.assertEqual(save.status_code, refused_status)
                        self.assertEqual(fetch.status_code, refused_status)
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

    def test_a_permanent_refusal_is_not_described_as_temporary(self):
        """The 403 message must not tell the user to wait for a retry.

        This is the half of bug 1z that kept it unreported: the user was told
        the backup was "temporarily unavailable and will retry", so nobody
        raised it.
        """
        source = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')
        self.assertIn('function standaloneTSRServerBackupFailureText(', source)
        self.assertIn('standaloneTSRServerBackupFailureText(result.server_sync_error)', source)
        # The status is what separates the three outcomes; without branching on
        # it the function is just the old single message with extra steps.
        self.assertIn("error?.httpStatus === 403", source)
        self.assertIn("error?.httpStatus === 401", source)
        # The temporary wording must survive for the case where it is true.
        self.assertIn('temporarily unavailable and will retry', source)


if __name__ == '__main__':
    unittest.main()
