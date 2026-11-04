import json
import pathlib
import unittest
import uuid
from datetime import timedelta
from unittest import mock

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


class PartsMonitoringScheduleTests(unittest.TestCase):
    """Parts Monitoring batch 3: Parts Installation on schedules."""

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.suffix = uuid.uuid4().hex[:8]
        db = app_module.db
        with cls.app.app_context():
            db.create_all()
            admin = app_module.User(username=f'parts_sched_admin_{cls.suffix}',
                                    password=app_module.generate_password_hash('test-password'),
                                    role='superadmin', is_active=True)
            eng_user = app_module.User(username=f'parts_sched_eng_{cls.suffix}',
                                       password=app_module.generate_password_hash('test-password'),
                                       role='engineer', is_active=True)
            client_row = app_module.Client(name=f'Parts Sched Client {cls.suffix}', address='X')
            db.session.add_all([admin, eng_user, client_row])
            db.session.flush()
            engineer = app_module.Engineer(employee_id=f'PS-{cls.suffix}', name=f'Parts Sched Eng {cls.suffix}',
                                           initials='PS', branch='Manila', user_id=eng_user.id)
            db.session.add(engineer)
            cls.serial_a = f'PS-A-{cls.suffix}'
            cls.serial_b = f'PS-B-{cls.suffix}'
            db.session.add_all([
                app_module.Product(serial_number=cls.serial_a, name='Fluoro A', client_id=client_row.id),
                app_module.Product(serial_number=cls.serial_b, name='Fluoro B', client_id=client_row.id),
            ])
            db.session.commit()
            cls.admin_id, cls.eng_user_id = admin.id, eng_user.id
            cls.client_id, cls.engineer_id = client_row.id, engineer.id

    @classmethod
    def tearDownClass(cls):
        db = app_module.db
        with cls.app.app_context():
            for shift in app_module.Shift.query.filter(app_module.Shift.title.like(f'%{cls.suffix}%')).all():
                app_module.ShiftEngineer.query.filter_by(shift_id=shift.id).delete()
                db.session.delete(shift)
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
                app_module.Product.serial_number.in_([cls.serial_a, cls.serial_b])).delete(synchronize_session=False)
            app_module.Engineer.query.filter_by(id=cls.engineer_id).delete()
            app_module.Client.query.filter_by(id=cls.client_id).delete()
            app_module.User.query.filter(app_module.User.id.in_([cls.admin_id, cls.eng_user_id])).delete(
                synchronize_session=False)
            db.session.commit()
            db.session.remove()

    def client_for(self, user_id):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def setUp(self):
        self.admin = self.client_for(self.admin_id)

    # Fixtures
    def new_commitment(self, label, stock=6, quantity=2, serial=None):
        part = self.admin.post('/api/parts-monitoring/items', json={
            'item_number': f'{label}-{self.suffix}', 'item_description': f'Tube {label}',
            'stock': stock, 'minimum_stock': 0,
        }).get_json()['item']
        allocation = self.admin.post(f"/api/parts-monitoring/items/{part['id']}/allocations", json={
            'kind': 'committed', 'quantity': quantity, 'client_id': self.client_id,
            'machine_source': 'product', 'machine_serial': serial or self.serial_a,
        }).get_json()['allocation']
        return part['id'], allocation['id']

    def schedule_payload(self, title, day_offset, days=0, serial=None, parts=None, **extra):
        with self.app.app_context():
            start = app_module.get_manila_today() + timedelta(days=day_offset)
        data = {
            'title': f'{title} {self.suffix}',
            'start_date': start.isoformat(),
            'end_date': (start + timedelta(days=days)).isoformat(),
            'start_time': '09:00', 'end_time': '11:00',
            'include_weekends': 'true',
            'engineers': json.dumps([self.engineer_id]),
            'engineer_id': str(self.engineer_id),
            'client_id': str(self.client_id),
            'product_id': serial or self.serial_a,
            'equipment_source': 'product',
            'status': 'In Progress',
        }
        if parts is not None:
            data['parts_allocation_ids'] = json.dumps(parts)
        data.update(extra)
        return data

    def chain(self, title):
        with self.app.app_context():
            return [row.id for row in app_module.Shift.query.filter_by(title=f'{title} {self.suffix}')
                    .order_by(app_module.Shift.start_time).all()]

    def figures(self, part_id):
        items = self.admin.get('/api/parts-monitoring/items').get_json()['items']
        item = next(row for row in items if row['id'] == part_id)
        return item['stock'], item['committed'], item['available']

    def status(self, allocation_id):
        with self.app.app_context():
            return app_module.db.session.get(app_module.PartsMonitoringAllocation, allocation_id).status

    # Tests
    def test_schedule_with_parts_uses_the_commitment(self):
        part_id, allocation_id = self.new_commitment('INS')
        response = self.admin.post('/add_shift', data=self.schedule_payload('Install', 101, parts=[allocation_id]))
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(self.figures(part_id), (4, 0, 4))
        self.assertEqual(self.status(allocation_id), 'installed')

    def test_multi_day_schedule_uses_parts_once(self):
        part_id, allocation_id = self.new_commitment('MULTI')
        response = self.admin.post('/add_shift', data=self.schedule_payload('Multi', 104, days=2, parts=[allocation_id]))
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(len(self.chain('Multi')), 3)
        self.assertEqual(self.figures(part_id), (4, 0, 4))

    def test_commitment_cannot_be_used_twice_or_on_another_machine(self):
        _part_id, allocation_id = self.new_commitment('TWICE')
        self.admin.post('/add_shift', data=self.schedule_payload('First', 108, parts=[allocation_id]))
        again = self.admin.post('/add_shift', data=self.schedule_payload('Second', 109, parts=[allocation_id]))
        self.assertEqual(again.status_code, 409)
        self.assertEqual(self.chain('Second'), [])
        _p2, other_machine = self.new_commitment('MACH', serial=self.serial_b)
        wrong = self.admin.post('/add_shift', data=self.schedule_payload('Wrong', 110, parts=[other_machine]))
        self.assertEqual(wrong.status_code, 409)
        self.assertEqual(self.chain('Wrong'), [])

    def test_edit_untick_returns_and_absent_field_keeps(self):
        part_id, allocation_id = self.new_commitment('EDIT')
        self.admin.post('/add_shift', data=self.schedule_payload('Edit', 112, parts=[allocation_id]))
        shift_id = self.chain('Edit')[0]
        kept = self.admin.post(f'/update_shift/{shift_id}', data=self.schedule_payload('Edit', 112))
        self.assertEqual(kept.status_code, 200, kept.get_data(as_text=True))
        self.assertEqual(self.status(allocation_id), 'installed')
        unticked = self.admin.post(f'/update_shift/{shift_id}', data=self.schedule_payload('Edit', 112, parts=[]))
        self.assertEqual(unticked.status_code, 200, unticked.get_data(as_text=True))
        self.assertEqual(self.status(allocation_id), 'open')
        self.assertEqual(self.figures(part_id), (6, 2, 4))
        retick = self.admin.post(f'/update_shift/{shift_id}', data=self.schedule_payload('Edit', 112, parts=[allocation_id]))
        self.assertEqual(retick.status_code, 200)
        self.assertEqual(self.figures(part_id), (4, 0, 4))

    def test_machine_change_returns_parts(self):
        part_id, allocation_id = self.new_commitment('SWAP')
        self.admin.post('/add_shift', data=self.schedule_payload('Swap', 115, parts=[allocation_id]))
        self.assertEqual(self.status(allocation_id), 'installed')
        shift_id = self.chain('Swap')[0]
        response = self.admin.post(f'/update_shift/{shift_id}', data=self.schedule_payload('Swap', 115, serial=self.serial_b))
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(self.status(allocation_id), 'open')
        self.assertEqual(self.figures(part_id), (6, 2, 4))

    def test_deleted_schedule_returns_parts(self):
        part_id, allocation_id = self.new_commitment('DELS')
        self.admin.post('/add_shift', data=self.schedule_payload('Gone', 118, parts=[allocation_id]))
        self.assertEqual(self.status(allocation_id), 'installed')
        shift_id = self.chain('Gone')[0]
        response = self.admin.delete(f'/delete_shift/{shift_id}')
        self.assertIn(response.status_code, (200, 204), response.get_data(as_text=True))
        self.assertEqual(self.chain('Gone'), [])
        self.assertEqual(self.figures(part_id), (6, 2, 4))
        self.assertEqual(self.status(allocation_id), 'open')

    def test_any_delete_path_returns_parts(self):
        """Bulk purges and previewed deletes remove rows directly; the sweep still returns parts."""
        part_id, allocation_id = self.new_commitment('BULK')
        self.admin.post('/add_shift', data=self.schedule_payload('Bulk', 121, days=1, parts=[allocation_id]))
        self.assertEqual(self.figures(part_id), (4, 0, 4))
        with self.app.app_context():
            for shift in app_module.Shift.query.filter_by(title=f'Bulk {self.suffix}').all():
                app_module.ShiftEngineer.query.filter_by(shift_id=shift.id).delete()
                app_module.db.session.delete(shift)
            app_module.db.session.commit()
        self.assertEqual(self.figures(part_id), (6, 2, 4))

    def test_non_admin_and_offline_queue_parts_are_ignored(self):
        part_id, allocation_id = self.new_commitment('IGN')
        engineer = self.client_for(self.eng_user_id)
        response = engineer.post('/add_shift', data=self.schedule_payload('EngSched', 124, parts=[allocation_id]))
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(self.status(allocation_id), 'open')
        queued = self.admin.post('/add_shift', data=self.schedule_payload(
            'Queued', 125, parts=[allocation_id], creation_token=f'parts-queue-{self.suffix}'))
        self.assertEqual(queued.status_code, 200, queued.get_data(as_text=True))
        self.assertEqual(self.status(allocation_id), 'open')
        self.assertEqual(engineer.get(
            f'/api/parts-monitoring/commitments?machine_source=product&machine_serial={self.serial_a}').status_code, 403)

    def test_commitments_api_lists_open_and_this_schedules_parts(self):
        _part_id, allocation_id = self.new_commitment('LIST')
        url = f'/api/parts-monitoring/commitments?machine_source=product&machine_serial={self.serial_a}'
        ids = {row['id'] for row in self.admin.get(url).get_json()['commitments']}
        self.assertIn(allocation_id, ids)
        self.admin.post('/add_shift', data=self.schedule_payload('Listed', 127, parts=[allocation_id]))
        shift_id = self.chain('Listed')[0]
        self.assertNotIn(allocation_id, {row['id'] for row in self.admin.get(url).get_json()['commitments']})
        rows = self.admin.get(f'{url}&shift_id={shift_id}').get_json()['commitments']
        self.assertTrue(any(row['id'] == allocation_id and row['installed'] for row in rows))
        other = self.admin.get(f'/api/parts-monitoring/commitments?machine_source=product&machine_serial={self.serial_b}')
        self.assertNotIn(allocation_id, {row['id'] for row in other.get_json()['commitments']})

    def test_installed_parts_shown_to_schedule_viewers(self):
        _part_id, allocation_id = self.new_commitment('VIEW')
        self.admin.post('/add_shift', data=self.schedule_payload('Viewed', 130, parts=[allocation_id]))
        with self.app.app_context():
            group_id = app_module.db.session.get(app_module.Shift, self.chain('Viewed')[0]).group_id
        with self.app.test_request_context():
            parts = app_module.parts_monitoring_installed_parts_for_group(group_id)
        self.assertEqual(parts, [{'item_number': f'VIEW-{self.suffix}', 'item_description': 'Tube VIEW', 'quantity': 2}])
        timeline = (ROOT / 'templates' / 'timeline.html').read_text(encoding='utf-8')
        self.assertIn("'installed_parts': parts_monitoring_installed_parts_for_group(", (ROOT / 'app.py').read_text(encoding='utf-8'))
        self.assertIn('renderInstalledPartsReadonly(shift);', timeline)
        self.assertIn('With Parts Installation?', timeline)

    def test_deleting_a_used_part_hides_it(self):
        part_id, allocation_id = self.new_commitment('HIDE')
        self.admin.post('/add_shift', data=self.schedule_payload('Hidden', 133, parts=[allocation_id]))
        self.assertEqual(self.admin.delete(f'/api/parts-monitoring/items/{part_id}').status_code, 200)
        with self.app.app_context():
            part = app_module.db.session.get(app_module.PartsMonitoringItem, part_id)
            self.assertIsNotNone(part)
            self.assertFalse(part.is_active)

    def test_service_worker_bumped(self):
        assert_cache_version_at_least(self, 356)


