"""Activity Log details panel: record references and the related-entries route."""

import json
import os
import pathlib
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_activity_details_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB_PATH))
os.environ.setdefault("SECRET_KEY", "activity-details-tests")

import app as app_module  # noqa: E402

ACTIVITY_TEMPLATE = (ROOT / 'templates' / 'activity.html').read_text(encoding='utf-8')
APP_SOURCE = (ROOT / 'app.py').read_text(encoding='utf-8')
RELEASES = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))


class ActivityReferenceTests(unittest.TestCase):
    def test_codes_and_numbered_records_are_found_in_order(self):
        extract = app_module.extract_activity_references
        self.assertEqual(extract('Marked Travel Request ready for liquidation: TR-20260609-11'), ['TR-20260609-11'])
        self.assertEqual(
            extract('Created Cash Advance Liquidation draft: CAL-20261004-3 for CA-20260616-1'),
            ['CAL-20261004-3', 'CA-20260616-1'],
        )
        self.assertEqual(extract('Deleted all 2 Reimbursement receipt(s): Reimbursement #45'), ['reimbursement #45'])
        self.assertEqual(extract('Saved TSR for schedule #876 and schedule #876'), ['schedule #876'])

    def test_equipment_serials_are_not_references(self):
        self.assertEqual(app_module.extract_activity_references('Added equipment: ZEN-119003-10824'), [])

    def test_reference_match_respects_number_boundaries(self):
        self.assertTrue(app_module.activity_mentions_reference('done for schedule #87.', 'schedule #87'))
        self.assertFalse(app_module.activity_mentions_reference('done for schedule #876', 'schedule #87'))
        self.assertFalse(app_module.activity_mentions_reference('TR-20260609-110 sent', 'TR-20260609-11'))


class ActivityRelatedRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=True)
        cls.suffix = uuid.uuid4().hex[:6].upper()
        base = datetime(2026, 10, 1, 9, 0)
        cls.tr = 'TR-20261001-' + str(int(uuid.uuid4().int % 90000) + 10000)
        cls.other_tr = cls.tr + '0'
        cls.lr = 'LR-20261001-' + str(int(uuid.uuid4().int % 90000) + 10000)
        cls.reject_at = base + timedelta(days=3)
        user = f'Tester{cls.suffix}'
        entries = {
            'tr_open': (user, f'Submitted Travel Request: {cls.tr}', base),
            'tr_close': ('Approver', f'Approved Travel Request: {cls.tr}', base + timedelta(days=2)),
            'tr_other': (user, f'Submitted Travel Request: {cls.other_tr}', base + timedelta(days=1)),
            'plain': (user, f'Added client: Center {cls.suffix} Manila', base + timedelta(days=5)),
            'near': (user, f'Modified details for client: Center {cls.suffix}', base + timedelta(days=5, minutes=20)),
            'far': (user, f'Modified details for client: Far {cls.suffix}', base + timedelta(days=5, minutes=45)),
            'routine': (user, 'Updated appearance preference: graphite / teal', base + timedelta(days=5, minutes=5)),
            'someone_else': ('Someone', f'Added client: Other {cls.suffix}', base + timedelta(days=5, minutes=2)),
            'lr_reject': ('Approver', f'Leave Request Rejected: {cls.lr}', cls.reject_at),
            'lr_submit': (user, f'Leave Request Submitted: {cls.lr}', cls.reject_at - timedelta(hours=2)),
        }
        with cls.app.app_context():
            app_module.db.create_all()
            viewer = app_module.User(username=f'activity-viewer-{cls.suffix}', password='test', role='admin', is_active=True)
            rows = {key: app_module.ActivityLog(user=u, action=a, timestamp=t) for key, (u, a, t) in entries.items()}
            app_module.db.session.add_all([viewer, *rows.values()])
            app_module.db.session.flush()
            travel = app_module.TravelRequest(
                request_no=cls.tr, user_id=viewer.id, request_type='Client Visit / Service',
                purpose='Route 1: Manila → Cebu\nNotes:\nBPI Account Number: 123', status='Approved',
                departure_date=datetime(2026, 11, 2).date(), return_date=datetime(2026, 11, 4).date(),
                requested_amount=9000, approved_amount=8000, account_number='SECRET-ACCT-123',
            )
            app_module.db.session.add(travel)
            app_module.db.session.flush()
            for sequence, (origin, destination) in enumerate((('Manila', 'Cebu'), ('Cebu', 'Davao')), start=1):
                route = app_module.TravelRequestRoute(
                    travel_request_id=travel.id, sequence_no=sequence, from_location=origin, to_location=destination
                )
                app_module.db.session.add(route)
                app_module.db.session.flush()
                app_module.db.session.add(app_module.TravelRequestRouteVisit(
                    route_id=route.id, travel_request_id=travel.id, sequence_no=1,
                    client_name=f'Hospital {destination}', product_name='MobileDaRt', purpose_tags='PM',
                ))
            engineer = app_module.Engineer(employee_id=f'LRT-{cls.suffix}', name=f'Leave Tester {cls.suffix}', initials='LT')
            app_module.db.session.add(engineer)
            app_module.db.session.flush()
            leave = app_module.LeaveRequest(
                request_no=cls.lr, user_id=viewer.id, engineer_id=engineer.id,
                application_date=base.date(), leave_type='Vacation Leave',
                start_date=datetime(2026, 10, 12).date(), end_date=datetime(2026, 10, 14).date(),
                weekday_count=3, reason='private medical detail', status='Rejected',
                approval_remarks='overwritten later',
            )
            app_module.db.session.add(leave)
            app_module.db.session.flush()
            audit_rows = [
                # An older rejection of the same request, outside the 5-minute window.
                app_module.UniversalApprovalAuditTrail(
                    module='leave_request', record_id=leave.id, action='rejected', actor_display_name='Old Approver',
                    remarks='older reason', created_at=cls.reject_at - timedelta(hours=1),
                ),
                app_module.UniversalApprovalAuditTrail(
                    module='leave_request', record_id=leave.id, action='rejected', actor_display_name='Manager One',
                    remarks='Overlaps the PM visit', created_at=cls.reject_at + timedelta(seconds=2),
                ),
            ]
            app_module.db.session.add_all(audit_rows)
            app_module.db.session.commit()
            cls.engineer_id = engineer.id
            cls.leave_id = leave.id
            cls.audit_ids = [row.id for row in audit_rows]
            cls.travel_id = travel.id
            cls.viewer_id = viewer.id
            cls.ids = {key: row.id for key, row in rows.items()}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            app_module.ActivityLog.query.filter(app_module.ActivityLog.id.in_(cls.ids.values())).delete(
                synchronize_session=False
            )
            for model in (app_module.TravelRequestRouteVisit, app_module.TravelRequestRoute):
                model.query.filter_by(travel_request_id=cls.travel_id).delete(synchronize_session=False)
            app_module.TravelRequest.query.filter_by(id=cls.travel_id).delete(synchronize_session=False)
            app_module.UniversalApprovalAuditTrail.query.filter(
                app_module.UniversalApprovalAuditTrail.id.in_(cls.audit_ids)
            ).delete(synchronize_session=False)
            app_module.LeaveRequest.query.filter_by(id=cls.leave_id).delete(synchronize_session=False)
            app_module.Engineer.query.filter_by(id=cls.engineer_id).delete(synchronize_session=False)
            app_module.User.query.filter_by(id=cls.viewer_id).delete(synchronize_session=False)
            app_module.db.session.commit()
            app_module.db.session.remove()

    def get(self, key_or_id, admin=True, regional=False):
        log_id = self.ids.get(key_or_id, key_or_id)
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.viewer_id)
            session['_fresh'] = True
        with patch.object(app_module, 'is_admin_authorized', return_value=admin), \
                patch.object(app_module, 'is_regional_admin_user', return_value=regional), \
                patch.object(app_module, 'is_superadmin_user', return_value=False):
            return client.get(f'/get_activity_log_related/{log_id}')

    def related_ids(self, response):
        return {row['id'] for row in response.get_json()['related']}

    def test_same_record_entries_are_returned_and_other_records_are_not(self):
        response = self.get('tr_open')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['related_by'], 'reference')
        self.assertEqual(data['references'], [self.tr])
        self.assertEqual(self.related_ids(response), {self.ids['tr_close']})
        self.assertIn('timestamp', data['log'])

    def test_travel_request_entry_carries_the_current_record_summary(self):
        records = self.get('tr_open').get_json()['records']
        self.assertEqual(len(records), 1)
        self.assertEqual((records[0]['reference'], records[0]['kind']), (self.tr, 'Travel Request'))
        self.assertEqual(records[0]['label'], f'Travel Request {self.tr}')
        fields = dict(records[0]['fields'])
        self.assertEqual(fields['Route'], 'Manila → Cebu → Davao')
        self.assertEqual(fields['Visits'], 'Hospital Cebu – MobileDaRt – PM; Hospital Davao – MobileDaRt – PM')
        self.assertEqual(fields['Travel dates'], 'Nov 2, 2026 – Nov 4, 2026')
        self.assertEqual(fields['Amount'], 'PHP 9,000.00 requested / PHP 8,000.00 approved')
        self.assertEqual(fields['Status'], 'Approved')
        self.assertNotIn('SECRET-ACCT-123', json.dumps(records))
        self.assertNotIn('123', fields.get('Purpose', ''))

    def test_open_link_only_for_the_assigned_approver(self):
        with patch.object(app_module, 'is_approval_center_user', return_value=True), \
                patch.object(app_module, 'can_user_review_travel_request', return_value=True):
            record = self.get('tr_open').get_json()['records'][0]
        self.assertEqual(record['open_url'], f'/approvals?module=travel_request&id={self.travel_id}')
        self.assertEqual(record['open_label'], 'Open in Approvals')
        with patch.object(app_module, 'is_approval_center_user', return_value=True), \
                patch.object(app_module, 'can_user_review_travel_request', return_value=False):
            self.assertIsNone(self.get('tr_open').get_json()['records'][0]['open_url'])
        with patch.object(app_module, 'is_approval_center_user', return_value=False), \
                patch.object(app_module, 'can_user_review_travel_request', return_value=True):
            self.assertIsNone(self.get('tr_open').get_json()['records'][0]['open_url'])

    def test_schedule_links_to_its_day_in_timeline(self):
        shift = SimpleNamespace(id=5, start_time=datetime(2026, 6, 4, 8, 0))
        with self.app.test_request_context():
            with patch.object(app_module, 'can_access_timeline_page', return_value=True):
                self.assertEqual(
                    app_module._activity_record_open_link('Schedule', shift),
                    {'open_url': '/timeline?date=2026-06-04', 'open_label': 'Show in Timeline'},
                )
            with patch.object(app_module, 'can_access_timeline_page', return_value=False):
                self.assertIsNone(app_module._activity_record_open_link('Schedule', shift)['open_url'])

    def test_rejected_leave_request_shows_reason_and_who_rejected(self):
        with patch.object(app_module, 'is_approval_center_user', return_value=True), \
                patch.object(app_module, 'can_approve_leave_request', return_value=True):
            data = self.get('lr_reject').get_json()
        self.assertEqual(data['decision'], {'decision': 'Rejected', 'reason': 'Overlaps the PM visit', 'by': 'Manager One'})
        record = data['records'][0]
        self.assertEqual(record['label'], f'Leave Request {self.lr}')
        fields = dict(record['fields'])
        self.assertEqual(fields['Leave type'], 'Vacation Leave')
        self.assertEqual(fields['Dates'], 'Oct 12, 2026 – Oct 14, 2026 (3 weekdays)')
        self.assertEqual(fields['Status'], 'Rejected')
        self.assertNotIn('private medical detail', json.dumps(data))
        self.assertEqual(record['open_url'], f'/approvals?module=leave_request&id={self.leave_id}')

    def test_reason_only_on_rejection_entries(self):
        self.assertIsNone(self.get('lr_submit').get_json()['decision'])
        self.assertIsNone(self.get('tr_open').get_json()['decision'])

    def test_code_without_a_record_has_no_summary(self):
        self.assertEqual(self.get('tr_other').get_json()['records'], [])
        self.assertIsNone(app_module.activity_record_summary('route #5'))

    def test_entry_without_code_shows_same_person_within_thirty_minutes(self):
        response = self.get('plain')
        data = response.get_json()
        self.assertEqual(data['records'], [])
        self.assertEqual(data['related_by'], 'nearby')
        self.assertEqual(self.related_ids(response), {self.ids['near']})

    def list_links(self, query, approver):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.viewer_id)
            session['_fresh'] = True
        with patch.object(app_module, 'is_admin_authorized', return_value=True), \
                patch.object(app_module, 'is_regional_admin_user', return_value=False), \
                patch.object(app_module, 'is_superadmin_user', return_value=False), \
                patch.object(app_module, 'is_approval_center_user', return_value=True), \
                patch.object(app_module, 'can_user_review_travel_request', return_value=approver):
            rows = client.get(f'/get_activity_logs?q={query}&per_page=100').get_json()['logs']
        return {row['id']: row['record_link'] for row in rows}

    def test_list_rows_carry_where_the_category_chip_leads(self):
        links = self.list_links(self.tr, approver=True)
        self.assertEqual(links[self.ids['tr_open']], {
            'open_state': 'open', 'record_label': f'Travel Request {self.tr}',
            'open_url': f'/approvals?module=travel_request&id={self.travel_id}', 'open_label': 'Open in Approvals',
        })
        denied = self.list_links(self.tr, approver=False)[self.ids['tr_open']]
        self.assertEqual((denied['open_state'], denied['open_url']), ('denied', None))
        # TR-...0 is a code with no record behind it.
        self.assertEqual(self.list_links(self.other_tr, approver=True)[self.ids['tr_other']]['open_state'], 'missing')
        self.assertIsNone(self.list_links(f'Center {self.suffix}', approver=True)[self.ids['plain']])

    def test_non_admin_is_denied(self):
        self.assertEqual(self.get('tr_open', admin=False).status_code, 403)

    def test_regional_admin_cannot_open_out_of_scope_entry(self):
        self.assertEqual(self.get('tr_close', regional=True).status_code, 404)

    def test_missing_entry_is_404(self):
        self.assertEqual(self.get(999999999).status_code, 404)


