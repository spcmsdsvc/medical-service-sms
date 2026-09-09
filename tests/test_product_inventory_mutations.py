"""Regression coverage for Product Inventory edit/delete mutations."""

import pathlib
import unittest
import uuid
from urllib.parse import quote

import app as app_module


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ProductInventoryMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.suffix = uuid.uuid4().hex[:10]
        cls.username = f'product_admin_{cls.suffix}'
        cls.serial = f'N/A-{cls.suffix}'

        # Use a test-only superadmin identity without changing the application's
        # production allowlist. This exercises the real mutation authorization guard.
        app_module.SUPERADMIN_USERNAMES.add(cls.username)

        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_product_contract_column()
            app_module.ensure_purchase_order_schema()

            cls.user = app_module.User(
                username=cls.username,
                password=app_module.generate_password_hash('test-password'),
                role='superadmin',
                is_active=True,
            )
            cls.client_record = app_module.Client(
                name=f'Product Mutation Client {cls.suffix}',
                address='Product mutation test address',
            )
            app_module.db.session.add_all([cls.user, cls.client_record])
            app_module.db.session.flush()
            cls.product = app_module.Product(
                serial_number=cls.serial,
                name='Slash Serial Machine',
                client_id=cls.client_record.id,
            )
            app_module.db.session.add(cls.product)
            app_module.db.session.commit()
            cls.user_id = cls.user.id
            cls.client_id = cls.client_record.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            product = app_module.db.session.get(app_module.Product, cls.serial)
            if product:
                app_module.db.session.delete(product)
            client_record = app_module.db.session.get(app_module.Client, cls.client_id)
            if client_record:
                app_module.db.session.delete(client_record)
            user = app_module.db.session.get(app_module.User, cls.user_id)
            if user:
                app_module.db.session.delete(user)
            app_module.db.session.commit()
        app_module.SUPERADMIN_USERNAMES.discard(cls.username)

    def setUp(self):
        self.client = self.app.test_client()
        response = self.client.post('/login', data={
            'username': self.username,
            'password': 'test-password',
        })
        self.assertIn(response.status_code, (302, 303))

    def test_edit_and_delete_accept_encoded_slash_serial_numbers(self):
        encoded_serial = quote(self.serial, safe='')

        updated = self.client.put(
            f'/update_product/{encoded_serial}',
            json={
                'serial_number': self.serial,
                'name': 'Edited Slash Serial Machine',
                'client_id': self.client_id,
                'under_contract': False,
            },
        )
        self.assertEqual(updated.status_code, 200, updated.get_data(as_text=True))

        deleted = self.client.delete(f'/delete_product/{encoded_serial}')
        self.assertEqual(deleted.status_code, 200, deleted.get_data(as_text=True))
        self.assertEqual(deleted.get_json()['status'], 'success')

        with self.app.app_context():
            self.assertIsNone(app_module.db.session.get(app_module.Product, self.serial))

    def test_product_page_uses_server_mutation_permissions_and_error_payloads(self):
        source = (ROOT / 'templates' / 'products.html').read_text(encoding='utf-8')
        self.assertIn('product_can_edit|tojson', source)
        self.assertIn('product_can_delete|tojson', source)
        self.assertIn('productResponseMessage', source)
        self.assertIn('await productResponseData(res)', source)
        self.assertNotIn("authRole !== 'engineer'", source)

        app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        self.assertIn("@app.route('/update_product/<path:serial_number>'", app_source)
        self.assertIn("@app.route('/delete_product/<path:serial_number>'", app_source)


if __name__ == '__main__':
    unittest.main()
