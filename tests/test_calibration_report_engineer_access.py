"""Focused access checks for approved generated Calibration Report PDFs."""

import json
import gc
import os
import pathlib
import tempfile
import unittest
import uuid
from datetime import datetime
from flask import g
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_calibration_report_access_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB_PATH))
os.environ.setdefault("SECRET_KEY", "calibration-report-access-tests")

import app as app_module  # noqa: E402
from tests.schema_flags import reset_schema_flags  # noqa: E402


class CalibrationReportEngineerAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=True)

    def setUp(self):
        self.context = self.app.app_context()
        self.context.push()
        app_module.db.create_all()
        app_module.ensure_calibration_certificate_approval_table()
        app_module.ensure_calibration_report_conversion_table()

        suffix = uuid.uuid4().hex[:8]
        self.requester = app_module.User(
            username=f"calibration-requester-{suffix}", password="test", role="engineer", is_active=True
        )
        self.remote_engineer = app_module.User(
            username=f"calibration-remote-engineer-{suffix}", password="test", role=" ENGINEER ", is_active=True
        )
        self.scheduler = app_module.User(
            username=f"calibration-scheduler-{suffix}", password="test", role="scheduler", is_active=True
        )
        self.requester_profile = app_module.Engineer(
            employee_id=f"CAL-REQ-{suffix}", name="Request Engineer", initials="RE", branch="Manila"
        )
        self.remote_profile = app_module.Engineer(
            employee_id=f"CAL-REMOTE-{suffix}", name="Remote Engineer", initials="RME", branch="Davao"
        )
        self.client_record = app_module.Client(name=f"Calibration Report Client {suffix}")
        app_module.db.session.add_all([
            self.requester,
            self.remote_engineer,
            self.scheduler,
            self.requester_profile,
            self.remote_profile,
            self.client_record,
        ])
        app_module.db.session.flush()
        self.requester_profile.user_id = self.requester.id
        self.remote_profile.user_id = self.remote_engineer.id
        self.product = app_module.Product(
            serial_number=f"CAL-REPORT-{suffix}", name="Calibration Report Unit", client_id=self.client_record.id
        )
        app_module.db.session.add(self.product)
        app_module.db.session.flush()
        self.shift = app_module.Shift(
            title="Calibration Report Access",
            start_time=datetime(2026, 9, 1, 9, 0),
            end_time=datetime(2026, 9, 1, 10, 0),
            engineer_id=self.requester_profile.id,
            client_id=self.client_record.id,
            product_id=self.product.serial_number,
            status="Completed",
        )
        app_module.db.session.add(self.shift)
        app_module.db.session.flush()
        app_module.db.session.add(app_module.ShiftEngineer(
            shift_id=self.shift.id, engineer_id=self.requester_profile.id
        ))

        token = uuid.uuid4().hex
        self.submission = app_module.OnlineTsrSubmission(
            shift_id=self.shift.id,
            tsr_number=f"TSR-CAL-ACCESS-{token[:8]}",
            submitted_by_user_id=self.requester.id,
            submitted_by_name="Request Engineer",
            status="completed",
            payload_json=json.dumps({
                "calibration_report": {},
                "_generated_calibration_report": {
                    "source": "generated_calibration_report",
                    "file_id": 0,
                },
            }),
        )
        app_module.db.session.add(self.submission)
        app_module.db.session.flush()
        self.signed_file = app_module.ShiftFile(
            shift_id=self.shift.id,
            filename=f"signed-certificate-{token}.pdf",
            original_filename="Calibration Certificate.pdf",
            online_tsr_submission_id=self.submission.id,
        )
        self.source_file = app_module.ShiftFile(
            shift_id=self.shift.id,
            filename=f"generated-calibration-report-source-{token}.docx",
            original_filename="Calibration Report source.docx",
            online_tsr_submission_id=self.submission.id,
        )
        app_module.db.session.add_all([self.signed_file, self.source_file])
        app_module.db.session.flush()
        self.submission.payload_json = json.dumps({
            "calibration_report": {},
            "_generated_calibration_report": {
                "source": "generated_calibration_report",
                "file_id": self.source_file.id,
            },
        })
        self.report_file = app_module.ShiftFile(
            shift_id=self.shift.id,
            filename=f"generated-calibration-report-{token}.pdf",
            original_filename="Calibration Report.pdf",
            online_tsr_submission_id=self.submission.id,
        )
        app_module.db.session.add(self.report_file)
        app_module.db.session.flush()
        self.conversion = app_module.CalibrationReportConversion(
            source_shift_file_id=self.source_file.id,
            pdf_shift_file_id=self.report_file.id,
            source_sha256="source-fixture",
            pdf_sha256="pdf-fixture",
            converter_version="test-fixture",
            state="ready",
            attempts=1,
            converted_at=datetime(2026, 9, 1, 11, 0),
            updated_at=datetime(2026, 9, 1, 11, 0),
        )
        app_module.db.session.add(self.conversion)
        self.approval = app_module.CalibrationCertificateApproval(
            shift_id=self.shift.id,
            online_tsr_submission_id=self.submission.id,
            requester_user_id=self.requester.id,
            revision_no=1,
            is_latest=True,
            status="Approved",
            certificate_number=f"CERT-{token[:8]}",
            mapped_data_json=json.dumps({"Text3": self.product.serial_number}),
            template_sha256="template",
            unsigned_artifact_path=f"unsigned-{token}.pdf",
            signed_shift_file_id=self.signed_file.id,
            approved_at=datetime(2026, 9, 1, 12, 0),
        )
        app_module.db.session.add(self.approval)
        app_module.db.session.commit()

    def tearDown(self):
        app_module.db.session.remove()
        app_module.db.drop_all()
        reset_schema_flags(app_module)
        self.context.pop()
        try:
            TEST_DB_PATH.unlink(missing_ok=True)
        except OSError:
            pass

    def client_for(self, user):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True
        return client

    def product_summary_for(self, client):
        g.pop("_login_user", None)
        response = client.get("/get_products")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        response.close()
        return next(row["calibration_summary"] for row in payload if row["serial_number"] == self.product.serial_number)

    def test_active_engineers_can_view_exact_report_and_other_roles_cannot(self):
        remote_client = self.client_for(self.remote_engineer)
        summary = self.product_summary_for(remote_client)
        self.assertIn(f"approval_id={self.approval.id}", summary["calibration_report_preview_url"])
        self.assertIn(f"approval_id={self.approval.id}", summary["calibration_report_download_url"])

        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = pathlib.Path(temp_dir) / "calibration-report.pdf"
            report_path.write_bytes(b"%PDF-1.4 generated calibration report")
            with patch.object(app_module, "managed_storage_read_path", return_value=str(report_path)):
                preview = remote_client.get(
                    f"/preview_tsr_archive_file/{self.report_file.id}?scope=all&approval_id={self.approval.id}"
                )
                with patch.object(app_module, "send_file", return_value=app_module.Response(b"report")):
                    download = remote_client.get(
                        f"/download_tsr_archive_file/{self.report_file.id}?scope=all&approval_id={self.approval.id}"
                    )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(download.status_code, 200)
        preview.close()
        download.close()
        del preview, download
        gc.collect()

        scheduler_client = self.client_for(self.scheduler)
        self.assertEqual(self.product_summary_for(scheduler_client)["calibration_report_preview_url"], "")
        denied = scheduler_client.get(
            f"/download_tsr_archive_file/{self.report_file.id}?scope=all&approval_id={self.approval.id}"
        )
        self.assertEqual(denied.status_code, 403)

        requester_summary = self.product_summary_for(self.client_for(self.requester))
        self.assertTrue(requester_summary["calibration_report_preview_url"])

    def test_report_access_rejects_stale_unready_unsigned_and_mismatched_artifacts(self):
        remote_client = self.client_for(self.remote_engineer)
        original_status = self.approval.status
        original_latest = self.approval.is_latest
        original_signed_file_id = self.approval.signed_shift_file_id
        original_state = self.conversion.state
        try:
            for status, latest in (("Pending", True), ("Returned", True), ("Approved", False)):
                self.approval.status = status
                self.approval.is_latest = latest
                app_module.db.session.commit()
                self.assertEqual(self.product_summary_for(remote_client)["calibration_report_preview_url"], "")
                self.assertIsNone(
                    app_module.calibration_certificate_report_approval_for_file_download(
                        self.report_file, self.approval.id
                    )
                )

            self.approval.status = "Approved"
            self.approval.is_latest = True
            self.conversion.state = "failed"
            app_module.db.session.commit()
            self.assertEqual(self.product_summary_for(remote_client)["calibration_report_preview_url"], "")

            self.conversion.state = "ready"
            self.approval.signed_shift_file_id = None
            app_module.db.session.commit()
            self.assertEqual(self.product_summary_for(remote_client)["calibration_report_preview_url"], "")

            unrelated = app_module.ShiftFile(
                shift_id=self.shift.id,
                filename="unrelated.pdf",
                original_filename="Unrelated.pdf",
                online_tsr_submission_id=self.submission.id,
            )
            app_module.db.session.add(unrelated)
            app_module.db.session.commit()
            self.approval.signed_shift_file_id = original_signed_file_id
            app_module.db.session.commit()
            self.assertIsNone(
                app_module.calibration_certificate_report_approval_for_file_download(
                    unrelated, self.approval.id
                )
            )
            self.assertIsNone(
                app_module.calibration_certificate_report_approval_for_file_download(
                    self.source_file, self.approval.id
                )
            )
        finally:
            self.approval.status = original_status
            self.approval.is_latest = original_latest
            self.approval.signed_shift_file_id = original_signed_file_id
            self.conversion.state = original_state
            app_module.db.session.commit()


if __name__ == "__main__":
    unittest.main()
