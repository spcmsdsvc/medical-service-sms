"""Focused contracts for Reimbursement row selection and bulk removal."""

import json
import pathlib
import subprocess
import textwrap
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / 'templates' / 'reimbursement.html').read_text(encoding='utf-8')
APP_SOURCE = (ROOT / 'app.py').read_text(encoding='utf-8')
RELEASES = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))


class ReimbursementBulkSelectionSourceTests(unittest.TestCase):
    def test_toolbar_and_row_checkbox_markup_cover_desktop_and_mobile(self):
        for token in (
            'id="reimRowSelectionToolbar"',
            'id="reimSelectAllRows"',
            'id="reimDeleteSelectedBtn"',
            'id="reimSelectedRowsStatus"',
            'class="reim-row-select"',
            'handleReimbursementRowSelection(this)',
            'handleReimbursementSelectAllRows(this)',
            'Delete selected',
        ):
            self.assertIn(token, TEMPLATE)

        render_start = TEMPLATE.index('function renderReimbursementRows(rows)')
        render_end = TEMPLATE.index('function syncReimbursementHorizontalScroll()', render_start)
        render_block = TEMPLATE[render_start:render_end]
        desktop_start = render_block.index('body.innerHTML = rows.map')
        mobile_start = render_block.index('mobile.innerHTML = rows.map')
        self.assertIn('class="reim-row-select"', render_block[desktop_start:mobile_start])
        self.assertIn('class="reim-row-select"', render_block[mobile_start:])

    def test_selection_helpers_track_keys_and_sync_controls(self):
        for token in (
            'let reimbursementSelectedRowKeys = new Set();',
            'function getReimbursementActiveRowKeys(',
            'function pruneReimbursementSelectedRowKeys(',
            'function syncReimbursementRowSelectionUi(',
            'function handleReimbursementRowSelection(',
            'function handleReimbursementSelectAllRows(',
            'function clearReimbursementRowSelection(',
            'selectAll.indeterminate =',
            'reimbursementSelectedRowKeys.has(',
        ):
            self.assertIn(token, TEMPLATE)

    def test_bulk_remove_rechecks_context_and_persists_once(self):
        start = TEMPLATE.index('async function removeSelectedReimbursementRows()')
        end = TEMPLATE.index('\n    async function restoreReimbursementRow', start)
        block = TEMPLATE[start:end]
        for token in (
            'reimbursementRowChangeBusy',
            'reimbursementTransitionBusy',
            'reimbursementSubmitBusy',
            'guardReimbursementEditableAction',
            'snapshotCurrentReimbursementWorksheetRows()',
            'reimConfirmDialog(',
            'reimbursementCurrentContext().key',
            'persistReimbursementRowChange(',
            'currentReimbursementExcludedRows',
            'Calendar schedules and package receipts will not be deleted.',
        ):
            self.assertIn(token, block)
        self.assertEqual(block.count('persistReimbursementRowChange('), 1)
        self.assertIn('clearReimbursementRowSelection()', block)

    def test_selection_is_wired_to_status_busy_submit_and_load_lifecycle(self):
        status_start = TEMPLATE.index('function applyReimbursementStatusUi()')
        status_end = TEMPLATE.index('\n    function getReimbursementReceiptList', status_start)
        status_block = TEMPLATE[status_start:status_end]
        self.assertIn('syncReimbursementRowSelectionUi()', status_block)
        self.assertIn('.reim-row-select', TEMPLATE)

        busy_start = TEMPLATE.index('function setReimbursementButtonsBusy(')
        busy_end = TEMPLATE.index('\n    function setReimbursementSubmitInputsBusy', busy_start)
        self.assertIn('reimDeleteSelectedBtn', TEMPLATE[busy_start:busy_end])

        submit_start = TEMPLATE.index('function setReimbursementSubmitInputsBusy(')
        submit_end = TEMPLATE.index('function showReimbursementDeleteDraftConfirm', submit_start)
        self.assertIn('.reim-row-select', TEMPLATE[submit_start:submit_end])

        load_start = TEMPLATE.index('async function loadReimbursementRows(')
        load_end = TEMPLATE.index('\n    function formatApprovalDateTime', load_start)
        load_block = TEMPLATE[load_start:load_end]
        self.assertIn('clearReimbursementRowSelection()', load_block)

    def test_removed_rows_payload_and_restore_paths_remain_authoritative(self):
        persist_start = TEMPLATE.index('async function persistReimbursementRowChange(')
        persist_end = TEMPLATE.index('\n    async function removeReimbursementRow', persist_start)
        persist_block = TEMPLATE[persist_start:persist_end]
        self.assertIn('saveReimbursementDraft(true)', persist_block)
        self.assertIn('currentReimbursementRows = previousRows', persist_block)
        self.assertIn('currentReimbursementExcludedRows = previousExcludedRows', persist_block)

        restore_start = TEMPLATE.index('async function restoreReimbursementRow(')
        restore_end = TEMPLATE.index('\n    async function restoreAllReimbursementRows', restore_start)
        self.assertIn('persistReimbursementRowChange(', TEMPLATE[restore_start:restore_end])

    def test_bulk_selection_cache_and_published_release_are_current(self):
        self.assertIn('medical-service-pwa-offline-navigation-v149-calibration-report-pdf', APP_SOURCE)
        matches = [
            release for release in RELEASES.get('releases', [])
            if release.get('release_key') == '2026-09-08-reimbursement-bulk-selection'
        ]
        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0].get('is_published'))
        self.assertTrue(any(item.get('category') == 'Reimbursement' for item in matches[0].get('items', [])))

    def test_selection_helpers_runtime_cover_partial_all_empty_and_mobile_sync(self):
        start = TEMPLATE.index('function getReimbursementActiveRowKeys(')
        end = TEMPLATE.index('function renderReimbursementRows(', start)
        helpers = TEMPLATE[start:end]
        node_script = textwrap.dedent(f"""
            const assert = require('assert');
            const elements = {{
                reimSelectAllRows: {{ checked: false, indeterminate: false, disabled: false, setAttribute() {{}} }},
                reimDeleteSelectedBtn: {{ disabled: true, textContent: '', title: '', setAttribute() {{}} }},
                reimSelectedRowsStatus: {{ textContent: '' }}
            }};
            const checkboxes = [
                {{ dataset: {{ rowKey: 'a' }}, checked: false, disabled: false }},
                {{ dataset: {{ rowKey: 'a' }}, checked: false, disabled: false }},
                {{ dataset: {{ rowKey: 'b' }}, checked: false, disabled: false }},
                {{ dataset: {{ rowKey: 'b' }}, checked: false, disabled: false }}
            ];
            const document = {{
                getElementById(id) {{ return elements[id] || null; }},
                querySelectorAll(selector) {{
                    return selector === '.reim-row-select' ? checkboxes : [];
                }}
            }};
            let currentReimbursementRows = [{{ shift_id: 'a' }}, {{ shift_id: 'b' }}];
            let reimbursementSelectedRowKeys = new Set();
            function getReimbursementRowKey(row) {{ return String(row.shift_id); }}
            let reimbursementRowChangeBusy = false;
            let reimbursementBulkDeleteBusy = false;
            let reimbursementButtonsBusy = false;
            let reimbursementTransitionBusy = false;
            let reimbursementTransitionPromptBusy = false;
            let reimbursementSubmitBusy = false;
            let reimbursementIsEditable = () => true;
            {helpers}
            syncReimbursementRowSelectionUi();
            assert.strictEqual(elements.reimDeleteSelectedBtn.disabled, true);
            checkboxes[0].checked = true;
            handleReimbursementRowSelection(checkboxes[0]);
            assert.deepStrictEqual([...reimbursementSelectedRowKeys], ['a']);
            assert.strictEqual(checkboxes[1].checked, true);
            assert.strictEqual(elements.reimSelectAllRows.indeterminate, true);
            assert.strictEqual(elements.reimDeleteSelectedBtn.disabled, false);
            handleReimbursementSelectAllRows({{ checked: true }});
            assert.deepStrictEqual([...reimbursementSelectedRowKeys].sort(), ['a', 'b']);
            assert.strictEqual(checkboxes.every(item => item.checked), true);
            assert.strictEqual(elements.reimSelectAllRows.checked, true);
            handleReimbursementSelectAllRows({{ checked: false }});
            assert.deepStrictEqual([...reimbursementSelectedRowKeys], []);
            assert.strictEqual(elements.reimDeleteSelectedBtn.disabled, true);
            reimbursementSelectedRowKeys = new Set(['stale']);
            pruneReimbursementSelectedRowKeys(currentReimbursementRows);
            assert.deepStrictEqual([...reimbursementSelectedRowKeys], []);
        """)
        result = subprocess.run(
            ['node', '-e', node_script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, (result.stderr or '') + (result.stdout or ''))

    def test_bulk_remove_runtime_uses_one_save_and_rolls_back_selection(self):
        start = TEMPLATE.index('async function removeSelectedReimbursementRows()')
        end = TEMPLATE.index('\n    async function restoreReimbursementRow', start)
        bulk = TEMPLATE[start:end]
        node_script = textwrap.dedent(f"""
            const assert = require('assert');
            let currentReimbursementRows = [
                {{ shift_id: 1, task: 'A', amounts: {{ transpo: 20 }}, remarks: 'keep A' }},
                {{ shift_id: 2, task: 'B', amounts: {{ transpo: 30 }}, remarks: 'keep B' }},
                {{ shift_id: 3, task: 'C', amounts: {{ transpo: 40 }}, remarks: 'keep C' }}
            ];
            let currentReimbursementExcludedRows = [];
            let reimbursementSelectedRowKeys = new Set(['1', '2']);
            let reimbursementRowChangeBusy = false;
            let reimbursementBulkDeleteBusy = false;
            let reimbursementTransitionBusy = false;
            let reimbursementTransitionPromptBusy = false;
            let reimbursementSubmitBusy = false;
            let currentReimbursementLifecycle = {{ editable: true }};
            let contextKey = 'range-a';
            let confirmResult = true;
            let persistResult = true;
            let saveCalls = 0;
            const alerts = [];
            function reimbursementIsEditable() {{ return !!currentReimbursementLifecycle.editable; }}
            function guardReimbursementEditableAction() {{ return reimbursementIsEditable(); }}
            function reimbursementCurrentContext() {{ return {{ key: contextKey }}; }}
            function getReimbursementRowKey(row) {{ return String(row.shift_id); }}
            function reimbursementExcludedRowKey(row) {{ return String(row.shift_id); }}
            function reimbursementRowLabel(row) {{ return row.task; }}
            function snapshotCurrentReimbursementWorksheetRows() {{ return currentReimbursementRows.map(row => ({{ ...row, amounts: {{ ...row.amounts }} }})); }}
            function reimConfirmDialog() {{ return Promise.resolve(confirmResult); }}
            function reimAlert(message) {{ alerts.push(message); }}
            function syncReimbursementRowSelectionUi() {{}}
            function applyReimbursementStatusUi() {{}}
            function clearReimbursementRowSelection() {{ reimbursementSelectedRowKeys.clear(); }}
            async function persistReimbursementRowChange(previousRows, previousExcludedRows) {{
                saveCalls += 1;
                if (!persistResult) {{
                    currentReimbursementRows = previousRows;
                    currentReimbursementExcludedRows = previousExcludedRows;
                    return false;
                }}
                return true;
            }}
            {bulk}
            await removeSelectedReimbursementRows();
            assert.strictEqual(saveCalls, 1);
            assert.deepStrictEqual(currentReimbursementRows.map(row => row.shift_id), [3]);
            assert.deepStrictEqual(currentReimbursementExcludedRows.map(row => row.shift_id), [1, 2]);
            assert.deepStrictEqual([...reimbursementSelectedRowKeys], []);

            currentReimbursementRows = [
                {{ shift_id: 1, task: 'A', amounts: {{ transpo: 20 }}, remarks: 'keep A' }},
                {{ shift_id: 2, task: 'B', amounts: {{ transpo: 30 }}, remarks: 'keep B' }},
                {{ shift_id: 3, task: 'C', amounts: {{ transpo: 40 }}, remarks: 'keep C' }}
            ];
            currentReimbursementExcludedRows = [];
            reimbursementSelectedRowKeys = new Set(['1', '2']);
            confirmResult = false;
            await removeSelectedReimbursementRows();
            assert.strictEqual(saveCalls, 1, 'cancellation must not save');
            assert.deepStrictEqual([...reimbursementSelectedRowKeys], ['1', '2']);

            confirmResult = true;
            persistResult = false;
            await removeSelectedReimbursementRows();
            assert.strictEqual(saveCalls, 2);
            assert.deepStrictEqual(currentReimbursementRows.map(row => row.shift_id), [1, 2, 3]);
            assert.deepStrictEqual([...reimbursementSelectedRowKeys], ['1', '2']);
        """)
        node_script = '(async function() {' + node_script + '})().catch(error => { console.error(error); process.exit(1); });'
        result = subprocess.run(
            ['node', '-e', node_script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == '__main__':
    unittest.main()
