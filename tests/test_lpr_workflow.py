import io
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]

try:
    from pypdf import PdfReader
    import app as app_module
except Exception as exc:  # pragma: no cover - allows source-only test runs without app deps
    PdfReader = None
    app_module = None
    APP_IMPORT_ERROR = exc
else:
    APP_IMPORT_ERROR = None


class LPRWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.template_source = (ROOT / 'templates' / 'lpr.html').read_text(encoding='utf-8')

    def test_lpr_page_and_routes_are_present(self):
        for route in (
            "@app.route('/lpr')",
            "@app.route('/save_lpr', methods=['POST'])",
            "@app.route('/submit_lpr/<int:lpr_id>', methods=['POST'])",
            "@app.route('/upload_lpr_attachments/<int:lpr_id>', methods=['POST'])",
            "@app.route('/delete_all_lpr_attachments/<int:lpr_id>', methods=['POST'])",
        ):
            self.assertIn(route, self.app_source)
        self.assertIn("href=\"/lpr\"", (ROOT / 'templates' / 'layout.html').read_text(encoding='utf-8'))
        self.assertIn('lpr_procurement', self.app_source)

    def test_lpr_form_contains_dynamic_items_and_attachment_controls(self):
        for marker in (
            'addLprItem',
            'saveLprDraft',
            'previewLpr',
            'submitLpr',
            'uploadLprAttachments',
            'deleteAllLprAttachments',
            '35MB per file',
            'first eight continue on additional pages',
        ):
            self.assertIn(marker, self.template_source)

        for field_id, option_value in (
            ('lprBranch', 'BC01'),
            ('lprClass', 'CC01'),
            ('lprDept', 'DC01'),
            ('lprProduct', 'PC18'),
        ):
            self.assertIn(f'id="{field_id}"', self.template_source)
            self.assertIn(f'value="{option_value}"', self.template_source)
        for optional_label in ('PO No. <span', 'Invoice No. <span', 'Received By <span'):
            self.assertIn(optional_label, self.template_source)
        self.assertIn('.lpr-field select', self.template_source)
        for retained_code in ('PC18', 'PC19', 'PC20', 'PC21', 'PC22', 'PC23', 'PC24', 'PC26'):
            self.assertIn(f'value="{retained_code}"', self.template_source)
        for removed_code in ('PC01', 'PC17', 'PC25'):
            self.assertNotIn(f'value="{removed_code}"', self.template_source)
        self.assertIn('<optgroup label="Medical">', self.template_source)
        self.assertIn('<optgroup label="Admin">', self.template_source)

    def test_lpr_is_separately_launch_gated(self):
        self.assertIn("app.config['LPR_ENABLED']", self.app_source)
        self.assertIn("def lpr_enabled()", self.app_source)
        self.assertIn("'message': 'Local Purchase Requisition is not available yet.'", self.app_source)
        self.assertIn("{% if lpr_enabled %}", (ROOT / 'templates' / 'layout.html').read_text(encoding='utf-8'))
        self.assertIn("{% if lpr_enabled %}", (ROOT / 'templates' / 'approvals.html').read_text(encoding='utf-8'))

    def test_lpr_pdf_fills_official_fields_and_continues_after_eight_rows(self):
        if app_module is None or PdfReader is None:
            self.skipTest(f'app dependencies unavailable: {APP_IMPORT_ERROR}')

        with app_module.app.app_context():
            app_module.ensure_lpr_tables()
            header = app_module.LPRHeader(
                user_id=1,
                lpr_no='LPR-20990101-01',
                request_date=app_module.get_manila_today(),
                branch_code='BC01',
                class_code='CC04',
                dept_code='DC03',
                product_code='PC18',
                intended_for='QA fixture',
                equipment='Demo unit',
                requester_name_snapshot='QA Requester',
                status='Draft',
            )
            for index in range(9):
                header.items.append(app_module.LPRItem(
                    row_index=index,
                    description=f'Item {index + 1}',
                    quantity=index + 1,
                    unit_measure='pcs',
                    unit_price=100,
                    line_total=(index + 1) * 100,
                    note='QA note',
                ))

            app_module.db.session.add(header)
            app_module.db.session.flush()
            try:
                pdf_bytes = app_module.lpr_fill_pdf_bytes(header)
                reader = PdfReader(io.BytesIO(pdf_bytes))
                fields = reader.get_fields() or {}
                text = '\n'.join(page.extract_text() or '' for page in reader.pages)
                self.assertEqual(len(reader.pages), 2)
                self.assertEqual(fields['Branch']['/V'], 'BC01')
                self.assertEqual(fields['ITEM  DESCRIPTION']['/V'], 'Item 1')
                self.assertIn('Item 9', text)
                self.assertIn('LOCAL PURCHASE REQUISITION - CONTINUED', text)
            finally:
                app_module.db.session.rollback()

    def test_lpr_validation_requires_positive_item_and_php_only(self):
        if app_module is None:
            self.skipTest(f'app dependencies unavailable: {APP_IMPORT_ERROR}')

        items, total = app_module.lpr_validate_items([{
            'description': 'Test item',
            'quantity': 2,
            'unit_measure': 'pcs',
            'unit_price': 125,
        }])
        self.assertEqual(total, 250.0)
        self.assertEqual(items[0]['line_total'], 250.0)
        self.assertEqual(app_module.LPR_EDITABLE_STATUSES, {'Draft', 'Rejected', 'Returned'})
        self.assertIn("header.currency_code = 'PHP'", self.app_source)


if __name__ == '__main__':
    unittest.main()
