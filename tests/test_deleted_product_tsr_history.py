"""Regression coverage for retaining deleted Product identity in TSR history."""

import json
import os
import pathlib
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_deleted_product_tsr_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB_PATH))
os.environ.setdefault("SECRET_KEY", "deleted-product-tsr-tests")

import app as app_module  # noqa: E402
from tests.schema_flags import reset_schema_flags  # noqa: E402


class DeletedProductTsrHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=True)

    def setUp(self):
        self.suffix = uuid.uuid4().hex[:8].upper()
        self.username = f"deleted-product-admin-{self.suffix}"
        app_module.SUPERADMIN_USERNAMES.add(self.username.lower())

        with self.app.app_context():
            app_module.db.create_all()
            self.admin = app_module.User(
                username=self.username,
                password="test",
                role="superadmin",
                is_active=True,
                reports_admin_access=True,
            )
            self.engineer = app_module.Engineer(
                employee_id=f"DPT-{self.suffix}",
                name="Deleted Product Test Engineer",
                initials="DPT",
            )
            self.client_record = app_module.Client(
                name=f"Deleted Product Client {self.suffix}",
                address="Test address",
            )
            app_module.db.session.add_all([self.admin, self.engineer, self.client_record])
            app_module.db.session.flush()
            self.product = app_module.Product(
                serial_number=f"DPT-PRODUCT-{self.suffix}",
                name="Historical Product",
                client_id=self.client_record.id,
            )
            app_module.db.session.add(self.product)
            app_module.db.session.flush()

            base = datetime(2026, 9, 28, 8, 0)
            self.shift = app_module.Shift(
                title="Product TSR",
                start_time=base,
                end_time=base + timedelta(hours=2),
                engineer_id=self.engineer.id,
                client_id=self.client_record.id,
                product_id=self.product.serial_number,
                equipment_source="product",
                status="Completed",
            )
            self.productless_shift = app_module.Shift(
                title="Productless TSR",
                start_time=base + timedelta(days=1),
                end_time=base + timedelta(days=1, hours=2),
                engineer_id=self.engineer.id,
                client_id=self.client_record.id,
                product_id=None,
                equipment_source="product",
                status="Completed",
            )
            self.vieworks = app_module.VieworksItem(
                serial_number=self.product.serial_number,
                name="Vieworks Collision",
                client_id=self.client_record.id,
                bsid=f"VC-{self.suffix}",
            )
            self.genoray = app_module.GenorayItem(
                serial_number=f"DPT-GENORAY-{self.suffix}",
                name="Genoray Collision",
                client_id=self.client_record.id,
                bsid=f"GC-{self.suffix}",
            )
            self.vieworks_shift = app_module.Shift(
                title="Vieworks Collision TSR",
                start_time=base + timedelta(days=2),
                end_time=base + timedelta(days=2, hours=2),
                engineer_id=self.engineer.id,
                client_id=self.client_record.id,
                product_id=self.product.serial_number,
                equipment_source="vieworks",
                status="Completed",
            )
            self.genoray_shift = app_module.Shift(
                title="Genoray TSR",
                start_time=base + timedelta(days=3),
                end_time=base + timedelta(days=3, hours=2),
                engineer_id=self.engineer.id,
                client_id=self.client_record.id,
                product_id=self.genoray.serial_number,
                equipment_source="genoray",
                status="Completed",
            )
            app_module.db.session.add_all([
                self.shift,
                self.productless_shift,
                self.vieworks,
                self.genoray,
                self.vieworks_shift,
                self.genoray_shift,
            ])
            app_module.db.session.flush()
            self.file = app_module.ShiftFile(
                shift_id=self.shift.id,
                filename=f"TSR_SHIMADZU_{self.suffix}.pdf",
                original_filename=f"TSR_SHIMADZU_{self.suffix}.pdf",
            )
            self.productless_file = app_module.ShiftFile(
                shift_id=self.productless_shift.id,
                filename=f"TSR_SHIMADZU_PRODUCTLESS_{self.suffix}.pdf",
                original_filename=f"TSR_SHIMADZU_PRODUCTLESS_{self.suffix}.pdf",
            )
            app_module.db.session.add_all([self.file, self.productless_file])
            app_module.db.session.commit()
            self.admin_id = self.admin.id
            self.shift_id = self.shift.id
            self.productless_shift_id = self.productless_shift.id
            self.vieworks_shift_id = self.vieworks_shift.id
            self.genoray_shift_id = self.genoray_shift.id
            self.product_serial = self.product.serial_number
            self.genoray_serial = self.genoray.serial_number

    def tearDown(self):
        with self.app.app_context():
            app_module.db.session.remove()
            app_module.db.drop_all()
            reset_schema_flags(app_module)
        app_module.SUPERADMIN_USERNAMES.discard(self.username.lower())

    def admin_client(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(self.admin_id)
            session["_fresh"] = True
        return client

    def test_product_deletion_preserves_identity_and_archive_search(self):
        response = self.admin_client().delete(f"/delete_product/{self.product_serial}")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["status"], "success")

        with self.app.app_context():
            self.assertIsNone(app_module.db.session.get(app_module.Product, self.product_serial))
            shift = app_module.db.session.get(app_module.Shift, self.shift_id)
            self.assertIsNone(shift.product_id)
            self.assertEqual(getattr(shift, "product_name_snapshot", None), "Historical Product")
            self.assertEqual(getattr(shift, "product_serial_snapshot", None), self.product_serial)

        by_name = self.admin_client().get("/get_tsr_archive?scope=all&q=Historical+Product")
        self.assertEqual(by_name.status_code, 200, by_name.get_data(as_text=True))
        name_rows = by_name.get_json()["rows"]
        self.assertTrue(any(row["shift_id"] == self.shift_id and row["product"] == "Historical Product" for row in name_rows))

        by_serial = self.admin_client().get(f"/get_tsr_archive?scope=all&q={self.product_serial}")
        self.assertEqual(by_serial.status_code, 200, by_serial.get_data(as_text=True))
        serial_rows = by_serial.get_json()["rows"]
        self.assertTrue(any(row["shift_id"] == self.shift_id and row["serial"] == self.product_serial for row in serial_rows))

    def test_live_equipment_wins_over_snapshot_and_productless_stays_blank(self):
        with self.app.app_context():
            shift = app_module.db.session.get(app_module.Shift, self.shift_id)
            shift.product_name_snapshot = "Stale Snapshot"
            shift.product_serial_snapshot = "STALE-SERIAL"
            archive = app_module.resolve_tsr_archive_identity(shift)
            self.assertEqual(archive["product"], "Historical Product")
            self.assertEqual(archive["serial"], self.product_serial)

            productless = app_module.db.session.get(app_module.Shift, self.productless_shift_id)
            productless_archive = app_module.resolve_tsr_archive_identity(productless)
            self.assertEqual(productless_archive["product"], "N/A")
            self.assertEqual(productless_archive["serial"], "")

    def test_primary_product_delete_does_not_change_other_equipment_sources(self):
        response = self.admin_client().delete(f"/delete_product/{self.product_serial}")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        with self.app.app_context():
            vieworks_shift = app_module.db.session.get(app_module.Shift, self.vieworks_shift_id)
            genoray_shift = app_module.db.session.get(app_module.Shift, self.genoray_shift_id)
            self.assertEqual(vieworks_shift.product_id, self.product_serial)
            self.assertEqual(vieworks_shift.equipment_source, "vieworks")
            self.assertEqual(genoray_shift.product_id, self.genoray_serial)
            self.assertEqual(genoray_shift.equipment_source, "genoray")
            self.assertIsNone(getattr(vieworks_shift, "product_name_snapshot", None))
            self.assertIsNone(getattr(genoray_shift, "product_name_snapshot", None))

    def test_snapshot_migration_is_repeatable_and_does_not_backfill(self):
        with self.app.app_context():
            self.assertTrue(
                hasattr(app_module, "ensure_shift_product_identity_snapshot_columns"),
                "the Shift identity snapshot migration helper is missing",
            )
            app_module.ensure_shift_product_identity_snapshot_columns()
            app_module.ensure_shift_product_identity_snapshot_columns()
            with app_module.db.engine.connect() as connection:
                columns = {
                    row[1]
                    for row in connection.exec_driver_sql("PRAGMA table_info(shift)")
                }
            self.assertIn("product_name_snapshot", columns)
            self.assertIn("product_serial_snapshot", columns)
            productless = app_module.db.session.get(app_module.Shift, self.productless_shift_id)
            self.assertIsNone(productless.product_name_snapshot)
            self.assertIsNone(productless.product_serial_snapshot)


if __name__ == "__main__":
    unittest.main()
