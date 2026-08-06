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

            records = [
                app_module.PurchaseOrder(
                    client_id=cls.client_one.id,
                    po_number=f'AN-PO-1-{cls.suffix}',
                    po_date=date(2026, 8, 6),
                    po_type=app_module.PO_TYPE_CONTRACT,
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
                    po_type=app_module.PO_TYPE_CONTRACT,
                ),
            ]
            app_module.db.session.add_all(records)
            app_module.db.session.flush()
            cls.created_po_ids.extend(record.id for record in records)
            app_module.db.session.commit()

            cls.po_user_id = cls.po_user.id
            cls.plain_user_id = cls.plain_user.id
            cls.reports_user_id = cls.reports_user.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            for po_id in cls.created_po_ids:
                record = app_module.db.session.get(app_module.PurchaseOrder, po_id)
                if record:
                    app_module.db.session.delete(record)
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
        self.assertNotIn('Service activity', html)
        self.assertNotIn('Engineer workload', html)

        po_response = client.get('/get_po_analytics?start_date=2026-08-01&end_date=2026-08-31')
        self.assertEqual(po_response.status_code, 200)
        payload = po_response.get_json()
        self.assertEqual(payload['scope_label'], 'Company-wide')
        self.assertEqual(payload['total'], 2)
        self.assertEqual(
            {row['label']: row['count'] for row in payload['by_type']},
            {'Contract': 1, 'Single Visit': 1},
        )
        self.assertNotIn('personnel', payload)

        self.assertEqual(client.get('/get_analytics_summary').status_code, 403)

    def test_plain_user_is_denied_but_reports_user_keeps_schedule_surface(self):
        plain = self._client_for(self.plain_user_id)
        self.assertEqual(plain.get('/analytics_page').status_code, 302)
        self.assertEqual(plain.get('/get_po_analytics').status_code, 403)

        reports = self._client_for(self.reports_user_id)
        self.assertEqual(reports.get('/analytics_page').status_code, 200)
        self.assertEqual(reports.get('/get_analytics_summary').status_code, 200)

    def test_po_source_contract_is_separate_from_schedule_analytics(self):
        source = (Path(self.app.root_path) / 'app.py').read_text(encoding='utf-8')
        self.assertIn("@app.route('/get_po_analytics')", source)
        endpoint = source.split("@app.route('/get_po_analytics')", 1)[1].split("@app.route", 1)[0]
        self.assertIn('can_view_admin_reports() or can_manage_purchase_orders()', endpoint)
        self.assertIn('ensure_purchase_order_schema()', endpoint)


if __name__ == '__main__':
    unittest.main()
