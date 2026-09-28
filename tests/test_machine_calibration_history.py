"""Focused contracts for source-aware calibration history and due-date warnings."""

import json
import os
import pathlib
import tempfile
import unittest
import uuid
from datetime import date, datetime
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_calibration_history_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB_PATH))
os.environ.setdefault("SECRET_KEY", "calibration-history-tests")

import app as app_module  # noqa: E402


class MachineCalibrationHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=True)

    def setUp(self):
        self.context = self.app.app_context()
        self.context.push()
        app_module.db.create_all()
        app_module.ensure_calibration_certificate_approval_table()
        suffix = uuid.uuid4().hex[:8].upper()
        self.user = app_module.User(
            username=f"calibration-history-admin-{suffix}", password="test", role="admin", is_active=True
        )
        self.engineer = app_module.Engineer(
            employee_id=f"CAL-HIST-{suffix}", name="Report Calibrator", initials="RC", branch="Manila"
        )
        self.client = app_module.Client(name=f"Calibration Client {suffix}")
        app_module.db.session.add_all([self.user, self.engineer, self.client])
        app_module.db.session.flush()
        self.product = app_module.Product(
            serial_number=f"CAL-PRODUCT-{suffix}", name="Product Calibration Unit", client_id=self.client.id
        )
        self.genoray = app_module.GenorayItem(
            serial_number=self.product.serial_number, name="Genoray Calibration Unit", client_id=self.client.id
        )
        self.vieworks = app_module.VieworksItem(
            serial_number=f"VIEW-CAL-{suffix}", name="Vieworks Calibration Unit", client_id=self.client.id
        )
        app_module.db.session.add_all([self.product, self.genoray, self.vieworks])
        app_module.db.session.commit()

    def tearDown(self):
        app_module.db.session.remove()
        app_module.db.drop_all()
        self.context.pop()
        try:
            TEST_DB_PATH.unlink(missing_ok=True)
        except OSError:
            pass

    def client_for_user(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(self.user.id)
            session["_fresh"] = True
        return client

    def make_approval(self, machine, calibration_date, *, source="product", status="Approved", latest=True, calibrator="Report Calibrator"):
        shift = app_module.Shift(
            title="Calibration visit",
            start_time=datetime(2026, 1, 1, 9, 0),
            end_time=datetime(2026, 1, 1, 10, 0),
            engineer_id=self.engineer.id,
            client_id=self.client.id,
            product_id=machine.serial_number,
            equipment_source=source,
            status="Completed",
        )
        app_module.db.session.add(shift)
        app_module.db.session.flush()
        token = uuid.uuid4().hex
        submission = app_module.OnlineTsrSubmission(
            shift_id=shift.id,
            tsr_number=f"TSR-CAL-{token[:8]}",
            client_name=self.client.name,
            product_name=machine.name,
            serial_number=machine.serial_number,
            submitted_by_user_id=self.user.id,
            submitted_by_name=calibrator,
            status="completed",
            submission_token=f"submission-{token}",
            payload_json=json.dumps({
                "calibration_report": {
                    "machine": {"serial_number": machine.serial_number, "modality": machine.name},
                    "facility": {"name": self.client.name},
                    "calibration": {
                        "machine_calibration_date": calibration_date,
                        "next_calibration_date": "2099-01-01",
                        "engineer_name": calibrator,
                    },
                }
            }),
            revision_no=1,
            is_latest=True,
        )
        app_module.db.session.add(submission)
        app_module.db.session.flush()
        signed_file = app_module.ShiftFile(
            shift_id=shift.id,
            filename=f"signed-{token}.pdf",
            original_filename=f"Calibration_Certificate_{token}.pdf",
        )
        app_module.db.session.add(signed_file)
        app_module.db.session.flush()
        approval = app_module.CalibrationCertificateApproval(
            shift_id=shift.id,
            online_tsr_submission_id=submission.id,
            requester_user_id=self.user.id,
            revision_no=1,
            is_latest=latest,
            status=status,
            certificate_number=f"CERT-{token[:8]}",
            mapped_data_json=json.dumps({
                "Textfield": f"CERT-{token[:8]}",
                "Text3": machine.serial_number,
                "Text4": calibration_date.replace("-", "/"),
                "Text5": "2099/01/01",
                "Text6": self.client.name,
            }),
            template_sha256="template",
            unsigned_artifact_path=f"unsigned-{token}.pdf",
            signed_shift_file_id=signed_file.id,
            approved_at=datetime(2026, 1, 2, 10, 0) if status == "Approved" else None,
            submitted_at=datetime(2026, 1, 1, 10, 0),
        )
        app_module.db.session.add(approval)
        app_module.db.session.commit()
        return approval

    def test_source_aware_summary_and_calendar_date_status(self):
        product_approval = self.make_approval(self.product, "2026-01-15", source="product")
        genoray_approval = self.make_approval(self.genoray, "2026-08-20", source="genoray")
        vieworks_approval = self.make_approval(self.vieworks, "2026-07-01", source="vieworks")
        response = self.client_for_user().get("/get_products?operational=1")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        rows = {(row["equipment_source"], row["serial_number"]): row for row in response.get_json()}
        product_summary = rows[("product", self.product.serial_number)]["calibration_summary"]
        genoray_summary = rows[("genoray", self.genoray.serial_number)]["calibration_summary"]
        vieworks_summary = rows[("vieworks", self.vieworks.serial_number)]["calibration_summary"]
        self.assertEqual(product_summary["approval_id"], product_approval.id)
        self.assertEqual(genoray_summary["approval_id"], genoray_approval.id)
        self.assertEqual(vieworks_summary["approval_id"], vieworks_approval.id)
        self.assertEqual(product_summary["calibration_date"], "2026-01-15")
        self.assertEqual(genoray_summary["calibration_date"], "2026-08-20")
        self.assertEqual(product_summary["certificate_preview_url"], "")
        self.assertEqual(product_summary["calibration_report_preview_url"], "")
        for source, machine, approval in (
            ("product", self.product, product_approval),
            ("genoray", self.genoray, genoray_approval),
            ("vieworks", self.vieworks, vieworks_approval),
        ):
            row = rows[(source, machine.serial_number)]
            self.assertEqual(row["calibration_summary"]["record_count"], 1)
            self.assertEqual(row["calibration_history"][0]["approval_id"], approval.id)
            self.assertFalse(any("url" in key for key in row["calibration_history"][0]))

        page_response = self.client_for_user().get("/get_products")
        self.assertEqual(page_response.status_code, 200, page_response.get_data(as_text=True))
        page_product = next(row for row in page_response.get_json() if row["serial_number"] == self.product.serial_number)
        self.assertTrue(page_product["calibration_summary"]["certificate_preview_url"])
        self.assertEqual(page_product["calibration_summary"]["calibration_report_preview_url"], "")

        genoray_response = self.client_for_user().get("/api/genoray/items")
        self.assertEqual(genoray_response.status_code, 200, genoray_response.get_data(as_text=True))
        page_genoray = next(row for row in genoray_response.get_json() if row["serial_number"] == self.genoray.serial_number)
        self.assertTrue(page_genoray["calibration_summary"]["certificate_preview_url"])

        vieworks_response = self.client_for_user().get("/api/vieworks/items")
        self.assertEqual(vieworks_response.status_code, 200, vieworks_response.get_data(as_text=True))
        page_vieworks = next(row for row in vieworks_response.get_json() if row["serial_number"] == self.vieworks.serial_number)
        self.assertTrue(page_vieworks["calibration_summary"]["certificate_preview_url"])
        with patch.object(app_module, "get_manila_today", return_value=date(2027, 1, 15)):
            status = app_module.calibration_status_for_summary(product_summary)
        self.assertEqual(status["label"], "Due today")

    def test_history_contains_multiple_approved_records_and_hides_pending(self):
        older = self.make_approval(self.product, "2025-01-15", source="product")
        newer = self.make_approval(self.product, "2026-01-15", source="product")
        pending = self.make_approval(self.product, "2026-09-01", source="product", status="Pending")
        response = self.client_for_user().get(f"/api/products/{self.product.serial_number}/history")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        rows = response.get_json()["calibrations"]
        self.assertEqual({row["approval_id"] for row in rows}, {older.id, newer.id})
        self.assertEqual(rows[0]["calibration_date"], "2026-01-15")
        self.assertEqual(rows[0]["calibrated_by"], "Report Calibrator")
        self.assertNotIn(pending.id, {row["approval_id"] for row in rows})
        self.assertTrue(rows[0]["certificate_preview_url"])

        operational_response = self.client_for_user().get("/get_products?operational=1")
        self.assertEqual(operational_response.status_code, 200, operational_response.get_data(as_text=True))
        operational_row = next(
            row for row in operational_response.get_json()
            if row["equipment_source"] == "product" and row["serial_number"] == self.product.serial_number
        )
        self.assertEqual(
            [row["approval_id"] for row in operational_row["calibration_history"]],
            [newer.id, older.id],
        )
        self.assertEqual(operational_row["calibration_summary"]["record_count"], 2)
        self.assertFalse(any("url" in key for key in operational_row["calibration_history"][0]))
        self.assertNotIn("certificate_preview_url", operational_row["calibration_history"][0])

        schedule_response = self.client_for_user().get("/get_offline_tsr_schedule_options")
        self.assertEqual(schedule_response.status_code, 200, schedule_response.get_data(as_text=True))
        schedule = next(row for row in schedule_response.get_json()["schedules"] if row["id"] == newer.shift_id)
        self.assertEqual(
            [row["approval_id"] for row in schedule["calibration_history"]],
            [newer.id, older.id],
        )
        self.assertEqual(schedule["calibration_summary"]["record_count"], 2)
        self.assertFalse(any("url" in key for key in schedule["calibration_summary"]))

    def test_date_boundaries_use_clamped_calendar_months(self):
        expiry = app_module.calibration_valid_until(date(2024, 2, 29))
        self.assertEqual(expiry, date(2025, 2, 28))
        summary = {"calibration_date": "2024-02-29", "valid_until": expiry.isoformat()}
        cases = [
            (date(2024, 11, 28), "Due within 3 months"),
            (date(2024, 12, 28), "Due within 2 months"),
            (date(2025, 1, 28), "Due within 1 month"),
            (date(2025, 2, 28), "Due today"),
            (date(2025, 3, 1), "Calibration expired"),
        ]
        for reference, expected in cases:
            with self.subTest(reference=reference):
                self.assertEqual(app_module.calibration_status_for_summary(summary, reference)["label"], expected)

    def test_products_and_timeline_markup_exposes_calibration_history_and_priority(self):
        products_source = (ROOT / "templates" / "products.html").read_text(encoding="utf-8")
        timeline_source = (ROOT / "templates" / "timeline.html").read_text(encoding="utf-8")
        offline_tsr_source = (ROOT / "templates" / "offline_tsr.html").read_text(encoding="utf-8")
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        releases = json.loads((ROOT / "static" / "changelog" / "releases.json").read_text(encoding="utf-8"))
        self.assertIn("calibration_summary", products_source)
        self.assertIn("Calibration History", products_source)
        self.assertIn("calibrated_by", products_source)
        self.assertIn("calibration_report_preview_url", products_source)
        self.assertIn("function renderProductCalibrationDocumentLinks(product, mobile = false)", products_source)
        self.assertIn("product-serial-document-actions", products_source)
        self.assertIn("<span>View Report</span>", products_source)
        self.assertIn("<span>View Certificate</span>", products_source)
        self.assertIn("if(summary.calibration_report_preview_url)", products_source)
        self.assertIn("if(summary.certificate_preview_url)", products_source)
        self.assertNotIn("product-calibration-date", products_source)
        self.assertIn("function sortCalibrationProducts", timeline_source)
        self.assertIn("slice(0, 10)", timeline_source)
        self.assertIn("timeline-product-search-identity", timeline_source)
        self.assertIn("timeline-product-search-statuses", timeline_source)
        self.assertIn("getProductCalibrationPickerLabel", timeline_source)
        self.assertIn("Valid to ${status.expiry}", timeline_source)
        self.assertIn("Due 1 mo", timeline_source)
        self.assertIn("calibration-status-details", timeline_source)
        self.assertIn("calibrationHistory", timeline_source)
        self.assertIn("informational", timeline_source.lower())
        self.assertIn("offline-tsr-calibration-history", offline_tsr_source)
        self.assertIn("refreshStandaloneCalibrationHistory", offline_tsr_source)
        self.assertIn("calibration_history", offline_tsr_source)
        self.assertIn("require an internet connection", offline_tsr_source)
        calibration_card = offline_tsr_source.split('id="calibration-report-card"', 1)[1].split(
            '<div class="card p-3 p-md-4 mb-3 no-print">', 1
        )[0]
        self.assertIn('offline-tsr-calibration-workspace', calibration_card)
        self.assertLess(
            calibration_card.index('id="calibration-report-create-btn"'),
            calibration_card.index('id="tsr-calibration-history-panel"'),
        )
        self.assertIn("medical-service-pwa-offline-navigation-v206-calendar-tsr-actions", app_source)
        release = next(item for item in releases["releases"] if item["release_key"] == "2026-09-27-machine-calibration-history")
        self.assertIn("report/certificate", release["summary"])


if __name__ == "__main__":
    unittest.main()
