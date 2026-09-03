import json
import pathlib
import unittest
import uuid
from datetime import timedelta
from types import SimpleNamespace


ROOT = pathlib.Path(__file__).resolve().parents[1]

# tests/__init__.py pins a fresh MEDICAL_SERVICE_TEST_DB for the whole run, so importing the
# app here cannot touch the real scheduler.db. Branch resolution and the write guard are
# tested by calling them rather than by matching source text: an authorization rule that is
# only asserted as a string can be refactored into something that no longer holds.
import app as app_module  # noqa: E402


class StockInventorySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.layout_source = (ROOT / 'templates' / 'layout.html').read_text(encoding='utf-8')
        cls.page_source = (ROOT / 'templates' / 'stock_inventory.html').read_text(encoding='utf-8')
        cls.dashboard_source = (ROOT / 'templates' / 'stock_inventory_dashboard.html').read_text(encoding='utf-8')
        cls.settings_source = (ROOT / 'templates' / 'settings.html').read_text(encoding='utf-8')
        cls.engineers_source = (ROOT / 'templates' / 'engineers.html').read_text(encoding='utf-8')

    def test_branch_inventory_module_and_additive_tables_exist(self):
        self.assertIn("@app.route('/stock_inventory')", self.app_source)
        self.assertIn('if not stock_inventory_can_view()', self.app_source)
        self.assertIn("stock_inventory_branch_for_user(requested_branch=request.args.get('branch'))", self.app_source)
        self.assertIn('def stock_inventory_view_api_guard', self.app_source)
        self.assertIn('def stock_inventory_api_guard', self.app_source)
        self.assertIn("__tablename__ = 'stock_inventory_item'", self.app_source)
        self.assertIn("__tablename__ = 'stock_inventory_movement'", self.app_source)
        self.assertIn("db.UniqueConstraint('branch_code', 'scan_barcode'", self.app_source)
        self.assertIn('ensure_stock_inventory_tables()', self.app_source)
        # Sidebar links render through the nav_link() macro in layout.html.
        self.assertIn("nav_link('/stock_inventory', 'fa-barcode', 'Stock Inventory')", self.layout_source)
        self.assertIn('{% if stock_inventory_view %}', self.layout_source)

    def test_engineer_read_only_access_and_branch_resolution_exist(self):
        for marker in (
            'def stock_inventory_can_view',
            'def stock_inventory_read_only_user',
            "'MANILA': 'BC01'",
            "'CEBU': 'BC02'",
            "'DAVAO': 'BC03'",
            'if stock_inventory_read_only_user(target):',
            'stock_inventory_branch_from_engineer_profile(profile)',
            'stock_inventory_managed_branch_codes',
            'STOCK_INVENTORY_ASSIGNMENT_VIEW_BRANCHES',
            'stock_read_only',
            'readOnly:',
        ):
            self.assertIn(marker, self.app_source if marker != 'stock_read_only' and marker != 'readOnly:' else self.page_source)

    def test_borrowed_inventory_projection_is_present(self):
        self.assertIn("@app.route('/api/stock-inventory/borrowed')", self.app_source)
        for marker in ('def stock_inventory_current_borrowings', 'borrowed_at_display', 'Currently Borrowed Items', 'Borrowed By'):
            self.assertIn(marker, self.app_source if marker == 'def stock_inventory_current_borrowings' or marker == 'borrowed_at_display' else self.page_source)
        self.assertIn('loadStockBorrowed()', self.page_source)
        self.assertIn('renderStockBorrowed()', self.page_source)

    def test_borrowed_pagination_and_collapse_contracts_are_present(self):
        for marker in (
            'id="stockBorrowedToggle"',
            'aria-controls="stockBorrowedContent"',
            'id="stockBorrowedContent"',
            'id="stockBorrowedPagination"',
            'id="stockBorrowedPrev"',
            'id="stockBorrowedNext"',
            'function toggleStockBorrowed',
            'function changeStockBorrowedPage',
            'function renderStockBorrowedPagination',
            'STOCK_BORROWED_COLLAPSED_STORAGE_KEY',
            'localStorage.getItem(STOCK_BORROWED_COLLAPSED_STORAGE_KEY)',
            'localStorage.setItem(STOCK_BORROWED_COLLAPSED_STORAGE_KEY',
            'borrowedPage',
            'borrowedRequestId',
            'data.total',
            'data.total_pages',
            'aria-expanded',
        ):
            self.assertIn(marker, self.page_source)
        for marker in (
            "request.args.get('page')",
            "'total_pages'",
            "'per_page'",
            "'total'",
        ):
            self.assertIn(marker, self.app_source)
        self.assertIn('medical-service-pwa-offline-navigation-v125-timeline-collapsed-preference', self.app_source)

    def test_read_only_ui_has_no_mutation_controls(self):
        self.assertIn('id="stockAddItemButton"', self.page_source)
        self.assertIn('addButton.hidden=stockState.readOnly', self.page_source)
        self.assertIn('if(stockState.readOnly) return', self.page_source)
        self.assertIn('No item was found for that barcode in your branch.', self.page_source)

    def test_scanner_and_transaction_controls_are_present(self):
        for marker in (
            'Scan / Enter Barcode',
            'lookupScannedBarcode',
            "event.key==='Enter'",
            "chooseStockDirection('IN')",
            "chooseStockDirection('OUT')",
            'Borrowed By',
            'Returned By',
            'movementEngineerSearch',
            'Reverse Transaction',
            'Out of Stock',
            'QTY',
        ):
            self.assertIn(marker, self.page_source)
        self.assertNotIn('Opening Quantity', self.page_source)
        self.assertNotIn('Minimum Stock', self.page_source)

    def test_api_surface_and_rules_are_present(self):
        for route in (
            "@app.route('/api/stock-inventory/borrowed')",
            "@app.route('/api/stock-inventory/summary')",
            "@app.route('/api/stock-inventory/items')",
            "@app.route('/api/stock-inventory/lookup', methods=['POST'])",
            "@app.route('/api/stock-inventory/items', methods=['POST'])",
            "@app.route('/api/stock-inventory/engineers')",
            "@app.route('/api/stock-inventory/movements', methods=['POST'])",
            "@app.route('/api/stock-inventory/movements/<int:movement_id>/reverse', methods=['POST'])",
        ):
            self.assertIn(route, self.app_source)
        self.assertIn("STOCK_IN_REASONS = {'Return', 'Restock', 'Adjustment'}", self.app_source)
        self.assertIn("'BC02': 'Cebu'", self.app_source)
        self.assertIn("'BC03': 'Davao'", self.app_source)
        self.assertIn('stock_inventory_request_branch(payload)', self.app_source)
        self.assertIn('stock_inventory_request_branch(payload, require_write=True)', self.app_source)
        self.assertIn('StockInventoryItem.current_quantity >= quantity', self.app_source)
        self.assertIn("'This movement has already been reversed.'", self.app_source)

    def test_inventory_only_access_and_dashboard_are_present(self):
        for marker in ('can_manage_stock_inventory', 'stock_inventory_only', 'stock_inventory_branch_code'):
            self.assertIn(marker, self.app_source)
        self.assertIn('restrict_stock_inventory_only_accounts', self.app_source)
        self.assertIn('Stock Inventory-only view', self.settings_source)
        self.assertIn('Assigned Inventory Branch', self.settings_source)
        self.assertIn('value="BC02_BC03"', self.settings_source)
        self.assertIn('Cebu + Davao', self.settings_source)
        self.assertIn('Cebu + Davao', self.engineers_source)
        self.assertIn('value="BC02_BC03"', self.engineers_source)
        self.assertIn('Inventory Dashboard', self.dashboard_source)

    def test_disabling_inventory_access_clears_inventory_only_mode(self):
        self.assertIn('function toggleStockInventoryAccess(input)', self.settings_source)
        self.assertIn('if (inventoryOnly) inventoryOnly.checked = false;', self.settings_source)
        self.assertIn('if not stock_inventory_requested:', self.app_source)
        self.assertIn('stock_inventory_only_requested = False', self.app_source)

    def test_superadmin_inventory_access_is_configurable(self):
        self.assertIn('stock_inventory_permission_initialized', self.app_source)
        self.assertIn('target_user.stock_inventory_permission_initialized = True', self.app_source)
        self.assertIn("bool(getattr(target, 'can_manage_stock_inventory', False))", self.app_source)
        self.assertIn('is_superadmin_user(target) or', self.app_source)
        self.assertNotIn('stock_inventory_access_locked', self.settings_source)

    def test_activity_log_has_distinct_stock_category(self):
        self.assertIn("'Stock Inventory': {'icon': 'fa-barcode'", self.app_source)
        self.assertIn("if 'stock inventory' in text:", self.app_source)
        self.assertIn("return 'Stock Inventory'", self.app_source)

    def test_release_manifest_contains_stock_inventory(self):
        manifest = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))
        release = next(item for item in manifest['releases'] if item['release_key'] == '2026-07-21')
        self.assertTrue(release['is_published'])
        self.assertTrue(any(item['item_key'] == '2026-07-21-stock-inventory' for item in release['items']))

    def test_release_manifest_contains_engineer_read_only_inventory_view(self):
        manifest = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))
        release = next(item for item in manifest['releases'] if item['release_key'] == '2026-08-03')
        self.assertTrue(any(item['item_key'] == '2026-08-03-engineer-stock-inventory-view' for item in release['items']))

    def test_search_contracts_cover_backend_fields_and_literal_terms(self):
        for marker in (
            'def stock_inventory_search_terms',
            'def stock_inventory_search_pattern',
            'def stock_inventory_apply_search',
            "StockInventoryItem.notes",
            "escape='\\\\'",
        ):
            self.assertIn(marker, self.app_source)
        movement_source = self.app_source.split('def get_stock_inventory_movements():', 1)[1].split(
            "@app.route('/api/stock-inventory/engineers')", 1
        )[0]
        for marker in (
            "request.args.get('q')",
            'Engineer.employee_id',
            'User.username',
            'StockInventoryMovement.remarks',
            'StockInventoryMovement.source_or_returned_by',
        ):
            self.assertIn(marker, movement_source)

    def test_shared_search_controls_and_loaders_are_present(self):
        for marker in (
            'id="stockClearSearch"',
            'id="stockSearchCount"',
            'id="stockIncludeInactiveWrap"',
            'historyItemId',
            'itemRequestId',
            'movementRequestId',
            'function updateStockSearchControls',
            'function loadStockSearchResults',
            'loadStockSearchResults()',
            'requestId!==stockState.itemRequestId',
            'requestId!==stockState.movementRequestId',
            'scopedItemId!==(stockState.historyItemId || null)',
            'No stock items match your search.',
            'No stock movements match your search.',
        ):
            self.assertIn(marker, self.page_source)
        self.assertIn('medical-service-pwa-offline-navigation-v125-timeline-collapsed-preference', self.app_source)

    def test_item_history_scope_and_clear_search_contracts_are_explicit(self):
        show_history = self.page_source.split('function showItemHistory(', 1)[1].split(
            '\n\nasync function lookupScannedBarcode', 1
        )[0]
        switch_tab = self.page_source.split('function switchStockTab(', 1)[1].split(
            'function showItemHistory(', 1
        )[0]
        self.assertIn('stockState.historyItemId=itemId', show_history)
        self.assertIn('stockSearchInput.value=\'\'', show_history)
        self.assertIn('loadStockMovements(itemId)', show_history)
        self.assertIn('stockState.historyItemId=null', switch_tab)
        self.assertIn('function clearStockSearch', self.page_source)

    def test_release_manifest_contains_stock_inventory_search(self):
        manifest = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))
        release = next(item for item in manifest['releases'] if item['release_key'] == '2026-09-03-stock-inventory-search')
        self.assertTrue(release['is_published'])
        self.assertTrue(any(
            item['item_key'] == '2026-09-03-stock-inventory-search-everyone'
            and 'everyone' in item['audiences']
            for item in release['items']
        ))

    def test_release_manifest_contains_borrowed_pagination(self):
        manifest = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))
        release = next(item for item in manifest['releases'] if item['release_key'] == '2026-09-03-stock-inventory-borrowed-pagination')
        self.assertTrue(release['is_published'])
        self.assertTrue(any(
            item['item_key'] == '2026-09-03-stock-inventory-borrowed-pagination-everyone'
            and 'everyone' in item['audiences']
            for item in release['items']
        ))


