"""Behavioral coverage for the standalone Reimbursement Tracker register."""

import json
import os
import pathlib
import re
import tempfile
import unittest
import uuid
from datetime import date
from io import BytesIO

os.environ.setdefault(
    'MEDICAL_SERVICE_TEST_DB',
    str(pathlib.Path(tempfile.gettempdir()) / 'medical_service_reimbursement_tracker_tests.db'),
)

import app as app_module  # noqa: E402
from openpyxl import load_workbook  # noqa: E402


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ReimbursementTrackerWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.suffix = uuid.uuid4().hex[:8]
        cls.created_user_ids = []
        cls.created_engineer_ids = []

        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_user_admin_capability_columns()
            app_module.ensure_reimbursement_tracker_schema()

            cls.superadmin = app_module.User.query.filter_by(username='jonamar').first()
            if not cls.superadmin:
                cls.superadmin = app_module.User(
                    username='jonamar',
                    password=app_module.generate_password_hash('test-password'),
                    role='superadmin',
                    is_active=True,
                )
                app_module.db.session.add(cls.superadmin)
                app_module.db.session.flush()
                cls.created_user_ids.append(cls.superadmin.id)
            cls.superadmin.reimbursement_tracker_access = False

            def create_user(username, **flags):
                user = app_module.User(
                    username=f'{username}_{cls.suffix}',
                    password=app_module.generate_password_hash('test-password'),
                    role='staff',
                    is_active=True,
                    **flags,
                )
                app_module.db.session.add(user)
                app_module.db.session.flush()
                cls.created_user_ids.append(user.id)
                return user

            cls.tracker_user = create_user('tracker_manager', reimbursement_tracker_access=True)
            cls.personnel_user = create_user('tracker_personnel', personnel_admin_access=True)
            cls.plain_user = create_user('tracker_plain')

            def create_engineer(name, initials, branch):
                engineer = app_module.Engineer(
                    employee_id=f'RT-{cls.suffix}-{len(cls.created_engineer_ids) + 1}',
                    name=name,
                    initials=initials,
                    branch=branch,
                )
                app_module.db.session.add(engineer)
                app_module.db.session.flush()
                cls.created_engineer_ids.append(engineer.id)
                return engineer

            cls.jfl_engineer = create_engineer('Jim Frederick Lim', 'JFL', 'Manila')
            cls.raj_engineer = create_engineer('Rodito Aretano Jr.', 'RAJ', 'Cebu')
            cls.jp_one = create_engineer('Jonamar Paunil', 'JP', 'Manila')
            cls.jp_two = create_engineer('Jocel Prudente', 'JP', 'Davao')
            app_module.db.session.commit()

            cls.superadmin_id = cls.superadmin.id
            cls.tracker_user_id = cls.tracker_user.id
            cls.personnel_user_id = cls.personnel_user.id
            cls.plain_user_id = cls.plain_user.id
            cls.jfl_id = cls.jfl_engineer.id
            cls.raj_id = cls.raj_engineer.id
            cls.jp_one_id = cls.jp_one.id
            cls.jp_two_id = cls.jp_two.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            for entry in app_module.ReimbursementTrackerEntry.query.all():
                app_module.db.session.delete(entry)
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

    @classmethod
    def _payload(cls, engineer_id=None, reference='BATCH-031', **overrides):
        payload = {
            'reference': reference,
            'submission_date': '2026-08-11',
            'engineer_id': engineer_id or cls.jfl_id,
            'office': 'Manila',
            'description': 'Tracker test row',
            'paid_in_full': False,
            'paid_transfer_date': '',
            'remarks': '',
        }
        for field, _label in app_module.REIMBURSEMENT_TRACKER_EXPENSE_FIELDS:
            payload[field] = '0'
        payload.update(overrides)
        return payload

    def _add(self, client, **overrides):
        response = client.post('/add_reimbursement_tracker_entry', json=self._payload(**overrides))
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()['entry']

    def test_authorization_and_escalation_boundary(self):
        personnel = self._client_for(self.personnel_user_id)
        self.assertEqual(personnel.get('/reimbursement_tracker').status_code, 302)
        self.assertEqual(personnel.get('/get_reimbursement_tracker_entries').status_code, 403)
        self.assertEqual(personnel.get('/export_reimbursement_tracker').status_code, 403)
        self.assertEqual(
            personnel.post('/add_reimbursement_tracker_entry', json=self._payload()).status_code,
            403,
        )
        self.assertEqual(
            personnel.put('/update_reimbursement_tracker_entry/999999', json={}).status_code,
            403,
        )
        self.assertEqual(personnel.delete('/delete_reimbursement_tracker_entry/999999').status_code, 403)
        self.assertEqual(self._client_for(self.plain_user_id).get('/reimbursement_tracker').status_code, 302)

        superadmin = self._client_for(self.superadmin_id)
        created = personnel.post('/add_engineer', json={
            'name': f'Unauthorized Tracker Grant {self.suffix}',
            'employee_id': f'RT-ESC-{self.suffix}',
            'initials': 'RTE',
            'reimbursement_tracker_access': True,
        })
        self.assertEqual(created.status_code, 403)

        self.assertEqual(superadmin.get('/reimbursement_tracker').status_code, 200)
        self.assertEqual(superadmin.get('/get_reimbursement_tracker_entries').status_code, 200)
        self.assertEqual(superadmin.get('/export_reimbursement_tracker').status_code, 200)

        granted = superadmin.post('/settings/update-approval-user', json={
            'user_id': self.plain_user_id,
            'reimbursement_tracker_access': True,
            'is_active': True,
        })
        self.assertEqual(granted.status_code, 200, granted.get_data(as_text=True))
        self.assertTrue(granted.get_json()['user']['reimbursement_tracker_access'])
        with self.app.app_context():
            plain = app_module.db.session.get(app_module.User, self.plain_user_id)
            self.assertTrue(plain.reimbursement_tracker_access)
            plain.reimbursement_tracker_access = False
            app_module.db.session.commit()

    def test_page_and_endpoints_flip_together(self):
        owner = self._client_for(self.tracker_user_id)
        row = self._add(owner)
        with self.app.app_context():
            user = app_module.db.session.get(app_module.User, self.tracker_user_id)
            user.reimbursement_tracker_access = False
            app_module.db.session.commit()

        denied_client = self._client_for(self.tracker_user_id)
        self.assertEqual(denied_client.get('/reimbursement_tracker').status_code, 302)
        self.assertEqual(denied_client.get('/get_reimbursement_tracker_entries').status_code, 403)
        self.assertEqual(denied_client.get('/export_reimbursement_tracker').status_code, 403)
        self.assertEqual(denied_client.post('/add_reimbursement_tracker_entry', json=self._payload()).status_code, 403)
        self.assertEqual(denied_client.put(f"/update_reimbursement_tracker_entry/{row['id']}", json={}).status_code, 403)
        self.assertEqual(denied_client.delete(f"/delete_reimbursement_tracker_entry/{row['id']}").status_code, 403)

        with self.app.app_context():
            user = app_module.db.session.get(app_module.User, self.tracker_user_id)
            user.reimbursement_tracker_access = True
            app_module.db.session.commit()
        self.assertEqual(owner.get('/reimbursement_tracker').status_code, 200)
        self.assertEqual(owner.get('/get_reimbursement_tracker_entries').status_code, 200)

    def test_settings_reports_stored_grant_and_unrelated_save_does_not_grant(self):
        with self.app.app_context():
            superadmin = app_module.db.session.get(app_module.User, self.superadmin_id)
            superadmin.reimbursement_tracker_access = False
            self.assertTrue(app_module.can_manage_reimbursement_tracker(superadmin))
            self.assertFalse(app_module.approval_user_to_dict(superadmin)['reimbursement_tracker_access'])

        client = self._client_for(self.superadmin_id)
        rendered = client.get('/settings/approval-routing-data')
        self.assertEqual(rendered.status_code, 200)
        row = next(item for item in rendered.get_json()['users'] if item['id'] == self.superadmin_id)
        self.assertFalse(row['reimbursement_tracker_access'])
        saved = client.post('/settings/update-approval-user', json={
            'user_id': self.superadmin_id,
            'is_active': True,
            'reimbursement_tracker_access': row['reimbursement_tracker_access'],
        })
        self.assertEqual(saved.status_code, 200, saved.get_data(as_text=True))
        with self.app.app_context():
            self.assertFalse(app_module.db.session.get(app_module.User, self.superadmin_id).reimbursement_tracker_access)

    def test_writes_are_refused_without_the_capability(self):
        owner = self._client_for(self.tracker_user_id)
        row = self._add(owner)
        with self.app.app_context():
            user = app_module.db.session.get(app_module.User, self.plain_user_id)
            user.reimbursement_tracker_access = False
            before = app_module.ReimbursementTrackerEntry.query.count()
            app_module.db.session.commit()

        intruder = self._client_for(self.plain_user_id)
        self.assertEqual(intruder.post('/add_reimbursement_tracker_entry', json=self._payload()).status_code, 403)
        self.assertEqual(intruder.put(f"/update_reimbursement_tracker_entry/{row['id']}", json={}).status_code, 403)
        self.assertEqual(intruder.delete(f"/delete_reimbursement_tracker_entry/{row['id']}").status_code, 403)
        with self.app.app_context():
            self.assertEqual(app_module.ReimbursementTrackerEntry.query.count(), before)

    def test_control_number_uses_engineer_initials_from_the_table(self):
        client = self._client_for(self.tracker_user_id)
        jfl = self._add(client, engineer_id=self.jfl_id, office='Manila')
        raj = self._add(client, engineer_id=self.raj_id, office='Cebu')
        self.assertTrue(jfl['control_number'].startswith('JFL-20260811-031'))
        self.assertTrue(raj['control_number'].startswith('RAJ-20260811-031'))
        self.assertNotIn('RB-', raj['control_number'])
        self.assertNotIn('#N/A', jfl['control_number'])

    def test_control_number_sequence_comes_from_batch_reference(self):
        client = self._client_for(self.tracker_user_id)
        first = self._add(client, engineer_id=self.jfl_id, office='Manila')
        second = self._add(client, engineer_id=self.jfl_id, office='Manila', description='Same batch again')
        third = self._add(client, engineer_id=self.raj_id, office='Cebu')
        self.assertTrue(first['control_number'].endswith('-031'))
        self.assertEqual(first['control_number'], second['control_number'])
        self.assertTrue(third['control_number'].endswith('-031'))

    def test_control_number_is_stable_after_engineer_initials_change(self):
        client = self._client_for(self.tracker_user_id)
        row = self._add(client, engineer_id=self.jfl_id, office='Manila')
        with self.app.app_context():
            engineer = app_module.db.session.get(app_module.Engineer, self.jfl_id)
            engineer.initials = 'CHANGED'
            app_module.db.session.commit()
        updated = client.put(f"/update_reimbursement_tracker_entry/{row['id']}", json={'remarks': 'kept stable'})
        self.assertEqual(updated.status_code, 200, updated.get_data(as_text=True))
        self.assertEqual(updated.get_json()['entry']['control_number'], row['control_number'])
        self.assertEqual(updated.get_json()['entry']['engineer_initials'], 'JFL')
        with self.app.app_context():
            engineer = app_module.db.session.get(app_module.Engineer, self.jfl_id)
            engineer.initials = 'JFL'
            app_module.db.session.commit()

    def test_total_is_recomputed_server_side(self):
        client = self._client_for(self.tracker_user_id)
        row = self._add(
            client,
            representation='1.25',
            per_diem='2.75',
            total='999999.99',
            paid_in_full=True,
            paid_transfer_date='2026-08-11',
        )
        self.assertEqual(row['total'], '4.00')
        self.assertEqual(row['paid_amount'], '4.00')
        updated = client.put(f"/update_reimbursement_tracker_entry/{row['id']}", json={'paid_in_full': False})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()['entry']['paid_amount'], '')

    def test_list_returns_offices_engineers_suggestion_and_duplicate_initial_warning(self):
        client = self._client_for(self.tracker_user_id)
        response = client.get('/get_reimbursement_tracker_entries')
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertIn('Manila', body['offices'])
        self.assertIn('Cebu', body['offices'])
        self.assertIn('JP', body['duplicate_initials'])
        self.assertTrue(body['suggested_reference'].startswith('BATCH-'))

    def test_export_reproduces_the_workbook_layout(self):
        client = self._client_for(self.tracker_user_id)
        self._add(client, reference='BATCH-031', engineer_id=self.jfl_id, office='Manila')
        self._add(client, reference='BATCH-031', engineer_id=self.raj_id, office='Cebu')
        response = client.get('/export_reimbursement_tracker?sort=submission_date&direction=asc')
        self.assertEqual(response.status_code, 200, response.status)
        workbook = load_workbook(BytesIO(response.data), data_only=False)
        worksheet = workbook['Sheet']
        self.assertEqual(worksheet['A1'].value, 'Current Input')
        self.assertEqual(worksheet['S1'].value, 'by: Diary Dizon')
        self.assertEqual(worksheet['V1'].value, 'Accounting')
        self.assertEqual(worksheet['A5'].value, 'Reimbursements')
        self.assertEqual(worksheet['A2'].value, 'Reference')
        self.assertEqual(worksheet['M2'].value, 'Trasnportation')
        self.assertEqual(worksheet['Q2'].value, 'Hotel Accomodation')
        self.assertEqual(worksheet['A6'].value, 'Reference')
        self.assertEqual(worksheet['M6'].value, 'Trasnportation')
        self.assertEqual(worksheet['Q6'].value, 'Hotel Accomodation')
        self.assertTrue(str(worksheet['G7'].value).startswith('=SUM(I7:R7)'))
        self.assertTrue(str(worksheet['W8'].value).startswith('=IF(V8=TRUE,G8'))
        self.assertTrue(str(worksheet['X8'].value).startswith('=IF(W8<>"",IF(X8="",TODAY(),X8)'))
        self.assertTrue(str(worksheet['Y8'].value).startswith('=IF(OR(V8=TRUE,W8<>""),W8-G8,0)'))
        self.assertTrue(str(worksheet['Z8'].value).startswith('=IF(Y8<0'))
        self.assertIsNone(worksheet['V7'].value)
        self.assertIsNone(worksheet['V8'].value)
        self.assertNotIn('TOTAL', '\n'.join(str(cell.value) for row in worksheet.iter_rows() for cell in row if cell.value))

    def test_export_enables_iterative_calculation_and_uses_nested_if(self):
        client = self._client_for(self.tracker_user_id)
        self._add(client, reference='BATCH-041')
        response = client.get('/export_reimbursement_tracker')
        workbook = load_workbook(BytesIO(response.data), data_only=False)
        self.assertTrue(workbook.calculation.iterate)
        self.assertGreaterEqual(workbook.calculation.iterateCount, 1)
        worksheet = workbook['Sheet']
        formulas = [
            cell.value for row in worksheet.iter_rows(min_row=7, max_col=26)
            for cell in row if isinstance(cell.value, str) and cell.value.startswith('=')
        ]
        self.assertTrue(formulas)
        self.assertTrue(str(worksheet['Z7'].value).startswith('=IF('))
        self.assertFalse(any('IFS(' in formula.upper() for formula in formulas))
        self.assertIn('OVER PAID', worksheet['Z7'].value)
        self.assertIn('EXCESS REIMBURSEMENT BY ACCTG.', worksheet['Z7'].value)

    def test_export_route_is_network_only_and_cache_version_is_bumped(self):
        client = self._client_for(self.tracker_user_id)
        worker = client.get('/service-worker.js')
        self.assertEqual(worker.status_code, 200)
        body = worker.get_data(as_text=True)
        self.assertIn("'/export_'", body)
        prefixes = body.split('const NETWORK_ONLY_DOWNLOAD_PREFIXES = [', 1)[1].split('];', 1)[0]
        self.assertTrue(any('/export_reimbursement_tracker'.startswith(prefix.strip().strip("',\"")) for prefix in prefixes.splitlines() if "'/" in prefix))
        version = body.split("const CACHE_VERSION = '", 1)[1].split("'", 1)[0]
        self.assertGreaterEqual(int(version.split('-v', 1)[1].split('-', 1)[0]), 86)

    def test_release_manifest_has_tracker_item(self):
        manifest = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))
        items = [item for release in manifest['releases'] for item in release.get('items', [])]
        self.assertTrue(any(item['item_key'] == '2026-08-11-reimbursement-tracker' for item in items))

    def test_tracker_item_sits_under_its_own_release_not_the_backup_one(self):
        """The item first shipped inside the release titled 'Backup Center Behaves Offline'.

        The coverage test passed because only the date is checked, but What's New would
        have shown a Reimbursement Tracker entry under a backup headline.
        """
        manifest = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))
        owning = [
            release for release in manifest['releases']
            if any(item['item_key'] == '2026-08-11-reimbursement-tracker'
                   for item in release.get('items', []))
        ]
        self.assertEqual(len(owning), 1, 'the tracker item must belong to exactly one release')
        release = owning[0]
        self.assertEqual(release['release_date'], '2026-08-11')
        self.assertIn('Reimbursement Tracker', release['title'])
        self.assertNotIn('Backup', release['title'])

    def test_every_theme_token_the_page_uses_is_actually_defined(self):
        """A misspelled custom property is invisible: it silently takes its fallback.

        The page shipped with `--app-raised-surface` -- the real token is
        `--app-surface-raised`, transposed -- so the mobile cards and the form's total
        box kept a light background in dark mode while their text went light, leaving
        white on white at 1.04:1 contrast. Asserting the class, not the one instance.
        """
        template = (ROOT / 'templates' / 'reimbursement_tracker.html').read_text(encoding='utf-8')
        themes = (ROOT / 'static' / 'css' / 'app-themes.css').read_text(encoding='utf-8')
        defined = set(re.findall(r'(--app-[a-z0-9-]+)\s*:', themes))
        self.assertIn('--app-surface-raised', defined, 'token source file looks wrong')

        used = set(re.findall(r'var\(\s*(--app-[a-z0-9-]+)', template))
        self.assertTrue(used, 'expected the page to use theme tokens')
        # Two tokens are deliberately undefined: their fallbacks are fixed colours that
        # are correct in both themes (a navy table header matching the Excel export, and
        # a blue focus ring). Everything else must resolve, or dark mode silently breaks.
        deliberate = {'--app-table-head', '--app-focus-ring'}
        undefined = sorted(used - defined - deliberate)
        self.assertEqual(undefined, [], f'undefined theme tokens fall back silently: {undefined}')

    def test_batch_suggestion_continues_from_the_workbook_not_from_one(self):
        """History was not imported, but Accounting reads the batch numbers as one sequence.

        The workbook's last batch was BATCH-031, so an empty register must suggest 032 --
        it suggested BATCH-001, which would have restarted a live numbering sequence.
        """
        client = self._client_for(self.tracker_user_id)
        with self.app.app_context():
            for entry in app_module.ReimbursementTrackerEntry.query.all():
                app_module.db.session.delete(entry)
            app_module.db.session.commit()

        empty = client.get('/get_reimbursement_tracker_entries').get_json()
        self.assertEqual(empty['entries'], [])
        self.assertEqual(empty['suggested_reference'], 'BATCH-032')

        # Once real data exists the stored rows drive it, and the floor stops mattering.
        self._add(client, reference='BATCH-040', engineer_id=self.jfl_id, office='Manila')
        self.assertEqual(
            client.get('/get_reimbursement_tracker_entries').get_json()['suggested_reference'],
            'BATCH-041',
        )

        # A row filed under an older batch must not drag the suggestion back below the floor.
        with self.app.app_context():
            for entry in app_module.ReimbursementTrackerEntry.query.all():
                app_module.db.session.delete(entry)
            app_module.db.session.commit()
        self._add(client, reference='BATCH-005', engineer_id=self.jfl_id, office='Manila')
        self.assertEqual(
            client.get('/get_reimbursement_tracker_entries').get_json()['suggested_reference'],
            'BATCH-032',
        )

    def test_the_form_actually_consumes_the_batch_suggestion(self):
        """The endpoint returning BATCH-032 is worth nothing if the form ignores it.

        It did: the Add form cleared the field and showed a hard-coded
        placeholder="BATCH-001", so the register still invited a restart at 001 while
        the API was already correct. The endpoint test passed the whole time -- assert
        the consumer, not just the producer.
        """
        template = (ROOT / 'templates' / 'reimbursement_tracker.html').read_text(encoding='utf-8')
        self.assertIn('data.suggested_reference', template,
                      'the page never reads the suggestion off the payload')
        self.assertRegex(
            template,
            r"byId\('rt-reference'\)\.value\s*=\s*state\.suggestedReference",
            'the Add form must prefill the reference from the suggestion',
        )
        self.assertNotRegex(
            template, r'placeholder="BATCH-001"',
            'a hard-coded BATCH-001 placeholder contradicts the continued sequence',
        )

    def test_modal_body_can_scroll_independently_of_the_form_wrapper(self):
        """The form sits between .modal-content and .modal-body, which broke Bootstrap.

        .modal-dialog-scrollable caps .modal-body only when it is a direct flex child of
        .modal-content. With the <form> in between, the body grew to full height, the
        content clipped it, and everything past Others/Misc -- including Save -- was
        unreachable with no way to scroll to it.
        """
        template = (ROOT / 'templates' / 'reimbursement_tracker.html').read_text(encoding='utf-8')
        self.assertIn('modal-dialog-scrollable', template)
        # The form must carry the flex column that .modal-content would otherwise provide.
        self.assertRegex(
            template,
            r'\.rt-modal-content\s*>\s*form\s*\{[^}]*display:\s*flex[^}]*flex-direction:\s*column',
        )
        self.assertRegex(
            template,
            r'\.rt-modal-content\s*>\s*form\s*>\s*\.modal-body\s*\{[^}]*overflow-y:\s*auto',
        )

    def test_control_date_format_constant_actually_drives_the_control_number(self):
        """The constant shipped unreferenced, so editing it changed nothing.

        It exists so the ambiguous unpadded day (Jan 12 and Nov 2 both render 2026112)
        is a one-line change. Swap in a padded format and the built number must follow.
        """
        self.assertEqual(
            app_module.reimbursement_tracker_control_number('JFL', date(2026, 8, 7), 31),
            'JFL-2026087-031',
        )
        original = app_module.REIMBURSEMENT_TRACKER_CONTROL_DATE_FORMAT
        try:
            app_module.REIMBURSEMENT_TRACKER_CONTROL_DATE_FORMAT = '{d.year}{d.month:02d}{d.day:02d}'
            self.assertEqual(
                app_module.reimbursement_tracker_control_number('JFL', date(2026, 8, 7), 31),
                'JFL-20260807-031',
                'the constant is not wired into the builder',
            )
        finally:
            app_module.REIMBURSEMENT_TRACKER_CONTROL_DATE_FORMAT = original

    def test_office_must_match_the_engineers_branch(self):
        """The workbook made this impossible: its engineer list was an INDIRECT on office.

        The page reproduces that, but the endpoint accepted any string at all -- so a
        Davao engineer could be filed under Manila, or under an office that exists nowhere.
        """
        client = self._client_for(self.tracker_user_id)
        before = client.get('/get_reimbursement_tracker_entries').get_json()['entries']

        mismatch = client.post('/add_reimbursement_tracker_entry',
                               json=self._payload(engineer_id=self.raj_id, office='Manila'))
        self.assertEqual(mismatch.status_code, 400)
        self.assertIn('Cebu', mismatch.get_json()['error'])

        unknown = client.post('/add_reimbursement_tracker_entry',
                              json=self._payload(engineer_id=self.jfl_id, office='Atlantis'))
        self.assertEqual(unknown.status_code, 400)

        # Positive control: the matching office still saves, so the rule refuses the
        # mismatch rather than refusing everything.
        ok = client.post('/add_reimbursement_tracker_entry',
                         json=self._payload(engineer_id=self.raj_id, office='Cebu'))
        self.assertEqual(ok.status_code, 201, ok.get_data(as_text=True))
        self.assertEqual(ok.get_json()['entry']['office'], 'Cebu')

        after = client.get('/get_reimbursement_tracker_entries').get_json()['entries']
        self.assertEqual(len(after), len(before) + 1, 'only the valid row may be stored')

    def test_a_transferred_engineer_does_not_make_old_rows_unsaveable(self):
        """Office is a snapshot of where the row was filed, deliberately denormalised.

        So the branch check must not fire when an existing row's stored office is
        resubmitted unchanged -- otherwise a transfer would freeze every historical row.
        """
        client = self._client_for(self.tracker_user_id)
        row = self._add(client, engineer_id=self.jfl_id, office='Manila')
        with self.app.app_context():
            engineer = app_module.db.session.get(app_module.Engineer, self.jfl_id)
            engineer.branch = 'Davao'
            app_module.db.session.commit()
        try:
            edit = client.post(f'/update_reimbursement_tracker_entry/{row["id"]}',
                               json=self._payload(engineer_id=self.jfl_id, office='Manila',
                                                  description='Edited after the transfer'))
            self.assertEqual(edit.status_code, 200, edit.get_data(as_text=True))
            self.assertEqual(edit.get_json()['entry']['office'], 'Manila')
        finally:
            with self.app.app_context():
                engineer = app_module.db.session.get(app_module.Engineer, self.jfl_id)
                engineer.branch = 'Manila'
                app_module.db.session.commit()


if __name__ == '__main__':
    unittest.main()
