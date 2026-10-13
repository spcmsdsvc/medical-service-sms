import pathlib
import unittest

from tests.sw_cache_version import assert_cache_version_at_least


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
        assert_cache_version_at_least(self, 241, APP_SOURCE)
        self.assertIn('"2026-10-05-travel-request-page"', (ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))



class TravelRequestBatch1SourceTests(unittest.TestCase):
    page = PAGE

    def test_link_buttons_keep_readable_colours(self):
        # Batch 4: the hero anchor rule left with the hero; the secondary anchor uses the theme text colour.
        self.assertNotIn('.travel-hero-actions a.travel-btn', self.page)
        self.assertIn('.travel-page a.travel-btn.travel-btn-secondary { color: var(--app-text); }', self.page)

    def test_warning_tone_uses_accent_button(self):
        self.assertNotIn('travel-btn-warning', self.page)
        self.assertIn("(options.tone === 'danger' ? 'travel-btn-danger' : 'travel-btn-primary')", self.page)

    def test_unsaved_changes_guard(self):
        for name in ('function isTravelFormDirty', 'async function confirmDiscardTravelChanges',
                     'async function startNewTravelRequest', 'async function openTravelRequest'):
            with self.subTest(name=name):
                self.assertIn(name, self.page)
        self.assertIn("window.addEventListener('beforeunload'", self.page)
        self.assertIn('onclick="startNewTravelRequest()"', self.page)
        self.assertIn('onclick="openTravelRequest(${id})"', self.page)
        self.assertIn('await openTravelRequest(Number(requestId))', block(self.page, 'async function openTravelNotification', '\n}\n'))
        self.assertIn('travelSavedSnapshot = travelFormSnapshot();', block(self.page, 'function applyTravelRequestRecord', '\n}\n'))

    def test_upload_checks_type_before_uploading(self):
        upload = block(self.page, 'async function uploadTravelRequestAttachments', '\n}\n')
        self.assertIn('/\.(pdf|jpe?g|png)$/i', upload)
        self.assertLess(upload.index('badType'), upload.index('travelFetch'))

    def test_status_groups_drive_filter_and_chip(self):
        group = block(self.page, 'function travelStatusGroup', '\n}\n')
        for value in ('rejected', 'liquidation', 'accounting', 'completed', 'draft', 'submitted', 'approved'):
            with self.subTest(value=value):
                self.assertIn(f"'{value}'", group)
                self.assertIn(f'<option value="{value}">', self.page)
        self.assertLess(group.index("'rejected'"), group.index("'accounting'"))
        self.assertIn('travelStatusGroup(item.status) === filter', self.page)
        self.assertIn('.travel-status-chip.rejected { background: #fde8ea; color: #a1121f; }', self.page)

    def test_every_static_label_is_linked(self):
        import re
        labels = re.findall(r'<label class="travel-label"[^>]*>', self.page)
        self.assertTrue(labels)
        for label in labels:
            with self.subTest(label=label):
                self.assertIn(' for="', label)

    def test_small_buttons_reach_44px_on_phones(self):
        self.assertIn('.travel-btn-sm { min-height: 44px; }', self.page)
        self.assertIn('.travel-notification-close { width: 44px; height: 44px; }', self.page)

    def test_existing_functions_kept(self):
        for name in ('saveTravelRequestDraft', 'submitTravelRequest', 'deleteTravelRequestDraft',
                     'uploadTravelRequestAttachments', 'deleteTravelRequestAttachment',
                     'deleteAllTravelRequestAttachments', 'restoreTravelBlocksForRequest',
                     'loadTravelRequestDetail', 'resetTravelForm', 'toggleTravelReadiness',
                     'checkTravelRequestConflicts', 'openRequestRecall'):
            with self.subTest(name=name):
                self.assertRegex(self.page, rf'function {name}\(|{name}\s*[=(]')


