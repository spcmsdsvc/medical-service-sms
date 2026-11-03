"""Schedule form: warn when the machine has no BSID (plans.md, 2026-11-03)."""

import json
import pathlib
import re
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / 'templates' / 'timeline.html').read_text(encoding='utf-8')
NODE = pathlib.Path(r"C:\Users\Jonamar\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe")


def _function_source(name):
    match = re.search(rf'    function {name}\(.*?\n    }}\n', TEMPLATE, re.S)
    if not match:
        raise AssertionError(f'{name} not found in timeline.html')
    return match.group(0)


class ScheduleBsidWarningTests(unittest.TestCase):
    def test_warning_element_is_hidden_by_default(self):
        self.assertRegex(TEMPLATE, r'id="product-bsid-warning"[^>]*class="[^"]*\bd-none\b')
        self.assertIn("Its calibration certificate can't be sent until an admin adds one in Product Inventory.", TEMPLATE)

    def test_warning_follows_every_calibration_box_redraw(self):
        self.assertIn('renderProductBsidWarning(product);', _function_source('renderProductCalibrationStatus'))

    @unittest.skipUnless(NODE.exists(), 'node runtime unavailable')
    def test_shown_only_for_product_inventory_machine_without_bsid(self):
        cases = {
            'none': None,
            'blank': {'equipment_source': 'product', 'bsid': '  '},
            'legacy_default_source': {'bsid': ''},
            'with_bsid': {'equipment_source': 'product', 'bsid': '175787'},
            'genoray': {'equipment_source': 'genoray', 'bsid': ''},
            'vieworks': {'equipment_source': 'vieworks', 'bsid': ''},
        }
        script = (
            "const classes = new Set(['d-none']);"
            "const el = {classList: {toggle: (c, on) => on ? classes.add(c) : classes.delete(c)}};"
            "const document = {getElementById: () => el};"
            + _function_source('renderProductBsidWarning') +
            f"const cases = {json.dumps(cases)}; const out = {{}};"
            "for (const [k, v] of Object.entries(cases)) { renderProductBsidWarning(v); out[k] = !classes.has('d-none'); }"
            "console.log(JSON.stringify(out));"
        )
        result = subprocess.run([str(NODE), '-e', script], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            'none': False, 'blank': True, 'legacy_default_source': True,
            'with_bsid': False, 'genoray': False, 'vieworks': False,
        })

    def test_saving_is_not_blocked(self):
        # Only the element and its one lookup: no save handler reads the warning.
        self.assertEqual(TEMPLATE.count('id="product-bsid-warning"'), 1)
        self.assertEqual(TEMPLATE.count("getElementById('product-bsid-warning')"), 1)
        self.assertEqual(TEMPLATE.count('renderProductBsidWarning('), 2)  # definition and one call


if __name__ == '__main__':
    unittest.main()
