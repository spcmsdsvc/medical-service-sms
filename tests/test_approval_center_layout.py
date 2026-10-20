"""Approval Center layout contracts (plans.md "Approval Center layout", 2026-10-20)."""

import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
os.environ.setdefault(
    "MEDICAL_SERVICE_TEST_DB",
    str(pathlib.Path(tempfile.gettempdir()) / "medical_service_approval_center_layout_tests.db"),
)

import app as app_module  # noqa: E402
from tests.test_approval_center_pagination import _entry  # noqa: E402

TEMPLATE_PATH = ROOT / "templates" / "approvals.html"


class ApprovalCenterWorkFirstTests(unittest.TestCase):
    """Batch 1: the queue is the first thing on the page."""

    template = None

    @classmethod
    def setUpClass(cls):
        if cls.template is None:
            cls.template = TEMPLATE_PATH.read_text(encoding="utf-8")

    def test_page_header_replaces_banner_and_dashboard_blocks(self):
        page = self.template
        self.assertIn('<header class="dash-page-header">', page)
        self.assertIn('<h1 class="dash-page-h1">Approvals</h1>', page)
        self.assertIn('id="approvalPageSub"', page)
        for removed in ('approval-hero', 'approval-command-center', 'approval-module-mini',
                        'approval-summary-strip', 'id="approvalSummaryTotal"', 'Total Records'):
            self.assertNotIn(removed, page)

    def test_tabs_carry_counts_and_tab_roles(self):
        page = self.template
        for name in ('Pending', 'Approved', 'Rejected'):
            with self.subTest(tab=name):
                self.assertIn(f'role="tab" id="approvalTab{name}"', page)
                self.assertIn(f'aria-controls="approvalPanel{name}"', page)
                self.assertIn(f'id="approvalSummary{name}"', page)
                self.assertIn(f'role="tabpanel" id="approvalPanel{name}"', page)

    def test_tabs_sit_above_filters_and_pagination_below_lists(self):
        page = self.template
        self.assertLess(page.index('class="approval-tabs"'), page.index('id="approvalQueueFilters"'))
        self.assertLess(page.index('id="approvalUnifiedRejectedList"'), page.index('id="approvalQueuePagination"'))

    def test_notifications_hide_when_nothing_is_unread(self):
        page = self.template
        self.assertIn('id="approvalNotificationCard" hidden', page)
        self.assertIn('cardEl.hidden = unread === 0;', page)

    def test_phone_filters_open_from_a_toggle(self):
        page = self.template
        self.assertIn('id="approvalQueueFiltersToggle" aria-expanded="false"', page)
        self.assertIn('.approval-queue-filters:not(.is-open) .approval-queue-filter-more { display: none; }', page)
        self.assertEqual(page.count('approval-queue-filter-more">'), 6)


class ApprovalCenterCardAnatomyTests(unittest.TestCase):
    """Batch 2: one card anatomy for every module, with waiting time."""

    template = None

    @classmethod
    def setUpClass(cls):
        if cls.template is None:
            cls.template = TEMPLATE_PATH.read_text(encoding="utf-8")

    def test_every_module_builder_uses_the_shared_card(self):
        page = self.template
        self.assertIn('function approvalCardHtml(card) {', page)
        for builder in ('function buildUnifiedApprovalItem(', 'function lprApprovalItem(',
                        'function leaveApprovalItem(', 'function calibrationCertificateApprovalItem('):
            with self.subTest(builder=builder):
                body = page.split(builder, 1)[1].split('\n    }\n', 1)[0]
                self.assertIn('approvalCardHtml({', body)

    def test_leave_card_keeps_duration_and_emergency_line_without_lpr_gate(self):
        page = self.template
        self.assertIn("['Duration', item.duration_label", page)
        self.assertIn('Emergency Sick Leave / Form to Follow', page)
        self.assertNotIn('approvalQueueFallbackCard', page)
        self.assertNotIn('approvalQueueExtensionPresent', page)

    def test_pending_cards_show_waiting_time_chip(self):
        page = self.template
        self.assertIn('approval-age-chip${days > 30 ?', page)
        self.assertIn('.approval-age-chip.is-late { background: #fde8ea; color: #a1121f; }', page)
        self.assertNotIn("|| 'Rodito';", page.split('function approvalActionBy(item) {', 1)[1].split('}', 1)[0])


