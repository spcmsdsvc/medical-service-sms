"""Print-ready reimbursement package: Excel layout, approval stamps, LPR long text."""

import pathlib
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import app as app_module


ROOT = pathlib.Path(__file__).resolve().parents[1]
FORMS = ROOT / 'forms'


def _row(row_id, day, work_lines=1, remarks='', **amounts):
    fields = {field: 0 for field in app_module.REIMBURSEMENT_EXPENSE_FIELDS}
    fields.update(amounts)
    return SimpleNamespace(
        id=row_id, row_date=day, shift_id=row_id, start_time='08:00', end_time='17:00',
        client_name='Davao Doctors Hospital (DDH)' if work_lines > 1 else '',
        task_name='System Installation' if work_lines > 1 else 'In Office',
        product_name='MobileDaRt Evolution (MX7c)' if work_lines > 2 else '',
        serial_number='MPF168167004' if work_lines > 2 else '',
        engineer_name='QA', remarks=remarks,
        row_total=sum(fields.values()), **fields,
    )


def _field_rect(writer, name):
    for annot in writer.pages[0].get('/Annots') or []:
        obj = annot.get_object()
        if str(obj.get('/T')) == name:
            return [float(v) for v in obj['/Rect']]
    return None


class ReimbursementExcelPrintTests(unittest.TestCase):
    def _workbook(self):
        header = SimpleNamespace(
            id=1, engineer_id=None, user_id=None,
            start_date=date(2026, 6, 1), end_date=date(2026, 6, 30),
            rows=[
                _row(1, date(2026, 6, 1), work_lines=3,
                     remarks='Angeles Medical Center installation support, coordination with biomed and '
                             'radiology heads for the acceptance test - PC18', transpo=250),
                _row(2, date(2026, 6, 2), work_lines=1, remarks='Parking - PC26', parking=50),
            ],
        )
        with app_module.app.test_request_context():
            return app_module.build_reimbursement_excel_workbook(header).active

    def test_rows_grow_with_wrapped_text(self):
        ws = self._workbook()
        long_row = ws.row_dimensions[7].height
        short_row = ws.row_dimensions[8].height
        self.assertGreater(long_row, 36, 'a 4-line Work Details row must not be clipped at 36 pt')
        self.assertLess(short_row, long_row)

    def test_a4_landscape_one_page_wide_with_page_numbers(self):
        ws = self._workbook()
        self.assertEqual(str(ws.page_setup.paperSize), str(ws.PAPERSIZE_A4))
        self.assertEqual(ws.page_setup.orientation, 'landscape')
        self.assertEqual(ws.page_setup.fitToWidth, 1)
        self.assertTrue(ws.print_options.horizontalCentered)
        self.assertIn('&P', ws.oddFooter.center.text or '')


