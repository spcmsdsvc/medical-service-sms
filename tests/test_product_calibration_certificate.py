"""Focused coverage for the Products-page Calibration Certificate surface.

The module selects its own disposable SQLite database before importing the application so
these tests never open or mutate the repository's scheduler.db.
"""

import json
import os
import pathlib
import tempfile
import unittest
import uuid
from datetime import datetime
from unittest.mock import patch

from pypdf import PdfWriter


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB = pathlib.Path(tempfile.gettempdir()) / f"medical_service_product_certificate_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB))
os.environ.setdefault("SECRET_KEY", "product-calibration-certificate-test-only")

import app as app_module  # noqa: E402


class ProductCalibrationCertificateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.db = app_module.db
        cls.app.config.update(TESTING=True)

    def setUp(self):
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.db.create_all()
        app_module.ensure_calibration_certificate_approval_table()

    def tearDown(self):
        self.db.session.remove()
        self.app_context.pop()

    def _make_user(self, label, role='engineer', with_profile=True):
        suffix = uuid.uuid4().hex[:8]
        user = app_module.User(
            username=f'{label}_{suffix}',
            password='test-only',
            role=role,
        )
        self.db.session.add(user)
        self.db.session.flush()
        profile = None
        if with_profile:
            profile = app_module.Engineer(
                user_id=user.id,
                employee_id=f'EMP-{suffix}',
                name=f'{label.title()} Engineer',
                initials=label[:2].upper(),
                branch='Manila',
            )
            self.db.session.add(profile)
            self.db.session.flush()
        return user, profile

    def _make_machine(self, label='machine'):
        suffix = uuid.uuid4().hex[:8]
        requester, engineer = self._make_user(f'{label}_requester')
        client = app_module.Client(name=f'{label.title()} Clinic {suffix}')
        self.db.session.add(client)
        self.db.session.flush()
        product = app_module.Product(
            serial_number=f'SN-{suffix}',
            name=f'{label.title()} X-Ray',
            client_id=client.id,
            bsid=f'B-{suffix[:6]}',
        )
        self.db.session.add(product)
        self.db.session.flush()
        shift = self._make_shift(product, client, engineer, label)
        self.db.session.commit()
        return {
            'requester': requester,
            'engineer': engineer,
            'client': client,
            'product': product,
            'shift': shift,
        }

    def _make_shift(self, product, client, engineer, label='service'):
        shift = app_module.Shift(
            title=f'{label.title()} Calibration',
            start_time=datetime(2026, 8, 20, 9, 0),
            end_time=datetime(2026, 8, 20, 10, 0),
            engineer_id=engineer.id,
            client_id=client.id,
            product_id=product.serial_number,
            status='Completed',
        )
        self.db.session.add(shift)
        self.db.session.flush()
        return shift

    def _make_approval(
        self,
        machine,
        *,
        status='Approved',
        is_latest=True,
        signed=True,
        approved_at=None,
        certificate_number=None,
        shift=None,
    ):
        shift = shift or machine['shift']
        suffix = uuid.uuid4().hex[:8]
        submission = app_module.OnlineTsrSubmission(
            shift_id=shift.id,
            tsr_number=f'TSR-{suffix}',
            client_name=machine['client'].name,
            product_name=machine['product'].name,
            serial_number=machine['product'].serial_number,
            submitted_by_user_id=machine['requester'].id,
            submitted_by_name=machine['engineer'].name,
            status='completed',
            submission_token=f'submission-{suffix}',
            payload_json=json.dumps({'calibration_report': {}}),
            revision_no=1,
            is_latest=is_latest,
        )
        self.db.session.add(submission)
        self.db.session.flush()

        mapped = {
            'Textfield': certificate_number or f'2026-0820-B-{suffix[:4]}',
            'Text1': 'Digital Angiography System',
            'Text2': 'MobileDart Evolution MX9',
            'Text3': machine['product'].serial_number,
            'Text4': '2026/08/20',
            'Text5': '2027/08/20',
            'Text6': machine['client'].name,
            'Textfield-0': submission.tsr_number,
        }

        signed_file = None
        if signed:
            signed_file = app_module.ShiftFile(
                shift_id=shift.id,
                filename=f'signed-{suffix}.pdf',
                original_filename=f'Calibration_Certificate_{suffix}.pdf',
                uploaded_at=approved_at or datetime(2026, 8, 20, 11, 0),
            )
            self.db.session.add(signed_file)
            self.db.session.flush()

        approval = app_module.CalibrationCertificateApproval(
            shift_id=shift.id,
            online_tsr_submission_id=submission.id,
            requester_user_id=machine['requester'].id,
            revision_no=1,
            is_latest=is_latest,
            status=status,
            certificate_number=mapped['Textfield'],
            mapped_data_json=json.dumps(mapped),
            template_sha256=app_module.CALIBRATION_CERTIFICATE_RUNTIME_SHA256,
            unsigned_artifact_path=f'unsigned-{suffix}.pdf',
            signed_shift_file_id=signed_file.id if signed_file else None,
            approved_at=approved_at,
            submitted_at=datetime(2026, 8, 20, 10, 30),
            created_at=datetime(2026, 8, 20, 10, 30),
            updated_at=datetime(2026, 8, 20, 10, 30),
        )
        self.db.session.add(approval)
        self.db.session.commit()
        return approval

    def _client_as(self, user):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user.id)
            session['_fresh'] = True
        return client

    def _product_record(self, client, serial_number):
        response = client.get('/get_products')
        self.assertEqual(response.status_code, 200)
        return next(product for product in response.get_json() if product['serial_number'] == serial_number)

    def test_product_api_serializes_current_approved_signed_certificate(self):
        machine = self._make_machine('approved')
        approval = self._make_approval(
            machine,
            certificate_number='2026-0820-B-43',
            approved_at=datetime(2026, 8, 20, 12, 0),
        )
        viewer, _ = self._make_user('product_viewer')
        self.db.session.commit()

        record = self._product_record(self._client_as(viewer), machine['product'].serial_number)
        certificate = record['calibration_certificate']

        self.assertEqual(
            set(certificate),
            {
                'approval_id',
                'certificate_number',
                'calibration_date',
                'next_calibration_date',
                'preview_url',
            },
        )
        self.assertEqual(certificate['approval_id'], approval.id)
        self.assertEqual(certificate['certificate_number'], '2026-0820-B-43')
        self.assertEqual(certificate['calibration_date'], '2026/08/20')
        self.assertEqual(certificate['next_calibration_date'], '2027/08/20')
        self.assertEqual(
            certificate['preview_url'],
            f'/calibration_certificate_preview/{approval.id}/signed',
        )

    def test_product_api_hides_pending_returned_superseded_unsigned_and_missing_certificates(self):
        cases = [
            ('pending', {'status': 'Pending'}),
            ('returned', {'status': 'Returned'}),
            ('superseded', {'status': 'Superseded'}),
            ('historical', {'status': 'Approved', 'is_latest': False}),
            ('unsigned', {'status': 'Approved', 'signed': False}),
        ]
        machines = []
        for label, options in cases:
            machine = self._make_machine(label)
            self._make_approval(machine, **options)
            machines.append(machine)

        missing_machine = self._make_machine('missing')
        viewer, _ = self._make_user('product_viewer_missing')
        self.db.session.commit()
        client = self._client_as(viewer)

        for machine in machines + [missing_machine]:
            record = self._product_record(client, machine['product'].serial_number)
            self.assertIsNone(record['calibration_certificate'], machine['product'].serial_number)

    def test_product_api_selects_newest_approval_for_one_machine_then_approval_id(self):
        machine = self._make_machine('multiple')
        older = self._make_approval(
            machine,
            certificate_number='2026-0801-B-01',
            approved_at=datetime(2026, 8, 1, 12, 0),
        )
        newer_shift = self._make_shift(machine['product'], machine['client'], machine['engineer'], 'multiple-newer')
        newer = self._make_approval(
            machine,
            certificate_number='2026-0820-B-43',
            approved_at=datetime(2026, 8, 20, 12, 0),
            shift=newer_shift,
        )
        tie_shift = self._make_shift(machine['product'], machine['client'], machine['engineer'], 'multiple-tie')
        tied = self._make_approval(
            machine,
            certificate_number='2026-0820-B-44',
            approved_at=newer.approved_at,
            shift=tie_shift,
        )
        viewer, _ = self._make_user('product_viewer_multiple')
        self.db.session.commit()

        record = self._product_record(self._client_as(viewer), machine['product'].serial_number)
        self.assertEqual(record['calibration_certificate']['approval_id'], tied.id)
        self.assertEqual(record['calibration_certificate']['certificate_number'], '2026-0820-B-44')
        self.assertGreater(tied.id, newer.id)
        self.assertLess(older.id, newer.id)

    def test_newer_pending_revision_hides_prior_approved_revision(self):
        machine = self._make_machine('pending_revision')
        self._make_approval(
            machine,
            status='Approved',
            is_latest=False,
            signed=True,
            certificate_number='2026-0801-B-01',
            approved_at=datetime(2026, 8, 1, 12, 0),
        )
        self._make_approval(
            machine,
            status='Pending',
            is_latest=True,
            signed=False,
            certificate_number='2026-0820-B-43',
        )
        viewer, _ = self._make_user('product_viewer_pending_revision')
        self.db.session.commit()

        record = self._product_record(self._client_as(viewer), machine['product'].serial_number)
        self.assertIsNone(record['calibration_certificate'])

    def test_product_page_user_can_preview_current_signed_certificate(self):
        machine = self._make_machine('preview')
        approval = self._make_approval(
            machine,
            certificate_number='2026-0820-B-43',
            approved_at=datetime(2026, 8, 20, 12, 0),
        )
        viewer, viewer_engineer = self._make_user('unassigned_product_viewer')
        self.db.session.commit()
        self.assertNotEqual(viewer.id, machine['requester'].id)
        self.assertNotEqual(viewer_engineer.id, machine['shift'].engineer_id)

        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        with tempfile.TemporaryDirectory(prefix='product_certificate_preview_') as temp_root:
            pdf_path = pathlib.Path(temp_root) / 'signed.pdf'
            with pdf_path.open('wb') as stream:
                writer.write(stream)
            client = self._client_as(viewer)
            with patch.object(app_module, 'managed_storage_read_path', return_value=str(pdf_path)):
                response = client.get(f'/calibration_certificate_preview/{approval.id}/signed')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/html')
        self.assertIn('data:application/pdf;base64,', response.get_data(as_text=True))
        self.assertNotIn('attachment', (response.headers.get('Content-Disposition') or '').lower())
        self.assertIn('no-store', response.headers.get('Cache-Control', ''))

    def test_product_page_user_cannot_preview_unsigned_or_no_signature_artifacts(self):
        machine = self._make_machine('artifact_access')
        approval = self._make_approval(machine, approved_at=datetime(2026, 8, 20, 12, 0))
        viewer, _ = self._make_user('artifact_product_viewer')
        self.db.session.commit()
        client = self._client_as(viewer)

        unsigned_response = client.get(f'/calibration_certificate_preview/{approval.id}/unsigned')
        no_signature_response = client.get(f'/calibration_certificate_preview/{approval.id}/no_signature')

        self.assertEqual(unsigned_response.status_code, 403)
        self.assertEqual(no_signature_response.status_code, 403)

    def test_products_markup_moves_compact_certificate_link_under_desktop_and_mobile_serial(self):
        source = (ROOT / 'templates' / 'products.html').read_text(encoding='utf-8')

        self.assertIn('calibration_certificate', source)
        self.assertIn('function renderProductSerialCertificateLink(product, mobile = false)', source)
        self.assertIn('renderProductSerialCertificateLink(p)', source)
        self.assertIn('renderProductSerialCertificateLink(p, true)', source)
        self.assertIn('product-serial-certificate-link', source)
        self.assertIn('product-serial-certificate-link-mobile', source)
        self.assertIn("if(!certificate || !certificate.preview_url) return '';", source)
        self.assertIn('target="_blank"', source)
        self.assertIn('rel="noopener"', source)
        self.assertIn('aria-label="View calibration certificate for ${serial}"', source)
        self.assertIn('title="View calibration certificate for ${serial}"', source)
        self.assertIn('<span>View Certificate</span>', source)
        self.assertNotIn('<th>Calibration Certificate</th>', source)
        self.assertNotIn('product-col-certificate', source)
        self.assertNotIn('product-mobile-certificate', source)
        self.assertNotIn('product-certificate-block', source)
        self.assertNotIn('product-certificate-number', source)
        self.assertNotIn('product-certificate-date', source)
        self.assertNotIn('No certificate on file', source)
        self.assertNotIn('certificate_number', source)
        self.assertNotIn('calibration_date', source)

    def test_products_markup_keeps_identity_actions_and_accessible_states(self):
        source = (ROOT / 'templates' / 'products.html').read_text(encoding='utf-8')

        self.assertIn('product-name-content', source)
        self.assertIn('product-row-actions no-print', source)
        self.assertIn("const serial = escapeHtml(product.serial_number || '');", source)
        self.assertIn('getProductIdentityLabel(product)', source)
        self.assertIn('onclick="openEditModal(\'${serial}\')"', source)
        self.assertIn('onclick="deleteProduct(\'${serial}\')"', source)
        self.assertIn('aria-label="Edit ${identity}"', source)
        self.assertIn('aria-label="Delete ${identity}"', source)
        self.assertIn("if(authRole !== 'engineer')", source)
        self.assertNotIn('<th>Actions</th>', source)
        self.assertNotIn('class="no-print text-end">Actions</th>', source)
        self.assertIn('<td class="product-identity-cell">', source)
        self.assertIn('<strong>${escapeHtml(p.serial_number)}</strong>\n                        ${renderProductSerialCertificateLink(p)}', source)
        self.assertIn('<div class="product-mobile-sn">${escapeHtml(p.serial_number)}</div>\n                        ${renderProductSerialCertificateLink(p, true)}', source)
        self.assertIn('${renderProductSerialCertificateLink(p)}', source)
        self.assertIn('${renderProductSerialCertificateLink(p, true)}', source)
        self.assertIn('colspan="7"', source)

        self.assertIn('position: sticky', source)
        self.assertIn('cell.style.left', source)
        self.assertIn('product-table-wrap tbody td.product-freeze-cell', source)
        self.assertIn('product-table-scrollbar', source)
        self.assertIn('target="_blank"', source)
        self.assertIn('rel="noopener"', source)

        self.assertIn('id="product-results-summary"', source)
        self.assertIn('id="product-clear-filters"', source)
        self.assertIn('function clearProductFilters()', source)
        self.assertIn('Loading products...', source)
        self.assertIn('Unable to load products right now.', source)
        self.assertIn('No products match your filters.', source)
        self.assertIn('onclick="loadData()">Retry</button>', source)

        self.assertIn('aria-describedby="modal-product-context"', source)
        self.assertIn('id="modal-product-context"', source)
        self.assertIn('aria-label="Close product details"', source)
        self.assertIn('for="p-serial"', source)
        self.assertIn('for="p-name"', source)
        self.assertIn('Edit Product Record', source)
        self.assertIn('This permanently removes the product record', source)
        self.assertIn('@media print', source)
        self.assertIn('@media screen and (max-width: 768px)', source)

    def test_products_markup_supports_user_selectable_frozen_columns(self):
        source = (ROOT / 'templates' / 'products.html').read_text(encoding='utf-8')

        self.assertIn('id="product-freeze-column"', source)
        self.assertIn('Freeze columns through', source)
        for value in ('none', 'serial', 'name', 'bsid', 'owner', 'start', 'end', 'status'):
            self.assertIn(f'<option value="{value}"', source)
        self.assertNotIn('<option value="certificate"', source)
        self.assertIn('Product Name + Actions', source)
        self.assertIn('function setProductFreezeColumn(value)', source)
        self.assertIn('function restoreProductFreezePreference()', source)
        self.assertIn('PRODUCT_FREEZE_STORAGE_KEY', source)
        self.assertIn('localStorage.setItem(PRODUCT_FREEZE_STORAGE_KEY, productFreezeColumn)', source)
        self.assertIn('function applyProductFreezeColumn()', source)
        self.assertIn('product-freeze-cell', source)
        self.assertIn('product-freeze-edge', source)
        self.assertIn('cell.style.left', source)
        self.assertIn('refreshProductTableLayout', source)
        self.assertIn('position: static !important', source)
        self.assertIn('status: 7', source)
        self.assertNotIn('certificate: 8', source)
        self.assertNotIn('left: 12rem', source)

    def test_products_markup_uses_compact_content_aware_column_sizing(self):
        source = (ROOT / 'templates' / 'products.html').read_text(encoding='utf-8')

        self.assertIn('table-layout: auto', source)
        self.assertIn('width: max-content;', source)
        self.assertIn('min-width: 100%;', source)
        self.assertNotIn('table-layout: fixed', source)
        self.assertIn('product-col-serial { width: 8.25rem; }', source)
        self.assertIn('product-col-name { width: 13rem; }', source)
        self.assertIn('product-col-bsid { width: 5rem; }', source)
        self.assertIn('product-col-date { width: 7rem; }', source)
        self.assertIn('product-col-status { width: 9rem; }', source)
        self.assertIn('justify-content: flex-start;', source)
        self.assertIn('width: 1.75rem;', source)
        self.assertIn('height: 1.75rem;', source)
        self.assertIn('font-size: 0.8rem;', source)
        self.assertNotIn('product-col-certificate', source)
        self.assertIn('longer identifier or label claim more room', source)
        self.assertIn('white-space: nowrap', source)
        self.assertIn('white-space: normal', source)
        self.assertNotIn('min-width: 90rem', source)

    def test_products_markup_keeps_list_view_with_laptop_horizontal_scroll(self):
        source = (ROOT / 'templates' / 'products.html').read_text(encoding='utf-8')

        self.assertIn('product-table-scroll-hint', source)
        self.assertIn('id="product-table-scrollbar"', source)
        self.assertIn('id="product-table-scrollbar-content"', source)
        self.assertIn('class="table-responsive product-table-wrap"', source)
        self.assertIn('role="region"', source)
        self.assertIn('aria-label="Product inventory table. Scroll horizontally to view all columns."', source)
        self.assertIn('position: sticky', source)
        self.assertIn('scrollBar.addEventListener', source)
        self.assertIn('tableWrap.addEventListener', source)
        self.assertIn('ResizeObserver', source)
        self.assertIn('@media screen and (min-width: 769px) and (max-width: 1600px)', source)
        self.assertIn('width: max-content;', source)
        self.assertIn('min-width: 100%;', source)
        self.assertNotIn('@media screen and (max-width: 1600px) {\n        .table-responsive {\n            display: none;', source)
        self.assertIn('@media screen and (max-width: 768px)', source)


if __name__ == '__main__':
    unittest.main()
