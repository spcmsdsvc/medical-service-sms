"""Schedule edits must never orphan TSR submissions, Calibration Reports or certificate approvals."""

import json
import os
import pathlib
import tempfile
import unittest
import uuid
from datetime import date, datetime, timedelta
from unittest.mock import patch

TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_schedule_links_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB_PATH))
os.environ.setdefault("SECRET_KEY", "schedule-links-tests")

import app as app_module  # noqa: E402

SERVICE_DATE = date(2026, 4, 14)


class ScheduleRebuildLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=True)
        with cls.app.app_context():
            app_module.db.create_all()
            suffix = uuid.uuid4().hex[:8]
            superadmin = app_module.User(username=f"links_admin_{suffix}", password="test", role="superadmin", is_active=True)
            first = app_module.Engineer(employee_id=f"LA-{suffix}", name="Links Engineer A", initials=f"LA{suffix[:3]}")
            second = app_module.Engineer(employee_id=f"LB-{suffix}", name="Links Engineer B", initials=f"LB{suffix[:3]}")
            client = app_module.Client(name=f"Links Client {suffix}")
            app_module.db.session.add_all([superadmin, first, second, client])
            app_module.db.session.commit()
            cls.superadmin_id = superadmin.id
            cls.engineer_ids = [first.id, second.id]
            cls.client_id = client.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            cls.purge()
            for model, identity in (
                (app_module.User, cls.superadmin_id),
                (app_module.Engineer, cls.engineer_ids[0]),
                (app_module.Engineer, cls.engineer_ids[1]),
                (app_module.Client, cls.client_id),
            ):
                row = app_module.db.session.get(model, identity)
                if row:
                    app_module.db.session.delete(row)
            app_module.db.session.commit()
            app_module.db.session.remove()

    @classmethod
    def purge(cls):
        """Bulk deletes bypass the flush guard, as test cleanup must."""
        session = app_module.db.session
        shift_ids = [row.id for row in app_module.Shift.query.filter_by(client_id=cls.client_id).all()]
        file_ids = [row.id for row in app_module.ShiftFile.query.filter(app_module.ShiftFile.shift_id.in_(shift_ids or [0])).all()]
        app_module.CalibrationCertificateApproval.query.filter(
            app_module.CalibrationCertificateApproval.shift_id.in_(shift_ids or [0])
        ).delete(synchronize_session=False)
        app_module.CalibrationReportConversion.query.filter(
            app_module.CalibrationReportConversion.source_shift_file_id.in_(file_ids or [0])
        ).delete(synchronize_session=False)
        app_module.OnlineTsrSubmission.query.filter(
            app_module.OnlineTsrSubmission.shift_id.in_(shift_ids or [0])
        ).delete(synchronize_session=False)
        app_module.ShiftFile.query.filter(app_module.ShiftFile.id.in_(file_ids or [0])).delete(synchronize_session=False)
        app_module.ShiftEngineer.query.filter(app_module.ShiftEngineer.shift_id.in_(shift_ids or [0])).delete(synchronize_session=False)
        app_module.Shift.query.filter(app_module.Shift.id.in_(shift_ids or [0])).delete(synchronize_session=False)
        session.commit()

    def setUp(self):
        with self.app.app_context():
            self.purge()

    def client_for(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(self.superadmin_id)
            session["_fresh"] = True
        return client

    def make_chain(self, dates, engineer_ids=None):
        engineer_ids = engineer_ids or self.engineer_ids[:1]
        group_id = str(uuid.uuid4())
        ids = []
        for service_date in dates:
            start = datetime.combine(service_date, datetime.min.time()).replace(hour=9)
            shift = app_module.Shift(
                title="Preventive Maintenance (PM)", start_time=start, end_time=start + timedelta(hours=2),
                engineer_id=engineer_ids[0], client_id=self.client_id, status="Completed", group_id=group_id,
            )
            app_module.db.session.add(shift)
            app_module.db.session.flush()
            for engineer_id in engineer_ids:
                app_module.db.session.add(app_module.ShiftEngineer(shift_id=shift.id, engineer_id=engineer_id))
            ids.append(shift.id)
        app_module.db.session.commit()
        return ids

    def attach_tsr_with_report(self, shift_id):
        """TSR PDF, generated report DOCX + PDF, ready conversion and a Pending approval."""
        session = app_module.db.session
        submission = app_module.OnlineTsrSubmission(
            shift_id=shift_id, tsr_number=f"TSR-{uuid.uuid4().hex[:6]}", status="completed", payload_json="{}",
        )
        session.add(submission)
        session.flush()
        tsr = app_module.ShiftFile(shift_id=shift_id, filename=f"TSR_links_{submission.id}.pdf",
                                   original_filename=f"TSR_links_{submission.id}.pdf", online_tsr_submission_id=submission.id)
        docx = app_module.ShiftFile(shift_id=shift_id, filename=f"CALIBRATION_REPORT_{submission.id}.docx",
                                    original_filename=f"CALIBRATION_REPORT_{submission.id}.docx",
                                    upload_token=f"calibration-report-{uuid.uuid4().hex[:8]}",
                                    online_tsr_submission_id=submission.id)
        pdf = app_module.ShiftFile(shift_id=shift_id, filename=f"CALIBRATION_REPORT_{submission.id}.pdf",
                                   original_filename=f"CALIBRATION_REPORT_{submission.id}.pdf",
                                   online_tsr_submission_id=submission.id)
        session.add_all([tsr, docx, pdf])
        session.flush()
        submission.payload_json = json.dumps({
            "_attached_file_id": tsr.id,
            "_completed_shift_ids": [shift_id],
            "_generated_calibration_report": {"source": "generated_calibration_report", "file_id": docx.id, "pdf_file_id": pdf.id},
        })
        session.add(app_module.CalibrationReportConversion(
            source_shift_file_id=docx.id, pdf_shift_file_id=pdf.id, state="ready", attempts=1,
        ))
        approval = app_module.CalibrationCertificateApproval(
            shift_id=shift_id, online_tsr_submission_id=submission.id, status="Pending",
            certificate_number=f"CERT-{submission.id}", template_sha256="0" * 64, unsigned_artifact_path="unused.pdf",
        )
        session.add(approval)
        session.commit()
        return {"submission": submission.id, "tsr": tsr.id, "docx": docx.id, "pdf": pdf.id, "approval": approval.id}

    def edit(self, shift_id, *, engineers, start, end):
        payload = {
            "title": "Preventive Maintenance (PM)", "client_id": self.client_id, "product_id": None,
            "engineers": engineers, "engineer_id": engineers[0], "status": "Completed",
            "start_date": start.isoformat(), "end_date": end.isoformat(),
            "start_time": "09:00", "end_time": "11:00", "edit_scope": "entire_schedule", "include_weekends": True,
        }
        with patch.object(app_module, "get_shift_payload", return_value=payload), \
             patch.object(app_module, "send_schedule_event_notification_async"):
            return self.client_for().post(f"/update_shift/{shift_id}")

    def assert_links_follow(self, ids, expected_date):
        app_module.db.session.expire_all()
        submission = app_module.db.session.get(app_module.OnlineTsrSubmission, ids["submission"])
        new_shift = app_module.db.session.get(app_module.Shift, submission.shift_id)
        self.assertIsNotNone(new_shift, "the TSR submission points at a deleted schedule")
        self.assertEqual(new_shift.start_time.date(), expected_date)
        approval = app_module.db.session.get(app_module.CalibrationCertificateApproval, ids["approval"])
        self.assertEqual(approval.shift_id, new_shift.id)
        for key in ("tsr", "docx", "pdf"):
            file_rec = app_module.db.session.get(app_module.ShiftFile, ids[key])
            self.assertIsNotNone(file_rec, f"{key} file row was deleted")
            self.assertEqual(file_rec.shift_id, new_shift.id)
            self.assertEqual(file_rec.online_tsr_submission_id, ids["submission"])
        self.assertEqual(app_module.ShiftFile.query.filter_by(shift_id=new_shift.id).count(), 3)
        payload = json.loads(submission.payload_json)
        self.assertEqual(payload["_completed_shift_ids"], [new_shift.id])
        report_pdf = app_module.calibration_certificate_generated_report_file(approval)
        self.assertIsNotNone(report_pdf, "Calibration Center would show 'Calibration Report PDF is unavailable.'")
        self.assertEqual(report_pdf.id, ids["pdf"])

    def test_adding_an_engineer_keeps_tsr_report_and_approval_linked(self):
        with self.app.app_context():
            [shift_id] = self.make_chain([SERVICE_DATE])
            ids = self.attach_tsr_with_report(shift_id)
        response = self.edit(shift_id, engineers=self.engineer_ids, start=SERVICE_DATE, end=SERVICE_DATE)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        with self.app.app_context():
            self.assert_links_follow(ids, SERVICE_DATE)

    def test_extending_a_linked_chain_moves_links_to_the_same_day(self):
        day_two = SERVICE_DATE + timedelta(days=1)
        with self.app.app_context():
            first_id, second_id = self.make_chain([SERVICE_DATE, day_two])
            ids = self.attach_tsr_with_report(second_id)
        response = self.edit(first_id, engineers=self.engineer_ids[:1], start=SERVICE_DATE, end=SERVICE_DATE + timedelta(days=2))
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        with self.app.app_context():
            self.assert_links_follow(ids, day_two)

    def test_deleting_a_schedule_with_a_tsr_is_refused(self):
        with self.app.app_context():
            [shift_id] = self.make_chain([SERVICE_DATE])
            ids = self.attach_tsr_with_report(shift_id)
        client = self.client_for()
        body = {"shift_id": shift_id, "delete_mode": "linked_chain"}
        for response in (
            client.post("/preview_delete_shifts", json=body),
            client.post("/delete_shifts_previewed", json=body),
            client.delete(f"/delete_shift/{shift_id}"),
        ):
            self.assertEqual(response.status_code, 409, response.get_data(as_text=True))
            self.assertEqual(response.get_json()["message"], app_module.SCHEDULE_LINKED_WORK_MESSAGE)
        with self.app.app_context():
            self.assertIsNotNone(app_module.db.session.get(app_module.Shift, shift_id))
            self.assertIsNotNone(app_module.db.session.get(app_module.ShiftFile, ids["docx"]))

    def test_deleting_a_schedule_without_linked_work_still_works(self):
        with self.app.app_context():
            [shift_id] = self.make_chain([SERVICE_DATE])
        with patch.object(app_module, "send_schedule_deleted_notification_async"):
            response = self.client_for().post("/delete_shifts_previewed", json={"shift_id": shift_id, "delete_mode": "linked_chain"})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        with self.app.app_context():
            self.assertIsNone(app_module.db.session.get(app_module.Shift, shift_id))

    def test_any_session_delete_of_a_linked_schedule_raises(self):
        with self.app.app_context():
            [shift_id] = self.make_chain([SERVICE_DATE])
            self.attach_tsr_with_report(shift_id)
            app_module.db.session.delete(app_module.db.session.get(app_module.Shift, shift_id))
            with self.assertRaises(app_module.ScheduleHasLinkedWorkError):
                app_module.db.session.flush()
            app_module.db.session.rollback()
            self.assertIsNotNone(app_module.db.session.get(app_module.Shift, shift_id))


if __name__ == "__main__":
    unittest.main()
