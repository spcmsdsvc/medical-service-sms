"""Focused disposable-DB coverage for inventory Room and Product name catalog."""

import csv
import io
import json
import os
import pathlib
import tempfile
import unittest
import uuid


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_room_catalog_{uuid.uuid4().hex}.db"
os.environ["MEDICAL_SERVICE_TEST_DB"] = str(TEST_DB_PATH)
os.environ.setdefault("SECRET_KEY", "room-catalog-tests")

import app as app_module  # noqa: E402


class ProductRoomCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=True)
        cls.username = f"room_catalog_admin_{uuid.uuid4().hex[:8]}"
        app_module.SUPERADMIN_USERNAMES.add(cls.username)
        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_product_name_catalog()
            app_module.ensure_genoray_item_table()
            app_module.ensure_vieworks_item_table()
            cls.user = app_module.User(
                username=cls.username,
                password=app_module.generate_password_hash("test-password"),
                role="superadmin",
                is_active=True,
            )
            cls.client_record = app_module.Client(
                name=f"Room Catalog Client {uuid.uuid4().hex[:8]}",
                address="Room catalog test address",
            )
            app_module.db.session.add_all([cls.user, cls.client_record])
            app_module.db.session.commit()
            cls.user_id = cls.user.id
            cls.client_id = cls.client_record.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            app_module.Product.query.filter(
                app_module.Product.serial_number.like("ROOM-CATALOG-%")
            ).delete(synchronize_session=False)
            app_module.GenorayItem.query.filter(
                app_module.GenorayItem.serial_number.like("ROOM-CATALOG-%")
            ).delete(synchronize_session=False)
            app_module.VieworksItem.query.filter(
                app_module.VieworksItem.serial_number.like("ROOM-CATALOG-%")
            ).delete(synchronize_session=False)
            client = app_module.db.session.get(app_module.Client, cls.client_id)
            user = app_module.db.session.get(app_module.User, cls.user_id)
            if client:
                app_module.db.session.delete(client)
            if user:
                app_module.db.session.delete(user)
            app_module.db.session.commit()
            app_module.db.session.remove()
        app_module.SUPERADMIN_USERNAMES.discard(cls.username)

    def setUp(self):
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.user_id)
            session["_fresh"] = True

    def test_seeded_catalog_contains_split_model_choices(self):
        response = self.client.get("/api/product-name-catalog")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        values = [item["name"] for item in response.get_json()]
        self.assertEqual(len(values), 49)
        self.assertIn("MobileDart Evolution MX9 Premium", values)
        self.assertIn("MobileDart Evolution MX9c Premium", values)
        self.assertIn("MobileDart Evolution MX7c", values)
        self.assertIn("Sonialvision G4 with CH-200M", values)

    def test_catalog_admin_crud_and_normalized_duplicate(self):
        created = self.client.post("/settings/product-names", json={"name": "  Room Catalog Test  "})
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        item = created.get_json()["item"]
        self.assertEqual(item["name"], "Room Catalog Test")

        duplicate = self.client.post("/settings/product-names", json={"name": "room   catalog test"})
        self.assertEqual(duplicate.status_code, 409)

        updated = self.client.put(
            f"/settings/product-names/{item['id']}",
            json={"name": "Room Catalog Updated"},
        )
        self.assertEqual(updated.status_code, 200, updated.get_data(as_text=True))
        deleted = self.client.delete(f"/settings/product-names/{item['id']}")
        self.assertEqual(deleted.status_code, 200, deleted.get_data(as_text=True))

    def test_product_add_requires_catalog_id_and_persists_room(self):
        catalog = self.client.get("/api/product-name-catalog").get_json()[0]
        missing = self.client.post(
            "/add_product",
            json={"serial_number": "ROOM-CATALOG-MISSING", "name": catalog["name"]},
        )
        self.assertEqual(missing.status_code, 400)

        created = self.client.post(
            "/add_product",
            json={
                "serial_number": "ROOM-CATALOG-PRODUCT",
                "product_name_id": catalog["id"],
                "room": "  Room 101 ",
                "client_id": self.client_id,
            },
        )
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        with self.app.app_context():
            product = app_module.db.session.get(app_module.Product, "ROOM-CATALOG-PRODUCT")
            self.assertEqual(product.name, catalog["name"])
            self.assertEqual(product.room, "Room 101")

    def test_genoray_and_vieworks_room_round_trip_and_csv_headers(self):
        genoray = self.client.post(
            "/api/genoray/items",
            json={"serial_number": "ROOM-CATALOG-GENORAY", "name": "Free Genoray", "room": "G-1"},
        )
        self.assertEqual(genoray.status_code, 200, genoray.get_data(as_text=True))
        vieworks = self.client.post(
            "/api/vieworks/items",
            json={"serial_number": "ROOM-CATALOG-VIEWORKS", "name": "Free Vieworks", "room": "V-2"},
        )
        self.assertEqual(vieworks.status_code, 200, vieworks.get_data(as_text=True))
        self.assertEqual(
            self.client.get("/api/genoray/items").get_json()[-1]["room"],
            "G-1",
        )
        self.assertEqual(
            self.client.get("/api/vieworks/items").get_json()[-1]["room"],
            "V-2",
        )
        product_export = self.client.get("/export_products")
        self.assertIn("Room", next(csv.reader(io.StringIO(product_export.get_data(as_text=True)))))
        genoray_export = self.client.get("/genoray/export")
        self.assertIn("Room", next(csv.reader(io.StringIO(genoray_export.get_data(as_text=True)))))
        vieworks_export = self.client.get("/vieworks/export")
        self.assertIn("Room", next(csv.reader(io.StringIO(vieworks_export.get_data(as_text=True)))))

    def test_product_csv_requires_catalog_for_new_rows_and_canonicalizes_existing_updates(self):
        body = (
            "Serial Number,Description,Room\n"
            "ROOM-CATALOG-CSV,  trinias   unity  ,CSV-101\n"
            "ROOM-CATALOG-CSV-UNKNOWN,Not In Catalog,CSV-102\n"
        )
        imported = self.client.post(
            "/import_products",
            data={"file": (io.BytesIO(body.encode()), "products.csv")},
            content_type="multipart/form-data",
        )
        self.assertEqual(imported.status_code, 200, imported.get_data(as_text=True))
        self.assertEqual(imported.get_json()["created"], 1)
        self.assertEqual(imported.get_json()["skipped"], 1)
        with self.app.app_context():
            product = app_module.db.session.get(app_module.Product, "ROOM-CATALOG-CSV")
            self.assertEqual(product.name, "Trinias Unity")
            self.assertEqual(product.room, "CSV-101")

        updated = self.client.post(
            "/import_products",
            data={
                "file": (
                    io.BytesIO(b"Serial Number,Description,Room\nROOM-CATALOG-CSV,  trinias   unity  ,CSV-103\n"),
                    "products-update.csv",
                )
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(updated.status_code, 200, updated.get_data(as_text=True))
        with self.app.app_context():
            product = app_module.db.session.get(app_module.Product, "ROOM-CATALOG-CSV")
            self.assertEqual(product.name, "Trinias Unity")
            self.assertEqual(product.room, "CSV-103")

    def test_template_and_release_contracts(self):
        products = (ROOT / "templates" / "products.html").read_text(encoding="utf-8")
        settings = (ROOT / "templates" / "settings.html").read_text(encoding="utf-8")
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        manifest = json.loads((ROOT / "static" / "changelog" / "releases.json").read_text(encoding="utf-8"))
        self.assertIn("Room", products)
        self.assertIn("product-names", settings)
        self.assertIn("ProductNameCatalog", source)
        self.assertTrue(isinstance(manifest.get("releases"), list))


if __name__ == "__main__":
    unittest.main()
