"""Product Inventory Batch 3: parallel loading, light client list, batched lookups."""

import unittest
import uuid

from sqlalchemy import event

import app as app_module
from tests.test_product_inventory_batch1 import TEMPLATE, function_body


class ProductInventoryLoadingSourceTests(unittest.TestCase):
    def test_page_starts_requests_together_and_skips_summary(self):
        self.assertIn('Promise.all([loadProductNameCatalog(), loadData()])', TEMPLATE)
        self.assertIn('loadVieworksLinkOptions()', function_body('loadData'))
        self.assertNotIn('inventorySummaryUrl', TEMPLATE)
        self.assertNotIn('productSummary', TEMPLATE)
        self.assertIn("/get_clients?fields=basic", TEMPLATE)

    def test_delete_updates_in_place(self):
        delete = function_body('deleteProduct')
        self.assertNotIn('loadData()', delete)
        self.assertIn('productsData.filter(', delete)


class ProductInventoryLoadingRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.suffix = uuid.uuid4().hex[:8].upper()
        cls.username = f'product_b3_admin_{cls.suffix.lower()}'
        app_module.SUPERADMIN_USERNAMES.add(cls.username)
        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_product_contract_column()
            app_module.ensure_product_vieworks_link_table()
            app_module.ensure_vieworks_item_table()
            user = app_module.User(
                username=cls.username,
                password=app_module.generate_password_hash('test-password'),
                role='superadmin',
                is_active=True,
            )
            clients = [
                app_module.Client(name=f'B3 Client {cls.suffix} {i}', address=f'Addr {i}')
                for i in range(2)
            ]
            app_module.db.session.add(user)
            app_module.db.session.add_all(clients)
            app_module.db.session.flush()
            cls.user_id = user.id
            cls.client_ids = [client.id for client in clients]
            cls.serials = []
            cls.vieworks_serials = []
            app_module.db.session.commit()
        cls.add_products(3)

    @classmethod
    def add_products(cls, count):
        with cls.app.app_context():
            for _ in range(count):
                index = len(cls.serials)
                client_id = cls.client_ids[index % 2]
                serial = f'B3P{cls.suffix}{index}'
                vieworks_serial = f'B3V{cls.suffix}{index}'
                app_module.db.session.add(app_module.Product(
                    serial_number=serial, name=f'B3 Product {index}', client_id=client_id
                ))
                app_module.db.session.add(app_module.VieworksItem(
                    serial_number=vieworks_serial, name=f'B3 Vieworks {index}', client_id=client_id
                ))
                app_module.db.session.add(app_module.ProductVieworksLink(
                    product_serial=serial, vieworks_serial=vieworks_serial
                ))
                cls.serials.append(serial)
                cls.vieworks_serials.append(vieworks_serial)
            app_module.db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            session = app_module.db.session
            app_module.ProductVieworksLink.query.filter(
                app_module.ProductVieworksLink.product_serial.in_(cls.serials)
            ).delete(synchronize_session=False)
            app_module.Product.query.filter(
                app_module.Product.serial_number.in_(cls.serials)
            ).delete(synchronize_session=False)
            app_module.VieworksItem.query.filter(
                app_module.VieworksItem.serial_number.in_(cls.vieworks_serials)
            ).delete(synchronize_session=False)
            app_module.Client.query.filter(
                app_module.Client.id.in_(cls.client_ids)
            ).delete(synchronize_session=False)
            user = session.get(app_module.User, cls.user_id)
            if user:
                session.delete(user)
            session.commit()
        app_module.SUPERADMIN_USERNAMES.discard(cls.username)

    def client(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.user_id)
            session['_fresh'] = True
        return client

    def test_basic_client_list_has_only_identity_fields(self):
        response = self.client().get('/get_clients?fields=basic')
        self.assertEqual(response.status_code, 200)
        rows = response.get_json()
        self.assertTrue(rows)
        self.assertEqual({key for row in rows for key in row}, {'id', 'name', 'address'})
        full = self.client().get('/get_clients').get_json()
        self.assertIn('product_count', full[0])

    def test_get_products_keeps_shape_and_query_count_is_flat(self):
        client = self.client()
        client.get('/get_products')  # warm up one-time ensure_* checks

        def count_queries():
            statements = []

            def record(*_args):
                statements.append(1)

            with self.app.app_context():
                engine = app_module.db.engine
            event.listen(engine, 'before_cursor_execute', record)
            try:
                response = client.get('/get_products')
            finally:
                event.remove(engine, 'before_cursor_execute', record)
            self.assertEqual(response.status_code, 200)
            return len(statements), response.get_json()

        before, rows = count_queries()
        with self.app.app_context():
            for serial in self.serials:
                row = next(item for item in rows if item['serial_number'] == serial)
                self.assertEqual(row['linked_vieworks'], app_module.product_vieworks_link_payload(serial))
                self.assertTrue(row['with_vieworks_canon'])
                product = app_module.db.session.get(app_module.Product, serial)
                self.assertEqual(row['client_name'], product.owner.name)

        self.add_products(3)
        after, _ = count_queries()
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
