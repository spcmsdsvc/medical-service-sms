"""Focused server-side checks for the Calibration Certificate workflow.

The test process pins an external disposable SQLite path before importing the
application. It never opens or mutates the repository's scheduler.db.
"""

import hashlib
import io
import json
import os
import pathlib
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from pypdf import PdfReader

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB = pathlib.Path(tempfile.gettempdir()) / f"medical_service_calibration_certificate_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB))
os.environ.setdefault("SECRET_KEY", "calibration-certificate-test-only")

import app as app_module  # noqa: E402


SIGNATURE = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAHgAAAAeCAYAAADnydqVAAAAVElEQVR42u3WsQkAMAwEsdt/"
    "aWeDlMEEHfwCVuNGX5cTABZgARZgARZgAQYswAIswAKsJ8CVLRtgwIABy5MlwAIswAIswIA"
    "FWIAFWIAFWIAFWJcOqjWBWhan81EAAAAASUVORK5CYII="
)


def complete_payload():
    return {
        "tsr-number": "TSR-77",
        "calibration_report": {
            "certificate": {"bsid": " B-43 "},
            "facility": {"name": "St. Mary's Clinic"},
            "machine": {"modality": "Digital Angiography System", "model": "Mobile Dart Evolution MX9", "serial_number": "SN-42"},
            "calibration": {
                "machine_calibration_date": "2026-08-20",
                "next_calibration_date": "2027-08-20",
            },
        },
    }


class CalibrationCertificateCatalogTests(unittest.TestCase):
    def _assert_catalog_loader_rejects(self, mutate, message):
        catalog_path = ROOT / 'static' / 'templates' / 'calibration-certificate' / 'calibration-certificate-catalog.json'
        catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
        mutate(catalog)
        with tempfile.TemporaryDirectory(prefix='calibration_certificate_catalog_') as temp_root:
            temp_path = pathlib.Path(temp_root) / 'catalog.json'
            temp_path.write_text(json.dumps(catalog, ensure_ascii=False), encoding='utf-8')
            with patch.object(app_module, 'CALIBRATION_CERTIFICATE_CATALOG_PATH', str(temp_path)):
                with self.assertRaisesRegex(RuntimeError, message):
                    app_module.calibration_certificate_catalog()

    def test_catalog_has_exact_reference_shape_and_source_metadata(self):
        catalog_path = ROOT / 'static' / 'templates' / 'calibration-certificate' / 'calibration-certificate-catalog.json'
        catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
        self.assertEqual(catalog['source_sha256'], '1AAB589266A30E6E70FE93E951C86C997D23B1EA1332373EE756E989A97A21BA')
        self.assertEqual(len(catalog['equipment_names']), 6)
        self.assertEqual(len(catalog['models']), 38)
        self.assertEqual(catalog['models'][9], 'Sonialvision G4 with CH-200M')
        self.assertEqual(catalog['models'][10], 'Flexavision HB')
        self.assertEqual(len({app_module.calibration_certificate_model_normalize(value) for value in catalog['equipment_names'] + catalog['models']}), 44)
        self.assertEqual(app_module.calibration_certificate_catalog(), {'equipment_names': catalog['equipment_names'], 'models': catalog['models']})
        payload = json.dumps(
            {'equipment_names': catalog['equipment_names'], 'models': catalog['models']},
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
        ).encode('utf-8')
        self.assertEqual(
            hashlib.sha256(payload).hexdigest().upper(),
            app_module.CALIBRATION_CERTIFICATE_CATALOG_PAYLOAD_SHA256,
        )

    def test_catalog_loader_rejects_non_string_raw_entry(self):
        self._assert_catalog_loader_rejects(
            lambda catalog: catalog['models'].__setitem__(0, 123),
            'must be strings',
        )

    def test_catalog_loader_rejects_unclean_raw_entry(self):
        self._assert_catalog_loader_rejects(
            lambda catalog: catalog['models'].__setitem__(0, ' Flexavision  F4 '),
            'unclean equipment model',
        )

    def test_catalog_loader_rejects_clean_altered_model_with_stale_or_forged_metadata(self):
        def alter_catalog(catalog):
            catalog['models'][0] = 'Trinias Unity Smart Altered'
            catalog['source_sha256'] = app_module.CALIBRATION_CERTIFICATE_CATALOG_SOURCE_SHA256
            catalog['catalog_payload_sha256'] = '0' * 64

        self._assert_catalog_loader_rejects(alter_catalog, 'canonical payload checksum')

    def test_python_matcher_accepts_normalized_variants_and_rejects_weak_or_ambiguous(self):
        self.assertEqual(app_module.calibration_certificate_model_match('Mobile Dart Evolution MX9')['value'], 'MobileDart Evolution MX9')
        self.assertEqual(app_module.calibration_certificate_model_match('CH-200M')['status'], 'ambiguous')
        self.assertEqual(app_module.calibration_certificate_model_match('zzzzzz')['status'], 'weak')
        malformed = app_module.calibration_certificate_catalog()
        malformed['models'][0] = '  malformed  '
        with self.assertRaises(RuntimeError):
            app_module.calibration_certificate_model_match('Trinias Unity Smart', catalog=malformed)
        errors, match = app_module.calibration_certificate_catalog_errors({
            'machine': {'modality': 'Digital Angiography System', 'model': 'zzzzzz'},
        })
        self.assertEqual(match['status'], 'weak')
        self.assertTrue(any('exact catalog Equipment Model' in error for error in errors))

    def test_approval_builder_can_render_immutable_legacy_mapped_snapshot(self):
        legacy = {
            'Textfield': '2026/08/20-B-43', 'Text1': 'Legacy Equipment', 'Text2': 'Legacy Model',
            'Text3': 'LEGACY-SN', 'Text4': '2026/08/20', 'Text5': '2027/08/20',
            'Text6': 'Legacy Clinic', 'Textfield-0': 'TSR-LEGACY',
        }
        payload = complete_payload()
        data, mapped, _ = app_module.build_calibration_certificate_pdf(
            payload,
            certificate_number_override=legacy['Textfield'],
            mapped_values_override=legacy,
        )
        self.assertEqual(mapped, legacy)
        text = '\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(data)).pages)
        for value in legacy.values():
            self.assertIn(value, text)


