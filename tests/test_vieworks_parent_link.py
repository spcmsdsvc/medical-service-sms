"""Linking a Vieworks item to its Product machine from the Vieworks add/edit form."""

import os
import pathlib
import tempfile
import unittest
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_vieworks_parent_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB_PATH))
os.environ.setdefault("SECRET_KEY", "vieworks-parent-link-tests")

import app as app_module  # noqa: E402


class VieworksParentLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=True)
        cls.suffix = uuid.uuid4().hex[:8].upper()
        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_product_contract_column()
            app_module.ensure_vieworks_item_table()
            app_module.ensure_product_vieworks_link_table()
            admin = app_module.User(username=f"vw-link-admin-{cls.suffix}", password="test", role="admin", is_active=True)
            client_one = app_module.Client(name=f"VW Link Center One {cls.suffix}", address="A")
            client_two = app_module.Client(name=f"VW Link Center Two {cls.suffix}", address="B")
            app_module.db.session.add_all([admin, client_one, client_two])
            app_module.db.session.flush()
            machines = [
                app_module.Product(serial_number=f"VWL-M1-{cls.suffix}", name="Machine One", client_id=client_one.id),
                app_module.Product(serial_number=f"VWL-M2-{cls.suffix}", name="Machine Two", client_id=client_one.id),
                app_module.Product(serial_number=f"VWL-M3-{cls.suffix}", name="Machine Three", client_id=client_two.id),
            ]
            app_module.db.session.add_all(machines)
            app_module.db.session.commit()
            cls.admin_id = admin.id
            cls.client_one_id = client_one.id
            cls.client_two_id = client_two.id
            cls.machine_one, cls.machine_two, cls.machine_three = [m.serial_number for m in machines]

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            pattern = f"%{cls.suffix}"
            app_module.ProductVieworksLink.query.filter(
                app_module.ProductVieworksLink.product_serial.like(pattern)
            ).delete(synchronize_session=False)
            app_module.VieworksItem.query.filter(
                app_module.VieworksItem.serial_number.like(pattern)
            ).delete(synchronize_session=False)
            app_module.Product.query.filter(
                app_module.Product.serial_number.like(pattern)
            ).delete(synchronize_session=False)
            app_module.Client.query.filter(app_module.Client.id.in_([cls.client_one_id, cls.client_two_id])).delete(
                synchronize_session=False
            )
            app_module.User.query.filter_by(id=cls.admin_id).delete(synchronize_session=False)
            app_module.db.session.commit()
            app_module.db.session.remove()

    def setUp(self):
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.admin_id)
            session['_fresh'] = True

    def link_of(self, vieworks_serial):
        with self.app.app_context():
            rows = app_module.ProductVieworksLink.query.filter_by(vieworks_serial=vieworks_serial).all()
            return [row.product_serial for row in rows]

    def add_item(self, name, **extra):
        serial = f"VWL-{name}-{self.suffix}"
        payload = {'serial_number': serial, 'name': f'Vieworks {name}', 'client_id': self.client_one_id, **extra}
        return serial, self.client.post('/api/vieworks/items', json=payload)

    def test_add_with_machine_links_and_shows_on_both_pages(self):
        serial, response = self.add_item('ADD', linked_product_serial=self.machine_one)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.get_json()['item']['linked_product']['serial_number'], self.machine_one)
        self.assertEqual(self.link_of(serial), [self.machine_one])
        products = self.client.get('/get_products').get_json()
        machine = next(row for row in products if row['serial_number'] == self.machine_one)
        self.assertIn(serial, [item['serial_number'] for item in machine['linked_vieworks']])

    def test_add_rejects_machine_from_another_center_or_unknown(self):
        serial, other_center = self.add_item('BADCENTER', linked_product_serial=self.machine_three)
        self.assertEqual(other_center.status_code, 400)
        _, unknown = self.add_item('UNKNOWN', linked_product_serial=f'NOPE-{self.suffix}')
        self.assertEqual(unknown.status_code, 400)
        with self.app.app_context():
            self.assertIsNone(app_module.db.session.get(app_module.VieworksItem, serial))

    def test_edit_changes_machine_then_unlinks(self):
        serial, response = self.add_item('EDIT', linked_product_serial=self.machine_one)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        changed = self.client.put(f'/api/vieworks/items/{serial}', json={'linked_product_serial': self.machine_two})
        self.assertEqual(changed.status_code, 200, changed.get_data(as_text=True))
        self.assertEqual(self.link_of(serial), [self.machine_two])
        unlinked = self.client.put(f'/api/vieworks/items/{serial}', json={'linked_product_serial': ''})
        self.assertEqual(unlinked.status_code, 200, unlinked.get_data(as_text=True))
        self.assertEqual(self.link_of(serial), [])
        self.assertIsNone(unlinked.get_json()['item']['linked_product'])

    def test_center_and_machine_change_together(self):
        serial, _ = self.add_item('MOVE', linked_product_serial=self.machine_one)
        kept_old_machine = self.client.put(
            f'/api/vieworks/items/{serial}',
            json={'client_id': self.client_two_id, 'linked_product_serial': self.machine_one},
        )
        self.assertEqual(kept_old_machine.status_code, 400)
        moved = self.client.put(
            f'/api/vieworks/items/{serial}',
            json={'client_id': self.client_two_id, 'linked_product_serial': self.machine_three},
        )
        self.assertEqual(moved.status_code, 200, moved.get_data(as_text=True))
        self.assertEqual(self.link_of(serial), [self.machine_three])

    def test_edit_without_the_field_keeps_link_and_old_rules(self):
        serial, _ = self.add_item('KEEP', linked_product_serial=self.machine_one)
        renamed = self.client.put(f'/api/vieworks/items/{serial}', json={'name': 'Renamed Vieworks'})
        self.assertEqual(renamed.status_code, 200, renamed.get_data(as_text=True))
        self.assertEqual(self.link_of(serial), [self.machine_one])
        moved = self.client.put(f'/api/vieworks/items/{serial}', json={'client_id': self.client_two_id})
        self.assertEqual(moved.status_code, 400)

    def test_linked_machine_control_renders_only_on_vieworks(self):
        for path in ('/vieworks', '/products_page', '/genoray'):
            self.assertEqual(self.client.get(path).status_code, 200, path)
        self.assertIn('id="v-linked-product"', self.client.get('/vieworks').get_data(as_text=True))
        self.assertNotIn('id="v-linked-product"', self.client.get('/products_page').get_data(as_text=True))
        self.assertNotIn('id="v-linked-product"', self.client.get('/genoray').get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
