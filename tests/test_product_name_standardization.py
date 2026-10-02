"""Focused disposable-DB coverage for existing Product name standardization."""

import io
import json
import os
import pathlib
import tempfile
import unittest
import uuid


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_product_standardization_{uuid.uuid4().hex}.db"
os.environ["MEDICAL_SERVICE_TEST_DB"] = str(TEST_DB_PATH)
os.environ.setdefault("SECRET_KEY", "product-standardization-tests")

import app as app_module  # noqa: E402


class ProductNameStandardizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=True)
        cls.username = f"product_standardization_admin_{uuid.uuid4().hex[:8]}"
        app_module.SUPERADMIN_USERNAMES.add(cls.username)
        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_product_name_catalog()
            cls.user = app_module.User(
                username=cls.username,
                password=app_module.generate_password_hash("test-password"),
                role="superadmin",
                is_active=True,
            )
            cls.client_record = app_module.Client(
                name=f"Standardization Client {uuid.uuid4().hex[:8]}",
                address="Standardization test address",
            )
            app_module.db.session.add_all([cls.user, cls.client_record])
            app_module.db.session.commit()
            cls.user_id = cls.user.id
            cls.client_id = cls.client_record.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            app_module.Product.query.filter(
                app_module.Product.serial_number.like("PRODUCT-STANDARDIZATION-%")
            ).delete(synchronize_session=False)
            app_module.ProductNameCatalog.query.filter(
                app_module.ProductNameCatalog.name.like("Standardization Catalog %")
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

    def catalog_item(self, name="Trinias Unity"):
        with self.app.app_context():
            return app_module.ProductNameCatalog.query.filter_by(name=name).first()

    def add_product(self, serial, name="Trinias Unity"):
        item = self.catalog_item(name)
        with self.app.app_context():
            product = app_module.Product(
                serial_number=serial,
                name=name,
                room="Room A",
                client_id=self.client_id,
            )
            app_module.db.session.add(product)
            app_module.db.session.commit()

    def test_product_edit_requires_catalog_and_canonicalizes_name(self):
        serial = "PRODUCT-STANDARDIZATION-EDIT"
        self.add_product(serial)
        missing = self.client.put(
            f"/update_product/{serial}",
            json={"serial_number": serial, "name": "Arbitrary Legacy Text", "client_id": self.client_id},
        )
        self.assertEqual(missing.status_code, 400, missing.get_data(as_text=True))

        item = self.catalog_item("Trinias Unity")
        saved = self.client.put(
            f"/update_product/{serial}",
            json={
                "serial_number": serial,
                "name": "Arbitrary Legacy Text",
                "product_name_id": item.id,
                "client_id": self.client_id,
                "room": "Room B",
            },
        )
        self.assertEqual(saved.status_code, 200, saved.get_data(as_text=True))
        with self.app.app_context():
            product = app_module.db.session.get(app_module.Product, serial)
            self.assertEqual(product.name, "Trinias Unity")
            self.assertEqual(product.room, "Room B")

    def test_standardization_review_suggests_exact_normalized_match_and_detects_stale_apply(self):
        serial = "PRODUCT-STANDARDIZATION-REVIEW"
        with self.app.app_context():
            app_module.db.session.add(app_module.Product(
                serial_number=serial,
                name="  trinias   unity  ",
                room="Room C",
                client_id=self.client_id,
            ))
            app_module.db.session.commit()

        review = self.client.get("/settings/product-name-standardization-data")
        self.assertEqual(review.status_code, 200, review.get_data(as_text=True))
        group = next(row for row in review.get_json()["groups"] if row["legacy_name"] == "  trinias   unity  ")
        self.assertEqual(group["count"], 1)
        self.assertEqual(group["suggestion"]["name"], "Trinias Unity")
        self.assertEqual(group["products"][0]["room"], "Room C")

        item = self.catalog_item("Trinias Unity")
        applied = self.client.post(
            "/settings/product-name-standardization-apply",
            json={
                "expected_current_name": "  trinias   unity  ",
                "serial_numbers": [serial],
                "product_name_id": item.id,
            },
        )
        self.assertEqual(applied.status_code, 200, applied.get_data(as_text=True))
        self.assertEqual(applied.get_json()["updated_product_count"], 1)
        with self.app.app_context():
            self.assertTrue(app_module.ActivityLog.query.filter(
                app_module.ActivityLog.action.like("Standardized 1 Product master(s)%")
            ).first())

        stale = self.client.post(
            "/settings/product-name-standardization-apply",
            json={
                "expected_current_name": "  trinias   unity  ",
                "serial_numbers": [serial],
                "product_name_id": item.id,
            },
        )
        self.assertEqual(stale.status_code, 409, stale.get_data(as_text=True))

        first = "PRODUCT-STANDARDIZATION-ATOMIC-1"
        second = "PRODUCT-STANDARDIZATION-ATOMIC-2"
        with self.app.app_context():
            app_module.db.session.add_all([
                app_module.Product(serial_number=first, name="Atomic Legacy", client_id=self.client_id),
                app_module.Product(serial_number=second, name="Atomic Legacy", client_id=self.client_id),
            ])
            app_module.db.session.commit()
        atomic = self.client.post(
            "/settings/product-name-standardization-apply",
            json={
                "expected_current_name": "Atomic Legacy",
                "serial_numbers": [first, "PRODUCT-STANDARDIZATION-MISSING"],
                "product_name_id": item.id,
            },
        )
        self.assertEqual(atomic.status_code, 409, atomic.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(app_module.db.session.get(app_module.Product, first).name, "Atomic Legacy")

    def test_review_tiers_counts_and_audit_serials(self):
        names = {
            "PRODUCT-STANDARDIZATION-TIER-MATCH": "TRINIAS: unity-smart",
            "PRODUCT-STANDARDIZATION-TIER-CLOSEST": "Trinias Unity Smart C16",
            "PRODUCT-STANDARDIZATION-TIER-NONE": "Zzqx Unrelated Device",
            "PRODUCT-STANDARDIZATION-TIER-BLANK": "",
        }
        with self.app.app_context():
            app_module.db.session.add_all([
                app_module.Product(serial_number=serial, name=name, client_id=self.client_id)
                for serial, name in names.items()
            ])
            app_module.db.session.commit()
        self.add_product("PRODUCT-STANDARDIZATION-TIER-USED", "Bransist Alexa")

        data = self.client.get("/settings/product-name-standardization-data").get_json()
        groups = {row["legacy_name"]: row for row in data["groups"]}
        match = groups["TRINIAS: unity-smart"]
        self.assertEqual((match["suggestion_tier"], match["suggestion"]["name"]), ("match", "Trinias Unity Smart"))
        closest = groups["Trinias Unity Smart C16"]
        self.assertEqual((closest["suggestion_tier"], closest["suggestion"]["name"]), ("closest", "Trinias Unity Smart"))
        for name in ("Zzqx Unrelated Device", ""):
            self.assertIsNone(groups[name]["suggestion"])
            self.assertIsNone(groups[name]["suggestion_tier"])

        usage = {row["name"]: row["usage_count"] for row in data["catalog"]}
        self.assertGreaterEqual(usage["Bransist Alexa"], 1)
        self.assertEqual(data["standardized_products"], sum(usage.values()))
        self.assertEqual(
            data["total_products"],
            data["standardized_products"] + sum(row["count"] for row in data["groups"]),
        )

        applied = self.client.post(
            "/settings/product-name-standardization-apply",
            json={
                "expected_current_name": "TRINIAS: unity-smart",
                "serial_numbers": ["PRODUCT-STANDARDIZATION-TIER-MATCH"],
                "product_name_id": match["suggestion"]["id"],
            },
        )
        self.assertEqual(applied.status_code, 200, applied.get_data(as_text=True))
        with self.app.app_context():
            self.assertTrue(app_module.ActivityLog.query.filter(
                app_module.ActivityLog.action.like("%[serials: PRODUCT-STANDARDIZATION-TIER-MATCH]")
            ).first())

    def test_catalog_rename_cascades_and_delete_blocks_in_use(self):
        created = self.client.post("/settings/product-names", json={"name": "Standardization Catalog Original"})
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        item = created.get_json()["item"]
        serial = "PRODUCT-STANDARDIZATION-CATALOG"
        self.add_product(serial, "Trinias Unity")
        item_id = item["id"]
        with self.app.app_context():
            product = app_module.db.session.get(app_module.Product, serial)
            product.name = "Standardization Catalog Original"
            app_module.db.session.commit()

        renamed = self.client.put(
            f"/settings/product-names/{item_id}",
            json={"name": "Standardization Catalog Renamed"},
        )
        self.assertEqual(renamed.status_code, 200, renamed.get_data(as_text=True))
        self.assertEqual(renamed.get_json()["updated_product_count"], 1)
        with self.app.app_context():
            self.assertEqual(
                app_module.db.session.get(app_module.Product, serial).name,
                "Standardization Catalog Renamed",
            )
            self.assertTrue(app_module.ActivityLog.query.filter(
                app_module.ActivityLog.action.like("Updated Product name catalog entry: Standardization Catalog Original%")
            ).first())

        blocked = self.client.delete(f"/settings/product-names/{item_id}")
        self.assertEqual(blocked.status_code, 409, blocked.get_data(as_text=True))
        self.assertEqual(blocked.get_json()["affected_product_count"], 1)

    def test_csv_invalid_name_skips_existing_row_without_partial_update(self):
        serial = "PRODUCT-STANDARDIZATION-CSV"
        self.add_product(serial)
        imported = self.client.post(
            "/import_products",
            data={
                "file": (
                    io.BytesIO(
                        b"Serial Number,Description,Room\n"
                        b"PRODUCT-STANDARDIZATION-CSV,Not A Catalog Name,Changed Room\n"
                    ),
                    "invalid-standardization.csv",
                )
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(imported.status_code, 200, imported.get_data(as_text=True))
        self.assertEqual(imported.get_json()["updated"], 0)
        self.assertEqual(imported.get_json()["skipped"], 1)
        self.assertEqual(imported.get_json()["invalid_product_names"], 1)
        with self.app.app_context():
            product = app_module.db.session.get(app_module.Product, serial)
            self.assertEqual(product.name, "Trinias Unity")
            self.assertEqual(product.room, "Room A")

    def test_templates_expose_standardization_controls(self):
        products = (ROOT / "templates" / "products.html").read_text(encoding="utf-8")
        settings = (ROOT / "templates" / "settings.html").read_text(encoding="utf-8")
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        manifest = json.loads((ROOT / "static" / "changelog" / "releases.json").read_text(encoding="utf-8"))
        self.assertIn("Legacy product name", products)
        self.assertIn("product-name-standardization-data", source)
        self.assertIn("product-name-standardization-apply", source)
        self.assertIn("Existing Products to Standardize", settings)
        for marker in ("Select all Matches", "Apply selected (", "Add as new name", "product-name-catalog-search"):
            self.assertIn(marker, settings)
        self.assertNotIn("product-standardization-options-", settings)
        self.assertTrue(isinstance(manifest.get("releases"), list))
        settings_response = self.client.get("/settings")
        self.assertEqual(settings_response.status_code, 200, settings_response.get_data(as_text=True))
        self.assertIn("Existing Products to Standardize", settings_response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
