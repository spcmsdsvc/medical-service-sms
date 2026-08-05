"""Regression coverage for the restricted HR schedule viewer."""

import os
import pathlib
import tempfile
import unittest
import uuid
from datetime import timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Pin an isolated database before importing app.py so this module never touches the
# project database when run by itself.
_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_hr_schedule_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402
from tests.sw_cache_version import assert_cache_version_at_least  # noqa: E402


class HRScheduleViewerSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.layout = (ROOT / 'templates' / 'layout.html').read_text(encoding='utf-8')
        cls.settings = (ROOT / 'templates' / 'settings.html').read_text(encoding='utf-8')
        cls.timeline = (ROOT / 'templates' / 'timeline.html').read_text(encoding='utf-8')
        cls.releases = (ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8')

    def test_schema_permission_guard_and_redaction_are_present(self):
        for expected in (
            'hr_schedule_view = db.Column(db.Boolean, default=False, nullable=False)',
            'def ensure_user_hr_schedule_view_column():',
            'def is_hr_schedule_viewer(user=None):',
            'def is_hr_schedule_only_user(user=None):',
            'def is_hr_schedule_engineer_profile(engineer=None):',
            'def redact_timeline_payload_for_hr(payload):',
            "@app.route('/get_timeline_data')",
            'restrict_hr_schedule_only_accounts',
        ):
            self.assertIn(expected, self.app_source)

    def test_settings_toggle_and_restricted_navigation_are_present(self):
        self.assertIn('hr_schedule_view', self.settings)
        self.assertIn('hrScheduleViewChecked', self.settings)
        self.assertIn('hr_schedule_only_user', self.layout)
        self.assertIn("nav_link('/timeline', 'fa-calendar-days', 'Calendar')", self.layout)
        self.assertIn("nav_link('/settings', 'fa-key', 'Password Settings')", self.layout)
        self.assertIn('timelineReadOnlyHR', self.timeline)
        self.assertIn('HR Schedule View', self.timeline)
        self.assertIn('timelineReadOnlyHR ||', self.timeline)

    def test_release_and_service_worker_are_bumped(self):
        self.assertIn('2026-08-05-hr-schedule-viewer', self.releases)
        assert_cache_version_at_least(self, 64, self.app_source)


class HRScheduleViewerWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.suffix = uuid.uuid4().hex[:10]

        with cls.app.app_context():
            app_module.db.create_all()

            cls.hr_user = app_module.User(
                username=f'hr_viewer_{cls.suffix}',
                password=app_module.generate_password_hash('HRViewer123'),
                role='staff',
                is_active=True,
                hr_schedule_view=True,
            )
            cls.engineer_user = app_module.User(
                username=f'hr_engineer_{cls.suffix}',
                password=app_module.generate_password_hash('HREngineer123'),
                role='engineer',
                is_active=True,
                hr_schedule_view=True,
            )
            app_module.db.session.add_all([cls.hr_user, cls.engineer_user])
            app_module.db.session.commit()
            cls.hr_user_id = cls.hr_user.id
            cls.engineer_user_id = cls.engineer_user.id

            cls.engineer = app_module.Engineer(
                user_id=cls.engineer_user.id,
                employee_id=f'HR-E-{cls.suffix}',
                name='HR Calendar Engineer',
                initials='HCE',
                branch='Cebu',
                phone='09170000000',
                email='hr-engineer@example.test',
            )
            cls.visible_engineer = app_module.Engineer(
                employee_id=f'CAL-E-{cls.suffix}',
                name='Visible Calendar Engineer',
                initials='VCE',
                branch='Cebu',
                phone='09171111111',
                email='visible-engineer@example.test',
            )
            cls.client_record = app_module.Client(
                name='HR Viewer Client',
                address='Commercial address must not be exposed',
                contact_person_1='Private Contact',
                contact_number_1='09179999999',
                email_address_1='private@example.test',
            )
            app_module.db.session.add_all([cls.engineer, cls.visible_engineer, cls.client_record])
            app_module.db.session.commit()
            cls.engineer_id = cls.engineer.id
            cls.visible_engineer_id = cls.visible_engineer.id
            cls.client_id = cls.client_record.id

            today = app_module.get_manila_today()
            start_dt, end_dt = app_module.build_shift_datetime_bounds(today, today)
            cls.shift = app_module.Shift(
                title='Private equipment installation for HR redaction',
                start_time=start_dt + timedelta(hours=8),
                end_time=start_dt + timedelta(hours=17),
                engineer_id=cls.visible_engineer.id,
                client_id=cls.client_record.id,
                status='In Progress',
            )
            app_module.db.session.add(cls.shift)
            app_module.db.session.commit()
            cls.shift_id = cls.shift.id
            app_module.db.session.add(app_module.ShiftEngineer(
                shift_id=cls.shift.id,
                engineer_id=cls.visible_engineer.id,
            ))
            app_module.db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            shift = app_module.db.session.get(app_module.Shift, cls.shift_id)
            if shift:
                app_module.ShiftEngineer.query.filter_by(shift_id=cls.shift_id).delete()
                app_module.db.session.delete(shift)
            engineer = app_module.db.session.get(app_module.Engineer, cls.engineer_id)
            if engineer:
                app_module.db.session.delete(engineer)
            visible_engineer = app_module.db.session.get(app_module.Engineer, cls.visible_engineer_id)
            if visible_engineer:
                app_module.db.session.delete(visible_engineer)
            client = app_module.db.session.get(app_module.Client, cls.client_id)
            if client:
                app_module.db.session.delete(client)
            for user_id in (cls.hr_user_id, cls.engineer_user_id):
                user = app_module.db.session.get(app_module.User, user_id)
                if user:
                    app_module.db.session.delete(user)
            app_module.db.session.commit()

    def _client_for(self, user_id):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def test_hr_calendar_is_available_but_other_pages_redirect(self):
        client = self._client_for(self.hr_user_id)

        calendar = client.get('/')
        self.assertEqual(calendar.status_code, 302)
        self.assertTrue(calendar.headers['Location'].endswith('/timeline'))

        timeline = client.get('/timeline')
        self.assertEqual(timeline.status_code, 200)
        html = timeline.get_data(as_text=True)
        self.assertIn('HR Schedule View', html)
        self.assertIn('Password Settings', client.get('/settings').get_data(as_text=True))

        reimbursement = client.get('/reimbursement')
        self.assertEqual(reimbursement.status_code, 302)
        self.assertTrue(reimbursement.headers['Location'].endswith('/'))

    def test_hr_timeline_feed_keeps_schedule_context_and_redacts_sensitive_detail(self):
        client = self._client_for(self.hr_user_id)
        response = client.get('/get_timeline_data?offset=0&branch=ALL')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()

        rows = []
        for day_map in payload['schedule'].values():
            for day_rows in day_map.values():
                rows.extend(day_rows)
        row = next(item for item in rows if item['id'] == self.shift_id)

        self.assertEqual(row['client_name'], 'HR Viewer Client')
        self.assertEqual(row['client_address'], '')
        self.assertEqual(row['product_name'], '')
        self.assertIsNone(row['client_id'])
        self.assertIsNone(row['product_id'])
        self.assertEqual(row['task'], 'Service Schedule')
        self.assertEqual(row['engineers'], [self.visible_engineer_id])
        self.assertEqual(row['status'], 'In Progress')
        self.assertEqual(row['file_details'], [])
        self.assertNotIn('download_url', row)
        self.assertNotIn('Commercial address', str(row))
        self.assertNotIn('Private equipment installation', str(row))

        clients = client.get('/get_clients')
        self.assertEqual(clients.status_code, 200)
        client_row = next(item for item in clients.get_json() if item['id'] == self.client_id)
        self.assertEqual(set(client_row), {'id', 'name'})

        products = client.get('/get_products')
        self.assertEqual(products.status_code, 200)
        self.assertEqual(products.get_json(), [])

        engineers = client.get('/get_engineers')
        self.assertEqual(engineers.status_code, 200)
        engineer_row = next(item for item in engineers.get_json() if item['id'] == self.visible_engineer_id)
        self.assertEqual(set(engineer_row), {'id', 'name', 'initials', 'branch'})

    def test_hr_flagged_personnel_is_hidden_from_calendar(self):
        client = self._client_for(self.hr_user_id)

        timeline = client.get('/get_timeline_data?offset=0&branch=ALL').get_json()
        timeline_rows = [
            row
            for day_map in timeline['schedule'].values()
            for day_rows in day_map.values()
            for row in day_rows
        ]
        self.assertNotIn(str(self.engineer_id), timeline['schedule'])
        self.assertNotIn(self.engineer_id, [engineer_id for row in timeline_rows for engineer_id in row.get('engineers', [])])

        calendar_engineers = client.get('/get_engineers?calendar=1').get_json()
        self.assertNotIn(self.engineer_id, [row['id'] for row in calendar_engineers])
        self.assertIn(self.visible_engineer_id, [row['id'] for row in calendar_engineers])

    def test_hr_write_endpoints_are_denied_even_with_direct_requests(self):
        client = self._client_for(self.hr_user_id)
        headers = {'Accept': 'application/json'}
        requests = (
            ('post', '/add_shift', {}),
            ('post', f'/update_shift/{self.shift_id}', {}),
            ('post', '/move_shift', {}),
            ('delete', f'/delete_shift/{self.shift_id}'),
            ('post', '/batch_delete_shifts', {}),
            ('post', '/preview_delete_shifts', {}),
            ('post', '/delete_shifts_previewed', {}),
            ('post', '/scheduler_quick_assign_shift', {}),
            ('post', '/scheduler_quick_reschedule_shift', {}),
            ('post', '/quick_add_timeline_client', {}),
        )

        for method, path, *body in requests:
            kwargs = {'headers': headers}
            if body:
                kwargs['json'] = body[0]
            response = getattr(client, method)(path, **kwargs)
            self.assertEqual(response.status_code, 403, f'{method.upper()} {path} was not denied')

    def test_hr_flag_does_not_strip_an_engineer_profile_account(self):
        with self.app.app_context():
            engineer_user = app_module.db.session.get(app_module.User, self.engineer_user_id)
            hr_user = app_module.db.session.get(app_module.User, self.hr_user_id)
            self.assertTrue(app_module.is_hr_schedule_viewer(engineer_user))
            self.assertFalse(app_module.is_hr_schedule_only_user(engineer_user))
            self.assertTrue(app_module.is_hr_schedule_only_user(hr_user))


if __name__ == '__main__':
    unittest.main()
