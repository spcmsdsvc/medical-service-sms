"""Behavioral and source-level coverage for the upgraded Analytics page."""

import pathlib
import unittest
import uuid
from datetime import datetime

import app as app_module  # noqa: E402

from tests.sw_cache_version import assert_cache_version_at_least  # noqa: E402


ROOT = pathlib.Path(__file__).resolve().parents[1]


class AnalyticsPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.suffix = uuid.uuid4().hex[:10]
        cls.created_user_ids = []
        cls.created_engineer_ids = []
        cls.created_client_ids = []
        cls.created_shift_ids = []

        cls.source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.template = (ROOT / 'templates' / 'analytics.html').read_text(encoding='utf-8')
        cls.css = (ROOT / 'static' / 'css' / 'app-analytics.css').read_text(encoding='utf-8')
        cls.js = (ROOT / 'static' / 'js' / 'app-analytics.js').read_text(encoding='utf-8')

        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_user_admin_capability_columns()

            def add_user(username, role='staff', **flags):
                user = app_module.User(
                    username=f'{username}_{cls.suffix}',
                    password=app_module.generate_password_hash('test-password'),
                    role=role,
                    is_active=True,
                    **flags,
                )
                app_module.db.session.add(user)
                app_module.db.session.flush()
                cls.created_user_ids.append(user.id)
                return user

            cls.reports_user = add_user('analytics_reports', reports_admin_access=True)
            cls.po_user = add_user('analytics_po', po_admin_access=True)
            cls.plain_user = add_user('analytics_plain')

            cls.regional_user = app_module.User.query.filter_by(username='kevin').first()
            if not cls.regional_user:
                cls.regional_user = app_module.User(
                    username='kevin',
                    password=app_module.generate_password_hash('test-password'),
                    role='regional_admin',
                    is_active=True,
                )
                app_module.db.session.add(cls.regional_user)
                app_module.db.session.flush()
                cls.created_user_ids.append(cls.regional_user.id)

            regional_profile = app_module.Engineer.query.filter_by(
                user_id=cls.regional_user.id
            ).first()
            if not regional_profile:
                regional_profile = app_module.Engineer(
                    user_id=cls.regional_user.id,
                    employee_id=app_module.REGIONAL_ADMIN_EMPLOYEE_ID,
                    name=f'Analytics Regional Admin {cls.suffix}',
                    initials='ARA',
                    branch='Cebu',
                )
                app_module.db.session.add(regional_profile)
                app_module.db.session.flush()
                cls.created_engineer_ids.append(regional_profile.id)

            cls.engineers = []
            for code, branch in (('MNL', 'Manila'), ('CEB', 'Cebu'), ('DAV', 'Davao')):
                engineer = app_module.Engineer(
                    employee_id=f'AN-{code}-{cls.suffix}',
                    name=f'Analytics {branch} "><img src=x onerror=alert(1)>',
                    initials=code,
                    branch=branch,
                )
                cls.engineers.append(engineer)
                app_module.db.session.add(engineer)
            app_module.db.session.flush()
            cls.created_engineer_ids.extend(engineer.id for engineer in cls.engineers)

            cls.client = app_module.Client(
                name=f'Analytics Client {cls.suffix} "><img src=x onerror=alert(1)>',
                address='Analytics test address',
            )
            app_module.db.session.add(cls.client)
            app_module.db.session.flush()
            cls.created_client_ids.append(cls.client.id)

            def add_shift(day, title, primary_engineer, status, hour):
                shift = app_module.Shift(
                    title=title,
                    start_time=datetime(2026, 8, day, hour, 0),
                    end_time=datetime(2026, 8, day, hour + 2, 0),
                    engineer_id=primary_engineer.id,
                    client_id=cls.client.id,
                    status=status,
                )
                app_module.db.session.add(shift)
                app_module.db.session.flush()
                cls.created_shift_ids.append(shift.id)
                return shift

            # One shift has three linked engineers. It must count as one schedule and
            # three assignments, which is the regression the old join-based query missed.
            cls.multi_shift = add_shift(
                6,
                'Preventive Maintenance',
                cls.engineers[0],
                'In Progress',
                9,
            )
            cls.completed_shift = add_shift(
                6,
                'Checkup',
                cls.engineers[1],
                'Completed',
                13,
            )
            cls.previous_shift = add_shift(
                5,
                'Previous Visit',
                cls.engineers[0],
                'Completed',
                10,
            )
            # A primary engineer without a ShiftEngineer membership is intentionally
            # excluded to preserve the historical Analytics scope contract.
            cls.invisible_shift = add_shift(
                6,
                'Primary Only Legacy Shift',
                cls.engineers[2],
                'In Progress',
                15,
            )

            memberships = [
                (cls.multi_shift.id, cls.engineers[0].id),
                (cls.multi_shift.id, cls.engineers[1].id),
                (cls.multi_shift.id, cls.engineers[2].id),
                (cls.completed_shift.id, cls.engineers[1].id),
                (cls.previous_shift.id, cls.engineers[0].id),
            ]
            app_module.db.session.add_all([
                app_module.ShiftEngineer(shift_id=shift_id, engineer_id=engineer_id)
                for shift_id, engineer_id in memberships
            ])
            app_module.db.session.commit()

            cls.reports_user_id = cls.reports_user.id
            cls.po_user_id = cls.po_user.id
            cls.plain_user_id = cls.plain_user.id
            cls.regional_user_id = cls.regional_user.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            app_module.db.session.query(app_module.ShiftEngineer).filter(
                app_module.ShiftEngineer.shift_id.in_(cls.created_shift_ids)
            ).delete(synchronize_session=False)
            for shift_id in cls.created_shift_ids:
                shift = app_module.db.session.get(app_module.Shift, shift_id)
                if shift:
                    app_module.db.session.delete(shift)
            for client_id in cls.created_client_ids:
                client = app_module.db.session.get(app_module.Client, client_id)
                if client:
                    app_module.db.session.delete(client)
            for engineer_id in reversed(cls.created_engineer_ids):
                engineer = app_module.db.session.get(app_module.Engineer, engineer_id)
                if engineer:
                    app_module.db.session.delete(engineer)
            for user_id in reversed(cls.created_user_ids):
                user = app_module.db.session.get(app_module.User, user_id)
                if user:
                    app_module.db.session.delete(user)
            app_module.db.session.commit()
            app_module.db.session.remove()

    @classmethod
    def _client_for(cls, user_id):
        client = cls.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def test_page_is_tokenized_accessible_and_separates_p_o_only_view(self):
        self.assertNotIn('<style>', self.template)
        self.assertIn('css/app-analytics.css', self.template)
        self.assertIn('js/app-analytics.js', self.template)
        self.assertIn('aria-live="polite"', self.template)
        self.assertIn('scope="col"', self.template)
        self.assertIn('caption', self.template)
        self.assertIn('createElementNS', self.js)
        self.assertIn('textContent', self.js)
        self.assertNotIn('innerHTML', self.js)
        self.assertIn('@media print', self.css)
        self.assertIn('var(--app-', self.css)
        self.assertRegex(self.css, r'\.analytics-grid-2\s*\{[^}]*align-items:\s*start')
        self.assertNotIn('analytics-', (ROOT / 'static' / 'css' / 'app-dark-pages.css').read_text(encoding='utf-8'))
        assert_cache_version_at_least(self, 73, self.source)
        self.assertIn("'/static/css/app-analytics.css',", self.source)
        self.assertIn("'/static/js/app-analytics.js',", self.source)

    def test_schedule_analytics_deduplicates_and_exposes_period_contract(self):
        client = self._client_for(self.reports_user_id)
        response = client.get('/get_analytics_summary?start_date=2026-08-06&end_date=2026-08-06')
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()

        self.assertEqual(payload['range_total'], 2)
        self.assertEqual(payload['assignment_total'], 4)
        self.assertEqual(payload['flow']['total']['previous'], 1)
        self.assertNotIn('statuses', payload)

        # Flow carries a comparison; stock never does. `active` is exactly
        # `total - completed`, so an arrow on it is an arrow on -completed: recent work has
        # had less time to finish. `completed` was already excluded for that reason and its
        # complement has to be excluded on the same grounds.
        self.assertIn('previous', payload['flow']['total'])
        for stock_key in ('active', 'open_client_work', 'completed'):
            self.assertNotIn(
                'previous', payload['stock'][stock_key],
                f'{stock_key} is stock and must not carry a period comparison',
            )
            self.assertIn('basis', payload['stock'][stock_key])
        self.assertNotIn('active', payload['flow'])

        # The arithmetic the exclusion rests on, asserted so it cannot drift.
        self.assertEqual(
            payload['stock']['active']['value'] + payload['stock']['completed']['value'],
            payload['flow']['total']['value'],
        )

        # Returned and consumed only. previous_open_statuses was shipped and never read.
        self.assertNotIn('previous_open_statuses', payload)
        self.assertEqual(payload['trend']['current'][0]['count'], 2)
        self.assertEqual(payload['trend']['previous'][0]['count'], 1)
        self.assertEqual(len(payload['trend']['current']), len(payload['trend']['previous']))

        counts = {row['name']: row['count'] for row in payload['engineers']}
        self.assertEqual(counts[f'Analytics Manila "><img src=x onerror=alert(1)>'], 1)
        self.assertEqual(counts[f'Analytics Cebu "><img src=x onerror=alert(1)>'], 2)
        self.assertEqual(counts[f'Analytics Davao "><img src=x onerror=alert(1)>'], 1)

    def test_branch_filter_narrows_both_schedules_and_assignments(self):
        client = self._client_for(self.reports_user_id)
        response = client.get(
            '/get_analytics_summary?start_date=2026-08-06&end_date=2026-08-06&branch=Manila'
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['range_total'], 1)
        self.assertEqual(payload['assignment_total'], 1)
        self.assertEqual(payload['engineers'][0]['branch'], 'Manila')

    def test_regional_admin_can_select_manila_read_scope(self):
        client = self._client_for(self.regional_user_id)
        response = client.get(
            '/get_analytics_summary?start_date=2026-08-06&end_date=2026-08-06&branch=Manila'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['branch'], 'Manila')

    def test_reports_export_and_tsr_archive_scope_remain_available(self):
        client = self._client_for(self.reports_user_id)
        export = client.get('/export_analytics_summary?start_date=2026-08-06&end_date=2026-08-06')
        self.assertEqual(export.status_code, 200)
        csv_text = export.get_data(as_text=True)
        self.assertEqual(len(csv_text.strip().splitlines()), 3)

        archive = client.get('/get_tsr_archive?scope=my&page=1&per_page=10')
        self.assertEqual(archive.status_code, 200)
        self.assertEqual(archive.get_json()['scope'], 'my')

    def test_schedule_analytics_stays_reports_only(self):
        """Called, not read as source.

        This replaced an assertIn on the literal "if not can_view_admin_reports():". A
        pinned rule string cannot tell you the rule holds, only that the text is present --
        the practice this repository has already had to undo five times.
        """
        reports = self._client_for(self.reports_user_id)
        self.assertEqual(reports.get('/get_analytics_summary').status_code, 200)

        with self.app.app_context():
            target = app_module.db.session.get(app_module.User, self.reports_user_id)
            target.reports_admin_access = False
            app_module.db.session.commit()
        try:
            stripped = self._client_for(self.reports_user_id)
            self.assertEqual(stripped.get('/get_analytics_summary').status_code, 403)
        finally:
            with self.app.app_context():
                target = app_module.db.session.get(app_module.User, self.reports_user_id)
                target.reports_admin_access = True
                app_module.db.session.commit()

    def test_reports_admin_sees_the_purchase_order_panel(self):
        """The panel gate must match /get_po_analytics, which uses either capability.

        Reading it from the P.O. capability alone hid the panel from reports admins while
        the endpoint still served them 200. Superadmins pass either way, so only a granted
        account shows the gap.
        """
        client = self._client_for(self.reports_user_id)
        page = client.get('/analytics_page')
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn('Purchase order reporting', html)
        self.assertEqual(client.get('/get_po_analytics').status_code, 200)

        # Positive control: the same page still gates the schedule panels separately, so
        # this is not passing because every panel renders for everyone.
        self.assertIn('Service activity', html)


if __name__ == '__main__':
    unittest.main()
