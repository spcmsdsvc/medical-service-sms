"""Focused server-side and source contracts for the standalone Vieworks inventory."""

import csv
from concurrent.futures import ThreadPoolExecutor
import io
import json
import os
import pathlib
import tempfile
import unittest
import uuid
from datetime import date, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_vieworks_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB_PATH))
os.environ.setdefault("SECRET_KEY", "vieworks-inventory-tests")

import app as app_module  # noqa: E402


class VieworksSourceContractTests(unittest.TestCase):
    def test_vieworks_contract_is_present(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        template = (ROOT / "templates" / "products.html").read_text(encoding="utf-8")
        layout = (ROOT / "templates" / "layout.html").read_text(encoding="utf-8")
        self.assertIn("class VieworksItem", source)
        self.assertIn("vieworks_item", source)
        self.assertIn("class VieworksBsidCounter", source)
        self.assertIn("vieworks_bsid_counter", source)
        for marker in (
            "'/api/vieworks/items'", "'/api/vieworks/summary'",
            "'/vieworks/import'", "'/vieworks/export'",
            "medicalServiceVieworksSortV1", "medicalServiceVieworksFreezeV1",
            "isVieworksInventory", "V-{int(next_number) - 1:06d}",
        ):
            self.assertIn(marker, template if "medicalService" in marker or "isVieworks" in marker else source)
        self.assertIn("nav_can_access_vieworks_inventory", source)
        self.assertIn("nav_link('/vieworks'", layout)
        self.assertIn("medical-service-pwa-offline-navigation-v160-vieworks-inventory", source)

        manifest = json.loads((ROOT / "static" / "changelog" / "releases.json").read_text(encoding="utf-8"))
        self.assertTrue(any(
            item["item_key"] == "2026-09-15-vieworks-inventory-admins"
            for release in manifest["releases"]
            for item in release.get("items", [])
        ))


class VieworksInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=True)
        cls.superadmin_username = f"vieworks_superadmin_{uuid.uuid4().hex[:8]}"
        app_module.SUPERADMIN_USERNAMES.add(cls.superadmin_username)
        with cls.app.app_context():
            cls.app_module_ensure = app_module.ensure_vieworks_item_table
            app_module.db.create_all()
            cls.app_module_ensure()
            cls.admin = app_module.User(
                username=f"vieworks_admin_{uuid.uuid4().hex[:8]}", password="test",
                role="admin", is_active=True,
            )
            cls.superadmin = app_module.User(
                username=cls.superadmin_username, password="test",
                role="superadmin", is_active=True,
            )
            cls.regional = app_module.User.query.filter_by(
                username=app_module.REGIONAL_ADMIN_USERNAME
            ).first()
            cls.regional_created = cls.regional is None
            if cls.regional is None:
                cls.regional = app_module.User(
                    username=app_module.REGIONAL_ADMIN_USERNAME, password="test",
                    role="regional_admin", is_active=True,
                )
            cls.engineer = app_module.User(
                username=f"vieworks_engineer_{uuid.uuid4().hex[:8]}", password="test",
                role="engineer", is_active=True,
            )
            cls.other_role = app_module.User(
                username=f"vieworks_approver_{uuid.uuid4().hex[:8]}", password="test",
                role="approver", is_active=True,
            )
            cls.inactive_admin = app_module.User(
                username=f"vieworks_inactive_{uuid.uuid4().hex[:8]}", password="test",
                role="admin", is_active=False,
            )
            cls.client_record = app_module.Client(
                name=f"Vieworks Medical Center {uuid.uuid4().hex[:8]}",
                address="Vieworks test address",
            )
            cls.product = app_module.Product(
                serial_number=f"VIEWORKS-PRODUCT-{uuid.uuid4().hex[:8]}",
                name="Existing Product Row",
            )
            cls.genoray = app_module.GenorayItem(
                serial_number=f"VIEWORKS-GENORAY-{uuid.uuid4().hex[:8]}",
                name="Existing Genoray Row",
            )
            app_module.db.session.add_all([
                cls.admin, cls.superadmin, cls.regional, cls.engineer,
                cls.other_role, cls.inactive_admin, cls.client_record,
                cls.product, cls.genoray,
            ])
            app_module.db.session.commit()
            cls.user_ids = [
                cls.admin.id, cls.superadmin.id, cls.engineer.id,
                cls.other_role.id, cls.inactive_admin.id,
            ]
            if cls.regional_created:
                cls.user_ids.append(cls.regional.id)
            cls.client_id = cls.client_record.id
            cls.product_serial = cls.product.serial_number
            cls.genoray_serial = cls.genoray.serial_number
            cls.admin_id = cls.admin.id
            cls.superadmin_id = cls.superadmin.id
            cls.regional_id = cls.regional.id
            cls.engineer_id = cls.engineer.id
            cls.other_role_id = cls.other_role.id
            cls.inactive_admin_id = cls.inactive_admin.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            app_module.VieworksItem.query.delete()
            app_module.VieworksBsidCounter.query.delete()
            for model, identifier in (
                (app_module.GenorayItem, cls.genoray_serial),
                (app_module.Product, cls.product_serial),
                (app_module.Client, cls.client_id),
            ):
                row = app_module.db.session.get(model, identifier)
                if row:
                    app_module.db.session.delete(row)
            for user_id in cls.user_ids:
                row = app_module.db.session.get(app_module.User, user_id)
                if row:
                    app_module.db.session.delete(row)
            app_module.db.session.commit()
            app_module.db.session.remove()
        app_module.SUPERADMIN_USERNAMES.discard(cls.superadmin_username)

    def setUp(self):
        with self.app.app_context():
            app_module.VieworksItem.query.delete()
            app_module.VieworksBsidCounter.query.delete()
            app_module.db.session.commit()

    def client_for(self, user):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(user if isinstance(user, int) else user.id)
            session["_fresh"] = True
        return client

    def import_csv(self, client, body, filename="vieworks.csv"):
        return client.post(
            "/vieworks/import",
            data={"file": (io.BytesIO(body.encode()), filename)},
            content_type="multipart/form-data",
        )

    def add_item(self, client, serial, name="Vieworks Item", **extra):
        return client.post("/api/vieworks/items", json={"serial_number": serial, "name": name, **extra})

    def test_permission_helper_and_every_route_boundary(self):
        with self.app.app_context():
            users = [
                app_module.db.session.get(app_module.User, user_id)
                for user_id in (self.admin_id, self.superadmin_id, self.regional_id,
                                self.engineer_id, self.other_role_id, self.inactive_admin_id)
            ]
            self.assertTrue(app_module.can_access_vieworks_inventory(users[0]))
            self.assertTrue(app_module.can_access_vieworks_inventory(users[1]))
            self.assertTrue(app_module.can_access_vieworks_inventory(users[2]))
            self.assertFalse(app_module.can_access_vieworks_inventory(users[3]))
            self.assertFalse(app_module.can_access_vieworks_inventory(users[4]))
            self.assertFalse(app_module.can_access_vieworks_inventory(users[5]))

        paths = [
            ("/vieworks", "GET"), ("/api/vieworks/items", "GET"),
            ("/api/vieworks/summary", "GET"), ("/api/vieworks/items/NOPE", "PUT"),
            ("/api/vieworks/items/NOPE", "DELETE"), ("/vieworks/import", "POST"),
            ("/vieworks/export", "GET"),
        ]
        for user_id in (self.engineer_id, self.other_role_id, self.inactive_admin_id):
            client = self.client_for(user_id)
            for path, method in paths:
                with self.subTest(user=user_id, path=path, method=method):
                    response = client.open(path, method=method, json={})
                    expected = (302, 403) if user_id == self.inactive_admin_id else (403,)
                    self.assertIn(response.status_code, expected, response.get_data(as_text=True))

    def test_allowed_roles_can_open_empty_page_and_sidebar(self):
        for user_id in (self.admin_id, self.superadmin_id, self.regional_id):
            client = self.client_for(user_id)
            self.assertEqual(client.get("/vieworks").status_code, 200)
            self.assertIn("MEDICAL SERVICE Vieworks Inventory", client.get("/vieworks").get_data(as_text=True))
            self.assertEqual(client.get("/api/vieworks/items").get_json(), [])
            self.assertEqual(client.get("/api/vieworks/summary").get_json()["total_items"], 0)
        self.assertIn('href="/vieworks"', self.client_for(self.admin_id).get("/products_page").get_data(as_text=True))
        self.assertNotIn('href="/vieworks"', self.client_for(self.engineer_id).get("/products_page").get_data(as_text=True))

    def test_first_load_finishes_request_writer_before_creating_index(self):
        with self.app.app_context():
            with app_module.db.engine.begin() as connection:
                connection.exec_driver_sql("DROP INDEX IF EXISTS uq_vieworks_bsid_nonblank")
                connection.exec_driver_sql(
                    "CREATE TABLE IF NOT EXISTS vieworks_lock_probe (id INTEGER PRIMARY KEY)"
                )
            # A preceding request migration can hold this session's writer lock.
            app_module.db.session.execute(app_module.db.text(
                "INSERT INTO vieworks_lock_probe DEFAULT VALUES"
            ))
            app_module._vieworks_item_table_ready = False
            app_module._vieworks_bsid_counter_ready = False
            app_module.ensure_vieworks_item_table()
            with app_module.db.engine.connect() as connection:
                indexes = connection.exec_driver_sql(
                    "PRAGMA index_list('vieworks_item')"
                ).fetchall()
                saved_probe = connection.exec_driver_sql(
                    "SELECT COUNT(*) FROM vieworks_lock_probe"
                ).scalar()
            self.assertIn("uq_vieworks_bsid_nonblank", [row[1] for row in indexes])
            self.assertGreater(saved_probe, 0)

    def test_page_sequence_is_six_digits_and_never_reused(self):
        client = self.client_for(self.admin_id)
        first = self.add_item(client, "V-SEQUENCE-1", bsid="ignored")
        second = self.add_item(client, "V-SEQUENCE-2", bsid="also-ignored")
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
        self.assertEqual(first.get_json()["item"]["bsid"], "V-000001")
        self.assertEqual(second.get_json()["item"]["bsid"], "V-000002")
        self.assertEqual(client.delete("/api/vieworks/items/V-SEQUENCE-1").status_code, 200)
        third = self.add_item(client, "V-SEQUENCE-3")
        self.assertEqual(third.get_json()["item"]["bsid"], "V-000003")
        edited = client.put("/api/vieworks/items/V-SEQUENCE-2", json={"bsid": "V-000010"})
        self.assertEqual(edited.status_code, 200, edited.get_data(as_text=True))
        fourth = self.add_item(client, "V-SEQUENCE-4")
        self.assertEqual(fourth.get_json()["item"]["bsid"], "V-000011")

    def test_csv_new_rows_generate_in_order_and_updates_preserve_bsid(self):
        client = self.client_for(self.admin_id)
        imported = self.import_csv(client, "Serial Number,Description,BSID\nCSV-V-1,First,supplied\nCSV-V-2,Second,supplied\n")
        self.assertEqual(imported.status_code, 200, imported.get_data(as_text=True))
        rows = {row["serial_number"]: row for row in client.get("/api/vieworks/items").get_json()}
        self.assertEqual(rows["CSV-V-1"]["bsid"], "V-000001")
        self.assertEqual(rows["CSV-V-2"]["bsid"], "V-000002")
        updated = self.import_csv(client, "Serial Number,Description,BSID\nCSV-V-1,First Revised,replacement\n", "update.csv")
        self.assertEqual(updated.status_code, 200, updated.get_data(as_text=True))
        rows = {row["serial_number"]: row for row in client.get("/api/vieworks/items").get_json()}
        self.assertEqual(rows["CSV-V-1"]["name"], "First Revised")
        self.assertEqual(rows["CSV-V-1"]["bsid"], "V-000001")

    def test_csv_skips_do_not_consume_ids_and_owner_status_are_mapped(self):
        client = self.client_for(self.admin_id)
        body = (
            "Serial Number,Description,BSID,Current Owner,Start Date,End Date,Contract\n"
            ",Missing,ignored\n"
            f"VALID-V,Valid,ignored,{self.client_record.name},2026-01-01,2027-01-01,Yes\n"
        )
        imported = self.import_csv(client, body, "mapped.csv")
        self.assertEqual(imported.status_code, 200, imported.get_data(as_text=True))
        self.assertEqual(imported.get_json()["skipped"], 1)
        row = client.get("/api/vieworks/items").get_json()[0]
        self.assertEqual(row["bsid"], "V-000001")
        self.assertEqual(row["client_id"], self.client_id)
        self.assertEqual(row["computed_status"], "Under Contract")

    def test_bsid_edit_duplicate_clear_and_manual_seed_rules(self):
        client = self.client_for(self.admin_id)
        first = self.add_item(client, "V-EDIT-1")
        second = self.add_item(client, "V-EDIT-2")
        self.assertEqual(client.put("/api/vieworks/items/V-EDIT-1", json={"bsid": "v-000002"}).status_code, 409)
        replaced = client.put("/api/vieworks/items/V-EDIT-1", json={"bsid": "MANUAL-V"})
        self.assertEqual(replaced.status_code, 200, replaced.get_data(as_text=True))
        self.assertEqual(client.put("/api/vieworks/items/V-EDIT-1", json={"bsid": " "}).status_code, 400)
        with self.app.app_context():
            app_module.db.session.add(app_module.VieworksItem(
                serial_number="LEGACY-V-0042", name="Legacy", bsid="V-00042"
            ))
            app_module.db.session.commit()
        generated = self.add_item(client, "AFTER-LEGACY-V")
        self.assertEqual(generated.get_json()["item"]["bsid"], "V-000043")

    def test_concurrent_creates_are_distinct_and_models_are_isolated(self):
        def add_from_thread(index):
            return self.add_item(self.client_for(self.admin_id), f"CONCURRENT-V-{index}")

        with ThreadPoolExecutor(max_workers=4) as executor:
            responses = list(executor.map(add_from_thread, range(4)))
        self.assertTrue(all(response.status_code == 200 for response in responses), [
            response.get_data(as_text=True) for response in responses
        ])
        self.assertEqual(sorted(response.get_json()["item"]["bsid"] for response in responses), [
            "V-000001", "V-000002", "V-000003", "V-000004"
        ])
        with self.app.app_context():
            self.assertIsNotNone(app_module.db.session.get(app_module.Product, self.product_serial))
            self.assertIsNotNone(app_module.db.session.get(app_module.GenorayItem, self.genoray_serial))
            self.assertEqual(app_module.VieworksItem.query.count(), 4)

    def test_template_release_and_export_contracts(self):
        client = self.client_for(self.admin_id)
        self.add_item(client, "EXPORT-V", client_id=self.client_id)
        exported = client.get("/vieworks/export")
        self.assertEqual(exported.status_code, 200)
        rows = list(csv.reader(io.StringIO(exported.get_data(as_text=True))))
        self.assertEqual(rows[0][:4], ["Serial Number", "Description", "BSID", "Current Owner"])
        self.assertEqual(rows[1][2], "V-000001")


if __name__ == "__main__":
    unittest.main()
