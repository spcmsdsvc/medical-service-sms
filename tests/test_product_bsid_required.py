"""Product Inventory: BSID required on add, edit and CSV import (plans.md, 2026-11-03)."""

import io
import pathlib
import unittest
import uuid

import app as app_module


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / 'templates' / 'products.html').read_text(encoding='utf-8')


class ProductBsidRequiredTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.suffix = uuid.uuid4().hex[:8].upper()
        cls.username = f'bsid_required_admin_{cls.suffix.lower()}'
        cls.serial = f'BSIDREQ{cls.suffix}'
        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_product_contract_column()
            app_module.ensure_purchase_order_schema()
            app_module.ensure_product_name_catalog()
            catalog = app_module.ProductNameCatalog.query.order_by(app_module.ProductNameCatalog.id.asc()).first()
            user = app_module.User(
                username=cls.username,
                password=app_module.generate_password_hash('test-password'),
                role='superadmin',
                is_active=True,
            )
            app_module.db.session.add(user)
            app_module.db.session.flush()
            cls.user_id = user.id
            cls.catalog_id = catalog.id
            cls.catalog_name = catalog.name
            app_module.db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            app_module.Product.query.filter(
                app_module.func.upper(app_module.Product.serial_number).like(f'BSIDREQ{cls.suffix}%')
            ).delete(synchronize_session=False)
            for model, serial in ((app_module.GenorayItem, f'BSIDREQ-GEN-{cls.suffix}'), (app_module.VieworksItem, f'BSIDREQ-VW-{cls.suffix}')):
                row = app_module.db.session.get(model, serial)
                if row:
                    app_module.db.session.delete(row)
            user = app_module.db.session.get(app_module.User, cls.user_id)
            if user:
                app_module.db.session.delete(user)
            app_module.db.session.commit()

    def setUp(self):
        # Session login: posting to /login before every test trips its 10-per-minute limit.
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.user_id)
            session['_fresh'] = True
        with self.app.app_context():
            app_module.Product.query.filter(
                app_module.func.upper(app_module.Product.serial_number).like(f'BSIDREQ{self.suffix}%')
            ).delete(synchronize_session=False)
            # A legacy machine saved before BSIDs were required.
            app_module.db.session.add(app_module.Product(serial_number=self.serial, name=self.catalog_name))
            app_module.db.session.commit()

    def stored_bsid(self, serial):
        with self.app.app_context():
            row = app_module.db.session.get(app_module.Product, serial)
            return None if row is None else row.bsid

    def import_csv(self, text):
        return self.client.post(
            '/import_products',
            data={'file': (io.BytesIO(text.encode('utf-8')), 'products.csv')},
            content_type='multipart/form-data',
        )

    def test_add_requires_bsid(self):
        payload = {'serial_number': f'{self.serial}N', 'product_name_id': self.catalog_id}
        for blank in ('', '   ', None):
            with self.subTest(bsid=blank):
                response = self.client.post('/add_product', json={**payload, 'bsid': blank})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()['field'], 'bsid')
                self.assertEqual(response.get_json()['message'], app_module.PRODUCT_BSID_REQUIRED_MESSAGE)
        self.assertIsNone(self.stored_bsid(f'{self.serial}N'))
        saved = self.client.post('/add_product', json={**payload, 'bsid': f'B{self.suffix}N'})
        self.assertEqual(saved.status_code, 200, saved.get_data(as_text=True))
        self.assertEqual(self.stored_bsid(f'{self.serial}N'), f'B{self.suffix}N')

    def test_legacy_machine_edit_needs_a_bsid(self):
        payload = {'serial_number': self.serial, 'product_name_id': self.catalog_id, 'room': 'Room 9'}
        refused = self.client.put(f'/update_product/{self.serial}', json=payload)
        self.assertEqual(refused.status_code, 400)
        self.assertEqual(refused.get_json()['field'], 'bsid')
        saved = self.client.put(f'/update_product/{self.serial}', json={**payload, 'bsid': f'B{self.suffix}L'})
        self.assertEqual(saved.status_code, 200, saved.get_data(as_text=True))
        self.assertEqual(self.stored_bsid(self.serial), f'B{self.suffix}L')

    def test_csv_rows_must_end_up_with_a_bsid(self):
        new_serial = f'{self.serial}CSV'
        result = self.import_csv(f'Serial Number,Description,BSID\n{new_serial},{self.catalog_name},\n').get_json()
        self.assertEqual((result['created'], result['skipped']), (0, 1))
        self.assertIn('1 row(s) had no BSID.', result['message'])
        self.assertIsNone(self.stored_bsid(new_serial))

        # Existing legacy machine and no BSID column: still no BSID, so the row is skipped.
        result = self.import_csv(f'Serial Number,Description\n{self.serial},{self.catalog_name}\n').get_json()
        self.assertEqual((result['updated'], result['skipped']), (0, 1))

        result = self.import_csv(f'Serial Number,Description,BSID\n{new_serial},{self.catalog_name},B{self.suffix}C\n').get_json()
        self.assertEqual(result['created'], 1)
        # A machine that already has a BSID keeps it when the CSV has no BSID column.
        result = self.import_csv(f'Serial Number,Description,Room\n{new_serial},{self.catalog_name},Room 3\n').get_json()
        self.assertEqual((result['updated'], result['skipped']), (1, 0))
        self.assertEqual(self.stored_bsid(new_serial), f'B{self.suffix}C')

    def test_genoray_and_vieworks_still_save_without_a_bsid(self):
        for path, serial in (('/api/genoray/items', f'BSIDREQ-GEN-{self.suffix}'), ('/api/vieworks/items', f'BSIDREQ-VW-{self.suffix}')):
            with self.subTest(path=path):
                response = self.client.post(path, json={'serial_number': serial, 'name': 'Auto BSID item'})
                self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

    def test_page_requires_bsid_only_for_product_inventory(self):
        self.assertIn('if (!isStandaloneInventory && !data.bsid) {', TEMPLATE)
        self.assertIn('Required. Used for the calibration certificate number.', TEMPLATE)
        self.assertNotIn('Optional for legacy inventory', TEMPLATE)


if __name__ == '__main__':
    unittest.main()
