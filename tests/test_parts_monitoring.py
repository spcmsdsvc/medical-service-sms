import pathlib
import unittest
import uuid

import app as app_module
from tests.sw_cache_version import assert_cache_version_at_least


ROOT = pathlib.Path(__file__).resolve().parents[1]


class PartsMonitoringTests(unittest.TestCase):
    """Parts Monitoring batch 1: admin-only page, add/edit/add stock/delete, Low tag."""

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.suffix = uuid.uuid4().hex[:8]
        cls.user_ids = {}
        with cls.app.app_context():
            app_module.db.create_all()
            for key, role in (('superadmin', 'superadmin'), ('regional', 'regional_admin'), ('engineer', 'engineer')):
                user = app_module.User(
                    username=f'parts_{key}_{cls.suffix}',
                    password=app_module.generate_password_hash('test-password'),
                    role=role,
                    is_active=True,
                )
                app_module.db.session.add(user)
                app_module.db.session.flush()
                cls.user_ids[key] = user.id
            app_module.db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            app_module.PartsMonitoringItem.query.filter(
                app_module.PartsMonitoringItem.item_number.like(f'%{cls.suffix}%')
            ).delete(synchronize_session=False)
            app_module.ActivityLog.query.filter(
                app_module.ActivityLog.action.like(f'%{cls.suffix}%')
            ).delete(synchronize_session=False)
            for user_id in cls.user_ids.values():
                user = app_module.db.session.get(app_module.User, user_id)
                if user:
                    app_module.db.session.delete(user)
            app_module.db.session.commit()
            app_module.db.session.remove()

    def client_for(self, key):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.user_ids[key])
            session['_fresh'] = True
        return client

    def setUp(self):
        self.admin = self.client_for('superadmin')

    def number(self, label):
        return f'{label}-{self.suffix}'

    def add_part(self, label='P', stock=6, minimum=2, client=None):
        return (client or self.admin).post('/api/parts-monitoring/items', json={
            'item_number': self.number(label),
            'item_description': f'Part {label}',
            'stock': stock,
            'minimum_stock': minimum,
        })

    # Access
    def test_engineer_is_refused_page_and_apis(self):
        engineer = self.client_for('engineer')
        self.assertEqual(engineer.get('/parts_monitoring').status_code, 403)
        self.assertEqual(engineer.get('/api/parts-monitoring/items').status_code, 403)
        self.assertEqual(self.add_part('ENG', client=engineer).status_code, 403)
        part_id = self.add_part('ENGX').get_json()['item']['id']
        self.assertEqual(engineer.put(f'/api/parts-monitoring/items/{part_id}', json={}).status_code, 403)
        self.assertEqual(engineer.post(f'/api/parts-monitoring/items/{part_id}/stock', json={'quantity': 1}).status_code, 403)
        self.assertEqual(engineer.delete(f'/api/parts-monitoring/items/{part_id}').status_code, 403)

    def test_superadmin_and_regional_admin_can_open_page(self):
        for key in ('superadmin', 'regional'):
            client = self.client_for(key)
            response = client.get('/parts_monitoring')
            self.assertEqual(response.status_code, 200, key)
            self.assertIn(b'Parts Monitoring', response.data)
            self.assertEqual(client.get('/api/parts-monitoring/items').status_code, 200, key)

    def test_sidebar_link_only_for_admins(self):
        admin_page = self.client_for('superadmin').get('/parts_monitoring').get_data(as_text=True)
        self.assertIn('href="/parts_monitoring"', admin_page)
        engineer_page = self.client_for('engineer').get('/').get_data(as_text=True)
        self.assertNotIn('href="/parts_monitoring"', engineer_page)

    # Add
    def test_add_part_returns_figures_and_low_flag(self):
        response = self.add_part('ADD', stock=6, minimum=2)
        self.assertEqual(response.status_code, 201)
        item = response.get_json()['item']
        self.assertEqual((item['stock'], item['committed'], item['reserved'], item['available']), (6, 0, 0, 6))
        self.assertFalse(item['is_low'])
        low = self.add_part('ADDLOW', stock=3, minimum=3).get_json()['item']
        self.assertTrue(low['is_low'])
        listed = {row['item_number'] for row in self.admin.get('/api/parts-monitoring/items').get_json()['items']}
        self.assertIn(self.number('ADD'), listed)

    def test_add_validation(self):
        cases = [
            ({'item_number': '', 'item_description': 'x', 'stock': 1, 'minimum_stock': 0}, 'item_number'),
            ({'item_number': self.number('V'), 'item_description': ' ', 'stock': 1, 'minimum_stock': 0}, 'item_description'),
            ({'item_number': self.number('V'), 'item_description': 'x', 'stock': '', 'minimum_stock': 0}, 'stock'),
            ({'item_number': self.number('V'), 'item_description': 'x', 'stock': -1, 'minimum_stock': 0}, 'stock'),
            ({'item_number': self.number('V'), 'item_description': 'x', 'stock': 1.5, 'minimum_stock': 0}, 'stock'),
            ({'item_number': self.number('V'), 'item_description': 'x', 'stock': 'abc', 'minimum_stock': 0}, 'stock'),
            ({'item_number': self.number('V'), 'item_description': 'x', 'stock': 1}, 'minimum_stock'),
        ]
        for payload, field in cases:
            response = self.admin.post('/api/parts-monitoring/items', json=payload)
            self.assertEqual(response.status_code, 400, payload)
            self.assertEqual(response.get_json()['field'], field, payload)

    def test_duplicate_item_number_ignores_case(self):
        self.assertEqual(self.add_part('dup').status_code, 201)
        response = self.admin.post('/api/parts-monitoring/items', json={
            'item_number': self.number('dup').upper(), 'item_description': 'Again', 'stock': 1, 'minimum_stock': 0,
        })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()['field'], 'item_number')

    # Edit
    def test_edit_changes_number_description_minimum_not_stock(self):
        part_id = self.add_part('EDIT', stock=5, minimum=1).get_json()['item']['id']
        response = self.admin.put(f'/api/parts-monitoring/items/{part_id}', json={
            'item_number': self.number('EDIT2'), 'item_description': 'Renamed', 'minimum_stock': 5, 'stock': 99,
        })
        self.assertEqual(response.status_code, 200)
        item = response.get_json()['item']
        self.assertEqual((item['item_number'], item['item_description'], item['minimum_stock'], item['stock']),
                         (self.number('EDIT2'), 'Renamed', 5, 5))
        self.assertTrue(item['is_low'])

    def test_edit_refuses_another_parts_number(self):
        self.add_part('TAKEN')
        part_id = self.add_part('MINE').get_json()['item']['id']
        response = self.admin.put(f'/api/parts-monitoring/items/{part_id}', json={
            'item_number': self.number('taken'), 'item_description': 'x', 'minimum_stock': 0,
        })
        self.assertEqual(response.status_code, 409)

    # Add stock
    def test_add_stock_adds_and_validates(self):
        part_id = self.add_part('STK', stock=2, minimum=3).get_json()['item']['id']
        response = self.admin.post(f'/api/parts-monitoring/items/{part_id}/stock', json={'quantity': 4})
        self.assertEqual(response.status_code, 200)
        item = response.get_json()['item']
        self.assertEqual(item['stock'], 6)
        self.assertFalse(item['is_low'])
        for bad in (0, -2, '', 'x', 1.5):
            response = self.admin.post(f'/api/parts-monitoring/items/{part_id}/stock', json={'quantity': bad})
            self.assertEqual(response.status_code, 400, bad)

    # Delete
    def test_delete_removes_part(self):
        part_id = self.add_part('DEL').get_json()['item']['id']
        self.assertEqual(self.admin.delete(f'/api/parts-monitoring/items/{part_id}').status_code, 200)
        listed = {row['id'] for row in self.admin.get('/api/parts-monitoring/items').get_json()['items']}
        self.assertNotIn(part_id, listed)
        self.assertEqual(self.admin.delete(f'/api/parts-monitoring/items/{part_id}').status_code, 404)

    # Activity Log
    def test_changes_are_logged_under_parts_monitoring(self):
        part_id = self.add_part('LOG').get_json()['item']['id']
        self.admin.post(f'/api/parts-monitoring/items/{part_id}/stock', json={'quantity': 2})
        with self.app.app_context():
            actions = [row.action for row in app_module.ActivityLog.query.filter(
                app_module.ActivityLog.action.like(f'%{self.number("LOG")}%')
            ).all()]
        self.assertEqual(len(actions), 2, actions)
        for action in actions:
            self.assertEqual(app_module.classify_activity_action(action), 'Parts Monitoring')
        self.assertIn('Parts Monitoring', app_module.ACTIVITY_CATEGORIES)

    def test_service_worker_bumped(self):
        assert_cache_version_at_least(self, 354)


