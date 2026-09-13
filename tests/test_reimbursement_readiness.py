"""Focused contracts for Reimbursement Package 2 readiness and action dock."""

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


class ReimbursementReadinessSourceTests(unittest.TestCase):
    def test_dock_reuses_existing_action_ids_and_is_accessible(self):
        for token in (
            'id="reimActionDock"',
            'id="reimReadinessToggle"',
            'id="reimReadinessPanel"',
            'id="reimReadinessList"',
            'aria-expanded="false"',
            'aria-controls="reimReadinessPanel"',
            'id="reimDraftStatus"',
            'id="reimSaveDraftBtn"',
            'id="reimSubmitBtn"',
            'toggleReimbursementReadiness()',
            'closeReimbursementReadiness()',
        ):
            self.assertIn(token, TEMPLATE)
        self.assertEqual(TEMPLATE.count('id="reimDraftStatus"'), 1)
        self.assertEqual(TEMPLATE.count('id="reimSaveDraftBtn"'), 1)
        self.assertEqual(TEMPLATE.count('id="reimSubmitBtn"'), 1)

    def test_readiness_model_and_resolution_actions_exist(self):
        for token in (
            "function buildReimbursementReadinessSnapshot(options)",
            "function updateReimbursementReadiness()",
            "function renderReimbursementReadiness(snapshot)",
            "function focusReimbursementAmountField()",
            "async function saveReimbursementFromReadiness()",
            "async function saveAndReviewReimbursementLpr()",
            "async function retryReimbursementReadinessSignature()",
            "function openReimbursementReceiptsFromReadiness()",
            "await refreshReimbursementSignatureStatus();",
            "reimbursementReadinessTokenMatches(readinessToken)",
        ):
            self.assertIn(token, TEMPLATE)

    def test_readiness_refreshes_from_existing_mutation_paths(self):
        for token in (
            "updateReimbursementReadiness();",
            "reimbursementReadinessState.lpr = 'missing';",
            "await refreshReimbursementLprPanel();",
            "await refreshReimbursementSignatureStatus();",
            "setReimbursementDockVisibility(true);",
            "setReimbursementDockVisibility(false);",
        ):
            self.assertIn(token, TEMPLATE)
        recalc_start = TEMPLATE.index("function recalculateReimbursementTotals()")
        recalc_end = TEMPLATE.index("\n    function buildMobileExpenseInputs", recalc_start)
        self.assertIn("updateReimbursementReadiness();", TEMPLATE[recalc_start:recalc_end])
        load_start = TEMPLATE.index("async function loadReimbursementRows(options)")
        load_end = TEMPLATE.index("\n    function formatApprovalDateTime", load_start)
        load_block = TEMPLATE[load_start:load_end]
        self.assertIn("await refreshReimbursementSignatureStatus();", load_block)
        self.assertIn("setReimbursementDockVisibility(true);", load_block)

    def test_readiness_model_runtime_classifies_blockers_and_advisories(self):
        build_start = TEMPLATE.index("function buildReimbursementReadinessSnapshot(options)")
        build_end = TEMPLATE.index("\n    function reimbursementReadinessActionMarkup", build_start)
        model = TEMPLATE[build_start:build_end]
        node_script = textwrap.dedent(
            f"""
            const assert = require('assert');
            const reimbursementExpenseKeys = ['representation','car_repair','toll_fee','gasoline','transpo','office_supplies','parking','per_diem','coding','others'];
            function getReimbursementPayloadRowTotal(row) {{
                if (!row || typeof row !== 'object') return 0;
                const amounts = row.amounts && typeof row.amounts === 'object' ? row.amounts : {{}};
                let total = 0;
                reimbursementExpenseKeys.forEach(key => {{ total += Number(amounts[key] || 0); }});
                if (!total && row.manual) total = Number(row.amount || row.row_total || 0);
                return Number.isFinite(total) ? total : 0;
            }}
            {model}
            const ready = buildReimbursementReadinessSnapshot({{
                rows: [{{ amounts: {{ transpo: 125 }} }}, {{ amounts: {{ transpo: 0 }} }}],
                editable: true, saveState: 'saved', unsaved: false, signature: 'ready',
                officeFieldTotal: 0, lpr: 'not-required', savedVersion: 0, receiptCount: 0
            }});
            assert.strictEqual(ready.ready, true);
            assert.strictEqual(ready.total, 125);
            assert.strictEqual(ready.includedRows, 1);
            assert.strictEqual(ready.zeroRows, 1);
            assert.strictEqual(ready.blockers.length, 0);
            assert.ok(ready.advisories.some(item => item.id === 'zero-rows'));
            assert.ok(ready.advisories.some(item => item.id === 'receipts'));

            const blocked = buildReimbursementReadinessSnapshot({{
                rows: [{{ amounts: {{ office_supplies: 15 }} }}],
                editable: true, saveState: 'unsaved', unsaved: true, signature: 'missing',
                officeFieldTotal: 15, lpr: 'missing', savedVersion: 0, hasSavedRecord: false, receiptCount: 0
            }});
            assert.strictEqual(blocked.ready, false);
            assert.deepStrictEqual(blocked.blockers.map(item => item.id), ['save', 'signature', 'lpr']);
            assert.strictEqual(blocked.blockers.find(item => item.id === 'lpr').action, 'saveAndReviewReimbursementLpr');

            const locked = buildReimbursementReadinessSnapshot({{
                rows: [{{ amounts: {{ transpo: 99 }} }}], editable: false,
                lifecycleLabel: 'Submitted / Waiting for Approval', lifecycleReason: 'Locked after submit.',
                saveState: 'saved', unsaved: false, signature: 'ready', officeFieldTotal: 0,
                lpr: 'not-required', savedVersion: 0, receiptCount: 2
            }});
            assert.strictEqual(locked.ready, false);
            assert.strictEqual(locked.blockers[0].id, 'lifecycle');
            """
        )
        result = subprocess.run(
            ["node", "-e", node_script], cwd=ROOT, capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_async_checks_are_context_guarded_and_lpr_rebases_after_save(self):
        lpr_start = TEMPLATE.index("async function refreshReimbursementLprPanel()")
        lpr_end = TEMPLATE.index("\n    async function deleteReimbursementLinkedLpr", lpr_start)
        lpr_block = TEMPLATE[lpr_start:lpr_end]
        self.assertIn("const readinessToken = reimbursementReadinessToken();", lpr_block)
        self.assertIn("if (!reimbursementReadinessTokenMatches(readinessToken)) return;", lpr_block)
        sig_start = TEMPLATE.index("async function refreshReimbursementSignatureStatus()")
        sig_end = TEMPLATE.index("\n    async function ensureReimbursementSignatureBeforeSubmit", sig_start)
        sig_block = TEMPLATE[sig_start:sig_end]
        self.assertIn("const token = reimbursementReadinessToken();", sig_block)
        self.assertIn("if (!reimbursementReadinessTokenMatches(token)) return false;", sig_block)
        save_start = TEMPLATE.index("async function executeReimbursementSaveEntry(entry)")
        save_end = TEMPLATE.index("\n    function startReimbursementSaveEntry", save_start)
        self.assertIn("reimbursementReadinessState.lprSavedVersion = entry.version;", TEMPLATE[save_start:save_end])

    def test_dock_layout_reserves_space_and_respects_focus_mobile_and_print(self):
        css_start = TEMPLATE.index(".reim-action-dock {")
        css_end = TEMPLATE.index("</style>", css_start)
        css = TEMPLATE[css_start:css_end]
        for token in (
            "left: var(--sidebar-width, 240px)",
            "env(safe-area-inset-bottom",
            "body.reim-focus-active .reim-action-dock",
            "@media (max-width: 820px)",
            "@media print",
            "aria-expanded",
        ):
            self.assertIn(token, css if token != "aria-expanded" else TEMPLATE)
        self.assertIn("padding-bottom: calc(84px", css)
        self.assertIn("padding: 4px 4px 0", TEMPLATE)
        self.assertIn("min-height: 44px", css)

    def test_focus_mode_uses_compact_selection_and_in_flow_dock_geometry(self):
        focus_start = TEMPLATE.index("/* Reimbursement worksheet focus view.")
        focus_css = TEMPLATE[focus_start:TEMPLATE.index("</style>", focus_start)]

        self.assertIn("body.reim-focus-active .reim-row-selection-toolbar", focus_css)
        selection_start = focus_css.index("body.reim-focus-active .reim-row-selection-toolbar")
        selection_end = focus_css.index("\n        }", selection_start)
        selection_css = focus_css[selection_start:selection_end]
        for token in (
            "height: 36px",
            "min-height: 36px",
            "padding: 2px 6px",
            "flex-wrap: nowrap",
        ):
            self.assertIn(token, selection_css)
        self.assertIn("body.reim-focus-active .reim-row-selection-control", focus_css)
        self.assertIn("body.reim-focus-active #reimDeleteSelectedBtn", focus_css)

        dock_start = TEMPLATE.index("body.reim-focus-active .reim-action-dock")
        dock_end = TEMPLATE.index("\n        }", dock_start)
        dock_css = TEMPLATE[dock_start:dock_end]
        for token in (
            "position: relative",
            "left: auto",
            "right: auto",
            "bottom: auto",
            "flex: 0 0 48px",
            "min-height: 48px",
        ):
            self.assertIn(token, dock_css)
        self.assertIn("body.reim-focus-active .reim-table-card", focus_css)
        self.assertIn("padding: 4px 4px 0", focus_css)
        self.assertIn("body.reim-focus-active .reim-readiness-panel", TEMPLATE)
        self.assertIn("bottom: 52px", TEMPLATE)

    def test_current_cache_and_published_release_are_current(self):
        self.assertIn("medical-service-pwa-offline-navigation-v156-reimbursement-worksheet-views", APP_SOURCE)
        matches = [
            release for release in RELEASES.get("releases", [])
            if release.get("release_key") == "2026-09-11-reimbursement-readiness"
        ]
        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0].get("is_published"))
        self.assertTrue(any(item.get("category") == "Reimbursement" for item in matches[0].get("items", [])))
        focus_matches = [
            release for release in RELEASES.get("releases", [])
            if release.get("release_key") == "2026-09-11-reimbursement-focus-space"
        ]
        self.assertEqual(len(focus_matches), 1)
        self.assertTrue(focus_matches[0].get("is_published"))
        self.assertTrue(any(item.get("category") == "Reimbursement" for item in focus_matches[0].get("items", [])))

    def test_readiness_has_no_new_backend_route_or_duplicate_action_markup(self):
        self.assertNotRegex(TEMPLATE, r"fetch\(['\"]/[^'\"]*(readiness|submission-readiness)")
        self.assertEqual(len(re.findall(r"id=\"reim(ReadinessPanel|ActionDock|ReadinessToggle)\"", TEMPLATE)), 3)


if __name__ == "__main__":
    unittest.main()
