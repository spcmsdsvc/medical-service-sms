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

    def test_products_markup_contains_desktop_mobile_certificate_status_and_accessible_new_tab_link(self):
        source = (ROOT / 'templates' / 'products.html').read_text(encoding='utf-8')

        self.assertIn('Calibration Certificate', source)
        self.assertIn('calibration_certificate', source)
        self.assertIn('product-mobile-certificate', source)
        self.assertIn('target="_blank"', source)
        self.assertIn('rel="noopener"', source)
        self.assertIn('aria-label="View calibration certificate', source)
        self.assertIn('No certificate on file', source)
        self.assertIn('certificate_number', source)
        self.assertIn('calibration_date', source)

    def test_products_markup_uses_cards_for_laptop_sized_viewports(self):
        source = (ROOT / 'templates' / 'products.html').read_text(encoding='utf-8')

        self.assertIn('@media screen and (max-width: 1600px)', source)
        self.assertIn('.table-responsive {\n            display: none;', source)
        self.assertIn('.product-mobile-list {\n            display: block;', source)
        self.assertIn('@media screen and (min-width: 1100px) and (max-width: 1600px)', source)
        self.assertIn('@media screen and (max-width: 768px)', source)


if __name__ == '__main__':
    unittest.main()