class CalibrationCertificateServerTests(unittest.TestCase):
    def test_submission_catalog_failure_is_retryable(self):
        app = app_module.app
        db = app_module.db
        catalog = json.loads((ROOT / 'static' / 'templates' / 'calibration-certificate' / 'calibration-certificate-catalog.json').read_text(encoding='utf-8'))
        catalog['models'][0] = 'Trinias Unity Smart Altered'
        catalog['catalog_payload_sha256'] = '0' * 64
        with tempfile.TemporaryDirectory(prefix='calibration_certificate_tampered_catalog_') as catalog_root, \
                tempfile.TemporaryDirectory(prefix='calibration_certificate_submission_storage_') as storage_root:
            catalog_path = pathlib.Path(catalog_root) / 'catalog.json'
            catalog_path.write_text(json.dumps(catalog, ensure_ascii=False), encoding='utf-8')
            with app.app_context(), app.test_request_context('/'):
                db.create_all()
                app_module.ensure_calibration_certificate_approval_table()
                user = app_module.User(
                    username=f'calibration_catalog_failure_{uuid.uuid4().hex[:8]}',
                    password='test-only', role='engineer',
                )
                db.session.add(user)
                db.session.flush()
                engineer = app_module.Engineer(
                    user_id=user.id, employee_id=f'CAT-{uuid.uuid4().hex[:8]}',
                    name='Catalog Engineer', initials='CA', branch='Manila',
                )
                client = app_module.Client(name=f'Catalog Failure Clinic {uuid.uuid4().hex[:8]}')
                db.session.add_all([engineer, client])
                db.session.flush()
                product = app_module.Product(
                    serial_number=f'CAT-{uuid.uuid4().hex[:8]}', name='X-Ray',
                    client_id=client.id, bsid=f'B-CAT-{uuid.uuid4().hex[:6]}',
                )
                db.session.add(product)
                db.session.flush()
                shift = app_module.Shift(
                    title='Catalog Failure', start_time=datetime.now(),
                    end_time=datetime.now() + timedelta(hours=1), engineer_id=engineer.id,
                    client_id=client.id, product_id=product.serial_number, status='Completed',
                )
                db.session.add(shift)
                db.session.flush()
                payload = complete_payload()
                payload['_generated_calibration_report'] = {'file_id': 1}
                submission = app_module.OnlineTsrSubmission(
                    shift_id=shift.id, tsr_number='TSR-CATALOG-FAIL', client_name=client.name,
                    product_name=product.name, serial_number=product.serial_number,
                    submitted_by_user_id=user.id, submitted_by_name=engineer.name,
                    status='completed', submission_token=f'catalog-fail-{uuid.uuid4().hex}',
                    payload_json=json.dumps(payload), revision_no=1, is_latest=True,
                )
                db.session.add(submission)
                db.session.commit()
                original_upload_folder = app.config.get('UPLOAD_FOLDER')
                app.config['UPLOAD_FOLDER'] = storage_root
                try:
                    with patch.object(app_module, 'CALIBRATION_CERTIFICATE_CATALOG_PATH', str(catalog_path)):
                        result = app_module.submit_calibration_certificate_for_submission(submission)
                finally:
                    app.config['UPLOAD_FOLDER'] = original_upload_folder
                self.assertFalse(result['ok'])
                self.assertEqual(result['code'], 'catalog_unavailable')
                self.assertTrue(result['retryable'])
                self.assertIn('canonical payload checksum', result['message'])
                self.assertIsNone(app_module.CalibrationCertificateApproval.query.filter_by(online_tsr_submission_id=submission.id).first())
                self.assertFalse(list(pathlib.Path(storage_root).glob('*')))
                db.session.remove()

    def test_offline_tsr_renders_unavailable_catalog_state_instead_of_500(self):
        with patch.object(app_module, 'can_back_up_tsr_drafts', return_value=True), \
                patch.object(app_module, 'get_email_template_value', return_value='TSR'), \
                patch.object(app_module, 'is_admin_authorized', return_value=False), \
                patch.object(app_module, 'calibration_certificate_catalog', side_effect=RuntimeError('missing catalog')), \
                patch.object(app_module, 'render_template', return_value='offline-rendered') as render:
            response = app_module.offline_tsr_page.__wrapped__()
        self.assertEqual(response, 'offline-rendered')
        catalog = render.call_args.kwargs['certificate_catalog']
        self.assertFalse(catalog['available'])
        self.assertEqual(catalog['equipment_names'], [])
        self.assertIn('unavailable', catalog['error'].lower())

    def test_incomplete_pending_snapshot_is_rejected_without_artifact_or_state_mutation(self):
        app = app_module.app
        db = app_module.db
        with tempfile.TemporaryDirectory(prefix='calibration_certificate_incomplete_snapshot_') as storage_root:
            original_upload_folder = app.config.get('UPLOAD_FOLDER')
            app.config['UPLOAD_FOLDER'] = storage_root
            try:
                with app.app_context(), app.test_request_context('/'):
                    db.create_all()
                    app_module.ensure_calibration_certificate_approval_table()
                    requester = app_module.User(
                        username=f'calibration_snapshot_requester_{uuid.uuid4().hex[:8]}',
                        password='test-only', role='engineer',
                    )
                    approver = app_module.User(
                        username=f'calibration_snapshot_approver_{uuid.uuid4().hex[:8]}',
                        password='test-only', role='superadmin', approval_title='Service Manager',
                    )
                    db.session.add_all([requester, approver])
                    db.session.flush()
                    requester_engineer = app_module.Engineer(
                        user_id=requester.id, employee_id=f'SNAP-REQ-{uuid.uuid4().hex[:8]}',
                        name='Snapshot Requester', initials='SR', branch='Manila',
                    )
                    approver_engineer = app_module.Engineer(
                        user_id=approver.id, employee_id=f'SNAP-APP-{uuid.uuid4().hex[:8]}',
                        name='Snapshot Approver', initials='SA', branch='Manila', signature_data=SIGNATURE,
                    )
                    client = app_module.Client(name=f'Snapshot Clinic {uuid.uuid4().hex[:8]}')
                    db.session.add_all([requester_engineer, approver_engineer, client])
                    db.session.flush()
                    product = app_module.Product(
                        serial_number=f'SNAP-{uuid.uuid4().hex[:8]}', name='X-Ray',
                        client_id=client.id, bsid=f'B-SNAP-{uuid.uuid4().hex[:6]}',
                    )
                    db.session.add(product)
                    db.session.flush()
                    shift = app_module.Shift(
                        title='Incomplete Snapshot', start_time=datetime.now(),
                        end_time=datetime.now() + timedelta(hours=1), engineer_id=requester_engineer.id,
                        client_id=client.id, product_id=product.serial_number, status='Completed',
                    )
                    db.session.add(shift)
                    db.session.flush()
                    submission = app_module.OnlineTsrSubmission(
                        shift_id=shift.id, tsr_number='TSR-SNAPSHOT', client_name=client.name,
                        product_name=product.name, serial_number=product.serial_number,
                        submitted_by_user_id=requester.id, submitted_by_name=requester_engineer.name,
                        status='completed', submission_token=f'snapshot-{uuid.uuid4().hex}',
                        payload_json=json.dumps(complete_payload()), revision_no=1, is_latest=True,
                    )
                    db.session.add(submission)
                    db.session.flush()
                    approval = app_module.CalibrationCertificateApproval(
                        shift_id=shift.id, online_tsr_submission_id=submission.id,
                        requester_user_id=requester.id, revision_no=1, is_latest=True,
                        status='Pending', certificate_number='2026/08/20-B-43',
                        mapped_data_json=json.dumps({'Textfield':'2026/08/20-B-43', 'Text1':'Legacy Equipment'}),
                        template_sha256=app_module.CALIBRATION_CERTIFICATE_RUNTIME_SHA256,
                        unsigned_artifact_path='missing-unsigned.pdf', submitted_at=datetime.now(),
                        created_at=datetime.now(), updated_at=datetime.now(),
                    )
                    db.session.add(approval)
                    db.session.commit()
                    app_module.login_user(approver)
                    with patch.object(app_module, 'calibration_certificate_approver_can_act', return_value=True), \
                            patch.object(app_module, 'approval_signature_required_response', return_value=None), \
                            patch.object(app_module, 'build_calibration_certificate_pdf', side_effect=AssertionError('PDF builder must not run')):
                        response = app_module.approve_calibration_certificate(approval.id)
                    if isinstance(response, tuple):
                        response, status_code = response
                    else:
                        status_code = response.status_code
                    body = response.get_json()
                    self.assertEqual(status_code, 400)
                    self.assertFalse(body['success'])
                    self.assertTrue(body.get('retryable'))
                    self.assertIn('complete', body['message'].lower())
                    db.session.refresh(approval)
                    self.assertEqual(approval.status, 'Pending')
                    self.assertIsNone(approval.signed_shift_file_id)
                    self.assertFalse(list(pathlib.Path(storage_root).glob('*')))
                    app_module.logout_user()
            finally:
                app.config['UPLOAD_FOLDER'] = original_upload_folder
                with app.app_context():
                    db.session.remove()


