"""Settings -> Templates: registry payload, preview, and the superadmin-only routes."""

import os
import pathlib
import tempfile
import unittest
import uuid

from tests.sw_cache_version import assert_cache_version_at_least

os.environ.setdefault(
    'MEDICAL_SERVICE_TEST_DB',
    str(pathlib.Path(tempfile.gettempdir()) / f'medical_service_email_templates_{uuid.uuid4().hex}.db'),
)

import app as app_module  # noqa: E402


ROOT = pathlib.Path(__file__).resolve().parents[1]
KEY = 'lpr_procurement_subject'
SCENARIO_KEYS = list(app_module.TSR_CLIENT_SUBJECT_TEMPLATE_KEYS)


class EmailTemplateSettingsTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.suffix = uuid.uuid4().hex[:10]
        cls.created_user_ids = []

        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_email_template_setting_table()

            superadmin = app_module.User.query.filter_by(username='jonamar').first()
            if not superadmin:
                superadmin = app_module.User(
                    username='jonamar',
                    password=app_module.generate_password_hash('test-password'),
                    role='superadmin',
                    is_active=True,
                )
                app_module.db.session.add(superadmin)
                app_module.db.session.flush()
                cls.created_user_ids.append(superadmin.id)

            engineer = app_module.User(
                username=f'tmpl_eng_{cls.suffix}',
                password=app_module.generate_password_hash('test-password'),
                role='engineer',
                is_active=True,
            )
            app_module.db.session.add(engineer)
            app_module.db.session.commit()
            cls.created_user_ids.append(engineer.id)
            cls.superadmin_id = superadmin.id
            cls.engineer_id = engineer.id

            cls.saved_rows = {
                row.template_key: (row.template_value, row.is_active)
                for row in app_module.EmailTemplateSetting.query.all()
            }

    @classmethod
    def _restore_rows(cls):
        for row in app_module.EmailTemplateSetting.query.all():
            if row.template_key in cls.saved_rows:
                row.template_value, row.is_active = cls.saved_rows[row.template_key]
        app_module.db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            cls._restore_rows()
            for user_id in cls.created_user_ids:
                user = app_module.db.session.get(app_module.User, user_id)
                if user:
                    app_module.db.session.delete(user)
            app_module.db.session.commit()
            app_module.db.session.remove()

    def setUp(self):
        # Other modules in a full run may clear the table after the once-per-process seeding.
        with self.app.app_context():
            app_module.db.create_all()
            app_module.seed_default_email_templates()

    def tearDown(self):
        with self.app.app_context():
            self._restore_rows()

    def _client(self, user_id=None):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id or self.superadmin_id)
            session['_fresh'] = True
        return client

    def _row(self, template_key=KEY):
        with self.app.app_context():
            row = app_module.EmailTemplateSetting.query.filter_by(template_key=template_key).first()
            return row.template_value, row.is_active

    def _last_log_action(self):
        with self.app.app_context():
            return app_module.ActivityLog.query.order_by(app_module.ActivityLog.id.desc()).first().action

    def test_routes_refuse_a_non_superadmin(self):
        client = self._client(self.engineer_id)
        self.assertEqual(client.get('/settings/email-templates-data').status_code, 403)
        for url in (
            '/settings/email-templates-preview',
            '/settings/email-templates-save',
            f'/settings/email-templates-reset/{KEY}',
            '/settings/email-templates-copy-standard',
            '/settings/email-templates-reset-scenarios',
        ):
            self.assertEqual(client.post(url, json={}).status_code, 403, url)

    def test_data_route_returns_the_registry_in_order_with_display_fields(self):
        data = self._client().get('/settings/email-templates-data').get_json()
        self.assertEqual(
            [item['template_key'] for item in data['templates']],
            list(app_module.EMAIL_TEMPLATE_DEFAULTS),
        )
        for item in data['templates']:
            self.assertTrue(item['section'], item['template_key'])
            self.assertTrue(item['placeholders'], item['template_key'])
            self.assertIn('is_customized', item)
            self.assertIn('updated_by', item)
            self.assertNotIn('{', item['preview'], item['template_key'])

    def test_every_default_is_valid_and_previews_without_placeholders(self):
        for key, cfg in app_module.EMAIL_TEMPLATE_DEFAULTS.items():
            is_valid, error = app_module.validate_managed_template_value(key, cfg['default_template'])
            self.assertTrue(is_valid, f'{key}: {error}')
            self.assertNotIn('{', app_module.preview_managed_template(key, cfg['default_template']), key)

    def test_preview_route_validates_and_writes_nothing(self):
        client = self._client()
        before = self._row()
        bad = client.post('/settings/email-templates-preview', json={
            'template_key': KEY, 'template_value': '[LPR] {nope}',
        }).get_json()
        self.assertIn('{nope}', bad['error'])

        good = client.post('/settings/email-templates-preview', json={
            'template_key': KEY, 'template_value': 'X {lpr_no}',
        }).get_json()
        self.assertEqual(good['preview'], 'X LPR-2026-001')

        filename = client.post('/settings/email-templates-preview', json={
            'template_key': 'tsr_pdf_filename',
            'template_value': 'TSR_{billing_marker}_{client_name}',
            'scenario': 'po',
        }).get_json()
        self.assertEqual(filename['preview'], 'TSR_B_Sample Medical Center.pdf')
        self.assertEqual(self._row(), before)

    def test_save_validates_and_logs_what_changed(self):
        client = self._client()
        save = lambda **body: client.post('/settings/email-templates-save', json=body)
        self.assertEqual(save(template_key='nope', template_value='x').status_code, 400)
        self.assertEqual(save(template_key=KEY, template_value='  ').status_code, 400)
        self.assertEqual(save(template_key=KEY, template_value='x' * 501).status_code, 400)

        old_value = self._row()[0]
        response = save(template_key=KEY, template_value='New {lpr_no}')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['template']['is_customized'])
        self.assertEqual(self._row(), ('New {lpr_no}', True))
        self.assertIn(f'{old_value} → New {{lpr_no}}', self._last_log_action())

        self.assertEqual(save(template_key=KEY, is_active=False).status_code, 200)
        self.assertEqual(self._row(), ('New {lpr_no}', False))
        self.assertTrue(self._last_log_action().startswith('Deactivated managed template'))

    def test_reset_and_scenario_actions(self):
        client = self._client()
        client.post('/settings/email-templates-save', json={'template_key': KEY, 'template_value': 'Changed'})
        client.post('/settings/email-templates-save', json={'template_key': KEY, 'is_active': False})
        self.assertEqual(client.post(f'/settings/email-templates-reset/{KEY}', json={}).status_code, 200)
        self.assertEqual(self._row(), (app_module.EMAIL_TEMPLATE_DEFAULTS[KEY]['default_template'], True))

        client.post('/settings/email-templates-save', json={
            'template_key': 'tsr_client_subject', 'template_value': 'Std {client_name}',
        })
        data = client.post('/settings/email-templates-copy-standard', json={}).get_json()
        self.assertEqual(len(data['templates']), 7)
        for key in SCENARIO_KEYS:
            self.assertEqual(self._row(key), ('Std {client_name}', True), key)

        client.post('/settings/email-templates-reset-scenarios', json={})
        for key in SCENARIO_KEYS:
            self.assertEqual(self._row(key), (app_module.TSR_CLIENT_SUBJECT_DEFAULT_TEMPLATE, True), key)

    def test_converted_subjects_match_the_previous_hardcoded_ones(self):
        render = app_module.render_email_subject_template
        with self.app.app_context():
            self.assertEqual(
                render('reimbursement_paid_subject', {'control_number': 'RB-1'}),
                'Reimbursement Paid - RB-1',
            )
            schedule = {'schedule_date': 'Jul 22, 2026', 'title': 'PM Visit'}
            self.assertEqual(render('schedule_assigned_subject', schedule), 'New Schedule Assigned - Jul 22, 2026 - PM Visit')
            self.assertEqual(render('schedule_deleted_subject', schedule), 'Schedule Deleted - Jul 22, 2026 - PM Visit')
            self.assertEqual(
                render('schedule_updated_subject', {**schedule, 'action': 'Updated'}),
                'Schedule Updated - Jul 22, 2026 - PM Visit',
            )
            self.assertEqual(
                render('changelog_announcement_subject', {'item_count': 1, 'update_word': 'update'}),
                "Medical Service - What's New (1 update)",
            )
            for key, label, ref in (
                ('travel_liquidation_subject', 'TRAVEL LIQUIDATION', 'request_no'),
                ('cash_advance_liquidation_subject', 'CASH ADVANCE LIQUIDATION', 'cash_advance_no'),
            ):
                context = {'liquidation_no': 'L-1', 'employee_name': 'Juan'}
                self.assertEqual(render(key, {**context, ref: 'R-9'}).rstrip(' |'), f'[{label}] L-1 | Juan | R-9')
                self.assertEqual(render(key, {**context, ref: ''}).rstrip(' |'), f'[{label}] L-1 | Juan')

    def test_page_and_app_keep_one_template_list(self):
        settings_source = (ROOT / 'templates' / 'settings.html').read_text(encoding='utf-8')
        app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        for removed in ('emailTemplateSampleContext', 'sanitizeTSRFilenamePreview', 'emailTemplateEscape'):
            self.assertNotIn(removed, settings_source)
        for removed in ('EMAIL_TEMPLATE_ORDER', 'EMAIL_TEMPLATE_ALLOWED_PLACEHOLDERS'):
            self.assertNotIn(removed, app_source)
        for route in ('settings_email_templates_save', 'settings_email_templates_reset'):
            before_route = app_source.split(f'def {route}(')[0].rsplit('@app.route', 1)[1]
            self.assertNotIn('csrf.exempt', before_route)
        self.assertIn('data-settings-section="email-templates"', settings_source)
        assert_cache_version_at_least(self, 234, app_source)


if __name__ == '__main__':
    unittest.main()
