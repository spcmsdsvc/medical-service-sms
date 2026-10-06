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


    # --- Rules that changed when the policy was extracted into the shared resolver ---
    #
    # Extracting resolve_staff_permission_request() was meant to be pure movement, but
    # three inputs came out behaving differently. The new behaviour is the one we want;
    # these pin it so the change stays deliberate and cannot drift back unnoticed.

    def _resolve(self, **payload):
        with self.app.app_context():
            target = app_module.User(
                username=f'policy_probe_{self.suffix}', role='engineer', is_active=True
            )
            return app_module.resolve_staff_permission_request(payload, target)

    def test_inventory_only_now_implies_the_underlying_inventory_capability(self):
        """Ticking Inventory-only alone used to clear BOTH flags and grant nothing.

        It now grants inventory access as well, because a restricted inventory view that
        carries no inventory access is not a coherent state. This widens access on a
        partial payload, so it is pinned rather than left to the reader to notice.
        """
        values, error = self._resolve(
            stock_inventory_only=True, stock_inventory_branch_code='BC01'
        )
        self.assertIsNone(error)
        self.assertTrue(values['stock_inventory_only'])
        self.assertTrue(values['can_manage_stock_inventory'])

        # Positive control: with neither box ticked nothing is granted, so the assertion
        # above is reading the implication and not a resolver that always returns True.
        off_values, off_error = self._resolve()
        self.assertIsNone(off_error)
        self.assertFalse(off_values['stock_inventory_only'])
        self.assertFalse(off_values['can_manage_stock_inventory'])

        # And the branch requirement still applies to the implied capability.
        _, branch_error = self._resolve(stock_inventory_only=True)
        self.assertEqual(branch_error, 'Select a branch for this Stock Inventory user.')

    def test_hr_view_conflicts_now_name_the_control_that_actually_clashes(self):
        """The message named Approver-only and Inventory-only whatever the payload held.

        Ticking HR beside Can Approve Requests therefore reported a conflict with two
        switches that were both off, leaving no way to work out what to change.
        """
        _, approve_error = self._resolve(hr_schedule_view=True, can_approve_requests=True)
        self.assertIn('Can Approve Requests', approve_error)
        self.assertNotIn('Approver-only view', approve_error)

        _, manage_error = self._resolve(
            hr_schedule_view=True, can_manage_stock_inventory=True,
            stock_inventory_branch_code='BC01',
        )
        self.assertIn('Can Manage Stock Inventory', manage_error)
        self.assertNotIn('Approver-only view', manage_error)

        _, only_error = self._resolve(
            hr_schedule_view=True, stock_inventory_only=True,
            stock_inventory_branch_code='BC01',
        )
        self.assertIn('Stock Inventory-only view', only_error)
        # Inventory-only implies Can Manage, but naming both would be noise.
        self.assertNotIn('Can Manage Stock Inventory', only_error)

        # Positive control: HR on its own is a valid account, so the rejections above are
        # the conflict rule and not a resolver that refuses HR outright.
        values, error = self._resolve(hr_schedule_view=True)
        self.assertIsNone(error)
        self.assertTrue(values['hr_schedule_view'])

    def test_initials_are_required_for_engineers_only(self):
        """Initials live on the Engineer row, so a non-engineer account discards them."""
        client = self._client_for(self.superadmin_id)

        hr_payload = self._payload('Initialless HR Person', 'hr')
        hr_payload.pop('initials')
        hr_response = client.post('/add_engineer', json=hr_payload)
        self.assertEqual(hr_response.status_code, 200)
        self._remember_created_account(hr_response)

        # Positive control: an engineer without initials is still refused, so the pass
        # above is the staff-type carve-out and not a dropped validation.
        engineer_payload = self._payload('Initialless Engineer Person')
        engineer_payload['initials'] = ''
        engineer_response = client.post('/add_engineer', json=engineer_payload)
        self.assertEqual(engineer_response.status_code, 400)
        self.assertIn('Initials', engineer_response.get_json()['message'])

        # A name is still mandatory for every staff type.
        nameless = self._payload('Nameless HR Person', 'hr')
        nameless['name'] = ''
        nameless.pop('initials')
        nameless_response = client.post('/add_engineer', json=nameless)
        self.assertEqual(nameless_response.status_code, 400)
        self.assertIn('Name', nameless_response.get_json()['message'])

    def _make_engineer(self, name, with_login=True):
        """Create an engineer (and optionally a login) directly; returns (engineer_id, user_id)."""
        tag = uuid.uuid4().hex[:8]
        with self.app.app_context():
            user = None
            if with_login:
                user = app_module.User(
                    username=f'person{tag}',
                    password=app_module.generate_password_hash('test-password'),
                    role='engineer',
                    is_active=True,
                )
                app_module.db.session.add(user)
                app_module.db.session.flush()
                self.created_user_ids.append(user.id)
            engineer = app_module.Engineer(
                user_id=user.id if user else None,
                employee_id=f'PH-{tag}',
                name=name,
                initials=f'X{tag[:4]}'.upper(),
                branch='Manila',
            )
            app_module.db.session.add(engineer)
            app_module.db.session.commit()
            self.created_engineer_ids.append(engineer.id)
            return engineer.id, (user.id if user else None)

    def test_delete_is_refused_when_the_engineer_has_schedules(self):
        engineer_id, _ = self._make_engineer('History Keeper')
        with self.app.app_context():
            start = app_module.datetime(2026, 1, 5, 8, 0)
            shift = app_module.Shift(
                title='History visit',
                start_time=start,
                end_time=start + app_module.timedelta(hours=2),
                engineer_id=engineer_id,
            )
            app_module.db.session.add(shift)
            app_module.db.session.commit()
            shift_id = shift.id

        response = self._client_for(self.superadmin_id).delete(f'/delete_engineer/{engineer_id}')
        self.assertEqual(response.status_code, 409)
        self.assertIn('Deactivate instead', response.get_json()['message'])
        with self.app.app_context():
            self.assertIsNotNone(app_module.db.session.get(app_module.Shift, shift_id))
            self.assertIsNotNone(app_module.db.session.get(app_module.Engineer, engineer_id))
            app_module.db.session.delete(app_module.db.session.get(app_module.Shift, shift_id))
            app_module.db.session.commit()

    def test_delete_still_works_without_records(self):
        engineer_id, user_id = self._make_engineer('Clean Slate')
        response = self._client_for(self.superadmin_id).delete(f'/delete_engineer/{engineer_id}')
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertIsNone(app_module.db.session.get(app_module.Engineer, engineer_id))
            self.assertIsNone(app_module.db.session.get(app_module.User, user_id))

    def test_deactivate_signs_the_person_out_and_activate_restores_access(self):
        engineer_id, user_id = self._make_engineer('Leaving Soon')
        engineer_client = self._client_for(user_id)
        self.assertEqual(engineer_client.get('/get_engineers').status_code, 200)

        admin = self._client_for(self.superadmin_id)
        response = admin.post(f'/set_engineer_active/{engineer_id}', json={'active': False})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()['account_active'])
        with self.app.app_context():
            self.assertFalse(app_module.db.session.get(app_module.User, user_id).is_active)

        # The existing session no longer counts as signed in.
        self.assertNotEqual(engineer_client.get('/get_engineers').status_code, 200)

        response = admin.post(f'/set_engineer_active/{engineer_id}', json={'active': True})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['account_active'])
        self.assertEqual(self._client_for(user_id).get('/get_engineers').status_code, 200)

    def test_cannot_deactivate_or_delete_own_or_protected_logins(self):
        regional = self._client_for(self.regional_admin_id)
        # Regional admin's own profile.
        self.assertEqual(
            regional.post(f'/set_engineer_active/{self.regional_profile_id}', json={'active': False}).status_code,
            403,
        )
        self.assertEqual(regional.delete(f'/delete_engineer/{self.regional_profile_id}').status_code, 403)

        # A profile linked to the protected superadmin login.
        with self.app.app_context():
            protected = app_module.Engineer(
                user_id=self.superadmin_id,
                employee_id=f'PROT-{uuid.uuid4().hex[:8]}',
                name='Protected Profile',
                initials=f'P{uuid.uuid4().hex[:4]}'.upper(),
            )
            app_module.db.session.add(protected)
            app_module.db.session.commit()
            protected_id = protected.id
            self.created_engineer_ids.append(protected_id)
        self.assertEqual(
            regional.post(f'/set_engineer_active/{protected_id}', json={'active': False}).status_code,
            403,
        )
        self.assertEqual(regional.delete(f'/delete_engineer/{protected_id}').status_code, 403)
        with self.app.app_context():
            self.assertTrue(app_module.db.session.get(app_module.User, self.superadmin_id).is_active)
            self.assertIsNotNone(app_module.db.session.get(app_module.User, self.superadmin_id))

    def test_deactivate_needs_a_login(self):
        engineer_id, _ = self._make_engineer('No Login Person', with_login=False)
        response = self._client_for(self.superadmin_id).post(
            f'/set_engineer_active/{engineer_id}', json={'active': False}
        )
        self.assertEqual(response.status_code, 400)

    def test_directory_does_not_link_accounts_by_first_name(self):
        tag = uuid.uuid4().hex[:8]
        with self.app.app_context():
            user = app_module.User(
                username=f'namesake{tag}',
                password=app_module.generate_password_hash('test-password'),
                role='engineer',
            )
            app_module.db.session.add(user)
            app_module.db.session.commit()
            self.created_user_ids.append(user.id)
        engineer_id, _ = self._make_engineer(f'Namesake{tag} Unlinked', with_login=False)

        rows = self._client_for(self.superadmin_id).get('/get_engineers').get_json()
        row = next(item for item in rows if item['id'] == engineer_id)
        self.assertIsNone(row['user_id'])
        self.assertIsNone(row['account_active'])


    def test_same_name_adds_get_distinct_case_insensitive_usernames(self):
        tag = uuid.uuid4().hex[:6]
        client = self._client_for(self.superadmin_id)
        with self.app.app_context():
            # A case variant of the first name is already taken.
            taken = app_module.User(
                username=f'Twin{tag}'.upper(),
                password=app_module.generate_password_hash('test-password'),
                role='engineer',
            )
            app_module.db.session.add(taken)
            app_module.db.session.commit()
            self.created_user_ids.append(taken.id)

        usernames = []
        for index in range(3):
            response = client.post('/add_engineer', json=self._payload(
                f'Twin{tag} Santos',
                employee_id=f'TWIN-{tag}-{index}',
                initials=f'T{tag[:3]}{index}'.upper(),
            ))
            self.assertEqual(response.status_code, 200, response.get_json())
            self._remember_created_account(response)
            usernames.append(response.get_json()['username'].lower())
        self.assertEqual(len(set(usernames)), 3)
        self.assertNotIn(f'twin{tag}', usernames)

    def test_employee_id_duplicates_ignore_case_and_spaces(self):
        client = self._client_for(self.superadmin_id)
        tag = uuid.uuid4().hex[:6]
        first = client.post('/add_engineer', json=self._payload(
            f'Idcheck{tag} One', employee_id=f'ab-{tag}', initials=f'I{tag[:3]}A'.upper()))
        self.assertEqual(first.status_code, 200, first.get_json())
        self._remember_created_account(first)

        duplicate = client.post('/add_engineer', json=self._payload(
            f'Idcheck{tag} Two', employee_id=f' AB-{tag.upper()} ', initials=f'I{tag[:3]}B'.upper()))
        self.assertEqual(duplicate.status_code, 400)

        other_id, _ = self._make_engineer(f'Idcheck{tag} Three')
        with self.app.app_context():
            other = app_module.db.session.get(app_module.Engineer, other_id)
            payload = {'employee_id': f'AB-{tag.upper()}', 'name': other.name, 'initials': other.initials}
        self.assertEqual(client.put(f'/update_engineer/{other_id}', json=payload).status_code, 400)

    def test_contact_checks_apply_only_to_changed_values(self):
        client = self._client_for(self.superadmin_id)
        tag = uuid.uuid4().hex[:6]
        bad_phone = client.post('/add_engineer', json=self._payload(
            f'Contact{tag} Bad', employee_id=f'CB-{tag}', phone='0917'))
        self.assertEqual(bad_phone.status_code, 400)
        self.assertIn('Mobile number', bad_phone.get_json()['message'])
        bad_email = client.post('/add_engineer', json=self._payload(
            f'Contact{tag} Bad', employee_id=f'CB-{tag}', email='not-an-email'))
        self.assertEqual(bad_email.status_code, 400)

        engineer_id, user_id = self._make_engineer(f'Contact{tag} Legacy')
        with self.app.app_context():
            engineer = app_module.db.session.get(app_module.Engineer, engineer_id)
            engineer.phone = '0917'
            app_module.db.session.commit()
            payload = {
                'employee_id': engineer.employee_id, 'name': engineer.name,
                'initials': engineer.initials, 'phone': '0917', 'email': '', 'branch': 'Cebu',
            }
        # Unchanged legacy phone still saves.
        self.assertEqual(client.put(f'/update_engineer/{engineer_id}', json=payload).status_code, 200)
        # A changed bad email is refused for the admin and for the engineer's own edit.
        self.assertEqual(
            client.put(f'/update_engineer/{engineer_id}', json=dict(payload, email='bad@')).status_code, 400)
        own = self._client_for(user_id)
        self.assertEqual(
            own.put(f'/update_engineer/{engineer_id}', json={'phone': '12', 'email': ''}).status_code, 400)
        self.assertEqual(
            own.put(f'/update_engineer/{engineer_id}', json={'phone': '0917 123 4567', 'email': ''}).status_code, 200)


class StaffCreationSourceTests(unittest.TestCase):
    def test_personnel_form_guards_save_and_keeps_edit_fields(self):
        template = (ROOT / 'templates' / 'engineers.html').read_text(encoding='utf-8')
        self.assertIn('id="eng-save-btn"', template)
        save_body = template.split('async function saveEngineer()', 1)[1].split('async function deleteEngineer', 1)[0]
        self.assertIn('finally', save_body)
        edit_body = template.split('function openEditModal(dbId)', 1)[1].split('async function saveEngineer', 1)[0]
        self.assertIn("classList.remove('d-none')", edit_body)
        initials_body = template.split('function autoInitials()', 1)[1].split('function openAddModal', 1)[0]
        self.assertIn('edit-eng-db-id', initials_body)
        self.assertIn('.slice(0, 5)', initials_body)

    def test_personnel_page_offers_deactivate_and_account_status(self):
        template = (ROOT / 'templates' / 'engineers.html').read_text(encoding='utf-8')
        for expected in (
            'function setEngineerActive(',
            'function engineerAccountBadge(',
            'function deleteEngineer(',
            'function openEditModal(',
            'function saveEngineer(',
        ):
            self.assertIn(expected, template)

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
