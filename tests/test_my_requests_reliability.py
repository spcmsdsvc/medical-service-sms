import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MyRequestsReliabilitySourceTests(unittest.TestCase):
    def test_cash_advance_schema_is_prepared_for_wsgi_and_guarded_after_failure(self):
        source = (ROOT / 'app.py').read_text(encoding='utf-8')

        self.assertIn('def prepare_deferred_workflow_schemas():', source)
        self.assertIn('def initialize_wsgi_workflow_schemas():', source)
        self.assertIn("if __name__ != '__main__' and os.environ.get('RAILWAY_ENVIRONMENT'):", source)
        self.assertIn('_cash_advance_schema_startup_attempted', source)
        self.assertIn('Cash Advance records are temporarily unavailable. Please refresh in a moment.', source)
        self.assertIn("'status': 'unavailable'", source)

    def test_accounting_center_has_bounded_module_and_queue_requests(self):
        source = (ROOT / 'templates' / 'accounting_center.html').read_text(encoding='utf-8')

        self.assertIn('const ACCOUNTING_REQUEST_TIMEOUT_MS = 15000;', source)
        self.assertIn('function fetchAccountingWithTimeout', source)
        self.assertGreaterEqual(source.count('fetchAccountingWithTimeout('), 3)
        self.assertIn('My Requests is taking too long to respond.', source)


if __name__ == '__main__':
    unittest.main()
