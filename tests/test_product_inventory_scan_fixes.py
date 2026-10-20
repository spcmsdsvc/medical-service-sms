"""Product Inventory scan fixes (plans.md, 2026-10-15): import, validation, page logic, design."""

import io
import pathlib
import unittest
import uuid

import app as app_module


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / 'templates' / 'products.html').read_text(encoding='utf-8')
APP_SOURCE = (ROOT / 'app.py').read_text(encoding='utf-8')


class ProductInventoryScanServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.suffix = uuid.uuid4().hex[:8].upper()
        cls.username = f'product_scan_admin_{cls.suffix.lower()}'
        cls.serial = f'SCANFIX{cls.suffix}'

        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_product_contract_column()
            app_module.ensure_purchase_order_schema()
            app_module.ensure_product_name_catalog()
            cls.catalog = app_module.ProductNameCatalog.query.order_by(app_module.ProductNameCatalog.id.asc()).first()
            user = app_module.User(
                username=cls.username,
                password=app_module.generate_password_hash('test-password'),
                role='superadmin',
                is_active=True,
            )
            client = app_module.Client(name=f'Scan Fix Hospital {cls.suffix}', address='Scan fix address')
            app_module.db.session.add_all([user, client])
            app_module.db.session.flush()
            cls.user_id = user.id
            cls.client_id = client.id
            cls.client_name = client.name
            cls.catalog_id = cls.catalog.id
            cls.catalog_name = cls.catalog.name
            app_module.db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            app_module.Product.query.filter(
                app_module.func.upper(app_module.Product.serial_number).like(f'SCANFIX{cls.suffix}%')
            ).delete(synchronize_session=False)
            for model, key in ((app_module.Client, cls.client_id), (app_module.User, cls.user_id)):
                row = app_module.db.session.get(model, key)
                if row:
                    app_module.db.session.delete(row)
            app_module.db.session.commit()

    def setUp(self):
        self.client = self.app.test_client()
        response = self.client.post('/login', data={'username': self.username, 'password': 'test-password'})
        self.assertIn(response.status_code, (302, 303))
        with self.app.app_context():
            app_module.Product.query.filter(
                app_module.func.upper(app_module.Product.serial_number).like(f'SCANFIX{self.suffix}%')
            ).delete(synchronize_session=False)
            app_module.db.session.add(app_module.Product(
                serial_number=self.serial,
                name=self.catalog_name,
                room='Room 2',
                bsid=f'BS{self.suffix}',
                client_id=self.client_id,
                start_warranty_date=app_module.parse_date('2024-01-01'),
                end_warranty_date=app_module.parse_date('2027-01-01'),
            ))
            app_module.db.session.commit()

    def product(self, serial=None):
        with self.app.app_context():
            row = app_module.db.session.get(app_module.Product, serial or self.serial)
            return None if row is None else {
                'client_id': row.client_id, 'room': row.room, 'bsid': row.bsid,
                'start': row.start_warranty_date, 'end': row.end_warranty_date,
            }

    def import_csv(self, text):
        return self.client.post(
            '/import_products',
            data={'file': (io.BytesIO(text.encode('utf-8')), 'products.csv')},
            content_type='multipart/form-data',
        )

    def add(self, **overrides):
        payload = {
            'serial_number': f'{self.serial}N',
            'product_name_id': self.catalog_id,
            'client_id': self.client_id,
        }
        payload.update(overrides)
        return self.client.post('/add_product', json=payload)

    # Batch 1
    def test_import_without_columns_keeps_existing_fields(self):
        before = self.product()
        response = self.import_csv(f'Serial Number,Description\n{self.serial},{self.catalog_name}\n')
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.get_json()['updated'], 1)
        self.assertEqual(self.product(), before)

    def test_import_uppercases_serials_instead_of_adding_a_duplicate(self):
        response = self.import_csv(f'Serial Number,Description\n{self.serial.lower()},{self.catalog_name}\n')
        self.assertEqual(response.get_json()['updated'], 1)
        self.assertEqual(response.get_json()['created'], 0)
        self.assertIsNone(self.product(self.serial.lower()))

    def test_import_na_owner_is_not_unmatched_and_fuzzy_match_is_reported(self):
        response = self.import_csv(
            'Serial Number,Description,Current Owner\n'
            f'{self.serial},{self.catalog_name},N/A\n'
            f'{self.serial}F,{self.catalog_name},{self.client_name}x\n'
        )
        data = response.get_json()
        self.assertEqual(data['unresolved_owners'], 0)
        self.assertEqual(data['fuzzy_owner_matches'], 1)
        self.assertIn('matched approximately', data['message'])

    def test_add_rejects_bad_dates_unknown_client_and_long_serial(self):
        cases = [
            ({'start_warranty': '2026-13-45'}, 'start_warranty'),
            ({'start_warranty': '2026-10-01', 'end_warranty': '2020-01-01'}, 'end_warranty'),
            ({'client_id': 99999999}, 'client_id'),
            ({'serial_number': 'X' * 101}, 'serial_number'),
        ]
        for overrides, field in cases:
            with self.subTest(field=field):
                response = self.add(**overrides)
                self.assertEqual(response.status_code, 400, response.get_data(as_text=True))
                self.assertEqual(response.get_json()['field'], field)

    def test_update_rejects_end_before_start(self):
        response = self.client.put(f'/update_product/{self.serial}', json={
            'serial_number': self.serial,
            'product_name_id': self.catalog_id,
            'client_id': self.client_id,
            'start_warranty': '2026-10-01',
            'end_warranty': '2020-01-01',
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['field'], 'end_warranty')

    def test_delete_missing_serial_returns_404(self):
        response = self.client.delete(f'/delete_product/{self.serial}MISSING')
        self.assertEqual(response.status_code, 404)

    def test_unused_products_summary_route_removed(self):
        self.assertEqual(self.client.get('/get_products_summary').status_code, 404)


class ProductInventoryScanPageSourceTests(unittest.TestCase):
    # Batch 2
    def test_export_only_for_users_the_server_allows(self):
        self.assertIn('{% if is_standalone_inventory or product_can_delete %}', TEMPLATE)

    def test_save_has_busy_guard(self):
        save = TEMPLATE.split('async function saveProduct()', 1)[1].split('async function deleteProduct', 1)[0]
        self.assertIn('if (productSaveBusy) return;', save)
        self.assertIn('saveButton.disabled = true', save)
        self.assertIn('id="product-save-btn"', TEMPLATE)

    def test_no_database_error_prefix_and_status_wording(self):
        self.assertNotIn('Database Error: ', TEMPLATE)
        self.assertIn('<option value="Under Warranty">Under Warranty</option>', TEMPLATE)

    # Batch 3
    def test_labels_sort_state_and_phone_card_structure(self):
        for field in ('search-text', 'filter-cli-search', 'filter-status'):
            self.assertIn(f'for="{field}"', TEMPLATE)
        self.assertIn("btn.closest('th')?.setAttribute('aria-sort'", TEMPLATE)
        self.assertNotIn('class="product-mobile-card" onclick="openProductHistory(${productJsArg(p.serial_number)}, ${productJsArg(inventoryMode)})" role="button"', TEMPLATE)
        self.assertIn('class="product-mobile-name product-mobile-open"', TEMPLATE)
        self.assertIn('data-bs-dismiss="toast" aria-label="Close"', TEMPLATE)

    def test_hardcoded_slate_text_and_info_icon_removed(self):
        self.assertNotIn('color: #64748b;', TEMPLATE)
        self.assertNotIn('text-info"></i>', TEMPLATE)
        self.assertIn('<header class="dash-page-header no-print">', TEMPLATE)
        self.assertIn('btn btn-outline-primary product-print-btn', TEMPLATE)

    # Batch 4
    def test_modal_scrolls_focuses_and_edit_header_is_neutral(self):
        self.assertIn('modal-dialog modal-lg modal-dialog-scrollable', TEMPLATE)
        self.assertIn("addEventListener('shown.bs.modal'", TEMPLATE)
        self.assertIn('function setProductModalEditMode(isEdit)', TEMPLATE)

    def test_status_pills_replace_solid_badges(self):
        self.assertNotIn('bg-danger">Expired - No Contract', TEMPLATE)
        for modifier in ('warranty', 'contract', 'expired', 'none'):
            self.assertIn(f'.product-status-pill--{modifier} {{', TEMPLATE)
            self.assertIn(f':root[data-app-theme="dark"] .product-status-pill--{modifier} {{', TEMPLATE)

    def test_phone_more_menu_and_filter_toggle(self):
        self.assertIn('class="dropdown product-more-actions"', TEMPLATE)
        self.assertIn('function toggleProductFilters()', TEMPLATE)
        self.assertIn("label.textContent = count ? `Filter (${count})` : 'Filter';", TEMPLATE)

    def test_history_dates_and_heading(self):
        self.assertIn('function formatProductHistoryDate(value)', TEMPLATE)
        self.assertIn('formatProductHistoryDate(row.approved_at)', TEMPLATE)
        self.assertNotIn('MEDICAL SERVICE {{ inventory_label }} Inventory', TEMPLATE)

    def test_server_helpers_present(self):
        self.assertIn('def product_payload_error(d, serial_number, client_id):', APP_SOURCE)
        self.assertIn('def csv_find_client_match(owner_name):', APP_SOURCE)
        self.assertNotIn("@app.route('/get_products_summary')", APP_SOURCE)


if __name__ == '__main__':
    unittest.main()