class CalibrationCertificateReportApprovalLinkTests(unittest.TestCase):
    def _create_fixture(self):
        app = app_module.app
        db = app_module.db
        with app.app_context():
            db.create_all()
            suffix = uuid.uuid4().hex[:10]
            requester = app_module.User(
                username=f'calibration_report_requester_{suffix}',
                password='test-only', role='engineer',
            )
            approver = app_module.User(
                username=f'calibration_report_approver_{suffix}',
                password='test-only', role='approver', can_approve_requests=True,
            )
            administrator = app_module.User(
                username=f'calibration_report_admin_{suffix}',
                password='test-only', role='superadmin',
            )
            unauthorized = app_module.User(
                username=f'calibration_report_unauthorized_{suffix}',
                password='test-only', role='engineer',
            )
            db.session.add_all([requester, approver, administrator, unauthorized])
            db.session.flush()
            engineer = app_module.Engineer(
                user_id=requester.id,
                employee_id=f'CAL-REPORT-{suffix}',
                name='Calibration Report Requester',
                initials='CR',
                branch='Manila',
            )
            client = app_module.Client(name=f'Calibration Report Clinic {suffix}')
            db.session.add_all([engineer, client])
            db.session.flush()
            product = app_module.Product(
                serial_number=f'CAL-REPORT-{suffix}',
                name='Calibration Report Machine',
                client_id=client.id,
                bsid=f'B-CAL-REPORT-{suffix}',
            )
            db.session.add(product)
            db.session.flush()
            shift = app_module.Shift(
                title='Calibration Report Approval',
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(hours=1),
                engineer_id=engineer.id,
                client_id=client.id,
                product_id=product.serial_number,
                status='Completed',
            )
            db.session.add(shift)
            db.session.flush()
            report_name = f'Calibration Report {suffix}.docx'
            disk_name = f'shift_{shift.id}_{uuid.uuid4().hex[:16]}_calibration_report.docx'
            report_file = app_module.ShiftFile(
                shift_id=shift.id,
                filename=disk_name,
                original_filename=report_name,
            )
            db.session.add(report_file)
            db.session.flush()
            payload = complete_payload()
            payload['_generated_calibration_report'] = {
                'source': 'generated_calibration_report',
                'file_id': report_file.id,
                'filename': report_name,
                'fingerprint': f'fingerprint-{suffix}',
            }
            submission = app_module.OnlineTsrSubmission(
                shift_id=shift.id,
                tsr_number=f'TSR-CAL-REPORT-{suffix}',
                client_name=client.name,
                product_name=product.name,
                serial_number=product.serial_number,
                submitted_by_user_id=requester.id,
                submitted_by_name=engineer.name,
                status='completed',
                submission_token=f'calibration-report-{suffix}',
                payload_json=json.dumps(payload),
                revision_no=1,
                is_latest=True,
            )
            db.session.add(submission)
            db.session.flush()
            report_file.online_tsr_submission_id = submission.id
            approval = app_module.CalibrationCertificateApproval(
                shift_id=shift.id,
                online_tsr_submission_id=submission.id,
                requester_user_id=requester.id,
                revision_no=1,
                is_latest=True,
                status='Pending',
                certificate_number=f'2026/{suffix}-B-43',
                mapped_data_json=json.dumps({'Textfield': f'2026/{suffix}-B-43'}),
                template_sha256=app_module.CALIBRATION_CERTIFICATE_RUNTIME_SHA256,
                unsigned_artifact_path=f'calibration-certificates/{suffix}.pdf',
            )
            db.session.add(approval)
            db.session.commit()
            fixture = {
                'approval_id': approval.id,
                'file_id': report_file.id,
                'shift_id': shift.id,
                'submission_id': submission.id,
                'report_name': report_name,
                'disk_name': disk_name,
                'requester_id': requester.id,
                'approver_id': approver.id,
                'administrator_id': administrator.id,
                'unauthorized_id': unauthorized.id,
            }
            db.session.remove()
            return fixture

    def _invoke_download(self, user_id, file_id, approval_id):
        app = app_module.app
        db = app_module.db
        request_path = (
            f'/download_tsr_archive_file/{file_id}'
            f'?scope=all&approval_id={approval_id}'
        )
        with app.app_context(), app.test_request_context(request_path):
            user = db.session.get(app_module.User, user_id)
            app_module.login_user(user)
            try:
                response = app_module.download_tsr_archive_file(file_id)
                response.direct_passthrough = False
                response.get_data()
                response.close()
                return response
            finally:
                app_module.logout_user()
                db.session.remove()

    def _download(self, fixture, user_id, storage_root, extra_file_id=None):
        path = pathlib.Path(storage_root) / fixture['disk_name']
        path.write_bytes(b'finalized calibration report docx bytes')
        file_id = extra_file_id or fixture['file_id']
        return self._invoke_download(user_id, file_id, fixture['approval_id'])

    def test_serializer_exposes_exact_report_filename_and_approval_scoped_url(self):
        fixture = self._create_fixture()
        with app_module.app.app_context(), app_module.app.test_request_context('/'):
            approval = app_module.db.session.get(
                app_module.CalibrationCertificateApproval,
                fixture['approval_id'],
            )
            item = app_module.calibration_certificate_approval_to_dict(approval)
            app_module.db.session.remove()

        self.assertEqual(item['calibration_report_filename'], fixture['report_name'])
        parsed = urlsplit(item['calibration_report_download_url'])
        self.assertEqual(parsed.path, f"/download_tsr_archive_file/{fixture['file_id']}")
        self.assertEqual(
            parse_qs(parsed.query),
            {'scope': ['all'], 'approval_id': [str(fixture['approval_id'])]},
        )

    def test_approval_report_preview_uses_local_pinned_runtime_without_new_server_surface(self):
        template = (ROOT / 'templates' / 'approvals.html').read_text(encoding='utf-8')
        renderer = ROOT / 'static' / 'vendor' / 'docx-preview' / 'docx-preview.min.js'
        license_path = ROOT / 'static' / 'vendor' / 'docx-preview' / 'LICENSE'
        self.assertTrue(renderer.is_file())
        self.assertTrue(license_path.is_file())
        renderer_source = renderer.read_text(encoding='utf-8')
        license_source = license_path.read_text(encoding='utf-8')
        self.assertIn('docx-preview <https://github.com/VolodymyrBaydalka/docxjs>', renderer_source)
        self.assertIn('renderAsync', renderer_source)
        self.assertIn('Apache License', license_source)
        self.assertIn('Version 2.0', license_source)
        self.assertIn('vendor/jszip/jszip.min.js', template)
        self.assertIn('vendor/docx-preview/docx-preview.min.js', template)
        self.assertIn('0.4.0', template)
        self.assertIn('calibration_report_download_url', template)
        app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        self.assertNotIn('vendor/docx-preview/docx-preview.min.js', app_source)
        self.assertIn('NETWORK_ONLY_DOWNLOAD_PREFIXES', app_source)

    def test_approval_scoped_download_allows_requester_approver_and_admin(self):
        fixture = self._create_fixture()
        app = app_module.app
        original_upload_folder = app.config.get('UPLOAD_FOLDER')
        with tempfile.TemporaryDirectory(prefix='calibration_report_approval_download_') as storage_root:
            app.config['UPLOAD_FOLDER'] = storage_root
            try:
                report_path = pathlib.Path(storage_root) / fixture['disk_name']
                report_path.write_bytes(b'finalized calibration report docx bytes')
                cases = (
                    ('requester', fixture['requester_id']),
                    ('approver', fixture['approver_id']),
                    ('administrator', fixture['administrator_id']),
                )
                for label, user_id in cases:
                    with self.subTest(label=label):
                        with patch.object(
                            app_module,
                            'calibration_certificate_requester_can_view',
                            return_value=label == 'requester',
                        ), patch.object(
                            app_module,
                            'calibration_certificate_approver_can_act',
                            return_value=label == 'approver',
                        ), patch.object(
                            app_module,
                            'is_admin_authorized',
                            return_value=label == 'administrator',
                        ):
                            response = self._invoke_download(
                                user_id,
                                fixture['file_id'],
                                fixture['approval_id'],
                            )
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(response.data, b'finalized calibration report docx bytes')
                        self.assertIn(
                            f'filename="{fixture["report_name"]}"',
                            response.headers.get('Content-Disposition', ''),
                        )

            finally:
                app.config['UPLOAD_FOLDER'] = original_upload_folder

    def test_approval_scoped_download_denies_unauthorized_user_and_mismatched_file(self):
        fixture = self._create_fixture()
        app = app_module.app
        db = app_module.db
        original_upload_folder = app.config.get('UPLOAD_FOLDER')
        with tempfile.TemporaryDirectory(prefix='calibration_report_approval_denial_') as storage_root:
            app.config['UPLOAD_FOLDER'] = storage_root
            try:
                unauthorized_response = self._download(
                    fixture,
                    fixture['unauthorized_id'],
                    storage_root,
                )
                self.assertEqual(unauthorized_response.status_code, 403)

                with app.app_context():
                    mismatched = app_module.ShiftFile(
                        shift_id=fixture['shift_id'],
                        online_tsr_submission_id=fixture['submission_id'],
                        filename=f"shift_{fixture['shift_id']}_{uuid.uuid4().hex[:16]}_unrelated.docx",
                        original_filename='Unrelated Attachment.docx',
                    )
                    db.session.add(mismatched)
                    db.session.commit()
                    mismatched_id = mismatched.id
                    db.session.remove()
                pathlib.Path(storage_root, mismatched.filename).write_bytes(b'unrelated docx bytes')

                with patch.object(app_module, 'calibration_certificate_approver_can_act', return_value=True):
                    mismatched_response = self._invoke_download(
                        fixture['approver_id'],
                        mismatched_id,
                        fixture['approval_id'],
                    )
                self.assertEqual(mismatched_response.status_code, 403)
            finally:
                app.config['UPLOAD_FOLDER'] = original_upload_folder

    def test_product_bsid_and_submission_contracts_are_present(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        template = (ROOT / "templates" / "products.html").read_text(encoding="utf-8")
        offline = (ROOT / "templates" / "offline_tsr.html").read_text(encoding="utf-8")
        self.assertIn("bsid = db.Column(db.String(40), nullable=True", source)
        self.assertIn("uq_product_bsid_nonblank", source)
        self.assertIn("def normalize_product_bsid", source)
        self.assertIn("product_bsid", source)
        self.assertIn("calibration_certificate", source)
        self.assertIn('id="p-bsid"', template)
        self.assertIn('id="calibration-report-bsid"', offline)
        self.assertIn('readonly', offline)

    def test_certificate_detail_exposes_embedded_preview_routes(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("def calibration_certificate_preview(approval_id, artifact):", source)
        self.assertIn("render_embedded_pdf_preview_shell(", source)
        self.assertIn("item['unsigned_preview_url']", source)
        self.assertIn("item['signed_preview_url']", source)

    def test_unsigned_pdf_is_flattened_and_covers_fixed_identity(self):
        payload = complete_payload()
        values, missing, _ = app_module.calibration_certificate_values(payload)
        self.assertEqual(values["Textfield"], "2026-0820-B-43")
        self.assertEqual(missing, [])
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "static" / "templates" / "calibration-certificate" / "calibration-certificate-template.pdf").read_bytes()
            ).hexdigest().upper(),
            app_module.CALIBRATION_CERTIFICATE_TEMPLATE_SHA256,
        )

        data, mapped, _ = app_module.build_calibration_certificate_pdf(payload)
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertEqual(mapped["Textfield"], "2026-0820-B-43")
        self.assertEqual(len(reader.pages), 1)
        self.assertIsNone(reader.get_fields())
        self.assertIsNone(reader.pages[0].get("/Annots"))
        self.assertNotIn("Rodito", text)
        self.assertNotIn("Aretano", text)
        self.assertNotIn("Medical Systems Division", text)

    def test_runtime_v2_preserves_source_geometry_fields_and_removes_fixed_identity_only(self):
        source_path = ROOT / "static" / "templates" / "calibration-certificate" / "calibration-certificate-template.pdf"
        runtime_path = source_path.with_name("calibration-certificate-runtime-v2.pdf")
        self.assertEqual(
            hashlib.sha256(source_path.read_bytes()).hexdigest().upper(),
            "C06F43E221C297229D5108E0F3BA0348FF0C1C6F299A791FF4359D60E9F17EBC",
        )
        self.assertTrue(runtime_path.is_file(), "the cleaned runtime-v2 template must be checked in")
        source = PdfReader(str(source_path))
        runtime = PdfReader(str(runtime_path))
        self.assertEqual(len(runtime.pages), 1)
        self.assertEqual(tuple(runtime.pages[0].mediabox), tuple(source.pages[0].mediabox))
        self.assertEqual(set(runtime.get_fields() or {}), set(source.get_fields() or {}))
        source_rects = {str(a.get_object().get("/T")): tuple(a.get_object().get("/Rect")) for a in source.pages[0]["/Annots"].get_object()}
        runtime_rects = {str(a.get_object().get("/T")): tuple(a.get_object().get("/Rect")) for a in runtime.pages[0]["/Annots"].get_object()}
        self.assertEqual(runtime_rects, source_rects)
        source_text = (source.pages[0].extract_text() or "")
        runtime_text = (runtime.pages[0].extract_text() or "")
        self.assertIn("Senior Service Manager", source_text)
        self.assertNotIn("Senior Service Manager", runtime_text)
        self.assertNotIn("Medical Systems Division", runtime_text)
        self.assertIn("Certified By:", runtime_text)
        self.assertIn("CUSTOMER  SUPPORT  CENTER", runtime_text)
        self.assertEqual(hashlib.sha256(runtime_path.read_bytes()).hexdigest().upper(), app_module.CALIBRATION_CERTIFICATE_RUNTIME_SHA256)
        from pypdf.generic import ContentStream
        source_ops = ContentStream(source.pages[0].get_contents(), source).operations
        runtime_ops = ContentStream(runtime.pages[0].get_contents(), runtime).operations
        ranges = []
        for predicate in (
            lambda operator, operands: operator == b"Td" and len(operands) == 2 and abs(float(operands[0]) - 411.613) < 0.001 and abs(float(operands[1]) - 256.796) < 0.001,
            lambda operator, operands: operator == b"Tm" and len(operands) == 6 and abs(float(operands[4]) - 397.90747) < 0.001 and abs(float(operands[5]) - 243.14021) < 0.001,
        ):
            anchor = next(i for i, (operands, operator) in enumerate(source_ops) if predicate(operator, operands))
            start = next(i for i in range(anchor, -1, -1) if source_ops[i][1] == b"BT")
            end = next(i for i in range(anchor, len(source_ops)) if source_ops[i][1] == b"ET")
            ranges.append((start, end))
        retained = [item for i, item in enumerate(source_ops) if not any(start <= i <= end for start, end in ranges)]
        self.assertEqual(retained, runtime_ops)

    def test_signed_pdf_uses_uniform_regular_data_font_humanist_approver_and_large_signature(self):
        import fitz

        data, mapped, _ = app_module.build_calibration_certificate_pdf(
            complete_payload(),
            approver="Jane Approver",
            signature_data=SIGNATURE,
            approval_title="Senior Service Manager, Medical Systems Division",
        )
        document = fitz.open(stream=data, filetype="pdf")
        page = document[0]
        spans = [
            span
            for block in page.get_text("dict")["blocks"]
            if block["type"] == 0
            for line in block["lines"]
            for span in line["spans"]
        ]
        data_spans = []
        for name in app_module.CALIBRATION_CERTIFICATE_FIELDS:
            matches = [span for span in spans if mapped[name] and span["text"].strip() == mapped[name]]
            self.assertTrue(matches, name)
            data_spans.append(matches[-1])
        self.assertEqual(len(data_spans), len(app_module.CALIBRATION_CERTIFICATE_FIELDS))
        self.assertTrue(all(span["font"].lower().startswith("helvetica") for span in data_spans))
        self.assertEqual({round(float(span["size"]), 1) for span in data_spans}, {11.0})
        approver_spans = [span for span in spans if "Jane Approver" in span["text"] or "Senior Service" in span["text"] or "Medical Systems" in span["text"]]
        self.assertTrue(approver_spans)
        self.assertTrue(all(abs(float(span["size"]) - 11.158) < 0.2 for span in approver_spans))
        self.assertTrue(any("helvetica" not in span["font"].lower() for span in approver_spans))
        self.assertTrue(any("humanist777" in span["font"].lower() for span in approver_spans))
        extracted = page.get_text()
        self.assertIn("Senior Service Manager", extracted)
        self.assertEqual(extracted.count("Medical Systems Division"), 1)
        self.assertNotIn("Senior Service Manager, Medical Systems Division", extracted)
        image_rects = []
        for image in page.get_images(full=True):
            image_rects.extend(page.get_image_rects(image[0]))
        self.assertTrue(any(
            rect.x0 >= 362 and rect.x1 <= 550 and rect.y1 <= 520 and
            rect.y1 - rect.y0 >= 8 and rect.x1 - rect.x0 >= 180
            for rect in image_rects
        ))
        rendered = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        signature_corner = rendered.pixel(388 * 2, 488 * 2)
        self.assertLess(max(signature_corner), 245, 'signature image corner must reveal the patterned page, not a white box')
        self.assertNotIn("drawRectangle", (ROOT / "static" / "js" / "app-calibration-report.js").read_text(encoding="utf-8"))

    def test_signature_cleanup_rejects_blank_and_stored_number_override_preserves_legacy_pending(self):
        from PIL import Image

        blank = io.BytesIO()
        Image.new("RGBA", (40, 20), (255, 255, 255, 255)).save(blank, format="PNG")
        blank_data = "data:image/png;base64," + __import__("base64").b64encode(blank.getvalue()).decode("ascii")
        with self.assertRaisesRegex(ValueError, "blank"):
            app_module.build_calibration_certificate_pdf(
                complete_payload(),
                approver="Jane Approver",
                signature_data=blank_data,
                approval_title="Calibration Manager",
            )

        legacy_number = "2026/08/20-B-43"
        data, mapped, _ = app_module.build_calibration_certificate_pdf(
            complete_payload(),
            certificate_number_override=legacy_number,
        )
        self.assertEqual(mapped["Textfield"], legacy_number)
        self.assertIn(legacy_number, "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages))

    def test_approver_title_wraps_to_two_lines_and_uses_helvetica_for_unsupported_glyphs(self):
        import fitz

        two_line, _, _ = app_module.build_calibration_certificate_pdf(
            complete_payload(),
            approver="Jane Approver",
            signature_data=SIGNATURE,
            approval_title="Senior Service Manager for",
        )
        two_line_text = fitz.open(stream=two_line, filetype="pdf")[0].get_text()
        self.assertIn("Senior Service Manager", two_line_text)
        self.assertIn("for", two_line_text)
        self.assertEqual(two_line_text.count("Medical Systems Division"), 1)

        fallback, _, _ = app_module.build_calibration_certificate_pdf(
            complete_payload(),
            approver="Jane Approver",
            signature_data=SIGNATURE,
            approval_title="José Manager",
        )
        fallback_page = fitz.open(stream=fallback, filetype="pdf")[0]
        fallback_spans = [
            span
            for block in fallback_page.get_text("dict")["blocks"]
            if block["type"] == 0
            for line in block["lines"]
            for span in line["spans"]
            if "Manager" in span["text"]
        ]
        self.assertTrue(fallback_spans)
        self.assertTrue(all("helvetica" in span["font"].lower() for span in fallback_spans))

    def test_shared_data_size_fallback_is_common_and_rejects_impossible_fit(self):
        values, _, _ = app_module.calibration_certificate_values(complete_payload())
        self.assertEqual(app_module.calibration_certificate_data_font_size(values), 11.0)
        long_values = dict(values)
        long_values["Text6"] = "Facility " + ("X" * 50)
        fallback = app_module.calibration_certificate_data_font_size(long_values)
        self.assertGreaterEqual(fallback, 8.5)
        self.assertLess(fallback, 11.0)
        import fitz
        long_payload = complete_payload()
        long_payload['calibration_report']['facility']['name'] = long_values['Text6']
        long_pdf, long_mapped, _ = app_module.build_calibration_certificate_pdf(long_payload)
        long_page = fitz.open(stream=long_pdf, filetype='pdf')[0]
        long_spans = [
            span
            for block in long_page.get_text('dict')['blocks']
            if block['type'] == 0
            for line in block['lines']
            for span in line['spans']
        ]
        rendered_sizes = [
            round(float(next(span for span in long_spans if long_mapped[name] and span['text'].strip() == long_mapped[name])['size']), 1)
            for name in app_module.CALIBRATION_CERTIFICATE_FIELDS
        ]
        self.assertEqual(set(rendered_sizes), {fallback})
        impossible = dict(values)
        impossible["Text6"] = "X" * 5000
        with self.assertRaisesRegex(ValueError, "Text6|Installed At"):
            app_module.build_calibration_certificate_pdf({**complete_payload(), "calibration_report": {**complete_payload()["calibration_report"], "facility": {"name": impossible["Text6"]}}})

    def test_signed_pdf_uses_acting_approver_identity(self):
        data, _, _ = app_module.build_calibration_certificate_pdf(
            complete_payload(),
            approver="Jane Approver",
            signature_data=SIGNATURE,
            approval_title="Calibration Manager",
        )
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertIn("Jane Approver", text)
        self.assertIn("Calibration Manager", text)
        self.assertNotIn("Rodito", text)
        self.assertIsNone(reader.get_fields())
        self.assertIsNone(reader.pages[0].get("/Annots"))

    def test_no_signature_pdf_uses_canonical_rodito_identity_and_is_flattened(self):
        data, mapped, _ = app_module.build_calibration_certificate_no_signature_pdf(complete_payload())
        reader = PdfReader(io.BytesIO(data))
        self.assertEqual(len(reader.pages), 1)
        self.assertIsNone(reader.get_fields())
        self.assertIsNone(reader.pages[0].get('/Annots'))
        text = '\n'.join(page.extract_text() or '' for page in reader.pages)
        self.assertIn('Rodito', text)
        self.assertIn('Senior Service Manager', text)
        self.assertIn('Medical Systems Division', text)
        self.assertNotIn('Jane Approver', text)
        for name, value in mapped.items():
            self.assertIn(value, text)

    def test_revision_submission_preserves_approved_history_and_selects_runtime_v2_latest(self):
        app = app_module.app
        db = app_module.db
        with tempfile.TemporaryDirectory(prefix='calibration_certificate_revision_') as storage_root:
            original_upload_folder = app.config.get('UPLOAD_FOLDER')
            app.config['UPLOAD_FOLDER'] = storage_root
            try:
                with app.app_context(), app.test_request_context('/'):
                    db.create_all()
                    app_module.ensure_calibration_certificate_approval_table()
                    user = app_module.User(
                        username=f'calibration_revision_{uuid.uuid4().hex[:8]}',
                        password='test-only', role='engineer', approval_title='Service Manager',
                    )
                    db.session.add(user)
                    db.session.flush()
                    engineer = app_module.Engineer(
                        user_id=user.id, employee_id=f'CERT-{uuid.uuid4().hex[:8]}',
                        name='Calibration Engineer', initials='CE', branch='Manila',
                    )
                    client = app_module.Client(name='Calibration Revision Clinic')
                    db.session.add_all([engineer, client])
                    db.session.flush()
                    product = app_module.Product(
                        serial_number=f'CERT-{uuid.uuid4().hex[:8]}', name='X-Ray',
                        client_id=client.id, bsid='B-REV2',
                    )
                    db.session.add(product)
                    db.session.flush()
                    shift = app_module.Shift(
                        title='Calibration Revision',
                        start_time=datetime.now(), end_time=datetime.now() + timedelta(hours=1),
                        engineer_id=engineer.id, client_id=client.id,
                        product_id=product.serial_number, status='Completed',
                    )
                    db.session.add(shift)
                    db.session.flush()
                    payload = complete_payload()
                    payload['calibration_report']['generated'] = {'fingerprint': 'report-rev1'}
                    submission = app_module.OnlineTsrSubmission(
                        shift_id=shift.id, tsr_number='TSR-REV', client_name=client.name,
                        product_name=product.name, serial_number=product.serial_number,
                        submitted_by_user_id=user.id, submitted_by_name=engineer.name,
                        status='completed', submission_token=f'rev1-{uuid.uuid4().hex}',
                        payload_json=json.dumps(payload), revision_no=1, is_latest=True,
                    )
                    db.session.add(submission)
                    db.session.commit()
                    with patch.object(app_module, 'get_assigned_approvers_for_requester', return_value=[]), \
                            patch.object(app_module, 'record_universal_approval_audit'), \
                            patch.object(app_module, 'create_system_notification'):
                        first = app_module.submit_calibration_certificate_for_submission(submission)
                        first_approval = first['approval']
                        first_path = pathlib.Path(storage_root) / first_approval.unsigned_artifact_path
                        first_bytes = first_path.read_bytes()
                        first_approval.status = 'Approved'
                        submission.is_latest = False
                        db.session.commit()
                        revised_payload = json.loads(submission.payload_json)
                        revised_payload['revision_reason'] = 'Calibration Certificate layout correction'
                        revised = app_module.OnlineTsrSubmission(
                            shift_id=shift.id, tsr_number='TSR-REV', client_name=client.name,
                            product_name=product.name, serial_number=product.serial_number,
                            submitted_by_user_id=user.id, submitted_by_name=engineer.name,
                            status='completed', submission_token=f'rev2-{uuid.uuid4().hex}',
                            payload_json=json.dumps(revised_payload), revision_no=2,
                            parent_submission_id=submission.id, is_latest=True,
                        )
                        db.session.add(revised)
                        db.session.commit()
                        second = app_module.submit_calibration_certificate_for_submission(revised)
                        second_approval = second['approval']
                        self.assertEqual(second_approval.revision_no, 2)
                        self.assertEqual(second_approval.certificate_number, first_approval.certificate_number)
                        self.assertEqual(second_approval.template_sha256, app_module.CALIBRATION_CERTIFICATE_RUNTIME_SHA256)
                        self.assertFalse(first_approval.is_latest)
                        self.assertEqual(first_approval.status, 'Approved')
                        self.assertEqual(first_path.read_bytes(), first_bytes)
                        self.assertEqual(
                            app_module.get_latest_online_tsr_submission_for_shift(shift.id).id,
                            revised.id,
                        )
                        self.assertEqual(revised_payload['revision_reason'], 'Calibration Certificate layout correction')
                        approver = app_module.User(
                            username=f'calibration_approver_{uuid.uuid4().hex[:8]}',
                            password='test-only', role='superadmin', approval_title='Service Manager',
                        )
                        db.session.add(approver)
                        db.session.flush()
                        db.session.add(app_module.Engineer(
                            user_id=approver.id, employee_id=f'APPROVER-{uuid.uuid4().hex[:8]}',
                            name='Robert Rio', initials='RR', branch='Manila', signature_data=SIGNATURE,
                        ))
                        db.session.commit()
                        legacy_number = '2026/08/20-B-43'
                        second_approval.certificate_number = legacy_number
                        db.session.commit()
                        with patch.object(app_module, 'calibration_certificate_approver_can_act', return_value=True), \
                                patch.object(app_module, 'approval_signature_required_response', return_value=None), \
                                patch.object(app_module, 'record_universal_approval_audit'), \
                                patch.object(app_module, 'create_system_notification'):
                            app_module.login_user(approver)
                            approval_response = app_module.approve_calibration_certificate(second_approval.id)
                            self.assertEqual(approval_response.get_json()['success'], True)
                            db.session.refresh(second_approval)
                            self.assertEqual(second_approval.status, 'Approved')
                            self.assertEqual(second_approval.certificate_number, legacy_number)
                            self.assertEqual(second_approval.approver_name_snapshot, 'Robert Rio')
                            self.assertEqual(second_approval.approver_title_snapshot, 'Service Manager')
                            self.assertTrue(second_approval.approver_signature_snapshot.startswith('data:image/'))
                            signed_file = db.session.get(app_module.ShiftFile, second_approval.signed_shift_file_id)
                            self.assertTrue(signed_file)
                            self.assertEqual(signed_file.original_filename, 'Calibration_Certificate_2026_08_20-B-43_REV2.pdf')
                            self.assertTrue((pathlib.Path(storage_root) / signed_file.filename).is_file())
                            no_signature_file = db.session.get(app_module.ShiftFile, second_approval.no_signature_shift_file_id)
                            self.assertTrue(no_signature_file)
                            self.assertEqual(no_signature_file.original_filename, 'Calibration_Certificate_2026_08_20-B-43_REV2_No_Signature.pdf')
                            self.assertTrue((pathlib.Path(storage_root) / no_signature_file.filename).is_file())
                            no_signature_text = '\n'.join(page.extract_text() or '' for page in PdfReader(str(pathlib.Path(storage_root) / no_signature_file.filename)).pages)
                            self.assertIn('Rodito', no_signature_text)
                            self.assertIn('Senior Service Manager', no_signature_text)
                            self.assertNotIn('Robert Rio', no_signature_text)
                            signed_text = '\n'.join(page.extract_text() or '' for page in PdfReader(str(pathlib.Path(storage_root) / signed_file.filename)).pages)
                            self.assertIn(legacy_number, signed_text)
                            preview_response = app_module.calibration_certificate_preview(second_approval.id, 'signed')
                            self.assertEqual(preview_response.mimetype, 'text/html')
                            self.assertIsNone(preview_response.headers.get('Content-Disposition'))
                            self.assertIn('data:application/pdf;base64,', preview_response.get_data(as_text=True))
                            app_module.logout_user()
            finally:
                app.config['UPLOAD_FOLDER'] = original_upload_folder
                with app.app_context():
                    db.session.remove()


if __name__ == "__main__":
    unittest.main()
