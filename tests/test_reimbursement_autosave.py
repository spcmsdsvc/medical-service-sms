"""Focused contracts for the Reimbursement Package 1 save coordinator."""

import json
import pathlib
import subprocess
import textwrap
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / 'templates' / 'reimbursement.html').read_text(encoding='utf-8')
APP_SOURCE = (ROOT / 'app.py').read_text(encoding='utf-8')
RELEASES = json.loads((ROOT / 'static' / 'changelog' / 'releases.json').read_text(encoding='utf-8'))


class ReimbursementAutosaveSourceTests(unittest.TestCase):
    def test_save_status_is_explicitly_stateful(self):
        self.assertRegex(
            TEMPLATE,
            r'id="reimDraftStatus"[^>]*data-save-state="idle"[^>]*aria-live="polite"',
        )
        self.assertIn('el.dataset.saveState = state', TEMPLATE)
        for state in ('saving', 'saved', 'unsaved'):
            self.assertIn(f"state === '{state}'", TEMPLATE)

    def test_save_coordinator_tracks_context_version_and_serializes_requests(self):
        for token in (
            "const REIMBURSEMENT_AUTOSAVE_DELAY_MS = 900;",
            'let reimbursementEditVersion = 0;',
            'let reimbursementSavedEditVersion = 0;',
            'let reimbursementContextRevision = 0;',
            'let reimbursementSaveInFlight = null;',
            'let reimbursementSaveQueued = null;',
            'let reimbursementTransitionPromptBusy = false;',
            'function scheduleReimbursementAutosave()',
            'function reimbursementSaveEntryMatches(',
            'function enqueueReimbursementSave(',
        ):
            self.assertIn(token, TEMPLATE)

        save_start = TEMPLATE.index('async function saveReimbursementDraft(')
        save_end = TEMPLATE.index('\n    function reimbursementOfficeFieldTotal', save_start)
        save_block = TEMPLATE[save_start:save_end]
        self.assertIn('enqueueReimbursementSave(', save_block)
        self.assertIn('reimbursementHasUnsavedEdits()', save_block)
        self.assertIn('reimbursementClearAutosaveTimer()', save_block)
        self.assertNotIn("fetch('/save_reimbursement_draft'", save_block)

    def test_dirty_hook_debounces_only_editable_work(self):
        dirty_start = TEMPLATE.index('function markReimbursementDirty()')
        dirty_end = TEMPLATE.index('\n    function getReimbursementCsrfToken', dirty_start)
        dirty_block = TEMPLATE[dirty_start:dirty_end]
        self.assertIn('reimbursementEditVersion += 1', dirty_block)
        self.assertIn("setReimbursementDraftStatus('Unsaved changes'", dirty_block)
        self.assertIn('scheduleReimbursementAutosave()', dirty_block)
        self.assertIn('reimbursementIsEditable()', dirty_block)

    def test_three_choice_transition_guard_is_wired_to_load_and_claim_open(self):
        for token in (
            'id="reim-dialog-discard"',
            'Save and continue',
            'Discard',
            'Stay',
            'function reimbursementPrepareContextTransition(',
        ):
            self.assertIn(token, TEMPLATE)

        load_start = TEMPLATE.index('async function loadReimbursementRows(')
        load_end = TEMPLATE.index('\n    function formatApprovalDateTime', load_start)
        load_block = TEMPLATE[load_start:load_end]
        self.assertIn('reimbursementPrepareContextTransition(', load_block)
        self.assertIn('previousLoadState', load_block)
        self.assertIn('Previous worksheet remains open.', load_block)

        open_start = TEMPLATE.index('async function openReimbursementStatusRecord(')
        open_end = TEMPLATE.index('\n    async function openLegacyReimbursementRange', open_start)
        self.assertIn('reimbursementPrepareContextTransition(', TEMPLATE[open_start:open_end])
        notification_start = TEMPLATE.index('async function openReimbursementNotification(')
        notification_end = TEMPLATE.index('\n    document.addEventListener', notification_start)
        notification_block = TEMPLATE[notification_start:notification_end]
        self.assertIn('if (start && end)', notification_block)
        self.assertIn('await openLegacyReimbursementRange(start, end);', notification_block)

    def test_submit_rechecks_latest_version_before_irreversible_request(self):
        submit_start = TEMPLATE.index('async function submitReimbursement()')
        submit_end = TEMPLATE.index('\n    function getLoadedReimbursementDates', submit_start)
        submit_block = TEMPLATE[submit_start:submit_end]
        self.assertIn('const submitContextKey = reimbursementCurrentContext().key;', submit_block)
        self.assertIn('const submitEditVersion = reimbursementEditVersion;', submit_block)
        self.assertIn('const latestSaved = await saveReimbursementDraft(false);', submit_block)
        self.assertIn('setReimbursementSubmitInputsBusy(true);', submit_block)
        self.assertIn('setReimbursementSubmitInputsBusy(false);', submit_block)

    def test_clear_delete_and_transition_invalidate_pending_saves(self):
        for function_name in (
            'async function deleteReimbursementDraft()',
            'async function clearReimbursementForm()',
        ):
            start = TEMPLATE.index(function_name)
            end = TEMPLATE.find('\n    async function ', start + len(function_name))
            if end < 0:
                end = TEMPLATE.find('\n    function ', start + len(function_name))
            self.assertIn('reimbursementBeginDestructiveMutation(', TEMPLATE[start:end])
        self.assertIn('reimbursementInvalidatePendingSaves(', TEMPLATE)

    def test_context_and_version_guard_runtime(self):
        start = TEMPLATE.index('function reimbursementContextKey(')
        end = TEMPLATE.index('\n    function ', start + 10)
        helper = TEMPLATE[start:end]
        match_start = TEMPLATE.index('function reimbursementSaveEntryMatches(')
        match_end = TEMPLATE.index('\n    function ', match_start + 10)
        helper += '\n' + TEMPLATE[match_start:match_end]
        node_script = textwrap.dedent(f"""
            const assert = require('assert');
            {helper}
            const key = reimbursementContextKey({{start: '2026-09-01', end: '2026-09-30', id: 17}});
            assert.strictEqual(key, JSON.stringify(['2026-09-01', '2026-09-30', 17]));
            const entry = {{contextRevision: 4, contextKey: key, version: 8}};
            assert.strictEqual(reimbursementSaveEntryMatches(entry, {{revision: 4, contextKey: key, version: 8}}), true);
            assert.strictEqual(reimbursementSaveEntryMatches(entry, {{revision: 4, contextKey: key, version: 9}}), false);
            assert.strictEqual(reimbursementSaveEntryMatches(entry, {{revision: 5, contextKey: key, version: 8}}), false);
            assert.strictEqual(reimbursementSaveEntryMatches(entry, {{revision: 4, contextKey: 'other', version: 8}}), false);
        """)
        result = subprocess.run(
            ['node', '-e', node_script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_save_queue_runtime_serializes_latest_edit_and_preserves_failed_values(self):
        helper_start = TEMPLATE.index('function reimbursementContextKey(')
        helper_end = TEMPLATE.index('\n    function reimEscape', helper_start)
        helpers = TEMPLATE[helper_start:helper_end]
        coordinator_start = TEMPLATE.index('function reimbursementCurrentContext()')
        coordinator_end = TEMPLATE.index('\n    function mergeReimbursementDraftRows', coordinator_start)
        coordinator = TEMPLATE[coordinator_start:coordinator_end]
        node_script = textwrap.dedent("""
            const assert = require('assert');
            const elements = {
                reimStartDate: { value: '2026-09-01' },
                reimEndDate: { value: '2026-09-30' },
                reimDraftStatus: {
                    dataset: {},
                    style: {},
                    textContent: '',
                    classList: { toggle() {} }
                }
            };
            const timers = new Map();
            let nextTimer = 1;
            const window = {
                setTimeout(callback, delay) {
                    const id = nextTimer++;
                    timers.set(id, { callback, delay });
                    return id;
                },
                clearTimeout(id) { timers.delete(id); }
            };
            const navigator = { onLine: true };
            const document = {
                getElementById(id) { return elements[id] || null; },
                querySelectorAll() { return []; }
            };
            let currentReimbursementId = null;
            let currentReimbursementRows = [{
                shift_id: 17,
                amounts: { transpo: 100 },
                row_total: 100
            }];
            let currentReimbursementExcludedRows = [];
            let reimbursementEditVersion = 1;
            let reimbursementSavedEditVersion = 0;
            let reimbursementContextRevision = 0;
            let reimbursementActiveContext = { start: '2026-09-01', end: '2026-09-30', id: 0, key: '' };
            let reimbursementAutosaveTimer = null;
            let reimbursementAutosaveSuspended = 0;
            let reimbursementSaveInFlight = null;
            let reimbursementSaveQueued = null;
            let reimbursementTransitionBusy = false;
            const REIMBURSEMENT_AUTOSAVE_DELAY_MS = 900;
            const statusLog = [];
            const errors = [];
            function reimbursementIsEditable() { return true; }
            function collectReimbursementRowsForSave() {
                return JSON.parse(JSON.stringify(currentReimbursementRows));
            }
            function getReimbursementCsrfToken() { return ''; }
            function setReimbursementDraftStatus(message, tone, state) {
                statusLog.push({ message, tone, state });
                elements.reimDraftStatus.textContent = message;
                elements.reimDraftStatus.dataset.saveState = state || '';
            }
            function setReimbursementButtonsBusy() {}
            function applyReimbursementStatusUi() {}
            function updateReimbursementLifecycleFromPayload(payload) {
                if (payload && payload.id) currentReimbursementId = payload.id;
                return {};
            }
            function applyReimbursementTotalSummary() { return null; }
            function refreshReimbursementLprPanel() { return Promise.resolve(); }
            function reimbursementServerTotalLabel() { return ''; }
            function reimAlert(message) { errors.push(message); }
            async function parseReimbursementJsonResponse(response) { return response.body; }
            const requests = [];
            function fetch(url, options) {
                requests.push({ url, body: JSON.parse(options.body), resolve: null });
                return new Promise(resolve => { requests[requests.length - 1].resolve = resolve; });
            }
        """) + helpers + coordinator + textwrap.dedent("""
            const first = enqueueReimbursementSave(false, {});
            await Promise.resolve();
            assert.strictEqual(requests.length, 1);
            reimbursementEditVersion = 2;
            currentReimbursementRows[0].amounts.transpo = 200;
            currentReimbursementRows[0].row_total = 200;
            const second = enqueueReimbursementSave(false, {});
            assert.strictEqual(requests.length, 1, 'a second edit must queue behind the active save');
            requests[0].resolve({
                ok: true,
                body: { success: true, id: 42, rows_saved: 1, excluded_rows: [] }
            });
            const firstResult = await first;
            assert.strictEqual(firstResult.stale, true, 'older response must be marked stale');
            assert.strictEqual(requests.length, 2, 'the queued latest snapshot should start after the first response');
            assert.strictEqual(requests[1].body.rows[0].amounts.transpo, 200);
            requests[1].resolve({
                ok: true,
                body: { success: true, id: 42, rows_saved: 1, excluded_rows: [] }
            });
            const secondResult = await second;
            assert.strictEqual(secondResult.applied, true, 'latest response must apply');
            assert.strictEqual(reimbursementSavedEditVersion, 2);
            assert.strictEqual(currentReimbursementId, 42);
            assert.ok(statusLog.some(entry => entry.state === 'saved'), 'latest response must report Saved');

            reimbursementEditVersion = 3;
            currentReimbursementRows[0].amounts.transpo = 300;
            currentReimbursementRows[0].row_total = 300;
            const failed = enqueueReimbursementSave(false, {});
            await Promise.resolve();
            requests[2].resolve({
                ok: false,
                body: { success: false, error: 'temporary save failure' }
            });
            const failedResult = await failed;
            assert.strictEqual(failedResult.ok, false);
            assert.strictEqual(currentReimbursementRows[0].amounts.transpo, 300);
            assert.strictEqual(reimbursementSavedEditVersion, 2);
            assert.strictEqual(elements.reimDraftStatus.dataset.saveState, 'unsaved');

            scheduleReimbursementAutosave();
            assert.strictEqual(timers.size, 1);
            assert.strictEqual([...timers.values()][0].delay, 900);
            scheduleReimbursementAutosave();
            assert.strictEqual(timers.size, 1, 'editing again should reset the debounce timer');
            navigator.onLine = false;
            scheduleReimbursementAutosave();
            assert.strictEqual(timers.size, 0, 'offline work must remain unsaved for a later online action');
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

    def test_autosave_release_and_worker_version_are_current(self):
        self.assertIn('medical-service-pwa-offline-navigation-v151-calibration-approval-gated-service-documents', APP_SOURCE)
        matches = [
            release for release in RELEASES.get('releases', [])
            if release.get('release_key') == '2026-09-07-reimbursement-autosave'
        ]
        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0].get('is_published'))
        self.assertTrue(any(item.get('category') == 'Reimbursement' for item in matches[0].get('items', [])))


if __name__ == '__main__':
    unittest.main()
