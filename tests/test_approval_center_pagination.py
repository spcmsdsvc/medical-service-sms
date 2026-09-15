"""Focused Approval Center queue, filtering, and pagination contracts."""

import os
import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
os.environ.setdefault(
    "MEDICAL_SERVICE_TEST_DB",
    str(pathlib.Path(tempfile.gettempdir()) / "medical_service_approval_center_pagination_tests.db"),
)

import app as app_module  # noqa: E402


def _entry(
    record_id,
    *,
    module="travel_request",
    status="Submitted",
    requester="Alice Engineer",
    date="2026-09-01T09:00:00",
    reference=None,
    context="Cebu service",
):
    reference = reference or f"{module.upper()}-{record_id}"
    item = {
        "id": record_id,
        "status": status,
        "request_no": reference,
        "requester_name": requester,
        "destination": context,
        "purpose": context,
        "client_name": context,
        "submitted_at": date,
        "approved_at": date if status == "Approved" else "",
        "rejected_at": date if status == "Rejected" else "",
        "updated_at": date,
    }
    return {
        "module": module,
        "module_label": module.replace("_", " ").title(),
        "status": status,
        "record_id": record_id,
        "requester": requester,
        "action_date": date,
        "item": item,
    }


class ApprovalCenterQueueHelperTests(unittest.TestCase):
    def setUp(self):
        self.entries = [
            _entry(index, date=f"2026-09-{index:02d}T09:00:00")
            for index in range(1, 24)
        ]

    def test_fixed_ten_card_pages_have_stable_boundaries(self):
        first = app_module.approval_center_filter_and_paginate(
            self.entries, requested_status="pending", page=1
        )
        third = app_module.approval_center_filter_and_paginate(
            self.entries, requested_status="pending", page=3
        )
        self.assertEqual(first["per_page"], 10)
        self.assertEqual(first["total"], 23)
        self.assertEqual(first["pages"], 3)
        self.assertEqual(first["page"], 1)
        self.assertEqual(len(first["items"]), 10)
        self.assertEqual(third["page"], 3)
        self.assertEqual([item["record_id"] for item in third["items"]], [21, 22, 23])
        self.assertEqual(
            len({item["record_id"] for item in first["items"]} | {item["record_id"] for item in third["items"]}),
            13,
        )

    def test_page_clamps_and_filters_are_case_insensitive_and_inclusive(self):
        filtered = app_module.approval_center_filter_and_paginate(
            [
                _entry(1, requester="Alice Engineer", context="Cebu Hospital", date="2026-09-01T09:00:00"),
                _entry(2, requester="Bob Engineer", context="Manila Clinic", date="2026-09-02T09:00:00"),
                _entry(3, requester="Alice Engineer", context="Cebu Hospital", date="2026-09-03T09:00:00"),
            ],
            requested_status="pending",
            q="hospital",
            requester="ALICE",
            date_from="2026-09-01",
            date_to="2026-09-03",
            page=999,
        )
        self.assertEqual(filtered["page"], 1)
        self.assertEqual(filtered["total"], 2)
        self.assertEqual([item["record_id"] for item in filtered["items"]], [1, 3])

    def test_sort_modes_and_module_filter_have_deterministic_ties(self):
        entries = [
            _entry(2, module="reimbursement", date="2026-09-05T09:00:00"),
            _entry(1, module="travel_request", date="2026-09-05T09:00:00"),
            _entry(3, module="travel_request", date="2026-09-02T09:00:00"),
        ]
        newest = app_module.approval_center_filter_and_paginate(
            entries, requested_status="pending", sort="newest"
        )
        oldest = app_module.approval_center_filter_and_paginate(
            entries, requested_status="pending", sort="oldest"
        )
        only_travel = app_module.approval_center_filter_and_paginate(
            entries, requested_status="pending", module="travel_request"
        )
        self.assertEqual([item["record_id"] for item in newest["items"]], [2, 1, 3])
        self.assertEqual([item["record_id"] for item in oldest["items"]], [3, 2, 1])
        self.assertEqual([item["record_id"] for item in only_travel["items"]], [3, 1])

    def test_invalid_queue_parameters_raise_clear_value_errors(self):
        for kwargs in (
            {"requested_status": "draft"},
            {"module": "not_a_module"},
            {"date_from": "09/01/2026"},
            {"sort": "random"},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    app_module.approval_center_filter_and_paginate(self.entries, **kwargs)


class ApprovalCenterPageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = (ROOT / "templates" / "approvals.html").read_text(encoding="utf-8")
        cls.source = (ROOT / "app.py").read_text(encoding="utf-8")

    def test_unified_queue_route_and_normalized_metadata_exist(self):
        self.assertIn("@app.route('/get_approval_center_queue')", self.source)
        self.assertIn("approval_center_filter_and_paginate", self.source)
        self.assertIn("'module_label'", self.source)
        self.assertIn("'record_id'", self.source)
        self.assertIn("'active_modules'", self.source)
        self.assertNotIn("get_approval_center_queue", self.source.split("def get_approval_center_items", 1)[1].split("def get_approval_audit_trail", 1)[0])

    def test_shared_filters_pagination_and_stale_request_guard_are_present(self):
        for marker in (
            'id="approvalQueueSearch"',
            'id="approvalQueueRequester"',
            'id="approvalQueueModule"',
            'id="approvalQueueDateFrom"',
            'id="approvalQueueDateTo"',
            'id="approvalQueueSort"',
            'id="approvalQueueClear"',
            'id="approvalQueuePagination"',
            "get_approval_center_queue",
            "AbortController",
            "approvalQueueRequestSequence",
            "Showing",
            "Previous",
            "Next",
            "aria-live=\"polite\"",
            "aria-busy",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.template)

    def test_existing_action_and_deep_link_contracts_remain(self):
        for marker in (
            "openTravelApprovalDetail",
            "openReimbursementApprovalDetail",
            "openCashAdvanceApprovalDetail",
            "openCashAdvanceLiquidationApprovalDetail",
            "openLiquidationApprovalDetail",
            "openCalibrationCertificateApprovalDetail",
            "openLeaveApprovalDetail",
            "openLprApprovalDetail",
            "approvalCurrentRecordIdForModule",
            "URLSearchParams",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.template)


class ApprovalCenterQueueWorkflowTests(unittest.TestCase):
    """Exercise route isolation and the revision/feature-switch guards."""

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.previous_config = {
            key: cls.app.config.get(key)
            for key in ('TESTING', 'WTF_CSRF_ENABLED', 'PROPAGATE_EXCEPTIONS', 'LPR_ENABLED')
        }
        cls.app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=False,
            PROPAGATE_EXCEPTIONS=False,
            LPR_ENABLED=True,
        )
        cls.created_user_ids = []
        with cls.app.app_context():
            app_module.db.create_all()
            approver = app_module.User(
                username='approval_queue_route_approver_20260915',
                password='test',
                role='superadmin',
                is_active=True,
                can_approve_requests=True,
            )
            outsider = app_module.User(
                username='approval_queue_route_outsider_20260915',
                password='test',
                role='engineer',
                is_active=True,
                can_approve_requests=False,
            )
            app_module.db.session.add_all([approver, outsider])
            app_module.db.session.commit()
            cls.approver_id = approver.id
            cls.outsider_id = outsider.id
            cls.created_user_ids.extend([approver.id, outsider.id])

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            try:
                if cls.created_user_ids:
                    app_module.User.query.filter(
                        app_module.User.id.in_(cls.created_user_ids)
                    ).delete(synchronize_session=False)
                    app_module.db.session.commit()
            except Exception:
                app_module.db.session.rollback()
            finally:
                app_module.db.session.remove()
        cls.app.config.update(cls.previous_config)

    def _client(self, user_id):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def test_route_clamps_page_and_rejects_invalid_status(self):
        entries = [_entry(index, date=f'2026-09-{index:02d}T09:00:00') for index in range(1, 13)]
        with patch.object(app_module, 'approval_center_collect_queue_entries', return_value=entries):
            response = self._client(self.approver_id).get('/get_approval_center_queue?status=pending&page=999')
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
            payload = response.get_json()
            self.assertEqual(payload['page'], 2)
            self.assertEqual(payload['pages'], 2)
            self.assertEqual(payload['per_page'], 10)
            self.assertEqual(len(payload['items']), 2)

            invalid = self._client(self.approver_id).get('/get_approval_center_queue?status=unknown')
            self.assertEqual(invalid.status_code, 400)
            self.assertIn('Invalid approval queue status', invalid.get_json()['error'])

    def test_route_keeps_approval_center_authorization_isolated(self):
        denied = self._client(self.outsider_id).get('/get_approval_center_queue')
        self.assertEqual(denied.status_code, 403)

    def test_disabled_lpr_is_explicitly_denied(self):
        self.app.config['LPR_ENABLED'] = False
        response = self._client(self.approver_id).get('/get_approval_center_queue?module=lpr')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json().get('status'), 'disabled')

    def test_pending_calibration_entries_only_include_latest_revision(self):
        latest = SimpleNamespace(is_latest=True)
        old = SimpleNamespace(is_latest=False)
        rows = [
            (latest, _entry(10, module='calibration_certificate', status='Pending')),
            (old, _entry(11, module='calibration_certificate', status='Pending')),
        ]
        metadata = [{
            'key': 'calibration_certificate',
            'label': 'Calibration Report & Certificate',
            'status': 'active',
            'enabled': True,
        }]
        with patch.object(app_module, 'approval_center_active_module_metadata', return_value=metadata), \
                patch.object(app_module, 'approval_center_queue_module_rows', return_value=rows):
            entries = app_module.approval_center_collect_queue_entries('calibration_certificate')
        self.assertEqual([entry['record_id'] for entry in entries], [10])

if __name__ == "__main__":
    unittest.main()
