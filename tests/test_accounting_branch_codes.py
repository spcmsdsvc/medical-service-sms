"""Focused contracts for Engineer-profile accounting branch codes."""

import json
import os
import pathlib
import tempfile
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
os.environ.setdefault(
    'MEDICAL_SERVICE_TEST_DB',
    str(pathlib.Path(tempfile.gettempdir()) / f'medical_service_branch_codes_{uuid.uuid4().hex}.db'),
)

import app as app_module  # noqa: E402


class AccountingBranchResolverTests(unittest.TestCase):
    def test_shared_resolver_maps_supported_engineer_labels(self):
        for label, expected in {
            'Manila': 'BC01',
            'Main': 'BC01',
            'Cebu': 'BC02',
            'Davao': 'BC03',
            'BC02': 'BC02',
            'Davao Branch': 'BC03',
            ' dAvAo  branch ': 'BC03',
        }.items():
            self.assertEqual(
                app_module.resolve_engineer_profile_branch_code(SimpleNamespace(branch=label)),
                expected,
            )

    def test_missing_or_unknown_profile_never_defaults(self):
        for label in ('', None, 'Baguio', 'BC99'):
            self.assertEqual(
                app_module.resolve_engineer_profile_branch_code(SimpleNamespace(branch=label)),
                '',
            )

    def test_stored_engineer_link_is_authoritative_and_owner_fallback_is_explicit(self):
        stored = SimpleNamespace(
            engineer_id=22,
            engineer=SimpleNamespace(branch='Cebu'),
            user_id=1,
            requester=SimpleNamespace(engineer_profile=SimpleNamespace(branch='Davao')),
        )
        self.assertEqual(app_module.resolve_accounting_branch_code(stored), 'BC02')

        fallback = SimpleNamespace(
            engineer_id=None,
            user_id=1,
            requester=SimpleNamespace(engineer_profile=SimpleNamespace(branch='Davao')),
        )
        self.assertEqual(app_module.resolve_accounting_branch_code(fallback), 'BC03')


class AccountingPayloadAndUIContractsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.travel_template = (ROOT / 'templates' / 'travel_liquidation.html').read_text(encoding='utf-8')
        cls.cash_template = (ROOT / 'templates' / 'cash_advance_liquidation.html').read_text(encoding='utf-8')
        cls.releases = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))

    def test_legacy_client_branch_is_accepted_but_ignored(self):
        travel = app_module.travel_liquidation_parse_row_payload(
            {'branch_code': 'BC01', 'amount': '10'},
            authoritative_branch_code='BC02',
        )
        cash = app_module.cash_advance_liquidation_parse_row_payload(
            {'branch_code': 'BC01', 'amount': '10'},
            authoritative_branch_code='BC03',
        )
        self.assertEqual(travel['branch_code'], 'BC02')
        self.assertEqual(cash['branch_code'], 'BC03')
        self.assertEqual(
            app_module.travel_liquidation_parse_row_payload({'branch_code': 'BC01', 'amount': '10'})['branch_code'],
            '',
        )

    def test_authoritative_branch_metadata_and_blocker_contracts_exist(self):
        for token in (
            'resolve_accounting_branch_code',
            'derived_branch_code',
            'require_accounting_branch_code',
            'branch_resolution_error',
            "@app.route('/admin/repair_accounting_branch_codes', methods=['GET', 'POST'])",
            'ACCOUNTING_BRANCH_REPAIR_VERSION',
            "'changed_count': len(repaired)",
        ):
            self.assertIn(token, self.source)
        self.assertIn('readonly aria-readonly="true"', self.travel_template)
        self.assertIn('readonly aria-readonly="true"', self.cash_template)
        self.assertIn('Derived Branch', self.travel_template)
        self.assertIn('Derived Branch', self.cash_template)
        self.assertIn('currentLiquidation?.derived_branch_code', self.travel_template)
        self.assertIn('currentLiquidation?.derived_branch_code', self.cash_template)

    def test_accounting_outputs_do_not_use_branch_one_fallback(self):
        for function_name in (
            'def travel_liquidation_prepare_rfp_field_values',
            'def build_travel_liquidation_form_payload',
            'def cash_advance_liquidation_prepare_rfp_field_values',
            'def build_cash_advance_liquidation_excel_payload',
            'def reimbursement_prepare_rfp_field_values',
        ):
            start = self.source.index(function_name)
            next_def = self.source.find('\ndef ', start + len(function_name))
            block = self.source[start:next_def if next_def > 0 else len(self.source)]
            self.assertNotIn("or 'BC01'", block, function_name)
        self.assertIn("v170-accounting-branch-codes", self.source)

    def test_release_entry_is_present(self):
        self.assertTrue(self.releases)
        newest = self.releases['releases'][0]
        self.assertEqual(newest.get('release_key'), '2026-09-22-calibration-model-approval')
        self.assertIn('temporary model', (newest.get('title') or '').lower())
        accounting_release = next(
            release for release in self.releases['releases']
            if release.get('release_key') == '2026-09-20-accounting-branch-codes'
        )
        self.assertIn('branch', (accounting_release.get('title') or '').lower())

    def test_forms_and_rfps_use_the_creator_branch_for_each_accounting_workflow(self):
        with app_module.app.app_context(), patch.object(app_module, 'travel_liquidation_recalculate_totals'), patch.object(app_module, 'cash_advance_liquidation_recalculate_totals'):
            for branch, expected in (('Manila', 'BC01'), ('Cebu', 'BC02'), ('Davao', 'BC03')):
                owner = SimpleNamespace(engineer_profile=SimpleNamespace(branch=branch))
                travel_row = SimpleNamespace(
                    id=None, actual_amount=100, expense_date=None, sort_order=1,
                    class_code='CC04', dept_code='DC03', product_code='PC18',
                    particulars='Travel', expense_type='Meals', source_currency_code='PHP',
                    source_amount=100, exchange_rate=1, remarks='', planned_amount=0,
                )
                travel = SimpleNamespace(
                    id=None, engineer_id=None, requester=owner, user_id=None, rows=[travel_row],
                    engineer=None, travel_request=SimpleNamespace(
                        currency_code='PHP', purpose='Travel', request_no='TR-1',
                        destination='Cebu', departure_date=None, return_date=None, lines=[],
                    ), currency_code='PHP', usd_to_php_rate=0, cash_advance_amount=0,
                    total_actual_expenses=0, due_to_shimadzu=0, due_to_employee=0,
                    status='Draft', liquidation_no='TL-1', travel_request_id=1,
                    created_at=None, updated_at=None, submitted_at=None, approved_at=None,
                    rejected_at=None, rejected_by_id=None, approved_by_id=None,
                    approval_remarks=None,
                )
                self.assertEqual(
                    app_module.travel_liquidation_prepare_rfp_field_values(travel)['BRANCH'],
                    expected,
                )
                self.assertEqual(
                    app_module.build_travel_liquidation_form_payload(travel)['record']['branch_code'],
                    expected,
                )

                cash_row = SimpleNamespace(
                    id=None, actual_amount=100, expense_date=None, sort_order=1,
                    class_code='CC04', dept_code='DC03', product_code='PC18',
                    particulars='Cash advance', expense_type='Meals', remarks='',
                )
                cash = SimpleNamespace(
                    id=None, engineer_id=None, requester=owner, user_id=None, rows=[cash_row],
                    engineer=None, cash_advance=SimpleNamespace(
                        id=1, cash_advance_no='CA-1', amount_requested=100,
                        approved_amount=100, purpose='Cash advance', user_id=None,
                    ), cash_advance_amount=100, total_actual_expenses=100,
                    due_to_shimadzu=0, due_to_employee=0, status='Draft',
                    liquidation_no='CAL-1', cash_advance_id=1, created_at=None,
                    updated_at=None, submitted_at=None, approved_at=None,
                    approval_name_snapshot='', approval_remarks='',
                )
                self.assertEqual(
                    app_module.cash_advance_liquidation_prepare_rfp_field_values(cash)['BRANCH'],
                    expected,
                )
                self.assertEqual(
                    app_module.build_cash_advance_liquidation_excel_payload(cash)['branch_code'],
                    expected,
                )

    def test_unresolved_creator_blocks_branch_outputs_without_rewriting_legacy_rows(self):
        with app_module.app.app_context():
            owner = SimpleNamespace(engineer_profile=SimpleNamespace(branch='Unknown Office'))
            row = SimpleNamespace(
                id=None, branch_code='BC01', actual_amount=100, expense_date=None,
                sort_order=1, class_code='CC04', dept_code='DC03', product_code='PC18',
                particulars='Legacy', expense_type='Meals', source_currency_code='PHP',
                source_amount=100, exchange_rate=1, remarks='', planned_amount=0,
            )
            travel = SimpleNamespace(
                id=None, engineer_id=None, requester=owner, user_id=None, rows=[row],
                engineer=None, travel_request=None, currency_code='PHP', usd_to_php_rate=0,
                cash_advance_amount=0, total_actual_expenses=0, due_to_shimadzu=0,
                due_to_employee=0, status='Draft', liquidation_no='TL-legacy',
                travel_request_id=1, created_at=None, updated_at=None, submitted_at=None,
                approved_at=None, rejected_at=None, rejected_by_id=None, approved_by_id=None,
                approval_remarks=None,
            )
            with self.assertRaisesRegex(ValueError, 'missing or has an unsupported branch'):
                app_module.travel_liquidation_prepare_rfp_field_values(travel)
            self.assertEqual(row.branch_code, 'BC01')

            cash = SimpleNamespace(
                id=None, engineer_id=None, requester=owner, user_id=None, rows=[row],
                engineer=None, cash_advance=SimpleNamespace(amount_requested=100, purpose='Legacy'),
                cash_advance_amount=100, total_actual_expenses=100, due_to_shimadzu=0,
                due_to_employee=0, status='Draft', liquidation_no='CAL-legacy',
                cash_advance_id=1, created_at=None, updated_at=None, submitted_at=None,
                approved_at=None, approval_name_snapshot='', approval_remarks='',
            )
            with self.assertRaisesRegex(ValueError, 'missing or has an unsupported branch'):
                app_module.cash_advance_liquidation_prepare_rfp_field_values(cash)
            self.assertEqual(row.branch_code, 'BC01')

    def test_repair_scan_reports_workflow_and_target_code_groups(self):
        travel_liquidation = SimpleNamespace(
            engineer_id=None,
            requester=SimpleNamespace(engineer_profile=SimpleNamespace(branch='Cebu')),
            user_id=None,
            status='Approved',
            liquidation_no='TL-1',
        )
        cash_liquidation = SimpleNamespace(
            engineer_id=None,
            requester=SimpleNamespace(engineer_profile=SimpleNamespace(branch='Davao')),
            user_id=None,
            status='Completed',
            liquidation_no='CAL-1',
        )
        travel_row = SimpleNamespace(id=1, liquidation_id=10, branch_code='BC01', liquidation=travel_liquidation)
        cash_row = SimpleNamespace(id=2, liquidation_id=20, branch_code='BC03', liquidation=cash_liquidation)

        class FakeQuery:
            def __init__(self, rows):
                self.rows = rows

            def order_by(self, *_args):
                return self

            def all(self):
                return self.rows

        with app_module.app.app_context(), \
                patch.object(app_module.TravelLiquidationRow, 'query', FakeQuery([travel_row])), \
                patch.object(app_module.CashAdvanceLiquidationRow, 'query', FakeQuery([cash_row])):
            items, summary = app_module._accounting_branch_repair_scan()

        self.assertEqual([item['action'] for item in items], ['repair', 'already_correct'])
        self.assertEqual(summary['by_workflow']['travel_liquidation']['repairable'], 1)
        self.assertEqual(summary['by_target_code']['BC02']['repairable'], 1)
        self.assertEqual(summary['by_target_code']['BC03']['already_correct'], 1)


if __name__ == '__main__':
    unittest.main()
