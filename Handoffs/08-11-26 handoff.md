# 08/11/26 handoff

**Project:** Medical Service SMS
**Workspace:** `D:\Shimadzu\Projects\SHIMADZU\medical-service-sms-railway`
**Prepared:** 2026-08-11, Asia/Manila
**Purpose:** Give the next Codex session a reliable starting point without repeating the project-history scan.

## Start Here

Read these files before making any code or system change:

1. `AGENTS.md` — project rules, especially the plan-approval gate, mandatory change journal, explicit staging, and database/artifact exclusions.
2. `changes.md` — the chronological implementation and verification record. Its newest section is dated 2026-08-11.
3. `plans.md` — the full approved-plan archive. The newest P.O. plan is marked Executed; all recorded plan status lines currently resolve to Executed.
4. `pending-work.md` — the open-work and verification journal. **Section 1 is currently empty: there is no open defect.** Read its correction notice at the top before trusting anything here.

Do not treat this handoff as a replacement for those journals. It is an orientation document and points back to them for the authoritative details.

**This file is now tracked in git.** That makes it authoritative for anyone who clones the repo, which is a stronger claim than an untracked scratch note — so a stale line here now travels. **Correct it in the same commit as the work it describes**, exactly as `changes.md` is maintained.

## Current Repository State

- Branch: `main`.
- `origin/main` and the local `HEAD` are at `14eee82` (backup record correction and review follow-up). The P.O. release is `3d66caf` with closeout `30c087c`; the System Backup Center is `b4b17fc`.
- All are pushed to GitHub `origin/main`.
- No Railway deployment was triggered by any of these actions.
- Service worker at `v85-backup-offline-fallback`. Suite green at **605** with one pre-existing skip.
- The working tree contains pre-existing local artifacts that must remain untouched:
  - modified `scheduler.db`
  - untracked `output/`
  - untracked `tmp/`
  - untracked `medical-service-sms-detailed-handoff-2026-07-26.md` (the older loose handoff, superseded by this one and deliberately left untracked)
- **`Handoffs/` IS tracked**, changed by the project owner on 2026-08-11. Handoff documents are now published with the code rather than kept as local scratch. See the operating rules below.
- The journal refresh that produced this file was committed in `14eee82` together with the corrections to it.

Never use `git add .`, `git commit -a`, `git reset --hard`, or a broad cleanup command in this workspace. Stage named files only after reviewing `git status --short` and `git diff --name-only`.

## Project Shape

This is a Flask/SQLAlchemy medical field-service management system with SQLite-backed local/runtime data, Railway deployment, persistent volume and bucket-backed user files, server-rendered HTML templates, browser JavaScript, generated PDFs/Excel files, offline TSR support, and role-specific navigation.

The major operational areas are:

- Calendar and schedules in `templates/timeline.html`.
- Create TSR and offline synchronization in `templates/offline_tsr.html` plus the corresponding Flask routes/helpers.
- TSR archive and reports in the reports templates and archive APIs.
- Accounting workflows: Reimbursement, Travel Request, Travel Liquidation, Cash Advance, Cash Advance Liquidation, and LPR.
- Leave Request, including normal and Form-to-Follow Sick Leave flows.
- Products and P.O. Details registers.
- Stock Inventory with branch-aware permissions, engineer read-only access, barcode-oriented movement tracking, and inventory-only accounts.
- Settings, approval routing, email recipients/subjects/templates, storage, backup, appearance themes, and user capabilities.
- Activity Logs and What’s New release communication.

The system has accumulated substantial compatibility behavior. Prefer existing helpers, serializers, storage adapters, authorization predicates, template conventions, and tests over new parallel abstractions.

## Latest Completed Release: P.O. Register Upgrade

The latest release is documented in full in:

- `plans.md`, section **P.O. Dates, Amount, and Complete Excel Export**.
- `changes.md`, the dated sections for 2026-08-10 and 2026-08-11.

High-level outcome:

