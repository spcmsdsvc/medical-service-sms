import io
import os
import pathlib
import tempfile
import unittest

from sqlalchemy import create_engine


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
        # Sidebar links render through the nav_link() macro in layout.html.
        self.assertIn("nav_link('/lpr'", (ROOT / 'templates' / 'layout.html').read_text(encoding='utf-8'))
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

    def test_lpr_is_enabled_in_the_released_workflow(self):
        self.assertIn("def lpr_enabled()", self.app_source)
        self.assertIsNotNone(app_module)
        self.assertTrue(app_module.lpr_enabled())
        self.assertTrue(app_module.embedded_lpr_enabled())
        self.assertIn("{% if lpr_enabled %}", (ROOT / 'templates' / 'layout.html').read_text(encoding='utf-8'))
        self.assertIn("{% if lpr_enabled %}", (ROOT / 'templates' / 'approvals.html').read_text(encoding='utf-8'))

    def test_lpr_pdf_uses_official_template_for_every_eight_item_page(self):
        if app_module is None or PdfReader is None:
            self.skipTest(f'app dependencies unavailable: {APP_IMPORT_ERROR}')

        with app_module.app.app_context():
            app_module.ensure_lpr_tables()
            try:
                for item_count in (1, 8, 9, 16, 17):
                    header = app_module.LPRHeader(
                        user_id=1,
                        lpr_no=f'LPR-20990101-{item_count:02d}',
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
                    for index in range(item_count):
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
                    pdf_bytes = app_module.lpr_fill_pdf_bytes(header)
                    reader = PdfReader(io.BytesIO(pdf_bytes))
                    expected_pages = max(1, (item_count + 7) // 8)
                    self.assertEqual(len(reader.pages), expected_pages)
                    for page in reader.pages:
                        self.assertAlmostEqual(float(page.mediabox.width), 576.0, places=2)
                        self.assertAlmostEqual(float(page.mediabox.height), 360.0, places=2)
                        page_text = page.extract_text() or ''
                        self.assertIn('SHIMADZU PHILIPPINES CORPORATION', page_text)
                        self.assertIn('Local Purchase Requisition Form', page_text)

                    fields = reader.get_fields() or {}
                    self.assertEqual(fields['Branch']['/V'], 'BC01')
                    self.assertEqual(fields['ITEM  DESCRIPTION']['/V'], 'Item 1')
                    self.assertEqual(fields['ITEM  DESCRIPTION-6']['/V'], 'Item 8' if item_count >= 8 else '')

                    if item_count <= 8:
                        self.assertNotIn('CONTINUATION - ITEMS', '\n'.join(
                            page.extract_text() or '' for page in reader.pages
                        ))
                    else:
                        for page_number, start in enumerate(range(8, item_count, 8), start=2):
                            chunk = list(range(start + 1, min(start + 8, item_count) + 1))
                            page_text = reader.pages[page_number - 1].extract_text() or ''
                            self.assertIn(
                                f'CONTINUATION - ITEMS {chunk[0]}-{chunk[-1]} - PAGE {page_number}',
                                page_text,
                            )
                            for item_number in chunk:
                                self.assertIn(f'Item {item_number}', page_text)
                            if chunk[-1] < item_count:
                                self.assertNotIn(f'Item {chunk[-1] + 1}', page_text)

                            self.assertIn('BC01', page_text)
                            self.assertIn('CC04', page_text)
                            self.assertIn('QA fixture', page_text)
                            self.assertIn('Demo unit', page_text)

                            # Continuation fields are painted into page content and have no
                            # widgets left, so duplicate official names cannot bleed into page
                            # one or be edited by a PDF viewer.
                            self.assertFalse(reader.pages[page_number - 1].get('/Annots'))

                        full_text = '\n'.join(page.extract_text() or '' for page in reader.pages)
                        self.assertNotIn('LOCAL PURCHASE REQUISITION - CONTINUED', full_text)
                        self.assertNotIn('Continuation total:', full_text)
                    app_module.db.session.rollback()
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

    def test_standalone_lpr_creation_is_single_flight_and_idempotent(self):
        self.assertIn('let lprSavePromise = null;', self.template_source)
        self.assertIn('if(lprSavePromise) return lprSavePromise;', self.template_source)
        self.assertIn('creation_token:ensureLprCreationToken()', self.template_source)
        self.assertIn('function fillServerResponse(data)', self.template_source)
        self.assertIn('fillServerResponse(data.item)', self.template_source)
        self.assertIn("'creation_token': header.creation_token or ''", self.app_source)
        self.assertIn("'token_reconciled': token_reconciled", self.app_source)
        self.assertIn('normalize_lpr_creation_token', self.app_source)
        self.assertIn('uq_lpr_header_creation_token', self.app_source)

        if app_module is None:
            self.skipTest(f'app dependencies unavailable: {APP_IMPORT_ERROR}')

        file_handle, database_path = tempfile.mkstemp(suffix='.db')
        os.close(file_handle)
        try:
            with app_module.app.app_context():
                extension = app_module.app.extensions['sqlalchemy']
                engines = extension._app_engines[app_module.app]
                original_engine = engines[None]
                original_ready = app_module._lpr_tables_ready
                test_engine = create_engine(f"sqlite:///{database_path.replace(os.sep, '/')}")
                try:
                    engines[None] = test_engine
                    app_module._lpr_tables_ready = False
                    app_module.db.create_all()
                    user = app_module.User(
                        username='lpr-idempotency-user',
                        password='test-only',
                        role='engineer'
                    )
                    app_module.db.session.add(user)
                    app_module.db.session.commit()

                    client = app_module.app.test_client()
                    with client.session_transaction() as session:
                        session['_user_id'] = str(user.id)

                    payload = {
                        'creation_token': 'lpr-test-creation-token-20260730',
                        'request_date': '2026-07-30',
                        'branch_code': 'BC01',
                        'class_code': 'CC04',
                        'dept_code': 'DC03',
                        'product_code': 'PC23',
                        'intended_for': 'QA inventory',
                        'equipment': 'Field service stock',
                        'items': [{
                            'description': 'SSD',
                            'quantity': 1,
                            'unit_measure': 'pc',
                            'unit_price': 200
                        }]
                    }
                    first = client.post('/save_lpr', json=payload)
                    second = client.post('/save_lpr', json=payload)
                    first_data = first.get_json()
                    second_data = second.get_json()

                    self.assertEqual(first.status_code, 200)
                    self.assertEqual(second.status_code, 200)
                    self.assertFalse(first_data['idempotent_replay'])
                    self.assertTrue(second_data['idempotent_replay'])
                    self.assertEqual(first_data['item']['id'], second_data['item']['id'])
                    self.assertEqual(first_data['item']['creation_token'], payload['creation_token'])

                    # Reopening a draft must restore the server token before the user adds
                    # another item and saves the same LPR again.
                    lpr_id = first_data['item']['id']
                    loaded = client.get(f'/get_lpr/{lpr_id}')
                    loaded_data = loaded.get_json()
                    self.assertEqual(loaded.status_code, 200)
                    self.assertEqual(loaded_data['item']['creation_token'], payload['creation_token'])
                    reopened_payload = dict(
                        payload,
                        id=lpr_id,
                        items=payload['items'] + [{
                            'description': 'LAN cable',
                            'quantity': 2,
                            'unit_measure': 'pcs',
                            'unit_price': 15
                        }]
                    )
                    reopened = client.post('/save_lpr', json=reopened_payload)
                    reopened_data = reopened.get_json()
                    self.assertEqual(reopened.status_code, 200)
                    self.assertFalse(reopened_data['token_reconciled'])
                    self.assertEqual(reopened_data['item']['id'], lpr_id)
                    self.assertEqual(reopened_data['item']['item_count'], 2)

                    # A stale browser token is reconciled only when the authorized LPR id
                    # identifies the draft; the persisted server token remains unchanged.
                    stale_payload = dict(
                        reopened_payload,
                        creation_token='lpr-stale-client-token-20260730',
                        items=reopened_payload['items'] + [{
                            'description': 'USB adapter',
                            'quantity': 1,
                            'unit_measure': 'pc',
                            'unit_price': 10
                        }]
                    )
                    repaired = client.post('/save_lpr', json=stale_payload)
                    repaired_data = repaired.get_json()
                    self.assertEqual(repaired.status_code, 200)
                    self.assertTrue(repaired_data['token_reconciled'])
                    self.assertEqual(repaired_data['item']['creation_token'], payload['creation_token'])
                    self.assertEqual(repaired_data['item']['item_count'], 3)
                    self.assertEqual(
                        app_module.LPRHeader.query.filter_by(user_id=user.id).count(),
                        1
                    )
                finally:
                    app_module.db.session.remove()
                    app_module._lpr_tables_ready = original_ready
                    engines[None] = original_engine
                    test_engine.dispose()
        finally:
            if os.path.exists(database_path):
                os.unlink(database_path)


class LPRSignaturePlacementTests(unittest.TestCase):
    """The approver signature was stamped a whole row above its own line.

    Hardcoded overlay coordinates put it on top of the Invoice No. label, and the requester
    signature on top of Equipment. The stamp is now derived from the template's own field
    rectangles, so these tests assert the geometry rather than the constants.
    """

    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')

    def test_signature_placement_is_not_hardcoded_anymore(self):
        # assertFalse rather than assertNotIn: assertNotIn prints the whole haystack on
        # failure, which for app.py is tens of thousands of lines of unreadable output.
        for dead in ('draw_signature(header.requester_signature_snapshot, 145, 49',
                     'draw_signature(header.approval_signature_snapshot, 397, 63'):
            self.assertFalse(
                dead in self.app_source,
                f'hardcoded signature coordinates are back: {dead!r}. They put the approver '
                'signature on top of the Invoice No. row.'
            )

        self.assertIn('def lpr_form_field_rects(', self.app_source)
        self.assertIn('def lpr_signature_box(', self.app_source)

        # The call site must actually use the computed boxes, not just define the helpers.
        for call in ('draw_signature(header.requester_signature_snapshot, *requester_box)',
                     'draw_signature(header.approval_signature_snapshot, *approver_box)'):
            self.assertTrue(
                call in self.app_source,
                f'signature stamping no longer goes through the computed box: {call!r}'
            )

    # The row sitting directly above each signature line on this template. The bound has to
    # be per-field: 'Intended for' is above the APPROVER line, and using it for both let the
    # requester stamp grow 14pt further than its own neighbour allows -- far enough to cover
    # the Equipment row whole while the test still passed.
    ROW_ABOVE = {'Requested by': 'Equipment', 'Approved by': 'Invoice No'}

    @unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
    def test_each_signature_stays_within_one_row_of_its_own_line(self):
        """The enlarged stamp may rise into the row above, but not past that row's top.

        The original assertion was that the stamp stayed inside its own field. That bound was
        deliberately loosened when the owner accepted overflow in exchange for a bigger
        signature -- so this now allows exactly one row of encroachment and no more. The
        downward bound and both horizontal bounds are unchanged: nothing about enlarging the
        stamp required giving those up.
        """
        template = app_module.find_lpr_form_template_path()
        if not template:
            self.skipTest('LPR FORM.pdf is not available in this environment')

        rects = app_module.lpr_form_field_rects(PdfReader(template))
        self.assertIn('Requested by', rects, 'template field rectangles could not be read')
        self.assertIn('Approved by', rects)

        for field_name, row_above in self.ROW_ABOVE.items():
            field = rects[field_name]
            x, y, width, height = app_module.lpr_signature_box(field, None)
            fx0, fy0, fx1, fy1 = field
            row_above_top = rects[row_above][3]

            # Positive control: the named row really is the one directly above this line.
            self.assertGreater(rects[row_above][1], fy0,
                               f'{row_above} is not above {field_name}')
            self.assertLess(rects[row_above][1] - fy0, 20,
                            f'{row_above} is not the row IMMEDIATELY above {field_name}')

            self.assertGreaterEqual(y + 0.01, fy0, f'{field_name} stamp starts below its row')
            self.assertLessEqual(y + height, row_above_top + 0.01,
                                 f'{field_name} stamp rises past the top of {row_above}')
            self.assertGreaterEqual(x + 0.01, fx0, f'{field_name} stamp starts left of its line')
            self.assertLessEqual(x + width, fx1 + 0.01, f'{field_name} stamp runs past its line')

    @unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
    def test_approver_signature_does_not_swallow_the_invoice_row(self):
        """The reported defect, re-bounded rather than abandoned.

        The approver stamp may now reach into the Invoice No. row -- measured at 4.5pt on a
        rendered form -- but it must never cover that row outright, which is what the original
        report was about.
        """
        template = app_module.find_lpr_form_template_path()
        if not template:
            self.skipTest('LPR FORM.pdf is not available in this environment')

        rects = app_module.lpr_form_field_rects(PdfReader(template))
        _, y, _, height = app_module.lpr_signature_box(rects['Approved by'], None)
        invoice_bottom, invoice_top = rects['Invoice No'][1], rects['Invoice No'][3]

        # Positive control: the Invoice No. row really does sit directly above the approver
        # line, so a tall enough stamp genuinely would collide with it.
        self.assertGreater(invoice_bottom, rects['Approved by'][1])
        self.assertLess(invoice_bottom - rects['Approved by'][1], 20)

        self.assertLessEqual(y + height, invoice_top + 0.01,
                             'approver signature covers the Invoice No. row outright')

    @unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
    def test_signature_box_falls_back_when_the_field_is_missing(self):
        fallback = (1.0, 2.0, 3.0, 4.0)
        for bad in (None, (), (1, 2), (0, 0, 5, 1)):
            self.assertEqual(app_module.lpr_signature_box(bad, fallback), fallback)

    @unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
    def test_the_fallback_box_is_enlarged_too(self):
        """A fallback left at the old size hands back a small signature exactly where nobody
        is looking -- on a template whose field rectangles could not be read."""
        x, y, width, height = app_module.lpr_scaled_fallback_box(189.1, 38.3, 83.8, 12.45)
        self.assertAlmostEqual(width, 83.8 * app_module.SIGNATURE_STAMP_SCALE, places=3)
        self.assertAlmostEqual(height, 12.45 * app_module.SIGNATURE_STAMP_SCALE, places=3)
        # Grows leftward: the right edge stays on the end of the signature line.
        self.assertAlmostEqual(x + width, 189.1 + 83.8, places=3)
        self.assertEqual(y, 38.3)


if __name__ == '__main__':
    unittest.main()
