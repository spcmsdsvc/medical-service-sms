import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class TSRCheckboxRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')

    def test_machine_type_medical_is_checked(self):
        self.assertIn("tsrCheckHtml(true,'Medical')", self.source)
        self.assertIn("canvasCheckbox(ctx, margin + pageW - 300, y + 78, 'Medical', true", self.source)

    def test_all_checked_boxes_use_shared_vector_renderer(self):
        self.assertIn('canvasCheckbox = function(ctx, x, y, label, checked, options={})', self.source)
        self.assertIn('ctx.lineTo(x + box * 0.42, top + box * 0.78);', self.source)
        self.assertIn("tsrCheckHtml = function(checked, label, extra='')", self.source)
        for category_key in ('Warranty', 'Checkup', 'Preventive', 'Installation', 'Others'):
            self.assertIn(f"isTSRCategorySelected(data,'{category_key}')", self.source)


if __name__ == '__main__':
    unittest.main()
