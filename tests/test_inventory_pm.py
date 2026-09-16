"""Focused disposable-database tests for Genoray/Vieworks PM monitoring."""

import json
import os
import pathlib
import tempfile
import unittest
import uuid
from datetime import date, datetime, timedelta
from unittest.mock import patch

from tests.sw_cache_version import assert_cache_version_at_least

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_inventory_pm_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB_PATH))
os.environ.setdefault("SECRET_KEY", "inventory-pm-tests")

import app as app_module  # noqa: E402


class InventoryPmSourceContractTests(unittest.TestCase):
    def test_pm_contract_markers_exist(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        template = (ROOT / "templates" / "inventory_pm.html").read_text(encoding="utf-8")
        layout = (ROOT / "templates" / "layout.html").read_text(encoding="utf-8")
        self.assertIn("class InventoryPmVisit", source)
        self.assertIn("inventory_pm_visit", source)
        self.assertIn("can_access_inventory_pm", source)
        self.assertIn("/api/<brand>/pm/visits", source)
        self.assertIn("cadence", source)
        self.assertIn("add_inventory_pm_months", source)
        self.assertIn("semi_annual", source)
        self.assertIn("quarterly", source)
        self.assertIn("April", template)
        self.assertIn("March", template)
        self.assertIn('id="pm-month-filter"', template)
        self.assertIn('id="pm-cadence"', template)
        self.assertIn('id="pm-start-date"', template)
        self.assertIn("Keep current schedule", template)
        self.assertIn("Update and Rebuild Plan", template)
        self.assertIn("cadence-rebuild", template)
        self.assertIn("regenerated_visits", source)
        self.assertIn("removed_future_dates", source)
        self.assertIn("plan_key", source)
        self.assertIn('@media (max-width: 375px)', template)
        self.assertIn('.pm-tap { min-height: 44px; }', template)
        self.assertIn("Genoray PM", layout)
        self.assertIn("Vieworks PM", layout)
        assert_cache_version_at_least(self, 163, source)
        releases = json.loads((ROOT / "static" / "changelog" / "releases.json").read_text(encoding="utf-8"))
        release = next(
            release for release in releases.get("releases", [])
            if release.get("release_key") == "2026-09-16-inventory-pm-monitoring"
        )
        self.assertIn("Semi-Annual", release["items"][0]["description"])
        self.assertIn("Product-name matching", release["items"][0]["description"])


class InventoryPmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=True)
        cls.superadmin_username = f"pm_superadmin_{uuid.uuid4().hex[:8]}"
        app_module.SUPERADMIN_USERNAMES.add(cls.superadmin_username)
        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_inventory_pm_visit_table()
            cls.admin = app_module.User(
                username=f"pm_admin_{uuid.uuid4().hex[:8]}", password="test",
                role="admin", is_active=True,
            )
            cls.superadmin = app_module.User(
                username=cls.superadmin_username, password="test",
                role="superadmin", is_active=True,
            )
            cls.engineer_user = app_module.User(
                username=f"pm_engineer_{uuid.uuid4().hex[:8]}", password="test",
                role="engineer", is_active=True,
            )
            cls.other_user = app_module.User(
                username=f"pm_approver_{uuid.uuid4().hex[:8]}", password="test",
                role="approver", is_active=True,
            )
            cls.inactive_admin = app_module.User(
                username=f"pm_inactive_{uuid.uuid4().hex[:8]}", password="test",
                role="admin", is_active=False,
            )
            cls.engineer = app_module.Engineer(
                employee_id=f"PM-{uuid.uuid4().hex[:8]}", name="PM Engineer", initials="PM",
            )
            cls.gen_client = app_module.Client(name=f"Genoray PM Client {uuid.uuid4().hex[:8]}")
            cls.other_client = app_module.Client(name=f"Other PM Client {uuid.uuid4().hex[:8]}")
            app_module.db.session.add_all([
                cls.admin, cls.superadmin, cls.engineer_user, cls.other_user, cls.inactive_admin,
                cls.engineer, cls.gen_client, cls.other_client,
            ])
            app_module.db.session.flush()
            cls.gen_item = app_module.GenorayItem(
                serial_number=f"GEN-PM-{uuid.uuid4().hex[:8]}".upper(), name="Genoray PM Unit",
                bsid="G-PM-1", client_id=cls.gen_client.id,
            )
            cls.view_item = app_module.VieworksItem(
                serial_number=f"VIEW-PM-{uuid.uuid4().hex[:8]}".upper(), name="Vieworks PM Unit",
                bsid="V-PM-1", client_id=cls.gen_client.id,
            )
            cls.product = app_module.Product(
                serial_number=f"PRODUCT-PM-{uuid.uuid4().hex[:8]}".upper(), name="  genoray pm unit  ",
                client_id=cls.gen_client.id,
            )
            cls.view_product = app_module.Product(
                serial_number=f"PRODUCT-VIEW-PM-{uuid.uuid4().hex[:8]}".upper(), name=" Vieworks PM Unit ",
                client_id=cls.gen_client.id,
            )
            app_module.db.session.add_all([cls.gen_item, cls.view_item, cls.product, cls.view_product])
            app_module.db.session.commit()
            cls.user_ids = [
                cls.admin.id, cls.superadmin.id, cls.engineer_user.id,
                cls.other_user.id, cls.inactive_admin.id,
            ]
            cls.ids = {
                "admin": cls.admin.id, "superadmin": cls.superadmin.id,
                "engineer": cls.engineer_user.id, "other": cls.other_user.id,
                "inactive": cls.inactive_admin.id,
            }
            cls.gen_serial = cls.gen_item.serial_number
            cls.view_serial = cls.view_item.serial_number
            cls.product_serial = cls.product.serial_number
            cls.view_product_serial = cls.view_product.serial_number
            cls.gen_client_id = cls.gen_client.id
            cls.other_client_id = cls.other_client.id
            cls.engineer_id = cls.engineer.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            app_module.InventoryPmVisit.query.delete()
            for model, identity in (
                (app_module.GenorayItem, cls.gen_serial),
                (app_module.VieworksItem, cls.view_serial),
                (app_module.Product, cls.product_serial),
                (app_module.Product, cls.view_product_serial),
                (app_module.Client, cls.gen_client_id),
                (app_module.Client, cls.other_client_id),
                (app_module.Engineer, cls.engineer_id),
            ):
                row = app_module.db.session.get(model, identity)
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
            app_module.InventoryPmVisit.query.delete()
            app_module.Shift.query.filter(
                app_module.Shift.client_id.in_([self.gen_client_id, self.other_client_id])
            ).delete(synchronize_session=False)
            gen_item = app_module.db.session.get(app_module.GenorayItem, self.gen_serial)
            view_item = app_module.db.session.get(app_module.VieworksItem, self.view_serial)
            if gen_item:
                gen_item.name = "Genoray PM Unit"
                gen_item.client_id = self.gen_client_id
            if view_item:
                view_item.name = "Vieworks PM Unit"
                view_item.client_id = self.gen_client_id
            product = app_module.db.session.get(app_module.Product, self.product_serial)
            view_product = app_module.db.session.get(app_module.Product, self.view_product_serial)
            if product:
                product.name = "  genoray pm unit  "
                product.client_id = self.gen_client_id
            if view_product:
                view_product.name = " Vieworks PM Unit "
                view_product.client_id = self.gen_client_id
            app_module.db.session.commit()

    def client_for(self, user_id):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
        return client

    def make_shift(
        self, *, title="PM test schedule", status="Planned", client_id=None, days=1,
        schedule_type="service", start_date=None, product_id=None,
    ):
        with self.app.app_context():
            selected_date = start_date or (app_module.get_manila_today() + timedelta(days=days))
            start = datetime.combine(selected_date, datetime.min.time()).replace(hour=9)
            shift = app_module.Shift(
                title=title,
                start_time=start,
                end_time=start + timedelta(hours=2),
                engineer_id=self.engineer_id,
                client_id=client_id or self.gen_client_id,
                product_id=product_id if product_id is not None else self.product_serial,
                status=status,
                schedule_type=schedule_type,
            )
            app_module.db.session.add(shift)
            app_module.db.session.commit()
            return shift.id

    def add_legacy_visit(self, *, brand="genoray", serial=None, target_date="2026-01-31"):
        with self.app.app_context():
            visit = app_module.InventoryPmVisit(
                brand=brand,
                equipment_serial=serial or self.gen_serial,
                target_date=app_module.parse_date(target_date),
                shift_id=None,
                cadence=None,
            )
            app_module.db.session.add(visit)
            app_module.db.session.commit()
            return visit.id

    def create_plan(self, client, *, brand="genoray", serial=None, cadence="quarterly", start_date="2026-01-31"):
        return client.post(f"/api/{brand}/pm/visits", json={
            "serial_number": serial or (self.gen_serial if brand == "genoray" else self.view_serial),
            "cadence": cadence,
            "start_date": start_date,
        })

    def visit_dates(self, brand="genoray", serial=None):
        with self.app.app_context():
            rows = app_module.InventoryPmVisit.query.filter_by(
                brand=brand,
                equipment_serial=serial or (self.gen_serial if brand == "genoray" else self.view_serial),
            ).order_by(app_module.InventoryPmVisit.target_date.asc()).all()
            return [(row.target_date.isoformat(), row.cadence) for row in rows]

    def test_additive_migration_adds_cadence_to_legacy_table(self):
        with self.app.app_context():
            app_module.db.session.remove()
            with app_module.db.engine.begin() as connection:
                connection.exec_driver_sql("DROP TABLE IF EXISTS inventory_pm_visit")
                connection.exec_driver_sql("""
                    CREATE TABLE inventory_pm_visit (
                        id INTEGER PRIMARY KEY,
                        brand VARCHAR(20) NOT NULL,
                        equipment_serial VARCHAR(100) NOT NULL,
                        target_date DATE NOT NULL,
                        shift_id INTEGER,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                """)
                connection.exec_driver_sql(
                    "INSERT INTO inventory_pm_visit "
                    "(id, brand, equipment_serial, target_date, created_at, updated_at) "
                    "VALUES (1, 'genoray', ?, '2026-01-31', '2026-01-01', '2026-01-01')",
                    (self.gen_serial,),
                )
            app_module._inventory_pm_visit_table_ready = False
            app_module.ensure_inventory_pm_visit_table()
            columns = {
                row[1] for row in app_module.db.session.execute(
                    app_module.db.text("PRAGMA table_info(inventory_pm_visit)")
                ).fetchall()
            }
            self.assertIn("cadence", columns)
            self.assertIn("plan_key", columns)
            legacy = app_module.db.session.get(app_module.InventoryPmVisit, 1)
            self.assertIsNone(legacy.cadence)
            self.assertIsNone(legacy.plan_key)

    def test_denied_roles_cannot_open_any_pm_surface(self):
        paths = [
            ("/genoray/pm", "GET"), ("/genoray/pm/" + self.gen_serial, "GET"),
            ("/api/genoray/pm", "GET"), ("/api/genoray/pm/visits", "GET"),
            ("/api/genoray/pm/visits", "POST"),
            ("/api/genoray/pm/schedule-options/" + self.gen_serial, "GET"),
            ("/vieworks/pm", "GET"), ("/api/vieworks/pm", "GET"),
            ("/api/vieworks/pm/visits", "GET"),
        ]
        for user_key in ("engineer", "other", "inactive"):
            client = self.client_for(self.ids[user_key])
            for path, method in paths:
                with self.subTest(user=user_key, path=path, method=method):
                    response = client.open(path, method=method, json={})
                    self.assertIn(response.status_code, (302, 403))

    def test_empty_overviews_and_brand_isolation(self):
        client = self.client_for(self.ids["admin"])
        self.assertEqual(client.get("/genoray/pm").status_code, 200)
        self.assertEqual(client.get("/vieworks/pm").status_code, 200)
        self.assertEqual(client.get("/api/genoray/pm").get_json()["visits"], [])
        self.assertEqual(client.get("/api/vieworks/pm").get_json()["visits"], [])
        self.assertEqual(client.get("/api/genoray/pm/items/" + self.gen_serial).get_json()["visits"], [])
        self.assertEqual(client.get("/api/vieworks/pm/items/" + self.view_serial).get_json()["visits"], [])

    def test_navigation_and_product_template_keep_brand_specific_pm_actions(self):
        client = self.client_for(self.ids["admin"])
        navigation = client.get("/").get_data(as_text=True)
        self.assertIn('href="/genoray/pm"', navigation)
        self.assertIn('href="/vieworks/pm"', navigation)
        genoray = client.get("/genoray").get_data(as_text=True)
        self.assertIn('const inventoryPMBaseUrl = "/genoray/pm";', genoray)
        product = client.get("/products_page").get_data(as_text=True)
        self.assertIn('const inventoryPMBaseUrl = "";', product)

    def test_visit_crud_fiscal_boundaries_and_dynamic_schedule_state(self):
        client = self.client_for(self.ids["admin"])
        shift_id = self.make_shift(status="Completed", start_date=date(2026, 4, 2))
        response = self.create_plan(client, cadence="semi_annual", start_date="2026-04-01")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        visit = response.get_json()["created_visits"][0]
        linked = client.put(f"/api/genoray/pm/visits/{visit['id']}", json={"shift_id": shift_id})
        self.assertEqual(linked.status_code, 200, linked.get_data(as_text=True))
        visit = linked.get_json()["visit"]
        self.assertEqual(visit["status"], "Completed")
        self.assertEqual(visit["target_date"], "2026-04-01")
        self.assertEqual(visit["cadence"], "semi_annual")
        self.assertEqual(visit["actual_date"], "2026-04-02")
        self.assertEqual(client.get("/api/genoray/pm").get_json()["fiscal_year"], 2026)
        self.assertEqual(len(client.get("/api/genoray/pm").get_json()["months"]), 12)
        april = client.get("/api/genoray/pm?scheduled_month=April").get_json()
        self.assertEqual(len(april["visits"]), 1)
        self.assertEqual(april["counts"]["total"], 1)

        with self.app.app_context():
            shift = app_module.db.session.get(app_module.Shift, shift_id)
            shift.status = "In Progress"
            app_module.db.session.commit()
        reopened = client.get("/api/genoray/pm/items/" + self.gen_serial).get_json()["visits"][0]
        self.assertEqual(reopened["status"], "Overdue")
        updated = client.put(f"/api/genoray/pm/visits/{visit['id']}", json={"target_date": "2027-03-31"})
        self.assertEqual(updated.status_code, 200, updated.get_data(as_text=True))
        deleted = client.delete(f"/api/genoray/pm/visits/{visit['id']}")
        self.assertEqual(deleted.status_code, 200, deleted.get_data(as_text=True))

    def test_schedule_options_require_service_pm_and_same_owner_and_are_shareable(self):
        client = self.client_for(self.ids["admin"])
        target = date(2026, 4, 15)
        eligible = self.make_shift(title="Preventive Maintenance PM", client_id=self.gen_client_id, start_date=date(2026, 4, 2))
        non_pm = self.make_shift(title="Repair visit", client_id=self.gen_client_id, start_date=date(2026, 4, 3))
        wrong_owner = self.make_shift(title="Preventive Maintenance PM", client_id=self.other_client_id, start_date=date(2026, 4, 4))
        options = client.get(
            "/api/genoray/pm/schedule-options/" + self.gen_serial + "?target_date=" + target.isoformat()
        ).get_json()["schedules"]
        ids = {row["id"] for row in options}
        self.assertIn(eligible, ids)
        self.assertNotIn(non_pm, ids)
        self.assertNotIn(wrong_owner, ids)

        response = self.create_plan(client, cadence="semi_annual", start_date="2026-04-02")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(len(client.get("/api/genoray/pm/items/" + self.gen_serial).get_json()["visits"]), 2)

    def test_recurring_generation_clamps_month_end_and_crosses_fiscal_year(self):
        client = self.client_for(self.ids["admin"])
        quarterly = self.create_plan(client, cadence="quarterly", start_date="2026-12-31")
        self.assertEqual(quarterly.status_code, 200, quarterly.get_data(as_text=True))
        self.assertEqual(
            quarterly.get_json()["created_dates"],
            ["2026-12-31", "2027-03-31", "2027-06-30", "2027-09-30"],
        )
        self.assertEqual({row[1] for row in self.visit_dates()}, {"quarterly"})
        self.assertEqual(
            [d.isoformat() for d in app_module.generate_inventory_pm_dates(date(2024, 8, 31), "semi_annual")],
            ["2024-08-31", "2025-02-28"],
        )
        self.assertEqual(
            [d.isoformat() for d in app_module.generate_inventory_pm_dates(date(2024, 2, 29), "quarterly")],
            ["2024-02-29", "2024-05-29", "2024-08-29", "2024-11-29"],
        )
        self.assertTrue(all(row["shift_id"] is None for row in quarterly.get_json()["created_visits"]))

    def test_new_plan_requires_supported_cadence_and_start_date(self):
        client = self.client_for(self.ids["admin"])
        missing_start = client.post("/api/genoray/pm/visits", json={
            "serial_number": self.gen_serial, "cadence": "quarterly",
        })
        unsupported = client.post("/api/genoray/pm/visits", json={
            "serial_number": self.gen_serial, "cadence": "monthly", "start_date": "2026-01-31",
        })
        self.assertEqual(missing_start.status_code, 400)
        self.assertEqual(unsupported.status_code, 400)
        self.assertEqual(self.visit_dates(), [])

    def test_partial_and_all_duplicate_generation_are_explicit(self):
        client = self.client_for(self.ids["admin"])
        self.add_legacy_visit(target_date="2026-04-30")
        partial = self.create_plan(client, cadence="quarterly", start_date="2026-01-31")
        self.assertEqual(partial.status_code, 200, partial.get_data(as_text=True))
        self.assertEqual(partial.get_json()["skipped_dates"], ["2026-04-30"])
        self.assertEqual(partial.get_json()["created_dates"], ["2026-01-31", "2026-07-31", "2026-10-31"])
        again = self.create_plan(client, cadence="quarterly", start_date="2026-01-31")
        self.assertEqual(again.status_code, 409, again.get_data(as_text=True))
        self.assertEqual(again.get_json().get("skipped_dates"), ["2026-01-31", "2026-04-30", "2026-07-31", "2026-10-31"])
        self.assertEqual(len(self.visit_dates()), 4)

    def test_batch_failure_rolls_back_all_generated_visits(self):
        client = self.client_for(self.ids["admin"])
        with patch.object(app_module.db.session, "add_all", side_effect=RuntimeError("forced batch failure")):
            response = self.create_plan(client, cadence="quarterly", start_date="2026-01-31")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.visit_dates(), [])

    def test_individual_edits_preserve_cadence_and_reject_duplicate_dates(self):
        client = self.client_for(self.ids["admin"])
        created = self.create_plan(client, cadence="quarterly", start_date="2026-01-31")
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        rows = created.get_json()["created_visits"]
        moved = client.put(f"/api/genoray/pm/visits/{rows[0]['id']}", json={"target_date": "2026-02-28"})
        self.assertEqual(moved.status_code, 200, moved.get_data(as_text=True))
        self.assertEqual(moved.get_json()["visit"]["cadence"], "quarterly")
        collision = client.put(f"/api/genoray/pm/visits/{rows[1]['id']}", json={"target_date": "2026-02-28"})
        self.assertEqual(collision.status_code, 409, collision.get_data(as_text=True))
        self.assertEqual(
            self.visit_dates(),
            [("2026-02-28", "quarterly"), ("2026-04-30", "quarterly"), ("2026-07-31", "quarterly"), ("2026-10-31", "quarterly")],
        )
        deleted = client.delete(f"/api/genoray/pm/visits/{rows[2]['id']}")
        self.assertEqual(deleted.status_code, 200, deleted.get_data(as_text=True))
        self.assertEqual(len(self.visit_dates()), 3)

    def test_new_recurring_plan_rows_share_one_plan_key(self):
        client = self.client_for(self.ids["admin"])
        created = self.create_plan(client, cadence="quarterly", start_date="2026-01-31")
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        ids = [row["id"] for row in created.get_json()["created_visits"]]
        with self.app.app_context():
            rows = [app_module.db.session.get(app_module.InventoryPmVisit, visit_id) for visit_id in ids]
            keys = {row.plan_key for row in rows}
        self.assertEqual(len(keys), 1)
        self.assertTrue(next(iter(keys)))

    def test_quarterly_to_semi_annual_rebuild_preserves_earlier_history(self):
        client = self.client_for(self.ids["admin"])
        created = self.create_plan(client, cadence="quarterly", start_date="2026-01-31")
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        rows = created.get_json()["created_visits"]
        old_first_key = rows[0]["plan_key"]
        selected_id = rows[1]["id"]
        rebuilt = client.put(f"/api/genoray/pm/visits/{selected_id}", json={
            "target_date": "2026-05-31", "cadence": "semi_annual",
        })
        self.assertEqual(rebuilt.status_code, 200, rebuilt.get_data(as_text=True))
        body = rebuilt.get_json()
        self.assertEqual(body["visit"]["target_date"], "2026-05-31")
        self.assertEqual(body["visit"]["cadence"], "semi_annual")
        self.assertEqual(body["regenerated_dates"], ["2026-05-31", "2026-11-30"])
        self.assertEqual(body["removed_future_dates"], ["2026-07-31", "2026-10-31"])
        self.assertEqual(self.visit_dates(), [
            ("2026-01-31", "quarterly"), ("2026-05-31", "semi_annual"),
            ("2026-11-30", "semi_annual"),
        ])
        with self.app.app_context():
            earlier = app_module.InventoryPmVisit.query.filter_by(
                brand="genoray", equipment_serial=self.gen_serial, target_date=date(2026, 1, 31)
            ).one()
            rebuilt_rows = app_module.InventoryPmVisit.query.filter_by(
                brand="genoray", equipment_serial=self.gen_serial, plan_key=body["visit"]["plan_key"]
            ).all()
        self.assertEqual(earlier.plan_key, old_first_key)
        self.assertEqual({row.target_date.isoformat() for row in rebuilt_rows}, {"2026-05-31", "2026-11-30"})

    def test_semi_annual_to_quarterly_rebuild_uses_edited_date_as_anchor(self):
        client = self.client_for(self.ids["admin"])
        created = self.create_plan(client, cadence="semi_annual", start_date="2026-01-31")
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        selected_id = created.get_json()["created_visits"][0]["id"]
        rebuilt = client.put(f"/api/genoray/pm/visits/{selected_id}", json={
            "target_date": "2026-02-28", "cadence": "quarterly",
        })
        self.assertEqual(rebuilt.status_code, 200, rebuilt.get_data(as_text=True))
        body = rebuilt.get_json()
        self.assertEqual(body["regenerated_dates"], [
            "2026-02-28", "2026-05-28", "2026-08-28", "2026-11-28",
        ])
        self.assertEqual(body["removed_future_dates"], ["2026-07-31"])
        self.assertEqual(self.visit_dates(), [
            ("2026-02-28", "quarterly"), ("2026-05-28", "quarterly"),
            ("2026-08-28", "quarterly"), ("2026-11-28", "quarterly"),
        ])

    def test_cadence_rebuild_blocks_linked_selected_or_later_visits(self):
        client = self.client_for(self.ids["admin"])
        created = self.create_plan(client, cadence="quarterly", start_date="2026-04-01")
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        rows = created.get_json()["created_visits"]
        selected_shift = self.make_shift(
            title="Preventive Maintenance PM", client_id=self.gen_client_id,
            product_id=self.product_serial, start_date=date(2026, 4, 2),
        )
        linked = client.put(f"/api/genoray/pm/visits/{rows[0]['id']}", json={"shift_id": selected_shift})
        self.assertEqual(linked.status_code, 200, linked.get_data(as_text=True))
        blocked = client.put(f"/api/genoray/pm/visits/{rows[0]['id']}", json={
            "target_date": "2026-04-15", "cadence": "semi_annual",
        })
        self.assertEqual(blocked.status_code, 409, blocked.get_data(as_text=True))
        self.assertIn("protected_visits", blocked.get_json())
        self.assertEqual(self.visit_dates(), [
            ("2026-04-01", "quarterly"), ("2026-07-01", "quarterly"),
            ("2026-10-01", "quarterly"), ("2027-01-01", "quarterly"),
        ])

        with self.app.app_context():
            app_module.InventoryPmVisit.query.delete()
            app_module.db.session.commit()
        created = self.create_plan(client, cadence="quarterly", start_date="2026-01-31")
        rows = created.get_json()["created_visits"]
        later_shift = self.make_shift(
            title="Preventive Maintenance PM", client_id=self.gen_client_id,
            product_id=self.product_serial, start_date=date(2026, 7, 2),
        )
        linked = client.put(f"/api/genoray/pm/visits/{rows[2]['id']}", json={"shift_id": later_shift})
        self.assertEqual(linked.status_code, 200, linked.get_data(as_text=True))
        blocked = client.put(f"/api/genoray/pm/visits/{rows[0]['id']}", json={"cadence": "semi_annual"})
        self.assertEqual(blocked.status_code, 409, blocked.get_data(as_text=True))
        self.assertEqual(self.visit_dates(), [
            ("2026-01-31", "quarterly"), ("2026-04-30", "quarterly"),
            ("2026-07-31", "quarterly"), ("2026-10-31", "quarterly"),
        ])

    def test_cadence_rebuild_rejects_collisions_with_retained_dates(self):
        client = self.client_for(self.ids["admin"])
        retained_id = self.add_legacy_visit(target_date="2026-05-31")
        created = self.create_plan(client, cadence="quarterly", start_date="2026-01-31")
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        selected_id = created.get_json()["created_visits"][0]["id"]
        blocked = client.put(f"/api/genoray/pm/visits/{selected_id}", json={
            "target_date": "2026-05-31", "cadence": "semi_annual",
        })
        self.assertEqual(blocked.status_code, 409, blocked.get_data(as_text=True))
        body = blocked.get_json()
        self.assertIn("conflicting_retained_dates", body)
        self.assertIn("2026-05-31", body["conflicting_retained_dates"])
        self.assertIsNotNone(retained_id)
        self.assertEqual(self.visit_dates(), [
            ("2026-01-31", "quarterly"), ("2026-04-30", "quarterly"),
            ("2026-05-31", None), ("2026-07-31", "quarterly"),
            ("2026-10-31", "quarterly"),
        ])

    def test_cadence_rebuild_rolls_back_update_delete_and_insert_together(self):
        client = self.client_for(self.ids["admin"])
        created = self.create_plan(client, cadence="quarterly", start_date="2026-01-31")
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        rows = created.get_json()["created_visits"]
        old_key = rows[0]["plan_key"]
        with patch.object(app_module.db.session, "add_all", side_effect=RuntimeError("forced rebuild failure")):
            failed = client.put(f"/api/genoray/pm/visits/{rows[0]['id']}", json={
                "target_date": "2026-02-28", "cadence": "semi_annual",
            })
        self.assertEqual(failed.status_code, 500, failed.get_data(as_text=True))
        self.assertEqual(self.visit_dates(), [
            ("2026-01-31", "quarterly"), ("2026-04-30", "quarterly"),
            ("2026-07-31", "quarterly"), ("2026-10-31", "quarterly"),
        ])
        with self.app.app_context():
            self.assertEqual({row.plan_key for row in app_module.InventoryPmVisit.query.all()}, {old_key})

    def test_legacy_row_rebuild_starts_new_plan_without_deleting_ungrouped_rows(self):
        client = self.client_for(self.ids["admin"])
        selected_id = self.add_legacy_visit(target_date="2026-01-31")
        other_id = self.add_legacy_visit(target_date="2026-07-31")
        rebuilt = client.put(f"/api/genoray/pm/visits/{selected_id}", json={
            "target_date": "2026-02-28", "cadence": "semi_annual",
        })
        self.assertEqual(rebuilt.status_code, 200, rebuilt.get_data(as_text=True))
        self.assertEqual(self.visit_dates(), [
            ("2026-02-28", "semi_annual"), ("2026-07-31", None), ("2026-08-28", "semi_annual"),
        ])
        with self.app.app_context():
            other = app_module.db.session.get(app_module.InventoryPmVisit, other_id)
            selected = app_module.db.session.get(app_module.InventoryPmVisit, selected_id)
        self.assertIsNone(other.plan_key)
        self.assertTrue(selected.plan_key)

    def test_unchanged_cadence_keeps_individual_edit_response_shape(self):
        client = self.client_for(self.ids["admin"])
        created = self.create_plan(client, cadence="quarterly", start_date="2026-01-31")
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        rows = created.get_json()["created_visits"]
        old_key = rows[0]["plan_key"]
        updated = client.put(f"/api/genoray/pm/visits/{rows[0]['id']}", json={
            "target_date": "2026-02-28", "cadence": "quarterly",
        })
        self.assertEqual(updated.status_code, 200, updated.get_data(as_text=True))
        self.assertNotIn("regenerated_visits", updated.get_json())
        self.assertEqual(updated.get_json()["visit"]["plan_key"], old_key)
        self.assertEqual(self.visit_dates(), [
            ("2026-02-28", "quarterly"), ("2026-04-30", "quarterly"),
            ("2026-07-31", "quarterly"), ("2026-10-31", "quarterly"),
        ])

    def test_exact_schedule_matching_and_server_link_validation(self):
        client = self.client_for(self.ids["admin"])
        target = "2026-04-15"
        eligible = self.make_shift(title="Preventive Maintenance PM", client_id=self.gen_client_id, start_date=date(2026, 4, 2))
        adjacent = self.make_shift(title="Preventive Maintenance PM", client_id=self.gen_client_id, start_date=date(2026, 5, 2))
        repair = self.make_shift(title="Repair visit", client_id=self.gen_client_id, start_date=date(2026, 4, 3))
        travel = self.make_shift(title="Preventive Maintenance PM", client_id=self.gen_client_id, schedule_type="travel", start_date=date(2026, 4, 4))
        wrong_product = app_module.Product(serial_number=f"WRONG-PM-{uuid.uuid4().hex[:8]}".upper(), name="Other Product", client_id=self.gen_client_id)
        with self.app.app_context():
            app_module.db.session.add(wrong_product)
            app_module.db.session.commit()
            wrong_product_serial = wrong_product.serial_number
        missing_product = self.make_shift(title="Preventive Maintenance PM", client_id=self.gen_client_id, product_id="", start_date=date(2026, 4, 5))
        wrong_product_shift = self.make_shift(title="Preventive Maintenance PM", client_id=self.gen_client_id, product_id=wrong_product_serial, start_date=date(2026, 4, 6))
        other_owner = self.make_shift(title="Preventive Maintenance PM", client_id=self.other_client_id, start_date=date(2026, 4, 7))
        options_response = client.get(f"/api/genoray/pm/schedule-options/{self.gen_serial}?target_date={target}")
        self.assertEqual(options_response.status_code, 200, options_response.get_data(as_text=True))
        option_ids = {row["id"] for row in options_response.get_json()["schedules"]}
        self.assertEqual(option_ids, {eligible})
        for rejected_id in (adjacent, repair, travel, wrong_product_shift, other_owner, missing_product):
            response = client.post(f"/api/genoray/pm/visits", json={
                "serial_number": self.gen_serial,
                "cadence": "semi_annual",
                "start_date": target,
                "shift_id": rejected_id,
            })
            self.assertIn(response.status_code, (400, 409), response.get_data(as_text=True))
        missing_date = client.get(f"/api/genoray/pm/schedule-options/{self.gen_serial}")
        self.assertEqual(missing_date.status_code, 400)
        created = self.create_plan(client, cadence="semi_annual", start_date=target)
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        visit_id = created.get_json()["created_visits"][0]["id"]
        linked = client.put(f"/api/genoray/pm/visits/{visit_id}", json={"shift_id": eligible})
        self.assertEqual(linked.status_code, 200, linked.get_data(as_text=True))
        wrong_month = client.put(f"/api/genoray/pm/visits/{visit_id}", json={"target_date": "2026-05-15", "shift_id": repair})
        self.assertEqual(wrong_month.status_code, 400, wrong_month.get_data(as_text=True))

        with self.app.app_context():
            eligible_row = app_module.db.session.get(app_module.Shift, eligible)
            eligible_row.title = "Preventive Maintenance PM"
            eligible_row.product_id = wrong_product_serial
            app_module.db.session.commit()
        preserved = client.put(f"/api/genoray/pm/visits/{visit_id}", json={"target_date": target})
        self.assertEqual(preserved.status_code, 200, preserved.get_data(as_text=True))
        self.assertEqual(preserved.get_json()["visit"]["shift_id"], eligible)
        options_after_change = client.get(f"/api/genoray/pm/schedule-options/{self.gen_serial}?target_date={target}").get_json()["schedules"]
        self.assertNotIn(eligible, {row["id"] for row in options_after_change})
        unlinked = client.put(f"/api/genoray/pm/visits/{visit_id}", json={"shift_id": None})
        self.assertEqual(unlinked.status_code, 200, unlinked.get_data(as_text=True))
        self.assertIsNone(unlinked.get_json()["visit"]["shift_id"])

    def test_vieworks_recurring_rows_serialize_cadence(self):
        client = self.client_for(self.ids["admin"])
        response = self.create_plan(client, brand="vieworks", cadence="semi_annual", start_date="2026-03-31")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["created_dates"], ["2026-03-31", "2026-09-30"])
        self.assertEqual({row["cadence"] for row in response.get_json()["created_visits"]}, {"semi_annual"})

    def test_vieworks_schedule_matching_uses_vieworks_product_name(self):
        client = self.client_for(self.ids["admin"])
        exact = self.make_shift(
            title="Preventive Maintenance PM", client_id=self.gen_client_id,
            product_id=self.view_product_serial, start_date=date(2026, 4, 2),
        )
        wrong_product = self.make_shift(
            title="Preventive Maintenance PM", client_id=self.gen_client_id,
            product_id=self.product_serial, start_date=date(2026, 4, 3),
        )
        options = client.get(
            f"/api/vieworks/pm/schedule-options/{self.view_serial}?target_date=2026-04-15"
        )
        self.assertEqual(options.status_code, 200, options.get_data(as_text=True))
        option_ids = {row["id"] for row in options.get_json()["schedules"]}
        self.assertEqual(option_ids, {exact})
        self.assertNotIn(wrong_product, option_ids)

    def test_detail_visits_alias_reuses_link_validation(self):
        client = self.client_for(self.ids["admin"])
        non_pm = self.make_shift(title="Repair test schedule", client_id=self.gen_client_id, start_date=date(2026, 4, 11))
        rejected = client.post(
            "/api/genoray/pm/items/" + self.gen_serial + "/visits",
            json={"cadence": "semi_annual", "start_date": "2026-04-11", "shift_id": non_pm},
        )
        self.assertEqual(rejected.status_code, 400, rejected.get_data(as_text=True))

        eligible = self.make_shift(title="Preventive Maintenance PM", client_id=self.gen_client_id, start_date=date(2026, 4, 11))
        created = client.post(
            "/api/genoray/pm/items/" + self.gen_serial + "/visits",
            json={"cadence": "semi_annual", "start_date": "2026-04-11"},
        )
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        visit_id = created.get_json()["created_visits"][0]["id"]
        linked = client.put(f"/api/genoray/pm/visits/{visit_id}", json={"shift_id": eligible})
        self.assertEqual(linked.status_code, 200, linked.get_data(as_text=True))
        detail = client.get("/api/genoray/pm/items/" + self.gen_serial + "/visits")
        self.assertEqual(detail.status_code, 200, detail.get_data(as_text=True))
        self.assertEqual(len(detail.get_json()["visits"]), 2)

    def test_owner_change_warns_and_missing_schedule_keeps_history(self):
        client = self.client_for(self.ids["admin"])
        shift_id = self.make_shift(title="Preventive Maintenance PM", client_id=self.gen_client_id, start_date=date(2026, 4, 12))
        created = client.post(
            "/api/genoray/pm/visits",
            json={"serial_number": self.gen_serial, "cadence": "semi_annual", "start_date": "2026-04-12"},
        )
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        visit_id = created.get_json()["created_visits"][0]["id"]
        linked = client.put(f"/api/genoray/pm/visits/{visit_id}", json={"shift_id": shift_id})
        self.assertEqual(linked.status_code, 200, linked.get_data(as_text=True))

        with self.app.app_context():
            item = app_module.db.session.get(app_module.GenorayItem, self.gen_serial)
            item.client_id = self.other_client_id
            app_module.db.session.commit()
        mismatch = client.get("/api/genoray/pm/items/" + self.gen_serial).get_json()["visits"][0]
        self.assertTrue(mismatch["owner_mismatch"])
        self.assertIn("owner changed", mismatch["mismatch_warning"])

        with self.app.app_context():
            item = app_module.db.session.get(app_module.GenorayItem, self.gen_serial)
            item.client_id = self.gen_client_id
            shift = app_module.db.session.get(app_module.Shift, shift_id)
            app_module.db.session.delete(shift)
            app_module.db.session.commit()
        missing = client.get("/api/genoray/pm/items/" + self.gen_serial).get_json()["visits"][0]
        self.assertIsNone(missing["schedule"])
        self.assertIn(missing["status"], ("Planned", "Overdue"))
        self.assertEqual(client.get("/api/genoray/pm").get_json()["counts"]["total"], 2)

    def test_permitted_schedule_files_are_links_only(self):
        client = self.client_for(self.ids["superadmin"])
        shift_id = self.make_shift(title="Preventive Maintenance PM", status="Completed", client_id=self.gen_client_id, start_date=date(2026, 4, 13))
        with self.app.app_context():
            app_module.db.session.add(app_module.ShiftFile(
                shift_id=shift_id,
                filename="TSR_pm_visibility.pdf",
                original_filename="TSR_pm_visibility.pdf",
            ))
            app_module.db.session.commit()
        created = client.post(
            "/api/genoray/pm/visits",
            json={"serial_number": self.gen_serial, "cadence": "semi_annual", "start_date": "2026-04-13"},
        )
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        visit = created.get_json()["created_visits"][0]
        linked = client.put(f"/api/genoray/pm/visits/{visit['id']}", json={"shift_id": shift_id})
        self.assertEqual(linked.status_code, 200, linked.get_data(as_text=True))
        visit = linked.get_json()["visit"]
        self.assertEqual(visit["status"], "Completed")
        self.assertEqual(len(visit["files"]), 1)
        self.assertTrue(visit["files"][0]["preview_url"].startswith("/preview_tsr_archive"))
        self.assertTrue(visit["files"][0]["download_url"].startswith("/download_tsr_archive"))

    def test_vieworks_serial_change_carries_history_and_blocks_delete(self):
        client = self.client_for(self.ids["admin"])
        created = client.post(
            "/api/vieworks/pm/visits",
            json={"serial_number": self.view_serial, "cadence": "semi_annual", "start_date": "2026-07-01"},
        )
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        new_serial = self.view_serial + "-NEW"
        updated = client.put("/api/vieworks/items/" + self.view_serial, json={
            "serial_number": new_serial, "name": "Renamed Vieworks", "bsid": "V-PM-1",
            "client_id": self.gen_client_id,
        })
        self.assertEqual(updated.status_code, 200, updated.get_data(as_text=True))
        self.assertEqual(len(client.get("/api/vieworks/pm/items/" + new_serial).get_json()["visits"]), 2)
        blocked = client.delete("/api/vieworks/items/" + new_serial)
        self.assertEqual(blocked.status_code, 409, blocked.get_data(as_text=True))

        with self.app.app_context():
            item = app_module.db.session.get(app_module.VieworksItem, new_serial)
            item.serial_number = self.view_serial
            app_module.InventoryPmVisit.query.update({"equipment_serial": self.view_serial})
            app_module.db.session.commit()

    def test_serial_change_carries_history_and_delete_is_blocked(self):
        client = self.client_for(self.ids["admin"])
        created = client.post("/api/genoray/pm/visits", json={
            "serial_number": self.gen_serial, "cadence": "semi_annual", "start_date": "2026-06-01",
        })
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        new_serial = self.gen_serial + "-NEW"
        updated = client.put("/api/genoray/items/" + self.gen_serial, json={
            "serial_number": new_serial, "name": "Renamed Genoray", "bsid": "G-PM-1",
            "client_id": self.gen_client_id,
        })
        self.assertEqual(updated.status_code, 200, updated.get_data(as_text=True))
        self.assertEqual(client.get("/api/genoray/pm/items/" + new_serial).get_json()["visits"].__len__(), 2)
        blocked = client.delete("/api/genoray/items/" + new_serial)
        self.assertEqual(blocked.status_code, 409, blocked.get_data(as_text=True))

        with self.app.app_context():
            item = app_module.db.session.get(app_module.GenorayItem, new_serial)
            item.serial_number = self.gen_serial
            app_module.InventoryPmVisit.query.update({"equipment_serial": self.gen_serial})
            app_module.db.session.commit()

    def test_vieworks_pm_does_not_read_genoray_or_product_visits(self):
        client = self.client_for(self.ids["admin"])
        response = client.post("/api/vieworks/pm/visits", json={
            "serial_number": self.view_serial, "cadence": "semi_annual", "start_date": "2026-07-01",
        })
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(client.get("/api/vieworks/pm").get_json()["visits"][0]["brand"], "vieworks")
        self.assertEqual(client.get("/api/genoray/pm").get_json()["visits"], [])
        self.assertEqual(client.get("/api/vieworks/pm/items/" + self.gen_serial).status_code, 404)


if __name__ == "__main__":
    unittest.main()
