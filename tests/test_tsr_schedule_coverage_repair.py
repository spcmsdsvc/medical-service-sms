import unittest

import fitz

from app import (
    TSR_HISTORICAL_COVERAGE_REPAIR_MARKER,
    TSR_SCHEDULE_COVERAGE_REPAIR_MARKER,
    TSR_SCHEDULE_COVERAGE_REPAIR_MARKER_V1,
    TSR_SCHEDULE_COVERAGE_REPAIR_MARKER_V2,
    TSR_VECTOR_PDF_CREATOR,
    ensure_authoritative_tsr_coverage_pdf,
    format_tsr_service_date_range,
    repair_tsr_multiday_historical_coverage_pdf,
    repair_tsr_multiday_service_date_range_pdf,
    repair_tsr_single_day_multi_engineer_coverage_pdf,
    stamp_tsr_single_day_team_footer,
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
        page.draw_rect(fitz.Rect(24, 680, 571, 715), color=(0, 0, 0), width=0.8)
        page.draw_line(fitz.Point(145, 680), fitz.Point(145, 715), color=(0, 0, 0), width=0.8)
        page.insert_text((28, 692), 'DATE OF SERVICE', fontsize=7)
        page.insert_text((150, 692), 'TIME STARTED', fontsize=7)
        page.insert_text((28, 708), '2026-07-13', fontsize=8)
        page.insert_text((150, 708), '08:00', fontsize=8)
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

    @staticmethod
    def make_original_vector_pdf(page_count=2):
        document = fitz.open()
        for index in range(page_count):
            page = document.new_page(width=595.28, height=841.89)
            page.insert_text((30, 45), 'SHIMADZU PHILIPPINES CORPORATION', fontsize=10)
            page.insert_text((30, 80), 'TECHNICAL SERVICE REPORT', fontsize=12)
            page.insert_text((440, 80), '20260715-01-AM', fontsize=8)
            page.insert_text((30, 120), f'ORIGINAL PAGE {index + 1}', fontsize=9)
            if index == 0:
                page.draw_rect(fitz.Rect(24, 630, 571, 690), color=(0, 0, 0), width=0.8)
                page.draw_line(fitz.Point(145, 630), fitz.Point(145, 690), color=(0, 0, 0), width=0.8)
                page.insert_text((28, 646), 'DATE OF SERVICE', fontsize=7)
                page.insert_text((150, 646), 'TIME STARTED', fontsize=7)
                page.insert_text((28, 673), '2026-07-13', fontsize=8)
                page.insert_text((150, 673), '08:00', fontsize=8)
                page.insert_text((70, 730), 'SERVICED BY:', fontsize=7)
                page.insert_text((80, 760), 'ENGINEER ONE', fontsize=8)
                page.insert_text((24, 815), 'SPC Service TSR 004-2020', fontsize=6)
        document.set_metadata({'creator': TSR_VECTOR_PDF_CREATOR})
        raw = document.tobytes()
        document.close()
        return raw

    @staticmethod
    def coverage_rows():
        return [
            {
                'date_iso': '2026-07-13',
                'date_label': 'Jul 13, 2026',
                'time_start': '08:00',
                'time_end': '17:00',
                'engineer_names': ['Engineer One', 'Engineer Two'],
                'engineer_ids': [1, 2],
                'shift_ids': [101],
            },
            {
                'date_iso': '2026-07-14',
                'date_label': 'Jul 14, 2026',
                'time_start': '13:00',
                'time_end': '17:00',
                'engineer_names': ['Engineer One'],
                'engineer_ids': [1],
                'shift_ids': [102],
            },
        ]

    def test_multiday_repair_inserts_vector_page_after_first_page(self):
        result = repair_tsr_multiday_historical_coverage_pdf(
            self.make_original_vector_pdf(page_count=2),
            self.coverage_rows(),
        )
        repaired = fitz.open(stream=result['pdf_bytes'], filetype='pdf')
        self.assertEqual(len(repaired), 3)
        self.assertIn('ORIGINAL PAGE 1', repaired[0].get_text())
        self.assertIn('SCHEDULE COVERAGE', repaired[1].get_text())
        self.assertIn('JULY 13, 2026', repaired[1].get_text().upper())
        self.assertIn('1:00 PM - 5:00 PM', repaired[1].get_text())
        self.assertIn('ENGINEER TWO', repaired[1].get_text().upper())
        self.assertIn('ORIGINAL PAGE 2', repaired[2].get_text())
        self.assertIn(TSR_HISTORICAL_COVERAGE_REPAIR_MARKER, repaired.metadata.get('keywords', ''))
        repaired.close()

    def test_multiday_repair_is_idempotent(self):
        first = repair_tsr_multiday_historical_coverage_pdf(
            self.make_original_vector_pdf(),
            self.coverage_rows(),
        )
        second = repair_tsr_multiday_historical_coverage_pdf(first['pdf_bytes'], self.coverage_rows())
        self.assertTrue(second['already_repaired'])
        self.assertEqual(second['pdf_bytes'], first['pdf_bytes'])

    def test_service_date_range_uses_compact_same_month_format(self):
        self.assertEqual(
            format_tsr_service_date_range(self.coverage_rows()),
            'JULY 13-14, 2026',
        )

    def test_date_range_repair_removes_old_coverage_page(self):
        legacy = repair_tsr_multiday_historical_coverage_pdf(
            self.make_original_vector_pdf(page_count=2),
            self.coverage_rows(),
        )
        result = repair_tsr_multiday_service_date_range_pdf(
            legacy['pdf_bytes'],
            self.coverage_rows(),
            serviced_by='Engineer One',
        )
        repaired = fitz.open(stream=result['pdf_bytes'], filetype='pdf')
        all_text = '\n'.join(page.get_text() for page in repaired)
        self.assertEqual(len(repaired), 2)
        self.assertNotIn('SCHEDULE COVERAGE', all_text)
        self.assertIn('JULY 13-14, 2026', repaired[0].get_text())
        self.assertIn('OTHER ASSIGNED ENGINEER(S): ENGINEER TWO', repaired[0].get_text().upper())
        self.assertIn('ORIGINAL PAGE 2', repaired[1].get_text())
        repaired.close()

    def test_date_range_repair_is_idempotent(self):
        first = repair_tsr_multiday_service_date_range_pdf(
            self.make_original_vector_pdf(page_count=1),
            self.coverage_rows(),
            serviced_by='Engineer One',
        )
        second = repair_tsr_multiday_service_date_range_pdf(
            first['pdf_bytes'],
            self.coverage_rows(),
            serviced_by='Engineer One',
        )
        self.assertTrue(second['already_repaired'])
        self.assertEqual(second['pdf_bytes'], first['pdf_bytes'])

    def test_date_range_repair_removes_coverage_from_first_page(self):
        result = repair_tsr_multiday_service_date_range_pdf(
            self.make_legacy_team_pdf(marker=''),
            self.coverage_rows(),
            serviced_by='Engineer One',
        )
        repaired = fitz.open(stream=result['pdf_bytes'], filetype='pdf')
        text = repaired[0].get_text().upper()
        self.assertTrue(result['body_coverage_removed'])
        self.assertNotIn('SCHEDULE COVERAGE', text)
        self.assertIn('JULY 13-14, 2026', text)
        self.assertIn('OTHER ASSIGNED ENGINEER(S): ENGINEER TWO', text)
        repaired.close()

    def test_old_single_day_pdf_without_coverage_gets_team_footer(self):
        result = stamp_tsr_single_day_team_footer(
            self.make_original_vector_pdf(page_count=1),
            ['Engineer One', 'Engineer Two'],
            serviced_by='Engineer One',
        )
        repaired = fitz.open(stream=result['pdf_bytes'], filetype='pdf')
        text = repaired[0].get_text().upper()
        self.assertIn('OTHER ASSIGNED ENGINEER(S): ENGINEER TWO', text)
        self.assertNotIn('SCHEDULE COVERAGE', text)
        repaired.close()

    def test_future_save_guard_uses_compact_date_range(self):
        guarded = ensure_authoritative_tsr_coverage_pdf(
            self.make_original_vector_pdf(page_count=1),
            self.coverage_rows(),
            serviced_by='Engineer One',
        )
        self.assertTrue(guarded['changed'])
        repaired = fitz.open(stream=guarded['pdf_bytes'], filetype='pdf')
        self.assertEqual(len(repaired), 1)
        text = repaired[0].get_text().upper()
        self.assertNotIn('SCHEDULE COVERAGE', text)
        self.assertIn('JULY 13-14, 2026', text)
        self.assertIn('OTHER ASSIGNED ENGINEER(S): ENGINEER TWO', text)
        repaired.close()


if __name__ == '__main__':
    unittest.main()
