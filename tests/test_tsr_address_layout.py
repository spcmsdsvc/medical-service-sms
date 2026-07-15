import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class TsrAddressLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')

    def test_address_uses_adaptive_multiline_layout(self):
        self.assertIn('function getAdaptiveTSRTableCellLayout(ctx, value, width, options={})', self.source)
        self.assertIn("const addressLayout = getAdaptiveTSRTableCellLayout(ctx, data['tsr-address'], rightW", self.source)
        self.assertIn('const customerAddressRowH = Math.max(rowH, customerLayout.requiredHeight, addressLayout.requiredHeight);', self.source)
        self.assertIn("'ADDRESS:', data['tsr-address'], 85, {layout:addressLayout}", self.source)

    def test_long_unbroken_address_tokens_are_wrapped(self):
        self.assertIn('while(remainingWord && ctx.measureText(remainingWord).width > maxWidth)', self.source)
        self.assertIn('canvasText(ctx, value, x + 10, y + 53, w - 20, layout.lineHeight, {maxLines:layout.lineCount});', self.source)


if __name__ == '__main__':
    unittest.main()
