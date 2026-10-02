"""Settings -> Email Recipients: registry payload and the superadmin-only routes."""

import os
import pathlib
import tempfile
import unittest
import uuid

from tests.sw_cache_version import assert_cache_version_at_least

os.environ.setdefault(
    'MEDICAL_SERVICE_TEST_DB',
    str(pathlib.Path(tempfile.gettempdir()) / f'medical_service_email_recipients_{uuid.uuid4().hex}.db'),
)

import app as app_module  # noqa: E402


ROOT = pathlib.Path(__file__).resolve().parents[1]
GROUP = 'lpr_procurement'
OTHER_GROUP = 'leave_request_hr'


class EmailRecipientSettingsTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.suffix = uuid.uuid4().hex[:10]
        cls.created_user_ids = []

        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_email_recipient_setting_table()

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
                username=f'recip_eng_{cls.suffix}',
                password=app_module.generate_password_hash('test-password'),
                role='engineer',
                is_active=True,
            )
            app_module.db.session.add(engineer)
            app_module.db.session.commit()
            cls.created_user_ids.append(engineer.id)
            cls.superadmin_id = superadmin.id
            cls.engineer_id = engineer.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            cls._delete_test_recipients()
            for user_id in cls.created_user_ids:
                user = app_module.db.session.get(app_module.User, user_id)
                if user:
                    app_module.db.session.delete(user)
            app_module.db.session.commit()
            app_module.db.session.remove()

    @classmethod
    def _delete_test_recipients(cls):
        app_module.EmailRecipientSetting.query.filter(
            app_module.EmailRecipientSetting.email.like(f'%{cls.suffix}@example.com')
        ).delete(synchronize_session=False)
        app_module.db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            self._delete_test_recipients()

    def _client(self, user_id=None):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id or self.superadmin_id)
            session['_fresh'] = True
        return client

    def _email(self, label):
        return f'{label}-{self.suffix}@example.com'

    def _rows(self, email, group_key=None):
        with self.app.app_context():
            query = app_module.EmailRecipientSetting.query.filter_by(email=email)
            if group_key:
                query = query.filter_by(group_key=group_key)
            return [(row.id, row.group_key, row.is_active, row.display_name) for row in query.all()]

    def _add(self, label, group_key=GROUP, **extra):
        response = self._client().post(
            '/settings/email-recipients-save',
            json={'group_key': group_key, 'email': self._email(label), **extra},
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()['recipient']['id']

    def _last_log_action(self):
        with self.app.app_context():
            return app_module.ActivityLog.query.order_by(app_module.ActivityLog.id.desc()).first().action

    def test_routes_refuse_a_non_superadmin(self):
        client = self._client(self.engineer_id)
        self.assertEqual(client.get('/settings/email-recipients-data').status_code, 403)
        for url in (
            '/settings/email-recipients-save',
            '/settings/email-recipients-bulk-add',
            '/settings/email-recipients-copy/1',
            '/settings/email-recipients-delete/1',
        ):
            self.assertEqual(client.post(url, json={}).status_code, 403, url)

    def test_data_route_returns_the_registry_in_order_with_display_fields(self):
        payload = self._client().get('/settings/email-recipients-data').get_json()
        self.assertEqual(
            [group['key'] for group in payload['groups']],
            list(app_module.EMAIL_RECIPIENT_GROUPS),
        )
        for group in payload['groups']:
            self.assertTrue(group['label'] and group['section'] and group['usage'] and group['description'])
            self.assertIn(group['kind'], ('primary', 'cc'))

    def test_save_validates_and_logs_what_changed(self):
        client = self._client()
        bad_email = client.post('/settings/email-recipients-save', json={'group_key': GROUP, 'email': 'nope'})
        self.assertEqual(bad_email.status_code, 400)
        bad_group = client.post('/settings/email-recipients-save', json={'group_key': 'x', 'email': self._email('a')})
        self.assertEqual(bad_group.status_code, 400)

        recipient_id = self._add('a', display_name='First', sort_order=30)
        self.assertIn('Added email recipient setting', self._last_log_action())

        duplicate = client.post('/settings/email-recipients-save', json={'group_key': GROUP, 'email': self._email('a')})
        self.assertEqual(duplicate.status_code, 400)
        self._add('a', group_key=OTHER_GROUP)

        switched = client.post('/settings/email-recipients-save', json={'id': recipient_id, 'is_active': False})
        self.assertEqual(switched.status_code, 200)
        self.assertIn('Deactivated email recipient setting', self._last_log_action())
        self.assertEqual(self._rows(self._email('a'), GROUP), [(recipient_id, GROUP, False, 'First')])
        with self.app.app_context():
            self.assertEqual(app_module.db.session.get(app_module.EmailRecipientSetting, recipient_id).sort_order, 30)
            self.assertNotIn(self._email('a'), app_module.get_active_email_recipients_by_group(GROUP))

    def test_bulk_add_reports_added_existing_and_invalid(self):
        self._add('old')
        response = self._client().post('/settings/email-recipients-bulk-add', json={
            'group_key': GROUP,
            'emails': f"{self._email('new1')}, {self._email('old')}\nnot-an-email; <{self._email('new2').upper()}>",
            'display_name': 'Team',
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['added'], [self._email('new1'), self._email('new2')])
        self.assertEqual(data['skipped_existing'], [self._email('old')])
        self.assertEqual(data['invalid'], ['not-an-email'])
        self.assertEqual(len(self._rows(self._email('new2'), GROUP)), 1)

        nothing = self._client().post('/settings/email-recipients-bulk-add', json={'group_key': GROUP, 'emails': 'nope'})
        self.assertEqual(nothing.status_code, 400)

    def test_copy_adds_to_other_groups_and_skips_where_present(self):
        recipient_id = self._add('copy', display_name='Copied')
        self._add('copy', group_key=OTHER_GROUP)
        response = self._client().post(
            f'/settings/email-recipients-copy/{recipient_id}',
            json={'group_keys': [OTHER_GROUP, 'travel_accounting', 'not_a_group']},
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['copied'], ['Travel Request Accounting'])
        self.assertEqual(data['skipped_existing'], ['Leave Request HR'])
        copied = self._rows(self._email('copy'), 'travel_accounting')
        self.assertEqual(len(copied), 1)
        self.assertEqual(copied[0][3], 'Copied')

    def test_delete_removes_only_the_one_row(self):
        recipient_id = self._add('gone')
        self._add('gone', group_key=OTHER_GROUP)
        client = self._client()
        self.assertEqual(client.post(f'/settings/email-recipients-delete/{recipient_id}', json={}).status_code, 200)
        self.assertEqual([row[1] for row in self._rows(self._email('gone'))], [OTHER_GROUP])
        self.assertEqual(client.post(f'/settings/email-recipients-delete/{recipient_id}', json={}).status_code, 404)

    def test_page_and_app_keep_one_group_list(self):
        settings_source = (ROOT / 'templates' / 'settings.html').read_text(encoding='utf-8')
        app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        for removed in ('emailRecipientGroupFallbacks', 'emailRecipientUsageLabel', 'email-recipient-order'):
            self.assertNotIn(removed, settings_source)
        for removed in ('EMAIL_RECIPIENT_GROUP_ORDER', 'seed_default_email_recipients'):
            self.assertNotIn(removed, app_source)
        for route in ('settings_email_recipients_save', 'settings_email_recipients_delete'):
            before_route = app_source.split(f'def {route}(')[0].rsplit('@app.route', 1)[1]
            self.assertNotIn('csrf.exempt', before_route)
        assert_cache_version_at_least(self, 233, app_source)


if __name__ == '__main__':
    unittest.main()
