import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APPROVALS_TEMPLATE = ROOT / "templates" / "approvals.html"


class ApprovalCenterWordingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = APPROVALS_TEMPLATE.read_text(encoding="utf-8")

    def test_shared_modal_is_not_reimbursement_specific(self):
        self.assertIn('id="approvalModalTitle">Request Review</h2>', self.source)
        self.assertIn('id="approvalRemarksLabel"', self.source)
        self.assertNotIn('id="approvalModalTitle">Reimbursement Review</h2>', self.source)
        self.assertNotIn(">Manager Remarks</label>", self.source)

    def test_every_module_uses_guarded_modal_loading(self):
        modules = (
            "calibration_certificate",
            "reimbursement",
            "travel_request",
            "travel_liquidation",
            "cash_advance",
            "cash_advance_liquidation",
            "lpr",
            "leave_request",
        )
        for module in modules:
            with self.subTest(module=module):
                self.assertIn(f"beginApprovalModalLoad('{module}')", self.source)
                self.assertIn(
                    f"approvalModalLoadIsCurrent(loadToken, '{module}')",
                    self.source,
                )
                self.assertIn(
                    f"showApprovalModalLoadError(loadToken, '{module}'",
                    self.source,
                )

        self.assertIn(
            "window.openCalibrationCertificateApprovalDetail = openCalibrationCertificateApprovalDetail;",
            self.source,
        )

    def test_module_names_and_negative_actions_are_consistent(self):
        expected_copy = {
            "calibration_certificate": "Return for Correction",
            "reimbursement": "Return for Correction",
            "travel_request": "Return for Correction",
            "travel_liquidation": "Return for Revision",
            "cash_advance": "Return for Correction",
            "cash_advance_liquidation": "Return for Revision",
            "lpr": "Return for Correction",
            "leave_request": "Reject",
        }
        for module, action in expected_copy.items():
            with self.subTest(module=module):
                pattern = (
                    rf"{re.escape(module)}:\s*\{{.*?"
                    rf"negativeAction:\s*'{re.escape(action)}'"
                )
                self.assertRegex(self.source, re.compile(pattern, re.DOTALL))

        self.assertIn("<strong>Travel Liquidation</strong>", self.source)
        self.assertIn("<strong>Cash Advance Liquidation</strong>", self.source)
        self.assertIn("<strong>Leave Request</strong>", self.source)
        self.assertNotIn("<strong>CA Liquidation</strong>", self.source)

    def test_reimbursement_heading_prefers_request_number(self):
        self.assertIn(
            "`Review ${data.request_no || ('Reimbursement #' + data.id)}`",
            self.source,
        )

    def test_calibration_notification_opens_certificate_review(self):
        self.assertIn(
            "await openCalibrationCertificateApprovalDetail(Number(recordId));",
            self.source,
        )

    def test_calibration_certificate_modal_uses_preview_only_urls(self):
        self.assertIn(
            "data.signed_preview_url || data.unsigned_preview_url || '#'",
            self.source,
        )
        self.assertNotIn(
            'src="${approvalEscape(data.signed_url || data.unsigned_url || \'#\')}"',
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
