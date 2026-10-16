"""Genoray and Vieworks scan fixes (plans.md, 2026-10-16, batches 1-4)."""

import io
import os
import pathlib
import tempfile
import unittest
import uuid

from sqlalchemy import event

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_brand_scan_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB_PATH))
os.environ.setdefault("SECRET_KEY", "brand-inventory-scan-tests")

import app as app_module  # noqa: E402

TEMPLATE = (ROOT / "templates" / "products.html").read_text(encoding="utf-8")
APP_SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")


class BrandInventoryServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=True)
        cls.suffix = uuid.uuid4().hex[:8].upper()
        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_product_contract_column()
            app_module.ensure_genoray_item_table()
            app_module.ensure_vieworks_item_table()
            app_module.ensure_product_vieworks_link_table()
            admin = app_module.User(username=f"brand-scan-admin-{cls.suffix}", password="test", role="admin", is_active=True)
            one = app_module.Client(name=f"Brand Scan Center One {cls.suffix}", address="A")
            two = app_module.Client(name=f"Brand Scan Center Two {cls.suffix}", address="B")
            app_module.db.session.add_all([admin, one, two])
            app_module.db.session.flush()
            machine = app_module.Product(serial_number=f"BSM-{cls.suffix}", name="Scan Machine", client_id=one.id)
            app_module.db.session.add(machine)
            app_module.db.session.commit()
            cls.admin_id, cls.one_id, cls.two_id = admin.id, one.id, two.id
            cls.one_name, cls.two_name = one.name, two.name
            cls.machine = machine.serial_number

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            pattern = f"%{cls.suffix}"
            app_module.ProductVieworksLink.query.filter(
                app_module.ProductVieworksLink.vieworks_serial.like(pattern)
            ).delete(synchronize_session=False)
            for model in (app_module.VieworksItem, app_module.GenorayItem, app_module.Product):
                model.query.filter(model.serial_number.like(pattern)).delete(synchronize_session=False)
            app_module.Client.query.filter(app_module.Client.id.in_([cls.one_id, cls.two_id])).delete(
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

    def add(self, brand, tag, **extra):
        serial = f"BS{brand[0].upper()}-{tag}-{self.suffix}"
        payload = {'serial_number': serial, 'name': f'{brand} {tag}', 'client_id': self.one_id,
                   'start_warranty': '2026-01-01', 'end_warranty': '2027-01-01', 'room': 'Room 1', **extra}
        response = self.client.post(f'/api/{brand}/items', json=payload)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return serial

    def import_csv(self, brand, text):
        return self.client.post(
            f'/{brand}/import',
            data={'file': (io.BytesIO(text.encode('utf-8')), 'scan.csv')},
            content_type='multipart/form-data',
        ).get_json()

    def item(self, brand, serial):
        model = app_module.VieworksItem if brand == 'vieworks' else app_module.GenorayItem
        with self.app.app_context():
            return app_module.db.session.get(model, serial)

    def test_import_keeps_fields_whose_column_is_missing(self):
        for brand in ('genoray', 'vieworks'):
            with self.subTest(brand=brand):
                serial = self.add(brand, 'KEEP')
                result = self.import_csv(brand, f"Serial Number,Description\n{serial},Renamed\n")
                self.assertEqual(result['updated'], 1, result)
                row = self.item(brand, serial)
                self.assertEqual(row.name, 'Renamed')
                self.assertEqual(row.client_id, self.one_id)
                self.assertEqual(row.room, 'Room 1')
                self.assertEqual(row.start_warranty_date.isoformat(), '2026-01-01')
                self.assertEqual(row.end_warranty_date.isoformat(), '2027-01-01')

    def test_import_treats_na_owner_as_blank_and_counts_fuzzy_matches(self):
        for brand in ('genoray', 'vieworks'):
            with self.subTest(brand=brand):
                serial = self.add(brand, 'NA', client_id=None)
                result = self.import_csv(brand, f"Serial Number,Description,Current Owner\n{serial},X,N/A\n")
                self.assertEqual(result['unresolved_owners'], 0, result)
                self.assertIsNone(self.item(brand, serial).client_id)
                fuzzy = self.import_csv(
                    brand, f'Serial Number,Description,Current Owner\n{serial},X,"{self.two_name}x"\n'
                )
                self.assertEqual(fuzzy['fuzzy_owner_matches'], 1, fuzzy)
                self.assertIn('matched approximately', fuzzy['message'])

    def test_vieworks_import_cannot_move_linked_item_to_another_center(self):
        serial = self.add('vieworks', 'LINK', linked_product_serial=self.machine)
        result = self.import_csv(
            'vieworks', f'Serial Number,Description,Current Owner\n{serial},Moved,"{self.two_name}"\n'
        )
        self.assertEqual(result['link_conflicts'], 1, result)
        self.assertEqual(result['updated'], 0, result)
        self.assertIn("machine's medical center", result['message'])
        self.assertEqual(self.item('vieworks', serial).client_id, self.one_id)
        with self.app.app_context():
            link = app_module.ProductVieworksLink.query.filter_by(vieworks_serial=serial).one()
            self.assertEqual(link.product_serial, self.machine)
        same_center = self.import_csv(
            'vieworks', f'Serial Number,Description,Current Owner\n{serial},Kept,"{self.one_name}"\n'
        )
        self.assertEqual(same_center['updated'], 1, same_center)

    def test_delete_missing_item_returns_404(self):
        for brand, label in (('genoray', 'Genoray'), ('vieworks', 'Vieworks')):
            with self.subTest(brand=brand):
                response = self.client.delete(f'/api/{brand}/items/NOPE-{self.suffix}')
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.get_json()['message'], f'{label} item not found.')

    def test_list_matches_per_item_serializer_with_flat_query_count(self):
        linked = self.add('vieworks', 'LIST1', linked_product_serial=self.machine)
        self.add('vieworks', 'LIST2')
        self.add('genoray', 'LIST1')
        for brand, serializer, model in (
            ('vieworks', app_module.vieworks_item_to_dict, app_module.VieworksItem),
            ('genoray', app_module.genoray_item_to_dict, app_module.GenorayItem),
        ):
            with self.subTest(brand=brand):
                rows = self.client.get(f'/api/{brand}/items').get_json()
                with self.app.test_request_context():
                    expected = {item.serial_number: serializer(item) for item in model.query.all()}
                for row in rows:
                    self.assertEqual(row, expected[row['serial_number']])
        listed = {row['serial_number']: row for row in self.client.get('/api/vieworks/items').get_json()}
        self.assertEqual(listed[linked]['linked_product']['serial_number'], self.machine)

        def count_queries(brand):
            counter = {'n': 0}

            def before(*_args):
                counter['n'] += 1

            with self.app.app_context():
                engine = app_module.db.engine
            event.listen(engine, 'before_cursor_execute', before)
            try:
                self.client.get(f'/api/{brand}/items')
            finally:
                event.remove(engine, 'before_cursor_execute', before)
            return counter['n']

        for brand in ('genoray', 'vieworks'):
            with self.subTest(brand=brand, step='queries'):
                before_count = count_queries(brand)
                for index in range(4):
                    self.add(brand, f'Q{index}')
                self.assertEqual(count_queries(brand), before_count)

    def test_access_helpers_have_no_unused_role_variable(self):
        for name in ('can_access_genoray_inventory', 'can_access_vieworks_inventory'):
            start = APP_SOURCE.index(f'def {name}(')
            body = APP_SOURCE[start:APP_SOURCE.index('\ndef ', start + 1)]
            self.assertNotIn('role = ', body, name)


