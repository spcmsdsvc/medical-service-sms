"""Regression coverage for the shared generated-signature enlargement scale."""

import pathlib
import unittest

try:
    import app as app_module
except Exception as exc:  # pragma: no cover - source-only environments
    app_module = None
    APP_IMPORT_ERROR = exc
else:
    APP_IMPORT_ERROR = None

from tests.sw_cache_version import assert_cache_version_at_least


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _signature_data_url(width, height):
    """A wide, short signature bitmap -- the shape a real captured signature has."""
    import base64
    import io

    from PIL import Image, ImageDraw

    image = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.line(
        [(int(width * 0.04), int(height * 0.77)), (int(width * 0.22), int(height * 0.23)),
         (int(width * 0.37), int(height * 0.81)), (int(width * 0.52), int(height * 0.27)),
         (int(width * 0.69), int(height * 0.77)), (int(width * 0.96), int(height * 0.42))],
        fill=(10, 10, 90, 255), width=max(4, height // 18))
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()


class _StubApprovedHeader:
    """The minimum an approved reimbursement header needs to reach the stamp path."""

    def __init__(self, signature_data):
        self.status = 'Approved'
        self.approval_signature_snapshot = signature_data
        self.approval_name_snapshot = 'Maria Santos'
        self.approval_title_snapshot = 'Manager'
        self.approved_at = None
        self.approval_signed_at = None


class SignatureStampSizeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.tsr_source = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')

    @unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
    def test_shared_scale_is_one_point_five(self):
        self.assertEqual(app_module.SIGNATURE_STAMP_SCALE, 1.5)

    def test_no_stamp_site_kept_a_hardcoded_size(self):
        """Every site goes through the shared knob, so one number moves all of them.

        Asserts the *absence* of each pre-enlargement literal rather than the presence of a
        particular spelling, so a site that is rewritten still passes while a site that
        reverts to a fixed size fails. An exact usage count was tried first and rejected:
        pinning it makes every future edit to an unrelated site fail the suite.
        """
        for dead in (
            'draw_signature_group(signature_people, 426, 842, 160, 54, max_columns=3)',
            'draw_signature_data_url(manager_signature_data, 421, 195, 160, 28',
            'draw_signature_top(pdf_canvas, page_height, 451, 124.5, 72, 22',
            'signature_image.width = 125',
            'signature_image.width = 95',
        ):
            self.assertFalse(dead in self.app_source,
                             f'a pre-enlargement size is back: {dead!r}')

    def test_the_tsr_footer_reserve_is_derived_from_the_signature_height(self):
        """The coupling that broke: the reserve was a hardcoded 247 -- exactly the old
        footer height -- so enlarging the signature made the footer taller than the space
        set aside for it, collapsing the page's bottom margin from 40px to 6px.

        Asserted at source because there is no JavaScript runner here; it asserts the
        outcome (the reserve references the derived constant) rather than its spelling.
        """
        self.assertIn('const TSR_SIGNATURE_FOOTER_HEIGHT = TSR_SIGNATURE_FOOTER_FIXED_HEIGHT + TSR_SIGNATURE_ROW_HEIGHT;',
                      self.tsr_source)
        self.assertIn('+ 80 + TSR_SIGNATURE_FOOTER_HEIGHT;', self.tsr_source)
        self.assertNotIn('+ 80 + 247;', self.tsr_source)
        self.assertIn('const sigH = TSR_SIGNATURE_ROW_HEIGHT;', self.tsr_source)
        self.assertIn('const SIGNATURE_STAMP_SCALE = Number({{ signature_stamp_scale|tojson }}) || 1.5;', self.tsr_source)
        self.assertIn('const sigImageW = Math.min(340, Math.round(250 * SIGNATURE_STAMP_SCALE));', self.tsr_source)
        self.assertIn('margin + 70, sigY, sigImageW, sigH', self.tsr_source)

    @unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
    def test_the_pcv_stamp_cannot_grow_wider_than_its_own_field(self):
        """0.82 * 1.5 is 1.23, so the enlarged box was wider than the field holding it.

        draw_x centres on the field width rather than on the box, so a wide signature hung
        past both edges into whatever sits beside the APPROVED BY box.

        This renders the real overlay and measures the placed image. An earlier version of
        this test recomputed the formula itself and therefore passed with the defect injected
        -- it proved nothing, which is precisely how a vacuous test reads.
        """
        import fitz

        wide_signature = _signature_data_url(900, 260)
        header = _StubApprovedHeader(wide_signature)
        field_x, field_y, field_width, field_height = 120.0, 400.0, 150.0, 46.0

        pdf_bytes = app_module.reimbursement_approval_signature_overlay_pdf(
            header, 612.0, 936.0, (field_x, field_y, field_width, field_height))
        self.assertTrue(pdf_bytes, 'the overlay produced no PDF')

        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        page = doc[0]
        rects = [r for info in page.get_images(full=True)
                 for r in page.get_image_rects(info[0])]
        self.assertEqual(len(rects), 1, 'expected exactly one stamped signature')
        rect = rects[0]
        doc.close()

        self.assertGreaterEqual(rect.x0 + 0.01, field_x,
                                'the PCV signature hangs off the left of its own field')
        self.assertLessEqual(rect.x1, field_x + field_width + 0.01,
                             'the PCV signature hangs off the right of its own field')
        # Positive control: it still grew well beyond the pre-enlargement 0.82 box.
        self.assertGreater(rect.width, field_width * 0.82)

    def test_upscale_caps_are_raised_but_not_removed(self):
        self.assertIn('box_height / float(image_height),\n                    SIGNATURE_STAMP_SCALE', self.app_source)
        self.assertIn('signature_area_height / float(image_height),\n                    SIGNATURE_STAMP_SCALE', self.app_source)
        self.assertNotIn('box_height / float(image_height), 1.0', self.app_source)
        self.assertNotIn('signature_area_height / float(image_height), 1.0', self.app_source)

    @unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
    def test_lpr_width_grows_and_remains_inside_a_wide_signature_line(self):
        old_width = min(86.0, max(40.0, 300.0 * 0.5))
        x, y, width, height = app_module.lpr_signature_box((100.0, 30.0, 400.0, 44.0), None)
        self.assertGreater(width, old_width)
        self.assertLessEqual(x, 400.0)
        self.assertGreaterEqual(x, 100.0)
        self.assertLessEqual(x + width, 400.0 + 0.01)
        self.assertGreater(height, 8.0)

    def test_excel_anchor_and_image_dimensions_are_scaled_together(self):
        self.assertIn('signature_image.width = signature_width', self.app_source)
        self.assertIn('signature_image.height = signature_height', self.app_source)
        self.assertIn('pixels_to_EMU(signature_width)', self.app_source)
        self.assertIn('pixels_to_EMU(signature_height)', self.app_source)

    @unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
    def test_the_traveller_name_cannot_run_under_the_signature_cells(self):
        """Enlarging the group moved its left edge from 426 to 366, into the 410pt the
        traveller name was free to use. A participant list past ~354pt ran under the first
        signature cell."""
        name_x, name_width, group_x, group_width = app_module.travel_request_traveller_row_layout()
        self.assertLessEqual(name_x + name_width, group_x,
                             'the traveller name overlaps the signature group')
        # Positive control: the group really did move left of where the name may reach.
        self.assertLess(group_x, name_x + 410.0,
                        'this form no longer has the overlap this test guards')
        self.assertLessEqual(group_x + group_width, 612.0, 'the group runs off the page')

    @unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
    def test_the_name_keeps_its_full_width_when_no_one_signed(self):
        """Nothing sits beside it then, so truncating a long list would be a loss for free."""
        _, name_width, _, _ = app_module.travel_request_traveller_row_layout(has_signatures=False)
        self.assertEqual(name_width, 410.0)
        _, narrowed, _, _ = app_module.travel_request_traveller_row_layout(has_signatures=True)
        self.assertLess(narrowed, name_width)

    @unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
    def test_the_two_stay_clear_of_each_other_at_any_scale(self):
        """The pair is derived from one calculation, so raising the scale must not
        re-create the overlap the way raising it from 1.0 to 1.5 did."""
        original = app_module.SIGNATURE_STAMP_SCALE
        try:
            for scale in (1.0, 1.5, 2.0, 2.5):
                app_module.SIGNATURE_STAMP_SCALE = scale
                name_x, name_width, group_x, _ = app_module.travel_request_traveller_row_layout()
                self.assertLessEqual(name_x + name_width, group_x,
                                     f'name and signature group overlap at scale {scale}')
        finally:
            app_module.SIGNATURE_STAMP_SCALE = original

    def test_service_worker_cache_floor_is_v78(self):
        assert_cache_version_at_least(self, 78, self.app_source)


if __name__ == '__main__':
    unittest.main()
