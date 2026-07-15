from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")


def template_source(name):
    return (ROOT / "templates" / name).read_text(encoding="utf-8")


class AccountingAttachmentManagementTests(unittest.TestCase):
    def test_every_accounting_workflow_has_bulk_delete_endpoint(self):
        expected_routes = [
            "/delete_all_reimbursement_receipts",
            "/delete_all_travel_request_attachments/<int:travel_request_id>",
            "/delete_all_cash_advance_attachments/<int:cash_advance_id>",
            "/delete_all_travel_liquidation_receipts/<int:liquidation_id>",
            "/delete_all_cash_advance_liquidation_receipts/<int:liquidation_id>",
        ]
        for route in expected_routes:
            self.assertIn(route, APP_SOURCE)

    def test_cash_advance_attachments_use_organized_bucket_prefix_and_limits(self):
        self.assertIn("STORAGE_PREFIX_CASH_ADVANCES = 'cash_advances'", APP_SOURCE)
        self.assertIn("CASH_ADVANCE_ATTACHMENT_MAX_FILES = 10", APP_SOURCE)
        self.assertIn("reimbursement_prepare_receipt_upload_bytes", APP_SOURCE)
        self.assertIn("build_cash_advance_supporting_attachments_pdf_bytes", APP_SOURCE)

    def test_liquidation_bulk_delete_does_not_delete_expense_rows(self):
        travel_block = APP_SOURCE.split("def delete_all_travel_liquidation_receipts", 1)[1].split("@app.route", 1)[0]
        cash_block = APP_SOURCE.split("def delete_all_cash_advance_liquidation_receipts", 1)[1].split("@app.route", 1)[0]
        self.assertIn("db.session.delete(receipt)", travel_block)
        self.assertIn("db.session.delete(receipt)", cash_block)
        self.assertNotIn("db.session.delete(row)", travel_block)
        self.assertNotIn("db.session.delete(row)", cash_block)

    def test_attachment_controls_are_present_in_all_workflow_templates(self):
        expectations = {
            "reimbursement.html": "deleteAllReimbursementReceipts",
            "travel_request.html": "deleteAllTravelRequestAttachments",
            "cash_advance.html": "deleteAllCashAdvanceAttachments",
            "travel_liquidation.html": "deleteAllLiquidationReceipts",
            "cash_advance_liquidation.html": "deleteAllLiquidationReceipts",
        }
        for template, function_name in expectations.items():
            source = template_source(template)
            self.assertIn(function_name, source)
            self.assertIn("fa-trash", source)

    def test_cash_advance_approval_shows_supporting_attachments(self):
        approvals = template_source("approvals.html")
        self.assertIn("Supporting Attachments", approvals)
        self.assertIn("renderApprovalReceiptLinks(data.attachments || [])", approvals)

    def test_reimbursement_uploads_are_content_deduplicated(self):
        reimbursement = template_source("reimbursement.html")
        self.assertIn("content_sha256 = db.Column(db.String(64)", APP_SOURCE)
        self.assertIn("uq_reimbursement_receipt_content", APP_SOURCE)
        self.assertIn("reimbursement_find_duplicate_receipt", APP_SOURCE)
        self.assertIn("already uploaded. No duplicate copy was added", APP_SOURCE)
        self.assertIn("reimbursementReceiptUploadBusy", reimbursement)


if __name__ == "__main__":
    unittest.main()
