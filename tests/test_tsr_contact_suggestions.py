"""Focused contracts for client-contact suggestions and TSR acknowledgement signatures."""

import json
import pathlib
import subprocess
import unittest
from datetime import datetime, time
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = pathlib.Path(r'C:\Users\Jonamar\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe')

try:
    import app as app_module
except Exception as exc:  # pragma: no cover - source contracts remain useful without imports
    app_module = None
    APP_IMPORT_ERROR = exc
else:
    APP_IMPORT_ERROR = None


class TSRContactSuggestionSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.tsr_source = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')
        cls.release_source = (ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8')

    def test_backend_builds_a_plural_client_scoped_projection(self):
        self.assertIn('def offline_tsr_client_contacts_payload', self.app_source)
        schedule_route = self.app_source.split("@app.route('/get_offline_tsr_schedule_options')", 1)[1]
        schedule_route = schedule_route.split("@app.route(", 1)[0]
        self.assertIn("'client_contacts': client_contacts", schedule_route)
        self.assertIn("'client_contact': client_contact", schedule_route)
        self.assertIn('offline_tsr_client_contacts_payload(client)', schedule_route)
        self.assertIn('.filter_by(client_id=client.id)', self.app_source)
        self.assertIn('.order_by(Contact.id.asc())', self.app_source)

    def test_backend_contact_projection_has_deduplication_and_legacy_fallback(self):
        self.assertIn('def offline_tsr_client_contacts_payload', self.app_source)
        helper = self.app_source.split('def offline_tsr_client_contacts_payload(', 1)[1].split('\n\n@app.route', 1)[0]
        for marker in (
            'clean_str',
            'lower()',
            'contact_person_{index}',
            'contact_number_{index}',
            'email_address_{index}',
            'range(1, 4)',
            'return contacts',
        ):
            self.assertIn(marker, helper)

    def test_current_signature_validation_preserves_legacy_uploaded_pdf_queue(self):
        self.assertIn('def online_tsr_has_acknowledged_signature', self.app_source)
        route = self.app_source.split("def save_offline_tsr_online():", 1)[1].split("@app.route(", 1)[0]
        self.assertIn('is_legacy_offline_queue', route)
        self.assertIn('online_tsr_has_acknowledged_signature(payload)', route)
        self.assertIn("_offline_queue_preserve_pdf", route)
        self.assertIn("_tsr_form_version", route)

    def test_frontend_suggestion_panel_is_rendered_and_isolated(self):
        for marker in (
            'id="tsr-client-contact-suggestions"',
            'function normalizeTSRClientContacts',
            'function renderTSRClientContactSuggestions',
            'function applySuggestedTSRClientContact',
            'client_contacts',
            'client_contact',
            'tsr-acknowledged-by',
            'tsr-contact-no',
            'tsr-email-add',
            'tsr-requested-by',
            'signatureData.acknowledged',
        ):
            self.assertIn(marker, self.tsr_source)

        apply_fn = self.tsr_source.split('function applySuggestedTSRClientContact(')[1].split('\nfunction ', 1)[0]
        self.assertIn("setFieldValue('tsr-acknowledged-by'", apply_fn)
        self.assertIn("setFieldValue('tsr-contact-no'", apply_fn)
        self.assertIn("setFieldValue('tsr-email-add'", apply_fn)
        self.assertIn("signatureData.acknowledged = ''", apply_fn)
        self.assertNotIn("getElementById('tsr-requested-by').value", apply_fn)

    def test_frontend_renders_contacts_after_each_schedule_restore_path(self):
        for function_name in (
            'refreshStandaloneScheduleOptions',
            'applyScheduleToStandaloneTSR',
            'applyStandaloneTSRDraftData',
            'loadOnlineTSRRevisionFromUrl',
        ):
            self.assertIn('renderTSRClientContactSuggestions', self.tsr_source.split(f'function {function_name}(')[1].split('\nfunction ', 1)[0] if f'function {function_name}(' in self.tsr_source else '')

    def test_final_validation_requires_both_signatures_but_settings_is_engineer_only(self):
        validation = self.tsr_source.split('async function validateTSRFinalSaveRequirements(')[1].split('\nconst TSR_RECOMMENDED_DETAIL_CHECKS', 1)[0]
        self.assertIn('hasRequiredServicedSignature', validation)
        self.assertIn('hasRequiredAcknowledgedSignature', validation)
        self.assertIn("openSignatureModal('acknowledged')", validation)
        self.assertNotIn("loadMySavedSignatureForTSR()", validation.split('hasRequiredAcknowledgedSignature', 1)[-1])
        saved_signature = self.tsr_source.split('async function applyMySavedSignatureToTSR(')[1].split('\nfunction hasRequiredServicedSignature', 1)[0]
        self.assertIn("target !== 'serviced'", saved_signature)

    def test_cache_and_release_markers_are_updated(self):
        self.assertIn("medical-service-pwa-offline-navigation-v127-tsr-contact-suggestions", self.app_source)
        for test_name in ('test_layout_sidebar.py', 'test_stock_inventory.py', 'test_timeline_desktop_collapse.py'):
            source = (ROOT / 'tests' / test_name).read_text(encoding='utf-8')
            self.assertIn('medical-service-pwa-offline-navigation-v127-tsr-contact-suggestions', source)
        self.assertIn('2026-09-05-tsr-contact-suggestions', self.release_source)
        self.assertIn('per-TSR client signing', self.release_source)

    @unittest.skipUnless(NODE.exists(), f'Node runtime unavailable at {NODE}')
    def test_node_contact_selection_maps_only_the_three_intended_fields(self):
        set_field_value = 'function setFieldValue(' + self.tsr_source.split('function setFieldValue(', 1)[1].split('\n\nfunction normalizeTSRClientContacts', 1)[0]
        normalize = 'function normalizeTSRClientContacts(' + self.tsr_source.split('function normalizeTSRClientContacts(', 1)[1].split('\n\nfunction renderTSRClientContactSuggestions', 1)[0]
        apply_contact = 'function applySuggestedTSRClientContact(' + self.tsr_source.split('function applySuggestedTSRClientContact(', 1)[1].split('\n\nconst TSR_SCHEDULE_LOCKED_FIELD_IDS', 1)[0]
        script = f"""
const fields = {{
  'tsr-acknowledged-by': {{ value: 'Old signer', dispatchEvent() {{}} }},
  'tsr-contact-no': {{ value: 'old-number', dispatchEvent() {{}} }},
  'tsr-email-add': {{ value: 'old@example.test', dispatchEvent() {{}} }},
  'tsr-requested-by': {{ value: 'Requester', dispatchEvent() {{}} }}
}};
const document = {{ getElementById(id) {{ return fields[id] || null; }} }};
class Event {{ constructor(type, options) {{ this.type = type; this.options = options; }} }}
let signatureData = {{ serviced: 'engineer', acknowledged: 'old-client-signature' }};
let standaloneTSRClientContactSuggestions = [];
let saved = false;
function updateSignatureStatuses() {{}}
function saveStandaloneTSRDraft() {{ saved = true; }}
function showTSRStatus() {{}}
{set_field_value}
{normalize}
{apply_contact}
standaloneTSRClientContactSuggestions = normalizeTSRClientContacts({{
  client_contacts: [
    {{name: ' Alice ', phone: ' 100 ', email: 'alice@example.test'}},
    {{name: 'Alice duplicate', phone: '', email: 'ALICE@example.test'}},
    {{name: 'Bob', phone: '200', email: ''}}
  ]
}});
const applied = applySuggestedTSRClientContact(0);
console.log(JSON.stringify({{ applied, count: standaloneTSRClientContactSuggestions.length, fields, signatureData, saved }}));
"""
        result = subprocess.run([str(NODE), '-e', script], cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout.strip())
        self.assertTrue(output['applied'])
        self.assertEqual(output['count'], 2)
        self.assertEqual(output['fields']['tsr-acknowledged-by']['value'], 'Alice')
        self.assertEqual(output['fields']['tsr-contact-no']['value'], '100')
        self.assertEqual(output['fields']['tsr-email-add']['value'], 'alice@example.test')
        self.assertEqual(output['fields']['tsr-requested-by']['value'], 'Requester')
        self.assertEqual(output['signatureData']['acknowledged'], '')
        self.assertTrue(output['saved'])


@unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
class TSRContactProjectionTests(unittest.TestCase):
    def test_dynamic_contacts_are_stable_trimmed_and_deduplicated(self):
        query = Mock()
        query.filter_by.return_value.order_by.return_value.all.return_value = [
            SimpleNamespace(name=' Alice ', phone=' +1 555 ', email=' ALICE@EXAMPLE.COM '),
            SimpleNamespace(name='Alice duplicate', phone='', email='alice@example.com'),
            SimpleNamespace(name=' Bob ', phone=' 555-2 ', email=''),
            SimpleNamespace(name='Bob', phone='555-2', email=''),
        ]
        client = SimpleNamespace(
            id=701,
            contact_person_1='Legacy Person', contact_number_1='legacy-phone', email_address_1='legacy@example.com',
            contact_person_2='', contact_number_2='', email_address_2='',
            contact_person_3='', contact_number_3='', email_address_3='',
        )
        with app_module.app.app_context(), patch.object(app_module.Contact, 'query', query):
            contacts = app_module.offline_tsr_client_contacts_payload(client)

        self.assertEqual(
            contacts,
            [
                {'name': 'Alice', 'phone': '+1 555', 'email': 'ALICE@EXAMPLE.COM'},
                {'name': 'Bob', 'phone': '555-2', 'email': ''},
            ],
        )
        query.filter_by.assert_called_once_with(client_id=701)

    def test_legacy_slots_are_used_when_dynamic_contacts_are_absent(self):
        query = Mock()
        query.filter_by.return_value.order_by.return_value.all.return_value = []
        client = SimpleNamespace(
            id=702,
            contact_person_1=' Legacy One ', contact_number_1=' 111 ', email_address_1='one@example.com',
            contact_person_2='legacy one', contact_number_2='111', email_address_2='ONE@example.com',
            contact_person_3='Legacy Two', contact_number_3='222', email_address_3='two@example.com',
        )
        with app_module.app.app_context(), patch.object(app_module.Contact, 'query', query):
            contacts = app_module.offline_tsr_client_contacts_payload(client)

        self.assertEqual(
            contacts,
            [
                {'name': 'Legacy One', 'phone': '111', 'email': 'one@example.com'},
                {'name': 'Legacy Two', 'phone': '222', 'email': 'two@example.com'},
            ],
        )

    def test_acknowledged_signature_predicate_is_independent_from_engineer_signature(self):
        valid = 'data:image/png;base64,client-signature'
        self.assertFalse(app_module.online_tsr_has_acknowledged_signature({'signatures': {'serviced': valid}}))
        self.assertTrue(app_module.online_tsr_has_acknowledged_signature({'signatures': {'acknowledged': valid}}))
        self.assertFalse(app_module.online_tsr_has_acknowledged_signature({'signatures': {'acknowledged': 'client-signature'}}))

    def test_same_draft_projection_keeps_acknowledgement_signature(self):
        valid = 'data:image/png;base64,client-signature'
        projected = app_module.project_tsr_draft_payload_for_server({
            'signatures': {'serviced': 'data:image/png;base64,engineer', 'acknowledged': valid},
            'attachments': [{'name': 'photo.jpg', 'blob': 'browser-only'}],
        })
        self.assertEqual(projected['signatures']['acknowledged'], valid)
        self.assertNotIn('browser-only', json.dumps(projected))


@unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
class TSRContactScheduleRouteTests(unittest.TestCase):
    """The schedule endpoint must return only the selected client's contacts."""

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.suffix = uuid4().hex[:10]
        with cls.app.app_context():
            app_module.db.create_all()
            user = app_module.User(
                username=f'tsr-contact-route-{cls.suffix}',
                password='test-password',
                role='engineer',
                is_active=True,
            )
            app_module.db.session.add(user)
            app_module.db.session.flush()
            engineer = app_module.Engineer(
                user_id=user.id,
                employee_id=f'TSR-CONTACT-{cls.suffix}',
                name='TSR Contact Route Engineer',
                initials='TCR',
                branch='Manila',
            )
            selected_client = app_module.Client(
                name=f'TSR Contact Route Client {cls.suffix}',
                address='Route client address',
                contact_person_1='Legacy route contact',
                contact_number_1='legacy-route-phone',
                email_address_1='legacy-route@example.test',
            )
            other_client = app_module.Client(name=f'Other TSR Contact Client {cls.suffix}')
            app_module.db.session.add_all([engineer, selected_client, other_client])
            app_module.db.session.flush()
            shift = app_module.Shift(
                title=f'TSR contact route shift {cls.suffix}',
                start_time=datetime.combine(app_module.get_manila_today(), time(8, 0)),
                end_time=datetime.combine(app_module.get_manila_today(), time(17, 0)),
                engineer_id=engineer.id,
                client_id=selected_client.id,
                status='In Progress',
            )
            contacts = [
                app_module.Contact(
                    client_id=selected_client.id,
                    name=' Route First ',
                    phone=' route-phone ',
                    email='route@example.test',
                ),
                app_module.Contact(
                    client_id=selected_client.id,
                    name='Duplicate Route First',
                    phone='',
                    email='ROUTE@example.test',
                ),
                app_module.Contact(
                    client_id=other_client.id,
                    name='Other Client Person',
                    phone='other-phone',
                    email='other@example.test',
                ),
            ]
            app_module.db.session.add_all([shift, *contacts])
            app_module.db.session.commit()
            cls.user_id = user.id
            cls.shift_id = shift.id
            cls.selected_client_id = selected_client.id
            cls.other_client_id = other_client.id
            cls.contact_ids = [contact.id for contact in contacts]
            cls.engineer_id = engineer.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            for contact_id in getattr(cls, 'contact_ids', []):
                contact = app_module.db.session.get(app_module.Contact, contact_id)
                if contact:
                    app_module.db.session.delete(contact)
            shift = app_module.db.session.get(app_module.Shift, getattr(cls, 'shift_id', None))
            if shift:
                app_module.db.session.delete(shift)
            client = app_module.db.session.get(app_module.Client, getattr(cls, 'selected_client_id', None))
            if client:
                app_module.db.session.delete(client)
            other_client = app_module.db.session.get(app_module.Client, getattr(cls, 'other_client_id', None))
            if other_client:
                app_module.db.session.delete(other_client)
            engineer = app_module.db.session.get(app_module.Engineer, getattr(cls, 'engineer_id', None))
            if engineer:
                app_module.db.session.delete(engineer)
            user = app_module.db.session.get(app_module.User, getattr(cls, 'user_id', None))
            if user:
                app_module.db.session.delete(user)
            app_module.db.session.commit()
            app_module.db.session.remove()

    def test_schedule_response_contains_singular_compatibility_and_plural_scoped_contacts(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.user_id)
            session['_fresh'] = True

        with patch.object(app_module, 'ensure_shift_file_original_filename_column'), \
                patch.object(app_module, 'get_tsr_completion_linked_shifts', return_value=[]), \
                patch.object(app_module, 'get_tsr_schedule_coverage_rows', return_value=[]):
            response = client.get('/get_offline_tsr_schedule_options')

        self.assertEqual(response.status_code, 200)
        schedule = next(item for item in response.get_json()['schedules'] if item['id'] == self.shift_id)
        self.assertEqual(schedule['client_contact'], {
            'name': 'Route First',
            'phone': 'route-phone',
            'email': 'route@example.test',
        })
        self.assertEqual(schedule['client_contacts'], [{
            'name': 'Route First',
            'phone': 'route-phone',
            'email': 'route@example.test',
        }])
        serialized = json.dumps(schedule)
        self.assertNotIn('Other Client Person', serialized)
        self.assertNotIn('other@example.test', serialized)

    def test_current_vector_save_rejects_a_missing_client_signature(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.user_id)
            session['_fresh'] = True

        payload = {
            'schedule_id': self.shift_id,
            'selectedSchedule': {'id': self.shift_id},
            'signatures': {'serviced': 'data:image/png;base64,engineer-only'},
            '_tsr_form_version': 'vector-pdf-v2',
        }
        with patch.object(app_module, 'can_work_on_existing_schedule_shift', return_value=True), \
                patch.object(app_module, 'get_tsr_schedule_coverage_rows', return_value=[]):
            response = client.post('/save_offline_tsr_online', json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn('Acknowledged By client signature is required', response.get_json()['message'])


if __name__ == '__main__':
    unittest.main()
