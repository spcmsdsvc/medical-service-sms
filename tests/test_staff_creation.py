"""Coverage for Staff Type and permission-aware Add Personnel creation."""

import os
import pathlib
import tempfile
import unittest
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f'medical_service_staff_creation_{uuid.uuid4().hex}.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402


class StaffCreationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.suffix = uuid.uuid4().hex[:10]
        cls.created_user_ids = []
        cls.created_engineer_ids = []
        cls.owned_base_user_ids = []
        cls.owned_regional_profile = False

        with cls.app.app_context():
            app_module.db.create_all()
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
                cls.owned_base_user_ids.append(cls.superadmin.id)

            cls.regional_admin = app_module.User.query.filter_by(username='kevin').first()
            if not cls.regional_admin:
                cls.regional_admin = app_module.User(
                    username='kevin',
                    password=app_module.generate_password_hash('test-password'),
                    role='regional_admin',
                    is_active=True,
                )
                app_module.db.session.add(cls.regional_admin)
                app_module.db.session.flush()
                cls.owned_base_user_ids.append(cls.regional_admin.id)

            cls.regional_profile = app_module.Engineer.query.filter_by(user_id=cls.regional_admin.id).first()
            if not cls.regional_profile:
                cls.regional_profile = app_module.Engineer(
                    user_id=cls.regional_admin.id,
                    employee_id=app_module.REGIONAL_ADMIN_EMPLOYEE_ID,
                    name='Kevin Regional Admin',
                    initials='KRA',
                    branch='Cebu',
                )
                app_module.db.session.add(cls.regional_profile)
                cls.owned_regional_profile = True
            app_module.db.session.commit()
            cls.superadmin_id = cls.superadmin.id
            cls.regional_admin_id = cls.regional_admin.id
            cls.regional_profile_id = cls.regional_profile.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            for engineer_id in reversed(cls.created_engineer_ids):
                engineer = app_module.db.session.get(app_module.Engineer, engineer_id)
                if engineer:
                    app_module.db.session.delete(engineer)
            regional_profile = app_module.db.session.get(app_module.Engineer, cls.regional_profile_id)
            if regional_profile and cls.owned_regional_profile:
                app_module.db.session.delete(regional_profile)
            for user_id in reversed(cls.created_user_ids + cls.owned_base_user_ids):
                user = app_module.db.session.get(app_module.User, user_id)
                if user:
                    app_module.db.session.delete(user)
            app_module.db.session.commit()
            app_module.db.session.remove()

    @classmethod
    def _client_for(cls, user_id):
        client = cls.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    @classmethod
    def _payload(cls, name, staff_type='engineer', **overrides):
        payload = {
            'staff_type': staff_type,
            'employee_id': f'STAFF-{cls.suffix}-{len(cls.created_user_ids) + 1}',
            'name': name,
            'initials': ''.join(part[0] for part in name.split()).upper()[:5],
            'branch': 'Cebu' if staff_type == 'engineer' else '',
            'phone': '',
            'email': '',
        }
        payload.update(overrides)
        return payload

    def _remember_created_account(self, response):
        body = response.get_json()
        self.assertTrue(body.get('username'))
        with self.app.app_context():
            user = app_module.User.query.filter_by(username=body['username']).first()
            self.assertIsNotNone(user)
            self.created_user_ids.append(user.id)
            return user.id

    def test_superadmin_can_create_engineer_hr_and_approver_accounts(self):
        client = self._client_for(self.superadmin_id)

        engineer_response = client.post('/add_engineer', json=self._payload('Test Engineer'))
        self.assertEqual(engineer_response.status_code, 200)
        engineer_user_id = self._remember_created_account(engineer_response)
        self.assertEqual(engineer_response.get_json()['staff_type'], 'engineer')
        with self.app.app_context():
            engineer_user = app_module.db.session.get(app_module.User, engineer_user_id)
            engineer_profile = app_module.Engineer.query.filter_by(user_id=engineer_user.id).first()
            self.assertIsNotNone(engineer_profile)
            self.created_engineer_ids.append(engineer_profile.id)
            self.assertEqual(engineer_user.role, 'engineer')

        hr_response = client.post('/add_engineer', json=self._payload('Test HR Viewer', 'hr'))
        self.assertEqual(hr_response.status_code, 200)
        hr_user_id = self._remember_created_account(hr_response)
        with self.app.app_context():
            hr_user = app_module.db.session.get(app_module.User, hr_user_id)
            self.assertEqual(hr_user.role, 'staff')
            self.assertTrue(hr_user.hr_schedule_view)
            self.assertIsNone(app_module.Engineer.query.filter_by(user_id=hr_user.id).first())
            self.assertIn('Settings', hr_response.get_json()['message'])
            self.assertTrue(app_module.is_hr_schedule_only_user(hr_user))

        approver_response = client.post('/add_engineer', json=self._payload('Test Approver', 'approver'))
        self.assertEqual(approver_response.status_code, 200)
        approver_user_id = self._remember_created_account(approver_response)
        with self.app.app_context():
            approver_user = app_module.db.session.get(app_module.User, approver_user_id)
            self.assertEqual(approver_user.role, 'approver')
            self.assertTrue(approver_user.can_approve_requests)
            self.assertTrue(app_module.is_approver_only_user(approver_user))
            self.assertIsNone(app_module.Engineer.query.filter_by(user_id=approver_user.id).first())
            self.assertIn('Settings', approver_response.get_json()['message'])

    def test_inventory_permission_is_validated_before_account_write(self):
        client = self._client_for(self.superadmin_id)

        invalid = self._payload(
            'Missing Branch Inventory User',
            can_manage_stock_inventory=True,
            stock_inventory_branch_code='',
        )
        response = client.post('/add_engineer', json=invalid)
        self.assertEqual(response.status_code, 400)
        self.assertIn('branch', response.get_json()['message'].lower())
        with self.app.app_context():
            self.assertIsNone(app_module.User.query.filter_by(username='missing').first())

        valid = self._payload(
            'Inventory Engineer',
            can_manage_stock_inventory=True,
            stock_inventory_only=True,
            stock_inventory_branch_code='BC02',
        )
        response = client.post('/add_engineer', json=valid)
        self.assertEqual(response.status_code, 200)
        user_id = self._remember_created_account(response)
        with self.app.app_context():
            user = app_module.db.session.get(app_module.User, user_id)
            self.assertTrue(user.can_manage_stock_inventory)
            self.assertTrue(user.stock_inventory_only)
            self.assertEqual(user.stock_inventory_branch_code, 'BC02')

    def test_superadmin_rejects_conflicting_staff_permissions_without_writing(self):
        client = self._client_for(self.superadmin_id)
        response = client.post('/add_engineer', json=self._payload(
            'Conflicting Account',
            can_manage_stock_inventory=True,
            stock_inventory_branch_code='BC01',
            approver_only=True,
        ))
        self.assertEqual(response.status_code, 400)
        self.assertIn('cannot also manage', response.get_json()['message'].lower())
        with self.app.app_context():
            self.assertIsNone(app_module.User.query.filter_by(username='conflicting').first())

    def test_regional_admin_can_add_plain_engineer_but_cannot_assign_staff_permissions(self):
        client = self._client_for(self.regional_admin_id)

        denied = client.post('/add_engineer', json=self._payload(
            'Regional HR Attempt',
            'hr',
        ))
        self.assertEqual(denied.status_code, 403)

        denied_permission = client.post('/add_engineer', json=self._payload(
            'Regional Permission Attempt',
            can_approve_requests=True,
        ))
        self.assertEqual(denied_permission.status_code, 403)

        accepted = client.post('/add_engineer', json=self._payload('Regional Engineer'))
        self.assertEqual(accepted.status_code, 200)
        engineer_user_id = self._remember_created_account(accepted)
        with self.app.app_context():
            engineer_user = app_module.db.session.get(app_module.User, engineer_user_id)
            self.assertEqual(engineer_user.role, 'engineer')
            profile = app_module.Engineer.query.filter_by(user_id=engineer_user.id).first()
            self.assertIsNotNone(profile)
            self.created_engineer_ids.append(profile.id)

        legacy_payload = self._payload('Regional Legacy Engineer')
        legacy_payload.pop('staff_type')
        legacy_response = client.post('/add_engineer', json=legacy_payload)
        self.assertEqual(legacy_response.status_code, 200)
        legacy_user_id = self._remember_created_account(legacy_response)
        with self.app.app_context():
            legacy_profile = app_module.Engineer.query.filter_by(user_id=legacy_user_id).first()
            self.assertIsNotNone(legacy_profile)
            self.created_engineer_ids.append(legacy_profile.id)

    def test_staff_type_controls_are_superadmin_only_in_the_rendered_page(self):
        superadmin_html = self._client_for(self.superadmin_id).get('/engineers_page')
        self.assertEqual(superadmin_html.status_code, 200)
        self.assertIn('value="hr"', superadmin_html.get_data(as_text=True))
        self.assertIn('id="e-stock-inventory-access"', superadmin_html.get_data(as_text=True))

        regional_html = self._client_for(self.regional_admin_id).get('/engineers_page')
        self.assertEqual(regional_html.status_code, 200)
        self.assertNotIn('value="hr"', regional_html.get_data(as_text=True))
        self.assertNotIn('id="e-stock-inventory-access"', regional_html.get_data(as_text=True))

    def test_settings_and_add_routes_share_conflict_policy(self):
        client = self._client_for(self.superadmin_id)
        target_response = client.post('/add_engineer', json=self._payload('Existing Engineer'))
        self.assertEqual(target_response.status_code, 200)
        target_id = self._remember_created_account(target_response)

        settings_response = client.post('/settings/update-approval-user', json={
            'user_id': target_id,
            'approver_only': True,
            'can_manage_stock_inventory': True,
            'stock_inventory_branch_code': 'BC01',
        })
        self.assertEqual(settings_response.status_code, 400)
        self.assertIn('cannot also manage', settings_response.get_json()['error'].lower())

        add_response = client.post('/add_engineer', json=self._payload(
            'Conflicting New Engineer',
            approver_only=True,
            can_manage_stock_inventory=True,
            stock_inventory_branch_code='BC01',
        ))
        self.assertEqual(add_response.status_code, 400)
        self.assertIn('cannot also manage', add_response.get_json()['message'].lower())

        hr_settings_response = client.post('/settings/update-approval-user', json={
            'user_id': target_id,
            'hr_schedule_view': True,
            'can_manage_stock_inventory': True,
            'stock_inventory_branch_code': 'BC01',
        })
        self.assertEqual(hr_settings_response.status_code, 400)
        self.assertIn('cannot be combined', hr_settings_response.get_json()['error'].lower())

        hr_add_response = client.post('/add_engineer', json=self._payload(
            'Conflicting HR Account',
            'hr',
            can_manage_stock_inventory=True,
            stock_inventory_branch_code='BC01',
        ))
        self.assertEqual(hr_add_response.status_code, 400)
        self.assertIn('cannot be combined', hr_add_response.get_json()['message'].lower())


class StaffCreationSourceTests(unittest.TestCase):
    def test_template_and_manifest_expose_the_new_staff_flow(self):
        template = (ROOT / 'templates' / 'engineers.html').read_text(encoding='utf-8')
        releases = (ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8')
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        for expected in (
            'id="e-staff-type"',
            'value="hr"',
            'value="approver"',
            'id="e-hr-schedule-view"',
            'id="e-stock-inventory-access"',
            'function syncStaffTypePermissionControls()',
            'staff_type',
            'def resolve_staff_permission_request',
        ):
            self.assertIn(expected, template + source)
        self.assertIn('2026-08-05-staff-type-personnel-accounts', releases)


if __name__ == '__main__':
    unittest.main()
