"""Focused contracts for the admin-only Calibration Center package.

This module is intentionally added before the implementation for the required
fail-first checkpoint.  It uses source and route contracts for the new surface,
then exercises the pure manifest/recipient helpers once they exist.  No browser
or repository scheduler.db access is performed.
"""

import json
import pathlib
import re
import subprocess
import tempfile
import textwrap
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import app as app_module


ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / 'app.py').read_text(encoding='utf-8')
TEMPLATE_SOURCE = (ROOT / 'templates' / 'calibration_center.html').read_text(encoding='utf-8')
LAYOUT_SOURCE = (ROOT / 'templates' / 'layout.html').read_text(encoding='utf-8')
SETTINGS_SOURCE = (ROOT / 'templates' / 'settings.html').read_text(encoding='utf-8')


class CalibrationCenterContracts(unittest.TestCase):
    def test_center_page_renders_with_no_store_header(self):
        with app_module.app.test_request_context('/admin/calibration-center'), \
                patch.object(app_module, 'can_access_calibration_center', return_value=True), \
                patch.object(app_module, 'render_template', return_value='<main>Calibration Center</main>'):
            response = app_module.calibration_center_page.__wrapped__()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get('Cache-Control'),
            'no-store, no-cache, must-revalidate, max-age=0',
        )
        self.assertIn(b'Calibration Center', response.get_data())

    def test_center_authority_delegates_only_to_strict_system_admin_helper(self):
        user = object()
        with patch.object(app_module, 'is_admin_authorized', return_value=True) as strict_admin:
            self.assertTrue(app_module.can_access_calibration_center(user))
            strict_admin.assert_called_once_with(user)
        with patch.object(app_module, 'is_admin_authorized', return_value=False):
            self.assertFalse(app_module.can_access_calibration_center(user))

    def test_center_cc_group_follows_creator_engineer_branch(self):
        cases = {
            'Manila': 'calibration_report_certificate_cc',
            'Main': 'calibration_report_certificate_cc',
            '': 'calibration_report_certificate_cc',
            'Cebu': 'calibration_report_certificate_cc_cebu_davao',
            'Davao': 'calibration_report_certificate_cc_cebu_davao',
            'BC02': 'calibration_report_certificate_cc_cebu_davao',
            'BC03': 'calibration_report_certificate_cc_cebu_davao',
            'Cebu Branch': 'calibration_report_certificate_cc_cebu_davao',
        }
        for branch, expected in cases.items():
            with self.subTest(branch=branch):
                self.assertEqual(
                    app_module.calibration_report_certificate_cc_group_for_branch(branch),
                    expected,
                )

    def test_center_cc_context_uses_approval_creator_profile_and_email(self):
        creator = SimpleNamespace(
            username='creator',
            engineer_profile=SimpleNamespace(branch='Davao', email_address_1='creator@example.test'),
        )
        approval = SimpleNamespace(requester=creator, requester_user_id=42)
        with patch.object(
            app_module,
            'get_active_email_recipients_by_group',
            return_value=['regional@example.test'],
        ) as resolver:
            context = app_module.get_calibration_center_cc_context(approval)

        self.assertEqual(context['cc_group_key'], 'calibration_report_certificate_cc_cebu_davao')
        self.assertEqual(context['creator_branch'], 'Davao')
        self.assertEqual(context['creator_email'], 'creator@example.test')
        self.assertEqual(context['system_cc'], ['regional@example.test'])
        resolver.assert_called_once_with('calibration_report_certificate_cc_cebu_davao')

    def test_center_cc_context_allows_missing_creator_email(self):
        creator = SimpleNamespace(username='unknown', engineer_profile=SimpleNamespace(branch='Manila'))
        approval = SimpleNamespace(requester=creator, requester_user_id=7)
        with patch.object(app_module, 'get_active_email_recipients_by_group', return_value=[]):
            context = app_module.get_calibration_center_cc_context(approval)

        self.assertEqual(context['cc_group_key'], 'calibration_report_certificate_cc')
        self.assertEqual(context['creator_email'], '')
        self.assertEqual(context['creator_copy_message'], 'Creator email unavailable')

    def test_center_message_orders_and_deduplicates_branch_creator_sender_and_manual_cc(self):
        approval = SimpleNamespace(
            id=8,
            status='Approved',
            is_latest=True,
            shift_id=4,
            shift=SimpleNamespace(id=4),
        )
        cc_context = {
            'cc_group_key': 'calibration_report_certificate_cc_cebu_davao',
            'cc_group_label': 'Calibration Report & Certificate CC - Cebu/Davao',
            'creator_branch': 'Cebu',
            'creator_email': 'creator@example.test',
            'creator_copy_message': '',
            'system_cc': ['regional@example.test'],
        }
        artifacts = [
            {'id': 1, 'filename': 'report.pdf'},
            {'id': 2, 'filename': 'certificate.pdf'},
        ]
        with patch.object(app_module, 'get_calibration_center_email_artifacts', return_value=artifacts), \
                patch.object(app_module, 'get_calibration_center_manifest_signature', return_value='manifest'), \
                patch.object(app_module, 'build_calibration_only_email_bodies', return_value=('text', '<p>html</p>')), \
                patch.object(app_module, 'build_calibration_only_email_subject', return_value='Calibration'), \
                patch.object(app_module, 'get_calibration_center_cc_context', return_value=cc_context), \
                patch.object(app_module, 'get_current_user_email_for_tsr_cc', return_value='sender@example.test'), \
                patch.object(app_module, 'current_user', SimpleNamespace(is_authenticated=True, username='admin')):
            message, error, status = app_module.prepare_calibration_center_email_message(
                approval,
                {
                    'emails': 'client@example.test',
                    'manual_cc': 'CREATOR@example.test, regional@example.test, manual@example.test',
                    'attachment_manifest_signature': 'manifest',
                },
            )

        self.assertIsNone(error)
        self.assertEqual(status, 200)
        self.assertEqual(message['system_cc'], ['regional@example.test'])
        self.assertEqual(message['creator_copy'], ['creator@example.test'])
        self.assertEqual(message['sender_copy'], ['sender@example.test'])
        self.assertEqual(message['manual_cc'], ['manual@example.test'])
        self.assertEqual(
            message['final_cc'],
            ['regional@example.test', 'creator@example.test', 'sender@example.test', 'manual@example.test'],
        )

    def test_strict_center_authority_and_all_routes_are_declared(self):
        self.assertIn('def can_access_calibration_center(user=None):', APP_SOURCE)
        self.assertIn("CALIBRATION_REPORT_HISTORICAL_REPAIR_VERSION = 'calibration-report-units-v3'", APP_SOURCE)
        self.assertIn('def _calibration_report_exposure_unit_resolution(source_file):', APP_SOURCE)
        self.assertIn("'unit_sources':", APP_SOURCE)
        self.assertIn("@app.route('/admin/calibration-center'", APP_SOURCE)
        self.assertIn("@app.route('/admin/calibration-center/data'", APP_SOURCE)
        self.assertIn("@app.route('/admin/calibration-center/<int:approval_id>/email'", APP_SOURCE)
        self.assertIn("@app.route('/admin/calibration-center/<int:approval_id>/email-preview'", APP_SOURCE)
        self.assertIn("@app.route('/admin/calibration-center/<int:approval_id>/send-email'", APP_SOURCE)
        self.assertIn("@app.route('/admin/calibration-center/<int:source_file_id>/repair'", APP_SOURCE)
        self.assertIn("@app.route('/admin/calibration-center/repair-file/<int:source_file_id>')", APP_SOURCE)
        # Routes the page never called were removed with the repair-section cleanup.
        for removed in (
            '/admin/calibration-center/repair-preview',
            "'/admin/calibration-center/repairs/data'",
            "'/admin/calibration-center/repair/<int:source_file_id>'",
        ):
            self.assertNotIn(removed, APP_SOURCE)
        repair_apply_block = APP_SOURCE.split("@app.route('/admin/calibration-center/<int:source_file_id>/repair'", 1)[1].split(
            "def calibration_report_certificate_cc_group_for_branch", 1
        )[0]
        self.assertNotIn('@csrf.exempt', repair_apply_block)

    def test_center_query_is_current_approved_only_and_paginated(self):
        self.assertIn("CalibrationCertificateApproval.status == 'Approved'", APP_SOURCE)
        self.assertIn('CalibrationCertificateApproval.is_latest.is_(True)', APP_SOURCE)
        self.assertIn('per_page = 10', APP_SOURCE)
        self.assertIn("'delivery'", APP_SOURCE)
        self.assertIn("'unavailable_reason'", APP_SOURCE)

    def test_fixed_pair_and_calibration_cc_are_server_owned(self):
        self.assertIn('def get_calibration_center_email_artifacts(', APP_SOURCE)
        self.assertIn('def prepare_calibration_center_email_message(', APP_SOURCE)
        self.assertIn('def get_calibration_center_cc_context(', APP_SOURCE)
        self.assertIn("'calibration_report_certificate_cc_cebu_davao'", APP_SOURCE)
        self.assertIn("'creator_copy'", APP_SOURCE)
        self.assertIn("'calibration_report'", APP_SOURCE)
        self.assertIn("'calibration_certificate'", APP_SOURCE)
        self.assertIn('attachments_changed', APP_SOURCE)

    def test_settings_group_and_sidebar_contracts(self):
        self.assertIn("'calibration_report_certificate_cc'", APP_SOURCE)
        self.assertIn("nav_can_access_calibration_center", APP_SOURCE)
        self.assertIn('/admin/calibration-center', LAYOUT_SOURCE)
        self.assertIn('Calibration Center', LAYOUT_SOURCE)
        self.assertIn('calibration_report_certificate_cc', SETTINGS_SOURCE)
        self.assertIn('calibration_report_certificate_cc_cebu_davao', SETTINGS_SOURCE)

    def test_template_contains_required_safe_states_and_controls(self):
        template = TEMPLATE_SOURCE
        for marker in (
            'calibration-center-loading',
            'calibration-center-empty',
            'calibration-center-error',
            'delivery',
            'email-preview',
            'send-email',
            'csrf',
            'attachment_manifest_signature',
            'data.html_body',
            'state.confirmKey = \'\'',
            'calibration-center-preview-creator-copy',
            'Creator email unavailable',
            'Repair All',
            'repairRunning',
            'candidate.target_units',
            'calibration-center-confirm-backdrop',
            'calibration-center-repair-result',
            'sandbox=""',
        ):
            self.assertIn(marker, template)
        # No typed confirmations, test-only markers, or implementation wording on the page.
        for removed in (
            'REPAIR ALL',
            'confirm-input',
            'repair-preview',
            'contract marker',
            'compatibility contracts',
            'twips',
            'Repair version',
            'bulk-safe',
            'immutable saved',
            'manual_required',
            'Needs review',
        ):
            self.assertNotIn(removed, template)

    def test_historical_repair_starts_hidden_and_exposes_accessible_toggle(self):
        self.assertRegex(
            TEMPLATE_SOURCE,
            r'id="calibration-center-repair-area"[^>]*class="[^"]*d-none',
        )
        self.assertRegex(
            TEMPLATE_SOURCE,
            r'id="calibration-center-repair-panel"[^>]*class="[^"]*d-none',
        )
        self.assertRegex(
            TEMPLATE_SOURCE,
            r'id="calibration-center-repair-view"[^>]*aria-expanded="false"[^>]*aria-controls="calibration-center-repair-panel"',
        )
        self.assertRegex(
            TEMPLATE_SOURCE,
            r'id="calibration-center-repair-hide"[^>]*aria-expanded="true"[^>]*aria-controls="calibration-center-repair-panel"',
        )

    def test_historical_repair_notice_uses_only_repairable_and_blocked_attention(self):
        self.assertIn('calibration-center-repair-notice', TEMPLATE_SOURCE)
        self.assertIn('repair-notice-repairable', TEMPLATE_SOURCE)
        self.assertIn('repair-notice-blocked', TEMPLATE_SOURCE)
        self.assertRegex(TEMPLATE_SOURCE, r'const attention\s*=\s*repairable\s*\+\s*blocked')
        self.assertIn('if (attention > 0)', TEMPLATE_SOURCE)
        self.assertIn('state.repairActionOccurred', TEMPLATE_SOURCE)
        self.assertIn('already_repaired', TEMPLATE_SOURCE)

    def test_historical_repair_completion_and_load_failure_stay_viewable(self):
        self.assertIn('calibration-center-repair-success', TEMPLATE_SOURCE)
        self.assertIn('All repairs are complete', TEMPLATE_SOURCE)
        self.assertIn('calibration-center-repair-load-error', TEMPLATE_SOURCE)
        self.assertIn('The repair list could not be loaded', TEMPLATE_SOURCE)
        self.assertIn('setVisible(\'calibration-center-repair-area\', true)', TEMPLATE_SOURCE)

    def test_historical_repair_details_keep_existing_actions(self):
        for marker in (
            'calibration-center-repair-summary',
            'calibration-center-repair-table-wrap',
            'calibration-center-repair-all',
            'js-calibration-repair',
            '`/admin/calibration-center/${id}/repair`',
            '`/admin/calibration-center/repair-file/${sourceFileId}`',
            'state.repairRunning',
        ):
            self.assertIn(marker, TEMPLATE_SOURCE)

    def test_historical_repair_surface_states_execute_in_node(self):
        script_match = re.search(r'<script>\s*(.*?)\s*</script>', TEMPLATE_SOURCE, re.DOTALL)
        self.assertIsNotNone(script_match)
        source = script_match.group(1)
        bootstrap = '    loadRecords(); loadRepairInventory();\n})();'
        self.assertIn(bootstrap, source)
        source = source.replace(
            bootstrap,
            '    globalThis.__repairTest = {state, renderRepairSurface, setRepairDetails, showRepairLoadError};\n})();',
            1,
        )
        node_script = textwrap.dedent(f'''
            const assert = require('assert');
            class ClassList {{
              constructor() {{ this.names = new Set(); }}
              toggle(name, force) {{
                const shouldHave = force === undefined ? !this.names.has(name) : Boolean(force);
                if (shouldHave) this.names.add(name); else this.names.delete(name);
                return shouldHave;
              }}
              contains(name) {{ return this.names.has(name); }}
            }}
            class Element {{
              constructor(id) {{ this.id = id; this.classList = new ClassList(); this.attributes = {{}}; this.listeners = {{}}; this.textContent = ''; this.value = ''; }}
              setAttribute(name, value) {{ this.attributes[name] = String(value); }}
              getAttribute(name) {{ return this.attributes[name] ?? null; }}
              addEventListener(name, handler) {{ this.listeners[name] = handler; }}
              focus() {{}}
              querySelector() {{ return null; }}
              querySelectorAll() {{ return []; }}
            }}
            const elements = new Map();
            const getElement = id => {{ if (!elements.has(id)) elements.set(id, new Element(id)); return elements.get(id); }};
            globalThis.document = {{
              getElementById: getElement,
              querySelector: () => null,
              querySelectorAll: () => [],
            }};
            globalThis.fetch = async () => {{ throw new Error('fetch should not run in this state harness'); }};
            eval({json.dumps(source)});
            const api = globalThis.__repairTest;
            const visible = id => !getElement(id).classList.contains('d-none');
            ['calibration-center-repair-area', 'calibration-center-repair-panel', 'calibration-center-repair-notice', 'calibration-center-repair-success', 'calibration-center-repair-load-error'].forEach(id => getElement(id).classList.toggle('d-none', true));
            getElement('calibration-center-repair-view').setAttribute('aria-expanded', 'false');
            getElement('calibration-center-repair-hide').setAttribute('aria-expanded', 'true');
            assert.strictEqual(visible('calibration-center-repair-area'), false);
            assert.strictEqual(getElement('calibration-center-repair-view').getAttribute('aria-expanded'), 'false');
            api.renderRepairSurface({{repairable: 2, blocked: 1, already_repaired: 9}});
            assert.strictEqual(visible('calibration-center-repair-area'), true);
            assert.strictEqual(visible('calibration-center-repair-notice'), true);
            assert.strictEqual(visible('calibration-center-repair-panel'), false);
            assert.strictEqual(getElement('repair-notice-repairable').textContent, '2');
            assert.strictEqual(getElement('repair-notice-blocked').textContent, '1');
            api.setRepairDetails(true);
            assert.strictEqual(visible('calibration-center-repair-panel'), true);
            assert.strictEqual(getElement('calibration-center-repair-view').getAttribute('aria-expanded'), 'true');
            assert.strictEqual(getElement('calibration-center-repair-hide').getAttribute('aria-expanded'), 'true');
            api.setRepairDetails(false);
            assert.strictEqual(visible('calibration-center-repair-panel'), false);
            api.renderRepairSurface({{repairable: 0, blocked: 0, already_repaired: 9}});
            assert.strictEqual(visible('calibration-center-repair-area'), false);
            api.state.repairActionOccurred = true;
            api.renderRepairSurface({{repairable: 0, blocked: 0}});
            assert.strictEqual(visible('calibration-center-repair-area'), true);
            assert.strictEqual(visible('calibration-center-repair-success'), true);
            assert.strictEqual(visible('calibration-center-repair-panel'), false);
            api.showRepairLoadError('request failed');
            assert.strictEqual(visible('calibration-center-repair-area'), true);
            assert.strictEqual(visible('calibration-center-repair-load-error'), true);
            assert.strictEqual(getElement('calibration-center-repair-load-error-message').textContent, 'request failed');
            assert.strictEqual(visible('calibration-center-repair-panel'), false);
            console.log('repair surface states: PASS');
        ''')
        with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8', delete=False) as script_file:
            script_file.write(node_script)
            script_path = script_file.name
        try:
            result = subprocess.run(['node', script_path], cwd=ROOT, capture_output=True, text=True, check=False)
        finally:
            pathlib.Path(script_path).unlink(missing_ok=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertIn('repair surface states: PASS', result.stdout)

    def test_repair_list_behaviour_executes_in_node(self):
        script_match = re.search(r'<script>\s*(.*?)\s*</script>', TEMPLATE_SOURCE, re.DOTALL)
        source = script_match.group(1)
        bootstrap = '    loadRecords(); loadRepairInventory();\n})();'
        source = source.replace(
            bootstrap,
            '    globalThis.__repairTest = {state, repairList, renderRepairInventory, repairListPage, repairButton, pageWindow, bulkCandidates};\n})();',
            1,
        )
        node_script = textwrap.dedent(f"""
            const assert = require('assert');
            class ClassList {{
              constructor() {{ this.names = new Set(); }}
              toggle(name, force) {{ const on = force === undefined ? !this.names.has(name) : Boolean(force); if (on) this.names.add(name); else this.names.delete(name); return on; }}
              add(name) {{ this.names.add(name); }}
              remove(name) {{ this.names.delete(name); }}
              contains(name) {{ return this.names.has(name); }}
            }}
            class Element {{
              constructor(id) {{ this.id = id; this.classList = new ClassList(); this.attributes = {{}}; this.textContent = ''; this.innerHTML = ''; this.value = ''; }}
              setAttribute(name, value) {{ this.attributes[name] = String(value); }}
              getAttribute(name) {{ return this.attributes[name] ?? null; }}
              addEventListener() {{}}
              focus() {{}}
              querySelector() {{ return null; }}
              querySelectorAll() {{ return []; }}
            }}
            const elements = new Map();
            const getElement = id => {{ if (!elements.has(id)) elements.set(id, new Element(id)); return elements.get(id); }};
            globalThis.document = {{ getElementById: getElement, querySelector: () => null, querySelectorAll: () => [] }};
            globalThis.fetch = async () => {{ throw new Error('fetch should not run in this harness'); }};
            eval({json.dumps(source)});
            const api = globalThis.__repairTest;
            const definitions = [
              {{repair_key: 'calibration-report-units-v3', title: 'Fix headings and units', description: 'Units.', artifact_scope: 'Calibration Report (Word and PDF)'}},
              {{repair_key: 'calibration-report-footer-layout-v1', title: 'Keep text clear of the footer', description: 'Footer.', artifact_scope: 'Calibration Report (Word and PDF)'}},
              {{repair_key: 'calibration-complete-fields-v1', title: 'Restore cut-off text', description: 'Text.', artifact_scope: 'Calibration Report and its certificates'}},
            ];
            const candidate = (key, id, status, extra) => Object.assign({{repair_key: key, candidate_id: id, source_file_id: id, status, title: definitions.find(d => d.repair_key === key).title, filename: 'CALIBRATION_REPORT_Shimadzu_Client_' + id + '.docx', repair_version: 'calibration-report-complete-fields-v5', footer_reserve_twips: 3600, bulk_safe: status === 'repairable' && key !== 'calibration-report-footer-layout-v1', reason: status === 'blocked' ? 'The saved file is missing.' : ''}}, extra || {{}});
            api.renderRepairInventory({{definitions, candidates: [
              candidate('calibration-report-units-v3', 1, 'already_repaired'),
              candidate('calibration-complete-fields-v1', 2, 'blocked'),
              candidate('calibration-report-footer-layout-v1', 3, 'repairable'),
              candidate('calibration-complete-fields-v1', 5, 'repairable', {{detected_fields: [{{label: 'Client / facility name'}}]}}),
            ]}});
            // Every registered repair type is selectable, including the footer repair.
            const typeOptions = getElement('calibration-center-repair-type-filter').innerHTML;
            definitions.forEach(d => assert.ok(typeOptions.includes('value="' + d.repair_key + '"'), d.repair_key));
            // The list opens on records needing action, ready ones first; completed ones are filtered out.
            assert.strictEqual(api.repairList.status, 'attention');
            const page = api.repairListPage(api.state.repairCandidates);
            assert.deepStrictEqual(page.items.map(item => item.status), ['repairable', 'repairable', 'blocked']);
            api.repairList.status = 'all';
            assert.strictEqual(api.repairListPage(api.state.repairCandidates).total, 4);
            api.repairList.status = 'attention';
            const body = getElement('calibration-center-repair-table-body').innerHTML;
            assert.ok(body.includes('Client / facility name'));
            assert.ok(body.includes('The saved file is missing.'));
            assert.ok(body.includes('Ready to repair') && body.includes('Cannot be repaired'));
            for (const jargon of ['twips', '3600', 'Repair version', 'complete-fields-v5', 'Review repair', 'Needs review']) assert.ok(!body.includes(jargon), jargon);
            assert.strictEqual((body.match(/js-calibration-repair/g) || []).length, 2);
            // Repair All covers only the repairs marked safe to run together.
            assert.deepStrictEqual(api.bulkCandidates().map(item => item.candidate_id), [5]);
            assert.strictEqual(getElement('calibration-center-repair-all').textContent, 'Repair All (1)');
            // An approved row offers Repair only when its report has a repair ready.
            assert.ok(api.repairButton({{repair_source_file_id: 5, repair_status: 'available'}}).includes('js-calibration-repair'));
            assert.ok(api.repairButton({{repair_source_file_id: 5, repair_status: 'update_available'}}).includes('Repair again'));
            assert.strictEqual(api.repairButton({{repair_source_file_id: 1, repair_status: 'available'}}), '');
            assert.strictEqual(api.repairButton({{repair_source_file_id: 2, repair_status: 'available'}}), '');
            assert.strictEqual(api.repairButton({{repair_source_file_id: null, repair_status: 'unavailable'}}), '');
            // Paging stays short however many pages exist.
            assert.deepStrictEqual(api.pageWindow(15, 30), [1, 13, 14, 15, 16, 17, 30]);
            assert.deepStrictEqual(api.pageWindow(1, 2), [1, 2]);
            console.log('repair list behaviour: PASS');
        """)
        with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8', delete=False) as script_file:
            script_file.write(node_script)
            script_path = script_file.name
        try:
            result = subprocess.run(['node', script_path], cwd=ROOT, capture_output=True, text=True, check=False)
        finally:
            pathlib.Path(script_path).unlink(missing_ok=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertIn('repair list behaviour: PASS', result.stdout)

    def test_single_record_lookup_does_not_scan_every_report(self):
        source_file = SimpleNamespace(id=77)
        lookup = MagicMock(return_value={'candidate_id': 77, 'source_file_id': 77, 'status': 'repairable'})
        key = 'calibration-report-footer-layout-v1'
        with patch.dict(app_module.CALIBRATION_REPAIR_REGISTRY[key], {'candidate_for_file': lookup}), \
                patch.object(app_module.db.session, 'get', return_value=source_file), \
                patch.object(app_module, '_calibration_repair_source_files', side_effect=AssertionError('full scan')):
            definition, candidate = app_module._calibration_repair_registry_candidate(key, 77)
        lookup.assert_called_once_with(source_file)
        self.assertEqual(candidate['repair_key'], key)
        self.assertEqual(candidate['title'], definition['title'])
        self.assertFalse(candidate['bulk_safe'])

    def test_repair_scan_reads_each_stored_file_once_per_report(self):
        source_file = SimpleNamespace(id=31)
        reads = []

        def read_source(file_record):
            reads.append(file_record.id)
            return b'docx-bytes'

        def candidate_for_file(file_record):
            app_module._calibration_report_source_bytes(file_record)
            return {'source_file_id': file_record.id, 'status': 'repairable'}

        definition = {'version': 'v', 'title': 't', 'description': 'd', 'artifact_scope': 's', 'bulk_safe': True, 'candidate_for_file': candidate_for_file}
        registry = {'first': dict(definition), 'second': dict(definition), 'third': dict(definition)}
        with patch.dict(app_module.CALIBRATION_REPAIR_REGISTRY, registry, clear=True), \
                patch.object(app_module, '_calibration_report_read_source_bytes', side_effect=read_source):
            candidates = app_module._calibration_repair_file_candidates(source_file)
            self.assertEqual([item['repair_key'] for item in candidates], ['first', 'second', 'third'])
            self.assertEqual(reads, [31])
            # Outside a scan nothing is held, so applying a repair always reads the current file.
            app_module._calibration_report_source_bytes(source_file)
            self.assertEqual(reads, [31, 31])

    def test_data_route_filters_ready_and_unavailable_records(self):
        records = {
            1: {'approval_id': 1, 'can_send': True, 'delivery_state': 'sent'},
            2: {'approval_id': 2, 'can_send': False, 'delivery_state': 'unsent'},
            3: {'approval_id': 3, 'can_send': True, 'delivery_state': 'unsent'},
        }
        approvals = MagicMock()
        approvals.query.options.return_value.filter.return_value.order_by.return_value.all.return_value = [1, 2, 3]

        def fetch(delivery):
            with app_module.app.test_request_context(f'/admin/calibration-center/data?delivery={delivery}'), \
                    patch.object(app_module, 'can_access_calibration_center', return_value=True), \
                    patch.object(app_module, 'ensure_calibration_certificate_approval_table'), \
                    patch.object(app_module, 'CalibrationCertificateApproval', approvals), \
                    patch.object(app_module, 'joinedload'), \
                    patch.object(app_module, '_calibration_center_record', side_effect=lambda approval: dict(records[approval])):
                response = app_module.calibration_center_data.__wrapped__()
            return response.get_json()

        self.assertEqual([item['approval_id'] for item in fetch('unavailable')['records']], [2])
        self.assertEqual([item['approval_id'] for item in fetch('ready')['records']], [1, 3])
        self.assertEqual([item['approval_id'] for item in fetch('unsent')['records']], [2, 3])
        data = fetch('all')
        self.assertEqual(data['summary'], {'approved': 3, 'ready': 2, 'unavailable': 1, 'unsent': 2, 'partial': 0, 'sent': 1})
        self.assertNotIn('approved', data)

    def test_service_worker_uses_v158_network_first_center_prefix(self):
        self.assertIn('medical-service-pwa-offline-navigation-v158-calibration-center', APP_SOURCE)
        self.assertIn("medical-service-pwa-offline-navigation-v195-pre-submission-calibration-report';", APP_SOURCE)
        self.assertIn("'/admin/calibration-center'", APP_SOURCE)
        self.assertIn('NETWORK_FIRST_AUTHENTICATED_PREFIXES', APP_SOURCE)
        page_route = APP_SOURCE.split("@app.route('/admin/calibration-center')", 1)[1].split(
            "@app.route('/admin/calibration-center/data'", 1
        )[0]
        self.assertIn("response.headers['Cache-Control']", page_route)

    def test_release_manifest_contains_admins_item(self):
        releases = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))
        matching = [
            item
            for release in releases['releases']
            for item in release.get('items', [])
            if 'calibration-center' in str(item.get('item_key', ''))
        ]
        self.assertTrue(matching)
        self.assertTrue(any('admins' in item.get('audiences', []) for item in matching))
        self.assertTrue(any(item.get('item_key') == '2026-09-25-calibration-center-repair-notice-admins' for item in matching))

    def test_registry_contract_and_complete_field_apply_guards_are_present(self):
        for marker in (
            'CALIBRATION_REPAIR_REGISTRY',
            'register_calibration_repair',
            "'calibration-report-units-v3'",
            "'calibration-report-footer-layout-v1'",
            "'calibration-complete-fields-v1'",
            "@app.route('/admin/calibration-center/repairs')",
            "@app.route('/admin/calibration-center/repairs/<repair_key>/<int:candidate_id>')",
            "@app.route('/admin/calibration-center/repairs/<repair_key>/<int:candidate_id>/apply'",
            'bulk_safe',
            'before_pdf_hash',
            'before_certificate_hash',
            'calibration_repair_applied',
            'rollback_warning',
            'source_values_unchanged',
            'mapped_snapshot_unchanged',
            'service_engineer_signature_preserved',
            'approver_signature_preserved',
        ):
            self.assertIn(marker, APP_SOURCE)
        self.assertNotIn('CALIBRATION_REPORT_REPAIR_MANUAL_FIELDS', APP_SOURCE)
        self.assertNotIn('_calibration_report_set_field_values', APP_SOURCE)
        for marker in (
            '/admin/calibration-center/repairs',
            'buildRepairDocx',
            'What will change',
            'What stays the same',
            "app-calibration-report.js') }}?v=43",
        ):
            self.assertIn(marker, TEMPLATE_SOURCE)
        self.assertIn('mapped_data_json', APP_SOURCE)
        self.assertIn("'bulk_safe': bool(definition.get('bulk_safe')) and item.get('status') == 'repairable'", APP_SOURCE)
        self.assertNotIn('data-repair-field', TEMPLATE_SOURCE)
        self.assertNotIn('fields_json', TEMPLATE_SOURCE)
        for repair_key, definition in app_module.CALIBRATION_REPAIR_REGISTRY.items():
            self.assertTrue(callable(definition['inventory']), repair_key)
            self.assertTrue(callable(definition['candidate_for_file']), repair_key)
            # Titles and descriptions are shown to administrators as written.
            for wording in (definition['title'], definition['description'], definition['artifact_scope']):
                self.assertNotRegex(wording, r'DOCX|immutable|artifact|deterministic|legacy', repair_key)
            self.assertTrue(callable(definition['apply']), repair_key)
            self.assertTrue(definition['audit'], repair_key)
            self.assertTrue(definition['idempotency'], repair_key)
            self.assertIn(definition['bulk_safe'], (True, False), repair_key)
        self.assertTrue(app_module.CALIBRATION_REPAIR_REGISTRY['calibration-complete-fields-v1']['bulk_safe'])
        footer_definition = app_module.CALIBRATION_REPAIR_REGISTRY['calibration-report-footer-layout-v1']
        self.assertEqual(footer_definition['version'], app_module.CALIBRATION_REPORT_FOOTER_LAYOUT_REPAIR_VERSION)
        self.assertFalse(footer_definition['bulk_safe'])
        self.assertEqual(app_module.CALIBRATION_REPORT_FOOTER_RESERVE_TWIPS, 3600)

    def test_registered_footer_repair_denies_without_center_authority(self):
        with app_module.app.test_request_context(
            '/admin/calibration-center/repairs/calibration-report-footer-layout-v1/1/apply',
            method='POST',
            json={},
        ), patch.object(app_module, 'can_access_calibration_center', return_value=False):
            response = app_module.calibration_center_repair_apply_registered.__wrapped__(
                'calibration-report-footer-layout-v1', 1
            )
        self.assertEqual(response[1], 403)

    def test_approved_record_repair_button_opens_deterministic_context(self):
        repair_button = TEMPLATE_SOURCE.split('const repairButton = (record) =>', 1)[1].split(
            'const actionsHtml', 1
        )[0]
        self.assertIn('repairableFor(record.repair_source_file_id)', repair_button)
        self.assertIn('js-calibration-repair', repair_button)
        self.assertIn('openRepair(repair.dataset.repairKey, Number(repair.dataset.candidateId))', TEMPLATE_SOURCE)

    def test_complete_fields_repair_uses_readable_relevant_targets(self):
        detected = app_module._calibration_report_repair_walk_values({
            'facility': {'address': 'A' * 40},
            'mechanical_checks': [{'criteria': 'C' * 231, 'result': 'R' * 60}],
            'auto_fill': {'fields': ['M' * 36]},
        }, output=[])
        self.assertEqual(
            [item['path'] for item in detected],
            ['facility.address', 'mechanical_checks.0.result'],
        )
        self.assertEqual(
            app_module._calibration_report_repair_field_label('facility.address'),
            'Client / facility address',
        )
        for marker in (
            'What will change',
            'What stays the same',
            'File details',
            'item.label',
            'item.artifact_label',
            'item.issue_label',
        ):
            self.assertIn(marker, TEMPLATE_SOURCE)
        render_context = TEMPLATE_SOURCE.split('function repairChanges(candidate)', 1)[1].split(
            'function repairChangeSummary', 1
        )[0]
        self.assertNotIn("item.path || 'saved field'", render_context)

    def test_complete_fields_repair_recovers_legacy_address_from_saved_tsr(self):
        truncated = 'M.L. Quezon Avenue Extension Dalig, Anti'
        complete = 'M.L. Quezon Avenue Extension Dalig, Antipolo City'
        payload = {
            'tsr-address': complete,
            'calibration_report': {'facility': {'address': truncated}},
        }
        resolved, recovered = app_module._calibration_report_resolved_repair_payload(payload)
        self.assertEqual(resolved['calibration_report']['facility']['address'], complete)
        self.assertEqual(recovered, {'facility.address': 'Saved TSR address'})
        self.assertEqual(payload['calibration_report']['facility']['address'], truncated)

        unrelated, recovered = app_module._calibration_report_resolved_repair_payload({
            'tsr-address': 'A different address that must not be substituted automatically',
            'calibration_report': {'facility': {'address': truncated}},
        })
        self.assertEqual(unrelated['calibration_report']['facility']['address'], truncated)
        self.assertEqual(recovered, {})

    def test_complete_fields_repair_recovers_legacy_certificate_mapping_from_report_snapshot(self):
        complete = 'Allied Care Experts (ACE) Medical Center - Cagayan De Oro'
        truncated = complete[:40].rstrip()
        payload = {
            'tsr-customer-name': complete,
            'tsr-number': 'TSR-20260923-01-KM',
            'calibration_report': {
                'facility': {'name': truncated},
                'machine': {
                    'modality': 'Digital Radiography System',
                    'model': 'MobileDart Evolution MX8',
                    'serial_number': 'MQ6B6FBAA001',
                },
            },
        }
        resolved, recovered = app_module._calibration_report_resolved_repair_payload(payload)
        mapped = {
            'Textfield': '2026-0923-B-42',
            'Text1': 'Digital Radiography System',
            'Text2': 'MobileDart Evolution MX8',
            'Text3': 'MQ6B6FBAA001',
            'Text4': '2026/09/23',
            'Text5': '2027/09/23',
            'Text6': truncated,
            'Textfield-0': 'TSR-20260923-01-KM',
        }
        values, certificate_recovered, blocked = app_module._calibration_report_resolved_certificate_mapping(
            resolved,
            mapped,
        )
        self.assertEqual(values['Text6'], complete)
        self.assertEqual(certificate_recovered, {'Text6': 'Saved report client name'})
        self.assertEqual(blocked, [])
        self.assertIn('facility.name', recovered)
        self.assertEqual(mapped['Text6'], truncated)

    def test_complete_fields_repair_blocks_conflicting_certificate_mapping(self):
        payload = {
            'calibration_report': {'facility': {'name': 'A' * 57}},
        }
        values, recovered, blocked = app_module._calibration_report_resolved_certificate_mapping(
            payload,
            {
                'Textfield': 'CERT-1', 'Text1': 'Equipment', 'Text2': 'Model',
                'Text3': 'Serial', 'Text4': '2026/09/23', 'Text5': '2027/09/23',
                'Text6': 'B' * 40, 'Textfield-0': 'TSR-1',
            },
        )
        self.assertEqual(values['Text6'], 'B' * 40)
        self.assertEqual(recovered, {})
        self.assertIn('Text6', blocked[0])

    def test_complete_fields_repair_recovers_legacy_console_model_from_saved_model(self):
        truncated = 'MobileDart Evolution M'
        complete = 'MobileDart Evolution MX8 Version'
        payload = {
            'tsr-equipment-model': complete,
            'calibration_report': {
                'machine': {
                    'model': complete,
                    'console_model': truncated,
                },
            },
        }
        resolved, recovered = app_module._calibration_report_resolved_repair_payload(payload)
        self.assertEqual(resolved['calibration_report']['machine']['console_model'], complete)
        self.assertEqual(recovered['machine.console_model'], 'Saved report equipment model')
        self.assertEqual(payload['calibration_report']['machine']['console_model'], truncated)

    def test_console_model_recovery_accepts_saved_parenthesized_suffix(self):
        truncated = 'MobileDart Evolution M'
        complete = 'MobileDart Evolution (MX8)'
        payload = {
            'tsr-equipment-model': complete,
            'calibration_report': {'machine': {'model': complete, 'console_model': truncated}},
        }
        resolved, recovered = app_module._calibration_report_resolved_repair_payload(payload)
        self.assertEqual(resolved['calibration_report']['machine']['console_model'], complete)
        self.assertIn('machine.console_model', recovered)
        self.assertEqual(payload['calibration_report']['machine']['console_model'], truncated)
        with patch.object(app_module, '_calibration_report_pdf_text', return_value=complete):
            app_module._calibration_report_pdf_contains_saved_values(
                b'pdf', resolved, [{'path': 'machine.console_model'}],
            )
        with patch.object(app_module, '_calibration_report_pdf_text', return_value=truncated):
            with self.assertRaisesRegex(ValueError, 'machine.console_model'):
                app_module._calibration_report_pdf_contains_saved_values(
                    b'pdf', resolved, [{'path': 'machine.console_model'}],
                )
        payload['calibration_report']['machine']['model'] = 'MobileDart Evolution (VX8)'
        payload['tsr-equipment-model'] = 'MobileDart Evolution (VX8)'
        resolved, recovered = app_module._calibration_report_resolved_repair_payload(payload)
        self.assertEqual(resolved['calibration_report']['machine']['console_model'], truncated)
        self.assertNotIn('machine.console_model', recovered)

    def test_complete_fields_repair_checks_recovered_value_in_pdf(self):
        payload = {'calibration_report': {'facility': {'address': 'Complete saved address'}}}
        fields = [{'path': 'facility.address'}]
        with patch.object(app_module, '_calibration_report_pdf_text', return_value='Complete\nsaved address'):
            app_module._calibration_report_pdf_contains_saved_values(b'pdf', payload, fields)
        with patch.object(app_module, '_calibration_report_pdf_text', return_value='Incomplete address'):
            with self.assertRaisesRegex(ValueError, 'facility.address'):
                app_module._calibration_report_pdf_contains_saved_values(b'pdf', payload, fields)

    def test_calibration_center_row_shows_repair_history_status(self):
        self.assertEqual(
            app_module.CALIBRATION_REPORT_COMPLETE_FIELDS_REPAIR_VERSION,
            'calibration-report-complete-fields-v5',
        )
        for marker in (
            'repair_status',
            'repair_history_count',
            'repair_last_at',
            'update_available',
            'Repair again',
            'Repaired ',
        ):
            self.assertIn(marker, APP_SOURCE + TEMPLATE_SOURCE)

    def test_complete_fields_repair_accepts_only_artifact_inputs(self):
        self.assertIn("'fields_json'", APP_SOURCE)
        apply_block = APP_SOURCE.split('def _calibration_report_apply_complete_fields_repair', 1)[1].split(
            'def register_calibration_repair', 1
        )[0]
        self.assertIn("'fields', 'fields_json', 'field_values', 'corrected_values', 'report_payload'", apply_block)
        self.assertIn('calibration_certificate_mapped_snapshot', apply_block)
        self.assertNotIn('approval.mapped_data_json =', apply_block)
        self.assertNotIn('_update_calibration_report_conversion_marker(source_file, pdf_job, pdf_file)', apply_block)

    def test_complete_fields_apply_rejects_replacement_values(self):
        source = SimpleNamespace(id=91, online_tsr_submission_id=92, shift_id=93)
        candidate = {
            'status': 'repairable',
            'source_sha256': 'source-hash',
            'pdf_sha256': '',
            'certificate_sha256': '',
        }
        with patch.object(app_module.db.session, 'get', return_value=source), \
                patch.object(app_module, 'calibration_report_source_file_is_private', return_value=True), \
                patch.object(app_module, '_calibration_report_complete_fields_context', return_value=candidate):
            result = app_module._calibration_report_apply_complete_fields_repair(
                91,
                {
                    'before_hash': 'source-hash',
                    'fields_json': '{"facility.address":"changed"}',
                    'confirmation': 'REPAIR',
                },
                None,
            )

        self.assertEqual(result['status'], 'failed')
        self.assertIn('does not accept replacement', result['message'])


if __name__ == '__main__':
    unittest.main()
