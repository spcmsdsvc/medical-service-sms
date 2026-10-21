"""Analytics page: correct numbers, overdue / top clients / field days, shared design, phone layout.

The run shares one database across test modules, so the behavioural tests measure the change
their own rows make (call, add rows, call again) rather than absolute totals another module
could disturb.
"""

import pathlib
import re
import unittest
import uuid
from datetime import datetime, timedelta

import app as app_module  # noqa: E402


ROOT = pathlib.Path(__file__).resolve().parents[1]


class AnalyticsBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.suffix = uuid.uuid4().hex[:10]
        cls.template = (ROOT / 'templates' / 'analytics.html').read_text(encoding='utf-8')
        cls.css = (ROOT / 'static' / 'css' / 'app-analytics.css').read_text(encoding='utf-8')
        cls.js = (ROOT / 'static' / 'js' / 'app-analytics.js').read_text(encoding='utf-8')

        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_user_admin_capability_columns()
            user = app_module.User(
                username=f'analytics_batches_{cls.suffix}',
                password=app_module.generate_password_hash('test-password'),
                role='staff',
                is_active=True,
                reports_admin_access=True,
            )
            app_module.db.session.add(user)
            app_module.db.session.flush()
            cls.user_id = user.id
            cls.engineer_ids = []
            for code, branch in (('M1', 'Manila'), ('M2', 'Manila'), ('C1', 'Cebu')):
                engineer = app_module.Engineer(
                    employee_id=f'AB-{code}-{cls.suffix}',
                    name=f'Batch {code} {cls.suffix}',
                    initials=code,
                    branch=branch,
                )
                app_module.db.session.add(engineer)
                app_module.db.session.flush()
                cls.engineer_ids.append(engineer.id)
            client = app_module.Client(name=f'Batch Client {cls.suffix}', address='Batch address')
            app_module.db.session.add(client)
            app_module.db.session.flush()
            cls.client_id = client.id
            cls.client_name = client.name
            app_module.db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            for model, ids in (
                (app_module.Client, [cls.client_id]),
                (app_module.Engineer, cls.engineer_ids),
                (app_module.User, [cls.user_id]),
            ):
                for record_id in ids:
                    record = app_module.db.session.get(model, record_id)
                    if record:
                        app_module.db.session.delete(record)
            app_module.db.session.commit()
            app_module.db.session.remove()

    def setUp(self):
        self.shift_ids = []

    def tearDown(self):
        with self.app.app_context():
            app_module.db.session.query(app_module.ShiftEngineer).filter(
                app_module.ShiftEngineer.shift_id.in_(self.shift_ids)
            ).delete(synchronize_session=False)
            app_module.db.session.query(app_module.Shift).filter(
                app_module.Shift.id.in_(self.shift_ids)
            ).delete(synchronize_session=False)
            app_module.db.session.commit()

    def client(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.user_id)
            session['_fresh'] = True
        return client

    def add_shift(self, day, title, engineers, status='In Progress', client=True, schedule_type='service'):
        with self.app.app_context():
            shift = app_module.Shift(
                title=title,
                start_time=datetime.combine(day, datetime.min.time()).replace(hour=8),
                end_time=datetime.combine(day, datetime.min.time()).replace(hour=17),
                engineer_id=self.engineer_ids[engineers[0]],
                client_id=self.client_id if client else None,
                status=status,
                schedule_type=schedule_type,
            )
            app_module.db.session.add(shift)
            app_module.db.session.flush()
            app_module.db.session.add_all([
                app_module.ShiftEngineer(shift_id=shift.id, engineer_id=self.engineer_ids[index])
                for index in engineers
            ])
            app_module.db.session.commit()
            self.shift_ids.append(shift.id)
            return shift.id

    def summary(self, start, end, branch='ALL'):
        response = self.client().get(
            f'/get_analytics_summary?start_date={start.isoformat()}&end_date={end.isoformat()}&branch={branch}'
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    @staticmethod
    def row(rows, label):
        return next((row for row in rows if row['label'] == label), {'count': 0, 'previous': 0})

    # --- Batch 1: correct numbers -------------------------------------------------------

    def test_travel_blocks_count_as_travel_on_the_page_and_in_the_csv(self):
        day = datetime(2026, 9, 14).date()
        before = self.summary(day, day)
        title = f'TRAVEL - Manila → Cebu - Meeting {self.suffix}'
        self.add_shift(day, title, [0], status='Approved', client=False, schedule_type='travel')
        after = self.summary(day, day)
        self.assertEqual(self.row(after['categories'], 'Travel')['count'] - self.row(before['categories'], 'Travel')['count'], 1)
        self.assertEqual(self.row(after['categories'], 'Training')['count'], self.row(before['categories'], 'Training')['count'])

        csv_text = self.client().get(f'/export_analytics_summary?start_date={day}&end_date={day}').get_data(as_text=True)
        line = next(line for line in csv_text.splitlines() if self.suffix in line)
        self.assertIn(',Travel,', line)

    def test_active_counts_open_service_work_only(self):
        day = datetime(2026, 9, 15).date()
        before = self.summary(day, day)['stock']['active']['value']
        self.add_shift(day, f'TRAVEL - Manila → Davao {self.suffix}', [0], status='Approved', client=False, schedule_type='travel')
        self.add_shift(day, 'Vacation Leave', [0], client=False)
        self.assertEqual(self.summary(day, day)['stock']['active']['value'], before)
        self.add_shift(day, f'Repair {self.suffix}', [0])
        self.assertEqual(self.summary(day, day)['stock']['active']['value'], before + 1)

    def test_branch_previous_period_counts_each_engineer_like_the_current_one(self):
        previous_day, day = datetime(2026, 9, 16).date(), datetime(2026, 9, 17).date()
        before = self.row(self.summary(day, day)['branches'], 'Manila')
        self.add_shift(previous_day, f'Install {self.suffix}', [0, 1])
        self.add_shift(day, f'Install day 2 {self.suffix}', [0, 1])
        after = self.row(self.summary(day, day)['branches'], 'Manila')
        self.assertEqual(after['count'] - before['count'], 2)
        self.assertEqual(after['previous'] - before['previous'], 2)

    def test_no_comparison_when_the_previous_period_is_before_system_start(self):
        start = app_module.ANALYTICS_SYSTEM_START_DATE
        payload = self.summary(start, start + timedelta(days=30))
        self.assertFalse(payload['comparison_available'])
        self.assertIsNone(payload['previous_range'])
        self.assertIsNone(payload['flow']['total']['previous'])
        self.assertEqual(payload['trend']['previous'], [])
        self.assertTrue(all(row['previous'] is None for row in payload['categories'] + payload['branches']))

        later = self.summary(datetime(2026, 9, 1).date(), datetime(2026, 9, 30).date())
        self.assertTrue(later['comparison_available'])
        self.assertIsNotNone(later['flow']['total']['previous'])

    def test_ranges_over_two_years_are_refused_on_both_routes(self):
        query = 'start_date=2024-01-01&end_date=2026-01-05'
        summary = self.client().get(f'/get_analytics_summary?{query}')
        self.assertEqual(summary.status_code, 400)
        self.assertEqual(summary.get_json()['message'], 'Choose a range of up to 2 years.')
        self.assertEqual(self.client().get(f'/export_analytics_summary?{query}').status_code, 400)
        self.assertEqual(self.client().get('/get_analytics_summary?start_date=2024-06-01&end_date=2026-05-31').status_code, 200)

    def test_csv_lists_every_engineer_on_a_schedule(self):
        day = datetime(2026, 9, 18).date()
        self.add_shift(day, f'Two engineers {self.suffix}', [0, 2])
        csv_text = self.client().get(f'/export_analytics_summary?start_date={day}&end_date={day}').get_data(as_text=True)
        line = next(line for line in csv_text.splitlines() if self.suffix in line)
        self.assertIn(f'Batch M1 {self.suffix}', line)
        self.assertIn(f'Batch C1 {self.suffix}', line)
        self.assertIn('"Cebu, Manila"', line)

    def test_engineer_map_has_no_primary_engineer_fallback(self):
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        body = source.split('def analytics_engineer_map(', 1)[1].split('\ndef ', 1)[0]
        self.assertNotIn('primary_ids', body)
        self.assertNotIn('visible_ids is None', source.split('def analytics_scope_query(', 1)[1].split('\ndef ', 1)[0])

    # --- Batch 2: more data -------------------------------------------------------------

    def test_overdue_client_work_is_bucketed_by_age(self):
        today = app_module.get_manila_time().date()
        start, end = today - timedelta(days=60), today
        before = {row['label']: row['count'] for row in self.summary(start, end)['stock']['overdue_client_work']['buckets']}
        for days in (3, 10, 40):
            self.add_shift(today - timedelta(days=days), f'Overdue {days} {self.suffix}', [0])
        self.add_shift(today - timedelta(days=5), f'Done {self.suffix}', [0], status='Completed')
        overdue = self.summary(start, end)['stock']['overdue_client_work']
        after = {row['label']: row['count'] for row in overdue['buckets']}
        self.assertEqual([after[label] - before[label] for label in ('1–7 days', '8–30 days', 'Over 30 days')], [1, 1, 1])
        self.assertEqual(overdue['value'], sum(after.values()))
        self.assertNotIn('previous', overdue)

    def test_top_clients_count_site_visits_with_previous_period(self):
        previous_day, day = datetime(2026, 9, 21).date(), datetime(2026, 9, 22).date()
        self.add_shift(previous_day, f'Visit A {self.suffix}', [0])
        self.add_shift(day, f'Visit B {self.suffix}', [0])
        self.add_shift(day, f'Visit C {self.suffix}', [1])
        payload = self.summary(day, day)
        row = self.row(payload['top_clients'], self.client_name)
        self.assertEqual((row['count'], row['previous']), (2, 1))
        self.assertLessEqual(len(payload['top_clients']), 8)

    def test_field_days_count_one_per_date(self):
        start, end = datetime(2026, 9, 23).date(), datetime(2026, 9, 24).date()
        self.add_shift(start, f'Morning {self.suffix}', [2])
        self.add_shift(start, f'Afternoon {self.suffix}', [2])
        self.add_shift(end, f'Next day {self.suffix}', [2])
        self.add_shift(end, 'Vacation Leave', [2], client=False)
        engineer = next(row for row in self.summary(start, end)['engineers'] if row['name'] == f'Batch C1 {self.suffix}')
        self.assertEqual(engineer['field_days'], 2)
        self.assertEqual(engineer['count'], 4)
        # Active follows the card: open service work, so the leave day is not active.
        self.assertEqual(engineer['active'], 3)

    def test_page_shows_the_new_numbers(self):
        for token in ('id="schedule-overdue"', 'id="schedule-overdue-buckets"', 'id="client-chart"',
                      'id="client-table-body"', 'Field days', 'id="workload-toggle"', 'aria-expanded="false"'):
            self.assertIn(token, self.template)
        self.assertNotIn('schedule-active', self.template)
        self.assertNotIn('schedule-active', self.js)
        self.assertIn('engineer.field_days', self.js)
        self.assertIn('data.top_clients', self.js)
        self.assertIn("classList.toggle('dashboard-metric-alert'", self.js)

    # --- Batch 3: shared design system --------------------------------------------------

    def test_page_uses_the_shared_header_and_stat_cards(self):
        self.assertIn('class="dash-page-header"', self.template)
        self.assertIn('class="dash-page-h1">Analytics</h1>', self.template)
        self.assertIn('class="dash-page-sub"', self.template)
        self.assertGreaterEqual(self.template.count('class="dash-stat"'), 8)
        for gone in ('analytics-eyebrow', 'Management Intelligence', 'analytics-metric"', 'fa-chart-line', '>Flow<',
                     'misleading period-over-period'):
            self.assertNotIn(gone, self.template)

    def test_arrows_are_ink_muted_and_weights_stay_at_or_below_600(self):
        self.assertNotIn('#198754', self.css)
        self.assertNotRegex(self.css, r'is-up\s*\{\s*(color|fill):\s*#dc3545')
        self.assertIsNone(re.search(r'font-weight:\s*(7|8|9)\d\d', self.css))
        self.assertFalse('#94a3b8' in self.css, 'the fixed previous-bar grey was 2.45:1')
        self.assertNotRegex(self.css, r'border-(left|top):\s*\d+px solid var\(--app-primary\)')

    # --- Batch 4: phone and layout ------------------------------------------------------

    def test_phone_filters_fold_and_presets_show_which_is_active(self):
        self.assertIn('id="analytics-filter-toggle"', self.template)
        self.assertIn('aria-controls="analytics-filter-form"', self.template)
        self.assertEqual(self.template.count('class="dash-segment-btn" data-analytics-preset='), 3)
        self.assertIn("button.setAttribute('aria-pressed'", self.js)
        self.assertIn('.analytics-filter-grid.is-open { display: grid; }', self.css)
        self.assertRegex(self.css, r'\.analytics-tabs \{ overflow-x: auto;')
        self.assertIn('white-space: nowrap', self.css.split('.analytics-tab-btn {', 1)[1].split('}', 1)[0])

    def test_rows_empty_in_both_periods_are_not_drawn(self):
        self.assertIn('function nonZeroRows(', self.js)
        self.assertIn('nonZeroRows(allRows)', self.js)
        self.assertIn('nonZeroRows(rows)', self.js.split('function renderBars(', 1)[1].split('\n    }', 1)[0])


if __name__ == '__main__':
    unittest.main()
