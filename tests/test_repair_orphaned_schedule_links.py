"""The orphaned-schedule repair script re-links what a pre-fix schedule rebuild left behind."""

import io
import json
import os
import pathlib
import tempfile
import unittest
import uuid
from datetime import datetime

TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_orphan_repair_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB_PATH))
os.environ.setdefault("SECRET_KEY", "orphan-repair-tests")

import app as app_module  # noqa: E402
from scripts import repair_orphaned_schedule_links as repair  # noqa: E402


class RepairOrphanedScheduleLinksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        with cls.app.app_context():
            app_module.db.create_all()
            suffix = uuid.uuid4().hex[:8]
            client = app_module.Client(name=f"Repair Client {suffix}")
            engineer = app_module.Engineer(employee_id=f"RP-{suffix}", name="Repair Engineer", initials=f"RP{suffix[:3]}")
            app_module.db.session.add_all([client, engineer])
            app_module.db.session.commit()
            cls.client_id = client.id
            cls.engineer_id = engineer.id
            cls.client_name = client.name
            cls.db_path = app_module.db.engine.url.database

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            for model, identity in ((app_module.Engineer, cls.engineer_id), (app_module.Client, cls.client_id)):
                row = app_module.db.session.get(model, identity)
                if row:
                    app_module.db.session.delete(row)
            app_module.db.session.commit()
            app_module.db.session.remove()

    def setUp(self):
        self.created_shift_ids = []

    def tearDown(self):
        with self.app.app_context():
            session = app_module.db.session
            submission_ids = [row.id for row in app_module.OnlineTsrSubmission.query.filter_by(client_name=self.client_name)]
            app_module.CalibrationCertificateApproval.query.filter(
                app_module.CalibrationCertificateApproval.online_tsr_submission_id.in_(submission_ids or [0])
            ).delete(synchronize_session=False)
            file_ids = [row.id for row in app_module.ShiftFile.query.filter(app_module.ShiftFile.shift_id.in_(self.created_shift_ids or [0]))]
            app_module.CalibrationReportConversion.query.filter(
                app_module.CalibrationReportConversion.source_shift_file_id.in_(file_ids or [0])
            ).delete(synchronize_session=False)
            # Conversions whose source file this test deleted (SQLite reuses those file ids).
            session.execute(app_module.db.text(
                "DELETE FROM calibration_report_conversion WHERE source_shift_file_id NOT IN (SELECT id FROM shift_file)"
            ))
            app_module.OnlineTsrSubmission.query.filter(app_module.OnlineTsrSubmission.id.in_(submission_ids or [0])).delete(synchronize_session=False)
            app_module.ShiftFile.query.filter(app_module.ShiftFile.id.in_(file_ids or [0])).delete(synchronize_session=False)
            app_module.Shift.query.filter(app_module.Shift.id.in_(self.created_shift_ids or [0])).delete(synchronize_session=False)
            app_module.ActivityLog.query.filter(app_module.ActivityLog.action.like("Repaired orphaned schedule links%")).delete(synchronize_session=False)
            session.commit()
            session.remove()

    def make_shift(self):
        start = datetime(2026, 4, 14, 9)
        shift = app_module.Shift(title="PM", start_time=start, end_time=start.replace(hour=11),
                                 engineer_id=self.engineer_id, client_id=self.client_id, status="Completed")
        app_module.db.session.add(shift)
        app_module.db.session.flush()
        self.created_shift_ids.append(shift.id)
        return shift

    def orphan_like_production(self, with_rebuild=True):
        """Recreate TSR 20261014-02-JMM's state: links on a deleted schedule, filename-only copies on the rebuilt one."""
        session = app_module.db.session
        old = self.make_shift()
        token = f"calibration-report-{uuid.uuid4().hex[:8]}"
        names = {"tsr": f"TSR_repair_{token}.pdf", "docx": f"CALIBRATION_REPORT_{token}.docx", "pdf": f"CALIBRATION_REPORT_{token}.pdf"}
        submission = app_module.OnlineTsrSubmission(shift_id=old.id, tsr_number=f"T-{token[-8:]}", client_name=self.client_name,
                                                    status="completed", payload_json="{}")
        session.add(submission)
        session.flush()
        old_files = {key: app_module.ShiftFile(shift_id=old.id, filename=name, original_filename=name,
                                               online_tsr_submission_id=submission.id,
                                               upload_token=token if key == "docx" else None)
                     for key, name in names.items()}
        session.add_all(old_files.values())
        session.flush()
        submission.payload_json = json.dumps({
            "_attached_file_id": old_files["tsr"].id,
            "_attached_disk_filename": names["tsr"],
            "_completed_shift_ids": [old.id],
            "_generated_calibration_report": {
                "source": "generated_calibration_report", "file_id": old_files["docx"].id, "filename": names["docx"],
                "upload_token": token, "pdf_file_id": old_files["pdf"].id, "pdf_filename": names["pdf"], "pdf_state": "ready",
            },
            "calibration_report": {"generated": {"file_id": old_files["docx"].id, "pdf_file_id": old_files["pdf"].id}},
        })
        session.add(app_module.CalibrationReportConversion(source_shift_file_id=old_files["docx"].id,
                                                           pdf_shift_file_id=old_files["pdf"].id, state="ready", attempts=1))
        approval = app_module.CalibrationCertificateApproval(
            shift_id=old.id, online_tsr_submission_id=submission.id, status="Approved",
            certificate_number=f"CERT-{token[-8:]}", template_sha256="0" * 64, unsigned_artifact_path="unused.pdf",
        )
        session.add(approval)
        new = self.make_shift() if with_rebuild else None
        if new:
            session.add_all([app_module.ShiftFile(shift_id=new.id, filename=name, original_filename=name) for name in names.values()])
        session.commit()
        ids = {"old": old.id, "new": new.id if new else None, "submission": submission.id, "approval": approval.id}
        old_file_ids = [row.id for row in old_files.values()]
        # The pre-fix rebuild: the old row and its files are gone (bulk delete, as the cascade did).
        app_module.ShiftFile.query.filter(app_module.ShiftFile.id.in_(old_file_ids)).delete(synchronize_session=False)
        app_module.Shift.query.filter_by(id=ids["old"]).delete(synchronize_session=False)
        session.commit()
        session.remove()
        return ids

    def snapshot(self):
        with self.app.app_context():
            session = app_module.db.session
            return (
                [tuple(row) for row in session.execute(app_module.db.text("SELECT id, shift_id, payload_json FROM online_tsr_submission ORDER BY id"))],
                [tuple(row) for row in session.execute(app_module.db.text("SELECT id, shift_id, online_tsr_submission_id, upload_token FROM shift_file ORDER BY id"))],
                [tuple(row) for row in session.execute(app_module.db.text("SELECT id, shift_id FROM calibration_certificate_approval ORDER BY id"))],
            )

    def test_dry_run_reports_and_writes_nothing(self):
        with self.app.app_context():
            ids = self.orphan_like_production()
        before = self.snapshot()
        out = io.StringIO()
        plans = repair.run(self.db_path, out=out)
        self.assertEqual(before, self.snapshot())
        plan = next(item for item in plans if item.old_shift_id == ids["old"])
        self.assertEqual(plan.status, "rebuilt", out.getvalue())
        self.assertEqual(plan.new_shift_id, ids["new"])
        self.assertIn("Dry run: nothing written", out.getvalue())

    def test_apply_restores_the_calibration_report_link(self):
        with self.app.app_context():
            ids = self.orphan_like_production()
            approval = app_module.db.session.get(app_module.CalibrationCertificateApproval, ids["approval"])
            self.assertIsNone(app_module.calibration_certificate_generated_report_file(approval))
            app_module.db.session.remove()
        repair.run(self.db_path, do_apply=True, out=io.StringIO())
        with self.app.app_context():
            approval = app_module.db.session.get(app_module.CalibrationCertificateApproval, ids["approval"])
            self.assertEqual(approval.shift_id, ids["new"])
            submission = app_module.db.session.get(app_module.OnlineTsrSubmission, ids["submission"])
            self.assertEqual(submission.shift_id, ids["new"])
            payload = json.loads(submission.payload_json)
            self.assertEqual(payload["_completed_shift_ids"], [ids["new"]])
            report_pdf = app_module.calibration_certificate_generated_report_file(approval)
            self.assertIsNotNone(report_pdf, "Calibration Center would still show the report as unavailable")
            source = app_module.calibration_certificate_generated_report_source_file(approval)
            self.assertTrue(app_module.calibration_report_source_file_is_private(source))
            tsr = app_module.db.session.get(app_module.ShiftFile, payload["_attached_file_id"])
            self.assertEqual((tsr.shift_id, tsr.online_tsr_submission_id), (ids["new"], ids["submission"]))
            self.assertEqual(app_module.ActivityLog.query.filter(
                app_module.ActivityLog.action.like(f"Repaired orphaned schedule links:%#{ids['old']} to #{ids['new']}")
            ).count(), 1)
        # A second run finds nothing left to repair for this schedule.
        plans = repair.run(self.db_path, out=io.StringIO())
        self.assertFalse([plan for plan in plans if plan.old_shift_id == ids["old"]])

    def test_truly_deleted_schedule_is_left_untouched(self):
        with self.app.app_context():
            ids = self.orphan_like_production(with_rebuild=False)
        before = self.snapshot()
        plans = repair.run(self.db_path, do_apply=True, out=io.StringIO())
        self.assertEqual(next(plan for plan in plans if plan.old_shift_id == ids["old"]).status, "deleted")
        self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
