import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class TravelRequestDraftInstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.template_source = (ROOT / 'templates' / 'travel_request.html').read_text(encoding='utf-8')

    def test_draft_instruction_fields_are_persisted_and_serialized(self):
        for field in ('special_instruction', 'account_number', 'health_condition', 'special_notes'):
            self.assertIn(f"payload.get('{field}')", self.app_source)
            self.assertIn(f"'{field}': clean_str(getattr(request_rec, '{field}', None))", self.app_source)
            self.assertIn(f"ALTER TABLE travel_request ADD COLUMN {field}", self.app_source)

    def test_frontend_collects_and_restores_deposit_fields(self):
        self.assertIn("special_notes: document.getElementById('travel-special-notes')", self.template_source)
        self.assertIn('function hydrateTravelDepositFieldsFromRequest(item)', self.template_source)
        self.assertIn('hydrateTravelDepositFieldsFromRequest(item);', self.template_source)
        helper_start = self.template_source.index('function hydrateTravelDepositFieldsFromRequest(item)')
        self.assertLess(
            self.template_source.index('updateDepositFieldsState();', helper_start),
            self.template_source.index('accountNumber.value', helper_start),
        )

    def test_generated_form_uses_saved_instruction(self):
        self.assertIn("special_instruction == 'check for encashment'", self.app_source)
        self.assertIn("account_number = safe_text(ctx.get('account_number'))", self.app_source)
        self.assertIn("health_text = safe_text(ctx.get('health_condition')) or 'Fit to travel'", self.app_source)


if __name__ == '__main__':
    unittest.main()
