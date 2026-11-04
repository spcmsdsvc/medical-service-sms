"""On-Call Schedule: admin-only weekend type, engineer read-only, per-day conversion, restore on delete."""

import json
import unittest
import uuid
from datetime import timedelta
from unittest import mock

import app as app_module
from tests.sw_cache_version import assert_cache_version_at_least


ON_CALL = 'On-Call Schedule'


class OnCallScheduleTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.suffix = uuid.uuid4().hex[:8]
        db = app_module.db
        with cls.app.app_context():
            db.create_all()
            password = app_module.generate_password_hash('test-password')
            admin = app_module.User(username=f'oncall_admin_{cls.suffix}', password=password,
                                    role='superadmin', is_active=True)
            eng_user_a = app_module.User(username=f'oncall_eng_a_{cls.suffix}', password=password,
                                         role='engineer', is_active=True)
            eng_user_b = app_module.User(username=f'oncall_eng_b_{cls.suffix}', password=password,
                                         role='engineer', is_active=True)
            client_row = app_module.Client(name=f'OnCall Client {cls.suffix}', address='X')
            db.session.add_all([admin, eng_user_a, eng_user_b, client_row])
            db.session.flush()
            eng_a = app_module.Engineer(employee_id=f'OCA-{cls.suffix}', name=f'OnCall Alvin {cls.suffix}',
                                        initials='OA', branch='Manila', user_id=eng_user_a.id)
            eng_b = app_module.Engineer(employee_id=f'OCB-{cls.suffix}', name=f'OnCall Martin {cls.suffix}',
                                        initials='OM', branch='Manila', user_id=eng_user_b.id)
            db.session.add_all([eng_a, eng_b])
            cls.serial = f'OC-{cls.suffix}'
            db.session.add(app_module.Product(serial_number=cls.serial, name='Fluoro OC', client_id=client_row.id))
            db.session.commit()
            cls.admin_id = admin.id
            cls.eng_user_a_id, cls.eng_user_b_id = eng_user_a.id, eng_user_b.id
            cls.eng_a_id, cls.eng_b_id = eng_a.id, eng_b.id
            cls.client_id = client_row.id
            today = app_module.get_manila_today()
        # A Saturday far enough ahead to be clear of everything else.
        start = today + timedelta(days=200)
        cls.saturday = start + timedelta(days=(5 - start.weekday()) % 7)
        cls.used_weekends = 0

    @classmethod
    def tearDownClass(cls):
        db = app_module.db
        with cls.app.app_context():
            engineer_ids = [cls.eng_a_id, cls.eng_b_id]
            shift_ids = {row.shift_id for row in app_module.ShiftEngineer.query.filter(
                app_module.ShiftEngineer.engineer_id.in_(engineer_ids)).all()}
            shift_ids |= {row.id for row in app_module.Shift.query.filter(
                app_module.Shift.engineer_id.in_(engineer_ids)).all()}
            if shift_ids:
                app_module.ShiftEngineer.query.filter(app_module.ShiftEngineer.shift_id.in_(shift_ids)).delete(
                    synchronize_session=False)
                app_module.Shift.query.filter(app_module.Shift.id.in_(shift_ids)).delete(synchronize_session=False)
            app_module.ActivityLog.query.filter(
                app_module.ActivityLog.action.like(f'%{cls.suffix}%')).delete(synchronize_session=False)
            app_module.Product.query.filter_by(serial_number=cls.serial).delete()
            app_module.Engineer.query.filter(app_module.Engineer.id.in_(engineer_ids)).delete(synchronize_session=False)
            app_module.Client.query.filter_by(id=cls.client_id).delete()
            app_module.User.query.filter(app_module.User.id.in_(
                [cls.admin_id, cls.eng_user_a_id, cls.eng_user_b_id])).delete(synchronize_session=False)
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
        self.engineer = self.client_for(self.eng_user_a_id)
        type(self).used_weekends += 1
        # Each test gets its own weekend so no test collides with another.
        self.sat = self.saturday + timedelta(days=7 * self.used_weekends)
        self.sun = self.sat + timedelta(days=1)

    # Fixtures
    def payload(self, start, end, title=ON_CALL, engineers=None, **extra):
        engineers = engineers or [self.eng_a_id]
        data = {
            'title': title,
            'start_date': start.isoformat(), 'end_date': end.isoformat(),
            'start_time': '08:00', 'end_time': '17:00',
            'include_weekends': 'true',
            'engineers': json.dumps(engineers), 'engineer_id': str(engineers[0]),
            'status': 'In Progress',
        }
        data.update(extra)
        return data

    def visit_payload(self, day, engineers=None, scope='assigned_engineers_day_only'):
        return self.payload(day, day, title=f'Breakdown call {self.suffix}', engineers=engineers,
                            client_id=str(self.client_id), product_id=self.serial,
                            equipment_source='product', edit_scope=scope,
                            start_time='10:00', end_time='15:00')

    def rows(self, engineer_id, start=None, end=None):
        start, end = start or self.sat, end or self.sun
        with self.app.app_context():
            query = (app_module.db.session.query(app_module.Shift)
                     .join(app_module.ShiftEngineer, app_module.Shift.id == app_module.ShiftEngineer.shift_id)
                     .filter(app_module.ShiftEngineer.engineer_id == engineer_id,
                             app_module.db.func.date(app_module.Shift.start_time) >= start,
                             app_module.db.func.date(app_module.Shift.start_time) <= end)
                     .order_by(app_module.Shift.start_time))
            return [
                {'id': s.id, 'title': s.title, 'client_id': s.client_id, 'group_id': s.group_id,
                 'date': s.start_time.date(), 'origin': s.on_call_origin,
                 'start': s.start_time.strftime('%H:%M')}
                for s in query.all()
            ]

    def add_on_call(self, engineers=None):
        response = self.admin.post('/add_shift', data=self.payload(self.sat, self.sun, engineers=engineers))
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return self.rows(self.eng_a_id)

    def convert_saturday(self, engineers=None):
        saturday_row = self.add_on_call()[0]
        response = self.admin.post(f"/update_shift/{saturday_row['id']}", data=self.visit_payload(self.sat, engineers))
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return saturday_row

    # Batch 1 - creating
    def test_engineer_cannot_add_on_call(self):
        response = self.engineer.post('/add_shift', data=self.payload(self.sat, self.sun))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.rows(self.eng_a_id), [])

    def test_weekday_in_range_is_refused(self):
        friday = self.sat - timedelta(days=1)
        response = self.admin.post('/add_shift', data=self.payload(friday, self.sun))
        self.assertEqual(response.status_code, 400)
        self.assertIn('Saturday or Sunday', response.get_json()['message'])

    def test_admin_adds_weekend_on_call_without_client(self):
        rows = self.add_on_call()
        self.assertEqual([r['date'] for r in rows], [self.sat, self.sun])
        self.assertTrue(all(r['title'] == ON_CALL and r['client_id'] is None for r in rows))

    def test_client_sent_with_on_call_is_dropped(self):
        response = self.admin.post('/add_shift', data=self.payload(
            self.sat, self.sat, client_id=str(self.client_id), product_id=self.serial, equipment_source='product'))
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertIsNone(self.rows(self.eng_a_id)[0]['client_id'])

    def test_two_engineers_get_separate_chains_and_emails(self):
        with mock.patch.object(app_module, 'notify_engineers_for_new_schedule_async') as notify:
            self.add_on_call(engineers=[self.eng_a_id, self.eng_b_id])
        rows_a, rows_b = self.rows(self.eng_a_id), self.rows(self.eng_b_id)
        self.assertEqual((len(rows_a), len(rows_b)), (2, 2))
        self.assertEqual(len({r['group_id'] for r in rows_a}), 1)
        self.assertNotEqual(rows_a[0]['group_id'], rows_b[0]['group_id'])
        self.assertEqual(sorted(call.args[2] for call in notify.call_args_list), sorted([[self.eng_a_id], [self.eng_b_id]]))

    # Batch 1 - engineers are read-only
    def test_engineer_cannot_edit_move_or_delete_on_call(self):
        rows = self.add_on_call()
        shift_id = rows[0]['id']
        edit = self.engineer.post(f'/update_shift/{shift_id}', data=self.payload(
            self.sat, self.sat, edit_scope='assigned_engineers_day_only', start_time='09:00'))
        self.assertEqual(edit.status_code, 403)
        move = self.engineer.post('/move_shift', json={
            'shift_id': shift_id, 'source_engineer_id': self.eng_a_id, 'new_engineer_id': self.eng_a_id,
            'new_start_date': (self.sat + timedelta(days=7)).isoformat(), 'move_mode': 'team'})
        self.assertEqual(move.status_code, 403)
        self.assertEqual(self.engineer.delete(f'/delete_shift/{shift_id}').status_code, 403)
        preview_body = {'shift_id': shift_id, 'delete_mode': 'single', 'engineer_id': self.eng_a_id}
        self.assertEqual(self.engineer.post('/preview_delete_shifts', json=preview_body).status_code, 403)
        self.assertEqual(self.engineer.post('/delete_shifts_previewed', json=preview_body).status_code, 403)
        purge = self.engineer.post('/batch_delete_shifts', json={
            'engineer_id': self.eng_a_id, 'start_date': self.sat.isoformat(), 'end_date': self.sun.isoformat()})
        self.assertEqual(purge.status_code, 403)
        self.assertEqual(len(self.rows(self.eng_a_id)), 2)

    def test_admin_cannot_put_on_call_on_a_weekday(self):
        rows = self.add_on_call()
        monday = self.sun + timedelta(days=1)
        edit = self.admin.post(f"/update_shift/{rows[0]['id']}", data=self.payload(
            self.sat, monday, edit_scope='entire_schedule'))
        self.assertEqual(edit.status_code, 400)
        move = self.admin.post('/move_shift', json={
            'shift_id': rows[0]['id'], 'source_engineer_id': self.eng_a_id, 'new_engineer_id': self.eng_a_id,
            'new_start_date': self.sun.isoformat(), 'move_mode': 'team'})
        self.assertEqual(move.status_code, 400)
        self.assertEqual([r['date'] for r in self.rows(self.eng_a_id)], [self.sat, self.sun])

    # Batch 2 - converting
    def test_admin_converts_one_day_and_the_other_stays_on_call(self):
        saturday_row = self.convert_saturday()
        saturday, sunday = self.rows(self.eng_a_id)
        self.assertEqual(saturday['client_id'], self.client_id)
        self.assertNotEqual(saturday['group_id'], saturday_row['group_id'])
        origin = json.loads(saturday['origin'])
        self.assertEqual(origin['engineer_id'], self.eng_a_id)
        self.assertTrue(origin['start'].endswith('08:00:00'))
        self.assertEqual(sunday['title'], ON_CALL)
        self.assertEqual(sunday['group_id'], saturday_row['group_id'])
        self.assertIsNone(sunday['origin'])

    def test_conversion_must_be_one_day_and_by_an_admin(self):
        saturday_row = self.add_on_call()[0]
        whole = self.admin.post(f"/update_shift/{saturday_row['id']}", data=self.visit_payload(
            self.sat, scope='entire_schedule'))
        self.assertEqual(whole.status_code, 400)
        by_engineer = self.engineer.post(f"/update_shift/{saturday_row['id']}", data=self.visit_payload(self.sat))
        self.assertEqual(by_engineer.status_code, 403)
        self.assertTrue(all(r['title'] == ON_CALL for r in self.rows(self.eng_a_id)))

    def test_converted_visit_has_badge_flag_and_engineer_can_edit_it(self):
        self.convert_saturday()
        visit_id = self.rows(self.eng_a_id)[0]['id']
        details = self.engineer.get(f'/get_shift_details/{visit_id}').get_json()['shift']
        self.assertTrue(details.get('from_on_call'), details)
        edit = self.engineer.post(f'/update_shift/{visit_id}', data=self.visit_payload(self.sat))
        self.assertEqual(edit.status_code, 200, edit.get_data(as_text=True))

    def test_deleting_converted_visit_restores_on_call(self):
        self.convert_saturday()
        visit_id = self.rows(self.eng_a_id)[0]['id']
        response = self.engineer.delete(f'/delete_shift/{visit_id}')
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        saturday, sunday = self.rows(self.eng_a_id)
        self.assertEqual((saturday['title'], saturday['start'], saturday['client_id']), (ON_CALL, '08:00', None))
        self.assertNotEqual(saturday['group_id'], sunday['group_id'])

    def test_removing_origin_engineer_from_shared_visit_restores_on_call(self):
        self.convert_saturday(engineers=[self.eng_a_id, self.eng_b_id])
        visit_id = self.rows(self.eng_a_id)[0]['id']
        response = self.admin.post('/delete_shifts_previewed', json={
            'shift_id': visit_id, 'delete_mode': 'single', 'engineer_id': self.eng_a_id})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(self.rows(self.eng_a_id)[0]['title'], ON_CALL)
        martin_rows = self.rows(self.eng_b_id)
        self.assertEqual([r['client_id'] for r in martin_rows], [self.client_id])

    def test_range_purge_does_not_restore(self):
        self.convert_saturday()
        response = self.admin.post('/batch_delete_shifts', json={
            'engineer_id': self.eng_a_id, 'start_date': self.sat.isoformat(), 'end_date': self.sun.isoformat()})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(self.rows(self.eng_a_id), [])

    def test_service_worker_bumped(self):
        assert_cache_version_at_least(self, 357)


if __name__ == '__main__':
    unittest.main()