class StockInventoryBranchResolutionTests(unittest.TestCase):
    """Free-text branch names resolve for engineers, and nowhere else.

    Adding the read-only engineer view meant mapping `Engineer.branch` -- which holds
    'Manila', 'Cebu', 'Davao' -- onto BC01/BC02/BC03. That tolerance was briefly added to
    `normalize_stock_inventory_branch`, which also guards the assigned
    `User.stock_inventory_branch_code`, so a stale or mistyped value there would have become
    working access to a branch instead of being refused. The one explicit multi-branch
    assignment is represented by its exact code and expanded only when resolving access.
    """

    def test_the_assigned_branch_field_accepts_codes_only(self):
        for rejected in ('Cebu', 'MANILA', 'davao branch', 'main', 'BC99', '', None):
            self.assertEqual(
                app_module.normalize_stock_inventory_branch(rejected), '',
                f'{rejected!r} must not resolve to a branch on the assigned-code path'
            )

    def test_the_assigned_branch_field_still_accepts_real_codes(self):
        """Positive control: the strict path must not reject everything."""
        for code in ('BC01', 'BC02', 'BC03'):
            self.assertEqual(app_module.normalize_stock_inventory_branch(code), code)
            self.assertEqual(app_module.normalize_stock_inventory_branch(code.lower()), code)

    def test_cebu_davao_is_one_assignment_with_two_physical_branches(self):
        self.assertEqual(app_module.normalize_stock_inventory_branch('BC02_BC03'), 'BC02_BC03')
        self.assertEqual(
            app_module.stock_inventory_assignment_branch_codes('BC02_BC03'),
            ('BC02', 'BC03'),
        )
        self.assertEqual(
            app_module.stock_inventory_assignment_branch_codes('BC02_BC03'.lower()),
            ('BC02', 'BC03'),
        )

    def test_combined_manager_can_view_manila_but_manages_only_cebu_and_davao(self):
        manager = SimpleNamespace(
            is_authenticated=True,
            is_active=True,
            username='combined_inventory_manager',
            role='staff',
            can_manage_stock_inventory=True,
            stock_inventory_branch_code='BC02_BC03',
        )
        with app_module.app.test_request_context('/'):
            self.assertEqual(
                app_module.stock_inventory_allowed_branch_codes(manager),
                ('BC01', 'BC02', 'BC03'),
            )
            self.assertEqual(
                tuple(app_module.stock_inventory_branch_options_for_user(manager).keys()),
                ('BC01', 'BC02', 'BC03'),
            )
            self.assertEqual(
                app_module.stock_inventory_branch_for_user(manager, 'BC02'),
                'BC02',
            )
            self.assertEqual(
                app_module.stock_inventory_branch_for_user(manager, 'BC03'),
                'BC03',
            )
            self.assertEqual(
                app_module.stock_inventory_branch_for_user(manager, 'BC01'),
                'BC01',
            )
            self.assertEqual(
                app_module.stock_inventory_branch_for_user(manager),
                'BC02',
            )
            self.assertFalse(app_module.stock_inventory_can_manage_branch('BC01', manager))
            self.assertTrue(app_module.stock_inventory_can_manage_branch('BC02', manager))
            self.assertTrue(app_module.stock_inventory_can_manage_branch('BC03', manager))
            self.assertEqual(
                app_module.stock_inventory_branch_for_write(manager, 'BC01'),
                '',
            )
            self.assertEqual(
                app_module.changelog_user_branch_codes(manager),
                {'BC02', 'BC03'},
            )
            self.assertEqual(app_module.changelog_user_branch(manager), '')

    def test_engineer_profile_branches_resolve(self):
        cases = {'Manila': 'BC01', 'Cebu': 'BC02', 'Davao': 'BC03', 'BC02': 'BC02'}
        for branch, expected in cases.items():
            profile = SimpleNamespace(branch=branch)
            self.assertEqual(app_module.stock_inventory_branch_from_engineer_profile(profile), expected)

    def test_an_unknown_engineer_branch_denies_rather_than_defaulting(self):
        """Defaulting would put an engineer in someone else's branch."""
        for branch in ('Baguio', '', None, 'BC99'):
            self.assertEqual(
                app_module.stock_inventory_branch_from_engineer_profile(SimpleNamespace(branch=branch)), ''
            )

    def test_the_two_paths_stay_separate(self):
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        strict = source.split('def normalize_stock_inventory_branch(')[1].split('\ndef ')[0]
        self.assertNotIn('STOCK_INVENTORY_BRANCH_ALIASES', strict,
                         'alias tolerance must not leak back into the assigned-code path')
        resolver = source.split('def stock_inventory_branch_from_engineer_profile(')[1].split('\ndef ')[0]
        self.assertIn('STOCK_INVENTORY_BRANCH_ALIASES', resolver)


