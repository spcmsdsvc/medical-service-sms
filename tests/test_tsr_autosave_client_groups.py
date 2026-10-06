"""Focused contracts and isolated route checks for the TSR/client package."""

import json
import os
import pathlib
import tempfile
import unittest
from contextlib import contextmanager

from sqlalchemy import create_engine

from tests.sw_cache_version import assert_cache_version_at_least


ROOT = pathlib.Path(__file__).resolve().parents[1]

try:
    import app as app_module
except Exception as exc:  # pragma: no cover - source contracts still run without deps
    app_module = None
    APP_IMPORT_ERROR = exc
else:
    APP_IMPORT_ERROR = None


class TsrAutosaveClientGroupSourceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.tsr_source = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')
        cls.calibration_source = (ROOT / 'static' / 'js' / 'app-calibration-report.js').read_text(encoding='utf-8')
        cls.clients_source = (ROOT / 'templates' / 'clients.html').read_text(encoding='utf-8')

    def test_saved_versions_identify_active_calibration_reports_independently(self):
        self.assertIn('standaloneTSRDraftVersionHasCalibrationReport', self.tsr_source)
        self.assertIn('Calibration Report saved with this draft', self.tsr_source)
        self.assertIn('standaloneTSRDraftVersionHasCalibrationReport(version)', self.tsr_source)
        self.assertIn("status !== 'not_started'", self.tsr_source)

    def test_autosave_uses_900_ms_and_calibration_editor_exposes_save_state(self):
        self.assertIn('const STANDALONE_TSR_SERVER_DRAFT_DEBOUNCE_MS = 900;', self.tsr_source)
        self.assertIn('id="calibration-report-save-status"', self.tsr_source)
        self.assertIn('setSaveStatusFromTSR', self.calibration_source)
        self.assertIn('scheduleDraftSave()', self.calibration_source)
        for state in ('unsaved', 'saving', 'device-saved', 'account-backed-up', 'conflict', 'failed'):
            self.assertIn("'{}'".format(state), self.calibration_source)
        self.assertIn("serverSync:'none'", self.tsr_source)

    def test_client_group_contract_and_hr_shape(self):
        self.assertIn('group_name = db.Column(db.String(100), nullable=True)', self.app_source)
        self.assertIn('ensure_client_group_column', self.app_source)
        self.assertIn("group_name = clean_str(payload.get('group_name')) or None", self.app_source)
        self.assertIn("'group_name': clean_str(getattr(c, 'group_name', None)) or None", self.app_source)
        self.assertIn("{'id': client.id, 'name': client.name or ''}", self.app_source)
        self.assertIn('id="c-group"', self.clients_source)
        self.assertIn('id="c-group-new"', self.clients_source)
        self.assertIn('id="s-group"', self.clients_source)
        self.assertIn('group_name', self.clients_source)

    def test_client_group_picker_exposes_existing_and_new_groups(self):
        self.assertIn('id="c-group"', self.clients_source)
        self.assertIn('id="c-group-new-wrap"', self.clients_source)
        self.assertIn('id="c-group-new"', self.clients_source)
        self.assertIn('CLIENT_GROUP_ADD_NEW_VALUE', self.clients_source)
        self.assertIn('refreshClientGroupOptions', self.clients_source)
        self.assertIn('setClientGroupSelection', self.clients_source)
        self.assertIn('getSelectedClientGroupName', self.clients_source)
        self.assertIn('Please enter a new group name.', self.clients_source)
        self.assertNotIn('<datalist id="client-group-list"', self.clients_source)

    def test_cache_and_release_are_registered(self):
        assert_cache_version_at_least(self, 199, self.app_source)
        releases = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))['releases']
        release = next(item for item in releases if item['release_key'] == '2026-09-26-tsr-autosave-client-groups')
        self.assertEqual(release['release_date'], '2026-09-26')


@unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
class ClientGroupRouteTests(unittest.TestCase):
    @contextmanager
    def isolated_database(self):
        fd, database_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        extension = None
        original_engine = None
        original_group_ready = None
        original_contact_ready = None
        test_engine = None
        original_csrf = None
        added_superadmin_username = None
        try:
            with app_module.app.app_context():
                extension = app_module.app.extensions['sqlalchemy']
                engines = extension._app_engines[app_module.app]
                original_engine = engines[None]
                original_group_ready = getattr(app_module, '_client_group_column_ready', False)
                original_contact_ready = getattr(app_module, '_contact_designation_column_ready', False)
                original_csrf = app_module.app.config.get('WTF_CSRF_ENABLED')
                app_module.app.config['WTF_CSRF_ENABLED'] = False
                test_engine = create_engine(f"sqlite:///{database_path.replace(os.sep, '/')}")
                engines[None] = test_engine
                app_module._client_group_column_ready = False
                app_module._contact_designation_column_ready = False
                app_module.db.session.remove()
                app_module.db.create_all()
                app_module.ensure_client_group_column()
                suffix = pathlib.Path(database_path).stem[-10:]
                admin = app_module.User(
                    username=f'client-group-admin-{suffix}', password='test-only', role='superadmin', is_active=True
                )
                engineer = app_module.User(
                    username=f'client-group-engineer-{suffix}', password='test-only', role='engineer', is_active=True
                )
                hr = app_module.User(
                    username=f'client-group-hr-{suffix}', password='test-only', role='staff', is_active=True,
                    hr_schedule_view=True,
                )
                app_module.db.session.add_all([admin, engineer, hr])
                app_module.db.session.commit()
                added_superadmin_username = admin.username.lower()
                app_module.SUPERADMIN_USERNAMES.add(added_superadmin_username)
                user_ids = {'admin': admin.id, 'engineer': engineer.id, 'hr': hr.id}
            clients = {}
            for label, user_id in user_ids.items():
                client = app_module.app.test_client()
                with client.session_transaction() as session:
                    session['_user_id'] = str(user_id)
                    session['_fresh'] = True
                clients[label] = client
            yield clients
        finally:
            if extension is not None:
                with app_module.app.app_context():
                    app_module.db.session.remove()
                    if original_engine is not None:
                        extension._app_engines[app_module.app][None] = original_engine
                    app_module._client_group_column_ready = original_group_ready
                    app_module._contact_designation_column_ready = original_contact_ready
                    if added_superadmin_username:
                        app_module.SUPERADMIN_USERNAMES.discard(added_superadmin_username)
                    if original_csrf is not None:
                        app_module.app.config['WTF_CSRF_ENABLED'] = original_csrf
            if test_engine is not None:
                test_engine.dispose()
            if database_path and os.path.exists(database_path):
                os.unlink(database_path)

    def test_admin_group_crud_non_hr_payload_and_hr_shape(self):
        with self.isolated_database() as clients:
            created = clients['admin'].post('/add_client', json={
                'name': 'Grouped Client', 'address': 'A', 'group_name': 'North Clinics',
            })
            self.assertEqual(created.status_code, 200)
            with app_module.app.app_context():
                client = app_module.Client.query.filter_by(name='Grouped Client').first()
                self.assertEqual(client.group_name, 'North Clinics')
                client_id = client.id

            payload = next(row for row in clients['admin'].get('/get_clients').get_json() if row['id'] == client_id)
            self.assertEqual(payload['group_name'], 'North Clinics')

            updated = clients['admin'].put(f'/update_client/{client_id}', json={
                'name': 'Grouped Client', 'address': 'A', 'group_name': '',
            })
            self.assertEqual(updated.status_code, 200)
            with app_module.app.app_context():
                self.assertIsNone(app_module.db.session.get(app_module.Client, client_id).group_name)

            hr_payload = next(row for row in clients['hr'].get('/get_clients').get_json() if row['id'] == client_id)
            self.assertEqual(set(hr_payload), {'id', 'name'})

    def test_contact_only_update_cannot_change_group(self):
        with self.isolated_database() as clients:
            with app_module.app.app_context():
                record = app_module.Client(name='Protected Group Client', group_name='Keep This')
                app_module.db.session.add(record)
                app_module.db.session.commit()
                client_id = record.id

            updated = clients['engineer'].put(f'/update_client/{client_id}', json={
                'name': 'Attempted Rename', 'address': 'Attempted Address', 'group_name': 'Hacked',
                'cp1': 'Field Contact',
            })
            self.assertEqual(updated.status_code, 200)
            with app_module.app.app_context():
                record = app_module.db.session.get(app_module.Client, client_id)
                self.assertEqual(record.group_name, 'Keep This')
                self.assertEqual(record.name, 'Protected Group Client')