class ReimbursementApprovalStampTests(unittest.TestCase):
    def _capture_box(self, template, **kwargs):
        from pypdf import PdfReader, PdfWriter
        writer = PdfWriter()
        writer.clone_document_from_reader(PdfReader(str(FORMS / template)))
        captured = {}

        def fake_overlay(header, page_width, page_height, box, label='APPROVED BY'):
            captured['box'] = [float(v) for v in box]
            return None

        with patch.object(app_module, 'reimbursement_is_approved_for_stamp', return_value=True), \
                patch.object(app_module, 'reimbursement_approval_signature_overlay_pdf', side_effect=fake_overlay):
            app_module.reimbursement_stamp_approval_signature(writer, SimpleNamespace(), **kwargs)
        return writer, captured['box']

    @staticmethod
    def _signature_top(box):
        # Mirrors reimbursement_approval_signature_overlay_pdf: the signature starts
        # 20 pt above the box bottom and may grow to SIGNATURE_STAMP_SCALE x its area.
        x, y, width, height = box
        return y + 20.0 + (height - 23.0) * app_module.SIGNATURE_STAMP_SCALE

    def test_pcv_signature_stays_below_the_approved_by_label(self):
        writer, box = self._capture_box('PETTY CASH VOUCHER FORM FILLABLE.pdf', field_name='APPROVED BY')
        field_top = _field_rect(writer, 'APPROVED BY')[3]
        self.assertLessEqual(self._signature_top(box), field_top + 0.5)

    def test_rfp_stamp_sits_in_the_approved_by_row(self):
        box = list(app_module.REIMBURSEMENT_RFP_APPROVAL_STAMP_BOX)
        _, captured = self._capture_box(
            'Request for Payment Form..pdf', field_name='APPROVED BY',
            fallback_box=box, force_fallback=True,
        )
        x, y, width, height = captured
        # "APPROVED BY:" label ends at x≈129; its row runs between the lines at y≈519 and y≈557,
        # and the NOTED BY label starts at y≈576.
        self.assertGreaterEqual(x, 129)
        self.assertLessEqual(x + width, 260)
        self.assertLessEqual(self._signature_top(captured), 557)
        self.assertGreaterEqual(y + 15.0, 505, 'printed name stays just under the APPROVED BY line')

    def test_both_rfp_builders_use_the_measured_box(self):
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        self.assertEqual(source.count('fallback_box=REIMBURSEMENT_RFP_APPROVAL_STAMP_BOX'), 2)
        self.assertNotIn('fallback_box=[44.65, 535.0, 213.85, 56.0]', source)


class ReimbursementPcvAmountAlignmentTests(unittest.TestCase):
    def test_amount_rows_are_not_nudged_below_their_particulars(self):
        from pypdf import PdfReader, PdfWriter
        writer = PdfWriter()
        writer.clone_document_from_reader(PdfReader(str(FORMS / 'PETTY CASH VOUCHER FORM FILLABLE.pdf')))
        before = _field_rect(writer, 'AMOUNTRow2')
        particulars_before = _field_rect(writer, 'PARTICULARSRow2')
        app_module.reimbursement_apply_pcv_field_formatting(writer)
        self.assertEqual(_field_rect(writer, 'AMOUNTRow2'), before)
        self.assertEqual(_field_rect(writer, 'PARTICULARSRow2'), particulars_before)


class LprLongTextTests(unittest.TestCase):
    LONG = ('Replacement parts for MobileDaRt Evolution at Davao Doctors Hospital, '
            'urgent field repair after detector failure')

    def _page(self, intended_for):
        from pypdf import PdfReader, PdfWriter
        writer = PdfWriter()
        writer.clone_document_from_reader(PdfReader(str(FORMS / 'LPR FORM.pdf')))
        values = {'Intended for': intended_for, 'Equipment': 'MobileDaRt'}
        app_module.lpr_fit_long_field_values(writer.pages[0], values)
        return writer, values

    def _annot(self, writer, name):
        for annot in writer.pages[0].get('/Annots') or []:
            obj = annot.get_object()
            if str(obj.get('/T')) == name:
                return obj
        return None

    def test_long_text_wraps_to_two_lines_at_a_fixed_size(self):
        writer, values = self._page(self.LONG)
        self.assertEqual(values['Intended for'].count('\n'), 1)
        self.assertEqual(values['Intended for'].replace('\n', ' '), self.LONG)
        annot = self._annot(writer, 'Intended for')
        size = float(str(annot['/DA']).split(' Tf')[0].split()[-1])
        self.assertGreaterEqual(size, 5.0)
        self.assertTrue(int(annot.get('/Ff', 0)) & 4096)

    def test_short_text_is_left_unchanged(self):
        writer, values = self._page('Field stock')
        self.assertEqual(values['Intended for'], 'Field stock')
        self.assertEqual(str(self._annot(writer, 'Intended for')['/DA']), '/Helv 0 Tf 0 g')
        self.assertEqual(values['Equipment'], 'MobileDaRt')


if __name__ == '__main__':
    unittest.main()
