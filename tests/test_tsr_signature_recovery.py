"""Focused contracts for explicit same-schedule/client TSR signature recovery."""

import json
import os
import pathlib
import subprocess
import tempfile
import unittest
from datetime import datetime, time
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4


ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = pathlib.Path(r"C:\Users\Jonamar\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe")

_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / f"medical_service_tsr_signature_{os.getpid()}_{uuid4().hex}.db"
os.environ.setdefault("MEDICAL_SERVICE_TEST_DB", str(_TEST_DB_PATH))

try:
    import app as app_module
except Exception as exc:  # pragma: no cover - source contracts remain useful without imports
    app_module = None
    APP_IMPORT_ERROR = exc
else:
    APP_IMPORT_ERROR = None


class TsrSignatureRecoverySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        cls.template = (ROOT / "templates" / "offline_tsr.html").read_text(encoding="utf-8")
        cls.release = (ROOT / "static" / "changelog" / "releases.json").read_text(encoding="utf-8")

    def test_draft_action_and_explicit_modal_controls_exist(self):
        for marker in (
            "Recover available signatures",
            "tsrSignatureRecoveryModal",
            "tsr-signature-recovery-target-${target}",
            "tsr-signature-recovery-source-list",
            "applyStandaloneTSRSignatureRecovery",
        ):
            self.assertIn(marker, self.template)

    def test_recovery_requires_same_schedule_and_client_context(self):
        for marker in (
            "getStandaloneTSRSignatureRecoveryContext",
            "standaloneTSRRecoveryContextsMatch",
            "client_id",
            "schedule_id",
            "selectedSchedule",
            "filterStandaloneTSRSignatureRecoveryCandidates",
        ):
            self.assertIn(marker, self.template)
        recovery = self.template.split("async function collectStandaloneTSRSignatureCandidates", 1)[1].split(
            "\nfunction renderStandaloneTSRSignatureRecovery", 1
        )[0]
        self.assertIn("filterStandaloneTSRSignatureRecoveryCandidates", recovery)
        self.assertIn("getStandaloneTSRSignatureRecoveryContext", self.template)

    def test_recovery_collection_has_only_unfinished_local_sources(self):
        recovery = self.template.split("async function collectStandaloneTSRSignatureCandidates", 1)[1].split(
            "\nfunction getStandaloneTSRSignatureRecoveryMissingTargets", 1
        )[0]
        for marker in (
            "loadStandaloneTSRDraftRecordsFromIndexedDB",
            "loadOfflineTSRQueueStore",
            "loadStandaloneTSRDraftFromLocalStorageFallback",
            "isStandaloneTSRUnfinishedSignatureRecoverySource",
            "Only unfinished device drafts",
        ):
            self.assertIn(marker, recovery)
        self.assertIn("server_submission_id", self.template.split("function isStandaloneTSRUnfinishedSignatureRecoverySource", 1)[1].split(
            "\nfunction buildStandaloneTSRSignatureRecoveryCandidate", 1
        )[0])
        self.assertNotIn("get_latest_online_tsr_for_shift", recovery)
        self.assertNotIn("get_online_tsr_submission", recovery)
        self.assertNotIn("fetchStandaloneTSRRecoverySubmission", recovery)
        self.assertNotIn("parent_submission_id", recovery)
        self.assertNotIn("revision_no", recovery)

    def test_selection_only_fills_missing_slots_and_preserves_existing_values(self):
        for marker in (
            "mergeStandaloneTSRRecoverySignatures",
            "requestedTargets",
            "currentSignatures",
            "signatureData",
        ):
            self.assertIn(marker, self.template)
        apply_fn = self.template.split("async function applyStandaloneTSRSignatureRecovery", 1)[1].split(
            "\nasync function deleteStandaloneTSRDraft", 1
        )[0]
        self.assertIn("standaloneTSRSignatureRecoveryStateIsActive", apply_fn)
        self.assertIn("contextVersion", self.template)
        self.assertIn("standaloneCurrentDraftId", self.template)
        self.assertIn("saveStandaloneTSRDraftLocally", apply_fn)

    def test_stale_context_and_failed_storage_are_reported(self):
        for marker in (
            "standaloneTSRSignatureRecoveryState",
            "contextVersion",
            "The current TSR draft changed",
            "could not be saved on this device",
            "source:'none'",
            "waitForStandaloneTSRLocalSaves",
        ):
            self.assertIn(marker, self.template)

    def test_server_final_paths_validate_and_strip_only_client_signature(self):
        helper = self.app_source.split("def strip_persisted_online_tsr_client_signature", 1)[1].split(
            "\n\nTSR_SUPPORTING_ATTACHMENT_MAX_BYTES", 1
        )[0]
        self.assertIn("signatures.pop('acknowledged', None)", helper)
        self.assertNotIn("serviced", helper.split("signatures.pop", 1)[1])

        normal_route = self.app_source.split("@app.route('/save_offline_tsr_online'", 1)[1].split(
            "@app.route(", 1
        )[0]
        revision_route = self.app_source.split("@app.route('/revise_online_tsr_submission/<int:submission_id>'", 1)[1].split(
            "@app.route(", 1
        )[0]
        for route in (normal_route, revision_route):
            self.assertIn("online_tsr_has_serviced_signature(payload)", route)
            self.assertIn("online_tsr_has_acknowledged_signature(payload)", route)
            self.assertIn("ensure_authoritative_tsr_coverage_pdf", route)
            self.assertIn("strip_persisted_online_tsr_client_signature(payload)", route)
        self.assertIn("submission.payload_json = json.dumps", normal_route)
        self.assertIn("revision.payload_json = json.dumps", revision_route)

    def test_queue_retains_pending_signature_and_strips_after_core_confirmation(self):
        queue_fn = self.template.split("async function queueStandaloneTSROffline", 1)[1].split(
            "\nlet offlineTSRSyncRunning", 1
        )[0]
        self.assertIn("coreSaveConfirmed", queue_fn)
        self.assertIn("stripStandaloneTSRClientSignatureForCompletedQueuePayload", queue_fn)
        self.assertIn("server_submission_id", queue_fn)
        self.assertIn("sync_phase", queue_fn)
        self.assertIn("saveStandaloneTSRDraftLocally", queue_fn)

    def test_idempotent_response_is_metadata_only_and_pdf_consumers_are_file_based(self):
        response_fn = self.app_source.split("def completed_online_tsr_response", 1)[1].split(
            "\n\nTSR_DRAFT_MAX_PAYLOAD_BYTES", 1
        )[0]
        self.assertNotIn("'payload':", response_fn)
        repair_fn = self.app_source.split("def _tsr_repair_submission_file", 1)[1].split(
            "\ndef _tsr_repair_date_value", 1
        )[0]
        self.assertIn("ShiftFile", repair_fn)
        self.assertNotIn("online_tsr_has_acknowledged_signature", repair_fn)

    def test_remote_missing_signatures_merge_only_from_matching_non_revision_local_copy(self):
        for marker in (
            "mergeStandaloneTSRSignaturesFromLocal",
            "standaloneTSRRecoveryContextsMatch",
            "parent_submission_id",
            "_revision_of_submission_id",
            "remotePayload",
            "localPayload",
        ):
            self.assertIn(marker, self.template)
        merge_fn = self.template.split("function mergeStandaloneTSRSignaturesFromLocal", 1)[1].split(
            "\nasync function mergeServerStandaloneTSRDrafts", 1
        )[0]
        self.assertIn("localPayload", merge_fn)
        self.assertIn("remotePayload", merge_fn)

    def test_correction_reset_and_hydration_deletion_guard_remain(self):
        revision_loader = self.template.split("async function loadOnlineTSRRevisionFromUrl", 1)[1].split(
            "\nfunction captureStandaloneTSRLocalSaveContext", 1
        )[0]
        self.assertIn("signatureData.acknowledged = '';", revision_loader)
        hydration = self.template.split("async function mergeServerStandaloneTSRDrafts", 1)[1].split(
            "\nasync function refreshStandaloneTSRDraftPanel", 1
        )[0]
        self.assertIn("readStandaloneTSRServerDraftDeleteQueue", hydration)
        self.assertIn("pendingServerDraftDeletes.has(draftKey)", hydration)
        revision_finish = self.template.split("if(state.isRevision)", 1)[1].split(
            "\n  if(navigator.onLine)", 1
        )[0]
        self.assertIn("initializeBlankStandaloneTSR();", revision_finish)

    @unittest.skipUnless(NODE.exists(), f"Node runtime unavailable at {NODE}")
    def test_runtime_hydration_merge_preserves_only_matching_non_revision_local_signatures(self):
        script = f"""
const fs = require('fs');
const source = fs.readFileSync({json.dumps(str(ROOT / 'templates' / 'offline_tsr.html'))}, 'utf8');
function take(start, end) {{
  const at = source.indexOf(start);
  if(at < 0) throw new Error('missing ' + start);
  const next = end ? source.indexOf(end, at) : source.length;
  if(next < 0) throw new Error('missing end ' + end);
  return source.slice(at, next);
}}
function normalizeStandaloneDraftComparable(value) {{ return String(value || '').trim().toLowerCase().replace(/\\s+/g, ' '); }}
function buildStableScheduleOptionUid(schedule) {{
  if(!schedule) return '';
  const id = String(schedule.id || schedule.schedule_id || '').trim();
  const date = String(schedule.date_iso || schedule.start_date || '').slice(0, 10);
  return id ? `shift::${{id}}::${{date}}` : `snap::${{normalizeStandaloneDraftComparable(schedule.client_name)}}::${{date}}`;
}}
function isSameScheduleSelection(storedId, schedule) {{
  const stored = String(storedId || '').trim();
  const id = String(schedule?.id || schedule?.schedule_id || '').trim();
  return Boolean(stored && id && (stored === id || stored === buildStableScheduleOptionUid(schedule)));
}}
eval(take('function getStandaloneTSRSignatureRecoveryPayload', '\\nfunction getStandaloneTSRRecoverySignatures'));
eval(take('function getStandaloneTSRRecoverySignatures', '\\nfunction filterStandaloneTSRSignatureRecoveryCandidates'));
eval(take('function isStandaloneTSRUnfinishedSignatureRecoverySource', '\\nfunction buildStandaloneTSRSignatureRecoveryCandidate'));
eval(take('function filterStandaloneTSRSignatureRecoveryCandidates', '\\nfunction mergeStandaloneTSRRecoverySignatures'));
eval(take('function mergeStandaloneTSRRecoverySignatures', '\\nfunction mergeStandaloneTSRSignaturesFromLocal'));
eval(take('function mergeStandaloneTSRSignaturesFromLocal', '\\nfunction buildStandaloneTSRSignatureRecoveryCandidate'));
const remote = {{ schedule_id:'42', 'tsr-customer-name':'Client A', signatures:{{ serviced:'', acknowledged:'' }} }};
const matchingLocal = {{ schedule_id:'shift::42::2026-09-08', 'tsr-customer-name':'Client A', signatures:{{ serviced:'data:image/png;base64,eng', acknowledged:'data:image/png;base64,client' }} }};
const wrongSchedule = {{ schedule_id:'99', 'tsr-customer-name':'Client A', signatures:matchingLocal.signatures }};
const wrongClient = {{ schedule_id:'42', 'tsr-customer-name':'Client B', signatures:matchingLocal.signatures }};
const correctedRemote = {{ schedule_id:'42', 'tsr-customer-name':'Client A', parent_submission_id:123, signatures:{{ serviced:'', acknowledged:'' }} }};
console.log(JSON.stringify({{
  matching: mergeStandaloneTSRSignaturesFromLocal(remote, matchingLocal).signatures,
  wrongSchedule: mergeStandaloneTSRSignaturesFromLocal(remote, wrongSchedule).signatures,
  wrongClient: mergeStandaloneTSRSignaturesFromLocal(remote, wrongClient).signatures,
  corrected: mergeStandaloneTSRSignaturesFromLocal(correctedRemote, matchingLocal).signatures
}}));
"""
        result = subprocess.run([str(NODE), "-e", script], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout.strip())
        self.assertEqual(output["matching"]["serviced"], "data:image/png;base64,eng")
        self.assertEqual(output["matching"]["acknowledged"], "data:image/png;base64,client")
        self.assertEqual(output["wrongSchedule"], {"serviced": "", "acknowledged": ""})
        self.assertEqual(output["wrongClient"], {"serviced": "", "acknowledged": ""})
        self.assertEqual(output["corrected"], {"serviced": "", "acknowledged": ""})

    @unittest.skipUnless(NODE.exists(), f"Node runtime unavailable at {NODE}")
    def test_runtime_candidate_collection_rejects_completed_sources_and_never_fetches_history(self):
        script = f"""
const fs = require('fs');
const source = fs.readFileSync({json.dumps(str(ROOT / 'templates' / 'offline_tsr.html'))}, 'utf8');
function take(start, end) {{
  const at = source.indexOf(start);
  if(at < 0) throw new Error('missing ' + start);
  const next = end ? source.indexOf(end, at) : source.length;
  if(next < 0) throw new Error('missing end ' + end);
  return source.slice(at, next);
}}
function normalizeStandaloneDraftComparable(value) {{ return String(value || '').trim().toLowerCase().replace(/\\s+/g, ' '); }}
function buildStableScheduleOptionUid(schedule) {{
  if(!schedule) return '';
  const id = String(schedule.id || schedule.schedule_id || '').trim();
  const date = String(schedule.date_iso || schedule.start_date || '').slice(0, 10);
  return id ? `shift::${{id}}::${{date}}` : `snap::${{normalizeStandaloneDraftComparable(schedule.client_name)}}::${{date}}`;
}}
function isSameScheduleSelection(storedId, schedule) {{
  const stored = String(storedId || '').trim();
  const id = String(schedule?.id || schedule?.schedule_id || '').trim();
  return Boolean(stored && id && (stored === id || stored === buildStableScheduleOptionUid(schedule)));
}}
eval(take('function getStandaloneTSRSignatureRecoveryPayload', '\\nfunction getStandaloneTSRRecoverySignatures'));
eval(take('function getStandaloneTSRRecoverySignatures', '\\nfunction filterStandaloneTSRSignatureRecoveryCandidates'));
eval(take('function isStandaloneTSRUnfinishedSignatureRecoverySource', '\\nfunction buildStandaloneTSRSignatureRecoveryCandidate'));
eval(take('function filterStandaloneTSRSignatureRecoveryCandidates', '\\nfunction mergeStandaloneTSRRecoverySignatures'));
eval(take('function mergeStandaloneTSRRecoverySignatures', '\\nfunction isStandaloneTSRUnfinishedSignatureRecoverySource'));
eval(take('function isStandaloneTSRUnfinishedSignatureRecoverySource', '\\nfunction buildStandaloneTSRSignatureRecoveryCandidate'));
eval(take('function buildStandaloneTSRSignatureRecoveryCandidate', '\\nasync function collectStandaloneTSRSignatureCandidates'));
eval(take('async function collectStandaloneTSRSignatureCandidates', '\\nfunction getStandaloneTSRSignatureRecoveryMissingTargets'));
const OFFLINE_TSR_ACTIVE_DRAFT_ID = 'active';
let fetchCalls = 0;
globalThis.fetch = async () => {{ fetchCalls += 1; throw new Error('history fetch is forbidden'); }};
globalThis.loadStandaloneTSRDraftRecordsFromIndexedDB = async () => [{{
  id:'local',
  payload:{{ schedule_id:'42', 'tsr-customer-name':'Client A', signatures:{{ serviced:'data:image/png;base64,local', acknowledged:'' }} }}
}}, {{
  id:'account', source:'server_draft',
  payload:{{ schedule_id:'42', 'tsr-customer-name':'Client A', signatures:{{ serviced:'', acknowledged:'data:image/png;base64,account' }} }}
}}, {{
  id:'completed-draft', status:'completed',
  payload:{{ schedule_id:'42', 'tsr-customer-name':'Client A', signatures:{{ serviced:'data:image/png;base64,bad', acknowledged:'' }} }}
}}];
globalThis.loadOfflineTSRQueueStore = async () => [{{
  id:'pending', status:'pending',
  payload:{{ schedule_id:'42', 'tsr-customer-name':'Client A', signatures:{{ serviced:'', acknowledged:'data:image/png;base64,pending' }} }}
}}, {{
  id:'server-confirmed', status:'pending', server_submission_id:77,
  payload:{{ schedule_id:'42', 'tsr-customer-name':'Client A', signatures:{{ serviced:'data:image/png;base64,bad', acknowledged:'' }} }}
}}, {{
  id:'complete-queue', status:'completed', sync_phase:'complete',
  payload:{{ schedule_id:'42', 'tsr-customer-name':'Client A', signatures:{{ serviced:'data:image/png;base64,bad', acknowledged:'' }} }}
}}];
globalThis.loadStandaloneTSRDraftFromLocalStorageFallback = () => ({{
  _draft_id:'fallback', schedule_id:'42', 'tsr-customer-name':'Other Client', signatures:{{ serviced:'data:image/png;base64,wrong', acknowledged:'' }}
}});
(async () => {{
  const result = await collectStandaloneTSRSignatureCandidates({{ id:'target', payload:{{ schedule_id:'42', 'tsr-customer-name':'Client A', signatures:{{ serviced:'', acknowledged:'' }} }} }});
  console.log(JSON.stringify({{ ids:result.candidates.map(candidate => candidate.id), labels:result.candidates.map(candidate => candidate.sourceLabel), warnings:result.warnings, fetchCalls }}));
}})().catch(error => {{ console.error(error); process.exitCode = 1; }});
"""
        result = subprocess.run([str(NODE), "-e", script], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout.strip())
        self.assertEqual(output["ids"], ["local_draft:local", "server_draft:account", "local_queue:pending"])
        self.assertEqual(output["labels"], ["Saved device draft", "Account backup draft", "Queued offline TSR"])
        self.assertEqual(output["fetchCalls"], 0)
        self.assertIn("Completed online TSRs and revision history are not recovery sources", " ".join(output["warnings"]))

    def test_worker_and_published_release_are_current(self):
        self.assertIn("medical-service-pwa-offline-navigation-v148-calibration-report-signature-name-filename", self.app_source)
        self.assertNotIn("medical-service-pwa-offline-navigation-v145-tsr-signature-recovery", self.app_source)
        manifest = json.loads(self.release)
        matches = [
            release for release in manifest["releases"]
            if release.get("release_key") == "2026-09-08-tsr-signature-recovery"
        ]
        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0].get("is_published"))
        release_text = json.dumps(matches[0]).lower()
        self.assertIn("unfinished", release_text)
        self.assertIn("never recovery sources", release_text)

    @unittest.skipUnless(NODE.exists(), f"Node runtime unavailable at {NODE}")
    def test_runtime_context_filter_and_partial_selection_contract(self):
        script = f"""
const fs = require('fs');
const source = fs.readFileSync({json.dumps(str(ROOT / 'templates' / 'offline_tsr.html'))}, 'utf8');
function take(start, end) {{
  const at = source.indexOf(start);
  if(at < 0) throw new Error('missing ' + start);
  const next = end ? source.indexOf(end, at) : source.length;
  if(next < 0) throw new Error('missing end ' + end);
  return source.slice(at, next);
}}
function normalizeStandaloneDraftComparable(value) {{ return String(value || '').trim().toLowerCase().replace(/\\s+/g, ' '); }}
function buildStableScheduleOptionUid(schedule) {{
  if(!schedule) return '';
  const id = String(schedule.id || schedule.schedule_id || '').trim();
  const date = String(schedule.date_iso || schedule.start_date || '').slice(0, 10);
  return id ? `shift::${{id}}::${{date}}` : `snap::${{normalizeStandaloneDraftComparable(schedule.client_name)}}::${{date}}`;
}}
function isSameScheduleSelection(storedId, schedule) {{
  const stored = String(storedId || '').trim();
  const id = String(schedule?.id || schedule?.schedule_id || '').trim();
  return Boolean(stored && id && (stored === id || stored === buildStableScheduleOptionUid(schedule)));
}}
eval(take('function getStandaloneTSRSignatureRecoveryPayload', '\\nfunction getStandaloneTSRRecoverySignatures'));
eval(take('function getStandaloneTSRRecoverySignatures', '\\nfunction filterStandaloneTSRSignatureRecoveryCandidates'));
eval(take('function isStandaloneTSRUnfinishedSignatureRecoverySource', '\\nfunction buildStandaloneTSRSignatureRecoveryCandidate'));
eval(take('function filterStandaloneTSRSignatureRecoveryCandidates', '\\nfunction mergeStandaloneTSRRecoverySignatures'));
eval(take('function mergeStandaloneTSRRecoverySignatures', '\\nfunction '));
const target = {{
  schedule_id:'42',
  'tsr-customer-name':'Client A',
  selectedSchedule:{{ id:'42', client_id:'7', client_name:'Client A', date_iso:'2026-09-08' }}
}};
const same = {{ id:'draft-same', payload:{{ schedule_id:'42', 'tsr-customer-name':'Client A', selectedSchedule:{{ id:'42', client_id:'7', client_name:'Client A', date_iso:'2026-09-08' }}, signatures:{{ serviced:'data:image/png;base64,eng', acknowledged:'' }} }} }};
const wrongSchedule = {{ id:'draft-wrong-schedule', payload:{{ schedule_id:'99', 'tsr-customer-name':'Client A', selectedSchedule:{{ id:'99', client_id:'7', client_name:'Client A', date_iso:'2026-09-08' }}, signatures:{{ serviced:'data:image/png;base64,bad', acknowledged:'data:image/png;base64,bad' }} }} }};
const wrongClient = {{ id:'draft-wrong-client', payload:{{ schedule_id:'42', 'tsr-customer-name':'Client B', selectedSchedule:{{ id:'42', client_id:'8', client_name:'Client B', date_iso:'2026-09-08' }}, signatures:{{ serviced:'data:image/png;base64,bad', acknowledged:'data:image/png;base64,bad' }} }} }};
const filtered = filterStandaloneTSRSignatureRecoveryCandidates(target, [same, wrongSchedule, wrongClient]);
const partialCandidate = {{ serviced:'data:image/png;base64/other-eng', acknowledged:'data:image/png;base64,client' }};
const kept = mergeStandaloneTSRRecoverySignatures(
  {{ serviced:'data:image/png;base64,current-eng', acknowledged:'' }},
  {{ serviced:'data:image/png;base64/other-eng', acknowledged:'data:image/png;base64/client' }},
  ['serviced','acknowledged']
);
kept.acknowledged = mergeStandaloneTSRRecoverySignatures(kept, partialCandidate, ['acknowledged']).acknowledged;
console.log(JSON.stringify({{ ids:filtered.map(row => row.id), kept }}));
"""
        result = subprocess.run([str(NODE), "-e", script], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout.strip())
        self.assertEqual(output["ids"], ["draft-same"])
        self.assertEqual(output["kept"]["serviced"], "data:image/png;base64,current-eng")
        self.assertEqual(output["kept"]["acknowledged"], "data:image/png;base64,client")

    @unittest.skipUnless(NODE.exists(), f"Node runtime unavailable at {NODE}")
    def test_runtime_same_logical_id_sources_are_unique_and_missing_slot_filtered(self):
        script = f"""
const fs = require('fs');
const source = fs.readFileSync({json.dumps(str(ROOT / 'templates' / 'offline_tsr.html'))}, 'utf8');
function take(start, end) {{
  const at = source.indexOf(start);
  if(at < 0) throw new Error('missing ' + start);
  const next = end ? source.indexOf(end, at) : source.length;
  if(next < 0) throw new Error('missing end ' + end);
  return source.slice(at, next);
}}
function normalizeStandaloneDraftComparable(value) {{ return String(value || '').trim().toLowerCase().replace(/\\s+/g, ' '); }}
function buildStableScheduleOptionUid(schedule) {{
  if(!schedule) return '';
  const id = String(schedule.id || schedule.schedule_id || '').trim();
  const date = String(schedule.date_iso || schedule.start_date || '').slice(0, 10);
  return id ? `shift::${{id}}::${{date}}` : `snap::${{normalizeStandaloneDraftComparable(schedule.client_name)}}::${{date}}`;
}}
function isSameScheduleSelection(storedId, schedule) {{
  const stored = String(storedId || '').trim();
  const id = String(schedule?.id || schedule?.schedule_id || '').trim();
  return Boolean(stored && id && (stored === id || stored === buildStableScheduleOptionUid(schedule)));
}}
eval(take('function getStandaloneTSRSignatureRecoveryPayload', '\\nfunction getStandaloneTSRRecoverySignatures'));
eval(take('function getStandaloneTSRRecoverySignatures', '\\nfunction filterStandaloneTSRSignatureRecoveryCandidates'));
eval(take('function filterStandaloneTSRSignatureRecoveryCandidates', '\\nfunction mergeStandaloneTSRRecoverySignatures'));
eval(take('function isStandaloneTSRUnfinishedSignatureRecoverySource', '\\nfunction buildStandaloneTSRSignatureRecoveryCandidate'));
eval(take('function buildStandaloneTSRSignatureRecoveryCandidate', '\\nasync function collectStandaloneTSRSignatureCandidates'));
const context = {{ schedule_id:'3523', 'tsr-customer-name':'Client A', selectedSchedule:{{ id:'3523', client_id:'7', client_name:'Client A', date_iso:'2026-09-01' }} }};
const target = {{ id:'active', payload:Object.assign({{}}, context, {{ signatures:{{ serviced:'data:image/png;base64,current-eng', acknowledged:'' }} }}) }};
const device = buildStandaloneTSRSignatureRecoveryCandidate(
  {{ id:'active', payload:Object.assign({{}}, context, {{ signatures:{{ serviced:'data:image/png;base64,other-eng', acknowledged:'' }} }}) }},
  'local_draft', {{ id:'active' }}
);
const fallback = buildStandaloneTSRSignatureRecoveryCandidate(
  {{ _draft_id:'active', ...context, signatures:{{ serviced:'', acknowledged:'data:image/png;base64,client' }} }},
  'localstorage', {{ id:'active' }}
);
const filtered = filterStandaloneTSRSignatureRecoveryCandidates(target, [device, fallback]);
console.log(JSON.stringify({{ allIds:[device.id, fallback.id], ids:filtered.map(row => row.id) }}));
"""
        result = subprocess.run([str(NODE), "-e", script], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout.strip())
        self.assertEqual(len(output["allIds"]), len(set(output["allIds"])))
        self.assertTrue(output["allIds"][0].startswith("local_draft"))
        self.assertTrue(output["allIds"][1].startswith("localstorage"))
        self.assertEqual(len(output["ids"]), 1)
        self.assertTrue(output["ids"][0].startswith("localstorage"))

    def test_recovery_captures_fallback_before_async_queue_read_and_exposes_apply_reason(self):
        start = self.template.index("async function collectStandaloneTSRSignatureCandidates")
        recovery = self.template[start:self.template.index(
            "\nfunction getStandaloneTSRSignatureRecoveryMissingTargets", start
        )]
        fallback_read = recovery.index("loadStandaloneTSRDraftFromLocalStorageFallback")
        first_await = recovery.index("await ")
        self.assertLess(fallback_read, first_await)
        self.assertNotIn("saveOfflineTSRQueueToIndexedDB", recovery)
        for marker in (
            "getStandaloneTSRSignatureRecoveryApplyDecision",
            "tsr-signature-recovery-apply-reason",
            "aria-describedby",
            "Searching saved signatures",
            "No saved source found",
            "Choose a saved source",
            "Selected source lacks",
            "state.selectedSourceId",
            "state.selectedTargets",
        ):
            self.assertIn(marker, self.template)

    @unittest.skipUnless(NODE.exists(), f"Node runtime unavailable at {NODE}")
    def test_runtime_apply_state_disables_incomplete_states_and_enables_valid_selection(self):
        script = f"""
const fs = require('fs');
const source = fs.readFileSync({json.dumps(str(ROOT / 'templates' / 'offline_tsr.html'))}, 'utf8');
function take(start, end) {{
  const at = source.indexOf(start);
  if(at < 0) throw new Error('missing ' + start);
  const next = end ? source.indexOf(end, at) : source.length;
  if(next < 0) throw new Error('missing end ' + end);
  return source.slice(at, next);
}}
eval(take('function getStandaloneTSRSignatureRecoveryApplyDecision', '\\nfunction updateStandaloneTSRSignatureRecoveryApplyState'));
eval(take('function getStandaloneTSRSignatureRecoveryPayload', '\\nfunction getStandaloneTSRRecoverySignatures'));
eval(take('function getStandaloneTSRRecoverySignatures', '\\nfunction filterStandaloneTSRSignatureRecoveryCandidates'));
const sourceWithClient = {{ id:'localstorage:active', signatures:{{ serviced:'', acknowledged:'data:image/png;base64,client' }} }};
const ready = {{ loading:false, candidates:[sourceWithClient], missingTargets:['serviced','acknowledged'] }};
const states = {{
  loading: getStandaloneTSRSignatureRecoveryApplyDecision({{ ...ready, loading:true }}, ['acknowledged'], sourceWithClient.id, {{ active:true, busy:false }}),
  noSource: getStandaloneTSRSignatureRecoveryApplyDecision({{ ...ready, candidates:[] }}, ['acknowledged'], '', {{ active:true, busy:false }}),
  noTarget: getStandaloneTSRSignatureRecoveryApplyDecision(ready, [], sourceWithClient.id, {{ active:true, busy:false }}),
  partial: getStandaloneTSRSignatureRecoveryApplyDecision(ready, ['serviced'], sourceWithClient.id, {{ active:true, busy:false }}),
  stale: getStandaloneTSRSignatureRecoveryApplyDecision(ready, ['acknowledged'], sourceWithClient.id, {{ active:false, busy:false }}),
  valid: getStandaloneTSRSignatureRecoveryApplyDecision(ready, ['acknowledged'], sourceWithClient.id, {{ active:true, busy:false }})
}};
console.log(JSON.stringify(states));
"""
        result = subprocess.run([str(NODE), "-e", script], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout.strip())
        for key in ("loading", "noSource", "noTarget", "partial", "stale"):
            self.assertTrue(output[key]["disabled"], key)
            self.assertTrue(output[key]["reason"], key)
        self.assertFalse(output["valid"]["disabled"])


    @unittest.skipUnless(NODE.exists(), f"Node runtime unavailable at {NODE}")
    def test_runtime_queue_signature_is_retained_until_core_success_then_removed(self):
        script = f"""
const fs = require('fs');
const source = fs.readFileSync({json.dumps(str(ROOT / 'templates' / 'offline_tsr.html'))}, 'utf8');
function take(start, end) {{
  const at = source.indexOf(start);
  if(at < 0) throw new Error('missing ' + start);
  const next = end ? source.indexOf(end, at) : source.length;
  if(next < 0) throw new Error('missing end ' + end);
  return source.slice(at, next);
}}
eval(take('function stripStandaloneTSRClientSignatureForCompletedQueuePayload', '\\nasync function queueStandaloneTSROffline'));
const pending = {{ signatures:{{ serviced:'data:image/png;base64,eng', acknowledged:'data:image/png;base64,client' }}, state:'pending' }};
const completed = stripStandaloneTSRClientSignatureForCompletedQueuePayload(pending);
console.log(JSON.stringify({{ pending:pending.signatures, completed:completed.signatures }}));
"""
        result = subprocess.run([str(NODE), "-e", script], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout.strip())
        self.assertEqual(output["pending"]["acknowledged"], "data:image/png;base64,client")
        self.assertNotIn("acknowledged", output["completed"])
        self.assertEqual(output["completed"]["serviced"], "data:image/png;base64,eng")


