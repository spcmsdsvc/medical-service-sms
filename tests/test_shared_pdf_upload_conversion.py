"""Focused regression coverage for the shared PDF upload conversion path."""

import io
import pathlib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from pypdf import PdfReader, PdfWriter
from werkzeug.datastructures import FileStorage

import app as app_module


ROOT = pathlib.Path(__file__).resolve().parents[1]
READABILITY_FAILURE = (
    'PDF could not be reduced below 2MB while keeping it readable. '
    'Please split it into smaller PDFs and upload them separately.'
)


def image_heavy_pdf(page_count=1, rotation=90):
    """Build deterministic scanned-looking pages with a searchable text overlay."""
    image = Image.effect_noise((3000, 2200), 80).convert('RGB')
    image_stream = io.BytesIO()
    image.save(image_stream, format='JPEG', quality=100, subsampling=0)
    image.close()

    import fitz

    document = fitz.open()
    try:
        for page_number in range(page_count):
            page = document.new_page(width=612, height=792)
            page.insert_image(page.rect, stream=image_stream.getvalue())
            page.insert_text(
                (36, 36),
                f'Searchable Vector Text Page {page_number + 1}',
                fontsize=14,
                color=(0, 0, 0),
            )
            page.set_rotation(rotation if page_number == 0 else 0)
        return document.tobytes(deflate=True)
    finally:
        document.close()
        image_stream.close()


def small_valid_pdf():
    import fitz

    document = fitz.open()
    try:
        page = document.new_page(width=612, height=792)
        page.insert_text((36, 36), 'Small valid PDF')
        return document.tobytes(deflate=True)
    finally:
        document.close()


