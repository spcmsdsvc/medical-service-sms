import pathlib
import json
import os
import tempfile
import unittest
from datetime import date
from types import SimpleNamespace

from sqlalchemy import create_engine

try:
    import app as app_module
except Exception as import_error:  # pragma: no cover - dependency-safe source runs
    app_module = None
    APP_IMPORT_ERROR = import_error
else:
    APP_IMPORT_ERROR = None


ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / 'app.py').read_text(encoding='utf-8')
TEMPLATE = (ROOT / 'templates' / 'reimbursement.html').read_text(encoding='utf-8')
RELEASES = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))


class ReimbursementManualCategorySourceTests(unittest.TestCase):
    def test_form_and_worksheet_contract_are_category_aware(self):
        for token in (
            'id="reimManualCategory"',
            'Please select an expense category.',
            'class="reim-manual-category"',
            'handleManualReimbursementCategoryChange',
            "category,",
            "category: payloadRow.manual ?",
            'reimbursementManualCategoryOptions',
            "'category': reimbursement_manual_category_from_amounts(amounts, effective_total)",
        ):
            self.assertIn(token, TEMPLATE if token != "'category': reimbursement_manual_category_from_amounts(amounts, effective_total)" else APP_SOURCE)

        for label in (
            'Representation',
            'Car Repair',
            'Toll Fee',
            'Gasoline',
            'Transpo',
            'Office/Field Items',
            'Parking',
            'Per Diem',
            'Coding',
            'Others',
        ):
            self.assertIn(label, TEMPLATE)

    def test_backend_keeps_mapping_reimbursement_local_and_legacy_others(self):
        self.assertIn('REIMBURSEMENT_MANUAL_CATEGORY_FIELDS', APP_SOURCE)
        self.assertIn("'coding': 'parking_coding'", APP_SOURCE)
        self.assertIn("'others': 'others_misc'", APP_SOURCE)
        self.assertIn('ReimbursementManualPayloadError', APP_SOURCE)
        self.assertIn("category_present = any(key in row_payload for key in ('category', 'manual_category'))", APP_SOURCE)

    @unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
    def test_all_ten_categories_write_one_canonical_component(self):
        expected = app_module.REIMBURSEMENT_MANUAL_CATEGORY_FIELDS
        for category, field in expected.items():
            amounts, total = app_module.reimbursement_manual_payload_amounts(
                {
                    'category': category,
                    'amount': '1250.50',
                    'amounts': {field: '1250.50'},
                },
                category,
                explicit_category=True,
            )
            self.assertEqual(total, 1250.50)
            self.assertEqual(amounts[field], 1250.50)
            self.assertEqual(
                [name for name, value in amounts.items() if value > 0],
                [field],
            )

    @unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
    def test_missing_category_preserves_original_others_payload(self):
        amounts, total = app_module.reimbursement_manual_payload_amounts(
            {'amount': 80, 'amounts': {'others': 80, 'others_misc': 80}},
            'others',
            explicit_category=False,
        )
        self.assertEqual(total, 80.0)
        self.assertEqual(amounts['others_misc'], 80.0)
        self.assertEqual(sum(amounts.values()), 80.0)

    @unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
    def test_invalid_explicit_category_amount_and_ambiguity_are_rejected(self):
        cases = (
            ({'category': 'not-a-category', 'amount': 20}, 'category'),
            ({'category': 'parking', 'amount': -20}, 'price'),
            ({'category': 'parking', 'amount': 'NaN'}, 'price'),
            ({'category': 'parking', 'amount': 20, 'amounts': {'parking': 20, 'transpo': 10}}, 'multiple'),
        )
        for payload, expected_text in cases:
            with self.subTest(payload=payload):
                if payload.get('category') == 'not-a-category':
                    category = None
                else:
                    category = app_module.reimbursement_normalize_manual_category(payload['category'])
                with self.assertRaises(app_module.ReimbursementManualPayloadError) as raised:
                    app_module.reimbursement_manual_payload_amounts(
                        payload,
                        category,
                        explicit_category=True,
                    )
                self.assertIn(expected_text, str(raised.exception).lower())

    @unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
    def test_category_inference_and_receipt_fallback_use_total(self):
        self.assertEqual(
            app_module.reimbursement_manual_category_from_amounts({'parking': 20}),
            'parking',
        )
        self.assertEqual(
            app_module.reimbursement_manual_category_from_amounts({'others_misc': 20}),
            'others',
        )

        first = SimpleNamespace(
            row_date=date(2026, 9, 6),
            task_name='Taxi to client',
            row_total=120,
            parking=120,
            others_misc=0,
            representation=0,
            car_repair=0,
            toll_fee=0,
            gasoline=0,
            transpo=0,
            office_supplies=0,
            per_diem=0,
            parking_coding=0,
        )
        second = SimpleNamespace(
            row_date=date(2026, 9, 6),
            task_name='Taxi to client',
            row_total=120,
            parking=0,
            others_misc=120,
            representation=0,
            car_repair=0,
            toll_fee=0,
            gasoline=0,
            transpo=0,
            office_supplies=0,
            per_diem=0,
            parking_coding=0,
        )
        self.assertEqual(
            app_module.reimbursement_manual_receipt_match_key_from_row(first),
            app_module.reimbursement_manual_receipt_match_key_from_row(second),
        )

    @unittest.skipUnless(app_module is not None, f'app dependencies unavailable: {APP_IMPORT_ERROR}')
    def test_save_reload_category_change_preserves_receipt_and_invalid_rolls_back(self):
        file_handle, database_path = tempfile.mkstemp(suffix='.db')
        os.close(file_handle)
        try:
            with app_module.app.app_context():
                extension = app_module.app.extensions['sqlalchemy']
                engines = extension._app_engines[app_module.app]
                original_engine = engines[None]
                original_lpr_tables_ready = app_module._lpr_tables_ready
                test_engine = create_engine(f"sqlite:///{database_path.replace(os.sep, '/')}")
                try:
                    engines[None] = test_engine
                    app_module._lpr_tables_ready = False
                    app_module.db.create_all()
                    user = app_module.User(
                        username='manual-category-owner',
                        password='test-only',
                        role='engineer',
                        is_active=True,
                    )
                    app_module.db.session.add(user)
                    app_module.db.session.flush()
                    engineer = app_module.Engineer(
                        user_id=user.id,
                        employee_id='MANUAL-CATEGORY-1',
                        name='Manual Category Owner',
                        initials='MCO',
                    )
                    app_module.db.session.add(engineer)
                    app_module.db.session.flush()
                    header = app_module.ReimbursementHeader(
                        user_id=user.id,
                        engineer_id=engineer.id,
                        start_date=date(2026, 9, 1),
                        end_date=date(2026, 9, 30),
                        status='Draft',
                    )
                    app_module.db.session.add(header)
                    app_module.db.session.flush()
                    row = app_module.ReimbursementRow(
                        reimbursement_id=header.id,
                        row_date=date(2026, 9, 6),
                        task_name='Taxi to client',
                        others_misc=80,
                        row_total=80,
                    )
                    second_row = app_module.ReimbursementRow(
                        reimbursement_id=header.id,
                        row_date=date(2026, 9, 6),
                        task_name='Taxi to client',
                        others_misc=80,
                        row_total=80,
                    )
                    app_module.db.session.add_all([row, second_row])
                    app_module.db.session.flush()
                    receipt = app_module.ReimbursementReceipt(
                        reimbursement_id=header.id,
                        shift_id=-row.id,
                        uploaded_by_id=user.id,
                        stored_filename='manual-category-receipt.png',
                        original_filename='taxi.png',
                        content_type='image/png',
                        file_size=3,
                    )
                    second_receipt = app_module.ReimbursementReceipt(
                        reimbursement_id=header.id,
                        shift_id=-second_row.id,
                        uploaded_by_id=user.id,
                        stored_filename='manual-category-receipt-2.png',
                        original_filename='taxi-2.png',
                        content_type='image/png',
                        file_size=3,
                    )
                    app_module.db.session.add_all([receipt, second_receipt])
                    app_module.db.session.commit()
                    old_row_id = row.id
                    old_second_row_id = second_row.id

                    client = app_module.app.test_client()
                    with client.session_transaction() as session:
                        session['_user_id'] = str(user.id)
                        session['_fresh'] = True

                    valid_payload = {
                        'id': header.id,
                        'start': '2026-09-01',
                        'end': '2026-09-30',
                        'rows': [
                            {
                                'manual': True,
                                'manual_key': f'manual_{old_row_id}',
                                'date': '2026-09-06',
                                'item_name': 'Taxi to client',
                                'category': 'parking',
                                'amount': 80,
                                'amounts': {'parking': 80, 'others': 0, 'others_misc': 0},
                            },
                            {
                                'manual': True,
                                'manual_key': f'manual_{old_second_row_id}',
                                'date': '2026-09-06',
                                'item_name': 'Taxi to client',
                                'category': 'transpo',
                                'amount': 80,
                                'amounts': {'transpo': 80, 'others': 0, 'others_misc': 0},
                            },
                        ],
                        'excluded_rows': [],
                    }
                    response = client.post('/save_reimbursement_draft', json=valid_payload)
                    self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
                    saved_rows = app_module.ReimbursementRow.query.filter_by(
                        reimbursement_id=header.id, shift_id=None
                    ).all()
                    self.assertEqual(len(saved_rows), 2)
                    saved_parking = next(item for item in saved_rows if item.parking == 80)
                    saved_transpo = next(item for item in saved_rows if item.transpo == 80)
                    self.assertEqual(saved_parking.others_misc, 0)
                    self.assertEqual(saved_transpo.others_misc, 0)
                    self.assertEqual(
                        app_module.reimbursement_row_to_dict(saved_parking)['category'],
                        'parking',
                    )
                    self.assertEqual(
                        app_module.reimbursement_row_to_dict(saved_transpo)['category'],
                        'transpo',
                    )
                    receipt_links = {
                        item.original_filename: item.shift_id
                        for item in app_module.ReimbursementReceipt.query.filter_by(
                            reimbursement_id=header.id
                        ).all()
                    }
                    self.assertEqual(receipt_links['taxi.png'], -saved_parking.id)
                    self.assertEqual(receipt_links['taxi-2.png'], -saved_transpo.id)

                    invalid_payload = dict(valid_payload)
                    invalid_payload['rows'] = [{
                        **valid_payload['rows'][0],
                        'category': 'not-a-category',
                    }, valid_payload['rows'][1]]
                    response = client.post('/save_reimbursement_draft', json=invalid_payload)
                    self.assertEqual(response.status_code, 400, response.get_data(as_text=True))
                    self.assertTrue(response.get_json().get('category_error'))
                    retained_rows = app_module.ReimbursementRow.query.filter_by(
                        reimbursement_id=header.id, shift_id=None
                    ).all()
                    retained_parking = next(item for item in retained_rows if item.parking == 80)
                    retained_transpo = next(item for item in retained_rows if item.transpo == 80)
                    self.assertEqual(retained_parking.id, saved_parking.id)
                    self.assertEqual(retained_transpo.id, saved_transpo.id)
                    receipt_links = {
                        item.original_filename: item.shift_id
                        for item in app_module.ReimbursementReceipt.query.filter_by(
                            reimbursement_id=header.id
                        ).all()
                    }
                    self.assertEqual(receipt_links['taxi.png'], -saved_parking.id)
                    self.assertEqual(receipt_links['taxi-2.png'], -saved_transpo.id)
                finally:
                    app_module.db.session.remove()
                    engines[None] = original_engine
                    app_module._lpr_tables_ready = original_lpr_tables_ready
                    test_engine.dispose()
        finally:
            for suffix in ('', '-wal', '-shm'):
                try:
                    os.unlink(database_path + suffix)
                except OSError:
                    pass

    def test_existing_lpr_and_artifact_paths_consume_component_amounts(self):
        self.assertIn("getattr(row, 'office_supplies', 0)", APP_SOURCE)
        self.assertIn('reimbursement_effective_row_amounts(row)', APP_SOURCE)
        self.assertIn("return reimbursement_total_snapshot(header)['category_totals']", APP_SOURCE)
        self.assertIn('reimbursementOfficeFieldTotal(rowsForSubmit)', TEMPLATE)
        self.assertIn('amounts.parking_coding = amounts.coding || 0;', TEMPLATE)
        self.assertIn('amounts.others_misc = amounts.others || 0;', TEMPLATE)

    def test_manual_category_release_and_cache_are_current(self):
        self.assertIn('medical-service-pwa-offline-navigation-v140-timeline-scroll-legend', APP_SOURCE)
        matches = [
            release for release in RELEASES.get('releases', [])
            if release.get('release_key') == '2026-09-06-reimbursement-manual-categories'
        ]
        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0].get('is_published'))
        self.assertTrue(any(item.get('category') == 'Reimbursement' for item in matches[0].get('items', [])))


if __name__ == '__main__':
    unittest.main()
