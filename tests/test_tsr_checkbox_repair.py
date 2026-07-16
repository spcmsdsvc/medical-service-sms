import unittest

import fitz

from app import TSR_CHECKBOX_REPAIR_MARKER, repair_tsr_pdf_checkboxes


class TsrCheckboxRepairTests(unittest.TestCase):
    @staticmethod
    def make_pdf():
        document = fitz.open()
        page = document.new_page(width=595.28, height=841.89)
        page.insert_text((430, 70), 'Medical', fontsize=8)
        page.insert_text((40, 300), 'SERVICE CATEGORY', fontsize=8)
        page.insert_text((48, 330), 'Warranty', fontsize=8)
        page.insert_text((40, 450), 'SUBMITTED ORIGINAL DOCUMENTS', fontsize=8)
        page.insert_text((48, 480), 'Service Report', fontsize=8)
        raw = document.tobytes()
        document.close()
        return raw

    def test_selected_marks_are_added_without_rebuilding_pdf(self):
        original = self.make_pdf()
        result = repair_tsr_pdf_checkboxes(
            original,
            {
                'tsr-service-category': 'Warranty',
                'documents': ['Service Report'],
            },
        )

        self.assertFalse(result['already_repaired'])
        self.assertEqual(result['missing_labels'], [])
        self.assertEqual(result['marks_added'], ['Medical', 'Warranty', 'Service Report'])
        self.assertNotEqual(result['pdf_bytes'], original)

        repaired = fitz.open(stream=result['pdf_bytes'], filetype='pdf')
        self.assertEqual(len(repaired), 1)
        self.assertGreaterEqual(len(repaired[0].get_drawings()), 6)
        repaired.close()

    def test_repair_is_idempotent(self):
        first = repair_tsr_pdf_checkboxes(
            self.make_pdf(),
            {'tsr-service-category': 'Warranty', 'documents': ['Service Report']},
        )
        second = repair_tsr_pdf_checkboxes(
            first['pdf_bytes'],
            {'tsr-service-category': 'Warranty', 'documents': ['Service Report']},
        )

        self.assertTrue(second['already_repaired'])
        self.assertEqual(second['marks_added'], [])
        self.assertEqual(second['pdf_bytes'], first['pdf_bytes'])

        document = fitz.open(stream=second['pdf_bytes'], filetype='pdf')
        self.assertIn(TSR_CHECKBOX_REPAIR_MARKER, document.metadata.get('keywords', ''))
        document.close()

    def test_unselected_categories_and_documents_are_not_marked(self):
        result = repair_tsr_pdf_checkboxes(self.make_pdf(), {})

        self.assertEqual(result['marks_added'], ['Medical'])
        self.assertEqual(result['missing_labels'], [])


if __name__ == '__main__':
    unittest.main()
