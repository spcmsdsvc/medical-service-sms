"""Focused coverage for retained Calibration Report DOCX to PDF conversion."""

import io
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
TEST_DB = pathlib.Path(tempfile.gettempdir()) / f"medical_service_calibration_report_pdf_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB))
os.environ.setdefault("SECRET_KEY", "calibration-report-pdf-test-only")

import app as app_module  # noqa: E402


DOCX_TEMPLATE = ROOT / "static" / "templates" / "calibration-report" / "calibration-report-template.docx"
PDF_FIXTURE = ROOT / "static" / "templates" / "calibration-certificate" / "calibration-certificate-runtime-v2.pdf"


class CalibrationReportPdfTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.db = app_module.db
        cls.docx_bytes = DOCX_TEMPLATE.read_bytes()
        cls.pdf_bytes = PDF_FIXTURE.read_bytes()

    def setUp(self):
        self.original_upload_folder = self.app.config.get("UPLOAD_FOLDER")
        self.storage = tempfile.TemporaryDirectory(prefix="calibration_report_pdf_storage_")
        self.app.config["UPLOAD_FOLDER"] = self.storage.name
        with self.app.app_context():
            self.db.create_all()

    def tearDown(self):
        with self.app.app_context():
            self.db.session.remove()
        self.app.config["UPLOAD_FOLDER"] = self.original_upload_folder
        self.storage.cleanup()

    def _create_source_fixture(self, suffix=None):
        suffix = suffix or uuid.uuid4().hex[:10]
        with self.app.app_context():
            engineer = app_module.Engineer(
                employee_id=f"PDF-ENGINEER-{suffix}",
                name="PDF Test Engineer",
                initials="PTE",
            )
            self.db.session.add(engineer)
            self.db.session.flush()
            shift = app_module.Shift(
                title="Calibration PDF Test",
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(hours=1),
                engineer_id=engineer.id,
                status="Completed",
            )
            self.db.session.add(shift)
            self.db.session.flush()
            disk_name = f"shift_{shift.id}_{suffix}_calibration_report.docx"
            source_file = app_module.ShiftFile(
                shift_id=shift.id,
                filename=disk_name,
                original_filename=f"Calibration Report {suffix}.docx",
                upload_token=f"calibration-report-source-{suffix}",
            )
            self.db.session.add(source_file)
            self.db.session.flush()
            submission = app_module.OnlineTsrSubmission(
                shift_id=shift.id,
                tsr_number=f"TSR-PDF-{suffix}",
                status="completed",
                submission_token=f"tsr-pdf-{suffix}",
                payload_json=json.dumps({
                    "_generated_calibration_report": {
                        "source": "generated_calibration_report",
                        "file_id": source_file.id,
                        "filename": source_file.original_filename,
                    },
                    "calibration_report": {
                        "generated": {
                            "attachment_id": source_file.upload_token,
                            "filename": source_file.original_filename,
                        }
                    },
                }),
                revision_no=1,
                is_latest=True,
            )
            self.db.session.add(submission)
            self.db.session.flush()
            source_file.online_tsr_submission_id = submission.id
            self.db.session.commit()
            pathlib.Path(self.storage.name, disk_name).write_bytes(self.docx_bytes)
            return source_file.id, submission.id, disk_name

    def test_docx_and_pdf_validation_happens_before_conversion(self):
        self.assertTrue(app_module._calibration_report_pdf_bytes_are_valid(self.pdf_bytes))
        self.assertFalse(app_module._calibration_report_pdf_bytes_are_valid(b"not a pdf"))
        with self.assertRaisesRegex(ValueError, "not a readable DOCX"):
            app_module._validate_calibration_report_docx_bytes(b"not a docx")

        with patch.object(app_module.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "not a readable DOCX"):
                app_module.convert_calibration_report_docx_bytes(b"not a docx")
            run.assert_not_called()

    def test_conversion_uses_isolated_headless_writer_and_validates_output(self):
        def fake_run(command, **kwargs):
            outdir = pathlib.Path(command[command.index("--outdir") + 1])
            source_path = pathlib.Path(command[-1])
            (outdir / f"{source_path.stem}.pdf").write_bytes(self.pdf_bytes)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch.dict(os.environ, {"LIBREOFFICE_BIN": ""}, clear=False), \
                patch.object(app_module.shutil, "which", side_effect=lambda name: "soffice" if name == "soffice" else None), \
                patch.object(app_module.subprocess, "run", side_effect=fake_run) as run:
            converted = app_module.convert_calibration_report_docx_bytes(
                self.docx_bytes,
                "Calibration Report sample.docx",
            )

        self.assertEqual(converted, self.pdf_bytes)
        command = run.call_args.args[0]
        self.assertIn("--headless", command)
        self.assertIn("--convert-to", command)
        self.assertIn("pdf", command)
        self.assertIn("--outdir", command)
        self.assertTrue(any(str(item).startswith("-env:UserInstallation=file:") for item in command))
        self.assertEqual(run.call_args.kwargs["timeout"], app_module.CALIBRATION_REPORT_CONVERTER_TIMEOUT_SECONDS)

    def test_stored_conversion_is_idempotent_and_keeps_source_bytes_private(self):
        source_id, submission_id, disk_name = self._create_source_fixture()
        with self.app.app_context():
            with patch.object(app_module, "convert_calibration_report_docx_bytes", return_value=self.pdf_bytes) as converter:
                first = app_module.convert_calibration_report_source(source_id)
                second = app_module.convert_calibration_report_source(source_id)

            source_file = self.db.session.get(app_module.ShiftFile, source_id)
            job = self.db.session.get(app_module.CalibrationReportConversion, first.id)
            pdf_file = self.db.session.get(app_module.ShiftFile, job.pdf_shift_file_id)
            submission = self.db.session.get(app_module.OnlineTsrSubmission, submission_id)
            marker = json.loads(submission.payload_json)["_generated_calibration_report"]
            self.assertEqual(first.id, second.id)
            self.assertEqual(job.state, "ready")
            self.assertEqual(job.attempts, 1)
            self.assertEqual(converter.call_count, 1)
            self.assertEqual(pdf_file.original_filename, f"Calibration_Report_{disk_name.split('_')[2]}.pdf")
            self.assertEqual(pathlib.Path(self.storage.name, disk_name).read_bytes(), self.docx_bytes)
            self.assertTrue(app_module.calibration_report_source_file_is_private(source_file))
            self.assertEqual(marker["pdf_state"], "ready")
            self.assertEqual(marker["pdf_file_id"], pdf_file.id)
            self.assertEqual(marker["pdf_filename"], pdf_file.original_filename)
            self.assertEqual(
                app_module.get_user_visible_shift_file_records(source_file.shift),
                [],
            )

    def test_conversion_failure_persists_retry_state_without_removing_source(self):
        source_id, submission_id, disk_name = self._create_source_fixture()
        with self.app.app_context():
            with patch.object(
                app_module,
                "convert_calibration_report_docx_bytes",
                side_effect=RuntimeError("writer unavailable"),
            ):
                job = app_module.convert_calibration_report_source(source_id)

            submission = self.db.session.get(app_module.OnlineTsrSubmission, submission_id)
            source_file = self.db.session.get(app_module.ShiftFile, source_id)
            marker = json.loads(submission.payload_json)["_generated_calibration_report"]
            self.assertEqual(job.state, "failed")
            self.assertEqual(job.attempts, 1)
            self.assertIsNotNone(job.next_retry_at)
            self.assertIn("writer unavailable", job.last_error)
            self.assertEqual(marker["pdf_state"], "failed")
            self.assertIn("writer unavailable", marker["pdf_error"])
            self.assertTrue(pathlib.Path(self.storage.name, disk_name).is_file())
            self.assertEqual(
                app_module.get_user_visible_shift_file_records(source_file.shift),
                [],
            )

    def test_email_gate_reports_pending_and_failed_latest_pdf_states(self):
        shift = SimpleNamespace(id=1)
        with self.app.app_context():
            with patch.object(app_module, "get_linked_schedule_file_shifts", return_value=[shift]), \
                    patch.object(app_module, "get_linked_schedule_calibration_report_file_state", return_value={
                        "pending_latest_source_ids": {11},
                        "failed_latest_source_ids": set(),
                    }):
                self.assertIn("still being prepared", app_module.get_calibration_report_email_block(shift))

            with patch.object(app_module, "get_linked_schedule_file_shifts", return_value=[shift]), \
                    patch.object(app_module, "get_linked_schedule_calibration_report_file_state", return_value={
                        "pending_latest_source_ids": set(),
                        "failed_latest_source_ids": {11},
                    }):
                self.assertIn("conversion failed", app_module.get_calibration_report_email_block(shift))


if __name__ == "__main__":
    unittest.main()
