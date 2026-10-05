import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / 'app.py').read_text(encoding='utf-8')
PAGE = (ROOT / 'templates' / 'travel_request.html').read_text(encoding='utf-8')
APPROVALS = (ROOT / 'templates' / 'approvals.html').read_text(encoding='utf-8')
DETAIL_FIELDS = (
    'training_title', 'training_provider', 'training_venue', 'training_objective',
    'meeting_subject', 'meeting_with', 'meeting_objective',
)


def block(source, start, end):
    begin = source.index(start)
    return source[begin:source.index(end, begin + len(start))]


class TravelRequestServerTests(unittest.TestCase):
    def test_detail_columns_are_migrated_saved_and_returned(self):
        save = block(APP_SOURCE, 'def save_travel_request_draft', '@app.route')
        for field in DETAIL_FIELDS:
            with self.subTest(field=field):
                self.assertIn(f"ALTER TABLE travel_request ADD COLUMN {field}", APP_SOURCE)
                self.assertIn(f"{field} = db.Column(", APP_SOURCE)
                self.assertIn(f"'{field}'", save)
                self.assertIn(f"'{field}': clean_str(getattr(request_rec, '{field}', None))", APP_SOURCE)

    def test_travel_migration_runs_at_railway_startup(self):
        startup = block(APP_SOURCE, 'def prepare_deferred_workflow_schemas', 'EMBEDDED_LPR_PARENT_MODULES')
        self.assertIn('ensure_travel_request_tables()', startup)

    def test_save_rejects_negative_amounts_and_reversed_dates(self):
        save = block(APP_SOURCE, 'def save_travel_request_draft', '@app.route')
        self.assertIn('Amounts cannot be negative.', save)
        self.assertIn('Return date cannot be before the departure date.', save)

    def test_submit_validates_dates_and_routes_before_conflicts(self):
        submit = block(APP_SOURCE, 'def submit_travel_request', '@app.route')
        dates = submit.index('Please set the departure and return dates before submitting.')
        self.assertLess(dates, submit.index('find_travel_request_conflicts_for_user'))
        self.assertIn('Please add at least one route plan before submitting.', submit)

    def test_route_without_travel_type_does_not_crash(self):
        helper = block(APP_SOURCE, 'def travel_request_travel_type_allows_airfare_c_o', 'def travel_request_routes_allow_airfare_c_o')
        self.assertIn("(clean_str(value) or '').lower()", helper)

    def test_dict_looks_up_approvers_and_participants_once(self):
        to_dict = block(APP_SOURCE, 'def travel_request_to_dict', 'def can_user_access_travel_request')
        self.assertEqual(to_dict.count('get_assigned_approvers_for_requester('), 1)
        self.assertEqual(to_dict.count('get_travel_request_participants('), 1)
        self.assertIn("'request_date'", to_dict)

    def test_approvals_prefers_stored_fields(self):
        self.assertIn("data.training_title || extractTravelApprovalField(data, 'Training Title')", APPROVALS)
        self.assertIn("data.meeting_subject || extractTravelApprovalField(data, 'Meeting Subject')", APPROVALS)


class TravelRequestPageTests(unittest.TestCase):
    def test_new_functions_present(self):
        self.assertIn('/preview_approved_travel_request_form/', PAGE)
        self.assertIn('item.approval_remarks', PAGE)
        self.assertIn("entry.action !== 'draft_saved'", PAGE)
        self.assertIn('id="travel-dock"', PAGE)
        self.assertIn('function travelReadinessItems()', PAGE)
        self.assertIn('id="travel-history-filter"', PAGE)

    def test_owner_only_controls_and_server_editable_statuses(self):
        self.assertIn('isTravelOwner(item)', PAGE)
        editable = block(PAGE, 'function isTravelEditableStatus', '}')
        self.assertNotIn('returned', editable)

    def test_removed_code_stays_removed(self):
        for marker in ('travel-delete-draft-panel', 'visit-product-select', 'lead_requester_name',
                       'travel-attachment-selection', 'SPCAcctgtravelrequest 002-2016</p>', 'Sign-off Placeholders'):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, PAGE)

    def test_release_records(self):
        self.assertIn("const CACHE_VERSION = 'medical-service-pwa-offline-navigation-v241-travel-request-page'", APP_SOURCE)
        self.assertIn('"2026-10-05-travel-request-page"', (ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
