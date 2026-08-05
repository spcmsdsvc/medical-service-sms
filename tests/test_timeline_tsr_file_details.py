"""Regression coverage for TSR attachment discovery from schedule details."""

import json
import os
import pathlib
import tempfile
import unittest
import uuid
from datetime import datetime, time

ROOT = pathlib.Path(__file__).resolve().parents[1]

_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / 'medical_service_timeline_file_details_tests.db'
os.environ.setdefault('MEDICAL_SERVICE_TEST_DB', str(_TEST_DB_PATH))

import app as app_module  # noqa: E402
from tests.sw_cache_version import assert_cache_version_at_least  # noqa: E402


class TimelineTsrFileDetailsSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.timeline_source = (ROOT / 'templates' / 'timeline.html').read_text(encoding='utf-8')
        cls.releases = (ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8')

    def test_the_mobile_files_action_no_longer_opens_the_edit_modal(self):
        """The workaround this feature exists to remove must not come back.

        This stays a source check on purpose: the behaviour lives in inline template
        JavaScript and there is no JS test runner in this project. It asserts an
        outcome -- that function does not reach for the Edit modal -- rather than
        pinning how the replacement is written. Everything else that was asserted as
        a source string here is now checked against real responses in the API tests
        below, because a string match only tells you the old text is gone.
        """
        files_action = self.timeline_source.split(
            'async function openMobileFullCalendarLiteFilesAction'
        )[1].split('function findMobileFullCalendarLiteShift')[0]
        self.assertNotIn('openEditModal', files_action)
        self.assertNotIn('scrollIntoView', files_action)

    def test_attachment_links_meet_the_tap_target_floor(self):
        """These links render in the mobile detail sheet, so the 44px bar applies.

        Shipped at 2.2rem (~35px) while every other tap target in this template uses
        2.75rem.
        """
        block = self.timeline_source.split('.timeline-tsr-attachment-link,', 1)[1].split('}', 1)[0]
        self.assertIn('min-height: 2.75rem;', block)

    def test_release_and_cache_metadata(self):
        self.assertIn('2026-08-05-schedule-card-tsr-preview-links', self.releases)
        assert_cache_version_at_least(self, 68, self.app_source)


class TimelineTsrFileDetailsApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.suffix = uuid.uuid4().hex[:10]

        with cls.app.app_context():
            app_module.db.create_all()

            cls.user = app_module.User(
                username=f'timeline_files_{cls.suffix}',
                password=app_module.generate_password_hash('TimelineFiles123'),
                role='engineer',
                is_active=True,
            )
            app_module.db.session.add(cls.user)
            app_module.db.session.commit()

            cls.engineer = app_module.Engineer(
                user_id=cls.user.id,
                employee_id=f'TL-F-{cls.suffix}',
                name='Timeline File Engineer',
                initials='TFE',
                branch='Manila',
                phone='09170000000',
                email='timeline-files@example.test',
            )
            cls.client_record = app_module.Client(
                name='Timeline TSR File Client',
                address='Timeline file test address',
            )
            app_module.db.session.add_all([cls.engineer, cls.client_record])
            app_module.db.session.commit()

            today = app_module.get_manila_today()
            cls.shift = app_module.Shift(
                title='Timeline TSR file detail test',
                start_time=datetime.combine(today, time(8, 0)),
                end_time=datetime.combine(today, time(17, 0)),
                engineer_id=cls.engineer.id,
                client_id=cls.client_record.id,
                status='Completed',
            )
            app_module.db.session.add(cls.shift)
            app_module.db.session.commit()

            app_module.db.session.add(app_module.ShiftEngineer(
                shift_id=cls.shift.id,
                engineer_id=cls.engineer.id,
            ))
            cls.manual_file = app_module.ShiftFile(
                shift_id=cls.shift.id,
                filename='supporting-photo.png',
                original_filename='Supporting Photo.png',
            )
            cls.generated_file = app_module.ShiftFile(
                shift_id=cls.shift.id,
                filename='generated-tsr.pdf',
                original_filename='Generated TSR.pdf',
            )
            app_module.db.session.add_all([cls.manual_file, cls.generated_file])
            app_module.db.session.commit()

            cls.submission = app_module.OnlineTsrSubmission(
                shift_id=cls.shift.id,
                tsr_number='20260805-01-TFE',
                submitted_by_user_id=cls.user.id,
                submitted_by_name='Timeline File Engineer',
                status='saved',
                payload_json=json.dumps({'_attached_file_id': cls.generated_file.id}),
            )
            app_module.db.session.add(cls.submission)
            app_module.db.session.commit()
            cls.generated_file.online_tsr_submission_id = cls.submission.id
            app_module.db.session.commit()

            # An HR schedule viewer: no Engineer profile, so is_hr_schedule_only_user()
            # is true and the timeline feed must be redacted for them.
            app_module.ensure_user_hr_schedule_view_column()
            cls.hr_user = app_module.User(
                username=f'timeline_files_hr_{cls.suffix}',
                password=app_module.generate_password_hash('TimelineFilesHR123'),
                role='staff',
                is_active=True,
                hr_schedule_view=True,
            )
            app_module.db.session.add(cls.hr_user)
            app_module.db.session.commit()

            cls.user_id = cls.user.id
            cls.hr_user_id = cls.hr_user.id
            cls.engineer_id = cls.engineer.id
            cls.client_id = cls.client_record.id
            cls.shift_id = cls.shift.id
            cls.manual_file_id = cls.manual_file.id
            cls.generated_file_id = cls.generated_file.id
            cls.submission_id = cls.submission.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            shift = app_module.db.session.get(app_module.Shift, cls.shift_id)
            if shift:
                app_module.ShiftEngineer.query.filter_by(shift_id=cls.shift_id).delete()
                app_module.ShiftFile.query.filter_by(shift_id=cls.shift_id).delete()
                app_module.db.session.delete(shift)
            submission = app_module.db.session.get(app_module.OnlineTsrSubmission, cls.submission_id)
            if submission:
                app_module.db.session.delete(submission)
            engineer = app_module.db.session.get(app_module.Engineer, cls.engineer_id)
            if engineer:
                app_module.db.session.delete(engineer)
            client = app_module.db.session.get(app_module.Client, cls.client_id)
            if client:
                app_module.db.session.delete(client)
            for user_id in (cls.user_id, cls.hr_user_id):
                user = app_module.db.session.get(app_module.User, user_id)
                if user:
                    app_module.db.session.delete(user)
            app_module.db.session.commit()

    @classmethod
    def _client_for_user(cls, user_id=None):
        client = cls.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id or cls.user_id)
            session['_fresh'] = True
        return client

    def _timeline_row_for(self, user_id):
        response = self._client_for_user(user_id).get('/get_timeline_data?offset=0&branch=ALL')
        self.assertEqual(response.status_code, 200)
        return self._find_shift(response.get_json(), self.shift_id)

    @staticmethod
    def _find_shift(payload, shift_id):
        for day_map in payload.get('schedule', {}).values():
            for rows in day_map.values():
                for row in rows:
                    if row.get('id') == shift_id:
                        return row
        raise AssertionError(f'shift {shift_id} was not present in timeline payload')

    def test_timeline_and_details_endpoints_distinguish_generated_tsr(self):
        client = self._client_for_user()

        timeline_response = client.get('/get_timeline_data?offset=0&branch=ALL')
        self.assertEqual(timeline_response.status_code, 200)
        timeline_row = self._find_shift(timeline_response.get_json(), self.shift_id)
        details_by_id = {item['id']: item for item in timeline_row['file_details']}

        self.assertTrue(details_by_id[self.generated_file_id]['is_tsr'])
        self.assertFalse(details_by_id[self.manual_file_id]['is_tsr'])
        self.assertTrue(details_by_id[self.generated_file_id]['download_url'])
        self.assertEqual(details_by_id[self.manual_file_id]['download_url'], '')

        details_response = client.get(f'/get_shift_details/{self.shift_id}')
        self.assertEqual(details_response.status_code, 200)
        details = {item['id']: item for item in details_response.get_json()['shift']['file_details']}
        self.assertTrue(details[self.generated_file_id]['is_tsr'])
        self.assertFalse(details[self.manual_file_id]['is_tsr'])

    def test_both_endpoints_return_an_identical_file_detail_shape(self):
        """The two feeds are served by one serializer; this is what proves it stayed one.

        They were duplicated blocks before, and the whole risk of duplicated blocks is
        that someone edits one. A source check that `timeline_file_detail_payload` is
        called twice cannot catch a hand-edited copy; comparing real responses can.
        """
        client = self._client_for_user()

        timeline_row = self._find_shift(
            client.get('/get_timeline_data?offset=0&branch=ALL').get_json(), self.shift_id
        )
        details_shift = client.get(f'/get_shift_details/{self.shift_id}').get_json()['shift']

        timeline_files = {item['id']: item for item in timeline_row['file_details']}
        details_files = {item['id']: item for item in details_shift['file_details']}

        self.assertEqual(set(timeline_files), set(details_files))
        for file_id, timeline_entry in timeline_files.items():
            self.assertEqual(timeline_entry, details_files[file_id])
        # Positive control: the comparison is over populated entries, not two empties.
        self.assertIn(self.generated_file_id, timeline_files)
        self.assertIn(self.manual_file_id, timeline_files)

    def test_hr_viewers_receive_no_attachment_data_at_all(self):
        """Behavioural replacement for a string match on "'file_details': [],".

        That assertion passed as long as the line existed somewhere in app.py; it could
        not tell you an HR session actually receives an empty list. The attachment block
        renders from file_details, so this emptiness is the whole protection.
        """
        hr_row = self._timeline_row_for(self.hr_user_id)
        self.assertEqual(hr_row['file_details'], [])
        self.assertEqual(hr_row['files'], [])
        self.assertNotIn('Generated TSR', json.dumps(hr_row))
        self.assertNotIn('Supporting Photo', json.dumps(hr_row))

        # Positive control: the same shift really does carry both files for a viewer
        # who is entitled to them, so the empties above are the redaction and not an
        # unattached fixture.
        engineer_row = self._timeline_row_for(self.user_id)
        self.assertEqual(len(engineer_row['file_details']), 2)


if __name__ == '__main__':
    unittest.main()
