"""Behavioural coverage for the P.O. Details register and capability boundary."""

import pathlib
import unittest
import uuid

import app as app_module  # noqa: E402


ROOT = pathlib.Path(__file__).resolve().parents[1]


class PurchaseOrderWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.suffix = uuid.uuid4().hex[:8]
        cls.created_user_ids = []
        cls.created_client_ids = []
        cls.created_engineer_ids = []

        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_user_admin_capability_columns()
            app_module.ensure_purchase_order_schema()

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

            def create_user(username, **flags):
                user = app_module.User(
                    username=f'{username}_{cls.suffix}',
                    password=app_module.generate_password_hash('test-password'),
                    role='staff',
                    is_active=True,
                    **flags,
                )
                app_module.db.session.add(user)
                app_module.db.session.flush()
                cls.created_user_ids.append(user.id)
                return user

            cls.po_user = create_user('po_manager', po_admin_access=True)
            cls.personnel_user = create_user('po_personnel', personnel_admin_access=True)
            cls.plain_user = create_user('po_plain')

            cls.client_one = app_module.Client(
                name=f'P.O. Test Medical Center One {cls.suffix}',
                address='Test address one',
            )
            cls.client_two = app_module.Client(
                name=f'P.O. Test Medical Center Two {cls.suffix}',
                address='Test address two',
            )
            app_module.db.session.add_all([cls.client_one, cls.client_two])
            app_module.db.session.flush()
            cls.created_client_ids.extend([cls.client_one.id, cls.client_two.id])
            app_module.db.session.commit()

            cls.superadmin_id = cls.superadmin.id
            cls.po_user_id = cls.po_user.id
            cls.personnel_user_id = cls.personnel_user.id
            cls.plain_user_id = cls.plain_user.id
            cls.client_one_id = cls.client_one.id
            cls.client_two_id = cls.client_two.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            for purchase_order in app_module.PurchaseOrder.query.all():
                if purchase_order.client_id in cls.created_client_ids:
                    app_module.db.session.delete(purchase_order)
            for client_id in reversed(cls.created_client_ids):
                client = app_module.db.session.get(app_module.Client, client_id)
                if client:
                    app_module.db.session.delete(client)
            for user_id in reversed(cls.created_user_ids):
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

    def test_authorization_and_escalation_boundary(self):
        personnel = self._client_for(self.personnel_user_id)
        self.assertEqual(personnel.get('/po_details').status_code, 302)
        self.assertEqual(personnel.get('/get_purchase_orders').status_code, 403)
        self.assertEqual(
            personnel.post('/add_engineer', json={
                'name': f'Unauthorized P.O. Grant {self.suffix}',
                'employee_id': f'PO-ESC-{self.suffix}',
                'initials': 'PEG',
                'po_admin_access': True,
            }).status_code,
            403,
        )

        plain = self._client_for(self.plain_user_id)
        self.assertEqual(plain.get('/po_details').status_code, 302)
        self.assertEqual(plain.get('/get_purchase_orders').status_code, 403)

        superadmin = self._client_for(self.superadmin_id)
        response = superadmin.post('/settings/update-approval-user', json={
            'user_id': self.plain_user_id,
            'po_admin_access': True,
            'is_active': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['user']['po_admin_access'])
        with self.app.app_context():
            self.assertTrue(app_module.db.session.get(app_module.User, self.plain_user_id).po_admin_access)
            app_module.db.session.get(app_module.User, self.plain_user_id).po_admin_access = False
            app_module.db.session.commit()

        created = superadmin.post('/add_engineer', json={
            'name': f'Purchase Grant {self.suffix}',
            'employee_id': f'PO-GRANT-{self.suffix}',
            'initials': 'PGR',
            'po_admin_access': True,
        })
        self.assertEqual(created.status_code, 200)
        username = created.get_json()['username']
        with self.app.app_context():
            granted = app_module.User.query.filter_by(username=username).first()
            self.assertIsNotNone(granted)
            self.assertTrue(granted.po_admin_access)
            self.created_user_ids.append(granted.id)
            engineer = app_module.Engineer.query.filter_by(user_id=granted.id).first()
            if engineer:
                self.created_engineer_ids.append(engineer.id)

    def test_register_update_soft_duplicate_and_delete(self):
        client = self._client_for(self.po_user_id)
        self.assertEqual(client.get('/po_details').status_code, 200)

        created = client.post('/add_purchase_order', json={
            'client_id': self.client_one_id,
            'po_date': '2026-08-06',
            'po_number': ' PO-001  ',
            'po_type': 'contract',
        })
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        record = created.get_json()['purchase_order']
        self.assertEqual(record['po_number'], 'PO-001')
        self.assertEqual(record['po_type'], 'contract')

        duplicate = client.post('/add_purchase_order', json={
            'client_id': self.client_one_id,
            'po_date': '2026-08-07',
            'po_number': 'po-001',
            'po_type': 'single_visit',
        })
        self.assertEqual(duplicate.status_code, 409)
        self.assertIn('duplicate', duplicate.get_json())

        forced = client.post('/add_purchase_order', json={
            'client_id': self.client_one_id,
            'po_date': '2026-08-07',
            'po_number': 'po-001',
            'po_type': 'single_visit',
            'force': True,
        })
        self.assertEqual(forced.status_code, 201)

        updated = client.put(f"/update_purchase_order/{record['id']}", json={
            'client_id': self.client_one_id,
            'po_date': '2026-08-08',
            'po_number': 'PO-001-UPDATED',
            'po_type': 'single_visit',
        })
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()['purchase_order']['po_type'], 'single_visit')

        listing = client.get('/get_purchase_orders')
        self.assertEqual(listing.status_code, 200)
        self.assertGreaterEqual(len(listing.get_json()['purchase_orders']), 2)

        self.assertEqual(client.delete(f"/delete_purchase_order/{record['id']}").status_code, 200)

    def test_client_delete_cascades_purchase_orders_without_touching_other_client(self):
        client = self._client_for(self.po_user_id)
        with self.app.app_context():
            delete_target = app_module.Client(
                name=f'P.O. Cascade Target {self.suffix}',
                address='Temporary cascade target',
            )
            app_module.db.session.add(delete_target)
            app_module.db.session.flush()
            delete_target_id = delete_target.id
            app_module.db.session.commit()
        first = client.post('/add_purchase_order', json={
            'client_id': delete_target_id,
            'po_date': '2026-08-06',
            'po_number': f'CASCADE-ONE-{self.suffix}',
            'po_type': 'single_visit',
        })
        second = client.post('/add_purchase_order', json={
            'client_id': self.client_two_id,
            'po_date': '2026-08-06',
            'po_number': f'CASCADE-TWO-{self.suffix}',
            'po_type': 'contract',
        })
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)

        superadmin = self._client_for(self.superadmin_id)
        deleted = superadmin.delete(f'/delete_client/{delete_target_id}')
        self.assertEqual(deleted.status_code, 200)

        with self.app.app_context():
            self.assertIsNone(app_module.db.session.get(app_module.Client, delete_target_id))
            self.assertFalse(app_module.PurchaseOrder.query.filter_by(client_id=delete_target_id).first())
            survivor = app_module.PurchaseOrder.query.filter_by(client_id=self.client_two_id).first()
            self.assertIsNotNone(survivor)

    def test_model_has_no_financial_or_schedule_linkage(self):
        columns = set(app_module.PurchaseOrder.__table__.columns.keys())
        self.assertFalse({'amount', 'shift_id', 'tsr_id', 'product_id'} & columns)
        self.assertEqual(
            app_module.Client.purchase_orders.property.cascade.delete_orphan,
            True,
        )

    def test_settings_reports_the_stored_grant_not_the_effective_permission(self):
        """The Settings payload must carry the stored flag, not the effective permission.

        approval_user_to_dict() drives the Settings switches, and saveApprovalUser()
        posts the rendered state straight back. Reporting can_manage_purchase_orders()
        -- which folds in is_admin_authorized() -- made the switch render checked for
        every superadmin and the regional admin, so saving any unrelated change on their
        card wrote po_admin_access=True and an audit line for a grant nobody performed.
        The regional admin reaches the same is_admin_authorized() branch.
        """
        with self.app.app_context():
            superadmin = app_module.db.session.get(app_module.User, self.superadmin_id)
            self.assertFalse(
                superadmin.po_admin_access,
                'fixture precondition: the superadmin holds no explicit grant',
            )
            # Effective access is unchanged -- admins still reach the register.
            self.assertTrue(app_module.can_manage_purchase_orders(superadmin))
            # ...but the Settings switch must show the stored grant, which is False.
            self.assertFalse(
                app_module.approval_user_to_dict(superadmin)['po_admin_access']
            )

            # Positive control: a real grantee still reports True, so the assertion
            # above cannot pass by the serializer simply always returning False.
            granted = app_module.db.session.get(app_module.User, self.po_user_id)
            self.assertTrue(granted.po_admin_access)
            self.assertTrue(
                app_module.approval_user_to_dict(granted)['po_admin_access']
            )

    def test_saving_an_unrelated_permission_does_not_grant_po_access(self):
        """A superadmin's card round-trips without silently persisting the flag."""
        superadmin = self._client_for(self.superadmin_id)
        rendered = superadmin.get('/settings/approval-routing-data')
        self.assertEqual(rendered.status_code, 200)
        row = next(
            user for user in rendered.get_json()['users']
            if user['id'] == self.superadmin_id
        )
        self.assertFalse(row['po_admin_access'], 'the switch must render unchecked')

        # Post back exactly what the UI rendered, as saveApprovalUser() does.
        saved = superadmin.post('/settings/update-approval-user', json={
            'user_id': self.superadmin_id,
            'is_active': True,
            'po_admin_access': row['po_admin_access'],
        })
        self.assertEqual(saved.status_code, 200)
        with self.app.app_context():
            self.assertFalse(
                app_module.db.session.get(app_module.User, self.superadmin_id).po_admin_access
            )

    def test_writes_are_refused_without_the_capability(self):
        owner = self._client_for(self.po_user_id)
        seeded = owner.post('/add_purchase_order', json={
            'client_id': self.client_two_id,
            'po_date': '2026-08-06',
            'po_number': f'GUARD-{self.suffix}',
            'po_type': 'contract',
        })
        self.assertEqual(seeded.status_code, 201)
        record_id = seeded.get_json()['purchase_order']['id']

        intruder = self._client_for(self.plain_user_id)
        self.assertEqual(intruder.post('/add_purchase_order', json={
            'client_id': self.client_two_id,
            'po_date': '2026-08-06',
            'po_number': f'INTRUDER-{self.suffix}',
            'po_type': 'contract',
        }).status_code, 403)
        self.assertEqual(intruder.put(f'/update_purchase_order/{record_id}', json={
            'client_id': self.client_two_id,
            'po_date': '2026-08-06',
            'po_number': f'INTRUDER-EDIT-{self.suffix}',
            'po_type': 'contract',
        }).status_code, 403)
        self.assertEqual(
            intruder.delete(f'/delete_purchase_order/{record_id}').status_code, 403
        )

        with self.app.app_context():
            survivor = app_module.db.session.get(app_module.PurchaseOrder, record_id)
            self.assertIsNotNone(survivor, 'the refused delete must not have landed')
            self.assertEqual(survivor.po_number, f'GUARD-{self.suffix}')

        # Positive control: the same three calls succeed for the capability holder.
        self.assertEqual(owner.put(f'/update_purchase_order/{record_id}', json={
            'client_id': self.client_two_id,
            'po_date': '2026-08-06',
            'po_number': f'GUARD-EDITED-{self.suffix}',
            'po_type': 'single_visit',
        }).status_code, 200)
        self.assertEqual(
            owner.delete(f'/delete_purchase_order/{record_id}').status_code, 200
        )

    def test_po_type_must_be_contract_or_single_visit(self):
        client = self._client_for(self.po_user_id)

        def add(po_type, number):
            return client.post('/add_purchase_order', json={
                'client_id': self.client_two_id,
                'po_date': '2026-08-06',
                'po_number': number,
                'po_type': po_type,
            })

        for rejected in ('maybe', '', 'Contracts', 'true', '1'):
            response = add(rejected, f'TYPE-BAD-{self.suffix}')
            self.assertEqual(response.status_code, 400, f'accepted po_type={rejected!r}')
            self.assertIn('Contract', response.get_json()['error'])

        # Positive control: both real values are accepted and stored as text.
        for accepted, label in (('contract', 'Contract'), ('single_visit', 'Single Visit')):
            response = add(accepted, f'TYPE-OK-{accepted}-{self.suffix}')
            self.assertEqual(response.status_code, 201)
            body = response.get_json()['purchase_order']
            self.assertEqual(body['po_type'], accepted)
            self.assertEqual(body['po_type_label'], label)

    def test_po_date_must_be_an_iso_date(self):
        client = self._client_for(self.po_user_id)

        def add(po_date, number):
            return client.post('/add_purchase_order', json={
                'client_id': self.client_two_id,
                'po_date': po_date,
                'po_number': number,
                'po_type': 'contract',
            })

        for rejected in ('08/06/2026', '2026-13-45', '', 'yesterday', '2026/08/06'):
            response = add(rejected, f'DATE-BAD-{self.suffix}')
            self.assertEqual(response.status_code, 400, f'accepted po_date={rejected!r}')
            self.assertIn('date', response.get_json()['error'].lower())

        # Positive control.
        response = add('2026-08-06', f'DATE-OK-{self.suffix}')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()['purchase_order']['po_date'], '2026-08-06')

    def test_missing_records_report_404_rather_than_a_silent_success(self):
        """delete_client() reports success for an id that never existed; this must not."""
        client = self._client_for(self.po_user_id)
        created = client.post('/add_purchase_order', json={
            'client_id': self.client_two_id,
            'po_date': '2026-08-06',
            'po_number': f'GONE-{self.suffix}',
            'po_type': 'single_visit',
        })
        self.assertEqual(created.status_code, 201)
        record_id = created.get_json()['purchase_order']['id']

        # Positive control: the first delete really does succeed.
        self.assertEqual(
            client.delete(f'/delete_purchase_order/{record_id}').status_code, 200
        )

        self.assertEqual(
            client.delete(f'/delete_purchase_order/{record_id}').status_code, 404
        )
        self.assertEqual(client.put(f'/update_purchase_order/{record_id}', json={
            'client_id': self.client_two_id,
            'po_date': '2026-08-06',
            'po_number': f'GONE-EDIT-{self.suffix}',
            'po_type': 'contract',
        }).status_code, 404)


if __name__ == '__main__':
    unittest.main()