class PartsMonitoringLowStockEmailTests(unittest.TestCase):
    """Parts Monitoring batch 4: one low-stock email per drop to the Settings group."""

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.suffix = uuid.uuid4().hex[:8]
        db = app_module.db
        with cls.app.app_context():
            db.create_all()
            admin = app_module.User(username=f'parts_mail_admin_{cls.suffix}',
                                    password=app_module.generate_password_hash('test-password'),
                                    role='superadmin', is_active=True)
            client_row = app_module.Client(name=f'Parts Mail Client {cls.suffix}', address='M')
            db.session.add_all([admin, client_row])
            db.session.flush()
            cls.serial = f'PM-MAIL-{cls.suffix}'
            db.session.add(app_module.Product(serial_number=cls.serial, name='Mail CT', client_id=client_row.id))
            db.session.commit()
            cls.admin_id, cls.client_id = admin.id, client_row.id

    @classmethod
    def tearDownClass(cls):
        db = app_module.db
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
            app_module.EmailRecipientSetting.query.filter(
                app_module.EmailRecipientSetting.email.like(f'%{cls.suffix}%')).delete(synchronize_session=False)
            app_module.Product.query.filter_by(serial_number=cls.serial).delete()
            app_module.Client.query.filter_by(id=cls.client_id).delete()
            app_module.User.query.filter_by(id=cls.admin_id).delete()
            db.session.commit()
            db.session.remove()

    def setUp(self):
        self.admin = self.app.test_client()
        with self.admin.session_transaction() as session:
            session['_user_id'] = str(self.admin_id)
            session['_fresh'] = True
        self.queued = []
        patcher = mock.patch.object(app_module, 'parts_monitoring_queue_low_stock_emails',
                                    side_effect=lambda alerts, url: self.queued.extend(alerts))
        patcher.start()
        self.addCleanup(patcher.stop)

    def new_part(self, label, stock, minimum):
        response = self.admin.post('/api/parts-monitoring/items', json={
            'item_number': f'{label}-{self.suffix}', 'item_description': f'Part {label}',
            'stock': stock, 'minimum_stock': minimum,
        })
        self.assertEqual(response.status_code, 201)
        return response.get_json()['item']['id']

    def reserve(self, part_id, quantity):
        return self.admin.post(f'/api/parts-monitoring/items/{part_id}/allocations',
                               json={'kind': 'reserved', 'quantity': quantity})

    def alerts_for(self, label):
        return [a for a in self.queued if a['item_number'] == f'{label}-{self.suffix}']

    def test_one_email_on_first_drop_none_while_still_low(self):
        part_id = self.new_part('DROP', stock=6, minimum=4)
        self.assertEqual(self.alerts_for('DROP'), [])
        self.reserve(part_id, 2)
        alerts = self.alerts_for('DROP')
        self.assertEqual(len(alerts), 1)
        self.assertEqual((alerts[0]['available'], alerts[0]['minimum_stock']), (4, 4))
        self.assertIn('Reserved 2', alerts[0]['cause'])
        self.reserve(part_id, 1)
        self.assertEqual(len(self.alerts_for('DROP')), 1)

    def test_new_email_after_restock_and_second_drop(self):
        part_id = self.new_part('AGAIN', stock=5, minimum=4)
        self.reserve(part_id, 1)
        self.assertEqual(len(self.alerts_for('AGAIN')), 1)
        self.admin.post(f'/api/parts-monitoring/items/{part_id}/stock', json={'quantity': 5})
        self.assertEqual(len(self.alerts_for('AGAIN')), 1)
        self.reserve(part_id, 6)
        self.assertEqual(len(self.alerts_for('AGAIN')), 2)

    def test_part_added_already_low_and_minimum_raise_alert(self):
        self.new_part('LOWNEW', stock=1, minimum=3)
        self.assertEqual(len(self.alerts_for('LOWNEW')), 1)
        part_id = self.new_part('RAISE', stock=5, minimum=1)
        self.admin.put(f'/api/parts-monitoring/items/{part_id}', json={
            'item_number': f'RAISE-{self.suffix}', 'item_description': 'Part RAISE', 'minimum_stock': 5})
        self.assertEqual(len(self.alerts_for('RAISE')), 1)

    def test_refused_change_sends_nothing(self):
        part_id = self.new_part('REF', stock=2, minimum=0)
        self.assertEqual(self.reserve(part_id, 5).status_code, 409)
        self.assertEqual(self.alerts_for('REF'), [])

    def test_sender_uses_the_settings_group_and_survives_failures(self):
        alert = {'item_number': f'S-{self.suffix}', 'item_description': 'Tube <x>', 'stock': 1, 'committed': 0,
                 'reserved': 0, 'available': 1, 'minimum_stock': 2, 'cause': 'Reserved 1 by admin'}
        with self.app.app_context():
            app_module.EmailRecipientSetting.query.filter_by(group_key='parts_low_stock').update({'is_active': False})
            app_module.db.session.commit()
            with mock.patch.object(app_module, 'send_email_notification') as send:
                app_module.parts_monitoring_send_low_stock_emails([alert], 'http://x/parts_monitoring')
                send.assert_not_called()  # no recipients yet
            app_module.db.session.add(app_module.EmailRecipientSetting(
                group_key='parts_low_stock', email=f'stock-{self.suffix}@example.com', is_active=True))
            app_module.db.session.commit()
            with mock.patch.object(app_module, 'send_email_notification', return_value=(True, 'ok')) as send:
                app_module.parts_monitoring_send_low_stock_emails([alert], 'http://x/parts_monitoring')
            recipients, subject, text_body, html_body = send.call_args[0]
            self.assertIn(f'stock-{self.suffix}@example.com', recipients)
            self.assertEqual(subject, f'Low stock: S-{self.suffix} Tube <x>')
            self.assertIn('Available: 1', text_body)
            self.assertIn('Tube &lt;x&gt;', html_body)
            with mock.patch.object(app_module, 'send_email_notification', side_effect=RuntimeError('quota')):
                app_module.parts_monitoring_send_low_stock_emails([alert], 'http://x/parts_monitoring')
            logged = app_module.ActivityLog.query.filter(
                app_module.ActivityLog.action.like(f'%low-stock email for part S-{self.suffix} failed%')).count()
            self.assertEqual(logged, 1)

    def test_settings_group_and_page_notice(self):
        self.assertIn('parts_low_stock', app_module.EMAIL_RECIPIENT_GROUPS)
        self.assertEqual(app_module.EMAIL_RECIPIENT_GROUPS['parts_low_stock']['label'], 'Parts Low Stock Alert')
        with self.app.app_context():
            app_module.EmailRecipientSetting.query.filter_by(group_key='parts_low_stock').update({'is_active': False})
            app_module.db.session.commit()
        page = self.admin.get('/parts_monitoring').get_data(as_text=True)
        self.assertIn('Low-stock emails are off', page)
        with self.app.app_context():
            app_module.db.session.add(app_module.EmailRecipientSetting(
                group_key='parts_low_stock', email=f'notice-{self.suffix}@example.com', is_active=True))
            app_module.db.session.commit()
        page = self.admin.get('/parts_monitoring').get_data(as_text=True)
        self.assertNotIn('Low-stock emails are off', page)

    def test_service_worker_bumped(self):
        assert_cache_version_at_least(self, 358)


if __name__ == '__main__':
    unittest.main()
