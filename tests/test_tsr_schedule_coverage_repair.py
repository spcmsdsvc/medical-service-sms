import unittest

import fitz

from app import (
    TSR_SCHEDULE_COVERAGE_REPAIR_MARKER,
    TSR_SCHEDULE_COVERAGE_REPAIR_MARKER_V1,
    TSR_SCHEDULE_COVERAGE_REPAIR_MARKER_V2,
    repair_tsr_single_day_multi_engineer_coverage_pdf,
)


class TsrScheduleCoverageRepairTests(unittest.TestCase):
    @staticmethod
    def make_legacy_team_pdf(marker=TSR_SCHEDULE_COVERAGE_REPAIR_MARKER_V2, compact=True):
        document = fitz.open()
        page = document.new_page(width=595.28, height=841.89)

        page.insert_text((30, 45), 'TECHNICAL SERVICE REPORT', fontsize=12)
        if compact:
            page.draw_rect(fitz.Rect(24, 239, 571, 278), color=(0, 0, 0), width=0.8)
            page.draw_line(fitz.Point(24, 252), fitz.Point(571, 252), color=(0, 0, 0), width=0.8)
        else:
            page.draw_rect(fitz.Rect(24, 239, 571, 252), color=(0, 0, 0), width=0.8)
            page.draw_rect(fitz.Rect(24, 252, 571, 278), color=(0, 0, 0), width=0.8)
        page.insert_text((31, 249), 'SCHEDULE COVERAGE', fontsize=7.5)
        page.insert_text((31, 267), 'ASSIGNED ENGINEER(S): Engineer One, Engineer Two', fontsize=7.2)

        page.draw_rect(fitz.Rect(24, 278, 571, 291), color=(0, 0, 0), width=0.8)
        page.insert_text((28, 288), 'COMPLAINT', fontsize=7.5)
        page.draw_rect(fitz.Rect(24, 291, 571, 320), color=(0, 0, 0), width=0.8)
        page.insert_text((28, 306), 'Preventive Maintenance', fontsize=7.5)

        page.draw_rect(fitz.Rect(24, 320, 571, 333), color=(0, 0, 0), width=0.8)
        page.insert_text((28, 330), 'ACTIONS TAKEN', fontsize=7.5)
        page.draw_rect(fitz.Rect(24, 333, 571, 520), color=(0, 0, 0), width=0.8)
        page.insert_text((28, 348), 'Checked system operation.', fontsize=7.5)

        page.draw_rect(fitz.Rect(24, 520, 571, 533), color=(0, 0, 0), width=0.8)
        page.insert_text((28, 530), 'REMARKS/RECOMMENDATIONS', fontsize=7.5)
        page.draw_rect(fitz.Rect(24, 533, 571, 560), color=(0, 0, 0), width=0.8)
        page.insert_text((28, 548), 'Unit is operational.', fontsize=7.5)

        page.draw_rect(fitz.Rect(24, 560, 571, 680), color=(0, 0, 0), width=0.8)
        page.insert_text((28, 575), 'SUBMITTED ORIGINAL DOCUMENTS', fontsize=7.5)
        page.insert_text((70, 730), 'SERVICED BY:', fontsize=7)
        page.insert_text((80, 760), 'ENGINEER ONE', fontsize=8)
        page.insert_text((360, 730), 'ACKNOWLEDGED BY:', fontsize=7)
        page.insert_text((365, 760), 'CUSTOMER NAME', fontsize=8)
        page.insert_text((24, 815), 'SPC Service TSR 004-2020', fontsize=6)

        document.set_metadata({'keywords': marker})
        raw = document.tobytes()
        document.close()
        return raw

    def test_original_full_coverage_table_is_removed(self):
        result = repair_tsr_single_day_multi_engineer_coverage_pdf(
            self.make_legacy_team_pdf(marker='', compact=False),
            ['Engineer One', 'Engineer Two'],
            serviced_by='Engineer One',
        )
        repaired = fitz.open(stream=result['pdf_bytes'], filetype='pdf')
        page_text = '\n'.join(page.get_text() for page in repaired)
        self.assertNotIn('SCHEDULE COVERAGE', page_text)
        self.assertIn('OTHER ASSIGNED ENGINEER(S): ENGINEER TWO', page_text)
        self.assertIn('COMPLAINT', page_text)
        repaired.close()

    def test_v1_and_v2_repairs_upgrade_to_team_footer_v3(self):
        for marker in (TSR_SCHEDULE_COVERAGE_REPAIR_MARKER_V1, TSR_SCHEDULE_COVERAGE_REPAIR_MARKER_V2):
            with self.subTest(marker=marker):
                result = repair_tsr_single_day_multi_engineer_coverage_pdf(
                    self.make_legacy_team_pdf(marker),
                    ['Engineer One', 'Engineer Two'],
                    serviced_by='Engineer One',
                )

                self.assertFalse(result['already_repaired'])
                self.assertEqual(result['other_assigned_engineers'], ['Engineer Two'])
                repaired = fitz.open(stream=result['pdf_bytes'], filetype='pdf')
                page_text = '\n'.join(page.get_text() for page in repaired)
                self.assertIn(TSR_SCHEDULE_COVERAGE_REPAIR_MARKER, repaired.metadata.get('keywords', ''))
                self.assertNotIn('SCHEDULE COVERAGE', page_text)
                self.assertIn('OTHER ASSIGNED ENGINEER(S): ENGINEER TWO', page_text)
                self.assertNotIn('OTHER ASSIGNED ENGINEER(S): ENGINEER ONE', page_text)
                self.assertIn('COMPLAINT', page_text)
                self.assertIn('ACTIONS TAKEN', page_text)
                self.assertIn('REMARKS/RECOMMENDATIONS', page_text)
                self.assertIn('UNIT IS OPERATIONAL', page_text.upper())
                self.assertIn('SPC Service TSR 004-2020', page_text)
                repaired.close()

    def test_team_footer_wraps_up_to_five_assigned_engineers(self):
        names = [
            'Engineer One',
            'Engineer Two',
            'Engineer Three',
            'Engineer Four',
            'Engineer Five',
        ]
        result = repair_tsr_single_day_multi_engineer_coverage_pdf(
            self.make_legacy_team_pdf(),
            names,
            serviced_by='Engineer One',
        )
        repaired = fitz.open(stream=result['pdf_bytes'], filetype='pdf')
        page_text = '\n'.join(page.get_text() for page in repaired)
        for name in names[1:]:
            self.assertIn(name.upper(), page_text)
        repaired.close()

    def test_team_footer_v3_is_idempotent(self):
        first = repair_tsr_single_day_multi_engineer_coverage_pdf(
            self.make_legacy_team_pdf(),
            ['Engineer One', 'Engineer Two'],
            serviced_by='Engineer One',
        )
        second = repair_tsr_single_day_multi_engineer_coverage_pdf(
            first['pdf_bytes'],
            ['Engineer One', 'Engineer Two'],
            serviced_by='Engineer One',
        )

        self.assertTrue(second['already_repaired'])
        self.assertEqual(second['pdf_bytes'], first['pdf_bytes'])


if __name__ == '__main__':
    unittest.main()
