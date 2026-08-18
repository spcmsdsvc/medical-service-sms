# Medical Service SMS — Approved Plans

Plans the project owner has approved, recorded in full **before** any of the work starts.

Companion to the other two journals:

| File | Answers |
| --- | --- |
| `plans.md` | what was **agreed and is waiting to be built** |
| `changes.md` | what **was** done |
| `pending-work.md` | what is **still open** |

**The rule this file exists for: approval of a plan is not permission to execute it.**
When a plan is approved, it gets written here in full and then work **stops** until the owner
separately says to start. See `AGENTS.md`, "Approved Plans", for the full statement.

## How to use this file

- Newest plan at the top, matching the convention in `changes.md`.
- Record the plan as approved, not a summary of it. Enough detail that someone else could
  execute it without the conversation that produced it: the files to touch, the reasoning
  behind the approach, what is deliberately excluded, and how it will be verified.
- Every plan carries a **Status** line, kept current:

| Status | Meaning |
| --- | --- |
| `Approved — awaiting go-ahead` | Agreed and recorded. **Do not start.** |
| `In progress` | The owner said to start. |
| `Executed` | Finished, with the commit hash. |
| `Superseded` / `Abandoned` | Say what replaced it, or why it was dropped. |

- When a plan is executed, leave it here with its commit hash rather than deleting it. The
  record of what was agreed is worth as much afterwards as before, especially where the plan
  and the outcome differed.
- If the work turns out to need something the plan did not cover, note it under the plan
  rather than quietly widening the scope.

### Required structure

Every plan is written to be **executed by someone who was not in the conversation**. Prose alone
is not enough: the execution steps must be numbered task bullets that can be worked through and
ticked off, and the plan must say what happens *after* the code is written, not only during.

| Section | What it must contain |
| --- | --- |
| **Status / dates** | The status line, when approved, when detailed, when finished with its commit. |
| **Context** | The problem, what prompted it, and the intended outcome. Why now. |
| **Decisions taken** | What the owner settled, so an executor does not reopen it. |
| **Investigation** | What was verified in the code, with `file:line`. Findings that changed the approach belong here, including anything that turned out **not** to be true. |
| **Execution steps** | **Numbered tasks, in order**, each naming the files and functions it touches and what "done" looks like. Small enough to finish and check one at a time. |
| **Deliberately excluded** | What is out of scope and the reason, so it reads as a decision rather than an oversight. |
| **Verification** | Tests to add, each with the positive control that proves it can fail; the browser sequence; the standing bar (375 px, tap targets, console, suite count). |
| **After implementation** | The review and release workflow below, made concrete for this plan. |
| **Risks** | What could go wrong, what the blast radius is, and what the safety net is. |

### After implementation — the workflow every plan ends with

## Fix Approval Center notification 500s caused by missing event metadata

**Status:** `Executed — 12682f2`
**Status-format note:** The owner explicitly required the ASCII-hyphen spelling for the approval
status on 2026-08-18; this records that historical approval form while the lifecycle status below
remains authoritative.
**Approved:** 2026-08-18
**Amended and re-approved:** 2026-08-18, after Builder pre-execution validation confirmed the
source assumptions but found test-environment, line-ending, status, isolation, and dirty-worktree
requirements that needed to be made accurate before execution.
**Execution authorization:** Granted separately by the owner on 2026-08-18 for correction
implementation, isolated verification, commit, and push to `origin/main`. Deployment operations
beyond the normal push trigger and production access remain unauthorized.
**Environment gate:** Satisfied on 2026-08-18 by the separately authorized project-local Python
3.11.9 environment bootstrap.
**Implementation verification note (2026-08-18):** The approved correction is implemented and
verified with focused and full isolated tests, and is committed as `12682f2`. The owner-authorized
push to `origin/main` completed with remote-ref verification. Railway deployment metadata could not
be independently verified because the Railway CLI is unavailable in this environment; deployment
operations beyond the normal push trigger and production work remain separate actions.

### Context

The supplied Approval Center screenshot shows the page itself loading while the **Approval
Notifications** panel renders the beginning of Flask's HTML `500 Internal Server Error` response.
An authorized approver's notification request must remain a valid JSON response when an unread
notification has missing, blank, null-like, or legacy metadata. An unusable notification must be
ignored by the approval-scope matcher instead of failing the entire panel.

Valid approval notifications for currently supported modules must continue to appear only when
their backing request is Submitted and the signed-in user may approve it. Authentication, routing,
workflow statuses, stored notification rows, and unrelated page behavior remain unchanged.

### Decisions taken

Owner approval and re-approval on 2026-08-18 settle the following:

1. Use the approved **shortened workflow B**: Builder implementation, focused/full testing, and a
   Builder report. A later Planner review is optional unless separately requested.
2. Correct the server-side exception inside
   `approval_notification_is_active_for_current_user()` rather than masking this failure in the
   frontend.
3. Normalize missing or blank `module` and `metadata.event` values to empty comparison keys before
   calling `.lower()`.
4. Treat incomplete notifications as non-matches without deleting, repairing, backfilling, marking
   read, or otherwise mutating them.
5. Preserve all existing predicates and event values for Travel Request, Reimbursement, Cash
   Advance, Travel Liquidation, and Cash Advance Liquidation.
6. Do not add Leave Request or LPR matcher branches. Their Approval Notifications completeness gap
   needs separate workflow-specific authorization and compatibility analysis.
7. Do not change the shared frontend JSON parser. The displayed HTML is a symptom of the server
   exception.
8. Cover both consumers of the matcher: notification loading and scoped mark-all-read.
9. Require focused and full isolated tests; do not lower the test bar because the environment is
   currently unavailable.
10. Do not bump `CACHE_VERSION`; no cached template, static asset, app shell, or worker behavior
    changes.
11. Do not install Python, download packages, or modify a shared/system runtime without separate
    environment-bootstrap authorization.

### Revalidated investigation

1. `clean_str()` returns `None` for `None`, blank strings, and null-like strings
   (`app.py:5004-5010`).
2. `approval_notification_is_active_for_current_user()` currently performs unsafe
   `clean_str(...).lower()` calls for the module and `metadata.event`
   (`app.py:10269-10276`). Missing event metadata deterministically raises
   `AttributeError: 'NoneType' object has no attribute 'lower'`.
3. `/get_my_approval_notifications` loads unread candidates with no module restriction and filters
   each through this matcher (`app.py:10348-10355`, `app.py:10366-10377`). One incomplete row can
   fail the complete response.
4. `/mark_scoped_notifications_read` uses the same matcher before applying read state
   (`app.py:10420-10450`), so Mark All Read can fail for the same reason.
5. Current Leave Request and LPR awaiting-approval producers omit event metadata
   (`leave_feature.py:1079`, `app.py:55668`).
6. The matcher has branches only for Travel Request, Reimbursement, Cash Advance, Travel
   Liquidation, and Cash Advance Liquidation (`app.py:10278-10323`). The correction stops the
   exception but does not make Leave Request or LPR appear in this panel.
7. `parseApprovalJsonResponse()` carries non-JSON response text into an error
   (`templates/approvals.html:2492-2509`), and the notification loader escapes and renders it
   (`templates/approvals.html:5548-5561`). That explains the visible HTML but is not the originating
   defect.
8. `tests/test_approval_notifications.py` does not exist. Existing safe login, approver, and
   positive-control patterns are available in `tests/test_dashboard_manager.py`.
9. The repository has no `venv/`, `.venv/`, `env/`, or project `pyvenv.cfg`. System `python` is an
   unavailable Microsoft Store alias. The Codex bundled Python is 3.12.13 and lacks Flask and its
   extensions. `runtime.txt` declares Python 3.11.9.
10. The cited `tests/test_dashboard_manager.py`, `tests/__init__.py`, and
    `tests/test_approval_center_wording.py` are UTF-8 without BOM and LF-only. Across the current
    test suite, 55 Python files are LF-only, seven CRLF-only, and two mixed. The original plan's
    CRLF requirement was factually wrong.
11. `tests/__init__.py:32-58` registers a broad stale-test-file cleanup only when
    `MEDICAL_SERVICE_TEST_DB` is absent. Setting an explicit unique test path before Python starts
    bypasses that cleanup and permits exact current-run deletion under the current project rule.
12. `app.py` is CRLF/no BOM. `static/changelog/releases.json`, `plans.md`, and `changes.md` are
    LF/no BOM. Each must retain its existing convention.
13. `core.autocrlf=true` emits expected LF-to-CRLF conversion notices for the mandated LF journals
    even when `git diff --check` exits 0. Verification must distinguish conversion notices from
    whitespace errors and confirm bytes directly.
14. Current dirty baseline at re-approval:
    - branch `agent/leave-request-1-5-day`, ahead of its upstream by one commit;
    - modified `changes.md`, `plans.md`, and protected `scheduler.db`;
    - untracked `.claude/`, the loose root handoff, `output/`, and `tmp/`;
    - no staged files and no relevant application/test source diff.
    These artifacts must be preserved and must not be broadly staged.
15. No production logs, database rows, Railway state, or real business data were inspected. The
    current source contains a deterministic failure consistent with the screenshot, but the plan
    does not claim which production row triggered it.

### Affected files and artifacts

| Path | Approved execution change |
| --- | --- |
| `app.py` | Null-safe normalization of two comparison keys inside `approval_notification_is_active_for_current_user()` only. Preserve CRLF/no BOM. |
| `tests/test_approval_notifications.py` | New behavioral regression module. Use UTF-8 without BOM and LF to match the cited sibling and prevailing test convention. |
| `static/changelog/releases.json` | Add the required approver-facing release item during authorized execution. Preserve LF/no BOM. |
| `changes.md` | Record implementation, exact validation, exclusions, environment setup if any, and release relevance. Preserve LF/no BOM. |
| `plans.md` | Maintain this plan's permitted status lifecycle and record the eventual commit only when separately authorized. Preserve LF/no BOM. |
| `venv/` | Conditional ignored local environment only if its creation and dependency installation are separately authorized. |

No template, schema, migration, database, upload, storage, dependency declaration, service-worker,
Railway configuration, or production file is approved for modification.

### Preconditions

1. The owner must provide a future explicit `ROLE: BUILDER` and an execution instruction such as
   `execute`, `do it`, `go ahead`, or `start`.
2. A project-local Python 3.11.9 environment must be available.
3. If no environment is provided, the owner must separately authorize:
   - obtaining or installing a compatible Python 3.11.9 interpreter;
   - creating ignored `venv/`; and
   - installing only `requirements.txt` into that environment.
4. Do not install packages into the Codex bundled runtime or a shared/global Python installation.
5. Verify that the project venv can import Flask and all declared Flask extensions before any
   application edit.
6. If environment provisioning is not authorized or fails, stop without changing application or
   test code.

### Execution steps

1. [x] **Builder preflight**
   - Re-read `AGENTS.md`, this amended plan, and `changes.md` in full.
   - Recheck source, branch, status, staged diff, and the dirty baseline.
   - Confirm no relevant source changed after this amendment. If an assumption changed materially,
     stop and report the conflict instead of adapting silently.
   - Preserve every protected or unrelated artifact.
   - Set the plan to `In progress` only after both correction execution and any necessary
     environment-bootstrap authority exist.

2. [x] **Validate or conditionally provision the test environment**
   - Use `venv\Scripts\python.exe` backed by Python 3.11.9.
   - If separately authorized to bootstrap it, create only ignored `venv/` and install
     `requirements.txt` without editing dependency files.
   - Confirm the interpreter version and required imports; record the validation.
   - Do not start Flask, bind port 5000, or access an external service.

3. [x] **Establish isolated test runs**
   - Before each Python process starts, set `MEDICAL_SERVICE_TEST_DB` to a unique verified path
     under the system temporary directory.
   - Use different paths for the focused and full-suite processes.
   - Set the variable externally before importing the `tests` package or `app.py`. This prevents
     `tests/__init__.py` from registering its broad stale-file sweep.
   - After each process ends, verify the exact database path and remove only that database and its
     exact `-wal`/`-shm` sidecars after confirming no writer remains.
   - Never point the variable at `scheduler.db`, `/data`, a backup, a shared fixture, or a persistent
     owner file.

4. [x] **Add the focused regression test first**
   - Create LF/no-BOM `tests/test_approval_notifications.py` using the existing Flask login and
     fixture patterns.
   - Seed an active legacy approval manager, an ordinary requester, a minimal Submitted
     `ReimbursementHeader`, and a valid unread reimbursement notification whose `metadata_json`
     contains `{"event": "submitted"}`. This valid row is the required positive control.
   - Seed an unread notification for the same approver with no event metadata, using a current shape
     such as `module='leave_request'`, plus any unrelated row required to prove scoped read behavior.
   - Before editing `app.py`, run the focused test and record the expected 500 or propagated
     `AttributeError`. An import/setup failure is not a valid red test.
   - Clean up only rows created by this module and restore altered configuration. Do not broadly
     delete rows or assume the suite database is disposable.

5. [x] **Apply the surgical server correction**
   - In `approval_notification_is_active_for_current_user()` only, change module normalization to
     the equivalent of `(clean_str(getattr(notification, 'module', None)) or '').lower()`.
   - Change event normalization to the equivalent of
     `(clean_str(metadata.get('event')) or '').lower()`.
   - Preserve CRLF/no BOM for `app.py`.
   - Do not alter supported-module branches, accepted event sets, database lookups, Submitted-state
     checks, authorization helpers, callers, serialization, query limits, or read mutations.
   - Done means missing/blank/null-like module or event values fall through to `False`; valid
     `submitted` and `liquidation_submitted` comparisons behave exactly as before.

6. [x] **Run focused behavioral verification**
   - GET `/get_my_approval_notifications` as the approver and assert HTTP 200, JSON
     `success: true`, inclusion of the valid reimbursement notification, exclusion of the
     missing-event notification, and counts consistent with active included rows.
   - POST `/mark_scoped_notifications_read` with `{"scope":"approval"}` and assert HTTP 200,
     the valid active row is counted and marked read, and missing-event/unrelated rows remain
     unread.
   - Verify that an active non-approver receives HTTP 403 from both endpoints. Keep an approver
     success assertion in the same fixture so denial cannot pass because setup or login is broken.
   - Rerun the complete focused module after the fix.

7. [x] **Run proportional verification**
   - Run `venv\Scripts\python.exe -m py_compile app.py`.
   - Run the focused module through `unittest` with its explicit isolated database.
   - Run `unittest discover -s tests` through the project venv with a second explicit isolated
     database.
   - A failure involving the corrected behavior blocks completion. Any unrelated full-suite failure
     must be reported exactly and requires owner acceptance; it may not be described as passing.

8. [x] **Record release and journal work during execution**
   - Append to the current Manila-date `changes.md` section, or create a new newest-date section if
     execution occurs later. Record files, behavior, test environment, exact tests/results,
     schema/storage/auth/cache impact, exclusions, and uncommitted/unpublished state.
   - Add one correctly dated approver-facing item to `static/changelog/releases.json` following
     `static/changelog/README.md`.
   - Validate JSON, required keys, key uniqueness, audience, and the reserved `app-` namespace.
   - Reconcile the release date before any later authorized publication if execution and release
     dates differ.
   - Do not edit `pending-work.md`, any handoff, dependency declarations, or cache version.

9. [x] **Final diff and status audit**
   - Inspect exact unstaged and staged file lists; nothing may be staged without commit authority.
   - Run `git diff --check` and require exit code 0 with no whitespace errors.
   - Treat `core.autocrlf` conversion notices separately; do not normalize mandated LF files merely
     to suppress them.
   - Byte-check: `app.py` remains CRLF/no BOM; the new test is LF/no BOM; and
     `releases.json`, `plans.md`, and `changes.md` remain LF/no BOM.
   - Check `git diff --numstat` and the actual diff for whole-file churn.
   - Confirm `scheduler.db` and all existing untracked/protected artifacts remain untouched and
     unstaged.

10. [x] **Report and stop**
    - Provide the Builder report with every test run, passed, failed, skipped, or omitted;
      environment details; manual checks; deviations; and remaining concerns.
    - If implementation is verified but no commit is authorized, keep status `In progress` and
      append a dated note that implementation is verified but awaiting commit authorization.
    - Change status to `Executed — <commit>` only after a separately authorized commit exists.
    - Stop before commit, push, deployment, production access, Railway changes, or browser
      verification.

### Deliberately excluded

- Leave Request or LPR active-notification matcher branches.
- General null-safety changes to other `clean_str(...).lower()` call sites, including missing-scope
  handling.
- Frontend parser, template, toast/modal, or error-display changes.
- Notification producer changes or notification-row backfill, repair, deletion, or cleanup.
- Approval routing, permissions, roles, status transitions, request state, email, audit, or queue
  changes.
- Schema or migration work.
- Default/local/production database inspection or mutation.
- Storage, Railway, service-worker, cache, dependency-file, or architecture changes.
- Browser automation.
- `pending-work.md`, handoffs, and unrelated dirty artifacts.
- Installing Python or dependencies unless separately authorized.

### Verification requirements

1. A valid pre-fix regression failure, not an environment/import failure.
2. Focused endpoint, persisted read-state, positive-control, and authorization tests pass after the
   correction.
3. The full isolated suite passes, or unrelated failures are precisely reported and accepted.
4. `app.py` compiles through the project venv.
5. Release JSON parses and uses unique, compliant keys.
6. `git diff --check` exits 0 with no whitespace errors; expected `core.autocrlf` conversion notices
   are documented rather than suppressed through line-ending changes.
7. Required encodings and per-file line endings are preserved.
8. The final diff contains only approved files and no whole-file churn.
9. No protected database, secret, output, handoff, or unrelated artifact is staged or modified.

No browser verification is required or authorized for this server-only correction. If the owner
later separately authorizes browser verification, use a non-5000 port, an explicit isolated
`MEDICAL_SERVICE_TEST_DB`, and synthetic fixtures; confirm the panel loads without raw HTML and
Mark All Read remains functional; then stop only the verified test server. Browser authorization
does not authorize production access.

### Completion criteria

- Missing or null-like notification metadata cannot raise from either approval-scoped endpoint.
- A valid active Submitted reimbursement notification remains visible and markable for an eligible
  approver.
- Incomplete and unrelated notifications are not returned or marked read.
- Non-approvers remain denied.
- Tests use externally pinned, unique disposable databases and exact cleanup.
- Required focused/full validation and documentation are truthfully complete.
- No excluded or separately authorized action occurred.

### After implementation

The approved shortened workflow ends with the Builder's verified report unless the owner requests
a Planner review. The Builder must still stop before every separately controlled action.

Still separately authorized:

- **Environment bootstrap:** obtaining/installing Python, creating `venv/`, or downloading packages.
- **Execution:** a future explicit `ROLE: BUILDER` and owner go-ahead.
- **Commit:** a separate explicit commit instruction and exact-path staging review.
- **Push/publication:** separate push authorization; pushing `origin/main` is production-affecting.
- **Deployment operations:** manual redeploy, rollback, Railway variables/settings, domains,
  volumes, scaling, and cache controls.
- **Data/production work:** production logs or database reads, migrations, repairs, cleanup,
  backups, restores, and storage changes.
- **Browser verification:** separate authorization under the project safety rule.

### Risks and controls

| Risk | Control |
| --- | --- |
| Null fallback hides valid notifications. | Restrict the code change to two expressions and require a real Submitted reimbursement positive control. |
| GET works but mark-all-read still fails. | Exercise both endpoints and inspect persisted read state. |
| Leave/LPR scope expands accidentally. | Explicitly exclude new matcher branches. |
| Test run touches owner data. | Externally set a unique temporary `MEDICAL_SERVICE_TEST_DB` before Python starts. |
| Existing broad stale cleanup deletes another run. | Bypass its registration with the externally set test DB; delete only exact current-run files. |
| Wrong Python/dependency environment produces meaningless failures. | Require a Python 3.11.9 project venv and verified imports before source edits. |
| Line-ending instructions cause churn. | Preserve `app.py` CRLF and use LF for the new test and journals; byte-check every affected file. |
| Dirty artifacts are staged. | Preserve the recorded baseline and use exact-path staging only after commit authorization. |
| Plan is marked executed without a commit. | Keep `In progress` until an authorized commit hash exists. |

The residual known limitation is explicit: after this correction, valid Leave Request and LPR
awaiting-approval notifications without supported matcher branches will be skipped rather than
shown in this particular panel. Their authoritative workflow queues remain unchanged. Resolving
that product-completeness gap requires a separately approved plan.

## Turn LPR off reversibly, without stranding what is already in flight

**Status:** `Executed — ae9bf99`, reviewed in `325e26f`; promoted to `origin/main` and deployed at
`6e375f6`. **Started:** 2026-08-14, on the owner's explicit "go and execute" instruction.
The production census remains an operational prerequisite for any later Railway flag change; code
execution proceeds with both flags defaulting on and no environment change.
**Corrected 2026-08-14:** this line read `Executed — 8543ba5`, which is the *AGENTS.md publishing
rule* commit that happened to be the branch head when the promotion ran — not this plan's
implementation. Same shape as the `a0e06bf` mis-credit corrected in `changes.md` hours earlier:
**the head at publish time is not the commit that did the work.**
**Approved:** 2026-08-14
**Detailed:** 2026-08-14, after an exhaustive inventory of all 28 LPR routes, four models, every
template and nav entry, the approvals and recall integrations, the PDF paths and the eight affected
test modules. Four claims were checked by reading the code rather than accepted from the exploration
summaries; one was **false** and is corrected in Investigation.

### Context

Management has stopped accepting digital LPRs and may accept them again later. The feature needs an
off switch that can be flipped back on without a code change.

**The scaffold already exists.** `lpr_enabled()` (`app.py:340`) and `embedded_lpr_enabled()`
(`app.py:344`) both hardcode `return True`, both are already injected into every template by
`inject_feature_flags()` (`app.py:1265`), and roughly 60% of the surfaces already respect them — the
sidebar link, the approvals tile and its whole script block, the approval scope list, the module
catalog, the pending badge, the embedded modal, and all three parent pages. **This is finishing
wiring, not building a kill switch.**

**But hiding LPR naively breaks other modules.** Reimbursement *requires* a linked LPR when
Office/Field Items has a claimed amount (`app.py:36978-36991`), so with LPR off those reimbursements
stop being submittable. Travel Request and Cash Advance approval packages embed LPR PDFs for
already-linked LPRs, so gating the PDF builder makes approving them 500.

### Decisions taken

Owner, 2026-08-14:

| Question | Decision |
| --- | --- |
| In-flight LPRs | **Drain, don't strand.** Block new; let submitted ones be approved, returned or withdrawn, and approved ones retry their procurement email |
| Where the switch lives | **A Railway environment variable**, matching the existing flag precedent. No DB column, no Settings toggle |
| Reimbursement's LPR requirement | **Dropped while LPR is off**, returning automatically when it is back on |
| Old LPR links | **An explaining page**, not a silent redirect |

Taken here while planning, with reasons:

1. **Two env booleans, three accessors.** `LPR_ENABLED` and `LPR_ACCEPTING_NEW`, read through the
   existing `env_flag_enabled()` (`app.py:211`) into `app.config` — this project's testing seam,
   never `os.environ`. **Both default to `True`, so the repo default is today's behaviour and the
   suite stays green throughout.** No call site reads the second flag directly; `lpr_accepting_new()`
   returns `lpr_enabled() and config[...]`. That conjunction is the argument against a three-valued
   `LPR_MODE`: the only real risk of two booleans is setting one and forgetting the other, and the
   derived accessor makes that state **structurally unreachable**. A mode string would need a parser,
   a normalisation table and a rule for unrecognised values — three new failure modes for one saved
   variable.
2. **Enforcement is per-route, not the existing path blocklist.** `is_lpr_path()` /
   `LPR_BLOCKED_PREFIXES` (`app.py:318-333`) cannot express drain mode, because drain splits a
   *single path* by request content: `POST /save_lpr` **with** an id must succeed and **without** one
   must refuse. A path blocklist answers per-path only, so using it would block editing of returned
   LPRs — stranding exactly the population we promised to drain.
3. **`embedded_lpr_enabled()` follows `LPR_ENABLED`, not accepting-new.** It is a *rendering* flag
   wrapping the whole embedded modal and the reimbursement "Attached LPR" panel. In drain mode a
   reimbursement carrying a linked LPR must still be reviewable and correctable, so the panel must
   still render; creation is blocked inside the write routes instead.
4. **`ensure_lpr_tables()` keeps running unconditionally** (`app.py:54170`). Gating it causes the
   exact breakage being avoided: `linked_lpr_records()` is called from Travel Request approval, Cash
   Advance approval and the accounting ZIP, so with the tables absent those raise `no such table`.
   Same for `lpr_fill_pdf_bytes()` and `forms/LPR FORM.pdf` — **never gate, never remove.**
5. **`/lpr` stays open in drain mode.** The nav link is hidden, but `lpr_notification_url()`
   (`app.py:55207`) has already written `/lpr?lpr_id=N` into notification rows that exist in
   production. In drain those must land on a working page — it is where a requester withdraws a
   submitted LPR or fixes a returned one. In off mode it renders the explaining page.

### Investigation

**Four things checked directly. One was false:**

1. **`/save_lpr`'s create branch sits *below* an idempotent replay lookup.** The `else:` branch first
   queries by `creation_token` and sets `idempotent_replay`, and only then falls into `if not header:`
   to create (`app.py:55466-55474`). **The guard must go inside `if not header:`.** One level up, a
   client retrying a save that already succeeded gets a 403 that reads as correct policy while its
   draft is orphaned. This is risk 2.
2. **The reimbursement submit has an `elif` that DELETES linked LPRs** (`app.py:36990`). Threading the
   flag through `office_field_sources` rather than around the whole condition would route every
   drain-mode submit into that delete. This is risk 1.
3. **`access_denied.html` takes `denied_title`, `denied_message`, `denied_action_url`,
   `denied_action_label`**, all defaulted, and `app.py:20318` is the render-with-403 precedent.
4. **FALSE, and worth recording so it is not repeated:** an exploration pass reported that
   `/approvals` renders an ungated LPR **tab** from `approval_modules` (`app.py:17437-17444`), and
   listed it as a must-fix. **It does not.** `approval_modules` is passed to the template and **never
   consumed by any template** — grep across `templates/` returns nothing. It is dead context. The
   real tile (`templates/approvals.html:2053`) and the whole LPR script block (`:5678-5924`) are
   already correctly gated.

**The three in-flight populations** that make "drain" a real requirement rather than a nicety:
standalone `Submitted` rows sitting in an approver's queue; approved rows with
`procurement_status='Email Failed'` that a human is expected to retry via
`/resend_lpr_procurement_email`; and embedded rows attached to live parents, which are excluded from
the approval queries (`.filter(LPRHeader.parent_module.is_(None))`) because they are approved as part
of the parent. **Local `scheduler.db` has all four LPR tables with 0 rows**, so none of this could be
sized here.

### Route behaviour

Drain = `LPR_ENABLED` true, `LPR_ACCEPTING_NEW` false. Off = `LPR_ENABLED` false.

| Surface | Drain | Off |
| --- | --- | --- |
| `/lpr` page | serve | **explaining page, 403** |
| `/approvals?module=lpr&id=N` | serve | **explaining page, 403** |
| `/save_lpr` — **create branch only** | update ok, **create 403** | 403 |
| `/save_embedded_lpr` — **create branch only** | update ok, **create 403** | 403 |
| `/prepare_reimbursement_lpr` — when nothing linked yet | review existing ok, **prepare-new 403** | 403 |
| `/submit_lpr`, `/approve_lpr`, `/reject_lpr`, `/resend_lpr_procurement_email` | **allow** | 403 |
| recall | **allow** — withdrawal is a drain action | 403 |
| reads, previews, downloads, attachments | serve | 403 |

`/submit_lpr` is allowed in drain deliberately: a **Returned** LPR is one an approver explicitly
asked to be corrected and resubmitted, and it shares a route and an editable-status set with plain
Drafts. Separating them would mean status-sniffing inside the route. Drafts nobody submits die when
the switch goes to off.

**Railway operating table** — re-enabling is deleting both variables.

| Intent | `LPR_ENABLED` | `LPR_ACCEPTING_NEW` |
| --- | --- | --- |
| Normal (today, and after re-enabling) | unset | unset |
| Drain — stop intake, finish the queue | unset | `false` |
| Hard off | `false` | irrelevant |

### Execution steps

Shippable and green after every step.

1. **Production census — read-only, and a prerequisite.** Count `LPRHeader` grouped by `status`,
   `parent_module IS NULL` and `procurement_status`. **Cannot be answered locally — 0 rows.** It
   decides whether drain lasts a week or a quarter, and it is what "the queue has emptied" is
   measured against. On 2026-08-14, the authenticated Railway CLI link was established for the
   production `web` service, but the read-only `railway ssh` census could not connect to
   `ssh.railway.com:22` before timing out. No production rows were read and no Railway variable
   was changed; the owner-operated census remains a prerequisite for a later flag flip.
2. **Config, accessors, decorators — no behaviour change.** Two `env_flag_enabled(..., default=True)`
   config lines beside `app.py:219`; replace the hardcoded returns; add `lpr_accepting_new()` with the
   conjunction and a comment on why it lives there. Generalise `embedded_lpr_disabled_response()`
   (`app.py:54185`) into `lpr_disabled_response(message)` keeping the old name as a wrapper — its
   `{'status': 'disabled'}, 403` shape is the project's wire convention for "feature off" as distinct
   from "not allowed", and 11 call sites plus source tests depend on it. Add
   `require_lpr_enabled` / `require_lpr_accepting_new` taking an explicit `as_json` rather than
   sniffing `Accept` (the heuristic at `app.py:1256` exists only because a `before_request` hook has
   no per-route knowledge), and `lpr_unavailable_page()`.
   **Done when:** the suite passes unchanged, and forcing `LPR_ENABLED=False` makes
   `lpr_accepting_new()` False.
3. **Gate the standalone routes.** `@require_lpr_enabled` on the 15 read/act routes; in `lpr_page()`
   the check goes **before** the approver-only redirect. **The `save_lpr` guard goes inside
   `if not header:`, after the replay lookup** — see Investigation 1.
   **Done when:** off mode 403s every route and `/lpr` returns a 403 **page**, not a 302.
4. **Embedded creation guards.** `save_embedded_lpr()` — the `else:` create branch only.
   `prepare_reimbursement_lpr()` — refuse only when nothing is linked yet. Updates stay open in both.
5. **Relax the reimbursement requirement without enabling the delete.** Restructure `app.py:36977-36991`
   so the deletion condition is stated **positively** — `elif not office_field_sources and linked_lprs:`
   — rather than being "whatever the previous branch didn't catch". Add a middle branch for
   drain/off-with-an-LPR-attached that still validates and still 409s on mismatch. Client side, wrap
   `templates/reimbursement.html:3813-3820` (which opens the review modal before the server is ever
   consulted) in a newly injected `lpr_accepting_new` flag.
   **Done when:** defaults on → the 409 still fires and all 7 integration tests pass; drain +
   office/field + no LPR → submit succeeds; drain + **no** office/field + a stale LPR → it is still
   deleted; drain + office/field + one LPR → validation still enforced.
6. **The explaining page on both entry points** — `lpr_page()` and `approvals_page()` (the latter only
   when `?module=lpr`, so a plain `/approvals` visit is unaffected). Guard server-side: with the flag
   off the LPR script block is not rendered, so a client-side check would silently do nothing. While
   there, comment `approval_modules` as verified-dead context (Investigation 4).
7. **Recall** — guard the LPR branch on `lpr_enabled`, **not** accepting-new. Leave
   `RECALL_REQUEST_REGISTRY` structurally intact; `tests/test_request_recall.py:29-37` asserts on its
   source text.
8. **Template cosmetics, deliberately minimal.** Only `templates/settings.html:1754` plus step 5's
   block. **Leave the other ungated LPR references alone** — `approvals.html:2203`/`:2849` are inert
   copy maps that tests assert on by source text, and `:5359-5362` renders receipt links for an LPR
   attached to a **reimbursement still in the approval queue**, which is the drain population.
9. **Blocklist hygiene** — add the embedded route-family prefixes, drop the dead `/mark_lpr_`, and
   comment that the tuple is an **exemption list for a different flag**, not the LPR switch. During
   execution the route census identified eight explicit embedded route families rather than five
   individually named prefixes, so all eight are covered (`get_parent_lprs`,
   `prepare_reimbursement_lpr`, `save/delete_embedded_lpr`, `delete_all_embedded_lpr_`,
   `upload_embedded_lpr_`, `preview_embedded_lpr`, and `download_embedded_lpr`). Its incompleteness
   is latent, not live.
10. **Tests.** Rewrite `tests/test_lpr_workflow.py:73`, which asserts `lpr_enabled()` is True and is
    conceptually wrong once the value varies — re-pin it on the *property*. Everything else survives
    because defaults are `True` and no source is deleted. New `tests/test_lpr_feature_switch.py`,
    with four that earn their keep: **idempotent replay in drain returns 200 not 403** (the only
    guard for risk 2); **the anti-deletion pair**; **cross-module regression with `LPR_ENABLED=False`**
    — approving a Travel Request and a Cash Advance that each carry a linked LPR, and the accounting
    ZIP still containing the LPR PDF; and **a route census** walking `app.url_map` for every
    LPR-shaped rule against an explicit allow/deny table, which is what catches the 28th route being
    added later without a flag.
11. **Release.** Bump `CACHE_VERSION` — `/lpr` is not in `APP_SHELL`, but `templates/layout.html` is
    embedded in `/timeline` and `/login`, which **are** precached, so an offline device could still
    show the LPR nav link. Narrow but real. **Read the live value before committing.** One dated
    `releases.json` item describing the user-visible reality, not the flag.

### Deliberately excluded

- **Deleting or archiving LPR data.** Every table, attachment, `forms/LPR FORM.pdf` and
  `STORAGE_PREFIX_LPR` stays — the feature must be resumable, and parent modules read this data.
- **Gating `ensure_lpr_tables()` or the PDF builder** — decision 4.
- **A Settings-page toggle** — the owner chose an env var.
- **Removing `templates/lpr.html`** — `tests/test_appearance_themes.py` requires it, and off mode
  never renders it.
- **Purging or rewriting existing LPR notification rows** — they are history; the explaining page is
  what handles the clicks.
- **Gating the reimbursement approval detail's LPR receipt links** — step 8.

### Verification

No browser automation, per `AGENTS.md` "Codex App Safety During Testing".

- Full suite with defaults on, then again with the new module. Every new test proved by injection —
  confirm it applied by needle count **and `git status`**, not by a hash, and read the assertion
  message rather than the exit code.
- **Prove step 5 specifically** by reverting its restructure and confirming the two anti-deletion
  tests fail **for different reasons**.
- **Hand to the owner:** on a staging deploy in drain mode, that the New LPR refusal produces a
  sensible message rather than a silent no-op; in off mode, that a real notification link from the
  database lands on the explaining page and reads correctly on a phone; and that a reimbursement with
  a linked LPR still shows its receipt links in the approval queue.

**Execution verification completed locally on 2026-08-14:** the focused LPR suites ran 47 tests
successfully; the full repository suite ran 679 tests with one existing skip. `app.py` and the new
feature-switch test compiled, the authenticated rendered `reimbursement.html` and `settings.html`
inline JavaScript parsed with Node, all touched templates compiled through Jinja, the release
manifest parsed, and `git diff --check` passed. No browser automation, Codex app navigation, commit,
push, deployment, Railway variable change, intentional project database/schema change,
`pending-work.md` edit, or protected local-artifact staging was performed. The existing
test-generated `scheduler.db` worktree modification remains unstaged and excluded. The implementation
was committed as `ae9bf99`, the reviewed hard-off correction as `325e26f`, and the complete verified
chain was promoted to `origin/main` at `8543ba5` after the owner's later publishing instruction.
Railway accepted that main commit and completed it successfully with a running instance; Railway
variables remain unchanged.

**Amended after review, 2026-08-14 — step 5 had drifted from the decision it implements.** The
shipped condition was `office_field_sources and (lpr_accepting_new() or linked_lprs)`, which keeps
validating the linked LPR **in hard-off as well as drain**. The Decisions table says the requirement
is *dropped while LPR is off*, and the drift is not cosmetic: in hard-off, `/prepare_reimbursement_lpr`,
`/get_parent_lprs`, `/save_embedded_lpr` and `/delete_embedded_lpr` all 403, and
`reconcile_reimbursement_linked_lpr_drafts()` is gated too, so a mismatched link produces a 409 with
**no route left to repair or remove it**. Drain is genuinely different — every one of those doors is
open there — which is why the check is kept in drain and dropped in off:
`office_field_sources and (lpr_accepting_new() or (lpr_enabled() and linked_lprs))`. The linked row is
still never deleted, because the cleanup branch requires `not office_field_sources`. Two tests added
to `tests/test_lpr_feature_switch.py`; suite now 681. **This belongs on the risk list as risk 1b** —
same branch, same silence, one flag further on.

### After implementation

- Re-read this plan against the diff and amend this entry if the implementation differed.
- Dated `changes.md` section, newest first, **with its own heading**.
- One dated `releases.json` item; re-run `tests/test_changelog_coverage.py` **after** committing.
- Stage explicitly, file by file. Never `scheduler.db`, `output/`, `tmp/`, or the handoff artifact.
- Push or deploy only after a separate owner instruction — and note the flag flip itself is a
  **Railway variable change**, a second, separate decision after the code ships.

### Risks

Ranked by "would ship and nobody notices".

1. **The `elif` deletion in the reimbursement submit.** Silent, permanent, and the victim — a linked
   LPR row plus its attachments — is invisible to the person submitting. Step 5 and its two tests
   exist entirely for this.
2. **The `/save_lpr` guard placed above the replay lookup.** A retrying client 403s on a row it
   already created; the user reads "disabled" as correct policy while a real draft is orphaned.
   Invisible to any single-request test.
3. **A parent approval 500 from a gated PDF path.** If anyone later "cleans up" `ensure_lpr_tables()`
   or gates the PDF builder, approving a Travel Request or Cash Advance breaks — but only for those
   that *have* a linked LPR, so it reads as a random 500 rather than a flag consequence.
4. **Drain-mode reimbursement blocked client-side.** The server would allow the submit; the browser
   opens an uncompletable modal. The user reports "I can't submit my reimbursement" and nobody
   connects it to LPR.
5. **The `/approvals?module=lpr` deep link doing nothing** in off mode — an approver clicks an old
   email, the page loads, nothing happens, they assume the request vanished.
6. **A stale offline shell showing the LPR nav.** Offline-only and self-healing on the next online
   load; the cache bump covers it.

## Leave Request — support 1.5-day leave

**Status:** `Executed — dbc32d2`
**Approved / started:** 2026-08-14, through the owner's explicit `PLEASE IMPLEMENT THIS PLAN` instruction.
**Detailed:** 2026-08-14, after tracing the existing full-day/half-day model, UI, Calendar writer,
conflict checker, PDF field, and Leave Request API.

### Context

Leave Request currently supports Full Day and Half Day only. Half-day records use one AM/PM value
and the existing Calendar/conflict code applies that one interval to every weekday in the range.
The owner wants a request that totals 1.5 weekdays while preserving accurate Calendar blocks,
conflict checks, approvals, PDF output, and history displays.

### Decisions taken

- A 1.5-day request contains exactly two weekdays; weekend gaps are allowed because the existing
  `weekdays()` helper excludes weekends.
- One weekday is full day, 08:00–17:00. The other is half day, either 08:00–12:00 or 13:00–17:00.
- The requester chooses whether the half-day is on the first or last leave weekday and chooses AM
  or PM. The wire values are `partial_day_position=first|last` and the existing
  `half_day_period=AM|PM`.
- Existing Full Day and Half Day records and their stored fields remain compatible. The new schema
  field is additive and defaults to `NULL` for historical rows.
- Calendar and conflict logic use split per-date intervals. The unused half of a partial date is
  not treated as a conflict.
- The Leave Request page is the user-facing scope. The provisional API accepts the same duration
  model; the existing Timeline provisional payload remains full-day-only in this change.
- `pending-work.md` is owner-maintained and will not be edited. No service-worker bump is needed
  because the page JavaScript is inline and no app-shell asset changes.

### Investigation

- `leave_feature.py:23-24` currently allows only `full_day` and `half_day`; `:72-85` stores the
  duration and AM/PM but has no field for which date is partial.
- `leave_feature.py:194-233` counts weekdays, forces half-day requests to one weekday, and applies
  one `leave_time_range()` to the whole request.
- `leave_feature.py:359-429` compares conflicts against one interval for every requested date;
  `:437-487` writes one same-time Calendar row per weekday.
- `leave_feature.py:499-516`, `:826-868`, and `:899-918` validate self-service save, provisional
  creation, and conflict checks separately and all need the same 1.5-day rules.
- `leave_feature.py:322-326`, `:522-631` serialize duration data and fill the official PDF; the
  existing history, approvals, Accounting, and HR paths already consume the shared payload.
- `templates/leave_request.html:49-105` has two duration choices, one AM/PM selector, and client
  logic that locks the end date for half-day requests.
- `tests/test_leave_request_workflow.py:107-148` currently guards additive half-day schema,
  Calendar/conflict markers, PDF/API labels, and UI markers; functional API coverage lives in
  `tests/test_provisional_leave.py`.

### Execution steps

1. **Schema and duration primitives — `leave_feature.py`.** Add the additive
   `partial_day_position` column and migration, add the `one_and_half_day` duration and
   `first|last` position validation, and update effective counts/labels/API serialization. Done
   when legacy full/half payloads normalize exactly as before and 1.5-day payloads return `1.5`
   with an unambiguous label.
2. **Per-date intervals — `leave_feature.py`.** Add one shared helper that maps each weekday to
   its full or half-day time range. Use it in `conflicts()` and `update_calendar()` so schedule
   conflicts, Leave Request overlaps, provisional supersession, and Calendar rows all follow the
   same date-specific intervals. Done when a 1.5-day request creates one full block and one
   correct half block without duplicates.
3. **All request paths and documents — `leave_feature.py` and `app.py`.** Apply the shared validation
   to draft save, conflict preview, submission recheck, approval recheck, and provisional creation.
   Update the PDF Inclusive field and HR/API duration values while retaining old full/half output;
   add the duration label to the allowed/default HR subject placeholders and handoff body.
4. **Page controls — `templates/leave_request.html`.** Add the 1.5 Days option, first/last weekday
   selector, and shared AM/PM selector; keep both dates editable for 1.5 days, show a clear
   exactly-two-weekdays hint, and update load/reset/payload behavior for existing and new records.
5. **Regression coverage — `tests/test_leave_request_workflow.py` and functional Leave Request
   tests.** Cover both partial positions and AM/PM choices, invalid weekday counts and missing
   metadata, API round trips, split Calendar rows, precise conflict behavior, PDF/history labels,
   provisional handling, and unchanged Full Day/Half Day behavior.
6. **Closeout.** Update `changes.md` and the dated release manifest, self-review the diff, run the
   focused and full suites, Python compilation, inline JavaScript syntax validation, release
   manifest parsing, and `git diff --check`. Do not use browser automation or Codex app navigation.

### Deliberately excluded

- No balance/accrual calculation or payroll deduction logic is added; the existing effective
  duration value is extended to `1.5` for downstream displays.
- No Timeline UI redesign is added for administrators; its existing provisional payload remains
  full-day-only, though the shared provisional API validator supports 1.5-day data.
- No historical row rewrite is performed; existing records retain their current duration metadata.
- No changes to `pending-work.md`, `scheduler.db`, or service-worker assets.

### Verification

- Save and reload 1.5-day requests for first/last weekday and AM/PM combinations; assert
  `duration_type`, `partial_day_position`, `half_day_period`, effective `weekday_count=1.5`,
  `calendar_weekday_count=2`, and the duration label.
- Reject ranges with fewer or more than two weekdays and reject missing/invalid partial-day data.
- Assert Calendar rows use 08:00–17:00 for the full weekday and 08:00–12:00 or 13:00–17:00 for the
  partial weekday, including weekend-spanning ranges.
- Assert conflicts on the full interval and selected half interval block, while the unused half
  remains available; retain existing Full Day/Half Day conflict controls.
- Assert submission, approval, rejection, provisional behavior, PDF Inclusive output, HR/API
  payloads, history, and approval displays preserve 1.5 days.
- Run focused Leave Request tests, the full repository suite, `python -m py_compile app.py`, inline
  JavaScript syntax validation, release-manifest parsing, and `git diff --check` locally only.

### After implementation

- Re-read this plan against the diff and amend it if implementation details differ.
- Add a newest dated `changes.md` entry and a separate dated release item for the user-visible
  duration option. Record the final commit hash only after the final commit exists.
- Leave the repository ready for the owner's separate commit/push instruction.

### Risks

- A single interval applied across all weekdays would create false conflicts or wrong Calendar
  blocks; the shared per-date interval helper and exact row assertions guard this risk.
- A new duration accepted by save but lost by edit/approval/PDF would create inconsistent records;
  round-trip tests cover every downstream serializer and lifecycle path.
- An additive column must not invalidate existing rows; the migration and legacy full/half tests
  keep the historical schema contract intact.

## Reimbursement Register: fix the filter and the export, and stop both registers jumping to the top

**Status:** `Executed — 723333b`. Implementation and local verification completed; the implementation
commit is pushed with a journal closeout commit.
**Approved:** 2026-08-13
**Detailed:** 2026-08-13, after mapping every filter, KPI, export path and notification on both
register pages. Four claims were checked by reading the code rather than accepted from the
exploration summaries; one of them reversed a design decision — see Investigation.

### Context

Two owner reports, one day after the shared-batch work shipped:

1. **Reimbursement Tracker** — *"the filter is messed up, the export is kind of confusing."*
2. **P.O. Details** — every save scrolls the page back to the top.

Both turned out to be concrete defects. **The most serious is one nobody has reported: filtering by
engineer and pressing Export silently produces a workbook with no rows in it.**

### Decisions taken

Owner, 2026-08-13:

| Question | Decision |
| --- | --- |
| Totals when filtered | **Follow the filters** |
| Export scope | **The batch on screen**, plus an explicit All-history option |
| Export file | **Name it by batch and date**, and **add a TOTAL row**. Columns stay at **seven** — the trim for Accounting was a deliberate earlier decision |
| Scope | **Fix the defects and polish.** Out: per-batch saved filters, mobile sort access, a search-everything box |

Taken here while planning, with reasons:

1. **Fix the broken export filter by matching `engineer_id` server-side**, and stop the page sending
   `engineer=`. The "pair the filters" convention from the P.O. register is *text on both sides*
   because that page's inputs are text; the tracker's client filter already compares **ids**
   (`templates/reimbursement_tracker.html:359`), so pairing honestly means pairing on id. Sending the
   name instead would fix the empty file and introduce a subtler bug — "Jose Cruz" and "Jose Cruz
   Jr.": the screen shows one, a name-substring export returns both, and the file looks plausible.
2. **The TOTAL row is a literal `Decimal`, never `=SUM()`.**
   `tests/test_reimbursement_tracker.py:562-566` asserts **no formulas anywhere** and that
   `calculation.iterate` is off — that test exists because a `#REF` on the Total is the one thing
   that corrupts the artifact Accounting consumes. openpyxl writes formulas as strings and never
   evaluates them, so any reader using `data_only=True` sees `None`. **The P.O. register's
   `=SUM(J2:Jn)` is not a precedent here — it is exactly what this test was written to keep out.**
3. **The TOTAL label goes in column F, not A.** `tests/test_reimbursement_tracker.py:521-527`
   collects column-1 values and asserts the exported batch references; a `TOTAL` in column A would
   inject a phantom reference and break a test about something else entirely.
4. **`batch_scope` keeps `{current, all}`; `current` gains an optional `batch_sequence` companion**,
   mirroring `/get_reimbursement_tracker_entries` (`app.py:40953`). A third enum value would fork the
   wire vocabulary from the endpoint the same page already calls. Backward compatibility is total —
   the pinned scope matrix sends no `batch_sequence`. **The honesty problem is fixed in the label,
   not the wire.**
5. **The filename is derived on the server and read from `Content-Disposition`.** Building it in JS
   would put the naming rule in two places, which is the same drift that caused the scope desync.
6. **The toast uses real theme tokens, and this overrides the obvious "copy the existing one".**
   See Investigation — the timeline toast is hardcoded light.
7. **The toast helper is duplicated locally in both templates, not extracted to `static/js/`.**
   Neither page is an `APP_SHELL` entry (`app.py:15759-15784`) and every existing file in
   `static/js/` *is* a shell asset, so extracting one forces a caching decision and a
   `CACHE_VERSION` bump for a cosmetic fix. Two ~35-line copies, contained by a parity test.
8. **Keep the filters after a save and warn when they hide the new row.** Clearing them on every add
   discards the user's working set on a routine action — a new defect, not a fix. (`switchBatchView`
   clearing them is different and correct: the rows underneath genuinely changed.)

### Investigation

**The nine verified defects** — each confirmed by reading the cited code, not inferred:

| | Defect | Consequence |
| --- | --- | --- |
| **D1** | The engineer `<select>` carries `value="{engineer.id}"` (`reimbursement_tracker.html:439`) and sends that raw id as `engineer=` (`:325`); the server matches it as a **substring of the engineer's name** (`app.py:40835`) | **A headers-only workbook, with no error.** Screen shows N rows, file has none |
| **D2** | `renderKpis()` sums `state.rows` (`:382-387`) and is called only from `loadData` and `switchBatchView` — **never** from the filter handlers (`:783-784`) | Filtered rows sit above the whole batch's money, while `rt-result-count` *is* filter-aware, so the page contradicts itself. **Almost certainly the report** |
| **D3** | `switchBatchView` defaults `resetExportScope=false` (`:634`) and `current` always means the *server's* active batch (`app.py:40824`) | Viewing BATCH-032 shows a control reading "Current batch (BATCH-033)" and exports 033. **No way to export a historical batch at all** |
| **D4** | The client hardcodes `link.download = 'reimbursement_tracker.xlsx'` (`:751`), discarding the server's dated name (`app.py:41114`) | Two batches become "file" and "file (1)" |
| **D5** | No TOTAL row (`app.py:40914`) | The page shows a total; the file Accounting receives does not |
| **D6** | One fixed empty-state string (`:201`) | A genuinely empty batch blames a filter — fires right after "Start new batch" |
| **D7** | Filters survive a save (`:701`) | A just-added row can be invisible while "row added" fires; reads as a lost save |
| **D8** | Office filter exact+case-sensitive client-side vs substring server-side; server 400s on `from > to` while the page silently shows zero; server pushes blanks last in sort, client does not | Export contents and order can differ from the screen |
| **D9** | A byte-identical scroll-to-top `notify()` in `po_details.html:535` and `reimbursement_tracker.html:314` | The reported P.O. complaint, live on both pages |

**Four things checked directly. One reversed a design decision:**

1. **The existing toast is not theme-aware.** `templates/timeline.html:7427-7461` hardcodes
   `background: #ffffff; color: #0f172a`. Copying it verbatim — the obvious move — would ship a white
   toast on a dark page, **precisely the defect class this project has now shipped twice**. The
   repo-wide guard in `tests/test_appearance_themes.py` does not forbid tokens, it forbids
   *undefined* ones, so real tokens are both safer and theme-aware. Hence decision 6: surface and text
   from `--app-surface-raised` / `--app-text` / `--app-border`, with **tone carried by a coloured left
   border and icon, never a tinted background** — a tinted background is the "token used as a
   `background:`" trap already recorded in `pending-work.md`.
2. **`renderKpis()` really is unwired from the filters** — confirmed at `:382`, `:625`, `:637` against
   the handlers at `:783-784`.
3. **The no-formulas assertion is real** and also pins `calculation.iterate` off — confirmed at
   `tests/test_reimbursement_tracker.py:556-566`.
4. **`test_tracker_item_sits_under_its_own_release_not_the_backup_one` exists**
   (`tests/test_reimbursement_tracker.py:601`), so the changelog entry must be its own dated release
   rather than items appended to an existing one.

**Also load-bearing:** the alert element is the **first child** of the main container on both pages
(`po_details.html:332`, `reimbursement_tracker.html:106`), so the scroll is what makes a success
message readable at all — deleting it without replacing the channel would make every success message
invisible. And `notify()` assigns `className` wholesale, stripping `d-none` (permanently revealing a
zero-height element at the top and reflowing the page on the *first* message) and `no-print` (so the
alert then prints). Nothing restores either.

### Execution steps

Server first, then client; the app is runnable after every step.

1. **`reimbursement_tracker_export_records`** (`app.py:40787-40873`) — accept `batch_sequence`
   (`clean_int`, 1–999, must be in `reimbursement_tracker_available_batches()` (`app.py:40572`), else
   `ValueError` → the existing 400 at `app.py:41105`; ignored when scope is `all`) and `engineer_id`
   (exact match on `record.engineer_id`; **elif** the legacy name-substring at `app.py:40835`, kept
   for bookmarked URLs). Return a `(records, resolved_sequence)` tuple — one caller
   (`app.py:41103`), so no duplicated parsing.
   **Done when:** `?batch_scope=current&batch_sequence=32` returns only BATCH-032, `?engineer_id=<id>`
   returns that engineer's rows, and no-argument behaviour is byte-identical to today.
2. **`build_reimbursement_tracker_workbook`** (`app.py:40877-40928`) — rename `last_row` →
   `last_data_row`; write `TOTAL` in **F** and the quantised sum in **G** at `last_data_row + 1`;
   bold both, thin top border across A:G, `#,##0.00` on G, **no merges**. Leave
   `auto_filter.ref = f'A1:G{last_data_row}'` so the total sits **outside** the filter range —
   otherwise sorting in Excel drags the grand total into the data where it reads as a row. Empty
   result gives `A1:G1`, which still satisfies the pinned `^A1:G\d+$`.
   **Done when:** two rows give `F4 == 'TOTAL'`, `G4 == G2 + G3`, `A4 is None`,
   `auto_filter.ref == 'A1:G3'`, `max_column == 7`, no formulas, no merges.
3. **`export_reimbursement_tracker`** (`app.py:41090-41120`) — `all` →
   `reimbursement_tracker_all-batches_{YYYYMMDD}.xlsx`; otherwise
   `reimbursement_tracker_{BATCH-0NN}_{YYYYMMDD}.xlsx` via `reimbursement_tracker_batch_reference()`
   (`app.py:40548`). Name the scope in the activity-log line.
4. **Totals follow the filters (D2).** `renderKpis(rows)` takes the filtered rows and is called from
   inside `renderRows()`; drop the standalone calls at `:625` and `:637` (both are followed by
   `renderRows`). **Add a `#rt-kpi-scope` caption** — *"Showing all of BATCH-032"* versus *"Showing 3
   filtered row(s) of BATCH-032"*. **Not optional; see risk 1.**
5. **The engineer filter reaches the export (D1).** Leave `currentFilters()` and `filteredRows()`
   alone — the id-based client filter is correct. In `exportRegister()` (`:737-746`) stop spreading
   `currentFilters()` wholesale; send `engineer_id` and **never** `engineer`. Omit empties.
   **Done when:** filter to one engineer, export, and the workbook row count equals the screen count.
6. **Export scope tracks the viewed batch (D3).** Drive the `current` option's label from
   `state.viewBatch`, not `state.currentBatch` (`:554-556`): *"This batch (BATCH-032)"*, plus
   *" — active"* when they coincide. Send `batch_sequence: state.viewBatch?.sequence`. The literal
   `byId('rt-export-scope').value = 'current'` in `clearRegisterFilters()` stays, so the pinned
   template assertion holds untouched.
7. **Filename from the response (D4).** Read `Content-Disposition` before consuming the blob;
   sanitise (strip `/`, `\`, leading dots; require `.xlsx`); client-built fallback if parsing fails.
8. **Empty batch versus filtered-empty (D6).** Branch the `#rt-empty-state` text on
   `state.rows.length === 0`, with an inline **Clear filters** action on the filtered branch. Keep the
   element id and position.
9. **Warn when filters hide the saved row (D7).** After `loadData()` in `saveForm()`, check whether
   the saved row survives `filteredRows()`; if not, notify with a `warning`. Preserve the existing
   server-`warning` branch with priority. Change `openAddForm()`'s notice to admit it cleared the
   filters, since it already does so silently.
10. **The screen/file divergences (D8).** Office filter → substring + lowercase, matching the server.
    `from > to` → render zero rows with an explaining message and disable Export, rather than letting
    the server 400 unexplained. Sort → mirror the server's blanks-last pass. *(The sort item is the
    one to drop first if this grows.)*
11. **The toast, in `templates/reimbursement_tracker.html`.** Mount
    `<div id="rt-toast-stack" class="page-toast-stack no-print">`; add the CSS block using **real
    theme tokens** per decision 6; rewrite `notify()` to set `alert.textContent` only — **never**
    `className` — call `pageToast(message, kind)`, and not scroll. Switch the alert from
    `alert d-none no-print` to `visually-hidden no-print`: this also fixes a latent a11y bug, since
    `d-none` is `display: none`, which removes the element from the accessibility tree, so the live
    region announced **nothing** once hidden. Ids, `role="status"` and `aria-live="polite"` all stay.
12. **The same helper in `templates/po_details.html`** — byte-identical CSS and `pageToast` body,
    `#po-toast-stack`, the same `notify()` rewrite, the same alert class change. Call sites unchanged.

### Deliberately excluded

- **Per-batch saved filters, mobile sort access, a search-everything box** — the owner scoped this to
  fixing what is broken. Sorting *is* unreachable below 768px today; recorded, not fixed.
- **Payment columns in the export.** The seven-column trim was a deliberate decision for Accounting.
- **Extracting the toast to `static/js/`** — decision 7.
- **Focus preservation across `innerHTML` rebuilds.** `renderRows()` rebuilds both lists, so focus
  inside the subtree is still lost after a save. Real, but a separate ticket.
- **Dark-theme tone *tints*** for the toast — border and icon carry tone instead, which is what makes
  it theme-safe by construction.
- **Adopting `leave_request.html:89` / `cash_advance.html:1072`'s scroll-into-view** — the same defect
  wearing different clothes.

### Verification

No browser automation, per `AGENTS.md` "Codex App Safety During Testing".

- Full suite (658 today) — **all of it**, because part 2 touches two templates and the theme-token
  guard is repo-wide. Then `tests.test_appearance_themes` explicitly, and `tests.test_changelog_coverage`
  last, since it reads the newest commit.
- Every workbook claim through the Flask test client + `openpyxl`. **Load once with `data_only=True`
  and assert the total is still a number** — the concrete proof of decision 2 that a formula fails.
- A script that computes the expected filtered set in Python and compares it to the exported rows
  across filter permutations (engineer, office, paid, date range, and combinations). This is the
  "screen and file agree" check, done without a browser.
- Each new test proved by injection: confirm the injection applied by **needle count and
  `git status`**, not by a hash — see the CRLF/LF trap recorded in `changes.md` — and read the
  assertion message rather than the exit code.
- **Hand to the owner:** the toast legible in light **and** dark; it must not cover the modal's Save
  button on a phone; the saved row stays put on a long register; and Excel opens the TOTAL row
  looking like a total.

### After implementation

- Re-read this plan against the diff and amend this entry if the implementation differed.
- Dated `changes.md` section, newest first, **with its own heading** — that has now been got wrong
  twice and corrected twice.
- **A new dated `releases.json` release, not items appended to an existing one** —
  `tests/test_reimbursement_tracker.py:601` exists because that mistake was made before.
- **No `CACHE_VERSION` bump** (`app.py:15755`): no new static asset, no `APP_SHELL` file touched, and
  neither page is a shell entry. Stated so nobody bumps it reflexively — but **read the live value
  before committing** regardless.
- Stage explicitly, file by file. Never `scheduler.db`, `output/`, `tmp/`, or the handoff artifact.
- Push or deploy only after a separate owner instruction.

### Risks

Ranked by "would ship and nobody notices".

1. **A filtered total mistaken for a batch total.** The most dangerous outcome of *fixing* D2: a
   number that is now correct-but-scoped, looking exactly like the number that used to be batch-wide.
   Someone copies ₱41,200 believing it is BATCH-032's total. **The scope caption is the entire
   mitigation, which is why step 4 marks it non-optional.**
2. **The TOTAL row sorted into the data.** If `auto_filter.ref` swallows it, an Excel user sorts by
   Total and the grand total lands mid-table reading as a row. Silent, permanent, found downstream.
3. **The legacy `engineer=` substring path staying live.** Kept for bookmarks, it means a hand-built
   URL still produces a wrong file with no error — D1 dormant rather than dead. Log when the name
   path fires with an all-digit value, and assert the page never sends it.
4. **`Content-Disposition` parsing failing silently** — the fallback name is plausible, so nobody
   notices the header path is dead until the server's rule changes. Assert the header directly.
5. **The two toast copies drifting.** One page gets a fix, the other does not, invisible until
   someone compares. The parity test is the containment.
6. **A white toast on a dark page** if decision 6 is not followed. This project has shipped that
   defect twice; the repo-wide token guard catches undefined tokens but **cannot** catch a hardcoded
   light literal — so this one is on the reviewer, not the suite.

## Reimbursement Tracker — selectable historical batch views

**Status:** `Executed — 47ebd96`
**Approved:** 2026-08-13
**Detailed:** 2026-08-13, after reviewing the current-only list response and the existing
current/all export selector. The owner requested a page-level batch view selector so historical
batches can be reviewed without exporting.

### Context

The tracker register now correctly defaults to the active batch and keeps historical rows out of
the page. Historical rows are available only through the All batches Excel option, which forces a
user who wants to inspect an older batch to leave the page.

### Decisions taken

- Add a View batch dropdown with the current batch selected by default and one option for each
  stored batch sequence; the active batch remains available even when it has no rows.
- Selecting a previous batch changes the visible rows, KPI totals, filters, and result count to
  that batch without changing any stored data or the global active batch.
- The Add reimbursement action always returns to the active batch before opening the form. Edit
  and Delete remain available for rows in the selected historical view.
- Starting a new batch always switches the view to the newly active batch and clears filters.
- Excel export keeps its existing explicit Current batch / All batches scope; the new dropdown is
  for on-page viewing and does not silently alter export scope.
- No schema migration, service-worker bump, browser automation, or `pending-work.md` update is
  required.

### Investigation

- `app.py:40911` currently filters the list endpoint to the current sequence and has no view query
  parameter or batch-option payload.
- `templates/reimbursement_tracker.html:569` loads the response as the current page rows, while
  `:349` calculates all KPIs from those rows and `:590` refreshes after transitions.
- The existing batch-state singleton and `batch_sequence` column already provide the authoritative
  view key; no data migration is necessary.

### Execution steps

1. Extend `app.py` with an optional validated `batch_sequence` query parameter for the list
   endpoint. Return `view_batch` and a distinct `available_batches` list, always include the
   active batch, reject malformed sequences with `400`, reject unavailable batches with `404`,
   and query only the selected sequence.

2. Update `templates/reimbursement_tracker.html` with a native accessible View batch select.
   Populate it from `available_batches`, reload the selected sequence, clear row filters when the
   view changes, keep the active-batch transition control authoritative, and switch to the active
   batch before opening Add reimbursement.

3. Extend `tests/test_reimbursement_tracker.py` to prove current defaulting, previous-batch
   selection, available-batch metadata, malformed/unavailable sequence handling, empty active
   batches, historical row preservation, and the UI wiring for view switching and safe Add behavior.

4. Append the user-visible change to the existing 2026-08-13 release entry and update `changes.md`
   with the behavior and verification. Keep export columns, authorization, control numbers,
   historical edit locking, and all existing batch-transition tests intact.

5. Run focused/full tests, Python compilation, inline JavaScript syntax validation, release JSON
   parsing, and `git diff --check`; do not use browser automation or navigate the Codex app.

### Deliberately excluded

- No deletion or rewriting of historical rows.
- No separate history page or new database table.
- No automatic change from the selected view to the export scope.
- No change to the server-owned active batch or to new-row validation.

### Verification

- Seed BATCH-032 and BATCH-033, verify the default response shows BATCH-033, selecting
  `batch_sequence=32` returns only BATCH-032, and both references appear in `available_batches`.
- Verify malformed and unavailable sequence requests return `400` and `404`, respectively.
- Verify selecting an empty active batch returns zero rows and preserves prior rows in storage.
- Verify source wiring for the dropdown, query parameter, filter reset, and Add-to-active-batch
  guard, plus the focused tracker suite and full repository suite.

### After implementation

- Set this plan to `Executed — <commit hash>` after the implementation commit.
- Record final test counts and the commit state in `changes.md`.
- Stage only intended source, test, journal, and release files; never stage local databases or
  generated artifacts.

### Risks

- A user may edit historical rows while viewing them; the existing server-side immutable batch
  identity rule remains the safety boundary.
- A refresh can race with a global transition; the active batch response remains authoritative,
  and successful transitions explicitly reload the new active view.

## Reimbursement Tracker — current-batch view and totals reset

**Status:** `Executed — 6722481`
**Approved:** 2026-08-13
**Detailed:** 2026-08-13, after inspecting the shared batch state, tracker list endpoint, export
route, page KPI calculation, transition handler, and existing focused tests. The owner separately
requested implementation on the same date.

### Context

The shared-batch workflow correctly advances one server-owned batch for all engineers, but the
tracker page still loads every stored row into `state.rows`. Its Rows, Paid in full, Unpaid, and
Total PHP KPIs therefore include historical batches. Starting a new batch refreshes the same
all-history payload, so the old rows remain visible and the Total PHP figure does not reset for
the new batch.

The page should be an active-batch register: previous rows remain durable and exportable, but the
visible register and its KPIs are scoped to the server's current batch. Historical Excel export
must remain available through an explicit scope choice.

### Decisions taken

- The register page always displays the current batch only; there is no history toggle in the
  table.
- `Total PHP`, Rows, Paid in full, and Unpaid are calculated only from current-batch rows and
  show zero when the new batch has no rows.
- Excel export defaults to the current batch. An explicit All batches option exports history.
- A successful batch transition clears reference, engineer, office, date, payment, and export
  scope filters so the new batch is immediately visible.
- Previous rows are never deleted or rewritten by this feature.
- No schema migration or service-worker bump is required. The existing singleton batch-state
  table and inline tracker JavaScript are sufficient.
- `pending-work.md` remains untouched because it is owner-maintained only.

### Investigation

- `app.py:40911` currently returns every `ReimbursementTrackerEntry`; the response already
  includes the authoritative `current_batch` payload.
- `app.py:40766` currently builds export records from every tracker row and applies only the
  visible filters; it has no batch scope.
- `app.py:41035` routes export requests to that helper without a scope parameter.
- `templates/reimbursement_tracker.html:349` calculates all four KPIs from `state.rows`, and
  `:569` loads the endpoint response directly into that array.
- `templates/reimbursement_tracker.html:590` starts a batch and reloads data, but does not clear
  filters or change the returned row scope.
- `tests/test_reimbursement_tracker.py` already covers shared transitions, stale requests,
  historical edits, and export layout, so the new coverage can extend the existing fixture
  without changing the database contract.

### Execution steps

1. Update `app.py` list and export behavior. Read the current singleton state before the list
   query and return only rows whose `batch_sequence` equals the active sequence. Add a validated
   `batch_scope=current|all` export argument, default it to `current`, filter current exports by
   the server state, and leave `all` unfiltered. Return `400` for an invalid scope while keeping
   authorization and existing export sorting/filtering intact.

2. Update `templates/reimbursement_tracker.html`. Add a current-batch-aware export selector,
   pass its value to the export request, clear the selected register/export filters after a
   successful transition, refresh current-batch state on stale transition responses, and retain
   KPI calculations over the freshly loaded current-batch `state.rows`.

3. Extend `tests/test_reimbursement_tracker.py`. Prove an old row remains in storage but is absent
   from the list response after advancing, an empty new batch returns zero rows, current and
   all-history exports contain the correct rows, the default is current, invalid scope is rejected,
   and the template contains the scope selector, KPI calculation, filter reset, and conflict
   refresh behavior. Existing authorization, migration, transition, stale-save, 999-limit, and
   historical-edit tests remain green.

4. Update `changes.md` in the existing 2026-08-13 section and append a user-facing
   `static/changelog/releases.json` item under the existing 2026-08-13 release. Record that the
   register is current-batch-only, historical export is explicit, and no service-worker bump was
   needed. Do not add secrets, personal data, or database contents.

5. Self-review the diff for accidental changes to historical data, authorization, export columns,
   filter semantics, and batch transitions. Run focused tests, the full suite, Python compilation,
   inline JavaScript syntax validation, release-manifest parsing, and `git diff --check`. Keep
   verification non-browser so the Codex app remains open and untouched.

### Deliberately excluded

- No deletion, migration, or rewriting of prior tracker rows.
- No history table toggle; All batches is exposed only through the export scope choice.
- No changes to control-number generation, batch transitions, paid notifications, or historical
  edit locking.
- No service-worker/cache version change, because the affected script is inline.
- No `pending-work.md` refresh.

### Verification

- Seed rows in BATCH-032, advance to BATCH-033, and verify the database still contains the old
  row while the list response contains only BATCH-033 rows.
- Verify an empty BATCH-033 response produces zero rows and the page's Total PHP source uses the
  refreshed current-batch array.
- Seed rows in two batches and verify omitted/default and explicit `current` exports contain only
  the active batch, while `all` contains both; invalid scope returns `400`.
- Verify successful transition code clears all selected register filters and export scope, and
  stale transition responses refresh the active batch before reporting the conflict.
- Run `python -m unittest tests.test_reimbursement_tracker -v`, the full repository suite,
  `python -m py_compile app.py`, Node inline-template JavaScript parsing, release JSON parsing,
  and `git diff --check`. No browser automation is permitted for this project.

### After implementation

- Update this plan's status to `Executed — <commit hash>` after the implementation commit.
- Record the final verification result and commit hash in `changes.md`.
- Stage only intended project files; leave `scheduler.db`, `output/`, `tmp/`, and the handoff
  artifact untouched.
- Commit and push only when the owner explicitly requests publication.

### Risks

- A current-only list response can make historical rows unavailable to table actions; this is an
  intentional product decision, with All batches export preserving historical accounting access.
- A transition concurrent with a refresh could briefly return stale rows; the transition handler
  must reload after success and refresh on conflicts, while the server remains authoritative for
  export scope.
- Changing export's no-argument default could surprise callers; the UI labels the scope clearly,
  tests pin the default, and All batches remains one explicit choice away.

## Reimbursement Tracker — shared current batch workflow

**Status:** `Executed — 7847100`
**Approved:** 2026-08-13
**Detailed:** 2026-08-13, after tracing the current tracker suggestion endpoint, modal consumer,
stored control-number derivation, schema migration guard, and the live-table boundary. The owner
confirmed one global batch, an explicit transition action, and a full current-table conversion to
`BATCH-032`; execution was separately requested on the same date.

### Context

The Reimbursement Tracker currently calculates the next suggested reference as the highest stored
`batch_sequence` plus one (`/get_reimbursement_tracker_entries` in
`D:/Shimadzu/Projects/SHIMADZU/medical-service-sms-railway/app.py`). The Add modal consumes that
suggestion every time it reloads, so entering one engineer's row advances the next engineer to a
different batch. Batch numbers are shared by a group of engineer rows, not allocated per input.

The deployed tracker data must be normalized before the new workflow begins: every existing row in
`reimbursement_tracker_entry` becomes `BATCH-032`, with its stored sequence and control-number
suffix aligned to 032. All other row data remains unchanged. The local workspace database was
empty for this table during planning, so the migration is designed for the deployed/live database,
not inferred from the local fixture.

### Decisions taken

Owner, 2026-08-13:

1. The active batch is **global and server-backed** across authorized users and devices.
2. New rows reuse the active batch until the user explicitly confirms **Start new batch**.
3. The transition is sequential: after the migration, the active batch is `BATCH-032`, and the
   first explicit transition produces `BATCH-033`.
4. Existing rows are rewritten to `BATCH-032`, `batch_sequence = 32`, and control numbers are
   recomputed with the stored engineer initials snapshot and submission date plus suffix `032`.
5. The original XLSM source workbook is not rewritten; the migration targets only live
   `reimbursement_tracker_entry` rows.
6. Existing rows retain their batch identity when edited. The UI and server cannot move a
   historical row into the active batch through an edit.
7. No service-worker bump is required because the tracker page uses inline JavaScript and is not
   an app-shell asset.

### Investigation

1. `ReimbursementTrackerEntry` already stores `reference`, `batch_sequence`, `control_number`,
   engineer identity snapshots, and `submission_date`; the control number is derived by
   `reimbursement_tracker_control_number()` from the stored submission date and sequence.
2. `ensure_reimbursement_tracker_schema()` is the guarded additive-migration boundary and runs
   from both the WSGI `before_request` path and `initialize_database()`. The new singleton state
   table and first-run data rewrite must therefore be atomic and idempotent inside that boundary.
3. The current client-side `resetForm()` assigns `state.suggestedReference`, while the API
   computes that value from `max(batch_sequence) + 1`. This is the direct cause of the per-engineer
   increment and will be replaced with the current-batch response.
4. The local `scheduler.db` contains zero tracker rows; no local data will be treated as the
   deployed data set. A verified database backup is required before the live migration.

### Execution steps

1. **Add server-backed batch state and migration** — edit
   `D:/Shimadzu/Projects/SHIMADZU/medical-service-sms-railway/app.py` beside
   `ReimbursementTrackerEntry` and inside `ensure_reimbursement_tracker_schema()`.
   Create a singleton state table holding the current sequence and audit timestamps/user. On the
   first state initialization, rewrite every existing tracker row to `BATCH-032`, sequence 32,
   and a rebuilt control number, preserving every other column. Validate that each row has enough
   stored date/initials data; if not, roll back the entire migration and report the affected row
   IDs. Insert state `32` only after the rewrite succeeds, so a failed run can retry safely.

2. **Make API writes use the active batch** — edit the tracker helpers and routes in
   `app.py`. Add one formatter/current-state helper, return `current_batch` from the list endpoint,
   and retain `suggested_reference` only as a compatibility alias if existing consumers still
   require it. Add `POST /start_reimbursement_tracker_batch`, gated by the existing tracker
   capability, with an expected-sequence compare-and-increment so stale users get `409` rather
   than skipping or overwriting a transition. Reject sequence 999. Require new rows to match the
   current sequence at save time, returning `409` without inserting when a form is stale. Preserve
   an existing row's reference and sequence during edits. Log the migration count and each batch
   transition without exposing personal or amount data.

3. **Update the tracker UI** — edit
   `D:/Shimadzu/Projects/SHIMADZU/medical-service-sms-railway/templates/reimbursement_tracker.html`.
   Show the current shared batch in the hero, add a confirmed Start new batch action, populate
   the modal from the server's current batch, and make the reference read-only. Refresh state
   after a successful transition and show a clear refresh/conflict message for stale saves. Keep
   the existing control-number preview derived from the displayed batch, date, and engineer.

4. **Add focused regression coverage** — edit
   `D:/Shimadzu/Projects/SHIMADZU/medical-service-sms-railway/tests/test_reimbursement_tracker.py`.
   Cover migration normalization and preservation, repeated engineer entries in one batch, the
   explicit 032-to-033 transition, stale transition/add conflicts, immutable historical batch
   identity on edit, authorization, the 999 ceiling, current-batch API/UI markup, and the
   no-row/no-skip controls. Replace the old max-plus-one expectation because it asserts the bug.

5. **Self-review and project records** — inspect the final diff against this plan, update the
   existing current-date section in `changes.md`, and append a dated Reimbursement Tracker item
   to `static/changelog/releases.json`. Do not bump the service worker. Update this plan to
   `Executed` with the final commit hash only after all verification succeeds.

### Deliberately excluded

- The original `forms/Reimbursement tracker (template).xlsm` is not edited or imported.
- The older personal reimbursement workflow (`ReimbursementHeader` / `ReimbursementRow`) is not
  changed.
- No per-engineer or per-browser batch state is introduced.
- No automatic batch increment remains; only the explicit server transition changes the active
  batch.
- No browser automation or Codex app navigation is used for verification.

### Verification

- Use an isolated test database with mixed references, then assert every row becomes `BATCH-032`,
  control suffixes become `032`, row count/totals/payment fields remain unchanged, and rerunning
  the migration is a no-op.
- Add two engineer rows without transitioning and assert both use `BATCH-032`; transition once
  and assert the next row uses `BATCH-033`.
- Submit stale expected sequences for both transition and add; assert `409`, no skipped state,
  and no extra row.
- Assert edits preserve the historical row's batch, unauthorized transition is denied, and 999
  cannot advance.
- Run the focused tracker suite and then the full suite, recording the collected test count and
  existing skips. Also run `python -m py_compile app.py`, inline JavaScript syntax validation,
  `releases.json` parsing, and `git diff --check`.
- Validate API responses and rendered markup with Flask test clients/source checks only; do not
  close, archive, navigate, or otherwise terminate the Codex app.

### After implementation

- Re-read this entry against the diff and amend it if implementation details differ.
- Take a verified file-level database backup before deploying the live rewrite; compare the
  pre/post row count and aggregate totals from the backup and live database.
- Confirm the release-manifest item and detailed `changes.md` entry are present before commit.
- Stage only intended files; never stage `scheduler.db`, `output/`, `tmp/`, or handoff artifacts.
- Re-read `origin/main` after completion. Commit and push only after a separate owner instruction.

### Risks

1. **Live data rewrite risk:** a malformed legacy row could lose its control number. The migration
   validates all rows, runs transactionally, and must be preceded by a verified backup.
2. **Stale multi-user forms:** an engineer could save after another user starts a new batch. The
   expected-sequence check returns `409` and prevents a row from landing in the wrong batch.
3. **Double transition:** two users could click simultaneously. The atomic compare-and-increment
   allows only the request holding the expected current sequence to advance.
4. **Historical edit drift:** allowing reference edits would silently move old rows. The server
   preserves reference/sequence on update, with a regression test and read-only UI field.
5. **Migration marker drift:** a partial marker could cause repeat conversion. State creation is
   committed in the same transaction as the rewrite; failed transactions leave no initialized
   marker and are retryable.

## One P.O., many machines — migrating a shipped one-to-one into a many

**Status:** `Executed — Part A 5d7372e; Part B f307253`.
**Approved:** 2026-08-13
**Detailed:** 2026-08-13, after mapping every use of the shipped `product_serial`, the association-table
and multi-select precedents, and the analytics counting paths. Four assumptions were checked by
reading the code rather than accepted from the exploration summaries — see Investigation.

### Context

The machine-scoped P.O. work shipped on 2026-08-12 (`081d647`, `73b4467`, pushed) on the decision
that a P.O. covers **exactly one** machine. **The owner has revised that on 2026-08-13: one P.O. can
cover several machines.** The previous plan's "Deliberately excluded — more than one machine per P.O."
entry is therefore reversed; see the note under that plan below.

**This is a migration of live data, not a fresh build.** The single-machine version is deployed, so
`purchase_order.product_serial` may hold real values in production. Nothing may be lost, and the
change must survive a rollback.

### Decisions taken

Owner, 2026-08-13:

| Question | Decision |
| --- | --- |
| Minimum machines | **At least one**, unchanged. Legacy rows with none stay readable, and are asked for machines only on edit |
| Excel export | **One row per P.O.**, machines joined inside the existing cells |
| Register column | **First machine + "+N more"**, so row height stays stable |

Taken here while planning, with reasons:

1. **An explicit association model `PurchaseOrderMachine`, not JSON columns.** The travel module's
   JSON approach (`app.py:2240-2244`) is a real in-repo precedent, but it has no equivalent of
   `update_product`'s **bulk** repoint (`app.py:45789-45792`) — with JSON that becomes a
   read-modify-write loop over every P.O. row, inside a request already doing a delete-and-recreate
   of a `Product`. The `delete_product` 409 guard (`app.py:45868`) has the same problem. Both must
   query by serial.
2. **A real `UniqueConstraint` on (purchase_order_id, product_serial).** `ShiftEngineer`
   (`app.py:2551`) omitted one and this repo consequently needs `repair_shift_engineer_links()`
   (`app.py:41221`) to clean duplicates in application code. It also makes the backfill's
   multi-worker race safe — see Investigation.
3. **`lazy='selectin'`, never `joinedload`, on the collection.** Joining a one-to-many multiplies
   parent rows, which is the hazard `analytics_scope_query()` (`app.py:37613-37627`) exists to avoid.
   This is risk 1.
4. **`product_serial` stays as a write-only mirror** — one writer, zero readers.
5. **Chips on the existing autocomplete, not the travel checklist** — see step 7.

### Investigation

**Four assumptions checked directly, two of which shaped the plan:**

1. **`notify()` uses `textContent`** (`templates/po_details.html:492`), so naming the offending serial
   in a validation error is XSS-safe. This mattered: with several machines an unnamed "not registered
   to this client" error is unactionable, but echoing user data needed proof first.
2. **`static/js/app-analytics.js` IS an `APP_SHELL` entry** (`app.py:15615`), so this change **does**
   require a `CACHE_VERSION` bump. `/po_details` alone would not have forced one — the analytics
   metric tile does.
3. `selectinload` is already imported (`app.py:87`); no new import.
4. `ReimbursementTrackerEntry` (`app.py:3658`) is the precedent for creating a second table inside
   `ensure_purchase_order_schema()`'s transaction.

**The hardest constraint:** `PurchaseOrder(**values, created_by=...)` (`app.py:40130`) and the
`setattr` loop (`app.py:40174-40175`) both consume `validate_purchase_order_payload`'s dict directly,
so a list of serials cannot ride inside it.

**The backfill race.** `ensure_purchase_order_schema()` is guarded by a **module-global** flag
(`app.py:3524`), so it runs once *per process*. Two workers can both see "no links yet". The unique
constraint is what makes that safe: the second insert raises, the whole `with db.engine.begin()`
block (`app.py:3530`) rolls back atomically, the `except` at `app.py:3574` leaves the flag False, and
the next request retries into a no-op.

**`ShiftEngineer` is the association precedent** (definition `app.py:2551-2554`, replace idiom
`app.py:21737-21741`, fuller parent+child version `apply_travel_request_routes` `app.py:28011-28047`),
and the normalizer/applier split to copy is `normalize_travel_request_participants_payload`
(`app.py:28116`) with its `seen`-set dedupe (`app.py:28129`).

**There is no `secondary=` many-to-many anywhere in this codebase** — every "many" is a hand-written
association model. Do not introduce the first one.

### Execution steps

Ordered so the app is never broken between steps: schema and backfill first (nothing reads the new
table yet), then writes, then reads, then UI, then analytics, then the last reader is removed.

1. **Model, schema, backfill.** New `PurchaseOrderMachine` after `app.py:1877` — `id`,
   `purchase_order_id` (FK, NOT NULL, indexed), `product_serial` (String(100), FK
   `product.serial_number`, NOT NULL, indexed), `position`, `created_at`; `__table_args__` carrying
   `uq_purchase_order_machine_pair` plus both indexes, commented with the `ShiftEngineer` lesson. On
   `PurchaseOrder`, a `machines` relationship ordered by `position, id`, `cascade='all, delete-orphan'`,
   `lazy='selectin'` — the cascade is what lets `Client` → `purchase_orders` reach the link rows and
   makes `delete_purchase_order` correct with no code change. In `ensure_purchase_order_schema()`:
   create the table after `app.py:3531`, leave `additive_columns` untouched, add the three
   `CREATE ... IF NOT EXISTS` indexes defensively, then the backfill
   `INSERT INTO purchase_order_machine ... SELECT ... WHERE product_serial IS NOT NULL AND TRIM(...) <> ''
   AND NOT EXISTS (SELECT 1 FROM purchase_order_machine m WHERE m.purchase_order_id = po.id)`.
   Three properties to comment: **`NOT EXISTS` keys on `purchase_order_id` alone** (keyed on the pair,
   a machine a user deliberately removed would be **resurrected** on the next restart); **no
   `INSERT OR IGNORE`** (a violation must surface so the retry happens); **no join to `product`**
   (`PRAGMA foreign_keys` is off, so a serial may name a deleted product and joining would silently
   drop the row — data loss).
   **Done when:** the table is populated, re-running is a no-op, and the app behaves identically.
2. **`purchase_order_to_dict()`** (`app.py:39753-39782`) walks `machines`. Adds `machines`,
   `machine_count`, `machine_serials`, `machine_summary`, `machine_display_all`, `machine_search`.
   **`machine_display` / `product_serial` / `product_name` / `product_client_id` keep their exact
   current meaning but are derived from `machines[0]`, never from the DB column** — the API contract
   is unchanged and `tests/test_purchase_orders.py:738` keeps passing. The `' — '` join is U+2014 and
   must stay byte-identical to `productDisplay()` (`templates/po_details.html:742-746`).
   **Done when:** every existing key still resolves and no consumer has changed.
3. **The mirror column.** Keep `product_serial` physically present; write from exactly one function;
   read from zero. Not dropped (SQLite DROP COLUMN needs a table rebuild; this codebase is
   additive-only). Not left stale (destroys rollback). Not read — that is the `pending-work.md` §6
   lesson, **but note that lesson is about two *readers* disagreeing**; one writer and zero readers
   cannot diverge observably. Written, because on a rollback the old code then shows the primary
   machine for every row rather than nothing. Enforced by: deleting the `PurchaseOrder.product`
   relationship in step 9; a **corruption test** (set the column to garbage via raw SQL, assert
   register/export/analytics never surface it — proves zero readers in a way grep cannot); and a
   mirror test.
4. **Write path.** New pure `normalize_purchase_order_machines(payload, client_id, existing=None)`:
   accepts a list, a single string, or comma-joined; dedupes case-insensitively preserving order;
   caps at 50 and **rejects rather than truncates** (silently dropping machines from a financial
   register is the worst available failure); empty gives the **byte-identical** existing message so
   current tests pass; per-serial resolution reuses `app.py:39849-39853` including the
   case-insensitive fallback. The not-found and wrong-client messages **gain the serial name**
   (XSS-safe, verified). `validate_purchase_order_payload` returns a **3-tuple**
   `(values, machine_serials, error)` — the list never enters the dict, so `PurchaseOrder(**values)`
   and the `setattr` loop keep working with no `pop` for a future field to slip through. **The machine
   block stays at its current position**, after amount/date/type/client validation, because
   `tests/test_purchase_orders.py:658` deliberately omits the serial in cases expecting those errors
   first. The applier uses **ORM collection assignment**, not the bulk-delete idiom: that idiom leaves
   the parent's in-session collection stale, and both routes re-serialize the parent in their own
   response (`app.py:40144`, `40187`), so it would need an `expire()` call that a reviewer would later
   delete as "unnecessary" and ship a response showing the old machine list. `add_purchase_order`
   needs a `flush()` before children. Both activity logs become list-aware via a bounded label helper.
   **Done when:** create, edit-replaces, and the legacy-edit refusal all behave, and step 10's tests 5
   and 6 pass.
5. **Products-side guards** (`app.py:45717-45883`). All three counts move to the link table via one
   helper counting **distinct P.O.s**. The rename repoint becomes **two** bulk updates — link rows and
   the mirror. Comment why a rename cannot collide with the unique constraint (`update_product`
   already 409s when the new serial exists as a Product, and a link can only exist for a real
   product). The owner-reassignment note is reworded: a multi-machine P.O. can now be partly valid.
6. **Filters, sort, export.** `purchase_order_export_records()` eager-loads via `selectinload`; the
   machine filter matches **any** machine; `sort_value` uses the **first** machine only (sorting by a
   concatenation of an arbitrary-length list is unstable, and the column shows the primary, so the
   sort must agree with the eye); `is_empty` becomes `not record.machines`. `export_purchase_orders()`
   keeps **all 13 headers byte-identical** and joins machines with `'\n'` inside G and H —
   `wrap_text=True` is already set (`app.py:40074`), so Excel stacks them and rows auto-height. **The
   `''` placeholder for a missing product name is mandatory**: filtering empties desyncs line *k* of G
   from line *k* of H and silently attributes the wrong model to a serial. Everything else stays put
   and must be re-verified — the number_format indices, the TOTAL block, `freeze_panes`,
   `auto_filter.ref` ending `M`, the 13 widths — all still correct **because rows were not
   multiplied**. Record the `chr(64 + index)` 13-column ceiling (`app.py:40095`) in `changes.md`
   rather than fixing it here.
7. **`templates/po_details.html` — chips, not the travel checklist.** The modal is
   `.modal-dialog-scrollable` with `overflow-y: auto`; the existing `.search-results` is already
   proven in production inside that scroll container, while the travel dropdown is a separate CSS
   system that has never run inside one and would clip at the body edge — **and it cannot be verified
   visually here**, so the proven container behaviour is the only defensible call. The three
   strengths (client scoping, disable-until-client, the pinned empty-state string) all live in the
   branch being kept, and the common case stays a one-machine P.O. Add `selectedMachines` to `state`
   and **delete the dead `productNameCounts`**. Keep all four existing machine ids so the markup test
   passes with one added assertion. `machineFields()` renders `machine_summary` with a `title` of the
   full list and serves **both** the desktop cell and the mobile line — one function, no divergence.
   **The two table header copies need no change**, since label and sort key are unchanged. New
   `.po-chip` CSS must use tokens that exist in `app-themes.css`; the repo-wide guard in
   `tests/test_appearance_themes.py` fails the build otherwise.
8. **Analytics** (`app.py:37888-37968`). Three units now coexist and must stay distinct: **order**
   (`total`, `linked_total`, `unlinked_total`, `linked_pct`, `client_total`, `unlinked_clients`),
   **link** (`by_machine`, `by_model`, `by_coverage`, new `machine_link_total`), and **entity**
   (`machine_total`). A 3-machine P.O. counts once as an order and three times across links. Comment
   that an empty `InstrumentedList` is falsy, so legacy rows stay unlinked by a truthiness
   coincidence. `orders_for_range` swaps to `selectinload` **with a comment**, because a `joinedload`
   would multiply the rows that `app.py:38017` counts with `len(orders)`.
   **Invariants:** `sum(by_coverage) == linked_total` **breaks**; `sum(by_machine) == linked_total`
   **never held** (`[:10]` truncated) and must not be "restored"; `linked_total + unlinked_total ==
   total` **still holds**; and the **new exact invariant** `sum(by_coverage) == machine_link_total`
   must be asserted. That is why `machine_link_total` is worth adding — it gives the per-link numbers
   a name, so "coverage adds to 27 but there are 12 P.O.s" has a checkable answer instead of looking
   like a defect. Add a fifth metric tile and reword the Coverage-mix subtitle.
9. **Remove the last reader.** Only after 2, 5, 6, 7, 8 land: delete the `PurchaseOrder.product`
   relationship, then grep to confirm zero `.product` reads and zero `joinedload(PurchaseOrder.product)`.
   This makes step 3 structural rather than aspirational.
10. **Tests.** Rewrite two, add ten. **`test_model_has_asset_linkage_but_no_work_linkage`** — second
    deliberate rewrite, docstring must say why; keep the forbidden-set assertion verbatim **and carry
    it to the new table** so the rule follows the asset link to its new home; add both FK targets,
    `delete_orphan` on `machines`, and a walk of `__table__.constraints` asserting the
    `UniqueConstraint` — **that assertion is what prevents the ShiftEngineer repeat** and is the
    reason a second rewrite is acceptable. **The export test** keeps its 13 headers, `D2`, `F2`,
    `J2`, `J3`, `J5` and `auto_filter.ref == 'A1:M3'` unchanged — that stability is the point of the
    one-row design — changing only `G2`/`H2` and adding a multi-machine case with the
    `len(G2.split('\n')) == len(H2.split('\n'))` alignment guard. New: backfill seeds exactly once;
    **backfill never resurrects a removed machine**; backfill keeps links whose product row is gone;
    duplicate links rejected by the database; edit **replaces** rather than appends; the **PUT
    response body** shows the new set; reads never consult the legacy column; the mirror tracks
    `machines[0]`; the filter matches any covered machine; a many-machine P.O. is one export row.
    Keep the existing string-form `product_serial` payloads — they are now the back-compat regression
    test and must not be converted to arrays.
11. **Release.** Bump `CACHE_VERSION` (`app.py:15595`) — **required**, because `app-analytics.js` is
    an `APP_SHELL` entry and step 8 changes it. **Read the live value immediately before committing,
    never from this document.** Bump the analytics `?v=` params in the same commit. Dated
    `releases.json` item. `changes.md` entry.

### Deliberately excluded

- **One row per machine in the export.** Would over-count the amount in TOTAL and break
  `auto_filter.ref`; every export in this codebase is one-row-per-parent.
- **A merged single "Machines" column.** Changes the column count, moving `auto_filter` off `M`,
  invalidating the 13 widths, shifting every `number_format` index and moving the `=SUM(J…)` column —
  for no analytical gain.
- **Dropping `product_serial`.** A table rebuild on a live deploy to save 100 bytes a row.
- **Porting the travel checklist.** Unverifiable containment risk under the browser rule — step 7.
- **Fixing the `chr(64 + index)` 26-column ceiling.** Real, but unrelated; mixing it in muddies the diff.
- **Relaxing the at-least-one-machine rule.** Asked and declined; the 89-client backfill stands.

### Verification

No browser automation, per `AGENTS.md` "Codex App Safety During Testing".

- **Suite:** `python -m unittest discover -s tests` on the project venv. Each new test needs the
  injection that proves it can fail — confirm the injection **applied** (needle count and SHA) and
  read the **assertion message**, not the exit code.
- **Test client round trip:** POST `product_serials: [A,B,C]` → 201; register → `machine_count == 3`
  and `machine_summary` ending `" +2 more"`; PUT `[C]` → the **PUT response body** shows `[C]`;
  export → **one** row with three lines in G.
- **Direct DB checks against a copy of the production file**, before and after: count P.O.s with a
  non-blank `product_serial` (`N`); assert `purchase_order_machine` holds exactly `N`; a `LEFT JOIN`
  on both id and serial `WHERE m.id IS NULL` must return **zero rows**; `PRAGMA
  index_list('purchase_order_machine')` must show the unique index **physically** (model-level
  assertions can pass while the table lacks it); zero orphan links after a client delete.
- **Query-count check** — a `before_cursor_execute` listener over the register with ~30 P.O.s,
  asserting a bounded statement count. This is the N+1 guard, and a browser would never have caught it.
- **Source-level:** zero `PurchaseOrder.product` reads after step 9; `widths` still 13;
  `auto_filter.ref` still ends `M`; every new `var(--app-*)` token resolves.
- **Hand to the owner:** the "+N more" cell at laptop width and its tooltip; six-plus chips inside the
  scrollable modal without clipping the dropdown (**the specific risk step 7 accepted**); dark mode on
  the chips; **the `.xlsx` opened in real Excel** — do the stacked cells render and auto-height, and is
  TOTAL still correct; the Equipment tab with five tiles at desktop and mobile.

### After implementation

- Re-read this plan against the diff and amend this entry if the implementation differed.
- Dated `changes.md` section, newest first. Record the 13-column export ceiling and the analytics
  unit change (order vs link) with the invariants that intentionally no longer sum.
- One dated `releases.json` item; re-run `tests/test_changelog_coverage.py` **after** committing.
- **Take a file-level database backup before deploying.** The backfill is one transaction and cannot
  half-apply, but a backup is what makes rollback unconditional.
- Stage explicitly, file by file. Never `scheduler.db`, `output/`, `tmp/`, or the handoff artifact.
- Re-read `origin/main` after finishing, not only before starting.
- Push or deploy only after a separate owner instruction.

### Risks

Ranked by "would ship and nobody notices".

1. **`joinedload` on the machines collection in analytics.** `len(orders)` is the headline "Total
   P.O.s"; a joined collection makes a 3-machine P.O. count as **three purchase orders** in a
   financial dashboard — plausible, moving the right way, unaudited.
2. **A stale collection in the update response** if the bulk-delete idiom is used: the PUT returns the
   *old* machine list, the user refreshes, sees the new one, and concludes the page is "slow".
3. **G/H line misalignment in the export** if empty names are filtered instead of placeheld. The file
   looks perfectly normal and attributes the wrong model to the wrong serial.
4. **A backfill re-run resurrecting a dropped machine** — audit-trail corruption in a financial
   register, visible only after an edit plus a restart.
5. **N+1 across the register** — 200 P.O.s, 201 queries; invisible on SQLite in dev.
6. **The partial-validity reassignment case** — a 5-machine P.O. refusing to save without saying which
   machine is wrong.
7. **`by_coverage` no longer summing to `linked_total`** — someone "fixes" it by de-duplicating per
   P.O. and quietly destroys the per-machine analysis.
8. **Chip dropdown clipping in the scrollable modal** — the only genuinely un-assertable risk, which
   is exactly why step 7 chose the container behaviour already proven there.

### Execution outcome — 2026-08-13

The plan was executed in two functional commits:

- `5d7372e` — Part A: association model and additive backfill, list-aware P.O. validation and
  writes, association-based reads/serialization/export, Product rename/delete safeguards, and the
  multi-machine P.O. selector with regression coverage.
- `f307253` — Part B: link-granularity Equipment analytics, the Machine links metric, analytics
  asset query bumps, service-worker cache `v88-multi-machine-po`, the dated release manifest item,
  and release-focused tests.

One implementation detail was amended during execution: replacing an existing association set first
clears the ORM collection and flushes orphan deletes before assigning the new collection. This keeps
the required ORM collection semantics while avoiding a transient unique-key collision when an edit
retains a serial. It is not a bulk SQL delete.

Verification completed without browser automation: 651 tests passed with one existing skip in the
full suite; 53 focused P.O./analytics tests, 84 offline/cache/regression tests, Python and JavaScript
syntax checks, a bounded association-query check, and deliberate runtime injection controls all
passed. The release-manifest coverage test was rerun after the Part B commit. Browser/Excel visual
checks and a copy-of-production-database inspection remain owner handoff items because the project
rules prohibit Codex browser automation and prohibit opening the local `scheduler.db`; no push or
deployment was performed.

## Machine-scoped P.O. records, and an Analytics Equipment tab

**Status:** `Executed — 081d647 + fd781b1`. Execution was authorized by the project owner on
2026-08-12 after the plan was reviewed and the separate go-ahead was given.
**Approved:** 2026-08-12
**Started:** 2026-08-12, after the project owner explicitly instructed execution.
**Finished:** 2026-08-12 in Part A commit `081d647` and Part B commit `fd781b1`; the documentation
status was recorded in a follow-up journal commit after the implementation hash existed.
**Detailed:** 2026-08-12, after reading the P.O. register end to end, the `Product`/`Client`
relationship, the four existing type-to-search pickers, and the Analytics page and its chart
helpers. Three claims were verified by reading the code rather than accepted from the exploration
summaries; two of them changed the plan — see Investigation.

> **PARTLY SUPERSEDED 2026-08-13 — read this before treating any decision below as current.** The
> owner reversed the "**exactly one machine per P.O.**" decision one day after this shipped. One P.O.
> can now cover several machines, and the replacement plan is **"One P.O., many machines"** at the
> top of this file. Everything else here still stands: the at-least-one-machine rule, the no-free-text
> rule, the legacy-rows-readable rule, the Products-side guards, the Equipment tab, and the tab
> structure are all unchanged and still describe the system.
>
> **Specifically reversed:** the "Deliberately excluded → More than one machine per P.O." entry below,
> and with it the single `product_serial` column, which becomes a write-only mirror behind a
> `PurchaseOrderMachine` association table.
>
> **The record is worth keeping rather than editing.** The one-machine decision was taken explicitly,
> with the multi-machine option costed and declined on the day — it was not an oversight. What changed
> was the requirement, not the reasoning. Note also that the excluded entry already named
> `templates/travel_request.html:2788-2801` as the pattern to use "if this is ever revisited", and
> that is exactly the pattern the replacement plan evaluates — a deliberate exclusion that carried its
> own way back is what made the reversal cheap to plan.

### Context

The admin clarified that **a P.O. is issued per machine, not per client.** The register records
only a client, so it cannot answer *"which P.O. covers this machine"* — the question the document
exists to answer. Alongside it, the Add/Edit modal's client picker is a plain `<select>` over 145
clients, which is slow to use.

This makes each P.O. name the exact machine it covers, turns the client picker into a type-to-search
box, and scopes a second picker to the chosen client's equipment. The Analytics page gains a tab
structure and a new Equipment tab reporting on the new data.

**No existing P.O. data is deleted or rewritten.** Every current row predates machine tracking;
those rows stay readable and exportable and are asked for a machine only when someone edits one.

### Decisions taken

Settled by the owner on 2026-08-12. An executor should not reopen these.

| Question | Decision |
| --- | --- |
| Machines per P.O. | **Exactly one.** A single nullable FK column, not a link table |
| Existing rows with no machine | **Readable, but required when edited.** Mirrors the existing legacy-Contract-missing-End-Date rule |
| Client has no registered equipment | **Say so and point to Products.** No free-text fallback |
| What the new Analytics tab shows | **Equipment / machine P.O. analytics** |

Decisions taken here while planning, with their reasons, so they are not re-litigated either:

1. **Column name `product_serial`, not `product_id`.** The stored value is literally a serial.
   `Shift.product_id` is the *schedule* linkage that `tests/test_purchase_orders.py:259` exists to
   keep out of this model; reusing the name blurs the line that test protects.
2. **Nullable in the schema, required in validation.** This is exactly how contract `end_date`
   already works — `nullable=True` at `app.py:1854`, required by validation at `app.py:39707`.
   It is what makes the legacy rule work without a data migration.
3. **The machine does not join duplicate detection.** The 409 is a soft advisory with a "Save
   Anyway" override (`templates/po_details.html:692-711`). Adding the machine to the key would
   suppress the warning in the likeliest typo case — the same number re-entered at the same client.
   Instead, name the existing record's machine in the warning text.
4. **Extend `/get_purchase_orders`; do not call `/get_products`.** The page makes exactly one fetch
   on load (`templates/po_details.html:681`). A second fetch adds ordering, a second failure mode
   and a second spinner state for no gain — and `/get_products` returns `[]` for HR-schedule-only
   users (`app.py:21061`), which would be a silent empty picker rather than an error.
5. **The machine is sortable, filterable and exportable.** Every on-screen filter here has a server
   twin; breaking that pairing is how an export starts disagreeing with the screen.
6. **The autocomplete donor is `templates/products.html:494-535`, not `timeline.html`.** The
   products version is self-contained; the timeline version drags in `getProductCoverageStatus`,
   `formatProductDisplay`, `bindCellClicks` and an offline-cache path this page does not need. Port
   the products skeleton, then layer on the four timeline *behaviours* listed in Investigation.
7. **The Equipment tab reuses the shared date filter but not the branch filter.** `PurchaseOrder`
   has no branch dimension — branch lives on `Engineer` — and `/get_po_analytics` already
   deliberately skips `analytics_scope_query`. Keep `scope_label: 'Company-wide'` visible so nobody
   misreads the numbers as branch-scoped.
8. **Extend `/get_po_analytics` rather than add an endpoint** — one capability gate, one
   `analytics_date_bounds()`, one round trip, one entry in the existing `Promise.all` fan-out.

### Investigation

Verified in the code, with what changed the approach called out.

**The data model needs no relationship work.** `Product` *is* the installed-equipment register
(`app.py:2379`), its **primary key is `serial_number` String(100)** rather than an int, and it
already carries `client_id` FK (`app.py:2388`, nullable). So *"what equipment does client X have?"*
is `Product.query.filter_by(client_id=...)` — a query that already exists at `app.py:39271`. The new
P.O. column is therefore a `String(100)` FK to `product.serial_number`, **not** an integer id.

**The requested interaction already ships**, in the schedule form, and is the pattern to copy:
client-scoped product filter (`templates/timeline.html:14272-14280`), disable-until-a-client-exists
with a placeholder swap (`templates/timeline.html:12634-12647`), clear-the-machine-when-the-client-
changes (`templates/timeline.html:14260` and `:14325`), and an equipment-specific empty state
(`templates/timeline.html:14286-14288`).

**Three things were checked directly rather than taken on trust. Two changed the plan:**

1. **A product serial rename orphans P.O. rows.** `update_product` renames by **delete-and-recreate**
   (`app.py:45587-45604`) and repoints `Shift.product_id` (`app.py:45598`) **and nothing else**.
   Without step 5 below, a rename silently blanks the machine on every affected P.O. — a blank cell
   is the only symptom.
2. **`delete_product` has no reference check at all** (`app.py:45655-45665`) — it deletes
   unconditionally, and there is no DB-level FK behind it (see the migration note in step 1). Step 5
   adds a 409.
3. **The Analytics resize observer only ever redraws schedule charts.** `CHART_FRAME_IDS` is
   `['trend-chart','branch-chart','category-chart']` (`static/js/app-analytics.js:361`) and the
   observer callback calls `renderScheduleCharts(state.schedule)` and nothing else
   (`static/js/app-analytics.js:387`). A new chart needs **both** a `CHART_FRAME_IDS` entry and a
   widened callback, or it never redraws.

**Constraints that dictate the Analytics design rather than merely bounding it:**

- `tests/test_analytics_page.py:201` asserts **no inline `<style>`** in the template, so tab CSS
  must live in `static/css/app-analytics.css`. (`po_details.html` has no such rule — inline style
  is fine there.)
- `tests/test_analytics_page.py:209` asserts **no `innerHTML`** in the analytics JS.
- `tests/test_analytics_purchase_orders.py:119-120` asserts the strings "Service activity" and
  "Engineer workload" are **absent** from the HTML for a P.O.-only user. **Therefore the tabs must
  be server-gated, not CSS-hidden.**
- `chartWidth` reads `clientWidth` (`static/js/app-analytics.js:105-110`), which is `0` inside a
  `display:none` panel and falls back to `CHART_MIN_WIDTH = 240`. Charts drawn in a hidden tab
  render at a fixed 240 px with no error.

**Two existing tests block the P.O. work and must be edited deliberately:**

- `tests/test_purchase_orders.py:256-263` asserts `product_id` is **absent** from the model.
- `tests/test_purchase_orders.py:502-547` pins the Excel export at 11 columns, `A1:K3`, and the
  cell coordinates `D2/H2/H3/F2/H5`.

**Also load-bearing:** `templates/po_details.html` defines its table header **twice** — static
markup at `:322-330` and `renderHeader()` at `:591-603` — and `tests/test_purchase_orders.py:207-217`
asserts literal strings from that file's inline JS (`const formatPHP = (value) =>`,
`row.po_type === 'contract'`, `id="po-contract-total"`, `Total amount: ₱0.00`).

`analytics_ranked_counts()` (`app.py:37704-37715`) already emits the exact `[{label,count,previous}]`
shape `renderHorizontalChart` consumes, and `product_contract_status()` (`app.py:2440`) already
supplies the coverage vocabulary the Products page uses.

### Execution steps

**Part A — the machine field.** Server before client, migration before model use, so the app is
never broken between steps.

1. **Migration.** Add `'product_serial': 'VARCHAR(100)'` to the `additive_columns` dict in
   `ensure_purchase_order_schema()` (`app.py:3531-3537`), plus
   `CREATE INDEX IF NOT EXISTS idx_purchase_order_product_serial` beside the existing index calls.
   Comment that the `ALTER TABLE ADD COLUMN` path yields a column with **no `REFERENCES` clause**
   while `create_all` on a fresh database yields one, and that this app never sets
   `PRAGMA foreign_keys` — so neither path enforces the FK and integrity comes from step 3 and
   step 5. Write that down or someone will later "fix" it with a table rebuild.
   **Done when:** run twice against a *copy* of a real database — one `[DB MIGRATION]` line, a
   no-op on the second run, and `SELECT COUNT(*) FROM purchase_order` unchanged.
2. **Model** (`app.py:1846-1870`). After `amount`, add
   `product_serial = db.Column(db.String(100), db.ForeignKey('product.serial_number'), nullable=True, index=True)`
   and `product = db.relationship('Product', foreign_keys=[product_serial])` **with no backref and
   no cascade** — deleting a machine must never delete a P.O.
   **Done when:** the app imports and every P.O. test passes except the one in step 10.
3. **Validation** (`validate_purchase_order_payload`, `app.py:39676-39723`). Resolve the serial with
   the file's own partial-update idiom (`payload.get(k) if k in payload else getattr(existing, k, None)`,
   as `po_number` does at `app.py:39679`). After the client lookup at `app.py:39713`: empty →
   `'Select the equipment/machine for this P.O.'`; `db.session.get(Product, serial)` with a
   case-insensitive fallback adopting the stored casing (`update_product` uppercases at
   `app.py:45551` but imported rows may not have) → not found:
   `'Equipment not found. Add it in Products first.'`; `product.client_id != client_id` →
   `'That machine is not registered to the selected medical center.'`. Add
   `'product_serial': product.serial_number` to the returned dict.
   **This single step delivers the legacy rule for free** — the dict is splatted into
   `PurchaseOrder(**values)` at `app.py:39950` and setattr-looped at `app.py:39992`, and **reads
   never call this function**, so legacy rows list and export fine while any edit of one is refused
   until a machine is supplied.
   **Done when:** the three refusals return 400 with those messages, and step 10's test 2 passes.
4. **Serialization.** `purchase_order_to_dict` (`app.py:39639-39660`) gains `product_serial`,
   `product_name`, `product_client_id` and `machine_display` (`"SN — Name"`, else the serial, else
   `''`). Computing the display string server-side stops the table cell, mobile card, duplicate
   warning and analytics labels drifting apart; `product_client_id` lets the modal explain a machine
   that was reassigned. In `/get_purchase_orders` (`app.py:39735-39756`) add
   `joinedload(PurchaseOrder.product)` to the options at `app.py:39741` — without it this is one
   query per row — and add a `products` array of
   `{serial_number, name, client_id, under_contract, end_warranty}` ordered by client then serial.
   **Done when:** every row carries the four new keys (`''` for legacy) and `products` is present.
5. **Guard the reference from the Products side.** Both halves are verified breakage, not theory.
   - `delete_product` (`app.py:45655-45665`): refuse with **409** when
     `PurchaseOrder.query.filter_by(product_serial=...).count()` is non-zero.
   - `update_product` (`app.py:45587-45604`): add
     `PurchaseOrder.query.filter_by(product_serial=old_serial).update({'product_serial': new_serial}, synchronize_session=False)`
     **before** the `db.session.delete(p)` at `app.py:45603`, and include the count in the
     `log_activity` line at `app.py:45606`.
   - Owner reassignment (`app.py:45621`): **do not block** — log the affected count and let the
     modal explain it on next edit. Blocking would make ordinary inventory corrections impossible.
   **Done when:** step 10's tests 6 and 7 pass.
6. **Filter and sort.** Add `'machine'` to `PURCHASE_ORDER_SORT_KEYS` (`app.py:39595-39603`); add a
   `machine` request arg matching serial **or** product name in `purchase_order_export_records()`
   (`app.py:39759-39830`); extend `sort_value` and the existing `is_empty` branch so legacy blanks
   sink to the bottom in **both** directions.
   **Done when:** `/export_purchase_orders?machine=…&sort=machine&direction=asc|desc` filters and
   sorts with blanks last either way.
7. **Excel export** (`app.py:39833-39929`). Two columns inserted after *Complete Address*, giving 13
   (A..M). Every one of these moves, and missing one leaves a file that still opens while being
   quietly wrong:

   | Thing | Line | Change |
   | --- | --- | --- |
   | `headers` | `app.py:39847` | insert `Machine Serial`, `Machine Name` at G, H |
   | row build | `app.py:39862` | insert serial and `record.product.name if record.product else ''` |
   | number formats | `app.py:39893` | `row[7]`→`row[9]` (amount), `row[8]`→`row[10]`, `row[10]`→`row[12]` |
   | TOTAL row | `app.py:39899` | column 8 → 10 in all three places; `=SUM(J2:Jn)` |
   | `auto_filter.ref` | `app.py:39909` | `A1:K` → `A1:M` |
   | `widths` | `app.py:39910` | 11 entries → 13 |

   **Done when:** headers read A..M, TOTAL is `=SUM(J2:Jn)`, and the amount is still
   currency-formatted.
8. **The modal** (`templates/po_details.html:340-393`). Replace the `<select id="po-client">` at
   `:352` with two `position-relative` blocks: a visible text input, a **hidden field keeping the id
   `po-client`**, and a results div — then the same trio for the machine with the input `disabled`
   by default. Keeping the hidden field's id means `saveForm` (`:717`) and `openForm` (`:661`) each
   change by about one line. **Use the class names `.search-results` / `.search-item`** —
   `static/css/app-dark-pages.css:82-105` already themes them globally, and a new name means a
   white-on-white dropdown in dark mode. Copy the dropdown rules from `templates/products.html:1161-1176`
   into this file's existing inline `<style>`.
   JS, inside the existing IIFE: `state` gains `products: []`; `loadData` fills it and builds the
   ambiguous-name count map; delete `populateClients()` (`:637`) and its three call sites; add one
   `setupPoAutocomplete(inputId, resultsId, hiddenId, kind)` serving both fields, built on the
   products.html skeleton, matching serial **or** name, capped at 10, rows via `createElement` +
   `textContent`. The machine branch reads `#po-client`: empty → "Select a client first."; else
   filter `state.products` on `client_id`; zero matches → render exactly **"No equipment registered
   for this client — add it in Products first."** and leave the hidden field empty. Because
   `saveForm` reads only the hidden field, **a typed machine name can never reach the server** —
   that is what enforces the no-free-text decision. Typing in the client field clears the machine
   selection immediately. `openForm` on a legacy row leaves the machine blank and shows *"This P.O.
   predates machine tracking. Select the machine to save your changes."*, and where
   `product_client_id` differs from `client_id`, *"This machine now belongs to a different medical
   center — reselect it."*
   **Do not touch** `formatPHP` (`:421`), the `po-contract-total` markup, or the
   `row.po_type === 'contract'` filters — `tests/test_purchase_orders.py:207-217` asserts those
   literals.
   **Done when:** the browser sequence in Verification passes, steps 1-5.
9. **The register table.** Add a **Machine** column after Medical Center in **both copies of the
   header** — static markup `templates/po_details.html:322-330` *and* `renderHeader()` `:591-603`.
   Then the `<td>` and mobile card line in `renderRows()` (`:605`, `—` for legacy), `machine` in
   `currentFilters()`/`filteredRows()` with blanks-last sorting, a `#po-machine-search` input in the
   filter panel, and `machine=` in the export query string.
   **Done when:** the header does not change shape between first paint and first re-render.
10. **Tests** (`tests/test_purchase_orders.py`). Edit two, add eight.
    - **`test_model_has_no_financial_or_schedule_linkage` (`:256`)** — edit deliberately, with a
      docstring saying why: a P.O. now references an **asset**; what stays forbidden is linkage to
      **work** (`shift_id`, `tsr_id`), and `product_id` stays forbidden because that is `Shift`'s
      name for a serial. **Add a positive control asserting the FK target is
      `product.serial_number`** — otherwise a future failure gets "fixed" by adding a bare string
      column and the referential meaning is gone while the test still passes.
    - **`test_filtered_sorted_excel_export_contains_complete_register_details` (`:502`)** — 13
      headers, `H2`→`J2`, `H3`→`J3`, `H5`→`J5` (`=SUM(J2:J3)`), `A1:K3`→`A1:M3`. **Add `G2`/`H2`
      assertions** so the new columns are pinned rather than merely tolerated.
    - New: (1) new P.O. without a machine → 400; (2) **legacy row lists, edit without the key → 400,
      edit with a valid serial → 200** — the mirror of `:470`; (3) machine belonging to another
      client → 400; (4) `/get_purchase_orders` carries the client-scoped `products` list; (5) the
      machine filter and sort reach the export; (6) **deleting a referenced machine → 409 and the
      P.O. survives**; (7) **renaming a serial repoints its P.O.s**; (8) the modal renders the
      combobox ids and the exact no-equipment sentence.

**Part B — Analytics tabs and the Equipment tab.**

11. **Endpoint** — extend `/get_po_analytics` (`app.py:37872-37918`) with `previous_range` and an
    `equipment` block, reusing `analytics_date_bounds()` and `analytics_ranked_counts()`, and adding
    `joinedload(PurchaseOrder.product)`. Existing keys stay byte-identical.

    ```jsonc
    "equipment": {
      "linked_total": 9, "unlinked_total": 3, "linked_pct": 75,
      "machine_total": 7, "client_total": 5,
      "by_machine":  [{ "label": "SN-1234 · CT-500", "count": 4, "previous": 2 }],  // top 10
      "by_model":    [{ "label": "CT-500", "count": 6, "previous": 3 }],            // top 10
      "by_coverage": [{ "label": "Under Contract", "count": 5 }],
      "unlinked_clients": [{ "label": "Client B", "count": 2 }]                     // backfill worklist
    }
    ```

    **Counts only, no money** — `templates/analytics.html:98` promises it and the tests read that
    contract. `by_coverage` reuses `product_contract_status()` (`app.py:2440`) so the wording matches
    the Products page rather than inventing a third vocabulary. `unlinked_clients` is the operational
    payoff: it is the backfill worklist for legacy rows. A row whose product was deleted falls into
    `unlinked_total`, never a crash.
    **Done when:** `linked_total + unlinked_total == total`.
12. **Tab shell** (`templates/analytics.html`). Build the tab list from a Jinja list populated
    **inside the existing `{% if %}` gates**, rendering the tablist only when more than one tab
    exists. The filter card (`:23-52`) and `#analytics-error` (`:54`) stay **outside** the tab shell.
    The existing `<main id="schedule-analytics">` and the P.O. `<section>` become panels; a new
    Equipment `<section>` follows. `window.ANALYTICS_CAPABILITIES` needs no new key — Equipment
    rides `purchaseOrders`.
    **Done when:** a P.O.-only user's HTML contains neither "Service activity" nor
    `data-analytics-panel="schedule"`.
13. **Equipment panel.** Follow the existing panel grammar so print support comes free via the
    `.analytics-chart-table` rule (`static/css/app-analytics.css:321`, flipped at `:363`): four
    metrics; **Top machines** and **By model** as SVG charts each with a mirror
    `<table class="analytics-chart-table">`; **Coverage mix** and **Missing a machine** as
    `renderBars` + `renderSimpleTable`. Every table needs `<caption>` and `scope="col"` —
    `tests/test_analytics_page.py:205-206` asserts both.
14. **Tab CSS and JS.** CSS in `static/css/app-analytics.css` **only**, using `var(--app-*)` tokens:
    `.analytics-tabs`, `.analytics-tab-btn`, `.is-active`, `:focus-visible`,
    `.analytics-tab-panel { display: none }`. In the existing `@media print` block (`:354-367`) add
    `.analytics-tab-panel { display: block !important }` so printing emits **every** authorized
    section, not just the visible tab; the tablist already disappears via `.no-print`.
    JS: `activateTab()` toggling `classList` and `aria-selected` (**no `innerHTML`**), arrow-key
    roving focus, and a `localStorage` restore that validates the stored tab exists in the DOM — a
    P.O.-only user must not restore a `schedule` tab that was never rendered. `updatePo` (`:411`)
    calls a new `renderEquipment()`; `resetPoDisplay` (`:32`) must clear the new nodes or the tab
    keeps stale numbers after a failed refresh.
    **Two things that silently produce a wrong-looking chart, both verified:** `CHART_FRAME_IDS`
    (`:361`) must gain the two new chart ids **and** the observer callback (`:387`) must be widened
    beyond `renderScheduleCharts(state.schedule)`; and because `chartWidth` returns `0` for a hidden
    panel, re-render a panel's charts when its tab is revealed and skip zero-width nodes in the
    observer so a hidden panel cannot record a bogus `lastChartWidths` entry that then suppresses
    the real redraw.
15. **Tests for Part B.** `tests/test_analytics_page.py`: keep `:201` and `:209` green — that is the
    point — and assert the tablist markup, the panel CSS, and that the print block covers
    `.analytics-tab-panel`. `tests/test_analytics_purchase_orders.py`: keep the two absent-string
    assertions and **add `assertNotIn('data-analytics-panel="schedule"', html)`** — that pair is
    what proves server-gating, since a CSS-only implementation leaves both strings in the DOM — plus
    assert the P.O.-only user *does* get the equipment panel. New: equipment counts
    (`linked + unlinked == total`, the legacy client named in `unlinked_clients`) and counts-only
    (no money-shaped key under `equipment`). `tests/test_analytics_chart_sizing.py`: the two new ids
    appear in the `CHART_FRAME_IDS` declaration.

### Deliberately excluded

- **Multiple machines per P.O.** Decided against by the owner. A link table, a multi-select
  checklist and a counting rule for a 3-machine P.O. in analytics is roughly double the work; the
  clarification was "per machine", which one column expresses exactly. `templates/travel_request.html:2788-2801`
  holds the multi-select pattern if this is ever revisited.
- **A free-text machine fallback.** Decided against. It would unblock the 89 of 145 clients with no
  registered equipment at the cost of the same machine being spelled three ways, which destroys the
  per-machine analytics this change exists to enable.
- **Backfilling the machine onto existing P.O. rows.** Nothing is auto-assigned — there is no
  defensible way to guess which machine an old P.O. covered. The Equipment tab's "Missing a machine"
  list is the worklist for doing it by hand.
- **A database-level FK constraint.** SQLite `ALTER TABLE ADD COLUMN` cannot add one to an existing
  table without a full rebuild, and this app never sets `PRAGMA foreign_keys`, so a constraint would
  not be enforced even where it exists. Steps 3 and 5 enforce it in application code instead.
- **Money in the Equipment analytics.** `templates/analytics.html:98` promises counts only and the
  tests read that contract. Amounts on a per-machine basis is its own decision.
- **Honouring the branch filter on any P.O. tab.** `PurchaseOrder` has no branch dimension. Recorded
  as a decision here so the "Company-wide" label is not later read as a bug.
- **Blocking a machine's reassignment to another client** when P.O.s reference it. It would make
  ordinary inventory corrections impossible; the modal explains the mismatch on next edit instead.
- **Rewriting the Analytics filter bar per tab.** The date range stays shared and global.

### Verification

**Tests, each with the control that proves it can fail.** Inject the defect, confirm the injection
*applied* (hash the file), and read the **assertion message** rather than the exit code — an
injection that aborts looks exactly like one that worked, which this project has now been caught by
twice.

```bash
python -m unittest tests.test_purchase_orders tests.test_analytics_page tests.test_analytics_purchase_orders tests.test_analytics_chart_sizing -v
```

Then the full suite — `tests/test_product_contract_status.py`, `tests/test_timeline_product_coverage.py`
and `tests/test_stock_inventory.py` all touch `Product` and are the likely collateral of step 5:

```bash
python -m unittest discover -s tests
```

Use the project venv; the documented command fails on the system Python with a misleading import
error. Suite is 635 with one pre-existing skip before this work — **re-measure rather than trusting
that number.**

**Migration proof.** Against a *copy* of a real database: exactly one
`[DB MIGRATION] Added purchase_order.product_serial`, nothing on restart, and
`SELECT COUNT(*) FROM purchase_order` identical before and after.

**Browser — `/po_details`.** Screenshots are not available here; measure geometry and computed
style, and **disable transitions before measuring anything animated** — a `.modal.fade` returns
`clientHeight: 0` on every child in this pane and the bug reads as absent.

1. Add P.O. → Medical Center is a text box; three letters gives ≤10 results; same-named clients show
   their address.
2. The Equipment field is **disabled** until a client is chosen.
3. A client **with** equipment → only that client's serials appear.
4. A client **with no** equipment → exactly *"No equipment registered for this client — add it in
   Products first."*, nothing selectable, Save refused. **No free-text machine can be saved.**
5. **Pick a machine, then change the client** → the machine clears and re-scopes. This is the step
   the design is most likely to get wrong.
6. Save → the row shows the machine; sort by Machine both ways; filter by partial serial; export and
   confirm G/H carry serial and name and TOTAL still sums the amount column.
7. Standing bar: dark mode legible (the reason for the `.search-results` naming), 375 px modal
   stacks with Save reachable, dropdown does not overflow, mobile card shows the Machine line, tap
   targets 44×44 — **both dimensions**, not whichever is convenient — console clean.

**The legacy rule — the proof that matters.** Take a real pre-existing P.O.; before this ships every
row is legacy:

- It **must** list with `—` and export without error. *Reading never calls the validator.*
- Edit it, change only the amount, Save → **rejected**, with a message naming the machine.
- Select the machine and Save → succeeds, and never regresses.
- Via devtools, a raw `PUT` **omitting `product_serial` entirely** must return **400** — the case
  the UI cannot produce, and the whole reason for the `getattr(existing, ...)` fallback in step 3.

**Browser — `/analytics_page`.**

- Reports admin: three tabs; switching redraws each panel's charts at the correct width; resize the
  window on the Equipment tab and confirm the bars re-lay-out.
- **P.O.-only user: two tabs.** View source — "Service activity", "Engineer workload" and
  `data-analytics-panel="schedule"` all absent.
- `linked + unlinked == total`; the "Missing a machine" list names real clients and shrinks by one
  per backfill.
- Ctrl+P on any tab → every authorized section prints, data tables visible, tab buttons gone.

### After implementation

### Outcome — 2026-08-12

Self-review completed against the endpoint, tab template, analytics CSS/JavaScript, focused tests,
change journal, and release manifest. The implementation matched the approved decisions: one
nullable machine serial per P.O.; legacy rows remain readable but require a machine on edit; the
Equipment analytics are counts-only, company-wide, and server-gated alongside the existing
capabilities; and no legacy P.O. or equipment row was backfilled, deleted, or rewritten.

- Part A is committed as `081d647` and Part B as `fd781b1`; the two implementation halves remain
  independently reviewable. The Part B service-worker cache moved from live `v86` to `v87`, and
  both analytics asset query strings moved from `v77` to `v78`.
- `changes.md` and the dated `2026-08-12` release entry were updated. The release entry now covers
  both machine-scoped P.O. records and the Equipment analytics tab.
- Focused analytics verification passed 24 tests; the full regression suite passed 643 tests with
  no failures or skips. `python -m py_compile app.py`, `node --check static/js/app-analytics.js`,
  JSON parsing, and `git diff --check` also passed.
- Browser verification used a fresh isolated database on port 5058. Reports access showed three
  tabs; Equipment charts redrew after reveal and at 375px with no horizontal overflow; keyboard
  arrow navigation moved focus and panels; P.O.-only access showed exactly Purchase orders and
  Equipment with no schedule markup; linked/unlinked counts rendered; and browser console
  warnings/errors were empty. Print behavior was covered by the print CSS and source assertions;
  the in-app browser run did not invoke the native print dialog.
- The database, generated output, temporary QA files, loose handoff artifact, and deployment state
  were deliberately excluded. Push and deployment remain pending a separate owner instruction.

- Re-read this plan against the diff and amend this entry if the implementation differed.
- Add a dated `changes.md` section, newest first. Do not log secrets or database contents.
- One `static/changelog/releases.json` item dated the commit date. **Re-run
  `tests/test_changelog_coverage.py` after committing** — it reads git for the latest commit and
  cannot see the commit before it exists.
- **`CACHE_VERSION` bump required for Part B**: `static/css/app-analytics.css` and
  `static/js/app-analytics.js` are both `APP_SHELL` entries and both change. **Read the live value
  out of `app.py` immediately before committing, never from this document** — that line has gone
  stale four times. Part A alone would need no bump, since `/po_details` is not in `APP_SHELL`.
- Bump the `?v=` params in `templates/analytics.html:3-4` and `:117` **in the same commit**. A fresh
  `CACHE_VERSION` against a stale `?v=` is how a user gets new markup with old CSS.
- Consider landing Part A and Part B as **two commits** — Part A needs no worker bump, and the two
  halves fail in unrelated ways.
- Stage explicitly, file by file. Never stage `scheduler.db`, `output/`, `tmp/`, or the loose
  2026-07-26 handoff. Re-read `origin/main` **after** finishing, not only before starting.
- Push or deploy only after a separate owner instruction.

### Risks

Ranked by "would ship and nobody notices" — the failure mode this project keeps meeting.

1. **Charts drawn inside a hidden tab** render at a fixed 240 px and stay wrong, with no error.
   There is no JS runner in this suite, so **only a browser can catch it.**
2. **A serial rename orphans P.O. rows** if step 5 is missed — verified breakage, not theory
   (`app.py:45598` repoints `Shift` only). The symptom is a blank cell.
3. **Deleting a product** silently blanks live P.O. rows; `app.py:45655` has no guard today and
   there is no DB-level FK behind it.
4. **Two copies of the P.O. table header.** Change one and the header silently changes shape after
   first render, with `data-sort` drifting out of step with the cells.
5. **The Excel index shift.** Miss one and the file still opens — the amount just stops being
   currency-formatted, or TOTAL sums the wrong column. This is the artifact Accounting consumes.
6. **Literal-string tests in `po_details.html`** (`tests/test_purchase_orders.py:207-217`) — a
   tidy-up while working nearby fails a test about a different feature.
7. **CSS-gated instead of server-gated tabs** passes casual review, fails the P.O.-only test, and
   would leak future schedule strings to a P.O.-only account.
8. **Operational, not technical: 89 of 145 clients have no equipment registered**, so P.O. entry for
   those clients is blocked until Products is backfilled. Correct behaviour, and the largest change
   users will feel on day one. Say so plainly rather than letting it read as broken.

Items 1 and 4 are exactly the shape of the last round's finding — **three of four defects were
suite-invisible and browser-obvious.** The browser pass here is not a formality after the tests; for
those two it is the only thing that works.

## Reimbursement Tracker — round two

**Status:** `Executed — 81b4f1b` (implementation by Codex, plus two fixes from the review here, in
the same commit). Suite green at 634 with one pre-existing skip. **Not pushed** — push and deploy
remain separate owner decisions.
**Reviewed:** 2026-08-12, by running it rather than reading it. **No defects.** The two fixes were a
per-request cost — the duplicate scan re-read every engineer row on every request, 0.353 ms against
0.039 ms for a flag-guarded sibling — and the suggestion chips having no regression guard at all.
One of Codex's tests was also corrected: it re-called the legacy correction without clearing the
ready flag, so it only proved the flag short-circuits rather than that the anchor protects a manual
edit. The riskiest items all held: the export's Total is a literal (no `#REF`), the correction
renames only `00021`, and one engineer's suggestion chips never appear for another.
**Approved:** 2026-08-12
**Detailed:** 2026-08-12, after mapping the email/recipient-group infrastructure, reading the
Personnel write routes and the export builder, and checking the live database for duplicate
initials, engineer email coverage and tracker row counts.

**Execution outcome (2026-08-12):** Steps 1–20 were completed in the working tree. The
intentional scope is `app.py` (initial validation/correction, export, and paid email), the two
affected templates, focused regression tests, `changes.md`, and `static/changelog/releases.json`.
No service-worker bump, database/runtime artifact, output/tmp/handoff artifact, commit, push, or
deploy was included. The focused suite passed 27 tests after the final logging-only adjustment;
the full suite passed 632 tests before that adjustment. The corrected pre-fix archive used the
same injected tests and went red with 7 failures plus 6 missing-behavior errors. Browser checks
confirmed the per-engineer chips, tap-to-fill total, 375px modal Save reachability, and export
success toast; the in-app browser's download-event hook did not capture the file event. The
release manifest parses and contains the new item. `tests/test_changelog_coverage.py` remains a
post-commit check because it evaluates the latest git commit, and no commit exists yet.

### Context

Four follow-ups the owner asked for on 2026-08-12 after using the register shipped in `018cfd0`.
**Changes 1-3 touch `app.py`; change 4 is frontend-only.**

1. **Duplicate engineer initials.** The register warns *"Duplicate engineer initials detected: JP"*.
   `JP` is held by **Jocel Prudente** (id 25, Davao, employee_id `00021`) and **Jonamar Paunil**
   (id 3, Manila, employee_id `18-185`). Initials feed the control number `INITIALS-<date>-NNN`, so
   a duplicate makes two people's control numbers indistinguishable. Nothing prevents it today.
2. **The export carries far more than Accounting needs** — *"remove the above header, she only needs
   the 2nd header, and the column should be cut to Total only."*
3. **No notification on payment.** Marking a row Paid in Full tells the engineer nothing.
4. **Re-typing the same amounts** every batch, with no suggestion from what that engineer claimed
   before.

### Decisions taken

Settled by the owner on 2026-08-12. An executor should not reopen any of these.

| Decision | Value |
| --- | --- |
| Jocel Prudente's initials | **`JOP`** |
| Export columns | **A-G only**, stopping at Total |
| Production data fix | **One-time automatic correction**, so the live site self-corrects on deploy |
| Email trigger | **Only the false→true transition** of `paid_in_full`, on an existing row |
| Re-toggle | **Re-sends** — a correction is real news, the amount may have changed |
| Amount suggestions | **Tappable chips** under each field; nothing fills without a tap |
| Suggestion source | **Tracker rows only**, not the older reimbursement feature |

### Investigation

- **`employee_id` uniqueness is the precedent to copy**: `app.py:45051-45052` (add) and
  `app.py:45178-45179` (update). Initials are assigned unvalidated at **`app.py:45182`**.
- **`00021` is a safe anchor for the correction.** `bootstrap_static_accounts()` (`app.py:45917`)
  seeds `Jonamar Paunil / JP / 18-185`, so a name-only or initials-only guard could rename the
  wrong person. Anchoring on employee_id **and** the stale value `JP` cannot.
- **The tracker table is empty in the live database (0 rows)**, so no `engineer_initials_snapshot`
  holds a stale `JP` and no existing control number becomes ambiguous. **Re-check before running** —
  this stops being true the moment Diary files a row.
- **23 of 27 engineers have an email.** The four without are **Jocel Prudente, John Erick Wong,
  Kevin Garoche, Mark Felongco** — so the notification silently no-ops for them unless the route
  says so.
- **Recipient groups are fully generic**: `EmailRecipientSetting` (`app.py:1715`), registry
  `EMAIL_RECIPIENT_GROUPS` (`app.py:362-407`), order (`app.py:409-421`), read helper
  `get_active_email_recipients_by_group()` (`app.py:3107`). A new group is a registry entry, an
  order entry and two `templates/settings.html` lists. **No migration, no new table.**
- **`send_email_with_attachments()` (`app.py:9054`) is the only dispatcher with `cc_emails`** —
  `send_email_notification()` (`app.py:9123`) has none.
- **`update_reimbursement_tracker_entry()` (`app.py:40361`) blindly `setattr`s every validated
  field**, so it cannot see a transition; it must be captured before the loop.
- **Column G is `=SUM(I{r}:R{r})`.** Cutting I-R without changing G leaves every Total a `#REF` —
  the highest-consequence detail here.
- **The suggestions need no server change at all.** `reimbursement_tracker_entry_to_dict()` already
  returns all ten category amounts (`app.py:40047-40048`) with `engineer_id` and `submission_date`,
  and `loadData()` puts every row in `state.rows`.

### Execution steps

1. **`engineer_with_initials(initials, exclude_id=None)`** above `add_engineer` (~`app.py:45005`),
   comparing `func.lower(Engineer.initials)` — case-insensitive, because every consumer upper-cases
   before building an identifier. **Done:** returns the holder, or `None`.
2. **`add_engineer()`** — refuse a duplicate after the employee_id check (`app.py:45051`), guarded on
   `staff_type == 'engineer'` exactly as that check is. 400 naming the current holder.
3. **`update_engineer()`** — read `name`/`initials` with `.get` and validate *before* assigning at
   `app.py:45182`. **Self-exclusion by `id`, not by value**, so re-saving a row's own initials in a
   different case is not a self-collision. The `.get` also fixes a latent 500 on a missing key.
4. **`ensure_unique_engineer_initials()`** beside `ensure_reimbursement_tracker_schema()`
   (~`app.py:3554`) with a `_engineer_initials_correction_ready` flag. Matches on **employee_id
   `00021` AND name `jocel prudente` AND initials `JP`** → sets `JOP`, commits, logs. All three must
   match, so it is a no-op once corrected and **cannot fight a later manual edit**. Then always
   recompute remaining duplicates and log them — an honest ops signal, not a silent claim.
5. **Wire it into both startup paths** after `ensure_reimbursement_tracker_schema()`:
   `initialize_database()` (~`app.py:45991`) and the `before_request` hook (~`app.py:45768`).
6. **No DB unique index, deliberately.** `CREATE UNIQUE INDEX` fails while a duplicate exists and
   every `ensure_*` swallows it in `try/except` — that ships a *silently absent* constraint that
   reads as enforced. **Record the reason in the docstring** or the next reader will add it.
7. **Ship all of step 1 in one commit**, validation before correction, so nothing can recreate `JP`
   in between.
8. **Export**: delete the row-1 banners, both `merge_cells`, and `A5 'Reimbursements'`.
9. **One header row at row 1** — Reference, Submission Date, Control #, Reimbursement, Engineer,
   Office, Total. Drop the `for row_number in (2, 6)` loop and the label splat.
10. **Data from row 2**, and **column G becomes the literal `record.total`**, not a formula. Delete
    `category_values` and the four formula writes at columns 23-26.
11. **Geometry shifts**: header fill on row 1; `freeze_panes='A2'`; `auto_filter.ref=f'A1:G{last}'`;
    widths `[18,16,20,34,28,14,15]`; number formats only on cols 2 and 7.
12. **Delete every `workbook.calculation.*` line** — dead once no formula remains. The nested-`IF`
    payment-status string goes with them; **that decision is not reversed, the column just ends.**
13. **Rewrite the `REIMBURSEMENT_TRACKER_EXPENSE_FIELDS` comment** (`app.py:1868`). Its claim to
    preserve "the workbook's Accounting-facing spellings" stops being true once nothing writes them
    to a workbook. Say they are the register form's labels, mirrored by hand in
    `templates/reimbursement_tracker.html:258-263`, and must not be corrected on one side only.
14. **New recipient group** `reimbursement_tracker_paid_cc` in `EMAIL_RECIPIENT_GROUPS` and
    `EMAIL_RECIPIENT_GROUP_ORDER`, mirrored in the two `templates/settings.html` lists.
15. **`reimbursement_tracker_engineer_email(entry)`**: `entry.engineer.email` →
    `get_user_email_for_notification()` on the linked User → `''`. **Never the name snapshot.**
16. **`format_reimbursement_tracker_paid_email(entry)`** → `(subject, text, html)`, pure and
    side-effect free so it is testable without threads.
17. **`send_reimbursement_tracker_paid_email_async(app_obj, entry_id)`** shaped like
    `send_reimbursement_notification_email_async` (`app.py:7387`) — id normalised outside the
    thread, worker re-fetches by id, CC from the group, sent via `send_email_with_attachments`.
    **No engineer address → log and return; do not fall back to CC-only.**
18. **Route**: capture `was_paid_in_full` before the setattr loop; fire **after** a successful
    commit so a rollback never mails. Comment `add_reimbursement_tracker_entry` to say creation
    deliberately never mails.
19. **Warn Diary synchronously** when the engineer has no address — `warning` in the JSON, surfaced
    by `notify(data.warning, 'warning')` in `saveForm` (~`:533`).
20. **Suggestions**: `SUGGESTION_LOOKBACK = 3`; `recentRowsForEngineer(engineerId, excludeId)`
    sorted by date then id descending; `renderCategorySuggestions()` dropping zero/blank values and
    deduping, rendering `<button type="button" class="rt-suggest-chip">` into a per-field container.
    Click fills the input and calls `updateFormTotal()`. Trigger from the existing engineer `change`
    listener (`:594`) and on modal open; clear in `resetForm()`. **Verify the theme token names
    against `static/css/app-themes.css`** — a transposed custom property is invisible.

### Deliberately excluded

- **A `paid_notified_at` column** — the owner chose re-send per transition.
- **Emailing on create**, and **rewriting `engineer_initials_snapshot`** on existing rows.
- **A unique index on `initials`** — see step 6.
- **Changing `REIMBURSEMENT_TRACKER_EXPENSE_FIELDS` values**, including the two typos.
- **Seeding suggestions from the older reimbursement feature** — lossy category mapping, and it
  would undo the standalone decision.
- **Prefilling amounts automatically** — prefilled figures that are never reviewed get saved
  unchanged. Every suggested amount needs a deliberate tap.

### Verification

Tests in `tests/test_reimbursement_tracker.py` plus a new `tests/test_engineer_initials.py`.
Behaviour by building an account and calling the route; source assertions only for inline
template/CSS, and then only on an outcome. **Every new test proven to fail without its fix, with the
injection confirmed applied** — CRLF files, so a `\n` needle silently matches nothing.

- Duplicate initials refused on add (`ZZQ` then `zzq` → 400 naming the holder) and on edit; a row
  re-saving **its own** initials in a different case still succeeds (a value-comparison
  implementation fails this).
- `PUT /update_engineer/<id>` with only `employee_id` → 400, not 500.
- **The correction renames only `00021`**, leaves `18-185` untouched, and re-running after a manual
  edit to `JX` leaves `JX` alone.
- **Total is a number, not `#REF`**: `G1 == 'Total'`, `H1 is None`, `G2` numeric, and **no cell
  anywhere holds a string starting `=`**.
- Geometry: `freeze_panes == 'A2'`, `auto_filter.ref == 'A1:G<n>'`, `max_column == 7`, and none of
  `Current Input` / `by: Diary Dizon` / `Accounting` / `Reimbursements` / `Summary` /
  `Trasnportation` / `Payment Status to Engineers` survives anywhere.
- `assertFalse(workbook.calculation.iterate)`.
- **The two typos keep an anchor**: assert the constant holds both spellings *and* that
  `GET /reimbursement_tracker` renders both. The export used to pin this; do not skip it.
- Email fires exactly on transition: create-already-paid → none; unpaid→paid → one; re-save → still
  one; untick then retick → two. Patch `app_module.send_reimbursement_tracker_paid_email_async`
  (module-attribute rebinding per `tests/test_changelog_workflow.py:409-462`) to avoid the thread.
- No-address engineer → wrapper not called, 200, `warning` contains "no email address".
- CC group seeded via `_seed_group()` and read back; formatter carries control number, reference,
  total and transfer date. **No provider is ever contacted.**
- **Suggestions are browser-verified, not suite-verified** — there is no JS runner. Two engineers
  with different amounts: the chips must match only the selected engineer. Confirm a chip fills the
  field and updates the total without submitting, that a row being edited does not suggest from
  itself, and that **Save is still reachable at 375 px** now that ten fields gained a chip row.

**Canary:** `test_list_returns_offices_engineers_suggestion_and_duplicate_initial_warning` (`:294`)
asserts `'JP' in duplicate_initials` and is safe only because its fixture uses `RT-<suffix>-N`
employee ids. **If it fails, the correction's guard is too loose** — treat it as the canary, not as
a test to update.

Then the focused run, the full suite against the **626 green + 1 skip** baseline, and a browser pass
including a real exported `.xlsx`.

### After implementation

- Re-read this plan against the diff and amend the entry if the implementation differed.
- Add a dated `changes.md` section, newest first; do not log secrets or database contents.
- One `static/changelog/releases.json` item dated the commit date. **Re-run
  `tests/test_changelog_coverage.py` after committing** — that guard reads git for the latest commit
  and cannot see the commit before it exists.
- **No `CACHE_VERSION` bump**: `templates/timeline.html` and `layout.html` are untouched.
- Stage only intentional source/template/test/journal/manifest files. Never stage `scheduler.db`,
  `output/`, `tmp/`, or handoff artifacts.
- Push or deploy only after a separate owner instruction.

### Risks

1. **`#REF` on every Total** if step 10 is missed — the one change that would corrupt the artifact
   Accounting actually consumes.
2. **Jocel's future Online TSR numbers restart.** `online_tsr_next_number_for_date()`
   (`app.py:11084`) builds `YYYYMMDD-NN-<INITIALS>`, so the `JOP` daily sequence starts at `01`.
   Historical values are stored strings and are unaffected — a visible discontinuity, not corruption.
3. **A threaded send that fails is invisible.** `send_email_with_attachments` returns
   `(False, reason)` and never raises, so a dead key shows only in stdout. The synchronous warning
   covers *no address on file*, **not delivery failure** — "no warning" must not be read as "sent".
4. **Re-toggling re-sends**, by decision; an accidental untick-retick duplicates the mail.
5. **Personnel writes gain a refusal path** that did not exist, so a save that used to succeed can
   now 400. Correct, but it is the change existing users will feel.
6. **Suggestions look empty on day one** — the tracker has no rows. Expected, not a defect, but say
   so or it reads as broken.
7. **Suggestions are a convenience, never a source of truth** — they reflect what was *claimed*
   before. Do not later "improve" tap-to-fill into automatic prefill; that is how a stale figure
   gets paid.

## Reimbursement Tracker

**Status:** `Executed — 018cfd0` (implementation by Codex, plus four fixes from the review here, in
the same commit). Suite green at 623 with one pre-existing skip.
**Reviewed:** 2026-08-11, by running it rather than reading it. Four defects were found and fixed
before the commit — the one that mattered was **dark mode at 1.04:1 contrast**, caused by the
transposed token `--app-raised-surface` (the real one is `--app-surface-raised`) silently taking a
light-only fallback. **It landed exactly in the verification gap Codex had honestly declared**, the
375 px pass it could not run. The other three: a constant that looked like a switch and controlled
nothing, `office` accepted as unvalidated free text by the endpoint, and the release item filed
under an unrelated headline. **Two spec errors were mine, not the implementation's** — the plan said
the export helper raises on a bad sort key, but the P.O. precedent it was told to mirror falls back
to a default and only raises for dates; and a review probe asserted 403 for an inactive account
where `login_required` correctly returns 302 first.
**Implementer:** Codex, by the owner's decision on 2026-08-11. This plan was written here and
deliberately not started; the review afterwards happens in this repository, per the established
build-then-review split.
**Approved:** 2026-08-11
**Detailed:** 2026-08-11, after reading all three sheets of `forms/Reimbursement tracker.xlsm`
(including its VBA project, data validations, defined names and array formulas), profiling its 222
log rows, and inspecting the `Engineer` model, the capability-flag pattern, and the P.O. register
that this feature copies.

### Context

`forms/Reimbursement tracker.xlsm` is a macro workbook maintained by hand by **one user (Diary
Dizon)**. It holds **222 rows, 25 engineers, Jun 2025 – Aug 2026, ₱2,086,392.26**. Sheet `Input` is a
data-entry form, sheet `Sheet` is the log sent to Accounting, `Sheet1` holds lookup lists. This
feature replaces the workbook with a register page plus an Excel export that reproduces `Sheet`, so
Accounting's downstream process is unchanged.

This is **not** the app's existing reimbursement feature (`ReimbursementHeader` / `ReimbursementRow`,
submit → approve → accounting → paid), which stays untouched. The tracker is a standalone log, and
many of its rows never were app reimbursements — *"PostQual with BAC of Davao Occidental General
Hospital"*, *"Service Meeting Meals"*.

### Decisions taken

Settled by the owner on 2026-08-11. An executor should not reopen any of these.

1. **Manual entry, standalone.** Rows are typed. Not auto-fed from app reimbursements.
2. **The xlsm's 10 categories exactly** — not the app's `REIMBURSEMENT_EXPENSE_FIELDS` (app.py:22053),
   which differ: the app has `office_supplies` + `parking_coding` where the sheet has Service
   Materials + Hotel Accommodation.
3. **A new grantable capability flag**, following `po_admin_access`. Starts granted to one account.
4. **Start empty.** The 222 historical rows are not imported.
5. **Fix the two Control # bugs, keep the format.**
6. **Track columns S–U in the app**; export V–X blank with live formulas for Accounting to fill.
7. **Engineer names come from the `Engineer` table**, not a static list.

### Investigation

**Two defects in the workbook, both fixed by construction rather than by reimplementing the formula:**

- `Input!H2` is `IFS(...ISNUMBER(SEARCH("Jim",))...)` — the second argument is missing, so the
  abbreviation is an error. **7 of 222 rows carry Control # `#N/A`.**
- The same formula tests `"Rod"→RB` before `"Rod"→RAJ`, so the later branch is unreachable and
  **Rodito Aretano Jr. receives Rodney Banza's initials.**

`Engineer.initials` (app.py:1774, `String(10)`, NOT NULL) already exists and the live table already
holds the correct codes — `Jim Frederick Lim→JFL`, `Rodito Aretano Jr→RAJ`, the exact two values the
formula gets wrong. **No new column is needed for abbreviations**, and reading this column makes both
defects unreachable.

**The finding that changed the design, and it contradicts the first reading of the sheet.** The `NN`
in `INITIALS-DATE-NN` was assumed to be a per-engineer daily sequence. Measured against the 222 rows,
it is **the batch number**:

- `NN == batch number` in **188 of 208** parseable rows (BATCH-001→`01`, BATCH-010→`010`,
  BATCH-014→`014`). The 20 mismatches are manual drift inside a batch.
- **Control numbers are NOT unique — 43 are shared by more than one row** (`MDC-2026087-029` appears
  6 times). A unique index would reject real usage outright.
- The date token is the **submission date** (206/208), rendered `yyyy` + `mm` + **unpadded** `d`.
- Width is `%03d` in practice (192 rows are 3-digit), despite `Input!D8` instructing "Use 2 digits".

Consequences: **no unique index, no sequence allocation, no concurrency retry, no 99-exhaustion
case.** The control number is a pure function of `(initials, submission_date, reference)`.

**Reference pattern to copy**, verified: `po_details_page()` app.py:39375, `/get_purchase_orders`
39384, `purchase_order_export_records()` 39408 (not a route — re-applies the register's filters and
sort server-side from `request.args`), `/export_purchase_orders` 39482 (openpyxl, header fill
`16243A`, `number_format`, `freeze_panes`, `auto_filter`, `add_activity_log_entry`, `io.BytesIO` →
`send_file`), CRUD 39580/39614/39656, and `templates/po_details.html`.

**Capability wiring**, verified: `_has_active_account_capability` app.py:8015, `can_manage_purchase_orders`
8040, capability columns 1498-1514, `ensure_user_admin_capability_columns()` already loops a tuple at
3411-3417 so the new column is a one-line addition. `NETWORK_ONLY_DOWNLOAD_PREFIXES` (app.py:15273)
already contains `'/export_'`, so the export route is covered **by prefix** — to be pinned by a test
rather than trusted.

### Execution steps

1. **Model.** Add `ReimbursementTrackerEntry` beside `PurchaseOrder` (app.py:1839), table
   `reimbursement_tracker_entry`, with the columns listed in the approved plan: `reference`,
   `submission_date`, `control_number` (stored, **not** unique), `batch_sequence`, `description`,
   `engineer_id` + `engineer_name_snapshot` + `engineer_initials_snapshot`, `office`, `total`, the
   ten `Numeric(12,2)` category columns, `paid_in_full` / `paid_amount` / `paid_transfer_date`,
   `remarks`, and the `created_*` / `updated_*` pair. Use `Numeric(12,2)`, not `Float`, reusing the
   `PurchaseOrder.amount` precedent (app.py:39256). **Done:** the model imports and
   `__table__.create()` succeeds against a scratch database.
2. **Category constant.** Add `REIMBURSEMENT_TRACKER_EXPENSE_FIELDS` beside the model — the ten
   `(field, label)` pairs in sheet order, **including the sheet's typos `Trasnportation` and
   `Hotel Accomodation`**, with a comment saying they are deliberate because Accounting pastes these
   columns downstream. Deliberately not placed near `REIMBURSEMENT_EXPENSE_FIELDS` (app.py:22053) so
   the two are not conflated. **Done:** one constant drives model, form and export.
3. **Migration.** Add `ensure_reimbursement_tracker_schema()` after `ensure_purchase_order_schema()`
   (app.py:3428) with a `_reimbursement_tracker_schema_ready` global: `__table__.create(checkfirst=True)`,
   additive-column dict against `PRAGMA table_info`, `CREATE INDEX IF NOT EXISTS` on
   `submission_date`, `reference`, `control_number`, `office`. Call it at startup beside
   `ensure_purchase_order_schema()` at **app.py:45030 and 45252**. **Done:** a fresh database and an
   existing one both come up clean.
4. **Capability column + helper.** Add `reimbursement_tracker_access` at app.py:1514; add
   `'reimbursement_tracker_access'` to the tuple at 3411-3417; add
   `can_manage_reimbursement_tracker()` at app.py:8043. **This single helper is the page gate, every
   endpoint gate and the nav predicate** — the "same expression" rule satisfied structurally.
   **Done:** the helper is the only gate expression anywhere in the feature.
5. **Settings + nav wiring.** `approval_user_to_dict` **app.py:7894 reporting the stored grant** with
   the comment from 7887-7893; nav context 1303; save route 17288, 17306, 17381, 17420, 17447;
   Add-Personnel 44294 / 44373; `templates/settings.html` 1820, ~1910 (class
   `reimbursement-tracker-access-input`, label "Reimbursement tracker access"), 2071;
   `templates/layout.html` 130, 135 (`records_paths`), ~267 (`nav_link` in Records).
   **Done:** granting the flag in Settings makes the nav entry appear for the grantee and nobody else.
6. **Control-number helper.** One function producing
   `f'{initials}-{d.year}{d.month:02d}{d.day}-{batch_sequence:03d}'` from the **submission date**
   (never `TODAY()`), behind `REIMBURSEMENT_TRACKER_CONTROL_DATE_FORMAT`. Computed once at save and
   stored. **Done:** deriving `NN` from `reference` removes the 20 drift rows by construction.
7. **Validator.** `total` always recomputed server-side as the sum of the ten fields, ignoring any
   client-supplied total; `paid_amount` forced to `total` when `paid_in_full` and `NULL` otherwise,
   in one place, mirroring `T =IF(S=TRUE,G,"")`. **Done:** the two can never drift.
8. **Routes.** The six in the approved plan, each calling the migration first, page redirecting to
   `dashboard_page` and APIs returning `denied(...)`. The list endpoint also returns `offices`,
   `engineers`, `suggested_reference` and `duplicate_initials`. Every mutation calls
   `add_activity_log_entry` naming the control number. **Done:** all six behave correctly for a
   granted and a non-granted account.
9. **Export helper.** `reimbursement_tracker_export_records()` modelled on
   `purchase_order_export_records()` (app.py:39408) — `request.args`, a sort whitelist, `ValueError`
   on bad input, caller returns 400.
10. **Excel export.** Reproduce `Sheet` exactly: banners `A1`/`S1`/`V1`, headers on rows 2 and 6,
    `A5 'Reimbursements'`, data from **row 7**. Per row `r`: `G` `=SUM(I{r}:R{r})`, `H` empty, `S`
    a real bool, `T`/`U` literals, `V` blank, and these four live formulas:

    ```
    W  =IF(V{r}=TRUE,G{r},"")
    X  =IF(W{r}<>"",IF(X{r}="",TODAY(),X{r}),"")
    Y  =IF(OR(V{r}=TRUE,W{r}<>""),W{r}-G{r},0)
    Z  =IF(Y{r}<0,"OVER PAID",IF(Y{r}>0,"EXCESS REIMBURSEMENT BY ACCTG.",""))
    ```

    **`Z` is a nested `IF`, not the workbook's `IFS`, by the owner's decision on 2026-08-11.**
    `IFS` requires Excel 2016+ and yields `#NAME?` in older Excel and some LibreOffice builds, and
    this column is read by Accounting rather than by us. The nested form is exactly equivalent: `Y`
    is always numeric (it is itself a formula ending in `0`), so the `IFS` arm `Y=0 → ""` is the
    same as the nested `else ""`. **Do not "modernise" this back to `IFS`** — a test pins it.

    **Every formula built with an f-string on `r` — a hard-coded `7` is the most likely defect
    here.** Set
    `workbook.calculation.iterate = True` (with `iterateCount`/`iterateDelta`), because `X` is
    self-referential exactly as the workbook's `U` and `X` are and Excel otherwise computes 0 behind a
    circular-reference warning. No TOTAL row. **Done:** a real export opens in Excel with no warning
    and computes when a `V` box is ticked.
11. **Frontend.** New `templates/reimbursement_tracker.html` modelled on `po_details.html`, with the
    form mirroring the `Input` sheet in order and the office→engineer filter replacing `INDIRECT`.
    Warning banner when `duplicate_initials` is non-empty.
12. **Service worker.** Bump `CACHE_VERSION` (app.py:15234) because `layout.html` is an `APP_SHELL`
    asset. **Read the live value out of `app.py` immediately before committing**, never from this plan.
13. **Changelog.** Add a `static/changelog/releases.json` entry dated the commit date, or
    `tests/test_changelog_coverage.py` fails.

### Deliberately excluded

- **Importing the 222 historical rows.** The owner chose to start empty.
- **Auto-populating from `ReimbursementHeader`.** Rejected: many tracker rows never were app
  reimbursements, and the two category sets do not match.
- **A unique constraint on `control_number`.** Measured to be wrong — 43 real control numbers are
  shared by more than one row.
- **Padding the date token to `yyyymmdd`.** The ambiguity is real (Jan 12 and Nov 2 both render
  `2026112`) but the owner chose to keep the existing format; the constant makes it a one-line change.
- **Auto-disambiguating the duplicate `JP` initials.** That would invent a code Accounting has never
  seen. Surfaced as a warning for the owner to fix in Personnel instead.
- **Touching the existing reimbursement feature** in any way.

### Verification

Tests in `tests/test_reimbursement_tracker.py`, modelled on `tests/test_purchase_orders.py`, with
accounts built in `setUpClass`. **Authorization is tested by building an account and calling the
route — never by asserting source text.** Each test must be proven to fail without its fix, and the
injection confirmed to have applied (files are CRLF; a `\n` needle silently matches nothing).

- `test_authorization_and_escalation_boundary` — non-granted: page 302 **and all five APIs 403**;
  granted: 200/201. Granting the flag via `/add_engineer` as a non-superadmin → 403.
- `test_page_and_endpoints_flip_together` — flip the stored flag, assert page and every endpoint move
  in lockstep.
- `test_settings_reports_the_stored_grant_not_the_effective_permission` (mirror :253) and
  `test_saving_an_unrelated_permission_does_not_grant_tracker_access` (mirror :284).
- `test_writes_are_refused_without_the_capability` (mirror :307), asserting the row count is unchanged.
- `test_control_number_uses_engineer_initials_from_the_table` — `JFL-`/`RAJ-`, never `RB-`, never `#N/A`.
- `test_control_number_sequence_comes_from_the_batch_reference` — three engineers in `BATCH-031` all
  get `-031`, and a second row for the same engineer in the same batch is **allowed and identical**,
  pinning that control numbers are deliberately not unique.
- `test_control_number_is_stable_after_engineer_initials_change`.
- `test_total_is_recomputed_server_side` — a forged total is ignored; `paid_amount == total` iff `paid_in_full`.
- `test_export_reproduces_the_workbook_layout` — banners, both header rows **including the two
  typos**, `A5`, data at row 7, and with **two** records `W8/X8/Y8/Z8` carrying row-**8** formulas
  while `V7`/`V8` are `None`. This is the positive control against a hard-coded row number.
- `test_export_enables_iterative_calculation`.
- `test_payment_status_uses_nested_if_not_ifs` — assert `Z7` starts `=IF(` and that **no formula
  anywhere in the sheet contains `IFS(`**, so the compatibility decision cannot be undone by a later
  tidy-up. Assert the behaviour too, not just the spelling: build three records with `paid_in_full`
  set and `paid_amount` above, below and equal to the total, and check each `Z` formula's arms carry
  `OVER PAID` / `EXCESS REIMBURSEMENT BY ACCTG.` / `""` against the right comparison. Positive
  control: substituting the `IFS` form must fail this test.
- `test_export_route_is_network_only_in_the_service_worker` — parse `NETWORK_ONLY_DOWNLOAD_PREFIXES`
  out of the inlined worker and assert the route matches a prefix.
- `assert_cache_version_at_least(...)` — a **floor**, never an exact pin.

Then: the focused run, then the full suite against the **605 green + 1 skip** baseline. Browser bar:
drive the real page with an explicit `MEDICAL_SERVICE_TEST_DB` (never port 5000) — create, confirm
the control number, edit, tick Paid in Full, delete — then 375 px and dark mode (disable transitions
first; the Browser pane never advances the animation timeline), console clean. **Open a real exported
`.xlsx` in Excel** and confirm the banners and both header rows land where Accounting expects, that
ticking a `V` box makes `W`/`X`/`Y`/`Z` compute, and that no circular-reference warning appears.

### After implementation

- Re-read this plan against the diff and amend the entry if the implementation differed.
- Add a dated `changes.md` section, newest first; do not log secrets or database contents.
- Validate the release manifest, run the focused and regression tests, and record exact results.
- Stage only intentional source/template/test/journal/manifest files if the owner later authorizes a
  commit. Never stage `scheduler.db`, `output/`, `tmp/`, or handoff artifacts.
- Push or deploy only after a separate owner instruction.

### Risks

1. **Two engineers share initials `JP`** — Jonamar Paunil (Manila) and Jocel Prudente (Davao). Their
   rows in the same batch on the same date get identical control numbers. Since control numbers are
   already non-unique by design, this is a **data-quality note, not a blocker**; surfaced via
   `duplicate_initials` for the owner to fix in Personnel (`String(10)`, no schema change).
2. **`yyyymmd` is ambiguous** — Jan 12 and Nov 2 both render `2026112`. Kept by owner decision.
3. ~~**`=IFS` needs Excel 2016+**~~ — **RESOLVED by the owner on 2026-08-11 before implementation
   started: use a nested `IF`.** Column `Z` is read by Accounting, not by us, so an unknown Excel
   version there is not a risk worth carrying for no gain. See execution step 10 for the exact
   formula and the equivalence argument. The export therefore emits **no `IFS` anywhere**, and a
   test asserts that so it cannot creep back.
4. **`office` is denormalised from `Engineer.branch`** — a transferring engineer keeps the office each
   historical row was filed under. Correct for an accounting log; comment it so it does not read as a bug.
5. **The `S1` banner hard-codes one person's name.** Correct today, wrong if the capability is ever
   granted to a second account.
6. **`Engineer` has no `is_active`** — departed engineers stay in the dropdown. Left unfiltered
   deliberately; filtering through the linked `User` would silently drop engineers with no user row.
7. **Blast radius.** Additive throughout: a new table, a new nullable-defaulted capability column, a
   new page and routes. The one shared edit is the capability plumbing in Settings, where the failure
   mode is a phantom grant — covered by the two mirrored tests. The service worker bump is the other
   shared surface; getting it wrong ships stale nav to field devices.

## P.O. Dates, Amount, and Complete Excel Export

**Status:** `Executed — 3d66caf; documentation closeout 30c087c. Local implementation and focused verification passed; both commits are pushed to origin/main.`
**Approved:** 2026-08-10
**Detailed:** 2026-08-10, after inspecting the existing `PurchaseOrder` model, additive schema
initializer, P.O. API routes, register template, access tests, and established Excel export patterns.
**Finished:** 2026-08-10 in implementation commit `3d66caf`, with journal closeout `30c087c`; focused verification passed and the release remains code-only.

### Context

The P.O. Details register currently stores the client, P.O. number, one date, type, and audit
timestamps. The existing date is the P.O. start date, but the page labels it only as P.O. Date and
has no end-date or amount support. The owner requested a complete, usable P.O. register with a
positive optional PHP amount and an Excel export that can be limited by the page's active filters.

The existing `po_date` column is retained as the internal Start Date because existing records and
analytics already depend on it. End Date is additive and nullable so legacy records continue to
load. Contract records created or edited through the new form require an End Date; Single Visit
records may leave it blank.

### Decisions taken

- Store amounts in PHP only.
- Amount is optional for backward compatibility; when supplied it must be greater than zero and
  use at most two decimal places.
- The existing `po_date` column remains the Start Date; new API consumers may use `start_date`,
  while legacy `po_date` payloads remain accepted.
- Contract P.O.s require End Date. Single Visit P.O.s may omit it.
- End Date cannot precede Start Date.
- Export is a formatted Excel workbook containing the currently active filters and all matching
  records, not only a visual subset.
- Existing P.O. permissions and count-only P.O. analytics remain unchanged.
- No database replacement, destructive migration, historical record rewrite, or artifact cleanup is
  part of this work.

### Investigation

- `app.py:1838-1868` defines `PurchaseOrder` with `po_date`, `po_number`, `po_type`, client, and
  audit fields but no amount or end date.
- `app.py:3429-3473` provides `ensure_purchase_order_schema()`, the established additive runtime
  migration boundary for the P.O. table.
- `app.py:39227-39399` contains the serializer, validation, list, add, update, and delete routes;
  these will remain behind `can_manage_purchase_orders()`.
- `templates/po_details.html:230-715` contains the modal, filters, sortable desktop table, mobile
  cards, and client-side export insertion point.
- `tests/test_purchase_orders.py` covers authorization, persistence, validation, duplicate handling,
  and client-delete cascade; its old no-financial-fields assertion must be replaced with amount and
  end-date compatibility coverage.
- Existing Excel generation uses `openpyxl` in `app.py`; the new export will use the same dependency
  and protected-route conventions.

### Execution steps

1. **Record the approved plan and schema boundary.** Update `plans.md` with this status and retain
   the known excluded files. Update the existing 2026-08-10 section in `changes.md` when behavior
   changes are complete. Do not run a database migration against `scheduler.db`.
2. **Extend the P.O. model and additive schema.** In `app.py`, add nullable `end_date` and nullable
   two-decimal PHP `amount` fields to `PurchaseOrder`. Extend `ensure_purchase_order_schema()` to add
   only missing columns and keep existing indexes and client cascade behavior intact. Existing rows
   remain readable with null values.
3. **Extend validation and API serialization.** Update `validate_purchase_order_payload()` to accept
   `start_date` with `po_date` fallback, parse `end_date`, normalize optional amount, require End Date
   for Contract values, reject reversed date ranges and invalid/non-positive/over-precision amounts,
   and allow an explicit blank amount to clear it on update. Update `purchase_order_to_dict()` with
   `start_date`, compatibility `po_date`, `end_date`, exact amount data, and creator metadata without
   breaking existing consumers. Include meaningful old/new date and amount details in update logs.
4. **Add the protected filtered Excel export.** Add `/export_purchase_orders` beside the P.O. routes in
   `app.py`, using the same access guard as `/get_purchase_orders`. Accept the existing client,
   number, type, and Start Date range filters plus a whitelisted sort key/direction. Export Start Date,
   End Date, P.O. ID/Number, Medical Center, complete address, type, amount, created/updated dates,
   and creator. Format headers, dates, PHP currency, widths, freeze panes, autofilter, and a total
   amount row. Log the export without exposing private data in the log.
5. **Update the P.O. Details interface.** In `templates/po_details.html`, rename the modal field to
   Start Date, add the End Date picker, and add optional Amount (PHP). Restore all values in edit mode;
   clear them for new records. Add Start Date, End Date, and Amount columns to desktop/mobile views,
   amount sorting, display formatting, and an Export Excel button that sends the current filters and
   sort state. Keep native validation, duplicate confirmation, filters, saved sorting, dark mode, and
   mobile layout intact.
6. **Add focused regression coverage.** Extend `tests/test_purchase_orders.py` for additive columns,
   Contract/Single Visit date rules, reversed dates, amount validation/clearing, serializer
   compatibility, and existing-record loading. Add export tests that inspect the generated workbook,
   filters, sorting, currency values, total, and authorization. Keep analytics count tests passing
   unchanged and add a template/static assertion only where it protects the new controls.
7. **Update release records and self-review.** Add detailed bullets to the current `changes.md` section
   and a human-readable P.O. register entry to `static/changelog/releases.json`. Confirm no service
   worker bump is needed unless the implementation touches an app-shell asset. Review the diff for
   accidental edits to `scheduler.db`, `output/`, `tmp/`, or handoff artifacts.
8. **Verify and close the plan.** Run focused P.O. tests, Excel workbook inspection, Python compilation,
   JavaScript syntax checks, the relevant regression suite, `git diff --check`, and a final status/diff
   review. Only after all checks pass may the plan status be changed to `Executed` with its commit
   hash; deployment/push remains subject to the owner's explicit release instruction.

### Deliberately excluded

- No currency selector, multi-currency support, or exchange-rate logic.
- No purchase-order amount totals in the existing analytics count panels.
- No automatic backfill of End Date or amount for legacy P.O. records.
- No changes to Products, Calendar, client records, approval routing, or P.O. workflow permissions.
- No replacement, direct edit, staging, commit, or push of `scheduler.db` or generated artifacts.

### Verification bar

- Positive controls must prove existing legacy P.O.s still load, Single Visit records can omit End
  Date, valid Contract ranges save, and export works with and without active filters.
- Negative controls must prove Contract without End Date, reversed ranges, zero/negative amounts,
  malformed amounts, unauthorized routes, and unsupported sort keys are rejected safely.
- Workbook checks must inspect actual cell values and formatting rather than only response status.
- Browser checks must cover Add/Edit, filters, amount sorting, export, modal scrolling, mobile cards,
  and dark mode without page overflow or broken actions.
- The final diff must contain only intentional code, template, test, release-manifest, journal, and
  plan changes.

### Risks and safeguards

- Legacy rows may have no End Date or amount; nullable columns and compatibility serialization prevent
  load failures.
- Decimal conversion can lose cents if serialized as binary floats; preserve a normalized decimal
  representation for JSON and use numeric cells only in the workbook.
- Export filters could drift from the page filters; share one parameter contract and test a filtered
  subset against the rendered register.
- A client delete must continue cascading P.O. records; retain and run the existing cascade test.

### After implementation

- Re-read the completed plan against the diff and amend this entry if implementation differs.
- Keep the current dated `changes.md` section newest and detailed; do not log secrets or database
  contents.
- Validate the release manifest, run the focused and regression tests, and record exact results.
- Stage only intentional source/template/test/journal/manifest files if the owner later authorizes a
  commit. Never stage `scheduler.db`, `output/`, `tmp/`, or handoff artifacts.
- Push or deploy only after a separate owner instruction.

## System Backup rework: build first, then download

**Status:** `Executed — b4b17fc. Implementation and verification are complete; push follows the journal status commit.`
**Approved:** 2026-08-09
**Detailed:** 2026-08-09, after mapping the backup end to end and confirming three load-bearing facts
by running them rather than reading them.

> **Process note, recorded because it matters more than the code.** Execution began immediately on
> plan approval. **That was wrong.** This repository's rule is that approving a plan is *not*
> permission to execute (`AGENTS.md`, "Approved Plans"); a separate go-ahead is required, and the
> owner stopped the work to say so. The plan-approval step was misread as that go-ahead. Nothing was
> committed or pushed, so the only cost is that this handoff exists.

### Implementation status — READ FIRST

The implementation is complete in commit `b4b17fc`. The release scope contains only the planned code,
template, test, release-manifest, and journal changes; `scheduler.db`, `output/`, `tmp/`, and the
existing handoff artifact remain outside the release scope.

**Done and verified by running it, not by reading it:**

| Step | What landed | Evidence |
| --- | --- | --- |
| 1 | `RUNTIME_STATE_DIR`, `BACKUP_ARCHIVE_DIR`, `PROCESS_BOOT_ID`, `ensure_runtime_state_dirs()`; `bucket_migration_state_path()` is now a pure join | dirs created at import; confirmed no I/O in the path helper |
| 2 | `safe_zip_writestr()`; all six bare `writestr` sites routed through it; optional `progress=` on `add_path_to_backup_zip()` | existing `tests/test_system_backup.py` still green (8/8) |
| 3 | `create_sqlite_snapshot()` + `sha256_of_file()` | **all three paths exercised**: clean snapshot (`quick_check: ok`, 500/500 rows), non-SQLite input → `raw_copy_fallback` with the error recorded, missing file → `FileNotFoundError` |
| 4 | Bucket phase: `progress`/`budget_seconds`/`cancel`, skipped-key enumeration, 64 MB cap, `zip.open(...,'w')` streaming write, `BACKUP_BUCKET_BACKGROUND_BUDGET_SECONDS = 900` | compiles; existing budget test still passes unchanged |
| 5 | `FileStorageBackend._client_lock` guarding `client()` and `_backup_client_for()` | **`threading` was missing from `storage_backend.py` imports** — it compiled anyway because the reference is inside a method body, and would have failed at runtime. Import added |
| 6 | Job state layer + `reconcile_backup_job_state()` | a `running` job with a foreign `boot_id` reconciles to `failed` |
| 7 | `sweep_backup_artifacts()` + throttled variant, `current_backup_archive()` | **the critical safety property is proven**: a decoy `<tmp>/medical_service_backup_deadbeef.db` survives a sweep |
| 8 | `estimate_backup_source_bytes()`, `backup_preflight_report()` | real run reports 47.20 MB estimated / 307.92 MB required; with `disk_usage` patched to 1 KB it refuses with the numbers in the message |
| 9-11 | `build_system_backup_archive()`, `BackupCancelled`, `run_system_backup_job()`, `backup_status_payload()`, routes `/admin/backup`, `/admin/backup/status|start|cancel|delete`, and `download_system_backup()` rewritten to serve the stored file | Focused route/build tests exercise archive generation, HTML error paths, repeated downloads, Range responses, and job state |

**Verification outcome:** `build_system_backup_archive()` has produced clean and warning-bearing
archives in tests; the download route has served byte-identical 200 responses and a 206 Range
response; non-superadmin and missing-archive paths render HTML; low-space preflight returns 507
without starting a thread; and stale/reclaim/sweep behavior is covered by focused tests.

**Release plumbing and verification completed:**

| Step | Work |
| --- | --- |
| 12 | Storage health integration — `backup_archive` snapshot, archive counted in `total_used_bytes`, and archive-aware storage details | Complete; covered by `test_storage_health_reports_published_archive_separately` |
| 13 | Service worker — `/admin/backup` network-first and cache version v84 | Complete; source-order and no-cache tests pass |
| 14 | `templates/system_backup.html` + `templates/access_denied.html` + dark-mode-safe styles | Complete; route rendering tests pass |
| 15 | Settings Backup card rewritten as a Backup Center entry point and obsolete source claim removed | Complete |
| 16 | `releases.json`, `changes.md`, and this plan updated | Complete; final commit hash will be recorded after commit |
| — | Focused backup/offline tests | 29 passed; full suite is the final release gate |

**Focused suite state:** 29 tests pass, including the newly added manifest-write degradation case.
The full suite is the remaining release gate and must be run before commit/push; any unrelated
pre-existing failures will be reported rather than hidden.

### Execution outcome

- The missing templates and Settings entry point are now present, so the previous `TemplateNotFound`
  failure paths are covered and the Backup Center is renderable for superadmins.
- Storage Health uses the actual report keys (`used_human`, `remaining_human`, `storage_status`, and
  `storage_status_label`) and separately reports the published backup archive.
- The service worker keeps `/admin/backup` out of the runtime/app-shell cache while preserving the
  existing network-only `/admin/download-backup` behavior.
- `scheduler.db`, generated output, temporary directories, and the existing handoff artifact are
  deliberately excluded from staging and deployment.

### Context

**The production failure.** The owner reported on 2026-08-09 (Brave, production) that the System
Backup download starts, fails with *"Check internet connection"*, and **Resume does not recover it**.

Two things are established by reading the code, not guessed:

1. **Resume can never work today, and the reason is not what it looks like.** Flask 3.1.2 already
   defaults `send_file` to `conditional=True, etag=True` — **verified by inspecting the installed
   signature** — so the route *already* advertises `Accept-Ranges` and would honour a Range request.
   It fails because `@response.call_on_close` **deletes the archive** the moment the response closes,
   including on failure. There is nothing to resume from, and retrying builds a *different* archive.
   **The fix is not a new parameter; it is keeping the file.**
2. **The archive is built entirely before the first byte is sent**, so an idle timeout — Railway's
   edge proxy the prime suspect — closes a connection that looks dead. Production is far larger than
   the 39 MB / 3.6 s measured locally.

**The wider ask** was to rework the feature and page and *"fix all bugs and errors"*. Exploration
found **twelve** further defects. The most serious is not the download at all: **the SQLite database
is copied as a raw file while the app is live**, with no `-wal`/`-shm`/`-journal` sidecars, so a
backup taken during a write can be a subtly corrupt database nobody discovers until they need it.

**Intended outcome.** Start Backup builds in the background with real progress; the finished file is
stored on the persistent volume; downloading starts instantly, resumes if interrupted, and returns
byte-identical content every time. Every backup is a guaranteed-consistent snapshot, and a partial
backup can no longer look identical to a complete one.

### Decisions taken

| Decision | Value |
| --- | --- |
| Shape | **Build first, then download.** Background build, polled progress, download a finished file |
| Restore | **Not in this work.** Fix the snapshot; restore is deferred as its own design |
| Storage | **Railway volume, keep only the latest**, expiring after ~24h |
| Scheduling | **Manual only.** No scheduler is added |

All four were the owner's choice from an explicit set of alternatives.

### Investigation

- `send_file` defaults to `conditional=True`/`etag=True` in Flask 3.1.2 — **Range/Resume is free once
  the file persists.** No streaming rework is needed to fix the reported bug.
- **No background job infrastructure exists** — no celery/rq/APScheduler/redis. The only precedent is
  `threading.Thread(daemon=True)` fire-and-forget email senders (`app.py:6113` and ~14 others).
  `Procfile` is one worker, 8 threads, so **job state must live on disk** or a restart loses it.
- **The atomic state-file pattern already exists**: `load_bucket_migration_state()` /
  `save_bucket_migration_state()` (`app.py:18046`, `18056`), temp file + `os.replace`.
- **The polling UI pattern already exists**: `loadBucketMigrationStatus()` / `runBucketOperation()`
  (`templates/settings.html:1664`, `1690`), `.bucket-progress` / `#bucket-progress-fill` (CSS `:3649`).
- `sqlite3.Connection.backup()` is available (local SQLite 3.50; Python 3.11.9 bundles 3.37+).
- `storage_backend.py` has **no presigned URLs, no range reads, no multipart** — every bucket object
  is read whole into memory, which bounds what the bucket phase can do.
- **A sweeper must not glob `medical_service_backup_*`**: `tests/test_system_backup.py:15` puts the
  **test database** at `<tmp>/medical_service_backup_<hex>.db`.

### The twelve defects and where each is fixed

| # | Defect | Fixed in step |
| --- | --- | --- |
| 1 | **Raw copy of a live SQLite DB**, no sidecars — can be torn | 3 |
| 2 | Resume impossible (file deleted on close) | 11 |
| 3 | Orphaned temp files if the process is killed | 7 |
| 4 | **Missing DB yields `backup_complete: true`** | 3, 9, 14 |
| 5 | Bucket budget silently truncates | 4 |
| 6 | Unbounded memory per bucket object | 4 |
| 7 | Unguarded `writestr` discards a built archive | 2 |
| 8 | `os.makedirs` inside the request can abort a build | 1 |
| 9 | UI claims the archive contains "application source" | 15 |
| 10 | Warnings never surfaced — partial looks complete | 14 |
| 11 | Shared boto3 client mutated across 8 threads | 5 |
| 12 | 403 returns raw JSON to a browser navigation | 11 |

### Architecture

`/admin/download-backup` **keeps its exact path and function name**, deliberately: it preserves the
`NETWORK_ONLY_DOWNLOAD_PREFIXES` match (`app.py:15270`) and three passing service worker tests. A new
download URL would silently re-enable the caching leak those tests guard.

| Route | Method | Gate | Notes |
| --- | --- | --- | --- |
| `/admin/backup` | GET | superadmin → **HTML** 403 | new Backup Center page |
| `/admin/backup/start` | POST | superadmin + CSRF | 202 / 409 running / 507 no space |
| `/admin/backup/status` | GET | superadmin | polled |
| `/admin/backup/cancel` | POST | superadmin + CSRF | cooperative cancel |
| `/admin/backup/delete` | POST | superadmin + CSRF | frees volume space |
| `/admin/download-backup` | GET | superadmin → **HTML** 403 | **unchanged path**, serves a stored file |

**Job state** at `RUNTIME_STATE_DIR/_system_backup_job.json`, written atomically under a module lock.
**Crash handling:** `PROCESS_BOOT_ID` regenerates at import; `reconcile_backup_job_state()` marks a
`running` job failed when its `boot_id` differs (the process died — a Railway redeploy mid-build) or
when `updated_at` is over 5 minutes old. `boot_id` rather than `pid`, because pids get reused.
Because state is on disk, reloading the page re-attaches to a running job.

### Execution steps

1. **Runtime state dirs** — `RUNTIME_STATE_DIR`, `BACKUP_ARCHIVE_DIR`, `PROCESS_BOOT_ID` created once
   at import, guarded. `bucket_migration_state_path()` becomes a pure join. *Done:* the path helper
   does nothing with `os.makedirs` patched to raise.
2. **`safe_zip_writestr()` + progress hook** — all six `writestr` sites routed through it; optional
   `progress=None` on `add_path_to_backup_zip()` so existing callers are unaffected.
3. **`create_sqlite_snapshot()`** — `Connection.backup()` single-step, `PRAGMA quick_check`, sha256.
   **Chosen over `VACUUM INTO`**: page-level copy through SQLite's own locking, correct in both
   journal modes, folds WAL state into one self-contained file, far faster; `VACUUM INTO` rebuilds
   every index and its compaction is worthless once deflated. Missing/unreadable DB **fails the job**;
   a `DatabaseError` falls back to raw copy *plus sidecars* and records the method — never silently.
4. **Bucket phase** — optional `progress`/`budget_seconds`/`cancel`; `budget_seconds=None` resolves
   the module constant **at call time** so the existing patch-based test still works;
   `BACKUP_BUCKET_BACKGROUND_BUDGET_SECONDS = 900`; 64 MB per-object cap checked *before* download;
   streaming `zip.open(...,'w')`; skipped keys enumerated into `bucket_objects_skipped.json`.
5. **`storage_backend.py` client lock** on `client()` and `_backup_client_for()`.
6. **Job state layer** + `reconcile_backup_job_state()`.
7. **`sweep_backup_artifacts()`** — strict regex allowlist confined to `BACKUP_ARCHIVE_DIR`, plus a
   **`.zip`-only** rule for legacy temp orphans. **Must never match `medical_service_backup_*.db`.**
8. **`backup_preflight_report()`** — stat-only estimate vs `shutil.disk_usage().free`, ~10% + 256 MB
   headroom, refuse above 90% volume usage. **Keep the previous archive unless preflight proves both
   do not fit** — always deleting first leaves zero backups when a build fails.
9. **`build_system_backup_archive()` + `run_system_backup_job()`** — builds into `.build-<id>/` and
   `.building-<id>.zip`, published by `os.replace` so a partial archive is never downloadable.
   `compresslevel=1` and periodic yields: uploads are PDFs/JPEGs that barely compress, so this costs
   almost no size and removes most GIL pressure on the other seven threads.
10. **Routes** start/status/cancel/delete.
11. **Rewrite `download_system_backup()`** to serve the stored file; keep `send_file`'s default
    `conditional=True`. `X-Backup-*` headers read from job state. Non-superadmin and missing archive
    both return **HTML**. **Rewrite the docstring** — a test asserts on it.
12. **Storage health** — add a `backup_archive` snapshot and **count it in `total_used_bytes`**; today
    the gauge counts only DB + uploads, so a stored archive is invisible to its own 75%/90% warnings.
13. **Service worker** — `/admin/backup` network-first; bump `CACHE_VERSION` to **v84**, read live.
14. **`templates/system_backup.html`** — status badge, storage meter, actions, progress, and a result
    panel surfacing warnings, an explicit **Database included: Yes/No** row, and a red banner when
    `backup_complete` is false.
15. **Rewrite the settings Backup card** as an entry point; **delete the "application source" claim**.
16. **Release plumbing** — `releases.json`, `changes.md`, this plan to `Executed`.

### Deliberately excluded

**Restore**, by the owner's decision — and the UI must not imply it exists. **Streaming the ZIP**,
which this design makes unnecessary: the archive already exists when the download starts, so the
first byte is immediate *and* `Content-Length` is known. **Any scheduler.** **A new download URL**,
which would drop out of the service worker's network-only list. **Changing the `Procfile`**, now more
load-bearing not less: `--workers 1` guarantees a single builder, `--threads 8` gives the build thread
somewhere to run.

### Verification

**Tests that will break, and what happens to each — none may simply be deleted:**

| Test | Action |
| --- | --- |
| `test_system_backup.py:95` `X-Backup-Complete == 'false'` | **Keep the assertion, move the setup.** The header survives — it is now read from job state |
| `test_system_backup.py:97-102` pins `database/<basename>` | Behaviour unchanged; the fixture must become a **real SQLite file** or it exercises the raw-copy fallback |
| `test_system_backup.py:113-144` patches budget constants | Passes unchanged (`budget_seconds=None` resolves at call time); add an override assertion |
| `test_system_backup.py:147-193` SW source tests | Untouched; add a new test that `/admin/backup` is network-first |
| `test_offline_api_status.py:112-121` streaming-decision record | **Rewrite, do not delete.** It exists to keep the trade-off beside the code, and that intent survives the reversal |
| `test_offline_api_status.py:78-111` Procfile pins | Do not touch the Procfile |
| Cache version | `assert_cache_version_at_least(self, 84, source)` — a floor, never a literal |

**New tests**, each with the positive control that proves it can fail: the snapshot is a consistent
self-contained DB; a missing DB **fails the job**; a second start returns 409; a foreign `boot_id`
reconciles to failed; preflight returns 507 and **starts no thread**; the download returns 206 with
`Content-Range`; **two downloads return byte-identical archives** (the direct regression); missing
archive and non-superadmin return HTML; **the sweeper never deletes the test database**; only the
latest archive is kept; budget exhaustion enumerates skipped objects; a manifest write failure is a
warning rather than a lost archive.

**End to end, which is what matters here:** start a backup from the page and watch progress; reload
mid-build and confirm it re-attaches; download and confirm `testzip()` is clean; **interrupt the
download and resume it**, then confirm the result is byte-identical to a single-pass download; delete
the archive and confirm the volume meter moves. Then the full suite (currently 582) and
`git diff --check`.

### Risks

| Risk | Blast radius | Mitigation |
| --- | --- | --- |
| **A build thread inside the single web worker** | Every other request slows while deflate holds the GIL; at worst one exceeds the 180 s timeout | `compresslevel=1`, periodic yields, one short DB-lock window, budget-bounded bucket phase. Accepted: the alternative is job infrastructure this deploy does not have |
| **Railway redeploy mid-build** | Wasted build, leaked disk, state stuck on `running` | `boot_id` reconcile marks it failed honestly; startup sweeper clears the workdir. **The previous archive is untouched** — publish is atomic and the old file is deleted only after success |
| **Filling the 5 GB volume** | Worse than a failed backup — uploads fail for everyone and SQLite writes can fail | Preflight free-space check, keep-only-latest, 24 h lazy expiry, manual delete, refusal above 90%, and storage health now *counts* the archive |
| A huge bucket object | OOM on the single worker | 64 MB cap before download; skipped with a warning — the right failure |
| SQLite lock contention during the snapshot | Writers block briefly | Page copy is fast; the 60 s busy timeout absorbs it. **Do not switch to incremental backup** — it restarts whenever the source is written, livelocking under steady writes |
| Sweeper deletes the wrong file | Data loss | Strict regex allowlist, `.zip`-only in temp, with a dedicated regression test for the `medical_service_backup_*.db` collision |

### Critical files

`app.py` — backup block (`17762`-`18960`), `get_storage_health_report()` (`18596`), service worker
(`15231`, `15270`, `15591`); `storage_backend.py` (`170`-`196`);
`templates/system_backup.html` (**new**); `templates/settings.html` (`250`-`276`);
`templates/access_denied.html` (**new**); `static/css/app-dark-pages.css`;
`tests/test_system_backup.py`; `tests/test_offline_api_status.py`;
`static/changelog/releases.json`.

## Every LPR page says which page it is, and how many there are

**Status:** `Executed — 29b2b9e`, reviewed in `ca4cacb`
**Approved:** 2026-08-08
**Detailed:** 2026-08-08, after probing `forms/LPR FORM.pdf` geometry directly to confirm the marker
strip is free on page one and clear of the enlarged signatures.

**Executed in `29b2b9e` after the project owner gave the separate go-ahead.**

### Context

`d5e6d60` rebuilt LPR continuation pages on the official template, which means **every page is now a
complete official form carrying the requester's and approver's signatures**. `pending-work.md`
section 2 raised that as a question rather than a defect: on a 3-page LPR the approver's signature
appears three times, and that changes what leaves the building.

The owner's answer, on 2026-08-08: *"i think we can add a page number with the lpr number so that
each page won't come off as an individual page."*

**The real problem this solves is detachment, not tidiness.** Because each page is a complete signed
form, any single page on its own reads as a fully approved requisition. A page left in a printer or
dropped from a stack cannot currently be recognised as a fragment. A page count does not prevent
that, but it makes it **visible**, on a document that authorises spending. That is the reason to do
it, and it is why the total matters more than the page number.

### Decisions taken

| Decision | Value |
| --- | --- |
| Marker on which pages | **Every page, including page one** |
| Format | **`LPR-<no> - ITEMS <a>-<b> - PAGE <n> OF <N>`** |
| The total | **Required.** `PAGE 2` says where you are; `PAGE 2 OF 3` says whether one is missing |
| Single-page LPRs | **`PAGE 1 OF 1`** — the owner took the recommendation |
| Historical PDFs | **Not regenerated.** New renders only — **this line was wrong, see the correction below** |

**The single-page decision was the one real trade and is recorded so it is not silently reversed.**
It changes the appearance of the *most common* LPR, which today carries no marker at all. It was
chosen because the entire value of the scheme is that the marker's absence never has to be
interpreted — if only multi-page LPRs are marked, an unmarked page is ambiguous between "complete
one-pager" and "page torn off a longer document", which is the exact ambiguity being removed.

### Investigation

Verified by probing the template with PyMuPDF, not by reading the generator.

- `lpr_continuation_marker_page()` (`app.py:51896`) draws at `(36, 274)` in ReportLab coordinates,
  8pt Helvetica-Bold, on a 576×360 page. It is called **only** from the continuation loop
  (`app.py:51957`), so **page one has no marker of any kind today** — the page most likely to be
  treated as the whole document is the one with nothing on it.
- **The LPR number is already on every page.** `lpr_form_common_values()` puts it in `Textfield`
  and the continuation loop applies those values to each cloned page. So the owner's "add the LPR
  number" half **already exists**; what is missing is the page position and the total.
- **The marker strip is free on page one.** ReportLab `y=274` is `y≈77..89` from the top. In that
  band the only content is the `Product` label at `x=414.2` and its widget at `x=471.6`, plus a
  drawing box starting at `x=401.2`. From `x=36` the band is clear, sitting in the ~24pt gap between
  the form title (ends `y=73.1`) and the `LPR No.` label (starts `y=97.4`).
- **No signature collision.** `Requested by`, `Approved by` and `Received by` widgets sit at
  `y≈294..322` from the top — far below the marker band — so the `8d97b58` signature enlargement
  cannot reach it.
- **The nearest thing to the right is at `x=401.2`**, which is the width budget the longer string
  must respect. This is the one geometric risk and step 3 measures it rather than eyeballing it.
- `tests/test_lpr_workflow.py:140` asserts the **exact** current string, and `:132` asserts a
  single-page LPR contains **no** `CONTINUATION - ITEMS` text. **Both must change**, and the second
  is the one that would otherwise be quietly deleted — it becomes an assertion about the *new*
  marker instead.
- **No service worker bump is required.** This is server-side PDF generation and `/lpr` is not an
  `APP_SHELL` entry — the same reasoning recorded for `d5e6d60`.

### Execution steps

1. **Generalise the marker helper.** In `app.py`, rename `lpr_continuation_marker_page()` to
   `lpr_page_marker_page()` and give it `(lpr_no, item_start, item_end, page_number, page_total,
   PdfReader)`. It renders `f'{lpr_no} - ITEMS {a}-{b} - PAGE {n} OF {N}'`. Keep the position,
   font, size and colour exactly as they are — they are already proven on continuation pages.
   *Done when* no caller passes a hardcoded `CONTINUATION` string.
2. **Compute the page total before rendering any page.** In `lpr_fill_pdf_bytes()`
   (`app.py:51916`), derive `page_total = max(1, (len(items) + 7) // 8)` **before** the first page is
   written, and merge a marker onto page one with `(1, min(8, len(items)), 1, page_total)`. Then
   pass the same `page_total` into the continuation loop. *Done when* a 1, 8, 9, 16 and 17-item LPR
   each carry a marker on every page whose `OF N` equals the real page count.
3. **Measure the string, do not assume it fits.** Use `reportlab.pdfbase.pdfmetrics.stringWidth(text,
   'Helvetica-Bold', 8)` and assert `36 + width < 401` — the left edge of the template's right-hand
   box. If a long LPR number ever breaches it, drop the `ITEMS <a>-<b>` segment rather than shrinking
   the font, because the page total is the load-bearing part and small print defeats the purpose.
   *Done when* the check exists in code, not only in a test.
4. **Update the two existing assertions honestly** in `tests/test_lpr_workflow.py`. `:140` becomes
   the new format. `:132` **inverts**: a single-page LPR must now contain `PAGE 1 OF 1`. Record in
   each docstring that the old assertion was replaced because the marker scheme changed, not
   because it was failing.
5. **Release plumbing.** `releases.json` entry dated the commit date, in the LPR category, describing
   it as pages now being identifiable as part of one requisition. **No service worker bump** — state
   that reasoning in `changes.md` so the omission reads as a decision.

### Deliberately excluded

- **Regenerating historical or already-submitted LPR PDFs.** They are records of what was issued.
  **Corrected after implementation: this exclusion was meaningless as written.** No LPR PDF is
  stored anywhere — all eight call sites build it on demand — so there was nothing to regenerate,
  and the practical effect is that **every existing LPR now carries the marker when re-downloaded**.
  Already-sent procurement emails hold frozen attachments and are unaffected. Left as-is on review:
  the change is additive and applying the page-count protection to older requisitions is arguably
  better. **The lesson for the next plan: check whether an artifact is stored or regenerated before
  writing an exclusion that assumes it is stored.**
- **Any change to the signature scheme itself.** The owner chose page numbering *instead of* removing
  the repeated signatures; this plan does not quietly do both.
- **Changing the marker's position, font or colour**, which are proven on continuation pages.
- **A "page 1 of 1" suppression option.** One behaviour, no configuration.
- **Any watermark, "COPY" marking, or per-page unique identifier.** A larger anti-detachment scheme
  is a different decision; this is the cheap 90%.

### Verification

Additions to `tests/test_lpr_workflow.py`, each with the positive control that proves it can fail:

| Assertion | Positive control |
| --- | --- |
| Page one of a 17-item LPR carries `PAGE 1 OF 3` | page two carries `PAGE 2 OF 3`, so a constant is not passing |
| A 1-item LPR carries `PAGE 1 OF 1` | the 9-item case carries `OF 2`, so the total is computed not hardcoded |
| `OF N` equals the real page count for 1, 8, 9, 16, 17 items | the 8 vs 9 boundary, where N changes from 1 to 2 |
| The LPR number appears in the marker text itself | a page whose `Textfield` differs still shows its own number |
| Marker width stays left of `x=401` | a deliberately long LPR number is measured, not assumed |
| No page has `CONTINUATION - ITEMS` any more | every page still has the official header text |

Prove each new test fails without its fix, **one at a time**, confirming by SHA that the injection
applied and that the failure message is the expected one. **`app.py` is CRLF** — a `\n` needle
silently matches nothing and reads exactly like a vacuous test.

**Then render and look at it, which is the part that actually matters here.** Generate a 1-page, a
2-page and a 3-page LPR against a throwaway database with a seeded signature, and confirm on the
**rendered** pages that the marker is legible, does not touch the form title above or the `LPR No.`
label below, does not run into the right-hand box, and does not collide with the enlarged
signatures. Then the full suite (580 tests, 1 pre-existing skipped test) and `git diff --check`.

### After implementation

Self-review the diff; `releases.json` dated the commit date; **no service worker bump, stated as a
decision**; `changes.md`; this plan to `Executed` with its hash; `pending-work.md` only if the owner
asks — the section 2 entry asking this question can then be closed. Commit per the standing
checklist, staging file by file, never `scheduler.db`.

### Risks

| Risk | Blast radius | Mitigation |
| --- | --- | --- |
| **Every LPR's appearance changes**, including the common single-page one | Every requisition issued from now on looks different from every one already filed | Deliberate and owner-approved; the marker is small, monochrome, and in dead space. Reversible by not drawing it on page one |
| A long LPR number pushes the text into the right-hand box | An official form with overlapping print | Step 3 measures the string in code, with a test using a deliberately long number |
| The two rewritten tests lose what they were guarding | A real continuation regression ships unnoticed | Neither is deleted: `:140` changes format, `:132` inverts to assert the new marker. Both keep the item-placement assertions around them |
| `OF N` computed after pages are built and coming out wrong on page one | A form that states its own page count incorrectly — worse than no count | Step 2 derives the total **before** any page is written; tests cross-check the 8/9 boundary |
| Someone later reverts single-page marking as clutter | The ambiguity this exists to remove comes back | The reasoning is in Decisions, not just in a commit message |

### Critical files

`app.py` — `lpr_continuation_marker_page()` → `lpr_page_marker_page()` (`51896`), `lpr_fill_pdf_bytes()`
(`51916`), reference `lpr_form_common_values()` for the LPR number source;
`tests/test_lpr_workflow.py` (`132`, `140`); `static/changelog/releases.json`; `changes.md`.
The official source `forms/LPR FORM.pdf` is **not** modified.

## LPR continuation pages use the official template

**Status:** `Executed — d5e6d60`
**Approved:** 2026-08-07
**Started:** 2026-08-07, after the project owner explicitly instructed execution.
**Detailed:** 2026-08-07, after inspecting the supplied two-page LPR PDF and tracing the overflow branch in `app.py`.
**Finished:** 2026-08-07 in implementation commit `d5e6d60`; the documentation follow-up records
the completed outcome and verification state.

### Context

The first LPR page is filled from `forms/LPR FORM.pdf`, but `lpr_fill_pdf_bytes()` currently draws overflow pages with a custom ReportLab table. The supplied `LPR-20260807-01.pdf` demonstrates the resulting mismatch: page one uses the official geometry while page two has different branding, spacing, labels, and a separate continuation total. The continuation page must remain the same official LPR form while carrying the next item rows.

### Decisions taken

- Keep the official template unchanged for page one and for every continuation page.
- Use eight item rows per page: items 1-8, 9-16, 17-24, and so on.
- Repeat Branch, Class, Department, Product, LPR number, date, Intended For, Equipment, PO No., Invoice No., Requested By, Approved By, Received By, and the selected requester/approver signatures on each continuation page.
- Add only a small vector continuation marker above the official item table; do not add a custom continuation total.
- Flatten continuation form fields so duplicate AcroForm names cannot bleed values between pages.
- Preserve existing first-page behavior for LPRs with eight or fewer items and leave historical submitted/archived PDFs unchanged.
- Regenerate the supplied unsubmitted example locally into a temporary corrected file without overwriting the Desktop source.

### Investigation

- `app.py:51533` currently fills the first eight official fields, then creates a custom ReportLab continuation page with twelve rows at `app.py:51615-51654`.
- `forms/LPR FORM.pdf` is a single 576 x 360 page with eight official item-row field groups and the complete request/signature layout.
- Existing helpers `lpr_form_field_rects()` and `lpr_signature_box()` already provide the geometry needed to repeat signature overlays on cloned pages.
- `tests/test_lpr_workflow.py` currently expects the old `LOCAL PURCHASE REQUISITION - CONTINUED` text and only verifies a nine-item two-page case; it must be updated to the official-template behavior.

### Execution steps

1. **Refactor the LPR PDF generator** — edit `app.py` near `lpr_fill_pdf_bytes()` and its signature helpers. Add shared helpers for the eight official field groups, common header/context values, item-slot values including blanks, signature overlays, and the vector continuation marker. Keep the first-page values and overlay behavior equivalent. For each overflow chunk, clone a fresh official template, fill at most eight items, repeat all shared fields/signatures, flatten the continuation page fields, add the marker, and append it to the output. Done means no custom twelve-row continuation table or continuation total remains.
2. **Add regression coverage** — edit `tests/test_lpr_workflow.py`. Verify page counts for 1, 8, 9, 16, and 17 items; every page is 576 x 360; continuation pages contain official static labels and the marker; item 9 starts page two, item 16 is the eighth row, item 17 starts page three, unused rows are blank, and continuation shared fields are present without cross-page field bleed. Done means the old custom continuation assertion is removed and tests prove the new page contract.
3. **Regenerate and inspect the local sample** — use the supplied unsubmitted LPR values to produce a corrected temporary PDF under `C:\Users\jonamar\AppData\Local\Temp`, render every page with PyMuPDF, inspect page one and continuation pages at normal and enlarged scale, and confirm the Desktop source is unchanged. Done means the sample visibly uses the same official template geometry on both pages.
4. **Update release records** — append a detailed entry to the current `changes.md` date section and add a structured 2026-08-07 LPR continuation item to `static/changelog/releases.json`. No database migration or service-worker bump is required because this is a server-side PDF generator change and `/lpr` is not an application-shell page.
5. **Self-review and verification** — run focused LPR tests, Python compilation, inline LPR JavaScript syntax, JSON parsing, PDF extraction/render checks, the full test suite, and `git diff --check`. Review the diff for unchanged first-page behavior, field isolation, signature repeat behavior, and excluded files. Done means all required checks pass and only intended code/tests/journals/manifest files are staged.
6. **Release** — commit the verified code-only change and push the current branch. Never stage, commit, push, replace, or upload `scheduler.db`, `output/`, `tmp/`, or handoff artifacts.

### Deliberately excluded

- Historical saved/submitted LPR PDF repair is excluded; only the supplied unsubmitted sample is regenerated locally.
- No database schema, record, storage, filename, approval, email, or frontend workflow changes are included.
- No service-worker bump is included because the affected generator is server-side and the LPR page is not in the app shell.
- The official `forms/LPR FORM.pdf` file is not modified.

### Verification

- Focused `tests/test_lpr_workflow.py` coverage for 1, 8, 9, 16, and 17 items, shared values, markers, blank rows, page sizes, and no old custom continuation text.
- Render the corrected local sample and inspect page geometry, branding, fields, signatures, selectable text, page count, and item placement.
- Run Python compilation, LPR inline JavaScript parsing, manifest parsing, full regression tests, and `git diff --check`.
- Confirm first-page output has no continuation marker for eight or fewer items and existing PDF consumers still receive the same byte stream shape for one-page LPRs.

### After implementation

Self-review completed against `app.py`, `tests/test_lpr_workflow.py`, `changes.md`, `plans.md`, and
`static/changelog/releases.json`. The supplied unsubmitted LPR was regenerated locally at
`C:\Users\jonamar\AppData\Local\Temp\LPR-20260807-01-corrected.pdf` without changing the
Desktop source. Focused LPR tests, Python compilation, inline JavaScript parsing, manifest parsing,
PDF extraction/render checks, synthetic repeated-signature checks, the full suite (**544 passed,
1 skipped**), and `git diff --check` passed. The implementation commit is `d5e6d60`; only the
intended code, test, journal, and release-manifest files were staged. The database, generated
output, temporary files, and handoff artifact were excluded.

### Risks

- Duplicate AcroForm names can cause field values to bleed between pages; fresh template readers, continuation flattening, and page-level extraction checks mitigate this.
- The official template has tight signature fields; the existing signature-box helpers are reused rather than introducing new geometry.
- A malformed template or unsupported PDF library behavior could make continuation generation fail; focused tests and visual rendering catch this before release.

### Critical files

`app.py` (`lpr_fill_pdf_bytes()` and shared LPR PDF helpers), `tests/test_lpr_workflow.py`, `changes.md`, `plans.md`, and `static/changelog/releases.json`. The official source remains `forms/LPR FORM.pdf`.

## Stop TSR drafts disappearing when the browser clears site data

**Status:** `Executed — f792d22`
**Approved:** 2026-08-07
**Detailed:** 2026-08-07, after tracing where a TSR draft is actually stored and comparing it with
every sibling module's draft handling.
**Finished:** 2026-08-07 in implementation commit `f792d22`; this documentation update records the
completed outcome and verification state.

Execution authorized by the project owner on 2026-08-07. The implementation is proceeding locally
with the existing database file and generated artifacts excluded from all changes.

### Context

Reported by the owner as live data loss on **Microsoft Edge** (Chrome unaffected): a user created a
TSR online, pressed **Save Draft**, shut the laptop down, reopened a bookmarked `/timeline`, was
logged out, signed in again — and the draft was gone.

**What the investigation found, and it reframes the problem:**

1. **A TSR draft never leaves the device.** IndexedDB `medical_service_offline_tsr_db`, store
   `tsr_drafts` (`offline_tsr.html:2752-2759`), with a localStorage fallback
   (`medicalServiceStandaloneTSRDraftV1`, `:503`). The UI already says so — *"Draft saved on this
   device."*
2. **TSR is the only module without a server-side draft.** `/save_reimbursement_draft`
   (`app.py:24008`), `/save_travel_request_draft` (`:26936`) and both liquidation drafts all persist
   server-side. TSR is the outlier.
3. **`navigator.storage.persist()` is never called** — only `estimate()`
   (`offline_tsr.html:4140`). Without it the origin's storage is *best-effort* and the browser may
   evict it. That is the one concrete lever we have; the rest is Edge configuration we cannot see.
4. **Our own code is not the culprit** — every `clearStandaloneTSRDraftLocally()` call is a user
   action or a successful submit, and the `v77` logout purge touches Cache Storage only, never
   IndexedDB.

Honest diagnosis: **the draft was only ever on that laptop, in storage the browser was entitled to
discard.** Whether it was "clear browsing data on close", Storage Sense or eviction is not knowable
from here, and the fix must not depend on knowing.

### Decisions taken

| Decision | Value |
| --- | --- |
| Approach | **Server-backed drafts *and* `navigator.storage.persist()`** |
| What syncs | **Typed fields and the signature.** Photos stay on the device |
| When | **Explicit Save Draft syncs immediately**; autosave debounced (~15s idle) |
| Scoping | Per user. A draft is never visible to another account |
| Conflict | **Last writer wins** on the device's `updated_at` |

### Execution steps

1. **Model and migration.** `TsrDraft` beside `OnlineTsrSubmission` (`app.py:2537`), whose
   `payload_json` Text column is the pattern to copy: `user_id` (FK, indexed), `draft_key` (the
   client's IndexedDB draft id, so the two sides correspond), the list fields the panel already
   shows mirroring `buildOfflineTSRDraftRecord()` (`offline_tsr.html:3056`) — `schedule_id`,
   `tsr_number`, `client_name`, `service_date`, `title`, `subtitle` — plus `payload_json`,
   `attachment_count`, `device_updated_at`, `created_at`, `updated_at`. Unique on
   `(user_id, draft_key)`. Add `ensure_tsr_draft_schema()` with a `_tsr_draft_schema_ready` global
   following `ensure_online_tsr_submission_table()` (`app.py:2596`), swallowing and logging on
   failure so a migration problem cannot take down login; register it in `initialize_database()`
   and the `before_request` hook.
2. **Three endpoints**, all `@login_required`, CSRF via the existing `getCSRFToken()` header:
   `POST /save_tsr_draft` upserts by `(current_user.id, draft_key)`, rejects an oversized payload,
   and ignores a write whose `device_updated_at` is older than the stored one;
   `GET /get_tsr_drafts` returns this user's drafts only, filtered on `current_user.id` and never
   on a parameter; `POST /delete_tsr_draft` deletes by `draft_key` scoped to the current user, 404
   for anyone else's.
3. **Ask for persistent storage.** Call `navigator.storage.persist()` once on load (guarded), store
   the result in the existing `tsr_metadata` store beside the health record, and **show it in the
   storage health panel**. This doubles as the diagnostic — the next report can say whether the
   browser had granted persistence.
4. **Sync the draft.** A successful local write in `saveStandaloneTSRDraftLocally()`
   (`offline_tsr.html:3078`) schedules a server sync; explicit Save Draft flushes immediately,
   autosave debounces. **Local write first, network strictly after** — a sync failure must never
   block a field save. Strip attachments with the **existing**
   `projectOfflineTSRPayloadForLocalStorage()` (`:2584`), recording `attachment_count` so a restored
   draft can say the photos stayed on the original device. Delete the server copy wherever
   `clearStandaloneTSRDraftLocally()` runs after a submit or explicit delete.
5. **Restore after sign-in.** `renderStandaloneTSRDraftPanel()` merges `GET /get_tsr_drafts` into
   the local list keyed on `draft_key`; a server draft with no local record renders as recovered,
   with an Open action that writes it back into IndexedDB. Reuse the existing
   `awaitingScheduleRepick` path (`:2014`) when a restored draft's schedule no longer matches.
6. **Release plumbing.** `releases.json` dated the commit date; **service worker bump** —
   `templates/offline_tsr.html` is an `APP_SHELL` entry.

### Deliberately excluded

**Uploading draft photos** — multi-megabyte uploads on a field connection for drafts usually
submitted minutes later; the recovered draft names them instead. **Any change to the offline TSR
queue**, which is submitted work with its own durable path. **Clearing IndexedDB on logout**, the
opposite of this fix. **Guessing which Edge setting is responsible** — the fix must hold whichever
it is.

### Verification

New `tests/test_tsr_draft_sync.py`, each with the positive control that proves it can fail:

| Assertion | Positive control |
| --- | --- |
| Save then fetch returns the draft for its owner | a second account's fetch returns **none of it** |
| Delete is scoped to the owner | the owner's delete returns 200; another account's 404s and the row survives |
| Re-saving the same `draft_key` updates rather than duplicates | a different `draft_key` creates a second row |
| An older `device_updated_at` does not overwrite a newer draft | a newer one does |
| The stored payload carries no attachment blob | it does carry the typed fields and signature |
| Anonymous requests refused on all three routes | the logged-in case succeeds |
| Cache floor ≥ 80 | — |

**End-to-end, reproducing the actual report** on a throwaway database: write a draft, confirm it
reached the server, then **delete the site's IndexedDB and localStorage in the browser** — which is
what Edge did, without needing Edge — sign out, sign in, and confirm the draft is offered and opens
with its fields and signature intact and its photos named as left behind. Repeat **offline**: the
local save must still work with the sync failing silently. Confirm `navigator.storage.persisted()`
reports true afterwards and that the health panel shows it.

### After implementation

Self-review completed against `app.py`, `templates/offline_tsr.html`,
`tests/test_tsr_draft_sync.py`, `static/changelog/releases.json`, and `changes.md`. The server now
stores an owner-scoped typed TSR draft snapshot with stale-device protection; the browser still
writes IndexedDB/localStorage first, then performs immediate Save Draft synchronization or a
debounced autosave synchronization. Signatures remain in the account snapshot, while supporting
file blobs remain on the originating device and are identified for re-selection after recovery.
Explicit deletion removes the account copy when online and queues the deletion when offline. The
storage persistence request and health indicator are also present.

The service worker was bumped to `v80-tsr-server-drafts`, and the release manifest and detailed
change journal were updated. Focused draft tests, TSR sync/layout tests, and the complete project
suite passed: **544 tests passed, 1 skipped**. `app.py` and the new test module compile, the
`offline_tsr.html` inline JavaScript parses, `releases.json` is valid JSON, and `git diff --check`
is clean. The implementation commit is `f792d22`; this plan status records that hash. No
database, generated output, temporary files, or handoff artifact was staged.

### Risks

| Risk | Blast radius | Mitigation |
| --- | --- | --- |
| **A draft leaking to another account** | Confidential service content | Every route filters on `current_user.id`; the cross-account tests are the point, not a formality |
| Sync failure blocking a field save | Lost work — worse than the bug being fixed | Local write first, network strictly after, failure a no-op retried next save |
| Signature data URLs make payloads large | Slow syncs, bloated rows | Attachments stripped, server-side size cap, debounced autosave |
| Last-writer-wins across two devices | The older device's edits lost | Bounded by `device_updated_at`; drafts are single-author. State it in the changelog rather than engineering a merge |
| Restored draft whose schedule is gone | Confusing empty picker | Reuse `awaitingScheduleRepick`, which already handles it |
| Forgotten worker bump | Devices keep the old page and never sync | The cache floor assertion |

### Critical files

`app.py` — `TsrDraft` (`2537`), `ensure_tsr_draft_schema()` (`2596`), three routes, worker
`CACHE_VERSION`; `templates/offline_tsr.html` — persist request, sync in
`saveStandaloneTSRDraftLocally` (`3078`), payload projection (`2584`), draft panel merge
(`renderStandaloneTSRDraftPanel`); `tests/test_tsr_draft_sync.py` (**new**);
`static/changelog/releases.json`. Reference while implementing: `/save_reimbursement_draft`
(`app.py:24008`).

## Enlarge every stamped signature by about 50%

**Status:** `Executed — 8d97b58`
**Approved:** 2026-08-07
**Started:** 2026-08-07, after the project owner explicitly instructed execution.
**Finished:** 2026-08-07 in commit `8d97b58`, after focused form-generation smoke checks and the full
regression suite passed (531 tests, 1 skipped).
**Detailed:** 2026-08-07, after mapping every place a saved signature is stamped into a generated
document — eight PDF sites, two Excel sheets and the client-side TSR canvas.

### Context

Stamped signatures come out small on the generated forms. Every document carrying a saved signature
— the requester/user's and the approver's — stamps it into a box tuned one form at a time, mostly to
*avoid* colliding with neighbouring rows. The result is consistent only in being cramped: the Cash
Advance approver box is 13 pt tall, the LPR boxes derive from a form row barely 14 pt high, and two
sites additionally refuse to scale a signature above its natural pixel size at all.

Intended outcome: a signature that reads as a signature on a printed form, at a size consistent
across every document, and tunable from one number afterwards.

### Decisions taken

| Decision | Value |
| --- | --- |
| Scope | Approval forms **+** both Excel sheets **+** TSR |
| Size | **~1.5×** the current box at each site |
| LPR and Cash Advance approver | **Enlarge too**, accepting overlap into the row above |
| How it is expressed | **One module-level constant**, not eleven edited magic numbers |
| Upscale caps | Raised to the new scale, **not removed** — they still guard against blur |

The overlap decision was raised explicitly with the owner, with the alternative of widening only,
and the owner chose to enlarge and accept the risk. It is reversible by lowering one constant.

### Investigation

Verified by reading. The eleven stamping sites, with what limits each:

| # | Document / signer | Where | Current box | Note |
| --- | --- | --- | --- | --- |
| 1 | Travel Request — approver | `app.py:6744` | 160 × 28 pt | Printed name sits just below at y=191; grow **upward** from the same bottom edge |
| 2 | Travel Request — traveller group | `app.py:6662` | 160 × 54 pt at x=426 | **Cannot take a literal 50%**: 426+240 runs off the 612 pt page |
| 3 | Reimbursement PCV — approver | `app.py:22104` | `width*0.82` × field height | Has a `min(..., 1.0)` **upscale cap** |
| 4 | Reimbursement RFP — requester | `app.py:22206` | 91 × 24 pt | Scaled by page ratio from a 612×936 template |
| 5 | Cash Advance — requester | `app.py:44611` | 72 × 22 pt | Free space around it |
| 6 | Cash Advance — approver | `app.py:44627` | 150 × **13** pt | Name printed 11.5 pt below. **Tight** |
| 7 | CA Liquidation RFP — approver | `app.py:47467` | `min(line*0.58, 124)` × 18 | Has a `min(..., 1.0)` **upscale cap** |
| 8 | LPR — requester **and** approver | `app.py:51091` | ≤86 wide, `field_height - 1.2` | **Tight**: rows ~13.9 pt apart. Two tests guard it |
| 9 | Travel Liquidation Excel — submitter | `app.py:31125` | 125 × 34 px | Also sets row 5 height to 34 |
| 10 | CA Liquidation Excel — approver | `app.py:48166` | 95 × 22 px | Size appears **twice** — `.width/.height` and the `OneCellAnchor` `ext` |
| 11 | TSR — serviced / acknowledged | `templates/offline_tsr.html:6937-6942` | 250 × 68 canvas px | Client-side canvas. Underline is only 360 wide |

Three findings that shaped the approach:

- **Source signatures are large enough to survive the enlargement.** Captured at `devicePixelRatio`
  and stored up to 800 KB (`normalize_signature_data_url`, `app.py:4067`), then tightly cropped by
  `reimbursement_signature_data_url_to_png_bytes` (`app.py:21876`). Every box above is far smaller
  than the stored bitmap, so these are downscales today and remain downscales at 1.5× — **no new
  blurriness**, except where a `1.0` cap currently binds.
- **The two `1.0` caps are why a bigger box alone would do nothing** on sites 3 and 7: they forbid
  scaling above natural size, so a small stored image ignores the box.
- **Site 10 stores its size twice.** Changing `.width`/`.height` without the `ext=XDRPositiveSize2D`
  produces a stretched or clipped image.

### Execution steps

1. **Add the knob.** `SIGNATURE_STAMP_SCALE = 1.5` in `app.py` beside the signature helpers, with a
   comment recording why it exists and that sites 2, 6, 8 and 11 are clamped by form geometry.
   *Done when* every site references it rather than a per-site literal.
2. **The unconstrained PDF sites — 1, 4, 5.** Multiply box width and height by the constant and
   re-anchor so the signature grows *away* from its printed name: site 1 keeps its bottom edge and
   horizontal centre (160×28 → 240×42, x 421→381); sites 4 and 5 keep their centre.
3. **The capped sites — 3 and 7.** Scale the box **and** raise the `min(..., 1.0)` cap to
   `SIGNATURE_STAMP_SCALE`, so a smaller stored signature can fill the larger box. Keep the cap.
4. **The Excel sheets — 9 and 10.** Scale the pixel sizes and the row heights together
   (`row_dimensions[5]`; rows 36-37), or the image overlaps the rows below. For site 10, change
   `.width`/`.height` **and** the `OneCellAnchor` `ext` in one edit.
5. **The clamped sites — 2, 6, 8, 11**, each taking as much of the 1.5× as its geometry allows:
   - **2:** shift x left rather than widening past 612 pt, and drop `max_columns` 3 → 2 so each cell
     is ~50% wider at no layout cost. With 3+ signers this trades a second row — verify that case.
   - **6:** 150×13 → 225×19.5, growing upward from the underline.
   - **8:** widen to `min(129, max(60, field_width*0.75))` and take the full 1.5× on height, which
     is what pushes it into the row above.
   - **11:** 250×68 → **340×102**, not 375 — width is capped by the 360 px underline; start x moves
     `margin+105` → `margin+70` to stay centred. Everything below derives from `sigY + sigH`, so the
     footer shifts down 34 px; confirm the page still fits.
6. **Relax the two LPR guards honestly, do not delete them.**
   `test_each_signature_sits_inside_its_own_field` and `test_approver_signature_clears_the_invoice_row`
   (`tests/test_lpr_workflow.py:251,270`) encode a real defect that was fixed — the approver stamp
   landing on the Invoice No. row. The assertions become **bounded**: the stamp may rise above its
   own field but must not pass the **top** of the row immediately above (`rects['Intended for'][3]`);
   the horizontal assertions are unchanged. Each docstring records that the bound was deliberately
   loosened, on whose instruction, and what it still protects.
7. **Release plumbing.** `releases.json` dated the commit date. **Service worker bump required** —
   `templates/offline_tsr.html` is an `APP_SHELL` entry, so a cached device keeps the old TSR
   renderer. Read the live `CACHE_VERSION` out of `app.py` immediately before committing.

### Deliberately excluded

The **signature capture UI** and stored resolution — a rendering change only; raising capture
resolution is a separate decision with an 800 KB limit attached. The **approvals-page on-screen
signature panel** (`templates/approvals.html:5127`) — a web view, not a stamped document.
**Re-tuning any printed name, underline or field position** beyond what moving the signature
requires. **Signatures not stamped into a document**, such as email-body thumbnails.

### Verification

New `tests/test_signature_stamp_sizes.py`, each assertion with the positive control that proves it
can fail:

| Assertion | Positive control |
| --- | --- |
| `SIGNATURE_STAMP_SCALE` exists and every site references it | no site keeps a hardcoded box literal |
| Each PDF site's box is ~1.5× its previous dimensions | the previous values are pinned as the "before", so a no-op edit fails |
| The two upscale caps equal the scale, not `1.0` | a signature smaller than its box scales up to fill it |
| Site 10's `.width/.height` and its `ext` agree | asserted **together**, since disagreeing is the actual defect |
| `lpr_signature_box` stays inside its line horizontally | unchanged from today — proves only the vertical bound moved |
| LPR stamp does not pass the top of the row above | the bounded replacement for the loosened guard |
| Cache floor ≥ 78 | — |

Prove each new test fails without its fix, one at a time, confirming by SHA that the injection
applied and that the failure message is the expected one. **`app.py` is CRLF; the templates and
static assets are LF** — a needle with the wrong line ending silently matches nothing and reads
exactly like a vacuous test.

**End-to-end, which is the part that actually matters here:** generate one real document of each of
the eleven kinds against a throwaway database with a seeded signature, then measure the stamped
image placement — PyMuPDF `get_image_rects()` for the PDFs, the drawing XML for the two XLSX files,
the browser for the TSR canvas. Confirm for each that the image is ~1.5× its previous size, does not
cover its own printed name or underline, and that on LPR and the Cash Advance approver line the
overflow lands where the owner accepted it — **look at the rendered page, not only the numbers**.
Then the full suite (currently 525), `node --check` on the TSR inline script, and a 375 px pass on
the TSR since its footer moved.

### After implementation

Self-review the diff; `releases.json` dated the commit date; bump the service worker reading the
live value out of `app.py`; `changes.md`; this plan to `Executed` with its hash; `pending-work.md`
only if asked; commit per the standing checklist, staging file by file, never `scheduler.db`.

### Risks

| Risk | Blast radius | Mitigation |
| --- | --- | --- |
| **LPR and CA approver signatures cover the row above** — accepted, not hypothetical | Two official forms leave the building with a signature touching Invoice No. / Intended for | The bounded test keeps it to one row; the end-to-end render confirms it is acceptable. **Reversible by lowering one constant** |
| The TSR footer shifts down 34 px | Content after the signature block could push off the page | Verify the rendered TSR; the footer is near the page bottom |
| Travel traveller group with 3+ signers | Two columns forces a second row and *smaller* cells for 3+ people | Verify a 3-signer request; keep `max_columns` a named argument so it reverts alone |
| Excel row heights not scaled with the image | The signature overlaps the rows below in the XLSX | Step 4 scales both; asserted together |
| Forgotten worker bump | Field devices keep the old TSR renderer and none of this reaches a phone | The cache floor assertion |
| One constant everywhere | A future change moves **all eleven** at once | That is the intent, and why the clamped sites are documented as clamped |

### Critical files

`app.py` — the constant plus sites 1-10 (`6662`, `6744`, `22104`, `22206`, `31125`, `44611`,
`44627`, `47467`, `48166`, `51091`); `templates/offline_tsr.html` (~`6937`) plus the `APP_SHELL`
bump; `tests/test_lpr_workflow.py` for the two loosened guards;
`tests/test_signature_stamp_sizes.py` (**new**); `static/changelog/releases.json`.

## Close the four open items: chart sizing, the runtime cache, two dead routes, the digest

**Status:** `Executed — e0182a2`
**Approved:** 2026-08-07
**Started:** 2026-08-07 — the owner asked for the fixes directly rather than approving a plan and
then releasing it, so the record and the execution are the same instruction.
**Finished:** 2026-08-07 in `e0182a2`, after seven defect injections, the full 521-test suite, and a
browser pass at 375 px and 1280 px against a throwaway database.

**Where the outcome differed from the plan, recorded rather than quietly absorbed:**

- **The `ResizeObserver` redraw could not be verified.** The Browser pane does not composite the
  page, so `requestAnimationFrame` never runs and no `ResizeObserver` callback is delivered — a
  control observer on the same node did not fire even its guaranteed initial callback. The
  measurement logic it calls is proven by re-rendering at three container widths; the trigger is
  not. Carried into `pending-work.md` section 3 as the one open item from this batch.
- **One existing test had to be rewritten**, which the plan did not anticipate:
  `test_exports_reach_no_other_strategy_later_in_the_handler` split the fetch handler on the first
  `}` and searched the following fragment for a `return;`, so it was asserting the shape of
  whichever branch came next. Adding the `/logout` branch broke it while the export branch it names
  was untouched. It now reads the export branch itself, and was proved still red by deleting that
  branch's `return;`.
- **Two injections aborted and one passed green on the first run**, all three in the reassuring
  direction: the CSS and JS assets are **LF** while `app.py` is **CRLF**, and commenting out
  `caches.delete(RUNTIME_CACHE)` leaves the string where a source-level assertion still finds it.
  The match-count check caught the first two; the third needed the injection changed from a comment
  to a removal.
**Detailed:** 2026-08-07, after reading the shipped chart renderers, the service worker fetch
handler, and confirming both routes have zero callers.

### Context

The owner asked, in one message: *"fix the analytics chart scrolling at 375px, fix runtime cache, i
have already sent digest to everyone, fix dead routes also."* Four items, three of them code and one
a journal correction. All four are already recorded in `pending-work.md`; nothing here is new work
discovered in passing.

**"Fix runtime cache" is read as the section 5 decision that was re-opened on 2026-08-06**, not as
anything about `/export_`, which `v71` already closed. That is the only open runtime-cache item:
authenticated pages survive a sign-out in `RUNTIME_CACHE`, and the 1:1-device reasoning that made it
acceptable predates the HR role — the first role whose whole purpose is to see *less* than another
role on the same screen. The decision is now reversed: sign-out clears them.

### Decisions taken

| Decision | Value |
| --- | --- |
| Chart sizing | **Rewrite to 1:1**, which is what the approved Analytics plan specified and what shipped did not. Not "add a fade to the scroll" |
| Where the logout purge lives | **In the service worker**, keyed on the `/logout` navigation — not in page JS, which never runs once the browser has left the page |
| What the purge removes | The **whole** `RUNTIME_CACHE`, plus `/timeline` and `/offline-tsr` from the app shell. Static assets, `/login` and `/offline` stay |
| Dead routes | **Removed**, not wired up. Both have been dead through four sessions and neither has a caller to restore |
| Digest | Journal-only. The owner sent it; nothing to build |

### Investigation

Verified by reading, not assumed:

1. **The charts scroll because of two lines, and one of them is load-bearing.**
   `app-analytics.css:238` sets `min-width: 560px` on the SVG inside a frame ~320 px wide at 375 px;
   `chartScaffold()` (`app-analytics.js:96`) emits a fixed `viewBox` with `width: 100%`. Removing the
   `min-width` alone would **not** fix it — it would shrink `<text>` to ~6 px, which is precisely the
   outcome the plan rejected and the reason the `min-width` was added. Both must change together, so
   the renderers have to become width-aware.
2. **Every x coordinate in both renderers is a literal against a 640-unit canvas** —
   `renderHorizontalChart` places the label at 4, the bar track at 178, the count at 556 and the
   delta at 636 (`app-analytics.js:150-181`); `renderTrend` divides `590 / rows.length`
   (`:124`). These become functions of the measured width.
3. **The app shell holds authenticated HTML too, so purging only the runtime cache would be half a
   fix.** `APP_SHELL` (`app.py:14816`) precaches `/timeline` and `/offline-tsr`, and
   `precacheShellEntry()` fetches them `credentials: 'same-origin'`. `/login` and `/offline` in the
   same list are signed-out pages and must survive, or an offline logout has nothing to land on.
4. **Both logout paths are navigations** — `templates/layout.html:312` is an `<a href="/logout">` and
   `templates/settings.html:1078` sets `location.href`. So a fetch-handler branch catches both, and
   page JS would catch neither reliably.
5. **The offline queues are IndexedDB, not Cache Storage** (`app-offline-schedule.js:38-45`), so a
   cache purge cannot destroy a queued schedule or TSR. This was the one way the fix could have lost
   field work, and it cannot.
6. **`/logout` is currently cached by `staleWhileRevalidate`**, which is the accepted residual
   recorded in section 5. The network-only branch closes it as a side effect.
7. **Both routes are genuinely dead.** `grep` across `templates/`, `static/js/` and `tests/` returns
   only `app.py` itself, the perf-log list (`app.py:1159`, `:1175`) and journal prose. `/activity_page`
   uses `/get_activity_logs`, a different endpoint, as `pending-work.md` already records.

### Execution steps

1. **Measure, then draw.** Add `chartWidth(target)` reading `clientWidth` and a `chartScaffold()`
   that sets `width`/`height` attributes **and** a matching `viewBox`, so one user unit is one CSS
   px. *Done when* the SVG's rendered width equals its `viewBox` width at 375 px and at 1280 px.
2. **Make `renderHorizontalChart` width-aware.** Columns derived from the measured width: label
   `clamp(72, 28%, 150)`, count and delta columns fixed at the right, bar track taking the rest.
   Labels truncated to the column with the full text still in the row `<title>`. Row height and the
   210 px canvas height stay — 12 rows at 15 px still fit.
3. **Make `renderTrend` width-aware**, with **label thinning**: at 375 px a 31-day range cannot
   carry 31 date labels, so draw every *n*th where *n* comes from the measured width. Bars keep a
   2 px floor so a low day is never invisible.
4. **Re-render on resize.** One debounced `ResizeObserver` over the three frames, guarded on
   **integer width change**, re-rendering from `state.schedule` and never writing to the container's
   own width — the loop the Analytics plan's risk table named.
5. **CSS:** drop `min-width: 560px` and the fixed `height: 210px` from
   `.analytics-chart-frame svg`; `height: auto` with `width: 100%`. Keep `overflow-x: auto` on the
   frame as a floor, not as the mechanism.
6. **The logout purge.** Add `AUTHENTICATED_SHELL_ROUTES` and `purgeAuthenticatedCaches()` to the
   worker; branch on `/logout` in the fetch handler **before** the navigate branch, exactly as the
   `/export_` branch is ordered and for the same reason. Network-only, `event.waitUntil()` the purge
   so it completes after the page is gone, and fall back to the shell's clean `/login` when the
   request cannot reach the server.
7. **Delete the two routes** and their two perf-log entries. Confirm no helper is orphaned by the
   deletion before committing.
8. **Journals:** `pending-work.md` — digest closed as sent, and the three items above closed.

### Deliberately excluded

**Clearing `localStorage`, IndexedDB or the queues on logout.** The queues hold work an engineer has
done and not yet synced; destroying them on a sign-out would lose real field work, which is a far
worse failure than the one being fixed. **Purging the shell's static assets** — they carry no account
data and dropping them makes the next login slow for nothing. **A `Clear-Site-Data` header**, which
is the server-side equivalent: it also drops IndexedDB, so it fails the same test. **Wiring up the
two dead routes.** **Any change to `staleWhileRevalidate` itself** — with the runtime cache cleared
at sign-out, the residual it carried is gone, and rewriting the default handler is a much wider
blast radius than this.

### Verification

New `tests/test_analytics_chart_sizing.py` and additions to `tests/test_logout_session.py`, each with
the positive control that proves it can fail:

| Assertion | Positive control |
| --- | --- |
| No `min-width` above the mobile frame width on the chart SVG | the frame's `overflow-x: auto` is still present |
| The scaffold sets `width`, `height` and `viewBox` from a measured value, not a literal | the old fixed `viewBox: 0 0 640` string is gone from the file |
| Both renderers take a width parameter and no literal 640/590 x-coordinate survives | the renderers are still there and still call `svgElement` |
| The resize guard compares integer widths | the observer exists at all |
| The `/logout` branch is matched **before** the navigate branch, by index comparison | the navigate branch is still present — the same shape as the `/export_` ordering test |
| The purge deletes `RUNTIME_CACHE` and the two authenticated shell routes | it does **not** delete `/login`, `/offline` or `/static/` |
| `/logout` still clears the session server-side | the existing logout tests, unchanged |
| Cache floor ≥ 77 | — |

Prove each new test fails without its fix, **one at a time**, confirming the injection applied by SHA
and that the failure message is the expected one — a `\n` needle against these CRLF files silently
no-ops and reads exactly like a vacuous test.

Browser: Analytics at **375 × 812** and 1280 × 800, light and dark, with a wide branch name and a
month-long range — **no horizontal scroll inside any chart frame**, no `<text>` below ~10 px, and the
window resized across the breakpoint to prove the observer redraws without looping. Then sign out on
the same browser and confirm `caches.keys()` holds no `/timeline` entry and the runtime cache is
empty, and that signing in again rebuilds it.

### After implementation

Self-review the diff; `releases.json` entries dated the commit date; **bump the service worker
reading the live value out of `app.py` immediately before committing**, and the `?v=` on the two
Analytics assets; `changes.md`; this plan to `Executed` with its hash; `pending-work.md`; commit per
the standing checklist, staging file by file, never `scheduler.db`.

### Risks

| Risk | Blast radius | Mitigation |
| --- | --- | --- |
| **The purge lands on a field device that then goes offline** | An engineer who signs out loses the offline shell until the next online load | Queued work is IndexedDB and untouched; 1:1 devices mean sign-out is rare; the shell keeps `/login` and `/offline` so the app still opens |
| `ResizeObserver` re-render loop | The page hangs | Integer-width guard, 100 ms debounce, never set the container's width — the mitigation the Analytics plan already specified |
| Label collision at 375 px on a long range | Unreadable chart, which is the complaint being fixed | Label thinning from the measured width, and the hidden data table carries every row regardless |
| Removing a route that turns out to have a caller | A 404 on a live page | Zero callers confirmed across templates, JS and tests; both are also absent from `APP_SHELL` |
| Forgotten worker bump | Devices keep the old worker and never purge on logout — the fix silently does not exist in the field | The floor assertion; the bump is what renames the caches |

### Critical files

`static/js/app-analytics.js`; `static/css/app-analytics.css`; `templates/analytics.html` (`?v=`);
`app.py` (service worker ~`14812`, perf-log list `1159`/`1175`, the two routes at `18559` and
`19129`); `tests/test_analytics_chart_sizing.py` (**new**); `tests/test_logout_session.py`;
`tests/test_analytics_page.py`; `static/changelog/releases.json`.

## Analytics upgrade: give the page a job, and report purchase orders

**Status:** `Executed — 45da21c`
**Started:** 2026-08-06, after the project owner explicitly said to execute the plan.
**Approved:** 2026-08-06
**Detailed:** 2026-08-06, after mapping the current Analytics page end to end, the design language
the four dashboard phases established, and what data exists that is not yet surfaced.
**Finished:** 2026-08-06, in commit `45da21c`, after focused tests, the neighboring regression set,
the full 497-test suite (1 intentional skip), syntax/JSON/diff checks, and local desktop/mobile
light/dark browser verification.

Execution is authorized. The implementation must preserve the reports-only boundary for personnel
analytics and must not stage or modify the tracked local database.

### Context

The owner asked for P.O. reporting on Analytics, and for the whole page to be upgraded:
*"P.O analytics. but let us also upgrade the whole analytics page. improve the design, propose an
upgrade for the page."*

Analytics is the last major page that predates the dashboard redesign, and it shows. ~250 lines of
inline `<style>` with **zero design tokens**, so the four accent themes have no effect on it. Its
charts are white slabs in dark mode. No `<h1>`, no aria anywhere, unlabelled filter controls. Two
renderers interpolate **user-editable branch names unescaped** while their siblings on the same page
escape correctly. A failed refresh leaves every stale number on screen looking authoritative.

More fundamentally the page has no job of its own. Its headline tiles — Today, This Week, This
Month — **ignore the date filter directly above them.** They answer *what is happening now*, which
is the dashboard's question, already answered better there.

Phase 3 recorded that the manager view *"compensated for having no trend by showing more numbers"*.
**Trend is the gap Analytics can own.** Intended outcome: a page that answers *how is service
activity changing over this period, and where is it concentrated* — themed, accessible, printable,
with purchase-order reporting alongside.

### Decisions taken

| Decision | Value |
| --- | --- |
| Charts | **Hand-rolled inline SVG** driven by `--app-*` tokens. No library: this is an offline-first PWA, and canvas would not inherit the theme, would be invisible to screen readers, and would print as a bitmap |
| Scope | **Refresh + give the page a job** — fix every defect, real stylesheet with tokens, re-focus on period-over-period trend |
| Trend discipline | **Flow metrics only.** Stock metrics carry no arrow |
| P.O. panel access | `can_view_admin_reports()` **or** `can_manage_purchase_orders()` |
| P.O. + branch filter | **Show it, labelled company-wide.** Never infer a branch |
| Money | **None.** `PurchaseOrder` has no amount by prior decision |

### Shape of the work

Eight commits with real stopping points. **1–2** move CSS and JS to static files byte-identically
(no visual change, individually reversible). **3–4** fix backend correctness and speed with the
numbers unchanged. **5–7** are the actual upgrade and must land together or the payload and template
disagree. **8** is the worker bump and changelog. Stopping after 4 leaves the page faster and its
queries correct with nothing half-built. **The one change granting new access is in commit 7.**

### Investigation

Verified by reading. Two findings changed the design.

1. **`analytics-*` class names do NOT inherit dark mode.** `app-dark-pages.css` wildcards only
   `[class*="manager-"]`, `[class*="scheduler-"]`, `[class*="dashboard-"]`. `analytics-` appears
   there as three hand-written literal lists (`:447`, `:758`, `:773`), and
   `grep -rln "analytics-" templates/ static/js/` returns `templates/analytics.html` **only**. So the
   fix is the opposite of adding a wildcard — those `!important` rules are what break token theming.
   Build on tokens and remove the `analytics-*` selectors. **Each of those three rules also lists
   unrelated selectors** (`.accounting-card`, `.activity-mobile-empty`, `.reports-empty`, …) — remove
   only the `analytics-*` names, never the whole rule.
2. **Widening `/get_analytics_summary` would leak personnel data.** The owner's decision applies to
   the *panel*. That endpoint returns engineer names, branches and per-engineer workload, which a
   P.O.-only manager must not receive. **Split**: new `/get_po_analytics` under the wider predicate;
   `/get_analytics_summary` keeps `can_view_admin_reports()`.
3. **The sidebar gate is coarser than it looks.** `templates/layout.html:223` wraps Analytics *and*
   TSR files in one `{% if is_reports_admin_user %}`. A P.O.-only user needs Analytics **without**
   TSR files, so this needs a third branch, not a widened condition.

Confirmed at source: `/analytics_page` `app.py:16228` passes no Jinja context; template 756 lines
(markup 1-177, `<style>` 179-506, `<script>` 508-754) with **no `page_head` block**;
`analytics_scope_query()` `app.py:35616` joins `ShiftEngineer` so a shift with N engineers returns N
rows, hence the de-dup at `35661` copy-pasted at `36641`/`36816`/`36867`; `count_between()` `35643`
runs three extra full queries for tiles that ignore the filter; `engineers` keyed by `eng.name`
(`35700`) so same-named engineers merge, capped at 15 with no total returned; `statuses` returned
with no consumer and contradicting `open_statuses`; `analytics_visible_engineer_ids()` `35595`
**shared with `/get_tsr_archive`** (`36024`); the load-bearing regional-admin-may-view-Manila comment
at `35602`; no eager loading so `get_shift_engineer_records()` is N+1; XSS at
`analytics.html:571,574,596,597` with `escapeHtml` sitting at `606`; `res.json()` before `res.ok` at
`711`; unconditional mobile re-render at `665`; dead `lastAnalyticsData` / `parseLocalDate` /
`renderMobileAnalyticsSummary` / `.analytics-page` / `.analytics-panel`; no `@media print`;
`.dashboard-metric-link` 25px; cache version `v72-schedule-error-text` at `14811`; **no analytics
test file exists**.

### The page's job, and the resulting layout

**"How is service activity changing over this period, and where is it concentrated?"**

Header + filter `<form>` → scope line (`role="status"`) and error region (`role="alert"`) →
**Trend** (new, leads) → branches → categories → open client work by status (**stock, no arrow**) →
engineer workload ("Top 15 of N") → **purchase orders, company-wide** (new).

Retired: the Today/Week/Month tiles (they ignore the filter above them, at the cost of three extra
queries); the three insight cards (each restates row 1 of the chart beneath it); the
`mini-chart` + `analytics-bars` pairs (same object rendered twice, one truncated to 6 and one
complete, so they disagree about how many categories exist); the `statuses` key; the
`.analytics-hero` gradient (hardcoded, immune to all four accents, prints as a colour slab).

### Execution steps

1. **Extract the CSS**, byte-identically, to `static/css/app-analytics.css` + a `page_head` block.
   Behaviour-neutral, own commit. *Done when* the extracted body diffs empty against the removed
   block and the page is pixel-identical at 1280/375 × light/dark.
2. **Extract the JS** to `static/js/app-analytics.js`. No Jinja in the block, so no config shim yet.
3. **Count each shift once** — rewrite `analytics_scope_query()` to a membership subquery instead of
   the join (set-equivalent, since every caller already de-duplicates); add
   `analytics_scoped_shifts()` and route all four call sites through it. **Preserve** the existing
   behaviour that a shift with only `Shift.engineer_id` is invisible to analytics — "fixing" it
   would silently move every historical number; note it in `pending-work.md` instead. **Do not touch
   `analytics_visible_engineer_ids()`.**
4. **Load engineers in two queries**, not per shift — `analytics_engineer_map()` keeping the
   `Shift.engineer_id` fallback that feeds `branches['Unassigned']`; add `joinedload` for client and
   product. Do not modify `get_shift_engineer_records()`; it has many callers.
5. **Trend and the flow/stock split** — `analytics_previous_bounds()`; previous window counted with
   **aggregates only** so it is not a fifth scan; bucket server-side and **in Python** (not
   `func.strftime`, SQLite-only, nor `date_trunc`, Postgres-only). **Enforce the discipline in the
   payload shape:** only metrics carrying `previous` may render an arrow. `completed` gets none — it
   is `status=='Completed'` read today against a past window, so an arrow would encode recency bias.
6. **Themed SVG charts** — two components built with `createElementNS` + `textContent`, never string
   interpolation, which makes the XSS class structurally unreachable rather than escaped by
   discipline. `role="img"` + `<title>`/`<desc>` plus a visually-hidden table carrying every row.
   Draw 1 user unit = 1 CSS px (a fixed viewBox at `width:100%` scales `<text>` to ~6px at 375px).
   Print hides the SVG and reveals the table. **No pie or donut.**
7. **The P.O. panel** — `/analytics_page` gate widened, `can_view_schedule_analytics` passed so a
   P.O.-only user gets no schedule panels; new `/get_po_analytics` calling
   `ensure_purchase_order_schema()` first; third sidebar branch. Counts only, `PO_TYPE_LABELS` as the
   single source for labels. **Scope note rendered always**, not only when filtered.
8. **Every remaining defect** — stale-data-after-failure, double render, dead code, `<h1>` and
   heading order, `<label for>` and a real `<form>`, `scope="col"` and `<caption>`, status/alert
   split, `prefers-reduced-motion`, tokens throughout, one radius/spacing/shadow scale, `@media
   print`, and the `.dashboard-metric-link` 44px fix closing that `pending-work.md` item.

Reuse rather than reinvent: load **both** `app-dashboard.css` and `app-analytics.css`, and use
`.dashboard-metric-strip` and friends, the risk-verdict pill (`app-dashboard.css:127-154`) and
`.dashboard-collapsible-toggle`.

### Deliberately excluded

Any money figure, spend column or billing proxy (spend reporting is deferred; the deleted Billing
Visibility panel string-matched TSR *filenames*). Inferring a P.O. branch from client schedules —
same failure mode. A charting library. Pie/donut charts. New panels from other modules (TSR
turnaround has **no reliable timestamp**, and offline-queued TSRs would read as multi-day). Changing
`analytics_visible_engineer_ids()`. Adding `analytics-` to the dark-page wildcards.

### Verification

New `tests/test_analytics_page.py` and `tests/test_analytics_purchase_orders.py` — behavioural, in
the style of `tests/test_purchase_orders.py`, since **this page has no tests today**. Each with the
positive control that proves it can fail: de-duplication (one shift/three assignees → 1 and 3);
branch filter; regional-admin-may-view-Manila; `/get_tsr_archive` scope unchanged after step 3; date
bounds and previous-window length; caps with uncapped totals; `previous` present on flow and
**absent** on `stock.completed`; `statuses` gone; the export; the **access matrix** including
**P.O.-only denied from `/get_analytics_summary`**; P.O. aggregation; cache floor 73.

Injection proof: set an `Engineer.branch` and `Client.name` to
`"><img src=x onerror=alert(1)>` and confirm literal text in the SVG label, per-row `<title>`, hidden
table, engineer table, mobile card and print view. Separately prove each new test fails without its
fix using the byte-level harness — a `\n` replace against these CRLF files silently no-ops and the
suite stays green, which reads exactly like the tests being vacuous.

Browser: {1280×800, 375×812} × {light, dark} × {classic, shimadzu-red} — accent-following fills, no
white slab in dark, full keyboard pass, `aria-live` announcement, network killed mid-request with
**every number reset to an em dash**, ≥44px controls, no horizontal scroll, exactly one of
table/cards. Then print preview in both themes.

### After implementation

Self-review the diff; `releases.json` items dated the commit date; **bump the service worker reading
the live value out of `app.py` immediately before committing** (and the `?v=` on both new assets);
`changes.md`; this plan to `Executed` with its hash; `pending-work.md` only if asked; commit per the
standing checklist, staging file by file and never `scheduler.db`.

### Risks

| Risk | Blast radius | Mitigation |
| --- | --- | --- |
| **Widening `/analytics_page` and the sidebar** — the only change granting anything new | A P.O.-only account reaching schedule analytics or the TSR archive | The endpoint split, the third sidebar branch, and the access-matrix test asserting `/get_analytics_summary` is **denied** |
| `analytics_scope_query` rewrite touches four endpoints including `/get_reports_summary` | Every historical analytics and reports number | Set-equivalence rests on every caller already de-duplicating — re-confirm all four, and pin `/get_tsr_archive` |
| Removing `analytics-*` from `app-dark-pages.css` | Those rules list unrelated selectors | Remove only the `analytics-*` names; re-grep at implementation time |
| Two windows means two scans | A year-long range scans a year twice | Previous window is count-only; consider refusing ranges > 400 days |
| `ResizeObserver` re-render loop | Page hangs | Integer-width guard + 100ms debounce; never set the container's own width |
| `func.strftime` / `date_trunc` | Works on SQLite, breaks on Postgres | Bucket in Python. Easy to miss in review |
| Forgotten worker bump or `?v=` | Returning users get the old page against the new API | The floor assertion |
| Retiring the today/week/month tiles | Someone may read them daily | They contradict the filter above them. Call it out in the changelog |

### Critical files

`app.py` (analytics module ~`35518`, `/analytics_page` `16228`, new `/get_po_analytics`, worker
`14811`); `templates/analytics.html`; `static/css/app-analytics.css` (**new**);
`static/js/app-analytics.js` (**new**); `static/css/app-dark-pages.css`;
`static/css/app-dashboard.css`; `templates/layout.html`; `tests/test_analytics_page.py` and
`tests/test_analytics_purchase_orders.py` (**new**); `static/changelog/releases.json`.

## P.O. Details page, with a grantable access toggle

**Status:** `Executed — b01c78c`
**Started:** 2026-08-06, after the project owner explicitly said to execute the plan.
**Approved:** 2026-08-06
**Detailed:** 2026-08-06, after tracing the Clients page end to end, the grantable-capability
pattern from the 2026-08-05 admin-capabilities work, and how the Analytics page is built.

**Finished:** 2026-08-06, after implementation, focused tests, the full test suite, and a
throwaway-database browser verification. Implementation commit: `b01c78c`. The follow-up journal
commit contains this final status update and completion documentation.

### Execution outcome

Implemented the standalone P.O. Details register and its grantable access capability. The code
adds the additive `PurchaseOrder` table/schema helper, `po_admin_access` user capability and
Settings toggle, guarded page/API access, CSRF-protected CRUD with soft duplicate confirmation,
Client delete-orphan cascade, responsive filtering/sorting/modal UI, release metadata, and the
service-worker cache bump. The implementation intentionally excludes amounts, CSV import/export,
Shift/TSR/Product linkage, and analytics, as decided above. Verification passed with 13 focused
P.O. tests, 472 full-suite tests plus one expected skip, Python/JavaScript checks, and a local
browser pass on a throwaway database. Implementation commit `b01c78c` contains the approved code
and tests. `scheduler.db`, `output/`, `tmp/`, and the handoff note are not part of the implementation
or release.

Execution is now authorized. The implementation must preserve the two owner-emphasized
safeguards below, and must not stage or modify the tracked local database.

### Context

There is nowhere in the system to record a client's purchase orders. The owner wants a register
listing, per record: the **medical center**, the **P.O. date**, the **P.O. number**, and whether the
order is a **contract** or a **single visit**. It should look and behave like the existing Medical
Centers page, and which accounts can reach it should be switchable per-user in Settings rather than
hardcoded to a role. Analytics gains P.O. reporting afterwards, as a separate phase.

Intended outcome: a superadmin grants "P.O. records access" to an account; that account gets a
**P.O. Details** entry in the Records sidebar group and can add, edit and delete P.O. records.

### Decisions taken

| Decision | Value |
| --- | --- |
| Monetary amount | **None.** Counts only. Deliberately keeps this clear of the spend-reporting work deferred in `pending-work.md` section 2 |
| Access model | **One capability, view + manage**, mirroring `personnel_admin_access`. Superadmin and regional admin hold it implicitly |
| Contract vs single visit | **Text column** `po_type` with values `'contract'` / `'single_visit'`, shown as a two-option selector — not a boolean checkbox |
| Linkage | **Standalone.** FK to `Client` only. No FK to Shift, TSR or Product |
| Duplicate P.O. numbers | **Soft 409 + `force` re-post**, not a DB unique constraint |

### Investigation

Verified by reading, not assumed:

- **The capability pattern is a well-worn groove.** Columns at `app.py:1505-1507`;
  `ensure_user_admin_capability_columns()` at `app.py:3293-3313` **loops a tuple**, so a new flag
  needs no new function; `_has_active_account_capability()` at `app.py:7761-7768`;
  `approval_user_to_dict()` at `app.py:7622-7645`; `resolve_staff_permission_request()` at
  `app.py:16573-16681` (return dict confirmed at `:16668-16681`); save route at `app.py:16684-16778`.
- **`add_engineer`'s `permission_fields` set at `app.py:41893-41906` is the security-critical line.**
  The escalation check at `:41907-41910` only fires when a *listed* field appears in the payload. A
  new flag omitted there lets a personnel-admin mint accounts carrying it — the same shape as the
  escalation fixed in `54c4aaa`.
- **`can_manage_purchase_orders()` does not need a flag-alone variant.**
  `has_schedule_admin_capability()` (`app.py:7786-7802`) exists only because the schedule helpers hit
  a *narrower* branch afterwards (regional admin restricted to `REGIONAL_ADMIN_BRANCHES`), and a
  broad predicate ahead of it deleted that rule. The P.O. surface has no branch, ownership or
  record-level narrowing after the check, so there is nothing for the broad form to swallow. If a
  scoped P.O. rule is ever added, the flag-alone variant must be added at the same time.
- **`db.create_all()` runs on every non-static request** —
  `ensure_runtime_sqlite_migrations_before_request()` at `app.py:42625-42637`. A brand-new *table*
  therefore appears by itself. The migration helper is still needed for indexes and for any column
  added later.
- **`Client.products` / `Client.shifts` (`app.py:1817-1819`) declare no cascade.** A P.O. backref
  without `cascade='all, delete-orphan'` would make SQLAlchemy NULL a `nullable=False` FK and break
  the existing `/delete_client`. `Engineer.shifts` (`app.py:1780-1786`) is the house pattern to copy.
- **`nav_can_manage_any_schedule` is injected at `app.py:1297` but referenced nowhere in
  `layout.html`.** Do not repeat that — wire the new key into the sidebar and grep to confirm.
- **Restricted-account gates already deny by default.** `restrict_stock_inventory_only_accounts()`
  (`app.py:42651`) and `restrict_hr_schedule_only_accounts()` (`app.py:42672`) are allowlists, so
  `/po_details` is blocked for both with no edit. Do not add it to either allowlist.
- Records subnav confirmed at `templates/layout.html:256-262`, `records_paths` at `:134`.
- **Three things in the Clients code are bugs, not patterns:** `clients.html:788` fetches
  `/get_clients_summary`, **a route that does not exist**, 404ing on every load and silently
  swallowed; `renderTable()` (`:1036`) does `innerHTML +=` inside a loop; and `delete_client()`
  (`app.py:37278-37287`) returns success for an id that never existed.
- `tests/test_admin_capabilities.py` contains a source-string class (`:35-52`) whose own docstring at
  `:241-246` argues against the practice. Add behavioural coverage; do not extend that class.

### Owner-emphasized safeguards

These two details are implementation-critical and must be treated as one review checkpoint:

- **Permission escalation guard:** `add_engineer`'s `permission_fields` set at
  `app.py:41893-41906` controls whether the escalation check runs. The new `po_admin_access`
  field must be added to that set and assigned to the new account in the same edit. If it is
  omitted from the set, a personnel administrator can submit the field without the escalation
  guard and mint an account with P.O. access. Add a behavioural test proving a personnel-admin
  receives `403` while a superadmin can grant it, and verify the failing injection before restoring
  the intact file.
- **Client deletion cascade:** `Client.products` and `Client.shifts` currently declare no cascade.
  The new `PurchaseOrder` relationship must use
  `cascade='all, delete-orphan'` so deleting a Client does not make SQLAlchemy NULL a non-nullable
  foreign key or break the existing `/delete_client` workflow. Add a regression test that deletes a
  Client with a P.O. and confirms the deletion succeeds while another Client's P.O. remains. This
  is a compatibility requirement, not optional cleanup.

### Execution steps

**1. Model and schema — `app.py`**

1.1 After `class Client` ends (`app.py:1821`, before `class Contact`), add `PO_TYPE_CONTRACT`,
`PO_TYPE_SINGLE_VISIT`, and `PO_TYPE_LABELS` — one source of truth for display strings so the page,
the API and the later report cannot drift.

1.2 Add `class PurchaseOrder(db.Model)`, `__tablename__ = 'purchase_order'`: `id`; `client_id`
FK→`client.id`, `nullable=False`, `index=True`; `po_number` `String(60)`, `nullable=False`,
`index=True`; `po_date` `Date`, `nullable=False`, `index=True`; `po_type` `String(20)`,
`nullable=False`, default single-visit; nullable `created_at` / `created_by` / `updated_at`.
Relationship to `Client` with
`backref=db.backref('purchase_orders', lazy=True, cascade='all, delete-orphan')`. This cascade is
required because the existing `Client.products` and `Client.shifts` relationships declare no
cascade; without it, `/delete_client` can fail when SQLAlchemy tries to NULL a non-nullable P.O.
foreign key.
*Done when:* `PurchaseOrder.__table__.columns.keys()` contains no `amount`, `shift_id`, `tsr_id`
or `product_id`.

1.3 Add `ensure_purchase_order_schema()` beside `ensure_user_admin_capability_columns()`
(`app.py:3293`), with a module-global `_purchase_order_schema_ready` guard next to `app.py:2534`. It
calls `PurchaseOrder.__table__.create(bind=db.engine, checkfirst=True)`, then an additive
`PRAGMA table_info(purchase_order)` loop for the three nullable columns, then three
`CREATE INDEX IF NOT EXISTS` statements — `(client_id, po_date)`, `(po_number)`, `(po_date)` — the
live-safe idiom already used by `ensure_schedule_delete_indexes()` (`app.py:38133-38154`).
**Swallow and log** on failure, matching `app.py:3312`, so a P.O. migration problem cannot take down
login.

1.4 Call it from `initialize_database()` (after `app.py:42862`), from
`ensure_runtime_sqlite_migrations_before_request()` (after `app.py:42643`), and at the top of each
P.O. endpoint (as `get_clients()` opens with `ensure_contact_designation_column()`, `app.py:18631`).
**Not** from `restore_pwa_session_before_route()` — that runs on every request including `/static`.

**2. The `po_admin_access` capability**

| # | File / location | Edit |
| --- | --- | --- |
| 2.1 | `app.py:1508` | `po_admin_access = db.Column(db.Boolean, default=False, nullable=False)` |
| 2.2 | `app.py:3305` | Append `'po_admin_access'` to the existing tuple — no new function |
| 2.3 | after `app.py:7787` | `can_manage_purchase_orders()` via `_has_active_account_capability`, with a docstring recording **why** no flag-alone variant is needed |
| 2.4 | `app.py:7640` | `'po_admin_access': bool(getattr(user, 'po_admin_access', False)),` |
| 2.5 | `app.py:16589`, `:16606`, `:16679` | Read the flag; append `'P.O. records access'` to `capability_labels`; return it in the dict |
| 2.6 | `app.py:16717`, `:16743` | Add to `tracked_permission_fields`; assign to the target user |
| 2.7 | `app.py:41904`, `:41982` | **Add to `permission_fields` and assign on the new user in the same edit.** This is the privilege-escalation guard; omitting the list entry lets a personnel-admin mint P.O.-enabled accounts. |
| 2.8 | `templates/settings.html` | Checked var after `:1819`; a `col-lg-4` switch after `:1890` with class `po-admin-access-input` and `onchange="toggleAdminCapability(this)"`; payload key after `:2062`; **and `.po-admin-access-input` added to BOTH exclusion lists at `:2458` and `:2472`** |
| 2.9 | `app.py:1297` | `'nav_can_manage_purchase_orders': can_manage_purchase_orders(),` |
| 2.10 | `templates/layout.html:134`, `:261` | Add `'/po_details'` to `records_paths`; add the gated `nav_link('/po_details', 'fa-file-invoice', 'P.O. Details')` after the Inventory link |

2.5 needs no new conflict rule: the rejections at `:16607-16619` join `capability_labels`, which is
built only from flags actually requested — so ticking P.O. + Approver-only yields "P.O. records
access cannot be combined with Approver-only view", naming exactly what the user turned on, which is
what the comment at `app.py:16620-16628` demands.

*Done when:* the switch appears in Settings, ticking it clears Approver-only / Stock Inventory-only /
HR Schedule View and vice versa, and `grep -c nav_can_manage_purchase_orders templates/layout.html`
returns 1.

**3. Page route and CRUD — `app.py`, after `delete_client()` (`app.py:37287`)**

3.1 Helpers: `normalize_po_type()` (canonical value or `None`), `normalize_po_number()`,
`find_duplicate_purchase_order(client_id, po_number, exclude_id=None)` (case-insensitive, scoped to
**same client**), `purchase_order_to_dict()` (includes `po_type_label`).

3.2 `GET /po_details` → `po_details_page()`, guarded `if not can_manage_purchase_orders(): redirect`.
Deliberately **not** the `clients_page()` shape (`app.py:16237-16243`), whose docstring delegates
access to templates — every endpoint below also carries its own check.

3.3 `GET /get_purchase_orders` — guard `denied()` (`app.py:7907`). Returns `purchase_orders`, the
`clients` list and `po_types` in **one** payload, so the page issues exactly one XHR.

3.4 `POST /add_purchase_order`, `PUT /update_purchase_order/<id>`,
`DELETE /delete_purchase_order/<id>` — each guarded by `can_manage_purchase_orders()`. Validate the
client exists, number non-empty and ≤60 chars, `parse_date` (`app.py:4415`) accepts the date,
`po_type` recognised; each failure a distinct 400 message. Update and delete return **404 for a
missing id** — the deliberate correction to `delete_client()`. All three call `log_activity()`. No
`@csrf.exempt`; the front end sends `X-CSRFToken` via `getCSRFToken()` (`templates/layout.html:368-370`).

*Duplicate handling — soft 409 + `force`, not a unique index.* SQLite cannot add a constraint to an
existing table, and `CREATE UNIQUE INDEX` *fails outright* if live data already holds a duplicate,
leaving the migration to crash or silently no-op forever. Duplicates are also legitimately real (a
revised P.O. keeps its number; two hospitals can issue the same one). `/add_client` already returns
`{'status':'conflict'}, 409` and honours `force` (`app.py:37177-37181`), and `clientConfirmDialog()`
exists for it. A unique index can be added later once data is known clean; the reverse is not true.

**4. `templates/po_details.html` (new)**

Modelled on `clients.html`: inline `<script>`/`<style>`, no separate asset file, no `<form>`, inline
`onclick`, custom toast/confirm instead of native `alert`/`confirm`. Namespace everything `po`/`po-`.

- Filters: client text, number text, type select, and a `po_date` from/to range.
- Sortable headers (`client`, `po_date`, `po_number`, `po_type`) with the localStorage preference
  pattern from `clients.html:257-260`.
- Empty `<tbody id="po-table-body">` plus a parallel `#po-mobile-list`, swapped by CSS at the
  **768px** breakpoint exactly as `clients.html:1720-1726`.
- One `#poModal` for add and edit, mode set by a hidden `#po-id`.
- **po_type control:** real radios with visually-hidden inputs and styled labels — keyboard and
  screen-reader behaviour comes free, and add-mode preselects nothing rather than letting a checkbox
  impose a silent default.
- Gate Add/Edit/Delete on `nav_can_manage_purchase_orders`, **not** on `current_user.role` —
  `clients.html:27` uses the role literal, which `tests/test_layout_sidebar.py:44` bans in
  `layout.html` for the reason given at `app.py:1271-1282`.
- Do not copy the phantom `/get_clients_summary` fetch or `innerHTML +=` in a loop (build with
  `.map().join('')` and assign once). Escape every interpolated value, `client_name` included.

### Deliberately excluded

| Excluded | Why |
| --- | --- |
| Any amount / value column | Owner decision. Would pull in the spend-reporting decision deferred in `pending-work.md` section 2 |
| FK to Shift / TSR / Product | Owner decision — standalone first version. Linking to shifts also raises the multi-engineer join de-duplication hazard |
| CSV import/export | Not requested. `/import_clients` and `/export_clients` exist as precedent if wanted later |
| A DB unique constraint on `po_number` | One-way door on SQLite; see 3.4 |
| Adding `/po_details` to `APP_SHELL` | Not a field-safe offline route; precaching an authorized page invites the cached-login-page failure `precacheShellEntry` (`app.py:14733-14750`) guards against |
| The analytics phase | Separate phase — outlined below, to be planned properly before it is built |

### Verification

New `tests/test_purchase_orders.py`, behavioural only, in the fixture style of
`tests/test_admin_capabilities.py:64-185`. Every test names the positive control that proves it can
fail:

| Test | Positive control |
| --- | --- |
| P.O. surface open only to the capability — grantee 200, personnel/reports/schedule/plain 302 on page and 403 on API | grantee + superadmin 200 in the same test |
| Writes refused without the capability (403 on add/update/delete) | the same three calls as grantee succeed |
| Superadmin and regional admin hold it implicitly with the flag `False` | plain user `False` in the same block |
| Duplicate number → 409, then 200 with `force` | a different number, and the same number under a *different* client, both 200 first try |
| `po_type` validated and stored as text (`'maybe'` → 400) | both valid values 200, read back with the right label |
| `po_date` must be real ISO (`'08/06/2026'` → 400) | `'2026-08-06'` → 200 |
| Deleting a missing P.O. → 404 | the first delete returns 200 — the test that would have caught `delete_client`'s bug |
| Deleting a client removes its P.O.s, no IntegrityError | a second client's P.O.s survive |
| Only superadmin can grant the flag (personnel-admin → 403 on `/add_engineer`) | superadmin → 200 and the flag is set |
| Conflict message names the switch actually turned on | the same payload without `approver_only` → 200 |
| Grant audited as `po_admin_access: False -> True`; unchanged save not re-logged | the first grant is logged |
| `assert_cache_version_at_least(self, 70)` — a **floor**, never a pinned version | — |
| `releases.json` carries the P.O. item keys | — |

**Extend** `tests/test_admin_capabilities.py::test_each_capability_opens_only_its_intended_surface`
(`:265-305`) with `/po_details` → 302 for the other three capabilities and the plain user. Do **not**
extend `AdminCapabilitySourceTests`.

**Prove each test fails without its fix**, one at a time — invert the endpoint guard, the `force`
check, `normalize_po_type`, the 404, the cascade, and the `permission_fields` entry. Confirm the
injection applied (hash the file) *and* that the failure message is the expected one; per
`pending-work.md` section 6, an injection that does not reproduce the defect reads exactly like
success.

**Full suite:** `python -m unittest discover -s tests` from the repo root, on the machine as it is.
Record the count (currently 468). Plus `python -m compileall app.py` and `node --check` on the new
template's inline script if practical.

**Browser, desktop 1280 then 375px** — explicit `MEDICAL_SERVICE_TEST_DB`, never port 5000,
`preview_start` with a URL, stop the server afterwards:

1. Grant P.O. access in Settings; confirm the exclusion switches clear in both directions.
2. Try P.O. + Approver-only; the error names "P.O. records access".
3. As the grantee: sidebar shows P.O. Details; page loads with **exactly one XHR** and a clean console.
4. Add, duplicate-then-confirm, edit to the other type, sort all four columns, reload (sort
   persists), filter by each control, delete. Check `/activity_page` for the add/edit/delete entries.
5. As a reports-admin: no link, `/po_details` redirects.
6. At 375px: card list replaces the table, no horizontal overflow, every control ≥44px, the segmented
   type control comfortably tappable, modal fits without zoom.
7. Both light and dark themes (`static/css/app-dark-pages.css` exists for page-level overrides).

### After implementation

1. Self-review the diff before anything else.
2. `static/changelog/releases.json` — two items dated the **commit date**: the P.O. Details page and
   the Settings access toggle, `audiences: ["admins"]`. Without this
   `tests/test_changelog_coverage.py` fails the commit.
3. **Bump the service worker** — read the live value out of `app.py` immediately before committing,
   never from this note. Required because `templates/layout.html` is edited and it is embedded in
   every app-shell page. Two commits have already shipped without this bump.
4. `changes.md` — new dated section at the top per `AGENTS.md` "Mandatory Change Log".
5. `plans.md` — this plan's status to `Executed` with the commit hash.
6. `pending-work.md` — only if the owner asks; add the analytics phase as an open item.
7. Commit per the standing checklist: `git fetch origin`, re-check `origin/main` **after** finishing,
   stage **file by file** (never `git add -A`; `scheduler.db` is tracked and gitignore does not
   protect it), `git diff --cached --check`, confirm with `git show --name-only`, then push.

### Later: the analytics phase (outline only, to be planned separately)

- **Decide access first:** `/analytics_page` gates on `can_view_admin_reports()`, a *different* flag.
  Choose whether P.O. cards show to reports-admins, to
  `can_view_admin_reports() or can_manage_purchase_orders()`, or via a separate endpoint under the
  P.O. flag.
- Counts only: total in range, Contract vs Single Visit split, top clients by count, P.O.s per month.
- Reuse `analytics_date_bounds()` (`app.py:35379-35393`) unchanged; the step-1.3 indexes already
  serve the grouping.
- **There is no charting library.** `renderMiniChart()` (`templates/analytics.html:563-582`) and
  `renderBars()` (`:584-604`) are hand-rolled flexbox bars taking a flat `{label: count}` object, so
  the endpoint must emit that shape.
- **Both helpers interpolate labels unescaped.** Client names are user-entered — fix the helpers to
  escape (which also benefits the existing branch and engineer charts) rather than escaping at each
  call site.

### Risks

| Risk | Blast radius | Mitigation |
| --- | --- | --- |
| `po_admin_access` omitted from `permission_fields` (`app.py:41893-41906`) | **Privilege escalation** — a personnel-admin mints accounts with P.O. access. Same shape as `54c4aaa` | Step 2.7 lands the list entry and the assignment as one edit; dedicated test |
| Missing cascade on the `Client` backref | `/delete_client` starts raising IntegrityError — breaks an existing working page | `cascade='all, delete-orphan'` in 1.2 + a test that calls the real route |
| Forgotten service worker bump | Every device keeps a stale `layout.html` with no P.O. link, indefinitely | After-implementation step 3 + the floor assertion |
| Only one of the two `settings.html` exclusion lists edited | UI offers a combination the resolver then rejects with a 400 — the confusion documented at `app.py:16620-16628` | Browser steps 1-2 check both directions |
| Resolver return-dict key omitted | `KeyError` → 500 saving **any** user's permissions, not just P.O. ones | Tests exercise the save path end to end |
| `layout.html` / `settings.html` edits | Reach every page and the whole permissions UI; a Jinja typo is a site-wide 500 | Small additive edits; `test_layout_sidebar.py` + `test_admin_capabilities.py` + a manual pass |
| Soft duplicate rule | Genuine duplicates enterable after a confirm | Accepted and justified; the unique-index door stays open, the reverse does not |
| Codex works the same tree | Merge conflict / clobber | Keep edits contiguous, land promptly, re-read `origin/main` at commit time |
| **Otherwise contained** | No existing route, model or template changes behaviour. Everything is additive except two nav/settings templates and three shared permission functions, each gaining one line | — |

### Critical files

`app.py`; `templates/po_details.html` (**new**); `templates/settings.html`;
`templates/layout.html`; `tests/test_purchase_orders.py` (**new**); `static/changelog/releases.json`.
Reference while implementing: `templates/clients.html`, `tests/test_admin_capabilities.py`.

## Open an attached TSR from the schedule card

**Status:** `Executed — 6fa7fe4`
**Started:** 2026-08-05, after the project owner gave the execution go-ahead.
**Approved:** 2026-08-05
**Executed:** 2026-08-05 in commit `6fa7fe4`; documentation status recorded in the follow-up commit.
**Detailed:** 2026-08-05, after tracing the timeline payload's file data, the card and popover
renderers, and the TSR preview/download authorization.

### Context

To read a TSR attached to a schedule, a user opens the Edit modal and scrolls to Attachments. That
is a heavy, mutating surface for a read-only glance, and on mobile the "View Files" button literally
performs that workaround for you — `openMobileFullCalendarLiteFilesAction`
(`templates/timeline.html:9585`) opens the Edit modal and scrolls to `#existing-files-list` on a
450 ms timer.

**Almost everything needed is already in place.** `/get_timeline_data` already ships `file_details[]`
per shift with `download_url` populated for recognised TSRs (`app.py:35164`), and
`shouldUseTimelineLitePayload()` is hardcoded to `false` with a comment recording that it was
deliberately turned off *so cards receive `file_details`* (`templates/timeline.html:7982`). The
client already normalises those entries and synthesises preview URLs in `getShiftFileDetails()`
(`templates/timeline.html:14648`) and `getTimelineFilePreviewUrl()` (`templates/timeline.html:14670`).

The Details popover already exists, already opens from every card, and already renders an
`N File(s)` badge (`templates/timeline.html:11786`) — it just never makes the files reachable. This
turns that badge into a real list.

Intended outcome: click Details on any card carrying a TSR, see the TSR listed, click it, read it in
the in-app viewer. No Edit modal, no scrolling.

### Decisions taken

| Decision | Value |
| --- | --- |
| Placement | **The existing Details popover.** No new card button, no new component |
| Opening a TSR | **In-app preview** (`preview_tsr_archive_file`), not a forced download |
| Which cards | **Any card with a recognised TSR**, not only Completed ones |
| `scope=all` on the link | **Left as-is.** Engineers may already reference any TSR through the archive page |

### Investigation

- **The recognition signal is a blank string, and that matters.** The server sets `download_url`
  **only** when `shift_file_is_recognized_tsr(file_record)` is true; every other attachment gets
  `''`. But the client's `getShiftFileDetails()` then *synthesises* a URL from the file id
  (`templates/timeline.html:14656`), overwriting exactly the blank that carried the meaning.
  Filtering on that field client-side would list every photo as a TSR.
- `shift_file_is_recognized_tsr()` (`app.py:11702`) is not a filename check alone: it matches the
  system-generated PDF by identity via `online_tsr_submission_id`, and otherwise falls back to
  `'TSR'` appearing in the display or disk filename.
- **The Edit modal's link pattern is the one to copy** — an `<a target="_blank" rel="noopener">`
  built from `getTimelineFilePreviewUrl(fileInfo)`, with a document/image icon chosen by extension
  (`templates/timeline.html:14520-14545`).
- **`getShiftFileDetails()` has a legacy fallback** for shifts whose payload carries only a `files`
  array of names (`templates/timeline.html:14660`). Those entries have **no id and no preview URL**,
  so anything rendering links must degrade to plain text rather than emit a dead `href`.
- **HR accounts are already safe**: `redact_timeline_payload_for_hr` blanks `file_details` to `[]`,
  so an HR viewer's popover has no attachments to list. No new gate needed — but the block must
  render from `file_details` and nothing else, or that protection is bypassed.
- The popover is shared with **travel blocks**, which have no attachments. The new block must be
  absent rather than empty for them.
- `preview_tsr_archive_file` and `download_tsr_archive_file` share one guard,
  `user_can_view_shift_tsr_archive` (`app.py:35628`) — so switching the card link from download to
  preview moves no authorization.
- **Noted, not fixed:** `hasScheduleTSRAttachment()` (`templates/timeline.html:14681`) returns true
  for *any* attachment, so the existing "Edit TSR" button already appears for shifts holding only a
  photo. Pre-existing looseness, out of scope, but it is why this plan does not reuse that predicate.

### Execution steps

1. **Make TSR recognition explicit in the payload.** Add
   `'is_tsr': shift_file_is_recognized_tsr(file_record)` to the `file_details` entries in
   `/get_timeline_data` (`app.py:35164`) **and** `/get_shift_details` (`app.py:35330`), whose blocks
   are identical in shape and must stay that way. Two lines. It replaces inferring recognition from
   whether a URL string happens to be empty — the kind of implicit coupling that has broken twice in
   recent reviews.

2. **Pass the flag through the client normaliser.** In `getShiftFileDetails()`
   (`templates/timeline.html:14648`) carry `is_tsr` onto each normalised entry, defaulting to
   `false` on the legacy `files` fallback path. **Leave the synthesised `download_url`/`preview_url`
   behaviour alone** — the Edit modal depends on it; just stop treating it as evidence of anything.

3. **Render the attachments block in the popover.** Extend
   `buildTimelineScheduleHoverSummaryHtml()` (`templates/timeline.html:11764`) with a section after
   the summary body listing entries where `is_tsr` is true, each an
   `<a href="${getTimelineFilePreviewUrl(file)}" target="_blank" rel="noopener">` with the display
   name, matching the Edit modal's markup. Keep the existing `N File(s)` badge — it counts all
   attachments and stays truthful.
   - An entry with **no preview URL** (legacy fallback) renders as plain text, never a dead link.
   - **Omit the whole block** when there are no recognised TSRs, so travel blocks and
     attachment-free schedules are unchanged.
   - When non-TSR attachments also exist, add one muted line naming the count, so a card holding
     three photos and one TSR does not look like it lost something.

4. **Retarget the mobile "View Files" button.** `openMobileFullCalendarLiteFilesAction`
   (`templates/timeline.html:9585`) currently opens the Edit modal and scrolls. Render the same list
   from step 3 inside the sheet body it already owns (`#mobile-full-calendar-lite-detail-body`).

5. **Release plumbing.** `releases.json` entry dated the commit date or
   `test_changelog_coverage.py` fails. **Service worker bump required** — `/timeline` is the first
   `APP_SHELL` entry (`app.py:14683`), so a cached shell would keep a popover with no attachment
   block. Currently `v67-admin-capabilities`; **read the live value out of `app.py` immediately
   before committing** rather than trusting this line.

### Deliberately excluded

- **A new card button or a new popover component.** The Details popover already opens from every
  card and already counts the files; a sixth icon on a card action row that is tight at 375 px buys
  nothing.
- **Changing `scope=all`.** Decided: engineers may already reference any TSR through the archive
  page, and this surfaces an existing path rather than widening one.
- **Tightening `hasScheduleTSRAttachment()`** so "Edit TSR" stops appearing for non-TSR attachments.
  Real, pre-existing, and its own change — fixing it here would alter an existing button's
  visibility under cover of a read-only feature.
- **Making the mobile expanded-details "Files" row clickable** (`templates/timeline.html:10989`).
  The popover is the agreed surface.
- **Any change to the Edit modal's Attachments section.** It keeps upload and delete; this feature
  only removes the need to go there to *read*.

### Verification

- **Assert the payload flag by calling the endpoint**: a shift with a recognised TSR returns a
  `file_details` entry with `is_tsr` true and a non-empty `download_url`. **Positive control:** a
  shift whose only attachment is a non-TSR file returns `is_tsr` false — the assertion that proves
  recognition is real and not inferred, and the whole reason step 1 exists.
- **Assert HR still sees nothing**: an HR-only session's `/get_timeline_data` returns
  `file_details: []`. Positive control: an admin session on the same shift does get the entries.
- **Assert the preview link resolves**: fetch the `preview_tsr_archive_file` URL as an authorised
  viewer and get 200; as an account the guard refuses, get 403 — confirming no authorization moved.
- **Assert the legacy fallback degrades**: a payload carrying only a `files` name array produces
  entries with `is_tsr` false and no preview URL, and renders no anchor.
- **Prove each new test fails without its fix**, injecting one defect at a time — most importantly
  removing `is_tsr` and falling back to the URL-emptiness inference, which must make the non-TSR
  control fail. **Verify each injection applied by SHA** before trusting a run, and confirm files
  are restored byte-identical.
- **Browser**, isolated database, explicit `MEDICAL_SERVICE_TEST_DB`, never port 5000: open Details
  on a schedule with a TSR and confirm the link opens the in-app viewer in a new tab; open Details
  on a travel block and on an attachment-free schedule and confirm no empty block appears; check a
  schedule holding both a TSR and photos shows one link plus the other-attachments count. Standing
  bar: no horizontal overflow at 375 px, no tap target under 44 px, console clean. **Restart the
  server after every template edit** — Jinja caches compiled templates — and unregister the service
  worker and clear both caches after each asset edit, not once.
- Full suite via the documented command as **its own step before the commit**, never chained ahead
  of `git push`.

### After implementation

Review against this plan before committing and correct this record where the outcome differed. Then
the standing checklist in `pending-work.md` section 4: `git fetch origin`, re-read `origin/main`
**after** the work, stage file by file, never `git add -A`, keep `scheduler.db` out by name, confirm
with `git show --name-only`, push `main`. Add the `changes.md` entry in the same task.

### Risks

**The one that matters: listing non-TSR attachments as TSRs.** The recognition signal is an empty
string that the client already overwrites, so the obvious implementation — filter on `download_url`
— silently lists every photo as a TSR. Step 1 replaces the inference with a flag, and the non-TSR
positive control is what proves it.

**Second: a dead link from the legacy payload shape.** `getShiftFileDetails()` still supports shifts
carrying only a `files` name array, with no id and no preview URL. Rendering those as anchors would
404 on click, on exactly the older records most likely to be looked up.

**Third: quietly undoing the HR redaction.** The block must read from `file_details` and nothing
else. Sourcing filenames from `shift.files`, or refetching per shift, would hand an HR viewer the
attachment names the redaction removes.

Low risk otherwise: two lines of additive payload, one new block in a function that already renders
conditional sections, and no change to any authorization path.

## Grantable admin capabilities in Settings

**Status:** `Executed — 2ce472b`
**Started:** 2026-08-05, after the project owner gave the execution go-ahead.
**Approved:** 2026-08-05
**Detailed:** 2026-08-05, after tracing what superadmin actually means in this codebase and the
full blast radius of the predicate that decides it.
**Finished:** 2026-08-05, implementation committed as `2ce472b` after focused and isolated full-suite verification.

### Context

The request was "add an ability in Settings to change a user's role to superadmin." Investigation
showed that cannot work as described, and would be actively dangerous if built literally.

**Setting `role = 'superadmin'` does not make a superadmin.** `is_superadmin_user()`
(`app.py:7691`) requires **both** `role == 'superadmin'` **and** membership in
`SUPERADMIN_USERNAMES` — a hardcoded set of five (`app.py:4763-4776`). A promoted account still
fails at roughly 145 gated call sites.

**But it would not do nothing.** Three functions read the role column directly, bypassing the
predicate: `can_user_access_cash_advance` (`app.py:44428`) grants access to every Cash Advance
record; `lpr_can_manage` (`app.py:50211`) and `can_user_approve_lpr` (`app.py:50222`) grant LPR
management and approval — including of the promoted user's own LPRs. Meanwhile `get_display_role`
(`app.py:7655`) would label them "Superadmin", so the half-state would look like success.

So instead of widening the most powerful predicate in the system, this grants **three specific
admin capabilities per user**, using the per-user permission-flag pattern the codebase already has
for stock inventory and HR schedule view. The superadmin allowlist stays code-controlled.

Intended outcome: a superadmin can give a trusted account personnel, reporting or scheduling
authority from Settings, without handing over password resets, permission granting, system backup
download, or approval-routing bypass.

### Decisions taken

| Decision | Value |
| --- | --- |
| Approach | **Capability toggles only.** No DB-backed superadmin, no change to `is_superadmin_user` |
| Capabilities | **Personnel management**, **Reports and analytics**, **Schedule management for all engineers** |
| Settings administration | **Not grantable.** Email templates, recipients and approval routing stay superadmin-only |
| The three raw-role bypasses | **Fixed in this change** |
| Who can grant | Superadmin only, inheriting the existing `settings_update_approval_user` gate |

Settings administration was deliberately left out: approval routing is how approvals get wired, so
granting it is the crown by another name.

**One decision made here for the owner to reverse if they disagree:** personnel management grants
**add and edit, not delete**. `delete_engineer` (`app.py:41880`) permanently deletes the linked
`User` account as well as the personnel record. That is a different order of destruction from
editing a phone number, so it stays superadmin-only. Including it is a one-line change to the guard.

### Investigation

- **The pattern to copy is `hr_schedule_view`**: an additive nullable-safe boolean on `User`, an
  `ensure_user_hr_schedule_view_column()` migration registered in both `initialize_database()` and
  the `before_request` hook, a predicate beside the other authorization helpers, and a toggle in the
  Settings approval-user card. Use **distinct names for column and predicate** — unlike
  `can_manage_stock_inventory`, where the column and the function share a name and the function
  reads the column through `getattr`, which is confusing to read.
- **`resolve_staff_permission_request()`** (`app.py:16470`) is now the single place permission rules
  live, shared by `settings_update_approval_user` and `add_engineer`. The new flags **must** go
  through it, or Settings and Add Personnel will drift — exactly what the last two reviews caught
  elsewhere.
- **`add_engineer`'s `permission_fields` set** (`app.py:41721`) is what stops a non-superadmin
  sending permission fields. The three new flags must be added to it, or a regional admin could
  assign them at creation time.
- **The four schedule permission functions** — `can_modify_schedule_for_engineer_ids`
  (`app.py:7841`), `can_create_schedule_for_engineer_ids` (`app.py:7866`),
  `can_work_on_existing_schedule_shift`, and `can_submit_update_engineer_ids_for_scope` — all branch
  on `is_superadmin_user()`, then `is_regional_admin_user()`, then `role == 'engineer'`, and
  **default-return `False`**. They take no user argument; they read `current_user`. Every schedule
  mutation endpoint depends on that default-deny, so this is the one place the schedule capability
  may be added.
- **The audit trail for permission changes is a single free-text line** —
  `f"Updated approval user settings for {target_user.username}"` (`app.py:16596`). No field, no
  before, no after. Acceptable for a stock-inventory toggle; not for granting personnel or schedule
  authority.
- **`make_user_admin`** (`app.py:41902`) returns "Admin promotion has been disabled." The git
  history **cannot say why** — `git log -S "make_user_admin"` returns only `b03e281` ("Initial
  Railway migration setup"), a squashed import, so the rationale predates this repo. Recorded
  because a future reader will otherwise assume it was never considered.

### Execution steps

1. **Add three columns and one migration.** On `User`, beside the stock-inventory and
   `hr_schedule_view` flags: `personnel_admin_access`, `reports_admin_access`,
   `schedule_admin_access`, all `db.Boolean, default=False, nullable=False`. One
   `ensure_user_admin_capability_columns()` following `ensure_user_hr_schedule_view_column()`
   verbatim in shape — `_ready` global, `PRAGMA table_info(user)`, `ALTER TABLE ... ADD COLUMN` only
   when absent, `[DB MIGRATION]` print — registered in `initialize_database()` **and** the
   `before_request` hook list.

2. **Add three predicates**, beside the other authorization helpers, each shaped
   `is_admin_authorized(target) or bool(getattr(target, '<column>', False))`:
   `can_administer_personnel()`, `can_view_admin_reports()`, `can_manage_any_schedule()`. **Purely
   additive** — superadmins and the regional admin keep everything they have, and no existing
   account's access changes until someone ticks a box.

3. **Route the flags through the shared resolver.** Add all three to
   `resolve_staff_permission_request()` (`app.py:16470`) and to `add_engineer`'s `permission_fields`
   set (`app.py:41721`). **Rule:** none of the three may combine with `approver_only`,
   `stock_inventory_only` or `hr_schedule_view` — those are restricted-view modes that strip the
   navigation, and an HR-only account with personnel administration is incoherent. Follow the
   message style fixed in the last review: name the switch that actually conflicts.

4. **Apply the personnel capability.** Swap `is_admin_authorized()` for `can_administer_personnel()`
   on `/engineers_page`, `/get_engineers` account metadata, `add_engineer`, `update_engineer` and
   `export_engineers`. **`delete_engineer` keeps `is_admin_authorized()`.**

   **The critical safety property:** `add_engineer`'s superadmin-only sub-gate on staff types and
   permission fields (`app.py:41732`) **must stay `is_superadmin_user()`**. If a
   personnel-management grantee could assign permissions, the capability would become a route to
   granting itself and everything else.

5. **Apply the reports capability.** Swap in `can_view_admin_reports()` on the admin reporting,
   analytics and HR-export gates. Read-only surfaces only — nothing that mutates.

6. **Apply the schedule capability in one place.** Add a single
   `if can_manage_any_schedule(): return True` branch to each of the four schedule permission
   functions, immediately after the `is_superadmin_user()` branch so a grantee gets all branches
   rather than the regional admin's Cebu/Davao restriction. **Nowhere else.**

7. **Fix the three raw-role bypasses.** Change `can_user_access_cash_advance` (`app.py:44428`),
   `lpr_can_manage` (`app.py:50211`) and `can_user_approve_lpr` (`app.py:50222`) from
   `role in {'superadmin', 'regional_admin'}` to `is_admin_authorized(<that user>)`, so there is one
   definition of admin. `lpr_can_manage` also has an asymmetry worth removing while there — it uses
   `is_admin_authorized()` when the target is the current user and the raw role otherwise.

   **Check before tightening, not after.** Count accounts carrying `role == 'superadmin'` outside
   `SUPERADMIN_USERNAMES`. If none — which the bootstrap code suggests, since only
   `bootstrap_static_accounts` sets that role and only for the five — the change provably alters
   nobody's access, and that number belongs in `changes.md`. Same discipline that made the
   stock-inventory branch narrowing safe.

8. **Make the permission audit line say what changed.** Replace the generic
   `"Updated approval user settings for X"` (`app.py:16596`) with a line naming each changed field
   and its old and new value.

9. **Settings UI.** Add the three toggles to the approval-user card in `templates/settings.html`
   beside the Stock Inventory and HR blocks, and to the payload in `saveApprovalUser`. Superadmin
   only, inheriting the existing gate on `settings_update_approval_user` (`app.py:16562`) — do not
   add a second gate. Label them for what they grant, not as "admin".

10. **Release plumbing.** `releases.json` entry dated the commit date or
    `test_changelog_coverage.py` fails. `templates/settings.html` is **not** an `APP_SHELL` entry
    and `layout.html` is untouched, so **no service worker bump** — confirm by reading `APP_SHELL`
    at implementation time rather than trusting this line.

### Deliberately excluded

- **Any change to `is_superadmin_user` or `SUPERADMIN_USERNAMES`.** The allowlist stays
  code-controlled. This plan grants capabilities, never the crown.
- **Settings administration as a capability** — email templates, recipients, approval routing.
  Approval routing decides who approves what; granting it is equivalent to granting everything.
- **`delete_engineer`.** Stays superadmin-only because it destroys the linked login too.
- **Password resets, system backup download, approval-routing bypass, stock adjustments and
  reversals.** All remain `is_superadmin_user()`. These are what make superadmin dangerous and none
  was asked for.
- **Re-enabling `make_user_admin`.** Stays disabled. Its rationale is not recoverable from this
  repo's history, and nothing here needs it.

### Verification

- **Prove each capability by calling endpoints, not by reading predicates.** For each of the three:
  build a user carrying only that flag and assert the newly-permitted endpoints return 200 while
  **every** endpoint belonging to the other two capabilities, and every superadmin-only endpoint,
  returns 403. Positive control: a real superadmin gets 200 on all of them.
- **The escalation test, which is the one that matters.** A personnel-management grantee calls
  `add_engineer` with permission fields and with a non-engineer `staff_type`, and **must get 403**.
  Positive control: the same account succeeds at adding a plain engineer. Without this, the
  capability can grant itself.
- **The schedule write surface, by calling all of it.** With only `schedule_admin_access`, hit
  `/add_shift`, `/update_shift`, `/move_shift`, `/delete_shift`, `/batch_delete_shifts`,
  `/preview_delete_shifts`, `/delete_shifts_previewed` and both scheduler quick-actions. Assert the
  first seven now succeed and the scheduler-only quick-actions still refuse — they gate on
  `is_scheduler_user`, not these four functions. Positive control: an account with no flag is
  refused on all of them.
- **Assert the additive property explicitly:** for a superadmin, the regional admin, an ordinary
  engineer and an approver-only account, every one of the three predicates returns exactly what it
  returned before the change.
- **Assert the mutual exclusions** reject and that the message names the switch that actually
  conflicts.
- **Assert the audit line names field, old value and new value**, with a positive control that an
  unchanged field is not listed.
- **Before tightening step 7**, record the count of `role == 'superadmin'` accounts outside
  `SUPERADMIN_USERNAMES` and put the number in `changes.md`.
- **Prove each new test fails without its fix**, injecting one defect at a time, **verifying the
  injection applied by SHA** before trusting a run and confirming the file is restored
  byte-identical. A `\n` search string against these CRLF files silently matches nothing.
- **Browser**, isolated database, explicit `MEDICAL_SERVICE_TEST_DB`, never port 5000: grant each
  capability to a seeded account, sign in as it, confirm the expected pages appear and the rest of
  the admin surface does not. Standing bar: no horizontal overflow at 375 px, no tap target under
  44 px, console clean. Restart the server after every template edit — Jinja caches compiled
  templates.
- Full suite via the documented command as **its own step before the commit**, never chained ahead
  of `git push`.

### After implementation

Review against this plan before committing and correct this record where the outcome differed. Then
the standing checklist in `pending-work.md` section 4: `git fetch origin`, re-read `origin/main`
**after** the work, stage file by file, never `git add -A`, keep `scheduler.db` out by name, confirm
with `git show --name-only`, push `main`. Add the `changes.md` entry in the same task.

### Risks

**The one that matters: a capability that can grant itself.** If step 4 lets a personnel-management
grantee assign permission fields in `add_engineer`, they can hand themselves every other flag and
the scoping of this plan evaporates. The net is the explicit escalation test in Verification, which
fails loudly rather than leaving a hole that only shows up when someone uses it.

**Second: widening the schedule write surface.** Step 6 adds a branch to four functions whose
default-deny currently protects nine mutation endpoints — the same functions an earlier plan
deliberately left untouched. Adding it anywhere other than those four, or to some and not others,
produces an account that can create schedules but not delete them, or the reverse. Hitting every
endpoint is what catches that.

**Third: silently changing access in step 7.** Tightening the three bypasses is correct, but if any
account outside the five carries `role == 'superadmin'` it would lose Cash Advance and LPR access
with no warning. Counting first turns that from a discovery into a decision.

## Recall: withdrawing a submitted request, with a reason

**Status:** `Executed - 2c20eed`
**Approved:** 2026-08-05
**Detailed:** 2026-08-05, after inventorying every submit-then-approve module, the shared approval
audit and notification infrastructure, and the requester-facing UI in each module.
**Finished:** 2026-08-05, implementation and verification completed in commit `2c20eed`.

### Context

Once a request is submitted there is no way to pull it back. The requester notices a wrong amount,
a wrong date, a missing receipt — and their only options are to ask an approver to reject it, or to
let it be approved wrongly and fix it afterwards. Neither leaves an honest record of what happened
or who decided it.

Recall lets the requester withdraw their own submitted-but-unapproved request, state a reason, and
get the record back in an editable state to correct and resubmit. The reason is mandatory and lands
in the audit trail.

**The audit half is nearly free.** `record_universal_approval_audit(module, record_id, action, ...)`
(`app.py:5228`) stores `action` as a plain `String(80)` with no enum, and already carries
`status_from`, `status_to`, `remarks` and `metadata_json`. A `'recalled'` action with the reason in
`remarks` needs **no schema change**, and `get_universal_approval_audit_entries()` already reads it
back generically for any module.

**Approval is single-step, first-actor-wins.** There is no per-approver state anywhere — no partial
approvals to unwind. Recall only ever undoes one flat `Submitted` status.

### Decisions taken

| Decision | Value |
| --- | --- |
| State after recall | **Editable and resubmittable** — the same record, corrected and sent again |
| Who can recall | **The requester only** — the owner of the record |
| Modules in scope | **Five:** Leave Request, Reimbursement, Travel Request, Cash Advance, LPR |
| Travel Liquidation and Cash Advance Liquidation | **Excluded for now** — accounting-gated, and they mirror status onto a parent record |
| Requester signature on recall | **Cleared.** Resubmitting requires re-signing |
| Reason | **Mandatory.** No reason, no recall |

Clearing the signature is the point worth defending: a signature attests to the content *as
submitted*. If the record is recalled and edited, carrying the old signature forward would attach an
attestation to content the signer never saw.

### Investigation

- **`reject_*` is the template to copy.** `reject_reimbursement` (`app.py:34298-34350`) is the
  cleanest instance: require remarks (400 if absent), 404 if missing, 403 if not yours, **409 if
  `status != 'Submitted'`**, then mutate, clear the signature snapshot,
  `record_universal_approval_audit(...)`, `resolve_pending_approval_notifications(module, id,
  event='submitted')`, notify, commit. Recall is the same shape with a different actor guard and a
  different destination status.
- **That 409 is the concurrency guard and must be kept.** It is what stops a recall landing on a
  request an approver approved a moment earlier.
- **`resolve_pending_approval_notifications`** (`app.py:5327`) already exists to clear stale
  "awaiting approval" notices and is used by every approve/reject handler. Recall must call it, or
  approvers keep a notification for a request that is no longer pending.
- **Requester signature fields are named identically across all five modules** —
  `requester_signature_snapshot`, `requester_signature_layout`, `requester_signed_at` (confirmed on
  `CashAdvanceHeader` `app.py:42730` and `LPRHeader` `app.py:49632`). One helper mirroring
  `clear_approval_signature_snapshot` (`app.py:5169`) covers them all.
- **`reimbursement_lock_claim_schedules`** (`app.py:22265`) is a transaction-scoped row lock, **not**
  a persistent flag — nothing to unlock on recall. Checked because it looked like state that would
  leak.
- **There is no module→model registry.** `can_view_universal_approval_audit` (`app.py:7298`)
  resolves records with a hardcoded if/elif chain per module. Five copies of recall logic is
  precisely the shape that drifted apart twice in recent reviews, so this plan introduces the
  registry rather than extending the chain.
- `APPROVAL_REQUEST_SCOPES` (`app.py:4786`) is the canonical module-string set already shared by
  routing, audit and notifications. The registry keys off the same strings.
- Editable-status constants per module: `EDITABLE_STATUSES` (`leave_feature.py:25`),
  `REIMBURSEMENT_EDITABLE_STATUSES` (`app.py:20334`), `TRAVEL_REQUEST_EDITABLE_STATUSES`
  (`app.py:25004`), `LPR_EDITABLE_STATUSES` (`app.py:49699`), and an inline list for Cash Advance
  (`app.py:44786`). The recall destination must land inside these, or the requester cannot edit what
  they just pulled back.
- **Seven modules have a submit→approve workflow**, not six: LPR has its own `submit_lpr`
  (`app.py:51027`), `approve_lpr` (`app.py:51103`) and `reject_lpr` (`app.py:51134`). Online TSR
  submission and the RFP/PCV documents are **not** approval workflows — TSR is an intake/versioning
  record with no approve route, and RFP/PCV are PDFs generated from an already-approved parent.

### Execution steps

1. **Build the recall registry.** One module-level table keyed by the existing scope strings, each
   entry naming the model, the owner field, the destination-status resolver, and an optional
   post-recall hook. Five entries: `leave_request`, `reimbursement`, `travel_request`,
   `cash_advance`, `lpr`. **Default deny** — a scope absent from the registry is not recallable, so
   adding a module is a deliberate act.

2. **Add `clear_requester_signature_snapshot(target_obj)`** beside
   `clear_approval_signature_snapshot` (`app.py:5169`), clearing `requester_signature_snapshot`,
   `requester_signature_layout` and `requester_signed_at` where present. Same defensive shape — skip
   fields the model does not have.

3. **Add one endpoint: `POST /api/requests/<module>/<int:record_id>/recall`.** Not five routes. Body
   `{reason}`. In order: resolve the registry entry (404 if unknown module), load the record (404),
   confirm `current_user.id` matches the owner field (**403**), require a non-empty reason (**400**),
   and require `status == 'Submitted'` (**409**, message naming the current status). Then: set the
   destination status, clear `submitted_at`, clear the requester signature via step 2, clear any
   approval/rejection fields, and reset `accounting_status` where the model has one.

4. **Write the audit and clear the stale notices.** `record_universal_approval_audit(module,
   record_id, 'recalled', actor_user=current_user, status_from='Submitted', status_to=<destination>,
   remarks=<reason>, metadata={...})`, then `resolve_pending_approval_notifications(module,
   record_id, event='submitted')`, then a `SystemNotification` to each assigned approver from
   `get_assigned_approvers_for_requester(header.user_id, module)` telling them it was withdrawn —
   they may have been about to act on it. Plus an `ActivityLog` row.

5. **Leave Request needs its own destination status, and getting this wrong destroys data.** A leave
   that reached `Submitted` from `Provisional` (a superadmin's plot) or `Form to Follow` (emergency
   Sick Leave) carries **calendar `Shift` rows**. Recalling it flatly to `Draft` would delete a
   superadmin's provisional block. The resolver returns `Provisional` when `provisional_created_at`
   is set, `Form to Follow` when `emergency_form_to_follow` is set, and `Draft` otherwise — all three
   are in `EDITABLE_STATUSES` — and the hook calls `update_calendar` with the matching state so the
   blocks follow.

6. **Per-module notes for the registry entries.**
   - **Travel Request** — participants can *submit* (`can_current_user_submit_travel_request`,
     `app.py:26084`), but per the decision only `user_id` may recall. State that in the entry so it
     reads as a decision, not an oversight.
   - **Cash Advance** — `user_id` is a plain `db.Integer`, **not a declared ForeignKey**
     (`app.py:42723`). The owner comparison still works; note it so nobody assumes a relationship
     exists. It also keeps its own `CashAdvanceAudit` alongside the universal trail — write both,
     matching what submit does.
   - **Reimbursement** — reset `accounting_status` as well as `status`.
   - **LPR** — destination `Draft`, inside `LPR_EDITABLE_STATUSES`.

7. **UI: one shared partial, not five copies.** The confirm-dialog and required-remarks pattern
   exists only in `templates/approvals.html` (`approvalConfirmDialog` ~2425-2484; the remarks
   textarea and its required check ~2124 and ~5802) and is approver-side. Extract a small
   recall-modal partial — confirm text plus a required reason textarea — and include it in the five
   requester templates (`leave_request.html`, `reimbursement.html`, `travel_request.html`,
   `cash_advance.html`, `lpr.html`). Add the Recall button to each module's own row renderer, shown
   only when the row is the user's own and its status is `Submitted`.

8. **Status display.** Each template maps status to a CSS class in its own helper (`statusClass` in
   `leave_request.html`, `getReimbursementStatusPillClass` in `reimbursement.html`, and so on).
   Recall lands records back in existing statuses — `Draft`, `Provisional`, `Form to Follow` — so
   **no new badge is needed**. Confirm that per template rather than assuming; a status with no class
   renders unstyled.

9. **Release plumbing.** `releases.json` entry dated the commit date or
   `test_changelog_coverage.py` fails. **Service worker bump required** — the five requester
   templates are reached through the app shell; currently `v65-provisional-leave`, but **read the
   live value out of `app.py:14588` immediately before committing** rather than trusting this line.

### Deliberately excluded

- **Travel Liquidation and Cash Advance Liquidation.** Excluded by decision. They sit behind an
  accounting-center gate and mirror their status onto a parent record on submit (`TravelRequest` →
  `'Liquidation Submitted'`, `CashAdvanceHeader` → same), so recalling one must also revert the
  parent or the parent reads "Liquidation Submitted" forever with nothing pending. That coupling
  deserves its own task.
- **Recall by anyone but the requester.** No superadmin override and no approver-side recall.
  Approvers already have Reject, which takes remarks and does the same job from their side.
- **Recalling an approved request.** Approval fires calendar blocks, HR emails and accounting
  handoffs. Un-approving is a different feature with a much larger blast radius.
- **Unsending notification emails.** Submit fires async emails to approvers and they cannot be
  recalled. The audit entry records that a recall happened after the fact; the notification to
  approvers in step 4 is the mitigation.
- **A cross-module "my requests" view.** Each module keeps its own page.

### Verification

- **Test the guards by calling them, on every module in the registry.** For each of the five: recall
  as the owner on a `Submitted` record succeeds; recall as a **different user** returns 403; recall
  with an empty reason returns 400; recall of a `Draft` and of an `Approved` record returns 409.
  Positive control: the same request with a reason, as the owner, on a Submitted record, succeeds —
  so the refusals are the guards and not a route that rejects everything.
- **Assert the record is genuinely editable afterwards** — the destination status is inside that
  module's editable-status constant, and a resubmit of the recalled record succeeds. A recall that
  strands a record in a state nobody can edit is worse than no recall.
- **Assert the reason reaches the audit trail**: a `'recalled'` entry for that module and record id
  with `status_from='Submitted'`, the destination in `status_to`, and the reason in `remarks`.
  Positive control: the reason string is one the fixture chose, so the assertion cannot pass on a
  pre-existing row.
- **Assert the requester signature is cleared** and that resubmitting requires signing again.
- **Assert the approvers' pending notifications are gone** after a recall, and that a withdrawal
  notice reached each assigned approver.
- **The leave-calendar case, which is the one that can destroy data**: recall a leave that reached
  Submitted from `Provisional` and assert it returns to `Provisional` **with its calendar blocks
  still present**. Positive control: an ordinary leave with no provisional history returns to `Draft`
  with no blocks, so the first assertion is reading the resolver and not a hook that always keeps
  blocks.
- **Prove each new test fails without its fix**, injecting one defect at a time, **verifying the
  injection applied by SHA** before trusting a run and confirming the file is restored
  byte-identical. A `\n` search string against these CRLF files silently matches nothing.
- **Browser**, isolated database, explicit `MEDICAL_SERVICE_TEST_DB`, never port 5000: submit and
  recall one request in each of the five modules as a real seeded requester; confirm the Recall
  button is absent on Draft and Approved rows and absent on another user's rows. Standing bar: no
  horizontal overflow at 375 px, no tap target under 44 px, console clean. **Restart the server after
  every template edit** — Jinja caches compiled templates — and unregister the service worker and
  clear both caches after each asset edit, not once.
- Full suite via the documented command as **its own step before the commit**, never chained ahead of
  `git push`.

### After implementation

Review against this plan before committing and correct this record where the outcome differed. Then
the standing checklist in `pending-work.md` section 4: `git fetch origin`, re-read `origin/main`
**after** the work, stage file by file, never `git add -A`, keep `scheduler.db` out by name, confirm
with `git show --name-only`, push `main`. Add the `changes.md` entry in the same task.

### Risks

**The one that matters: recalling a request an approver is acting on.** Approve and recall both read
then write `status`. Without the `status == 'Submitted'` check inside the same transaction as the
write, a recall can land on a just-approved request and quietly un-approve it — after the approval
emails and calendar blocks have already fired. The net is step 3's 409, the same guard
`reject_reimbursement` already relies on, plus the explicit test that recalling an `Approved` record
is refused.

**Second: destroying a superadmin's provisional leave plot.** Step 5 exists for this. A flat `Draft`
destination would delete calendar blocks somebody else created, and the deletion would look like
correct behaviour. The positive control in Verification is what separates "blocks kept because the
resolver worked" from "blocks kept because the hook never runs".

**Third: five modules, one behaviour.** The registry is the mitigation. If recall logic gets copied
per module instead, the five copies will diverge — exactly what happened to the HR export redaction
and to the permission resolver in the last two reviews. Any per-module difference belongs in a
registry entry, not in a branch inside the endpoint.

## Provisional leave: superadmins plotting leave ahead of approval

**Status:** `Executed — 5c976bb`
**Started:** 2026-08-05, after the project owner gave the execution go-ahead.
**Approved:** 2026-08-05
**Detailed:** 2026-08-05, after tracing the leave approval path, the calendar writer, the
2026-07-21 commit that closed manual leave plotting, and the existing Form-to-Follow mechanism.
**Finished:** 2026-08-05, implementation committed as `5c976bb`; full verification passed and the
 release is ready to push without database or generated-artifact changes.

### Context

A superadmin plotting August needs to block out a week of leave an engineer has already asked for
verbally, while the signed form is still working through approval. Today they cannot: commit
`44cb579` (2026-07-21, "Route current leave entries through leave requests") added a hard 400 in
`/add_shift` for any leave-titled schedule dated today or later, **with no superadmin carve-out**,
and hid the Leave option in the Add Schedule modal for non-past dates.

Three corrections to the premise, established in code:

- **The scenario fails at step 2, not step 4.** The superadmin cannot plot the leave at all.
- **It would also fail at step 3.** `submit_leave_request` blocks on any overlapping calendar
  commitment (`leave_feature.py:810-812`), so the engineer could not submit while a manual block
  sat on those dates. Approval blocks the same way (`leave_feature.py:858-861`).
- **"Manual leave" was never a real type.** `schedule_type='leave'` has never existed. The old
  mechanism set the Shift *title* to a `LEAVE_CATEGORIES` string and created an ordinary
  `schedule_type='service'` row, recognised by string matching. "Same leave type?" would have meant
  comparing free text against `header.leave_type` — and the lists differ: `LEAVE_CATEGORIES`
  (`app.py:1419`) carries Emergency and Paternity Leave, `LEAVE_TYPES` (`leave_feature.py:22`)
  does not.

Intended outcome: the superadmin plots leave from the calendar as before, but what it creates is a
**real provisional leave request** the engineer then completes and signs — so in the normal case
there is one record from start to finish and nothing to reconcile.

### Decisions taken

| Decision | Value |
| --- | --- |
| Entry point | The Add Schedule modal's **Leave** category, as before |
| What it creates | A **provisional `LeaveRequest`** for the engineer, not a bare titled `Shift` |
| Who can do it | **Superadmins only** — `is_superadmin_user()`, not `is_admin_authorized()` |
| Engineer's path | Opens **that same record**, adds reason and signature, submits |
| Approved leave vs a provisional on the same dates | **Approved always wins and is always placed** |
| Different leave type | **Still replaced**, flagged loudly — both types named in the audit, plotter notified |
| Both on the same dates | **Never.** Double-booking on leave is what the conflict detector exists to prevent |

The reasoning on mismatch: a signed, audited, approved document beats a manually typed placeholder.
A type mismatch is not a conflict to resolve on the calendar — it is a signal the plotter guessed
wrong. Blocking approval would leave the engineer's approved leave unrecorded, which is today's
behaviour and the thing being fixed.

The owner initially chose "revive the old calendar Leave option" alongside "the engineer completes
the existing record". Those are incompatible — the old option produces a bare titled `Shift` with
no record to complete — and the conflict was resolved in favour of keeping the familiar **entry
point** while creating a real leave request behind it.

### Investigation

- **The provisional mechanism already exists**, restricted to Sick Leave and to the requester:
  `mark_leave_form_to_follow` (`leave_feature.py:773-794`) sets `provisional_created_by_id` /
  `provisional_created_at` and calls `update_calendar(header, 'Form to Follow')`. The columns this
  plan needs are already on the model (`leave_feature.py:85-87`).
- `update_calendar()` (`leave_feature.py:400-446`) is the calendar writer: one `Shift` per
  **weekday** (weekends excluded by `weekdays()`), `schedule_type='leave_request'`,
  `leave_request_id` set, `group_id = leave-request-{id}`, times from `leave_time_range()` — full
  day 08:00–17:00, half AM 08:00–12:00, half PM 13:00–17:00. It already reconciles
  update-or-delete-obsolete against its **own** rows. Extend it, do not replace it.
- **Leave-owned rows are protected from calendar mutation** — `update_shift` (`app.py:40382`) and
  `delete_shift` (`app.py:41610`) return 409, and `delete_shift_rows_with_cleanup` silently skips
  them (`app.py:41342`). Creating the provisional as a real leave row inherits that protection for
  free; a bare titled Shift would not.
- **Notification asymmetry, and how this plan avoids it.** Deleting through
  `delete_shift_rows_with_cleanup` fires a "Schedule Deleted" email per row, while leave approval
  fires no creation email at all — so a delete-then-create reconciliation would email the engineer
  a deletion with nothing to balance it. `update_calendar()` deletes rows directly and sends
  nothing, so **superseding through `update_calendar` avoids the problem entirely.** Do not route
  this through `delete_shift_rows_with_cleanup`.
- `submit_leave_request` requires `header.user_id == current_user.id` (`leave_feature.py:805`) and
  `editable(header)` (`leave_feature.py:800`, `EDITABLE_STATUSES` at `leave_feature.py:25`). So the
  provisional must be owned by the **engineer's** user account with the superadmin recorded only in
  `provisional_created_by_id`, and its status must be editable.
- `conflicts()` (`leave_feature.py:356-398`) takes `exclude_leave_id`, so a request is never
  blocked by its own calendar rows. That is what makes the single-record flow work without touching
  the conflict logic.
- `save_leave_request` refuses to create for another engineer (`leave_feature.py:719-721`) — the
  provisional needs its own route rather than a carve-out there.

### Execution steps

1. **Add a `Provisional` status.** Add it to `EDITABLE_STATUSES` (`leave_feature.py:25`) so the
   engineer can complete and submit it, and to the pending buckets at `leave_feature.py:679` and
   `687`. **Do not reuse `'Form to Follow'`** — that means "emergency Sick Leave, signed form
   coming" and sets `emergency_form_to_follow`, which changes reject behaviour
   (`leave_feature.py:897`). Conflating them would make rejection behave differently for reasons
   nobody could trace. Done: a Provisional request is editable and appears in the engineer's
   pending list.

2. **Add `POST /api/leave-requests/provisional`** in `leave_feature.py`, guarded by
   `is_superadmin_user()`. Takes engineer_id, leave_type, start/end date, duration/half-day period,
   and optional `verbal_approval_notes`. Creates a `LeaveRequest` with `user_id` = **the engineer's
   linked User**, `engineer_id` = their profile, `status='Provisional'`,
   `provisional_created_by_id = current_user.id`, `provisional_created_at = now`, and a
   `request_no` from `request_number()`. **Refuse if the engineer has no linked user account** —
   otherwise nobody can ever sign it. Then `update_calendar(header, 'Pending Approval')`, which
   already maps to that Shift status (`leave_feature.py:407-410`) so no calendar-side change is
   needed. Audit, notify the engineer, `ActivityLog`. Done: a superadmin creates a typed, protected
   leave block plus a record the engineer can sign.

3. **Keep `/add_shift`'s leave block exactly as it is.** The modal routes Leave to the new endpoint
   instead. That block correctly prevents untyped title-matched leave rows and should not be
   reopened — reviving it is what would bring back free-text type matching. Done:
   `block_new_calendar_leave_for_current_or_future` is untouched and still returns 400 for
   everyone.

4. **Re-enable the modal's Leave option for superadmins.** In `updateLegacyLeaveOptionForDate()`
   (`templates/timeline.html:12524-12540`) add a superadmin branch to `allowLegacyLeave`. When
   Leave is selected and the user is superadmin, the save path posts to the new endpoint rather
   than `/add_shift`, and the form requires **exactly one** engineer — a leave request belongs to
   one person, and the modal otherwise allows several. Done: a superadmin picks Leave for a future
   date and it saves; everyone else sees the option hidden as now.

5. **Let a provisional be superseded rather than block.** In `conflicts()`
   (`leave_feature.py:356`) classify an overlapping `Provisional` request for the same engineer
   into a new `supersedable_provisionals` bucket instead of `overlapping_leave_requests`, and leave
   its `Shift` rows out of `blocking_schedules`. Submit and approve keep blocking on everything
   else. Done: an engineer who files their own request can still submit and be approved over their
   own provisional.

6. **Supersede on approval.** In `approve_leave_request` (`leave_feature.py:849-881`), after the
   header is marked Approved and **before** `update_calendar(header, 'Approved')`, resolve any
   supersedable provisional: set its status to `'Superseded'`, record the approved request's id on
   it, and clear its calendar rows via `update_calendar` on that header with an empty expected
   range — **not** `delete_shift_rows_with_cleanup`, per the notification finding. Ordering is
   load-bearing: clear the provisional's rows first, or the approved request's rows collide with
   them on the same dates. Done: the approved leave lands and the provisional's blocks are gone.

7. **Flag a type mismatch loudly.** When the superseded provisional's `leave_type` differs from the
   approved request's, write an audit entry naming **both** types, and `create_system_notification`
   to `provisional_created_by_id` saying which dates changed and from what to what. A matching type
   gets a quieter audit line and no notification. Never block either way.

8. **Release plumbing.** `releases.json` entry dated the commit date or
   `test_changelog_coverage.py` fails. `templates/timeline.html` **is** an `APP_SHELL` route
   (`app.py:14593`), so this **does** need a service worker bump — currently
   `v64-hr-schedule-viewer`; **read the live value out of `app.py` immediately before committing**
   rather than trusting this line.

### Deliberately excluded

- **Reviving the untyped title-matched leave row.** The entry point is restored; the mechanism
  behind it is not. Free-text titles as a type system is what made "is it the same leave type?"
  unanswerable in the first place.
- **Schedulers and regional admins plotting leave.** Superadmins only, per the decision. Widening
  it later is a one-line predicate change.
- **Cancelling or un-approving an approved leave.** No such route exists today
  (`reject_leave_request` only accepts `Submitted`), and adding one is its own task with its own
  calendar and HR-email consequences.
- **Reconciling the two leave-type lists.** `LEAVE_CATEGORIES` (`app.py:1419`) and `LEAVE_TYPES`
  (`leave_feature.py:22`) disagree, and `classify_schedule_type` still buckets by title string
  (`app.py:35211`). Real inconsistency, pre-existing, and off this path once the provisional
  carries a proper `leave_type`.
- **Leave balance accounting.** Nothing tracks entitlement or deducts days, so a type change has no
  balance to correct.

### Verification

- **Drive the owner's scenario end to end, by calling it**: superadmin plots a one-week VL
  provisional; assert the calendar carries five weekday blocks with `schedule_type='leave_request'`
  and `leave_request_id` set, and **not** a `service` row. The engineer opens the same record, adds
  a reason and signature, and **submits successfully** — the assertion that proves the
  single-record flow, since submit blocks on conflicts today and must not block on its own rows.
  Approve and assert the blocks survive with status Approved.
- **The mismatch path**: superadmin plots VL, engineer files a *separate* SL request, approve it.
  Assert the SL blocks are placed, the VL provisional is `Superseded` with **zero** remaining Shift
  rows, and **exactly one** set of blocks exists for those dates — the no-double-booking assertion.
  Assert the audit names both leave types and a notification reached `provisional_created_by_id`.
  Positive control: the same flow with matching types supersedes too but sends **no** mismatch
  notification, so that assertion is reading the mismatch branch rather than firing unconditionally.
- **Assert no "Schedule Deleted" email fires** during supersede — the specific asymmetry
  `delete_shift_rows_with_cleanup` would have introduced.
- **Assert a non-superadmin is refused** the provisional endpoint (403) and still sees the Leave
  option hidden. Positive control: the superadmin succeeds on the identical request.
- Assert `/add_shift` still returns 400 for a leave-titled future schedule for everyone, proving
  step 3 left that path closed.
- **Prove each new test fails without its fix**, injecting one defect at a time, **verifying the
  injection applied by SHA** before trusting a run and confirming the file is restored
  byte-identical. A `\n` search string against these CRLF files silently matches nothing.
- **Browser**, isolated database, explicit `MEDICAL_SERVICE_TEST_DB`, never port 5000: plot leave
  from the real modal as a seeded superadmin, sign in as the engineer and complete it, approve as
  the approver. Confirm the leave block cannot be dragged, edited or deleted from the calendar (409,
  inherited from leave-row protection). Standing bar: no horizontal overflow at 375 px, no tap
  target under 44 px, console clean. **Restart the server after every template edit** — Jinja caches
  compiled templates — and unregister the service worker and clear both caches after each asset
  edit, not once.
- Full suite via the documented command as **its own step before the commit**, never chained ahead
  of `git push`.

### After implementation

Review against this plan before committing and correct this record where the outcome differed. Then
the standing checklist in `pending-work.md` section 4: `git fetch origin`, re-read `origin/main`
**after** the work, stage file by file, never `git add -A`, keep `scheduler.db` out by name, confirm
with `git show --name-only`, push `main`. Add the `changes.md` entry in the same task.

### Risks

**The one that matters: two sets of leave blocks on the same dates.** If step 6's ordering is wrong
— the approved request's rows written before the provisional's are cleared — the engineer is
double-booked on leave, which is exactly the outcome every decision here was made to prevent. The
net is the "exactly one set of blocks" assertion, which fails loudly rather than leaving a
plausible-looking calendar.

**Second: a provisional nobody can sign.** If the target engineer has no linked `User`, the record
is created, blocks the calendar, and can never be submitted or approved — a permanent phantom. Step
2 refuses up front for that reason.

**Third: `Provisional` is a new status in a module that branches on status in several places.**
`EDITABLE_STATUSES`, `ACTIVE_CONFLICT_STATUSES`, the queue buckets and the UI status rendering all
enumerate statuses. Sweep for `status ==` and `status.in_` in `leave_feature.py` before relying on
it; a status that is editable but missing from `ACTIVE_CONFLICT_STATUSES` would stop blocking
double-booking elsewhere.

## Staff type and permission tickboxes on Add Personnel

**Status:** `Executed — 4516c89`
**Approved:** 2026-08-05
**Detailed:** 2026-08-05, after reviewing the HR schedule viewer commits and tracing the
account-creation path against the Settings permission handler.

### Context

Permissions are edited in one place today — the Settings approval-user card: approver-only, HR
Schedule View, Stock Inventory, branch. But accounts are *created* somewhere else entirely, on
the Personnel page, with no permissions at all. So adding a person is always two screens and a
context switch, and the second half is easy to forget.

The owner asked for permission tickboxes on the Add Personnel form. Investigation turned up
three reasons it cannot be only that.

**It would be a privilege escalation as stated.** `add_engineer` (`app.py:41648`) gates on
`is_admin_authorized()` — superadmin **or** regional admin. `settings_update_approval_user`
(`app.py:16373`) gates on `is_superadmin_user()` — superadmin only. Tickboxes on the add form
would let the regional admin grant permissions the Settings screen refuses them.

**The HR tickbox would be a guaranteed no-op there.** `add_engineer` always creates
`role='engineer'` **and** an `Engineer` row (`app.py:41664-41682`). `is_hr_schedule_only_user`
(`app.py:4964`) requires `not has_engineer_profile`. An HR person created through that form gets
the flag and no restriction, no redaction, no stripped nav. `test_hr_flag_does_not_strip_an_
engineer_profile_account` pins that as intended behaviour, so the tickbox would silently grant
nothing.

**And the existing design already contradicts itself here.** `is_hr_schedule_engineer_profile`
(`app.py:4981`, from `2ff9181`) exists to hide HR staff from the calendar roster, which assumes
HR people *have* `Engineer` rows. But having one disables the HR restriction entirely. Both
cannot be right.

The root cause under all three: **Add Personnel only knows how to make engineers, and HR staff
are not engineers.** Intended outcome — one screen creates the right kind of account with the
right permissions, and the HR view actually applies to the people it was built for.

### Decisions taken

| Decision | Value |
| --- | --- |
| Staff type on the add form | **Engineer / HR / Approver.** HR and Approver get **no `Engineer` row** |
| Who sees the permission tickboxes | **Superadmin only**, matching Settings. Regional admins keep adding personnel, without them |
| Editing an existing person | **Not in scope.** Settings stays the place to change permissions after the fact |
| Where non-engineer staff appear | **The Settings user list only.** Personnel stays the technical roster |

### Investigation

- `add_engineer` (`app.py:41644-41691`) hardcodes `role='engineer'`, derives the username from
  the first name with a collision fallback (`app.py:41656-41658`), issues a temp password with
  `must_change_password=True`, and returns both to the caller. All of that is reusable as-is for
  every staff type; only the role and the `Engineer` row are type-specific.
- `settings_update_approval_user` (`app.py:16471-16510`) is where every permission rule already
  lives: `stock_inventory_only` implies `can_manage_stock_inventory` and turning inventory off
  clears the restricted view (`app.py:16481-16486`); approver-only and inventory are mutually
  exclusive (`app.py:16488`); HR cannot combine with either restricted mode (`app.py:16490`); a
  non-superadmin inventory user needs a branch (`app.py:16492`); and `protected_business_roles`
  (`app.py:16497`) blocks restricted views on managers, schedulers, the developer superadmin and
  the regional admin. **None of this may be re-implemented on the add path.**
- `templates/engineers.html` holds the add/edit modal (`#e-emp-id`, `#e-name`, `#e-initials`,
  `#e-branch`) and the directory table. The directory renders `Engineer` rows only, which is why
  a non-engineer account created here would not appear in it.
- `/engineers_page` and `/settings` are **not** `APP_SHELL` entries (`app.py:14592-14614`), and
  this plan changes no shell asset, so **no service worker bump is required**.

**The failure mode this plan is shaped to avoid** is the one just fixed in `5278df2`: the HR CSV
export leaked the job title because the export built its own cell text instead of calling the
redaction helper. Two places deciding the same thing drifted apart. Permissions written from two
screens is the same shape, with a worse blast radius.

### Execution steps

1. **Extract the permission rules into one resolver.** Add
   `resolve_staff_permission_request(payload, target_user=None)` beside
   `settings_update_approval_user`, returning `(values, error_message)`. Move the whole rule set
   from `app.py:16477-16510` into it unchanged — the implications, the three mutual exclusions,
   the branch requirement, and the `protected_business_roles` checks. Done: the function is the
   only place those rules exist.

2. **Refactor `settings_update_approval_user` to call it**, and change nothing else about that
   route. Done: the existing Settings tests pass untouched, proving the extraction is
   behaviour-preserving. **Run them before writing step 3** — if the refactor changed behaviour,
   find out now and not through the new form.

3. **Add `staff_type` to `add_engineer`**, accepting `engineer` (default), `hr`, `approver`, and
   rejecting anything else. Default must stay `engineer` so existing callers that send no
   `staff_type` keep working byte-for-byte. Per type:
   - `engineer` — exactly today's behaviour, `role='engineer'` plus the `Engineer` row.
   - `hr` — `role='staff'`, `hr_schedule_view=True`, **no `Engineer` row**. (`role='staff'`
     matches the account shape their own HR fixture uses.)
   - `approver` — `role='approver'`, `can_approve_requests=True`, **no `Engineer` row**.

   The `Engineer` row creation becomes conditional; username, temp password and
   `must_change_password` stay shared. Done: three account shapes from one route.

4. **Gate the permission fields on superadmin, and refuse rather than ignore.** Inside
   `add_engineer`, if the payload carries any permission field or a non-default `staff_type` and
   `is_superadmin_user()` is false, return 403 with a message naming the reason. **Silently
   dropping the fields is not acceptable** — a regional admin would believe they had granted
   access. Done: a regional admin can still add an engineer and is refused anything more.

5. **Route the permission payload through step 1's resolver** on the add path, applying the
   returned values to the new `User`. On error, return the resolver's message and **create
   nothing** — no half-made account. Done: an invalid combination fails the same way on both
   screens, with the same wording.

6. **Update the Add Personnel modal** in `templates/engineers.html`: a staff-type select, and the
   permission tickboxes rendered only when the viewer is superadmin. The tickboxes shown must
   follow the selected type — do not offer Stock Inventory branch to an HR account. The edit
   modal is untouched. Done: a superadmin creates a working HR account in one step; a regional
   admin sees the form without the permission block.

7. **Say where the person went.** When a non-engineer account is created, the success message
   must state that the account exists in Settings rather than the Personnel directory, because
   the row will not appear in the table the admin is looking at. Done: no silent disappearance.

8. **Release plumbing.** Add a `releases.json` entry dated the commit date or
   `test_changelog_coverage.py` fails. **No service worker bump** — confirmed above that nothing
   in `APP_SHELL` changes; re-confirm by reading `APP_SHELL` at implementation time rather than
   trusting this line.

### Deliberately excluded

- **Editing permissions from the Personnel page.** Settings remains the single place to change an
  existing account. Adding a second writer for the same fields is the drift risk this plan is
  built to avoid; doing it at creation only means the two paths never compete over one row.
- **Approval routing detail for the Approver type.** `approval_scope` and `approval_title` stay a
  Settings concern. The form creates a working approver account; tuning its routing is a separate
  screen and a separate decision.
- **A non-technical staff section on the Personnel page.** Decided against — Personnel stays the
  deployable roster. Revisit only if managing non-engineer staff from Settings proves awkward.
- **Reworking `is_hr_schedule_engineer_profile`.** With HR accounts no longer carrying `Engineer`
  rows it becomes legacy-only, covering HR people created before this change. Leave it: it is
  correct for those accounts and harmless for new ones. Note it in `changes.md` so the next
  reader knows why it looks redundant.
- **A general create-user UI in Settings.** Still absent, still provisioned in seed code for
  anyone who is not staff. Out of scope here.
- **Employment status and the destructive `delete_engineer` cascade** (`app.py:41645`). Still
  open, still its own task.

### Verification

- **Test the rules through both call sites, by calling them.** For each invalid combination
  (approver-only plus inventory, HR plus either restricted mode, inventory without a branch,
  restricted view on a protected account) assert the **same** rejection from
  `settings_update_approval_user` and from `add_engineer`. Positive control: the valid version of
  each combination succeeds on both, so the assertions cannot pass on a route that rejects
  everything.
- **Assert the escalation is closed by calling as a regional admin:** `add_engineer` with a
  permission field returns 403, and the plain engineer add still returns success. Positive
  control: the identical request as a superadmin succeeds.
- **Assert an HR account created through the form actually gets the restriction** —
  `is_hr_schedule_only_user()` true, no `Engineer` row, `/get_timeline_data` redacted,
  `/export_timeline` redacted. This is the whole point of the staff-type work; without it the
  tickbox is decoration.
- Assert `add_engineer` with **no** `staff_type` produces byte-identical behaviour to today —
  the backward-compatibility guarantee for existing callers.
- **Prove each new test fails without its fix**, injecting one defect at a time, **verifying the
  injection actually applied by SHA** before trusting a run and confirming the file is restored
  byte-identical afterwards. A `\n` search string against these CRLF files silently matches
  nothing and leaves a green suite reading as vacuous.
- **Browser**, isolated database, explicit `MEDICAL_SERVICE_TEST_DB`, never port 5000: as
  superadmin create one account of each type and confirm the engineer appears in the directory
  while HR and approver do not, and appear in the Settings user list instead; sign in as the new
  HR account and confirm the stripped calendar. As regional admin confirm the permission block is
  absent. Standing bar: no horizontal overflow at 375 px, no tap target under 44 px, console
  clean. Restart the server after every template edit — Jinja caches compiled templates.
- Full suite via the documented command as **its own step before the commit**, never chained
  ahead of `git push`.

### After implementation

Review against this plan before committing and correct this record where the outcome differed.
Then the standing checklist in `pending-work.md` section 4: `git fetch origin`, re-read
`origin/main` **after** the work, stage file by file, never `git add -A`, keep `scheduler.db` out
by name, confirm with `git show --name-only`, push `main`. Add the `changes.md` entry in the same
task. Update `pending-work.md` **only if the owner asks**.

### Risks

**The one that matters: the extraction in step 1 changing a permission rule by accident.** It
moves live authorization logic that currently protects manager, scheduler, regional-admin and
superadmin accounts from being handed restricted views. A subtle change there is silent and
affects existing accounts, not just new ones. The net is step 2 — refactor first, run the
existing Settings tests before any new behaviour is added, so a difference surfaces while the
change is still one commit of pure movement.

**Second: a half-created account.** Step 5 must validate before writing anything. `add_engineer`
flushes the `User` before building the `Engineer` row (`app.py:41670-41671`), so a rejection
after that point leaves an account with no personnel record and no way to reach it from the
Personnel page. Validate first, write once.

**Third: `role='staff'` is a new value in a system that branches on `role` in many places.**
`get_display_role` (`app.py:7573`) will fall through to `'Staff'`, which is fine, but sweep for
`role ==` comparisons that assume the closed set before relying on it.

### Outcome

Implemented the approved plan in `app.py`, `templates/engineers.html`,
`static/changelog/releases.json`, `tests/test_staff_creation.py`, `changes.md`, and this plan.
The Settings permission rules now live in `resolve_staff_permission_request()` and are shared by
Settings updates and Add Personnel. The add route accepts Engineer, HR, and Approver staff types;
engineer accounts retain their linked `Engineer` profile, while HR and Approver accounts are
created without one and are directed to Settings for ongoing permission management. Superadmin
controls are visible only to superadmins, and regional administrators are explicitly refused
permission-bearing or non-engineer creation requests instead of having those fields silently
discarded. Validation runs before account creation, so rejected combinations do not leave partial
accounts.

The implementation intentionally corrected two policy edge cases rather than copying the old
resolver literally: inventory-only now implies inventory management as the UI and access model
require, and HR Schedule View rejects approval capability as well as restricted inventory modes.
These deviations are documented in `changes.md` and covered by shared call-site tests.

Verification completed: focused staff tests (7), targeted regressions (38), dashboard regressions
(77), service-worker checks (5), JavaScript extraction, Python compilation, manifest parsing,
`git diff --check`, and the full repository discovery suite (**439 tests passed**). No schema
migration or service-worker bump was needed. `scheduler.db`, `output/`, `outputs/`, `tmp/`, and
the unrelated handoff artifact remain outside the intended change set.

## HR Schedule Viewer — a read-only "who is deployed" account

**Status:** `Executed — 9b6effd`
**Approved:** 2026-08-05
**Detailed:** 2026-08-05, after mapping the schedule write surface, the timeline data feed, the
existing read-only-approver mode, and the `stock_inventory_only` restricted-account pattern.

### Context

Management wants HR to see the system. On investigation the ask is narrower than it sounded:
**HR needs to see who is deployed and when.** Nothing else.

HR already interacts with this system — as an email address. Approving a leave request fires
`send_hr_email_background` to the `leave_request_hr` recipient group (`leave_feature.py:595`),
and the row stores `hr_email_status`. HR works out of an inbox today. This gives them a
read-only window instead.

Two owner decisions shrank the work substantially: **departments are not needed** (they would
have been entirely net-new — no model, column, enum or dropdown exists anywhere in the
codebase), and the **personnel page revision is dropped** as unnecessary for this goal.

Intended outcome: an HR account logs in, sees a calendar and nothing else, can read who is
assigned where and when, and cannot change anything or see client commercial detail.

### Decisions taken

| Decision | Value |
| --- | --- |
| What HR sees per schedule | Engineer, date, time, status, **and client name** — nothing further |
| Nav shape | Schedule only, stripped nav, mirroring `stock_inventory_only` |
| How access is granted | Per-user boolean toggle in Settings, superadmin-controlled |
| Departments | **Not needed at all.** Dropped |
| Personnel model/page revision | Dropped — not required for HR access |

Rejected on the way: a hardcoded username allowlist (matches how manager/scheduler/superadmin
work today, but means a code change and deploy whenever HR staffing changes) and a single shared
HR login (no accountability — the activity log could not say which HR person did what).

### Investigation

**The write surface is already closed, and this is the most important finding.** Every schedule
mutation endpoint gates on `can_create_schedule_for_engineer_ids` (`app.py:7784`),
`can_modify_schedule_for_engineer_ids` (`app.py:7759`), `can_work_on_existing_schedule_shift`
(`app.py:7848`) or `can_submit_update_engineer_ids_for_scope` (`app.py:7863`). All four branch
**only** on `is_superadmin_user`, `is_regional_admin_user` or `role == 'engineer'`, and
**default-return `False`**. A new role never folded into those three is refused by `/add_shift`,
`/update_shift`, `/move_shift`, `/delete_shift`, `/batch_delete_shifts`,
`/preview_delete_shifts`, `/delete_shifts_previewed` and both scheduler quick-actions **without
one line of new guard code**. This plan's job is to not break that, not to build it.

**A read-only timeline mode already exists.** `timeline_read_only_approver` (`app.py:15955`)
feeds `isTimelineReadOnlyApproverMode()` (`templates/timeline.html:8375`), which roughly fifteen
mutation paths short-circuit on. Generalising that one function covers all of them at once.

**The exposure is in the data feed, not the UI.** `/timeline` (`app.py:15938`) and
`/get_timeline_data` (`app.py:34609`) carry **no guard beyond `@login_required`**, and the
per-shift payload (`app.py:34755-34816`) includes `client_address`, `product_name`, `files`,
`file_details` with live `download_url` links to TSR archive files, and travel
purpose/destination/remarks. That payload — not the buttons — is what has to be filtered.

**A second leak path the payload does not show.** The mobile card reads client contact via
`getMobileClientContact` (`templates/timeline.html:10953`), sourced from the page's client master
fetch rather than the timeline payload. Redacting `/get_timeline_data` alone does **not** close
it.

**`timeline_lite`** (`app.py:34768`) already conditionally empties `files` and `file_details` in
this exact dict — the redaction precedent to follow rather than invent.

**The restricted-account shape to copy:** `User.stock_inventory_only` →
`is_stock_inventory_only_user()` (`app.py:4921`) → `inject_feature_flags()` (`app.py:1253`) →
the negative nav gate at `templates/layout.html:144` → plus a route-level redirect in
`dashboard_page()` (`app.py:14826`). All four parts are needed; the template gate alone is not a
boundary.

**What turned out not to be true.** The request arrived as "revise personnel, add departments".
Neither is required. There is no department/division/team/org-unit concept anywhere — the only
`dept_code` in the codebase is an unrelated accounting classification on payment forms, and
`Engineer.branch` is a location, not a department. Separately, `Engineer` carries only 9 columns
with no employment status, and `delete_engineer` (`app.py:41543`) permanently deletes the linked
`User` account — a real gap, but not this task's.

### Execution steps

1. **Add the column and its migration.** `User.hr_schedule_view = db.Column(db.Boolean,
   default=False, nullable=False)` beside the stock-inventory flags (`app.py:1494-1497`). Write
   `ensure_user_hr_schedule_view_column()` following `ensure_shift_creation_token_column()`
   (`app.py:3709`) verbatim in shape: module-level `_ready` global, `PRAGMA table_info(user)`,
   `ALTER TABLE ... ADD COLUMN` only when absent, `[DB MIGRATION]` print. Register it in
   `initialize_database()` (`app.py:42304`) **and** in the `before_request` hook list
   (`app.py:3860`). Done: a live DB without the column gains it on next request.

2. **Add the two permission helpers**, in the authorization block beside the stock-inventory
   ones (~`app.py:4876-4947`):
   - `is_hr_schedule_viewer(user=None)` — authenticated, active, `hr_schedule_view` true.
   - `is_hr_schedule_only_user(user=None)` — the above **and not** `is_superadmin_user`, **and
     not** `is_admin_authorized`, **and not** `has_engineer_profile`. Mirrors
     `is_stock_inventory_only_user()` (`app.py:4921`).

   **Do not touch `is_admin_authorized`, `is_superadmin_user`, `is_scheduler_user`, or any
   `role == 'engineer'` branch.** That untouched default-deny is the entire write protection.
   Done: an HR account returns `False` from all four schedule-modify helpers.

3. **Surface the toggle in Settings.** Add a checkbox to the approval-user-card beside the Stock
   Inventory block (`templates/settings.html:1848-1874`), add the field to the payload in
   `saveApprovalUser` (`templates/settings.html:2020-2030`), and write it in
   `settings_update_approval_user` (`app.py:16364-16439`) next to the
   `can_manage_stock_inventory` write at `app.py:16412`. That handler is already
   `is_superadmin_user`-gated at `app.py:16373` — inherit it, do not add a second gate.
   **Reuse the existing protected-account rule** at `app.py:16401-16406`: managers, schedulers,
   the developer superadmin and the regional admin must not be assignable an HR-only view.
   Done: a superadmin can tick the box and the flag persists.

4. **Redact the feed.** In `/get_timeline_data` (`app.py:34609`) resolve
   `hr_view = is_hr_schedule_viewer()` **once before the shift loop**, then apply a
   `redact_timeline_payload_for_hr(payload)` helper after the dict is built (`app.py:34816`),
   following how `timeline_lite` already branches.

   **Keep:** `id`, `client_name`, `time_start`, `time_end`, `status`, `engineers`,
   `day_owner_engineer_*`, `start_date`, `end_date`, `group_id`, `schedule_type`,
   `is_travel_block` — the last two because the grid cannot render without them.

   **Blank:** `client_address`, `product_name`, `client_id`, `product_id`, `files`,
   `file_details`, `travel_request_no`, `travel_destination`, `travel_purpose`,
   `travel_remarks`, `travel_schedule_suggestions`, `can_open_travel_request`.

   **One judgment call to confirm at review:** `task` is `shift.title`, a free-text job
   description that may carry commercial detail. "Client name, nothing else" was explicit, so
   redact it to a generic label derived from `schedule_type` and raise it with the owner rather
   than deciding silently. Done: an HR session's feed contains no address, contact, product or
   download URL.

5. **Close the second leak path.** Audit every other endpoint `templates/timeline.html` calls on
   load — the client and product masters and `/get_engineers` — and confirm none returns client
   contact fields to an HR account. Either omit those fields server-side for HR or stop the
   mobile card calling `getMobileClientContact` (`templates/timeline.html:10953`) in HR mode.
   Done: a network trace of an HR session contains no client phone, email or contact name.

6. **Generalise the read-only UI mode.** Compute `timeline_read_only_hr` in `timeline_page()`
   beside `timeline_read_only_approver` (`app.py:15955`), thread it into the template next to
   `timelineReadOnlyApprover` (`templates/timeline.html:8364`), and **OR it into
   `isTimelineReadOnlyApproverMode()`** (`templates/timeline.html:8375`) rather than editing its
   ~15 call sites. Rename to `isTimelineReadOnlyMode()` and keep the old name as a one-line
   alias so no call site is missed. Done: every add/edit/drag/delete affordance is inert for HR,
   with the existing view-only toast.

7. **Guard the two routes.** `/timeline` and `/get_timeline_data` currently admit any
   authenticated user. Add an explicit allow-check so HR is admitted deliberately rather than by
   the absence of a check. Done: the guard names HR as permitted instead of relying on the hole
   that already lets approver-only accounts in.

8. **Strip the nav.** Add `hr_schedule_only_user` to `inject_feature_flags()`
   (`app.py:1253-1263`), extend the negative gate at `templates/layout.html:144` so an HR-only
   account keeps only the calendar link, and route `dashboard_page()` (`app.py:14826`) for HR the
   way it already special-cases stock-inventory-only accounts. Done: HR's sidebar is the calendar
   and a password link.

9. **Release plumbing.** Bump `CACHE_VERSION` — **read the live value out of `app.py:14518`
   immediately before committing**; `layout.html` is embedded in every `APP_SHELL` page, so a
   stale shell would keep rendering the old sidebar. Add a `releases.json` entry dated the commit
   date, `audiences: ["admins"]`, or `test_changelog_coverage.py` fails the commit.

### Deliberately excluded

- **Departments, and any `Engineer` schema change.** Settled by the owner as not needed. Adding
  an org-unit concept is net-new schema for no requirement this task carries.
- **The personnel page revision.** Dropped by the owner as unnecessary here.
- **Leave, reimbursements, personnel directory and TSR files for HR.** HR asked for schedules.
  Each of the others is its own authorization surface and its own decision.
- **A create-user UI.** None exists — accounts are provisioned in seed code (`app.py:4683`,
  `4722`, `41472`). The HR account will need creating the same way. Worth raising as its own
  task; not built here.
- **Fixing `/timeline`'s pre-existing openness for approver-only accounts.** Step 7 adds a
  deliberate guard for this path; auditing every other ungated route is separate work.
- **Employment status on `Engineer`, and the destructive `delete_engineer` cascade.** Real gaps
  found during investigation, deliberately not widened into. Their own task.

### Verification

- **Prove the write surface by calling it, not by reading it.** The standing rule after
  `test_stock_inventory.py` pinned a source line that a safe refactor then broke. Build an HR
  user, hit `/add_shift`, `/update_shift`, `/move_shift`, `/delete_shift`,
  `/batch_delete_shifts`, `/preview_delete_shifts`, `/delete_shifts_previewed` and both scheduler
  quick-actions, and **assert 403 on every one**. Positive control: the same requests from a
  seeded engineer/admin succeed, so the assertions cannot pass on a broken fixture.
- **Assert the redaction on the response body**, not the helper: an HR session's
  `/get_timeline_data` JSON contains no `client_address`, `product_name`, `download_url` or
  travel purpose, **and still contains `client_name` and the engineer assignment**. Positive
  control: the same request as an admin does contain them.
- Assert `is_hr_schedule_only_user()` is false for a superadmin, an admin and an engineer, so the
  flag can never strip an existing account's nav.
- **Prove each new test fails without its fix**, and **confirm the injection actually applied**
  (print whether the replacement changed the text, or compare a hash) before trusting a green
  run. A `\n` search string against these CRLF files silently does nothing and reads as "the
  tests are vacuous".
- **Browser**, on an isolated database with an explicit `MEDICAL_SERVICE_TEST_DB`, never port
  5000, signed in as a real seeded HR account: sidebar shows the calendar only; the grid renders
  with engineer, date, time, status and client name; no add/edit/drag/delete affordance responds;
  a network trace shows no client contact detail or TSR download URL anywhere. Standing bar: no
  horizontal overflow at 375 px, no tap target under 44 px, console clean.
- Full suite via the documented command, expecting the current 422 plus the new tests, run as
  **its own step before the commit** — `ac78987` reached `origin/main` red because a check was
  chained ahead of `git push`.
- Restart the server after every template edit (Jinja caches compiled templates) and unregister
  the service worker plus clear both caches after **each** asset edit, not once.

### After implementation

Review against this plan before committing; correct this record where the outcome differed. Then
the standing commit checklist in `pending-work.md` section 4: `git fetch origin`, re-read
`origin/main` **after** the work, stage file by file, never `git add -A`, keep `scheduler.db` out
by name, confirm with `git show --name-only`, push `main`. Add the `changes.md` entry in the same
task. Record anything left unverified in `pending-work.md` **only if the owner asks**.

### Risks

**The one that matters: silently widening write access.** If step 2's helpers are ever folded
into `is_admin_authorized` or an engineer branch for convenience, every schedule endpoint opens
to HR at once and nothing visibly breaks. Blast radius is the whole scheduler. The net is the 403
suite above, which fails loudly the moment it happens.

**Second: partial redaction reading as complete.** Step 4 filters the feed, but step 5's client
master is a separate path. Closing one and assuming both would leave contact data visible on
mobile cards specifically — the layout HR is least likely to be checked on. The network trace,
not the payload assertion, is what proves it.

Low risk elsewhere: the column is additive and nullable-safe, the flag defaults false, and no
existing account's behaviour changes until someone ticks the box.

## Engineer Read-Only Stock Inventory Access

**Status:** `Executed — 6d824a5`
**Approved:** 2026-08-03
**Detailed:** 2026-08-03, after review of the existing branch-aware Stock Inventory guards, movement ledger, and sidebar rendering.
**Finished:** 2026-08-03. Implemented and verified locally; main implementation committed as `6d824a5`; no Railway deployment was made.

### Context

Stock Inventory currently uses `can_manage_stock_inventory()` as the single page and API gate. That correctly protects existing inventory operators, but ordinary engineers cannot inspect stock accountability. The requested outcome is a branch-scoped read-only view for engineers, with current borrowings presented first, while preserving every existing write privilege and keeping `scheduler.db` out of the worktree changes.

### Decisions taken

- Preserve explicit inventory-management permission. An engineer who already has `can_manage_stock_inventory` keeps the existing write behavior; an ordinary engineer without that permission receives read-only access.
- Resolve ordinary engineer branch access from the linked `Engineer.branch` profile: Manila/Main to BC01, Cebu to BC02, and Davao to BC03. Missing or unsupported branch data denies access rather than defaulting to BC01.
- Show a first-position Currently Borrowed Items view, followed by the existing item and full movement-history views.
- Derive outstanding borrowings from OUT, Return IN, and correction ledger movements. Do not add a balance column or change the existing inventory schema.

### Investigation

- `app.py:4837-4860` currently defines `can_manage_stock_inventory`, `stock_inventory_branch_for_user`, and superadmin-only administration.
- `app.py:15962-15979` gates `/stock_inventory` exclusively on management access and passes branch/admin state to the template.
- `app.py:50829-51366` uses one API guard for read and mutation endpoints, so the implementation must split read and mutation guards without changing the mutation routes' existing permission semantics.
- `app.py:1740-1770` stores engineer branch values as human labels such as Manila, Cebu, and Davao.
- `templates/layout.html:140-142` renders the Stock Inventory sidebar link only when `stock_inventory_access` is true.
- `templates/stock_inventory.html:115-336` currently renders scanner, item, movement, edit, and reversal controls together and loads movement history through the existing read endpoint.

### Execution steps

1. Update `app.py` access helpers and page context so authorized inventory users retain their current permissions, ordinary engineers gain branch-scoped read access, and missing engineer branches return a clear 403.
2. Split Stock Inventory read and mutation API authorization. Allow branch-scoped GET/read behavior and barcode lookup for engineers; keep item registration, edits, movements, and reversals blocked for read-only engineers, including direct API calls.
3. Add the branch-scoped `GET /api/stock-inventory/borrowed` response. Replay the immutable ledger to return outstanding item, quantity, borrower, timestamp, purpose, and branch data, including correction movements without modifying historical records.
4. Update `templates/layout.html` and `templates/stock_inventory.html` to show the link to engineers, hide write controls for read-only users, keep safe search/history/barcode lookup, and render the borrower panel before the item list.
5. Add focused source, authorization, branch-isolation, borrower-aggregation, and read-only UI tests in `tests/test_stock_inventory.py` or adjacent focused tests. Verify superadmin and explicit inventory-manager regressions.
6. Self-review the diff, run defect-injection checks for branch bypass and mutation authorization, run focused tests and the full suite, perform local browser checks for desktop/mobile/dark mode, bump the service-worker cache from the live value in `app.py`, add a dated `releases.json` entry, and update `changes.md`.

### Deliberately excluded

- No inventory schema migration or new persistent fields.
- No change to existing inventory-user write workflows, superadmin branch switching, quantity adjustments, or reversal rules.
- No automatic checkout/return pairing UI beyond the read-only outstanding-borrowing calculation.
- No database schema/data migration or Railway deployment in this task. Commit and push are handled only after the owner's separate go-ahead.

### Verification

- Ordinary engineer can open Stock Inventory and sees only their Engineer-profile branch.
- Branch query tampering cannot expose another branch.
- Ordinary engineer receives 403 for registration, item edit, movement creation, and reversal APIs.
- Explicit inventory managers and superadmins retain their existing capabilities.
- OUT and Return movements produce correct outstanding borrowing rows; reversals net out without changing history.
- Borrowed panel displays borrower, item, quantity, time, purpose, and branch first; empty state is clear.
- Desktop/mobile layout, scrolling, barcode lookup, search, dark mode, Python compilation, JavaScript checks, focused tests, full suite, and `git diff --check` pass.

### Outcome

- Added the separate read guard and profile-branch precedence without altering mutation authorization.
- Kept superadmin status authoritative for inventory management so an editable user toggle cannot remove a protected superadmin's existing write access.
- Fixed the page route's branch-helper argument so valid engineer viewers reach the branch-scoped page before API loading begins; query tampering remains ignored for them.
- Added the borrowed-items ledger projection and first-position responsive panel; existing item and movement history views remain available.
- Focused Stock Inventory tests passed (12 tests), inline JavaScript parsing passed, and a clean isolated full run passed all 411 tests. A non-isolated run was affected by a reused temporary dashboard fixture database and was not treated as a product regression.
- Updated the service-worker cache and release manifest. No database schema or data migration was performed; commit and push are now authorized by the owner, while Railway deployment remains separate.

### Risks

- Engineer profiles with missing branch values may lose access by design; the denial message and test coverage make the data issue visible rather than exposing BC01 incorrectly.
- Return movements recorded for a different engineer may make borrower-level pairing ambiguous; the ledger replay will reduce matching open loans first and preserve all original movement rows.
- Mutation authorization must remain stricter than read authorization; every mutating endpoint will retain an explicit management guard in addition to the new view guard.

State these explicitly in the plan, with anything plan-specific filled in:

1. **Self-review the diff** before anything else — read it as a reviewer would, not as its author.
2. **Prove the new tests fail without the fix.** Re-inject each defect, watch the test fail,
   restore from an intact copy, and confirm no residue.
3. **Full suite green**, quoting the before and after counts.
4. **Browser verification** of the real user path, against a genuinely stopped server where the
   change touches offline behaviour.
5. **Service worker bump** when a precached asset or template changed — read the live value out
   of `app.py` at commit time, never from a note made earlier in the session.
6. **`releases.json` entry** dated the commit date for anything user-facing.
7. **Update the journals**: `changes.md` for what was done, this file for the status and for
   where the plan and the outcome differed.
8. **Commit and push** against the standing checklist in `pending-work.md` section 4 — explicit
   staging, never `git add -A`, `scheduler.db` excluded by name, re-read `origin/main` after
   finishing rather than only before starting.
9. **Report honestly**: what was verified, what was not, and anything found along the way that
   was left alone.

## Reimbursement Package Total Consistency Repair

**Status:** `Executed — aff9001`
**Approved:** 2026-08-03
**Detailed:** 2026-08-03, after reviewing the worksheet total, the reimbursement download audit, and the Excel/PCV/RFP generation paths.
**Finished:** 2026-08-03 in `aff9001`. The verified implementation commit is ready for push; the journal closeout is recorded separately below.

### Context

An engineer reported that a reimbursement worksheet showed approximately PHP 55,241.42 while the downloaded Request for Payment form showed a lower amount. The worksheet is calculated from browser inputs, while generated forms currently recalculate independently from persisted expense columns. The fix must make the saved reimbursement header the single source for all generated outputs without changing existing records destructively or breaking range reuse, row deletion, receipts, automatic LPR reconciliation, approval, or accounting handoff.

### Decisions taken

- Use one backend reimbursement total snapshot for the worksheet reload response, status/history summaries, approval serialization, email context, Excel, PCV, RFP, and accounting package generation.
- Persisted expense columns are authoritative for current rows. A legacy row that has a positive `row_total` but no positive expense-column values is preserved through a controlled fallback into `Others / Misc` for generated outputs.
- Do not mutate historical rows merely because a mismatch is detected. Return explicit consistency metadata so the UI and logs can identify a mismatch instead of silently presenting different totals.
- Resolve downloads by the active `reimbursement_id`; retain the existing date-range lookup only as a compatibility fallback for callers that do not provide an ID.
- Return the server-calculated total after draft save and show it before a package download. Existing locked records, row deletion/restoration, receipts, linked LPRs, and submission cleanup remain unchanged.

### Investigation

- `app.py:19914-19953` defines the reimbursement component fields and currently treats `row_total` as a claimability fallback.
- `app.py:20125-20153`, `app.py:23222-23223`, and `app.py:23309` serialize totals from `row_total`, while `app.py:21188-21213` builds generated-form categories from component fields.
- `app.py:20221-20345` writes Excel rows and totals from component fields; `app.py:20471-20500`, `app.py:20676-20702`, and `app.py:21228-21254` feed PCV/RFP totals from the category helper.
- `app.py:20448-20465` already prefers an exact request `reimbursement_id` and only uses legacy date-range lookup when no ID is supplied.
- `app.py:23400-23560` saves all current component values and returns the header lifecycle, but does not return the authoritative saved total or a consistency warning.
- `templates/reimbursement.html:2131-2170` calculates the visible worksheet total from active inputs, and `templates/reimbursement.html:3553-3660` saves an editable draft before downloading the package. The frontend does not currently display the server-calculated total.
- No destructive live-data or database-file operation is part of this repair. The existing unrelated `scheduler.db`, `output/`, `tmp/`, and handoff artifact worktree changes remain untouched.

### Execution steps

1. Update `app.py` near `REIMBURSEMENT_EXPENSE_FIELDS` with effective row-amount and reimbursement-total snapshot helpers. Done means the helper reports component totals, row-total totals, legacy fallbacks, mismatch rows, category totals, and a serializable warning without mutating rows.
2. Route `reimbursement_expense_category_totals`, reimbursement email context, manager/history/draft serializers, and `reimbursement_row_to_dict` through the snapshot. Done means every API summary and loaded row uses the same effective saved values.
3. Route Excel, PCV, and RFP generation through the effective row/category values. Done means all generated forms and the detailed Excel agree for component-backed rows and preserve row-total-only legacy rows under `Others / Misc`.
4. Extend the draft-save response and frontend `templates/reimbursement.html` state/update functions with the server total summary and mismatch warning. Done means save/download displays the server total and warns when saved data is inconsistent without preventing normal editing or download.
5. Add focused regression tests for component totals, legacy row-total fallback, mismatch metadata, generated RFP/PCV/Excel consistency, exact-ID package selection, and LPR/zero-row compatibility. Done means the tests fail when the new snapshot path is bypassed and pass after restoration.
6. Add the user-facing reimbursement consistency item to `static/changelog/releases.json`; no service-worker bump is required unless verification shows this template is in a precached shell asset. Update `changes.md` in the same task.
7. Self-review the diff before the full suite, run defect-injection checks, compile Python, run focused and isolated full tests, perform a local save/reload/download smoke check, run `git diff --check`, explicitly stage only intended code/journal/manifest/test files, commit, re-read `origin/main`, and push `main`. Never stage `scheduler.db`, `output/`, `outputs/`, or `tmp/`.

### Deliberately excluded

- No database migration, live database replacement, or historical row rewrite.
- No change to reimbursement date-range reuse or claimed-schedule rules.
- No change to package receipt handling, linked LPR ownership, approval routing, or submission lifecycle.
- No change to the official PDF templates, accounting codes, filenames, or the browser worksheet column layout.
- No service-worker cache bump unless the changed asset is actually precached; the modified reimbursement template is served through the authenticated route rather than the current app shell.

### Verification

- Positive controls: component-backed rows generate the same total in the worksheet response, manager response, Excel, PCV, RFP, email context, and downloaded ZIP.
- Legacy control: a row with `row_total=500` and all component fields zero generates PHP 500 under `Others / Misc` rather than disappearing.
- Mismatch control: a row with a nonzero component sum different from `row_total` returns warning metadata and all generated forms use the same component-derived total.
- Exact-record control: two records with the same date range download the explicitly requested ID, not the newest range match.
- Defect injection: temporarily bypass the helper in one generated path, observe the focused consistency test fail, restore the intact implementation, and confirm no source residue.
- Run `python -m py_compile app.py`, focused reimbursement tests, the isolated full suite with its before/after count, JavaScript/template syntax checks, a local browser/API smoke path where available, and `git diff --check`.

### Outcome

- Implemented the shared non-mutating reimbursement total snapshot and routed worksheet reloads, status/history responses, approval serialization, email context, Excel, PCV, RFP, accounting ZIP output, and receipt-divider row totals through it.
- Preserved positive legacy `row_total`-only rows under Others / Misc without rewriting historical rows. Nonzero mismatches now remain visible through response metadata, activity output, and the reopened-draft warning while generated documents use the saved component columns consistently.
- Verified with the focused reimbursement/range/LPR suite (14/14), a fresh isolated full suite (415 passed, 1 existing skip), Python compilation, inline JavaScript parsing, manifest parsing, exact-ID API/package smoke, generated artifact checks, defect injection, and `git diff --check`.
- No database migration, live database operation, service-worker change, historical rewrite, or artifact cleanup was performed. The implementation commit is `aff9001`.

### Risks

- Legacy rows with only `row_total` could otherwise disappear from accounting forms; the fallback preserves them without changing the database.
- Genuine nonzero component/row-total mismatches may represent stale or manually inconsistent data. The repair makes the discrepancy visible and keeps every generated output consistent, but does not guess which historical value should be edited.
- The package download is a high-blast-radius path, so exact-ID resolution and focused artifact-total tests are required before release.

---

## A — Give schedule options an identity that does not depend on list position

**Status:** `Executed`
**Approved:** 2026-08-01
**Detailed:** 2026-08-01, on the owner's instruction to plan it carefully against the constraint
that **the workflow must not be affected once this is live**. That pass changed the plan
materially — see "What the detailed pass changed" below.
**Finished:** 2026-08-01 in `515698f`. See `changes.md` under 2026-08-01.

**Where the plan and the outcome differed:**

- **Nothing was cut, and one thing was added:** `draftMatchesSelectedStandaloneSchedule` needed
  the helper too. It compares persisted values on *both* sides, so a pre-change draft would have
  been filtered out of the drafts panel and looked lost.
- **A positive control written during the pending-schedule work fired as designed.**
  `test_the_option_identity_still_depends_on_index` asserted identity *was* index-derived,
  specifically so that changing it would fail loudly and force the append rule to be revisited
  rather than silently kept. It was replaced by its successor, and the in-code comment
  justifying the append was corrected — appending is now ordering only, not a correctness
  guard.
- **The upgrade path was verified against drafts written by the old code**, captured before any
  edit because that state cannot be recreated afterwards. All three legacy shapes were covered,
  including the two that deliberately do not resolve.
- **Not covered:** an engineer who picks a schedule while a draft awaits a re-pick and then
  abandons it without saving. The flag simply resets; nothing is lost.
**Raised by:** the offline audit, after this exact defect reached the field.

### Owner's decisions

1. An unmatched draft **keeps the engineer's work** and asks them to re-pick the schedule. It
   never silently guesses which schedule was meant.
2. The old identity format stays understood **permanently**. Drafts sit on field devices for
   months, and the server keeps returning old-format ids through the revision path, so there is
   no safe date to remove it.
3. Straight to live, **verified against drafts saved under the old format first**.

### Context

`normalizeStandaloneScheduleOptions` (`templates/offline_tsr.html:1390`) stamps every picker
option with `_offline_uid = getStandaloneScheduleRuntimeId(schedule, index)` — **derived from
the option's position in the array**. That string is the identity a saved TSR draft stores in
`selectedScheduleId` and later matches on, so anything that changes list composition renumbers
every option after it and detaches drafts from their schedules.

It has already caused one field incident: the pending-schedule merge prepended queued schedules,
`4821::2026-07-31::09:00-11:00::0` became `...::2`, and a draft stopped matching its own
schedule (fixed in `e12a439` by appending). **Appending only made it rarer.** A schedule added
or removed server-side, a queued schedule syncing away, or a different week loading still
renumbers everything after the change.

Today the damage is usually absorbed: `getSelectedStandaloneSchedule` (`:2434`) falls back to
the draft's `selectedSchedule` snapshot, which normally carries the right id. The failure is
therefore quiet and intermittent, which is precisely why it should not be left.

**Intended outcome:** an option's identity is a function of the schedule, not of where it
happens to sit in an array, and drafts saved under the old scheme still resolve.

### What the change touches

Identity is **produced** in three places and **consumed** through one function, which is what
makes this contained:

| Produced | Line |
| --- | --- |
| `normalizeStandaloneScheduleOptions` — every option, from the array index | `:1390` |
| `ensureStandaloneScheduleOptionFromContext` — uses `standaloneScheduleOptions.length` | `:1357` |
| `readPendingScheduleOptions` — `pending::<token>::<date>::<i>`, already content-derived | `:1528` |

Every consumer goes through `getStandaloneScheduleRuntimeId` (`:1209`), which returns
`_offline_uid` when present — so fixing the producers fixes all eleven call sites without
touching them: `:1421`, `:1654`, `:1655`, `:1692`, `:1697`, `:1701`, `:1788`, `:1800`, `:1921`,
`:1972`, `:2434`, `:2837`, `:3053`, `:6956`.

### The scheme

New `buildStableScheduleOptionUid(schedule)`, used by all three producers:

- **Real server schedule** → `shift::<id>::<date_iso>`. The date is included because a
  multi-day chain shares one shift id per row in some sources, and a TSR is written for a day.
- **Queued offline schedule** → `pending::<creation_token>::<date_iso>` — what
  `readPendingScheduleOptions` already does, minus the trailing index.
- **Snapshot-sourced entry with no id** → `snap::<hash>` where the hash is a stable digest of
  `client_id|product_id|date_iso|time_start|time_end|task`, lower-cased and trimmed. Same
  inputs as the existing `getStandaloneScheduleGroupKey` (`:1393`), so it is already the
  project's notion of "the same schedule".

**Accepted collision:** two genuinely identical entries — same client, product, date and times —
collapse to one uid. They are interchangeable for writing a TSR, and today they already collapse
in `getStandaloneScheduleGroupKey`. Recording it here so it is a decision, not a surprise.

### What the detailed pass changed

Three findings, and the first one is the whole answer to "will the workflow be affected":

- **The real risk is data loss, not mismatching.** `applyScheduleToStandaloneTSR` (`:1921`)
  compares the computed uid against the stored one and, when they differ, calls
  `clearStandaloneTSRWorkFieldsForScheduleChange()` and wipes `standaloneCurrentDraftId`. Swap
  the identity function naively and that fires for **every** engineer on their first schedule
  re-selection, erasing typed TSR content. This single line governs the blast radius.
- **The options localStorage cache does not persist `_offline_uid`.**
  `cacheStandaloneScheduleOptions` is only ever called with raw server/snapshot arrays, before
  `normalizeStandaloneScheduleOptions` runs, so uids are recomputed on every page load. But
  draft, queue and server `payload_json` records **do** freeze a `selectedSchedule` snapshot
  carrying the old uid, and `getStandaloneScheduleRuntimeId` returns `_offline_uid` first
  (`:1211`) — so a rehydrated snapshot yields the stale value.
- **A stale id can never mis-file a TSR.** The server's `clean_int` returns `None` for
  `12::2026-08-01::09:00-11:00::0`, so the worst case is the 400 that is already handled, never a
  report saved against the wrong shift. That bounds the whole change.

### Always compute, never trust a stored uid

`getStandaloneScheduleRuntimeId(schedule)` drops both the `_offline_uid` early return and the
`index` parameter, delegating to `buildStableScheduleOptionUid`. This is what neutralises the
frozen-snapshot problem: a snapshot rehydrated from a draft now yields the new canonical uid
because it is computed from the schedule's own fields. `normalizeStandaloneScheduleOptions` and
`ensureStandaloneScheduleOptionFromContext` (`:1357`, which also uses
`standaloneScheduleOptions.length` today) stop passing an index.

### One comparison helper, used everywhere stored meets computed

New `isSameScheduleSelection(storedId, schedule)`, true when any of: the canonical uid matches;
`storedId === String(schedule.id)` (the existing real-id arm at `:2434`); or the **legacy** case —
`storedId` contains `::` and its first segment equals `getStandaloneScheduleRealId(schedule)`, or
is `pending` with a matching token, with the old second segment matching the date when present.

Apply it only where the other side can be a *persisted* value: `:1655`, `:1692`, `:1697`, `:1921`,
`:2434`, `:2837`, `:3053`. The remaining call sites compare freshly rendered values within one
pass and need no change. `:6956` looks unreachable but was not proven so — route it through the
helper rather than special-casing it.

### Self-healing, with no bulk rewrite

Whenever a stored selection resolves — draft open, revision load — set
`selectedStandaloneScheduleId` to the **canonical** uid immediately, so the next save persists the
new format and devices migrate as they are used. Do **not** rewrite stored drafts in bulk:
matching is reversible, editing every draft on a device is not.

### Protecting in-progress work — the part that must be right

- `:1922` becomes `if(!isSameScheduleSelection(selectedStandaloneScheduleId, schedule))`, so a
  legacy id referring to the same schedule no longer reads as a change and nothing is cleared.
- When a draft's stored selection resolves to **nothing**, clear the selection, leave every field
  untouched, and ask the engineer to pick the schedule again. `updateCreateTSRScheduleGate`
  disables the fields but they keep their values.
- Set a module flag while that draft awaits a re-pick, and have `applyScheduleToStandaloneTSR`
  skip `clearStandaloneTSRWorkFieldsForScheduleChange()` once for that selection. **Without this
  the re-pick itself wipes the work just preserved**, because the selection moves from `''` to a
  real uid and that reads as a schedule change.

### Deliberately excluded

- **Changing what a draft stores.** Only how a stored value is matched.
- **Rewriting `resolveStandaloneTSRDraftId`.** `_draft_id` short-circuits on reopen, so existing
  drafts keep their key; only a pending-schedule draft saved fresh gets the new key shape.
- **Server changes.** `clean_int` already refuses composites.
- **Touching the offline schedule queue's own identity.** Its key is the creation token and it
  has never been position-derived.
- **Deduplicating the picker.** Tempting alongside a content hash, and a separate decision.

### Verification

New tests in `tests/test_offline_resilience.py`, in the house style with positive controls:

- **The identity is stable under reordering** — build an option list, capture the uids, insert
  an entry at the front, and assert every original uid is unchanged. Positive control: the same
  assertion against the old index-derived function must fail.
- **The three producers agree** — a real schedule, a queued one and a snapshot entry each
  produce the documented shape, and `normalizeStandaloneScheduleOptions` no longer passes an
  index.
- **A legacy draft still resolves** — an old `4821::2026-07-31::09:00-11:00::0` value finds the
  option whose real id is `4821`. Positive control: a legacy value whose id is not in the list
  must still fall through to the snapshot rather than matching something else.
- **A legacy value never matches the wrong schedule** — two options sharing a date but not an
  id; the old-format value must resolve to the one whose id matches, or to nothing.
- Source assertion: `getStandaloneScheduleRuntimeId` is no longer called with an index argument
  anywhere.

- **The work-field guard does not fire for a legacy id of the same schedule** — the regression
  that would erase typed content, and the single most important assertion in the set.

**Browser, and this is the test that decides whether it ships.** Isolated database, port 5056,
never 5000, as a real seeded engineer:

1. **On the current code**, save two drafts — one against a normal schedule, one against a queued
   offline schedule — and confirm the old-format ids are in IndexedDB. This snapshot of "before"
   is the only way to test the upgrade honestly, and it cannot be recreated afterwards.
2. Switch to the new code, restart the server (Jinja caches compiled templates), unregister the
   worker and clear **both** caches.
3. Reopen each draft: it must select its own schedule, keep every typed field, and save.
4. Re-pick the schedule on an open draft and confirm the work is **not** cleared.
5. Force an unmatched draft by editing its stored id to a dead one: work preserved, prompt shown,
   re-pick, then save — with no field wiped at any point.
6. Reorder the list for real — queue a schedule so a pending option appears, then sync it so it
   disappears — and confirm an open draft still matches throughout.

Bump the service worker; `/offline-tsr` is precached.

### Risks worth stating

- **This changes the identity of every option on every device at once.** The legacy read path is
  the whole safety net, and it is the part to test hardest.
- The old scheme's first segment is only the shift id *when the schedule had one*. Entries that
  fell back to `client_id` or `client_name` produce a legacy value that cannot be resolved by id
  and will land on the snapshot — the same place they land today.

---

## B — Decide the offline TSR queue's storage strategy

**Status:** `Executed`
**Approved:** 2026-08-01
**Decision made:** 2026-08-01. The question this plan was blocked on is answered below, and the
owner improved the answer — the failure is framed as "saved as a draft" rather than "cannot
save".
**Finished:** 2026-08-02. Implemented by Codex, reviewed and completed here. See `changes.md`
under 2026-08-02.

**Where the plan and the outcome differed:**

- **The implementation was reported as verified when it was not.** Static checks and a green
  suite were done; the plan's browser sequence and the defect-injection step were skipped. Both
  were run at review, and the code passed — but "verification completed" in `changes.md` was
  corrected to say what had actually happened at each point.
- **Two defects were found at review and fixed**, neither of which the plan anticipated:
  `navigator.storage.estimate()` ran on every draft autosave, and the legacy queue backup was
  removed unconditionally even though the load path reads it to migrate it — on a device whose
  IndexedDB came up empty, a write before a load would have discarded the only copy.
- **Migration held.** `resolveQueuedPDFBlob` and `resolveQueuedAttachmentBlob` still fall back
  to the legacy `pdf_data_url` / `data_url`, so a TSR queued before this change can still be
  sent. Worth recording because it was the most likely thing to have been missed.
- **A review method worth reusing:** the first defect-injection attempt silently no-oped because
  the search strings used `\n` against a CRLF file, and the tests passed — which would have read
  as "the tests are vacuous". Always confirm the injection actually applied before trusting what
  the test run says.
**Rewritten:** 2026-08-01 to the required structure — investigation, numbered execution steps,
and the after-implementation workflow. This is the first plan written to that rule.

### Context

`writeOfflineTSRQueueLocalStorageFallback` (`templates/offline_tsr.html:3267`) serialises the
whole queue and writes it to **two** localStorage keys, and
`prepareOfflineTSRQueueItemBlobs` (`:3473`) keeps the base64 `pdf_data_url` on the record when
the IndexedDB blob write fails. So the same multi-megabyte payload is written twice into a
5–10 MB store — precisely when storage is already under pressure, which is the condition that
made the blob write fail in the first place.

`normalizeOfflineTSRQueue` (`:4109`) does not strip heavy fields, so nothing else prevents it.

### The decision, now made

Stripping the PDF from the localStorage mirror is the obvious move, and it is wrong on its own:
**the mirror is the only copy when IndexedDB is unavailable**, which is exactly the case the
fallback exists to serve. The question this plan was blocked on was therefore:

> Is a TSR queued on a device with no working blob storage worth keeping at all, or should that
> device refuse and tell the engineer to stay online?

**Decision: refuse the send, never the typing — and frame it as a draft, not a failure.** The
owner's improvement on the original recommendation, and it is the better design: "cannot save"
is a dead end for someone standing in a hospital corridor, while "it is saved as a draft" is a
next step. The engineer is not asked to perform the recovery; the draft is saved for them and
they are told it is done.

**Sending and drafting are different weights, and that is what makes this safe.** A draft holds
the typed fields, the signatures and any attachments; the PDF is generated only at final save.
Confirmed against a real captured draft during the plan A work: it contained the field values
and signature slots and **no PDF at all**. So refusing the send costs the engineer nothing they
have typed.

### What the engineer sees

1. The send cannot complete, so the draft is saved automatically first.
2. Draft saved → *"No connection right now, so this TSR could not be sent. It's saved as a draft
   on this device — open it from Continue Saved Work and send it when you're back in signal."*
3. **Draft also failed** → say so plainly and offer the escape hatch (download the PDF now, keep
   the tab open). This is the only case where work is genuinely at risk, and it is the one place
   a reassuring message would be a lie. The entire reason for this work is that the app used to
   imply things were saved when they were not.

Order matters: try the draft, then report what actually happened. Never print the calm message
without having confirmed the draft write succeeded.

### Investigation — verified in the source

| Fact | Where |
| --- | --- |
| The whole queue is serialised and written to **two** localStorage keys | `writeOfflineTSRQueueLocalStorageFallback`, `offline_tsr.html:3369`; `OFFLINE_TSR_QUEUE_BACKUP_KEY`, `:2698` |
| The base64 PDF is **kept on the record** when the IndexedDB blob write fails | `prepareOfflineTSRQueueItemBlobs`, `:3567` — the `catch` keeps `pdf_data_url` |
| Nothing strips heavy fields before the mirror is written | `normalizeOfflineTSRQueue`, `:4223` |
| A draft stores the **whole payload**, including `attachments` | `buildOfflineTSRDraftRecord`, `:2953` |
| Each photo is held as a base64 data URL | `fileToQueuedAttachment`, `:2542` |
| The draft localStorage fallback writes that whole payload | `saveStandaloneTSRDraftToLocalStorageFallback`, `:3024`; `STANDALONE_TSR_KEY`, `:503` |
| Queue items already have a working blob path to copy | `saveOfflineTSRBlobRecord`, `:3477` |
| A draft carries **no PDF** — confirmed against a real captured draft during the plan A work | `collectTSRData`; PDF is built only at final save |

### Execution steps

1. **Stop the PDF surviving in the queue record.** In `prepareOfflineTSRQueueItemBlobs`
   (`:3567`), the blob-write `catch` must clear `pdf_data_url` and mark the item as having no
   durable PDF, then surface that to the caller instead of degrading quietly.
   *Done when:* a forced blob-write failure returns a record with no base64 payload and a caller
   can tell it failed.
2. **Make the localStorage mirror metadata only.** In `writeOfflineTSRQueueLocalStorageFallback`
   (`:3369`), serialise a projection — id, status, tokens, client, product, timestamps, sync
   state, error fields — never `pdf_data_url` or attachment data URLs. Drop the duplicate write
   to `OFFLINE_TSR_QUEUE_BACKUP_KEY` (`:2698`) and delete any value already stored there.
   *Done when:* the two localStorage keys hold kilobytes, and IndexedDB still holds the blobs.
3. **Move draft photos to blob references.** Reuse `saveOfflineTSRBlobRecord` (`:3477`) for
   `payload.attachments` in `buildOfflineTSRDraftRecord` (`:2953`), mirroring what queue items
   already do, and rehydrate on draft open. `saveStandaloneTSRDraftToLocalStorageFallback`
   (`:3024`) writes the projection, never the photos.
   *Done when:* a draft with three photos is kilobytes in localStorage and the photos still come
   back when the draft is reopened.
4. **Draft first, then report — truthfully.** In the final-save failure path in
   `finishStandaloneTSRFinalSave`, attempt `saveStandaloneTSRDraftLocally` (`:3187`) and branch
   on the **actual result**: success gives the calm draft message, failure gives the blunt one
   plus the download-the-PDF escape hatch.
   *Done when:* forcing the draft write to fail produces the blunt message, not the calm one.
5. **Warn before the wall, not after it.** Use `navigator.storage.estimate()` where available to
   warn as the queue grows, keeping the existing "browser storage is full" text as the last
   resort.
   *Done when:* a device near its quota is warned while it can still act.
6. **Cache bump and changelog.** Read `CACHE_VERSION` live out of `app.py` at commit time;
   `/offline-tsr` is precached. Add a `releases.json` entry dated the commit date.

### Deliberately excluded

- Changing the IndexedDB blob layout. It works; this is about the fallback around it.
- The offline schedule queue's attachments — a separate open item, still unverified against a
  real device camera.
- Any change to what the engineer types or how a TSR is composed. This is storage and messaging.

### Verification

Tests in `tests/test_offline_resilience.py`, each with the control that proves it can fail:

- A queue item's localStorage form contains no base64 payload. **Control:** the IndexedDB record
  still does, so the assertion cannot pass by the data having vanished entirely.
- A draft carrying photos stores blob references, not data URLs, with the same control.
- Only one localStorage queue key is written.
- A simulated blob-write failure surfaces rather than degrading silently.
- The calm draft message is only reachable after a successful draft write. **Control:** force the
  draft write to fail and assert the blunt message appears instead — this is the assertion that
  stops the app implying something was saved when it was not.

Browser, isolated database, port 5056, as a real seeded engineer:

1. Queue a TSR normally and confirm the localStorage keys are small while the PDF is in IndexedDB.
2. Attach three photos to a draft; confirm the draft reopens with the photos intact.
3. Force the blob store to fail: confirm the send is refused, the draft is saved, and the calm
   message names it.
4. Force the draft write to fail too: confirm the blunt message and the escape hatch.
5. Standing bar — 375 px with no horizontal overflow, tap targets ≥44 px, console clean.

### After implementation

Follow the workflow in "How to use this file", specifically for this plan:

1. Self-review the diff.
2. Prove each new test fails without its fix, then restore from an intact copy and confirm no
   residue.
3. Full suite green, quoting before and after counts (397 at the time of writing).
4. Browser sequence above, including both forced-failure cases.
5. Service worker bump, read live from `app.py` at commit time.
6. `releases.json` entry dated the commit date.
7. Update `changes.md`, and this plan's status to `Executed` with its commit hash and any place
   the plan and the outcome differed.
8. Commit and push against the `pending-work.md` section 4 checklist — explicit staging,
   `scheduler.db` excluded by name, re-read `origin/main` after finishing.
9. Report what was verified, what was not, and anything found and left alone.

---

## Create a TSR against a schedule that has not synced yet

**Status:** `Executed`
**Approved:** 2026-07-31
**Started:** 2026-08-01, on the owner's go-ahead.
**Finished:** 2026-08-01 in `28ba1b0`. See `changes.md` under 2026-08-01.

**Where the plan and the outcome differed** — the part worth keeping this record for:

- **The plan named `buildPureEngineerMobileWorkflowActions` as "the primary engineer path and
  the gate that actually matters".** It is not, in this build: no card renders that row at all,
  real or pending. The live path is the sticky action bar reached through the card's **Details**
  button. Both gates were opened, so the feature works either way, but the plan's emphasis was
  wrong and the next reader should not trust it.
- **Two defects that only the browser found**, neither visible in review — see `changes.md`:
  `hasQueued` read a missing IndexedDB row as present, and the fresh-submission-token rule
  missed a send attempt whose response never returned.
- **The pending token had to be carried explicitly on three payload builders.** The plan
  treated `queueStandaloneTSROffline` as the only place it needed to be persisted; in fact
  `prepareTSRForFinalSave` and the offline branch of the final-save preview each rebuild the
  payload, and the token survived only by riding inside `selectedSchedule`.
- **Step 11, the two-tab race, was not exercised.**
- **A pre-existing weak-signal gap was found and deliberately not fixed** — the offline TSR
  branch is gated on `navigator.onLine === false`, so with a live radio and an unreachable
  server the TSR number fetch throws and nothing queues. It predates this work and affects
  every offline TSR, so it is its own task.

Both of those belong in `pending-work.md`, which is only edited when the owner asks. They are
written up in `changes.md` under 2026-08-01 until then.

### Context

An engineer with no signal opens the calendar, finds no schedule for today, adds one offline,
does the work — and then cannot write the TSR while the details are fresh. He must wait for
signal, let the schedule sync, and only then create the TSR. That leaves the field sequence
half-solved: `709106c` gave engineers offline schedule creation, but the document the schedule
exists to produce still requires a connection.

**Correct `pending-work.md:91-93` when this lands.** It records a workaround — "open Create TSR
from the sidebar and write a standalone TSR, that is fully offline already". That is **wrong**.
`/offline-tsr` hard-gates every field until a schedule is selected (`updateCreateTSRScheduleGate`,
`templates/offline_tsr.html:939-958`), and the picker's three sources — the live endpoint, the
localStorage cache, and `readTimelineSnapshotSchedules` (`:1466`) — none of them ever contain a
queued offline schedule. There is no way today to write a TSR with no shift, on the device or on
the server. The gap is bigger than that file claims.

**Intended outcome:** the engineer taps **Create TSR** on a queued schedule card, writes the TSR
offline, and both queue. When signal returns the schedule syncs first, learns its real shift id,
and the TSR behind it is rewritten to point at that id before it is sent.

### Decisions taken by the owner

1. **Dependent queue items, not standalone-then-retro-link.** This resolves the open question
   posed in `pending-work.md` — the TSR waits for its schedule.
2. **A written TSR must never be lost.** If the parent parks as a conflict and the engineer
   removes it from the queue, the TSR survives and moves to a "needs a schedule" state where the
   engineer picks a schedule for it.
3. **Multi-day chains:** attach to the shift whose date matches the TSR's service date, with the
   first shift of the chain as the fallback.
4. **Queued schedules appear in the Create TSR picker**, marked pending, as well as being
   reachable from the button on the card.

### What already exists, and what genuinely blocks this

Three load-bearing pieces are already built: `/add_shift` resolves a `creation_token` replay
**before** the collision check (`app.py:39635` before `:39706`, pinned by
`tests/test_offline_schedule.py:39`); the schedule queue replays strictly serially and
single-flight (`static/js/app-offline-schedule.js:383-458`); and the TSR queue tolerates per-item
failure without stopping its loop (`templates/offline_tsr.html:4518-4537`).

Five real blockers, each verified in the source rather than assumed:

- **`/add_shift` returns no ids on a fresh create** — `jsonify({'status': 'success'})`,
  `app.py:39801`. Ids come back only on the replay path (`build_schedule_replay_response`,
  `:39607`). And `sendOne` never reads the response body anyway
  (`app-offline-schedule.js:472-475`).
- **`app-offline-schedule.js` is not loaded on `/offline-tsr`.** Its only include is
  `templates/timeline.html:12`, so `window.offlineSchedule` is `undefined` there.
- **A pending card carries no client or product.** `summary` holds only
  title/dates/times/engineers (`timeline.html:12905-12913`) and the merged row hardcodes
  `client_id:''`, `client_name:''` (`:13053`). A TSR written from one would be rejected by
  `get_online_tsr_missing_core_details` (`app.py:13593`) *after* the engineer wrote the whole
  thing.
- **A pre-existing latent bug this feature must fix, not merely avoid.** `collectTSRData`
  (`offline_tsr.html:2383`) is `schedule_id: selectedSchedule?.id || selectedStandaloneScheduleId
  || ''` — it falls through to the **composite runtime id**
  (`"...::2026-08-01::09:00-11:00::0"`). `clean_int` (`app.py:4310`) returns `None` for that, so
  `/save_offline_tsr_online` 400s (`app.py:13537`) — and 400 is non-retriable
  (`isRetriableTSRSyncError`, `:684`), so the TSR parks permanently.
- **Re-pointing a TSR at a different shift 409s forever** unless a fresh `submission_token` is
  minted — the cross-shift guard at `app.py:13569`, also non-retriable.

### The design in one paragraph

`/add_shift` returns `group_id` / `shift_ids` / `shift_dates` on first success **only when a
creation token was sent**, so ordinary online saves are untouched. The schedule queue writes a
durable token → ids mapping into a new IndexedDB store *before* discarding the queue row, so a
failed mapping write means no discard and the item replays into the same ids. The TSR queue item
carries a `pending_schedule_token` instead of a `schedule_id`; at sync it awaits the schedule
queue (single-flight, so awaiting is safe), resolves the token, rewrites the shift reference, and
only then posts. Unresolved-but-still-queued is retriable; unresolved-and-gone becomes
"needs a schedule", which the engineer resolves from the existing picker.

### Step 1 — Server: `/add_shift` hands back the ids (`app.py`)

- Generalise `build_schedule_replay_response` (`:39607`) into
  `build_schedule_ids_response(first_shift, chain, replay)`; keep the old name as a wrapper with
  `replay=True` so the two existing replay branches (`:39642`, `:39787`) emit byte-identical
  output. Add `shift_dates` (ISO, parallel to `shift_ids`) to both shapes — additive keys only,
  so `tests/test_offline_schedule.py:244` keeps passing.
- In the create loop (`:39714-39748`) collect every `new_shift` into `created_shifts`; only
  `first_shift` is retained today (`:39744`). `schedule_dates` is already ascending, matching the
  replay ordering (`Shift.start_time.asc()`, `:39598`).
- Replace `:39801` with `build_schedule_ids_response(first_shift, created_shifts, replay=False)`
  **gated on `creation_token` being truthy**. No token → the untouched `{'status': 'success'}`.

Nothing moves above `:39644`, so the replay-before-collision ordering is untouched.

### Step 2 — Schedule module: durable mapping (`static/js/app-offline-schedule.js`)

- `DB_VERSION` `:16` → `2`; add a **new `resolved` store** (keyPath `token`) inside the existing
  `contains()`-guarded `onupgradeneeded` (`:37-51`). Record:
  `{token, groupId, shiftIds:[], shiftDates:[], resolvedAt}`. Do **not** reuse the `reference`
  store — `getCachedList` (`:115`) assumes every record has a `rows` array, and overloading it is
  a type collision waiting to happen.
- Export `resolveToken(token)`, `hasQueued(token)` (the queue keyPath *is* the token, `:268`) and
  `forgetResolved(token)` on `window.offlineSchedule` (`:519-531`).
- Rewrite the `sendOne` success branch (`:472-475`) as an ordered chain: `response.json()` →
  `recordResolved(...)` → `discard(item.id)` → `outcome.synced += 1`. A `recordResolved`
  rejection must skip the discard and fall into the existing catch (`:500`), leaving the item
  queued — the next pass replays and gets the same ids back. **Increment `synced` last**, or a
  mapping failure reports "Synced 1 schedule" for an item still sitting in the queue.

### Step 3 — Timeline: give pending cards what a TSR needs (`templates/timeline.html`)

- `queueScheduleOffline` `:12905` — extend `summary` with
  `clientId/clientName/clientAddress/productId/productName/status`, all already present in the
  `dataSet` FormData.
- `renderOfflineScheduleQueue` `:12939` — carry them into `queuedScheduleRows`.
- `mergeQueuedSchedulesIntoGrid` `:13045` — populate those fields on the pending row and add
  `creation_token: row.id`. **Keep the strip-then-append idempotence at `:13027-13035` exactly as
  it is** — stacking duplicate pending cards was a shipped bug once already.
- `buildMobileScheduleContextKey` `:9947` — add `shift?.queue_id`. The key is currently
  `[shift?.id || '', day.iso, engineer.id]`, so every pending card on the same day for the same
  engineer collides and tapping the second opens the first one's actions.
- `buildPureEngineerMobileWorkflowActions` `:10836` — **this is the primary engineer path and the
  gate that actually matters**, not the sticky bar. Change `!shift?.id` to
  `!shift?.id && !shift?.queue_id`, and route pending shifts at `:10846` through a new
  `redirectToCreateTSRPageFromQueuedSchedule()`.
- `renderMobileStickyActionBar` `:10076` — same treatment for the `offlineTsrBtn`. Edit, send and
  duplicate stay disabled; `canManageExistingScheduleForRow` (`:14122`) is unchanged.
- New `redirectToCreateTSRPageFromQueuedSchedule(...)` beside `:18368`, requiring `queue_id` and
  passing `pending_schedule_token` with **no** `shift_id`. `buildCreateTSRPageUrlFromContext`
  (`:18333`) gains a branch emitting `?pending_schedule=<token>`; `storeCreateTSRContextForPage`
  (`:18349`) stores the whole object and needs no change.

### Step 4 — TSR page: accept a pending token (`templates/offline_tsr.html`)

- **Add the `app-offline-schedule.js` include**, mirroring `timeline.html:12`. It is already an
  `APP_SHELL` precache entry (`app.py:14407`), and it is a self-contained IIFE whose only side
  effects are the `online` listener and the `window.offlineSchedule` assignment. Do **not** open
  `medical_service_offline_schedule_db` by name from this page: an unversioned `open()` on a
  device where the module never ran creates an empty v1 database with no object stores, and every
  later `withStore()` call fails with `NotFoundError` permanently.
- `normalizeStandaloneCreateTSRContext` `:1210` and `getStandaloneCreateTSRHandoffContext` `:1246`
  — read and preserve `pending_schedule_token` (query param `pending_schedule`), and count it in
  the "is this context meaningful" test at `:1215`.
- `findStandaloneScheduleFromCreateTSRContext` `:1281` — when a pending token is present, match
  **only** on that token. The existing fallback at `:1299` matches on date + client/product, which
  would silently bind the TSR to a real server schedule for the same client on the same day.
- `getStandaloneScheduleRealId` `:1206` — numeric-only (`/^\d+$/`), `''` for a pending schedule.
- `collectTSRData` `:2383` — `schedule_id: getStandaloneScheduleRealId(selectedSchedule)` plus a
  new `pending_schedule_token`. **This is the latent-bug fix.**
- New `readPendingScheduleOptions()` beside `readTimelineSnapshotSchedules` (`:1466`), reading
  `window.offlineSchedule.list()` and emitting one option per date in the chain, labelled
  "Waiting to sync — ", with `pending_schedule_token` and `_offline_uid`. Merge it in
  `refreshStandaloneScheduleOptions` (`:1630`) **after** `cacheStandaloneScheduleOptions`
  (`:1642`, `:1654`) so pending entries never reach localStorage and outlive the queue.
- `queueStandaloneTSROffline` `:4242` — persist `pending_schedule_token` on the item and inside
  `payload`; `sanitizeTSRPayloadForTransport` (`:3341`) only strips `attachments`, so it survives.

**Leave `hasStandaloneScheduleSelection` (`:871`), `updateCreateTSRScheduleGate` (`:939`) and
`requireStandaloneScheduleForTSRAction` (`:954`) alone.** They check the *runtime* picker id,
which a pending option gets for free — relaxing them would weaken a working guard for nothing.

**Leave `openOfflineTSRDraftFromShiftModal` (`:18419`) alone.** It is the desktop edit-modal path,
which only ever opens saved shifts.

### Step 5 — TSR sync: resolve before posting (`templates/offline_tsr.html`)

- New `resolveTSRQueueItemSchedule(item)`: a positive integer `schedule_id` → done; a token that
  resolves → pick the shift by service date (Step 6) and apply (Step 7); a token that does not
  resolve but `hasQueued(token)` → throw a **retriable** `schedule_pending` error naming the
  schedule; a token that resolves to nothing and is not queued → `needs_schedule`.
- `syncOfflineTSRQueue` `:4451` — after the health check (`:4482`) and **above** the loop at
  `:4518`, if any pending item has an unresolved token,
  `await window.offlineSchedule.sync({silent:true}).catch(()=>{})`. Once per run, not per item.
  The catch matters: `sync()` **rejects** on session expiry (`:451-455`), and that must leave the
  TSR queued-retriable rather than parked.
- `uploadQueuedOfflineTSR` `:4336` — resolve **before** building `finalizedPayload` at `:4340`,
  and take `schedule_id` from the resolved integer only. The existing fallback chain at `:4341`
  (`payload.selectedScheduleId || payload.selectedSchedule?.id`) is precisely what posts a
  composite string today. Skip resolution when `server_submission_id` is already set (`:4345`).
- `scheduleOfflineTSRSyncRetry` `:4280` — floor the `schedule_pending` delay at 15s; the 5s first
  retry would just re-await a schedule queue that is offline for the same reason.

The per-item catch at `:4530` needs no change — a retriable throw lands in
`markFailedOfflineTSRQueueItem` (`:3602`), keeps `status:'pending'`, and the loop continues.

### Step 6 — Multi-day service-date match

The `resolved` record holds `shiftIds` / `shiftDates` in chain order. Match on
`payload['tsr-service-date']` (already read at `:4352`), else `selectedSchedule?.date_iso`, else
`payload.service_date`; find that date in `shiftDates` and take the parallel id. No match →
`shiftIds[0]`, which is also the token-carrying shift (`app.py:39738`). Record
`resolved_by: 'service_date' | 'chain_first'` on the item so the panel can say which, and so a
support question later has an answer.

### Step 7 — One writer for the shift reference, and the "needs a schedule" state

The shift reference lives in **four** places that must agree: `item.schedule_id`,
`payload.schedule_id`, `payload.selectedScheduleId`, `payload.selectedSchedule.id`. All four are
written by a single `applyResolvedScheduleToTSRQueueItem(item, {shiftId, scheduleSnapshot})` going
through `patchOfflineTSRQueueItem` (`:4318`). It also clears the pending token, clears
`needs_schedule`, restores `retryable`, and — **when the resolved id changes or
`server_submission_id` is set** — mints a fresh `submission_token` and nulls
`server_submission_id` / `server_result` / `core_saved_at`. Without that, the cross-shift guard at
`app.py:13569` 409s every retry forever and the re-point flow bricks itself. No other function may
write those four fields.

**"Needs a schedule" is detected pull-side**, at TSR sync or panel render, when a token resolves to
nothing and `hasQueued` is false. Do not try to push a notification from `discardQueuedSchedule`
(`timeline.html:12992`) — different database, and the TSR page may not even be open. Such an item
keeps `status:'pending'` (so it is never lost), gains `needs_schedule: true`, and
`renderOfflineTSRQueuePanel` (`:4041`) shows **Pick a schedule** instead of Retry, reusing the
existing picker — which, after Step 4, lists re-added pending schedules too.
`removeOfflineTSRQueueItem` (`:4626`) stays the only deletion path and is already confirm-gated.

### Step 8 — Cache versions

Bump `CACHE_VERSION` in `app.py:14387` (**read the live value immediately before committing** —
`v49` was claimed and then overwritten by a bump from outside that session), and the `?v=` on both
module includes. No `APP_SHELL` change; the module is already listed at `:14407`.

### What must not change

- `/add_shift` for ordinary online saves — the new response is gated on `creation_token`, which
  the online save paths never send. A test asserts the untokened body is exactly
  `{'status': 'success'}`.
- Replay-before-collision ordering (`app.py:39635` before `:39706`).
- `/save_offline_tsr_online`'s validation — the falsy-id 400 (`:13537`), missing-shift 404
  (`:13541`), `can_work_on_existing_schedule_shift` (`:13544`), cross-shift 409 (`:13569`),
  `get_online_tsr_missing_core_details` (`:13593`). The client stops sending bad ids; the server
  keeps refusing them.
- The three TSR page gates (`:871`, `:939`, `:954`) and `mergeQueuedSchedulesIntoGrid`'s
  idempotence (`:13027`).
- `canManageExistingScheduleForRow`'s pending refusal (`:14122`) — queued schedules stay
  non-editable.

### Verification

**Tests** — new `tests/test_offline_tsr_pending_schedule.py`, house style: `os.environ.setdefault`
before `import app`, a distinctive title prefix, and a `tearDownClass` deleting the shifts,
`ShiftEngineer` links, `OnlineTsrSubmission` rows, engineers and users it created — the suite
shares one database and one Flask app.

Functional, each with a positive control that proves it can fail:

- First success with a token returns `group_id`, `shift_ids`, `shift_dates`; a 5-day range returns
  the whole chain in ascending date order.
- Replay returns ids **equal** to the first success — this is what makes the "mapping write
  failed, let it replay" recovery real rather than theoretical.
- **Untokened save response is byte-identical to today** — the positive control for all of Step 1.
- A TSR posted against the middle shift of a 3-day chain lands on that shift; `schedule_id=0`
  still 400s; a composite runtime id still 400s.

Source assertions: the module is included in `offline_tsr.html` (control: the same assertion
against another template must fail); `DB_VERSION = 2` and the `resolved` store guard;
`recordResolved` appears **before** `discard(item.id)` in `sendOne`;
`resolveTSRQueueItemSchedule` appears before `'/save_offline_tsr_online'` in
`uploadQueuedOfflineTSR`; `selectedScheduleId` is assigned in exactly one place outside
`collectTSRData`; pending options are merged after `cacheStandaloneScheduleOptions`;
`buildMobileScheduleContextKey` includes `queue_id`; cache version bumped via
`assert_cache_version_at_least`.

**Browser, against a genuinely stopped server** — not DevTools "Offline", which the last round
showed can still serve from the HTTP cache. Isolated `MEDICAL_SERVICE_TEST_DB`, port 5056, never
5000, signed in as a real seeded engineer. Unregister the worker and clear **both** caches after
each asset edit, and restart the server after every template edit — Jinja caches compiled
templates and that cost real time in `709106c`.

1. Online: load `/timeline`, then `/offline-tsr` once so both shells and the module precache.
2. **Stop the server** and confirm the port refuses.
3. Add a 3-day schedule with a client and product; confirm three dashed pending cards land on the
   right dates **and show the client name** — blank means Step 3 is incomplete.
4. Tap a pending card: Create TSR enabled in both the workflow row and the sticky bar. Tap a
   second pending card on the same day and confirm you get *its* actions, not the first card's.
5. Create TSR → `/offline-tsr` loads from cache, the picker shows "Waiting to sync", fields are
   enabled, client/product/task/date auto-filled.
6. Reload `/offline-tsr` with **no query string** — the pending schedule must still be selectable.
   The sessionStorage context is cleared at `:1343`, so this is what catches a memory-only
   injection.
7. Queue the TSR; in IndexedDB confirm `schedule_id` is `''`, `pending_schedule_token` is set, and
   `payload.selectedScheduleId` is not a composite string.
8. Sync with the server still stopped: item stays pending, **no** `/save_offline_tsr_online` in
   the Network tab, message names the schedule it is waiting for.
9. **Start the server.** In order: `/add_shift` fires, the `resolved` store gains a record with
   three ids and dates, the schedule queue empties, then `/save_offline_tsr_online` fires **once**
   with the numeric id of the chain shift matching the TSR's service date.
10. **Orphan path:** queue a conflicting schedule plus a TSR against it; let it park; remove it.
    The TSR must still be there in "needs a schedule". Pick a real schedule; confirm all four
    fields rewrite, a **new** `submission_token` is minted, and it then sends.
11. **Two-tab race:** `/timeline` and `/offline-tsr` open together, go online, confirm exactly one
    `/add_shift` per schedule and one `/save_offline_tsr_online` per TSR. Both pages now carry an
    `online` listener, so this is the only way to prove the single-flight guard holds.

Plus the standing bar: both themes, 375 px with no horizontal overflow, tap targets ≥44 px,
console clean, `python -m unittest discover -s tests` green from 334, and a `releases.json` entry
dated the commit date.

### Deliberately excluded

- **The desktop edit-modal path** (`openOfflineTSRDraftFromShiftModal`, `:18419`) — offline
  creation is a mobile-engineer flow.
- **Cross-device resolution.** The mapping is device-local by construction. A TSR queued on phone
  A whose schedule synced from phone B sits in "needs a schedule" until the engineer picks it.
  Fixing that needs a server-side token lookup endpoint; the re-point flow covers it acceptably
  without new API surface.
- **Automatic re-point when a removed parent is re-added.** The re-added schedule gets a new
  token; asking the engineer to pick it is safer than guessing an identity match on title + date
  + time.
- **Offline editing of a queued schedule**, and **TSR revision mode against a pending schedule** —
  a revision targets an existing server submission, which implies a real shift.

### Risks worth stating

- **This is a larger cut than `709106c`:** four files, a schema version bump on a live device
  database, and a change to the response shape of `/add_shift`. Steps 1–2 are self-contained and
  low risk; Step 4 touches the most fragile file in the app.
- **The natural seam if it should be split is after Step 3** — server ids, durable mapping and
  enabled pending cards can land and be verified on their own, with the Create TSR button still
  routing to today's "saved schedules only" behaviour.
- **The IndexedDB version bump lands on devices that already hold a v1 database.** The existing
  `contains()` guards make it additive, but it is the first schema change to a store field
  engineers already rely on.

---

## Offline schedule creation for field engineers

**Status:** `Executed`
**Approved:** 2026-07-31
**Started:** 2026-07-31, on the owner's go-ahead.
**Finished:** 2026-07-31. See `changes.md` under 2026-07-31 for what was built and what was
found along the way.

**Where the plan and the outcome differed** — the part worth keeping this record for:

- The plan called for adding an `error_kind` marker to the conflict response. Not done, and
  deliberately: `build_conflict_response()` already returns HTTP 409 with `status: 'conflict'`,
  and travel conflicts return `status: 'travel_conflict'` with an override key, so the device
  could already tell retry from stop. A second discriminator would have been redundant.
- The plan assumed queued rows only needed merging into the timeline grid. Engineers actually
  render through the role-aware **mobile** path, so the merge had to be applied there too —
  otherwise pending cards would have appeared for everyone except the people who create them.
- Two defects the plan could not have anticipated, both found in the browser: a UTC date shift
  that filed queued schedules on the previous day, and a non-idempotent grid merge that stacked
  duplicate pending cards on every re-render.

### Context

Engineers working in remote areas cannot reliably add a schedule, because `/add_shift`
requires a live connection. The work still happens; the record of it waits until they find
signal, which means schedules are entered late, from memory, or not at all.

The app already solves this exact problem for TSRs. `/offline-tsr` runs a complete offline
workflow — IndexedDB drafts, a sync queue, retriable-vs-fatal error handling, a health ping,
and server-assigned numbering at sync time. The goal is to give schedule creation the same
treatment, reusing that machinery rather than inventing a second offline system.

Why this is achievable rather than speculative:

- `/timeline` is already in `APP_SHELL` and `FIELD_SAFE_ROUTES` (`app.py:14348`), so the page
  already loads with no connection.
- The timeline already persists **up to 24 week/branch snapshots** covering a proactive
  ~9-week window (`saveTimelineOfflineSnapshot`, `templates/timeline.html:12694`), each holding
  the full `{days, engineers}` grid — exactly the data needed to check conflicts on the device.
- The duplicate-on-retry problem was solved for LPR in `9a2ad4d`: a nullable unique
  `creation_token` with a partial unique index and replay-the-existing-record on conflict
  (`app.py:48820`, `app.py:48911`, `app.py:48970`).
- Engineers may already create schedules that include their own profile
  (`can_create_schedule_for_engineer_ids`, `app.py:7653`), so this is not a permission change.

**Intended outcome:** an engineer with no signal opens the timeline, adds a schedule with the
same form they always use, sees it immediately marked as pending, and it reaches the server
intact and exactly once when signal returns — or comes back to them clearly if it collides.

### Decisions taken by the owner

1. **Conflict policy** — warn on the device using the cached snapshot, and if a conflict still
   appears at sync, **do not create the schedule**: park the queue item as "needs attention"
   showing the schedule it collides with, for the engineer to edit and resend.
2. **Who** — engineers only, creating schedules that include themselves. No permission change.
3. **Form scope** — the full form: client, product, multi-day range, task, teammates and
   attachments.

### Part A — Server: idempotent, offline-aware schedule creation

Reuse the LPR token pattern; do not invent a new one.

- Add `Shift.creation_token` (`db.String(100)`, nullable, unique index) to the model at
  `app.py:2416`, and add the column to the **existing additive migration list** at
  `app.py:37282`
  (`('creation_token', "ALTER TABLE shift ADD COLUMN creation_token VARCHAR(100)")`), plus a
  partial unique index mirroring `uq_lpr_header_creation_token` (`app.py:48970`). Additive and
  nullable, so existing rows and the live SQLite database are untouched.
- Add `normalize_schedule_creation_token()` beside the schedule helpers, mirroring
  `normalize_lpr_creation_token` (`app.py:48911`) — same length and charset rules.
- **The token keys the chain, not the row.** A multi-day add creates one `Shift` per date
  sharing a `group_id` (`app.py:39603`). Store the token on the first shift of the chain only;
  a replayed request looks the token up and returns that chain's `group_id` and shift ids
  rather than creating a second chain. Getting this wrong produces duplicate week-long
  schedules, so it needs its own test.
- `/add_shift` (`app.py:39525`) accepts an optional `creation_token`, validates it, and on
  replay returns the existing chain with the same success shape the client already handles.
- **Make the conflict response machine-readable.** The queue must distinguish "retry later"
  from "stop and ask the engineer". The existing collision path
  (`handle_schedule_collision_or_travel_warning`, `app.py:36645`) already returns a structured
  payload; add an explicit marker (e.g. `error_kind: 'schedule_conflict'`) so the device can
  park rather than retry forever. Travel-block conflicts already carry an override key and keep
  their existing warning-only behaviour.
- Reuse `/offline_tsr_sync_ping` as the connectivity-and-session check rather than adding a
  second one. Its name is TSR-specific and now slightly wrong; note it, do not rename it here.

### Part B — Device: persist the reference data

`masterClients` and `masterProducts` are fetched fresh from `/get_clients` and `/get_products`
(`templates/timeline.html:13571`) and never stored, so offline the client and product
autocompletes are empty. This is the single blocker to the full form working offline.

- Cache both lists in **IndexedDB, not localStorage** — these are unbounded lists and
  localStorage is a small synchronous store already holding 24 timeline snapshots.
- Refresh them on every successful online timeline load, next to the existing
  `saveTimelineOfflineSnapshot` call, so there is one "we are online, top up the device" moment
  rather than two.
- `setupAutocomplete` (`templates/timeline.html:13582`) is fed from these arrays and needs no
  change — only the source of the arrays changes.

### Part C — Device: create offline and queue

- New IndexedDB database mirroring `OFFLINE_TSR_DB_STORES` (`templates/offline_tsr.html:2423`)
  with `queue`, `attachments` and `metadata` stores. Same shape and helper style, so the two
  offline systems stay recognisably siblings.
- Intercept the submit at `templates/timeline.html:15498`. When offline — or when the POST
  fails with a network error, which is the case that actually bites in weak signal — enqueue
  the `FormData` instead of discarding it. Attachments go to the attachment store, reusing the
  blob-reference approach the TSR queue already uses.
- Generate the `creation_token` on the device at enqueue time and keep it with the item, so
  every retry of that item carries the same token.
- **Pre-check conflicts on the device before queueing**, against the cached snapshot for the
  target week: same engineer, same date, overlapping times. Mirror the server's rule in
  `find_add_schedule_collision` (`app.py:36656`) — only schedules whose start date is the date
  being added can block it. Warn the engineer while they can still change it, and make clear
  the check is against a cached copy and the server decides.
- **Show queued schedules on the timeline immediately**, visually marked as pending sync, so
  the engineer can see their own work. They must be visually distinct from confirmed schedules
  and must not be editable through the normal edit path while queued.
- Queue panel on the timeline mirroring the TSR one (`templates/offline_tsr.html:46`): count,
  last-sync label, "Sync Now", and per-item state.

### Part D — Sync

Mirror `syncOfflineTSRQueue`, including its error classification (`makeTSRSyncError` /
`isRetriableTSRSyncError`, `templates/offline_tsr.html:678`):

- Health ping first, then replay each queued item as the same multipart POST it would have made
  online, carrying its `creation_token`.
- **Success** → mark synced, drop the attachments, refresh the grid.
- **Retriable** (network, timeout, 5xx) → leave queued, try again later.
- **Session expired** → keep the item and say so plainly, exactly as the TSR queue does.
- **Conflict** → park the item as "needs attention" with the conflicting schedule shown, and do
  not retry it automatically. The engineer edits and resends.
- Sync on regaining connectivity and on manual request; never on a timer that could fire
  mid-form.

### Part E — Tests

New `tests/test_offline_schedule.py`, in the house style of source assertions plus functional
coverage:

- **Idempotency, with a positive control**: two `/add_shift` posts with the same
  `creation_token` produce one chain and return the same shift ids — plus a control asserting
  that two posts *without* a token genuinely produce two chains, so the assertion cannot pass
  vacuously.
- **Multi-day chains**: a replayed 5-day request leaves 5 shifts, not 10, and one `group_id`.
- **Conflict is fatal, not retriable**: a colliding queued schedule returns the conflict marker
  and creates nothing.
- **Authorization still holds at sync**: an engineer cannot use the offline path to create a
  schedule that excludes their own profile — `can_create_schedule_for_engineer_ids` is
  re-checked server-side and the token does not bypass it.
- **Migration is additive**: `creation_token` is nullable, existing rows unaffected, and no
  `DROP COLUMN` appears in the source.
- Source-level: the timeline enqueues rather than discarding on network failure, the queue
  renderer issues no `fetch(` of its own (the phase-1 rule), and no template syntax leaks into
  any extracted JS.

Watch the documented cross-module hazard: every test module pins `MEDICAL_SERVICE_TEST_DB` with
`os.environ.setdefault`, so the first import wins and all modules share one database. Anything
seeding engineers or shifts must clean up in `tearDownClass`.

### Verification

- `python -m py_compile app.py`, `node --check` on any extracted JS, CSS braces balanced.
- `python -m unittest discover -s tests` — green, from 315.
- **Bump the service worker**, reading the live value out of `app.py` immediately before
  committing rather than trusting a value noted earlier in the session.
- `releases.json` entry dated the commit date — and check the date at commit time, not when the
  entry is written.
- Browser on an isolated database, explicit `MEDICAL_SERVICE_TEST_DB`, port 5056, never 5000,
  signed in as a **real seeded engineer account**. The end-to-end path that matters:
  1. Load the timeline online so snapshots and reference data cache.
  2. Go offline in the browser pane, reload, confirm the page and form still work and the
     client/product autocompletes are populated.
  3. Add a schedule offline; confirm it queues, renders as pending, and survives a reload.
  4. Add one that collides with a cached schedule; confirm the device warns.
  5. Go online; confirm it syncs exactly once, the pending marker clears, and the row is real.
  6. **Sync the same queue item twice** to prove the token holds.
  7. Queue a schedule that genuinely conflicts server-side; confirm it parks rather than
     silently vanishing or double-booking.
- Contrast in both themes for the new queue panel and pending-row treatment, 375px with no
  horizontal overflow, tap targets ≥44px, console clean.
- `/static/` is `cacheFirst` and the worker re-registers on every load: unregister it and clear
  **both** caches after each asset edit. Restart the server after template edits — Jinja caches
  compiled templates.

### Deliberately excluded

- **Editing or deleting schedules offline.** Creation is the stated problem. Offline edits need
  conflict resolution against a row that may have changed server-side, which is materially
  harder and belongs in its own task.
- **Schedulers and admins.** They create schedules for many engineers at once, which multiplies
  the conflict surface, and they are typically on a connection.
- **Background Sync API.** Manual and on-reconnect sync only, matching the TSR queue.
- **Renaming `/offline_tsr_sync_ping`** to something generic, despite it now serving both.

### Risks worth stating

- **The device pre-check is only as fresh as the cached snapshot.** An engineer offline for a
  week checks against week-old data. The UI must say so rather than implying certainty; the
  server remains the authority.
- **Attachments are the heavy part of the queue.** Large photos in IndexedDB on a field phone
  are the most likely source of storage-pressure bugs. Reuse the TSR queue's blob-reference
  approach rather than re-deriving it.
- **`/add_shift` is a large, much-used route.** The token path must not alter behaviour for
  ordinary online saves; that is what the "no token" positive control is for.

---

## Earlier work, for reference

Plans predate this file only in the sense that they were not written down separately — the
dashboard redesign phases 1–4, the hybrid ratification, and the TSR files rename were all
planned, approved and executed before this rule existed. Their detail lives in `changes.md`
under their dates, and the hybrid ratification plan in particular is recorded there in full.
Nothing is missing; it simply is not in this file.
