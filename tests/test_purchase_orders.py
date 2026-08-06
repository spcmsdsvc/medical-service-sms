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


if __name__ == '__main__':
    unittest.main()
