"""Focused contracts for Reimbursement Package 3 worksheet views."""

import json
import pathlib
import re
import subprocess
import textwrap
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "templates" / "reimbursement.html").read_text(encoding="utf-8")
APP_SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")
RELEASES = json.loads((ROOT / "static" / "changelog" / "releases.json").read_text(encoding="utf-8"))


class ReimbursementWorksheetViewTests(unittest.TestCase):
    def test_view_disclosure_has_compact_accessible_overlay_controls(self):
        for token in (
            'id="reimViewToggle"',
            'id="reimViewPopover"',
            'aria-controls="reimViewPopover"',
            'aria-expanded="false"',
            'id="reimViewSearch"',
            'id="reimViewFilter"',
            'id="reimViewCategoryList"',
            'id="reimViewShowAll"',
            'id="reimViewClose"',
            'closeReimbursementViewPopover()',
            'toggleReimbursementViewPopover()',
            'handleReimbursementViewKeydown',
            'reimColumnView',
            'reimZoomLevel',
        ):
            self.assertIn(token, TEMPLATE)
        self.assertEqual(TEMPLATE.count('id="reimViewToggle"'), 1)
        self.assertEqual(TEMPLATE.count('id="reimViewPopover"'), 1)

    def test_view_state_is_page_local_and_reapplies_without_replacing_rows(self):
        for token in (
            "let reimbursementWorksheetViewState",
            "function rowMatchesReimbursementView(row)",
            "function applyReimbursementWorksheetView()",
            "function renderReimbursementWorksheetViewStatus(",
            "data-row-key=",
            "style.display",
            "currentReimbursementRows",
            "collectReimbursementRowsForSave",
            "reimbursementSelectedRowKeys",
        ):
            self.assertIn(token, TEMPLATE)
        self.assertIn("applyReimbursementWorksheetView();", TEMPLATE)
        self.assertIn("Showing ${visible} of ${total} rows", TEMPLATE)

    def test_view_predicate_and_category_visibility_runtime(self):
        view_start = TEMPLATE.index("function reimbursementViewRowText(row)")
        view_end = TEMPLATE.index("\n    function toggleReimbursementViewPopover", view_start)
        view_code = TEMPLATE[view_start:view_end]
        node_script = textwrap.dedent(
            f"""
            const assert = require('assert');
            const reimbursementExpenseKeys = ['representation','car_repair','toll_fee','gasoline','transpo','office_supplies','parking','per_diem','coding','others'];
            let reimbursementWorksheetViewState = {{search:'', filter:'all', hiddenCategories:new Set(), open:false}};
            {view_code}
            const row = {{date:'2026-09-13', client:'Acme', product:'Pump', serial_number:'SN-7', task:'Calibration', amounts:{{transpo: 25}}}};
            assert.strictEqual(rowMatchesReimbursementView(row), true);
            reimbursementWorksheetViewState.search = 'sn-7';
            assert.strictEqual(rowMatchesReimbursementView(row), true);
            reimbursementWorksheetViewState.search = 'missing';
            assert.strictEqual(rowMatchesReimbursementView(row), false);
            reimbursementWorksheetViewState.search = '';
            reimbursementWorksheetViewState.filter = 'with-expenses';
            assert.strictEqual(rowMatchesReimbursementView(row), true);
            const empty = {{manual:true, task:'Manual taxi', amounts:{{}}}};
            reimbursementWorksheetViewState.filter = 'zero-amount';
            assert.strictEqual(rowMatchesReimbursementView(empty), true);
            reimbursementWorksheetViewState.filter = 'manual-items';
            assert.strictEqual(rowMatchesReimbursementView(empty), true);
            assert.strictEqual(getReimbursementExpenseCategoryVisibility('transpo', {{transpo: 1}}, false), true);
            assert.strictEqual(getReimbursementExpenseCategoryVisibility('transpo', {{transpo: 0}}, true), false);
            assert.strictEqual(getReimbursementExpenseCategoryVisibility('transpo', {{transpo: 1}}, true), true);
            """
        )
        result = subprocess.run(
            ["node", "-e", node_script], cwd=ROOT, capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_hidden_rows_remain_in_save_and_full_totals(self):
        for token in (
            "const rowsForSave = collectReimbursementRowsForSave();",
            "const totalRows = rowsForTotal.length",
            "totalRows.forEach(function(row)",
            "getReimbursementPayloadRowTotal(row)",
            "reimbursementWorksheetViewState",
            "data-expense=",
            "data-total-expense=",
        ):
            self.assertIn(token, TEMPLATE)
        recalc_start = TEMPLATE.index("function recalculateReimbursementTotals()")
        recalc_end = TEMPLATE.index("\n    function buildMobileExpenseInputs", recalc_start)
        self.assertIn("currentReimbursementRows", TEMPLATE[recalc_start:recalc_end])
        collect_start = TEMPLATE.index("function collectReimbursementRowsForSave()")
        collect_end = TEMPLATE.index("\n    function snapshotCurrentReimbursementWorksheetRows", collect_start)
        self.assertIn("currentReimbursementRows", TEMPLATE[collect_start:collect_end])

    def test_mobile_cards_have_summary_disclosure_and_populated_first_order(self):
        for token in (
            "reim-mobile-card-summary",
            "reim-mobile-card-details",
            "reim-mobile-expense-disclosure",
            "Add expense category",
            "reimbursementMobileExpandedRowKeys",
            "toggleReimbursementMobileCard",
            "buildMobileExpenseInputs(row)",
            "getPopulatedReimbursementExpenseKeys(row)",
        ):
            self.assertIn(token, TEMPLATE)
        render_start = TEMPLATE.index("function renderReimbursementRows(rows)")
        render_end = TEMPLATE.index("\n    function syncReimbursementHorizontalScroll", render_start)
        render = TEMPLATE[render_start:render_end]
        self.assertIn("applyReimbursementWorksheetView();", render)
        self.assertIn("reimbursementMobileExpandedRowKeys", render)

    def test_view_overlay_and_focus_geometry_do_not_add_persistent_rows(self):
        view_start = TEMPLATE.index(".reim-view-popover")
        view_css = TEMPLATE[view_start:TEMPLATE.index("</style>", view_start)]
        for token in ("position: absolute", "z-index", "display: none", "max-height"):
            self.assertIn(token, view_css)
        focus_css = TEMPLATE[TEMPLATE.index("/* Reimbursement worksheet focus view."):TEMPLATE.index("</style>")]
        self.assertIn("body.reim-focus-active .reim-focus-toolbar", focus_css)
        self.assertRegex(
            focus_css,
            r"body\.reim-focus-active \.reim-view-toggle\s*\{[^}]*min-height:\s*30px;[^}]*height:\s*30px;",
        )
        self.assertRegex(
            focus_css,
            r"body\.reim-focus-active \.reim-view-status\s*\{[^}]*display:\s*none;",
        )
        self.assertNotIn("body.reim-focus-active .reim-view-popover", focus_css)
        tablet_start = TEMPLATE.index("@media (min-width: 821px) and (max-width: 1100px)")
        tablet_end = TEMPLATE.index("@media (max-width: 820px)", tablet_start)
        tablet_css = TEMPLATE[tablet_start:tablet_end]
        self.assertIn("overflow: visible;", tablet_css)
        self.assertIn("@media (max-width: 820px)", TEMPLATE)

    def test_lifecycle_and_context_reset_view_session_state(self):
        self.assertIn("resetReimbursementWorksheetViewState();", TEMPLATE)
        load_start = TEMPLATE.index("async function loadReimbursementRows(options)")
        load_end = TEMPLATE.index("\n    function formatApprovalDateTime", load_start)
        load = TEMPLATE[load_start:load_end]
        self.assertIn("resetReimbursementWorksheetViewState();", load)
        self.assertIn("applyReimbursementWorksheetView();", load)

    def test_current_worker_marker_and_release_record_are_current(self):
        self.assertIn("medical-service-pwa-offline-navigation-v156-reimbursement-worksheet-views", APP_SOURCE)
        matches = [
            release for release in RELEASES.get("releases", [])
            if release.get("release_key") == "2026-09-13-reimbursement-worksheet-views"
        ]
        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0].get("is_published"))
        self.assertTrue(any(item.get("category") == "Reimbursement" for item in matches[0].get("items", [])))


if __name__ == "__main__":
    unittest.main()