@unittest.skipIf(APP_IMPORT_ERROR is not None, f"app.py import unavailable: {APP_IMPORT_ERROR}")
class TsrSignatureSubmissionRouteTests(unittest.TestCase):
    """Exercise final/revision persistence with a disposable external database."""

    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config["TESTING"] = True
        cls.app.config["WTF_CSRF_ENABLED"] = False
        cls.suffix = uuid4().hex[:10]
        with cls.app.app_context():
            app_module.db.create_all()
            user = app_module.User(
                username=f"tsr-signature-route-{cls.suffix}",
                password="test-password",
                role="engineer",
                is_active=True,
            )
            app_module.db.session.add(user)
            app_module.db.session.flush()
            engineer = app_module.Engineer(
                user_id=user.id,
                employee_id=f"TSR-SIGNATURE-{cls.suffix}",
                name="TSR Signature Route Engineer",
                initials="TSR",
                branch="Manila",
            )
            client = app_module.Client(
                name=f"TSR Signature Route Client {cls.suffix}",
                address="Signature route client address",
            )
            app_module.db.session.add_all([engineer, client])
            app_module.db.session.flush()
            shift = app_module.Shift(
                title=f"TSR signature route shift {cls.suffix}",
                start_time=datetime.combine(app_module.get_manila_today(), time(8, 0)),
                end_time=datetime.combine(app_module.get_manila_today(), time(17, 0)),
                engineer_id=engineer.id,
                client_id=client.id,
                status="In Progress",
            )
            app_module.db.session.add(shift)
            app_module.db.session.commit()
            cls.user_id = user.id
            cls.shift_id = shift.id
            cls.engineer_id = engineer.id
            cls.client_id = client.id
            cls.submission_ids = []

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            for submission_id in getattr(cls, "submission_ids", []):
                submission = app_module.db.session.get(app_module.OnlineTsrSubmission, submission_id)
                if submission:
                    app_module.db.session.delete(submission)
            shift = app_module.db.session.get(app_module.Shift, getattr(cls, "shift_id", None))
            if shift:
                app_module.db.session.delete(shift)
            client = app_module.db.session.get(app_module.Client, getattr(cls, "client_id", None))
            if client:
                app_module.db.session.delete(client)
            engineer = app_module.db.session.get(app_module.Engineer, getattr(cls, "engineer_id", None))
            if engineer:
                app_module.db.session.delete(engineer)
            user = app_module.db.session.get(app_module.User, getattr(cls, "user_id", None))
            if user:
                app_module.db.session.delete(user)
            app_module.db.session.commit()
            app_module.db.session.remove()

    def setUp(self):
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.user_id)
            session["_fresh"] = True

    def payload(self, token):
        return {
            "schedule_id": self.shift_id,
            "selectedScheduleId": self.shift_id,
            "selectedSchedule": {
                "id": self.shift_id,
                "client_id": self.client_id,
                "client_name": f"TSR Signature Route Client {self.suffix}",
                "date_iso": app_module.get_manila_today().isoformat(),
            },
            "tsr-service-date": app_module.get_manila_today().isoformat(),
            "tsr-customer-name": f"TSR Signature Route Client {self.suffix}",
            "tsr-serviced-by": "TSR Signature Route Engineer",
            "tsr-equipment-model": "Route Model",
            "tsr-serial-no": "ROUTE-SERIAL",
            "_tsr_form_version": "vector-pdf-v2",
            "submission_token": token,
            "signatures": {
                "serviced": "data:image/png;base64,engineer",
                "acknowledged": "data:image/png;base64,client",
            },
        }

    def route_patches(self, generated_name="signed.pdf"):
        attached = SimpleNamespace(
            id=990001,
            filename=generated_name,
            original_filename=generated_name,
            online_tsr_submission_id=None,
        )
        return patch.multiple(
            app_module,
            can_work_on_existing_schedule_shift=lambda shift: True,
            get_tsr_schedule_coverage_rows=lambda shift: [],
            get_online_tsr_missing_core_details=lambda shift, payload: [],
            ensure_product_from_tsr_payload=lambda shift, payload: {"status": "not_required"},
            get_latest_online_tsr_submission_for_shift=lambda shift_id: None,
            mark_existing_online_tsr_submissions_superseded=lambda shift_id, exclude_submission_id=None: 0,
            generate_online_tsr_submission_pdf=lambda submission, shift, payload: generated_name,
            attach_online_tsr_pdf_to_shift=lambda shift, filename: attached,
            attach_uploaded_online_tsr_extra_files_to_shift=lambda shift, excluded_file_ids=None: [],
            update_shift_time_from_online_tsr_payload=lambda shift, payload: {},
            complete_schedules_for_online_tsr=lambda shift, completion_scope="linked_all": [],
            complete_linked_schedules_for_online_tsr=lambda shift: [],
            save_tsr_payload_contact_to_medical_center=lambda shift, payload, source_label="": [],
            auto_capture_tsr_client_contact_from_payload=lambda shift, payload: [],
            get_shift_file_display_name=lambda file_rec: generated_name,
            tsr_knowledge_current_engineer_name=lambda: "TSR Signature Route Engineer",
            online_tsr_next_number_for_date=lambda value: "TSR-ROUTE-001",
            online_tsr_submitted_number_is_available=lambda value, sequence_date: True,
            correct_product_from_tsr_revision=lambda shift, payload: None,
        )

    def test_online_success_persists_signed_pdf_input_without_client_signature_and_replays_idempotently(self):
        token = f"route-online-{uuid4().hex}"
        payload = self.payload(token)
        with self.app.app_context(), self.route_patches(), patch.object(
            app_module,
            "generate_online_tsr_submission_pdf",
            return_value="signed-online.pdf",
        ) as generated:
            response = self.client.post("/save_offline_tsr_online", json=payload)
            self.assertEqual(response.status_code, 200, response.get_json())
            submission_id = response.get_json()["submission_id"]
            self.submission_ids.append(submission_id)
            generated.assert_called_once()
            self.assertIn("acknowledged", generated.call_args.args[2]["signatures"])
            stored = app_module.db.session.get(app_module.OnlineTsrSubmission, submission_id)
            persisted = json.loads(stored.payload_json)
            self.assertNotIn("acknowledged", persisted["signatures"])
            self.assertEqual(persisted["signatures"]["serviced"], payload["signatures"]["serviced"])
            self.assertEqual(persisted["_generated_pdf_filename"], "signed-online.pdf")

            replay = self.client.post("/save_offline_tsr_online", json=payload)
            self.assertEqual(replay.status_code, 200, replay.get_json())
            self.assertTrue(replay.get_json()["duplicate"])
            self.assertNotIn("payload", replay.get_json())

    def test_revision_success_strips_client_signature_and_requires_it_before_save(self):
        original_token = f"route-original-{uuid4().hex}"
        with self.app.app_context(), self.route_patches("signed-original.pdf"):
            original_response = self.client.post(
                "/save_offline_tsr_online",
                json=self.payload(original_token),
            )
            self.assertEqual(original_response.status_code, 200, original_response.get_json())
            original_id = original_response.get_json()["submission_id"]
            self.submission_ids.append(original_id)

        revision_token = f"route-revision-{uuid4().hex}"
        revision_payload = self.payload(revision_token)
        revision_payload["revision_reason"] = "Corrected signature lifecycle test"
        with self.app.app_context(), self.route_patches("signed-revision.pdf"), patch.object(
            app_module,
            "get_latest_online_tsr_submission_for_shift",
            lambda shift_id: app_module.db.session.get(app_module.OnlineTsrSubmission, original_id),
        ), patch.object(
            app_module,
            "generate_online_tsr_submission_pdf",
            return_value="signed-revision.pdf",
        ) as generated:
            response = self.client.post(
                f"/revise_online_tsr_submission/{original_id}",
                json=revision_payload,
            )
            self.assertEqual(response.status_code, 200, response.get_json())
            revision_id = response.get_json()["submission_id"]
            self.submission_ids.append(revision_id)
            generated.assert_called_once()
            self.assertIn("acknowledged", generated.call_args.args[2]["signatures"])
            persisted = json.loads(app_module.db.session.get(app_module.OnlineTsrSubmission, revision_id).payload_json)
            self.assertNotIn("acknowledged", persisted["signatures"])
            self.assertEqual(persisted["signatures"]["serviced"], revision_payload["signatures"]["serviced"])

            rejected_payload = dict(revision_payload)
            rejected_payload["submission_token"] = f"route-rejected-{uuid4().hex}"
            rejected_payload["signatures"] = {"serviced": revision_payload["signatures"]["serviced"]}
            rejected = self.client.post(
                f"/revise_online_tsr_submission/{original_id}",
                json=rejected_payload,
            )
            self.assertEqual(rejected.status_code, 400)
            self.assertIn("Acknowledged By client signature", rejected.get_json()["message"])

    def test_online_failure_rolls_back_without_completed_submission(self):
        token = f"route-failure-{uuid4().hex}"
        with self.app.app_context(), self.route_patches(), patch.object(
            app_module,
            "generate_online_tsr_submission_pdf",
            side_effect=RuntimeError("signed PDF failed"),
        ):
            response = self.client.post(
                "/save_offline_tsr_online",
                json=self.payload(token),
            )
            self.assertEqual(response.status_code, 500, response.get_json())
            self.assertFalse(
                app_module.OnlineTsrSubmission.query.filter_by(submission_token=token).first()
            )


@unittest.skipIf(APP_IMPORT_ERROR is not None, f"app.py import unavailable: {APP_IMPORT_ERROR}")
class TsrSignaturePayloadHelperTests(unittest.TestCase):
    def test_persisted_payload_removes_only_client_signature_after_signed_pdf_path(self):
        payload = {
            "signatures": {
                "serviced": "data:image/png;base64,engineer",
                "acknowledged": "data:image/png;base64,client",
            },
            "tsr-customer-name": "Client A",
            "_generated_pdf_filename": "signed.pdf",
        }
        persisted = app_module.strip_persisted_online_tsr_client_signature(payload)
        self.assertEqual(persisted["signatures"]["serviced"], payload["signatures"]["serviced"])
        self.assertNotIn("acknowledged", persisted["signatures"])
        self.assertEqual(persisted["tsr-customer-name"], "Client A")
        self.assertIn("acknowledged", payload["signatures"])
        self.assertTrue(app_module.online_tsr_has_serviced_signature(payload))
        self.assertTrue(app_module.online_tsr_has_acknowledged_signature(payload))
        self.assertFalse(app_module.online_tsr_has_acknowledged_signature(persisted))


if __name__ == "__main__":
    unittest.main()
