"""Access and aggregation tests for the Analytics purchase-order panel."""

import unittest
import uuid
from datetime import date
from pathlib import Path

import app as app_module  # noqa: E402


class AnalyticsPurchaseOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.suffix = uuid.uuid4().hex[:10]
        cls.created_user_ids = []
        cls.created_client_ids = []
        cls.created_product_serials = []
        cls.created_po_ids = []

        with cls.app.app_context():
            app_module.db.create_all()
            app_module.ensure_user_admin_capability_columns()
            app_module.ensure_purchase_order_schema()

            def add_user(username, **flags):
                user = app_module.User(
                    username=f'{username}_{cls.suffix}',
                    password=app_module.generate_password_hash('test-password'),
                    role='staff',
                    is_active=True,
                    **flags,
                )
                app_module.db.session.add(user)
                app_module.db.session.flush()
                cls.created_user_ids.append(user.id)
                return user

            cls.po_user = add_user('analytics_po_only', po_admin_access=True)
            cls.plain_user = add_user('analytics_no_access')
            cls.reports_user = add_user('analytics_reports_only', reports_admin_access=True)

            cls.client_one = app_module.Client(
                name=f'Analytics P.O. Client One {cls.suffix}',
                address='P.O. test address one',
            )
            cls.client_two = app_module.Client(
                name=f'Analytics P.O. Client Two {cls.suffix}',
                address='P.O. test address two',
            )
            app_module.db.session.add_all([cls.client_one, cls.client_two])
            app_module.db.session.flush()
            cls.created_client_ids.extend([cls.client_one.id, cls.client_two.id])

            cls.product = app_module.Product(
                serial_number=f'AN-SN-{cls.suffix}',
                name='AN CT-500',
                client_id=cls.client_one.id,
                under_contract=True,
            )
            app_module.db.session.add(cls.product)
            app_module.db.session.flush()
            cls.created_product_serials.append(cls.product.serial_number)

            records = [
                app_module.PurchaseOrder(
                    client_id=cls.client_one.id,
                    po_number=f'AN-PO-1-{cls.suffix}',
                    po_date=date(2026, 8, 6),
                    end_date=date(2026, 12, 31),
                    po_type=app_module.PO_TYPE_CONTRACT,
                    product_serial=cls.product.serial_number,
                ),
                app_module.PurchaseOrder(
                    client_id=cls.client_one.id,
                    po_number=f'AN-PO-2-{cls.suffix}',
                    po_date=date(2026, 8, 7),
                    po_type=app_module.PO_TYPE_SINGLE_VISIT,
                ),
                app_module.PurchaseOrder(
                    client_id=cls.client_two.id,
                    po_number=f'AN-PO-3-{cls.suffix}',
                    po_date=date(2026, 7, 31),
                    end_date=date(2026, 12, 31),
                    po_type=app_module.PO_TYPE_CONTRACT,
                ),
            ]
            app_module.db.session.add_all(records)
            app_module.db.session.flush()
            app_module.apply_purchase_order_machines(records[0], [cls.product.serial_number])
            cls.created_po_ids.extend(record.id for record in records)
            app_module.db.session.commit()

            cls.po_user_id = cls.po_user.id
            cls.plain_user_id = cls.plain_user.id
            cls.reports_user_id = cls.reports_user.id
            cls.product_serial = cls.product.serial_number
            cls.product_name = cls.product.name
            cls.client_one_name = cls.client_one.name

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            for po_id in cls.created_po_ids:
                record = app_module.db.session.get(app_module.PurchaseOrder, po_id)
                if record:
                    app_module.db.session.delete(record)
            for serial_number in cls.created_product_serials:
                product = app_module.db.session.get(app_module.Product, serial_number)
                if product:
                    app_module.db.session.delete(product)
            for client_id in cls.created_client_ids:
                client = app_module.db.session.get(app_module.Client, client_id)
                if client:
                    app_module.db.session.delete(client)
            for user_id in reversed(cls.created_user_ids):
                user = app_module.db.session.get(app_module.User, user_id)
                if user:
                    app_module.db.session.delete(user)
            app_module.db.session.commit()
            app_module.db.session.remove()

    @classmethod
    def _client_for(cls, user_id):
        client = cls.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        return client

    def test_po_only_user_gets_company_counts_but_no_personnel_analytics(self):
        client = self._client_for(self.po_user_id)
        page = client.get('/analytics_page')
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn('Purchase order reporting', html)
        self.assertIn('Equipment', html)
        self.assertIn('data-analytics-panel="equipment"', html)
        self.assertNotIn('Service activity', html)
        self.assertNotIn('Engineer workload', html)
        self.assertNotIn('data-analytics-panel="schedule"', html)

        po_response = client.get('/get_po_analytics?start_date=2026-08-01&end_date=2026-08-31')
        self.assertEqual(po_response.status_code, 200)
        payload = po_response.get_json()
        self.assertEqual(payload['scope_label'], 'Company-wide')
        self.assertEqual(payload['total'], 2)
        self.assertEqual(
            {row['label']: row['count'] for row in payload['by_type']},
            {'Contract': 1, 'Single Visit': 1},
        )
        equipment = payload['equipment']
        self.assertEqual(equipment['linked_total'] + equipment['unlinked_total'], payload['total'])
        self.assertEqual(equipment['linked_total'], 1)
        self.assertEqual(equipment['unlinked_total'], 1)
        self.assertEqual(equipment['linked_pct'], 50)
        self.assertEqual(equipment['machine_link_total'], 1)
        self.assertEqual(equipment['machine_total'], 1)
        self.assertEqual(equipment['client_total'], 1)
        self.assertIn(self.product_serial, equipment['by_machine'][0]['label'])
        self.assertEqual(equipment['by_model'][0]['label'], self.product_name)
        self.assertEqual(equipment['by_coverage'][0]['count'], 1)
        self.assertEqual(sum(row['count'] for row in equipment['by_coverage']), equipment['machine_link_total'])
        self.assertEqual(equipment['unlinked_clients'][0]['label'], self.client_one_name)
        self.assertFalse({'amount', 'total_amount', 'currency'} & set(equipment))
        self.assertNotIn('personnel', payload)

        self.assertEqual(client.get('/get_analytics_summary').status_code, 403)

    def test_equipment_analytics_separates_po_and_machine_link_units(self):
        second_serial = f'AN-SN-SECOND-{self.suffix}'
        with self.app.app_context():
            second = app_module.Product(
                serial_number=second_serial,
                name='AN CT-700',
                client_id=self.client_one.id,
            )
            record = app_module.PurchaseOrder(
                client_id=self.client_one.id,
                po_number=f'AN-PO-MULTI-{self.suffix}',
                po_date=date(2026, 8, 8),
                po_type=app_module.PO_TYPE_SINGLE_VISIT,
                product_serial=self.product.serial_number,
            )
            app_module.db.session.add_all([second, record])
            app_module.db.session.flush()
            app_module.apply_purchase_order_machines(
                record,
                [self.product.serial_number, second_serial],
            )
            app_module.db.session.commit()
            self.created_product_serials.append(second_serial)
            self.created_po_ids.append(record.id)

        client = self._client_for(self.po_user_id)
        response = client.get('/get_po_analytics?start_date=2026-08-01&end_date=2026-08-31')
        self.assertEqual(response.status_code, 200)
        equipment = response.get_json()['equipment']
        self.assertEqual(equipment['linked_total'], 2)
        self.assertEqual(equipment['unlinked_total'], 1)
        self.assertEqual(equipment['machine_link_total'], 3)
        self.assertEqual(equipment['linked_total'] + equipment['unlinked_total'], 3)
        self.assertEqual(sum(row['count'] for row in equipment['by_coverage']), 3)
        machine_counts = {row['label']: row['count'] for row in equipment['by_machine']}
        self.assertEqual(machine_counts[self.product_serial + ' · ' + self.product_name], 2)
        self.assertEqual(machine_counts[second_serial + ' · AN CT-700'], 1)
        with self.app.app_context():
            created_record = app_module.db.session.get(app_module.PurchaseOrder, record.id)
            if created_record:
                app_module.db.session.delete(created_record)
            created_product = app_module.db.session.get(app_module.Product, second_serial)
            if created_product:
                app_module.db.session.delete(created_product)
            app_module.db.session.commit()

    def test_plain_user_is_denied_but_reports_user_keeps_schedule_surface(self):
        plain = self._client_for(self.plain_user_id)
        self.assertEqual(plain.get('/analytics_page').status_code, 302)
        self.assertEqual(plain.get('/get_po_analytics').status_code, 403)

        reports = self._client_for(self.reports_user_id)
        self.assertEqual(reports.get('/analytics_page').status_code, 200)
        self.assertEqual(reports.get('/get_analytics_summary').status_code, 200)

    def test_po_endpoint_serves_both_capabilities_and_nobody_else(self):
        """Called, not read as source.

        This replaced assertIn on the literal gate expression. A pinned rule string cannot
        tell you the rule holds; building each account and calling the route can.
        """
        for user_id, label in (
            (self.po_user_id, 'P.O. capability'),
            (self.reports_user_id, 'reports capability'),
        ):
            client = self._client_for(user_id)
            response = client.get('/get_po_analytics')
            self.assertEqual(response.status_code, 200, f'{label} was refused')
            self.assertEqual(response.get_json()['scope_label'], 'Company-wide')

        # Negative, and the reason the two capabilities are kept separate at all.
        self.assertEqual(
            self._client_for(self.plain_user_id).get('/get_po_analytics').status_code, 403
        )
        self.assertEqual(
            self._client_for(self.po_user_id).get('/get_analytics_summary').status_code, 403
        )


if __name__ == '__main__':
    unittest.main()
