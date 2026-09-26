"""Focused Product/Vieworks linking, permissions, and service-history coverage."""

import json
import io
import os
import pathlib
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_product_history_{uuid.uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(TEST_DB_PATH))
os.environ.setdefault("SECRET_KEY", "product-history-tests")

import app as app_module  # noqa: E402


class ProductVieworksLinkHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=True)
        suffix = uuid.uuid4().hex[:8].upper()
        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_product_contract_column()
            app_module.ensure_genoray_item_table()
            app_module.ensure_vieworks_item_table()
            app_module.ensure_product_vieworks_link_table()
            cls.admin = app_module.User(username=f"history-admin-{suffix}", password="test", role="admin", is_active=True)
            cls.superadmin = app_module.User(username=f"history-superadmin-{suffix}", password="test", role="superadmin", is_active=True)
            cls.engineer_user = app_module.User(username=f"history-engineer-{suffix}", password="test", role="engineer", is_active=True)
            cls.client_one = app_module.Client(name=f"History Center One {suffix}", address="A")
            cls.client_two = app_module.Client(name=f"History Center Two {suffix}", address="B")
            cls.engineer = app_module.Engineer(employee_id=f"HIST-{suffix}", name="History Engineer", initials="HE", user_id=None, branch="Cebu")
            app_module.db.session.add_all([cls.admin, cls.superadmin, cls.engineer_user, cls.client_one, cls.client_two, cls.engineer])
            app_module.db.session.flush()
            cls.engineer.user_id = cls.engineer_user.id
            cls.product = app_module.Product(serial_number=f"PRODUCT-{suffix}", name="Linked Product", client_id=cls.client_one.id)
            cls.vieworks = app_module.VieworksItem(serial_number=f"VIEWORKS-{suffix}", name="Linked Vieworks", client_id=cls.client_one.id, bsid=f"V-{suffix}")
            cls.vieworks_collision = app_module.VieworksItem(serial_number=cls.product.serial_number, name="Vieworks Collision", client_id=cls.client_one.id, bsid=f"VC-{suffix}")
            cls.other_vieworks = app_module.VieworksItem(serial_number=f"VIEWORKS-OTHER-{suffix}", name="Other Vieworks", client_id=cls.client_two.id, bsid=f"VO-{suffix}")
            app_module.db.session.add_all([cls.product, cls.vieworks, cls.vieworks_collision, cls.other_vieworks])
            app_module.db.session.commit()
            cls.admin_id = cls.admin.id
            cls.superadmin_id = cls.superadmin.id
            cls.engineer_user_id = cls.engineer_user.id
            cls.engineer_id = cls.engineer.id
            cls.client_one_id = cls.client_one.id
            cls.client_two_id = cls.client_two.id
            cls.product_serial = cls.product.serial_number
            cls.vieworks_serial = cls.vieworks.serial_number
            cls.other_vieworks_serial = cls.other_vieworks.serial_number
            app_module.SUPERADMIN_USERNAMES.add(cls.superadmin.username.lower())

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            app_module.db.session.remove()
            app_module.db.drop_all()
        try:
            TEST_DB_PATH.unlink(missing_ok=True)
        except OSError:
            pass
        app_module.SUPERADMIN_USERNAMES.discard(cls.superadmin.username.lower())

    def client_for(self, user_id):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def create_linked_engineer_user(self, branch=None, active=True):
        suffix = uuid.uuid4().hex[:8].upper()
        with self.app.app_context():
            user = app_module.User(
                username=f"history-regional-{suffix}",
                password="test",
                role="engineer",
                is_active=active,
            )
            app_module.db.session.add(user)
            app_module.db.session.flush()
            if branch is not None:
                app_module.db.session.add(app_module.Engineer(
                    employee_id=f"HIST-REG-{suffix}",
                    name=f"History Regional {suffix}",
                    initials="HR",
                    branch=branch,
                    user_id=user.id,
                ))
            app_module.db.session.commit()
            return user.id

    def test_regional_engineers_can_add_and_edit_all_inventories_but_not_admin_actions(self):
        for admin_id in (self.admin_id, self.superadmin_id):
            admin_page = self.client_for(admin_id).get("/products_page")
            self.assertEqual(admin_page.status_code, 200)
            self.assertIn("const productCanEdit = true;", admin_page.get_data(as_text=True))
        users = [self.engineer_user_id, self.create_linked_engineer_user("Davao")]
        for index, user_id in enumerate(users):
            client = self.client_for(user_id)
            with self.subTest(user_id=user_id):
                for path in ("/products_page", "/genoray", "/vieworks"):
                    page = client.get(path)
                    self.assertEqual(page.status_code, 200)
                    self.assertIn("const productCanEdit = true;", page.get_data(as_text=True))

                product_serial = f"REGIONAL-PRODUCT-{index}-{uuid.uuid4().hex[:8].upper()}"
                added_product = client.post(
                    "/add_product",
                    json={"serial_number": product_serial, "name": "Regional Product"},
                )
                self.assertEqual(added_product.status_code, 200, added_product.get_data(as_text=True))
                updated_product = client.put(
                    f"/update_product/{product_serial}",
                    json={"serial_number": product_serial, "name": "Regional Product Updated"},
                )
                self.assertEqual(updated_product.status_code, 200, updated_product.get_data(as_text=True))

                genoray_serial = f"REGIONAL-GEN-{index}-{uuid.uuid4().hex[:8].upper()}"
                added_genoray = client.post(
                    "/api/genoray/items",
                    json={"serial_number": genoray_serial, "name": "Regional Genoray"},
                )
                self.assertEqual(added_genoray.status_code, 200, added_genoray.get_data(as_text=True))
                updated_genoray = client.put(
                    f"/api/genoray/items/{genoray_serial}",
                    json={"name": "Regional Genoray Updated"},
                )
                self.assertEqual(updated_genoray.status_code, 200, updated_genoray.get_data(as_text=True))

                vieworks_serial = f"REGIONAL-VIEWORKS-{index}-{uuid.uuid4().hex[:8].upper()}"
                added_vieworks = client.post(
                    "/api/vieworks/items",
                    json={"serial_number": vieworks_serial, "name": "Regional Vieworks"},
                )
                self.assertEqual(added_vieworks.status_code, 200, added_vieworks.get_data(as_text=True))
                updated_vieworks = client.put(
                    f"/api/vieworks/items/{vieworks_serial}",
                    json={"name": "Regional Vieworks Updated"},
                )
                self.assertEqual(updated_vieworks.status_code, 200, updated_vieworks.get_data(as_text=True))

                self.assertEqual(client.delete(f"/delete_product/{product_serial}").status_code, 403)
                self.assertEqual(client.delete(f"/api/genoray/items/{genoray_serial}").status_code, 403)
                self.assertEqual(client.delete(f"/api/vieworks/items/{vieworks_serial}").status_code, 403)
                self.assertEqual(client.post(
                    "/import_products",
                    data={"file": (io.BytesIO(b"Serial Number,Description\nBLOCKED,Nope\n"), "blocked.csv")},
                    content_type="multipart/form-data",
                ).status_code, 403)
                self.assertEqual(client.post(
                    "/genoray/import",
                    data={"file": (io.BytesIO(b"Serial Number,Description\nBLOCKED,Nope\n"), "blocked.csv")},
                    content_type="multipart/form-data",
                ).status_code, 403)
                self.assertEqual(client.post(
                    "/vieworks/import",
                    data={"file": (io.BytesIO(b"Serial Number,Description\nBLOCKED,Nope\n"), "blocked.csv")},
                    content_type="multipart/form-data",
                ).status_code, 403)
                self.assertEqual(client.get("/genoray/pm").status_code, 403)
                self.assertEqual(client.get("/vieworks/pm").status_code, 403)

    def test_manila_unresolved_unsupported_and_inactive_engineers_remain_read_only(self):
        users = [
            self.create_linked_engineer_user("Manila"),
            self.create_linked_engineer_user(None),
            self.create_linked_engineer_user("Unsupported Branch"),
            self.create_linked_engineer_user("Cebu", active=False),
        ]
        with self.app.app_context():
            genoray = app_module.GenorayItem(
                serial_number=f"DENIED-GEN-{uuid.uuid4().hex[:8].upper()}",
                name="Denied Genoray",
            )
            app_module.db.session.add(genoray)
            app_module.db.session.commit()
            denied_genoray_serial = genoray.serial_number

        for user_id in users:
            client = self.client_for(user_id)
            inactive = user_id == users[-1]
            with self.subTest(user_id=user_id):
                with self.app.app_context():
                    user = app_module.db.session.get(app_module.User, user_id)
                    self.assertFalse(app_module.can_manage_regional_inventory_as_engineer(user))
                for path in ("/products_page", "/genoray", "/vieworks"):
                    page = client.get(path)
                    self.assertEqual(page.status_code, 302 if inactive else 200)
                    if not inactive:
                        self.assertIn("const productCanEdit = false;", page.get_data(as_text=True))
                expected_denied = 302 if inactive else 403
                self.assertEqual(client.post("/add_product", json={"serial_number": "DENIED", "name": "Nope"}).status_code, expected_denied)
                self.assertEqual(client.put(
                    f"/update_product/{self.product_serial}",
                    json={"serial_number": self.product_serial, "name": "Nope"},
                ).status_code, expected_denied)
                self.assertEqual(client.post("/api/genoray/items", json={"serial_number": "DENIED-GEN-NEW", "name": "Nope"}).status_code, expected_denied)
                self.assertEqual(client.put(
                    f"/api/genoray/items/{denied_genoray_serial}",
                    json={"name": "Nope"},
                ).status_code, expected_denied)
                self.assertEqual(client.post("/api/vieworks/items", json={"serial_number": "DENIED-VIEWORKS", "name": "Nope"}).status_code, expected_denied)
                self.assertEqual(client.put(
                    f"/api/vieworks/items/{self.vieworks_serial}",
                    json={"name": "Nope"},
                ).status_code, expected_denied)

        with self.app.app_context():
            self.assertEqual(app_module.db.session.get(app_module.Product, self.product_serial).name, "Linked Product")
            self.assertEqual(app_module.db.session.get(app_module.VieworksItem, self.vieworks_serial).name, "Linked Vieworks")
            self.assertEqual(app_module.db.session.get(app_module.GenorayItem, denied_genoray_serial).name, "Denied Genoray")

    def test_same_client_links_and_parent_serialization(self):
        client = self.client_for(self.admin_id)
        with self.app.app_context():
            self.assertIsNotNone(app_module.db.session.get(app_module.VieworksItem, self.vieworks_serial))
            self.assertIsNone(app_module.validate_product_vieworks_links(self.client_one_id, [self.vieworks_serial]))
        linked_serial = f'LINKED-{self.product_serial}'
        response = client.post(
            '/add_product',
            json={
                'serial_number': linked_serial,
                'name': 'Linked Product',
                'client_id': self.client_one_id,
                'with_vieworks_canon': True,
                'linked_vieworks_serials': [self.vieworks_serial],
            },
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        with self.app.app_context():
            self.assertIsNotNone(app_module.ProductVieworksLink.query.filter_by(
                product_serial=linked_serial.upper(),
                vieworks_serial=self.vieworks_serial,
            ).first())
        product_payload = client.get('/get_products').get_json()
        linked = next(row for row in product_payload if row['serial_number'] == linked_serial.upper())
        self.assertTrue(linked['with_vieworks_canon'])
        self.assertEqual(linked['linked_vieworks'][0]['serial_number'], self.vieworks_serial)
        vieworks_payload = client.get('/api/vieworks/items').get_json()
        parent = next(row for row in vieworks_payload if row['serial_number'] == self.vieworks_serial)['linked_product']
        self.assertEqual(parent['serial_number'], linked_serial.upper())

        expanded = client.put(
            f'/update_product/{linked_serial.upper()}',
            json={
                'serial_number': linked_serial.upper(),
                'name': 'Linked Product',
                'client_id': self.client_one_id,
                'with_vieworks_canon': True,
                'linked_vieworks_serials': [self.vieworks_serial, self.product_serial],
            },
        )
        self.assertEqual(expanded.status_code, 200, expanded.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(
                app_module.ProductVieworksLink.query.filter_by(product_serial=linked_serial.upper()).count(),
                2,
            )

        conflict = client.post(
            '/add_product',
            json={
                'serial_number': f'CONFLICT-{self.product_serial}',
                'name': 'Conflicting Product',
                'client_id': self.client_one_id,
                'with_vieworks_canon': True,
                'linked_vieworks_serials': [self.vieworks_serial],
            },
        )
        self.assertEqual(conflict.status_code, 400)

    def test_serial_rename_scopes_schedules_and_cleans_links(self):
        client = self.client_for(self.admin_id)
        old_product_serial = f'LINKED-{self.product_serial}'
        new_product_serial = f'RENAMED-{self.product_serial}'
        with self.app.app_context():
            colliding_vieworks = app_module.VieworksItem(
                serial_number=old_product_serial,
                name='Vieworks/Product Collision',
                client_id=self.client_one_id,
                bsid=f'COLLIDE-{self.product_serial}',
            )
            gen_serial = f'GEN-SCOPE-{self.product_serial}'
            colliding_genoray = app_module.GenorayItem(
                serial_number=gen_serial,
                name='Genoray/Product Collision',
                client_id=self.client_one_id,
                bsid=f'GEN-COLLIDE-{self.product_serial}',
            )
            genoray_shift = app_module.Shift(
                title='Genoray Schedule', start_time=datetime(2026, 9, 22, 12), end_time=datetime(2026, 9, 22, 13),
                engineer_id=self.engineer_id, client_id=self.client_one_id,
                product_id=gen_serial, equipment_source='genoray', status='Completed',
            )
            genoray_collision_shift = app_module.Shift(
                title='Genoray Product Collision Schedule', start_time=datetime(2026, 9, 22, 14), end_time=datetime(2026, 9, 22, 15),
                engineer_id=self.engineer_id, client_id=self.client_one_id,
                product_id=gen_serial, equipment_source='product', status='Completed',
            )
            product_shift = app_module.Shift(
                title='Product Schedule', start_time=datetime(2026, 9, 22, 8), end_time=datetime(2026, 9, 22, 9),
                engineer_id=self.engineer_id, client_id=self.client_one_id,
                product_id=old_product_serial, equipment_source='product', status='Completed',
            )
            vieworks_shift = app_module.Shift(
                title='Vieworks Schedule', start_time=datetime(2026, 9, 22, 10), end_time=datetime(2026, 9, 22, 11),
                engineer_id=self.engineer_id, client_id=self.client_one_id,
                product_id=old_product_serial, equipment_source='vieworks', status='Completed',
            )
            product_collision_shift = app_module.Shift(
                title='Product Collision Schedule', start_time=datetime(2026, 9, 22, 16), end_time=datetime(2026, 9, 22, 17),
                engineer_id=self.engineer_id, client_id=self.client_one_id,
                product_id=self.product_serial, equipment_source='product', status='Completed',
            )
            app_module.db.session.add_all([
                colliding_vieworks, colliding_genoray, product_shift, vieworks_shift,
                product_collision_shift,
                genoray_shift, genoray_collision_shift,
            ])
            app_module.db.session.commit()

        renamed_product = client.put(
            f'/update_product/{old_product_serial.upper()}',
            json={
                'serial_number': new_product_serial,
                'name': 'Linked Product',
                'client_id': self.client_one_id,
                'with_vieworks_canon': True,
                'linked_vieworks_serials': [self.vieworks_serial, self.product_serial],
            },
        )
        self.assertEqual(renamed_product.status_code, 200, renamed_product.get_data(as_text=True))
        with self.app.app_context():
            self.assertIsNone(app_module.db.session.get(app_module.Product, old_product_serial))
            self.assertIsNotNone(app_module.db.session.get(app_module.Product, new_product_serial))
            product_shift_row = app_module.Shift.query.filter_by(title='Product Schedule').one()
            vieworks_shift_row = app_module.Shift.query.filter_by(title='Vieworks Schedule').one()
            self.assertEqual(product_shift_row.product_id, new_product_serial)
            self.assertEqual(vieworks_shift_row.product_id, old_product_serial)

        renamed_genoray_serial = f'GEN-SCOPE-RENAMED-{self.product_serial}'
        renamed_genoray = client.put(
            f'/api/genoray/items/{gen_serial}',
            json={
                'serial_number': renamed_genoray_serial,
                'name': 'Genoray Collision Renamed',
                'client_id': self.client_one_id,
                'bsid': f'GEN-RENAMED-{self.product_serial}',
            },
        )
        self.assertEqual(renamed_genoray.status_code, 200, renamed_genoray.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(app_module.Shift.query.filter_by(title='Genoray Schedule').one().product_id, renamed_genoray_serial)
            self.assertEqual(
                app_module.Shift.query.filter_by(title='Genoray Product Collision Schedule').one().product_id,
                gen_serial,
            )

        renamed_vieworks_serial = f'VIEWORKS-RENAMED-{self.product_serial}'
        renamed_vieworks = client.put(
            f'/api/vieworks/items/{self.product_serial}',
            json={
                'serial_number': renamed_vieworks_serial,
                'name': 'Vieworks Collision Renamed',
                'client_id': self.client_one_id,
                'bsid': f'VC-RENAMED-{self.product_serial}',
            },
        )
        self.assertEqual(renamed_vieworks.status_code, 200, renamed_vieworks.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(
                app_module.ProductVieworksLink.query.filter_by(vieworks_serial=renamed_vieworks_serial).count(),
                1,
            )
            source_scoped_vieworks = app_module.Shift.query.filter_by(title='Vieworks Visit').first()
            if source_scoped_vieworks:
                self.assertEqual(source_scoped_vieworks.product_id, renamed_vieworks_serial)
            self.assertEqual(
                app_module.Shift.query.filter_by(title='Product Collision Schedule').one().product_id,
                self.product_serial,
            )

        with self.app.app_context():
            self.assertTrue(app_module.is_superadmin_user(app_module.db.session.get(app_module.User, self.superadmin_id)))
        deleted_product = self.client_for(self.superadmin_id).delete(f'/delete_product/{new_product_serial}')
        self.assertEqual(deleted_product.status_code, 200, deleted_product.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(app_module.ProductVieworksLink.query.filter_by(product_serial=new_product_serial).count(), 0)
            self.assertIsNotNone(app_module.db.session.get(app_module.VieworksItem, self.vieworks_serial))

        deleted_vieworks = client.delete(f'/api/vieworks/items/{renamed_vieworks_serial}')
        self.assertEqual(deleted_vieworks.status_code, 200, deleted_vieworks.get_data(as_text=True))

    def test_link_validation_and_clearing(self):
        client = self.client_for(self.admin_id)
        mismatch = client.put(
            f'/update_product/{self.product_serial}',
            json={
                'serial_number': self.product_serial,
                'name': 'Linked Product',
                'client_id': self.client_two_id,
                'with_vieworks_canon': True,
                'linked_vieworks_serials': [self.vieworks_serial],
            },
        )
        self.assertEqual(mismatch.status_code, 400)
        missing_selection = client.put(
            f'/update_product/{self.product_serial}',
            json={
                'serial_number': self.product_serial,
                'name': 'Linked Product',
                'client_id': self.client_one_id,
                'with_vieworks_canon': True,
                'linked_vieworks_serials': [],
            },
        )
        self.assertEqual(missing_selection.status_code, 400)
        clear = client.put(
            f'/update_product/{self.product_serial}',
            json={
                'serial_number': self.product_serial,
                'name': 'Linked Product',
                'client_id': self.client_one_id,
                'with_vieworks_canon': False,
                'linked_vieworks_serials': [],
            },
        )
        self.assertEqual(clear.status_code, 200, clear.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(app_module.ProductVieworksLink.query.filter_by(product_serial=self.product_serial).count(), 0)

    def test_history_is_source_scoped_and_groups_parts(self):
        with self.app.app_context():
            base = datetime(2026, 9, 20, 8, 0)
            first = app_module.Shift(
                title='Preventive Maintenance', start_time=base, end_time=base + timedelta(hours=2),
                engineer_id=self.engineer_id, client_id=self.client_one_id,
                product_id=self.product_serial, equipment_source='product', status='Completed', group_id='HIST-GROUP',
            )
            second = app_module.Shift(
                title='Preventive Maintenance', start_time=base + timedelta(days=1), end_time=base + timedelta(days=1, hours=2),
                engineer_id=self.engineer_id, client_id=self.client_one_id,
                product_id=self.product_serial, equipment_source='product', status='Completed', group_id='HIST-GROUP',
            )
            other = app_module.Shift(
                title='Vieworks Visit', start_time=base, end_time=base + timedelta(hours=1),
                engineer_id=self.engineer_id, client_id=self.client_one_id,
                product_id=self.product_serial, equipment_source='vieworks', status='Completed', group_id=None,
            )
            app_module.db.session.add_all([first, second, other])
            app_module.db.session.flush()
            first_submission = app_module.OnlineTsrSubmission(
                shift_id=first.id, payload_json=json.dumps({'parts': [{'item': 'Old part', 'qty': '1'}]}),
                revision_no=1, is_latest=False, status='received',
            )
            latest_submission = app_module.OnlineTsrSubmission(
                shift_id=second.id, payload_json=json.dumps({'parts': [{'item': 'New part', 'number': 'NP-1', 'qty': '2'}]}),
                revision_no=2, is_latest=True, status='received',
            )
            first.files.append(app_module.ShiftFile(filename='TSR_old.pdf'))
            second.files.append(app_module.ShiftFile(filename='TSR_new.pdf'))
            app_module.db.session.add_all([first_submission, latest_submission])
            first_id, second_id = first.id, second.id
            app_module.db.session.commit()
        client = self.client_for(self.engineer_user_id)
        product_history = client.get(f'/api/products/{self.product_serial}/history')
        self.assertEqual(product_history.status_code, 200, product_history.get_data(as_text=True))
        product_data = product_history.get_json()
        self.assertEqual(len(product_data['visits']), 1)
        self.assertEqual(product_data['visits'][0]['shift_ids'], [first_id, second_id])
        self.assertEqual(product_data['visits'][0]['parts_supplied'][0]['number'], 'NP-1')
        self.assertEqual(product_data['visits'][0]['artifacts'][0]['category'], 'tsr')
        self.assertEqual(product_data['visits'][0]['engineer_names'], ['History Engineer'])
        vieworks_history = client.get(f'/api/vieworks/items/{self.product_serial}/history')
        self.assertEqual(vieworks_history.status_code, 200)
        self.assertEqual(len(vieworks_history.get_json()['visits']), 1)


if __name__ == '__main__':
    unittest.main()