class StockInventorySuperadminBypassTests(unittest.TestCase):
    """The superadmin bypass in can_manage_stock_inventory is deliberate, and bounded.

    `is_superadmin_user` is a hardcoded username allowlist rather than a settable flag, and
    `stock_inventory_can_administer` already grants those accounts the admin surface, so
    un-ticking the toggle for a superadmin never withheld anything. Pinned here so it cannot
    quietly widen to ordinary accounts.
    """

    def test_the_bypass_is_limited_to_superadmins(self):
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        guard = source.split('def can_manage_stock_inventory(')[1].split('\ndef ')[0]
        self.assertIn('is_superadmin_user(target)', guard)
        self.assertIn("getattr(target, 'can_manage_stock_inventory', False)", guard)

    def test_an_ordinary_account_still_needs_the_flag(self):
        """Positive control: without the flag and without superadmin, write access is refused."""
        ordinary = SimpleNamespace(
            is_authenticated=True, is_active=True, role='engineer',
            username='ordinary_engineer', can_manage_stock_inventory=False,
        )
        with app_module.app.test_request_context('/'):
            self.assertFalse(app_module.can_manage_stock_inventory(ordinary))
            self.assertFalse(app_module.is_superadmin_user(ordinary))


class StockInventorySettingsSwitchTests(unittest.TestCase):
    """The Settings switches must report the stored grant, not the effective permission.

    approval_user_to_dict() drives those switches and saveApprovalUser() posts the rendered
    state straight back, so a computed value silently rewrites what it displayed: the
    inventory switch rendered checked for every superadmin with nothing granted, and saving
    any unrelated change on their card then wrote can_manage_stock_inventory=True plus an
    audit line for a grant nobody performed.

    This is about the serializer only. The superadmin bypass inside
    can_manage_stock_inventory() is deliberate, documented, and pinned by the class above --
    the first test here asserts it still holds, so reporting the stored value cannot be
    mistaken for revoking admin access.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.created_user_ids = []

        with cls.app.app_context():
            app_module.db.create_all()

            cls.superadmin = app_module.User.query.filter_by(username='jonamar').first()
            if not cls.superadmin:
                cls.superadmin = app_module.User(
                    username='jonamar',
                    password=app_module.generate_password_hash('test-password'),
                    role='superadmin', is_active=True,
                )
                app_module.db.session.add(cls.superadmin)
                app_module.db.session.flush()
                cls.created_user_ids.append(cls.superadmin.id)

            # Whatever an earlier module left behind, this class needs the superadmin to
            # hold no explicit inventory grant -- that is the whole precondition.
            cls.superadmin.can_manage_stock_inventory = False
            cls.superadmin.stock_inventory_only = False

            cls.granted = app_module.User(
                username='stock_grantee_settings_switch',
                password=app_module.generate_password_hash('test-password'),
                role='staff', is_active=True,
                can_manage_stock_inventory=True,
                stock_inventory_only=True,
                stock_inventory_branch_code='BC02',
            )
            app_module.db.session.add(cls.granted)
            app_module.db.session.flush()
            cls.created_user_ids.append(cls.granted.id)

            # only-mode stored True while access is False. This combination is the ONLY
            # thing that separates the stored column from is_stock_inventory_only_user(),
            # which requires can_manage_stock_inventory() first -- without this fixture the
            # stock_inventory_only assertions below pass either way and prove nothing.
            cls.only_without_access = app_module.User(
                username='stock_only_without_access_switch',
                password=app_module.generate_password_hash('test-password'),
                role='staff', is_active=True,
                can_manage_stock_inventory=False,
                stock_inventory_only=True,
            )
            app_module.db.session.add(cls.only_without_access)
            app_module.db.session.flush()
            cls.created_user_ids.append(cls.only_without_access.id)
            app_module.db.session.commit()

            cls.superadmin_id = cls.superadmin.id
            cls.granted_id = cls.granted.id
            cls.only_without_access_id = cls.only_without_access.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            for user_id in reversed(cls.created_user_ids):
                user = app_module.db.session.get(app_module.User, user_id)
                if user:
                    app_module.db.session.delete(user)
            # The superadmin may pre-date this module; leave its flags as this class found
            # them rather than as this class set them.
            survivor = app_module.User.query.filter_by(username='jonamar').first()
            if survivor:
                survivor.can_manage_stock_inventory = False
                survivor.stock_inventory_only = False
            app_module.db.session.commit()
            app_module.db.session.remove()

    def _client_for(self, user_id):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def test_the_switch_reports_the_stored_grant_and_the_bypass_still_holds(self):
        with self.app.app_context():
            superadmin = app_module.db.session.get(app_module.User, self.superadmin_id)
            self.assertFalse(superadmin.can_manage_stock_inventory,
                             'precondition: the superadmin holds no explicit grant')

            # The documented bypass is untouched -- superadmins keep write access.
            self.assertTrue(app_module.can_manage_stock_inventory(superadmin))

            # ...but the switch must show what is stored, which is nothing.
            payload = app_module.approval_user_to_dict(superadmin)
            self.assertFalse(payload['can_manage_stock_inventory'])
            self.assertFalse(payload['stock_inventory_only'])

            # Positive control: a real grantee still reports True, so the assertions above
            # cannot pass by the serializer simply always returning False.
            granted = app_module.db.session.get(app_module.User, self.granted_id)
            granted_payload = app_module.approval_user_to_dict(granted)
            self.assertTrue(granted_payload['can_manage_stock_inventory'])
            self.assertTrue(granted_payload['stock_inventory_only'])

            # The only-mode field specifically: stored True while
            # is_stock_inventory_only_user() is False, because that predicate requires
            # can_manage_stock_inventory() first. The switch must show the stored True,
            # or saving the card would silently clear a grant the admin did set.
            odd = app_module.db.session.get(app_module.User, self.only_without_access_id)
            self.assertFalse(app_module.is_stock_inventory_only_user(odd),
                             'fixture precondition: the computed value is False here')
            self.assertTrue(odd.stock_inventory_only)
            self.assertTrue(app_module.approval_user_to_dict(odd)['stock_inventory_only'])

    def test_saving_a_superadmin_card_does_not_grant_inventory_access(self):
        client = self._client_for(self.superadmin_id)
        rendered = client.get('/settings/approval-routing-data')
        self.assertEqual(rendered.status_code, 200)
        row = next(user for user in rendered.get_json()['users']
                   if user['id'] == self.superadmin_id)
        self.assertFalse(row['can_manage_stock_inventory'],
                         'the switch must render unchecked')

        # Post back exactly what the UI rendered, as saveApprovalUser() does.
        saved = client.post('/settings/update-approval-user', json={
            'user_id': self.superadmin_id,
            'is_active': True,
            'can_manage_stock_inventory': row['can_manage_stock_inventory'],
            'stock_inventory_only': row['stock_inventory_only'],
        })
        self.assertEqual(saved.status_code, 200)

        with self.app.app_context():
            after = app_module.db.session.get(app_module.User, self.superadmin_id)
            self.assertFalse(after.can_manage_stock_inventory)
            # Still reaches the inventory surface through the documented bypass.
            self.assertTrue(app_module.can_manage_stock_inventory(after))

    def test_approver_only_stays_computed_because_it_has_no_column(self):
        """Guard against 'fixing' a field that is correctly derived.

        There is no approver_only column: it is derived from role plus
        can_approve_requests, and the save route flips the role from it. Reporting a stored
        value here would report a column that does not exist.
        """
        self.assertNotIn('approver_only', app_module.User.__table__.columns.keys())
        for stored_column in ('can_manage_stock_inventory', 'stock_inventory_only'):
            self.assertIn(stored_column, app_module.User.__table__.columns.keys())


class StockInventorySearchEndpointTests(unittest.TestCase):
    """Exercise search through the isolated Flask client, not only source contracts."""

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.tag = uuid.uuid4().hex[:10]
        cls.item_ids = []
        cls.movement_ids = []
        cls.borrowed_page_item_ids = []

        with cls.app.app_context():
            app_module.db.create_all()
            cls.manager = app_module.User(
                username=f'stock-search-admin-{cls.tag}',
                password=app_module.generate_password_hash('test-password'),
                role='staff',
                is_active=True,
                can_manage_stock_inventory=True,
                stock_inventory_branch_code='BC01',
            )
            cls.engineer = app_module.Engineer(
                employee_id=f'ENG-{cls.tag}',
                name=f'EngineerName{cls.tag}',
                initials='ES',
                branch='Manila',
            )
            app_module.db.session.add_all([cls.manager, cls.engineer])
            app_module.db.session.flush()

            cls.main_item = cls._create_item(
                branch_code='BC01',
                scan_barcode=f'STOCK-{cls.tag}-100%_LITERAL',
                item_name=f'Thermal Pump Kit {cls.tag}',
                category=f'Surgical Supplies {cls.tag}',
                storage_location=f'Manila Cold Room {cls.tag}',
                notes=f'Internal note token {cls.tag}',
            )
            cls.wildcard_decoy = cls._create_item(
                branch_code='BC01',
                scan_barcode=f'STOCK-{cls.tag}-100XXLITERAL',
                item_name=f'Wildcard Decoy {cls.tag}',
                category=f'General {cls.tag}',
                storage_location=f'Decoy Shelf {cls.tag}',
                notes=f'Decoy note {cls.tag}',
            )
            cls.inactive_item = cls._create_item(
                branch_code='BC01',
                scan_barcode=f'INACTIVE-{cls.tag}',
                item_name=f'Inactive Filter {cls.tag}',
                category=f'Inactive Category {cls.tag}',
                storage_location=f'Inactive Shelf {cls.tag}',
                notes=f'Inactive note {cls.tag}',
                is_active=False,
            )
            cls.branch_item = cls._create_item(
                branch_code='BC02',
                scan_barcode=f'BRANCH-{cls.tag}',
                item_name=f'Branch Only {cls.tag}',
                category=f'Branch Category {cls.tag}',
                storage_location=f'Cebu Shelf {cls.tag}',
                notes=f'Branch note {cls.tag}',
            )
            cls.history_item = cls._create_item(
                branch_code='BC01',
                scan_barcode=f'HISTORY-{cls.tag}',
                item_name=f'History Valve {cls.tag}',
                category=f'History Category {cls.tag}',
                storage_location=f'History Shelf {cls.tag}',
                notes=f'History note {cls.tag}',
            )
            cls.limit_item = cls._create_item(
                branch_code='BC01',
                scan_barcode=f'LIMIT-{cls.tag}',
                item_name=f'Limit Device {cls.tag}',
                category=f'Limit Category {cls.tag}',
                storage_location=f'Limit Shelf {cls.tag}',
                notes=f'Limit note {cls.tag}',
            )

            now = app_module.get_manila_time()
            cls.main_movement = cls._create_movement(
                cls.main_item,
                direction='OUT',
                reason='Issue',
                recipient=f'RecipientToken{cls.tag}',
                purpose=f'PurposeToken{cls.tag}',
                source_or_returned_by=f'SourceToken{cls.tag}',
                remarks=f'RemarksToken{cls.tag}',
                engineer_id=cls.engineer.id,
                engineer_name_snapshot=f'EngineerSnapshot{cls.tag}',
                created_at=now - timedelta(hours=1),
            )
            cls.history_match = cls._create_movement(
                cls.history_item,
                direction='OUT',
                reason='Issue',
                recipient=f'HistoryRecipient{cls.tag}',
                purpose=f'HistoryPurpose{cls.tag}',
                source_or_returned_by=f'HistorySource{cls.tag}',
                remarks=f'HistoryMatch{cls.tag}',
                engineer_id=cls.engineer.id,
                engineer_name_snapshot=f'EngineerSnapshot{cls.tag}',
                created_at=now - timedelta(hours=2),
            )
            cls.history_other_direction = cls._create_movement(
                cls.history_item,
                direction='IN',
                reason='Return',
                recipient=f'HistoryOtherRecipient{cls.tag}',
                purpose=f'HistoryOtherPurpose{cls.tag}',
                source_or_returned_by=f'HistoryOtherSource{cls.tag}',
                remarks=f'HistoryMatch{cls.tag}',
                engineer_id=cls.engineer.id,
                engineer_name_snapshot=f'EngineerSnapshot{cls.tag}',
                created_at=now - timedelta(hours=3),
            )
            cls.branch_movement = cls._create_movement(
                cls.branch_item,
                direction='OUT',
                reason='Issue',
                remarks=f'BranchMovement{cls.tag}',
                created_at=now - timedelta(hours=4),
            )
            cls.branch_borrowed_item = cls._create_item(
                branch_code='BC02',
                scan_barcode=f'BRANCH-BORROWED-{cls.tag}',
                item_name=f'Branch Borrowed {cls.tag}',
                category=f'Branch Borrowed Category {cls.tag}',
                storage_location=f'Cebu Borrowed Shelf {cls.tag}',
                notes=f'Branch borrowed note {cls.tag}',
            )
            cls.branch_borrowed_movement = cls._create_movement(
                cls.branch_borrowed_item,
                direction='OUT',
                reason='Issue',
                purpose=f'Branch Borrowed Purpose {cls.tag}',
                engineer_id=cls.engineer.id,
                engineer_name_snapshot=f'EngineerSnapshot{cls.tag}',
                created_at=now - timedelta(minutes=90),
            )
            for index in range(11):
                page_item = cls._create_item(
                    branch_code='BC01',
                    scan_barcode=f'BORROWED-PAGE-{cls.tag}-{index:02d}',
                    item_name=f'Borrowed Page {index:02d} {cls.tag}',
                    category=f'Borrowed Page Category {cls.tag}',
                    storage_location=f'Borrowed Page Shelf {index:02d}',
                    notes=f'Borrowed page note {cls.tag}',
                )
                cls._create_movement(
                    page_item,
                    direction='OUT',
                    reason='Issue',
                    purpose=f'Borrowed Page Purpose {cls.tag}',
                    engineer_id=cls.engineer.id,
                    engineer_name_snapshot=f'EngineerSnapshot{cls.tag}',
                    created_at=now - timedelta(minutes=index + 1),
                )
                cls.borrowed_page_item_ids.append(page_item.id)
            cls.limit_match = cls._create_movement(
                cls.limit_item,
                direction='IN',
                reason=f'LimitMatch{cls.tag}',
                remarks=f'LimitMatch{cls.tag}',
                created_at=now - timedelta(days=2),
            )
            for index in range(300):
                cls._create_movement(
                    cls.limit_item,
                    direction='IN',
                    reason=f'LimitNoise{cls.tag}{index}',
                    remarks=f'LimitNoise{cls.tag}{index}',
                    created_at=now - timedelta(minutes=index),
                )
            cls.main_item_id = cls.main_item.id
            cls.wildcard_decoy_id = cls.wildcard_decoy.id
            cls.inactive_item_id = cls.inactive_item.id
            cls.branch_item_id = cls.branch_item.id
            cls.branch_borrowed_item_id = cls.branch_borrowed_item.id
            cls.history_item_id = cls.history_item.id
            cls.limit_item_id = cls.limit_item.id
            cls.main_movement_id = cls.main_movement.id
            cls.history_match_id = cls.history_match.id
            cls.history_other_direction_id = cls.history_other_direction.id
            cls.branch_movement_id = cls.branch_movement.id
            cls.branch_borrowed_movement_id = cls.branch_borrowed_movement.id
            cls.limit_match_id = cls.limit_match.id
            app_module.db.session.commit()
            cls.manager_id = cls.manager.id
            cls.engineer_id = cls.engineer.id

    @classmethod
    def _create_item(cls, branch_code, scan_barcode, item_name, category, storage_location, notes, is_active=True):
        item = app_module.StockInventoryItem(
            barcode=app_module.stock_inventory_storage_barcode(branch_code, scan_barcode),
            scan_barcode=scan_barcode,
            item_name=item_name,
            category=category,
            storage_location=storage_location,
            notes=notes,
            branch_code=branch_code,
            is_active=is_active,
            current_quantity=10,
            created_by_id=cls.manager.id,
            updated_by_id=cls.manager.id,
        )
        app_module.db.session.add(item)
        app_module.db.session.flush()
        cls.item_ids.append(item.id)
        return item

    @classmethod
    def _create_movement(cls, item, **values):
        movement = app_module.StockInventoryMovement(
            item_id=item.id,
            direction=values.pop('direction'),
            quantity=1,
            reason=values.pop('reason'),
            resulting_quantity=10,
            created_by_id=cls.manager.id,
            **values,
        )
        app_module.db.session.add(movement)
        app_module.db.session.flush()
        cls.movement_ids.append(movement.id)
        return movement

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            movement_ids = getattr(cls, 'movement_ids', [])
            item_ids = getattr(cls, 'item_ids', [])
            engineer_id = getattr(cls, 'engineer_id', None)
            manager_id = getattr(cls, 'manager_id', None)
            if movement_ids:
                app_module.db.session.query(app_module.StockInventoryMovement).filter(
                    app_module.StockInventoryMovement.id.in_(movement_ids)
                ).delete(synchronize_session=False)
            if item_ids:
                app_module.db.session.query(app_module.StockInventoryItem).filter(
                    app_module.StockInventoryItem.id.in_(item_ids)
                ).delete(synchronize_session=False)
            if engineer_id:
                app_module.db.session.query(app_module.Engineer).filter_by(id=engineer_id).delete(
                    synchronize_session=False
                )
            if manager_id:
                app_module.db.session.query(app_module.ApprovalRouting).filter(
                    app_module.or_(
                        app_module.ApprovalRouting.requester_user_id == manager_id,
                        app_module.ApprovalRouting.approver_user_id == manager_id,
                    )
                ).delete(synchronize_session=False)
                app_module.db.session.query(app_module.User).filter_by(id=manager_id).delete(
                    synchronize_session=False
                )
            app_module.db.session.commit()
            app_module.db.session.remove()

    def _client(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.manager_id)
            session['_fresh'] = True
        return client

    def _items(self, **query):
        response = self._client().get('/api/stock-inventory/items', query_string={
            'branch': 'BC01',
            **query,
        })
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()['items']

    def _movements(self, **query):
        response = self._client().get('/api/stock-inventory/movements', query_string={
            'branch': 'BC01',
            **query,
        })
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()['movements']

    def _borrowed(self, **query):
        response = self._client().get('/api/stock-inventory/borrowed', query_string={
            'branch': 'BC01',
            **query,
        })
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    def test_borrowed_pagination_returns_metadata_and_newest_first_pages(self):
        first = self._borrowed(page=1)
        first_ids = [row['item_id'] for row in first['borrowed']]
        self.assertEqual(first['page'], 1)
        self.assertEqual(first['per_page'], 10)
        self.assertEqual(first['total'], 13)
        self.assertEqual(first['total_pages'], 2)
        self.assertEqual(first_ids, self.borrowed_page_item_ids[:10])

        second = self._borrowed(page=2)
        self.assertEqual(second['page'], 2)
        self.assertEqual(
            [row['item_id'] for row in second['borrowed']],
            [self.borrowed_page_item_ids[10], self.main_item_id, self.history_item_id],
        )

    def test_borrowed_pagination_clamps_invalid_and_out_of_range_pages(self):
        invalid = self._borrowed(page='not-a-number')
        self.assertEqual(invalid['page'], 1)
        self.assertEqual(len(invalid['borrowed']), 10)

        out_of_range = self._borrowed(page=999)
        self.assertEqual(out_of_range['page'], 2)
        self.assertEqual(len(out_of_range['borrowed']), 3)

        empty = self._borrowed(q=f'No current loan {self.tag}')
        self.assertEqual(empty['borrowed'], [])
        self.assertEqual(empty['total'], 0)
        self.assertEqual(empty['total_pages'], 1)
        self.assertEqual(empty['page'], 1)

    def test_borrowed_query_filters_before_pagination_and_branch_isolation_remains(self):
        filtered = self._borrowed(q=f'Branch Borrowed Purpose {self.tag}', page=1)
        self.assertEqual(filtered['total'], 0)
        self.assertEqual(filtered['borrowed'], [])

        matching = self._borrowed(q=f'Borrowed Page Purpose {self.tag}', page=1)
        self.assertEqual(matching['total'], 11)
        self.assertEqual(matching['total_pages'], 2)
        self.assertEqual(
            [row['item_id'] for row in matching['borrowed']],
            self.borrowed_page_item_ids[:10],
        )

        branch_rows = self._borrowed(page=1)
        self.assertTrue(all(row['branch_code'] == 'BC01' for row in branch_rows['borrowed']))
        self.assertNotIn(self.branch_borrowed_item_id, {
            row['item_id'] for row in branch_rows['borrowed']
        })

    def test_borrowed_endpoint_requires_stock_inventory_view_access(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session.pop('_user_id', None)
            session['_fresh'] = True
        response = client.get('/api/stock-inventory/borrowed')
        self.assertIn(response.status_code, (302, 401, 403))

    def test_search_helper_splits_terms_and_escapes_sql_wildcards(self):
        self.assertEqual(
            app_module.stock_inventory_search_terms('  Alpha   beta  '),
            ['Alpha', 'beta'],
        )
        self.assertEqual(
            app_module.stock_inventory_search_pattern(r'100%_\token'),
            r'%100\%\_\\token%',
        )

    def test_items_search_matches_fields_notes_and_and_terms(self):
        rows = self._items(q=f'  thermal   cold  ')
        self.assertEqual([row['id'] for row in rows], [self.main_item_id])

        for term in (
            f'STOCK-{self.tag}',
            f'Surgical',
            f'Manila',
            f'Internal note token',
        ):
            self.assertIn(self.main_item_id, {row['id'] for row in self._items(q=term)})

    def test_items_inactive_behavior_literal_wildcards_and_branch_isolation(self):
        inactive_query = f'Inactive Filter {self.tag}'
        self.assertIn(self.inactive_item_id, self.item_ids)
        self.assertNotIn(self.inactive_item_id, {row['id'] for row in self._items(q=inactive_query)})
        self.assertIn(
            self.inactive_item_id,
            {row['id'] for row in self._items(q=inactive_query, include_inactive='true')},
        )

        literal_rows = self._items(q=f'100%_LITERAL')
        literal_ids = {row['id'] for row in literal_rows}
        self.assertIn(self.main_item_id, literal_ids)
        self.assertNotIn(self.wildcard_decoy_id, literal_ids)

        branch_rows = self._items(q=f'Branch Only {self.tag}')
        self.assertEqual(branch_rows, [])

    def test_movements_search_matches_item_movement_engineer_and_admin_fields(self):
        for term in (
            f'Thermal',
            f'STOCK-{self.tag}',
            f'Surgical',
            f'Cold',
            'OUT',
            'Issue',
            f'RecipientToken{self.tag}',
            f'PurposeToken{self.tag}',
            f'SourceToken{self.tag}',
            f'RemarksToken{self.tag}',
            f'ENG-{self.tag}',
            f'EngineerName{self.tag}',
            f'EngineerSnapshot{self.tag}',
            f'stock-search-admin-{self.tag}',
        ):
            movement_ids = {row['id'] for row in self._movements(q=term)}
            self.assertIn(self.main_movement_id, movement_ids, term)

    def test_item_history_text_search_preserves_item_and_direction_filters(self):
        rows = self._movements(
            item_id=self.history_item_id,
            direction='OUT',
            q=f'HistoryMatch{self.tag}',
        )
        self.assertEqual([row['id'] for row in rows], [self.history_match_id])
        self.assertTrue(all(row['item_id'] == self.history_item_id for row in rows))

        all_history_rows = self._movements(item_id=self.history_item_id, q=f'HistoryMatch{self.tag}')
        self.assertEqual(
            {row['id'] for row in all_history_rows},
            {self.history_match_id, self.history_other_direction_id},
        )

    def test_movement_branch_isolation_and_search_before_limit(self):
        self.assertIn(self.branch_movement_id, self.movement_ids)
        self.assertEqual(self._movements(q=f'BranchMovement{self.tag}'), [])

        rows = self._movements(q=f'LimitMatch{self.tag}', limit=300)
        self.assertEqual([row['id'] for row in rows], [self.limit_match_id])


if __name__ == '__main__':
    unittest.main()
