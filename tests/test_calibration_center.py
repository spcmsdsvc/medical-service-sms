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
import textwrap
import unittest
from types import SimpleNamespace
from unittest.mock import patch

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
        self.assertIn("@app.route('/admin/calibration-center/repair-preview'", APP_SOURCE)
        self.assertIn("@app.route('/admin/calibration-center/<int:source_file_id>/repair'", APP_SOURCE)
        repair_preview_block = APP_SOURCE.split("@app.route('/admin/calibration-center/repair-preview'", 1)[1].split(
            "@app.route('/admin/calibration-center/<int:source_file_id>/repair'", 1
        )[0]
        repair_apply_block = APP_SOURCE.split("@app.route('/admin/calibration-center/<int:source_file_id>/repair'", 1)[1].split(
            "def calibration_report_certificate_cc_group_for_branch", 1
        )[0]
        self.assertNotIn('@csrf.exempt', repair_preview_block)
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
            'Confirm',
            'Historical Report Repair',
            'Repair All',
            'REPAIR ALL',
            'repair-preview',
            'repairRunning',
            'candidate.target_units',
            'candidate.unit_sources',
            'Target units / source',
        ):
            self.assertIn(marker, template)

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
        self.assertIn('All historical report repairs are complete', TEMPLATE_SOURCE)
        self.assertIn('calibration-center-repair-load-error', TEMPLATE_SOURCE)
        self.assertIn('Inventory could not be loaded', TEMPLATE_SOURCE)
        self.assertIn('setVisible(\'calibration-center-repair-area\', true)', TEMPLATE_SOURCE)

    def test_historical_repair_details_keep_existing_actions(self):
        for marker in (
            'calibration-center-repair-warning',
            'calibration-center-repair-summary',
            'calibration-center-repair-table-wrap',
            'calibration-center-repair-confirm',
            'calibration-center-repair-all',
            'js-calibration-repair',
            '`/admin/calibration-center/${sourceFileId}/repair`',
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
        result = subprocess.run(['node', '-e', node_script], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertIn('repair surface states: PASS', result.stdout)

    def test_service_worker_uses_v158_network_first_center_prefix(self):
        self.assertIn('medical-service-pwa-offline-navigation-v158-calibration-center', APP_SOURCE)
        self.assertIn("medical-service-pwa-offline-navigation-v194-calibration-repair-notice';", APP_SOURCE)
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


if __name__ == '__main__':
    unittest.main()