class TravelRequestBatch2SourceTests(unittest.TestCase):
    page = PAGE

    def test_limits_reach_page_and_readiness(self):
        self.assertIn('const TRAVEL_MAX_DAYS = {{ travel_max_days }};', self.page)
        self.assertIn('const TRAVEL_MAX_AMOUNT = {{ travel_max_amount }};', self.page)
        readiness = block(self.page, 'function travelReadinessItems', '\n}\n')
        self.assertIn('travelTripTooLong(departure, returnDate)', readiness)
        self.assertIn('calculateTravelTotal() > TRAVEL_MAX_AMOUNT', readiness)
        save = block(self.page, 'async function saveTravelRequestDraft', '\n}\n')
        self.assertLess(save.index('travelTripTooLong('), save.index('travelFetch'))
        self.assertLess(save.index('TRAVEL_MAX_AMOUNT'), save.index('travelFetch'))
        self.assertIn('travel_max_days=TRAVEL_REQUEST_MAX_DAYS', APP_SOURCE)

    def test_history_show_more(self):
        self.assertIn('id="travel-history-more"', self.page)
        self.assertIn('onclick="loadMyTravelRequests(true)"', self.page)
        load = block(self.page, 'async function loadMyTravelRequests', '\n}\n')
        self.assertIn('offset=${offset}', load)
        self.assertIn("$t('travel-history-more').hidden = !data.has_more;", load)

    def test_payload_drops_ignored_keys(self):
        payload = block(self.page, 'function collectTravelPayload', '\n}\n')
        for key in ('travel_type', 'arrival_date', 'participant_names', 'client_id', 'product_id', 'equipment'):
            with self.subTest(key=key):
                self.assertNotRegex(payload, rf'\n        {key}:')
        for key in ('client_name', 'destination', 'request_type', 'routes'):
            with self.subTest(key=key):
                self.assertRegex(payload, rf'\n        {key}[:,\n]')


class TravelRequestBatch3SourceTests(unittest.TestCase):
    page = PAGE
    dark_css = (ROOT / 'static' / 'css' / 'app-dark-pages.css').read_text(encoding='utf-8')

    def test_dark_red_outline_readable(self):
        self.assertIn(':root[data-app-theme="dark"] .travel-btn-danger-outline { background: transparent !important; '
                      'color: #fca5a5 !important;', self.dark_css)
        self.assertIn(':root[data-app-theme="dark"] .travel-btn-danger-outline:is(:hover, :focus-visible)', self.dark_css)

    def test_hero_pill_replaced_by_status_chip(self):
        # Batch 4: the white hero pill became a status chip in the Page Header.
        self.assertNotIn('.travel-hero-pill', self.page)
        self.assertIn("pill.className = ('travel-status-chip ' + travelStatusChipClass(status)).trim();", self.page)

    def test_disabled_equipment_toggle_text(self):
        self.assertIn('.travel-equipment-toggle:disabled { background: var(--app-surface-raised); color: #475569;', self.page)

    def test_kept_hooks(self):
        for hook in ('id="travel-delete-all-attachments-btn"', 'id="travel-delete-draft-btn"',
                     'onclick="removeTravelVisit(this)"', 'onclick="deleteTravelRequestAttachment(',
                     "openRequestRecall('travel_request'"):
            with self.subTest(hook=hook):
                self.assertIn(hook, self.page)


