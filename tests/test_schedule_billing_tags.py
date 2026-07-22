import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ScheduleBillingTagSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.timeline_source = (ROOT / 'templates' / 'timeline.html').read_text(encoding='utf-8')
        cls.tsr_source = (ROOT / 'templates' / 'offline_tsr.html').read_text(encoding='utf-8')

    def test_po_subtypes_are_optional_and_mutually_exclusive(self):
        self.assertIn('id="site-visit-po-subtype-container"', self.timeline_source)
        self.assertIn('name="f-po-subtype" id="f-flag-sc"', self.timeline_source)
        self.assertIn('name="f-po-subtype" id="f-flag-sv"', self.timeline_source)
        self.assertIn('syncSiteVisitPOSubtypeControls()', self.timeline_source)
        self.assertIn("['f-flag-sc', 'f-flag-sv']", self.timeline_source)

    def test_schedule_tokens_persist_and_render_as_badges(self):
        for marker in (
            "token: '[Warranty]'",
            "token: '[FOC]'",
            "token: '[With P.O.]'",
            "token: '[SC]'",
            "token: '[SV]'",
            'renderSiteVisitFlagBadges(s.task)',
        ):
            self.assertIn(marker, self.timeline_source)

    def test_frontend_and_backend_reject_invalid_combinations(self):
        self.assertIn('validateSiteVisitBillingTags()', self.timeline_source)
        self.assertIn('Select either SC or SV, not both.', self.timeline_source)
        self.assertIn('validate_shift_billing_tags(shift_title)', self.app_source)
        self.assertEqual(self.app_source.count('validate_shift_billing_tags(shift_title)'), 2)
        self.assertIn('SC or SV can only be selected together with With P.O.', self.app_source)

    def test_create_tsr_hides_billing_tokens_from_service_text(self):
        self.assertIn('function stripScheduleBillingTags(value)', self.tsr_source)
        self.assertIn('Warranty|FOC|With\\s*P\\.?O\\.?|SC|SV', self.tsr_source)
        self.assertIn('stripScheduleBillingTags(schedule.task)', self.tsr_source)
        self.assertIn('const task = stripScheduleBillingTags(', self.tsr_source)


if __name__ == '__main__':
    unittest.main()
