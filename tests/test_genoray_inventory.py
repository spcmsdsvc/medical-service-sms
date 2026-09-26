"""Focused server-side and source contracts for the standalone Genoray inventory."""

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
TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_genoray_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB_PATH))
os.environ.setdefault("SECRET_KEY", "genoray-inventory-tests")

import app as app_module  # noqa: E402
from tests.sw_cache_version import assert_cache_version_at_least  # noqa: E402


class GenorayInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=True)
        cls.superadmin_username = f"genoray_superadmin_{uuid.uuid4().hex[:8]}"
        app_module.SUPERADMIN_USERNAMES.add(cls.superadmin_username)
        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_genoray_item_table()
            cls.admin = app_module.User(
                username=f"genoray_admin_{uuid.uuid4().hex[:8]}",
                password="test",
                role="admin",
                is_active=True,
            )
            cls.superadmin = app_module.User(
                username=cls.superadmin_username,
                password="test",
                role="superadmin",
                is_active=True,
            )
            cls.regional = app_module.User(
                username=app_module.REGIONAL_ADMIN_USERNAME,
                password="test",
                role="regional_admin",
                is_active=True,
            )
            cls.engineer = app_module.User(
                username=f"genoray_engineer_{uuid.uuid4().hex[:8]}",
                password="test",
                role="engineer",
                is_active=True,
            )
            cls.other_role = app_module.User(
                username=f"genoray_approver_{uuid.uuid4().hex[:8]}",
                password="test",
                role="approver",
                is_active=True,
            )
            cls.inactive_admin = app_module.User(
                username=f"genoray_inactive_{uuid.uuid4().hex[:8]}",
                password="test",
                role="admin",
                is_active=False,
            )
            cls.client_record = app_module.Client(
                name=f"Genoray Medical Center {uuid.uuid4().hex[:8]}",
                address="Genoray test address",
            )
            cls.product = app_module.Product(
                serial_number=f"PRODUCT-{uuid.uuid4().hex[:8]}",
                name="Existing Product Row",
            )
            app_module.db.session.add_all([
                cls.admin,
                cls.superadmin,
                cls.regional,
                cls.engineer,
                cls.other_role,
                cls.inactive_admin,
                cls.client_record,
                cls.product,
            ])
            app_module.db.session.flush()
            cls.engineer_profile = app_module.Engineer(
                employee_id=f"GEN-ENG-{uuid.uuid4().hex[:8].upper()}",
                name="Genoray Cebu Engineer",
                initials="GCE",
                branch="Cebu",
                user_id=cls.engineer.id,
            )
            app_module.db.session.add(cls.engineer_profile)
            app_module.db.session.commit()
            cls.user_ids = [
                cls.admin.id,
                cls.superadmin.id,
                cls.regional.id,
                cls.engineer.id,
                cls.other_role.id,
                cls.inactive_admin.id,
            ]
            cls.client_id = cls.client_record.id
            cls.product_serial = cls.product.serial_number
            cls.admin_id = cls.admin.id
            cls.superadmin_id = cls.superadmin.id
            cls.regional_id = cls.regional.id
            cls.engineer_id = cls.engineer.id
            cls.other_role_id = cls.other_role.id
            cls.inactive_admin_id = cls.inactive_admin.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            app_module.GenorayItem.query.delete()
            app_module.Engineer.query.filter(app_module.Engineer.user_id.in_(cls.user_ids)).delete(synchronize_session=False)
            for model, identifier in (
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
            app_module.GenorayItem.query.delete()
            app_module.GenorayBsidCounter.query.delete()
            app_module.db.session.commit()

    def client_for(self, user):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(user if isinstance(user, int) else user.id)
            session["_fresh"] = True
        return client

    def import_csv(self, client, body, filename="genoray.csv"):
        return client.post(
            "/genoray/import",
            data={"file": (io.BytesIO(body.encode()), filename)},
            content_type="multipart/form-data",
        )

    def add_item(self, client, serial, name="Genoray Item", **extra):
        payload = {"serial_number": serial, "name": name, **extra}
        return client.post("/api/genoray/items", json=payload)

    def create_linked_engineer_user(self, branch=None, active=True):
        suffix = uuid.uuid4().hex[:8].upper()
        with self.app.app_context():
            user = app_module.User(
                username=f"genoray_regional_{suffix}",
                password="test",
                role="engineer",
                is_active=active,
            )
            app_module.db.session.add(user)
            app_module.db.session.flush()
            if branch is not None:
                app_module.db.session.add(app_module.Engineer(
                    employee_id=f"GEN-REG-{suffix}",
                    name=f"Genoray Regional {suffix}",
                    initials="GR",
                    branch=branch,
                    user_id=user.id,
                ))
            app_module.db.session.commit()
            self.__class__.user_ids.append(user.id)
            return user.id

    def test_permission_helper_allows_regional_engineer_edit_but_not_admin_actions(self):
        with self.app.app_context():
            users = [app_module.db.session.get(app_module.User, user_id) for user_id in (
                self.admin_id, self.superadmin_id, self.regional_id,
                self.engineer_id, self.other_role_id, self.inactive_admin_id,
            )]
            self.assertTrue(app_module.can_access_genoray_inventory(users[0]))
            self.assertTrue(app_module.can_access_genoray_inventory(users[1]))
            self.assertTrue(app_module.can_access_genoray_inventory(users[2]))
            self.assertTrue(app_module.can_access_genoray_inventory(users[3]))
            self.assertFalse(app_module.can_access_genoray_inventory(users[4]))
            self.assertFalse(app_module.can_access_genoray_inventory(users[5]))
            self.assertFalse(app_module.can_administer_genoray_inventory(users[3]))
            self.assertTrue(app_module.can_edit_genoray_inventory(users[3]))
            self.assertTrue(app_module.can_access_inventory_pm('genoray', users[0]))
            self.assertFalse(app_module.can_access_inventory_pm('genoray', users[3]))

    def test_regional_engineer_can_add_and_edit_but_cannot_delete_import_or_pm(self):
        client = self.client_for(self.engineer_id)
        self.assertEqual(client.get("/genoray").status_code, 200)
        self.assertEqual(client.get("/api/genoray/items").status_code, 200)
        self.assertEqual(client.get("/api/genoray/summary").status_code, 200)
        created = self.add_item(client, "ENGINEER-GENORAY")
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        self.assertEqual(client.put("/api/genoray/items/ENGINEER-GENORAY", json={"name": "Updated"}).status_code, 200)
        self.assertEqual(client.get("/genoray/export").status_code, 200)
        self.assertEqual(client.delete("/api/genoray/items/ENGINEER-GENORAY").status_code, 403)
        self.assertEqual(self.import_csv(client, "Serial Number,Description\nENGINEER-IMPORT,Nope\n").status_code, 403)
        self.assertEqual(client.get("/genoray/pm").status_code, 403)

    def test_manila_missing_unsupported_and_inactive_engineers_cannot_edit(self):
        users = [
            self.create_linked_engineer_user("Manila"),
            self.create_linked_engineer_user(None),
            self.create_linked_engineer_user("Unsupported Branch"),
            self.create_linked_engineer_user("Davao", active=False),
        ]
        client = self.client_for(self.admin_id)
        self.assertEqual(self.add_item(client, "DENIED-GENORAY", "Existing" ).status_code, 200)
        for user_id in users:
            restricted = self.client_for(user_id)
            inactive = user_id == users[-1]
            with self.subTest(user_id=user_id):
                with self.app.app_context():
                    user = app_module.db.session.get(app_module.User, user_id)
                    self.assertFalse(app_module.can_edit_genoray_inventory(user))
                page = restricted.get("/genoray")
                self.assertEqual(page.status_code, 302 if inactive else 200)
                if not inactive:
                    self.assertIn("const productCanEdit = false;", page.get_data(as_text=True))
                expected_denied = 302 if inactive else 403
                self.assertEqual(self.add_item(restricted, f"DENIED-{user_id}").status_code, expected_denied)
                self.assertEqual(restricted.put("/api/genoray/items/DENIED-GENORAY", json={"name": "Changed"}).status_code, expected_denied)
                self.assertEqual(restricted.delete("/api/genoray/items/DENIED-GENORAY").status_code, expected_denied)
                self.assertEqual(self.import_csv(restricted, "Serial Number,Description\nDENIED-IMPORT,Nope\n").status_code, expected_denied)
        with self.app.app_context():
            self.assertEqual(app_module.db.session.get(app_module.GenorayItem, "DENIED-GENORAY").name, "Existing")

    def test_other_roles_remain_denied_from_genoray_routes(self):
        paths = [
            ("/genoray", "GET"),
            ("/api/genoray/items", "GET"),
            ("/api/genoray/summary", "GET"),
            ("/api/genoray/items/NOPE", "PUT"),
            ("/api/genoray/items/NOPE", "DELETE"),
            ("/genoray/import", "POST"),
            ("/genoray/export", "GET"),
        ]
        for user, user_id in (
            (self.other_role, self.other_role_id),
            (self.inactive_admin, self.inactive_admin_id),
        ):
            client = self.client_for(user_id)
            for path, method in paths:
                with self.subTest(user=user.role, path=path, method=method):
                    response = client.open(path, method=method, json={})
                    expected = (302, 403) if user is self.inactive_admin else (403,)
                    self.assertIn(response.status_code, expected, response.get_data(as_text=True))

    def test_allowed_roles_can_open_page_and_empty_apis(self):
        for user, user_id in (
            (self.admin, self.admin_id),
            (self.superadmin, self.superadmin_id),
            (self.regional, self.regional_id),
        ):
            client = self.client_for(user_id)
            with self.subTest(user=user.username):
                page = client.get("/genoray")
                self.assertEqual(page.status_code, 200)
                self.assertIn("MEDICAL SERVICE Genoray Inventory", page.get_data(as_text=True))
                self.assertEqual(client.get("/api/genoray/items").get_json(), [])
                self.assertEqual(client.get("/api/genoray/summary").get_json()["total_items"], 0)

    def test_sidebar_exposes_genoray_only_to_permitted_admins(self):
        admin_shell = self.client_for(self.admin_id).get("/products_page")
        engineer_shell = self.client_for(self.engineer_id).get("/products_page")
        self.assertEqual(admin_shell.status_code, 200)
        self.assertEqual(engineer_shell.status_code, 200)
        self.assertIn('href="/genoray"', admin_shell.get_data(as_text=True))
        self.assertIn('href="/genoray"', engineer_shell.get_data(as_text=True))
        self.assertIn('href="/genoray/pm"', admin_shell.get_data(as_text=True))
        self.assertNotIn('href="/genoray/pm"', engineer_shell.get_data(as_text=True))

    def test_page_adds_start_at_g00001_and_never_reuse_deleted_numbers(self):
        client = self.client_for(self.admin_id)
        first = self.add_item(client, "G-SEQUENCE-1", bsid="supplied-value")
        second = self.add_item(client, "G-SEQUENCE-2", bsid="another-supplied-value")
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
        self.assertEqual(first.get_json()["item"]["bsid"], "G-00001")
        self.assertEqual(second.get_json()["item"]["bsid"], "G-00002")

        self.assertEqual(client.delete("/api/genoray/items/G-SEQUENCE-1").status_code, 200)
        third = self.add_item(client, "G-SEQUENCE-3")
        self.assertEqual(third.status_code, 200, third.get_data(as_text=True))
        self.assertEqual(third.get_json()["item"]["bsid"], "G-00003")

        edited = client.put("/api/genoray/items/G-SEQUENCE-2", json={
            "bsid": "G-00010",
        })
        self.assertEqual(edited.status_code, 200, edited.get_data(as_text=True))
        fourth = self.add_item(client, "G-SEQUENCE-4")
        self.assertEqual(fourth.status_code, 200, fourth.get_data(as_text=True))
        self.assertEqual(fourth.get_json()["item"]["bsid"], "G-00011")

    def test_csv_new_rows_generate_in_order_and_updates_preserve_stored_bsid(self):
        client = self.client_for(self.admin_id)
        imported = self.import_csv(client, (
            "Serial Number,Description,BSID\n"
            "G-CSV-1,First,CSV-SUPPLIED-1\n"
            "G-CSV-2,Second,CSV-SUPPLIED-1\n"
        ))
        self.assertEqual(imported.status_code, 200, imported.get_data(as_text=True))
        rows = {
            row["serial_number"]: row
            for row in client.get("/api/genoray/items").get_json()
        }
        self.assertEqual(rows["G-CSV-1"]["bsid"], "G-00001")
        self.assertEqual(rows["G-CSV-2"]["bsid"], "G-00002")

        updated = self.import_csv(client, (
            "Serial Number,Description,BSID\n"
            "G-CSV-1,First Revised,REPLACEMENT-SUPPLIED\n"
        ), "update.csv")
        self.assertEqual(updated.status_code, 200, updated.get_data(as_text=True))
        row = next(row for row in client.get("/api/genoray/items").get_json()
                   if row["serial_number"] == "G-CSV-1")
        self.assertEqual(row["name"], "First Revised")
        self.assertEqual(row["bsid"], "G-00001")

    def test_skipped_csv_rows_do_not_consume_sequence_values(self):
        client = self.client_for(self.admin_id)
        imported = self.import_csv(client, (
            "Serial Number,Description,BSID\n"
            ",Missing Serial,ignored\n"
            "VALID-CSV,Valid Item,also-ignored\n"
        ), "skipped.csv")
        self.assertEqual(imported.status_code, 200, imported.get_data(as_text=True))
        self.assertEqual(imported.get_json()["created"], 1)
        self.assertEqual(imported.get_json()["skipped"], 1)
        row = client.get("/api/genoray/items").get_json()[0]
        self.assertEqual(row["serial_number"], "VALID-CSV")
        self.assertEqual(row["bsid"], "G-00001")

    def test_existing_blank_and_manual_bsid_values_are_preserved(self):
        client = self.client_for(self.admin_id)
        with self.app.app_context():
            app_module.db.session.add_all([
                app_module.GenorayItem(
                    serial_number="LEGACY-BLANK",
                    name="Legacy Blank",
                    bsid=None,
                ),
                app_module.GenorayItem(
                    serial_number="LEGACY-MANUAL",
                    name="Legacy Manual",
                    bsid="MANUAL-001",
                ),
            ])
            app_module.db.session.commit()

        blank_update = client.put("/api/genoray/items/LEGACY-BLANK", json={
            "name": "Legacy Blank Revised",
        })
        self.assertEqual(blank_update.status_code, 200, blank_update.get_data(as_text=True))
        self.assertEqual(blank_update.get_json()["item"]["bsid"], "")

        manual_update = client.put("/api/genoray/items/LEGACY-MANUAL", json={
            "name": "Legacy Manual Revised",
        })
        self.assertEqual(manual_update.status_code, 200, manual_update.get_data(as_text=True))
        self.assertEqual(manual_update.get_json()["item"]["bsid"], "MANUAL-001")

    def test_bsid_edit_allows_replacement_rejects_duplicate_and_clearing(self):
        client = self.client_for(self.admin_id)
        first = self.add_item(client, "G-EDIT-1")
        second = self.add_item(client, "G-EDIT-2")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)

        duplicate = client.put("/api/genoray/items/G-EDIT-1", json={
            "bsid": "g-00002",
        })
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.get_json().get("field"), "bsid")

        replaced = client.put("/api/genoray/items/G-EDIT-1", json={
            "bsid": "MANUAL-REPLACEMENT",
        })
        self.assertEqual(replaced.status_code, 200, replaced.get_data(as_text=True))
        self.assertEqual(replaced.get_json()["item"]["bsid"], "MANUAL-REPLACEMENT")

        cleared = client.put("/api/genoray/items/G-EDIT-1", json={
            "bsid": "   ",
        })
        self.assertEqual(cleared.status_code, 400)
        self.assertIn("cannot be cleared", cleared.get_json()["message"].lower())

    def test_existing_high_manual_g_number_advances_future_generation(self):
        client = self.client_for(self.admin_id)
        with self.app.app_context():
            app_module.db.session.add(app_module.GenorayItem(
                serial_number="LEGACY-G-0042",
                name="Legacy G Number",
                bsid="G-00042",
            ))
            app_module.db.session.commit()

        generated = self.add_item(client, "AFTER-LEGACY-G")
        self.assertEqual(generated.status_code, 200, generated.get_data(as_text=True))
        self.assertEqual(generated.get_json()["item"]["bsid"], "G-00043")

    def test_concurrent_page_adds_receive_distinct_sequence_values(self):
        def add_from_thread(index):
            client = self.client_for(self.admin_id)
            return client.post("/api/genoray/items", json={
                "serial_number": f"CONCURRENT-{index}",
                "name": f"Concurrent {index}",
            })

        with ThreadPoolExecutor(max_workers=4) as executor:
            responses = list(executor.map(add_from_thread, range(4)))

        self.assertTrue(all(response.status_code == 200 for response in responses), [
            response.get_data(as_text=True) for response in responses
        ])
        assigned = sorted(response.get_json()["item"]["bsid"] for response in responses)
        self.assertEqual(assigned, ["G-00001", "G-00002", "G-00003", "G-00004"])

    def test_crud_owner_status_and_product_isolation(self):
        client = self.client_for(self.admin_id)
        future = (date.today() + timedelta(days=30)).isoformat()
        created = client.post("/api/genoray/items", json={
            "serial_number": "gy-001",
            "name": "Genoray Dental Unit",
            "bsid": "Gy-Bsid-1",
            "client_id": self.client_id,
            "start_warranty": date.today().isoformat(),
            "end_warranty": future,
            "under_contract": True,
        })
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        item = created.get_json()["item"]
        self.assertEqual(item["serial_number"], "GY-001")
        self.assertEqual(item["bsid"], "G-00001")
        self.assertEqual(item["client_name"], self.client_record.name)
        self.assertEqual(item["computed_status"], "Under Contract")

        duplicate_serial = client.post("/api/genoray/items", json={
            "serial_number": "gy-001", "name": "Duplicate",
        })
        self.assertEqual(duplicate_serial.status_code, 409)
        second_item = client.post("/api/genoray/items", json={
            "serial_number": "GY-002", "name": "Second Item", "bsid": " gy-bsid-1 ",
        })
        self.assertEqual(second_item.status_code, 200)
        self.assertEqual(second_item.get_json()["item"]["bsid"], "G-00002")
        self.assertEqual(client.get("/api/genoray/items").get_json()[0]["name"], "Genoray Dental Unit")

        updated = client.put("/api/genoray/items/gy-001", json={
            "serial_number": "gy-001-new",
            "name": "Updated Genoray Dental Unit",
            "client_id": self.client_id,
            "under_contract": False,
        })
        self.assertEqual(updated.status_code, 200, updated.get_data(as_text=True))
        self.assertEqual(updated.get_json()["item"]["serial_number"], "GY-001-NEW")
        deleted = client.delete("/api/genoray/items/GY-001-NEW")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(client.delete("/api/genoray/items/GY-002").status_code, 200)
        with self.app.app_context():
            self.assertIsNotNone(app_module.db.session.get(app_module.Product, self.product_serial))
            self.assertEqual(app_module.GenorayItem.query.count(), 0)

    def test_csv_import_export_and_supplied_bsid_is_ignored(self):
        client = self.client_for(self.admin_id)
        csv_body = (
            "Serial Number,Description,BSID,Current Owner,Start Date,End Date,Contract\n"
            f"GY-CSV-1,Imported Genoray,GY-CSV-BSID,{self.client_record.name},2026-01-01,2027-01-01,Yes\n"
        )
        imported = client.post(
            "/genoray/import",
            data={"file": (io.BytesIO(csv_body.encode()), "genoray.csv")},
            content_type="multipart/form-data",
        )
        self.assertEqual(imported.status_code, 200, imported.get_data(as_text=True))
        self.assertEqual(imported.get_json()["created"], 1)
        row = client.get("/api/genoray/items").get_json()[0]
        self.assertEqual(row["bsid"], "G-00001")
        self.assertEqual(row["client_id"], self.client_id)
        self.assertEqual(row["computed_status"], "Under Contract")

        duplicate_csv = (
            "Serial Number,Description,BSID\n"
            "GY-CSV-2,Second,GY-CSV-BSID\n"
            "GY-CSV-3,Third,gy-csv-bsid\n"
        )
        imported_duplicate_values = client.post(
            "/genoray/import",
            data={"file": (io.BytesIO(duplicate_csv.encode()), "duplicate.csv")},
            content_type="multipart/form-data",
        )
        self.assertEqual(imported_duplicate_values.status_code, 200)
        self.assertEqual(imported_duplicate_values.get_json()["created"], 2)
        imported_rows = {
            row["serial_number"]: row["bsid"]
            for row in client.get("/api/genoray/items").get_json()
        }
        self.assertEqual(imported_rows["GY-CSV-1"], "G-00001")
        self.assertEqual(imported_rows["GY-CSV-2"], "G-00002")
        self.assertEqual(imported_rows["GY-CSV-3"], "G-00003")

        exported = client.get("/genoray/export")
        self.assertEqual(exported.status_code, 200)
        rows = list(csv.reader(io.StringIO(exported.get_data(as_text=True))))
        self.assertEqual(rows[0][:4], ["Serial Number", "Description", "BSID", "Current Owner"])
        self.assertEqual(rows[1][0], "GY-CSV-1")
        self.assertEqual(rows[1][2], "G-00001")

    def test_template_layout_release_and_worker_contracts(self):
        template = (ROOT / "templates" / "products.html").read_text(encoding="utf-8")
        layout = (ROOT / "templates" / "layout.html").read_text(encoding="utf-8")
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("inventory_mode", template)
        for marker in (
            "'/api/genoray/items'", "'/api/genoray/summary'", "'/genoray/import'", "'/genoray/export'",
            "medicalServiceGenoraySortV1", "medicalServiceGenorayFreezeV1",
            "if(isGenorayInventory) return '';", "!isGenorayInventory",
            "Assigned automatically on save", "cannot be cleared once it has been assigned",
            "bsidField.disabled = isGenorayInventory", "responseData.item || responseData",
        ):
            self.assertIn(marker, template)
        self.assertIn("nav_can_access_genoray_inventory", source)
        self.assertIn("allocate_genoray_bsid", source)
        self.assertIn("genoray_bsid_counter", source)
        self.assertIn("can_access_genoray_inventory", layout)
        self.assertIn("nav_link('/genoray'", layout)
        assert_cache_version_at_least(self, 159, source)

        manifest = json.loads((ROOT / "static/changelog/releases.json").read_text(encoding="utf-8"))
        self.assertTrue(any(
            item["item_key"] == "2026-09-15-genoray-inventory-admins"
            for release in manifest["releases"]
            for item in release.get("items", [])
        ))


if __name__ == "__main__":
    unittest.main()
