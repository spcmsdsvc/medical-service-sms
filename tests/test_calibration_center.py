"""Focused contracts for the admin-only Calibration Center package.

This module is intentionally added before the implementation for the required
fail-first checkpoint.  It uses source and route contracts for the new surface,
then exercises the pure manifest/recipient helpers once they exist.  No browser
or repository scheduler.db access is performed.
"""

import json
import pathlib
import unittest
from unittest.mock import patch

import app as app_module


ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / 'app.py').read_text(encoding='utf-8')
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

    def test_center_cc_helper_reads_only_calibration_group(self):
        with patch.object(app_module, 'get_active_email_recipients_by_group', return_value=['internal@example.test']) as resolver:
            self.assertEqual(
                app_module.get_calibration_report_certificate_cc_emails(),
                ['internal@example.test'],
            )
            resolver.assert_called_once_with('calibration_report_certificate_cc')

    def test_strict_center_authority_and_all_routes_are_declared(self):
        self.assertIn('def can_access_calibration_center(user=None):', APP_SOURCE)
        self.assertIn("@app.route('/admin/calibration-center'", APP_SOURCE)
        self.assertIn("@app.route('/admin/calibration-center/data'", APP_SOURCE)
        self.assertIn("@app.route('/admin/calibration-center/<int:approval_id>/email'", APP_SOURCE)
        self.assertIn("@app.route('/admin/calibration-center/<int:approval_id>/email-preview'", APP_SOURCE)
        self.assertIn("@app.route('/admin/calibration-center/<int:approval_id>/send-email'", APP_SOURCE)

    def test_center_query_is_current_approved_only_and_paginated(self):
        self.assertIn("CalibrationCertificateApproval.status == 'Approved'", APP_SOURCE)
        self.assertIn('CalibrationCertificateApproval.is_latest.is_(True)', APP_SOURCE)
        self.assertIn('per_page = 10', APP_SOURCE)
        self.assertIn("'delivery'", APP_SOURCE)
        self.assertIn("'unavailable_reason'", APP_SOURCE)

    def test_fixed_pair_and_calibration_cc_are_server_owned(self):
        self.assertIn('def get_calibration_center_email_artifacts(', APP_SOURCE)
        self.assertIn('def prepare_calibration_center_email_message(', APP_SOURCE)
        self.assertIn("get_active_email_recipients_by_group('calibration_report_certificate_cc')", APP_SOURCE)
        self.assertIn("'calibration_report'", APP_SOURCE)
        self.assertIn("'calibration_certificate'", APP_SOURCE)
        self.assertIn('attachments_changed', APP_SOURCE)

    def test_settings_group_and_sidebar_contracts(self):
        self.assertIn("'calibration_report_certificate_cc'", APP_SOURCE)
        self.assertIn("nav_can_access_calibration_center", APP_SOURCE)
        self.assertIn('/admin/calibration-center', LAYOUT_SOURCE)
        self.assertIn('Calibration Center', LAYOUT_SOURCE)
        self.assertIn('calibration_report_certificate_cc', SETTINGS_SOURCE)

    def test_template_contains_required_safe_states_and_controls(self):
        template = (ROOT / 'templates' / 'calibration_center.html').read_text(encoding='utf-8')
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
            'Confirm',
        ):
            self.assertIn(marker, template)

    def test_service_worker_uses_v158_network_first_center_prefix(self):
        self.assertIn('medical-service-pwa-offline-navigation-v158-calibration-center', APP_SOURCE)
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


if __name__ == '__main__':
    unittest.main()
