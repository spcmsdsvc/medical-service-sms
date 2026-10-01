import json
import pathlib
import shutil
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = shutil.which('node')

# Runs the page's own PDF drawing functions against a recording context. Text width is a fixed
# amount per character, so this proves allocation and completeness, not pixel fit.
HARNESS = r"""
const fs = require('fs');
const source = fs.readFileSync(process.argv[2], 'utf8');
function block(start, end){
  const from = source.indexOf(start);
  const to = source.indexOf(end, from);
  if(from < 0 || to < 0) throw new Error('Missing block: ' + start);
  return source.slice(from, to);
}
const TSR_SIGNATURE_FOOTER_HEIGHT = 281;
let pages = [];
function createTSRCanvas(){
  const page = [];
  pages.push(page);
  let fontSize = 10;
  const ctx = {
    set font(value){ fontSize = Number(String(value).match(/([0-9.]+)px/)[1]); },
    get font(){ return `bold ${fontSize}px Arial`; },
    measureText(text){ return { width: String(text || '').length * fontSize * 0.55 }; },
    fillText(text, x, y){ page.push({ text:String(text), x, y }); },
    strokeRect(){}, fillRect(){}, beginPath(){}, moveTo(){}, lineTo(){}, stroke(){}, save(){}, restore(){}, drawImage(){}
  };
  return { canvas:{ width:1488, height:2105 }, ctx };
}
async function drawTSRCanvasHeader(ctx, data, margin, pageW, y){ return y + 188; }
async function drawTSRSignatureFooter(ctx, data, margin, pageW, y){ ctx.fillText('FOOTER', margin, y); return y + TSR_SIGNATURE_FOOTER_HEIGHT; }
function formatTSRServiceDateRange(){ return '2026-09-30'; }
// One eval: the blocks share const declarations, which are scoped to their eval.
(function(){ eval([
  block('function getTSRServiceCategoryText(data){', 'function tsrCheckHtml('),
  block('function canvasText(ctx, text, x, y, maxWidth, lineHeight, options={}){', 'const TSR_VECTOR_FONT_REGULAR_URL'),
  block('async function renderTSRPrintSheetCanvases(dataOverride=null){', 'let currentTSRPreviewPDFUrl'),
  'globalThis.api = { renderTSRPrintSheetCanvases, isTSRCategorySelected, planTSRMainPageLayout: typeof planTSRMainPageLayout === "function" ? planTSRMainPageLayout : null };'
].join(';')); })();
const { renderTSRPrintSheetCanvases, isTSRCategorySelected, planTSRMainPageLayout } = globalThis.api;

const lines = (prefix, count) => Array.from({length:count}, (_, i) => `${prefix}${i + 1}`).join('\n');
const makeParts = count => Array.from({length:count}, (_, i) => ({ item:'', number:`N${i + 1}`, description:`PART-${String(i + 1).padStart(2, '0')}-END`, qty:'1', dr:'' }));
const base = { 'tsr-customer-name':'Client', 'tsr-address':'Address', 'tsr-service-category':'Warranty', documents:[], parts:[] };
const scenarios = {
  eleven: { ...base, 'tsr-actions-taken':lines('A', 5), 'tsr-remarks':lines('R', 2), parts:makeParts(11) },
  forty: { ...base, 'tsr-actions-taken':lines('A', 60), 'tsr-remarks':lines('R', 2), parts:makeParts(40) },
  remarks: { ...base, 'tsr-actions-taken':lines('A', 5), 'tsr-remarks':lines('REMARK', 8) },
  complaint: { ...base, 'tsr-complaint':'COMPLAINT1\nCOMPLAINT2\nCOMPLAINT3', 'tsr-actions-taken':lines('A', 5) },
  others: { ...base, 'tsr-service-category':'Warranty, Others', 'tsr-service-category-other':'Site repair inspection' },
  short: { ...base, 'tsr-actions-taken':lines('A', 3), 'tsr-remarks':'R1' }
};
(async () => {
  const out = {};
  for(const [name, data] of Object.entries(scenarios)){
    pages = [];
    await renderTSRPrintSheetCanvases(data);
    out[name] = pages.map(page => page.map(item => item.text));
    out[name + 'MaxY'] = Math.max(...pages[0].map(item => item.y));
  }
  out.othersTicked = Boolean(isTSRCategorySelected(scenarios.others, 'Others'));
  out.repairTicked = Boolean(isTSRCategorySelected(scenarios.others, 'Repair'));
  pages = [];
  const { ctx } = createTSRCanvas();
  const plan = planTSRMainPageLayout(ctx, scenarios.short, { startY:598, pageHeight:2105, pageW:1368 });
  out.shortPlan = { complaintHeight:plan.complaintHeight, remarksHeight:plan.remarksHeight, actionsHeight:plan.actionsHeight, partRowsOnPage:plan.partRowsOnPage };
  process.stdout.write(JSON.stringify(out));
})().catch(err => { console.error(err); process.exit(1); });
"""


class TsrPdfLayoutSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')

    def test_hardcoded_caps_are_gone(self):
        self.assertNotIn('visiblePartRows', self.source)
        self.assertNotIn('const remarksHeight = 150;', self.source)
        self.assertNotIn('partRowCount', self.source)
        self.assertIn('function planTSRMainPageLayout(ctx, data, { startY, pageHeight, pageW })', self.source)
        self.assertIn('function drawTSRPartsTable(ctx, parts, x, y, pageW, startIndex=0, rowCount=parts.length)', self.source)

    def test_part_placeholder_follows_row_position(self):
        self.assertIn("document.querySelectorAll('#tsr-parts-rows .tsr-part-row').length+1", self.source)


@unittest.skipUnless(NODE, 'Node.js is required for the TSR PDF layout runtime tests')
class TsrPdfLayoutRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as folder:
            harness = pathlib.Path(folder) / 'harness.js'
            harness.write_text(HARNESS, encoding='utf-8')
            result = subprocess.run(
                [NODE, str(harness), str(ROOT / 'templates' / 'offline_tsr.html')],
                capture_output=True, text=True, encoding='utf-8', timeout=60,
            )
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        cls.out = json.loads(result.stdout)

    @staticmethod
    def part_names(count):
        return [f'PART-{index:02d}-END' for index in range(1, count + 1)]

    def test_eleven_parts_all_print_on_one_page(self):
        pages = self.out['eleven']
        self.assertEqual(len(pages), 1)
        for name in self.part_names(11):
            self.assertEqual(pages[0].count(name), 1, name)

    def test_blank_item_number_prints_row_position(self):
        self.assertIn('11', self.out['eleven'][0])

    def test_forty_parts_print_exactly_once_across_pages(self):
        pages = self.out['forty']
        self.assertGreater(len(pages), 1)
        everything = [text for page in pages for text in page]
        for name in self.part_names(40):
            self.assertEqual(everything.count(name), 1, name)
        self.assertTrue(any('on the next page' in text for text in pages[0]))
        self.assertIn('40', everything)

    def test_eight_remark_lines_stay_on_page_one(self):
        pages = self.out['remarks']
        self.assertEqual(len(pages), 1)
        for index in range(1, 9):
            self.assertIn(f'REMARK{index}', pages[0])

    def test_three_complaint_lines_print(self):
        for index in range(1, 4):
            self.assertIn(f'COMPLAINT{index}', self.out['complaint'][0])

    def test_others_category_is_ticked_and_printed(self):
        self.assertTrue(self.out['othersTicked'])
        self.assertFalse(self.out['repairTicked'])
        self.assertIn('Site repair inspection', self.out['others'][0])

    def test_short_tsr_fills_the_page_without_passing_the_margin(self):
        plan = self.out['shortPlan']
        self.assertEqual(plan['complaintHeight'], 88)
        self.assertEqual(plan['remarksHeight'], 150)
        self.assertEqual(plan['partRowsOnPage'], 2)
        # 2105 - (598 + 88) - 140 - 64 - 80 - 281 - 40 = 814 shared by the three sections.
        self.assertEqual(plan['actionsHeight'] + plan['remarksHeight'] + plan['partRowsOnPage'] * 34, 814)
        for name in ('eleven', 'forty', 'remarks', 'complaint', 'short'):
            self.assertLess(self.out[name + 'MaxY'], 2105 - 281, name)


if __name__ == '__main__':
    unittest.main()