- P.O. records retain the legacy `po_date` field as the compatible Start Date.
- Additive `end_date` and optional positive PHP `amount` support were added.
- Contract P.O.s require an End Date; Single Visit P.O.s may leave it blank; End Date cannot precede Start Date.
- Existing legacy records remain readable.
- The P.O. register now shows Start Date, End Date, Amount, contract-aware status behavior, sorting, and mobile-compatible rendering.
- A protected filtered Excel export includes P.O. identity, date range, number, medical center/address, type, amount, creator/audit data, formatting, freeze panes, autofilter, and a total amount row.
- Focused verification passed 16 P.O./analytics tests, Python compilation, inline P.O. JavaScript syntax, release manifest parsing, and `git diff --check`.
- The What’s New release metadata was updated; no service-worker bump was needed for this server/API and template change.

The P.O. release did not replace the database, rewrite historical records, clean generated artifacts, or change existing P.O. access rules.

## Current Open Work

### 1. ~~System Backup Download Failure in Production~~ — ALREADY FIXED. DO NOT RE-IMPLEMENT.

> **CORRECTED 2026-08-11.** This section described the backup as the next actionable defect. **It was
> fixed on 2026-08-09 in `b4b17fc`, which is on `origin/main`.** The diagnosis below named
> `response.call_on_close` deleting the temp file — **that code no longer exists**. Acting on the
> original text would have meant re-implementing a shipped feature.
>
> The error came from reconciling the journals against each other rather than against the tree. If
> you are reading this in a fresh session: **check the code before trusting any "open defect" here.**

**What actually shipped**, verified by running it rather than reading it:

- The archive is **built ahead of time by a background job** (`/admin/backup/start`), with polled
  progress, cooperative cancel, and durable job state that survives a redeploy. `/admin/download-backup`
  then serves a **finished file**.
- **Resume works.** A ranged request returns `206`; a partial + resumed download reassembles
  byte-identical to a single-pass download; two full downloads are byte-identical.
- **The root cause was not what the original diagnosis said.** Flask 3.1.2 defaults `send_file` to
  `conditional=True`/`etag=True`, so the old route *already* advertised `Accept-Ranges`. Resume failed
  purely because the file was deleted on response close. **The fix was keeping the file, not adding a
  parameter.**
- **Streaming was never built and is not needed** — build-then-download keeps `Content-Length` and the
  `X-Backup-*` headers *and* gains Range. `pending-work.md` section 5 records it as superseded.
- Also fixed in the same work: the database is snapshotted through SQLite's backup API instead of
  copied as a raw live file, so an archive can no longer hold a torn database.
- **Follow-up shipped 2026-08-11**: `/admin/backup` now falls back to the app's offline page instead
  of a raw browser error; worker at `v85-backup-offline-fallback`.

**There is no open defect.** The next actionable items are the verification gaps below and the queued
Analytics print work in `pending-work.md` section 2.

### 2. Browser Verification Gap

- Brave is covered by the owner’s daily use.
- Edge remains the main unverified browser gap, including the previously reported session-loss behavior.
- The journals also retain structural verification gaps such as real keyboard focus behavior and some end-to-end production checks. Read `pending-work.md` before claiming a workflow is fully verified.

## Operating Rules From the Owner and Project Instructions

- Never stage, commit, push, replace, copy, delete, or migrate `scheduler.db`.
- Never stage or push `output/`, `tmp/`, or generated files.
- **Handoff rule changed by the owner on 2026-08-11: `Handoffs/` is tracked and committed.** Documents there are published with the code, so treat them like `changes.md` — correct a stale line in the same commit as the work that made it stale. The older loose `medical-service-sms-detailed-handoff-2026-07-26.md` at the repo root stays untracked; do not stage it.
- The live database must not be replaced by the local database. Additive migrations are acceptable only when explicitly planned and executed safely.
- The latest explicit release instruction controls deployment. Do not deploy to Railway merely because code was pushed to GitHub.
- When the owner approves a plan, record the complete plan in `plans.md` and stop. Approval is not execution permission. Start only after a separate go-ahead such as “execute,” “go ahead,” or “do it.”
- Before any request that changes files or behavior, read `changes.md` in full. After every change, update `changes.md` in the same task with detailed factual bullets.
- When a plan changes during execution, amend `plans.md`; do not silently widen or replace it.
- Use `keep-up` when requested to reconcile `changes.md`, `plans.md`, and `pending-work.md` before acting.
- Commit and push only intentionally staged files. Verify the staged list and explicitly scan it for database, output, temporary, and handoff paths.
- Never revert changes that came from the owner or another tool. Inspect and work around unrelated dirty files.
- Preserve existing permissions, data, archive links, file names, offline queues, signatures, and sent artifacts unless a plan explicitly changes them.

