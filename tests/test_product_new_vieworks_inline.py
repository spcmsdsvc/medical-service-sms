"""Creating a Vieworks item from inside the Product add/edit form."""

import os
import pathlib
import tempfile
import unittest
import uuid
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_product_new_vieworks_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB_PATH))
os.environ.setdefault("SECRET_KEY", "product-new-vieworks-tests")

import app as app_module  # noqa: E402

TEMPLATE = (ROOT / 'templates' / 'products.html').read_text(encoding='utf-8')


class ProductNewVieworksInlineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=True)
        cls.suffix = uuid.uuid4().hex[:8].upper()
        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_product_contract_column()
            app_module.ensure_product_name_catalog()
            app_module.ensure_vieworks_item_table()
            app_module.ensure_product_vieworks_link_table()
            admin = app_module.User(username=f"pnv-admin-{cls.suffix}", password="test", role="admin", is_active=True)
            center = app_module.Client(name=f"PNV Center {cls.suffix}", address="A")
            catalog = app_module.ProductNameCatalog(name=f"PNV Machine {cls.suffix}")
            app_module.db.session.add_all([admin, center, catalog])
            app_module.db.session.commit()
            cls.admin_id = admin.id
            cls.center_id = center.id
            cls.catalog_id = catalog.id
            cls.catalog_name = catalog.name

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
            app_module.ProductNameCatalog.query.filter_by(id=cls.catalog_id).delete(synchronize_session=False)
            app_module.Client.query.filter_by(id=cls.center_id).delete(synchronize_session=False)
            app_module.User.query.filter_by(id=cls.admin_id).delete(synchronize_session=False)
            app_module.db.session.commit()
            app_module.db.session.remove()

    def setUp(self):
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.admin_id)
            session['_fresh'] = True

    def test_panel_renders_only_on_the_product_page(self):
        pages = {path: self.client.get(path) for path in ('/products_page', '/vieworks', '/genoray')}
        for path, response in pages.items():
            self.assertEqual(response.status_code, 200, path)
        product_html = pages['/products_page'].get_data(as_text=True)
        for element_id in ('p-new-vieworks-btn', 'p-new-vieworks-form', 'p-new-vieworks-serial',
                           'p-new-vieworks-name', 'p-new-vieworks-msg'):
            self.assertIn(f'id="{element_id}"', product_html)
        for path in ('/vieworks', '/genoray'):
            self.assertNotIn('id="p-new-vieworks-btn"', pages[path].get_data(as_text=True))

    def test_script_posts_with_the_machine_center_room_and_dates(self):
        start = TEMPLATE.index('async function createVieworksFromProduct')
        body = TEMPLATE[start:TEMPLATE.index('async function loadProductLinkOptions', start)]
        self.assertIn("fetch('/api/vieworks/items'", body)
        for key in ('client_id: clientId', "getElementById('p-room')",
                    "start_warranty: document.getElementById('p-w-start').value",
                    "end_warranty: document.getElementById('p-w-end').value"):
            self.assertIn(key, body)
        self.assertIn('refreshVieworksLinkOptions([...currentLinkedVieworksSerials(), item.serial_number])', body)

    def test_created_item_takes_machine_dates_and_links_on_product_save(self):
        vieworks_serial = f"PNV-V-{self.suffix}"
        created = self.client.post('/api/vieworks/items', json={
            'serial_number': vieworks_serial,
            'name': 'Inline Vieworks',
            'client_id': self.center_id,
            'room': 'X-Ray 1',
            'start_warranty': '2026-01-01',
            'end_warranty': '2027-01-01',
        })
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        machine_serial = f"PNV-M-{self.suffix}"
        saved = self.client.post('/add_product', json={
            'serial_number': machine_serial,
            'name': self.catalog_name,
            'product_name_id': self.catalog_id,
            'client_id': self.center_id,
            'room': 'X-Ray 1',
            'start_warranty': '2026-01-01',
            'end_warranty': '2027-01-01',
            'with_vieworks_canon': True,
            'linked_vieworks_serials': [vieworks_serial],
        })
        self.assertEqual(saved.status_code, 200, saved.get_data(as_text=True))
        with self.app.app_context():
            item = app_module.db.session.get(app_module.VieworksItem, vieworks_serial)
            self.assertEqual((item.start_warranty_date, item.end_warranty_date), (date(2026, 1, 1), date(2027, 1, 1)))
            self.assertEqual(item.room, 'X-Ray 1')
            link = app_module.ProductVieworksLink.query.filter_by(vieworks_serial=vieworks_serial).first()
            self.assertEqual(link.product_serial, machine_serial)


if __name__ == '__main__':
    unittest.main()