class PartsMonitoringCommitmentTests(unittest.TestCase):
    """Parts Monitoring batch 2: commit to a client's machine, reserve, cancel."""

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.suffix = uuid.uuid4().hex[:8]
        with cls.app.app_context():
            app_module.db.create_all()
            admin = app_module.User(
                username=f'parts_alloc_admin_{cls.suffix}',
                password=app_module.generate_password_hash('test-password'),
                role='superadmin', is_active=True,
            )
            engineer = app_module.User(
                username=f'parts_alloc_eng_{cls.suffix}',
                password=app_module.generate_password_hash('test-password'),
                role='engineer', is_active=True,
            )
            client_a = app_module.Client(name=f'Parts Client A {cls.suffix}', address='A')
            client_b = app_module.Client(name=f'Parts Client B {cls.suffix}', address='B')
            app_module.db.session.add_all([admin, engineer, client_a, client_b])
            app_module.db.session.flush()
            cls.serials = {
                'product': f'PM-PROD-{cls.suffix}',
                'genoray': f'PM-GEN-{cls.suffix}',
                'vieworks': f'PM-VW-{cls.suffix}',
                'other': f'PM-OTHER-{cls.suffix}',
            }
            app_module.db.session.add_all([
                app_module.Product(serial_number=cls.serials['product'], name='Fluoroscopy', client_id=client_a.id),
                app_module.GenorayItem(serial_number=cls.serials['genoray'], name='Genoray C-arm', client_id=client_a.id),
                app_module.VieworksItem(serial_number=cls.serials['vieworks'], name='Vieworks DR', client_id=client_a.id),
                app_module.Product(serial_number=cls.serials['other'], name='Other CT', client_id=client_b.id),
            ])
            app_module.db.session.commit()
            cls.admin_id, cls.engineer_id = admin.id, engineer.id
            cls.client_a_id, cls.client_b_id = client_a.id, client_b.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            part_ids = [row.id for row in app_module.PartsMonitoringItem.query.filter(
                app_module.PartsMonitoringItem.item_number.like(f'%{cls.suffix}%')).all()]
            if part_ids:
                app_module.PartsMonitoringAllocation.query.filter(
                    app_module.PartsMonitoringAllocation.part_id.in_(part_ids)).delete(synchronize_session=False)
                app_module.PartsMonitoringItem.query.filter(
                    app_module.PartsMonitoringItem.id.in_(part_ids)).delete(synchronize_session=False)
            app_module.ActivityLog.query.filter(
                app_module.ActivityLog.action.like(f'%{cls.suffix}%')).delete(synchronize_session=False)
            app_module.Product.query.filter(
                app_module.Product.serial_number.in_([cls.serials['product'], cls.serials['other']])).delete(synchronize_session=False)
            app_module.GenorayItem.query.filter_by(serial_number=cls.serials['genoray']).delete(synchronize_session=False)
            app_module.VieworksItem.query.filter_by(serial_number=cls.serials['vieworks']).delete(synchronize_session=False)
            app_module.Client.query.filter(
                app_module.Client.id.in_([cls.client_a_id, cls.client_b_id])).delete(synchronize_session=False)
            app_module.User.query.filter(
                app_module.User.id.in_([cls.admin_id, cls.engineer_id])).delete(synchronize_session=False)
            app_module.db.session.commit()
            app_module.db.session.remove()

    def client_for(self, user_id):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def setUp(self):
        self.admin = self.client_for(self.admin_id)

    def new_part(self, label, stock=6, minimum=0):
        response = self.admin.post('/api/parts-monitoring/items', json={
            'item_number': f'{label}-{self.suffix}', 'item_description': 'X-ray Tube',
            'stock': stock, 'minimum_stock': minimum,
        })
        self.assertEqual(response.status_code, 201)
        return response.get_json()['item']['id']

    def commit(self, part_id, quantity, source='product', client_id=None, serial=None):
        return self.admin.post(f'/api/parts-monitoring/items/{part_id}/allocations', json={
            'kind': 'committed', 'quantity': quantity,
            'client_id': client_id or self.client_a_id,
            'machine_source': source, 'machine_serial': serial or self.serials[source],
        })

    def reserve(self, part_id, quantity):
        return self.admin.post(f'/api/parts-monitoring/items/{part_id}/allocations',
                               json={'kind': 'reserved', 'quantity': quantity})

    def item(self, part_id):
        items = self.admin.get('/api/parts-monitoring/items').get_json()['items']
        return next(row for row in items if row['id'] == part_id)

    def test_commit_lowers_available(self):
        part_id = self.new_part('TUBE')
        response = self.commit(part_id, 2)
        self.assertEqual(response.status_code, 201)
        item = self.item(part_id)
        self.assertEqual((item['stock'], item['committed'], item['reserved'], item['available']), (6, 2, 0, 4))
        allocation = response.get_json()['allocation']
        self.assertEqual(allocation['client_name'], f'Parts Client A {self.suffix}')
        self.assertIn(self.serials['product'], allocation['machine_label'])

    def test_commit_more_than_available_is_refused(self):
        part_id = self.new_part('OVER')
        self.commit(part_id, 2)
        response = self.commit(part_id, 5)
        self.assertEqual(response.status_code, 409)
        self.assertIn('Only 4 available', response.get_json()['error'])
        self.assertEqual(self.reserve(part_id, 5).status_code, 409)
        self.assertEqual(self.item(part_id)['available'], 4)

    def test_commit_needs_client_and_its_own_machine(self):
        part_id = self.new_part('CHK')
        no_client = self.admin.post(f'/api/parts-monitoring/items/{part_id}/allocations', json={
            'kind': 'committed', 'quantity': 1, 'machine_source': 'product', 'machine_serial': self.serials['product'],
        })
        self.assertEqual((no_client.status_code, no_client.get_json()['field']), (400, 'client_id'))
        no_machine = self.admin.post(f'/api/parts-monitoring/items/{part_id}/allocations', json={
            'kind': 'committed', 'quantity': 1, 'client_id': self.client_a_id,
        })
        self.assertEqual((no_machine.status_code, no_machine.get_json()['field']), (400, 'machine'))
        other = self.commit(part_id, 1, client_id=self.client_a_id, serial=self.serials['other'])
        self.assertEqual((other.status_code, other.get_json()['field']), (400, 'machine'))
        self.assertEqual(self.item(part_id)['committed'], 0)

    def test_reserve_needs_no_client(self):
        part_id = self.new_part('RES')
        self.assertEqual(self.reserve(part_id, 1).status_code, 201)
        item = self.item(part_id)
        self.assertEqual((item['reserved'], item['available']), (1, 5))

    def test_machines_listed_from_all_three_lists(self):
        response = self.admin.get(f'/api/parts-monitoring/machines?client_id={self.client_a_id}')
        sources = {(m['source'], m['serial_number']) for m in response.get_json()['machines']}
        self.assertEqual(sources, {('product', self.serials['product']), ('genoray', self.serials['genoray']),
                                   ('vieworks', self.serials['vieworks'])})
        for source in ('genoray', 'vieworks'):
            part_id = self.new_part(f'SRC{source}')
            self.assertEqual(self.commit(part_id, 1, source=source).status_code, 201, source)
        clients = {c['id'] for c in self.admin.get('/api/parts-monitoring/clients').get_json()['clients']}
        self.assertTrue({self.client_a_id, self.client_b_id} <= clients)

    def test_low_uses_available(self):
        part_id = self.new_part('LOW', stock=6, minimum=4)
        self.assertFalse(self.item(part_id)['is_low'])
        self.commit(part_id, 2)
        self.assertTrue(self.item(part_id)['is_low'])

    def test_cancel_returns_quantity_and_only_once(self):
        part_id = self.new_part('CAN')
        allocation_id = self.commit(part_id, 2).get_json()['allocation']['id']
        listed = self.admin.get(f'/api/parts-monitoring/items/{part_id}/allocations').get_json()['allocations']
        self.assertEqual([row['id'] for row in listed], [allocation_id])
        self.assertEqual(self.admin.post(f'/api/parts-monitoring/allocations/{allocation_id}/cancel').status_code, 200)
        self.assertEqual(self.item(part_id)['available'], 6)
        self.assertEqual(self.admin.post(f'/api/parts-monitoring/allocations/{allocation_id}/cancel').status_code, 404)

    def test_delete_refused_while_open(self):
        part_id = self.new_part('DELO')
        allocation_id = self.reserve(part_id, 1).get_json()['allocation']['id']
        self.assertEqual(self.admin.delete(f'/api/parts-monitoring/items/{part_id}').status_code, 409)
        self.admin.post(f'/api/parts-monitoring/allocations/{allocation_id}/cancel')
        self.assertEqual(self.admin.delete(f'/api/parts-monitoring/items/{part_id}').status_code, 200)

    def test_engineer_refused(self):
        engineer = self.client_for(self.engineer_id)
        part_id = self.new_part('ENGA')
        self.assertEqual(engineer.get('/api/parts-monitoring/clients').status_code, 403)
        self.assertEqual(engineer.get(f'/api/parts-monitoring/machines?client_id={self.client_a_id}').status_code, 403)
        self.assertEqual(engineer.get(f'/api/parts-monitoring/items/{part_id}/allocations').status_code, 403)
        self.assertEqual(engineer.post(f'/api/parts-monitoring/items/{part_id}/allocations',
                                       json={'kind': 'reserved', 'quantity': 1}).status_code, 403)
        allocation_id = self.reserve(part_id, 1).get_json()['allocation']['id']
        self.assertEqual(engineer.post(f'/api/parts-monitoring/allocations/{allocation_id}/cancel').status_code, 403)

    def test_commit_and_cancel_logged(self):
        part_id = self.new_part('LOGA')
        allocation_id = self.commit(part_id, 1).get_json()['allocation']['id']
        self.admin.post(f'/api/parts-monitoring/allocations/{allocation_id}/cancel')
        with self.app.app_context():
            actions = [row.action for row in app_module.ActivityLog.query.filter(
                app_module.ActivityLog.action.like(f'%LOGA-{self.suffix}%')).all()]
        self.assertTrue(any('committed 1 of part' in a for a in actions), actions)
        self.assertTrue(any('cancelled commitment of 1' in a for a in actions), actions)

    def test_service_worker_bumped(self):
        assert_cache_version_at_least(self, 355)


if __name__ == '__main__':
    unittest.main()
