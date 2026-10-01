import unittest
from types import SimpleNamespace
from unittest.mock import patch

try:
    import app as app_module
    from reportlab.pdfgen import canvas as canvas_module
except ModuleNotFoundError as import_error:  # pragma: no cover - local minimal test environments
    app_module = None
    APP_IMPORT_ERROR = import_error
else:
    APP_IMPORT_ERROR = None

CHECK_ROWS = {798: 'Warranty', 781: 'Repair', 764: 'PM', 747: 'Installation', 730: 'Others'}
PURPOSE_TEXT = 'Route 1: Manila → Tacloban\n  Visit 1: Sample Hospital\n\nNotes:\nRequest Type: Client Visit / Service'


@unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
class TravelRequestSiteVisitTests(unittest.TestCase):
    def test_visit_purpose_text(self):
        build = app_module.build_travel_visit_purpose
        self.assertEqual(build([], ['Site Visit']), 'Site Visit')
        self.assertEqual(build([], ['Others']), 'Others')
        self.assertEqual(build([], ['Repair', 'Warranty']), 'Repair - Warranty')
        self.assertEqual(build(['MobileArt / SN1'], ['PM']), 'PM of MobileArt / SN1')

    def render(self, tags, notes='', product_names='[]'):
        visit = SimpleNamespace(
            sequence_no=1, id=1, client_name='Sample Hospital', client=None,
            product_names_json=product_names, product_ids_json='[]', product_name='', product_id='',
            visit_purpose='', purpose_tags=tags, notes=notes,
        )
        route = SimpleNamespace(
            sequence_no=1, id=1, from_location='Manila', to_location='Tacloban',
            route_summary='', visits=[visit],
        )
        request_rec = SimpleNamespace(
            id=1, routes=[route], lines=[], client_name='Sample Hospital', currency_code='PHP',
            approved_amount=0, requested_amount=0, approval_signed_at=None, approved_at=None,
            approval_remarks='', approval_name_snapshot='', approval_signature_snapshot='',
        )
        ctx = {
            'request_no': 'TR-1', 'request_type': 'Client Visit / Service', 'purpose': PURPOSE_TEXT,
            'destination': 'Manila → Tacloban', 'travel_dates': '', 'requester_name': 'Test Engineer',
            'participant_names': [], 'participants_label': '', 'currency_code': 'PHP',
        }
        drawn = []
        original = canvas_module.Canvas.drawString

        def record(canvas_self, x, y, text, *args, **kwargs):
            drawn.append((x, y, text))
            return original(canvas_self, x, y, text, *args, **kwargs)

        with patch.object(app_module, 'travel_request_email_context', return_value=ctx), \
             patch.object(app_module, 'get_travel_request_signature_people', return_value=[]), \
             patch.object(app_module, 'travel_request_allows_airfare_c_o', return_value=False), \
             patch.object(canvas_module.Canvas, 'drawString', record):
            app_module.build_travel_request_accounting_pdf_bytes(request_rec)

        checks = {CHECK_ROWS[y] for x, y, text in drawn if text == 'X' and x == 37 and y in CHECK_ROWS}
        others_line = ' '.join(text for x, y, text in drawn if x == 130 and y <= 714 and y > 700)
        texts = [text for _, _, text in drawn]
        return checks, others_line, texts

    def test_site_visit_replaces_others_label_and_shows_remarks(self):
        checks, others_line, texts = self.render('Site Visit', notes='Ocular inspection of room')
        self.assertEqual(checks, {'Others'})
        self.assertIn('Site Visit', texts)
        self.assertNotIn('N/A', texts)
        self.assertEqual(others_line, 'Ocular inspection of room')

    def test_others_line_shows_remarks_not_route(self):
        checks, others_line, texts = self.render('Others', notes='Deliver documents')
        self.assertEqual(checks, {'Others'})
        self.assertNotIn('Site Visit', texts)
        self.assertEqual(others_line, 'Deliver documents')

        _, blank_line, _ = self.render('Others')
        self.assertEqual(blank_line, '')

    def test_checkboxes_follow_saved_tags_not_keywords_in_remarks(self):
        checks, _, _ = self.render('Repair, Others', notes='warranty claim to follow')
        self.assertEqual(checks, {'Repair', 'Others'})

    def test_legacy_request_without_tags_keeps_keyword_fallback(self):
        checks, _, _ = self.render('')
        self.assertEqual(checks, {'Others'})


if __name__ == '__main__':
    unittest.main()
