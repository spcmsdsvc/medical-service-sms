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


class SignatureStampSizeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.tsr_source = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')

    @unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
    def test_shared_scale_is_one_point_five(self):
        self.assertEqual(app_module.SIGNATURE_STAMP_SCALE, 1.5)

    def test_all_generated_stamp_sites_use_the_scale(self):
        for marker in (
            'traveller_group_width = 160 * SIGNATURE_STAMP_SCALE',
            '28 * SIGNATURE_STAMP_SCALE',
            'width * 0.82 * SIGNATURE_STAMP_SCALE',
            'box_height = sig_area_height * SIGNATURE_STAMP_SCALE',
            'base_box_width * SIGNATURE_STAMP_SCALE',
            '34.0 * SIGNATURE_STAMP_SCALE',
            '13 * SIGNATURE_STAMP_SCALE',
            '18.0 * SIGNATURE_STAMP_SCALE',
            '86.0 * SIGNATURE_STAMP_SCALE',
            'SIGNATURE_STAMP_SCALE\n                )',
        ):
            self.assertIn(marker, self.app_source, f'missing shared scale usage: {marker!r}')

        self.assertIn('const SIGNATURE_STAMP_SCALE = Number({{ signature_stamp_scale|tojson }}) || 1.5;', self.tsr_source)
        self.assertIn('const sigH = Math.round(68 * SIGNATURE_STAMP_SCALE);', self.tsr_source)
        self.assertIn('const sigImageW = Math.min(340, Math.round(250 * SIGNATURE_STAMP_SCALE));', self.tsr_source)
        self.assertIn('margin + 70, sigY, sigImageW, sigH', self.tsr_source)

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

    def test_service_worker_cache_floor_is_v78(self):
        assert_cache_version_at_least(self, 78, self.app_source)


if __name__ == '__main__':
    unittest.main()