@unittest.skipIf(app_module is None, f'app import failed: {APP_IMPORT_ERROR}')
class MedicalCenterProtectDataTests(unittest.TestCase):
    """Medical Center Batch 1: safe delete, blank names, and CSV round trip."""

    isolated_database = ClientGroupRouteTests.isolated_database

    def _add_client(self, name='Linked Client', **contacts):
        with app_module.app.app_context():
            record = app_module.Client(name=name, address='Addr', group_name=contacts.pop('group', None))
            app_module.db.session.add(record)
            app_module.db.session.flush()
            for contact_name in contacts.pop('contact_names', []):
                app_module.db.session.add(app_module.Contact(client_id=record.id, name=contact_name))
            app_module.db.session.commit()
            return record.id

    def _import(self, client, text):
        import io
        return client.post('/import_clients', data={'file': (io.BytesIO(text.encode('utf-8')), 'clients.csv')},
                           content_type='multipart/form-data')

    def test_delete_refused_with_schedule_equipment_or_po(self):
        from datetime import date, datetime
        with self.isolated_database() as clients:
            with_shift = self._add_client('Has Schedule')
            with_product = self._add_client('Has Equipment')
            with_po = self._add_client('Has PO')
            with app_module.app.app_context():
                engineer = app_module.Engineer(employee_id='MC-1', name='Eng One', initials='EO')
                app_module.db.session.add(engineer)
                app_module.db.session.flush()
                shift = app_module.Shift(title='PM', start_time=datetime(2026, 10, 1, 8), end_time=datetime(2026, 10, 1, 17),
                                         engineer_id=engineer.id, client_id=with_shift)
                app_module.db.session.add(shift)
                app_module.db.session.add(app_module.Product(serial_number='MC-SN-1', name='CT', client_id=with_product))
                app_module.db.session.add(app_module.PurchaseOrder(client_id=with_po, po_number='MC-PO-1',
                                                                   po_date=date(2026, 10, 1), po_type='single'))
                app_module.db.session.commit()
                shift_id = shift.id

            for client_id, word in ((with_shift, 'schedule'), (with_product, 'equipment'), (with_po, 'P.O.')):
                response = clients['admin'].delete(f'/delete_client/{client_id}')
                self.assertEqual(response.status_code, 409, word)
                self.assertIn(word, response.get_json()['message'])

            with app_module.app.app_context():
                self.assertEqual(app_module.db.session.get(app_module.Shift, shift_id).client_id, with_shift)
                self.assertEqual(app_module.db.session.get(app_module.Product, 'MC-SN-1').client_id, with_product)
                self.assertEqual(app_module.PurchaseOrder.query.filter_by(client_id=with_po).count(), 1)
                for client_id in (with_shift, with_product, with_po):
                    self.assertIsNotNone(app_module.db.session.get(app_module.Client, client_id))

    def test_delete_unlinked_removes_contacts_and_missing_is_404(self):
        with self.isolated_database() as clients:
            client_id = self._add_client('Unlinked', contact_names=['Ana', 'Ben'])
            self.assertEqual(clients['admin'].delete(f'/delete_client/{client_id}').status_code, 200)
            with app_module.app.app_context():
                self.assertIsNone(app_module.db.session.get(app_module.Client, client_id))
                self.assertEqual(app_module.Contact.query.filter_by(client_id=client_id).count(), 0)
            self.assertEqual(clients['admin'].delete(f'/delete_client/{client_id}').status_code, 404)

    def test_blank_name_is_400_on_add_and_update(self):
        with self.isolated_database() as clients:
            added = clients['admin'].post('/add_client', json={'name': '  ', 'address': 'A'})
            self.assertEqual(added.status_code, 400)
            self.assertEqual(added.get_json()['message'], 'Company name is required.')
            client_id = self._add_client('Named')
            updated = clients['admin'].put(f'/update_client/{client_id}', json={'name': '', 'address': 'A'})
            self.assertEqual(updated.status_code, 400)

    def test_import_with_designation_and_group(self):
        with self.isolated_database() as clients:
            response = self._import(clients['admin'],
                'Name,Address,Group,Contact 1 Name,Contact 1 Designation,Contact 1 Phone,Contact 1 Email\n'
                'Imported Center,Cebu,South,Ana,Head Nurse,0917 000 0000,ana@example.com\n')
            self.assertEqual(response.status_code, 200, response.get_json())
            with app_module.app.app_context():
                record = app_module.Client.query.filter_by(name='Imported Center').one()
                self.assertEqual(record.group_name, 'South')
                contact = app_module.Contact.query.filter_by(client_id=record.id).one()
                self.assertEqual((contact.name, contact.designation), ('Ana', 'Head Nurse'))

    def test_export_import_round_trip_is_unchanged(self):
        with self.isolated_database() as clients:
            created = clients['admin'].post('/add_client', json={
                'name': 'Round Trip', 'address': 'Davao', 'group_name': 'East',
                'cp1': 'Ana', 'cd1': 'Head Nurse', 'cn1': '0917 111 1111', 'ce1': 'ana@example.com',
                'cp2': 'Ben', 'cd2': 'Biomed', 'cn2': '0918 222 2222', 'ce2': 'ben@example.com',
            })
            self.assertEqual(created.status_code, 200)
            exported = clients['admin'].get('/export_clients').get_data(as_text=True)
            self.assertIn('Group', exported.splitlines()[0])
            self.assertIn('Contact 1 Designation', exported.splitlines()[0])

            def snapshot():
                with app_module.app.app_context():
                    record = app_module.Client.query.filter_by(name='Round Trip').one()
                    rows = app_module.Contact.query.filter_by(client_id=record.id).order_by(app_module.Contact.id).all()
                    return (record.address, record.group_name,
                            [(c.name, c.designation, c.phone, c.email) for c in rows])

            before = snapshot()
            response = self._import(clients['admin'], exported)
            self.assertEqual(response.status_code, 200, response.get_json())
            self.assertEqual(snapshot(), before)

    def test_import_row_without_contacts_keeps_existing_contacts(self):
        with self.isolated_database() as clients:
            client_id = self._add_client('Keep Contacts', contact_names=['Ana'])
            response = self._import(clients['admin'], 'Name,Address\nKeep Contacts,Addr\n')
            self.assertEqual(response.status_code, 200, response.get_json())
            with app_module.app.app_context():
                self.assertEqual(app_module.Contact.query.filter_by(client_id=client_id).count(), 1)

    def test_page_handles_delete_refusal_and_blank_name(self):
        page = (ROOT / 'templates' / 'clients.html').read_text(encoding='utf-8')
        self.assertIn('Medical center deleted.', page)
        self.assertIn('Please enter the company name.', page)
        self.assertIn('Only possible when it has no schedules, equipment or P.O.s.', page)


