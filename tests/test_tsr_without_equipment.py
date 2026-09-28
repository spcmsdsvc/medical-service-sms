"""Focused coverage for Francis-only TSRs on client schedules without equipment."""

import json
import os
import pathlib
import tempfile
import types
import unittest
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_tsr_without_equipment_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB_PATH))
os.environ.setdefault("SECRET_KEY", "tsr-without-equipment-tests")

import app as app_module  # noqa: E402


class TsrWithoutEquipmentSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        cls.timeline_source = (ROOT / "templates" / "timeline.html").read_text(encoding="utf-8")
        cls.tsr_source = (ROOT / "templates" / "offline_tsr.html").read_text(encoding="utf-8")
        cls.settings_source = (ROOT / "templates" / "settings.html").read_text(encoding="utf-8")
        cls.release_source = (ROOT / "static" / "changelog" / "releases.json").read_text(encoding="utf-8")

    def test_restricted_permission_and_authoritative_no_equipment_paths_exist(self):
        for marker in (
            "can_create_tsr_without_equipment = db.Column(db.Boolean, default=False, nullable=False)",
            "def can_create_tsr_without_equipment_for_user(user=None):",
            "can_create_tsr_without_equipment",
            "without_equipment",
            "equipment_assignment_conflict",
            "def build_tsr_filename_template_context(",
        ):
            self.assertIn(marker, self.app_source)

    def test_calendar_picker_and_settings_contracts_are_restricted(self):
        self.assertIn("timeline_can_create_tsr_without_equipment", self.app_source)
        self.assertIn("offline_tsr_can_create_tsr_without_equipment", self.app_source)
        self.assertIn("canCreateTSRForSchedule", self.timeline_source)
        self.assertIn("isScheduleEquipmentAssignable", self.tsr_source)
        self.assertIn("No equipment assigned", self.timeline_source + self.tsr_source)
        self.assertIn("can_create_tsr_without_equipment", self.settings_source)
        self.assertIn("approvalUserIsFrancis", self.settings_source)
        self.assertNotIn("Create Calibration Report", self.timeline_source.split("function canOpenCalibrationReportForSchedule", 1)[1].split("function getCalibrationReportTimelineLabel", 1)[0])

    def test_release_and_cache_are_advanced_for_this_package(self):
        self.assertIn("medical-service-pwa-offline-navigation-v210-deleted-product-tsr-history", self.app_source)
        self.assertIn("2026-09-28-francis-tsr-without-equipment", self.release_source)


class TsrWithoutEquipmentWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=True)
        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_user_approval_columns()
            app_module.ensure_genoray_item_table()
            app_module.ensure_vieworks_item_table()

            suffix = uuid.uuid4().hex[:8]
            cls.admin = app_module.User(
                username="jonamar",
                password=app_module.generate_password_hash("test-password"),
                role="superadmin",
                is_active=True,
            )
            cls.francis = app_module.User(
                username="francis",
                password=app_module.generate_password_hash("test-password"),
                role="engineer",
                is_active=True,
            )
            cls.other = app_module.User(
                username=f"other_tsr_{suffix}",
                password=app_module.generate_password_hash("test-password"),
                role="engineer",
                is_active=True,
            )
            cls.francis_profile = app_module.Engineer(
                employee_id=f"FR-{suffix}", name="Francis Engineer", initials="FE", branch="Manila"
            )
            cls.other_profile = app_module.Engineer(
                employee_id=f"OT-{suffix}", name="Other Engineer", initials="OE", branch="Manila"
            )
            cls.client = app_module.Client(name=f"No Equipment Client {suffix}", address="Test address")
            app_module.db.session.add_all([
                cls.admin, cls.francis, cls.other, cls.francis_profile, cls.other_profile, cls.client
            ])
            app_module.db.session.flush()
            cls.francis_profile.user_id = cls.francis.id
            cls.other_profile.user_id = cls.other.id
            cls.shift = app_module.Shift(
                title="Client visit without assigned equipment",
                start_time=datetime.now().replace(microsecond=0) + timedelta(days=1),
                end_time=datetime.now().replace(microsecond=0) + timedelta(days=1, hours=2),
                engineer_id=cls.francis_profile.id,
                client_id=cls.client.id,
                product_id=None,
                equipment_source="product",
                status="In Progress",
            )
            app_module.db.session.add(cls.shift)
            app_module.db.session.commit()
            cls.admin_id = cls.admin.id
            cls.francis_id = cls.francis.id
            cls.other_id = cls.other.id
            cls.francis_profile_id = cls.francis_profile.id
            cls.other_profile_id = cls.other_profile.id
            cls.client_id = cls.client.id
            cls.shift_id = cls.shift.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            for submission in app_module.OnlineTsrSubmission.query.filter_by(shift_id=cls.shift_id).all():
                app_module.db.session.delete(submission)
            shift = app_module.db.session.get(app_module.Shift, cls.shift_id)
            if shift:
                app_module.db.session.delete(shift)
            for model, row_id in (
                (app_module.Client, cls.client_id),
                (app_module.Engineer, cls.francis_profile_id),
                (app_module.Engineer, cls.other_profile_id),
                (app_module.User, cls.francis_id),
                (app_module.User, cls.other_id),
                (app_module.User, cls.admin_id),
            ):
                row = app_module.db.session.get(model, row_id)
                if row:
                    app_module.db.session.delete(row)
            app_module.db.session.commit()
            app_module.db.session.remove()

    @classmethod
    def _client_for(cls, user_id):
        client = cls.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
        return client

    def setUp(self):
        with self.app.app_context():
            francis = app_module.db.session.get(app_module.User, self.francis_id)
            other = app_module.db.session.get(app_module.User, self.other_id)
            francis.can_create_tsr_without_equipment = False
            other.can_create_tsr_without_equipment = False
            app_module.db.session.commit()

    def test_default_off_and_effective_permission_is_francis_only(self):
        with self.app.app_context():
            francis = app_module.db.session.get(app_module.User, self.francis_id)
            other = app_module.db.session.get(app_module.User, self.other_id)
            self.assertFalse(getattr(francis, "can_create_tsr_without_equipment", False))
            self.assertFalse(app_module.can_create_tsr_without_equipment_for_user(francis))

            francis.can_create_tsr_without_equipment = True
            other.can_create_tsr_without_equipment = True
            self.assertTrue(app_module.can_create_tsr_without_equipment_for_user(francis))
            self.assertFalse(app_module.can_create_tsr_without_equipment_for_user(other))

            francis.is_active = False
            self.assertFalse(app_module.can_create_tsr_without_equipment_for_user(francis))
            francis.is_active = True
            francis.role = "superadmin"
            self.assertFalse(app_module.can_create_tsr_without_equipment_for_user(francis))
            francis.role = "engineer"

    def test_settings_grant_audits_only_francis_and_unrelated_save_round_trips(self):
        admin_client = self._client_for(self.admin_id)
        granted = admin_client.post(
            "/settings/update-approval-user",
            json={
                "user_id": self.francis_id,
                "can_create_tsr_without_equipment": True,
                "is_active": True,
            },
        )
        self.assertEqual(granted.status_code, 200, granted.get_data(as_text=True))
        self.assertTrue(granted.get_json()["user"]["can_create_tsr_without_equipment"])

        unrelated = admin_client.post(
            "/settings/update-approval-user",
            json={
                "user_id": self.francis_id,
                "reports_admin_access": True,
                "is_active": True,
            },
        )
        self.assertEqual(unrelated.status_code, 200, unrelated.get_data(as_text=True))
        self.assertTrue(unrelated.get_json()["user"]["can_create_tsr_without_equipment"])

        other_grant = admin_client.post(
            "/settings/update-approval-user",
            json={
                "user_id": self.other_id,
                "can_create_tsr_without_equipment": True,
                "is_active": True,
            },
        )
        self.assertEqual(other_grant.status_code, 400, other_grant.get_data(as_text=True))

        with self.app.app_context():
            francis = app_module.db.session.get(app_module.User, self.francis_id)
            other = app_module.db.session.get(app_module.User, self.other_id)
            self.assertTrue(francis.can_create_tsr_without_equipment)
            self.assertFalse(other.can_create_tsr_without_equipment)
            audit = (
                app_module.ActivityLog.query
                .filter(app_module.ActivityLog.action.ilike("%can_create_tsr_without_equipment%"))
                .order_by(app_module.ActivityLog.id.desc())
                .first()
            )
            self.assertIsNotNone(audit)
            self.assertIn("False -> True", audit.action)

    def test_no_equipment_authorization_clears_payload_and_never_creates_inventory(self):
        from flask_login import login_user

        with self.app.test_request_context():
            francis = app_module.db.session.get(app_module.User, self.francis_id)
            francis.can_create_tsr_without_equipment = True
            app_module.db.session.commit()
            login_user(francis)
            shift = app_module.db.session.get(app_module.Shift, self.shift_id)
            before_products = app_module.Product.query.count()
            payload = {
                "tsr-equipment-model": "",
                "tsr-serial-no": "",
                "selectedSchedule": {
                    "id": shift.id,
                    "client_id": shift.client_id,
                    "product_id": "",
                    "product_name": "",
                    "equipment_source": "product",
                },
            }
            result = app_module.ensure_product_from_tsr_payload(shift, payload)
            self.assertEqual(result["status"], "without_equipment")
            self.assertEqual(payload["tsr-equipment-model"], "")
            self.assertEqual(payload["tsr-serial-no"], "")
            self.assertEqual(payload["selectedSchedule"]["product_id"], "")
            self.assertEqual(payload["selectedSchedule"]["product_name"], "")
            self.assertEqual(app_module.Product.query.count(), before_products)
            self.assertNotIn("Equipment / Model", app_module.get_online_tsr_missing_core_details(
                shift,
                {"tsr-service-category": "Repair", "tsr-actions-taken": "Inspected"},
            ))

    def test_forged_equipment_and_other_engineer_remain_blocked(self):
        from flask_login import login_user

        with self.app.test_request_context():
            other = app_module.db.session.get(app_module.User, self.other_id)
            other.can_create_tsr_without_equipment = True
            app_module.db.session.commit()
            login_user(other)
            shift = app_module.db.session.get(app_module.Shift, self.shift_id)
            forged = {
                "tsr-equipment-model": "Forged model",
                "tsr-serial-no": "Forged serial",
                "selectedSchedule": {"id": shift.id, "client_id": shift.client_id},
            }
            result = app_module.ensure_product_from_tsr_payload(shift, forged)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["reason"], "missing_equipment_assignment")

        with self.app.app_context():
            shift = app_module.db.session.get(app_module.Shift, self.shift_id)
            shift.product_id = "UNKNOWN-SERIAL"
            shift.equipment_source = "product"
            app_module.db.session.commit()
            from flask_login import login_user
            with self.app.test_request_context():
                francis = app_module.db.session.get(app_module.User, self.francis_id)
                francis.can_create_tsr_without_equipment = True
                app_module.db.session.commit()
                login_user(francis)
                result = app_module.ensure_product_from_tsr_payload(shift, {
                    "tsr-equipment-model": "",
                    "tsr-serial-no": "",
                    "selectedSchedule": {"id": shift.id, "client_id": shift.client_id},
                })
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(result["reason"], "equipment_not_found")
            shift.product_id = None
            app_module.db.session.commit()

    def test_initial_and_revision_routes_store_blank_equipment(self):
        from flask_login import login_user

        with self.app.app_context():
            francis = app_module.db.session.get(app_module.User, self.francis_id)
            francis.can_create_tsr_without_equipment = True
            app_module.db.session.commit()

        payload = {
            "schedule_id": self.shift_id,
            "selectedScheduleId": self.shift_id,
            "selectedSchedule": {
                "id": self.shift_id,
                "client_id": self.client_id,
                "product_id": "",
                "product_name": "",
                "equipment_source": "product",
            },
            "tsr-customer-name": "No Equipment Client",
            "tsr-service-category": "Repair",
            "tsr-actions-taken": "Inspected and documented",
            "tsr-serviced-by": "Francis Engineer",
            "_tsr_form_version": "vector-pdf-v2",
            "signatures": {
                "serviced": "data:image/png;base64,engineer",
                "acknowledged": "data:image/png;base64,client",
            },
            "submission_token": f"francis-no-equipment-{uuid.uuid4().hex}",
        }
        attachment = types.SimpleNamespace(id=9001, filename="test-tsr.pdf", original_filename="test-tsr.pdf")
        with patch.object(app_module, "generate_online_tsr_submission_pdf", return_value="test-tsr.pdf"), \
                patch.object(app_module, "attach_online_tsr_pdf_to_shift", return_value=attachment), \
                patch.object(app_module, "attach_uploaded_online_tsr_extra_files_to_shift", return_value=[]), \
                patch.object(app_module, "save_tsr_payload_contact_to_medical_center", return_value=[]), \
                patch.object(app_module, "auto_capture_tsr_client_contact_from_payload", return_value=[]), \
                patch.object(app_module, "complete_schedules_for_online_tsr", return_value=[]), \
                patch.object(app_module, "consume_online_tsr_number_reservation"), \
                patch.object(app_module, "reserve_online_tsr_number", return_value=types.SimpleNamespace(
                    reservation_token="reservation-one", tsr_number="20260929-01-FE"
                )):
            client = self._client_for(self.francis_id)
            response = client.post("/save_offline_tsr_online", json=payload)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        submission_id = response.get_json()["submission_id"]

        with self.app.app_context():
            submission = app_module.db.session.get(app_module.OnlineTsrSubmission, submission_id)
            self.assertEqual(submission.product_name, "")
            self.assertEqual(submission.serial_number, "")
            stored_payload = json.loads(submission.payload_json)
            self.assertEqual(stored_payload.get("tsr-equipment-model"), "")
            self.assertEqual(stored_payload.get("tsr-serial-no"), "")
            self.assertEqual(stored_payload["selectedSchedule"].get("product_id"), "")
            self.assertEqual(app_module.Product.query.count(), 0)

        revision_payload = dict(payload)
        revision_payload["submission_token"] = f"francis-no-equipment-revision-{uuid.uuid4().hex}"
        revision_payload["revision_reason"] = "Corrected service notes"
        revision_attachment = types.SimpleNamespace(id=9002, filename="test-tsr-revision.pdf", original_filename="test-tsr-revision.pdf")
        with patch.object(app_module, "generate_online_tsr_submission_pdf", return_value="test-tsr-revision.pdf"), \
                patch.object(app_module, "attach_online_tsr_pdf_to_shift", return_value=revision_attachment), \
                patch.object(app_module, "attach_uploaded_online_tsr_extra_files_to_shift", return_value=[]), \
                patch.object(app_module, "save_tsr_payload_contact_to_medical_center", return_value=[]), \
                patch.object(app_module, "auto_capture_tsr_client_contact_from_payload", return_value=[]), \
                patch.object(app_module, "complete_linked_schedules_for_online_tsr", return_value=[]):
            client = self._client_for(self.francis_id)
            revised = client.post(f"/revise_online_tsr_submission/{submission_id}", json=revision_payload)
        self.assertEqual(revised.status_code, 200, revised.get_data(as_text=True))
        revision_id = revised.get_json()["submission_id"]
        with self.app.app_context():
            revision = app_module.db.session.get(app_module.OnlineTsrSubmission, revision_id)
            self.assertEqual(revision.product_name, "")
            self.assertEqual(revision.serial_number, "")
            self.assertEqual(json.loads(revision.payload_json).get("tsr-serial-no"), "")


if __name__ == "__main__":
    unittest.main()
