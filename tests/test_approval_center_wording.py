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

    def test_calibration_certificate_modal_exposes_pdf_download_or_unavailable_state(self):
        self.assertIn("data.calibration_report_download_url", self.source)
        self.assertIn("data.calibration_report_filename", self.source)
        self.assertIn("Download Calibration Report (PDF)", self.source)
        self.assertIn('href="${approvalEscape(data.calibration_report_download_url)}"', self.source)
        self.assertIn('target="_blank" rel="noopener"', self.source)
        self.assertIn("The Calibration Report PDF is still being prepared after TSR synchronization.", self.source)
        self.assertIn("PDF conversion failed. Retry the report conversion before reviewing this certificate.", self.source)

    def test_calibration_decision_handlers_report_failures_and_signature_requirements(self):
        handlers = {
            "approveSelectedCalibrationCertificate": "Unable to approve Calibration Certificate.",
            "returnSelectedCalibrationCertificate": "Unable to return Calibration Certificate.",
        }
        for name, fallback in handlers.items():
            with self.subTest(handler=name):
                start = self.source.index(f"async function {name}()")
                next_handler = self.source.find("\n    async function ", start + 1)
                end = next_handler if next_handler != -1 else self.source.index(
                    "\n    const originalBuildCalibrationCertificateApprovalItem",
                    start,
                )
                body = self.source[start:end]
                self.assertIn("try {", body)
                self.assertIn("catch (error)", body)
                self.assertIn("showApprovalSignatureRequiredPrompt(error)", body)
                self.assertIn("approvalAlert(error.message ||", body)
                self.assertIn(fallback, body)
                self.assertIn("approvalAlert(payload.message ||", body)
                self.assertIn("closeApprovalModal()", body)
                self.assertIn("await refreshAllApprovalCenterLists()", body)

    def test_calibration_report_preview_has_accessible_nested_dialog_and_safe_data_binding(self):
        self.assertIn("Preview Calibration Report", self.source)
        self.assertIn('id="approvalCalibrationReportPreviewBackdrop"', self.source)
        self.assertIn('role="dialog" aria-modal="true"', self.source)
        self.assertIn('aria-labelledby="approvalCalibrationReportPreviewTitle"', self.source)
        self.assertIn('id="approvalCalibrationReportPreviewStatus"', self.source)
        self.assertIn('role="status" aria-live="polite"', self.source)
        self.assertIn('id="approvalCalibrationReportPreviewError"', self.source)
        self.assertIn('id="approvalCalibrationReportPreviewContent"', self.source)
        self.assertIn('data-calibration-report-preview-url="${approvalEscape(calibrationReportPreviewUrl)}"', self.source)
        self.assertIn('data-calibration-report-preview-filename="${approvalEscape(data.calibration_report_filename || \'Calibration Report.pdf\')}"', self.source)
        self.assertNotIn('onclick="openCalibrationReportPreview', self.source)
        self.assertNotIn("onclick='openCalibrationReportPreview", self.source)
        self.assertIn("id=\"approvalCalibrationReportPreviewClose\"", self.source)
        self.assertIn("id=\"approvalCalibrationReportPreviewFooterClose\"", self.source)

    def test_calibration_report_preview_uses_authenticated_server_pdf_viewer(self):
        for expected in (
            "const reportUrl = new URL(String(url), window.location.origin).href",
            "frame.src = reportUrl",
            "preview_tsr_archive_file",
            "setCalibrationReportPreviewState('ready'",
            "closeCalibrationReportPreview",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.source)
        self.assertIn("calibrationReportPreviewSequence", self.source)
        self.assertNotIn("docx-preview.min.js", self.source)
        self.assertNotIn("docx.renderAsync", self.source)


if __name__ == "__main__":
    unittest.main()