@unittest.skipIf(app_module is None, f'app import failed: {APP_IMPORT_ERROR}')
class MedicalCenterSafetyTests(unittest.TestCase):
    """Medical Center Batch 2: escaping, admin-only buttons, contact safety."""

    isolated_database = ClientGroupRouteTests.isolated_database

    def _client_with_contacts(self, rows):
        with app_module.app.app_context():
            record = app_module.Client(name='Safety Client', address='Addr')
            app_module.db.session.add(record)
            app_module.db.session.flush()
            for name, phone, email in rows:
                app_module.db.session.add(app_module.Contact(client_id=record.id, name=name, phone=phone, email=email))
            app_module.db.session.commit()
            return record.id

    def _contacts(self, client_id):
        with app_module.app.app_context():
            return [(c.name, c.phone, c.email) for c in
                    app_module.Contact.query.filter_by(client_id=client_id).order_by(app_module.Contact.id).all()]

    def test_engineer_blank_row_keeps_every_contact(self):
        with self.isolated_database() as clients:
            rows = [('Ana', '0917 111 1111', None), ('Ben', '0917 222 2222', None), ('Cy', '0917 333 3333', None)]
            client_id = self._client_with_contacts(rows)
            response = clients['engineer'].put(f'/update_client/{client_id}', json={
                'name': 'Safety Client', 'address': 'Addr',
                'cp1': '', 'cd1': '', 'cn1': '', 'ce1': '',
                'cp2': 'Ben', 'cd2': '', 'cn2': '0917 222 2222', 'ce2': '',
                'cp3': 'Cy', 'cd3': '', 'cn3': '0917 333 3333', 'ce3': '',
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self._contacts(client_id), rows)

    def test_invalid_new_phone_or_email_is_refused(self):
        with self.isolated_database() as clients:
            added = clients['admin'].post('/add_client', json={'name': 'New Center', 'address': 'A', 'cp1': 'Ana', 'cn1': '12'})
            self.assertEqual(added.status_code, 400)
            self.assertIn('Contact 1: phone number is not valid', added.get_json()['message'])
            client_id = self._client_with_contacts([('Ana', '0917 111 1111', None)])
            for role in ('admin', 'engineer'):
                bad = clients[role].put(f'/update_client/{client_id}', json={
                    'name': 'Safety Client', 'address': 'Addr',
                    'cp1': 'Ana', 'cn1': '0917 111 1111', 'cp2': 'Ben', 'ce2': 'not-an-email',
                })
                self.assertEqual(bad.status_code, 400, role)
                self.assertIn('Contact 2: email address is not valid', bad.get_json()['message'])

    def test_unchanged_saved_value_is_still_accepted(self):
        with self.isolated_database() as clients:
            client_id = self._client_with_contacts([('Ana', '8123 loc 205', 'old-format')])
            response = clients['admin'].put(f'/update_client/{client_id}', json={
                'name': 'Safety Client', 'address': 'Addr', 'cp1': 'Ana', 'cn1': '8123 loc 205', 'ce1': 'old-format',
            })
            self.assertEqual(response.status_code, 200)

    def test_export_buttons_are_admin_only(self):
        with self.isolated_database() as clients:
            self.assertIn("/export_clients", clients['admin'].get('/clients_page').get_data(as_text=True))
            engineer_page = clients['engineer'].get('/clients_page').get_data(as_text=True)
            self.assertNotIn("/export_clients", engineer_page)
            self.assertIn('const canEditProducts', engineer_page)

    def test_page_escapes_saved_text(self):
        import re
        page = (ROOT / 'templates' / 'clients.html').read_text(encoding='utf-8')
        for raw in ('${c.name}', '${c.address ||', '${p.name ||', '${p.serial_number ||', '${p.client_name ||',
                    '${item.name}', '${item.address ||', '${data.name}', '${data.address ||'):
            self.assertNotIn(raw, page)
        self.assertIsNone(re.search(r"\('\$\{p\.serial_number\}'\)", page))
        self.assertIn('function clientJsArg(', page)


@unittest.skipIf(app_module is None, f'app import failed: {APP_IMPORT_ERROR}')
class MedicalCenterSpeedAndUiTests(unittest.TestCase):
    """Medical Center Batches 3 & 4: code cuts, faster loading, UI."""

    isolated_database = ClientGroupRouteTests.isolated_database

    def page(self):
        return (ROOT / 'templates' / 'clients.html').read_text(encoding='utf-8')

    def test_get_clients_returns_product_count(self):
        with self.isolated_database() as clients:
            with app_module.app.app_context():
                record = app_module.Client(name='Counted', address='A')
                app_module.db.session.add(record)
                app_module.db.session.flush()
                app_module.db.session.add(app_module.Product(serial_number='UI-SN-1', name='CT', client_id=record.id))
                app_module.db.session.add(app_module.Contact(client_id=record.id, name='Ana', email='ana@example.com'))
                app_module.db.session.commit()
                client_id = record.id
            row = next(r for r in clients['admin'].get('/get_clients').get_json() if r['id'] == client_id)
            self.assertEqual(row['product_count'], 1)
            self.assertEqual(row['cp1'], 'Ana')

    def test_search_route_removed_and_duplicate_409_has_details(self):
        with self.isolated_database() as clients:
            self.assertEqual(clients['admin'].get('/search_clients?q=x').status_code, 404)
            clients['admin'].post('/add_client', json={'name': 'Twin', 'address': 'Same'})
            duplicate = clients['admin'].post('/add_client', json={'name': 'Twin', 'address': 'Same'})
            self.assertEqual(duplicate.status_code, 409)
            body = duplicate.get_json()
            self.assertEqual((body['existing_name'], body['existing_address']), ('Twin', 'Same'))

    def test_dead_and_duplicated_code_removed(self):
        page = self.page()
        self.assertNotIn('while(c[`cp${i}`]', page)
        for gone in ('get_clients_summary', 'schedulerUsernames', 'autoCompleteClient', 'importToast', 'function clientEscape'):
            self.assertNotIn(gone, page)
        self.assertIn('function getClientContacts(', page)
        self.assertIn('function getClientProducts(', page)

    def test_ui_search_states_and_wording(self):
        page = self.page()
        for text in ('id="s-search"', '<select id="s-group"', 'Loading medical centers…',
                     'No medical centers match your search.', 'Could not load medical centers. Refresh to try again.',
                     'Medical Centers</h1>', '+ Add Medical Center', 'aria-label="Contact ${contactCount} name"'):
            self.assertIn(text, page)
        self.assertNotIn('<h5', page)

    def test_every_called_page_function_is_defined(self):
        import re
        page = self.page()
        script = page[page.index('<script>'):page.rindex('</script>')]
        shared = ''.join(p.read_text(encoding='utf-8') for p in [ROOT / 'templates' / 'layout.html', *(ROOT / 'static' / 'js').glob('*.js')])
        called = set(re.findall(r'on(?:click|input|change)="([A-Za-z_]\w*)\(', page))
        called |= set(re.findall(r'\b(\w*[Cc]lient\w*)\(', script))
        for name in sorted(called):
            self.assertTrue(re.search(rf'function\s+{name}\s*\(|window\.{name}\s*=', page + shared), f'{name} is called but not defined')


if __name__ == '__main__':
    unittest.main()