class ActivityDetailsPageTests(unittest.TestCase):
    def test_panel_and_script_are_wired_and_existing_functions_remain(self):
        for token in (
            'id="activity-detail"',
            'offcanvas-end activity-detail-panel',
            'data-bs-backdrop="false"',
            'function openActivityDetail(',
            'function parseActivityFields(',
            '/get_activity_log_related/',
            'data-log-id="${log.id}"',
            'class="activity-detail-link"',
            'Same person, around this time',
            'id="activity-detail-records"',
            'function renderActivityRecords(',
            'renderActivityRecords(data.records)',
            'Current record · ',
            'function activityRecordOpenLink(',
            'target="_blank" rel="noopener"',
            'Only the assigned approver can open this record.',
            'renderActivityDetail(data.log, data.decision)',
            '${decision.decision} reason',
            'function renderCategoryChip(',
            'function showActivityToast(',
            'id="activity-toast"',
            "denied: 'Only the assigned approver can open this record.'",
            "missing: 'This record no longer exists.'",
            "onclick=\"filterBy('filter-type', this.dataset.value)\"",
            "event.target.closest('button, a')",
        ):
            self.assertIn(token, ACTIVITY_TEMPLATE)
        for name in ('loadLogs', 'filterBy', 'exportLogs', 'resetFilters', 'changePage', 'renderRow', 'loadFilterOptions'):
            self.assertIn(f'function {name}(', ACTIVITY_TEMPLATE)

    def test_release_entry_and_cache_marker(self):
        release = next(r for r in RELEASES['releases'] if r['release_key'] == '2026-10-08-activity-details')
        self.assertTrue(release['is_published'])
        self.assertEqual(release['items'][0]['audiences'], ['admins'])
        self.assertIn('v275-activity-details.', APP_SOURCE)
        follow_up = next(r for r in RELEASES['releases'] if r['release_key'] == '2026-10-08-activity-open-record')
        self.assertEqual(follow_up['items'][0]['audiences'], ['admins'])
        self.assertIn('v276-activity-open-record.', APP_SOURCE)
        chip = next(r for r in RELEASES['releases'] if r['release_key'] == '2026-10-08-activity-chip-open')
        self.assertEqual(chip['items'][0]['audiences'], ['admins'])
        self.assertIn("v277-activity-chip-open';", APP_SOURCE)


if __name__ == '__main__':
    unittest.main()
