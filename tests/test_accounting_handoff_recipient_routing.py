"""Focused coverage for branch-aware Accounting Handoff CC recipients."""

import os
import pathlib
import tempfile
import unittest
import uuid
from types import SimpleNamespace


os.environ.setdefault(
    'MEDICAL_SERVICE_TEST_DB',
    str(pathlib.Path(tempfile.gettempdir()) / f'medical_service_accounting_cc_{uuid.uuid4().hex}.db'),
)

import app as app_module  # noqa: E402


ROOT = pathlib.Path(__file__).resolve().parents[1]


class AccountingHandoffRecipientRoutingTests(unittest.TestCase):
    """Keep the shared handoff CC split narrow, additive, and branch-safe."""

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.suffix = uuid.uuid4().hex[:10]
        cls.created_user_ids = []
        cls.created_engineer_ids = []
        cls.created_recipient_ids = []

        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_email_recipient_setting_table()

            def create_user(label, branch, email):
                user = app_module.User(
                    username=f'acctcc_{label}_{cls.suffix}',
                    password=app_module.generate_password_hash('test-password'),
                    role='engineer',
                    is_active=True,
                )
                app_module.db.session.add(user)
                app_module.db.session.flush()
                engineer = app_module.Engineer(
                    user_id=user.id,
                    employee_id=f'ACC-{cls.suffix}-{len(cls.created_engineer_ids) + 1}',
                    name=f'Accounting CC {label}',
                    initials=label[:3].upper(),
                    email=email,
                    branch=branch,
                )
                app_module.db.session.add(engineer)
                app_module.db.session.flush()
                cls.created_user_ids.append(user.id)
                cls.created_engineer_ids.append(engineer.id)
                return user

            cls.user_ids = {}
            cls.requester_emails = {}
            for label, branch in (
                ('manila', 'Manila'),
                ('main', 'Main'),
                ('bc01', 'BC01'),
                ('blank', ''),
                ('unknown', 'Quezon City'),
                ('cebu', 'Cebu'),
                ('davao', 'Davao'),
                ('bc02', 'BC02'),
                ('bc03', 'BC03'),
                ('cebu_label', 'Cebu Service Center'),
                ('davao_label', 'Davao Office'),
            ):
                email = f'requester-{label}-{cls.suffix}@example.com'
                user = create_user(label, branch, email)
                cls.user_ids[label] = user.id
                cls.requester_emails[label] = email

            cls.manila_email = f'manila-cc-{cls.suffix}@example.com'
            cls.regional_email = f'regional-cc-{cls.suffix}@example.com'
            cls.inactive_manila_email = f'inactive-manila-{cls.suffix}@example.com'
            cls.inactive_regional_email = f'inactive-regional-{cls.suffix}@example.com'
            rows = [
                app_module.EmailRecipientSetting(
                    group_key='accounting_handoff_cc',
                    email=cls.manila_email,
                    display_name='Manila CC',
                    sort_order=10,
                    is_active=True,
                ),
                app_module.EmailRecipientSetting(
                    group_key='accounting_handoff_cc',
                    email=cls.inactive_manila_email,
                    display_name='Inactive Manila CC',
                    sort_order=20,
                    is_active=False,
                ),
                app_module.EmailRecipientSetting(
                    group_key='accounting_handoff_cc_cebu_davao',
                    email=cls.regional_email,
                    display_name='Cebu/Davao CC',
                    sort_order=10,
                    is_active=True,
                ),
                app_module.EmailRecipientSetting(
                    group_key='accounting_handoff_cc_cebu_davao',
                    email=cls.inactive_regional_email,
                    display_name='Inactive Cebu/Davao CC',
                    sort_order=20,
                    is_active=False,
                ),
            ]
            app_module.db.session.add_all(rows)
            app_module.db.session.flush()
            cls.created_recipient_ids.extend(row.id for row in rows)

            cls.superadmin = app_module.User.query.filter_by(username='jonamar').first()
            if not cls.superadmin:
                cls.superadmin = app_module.User(
                    username='jonamar',
                    password=app_module.generate_password_hash('test-password'),
                    role='superadmin',
                    is_active=True,
                )
                app_module.db.session.add(cls.superadmin)
                app_module.db.session.flush()
                cls.created_user_ids.append(cls.superadmin.id)

            app_module.db.session.commit()
            cls.superadmin_id = cls.superadmin.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            for recipient_id in reversed(cls.created_recipient_ids):
                recipient = app_module.db.session.get(app_module.EmailRecipientSetting, recipient_id)
                if recipient:
                    app_module.db.session.delete(recipient)
            for engineer_id in reversed(cls.created_engineer_ids):
                engineer = app_module.db.session.get(app_module.Engineer, engineer_id)
                if engineer:
                    app_module.db.session.delete(engineer)
            for user_id in reversed(cls.created_user_ids):
                user = app_module.db.session.get(app_module.User, user_id)
                if user:
                    app_module.db.session.delete(user)
            app_module.db.session.commit()
            app_module.db.session.remove()

    def _record(self, label):
        return SimpleNamespace(user_id=self.user_ids[label])

    def _admin_client(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.superadmin_id)
            session['_fresh'] = True
        return client

    def test_registry_keeps_manila_key_and_adds_adjacent_regional_key(self):
        groups = app_module.get_email_recipient_groups_payload()
        keys = [group['key'] for group in groups]
        manila_key = 'accounting_handoff_cc'
        regional_key = 'accounting_handoff_cc_cebu_davao'
        self.assertIn(manila_key, keys)
        self.assertIn(regional_key, keys)
        self.assertEqual(
            app_module.EMAIL_RECIPIENT_GROUPS[manila_key]['label'],
            'Accounting Handoff CC - Manila',
        )
        self.assertEqual(
            app_module.EMAIL_RECIPIENT_GROUPS[regional_key]['label'],
            'Accounting Handoff CC - Cebu/Davao',
        )
        self.assertEqual(keys.index(regional_key), keys.index(manila_key) + 1)
        self.assertEqual(app_module.normalize_email_recipient_group(regional_key), regional_key)
        self.assertEqual(app_module.normalize_email_recipient_group('not_a_group'), '')

    def test_settings_fallback_identifies_both_accounting_cc_lists(self):
        settings_source = (ROOT / 'templates' / 'settings.html').read_text(encoding='utf-8')
        for expected in (
            "key: 'accounting_handoff_cc'",
            "label: 'Accounting Handoff CC - Manila'",
            "key: 'accounting_handoff_cc_cebu_davao'",
            "label: 'Accounting Handoff CC - Cebu/Davao'",
            'accounting_handoff_cc_cebu_davao: \'Used by Cebu/Davao Accounting handoffs\'',
        ):
            self.assertIn(expected, settings_source)
        self.assertLess(
            settings_source.index("key: 'accounting_handoff_cc'"),
            settings_source.index("key: 'accounting_handoff_cc_cebu_davao'"),
        )

    def test_requester_branch_selects_only_the_matching_shared_cc_group(self):
        regional_labels = {'cebu', 'davao', 'bc02', 'bc03', 'cebu_label', 'davao_label'}
        default_labels = {'manila', 'main', 'bc01', 'blank', 'unknown'}
        with self.app.app_context():
            for label in sorted(regional_labels | default_labels):
                with self.subTest(label=label):
                    copy_emails = app_module.get_requester_accounting_copy_emails(
                        self._record(label),
                        primary_emails=['primary-recipient@example.com'],
                    )
                    requester_email = self.requester_emails[label]
                    self.assertIn(requester_email, copy_emails)
                    if label in regional_labels:
                        self.assertIn(self.regional_email, copy_emails)
                        self.assertNotIn(self.manila_email, copy_emails)
                        self.assertNotIn(self.inactive_regional_email, copy_emails)
                    else:
                        self.assertIn(self.manila_email, copy_emails)
                        self.assertNotIn(self.regional_email, copy_emails)
                        self.assertNotIn(self.inactive_manila_email, copy_emails)

    def test_requester_and_primary_recipients_are_case_insensitively_deduplicated(self):
        with self.app.app_context():
            user = app_module.db.session.get(app_module.User, self.user_ids['manila'])
            original_email = user.engineer_profile.email
            user.engineer_profile.email = self.manila_email.upper()
            try:
                copy_emails = app_module.get_requester_accounting_copy_emails(
                    self._record('manila'),
                    primary_emails=['PRIMARY-RECIPIENT@example.com', self.manila_email.upper()],
                )
            finally:
                user.engineer_profile.email = original_email
        lowered = [email.lower() for email in copy_emails]
        self.assertNotIn(self.manila_email.lower(), lowered)
        self.assertEqual(len(lowered), len(set(lowered)))
        self.assertNotIn('primary-recipient@example.com', lowered)

    def test_settings_payload_order_and_save_accept_the_new_key(self):
        client = self._admin_client()
        response = client.get('/settings/email-recipients-data')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        keys = [group['key'] for group in payload['groups']]
        self.assertEqual(
            keys[keys.index('accounting_handoff_cc') + 1],
            'accounting_handoff_cc_cebu_davao',
        )

        saved_email = f'saved-regional-{self.suffix}@example.com'
        response = client.post(
            '/settings/email-recipients-save',
            json={
                'group_key': 'accounting_handoff_cc_cebu_davao',
                'email': saved_email,
                'display_name': 'Saved Cebu/Davao CC',
                'sort_order': 30,
                'is_active': True,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['success'])
        with self.app.app_context():
            saved = app_module.EmailRecipientSetting.query.filter_by(email=saved_email).one()
            self.assertEqual(saved.group_key, 'accounting_handoff_cc_cebu_davao')
            app_module.db.session.delete(saved)
            app_module.db.session.commit()

    def test_settings_page_renders_the_split_metadata(self):
        response = self._admin_client().get('/settings')
        self.assertEqual(response.status_code, 200)
        rendered = response.get_data(as_text=True)
        self.assertIn('Accounting Handoff CC - Manila', rendered)
        self.assertIn('Accounting Handoff CC - Cebu/Davao', rendered)
        self.assertIn('accounting_handoff_cc_cebu_davao', rendered)

    def test_all_accounting_handoff_callers_still_converge_on_shared_helper(self):
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        self.assertEqual(source.count('get_requester_accounting_copy_emails('), 6)
        self.assertEqual(source.count("get_active_email_recipients_by_group('accounting_handoff_cc')"), 0)


if __name__ == '__main__':
    unittest.main()