class SharedPdfUploadConversionTests(unittest.TestCase):
    def _prepare(self, pdf_bytes, filename='scan.pdf'):
        return app_module.reimbursement_prepare_receipt_upload_bytes(
            FileStorage(
                stream=io.BytesIO(pdf_bytes),
                filename=filename,
                content_type='application/pdf',
            ),
            filename,
        )

    def test_image_heavy_pdf_reaches_strict_stored_limit(self):
        source = image_heavy_pdf()
        self.assertGreater(len(source), app_module.REIMBURSEMENT_RECEIPT_MAX_BYTES)

        converted, stored_ext, content_type = self._prepare(source)

        self.assertLessEqual(len(converted), app_module.REIMBURSEMENT_RECEIPT_MAX_BYTES)
        self.assertEqual(stored_ext, 'pdf')
        self.assertEqual(content_type, 'application/pdf')

    def test_native_rewrite_preserves_page_topology_and_searchable_text(self):
        source = image_heavy_pdf()
        with patch.object(
            app_module,
            '_reimbursement_rasterize_pdf_profile',
            side_effect=AssertionError('native profile should reach the target first'),
        ):
            converted, _, _ = self._prepare(source)

        import fitz

        document = fitz.open(stream=converted, filetype='pdf')
        try:
            self.assertEqual(len(document), 1)
            page = document[0]
            self.assertAlmostEqual(page.mediabox.width, 612, delta=0.1)
            self.assertAlmostEqual(page.mediabox.height, 792, delta=0.1)
            self.assertEqual(page.rotation, 90)
            self.assertIn('Searchable Vector Text Page 1', page.get_text())
        finally:
            document.close()

        self.assertEqual(len(PdfReader(io.BytesIO(converted)).pages), 1)

    def test_raster_fallback_preserves_page_dimensions_and_rotation(self):
        source = image_heavy_pdf()
        with patch.object(
            app_module,
            '_reimbursement_rewrite_pdf_images_native',
            return_value=source,
        ):
            converted, _, _ = self._prepare(source)

        import fitz

        document = fitz.open(stream=converted, filetype='pdf')
        try:
            self.assertEqual(len(document), 1)
            page = document[0]
            self.assertAlmostEqual(page.mediabox.width, 612, delta=0.1)
            self.assertAlmostEqual(page.mediabox.height, 792, delta=0.1)
            self.assertEqual(page.rotation, 90)
            self.assertNotIn('Searchable Vector Text Page 1', page.get_text())
        finally:
            document.close()

        self.assertLessEqual(len(converted), app_module.REIMBURSEMENT_RECEIPT_MAX_BYTES)

    def test_multipage_output_keeps_count_and_each_source_media_box(self):
        source = image_heavy_pdf(page_count=2)
        converted, _, _ = self._prepare(source)

        import fitz

        document = fitz.open(stream=converted, filetype='pdf')
        try:
            self.assertEqual(len(document), 2)
            for page_number, page in enumerate(document):
                self.assertAlmostEqual(page.mediabox.width, 612, delta=0.1)
                self.assertAlmostEqual(page.mediabox.height, 792, delta=0.1)
                self.assertEqual(page.rotation, 90 if page_number == 0 else 0)
        finally:
            document.close()

    def test_password_protected_pdf_is_actionable(self):
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.encrypt('test-password')
        output = io.BytesIO()
        writer.write(output)

        with self.assertRaisesRegex(ValueError, 'password-protected'):
            self._prepare(output.getvalue(), 'locked.pdf')

    def test_malformed_pdf_is_actionable(self):
        with self.assertRaisesRegex(ValueError, 'malformed'):
            self._prepare(b'%PDF-1.7\nnot a complete PDF', 'broken.pdf')

    def test_readability_floor_failure_is_actionable(self):
        source = image_heavy_pdf()
        with patch.object(
            app_module,
            '_reimbursement_rewrite_pdf_images_native',
            return_value=source,
        ), patch.object(
            app_module,
            '_reimbursement_rasterize_pdf_profile',
            return_value=source,
        ):
            with self.assertRaisesRegex(ValueError, READABILITY_FAILURE):
                app_module.reimbursement_compress_pdf_bytes_best_effort(source)

    def test_oversized_intake_is_rejected_before_pdf_conversion(self):
        oversized = b'%PDF-1.7\n' + (b'x' * (35 * 1024 * 1024 + 1))
        with patch.object(
            app_module,
            'reimbursement_compress_pdf_bytes_best_effort',
            side_effect=AssertionError('intake rejection must happen first'),
        ):
            with self.assertRaisesRegex(ValueError, '35MB'):
                self._prepare(oversized, 'too-large.pdf')

    def _liquidation_conversion_error_response(self, route_name, row):
        route = getattr(app_module, route_name).__wrapped__
        request_path = f'/{route_name}'
        upload_data = {
            'receipt': (io.BytesIO(b'%PDF-1.7\nplaceholder'), 'receipt.pdf'),
        }
        with app_module.app.test_request_context(
            request_path,
            method='POST',
            data=upload_data,
            content_type='multipart/form-data',
        ):
            with patch.object(app_module, 'require_accounting_center_access', return_value=None), \
                    patch.object(app_module, 'ensure_travel_liquidation_tables'), \
                    patch.object(app_module, 'validate_travel_liquidation_receipt_upload', return_value=(True, None)), \
                    patch.object(app_module.db.session, 'get', return_value=row), \
                    patch.object(app_module, 'can_edit_travel_liquidation', return_value=(True, '')), \
                    patch.object(app_module, 'can_edit_cash_advance_liquidation', return_value=(True, '')), \
                    patch.object(app_module, 'travel_liquidation_secure_receipt_filename', return_value=('stored.pdf', 'receipt.pdf')), \
                    patch.object(app_module, 'cash_advance_liquidation_secure_receipt_filename', return_value=('stored.pdf', 'receipt.pdf')), \
                    patch.object(app_module, 'reimbursement_prepare_receipt_upload_bytes', side_effect=ValueError(READABILITY_FAILURE)):
                return app_module.app.make_response(route(row.id))

    def test_travel_liquidation_conversion_failure_is_http_400(self):
        row = SimpleNamespace(
            id=11,
            liquidation=SimpleNamespace(id=21, status='Draft', travel_request_id=31, liquidation_no='TL-31'),
        )
        response = self._liquidation_conversion_error_response('upload_travel_liquidation_receipt', row)
        self.assertEqual(response.status_code, 400)
        self.assertIn(READABILITY_FAILURE, response.get_json()['error'])

    def test_cash_advance_liquidation_conversion_failure_is_http_400(self):
        row = SimpleNamespace(
            id=12,
            liquidation=SimpleNamespace(id=22, status='Draft', cash_advance_id=32, liquidation_no='CAL-32'),
        )
        response = self._liquidation_conversion_error_response('upload_cash_advance_liquidation_receipt', row)
        self.assertEqual(response.status_code, 400)
        self.assertIn(READABILITY_FAILURE, response.get_json()['error'])

    def test_source_has_stage_specific_pdf_diagnostics(self):
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        self.assertIn('failure_category', source)
        self.assertIn('selected_stage', source)
        self.assertNotIn('All Receipts PDF optimized:', source)


if __name__ == '__main__':
    unittest.main()
