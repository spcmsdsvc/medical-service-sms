"""Focused coverage for standalone equipment in schedule/TSR/calibration workflows."""

import os
import pathlib
import tempfile
import unittest
import uuid
from datetime import timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_operational_equipment_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB_PATH))
os.environ.setdefault("SECRET_KEY", "operational-equipment-tests")

import app as app_module  # noqa: E402


class OperationalEquipmentWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=True)
        suffix = uuid.uuid4().hex[:8].upper()
        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_genoray_item_table()
            app_module.ensure_vieworks_item_table()

            cls.admin = app_module.User(
                username=f"operational_admin_{suffix.lower()}", password="test",
                role="admin", is_active=True,
            )
            cls.engineer_user = app_module.User(
                username=f"operational_engineer_{suffix.lower()}", password="test",
                role="engineer", is_active=True,
            )
            cls.engineer = app_module.Engineer(
                user_id=None, employee_id=f"OP-{suffix}", name="Operational Engineer",
                initials="OP", branch="Manila",
            )
            cls.client = app_module.Client(name=f"Operational Client {suffix}", address="Test address")
            cls.other_client = app_module.Client(name=f"Other Client {suffix}")
            app_module.db.session.add_all([cls.admin, cls.engineer_user, cls.engineer, cls.client, cls.other_client])
            app_module.db.session.flush()
            cls.engineer.user_id = cls.engineer_user.id

            cls.product_serial = f"PRODUCT-{suffix}"
            cls.product_name = "Product Equipment"
            cls.product_bsid = f"P-{suffix}"
            cls.genoray_serial = f"GENORAY-{suffix}"
            cls.genoray_name = "Genoray Equipment"
            cls.genoray_bsid = f"G-{suffix}"
            cls.vieworks_serial = f"VIEWORKS-{suffix}"
            cls.vieworks_name = "Vieworks Equipment"
            cls.vieworks_bsid = f"V-{suffix}"
            cls.product = app_module.Product(
                serial_number=cls.product_serial, name=cls.product_name, client_id=cls.client.id,
                bsid=cls.product_bsid,
            )
            cls.genoray = app_module.GenorayItem(
                serial_number=cls.genoray_serial, name=cls.genoray_name, client_id=cls.client.id,
                bsid=cls.genoray_bsid,
            )
            cls.vieworks = app_module.VieworksItem(
                serial_number=cls.vieworks_serial, name=cls.vieworks_name, client_id=cls.client.id,
                bsid=cls.vieworks_bsid,
            )
            app_module.db.session.add_all([cls.product, cls.genoray, cls.vieworks])
            app_module.db.session.commit()

            cls.admin_id = cls.admin.id
            cls.engineer_user_id = cls.engineer_user.id
            cls.engineer_id = cls.engineer.id
            cls.client_id = cls.client.id
            cls.other_client_id = cls.other_client.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            for shift in app_module.Shift.query.filter(
                app_module.Shift.client_id.in_([cls.client_id, cls.other_client_id])
            ).all():
                app_module.ShiftEngineer.query.filter_by(shift_id=shift.id).delete(synchronize_session=False)
                app_module.db.session.delete(shift)
            for model, identity in (
                (app_module.Product, cls.product_serial),
                (app_module.GenorayItem, cls.genoray_serial),
                (app_module.VieworksItem, cls.vieworks_serial),
                (app_module.Client, cls.client_id),
                (app_module.Client, cls.other_client_id),
                (app_module.Engineer, cls.engineer_id),
                (app_module.User, cls.admin_id),
                (app_module.User, cls.engineer_user_id),
            ):
                row = app_module.db.session.get(model, identity)
                if row:
                    app_module.db.session.delete(row)
            app_module.db.session.commit()
            app_module.db.session.remove()

    def client_for(self, user_id):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
        return client

    def schedule_payload(self, serial, source):
        start_date = (app_module.get_manila_today() + timedelta(days=2)).isoformat()
        return {
            "title": "Operational equipment service",
            "start_date": start_date,
            "end_date": start_date,
            "start_time": "09:00",
            "end_time": "11:00",
            "engineer_id": str(self.engineer_id),
            "client_id": str(self.client_id),
            "product_id": serial,
            "equipment_source": source,
            "status": "Planned",
        }

    def test_operational_endpoint_includes_all_equipment_sources(self):
        client = self.client_for(self.engineer_user_id)
        response = client.get("/get_products?operational=1")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        rows = {(row.get("equipment_source"), row.get("serial_number")): row for row in response.get_json()}
        self.assertIn(("product", self.product_serial), rows)
        self.assertIn(("genoray", self.genoray_serial), rows)
        self.assertIn(("vieworks", self.vieworks_serial), rows)
        self.assertEqual(rows[("genoray", self.genoray_serial)]["bsid"], self.genoray_bsid)
        self.assertEqual(rows[("vieworks", self.vieworks_serial)]["client_id"], self.client_id)

        legacy_response = client.get("/get_products")
        self.assertEqual(legacy_response.status_code, 200, legacy_response.get_data(as_text=True))
        legacy_serials = {row.get("serial_number") for row in legacy_response.get_json()}
        self.assertIn(self.product_serial, legacy_serials)
        self.assertNotIn(self.genoray_serial, legacy_serials)
        self.assertNotIn(self.vieworks_serial, legacy_serials)

    def test_schedule_create_persists_source_and_tsr_options_resolve_standalone_item(self):
        client = self.client_for(self.engineer_user_id)
        response = client.post("/add_shift", data=self.schedule_payload(self.genoray_serial, "genoray"))
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

        with self.app.app_context():
            shift = app_module.Shift.query.filter_by(product_id=self.genoray_serial).order_by(app_module.Shift.id.desc()).first()
            self.assertIsNotNone(shift)
            self.assertEqual(shift.equipment_source, "genoray")
            shift_id = shift.id

        details = client.get(f"/get_shift_details/{shift_id}")
        self.assertEqual(details.status_code, 200, details.get_data(as_text=True))
        detail_row = details.get_json()["shift"]
        self.assertEqual(detail_row["product_name"], self.genoray_name)
        self.assertEqual(detail_row["equipment_source"], "genoray")

        engineer_client = self.client_for(self.engineer_user_id)
        options = engineer_client.get("/get_offline_tsr_schedule_options")
        self.assertEqual(options.status_code, 200, options.get_data(as_text=True))
        selected = next(row for row in options.get_json()["schedules"] if row["id"] == shift_id)
        self.assertEqual(selected["product_name"], self.genoray_name)
        self.assertEqual(selected["product_bsid"], self.genoray_bsid)
        self.assertEqual(selected["equipment_source"], "genoray")

    def test_schedule_rejects_wrong_client_and_unknown_equipment_source(self):
        client = self.client_for(self.engineer_user_id)

        wrong_client_payload = self.schedule_payload(self.genoray_serial, "genoray")
        wrong_client_payload["client_id"] = str(self.other_client_id)
        wrong_client_response = client.post("/add_shift", data=wrong_client_payload)
        self.assertEqual(wrong_client_response.status_code, 400)
        self.assertIn("different medical center", wrong_client_response.get_json()["message"])

        unknown_source_response = client.post(
            "/add_shift",
            data=self.schedule_payload(self.genoray_serial, "unknown"),
        )
        self.assertEqual(unknown_source_response.status_code, 400)
        self.assertIn("equipment source is invalid", unknown_source_response.get_json()["message"])

    def test_tsr_recognizes_standalone_item_without_creating_product_duplicate(self):
        with self.app.app_context():
            shift = app_module.Shift(
                title="Standalone TSR source test",
                start_time=app_module.datetime.combine(app_module.get_manila_today(), app_module.datetime.min.time()).replace(hour=8),
                end_time=app_module.datetime.combine(app_module.get_manila_today(), app_module.datetime.min.time()).replace(hour=10),
                engineer_id=self.engineer_id,
                client_id=self.client_id,
                product_id=self.vieworks_serial,
                status="Completed",
            )
            setattr(shift, "equipment_source", "vieworks")
            app_module.db.session.add(shift)
            app_module.db.session.commit()
            before_count = app_module.Product.query.filter_by(serial_number=self.vieworks_serial).count()
            result = app_module.ensure_product_from_tsr_payload(shift, {
                "tsr-equipment-model": self.vieworks_name,
                "tsr-serial-no": self.vieworks_serial,
                "selectedSchedule": {},
            })
            after_count = app_module.Product.query.filter_by(serial_number=self.vieworks_serial).count()
            self.assertEqual(result["status"], "existing")
            self.assertEqual(result["product_name"], self.vieworks_name)
            self.assertEqual(before_count, after_count)
            app_module.db.session.delete(shift)
            app_module.db.session.commit()

    def test_calibration_certificate_uses_standalone_bsid(self):
        with self.app.app_context():
            shift = app_module.Shift(
                title="Standalone calibration source test",
                start_time=app_module.datetime.combine(app_module.get_manila_today(), app_module.datetime.min.time()).replace(hour=8),
                end_time=app_module.datetime.combine(app_module.get_manila_today(), app_module.datetime.min.time()).replace(hour=10),
                engineer_id=self.engineer_id,
                client_id=self.client_id,
                product_id=self.genoray_serial,
                status="Completed",
            )
            setattr(shift, "equipment_source", "genoray")
            app_module.db.session.add(shift)
            app_module.db.session.commit()
            payload = {
                "tsr-number": "TSR-OP-1",
                "calibration_report": {
                    "machine": {
                        "model": self.genoray_name,
                        "serial_number": self.genoray_serial,
                        "modality": "X-ray",
                    },
                    "facility": {"name": "Operational Client"},
                    "calibration": {
                        "machine_calibration_date": "2026-09-22",
                        "next_calibration_date": "2027-09-22",
                    },
                    "certificate": {},
                },
            }
            values, missing, _ = app_module.calibration_certificate_values(payload, shift=shift)
            self.assertIn(self.genoray_bsid, values["Textfield"])
            self.assertNotIn("Certificate No.", missing)
            app_module.db.session.delete(shift)
            app_module.db.session.commit()


if __name__ == "__main__":
    unittest.main()