class TravelRequestBatch4SourceTests(unittest.TestCase):
    page = PAGE

    def style(self):
        return block(self.page, '<style>', '</style>')

    def test_page_header_reused(self):
        self.assertIn("filename='css/app-dashboard.css') }}?v=17", self.page)
        for cls in ('dash-page-header', 'dash-page-h1', 'dash-page-sub', 'dash-page-actions'):
            with self.subTest(cls=cls):
                self.assertIn(f'class="{cls}"', self.page)
        self.assertNotIn('travel-hero"', self.page)
        self.assertNotIn('.travel-hero', self.page)
        self.assertEqual(self.page.count('class="btn btn-outline-primary"'), 4)

    def test_header_status_uses_chip_classes(self):
        locked = block(self.page, 'function setTravelRequestLockedState', '\n}\n')
        self.assertIn("pill.className = ('travel-status-chip ' + travelStatusChipClass(status)).trim();", locked)
        self.assertIn('id="travel-hero-status" class="travel-status-chip"', self.page)

    def test_button_roles(self):
        self.assertIn('class="travel-btn travel-btn-primary" id="travel-submit-btn"', self.page)
        self.assertIn('class="travel-btn travel-btn-outline" id="travel-save-btn"', self.page)
        self.assertNotIn('travel-btn-success', self.page)

    def test_weights_and_radii_follow_design(self):
        import re
        weights = {int(w) for w in re.findall(r'font-weight:\s*(\d+)', self.style())}
        self.assertTrue(weights)
        self.assertLessEqual(max(weights), 600)
        radii = set(re.findall(r'border-radius:\s*([^;]+);', self.style()))
        self.assertLessEqual(radii, {'6px', '10px', '12px', '16px', '999px'})

    def test_neutral_hex_moved_to_theme_variables(self):
        style = self.style().lower()
        for value in ('#0f172a', '#334155', '#64748b', '#e2e8f0', '#cbd5e1', '#dbe4ee', '#f8fafc', '#f1f5f9'):
            with self.subTest(value=value):
                self.assertNotIn(value, style.replace('var(--app-border, #e2e8f0)', ''))

    def test_phone_first_screen_and_dock(self):
        for field in ('travel-date', 'travel-department', 'travel-current-status', 'travel-request-no'):
            with self.subTest(field=field):
                self.assertIn(f'<div class="col-6 col-md-3"><label class="travel-label" for="{field}">', self.page)
        self.assertIn('.travel-dock-inner { display: grid; grid-template-columns: 1fr 1fr 44px 44px; gap: 8px; }', self.page)
        self.assertIn('.travel-dock-actions { display: contents; }', self.page)
        self.assertIn('.travel-dock-label { position: absolute;', self.page)
        self.assertIn('onclick="toggleTravelReadiness()" aria-label="Readiness"', self.page)
        self.assertIn('onclick="deleteTravelRequestDraft()" aria-label="Delete Draft"', self.page)

    def test_kept_hooks(self):
        for hook in ('id="travel-hero-title"', 'id="travel-hero-status"', 'id="travel-preview-btn"',
                     'id="travel-open-timeline-btn"', 'id="travel-restore-blocks-btn"', 'onclick="startNewTravelRequest()"',
                     'onclick="openTimelineForTravelRequest(currentTravelRequest)"',
                     'onclick="restoreTravelBlocksForRequest(currentTravelRequest?.id)"',
                     'id="travel-dock"', 'id="travel-dock-total"', 'id="travel-save-btn"', 'id="travel-submit-btn"',
                     'id="travel-delete-draft-btn"', 'onclick="saveTravelRequestDraft()"', 'onclick="submitTravelRequest()"',
                     'onclick="deleteTravelRequestDraft()"', 'onclick="toggleTravelReadiness()"',
                     'id="travel-date"', 'id="travel-department"', 'id="travel-current-status"', 'id="travel-request-no"'):
            with self.subTest(hook=hook):
                self.assertIn(hook, self.page)
        for name in ('travelConfirmDialog', 'applyTravelRequestRecord', 'toggleTravelReadiness', 'saveTravelRequestDraft',
                     'submitTravelRequest', 'deleteTravelRequestDraft', 'startNewTravelRequest',
                     'openTimelineForTravelRequest', 'restoreTravelBlocksForRequest', 'travelStatusChipClass'):
            with self.subTest(name=name):
                self.assertRegex(self.page, rf'function {name}\(|{name}\s*=')


if __name__ == '__main__':
    unittest.main()
