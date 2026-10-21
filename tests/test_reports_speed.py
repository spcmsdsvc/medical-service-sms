"""Reports page speed: the archive and summary must not query once per file, shift or product.

Railway logged /get_tsr_archive at 1.3-7.9 s and /get_reports_summary at about 1 s. On a copy
of the live database they ran about 441 and 452 queries: the archive looked up each shift's
online TSR and each PDF's calibration conversion one at a time, and the summary loaded every
product's schedules for counts the page never showed.
"""

import json
import os
import pathlib
import tempfile
import threading
import unittest
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta

from sqlalchemy import event

TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_reports_speed_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB_PATH))
os.environ.setdefault("SECRET_KEY", "reports-speed-tests")

import app as app_module  # noqa: E402
from tests.schema_flags import reset_schema_flags  # noqa: E402


@contextmanager
def count_queries():
    counter = {'n': 0}
    thread_id = threading.get_ident()

    def before_cursor_execute(*_args):
        if threading.get_ident() == thread_id:
            counter['n'] += 1

    engine = app_module.db.engine
    event.listen(engine, 'before_cursor_execute', before_cursor_execute)
    try:
        yield counter
    finally:
        event.remove(engine, 'before_cursor_execute', before_cursor_execute)


class ReportsSpeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=True)

    def setUp(self):
        self.suffix = uuid.uuid4().hex[:8].upper()
        self.created = 0
        with self.app.app_context():
            app_module.db.create_all()
            admin = app_module.User(
                username=f"reports-speed-{self.suffix}", password="test",
                role="superadmin", is_active=True, reports_admin_access=True,
            )
            engineer = app_module.Engineer(
                employee_id=f"RS-{self.suffix}", name="Reports Speed Engineer", initials="RSE",
            )
            client = app_module.Client(name=f"Reports Speed Client {self.suffix}", address="Test")
            app_module.db.session.add_all([admin, engineer, client])
            app_module.db.session.commit()
            self.admin_id, self.engineer_id, self.client_id = admin.id, engineer.id, client.id
        self.today = app_module.get_manila_time().replace(tzinfo=None)

    def tearDown(self):
        with self.app.app_context():
            app_module.db.session.remove()
            app_module.db.drop_all()
            reset_schema_flags(app_module)

    def admin_client(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(self.admin_id)
            session["_fresh"] = True
        return client

    def add_serviced_schedules(self, count):
        """Each schedule: a product, a TSR PDF, an online TSR with an older revision."""
        with self.app.app_context():
            for _ in range(count):
                self.created += 1
                index = self.created
                product = app_module.Product(
                    serial_number=f"RS-{self.suffix}-{index}", name=f"Speed Product {index}",
                    client_id=self.client_id,
                )
                start = self.today - timedelta(days=index)
                shift = app_module.Shift(
                    title=f"Speed visit {index}", start_time=start, end_time=start + timedelta(hours=2),
                    engineer_id=self.engineer_id, client_id=self.client_id,
                    product_id=product.serial_number, equipment_source="product", status="Completed",
                )
                app_module.db.session.add_all([product, shift])
                app_module.db.session.flush()
                tsr_file = app_module.ShiftFile(
                    shift_id=shift.id, filename=f"TSR_SPEED_{self.suffix}_{index}.pdf",
                    original_filename=f"TSR_SPEED_{self.suffix}_{index}.pdf",
                )
                app_module.db.session.add_all([
                    tsr_file,
                    app_module.ShiftEngineer(shift_id=shift.id, engineer_id=self.engineer_id),
                ])
                app_module.db.session.flush()
                for revision, latest in ((1, False), (2, True)):
                    submission = app_module.OnlineTsrSubmission(
                        shift_id=shift.id, tsr_number=f"RS-{index}-{revision}",
                        payload_json=json.dumps({'_attached_file_id': tsr_file.id}),
                        revision_no=revision, is_latest=latest,
                        created_at=start + timedelta(minutes=revision),
                    )
                    app_module.db.session.add(submission)
                    app_module.db.session.flush()
                tsr_file.online_tsr_submission_id = submission.id
            app_module.db.session.commit()

    def archive_query_count(self):
        client = self.admin_client()
        client.get('/api/preferences/appearance')
        with self.app.app_context(), count_queries() as counter:
            response = client.get('/get_tsr_archive?branch=ALL&q=&scope=all&page=1&per_page=10')
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return counter['n'], response.get_json()

    def summary_query_count(self):
        client = self.admin_client()
        client.get('/api/preferences/appearance')
        start = (self.today - timedelta(days=60)).date().isoformat()
        end = self.today.date().isoformat()
        with self.app.app_context(), count_queries() as counter:
            response = client.get(f'/get_reports_summary?start_date={start}&end_date={end}&branch=ALL')
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return counter['n'], response.get_json()

    def test_archive_queries_do_not_grow_with_files(self):
        self.add_serviced_schedules(3)
        small, _ = self.archive_query_count()
        self.add_serviced_schedules(9)
        large, data = self.archive_query_count()
        self.assertEqual(data['total'], 12)
        self.assertLessEqual(large - small, 2, f'{small} queries for 3 files, {large} for 12')
        self.assertIn('RS-12-2', {row['tsr_number'] for row in data['rows']})

    def test_batched_latest_submission_matches_single_lookup(self):
        self.add_serviced_schedules(4)
        with self.app.app_context():
            shifts = app_module.Shift.query.filter_by(client_id=self.client_id).all()
            # One shift whose submissions are all superseded falls back to the newest one.
            app_module.OnlineTsrSubmission.query.filter_by(shift_id=shifts[0].id).update({'is_latest': False})
            app_module.db.session.commit()
            batched = app_module.tsr_archive_latest_submissions({shift.id for shift in shifts})
            for shift in shifts:
                single = app_module.get_latest_online_tsr_submission_for_shift(shift.id)
                self.assertEqual(batched[shift.id].id, single.id)

    def test_summary_queries_do_not_grow_with_products(self):
        self.add_serviced_schedules(3)
        small, _ = self.summary_query_count()
        with self.app.app_context():
            for index in range(20):
                app_module.db.session.add(app_module.Product(
                    serial_number=f"RS-IDLE-{self.suffix}-{index}", name="Idle product",
                    client_id=self.client_id,
                ))
            app_module.db.session.commit()
        large, data = self.summary_query_count()
        self.assertLessEqual(large - small, 1, f'{small} queries before 20 idle products, {large} after')
        self.assertEqual(data['tsr']['service_schedules'], 3)
        self.assertEqual(data['tsr']['attached'], 3)
        self.assertEqual(data['product']['total'], 23)
        self.assertEqual(len(data['product']['high_maintenance']), 3)
        for key in ('missing', 'missing_rows'):
            self.assertIn(key, data['tsr'])
        for key in ('sent_count', 'recent'):
            self.assertIn(key, data['email'])


class ReportsTemplateDesignTests(unittest.TestCase):
    """Design scan 2026-10-21: dark-mode values at 1.02:1, unlabelled inputs, green Export CSV."""

    @classmethod
    def setUpClass(cls):
        root = pathlib.Path(__file__).resolve().parents[1]
        cls.source = (root / 'templates' / 'reports.html').read_text(encoding='utf-8')
        cls.style = cls.source.split('<style>', 1)[1].split('</style>', 1)[0]
        cls.layout = (root / 'templates' / 'layout.html').read_text(encoding='utf-8')

    def test_colours_come_from_theme_variables(self):
        import re
        hexes = set(re.findall(r'#[0-9a-fA-F]{3,8}\b', self.style))
        # Only the semantic alert pair for a missing-TSR count above zero (DESIGN.md).
        self.assertEqual(hexes, {'#a1121f', '#fecdd3'})
        self.assertNotRegex(self.style, r'font-weight:\s*(7|8|9)00')

    def test_inputs_have_linked_labels(self):
        for control in ('reports-start-date', 'reports-end-date', 'reports-branch', 'reports-search', 'reports-scope'):
            self.assertIn(f'for="{control}"', self.source)

    def test_page_header_buttons_and_dead_preview_modal(self):
        self.assertIn('<h1 class="dash-page-h1">Reports</h1>', self.source)
        self.assertNotIn('btn-success', self.source)
        self.assertNotIn('tsrPreviewModal', self.source)
        self.assertNotIn('openTSRPreview', self.source)
        self.assertIn('btn btn-sm btn-primary archive-download-btn', self.source)
        self.assertIn("nav_link('/reports_page', 'fa-file-lines', 'Reports')", self.layout)

    def test_tsr_files_come_first_and_missing_tsrs_are_collapsed(self):
        # Owner, 2026-10-21: TSR files first; Missing TSRs only as a collapsible section.
        self.assertLess(self.source.index('id="archive-title"'), self.source.index('id="missing-tsr-title"'))
        self.assertIn('<details class="card reports-card reports-collapse mb-3" id="reports-missing">', self.source)
        self.assertNotIn('id="reports-missing" open', self.source)
        # The branch filter drives both lists, so it stays visible beside the archive search.
        self.assertLess(self.source.index('for="reports-branch"'), self.source.index('id="reports-missing"'))


if __name__ == '__main__':
    unittest.main()
