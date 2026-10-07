"""Product Inventory Batch 1: safe handlers, text-only autocomplete, forced rename."""

import datetime
import pathlib
import re
import unittest
import uuid
from urllib.parse import quote

import app as app_module


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / 'templates' / 'products.html').read_text(encoding='utf-8')


def function_body(name):
    """Return the source of one top-level JS function in products.html."""
    match = re.search(r'(?:async\s+)?function ' + re.escape(name) + r'\s*\(', TEMPLATE)
    if not match:
        return ''
    depth = 0
    start = TEMPLATE.index('{', match.end())
    for index in range(start, len(TEMPLATE)):
        if TEMPLATE[index] == '{':
            depth += 1
        elif TEMPLATE[index] == '}':
            depth -= 1
            if depth == 0:
                return TEMPLATE[match.start():index + 1]
    return ''


class ProductInventoryTemplateTests(unittest.TestCase):
    def test_handlers_never_quote_escaped_html_as_js_strings(self):
        self.assertIsNone(re.search(r"\('\$\{(escapeHtml|productEscape)\(", TEMPLATE))
        self.assertIsNone(re.search(r", '\$\{(escapeHtml|productEscape|inventoryMode)", TEMPLATE))
        self.assertIn('function productJsArg(', TEMPLATE)
        self.assertIn('openEditModal(${productJsArg(', TEMPLATE)
        self.assertIn('deleteProduct(${productJsArg(', TEMPLATE)
        self.assertIn('openProductHistory(${productJsArg(', TEMPLATE)

    def test_highlight_escapes_serial_selector(self):
        self.assertIn('CSS.escape(serial)', function_body('highlightAndScroll'))

    def test_autocomplete_renders_client_names_as_text(self):
        body = function_body('setupAutocomplete')
        self.assertNotIn('innerHTML = `<strong>', body)
        self.assertIn('textContent = displayName', body)

    def test_status_chips_sit_above_table_and_filter(self):
        self.assertNotIn('fa-shield-check', TEMPLATE)
        self.assertLess(TEMPLATE.index('id="product-status-chips"'), TEMPLATE.index('id="product-table-wrap"'))
        self.assertIn('<input type="hidden" id="filter-status" value="">', TEMPLATE)
        chips = function_body('renderProductStatusChips')
        self.assertIn('productsData.filter(productMatchesTextFilters)', chips)
        self.assertIn('aria-pressed', chips)
        self.assertIn('field.value === value ? \'\' : value', function_body('setProductStatusFilter'))

    def test_phone_toolbar_and_paged_cards(self):
        self.assertIn('id="product-filter-toggle"', TEMPLATE)
        self.assertIn('aria-controls="product-client-filter"', TEMPLATE)
        self.assertIn('class="dropdown product-more-actions"', TEMPLATE)
        self.assertEqual(TEMPLATE.count('product-header-action'), 4)  # Import, Export, Print + CSS rule
        self.assertIn('const PRODUCT_MOBILE_PAGE_SIZE = 20;', TEMPLATE)
        cards = function_body('renderProductMobileCards')
        self.assertIn('data.slice(0, productMobileVisible)', cards)
        self.assertIn('productMobileVisible = PRODUCT_MOBILE_PAGE_SIZE', cards)
        self.assertIn('.focus()', function_body('showMoreProductMobileCards'))

    def test_save_refreshes_vieworks_options_and_warns_about_po_owner(self):
        self.assertIn('async function loadVieworksLinkOptions(', TEMPLATE)
        save = function_body('saveProduct')
        self.assertIn('loadVieworksLinkOptions()', save)
        self.assertIn('linked_purchase_order_count', save)

    def test_desktop_rows_open_history_from_keyboard(self):
        render = function_body('renderTable')
        self.assertIn('tabindex="0"', render)
        self.assertIn('event.target===this', render)
        self.assertIn('.product-clickable-row:focus-visible', TEMPLATE)

    def test_legacy_name_edit_clears_field_and_names_old_value(self):
        self.assertIn('setProductNameForEdit(p.name)', function_body('openEditModal'))
        helper = function_body('setProductNameForEdit')
        self.assertIn('Pick a standard name (was: ', helper)
        self.assertIn("input.value = isLegacy ? ''", helper)
        self.assertIn('is not in the Product Name list. Pick a standard name before saving.', TEMPLATE)
        save = function_body('saveProduct')
        self.assertIn('Select a standard Product Name from the list before saving.', save)


class ProductOwnerChangePurchaseOrderCountTests(unittest.TestCase):
    """Positive control: the server reports linked P.O.s that step 6 surfaces."""

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.suffix = uuid.uuid4().hex[:10]
        cls.username = f'product_b1_admin_{cls.suffix}'
        cls.serial = f'B1-{cls.suffix}'.upper()
        app_module.SUPERADMIN_USERNAMES.add(cls.username)

        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_product_contract_column()
            app_module.ensure_purchase_order_schema()
            app_module.ensure_product_name_catalog()
            catalog = app_module.ProductNameCatalog(name=f'Batch1 Catalog {cls.suffix}')
            user = app_module.User(
                username=cls.username,
                password=app_module.generate_password_hash('test-password'),
                role='superadmin',
                is_active=True,
            )
            old_client = app_module.Client(name=f'Batch1 Old {cls.suffix}', address='A')
            new_client = app_module.Client(name=f'Batch1 New {cls.suffix}', address='B')
            app_module.db.session.add_all([catalog, user, old_client, new_client])
            app_module.db.session.flush()
            product = app_module.Product(
                serial_number=cls.serial, name=catalog.name, client_id=old_client.id
            )
            app_module.db.session.add(product)
            app_module.db.session.flush()
            order = app_module.PurchaseOrder(
                client_id=old_client.id,
                po_number=f'PO-{cls.suffix}',
                po_date=datetime.date(2026, 1, 1),
            )
            order.machines.append(app_module.PurchaseOrderMachine(product_serial=cls.serial, position=0))
            app_module.db.session.add(order)
            app_module.db.session.commit()
            cls.ids = {
                'catalog': catalog.id, 'user': user.id, 'old': old_client.id,
                'new': new_client.id, 'order': order.id,
            }

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            session = app_module.db.session
            order = session.get(app_module.PurchaseOrder, cls.ids['order'])
            if order:
                session.delete(order)
                session.flush()
            product = session.get(app_module.Product, cls.serial)
            if product:
                session.delete(product)
                session.flush()
            for model, key in (
                (app_module.Client, 'old'), (app_module.Client, 'new'),
                (app_module.User, 'user'), (app_module.ProductNameCatalog, 'catalog'),
            ):
                row = session.get(model, cls.ids[key])
                if row:
                    session.delete(row)
            session.commit()
        app_module.SUPERADMIN_USERNAMES.discard(cls.username)

    def test_owner_change_reports_linked_purchase_orders(self):
        client = self.app.test_client()
        # Session login avoids spending the shared /login rate limit other modules rely on.
        with client.session_transaction() as session:
            session['_user_id'] = str(self.ids['user'])
            session['_fresh'] = True
        response = client.put(f'/update_product/{quote(self.serial, safe="")}', json={
            'serial_number': self.serial,
            'product_name_id': self.ids['catalog'],
            'client_id': self.ids['new'],
        })
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertGreaterEqual(response.get_json().get('linked_purchase_order_count', 0), 1)


if __name__ == '__main__':
    unittest.main()
