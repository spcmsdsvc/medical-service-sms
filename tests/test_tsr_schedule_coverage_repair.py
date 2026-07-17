import unittest

import fitz

from app import (
    TSR_SCHEDULE_COVERAGE_REPAIR_MARKER,
    TSR_SCHEDULE_COVERAGE_REPAIR_MARKER_V1,
    repair_tsr_single_day_multi_engineer_coverage_pdf,
)


class TsrScheduleCoverageRepairTests(unittest.TestCase):
    @staticmethod
    def make_v1_repaired_pdf():
        document = fitz.open()
        page = document.new_page(width=595.28, height=841.89)

        page.draw_rect(fitz.Rect(24, 239, 571, 252), color=(0, 0, 0), width=0.8)
        page.insert_text((31, 249), 'SCHEDULE COVERAGE', fontsize=7.5)
        columns = [(24, 172), (172, 298), (298, 571)]
        for left, right in columns:
            page.draw_rect(fitz.Rect(left, 252, right, 264), color=(0, 0, 0), width=0.8)
            page.draw_rect(fitz.Rect(left, 264, right, 278), color=(0, 0, 0), width=0.8)
        page.insert_text((31, 261), 'SCHEDULED DATE', fontsize=6.5)
        page.insert_text((179, 261), 'SCHEDULED TIME', fontsize=6.5)
        page.insert_text((305, 261), 'ASSIGNED ENGINEER(S)', fontsize=6.5)
        page.insert_text((31, 274), 'Jul 16, 2026', fontsize=6.5)
        page.insert_text((179, 274), '17:00 - 19:00', fontsize=6.5)
        page.insert_text((305, 274), 'Engineer One, Engineer Two', fontsize=6.5)

        # Simulate the first repair's extra compact rectangle while retaining
        # the old table graphics underneath it.
        page.draw_rect(fitz.Rect(27, 240, 568, 283), color=(0, 0, 0), fill=(1, 1, 1), width=0.8)
        page.draw_line(fitz.Point(27, 252), fitz.Point(568, 252), color=(0, 0, 0), width=0.6)
        page.insert_text((34, 250), 'SCHEDULE COVERAGE', fontsize=7.5)
        page.insert_text((34, 264), 'ASSIGNED ENGINEER(S): Engineer One, Engineer Two', fontsize=7.2)

        page.draw_rect(fitz.Rect(24, 282, 571, 293), color=(0, 0, 0), width=0.8)
        page.insert_text((28, 291), 'COMPLAINT', fontsize=7.5)
        page.draw_rect(fitz.Rect(24, 294, 571, 319), color=(0, 0, 0), width=0.8)
        page.insert_text((28, 307), 'Preventive Maintenance', fontsize=7.5)

        document.set_metadata({'keywords': TSR_SCHEDULE_COVERAGE_REPAIR_MARKER_V1})
        raw = document.tobytes()
        document.close()
        return raw

    def test_v1_overlap_is_upgraded_to_clean_v2_block(self):
        result = repair_tsr_single_day_multi_engineer_coverage_pdf(
            self.make_v1_repaired_pdf(),
            ['Engineer One', 'Engineer Two'],
        )

        self.assertFalse(result['already_repaired'])
        repaired = fitz.open(stream=result['pdf_bytes'], filetype='pdf')
        page = repaired[0]
        self.assertIn(TSR_SCHEDULE_COVERAGE_REPAIR_MARKER, repaired.metadata.get('keywords', ''))
        self.assertEqual(len(page.search_for('SCHEDULE COVERAGE')), 1)
        self.assertEqual(len(page.search_for('ASSIGNED ENGINEER(S)')), 1)
        self.assertEqual(len(page.search_for('COMPLAINT')), 1)

        # Old table dividers at x=172 and x=298 must be removed from the
        # coverage band; only the compact outer border and title divider remain.
        old_dividers = []
        for drawing in page.get_drawings():
            rect = drawing.get('rect')
            if not rect or rect.y1 < 239 or rect.y0 > 282:
                continue
            if abs(rect.x0 - 172) < 1 or abs(rect.x0 - 298) < 1:
                old_dividers.append(rect)
        self.assertEqual(old_dividers, [])
        repaired.close()

    def test_v2_repair_is_idempotent(self):
        first = repair_tsr_single_day_multi_engineer_coverage_pdf(
            self.make_v1_repaired_pdf(),
            ['Engineer One', 'Engineer Two'],
        )
        second = repair_tsr_single_day_multi_engineer_coverage_pdf(
            first['pdf_bytes'],
            ['Engineer One', 'Engineer Two'],
        )

        self.assertTrue(second['already_repaired'])
        self.assertEqual(second['pdf_bytes'], first['pdf_bytes'])


if __name__ == '__main__':
    unittest.main()