class ApprovalCenterReviewWindowTests(unittest.TestCase):
    """Batch 3: review window behaviour and the incomplete-package guard."""

    template = None

    @classmethod
    def setUpClass(cls):
        if cls.template is None:
            cls.template = TEMPLATE_PATH.read_text(encoding="utf-8")

    def test_review_window_is_a_dialog_that_closes_on_escape_and_returns_focus(self):
        page = self.template
        self.assertIn('id="approvalModalBackdrop" role="dialog" aria-modal="true" aria-labelledby="approvalModalTitle"', page)
        self.assertIn("if (reviewBackdrop && reviewBackdrop.style.display === 'flex') closeApprovalModal();", page)
        self.assertIn('approvalModalOpener = active && !backdrop.contains(active) ? active : null;', page)

    def test_incomplete_package_warns_and_confirms(self):
        page = self.template
        self.assertIn('id="approvalPackageWarning"', page)
        self.assertIn("title: 'Approve with an incomplete package?'", page)
        self.assertEqual(page.count('approvalConfirmDialog(approvalPackageConfirmOptions({'), 2)

    def test_remarks_live_in_the_decision_bar_with_open_next(self):
        page = self.template
        bar = page.split('id="approvalDecisionBar"', 1)[1].split('{% if approval_center_view_only %}', 1)[0]
        for element_id in ('approvalRemarks', 'approvalOpenNext', 'approvalApproveBtn', 'approvalRejectBtn'):
            self.assertIn(f'id="{element_id}"', bar)
        self.assertIn("['approveSelectedApproval', 'rejectSelectedApproval'].forEach", page)


class ApprovalCenterCleanupTests(unittest.TestCase):
    """Batch 4: dead code and off-system values are gone."""

    template = None

    @classmethod
    def setUpClass(cls):
        if cls.template is None:
            cls.template = TEMPLATE_PATH.read_text(encoding="utf-8")

    def test_dead_refresh_paths_are_removed(self):
        page = self.template
        for removed in ('async function refreshApprovalSummary()', 'async function refreshAllApprovalCenterLists()',
                        'originalRefreshAllApprovalCenterLists', 'function renderUnifiedApprovalQueues(',
                        'approvalSummaryTotal'):
            self.assertNotIn(removed, page)
        self.assertIn('window.refreshAllApprovalCenterLists = async function () {', page)

    def test_no_heavy_weights_or_hardcoded_accent(self):
        import re
        page = self.template
        self.assertIsNone(re.search(r'font-weight:\s*[7-9]\d\d', page))
        self.assertIsNone(re.search(r'rgba\(37,\s*99,\s*235', page))
        self.assertNotIn('border-radius: 22px', page)

    def test_summary_has_no_unused_travel_query(self):
        source = (ROOT / 'app.py').read_text(encoding='utf-8')
        self.assertNotIn('travel_status_rows', source)


class ApprovalCenterPendingOverviewTests(unittest.TestCase):
    """The page subtitle reads from the unfiltered pending overview."""

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.previous_config = {key: cls.app.config.get(key) for key in ('TESTING', 'PROPAGATE_EXCEPTIONS')}
        cls.app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False)
        with cls.app.app_context():
            app_module.db.create_all()
            approver = app_module.User(
                username='approval_layout_overview_approver_20261020',
                password='test',
                role='superadmin',
                is_active=True,
                can_approve_requests=True,
            )
            app_module.db.session.add(approver)
            app_module.db.session.commit()
            cls.approver_id = approver.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            app_module.User.query.filter_by(id=cls.approver_id).delete()
            app_module.db.session.commit()
            app_module.db.session.remove()
        cls.app.config.update(cls.previous_config)

    def _get(self, url):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.approver_id)
            session['_fresh'] = True
        return client.get(url).get_json()

    def test_overview_counts_every_pending_entry_and_finds_the_oldest(self):
        entries = [
            _entry(1, date='2026-10-05T09:00:00'),
            _entry(2, date='2026-09-01T09:00:00'),
            _entry(3, status='Approved', date='2026-08-01T09:00:00'),
        ]
        with patch.object(app_module, 'approval_center_collect_queue_entries', return_value=entries):
            payload = self._get('/get_approval_center_queue?status=approved')
        self.assertEqual(payload['pending_overview'], {'count': 2, 'oldest_date': '2026-09-01'})

    def test_overview_is_left_out_when_a_module_filter_is_applied(self):
        with patch.object(app_module, 'approval_center_collect_queue_entries', return_value=[_entry(1)]):
            payload = self._get('/get_approval_center_queue?status=pending&module=travel_request')
        self.assertIsNone(payload['pending_overview'])


if __name__ == "__main__":
    unittest.main()
