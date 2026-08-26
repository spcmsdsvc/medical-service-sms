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
ROTATIONS = (0, 90, 180, 270)
MARKER_COLORS = {
    'top_left': (1.0, 0.0, 0.0),
    'top_right': (0.0, 0.8, 0.0),
    'bottom_left': (0.0, 0.2, 1.0),
    'bottom_right': (1.0, 0.8, 0.0),
}


def image_heavy_pdf(page_count=1, rotations=None, markers=False):
    """Build deterministic scanned-looking pages with searchable text."""
    image = Image.effect_noise((3000, 2200), 80).convert('RGB')
    image_stream = io.BytesIO()
    image.save(image_stream, format='JPEG', quality=100, subsampling=0)
    image.close()

    import fitz

    rotations = tuple(rotations or (90,))
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
            if markers:
                marker_rects = {
                    'top_left': fitz.Rect(8, 8, 88, 88),
                    'top_right': fitz.Rect(524, 8, 604, 88),
                    'bottom_left': fitz.Rect(8, 704, 88, 784),
                    'bottom_right': fitz.Rect(524, 704, 604, 784),
                }
                for marker_name, rect in marker_rects.items():
                    color = MARKER_COLORS[marker_name]
                    page.draw_rect(rect, color=color, fill=color, width=1)
            page.set_rotation(rotations[page_number % len(rotations)])
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


def rendered_page_image(pdf_bytes, page_number=0, grayscale=False):
    import fitz

    document = fitz.open(stream=pdf_bytes, filetype='pdf')
    try:
        pixmap = document[page_number].get_pixmap(
            matrix=fitz.Matrix(1, 1),
            colorspace=fitz.csGRAY if grayscale else None,
            alpha=False,
        )
        mode = 'L' if pixmap.n == 1 else 'RGB'
        return Image.frombytes(mode, (pixmap.width, pixmap.height), pixmap.samples)
    finally:
        document.close()