## Working Style and Collaboration Preferences

- Address the owner as **partner** unless the owner requests another form of address.
- Keep progress updates short, concrete, and evidence-based; status updates are not approval gates.
- Read the existing code and journals before deciding. Prefer local patterns and shared helpers.
- For UI repairs, prioritize real clickability, native browser scrolling, modal layering, keyboard/touch targets, mobile layout, and cross-browser behavior. Avoid fragile whole-card handlers, wheel interception, hover-only actions, and body-level pointer-event tricks.
- For PDF work, inspect the official source template, preserve data/geometry/signatures, render at meaningful zoom levels, extract text, and verify page breaks and file consumers.
- For permissions, test every differentiated account shape and every route/API, not only superadmin. Keep page guards and endpoint guards aligned.
- For generated workbooks and packages, inspect actual cell/file contents rather than relying only on source-text assertions.
- Use the smallest focused verification set that proves the change, then broaden only when the risk or failure justifies it.

## Release and Verification Checklist

For future implementation tasks:

1. Read `changes.md`, `plans.md`, and relevant sections of `pending-work.md`.
2. Check `git status --short`, branch, remote, and recent commits.
3. Confirm the exact scope and whether the owner has authorized execution, commit, push, or Railway deployment.
4. Implement with focused edits and update `changes.md` immediately after the behavior changes.
5. Add or update behavioral tests with positive controls; avoid decorative source-text tests.
6. Run targeted tests, Python compilation, JavaScript syntax checks, PDF/Excel inspection when relevant, `git diff --check`, and browser verification for UI changes.
7. Review the complete diff and staged file list. Explicitly confirm forbidden files are absent.
8. Commit with a focused message only after verification.
9. Update the corresponding plan status to Executed with the commit hash; commit that journal closeout separately if needed.
10. Push only after explicit authorization and verify `git ls-remote origin refs/heads/<branch>` matches local `HEAD`.
11. Deploy Railway only after a separate deployment instruction; verify the live service and database/storage behavior afterward.

## Suggested Skills for the Next Agent

Invoke these only when the task matches their scope:

- `$keep-up` for a read-only reconciliation of the three project journals before starting work.
- `frontend-repair-baseline` for browser-safe calendar, modal, scrolling, click, responsive, and theme repairs.
- `pdf` for official-template PDF inspection, generation, rendering, extraction, and visual verification.
- `spreadsheets` for standalone Excel/CSV artifact inspection and validation.
- `web-app-security-hardening` for authorization, file access, upload, session, or production hardening reviews.
- `github:github` for repository/PR orientation and `github:yeet` only when the owner explicitly asks to publish verified work.
- `browser:control-in-app-browser` or `chrome:control-chrome` for authenticated browser verification when the appropriate session is available.
- `computer-use:computer-use` for device-level or browser interactions that cannot be handled through the in-app browser.

## Handoff Boundary

At the start of the next chat, do not begin a new feature automatically. First read the three journals and this file, inspect the current working tree, and confirm whether the owner wants analysis, a plan, implementation, commit, push, or deployment.

**There is no open defect.** ~~The immediate known technical priority is the production System Backup download defect~~ — corrected 2026-08-11; that shipped in `b4b17fc`, see section 1. The open items are verification gaps (Edge; offline schedule attachments from a real device camera) and the queued Analytics print work.

**And take the lesson from how this file was wrong:** it described the backup defect confidently, in detail, citing code that had already been deleted. It was written by reconciling journals against each other instead of against the tree. **Verify a claimed defect against the code before acting on it** — the cost of not doing so here would have been re-implementing a shipped feature.
