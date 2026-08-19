import json
import pathlib
import unittest
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

    def test_read_only_ui_has_no_mutation_controls(self):
        self.assertIn('{% if not stock_read_only %}', self.page_source)
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
        self.assertIn('StockInventoryItem.current_quantity >= quantity', self.app_source)
        self.assertIn("'This movement has already been reversed.'", self.app_source)

    def test_inventory_only_access_and_dashboard_are_present(self):
        for marker in ('can_manage_stock_inventory', 'stock_inventory_only', 'stock_inventory_branch_code'):
            self.assertIn(marker, self.app_source)
        self.assertIn('restrict_stock_inventory_only_accounts', self.app_source)
        self.assertIn('Stock Inventory-only view', self.settings_source)
        self.assertIn('Assigned Inventory Branch', self.settings_source)
        self.assertIn('value="BC02_BC03"', self.settings_source)
        self.assertIn('BC02 + BC03 - Cebu + Davao', self.settings_source)
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

    def test_combined_manager_can_select_either_branch_but_not_manila(self):
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
                ('BC02', 'BC03'),
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
                'BC02',
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


if __name__ == '__main__':
    unittest.main()