def marker_centers(pdf_bytes):
    """Return normalized marker centers from a color render of the source."""
    image = rendered_page_image(pdf_bytes)
    if image.mode != 'RGB':
        image = image.convert('RGB')
    pixels = image.load()
    centers = {}
    for marker_name, color in MARKER_COLORS.items():
        target = tuple(int(channel * 255) for channel in color)
        points = []
        for y in range(image.height):
            for x in range(image.width):
                pixel = pixels[x, y]
                if sum(abs(pixel[index] - target[index]) for index in range(3)) <= 95:
                    points.append((x, y))
        if not points:
            raise AssertionError(f'Marker {marker_name} was not rendered.')
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        centers[marker_name] = (
            sum(xs) / len(xs) / image.width,
            sum(ys) / len(ys) / image.height,
            sum(sum(pixels[x, y]) for x, y in points) / (3 * len(points)),
        )
    return centers


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

    def _assert_topology(self, source_bytes, converted_bytes, expected_text=None):
        import fitz

        source_document = fitz.open(stream=source_bytes, filetype='pdf')
        converted_document = fitz.open(stream=converted_bytes, filetype='pdf')
        try:
            self.assertEqual(len(converted_document), len(source_document))
            for source_page, converted_page in zip(source_document, converted_document):
                self.assertAlmostEqual(converted_page.mediabox.width, source_page.mediabox.width, delta=0.1)
                self.assertAlmostEqual(converted_page.mediabox.height, source_page.mediabox.height, delta=0.1)
                self.assertEqual(converted_page.rotation, source_page.rotation)
            if expected_text:
                self.assertIn(expected_text, converted_document[0].get_text())
        finally:
            source_document.close()
            converted_document.close()
        self.assertEqual(
            len(PdfReader(io.BytesIO(converted_bytes), strict=False).pages),
            len(PdfReader(io.BytesIO(source_bytes), strict=False).pages),
        )

    def test_image_heavy_pdf_reaches_strict_stored_limit(self):
        source = image_heavy_pdf()
        self.assertGreater(len(source), app_module.REIMBURSEMENT_RECEIPT_MAX_BYTES)

        converted, stored_ext, content_type = self._prepare(source)

        self.assertLessEqual(len(converted), app_module.REIMBURSEMENT_RECEIPT_MAX_BYTES)
        self.assertEqual(stored_ext, 'pdf')
        self.assertEqual(content_type, 'application/pdf')

    def test_native_rewrite_preserves_page_topology_and_searchable_text(self):
        source = image_heavy_pdf(rotations=(90,))
        with patch.object(app_module, '_reimbursement_structural_pdf_candidate', return_value=source), \
                patch.object(
                    app_module,
                    '_reimbursement_rasterize_pdf_profile',
                    side_effect=AssertionError('native profile should reach the target first'),
                ):
            converted, _, _ = self._prepare(source)

        self._assert_topology(source, converted, 'Searchable Vector Text Page 1')

    def test_raster_fallback_preserves_page_dimensions_rotation_and_parseability(self):
        source = image_heavy_pdf(rotations=(90,))
        with patch.object(app_module, '_reimbursement_structural_pdf_candidate', return_value=source), \
                patch.object(app_module, '_reimbursement_rewrite_pdf_images_native', return_value=source):
            converted, _, _ = self._prepare(source)

        self._assert_topology(source, converted)
        import fitz

        document = fitz.open(stream=converted, filetype='pdf')
        try:
            self.assertNotIn('Searchable Vector Text Page 1', document[0].get_text())
        finally:
            document.close()
        self.assertLessEqual(len(converted), app_module.REIMBURSEMENT_RECEIPT_MAX_BYTES)

    def test_asymmetric_markers_survive_color_and_grayscale_raster_profiles_at_all_rotations(self):
        rasterizer = getattr(app_module, '_reimbursement_rasterize_pdf_profile', None)
        self.assertTrue(callable(rasterizer), 'the explicit raster profile contract is missing')
        if not callable(rasterizer):
            return

        for rotation in ROTATIONS:
            source = image_heavy_pdf(rotations=(rotation,), markers=True)
            source_markers = marker_centers(source)
            for dpi, quality, grayscale in ((96, 50, False), (72, 45, True)):
                with self.subTest(rotation=rotation, dpi=dpi, grayscale=grayscale):
                    candidate = rasterizer(source, dpi, quality, grayscale)
                    self.assertIsInstance(candidate, bytes)
                    self._assert_topology(source, candidate)
                    output = rendered_page_image(candidate)
                    if grayscale:
                        source_grayscale = rendered_page_image(source, grayscale=True)
                        for x_ratio, y_ratio, source_luma in source_markers.values():
                            source_luma = source_grayscale.getpixel((int(x_ratio * source_grayscale.width), int(y_ratio * source_grayscale.height)))
                            pixel = output.getpixel((int(x_ratio * output.width), int(y_ratio * output.height)))
                            if isinstance(pixel, tuple):
                                pixel = sum(pixel) / len(pixel)
                            self.assertLess(abs(pixel - source_luma), 40)
                    else:
                        output_markers = marker_centers(candidate)
                        for marker_name, source_marker in source_markers.items():
                            output_marker = output_markers[marker_name]
                            self.assertLess(abs(output_marker[0] - source_marker[0]), 0.08)
                            self.assertLess(abs(output_marker[1] - source_marker[1]), 0.08)

    def test_multipage_output_keeps_count_and_each_source_media_box(self):
        source = image_heavy_pdf(page_count=2, rotations=(90, 0))
        converted, _, _ = self._prepare(source)
        self._assert_topology(source, converted)

    def test_native_and_raster_profiles_are_fresh_source_profiles(self):
        source = image_heavy_pdf(rotations=(90,))
        source_calls = []

        def record_native(pdf_bytes, dpi, quality):
            source_calls.append(('native', pdf_bytes))
            return source

        def record_raster(pdf_bytes, dpi, quality, grayscale=False):
            source_calls.append(('raster', pdf_bytes))
            return source

        with patch.object(app_module, '_reimbursement_structural_pdf_candidate', return_value=source), \
                patch.object(app_module, '_reimbursement_rewrite_pdf_images_native', side_effect=record_native), \
                patch.object(app_module, '_reimbursement_rasterize_pdf_profile', side_effect=record_raster):
            with self.assertRaisesRegex(ValueError, READABILITY_FAILURE):
                app_module.reimbursement_optimize_pdf_receipt_bytes(source)
        self.assertGreaterEqual(len(source_calls), 2)
        self.assertTrue(all(call_bytes == source for _, call_bytes in source_calls))

    def test_password_protected_pdf_is_actionable_even_below_limit(self):
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.encrypt('test-password')
        output = io.BytesIO()
        writer.write(output)

        with self.assertRaisesRegex(ValueError, 'password-protected'):
            self._prepare(output.getvalue(), 'locked.pdf')

    def test_malformed_pdf_is_actionable_even_below_limit(self):
        with self.assertRaisesRegex(ValueError, 'malformed'):
            self._prepare(b'%PDF-1.7\nnot a complete PDF', 'broken.pdf')

    def test_readability_floor_failure_uses_exact_split_instruction_for_uploads(self):
        source = image_heavy_pdf()
        with patch.object(app_module, '_reimbursement_structural_pdf_candidate', return_value=source), \
                patch.object(app_module, '_reimbursement_rewrite_pdf_images_native', return_value=source), \
                patch.object(app_module, '_reimbursement_rasterize_pdf_profile', return_value=source):
            with self.assertRaises(ValueError) as raised:
                app_module.reimbursement_optimize_pdf_receipt_bytes(source)
        self.assertEqual(str(raised.exception), READABILITY_FAILURE)

    def test_best_effort_generated_package_call_returns_valid_candidate_at_floor(self):
        source = image_heavy_pdf()
        with patch.object(app_module, '_reimbursement_structural_pdf_candidate', return_value=source), \
                patch.object(app_module, '_reimbursement_rewrite_pdf_images_native', return_value=source), \
                patch.object(app_module, '_reimbursement_rasterize_pdf_profile', return_value=source):
            result = app_module.reimbursement_compress_pdf_bytes_best_effort(source, target_bytes=1)
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 0)
        self.assertEqual(len(PdfReader(io.BytesIO(result), strict=False).pages), 1)

    def test_public_rasterizer_has_explicit_failure_contract(self):
        source = image_heavy_pdf()
        with patch.object(app_module, '_reimbursement_rasterize_pdf_profile', return_value=source):
            with self.assertRaisesRegex(ValueError, READABILITY_FAILURE):
                app_module.reimbursement_rasterize_pdf_receipt_bytes(source)

    def test_oversized_intake_is_rejected_before_pdf_conversion(self):
        oversized = b'%PDF-1.7\n' + (b'x' * (35 * 1024 * 1024 + 1))
        with patch.object(
            app_module,
            'reimbursement_optimize_pdf_receipt_bytes',
            side_effect=AssertionError('intake rejection must happen first'),
        ):
            with self.assertRaisesRegex(ValueError, '35MB'):
                self._prepare(oversized, 'too-large.pdf')

    def _liquidation_conversion_response(self, route_name, row, failure):
        route = getattr(app_module, route_name).__wrapped__
        upload_data = {'receipt': (io.BytesIO(b'%PDF-1.7\nplaceholder'), 'receipt.pdf')}
        with app_module.app.test_request_context(
            f'/{route_name}',
            method='POST',
            data=upload_data,
            content_type='multipart/form-data',
        ):
            with patch.object(app_module, 'require_accounting_center_access', return_value=None), \
                    patch.object(app_module, 'ensure_travel_liquidation_tables'), \
                    patch.object(app_module, 'ensure_cash_advance_liquidation_tables'), \
                    patch.object(app_module, 'validate_travel_liquidation_receipt_upload', return_value=(True, None)), \
                    patch.object(app_module.db.session, 'get', return_value=row), \
                    patch.object(app_module, 'can_edit_travel_liquidation', return_value=(True, '')), \
                    patch.object(app_module, 'can_edit_cash_advance_liquidation', return_value=(True, '')), \
                    patch.object(app_module, 'travel_liquidation_secure_receipt_filename', return_value=('stored.pdf', 'receipt.pdf')), \
                    patch.object(app_module, 'cash_advance_liquidation_secure_receipt_filename', return_value=('stored.pdf', 'receipt.pdf')), \
                    patch.object(app_module, 'reimbursement_prepare_receipt_upload_bytes', side_effect=failure), \
                    patch.object(app_module.db.session, 'rollback') as rollback, \
                    patch.object(app_module, 'managed_storage_rollback_new_file') as cleanup:
                response = app_module.app.make_response(route(row.id))
            return response, rollback, cleanup

    def test_travel_liquidation_conversion_failure_is_http_400_and_rolls_back(self):
        row = SimpleNamespace(
            id=11,
            liquidation=SimpleNamespace(id=21, status='Draft', travel_request_id=31, liquidation_no='TL-31'),
        )
        response, rollback, _ = self._liquidation_conversion_response(
            'upload_travel_liquidation_receipt', row, ValueError(READABILITY_FAILURE)
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error'], READABILITY_FAILURE)
        rollback.assert_called_once()

    def test_cash_advance_liquidation_conversion_failure_is_http_400_and_rolls_back(self):
        row = SimpleNamespace(
            id=12,
            liquidation=SimpleNamespace(id=22, status='Draft', cash_advance_id=32, liquidation_no='CAL-32'),
        )
        response, rollback, _ = self._liquidation_conversion_response(
            'upload_cash_advance_liquidation_receipt', row, ValueError(READABILITY_FAILURE)
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error'], READABILITY_FAILURE)
        rollback.assert_called_once()

    def test_liquidation_unexpected_storage_failure_remains_http_500(self):
        row = SimpleNamespace(
            id=13,
            liquidation=SimpleNamespace(id=23, status='Draft', travel_request_id=33, liquidation_no='TL-33'),
        )
        response, _, _ = self._liquidation_conversion_response(
            'upload_travel_liquidation_receipt', row, RuntimeError('storage unavailable')
        )
        self.assertEqual(response.status_code, 500)

    def test_source_has_stage_specific_pdf_diagnostics_and_no_document_identity_logging(self):
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        self.assertIn('failure_category', source)
        self.assertIn('selected_stage', source)
        self.assertIn('profile=', source)
        self.assertNotIn('All Receipts PDF optimized:', source)


if __name__ == '__main__':
    unittest.main()