class BrandInventoryTemplateTests(unittest.TestCase):
    def test_serial_change_text_names_schedules_and_pm_visits(self):
        self.assertIn('Its schedules and PM visits move with it, and an activity log is created.', TEMPLATE)
        self.assertIn('Its schedules and PM visits move to the new serial', TEMPLATE)
        self.assertIn('Moved ${movedSchedules} schedule(s) and ${movedPmVisits} PM visit(s) to the new serial.', TEMPLATE)

    def test_brand_labels_keep_capitals(self):
        self.assertNotIn('inventoryPlural.toLowerCase()', TEMPLATE)
        self.assertIn('source === inventoryMode ? inventoryLabel', TEMPLATE)
        self.assertIn("{% set inventory_name_label = 'Equipment Name' if is_standalone_inventory else 'Product Name' %}", TEMPLATE)
        self.assertIn('placeholder="S/N or {{ inventory_name_label }}"', TEMPLATE)
        self.assertIn("setProductSort('name')\">{{ inventory_name_label }} <span", TEMPLATE)

    def test_delete_toast_and_single_bsid_rule(self):
        self.assertIn("productToast(isStandaloneInventory ? `${inventoryLabel} item deleted.` : 'Product deleted.', 'success');", TEMPLATE)
        self.assertIn('bsidField.disabled = isStandaloneInventory;', TEMPLATE)
        self.assertNotIn('bsidField.disabled = isGenorayInventory;', TEMPLATE)

    def test_pm_buttons_have_dark_theme_pair(self):
        self.assertIn(':root[data-app-theme="dark"] .product-row-pm,\n    :root[data-app-theme="dark"] .product-mobile-pm {', TEMPLATE)

    def test_vieworks_rows_show_linked_machine_and_empty_state_has_next_step(self):
        self.assertIn('function renderVieworksLinkedProduct(item, mobile=false){', TEMPLATE)
        self.assertIn('${renderVieworksLinkedProduct(p, true)}', TEMPLATE)
        self.assertIn('${renderVieworksLinkedProduct(p)}', TEMPLATE)
        # The link line wraps under the name + actions instead of squeezing the name.
        self.assertIn('.product-name-content { flex-wrap: wrap; }', TEMPLATE)
        self.assertIn('.product-name-content > .product-linked-vieworks {\n        order: 3;\n        flex-basis: 100%;', TEMPLATE)
        self.assertIn("`No ${inventoryPlural} yet. Use Add ${inventoryLabel} Item${productCanDelete ? ' or Import' : ''} to create the first one.`", TEMPLATE)


if __name__ == '__main__':
    unittest.main()
