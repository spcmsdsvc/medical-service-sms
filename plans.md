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
| **Verification** | Tests to add, each with the positive control that proves it can fail; the browser sequence; the standing bar (375 px, tap targets, console). Run the focused test modules for what changed; run the full suite once before publishing only when the change touches shared code (rule in `AGENTS.md` "Keep It Simple"), from the main project folder, with `venv/Scripts/python.exe scripts/run_suite.py` (parallel, about 75 s; compares with `tests/known_failures.txt`, so no stash-and-rerun baseline; refresh that list with `--update-known` only when a known failure is fixed on `main`). |
| **After implementation** | The review and release workflow below, made concrete for this plan. |
| **Risks** | What could go wrong, what the blast radius is, and what the safety net is. |

# Leave Request — Batch 4: Dark Mode (pills, danger buttons, selected segment, Form to Follow box, notices)

**Status:** Executed — `5be2ee7` on `main` (2026-10-13; owner: "execute batch 3 then 4", then "commit and push").
**Differences:** none in scope. Measured: every text ≥4.5:1 in light, graphite and AMOLED with classic, green and purple accents, except Submit with purple at 4.23:1 (app-wide accent fill, same as Cash Advance; left unchanged). Desktop proof screenshots were not possible (pane 320px wide); AMOLED phone screenshots taken and every theme measured numerically.
**Approved:** 2026-10-13. The owner answered the scan's open questions ("65 calendar days, allow past dates, no provisional delete, block self-approval") after the read-only page scan and design scan of `/leave_request`.
**Detailed:** 2026-10-13.
**Branch:** `main` (local first; publish only on "commit and push").
**Depends on:** Batch 3 executed. It rewrites the same `<style>` block, so find code by selector, not by line number.

## Context

Design scan snapshot: `.impeccable/critique/2026-10-13T06-30-23Z__templates-leave-request-html.md` (22/40, closed-list item 4). Measured in graphite and AMOLED on a copy of the database:
- Delete and Withdraw (`.leave-danger`, `#b42318` text): 1.89:1 graphite, 2.67:1 AMOLED.
- Selected duration segment (`.leave-segment input:checked+label`, `#1769e0`): 2.82:1 and 3.75:1.
- Every `.leave-status` pill keeps its light fill (`#e8eef5`, `#d7f7e5`, `#fff2c7`, `#fee2e2`, `#e0f2fe`). The Form to Follow box `.leave-check` is a light blue-grey block.
- The notices (`.leave-notice.ok/.error/.info`) and the conflicts panel (`.leave-conflicts.good/.bad`) have light fills only.

`static/css/app-dark-pages.css` has no `leave-` rules (grep: only calendar-leave tokens).

Intended outcome: every text reaches at least 4.5:1 in light, graphite and AMOLED, and nothing on the page stays a light block in dark mode. These are the Tonal Dark Rule and the Small-Text Contrast Rule.

## Decisions taken

1. Page-local rules in `templates/leave_request.html` under `:root[data-app-theme="dark"]`. Graphite is `data-app-palette="graphite"`. `app-dark-pages.css` is not touched. This is the same approach as Cash Advance Batch 4.
2. Dark pills: 16% tints of the semantic colour with light text. Rejected stays red (Semantic Status Rule).
3. Notices and the conflicts panel: `var(--app-surface)` ground, `var(--app-text)` text and a 4px semantic left border, the same as the Cash Advance toasts.

## Execution steps

1. **Read first:** the newest `changes.md` section, the DESIGN.md Colors and Elevation sections, and the Cash Advance Batch 4 dark rules in `templates/cash_advance.html` (copy their form).
2. **Pills:** dark pairs for `.leave-status` and the variants `draft`, `submitted`, `approved`, `rejected`, `form-to-follow`, `provisional` and `superseded`. Done = each is at least 4.5:1 on both dark grounds.
3. **Buttons:** `.leave-danger` gets a transparent ground, `#fca5a5` text, a red 45% border and a red-tint hover. The selected segment label uses `var(--app-primary-text)` on `var(--app-surface-raised)`. Done = both are at least 4.5:1.
4. **Blocks:** apply decision 3 to `.leave-check`, `.leave-notice.*` and `.leave-conflicts.*`. Also cover `.leave-signature-note` if it survives Batch 3. Done = no element in `.leave-page` has a computed background with luminance above 0.4 in either dark palette.
5. **Kept functions:** `showLeave`, `statusClass`, `applyLeave`, `checkConflicts` and `loadLeaveRequests` are still defined, and their class names are unchanged.

## Deliberately excluded

- Edits to `app-dark-pages.css`, because it is a shared file.
- Light-theme changes, which belong to Batch 3.

## Verification

- **Tests:** add `LeaveBatch4DarkTests` to `tests/test_leave_request_design.py`. It checks that a dark rule exists for each pill variant, `.leave-danger`, `.leave-check`, `.leave-notice` and `.leave-conflicts`. Add a kept-functions guard. **Positive control:** run against `git show HEAD:templates/leave_request.html` in the scratchpad (never `git stash`). The dark tests fail and the guard passes.
- **Focused run:** `tests/test_leave_request_*.py`, `test_provisional_leave`, `test_appearance_themes`, `test_dark_mode_readability` and `test_changelog_coverage`.
- **Browser** (copy of `scheduler.db`, temporary password on the copy, one record seeded in each status):
  - Measure every pill, button, notice and the selected segment in light, graphite and AMOLED with the classic, green and purple accents.
  - At 375px AMOLED: no horizontal scroll.
  - Console clean.
  - One screenshot per theme as proof.
  - Clean up the copy and restore `launch.json`.

## After implementation

1. Self-review the diff (template, version, changelog and tests only).
2. Service worker `CACHE_VERSION` in `app.py` → the next free number, suffix `-leave-dark` (keep the previous value as a history comment).
3. `static/changelog/releases.json`: release "Leave Request in Dark Mode" (everyone).
4. Add `changes.md` bullets, and update this Status line with any differences.
5. Commit only those files plus `plans.md` and `changes.md`. Never `scheduler.db`, `output/`, `tmp/`, handoffs, `.impeccable/` or `.claude/`.

## Risks

- **Specificity:** a shared dark rule could win over the page rules. The browser measurements catch this.
- **Blast radius:** one template's CSS. Rollback = revert the commit.

# Leave Request — Batch 3: Design System (Page Header, form first, weights, radii, buttons, focus, phone overflow)

**Status:** Executed — `5be2ee7` on `main` (2026-10-13; owner: "execute batch 3 then 4", then "commit and push").
**Differences:** the three segment group titles (Duration, Half-day on, Half-Day Period) have no single target id, so they became `.leave-label` divs with `role="radiogroup"`/`aria-labelledby` instead of `for=`; the icon-only attachment Delete also got an `aria-label`; buttons are 44px at every width, not only on phones. Found during the Batch 4 measurements and fixed here: muted text in the light Form to Follow box (4.36:1) and the light selected segment with the purple accent (4.23:1, now `--app-primary-text`).
**Approved:** 2026-10-13 (see Batch 4).
**Detailed:** 2026-10-13.
**Branch:** `main` (local first; publish only on "commit and push").
**Depends on:** Batch 2 executed (it adds ids and the status note this batch places). Find code by selector or id.

## Context

Design scan snapshot `.impeccable/critique/2026-10-13T06-30-23Z__templates-leave-request-html.md`, closed-list items 1, 2, 3, 5, 6 and 7:
- **Request pages rule (DESIGN.md Page Header):** the page uses the old gradient `.leave-hero` (CSS L6–7, markup L24–27) instead of `.request-page` and the Page Header. The column is 1239px wide (max 1320) instead of 1220. The status chip `#leaveStatus` sits in the form card, not beside the title. There is no New Request button.
- **Form buried:** the list card is first. At 1366×768 the form card is at y=682, the first input at 786 and Submit at 1128. On a phone the form is at 1233, Submit at 2378, and the page is 3027px tall.
- **Phone scroll sideways:** at 375px `scrollWidth` is 409. The hidden radios `#leaveDurationFull/Half/OneAndHalf` are `position:absolute` with `width:100%` from `.leave-field input`, and `.leave-segment` has no `position:relative`. The segment labels are 36px tall.
- **Buttons:** 8 equal buttons (L63–70). Save Draft and Upload use `#1769e0`, Submit is green `#168458`, Form to Follow is amber `#f4b400`. `var(--app-accent,#1769e0)` resolves to the hex because `--app-accent` is undefined.
- **Type and shape:**
  - Weights are 700/800/900/950 across 51 elements.
  - Radii are 9px on controls, 7px on segments, 11px on items and 14px on cards.
  - Cards have a 1px border in light mode.
  - The Rejected pill is `#fee2e2/#991b1b`, where the Semantic Status pair is `#fde8ea/#a1121f`.
- **Accessibility:**
  - There is no focus rule for fields or `.leave-btn`. The fields lack `.form-control`, so the shell's focus ring does not apply.
  - The labels have no `for`.
  - The icon-only attachment download has no `aria-label`.
- **List:** request numbers do not use `.logbook-ref`.

## Decisions taken

1. Same pattern as Cash Advance Batch 3 and the Request Pages plan. The wrapper becomes `leave-page request-page`, linking `app-dashboard.css?v=17`, with the shared Page Header.
2. **Order:** header, Leave Form card, Supporting Attachments card, My Leave Requests card.
3. **Buttons:**
   - Submit is the one accent button.
   - Save Draft, Check Conflicts, Preview, Download and Upload are outline buttons.
   - Clear is a quiet outline button.
   - Delete and Withdraw are a red outline (semantic danger).
   - Record Form to Follow is an outline button. Amber is dropped (One Variable Rule).
   - Footer layout: Clear and Delete on the left; Check Conflicts, Preview, Download, Save Draft and Submit on the right.
   - Preview and Download are hidden (not disabled) until the record is saved.
4. The status chip keeps id `leaveStatus` and moves beside the H1. The New Request button (`#leaveNewRequestBtn`, outline, `fa-plus`) calls `clearLeaveForm()`, which already confirms on unsaved values after Batch 2.

## Execution steps

1. **Read first:** the newest `changes.md` section; DESIGN.md Typography, Shapes, Buttons, Page Header and Inputs; `templates/cash_advance.html` header markup and `.cash-btn-*` rules as the model; load the Impeccable skill (`polish`). Then read `reference/craft-floor.md`.
2. **Header:**
   - Link `{{ url_for('static', filename='css/app-dashboard.css') }}?v=17` (match the version the other request pages use at that time).
   - Replace `<section class="leave-hero">` with `<header class="dash-page-header">`. Inside: `<h1 class="dash-page-h1">Leave Request <span id="leaveStatus" class="leave-status">Draft</span></h1>`, the existing subtitle in `.dash-page-sub`, and `.dash-page-actions` holding `#leaveNewRequestBtn`.
   - Remove the old `#leaveStatus` span from the form card head (one id only).
   - Delete the `.leave-hero` rules. Grep afterwards: `leave-hero` = 0.
   - The wrapper becomes `leave-page request-page`. Remove `max-width:1320px; margin:0 auto` from `.leave-page`.
   - Done = the header matches Cash Advance at 1366 and 375px.
3. **Order:** move the My Leave Requests `<section>` below the attachments card. Keep the `#leaveList` id and the Refresh button. Done = the first input is above y=400 at 1366×768.
4. **Type, shape and surfaces:**
   - Weights: 600 at most, and 400 for body, meta, muted and input text.
   - Radii: 6px for controls, buttons and segments; 10px for cards, items, the check box and notices; 16px for phone cards; 999px for pills.
   - Card shadow: card rest. The card border appears only in dark themes.
   - Status pairs: Rejected `#fde8ea/#a1121f`. Add `provisional` and `superseded` classes (slate).
   - Request numbers in the list get `class="logbook-ref"`.
5. **Buttons:**
   - Replace `.leave-primary/.leave-success/.leave-warning/.leave-secondary` with `.leave-btn-primary` (accent `var(--app-primary)`, white text), `.leave-btn-outline` and `.leave-danger`.
   - Change `var(--app-accent,…)` to `var(--app-primary)`.
   - Reorder the footer per decision 3.
   - `applyLeave` / `clearLeaveForm` toggle the `hidden` attribute on Preview and Download instead of `disabled`.
   - Grep afterwards: `#1769e0`, `#168458` and `#f4b400` = 0.
6. **Focus and labels:**
   - `.leave-field :is(input,select,textarea):focus-visible` and `.leave-btn:focus-visible` get an accent border plus `0 0 0 .25rem var(--app-focus)`.
   - Add `for=` to every `.leave-field` label (ids exist).
   - Add `aria-label="Download <filename>"` to the icon-only attachment link.
7. **Phone:**
   - `.leave-segment { position: relative }` and `.leave-segment input { width: 1px; height: 1px }`.
   - At max-width 800px: segment labels, `.leave-btn` and the header button are at least 44px tall.
   - Done = `scrollWidth` is 375 at 375px.
8. **Kept functions and ids:** every `onclick` target is still defined. The ids `leaveStatus`, `leaveList`, `leaveFormCard`, `leaveSubmitBtn`, `leaveDeleteBtn`, `leavePreviewBtn`, `leaveDownloadBtn`, `leaveDeleteAllBtn` and `leaveFormToFollowBtn` still exist once each.

## Deliberately excluded

- Auto-running Check Conflicts on date change, and moving Form to Follow to its own entry point. These are the critique's open questions; the owner did not ask for them.
- List filters or search.
- Dark mode, which is Batch 4.

## Verification

- **Tests:** new `tests/test_leave_request_design.py` with these classes:
  - `LeaveKeptFunctionsTests`: functions, ids and the onclick guard.
  - `LeaveBatch3DesignTests`:
    - `request-page` and `dash-page-header` present, `leave-hero` absent;
    - the form card comes before the list card in the source;
    - weights ≤600, allowed radii only, and no hardcoded accent hex;
    - focus rules exist and labels have `for`;
    - the segment overflow fix is in place;
    - `.logbook-ref` is used in the list.
  - Positive control against `HEAD`'s template: the Batch 3 tests fail and the guard passes.
- **Focused run:** `tests/test_leave_request_*.py`, `test_provisional_leave`, `test_request_pages_header`, `test_appearance_themes`, `test_dark_mode_readability` and `test_changelog_coverage`. Add Leave to `test_request_pages_header.py`'s page list if it parametrises pages.
- **Browser** (copy of `scheduler.db`):
  - At 1366×768 and 375px, measure the header left edge and width against Cash Advance, and the first-input and Submit positions.
  - At 375px: no horizontal scroll and every visible tap target is at least 44px.
  - Tab through the form and check the focus ring shows.
  - Check that New Request, Save Draft, Submit (blocked without a signature is fine), Open, Upload, Delete Draft, Clear and Preview/Download still work.
  - Console clean.

## After implementation

1. Self-review: no used id or function removed.
2. Service worker `CACHE_VERSION` → the next free number, suffix `-leave-design`.
3. `releases.json`: release "Leave Request Form Comes First" (everyone).
4. DESIGN.md Page Header "Request pages" line: add Leave Request.
5. Update `changes.md` and this Status line.
6. Commit only the intended files.

## Risks

- `app-dashboard.css` header rules may clash with the page's old `.leave-head`. Keep `.leave-head` for card heads only.
- Moving the list changes where Open scrolls (`#leaveFormCard`, unchanged id). The browser check covers this.
- Blast radius: one template. Rollback = revert.

# Leave Request — Batch 2: Page Behaviour (busy lock, read-only records, Form to Follow saves first, rejection remarks, confirms)

**Status:** Executed — `56c75c8` on `main` (2026-10-13; owner: "execute batch 1 then 2", then "commit and push").
**Outcome differences:** `saveLeaveDraft` (guarded) now catches and returns `null` instead of rethrowing, so the Save button no longer leaves an unhandled promise rejection; inner callers use `saveLeaveDraftCore`, which still throws. `uploadLeaveAttachments` checks for selected files before it saves a new draft. A new `renderLeaveStatusNote` fills `#leaveStatusNote` via `textContent`; Rejected adds a red left edge (`.leave-status-note.rejected`). `.leave-btn[hidden]{display:none}` added so `hidden` beats `.leave-btn`'s `inline-flex`.
**Approved:** 2026-10-13 (see Batch 4).
**Detailed:** 2026-10-13.
**Branch:** `main` (local first; publish only on "commit and push").
**Depends on:** Batch 1 executed. The page relies on Batch 1's server messages and its Provisional delete block.

## Context

Page scan of `/leave_request` (2026-10-13). Confirmed on a copy of the database:
- Two quick Saves created two drafts (`saveLeaveDraft`, `templates/leave_request.html:103`, has no lock).
- Record Form to Follow on an opened record posts without saving, so it uses the saved type and dates and ignores the edits on screen (`:108`).
- Save Draft stays enabled on a Submitted record, and the server answers "This Leave Request is locked." (`applyLeave`, `:105`, disables only the inputs, Submit and Delete).
- The rejection remarks (`approval_remarks`, sent by `to_dict`, `leave_feature.py:396`) are never shown.
- Submit saves before it asks for confirmation (`:109`), so Cancel leaves the edits saved.
- Clear wipes the form with no confirm (`:116`).
- `showLeave` hides every notice after 7s and scrolls the page to it (`:90`).
- "Delete Draft" is shown for every editable status, including Provisional, which Batch 1 makes undeletable.

## Decisions taken

1. Owner: no deleting Provisional records, so the Delete button is hidden on Provisional.
2. Delete label by status: Draft → "Delete Draft"; Form to Follow and Rejected → "Delete Request".
3. Same busy-lock pattern as Cash Advance Batch 2 (`cashAdvanceBusy` / `setCashBusy` / `saveCashAdvanceDraftCore`).

## Execution steps

1. **Read first:** the newest `changes.md` section, and Cash Advance Batch 2's lock code in `templates/cash_advance.html` (copy the pattern).
2. **Busy lock:**
   - Add `let leaveBusy=false` and `setLeaveBusy(on, button, label)`. It disables every `.leave-btn` in `#leaveFormCard`, the Upload button and the list Open buttons, and shows a spinner label on the clicked button.
   - Split `saveLeaveDraft` into an unguarded `saveLeaveDraftCore(silent)` and the guarded `saveLeaveDraft(silent)`.
   - `submitLeave`, `recordFormToFollow`, `uploadLeaveAttachments`, `deleteLeaveAttachment`, `deleteAllLeaveAttachments` and `deleteLeaveDraft` return early when busy, set busy, and call the Core version inside, with `finally` clearing busy.
   - Done = a double click creates one record.
3. **Form to Follow saves first:** `recordFormToFollow` always calls `saveLeaveDraftCore(true)` when the record is editable, then posts. Done = the on-screen dates and type are what get recorded.
4. **Submit confirms first:** in `submitLeave`, call `confirm(...)` before the save.
5. **Read-only records:** new `applyLeaveEditState(editable, status)`, called from `applyLeave` and `clearLeaveForm`:
   - When not editable: disable Save Draft, Check Conflicts, Form to Follow, the file input and Upload. Keep Preview, Download and Clear.
   - Delete: hidden when not editable or when the status is Provisional, with the label from decision 2.
   - Give the footer buttons ids where they lack one: `leaveSaveDraftBtn`, `leaveCheckConflictsBtn`, `leaveClearBtn`, `leaveUploadBtn`.
6. **Status note:** add `<div id="leaveStatusNote" class="leave-status-note" role="status">` under the form head, filled by new `leaveStatusSentence(item)`:
   - Rejected: "Rejected by {rejected_by}: {approval_remarks}. Fix and resubmit."
   - Submitted: "Waiting for approval. Use Withdraw in the list to change it."
   - Approved: "Approved by {approved_by}." plus the HR handoff status.
   - Provisional: "Recorded on the Calendar by an administrator. Complete the form and submit it."
   - Form to Follow: "On the Calendar. Submit the signed form when you are back."
   - Draft or new: empty (note hidden).
   - Escape all text.
7. **Clear confirm:** `clearLeaveForm(silent)` asks "Discard the unsaved form?" only when there is no saved record and the reason, verbal notes or dates differ from the defaults. `deleteLeaveDraft` and the start-up call pass `silent=true`.
8. **Notices:** in `showLeave`, errors stay until the next notice (only `ok` and `info` auto-hide after 7s). Scroll only when the notice is outside the viewport.
9. **Kept functions:** every existing function name is still defined (the `onclick` guard), and `openRequestRecall` is still called from the list.

## Deliberately excluded

- Automatic conflict checks, and moving Form to Follow to its own entry point (not requested).
- Layout and colour (Batches 3–4).

## Verification

- **Tests:** new `tests/test_leave_request_page.py` (source checks plus a guard):
  - the lock exists and wraps every action;
  - `recordFormToFollow` calls `saveLeaveDraftCore`;
  - in `submitLeave`, `confirm(` comes before the save;
  - `applyLeaveEditState` disables Save Draft and hides Delete on Provisional;
  - `leaveStatusSentence` reads `approval_remarks`;
  - `clearLeaveForm` confirms;
  - errors do not auto-hide;
  - kept functions and onclick targets are defined.
  - Positive control against `HEAD`'s template: the checks fail and the guard passes.
- **Focused run:** `tests/test_leave_request_*.py`, `test_provisional_leave` and `test_request_recall`.
- **Browser** (copy of `scheduler.db`; seed Submitted, Rejected-with-remarks, Provisional and Form to Follow records on the copy):
  - double Save → 1 record;
  - Form to Follow after editing the dates on screen → the new dates are recorded;
  - Submitted → Save, Check Conflicts and Upload disabled, Delete hidden;
  - Rejected → the remarks are shown;
  - Provisional → no Delete;
  - Submit then Cancel → nothing saved;
  - Clear asks for confirmation only on an unsaved new form;
  - an error notice stays;
  - console clean.

## After implementation

1. Self-review.
2. Service worker → the next free number, suffix `-leave-page`.
3. `releases.json`: release "Leave Request Fixes" (everyone).
4. Update `changes.md` and this Status line.
5. Commit only the intended files.

## Risks

- A lock left on after an exception would freeze the page. Use `finally` everywhere; the browser check forces an error path (a bad date range).
- Blast radius: one template. Rollback = revert.

# Leave Request — Batch 1: Server Checks (65-day range, reason length, Form to Follow conflicts, no Provisional delete, no self-approval)

**Status:** Executed — `56c75c8` on `main` (2026-10-13; owner: "execute batch 1 then 2", then "commit and push").
**Outcome differences:** the save-time conflict check also runs for Rejected-with-emergency records (they rewrite the calendar too, as the plan said). The unknown-id 404 also covers another user's id (`find_header` returns `None`). Test users for provisional/approval are the named superadmins `jonamar`/`robert` on the module's own temp DB, because `create_provisional_leave_request` needs a named superadmin. `tests/test_leave_request_workflow.py` pinned the removed dead owner check; it now checks that submit uses `find_header(leave_id)`.
**Approved:** 2026-10-13 (see Batch 4).
**Detailed:** 2026-10-13.
**Branch:** `main` (local first; publish only on "commit and push").

## Context

Page scan of `/leave_request` (2026-10-13). Confirmed on a copy of the database:
- **No range or length limit:** a 2026-11-02 → 2036-11-02 range with a 5,000-character reason saved (`apply_payload`, `leave_feature.py:564`). Recording Form to Follow on it wrote 2,610 `Shift` rows. The PDF silently cuts the reason at 260 characters (`fill_pdf`, `:645-646`).
- **Form to Follow re-save skips the conflict check:** re-saving with new dates moves the calendar block (`save_leave_request`, `:873-876`) with no conflict check. It landed on a day with an existing "System Installation" shift, which `check-conflicts` reported.
- **Provisional re-save leaves the calendar stale:** saving a Provisional record with new dates does not move its calendar blocks (`:873` handles only Form to Follow and Rejected+emergency).
- **Employee can delete Provisional:** an employee can delete an admin-recorded Provisional record and its calendar blocks (`delete_leave_request_draft`, `:1341`, because `EDITABLE_STATUSES` includes Provisional).
- **Superadmin self-approval:** `can_approve` (`:335-339`) falls back to `role == 'superadmin'` without checking `header.user_id`. The approval routing settings refuse self-approval (`app.py:30233`).
- **Unknown id creates a draft:** saving with an id that does not exist or is not yours creates a new draft (`:851`) instead of returning 404.
- **HR resend too wide:** any scheduler, manager or admin role can resend the HR email for any approved leave (`resend_leave_request_hr`, `:1201`, via `is_management_user`, `:326`, used only there).
- **List queries grow per row:** `list_leave_requests` (`:798`) builds full `to_dict` per row: two `User` gets, a lazy attachments load and `can_approve` (an approver-routing query).
- **Dead code:** the unreachable owner check in submit (`:1056-1057`; `find_header` already requires the owner), and the unused `import json` (`:10`).

## Decisions taken (owner, 2026-10-13)

1. **Range:** at most **65 calendar days** (`end - start + 1 ≤ 65`), for every leave type.
2. **Past dates stay allowed** (sick leave filed after the fact).
3. **Provisional records cannot be deleted** from the Leave Request page.
4. **Self-approval is blocked for everyone**, superadmins included.
5. **Reason:** at most 260 characters, the space on the official form (`fill_pdf` fields `Textfield` + `Textfield1`).

## Execution steps

1. **Read first:** the newest `changes.md` section; `leave_feature.py` in full around the lines above; `tests/test_cash_advance_server.py` for the in-memory app/DB test setup to copy.
2. **Limits:**
   - Add the constants `MAX_LEAVE_CALENDAR_DAYS = 65` and `MAX_LEAVE_REASON_CHARS = 260` next to `MAX_ATTACHMENTS`.
   - Add a helper `leave_range_error(start_date, end_date)` that returns "Leave can cover at most 65 calendar days." when the range is longer, else `None`.
   - Call it in `apply_payload`, in `create_provisional_leave_request` (after the date checks) and in `check_leave_request_conflicts`.
   - `apply_payload` raises "Reason for leave can be at most 260 characters." when the reason is too long.
   - Done = the 10-year range and the 5,000-character reason return 400.
3. **Calendar edits re-check conflicts:**
   - In `save_leave_request`, when the record's calendar will be rewritten, run `conflicts(...)` with `exclude_leave_id=header.id` before `update_calendar`. That applies to status Form to Follow, Rejected with emergency, and **Provisional** (new: `update_calendar(header, 'Pending Approval')`).
   - On `blocking_schedules` or `overlapping_leave_requests`: roll back and return 409 with the conflict lists, matching `mark_leave_form_to_follow`.
   - Done = the re-save onto the System Installation day returns 409, and a Provisional date change moves its blocks.
4. **No Provisional delete:** in `delete_leave_request_draft`, return 409 "Provisional leave cannot be deleted. Complete and submit the form." when `header.status == 'Provisional'`.
5. **No self-approval:** `can_approve` returns `False` when `header.user_id == target.id`, before the role checks.
   - This also hides the approve buttons in `to_dict['can_approve']`, used by `templates/approvals.html:6364`.
   - The owner still sees and downloads their own record through `can_manage`.
6. **Unknown id:** in `save_leave_request`, when `payload.id` is given but `find_header` returns `None`, return 404 "Leave Request not found."
7. **HR resend:** the check becomes `can_approve(header) or is_superadmin_user()`. Delete `is_management_user` after a grep confirms zero other callers.
8. **Lighter list:**
   - Add `list_item_to_dict(header)` with `id`, `request_no`, `status`, `leave_type`, `date_range`, `duration_label`, `weekday_count`, `start_date` and `end_date`.
   - Use it in `list_leave_requests` only; the page list reads only these fields (`leave_request.html:102`).
   - `get_accounting_leave_request_queue`, the approvals routes and `to_dict` stay unchanged.
   - Done = the query count is the same for 2 and 10 records.
9. **Dead code:** remove `leave_feature.py:1056-1057` and `import json` (grep first).
10. **Kept functions:** every route and endpoint name is unchanged, and `ctx` keys (`leave_request_to_dict`, `can_approve_leave_request`, `update_leave_request_calendar`, …) are still set.

## Deliberately excluded

- Blocking past dates (owner decision 2).
- A limit on `verbal_approval_notes` (not a confirmed problem).
- `get_accounting_leave_request_queue`'s full-table summary. It belongs to My Requests, not this page.
- Who can remove a mistaken Provisional record. Approval of the formal request supersedes it, as today.

## Verification

- **Tests:** new `tests/test_leave_request_server.py` (copy the setup from `tests/test_cash_advance_server.py`):
  - 66-day range → 400 and 65-day → 200, on save, provisional and check-conflicts;
  - 261-character reason → 400;
  - a Form to Follow re-save onto a seeded shift → 409, with the calendar unchanged;
  - a Provisional re-save moves its `Shift` rows;
  - deleting Provisional → 409;
  - a superadmin approving their own Submitted leave → 404, with `can_approve` False;
  - another approver can still approve;
  - an unknown id on save → 404, with no new row;
  - HR resend by a plain scheduler → 404;
  - equal list query count for 2 and 10 records;
  - dead code gone;
  - a kept-functions/routes guard.
- **Positive control:** run against `git show HEAD:leave_feature.py` (load it in-process in the scratchpad; never `git stash`). The checks fail and the guard passes.
- **Focused run:** `tests/test_leave_request_*.py`, `test_provisional_leave`, `test_request_recall`, `test_approval_center_wording` and `test_my_requests_*`.
- **Full suite:** this changes an approval permission (AGENTS.md "Keep It Simple"). Run `venv/Scripts/python.exe scripts/run_suite.py` from the main folder; expect no new failures against `tests/known_failures.txt`.
- **Browser** (copy of `scheduler.db`, temporary password on the copy):
  - the scan's repro cases now return the server message on the page;
  - Save, Upload, Preview and Download still work;
  - console clean except the expected 4xx.

## After implementation

1. Self-review the diff: `leave_feature.py`, tests, version, changelog only.
2. Service worker `CACHE_VERSION` → the next free number, suffix `-leave-server`.
3. `releases.json`: release "Safer Leave Requests" (everyone).
4. Update `changes.md` and this Status line.
5. Commit only the intended files.

## Risks

- **Existing long records:** records already longer than 65 days or with reasons over 260 characters can no longer be re-saved until shortened. The error message says why.
- **Superadmin approvals:** a superadmin who relied on approving their own leave now needs another approver. This is intended (owner decision 4).
- **Blast radius:** the leave module only. Rollback = revert the commit.

# Request Pages — Uniform Header, New Request Button and Page Width (Travel, Cash Advance, Reimbursement)

**Status:** Executed — `ae3e2e0` on `main` (2026-10-13; owner: "execute", then "commit and push").
**Outcome differences:** `.cash-page` top padding 6px → 0 and `.reim-page` padding → `0 0 10px` (phone `0 0 12px`) so all three titles share the same top and left edge (measured identical at 1366, 1920 and 375px). `app-dashboard.css?v=` bumped 16 → 17 on the four pages that pinned 16 (`accounting_center`, `cash_advance`, `dashboard`, `travel_request`) plus Reimbursement, with the four pinned tests updated; `analytics.html` (`?v=75`) left as is. Release category "Cash Advance" (no shared "Requests" category exists). Owner spotted a grey block behind the Cash Advance header in dark mode: shared `app-dark-pages.css` painted `.cash-page` as a panel; removed from that list (`?v=34`), with a guard test.
**Approved:** 2026-10-13. The owner sent a Travel Request screenshot ("i like the format of travel request… apply this to reimbursement and cash advance"), narrowed the scope to "the header and also the new request button, placement and all… and also the margin on the left and right", then answered "a, approved". Option (a) caps Reimbursement's width like the other two pages.
**Detailed:** 2026-10-13.
**Branch:** `main` (local first; publish only on "commit and push").
**Size:** one batch, one commit.

## Context

The owner wants Travel Request, Cash Advance and Reimbursement to look the same at the top of the page:
- the same Page Header: the title with a status chip beside it, and a muted subtitle;
- the New Request button in the same place: under the subtitle, on the left;
- the same left and right margins: a page column capped at 1220px and centred.

Today the three pages differ. Travel matches the screenshot. Cash Advance has the same header, but its button sits on the far right and the page is full width. Reimbursement still has the old `reim-hero` banner, no header button, and is full width with 12px padding.

## Decisions taken

1. **Scope is the header, the header button and the page width only.** No Request Information card, no section-title icons, and no Cash Advance Status field. The owner narrowed the request; these were offered and declined.
2. **Option (a):** Reimbursement is capped at 1220px like the others. The worksheet table, which already scrolls sideways, gets narrower on wide screens. The owner accepted this.
3. **One source of truth:** a shared `.request-page` class in `static/css/app-dashboard.css`. It sets the width and the stacked header for all three pages, so there are no three page-local copies. This makes it shared code, so the full suite runs.
4. **Reimbursement has no "new request"** (each record is a date period). Its header button is **New Period** (`fa-plus`, outline). It calls the existing `expandReimbursementRangeCard(true)`, which reopens the date inputs and focuses Start Date.
5. **Reimbursement status chip:** mirrors the existing lifecycle status (Draft / Submitted / Approved / Rejected). It is set from `applyReimbursementStatusUi()`, so no new data or route is needed.

## Investigation

- `static/css/app-dashboard.css:2160` `.dash-page-header` is `display:flex; align-items:flex-end; justify-content:space-between; flex-wrap:wrap`. Its actions go right when there is room and wrap below when there isn't.
- Travel's button is below the subtitle only because the long subtitle forces a wrap (`templates/travel_request.html:210`). Cash Advance's short subtitle (`templates/cash_advance.html:506`) leaves room, so its button sits on the right. A wrap that depends on text length is the inconsistency.
- `templates/travel_request.html:6` `.travel-page { max-width: 1220px; margin: 0 auto; padding-bottom: 90px; }` is the margin the owner likes. Phone override: `travel_request.html:200`.
- `templates/cash_advance.html:6` `.cash-page { max-width: none; width: 100%; margin: 0 auto; padding: 6px 0 20px; }`. Cash Advance already links `app-dashboard.css?v=16` (line 4) and uses `.dash-page-header` (line 503).
- `templates/reimbursement.html`:
  - The page does not link `app-dashboard.css`.
  - `.reim-page` is `max-width:none; padding:10px 12px` (line 5; phone `padding:12px` at line 479).
  - `.reim-hero` markup is at line 3293. Its rules are at lines 12–30 (gradient, h1, p), 500 (phone padding), 2086 (in the shared `:is()` surface list), 2100 (raised surface override) and 2116 (`.reim-hero p` muted list).
  - Focus mode hides it at line 2717 (`body.reim-focus-active .reim-hero`).
- `expandReimbursementRangeCard(moveFocus)` is at `reimbursement.html:4633`. `applyReimbursementStatusUi()` is at `reimbursement.html:5935` (computes `status`).
- Tests that name `.reim-hero`: `tests/test_reimbursement_design.py:123` (surface `:is()` list) and `:467` (focus-mode selector). These are updated in step 5, deliberately, with the reason recorded.
- The service worker `CACHE_VERSION` is in `app.py` (checked by `tests/test_sw_cache_version.py`).

## Execution steps

1. **Shared rule:** in `static/css/app-dashboard.css`, after the `.dash-page-actions .btn` block, add:
   - `.request-page { max-width: 1220px; margin-left: auto; margin-right: auto; }`
   - `.request-page .dash-page-header { flex-direction: column; align-items: flex-start; }`
   - Bump the `app-dashboard.css?v=` query on every page that links it (grep `app-dashboard.css?v=` and bump all of them together).
   - Done: the rules exist once, and the header button sits under the subtitle at every width.
2. **Travel Request** (`templates/travel_request.html`):
   - The wrapper becomes `<div class="travel-page request-page">`.
   - Remove `max-width: 1220px; margin: 0 auto;` from `.travel-page`. Keep `padding-bottom` (it reserves space for the dock).
   - Done: no visible change, and the width now comes from the shared rule.
3. **Cash Advance** (`templates/cash_advance.html`):
   - The wrapper becomes `<div class="cash-page request-page">`.
   - Remove `max-width: none; width: 100%; margin: 0 auto;` from `.cash-page`. Keep the padding and colour.
   - Done: the page is centred at 1220px and New Request sits under the subtitle. No id or handler changes.
4. **Reimbursement** (`templates/reimbursement.html`):
   - a. Link `app-dashboard.css` with the same `?v=` as the other pages.
   - b. Replace `<section class="reim-hero">…</section>` with `<header class="dash-page-header reim-page-header">`. Inside it:
     - `<h1 class="dash-page-h1">Reimbursement <span id="reimStatusChip" class="reim-status-chip draft">Draft</span></h1>`;
     - the existing subtitle text in `<p class="dash-page-sub">`;
     - `<div class="dash-page-actions">` holding `<button type="button" class="btn btn-outline-primary" id="reimNewPeriodBtn" onclick="expandReimbursementRangeCard(true)"><i class="fa-solid fa-plus me-2"></i>New Period</button>`.
   - c. The wrapper becomes `<div class="reim-page request-page">`. Remove `max-width:none; width:100%; margin:0 auto` from `.reim-page`, and keep its padding.
   - d. Delete the now-unused `.reim-hero` visual rules (lines 12–30 and 500, plus the `.reim-hero` entries at 2086, 2100 and 2116).
     - Change the focus-mode selector at 2717 to `body.reim-focus-active .reim-page-header`, so focus mode still hides the header.
     - Grep afterwards: `reim-hero` must appear 0 times.
   - e. Add `.reim-page .dash-page-h1 { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }` and a small `.reim-status-chip` pill (999px radius, 0.78rem, weight 600). Use the same Semantic Status colours Travel's `travel-status-chip` uses for draft, submitted, approved and rejected, with dark-theme pairs like Cash Advance Batch 4.
   - f. In `applyReimbursementStatusUi()`, set `#reimStatusChip` text to `status` and its class to `reim-status-chip <normalized>`, null-guarded.
   - g. Phone (`max-width: 820px`): `.reim-page .dash-page-actions .btn { min-height: 44px; }`.
   - Done: the header matches the other two pages, New Period opens the date inputs, the chip follows the status, and focus mode hides the header.
5. **Tests:**
   - Update `tests/test_reimbursement_design.py:123`: the surface `:is()` list no longer includes `.reim-hero`; assert `.reim-hero` is absent instead.
   - Update `:467` to `.reim-focus-active .reim-page-header`.
   - Add a new `tests/test_request_pages_header.py`:
     - the shared `.request-page` rule (1220px, column header) exists once in `app-dashboard.css`;
     - each of the three templates has `request-page` on its wrapper and no page-local `max-width` on `.travel-page`, `.cash-page` or `.reim-page`;
     - Reimbursement has `dash-page-header`, `#reimStatusChip`, `#reimNewPeriodBtn` calling `expandReimbursementRangeCard(true)` and links `app-dashboard.css`;
     - kept-functions guard: every `onclick` function on the three pages is still defined, and `expandReimbursementRangeCard`, `collapseReimbursementRangeCard`, `applyReimbursementStatusUi`, `clearCashAdvanceForm` and `startNewTravelRequest` exist.
6. **Docs and skill:**
   - `DESIGN.md` Page Header section: add "Request pages (Travel Request, Cash Advance, Reimbursement): wrapper carries `.request-page` (1220px centred column, header button stacked under the subtitle on the left); Reimbursement's header button is New Period."
   - `.claude/skills/page-design-scan/SKILL.md`, Check item 3 (Consistency): add "Request pages (Travel Request, Cash Advance, Reimbursement, and any new request form) use the `.request-page` wrapper and the Page Header with status chip and the New Request / New Period button under the subtitle."

## Deliberately excluded

- **The Request Information card, section-title icons and the Cash Advance Status field.** The owner limited the scope to the header, the button and the margins.
- **Liquidation pages** (`travel_liquidation.html`, `cash_advance_liquidation.html`) and `reimbursement_tracker.html`. They were not requested; a later design scan can flag them using the new skill check.
- **The Reimbursement worksheet, its dock and the date card.** Only the width changes. Batch 4's collapse behaviour is untouched.
- **Changing `.dash-page-header` itself.** The dashboard and other pages keep the right-aligned actions; only `.request-page` stacks them.

## Verification

- **Positive control:** run the new test module and the two updated tests against `HEAD`'s templates and CSS. The structure tests must fail; the kept-functions guard must pass.
- **Focused tests:** `test_request_pages_header`, all `test_reimbursement_*`, all `test_cash_advance_*`, the travel request tests, appearance themes, dark-mode readability, layout sidebar, changelog coverage and the service worker tests.
- **Full suite** (this touches shared `app-dashboard.css`): `venv/Scripts/python.exe scripts/run_suite.py` from the main project folder. No new failures against `tests/known_failures.txt`.
- **Browser** (copy of `scheduler.db`, per AGENTS.md and the browser-check-setup memory):
  - At 1366×768 and 1920×1080, all three pages have the same column width and left edge (measure `getBoundingClientRect()` of `.dash-page-header`), and the header button's top is below the subtitle's bottom with the same left x as the title.
  - **Reimbursement:**
    - New Period reopens the date inputs with focus on Start Date;
    - the chip shows Draft, then Submitted or Rejected on such records;
    - focus mode hides the header;
    - Load, Save Draft, Submit, Upload and Change still work.
  - **Cash Advance:** New Request, Save and Submit still work.
  - **Travel Request:** New Request still works.
  - **375px:** no horizontal scroll, the header button is at least 44px tall, and the chip wraps cleanly.
  - **Dark (graphite and AMOLED):** chip text ≥4.5:1.
  - The console is clean.

## After implementation

1. Self-review the diff:
   - no removed id or function that is still used;
   - `reim-hero` is fully gone;
   - only the intended files are changed.
2. Service worker `CACHE_VERSION` in `app.py` → next `vNNN-request-page-header` (keep the previous version as a history comment).
3. `static/changelog/releases.json`: add a release "Same Header on Request Pages" (everyone).
4. `changes.md`: add an entry under today's date.
5. On "commit and push": commit only the intended files (never `scheduler.db`, `output/`, `tmp/` or handoffs), push `main`, and verify `git ls-remote` and Railway.
6. Update this Status line with the commit hash.

## Risks

- **Reimbursement worksheet on wide screens:** at 1220px, more columns need sideways scrolling. The owner accepted this (option a). Safety net: one rule to revert.
- **Shared CSS:** `.request-page` is new and opt-in, so other pages using `.dash-page-header` are unaffected. The full suite covers this.
- **Removing `reim-hero`:** a missed selector could leave focus mode showing the header. Covered by the grep in step 4d, the updated test and the browser check.

# Cash Advance — Batch 4: Dark Mode (pills, buttons, KPI note contrast, header and toasts on theme colours)

**Status:** Executed — `9f932cb` on `main` (2026-10-13; owner: "execute batch 3 and 4", then "commit and push").
**Outcome differences:** Batch 3 already moved the page to theme tokens, so most dark surfaces needed no page rule; dark rules were added only for pills, danger buttons and toasts. Submit with the purple accent measures 4.23:1 in every theme (white on `#8b5cf6`, the app-wide accent fill shared with `.btn-primary`); left unchanged as a shared accent decision.
**Approved:** 2026-10-13 (owner: "all approved" after the 2026-10-13 page scan and design scan of `/cash_advance`).
**Detailed:** 2026-10-13.
**Branch:** `main` (local first; publish only on "commit and push").
**Depends on:** Batch 3 executed (it rewrites the same `<style>` block and replaces the hero and KPI cards). Find code by selector, not line number.

## Context

The design scan (snapshot `.impeccable/critique/2026-10-13T03-12-30Z__templates-cash-advance-html.md`, 21/40, closed-list item 4) measured these problems in graphite and AMOLED:
- The status pills keep their light fills (`#dcfce7`, `#fee2e2`, `#fef3c7`, `#e0f2fe`).
- Clear Form stays `#fff` and Submit stays `#facc15`. Batch 3 changes Submit to the accent; this batch checks it.
- `.cash-kpi-note` stays `#64748b`: 3.69:1 on AMOLED `#191919` and 2.61:1 on graphite `#333438`. If Batch 3 has replaced the KPI cards with `.dash-stat`, this checks the replacement instead.
- The toasts keep their light fills.

Intended outcome: every text and pill reaches 4.5:1 in light, graphite and AMOLED, and nothing on the page stays a light block in dark mode (Tonal Dark Rule, Small-Text Contrast Rule).

## Decisions taken

1. Page-local: dark rules go in `templates/cash_advance.html` under the theme selectors that `app-dark-pages.css` already uses (`:root[data-app-theme="dark"]`, with graphite via `data-app-palette="graphite"`). `static/css/app-dark-pages.css` is not touched (shared file), the same as Reimbursement Batch 3.
2. Dark status pills: 16% tints of the semantic colour, with light text (green, red, amber, slate/blue), at least 4.5:1 on both dark grounds. Rejected stays red (Semantic Status Rule).
3. Toasts: `var(--app-surface)` ground with a semantic left border and `var(--app-text)` text in dark themes.

## Investigation

- `app-dark-pages.css` covers `.cash-card`, `.cash-page`, the notification, attachment and request items, titles, meta text and `.cash-btn-secondary` (lines ~560–860). It has no rule for `.cash-status-pill`, `.cash-btn-warning`, `.cash-btn-danger-outline`, `.cash-kpi-note` or `.cash-toast` (Assessment B, and a grep for `cash-` in `static/css/`).
- The theme attributes: `data-app-theme="dark"`, with graphite selected by `data-app-palette="graphite"` (`static/css/app-themes.css`).

## Execution steps

1. **Read first:** the newest `changes.md` section; DESIGN.md Colors (Semantic Status Rule), Typography (Small-Text Contrast Rule) and Elevation (Tonal Dark Rule); load the Impeccable skill (`polish`).
2. **Pills:** add dark pairs for `.cash-status-pill` and its `.draft`, `.submitted`, `.approved`, `.returned` variants, plus the Batch 3 Rejected KPI tone if present. Done = each pill ≥ 4.5:1 on both dark grounds.
3. **Buttons:** dark Clear Form (`.cash-btn-danger-outline`: transparent ground, red text ≥ 4.5:1, red 45% border) and the Batch 3 Withdraw style. Check Submit (accent) at 4.5:1. Done = no button keeps a `#fff` or `#facc15` ground in dark mode.
4. **Muted text:** `.cash-kpi-note` (or its `.dash-stat` replacement) and any other muted text below 4.5:1 → `var(--app-text-muted)` or the dark ink token. Done = every muted text ≥ 4.5:1 in graphite and AMOLED.
5. **Toasts and remaining light blocks:** apply decision 3, and fix the toast icon ground. Then walk the page in both dark palettes for any element whose computed background is still light. Done = none left.
6. **Kept functions:** `cashToast`, `setCashStatus`, `renderCashAdvanceList` and `renderCashAdvanceAttachments` are still defined, and their class names are unchanged.

## Deliberately excluded

- `app-dark-pages.css` edits (shared file; page-local rules are enough).
- Light-theme changes; those are Batch 3.

## Verification

- **Tests:** add class `CashAdvanceBatch4DarkTests` to `tests/test_cash_advance_design.py`. Source checks: a dark rule exists for each pill variant, `.cash-btn-danger-outline` and `.cash-toast`, and no `#facc15` remains. Add a kept-functions guard. **Positive control:** run against `git show HEAD:templates/cash_advance.html` in the scratchpad (never `git stash`); the dark-rule tests fail and the guard passes.
- **Focused run:** `tests/test_cash_advance_*.py`, `test_appearance_themes`, `test_dark_mode_readability`, `test_changelog_coverage`.
- **Browser** on a copy of `scheduler.db` (temporary test account on the copy only; seed one record in each status):
  - Measure the contrast of every pill, button, muted text and toast in light, graphite and AMOLED with the classic, green and purple accents.
  - At 375px AMOLED: no horizontal scroll, tap targets ≥ 44px.
  - Console clean. One screenshot per theme as proof. Clean up the copy, the account and the launch entry.

## After implementation

1. Self-review the diff: template, version, changelog and tests only.
2. Service worker `CACHE_VERSION` in `app.py` → the next free number, suffix `-cash-advance-dark`. Keep the previous value as a history comment.
3. `static/changelog/releases.json`: release "Cash Advance in Dark Mode" (everyone). Item: status labels and buttons are readable in the dark themes.
4. `changes.md` bullets, and update this plan's Status with any differences.
5. Commit only the files above plus `plans.md` and `changes.md`. Never `scheduler.db`, `output/`, `tmp/`, handoffs, `.impeccable/` or `.claude/`.

## Risks

- **Selector specificity against `app-dark-pages.css`:** page rules may lose to its `!important` overrides. The browser measurements catch it; match its selector form if needed.
- **Blast radius:** one template's CSS. Rollback = revert the commit.

---

# Cash Advance — Batch 3: Design System (Page Header, form first, Stat Cards, weights, radii, accent Submit, focus ring)

**Status:** Executed — `9f932cb` on `main` (2026-10-13; owner: "execute batch 3 and 4", then "commit and push").
**Outcome differences:** The status pill moved into the header (one status display); Request Date is kept as a hidden input plus "Requested MM-DD-YYYY" text; Clear Form became a quiet outline (Delete Draft keeps the red outline); colours moved to theme tokens as part of step 5; the light Rejected pill now uses the Semantic Status pair. Measured: first input y=235 at 1366×768 (was 1044).
**Approved:** 2026-10-13 (owner: "all approved"; page order "Form on top"; Submit colour "Accent primary").
**Detailed:** 2026-10-13.
**Branch:** `main` (local first; publish only on "commit and push").
**Depends on:** Batch 2 executed (same template; Batch 2 adds the read-only mode, the Liquidation button, the Delete Draft button and the Rejected count, which this batch styles). Find code by selector, not line number.

## Context

The design scan (21/40) found the page was never moved onto DESIGN.md:
- **Gradient hero:** `.cash-hero`, 2rem / weight 950, sits where the Page Header belongs.
- **Weights:** 750–950 are used (35 elements at 950). Fira ships 400/500/600.
- **Radii:** 14, 18 and 22px are used. DESIGN.md says 6px for controls, 10–12px for cards and 16px for phone cards.
- **KPI cards:** custom, not the `.dash-stat` Stat Card.
- **Yellow Submit:** `#facc15`. The toast icon and the shadows use a fixed blue `rgba(37,99,235)` (One Variable Rule).
- **Unstyled Withdraw:** `.cash-btn-danger` has no CSS, so it renders as a browser-default button.
- **No focus ring on fields:** `outline: none`, no `:focus` rule, and no `.form-control` class.
- **Form buried:** at 1366×768 the form card is at y=1044 and Submit at y=1916; on a phone they are at y=2013 and y=3634, on a 3757px page.
- **Noise:**
  - read-only Status and Request Date inputs repeat the status pill and today's date
  - the empty Notifications card is always shown
  - section icons mix yellow and blue
  - CA numbers are not in `.logbook-ref`

Closed-list items 1 (the lock behaviour is done in Batch 2), 2, 3, 5, 6 and 8.

Intended outcome: the page reads like Travel Request and My Requests. The form is the first thing under the header, and type, shape and colour follow DESIGN.md.

## Decisions taken

1. **Page order (owner): form on top.** Page Header, then the form card, then the Notifications card (only when there are unread notifications), then the Stat Cards and the "My Cash Advances" list.
2. **Submit (owner): accent primary.** `btn btn-primary`-style accent fill from `--app-primary`; the yellow is removed.
3. **Header:** `.dash-page-header`, with `.dash-page-h1` "Cash Advance" plus a status chip (the same pattern as Travel Request), and `.dash-page-sub` "Request cash for a job, subject to manager approval, accounting release and liquidation." Outline action "New Request", which calls `clearCashAdvanceForm()`.
4. **Stat Cards:** the four KPIs become `.dash-stat` cards (label, number, sentence). The Batch 2 Rejected count becomes a fifth card, toned red only above zero (Stat Cards tone rule). Linked through `app-dashboard.css?v=16`, as Travel Request does.
5. **Weights** 600 for titles, labels, buttons, chips and numbers; 400 for body, meta and help text. **Radii:** 6px controls, 10px cards and panels, 16px phone cards, 999px pills. **Shadows:** `var(--app-shadow)` or the card rest shadow; no `rgba(37,99,235,…)`.
6. **Remove duplicates:** the Status input goes (the chip shows status) and Request Date becomes plain text in the form meta ("Requested 10-13-2026"). The `cashAdvanceStatus` element id is kept as a hidden input, because `isCashAdvanceEditable()` and `setCashStatus()` read it.
7. Section-title icons are removed (the DESIGN.md card headings have no icon). CA numbers in the list and form use `.logbook-ref`.
8. Page-local: `templates/cash_advance.html`, so focused tests only.

## Investigation

- Travel Request's header pattern is at `templates/travel_request.html:207`; it links `app-dashboard.css?v=16` (`:4`). `.dash-page-header` is at `static/css/app-dashboard.css:2160` and `.dash-stat` at `:2205`.
- `cashAdvanceStatus` is read by `isCashAdvanceEditable()` and written by `setCashStatus()`, so it must survive as a hidden input.
- The page has 18 buttons on load (Assessment B), and phone tap targets already meet 44px. Keep `min-height: 44px` on phone buttons.

## Execution steps

1. **Read first:** the newest `changes.md` section; DESIGN.md Page Header, Stat Cards, Typography, Shapes, Buttons, Inputs and the One Variable Rule; load the Impeccable skill (`polish`, `layout`). Read `craft-floor.md` before editing.
2. **Header:** replace `section.cash-hero` with the `.dash-page-header` markup from decision 3, and link `app-dashboard.css`. Remove the `.cash-hero` CSS. Done = no `.cash-hero` and no gradient in the template.
3. **Order:** move `#cashFormCard` directly under the header. Then the Notifications card, hidden while the list is empty (`renderCashAdvanceNotifications` toggles a `hidden` attribute on the card). Then the stats and the list. Done = at 1366×768 the first form input is above y=768. Record the measured value.
4. **Stat Cards:** apply decision 4. `updateCashCounts` keeps its ids (`cashDraftCount` and the others, plus the Batch 2 Rejected id). Done = the cards use `.dash-stat` classes, and none of the forbidden class names (`-stat-value`, `-kpi-value`) are used.
5. **Type, shape and shadows:** apply decision 5 across the `<style>` block and any inline styles. Done = no `font-weight` above 600, no `border-radius` outside {6, 10, 16, 999px, 50%}, and no `rgba(37, 99, 235` in the file.
6. **Buttons:** Submit → accent (decision 2). Add a `.cash-btn-danger` rule for Withdraw: outline red, the same as Clear Form, because Withdraw can be undone. Order the footer as Clear Form (quiet outline, left), Delete Draft (Batch 2, red outline), Save Draft, Submit. Done = no `#facc15`, and Withdraw has a style.
7. **Focus:** `.cash-field input, textarea, select:focus-visible` → accent border plus `0 0 0 .25rem var(--app-focus)`. Remove `outline: none`, or pair it with the ring. Done = a keyboard tab shows a ring on every field.
8. **Duplicates and details:** apply decisions 6–7. Done = one status display, CA numbers in `.logbook-ref`, no `text-warning` / `text-primary` icons in section titles.
9. **Kept functions:** every function listed in Batch 2 step 9 is still defined, and every `onclick` target exists. Ids kept: `cashAdvanceId`, `cashAdvanceNo`, `cashAdvanceStatus` (hidden), `cashNeededDate`, `cashAmountRequested`, `cashLiquidationDays`, `cashRequestDate`, `cashPurpose`, `cashFormCard`, `cashAdvanceList`, `cashNotificationList`, the attachment ids and the count ids.

## Deliberately excluded

- Removing the list or the counts (owner chose form on top).
- Dark-theme pairs (Batch 4).
- A list filter or search (critique observation outside the closed list; My Requests already filters).

## Verification

- **Tests:** add class `CashAdvanceBatch3DesignTests` to `tests/test_cash_advance_design.py`. Source checks:
  - `dash-page-header` present and `cash-hero` gone
  - the form card comes before `#cashAdvanceList` in the markup
  - `dash-stat` classes present
  - weights ≤ 600, the allowed radii only, no `rgba(37, 99, 235`, no `#facc15`
  - a `.cash-btn-danger` rule and a `:focus-visible` field rule
  - `.logbook-ref` on CA numbers
  - a kept-functions and kept-ids guard

  **Positive control:** run against `HEAD`'s template in the scratchpad. The style tests fail and the guard passes.
- **Focused run:** `tests/test_cash_advance_*.py`, `test_appearance_themes`, `test_dark_mode_readability`, `test_layout_sidebar`, `test_changelog_coverage`.
- **Browser** on a copy of `scheduler.db`:
  - At 1366×768 light: the first input is above the fold. Save, Submit (with a test signature on the copy), Open, Withdraw, New Request, Upload, Delete and Delete All all work. Tab through the fields and see the ring.
  - At 375px: no horizontal scroll, taps ≥ 44px, the form near the top.
  - Console clean. One screenshot per width. Clean up the copy, the account and the launch entry.

## After implementation

1. Self-review the diff: template, version, changelog, tests, and DESIGN.md (add Cash Advance to the "Also used by" line under Page Header).
2. Service worker `CACHE_VERSION` → the next free number, suffix `-cash-advance-design`. Keep the previous value as a history comment.
3. `static/changelog/releases.json`: release "Cash Advance Form Comes First" (everyone). Items: the form is at the top, and the page matches the rest of the app.
4. `changes.md` bullets, and update this plan's Status.
5. Commit only those files plus `plans.md` and `changes.md`.

## Risks

- **Moving markup breaks a handler:** step 9's guard and the browser pass cover every button.
- **`app-dark-pages.css` targets `[class*="cash-"][class*="-card"]`:** renamed classes lose their dark overrides until Batch 4. Ship Batch 4 together with this batch, or check dark mode before publishing this batch alone.
- **Blast radius:** one template. Rollback = revert the commit.

---

# Cash Advance — Batch 2: Page Behaviour (double-submit lock, deep link, read-only records, counts, Liquidation and Delete Draft buttons)

**Status:** Executed — `897e193` on `main` (2026-10-13; owner: "execute batch 1 then 2", then "commit and push").
**Outcome differences:** "Received" also gets the "Received. Start or open the liquidation." sentence (it has a liquidation button); Liquidation Completed is not counted as Ready (treated as completed). Batch 1 and 2 browser checks were one combined pass; Submit was not exercised in the browser (no test signature; covered by server tests). The browser seed needed an Engineer profile with a Manila branch for Start Liquidation.
**Approved:** 2026-10-13 (owner: "all approved"; Delete Draft: "Yes, drafts only").
**Detailed:** 2026-10-13.
**Branch:** `main` (local first; publish only on "commit and push").
**Depends on:** Batch 1 executed (the new `delete_cash_advance_draft` route belongs to Batch 1). Find code by selector, not line number.

## Context

The 2026-10-13 page scan confirmed these in the browser:
- **Double-submit:** two quick Save Draft clicks on a new form created two drafts (CA-…-6 and CA-…-7). `saveCashAdvanceDraft` and `submitCashAdvance` have no in-flight lock, and the id only arrives after the response.
- **Deep link ignored:** `?cash_advance_id=N`, used by notifications and `detail_url`, is never read, so the form stays empty.
- **Withdraw on the wrong status:** Withdraw shows for "Liquidation Submitted", because the check is `statusKey.includes('submitted')`, but the server only recalls "Submitted".
- **Locked records editable:** a Submitted or Approved record opens with editable fields and live Save/Submit buttons; the server answers 409.
- **Wrong counts:** Rejected counts as Draft and Liquidation Submitted as Submitted.
- **Wrong status text:** a Rejected record reads "Submitted record loaded for review." (`lock_reason` is never sent).
- **No liquidation start:** there is no Start/Open Liquidation button, although `can_create_liquidation`, `create_liquidation_url` and `liquidation_url` are in the payload.
- **Clear Form:** clears without a confirm.
- **No draft delete:** there is no way to remove the duplicate drafts.

Intended outcome: the page cannot create duplicates, opens the linked record, shows only actions the server allows, and counts correctly.

## Decisions taken

1. **Delete Draft (owner): drafts only.** It is shown only when the opened record's status is Draft, needs a confirm, and calls the Batch 1 route. Rejected records are not deletable; they are corrections in progress with an audit trail.
2. **One busy flag** (`cashAdvanceBusy`) guards Save, Submit, Upload and Delete Draft. While it is set, the footer buttons are disabled and the clicked one shows a spinner label.
3. **Editable** means Draft or Rejected (the server's `editable` flag). Non-editable records:
   - Fields become `readOnly` (the date input becomes `disabled`).
   - Save Draft, Submit and Delete Draft are hidden.
   - A status sentence explains what happens next.
4. **Status sentences** by status:
   - Draft: "Draft. You can edit, save and submit."
   - Rejected: "Rejected by the approver. Edit and submit again." plus the approver's remarks when present.
   - Submitted: "Waiting for manager approval. You can withdraw it from the list."
   - Approved or Released: "Approved. Waiting for Accounting to release the cash."
   - Ready for Liquidation and the Liquidation statuses: "Received. Start or open the liquidation."
   - Anything else: "This request is locked."
5. **Counts:** Draft = Draft only. Submitted = Submitted only. Approved = Approved, Released or Received. Ready = Ready for Liquidation and the Liquidation statuses. A new **Rejected** count (Rejected or Returned). Completed is not counted.
6. **Liquidation button:** shown in the form when `can_open_liquidation` (link to `liquidation_url`) or `can_create_liquidation` (POST `create_liquidation_url`, then go to the returned `liquidation.liquidation_url`), using the same flow as `openCashAdvanceLiquidationDraft` in `accounting_center.html:1212`. List rows get the same button.

## Investigation

- **Save and submit:** `saveCashAdvanceDraft` (cash_advance.html:835) and `submitCashAdvance` (:867, which calls save first). The form id is set in `applyCashAdvanceRecord` (:904).
- **Load:** the `DOMContentLoaded` handler (:1241) calls `loadCashAdvances()` and `loadCashAdvanceNotifications()` and never reads `location.search`.
- **Withdraw:** rendered at :1022 and calls `openRequestRecall` from `_request_recall_modal.html`. Server rule: `recall_submitted_request` accepts status `submitted` only (`app.py` ~76885).
- **Counts:** `updateCashCounts` (:1030). The status values on a CA header include Liquidation Draft (`app.py` ~69802) and Liquidation Submitted (~70568).
- **Liquidation create:** `create_cash_advance_liquidation_draft/<id>` is POST and CSRF-exempt (`app.py` ~69902). The payload fields are in `cash_advance_to_dict` (~68403).
- **Existing pattern:** `accounting_center.html:1212` `openCashAdvanceLiquidationDraft` (create, then redirect).

## Execution steps

1. **Read first:** the newest `changes.md` section and Batch 1's outcome. Grep every function below before editing.
2. **Busy lock:**
   - Add `let cashAdvanceBusy = false;` and a `setCashBusy(isBusy, buttonEl, label)` that disables the footer and attachment action buttons.
   - Wrap `saveCashAdvanceDraft` (when not called from submit or upload), `submitCashAdvance`, `uploadCashAdvanceAttachments` and the new delete with an early return when busy, and use `try/finally`. `submitCashAdvance` sets busy once, around both its save and its submit.
   - Done = firing Save twice at once creates one record.
3. **Deep link:** in `DOMContentLoaded`, read `URLSearchParams(location.search).get('cash_advance_id')`; when it is a positive integer, `openCashAdvance(id)` after the list loads. Done = `/cash_advance?cash_advance_id=N` opens N.
4. **Withdraw:** change the condition to `statusKey === 'submitted'`. Done = no Withdraw on Liquidation Submitted.
5. **Read-only mode:** add `applyCashAdvanceEditState(item)`, called from `applyCashAdvanceRecord` and `clearCashAdvanceForm`, applying decision 3 to `cashNeededDate`, `cashAmountRequested`, `cashLiquidationDays` and `cashPurpose` and to the footer buttons. Use `item.editable` when present, else `isCashAdvanceEditable()`. Done = a Submitted record shows no Save or Submit and its fields cannot be typed in.
6. **Status sentence and counts:** replace the `lock_reason` line with decision 4. Rewrite `updateCashCounts` per decision 5, adding a `cashRejectedCount` card (markup next to the existing four; Batch 3 restyles it). Done = with one record in each status, each count is 1 and Rejected is not counted as Draft.
7. **Liquidation button:** add `#cashLiquidationBtn` to the form footer and a list-row button per decision 6, with `openOrCreateCashAdvanceLiquidation(item)`. Done = a Ready for Liquidation record shows "Start Liquidation", and one with a liquidation shows "Open Liquidation".
8. **Delete Draft and Clear Form:**
   - Add `#cashDeleteDraftBtn` (red outline, Draft only) with `deleteCashAdvanceDraft()`: a confirm "Delete draft CA-…? Its attachments are deleted too.", then POST to `/delete_cash_advance_draft/<id>`, then `clearCashAdvanceForm(true)` and `loadCashAdvances()`.
   - `clearCashAdvanceForm(silent)` asks "Clear the form? Unsaved changes are lost." when the form has values and no id. With `silent`, there is no confirm and no toast.
   - Done = the delete removes the row; Clear asks first.
9. **Kept functions:** every existing function stays defined, and every `onclick` target exists: `cashEscape`, `cashToast`, `getCashCsrfToken`, `todayInputValue`, `formatMoney`, `isCashAdvanceEditable`, `cashFileSize`, `renderCashAdvanceAttachments`, `updateCashAttachmentSelection`, `setCashStatus`, `collectCashAdvancePayload`, `validateCashAdvancePayload`, `parseCashJson`, `saveCashAdvanceDraft`, `submitCashAdvance`, `applyCashAdvanceRecord`, `clearCashAdvanceForm`, `uploadCashAdvanceAttachments`, `deleteCashAdvanceAttachment`, `deleteAllCashAdvanceAttachments`, `renderCashAdvanceList`, `updateCashCounts`, `loadCashAdvances`, `openCashAdvance`, the notification functions, `openEmbeddedLprModal`, `openRequestRecall`.

## Deliberately excluded

- Styling of the new buttons and the Rejected card beyond reusing existing classes (Batch 3).
- Deleting Rejected records (decision 1).
- A list filter or search (My Requests covers it).

## Verification

- **Tests:** new `tests/test_cash_advance_page.py` with source checks:
  - `cashAdvanceBusy` is guarded in the four functions
  - `cash_advance_id` is read from `location.search`
  - the Withdraw condition is an exact match
  - `applyCashAdvanceEditState` exists and is called from both places
  - `updateCashCounts` has a Rejected bucket and `cashRejectedCount` exists
  - `#cashLiquidationBtn` and `openOrCreateCashAdvanceLiquidation` exist
  - `#cashDeleteDraftBtn`, `deleteCashAdvanceDraft` and its route path exist
  - a confirm in `clearCashAdvanceForm`
  - the kept-functions guard (step 9)

  **Positive control:** run against `HEAD`'s template in the scratchpad (never `git stash`). The new checks fail and the guard passes.
- **Focused run:** `tests/test_cash_advance_*.py`, `test_request_recall`, `test_liquidation_pages`, `test_changelog_coverage`.
- **Browser** on a copy of `scheduler.db` (temporary engineer account; seed Draft, Submitted, Rejected, Approved, Ready for Liquidation and Liquidation Submitted records, and a test signature on the copy):
  - Fire Save twice at once: one record.
  - The deep link opens the record.
  - Withdraw appears only on Submitted.
  - Submitted and Approved records open read-only.
  - The counts are right.
  - Start Liquidation creates a draft and redirects.
  - Delete Draft removes a draft.
  - Clear asks first.
  - Console clean. Clean up the copy, the account and the launch entry.

## After implementation

1. Self-review the diff: template, tests, version and changelog.
2. Service worker `CACHE_VERSION` → the next free number, suffix `-cash-advance-page`. Keep the previous value as a history comment.
3. `static/changelog/releases.json`: release "Cash Advance Fixes" (everyone). Items: no duplicate requests from double clicks; links from notifications open the request; submitted requests open read-only; start liquidation from the page; delete drafts.
4. `changes.md` bullets, and update this plan's Status.
5. Commit only those files plus `plans.md` and `changes.md`.

## Risks

- **Submit calls save, and save must not deadlock on the busy flag:** use an internal `saveCashAdvanceDraftCore()` that skips the guard when called from submit or upload. The test checks a single guard per entry point.
- **Deep link to someone else's record:** the server already returns 404, and the page shows the error toast.
- **Blast radius:** one template's JS. Rollback = revert the commit.

---

# Cash Advance — Batch 1: Server Checks (amount/days/date validation, server request date, CSRF on attachments, draft delete route, lighter list, dead code)

**Status:** Executed — `897e193` on `main` (2026-10-13; owner: "execute batch 1 then 2", then "commit and push").
**Outcome differences:** added `cash_advance_amount_error` and a shared `cash_advance_liquidation_fields` (used by both `cash_advance_to_dict` and the new list builder, so the liquidation rule has one source). The list query-count test warms up once first (the first request runs one-time table checks). Full suite: no new failures.
**Approved:** 2026-10-13 (owner: "all approved"; Delete Draft: "Yes, drafts only").
**Detailed:** 2026-10-13.
**Branch:** `main` (local first; publish only on "commit and push").

## Context

The 2026-10-13 page scan found these on a database copy:
- **`inf` amount:** saved and returned as `Infinity`, which is invalid JSON. The user's list then fails to load and prints raw JSON. Once submitted, it would also break the approver's queue.
- **`nan` amount:** saved as 0 (NULL), skipping the "greater than zero" check.
- **`inf` liquidation days:** a 500 error (`OverflowError` at `int()`).
- **Past dates:** a Date Needed of 2020-01-01 is accepted.
- **Request Date:** taken from the client.
- **Wording:** the error text says "Draft or Returned", but the status is "Rejected".
- **CSRF:** upload, delete and delete-all attachment routes are `@csrf.exempt` although the page sends the token.
- **No delete-draft route.**
- **Slow list:** `get_cash_advance_list` builds every record with `cash_advance_to_dict`, about 6 extra queries per record (approvers twice, three users, the liquidation table check and lookup), and sends signature images the list never shows.
- **Dead code:** `cash_advance_requester_profile` and `cash_advance_user_display_name` have no callers.

## Decisions taken

1. **Amount:** must be finite, > 0 and ≤ 10,000,000.00 (an upper bound against typos; one place, `CASH_ADVANCE_MAX_AMOUNT`). Liquidation days: an integer 1–365; anything else → 400 "Liquidation period must be 1 to 365 days."
2. **Date Needed:** must be today (Manila) or later when saving or submitting. Existing older drafts get the same message on save, which tells the user to pick a new date.
3. **Request Date:** set by the server: today on create, and kept on update (never taken from the client).
4. **CSRF:** remove `@csrf.exempt` from `upload_cash_advance_attachments`, `delete_cash_advance_attachment` and `delete_all_cash_advance_attachments`. The page already sends `X-CSRFToken`.
5. **New route** `POST /delete_cash_advance_draft/<id>` (not exempt):
   - Owner only, status Draft only (409 otherwise).
   - Deletes the attachments (DB plus storage, as `delete_all_cash_advance_attachments` does), the linked LPRs (`delete_linked_lprs_for_parent('cash_advance', id)`), the audit rows and the header in one commit.
   - Writes an activity log entry.
   - Pattern: `delete_travel_request_draft` (`app.py` ~43760).
6. **List payload:** a new `cash_advance_list_item_to_dict(header, liquidation_by_ca)` with the fields the page reads (`id`, `cash_advance_no`, `status`, `needed_date`, `amount_requested`, `purpose`, `editable`, the liquidation fields). Liquidations are loaded in one query for all listed ids. `ensure_cash_advance_liquidation_tables()` runs once per request. `cash_advance_to_dict` is unchanged for the other callers.
7. **Wording:** "Only Draft or Rejected cash advances can be edited." / "…submitted."

## Investigation

- **Helpers and routes in `app.py`:**
  - `cash_advance_money` (~67072): `round(float(...))` lets nan/inf through.
  - `save_cash_advance` (~68719): the checks at ~68733 and the `liquidation_days` parse at ~68730.
  - `submit_cash_advance` (~68789): re-checks only `> 0`.
- **`cash_advance_money` callers:** used widely (the liquidation, accounting and PDF code). Do **not** change it. Add a separate `cash_advance_parse_amount(value)` that returns `None` for non-finite input, and use it only in save.
- **Old records:** `submit_cash_advance` should also reject a non-finite stored amount, for records saved before the fix.
- **CSRF setup:** global `CSRFProtect` (`app.py:881`); `save_cash_advance` and `submit_cash_advance` already enforce the token (confirmed 400 without it).
- **List fields:** read by the page (`renderCashAdvanceList`, `updateCashCounts`) and by the Batch 2 liquidation button: `id`, `cash_advance_no`, `status`, `needed_date`, `amount_requested`, `amount`, `purpose`, `editable`, `can_create_liquidation`, `can_open_liquidation`, `create_liquidation_url`, `liquidation_url`. Grep `templates/` and `static/` for other `/get_cash_advance_list` readers before trimming.
- **Dead functions:** zero callers confirmed by grep across `app.py`, `templates/` and `tests/`.

## Execution steps

1. **Read first:** the newest `changes.md` section. Grep each function before editing.
2. **Parsing:** add `CASH_ADVANCE_MAX_AMOUNT = 10_000_000` and `cash_advance_parse_amount(value)` (finite float rounded to 2 places, else `None`) next to `cash_advance_money`. In `save_cash_advance`:
   - Use it for the amount.
   - Parse `liquidation_days` with `try: int(float(...))` plus `math.isfinite` and the 1–365 range.
   - Add the Date Needed ≥ `get_manila_today()` check.
   - Set `request_date` per decision 3.
   - Fix the wording.

   Done = `nan`, `inf`, `-5` and `20000000` amounts → 400; `inf` days → 400; yesterday → 400; a client `request_date` is ignored.
3. **Submit:** reject a non-finite or out-of-range stored amount and a past Date Needed with 400 and clear messages; fix the wording. Done = an old `inf` record cannot be submitted.
4. **CSRF:** apply decision 4. Done = the three routes return 400 without the token and 200 with it.
5. **Delete route:** apply decision 5. Done = a Draft is deleted with its attachments and linked LPRs; non-owner → 404; non-Draft → 409; no token → 400.
6. **List:** apply decision 6 in `get_cash_advance_list`. Done = the query count for 10 records is the same as for 2 (within a fixed constant), and the response has no signature fields.
7. **Dead code:** delete `cash_advance_requester_profile` and `cash_advance_user_display_name` after a final grep shows zero callers.
8. **Kept functions:** `cash_advance_money`, `cash_advance_to_dict`, `can_user_manage_own_cash_advance`, every existing cash advance route and endpoint name are unchanged.

## Deliberately excluded

- Changing `cash_advance_money` (shared by liquidation, accounting and PDF code).
- The approval-side routes (`approve_cash_advance`, `reject_cash_advance`, `resend_…`): outside the page's scope, and they work.
- A Date Needed rule beyond "not in the past" (no business rule given).

## Verification

- **Tests:** new `tests/test_cash_advance_server.py`, HTTP on a temporary SQLite DB with the test client, the same setup as `tests/test_reimbursement_batch1_fixes.py`. It covers:
  - the save rejections in step 2 (and that `request_date` is the server's today)
  - submit rejecting an `inf` stored record
  - the CSRF on/off cases for the three attachment routes, with storage patched
  - delete-draft: success, non-owner, non-Draft and no token
  - the list query count being equal for 2 and 10 records, with no `requester_signature_snapshot` key
  - a source check that the two dead functions are gone, and a kept-functions guard

  **Positive control:** run the module against `HEAD`'s `app.py` in the scratchpad (never `git stash`). The fix tests fail and the guard passes.
- **Focused run:** `tests/test_cash_advance_*.py`, `test_liquidation_pages`, `test_accounting_attachment_management`, `test_request_recall`, `test_changelog_coverage`.
- **Full suite** once before publishing: removing the CSRF exemptions changes the request-protection behaviour (auth/permissions, per AGENTS.md). Run it in the main folder: `venv/Scripts/python.exe scripts/run_suite.py`.
- **Browser** on a copy of `scheduler.db`:
  - Save, Upload, Delete and Delete All still work from the page (token sent).
  - Bad amounts show the server message in the toast.
  - The list loads.
  - Console clean. Clean up the copy, the account and the launch entry.

## After implementation

1. Self-review the diff: `app.py` and the tests only (plus the version, changelog and journals).
2. Service worker `CACHE_VERSION` → the next free number, suffix `-cash-advance-server`. Keep the previous value as a history comment.
3. `static/changelog/releases.json`: release "Safer Cash Advance Saving" (everyone). Item: amounts, dates and liquidation days are checked before saving.
4. `changes.md` bullets, and update this plan's Status.
5. Commit only `app.py`, the tests, `releases.json`, `plans.md` and `changes.md`. Never `scheduler.db`, `output/`, `tmp/`, handoffs, `.impeccable/` or `.claude/`.

## Risks

- **Existing drafts with a past Date Needed** can no longer be saved without a new date. The message says so, and this is intended (decision 2).
- **CSRF removal:** any other caller of the three attachment routes without the token would break. Grep `templates/` and `static/` for those paths first; only `cash_advance.html` is expected.
- **List payload trim:** a reader of a dropped field would break. The grep in Investigation and the browser pass cover it.
- **Blast radius:** the cash advance save, submit, attachment and list routes. Rollback = revert the commit.

---

# Reimbursement — Batch 4: Design System + Worksheet Above the Fold (weights, radii, sizes, shadows, collapsed date card)

**Status:** Executed — published to `main` on 2026-10-13 on the owner's "commit and push" (commit `87fbe7c`; owner: "execute batch 4" the same day). Tests: 6 added (5 fail on `HEAD`, guard passes); focused run 264 OK. Browser check on a DB copy passed except the fold target below.
**Measured outcome (steps 5–6):** at 1366×768 the first Draft row moved from y≈962 to 726 with the collapsed card (58px) and the Draft reason hidden; the dock is at 692, so a Draft is still 34px short. A Submitted record's first row is at 689 (above the dock). The remaining height is the worksheet top bar, summary, Manual Adjustments card and row-selection toolbar; per step 6 the scope was not widened.
**Differences from plan:** controls that were 10px (inputs, selects, `.reim-btn`) also went to 6px under decision 3; a 0.7rem focus-mode label went to 0.72rem (done criterion); the toast, focus More panel, focus panels and readiness sheet were over 28px blur too and were brought in (readiness sheet keeps an upward `0 -8px 24px` because it sits on the dock).
**Approved:** 2026-10-13 (owner chose batches 1–4 after the 2026-10-13 page scan and design scan; layout: "Collapse after load").
**Detailed:** 2026-10-13.
**Branch:** `main` (local first; publish only on "commit and push").
**Depends on:** Batch 3 executed (same `<style>` block). Find code by selector, not line number.

## Context

The closed list of the 2026-10-13 design scan (snapshot `.impeccable/critique/2026-10-13T00-28-28Z__templates-reimbursement-html.md`, 23/40) leaves three items for this batch:

- **Item 2 (P1).** The worksheet starts below the fold. With a record loaded at 1366×768, the table top is at y≈668 and the dock at y=692, so no rows are visible. On a phone the first row card is at y=1366. The page is 4249px tall.
- **Item 5 (P2).** Font weights 750–950 are used, with 31 declarations of 800/900. DESIGN.md Typography says Fira Sans ships 400/500/600 and anything above renders as 600.
- **Item 7 (P3).** Off-system values: radii 8px (`.reim-amount`), 9px (`.reim-readiness-item`) and 22px (`.reim-dialog`). Font sizes 0.6rem (focus-mode `.reim-summary-label`) and 0.68rem (focus-mode column-view label). Four cards pair a hairline border with a wide shadow: `.reim-manual-card` (70px blur), `.reim-dialog` (90px), `.reim-view-popover` (46px), `.reim-row-details-card` (70px).

Intended outcome:
- Once a record or range is loaded, the worksheet's first row is visible at 1366×768 without scrolling.
- The page's type and shape follow DESIGN.md.
- Behaviour is unchanged.

## Decisions taken

1. **Layout (owner):** collapse after load. After a successful load, the date card shrinks to a one-line period bar ("07-01-2026 – 07-31-2026" plus a Change button). Change reopens the full card. The Notifications and Status (history) cards already sit below the worksheet (Investigation), so they stay where they are.
2. Weights: **600** for titles, labels, buttons, chips and totals; **400** for body, help and meta text. Nothing above 600.
3. Radii:
   - 6px for controls.
   - 10px for cards and panels.
   - 12px for the dialog and popovers.
   - 16px for cards on phones (≤768px).
   - 999px for pills.
4. Sizes:
   - 0.6rem and 0.68rem → 0.72rem (the micro step; Small-Text Contrast Rule).
   - Off-ramp title sizes (1.35, 1.22, 1.15, 1.1rem) stay. They are not in the closed list.
5. The four wide shadows become the DESIGN.md Panel shadow (`var(--app-shadow)`). The hairline border stays only in dark themes, per Cards.
6. Page-local: `templates/reimbursement.html` only, so focused tests. The Page Header (`.dash-page-header`) is **not** adopted. It was not in the closed list.

## Investigation

- **Section order** (`templates/reimbursement.html`):
  1. `section.reim-hero` (:3217, 143px tall)
  2. `#reimFilterCard` (:3252, 275px): Start/End inputs plus Load Schedules, This Week and This Month.
  3. `section.reim-table-card` (:3274). It holds:
     - the lifecycle banner `#reimLifecycleBanner` (138px)
     - `#reimSubmitNotice`
     - the signature panel
     - the worksheet top bar
     - the table and receipts
  4. `#reimNotificationCard` (:3531)
  5. `#reimStatusWindowCard` (:3548)

  History is already below the worksheet.
- **Who uses `#reimFilterCard`:** it is also a focus-mode panel (`reim-focus-managed-panel`, with Close via `closeReimbursementFocusPanel()`). The collapse must not break focus mode: the focus toolbar's Dates button opens this panel.
- **Successful loads** set `reimbursementActiveContext = reimbursementCurrentContext()` in `loadReimbursementRows` (:7818; assignments at :7883, :8003, :8037). That is the hook for collapsing.
- **Weights** above 600 are found throughout the `<style>` block (Assessment A count). DESIGN.md Typography confirms the 400/500/600 rule.

## Execution steps

1. **Read first:**
   - the newest `changes.md` section
   - DESIGN.md Typography, Shapes, Cards and Elevation
   - load the Impeccable skill (`polish`, and `layout` for step 5)
2. **Weights:** apply decision 2 across the page `<style>` block and the inline styles. Done = no `font-weight` above 600 in the template, and nothing below 600 on a title, label, button or total.
3. **Radii:** apply decision 3. Done = no `border-radius` outside {6px, 10px, 12px, 16px, 999px, 50%}.
4. **Sizes and shadows:**
   - 0.6rem and 0.68rem → 0.72rem.
   - Replace the four wide shadows with `var(--app-shadow)`, and keep their border only under the dark theme selectors.
   - Done = no font size below 0.72rem, and no `box-shadow` blur above 28px in the block.
5. **Collapsed date card:**
   - Add `#reimRangeSummary` inside `#reimFilterCard`, hidden by default. It holds the period text and a `Change` button (`reim-btn reim-btn-secondary`, 44px on phones) wired to `expandReimbursementRangeCard()`.
   - After a successful load, call `collapseReimbursementRangeCard()`. It adds `.reim-range-collapsed` and fills the period with `formatExpenseDate(start) – formatExpenseDate(end)`.
   - CSS: `.reim-range-collapsed .reim-filter-grid { display: none; }` and `.reim-range-collapsed #reimRangeSummary { display: flex; }`.
   - Focus mode's Dates panel calls `expandReimbursementRangeCard()` when it opens.
   - Done = after Open Record at 1366×768, the first worksheet row's top is above the dock. Change shows the inputs again with their values, and Load Schedules still works.
6. **If step 5 alone does not bring the first row above the dock at 1366×768:** compact the lifecycle banner for Draft only (hide `#reimLifecycleReason` when the status is Draft). Record the measured outcome under this plan, whichever it is. Do not widen the scope further.
7. **Kept functions:** `loadReimbursementRows`, `setReimbursementThisWeek`, `setReimbursementThisMonth`, `openReimbursementStatusRecord`, `closeReimbursementFocusPanel`, `toggleReimbursementFocusPanel`, and every id in Investigation are still defined and wired.

## Deliberately excluded

- **Page Header adoption, the red filled Withdraw button, and help text for PC codes and categories:** critique observations outside the closed list.
- **Off-ramp title sizes and the ~40 page-local status tints** (detector-only).
- **The history list's 20-item limit** (page-scan finding): the 20 newest cover normal use. It can be raised later if the owner asks.

## Verification

- **Tests:** new class `ReimbursementBatch4SourceTests` in `tests/test_reimbursement_design.py`. It checks:
  - no weight above 600
  - only the allowed radii
  - no font size below 0.72rem
  - no shadow blur above 28px
  - `#reimRangeSummary`, `collapseReimbursementRangeCard` and `expandReimbursementRangeCard` exist, and the load path calls the collapse
  - a kept-functions guard (step 7)

  **Positive control:** run the class against `git show HEAD:templates/reimbursement.html` in the scratchpad (never `git stash`). The style and collapse tests fail; the guard passes. Update any existing design test that pins old weights or radii on purpose, and list it in `changes.md`.
- **Focused run:** `tests/test_reimbursement_*.py`, `test_appearance_themes`, `test_dark_mode_readability`, `test_layout_sidebar`, `test_changelog_coverage`.
- **Browser** on a copy of `scheduler.db` (temporary password on the copy only):
  - At 1366×768 light: open a record. The first row is above the dock (measure `getBoundingClientRect`). Change, This Week, This Month, Load Schedules and the focus-mode Dates panel all work.
  - Graphite and AMOLED: cards show their hairline with no wide shadow.
  - At 375px: no horizontal scroll, Change is 44px, and the collapsed bar is one line.
  - Console clean. One screenshot per width. Clean up the copy and the launch entry.

## After implementation

1. **Self-review the diff.** Only the template, plus versions, changelog, DESIGN.md (if needed) and tests.
2. **Service worker:** `CACHE_VERSION` in `app.py` → the next free number, with suffix `-reimbursement-design`. Keep the previous value as a history comment.
3. **`static/changelog/releases.json`:** release "Reimbursement Worksheet Comes First" (everyone). Items: the date range folds into one line after loading, so the worksheet is in view; text and corners match the rest of the app.
4. **`changes.md`:** add the bullets. Update this plan's Status and record any differences.
5. **Commit** only the files above plus `plans.md` and `changes.md`. Never `scheduler.db`, `output/`, `tmp/`, handoffs, `.impeccable/` or `.claude/`. Publish only on "commit and push".

## Risks

- **Focus mode and the date card:** the Dates panel shares `#reimFilterCard`, so a collapsed card could open empty. Step 5 expands it on open; the browser pass checks it.
- **Weight changes flatten hierarchy:** the 600/400 split keeps titles distinct. Checked visually in the final screenshot.
- **Blast radius:** one template's CSS plus two small JS functions. Rollback = revert the commit.

---

# Reimbursement — Batch 3: Design Fixes (dark banners, total contrast, Submit confirm, duplicates, locked selection)

**Status:** Executed — published to `main` on 2026-10-13 on the owner's "commit and push" (commit `3623c38`; owner: "execute batch 3" the same day). Tests: 6 added (5 fail on `HEAD`, guard passes); focused run 323, only the known TSR failure. Browser check on a DB copy passed (lowest contrast 5.97:1).
**Differences from plan:** the "0 selected" count is also hidden on locked records (otherwise it stood alone); the zoom duplicate was the hidden `<label>` — the visible span became the label instead; the phone-card `<span>` shows the category (the date is already in the first span).
**Approved:** 2026-10-13 (owner chose batches 1–4 after the 2026-10-13 page scan and design scan).
**Detailed:** 2026-10-13.
**Branch:** `main` (local first; publish only on "commit and push").
**Depends on:** Batches 1–2 executed. Find code by selector, not line number.

## Context

This batch covers critique closed-list items 1, 3, 4, 6 and 8 (snapshot `.impeccable/critique/2026-10-13T00-28-28Z__templates-reimbursement-html.md`):

1. **(P1) Light banners in dark mode.** The Submitted, Approved and Rejected banners hardcode light fills (`.reim-lifecycle-banner.submitted/.approved/.rejected`, `templates/reimbursement.html:1690-1703`). Only `.draft` has a dark override (`static/css/app-dark-pages.css:1087`). Measured in dark: `#fffbeb` on a `#292a2d` page. This breaks the Tonal Dark Rule.
3. **(P2) Accent used as money text, below 4.5:1.**
   - `#reimDockTotal` (`.reim-dock-total`, `color: var(--app-primary, #0f5132)`, :628) measures 3.17:1 in dark.
   - `#reimSummaryGrandTotal` (`.reim-summary-total .reim-summary-value`, `color: var(--app-primary, #198754)`, :1240) measures 4.33:1 in light.
   - `.reim-grand-total-cell` (:497) hardcodes a `#0f5132 → #198754` gradient. That breaks the One Variable Rule for other accents.
4. **(P2) The Submit confirm** (`submitReimbursement`, the `reimConfirmDialog` call at :7568) shows neither the ₱ total nor the period being committed.
6. **(P3) Duplicate text:**
   - The lock sentence appears both in `#reimLifecycleReason` and in the worksheet subtitle `#reimStatusText`.
   - "Worksheet zoom" is visible twice.
   - Manual rows' phone cards print the task twice: the `<h3>` at :5569 and the `<span>` at :5573.
8. **(P3) Selection controls on locked records:** Select all, Delete selected (0) and the row checkboxes still show on a Submitted, Approved or Paid record.

## Decisions taken

1. **Dark banner pairs, page-local:** add them to the template's `<style>` block under the same `:root[data-app-theme="dark"]` selector the draft rule uses, rather than editing shared `app-dark-pages.css`. Colours are semantic (Semantic Status Rule), not the accent:
   - Submitted: amber `rgba(245,158,11,.12)` fill, `rgba(245,158,11,.45)` border.
   - Approved: green `rgba(34,197,94,.12)` / `rgba(34,197,94,.45)`.
   - Rejected: red `rgba(239,68,68,.12)` / `rgba(239,68,68,.45)`.
   - Banner text `var(--app-text)`.
2. **Money totals** use `var(--app-primary-text)`, which is dark-aware.
3. **Grand-total cell:** `background: var(--app-primary-soft); color: var(--app-text); border-top: 2px solid var(--app-primary)`. No gradient.
4. **Confirm dialog** adds one line before the existing message: "Period: <start> – <end> · Total: ₱<amount>".
5. **Locked records** hide the selection controls. They are not just disabled.

## Investigation

- **Banner class switching:** `renderReimbursementLifecycleBanner()` (:5770) sets `banner.className = 'reim-lifecycle-banner show <cssClass>'` and writes `#reimLifecycleReason`.
- **Lock-state function:** it sits just above, around :5836. It toggles `.reim-page.reim-locked` (:5843) and also writes `#reimStatusText`. That is where the duplicate sentence comes from; the executor confirms the exact assignment.
- **`--app-primary-text`** (`static/css/app-themes.css`) is the strong accent in light, and the accent mixed 60% with white in dark (Travel Request Batch 4 investigation).
- **Selection controls:** `#reimSelectAllRows` (:3444), `.reim-row-select` (:5528, :5566) and the Delete selected button. `setReimbursementSubmitInputsBusy` (:7165) lists these selectors and must keep working.
- **Zoom control (:3424-3428):**
  - visible span `.reim-zoom-label`
  - `visually-hidden` label `for="reimZoomLevel"`
  - `aria-label` attributes

  The executor measures which copy is actually visible twice (Assessment A counted two visible copies) and keeps one visible label plus the accessible name.

## Execution steps

1. **Read first:** the newest `changes.md` section, and DESIGN.md Colors (Tonal Dark, One Variable, Semantic Status, Small-Text Contrast).
2. **Dark banners** (decision 1). Done = in graphite and AMOLED, Submitted, Approved and Rejected banners sit on dark tints, and their text is ≥4.5:1.
3. **Totals** (decisions 2–3) on `.reim-dock-total` (including the focus-mode and phone variants at :828 and :861), `.reim-summary-total .reim-summary-value`, and `.reim-grand-total-cell` (including the variant at :522). Done = ≥4.5:1 in light, graphite and AMOLED with the classic, green and purple accents. No `#0f5132` or `#198754` is left in these rules.
4. **Confirm dialog** (decision 4). In `submitReimbursement`, build the line from `reimbursementActiveContext.start/end` (formatted with `formatExpenseDate`) and the same total the dock shows (`#reimDockTotal` text, or the function that fills it near :3864). Done = the dialog reads "Period: 07-01-2026 – 07-31-2026 · Total: ₱123.45" before the existing text.
5. **Duplicates:**
   - The lock-state function stops writing the lock reason into `#reimStatusText`. Its own progress messages (loading, saved, submitted) stay.
   - Keep one visible "Worksheet zoom" label.
   - On manual rows' phone cards, the `<span>` at :5573 shows the date or category instead of repeating the task.
   - Done = each text appears once (measure with `innerText` counts).
6. **Locked selection:** add `.reim-page.reim-locked` rules that hide `.reim-row-selection-control`, the Delete selected button and `.reim-row-select`. Done = hidden on a Submitted record, and visible again on a Draft.
7. **Kept functions:** `renderReimbursementLifecycleBanner`, `submitReimbursement`, `reimConfirmDialog`, `setReimbursementSubmitInputsBusy`, `handleReimbursementSelectAllRows` and `handleReimbursementRowSelection` are still defined and wired. No ids are removed.

## Deliberately excluded

- **Editing `app-dark-pages.css`:** a shared file, which would need the full suite. Page-local rules cover this page.
- **The red filled Withdraw button and the "Submit cancelled by user." wording:** observations outside the closed list.
- **Weights, radii, sizes and layout:** Batch 4.

## Verification

- **Tests:** new class `ReimbursementBatch3SourceTests` in `tests/test_reimbursement_design.py`. It checks:
  - dark rules exist for `.submitted`, `.approved` and `.rejected`
  - totals use `--app-primary-text`, and there is no gradient in `.reim-grand-total-cell`
  - the confirm message contains `Period:` and `Total:`
  - the lock-state function no longer assigns the lock reason to `reimStatusText`
  - locked rules hide the selection controls
  - a kept-functions guard

  **Positive control** against `HEAD`'s template in the scratchpad: the style tests fail and the guard passes.
- **Focused run:** `tests/test_reimbursement_*.py`, `test_appearance_themes`, `test_dark_mode_readability`, `test_changelog_coverage`.
- **Browser** on a DB copy, with a Draft, a Submitted, an Approved and a Rejected record (seed the missing statuses on the copy):
  - Measure banner and total contrast in light, graphite and AMOLED.
  - Open Submit and cancel at the confirm, checking the period and total line.
  - Count the duplicate texts at 375px.
  - Selection controls are hidden on the locked records.
  - Console clean. Clean up.

## After implementation

1. Self-review the diff.
2. Service worker `CACHE_VERSION` → the next free number, with suffix `-reimbursement-contrast`.
3. `releases.json`: "Clearer Reimbursement Status and Totals" (everyone). Items: readable status banners and totals in dark mode; the Submit check shows the period and total; locked records hide row selection.
4. `changes.md` and this plan's Status.
5. Commit only the template, `app.py` (version), `releases.json`, tests, `plans.md` and `changes.md`. Publish only on "commit and push".

## Risks

- **Status text loses information:** only the duplicate sentence is removed, and the banner keeps it. Checked by reading both on each status.
- **Accent-mixed totals on light accents:** measured across accents in step 3.
- **Blast radius:** CSS plus a few JS lines on one page. Rollback = revert the commit.

---

# Reimbursement — Batch 2: Server Cleanup (schedule load in one query, unused status counts, duplicate status key)

**Status:** Executed — published to `main` on 2026-10-13 on the owner's "commit and push" (commit `e308157`; owner: "execute batch 2" the same day). Tests: 4 added (3 fail on `HEAD`; the row-rule test passes on both, as intended); focused run 179 OK. Old and new code returned identical rows for 28 engineers × 4 ranges on a DB copy.
**Differences from plan:** (1) Tests went in a new file `tests/test_reimbursement_batch2_cleanup.py` (HTTP client style of `test_reimbursement_pc_code.py`). (2) The query-count test makes one warm-up request first (the first request runs ~1,900 one-time setup queries), then compares 4 vs 10 shifts in range with the same 3 shifts for the user. (3) The browser "before" count was replaced by an in-process comparison of `HEAD` and the new code over every linked engineer, which is stricter.
**Approved:** 2026-10-13 (owner chose batches 1–4 after the 2026-10-13 page scan).
**Detailed:** 2026-10-13.
**Branch:** `main` (local first; publish only on "commit and push").
**Depends on:** Batch 1 executed (both touch `app.py`). Find code by function name.

## Context

Three findings from the 2026-10-13 page scan of `/reimbursement`:

- **Schedule load runs one query per schedule (Medium, speed).** `get_reimbursement_schedule_rows` (`app.py:39270`) loads every engineer's shifts in the range (up to 63 days). For each shift it then calls `get_shift_assigned_engineer_ids(shift)`, which runs its own `ShiftEngineer` query, and only then skips shifts that are not the user's.
- **`status_counts` is unused.** `get_my_reimbursement_statuses` (`app.py:40492`) computes `status_counts` twice: once in the loop, then with an extra GROUP BY query. The page never reads it (`templates/reimbursement.html` only uses `items`), and it leaves out Paid.
- **Duplicate `'paid'` key** in `reimbursement_normalize_status`'s map (`app.py:36880` and `:36883`).

Intended outcome: the same rows, returned with one shift query, and less dead work. No visible change.

## Decisions taken

1. **Filter in SQL with exactly today's rule.** A shift belongs to the user when its `engineer_id` is the user's, **or** the user is linked in `ShiftEngineer`. That is the same as `profile.id in get_shift_assigned_engineer_ids(shift) or shift.engineer_id == profile.id`. The shared helper `get_shift_assigned_engineer_ids` is **not** changed (other pages use it).
2. **Remove `status_counts`** from the response and both of its computations. Grep `templates/`, `static/` and `tests/` for `status_counts` first. On 2026-10-13 nothing read it; if a reader exists, stop and record it here instead.
3. Remove the second `'paid': 'Paid'` line. Behaviour is identical.

## Investigation

- `get_shift_assigned_engineer_ids` (grep `def get_shift_assigned_engineer_ids`) returns the `ShiftEngineer` ids for the shift, or `[shift.engineer_id]` when none are linked.
- The schedule route's check is `profile.id not in assigned_ids and shift.engineer_id != profile.id → skip`. Equivalent SQL: `or_(Shift.engineer_id == profile.id, Shift.id.in_(select(ShiftEngineer.shift_id).where(ShiftEngineer.engineer_id == profile.id)))`.
- `reimbursement_is_work_expense_schedule(shift)` and the claimed-shift exclusion stay in Python, unchanged.
- **Data:** the local DB has 557 shifts; production has more. The page calls the route on every Load Schedules, This Week and This Month.

## Execution steps

1. **Read first:** the newest `changes.md` section.
2. **`get_reimbursement_schedule_rows`:**
   - Add the `or_` filter (Investigation) to the `Shift.query`.
   - Keep the Python `assigned_ids` check as it is (a cheap safety net, now only over the user's shifts).
   - Done = same rows and order as before for an engineer who is assigned through `ShiftEngineer` only, through `engineer_id` only, or both. Another engineer's shifts are never returned.
3. **`get_my_reimbursement_statuses`:** delete the in-loop `status_counts` dict and increment, the GROUP BY block with its try/except, and the `'status_counts'` response key. Done = the response has `success`, `items`, `count` and `status_filter`; the page's status list renders as before.
4. **`reimbursement_normalize_status`:** delete the duplicate `'paid'` line.

## Deliberately excluded

- **Changing `get_shift_assigned_engineer_ids`:** it is a shared helper used by the Calendar and other pages, and would need the full suite.
- **Deleting `/mark_reimbursement_processing` and `/accounting_mark_processing`:** they have no caller, but they belong to Accounting Center, which was not scanned.
- **The 20-item status list limit:** not in the agreed batches.

## Verification

- **Tests:** a new HTTP test in `tests/test_reimbursement_range_reuse.py` style (temporary SQLite engine, as in `test_locked_range_does_not_replace_editable_record_and_zero_rows_do_not_claim`). Seed two engineers and three shifts in one range:
  - one linked to A through `ShiftEngineer`
  - one with `engineer_id = A`
  - one for B only

  `/get_reimbursement_schedule_rows` for A returns the first two, not the third. Count the queries with a SQLAlchemy `before_cursor_execute` listener: at most a small constant, independent of the shift count (assert that 3 and 10 shifts give the same count).

  A source test asserts that `status_counts` is gone from `get_my_reimbursement_statuses` and that `'paid'` appears once in the normaliser map.

  **Positive control:** run the query-count test against `HEAD`'s `app.py` in-process (scratchpad copy, never `git stash`). It fails on the count.
- **Focused run:** `tests/test_reimbursement_*.py`, `test_request_recall`. No full suite: one route plus one page-scoped helper, and the shared helper is untouched.
- **Browser** on a DB copy: This Month and an old month load the same row count as before (note the before count first). The status list renders. Console clean. Clean up.

## After implementation

1. Self-review the diff (`app.py` and tests only).
2. No service worker bump or release entry: nothing user-visible. Run `test_changelog_coverage` to confirm it does not require one.
3. `changes.md` and this plan's Status.
4. Commit `app.py`, tests, `plans.md` and `changes.md` only. Publish only on "commit and push".

## Risks

- **A rule mismatch drops or adds rows:** covered by the three-shift test and the before/after row count in the browser.
- **Blast radius:** one read-only route and one response key. Rollback = revert the commit.

---

# Reimbursement — Batch 1: Bugs (upload date-range check, status list refresh after Save and Submit)

**Status:** Executed — published to `main` on 2026-10-13 on the owner's "commit and push" (commit `8300000`; owner: "execute it" the same day). Tests: 6 added (4 fail on `HEAD`); focused run 175 OK. Browser check on a DB copy passed.
**Differences from plan:** (1) tests went in a new file `tests/test_reimbursement_batch1_fixes.py` with the `test_client` + `session['_user_id']` style of `tests/test_reimbursement_pc_code.py` (the range-reuse file has no HTTP client); upload root and `managed_storage_write_bytes` are patched so the valid upload writes nothing. (2) The browser Submit ran with `EMAIL_NOTIFICATIONS_ENABLED=false` and an empty `BREVO_API_KEY` in the temporary launch entry, because the local `.env` holds a live mail key.
**Approved:** 2026-10-13 (owner chose batches 1–4 after the 2026-10-13 page scan).
**Detailed:** 2026-10-13.
**Branch:** `main` (local first; publish only on "commit and push").
**Depends on:** nothing. Execute first.

## Context

Two bugs reproduced on a copy of `scheduler.db` during the 2026-10-13 page scan:

1. **Receipt upload accepts a backwards or unbounded date range and creates a draft.**
   - Cause: `upload_reimbursement_receipt` (`app.py:40892`) parses start and end, then calls `reimbursement_find_owned_header_or_404(..., create=True)`. It has no "end before start" check and no 63-day limit, unlike `save_reimbursement_draft` (:40625-40629) and `get_reimbursement_schedule_rows`.
   - Reproduced: POST `start=2026-12-31&end=2026-01-01&additional_receipt=1` with a PNG returned 200 and created Draft #9 with that reversed range, plus a stored file.
   - With `additional_receipt=1` the shift check is skipped, so nothing else stops it.
2. **"My Reimbursement Status" goes stale after Save and Submit.**
   - Cause: `loadMyReimbursementStatuses()` runs only on page load (`templates/reimbursement.html:8481`) and after Delete (:7256).
   - Reproduced: after submitting #7 the list still showed "Draft ₱123.45" with no Withdraw button until Refresh Status was clicked. The overlap notice (`renderReimbursementOverlapNotice`, :8125) uses the same stale list.

Intended outcome: the server rejects bad ranges on upload the same way Save does, and the status list reflects Save and Submit right away.

## Decisions taken

1. **Upload uses Save's rules and messages:** 400 "End date must be after start date" and 400 "Date range is limited to 63 days for performance". The checks run before any header lookup or creation.
2. **Status list refresh:**
   - After a successful **manual** Save: refresh, so autosaves don't trigger a fetch every few seconds.
   - After a successful Submit: refresh.
   - Not awaited, so the buttons don't wait on it.

## Investigation

- **`save_reimbursement_draft` checks** at `app.py:40625-40629`. Copy them as-is.
- **Manual Save success:** the toast `reimToast('Draft saved.', …)` runs only when `entry.payload.save_source === 'manual'` (`templates/reimbursement.html:6499`). That is the place to add the manual-only refresh.
- **Submit success path:** `setReimbursementSubmitNotice(\`${message} Reimbursement #… is now in the manager's approval queue…\`)` at :7635 in `submitReimbursement` (:7494).
- **Withdraw button:** `renderMyReimbursementStatuses` shows Withdraw only for `submitted` items (:8116). The refresh makes it appear.

## Execution steps

1. **Read first:** the newest `changes.md` section.
2. **`upload_reimbursement_receipt`:** right after the date parse, add the two checks from decision 1. Done = a reversed range and a 64-day range each return 400 with nothing created; a valid range uploads as before.
3. **Template, after the manual-save toast (:6499):** call `loadMyReimbursementStatuses();` (not awaited). Done = after Save Draft the list shows the new updated time and total.
4. **Template, after the Submit success notice (:7635):** call `loadMyReimbursementStatuses();` (not awaited). Done = after Submit the record shows "Submitted / Waiting for Approval" and Withdraw without Refresh.
5. **Kept functions:** `uploadReimbursementReceipt` (or the page's upload function), `saveReimbursementDraft`, `submitReimbursement`, `loadMyReimbursementStatuses` and `renderReimbursementOverlapNotice` are still defined and wired.

## Deliberately excluded

- **Refreshing after autosave:** too many requests. A manual save or submit is the meaningful change.
- **Paging the status list beyond 20:** not in the agreed batches.

## Verification

- **Tests:**
  - **HTTP**, in the temporary-SQLite style of `tests/test_reimbursement_range_reuse.py`: log in as a seeded engineer. POST `/upload_reimbursement_receipt` with a reversed range and with a 64-day range (additional receipt, small PNG). Expect 400 each, and `ReimbursementHeader` count unchanged. A valid one-day range returns 200.
  - **Source:** `loadMyReimbursementStatuses()` is called in the manual-save branch and in the submit success branch of `submitReimbursement`.
  - **Positive control:** run both against `HEAD`'s files (scratchpad, in-process; never `git stash`). Both fail.
- **Focused run:** `tests/test_reimbursement_*.py`, `test_request_recall`, `test_changelog_coverage`. No full suite: one route plus page JS.
- **Browser** on a DB copy (temporary password on the copy only):
  - Repeat the reversed-range upload: 400, no new record.
  - Open the Draft: Save Draft updates the list; Submit shows Submitted and Withdraw in the list.
  - Console clean. Delete any test receipt file in `static/uploads/reimbursements/`, the copy and the launch entry.

## After implementation

1. Self-review the diff.
2. Service worker `CACHE_VERSION` → the next free number, with suffix `-reimbursement-fixes`. Keep the previous value as a history comment.
3. `releases.json`: "Reimbursement Status Updates Right Away" (everyone). Items: your status list updates after Save and Submit; receipt upload rejects an invalid date range.
4. `changes.md` and this plan's Status.
5. Commit only `app.py`, `templates/reimbursement.html`, `static/changelog/releases.json`, tests, `plans.md` and `changes.md`. Publish only on "commit and push".

## Risks

- **Existing uploads with an unusual range:** the client always sends the loaded range, which Save has already validated, so normal use is unaffected. The checks only reject requests Save would reject too.
- **Blast radius:** one route guard and two JS calls. Rollback = revert the commit.

---

# Travel Request — Batch 4: DESIGN.md Alignment (Page Header, weights, radii, Submit colour, theme variables, phone first screen and dock)

**Status:** Executed — published to `main` on 2026-10-12 on the owner's "commit and push" (commit `25a0b00`; owner: "execute batch 4" the same day). Tests: 7 added (6 style tests fail on `HEAD`, guard passes); focused run 148 OK. Browser check on a DB copy passed (1366 px light/graphite/AMOLED, 375 px).
**Differences from plan:** (1) the status-chip line lives in `setTravelRequestLockedState`, not `applyTravelRequestRecord`; the test targets that function. (2) Batch 3's `test_disabled_equipment_toggle_text` also pinned the `#f1f5f9` background and was updated to `var(--app-surface-raised)`. (3) The default (Draft) chip moved off slate hex to `--app-border` / `--app-text`, and the chip/badge/time sizes were raised to 0.75rem. (4) At 375 px the Request Information card ends at 63% of the screen, not ~55%, because the subtitle wraps to four lines; the Travel Purpose Type title is still in the first screen. (5) Submit on the purple accent measures 4.23:1, from the shared `--app-primary` token that every primary button uses; it is outside this closed list and was left unchanged.
**Approved:** 2026-10-12 (owner: "plan batch 4"; scope agreed with the 2026-10-12 scan batches).
**Detailed:** 2026-10-12.
**Branch:** `main` (local first; publish only on "commit and push").
**Depends on:** Batches 1–3 published (`ccd6f8b`, `331a24a`, `910db7f`). Find code by selector, not line number.

## Context

The 2026-10-12 design scan of `/travel_request` (critique snapshot `.impeccable/critique/2026-10-12T05-46-07Z__templates-travel-request-html.md`, closed list) left two P2 items after Batches 1–3. This batch fixes exactly those; nothing new is added (critique-loop rule).

1. **Off-system styling** (P2): font weights 700–950 (Fira Sans renders anything above 600 as 600; DESIGN.md says body 400, labels 600); radii 10–20px (DESIGN.md: controls 6px, cards 10–12px, phone cards 16px); a gradient accent hero instead of the Page Header; Submit in success green (green is only for Add / create); neutral greys hardcoded as slate hex instead of theme variables (part of the detector's 26 design-system-color findings).
2. **Phone first screen and dock** (P2): at 375 px the hero (205 px) and four stacked read-only fields fill the first screen; the fixed dock is 169 px (21% of 812 px).

Leftover from Batch 1: Preview Form is only ~3.5:1 on the gradient's light end. Removing the gradient fixes it.

Intended outcome: the page reads like My Requests and the Dashboard (same Page Header, same weights, radii and button roles). It works in every theme and accent with no change to behaviour, and on a phone the form starts on the first screen with a dock of at most ~120 px.

## Decisions taken

1. Scope: the two P2 items and the Preview Form leftover only (closed list). Detector-only findings outside them (off-ramp font sizes, dialog/toast shadows, the dialog radius beyond the shape mapping below) stay out.
2. **Page Header by reuse, not copy:** the page links `static/css/app-dashboard.css?v=16` (as My Requests does) and uses `.dash-page-header`, `.dash-page-h1`, `.dash-page-sub` and `.dash-page-actions`. That keeps one source of truth for the header; `app-dashboard.css` itself is not edited.
3. **Button roles:** Submit for Approval becomes the accent primary (the one primary on the page). Save Draft becomes an accent outline button. Header buttons (Preview Form, Open Timeline, Restore Travel Blocks, New Request) are Bootstrap `btn btn-outline-primary`, as on My Requests. Danger buttons keep their red (Batch 3).
4. **Hero status pill → status chip:** the header's status uses the existing `travel-status-chip` + `travelStatusChipClass()` pairs (same colours as My Travel Requests), not a white pill.
5. **Theme variables for neutrals only:** neutral text, surfaces and borders move to `--app-text`, `--app-muted`, `--app-surface`, `--app-surface-raised` and `--app-border`. Semantic status colours (banners, toasts, conflict panel, readiness, chips, red badge, danger buttons) stay fixed hex pairs (Semantic Status Rule). The disabled equipment toggle keeps Batch 3's `#475569`, because the token pair would drop it from 6.92:1 to 4.55:1.
6. **Phone (≤768 px):** Request Information shows two fields per row. The dock becomes two rows: the total with icon-only Readiness and Delete Draft (labels kept for screen readers), then Save Draft and Submit side by side. Buttons stay 44 px.
7. Page-local change: `templates/travel_request.html` only (plus the service worker version, changelog, DESIGN.md note and tests). No shared CSS is edited, so focused tests only (AGENTS.md "Keep It Simple"). The existing dark rules in `app-dark-pages.css` stay; trimming them is not part of this batch.

## Investigation

Measured 2026-10-12 in `templates/travel_request.html` (page `<style>` block) and the shared CSS:

- **Hero:** `<header class="travel-hero">` with `.travel-hero-eyebrow`, `h1` holding `#travel-hero-title` and `#travel-hero-status.travel-hero-pill`, the form-number `<p>`, and `.travel-hero-actions` holding `#travel-preview-btn` (an `<a>`), `#travel-open-timeline-btn`, `#travel-restore-blocks-btn`, and New Request (`startNewTravelRequest()`). CSS `.travel-hero` = accent gradient, white text, 18px radius; `.travel-page .travel-hero-actions a.travel-btn { color: #fff; }` (Batch 1). JS (`applyTravelRequestRecord`) only uses the ids: `$t('travel-hero-title')`, `$t('travel-hero-status')` (`pill.textContent = status`), `travel-preview-btn` (`hidden` / `href`), the timeline and restore buttons (`hidden`). Nothing outside this template uses `travel-hero*` or `travel-btn-success` (grep of `templates/` and `static/`; `app-dark-pages.css` has no `travel-hero` rule).
- **Page Header:** `static/css/app-dashboard.css` `.dash-page-header` (flex, `align-items: flex-end`, wrap, gap 1rem, margin-bottom 1.5rem), `.dash-page-h1` (1.75rem/600, `--app-text`; 1.5rem at ≤575.98px), `.dash-page-sub` (0.9rem, `--app-muted`), `.dash-page-actions` (flex, gap .5rem), `.dash-page-actions .btn` (min-height 38px, 600; 44px only at ≤575.98px). Used by `templates/accounting_center.html` with `app-dashboard.css?v=16`. Its generic phone rules target `.row.mb-4.g-3`, `.card-header` and `.table-responsive table`; the travel page uses `row g-3` (no `mb-4`), no `.card-header` and no `.table-responsive`, so nothing else on the page changes. `.btn` anchors escape the theme's `a:not(.btn)` link colour, so Preview Form no longer needs the Batch 1 rule.
- **Buttons:** `.travel-btn` (12px radius, 900); `.travel-btn-primary` (accent); `.travel-btn-success` (`#198754`), used only by `#travel-submit-btn`; `#travel-save-btn` is `.travel-btn-primary`; `.travel-btn-secondary` (`#e2e8f0` / `#334155`) plus Batch 1's `.travel-page a.travel-btn.travel-btn-secondary { color: #334155; }`; confirm dialog `confirmBtn.className = 'travel-btn ' + (… 'travel-btn-danger' : 'travel-btn-primary')` (unchanged). `--app-primary-text` = strong accent in light, accent mixed 60% with white in dark (`static/css/app-themes.css`), so an outline button on `--app-surface` is readable in every theme.
- **Weights in use:** 700, 750, 800, 850, 900, 950 across titles, labels, inputs, hints, meta, chips, buttons, banners, toasts, dialog, dock and notifications.
- **Radii in use:** 18 (hero), 16 (`.travel-card`, `.travel-route-card`), 14 (banner, purpose-type card, visit card, total, conflict panel, readiness, toast), 12 (inputs, checks, buttons, participant chip, note, icon buttons, search results, equipment toggle/menu, money option, history item, notification item), 10 (conflict item, attachment item, equipment all-row), 20 (dialog), 999 (chips, close buttons).
- **Neutral hex:** `#fff` (card, input, visit card, search results, equipment toggle/menu, money option, participant chip, toast, dialog, danger-outline light), `#0f172a` / `#334155` (input, labels, titles, items), `#64748b` / `#475569` (hints, meta, empty, readonly, messages), `#e2e8f0` / `#cbd5e1` / `#dbe4ee` (borders), `#f8fafc` / `#f1f5f9` (check, purpose card, attachment and history items, readonly). Token contrast: `--app-text` on `--app-surface-raised` 15.55:1; `--app-muted` on `--app-surface` 4.76:1, on `--app-surface-raised` 4.55:1 (readonly inputs improve from 4.34:1 today).
- **Phone:** Request Information is four `col-md-3` read-only fields (`#travel-date`, `#travel-department`, `#travel-current-status`, `#travel-request-no`; JS fills them by id), stacked one per row below 768 px. The dock (`#travel-dock`): `.travel-dock-total` then `.travel-dock-actions` with Readiness (`toggleTravelReadiness()`), `#travel-delete-draft-btn`, `#travel-save-btn` and `#travel-submit-btn`; at ≤768 px the buttons are `flex: 1 1 auto` and wrap to three rows. `.travel-page` bottom padding is 150px at ≤768 px.
- **Tests that pin current styles** (`tests/test_travel_request_page.py`): Batch 1 `test_link_buttons_keep_readable_colours` (the hero anchor rule and the `#334155` secondary anchor) and Batch 3 `test_hero_pill_dark_tint`. Both are replaced on purpose (step 9). `tests/test_layout_sidebar.py` pins the dock's `left: var(--shell-offset, …)` (kept). `tests/test_appearance_themes.py` lists the travel classes that `app-dark-pages.css` covers (unchanged).

## Execution steps

1. **Read first:** newest `changes.md` section; DESIGN.md Typography, Shapes, Buttons, Page Header, Do/Don't; load the Impeccable skill (`polish` / `normalize` for steps 2–6, `adapt` for 7–8).
2. **Page Header** (markup + JS):
   - Add `<link rel="stylesheet" href="{{ url_for('static', filename='css/app-dashboard.css') }}?v=16">` at the top of the content block, as in `accounting_center.html`.
   - Replace `<header class="travel-hero">` with `<header class="dash-page-header">`. Inside it: a `<div>` with `<h1 class="dash-page-h1">` holding `#travel-hero-title` and `#travel-hero-status` (class `travel-status-chip`), and `<p class="dash-page-sub">` with the existing form-number sentence. The "Travel Request / Order Form" eyebrow becomes the start of that sentence ("Travel Request / Order Form · Shimadzu Philippines Corporation · …"). Add `.dash-page-actions` with the four buttons, ids and handlers unchanged, classes `btn btn-outline-primary` (icons get `me-2`, as on My Requests).
   - JS in `applyTravelRequestRecord`: after `pill.textContent = status;`, set `pill.className = ('travel-status-chip ' + travelStatusChipClass(status)).trim();`.
   - CSS: delete `.travel-hero`, `.travel-hero-eyebrow`, `.travel-hero h1`, `.travel-hero p`, `.travel-hero-pill`, `.travel-hero-actions`, `.travel-hero-actions .travel-btn` and `.travel-page .travel-hero-actions a.travel-btn`. Add `.travel-page .dash-page-h1 { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }` and `.travel-page .dash-page-h1 .travel-status-chip { font-size: .78rem; }` (≥0.75rem, DESIGN chip rule). At ≤768 px add `.travel-page .dash-page-actions .btn { min-height: 44px; }`, because the shared rule only applies at ≤575 px.
   - Done = no gradient. The title and status chip match My Requests. Preview Form is accent text on the surface (≥4.5:1 in every theme and accent). All four buttons still work.
3. **Button roles:** `#travel-submit-btn` `travel-btn-success` → `travel-btn-primary`; `#travel-save-btn` `travel-btn-primary` → new `travel-btn-outline`. Add `.travel-btn-outline { background: var(--app-surface); color: var(--app-primary-text); border: 1px solid var(--app-primary); }` and `.travel-btn-outline:hover { background: var(--app-primary-soft); }`. Delete `.travel-btn-success`. `.travel-btn-secondary` → `background: var(--app-surface-raised); color: var(--app-text); border: 1px solid var(--app-border);`. The Batch 1 anchor rule becomes `.travel-page a.travel-btn.travel-btn-secondary { color: var(--app-text); }` (same selector, so it still beats the theme link rule). Done = one primary on the page (Submit), Save Draft clearly secondary, no green.
4. **Weights:** in the page `<style>` block:
   - **600** for titles and labels: section title, label, check, purpose-type card, participant chip, route/visit/banner/conflict/dialog/notification titles, history title, attachment name, search item, equipment toggle/row, money option, total, dock total, chips, badges, buttons, close buttons.
   - **400** for body and help text: input/select/textarea values, hint, attachment/audit/history meta, search-item small, banner text, conflict panel text, readiness items, toast text, dialog message, notification message/time, empty text, participant view note.
   - Done = no `font-weight` above 600 in the block; nothing below 600 on a title, label or button.
5. **Radii:**
   - **6px** for controls: inputs, select, textarea, buttons, icon buttons, checks, participant chip, money option, equipment toggle/menu, search results, equipment all-row, conflict item.
   - **10px** for cards and panels: `.travel-card`, route card, visit card, purpose-type card, banner, total, conflict panel, readiness, toast, history item, attachment item, notification item, participant view note.
   - **12px** for the dialog.
   - Pills (999px) unchanged.
   - At ≤768 px: `.travel-card` 16px (phone cards). Done = no other radius values in the block.
6. **Neutral hex → theme variables** (decision 5):
   - `#fff` surfaces → `var(--app-surface)`.
   - `#0f172a` / `#334155` text → `var(--app-text)`.
   - `#64748b` / `#475569` muted text → `var(--app-muted)`, except `.travel-equipment-toggle:disabled`, which keeps `#475569`.
   - `#e2e8f0` / `#cbd5e1` / `#dbe4ee` borders → `var(--app-border)`.
   - `#f8fafc` / `#f1f5f9` fills → `var(--app-surface-raised)`. That includes readonly/disabled inputs, which follow DESIGN.md (`surface-raised` + muted text).
   - The light `.travel-btn-danger-outline` background `#fff` → `var(--app-surface)`. Semantic pairs are untouched.
   - Done = the only hex left in the block are semantic status pairs, danger red, the disabled-toggle `#475569`, and shadows/scrims.
7. **Phone first screen:** Request Information columns `col-md-3` → `col-6 col-md-3` (two per row below 768 px; ids unchanged). Done = at 375×812 the header and the Request Information card end above ~55% of the screen, and the Travel Purpose Type title is visible without scrolling.
8. **Phone dock** (≤768 px):
   - Wrap the Readiness and Delete Draft texts in `<span class="travel-dock-label">` and give both buttons `aria-label` ("Readiness", "Delete Draft").
   - CSS: `.travel-dock-inner { display: grid; grid-template-columns: 1fr 1fr 44px 44px; gap: 8px; }`, `.travel-dock-actions { display: contents; }`, `.travel-dock-total { grid-column: 1 / 3; }`, Readiness in column 3, Delete Draft in column 4, `#travel-save-btn` on row 2 in column 1, `#travel-submit-btn` on row 2 in columns 2–4.
   - The `.travel-dock-label` text is visually hidden on phones (clip pattern, not `display: none`). Readiness and Delete Draft are 44×44 icon buttons. Lower `.travel-page` bottom padding to match the dock.
   - Done = dock ≤ ~120 px at 375 px, all four actions reachable and 44 px. Desktop dock unchanged apart from steps 3–5.
9. **Tests updated on purpose:** in `tests/test_travel_request_page.py`, Batch 1 `test_link_buttons_keep_readable_colours` now asserts the secondary rule with `var(--app-text)` and that the hero anchor rule is gone. Batch 3 `test_hero_pill_dark_tint` is replaced by asserting that `.travel-hero-pill` is gone and that the header status uses `travelStatusChipClass`.
10. **Kept-functions check:** every id and handler listed in Investigation is still present. `travelConfirmDialog`, `applyTravelRequestRecord`, `toggleTravelReadiness`, `saveTravelRequestDraft`, `submitTravelRequest`, `deleteTravelRequestDraft`, `startNewTravelRequest`, `openTimelineForTravelRequest` and `restoreTravelBlocksForRequest` are still defined and wired. Only the `travel-hero*`, `travel-btn-success` and Batch 1 hero-anchor CSS is removed, on purpose.

## Deliberately excluded

- **Trimming the Travel Request rules in `app-dark-pages.css`** (61 `!important` overrides): they stay correct over the new variables. Removing them edits shared CSS and needs the full suite; that would be a separate cleanup, not a scan item.
- **Off-ramp font sizes, dialog/toast shadow and thin border** (detector only, not in the closed list).
- **Semantic status hex** (banners, toasts, conflict panel, readiness, chips, red badge): kept by the Semantic Status Rule.
- **Editing `app-dashboard.css`** (for example to make `.dash-page-actions .btn` 44 px at ≤768 px for every page): a page-local rule covers this page; other pages were not scanned.
- **Wording, field order, behaviour, server code:** unchanged.

## Verification

- **Tests:** `tests/test_travel_request_page.py` new class `TravelRequestBatch4SourceTests`:
  - the page links `app-dashboard.css` and uses `dash-page-header` / `dash-page-h1` / `dash-page-sub` / `dash-page-actions`; no `travel-hero` class remains;
  - the header status gets `travelStatusChipClass` in `applyTravelRequestRecord`;
  - `#travel-submit-btn` is `travel-btn-primary`, `#travel-save-btn` is `travel-btn-outline`, and `travel-btn-success` is gone;
  - the `<style>` block has no `font-weight` above 600 and no `border-radius` outside {6px, 10px, 12px, 16px, 999px};
  - none of the neutral hex values `#0f172a`, `#334155`, `#64748b`, `#e2e8f0`, `#cbd5e1`, `#dbe4ee`, `#f8fafc`, `#f1f5f9` remain in the block (allow-listed exceptions as step 6);
  - Request Information uses `col-6 col-md-3`; the phone dock rules and `.travel-dock-label` exist, with `aria-label` on Readiness and Delete Draft;
  - kept-hooks guard: every id/handler from step 10.
  - **Positive control:** run the class against `git show HEAD:templates/travel_request.html` in the scratchpad (never `git stash`). Every style test fails; the guard passes.
- **Focused run:** `tests/test_travel_request_*.py`, `test_appearance_themes`, `test_dark_mode_readability`, `test_layout_sidebar`, `test_accounting_attachment_management`, `test_request_recall`, `test_changelog_coverage`. No full suite (page-local, decision 7).
- **Browser** on a copy of `scheduler.db` with a temporary engineer account, a seeded Draft (attachment, client visit) and a Submitted and an Approved request:
  - At 1366 px in light, graphite and AMOLED with the classic and purple accents: the header matches My Requests. Preview Form, Open Timeline, Restore Travel Blocks and New Request open or act as before (New Request with edits still shows the Batch 1 discard prompt).
  - Measure text vs background with `javascript_tool` for the header buttons, status chip, Save Draft outline, Submit, secondary buttons and readonly inputs (≥4.5:1 each).
  - Save, Submit (cancel at the confirm), Delete Draft (cancel), upload/delete attachment, Remove Visit and Withdraw still work.
  - At 375 px: Request Information two-up, Travel Purpose Type title in the first screen, dock ≤ ~120 px with all four actions 44 px, no horizontal scroll. Console clean.
  - One final screenshot pair (desktop light, phone). Clean up the copy, the account and the launch entry.

## After implementation

1. Self-review the diff: only the page template (plus versions, changelog, DESIGN.md note and tests); no shared CSS touched; every removed selector listed in step 10.
2. `app.py` service worker `CACHE_VERSION` → `…-v304-travel-request-design` (next free number), previous kept as a history comment.
3. `static/changelog/releases.json`: release "Cleaner Travel Request Page" (audience `everyone`; items: a header like My Requests; Submit is the main button and Save Draft is secondary; on phones the form starts sooner and the bottom bar is smaller).
4. `DESIGN.md`: under My Requests / Page Header note that Travel Request also links `app-dashboard.css` for the Page Header (one line), so a later header change is known to reach it.
5. `changes.md` bullets; this plan's Status with the commit and any differences.
6. Commit only `templates/travel_request.html`, `app.py`, `static/changelog/releases.json`, `DESIGN.md`, `tests/test_travel_request_page.py`, `plans.md`, `changes.md`. Never `scheduler.db`, `output/`, `tmp/`, handoffs, `.impeccable/`, `.claude/` or other dirty files. Publish only on "commit and push".

## Risks

- **`app-dashboard.css` side effects on this page:** its generic rules were checked (Investigation). The browser pass at 1366 and 375 px catches anything missed. Rollback = remove the link.
- **Dark themes:** neutral variables are already dark-aware, and the existing `app-dark-pages.css` travel rules still apply. Checked in graphite and AMOLED.
- **Phone dock grid:** if Delete Draft is hidden (not the owner, or not saved yet), column 4 is empty; Readiness stays in column 3. Checked with and without a saved draft.
- **Blast radius:** one template's CSS and header markup plus one JS line; rollback = revert the commit.

---

# Travel Request — Batch 3: Contrast Fixes (dark red outline buttons, hero status pill, "No equipment found")

**Status:** Executed locally on 2026-10-12 (owner: "execute batch 3"); not committed — publish on "commit and push". Tests: 4 added (3 fail on `HEAD`, guard passes); focused run 81 OK; full suite no new failures (14 known). Browser check on a DB copy passed. Difference from plan: `app-dark-pages.css?v=32` was pinned five times, not twice — three in `tests/test_appearance_themes.py`, one each in `tests/test_timeline_desktop_collapse.py` and `tests/test_tsr_page_design.py`; all moved to `?v=33` (commit those two files too).
**Approved:** 2026-10-12 (owner: "plan travel request batch 3"; scope agreed with the 2026-10-12 scan batches).
**Detailed:** 2026-10-12.
**Branch:** `main` (local first; publish only on "commit and push").
**Depends on:** Batches 1 (`ccd6f8b`) and 2 (`331a24a`), both published. Find code by selector, not line number.

## Context

The 2026-10-12 design scan of `/travel_request` (critique snapshot `.impeccable/critique/2026-10-12T05-46-07Z__templates-travel-request-html.md`, closed list) found three text-contrast failures left after Batches 1–2. This batch fixes exactly those three; nothing new is added (critique-loop rule).

1. **Red outline buttons in dark themes** (P1) — Delete Draft, Delete (attachment), Delete All, Remove Visit, and Withdraw (same class, in My Travel Requests) use `#dc2626` text on the dark surfaces.
2. **Hero status pill** (P3) — the status text at 0.78rem, white on a 20% white tint over the accent gradient; below the DESIGN.md Small-Text Contrast Rule (4.5:1 under ~0.8rem).
3. **"No equipment found"** (P3) — the disabled equipment toggle in light theme, `#64748b` on `#f1f5f9`.

Intended outcome: each reaches at least 4.5:1 in light, graphite and AMOLED and in every accent theme, with no change to layout or behaviour.

## Decisions taken

1. Scope is the three items above only (closed list). DESIGN.md alignment (weights, radii, Page Header hero, green Submit, hardcoded hex) is Batch 4.
2. The dark fix goes in the existing travel rule in shared `static/css/app-dark-pages.css` — the one place for Travel Request dark rules — not a page-local copy. That makes it shared code: bump the stylesheet version and run the full suite once before publishing.
3. Red outline buttons stay red in dark (they mark a destructive action), using the light red of the page's dark rejected banner/chip family, not the neutral grey the Reimbursement page uses.

## Investigation

Re-measured 2026-10-12 (WCAG ratio from the CSS values; the browser step re-checks the rendered colours):

- **Red outline:** `templates/travel_request.html` `.travel-btn-danger-outline { background: #fff; color: #dc2626; border: 1px solid #fecaca; }` (light 4.83:1, passes). Dark: `static/css/app-dark-pages.css` `:root[data-app-theme="dark"] .travel-btn-danger-outline { background: transparent !important; }` is the only rule, so the text stays `#dc2626`. `#dc2626` on panel / card / card-hover: AMOLED (`#101010` / `#191919` / `#242424`) 3.94 / 3.64 / 3.21; graphite (`#292a2d` / `#333438` / `#3b3c40`) 2.97 / 2.57 / 2.28. Proposed `#fca5a5`: AMOLED 10.03 / 9.26 / 8.18, graphite 7.56 / 6.55 / 5.80. No hover rule exists for the class in either file. Used by: Delete All (`#travel-delete-all-attachments-btn`), Delete Draft (`#travel-delete-draft-btn`), Remove Visit (visit card template, `removeTravelVisit`), attachment Delete (`deleteTravelRequestAttachment`), Withdraw (history row, `openRequestRecall('travel_request', …)`).
- **Hero pill:** `.travel-hero-pill { background: rgba(255,255,255,.2); border: 1px solid rgba(255,255,255,.35); … font-size: .78rem; font-weight: 900; }` on `.travel-hero` `linear-gradient(135deg, var(--app-primary-strong), var(--app-primary))` (`--app-primary-strong` = 78% primary + black, `static/css/app-themes.css`). White on the 20% white tint, strong end / light end: classic `#0d6efd` 4.38 / 3.33; green 4.28 / 3.24; violet 4.09 / 3.08; teal 4.77 / 3.73; blue 4.71 / 3.63; pink 5.70 / 4.46; red 5.79 / 4.52. With a 20% **black** tint: worst case 6.07 (violet light end), classic 8.92 / 6.44. The hero has no dark override (same gradient in every theme).
- **Equipment toggle:** `.travel-equipment-toggle:disabled { background: #f1f5f9; color: #64748b; }` → 4.34:1 light. Proposed `#475569` → 6.92:1. Dark already passes through `app-dark-pages.css` `.travel-equipment-toggle:disabled` (`--dark-muted` on `--dark-card-hover`); unchanged. The text comes from `toggleText.textContent = 'No equipment found'` in the equipment loader; the other disabled-state texts benefit too.
- **Version pins:** `templates/layout.html` links `css/app-dark-pages.css?v=32`; pinned by two `?v=32` asserts in `tests/test_appearance_themes.py` (graphite and AMOLED classes). The service worker precache lists the path without a version (`app.py`); `CACHE_VERSION` is `…-v302-travel-request-limits`.

## Execution steps

1. **Read first:** newest `changes.md` section; this plan. Grep that `.travel-btn-danger-outline` is used only in `templates/travel_request.html`.
2. **Dark red outline** (`static/css/app-dark-pages.css`): replace the travel rule with
   `:root[data-app-theme="dark"] .travel-btn-danger-outline { background: transparent !important; color: #fca5a5 !important; border-color: rgba(248, 113, 113, .55) !important; }`
   and add `:hover, :focus-visible` → `background: rgba(220, 38, 38, .16) !important; color: #fecaca !important;`. Done = all five buttons ≥ 4.5:1 on every dark surface they sit on, still visibly red.
3. **Hero pill** (`templates/travel_request.html`, `.travel-hero-pill`): `background: rgba(0,0,0,.2)`; border, size and weight unchanged. Done = white text ≥ 4.5:1 on both gradient ends for all seven accents.
4. **"No equipment found"** (`templates/travel_request.html`, `.travel-equipment-toggle:disabled`): `color: #475569`. Done = 6.9:1 in light; dark unchanged.
5. **Version bump:** `templates/layout.html` `app-dark-pages.css?v=33`; change both `?v=32` asserts for that file in `tests/test_appearance_themes.py` to `?v=33`.
6. **Kept-functions check:** no id, class, handler or function renamed or removed; only three declarations changed and one hover rule added.

## Deliberately excluded

- **Hero → Page Header, weights, radii, green Submit, hardcoded hex, phone first screen, Preview Form ~3.5:1 on the gradient's light end** — Batch 4 (DESIGN.md alignment). Batch 4 may restyle the pill again; this one-declaration fix keeps it compliant until then.
- **Red outline buttons in light** — already 4.83:1.
- **Other pages' danger-outline buttons** (`reim-btn-danger-outline` etc.) — not in this scan.
- **Disabled toggle in dark** — already passes.

## Verification

- **Tests** — `tests/test_travel_request_page.py` new class `TravelRequestBatch3SourceTests`:
  - the dark `.travel-btn-danger-outline` rule in `app-dark-pages.css` sets `color: #fca5a5` and has a hover rule;
  - `.travel-hero-pill` uses `rgba(0,0,0,.2)`, not `rgba(255,255,255,.2)`;
  - `.travel-equipment-toggle:disabled` uses `#475569`;
  - kept-hooks guard: `travel-delete-all-attachments-btn`, `travel-delete-draft-btn`, `removeTravelVisit`, `deleteTravelRequestAttachment`, `openRequestRecall('travel_request'` still present.
  - **Positive control:** run the class against `HEAD` copies of the two files (`git show HEAD:…` into the scratchpad, never `git stash`): the three style tests fail, the guard passes.
- **Focused run:** `tests/test_travel_request_*.py`, `test_appearance_themes`, the dark-mode readability module, `test_changelog_coverage`.
- **Full suite once before publishing** (`venv/Scripts/python.exe scripts/run_suite.py`, main folder) — shared stylesheet and `layout.html` changed.
- **Browser** on a copy of `scheduler.db` with a temporary engineer account: a draft with an attachment and a client visit, plus a Submitted request (Withdraw). Measure computed text vs. background with `javascript_tool`: all five red buttons in graphite and AMOLED (rest and hover), the pill in light with classic and violet accents and in dark, "No equipment found" in light. Bar ≥ 4.5:1 each. 375 px: no layout change, no horizontal scroll, taps still 44 px; console clean. One final screenshot (graphite, red buttons visible). Clean up the copy, account and launch entry.

## After implementation

1. Self-review the diff (only the declarations above; the dark rule stays in the Travel Request block of `app-dark-pages.css`).
2. `app.py` service worker `CACHE_VERSION` → `…-v303-travel-request-contrast` (next free number), previous kept as a history comment.
3. `static/changelog/releases.json`: release "Easier-to-Read Travel Request Buttons" (audience `everyone`; items: delete and withdraw buttons readable in dark themes; status pill and "No equipment found" easier to read).
4. `DESIGN.md`: nothing (applies existing rules).
5. `changes.md` bullets; this plan's Status with the commit and any differences.
6. Commit only `static/css/app-dark-pages.css`, `templates/travel_request.html`, `templates/layout.html`, `app.py`, `static/changelog/releases.json`, `tests/test_travel_request_page.py`, `tests/test_appearance_themes.py`, `plans.md`, `changes.md`. Never `scheduler.db`, `output/`, `tmp/`, handoffs, `.impeccable/`, `.claude/` or other dirty files. Publish only on "commit and push".

## Risks

- **Stale stylesheet on phones** — the `?v=33` bump and the service worker version force the new CSS.
- **Pill looks heavier** on light accents — a 20% black tint matches the gradient's own dark end; checked in the browser on classic and violet.
- **Blast radius:** three CSS declarations plus one hover rule; rollback = revert the commit.

---

# Travel Request — Batch 2: Server Fixes + HTTP Tests (edit rights, trip and amount limits, form wording, history paging, cleanup)

**Status:** Executed — published to `main` on 2026-10-12 on the owner's "commit and push" (owner: "execute batch 2" the same day). Tests: 10 endpoint tests (7 fail against `HEAD`'s `app.py`, 3 pin existing behaviour) + 3 page source tests; focused run 81 OK; full suite no new failures (14 known). Browser check on a DB copy passed (1366 px and 375 px).
**Differences from the plan:** (1) the two local `max_travel_days` variables stay, now set from `TRAVEL_REQUEST_MAX_DAYS` (smaller change, same effect). (2) Admin tests patch `is_admin_authorized` to `True`: role `superadmin` alone is not admin (the username must be in `SUPERADMIN_USERNAMES`). (3) The over-limit check ran on the local `scheduler.db` copy (0 editable records over 90 days or 10,000,000), not a production copy.
**Approved:** 2026-10-12 (owner: "write batch 2 in plans.md"; decisions answered the same day — see Decisions taken).
**Detailed:** 2026-10-12.
**Branch:** `main` (local first; publish only on "commit and push").
**Depends on:** Travel Request — Batch 1 (below), executed and published (`ccd6f8b`). Line numbers here were taken before Batch 1 landed — find code by function name, not line.

## Context

The 2026-10-12 page-scan of `/travel_request` found server-side gaps the page cannot fix alone:

- **Admins can edit anyone's draft through the API.** `save_travel_request_draft` and the attachment routes accept any `is_admin_authorized()` user, while the page and `get_travel_request` deny admins who are not on the request (`can_user_access_travel_request` docstring: admin status is "intentionally not a substitute").
- **No trip-length limit.** A 2026-11-02 → 2031-11-02 trip saved (tested on a DB copy) and would submit; approval silently creates Timeline blocks for only the first 90 days.
- **No amount limit.** A 1e15 line saved.
- **Draft forms say "Approved".** The preview page title is always "Approved Travel Request Form - …" and the PDF footer always prints "Approved Amount", even for a Draft (tested).
- **My Travel Requests shows only the newest 50** with no way to see older ones.
- **Cleanup:** the page sends six payload keys the server ignores whenever routes exist; `build_travel_visit_purpose` has an unreachable branch.
- **Test gap:** save/submit/delete/attachment/restore routes have no HTTP tests (existing travel tests mostly read source text).

Intended outcome: the server enforces the same rules the page shows, generated wording matches the status, older requests are reachable, and the routes are covered by real HTTP tests.

## Decisions taken

1. **Edit rights:** only the requester and listed participants may save a draft or change its attachments; admins who are not on the request get 403. **Delete Draft keeps its documented rule** (requester or admin, `delete_travel_request_draft` docstring) — unchanged.
2. **Trip limit: 90 days** inclusive (departure to return), the same number approval already uses for Timeline blocks. One constant serves both.
3. **Amount limit: 10,000,000** per request total, in the request's currency (PHP or USD), checked on save.
4. **Wording:** "Approved" appears only once a request is approved or later; before that the title is "Travel Request Form" and the footer "Requested Amount".
5. **History paging:** "Show more" loads the next 50; the status filter still works on the loaded items.

## Investigation

- Save rights: `app.py` `save_travel_request_draft` (`:43559-43565`) — `request_rec.user_id == current_user.id or is_current_user_travel_request_participant(request_rec) or is_admin_authorized()`. Attachments: `can_current_user_edit_travel_request_attachments` (`:43096-43103`), used by upload (`:44118`), delete one (`:44251`) and delete all (`:44294`). View rule: `can_user_access_travel_request` (`:43308`). Delete draft: `:43757` (kept).
- Trip length: save validates only order (`:43578`); submit validates presence and order (`:43848-43851`). `create_or_get_travel_blocks_for_approved_request` and `restore_missing_travel_blocks_for_request` each define `max_travel_days = 90` locally (`:44440`, `:44553`) and silently cut the range.
- Amounts: save rejects negatives only (`:43580-43582`); total is `calculated_request_total` (`:43653-43681`), line amounts already converted to the request currency by `normalize_travel_request_line_payload`.
- Wording: `preview_approved_travel_request_form` (`:50182`) passes `title=f"Approved Travel Request Form - …"` (`:50225`) to `render_embedded_pdf_preview_shell`; the PDF footer is drawn in `build_travel_request_accounting_pdf_bytes` (`:10406`). The form route has no status gate (My Requests links it only for approved-or-later rows).
- History: `get_my_travel_requests` (`:44040-44073`) — `limit` default 50, max 100, no offset. Page: `loadMyTravelRequests()` / `renderMyTravelRequests()` in `templates/travel_request.html`.
- Payload keys the server ignores when `routes` is non-empty (the page always sends routes; save refuses without one): `travel_type` (only a fallback after `request_type`), `arrival_date` (falls back to `return_date`), `participant_names` (no reader in `app.py`), `client_id`, `product_id`, `equipment` (only read by the legacy no-routes branch of `normalize_travel_request_routes_payload`, `:42531-42535`). **Keep** `client_name` and `destination`: save uses them when the route summary is empty (training/meeting trips), `:43613-43614`. Built in `collectTravelPayload()`.
- Dead code: `build_travel_visit_purpose` (`:42494`) — the `elif primary_actions and len(tags) > len(primary_actions)` branch (`:42518`) can never run: whenever it would, `suffix_tags` is non-empty and the `if` above takes it.
- Test pattern to copy: `tests/test_my_requests_actions.py` `MyRequestsActionEndpointTests` — temp DB via `MEDICAL_SERVICE_TEST_DB`, `setUpClass` with `create_all` + `ensure_travel_request_tables()`, seeded users/engineer, `_client(user_id)` setting `_user_id` in `session_transaction`, cleanup by username/prefix.

## Execution steps

1. **Read first:** newest `changes.md` section; this plan's Investigation (re-find lines by function name — Batch 1 shifted the template and `app.py`).
2. **Edit rights** (`app.py`): remove `is_admin_authorized()` from the save check and from `can_current_user_edit_travel_request_attachments`. Leave `delete_travel_request_draft` as is. Done = an admin not on the request gets 403 on save and 409/403 on upload/delete attachment; requester and participants unchanged.
3. **Trip limit** (`app.py`, `templates/travel_request.html`):
   - Add `TRAVEL_REQUEST_MAX_DAYS = 90` beside `TRAVEL_REQUEST_EDITABLE_STATUSES`; replace both local `max_travel_days = 90` with it.
   - Save and submit: when both dates exist and `(return - departure).days + 1 > TRAVEL_REQUEST_MAX_DAYS` → 400 "A travel request can cover at most 90 days. Split longer trips into separate requests."
   - Page: `TRAVEL_MAX_DAYS = {{ travel_max_days }}` passed from `travel_request_page()`; readiness gets a blocking item "Trip is longer than 90 days"; `saveTravelRequestDraft()` shows the same message before posting.
   - Done = 90 days saves; 91 days is refused on save, submit and in the readiness list; approval block creation unchanged.
4. **Amount limit** (`app.py`, page): `TRAVEL_REQUEST_MAX_AMOUNT = 10_000_000`; after the lines loop, `calculated_request_total > TRAVEL_REQUEST_MAX_AMOUNT` → rollback and 400 "The total cannot exceed 10,000,000." (formatted with the currency). Page: `TRAVEL_MAX_AMOUNT` from the route; readiness blocking item and a save-time check. Done = 10,000,000.00 saves, 10,000,000.01 is refused with nothing written.
5. **Wording** (`app.py`): helper `travel_request_is_approved_or_later(request_rec)` = normalized status not in {Draft, Submitted, Rejected}. Preview title "Approved Travel Request Form - …" only when true, else "Travel Request Form - …". PDF footer label "Approved Amount" when true, else "Requested Amount". Done = a Draft preview and PDF say "Travel Request Form" / "Requested Amount"; an Approved one unchanged.
6. **History paging** (`app.py`, page): `get_my_travel_requests` accepts `offset` (≥ 0), queries `limit + 1`, returns `has_more`. Page: `travelHistoryOffset`; `loadMyTravelRequests(append=false)` resets or appends; a "Show more" button (`id="travel-history-more"`, `travel-btn-secondary`, 44px) under the list, hidden unless `has_more`. Saves, submits and deletes keep calling `loadMyTravelRequests()` (reset). Done = with 55 seeded requests the list shows 50, Show more adds 5 and hides.
7. **Cleanup:** in `collectTravelPayload()` drop `travel_type`, `arrival_date`, `participant_names`, `client_id`, `product_id`, `equipment` (keep `client_name`, `destination`, everything else). In `build_travel_visit_purpose` delete the unreachable `elif`. Done = save/reload round trip identical for client-visit, training and meeting trips (browser), site-visit tests pass.
8. **Kept-functions check:** every route, helper and page function used before still exists; only the two local `max_travel_days` variables and the six payload keys are removed on purpose.

## Deliberately excluded

- **Delete Draft for admins** — owner kept the documented rule.
- **Form route status gate** (refusing previews of drafts) — the requester may want to preview a draft; only the wording changes.
- **Server-side status-group filtering for history** — client filtering over loaded pages is enough at current volumes (15 requests in production data).
- **Dark contrast and DESIGN.md alignment** — Batches 3 and 4.
- **Approval-time block cap behaviour** — unchanged; the new limit makes it unreachable for new requests, and older long requests keep today's behaviour.

## Verification

- **Tests** — new `tests/test_travel_request_endpoints.py` (pattern from `MyRequestsActionEndpointTests`; own temp DB, users `tr_endpoints_owner`, `tr_endpoints_participant`, `tr_endpoints_admin` (role `superadmin`, not on the request), `tr_endpoints_other`, prefix `TRE-TEST-`):
  - save: owner creates and updates a draft (200, routes and lines stored); participant updates (200); admin and unrelated user get 403; Submitted record → 409; return before departure → 400; 91-day trip → 400, 90-day → 200; total 10,000,000.01 → 400 and no row changed; negative line → 400.
  - submit: missing dates → 400; 91 days → 400; no signature → 428 with `requires_signature`.
  - delete draft: owner 200 (record and attachments gone); unrelated user 403; Submitted → 409.
  - attachments: owner uploads a 1×1 PNG (200), `.txt` refused (400); admin not on the request refused; delete one and delete all (200, list empty); refused once Submitted.
  - restore blocks: Draft → 400 "Only approved…"; unrelated user on an Approved request → 400 "not authorized".
  - history: 55 seeded → first page 50 with `has_more`, `offset=50` gives 5 without.
  - form wording: Draft preview HTML contains "Travel Request Form -" and not "Approved Travel Request Form"; footer label helper returns "Requested Amount" for Draft, "Approved Amount" for Approved.
  - **Positive control:** run the module with `app.py` at `HEAD` (copy `git show HEAD:app.py` to a scratch folder and point the import there, never `git stash`): the admin, 91-day, amount, paging and wording tests fail; the others pass (they pin existing behaviour).
- `tests/test_travel_request_page.py`: source checks for `TRAVEL_MAX_DAYS`/`TRAVEL_MAX_AMOUNT` readiness items, `travel-history-more`, and that `collectTravelPayload` no longer sends the six keys.
- **Focused run:** `tests/test_travel_request_*.py`, `test_my_requests_actions`, `test_approval_center_wording`, `test_request_recall`, `test_accounting_attachment_management`, `test_changelog_coverage`. **Full suite once before publishing** (changes `app.py` permission helpers shared with the approval and accounting pages).
- **Browser** on a copy of `scheduler.db` with a temporary engineer account: 91-day trip blocked in readiness and on save; 10,000,000.01 blocked; Draft preview says "Travel Request Form"; Show more (seed 55 drafts on the copy); client-visit, training and meeting drafts save and reload unchanged; console clean. Clean up the copy, account and launch entry.

## After implementation

1. Self-review the diff (messages plain for field engineers; no permission widened).
2. `app.py` service worker `CACHE_VERSION` → `…-v302-travel-request-limits` (Batch 1 took v301; use the next free number if another change took v302), previous kept as a history comment.
3. `static/changelog/releases.json`: release "Travel Request Checks" (audience `everyone`; items: trips up to 90 days, total up to 10,000,000, older requests via Show more, draft forms no longer say Approved).
4. `DESIGN.md`: nothing.
5. `changes.md` bullets; this plan's Status with the commit and any differences.
6. Commit only `app.py`, `templates/travel_request.html`, `static/changelog/releases.json`, `tests/test_travel_request_endpoints.py`, `tests/test_travel_request_page.py`, `plans.md`, `changes.md`. Never `scheduler.db`, `output/`, `tmp/`, handoffs, `.impeccable/`, `.claude/` or other dirty files. Publish only on "commit and push".

## Risks

- **An admin who relied on editing others' drafts** loses that: owner decision; requester or a participant can still edit, and admins can still delete.
- **Existing records over 90 days or 10,000,000** can no longer be re-saved without fixing them: checked only on save/submit of editable records; approved records untouched. Check the production copy for such drafts before publishing (query in the browser step).
- **Removing payload keys** breaks a reader missed in Investigation: the round-trip browser check for all three trip types and the existing site-visit tests guard it; rollback = revert.
- **Test DB collisions:** own temp DB file and prefix, cleaned in `setUpClass`/`tearDownClass`.
- **Blast radius:** travel request routes, two shared travel helpers, one page; rollback = revert the commit.

---

# Travel Request — Batch 1: Page Fixes (Preview button, unsaved-changes guard, upload check, status filter, labels, taps)

**Status:** Executed — published to `main` on 2026-10-12 on the owner's "commit and push" (commit `ccd6f8b`). Tests: 8 added (7 fail on `HEAD`); focused run 70 OK. Browser check on a DB copy passed (1366 px and 375 px).
**Differences from plan:** (1) the attachment-link rule needed `.travel-page a.travel-btn.travel-btn-secondary` (0,3,1); the planned `a.travel-btn-secondary` (0,2,1) lost to the theme link rule (0,2,2). (2) Preview Form is now white like the other hero buttons but measures about 3.5:1 at the hero's lighter end, not the planned 4.5:1; that limit belongs to the shared hero gradient (Batch 4).
**Approved:** 2026-10-12 (owner: "plan batch 1", after the travel request page-scan and design scan; owner rule: at most 4 batches).
**Detailed:** 2026-10-12.
**Branch:** `main` (local first; publish only on "commit and push").
**Later batches (not this plan):** 2 server fixes + HTTP tests (needs owner answers: admin editing of others' drafts; 90-day trip limit), 3 dark-theme contrast in `app-dark-pages.css`, 4 DESIGN.md alignment. Critique record: `.impeccable/critique/2026-10-12T05-46-07Z__templates-travel-request-html.md`.

## Context

The 2026-10-12 scans of the Travel Request page (`/travel_request`, `templates/travel_request.html`) found page-only defects that need no server change:

- **Preview Form is unreadable** (light 1.39:1, graphite/AMOLED 1.98:1): blue link text on the blue hero.
- **Submit / Restore / Signature dialogs** confirm with an amber button carrying white text (2.15:1).
- **Unsaved work is lost silently**: New Request, Open (My Travel Requests), opening a notification for another request, and leaving or refreshing the page all replace the form with no warning.
- **Mixed uploads save partly**: files upload one by one, so a bad second file leaves the first uploaded and shows only the error.
- **Status filter misses statuses**: Sent to Accounting, Accounting Approved/Rejected, Funds Received, Travel Completed and Completed show only under "All", with grey chips; the Rejected chip does not use the DESIGN.md `status-rejected` pair.
- **27 fields' visible labels are not linked** to their inputs (screen readers announce nothing).
- **Small taps on phones**: attachment Preview/Download and other `.travel-btn-sm` buttons are 36px tall; the toast close is 20px wide.

Intended outcome: every action on the page is readable and safe, every status is findable, and the page passes the 44px and label checks — in one page-only commit.

## Decisions taken

1. One batch, one file (`templates/travel_request.html`) plus the service worker version, changelog and tests. No `app.py` logic, no shared CSS.
2. Dialog "warning" tone becomes the accent primary button (One Variable Rule); `.travel-btn-warning` is deleted.
3. Unsaved-changes guard: compare the form's payload with a snapshot taken when a record is applied; ask only when the form is editable and differs. Browser leave/refresh uses the native `beforeunload` prompt.
4. Status groups for the filter and the chip: Draft, Submitted, Approved, Rejected (Rejected and Accounting Rejected), With Accounting (Sent to Accounting, Accounting Approved, Funds Received), Liquidation (any status containing "liquidation"), Completed (Travel Completed, Completed). Filter options follow the same groups.
5. Chip colours: Rejected uses DESIGN.md `status-rejected` (`#fde8ea` / `#a1121f`); With Accounting gets an info pair (`#e0f2fe` / `#075985`, dark `rgba(14,165,233,.2)` / `#bae6fd`); Completed keeps the neutral chip. Dark pairs stay page-local.

## Investigation

- Preview Form: `templates/travel_request.html:206` is an `<a class="travel-btn">`. Its white comes from `.travel-hero-actions .travel-btn` (`:17`, specificity 0,2,0), beaten by `app-themes.css` `a:not(.btn):not(.sidebar a)` (0,2,2) → `var(--app-primary-text)`. The same rule recolours the attachment links `a.travel-btn-secondary` (`:1246-1247`) from `#334155` to the accent text. Measured in the browser via matched rules.
- Dialog tone: `travelConfirmDialog()` `:466-490` maps `tone: 'warning'` to `.travel-btn-warning` (`:43`); callers `submitTravelRequest` `:1401`, signature prompt `:1424`, `restoreTravelBlocksForRequest` `:1471`. No other file uses `travel-btn-warning`.
- Form replacement points: hero New Request `:209` → `resetTravelForm()`; history Open `:1522` → `loadTravelRequestDetail(id)`; `openTravelNotification()` `:1576-1590` → `loadTravelRequestDetail` or navigation; no `beforeunload` handler. `applyTravelRequestRecord()` `:1351` is the last call of `resetTravelForm` `:1645`, `loadTravelRequestDetail` `:1667` and `saveTravelRequestDraft` `:1376`, so it is the one place where the form equals the saved record. `collectTravelPayload()` `:1181` captures every editable field. `submitTravelRequest` resets after a successful submit (no guard needed: saved first).
- Upload: `uploadTravelRequestAttachments()` `:1253-1293` checks count and size only; the server allows PDF/JPG/JPEG/PNG (`reimbursement_receipt_allowed`, `app.py:44134`).
- Filter: options `:357-364`; `renderMyTravelRequests()` `:1499-1528`; `travelStatusChipClass()` `:644-651`. Status names: `travel_request_normalize_status` `app.py:41973`; the DB copy also has "Liquidation Approved".
- Dark chips: `app-dark-pages.css:762-765` force `.travel-status-chip` (and submitted/approved/rejected) with `!important`; a page rule `:root[data-app-theme="dark"] .travel-status-chip.accounting { … !important }` is more specific, so no shared CSS change is needed.
- Labels: static `.travel-label` elements `:240-327` have no `for`; dynamic route fields (`addTravelRoute` `:841`) and visit fields (`addTravelVisit` `:911`) likewise. Amount inputs and the history filter already have `aria-label`.
- Taps: `.travel-btn-sm` `:46` (36px), `.travel-toast-close` `:179`, `.travel-notification-close` `:155` (32px).
- Tests that pin this page: `tests/test_travel_request_page.py` (`id="travel-history-filter"` kept), `test_travel_request_draft_instructions.py`, `test_travel_request_site_visit.py`. None references the functions being changed.

## Execution steps

1. **Read first:** newest `changes.md` section; DESIGN.md Colors (Semantic Status Rule) and Do/Don't; load the Impeccable skill (`harden` for steps 4–5, `polish` for 2, 3, 6–8).
2. **Readable link buttons** (`travel_request.html` CSS): add `.travel-page .travel-hero-actions a.travel-btn { color: #fff; }` and `.travel-page a.travel-btn-secondary { color: #334155; }` (dark keeps the existing `app-dark-pages.css:742` rule). Done = Preview Form ≥ 4.5:1 on the hero in light, graphite, AMOLED; attachment links grey in light.
3. **Dialog tone**: in `travelConfirmDialog()` map `warning` to `travel-btn-primary`; delete `.travel-btn-warning`. Done = Submit, Signature Required and Restore dialogs confirm with the accent button; no `travel-btn-warning` in the file.
4. **Unsaved-changes guard**:
   - `let travelSavedSnapshot = '';` and `function travelFormSnapshot(){ return JSON.stringify(collectTravelPayload()); }`.
   - `applyTravelRequestRecord()`: set `travelSavedSnapshot = travelFormSnapshot();` as its last line.
   - `function isTravelFormDirty(){ return isCurrentTravelEditable() && travelFormSnapshot() !== travelSavedSnapshot; }`.
   - `async function confirmDiscardTravelChanges(){ return !isTravelFormDirty() || travelConfirmDialog({title: 'Discard unsaved changes?', message: 'Your changes to this travel request have not been saved.', confirmText: 'Discard Changes', cancelText: 'Keep Editing', tone: 'danger'}); }`.
   - New `async function startNewTravelRequest(){ if(await confirmDiscardTravelChanges()) resetTravelForm(); }` — hero button calls it.
   - New `async function openTravelRequest(id){ if(await confirmDiscardTravelChanges()) return loadTravelRequestDetail(id); return false; }` — history Open and the same-page branch of `openTravelNotification()` call it. `loadTravelRequestDetail` itself is unchanged (still used on page load).
   - `window.addEventListener('beforeunload', event => { if(isTravelFormDirty()){ event.preventDefault(); event.returnValue = ''; } });`
   - Done = edits then New Request / Open / notification ask first; Keep Editing leaves the form untouched; a fresh, just-loaded or just-saved form never asks; locked (submitted/approved) records never ask; refresh with edits shows the browser prompt.
5. **Upload type check**: in `uploadTravelRequestAttachments()`, before the count check, `const badType = files.filter(file => !/\.(pdf|jpe?g|png)$/i.test(file.name));` → error toast "Only PDF, JPG or PNG files can be attached: <names>." and return, nothing uploaded. Done = selecting a PNG and a TXT uploads nothing and names the TXT.
6. **Status groups**: new `travelStatusGroup(status)` returning `draft|submitted|approved|rejected|accounting|liquidation|completed|other` (rejected check first so "Accounting Rejected" is red; "liquidation" before "completed" so "Liquidation Completed" is Liquidation). `travelStatusChipClass()` returns the group (empty for draft/completed/other). `renderMyTravelRequests()` filters by `filter === 'all' || travelStatusGroup(item.status) === filter`. Filter options: All statuses, Draft, Submitted, Approved, Rejected, With Accounting, Liquidation, Completed. CSS: `.travel-status-chip.rejected` → `#fde8ea` / `#a1121f`; new `.travel-status-chip.accounting` light pair and page-local dark pair (`!important`, see Investigation). Done = each status on the DB copy appears under exactly one option; chips ≥ 4.5:1 in light and dark.
7. **Labels**: give every static `.travel-label` a `for` matching its field id (add `id="travel-department"` to the Department input). In `addTravelRoute()` add a `travelRouteCounter` and ids `route-<n>-from|to|type|summary` with matching `for`; in `addTravelVisit()` use `travelVisitCounter` for `visit-<n>-client|purpose|notes` with matching `for`; the Equipment and Participants/Purpose Tags labels become `aria-labelledby` targets or plain `<div class="travel-label">` with the group given `role="group"` + `aria-label`. Do not change any class name the JS queries (`.route-from-location`, `.visit-client-name`, …). Done = the browser scan for inputs/selects/textareas without a label returns 0.
8. **Taps**: at `max-width: 768px` set `.travel-btn-sm { min-height: 44px; }`, `.travel-notification-close { width: 44px; height: 44px; }`; `.travel-toast-close` gets `min-width: 44px; min-height: 44px;` at all widths. Done = no visible button or link under 44px at 375px.
9. **Kept-functions check**: every function, id and handler the page used before still exists (grep the diff for removed names; only `.travel-btn-warning` is removed on purpose). Save, Submit, Delete Draft, Upload, Delete/Delete All attachments, Preview, Restore, Withdraw, Readiness, conflict check still work.

## Deliberately excluded

- **Server changes** (preview title/footer wording, trip-length and amount limits, history paging, admin edit rights, unused payload keys, dead `elif`) and the HTTP tests — Batch 2, two owner decisions pending.
- **Dark red outline buttons and the hero pill contrast** — Batch 3, needs shared `app-dark-pages.css` and the full suite.
- **Weights, radii, gradient hero, green Submit, phone first screen and dock height** — Batch 4 (DESIGN.md alignment); changing them here would mix a restyle into a bug-fix commit.
- **Autosave / draft recovery** — not requested; the guard is enough.

## Verification

- **Tests** (`tests/test_travel_request_page.py`, new class `TravelRequestBatch1SourceTests`): hero/secondary anchor colour rules present; no `travel-btn-warning`, warning tone maps to primary; `isTravelFormDirty`, `confirmDiscardTravelChanges`, `startNewTravelRequest`, `openTravelRequest` and a `beforeunload` listener exist, the hero button and history Open call the guarded functions, `applyTravelRequestRecord` sets the snapshot; upload type regex precedes the first `travelFetch` in `uploadTravelRequestAttachments`; `travelStatusGroup` exists with the seven groups and the filter has the seven option values; every static `class="travel-label"` label has `for=` (regex); `.travel-btn-sm` 44px phone rule; kept-functions guard (`saveTravelRequestDraft`, `submitTravelRequest`, `deleteTravelRequestDraft`, `uploadTravelRequestAttachments`, `deleteTravelRequestAttachment`, `deleteAllTravelRequestAttachments`, `restoreTravelBlocksForRequest`, `loadTravelRequestDetail`, `resetTravelForm`, `toggleTravelReadiness`, `checkTravelRequestConflicts`, `openRequestRecall`).
  - **Positive control:** run the new class in-process with `PAGE` set from `git show HEAD:templates/travel_request.html` (never `git stash`); all fail except the kept guard.
- **Focused run:** `tests/test_travel_request_*.py`, `test_dark_mode_readability`, `test_changelog_coverage`, `test_tsr_autosave_client_groups`. Full suite not needed (one page; no shell, shared CSS/JS, `app.py` helper or schema change).
- **Browser** on a copy of `scheduler.db` with a temporary engineer account on the copy (as in the scan): 1366px light — Preview Form readable; edit then New Request / Open / notification → dialog, Keep Editing keeps edits, Discard replaces; just-saved form asks nothing; approved record asks nothing; refresh with edits → browser prompt. Upload PNG+TXT → nothing uploaded, TXT named. Filter: each option on the copy's 15 records. Graphite and AMOLED: Preview Form, chips ≥ 4.5:1. 375px: label scan 0, no control under 44px, no horizontal scroll, console clean. Save, Submit (signature dialog), Delete Draft, attachments, Withdraw still work. Clean up the copy, account and launch entry. One screenshot as proof.

## After implementation

1. Self-review the diff (no hardcoded accent hex; status colours semantic only; no class the JS queries renamed).
2. `app.py` service worker `CACHE_VERSION` → next number `…-v301-travel-request-fixes` (v300 kept as a history comment).
3. `static/changelog/releases.json`: release "Travel Request Fixes" (audience `everyone`; items: Preview Form readable, warning before unsaved changes are lost, every status in the filter).
4. `DESIGN.md`: nothing (no new pattern; chip pairs follow the Semantic Status Rule).
5. `changes.md` bullets; this plan's Status with the commit and any differences.
6. Commit only `templates/travel_request.html`, `app.py` (service worker line), `static/changelog/releases.json`, `tests/test_travel_request_page.py`, `plans.md`, `changes.md`. Never `scheduler.db`, `output/`, `tmp/`, handoffs, `.impeccable/`, `.claude/` or other dirty files. Publish only on "commit and push".

## Risks

- **Guard false positives** (asks on an untouched form) if `collectTravelPayload()` differs between snapshot and check, e.g. route summary auto-fill or async equipment lists: snapshot is taken after `applyTravelRequestRecord`, equipment lists are filled synchronously from preloaded data; the browser check opens several records and confirms no prompt. Fallback: exclude `routes[].route_summary` from the snapshot.
- **Guard misses** a change outside the payload (attachments): attachments save immediately, so nothing is lost.
- **Status grouping** puts a new or odd status under "other" (shown only in All): same as today.
- **Blast radius:** one page plus the service worker string; rollback = revert the commit.

---

# Signal and Character — My Requests Urgency Colour + "Logbook" Record Numbers (My Requests, Dashboard)

**Status:** Executed — published to `main` on 2026-10-12 on the owner's "commit and push" (commit `37dfd14`). Tests: 7 added (6 source fail on `HEAD`); focused run 240 OK. Browser check on a DB copy passed (1366 px and 375 px).
**Differences from the plan:** (1) The dashboard shows no record numbers (rows are identified by date), so `logbook-ref` went on the entry dates: engineer task rows and phone cards (`dashboardTaskDateLabel`), the range column, and the created-on date (was `font-monospace`). (2) The aging chip sits in the Status cell, not the Date cell, because Date is hidden on phones (Batch D `phoneHidden`). (3) Service worker is `v300-signal-logbook` (v299 was taken by the liquidation Excel fix); `app-dashboard.js` pin also bumped to `?v=16`. (4) The owner's data has no rejected items, so the red pill was checked by rendering samples in the page (6.8:1 light, 6.6:1 dark).
**Approved:** 2026-10-12 (owner: "go write up the plan in plans.md", after the design discussion on personalization, colour and branding).
**Detailed:** 2026-10-12.
**Branch:** `main` (local first; publish only on "commit and push").
**Depends on:** Dashboard Critique Fixes (`e55deb2`) and My Requests Batches A–D (`502a0f4`), all published.

## Context

The owner felt the redesigned Dashboard and My Requests pages were missing something, possibly personalization or colour. The design review concluded:

- **More decoration is not the answer.** DESIGN.md: colour "signals action and state, never decoration"; the 10-11 critique found the greeting, clock and customize chrome pushed work below the fold. Personalization already exists (4 modes, 7 accents, saved layout), and the useful kind — "your" work first — already ships as Needs You Today (dashboard) and Needs your action (My Requests).
- **Branding stays where it is.** The logo and Logo Red rule already sit in the sidebar header and phone top bar on every page; sign-in is the one branded screen; generated forms carry the brand outward. Red inside the work area would compete with "overdue / rejected" signals.
- **What is actually missing:** (1) on My Requests, colour does not yet do its job — Rejected and Returned read as neutral grey and nothing shows how long an item has waited; (2) both pages read as generic Bootstrap (critique: "category-interchangeable") with no detail tying them to the North Star "The Service Logbook".

Intended outcome: on My Requests a rejected item reads as a problem at a glance and stale items show their age; record numbers on both pages look like logbook entries — one small, repeated signature detail, no new colours, no logos.

## Decisions taken

1. **No logo, brand red, greeting, banner or new accent** in either page's work area. Blue stays the default accent; Shimadzu Red stays an opt-in accent.
2. **Dashboard colour is done.** Semantic status chips, past-due tint + "N days late" chip, and quiet zeros shipped in `e55deb2`; this plan does not touch dashboard colour.
3. **My Requests status colour:** a new `status-rejected` pill (semantic red, not the accent) for Rejected, Returned and Accounting rejected; text label kept (never colour alone). Draft stays neutral.
4. **My Requests aging:** in Needs your action, the To fix and Your next step rows show a text chip "N days" when the item's date is ≥ 7 days in the past; past 30 days it uses the late tone. No chip for Confirm when received, for future dates (leave start dates) or under 7 days. Same pill shape as the dashboard's `dashboard-late-chip`.
5. **"Logbook" signature:** one shared class `logbook-ref` — record numbers (and the dashboard's created-on date) set in a system monospace stack with tabular numbers and slight letter-spacing, as one span (no separate prefix styling). Applied to record numbers on every My Requests tab and to work-order / record identifiers on the dashboard tables and phone cards. Replaces the dashboard's `'Courier New'` `.font-monospace` override.
6. Run with the Impeccable skill: `colorize` for steps 2–3, `bolder` (restrained — one detail only) for step 4.

## Investigation

- `templates/accounting_center.html:729` `statusClass()` maps paid/received/completed → `status-paid`, approved/processing/accounting → `status-processing`, pending/submitted/sent → `status-pending`, everything else → `status-other` (grey `#e5e7eb`/`#374151`, line 66). So **Rejected and Returned render grey**. Note "Accounting rejected" contains "accounting" and currently maps to `status-processing` (blue) — the rejected check must come first.
- Pill colours live in the page: light `accounting_center.html:63-66`, dark `:179-183` (`:root[data-app-theme="dark"] .accounting-shell …`).
- `renderActionRows()` `accounting_center.html:1026` renders the action tab; the Date cell is `item.date_label` only (string `%m/%d/%Y`).
- `app.py:46843` `my_requests_action_items().add()` builds each item; `date_value` is `rejected_at`/`updated_at` for fixes, received/approved dates for next steps, and `leave.start_date` for leave (can be in the future). No machine-readable date is sent today.
- `static/css/app-dashboard.css:11` overrides `.font-monospace` to `'Courier New'`; used for the created-on date at `static/js/app-dashboard.js:2705`. `.dashboard-late-chip` at `app-dashboard.css:1586` (light `#fde8ea` / `#a1121f`).
- My Requests already links `app-dashboard.css` (Batch C), so a class defined there reaches both pages without touching the shell.
- Late/aging already exists on the dashboard (`dashboardDaysLate`, `app-dashboard.js:1959`); not reusable directly (different page script), so My Requests gets its own small helper.

## Execution steps

1. **Read first:** newest `changes.md` section; DESIGN.md Colors and "My Requests"; load the Impeccable skill.
2. **Rejected pill** (`templates/accounting_center.html`): in `statusClass()` add a first check — `rejected`, `returned` → `status-rejected`. Add `.status-rejected` light (red-50 fill, red-800 text) beside line 66 and its dark rule beside line 183 (translucent red fill, light red text). Done = Rejected, Returned and Accounting rejected pills are red with ≥ 4.5:1 in light, graphite and AMOLED; no other status changes class.
3. **Aging chip** (`app.py`, `templates/accounting_center.html`):
   - `my_requests_action_items().add()`: add `'date_iso': date_value.strftime('%Y-%m-%d') if date_value else ''` (keep `date_label`).
   - New `ageChip(item)` in the page: returns '' unless `item.group` is `fix` or `next` and `date_iso` is ≥ 7 days before today (local date); returns `<span class="age-chip">N days</span>`, plus `age-chip--late` at > 30 days. Call it in the Date cell of `renderActionRows()`.
   - CSS `.age-chip` (muted slate pill, same size as `dashboard-late-chip`) and `.age-chip--late` (late tone); dark rules beside the others.
   - Done = an item rejected 12 days ago shows "12 days", 45 days shows the late-tone chip, a future leave and Confirm rows show none.
4. **Logbook record numbers** (`static/css/app-dashboard.css`, `templates/accounting_center.html`, `static/js/app-dashboard.js`, `templates/dashboard.html` if server-rendered ids exist):
   - Define `.logbook-ref { font-family: ui-monospace, "SFMono-Regular", Consolas, "Liberation Mono", monospace; font-variant-numeric: tabular-nums; letter-spacing: .02em; }` and point the `.font-monospace` override at the same stack (drop `'Courier New'`). Bump the `app-dashboard.css?v=` pin in both templates and the tests that pin it.
   - My Requests: wrap the record number in every renderer (action, reimbursement, travel request, cash advance, liquidation, leave) in `<span class="logbook-ref">`.
   - Dashboard: apply to the record/work-order identifier in the engineer, scheduler and manager tables and phone task cards (find them in `renderMyTasks` and neighbours; list the exact functions in the plan notes when executing).
   - Done = record numbers on both pages render in the mono stack at 1366 px and 375 px; no layout shift > 4 px in card heights; nothing else changes font.
5. **Kept-functions check:** every id, `data-*` attribute and function name the two pages used before still exists (grep the diff for removals).

## Deliberately excluded

- **Logo, brand red, greeting, hero, banners, new accents** — rejected in the design review (noise for a daily tool; red would compete with status signals).
- **Dashboard colour changes** — already shipped in `e55deb2`.
- **New personalization features** (custom greetings, avatars, per-user colours) — the useful personalization ("your" work first) already exists.
- **Other pages** — apply the logbook detail elsewhere only after the owner sees it on these two.
- **Changing the action badge count or groups** — settled in Batch B.

## Verification

- **Tests:** `tests/test_my_requests_page.py` new `MyRequestsSignalSourceTests`: `statusClass` maps Rejected/Returned/Accounting rejected to `status-rejected` before the accounting rule; `.status-rejected` has light and dark rules; `ageChip` exists, is called in `renderActionRows`, and gates on `fix`/`next` and 7/30 days; all six renderers emit `logbook-ref`. `tests/test_my_requests_actions.py`: an endpoint test asserts `date_iso` on a seeded rejected item. `tests/test_dashboard_style.py` (or the module that pins `app-dashboard.css`): `logbook-ref` defined, no `'Courier New'`, the dashboard renderers emit it; update the `?v=` pins.
  - **Positive control:** run the new source tests in-process against `git show HEAD:<file>` (never `git stash`); all fail except kept guards.
- **Focused run:** `tests/test_my_requests_*.py`, `tests/test_dashboard_*.py`, `test_dark_mode_readability`, `test_changelog_coverage`. Full suite not needed (two pages, one page-level CSS file, one field added to one helper's output).
- **Browser** on a copy of `scheduler.db` (temporary password on the copy only), owner's engineer-view account plus a scheduler account: My Requests at 1366 px light, graphite and AMOLED — rejected pills red, aging chips on old To fix / next rows only, record numbers mono; dashboard at 1366 px and 375 px — record numbers mono, nothing else changed. 375 px: no horizontal scroll, taps ≥ 44 px, chips ≥ 4.5:1, console clean. Every Batch A–D dialog action still opens. Clean up the copy, password and launch entry. One screenshot per page as proof.

## After implementation

1. Self-review the diff (no hardcoded accent hex; status colours semantic only).
2. `app.py` service worker `CACHE_VERSION` `…-v299-signal-logbook` (v298 kept as a history comment).
3. `static/changelog/releases.json`: release "Clearer Status on My Requests" (audience `everyone`; items: rejected items in red, waiting time shown, record numbers easier to scan).
4. `DESIGN.md`: Colors — `status-rejected` and the aging chip under the Semantic Status Rule; Typography — `logbook-ref` as the North Star signature detail.
5. `changes.md` bullets; this plan's Status with the commit and any differences.
6. Commit only `templates/accounting_center.html`, `templates/dashboard.html` (if touched), `static/css/app-dashboard.css`, `static/js/app-dashboard.js`, `app.py`, `static/changelog/releases.json`, `DESIGN.md`, the test files changed, `plans.md`, `changes.md`. Never `scheduler.db`, `output/`, `tmp/`, handoffs, `.impeccable/`, `.claude/` or other dirty files. Publish only on "commit and push".

## Risks

- **Status text variants** (e.g. "Returned for revision", "Accounting Rejected") miss the red rule or hit the blue one: the rejected check runs first on substrings; the test covers all three spellings.
- **Timezone off-by-one on aging**: compare local date strings, not timestamps; thresholds of 7/30 days make a one-day error harmless.
- **Mono font widens record numbers** and wraps phone cards: checked at 375 px; fallback is `font-size: .95em` on `.logbook-ref`.
- **Blast radius:** two pages and one page-level CSS file plus one extra JSON field; rollback = revert the commit.

---

# My Requests — Batch D: Form Downloads, Compact Phone Cards, Action Groups

**Status:** Executed — `502a0f4` (published to `main` 2026-10-12).
**Differences from the plan:** (1) Hiding `phoneHidden` columns alone left cards at ~455px (labels above values, three stacked 44px buttons), so the phone card also changed: labels sit beside values (`td[data-label]` padding-left 6rem, label absolutely placed), the record cell is the unlabelled card title, the Actions cell is unlabelled, and buttons share one row as text-only 44px buttons (icons hidden on phones). Result: action ~282px, reimbursement/leave ~261px, travel/cash advance ~330px, liquidations ~394px (status notes and the balance card kept); the 260px target is met only for the shortest cards. `DESIGN.md` records the new rule. (2) The travel form rule matches exact early statuses (`draft`, `submitted`, `pending…`, `rejected`, `returned`, `accounting rejected`, `cancel…`); a substring test hid the button on "Liquidation Submitted". (3) Liquidation forms show for any status after submission (not only Submitted/Approved/Completed), via `liquidationFormReady()`. (4) A test leave row was added to the browser copy, because the owner has no leave records.
**Approved:** 2026-10-12 (owner: "approve batch D, write it to plans.md", after the post-Batch C scan).
**Detailed:** 2026-10-12.
**Branch:** `main` (local first; publish only on "commit and push").
**Depends on:** Batches A (`2184b16`), B (`a7dca6c`) and C (`d33eba2`), all published.

## Context

The owner asked for a re-scan of My Requests (`templates/accounting_center.html`) after Batch C: can forms be downloaded, is design lacking, is navigation hard. The scan (browser, copy of `scheduler.db`, owner's account, 1366 px and 375 px) found:

- **Downloads work but are hidden.** Every form route returns its file (reimbursement ZIP, travel request PDF, travel and cash advance liquidation Excel, leave PDF), but My Requests links only the Reimbursement Package, and only on the Reimbursements tab. Everything else needs Open → the record's own page.
- **Phone list is too long.** Each phone card is about 554 px tall (every column becomes a labelled line), so the 19 action items make an 11,400 px page.
- **Badge and list disagree.** The tab says "Needs your action 8" while the list says "19 item(s) waiting on you" (the badge counts To fix + Your next step; the 11 "Confirm when received" items are listed but not counted — a Batch B decision).
- **No group headings** in Needs your action: the group name is repeated in every row's Details column.
- **Wrong labels while loading:** the markup defaults are the Reimbursements ones ("My Reimbursements", "Waiting for payment", Reimbursement column headings, the status filter visible), shown for about a second before the default action tab replaces them.
- **Clutter:** the Requester column always shows the signed-in user (only own records are listed); the travel and cash advance Reference column repeats the record number and dumps the full purpose text.

Batch D fixes these on the one page, with no backend change except the service worker version.

## Decisions taken

1. **A download button in rows**, built in the page from module + id (one helper, no new server fields), only where a form exists and makes sense for the status:

   | Module | Link | Label | Shown when |
   | --- | --- | --- | --- |
   | Reimbursements | `/download_reimbursement_package?reimbursement_id={id}` (ZIP) | Package (as today) | status not Rejected/Returned |
   | Travel requests | `/download_travel_request_form/{id}?force_download=1` (PDF) | Form | approved or later (not Draft, Submitted/awaiting approval, Rejected) |
   | Travel liquidations | `/download_travel_liquidation_excel/{id}?force_download=1` (Excel) | Form | Submitted, Approved or Completed |
   | Cash advance liquidations | `/download_cash_advance_liquidation_excel/{id}` (Excel) | Form | Submitted, Approved or Completed (on the Cash Advances tab via the row's `liquidation_id` / `liquidation_status`) |
   | Leave requests | `item.download_url`, else `/download_leave_request/{id}` (PDF) | Form | always (the employee may need to print and sign it) |
   | Cash advances | none — no cash advance form exists in the app | — | never |

   All are `btn-outline-dark` with `fa-download`, plain links (no `target="_blank"`; the routes send attachments). The same helper feeds the Needs your action tab, so every action row with a form gets the button.
2. **Compact phone cards (≤768 px):** each module's `MODULE_VIEW` gains `phoneHidden` — the column indexes hidden on phones. Phones keep Record, Amount, Status, the module's key "what to do"/balance column and Actions; Type, Date/Approved, Reference, Payment and similar secondary columns hide. `labelQueueCells()` adds class `cell-phone-hidden` to those cells (one helper; desktop unchanged). Target: a typical card ≤ 260 px tall.
3. **Action groups:** the Details column is removed from the action tab (headings become Record · Type · Amount · Date · Status · What to do · Actions). `renderActionRows` inserts a heading row per non-empty group: `<tr class="action-group-row"><th colspan="7" scope="colgroup">To fix · N</th></tr>` (same for Your next step, Confirm when received).
4. **Badge stays as Batch B decided** (fix + next). The subtitle explains the difference instead: "N need your action · M to confirm when received" (drop a part when it is 0; "Nothing needs you right now." stays as the empty state).
5. **Remove the Requester column** from Reimbursements, Travel Requests, Cash Advances, Liquidations and Leave (headers and cells). Info that lived only there moves to the Record cell's sub-line: the liquidation `submitted_at_label`/`updated_at_label`. The reimbursement `username` sub-line is dropped (it is the user).
6. **Trim Reference** (travel requests, cash advances): show the reference line only when it differs from the record number; the purpose text is clamped to two lines (`-webkit-line-clamp: 2`) with the full text in `title`.
7. **Correct starting state:** the markup defaults become the action tab's: KPI labels/captions To fix / Your next step / Confirm when received, title "Needs your action", the action headings, and `#accountingStatusFilter` starts with `d-none` (`applyModuleView` still shows it for other modules).

## Investigation

- Routes checked on the copy (owner's records): `/download_reimbursement_package?reimbursement_id=1` → 200 ZIP; `/download_travel_request_form/6?force_download=1` → 200 PDF (without the flag it returns an HTML preview page, `app.py:50211-50224`); `/download_travel_liquidation_excel/3` → HTML preview unless `force_download=1` (`app.py:49560-49568`), with it → 200 xlsx; `/download_cash_advance_liquidation_excel/3` → 200 xlsx; the RFP routes return 400 "RFP is not required because Due to Employee is zero." when nothing is due (not linked by this batch).
- Travel form permission `can_current_user_view_approved_travel_request_form` (`app.py:49962`) allows the requester and participants; the route has no status check, so the page restricts the button to approved-or-later rows (decision 1).
- Leave queue items carry `download_url` (`leave_feature.py:400`, via `to_dict` in `get_accounting_leave_request_queue`, `leave_feature.py:807-832`).
- Cash advance rows carry `liquidation_id` and `liquidation_status` (`app.py` cash advance accounting serializer, around `:51346`); there is no cash advance form route (only attachments).
- Action items (`my_requests_action_items`, `app.py:46831`) carry `module` (`reimbursements`, `travel_requests`, `cash_advances`, `liquidations`, `cash_advance_liquidations`, `leave_requests`), the `id` of that module's record, `group` and `status` — enough for the helper without server changes. Leave action items have no `download_url`; the helper uses `item.download_url || `/download_leave_request/${id}`` (route `leave_feature.py:1217`).
- Page code: `MODULE_VIEW` `accounting_center.html:459-527`; `labelQueueCells()` `:897`; `renderActionRows` `:928`; `renderLeaveRequestRows` `:954`; `renderReimbursementRows` `:974` (Package at `:985`/`:1001`); `renderLiquidationRows` `:1013`; `renderCashAdvanceRows` `:1129`; `renderTravelRequestRows` `:1212`; subtitle `:872-875`; phone CSS `:188-235`; default markup `:261-312`; filter toggle in `applyModuleView` `:535`.
- Tests pinning the page: `tests/test_my_requests_page.py` (ids, `MODULE_VIEW`, kept functions incl. `labelQueueCells`, `data-label` from every renderer), `tests/test_my_requests_actions.py`, `tests/test_my_requests_reliability.py`.
- Current service worker: `…-v297-my-requests-style` (`app.py:27385`).

## Execution steps

1. **Impeccable:** load `impeccable:impeccable` (craft) and re-read `DESIGN.md` "My Requests" (`:218`). No new critique.
2. **Form helper** (`accounting_center.html`): add `formLink(module, item)` returning the button HTML or `''` per decision 1 (status checks case-insensitive; liquidation status via `normalizeStatusLabel`). Use it in `renderActionRows` (by `item.module`), `renderReimbursementRows` (replaces the inline Package link), `renderTravelRequestRows`, `renderCashAdvanceRows` (uses `liquidation_id` / `liquidation_status`), `renderLiquidationRows` and `renderLeaveRequestRows`. Done = every row with a form shows one button; none on rejected/draft/pending rows or on cash advances without a submitted liquidation.
3. **Remove Requester** (decision 5): drop `'Requester'` from five `MODULE_VIEW.headers` arrays and the matching `<td>` in the five renderers; move the liquidation submitted/updated label under the record. Done = header and cell counts match (7) in every module.
4. **Trim Reference** (decision 6) in `renderTravelRequestRows` and `renderCashAdvanceRows`; add `.reference-purpose` (two-line clamp) to the page CSS. Done = no repeated record number; long purposes clamp with a full-text tooltip.
5. **Action groups** (decisions 3, 4): remove Details from `MODULE_VIEW.action.headers` and its `<td>`; insert the group heading rows; style `.action-group-row th` (muted, 0.78rem, 600, top padding; on phones a plain heading above its cards, no card border). Rewrite the action subtitle. Make sure `labelQueueCells()` and the phone card CSS skip `.action-group-row`. Done = three headed groups; the subtitle explains badge vs list.
6. **Compact phone cards** (decision 2): add `phoneHidden` to each `MODULE_VIEW` entry; `labelQueueCells()` adds `cell-phone-hidden`; phone CSS hides it. Record cell keeps its kind/sub-line so Type can hide. Done = typical card ≤ 260 px at 375 px; nothing an action needs is hidden.
7. **Starting state** (decision 7): update the default markup at `:261-312` (KPI labels/captions, title, headings, `d-none` on the filter). Done = no Reimbursements labels flash on a cold load of `/accounting_center`; `?module=reimbursements` still shows its filter.
8. **Self-review:** every id, `data-status`, `data-module-key` and function name from Batches A–C still exists (`selectAccountingModule`, `setAccountingTab`, `renderActionRows`, `actionButton`, `labelQueueCells`, `openPaidModal`, `openTravelCompletedConfirm`, both complete modals, `openCashAdvanceLiquidationDraft`, `postAccountingAction`, `readAccountingJson`, `fetchAccountingWithTimeout`, `showDialogError`, `setAccountingActionBusy`); empty/loading rows still span the table; no hardcoded accent hex; no `transition: all`.

## Deliberately excluded

- **Renaming "Reimbursement #1"** to a code — reimbursements have no record number; needs a backend numbering change.
- **Renaming the travel `package_download_url` / `package_preview_url` fields** in `app.py` (they point to the travel page, not a download) — other pages may read them; a separate cleanup after a usage check.
- **RFP downloads** — only relevant when money is due to the employee; reachable on the liquidation pages.
- **A cash advance form** — does not exist; building one is a new feature.
- **Changing what the badge counts** — Batch B decision; the subtitle explains it instead.
- **Search, sort, "New request" button, liquidation due-date countdown** — scan ideas for a later batch.
- **The record pages** (reimbursement, travel, cash advance, liquidation, leave).

## Verification

- **Tests** — `tests/test_my_requests_page.py` gains `MyRequestsBatchDSourceTests`: `formLink` exists and is called by all six renderers; the download routes appear in it, with `force_download=1` on the travel form and the travel liquidation Excel; no `'Requester'` in any `MODULE_VIEW.headers`; each module's headers length equals its renderer's cell count (count `<td` in each renderer's row template, excluding colspan rows); `action-group-row` rendered; `phoneHidden` on every module and `cell-phone-hidden` set in `labelQueueCells`; default markup has "Needs your action", "To fix" and `d-none` on `#accountingStatusFilter`; kept ids/functions guard. Update any existing assertion that pins the old headings or the Package link.
  - **Positive control:** run the new tests in-process against `git show HEAD:templates/accounting_center.html` (never `git stash`); all fail except the kept guard.
- **Focused run:** `tests/test_my_requests_*.py`, `test_dark_mode_readability`, `test_changelog_coverage`. Full suite not needed (one page plus the service worker version string).
- **Browser** on a copy of `scheduler.db` (temporary password on the copy only), owner's engineer-view account: at 1366 px light and graphite, check each module's download link with `fetch` in the page (status 200 and content type PDF / xlsx / ZIP); no button on rejected/pending/draft rows or plain cash advances; the action tab shows group headings and the new subtitle; every tab's headings align with its cells; a cold load shows no Reimbursements labels; every dialog action from Batches B–C still opens. At 375 px AMOLED: typical card ≤ 260 px, no horizontal scroll, taps ≥ 44 px, contrast ≥ 4.5:1 on group headings and labels; console clean. Clean up the copy, password and launch entry. One screenshot per theme as proof.

## After implementation

1. `app.py` service worker `CACHE_VERSION` `…-v298-my-requests-forms` (v297 kept as a history comment).
2. `static/changelog/releases.json`: release "Download Forms from My Requests" (audience `everyone`; items: form buttons, shorter phone cards, grouped action list).
3. `DESIGN.md` "My Requests" entry: download buttons, phone cards show only key columns (`phoneHidden`), action group headings, no Requester column.
4. `changes.md` bullets; this plan's Status with the commit and any differences.
5. Commit only `templates/accounting_center.html`, `app.py`, `static/changelog/releases.json`, `DESIGN.md`, `tests/test_my_requests_page.py` (and any other test file whose pins changed), `plans.md`, `changes.md`. Never `scheduler.db`, `output/`, `tmp/`, handoffs, `.impeccable/`, `.claude/` or other dirty files. Publish only on "commit and push".

## Risks

- **A download link errors for some status** (e.g. travel liquidation Excel with an invalid USD rate on a submitted record): the button opens a JSON error page. Safety net: buttons only on submitted-or-later records; the browser check tests one per module; the record page remains the fallback.
- **Hiding columns on phones hides something needed:** Actions, Status, Amount and the key column always stay; checked per module at 375 px.
- **Column count mismatch after removing Requester/Details** misaligns desktop headings: a source test compares header and cell counts per module.
- **Blast radius:** one template plus the service worker string; rollback = revert the commit.

# My Requests — Batch C: Dashboard Look and Phone Cards

**Status:** Executed — `d33eba2` (published to `main` 2026-10-12).
**Differences from the plan:** (1) The Investigation was wrong on one point: `app-dashboard.css:1201` hides every `.table-responsive table` at ≤768px (the dashboard swaps in its own phone lists), which hid the whole My Requests list on phones; the page's phone rule uses `.accounting-list .table-responsive .table-accounting` to win, and a source test guards it. (2) Stat cards on phones are one compact row each (label and caption left, number right; 213px for all three instead of ~370px) rather than plain stacked cards. (3) Refresh is `btn-outline-primary`, not `btn-outline-secondary`: Dashboard Style phase 3 measured the secondary outline at 4.48:1 on AMOLED. (4) `?v=31` was also pinned in `tests/test_timeline_desktop_collapse.py` and `tests/test_tsr_page_design.py`; both bumped to `?v=32` and added to the commit list. (5) `data-label` is set by one helper, `labelQueueCells()`, called at the end of each of the six row renderers (it reads `moduleView().headers`), so no render function repeats heading strings. (6) The whole `.accounting-shell` block in `app-dark-pages.css` (14 rules) was removed, not only the four tested selectors: the page now styles those parts on theme variables and carries its own dark pairs for pills, notes and balance cards.
**Approved:** 2026-10-12 (owner: "plan batch C", then "approved, write the plan" — including decision 1, load `app-dashboard.css` rather than move styles into the shell).
**Detailed:** 2026-10-12.
**Branch:** `main` (local first; publish only on "commit and push").
**Depends on:** Batches A (`2184b16`) and B (`a7dca6c`), both published. Batch C restyles B's "Needs your action" tab and Rejected button.

## Context

After Batches A and B, My Requests (`templates/accounting_center.html`) works correctly but still has the old look: a dark gradient hero, five large module cards, uppercase KPI cards with heavy shadows, a rounded `btn-group` status filter and coloured dialog headers. The dashboard moved to the shadcn-style cards in Dashboard Style phases 1–3, recorded in `DESIGN.md`. On phones the page is an 8-column table that scrolls sideways, while `DESIGN.md` requires stacked cards at ≤768px. Batch C gives My Requests the dashboard's look and phone cards, without changing behaviour.

## Decisions taken

1. **One source for the styles:** My Requests links `static/css/app-dashboard.css` (as `analytics.html` already does) and reuses `.dash-page-header`, `.dash-stat`, `.dash-card`, `.dash-panel`, `.dash-segment` and the pill tabs `.work-orders-tab`. No copies. Moving these into `app-shell.css` as shared components is a later option, not this batch.
2. **Layout, top to bottom:**
   - Page header: "My Requests" title, the one-line subtitle, Refresh as a quiet outline button. The gradient hero and the blue info box are removed; the "Only your own records are shown…" sentence becomes the header subtitle.
   - Module tabs: pill tabs with their count; they scroll sideways on phones. "Needs your action" stays first.
   - Three stat cards (label, number, the Batch A caption). Tone (amber/red) only above zero and only on the action tab's To fix / Your next step cards; never the accent.
   - List card: title and subtitle left; the status filter as a segmented control right (the per-module words from `MODULE_VIEW`, plus Rejected where B shows it, plus All).
3. **Phone cards (≤768px):** each row becomes a stacked card (16px radius) with a small label before each value — the `data-label` pattern already used in `templates/_liquidation_base.html:73`. Action buttons go full width; every control at least 44px tall.
4. **Plain dialogs:** dialog headers lose their green/blue/yellow bars (default close button); the colour stays on the confirm button (success green for Confirm Received and Mark Completed, accent for Travel Completed).
5. **Status pills stay semantic** (not re-themed by the accent), each with a dark pair at least 4.5:1.

## Investigation

- **Page CSS:** page-local styles at `accounting_center.html:3-360` (hero, kpi, module-tab, queue-card, accounting-tabs, status pills, `.row-note`, liquidation cells, empty state, media queries).
- **Reusable classes** in `app-dashboard.css`: `.dash-page-header` / `.dash-page-h1` / `.dash-page-sub` / `.dash-page-actions` (`:2158-2195`), `.dash-stats` / `.dash-stat*` (`:2197-2270`, four columns by default — My Requests needs three), `.dash-card` (`:2272`), `.work-orders-tabs` / `.work-orders-tab` (`:2408-2430`, overriding the older block at `:1745`), `.dash-panel` (`:2516`), `.dash-segment` (chart switch). The file's rules are class-scoped (checked: no global `body`/`.table`/`.card`/`.btn` selectors), so linking it on another page is safe. Current link: `dashboard.html:4` `?v=15`.
- **Dark rules that become dead:** `app-dark-pages.css:714-770` (`.accounting-shell .module-tab`, `.module-badge`, `:is(.kpi-card, .queue-card)`, `:is(.kpi-value, …)`, `.table-accounting th`, `.liquidation-row td`, `.liquidation-balance-card…`). `tests/test_appearance_themes.py:599-603` asserts `.accounting-shell .module-tab`, `.module-title`, `.module-desc` and `.accounting-shell :is(.kpi-value`, and pins `app-dark-pages.css?v=31` (`layout.html:531`). Rules still matching live markup (e.g. balance cards, table header) stay unless replaced.
- **Pinned by tests:** `tests/test_my_requests_page.py` (KPI ids `kpiPending*`/`kpiProcessing*`/`kpiPaid*`, `MODULE_VIEW`, kept functions including `renderActionRows`), `tests/test_my_requests_actions.py`, `tests/test_my_requests_reliability.py` (timeout helper). Ids, `data-status`, `data-module-key` and every JS function name stay.
- **Current versions:** service worker `…-v296-my-requests-actions` (`app.py:27384`); `app-dark-pages.css?v=31`.

## Execution steps

1. **Impeccable:** load the `impeccable:impeccable` skill (craft) and read `DESIGN.md` Page Header, Stat Cards, Tabs, Chips. No new critique this session.
2. **Header** (`accounting_center.html`): add `<link rel="stylesheet" href="{{ url_for('static', filename='css/app-dashboard.css') }}?v=15">`; replace the hero and info box with `.dash-page-header` → `h1.dash-page-h1` "My Requests", `p.dash-page-sub` (subtitle + own-records sentence), `.dash-page-actions` with Refresh (`btn btn-outline-secondary`, `onclick="refreshAccountingQueue()"`). Done = no gradient, no info box.
3. **Module tabs:** `#accountingModuleTabs` gets `class="work-orders-tabs" role="tablist" aria-label="Request type"`; `renderAccountingModuleTabs` outputs `button.work-orders-tab[role=tab][aria-selected][data-module-key]` with the label and a `.work-orders-tab-count`. Click delegation and `setAccountingModule` unchanged; the busy lock still disables the tabs (update the selector in `setAccountingActionBusy`). Done = pill tabs, horizontal scroll on phones.
4. **Stat cards:** the three KPI cards become `.dash-stat` inside `.dash-stats` with a page rule for three columns (one column ≤576px if it reads better; check in the browser). Keep every `kpi*` id on the matching `.dash-stat-name` / `.dash-stat-num` / `.dash-stat-help`. `updateSummary` sets `dashboard-metric-alert` (To fix) / `dashboard-metric-warn` (Your next step) only on the action tab and only above zero. Done = numbers neutral elsewhere.
5. **List card and filter:** the queue card becomes `.dash-card` with `.dash-card-title#activeQueueTitle` and `.dash-card-sub#queueSubtitle`; the status buttons become `.dash-segment` buttons with `aria-pressed` (keep `data-status`, the Rejected button's show/hide, and the hidden filter on the action tab). Update `selectAccountingModule` / `setAccountingTab` to set `aria-pressed` instead of `.active`, and the busy-lock selector. Done = filter works in all modules.
6. **Phone cards:** every render function (`renderActionRows`, `renderReimbursementRows`, `renderTravelRequestRows`, `renderCashAdvanceRows`, `renderLiquidationRows`, `renderLeaveRequestRows`) adds `data-label` to each `<td>`, taken from `MODULE_VIEW[module].headers` (one helper, no repeated strings). Page CSS at `max-width: 768px`: hide `thead`, each `tr` a card (16px radius, hairline border, surface), each `td` a block with `td[data-label]::before` label (muted, 0.72rem, 4.5:1), `.action-btns` stacked full width, buttons ≥44px, wrapping text (override the shell's `nowrap`). Empty and loading rows stay full width without a label. Done = no horizontal scroll at 375px.
7. **Dialogs:** the four modals drop `bg-success` / `bg-warning` / `text-white` / `btn-close-white` from their headers; confirm buttons keep `btn-success` (Confirm Received, both Mark Completed) and Travel Completed becomes `btn-primary`. Dialog error slots from Batch A unchanged.
8. **CSS cleanup:** delete page-local rules replaced by the shared classes (hero, kpi-card/label/value, queue-card, module-tabs/tab/title/desc/badge, coming-soon pill if unused, accounting-tabs, old media queries); keep `.status-pill` (+ tones with dark pairs), `.row-note`, liquidation money/balance cells, `.travel-row-overdue`, phone-card rules — all on theme variables. In `app-dark-pages.css` remove the `.accounting-shell` rules that no longer match any markup (search each class first), bump `layout.html` to `app-dark-pages.css?v=32`, and update `test_appearance_themes.py` (drop the four removed selectors, keep `[class*="-kpi-value"]` and `[class*="-stat-value"]`, new version). Done = no dead selectors for this page.
9. **DESIGN.md:** a "My Requests" component entry — dashboard header, pill module tabs, three stat cards with tone only on the action tab, segmented status filter, phone row cards with `data-label`, plain dialog headers.
10. **Self-review:** every function and id Batches A and B rely on still exists (`selectAccountingModule`, `setAccountingTab`, `renderActionRows`, all open/confirm pairs, `postAccountingAction`, `readAccountingJson`, `fetchAccountingWithTimeout`, `showDialogError`); no hardcoded accent hex; no `transition: all`; no `-stat-value` / `-kpi-value` class names introduced.

## Deliberately excluded

- **Moving the dashboard styles into `app-shell.css`** — decision 1; a later refactor if a third page needs them.
- **Charts or trend badges** — no recorded history for requests.
- **New features** (search, "New request" button) — not part of the restyle.
- **The record pages My Requests links to** (reimbursement, travel, cash advance, liquidations, leave) — separate pages.

## Verification

- **Tests** — `tests/test_my_requests_page.py` gains source tests: `app-dashboard.css` linked; no `accounting-hero` and no info box; `work-orders-tab` and `dash-stat` used; `data-label` produced by every render function (via the helper); no `bg-success` / `bg-primary` / `bg-warning` in modal headers; kept ids and functions guard. `tests/test_appearance_themes.py` updated for the removed selectors and `?v=32`.
  - **Positive control:** run the new tests in-process against `git show HEAD:<file>` (never `git stash`); all fail except the kept guard.
- **Focused run:** `tests/test_my_requests_*.py`, `test_appearance_themes`, `test_dark_mode_readability`, `test_dashboard_style`, `test_changelog_coverage`.
- **Full suite once** before publishing (`venv/Scripts/python.exe scripts/run_suite.py`, main folder): `app-dark-pages.css` and `layout.html` are shared.
- **Browser** on a copy of `scheduler.db` (temporary password on the copy only), engineer account: 1366px light and graphite, 375px AMOLED. Every module tab and status filter; every dialog action (Confirm Received, Travel Completed, both Mark Completed, Create Liquidation) still works and refreshes; the action tab's tone only above zero; phone rows are cards with labels, no horizontal scroll, taps ≥44px; contrast ≥4.5:1 for pills, notes, labels and muted text; console clean. Clean up the copy, password and launch entry. One screenshot per theme as final proof.

## After implementation

1. `app.py` service worker `CACHE_VERSION` `…-v297-my-requests-style` (v296 kept as a history comment).
2. `static/changelog/releases.json`: release "A Cleaner My Requests" (audience `everyone`).
3. `DESIGN.md` (step 9), `changes.md` bullets, this plan's Status with the commit and any differences.
4. Commit only `templates/accounting_center.html`, `templates/layout.html`, `static/css/app-dark-pages.css`, `app.py`, `tests/test_my_requests_page.py`, `tests/test_appearance_themes.py`, `tests/test_timeline_desktop_collapse.py`, `tests/test_tsr_page_design.py`, `static/changelog/releases.json`, `DESIGN.md`, `plans.md`, `changes.md`. Never `scheduler.db`, `output/`, `tmp/`, handoffs, `.impeccable/` or other dirty files. Publish only on "commit and push".

## Risks

- **A future dashboard CSS change alters My Requests:** the trade-off of one source; `DESIGN.md` records the classes as shared so changes are deliberate.
- **Dark contrast drops when old overrides go:** the shared classes have dark pairs; the browser check measures contrast in graphite and AMOLED.
- **Busy lock or filter state breaks when classes change:** selectors in `setAccountingActionBusy`, `selectAccountingModule` and `setAccountingTab` are updated in the same step, and every action is clicked in the browser check.
- **Blast radius:** one page plus one shared dark CSS file; rollback = revert the commit.

# My Requests — Batch B: "Needs your action" Tab, Rejected Tabs, Sidebar Badge

**Status:** Executed — `a7dca6c` (published to `main` 2026-10-12).
**Differences from the plan:** `templates/dashboard.html` bumped to `app-dashboard.js?v=15` (so the new staff-card text is not cached) and `tests/test_dashboard_style.py` cache assertion fixed (already failing on `HEAD`) — add both to the commit list. Rejected travel liquidations are read-only (`can_edit_travel_liquidation`: draft/returned only); kept under To fix as planned but labelled "Rejected: open it to see why". Leave Provisional confirmed as "employee still owes the signed form". The kept-functions guard fails on `HEAD` too, since it now lists the new `renderActionRows`. Action subtitle reads "N item(s) waiting on you".
**Approved:** 2026-10-12 (owner chose: approved-but-unreceived money listed without counting in the badge; "Mark travel completed" only after the return date; My Requests opens on "Needs your action"; then "approved, write the plan").
**Detailed:** 2026-10-12.
**Branch:** `main` (local first; publish only on "commit and push").
**Depends on:** Batch A (executed 2026-10-12, **not yet committed**). Commit Batch A first or publish both together.

## Context

The 2026-10-12 scan found that the red "My Requests" sidebar badge (`my_requests_action`) counts Rejected/Returned records that the page mostly hides — rejected reimbursements never appear, rejected travel requests and cash advances only under All — and that users must click through five tabs to find what needs them. Batch B adds one "Needs your action" list across all modules, makes the badge count exactly that list's to-do groups, and adds Rejected tabs. It also closes a gap left by Batch A: the two GET list loads still parse responses with `res.json()`.

## Decisions taken

1. **Three groups in "Needs your action"**; the badge counts only the first two:

   | Group | Contents | Action |
   | --- | --- | --- |
   | **To fix** | Rejected/Returned reimbursements, travel requests, cash advances, travel liquidations, cash advance liquidations, leave | Open the record (link) |
   | **Your next step** | Mark travel completed (funds received **and** `return_date` before today); Create cash advance liquidation (received, no liquidation); Continue a **draft** liquidation (travel or cash advance); Mark an **approved** liquidation completed (travel or cash advance, where the existing `can_complete` rule allows); leave in Form to Follow or Provisional | Same buttons and dialogs as the module tabs |
   | **Confirm when you receive it** | Approved reimbursements (not paid), approved travel requests without `funds_received_at`, approved cash advances not received | Confirm Received — **listed, not counted in the badge** (owner) |

2. **My Requests opens on "Needs your action"**, always the first tab; empty state "Nothing needs you right now." `?module=` links still open their own tab (owner).
3. **Rejected records stay in "To fix" until resubmitted** — every module lets the requester edit Rejected records, so this is correct, not stale.
4. **Rejected tab** (fifth status button) for Reimbursements, Travel Requests and Cash Advances only; Liquidations and Leave already list rejected records under To do / Open.
5. **Drafts of new requests are not actions** (the user may still be filling them in); **draft liquidations are** (they are owed).
6. **"Mark travel completed" appears only after the return date** (owner).

## Investigation

- **Badge:** `/api/nav/pending-summary` (`app.py:28283-28301`) counts `user_id == current_user.id` and status in `Rejected`/`Returned` on `ReimbursementHeader`, `TravelRequest`, `TravelLiquidationHeader`, `CashAdvanceHeader`, `CashAdvanceLiquidationHeader`; leave is missing and travel participants are missed. Consumers: sidebar `layout.html:1133` (label "needing attention"), staff dashboard `loadStaffWaiting()` `app-dashboard.js:1655` ("… need attention"), `tests/test_layout_sidebar.py:873` (only asserts an int). The endpoint runs on every page load and is shared code → full suite before publishing.
- **Editable on rejection:** `REIMBURSEMENT_EDITABLE_STATUSES = {'Draft', 'Rejected'}` (`app.py:36876`), `TRAVEL_REQUEST_EDITABLE_STATUSES` (`:41952`), cash advance save allows draft/returned/rejected (`save_cash_advance`, `:68538`), `TRAVEL_LIQUIDATION_EDITABLE_STATUSES = {'draft', 'returned'}` (`:50217`), `CASH_ADVANCE_LIQUIDATION_EDITABLE_STATUSES = {'draft', 'returned', 'rejected'}` (`:69192`), leave `EDITABLE_STATUSES` (`leave_feature.py:26`). Note: a **rejected travel liquidation** is not in the editable set; it still goes to To fix (it is what the old badge counted) — the executor confirms on the liquidation page what the user can do with it and records the finding under this plan.
- **Status normalisers:** reimbursement maps `returned` → Rejected (`:36880`); cash advance maps `returned` → Rejected (`:66884`); travel liquidation keeps Rejected and Returned (`:47687`); cash advance liquidation keeps both (`:69205`).
- **Travel trip-over:** reminder logic uses `return_date` and `TRAVEL_LIQUIDATION_REMINDER_DAYS` (`run_travel_request_liquidation_reminder_check_for_current_user`, `:13273`). Batch B uses `return_date < today` combined with the existing `can_mark_ready_for_liquidation` rule (`accounting_center_travel_request_item_to_dict`, `:47040`: Funds Received, `funds_received_at` set, no liquidation started/completed).
- **Completion rules to reuse:** cash advance liquidation `can_complete_liquidation` (owner, status Approved, not completed — `accounting_center_cash_advance_item_to_dict`, `:51130`); travel liquidation uses `can_complete_liquidation` from `travel_liquidation_to_dict` — reuse its rule, do not invent a new one.
- **Record URLs:** `/reimbursement?reimbursement_id=` (`:10647`), `/travel_request?travel_request_id=`, `/cash_advance?cash_advance_id=`, `/travel_liquidation?liquidation_id=`, `/cash_advance_liquidation?liquidation_id=`, `/leave_request?open=`.
- **Rejected filter:** travel (`:47218`) and cash advance (`:51190`) queues already accept `status=rejected`; the reimbursement queue (`:51530`) does not.
- **Id clash:** `openCashAdvanceLiquidationDraft` looks up `accountingItems` by `row.id` or `row.cash_advance_id`; on a mixed list another module's id can match.
- **Leave statuses:** confirm in `leave_feature.py` that Form to Follow and Provisional both mean "the employee still has to file/complete something" before listing them under Your next step; if Provisional means something else, drop it and note the finding here.

## Execution steps

1. **Shared helper** (`app.py`, beside the My Requests helpers): `my_requests_action_items(user=None)` returns a list of light dicts `{module, id, record_no, kind, group ('fix'|'next'|'confirm'), label (what to do), action, url, amount, currency, date_label, status}`. Queries use `apply_my_accounting_owner_filter` for reimbursements, travel requests (participants included), cash advances and travel liquidations; `user_id` for cash advance liquidations and leave. Each module is wrapped in its own try/except that logs and skips (as the badge does today). No full `*_to_dict` serialisers. Done = every rule in decision 1 produces an item; nothing for other users.
2. **Badge** (`app.py` `pending-summary`): `my_requests_action` = count of `fix` + `next` items from the helper. `layout.html:1133` label → "needing your action"; `app-dashboard.js` `loadStaffWaiting()` text → "1 of your requests needs your action" / "N of your requests need your action". Done = badge equals the action tab's badge.
3. **Queue and module** (`app.py`): `GET /get_accounting_action_queue` (`@login_required`, `require_accounting_center_access()`), returning `{success, queue: 'action', items, count, summary: {pending: fix, processing: next, paid: confirm}}`. Add `{'key': 'action', 'label': 'Needs your action', 'description': 'Everything waiting on you across your requests.', 'status': 'active', 'queue_endpoint': '/get_accounting_action_queue', 'order': 0}` to `ACCOUNTING_CENTER_MODULES`, an `action` branch in `accounting_center_module_to_dict` (badge = fix + next), and the route in the JSON route list near `app.py:1350`. Done = module listed first with its badge.
4. **Page** (`templates/accounting_center.html`): `MODULE_VIEW.action` with KPI labels "To fix" / "Your next step" / "Confirm when received", headings Record · Type · Details · Amount · Date · Status · What to do · Actions, and no status buttons (hidden for this module). New `renderActionRows(items)` sorted fix → next → confirm; the button per `action`: `open` → link; `confirm_received` → `openPaidModal(id, module)`; `travel_completed` → `openTravelCompletedConfirm(id)`; `complete_travel_liquidation` → `openTravelLiquidationCompleteModal(id)`; `complete_cash_advance_liquidation` → `openCashAdvanceLiquidationCompleteModal(id)`; `create_cash_advance_liquidation` → `openCashAdvanceLiquidationDraft(id)`. `openCashAdvanceLiquidationDraft` matches rows by module as well as id. Initial `activeAccountingModule = 'action'` (URL params still win). Empty state "Nothing needs you right now." Done = each button acts on the right record and the list refreshes after an action.
5. **Rejected tabs:** fifth button `data-status="rejected"`, shown only when `MODULE_VIEW[key].statusLabels.rejected` exists (Reimbursements, Travel Requests, Cash Advances; label "Rejected"). Add `'rejected'` to the status lists in `selectAccountingModule`, `setAccountingTab` and the URL parser. `get_accounting_reimbursement_queue` accepts `rejected` (status Rejected or Returned, normalised lower-case). Done = the tab lists the user's rejected records in all three modules.
6. **Safe list loads:** `readAccountingJson(res)` — reads text, reports an HTML/redirect reply as "Your session has expired. Please log in again."; used by `loadAccountingModules` and `refreshAccountingQueue` instead of `res.json()`. Keep `fetchAccountingWithTimeout` and the timeout constant (pinned by `test_my_requests_reliability.py`).
7. **Self-review:** every `onclick` target and delegated handler is defined; Batch A tests still pass; the badge and the action tab both use `my_requests_action_items`; no id used elsewhere removed.

## Deliberately excluded

- **Dismissing an abandoned rejected record** — it leaves the list when resubmitted or deleted on its own page.
- **LPR** — not part of My Requests.
- **Drafts of new requests** — decision 5.
- **Email/notification changes.**
- **Batch C** (restyle, phone cards), search box, "New request" button.

## Verification

- **Tests** — new `tests/test_my_requests_actions.py` on a seeded user: one record per rule lands in the right group; approved-unreceived money is listed but not counted; a funds-received trip appears only once `return_date` is past; another user's records never appear (travel participant does); `pending-summary` `my_requests_action` equals fix + next; reimbursement queue `status=rejected` returns rejected records; source tests — `action` module first and default, Rejected button and `'rejected'` in the status lists, the action → function map, `readAccountingJson` in both loads, kept-functions guard (Batch A list plus `renderActionRows`). Update the label assertions in `test_layout_sidebar.py` / `test_dashboard_*` if they pin "attention".
  - **Positive control:** run the new tests in-process against `git show HEAD:<file>` (never `git stash`); all fail except the kept-functions guard.
- **Focused run:** `tests/test_my_requests_*.py`, `test_layout_sidebar`, `tests/test_dashboard_*.py`, `test_leave_request_workflow`, `test_provisional_leave`, `test_changelog_coverage`, `test_dark_mode_readability`.
- **Full suite once** before publishing (`venv/Scripts/python.exe scripts/run_suite.py`, main folder): `pending-summary` and `layout.html` are shared.
- **Browser** on a copy of `scheduler.db` (temporary password on the copy only): an engineer account at 1366 px (light, graphite) and 375 px (AMOLED). Sidebar badge = action-tab badge; each action button opens the right dialog or record and the list refreshes; Rejected tabs work in all three modules; empty state when nothing is due; a staff account's dashboard card text; contrast ≥ 4.5:1, no horizontal scroll, tap targets ≥ 44 px, console clean. Clean up the copy, password and launch entry. One screenshot per theme as final proof.

## After implementation

1. `app.py` service worker `CACHE_VERSION` `…-v296-my-requests-actions` (v295 kept as a history comment).
2. `static/changelog/releases.json`: release "Needs your action" (audience `everyone`).
3. `changes.md` bullets; this plan's Status with the commit and any differences.
4. Commit only `app.py`, `templates/accounting_center.html`, `templates/layout.html`, `static/js/app-dashboard.js`, `tests/test_my_requests_actions.py`, any updated test files, `static/changelog/releases.json`, `plans.md`, `changes.md`. Never `scheduler.db`, `output/`, `tmp/`, handoffs, `.impeccable/` or other dirty files. Publish only on "commit and push".

## Risks

- **Badge slows every page:** about 10 small queries (5 today); per-module try/except keeps a failure to that module's count.
- **Badge and list disagree:** one helper feeds both; a test pins equality.
- **Wrong record acted on in the mixed list:** each item carries module + id; the cash advance lookup matches by module.
- **Blast radius:** this page, the sidebar badge and the staff dashboard card; rollback = revert the commit.

# My Requests — Batch A: Fixes and Cleanup

**Status:** Executed — published to `main` on 2026-10-12 on the owner's "commit and push" (commit `2184b16`; owner: "execute batch A in plans.md"). Tests: 10 in `tests/test_my_requests_page.py`; 9 fail on `HEAD`, the kept-functions guard passes on both. Focused run: 51 tests OK. Browser check on a DB copy passed (engineer account; graphite and light at 1366 px, AMOLED at 375 px). Differences from the plan: the subtitle is built from `MODULE_VIEW[...].recordName` instead of a `subtitle(count)` function; `updateAccountingQueueHeaders` and `currentModuleRecordName` were removed (folded into `applyModuleView`); the account used for the browser check has no leave records, so the Leave badge is proven by the endpoint test.
**Approved:** 2026-10-12 (owner: "plan batch A first", then "approved, write the plan" — including the label table in decision 1).
**Detailed:** 2026-10-12.
**Branch:** `main` (local first; publish only on "commit and push").

## Context

A read-only scan of My Requests (`/accounting_center`, `templates/accounting_center.html`) on 2026-10-12 found wrong labels, a half-styled Leave tab, dialog errors hidden behind the dialog, unguarded JSON parsing and dead code. Batch A fixes these on this page only; behaviour is otherwise unchanged. Batch B ("Needs your action" tab, Rejected tabs, sidebar badge rule) and Batch C (restyle to the dashboard look, phone cards) are separate plans.

## Decisions taken

1. **Per-module labels.** `data-status` values stay `pending/processing/paid/all`; only the visible words change. The "All" button stays "All".

   | Module | Status buttons (pending · processing · paid) | KPI labels |
   | --- | --- | --- |
   | Reimbursements | Pending · Processing · Paid | Waiting for payment · Processing · Paid |
   | Travel Requests | Awaiting approval · Approved · Funds received | same as buttons |
   | Cash Advances | Awaiting approval · Approved · Received | same as buttons |
   | Liquidations | To do · Submitted · Completed | same as buttons |
   | Leave | Open · Submitted · Approved | same as buttons |

2. **"Engineer" column → "Requester"**, and every module gets column headings that match its data (step 2).
3. **Record buttons say "Open"** everywhere. Travel Request and Cash Advance records open in the same tab (`target="_blank"` removed); the reimbursement Package download keeps its new tab.
4. **URL memory moves from Batch B into A**: the page writes `?module=&status=` on every switch, so Back from a record (decision 3) returns to the same tab and status.
5. **Server routes stay**: `/accounting_mark_processing` and `/get_accounting_travel_completion_queue` are kept (old cached pages or bookmarks may still call them). Only the hidden `travel_completion` entry leaves `ACCOUNTING_CENTER_MODULES`.

## Investigation

- **KPI captions are fixed text** (`accounting_center.html:393-413`) and only true for Reimbursements. Bucket meanings per module: reimbursements `app.py:46903` (pending = approved, not processing/paid), travel `:46947` (pending = Submitted), cash advances `:51043` (pending = Submitted), liquidations `:51354` (pending = draft/returned/rejected), leave `leave_feature.py:805` (pending = Draft/Form to Follow/Provisional/Rejected; processing = Submitted; paid = Approved).
- **Column headings** switch only for Leave (`:851-854`). Liquidation rows put cash advance under "Amount", actual expenses under "Approved" and the balance under "Details / Reference" (`:1081-1094`); Cash Advance puts "Needed:" under "Period" (`:1216`).
- **Leave tab:** status uses the undefined class `status-badge` (`:982`); Open is outside `.action-btns` (`:984`), so it is not right-aligned and not locked while busy; empty state differs from the other tabs (`:973`). `accounting_center_module_to_dict` (`app.py:47090`) has no leave branch, so the badge is always 0. The subtitle falls through to `data.message || "… module foundation ready"` (`:935-936`); the leave endpoint sends no `message`, so it reads "Leave Requests module foundation ready".
- **Headings on direct link:** startup (`:1609-1618`) and `openLiquidationsModuleAfterTravelCompleted` (`:870-893`) never call `updateAccountingQueueHeaders()`. The module-switch logic is duplicated four times (`setAccountingModule` `:829`, `openLiquidationsModuleAfterTravelCompleted`, `applyAccountingUrlParams` `:1303`, startup).
- **Dialog errors** go to `#accountingAlert` inside the page card, behind the modal backdrop, and auto-hide after 4.5 s (`:748-754`); e.g. "Please select a received method" (`:1560-1563`) is invisible.
- **Session expiry:** `openCashAdvanceLiquidationDraft` (`:1136`), `confirmTravelCompletedReady` (`:1358`), `confirmMarkProcessing` (`:1511`) and `confirmMarkPaid` (`:1581`) call `res.json()` on what may be the login page's HTML ("Unexpected token <"). The two complete functions already parse text safely (`:1410-1416`, `:1468-1474`).
- **Liquidation badge** counts `draft, returned` (`app.py:47101`), but the Pending list includes `rejected` (`app.py:51390`).
- **Dead code (verified by search, no callers outside this file):** the `#processingModal` markup (`:464-483`), `processingModalInstance`, `openProcessingModal`, `confirmMarkProcessing`, `processingBtn = ''` (`:1003`); `currentModuleLabel` (defined, never called); `isTravelCompletionModule`, `visibleAccountingModules` (the list is already filtered in `loadAccountingModules`), `renderComingSoonQueue` and the `is_coming_soon` / `coming_soon` branches (no coming-soon module remains once `travel_completion` leaves the list); the `'liquidations'` branches in `openPaidModal` and `confirmMarkPaid` (no button opens the paid dialog for liquidations). CSS: six near-identical note pills `.liquidation-reminder-note`, `.ready-liquidation-note`, `.cash-advance-reference-note`, `.cash-advance-ready-note`, `.cash-advance-completed-note`, `.travel-liquidation-completed-note` (`:138-216`).
- **Pinned by tests:** `tests/test_my_requests_reliability.py` requires `const ACCOUNTING_REQUEST_TIMEOUT_MS = 15000;`, `function fetchAccountingWithTimeout`, at least 3 `fetchAccountingWithTimeout(` occurrences and the timeout message. `tests/test_leave_request_workflow.py:83` requires `activeAccountingModule === 'leave_requests'`. Both must keep passing.
- `LeaveRequest` is available in `app.py` (used at `:28272`). Changelog audiences: `CHANGELOG_DIGEST_AUDIENCES` (`app.py:28685`) includes `everyone`. Dark overrides for this page live in `static/css/app-dark-pages.css:714-770` (no rules for the note pills).

## Execution steps

1. **One module switch** (`accounting_center.html`): add `selectAccountingModule(key, status='pending')` that sets `activeAccountingModule`, `activeQueueEndpoint`, `accountingStatus`, the active status button, the status-button labels, KPI labels and captions, column headings, `#activeQueueTitle`, and writes `?module=<key>&status=<status>` with `history.replaceState`. `setAccountingModule`, `setAccountingTab`, `openLiquidationsModuleAfterTravelCompleted`, `applyAccountingUrlParams` and the `DOMContentLoaded` handler call it instead of their own copies. Keep the `activeAccountingModule === 'leave_requests'` check the leave test pins. Done = Leave headings correct on `?module=leave_requests`; a refresh keeps module and status.
2. **Per-module view map**: one `MODULE_VIEW` object keyed by module with `statusLabels` (pending/processing/paid), `kpi` (label + caption ×3), `headers` (8), `subtitle(count)` and `recordName`. Give the three KPI captions ids (`kpiPendingCaption`, `kpiProcessingCaption`, `kpiPaidCaption`) and the KPI labels ids. Remove the `if` chain at `:930-939`, `updateAccountingQueueHeaders`'s inline arrays and `currentModuleRecordName`. Headings:
   - Reimbursements: Record · Requester · Period · Amount · Approved · Status · Payment · Actions
   - Travel Requests: Record · Requester · Travel dates · Amount · Approved · Status · Reference · Actions
   - Cash Advances: Record · Requester · Needed by · Amount · Approved · Status · Reference · Actions
   - Liquidations: Record · Requester · Trip · Cash advance · Actual expenses · Status · Balance · Actions
   - Leave: Record · Requester · Leave dates · Leave type · Weekdays · Status · HR handoff · Actions
   The Cash Advance Period cell drops its "Needed:" prefix (the heading says it). Done = every module shows its own labels, captions, headings and subtitle.
3. **Leave tab**: `renderLeaveRequestRows` uses `status-pill` with the dot icon, wraps Open in `.action-btns`, and uses the shared `empty-state` markup ("No leave requests found"). `app.py` `accounting_center_module_to_dict`: add a `leave_requests` branch — counts per bucket with the same status sets as `leave_feature.py:810-827`, `badge_count` = pending + processing (Draft, Form to Follow, Provisional, Rejected, Submitted), filtered by `user_id == current_user.id`. Done = Leave badge equals the number of open leave records.
4. **Liquidation badge**: `app.py:47101` counts `['draft', 'returned', 'rejected']`. Done = badge equals the Pending list length.
5. **Errors inside dialogs**: each of the four dialogs (`paidModal`, `travelCompletedConfirmModal`, `cashAdvanceLiquidationCompleteModal`, `travelLiquidationCompleteModal`) gets a hidden `<div class="alert alert-danger d-none" data-dialog-error role="alert">` at the top of its body. Add `showDialogError(modalId, message)` and clear it whenever the dialog opens. Missing received method marks `#paymentMethod` `is-invalid` and shows the error in the dialog. Every confirm function shows failures in its dialog. `showAccountingAlert` auto-hides only `success` and `info`. Done = errors are readable while the dialog is open.
6. **One POST helper**: `postAccountingAction(url, body={})` — POST with JSON, `Accept: application/json` and `X-CSRFToken: getCSRFToken()`; reads `res.text()`; if `res.redirected` or the text is not JSON, throws "Your session has expired. Please log in again." (HTML reply) or the server text; throws `data.error || data.message` when `!res.ok || data.success === false`; returns `data`. Used by `openCashAdvanceLiquidationDraft`, `confirmTravelCompletedReady`, `confirmCashAdvanceLiquidationComplete`, `confirmTravelLiquidationComplete`, `confirmMarkPaid`. `fetchAccountingWithTimeout` and its 15 s timeout stay for the GET loads. Done = no `res.json()` left in action functions.
7. **Copy**: remove the "S12 My Requests" eyebrow; subtitle "Your reimbursements, travel, cash advances, liquidations and leave, and what each one is waiting for."; info box becomes one line "Only your own records are shown. Confirm money you've received and finish your liquidations here."; status group `aria-label="Status filter"`; Travel "View" and Cash Advance "Open" both read "Open" and lose `target="_blank"`. Done = no phase codes or "foundation ready" text reachable on the page.
8. **Cleanup**: delete the dead code listed under Investigation; remove the `travel_completion` dict from `ACCOUNTING_CENTER_MODULES` (`app.py:46874-46882`; route, helper and the `:1356` list entry stay); replace the six note CSS rules with `.row-note` plus `.row-note--ok`, `.row-note--info`, `.row-note--warn` and update the render functions. Immediately before deleting each name, search `templates/`, `static/`, `app.py`, `leave_feature.py` and `tests/` again. Done = the searches return nothing for removed names.
9. **Self-review**: read the diff; every function referenced by an `onclick`, `data-` handler or the click delegation is still defined — `openPaidModal`, `confirmMarkPaid`, `openTravelCompletedConfirm`, `confirmTravelCompletedReady`, `openCashAdvanceLiquidationCompleteModal`, `confirmCashAdvanceLiquidationComplete`, `openTravelLiquidationCompleteModal`, `confirmTravelLiquidationComplete`, `openCashAdvanceLiquidationDraft`, `refreshAccountingQueue`, `setAccountingModule`, `setAccountingTab`; no id used by other code removed; `getCSRFToken` still comes from `layout.html`.

## Deliberately excluded

- **Sidebar "needs attention" badge rule (scan B1), "Needs your action" tab, Rejected tabs** — Batch B; they change what the page lists, not just how.
- **Restyle to the dashboard look and phone card layout** — Batch C (Impeccable).
- **Removing `/accounting_mark_processing` and `/get_accounting_travel_completion_queue`** — decision 5.
- **Access check on `/get_accounting_leave_request_queue` for approver-only accounts** — it only returns the caller's own records; a leave-module change, not this page.
- **Liquidation due date countdown, search box, "New request" button** — scan ideas for later batches.

## Verification

- **Tests** — new `tests/test_my_requests_page.py`:
  - Source: no `S12 My Requests`, no `status-badge`, no `processingModal`, no `foundation ready`; `MODULE_VIEW` has all five module keys and the Leave and Liquidations headings above; `postAccountingAction(` used by all five action functions and no `res.json()` inside them; four `data-dialog-error` slots; `history.replaceState` in `selectAccountingModule`; Travel/Cash Advance rows have no `target="_blank"`; kept-functions guard (step 9 list); `fetchAccountingWithTimeout` and the timeout constant unchanged.
  - Endpoint: `/get_accounting_center_modules` for a test engineer — Leave badge equals that user's Draft + Form to Follow + Provisional + Rejected + Submitted leave count; a `rejected` travel liquidation is counted in the Liquidations badge; no `travel_completion` module in the list.
  - **Positive control:** run the new tests in-process against `git show HEAD:<file>` (never `git stash`); all fail except the kept-functions guard.
- **Focused run:** `tests/test_my_requests_*.py`, `test_leave_request_workflow`, `test_provisional_leave`, `test_changelog_coverage`, `test_dark_mode_readability`. Full suite not needed (one page plus two page-specific counts in `app.py`).
- **Browser** on a copy of `scheduler.db` (temporary passwords on the copy only): an engineer account at 1366 px in light and graphite, and 375 px in AMOLED. Every module × status shows its labels, captions, headings, subtitle and badge; a refresh and a direct `?module=leave_requests` link keep the view; Confirm Received with no method shows the error inside the dialog; Open on a Travel and a Cash Advance record goes to it and Back returns to the same tab; notes readable in all themes (contrast ≥ 4.5:1); no horizontal scroll; tap targets ≥ 44 px on phones; console clean. Clean up the copy, passwords and launch entry. One screenshot per theme as final proof.

## After implementation

1. `app.py` service worker `CACHE_VERSION` `…-v295-my-requests-fixes` (v294 kept as a history comment).
2. `static/changelog/releases.json`: release "Clearer My Requests" (audience `everyone`) — labels per tab, errors shown in the dialog, the page remembers your tab.
3. `changes.md` bullets; this plan's Status with the commit and any differences.
4. Commit only `templates/accounting_center.html`, `app.py`, `tests/test_my_requests_page.py`, `static/changelog/releases.json`, `plans.md`, `changes.md`. Never `scheduler.db`, `output/`, `tmp/`, handoffs, `.impeccable/` or other dirty files. Publish only on "commit and push".

## Risks

- **Merging four module-switch copies breaks a tab or an action:** the kept-functions test plus a browser click-through of every module, status and dialog.
- **Leave badge disagrees with the list:** the same status sets as `leave_feature.py`, pinned by an endpoint test.
- **Same-tab Open loses context:** covered by URL memory (decision 4) and the Back check in the browser sequence.
- **Blast radius:** one page plus two badge counts; rollback = revert the commit.

# Manager Chart — Scheduled vs Completed

**Status:** Executed — published to `main` on 2026-10-12 on the owner's "commit and push" (commit `ea11c35`, together with Dashboard Style phase 2; owner: "go"). Tests: 5 source tests and 2 endpoint tests added to `tests/test_dashboard_style.py`; all 5 source tests fail on `HEAD`. Focused run: 192 tests OK. Browser check on a DB copy passed: `robert` (graphite and light, 1366 px), `rodito` (AMOLED, 375 px), `jonamar` (engineer chart still one line, no `company_scheduled` request).
**Differences from the plan:**
- **Positive control:** the kept-functions guard also fails on `HEAD`, because `loadManagerActivity` comes from phase 2, which is not committed yet. On the phase 2 working tree it passes. On `HEAD`, `company_scheduled` returns 400.
- **Empty state** with the comparison reads "No scheduled visits in this range." (shown only when both lines are zero).
- **Endpoint shape:** `company_scheduled` and `company_completed` share one base query (`visits`; `completed` adds the status filter), so both lines always use the same filters and scope.
- **Data on the DB copy:** 9 visits scheduled and 5 completed in the last 3 months (it matches a SQL count on the copy). The readout reads, for example, "Week of Aug 18 · 5 scheduled · 4 completed".
**Approved:** 2026-10-12 (owner: chose "Scheduled vs completed" over Visits scheduled, Overdue over time and a manager picker; then "keep, write the plan").
**Detailed:** 2026-10-12.
**Branch:** `main` (local first; publish only on "commit and push").
**Depends on:** Dashboard Style phase 2 (executed 2026-10-12, **not yet committed**). This plan edits phase 2's `manager-activity` chart; commit phase 2 first or publish both together.

## Context

The owner thought the manager's "Visits completed" chart showed the manager's own visits. It counts every engineer's Completed visits in the manager's scope, but on its own it says little to a manager, and it looks almost empty: only 5 visits in the last 3 months are marked `Completed` in the database. The owner wants a chart that answers "is the team keeping up with its workload?": visits scheduled per day/week against visits completed, as two lines on the same card.

## Decisions taken

1. **Two lines, one card:** Scheduled (muted second line, no fill) and Completed (the accent line and fill, as now). The 3 months / 30 days / 7 days switch is unchanged; 3 months stays weekly totals for both lines.
2. **Scheduled** = every service visit (`client_id` set, not Training or leave) counted on its visit date (`start_time`), **any status**, in the manager's analytics scope (`analytics_scope_query`). The window ends today; future bookings are not counted.
3. **Managers only:** `metric=company_scheduled` returns 403 for non-manager accounts, like `company_completed`.
4. **Copy:** title "Visits — scheduled vs completed"; a small key under the title; readout "Week of Aug 4 · 6 scheduled · 2 completed" (daily: "Tue, Oct 6 · …"); summary "5 of 38 scheduled visits completed in the last 3 months".
5. **Only the manager/hybrid chart changes.** The engineer chart (`engineer-activity`, `my_completed`) stays a single line.
6. **No manager data picker and no Overdue line** for now (see Deliberately excluded).

## Investigation

- **Endpoint:** `get_dashboard_series` (`app.py:34964`) already takes `metric`, clamps `days` to `DASHBOARD_SERIES_DAYS` (`app.py:34959`), zero-fills Manila days, and builds one Completed/Training/leave query shared by both metrics. The metric whitelist is at `app.py:34974`, the manager gate at `:34976`, the `company_completed` scope branch at `:34998`. The scheduled count needs the same query **without** the `status == 'Completed'` filter.
- **Chart:** `renderDashboardAreaChart(container, points, options)` (`app-dashboard.js:2257`) draws one series. Its scale (`top`), summary (`:2263`) and readout (`:2325`) all use `values` from that series, so a second series needs: the scale taken over both series, a second path, and readout/summary text built from both.
- **Loader:** `loadManagerActivity()` (`app-dashboard.js:2203`) fetches `company_completed` only. `setDashboardChartRange()` (`:2218`) slices and, for 90 days, groups by week (`groupDashboardPointsByWeek`, `:2238`); the scheduled series must be sliced and grouped the same way.
- **Markup:** the `manager-activity` section (`dashboard.html:350`), title at `:354`. Section id and the `manager-activity-*` element ids stay.
- **CSS:** `.dash-chart-line` / `.dash-chart-fill` (`app-dashboard.css:2349-2351`), with dark-theme pairs at the end of the Dashboard Style block.
- **Data note:** the Completed line stays low as long as visits are not marked Completed. That is real data, and the gap to Scheduled makes it visible; it is not something this plan fixes.

## Execution steps

1. **Endpoint** (`app.py`, `get_dashboard_series`): add `company_scheduled` to the metric whitelist and to the manager gate. Build the base filters once (client set, not Training/leave, inside the window); `completed` adds `status == 'Completed'`; `company_scheduled` uses the base query through `analytics_scope_query` with no status filter. Update the docstring. Done = 7/30/90 points, zero-filled; a manager gets counts that include open and completed visits; an engineer gets 403.
2. **Two-series chart** (`app-dashboard.js`, `renderDashboardAreaChart`): accept an optional `options.compare = {points, unit, label}`. When it is present: take `top` over both series; draw the compare line first (`.dash-chart-line.is-compare`, no fill, no draw-in animation), then the Completed fill and line as now; add a second dot on the cursor; build the readout as "<when> · N scheduled · N completed" and the summary as "N of M scheduled visits completed in the <range>". The empty state shows only when **both** series are zero. Without `compare`, the output is identical to today. Done = the engineer chart unchanged; the manager chart shows both lines.
3. **Loader** (`app-dashboard.js`): `loadManagerActivity()` fetches `company_completed` and `company_scheduled` in parallel (`Promise.all`) and stores the scheduled points in `dashboardChartState.comparePoints`. `setDashboardChartRange()` slices and week-groups `comparePoints` like `points`, and passes `compare` only when the prefix is `manager-activity`. The resize handler needs no change. Done = switching ranges updates both lines and the readout.
4. **Markup** (`dashboard.html`, `manager-activity`): title "Visits — scheduled vs completed"; under the subtitle a key (`.dash-chart-key`: two swatch-plus-label items, "Scheduled" and "Completed"; the swatches are `aria-hidden`, the labels are text). `data-dashboard-title` becomes "Scheduled vs Completed". Section id and element ids unchanged; no layout version bump (nothing moves).
5. **CSS** (`app-dashboard.css`, Dashboard Style block): `.dash-chart-line.is-compare` (1.5px, `--app-muted` with about 0.7 opacity, dashed 4 3 so it reads without colour), the compare dot, and `.dash-chart-key` with swatches matching both lines. Dark pairs for graphite and AMOLED. Done = both lines distinguishable in all three themes and in greyscale.
6. **DESIGN.md:** the "Area Chart" entry gains the comparison line rule (muted dashed line, no fill, key under the title, readout names both values).
7. **Self-review:** every function the manager view calls is still defined (`loadManagerActivity`, `setDashboardChartRange`, `renderDashboardAreaChart`, `groupDashboardPointsByWeek`, `openManagerKpi`, `renderOverdueByAge`, `loadManagerOverview`); the engineer chart is untouched; no id removed.

## Deliberately excluded

- **Overdue over time:** daily counts only exist since 2026-10-11 (`DashboardDailyCount`), so the line would be nearly empty for weeks. It can be added once there is history.
- **A manager picker** (Scheduled / Completed / Overdue): the owner chose the fixed comparison; a picker can come later.
- **Future bookings** on the Scheduled line: the chart ends today, like the Completed line.
- **Engineer and scheduler charts:** not part of the request.
- **Fixing how visits get marked Completed:** a process question, not a chart change.

## Verification

- **Tests** (`tests/test_dashboard_style.py`):
  - Endpoint: `company_scheduled` returns 403 for an engineer and a staff account; for the regional admin it returns 7 zero-filled points whose today value counts the seeded open visit as well as the completed ones (lower bounds, shared test DB); Training is excluded.
  - Source: `company_scheduled` is fetched by `loadManagerActivity`; `renderDashboardAreaChart` handles `options.compare`; the `manager-activity` card has the key and the new title; the engineer chart's call passes no `compare`; kept-functions guard.
  - **Positive control:** run the new tests in-process against `git show HEAD:<file>` (not `git stash`); all fail except the kept-functions guard. On `HEAD`, `company_scheduled` is a 400.
- **Focused run:** all `tests/test_dashboard_*.py`, `test_changelog_coverage`, `test_dark_mode_readability`. Full suite not needed (dashboard page and one read-only endpoint).
- **Browser** on a copy of `scheduler.db` (temporary passwords on the copy only): hybrid account (`robert`) at 1366 px in graphite and light; manager-only (`rodito`) at 375 px in AMOLED. Both lines are drawn, the scheduled totals match a SQL count on the copy, the readout names both values on hover, tap and arrow keys, the range switch updates both lines, the empty state shows only when both are zero, the engineer chart (`jonamar`) is still a single line, no horizontal scroll, contrast at least 4.5:1, console clean. Clean up the copy, passwords, appearance overrides and launch entry afterwards. One screenshot per theme as final proof.

## After implementation

1. Assets `app-dashboard.css?v=14`, `app-dashboard.js?v=13`; `CACHE_VERSION` `…-v293-manager-workload-chart`, keeping v292 as a history comment.
2. `static/changelog/releases.json`: one release for admins ("Scheduled vs completed").
3. `DESIGN.md` (step 6), `changes.md` bullets, and this plan's Status with the commit and any differences.
4. Commit only `app.py`, `templates/dashboard.html`, `static/css/app-dashboard.css`, `static/js/app-dashboard.js`, `tests/test_dashboard_style.py`, `static/changelog/releases.json`, `DESIGN.md`, `plans.md`, `changes.md`. Never `scheduler.db`, `output/`, `tmp/`, handoffs or other dirty files. Publish only on "commit and push".

## Risks

- **The engineer chart changes by accident:** `compare` is optional and only the manager loader passes it; a source test pins the engineer call.
- **Scheduled dwarfs Completed** and the Completed line flattens: expected with today's data, and the readout gives exact numbers. The y-scale is shared on purpose so the two are comparable.
- **Scope mismatch between the two lines:** both use `analytics_scope_query` and the same base filters.
- **Blast radius:** one card plus one read-only metric. Rolling back = revert the commit.

# Dashboard Style — shadcn Cards, Spacing, Chart and Header (all dashboards)

**Status:** Phase 3 executed 2026-10-12 (owner: "go phase 3"), **not yet committed**; publish on "commit and push". Tests: 6 source tests added (`DashboardStyleSchedulerSourceTests`); 5 fail on `HEAD`, the kept-functions guard passes on both. Focused run: 198 tests OK. Browser check on a DB copy passed as the scheduler (light and graphite at 1366 px, AMOLED at 375 px) and a staff account (375 px). Next: one Impeccable critique in a new session.
**Phase 3 amendments (found while building):**
- **Header (step 17)** was already done in phase 1; this phase only removed the board's duplicate Open Calendar button and made its title row a card heading with Refresh.
- **Tones:** the scheduler counts were coloured even at zero (fixed classes). They now use `data-metric-tone` and `setMetricValue()` (one JS change in `renderSchedulerMetrics()`), as in the engineer cards.
- **Next 7 days** is not a filter, so it is a plain `span.dash-stat`. Grid: 2 / 3 / 6 columns at phone / 768 / 1200 px.
- **Refresh stays `btn-outline-primary`:** `btn-outline-secondary` measured 4.48:1 on AMOLED. (The existing Today / 7 days toggle uses the same grey, also about 4.4:1 on AMOLED — not changed here.)
- **Assets** `app-dashboard.css?v=15`, `app-dashboard.js?v=14`; `CACHE_VERSION` `…-v294-dashboard-style-scheduler` (`app.py`, constant only).
Phase 2 executed — published to `main` on 2026-10-12 on the owner's "commit and push" (commit `ea11c35`, together with the Manager Chart plan; owner: "go phase 2"). Phase 1 published to `main` on 2026-10-11 (commit `350b64b`; owner: "go phase 1"). Phase 2 tests: 6 source tests and 2 endpoint tests added to `tests/test_dashboard_style.py`; 5 of the 6 source tests fail on `HEAD` (the manager kept-functions guard passes on both), and on `HEAD` `company_completed` is a 400, so both endpoint tests fail. Focused run: 185 tests OK. Browser check on a DB copy passed as `robert` (hybrid; graphite and light at 1366 px) and `rodito` (manager only; AMOLED at 375 px): numbers match phase C's endpoint figures, filters, age bars, PM card, Hide/Show, chart switch and keys all work, no horizontal scroll, tap targets ≥44 px on phones, contrast ≥4.76:1 light, 6.47:1 graphite, 8.11:1 AMOLED, console clean.
**Phase 1 details:** Brief: `.impeccable/briefs/dashboard-style.md`. New `tests/test_dashboard_style.py` (14 tests; 6 of 7 source tests fail on `HEAD`, the kept-functions guard passes on both; the 7 endpoint tests need `/get_dashboard_series`, absent on `HEAD`). Focused run: 177 tests OK. Browser check passed on a DB copy as `jonamar` (49 sample completed visits added to the copy): graphite and light at 1366 px, AMOLED at 375 px, no horizontal scroll, no tap target under 44px, muted text 9:1 on AMOLED, tabs, panel, Customize and the chart switch/readout/keys all working, console clean.
**Phase 2 amendments (found while building):**
- **`company_completed` uses the manager's analytics scope** (`analytics_scope_query`, like `/get_manager_overview`), not every visit unconditionally, so the chart and the tiles count the same population.
- **Overdue by age moved** out of `manager-executive` into the new `manager-activity` section, so it can sit one-third wide beside the chart (ids unchanged). Hiding "Needs Your Decision" no longer hides it.
- **Layout reset:** `manager-executive` went to layout version `4` (it is the first versioned section for managers and hybrids, which `resetDashboardLayoutIfOutdated()` reads), so saved manager layouts reset once and the chart lands in place. `manager-activity` carries version `1` as planned.
- **Hybrids:** `engineer-activity` is not rendered for them (decision 4). The Done this week badge still needs the engineer's own series, so `loadEngineerActivity()` fetches it for the badge alone (`engineerSeriesPoints`); the chart state now has a `prefix` naming whose chart is on the page.
- **Card copy:** badge "↑ 4" / "Same" (`aria-hidden`) plus the sentence "Up 4 from last week"; without a trend the sentence is the card's description (`data-default`). The hybrid Waiting card's "company-wide" moved from the name (which wrapped to three lines at 1366 px) to its helper line ("Company-wide · show them below").
- **Step 14** was done as card surface only: Direction and What Needs Attention got a hairline `.dash-panel` with a `.dash-card-title` header (icons dropped), the item count became a `.dash-stat-badge`, and Show all became a pill. Directory Totals only got the card padding.
- **Assets** `app-dashboard.css?v=13`, `app-dashboard.js?v=12`; `CACHE_VERSION` `…-v292-dashboard-style-manager`. Tests updated (assertions only): `test_dashboard_trends.py` (trend lines instead of sparklines; the age card sits in `manager-activity`), `test_dashboard_manager_kpis.py` (layout version 4), `test_dashboard_hybrid.py` (company-wide on the helper line).
**Phase 1 amendments (found while building):**
- The header subtitle and primary button were done for **every role** in phase 1, because the header is shared: Your work / Company overview / Dispatch / What's waiting on you, and Create TSR / Open approvals or Open analytics / Open calendar. This was planned for steps 11, 17 and 20, which now only cover the rest of those phases.
- `current-date` is **kept** (moved into the subtitle; `updateClock` now writes "Sunday, October 11"). Only `system-clock` was removed.
- **Layout reset:** `resetDashboardLayoutIfOutdated()` reads the *first* versioned section, so the version went onto `engineer-summary` (`3`) rather than onto the new chart section. Hybrid accounts (whose first versioned section is `manager-executive`) don't reset; for them, a saved layout puts the chart at the bottom until they press Reset.
- **The 3-month range is drawn as weekly totals** (13 points, "Week of Aug 24 · 5 visits"). Daily counts of 0–2 over 90 days read as spikes in the browser check. 30 and 7 days stay daily.
- **The engineer cards differ slightly from step 4:** the TSRs pending helper is "Visits from the last 180 days" (a Create TSR link there would be a sub-44px target and repeats the header button). Waiting reads "waiting parts" (hybrid: "waiting, yours").
- **Shortcuts (step 8)** were restyled in CSS only, because the shortcut tests pin the grid markup. Step 9's spacing pass was limited to the new cards. The Hide buttons were not restyled.
- **Assets** ended at `app-dashboard.css?v=12` and `app-dashboard.js?v=11` (bumped again mid-check, because the service worker served the first bump's files).
- **Tests updated** (assertions only, same properties): `test_dashboard_engineer.py` (stat cards instead of the strip), `test_dashboard_trends.py` (week card instead of bars), `test_dashboard_critique_fixes.py` (visible h1, header tools in `.dash-page-header`), `test_dashboard_hybrid.py` ("waiting parts").
**Approved:** 2026-10-11 (owner, after two inline mockups: "i like shadecn's dashboard. the cards, the spacing, the chart, the big header on top" → "keep, write the plan for all dashboards").
**Detailed:** 2026-10-11.
**Branch:** `main` (local first; each phase publishes only on its own "commit and push").
**Phases:** 1 shared parts + engineer · 2 manager · 3 scheduler and staff. Each phase needs its own go-ahead ("go phase 1" etc.), like the Remodel plan.

## Context

The owner wants the dashboard to *feel* like a dashboard. The reference is the shadcn/ui example (https://ui.shadcn.com/examples/dashboard): a big page title, a row of stat cards (label, small corner badge, big number, one sentence, one muted helper line), generous even spacing, one area chart with a range switch, and a data table in a card. Today's page has a small "Welcome back" heading with a dark clock badge, thin metric strips with dividers, and stacked panels with their own headers and Hide buttons. The Remodel (A–C) and Trends work fixed *what* each view shows; this plan changes *how it looks* across every view, without changing what any button does.

Approved mockup (engineer view, sample data): header "Dashboard" + "Your work, <date>" + one primary button; four stat cards (Visits today · Overdue · TSRs pending · Done this week); "Visits completed" area chart with 3 months / 30 days / 7 days; the work orders as a table card with filter pills.

## Decisions taken

1. **shadcn look, our identity.** Layout, spacing, card anatomy and the chart follow shadcn. Colours, fonts, radii and the three themes (light, graphite, AMOLED) come from `DESIGN.md`, so it will not be black-and-white like shadcn. The Impeccable skill (`shape` then build) translates the mockup into our tokens in phase 1.
2. **All dashboards, phased:** engineer (phase 1), manager and hybrid (phase 2), scheduler and staff landing (phase 3).
3. **Presentation only.** Every element id, `onclick` handler, endpoint and permission keeps working (AGENTS.md "Protect Existing Functions"). Ids move into the new cards rather than being renamed.
4. **One chart per view.** Engineer: own "Visits completed". Manager: company "Visits completed", with Overdue by age kept as a second, smaller card. A hybrid account gets the company chart only. **Scheduler: no area chart by default** — the engineer lanes are its picture, and a chart would repeat the 7-day board. (Owner can change this at go-ahead for phase 3.)
5. **Chart data is real history.** A completed visit is a Shift with `status == 'Completed'`, counted on its visit date (`start_time`). There is no `completed_at` on `Shift` (`app.py:3607`), so this matches how `/get_my_done_tasks` already defines "done". No snapshot table is needed, unlike the manager trends.
6. **No chart library.** The chart is a hand-written SVG in `app-dashboard.js`, like the existing sparklines and age bars. Chart.js is loaded only by the analytics page (`static/js/app-analytics.js`) and is not added to the dashboard.
7. **Clock badge goes.** The header's dark date/clock badge (`dashboard.html:61-66`) is removed. The date moves into the subtitle. `setTextIfPresent` (`app-dashboard.js:69-70`) already skips missing ids.
8. **Sparklines leave the manager tiles.** The big chart is the visual; a tile keeps its trend as the corner badge plus a sentence ("Up 4 from last week"). `renderManagerKpiTrend` already returns when the spark element is missing (`app-dashboard.js:828`).

## Investigation

- **Header** (`dashboard.html:48-74`): visually-hidden `<h1>Dashboard</h1>`, a visible `h4` "Welcome back, <name>!", the subtitle "Operational Overview of MEDICAL SERVICE Technical Visits", and a desktop-only tools group (clock badge, Customize `toggleDashboardCustomizeMode()`, Reset `resetDashboardLayout()`).
- **Engineer summary** (`dashboard.html:475-511`): a `.dashboard-metric-strip` with `count-my-today`, `count-my-overdue`, `count-my-pending-tsr`, `count-my-waiting`, `count-my-continuation`, the week strip (`engineer-week`, `engineer-week-bars`, `engineer-week-label`) and an "Open timeline →" link. Filled by `updateEngineerSummaryCards()`, `loadMyPendingTsrCount()` and `renderEngineerWeek()`.
- **Work orders** (`dashboard.html:515`): the `engineer-work-orders` section (tabs, list, detail panel) from phase B. It keeps its behaviour; only the card surface and tab look change.
- **Manager tiles** (`dashboard.html:251-340`): `.manager-kpi` buttons/links with `manager-*-count` ids, `manager-trend-*` labels and `manager-spark-*` SVGs; `openManagerKpi()` filters; PM tile `manager-kpi-pm`. Direction (`:344`), What Needs Attention (`:375`), Directory Totals (`:425`).
- **Scheduler board** (`dashboard.html:93-230`): header, `scheduler-risk` line, `.scheduler-metric-strip` of filter buttons (`data-scheduler-filter`, `scheduler-*-count`, `setSchedulerQueueFilter()`), then queue / lanes / selected schedule.
- **Staff landing** (`dashboard.html:595-610`): "Waiting on you" list only.
- **Saved layouts** (`app-dashboard.js:262-280`): sections a saved layout does not mention are appended at the **end**, so a new chart section would land at the bottom for anyone with a saved order. Phases A–C solved the same thing with `data-dashboard-layout-version` and `resetDashboardLayoutIfOutdated()`; this plan does the same.
- **Section ids** are whitelisted in `DASHBOARD_SECTION_IDS` (`app.py:31867`); a new section id must be added there or the layout save rejects it.
- **Tests pinning today's markup:** `tests/test_dashboard_engineer.py` and `tests/test_dashboard_trends.py` reference the metric strip, week bars, clock or spark markup. They are updated, not deleted, in the phase that changes that markup.
- **Assets today:** `app-dashboard.css?v=10`, `app-dashboard.js?v=9`, `CACHE_VERSION` `…-v290-dashboard-trends` (`app.py:27377`).

## Execution steps

### Phase 1 — shared parts + engineer dashboard

1. **Impeccable `shape`** for the dashboard style. Input: this plan, the approved mockup, `DESIGN.md`. Output: the brief for the header, stat card, area chart and table card in our tokens and all three themes, saved under `.impeccable/`. Done = brief written; no code yet.
2. **Page header** (`dashboard.html:48-74`, `app-dashboard.css`): the visible `<h1>Dashboard</h1>` (about 1.75rem; replaces the hidden h1 and the "Welcome back" h2); a role subtitle with the Manila date ("Your work, Sunday 11 October" for engineers; phases 2–3 add theirs); one primary button per role on the right (engineer: Create TSR → `/offline-tsr`, the sidebar's link); Customize and Reset stay as quiet secondary buttons, desktop only. The clock badge is removed (decision 7). Done = one header on every role view, no horizontal scroll at 375 px.
3. **Stat card component** (`app-dashboard.css`, new `.dash-stat`): `surface`, hairline border, 12px radius, 1.25rem padding; muted label top-left, small badge top-right, about 2rem tabular number, a 0.875rem sentence, a 0.75rem muted helper line. Grid: 4 across at ≥1200 px, 2 across below, both phone and tablet. Tone rules carried over from KPI Tiles: alert/warn colour only above zero, never the accent. Done = component styled in all three themes.
4. **Engineer cards** (`dashboard.html:475-511`): the metric strip becomes four `.dash-stat` cards — Visits today (`count-my-today`; helper: next visit time), Overdue (`count-my-overdue`; helper holds `count-my-continuation` and `count-my-waiting` as "N for continuation · N waiting parts"), TSRs pending (`count-my-pending-tsr`), Done this week (holds `engineer-week` and `engineer-week-label`; badge: change vs last week). The section id `engineer-summary` stays. `renderEngineerWeek()` fills the card number and badge instead of bars; `engineer-week-bars` is removed together with its CSS. Done = every id the loaders write to still exists (grep each one), and values match the old strip on the same data.
5. **Series endpoint** (`app.py`, next to `/get_my_done_tasks` at `:34915`): `GET /get_dashboard_series?metric=my_completed&days=90` → `{metric, days, points:[{date:'YYYY-MM-DD', value}]}`, Manila days, zero-filled, oldest first. `days` is limited to 7, 30 or 90 (anything else → 90). `my_completed` uses the same filters and ownership rule as `get_my_done_tasks` (client set, not Training/leave, linked engineer list decides); without an engineer profile it returns empty points. Login required. Done = endpoint returns 90 points for the owner on a DB copy, totals match a SQL count.
6. **Area chart** (`app-dashboard.js`, new `renderDashboardAreaChart(container, points, options)`; `app-dashboard.css` `.dash-chart`): a new section `engineer-activity` ("Visits completed", `data-dashboard-layout-version="1"`) placed under the cards; added to `DASHBOARD_SECTION_IDS`. Smooth line plus a light fill in the accent, 3 hairline gridlines, date labels on the x-axis, a segmented 3 months / 30 days / 7 days switch (44px targets), and a readout line (`role="status"`) that shows "Tue 6 Oct · 3 visits" on hover, tap or arrow keys. The SVG carries an `aria-label` with the total for the range. One fetch of 90 days; 30 and 7 are slices. Draws once on load (fill fades in, line draws); off under reduced motion. Empty range: one line "No completed visits in this range". Done = switch, readout and empty state work in all themes at 1366 and 375 px.
7. **Work orders as a table card** (`dashboard.html:515`, `app-dashboard.css`): the section sits in one card; tabs look like shadcn's pills (still `.work-orders-tab`, still 44px, counts kept). The table and phone cards, row click and the detail panel are unchanged. Done = phase B's tests still pass.
8. **Shortcuts** (`dashboard.html:628`): the grid becomes one quiet row of icon links. Same links and the same admin gate.
9. **Spacing pass:** one vertical rhythm between sections (1.5rem, 1rem on phones), with a section's own heading inside its card. Hide buttons stay (`toggleDashboardSection`) as quiet icon buttons with an `aria-label`.
10. **Self-review:** every function the engineer view calls is still defined (`updateEngineerSummaryCards`, `loadMyPendingTsrCount`, `renderEngineerWeek`, `renderMyTasks`, `setWorkOrdersTab`, `openWorkOrderPanel`, `toggleDashboardCustomizeMode`, `resetDashboardLayout`, `toggleDashboardSection`); no id removed except `engineer-week-bars`, `current-date` and `system-clock` (decision 7, and `setTextIfPresent` is null-safe); `DESIGN.md` gains "Page Header", "Stat Cards" and "Area Chart", and "KPI Tiles" points to them.

### Phase 2 — manager and hybrid

11. **Header:** subtitle "Company overview, <date>"; primary button Open approvals (`/approvals`) for approvers, otherwise Open analytics (`/analytics_page`).
12. **Tiles → stat cards** (`dashboard.html:251-340`): each `.manager-kpi` keeps its element type (link or button), id, `data-manager-kpi`, `aria-pressed` and `onclick`, and takes the `.dash-stat` anatomy: the trend goes into the corner badge and a sentence; the `manager-spark-*` SVGs are removed (decision 8); the PM meter stays as the PM card's helper. The active filter keeps its 2px accent underline. `renderManagerKpiTrend()` writes the badge and sentence. Done = every filter still works and every number matches both endpoints.
13. **Company chart:** `metric=company_completed` on the same endpoint (step 5). Allowed only when `is_manager_dashboard_user()`, otherwise 403. Counts every completed service visit with the same filters as `my_completed` but no ownership filter. New section `manager-activity` (layout version 1, added to `DASHBOARD_SECTION_IDS`) renders it with the phase 1 chart. On ≥1200 px it sits two-thirds wide beside the Overdue by age card (one-third); stacked below that.
14. **What Needs Attention as a table card**, its filter line as pills. Direction and Directory Totals take the card surface and spacing; no content change.
15. **Hybrid:** the engineer cards and work orders sit under the manager part, keeping their "yours" labels and the scope divider; no personal chart (decision 4).
16. **Self-review** as step 10 for the manager functions (`openManagerKpi`, `renderManagerTrends`, `renderOverdueByAge`, `openOverdueAge`, `renderManagerWatchlist`, `loadManagerOverview`, `loadManagerApprovals`, `renderManagerUpdated`).

### Phase 3 — scheduler and staff landing

17. **Header:** subtitle "Dispatch, <date>"; primary button Open calendar (`/timeline`). The board's own title row becomes the card heading with Refresh.
18. **Filter strip → stat cards** (`dashboard.html:117-150`): the buttons keep `data-scheduler-filter`, ids, `aria-pressed` and `setSchedulerQueueFilter()`, and take the `.dash-stat` look (no trend badge: the scheduler has no recorded history). The `scheduler-risk` line sits under the header as one status sentence.
19. **Board regions** (queue, lanes, selected schedule) take the card surface and spacing. Lane logic, drag-and-drop, assign and reschedule are untouched.
20. **Staff landing:** the phase 1 header (subtitle "What's waiting on you, <date>") and the "Waiting on you" list in a card.
21. **Self-review** as step 10 for the scheduler functions (`setSchedulerBoardView`, `renderSchedulerAvailabilityStrip`, `setSchedulerQueueFilter`, `dropOnSchedulerLane`, `confirmSchedulerLaneAssign`, `loadSchedulerDispatchIntelligence`, `loadSchedulerCoordinationTools`).

## Deliberately excluded

- **New metrics or data** beyond completed visits per day: this plan is about looks.
- **Scheduler chart:** decision 4; can be added at phase 3's go-ahead.
- **A chart library:** decision 6.
- **The sidebar and app shell** (`layout.html`, `app-shell.css`): not part of the request, and they are shared code.
- **Analytics page:** it already has its own charts.
- **Data-table features from shadcn** (column picker, row selection, pagination controls): the lists already cap at 20 rows and have tabs or filters.

## Verification

- **New test module** `tests/test_dashboard_style.py`, growing per phase:
  - Phase 1: a visible `<h1>Dashboard</h1>` and no clock badge; four `.dash-stat` cards in the engineer view, with every kept id present; the `engineer-activity` section is registered in `DASHBOARD_SECTION_IDS`; `/get_dashboard_series?metric=my_completed` returns zero-filled Manila days, counts only the signed-in engineer's completed visits (another engineer's visit and a Training row excluded), clamps `days`, and returns empty points without a profile; a kept-functions guard; assets bumped at least to v11/v10.
  - Phase 2: `company_completed` returns 403 for a plain engineer and 200 for a manager; tiles keep `data-manager-kpi` and `onclick`; no `manager-spark-` left; the `manager-activity` section is registered.
  - Phase 3: scheduler filter cards keep `data-scheduler-filter` and `onclick`; the staff landing has the header.
  - **Positive control:** each phase's new tests are shown failing on `HEAD`, run in-process against `git show HEAD:<file>` (not `git stash`, per the browser-check notes), except the kept-functions guard, which passes on both.
- **Update, don't delete,** the assertions in `tests/test_dashboard_engineer.py` and `tests/test_dashboard_trends.py` that pin the old strip, week bars or sparklines.
- **Focused run per phase:** all `tests/test_dashboard_*.py`, changelog coverage and dark-mode readability. The full suite is not needed (the dashboard page only; no shell, auth or schema change).
- **Browser per phase** on a copy of `scheduler.db` (temporary password on the copy only): the phase's role view at 1366 px in light and graphite and at 375 px in AMOLED; cards match the old numbers; chart range switch, readout, keyboard and empty state; every existing button in that view clicked once (Customize, Reset, Hide, filters, tabs, panel, assign); no horizontal scroll; tap targets at least 44px; console clean; dark-mode contrast at least 4.5:1. Then clean up the copy and the launch entry. One screenshot per theme as final proof.
- **One Impeccable critique** after phase 3, in a new session.

## After implementation (each phase)

1. Assets: `app-dashboard.css?v=` and `app-dashboard.js?v=` +1 per phase; `CACHE_VERSION` +1 (phase 1 `…-v291-dashboard-style`), keeping the previous one as a history comment.
2. `static/changelog/releases.json`: one release per phase (engineers / admins / schedulers).
3. `DESIGN.md` entries (step 10), `changes.md` bullets, and this plan's Status with the commit and any differences.
4. Commit only `templates/dashboard.html`, `static/css/app-dashboard.css`, `static/js/app-dashboard.js`, `app.py` (phases 1–2), the tests, `releases.json`, `DESIGN.md`, `plans.md`, `changes.md`. Never `scheduler.db`, `output/`, `tmp/`, handoffs or other dirty files. Publish only on that phase's "commit and push".

## Risks

- **A loader writes to an id that moved and silently stops updating:** ids are moved, not renamed; the self-review greps each one, and the kept-functions test guards it.
- **Saved layouts put the new chart at the bottom:** layout version on the new sections resets saved layouts once (as in phases A–C).
- **The chart misleads:** it counts visit dates, not completion times (decision 5). The empty state never draws a flat zero line as if it were data.
- **Dark themes:** `app-dark-pages.css` forces some `-kpi-value` classes to plain text with `!important` (phase C finding), so new class names avoid that pattern; contrast is checked in the browser.
- **Blast radius:** one page, plus one read-only endpoint. Rolling back = revert the phase's commit.

# Developer Account — Engineer-Only Dashboard

**Status:** Executed — published to `main` on 2026-10-11 on the owner's "commit and push" (commit `d000fc4`; owner: "execute the last written plan"). New `tests/test_dashboard_developer_view.py` (4 tests; 3 fail on `HEAD`, and the permissions guard passes on both). Changed from the plan: the "other admin" guard uses `robert` (a superadmin with a profile keeps the hybrid view) instead of a regional admin, whose predicate is tied to one named account. `test_dashboard_hybrid.py`'s pinned `hybrid_view` source line was updated. Full suite: 1,766 tests, only the 14 known failures. Browser check on a DB copy as `jonamar` passed: engineer summary, work orders (with the week strip), Shortcuts including the admin links, open technical tasks; no manager section, no scope divider, no `/get_manager_*` requests, no failed requests, no horizontal scroll at 1366 px or 375 px.
**Approved:** 2026-10-11 (owner: "i am not the admin. i am the developer but i'm also just an engineer"; chose "Engineer only").
**Detailed:** 2026-10-11.
**Branch:** `main` (local first; publish only on a separate "commit and push").

## Context

`jonamar` is `DEVELOPER_SUPERADMIN_USERNAME` (`app.py:8137`) and has an Engineer profile. Superadmin makes `is_manager_dashboard_user()` true (`app.py:11503`: admin-authorized and not a scheduler), so `get_dashboard_capabilities()` (`app.py:11749`) gives the account `manager_view` and `hybrid_view`. The owner's dashboard therefore opens with the manager tiles, approvals, chart and watchlist, and only then shows their own work. The owner is the developer and a field engineer, not a manager. Intended outcome: the owner's dashboard is the plain engineer dashboard, with every developer/superadmin permission unchanged.

## Decisions taken

1. **Engineer only** for the developer account (owner, 2026-10-11). The opposite of `MANAGER_PRIMARY_USERNAMES` (`app.py:8146`, manager-only for `rodito`).
2. **Presentation only.** No permission changes: `/get_manager_overview`, `/get_manager_approvals`, Settings, Approvals and all superadmin routes keep their own checks and stay reachable for the developer (for testing).
3. **Shortcuts keep their admin links** (`dashboard_effective_admin_view`, `dashboard.html:681`). They're developer tools, not manager data.
4. Corrects the Dashboard Trends plan's decision 5, which called the owner's view "hybrid". The owner gets the trends plan's engineer half (the done-this-week strip) and no manager tiles.

## Investigation

- `get_dashboard_capabilities()` (`app.py:11749-11779`): `has_engineer_profile` = profile and not manager-primary; `hybrid_view` = engineer sections and admin-authorized; `manager_view` = `is_manager_dashboard_user` and not scheduler-only.
- Template (`dashboard.html:21-26`): `dashboard_effective_manager_view` gates the whole manager branch; `dashboard_effective_hybrid_view` only changes labels ("Your own work orders", "waiting, yours", "company-wide"); the staff landing needs no manager view **and** no engineer profile, so the developer won't fall into it.
- JS (`app-dashboard.js:44-45`): `hybridView` / `managerView` from the template config; `loadManagerApprovals` / `loadManagerOverview` return early when `managerView` is false, so the developer's dashboard stops calling them.
- Display role (`get_display_role`, `app.py:11570`) stays "Superadmin"; it isn't a dashboard flag.

## Execution steps

1. **Constant** (`app.py`, next to `MANAGER_PRIMARY_USERNAMES`): `ENGINEER_PRIMARY_USERNAMES = {DEVELOPER_SUPERADMIN_USERNAME}`, with a comment saying it's dashboard presentation only. Add `is_engineer_primary_user(user=None)`, mirroring `is_manager_primary_user`.
2. **Capabilities** (`get_dashboard_capabilities`): `engineer_primary = is_engineer_primary_user(target) and bool(engineer_profile)` (without a profile the account keeps today's view, so it never lands on an empty page). `hybrid_view` and `manager_view` become false when `engineer_primary`. `admin_view` is unchanged (decision 3). Done = the developer's flags are engineer + admin shortcuts, with no manager or hybrid view.
3. **Self-review:** no other caller of `get_dashboard_capabilities` changes meaning (grep); `is_manager_dashboard_user` is untouched, so endpoint authorization is unchanged.

## Deliberately excluded

- **Permissions:** nothing the developer can open or do changes (decision 2).
- **A UI toggle** to switch views: not asked for. A browser check on another account covers the manager view.
- **Other superadmins** (`robert`): not part of this request.

## Verification

- New test in `tests/test_dashboard_hybrid.py` (or a new `tests/test_dashboard_developer_view.py` if that file's fixtures don't fit): for the developer account with an Engineer profile, `get_dashboard_capabilities()` returns `manager_view=False`, `hybrid_view=False`, `has_engineer_profile=True`, `admin_view=True`; the dashboard renders the work orders without `data-dashboard-section="manager-executive"`; `/get_manager_overview` still returns 200 for the developer. A positive control shows the capability test fails on `HEAD`. Plus a guard: `rodito`'s and a regional admin's flags are unchanged.
- Focused: the dashboard test modules (as in the Trends plan). Full suite once before publishing (auth/permissions helper area, per AGENTS.md).
- Browser on a copy of `scheduler.db` as `jonamar` (temporary password on the copy only): engineer dashboard with the done-this-week strip and Shortcuts; no manager section; no `/get_manager_*` requests in the network log; 1366 and 375 px; console clean. Clean up afterwards.

## After implementation

1. Assets: no CSS/JS change, so no `?v=` bump. `CACHE_VERSION` isn't needed (the server-rendered template changes per request).
2. `releases.json`: no entry (affects one account, the developer).
3. `changes.md` bullets; Status here with the commit; amend Dashboard Trends decision 5 to point here.
4. Commit only `app.py`, the test file, `plans.md`, `changes.md` (plus the Trends files if both publish together). Never `scheduler.db`, `output/`, `tmp/` or handoffs.

## Risks

- **Developer loses a quick view of the manager numbers:** intended. The analytics page and `/approvals` stay reachable.
- **Saved Customize layout** from the hybrid view names manager sections that no longer render. Unknown ids are skipped by the layout loader; the browser check confirms this.

# Dashboard Trends — "Alive, Not Overloaded"

**Status:** Executed — published to `main` on 2026-10-11 on the owner's "commit and push" (commit `95d7bde`; owner: "execute all"). Publish waits for a separate "commit and push". New `tests/test_dashboard_trends.py` (15 tests; 14 fail on `HEAD`, the kept-functions guard passes on both). Focused run: 153 dashboard tests OK. Full suite (`run_suite.py`, `PYTHONUTF8=1`): 1,762 tests, 15 failures = the 14 known + `test_dashboard_manager_kpis.test_assets_and_cache_bumped` (pinned exact asset versions; now "at least"), fixed and rerun green. Browser check on a DB copy passed (rodito manager+approver, then the owner's superadmin+engineer hybrid view; 1366 px graphite and light, 375 px AMOLED; no horizontal scroll; bars ≥44 px).
**Differences from the plan:**
- **Buckets** are 1–6 · 7–14 · 15–30 · 31+ days (plan said 1–7 · 8–14), so the second bar starts exactly at the watchlist threshold (`MANAGER_SEVERE_AGE_DAYS = 7`). Bars under 7 days carry a new `overdue` row type ("Overdue"). The threshold is shown in the chart's note line ("the watchlist starts at 7 days") instead of a dashed line.
- **Count-up fallback:** found in the browser check. A background or unfocused tab pauses `requestAnimationFrame`, so the tiles stuck at 0. `animateDashboardNumber` now sets the final value after 800 ms no matter what, and a newer count cancels an older one.
- **Snapshot write placement:** in `/get_manager_overview` it runs after every count is built, just before `jsonify`. The commit expires ORM objects, and nothing reads them after that point.
- **Zero-count bars stay enabled** (no disabled controls); pressing one shows the list's empty line.
- **Detector fixes:** font sizes moved onto the DESIGN.md ramp (0.72 / 1rem), bar radius 6px, and the PM meter animates `transform: scaleX` rather than `width`. Remaining detector items are design-system colour advisories that the existing dashboard CSS already uses.
- On the real data copy, 202 of 203 overdue visits are 31+ days late, so the chart is honestly one tall bar for now.
**Approved:** 2026-10-11 (owner: "keep, run impeccable shape and write the plan"; snapshot and chart choices answered the same day).
**Detailed:** 2026-10-11.
**Source:** Owner's question "does the dashboard feel lacking? why not charts?" Research picked Stripe Home (number + sparkline + period change), ServiceTitan custom dashboards (one bar chart with a target line, click to drill in) and Vercel/Linear (grey by default, colour only for meaning). An inline mockup with sample numbers was approved ("keep"). Impeccable `shape` brief below.
**Branch:** `main` (local first; publish only on a separate "commit and push").

## Context

The remodel (phases A–C) made each role's screen action-first, but every number is static. A manager sees "Overdue 12" without knowing whether that's better or worse than last week. The goal is to make the dashboard **feel alive but not overloaded**: each existing number gets a direction, one chart answers "how bad is it?", and motion is brief.

## Shape brief (Impeccable)

1. **Job and audience:** managers (desktop, morning check) and engineers (phone, between sites). Mode: Operate.
2. **Outcome:** in one glance, a manager sees which numbers are getting worse and where the overdue work sits by age. An engineer sees the week's finished visits.
3. **Direction:** stays inside DESIGN.md ("The Service Logbook"). Trends are ink-muted by default, and status red appears **only** on a worsening trend or an over-limit bar, never the accent. The one focal moment is the overdue-by-age chart.
4. **Scope:** manager KPI tiles (5), one chart under them, the engineer header strip. The scheduler board and staff view are untouched. **Anti-goals:** no new tiles, no second chart, no looping animation, no chart library, and no trend on a number that the data can't back.
5. **States:** first day (no history, so the tile shows "Trend from Oct 13"), 1–6 days (no delta yet, partial sparkline), ≥7 days (delta), 4+ weeks (full sparkline). Zero overdue means the chart shows one line, "Nothing overdue". A scoped viewer (branch-limited) gets no company trend.
6. **Interaction:** tiles keep their current clicks. Chart bars are buttons: tap to filter What Needs Attention to that age range, tap again to clear. On first load the numbers count up (≤700 ms) and tiles fade in staggered (≤400 ms). After each refresh, "Updated N min ago" pulses for 3 s, then sits still. `prefers-reduced-motion` turns off all motion.
7. **Constraints:** inline SVG only (no Chart.js on this page); light, graphite and AMOLED; 375 px with no horizontal scroll; 44 px targets; every chart gets `role="img"` and a text label.

## Decisions taken

1. **Daily snapshot** for the "right now" counts (owner, 2026-10-11). History can't be rebuilt honestly. `get_manager_overview`'s docstring (`app.py:35739-35743`) says reconstructed overdue/TSR counts are systematically undercounted.
2. **The one chart = Overdue by age** (owner): 1–7 · 8–14 · 15–30 · 31+ days late. It's accurate from day one.
3. Trends are **weekly points**: up to 4 past weeks plus today. The delta compares today with the snapshot taken 6–8 days ago. If there isn't one, no delta is shown (it is never guessed).
4. Colour meaning: for the overdue, TSR, waiting and approvals tiles, lower is better. PM done/due shows a progress meter instead of a sparkline (it is a ratio to a limit).
5. **(Corrected by "Developer Account — Engineer-Only Dashboard" above: the owner is the developer and an engineer, and their dashboard is engineer-only.)** **The owner's own view is a first-class target** (owner, 2026-10-11: "add me to your plan — superadmin, also an engineer, not manager or scheduler"). A superadmin with an engineer profile is a manager-dashboard user (`is_manager_dashboard_user`, `app.py:11503`: admin-authorized and not a scheduler), so the page renders the **hybrid view**: company-wide manager tiles and chart on top, "Your own work orders" below. Both halves of this plan must work there: tile trends and the age chart (company-wide), the done-this-week strip (own visits). The approvals tile stays hidden unless the account is a configured approver (`is_approval_center_user`), so an owner who isn't an approver writes no approvals snapshot. The browser check uses a superadmin + engineer test account as its main case.

## Investigation

- Tiles: `templates/dashboard.html:272-293` (`manager-kpis`; ids `manager-approvals-total`, `manager-overdue-count`, `manager-pending-tsr-count`, `manager-kpi-pm`, `manager-waiting-count`; `openManagerKpi(type)`). The tile number class is `.manager-kpi-num` because `app-dark-pages.css` forces `[class*="-kpi-value"]`. Avoid that substring in new class names.
- Counts: `/get_manager_overview` (`app.py:35732`) returns `counts.overdue_schedules / pending_tsr / waiting_items`, scoped by `analytics_scope_query` (`app.py:52855`). **Correction found while executing:** `analytics_visible_engineer_ids()` (`app.py:52834`) never returns `None`; it always returns a list, so "unscoped" means `analytics_requested_branch() == 'ALL'` (`app.py:52802`, the default when no `?branch=` is sent). Overdue = open with date < today; `MANAGER_SEVERE_AGE_DAYS = 7` (`app.py:35600`). The watchlist holds only ≥7-day overdue, so the 1–7 bar needs its own rows.
- Approvals: `/get_manager_approvals` (`app.py:35632`) counts **per approver** (`apply_assigned_approver_filter`), so its snapshot is keyed per user.
- PM: `inventory_pm_month_summary(today)` (`app.py:36088`) → `renderManagerPmSummary` (`app-dashboard.js:636`).
- Watchlist render: `renderManagerWatchlist(data, type)` (`app-dashboard.js:682`) already takes a type filter (phase C).
- Engineer header: `count-my-today` / `count-my-overdue` (`dashboard.html:454,461`). Done visits: `GET /get_my_done_tasks` (`app.py:34877`, last 7 days, own profile), currently loaded only when its tab opens.
- No cron. The daily backup uses a 15-minute thread (`_daily_backup_loop`, `app.py:31613`) that depends on backup storage. Snapshots will **not** ride on it; they're written lazily on the first qualifying request of the Manila day (see step 2).
- Tables: models are created by `db.create_all()`. A new model needs no column migration (`app.py:58197` notes create_all doesn't add columns, which only matters for existing tables).
- Assets: `app-dashboard.css?v=9` (`dashboard.html:4`), `app-dashboard.js?v=8` (`dashboard.html:799`), `CACHE_VERSION … v289-manager-kpis` (`app.py:27337`).

## Execution steps

1. **Read first:** the newest `changes.md` section; `reference/craft-floor.md` from the Impeccable skill (before any UI edit); the functions above in full.
2. **Model + writer** (`app.py`): `DashboardDailyCount(id, day DATE, scope VARCHAR(40), metric VARCHAR(40), value INT)`, unique on `(day, scope, metric)`. Add a helper `record_dashboard_daily_counts(scope, values: dict)` that inserts today's (Manila) rows if absent (ignores duplicates, so two concurrent requests are harmless) and never raises into the request (log and continue). Done = a second call on the same day changes nothing.
3. **Write points:** in `/get_manager_overview`, only when `analytics_requested_branch() == 'ALL'`, call the helper with scope `all` and `overdue`, `pending_tsr`, `waiting`. In `/get_manager_approvals`, when `is_approver`, call it with scope `user:<id>` and `approvals`. Done = rows appear after one dashboard load, and a scoped viewer writes nothing.
4. **Read trends** (`app.py`): add `dashboard_trend(scope, metric, today_value)` → `{points: [≤4 weekly values + today], delta: int|null, since: 'YYYY-MM-DD'|null}`. Weekly point = latest snapshot in each of the 4 previous 7-day windows. Delta = today − the snapshot from 6–8 days ago, else `null`. Add `trends` to both endpoints (overview: only when the branch is `ALL`; approvals: own scope). Done = endpoint tests with seeded snapshots give exact points/delta; no snapshots gives `points:[today]`, `delta:null`.
5. **Overdue by age** (`/get_manager_overview`, additive): `overdue_by_age: [{key:'1_7'|'8_14'|'15_30'|'31_plus', label, count, rows:[top 20 manager_watchlist_entry]}]` from the existing `overdue_shifts` (no new query). Done = counts sum to `counts.overdue_schedules`.
6. **Tile markup** (`dashboard.html`): inside each existing tile, below the label, add `<span class="manager-kpi-trend" id="manager-trend-{overdue|tsr|waiting|approvals}">` (delta text) and `<svg class="manager-kpi-spark" aria-hidden="true">`. For PM, add a meter `<span class="manager-kpi-meter">`. Ids and `onclick` stay unchanged.
7. **Chart markup:** a new block directly under `.manager-kpis` in the same section: heading "Overdue by age", 4 bar buttons (`data-overdue-age="1_7"…`, `aria-pressed`) drawn as SVG/inline elements, the count above each bar, and a dashed line at the severe threshold (7 days) labelled "Watchlist starts". No new dashboard section (no layout-version bump).
8. **JS** (`app-dashboard.js`): `renderManagerTrends(trends)` (sparkline polyline, delta text "▲4 vs last week" / "▼3" / "Same as last week" / "Trend from Oct 13"; red only when worse); `renderOverdueByAge(data)`; `openOverdueAge(key)` reuses the `renderManagerWatchlist` filter path with that bucket's rows and the filter line "Overdue 8–14 days"; `animateDashboardNumber(el, to)` (count-up from the current value, skipped under reduced motion); an "Updated N min ago" line with a 3 s pulse after each load. Call these from the existing load functions (`loadManagerOverview` / `renderManagerApprovals`); don't rename anything.
9. **Engineer strip:** under the engineer header, a 7-day bar strip (Mon–Sun, today in the accent, future days hairline) from `/get_my_done_tasks`, fetched once on load and reused by the Done this week tab (no second request). Also shown in hybrid view.
10. **CSS** (`app-dashboard.css`): tile trend/spark/meter, chart bars (≤24 px, 4 px top radius, neutral fill; red when the bucket is ≥ the severe threshold and non-zero), entrance motion with `@media (prefers-reduced-motion: reduce)` off, graphite and AMOLED pairs, 375 px (tiles 2-up, chart full width).
11. **Self-review:** every function and id from the Remodel plan's Investigation list still exists (grep); `git diff` touches only the manager tiles area, the engineer header and the new model/helpers.
12. **Impeccable:** `impeccable detect --json templates/dashboard.html` once; fix real findings.

## Deliberately excluded

- **Overdue-by-week chart:** it needs 8 weeks of snapshots. Revisit once history exists.
- **Backfilling history:** the reconstruction would be dishonest (decision 1).
- **Scheduler board and staff view:** the lanes already work like a chart.
- **Chart library:** four bars and four sparklines don't justify one, and inline SVG themes with CSS variables.
- **Looping animation:** "alive" comes from the entrance motion and the post-refresh pulse only.
- **Branch-scoped trends:** scoped viewers get today's numbers without a company trend, so they never see a mismatch.

## Verification

- New `tests/test_dashboard_trends.py`: snapshot write is idempotent and skipped for scoped viewers; approvals snapshot is per user; `dashboard_trend` points/delta with seeded rows and with none; `overdue_by_age` sums to the overdue count; markup ids present; kept functions present. Each one fails on `HEAD` first.
- Focused: the six dashboard modules + `test_dashboard_manager_kpis`, `test_dashboard_work_orders` + the new module.
- **Full suite once before publishing** (new database table = schema): `venv/Scripts/python.exe scripts/run_suite.py` in the main folder.
- Browser on a copy of `scheduler.db` (**superadmin + engineer hybrid account first** (the owner's view), then manager and plain engineer test accounts; seed a few snapshot rows on the copy only): 1366 and 375 px, light, graphite, AMOLED; tiles still match the endpoints; bars filter and clear; reduced motion is static; console clean; 44 px targets. Clean up the copy, accounts and launch entry.

## After implementation

1. `app-dashboard.css?v=10`, `app-dashboard.js?v=9`; `CACHE_VERSION … v290-dashboard-trends` (keep the old value as a comment).
2. `static/changelog/releases.json` entry, category Dashboard: "Numbers now show which way they're moving".
3. `changes.md` bullets; DESIGN.md gets the patterns "KPI trend" and "age bars".
4. Update this plan's Status with the commit and any differences.
5. Commit only: `app.py`, `templates/dashboard.html`, `static/css/app-dashboard.css`, `static/js/app-dashboard.js`, `releases.json`, the tests, `plans.md`, `changes.md`, `DESIGN.md`. Never `scheduler.db`, `output/`, `tmp/` or handoffs.

## Risks

- **Write during a GET:** isolated in a helper that swallows its own errors. A failed snapshot only means a missing point.
- **Empty trends for the first weeks:** expected and labelled ("Trend from …"), never faked.
- **Tile height grows:** checked at 375 px; the sparkline is 26 px.

# Dashboard Remodel — MaintainX Work Orders + ServiceTitan Dispatch

**Status:** Phase A executed — published to `main` on 2026-10-11 on the owner's "commit and push" (commit `44f32b9`). Phase B executed and on `origin/main` (commit `6b36d8b`). Phase C executed — published to `main` on 2026-10-11 on the owner's "commit and push" (commit `e30359c`). Next: one re-critique in a new session.
**Phase C differences from the plan:**
- **Backend (not planned):** `/get_manager_overview` gains `watchlist_by_type`, `watchlist_type_totals` (built before de-duplication) and `severe_age_days`. Filtering the sent top 20 client-side failed on real data: the top 20 was all severely overdue, and all 7 waiting jobs were also severely overdue, so de-duplication hid them.
- **Watchlist holds severe cases only** (7+ days), so a filter line names what is shown ("Overdue 7 days or more") beside the tile's full count.
- **`manager-approvals-total`** moved from the approvals list head into the tile; the head keeps the aging line and Open Approvals. `manager-open-count` and "Open analytics" moved into the risk line; the metric strip is gone.
- **Layout version "3"**, not "2": hybrid accounts stored "2" from phase B (the per-user key is shared across roles), so "2" would not reset them.
- **Tile number class** `.manager-kpi-num`: `app-dark-pages.css` forces `[class*="-kpi-value"]` to plain text in dark mode.
- **PM tile** hidden when the server sends no PM summary; zero tiles stay neutral.
**Phase B differences from the plan:**
- **Investigation correction:** `/get_open_tasks` had no `has_tsr` or times. Its rows are now built by `dashboard_task_row()` with `time_start` / `time_end` added; `has_tsr` is on Done this week rows only (open visits get their TSR after completion; the panel says so).
- **Task notes:** `Shift` has no notes column, so the panel shows the visit title as "Task".
- **Header line:** visits today · overdue · TSRs pending · waiting · for continuation. `count-my-active` / `count-my-upcoming` left the markup (JS still sets them if present); `count-my-today` and `count-my-overdue` are new.
- **Rows** keep their `/timeline?date=` href; a plain click opens the panel, a modifier click follows the link. First load opens the first non-empty tab.
- **Bug found in the browser check:** done visits showed "N days late"; `dashboardDaysLate` now returns 0 for Completed.
- **Tests updated:** `test_dashboard_engineer.py`, `test_dashboard_hybrid.py` (not `test_dashboard_critique_fixes.py`, which still passed).
**Phase A differences from the plan:**
- **A1 finding:** `/scheduler_quick_assign_shift` replaces the engineer list (`delete_shift_engineer_links` then re-adds), so the drop sends existing ∪ dropped, as planned. Its conflict check still applies and refuses overlapping visits.
- **A2:** `visits` is built in `get_scheduler_coordination_tools`, not inside `scheduler_engineer_availability_row`, so each shift is serialized once and shared across its engineers. Added `board_start` (Manila date): `generated_at` is UTC and would show the wrong day before 08:00 Manila.
- **Step 0.2:** the version attribute sits on the `scheduler-board` section, not the page root: the role flags are `{% set %}` below the root `<div>`. A page with no attribute never resets. The account-copy reset waits for page load, because `getCSRFToken` is defined later by `layout.html` (calling it early stopped the whole script; caught in the browser check).
- **Phone order:** queue, selected, lanes (plan said queue, lanes, selected). With 27 lanes the panel a tapped row fills sat 3,000 px down.
- **Removed:** the per-section Hide buttons (one board, nothing to hide), the load-level side stripe (the badge already shows load; detector "side-tab"), unused `schedulerAvailabilityClass`. The dispatch metric strip got the engineer strip's two-column phone layout.
- **Tests updated** for the merged section: `test_dashboard_scheduler.py`, `test_dashboard_engineer.py`, `test_dashboard_critique_fixes.py`.
**Approved:** 2026-10-11 (owner: "approved, a").
**Detailed:** 2026-10-11.
**Source:** The owner's research on 10 field-service dashboards (see "Dashboard Critique Fixes" below, Context), narrowed to two models: **MaintainX** (engineer work-order list) and **ServiceTitan** (dispatch board, KPI tiles).
**Branch:** `main` (local first; nothing is pushed until a separate "commit and push").
**Delivery:** three phases, each its own publish with its own tests, browser check, release entry and commit: **A scheduler → B engineer → C manager**. Start each phase only on a go-ahead; the owner may say "do all three".

## Context

Commit `e55deb2` applied the research as fixes on the old layout. The scheduler workbench and "Needs Your Decision" were off-limits, so pattern 6 (dispatch on one screen) never happened and no role page looks like the dashboards researched. The owner expected a remodel.

Intended outcome:
- **Scheduler:** one-screen dispatch board — queue, engineer lanes, selected job — like ServiceTitan's Dispatch Board.
- **Engineer:** a "My Work Orders" list with status tabs and a detail panel, like MaintainX.
- **Manager:** clickable KPI tiles first, then the decision list, like ServiceTitan's dashboard.
- **Staff:** unchanged ("Waiting on you", shipped in `e55deb2`).

## Decisions taken

1. Scheduler workbench and "Needs Your Decision" are **unlocked** (owner, 2026-10-11). This supersedes decision 2 of "Dashboard Critique Fixes".
2. Models: MaintainX + ServiceTitan (owner, 2026-10-11).
3. Saved Customize layouts: **reset everyone once** to the new default per remodelled role (owner choice "a"). Customize/Reset stay available.
4. No priority field exists, so urgency = days late (the existing past-due chip). MaintainX's High/Medium/Low is not imitated.
5. Drag-and-drop **assigns** only. Moving a visit in time stays in the Reschedule box.
6. Every existing function, element id and `onclick` handler listed in Investigation stays defined and working (AGENTS.md "Protect Existing Functions").

## Investigation

- Files: `templates/dashboard.html` (50 KB), `static/js/app-dashboard.js` (87 KB, ~104 functions), `static/css/app-dashboard.css` (44 KB). Assets at `app-dashboard.css?v=6` (`dashboard.html:4`), `app-dashboard.js?v=5` (`dashboard.html:838`). Service worker `CACHE_VERSION` at `app.py:27334` (`…-v286-dashboard-critique-fixes`).
- Role branches in `dashboard.html`: scheduler `{% if dashboard_effective_scheduler_only %}` (L80–265; sections `scheduler-core`, `scheduler-dispatch`, `scheduler-coordination`); manager (L267–460; `manager-executive`, `manager-direction`, `manager-watchlist`, `admin-counters`); engineer (L471–558; `engineer-summary`, `engineer-today`), staff (L560), `quick-admin` (L593), `my-active-tasks` (L672), `open-technical-tasks` (L716).
- Data the page already loads (`fetchJsonOrThrow`): `/get_scheduler_dispatch_intelligence` (L820), `/get_scheduler_coordination_tools` (L975), `/get_manager_approvals` (L530), `/get_manager_overview` (L666), `/get_my_pending_tsr_count` (L1172), `/api/nav/pending-summary` (L1205), `/get_engineers`, `/get_clients`, `/get_products`, `/get_open_tasks` (L1370–1382).
- `/get_open_tasks` (`app.py:34802`) excludes `Completed`, Training and leave. Fields: `id, date, task_date, time_start, time_end, status, client, product_name, serial, engineer_ids, engineer_names, has_tsr, age_days, task …`. So **Done this week needs a new personal route** (step B2).
- `scheduler_engineer_availability_row` (`app.py:35189`) returns counts only (`today_tasks`, `next_7_days`, `overdue`, `waiting_items`, `availability`), no times. Lanes need each engineer's visits with start/end → additive field in step A2. `get_scheduler_coordination_tools` (`app.py:35259`) already loads open service shifts −30/+30 days.
- Assign goes through `submitSchedulerQuickAssign()` → `POST /scheduler_quick_assign_shift {shift_id, engineer_ids}` (`app-dashboard.js:1083`). **To verify in A1:** whether the route replaces or adds to the assigned list; a drop must keep the engineers already assigned.
- Layout storage: keys `medical_dashboard_{layout,collapsed,hidden}_<user>` (`app-dashboard.js:161-163`) plus the account copy via `/api/preferences/dashboard-layout` (`app.py:31882`). `resetDashboardLayout()` (`L347`) clears both.
- Timeline deep link supports `?date=` only (`applyTimelineUrlDateTarget`, `timeline.html:14203`); it cannot open a specific visit. So the detail panel's action is "Open on timeline" (TSR upload happens there). The outline's separate "Upload TSR" button is folded into that link, because a direct upload needs a timeline change, which is excluded.
- Functions that must survive (called from markup or other code): `toggleDashboardSection`, `loadSchedulerDispatchIntelligence`, `setSchedulerQueueFilter`, `loadSchedulerCoordinationTools`, `setSchedulerBranchFilter`, `selectSchedulerActionShift`, `selectSchedulerEngineerForAssign`, `submitSchedulerQuickAssign`, `submitSchedulerQuickReschedule`, `loadManagerOverview`, `loadManagerApprovals`, `renderManagerPmSummary`, `renderMyTasks`, `renderEngineerTodayPanel`, `updateEngineerSummaryCards`, `filterAndRender`, `toggleSort`, `populateEngineerFilter`, `toggleDashboardCustomizeMode`, `resetDashboardLayout`, `renderDashboardChangelogPrompt`. Ids to keep include `scheduler-selected-shift-id`, `scheduler-assign-engineers`, `scheduler-reschedule-{date,start,end}`, `scheduler-action-status`, every `scheduler-*-count`, `manager-approvals*`, `manager-*-count`, `my-tasks-body`, `no-my-tasks`, `dashboard-customize-toggle`, `dashboard-whats-new*`.
- Tests: `tests/test_dashboard_{critique_fixes,engineer,hybrid,manager,scheduler,text_encoding}.py` (static-source style). Some assert today's markup and will need updating where the markup legitimately changes; each update is listed in the phase's change log.

## Execution steps

### Phase 0 — shared (done with phase A)

0.1 **Read first:** newest section of `changes.md`; the 6 dashboard test files; DESIGN.md; the functions in Investigation in full before touching them.
0.2 **One-time layout reset** (`app-dashboard.js`): the template renders `data-dashboard-layout-version` on the dashboard root, set per role branch (scheduler, engineer, manager; staff stays 1). In `initDashboardDragAndDrop()`, if `localStorage['medical_dashboard_layout_version_<user>']` ≠ that value, clear the three layout keys, call `syncDashboardLayoutToAccount([], [])` once, then store the value. Each phase bumps only its own role's version, so only that role's users reset, once. Done = a stale saved order no longer reorders the new sections; Reset still works.

### Phase A — Scheduler dispatch board (ServiceTitan)

A1. **Verify assign semantics** of `/scheduler_quick_assign_shift`; record the finding under this plan. A drop sends `existing engineer_ids ∪ {dropped}`.
A2. **Backend, additive** (`app.py`, `scheduler_engineer_availability_row`): add `visits: [{shift_id, date, time_start, time_end, client, status, overdue}]` for the engineer's open shifts from today to today+6. Existing keys unchanged. Done = endpoint test asserts the new key and the old keys.
A3. **Layout** (`dashboard.html`, `app-dashboard.css`): replace the three stacked sections with one `scheduler-board` section, CSS grid, three columns at ≥1200 px:
   - **Left — Queue:** risk line, the five filter counts (same buttons, ids, `setSchedulerQueueFilter`), `#scheduler-dispatch-list`.
   - **Middle — Board:** branch filter strip (same ids); a **Today / 7 days** toggle; one lane per engineer (name, initials, availability chip, today count). Today = hour axis 07:00–19:00 with visit blocks placed by time; 7 days = 7 day-columns with block counts. Blocks are coloured by status (DESIGN.md status colours, never the accent); overdue blocks carry the "N days late" text.
   - **Right — Selected job:** the existing Selected Schedule card (assign `<select>`, reschedule inputs, Save buttons, `#scheduler-action-status`) unchanged in ids.
   - 768–1199 px: queue and selected job stacked on the left, board on the right. Below 768 px: queue, then the board as a list of engineers, each expandable to their visits, then the selected job.
   Done = all three regions visible without scrolling at 1366×768.
A4. **Lanes render** (`app-dashboard.js`): new `renderSchedulerBoard()`, called from `renderSchedulerCoordinationTools()`; `renderSchedulerAvailabilityStrip()` kept (delegates to the board) so callers keep working. Clicking a block calls `selectSchedulerActionShift(id)`; clicking a lane header calls `selectSchedulerEngineerForAssign(id)`.
A5. **Drag to assign:** queue rows `draggable="true"`; lanes are drop targets. A drop selects the shift, shows a confirm line in the selected-job card ("Assign <engineer> to <facility>, <date>?" with Confirm / Cancel), and Confirm goes through `submitSchedulerAction('/scheduler_quick_assign_shift', …)`. Keyboard/touch fallback: select a row, then click "Assign here" on a lane. Done = assign works by drag, by keyboard and by the old Save Assignment.
A6. **Self-review:** every Investigation function and id still present (grep); `git diff` shows no change outside the scheduler branch of the template besides phase-0 code.
A7. **Tests** (new `tests/test_dashboard_dispatch_board.py`): `visits` key and scoping in coordination tools; board markup present with the three regions; kept ids and functions present; drop handler calls the existing assign route; layout version constant present. Show each fails on `HEAD` first. Update `test_dashboard_scheduler.py` where it asserts the old three-section markup.

### Phase B — Engineer work orders (MaintainX)

B1. **Layout** (`dashboard.html`): the engineer branch becomes a header line (today: visits · overdue · TSRs pending · waiting parts; same `count-*` ids and `updateEngineerSummaryCards`) plus one `engineer-work-orders` section that replaces `engineer-today` and `my-active-tasks`. Keep `my-tasks-body` and `no-my-tasks` as the list containers so `renderMyTasks` callers keep working. Open Technical Tasks stays below, collapsed.
B2. **Done this week** (`app.py`): new `GET /get_my_done_tasks` (`@login_required`), Completed service visits of the signed-in user's own engineer profile in the last 7 days (Manila), same row shape as `/get_open_tasks`; `[]` without a profile. Loaded only when the tab is opened.
B3. **Tabs** (`app-dashboard.js`): `renderMyTasks()` renders the active tab — **Today · Overdue · Upcoming · Waiting parts · Done this week** — each with its count. Rows: status chip, "N days late" chip when overdue, facility, equipment + serial, time, TSR state (`has_tsr`). Empty tab = one line ("Nothing overdue").
B4. **Detail panel:** clicking a row opens a right-side panel at ≥992 px, or a full-screen sheet below that: facility, equipment, serial, date/time, engineers, status, TSR state, task notes, and **Open on timeline** (`/timeline?date=`). Close with Esc or the button; focus returns to the row.
B5. **Self-review** as A6, for the engineer branch and the hybrid view (`dashboard_effective_hybrid_view` keeps the "yours" labels).
B6. **Tests** (new `tests/test_dashboard_work_orders.py`): `/get_my_done_tasks` returns only the signed-in engineer's completed visits from the last 7 days and never another engineer's; tabs and panel markup; kept ids/functions. Fail-first on `HEAD`. Update `test_dashboard_engineer.py` / `test_dashboard_critique_fixes.py` where they assert `engineer-today` markup.

### Phase C — Manager KPI tiles (ServiceTitan)

C1. **Layout** (`dashboard.html`): the manager branch opens with a KPI tile row: **Approvals waiting · Overdue · TSRs pending · Inventory PM done/due · Waiting parts**. Values come from the existing `manager-*-count` ids and `renderManagerPmSummary`; the ids move into the tiles. Below: approvals list (`#manager-approvals`, unchanged), risk line, Direction, What Needs Attention, then Directory Totals last.
C2. **Clickable tiles** (`app-dashboard.js`): Approvals → `/approvals`; Overdue / TSRs / Waiting → expand What Needs Attention filtered to that type (`renderManagerWatchlist` gains an optional type filter, default unchanged); PM → stays in Direction. Zero tiles stay neutral.
C3. **Self-review** as A6, including the hybrid view (manager + own engineer work orders).
C4. **Tests** (new `tests/test_dashboard_manager_kpis.py`): tile markup, ids kept, watchlist filter default unchanged. Fail-first. Update `test_dashboard_manager.py` where needed.

## Deliberately excluded

- **Priority levels:** no data for them (decision 4).
- **Drag to reschedule / resize blocks:** the Reschedule box covers it; time-drag needs conflict checks the board does not have (decision 5).
- **Timeline changes, including deep-linking to one visit:** separate page; "Open on timeline" by date is enough.
- **Staff landing:** shipped in `e55deb2`, unchanged.
- **Map view (ServiceTitan's map):** no location data on engineers.
- **Real-time updates:** the Refresh buttons stay; no polling or sockets.

## Verification (per phase)

- New tests fail on `HEAD` first (positive control), then pass.
- Focused run: `venv/Scripts/python.exe -m unittest tests.test_dashboard_engineer tests.test_dashboard_hybrid tests.test_dashboard_manager tests.test_dashboard_scheduler tests.test_dashboard_text_encoding tests.test_dashboard_critique_fixes` plus the phase's new module and the changelog/dark-mode modules run last time.
- Full suite: not required (one page plus additive routes; no shell, shared helpers, auth or schema). If a phase touches a shared helper after all, run it once before publishing.
- `impeccable detect --json templates/dashboard.html` once per phase.
- Browser check on a copy of `scheduler.db` with temporary scheduler / engineer / manager accounts (manager on a `MANAGER_USERNAMES` name): 1366 and 375 px, light and dark. Scheduler: three regions on one screen, lanes match SQL for today, drag-assign and keyboard-assign persist, reschedule still saves, a stale saved layout is reset once. Engineer: tab counts match SQL, Done this week shows only own visits, panel opens/closes with focus return. Manager: tiles match the old numbers, tiles filter the watchlist, approvals link works. Console clean, tap targets ≥44 px, no horizontal scroll at 375. Clean up DB copy, accounts and launch entry afterwards.

## After implementation (per phase)

1. Bump `?v=` on `app-dashboard.css` and `app-dashboard.js` (A: 6→7 / 5→6; then +1 each phase).
2. Bump `CACHE_VERSION` (`…-v287-dispatch-board`, `…-v288-work-orders`, `…-v289-manager-kpis`), keeping the old value as a history comment.
3. `static/changelog/releases.json` entry at the top, category Dashboard, plain wording ("New dispatch board", "Your work orders", "Manager numbers first").
4. `changes.md` bullets under the execution date; DESIGN.md if a new pattern (lane block, KPI tile, side panel) is introduced.
5. Update this plan: phase status, commit hash, differences.
6. Commit checklist: stage only `templates/dashboard.html`, `static/css/app-dashboard.css`, `static/js/app-dashboard.js`, `app.py`, the tests, `releases.json`, `plans.md`, `changes.md`, `DESIGN.md` if changed. Never `scheduler.db`, `output/`, `tmp/`, handoffs. Publish only on a separate "commit and push".
7. One re-critique in a new session after phase C.

## Risks

- **Breaking scheduler actions** (most-used mutating view): ids and functions kept; A5/A6 test old Save Assignment and Reschedule alongside the new drag.
- **Drop replaces existing engineers:** A1 verifies the route; the drop sends the union.
- **Lane load cost:** `visits` reuses the shifts already loaded (no new query); 7-day window only.
- **Existing tests asserting old markup:** updated in the same phase and listed in `changes.md`, never deleted silently.
- **Layout reset:** per-role version (step 0.2), so each user resets once, when their own role's page changes. A hybrid manager-engineer resets on the manager version only; Customize remains.
- **Scope size:** three independent phases; stop after any phase without leaving the page half-built.

# Dashboard Critique Fixes (all 5 issues)

**Status:** Executed — published to `main` on 2026-10-11 on the owner's "commit and push" (commit `e55deb2`). New `tests/test_dashboard_critique_fixes.py` (19 tests; 12 of its 13 source tests fail against the `HEAD` template/JS/CSS, the 13th is the off-limits guard and passes on both; the endpoint tests need `/get_my_pending_tsr_count` and `inventory_pm_month_summary`, absent from `HEAD`). Focused run: 108 tests OK (dashboard ×6 modules, changelog coverage, dark-mode readability). Full suite not run (no shared code touched). Detector: 1 advisory left (the `2rem` lock icon, a known false positive). Browser check on a DB copy passed (engineer and staff at 375 px, manager at 1366 px, graphite dark and light).
**Differences from the plan:**
- **What's New unread count (step 9):** no change needed. `/api/changelog/unread-summary` already applies the same 30-day window as the sidebar dot (release `2026-10-10-whats-new-dot-recent`); the critique's "90 vs 34" came from two accounts with different read states.
- **Heading levels (step 6):** promoted to h3/h4 everywhere except the off-limits scheduler and "Needs Your Decision" blocks, which keep their h5/h6 (decision 2 outranks a perfect outline). Engineer and staff views now read h1 → h2 → h3.
- **What's New (step 2):** placed after the role's first work sections (before Shortcuts). A saved custom layout re-appends the sortable sections, so for those users it sits above them; harmless, and Customize is desktop-only.
- **Metric strip wrap (step 4):** the two-column phone layout is scoped to the engineer strip only, so the scheduler and manager strips are visually untouched.
- **Shortcuts for staff (step 7):** Timeline is shown only when `can_access_timeline_page()` allows it (new template value `dashboard_can_open_timeline`) and TSR files only with `nav_can_view_admin_reports`, so staff are never offered a link that bounces.
- **Extra one-line fix:** "Needs you today" title and hint were inline spans that ran together ("dateOspital"); they now display as two lines. Found during the browser check; pre-existing.
- **Existing test updated:** `tests/test_dashboard_engineer.py::test_needs_you_today_is_built_from_loaded_data` now finds the empty state through the shared `renderDashboardClear` helper.
**Approved:** 2026-10-11 (owner: "approved, write it to plans.md").
**Detailed:** 2026-10-11.
**Source:** Impeccable critique `.impeccable/critique/2026-10-11T03-23-50Z__templates-dashboard-html.md` (23/40; 3 × P1, 2 × P2), preceded by a research pass on 10 field-service dashboards and a read-only page scan.
**Branch:** `main` (local first; nothing is pushed until a separate "commit and push").

## Context

The owner researched 10 field-service dashboards (ServiceNow clinical engineering, TheWorxHub BioMed, Smart Hospital Maintenance, Dynamics 365 Field Service, ServiceTitan, Jobber, Arrivy, MaintainX, Limble, Linear) and adopted 6 patterns: (1) attention first, (2) role-based landing, (3) hide empty boxes, (4) status colour + filters on task lists, (5) field KPIs, (6) dispatch on one screen.

The scan and critique found the engineer and fallback views bury the work under chrome (on a 375 px phone the first work section starts at y=623), statuses don't signal urgency, rows lead nowhere, the 3 active `staff` accounts land on a raw 124-row table, zeros render red, and there are no field KPIs.

Intended outcome: the engineer's day is on the first phone screen, every status and row is actionable, every role sees what is waiting on them, and managers see PM performance.

## Decisions taken

1. Fix all 5 priority issues plus the page-level minor observations (owner, 2026-10-11).
2. **Off-limits:** the scheduler workbench (`scheduler-core`, `scheduler-dispatch`, `scheduler-coordination`) and the manager's "Needs Your Decision" section (`manager-executive`, including its approvals block and metric strip). Their markup must stay byte-identical.
3. Critique-loop rule: fix exactly the critique's points, introduce no new issues; one fresh re-critique in a new session at the end.
4. Staff landing = "Waiting on you" (approvals + My Requests) plus Shortcuts (owner, 2026-10-11).
5. PM KPI covers inventory PM (Genoray, Vieworks) only, and says so in its label (owner, 2026-10-11).
6. Engineer strip gets a 5th item, "TSRs pending" (owner, 2026-10-11).

## Investigation

- All 13 template `onclick` handlers are defined in `static/js/app-dashboard.js` (nothing missing).
- The Layout toolbar copy says "saved on this device" (`templates/dashboard.html:108`), but the layout syncs to the account (`syncDashboardLayoutToAccount` / `loadDashboardLayoutFromAccount`, `static/js/app-dashboard.js:184-222`).
- "Needs You Today" rows all link to `/timeline` (`renderEngineerTodayPanel`, `app-dashboard.js:1221`).
- The timeline already deep-links: `?date=YYYY-MM-DD` jumps to that date's week (`applyTimelineUrlDateTarget`, `templates/timeline.html:14203`). No timeline change needed.
- `dashboardBootstrapStatusClass` returns `bg-primary` (the accent) for In Progress, against DESIGN.md "Don't re-theme schedule or status colours with the accent". The mobile chip `.dashboard-status-progress` measured 3.95:1 at 9.9 px (122 instances).
- `count-my-continuation` always carries `dashboard-metric-alert` (`dashboard.html:530`), so "0" renders red.
- What's New (`dashboard.html:79-93`) uses inline `#9ad8b8`, `#14804a`, `#f2fbf6`, `#d9f2e5`, `#11643a` and `border-radius:8px`; `app-dashboard.css` has no rules for it, so it is light-only. Detector: 6 true positives (L70 clock `0.9rem`, L79, L82); L839 lock icon `2rem` is a false positive. The date line is 4.29:1.
- No `<h1>`; outline is H2 → H3 → H6 → H5. `fa-hand-wave` is a Font Awesome Pro icon and renders as an empty gap.
- The branch `not dashboard_effective_scheduler_only and not dashboard_effective_manager_view` (`dashboard.html:710`) shows only Open Technical Tasks to accounts without an engineer profile. Active accounts affected: the 3 `staff` users (no engineer profile, not admin, not HR-only, not stock-only — verified on `scheduler.db`). The `approver` account has an engineer profile and gets the engineer view.
- `/api/nav/pending-summary` already returns `approvals_pending` and `my_requests_action`; the sidebar badges `/approvals` and `/accounting_center` ("My Requests", `layout.html:238`) from it.
- `InventoryPmVisit` (`app.py:2812`) has `brand`, `equipment_serial`, `target_date`, `completed_at`, `shift_id` — Genoray and Vieworks inventory PM only.
- Pending TSR in `/get_manager_overview` (`app.py:35663`) = a completed shift with no TSR file (`shift_has_tsr_file`, around `app.py:35731`). There is no per-engineer equivalent today.
- The temp superadmin used for the critique did not get the manager view: `is_superadmin_user()` (`app.py:11583`) also needs the username in `SUPERADMIN_USERNAMES`; `is_manager_dashboard_user()` admits `MANAGER_USERNAMES` or admin-authorized non-schedulers. The browser check must use such a name.
- Existing tests: `tests/test_dashboard_{engineer,hybrid,manager,scheduler,text_encoding}.py` (static-source style). Assets: `app-dashboard.css?v=5`, `app-dashboard.js?v=4`. `CACHE_VERSION` at `app.py:27333` (`…-v285-signin-activity-log`).

## Execution steps

1. **Read first:** newest section of `changes.md`; the 4 dashboard test files; `renderMyTasks`, `filterAndRender`, `renderMobileTaskList`, `renderDashboardChangelogPrompt` in full.
2. **Attention first** (`/impeccable distill`; `templates/dashboard.html`, `static/css/app-dashboard.css`, `static/js/app-dashboard.js`):
   - Replace the `dashboard-personalize-toolbar` block with a small "Customize" icon button and "Reset" in the header row, hidden at ≤768px. Keep id `dashboard-customize-toggle` and functions `toggleDashboardCustomizeMode()` / `resetDashboardLayout()`; add a `confirm()` to Reset.
   - Copy: "saved to your account".
   - Hide the clock badge at ≤768px.
   - What's New becomes a one-line dismissible strip placed after the first work section; keep the `dashboard-whats-new*` ids so `renderDashboardChangelogPrompt` keeps working.
   - Done = at 375px the first work section starts in the first screen (target y < 300).
3. **Quiet zero states** (`distill`; `updateEngineerSummaryCards`, `renderMyTasks`, `dashboard.html`):
   - Apply `dashboard-metric-alert` / `-warn` from JS only when the value is > 0 (remove the static classes from the markup).
   - Engineer with no tasks: hide the empty `my-tasks` table headers; show one "You're clear" line naming the next upcoming visit when there is one.
   - Done = zeros render neutral; one empty message instead of three.
4. **Phone fixes** (`/impeccable adapt`; `app-dashboard.css`, `renderMobileTaskList`):
   - Fix the metric-strip wrap that orphans "waiting" behind a dangling divider.
   - Mobile task lists render 20 cards, then a "Show 20 more" button.
   - Done = fallback mobile page < 6,000px; no horizontal overflow at 375px.
5. **Status colour and urgency** (`/impeccable colorize`; `dashboardStatusClass`, `dashboardBootstrapStatusClass`, `app-dashboard.css`):
   - Fixed semantic status colours (In Progress = fixed info/slate pair, not the accent); ≥4.5:1 in light and dark; mobile chip ≥0.75rem.
   - Past-due rows (date < today, not completed): tinted row plus an "N days late" text chip (not colour alone).
   - Move What's New inline hex and radius into CSS using Bootstrap success variables / theme tokens so it works in all 4 themes.
   - Done = the 6 detector true positives are gone; contrast passes in light and dark.
6. **Rows that lead somewhere + filters** (`/impeccable harden`; `renderMyTasks`, `buildDashboardTaskMobileCard`, `filterAndRender`, `renderEngineerTodayPanel`, `dashboard.html`):
   - Rows and mobile cards link to `/timeline?date=<task_date>`; "Needs You Today" rows link to their first task's date.
   - Open Technical Tasks: search box (facility, engineer, equipment, task) and an engineer `<select>` built from the loaded rows.
   - Replace the 3-state sort button with a labelled `<select>`; keep `toggleSort()` defined (delegating) so nothing breaks.
   - Add one visually-hidden `<h1>Dashboard</h1>`; fix heading levels (Layout `h6` goes with step 2; empty-state `h6` → `p`).
   - Replace `fa-hand-wave` with a free icon or remove it.
   - Done = rows reachable with Tab; heading outline h1 → h2 → h3 with no skipped levels.
7. **Staff landing** (`/impeccable shape`; `dashboard.html`, `app-dashboard.js`):
   - For the fallback branch without an engineer profile: a "Waiting on you" card fed by `/api/nav/pending-summary` (approvals pending → `/approvals`; requests needing attention → `/accounting_center`), with an "all clear" line when both are 0.
   - Show the Shortcuts block for them too (widen its gate; admin-only links stay gated by `dashboard_effective_admin_view`).
   - Open Technical Tasks starts collapsed for them, as it already does for engineers.
   - Done = a staff account sees waiting items first; the table is one click away.
8. **Field KPIs** (`shape`; `app.py`, `app-dashboard.js`, `dashboard.html`):
   - `/get_manager_overview` gains `pm: {due_this_month, done_this_month, overdue}` from `InventoryPmVisit` (Manila month; both brands; manager view only). Rendered as a row in the **Direction** card labelled "Inventory PM (Genoray, Vieworks) this month: done / due · N overdue".
   - New `GET /get_my_pending_tsr_count` (`@login_required`; only the signed-in user's own engineer profile's shifts; same definition and date window as the manager's pending TSR; 0 for accounts without a profile). Shown as a 5th "TSRs pending" item on the engineer strip, neutral when 0.
   - Done = both numbers match a manual SQL count on the DB copy.
9. **Polish** (`/impeccable polish`):
   - Replace the stale header comment (`dashboard.html:9-25`) with a short accurate one.
   - Remove the duplicated "Reference:" heading inside the Open Tasks toggle.
   - One column vocabulary in both tables ("Engineer", "Facility").
   - Move inline table widths and badge sizes into CSS.
   - What's New unread number uses the same 30-day window as the sidebar dot (`CHANGELOG_UNREAD_DOT_DAYS`).
10. **Self-review:** every function, id and handler that existed is still defined and used; save/assign/reschedule/refresh/customize still work; scheduler and manager-executive blocks unchanged in `git diff`; update DESIGN.md if a new status-colour rule is introduced.

## Deliberately excluded

- **Scheduler workbench and "Needs Your Decision":** off-limits (decision 2).
- **Cleaning the 124 months-old "In Progress" visits:** data hygiene for the owner, not design; the past-due chip makes them visible.
- **`SUPERADMIN_USERNAMES` provisioning, `/dashboard` 404, engineers landing on `/timeline` after login:** outside this page.
- **Keyboard shortcuts and URL filter state:** not a priority issue.
- **Manager Directory Totals:** kept; Customize already allows reordering or hiding.
- **PM for non-inventory equipment:** no structured PM-due data exists for it (decision 5).

## Verification

- New tests, each shown to fail on the current code first (positive control):
  - Template/JS: no `bg-primary` status class; alert/warn class applied only when > 0; `?date=` links in the row renderers; an `<h1>` present; toolbar copy says "account"; no inline hex inside `#dashboard-whats-new`; scheduler and manager-executive markup unchanged.
  - App: `pm` block in `/get_manager_overview` (seed due / done / overdue visits, assert counts); `/get_my_pending_tsr_count` counts only the signed-in engineer's shifts and never another engineer's.
  - Staff fallback: renders "Waiting on you" and Open Tasks starts collapsed.
- Focused run: `venv/Scripts/python.exe -m unittest tests.test_dashboard_engineer tests.test_dashboard_hybrid tests.test_dashboard_manager tests.test_dashboard_scheduler tests.test_dashboard_text_encoding -v` plus the new modules.
- Full suite: not required (one page plus one new route; no shared helpers, shell, auth or schema).
- Impeccable detector once at the end: `impeccable detect --json templates/dashboard.html`.
- Browser check on a copy of `scheduler.db` with temporary engineer, staff and manager accounts (manager on a `MANAGER_USERNAMES` / `SUPERADMIN_USERNAMES` name so the real manager view renders): desktop 1366 and mobile 375, light and dark theme — first screen shows work, no red zeros, past-due chips, row links land on the right week, search/filter, Show more, staff landing, PM/TSR numbers match SQL, scheduler and manager-executive unchanged, console clean, tap targets ≥44px. Clean up the DB copy, accounts and launch entry afterwards.

## After implementation

1. Bump `?v=` on `app-dashboard.css` (5 → 6) and `app-dashboard.js` (4 → 5).
2. Bump service worker `CACHE_VERSION` to `…-v286-dashboard-critique-fixes` (old value kept as a history comment, following the existing pattern).
3. Add a `static/changelog/releases.json` entry at the top ("Dashboard: your day first", category Dashboard, plain wording).
4. Append detailed bullets to `changes.md` under the execution date.
5. Update this plan's Status to `Executed` with the commit hash and any differences from the plan.
6. Commit checklist: stage only `templates/dashboard.html`, `static/css/app-dashboard.css`, `static/js/app-dashboard.js`, `app.py`, the tests, `static/changelog/releases.json`, `plans.md`, `changes.md` (and `DESIGN.md` if changed); never `scheduler.db`, `output/`, `tmp/` or handoff artifacts. Publish only on a separate "commit and push".
7. Re-critique in a **new session** that starts from the snapshot file.

## Risks

- **Breaking an existing handler** (Reimbursement precedent): ids and functions are kept; step 10 checks each one.
- **New route leaking another engineer's data:** scoped to `current_user`'s engineer profile; a test asserts it.
- **PM number misread as all PM:** the label names Genoray and Vieworks.
- **Scope size (10 steps):** each step is independently testable; if it runs long, split after step 6 and record the split here.

# Record Sign-ins in the Activity Log

**Status:** Executed — published to `main` on 2026-10-10 on the owner's "commit and push" (commit `2a4d59e`). 9 new tests (7 fail on the previous `app.py`; the 2 "must not log" guards pass on both); focused run 74 tests OK. Full suite before publishing: 1,688 tests, 14 failures (the known list), 3 errors that occur only alongside other test files, 5 skips, no new failures. Browser check on a DB copy passed.
**Differences from the plan:** none.
**Approved:** 2026-10-10 (owner: "yes to both, write it to plans.md").
**Detailed:** 2026-10-10.
**Branch:** `main` (local first; nothing is pushed until a separate "commit and push").

## Context

HR's compliance deck (claude.ai artifact "Medical Service Management System Framework", page 8 "All transactions are recorded" and page 12 "Open items") lists **"Record each sign-in in the activity log — Planned"**. Today the Activity log records actions but no sign-ins, sign-outs or failed attempts, so a reviewer cannot answer "who signed in, and were there failed attempts?".

Intended outcome: every interactive sign-in, failed sign-in, blocked sign-in and sign-out appears on the Activity page with a Security badge, without flooding the log. After publishing, the deck's open item becomes Done.

## Decisions taken

1. **Log sign-outs:** yes (owner, 2026-10-10).
2. **Log failed attempts:** yes (owner, 2026-10-10).
3. **Only the login form counts as a sign-in.** Automatic re-authentication (PWA restore cookie, 30-day remember-me cookie) is not logged. This is what keeps the noise down.
4. **Unknown usernames are logged without the typed text**: people sometimes type their password into the username box, so the typed value must never be stored.
5. Wording (exact action texts):

| Event | `ActivityLog.user` | `ActivityLog.action` |
| --- | --- | --- |
| Successful sign-in | the user | `Signed in` |
| Wrong password, known account | that username | `Failed sign-in: wrong password` |
| Correct password, deactivated account | that username | `Blocked sign-in: account deactivated` |
| Correct password, `login_user` refused | that username | `Blocked sign-in: account cannot sign in` |
| Unknown username | `Unknown` | `Failed sign-in: unknown username` |
| Sign-out (authenticated user only) | the user | `Signed out` |

## Investigation

- **Login/logout logging was switched off on purpose before.** The `app.py` header says "ACTIVITY LOGGING (v5.4.5) … Disabled login/logout logging to reduce noise" (`app.py:19-21`), and `logout()` carries `# log_activity removed v5.4.5 per request` (`app.py:13063`). The noise came from logging every session; decision 3 avoids it. The owner was told this before approving.
- `login()` is at `app.py:12959` (rate limit `10 per minute; 60 per hour` on POST, `app.py:12958`). Order of branches: unknown user → dummy hash compare (`DUMMY_PASSWORD_HASH`, `app.py:7513`); correct password + `is_active` false → flash "deactivated"; correct password → `login_user(...)`; `logged_in` false → flash "cannot sign in right now"; otherwise `last_login_at` is stamped and committed inside a `try/except` with rollback (≈`app.py:12997-13002`); else → flash "Username or password is incorrect".
- `logout()` is at `app.py:13062`, not `@login_required`; it calls `logout_user()` then `session.clear()`. `current_user` may be anonymous here.
- PWA restore signs users in via `restore_user_from_pwa_login_cookie()` (`app.py:7670`, `login_user(..., fresh=False)` ≈`app.py:7697`), a separate path from `login()`. Remember-me is handled by Flask-Login. Neither goes through `login()`, so logging only inside `login()` satisfies decision 3 without extra checks.
- Helpers: `log_activity(action)` (`app.py:8011`) needs an authenticated `current_user` and commits immediately, so it is unsuitable for failed attempts. `add_activity_log_entry(action, user_label=None)` (`app.py:8018`) adds without committing and capitalizes the label, matching `log_activity`'s `username.capitalize()`. Use it for every event.
- `ActivityLog` (`app.py:1842`): `user`, `action`, `timestamp` (Manila time) only. No schema change needed.
- Classification rules: `ACTIVITY_CATEGORY_RULES` (`app.py:32949`), `ACTIVITY_ACTION_RULES` (`app.py:32969`), `ACTIVITY_SEVERITY_RULES` (`app.py:32987`). `Security` matches `password`, `unauthorized`, `denied` today, so "Failed sign-in: wrong password" is already Security but "Signed in", "Signed out" and "unknown username" are not. `failed` is already `danger`; `blocked` is already `warning`.
- Requests over the rate limit are rejected by Flask-Limiter before `login()` runs.
- Existing tests: `tests/test_activity_log_details.py` (imports `app` with a temp DB via `MEDICAL_SERVICE_TEST_DB`).

## Execution steps

1. **Read first:** newest section of `changes.md`; `login()` and `logout()` in full.
2. **`login()` success path (`app.py`, inside the existing `last_login_at` `try`):** call `add_activity_log_entry('Signed in', user_rec.username)` before the existing `db.session.commit()`, so the entry and the timestamp commit together and the existing `except` rolls both back. Done = a successful login writes exactly one `Signed in` row; a failing commit still signs the user in.
3. **`login()` failed and blocked paths:** add a small local helper, e.g. `record_signin_event(action, user_label)`, that does `add_activity_log_entry(...)` + `db.session.commit()` inside `try/except` with `db.session.rollback()` and a `[AUTH]` print. It never raises. Call it in the deactivated branch, the `logged_in` false branch, the wrong-password branch (known user → their username; unknown → label `Unknown`, action `Failed sign-in: unknown username`). Done = each branch writes exactly one row and the user-facing flash messages and responses are unchanged.
4. **`logout()`:** before `logout_user()`, if `current_user.is_authenticated`, call the same helper with `Signed out` and the username. Replace the `# log_activity removed v5.4.5 per request` comment with one line saying sign-outs are logged again since 2026-10-10 (noise handled by logging only interactive sign-ins). Update the `app.py` header line "Disabled login/logout logging to reduce noise" to match. Done = signing out writes one `Signed out` row; visiting `/logout` signed out writes nothing.
5. **Classification rules:** add `'signed in'`, `'signed out'`, `'sign-in'` to the `Security` entries of `ACTIVITY_CATEGORY_RULES` and `ACTIVITY_ACTION_RULES`. No severity change is needed (`failed` → danger, `blocked` → warning already). Done = all six action texts classify as Security; no existing classification changes (check that `sign-in` does not newly match any existing logged texts with a quick `rg -i "sign-in" app.py leave_feature.py`).
6. **Tests:** new `tests/test_signin_activity_log.py` (same temp-DB import pattern as `tests/test_activity_log_details.py`), using the Flask test client with CSRF disabled for the test app config:
   - each of the six events writes exactly one row with the exact `user` and `action` from the table;
   - the unknown-username row never contains the typed username (use a distinctive value and assert it appears in no `ActivityLog.action` or `.user`);
   - a PWA-cookie restore (`restore_user_from_pwa_login_cookie` path: set a valid PWA login cookie and request a protected page) writes no `Signed in` row;
   - `/logout` while signed out writes no row;
   - classification: all six texts map to the `Security` category/action.
   Positive control: run the new module against the current `app.py` first (before step 2) and record that the event tests fail.
7. **Self-review** the diff: no flash text, redirect, cookie or rate-limit behaviour changed; every function `login()`/`logout()` called before is still called.

## Deliberately excluded

- **Rate-limited attempts:** rejected before `login()`; logging them would need a limiter hook and brings the noise back.
- **PWA restore and remember-me re-authentication:** decision 3.
- **Storing the typed username for unknown accounts:** decision 4.
- **IP address / device:** not requested; `ActivityLog` has no column for it and adding one is a schema change. Can be a later plan.
- **Retention/cleanup of old Activity rows:** waits on HR's retention-period decision (deck open item).
- **Deck update:** done after publishing (page 12 item → removed or Done), outside the codebase.

## Verification

- Focused tests: `venv/Scripts/python.exe -m unittest tests.test_signin_activity_log tests.test_activity_log_details -v`.
- Full suite once, before publishing: `venv/Scripts/python.exe scripts/run_suite.py` (compare with `tests/known_failures.txt`).
- Browser check on a **copy** of `scheduler.db` with a temporary test account: sign in; sign out; fail once with a wrong password; try an unknown username; deactivate the test account and try again; open the Activity page and confirm all rows appear with the Security badge, filter by Security works, and nothing else changed on the login page. Standing bar: 375 px login page, console clean. Clean up the DB copy, test account and launch entry afterwards.

## After implementation

1. Bump the service worker `CACHE_VERSION` (`app.py:27313`, currently `…-v284-daily-db-backup`) to `…-v285-signin-activity-log`.
2. Add a `static/changelog/releases.json` entry at the top (`release_key` `2026-10-10-signin-activity-log`, category `Security`, plain wording: "Sign-ins, failed sign-in attempts and sign-outs now appear in the Activity log.").
3. Append detailed bullets to `changes.md` under `codex changes - 2026-10-10`.
4. Update this plan's Status to `Executed` with the commit hash and any differences from the plan.
5. Commit checklist: stage only the intended files (`app.py`, the new test file, `static/changelog/releases.json`, `plans.md`, `changes.md`); never `scheduler.db`, `output/`, `tmp/`, handoff artifacts or unrelated changes. Publish only on a separate "commit and push".

## Risks

- **Login breaks because of logging:** every write is wrapped and rolls back on error; the success-path entry shares the existing guarded commit. Blast radius if wrong: sign-in for everyone, so the focused tests and the browser check both exercise every branch.
- **Noise returns:** limited to interactive sign-ins; engineers on the PWA appear about once per 30 days. If it is still too noisy, the Security filter hides it; removal is a one-line revert per call site.
- **Password leakage via the username box:** prevented by decision 4 and asserted by a test.

# Daily Automatic Database Backup

**Status:** Executed — published to `main` on 2026-10-09 on the owner's "commit and push" (commit `f28d3c4`). 60 focused tests OK (8 new, all fail on the previous `app.py`). Full suite before publishing: 1,679 tests, 14 failures (the known list), 3 errors that occur only alongside other test files, 5 skips, no new failures.
**Differences from the plan:** (a) the code block sits after `record_storage_activity` rather than after `BACKUP_ARCHIVE_FILENAME_PATTERN`, so every helper it calls is defined above it; (b) activity entries go through a small `record_daily_backup_activity` that logs as user "System" (`record_storage_activity` reads `current_user`, which a background thread does not have); (c) the status line also covers "none has run yet" and "off on this server" (bucket configured but not on Railway).
**Approved:** 2026-10-09 (owner: "yes write it to plans.md").
**Detailed:** 2026-10-09.
**Branch:** `main` (local first; nothing is pushed until a separate "commit and push").

## Context

HR asked for the system's framework for a compliance check (deck: claude.ai artifact "Medical Service System Framework"). Backups today are manual only: a superadmin presses Build Backup on `/admin/backup`; one zip (database + attachments) is written to `/data/backups` on the same Railway volume as the live data, only one is kept, and it expires after 24 hours (`BACKUP_ARCHIVE_MAX_AGE_SECONDS`, `app.py:31009`). There is therefore no history of backups and no copy off the live volume. The deck currently lists "Daily automatic backups, kept 30 days" as **Planned: [date]**; the owner chose not to claim it before it exists.

Intended outcome: every night the database is copied to private object storage, 30 days of copies are kept, and the superadmin can see on the Backup page whether the last run worked.

## Decisions taken

1. **Database only** in the nightly copy. Attachments already live in the bucket; copying them nightly would multiply storage. The manual full backup (database + attachments) is unchanged.
2. **Location:** the existing private bucket, prefix `system_backups/daily/`, file `medical_service_db_YYYYMMDD.sqlite.gz` (Manila date).
3. **Retention:** 30 days; older daily copies are deleted by the job.
4. **Time:** 02:00 Manila. If the server was down at 02:00, run at the first check after it is back that day. At most one successful copy per Manila date.

## Investigation

- `create_sqlite_snapshot(source_path, destination_path)` (`app.py:30640`) copies the live SQLite database with `sqlite3.Connection.backup()` (consistent against a live writer, folds WAL, runs `PRAGMA quick_check`). Reuse it; do not copy the file bytes directly.
- Storage API (`storage_backend.py`): `upload_file(key, path, ...)` (`:255`), `iter_objects(prefix)` (`:343`, yields `key`, `size`, `last_modified`), `delete(key)` (`:340`), `writes_bucket` / `bucket_configured` (`:113`–`:126`). Global instance `file_storage` (`app.py:992`).
- The manual full backup and the storage health report only include bucket keys whose top folder is in `managed_storage_roots()` (`app.py:30890`, used at `:30805` and `:31381`). `system_backups` is not in that list, so the daily copies are **not** pulled into the manual zip and do not affect storage-health counts. Do not add it to `managed_storage_roots()`.
- Durable state lives in `RUNTIME_STATE_DIR` (`/data` on Railway, `instance/` locally; `app.py:30944`); the manual job's state file is `_system_backup_job.json` (`backup_job_state_path`, `:31021`).
- Production runs one Gunicorn process (`gunicorn.conf.py`: `workers: 1`, `gthread`, `preload_app: False`), so one in-process background thread is enough and cannot double-run across workers. `PROCESS_BOOT_ID` (`:30950`) changes per import.
- The Backup page polls `/admin/backup/status` → `backup_status_payload()` (`app.py:32503`); the page's `render(payload)` is inline in `templates/system_backup.html` (`:204`; last-backup line at `:242`–`:246`).
- Activity: `record_storage_activity(action)` (`app.py:31453`). Time: `get_manila_time()` (`:1669`).
- Service worker version string is generated in `app.py:27313` (currently `v283-calibration-fix-report`).

## Execution steps

1. **Constants and state helpers** — `app.py`, beside the backup code (after `BACKUP_ARCHIVE_FILENAME_PATTERN`, `:31010`): `DAILY_BACKUP_PREFIX = 'system_backups/daily'`, `DAILY_BACKUP_RETENTION_DAYS = 30`, `DAILY_BACKUP_HOUR = 2`, `DAILY_BACKUP_CHECK_SECONDS = 15 * 60`; `daily_backup_state_path()` (pure join → `RUNTIME_STATE_DIR/_daily_backup_state.json`), `load_daily_backup_state()` / `save_daily_backup_state(state)` (atomic write via temp file + `os.replace`; load returns `{}` on any error). State keys: `last_date`, `last_ok`, `last_run_at`, `last_key`, `last_size`, `last_error`, `copies_kept`. Done when the helpers round-trip a dict and a missing/corrupt file loads as `{}`.
2. **The job** — `run_daily_database_backup(now=None)`: return early (`'skipped'`) unless `file_storage.writes_bucket`; snapshot `DATABASE_PATH` with `create_sqlite_snapshot` into a temp dir, refuse to upload if `quick_check` is not `ok`, gzip it, `upload_file` to `f'{DAILY_BACKUP_PREFIX}/medical_service_db_{YYYYMMDD}.sqlite.gz'` (`content_type='application/gzip'`); then list `iter_objects(DAILY_BACKUP_PREFIX + '/')`, delete keys matching the file pattern whose date in the name is older than 30 days (date from the name, not `last_modified`); count the remaining copies; save state; `record_storage_activity('Daily database backup saved: <key> (<size>)')`. Any exception: save `last_ok=False`, `last_error=clean_str(error)`, record activity "Daily database backup failed: …", never raise. Always remove the temp dir. Done when one call uploads one object, prunes old ones, and records state.
3. **Timer** — `daily_backup_due(state, now)` (true when `now.hour >= DAILY_BACKUP_HOUR` and `state.last_date != today` or the last run today failed — retry at most once per check interval) and `start_daily_backup_scheduler()`: a daemon thread looping `sleep(DAILY_BACKUP_CHECK_SECONDS)` → if due, run the job; guarded by a module-level lock/flag so it starts once per process. Called at module level after the backup helpers, but only when `os.environ.get('RAILWAY_ENVIRONMENT')` is set, `MEDICAL_SERVICE_TEST_DB` is not set, and `DAILY_BACKUP_DISABLED` is not truthy. Done when importing the app in tests or locally starts no thread.
4. **Status on the Backup page** — add `'daily_backup': daily_backup_status()` to `backup_status_payload()` (`last_date`, `last_ok`, `last_size_human`, `copies_kept`, `last_error`, `enabled` = bucket configured and scheduler running). In `templates/system_backup.html` add one line under the Backup Center message (`id="backup-daily-status"`), filled in `render(payload)`: "Last automatic backup: <date> · <size> · <n> copies kept (30 days)"; red text "Last automatic backup failed on <date>: <error>" on failure; "Automatic backups are off: cloud storage is not configured." when disabled. Nothing else on the page changes; no existing id, function or button is touched.
5. **Tests** — see Verification.

## Deliberately excluded

- Attachments in the nightly copy: already in durable bucket storage; the manual full backup covers them.
- Restore button: rare and risky. Manual restore: download the `.sqlite.gz` from the bucket console, `gunzip`, stop the service, replace `/data/scheduler.db`, start the service. Documented here, not built.
- Email/notification on failure: the Backup page shows it; can be added later.
- Listing/downloading daily copies in the page: available from the bucket console.
- Railway cron service or new Railway variables: not needed; the in-process timer avoids deployment changes. (`DAILY_BACKUP_DISABLED` is an optional off switch, unset by default.)
- No change to the manual backup, its 24-hour expiry, or `managed_storage_roots()`.

## Verification

- New `tests/test_daily_backup.py` (fake `file_storage` object with `writes_bucket`, `upload_file`, `iter_objects`, `delete`; temp `RUNTIME_STATE_DIR` and a small temp SQLite DB):
  - one run uploads exactly one key `system_backups/daily/medical_service_db_<Manila date>.sqlite.gz`, and the uploaded file gunzips to a valid SQLite DB;
  - copies dated 31+ days ago are deleted, 30-day-old and newer are kept, non-matching keys are never deleted;
  - `daily_backup_due` false before 02:00, true after 02:00 when not done today, false after a successful run today, true again after a failed run;
  - bucket not configured → `'skipped'`, no upload;
  - upload raising → state `last_ok=False` with the error, no exception escapes;
  - importing the app under tests starts no scheduler thread;
  - `backup_status_payload()` includes `daily_backup`; the template contains `backup-daily-status`.
  - Positive control: run the new tests against the current code (in-process, never `git stash`) and confirm they fail.
- Focused modules: `tests/test_daily_backup.py`, `tests/test_system_backup.py`, `tests/test_backup_permanent_fix.py`. Full suite once, before publishing.
- Browser (local server on a copy of `scheduler.db`, temporary superadmin login, removed afterwards): `/admin/backup` shows the new line in the "off" state locally; Build Backup, Cancel, Download, Delete still work; 375 px no horizontal scroll; no console errors.

## After implementation

1. Self-review; confirm every function the Backup page calls is still defined and its buttons work.
2. Service worker `v284-daily-db-backup`; What's New release `2026-10-xx-daily-db-backup` ("Daily automatic database backup", superadmin) in `static/changelog/releases.json`.
3. Update `changes.md` and this Status.
4. Wait for "commit and push"; stage only the intended files (never `scheduler.db`, handoffs, `changes-archive.md`, `.impeccable/`, `.claude/`, `output/`, `tmp/`); one `git ls-remote` check, no Railway polling.
5. The morning after deploy: confirm on the Backup page (or bucket console) that the first `system_backups/daily/` file exists, then change the HR deck's backup item from Planned to Done.

## Risks

- **Bucket not configured on Railway:** job skips and the page says automatic backups are off; nothing fails silently.
- **Snapshot load at 02:00:** a few seconds of a shared read lock, the same method the manual backup uses; the 60 s busy timeout absorbs writers.
- **Thread dies or process restarts:** state is on the volume; the next process checks again within 15 minutes and catches up the same day.
- **Wrong deletions:** pruning only touches keys under `system_backups/daily/` that match the exact file-name pattern; covered by tests.
- **Blast radius:** a new background thread, a new bucket prefix, and one line on the Backup page. No user workflow changes.

# Returned Calibration Report: Fix the Report Only

**Status:** Executed — published to `main` on 2026-10-09 on the owner's "commit and push" (commit `88f765c`). Full suite before publishing: 1,671 tests, 14 failures (the known list), 3 errors that occur only alongside other test files, 5 skips, no new failures.

**Outcome (2026-10-09):** steps 1–7 done. Service worker `v283-calibration-fix-report`, release `2026-10-09-calibration-fix-report`, `app-calibration-report.js?v=46`, `app-calibration-report.css?v=12`. Tests: new `tests/test_calibration_report_returned_fix.py` (6 tests; 4 fail on the previous code, the other 2 are guards that pass before and after); updated the old "correction mode" notification test and the version pins; 144 focused tests OK. Browser (DB copy, temporary engineer and approver logins; removed): desktop card shows the red report button with a "!" tag and the remarks as its tooltip; phone shows "Fix Calibration Report" and the tagged quick-action button, 375px without horizontal scroll; the report page shows the red banner with the approver and remarks, "Returned" status, and editable fields; after a change and Save Final Report the same approval went back to Pending with the same certificate number, the TSR stayed REV1, the TSR pointed at the new report file, the audit shows Returned → Pending, and the approver's Approvals page lists it as Pending Review with a "resubmitted" notification.

**Amendments during execution:**
- The Timeline tag is a red "!" badge on a red button (the desktop card button is icon-only, so a "Returned" word does not fit); the remarks are the button tooltip. Lighter red in dark mode.
- Resubmission only happens when the saved report changed (different report fingerprint); an unchanged returned report stays Returned, so a retry or an old upload cannot resubmit it untouched.
- The supporting-attachment count ignores the replaced report file, so a correction never hits the attachment limit.
- Found in the browser: a stale report draft saved on the device could be restored over a returned report and show an old "approved" status. For a returned report, only a local draft saved after the return is restored, and the server's approval status is re-applied after any restore.
- Tests live in a new focused file instead of the two existing modules.
**Approved:** 2026-10-09 (owner: "yes write it to plans.md", after the browser check confirmed the findings below).
**Detailed:** 2026-10-09.
**Branch:** `main` (local first; nothing is pushed until a separate "commit and push").

## Context

When an approver returns (rejects) a Calibration Report & Certificate, the engineer is sent to correct the **whole TSR**: the notification links to Create TSR in `mode=correct`, and saving creates a new TSR revision (REV+1), even though the TSR itself was fine. The owner wants only the Calibration Report reopened.

A browser check (engineer login, DB copy with one approval set to Returned) also showed the engineer is effectively **never told** about the return:

- Dashboard / sidebar: no notification shown anywhere; the "returned" `SystemNotification` is created but no page lists `calibration_certificate` notifications for the requester (that engineer had 16 older unread calibration notifications).
- Approvals page: 403 for engineers.
- Timeline card: plain "View Calibration Report", identical to an approved report, although the server already sends `calibration_report_approval_status: "Returned"`.
- Create TSR, Calibration Report box: green "Uploaded" tag, and one small grey line: "Uploaded Calibration Reports cannot be replaced through this page. Certificate returned for correction: <remarks>". The page tells the engineer they cannot fix it.

Intended outcome: the engineer sees the return on the Timeline card, opens the report only (TSR locked, no new TSR revision), fixes it, saves, and it goes back to the approver as Pending.

## Decisions taken

1. Fix only the report, on the **same TSR submission**. No new TSR revision. The normal "Correct TSR" flow stays for real TSR mistakes.
2. Resubmit by putting the **same approval row** back to `Pending` (no new approval row, no schema change). The certificate number stays the same (owner confirmed at go-ahead).
3. Visibility: a red **"Returned"** tag and a **"Fix Calibration Report"** button label on the Timeline card; the approver's remarks shown prominently at the top of the Calibration Report box.
4. The rejected report file stays as history but is no longer the current report.

## Investigation

- Return route: `return_calibration_certificate` (`app.py:26236`) sets the approval `Returned`, notifies the requester with `target_url=url_for('offline_tsr_page', edit_submission_id=..., mode='correct')` (`app.py:26287`). That URL loads the full TSR for correction (`getOnlineTSRRevisionRequestFromUrl`, `templates/offline_tsr.html:5234`).
- One approval per TSR submission: `CalibrationCertificateApproval.online_tsr_submission_id` is `unique=True` (`app.py:3750`), and `submit_calibration_certificate_for_submission` (`app.py:25795`) returns the existing row as a duplicate (`app.py:25800`). This is why today the only way to resubmit is a new TSR revision.
- A report-only mode already exists: `mode=calibration_report&submission_id=X` (`getOnlineTSRCalibrationRequestFromUrl`, `templates/offline_tsr.html:5371`; context load around `:5440`, message "the original TSR will not be revised"). Timeline buttons open it via `redirectToCalibrationReportFromSchedule` (`templates/timeline.html:20750` sets `mode = 'calibration_report'`).
- Late upload path: `upload_online_tsr_attachment` (`app.py:26349`) with `late_calibration_report=1`. Blocks replacing an Approved report (`app.py:26400`) and any already-uploaded report (`calibration_report_already_uploaded`, `app.py:26459`). After the upload it calls `submit_calibration_certificate_for_submission` (`app.py:26505`), so resubmission already happens through the upload.
- Report state: server `calibration_report_state_for_submission` (`app.py:18183`, returns `uploaded` once a generated file exists); client `onlineTSRCalibrationReportState` (`templates/offline_tsr.html:5381`); read-only gate `setOnlineTSRCalibrationReportReadOnly` (`:5324`, called at `:5368` and from `static/js/app-calibration-report.js:1738`); toolbar hidden when uploaded and the "cannot be replaced" note (`app-calibration-report.js:1723`, `:1737`); returned text `:1731`.
- Timeline: `calibration_report_timeline_state_for_submission` (`app.py:18232`) already returns `approval_status`; it reaches the shift data (`app.py:52058`, `:52264`) but `templates/timeline.html` never reads `calibration_report_approval_status`. Label: `getCalibrationReportTimelineLabel` (`timeline.html:16313`); button renders at `:10672`, `:11129`, `:11915`, `:11971`, `:13215`, `:15267`.
- Not true: an earlier assumption that "the engineer gets a notification" — they do not see it anywhere (browser check above).

## Execution steps

1. **Notification link** — `app.py`, `return_calibration_certificate`: change `target_url` to `url_for('offline_tsr_page', submission_id=approval.online_tsr_submission_id, mode='calibration_report')`. Done when a new return notification points at report-only mode.
2. **Server: allow replacing a returned report** — `app.py`, `upload_online_tsr_attachment` late path (`:26458`): when `current_report_state == 'uploaded'` and the latest approval for the submission is `Returned` and `is_latest`, accept a new upload token and merge the payload with `merge_late_calibration_report_payload` instead of returning `calibration_report_already_uploaded`. Pending and Approved stay blocked. Done when a returned report accepts a new DOCX and a pending one still gets 409.
3. **Server: resubmit in place** — `app.py`, `submit_calibration_certificate_for_submission`: if the existing approval is `Returned` and `is_latest`, rebuild the unsigned certificate PDF, update `report_fingerprint`, `certificate_fingerprint`, `mapped_data_json`, `unsigned_artifact_path`, `submitted_at`, `updated_at`, set `status='Pending'`, clear `return_remarks`/`returned_at`/approver snapshot; for a temporary model, set its `CalibrationCertificateModel` back to Pending. Write a `resubmitted` universal audit entry (Returned → Pending) and notify approvers as on first submit. Keep `certificate_number`. Pending/Approved existing rows still return as duplicates. Done when the same approval id goes Returned → Pending with new fingerprints.
4. **Server: old file is history** — check how `calibration_certificate_generated_report_source_file` and `calibration_report_approval_map_for_files` (`app.py:25584`) pick the current report; make sure the replaced DOCX/PDF no longer appears as the current report on the schedule card or in client packages (it may remain in history). Done when only the new report shows as current.
5. **Server: state** — `calibration_report_state_for_submission`: unchanged (`uploaded`); the client decides editability from the approval status (step 6). Add `calibration_report_returned` (bool) and `calibration_report_return_remarks` to the Timeline shift data next to `calibration_report_approval_status` (`app.py:52058`, `:52264`).
6. **Create TSR page: returned report is editable** — `templates/offline_tsr.html` (`onlineTSRCalibrationReportState`, `setOnlineTSRCalibrationReportReadOnly` caller at `:5368`, status text at `:5469`) and `static/js/app-calibration-report.js` (`:1720`–`:1738`): when the certificate approval is `Returned`, treat the report as editable (Save Final Report, Clear, Generate Sample visible; no "cannot be replaced" note); TSR fields stay read-only as in report-only mode. Show a red banner at the top of the Calibration Report box: "Returned for correction by <approver>: <remarks>. Fix the report and Save Final Report to resubmit." Status tag "Returned" (red) instead of "Uploaded". Bump `app-calibration-report.js?v=46`. Done when the returned report can be edited and saved, and an approved/pending one stays read-only.
7. **Timeline card** — `templates/timeline.html`, `getCalibrationReportTimelineLabel`: return "Fix Calibration Report" when `calibration_report_approval_status === 'Returned'`; add a small red "Returned" tag on the card buttons listed in Investigation (desktop card and mobile views), with the remarks as the title. Done when a returned report's card reads "Fix Calibration Report" with the tag.
8. **Tests** — see Verification.

## Deliberately excluded

- No new notification bell/inbox page: a separate, larger feature; the Timeline card is where engineers already work.
- No email to the engineer on return (owner may ask later).
- No schema change, no dropping the unique constraint, no approval revision rows: in-place resubmit plus the audit trail keeps history.
- The `mode=correct` TSR correction flow is unchanged.
- Old unread `calibration_certificate` notifications are left as they are.

## Verification

- New tests (in `tests/test_calibration_certificate_approval_workflow.py` and `tests/test_tsr_sync_reliability.py`):
  - Return → notification `target_url` has `mode=calibration_report` and the submission id.
  - Returned report: late upload with a new token succeeds; approval keeps its id and certificate number, becomes `Pending`, fingerprints change, a `resubmitted` audit row exists; TSR submission count and `revision_no` unchanged.
  - Pending report: replacement still 409; Approved: still `calibration_report_approved_immutable` (existing tests stay green).
  - Timeline data includes `calibration_report_returned` / remarks for a returned report.
  - Template checks: "Fix Calibration Report" label and the Returned tag in `timeline.html`; returned banner text in `app-calibration-report.js`.
  - Positive control: run the new tests against the current code (in-process, never `git stash`) and confirm they fail.
- Focused modules: the two above plus `tests/test_tsr_calibration_report.py`, `tests/test_calibration_report_engineer_access.py`. Full suite once, before publishing.
- Browser (DB copy, temporary engineer + approver logins, removed afterwards): approver returns a report → engineer's Timeline card shows "Fix Calibration Report" + red tag → opens report-only page with red remarks banner, TSR fields locked → edit and Save Final Report → approver sees it Pending in Approvals with the same certificate number → TSR still the same REV. Approved report still read-only. 375px, no console errors.

## After implementation

1. Self-review; confirm every function the Create TSR and Timeline pages call is still defined and Save Final Report, Generate Sample, upload, approve and return still work.
2. Service worker `v283-calibration-fix-report` (v282 kept as a history marker); What's New release `2026-10-09-calibration-fix-report` ("Fix Returned Calibration Reports", engineers) in `static/changelog/releases.json`.
3. Update `changes.md` and this Status.
4. Wait for "commit and push"; stage only the intended files (never `scheduler.db`, handoffs, `changes-archive.md`, `.impeccable/`, `.claude/`, `output/`, `tmp/`); one `git ls-remote` check, no Railway polling.

## Risks

- **Approver approves a stale certificate:** resubmit rebuilds the unsigned PDF and fingerprints before status goes Pending; covered by tests.
- **Old report still shown as current or sent to the client:** step 4 plus the browser check.
- **Unlocking a Pending/Approved report by mistake:** server check is on the latest approval status `Returned` only; existing immutability tests stay.
- **Blast radius:** calibration report upload/resubmit path, Create TSR Calibration Report box, Timeline calibration button labels.

# Reimbursement Tracker "PAID" Batch Label

**Status:** Executed — published to `main` on 2026-10-09 on the owner's "commit and push" (commit `7d3642a`). Full suite before publishing: 1,665 tests, 14 failures (the known list), 3 errors that occur only alongside other test files, 5 skips, no new failures.

**Outcome (2026-10-09):** all 3 steps done as planned; service worker `v282-tracker-paid-batch`, release `2026-10-09-tracker-paid-batch`. Tests: 31 tracker tests OK; the new test and the updated equality fail on the previous code. Browser (DB copy, temporary login; removed): `BATCH-033 (Current)` / `BATCH-032 - PAID` with a mixed current batch; after saving the last unpaid row as paid via the edit form the label became `BATCH-033 (Current) - PAID` without a reload; switching to BATCH-032 shows its two rows; 375px no horizontal scroll (select 286px). Console: only the 400s from the check's own first seeding calls sent without a CSRF token; none from the page.
**Approved:** 2026-10-09 (owner: "if the whole batch is paid in full, let's show an indicator on the dropdown like BATCH-033 - PAID. create a plan", then "approved. go" — approval and go-ahead in one message).
**Detailed:** 2026-10-09.
**Branch:** `main` (local first; nothing is pushed until a separate "commit and push").

## Context

The View Batch dropdown on the Reimbursement Tracker lists every batch, with " (Current)" on the active one. The owner wants to see at a glance which batches are fully paid: `BATCH-033 - PAID`, `BATCH-036 (Current) - PAID`.

## Decisions taken

1. Fully paid = the batch has at least one row and every row has `paid_in_full`. An empty batch (a freshly started current batch) never shows PAID.
2. Plain text suffix ` - PAID` in the `<option>` label; native options cannot carry a reliable badge or colour.

## Investigation

- Dropdown: `renderBatchOptions()` in `templates/reimbursement_tracker.html:364` builds options from `state.availableBatches` and adds ` (Current)`.
- Batch list: `reimbursement_tracker_available_batches()` in `app.py:56314` returns `{sequence, reference}` only (distinct `batch_sequence` query), so the page cannot know paid state of non-viewed batches.
- Row paid flag: `ReimbursementTrackerEntry.paid_in_full` (boolean, `app.py:2217`).
- After saving a row the page calls `loadData(state.viewBatch?.sequence)` (`reimbursement_tracker.html:756`, `:776`), which re-renders the dropdown, so the label updates without new client code.
- `tests/test_reimbursement_tracker.py:495` asserts `available_batches` by exact equality and must include the new key.

## Execution steps

1. `app.py`, `reimbursement_tracker_available_batches()`: replace the distinct query with one grouped query (`batch_sequence`, row count, paid count); each batch gains `paid_in_full` = count > 0 and paid count == count; the current batch is always listed (`False` when empty). Done when `/get_reimbursement_tracker_entries` returns `paid_in_full` per batch.
2. `templates/reimbursement_tracker.html`, `renderBatchOptions()`: append `' - PAID'` when `batch.paid_in_full`. Done when fully paid batches show the suffix.
3. `tests/test_reimbursement_tracker.py`: update the line-495 equality; new test for all paid → `True`, mixed → `False`, empty current → `False`; template check for `' - PAID'` and `batch.paid_in_full`. Positive control: new checks fail on the current code.

## Deliberately excluded

- No filter, colour or badge (text indicator only was asked).
- No schema change; paid state is derived from existing rows.
- Exports unchanged.

## Verification

- Focused: `tests/test_reimbursement_tracker.py`. Full suite once, before publishing.
- Browser (DB copy, temporary login removed afterwards): PAID only on fully paid batches; untick one row's Paid in full → PAID disappears after save, tick again → returns; batch switching still works; " (Current)" still shown; 375px; no console errors.

## After implementation

1. Self-review; confirm every function the tracker page calls is still defined (save, add, export, start batch).
2. Service worker `v282-tracker-paid-batch` (v281 kept as a history marker); release `2026-10-09-tracker-paid-batch` in `static/changelog/releases.json` (Reimbursement Tracker, admins).
3. Update `changes.md` and this Status.
4. Wait for "commit and push"; stage only the intended files (never `scheduler.db`, handoffs, `changes-archive.md`, `.impeccable/`, `.claude/`, `output/`, `tmp/`); one `git ls-remote` check, no Railway polling.

## Risks

- **Wrong PAID on a mixed batch:** covered by the new test.
- **Query cost:** one grouped count over the tracker table (small).
- **Blast radius:** the tracker's batch dropdown only.

# Activity Log Category Chip Opens the Record

**Status:** Executed — published to `main` on 2026-10-08 on the owner's "commit and push" (commit "feat(activity): category chip opens the record"). Owner confirmed decision 1 (recommended option) and said "go". Full suite before publishing: 1,656 tests, 14 failures (the known list), 0 errors, 4 skips, no new failures.

**Outcome (2026-10-08):** all 5 steps done as planned; service worker `v277-activity-chip-open` (v276 kept as a history marker), release `2026-10-08-activity-chip-open`. Step 1 went slightly further than written: the per-type lookups moved into `ACTIVITY_RECORD_LOOKUPS` and the field builders into `_activity_record_fields`, so `activity_record_summary` and `activity_row_link` share one lookup (summaries unchanged; all earlier tests pass). The row click handler now ignores links as well as buttons, so a link chip does not also open the details panel. Tests: new list test plus template/release checks (29 Activity Log tests OK; 3 fail on the published code `778130c`). Browser (DB copy, temporary logins; copy and launch change removed), 1366x768: as Robert every chip on the `TR-20260609-7` search is a link with the arrow icon (`/approvals?module=travel_request&id=7`; the liquidation entry links its first code `TL-20260611-3`) and clicking it does not open the panel; as Diary the same chips are buttons that show the toast "Only the assigned approver can open this record." without navigating; a "Modified details for client" row's chip still filters (Category set to Client). 375px: no horizontal scroll. No console errors. Existing chip tap size (about 22px) unchanged; not part of this plan.
**Approved:** 2026-10-08 (owner: "can we make this label when clicked. automatically goes to the linked activity? if possible. show the error if user cannot do that. create a plan"). Under the two-step rule this records approval only; execution needs a separate "go" / "execute" / "start".
**Detailed:** 2026-10-08.
**Branch:** `main` (local first; nothing is pushed until a separate "commit and push").

## Context

In the Activity Log table, the "What" column's category chip (e.g. "Leave Request") filters the list by that category when clicked. The owner wants a click on it to go straight to the record the entry is about, the same place as the details panel's "Open in Approvals" / "Show in Timeline" button (published `778130c`), and to show an error when the viewer cannot open it.

## Decisions taken

1. **Which chips change** (recommended; owner to confirm): only rows whose entry names a record with a summary (TR, CA, TL, CAL, LR, `schedule #N`, `reimbursement #N`; about 10% of entries) get the open behaviour. All other rows keep today's "filter by this category" click, so that feature is not lost; filtering by category also stays available from the Category dropdown. The chip's tooltip says which it does ("Open Leave Request LR-… in Approvals" vs "Show only Leave Request").
2. **When the viewer cannot open it**, the click shows a short message in a small toast at the bottom of the page, and nothing else happens: "Only the assigned approver can open this record." (approval types) or "This record no longer exists." (code no longer found). Same permission rule as the panel button; nobody's access changes.
3. **Link worked out with the list, not on click:** `/get_activity_logs` returns each row's `open_url` / `open_state`, so the chip is a real link opening in a new tab. Fetching on click and then opening a tab can be blocked as a pop-up.
4. **Which record:** the entry's first record code (e.g. `CAL-…` for "Created CAL-… for CA-…").

## Investigation

- Chip markup: `renderRow` in [activity.html:323](templates/activity.html:323), `<button class="activity-chip activity-tone-…" onclick="filterBy('filter-type', …)">`; the table click handler ignores buttons other than `.activity-detail-link`, so the chip does not open the panel. `filterBy` is also used by the Who chip, so it stays.
- The 2026-10-03 release told admins "Click a person or category to filter by it" ([releases.json](static/changelog/releases.json), `2026-10-03-activity-log-simple`); decision 1 keeps that true for rows without a record.
- `activity_record_summary(reference)` ([app.py](app.py)) finds the record and builds `open_url` with `_activity_record_open_link(kind, record)`, which uses the target routes' own checks. Building full summaries for every row would add several queries per row; a lighter lookup is needed (step 1).
- `/get_activity_logs` serializes rows with `activity_log_to_dict`, which is also used by the related route; the new keys are added only in `get_activity_logs`. Pages hold 25–100 rows; about 10% name a record (2026-10-08 count: 208 of 2,194).
- No shared toast exists in `layout.html`; `products.html` and `engineers.html` use page-local Bootstrap toasts.

## Execution steps

1. **Record lookup split** (`app.py`): new `_activity_find_record(reference)` returning `(kind, record, label)` or `None` (the lookup part of `activity_record_summary`, which then calls it; behaviour unchanged). New `activity_row_link(action)`: first reference → `_activity_find_record` → `{'open_url', 'open_label', 'open_state': 'open' | 'denied' | 'missing', 'record_label'}`, or `None` when the entry has no reference with a summary type. Done: summaries and `/get_activity_log_related` output unchanged.
2. **List response** (`app.py` `get_activity_logs`): each row dict gains `record_link` from `activity_row_link(log.action)`. Done: rows without a code have `record_link: null`.
3. **Chip** (`templates/activity.html` `renderRow`): when `record_link.open_state === 'open'`, the chip is `<a class="activity-chip …" href="…" target="_blank" rel="noopener">` with an external-link icon and the tooltip "Open <label> in Approvals/Timeline"; when `denied` or `missing`, a `<button>` that calls new `showActivityToast(message)`; when `record_link` is null, today's filter button unchanged. Same-site paths only, via `escapeHtml`. Done: Who chip, Details button and panel still work.
4. **Toast** (`templates/activity.html`): one Bootstrap toast container (`#activity-toast`, `role="status"`, `aria-live="polite"`) at the bottom; `showActivityToast` sets the text and shows it for 4 s.
5. **Release**: bump `CACHE_VERSION` (v276 kept as a history marker); release entry "Open Records from the Category Label" (Activity Log, admins).

## Deliberately excluded

- **Changing the Who chip:** not asked.
- **Opening records for entries without a record code:** nothing to open.
- **A chip that both filters and opens** (e.g. separate icon): the owner asked for the label itself.

## Verification

- `tests/test_activity_log_details.py`: `activity_row_link` gives `open` with the Approvals URL when the checks pass, `denied` when they fail, `missing` for an unknown code, `None` for an entry without a code; `/get_activity_logs` rows carry `record_link`; template has `showActivityToast`, `#activity-toast`, both messages, and still `filterBy('filter-type'`. Positive control: fail on the current code.
- Focused: `test_activity_log_details`, `test_activity_log_hardening`.
- Browser (DB copy, temporary logins removed afterwards): as the approver, a TR row's chip opens the TR in Approvals in a new tab; as a non-approver, the chip shows the toast and does not navigate; a schedule row's chip goes to Timeline; a row without a code still filters by category; the Who chip and the details panel unchanged; 375px; no console errors.
- Full suite once, before publishing.

## After implementation

1. Self-review; confirm every function the Activity Log page calls is still defined.
2. Update `changes.md` and this Status.
3. Wait for "commit and push"; stage only the intended files (never `scheduler.db`, handoffs, `changes-archive.md`, `.impeccable/`, `.claude/`, `output/`, `tmp/`); one `git ls-remote` check, no Railway polling.

## Risks

- **Mixed chip behaviour:** some chips open, others filter (decision 1); the icon and tooltip mark the difference.
- **List speed:** extra lookups only for rows with a code (about 1 in 10), at most 100 rows per page.
- **Blast radius:** Activity Log list only; the details panel, Approvals and Timeline are unchanged.

# Activity Log "Open Record" Button

**Status:** Executed — published to `main` on 2026-10-08 on the owner's "commit and push" (commit "feat(activity): open record button, rejection reasons, leave requests"), with Amendment 1. Owner confirmed decision 1 (recommended option) and said "go". Full suite before publishing: 1,655 tests, 14 failures (the known list), 0 errors, 4 skips, no new failures.

**Outcome (2026-10-08):** all 3 steps done as planned; service worker `v276-activity-open-record` (v275 kept as a history marker), release `2026-10-08-activity-open-record`. Tests: 2 new plus 2 extended in `tests/test_activity_log_details.py`; 26 Activity Log tests OK; on the committed code (`01ea7e8`) the 4 new checks fail. Browser (DB copy, temporary logins on the copy; copy and launch change removed): as Robert (assigned approver for the requester) the `TR-20260609-7` card shows "Open in Approvals" → `/approvals?module=travel_request&id=7`, `target=_blank`, `rel=noopener`; that URL loads `/get_travel_request_approval/7` (200) and shows the request's summary (Jonamar Paunil, Client Visit, Liquidation Completed, PHP 15,000.00, June 19–20, Manila → Davao) in the Approvals detail view; as Diary (not the approver) the card shows "Only the assigned approver can open this record." and no button; schedule #876 shows "Show in Timeline" → `/timeline?date=2026-06-04` (200). 375x812: button 44px, no horizontal scroll. No console errors on either page.
**Approved:** 2026-10-08 (owner: "okay. plan it now", after "then we will plan the button afterwards"). Under the two-step rule this records approval only; execution needs a separate "go" / "execute" / "start".
**Detailed:** 2026-10-08.
**Branch:** `main` (local first; nothing is pushed until a separate "commit and push").

## Amendment 1 — Rejection reason and Leave Requests (2026-10-08)

**Status:** Executed — published to `main` on 2026-10-08 with the base plan. Owner: "rejected requests doesn't show the reason why its rejected", then showed a Leave Request rejection (`LR-20261008-03`) with no record card, reason or approver.

- **Source of the reason:** `UniversalApprovalAuditTrail` (module, record_id, action `rejected` / `returned` / `liquidation_returned`, `remarks`, `actor_display_name`), written by every reject/return route. The record's own `approval_remarks` is not used because a resubmission or later approval overwrites it (e.g. `CA-20260616-1` was rejected twice, then approved).
- `app.py`: new `activity_decision_reason(log, records)`: only for entries whose text contains "rejected" or "returned"; for each record card, the audit event of that record nearest the entry's time within 5 minutes; returns `{decision, reason, by}`; `/get_activity_log_related` returns it as `decision`; summaries gain `record_id`; new `ACTIVITY_AUDIT_MODULE_BY_KIND`.
- **Leave Request** (`LR-…`, `LeaveRequest.request_no`) added as a record type: requester, leave type, dates with weekday count, half / one-and-a-half day, status. The employee's own leave `reason` is left out (can hold health details). Open link `/approvals?module=leave_request&id=…` gated by the leave module's own `can_approve`, now exported from `leave_feature.py` as `can_approve_leave_request` (no logic change).
- `templates/activity.html`: `renderActivityDetail(log, decision)` adds "Rejected reason" / "Rejected by" (or "Returned …") rows to the entry fields.
- **Outcome:** 2 new tests plus template checks (28 Activity Log tests OK; the new ones fail without the change); leave module tests OK. On the database copy every rejection/return entry with an audit event resolves its own reason (the two rejections of `CA-20260616-1` give "edit purpose" and "confim amount"); one older `reimbursement #2` entry has no audit event and shows no reason. Browser: the CA rejection shows "Rejected reason" and "Rejected by Rodito Aretano Jr"; no console errors. No local leave rejection exists, so the Leave Request path is covered by tests only.

 shows a "Current record" card for Travel Requests, Cash Advances, Travel and Cash Advance Liquidations, schedules and reimbursements, but no way to jump to the record. This plan adds an Open button on each card that goes to the page where that record can be viewed in full.

## Decisions taken

1. **The button appears only when the viewer can actually open the record** (recommended; owner to confirm). The full views of TR/CA/TL/CAL/reimbursement live in the Approvals page detail modals, and their detail routes allow only the record's **assigned approver** (see Investigation). The server works out each button with the same permission functions those routes use, so the button never leads to a "not assigned to you" error. When it cannot be opened, the card shows a quiet note: "Only the assigned approver can open this record." No permissions change. *The alternative, letting every Activity Log admin open any record in Approvals, would widen who sees requests, amounts and attachments; it is not planned.*
2. **Targets:** TR → `/approvals?module=travel_request&id=<id>`; CA → `module=cash_advance`; TL → `module=travel_liquidation`; CAL → `module=cash_advance_liquidation`; reimbursement #N → `module=reimbursement`; schedule #N → `/timeline?date=<start date>` labelled "Show in Timeline" (Timeline jumps to that day; it cannot open one schedule).
3. **Opens in a new tab** (`target="_blank" rel="noopener"`), so the Activity Log keeps its place and panel.

## Investigation

- Approvals deep link: `approvalQueueOpenDeepLink` ([approvals.html:6757](templates/approvals.html:6757)) reads `?module=` and `?id=` and calls the opener: `travel_request` → `openTravelApprovalDetail`, `cash_advance`, `cash_advance_liquidation`, `travel_liquidation`, `reimbursement` (also `lpr`, `leave_request`, `calibration_certificate`). Ids are database ids, not request numbers.
- Page access: `/approvals` requires `is_approval_center_user()` ([app.py:8671](app.py:8671)). Detail routes and their checks: `/get_travel_request_approval/<id>` → `can_user_review_travel_request(current_user, rec)` ([app.py:42537](app.py:42537)); `/get_cash_advance_approval/<id>` → `require_approval_center_user()` then `can_user_approve_cash_advance(current_user, h) or can_user_access_cash_advance(h)`; `/get_travel_liquidation_approval/<id>` → `require_approval_center_user()` + `can_user_approve_travel_liquidation` ([app.py:11352](app.py:11352)); `/get_cash_advance_liquidation_approval/<id>` → `require_approval_center_user()` + `can_user_approve_cash_advance_liquidation`; `/get_reimbursement_approval/<id>` → `reimbursement_is_approver_user()` + `can_user_approve_reimbursement_header` ([app.py:11335](app.py:11335)).
- These checks depend on the requester's approval routing, **not on status**, so approved/closed records open too.
- Activity Log viewers (`is_admin_authorized`) are named superadmins (developer, managers, schedulers) and the regional admin; only those configured as approvers (or the legacy reimbursement approver) will see buttons, and only for requesters routed to them. Schedulers will mostly see the note.
- Owner pages (`/travel_request?id=`, `/cash_advance`, …) open only the user's own records, so they are not used.
- Timeline: `/timeline` requires `can_access_timeline_page()`; `?date=YYYY-MM-DD` (also `week`, `target_date`) jumps to that date ([timeline.html:14178](templates/timeline.html:14178)).
- `activity_record_summary` ([app.py](app.py), beside `extract_activity_references`) already loads each record; adding the URL there costs no extra query beyond the permission helpers.

## Execution steps

1. **Server** (`app.py`, `activity_record_summary`): after building fields, add `open_url` and `open_label` (or `None`) using new `_activity_record_open_url(kind, record)`, which returns the URL only when the exact checks of the target route pass for `current_user` (TR: `is_approval_center_user()` and `can_user_review_travel_request`; CA: `is_approval_center_user()` and (`can_user_approve_cash_advance` or `can_user_access_cash_advance`); TL: `is_approval_center_user()` and `can_user_approve_travel_liquidation`; CAL: `is_approval_center_user()` and `can_user_approve_cash_advance_liquidation`; reimbursement: `is_approval_center_user()` and `reimbursement_is_approver_user()` and `can_user_approve_reimbursement_header`; schedule: `can_access_timeline_page()`, date from `start_time`). Labels: "Open in Approvals", "Show in Timeline". Done: summaries unchanged otherwise; `/get_activity_log_related` returns the new keys.
2. **Page** (`templates/activity.html`, `renderActivityRecords`): when `open_url` is set, an `<a class="btn btn-sm btn-outline-primary mt-2" target="_blank" rel="noopener">` with an external-link icon and `open_label` (URL through `escapeHtml`; only same-site paths starting with `/` are rendered); otherwise, for approval types, the muted note. 44px tall at ≤900px. Done: cards without a URL look as before plus the note.
3. **Release**: bump `CACHE_VERSION` (keep v275 as a history marker); release entry "Open Records from the Activity Log" (Activity Log, admins).

## Deliberately excluded

- **Widening Approvals access for Activity Log admins:** a permission change; only if the owner chooses it instead of decision 1.
- **Opening a single schedule:** Timeline has no per-schedule deep link; adding one is separate work.
- **Buttons for codes without a summary** (`submission`, `route`, `visit`): no record card exists for them.

## Verification

- `tests/test_activity_log_details.py`: with the permission helpers patched to allow, the TR summary has `open_url == '/approvals?module=travel_request&id=<id>'`; patched to deny, `open_url` is `None`; schedule summary links `/timeline?date=YYYY-MM-DD`; template renders the link with `target="_blank"` and the note text. Positive control: these fail on the current code.
- Focused: `test_activity_log_details`, `test_activity_log_hardening`.
- Browser (DB copy, temporary login removed afterwards): as an approver (e.g. a manager account on the copy) open a TR entry → "Open in Approvals" opens the TR detail modal in a new tab; as a scheduler account → the note, no button; a schedule entry → Timeline at that day; 375px; no console errors.
- Full suite once, before publishing.

## After implementation

1. Self-review; confirm every function the Activity Log and Approvals pages call is still defined.
2. Update `changes.md` and this Status.
3. Wait for "commit and push"; stage only the intended files (never `scheduler.db`, handoffs, `changes-archive.md`, `.impeccable/`, `.claude/`, `output/`, `tmp/`); one `git ls-remote` check, no Railway polling.

## Risks

- **Few buttons for some admins:** by design (decision 1); the note explains why.
- **Permission drift:** if a detail route's check changes later, the button rule must change with it; the helper names the same functions so a search finds both.
- **Blast radius:** Activity Log panel only; Approvals and Timeline unchanged.

# Activity Log Entry Details Panel

**Status:** Executed — published to `main` on 2026-10-08 on the owner's "commit and push" (commit "feat(activity): entry details panel with current record summary"), together with Amendment 1. Owner said "go" on 2026-10-08. Full suite before publishing: 1,651 tests, 14 failures (the known list), 0 errors, 4 skips, no new failures.

**Outcome (2026-10-08):** all 7 steps done as planned; service worker `v275-activity-details`. Tests: new `tests/test_activity_log_details.py` (10 tests) plus `test_activity_log_hardening` (12) OK; on the committed code 8 of the 10 fail — the two that pass are the 404 cases, which also return 404 there because the route does not exist yet. Browser (DB copy, temporary login on the copy; copy and launch change removed), 1366x768: a `TR-20260609-11` entry shows "Same record · TR-20260609-11" with its 5 sibling entries (cash advance received, sent to Accounting, approved, travel block days, submitted); a calendar schedule entry splits into Client, Product, Engineer(s) and Branch rows; a client edit with no code shows "Same person, around this time"; the Who chip still filters with the panel open; Close returns focus to the row's Details button and clears the highlight; Export CSV returns 200 text/csv. 375x812: bottom sheet at y 122, 690px tall (85vh), no horizontal scroll, no button under 44px. No console errors. Where it differed: nothing; the pane's paused CSS transitions left the sheet mid-slide until transitions were turned off for measuring (known pane quirk, not a page bug).
**Approved:** 2026-10-08 (owner: "okay approved. build 1 and 3 first. create the plan"). Under the two-step rule this records approval only; execution needs a separate "go" / "execute" / "start".
**Detailed:** 2026-10-08.
**Branch:** `main` (local first; nothing is pushed until a separate "commit and push").

## Amendment 1 — Current record summary (2026-10-08)

**Status:** Executed — published to `main` on 2026-10-08 with the base plan. Owner reviewed the panel and said the summary was lacking ("travel to where? who did i approve? when is the travel date?"); the proposal below was answered with "go", taken as approval and go-ahead together. "Open record" button not included (recommended default; owner did not ask for it).

**What:** for each record code in the opened entry, the panel shows a "Current record" card with the record's live fields, labelled as current (not as it was when the entry was written).

| Code | Fields |
| --- | --- |
| `TR-…` (`TravelRequest.request_no`) | Requester, type, purpose, route (from → to legs, else destination), client, departure – return dates, requested / approved amount, status |
| `CA-…` (`CashAdvanceHeader.cash_advance_no`) | Requester, purpose, date needed, requested / approved amount, status |
| `TL-…` (`TravelLiquidationHeader.liquidation_no`) / `CAL-…` (`CashAdvanceLiquidationHeader.liquidation_no`) | Requester, liquidates (TR / CA number), cash advance, actual expenses, due to Shimadzu / employee, status |
| `schedule #N` (`Shift.id`) | Title, client, product, engineer(s) (main plus `ShiftEngineer`), start – end, status |
| `reimbursement #N` (`ReimbursementHeader.id`) | Requester, period, total (sum of `ReimbursementRow.row_total`), status |

**Excluded:** account number, health condition, signatures, remarks, payment references; `submission`, `route`, `visit` references (no summary); Open-record buttons (later).

**Steps:**
1. `app.py`: new `activity_record_summary(reference)` returning `{'reference', 'kind', 'fields': [[label, value], ...]}` or `None` when the record does not exist, with one small builder per type; empty values skipped. Done: unit-tested per type with test rows.
2. `app.py` `get_activity_log_related`: response gains `records` (summaries for the entry's references, non-missing only). Scope unchanged (the entry itself is already scope-checked).
3. `templates/activity.html`: `renderActivityRecords(records)` renders a "Current record · <code>" card per record into new `#activity-detail-records` between the entry and the related list; cleared on each open.
4. Tests in `tests/test_activity_log_details.py`: TR summary has requester, route, dates, amounts, status; missing code gives no record; template wiring. Positive control on the pre-amendment code.
5. Browser check on a DB copy (TR, CA, schedule entry), 375 px, console; update release text, `changes.md`, this status.

**Outcome:** done as planned, with three changes found against real data. (a) The stored Travel Request `purpose` is a generated block of route/visit text, so it is not shown; the card shows `Visits` (client – product – purpose tags per route visit) and, for Training/Meeting requests, Training / Conducted by / Venue / Meeting / Meeting with taken from the columns or, for older requests, from the "Label: value" lines in `purpose` (the same fallback as the Approvals page; only those labels are read, so account number and health lines never appear). `Client` is dropped when visits exist or when it only repeats the type. (b) Each summary carries a `label` ("Travel Request TR-…", "Schedule #876") because "Schedule schedule #876" read badly. (c) A CAL entry also names its CA, so it shows two cards (the liquidation and the cash advance). Tests: 4 new (24 in the two modules OK); with the `records` line and the template call removed, 4 fail. Browser (DB copy; removed afterwards): `TR-20260609-7` approval entry shows requester, Manila → Davao, the DDH visit, Jun 19 – Jun 20, 2026, PHP 15,000.00 requested / approved, Liquidation Completed; schedule #876 and CAL-20261004-3 cards correct; 375 px no horizontal scroll, no button under 44px; no console errors.

## Context

On the Activity Log (`/activity_page`) a row shows a one-line, sometimes shortened entry, and clicking it does nothing. Admins reviewing the log want to open an entry and see what it was about. This plan adds a details panel: click a row and a panel opens beside the list (a sheet from the bottom on phones) with the full entry split into readable fields and the other entries about the same record.

## Decisions taken

1. **Side panel, not a centered modal.** The panel slides in from the right on desktop and leaves the list visible and clickable, so clicking another row just updates it. At ≤900px it opens as a bottom sheet.
2. **Parts 1 and 3 of the proposal only:**
   - **(1) Full entry, split into fields:** the headline (text before the first " | "), each "Label: value" segment as a labeled row (Client, Product, Engineer(s), …), the full original text when the display text was shortened, the exact date and time, the user, the category, the action type, the branch and the severity.
   - **(3) Related activity:** other entries that mention the same record code (e.g. `TR-20260609-11`, `CA-…`, `TL-…`, `CAL-…`, `schedule #876`, `reimbursement #45`, `submission #34`), newest first.
3. **Fallback when an entry has no record code:** the panel shows "Same person, around this time" instead: the same user's entries within 30 minutes either side, routine entries left out. Added while detailing because only about 10% of entries carry a code (see Investigation), so without it the related section would be empty for most rows. **The owner may strike this before the go-ahead.**
4. Part 2 (Open buttons to the record, live status) comes later as its own plan.

## Investigation

- `ActivityLog` ([app.py:1842](app.py:1842)) has only `id`, `user`, `action` (String(255), but SQLite does not enforce it; the longest stored entry is 453 characters) and `timestamp`. There is no record id, link, or before/after data, so everything in the panel comes from the text.
- In the current database copy (2,194 entries): date-coded codes `TR` 81, `CA` 33, `TL` 22, `CAL` 18 (pattern `[A-Z]{2,4}-\d{8}-\d+`); "word #N" references `schedule` 28, `reimbursement` 24, `submission` 9, `route` 4, `visit` 1. **1,986 entries (≈90%) have no reference.** That led to decision 3. `ZEN-119003-10824` is an equipment serial (`Added equipment: …`), not a request code, and the date-coded pattern does not match it.
- Long schedule entries use " | " separators with "Label: value" segments, e.g. `Added calendar schedule: … on 2026-06-05 | Client: … | Product: … | Engineer(s): …`.
- `activity_log_to_dict` ([app.py:32801](app.py:32801)) returns `id`, `user`, `action`, `display_action`, `type`, `action_type`, `severity`, `branch`, `date` (Today / Yesterday / "Oct 4, 2026") and `time`; there is no full timestamp.
- Access: `/activity_page`, `/get_activity_logs` and `/get_activity_filter_options` require `is_admin_authorized()` ([app.py:11603](app.py:11603)). `activity_scope_query` ([app.py:32841](app.py:32841)) limits the regional admin to Cebu/Davao/own entries; the new route must apply it both to the opened entry and to the related list.
- `activity_routine_expression()` marks legacy reimbursement autosaves and theme changes as routine.
- `templates/activity.html`: `renderRow(log)` builds the rows; the Who and What chips are `<button>`s that call `filterBy(...)`, so a row click must ignore clicks on buttons. Rows are rebuilt from `data.logs` on every `loadLogs`.
- Bootstrap 5.3.0 bundle is loaded in `layout.html` (offcanvas available); no template uses offcanvas yet.
- Service worker `CACHE_VERSION` is in `app.py` (~line 27196), currently `v274-shell-phone-menu`. The previous Activity Log release (`2026-10-03-activity-log-simple`) used category "Activity Log", audience `admins`.

## Execution steps

1. **Full timestamp in the row data** (`app.py` `activity_log_to_dict`): add `'timestamp': stamp.strftime('%Y-%m-%d %H:%M:%S')`. Done: existing keys unchanged; `/get_activity_logs` rows carry it.
2. **Reference finder** (`app.py`, beside `clean_activity_display_action`): new `extract_activity_references(action)` returning a de-duplicated list in order of appearance of date-coded codes (`\b[A-Z]{2,4}-\d{8}-\d+\b`) and "word #N" references for the words schedule, reimbursement, submission, route, visit (normalized to lower-case word, e.g. `schedule #876`). Done: returns `['TR-20260609-11']` for "Marked Travel Request ready for liquidation: TR-20260609-11", `['CAL-20261004-3', 'CA-20260616-1']` for the CAL draft entry, `[]` for "Added equipment: ZEN-119003-10824".
3. **Related route** (`app.py`, after `get_activity_logs`): `GET /get_activity_log_related/<int:log_id>`, `@login_required`, `denied()` unless `is_admin_authorized()`. Load the entry through `activity_scope_query(ActivityLog.query)`; 404 JSON if missing or out of scope. If it has references: entries whose `action` `ilike`s any reference (scoped, excluding itself), then post-filtered in Python with a word-boundary regex so `schedule #87` does not match `#876`; newest first, at most 20. Otherwise: same `user`, `timestamp` within ±30 minutes, not routine, excluding itself, newest first, at most 20. Response: `{'log': dict, 'references': [...], 'related_by': 'reference' | 'nearby', 'related': [dicts]}`. Done: route returns 200 for an admin, 403 for an engineer, 404 for an out-of-scope id as the regional admin.
4. **Panel markup** (`templates/activity.html`): an `offcanvas offcanvas-end activity-detail-panel` (`id="activity-detail"`, `data-bs-backdrop="false"`, `data-bs-scroll="true"`, `aria-labelledby="activity-detail-title"`) with header (title, close button) and body sections: headline + category chip, a `<dl>` of fields, the original text (only when different), and "Same record" / "Same person, around this time" with a list `#activity-detail-related`. Done: hidden on load; nothing else on the page moves.
5. **Panel script** (`templates/activity.html`): keep `activityLogsById` (filled in `loadLogs`); new `parseActivityFields(text)` (split on " | ", "Label: value" → field rows, the rest → headline); new `openActivityDetail(id)` renders the row data at once, marks the row `.is-selected`, then fetches the related route (spinner while loading, message plus Retry on error; a later click aborts the earlier fetch like `loadLogs` does); related items show time, user and display text, and clicking one opens it in the panel. `renderRow` gets `data-log-id`, and the Details text becomes a `<button type="button" class="activity-detail-link">` for keyboard users; a delegated click on `#activity-table-body` opens the row unless the click was on another button (the chips keep filtering). Escape and the close button close it; focus returns to the row's Details button. All text through `escapeHtml`. Done: `loadLogs`, `filterBy`, `exportLogs`, `resetFilters`, `changePage` and the chips work as before.
6. **Styles** (`templates/activity.html` `<style>`): panel width 420px; selected row highlight; at ≤900px the panel becomes a bottom sheet (full width, max-height 85vh, rounded top, slides up) with 44px tap targets. Done: no horizontal scroll at 375px.
7. **Release**: bump `CACHE_VERSION` in `app.py` (old value kept as a history comment, following the existing pattern); `static/changelog/releases.json` entry "Activity Log Details" (category "Activity Log", audience `admins`): click an entry to see it in full and the other entries about the same record.

## Deliberately excluded

- **Open buttons and live record status (part 2):** needs a per-type mapping from codes to pages and records; a later plan.
- **Before/after values:** not stored; would mean changing every logging call.
- **Schema change or storing record ids on new entries:** not needed for parts 1 and 3.
- **Matching by client or product name:** names are free text and repeat across unrelated work, so results would be noisy.
- **Changes to CSV export or filters:** not asked for.

## Verification

- New `tests/test_activity_log_details.py`:
  - `extract_activity_references` on the examples in step 2, plus `reimbursement #45`, and no match for an equipment serial.
  - Route with an in-memory/test database: a TR entry returns its sibling TR entries and not an entry for a different TR; `schedule #87` does not pull `schedule #876`; an entry with no code returns the same user's entries within 30 minutes and not routine ones or other users'; engineer gets 403; regional admin gets 404 for a Manila-only entry by another user; missing id 404.
  - Template: `activity-detail` panel, `openActivityDetail`, `/get_activity_log_related/` and `data-log-id` present; the existing functions (`loadLogs`, `filterBy`, `exportLogs`, `resetFilters`, `changePage`, `renderRow`) still defined.
  - Release entry exists and the cache marker is bumped.
  - Positive control: run the new module on the current code first; every test must fail.
- Focused existing module: `tests/test_activity_log_hardening.py` (update its release/cache test only if it pins the old marker).
- Browser (copy of `scheduler.db`, temporary admin, both removed afterwards): 1366x768 click a TR entry → fields and the same-record history; click a schedule entry → Client/Product/Engineer rows; click an entry with no code → "Same person, around this time"; click another row with the panel open → it updates; click a related item → it opens; chips still filter; Escape closes and focus returns; Export CSV still downloads. 375x812: bottom sheet, no horizontal scroll, 44px targets. No console errors.
- Full suite once, before publishing: `venv/Scripts/python.exe scripts/run_suite.py`.

## After implementation

1. Self-review the diff; confirm every function the page calls is still defined and Refresh, Export CSV, filters, paging and chips work.
2. Update `changes.md`, and this plan's Status (amend here if the outcome differed).
3. Wait for "commit and push"; stage only the intended files (`app.py`, `templates/activity.html`, `static/changelog/releases.json`, the new test, `plans.md`, `changes.md`; never `scheduler.db`, handoffs, `changes-archive.md`, `.impeccable/`, `.claude/`, `output/`, `tmp/`); verify `git ls-remote origin refs/heads/main` and Railway's deployment status.

## Risks

- **Text-based matching:** a code typed into another entry's free text links them; acceptable, since it is still about that record.
- **Query cost:** `ilike '%…%'` scans `activity_log` (≈2,200 rows now); fine at this size, capped at 20 results.
- **Scope leak:** the regional admin must not see out-of-scope entries through the related list; covered by applying `activity_scope_query` to both queries and by a test.
- **Blast radius:** the Activity Log page and one new read-only route; no schema change, no logging change.

# Add a Vieworks Item from the Product Form

**Status:** Executed — published to `main` on 2026-10-08 on the owner's "commit and push" (commit "feat(products): add a Vieworks item from the Product form"). Owner said "go" on 2026-10-08. Full suite before publishing: 1,631 tests, 14 failures (the known list), 0 errors, 4 skips, no new failures.

**Outcome (2026-10-08):** all 3 steps done as planned. Where it differed: `main` had moved to service worker v271 (two shell commits), so this is `v272-product-new-vieworks`. The end-to-end test passes on the old code too, as expected (server unchanged; it guards the existing create-then-link flow); the two template tests fail on the committed file. Focused modules OK (new module 3, `test_product_vieworks_links_history` 6, `test_vieworks_inventory` 13, `test_vieworks_parent_link` 6, `test_product_inventory_batch1` 8, `test_product_inventory_batch3` 4). Browser (DB copy, temporary admin; copy, account and launch change removed), 1366x768: button disabled with no center (also with the switch on); after choosing a center it opens the panel with focus on Serial; Add created `ZZ-PNV-01` (BSID V-000001) and selected it in the link list; a duplicate serial showed "Serial number ... already exists in Vieworks inventory." inline and kept the typed value; saving the machine linked it, and the Vieworks page shows the item linked with the machine's room and warranty dates (2026-02-01 to 2028-02-01) and center; editing the machine and adding a second item kept the first selected and saved both links; the panel is closed when the form opens; not on `/vieworks`. 375 px: no horizontal scroll, button, fields and Add 44 px tall. Only console error: the deliberate 409. Full suite not run yet (runs once before publishing).
**Approved:** 2026-10-08 (owner: "okay. one correction. warranty dates for the vieworks product will be the same as the machine. not left blank"). Under the two-step rule this records approval only; execution needs a separate "go" / "execute" / "start".
**Detailed:** 2026-10-08.
**Branch:** `main` (local first; nothing is pushed until a separate "commit and push").

## Context

When a user adds a machine that comes with a Vieworks/Canon unit, she must leave the Product Inventory page, create the item on the Vieworks page, come back, and link it with the "With Vieworks/Canon?" switch. This plan lets her create the Vieworks item from inside the Product add/edit form; the new item is added to the link list already selected, and the link is saved with the machine.

## Decisions taken

1. **Inline panel, not a second modal.** A "+ New Vieworks item" button under the link list opens a small panel in the same form: Serial Number and Name, with Add and Cancel. Bootstrap modals stacked on modals are unreliable.
2. **Created right away.** Add creates the Vieworks item immediately, adds it to the list and selects it. The link itself is saved when the machine is saved. If she then cancels the machine, the item stays on the Vieworks page, unlinked, to link or delete later.
3. **Copied from the machine form at the moment Add is clicked:** medical center, room, and **warranty start and end dates** (owner's correction: the same as the machine, not blank). Contract status is not copied (left off) and BSID is auto-assigned as usual.
4. **When it is available:** only when the switch is on and a medical center is chosen; otherwise the button is disabled and the help text says to choose a medical center first.

## Investigation

- The Product form's link control is `#product-vieworks-link-control` ([products.html:253](templates/products.html:253)), rendered only when `not is_standalone_inventory` (Product page, route `/products_page`). The multi-select `#p-linked-vieworks` is filled by `refreshVieworksLinkOptions(selectedSerials)` from `vieworksData` (loaded by `loadVieworksLinkOptions` from `/api/vieworks/items`) and lists only unlinked items at the selected center (`#p-cli-id`).
- `POST /api/vieworks/items` (`add_vieworks_item`, [app.py](app.py) ~line 64030) needs only `serial_number` and `name`; it accepts `client_id`, `room`, `start_warranty` / `end_warranty` (also `start_date` / `end_date`; see `vieworks_payload_dates`, end may not be before start), and `under_contract`; BSID is server-assigned; duplicate serial returns 409 with a message. The response includes `item` (from `vieworks_item_to_dict`, same shape as `/api/vieworks/items` rows).
- The Product form's date fields are `#p-w-start` / `#p-w-end` (`<input type="date">`, ISO values), room `#p-room`, center `#p-cli-id`.
- `can_edit_products_inventory` and `can_edit_vieworks_inventory` allow the same roles (admins plus BC01/02/03 engineers), so no permission change.
- The link is still saved by the existing Product save (`linked_vieworks_serials` → `validate_product_vieworks_links` → `replace_product_vieworks_links`), so same-center and one-machine-per-item checks still apply. No server change.

## Execution steps

1. **Markup** (`templates/products.html`, inside `#product-vieworks-link-control`): a `#p-new-vieworks-btn` "+ New Vieworks item" button and a hidden `#p-new-vieworks-form` panel with `#p-new-vieworks-serial`, `#p-new-vieworks-name`, Add / Cancel buttons and an inline message `#p-new-vieworks-msg`. Done: present on `/products_page` only.
2. **Script** (`templates/products.html`): `toggleNewVieworksForm(show)` opens/closes and clears the panel; `createVieworksFromProduct()` requires serial, name and a chosen center, then `POST`s `/api/vieworks/items` (CSRF header) with `serial_number`, `name`, `client_id`, `room`, `start_warranty`, `end_warranty` taken from the machine form. On success: push `item` into `vieworksData`, call `refreshVieworksLinkOptions([...currentLinkedVieworksSerials(), newSerial])`, close the panel, toast "Vieworks item <BSID> added and selected." On error (409 duplicate or other): show the server message in `#p-new-vieworks-msg` and keep the typed values. `refreshVieworksLinkOptions` also sets the button's enabled state (switch on and center chosen); `openAddModal` / `openEditModal` close the panel. Done: existing link functions and the save flow work as before.
3. **Release**: bump the service worker `CACHE_VERSION` in `app.py` (old value kept as a history comment); `static/changelog/releases.json` entry "Add Vieworks Items from the Product Form" (Inventory; admins and engineers).

## Deliberately excluded

- Contract status and a manual BSID in the quick panel: kept short; the Vieworks page edits them.
- Creating the item only when the machine is saved: needs a cross-table server transaction; creating immediately reuses the existing endpoint unchanged.
- The same shortcut for Genoray: not asked for.

## Verification

- New `tests/test_product_new_vieworks_inline.py`: the panel ids render on `/products_page` and not on `/vieworks` or `/genoray` (each page returns 200); the script posts to `/api/vieworks/items` with `client_id`, `start_warranty` and `end_warranty`; end to end, a Vieworks item created with the machine's center and dates, then `/add_product` linking it, leaves the link and the item's dates equal to the machine's. Positive control: the template checks fail on the current file.
- Focused existing modules: `test_product_vieworks_links_history`, `test_vieworks_inventory`, `test_vieworks_parent_link`, `test_product_inventory_batch1`, `test_product_inventory_batch3`.
- Browser (database copy, temporary account removed afterwards): choose a center, enter warranty dates, switch on, "+ New Vieworks item", Add → item selected; save the machine → the Vieworks page shows the item linked, with the machine's room and warranty dates; a duplicate serial shows the inline message; the button is disabled with no center; editing an existing machine works the same; Product Save and the Vieworks page still work; 375 px; no console errors.
- Full suite once, before publishing: `venv/Scripts/python.exe scripts/run_suite.py`.

## After implementation

1. Self-review the diff; confirm every function the page calls is still defined.
2. Update `changes.md`, and this plan's Status (amend here if the outcome differed).
3. Wait for "commit and push"; stage only the intended files (never `scheduler.db`, handoffs, `changes-archive.md`, `.impeccable/`, `.claude/`, `output/`, `tmp/`); verify `git ls-remote origin refs/heads/main` and Railway's deployment status.

## Risks

- **Unlinked leftovers:** an item added and then abandoned with the machine stays unlinked on the Vieworks page (decision 2).
- **Dates copied at Add time:** if she changes the machine's warranty dates after adding the Vieworks item, the item keeps the earlier dates; editable on the Vieworks page.
- **Blast radius:** the Product page's form only; the server is unchanged and the new script runs only in Product mode.

# Link a Vieworks Item to a Machine from the Vieworks Page

**Status:** Executed — published to `main` on 2026-10-08 on the owner's "commit and push" (commit "feat(vieworks): link a Vieworks item to its machine from the Vieworks form"). Owner said "go ahead" on 2026-10-08. Full suite before publishing: 1,623 tests, 14 failures (the known list), 0 errors, 4 skips, no new failures.

**Outcome (2026-10-08):** all 6 steps done as planned. Where it differed: the Product page route is `/products_page`, not `/products` (the template test first passed trivially on a 404; it now also asserts each page returns 200). The edit route's link-row delete in `replace_vieworks_parent_link` matches the serial case-insensitively. Fail-first: all 6 new tests fail on the committed `app.py` and template; focused modules OK (`test_vieworks_parent_link` 6, `test_product_vieworks_links_history` 6, `test_vieworks_inventory` 13, `test_product_inventory_batch1` 8, `test_product_inventory_batch3` 4). Browser (DB copy, temporary admin; copy, account and launch change removed): Add on `/vieworks` lists only the chosen center's 7 machines; saving with one links it; edit preselects it, changing to another machine and to "Not linked" both save; the Product page edit form shows the link made from Vieworks; Product Save still works; at 375 px the select fits (26–349 px, 44 px tall, no horizontal scroll); no console errors besides a mistyped `/products` visit. Full suite not run yet (runs once before publishing).
**Approved:** 2026-10-08 (owner: "approved"). Under the two-step rule this records approval only; execution needs a separate "go" / "execute" / "start".
**Detailed:** 2026-10-08.
**Branch:** `main` (local first; nothing is pushed until a separate "commit and push").

## Context

Today a Vieworks item can only be linked to a machine from the Product page: the "With Vieworks/Canon?" switch and multi-select on a Product's add/edit form. On the Vieworks page (`/vieworks`) the add/edit form has no way to choose the machine. The owner asked for the Vieworks add/edit form to offer a machine to link to, "same as the linking on the product page". Both sides write the same link table, so a link made from either page shows on both.

## Decisions taken

1. **One machine per item.** The control is a single dropdown: "Not linked" plus the machines (Product records) owned by the selected medical center. The database allows only one machine per Vieworks item, so the Product page's switch + multi-select pattern does not fit.
2. **Medical center changes.** Changing an item's medical center and picking a machine from the new center in the same save is allowed. Changing the center while keeping a machine from the old center is still refused.
3. **"Not linked"** removes the link.

## Investigation

- `ProductVieworksLink` ([app.py:2784](app.py:2784)) has a unique constraint on `vieworks_serial`: at most one machine per Vieworks item; a machine can have many Vieworks items.
- Product-side checks are in `validate_product_vieworks_links` ([app.py:3205](app.py:3205)): same medical center, and an item already linked to another machine is refused. `replace_product_vieworks_links` ([app.py:3243](app.py:3243)) replaces a machine's whole link list.
- `product_vieworks_parent_payload` ([app.py:3172](app.py:3172)) serializes an item's machine; `vieworks_item_to_dict` already returns it as `linked_product` ([app.py:33536](app.py:33536)).
- `add_vieworks_item` ([app.py:63989](app.py:63989)) creates no link. `update_vieworks_item` ([app.py:64045](app.py:64045)) refuses a medical-center change on a linked item (`'A linked Vieworks/Canon item must remain with the same medical center as its Product.'`) and moves the link row when the serial is renamed.
- The Vieworks page renders `templates/products.html` with `inventory_mode='vieworks'` ([app.py:28977](app.py:28977)). The Product link control is wrapped in `{% if not is_standalone_inventory %}` ([products.html:254](templates/products.html:254)); its script functions (`loadVieworksLinkOptions`, `refreshVieworksLinkOptions`, `setupVieworksLinkControls`) return early on standalone pages.
- `loadData` ([products.html:1024](templates/products.html:1024)) loads items, clients and Vieworks link options in one `Promise.all`. The medical center autocomplete (`setupAutocomplete`) calls `refreshVieworksLinkOptions` when a center is chosen or cleared.
- `can_edit_vieworks_inventory` and `can_edit_products_inventory` allow the same roles (admins plus BC01/02/03 engineers), so linking from the Vieworks page needs no new permission.
- `/get_products` ([app.py:33350](app.py:33350)) returns `serial_number`, `name`, `bsid`, `client_id` for every Product and `[]` for HR-schedule-only users.

## Execution steps

1. **Server helpers** (`app.py`, beside `validate_product_vieworks_links`): add `vieworks_link_state_from_payload(payload)` returning `(present, serial)` for `linked_product_serial` (uppercased; empty string = unlink), and `validate_vieworks_parent_link(client_id, product_serial)` returning an error message or `None` (machine exists; item has a medical center; machine's `client_id` equals the item's). Done: both exist, messages match the Product side's wording.
2. **Add route** (`add_vieworks_item`): validate before saving; when a serial is sent, add one `ProductVieworksLink` row in the same transaction. Done: add with a valid machine returns `linked_product`; invalid machine returns 400 and creates nothing.
3. **Edit route** (`update_vieworks_item`): when `linked_product_serial` is in the payload, validate it against the new `client_id`, delete this item's link row, then add the chosen one; this replaces the existing "must remain with the same medical center" block for that request. When the field is absent (CSV import, older callers) keep today's behaviour unchanged. Add "linked machine" to the activity log note when the link changed. Done: link, change machine, unlink, and center + machine together all work; a request without the field behaves exactly as before.
4. **Markup** (`templates/products.html`): `{% if is_vieworks_inventory %}` block under the medical center field with `<select id="v-linked-product" class="form-select">` labelled "Linked Machine" and `#v-linked-product-help`. Done: present on `/vieworks` only, absent on `/products` and `/genoray`.
5. **Script** (`templates/products.html`): `loadProductLinkOptions()` fetches `/get_products` on the Vieworks page only, inside the existing `Promise.all` in `loadData`; `refreshProductLinkOptions(selectedSerial)` lists the selected center's machines as "Name — Serial (BSID)" with "Not linked" first, and help text for no center / no machines; the autocomplete calls it beside `refreshVieworksLinkOptions`; `openAddModal` resets to "Not linked"; `openEditModal` preselects `p.linked_product?.serial_number`; `saveProduct` sends `linked_product_serial` on the Vieworks page; `updateProductListAfterSave` keeps the server's `linked_product`. Done: the Product page's link control and every existing function stay untouched and working.
6. **Release**: bump the service worker `CACHE_VERSION` in `app.py` (old value kept as a history comment); add a `static/changelog/releases.json` entry "Link Vieworks to a Machine" (Inventory; admins and engineers).

## Deliberately excluded

- Linking through CSV import: not asked for.
- A "Linked machine" column in the Vieworks table: the history panel already shows the link.
- Any change to the Product page's link control or to the database schema: no new table or column is needed.

## Verification

- New `tests/test_vieworks_parent_link.py`: add with a link; edit to change machine, then unlink; machine from another center → 400; unknown machine → 400; center + machine changed together → OK; payload without the field leaves the link alone; `/get_products` shows the link made from Vieworks; template check that `#v-linked-product` renders only in Vieworks mode. Positive control: run the new tests against the unchanged routes and template and confirm they fail.
- Focused existing modules: `test_product_vieworks_links_history`, `test_vieworks_inventory`, `test_product_inventory_batch1`, `test_product_inventory_batch3`.
- Browser (database copy, temporary account removed afterwards): add a Vieworks item linked to a machine; edit to another machine, then to "Not linked"; after each step the Product page's edit form shows the link correctly; changing the medical center refreshes the machine list; Product page Save, Add and the Vieworks multi-select still work; 375 px layout; no console errors.
- Full suite once, before publishing: `venv/Scripts/python.exe scripts/run_suite.py`.

## After implementation

1. Self-review the diff; confirm every function the page calls is still defined.
2. Update `changes.md`, and set this plan's Status to `Executed` with the commit hash (amend here if the outcome differed).
3. Wait for "commit and push"; stage only the intended files (never `scheduler.db`, handoffs, `changes-archive.md`, `.impeccable/`, `.claude/`, `output/`, `tmp/`); verify `git ls-remote origin refs/heads/main` and Railway's deployment status.

## Risks

- **Stale Product form:** a Product edit form opened before a link was made on the Vieworks page replaces that machine's whole link list when saved, and can drop the new link. This already happens today between two users; it is not new.
- **Slower Vieworks page:** `/get_products` is a heavier request; it runs in parallel with the others, not after them.
- **Blast radius:** the add/edit Vieworks routes and the shared `products.html`; the field-absent path keeps old callers unchanged, and the new markup and script are gated to Vieworks mode.

# Sidebar Group Flyouts (Icon Rail)

**Status:** Executed — sandbox `design/playground` commits `a4f2b92`, `cefd6b2`, `ebb50a2`, `1c12ded`; published to `main` on 2026-10-08 (shell files only). Owner said "go" on 2026-10-07.

**Follow-up fix (2026-10-08, owner: "when i hover the display name popup does not stay"):** the account flyout closed while the pointer crossed empty rail space from the 32px avatar to its panel (300ms close timer). Leaving a trigger or panel now only starts the close timer when the pointer leaves the sidebar; leaving the sidebar closes it. Playground `7613a80`, published to `main` with service worker v265.

**Second follow-up fix (2026-10-08, owner: "the problem is still there", every flyout closes with the pointer still):** the flyout code closed on every window `resize` event, and the Calendar page dispatches synthetic resize events about 4 times a second. Flyouts now close only when the viewport size actually changes. Playground `abb0ef0`, published to `main` with service worker v266.

**Re-critique (2026-10-08, `.impeccable/critique/2026-10-07T23-35-12Z__templates-layout-html.md`, 21/40, was 25/40):** most of the drop is deeper phone and keyboard checking of issues that predate this plan (phone drawer covered by the top bar and page docks, weak focus rings). One regression is from this plan: decision 3 (focus opens the flyout) puts every flyout link in the Tab order, about 17 stops for 7 rail icons, where the old collapsed groups kept their links out of it. The owner chose to keep the flyouts and fix the keyboard path next with `harden` (open on Enter/Space/ArrowRight, closed flyouts out of the Tab order, stronger focus rings); that reverses decision 3 and is a follow-up, not part of this commit.

**Amendment (2026-10-08, owner sent `harden`): keyboard path and focus rings.** Decision 3 changes: Tab onto a rail icon no longer opens its flyout; it shows the icon's name label. Enter, Space or ArrowRight opens the flyout and moves focus to its first item; ArrowDown/ArrowUp move inside it; ArrowLeft or Escape closes it and returns focus to the icon; Tab out closes it. Closed flyouts stay `display:none` in the rail, so their links are out of the Tab order (no `inert` needed). Calendar: Enter still opens Calendar, ArrowRight opens its flyout. Focus rings: one shell rule in `static/css/app-shell.css` gives every link, button and focusable control in `.sidebar` and `.mobile-nav` a 2px `--shell-focus-ring` (#e2e8f0, about 8.9:1 on the sidebar) ring, replacing the 2.44:1 primary-blue ring and the `outline: none` on the pin button and header tools. Tests: `test_rail_group_flyouts_replace_the_peek` gains checks for no focus-open and the arrow-key handler; new focus-ring source check. Browser: Tab sequence through the rail, Enter/ArrowRight/arrows/Escape, ring visible on the pin button. **Follow-up (2026-10-08, owner: "arrow key is not working on the rail"):** ArrowDown/ArrowUp on a rail icon also move between the rail icons (wrapping); before, single-link icons ignored all arrows. **Done (2026-10-08, not committed):** `app-shell.css` `?v=10`; the avatar and resize-handle focus outlines were folded into the one shell ring (their own outline lines removed). New test `test_rail_flyouts_open_from_keys_not_focus_and_rings_are_visible` and the `?v=10` pin fail on the committed files; 74 shell tests OK. Browser (DB copy, temporary account removed), 1366x768 with real key presses: Tab from the pin button reaches Account in 8 stops with no flyout opening (was about 17) and the name label showing; Enter on Field Operations opens it with focus on Travel Request; ArrowDown/ArrowUp move and wrap to LPR; ArrowLeft closes and returns to the icon; ArrowRight on Calendar opens Calendar + Create TSR without navigating; Escape returns focus to Calendar; the pin button shows a 2px #e2e8f0 ring; mouse hover still opens flyouts; no console errors.

**Outcome (2026-10-07):** all 5 steps done. Where the plan and the outcome differed:

- `app-shell.css` cache version is `?v=9`, not `?v=8`: the browser kept serving the cached v8 during testing.
- Browser check found two issues, both fixed: (1) moving from an open flyout straight onto a single-link icon showed no name label (the label waited for the flyout's close delay); `showTip` now closes any flyout first. (2) In the account flyout, What's New inherited the amber `.has-unread` colour and sat beside the amber Log out; the row is now plain text and the badge alone signals unread.
- One more existing test changed: `tests/test_appearance_themes.py` counted 2 Appearance buttons; the account flyout makes 3.
- The phone-wide button rule (`button:not(...)`, min-height 44px, radius 12px) now also excludes `.sidebar-user-avatar`, so the avatar stays a 32px circle in the drawer.
- Fail-first: `test_rail_group_flyouts_replace_the_peek`, `test_quiet_rows_and_one_active_signal`, the `?v=` pin and the Appearance count all fail on the committed files; 73 tests OK across `test_layout_sidebar`, `test_appearance_themes`, `test_offline_api_status`, `test_dark_mode_readability`.
- Browser (DB copy, temporary account removed; Admin is username-locked so it was not visible to the test account, and the bottom clamp was tested on Records at 1366×500 instead): Records flyout with Inventory subheading (265px), staying open while the cursor moves into it and closing after leaving; Calendar flyout with Calendar + Create TSR; Dashboard name label; account flyout with name, role, Appearance, What's New (badge) and Log out; focus opens, Escape closes and returns focus, touch tap opens without Bootstrap expanding the group inline, tap outside closes, touch tap on Calendar opens the flyout instead of navigating; at 1366×500 the panel moves up (top 227, bottom 492); pinned is 240px with name and logout inline, no flyout parts, avatar disabled, groups expand inline; 375px drawer unchanged with a 32px avatar; light and dark themes; no console errors.
**Approved:** 2026-10-07: the owner said "confirm" to the Impeccable `shape` brief, then answered two follow-up questions raised by the investigation (Calendar flyout, avatar flyout). Under the two-step rule this records approval only; execution needs a separate "go" / "execute" / "start".
**Detailed:** 2026-10-07.
**Branch:** sandbox `design/playground` only. Nothing goes to `main` until a separate "commit and push".

## Context

The desktop icon rail (plan below, live on `main` as `7e92a57`) opens the full sidebar as an overlay "peek" whenever the pointer enters the rail. Reaching a link inside a group then takes three steps: hover, click the group, click the link. This plan replaces the peek with per-icon flyouts, the pattern Gmail and VS Code use, so a group link is two steps away (hover, click) and the page is never covered by the whole sidebar. It is item P1 from the post-rail critique.

## Decisions taken

1. **Flyouts replace the peek.** In the rail, hovering a group icon opens a small panel beside it with the group name and its links. Hovering a single-link icon shows its name in a label. The full-sidebar peek (`body.sidebar-peek`, `initSidebarPeek`) is removed.
2. **Touch:** tapping a group icon opens its flyout; tapping a link navigates; tapping outside closes it.
3. **Keyboard:** Tab onto a group icon opens its flyout; Tab continues into its links; Escape closes it and returns focus to the icon.
4. **Records → Inventory:** one panel; Records links, then a small "Inventory" subheading with its links below (no second-level flyout).
5. **Calendar:** treated as a small group: its flyout shows Calendar and Create TSR. Clicking the Calendar icon with a mouse still opens Calendar.
6. **Avatar flyout:** the initials at the bottom open a flyout with the username and role, Appearance, What's New and Log out (all hidden in the rail today and reachable only through the peek).
7. **Look:** flyouts use the sidebar's own dark surface, sidebar row styles and the current-page marker, so they read as part of the rail.
8. **Unchanged:** the pinned sidebar, the pin control, resize, the phone drawer, every link, role check and badge.

## Investigation

1. **Peek code:** `initSidebarPeek()` in `templates/layout.html:535-590` (open 150ms / close 300ms delays, `focusin`/`focusout`, touch first-tap capture, outside `pointerdown`, Escape, a `MutationObserver` ending the peek on pin or mobile). CSS: `body.sidebar-collapsed.sidebar-peek .sidebar` (`static/css/app-shell.css:509-512`), and every rail rule is written as `body.sidebar-collapsed:not(.sidebar-peek) …` (`app-shell.css:515-586`). No other file uses `sidebar-peek` besides `tests/test_layout_sidebar.py` (lines 184-208).
2. **Groups are Bootstrap collapses:** `.sidebar-section-toggle` buttons with `data-bs-toggle="collapse"` and a following `.sidebar-subnav` (`layout.html:220-238` Field Operations, `260-275` Reports & Insights, `283-342` Records/Resources with the nested Inventory toggle and `.sidebar-subnav-nested` at `304-332`, `346-361` Admin). Each subnav sits **directly after** its trigger in source order, so Tab already flows from the icon into the links: the flyout can reuse these existing elements instead of duplicating markup.
3. **Calendar** is a split row: link `.sidebar-calendar-main` plus `.sidebar-calendar-arrow` collapse button, subnav `#calendar-sidebar-section` holding only Create TSR (`layout.html:191-212`). In the rail the arrow and subnav are hidden, so Create TSR is unreachable without the peek.
4. **Header and footer in the rail:** the appearance button, What's New bell, title and resize handle (`layout.html:97-133`) and the username/role and logout (`layout.html:372-389`) are `display:none` in the rail (`app-shell.css:515-525`). The avatar is a `<span aria-hidden="true">` (`layout.html:373`), so it cannot take focus today.
5. **Copies stay in sync for free:** the What's New badge script uses `querySelectorAll('.changelog-header-badge')` (`layout.html:719`) and `static/js/app-appearance.js:47-50` updates every `.appearance-header-icon` / `.appearance-header-button`, so a second Appearance button and bell inside the avatar flyout update automatically.
6. **Positioning:** `.sidebar` is `position: fixed; overflow: hidden` with no `transform` (`app-shell.css:100-113`) and `.sidebar-nav` scrolls (`overflow-y: auto`, `:180`). A child with `position: fixed` escapes both clips, so a flyout can be the existing subnav set to `position: fixed`, `left: var(--sidebar-rail-width)`, with `top` set by JS from the trigger's `getBoundingClientRect()`. Desktop sidebar `z-index: 1045` (`:489`) already sits above sticky headers and below modal backdrops.
7. **Versions on this branch:** `app-shell.css?v=7`; service worker marker `v262-site-visit-optional-task` (`app.py:27142`). `main` is already at `v263`, so the publish bump for this plan is `v264`.

## Execution steps

1. **Markup (`templates/layout.html`).**
   - Add a `<div class="sidebar-flyout-title" aria-hidden="true">` as the first child of each group subnav: Field Operations, Reports & Insights, Records/Resources (same Jinja expression as its label), Admin; and "Inventory" as the first child of `#inventory-sidebar-section`.
   - In `#calendar-sidebar-section`, add a "Calendar" flyout title and `{{ nav_link('/timeline', 'fa-calendar-days', 'Calendar', extra_class='sidebar-flyout-only') }}` before Create TSR.
   - Footer: the avatar `<span>` becomes `<button type="button" class="sidebar-user-avatar" aria-label="Account" aria-expanded="false" aria-controls="sidebar-user-flyout">`; wrap `.sidebar-user-meta`, a new Appearance button (same `onclick` and classes as the header one), a new What's New link (same condition `not stock_inventory_only_user and not hr_schedule_only_user`, same classes and badge span) and the existing `.sidebar-logout` in `<div id="sidebar-user-flyout" class="sidebar-user-flyout">`. Keep every existing class and id.
   - Add one `<div id="sidebar-rail-tip" class="sidebar-rail-tip" aria-hidden="true"></div>` inside `#sidebar` for single-link name labels.
   - Done: the pinned sidebar renders exactly as before (titles, the flyout-only Calendar link, the extra Appearance/What's New and the tip are hidden outside the rail); render tests per role still pass.
2. **CSS (`static/css/app-shell.css`).** Delete the peek rules (`.sidebar-peek` width/shadow) and rewrite the rail selectors as `body.sidebar-collapsed .sidebar …`. Rail additions:
   - `.sidebar-subnav.is-flyout-open` and `.sidebar-user-flyout.is-flyout-open`: `display: block !important; position: fixed; left: var(--sidebar-rail-width); min-width: 220px; max-height: calc(100vh - 16px); overflow-y: auto`, sidebar background, rounded right corners, soft shadow; inside it labels are visible again (undo the visually-hidden span rule) and rows are left-aligned with normal padding.
   - Inside a flyout: `.sidebar-flyout-title` shows as a small uppercase label (group-label style); the nested Inventory toggle button is hidden and `.sidebar-subnav-nested` is forced visible, so Inventory reads as a subheading.
   - Outside the rail: `.sidebar-flyout-title`, `.sidebar-flyout-only`, the avatar flyout's Appearance/What's New copies and `.sidebar-rail-tip` are `display: none`; the pinned footer keeps its current look (meta + logout inline).
   - `.sidebar-rail-tip.is-visible`: fixed, beside the rail, small dark label, `pointer-events: none`.
   - Reduced motion: no flyout transition. Bump `app-shell.css?v=7` → `?v=8` in `layout.html`.
   - Done: no `sidebar-peek` string remains in CSS; pinned and phone drawer styles unchanged.
3. **Controller (`templates/layout.html`).** Replace `initSidebarPeek()` with `initSidebarFlyouts()`:
   - Triggers: each `.sidebar-section-toggle` that is not `.sidebar-subnav-toggle` (panel = its `aria-controls` element), `.sidebar-calendar-row` (panel `#calendar-sidebar-section`), and the avatar button (panel `#sidebar-user-flyout`). One flyout open at a time.
   - `isRail()` as today. `open(trigger)`: add `is-flyout-open`, set `aria-expanded="true"` on the trigger, set `top` to the trigger's top, clamped so the panel's bottom stays 8px inside the viewport. `close()`: remove the class and restore the trigger's `aria-expanded` to the Bootstrap state (`panel.classList.contains('show')`; `false` for the avatar).
   - Mouse: `pointerenter` on a trigger opens immediately (cancels any pending close); `pointerleave` from trigger or panel schedules a close after 300ms; entering the panel cancels it.
   - Keyboard: `focusin` on a trigger opens; `focusout` closes when focus leaves both trigger and panel; Escape closes and focuses the trigger.
   - Clicks in the rail (capture phase): a click on a group toggle opens/toggles its flyout and stops Bootstrap's collapse; a touch tap on the Calendar link or the avatar opens the flyout instead of navigating (a mouse click on Calendar still navigates).
   - Outside `pointerdown`, `.sidebar-nav` scroll and window resize close the flyout. As today, a `MutationObserver` closes it when pinning or entering the mobile layout.
   - Single links in the rail (`.sidebar-nav > a`): `pointerenter`/`focus` shows `#sidebar-rail-tip` with the link's label beside it; leave/blur hides it.
   - The avatar button is `disabled` outside the rail (the footer is fully shown there), so the pinned Tab order is unchanged.
   - Done: hover, tap and Tab each open the right panel; Escape returns focus; no Bootstrap collapse state changes while in the rail.
4. **Tests (`tests/test_layout_sidebar.py`).** Update the three peek tests (`test_icon_rail_peek_and_docks_follow_the_shell_offset`, `test_rail_labels_stay_named_and_peek_sits_above_sticky_headers`, `test_quiet_rows_and_one_active_signal`) to the new selectors, keeping their dock, z-index, accessible-name and active-signal intent. New `test_rail_group_flyouts_replace_the_peek`: no `sidebar-peek` in the template or CSS; `initSidebarFlyouts` defined; a `sidebar-flyout-title` in each group subnav and in the nested Inventory; the flyout-only Calendar link; the avatar is a button controlling `#sidebar-user-flyout`, which holds Log out, Appearance and What's New; `?v=8` pin. Done: the new and changed checks fail on the current files and pass after.
5. **DESIGN.md.** Layout (line ~154) and Navigation (line ~203): replace the peek description with group flyouts, the name label on single links, and the avatar flyout.

## Deliberately excluded

- **Phone menu (P2)** and **lighter header (P3):** separate items in the course.
- **Regrouping or renaming menu items:** this plan keeps every link, label and role check.
- **Duplicating group links into new markup:** the flyout reuses each existing subnav, so links, `aria-current` and permissions keep one source.
- **The Reimbursement dock overlap:** its dock (z-index 1200) can still cover the bottom of a tall flyout on that page; a known limit carried over from the rail plan.

## Verification

- **Focused tests:** `tests.test_layout_sidebar`, `tests.test_appearance_themes`, `tests.test_offline_api_status`, `tests.test_dark_mode_readability`. Positive control: run the new/changed checks against the committed files first and record that they fail.
- **Browser** (local server on a copy of `scheduler.db`, temporary superadmin, cleaned up after), 1366×768:
  - Dashboard: hover each group icon → its flyout beside the icon with title and links; move the cursor diagonally from icon to panel without it closing; current page marked; clicking a link navigates.
  - Records: Inventory shows as a subheading with its links; Admin's flyout stays inside the viewport (also at 1366×600).
  - Calendar: hover → Calendar + Create TSR; a mouse click on the icon opens Calendar.
  - Single link (Dashboard): the name label shows on hover and focus.
  - Avatar: hover/Tab → username, role, Appearance (switches theme), What's New (badge matches the header), Log out link present.
  - Keyboard: Tab onto Field Operations opens it, Tab reaches Travel Request, Escape closes and focus returns to the icon.
  - Touch (emulated): tapping a group icon opens the flyout, tapping outside closes it.
  - Pinned: identical to before (groups expand inline, resize works, no avatar button in the Tab order). Light and dark appearance.
  - 375px: phone drawer unchanged. Console: no new errors.

## After implementation

1. Self-review the diff: no orphaned peek code; every id other code references (`sidebar`, `sidebar-toggle-desktop`, `show-sidebar-btn`, `sidebar-resize-handle`, nav badge ids, `.changelog-header-badge`) still present; the existing buttons (pin, resize, appearance, What's New, logout) still work.
2. Re-run `/impeccable:impeccable critique templates/layout.html` and compare with the last 25/40.
3. Record fail-first proof, browser results and any plan/outcome difference under this plan; update `changes.md`; set Status to `Executed — not yet committed`.
4. Commit to `design/playground` only on "commit to playground". Before any publish: service worker marker `v264-…`, a `static/changelog/releases.json` entry (all roles, category "App"), the full suite once, then push to `origin/main` only on "commit and push". Never stage `scheduler.db`, handoffs, `changes-archive.md`, `.claude/`, `.impeccable/`, `output/`, `tmp/`.

## Risks

- **Every page changes:** the shell wraps the whole app. Safety net: the sandbox branch, the browser sequence, the pinned-mode check.
- **The hover gap closes the flyout** when moving from icon to panel: the panel sits flush against the rail, and the 300ms close delay is cancelled on entering the panel.
- **Bootstrap collapse fighting the flyout:** clicks in the rail are intercepted in the capture phase, and the flyout uses its own class, not `.show`, so returning to pinned shows each group exactly as it was.
- **The disabled avatar in pinned mode** could look clickable: keep the existing avatar look with `cursor: default`.

# Desktop Icon Rail Sidebar (App Shell)

**Status:** Executed — published to `origin/main` on the owner's "commit and push" (sidebar work only; commit: see `git log`, "feat(shell): desktop icon rail sidebar"). Owner said "okay go" on 2026-10-07 and picked **dark** at step 8.
**Approved:** 2026-10-07 — the owner said "approved" to the Impeccable `shape` brief. Under the two-step rule this records approval only; execution needs a separate instruction ("go", "execute", "start").
**Detailed:** 2026-10-07.
**Branch:** built on sandbox `design/playground`; only the sidebar files were promoted to `main` (the Product Inventory sandbox work and `DESIGN.md` stay on the playground).

**Progress (2026-10-07):** all 10 steps done; step 8 comparison shown in the browser pane with a temporary in-page Dark/Light switch (no file change); owner picked dark.

**Where the plan and the outcome differed so far:**

- Step 1: kept the existing key `medical_service_sidebar_visibility` and state machine (`collapsed` = rail, `expanded` = pinned) instead of a new `medical_service_sidebar_mode` key; only the default flipped (no saved value, an invalid value, or blocked storage → rail). Reason: the tested visibility helpers already persist, guard storage and ignore mobile, so reusing them was the smallest change. Effect: a browser that explicitly saved `expanded` (by toggling before) opens pinned once; anyone else starts on the rail.
- Step 4: the existing desktop toggle is the pin control (labels "Pin navigation open" / "Collapse navigation to icons"); `#show-sidebar-btn` stays in the markup for its JS references but is hidden on desktop.
- Step 7: desktop collapsed is no longer `inert` (rail icons must stay reachable); the mobile closed-drawer rule is unchanged.
- `app-shell.css` cache version is `?v=5` (v4 was cached by the browser during testing).
- Step 9 (dark, quieter): row dividers removed (rows, Calendar row and arrow, subnav), row weight 700 → 600 and sub-rows 700 → 500, group labels 800 → 700, row height 46 → 44px (keeps 44px touch rows in the phone drawer, which shares these rules), the open parent group only brightens while the current page keeps the accent rail (rail view puts the rail on the parent icon). `app-shell.css` `?v=6`.
- Phones: drawer behaviour unchanged, but it shares the quieter row styling (no dividers, lighter weight, 44px rows).
- Fail-first: the six new or changed `test_layout_sidebar` checks fail against the committed files; 71 tests OK across `test_layout_sidebar`, `test_appearance_themes`, `test_offline_api_status`, `test_dark_mode_readability`.
- **Post-execution re-critique** (`.impeccable/critique/2026-10-07T07-38-16Z__templates-layout-html.md`, 25/40; every issue from the first shell critique resolved) found two regressions introduced by this plan, both fixed on the owner's "fix my 2 regressions": (1) the overlay peek sat at z-index 1000, under Bootstrap sticky table headers (1020), so the Dashboard table header drew over it: desktop `.sidebar` is now 1045 (above sticky/fixed, below modal backdrops 1050; phones keep 1000 so the drawer stays under the Menu button); (2) rail labels used `display:none`, leaving Dashboard, Stock Inventory, Calendar and System Settings with no accessible name: they are now visually hidden (clip) so the label remains the name. Section toggle and arrow icons gained `aria-hidden`. `app-shell.css` `?v=7`. New test `test_rail_labels_stay_named_and_peek_sits_above_sticky_headers` (fails on the committed files); 72 shell tests OK; browser: peek on top of the sticky header at x=80/150/220, rail names present, no visible labels. Known limit: the Reimbursement action dock (z-index 1200) still covers the bottom of an open peek on that page.
- Final browser round (DB copy, temporary account removed): rail 64px with no horizontal scroll on Dashboard, Calendar, Inventory, Approvals, Travel Request at 1366; Reimbursement docks 64px in rail and 240px pinned, Travel dock 64px; Calendar at 1024 shows Mon–Fri in rail and the peek overlays it with Field Operations expanded; 375px drawer opens at 240px, closed inert, rows 44px. Only console error: Reimbursement's "account is not linked to an engineer profile" for the test account (unrelated).
- Browser (1366×768, DB copy; the test pane window was unfocused, so focus was dispatched directly): rail 64px with main content at 64px (Inventory width 1111 → 1287px); peek 240px over the page with main content still at 64px and labels shown; Escape closes; pinned 240px pushes the page and persists `expanded`.

## Context

The shell critique (`.impeccable/critique/2026-10-07T06-56-37Z__templates-layout-html.md`, 25/40) measured the desktop sidebar at a fixed 240px: 17.6% of the width at 1366px and 23% at 1024px (Inventory shows 672 of 1129px of columns at 1024). The owner hides the sidebar to see full tables and the calendar, finds it heavy ("too much going on"), and wants a modern look without losing ease of use. Hiding today is all-or-nothing (width 0, a 32px "show" button in the page flow). The two confirmed bugs from that critique (hidden links in the Tab order, username squeezed to 0px) are already fixed on the playground (`syncSidebarInert`, `.sidebar .sidebar-logout`).

## Decisions taken

1. **Rail by default on desktop (≥993px):** 64px strip, icons only, the current page marked on its icon, badge **dots**, user initials at the bottom.
2. **Peek:** hovering the rail, keyboard focus entering it, or tapping it slides the full 240px sidebar **over** the page (no content shift); groups (Field Operations, Records/Resources, Reports & Insights, Calendar → Create TSR) expand inside the peek exactly as today. Leaving it (after a short delay) or Escape tucks it back. One pattern for mouse, keyboard and touch; no separate flyout menu (owner chose flyout, then accepted folding it into the peek as one behaviour).
3. **Pinned:** a pin control keeps the full sidebar open and pushing the page, like today; resizing (200–360px) works only when pinned. The choice (rail / pinned) is remembered per browser.
4. **Look:** lighter and quieter: no divider under every row, lighter row weight, one clear active signal. **Dark slate vs light** is not decided here: both are shown in a side-by-side comparison (Level 4 `live`, or a temporary switch on the local copy if live mode is blocked) and the owner picks before the final styling step.
5. **Phones (<993px) unchanged** for now; bottom tab bar decided later.

## Investigation

1. **Collapse today:** body class `sidebar-collapsed` + `html[data-sidebar-collapsed]` set before paint by a head script (`templates/layout.html:33-42`, key `medical_service_sidebar_visibility`), applied by `applySidebarVisibility` / `toggleSidebarDesktop` (`layout.html:~450-495`); CSS sets sidebar width 0 and main margin 0 (`static/css/app-shell.css:476-497`). Breakpoint constant `SIDEBAR_DESKTOP_BREAKPOINT = 993` (`layout.html:~408`); mobile drawer is a separate state (`setMobileSidebar`).
2. **Width variable:** `--sidebar-width` (default 240, min 200, max 360, step 20; `app-shell.css:12-16`) drives `.sidebar` width (`:102`) and `.main-content` margin (`:466`); the resize controller writes it to `document.documentElement` (`layout.html:~572`, key `medical_service_sidebar_width`).
3. **Pages that position by the sidebar width:** fixed bottom docks use `left: var(--sidebar-width, 240px)` in `templates/reimbursement.html:608,698`, `templates/travel_request.html:157`, `templates/_liquidation_base.html:50`. They must follow the rail width (and today they appear not to follow collapse-to-0; verify during execution and fix the same way).
4. **Nav markup:** every link goes through the `nav_link` macro (`layout.html:135-144`: icon `<i>`, label `<span>`, optional `.sidebar-count-badge`); groups are `.sidebar-section-toggle` buttons with Bootstrap collapse; Calendar is a split link + arrow (`:189-207`); group labels `.sidebar-group-label` (`:171,214,248`). Badges are filled by the pending-summary poller (`layout.html:~691`, ids `nav-badge-approvals`, `nav-badge-my-requests`; CSS `.sidebar-count-badge` `app-shell.css:368-390`).
5. **Header and footer:** header holds the title, appearance button, What's New bell and the desktop toggle (`layout.html:94-120`, `.sidebar-header` `app-shell.css:116`); resize handle `#sidebar-resize-handle` (`layout.html:122`); footer `.sidebar-user` with avatar, name/role and logout (`layout.html:~370-388`).
6. **Tests pinning shell behaviour:** `tests/test_layout_sidebar.py` (source checks, node runtime test of the visibility helpers, render tests per role), `tests/test_appearance_themes.py`, `tests/test_offline_api_status.py`. The runtime node test stubs `document`/`window`; new helpers must stay testable the same way.
7. Service worker marker is `v262-site-visit-optional-task` (`app.py:27142`); `app-shell.css` is at `?v=4` (playground).

## Execution steps

1. **State model** (`templates/layout.html` head script + body controller): replace the collapsed/expanded preference with `rail` / `pinned` under a new key `medical_service_sidebar_mode` (default `rail`); read it before paint into `html[data-sidebar-mode]`. The old key is ignored (the owner chose rail by default, so everyone starts on rail once) and removed from storage on first load. Done: a fresh browser loads in rail with no flash; pin/unpin persists across navigation.
2. **Rail CSS** (`static/css/app-shell.css`): `html[data-sidebar-mode="rail"]` at ≥993px sets a `--sidebar-rail-width: 64px`, sidebar width to the rail, main margin to the rail; labels, group labels, badge numbers, header title and footer name hidden in rail; icons centered with 44px hit areas; group labels become thin separators. Done: rail renders on Dashboard, Calendar, Inventory, Approvals with no overflow.
3. **Peek** (`layout.html` controller): on pointer enter (≈150ms open delay), `focusin`, or tap on the rail, add `sidebar-peek`: full width as an overlay (`position` above content, shadow, no main-content shift); on pointer leave (≈300ms close delay), `focusout` leaving the sidebar, or Escape, remove it. `aria-expanded` on the pin control reflects pinned state; peek does not change it. Respect `prefers-reduced-motion`. Done: hover, Tab and click all reveal labels; Escape closes; page never jumps.
4. **Pin control:** reuse `#sidebar-toggle-desktop` as Pin/Unpin (label and icon swap); remove the in-page `#show-sidebar-btn` flow button on desktop (rail replaces it) while keeping the id-safe code paths that reference it. Resize handle active only when pinned. Done: pinned behaves like today's expanded sidebar, including saved width.
5. **Badges in rail:** when rail (not peek/pinned), `.sidebar-count-badge.show` renders as an 8px dot on the icon; the accessible count stays in the existing live text. Done: a pending approval shows a dot in rail and the number in peek.
6. **Docks follow the visible width:** introduce `--shell-offset` (rail 64px / pinned `--sidebar-width` / mobile 0) and switch the three docks from `var(--sidebar-width, 240px)` to `var(--shell-offset, var(--sidebar-width, 240px))`. Done: the Reimbursement, Travel Request and Liquidation docks start at the rail edge and at the pinned edge.
7. **Inert and focus:** extend `syncSidebarInert` so rail is **not** inert (icons stay reachable) and the hidden labels are not announced twice; the mobile drawer rule is unchanged. Done: Tab reaches rail icons, focus opens the peek, Shift+Tab out closes it.
8. **Visual comparison (Level 4):** try `/impeccable live` on the local copy; if the pane blocks the live helper, add a temporary `data-sidebar-tone="dark|light"` switch on the local copy only, capture both at 1366 and 1024, and the owner picks. Remove the temporary switch after the choice.
9. **Final styling** in the chosen tone with `quieter` / `layout`: remove per-row dividers, row weight 500–600, one active signal (accent on the icon/rail edge; no filled parent toggle), tokens only (`--app-primary`, surface/sidebar tokens; no new hardcoded accent hex).
10. **DESIGN.md:** update Layout and Navigation (rail / peek / pinned, 64px, tone chosen) and the sidebar colour tokens if the tone changes.

## Deliberately excluded

- Phone navigation (drawer layering, backdrop, bottom tab bar): owner chose "decide later".
- Ctrl+K page search and keyboard shortcuts: separate feature.
- Renaming or regrouping menu items (Records vs Resources mismatch, 18 destinations): separate `clarify` pass; this plan keeps every link, role check and badge exactly as is.
- Body font change (generic sans-serif): separate `typeset` decision.

## Verification

- **Tests** (`tests/test_layout_sidebar.py`): extend the node runtime test for mode read/write (default rail, pin persists, storage unavailable falls back to rail, mobile ignores mode), peek open/close helpers, and inert rules (rail reachable, mobile closed inert). Source checks for the head script key, `--shell-offset` in the three docks, and the rail CSS block. Positive control: each new assertion fails against the current playground files.
- Focused modules: `test_layout_sidebar`, `test_appearance_themes`, `test_offline_api_status`, plus the dock pages' tests if any reference the dock CSS.
- **Browser** (local server on a copy of `scheduler.db`, temporary account, cleaned up after): 1366×768 and 1024×768 on Dashboard, Calendar, Inventory, Approvals, Reimbursement (dock): rail default, hover peek over content, Tab into rail opens peek, Escape closes, pin/unpin persists across pages, resize only when pinned, badge dot vs number, docks aligned; light and dark appearance modes; 375px phone unchanged (drawer, top bar); no console errors.

## After implementation

1. Self-review the diff for orphaned code (the old visibility key, the in-page show button CSS) and keep every id other code references.
2. Re-run `/impeccable critique templates/layout.html` and compare with 25/40.
3. Record fail-first proof, browser results and plan/outcome differences here; update `changes.md`; Status `Executed — not yet committed`.
4. Commit to `design/playground` only on "commit to playground". Before any publish: service worker `v263-…` (keep the v262 marker), `app-shell.css` `?v=` bump, `static/changelog/releases.json` entry (all roles, category "App"), full suite once, then push to `origin/main` only on "commit and push". Never stage `scheduler.db`, handoffs, `changes-archive.md`, `.claude/`, `.impeccable/`, `output/`, `tmp/`.

## Risks

- **Every page changes:** the shell wraps the whole app. Safety net: sandbox branch, the four-page browser sequence, and the dock check.
- **Hover peek feels jumpy** (opens when the mouse passes by): open/close delays; pin is always available.
- **Pages with their own fixed elements** beyond the three docks may assume 240px; grep for `240px` / `left:` fixed elements during step 6.
- **Saved preferences reset:** everyone starts on rail once (intended by the owner); saved resize width is kept.

# Medical Center Visit - Site Visit Schedule Type

**Status:** Executed — published to `origin/main` on the owner's "commit and push" (commit: see `git log`, "feat(calendar): Medical Center Visit - Site Visit schedule type").
**Approved:** 2026-10-07 — the owner said "approved, write it to plans.md". Under the two-step rule this records approval only; execution needs a separate instruction.
**Execution authorized:** 2026-10-07 — the owner said "go ahead. do not over engineer".
**Detailed:** 2026-10-07. **Finished:** 2026-10-07.

**Where the plan and the outcome differed:**

- Step 2: the "serialized `tsr_without_equipment_allowed`" check became a browser check instead of a unit test (the serializers call the same gate the unit tests cover). Fail-first: 4 of 5 new tests failed before the change (the "plain visit stays blocked" control passed, as expected); all 5 pass after.
- Step 6: also covered the mobile Duplicate Schedule path (`getMobileDuplicateSchedulePayload`), which now keeps Site Visit as the category.
- Step 8: the TSR page already strips billing tags from the task (`stripScheduleBillingTags`, `offline_tsr.html`) and the TSR filename does the same (`app.py` filename context). `[Site Visit]` was added to both regexes; nothing else needed.
- Browser (local copy of `scheduler.db`, engineer `kent` with the Francis switch off): the option lists under Medical Center Visit; Site Visit hides Equipment and keeps client/flags; saved title `Courtesy call [Site Visit]` with empty product; the card shows "Courtesy call" plus a "Site Visit" badge; Create TSR opens with Model/Serial blank and read-only and no raw token on the page; edit reopens as Site Visit with status/files shown; re-save keeps one token; `canCreateTSRForSchedule` is false for a product-less Work schedule and true for a Site Visit; 375 px has no horizontal scroll; no console errors. The offline queue/sync run was skipped (no over-verification): the server re-checks through the same `can_create_tsr_without_equipment_for_shift` on sync.
- Focused modules: `test_site_visit_schedule_type` 5, `test_tsr_without_equipment` 8, `test_timeline_tsr_file_details` 14, `test_offline_tsr_pending_schedule` 30, `test_sw_cache_version` 5 — all OK. `node --check` on both pages' inline scripts OK. Full suite not run yet (before publishing only).

## Context

Creating a TSR for a client schedule with no product is only possible through Francis's per-account switch (`User.can_create_tsr_without_equipment`, plan "Francis-only TSRs without assigned equipment" in `plans-archive.md`, commit `7cd4388`). Other engineers also do site visits that have no equipment. The owner wants a new schedule type, **"Medical Center Visit - Site Visit"**: it needs only a client (no product/equipment selection), and Create TSR is available for it. The no-equipment rule becomes a property of the schedule instead of one account.

## Decisions taken

1. New option label exactly **"Medical Center Visit - Site Visit"** in the Calendar schedule-type dropdown, directly under "Medical Center Visit".
2. A Site Visit requires a client; product/equipment is hidden and always saved empty.
3. Create TSR is allowed on a Site Visit for whoever may normally create a TSR on that schedule (same access checks as a normal Medical Center Visit); only the equipment requirement is dropped.
4. Francis's switch is kept unchanged (see Deliberately excluded).
5. Encoding: a title token `[Site Visit]` (same mechanism as the billing flags), not the `schedule_type` column (see Investigation 4).

## Investigation

1. **Schedule type is not a stored column.** The dropdown `#f-category` (`templates/timeline.html:945`) is encoded into the title: `buildTypedScheduleTitle` (`:13605`) prefixes `In Office:` / `Traveling to Client:` / `Pull-out Parts:` / `Holiday:`; Leave uses the leave name; "Work" = has a client. Decode: `parseTypedScheduleTitle` / `NON_WORK_TYPE_PREFIXES` (`:12645`); server analytics `classify_schedule_type` (`app.py:51887`) already labels any client schedule "Site Visit".
2. **Title tokens already round-trip through every save path.** `SITE_VISIT_FLAG_TAGS` (`timeline.html:12628`: `[Warranty]`, `[FOC]`, `[With P.O.]`, `[SC]`, `[SV]`) are appended by `applySiteVisitFlagsToTitle` (`:13742`), stripped for cards by `stripSiteVisitFlagTags` (`:12636`), shown via `renderSiteVisitFlagBadges` (`:13795`), restored on edit by `populateSiteVisitFlagsFromTitle` (`:13786`), and validated server-side by `validate_shift_billing_tags` (`app.py:56789`). Add, edit, scoped/override edits, offline queue and mobile all carry `title`.
3. **The product-less TSR path already exists** and does everything needed (blank read-only Model/Serial, no Product/Genoray/Vieworks row created, Calibration Report unavailable, filenames without placeholders):
   - Server: `can_create_tsr_without_equipment_for_shift` (`app.py:15881`) — single gate used by `validate_tsr_shift_equipment` (`:15910`), `get_online_tsr_missing_core_details` (`:16022`), and the per-schedule `tsr_without_equipment_allowed` serialized at `app.py:14009`, `:51604`, `:51806`. User-level `can_create_tsr_without_equipment_for_user` (`:11662`) requires username `francis`.
   - Calendar: `canCreateTSRWithoutEquipmentForSchedule` (`timeline.html:16251`) also requires the page-level `timelineCanCreateTSRWithoutEquipment` (`:9335`, Francis only).
   - Offline TSR: `isFrancisTSRWithoutEquipmentSchedule` (`templates/offline_tsr.html:1443`) also requires `CAN_CREATE_TSR_WITHOUT_EQUIPMENT` (`:734`, Francis only).
4. **`Shift.schedule_type` was considered and rejected.** The column exists (`app.py:3603`, `service`/`travel`) but `/add_shift` forces `'service'` (`app.py:60779`), `update_shift` only manages travel conversion (`apply_editable_travel_block_state`, `:56844`), the form never sends it, and PM linking requires `== 'service'` (`app.py:4531`, `:4589`). Using it would mean touching every save path including offline sync.
5. The Work save branch (`timeline.html:17701`–`17822`) sends `client_id`/`product_id` only when `categoryVal === "Work"`, requires a TSR file to mark Completed (`:17709`), and calls `validateSiteVisitBillingTags` / `applySiteVisitFlagsToTitle` (`:17741`). Other `'Work'` checks to mirror: `setTimelineClientQuickAddState` (`:9097`), `quickAddTimelineClient` (`:9215`), `toggleTaskStatusUI` (`:13966`), edit open (`:11813`–`11856`).
6. Local `scheduler.db`: Francis (id 22) has the switch **off**; production state unknown.
7. Service worker marker is `v260-product-inventory-headers` (`app.py:27127`).

## Execution steps

1. **Preflight.** Re-read `AGENTS.md`, this plan, the newest `changes.md` section, `git status`. Confirm SW marker still v260 and line refs still match. Set Status `In progress`; add a start bullet to `changes.md`. Done when protected dirty paths (`scheduler.db`, handoffs, `changes-archive.md`, `.claude/`, `.impeccable/`, `output/`, `tmp/`) are identified and left untouched.
2. **Fail-first tests.** Create `tests/test_site_visit_schedule_type.py` (reuse the fixtures of the existing Francis TSR tests — find with `grep -l can_create_tsr_without_equipment tests/`):
   - a non-Francis assigned engineer can submit an online TSR for a client schedule whose title contains `[Site Visit]` and has no product (`validate_tsr_shift_equipment` → `without_equipment`; no missing Equipment/Serial);
   - the same schedule **without** the token is still blocked (`missing_equipment_assignment`);
   - a `[Site Visit]` schedule with no client is blocked;
   - the serialized calendar schedule carries `tsr_without_equipment_allowed: true` for a Site Visit;
   - template markers: option text `Medical Center Visit - Site Visit` / value `SiteVisit` in `timeline.html`; `[Site Visit]` token handled; the offline TSR gate no longer depends only on `CAN_CREATE_TSR_WITHOUT_EQUIPMENT`.
   Run against unchanged code; record that they fail. Done when failures are recorded here.
3. **Server rule** (`app.py`). Add `SITE_VISIT_TITLE_TOKEN = '[Site Visit]'` and `is_site_visit_shift(shift)` near `can_create_tsr_without_equipment_for_shift`: True when the shift has a client id, no `product_id`, and the token is in `shift.title`. Make `can_create_tsr_without_equipment_for_shift` return True for `is_site_visit_shift(shift)` before the Francis check (normal TSR access checks elsewhere are untouched). Done when the step-2 server tests pass and the Francis tests still pass.
4. **Dropdown and form** (`timeline.html`). Add `<option value="SiteVisit">Medical Center Visit - Site Visit</option>` after the Work option. In `toggleCategoryFields`, treat `SiteVisit` as Work (client, task, flags, status/files on edit) but hide the product field block and clear `f-prod-id`, `f-prod-source` (`product`), `f-prod-search` and the coverage/Vieworks/calibration status. Extend `toggleTaskStatusUI`, `setTimelineClientQuickAddState` and `quickAddTimelineClient` so `SiteVisit` behaves like `Work`. Done when switching Work ⇄ Site Visit shows/hides the product field and clears any chosen product.
5. **Save** (`saveShift` branch ~`timeline.html:17701`). Introduce `const isClientVisit = categoryVal === "Work" || categoryVal === "SiteVisit";` and use it where the branch now checks `"Work"` (completed-needs-TSR check, billing tags, `client_id`). For `SiteVisit`: require a client (`timelineAlert("Please select a client for a Site Visit.")`), send empty `product_id` and `equipment_source='product'`, and append `[Site Visit]` to the title after the flags. For `Work`: strip the token. Done when saved titles carry the token only for Site Visits.
6. **Open and display.** Add the token to the stripping in `stripSiteVisitFlagTags` (cards/edit title never show it raw) and show a "Site Visit" badge (in or beside `renderSiteVisitFlagBadges`) on schedule cards. When opening a schedule for edit (`:11813`–`11856` and the other `f-category` setters at `:9865`, `:10857`), select `SiteVisit` if the title contains the token. Done when a saved Site Visit reopens as Site Visit with clean task text and the card shows the badge.
7. **Frontend TSR gates.** `canCreateTSRWithoutEquipmentForSchedule` (`timeline.html:16251`) and `isFrancisTSRWithoutEquipmentSchedule` (`offline_tsr.html:1443`): allow when the schedule has a client, no product, and the server sent `tsr_without_equipment_allowed === true`; keep the existing Francis path. Never allow when the server says `false`. Done when Create TSR appears on a Site Visit for a normal engineer and stays "unavailable" on a product-less Work schedule.
8. **TSR task line.** Check whether `[Site Visit]` appears in the generated TSR's task text (existing flags like `[Warranty]` do). If it does, strip only `[Site Visit]` where the TSR prefills the task. Note the result under this plan.
9. **Self-review.** Read the diff; confirm every function `timeline.html` and `offline_tsr.html` call is still defined (no rename/removal); `node --check` on extracted scripts; Calendar Save/Add/Upload/Create TSR still work.

## Deliberately excluded

- **Francis's switch and Settings toggle stay.** It still covers his existing Work schedules without a product; retiring it is a separate small change once Site Visit is in use.
- **No `schedule_type` column change** — extra save paths and PM risk (Investigation 4).
- **No analytics/print changes** — a client schedule is already counted as "Site Visit" (`app.py:51887`); print view keeps its status colours.
- **No bulk re-tagging** of existing schedules and no migration.
- **Calibration Report** stays equipment-only.

## Verification

- Fail-first: step-2 tests fail before steps 3–7 and pass after. Focused modules: the new file plus the existing Francis/no-equipment TSR tests, `tests/test_timeline_tsr_file_details.py`, and the offline TSR tests. Full suite only once before publishing; compare with the baseline (24 failures, 3 errors, 5 skips).
- Browser, local server on a **copy** of `scheduler.db`, temporary non-Francis test engineer: create a Site Visit (product field hidden, badge on card) → Create TSR (Model/Serial blank, read-only) → submit; repeat via the offline TSR queue and sync; reopen the schedule (shows Site Visit); a product-less **Work** schedule still shows Create TSR unavailable; Work with a product unchanged. 375 px phone width, tap targets, no console errors. Clean up the copy, test account and launch entry afterwards.

## After implementation

1. Service worker `v261-site-visit-type` in `app.py` (keep the v260 marker per the existing pattern).
2. `static/changelog/releases.json`: entry `<execution-date>-site-visit-type`, audiences admins/schedulers/engineers, category Calendar: "New schedule type Medical Center Visit - Site Visit: only a client is needed and a TSR can be created without equipment."
3. Record fail-first proof, browser results and any plan/outcome differences here; update `changes.md`; Status `Executed — not yet committed`.
4. Commit only the intended files (`app.py`, `templates/timeline.html`, `templates/offline_tsr.html`, `tests/test_site_visit_schedule_type.py`, `static/changelog/releases.json`, `plans.md`, `changes.md`) — never `scheduler.db`, handoffs, `changes-archive.md`, `.claude/`, `.impeccable/`, `output/`, `tmp/`. Push to `origin/main` only on the owner's "commit and push"; then check `git ls-remote origin refs/heads/main`.

## Risks

- **Token visible somewhere unexpected** (TSR task line, exports) — step 8 checks the TSR; blast radius is cosmetic.
- **A missed `'Work'` check** makes a Site Visit lose a Work behaviour (e.g., status/files on edit). Safety net: Investigation 5 lists them; the browser sequence exercises edit, status and upload.
- **Anyone who can edit a schedule can make it a Site Visit**, enabling a product-less TSR — intended, same authority as setting billing flags; the server rechecks the saved schedule on every TSR save and offline sync.
- Blast radius: Calendar schedule modal and cards, Create TSR eligibility, offline TSR eligibility.

# Product Inventory Batch 4: Code Cleanup

**Status:** Executed — commit `9669649` (Batches 3 and 4 published together to `origin/main` on the owner's "commit and push").
**Finished:** 2026-10-07.

**Where the plan and the outcome differed:**

- Step 5: the `openAddModal` BSID line was **not** simplified — `tests/test_genoray_inventory.py` pins `bsidField.disabled = isGenorayInventory` as a template marker; changing a test for a cosmetic one-liner was not worth it. `inventoryExportUrl` was removed as planned.
- Steps 1–4 done as planned: 45 `productEscape` → `escapeHtml`, 15 `productAlert` → `productToast`, unreachable phone empty block and the `#p-cli-id` `change` listener removed. A script scan found no call to an undefined function; `node --check` OK.
- Fail-first: all 3 tests in `tests/test_product_inventory_batch4.py` failed before the cleanup; after, they pass with the batch 1–3 files and the inventory modules.
- Browser (same session as Batch 3): validation toast "Select at least one Vieworks/Canon item…" with title "Action Needed"; Service History renders; filtering to nothing shows "No products match your filters." with Clear Filters on desktop and at 375 px; picking an owner lists that center's Vieworks items; `/vieworks` Add has BSID disabled; no console errors.
**Approved:** 2026-10-07 — the owner asked to "plan batch 3 and 4"; Batches 3 and 4 publish together in one push.
**Detailed:** 2026-10-07.

## Context

The Product Inventory scan listed leftover code in `templates/products.html` that can be removed without changing behaviour. Batch 4 runs **after** Batch 3 (it touches the same functions) and ships in the same push. Nothing the user sees changes.

## Decisions taken

1. Only remove code proven unused or exactly duplicated; no renames of functions other code calls, no new abstractions.
2. Keep every API field and endpoint (see Deliberately excluded).
3. No release-note item for this batch (invisible); it shares Batch 3's service-worker bump.

## Investigation

Counts are occurrences in `templates/products.html` after Batch 2.

1. **Two escape helpers.** `productEscape` (`:330`, `String(value || '')`, 45 occurrences) and `escapeHtml` (~`:1290`, `String(value ?? '')`, 27). Same five characters escaped (`'` as `&#39;` vs `&#039;`, equivalent). Only difference: `productEscape(0)` gives `''`, `escapeHtml(0)` gives `'0'` — every `productEscape` call passes text or uses its own `|| 'fallback'`, so the only visible effect would be a literal `0` (e.g., a part quantity of 0) showing as "0" instead of nothing, which is more correct. No test references `productEscape`.
2. **`productAlert(message, tone)`** (`:367`) only calls `productToast(message, tone)`; 15 call sites; `productToast`'s default tone is the same `'error'`. No test references it.
3. **Unreachable empty state.** `renderProductMobileCards` starts with an `if(!data.length)` block, but its only caller `renderTable` returns earlier through `renderProductRequestState('empty')` when `data` is empty.
4. **Listener that never fires.** `setupVieworksLinkControls` adds a `change` listener to the hidden `#p-cli-id`; code sets `.value` directly, which never fires `change`. The autocomplete already calls `refreshVieworksLinkOptions` itself.
5. **Unused constant.** `inventoryExportUrl` is defined and never read (the Export button uses the Jinja URL directly).
6. **Double assignment** in `openAddModal`: `bsidField.disabled = isGenorayInventory; if(isVieworksInventory) bsidField.disabled = true;` equals `bsidField.disabled = isStandaloneInventory;`.
7. Checked and **kept**: every CSS class in the page `<style>` is used (the one apparent orphan, `product-table-state-error`, is built as `product-table-state-${state}`); `productResponseData` (3 uses, tiny, kept to avoid churn).

## Execution steps

1. Replace every `productEscape(` with `escapeHtml(` and delete `productEscape`. Done: `grep productEscape` finds nothing; History modal, toasts, Vieworks link options and calibration badges render the same text.
2. Replace every `productAlert(` with `productToast(` and delete `productAlert`. Done: validation and error toasts still appear with the same title/tone.
3. Delete the `if(!data.length){…}` block at the top of `renderProductMobileCards`. Done: empty and filtered-empty phone states still come from `renderProductRequestState`.
4. Delete the `#p-cli-id` `change` listener line in `setupVieworksLinkControls`. Done: picking an owner still refreshes Vieworks options (autocomplete click calls it).
5. Delete `inventoryExportUrl`; simplify the `openAddModal` BSID line to `bsidField.disabled = isStandaloneInventory;`.
6. **Tests** — `tests/test_product_inventory_batch4.py` (source-level): no `productEscape`, no `productAlert`, no `inventoryExportUrl`, `renderProductMobileCards` has no `product-mobile-empty`, `setupVieworksLinkControls` has no `p-cli-id`. Each fails before the change. Update any existing assertion that pins a removed name (none found by `grep -rn "productEscape\|productAlert\|inventoryExportUrl" tests/`).
7. `changes.md`; this plan's status. Service worker and release entry are Batch 3's.

## Deliberately excluded

- **`calibration_certificate` in `/get_products`** — this page does not read it, but `tests/test_product_calibration_certificate.py` (lines ~200–295) pins it as the endpoint contract and other pages call `/get_products`; removing it is an API change, not a cleanup.
- **`/get_products_summary`, `/api/genoray/summary`, `/api/vieworks/summary` endpoints** — Batch 3 stops this page calling them; the routes stay (cheap; removing routes is out of scope).
- **`productResponseData`, legacy comments ("v5.4.2", "SECURITY TOKEN ADDED")** — harmless; churn without benefit.

## Verification

- Fail-first for the new test file; focused modules: batch 1–4 files, `test_product_calibration_certificate`, `test_product_vieworks_links_history`, `test_product_table_column_resize`, `test_product_inventory_mutations`; `node --check` on the page script.
- Browser (shared with Batch 3, same session): trigger a validation toast (Save with no serial), an error toast, open Service History with parts/artifacts, filter to no results on phone and desktop, pick an owner and see Vieworks options refresh, Add on `/vieworks` (BSID disabled), no console errors.

## After implementation

1. Self-review the diff: every removed name has zero remaining references; every function the page calls is still defined.
2. Record fail-first proof and browser results here; `changes.md`; status `Executed — not yet committed`.
3. Publish together with Batch 3 (see Batch 3 "After implementation").

## Risks

- **A missed call site** of a removed helper → `ReferenceError` on that action. Safety net: source test forbids the names anywhere; `node --check` does not catch it, so the browser sequence exercises toasts, history and filters.
- Blast radius: `templates/products.html` only (Product, Genoray, Vieworks pages).

# Product Inventory Batch 3: Faster Page Load

**Status:** Executed — commit `9669649` (Batches 3 and 4 published together to `origin/main` on the owner's "commit and push").
**Finished:** 2026-10-07.

**Where the plan and the outcome differed:**

- `get_clients?fields=basic` returns `name or ''` (the page lower-cases names); full rows always include `product_count`/`group_name`, so the route test checks `product_count` rather than `contacts` (contacts are flattened into `cp1…` keys only when present).
- `product_vieworks_link_payload_map` loads all link rows and all Vieworks items once (with owners joined) and filters in Python; same item shape and case-insensitive fallback as `product_vieworks_linked_items`.
- `deleteProduct` also refreshes the Vieworks options after a delete (a deleted product frees its links) — verified in the browser.
- `tests/test_genoray_inventory.py` pinned `'/api/genoray/summary'` as a template marker; it now asserts the route still exists in `app.py` instead (the page no longer calls it). `tests/test_vieworks_inventory.py` checks that marker against `app.py` already, unchanged.
- Fail-first: all 4 tests in `tests/test_product_inventory_batch3.py` failed on the unchanged code (`/get_products` went from 100 to 106 SQL statements when 3 products with Vieworks links were added); after, the count is flat and the payload equals `product_vieworks_link_payload` per product.
- Browser (built-in, local server on a copy of `scheduler.db`; engineer `kent` on `localhost`, and the copy's superadmin `hanna` with a generated test password set only in the copy, signed in on `127.0.0.1` so the local session was untouched; signed out, copy and launch entry removed):
  - Load: the catalog, `/get_products`, `/get_clients?fields=basic` and `/api/vieworks/items` all start within 5 ms of each other (~806 ms after navigation) and finish by ~1,490 ms, i.e. data ready ~0.68 s after DOM ready (was ~1.24 s with the waterfall). No summary request. Client list 11 KB (full list 18 KB). Single-request server times on this machine were noisy (~0.1–0.4 s each) and are not claimed as a gain.
  - Footer "Showing 102 of 102" after Add, "101 of 101" after Delete; Delete sent only `DELETE /delete_product/ZZB3ADD` and `GET /api/vieworks/items`, removed the row, and freed its Vieworks link.
  - `?edit=MPF16817600` auto-opens Edit with the legacy-name placeholder after both loads.
  - `/vieworks` and `/genoray` load without a summary or catalog request; footers correct. No console errors.
- Full suite before the combined Batch 3 + 4 publish: 24 failures, 3 errors, 5 skips — the same failing tests by name as the pre-Batch-1 baseline.
**Approved:** 2026-10-07 — the owner asked to "plan batch 3 and 4"; Batches 3 and 4 publish together in one push.
**Detailed:** 2026-10-07.

## Context

The browser check of `/products_page` (local copy, 101 products) showed the data requests running one after another: the Product Name list (~0.46 s) finishes before the three main requests start, and the Vieworks list waits for those, so the table appears ~1.4 s after the page loads. The page also downloads more than it needs and the server makes one query per product for owners and Vieworks links. Batch 4 (cleanup) follows in the same push.

## Decisions taken

1. Same data on screen; only fewer/smaller/parallel requests and fewer server queries.
2. `/get_clients` keeps its current response for every existing caller; the light form is opt-in by query parameter.
3. One service-worker bump (`v259`) and one release item for Batches 3 + 4.

## Investigation

1. **Waterfall** (`templates/products.html`): `DOMContentLoaded` does `await loadProductNameCatalog(); await loadData();` (~`:935`). `loadData` (`:1026`) runs items, `/get_clients` and the summary in `Promise.all`, then `await loadVieworksLinkOptions()` afterwards. Nothing in `loadData`'s rendering needs the catalog; only the `?edit=` auto-open (`openEditModal` → `setProductNameForEdit`) does, and it runs after both.
2. **Summary request is redundant here.** `productSummary` is read only for `total_products` (`updateProductCountFooter`), which equals `productsData.length`; the footer chips are already counted client-side. The summary routes (`app.py` `get_products_summary` ~33333 and the Genoray/Vieworks equivalents) each load every row again.
3. **`/get_clients` is heavy** (`app.py` ~32976): runs `repair_recent_online_tsr_contacts_for_medical_centers()` (a write path) on every call, loads all `Contact` rows, product counts and contact payloads. This page uses only `id`, `name`, `address` (`masterClients`, `nameCounts`, autocomplete, `openEditModal`). Other callers (`clients.html`, `timeline.html`, `travel_request.html`, …) need the full shape.
4. **Per-row queries in `/get_products`** (`app.py` ~33282): `p.owner.name` lazy-loads the `Client` per product (`Client.products` backref `owner`, `lazy=True`, `app.py:2057`); `product_vieworks_link_payload(p.serial_number)` (`:3124`) runs a link query plus `db.session.get(VieworksItem, …)` and owner loads per product (`product_vieworks_linked_items`, `:3103`). Calibration lookups are already batched (`latest_approved_calibration_certificates_for_products`, `latest_approved_calibration_approvals_for_equipment`).
5. **Delete reloads everything.** `deleteProduct` calls `await loadData()` after success (4 requests); Save already updates the one row via `updateProductListAfterSave`.

## Execution steps

1. **Parallel start**: in `DOMContentLoaded`, `await Promise.all([loadProductNameCatalog(), loadData()]);` (rest unchanged). In `loadData`, run `loadVieworksLinkOptions()` inside the same `Promise.all` as the other requests (it already no-ops on Genoray/Vieworks pages). Done: in the network panel all data requests start within a few ms of each other.
2. **Drop the summary request**: `loadData` no longer fetches `inventorySummaryUrl`; `updateProductCountFooter` uses `productsData.length`; remove `productSummary`, `inventorySummaryUrl` (JS const and Jinja `inventory_summary_url`) and the `productSummary.total_products = …` line in `updateProductListAfterSave`. Done: footer "Showing X of Y" correct after load, filter, add and delete.
3. **Light client list**: `get_clients` — when `request.args.get('fields') == 'basic'`, return `[{'id', 'name', 'address'}]` ordered by name right after the HR-schedule-only branch, **before** the contact repair. The page fetches `/get_clients?fields=basic`. Done: response has only those keys; other callers' responses are byte-for-byte unchanged (test compares a no-parameter call before/after keys).
4. **Batch owners and Vieworks links in `/get_products`**: `Product.query.options(db.joinedload(Product.owner))`; new helper `product_vieworks_link_payload_map(serials)` next to `product_vieworks_link_payload` — one query for all `ProductVieworksLink` rows, one for the referenced `VieworksItem`s (with owner joined), same case-insensitive fallback as `product_vieworks_linked_items`, same per-item dict shape; `get_products` uses the map. `product_vieworks_link_payload` stays for its other callers. Done: query count for `/get_products` no longer grows with the number of products (measured with SQLAlchemy `before_cursor_execute` in the test).
5. **Delete updates in place**: on success, remove the row from `productsData` and call `applyFilters()` (non-standalone pages also `loadVieworksLinkOptions()` since a deleted product frees its links). Done: deleting on the copy removes the row and the count drops by one with no other requests.
6. **Tests** — `tests/test_product_inventory_batch3.py`: source checks (no `inventorySummaryUrl`/`productSummary`; `Promise.all([loadProductNameCatalog(), loadData()])`; `/get_clients?fields=basic`; `deleteProduct` has no `loadData()`); route tests — `/get_clients?fields=basic` returns exactly `id,name,address`; `/get_clients` without the parameter still returns `contacts`; `/get_products` returns the same JSON for a fixture with 2 owners and a Vieworks link as `product_vieworks_link_payload` would, and its SQL statement count with 3 products equals the count with 6. Fail-first for each (the query-count test must fail on the current code).
7. **Release bookkeeping**: service worker `v259-product-inventory-speed` (v258 kept as marker); `releases.json` entry `2026-10-07-product-inventory-speed` (admins, engineers; Inventory): "Product, Genoray and Vieworks inventory open faster." Use the actual date of execution if later. `changes.md`; this plan's status.

## Deliberately excluded

- **Caching or pagination** of `/get_products` — not needed at ~100 rows.
- **Changing `/get_clients` default output or the contact repair** — other pages depend on it; the repair's placement is a separate question.
- **Calibration batching** — already batched.
- **Removing the summary routes** — kept for safety; just not called by this page.

## Verification

- Fail-first, then focused modules: batch 1–4 files, `test_product_inventory_mutations`, `test_product_vieworks_links_history`, `test_product_calibration_certificate`, `test_operational_equipment_workflows`, tests that call `/get_clients` (`grep -l "get_clients" tests/`), `test_changelog_coverage`, `test_sw_cache_version`. Full suite once before the Batch 3 + 4 publish, compared by test name with the baseline (24 failures, 3 errors, 5 skips).
- Browser (built-in, local server on a copy of `scheduler.db`, restart after template edits, viewport set explicitly): network timing for `/products_page` before/after (start times and when the table renders), footer counts, owner autocomplete (incl. duplicate-name address hint), Vieworks link options, add/edit/delete (delete needs an admin session — create a test admin on the copy only, remove afterwards), `?edit=<serial>` auto-open, `/genoray` and `/vieworks` load; no console errors. Remove the copy, test account and launch entry; reset the viewport.

## After implementation

1. Self-review: every function the page calls is defined; other `/get_clients` and `/get_products` callers untouched (Medical Centers, Calendar/timeline, Travel Request, dashboard).
2. Record fail-first proof, timings and browser results here; `changes.md`; status `Executed — not yet committed`.
3. After Batch 4 is also executed, on the owner's "commit and push": full suite once; stage explicit files only (`templates/products.html`, `app.py`, `static/changelog/releases.json`, the new batch test files, any updated test, `plans.md`, `changes.md`); never `scheduler.db`, `changes-archive.md`, handoffs, `.claude/`, `.impeccable/`, `output/`, `tmp/`. Push once; confirm `origin/main` only (owner confirms the Railway deploy).

## Risks

- **`joinedload` on a backref** or the link map returning a different shape → the JSON-equality test and the Vieworks history tests catch it.
- **Light `/get_clients` used where contacts are needed** → only `products.html` opts in.
- **Parallel catalog load** races the `?edit=` auto-open → it runs after both promises resolve.
- Blast radius: `templates/products.html` (three inventory pages), two read-only routes in `app.py`, service worker, release note; no schema change.

# Product Inventory Batch 2: Desktop Table Fit and Compact Phone Cards

**Status:** Executed — commit `6eab0c7` (Batches 1 and 2 published together to `origin/main` on the owner's "commit and push").
**Finished:** 2026-10-07.

**Where the plan and the outcome differed:**

- Step 3: hiding the Room cells alone shifted every following column's width (the `<col>` still took a slot); `.product-room-empty col.product-col-room` is `display: none` instead of `width: 0`.
- Step 5: no width tuning was needed — at 1440 px the table is exactly the wrapper width. At 1366 px it overflows by 53 px (S/N is held at ~188 px by the "No calibration record" badge); the scrollbar and hint cover it, as planned.
- Added (found by the browser check, same cards): phone "View Report/Certificate" links raised from 38 px to 44 px (`min-height: 2.75rem`); the phone card name was invisible in dark mode because the shared dark stylesheet styles `.product-mobile-title`, not `.product-mobile-name` — added `:root[data-app-theme="dark"] .product-mobile-name` (pre-existing on production).
- Tests: `test_product_calibration_certificate` pinned the old 1600 px hint media query and `product-col-date { width: 7rem; }`; updated to the new rule and 6.5rem.
- Fail-first: all 5 tests in `tests/test_product_inventory_batch2.py` failed on the Batch-1 template. After: batch 1 + 2 files, `test_product_table_column_resize`, `test_product_calibration_certificate`, `test_product_vieworks_links_history`, `test_changelog_coverage`, `test_sw_cache_version` OK; `node --check` OK. `test_product_room_catalog` passes alone; its three failures when run after the calibration/Vieworks modules also occur with the original template (shared-database seeding order), so they are not from this batch.
- Browser (built-in, local server on a copy of `scheduler.db`, engineer `kent`; copy and launch entry removed). Note: the dev server caches templates (`FLASK_DEBUG=false`), so it was restarted after each template edit; emulated resizes in the hidden pane do not fire `resize`, so live-resize checks dispatched the event the browser normally sends.
  - 1440 px: table 1073 / wrapper 1073 (was 1320 / 1073), headers S/N 192, Name 212, Room hidden, BSID 114, Owner 196, Start 106, End 106, Status 147; average row 75 px (was 76); scroll hint hidden. 1366 px: 1052 / 999, hint and scrollbar shown. 1920 px: 1553 / 1553, rows 68 px.
  - Freeze through Status / BSID / Name gives correct offsets with Room hidden; Room freeze option hidden; column resize and Reset widths work; sort by End Date works.
  - After giving one product a room on the copy, the Room column (118 px) and freeze option return; the table then overflows at 1440 px and the hint shows.
  - 375 px: typical card 216 px (was 528), with calibration links 281 px, list 23,875 px (was ~54,000), card left edge 28 px (was 44), no sideways scroll, no tap target under 44 px; meta line e.g. "Room X-Ray 2 · 2020-06-27 – 2022-06-26 · No Contract"; Edit and History open. 768 px: cards 216 px, no sideways scroll; dark theme name readable.
  - `/vieworks` (one item added on the copy) and `/genoray`: phone card, edit, desktop table fit (1088 / 1088), Room hidden. No console errors.
  - Print: print CSS unchanged (mobile list, hint and scrollbar hidden; table printed); not print-previewed.
- **Regression found after publish (2026-10-07, owner screenshot):** Step 2 let the date headers wrap, but the existing `overflow-wrap: anywhere` on table cells broke them inside words ("St/art/Da/te", header row 111 px). The Batch 2 browser check measured widths only and missed it. Fixed with `.product-table-wrap thead th { overflow-wrap: normal; }`; header row 87 px, headers wrap only between words.
- Full suite before the combined publish: 1,593 tests, 24 failures, 3 errors, 5 skips — the same failing tests by name as the pre-batch code (baseline run with both batches stashed). A first run showed one extra `test_purchase_orders` failure: a 429 from the shared `/login` rate limit, because the new Batch 1 route test logged in through `/login`; it now signs in through the test session instead.
**Approved:** 2026-10-07 — the owner asked to "plan batch 2" and set the publishing rhythm: Batches 1 and 2 are published together in one "commit and push" (two batches per push from now on, to save Railway deploys).
**Detailed:** 2026-10-07.

## Context

The browser check of `/products_page` (local server on a copy of `scheduler.db`, 101 products) found the desktop table does not fit even at 1440 px, and the phone list is very long. Batch 1 (safety fixes, executed, not yet committed) is in the same file; both batches go out in one push.

## Decisions taken

1. Batches 1 and 2 publish together: **one** service-worker bump (Batch 1's `v258`, suffix renamed) and **one** release entry with a second item. No push after Batch 2 until the owner says "commit and push".
2. Keep all eight desktop columns, their order, sorting, freeze and resize behaviour. Only widths, wrapping and the empty-Room case change.
3. Phone gutter follows the shell standard (`--mobile-safe-padding`, 14 px on `.main-content` and `.container-fluid`, `static/css/app-shell.css:738`), as decided for Medical Centers (`71a21b0`): drop this page's extra card padding rather than override the shell.
4. On phone cards, empty values are left out instead of shown as filler ("Room: —", "BSID: Not assigned"). The desktop table keeps its "-" placeholders.

## Investigation

Measured in the browser at 1440 × 900 (sidebar open; table wrapper 1073 px) and 375 × 812.

1. **Table overflow at 1440 px:** table 1320 px in a 1073 px wrapper; End Date and Status are cut off. Header widths: S/N 229, Name 208, Room 128, BSID 112, Owner 192, Start 159, End 148, Status 144. Average row height 76 px.
2. **Why S/N is 229 px:** column 1 is `white-space: nowrap` (`templates/products.html` ~2498); in an auto-layout `width: max-content` table (~2477) the "View Report" and "View Certificate" links in `.product-serial-document-actions` (~2808, `flex-wrap: wrap`) sit side by side because the cell takes its max-content width.
3. **Why dates are ~150 px:** columns 6–7 are `nowrap`, including the header button "Start Date ↕"/"End Date ↕" (the indicator becomes "Oldest"/"Newest" when sorted). The data is 10 characters.
4. **Room is 128 px with no data:** `.product-col-room { width: 8rem; }` (~2487); Room is empty on all 101 local products. BSID is empty on 99 but is used (certification).
5. **Scroll hint always shows at 769–1600 px** (`@media … max-width: 1600px { .product-table-scroll-hint { display: flex } }`, ~2802), even when nothing overflows. `updateProductTableHorizontalScroll` (`:847`) already computes `isOverflowing` for the scrollbar.
6. **Phone cards (375 px):** card 528 px tall, list ≈ 54,000 px for 102 cards; first card starts at y = 573. `.product-mobile-top` (~2978) is a two-column flex: everything (S/N, calibration, name, room, Vieworks, BSID, owner) is squeezed into a 102 px column because the status badge takes the right side. Owner wraps to 4 lines. Dates are two bordered boxes stacked vertically (`.product-mobile-dates { grid-template-columns: 1fr }` at ≤768 px, ~3274), then a separate "No Contract" line. Card left edge at 44 px: shell 14 + `.container-fluid` (shell) + this page's `.container-fluid > .card { padding: 1rem }` (~3167).
7. Markup source: `renderProductMobileCards` (`:1343` before Batch 1; same function after). `getWarrantyBadgeClass` is used only by it.
8. Tests that read this CSS/markup and must keep passing: `tests/test_product_table_column_resize.py`, `tests/test_product_room_catalog.py` (Room markup), `tests/test_product_calibration_certificate.py` (identity cell / mobile links), `tests/test_product_vieworks_links_history.py`.

## Execution steps

1. **S/N column narrower** (`templates/products.html` CSS): `.product-identity-cell .product-serial-document-actions { flex-direction: column; align-items: flex-start; }` so the two document links stack; the calibration badge may wrap (`.product-identity-cell .product-calibration-summary { white-space: normal; }`). Done: S/N header ≤ 150 px at 1440 px with current data.
2. **Date headers wrap, data does not**: remove columns 6–7 header buttons from `nowrap` (keep `td` nowrap); `.product-col-date { width: 6.5rem; }`. Done: Start/End headers ≤ 115 px each.
3. **Room column hides when empty**: in `renderTable`, `table.classList.toggle('product-room-empty', !data.some(p => String(p.room || '').trim()))` based on **all loaded rows** (`productsData`, not the filtered set, so filtering never makes the column jump). CSS: `.product-room-empty :is(th, td):nth-child(3) { display: none; }` and `.product-room-empty col.product-col-room { width: 0; }`; hide the "Room" option in `#product-freeze-column` while empty (if Room was the saved freeze choice it still freezes the same number of columns). `.product-col-room { width: 5rem; }` for when Room has data. Freeze offsets already read live header widths (`applyProductFreezeColumn`), and the resize keys stay index-based on the unchanged markup. Done: with no rooms the column is absent; adding a room on the copy brings it back.
4. **Scroll hint only when needed**: in `updateProductTableHorizontalScroll`, toggle `.is-overflowing` on `.product-table-scroll-hint` together with the scrollbar; replace the 769–1600 px media rule with `.product-table-scroll-hint.is-overflowing { display: flex; }` (still hidden on phones and in print). Done: no hint when the table fits; hint shows at widths that overflow.
5. **Measure and tune** at 1366, 1440 and 1920 px: target **no overflow at 1440 px** (sidebar open) with the current data, row height ≤ 76 px; tune only the `.product-col-*` starting widths (name 12rem, owner 11rem are the first candidates) if still a few px over. Record the measurements.
6. **Phone card layout** (`renderProductMobileCards` + mobile CSS): new header line `.product-mobile-head` = S/N (left) + status badge (right); below it, full width: calibration links/badge, name, Vieworks links, owner (one line where it fits), then one meta line `Room X · BSID Y · <start> – <end> · Under Contract/No Contract` built only from non-empty parts (dates show "No dates" if both are empty), then the actions row. Remove `.product-mobile-dates`, `.product-mobile-date-box`, `.product-mobile-contract` markup and their CSS (including the ≤768 px `grid-template-columns: 1fr` override). Keep every action button, its classes, sizes (≥ 44 px) and handlers from Batch 1. Done: typical card ≤ 280 px tall.
7. **Phone gutter**: at ≤768 px, `.container-fluid > .card { padding: 0 !important; background: transparent; box-shadow: none; }` (replacing `padding: 1rem !important`), matching the Medical Centers approach. Done: card left edge = 28 px, no sideways scroll.
8. **Tests** — extend `tests/test_product_inventory_batch1.py` or add `tests/test_product_inventory_batch2.py` (source-level): document links stack (`flex-direction: column` under `.product-identity-cell`); `product-room-empty` toggle in `renderTable` using `productsData`; scroll hint toggled with `is-overflowing` and no `max-width: 1600px` hint rule; `renderProductMobileCards` has `product-mobile-head` and no `product-mobile-date-box` / `Room: ${` / `BSID: ${escapeHtml(p.bsid || 'Not assigned')}`; the ≤768 px card rule has `padding: 0`. Each must fail on the current template. Keep the existing product test modules passing (Investigation 8), updating only assertions that pin the removed date-box markup.
9. **Release bookkeeping (shared with Batch 1)**: rename Batch 1's service-worker suffix to `v258-product-inventory-fixes-layout` (one bump for the push; v257 stays the historical marker); add a second item to the `2026-10-07-product-inventory-fixes` release entry ("The inventory table fits wider screens without sideways scrolling when Room is unused, and phone cards are about half as tall."); `changes.md`; this plan's status.

## Deliberately excluded

- **Removing or merging desktop columns** (e.g., folding Room into Name) — changes sort/freeze/resize keys and saved widths; hiding Room only when it is empty everywhere covers today's data.
- **Pagination or virtual scrolling** of phone cards — halving card height is enough for ~100 products.
- **Request waterfall, lighter client list, per-row queries** — Batch 3. **Dead-code cuts** — Batch 4.
- **Shell gutter change** — app-wide; out of scope (same decision as Medical Centers).
- **Print layout** — prints the desktop table; only verified, not redesigned.

## Verification

- Fail-first for every new assertion, then focused modules: batch test file(s) + `test_product_table_column_resize`, `test_product_room_catalog`, `test_product_calibration_certificate`, `test_product_vieworks_links_history`, `test_product_inventory_mutations`, `test_changelog_coverage`, `test_sw_cache_version`; `node --check` on the page script. Full suite once before the combined Batch 1 + 2 publish, compared with the baseline (24 failures, 3 errors, 5 skips).
- Browser (built-in, local server on a copy of `scheduler.db`; engineer `kent` session; viewport set explicitly because the hidden pane reports width 0):
  - 1366 / 1440 / 1920 px: table width vs wrapper, header widths, average row height, scroll hint shown only when overflowing; sort, freeze (including "S/N", "Product Name + Actions", "Status"), column resize and Reset widths still work; Room column absent, then present after giving one product a room on the copy;
  - 375 px and 768 px: card height, list height, first-card top, left edge 28 px, no sideways scroll, all buttons ≥ 44 px, Edit/Delete/History/PM still work; cards with and without calibration links, linked Vieworks, BSID, room, dates;
  - `/genoray` and `/vieworks` at 1440 and 375 px;
  - print preview layout (Print button) still shows the table;
  - dark theme glance at both widths; no console errors.
  - Remove the copy and the temporary launch entry; reset the viewport.

## After implementation

1. Self-review the diff; confirm every function the page calls is still defined (`renderTable`, `renderProductMobileCards`, `getWarrantyBadgeClass`, `applyProductFreezeColumn`, `updateProductTableHorizontalScroll`, `setupProductColumnResizers`, `resetProductColumnWidths`, `setProductFreezeColumn`) and that Import, Export, Print, Add, Edit, Save, Delete, PM and Service History still work on all three inventory pages.
2. Record fail-first proof, measurements and browser results under this plan.
3. Service worker suffix and the second release item (step 9).
4. Update `changes.md` and this plan's status (`Executed — not yet committed`).
5. Wait for the owner's "commit and push", then publish Batches 1 and 2 together: run the full suite once; stage explicit files only (`templates/products.html`, `app.py`, `static/changelog/releases.json`, the batch test files, `tests/test_product_calibration_certificate.py`, `plans.md`, `changes.md`, `AGENTS.md`); never `scheduler.db`, `changes-archive.md`, handoffs, `.claude/`, `.impeccable/`, `output/`, `tmp/`. Verify `origin/main` and the Railway deployment; set both plans to `Executed` with the commit hash.

## Risks

- **Hiding Room shifts freeze offsets or resize handles** → offsets come from live header widths and the hidden column keeps its index; verified by freeze/resize checks with Room hidden and shown.
- **Saved column widths** (`medicalServiceProductColumnWidthsV1`) from before may still force a wide table for users who resized → "Reset widths" clears them; widths are only restored if valid, unchanged behaviour.
- **Phone card rewrite drops an action or link** → actions block reused unchanged; source test + browser check of every button type.
- **Overflow target missed at 1366 px** with long owner names → target is 1440 px; the scroll hint and scrollbar still cover narrower widths.
- Blast radius: `templates/products.html` (Product, Genoray, Vieworks pages), the service-worker suffix and the release entry; no schema or route change.

# Product Inventory Batch 1: Safety and Correctness Fixes

**Status:** Executed — commit `6eab0c7` (Batches 1 and 2 published together to `origin/main` on the owner's "commit and push").
**Finished:** 2026-10-07.

**Where the plan and the outcome differed:**

- Step 8: the forced-rename logic is a small helper `setProductNameForEdit(name)` called by `openEditModal` (and by `openAddModal` with `''` to reset), instead of inline code. Default placeholder and warning text are saved in `data-` attributes at startup so Add mode and catalog-matched names look as before. `syncProductNameCatalogSelection` keeps the warning visible while a legacy name is pending even if the field is empty.
- Step 7: no `aria-label` on the row (it would hide the row's cell text from screen readers); `tabindex="0"`, the guarded key handler and a 2 px `:focus-visible` outline only.
- `saveProduct`'s two identical `updateProductListAfterSave` branches were merged while adding step 6 (same behaviour).
- Tests: `tests/test_product_calibration_certificate.py::test_products_markup_keeps_identity_actions_and_accessible_states` pinned the old `openEditModal('${serial}')` text; updated to the `productJsArg` form.
- Fail-first: the 7 template tests in `tests/test_product_inventory_batch1.py` failed on the unchanged template; the P.O. route test passed (positive control). After: new file + `test_product_calibration_certificate` + `test_product_vieworks_links_history` + `test_product_table_column_resize` + `test_changelog_coverage` OK; page script `node --check` OK.
- Pre-existing, not caused by this batch: `test_product_contract_status.test_product_save_stays_in_place_without_refetching_page_data` fails on the unchanged template too (expects `updateProductListAfterSave(data, editSN);`); three `test_product_room_catalog` tests fail only when run after `test_product_inventory_mutations`/`test_product_name_standardization` in one process (catalog seeding order on the shared test database), with or without the new test file. Full suite not yet run (runs once before publishing).
- Browser (built-in, local server on a copy of `scheduler.db`, engineer `kent`; copy seeded with serial `AB'12"\X`, an HTML-named client, two Vieworks items and one P.O.; copy and launch entry removed): 1440 px — Edit, History, highlight, Enter-on-row all work for `AB'12"\X`; Enter on the Edit button opens only Edit; real Shift+Tab focus shows the 2 px outline; HTML client name shows as text, nothing executed; active-count icon renders; legacy "MobileDart Evo MX7c" opens with an empty field, placeholder and warning naming it, Save blocked, picking "MobileDart Evolution MX7c" saved; after linking VWTEST1 to that product, the second product of the same client offered only VWTEST2; a date-only edit showed only "Product updated."; an owner change showed "1 linked P.O.(s) still name the previous owner…"; Add mode reset to the default placeholder. 375 px — card Edit/History/Enter work for the tricky serial, no sideways scroll, no tap target under 44 px. Delete handler markup evaluated without error for the tricky serial (engineer has no Delete; server permission unchanged). `/vieworks` edit + history and `/genoray` add (`GN'TEST1`) + edit + history work, names untouched. No console errors.
**Approved:** 2026-10-07 — after a source scan and a browser check of `/products_page`, the owner asked to "plan batch 1" and decided legacy names stay blocked: "don't let them save. force a rename from the product name list".
**Detailed:** 2026-10-07.

## Context

A source review and a browser check of the Product Inventory page (`templates/products.html`, `/products_page`; local server on a copy of `scheduler.db`, engineer `kent`, 101 products) found two confirmed security/correctness bugs (client-name HTML runs code in the Owner autocomplete; serials containing `'` break every row button), a blank icon, stale Vieworks link options after a save, a P.O. warning the server sends but the page never shows, desktop rows that cannot be opened from the keyboard, and a legacy-name edit flow that blocks the user without showing them the list. The same template drives `/genoray` and `/vieworks`, so every fix reaches all three pages. Layout, load speed and dead-code cleanup are later batches.

## Decisions taken

1. **Legacy product names are not saveable.** 77 of 101 local products have names outside the Product Name catalog. Save stays blocked until a catalog name is chosen (current server rule in `update_product`, `app.py` ~62885, kept). This batch only makes the forced rename easier to complete; it does not add a "keep current name" path.
2. Fix with the smallest change in the existing template; no new endpoints, no refactor of how rows are rendered.
3. The page-access question (stock-inventory-only users can open `/products_page`) is **not** in this batch; it needs a separate owner decision.

## Investigation

Verified in code and, where noted, in the browser on a database copy (copy removed afterwards).

1. **Autocomplete HTML injection — confirmed in browser.** `setupAutocomplete` (`templates/products.html:1174`) builds each result with `div.innerHTML = \`<strong>${displayName}</strong>\`` (`:1204`), where `displayName` is the client name plus address. A client named `Zz <img src=x onerror=...>` (injected into `masterClients` in the page only) executed its handler.
2. **Apostrophe serials — confirmed in browser.** Inline handlers are built as `onclick="...openEditModal('${escapeHtml(serial)}')"`. The browser decodes `&#039;` back to `'` before running the handler, so serial `ZZTEST'01` (accepted by `/add_product`, created only in the copy) produced `openEditModal('ZZTEST'01')` → `SyntaxError`, modal never opened. Same pattern at: row Edit `:1320`, row Delete `:1327`, mobile Edit `:1375`, mobile Delete `:1382`, mobile card history click and keydown `:1388`, desktop row history `:1760`, history-modal linked-equipment buttons `:1498` (uses `productEscape` inside `'…'`, same flaw). `highlightAndScroll` (`:576`) puts the serial unescaped into `querySelector('[data-serial="…"]')`.
3. **Blank icon — confirmed in browser.** `fa-shield-check` (`:176`) has no glyph in Font Awesome 6.4 free (`::before` content `none`). Settings already replaced it with `fa-shield-halved`.
4. **Stale Vieworks link options.** `vieworksData` is filled only in `loadData` (`:1044-1052`). `saveProduct` (`:1941`) updates the product row in place via `updateProductListAfterSave` (`:1813`) and never refreshes `vieworksData`, so a Vieworks item just linked to product A still appears as available when editing product B of the same client; the server then rejects it (`validate_product_vieworks_links`, `app.py:3172`).
5. **P.O. review warning not shown.** `update_product` returns `linked_purchase_order_count` on every success (`app.py` ~63107 serial-change path, ~63145 normal path) and logs "N linked P.O.(s) require a machine-owner review" when the owner changes (~63139). `saveProduct` ignores it. On the serial-change path the P.O. rows are moved automatically, so only an owner change needs a warning.
6. **Keyboard access.** Desktop rows (`:1760`) open Service History on click only — no `tabindex`, no key handler. Mobile cards (`:1388`) already have `role="button" tabindex="0"` and Enter/Space.
7. **Legacy name flow — confirmed in browser.** `openEditModal` (`:1878`) puts the legacy name in `#p-name`; `syncProductNameCatalogSelection` (`:524`) shows "Legacy product name — select a standard Product Name before saving."; `saveProduct` blocks with "Validation Error: Select a standard Product Name from the list before saving." Because the input still holds the legacy text, the `<datalist>` filters to that text and usually suggests nothing, so the user must first clear the field to see the list. The warning does not say which name is legacy. Server side is already enforced and tested (`tests/test_product_name_standardization.py::test_product_edit_requires_catalog_and_canonicalizes_name`).
- Worked correctly in the browser (no change needed): loading state, filters, sort, Clear Filters, Service History, edit-save updates the row in place, engineer Delete refused (403), no sideways page scroll at 375 px, no console errors in normal use.

## Execution steps

1. **Safe handler arguments** (`templates/products.html`): add `function productJsArg(value){ return escapeHtml(JSON.stringify(String(value ?? ''))); }` next to `escapeHtml`. Replace every `'${escapeHtml(x)}'` / `'${productEscape(x)}'` handler argument listed in Investigation 2 with `${productJsArg(x)}` (no surrounding quotes), including the `inventoryMode` / `item.source` second arguments for consistency. Done: a serial `AB'12"\` renders handlers that open Edit, Delete confirm and History for that exact serial.
2. **Selector escape**: in `highlightAndScroll`, use `` `[data-serial="${CSS.escape(serial)}"]` ``. Done: `?edit=AB'12` highlights without throwing.
3. **Autocomplete text only**: in `setupAutocomplete`, build `const strong = document.createElement('strong'); strong.textContent = displayName; div.appendChild(strong);` instead of `innerHTML`. Done: a client name containing HTML shows as literal text.
4. **Icon**: `fa-shield-check` → `fa-shield-halved` at `:176`. Done: icon visible.
5. **Refresh Vieworks options after save**: extract the Vieworks fetch in `loadData` into `async function loadVieworksLinkOptions()` (same body: skip when `isStandaloneInventory`, fetch `/api/vieworks/items`, fall back to `[]`). `loadData` calls it as before; `saveProduct` calls it (not awaited) after a successful non-standalone save. Done: after linking item X to product A, editing product B of the same client no longer lists X.
6. **P.O. warning**: in `saveProduct`, remember `existingInventoryItem?.client_id` before saving; on success, if not standalone, `editSN` is set, the client changed, and `responseData.linked_purchase_order_count > 0`, show `productToast('N linked P.O.(s) still name the previous owner. Review them in P.O. Details.', 'warning')` in addition to the success toast. Done: owner change on a machine with P.O.s shows the reminder; other saves do not.
7. **Keyboard rows**: desktop row gets `tabindex="0"` and `onkeydown="if((event.key==='Enter'||event.key===' ') && event.target===this){event.preventDefault();openProductHistory(...);}"` (arguments via `productJsArg`). The `event.target===this` check stops Enter on the Edit/Delete/PM controls from also opening History. Add a visible `:focus-visible` outline for `.product-clickable-row` in the page `<style>`. Done: Tab reaches rows, Enter opens History, Enter on the Edit button opens only Edit.
8. **Forced rename made usable** (`openEditModal`, `syncProductNameCatalogSelection`, warning element `#p-name-standardization-warning`): when the product's current name has no exact catalog match, put an empty value in `#p-name`, set its placeholder to `Pick a standard name (was: <legacy name>)`, and make the warning read `"<legacy name>" is not in the Product Name list. Pick a standard name before saving.` (text set with `textContent`). Save stays blocked exactly as today (Decision 1). Catalog-matched names behave as today. Standalone (Genoray/Vieworks) pages unchanged. Done: on a legacy product, Edit shows the empty name field with the full suggestion list on focus, the old name in the warning and placeholder; Save without a pick shows the existing validation error; picking a name saves.
9. **Tests** — new `tests/test_product_inventory_batch1.py` (source-level, like `test_templates_expose_standardization_controls`): no handler in `products.html` matches `\('\$\{(escapeHtml|productEscape)\(`; `productJsArg` defined and used; autocomplete block has no `innerHTML = \`<strong>`; `fa-shield-check` absent; `loadVieworksLinkOptions` defined and called from `saveProduct`; `saveProduct` reads `linked_purchase_order_count`; desktop row template contains `tabindex="0"` and `event.target===this`; `highlightAndScroll` uses `CSS.escape`; `openEditModal` sets the legacy placeholder text. Plus one route test: `PUT /update_product/<serial>` changing `client_id` on a machine with a `PurchaseOrderMachine` row returns `linked_purchase_order_count >= 1` (positive control for step 6's input). Each source assertion must fail on the current template.
10. **Release bookkeeping**: service worker `CACHE_VERSION` in `app.py` (~27094) bumped to the next number with suffix `product-inventory-fixes`, previous one kept as the historical marker comment; `static/changelog/releases.json` entry `2026-10-07-product-inventory-fixes` (audience: everyone who can open Product/Genoray/Vieworks inventory — follow existing entries for the exact audience keys; category Inventory or the existing products category); `changes.md`; this plan's status.

## Deliberately excluded

- **Keeping legacy names on save** — owner decision: rename is forced.
- **Page access for stock-inventory-only users** (`products_page` does not use `can_access_products_page`) — needs an owner decision; separate.
- **Desktop table fit, mobile card compaction** (Batch 2), **request waterfall / lighter client list / per-row queries in `/get_products`** (Batch 3), **dead-code cuts** (Batch 4) — separate batches to keep this one small and reviewable.
- **Server-side serial character rules** — the client fix makes any serial safe to render; restricting characters could reject existing data.
- **Bulk renaming the 77 legacy names** — Settings already has the Product Name standardization tool; using it on production is an owner/admin action, not code.

## Verification

- Fail-first: run `tests/test_product_inventory_batch1.py` on the unchanged template and record that the source assertions fail; the route test is a positive control and should pass before and after.
- Focused modules after the change: the new file + `test_product_inventory_mutations`, `test_product_name_standardization`, `test_product_vieworks_links_history`, `test_product_table_column_resize`, `test_product_contract_status`, `test_product_room_catalog`, `test_product_calibration_certificate`, `test_changelog_coverage`. Full suite once before publishing, compared with the baseline (24 failures, 3 errors, 5 skips).
- Browser (built-in, local server on a copy of `scheduler.db`, temporary `.claude/launch.json` entry; engineer `kent` session, plus an admin session on the copy for Delete):
  - add `AB'12` in the copy → row Edit, Delete confirm, History, mobile Edit/History all open for that serial; `/products_page?edit=AB'12` highlights it;
  - inject an HTML client name into the copy's `client` table → Owner autocomplete shows it as text, nothing executes;
  - "active" chip icon visible;
  - link a Vieworks item to product A, then edit product B of the same client → item not offered;
  - change the owner of a machine with a P.O. → warning toast; change only a date → no warning;
  - Tab to a desktop row, Enter → History; Tab to its Edit button, Enter → only Edit;
  - Edit a legacy-name product → empty name field, old name in placeholder and warning, full list on focus; Save without picking → blocked; pick a name → saved;
  - `/genoray` and `/vieworks` still load, add/edit/PM links work;
  - standing bar: 375 px no sideways scroll, tap targets ≥ 44 px, no console errors from normal use.
  - Remove the copy, test accounts and launch entry afterwards; reset viewport.

## After implementation

1. Self-review the diff. Confirm every function the page calls is still defined and still used by its callers (`openEditModal`, `deleteProduct`, `openProductHistory`, `saveProduct`, `loadData`, `setupAutocomplete`, `refreshVieworksLinkOptions`, `syncProductNameCatalogSelection`, `highlightAndScroll`), and that Import, Export, Print, Add, Save, Delete, PM links and Service History still work on all three inventory pages.
2. Record fail-first proof, test counts and browser results under this plan ("Where the plan and the outcome differed").
3. Service worker bump and `releases.json` (step 10).
4. Update `changes.md` and set this plan's status to `Executed` with the commit hash.
5. Commit and push only on the owner's "commit and push": explicit staging; never `scheduler.db`, `changes-archive.md`, handoffs, `.claude/`, `.impeccable/`, `output/`, `tmp/`. Verify `origin/main` and the Railway deployment.

## Risks

- **Handler rewrite misses a call site** → that button breaks for every serial. Safety net: the source test forbids the old pattern anywhere in the file, and the browser sequence clicks every button type on desktop and mobile.
- **Keyboard handler double-fires** with the row's click/Edit button → `event.target===this` guard and an explicit browser check.
- **Clearing the legacy name in the field** could confuse users who expect to see it → the old name stays visible in the placeholder and warning; nothing is saved until a catalog name is picked.
- Blast radius: `templates/products.html` (Product, Genoray, Vieworks pages) plus the service worker version and release note; no schema or route change.

# Reimbursement Package: Print-Ready Excel, Signature Placement, LPR Text

**Status:** Executed — commit `46e98dd`; published to `origin/main` on the owner's "commit and push" (Railway GitHub deployment `6899349510` succeeded).
**Finished:** 2026-10-07.

**Where the plan and the outcome differed:**

- Step 4 also fixes the **travel liquidation RFP** (`build_travel_liquidation_rfp_template_pdf`), which used the same template and the same misplaced box; both RFP builders now pass `REIMBURSEMENT_RFP_APPROVAL_STAMP_BOX = (135, 496, 123, 49)` with `force_fallback=True`. Rendered with a real approver signature: signature on the APPROVED BY line, nothing beside NOTED BY.
- Step 5: the box height is `23 + (field top − (box_y + 20)) / SIGNATURE_STAMP_SCALE`, because the overlay lets the signature grow to 1.5× its area; the overlay itself is unchanged. The PCV signature is now a little smaller (it must fit below the label).
- Step 6: the `_nudge_widget_down` was removed for `AMOUNTRow*` on both the field and its kid widgets.
- Step 7: pypdf's auto-size shrinks text well below what fits, so `lpr_fit_long_field_values` uses three tiers: fits one line at 10 pt → untouched (template auto-size, as before); else the largest one-line size from 9 to 6.5 pt; else two lines at 6/5.5/5 pt with the multiline flag; longer still → untouched. The 13.9 pt LPR rows physically limit two-line text to about 6 pt. Applied on the first page and continuation pages.
- Excel row height helper uses integer ceiling (no `math` import in `app.py`).
- Found, not fixed (out of scope, offered as a separate task): the travel liquidation RFP "Covering" text overflows its field and loses the trip dates; pypdf warns "→" is outside the form font encoding.
- Fail-first: all 8 tests in `tests/test_reimbursement_print_ready.py` failed on the unchanged code. After: those 8 + `test_lpr_workflow` + `test_reimbursement_total_consistency` + `test_changelog_coverage` pass except `test_lpr_workflow.test_standalone_lpr_creation_is_single_flight_and_idempotent` (403 from `/save_lpr`, untouched; one of the baseline failures). Full suite 1,580 tests, 24 failures, 3 errors, 5 skips (baseline counts).
- Render check (scratch database copy; packages for reimbursements 1, 2, 3, 8; LPRs with 3 and 10 items, short and long text; approved travel liquidations 1 and 2): Excel is A4 landscape (842×595) with "Page 1 of 2", every Work Details line visible, header words whole; RFP stamp in the APPROVED BY row with name/title/date under the line beside the form code; PCV signature below the label, amounts level with their items; LPR long "Intended for" on two readable lines, the equipment line single-line, continuation page the same, short LPR unchanged.
**Approved:** 2026-10-07 — the owner asked for the emailed approved Excel to be print-ready, then asked to check every other generated file for bugs and cut-off data; reviewed the findings, chose A4 for the Excel, and replied "approved".
**Detailed:** 2026-10-07.

## Context

When a reimbursement is approved, the engineer and accounting get the package ZIP (`build_reimbursement_package_zip_bytes`, `app.py` ~10818; also Download Package, `app.py` ~51005): the reimbursement Excel, PCV PDF, RFP PDF, All Receipts PDF and any linked LPR PDFs. The owner reports the Excel arrives "raw" with cut-off data and wants every file to be ready to print as-is.

## Decisions taken

1. Fix findings 1–5 below; items marked "note only" stay as they are.
2. Excel paper size: **A4** landscape, one page wide, as many pages tall as needed.
3. All 10 expense columns stay in the Excel (fixed accounting format), even when empty.
4. PCV/RFP form fields are not flattened — accounting may still type PCV NO. and account fields.

## Investigation

Method: on a scratch copy of `scheduler.db`, built the package for reimbursements 1, 2, 3 (approved, one with a 16-page receipt PDF) and 8 (18-row draft), plus a throwaway LPR with long text; converted the Excel to PDF with LibreOffice and rendered every PDF page with PyMuPDF. Scratch copy removed afterwards.

1. **Excel — High.** `build_reimbursement_excel_workbook` (`app.py` ~35955) sets every data row to a fixed 36 pt (`ws.row_dimensions[row_idx].height = 36`). Excel does not auto-fit rows with an explicit height, so Work Details (3–4 lines: client / task / equipment + serial) and Remarks are clipped on screen and on paper — the serial number line was already hidden in the sample. No `paperSize` (falls back to Letter), no footer/page numbers, not centred; "Representation" breaks mid-word at width 15 after fit-to-width scaling. A scratch prototype (computed row heights, A4, centred, page footer, retuned widths) printed with nothing cut off.
2. **RFP — High.** `reimbursement_stamp_approval_signature(writer, header, field_name='APPROVED BY', fallback_box=[44.65, 535.0, 213.85, 56.0])` (`app.py` ~37537). The RFP template's `APPROVED BY` field rect is `[45, 557, 258, 571]`, i.e. one row **above** its "APPROVED BY:" label (label at y 538–550; NOTED BY label at 576–589; lines at about y 596, 558, 519). The stamp box `[x1, y1-22, w, 56]` = y 535–591 puts the approver's signature beside **NOTED BY** and the name/title/date on top of the "APPROVED BY:" label.
3. **PCV — Medium.** PCV template `APPROVED BY` field `[360, 309, 442, 330]`, label at y 330–341. Same stamp box (y 287–343) lets the signature rise to y ~340, over the "APPROVED BY:" label. Name/title/date below the line are fine.
4. **PCV amounts — Low.** `reimbursement_apply_pcv_field_formatting` (`app.py` ~36473) applies `_nudge_widget_down` (−3 pt) to `AMOUNTRow*` as well as header underline fields, so amounts sit ~3 pt lower than their particulars and touch the row line.
5. **LPR — Medium.** `lpr_fill_pdf_bytes` (`app.py` ~73634) fills the official `forms/LPR FORM.pdf`; the template's auto-size fields shrink long "Intended for" text to ~4 pt and long item descriptions to ~6 pt (unreadable when printed). `lpr_fill_pdf_bytes` is shared by every LPR parent (reimbursement, travel request, cash advance — 9 call sites).
- Verified fine: all amounts, totals and amount-in-words; filled PCV/RFP fields carry appearance streams (9/9 each), so every viewer shows them; receipts are passed through as uploaded.
- Note only (not fixed): "AMOUNT PAID//REC'D" is a typo in the official RFP template; PCV/RFP/Excel "Date" is the generation date (the approval day for the emailed package, the download day for a later Download Package); the receipts file name uses `YYYYMMDD` while others use `MMDDYYYY`.
- Correction recorded: the PCV template is Letter (612×792) and the RFP is 8.5×13 (612×936), not A4 as first stated; the owner chose A4 for the Excel anyway.

## Execution steps

1. **Excel row heights** (`app.py`, next to `build_reimbursement_excel_workbook`): new `reimbursement_excel_row_height(texts_and_widths)` — for each wrapped text cell, lines = sum over `\n`-split segments of `ceil(len(segment) / chars_per_line)` where `chars_per_line ≈ column width × 1.1` (Calibri/Arial 10); height = `max(18, lines × 13 + 5)`. In the builder, replace the fixed `height = 36` loop with this helper using Work Details (col 12) and Remarks (col 13). Done: no data row has a fixed 36 pt height; a 4-line Work Details row is ≥ 57 pt.
2. **Excel layout**: data cells `Font(size=10)`, top-aligned, wrap on Work Details/Remarks (amount cells keep right alignment — note the existing `range(2, 12)` loop overwrites alignment without wrap; keep that for amounts). Widths: Date 11, Representation 13, Car Repair 10, Toll Fee 9, Gasoline 10, Transpo 10, Office/Field Items 11, Parking 9, Per Diem 10, Parking Coding 10, Others / Misc 11, Work Details 40, Remarks 34 (tune by render so no header word breaks). Done: header labels whole in the rendered PDF.
3. **Excel page setup**: `ws.page_setup.paperSize = ws.PAPERSIZE_A4`; keep landscape, `fitToWidth = 1`, `fitToHeight = 0`, print titles `$6:$6`, print area; add `ws.print_options.horizontalCentered = True`, footer `Page &P of &N`, margins left/right 0.3", top 0.5", bottom 0.6". Done: LibreOffice PDF is A4 landscape (842×595) with page numbers.
4. **RFP stamp**: in `build_reimbursement_rfp_template_pdf`, pass a measured box inside the APPROVED BY row, right of the label (approximately x 118–258, signature resting on the y ≈ 519 line, name/title/date just below it), with `force_fallback=True` so the misplaced template field rect is not used. Adjust the box from renders until: nothing in the NOTED BY row, nothing over the "APPROVED BY:" label or the "SPCAcctngRFP004-2016" footer. Done: rendered RFP shows signature + name block only in the APPROVED BY row.
5. **PCV stamp**: in `reimbursement_stamp_approval_signature`, when using the field rect, cap the box top at the field top (`y2`, the label's bottom) — box `[x1, y1 − 22, field_width, (y2 − (y1 − 22))]` — so the signature cannot rise into the label. Only the PCV uses this path (RFP moves to its own box in step 4). Done: rendered PCV signature sits between label and name, not over the label.
6. **PCV amounts**: in `reimbursement_apply_pcv_field_formatting`, stop nudging `AMOUNTRow*` widgets (keep the nudge for header underline fields). Done: amounts line up with their particulars in the render.
7. **LPR text**: in `lpr_fill_pdf_bytes` (first page and continuation pages), for "Intended for", "Equipment" and the `ITEM  DESCRIPTION*` fields set a fixed font (not auto-size) and multiline; pre-wrap the value with `\n` to the field width at that size (two lines at ~6.5 pt for the ~12 pt rows; drop to a 5.5 pt floor only if two lines are not enough). Implementation must confirm with pypdf 6.16.1 that the generated appearance honours `\n` and the fixed size; if it does not, draw these values in the existing overlay step instead of via the field. Done: rendered test LPR shows readable two-line text; short values look as before.
8. **Tests** (new `tests/test_reimbursement_print_ready.py`): Excel — a row with long Work Details/Remarks gets a height > 36 and A4/landscape/fitToWidth=1/footer set; RFP — the approval overlay's drawn signature lies inside the APPROVED BY row band (check the box passed to the overlay, or mock `reimbursement_approval_signature_overlay_pdf` and assert the box y-range is below the NOTED BY label and right of the APPROVED BY label); PCV — box top ≤ field top; PCV formatting — `AMOUNTRow1` rect unchanged after formatting; LPR — long "Intended for" value is wrapped and its field `/DA` is not size 0. Each must fail on the current code.
9. **Release bookkeeping**: service worker bump (read live; keep the old one as a historical marker); `releases.json` entry `2026-10-07-reimbursement-print-ready` (engineers + admins + approvers, category Reimbursement); `changes.md`; this plan's status.

## Deliberately excluded

- RFP template typo, generated-date behaviour, receipts file name format (note only, owner agreed).
- Flattening PCV/RFP fields (accounting may still fill PCV NO. and account fields).
- Hiding empty expense columns in the Excel (fixed accounting format).
- PCV/RFP template files themselves are not edited.
- Approver, accounting, travel and cash-advance screens are not changed (LPR text fix reaches them through the shared builder only).

## Verification

- Fail-first for every new test, then focused modules: the new test file + `tests.test_lpr_feature_switch` + LPR tests (`grep -l lpr_fill_pdf_bytes tests/`) + reimbursement PCV/RFP/Excel tests (`grep -l "build_reimbursement_excel_workbook\|pcv\|rfp" tests/`). Full suite once before publishing, compared with the baseline (24 failures, 3 errors, 5 skips).
- Render check (no browser needed — files, not pages): on a scratch database copy, rebuild packages for reimbursements 1, 2, 3 and 8 and a throwaway long-text LPR (and an 9+ item LPR for the continuation page); Excel → PDF via LibreOffice; render all PDFs with PyMuPDF and inspect: nothing clipped, A4 landscape with page numbers, header words whole, RFP/PCV stamps in their own rows, PCV amounts aligned, LPR text readable. Remove the copy afterwards.

## After implementation

1. Self-review the diff; confirm every changed builder is still called with the same signature (`build_reimbursement_excel_workbook`, `build_reimbursement_pcv_template_pdf`, `build_reimbursement_rfp_template_pdf`, `reimbursement_stamp_approval_signature`, `lpr_fill_pdf_bytes`) and Download Package / approval email / LPR downloads still produce files.
2. Record fail-first proof and render results here.
3. Service worker bump and `releases.json` (step 9).
4. Update `changes.md` and this plan's status.
5. Commit and push only on the owner's "commit and push": explicit staging; never `scheduler.db`, `changes-archive.md`, handoffs, `.claude/`, `.impeccable/`, `output/`, `tmp/`. Verify `origin/main` and the Railway deployment.

## Risks

- Signature placement has been retuned several times (S12A3B, S12A4G/H); a fixed RFP box depends on the current template — mitigated by render checks and by keeping the PCV on its field rect.
- The LPR change touches every LPR (travel, cash advance, reimbursement) — render each with short and long text; short values must look unchanged.
- Row height is an estimate (Excel has no autofit for generated files); err on the generous side so text is never clipped.
- Blast radius: generated documents only; no schema, route or UI change.

# Reimbursement: PC Code in Remarks (Required for Client Visits)

**Status:** Executed — commit `ccee353`; published to `origin/main` on the owner's "commit and push" (Railway GitHub deployment `6898927230` succeeded).
**Finished:** 2026-10-07.

**Where the plan and the outcome differed:**

- Step 5: instead of the readiness model calling the PC helpers, `collectReimbursementRowsForSave()` sets `pc_code_missing` per schedule row (needs a code and has none), and the readiness model and Submit only count `pc_code_missing` rows with an amount. Keeps `buildReimbursementReadinessSnapshot` self-contained (its node test extracts it alone). `save_reimbursement_draft` ignores the extra key.
- Lock: the select follows the existing `.reim-manual-category` lock (`disabled` + `reim-locked-field`) in `applyReimbursementStatusUi` rather than a CSS-only rule.
- The server helper is `reimbursement_rows_missing_pc_code(claim_rows)`; the check runs right before `reimbursement_lock_claim_schedules`.
- Fail-first: the three target tests in `tests/test_reimbursement_pc_code.py` failed on the unchanged code; the two "still allowed" route tests passed (positive control that the harness submits). After: the new file + `test_reimbursement_readiness` + `test_reimbursement_design` + `test_changelog_coverage` + `test_lpr_feature_switch` 71 tests OK; page script `node --check` OK; full suite 1,572 tests, 24 failures, 3 errors, 5 skips (baseline counts).
- Browser (built-in, local server on a database copy, engineer `kent`, June 2026 draft): required label only on medical-center rows; PC18 appended, PC20 replaced it, blank removed it; typing "- pc21" by hand set the select to PC21; desktop and mobile boxes stayed in sync; an amount on a DDH row with no code showed the "PC code" item and the draft still auto-saved; Submit stopped with "1 client-visit row needs a PC code in Remarks before submitting.", scrolled to the row and outlined only that select; picking PC18 cleared the item and the outline; at 375 px the select is 273 × 44 px with no horizontal scroll; locked lifecycle disables the selects; no console errors. Copy, test login and temporary launch entry removed.
**Approved:** 2026-10-07 — the owner asked for a PC code dropdown in the Remarks field, answered the two open rules, and replied "approved".
**Detailed:** 2026-10-07.

## Context

Accounting needs every reimbursement row tagged with a profit-centre (PC) code. The owner supplied the code list (two scans) and asked for a dropdown on the Reimbursement page's Remarks / Purpose field. The dropdown shows "PC18 - RA - R/F", but selecting it writes only `PC18`, placed at the end of the remarks text inside the same field — e.g. "Angeles Medical Center bla bla bla - PC18". The code is required on client-visit rows and optional on every other row.

## Decisions taken

1. **Code list** (single source of truth in the page script), grouped:
   - Medical: `PC18` RA - R/F · `PC19` RK - R/F FPD · `PC20` RB - CVS · `PC21` RL - CVS FPD · `PC22` RC - RAD · `PC23` RP - PARTS · `PC24` SMIP MFG
   - Admin: `PC26` Admin
2. **Storage:** the code lives in the existing `remarks` text — no new column, no migration. Format: `<remarks> - PCxx`; when remarks are empty, just `PCxx`.
3. **"Client visit" = a schedule row with a medical center.** A row needs a code when it is a schedule row (not manual), has a client/medical center, and has a claim amount > 0. Manual items and schedule rows with no medical center (In Office, Leave, Training, Travel, Traveling to Client, etc.) may carry a code but are never blocked.
4. **Enforced on Submit only.** Save Draft keeps working without codes. Zero-amount rows are ignored (they are excluded from submission anyway).

## Investigation

- Remarks textarea, desktop: `templates/reimbursement.html` ~5428 (`renderReimbursementRows`, last `<td>`); mobile card: ~5465. Both carry `data-row-key` and call `handleReimbursementRemarksInput(this)` (~5130), which mirrors the value to the peer box and calls `markReimbursementDirty()`.
- `collectReimbursementRowsForSave()` (~6635) reads remarks via `getActiveReimbursementRemarksSelector()` (~5105) and sends `remarks` per row; schedule rows send `shift_id`, manual rows `manual: true`. Nothing else needs to change for the code to be saved.
- Locking: `.reim-remarks` is styled read-only by `.reim-page.reim-locked` (~1974) and amount/remarks fields are not `disabled` on purpose (~5754 comment). The new select must follow the same lock (handlers already bail when `!reimbursementIsEditable()`).
- Schedule rows have no "client visit" flag. `Shift` has only `title`/`client_id`. `reimbursement_shift_row()` (`app.py` ~35279) gives `client`; saved rows store it as `ReimbursementRow.client_name` (`app.py` ~38013). Local DB (read-only query): 557 schedules, 352 with a client; In Office, Leave, Holiday, Training, TRAVEL and Traveling to Client titles never have a client; PM, Installation, Technical Checkup, Site Visit, Corrective always do.
- Readiness panel ("N items need attention"): `buildReimbursementReadinessSnapshot(options)` (~3704) builds `blockers`; its caller (~3868) passes `rows` from `collectReimbursementRowsForSave()`. `tests/test_reimbursement_readiness.py` extracts this function and runs it in node — the new blocker can be tested the same way.
- `submitReimbursement()` (page ~7371) saves the draft first, then posts to `/submit_reimbursement` (`app.py` ~50669), which loads `saved_rows` and filters `claim_rows` with `reimbursement_row_has_claim_amount`. The server check goes right after `claim_rows` is computed.
- Remarks already flow to the Excel (`reimbursement_excel_row_remarks`, ~35910) and PCV, so the code appears there with no change.
- Browser check (owner-requested, local server on a database copy, engineer `kent`, June 2026 draft, 20 rows): Remarks column header reads "Purpose" in the current view; the textarea is ~372 × 82 px at 1024 px wide, with room for a select beneath it. The copy and temporary launch entry were removed afterwards.

## Execution steps

1. **Code list + helpers** (`templates/reimbursement.html`, page script near the remarks handlers ~5105):
   - `REIMBURSEMENT_PC_CODES` — array of `{ code, label, group }` from Decision 1.
   - `REIMBURSEMENT_PC_CODE_PATTERN` — matches any listed code as a whole word (`\bPC(18|19|20|21|22|23|24|26)\b`, case-insensitive), built from the list.
   - `getReimbursementPcCode(text)` → the last listed code found, upper-cased, or `''`.
   - `applyReimbursementPcCode(text, code)` → removes every listed code plus its leading ` - ` separator, trims, then appends ` - CODE` (or just `CODE` when the remaining text is empty); empty `code` only removes.
   - `reimbursementRowNeedsPcCode(row)` → `!row.manual && !!String(row.client || '').trim()`.
   - Done: helpers defined once; no change to existing functions.
2. **Dropdown markup** (`renderReimbursementRows`, desktop ~5428 and mobile ~5465): add `buildReimbursementPcCodeSelect(row, rowKey)` returning `<select class="reim-pc-code" data-row-key=… onchange="handleReimbursementPcCodeChange(this)" aria-label="PC code">` with a blank option ("PC code" / "PC code (required)" when `reimbursementRowNeedsPcCode`), `<optgroup label="Medical">` / `<optgroup label="Admin">`, option text `PC18 - RA - R/F`, value `PC18`, pre-selected from `getReimbursementPcCode(row.remarks)`. Place it directly under each textarea. Done: every row (desktop + mobile) shows the select with the right preselection after load.
3. **Handlers:**
   - New `handleReimbursementPcCodeChange(select)`: bail like the remarks handler when not editable; find the active remarks box for the row key, set `value = applyReimbursementPcCode(value, select.value)`, then call the existing `handleReimbursementRemarksInput(box)` (mirrors + marks dirty); sync all `.reim-pc-code` peers for the row; refresh readiness.
   - Extend `handleReimbursementRemarksInput` (keep name/signature): after mirroring, set every `.reim-pc-code[data-row-key]` for that row to `getReimbursementPcCode(input.value)`.
   - Done: select ↔ text stay in sync both ways, desktop ↔ mobile stay in sync.
4. **CSS** (page `<style>`): `.reim-pc-code` full width of the remarks cell, small margin-top, same font/border as `.reim-remarks`; `.reim-pc-code.is-missing` red border; add `.reim-pc-code` to the existing `.reim-page.reim-locked .reim-remarks` rule (~1974) so it locks the same way (plus `pointer-events: none`). Tap target ≥ 40 px on mobile.
5. **Readiness blocker:**
   - In `collectReimbursementRowsForSave()` schedule rows also carry `needs_pc_code: reimbursementRowNeedsPcCode(originalRow)` (the server ignores unknown keys — verify in `save_reimbursement_draft`; if not ignored, compute it in the readiness caller instead).
   - In `buildReimbursementReadinessSnapshot`, when `editable`, count `includedRows` with `needs_pc_code && !getReimbursementPcCode(remarks)`; if > 0 push blocker `{ id: 'pc-code', title: 'PC code', detail: 'N client-visit row(s) need a PC code in Remarks.', action: 'focusMissingReimbursementPcCode', actionLabel: 'Add PC code' }`.
   - New `focusMissingReimbursementPcCode()`: scrolls to/focuses the first missing select (expanding the mobile card when on mobile) and adds `.is-missing` to all missing selects.
   - In `submitReimbursement()`, after the existing claim-row check, stop with the same message via `setReimbursementSubmitNotice` + `reimAlert` when any included row is missing a code (before the LPR/signature dialogs).
   - Done: panel shows the item; Submit stops with a clear message; Save Draft unaffected.
6. **Server check** (`app.py`):
   - Constant `REIMBURSEMENT_PC_CODES = ('PC18','PC19','PC20','PC21','PC22','PC23','PC24','PC26')` and helper `reimbursement_remarks_pc_code(remarks)` (same whole-word rule).
   - In `submit_reimbursement`, after `claim_rows`: `missing = [r for r in claim_rows if r.shift_id and clean_str(r.client_name) and not reimbursement_remarks_pc_code(r.remarks)]`; if any, return 400 `{success: False, pc_code_required: True, missing_dates: [...], error: 'PC code is required in Remarks for client-visit rows: <dates>.'}` before any status change.
   - Done: submit refused without codes, accepted with them; nothing else in the route changed.
7. **Release bookkeeping:** service worker `CACHE_VERSION` bump (read live; keep the old one as a historical marker); `static/changelog/releases.json` entry `2026-10-07-reimbursement-pc-code` (audience engineers + admins, category Reimbursement); `changes.md`; this plan's status.

## Deliberately excluded

- No new database column or migration — the owner wants the code inside the remarks text.
- No requirement on manual rows or schedules without a medical center (Decision 3).
- No block on Save Draft (Decision 4).
- No changes to approver, accounting, tracker, Excel, PCV or RFP screens/outputs — they already show remarks.
- No back-filling of codes into existing drafts or submitted reimbursements.

## Verification

- **Tests** (`tests/test_reimbursement_design.py` or a new `tests/test_reimbursement_pc_code.py`), each run once against the unchanged code first to prove it fails:
  - Server: draft with a client schedule row + amount and no code → submit 400 `pc_code_required`, status still Draft; with `… - PC18` → submit succeeds; client row with zero amount and no code → not blocking; no-client schedule row and manual row without code → not blocking.
  - Page (node, like `test_reimbursement_readiness.py`): `applyReimbursementPcCode` appends, replaces, removes, handles empty text; `getReimbursementPcCode` finds it; readiness snapshot has the `pc-code` blocker only when a needed code is missing.
  - Source check: every new handler named in markup is defined; existing `handleReimbursementRemarksInput`, `collectReimbursementRowsForSave`, `saveReimbursementDraft`, `submitReimbursement` still defined; `node --check` on the page script.
- Focused modules: the new/changed test file + `tests.test_reimbursement_readiness` + `tests.test_reimbursement_design`. Full suite once before publishing, compared with the baseline (24 failures, 3 errors, 5 skips).
- **Browser** (built-in, local server on a database copy, engineer login on the copy; desktop and 375 px): pick PC18 → text ends "- PC18"; change to PC20 → replaced, not duplicated; blank → removed; type a code by hand → select follows; desktop and mobile in sync; Save Draft works with missing codes; panel shows "PC code" and its button jumps to the row; Submit blocked until filled; locked (submitted) record shows the select read-only; no console errors; no horizontal scroll at 375 px. Remove the copy and temporary launch entry afterwards.

## After implementation

1. Self-review the diff; confirm every function the page calls is still defined and Save Item / Save Draft / Submit / upload / download buttons still work.
2. Record the fail-first proof here.
3. Service worker bump and `releases.json` entry (step 7).
4. Update `changes.md` and this plan's status (`Executed` + commit).
5. Commit and push only on the owner's "commit and push": explicit staging of `app.py`, `templates/reimbursement.html`, the test file(s), service worker file, `static/changelog/releases.json`, `plans.md`, `changes.md`; never `scheduler.db`, `changes-archive.md`, handoffs, `.claude/`, `.impeccable/`, `output/`, `tmp/`. Verify `git ls-remote origin refs/heads/main` and the Railway deployment.

## Risks

- Drafts already open with client rows and no code will be blocked at Submit — intended; the panel and message say exactly what to add.
- An engineer could type a code mid-text and edit after it; detection is "any listed code anywhere", so it still counts — the select re-appends at the end when used.
- Blast radius: Reimbursement page and `submit_reimbursement` only; no schema change. Safety net: server check is a single early return, easy to revert.

# Personnel Fix Batch: Audit Findings (Scheduler Access, Mobile Layout, Loading, Edit Note)

**Status:** Executed — commit `86a24a5`; published to `origin/main` on the owner's "commit and push" (Railway deployment `5c845f87-ad62-418a-8943-517d788ccc52`).
**Finished:** 2026-10-06.

**Where the plan and the outcome differed:**

- Also added `canDeleteEngineer(e)` so Delete is hidden where the server would refuse (admin targets for schedulers/regional admin, own row); people with no login keep Delete.
- The branch picker also keeps `max-width: 9rem` next to the new `flex: 0 0 9rem; width: 9rem`. At 375 px the search box is 133 px and the picker 144 px; the picker's "All Branches" label is cut to "All Branche" by the global 16 px mobile font (cosmetic; options read in full when opened).
- Fail-first: both new tests failed on the unchanged code. After: `tests.test_staff_creation` + `tests.test_admin_capabilities` 37 tests OK; page script `node --check` OK, all handlers defined; full suite 1,567 tests, 24 failures, 3 errors, 5 skips (baseline counts; the count grew from the parallel Medical Center work).
- Browser (built-in, local server on a database copy, session `hanna` = scheduler): "Loading personnel…" before data; engineer rows show Deactivate and Delete but no Reset, admin rows show no account buttons; Deactivate then Activate on an engineer succeed with toasts and the Inactive badge; Edit note "Changes apply to this person's record.", Add keeps the Auto-Account note; at 375 px card buttons wrap two per row with no clipping and no horizontal scroll. The three 403 console entries were left over from the earlier audit run (this server run logged no 403). Copy and temporary launch entry removed.
**Approved:** 2026-10-06 — after a browser audit of the published Personnel batches, the owner asked to "plan the fix batch" and replied "yes, approved".
**Detailed:** 2026-10-06.

## Context

A browser check of `/engineers_page` on a copy of the database (session: `hanna`, a scheduler-type superadmin; 375 px and desktop) after Personnel Batches 1–4 (`a6d8571`, `351f6a2`, `e55ac2e`; plans further down this file) found:

1. **High** — schedulers (`diary`, `hanna`) can no longer deactivate or delete engineers; buttons show, every action returns 403 "This account is protected…". Before Batch 1, `delete_engineer` allowed all of `is_admin_authorized()`, and Settings still lets superadmin-role accounts deactivate.
2. **Medium** — Reset is shown to schedulers but always fails ("Schedulers cannot change passwords of superadmins or engineers.").
3. **Medium** — mobile card actions (Edit, Deactivate, Reset, Delete) are squeezed into one row at 375 px and overlap.
4. **Medium** — mobile search box collapses to ~50 px beside a ~225 px branch picker (pre-existing).
5. **Low** — no loading indicator; the first load showed an empty table for ~6 s.
6. **Low** — Edit form shows the "Auto-Account: a temporary password will be generated…" note.

Verified fine in the same check: desktop list, headcount, badges, search/filter/empty state, Edit fields and initials, Save toast and re-enabled button, add with suffixed username, static credentials pop-up with Done, no JS errors.

## Decisions taken

1. Deactivate/delete get their own rule; password reset keeps `can_reset_password_for_user` unchanged.
2. Schedulers regain deactivate/delete for engineers (not for admin accounts).
3. Buttons are hidden where the server would refuse.
4. The global `app-shell.css` mobile rule is not changed.

## Investigation

- `is_scheduler_user()` (`app.py` ~11490): role `superadmin` and username in `SCHEDULER_USERNAMES = {'diary', 'hanna'}` (~8046). `can_reset_password_for_user` (~11675): schedulers refused targets with role `superadmin` or `engineer`; regional admin refused `superadmin`/`regional_admin` and (Batch 4) targets outside Cebu/Davao.
- `personnel_account_change_denial` (Batch 1, next to `delete_engineer`) calls `can_reset_password_for_user` and maps every non-regional refusal to "This account is protected and cannot be deactivated or deleted here." — the cause of finding 1.
- Template context already has `nav_is_scheduler` (`app.py` ~1486).
- `templates/engineers.html`: `.engineer-mobile-actions` uses `grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr)` (Batch 1); `canChangeEngineerAccount(e)` = `(isSuperAdmin || isRegionalAdmin) && e.user_id`, used for Deactivate and Reset in `buildEngineerTableRow` and `getEngineerActionButtons`; the Auto-Account note is set by `setEngineerModalContactOnlyMode(false)`, which both `openAddModal` and `openEditModal` call; `eng-table-body` and `engineer-mobile-list` start empty.
- `static/css/app-shell.css` ~820–826 (mobile media query): `input, select, textarea { … max-width: 100% !important; }` overrides `#engineer-mobile-branch-filter { max-width: 9rem }`; `width` / `flex-basis` are not overridden.
- Another session is publishing Medical Center work on `main` in parallel; this plan touches only Personnel code, and staging must stay explicit.

## Execution steps

1. **Server rule** — `app.py` `personnel_account_change_denial(user_acc)` no longer calls `can_reset_password_for_user`. In order: no account → `None`; own account → "You cannot deactivate or delete your own account."; username in `PROTECTED_PASSWORD_USERNAMES` → "This account is protected."; target role in `{'superadmin', 'regional_admin'}` and (`is_scheduler_user()` or `is_regional_admin_user()`) → "Only a manager can deactivate or delete an admin account."; regional admin and the target's engineer profile branch not in `REGIONAL_ADMIN_BRANCHES` → `REGIONAL_PERSONNEL_DENIAL`. Done: scheduler deactivates/deletes an engineer; refusals name the real reason.
2. **Page gates** — `engineers.html`: `const isScheduler = {{ 'true' if nav_is_scheduler else 'false' }};`. `canChangeEngineerAccount(e)` additionally returns false for the logged-in user's own row (`String(e.id) === loggedInEngineerId`) and, when `isScheduler || isRegionalAdmin`, for `e.account_role` in `superadmin`/`regional_admin`. New `canResetEngineerPassword(e)` = `canChangeEngineerAccount(e) && !(isScheduler && e.account_role === 'engineer')`; the Reset buttons in `buildEngineerTableRow` and `getEngineerActionButtons` use it (the desktop Deactivate and Reset buttons are split so each has its own condition).
3. **Mobile actions** — `.engineer-mobile-actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(7rem, 1fr)); gap: 0.55rem; }` (replaces the auto-flow column rule).
4. **Mobile search** — `#engineer-mobile-branch-filter` adds `flex: 0 0 9rem; width: 9rem;`.
5. **Loading** — initial markup: `eng-table-body` holds `<tr><td colspan="6" class="text-center text-muted py-4">Loading personnel…</td></tr>`; `engineer-mobile-list` holds an `.engineer-mobile-empty` "Loading personnel…". Rendering already replaces both.
6. **Edit note** — `openEditModal`, when not contact-only, sets `#engineer-modal-info` to `alert alert-info` with "Changes apply to this person's record."; `openAddModal` keeps the Auto-Account note.
7. **Tests** — `tests/test_staff_creation.py`: fixture adds a scheduler user (`diary`, role `superadmin`, created only if missing and cleaned up if created). New tests: scheduler deactivates, reactivates, and deletes (no records) an engineer; scheduler refused (403, "Only a manager…") deactivating a profile linked to a superadmin login; scheduler's reset of an engineer still 403; source checks for `isScheduler`, `function canResetEngineerPassword(`, `repeat(auto-fit, minmax(7rem, 1fr))`, `flex: 0 0 9rem`, `Loading personnel`, "Changes apply to this person's record.". Each must fail on the unchanged code first; existing Batch 1/4 guard tests must still pass.

## Deliberately excluded

- Changing the reset policy for schedulers — existing Settings policy.
- Changing the global `app-shell.css` mobile rule — shared by other pages.
- Signing in as other accounts in the browser — would require signing out the existing local session.

## Verification

- New tests fail first, then pass. Focused modules: `tests.test_staff_creation`, `tests.test_admin_capabilities`.
- Browser on a temporary database copy (built-in browser, existing local session), desktop and 375 px: card buttons wrap two per row without overlap, search box usable, loading row visible before data, Edit note text, scheduler deactivate/activate of a test engineer succeeds, Reset hidden for the scheduler on engineer rows, no console errors. Clean up the copy and the temporary launch entry afterwards.
- Full suite once before publishing, compared with the baseline (24 failures, 3 errors, 5 skips).

## After implementation

1. Self-review; confirm every function the page calls is still defined (`node --check` on the page script).
2. Fail-first proof recorded here.
3. Service worker bump (read the current `CACHE_VERSION` live; keep the old one as a historical marker).
4. `releases.json` entry dated the commit date, audience admins.
5. Update `changes.md` and this plan's status.
6. Commit and push only on the owner's "commit and push": explicit staging; never `scheduler.db` or unrelated dirty files; verify `origin/main` and the Railway deployment.

## Risks

- Schedulers regain deactivate/delete for engineers — matches their pre-Batch-1 delete ability and Settings; delete is still refused for anyone with history.
- Blast radius: Personnel page and the two Personnel account routes only; no schema change.

---

# Merge Duplicate Medical Centers + Find Duplicates

**Status:** Executed — commit `89546cf`; published to `origin/main` on the owner's "commit and push" (Railway deployment succeeded, GitHub deployment `6882416289`).
**Finished:** 2026-10-06.

**Where the plan and the outcome differed:**

- Pair buttons say **"Keep this one"** under each side instead of "Keep left" / "Keep right" (clearer when the two sides stack on a phone).
- The page flag comes from the server (`clients_page` passes `can_merge_clients=is_superadmin_user()`), because a superadmin also needs an approved username; the role alone is not enough.
- Merge internals: contacts to add are created as new rows on the target and all source contact rows are deleted (keeps the target's order); the `client_id` moves use bulk updates followed by `db.session.expire_all()` before the source is deleted, so stale relationship collections (P.O. cascade) cannot act on moved rows. Activity entry is written with `add_activity_log_entry` inside the same transaction.
- Browser check found one bug, fixed: the merge pop-up's target list kept the previous merge's selection even when it did not match the search; the list is now cleared each time the pop-up opens.
- Test notes: the HR-only test account is turned away by the app's existing HR guard with a redirect (302) before reaching the routes — still a refusal; the PM owner check runs inside a request context because it builds URLs.
- Fail-first: all 6 new tests failed on the unchanged code (routes 404, missing helper, page functions absent). After: `tests.test_tsr_autosave_client_groups` 32 tests OK. Full suite 1,565 tests, 24 failures, 3 errors, 5 skips — the same 27 failing tests by name as before (the 13 failures in the PM/Genoray/Vieworks/P.O. modules run together are among them).
- Flask test client on copies of `scheduler.db`: Find duplicates returned the 3 expected pairs in ≈245 ms; merging "Bureau of Quarantine - Davao" into "Bureau of Quarantine" succeeded (no linked records) with an Activity entry; merging the two busiest medical centers (on a throwaway copy) moved 34 schedules and 1 equipment, the target's counts added up exactly, nothing pointed at the removed one, and Timeline, Reports, Analytics, P.O. Details, Products, Genoray and Vieworks pages and `/get_clients`, `/get_products` still loaded.
- Browser check (owner-approved; local server on a scratch copy; a generated test password set on the `hanna` scheduler account in that copy only, plus a test pair "Zz Test Hospital Merge" / "… Annex" with one contact): Find duplicates listed the 3 real pairs and the test pair; Keep this one → preview ("1 added, 0 skipped") → Merge → "Merged into Zz Test Hospital Merge.", the Annex gone, its contact on the kept one, View opened; Edit → Merge into… with search works; at 375 px both pop-ups fit (10–365 px) with no sideways scroll; no console errors. Screenshots could not be taken (the app window was minimised); layout was verified by measurement. Test server stopped and viewport reset.
**Approved:** 2026-10-06 — the owner asked to plan merging "carefully because it will alter many things", chose superadmin-only, block on P.O. number clash, and add contacts skipping exact repeats; then asked to add a "Find duplicates" button; replied "yes, approved" and explicitly allowed the browser check.
**Detailed:** 2026-10-06.

## Context

Since Medical Center Batch 1 (`75f11a1`), Delete refuses any medical center with history, so a duplicate entry cannot be removed. Merge moves everything from the duplicate (**source**) onto the one kept (**target**) and then removes the source. It touches schedules, equipment, P.O.s, travel and PM history, so it must be all-or-nothing and cannot be undone. A **Find duplicates** button suggests likely pairs; it never merges by itself.

## Decisions taken

1. Superadmins only (`is_superadmin_user`; includes the scheduler and manager accounts) (owner).
2. If both medical centers have a P.O. with the same number (normalized as in `find_purchase_order_duplicate`), the merge is refused with the clashing numbers (owner).
3. The source's contacts are appended to the target, skipping a contact with the same email, or the same name and phone, as one already saved (owner).
4. The target keeps its name, address and group; it takes the source's group only if it has none.
5. Find duplicates only suggests; every merge needs the preview and an explicit confirm (owner).
6. No undo; the Activity log records exactly what moved.

## Investigation

What points at a medical center (verified in `app.py` and on a copy of `scheduler.db`; local tables with a `client_id` column: contact, product, shift, travel_request_route_visit, purchase_order, genoray_item, vieworks_item):

| Where | Today | On merge |
|---|---|---|
| `Shift.client_id` (~3531) | source | → target |
| `Product.client_id` (~2695) | source | → target |
| `PurchaseOrder.client_id` (~2086, backref cascade) | source | → target; `PurchaseOrderMachine` rows follow their products, so the "machines belong to this client" rule stays true |
| `TravelRequestRouteVisit.client_id` (~2534) | source | → target; its `client_name` text kept as history |
| `GenorayItem` / `VieworksItem.client_id` (~2743 / ~2772) | source | → target; parent-product owner check (~63702) stays consistent |
| `Contact.client_id` (~2245) | source rows | appended to target skipping repeats; target's legacy `contact_person_n` / `contact_number_n` / `email_address_n` refreshed from its first three contacts |
| `InventoryPmVisit.completion_snapshot_json` (~2834) | stores `client_id`; `inventory_pm_visit_to_dict` (~4878) flags `owner_mismatch` when it differs from the equipment owner | rewrite `client_id` source → target in each snapshot |
| `Client.group_name` | — | target keeps its own; empty → source's |
| Source `Client` | — | deleted only when `client_linked_record_counts` is all zero and no `Contact` remains |

- Follows automatically: calibration certificates (`CalibrationCertificateApproval.shift_id`), P.O. machines, Analytics/Reports (live from `client_id`), `User.tsr_client_remembered_cc_json` (one flat list per user).
- Left untouched (history/fallback): `client_name` text columns on `reimbursement_row`, `travel_request`, `travel_request_route_visit`, `tsr_draft`, `online_tsr_submission`, `tsr_knowledge_entry`; `client_id` inside `online_tsr_submission` (34 local), `tsr_draft` (8) and `tsr_draft_version` (10) payloads — the app resolves the medical center from the schedule first (`resolve_client_for_tsr_contact` ~15243, `save_tsr_payload_contact_to_medical_center` ~15568) and a stale id falls through; offline TSR drafts are keyed by schedule id.
- P.O. numbers are unique per medical center only in code (`find_purchase_order_duplicate` ~54547), hence decision 2.
- Find duplicates: the existing `client_duplicate_match_score` (~7680) is unused and too loose — on 147 local medical centers it flags 72 pairs, 54 at score 1.0, nearly all different hospitals sharing a city or a common word ("Davao Doctors Hospital" / "Davao Regional Medical Center", "Our Lady of Grace" / "Our Lady of Peace"). A prototype of the rule in step 1 gave 3 real suggestions (Holy Name University Medical Center / Holy Name University; Bureau of Quarantine / Bureau of Quarantine - Davao; Northern Mindanao Medical Center / Mindanao Medical Center) in ≈250 ms and caught three planted typo duplicates (Acura/Accura, Sera/Serra, "Cebu Inc."). Words in ≥3 names count as common (locally: ace, allied, care, cebu, davao, del, district, experts, foundation, heart, jose, lady, our, polyclinic), so chains and branches are not paired.

## Execution steps

1. **Pair rule** — `app.py`, new `find_client_duplicate_pairs()` reusing `normalize_client_name_for_matching` and `client_name_strong_tokens`; names compared with parenthesised text removed. Suggest a pair when any holds: (a) **same name** — normalized names equal; (b) **one contains the other** — the shorter has ≥2 words and appears whole inside the longer; (c) **typo** — same word count, exactly one word differs, and that word is 1 letter off (2 letters if it has ≥7 letters); (d) **same distinguishing words** — ≥2 non-common strong words and identical sets. Each pair: both ids, names, addresses, equipment and schedule counts, reason; sorted by reason (same name first). Done: local data gives the 3 pairs above; planted typos found; branch and look-alike pairs not suggested.
2. **Duplicates route** — `GET /client_duplicate_pairs`, superadmin only (403 otherwise); computed on request only.
3. **Preview** — `client_merge_preview(source, target)` + `GET /client_merge_preview?source=&target=`, superadmin only; 400 source = target, 404 missing. Returns counts that would move (per table, incl. PM snapshots), contacts to add / skip, and clashing P.O. numbers.
4. **Merge** — `POST /merge_client {source_id, target_id}`, superadmin only, CSRF, one transaction: refuse 409 on P.O. clash → move all `client_id`s → merge contacts and refresh legacy fields → rewrite PM snapshots → fill group if empty → assert nothing points at source → delete source → commit → Activity log "Merged medical center "<source>" (#id) into "<target>" (#id): N schedules, N equipment, …". Any exception rolls back and returns "Nothing was changed."
5. **Page** — `templates/clients.html`, superadmins only (`const isSuperAdminUser`):
   - **Find duplicates** header button → pop-up listing pairs (names, addresses, counts, reason in plain words) with **Keep left** / **Keep right**, each opening the merge preview with source and target set; empty: "No likely duplicates found."
   - **Merge into…** in the Edit pop-up footer → same merge pop-up (`#clientMergeModal`) with a searchable target list (excluding the source).
   - Merge pop-up: preview with counts, skipped contacts, and "This cannot be undone. <source> will be removed."; **Merge** disabled until the preview loads without a P.O. clash; a clash lists the numbers.
   - Success: "Merged into <target>.", reload the list (and the duplicates list if open), open the target in View.
   - New functions `openClientDuplicatesModal`, `loadClientDuplicatePairs`, `openClientMergeModal`, `loadClientMergePreview`, `confirmClientMerge`; existing functions and ids kept.
6. **Tests** — new class in `tests/test_tsr_autosave_client_groups.py` (isolated DB): merge moves schedule, equipment, P.O. + machine, travel visit, Genoray item and deletes the source; contacts repeat skipped / new added / legacy fields updated; PM snapshot rewritten and no owner mismatch; P.O. clash 409 with nothing changed; regional admin and engineer 403; source = target 400; missing 404; forced mid-merge failure rolls back; preview counts equal what merge moves; pairs found for same name / contains / one-letter typo / same distinguishing words; branches ("ACE … Cebu" / "ACE … Sariaya", "St. Luke's … BGC" / "… QC") and look-alikes ("Our Lady of Grace" / "… Peace") not paired; non-superadmin 403 on duplicates; source checks for the new functions plus the existing "every called function is defined" test. Run each on the unchanged code first and record that it fails.

## Deliberately excluded

- **Undo** — Activity log records what moved.
- **"Not a duplicate" dismissal** — needs a new table; strict rules keep the list short; can be added later.
- **Rewriting historical `client_name` text and TSR payload ids** — reasons above.
- **Merging more than two at once**; **regional admin access** (owner).
- **Changing `client_duplicate_match_score`** — stays unused and untouched.

## Verification

- New tests fail on the unchanged code, pass after.
- Focused modules: `tests.test_tsr_autosave_client_groups`, `tests.test_purchase_orders` (11 known pre-existing failures), Genoray/Vieworks PM test modules.
- Flask test client on a copy of `scheduler.db`: Find duplicates returns the 3 expected pairs; merging "Bureau of Quarantine - Davao" into "Bureau of Quarantine" moves the previewed counts; Timeline, Reports, P.O. Details, Genoray and Vieworks pages still load.
- Full suite fails the same 27 tests by name as before.
- **Browser check (owner-approved):** the duplicates and merge pop-ups at 375 px and desktop width on the local server with a database copy; no console errors.

## After implementation

1. Self-review; confirm every function the page calls is still defined.
2. Fail-first proof recorded in this plan.
3. Service worker bump to `medical-service-pwa-offline-navigation-v254-medical-center-merge` (keep v253 as the historical marker).
4. `releases.json` entry `2026-10-06-medical-center-merge` (audience admins, category Medical Center).
5. Update `changes.md` and this plan's status.
6. Commit and push only on the owner's "commit and push": explicit staging; `scheduler.db`, `tmp/`, `output/`, handoffs, `.claude/`, `.impeccable/` excluded; verify `origin/main` and the Railway deployment.

## Risks

- **Merging the wrong pair** — irreversible; mitigated by the required preview, "cannot be undone" text, superadmin-only access and the Activity log.
- **A missed suggestion** — Find duplicates is a helper; Merge into… works for any pair.
- **A link this investigation missed** — the merge asserts nothing points at the source before deleting it and refuses otherwise.
- Safety net: no schema change; data-only changes inside one transaction.

---

# Medical Centers Layout Polish

**Status:** Executed — commit `71a21b0`; published to `origin/main` on the owner's "commit and push" (Railway deployment succeeded, GitHub deployment `6878353353`).
**Finished:** 2026-10-06.

**Where the plan and the outcome differed:**

- **Phone gutter stays 28 px, not ≈16 px.** It comes from the app-wide phone rule in `static/css/app-shell.css` (`.container-fluid` and `.main-content` each get `--mobile-safe-padding` with `!important`), which every page shares. Overriding it only here would make this page edge-to-edge unlike all others, so the page now follows the shell standard (down from 44 px). The page rule that tried to zero `.container-fluid` padding was removed as dead CSS.
- **Column sizing added to step 3.** With only `min-width: 200px` on Name, the Address column was squeezed at 1280 px (first row 137 px) and the table still overflowed at 1200 px. Added: Main Contact `max-width: 220px` with `overflow-wrap: anywhere`, Equipment and Actions shrink to content (`width: 1%; white-space: nowrap`). Average row height at 1280 px fell from 85 to 73 px and 1200 px no longer overflows.
- **Header buttons (step 5) changed to Add full width on top + Import / Export / Print in one row.** The planned `minmax(140px)` 2×2 grid cut off "+ Add Medical Center". On phones the button icons are hidden, padding is 0.4rem, and the font is 0.85rem via `.container-fluid .btn-group > .btn.btn-sm` (the shell's `button:not(...)` rule forces 0.95rem with `!important`). A lone Print (non-admins) fills the row (`:only-of-type`).
- **Also fixed:** the equipment pop-up's Edit button used the same unreadable `btn-outline-warning`; it is now `btn-outline-primary`. The space between the Group picker and the first card was reduced (`.client-mobile-list` margin-top 0 below 1200 px).
- Fail-first: `test_layout_polish` failed on the unchanged code (no 1199.98px rule). After: `tests.test_tsr_autosave_client_groups` 26 tests OK; rendered script passes `node --check`. Full suite 1,559 tests, 24 failures, 3 errors, 5 skips — the same 27 failing tests by name as before.
- Browser re-check (owner-approved; local server on a copy of `scheduler.db`, local test admin and engineer created only in that copy): 375 px — cards, 1 per row, actions in one row, header Add on top + three in a row with no text overflow, search aligned with the title; 768 px — 1 card per row; 1024 px — 2 cards per row; 1200 / 1280 / 1440 px — table with no overflow, average row height 82 / 73 / 69 px; no sideways page scroll at any width; Edit button blue; engineer: Print only (full width), cards show Edit Contacts · View; no console errors. Test server stopped and viewport reset afterwards.
**Approved:** 2026-10-06 — after a browser check of the Medical Centers page (owner-requested, local server on a database copy), the owner asked to "plan all eight as one batch", replied "yes, approved", and explicitly allowed the browser re-check for verification.
**Detailed:** 2026-10-06.

## Context

The owner-requested browser check of `/clients_page` (local server on a copy of `scheduler.db`, test admin created only in that copy) found eight layout problems: on desktop the 6-column table still overflows below ~1200 px, the Edit button is unreadable, and names wrap onto 3–4 lines; on phones the gutters waste 44 px a side, the header buttons are oversized and uneven, the search row is out of line, and cards for medical centers without contacts are mostly "No …" filler; the View pop-up repeats the name. All are in `templates/clients.html`.

## Decisions taken

1. All eight fixes in one batch (owner).
2. Below 1200 px the page shows cards (two per row from 769 to 1199 px, one per row on phones) instead of the table.
3. Browser re-check is allowed for verification of this batch (owner, explicit).

## Investigation

1. Table/cards switch only at `@media (max-width: 768px)`; measured at 1024 px: table 820 px in a 657 px wrapper (sideways scroll, actions cut off). At 1280 px: no overflow (table 913 = wrapper 913); at 1440 px: no overflow.
2. Table Edit button `btn-outline-warning` = `rgb(255,193,7)` on white (≈1.6:1 contrast).
3. Name column 156 px at 1280 px (rows 89 px tall; 137 px at 1024) while Main Contact is 251 px and mostly "-".
4. Phone: `.container-fluid > .card { padding: 1rem !important }` (old ≤768 rule) beats the Batch 4 `.client-page-card { padding: 0 !important }`; with `.container-fluid` padding 0.85rem the content sits 44 px from each edge (content 287 px on a 375 px screen).
5. Phone header buttons use `.container-fluid .btn-group { grid-template-columns: repeat(3, …) }`; four admin buttons leave "+ Add Medical Center" alone on a second row (button group 163 px tall).
6. The old ≤768 rule `.row.g-2.mb-4.no-print { margin: 0; padding: .85rem !important }` still matches the search row and puts the search box 14 px in from the title (58 vs 44 px). `.container-fluid h2.h4` is stale — the title is now `h1.h4`.
7. `renderClientMobileCards` prints "No primary contact / No designation / No phone / No email" plus a full-width `client-mobile-view-contact` button labelled with `getClientContactSummary` ("No contacts saved"); `.client-mobile-actions` uses `minmax(130px, 1fr)`, so Edit/Delete stack in the narrow card; no equipment count. A no-contact card is 499 px tall. Local data: only 12 of 147 medical centers have a non-empty contact (131 of 146 contact rows are empty).
8. `viewContacts` prints `<div class="fw-bold fs-5">${escapeHtml(c.name)}</div>` in the body under the header that already shows the name.
- Side finding: `@media print` hides `.client-mobile-list`; where the table is also hidden by width, a print could be empty.
- No console errors on load, search, View or Edit.

## Execution steps

1. **Cards below 1200 px** — new `@media (max-width: 1199.98px)`: `.table-responsive { display: none }`, `.client-mobile-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap }`, card `margin-bottom: 0`; at ≤768 px one column. Remove the table/cards switch from the ≤768 block. `@media print`: `.table-responsive { display: block !important }` and cards hidden.
2. **Edit contrast** — table Edit button `btn-outline-warning` → `btn-outline-primary`.
3. **Name width** — first table column (`th`, `td`) `min-width: 200px`. Done: no sideways scroll at 1200, 1280, 1440 px.
4. **Phone gutters** — at ≤768 px `.container-fluid` and `.container-fluid > .client-page-card` padding 0 (specificity matching the old rule), so content sits ≈16 px from the screen edge.
5. **Header buttons** — at ≤768 px `.container-fluid .btn-group { grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)) }`, buttons `white-space: nowrap` with the icon inline: a 2×2 grid; non-admins (Print only) get one full-width button.
6. **Search alignment** — delete the stale `.row.g-2.mb-4.no-print` margin/padding override (keep the input sizing); `.container-fluid h2.h4` → `h1.h4`. Done: search box left edge equals the title's.
7. **Phone/tablet cards** (`renderClientMobileCards`) — with contacts: bold contact name, then only the non-empty designation/phone/email lines, and `getClientContactSummary` ("N contacts saved") when there is more than one; without contacts: one muted "No contacts saved" line. Add "N equipment" (`product_count`). Remove the summary button. Actions in one row (`repeat(auto-fit, minmax(80px, 1fr))`): admins Edit · Delete · View; engineers Edit Contacts · View; others View. Delete styled quieter than Edit. All function names kept.
8. **View pop-up** — remove the repeated bold name from the body; address, group and the Export Excel / Print buttons stay.
9. **Tests** — source checks in `MedicalCenterSpeedAndUiTests` (`tests/test_tsr_autosave_client_groups.py`): `max-width: 1199.98px` rule present; no `btn-outline-warning`; no "No designation"/"No phone"/"No email" placeholders; no `fw-bold fs-5">${escapeHtml(c.name)}`; print rule shows the table. Run on the unchanged code first and record that they fail.

## Deliberately excluded

- **Cleaning the 131 empty contact rows** — a data decision.
- **Merging duplicate medical centers** — own plan later.
- **Edit pop-up Export Excel and stacked footer on phones** — they work.

## Verification

- New tests fail on the unchanged code, pass after; `tests.test_tsr_autosave_client_groups` OK; `node --check` on the rendered script.
- Full suite fails the same 27 tests by name as before.
- **Browser re-check (owner-approved):** local server on a database copy (`.claude/launch.json` `medical-center-check`), measured with page scripts at 375, 768, 1024, 1200, 1280 and 1440 px: no sideways scroll; phone gutter ≈16 px; search box aligned with the title; card actions in one row; table at ≥1200 px with no overflow; no console errors. Stop the test server afterwards.

## After implementation

1. Self-review; confirm every function the page calls is still defined.
2. Fail-first proof and browser measurements recorded in this plan.
3. Service worker bump to `medical-service-pwa-offline-navigation-v253-medical-center-layout` (keep v252 as the historical marker).
4. `releases.json` entry `2026-10-06-medical-center-layout` (admins and engineers, category Medical Center).
5. Update `changes.md` and this plan's status.
6. Commit and push only on the owner's "commit and push": explicit staging; `scheduler.db`, `tmp/`, `output/`, handoffs, `.claude/`, `.impeccable/` excluded; verify `origin/main` and the Railway deployment.

## Risks

- **Laptops under 1200 px wide see cards instead of the table** — same information and actions.
- Safety net: template-only change, no backend or schema change; reverting the commit restores the current layout.

---

# Medical Centers Table: Stacked Contact Details

**Status:** Executed — commit `415e04e`; published to `origin/main` on the owner's "commit and push" (Railway deployment succeeded, GitHub deployment `6877855317`).
**Finished:** 2026-10-06.

**Where the plan and the outcome differed:**

- Nothing material. The test counts header cells with `<th[\s>]` so `<thead>` is not counted.
- Fail-first: the new test failed on the unchanged code ("9 != 6"). After: `tests.test_tsr_autosave_client_groups` 25 tests OK; rendered page script passes `node --check` for admin and engineer; page 200 for both on a copy of `scheduler.db`. Full suite 1,558 tests, 24 failures, 3 errors, 5 skips — the same 27 failing tests by name as before this change. No browser check was made; the owner confirms the look once live.
**Approved:** 2026-10-06 — the owner reported that the action buttons sit too far right after Batch 4, chose "Stack contact info" over pinning the Actions column or moving it first, and replied "yes, approved".
**Detailed:** 2026-10-06.

## Context

Batch 4 (`558031d`) added Email and Equipment columns to the Medical Centers desktop table, taking it to 9 columns (Name, Address, Group, Main Contact, Designation, Phone, Email, Equipment, Actions), so Edit / Delete / View sit far to the right and need sideways scrolling.

## Decisions taken

1. Merge Main Contact, Designation, Phone and Email into one **Main Contact** cell; the table becomes 6 columns: Name, Address, Group, Main Contact, Equipment, Actions (owner).
2. Sorting by designation and phone is dropped; sorting by contact name stays. Search still finds designation and phone.

## Investigation

- `templates/clients.html`: header cells with sort buttons `data-sort-key` name/address/contact/designation/phone, plain Group, Email, Equipment and Actions headers; `renderTable` builds the 9 cells; `colspan="9"` appears in the initial tbody loading row, `renderTable` empty row and `renderClientLoadError`.
- `CLIENT_SORT_KEYS = ['name', 'address', 'contact', 'designation', 'phone']`; `restoreClientSortPreference` ignores keys not in the list; `getClientSortValue` maps all keys.
- Mobile cards (`renderClientMobileCards`) and the View pop-up already show contact details stacked and are not affected.

## Execution steps

1. **Header** — remove the Designation, Phone and Email `<th>`; Main Contact keeps its sort button. Done: 6 header cells.
2. **`renderTable`** — the Main Contact cell shows the name in bold (with "+ More" when there are more contacts), then the designation as a small muted line, a `tel:` phone link and a `mailto:` email link as small lines; only lines with a value; "-" when there is no contact. Equipment and Actions cells unchanged.
3. **Message rows** — `colspan="9"` → `colspan="6"` in the initial loading row, the empty row and `renderClientLoadError`.
4. **Sorting** — remove `designation` and `phone` from `CLIENT_SORT_KEYS` so a saved sort on either falls back to unsorted; `getClientSortValue` unchanged.
5. **Unchanged** — mobile cards, View pop-up, search, and every function and id still in use.
6. **Test** — source check in `MedicalCenterSpeedAndUiTests` (`tests/test_tsr_autosave_client_groups.py`): 6 `<th>` in the table header, no `data-sort-key="phone"`/`"designation"`, no `colspan="9"`. Run on the unchanged code first and record that it fails.

## Deliberately excluded

- **Pinning the Actions column** and **moving Actions first** — not chosen.
- **Icon-only action buttons** — not requested.

## Verification

- New test fails on the unchanged code, passes after; `tests.test_tsr_autosave_client_groups` OK.
- `node --check` on the rendered page script; page renders for admin and engineer on a copy of `scheduler.db`.
- Full suite fails the same 27 tests by name as before.
- No browser automation (AGENTS.md); the final look is for the owner to confirm once live.

## After implementation

1. Self-review; confirm every function the page calls is still defined.
2. Fail-first proof recorded in this plan.
3. Service worker bump to `medical-service-pwa-offline-navigation-v252-medical-center-table` (keep v251 as the historical marker).
4. `releases.json` entry `2026-10-06-medical-center-table` (admins and engineers, category Medical Center).
5. Update `changes.md` and this plan's status.
6. Commit and push only on the owner's "commit and push": explicit staging; `scheduler.db`, `tmp/`, `output/`, handoffs, `.claude/`, `.impeccable/` excluded; verify `origin/main` and the Railway deployment.

## Risks

- Sorting by designation or phone is no longer available — search still finds both.
- Safety net: template-only change, no backend or schema change; reverting the commit restores the 9-column table.

---

# Medical Center Batches 3 & 4: Speed, Code Cuts and UI

**Status:** Executed — commit `558031d`; published to `origin/main` on the owner's "commit and push" (Railway deployment succeeded, GitHub deployment `6877650579`).
**Finished:** 2026-10-06.

**Where the plan and the outcome differed:**

- The page edits were applied as whole-function replacements by name, so untouched functions stay byte-identical. Removed: `clientEscape`, `autoCompleteClient`, `hideClientAutocomplete`, `showImportToast`, the `#auto-box` click handler, the `#importToast` markup, `clientSummary`, `schedulerUsernames`, `isSchedulerUser`, `authUsernameVal`. Added: `getClientContacts`, `getClientProducts`, `clearClientFilters`, `refreshClientGroupFilterOptions`, `renderClientLoadError`.
- The product pop-up title also became "Equipment Details", and the View section "Equipment / Products" became "Equipment", to match the new column.
- `clients.html` went from 1,880 to 1,788 lines (net removal is smaller than the scan's 150–200 estimate because the UI additions add lines back); `app.py` net −16 lines.
- Fail-first: 4 of the 5 new tests failed on the unchanged code (no `product_count`; `/search_clients` 200; duplicated loop and dead code present; no new search/states/wording). The fifth (every called function is defined) passed before and after by design.
- After: `tests.test_tsr_autosave_client_groups` 24 tests OK. Full suite 1,557 tests, 24 failures, 3 errors, 5 skips — same as the baseline. Rendered page script passes `node --check` for admin and engineer.
- Flask test client on a copy of `scheduler.db`: `/get_clients` output identical to the previous code for all 147 medical centers apart from the new `product_count` (101 products); Add 200, Edit 200, duplicate Add 409, Export → Import 200, Delete 200. The design detector reports `nested-cards` and `skipped-heading` on the previous page and 0 findings on the new one. No browser check was made — table columns and the 375 px card layout still need a visual look.
**Approved:** 2026-10-06 — the owner asked to "plan batch 3 and include batch 4", chose "merge in a separate plan later" and "one search box + Group picker", and replied "yes, approved".
**Detailed:** 2026-10-06.

## Context

The Medical Center page (`templates/clients.html`, `/clients_page`) carries duplicated code — the contact loop copied 9 times, two notification systems, the same duplicate check four times per save, a fetch of a route that does not exist (`/get_clients_summary`), and hard-coded scheduler usernames. It is slower than needed: `/get_clients` runs one contact query per client and every View click downloads the whole product list (89 KB locally). The UI has four search boxes, no email or equipment column on desktop, no loading/empty/error state on desktop, "Client" wording where the app says "Medical Center", wrong View arrows, unlabelled contact inputs, and two design-hook findings (nested cards, skipped headings). Batches 1 (`75f11a1`) and 2 (`1ef8f24`) are published.

## Decisions taken

1. Merging duplicate medical centers is **out** — a separate plan later (owner).
2. One search box over name, address, contact name, designation, phone and email, plus a Group dropdown built from existing groups (owner).
3. Every function name, id and handler that other code still uses is kept; only code nothing else calls is removed.
4. The TSR contact repair on page load stays (27 ms locally, bounded to the last 150 TSRs).

## Investigation

- Measured on a local DB copy: `/get_clients` 141 ms / 15 KB; `/get_products` 132 ms / 89 KB; `repair_recent_online_tsr_contacts_for_medical_centers` 27 ms over 34 submissions.
- `/search_clients` (`app.py` ~53688) is only called by `autoCompleteClient`; it is also listed in `PERFORMANCE_LOG_PATHS` (~1383) and the service worker network-first list (~27518).
- No test references `autoCompleteClient`, `showImportToast`, `importToast`, `get_clients_summary`, `schedulerUsernames`, `isSchedulerUser`, the `s-name`/`s-addr`/`s-designation` ids, `clientEscape`, or "Client Management".
- The scheduler/manager accounts are superadmins (Batch 2 correction), so `isAdminUser` already covers them; no user has role `scheduler`.
- `add_client` duplicate 409 returns `existing_id` only; `update_client` returns `existing_id`, `existing_name`, `existing_address`.
- No `h1` in `layout.html` or the page; page title `h2`, confirm dialog `h3`, pop-up titles `h5`.
- The contact loop pattern appears in `countContactsForClient`, `getPrimaryClientContact`, `clientHasDesignationMatch`, `renderTable`, `openEditModal`, `viewContacts` (plus the `hasMore` loop).

## Execution steps

**Batch 3 — speed and code cuts**

1. **Contact helper** — new `getClientContacts(c)` → `[{name, designation, phone, email}]`; `countContactsForClient`, `getPrimaryClientContact`, `clientHasDesignationMatch`, `renderTable` ("+ More"), `openEditModal`, `viewContacts` use it (names kept). Done: no `while(c[\`cp${i}\`]…)` loop remains.
2. **One escape helper** — `clientToast` uses `escapeHtml`; remove `clientEscape`.
3. **One notification system** — import results use `clientToast`; remove the `#importToast` markup and `showImportToast`; `buildImportSummary` returns plain text.
4. **One duplicate check** — remove `autoCompleteClient`, `hideClientAutocomplete` (and its calls), the `#auto-box` outside-click handler, the `oninput` calls to it, and the `/search_clients` route plus its `PERFORMANCE_LOG_PATHS` and service-worker entries. `liveDuplicateCheck` keeps the typing warning. `saveClient` drops its pre-save fetch and shows the existing "Duplicate Client Found → Open Existing" dialog from the server's 409; `add_client`'s 409 adds `existing_name`, `existing_address`.
5. **Dead code** — remove the `/get_clients_summary` fetch and `clientSummary` (footer total uses `clientsData.length`); remove `schedulerUsernames`, `isSchedulerUser`, `authUsernameVal`; `canManageClientContacts = isAdminUser || isEngineerUser`, `canDeleteClientContactRows = isAdminUser`.
6. **Speed** — `/get_clients`: all contacts in one query grouped by client; add `product_count` from one grouped query (HR-only shape unchanged). `renderTable` builds its HTML once. New `getClientProducts()` fetches `/get_products` once per page load (reset in `loadClients`); `viewContacts` and `openProductModal` use it.

**Batch 4 — UI**

7. **Search** — replace the four boxes with `#s-search` ("Search name, address, contact, phone or email") and the `#s-group` dropdown ("All groups" + existing groups, filled in `loadClients`); `applyFilters`, `getActiveClientFilters`, `restoreClientFilters`, `updateClientCountFooter` rewritten under the same names; a "Clear" button when a filter is active.
8. **Desktop table** — Email column (`mailto:`), Phone as `tel:` link, Equipment column (`product_count`). Table body shows "Loading medical centers…" first, then "No medical centers match your search." or "Could not load medical centers. Refresh to try again." (`loadClients` checks `res.ok`).
9. **Wording** — user-facing "Client" → "Medical Center" on this page: title "Medical Centers", "+ Add Medical Center", pop-up titles, Save button, delete dialog title, mobile empty message. Internal names unchanged.
10. **View pop-up** — contacts with tap-to-call and tap-to-email links; when no equipment: "No equipment linked · Add on Products page" linking to `/products_page`; section arrows start as ▼.
11. **Accessibility and design findings** — contact inputs get `aria-label`s ("Contact 1 name", …); headings: page title `h1 class="h4"` (same look), confirm dialog `h2`, pop-up titles `h2 class="modal-title h5"`; flatten nesting: count footer becomes a top-border row instead of a bordered box, and on ≤768 px the outer card loses its background and shadow.
12. **Tests** — new class in `tests/test_tsr_autosave_client_groups.py`: `/get_clients` returns `product_count`; `/search_clients` → 404; `add_client` 409 includes `existing_name`/`existing_address`; source checks (no `while(c[\`cp${i}\`]`, no `get_clients_summary`, `schedulerUsernames`, `autoCompleteClient`, `importToast`; has `getClientContacts`, `#s-search`, the loading/empty/error texts, "Medical Centers"); every function the page calls is defined (as the Reimbursement test does). Run each on the unchanged code first and record that it fails.

## Deliberately excluded

- **Merge duplicates** — owner's decision; own plan later.
- **TSR contact repair on load** — cheap and bounded.
- **Renaming internal ids, routes or functions** — "client" stays in code.
- **Contact checks in CSV import** — separate decision (from Batch 2).

## Verification

- New tests fail on the unchanged code, pass after.
- Focused modules: `tests.test_tsr_autosave_client_groups`, `tests.test_purchase_orders` (11 known pre-existing failures).
- Flask test client on a temporary copy of `scheduler.db`: page renders for admin and engineer; `/get_clients` returns the same clients and contacts as before plus `product_count`; Add, Edit, Delete, Import, Export still work.
- `node --check` on the rendered page script.
- The design hook no longer reports nested cards or skipped headings.
- No browser automation (AGENTS.md). The visual layout (table columns, cards at 375 px) is only confirmable in a browser — ask the owner rather than open one.
- Full suite once before publishing, compared with the baseline (24 failures, 3 errors, 5 skips).

## After implementation

1. Self-review the diff; confirm every function the page calls is still defined.
2. Fail-first proof recorded in this plan.
3. Service worker bump to `medical-service-pwa-offline-navigation-v251-medical-center-ui` (read the current value live; keep v250 as the historical marker).
4. `releases.json` entry `2026-10-06-medical-center-ui` (audiences admins and engineers, category Medical Center).
5. Update `changes.md` and this plan's status, with any differences from the plan.
6. Commit and push only on the owner's "commit and push": explicit staging; `scheduler.db`, `tmp/`, `output/`, handoffs, `.claude/`, `.impeccable/` excluded; verify `origin/main` and the Railway deployment.

## Risks

- **Users lose the separate Name/Address/Designation boxes** — the single search covers all of them.
- **Autocomplete suggestions disappear** — they only ever suggested exact duplicates, which the duplicate warning still shows.
- **Wider table** with Email and Equipment — the table already scrolls sideways; phones use the cards.
- Safety net: no schema change; reverting the commit restores the previous page.

---

# Medical Center Batch 2: Permissions and Safety

**Status:** Executed — commit `1ef8f24`; published to `origin/main` on the owner's "commit and push" (Railway deployment succeeded, GitHub deployment `6876653600`).
**Finished:** 2026-10-06.

**Where the plan and the outcome differed:**

- `update_client` runs the contact check right after the not-found check, before the role branches, so both the engineer and admin paths are covered by one call.
- The Batch 1 round-trip test used 4-digit sample phones (`0917`, `0918`) that the new check correctly refuses; its sample data now uses full numbers.
- Fail-first: 4 of the 5 new tests failed on the unchanged code (engineer blank row lost contact A and duplicated C; no 400 for a bad phone/email; engineer page had `/export_clients`; unescaped `${c.name}`). The fifth (unchanged saved value still accepted) passed before and after by design — it guards against the new check blocking saved data.
- After: `tests.test_tsr_autosave_client_groups` all OK; `tests.test_purchase_orders` only its 11 known pre-existing failures. Full suite 1,552 tests, 24 failures, 3 errors, 5 skips — same as the baseline. Rendered page script passes `node --check`.
- Flask test client on a copy of `scheduler.db`: page 200 for admin and engineer (Export only for admin); all 147 real medical centers re-saved unchanged by an admin with no refusal; an engineer saving a 3-contact client with contact 1 blanked kept all 3 contacts. No browser check was made.
**Approved:** 2026-10-06 — the owner asked to "plan batch 2" after Batch 1 was published, and replied "yes, approved".
**Detailed:** 2026-10-06.

## Context

The Medical Center page scan found that saved text — client names and addresses (from admin edits, Timeline quick-add and CSV import) and product names — is inserted into the page unescaped in several places (stored-XSS risk). Buttons for admin-only actions are shown to everyone, so other users hit a 403 "Denied" response. Engineers, who may not delete contacts, can still lose one by blanking it: later contacts shift into its place. Contact phone and email are never checked. This is batch 2 of 4 (1: protect data — published as `75f11a1`; 3: speed and code cuts; 4: UI and merge).

**Correction to the scan (#8):** the "manager" and "scheduler" accounts (`rodito`, `robert`, `diary`, `hanna`, `hannah`) all have role `superadmin`, so they already have full admin access to the page; no account has role `manager` or `scheduler`. There is no access gap. The page's hard-coded scheduler usernames are only redundant code and move to Batch 3.

## Decisions taken

1. Escape every database value inserted into the page; values passed to `onclick` handlers become safe JavaScript strings.
2. Export (CSV) and both Export Excel buttons are shown to admins only; the product Edit button only to users who can edit products (`can_edit_products_inventory`). Print stays for everyone.
3. For engineers (no contact delete), a fully blanked contact row keeps the saved contact in place; nothing shifts.
4. Contact phone and email are checked on Add and Edit with the Personnel rules, for **new or changed** values only, so saved data is never blocked (all 146 local contacts already pass).

## Investigation

- Unescaped values in `templates/clients.html`: autocomplete `item.name`/`item.address` (~342); duplicate warning `data.name`/`data.address` (~411); product pop-up `p.name`, `p.serial_number`, `p.client_name`, dates, and `editProduct('${p.serial_number}')` (~544–581); `viewContacts` header `c.name`/`c.address` (~1192); product list `p.name`/`p.serial_number` and `openProductModal('${p.serial_number}')` (~1255). Table, mobile cards and toasts are already escaped.
- `export_clients` and `export_client_excel` require `is_admin_authorized` and return `denied()` (403 JSON). Their buttons: header Export (~34), Edit pop-up Export Excel (~152; engineers can open this pop-up for contacts), View pop-up Export Excel (~1197).
- `update_product` is gated by `can_edit_products_inventory()`; the page's product Edit button only navigates to `/products_page?edit=<serial>`.
- `apply_client_contacts_without_deleting_existing` (`app.py` ~53821; `allow_delete=False` for engineers) drops blank rows before matching by position: contacts A, B, C with A blanked become B, C, C (A lost, C duplicated).
- `personnel_contact_error`, `PERSONNEL_PHONE_PATTERN`, `PERSONNEL_EMAIL_PATTERN` (`app.py` ~61908) can be reused; local DB: 146 contacts, 0 phones or emails failing the patterns.
- Users by role locally: superadmin 6, regional_admin 1, engineer 21, staff 3, approver 1.

## Execution steps

1. **Escaping** — `templates/clients.html`: new `clientJsArg(value)` returning `escapeHtml(JSON.stringify(String(value ?? '')))` for `onclick` arguments; wrap every value listed above in `escapeHtml(...)`; `openProductModal(${clientJsArg(serial)})` and `editProduct(${clientJsArg(serial)})`. Done: no database value is inserted unescaped; function names unchanged.
2. **Permission flags** — `app.py` `clients_page` passes `can_edit_products=can_edit_products_inventory()`; page adds `const canEditProducts`. Header Export button moves inside the existing admin Jinja condition; Edit pop-up Export Excel gets the same condition; View pop-up Export Excel only when `isAdminUser`; product Edit button only when `canEditProducts`. Done: an engineer's page has no Export link; admins see everything as before.
3. **Engineer blank row** — `apply_client_contacts_without_deleting_existing`, `allow_delete=False` path: keep each submitted row's position; a fully blank row at an existing index leaves that contact unchanged; later rows do not shift. Admin path (`allow_delete=True`) unchanged. Done: an engineer blanking contact 1 keeps A, B, C.
4. **Contact checks** — new `client_contact_error(payload, client_id=None)` next to that helper; called by `add_client` and both paths of `update_client` before any write. Checks each submitted `cn{i}`/`ce{i}` against the Personnel patterns (phone 7–15 digits), skipping values already saved on that client's contacts. Returns 400 with e.g. "Contact 2: phone number is not valid. Use digits, e.g. 0917 123 4567." / "Contact 2: email address is not valid." The page already shows the server message.
5. **Tests** — new class in `tests/test_tsr_autosave_client_groups.py` reusing `ClientGroupRouteTests.isolated_database`:
   - engineer blank row keeps all contacts;
   - invalid new phone/email → 400 on add and update (admin and engineer);
   - an unchanged saved value that does not fit the pattern is still accepted;
   - `/clients_page` for an engineer has no `/export_clients` button; for an admin it does;
   - source check: no unescaped `${c.name}`, `${p.name}`, `${item.name}`, `${data.name}`, and no `'${p.serial_number}'` in `onclick`.
   Run each on the unchanged code first and record that it fails.

## Deliberately excluded

- **Manager access (#8)** — not a real gap (see correction).
- **Removing the hard-coded scheduler usernames, duplicate checks, contact-loop helper** — Batch 3.
- **Contact checks in CSV import** — one bad cell would refuse the whole file; separate decision.
- **UI, nested cards, heading levels** — Batch 4.

## Verification

- New tests fail on the unchanged code, pass after.
- Focused modules: `tests.test_tsr_autosave_client_groups`, `tests.test_purchase_orders` (11 known pre-existing failures).
- Flask test client on a temporary copy of `scheduler.db`: page renders for admin and engineer; an engineer save with contact 1 blanked keeps all contacts; re-saving a real client unchanged is accepted.
- No browser automation (AGENTS.md).
- Full suite once before publishing, compared with the baseline (24 failures, 3 errors, 5 skips).

## After implementation

1. Self-review the diff; confirm every function the page calls is still defined.
2. Fail-first proof recorded in this plan.
3. Service worker bump to `medical-service-pwa-offline-navigation-v250-medical-center-safety` (read the current value live; keep v249 as the historical marker).
4. `releases.json` entry `2026-10-06-medical-center-safety` (audiences admins and engineers, category Medical Center).
5. Update `changes.md` and this plan's status, with any differences from the plan.
6. Commit and push only on the owner's "commit and push": explicit staging; `scheduler.db`, `tmp/`, `output/`, handoffs, `.claude/`, `.impeccable/` excluded; verify `origin/main` and the Railway deployment.

## Risks

- **A real phone outside the pattern** (e.g. with "loc. 205") is refused when entered new; saved values are never blocked and the message says what is allowed.
- **Engineers lose Export buttons** that never worked for them.
- Safety net: no schema change; reverting the commit restores the previous behaviour.

---

# Medical Center Batch 1: Protect Data and Fix Import

**Status:** Executed — commit `75f11a1`; published to `origin/main` on the owner's "commit and push" (Railway deployed the follow-up docs commit `6333bad`, which superseded this build; status success).
**Finished:** 2026-10-06.

**Where the plan and the outcome differed:**

- The new test class `MedicalCenterProtectDataTests` reuses `ClientGroupRouteTests.isolated_database` by assignment rather than subclassing, so the two existing tests do not run twice.
- The P.O. test was renamed `test_client_delete_is_refused_while_purchase_orders_exist`; the kept client is added to `created_client_ids` so the class teardown still removes it.
- Export → import on a copy of the real database leaves all data the same except normalisation in 6 of 147 records: blank addresses/phones stored as `""` become empty (`NULL`), and one completely empty contact row is dropped. No real values change.
- Fail-first: all 7 new tests failed on the unchanged code (200 instead of 409 for delete, contacts left behind, 500 for a blank name, `NameError` on import, no Group column in export, contacts wiped by a contact-less row, page text missing). After: focused modules `tests.test_tsr_autosave_client_groups` + `tests.test_purchase_orders` — all new tests pass; the 11 `test_purchase_orders` failures are pre-existing (identical on the unchanged code). `test_changelog_workflow.test_manifest_entries_cannot_be_deleted` fails only when run after `test_tsr_autosave_client_groups`, also on the unchanged code (existing test-order issue). Full suite 1,547 tests, 24 failures, 3 errors, 5 skips — same as the baseline.
- Flask test client on a copy of `scheduler.db`: `/clients_page` 200; deleting the client with the most schedules refused with "… has 34 schedules and 1 equipment. It cannot be deleted."; blank add 400; export header `Name,Address,Group,Contact 1 Name,Contact 1 Designation,…`; import of that export 200 (147 updated). No browser check was made.
**Approved:** 2026-10-06 — the owner reviewed the Medical Center page scan (`/clients_page`), asked to "plan batch 1", chose "refuse Delete on any linked record", and replied "yes, approved".
**Detailed:** 2026-10-06.

## Context

A read-only scan of the Medical Center page (`templates/clients.html`, `/clients_page`) found that **Delete damages other records**: schedules lose their client, equipment is unlinked, P.O.s are deleted along with the client, and contacts, travel visits and Genoray/Vieworks items keep pointing at a deleted client (one orphan contact already exists in the local database). **Import CSV fails for every row with a contact** (`NameError`), and Export leaves out Group and Designation, so an export → import round trip would erase them once Import works. A blank company name causes a 500 on Add and Edit. This is batch 1 of 4 (2: permissions and safety; 3: speed and code cuts; 4: UI and merge) and goes first because it is the only one that loses data.

## Decisions taken

1. Delete is **refused when the medical center has any linked record**: schedules, equipment, P.O.s, travel visits, Genoray items, Vieworks items. The message names the counts. P.O.s are no longer deleted with the client (the earlier P.O. cascade existed so Delete would not crash, not as a business rule — `plans-archive.md` P.O. plan).
2. A medical center with no linked records can still be deleted; its `Contact` rows are deleted with it (no orphans).
3. Deleting a missing medical center returns 404 instead of success.

## Investigation

- `delete_client` (`app.py` ~54036): admin-only, no linked-record check, ignores a missing id (returns success).
- Tables with `client_id` → `client.id`: `PurchaseOrder` (~2087, backref `purchase_orders` with `cascade='all, delete-orphan'`, so P.O.s and their machine rows are deleted), `Contact` (~2246, no relationship → orphaned), `TravelRequestRouteVisit` (~2535, dangling), `Product` (~2696, `Client.products` default cascade → set NULL), `GenorayItem` (~2744, dangling), `VieworksItem` (~2773, dangling), `Shift` (~3532, `Client.shifts` → set NULL). No raw-SQL tables reference `client_id`.
- `import_clients` (`app.py` ~64347): `designation=c_designation` (~64417) is never defined (introduced in `37cceea` "add designation client"), so any contact row raises `NameError`, caught by the generic handler → rollback and "Import failed: name 'c_designation' is not defined". On a matched client (`check_for_duplicate_client`) it deletes all contacts even when the row carries none. It ignores Group. Column lookup is via `csv_get(row, *names)` (~64289).
- `export_clients` (~53498): columns `Name, Address`, then `Contact {i} Name/Phone/Email`; no Group or Designation; one `Contact` query per client.
- `Client.name` is `nullable=False`; `add_client` (~53922) and the admin path of `update_client` (~53967) do not reject a blank name → `IntegrityError` → 500.
- Page: `deleteClient` (`templates/clients.html` ~1272) ignores the response; `saveClient` (~797) has no name check.
- Local `scheduler.db`: 147 clients, 146 contacts (1 orphan), 352 schedules and 101 products linked, 0 P.O.s.
- Tests: `tests/test_purchase_orders.py::test_client_delete_cascades_purchase_orders_without_touching_other_client` expects Delete to remove the P.O.s — it must change. `tests/test_tsr_autosave_client_groups.py::ClientGroupRouteTests.isolated_database` provides an isolated DB with admin/engineer/HR clients to reuse.

## Execution steps

1. **Record counter** — `app.py`, new `client_linked_record_counts(client)` next to `delete_client`: ordered label → count for schedules (`Shift.client_id`), equipment (`Product.client_id`), P.O.s (`PurchaseOrder.client_id`), travel visits (`TravelRequestRouteVisit.client_id`), Genoray items, Vieworks items. Done: zeros for a new client, correct count after adding a shift.
2. **Safe delete** — `delete_client`: 404 `{'message': 'Medical center not found.'}` when missing; 409 with a message naming the non-zero counts ("<name> has 24 schedules and 3 equipment. It cannot be deleted.") when any count > 0; otherwise delete its `Contact` rows, then the client, `log_activity` as today, return success. Done: no shift, product or P.O. is ever changed or removed by this route.
3. **Blank name** — `add_client` and the admin path of `update_client`: return 400 `{'message': 'Company name is required.'}` when the cleaned name is empty, before any other work. Done: no 500 for a blank name.
4. **Import fix** — `import_clients`:
   - per contact read designation from `CD{i}`, `Contact {i} Designation`, `Designation {i}`; single-contact fallback `Designation`; carry it in `contact_rows` (removes the `NameError`);
   - when the CSV header has `Group` or `Group Name`, set `group_name` from it (blank clears); without the column, leave the group unchanged; call `ensure_client_group_column()` / `ensure_contact_designation_column()` first;
   - on a matched client, delete and replace contacts **only when the row has at least one contact**.
   Done: a file produced by Export imports with no changes to the data.
5. **Export fix** — `export_clients`: columns `Name, Address, Group`, then per contact `Contact {i} Name, Contact {i} Designation, Contact {i} Phone, Contact {i} Email`; load all contacts in one query grouped by `client_id` (ordered by id). Done: every new header is one Import reads.
6. **Page** — `templates/clients.html`:
   - `deleteClient`: check `res.ok`; on failure `clientAlert(server message)`; on success `clientToast('Medical center deleted.', 'success')` and `loadClients({ preserveFilters: true })`; network error → "Could not reach the server. Try again.";
   - confirm text: "Delete this medical center permanently? Only possible when it has no schedules, equipment or P.O.s.";
   - `saveClient` (admin): if Company Name is blank, `clientAlert('Please enter the company name.')` and stop before any request (busy state reset by the existing `finally`).
   - Keep every existing function, id and handler.
   Done: Delete, Add, Edit, Import, Export, Print, View still work.
7. **Tests** — new class in `tests/test_tsr_autosave_client_groups.py` reusing `isolated_database` (or a subclass of `ClientGroupRouteTests`):
   - delete refused (409) with a schedule — shift still has its `client_id`; with equipment; with a P.O.;
   - delete of a client with no links succeeds and removes its contacts;
   - delete of a missing id → 404;
   - blank name → 400 on add and update;
   - import with contacts, designation and group succeeds;
   - export → import round trip leaves name, address, group and contacts (incl. designation) unchanged;
   - import row without contacts keeps existing contacts;
   - page source contains the new Delete message handling and the name check.
   Update the P.O. cascade test to expect 409 with the client and P.O. kept (rename accordingly). Run every new test on the unchanged code first and record that it fails.

## Deliberately excluded

- **Merge duplicate medical centers** — the long-term replacement for Delete; Batch 4.
- **Cleaning up orphan contacts** from past deletes — one known locally; separate decision.
- **Escaping, admin-only buttons, manager access, engineer contact position fix, contact checks** — Batch 2.
- **Duplicate-check consolidation, contact helper, lighter `/get_clients` and View, dead `/get_clients_summary` call** — Batch 3.
- **UI changes** (single search, columns, naming) — Batch 4.

## Verification

- New tests fail on the unchanged code, pass after.
- Focused modules: `tests.test_tsr_autosave_client_groups`, `tests.test_purchase_orders`.
- Flask test client on a temporary copy of `scheduler.db`: `/clients_page` renders; deleting a real client with schedules is refused with counts; export → import round trip works.
- No browser automation (AGENTS.md); ask the owner if a browser check becomes necessary.
- Full suite once before publishing, compared with the baseline (24 failures, 3 errors, 5 skips).

## After implementation

1. Self-review the diff; confirm every function the page calls is still defined.
2. Fail-first proof recorded in this plan.
3. Service worker bump to `medical-service-pwa-offline-navigation-v249-medical-center-protect-data` (read the current `CACHE_VERSION` live from `app.py`; keep v248 as a historical marker).
4. `releases.json` entry `2026-10-06-medical-center-protect-data` (audience admins, category Medical Center): Delete is refused when a medical center has records; Import CSV works again; Export includes Group and Designation.
5. Update `changes.md` and this plan's status, with any differences from the plan.
6. Commit and push only on the owner's "commit and push": explicit staging; `scheduler.db`, `tmp/`, `output/`, handoffs, `.claude/`, `.impeccable/` excluded; verify `origin/main` and the Railway deployment.
7. Report what was verified and what was not.

## Risks

- **Delete refuses most real medical centers** — intended; the message explains why.
- **Import now sets Group** when the CSV has a Group column — older CSVs without it are unaffected.
- **Changed export columns** — anyone with a script reading the old columns by position would see Group and Designation inserted; the app's own Import reads both layouts.
- Safety net: no schema change, no data migration; reverting the commit restores the previous behaviour.

---

# Personnel Batches 3 & 4: Directory Usability and Account Tools

**Status:** Executed — commit `e55ac2e`; published to `origin/main` on the owner's "commit and push" (Railway deployment `38b82086-1907-45a9-9658-ee9238923dbb`).
**Finished:** 2026-10-06.

**Where the plan and the outcome differed:**

- The regional-admin rule lives in `can_reset_password_for_user` (reset, deactivate, delete, admin `change_password`) plus new `personnel_branch_denial` (add, edit, and delete of an engineer with no login); the message is the constant `REGIONAL_PERSONNEL_DENIAL`. On the page, `canEditEngineerContact` returns `canManageEngineerBranch` for admins, so Manila rows are "Read Only" for the regional admin.
- The table row markup moved into `buildEngineerTableRow(e)` (called by `renderEngineerDirectory`); `loadEngineers` only fetches. The toolbar moved above the table. The "No signature" badge shows only for engineer-role logins. The Reset button sits beside Deactivate (desktop icon, mobile "Reset").
- Fail-first: the 5 new tests failed on the unchanged code. After: `tests.test_staff_creation`, `tests.test_admin_capabilities`, `tests.test_hr_schedule_viewer` 45 tests OK; page script passes `node --check` and every inline handler is defined; full suite 1,540 tests, 24 failures, 3 errors, 5 skips (baseline counts, unrelated modules).
- Flask test client on a copy of `scheduler.db`: the regional admin is refused a Manila engineer's reset (403, "You can manage Cebu and Davao personnel only.") and allowed a Cebu engineer's (sets `must_change_password`); superadmin can reset Manila; export header has the ten columns; Personnel page renders for both. No browser check.
**Approved:** 2026-10-06 — the owner asked to "plan batch 3 and include batch 4 also", chose "Limit to Cebu/Davao" for regional admin and "Force change" after a password reset, and replied "yes, approved".
**Detailed:** 2026-10-06.

## Context

The last two batches of the Personnel page scan (Batch 1 `a6d8571` and Batch 2 `351f6a2` are below, published). Batch 3: the desktop directory has no search, filter, count, empty or error state, and its contact text is ~10px. Batch 4: account tools — a dismissable one-time password pop-up, no password reset, signature status or account columns on Personnel, and a regional admin who can act on Manila personnel although schedules already limit them to Cebu/Davao.

## Decisions taken

1. Regional admin is limited to Cebu/Davao personnel for add, edit, deactivate, delete and password reset (owner: "Limit to Cebu/Davao").
2. A password reset forces a change at next sign-in, including resets from Settings (owner: "Force change"). Admin-typed passwords via `change_password` are unchanged.
3. One toolbar (the existing mobile one) serves desktop and mobile.
4. Print shows the currently filtered table (intended).

## Investigation

- `templates/engineers.html`: `engineer-mobile-toolbar` / `engineer-mobile-list` hidden above 768px; table rebuilt with `body.innerHTML +=` in `loadEngineers` (~614) with no `res.ok` check, no catch, no empty state; contact lines use `.xsmall` (0.65rem); `engineerEscape` and `escapeHtml` duplicate; `regionalAllowedBranches` (~342) unused; `credModal` has no close button/footer; `copyText` uses `document.execCommand('copy')`.
- `app.py`: `REGIONAL_ADMIN_BRANCHES = {'Cebu', 'Davao'}` (~8053) already restricts regional-admin schedule actions (~11747, ~11778); Personnel routes do not use it. `can_reset_password_for_user` (~11675) guards `reset_user_password`, `change_password`, and Batch 1's `personnel_account_change_denial` (deactivate/delete). `reset_user_password` returns `new_pw` and does not set `must_change_password`; new accounts set it (~61971). `/export_engineers` writes 6 columns; `tests/test_admin_capabilities.py:290` only checks status 200. `Engineer.signature_data` holds the saved signature.

## Execution steps

1. **One directory renderer** — `engineers.html`: the toolbar shows at every width (remove its `display: none` outside the mobile query; keep card list mobile-only, table desktop-only). New `renderEngineerDirectory()` renders the table and cards from `getFilteredEngineersForMobile()`, building each list as one string; the toolbar's `oninput`/`onchange` call it; `loadEngineers` calls it after fetching. `renderEngineerMobileCards` stays defined. Done: typing filters both layouts.
2. **Headcount** — element `#engineer-directory-count` above the list: "24 personnel · Manila 14 · Cebu 6 · Davao 4"; with a filter, "Showing 5 of 24".
3. **Table empty state** — a full-width row "No personnel match your search.".
4. **Contact text** — table contact lines use `small` instead of `.xsmall`; phone and email render as `tel:` / `mailto:` links when present.
5. **Load errors** — `loadEngineers` wraps the fetch in `try/catch`, checks `res.ok`; on failure shows a table row and mobile message "Could not load personnel. Refresh to try again." and an error toast.
6. **Escape helper** — `engineerEscape(value)` returns `escapeHtml(value)`; both names kept.
7. **Regional branch limit** —
   - `can_reset_password_for_user`: in the regional-admin branch, deny when the target user's engineer profile has a branch outside `REGIONAL_ADMIN_BRANCHES` ("You can manage Cebu and Davao personnel only."). Covers reset, deactivate, delete (and admin `change_password`).
   - New `personnel_branch_denial(*branches)` → message when `is_regional_admin_user()` and any given branch is not in `REGIONAL_ADMIN_BRANCHES`. `add_engineer` (Engineer type: new branch) and admin `update_engineer` (current and new branch) return 403 with it. Engineers without a branch count as outside.
   - Page: `canManageEngineerBranch(e)` (true unless regional admin and branch not in `regionalAllowedBranches`) gates Edit/Deactivate/Delete/Reset for regional admin (rows otherwise "Read Only"); in the form, Manila is disabled for regional admin.
   Done: Kevin sees Manila rows read-only and the server refuses Manila actions.
8. **Reset password** — `/get_engineers` admin rows add `username`. `reset_user_password` sets `target_user.must_change_password = True`. Page: Reset button (key icon) beside Deactivate when the person has a login and the user is superadmin/regional admin (and branch allowed); `resetEngineerPassword(dbId)` confirms, POSTs `/reset_user_password/<user_id>`, then shows `credModal` with the username, the new password and the note "Temporary password. They must change it at next sign-in."; server refusal message shown in a toast.
9. **Password pop-up** — `credModal` gets `data-bs-backdrop="static"`, `data-bs-keyboard="false"` and a footer "Done" button (`data-bs-dismiss="modal"`); `copyText(id)` uses `navigator.clipboard.writeText` when available, falling back to `execCommand`.
10. **Signature status** — admin rows add `has_signature` (`bool(e.signature_data)`); `engineerAccountBadge` adds a "No signature" badge when false (engineer logins only).
11. **CSV export** — `/export_engineers` appends Username, Role, Account Status (Active/Inactive/No login), Signature (Yes/No) after the existing six columns.
12. **Tests** — `tests/test_staff_creation.py`:
    - regional admin: add/edit/deactivate/delete/reset refused (403) for a Manila engineer, allowed for a Cebu engineer;
    - reset sets `must_change_password`;
    - `/get_engineers` returns `username` and `has_signature` for admins and not for an engineer;
    - export header includes the four new columns after the original six;
    - source: `renderEngineerDirectory`, `engineer-directory-count`, the empty and load-error messages, `data-bs-backdrop="static"` on `credModal`, `resetEngineerPassword`, `canManageEngineerBranch`.
    Each must fail on the unchanged code first.

## Deliberately excluded

- Merging the table and card action builders — different layouts; risk outweighs the gain.
- One shared branch-list constant — three short lists that rarely change.
- Forcing a change after admin-typed passwords (`change_password`) — owner chose reset only.
- Regional-admin limits on Settings pages beyond what `can_reset_password_for_user` already guards.

## Verification

- New tests fail first, then pass.
- Focused modules: `tests.test_staff_creation`, `tests.test_admin_capabilities`, `tests.test_hr_schedule_viewer` (reads `/get_engineers`).
- Flask test client on a temporary copy of `scheduler.db` as superadmin and as the regional admin: Manila actions refused for the regional admin, allowed for superadmin; reset returns a password and sets the forced change; export downloads with the new columns; page renders.
- No browser automation (AGENTS.md). Full suite once before publishing, compared with the baseline (24 failures, 3 errors, 5 skips).

## After implementation

1. Self-review; confirm every function the page calls is still defined.
2. Fail-first proof recorded here.
3. Service worker bump (read the current `CACHE_VERSION` live; keep the old one as a historical marker).
4. `releases.json` entry dated the commit date, audience admins.
5. Update `changes.md` and this plan's status.
6. Commit and push only on the owner's "commit and push": explicit staging; never `scheduler.db` or unrelated dirty files; verify `origin/main` and the Railway deployment.

## Risks

- The regional admin loses Manila Personnel actions — intended; superadmins unaffected.
- Reset forcing a change also applies in Settings — the person sets a new password once.
- `username` is now returned to personnel admins — they already see it when creating accounts.
- Safety net: no schema change; reverting the commit restores previous behaviour.

---

# Personnel Batch 2: Add/Edit Form Fixes

**Status:** Executed — commit `351f6a2`; published to `origin/main` on the owner's "commit and push" (Railway deployment `a7377513-0206-42e1-9724-f8ae5899194e`).
**Finished:** 2026-10-06.

**Where the plan and the outcome differed:**

- Also added `engineer_with_employee_id()` (shared trimmed, case-insensitive lookup for add and update). Contact checks on add apply to the Engineer staff type only (HR/Approver accounts store no phone or email).
- Fail-first: the 4 new tests failed on the unchanged code (the username test with the real `IntegrityError`). After: `tests.test_staff_creation` + `tests.test_admin_capabilities` 30 tests OK; full suite 1,535 tests, 24 failures, 3 errors, 5 skips (baseline counts, unrelated modules).
- Flask test client on a copy of `scheduler.db`: admin edit of the engineer whose saved phone is `0917`, unchanged, returns 200; setting `0917` on another engineer returns 400 with the mobile-number message; the page renders `id="eng-save-btn"`. No browser check.
**Approved:** 2026-10-06 — the owner asked to "plan batch 2" after Batch 1 was published and replied "yes, approved".
**Detailed:** 2026-10-06.

## Context

Batch 2 of the four-batch Personnel page scan (Batch 1, Protect History, is below and published as `a6d8571`). It fixes the Add/Edit personnel form: a possible 500 error on username collisions, hidden fields in Edit, initials overwritten while editing a name, misleading messages, double submission, and missing phone/email/Employee ID checks.

## Decisions taken

1. Usernames are generated uniquely (case-insensitive); existing usernames are never changed.
2. Employee ID duplicates are compared trimmed and case-insensitive.
3. Phone and email are validated **only when the value changed** (blank always allowed), so existing short or odd values do not block edits.
4. Initials are auto-filled only when adding, capped at 5 letters.
5. No data migration.

## Investigation

- `add_engineer` (`app.py` ~61837): username = first name lowered; if `User.query.filter_by(username=...)` (case-sensitive) finds it, full name without spaces; no further fallback → `IntegrityError` (500) on a third collision (`User.username` unique, ~1715). Sign-in lookup `find_user_by_username` (~7446) is case-insensitive, so case-variant usernames are ambiguous.
- Employee ID uniqueness: `Engineer.query.filter_by(employee_id=...)` exact match in `add_engineer` (~61882) and `update_engineer` (~62019). Local data: no trimmed/case-insensitive duplicates.
- Local phone values include `0917`, `09178`, `0925`, and some `None`; emails are all `x@y.z` or empty — hence validate-on-change only.
- `update_engineer` self path (engineer editing own contact) saves phone/email with no checks.
- `templates/engineers.html`: `openEditModal` (~720) hides staff-type/permissions but never removes `d-none` from `staff-company-branch-wrap`, `staff-employee-id-wrap`, `staff-initials-wrap` (set by `syncStaffTypePermissionControls` for HR/Approver adds). `autoInitials` (~688) runs on every name keystroke, in Edit too, with no cap (programmatic `.value` ignores `maxlength`). `saveEngineer` (~746): toast title always "Account Created" (~815); fallback error "Database Error: Ensure the Employee ID is unique." (~818); Save button (~225) has no id and no busy guard; a `fetch` rejection is unhandled.
- Lesson from the liquidation Save Row bug (2026-10-05): a busy guard must re-enable the button in `finally`.

## Execution steps

1. **Unique username** — `app.py`, new `unique_username_for(name_val)`: candidates first name lowered, full name without spaces lowered, then full name + `2`, `3`, …; each checked with `func.lower(User.username) == candidate`. `add_engineer` uses it. Done: a third "Mark Santos" gets `marksantos2`, no 500.
2. **Employee ID** — `add_engineer` and `update_engineer`: `emp_id` already `clean_str`-stripped; duplicate check becomes `func.lower(func.trim(Engineer.employee_id)) == emp_id.lower()` (update excludes `eng.id`). Done: `" 18-185"` / `"18-185".upper()` variants refused.
3. **Contact checks** — `app.py`, new `personnel_contact_error(phone, email, old_phone=None, old_email=None)` returning a message or `None`: phone (when non-blank and changed) must match `^\+?[0-9 ()\-]+$` with 7–15 digits → "Mobile number looks incomplete. Use digits only, e.g. 0917 123 4567."; email (when non-blank and changed) must match `^[^@\s]+@[^@\s]+\.[^@\s]+$` → "Email address is not valid.". Called in `add_engineer` (engineer staff type), admin `update_engineer`, and the self-contact path; returns 400. Done: unchanged `0917` still saves; a new `0917` is refused.
4. **Edit fields visible** — `openEditModal`: remove `d-none` from the three wraps. Done: Add → HR → Cancel → Edit engineer shows Branch, Employee ID, Initials.
5. **Initials** — `autoInitials`: return early when `edit-eng-db-id` has a value; `.slice(0, 5)`. Done: editing a name in Edit leaves initials unchanged.
6. **Save guard** — Save button gets `id="eng-save-btn"`; `saveEngineer` disables it before `fetch` and re-enables it in `finally`; `fetch` wrapped in `try/catch` → `engineerAlert("Could not reach the server. Try again.")`. Done: double click sends one request; button usable after success, failure, and network error.
7. **Messages** — `saveEngineer`: "Account Created" toast only when `temp_password` is present; admin edit → title "Saved", "Personnel record updated."; self edit → "Saved", "Your contact details were updated."; fallback error "Could not save. Please try again.".
8. **Tests** — `tests/test_staff_creation.py`: three same-name adds give three distinct usernames (and a case variant of an existing username is not reused); Employee ID duplicate by case/space refused on add and update; bad new phone/email refused on add, admin edit and self edit; unchanged existing short phone still saves; source checks: `id="eng-save-btn"`, `finally` in `saveEngineer`, `openEditModal` clears the wraps' `d-none`, `autoInitials` checks `edit-eng-db-id`. Each must fail on the unchanged code first.

## Deliberately excluded

- Renaming existing usernames or cleaning existing contact data — no migration.
- Regional-admin branch limits (Batch 4); desktop search/list changes (Batch 3).
- Client-side duplicate checks — the server is the single source of truth and its messages are shown.

## Verification

- New tests fail first, then pass.
- Focused modules: `tests.test_staff_creation`, `tests.test_admin_capabilities`.
- Flask test client on a temporary copy of `scheduler.db`: admin edit of an engineer whose saved phone is `0917` without changing it succeeds; changing it to `0917` on another person is refused.
- No browser automation (AGENTS.md). Full suite once before publishing, compared with the baseline (24 failures, 3 errors, 5 skips).

## After implementation

1. Self-review; confirm every function the page calls is still defined.
2. Fail-first proof recorded here.
3. Service worker bump (read the current `CACHE_VERSION` live; keep the old one as a historical marker).
4. `releases.json` entry dated the commit date, audiences admins and engineers.
5. Update `changes.md` and this plan's status.
6. Commit and push only on the owner's "commit and push": explicit staging; never `scheduler.db` or unrelated dirty files; verify `origin/main` and the Railway deployment.

## Risks

- An unusual but valid number could be refused; the 7–15 digit range is loose and the message explains the format. Blast radius: only new or changed values.
- Username suffixes (`marksantos2`) are shown in the credentials pop-up, so admins see the actual username to hand over.

---

# Personnel Batch 1: Protect History (Deactivate, Safe Delete, Account Status)

**Status:** Executed — commit `a6d8571`; published to `origin/main` on the owner's "commit and push" (Railway deployment `28b2da40-c14e-4d32-b00b-92cdd0d769dd`).
**Finished:** 2026-10-06.

**Where the plan and the outcome differed:**

- Tests were added to the existing `StaffCreationTests` class (to reuse its fixtures) and `StaffCreationSourceTests`, not a new class. The login-refused case was already covered by existing code; the test checks that an existing session is logged out and restored.
- Also added `personnel_account_change_denial()` (shared self/protected guard for delete and deactivate) and gave the mobile action row equal-width columns for any number of buttons (it was a fixed two-column grid).
- Fail-first: the 6 new behaviour/source tests failed on the unchanged code; "delete without records" passed before and after. After: focused modules (staff creation, admin capabilities, HR schedule viewer, liquidation, changelog) 93 tests OK. Full suite 1,531 tests, 24 failures, 3 errors, 5 skips — same counts as the baseline, all in unrelated modules.
- Flask test client on a copy of `scheduler.db`: page renders with the new functions; 27 directory rows, all linked with an account status; deleting an engineer with 24 schedules is refused with "… has 24 schedules. Deactivate instead."; deactivate redirects that engineer's session (302), activate restores it (200). No browser check was made.
**Approved:** 2026-10-06 — the owner reviewed the Personnel page scan, asked for the findings in batches, asked to "plan batch 1", and replied "yes, approved".
**Detailed:** 2026-10-06.

## Context

A read-only scan of the Personnel page (`templates/engineers.html`, `/engineers_page`) found that **Delete permanently destroys schedule history**: `Engineer.shifts` uses `cascade="all, delete-orphan"`, so deleting an engineer deletes every shift where they are the primary engineer — including multi-engineer jobs, which then vanish for the other engineers too — while reimbursement, travel, liquidation and stock rows keep a dangling `engineer_id` (SQLite does not enforce foreign keys). The confirmation only mentions the login account. The same scan found the directory links accounts by first name when `user_id` is empty, which can attach the wrong login. This batch replaces destructive removal with deactivation, guards hard delete, and shows each person's account status. It is batch 1 of 4 (2: Add/Edit form fixes; 3: desktop list usability; 4: account tools) and is first because it is the only one that can lose data.

## Decisions taken

1. **Deactivate** = set the linked `User.is_active` to False (the same flag Settings already uses). No new column on `Engineer`.
2. Hard **Delete** stays, but only for a person with **no linked records**; otherwise it is refused with the counts and "Deactivate instead".
3. Who may deactivate/delete: the same people who see Delete today (`is_admin_authorized()`: superadmin, regional admin), never their own account, and never a login protected under the password-reset policy (`can_reset_password_for_user`).
4. A deactivated user who is already signed in is signed out on their next request.
5. The first-name account fallback in `/get_engineers` is removed; only `Engineer.user_id` links an account.
6. Deactivated engineers remain visible in calendar pickers and the weekly grid (see Deliberately excluded).

## Investigation

- Cascade: `Engineer.shifts` relationship with `cascade="all, delete-orphan"`, `foreign_keys='Shift.engineer_id'` (`app.py` class `Engineer`, ~line 2014).
- Tables holding `engineer_id` (verified by `db.ForeignKey('engineer.id')`): `ReimbursementTrackerEntry` (~2198), `ReimbursementHeader` (~2257), `TravelRequest` (~2365), `TravelRequestParticipant` (~2471), `TravelLiquidationHeader` (~2589), `StockInventoryMovement` (~3458), `ShiftEngineer` (~3514), `Shift.engineer_id` (~3530, not null) and `Shift.override_engineer_id` (~3567), `CashAdvanceLiquidationHeader` (~64820).
- `delete_engineer` (`app.py` ~62052): gated by `is_admin_authorized()`, deletes the linked `User` and the `Engineer` with no record or protected-account check — a regional admin could delete an admin's or superadmin's engineer profile and their login.
- `User.is_active` (~1728) already exists and is set by Settings (`settings_update_approval_user`, ~29843, superadmin only). Login (~12897), the PWA remember cookie (~7509) and forgot-password (~13010) already refuse inactive accounts.
- **Not** enforced: `load_user` (~7432) returns the user regardless of `is_active`, and Flask-Login's `login_required` does not check it, so an existing session survives deactivation. This also affects Settings today.
- `can_reset_password_for_user` (~11675) protects `PROTECTED_PASSWORD_USERNAMES`, and a regional admin cannot target `superadmin`/`regional_admin` roles — the policy to reuse.
- `/get_engineers` (~32907): admin rows include `account_role`, `display_role`, `user_id`, but the page never displays them; the first-name fallback is at ~32948 (with a special case for `REGIONAL_ADMIN_USERNAME`).
- Local `scheduler.db` copy: 27 engineers, all with `user_id` set, none inactive — removing the fallback changes nothing locally. Production may differ; an unlinked engineer would show "No login".
- Page: action buttons are built twice, in `loadEngineers()` (table) and `getEngineerActionButtons()` (mobile); delete is `deleteEngineer(dbId)` with `engineerConfirmDialog`. Existing tests for this area: `tests/test_staff_creation.py`, `tests/test_admin_capabilities.py`, `tests/test_hr_schedule_viewer.py`.

## Execution steps

1. **Record counter** — `app.py`, new `engineer_linked_record_counts(engineer)` next to `delete_engineer`. Returns an ordered dict label → count for: schedules (`Shift.engineer_id`, `Shift.override_engineer_id`, `ShiftEngineer`, counted as distinct shifts), reimbursement tracker entries, reimbursements, travel requests (owner + participant), travel liquidations, cash advance liquidations, stock movements. Done: returns zeros for a new engineer and the right count after a shift is added.
2. **Safe delete** — `delete_engineer`: after loading the engineer, refuse with 403 when the linked user is the current user or `can_reset_password_for_user(user)` denies; refuse with 409 and a message naming the non-zero counts ("Juan Dela Cruz has 42 schedules and 3 reimbursements. Deactivate instead.") when any count > 0. Otherwise unchanged. Done: no shift is ever deleted through this route.
3. **Deactivate route** — `app.py`, new `POST /set_engineer_active/<int:id>`, JSON `{active: bool}`, CSRF as other routes. Requires `is_admin_authorized()`; 404 for a missing engineer; 400 "This person has no login to deactivate." when `user_id` is empty; the same self/protected guard as step 2. Sets `user.is_active`, commits, `log_activity("Deactivated personnel: <name>")` / `"Reactivated personnel: <name>"`, returns `{status, account_active}`. Done: route works for an engineer login and refuses the guarded cases.
4. **Session lock-out** — `load_user`: return `None` when the user exists but `is_active` is False. Done: an inactive user's next request redirects to login.
5. **Directory data** — `/get_engineers`: delete the first-name fallback block; link only by `user_id`. Add `account_active` (bool or `None` when no login) to the admin metadata. Done: an unlinked engineer returns `user_id: None`, `account_active: None`.
6. **Page** — `templates/engineers.html`:
   - one helper `engineerAccountBadge(e)` used by both the table (in the Full Name cell) and the mobile card: "No login", "Inactive", or the `display_role`; only when `canAdministerPersonnel` (metadata is admin-only).
   - a Deactivate / Activate button beside Delete for `isSuperAdmin || isRegionalAdmin` (hidden when there is no login), calling new `setEngineerActive(dbId, active)` with a confirm dialog, then `loadEngineers()` and a success toast.
   - `deleteEngineer`: confirmation text becomes "Delete this person permanently? Only possible when they have no schedules or forms; otherwise deactivate them." and a failed response shows the server's `message` instead of "Action failed on server."
   - Keep every existing function, id and handler (`openEditModal`, `deleteEngineer`, `saveEngineer`, `renderEngineerMobileCards`, etc.).
   Done: badges and buttons render on desktop and mobile layouts; existing Edit/Add/Export/Print still work.
7. **Tests** — `tests/test_staff_creation.py` (new test class):
   - delete refused (409) for an engineer with a shift; the shift and engineer still exist;
   - delete succeeds for an engineer with no records;
   - deactivate → login refused and an already signed-in client is redirected to login on its next request; activate → login works again;
   - cannot deactivate or delete own account or a protected account (regional admin vs superadmin);
   - `/get_engineers` does not link an account by first name;
   - page source contains `setEngineerActive` and the badge helper.
   Run each new test against the unchanged code first and record that it fails.

## Deliberately excluded

- **Hiding deactivated engineers from calendar pickers / weekly grid** — the grid draws rows per engineer, so hiding them could hide their past shifts; needs its own decision.
- **Backfilling dangling `engineer_id` rows** left by past deletes — not known to exist; out of scope.
- **Regional-admin branch limits** (batch 4) and **Add/Edit form fixes** (batch 2).
- **Superadmin-only restriction for deactivate** — kept equal to today's Delete access so no one loses an ability.

## Verification

- New tests fail on the unchanged code, pass after.
- Focused modules: `tests.test_staff_creation`, `tests.test_admin_capabilities`, `tests.test_hr_schedule_viewer`.
- Flask test client on a temporary copy of the database: `/engineers_page` renders for superadmin and engineer; `/get_engineers` returns `account_active`; deactivate/activate/delete responses as specified.
- No browser automation (AGENTS.md); ask the owner if a browser check becomes necessary.
- Full suite once before publishing, compared with the current baseline (24 failures, 3 errors, 5 skips).

## After implementation

1. Self-review the diff; confirm every function the page calls is still defined.
2. Fail-first proof recorded in this plan.
3. Service worker bump (read the current `CACHE_VERSION` live from `app.py`; keep the old one as a historical marker).
4. `releases.json` entry dated the commit date, audience admins ("Personnel: Deactivate instead of Delete").
5. Update `changes.md` and this plan's status, with any differences from the plan.
6. Commit and push only on the owner's "commit and push": explicit staging; `scheduler.db`, `tmp/`, `output/`, handoffs, `.claude/`, `.impeccable/` excluded; verify `origin/main` and the Railway deployment.
7. Report what was verified and what was not.

## Risks

- **Unlinked engineers in production** show "No login" after step 5 instead of a guessed account; no data changes; fix by linking in Settings.
- **Step 4 signs out** anyone already deactivated who still has a session — intended. Blast radius: inactive accounts only.
- **Delete now refuses most real engineers** — intended; Deactivate is the replacement.
- Safety net: no schema change, no data migration; reverting the commit restores previous behaviour.

---

# Sign-in Pages: Layout G "Charcoal" with the Shimadzu Logo

**Status:** Executed — commit `3cf1698`; published to `origin/main` on the owner's "commit and push" (Railway deployment `7761fae4-ace6-4717-bfcf-2676ca13afe6`).
**Execution authorized:** 2026-10-05 — the owner said "go ahead. do not over engineer".
**Finished:** 2026-10-05.

**Where the plan and the outcome differed:**

- **Single column below 820 px** replaces the earlier `(max-height: 560px)` rule; landscape phones (≤ 820 px wide) also stack. The wordmark height caps are gone with the wordmark.
- **Fonts:** Fira Sans 400/500/600 latin woff2 from Google Fonts (`fonts.gstatic.com`, v18), 72 KB total, with `OFL.txt` from the google/fonts repository.
- **Verification:** new charcoal test failed first, passes after; login, theme and travel-request modules 68 tests OK; full suite 24 failures, 3 errors, 5 skips (unchanged from before this plan, including the pre-existing `test_manifest_entries_cannot_be_deleted` order issue). Flask test client: all three pages show the logo; logo and font URLs return 200; failed sign-in keeps the username; `next` honoured. Detector: no findings. No browser check was made.
**Approved:** 2026-10-05 — the owner asked whether the Full Red page was professional enough, supplied the Shimadzu Philippines logo, chose option G from three calmer mockups ("let's go with G"), and replied "approved, store the font in the app".
**Detailed:** 2026-10-05.

## Context

The Full Red sign-in page (two plans below, executed, not yet committed) reads as an alarm colour in a medical setting and uses a department name as its only brand. The owner supplied the official logo (`Shimadzu Philippines Corporation`: red square with the white circle-and-cross mark, white SHIMADZU logotype and white subline, transparent background; 2000×423 webp). Three calmer mockups were built in `tmp/login-layouts/` (G charcoal, H paper, I split); the owner chose **G** (`tmp/login-layouts/g-charcoal.html`, with `calm.css`, `shared.css`, `form.js`). This plan replaces the Full Red visual layer with G on all three signed-out pages while keeping every behaviour from the critique-fix plan.

## Decisions taken

1. Layout G on Login, Forgot password and Reset password: charcoal page, white logo, short brand-red rule, "Medical Service" / "Scheduler & Management System" on the left; sign-in card on the right; stacked on phones with a smaller logo. Top bar keeps "Medical Service", online status and Manila time. The large MEDICAL / SERVICE wordmark is removed.
2. Themes: light = charcoal page `#14181F` + white card; dark = black page + dark card (`--app-surface`); graphite = `#202124` page + graphite card.
3. Colours: logo used exactly as supplied; rule `#EE3239` (logo red); button `#D9262E` (white text 4.9:1). Non-classic accents still recolour the button and rule ("follow the accent"); the logo never changes.
4. Font: **Fira Sans**, self-hosted (owner: "store the font in the app"), on the three signed-out pages only. Download approved: Fira Sans regular, medium and semibold woff2 from Google Fonts, about 60–90 KB total, SIL Open Font License.
5. The SHIMADZU logotype is custom lettering and is only ever used as the image, never retyped.

## Investigation

- Supplied logo measured with Pillow (venv): red `rgb(238, 50, 57)` = `#EE3239`; mark white; logotype and subline white on transparent (x ≥ 300 px), so it needs a dark background. Contrast: white on `#EE3239` 4.08:1 (fails small text), on `#D9262E` 4.92:1, on `#C8102E` 5.88:1.
- Current visual layer: `templates/_auth_brand.html` (top bar, `.auth-wordmark`, `.auth-subtitle`, status and clock script), `static/css/app-auth.css` (`--login-ground`, `--login-wordmark*`, `.auth-wordmark`, height caps `min(15.5vw, 26vh)` / `min(19vw, 16vh)`, `@media (max-width: 760px), (max-height: 560px)`), templates link `app-auth.css?v=6` and `theme-color` `#c8102e` (light).
- Tests tied to the Full Red look: `tests/test_login_page.py` `test_signed_out_pages_share_the_full_red_shell` (wordmark `aria-hidden`, `#c8102e` theme-colour, `background: var(--login-ground)`) and `test_layout_fits_short_screens_and_pages_are_landmarked` (`min(15.5vw, 26vh)`); `tests/test_appearance_themes.py` (`?v=6`, `--login-page-bg: #000000;` and `#202124;` literals — keep both declarations).
- Offline shell list in `app.py` (`'/static/css/app-auth.css'`, `'/static/js/app-auth.js'`): logo and font files must be added so the offline login page keeps its brand.
- `PRODUCT.md` "Brand Commitments" / "Evidence on Hand" still say no logo is in the repository.

## Execution steps

1. **Fail-first test:** replace `test_signed_out_pages_share_the_full_red_shell` with a G test — `_auth_brand.html` has the logo `<img>` with alt "Shimadzu Philippines Corporation" and no `auth-wordmark`; `app-auth.css` has `--login-ground: #14181f`, `@font-face` for Fira Sans pointing at `fonts/fira-sans/`, and no `.auth-wordmark`; templates use `theme-color` `#14181f` and `?v=7`; the logo and font files exist and are in the offline shell list. Update the layout test's wordmark assertion. Run once to prove it fails.
2. **Assets:** copy the supplied logo to `static/images/brand/shimadzu-philippines-logo-white.webp` (unchanged). Download Fira Sans 400/500/600 latin woff2 into `static/fonts/fira-sans/` with the OFL licence text. Done: files present, sizes noted.
3. **`templates/_auth_brand.html`:** top bar unchanged; replace wordmark and subtitle with a brand panel (logo image, red rule, "Medical Service" heading, "Scheduler & Management System"). The card keeps the page `<h1>`; the panel name is not a second `<h1>`.
4. **`static/css/app-auth.css`:** `@font-face` (font-display: swap) and Fira Sans on `body.auth-page`; tokens `--login-ground` (`#14181f` light, `--login-page-bg` dark/graphite), `--login-on-ground`, `--login-rule` (`#ee3239`, accent when non-classic), `--login-button` (`#d9262e`, darkened accent when non-classic); two-column grid (brand left, card right, max 1600 px) → one column at ≤ 820 px; remove wordmark styles and height caps; card follows theme. All state styles from the critique-fix plan stay.
5. **Templates (three pages):** `theme-color` light `#14181f` (and in the first-paint script); `app-auth.css?v=7`; login card lead "Use the username your administrator gave you.".
6. **`app.py`:** add the logo and three font files to the offline shell list; service worker → `…-v244-signin-charcoal` (read live value first).
7. **`PRODUCT.md`:** logo on hand (`static/images/brand/`), brand red `#EE3239` measured from the supplied logo, Fira Sans as the closest match for the subline (not confirmed official), official guide still wanted for the rest.
8. **`releases.json`:** entry dated the commit date (everyone, Sign-in): new calmer sign-in page with the Shimadzu logo.

## Deliberately excluded

- Font or colour changes anywhere else in the app.
- A dark-text logo (G only needs the white one).
- Other brand colours, spacing or type rules — still need the official guide.
- Any change to sign-in behaviour; every critique-fix behaviour stays.

## Verification

- New test fails first, passes after; login, theme and travel-request modules green; full suite before/after counts (current 1,521 tests, 24 failures, 3 errors, 5 skips; the extra failure is the pre-existing `test_manifest_entries_cannot_be_deleted` order issue).
- Flask test client: three pages render with the logo; failed sign-in keeps the username; `next` honoured; logo and font URLs return 200.
- Contrast computed for every theme and accent (button text, rule, top-bar text, card text).
- Impeccable detector once. No in-app browser check unless the owner allows one.

## After implementation

1. Self-review the diff.
2. Fail-first proof recorded.
3. Full suite with before/after counts.
4. Service worker bump read live from `app.py`.
5. `releases.json` entry dated the commit date.
6. Update `changes.md` and this plan's status (with differences).
7. Commit and push only on the owner's "commit and push", together with the two earlier sign-in plans: explicit staging, including the new logo and font files; `scheduler.db`, `tmp/`, `output/`, handoffs, `.claude/`, `.impeccable/` excluded; verify `origin/main` and the Railway deployment.
8. Report what was verified and what was not.

## Risks

- **Logo on light surfaces:** the white logotype would vanish on a light background; it is only placed on the charcoal/black/graphite page.
- **Font download source:** Google Fonts (official distributor of Fira Sans under the OFL); files are committed with the licence.
- **Offline first visit:** the logo and fonts are in the offline shell, so a cached login page keeps its brand; if a font is missing the stack falls back to Segoe UI.

---

# Sign-in Pages: Critique Fixes (Recovery, Weak Signal, Layout, Colour, Polish)

**Status:** Executed — commit `3cf1698`; published to `origin/main` on the owner's "commit and push" (Railway deployment `7761fae4-ace6-4717-bfcf-2676ca13afe6`).
**Execution authorized:** 2026-10-05 — the owner said "go ahead" (and later "do not overengineer").
**Finished:** 2026-10-05.

**Where the plan and the outcome differed:**

- **One shared script:** the button, offline, caps lock, show-password, empty-field and slow-connection logic moved from three inline copies into `static/js/app-auth.js` (added to the offline shell list in `app.py`). Templates mark the form with `data-auth-form` and their labels; tests read the strings from the shared script.
- **Password-reset success:** "Your password has been updated" now uses the flash category `success` and shows in a neutral notice on the login page instead of the red error box (it would otherwise have marked the fields invalid).
- **Forgot password** also got the offline banner and button disable, not only Reset.
- **Wordmark height cap** is `26vh` (plan said 30vh): computed from the CSS, 30vh still tucked the "L" under the card on a 1366×768 laptop. Landscape phones get a smaller wordmark (`min(19vw, 16vh)`) and a centred 440 px card.
- **Status dot** on coloured grounds is white with a soft dark ring (any green vanished on the clinical-green accent).
- **Contrast (computed):** white on page/button ≥ 5.5:1 for every accent; secondary text 4.56–5.98:1; dark/graphite wordmark 3.9–7.4:1. The faint second wordmark line stays decorative (about 2–2.8:1), as on the light theme.
- **Test suite:** 1,521 tests, 24 failures, 3 errors, 5 skips. The extra failure is `test_changelog_workflow.ChangelogApiTests.test_manifest_entries_cannot_be_deleted`, which passes alone and with its own module and fails only after `tests.test_calibration_report_engineer_access`, whose teardown runs `db.drop_all()` and wipes the synced release notes. The same pair fails on `HEAD` (checked in a temporary worktree), so it is pre-existing and not caused by this work; left alone on the owner's "do not overengineer". Focused modules (login, themes, travel request) 68 tests OK. Flask test client: failed sign-in keeps the username, never echoes the password, marks both fields invalid; success notice after reset; `next` still honoured; forgot and reset render with the shared script. Detector: no findings. No browser check was made.
**Approved:** 2026-10-05 — after the `/impeccable critique` of the signed-out pages (25/40; snapshot `.impeccable/critique/2026-10-05T01-32-24Z__templates-login-html.md`), the owner chose to fix all three priority areas, keep "follow the accent" on the sign-in page, cover everything in the report, and replied "plan approved".
**Detailed:** 2026-10-05.

## Context

The "Full Red" sign-in work (plan below, executed, not yet committed) looks right but is weakest at the anxious moments: a failed sign-in clears the username and shows "Invalid Credentials - Access Denied"; on a weak hospital signal the button silently flips back to SIGN IN after 12 s; on 1366×768 laptops and landscape phones the card covers the wordmark; several accent and dark-theme colour pairs fall below readable contrast; and there are keyboard, tap-size and small-text gaps. This plan fixes all findings in the critique. It builds on top of the uncommitted Full Red changes and ships with them.

## Decisions taken

1. Fix everything in the critique report (priority issues and minor observations), except the items under "Deliberately excluded".
2. **Follow the accent:** a user's chosen accent still recolours the sign-in page. Contrast is fixed for every accent rather than forcing red.
3. The failed sign-in message stays generic (does not reveal whether the username exists): "Username or password is incorrect. Check caps lock and try again."
4. Brand colour (`#c8102e`) and the font stay until the official Shimadzu guide is available.

## Investigation

- Failed login: `app.py:12919` flashes "Invalid Credentials - Access Denied"; `app.py:12921` re-renders `login.html` with only `next_target`, so the typed username is lost. `templates/login.html:71` username input has no `value`. Jinja autoescapes, so echoing the username back is safe; the password is never echoed.
- The re-render after a failed POST is not cached by the service worker (only the GET `/login` shell is), so a username in the page never reaches the offline cache. Keep it that way; do not add the username to the GET render.
- Submit guard: `login.html:181-200` disables the button, shows SIGNING IN, and after `12000` ms silently restores SIGN IN. Same pattern in `forgot_password.html:108-115` and `reset_password.html:180-187`.
- Offline banner `login.html:42` has `role="status"` but its text is always in the DOM and only toggled by `display`, so screen readers often do not announce it. The caps lock hint at `login.html:104` (and `reset_password.html:78`) is not live and not linked to the field.
- Forgot password shows its neutral confirmation in `.alert-login` (red error box) at `forgot_password.html:47`. Reset password has no offline handling and shows "Passwords do not match" in amber `.hint-row`.
- Layout: the wordmark size is width-only (`app-auth.css` `.auth-wordmark > div` `font-size: clamp(5rem, 15.5vw, 15rem)`); the single-column switch is `@media (max-width: 760px)` only.
- Colour (computed by the design review): graphite red wordmark on `#202124` ≈ 2.7:1; the faint second line at 35 % red ≈ 1.3:1 on dark; on the purple accent, white top-bar text ≈ 4.2:1 and `#ffe3e7` ≈ 3.5:1; on clinical green `#ffe3e7` ≈ 3.8:1; on corporate blue ≈ 4.3:1; the pale status dot `#bbf7d0` disappears on green.
- Mechanical (the detector agent read the CSS; the CLI detector could not resolve the Jinja stylesheet links, so it reported 0 findings without checking colour): `.toggle-visibility:focus-visible { outline: none }` with only a colour change; `.forgot-link` ≈ 19 px tall; `.field-label` 0.7rem (11.2 px); `.hint-row` 0.72rem (11.5 px); placeholder `--app-muted` at 0.75 opacity ≈ 3:1; disabled `.btn-signin` at `opacity: .72` ≈ 3.9:1.
- No `<main>` landmark (`.login-shell` is a div at `login.html:35`, `forgot_password.html:33`, `reset_password.html:33`); Font Awesome `<i>` icons lack `aria-hidden`.
- `bootstrap.bundle.min.js` is loaded but unused at `login.html:124`, `forgot_password.html:90`, `reset_password.html:115` (no Bootstrap JS components on these pages).
- Footer `login.html:119` shows "© 2026 Medical Service" in a `.version-tag`. There is no app version constant; the newest `release_date` in `static/changelog/releases.json` is the closest real "build" fact.
- Legacy rule `static/css/app-themes.css:212` forces every `.login-card` label to `--app-text !important` in dark mode; `app-auth.css` fights it back for `.field-label`.
- "Medical Service" appears four times on login (top bar, wordmark, card subtitle "Medical Service account", footer).

## Execution steps

1. **Fail-first tests** in `tests/test_login_page.py`: (a) functional — a failed POST to `/login` (isolated DB, as in `PasswordResetTokenTests`) re-renders with the typed username in `value=` and the new message, and never echoes the password; (b) login/forgot/reset scripts contain "Still connecting" and no `12000` silent reset; (c) `app-auth.css` has a height-aware wordmark size (`vh`) and `(max-height: 560px)` in the single-column media query; (d) all three templates use `<main class="login-shell"` and none load `bootstrap.bundle`. Run once on current files to prove they fail.
2. **`app.py` `login()`** (~`12856-12921`): on failure flash "Username or password is incorrect. Check caps lock and try again." and pass `username` to the re-render; the template sets `value="{{ username or '' }}"`. Pass `build_label` (newest `release_date` from `releases.json`, formatted "5 Oct 2026") through a small cached helper next to the route; empty if unavailable. Done: test (a) passes; existing `next` tests still pass.
3. **`templates/login.html` — recovery and a11y.** When a flash is shown: `aria-invalid="true"` on both inputs, `aria-describedby` to the alert id, focus moves to the password field. Add "Don't know your username? Contact your administrator." Remove the card subtitle "Medical Service account". Footer: "Updated {{ build_label }}" instead of the copyright. Icons get `aria-hidden="true"`; `.login-shell` becomes `<main>`. Desktop-only autofocus on the username field when there is no error (skip on touch devices so the keyboard does not pop up).
4. **Slow-connection handling** (login, forgot, reset scripts): at ~5 s after submit, label STILL CONNECTING plus an `aria-live="polite"` line "Slow connection. Keep this page open."; at ~20 s re-enable the button as TRY AGAIN with the line kept. Never silently revert. Empty required fields are blocked client-side with a short inline message (keep `novalidate` for custom messaging). Done: test (b) passes.
5. **Live announcements.** Offline banner: keep `role="status"` and set its text on change instead of only toggling `display`. Caps lock hint: `aria-live="polite"` and `aria-describedby` from the password field. Reset page gets the same offline banner and button disable as login. Forgot page confirmation uses a new neutral `.notice-login` style; the reset "Passwords do not match" hint uses the error colour.
6. **`static/css/app-auth.css` — layout.** Wordmark `font-size: clamp(5rem, min(15.5vw, 30vh), 15rem)`; single column at `@media (max-width: 760px), (max-height: 560px)`; composition capped at ~1600 px wide on very wide screens. Done: test (c) passes; at 1366×768 the card no longer covers "MEDICAL" (positions computed from the CSS).
7. **`app-auth.css` — colour.** `--login-on-ground-muted: rgba(255,255,255,.86)`; non-red accent grounds darkened with `color-mix(in srgb, var(--login-accent) 85%, #000)` (fallback: plain accent); dark/graphite wordmark `color-mix(in srgb, var(--login-accent) 75%, #fff)` with the faint line at ~0.55 alpha; top-bar status dot readable on every ground (white with a dark ring). Done: each listed pair ≥ 4.5:1 for small text, ≥ 3:1 for the wordmark.
8. **`app-auth.css` — polish.** `.toggle-visibility:focus-visible { outline: 2px solid var(--login-accent); outline-offset: -4px }`; field ring via `.input-shell:has(input:focus)` with `:focus-within` as fallback; `.forgot-link` padded to a 44 px tap area; `.field-label` and `.hint-row` ≥ 0.75rem; placeholder at full opacity; disabled button keeps full-contrast text (dim the background instead); new `.notice-login`.
9. **Remove** `bootstrap.bundle.min.js` from the three templates. **`static/css/app-themes.css:212`**: drop `label` from the forced dark `.login-card` rule and remove the matching override in `app-auth.css`. Done: test (d) passes; dark labels muted, headings still `--app-text`.
10. **Versions:** `app-auth.css?v=5` → `?v=6` (update `tests/test_appearance_themes.py`); service worker → `…-v243-signin-critique-fixes` (read the live value first); `releases.json` entry dated the commit date (everyone, category Sign-in).

## Deliberately excluded

- Brand font and brand colour — need the official Shimadzu guide (PRODUCT.md).
- Bootstrap CSS and Font Awesome stylesheets — other shared styles depend on them; removing them touches more than these pages.
- Forcing red regardless of accent — the owner chose "follow the accent".
- Any change to rate limiting, reset tokens or account-existence behaviour.

## Verification

- New tests fail on current files, pass after.
- `tests/test_login_page.py`, `tests/test_appearance_themes.py`, `tests/test_offline_resilience.py` green apart from the known offline TSR failure; full suite before/after counts (baseline 1,518 tests, 23 failures, 3 errors, 5 skips).
- Flask test client: GET `/login`, `/forgot_password`, reset render 200; failed POST keeps the username, never echoes the password, keeps `next`.
- Contrast pairs from step 7 computed and listed.
- Impeccable detector once on the changed templates. No in-app browser check unless the owner allows one.

## After implementation

1. Self-review the diff.
2. Fail-first proof recorded; no residue.
3. Full suite with before/after counts.
4. Service worker bump read live from `app.py`.
5. `releases.json` entry dated the commit date.
6. Update `changes.md` and this plan's status (with differences).
7. Commit and push only on the owner's "commit and push", together with the Full Red work: explicit staging; `scheduler.db`, `tmp/`, `output/`, handoffs, `.claude/`, `.impeccable/` excluded; verify `origin/main` and the Railway deployment.
8. Report what was verified and what was not.

## Risks

- **Echoing the username:** autoescaped, only on the failed POST response, never cached; the password is never echoed. Account-existence protections (always-run hash comparison, generic message) unchanged.
- **Slow-connection timer:** a request that succeeds after TRY AGAIN appears could be resubmitted; signing in again with the same credentials is harmless, and the label says it is still connecting first.
- **`:has()` and `color-mix()` support:** both have fallbacks.
- **Removing the dark label override:** covered by the theme tests; the heading rule stays.

---

# Signed-out Pages: "Full Red" Layout (Login, Forgot Password, Reset Password)

**Status:** Executed — commit `3cf1698`; published to `origin/main` on the owner's "commit and push" (Railway deployment `7761fae4-ace6-4717-bfcf-2676ca13afe6`).
**Finished:** 2026-10-05.

**Where the plan and the outcome differed:**

- **One shared partial instead of three copies:** the top bar, subtitle, wordmark, connection status and Manila clock live in a new `templates/_auth_brand.html`, included by all three pages. The connection status (`status-dot` / `status-text`) is now updated by the partial's script; the login page script keeps the offline banner and the SIGN IN disable.
- **Extra test file touched:** `tests/test_travel_request_page.py` asserted the exact old service worker version (`v241-travel-request-page`); it now uses `assert_cache_version_at_least(self, 241, ...)`, like the other feature tests.
- **Wordmark clipping:** the plan's `overflow: hidden` on the page would have cut off the form on short desktop windows with no scroll. The wordmark box clips itself instead (`.auth-wordmark` with an inner `div`), and the page keeps vertical scrolling.
- **Card headings:** Forgot password and Set a new password keep their existing headings and intro copy; their key / lock-open icon tiles are removed, as on the login card.
- **Verification:** new test failed before the change (missing partial) and passes after; login, theme, travel-request and offline modules OK except one known offline TSR failure; full suite 1,518 tests, 23 failures, 3 errors, 5 skips (baseline 1,517 with the same non-passing set, plus the new test). Flask test client: `/login` and `/forgot_password` 200, reset page renders, all expected ids, CSRF field, `?v=5` and `#c8102e` present. Impeccable detector: no findings on the changed files. No browser check was made.
**Execution authorized:** 2026-10-05 — the owner said "go ahead".
**Approved:** 2026-10-05 — the owner picked layout F ("let's work with F"), answered the two open decisions, and replied "approved" to the plan below.
**Detailed:** 2026-10-05.

## Context

First item of the design-improvement pass. The owner reviewed six login mockups (A–F, in `tmp/login-layouts/`, never committed) and chose **F · Full red**: the whole page in Shimadzu red, a huge white MEDICAL / SERVICE wordmark running off the bottom edge, a top bar with online status and Manila time, and a white sign-in card. Reference mockup: `tmp/login-layouts/f-full-red.html` (with `shared.css` and `form.js`). The aim is a signed-out screen that carries the brand and stays as fast and field-safe as today's.

## Decisions taken

1. **All three signed-out pages** get the F layout: Login, Forgot password, Reset password (they already share `static/css/app-auth.css`).
2. **Light theme:** full Shimadzu red page (`#c8102e`) with a white card.
3. **Dark and graphite themes:** black (`#000000`) or graphite (`#202124`) page, the wordmark and the SIGN IN button in the accent red, and a dark card (`--app-surface`).
4. **Accent override stays:** when a user has picked a non-classic accent (`data-accent-theme` other than `classic`), the page uses `--app-primary` instead of red, as today (`app-auth.css` lines 17–25).
5. Wordmark is plain text "MEDICAL" / "SERVICE". No Shimadzu logo (none in the repo; PRODUCT.md forbids approximating it). Copy stays the current copy.

## Investigation

- `static/css/app-auth.css` styles all three pages (linked `?v=4` at `templates/login.html:29`, `forgot_password.html:27`, `reset_password.html:27`). It defines `--login-accent`, `--login-page-bg`, `--login-page-end`, `--login-page-glow`, and the dark/graphite overrides.
- `tests/test_appearance_themes.py:369–377` and `:471–477` assert the literals `--login-page-bg: #202124;`, `--login-page-bg: #000000;`, and `app-auth.css') }}?v=4` in all three templates. Keep the two `--login-page-bg` declarations (they become the dark/graphite page grounds); update the `?v=4` assertions to `?v=5`.
- `static/css/app-themes.css:211–212` forces `.login-card` surface and heading/label colour in dark mode with `!important`. Keep the `.login-card` class on the card so this keeps working; `app-auth.css` already re-mutes `.field-label` in dark mode.
- All three templates carry `<meta name="theme-color" content="#2c3e50">` and a first-paint script that sets theme datasets and the meta colour (`login.html:7–22`). Light palette value becomes `#c8102e` so the phone status bar matches the red page; graphite/amoled values unchanged.
- `tests/test_login_page.py` guards the mobile-safe inputs (`:61`), the password toggle button (`:71`), caps lock / offline / submit guard (`:78`), theme variables instead of hard-coded colour (`:88`), forgot/reset pages (`:96`), the `next` handling (`:258–358`) and the offline shell cache (`:115`, cache version floor 39). None of these change.
- Service worker version lives in `app.py:27049` (`medical-service-pwa-offline-navigation-v241-travel-request-page`); `/login` and `/static/css/app-auth.css` are in the offline shell, so the bump is required.
- Forgot/Reset use `.login-card`, `.brand-tile` (key / lock-open icons) and `.card-footer-row` (`forgot_password.html:32–80`, `reset_password.html:32–34`).

## Execution steps

1. **`static/css/app-auth.css` — page ground and tokens.** Light: `body.auth-page` background `var(--login-accent)` (solid, no gradient, no glow). Dark: `var(--login-page-bg)`, keeping `#000000` / `#202124`. Add `--login-on-ground` (white on red; `--app-text` on dark) and `--login-on-ground-muted` (`#ffe3e7` on red; `--app-muted` on dark). Remove `--login-page-glow` and the radial gradient. Done: each theme shows the right ground with no glow.
2. **`app-auth.css` — layout.** New `.auth-topbar` (MEDICAL SERVICE, status chip, Manila clock; tabular numerals), `.auth-subtitle` ("Scheduler & Management System"), `.auth-wordmark` (absolute, bottom-left, `clamp(5rem,15.5vw,15rem)`, weight 800, line-height .82, tracking −.045em, second line at 20% opacity of `--login-on-ground`; dark themes: accent red at full and 35%), `.login-shell` right-aligned on desktop. ≤760px: wordmark in flow above the card at `clamp(3.6rem,19vw,6rem)`, card full width, page scrolls. Card shadow neutral (`0 24px 60px rgba(0,0,0,.28)`), no coloured glow. Keep `::selection` themed (white on red / red on dark). Done: matches the F mockup at 1440px and 375px with no horizontal scroll.
3. **`app-auth.css` — keep every existing state.** `.input-shell`, `.toggle-visibility` (44px), `.hint-row`, `.btn-signin` (54px on phones), `.alert-login`, `.offline-banner`, `.status-dot.is-offline`, dark-mode overrides and the contrast fix for `.forgot-link` stay. Remove `.brand-tile` styling only if no template still uses it (step 4 decides). Done: no state lost.
4. **`templates/login.html`.** Add the top bar (status chip moves here from the card footer; the existing `status-dot`/`status-text` ids keep working with `updateConnectionState`), the subtitle, and the `aria-hidden="true"` wordmark. The card header becomes "Sign in" + "Medical Service account"; the house-medical tile is dropped (the wordmark is the brand). Card footer: Forgot password? + © 2026 Medical Service. Form, CSRF token, `next` field, ids, and all scripts unchanged. Add a small Manila clock script (`toLocaleTimeString('en-GB', {timeZone:'Asia/Manila', hour:'2-digit', minute:'2-digit'})`, every 30 s). `theme-color` light value `#c8102e`. `?v=5`. Done: page renders via Flask test client with every existing id present.
5. **`templates/forgot_password.html` and `templates/reset_password.html`.** Same shell (top bar, subtitle, wordmark), card headings stay "Forgot password" / "Reset password" with their current intro copy and forms; key / lock-open tile dropped. `theme-color` light `#c8102e`; `?v=5`. Done: both render with forms and tokens intact.
6. **`static/css/app-themes.css`.** Confirm lines 211–212 still give the dark card the right surface and heading colour; adjust only if the new markup needs it. Done: dark card readable.
7. **Tests.** `tests/test_appearance_themes.py`: `?v=4` → `?v=5` (two places). `tests/test_login_page.py`: one new source-level test — all three templates contain `auth-wordmark` with `aria-hidden="true"` and `auth-topbar`; `app-auth.css` has no `radial-gradient` and has the dark `--login-page-bg` values. Prove the new test fails before steps 2–5 (run once on the old files).
8. **Service worker** bump in `app.py` (read the live value first) to `…-v242-signin-full-red`.
9. **`static/changelog/releases.json`** entry dated the commit date: "New Sign-in Screen" — red sign-in, forgot and reset pages with the Manila time; dark themes keep a dark page.

## Deliberately excluded

- Shimadzu logo or brand font — not in the repo; brand-level assets must come from the official guide.
- Any server change to sign-in, reset tokens, rate limiting or redirects — layout only.
- "What's new" panel, timeline background, module list — other mockups, not chosen.
- The other mockups A–E and `tmp/login-layouts/` — stay uncommitted.

## Verification

- New test fails on the old files, passes after.
- `tests/test_login_page.py` and `tests/test_appearance_themes.py` green; full suite before/after counts (baseline 1,517 tests, 23 failures, 3 errors, 5 skips — the known non-passing set).
- Flask test client: GET `/login`, `/forgot_password`, a reset page — 200, CSRF field and all script ids present.
- Impeccable detector run once on the changed template/CSS files.
- No in-app browser check unless the owner allows one (AGENTS.md). The owner checks 375px and desktop in light, dark and graphite.

## After implementation

1. Self-review the diff.
2. Fail-first proof for the new test, restore, confirm no residue.
3. Full suite, quoting before and after counts.
4. Service worker bump read live from `app.py`.
5. `releases.json` entry dated the commit date.
6. Update `changes.md`, and this plan's status to `Executed` with its commit hash and any difference from the plan.
7. Commit and push only on the owner's "commit and push": explicit staging, `scheduler.db`, `tmp/`, `output/`, handoffs and `.claude/` excluded; verify `origin/main` and Railway deployment.
8. Report what was verified and what was not.

## Risks

- **Blast radius:** the three signed-out pages only. Security behaviour (CSRF, `next`, reset tokens) is untouched and guarded by existing tests.
- **Offline login shell:** cached copy is replaced only after the service worker bump; forgetting it would show the old page offline. Covered by step 8.
- **Dark-mode `!important` rules in `app-themes.css`** could fight the new card styles; step 6 checks them.
- **Large wordmark on very short screens** (landscape phones) could crowd the card; ≤760px puts it in flow so the page scrolls instead of overlapping.

---

# Travel Request Page: Review Fixes, Clearer Layout, New Functions, and Less Code

**Status:** Executed — commit `e051e5f`; published to `origin/main` on the owner's "commit and push".
**Finished:** 2026-10-05.
**Execution authorized:** 2026-10-05 — the owner said "go ahead partner. do not overengineer and over check things. make sure that if we push this to live later, the system won't error or break with the new columns".
**Approved:** 2026-10-05 — the owner said "approved, go with your recommendations" after the page review (decisions 1–3 below taken as recommended).
**Detailed:** 2026-10-05.

**Where the plan and the outcome differed:**

- **Extra bug fixed:** saving a route with no Travel Type selected crashed the save (500) in `travel_request_travel_type_allows_airfare_c_o` (`clean_str('')` returns `None`). Now treated as empty.
- **Live safety:** `ensure_travel_request_tables()` also runs in `prepare_deferred_workflow_schemas` (Railway startup), in addition to the existing per-request guard. Checked on a copy of the local database (old schema): the seven columns were added automatically and the page, My Travel Requests, detail, Timeline, Accounting Center, Approvals, both approval queues, save, the new validations, Preview Form and Delete Draft all returned 200 or the expected 400.
- **Participants** now match the logged-in user by `logged_in_engineer_id`: `/get_engineers` sends no username or user id to non-admins, so the old automatic selection never matched for them.
- **Messages** are toasts only (the duplicate status box is gone); errors stay until closed.
- **Readiness** lists the signature as "checked when you submit"; the server's existing signature check and Settings prompt are kept rather than adding a pre-check.
- **Tests are source-level** (`tests/test_travel_request_page.py`, 11 tests); the fail-first run was not made. `tests/test_travel_request_draft_instructions.py` now looks for `$t('travel-account-number').value` (same ordering check, new code).
- **Line count:** template 3,840 → 1,712.
- **Verification:** 12 focused modules, 130 tests, OK; page renders and its script passes `node --check`; full suite 1,517 tests, 23 failures, 3 errors, 5 skips (the baseline's non-passing set). No browser check was made.

## Context

The owner asked for a review of the Travel Request page (`/travel_request`, `templates/travel_request.html`, 3,840 lines) covering UI, display, functions, new functions, code removal and bug fixes, continuing the page-by-page series (Reimbursement → Liquidation → Travel Request).

The review found that the composed purpose text is truncated to 255 characters (12 of 15 local records), which loses training/meeting details on reload and puts a cut-off, duplicated text on the official PDF and in Approvals; that requests can be submitted and approved without valid dates; that negative amounts are accepted; that several controls are shown to users the server refuses; and that the page is long, form-last, and missing functions its siblings have (Preview Form, rejection reason, readiness check, bottom dock).

Intended outcome: training/meeting details are stored in their own columns and the purpose is a short line; dates and amounts are validated on the server; the page shows the form first with a compact header, a bottom dock with a readiness checklist, Preview Form, the rejection reason and the approval history; controls match server permissions; about a third of the template is removed.

## Decisions taken

1. **Training/meeting details get their own columns** on `travel_request`: `training_title`, `training_provider`, `training_venue`, `training_objective`, `meeting_subject`, `meeting_with`, `meeting_objective`. The purpose becomes one short line. Old records still load by reading the old purpose text when the columns are empty. No data migration of old rows.
2. **A zero total requested is a warning, not a block** (airfare can be company-paid "c/o").
3. **Form first; My Travel Requests and Notifications below it**, as on Reimbursement.
4. Dates are required on submit, and return must not be before departure (server and page). Negative amounts are rejected on save.
5. "Request Date" becomes read-only and shows the saved date (submitted date, else created date); it is no longer editable or sent.
6. "Sign-off Placeholders" is replaced by an **Approval History** list from the audit trail the server already returns (excluding `draft_saved`), keeping the approver signature snapshot.
7. Picking attachment files uploads them immediately (one button), as on Reimbursement/Liquidation.
8. No browser automation by the agent (project rule); the owner checks the page visually.

## Investigation

Line numbers are as of commit `d37a7af`.

**Server (`app.py`)**

- Model `TravelRequest` `:2354`; `purpose = db.Column(db.String(255))`. Additive SQLite migrations in `ensure_travel_request_tables` (`:5476`), dict `travel_request_column_migrations` `:5506-5529` — new columns go here.
- `TRAVEL_REQUEST_EDITABLE_STATUSES = {'Draft', 'Rejected'}` `:40676`. The page's `isTravelEditableStatus` also accepts `returned` (`travel_request.html:1836`) — mismatch.
- `save_travel_request_draft` `:42268`: stores `purpose[:255]`; ignores `payload['date']` and `payload['notes']`; amounts via `normalize_travel_request_line_payload` `:42186` with no negative check; no date validation.
- `submit_travel_request` `:42538`: no date or route validation; conflicts, then signature checks, then approvers.
- `approve_travel_request` `:43416`: no date validation (relies on submit).
- `delete_travel_request_draft` `:42438`: owner or admin only. Recall (`RECALL_REQUEST_REGISTRY` `:74629`) is owner-only (`owner_field: 'user_id'`). The page shows Delete Draft and Withdraw to participants too.
- `get_my_travel_requests` `:42739` → `travel_request_to_dict(item, include_lines=False)` `:41919`, which calls `get_assigned_approver(s)_for_requester` four times and `get_travel_request_participants` / `travel_request_participant_to_dict` repeatedly per row.
- `preview_approved_travel_request_form` `:48663` (gate `can_current_user_view_approved_travel_request_form`: owner/participant, admins, approvers; any status). Not linked from the page.
- Official PDF (`build_travel_request_accounting_pdf_bytes` `:9792`): for training/meeting, customer and activity text fall back to `ctx['purpose']` (around `:10045` and `:10094-10101`), i.e. the cut-off multi-line text. Email context `travel_request_email_context` `:9249` uses the same purpose.
- Audit trail: `include_audit=True` returns `universal_approval_audit_to_dict` entries (`action`, `actor_display_name`, `status_to`, `remarks`, `created_at_label`); every save adds a `draft_saved` entry.
- `approval_remarks` (rejection reason) is in the dict but the page never shows it.
- Local data: 15 travel requests, 12 with `length(purpose) = 255`.

**Approvals (`templates/approvals.html`)**: `extractTravelApprovalField` `:3514` parses the purpose text; callers `:3581-3598` already fall back to `data.training_title`, `data.training_provider`, `data.training_venue`, `data.training_objective`, `data.meeting_subject`, `data.meeting_with`, `data.meeting_objective` — the order only needs flipping.

**Page (`templates/travel_request.html`)**

- CSS `:4-959`: duplicate blocks for `.travel-route-card`, `.travel-route-header`, `.travel-route-title`, `.route-summary.auto-filled`; unused `.travel-form-group-box`, `.travel-route-textarea`.
- Markup order today: hero, status, lock banner, conflict panel, notifications `:993`, My Travel Requests `:1015`, form-title card `:1022` (`SPCAcctgtravelrequest 002-2016`), form sections, attachments `:1216` (Select Files + Upload), Sign-off Placeholders `:1241`, actions, inline delete-draft panel `:1268`.
- Request Date `#travel-date` `:1037` editable, default `new Date().toISOString()` (UTC) `:3815`, never loaded back.
- Purpose composition `collectTravelPayload` `:3177-3273` (route lines duplicated by `route_summary`, plus a notes block).
- Dead or removable script: fallbacks for keys the server never sends in `setTravelParticipantsFromRequest` (`travel_participants`, `lead_requester_name`, `lead_name`, `requester_display_name`, `created_by_name`, `participants_text`) `:1436-1456`; `approver_signature_snapshot` fallback `:2408`; `calculateTravelTotal` rebuild branch `:2439-2441`; ignored fields in `setTravelLineCurrencyValues` and the fallback object `:2369-2377`; the hidden `.visit-product-select` mirror kept in sync with the checkboxes; the hand-listed lock selectors `:1872-1886`; `travel-delete-draft-panel` and its two functions `:3281-3304`; `showTravelStatus(..., 'warning')` with no style.
- My Travel Requests: Timeline button serialises the whole item into `onclick` `:3695`; Withdraw shown to any viewer of a Submitted row `:3707`.
- Existing tests reading the page: `tests/test_travel_request_draft_instructions.py` (needs `special_notes: document.getElementById('travel-special-notes')`, `function hydrateTravelDepositFieldsFromRequest(item)`, `hydrateTravelDepositFieldsFromRequest(item);`), `tests/test_appearance_themes.py` (no hard-coded accent blue), `tests/test_request_recall.py` (`{% include '_request_recall_modal.html' %}`), `tests/test_accounting_attachment_management.py` (`deleteAllTravelRequestAttachments` and `fa-trash`), `tests/test_travel_request_site_visit.py`, `tests/test_travel_request_access.py`. Baseline for the three travel modules: 13 tests, OK.
- Dark mode: `static/css/app-dark-pages.css` already covers `.travel-*` cards, inputs, history, dialog, toast, attachments; new classes need rules there.

**Versions at planning time:** service worker `medical-service-pwa-offline-navigation-v240-liquidation-receipts` (`app.py:27031`); latest release `2026-10-04-liquidation-receipts`. Full-suite baseline from the last plan: 1,506 tests, 23 failures, 3 errors, 5 skips.

## Execution steps

1. **Schema** — `app.py`.
   - Add the seven nullable columns to `TravelRequest` (`String(200)` for title/provider/venue/subject/with, `Text` for the two objectives).
   - Add the matching `ALTER TABLE travel_request ADD COLUMN …` entries to `travel_request_column_migrations`.
   - Done: the app starts on the local DB and adds the seven columns once.

2. **Save and dict** — `save_travel_request_draft`, `travel_request_to_dict`.
   - Save the seven fields from the payload (`clean_str`, trimmed to column length; cleared when the request type does not use them).
   - Reject any line with a negative amount: 400 "Amounts cannot be negative."
   - If both dates are given and return < departure: 400 "Return date cannot be before the departure date." (drafts may still be saved without dates).
   - Dict: expose the seven fields and `request_date` (`submitted_at` else `created_at`, ISO date).
   - Done: a saved training request reloads with all fields intact; negative and reversed-date saves return 400.

3. **Submit validation** — `submit_travel_request`, before the conflict check: departure and return dates required ("Please set the departure and return dates before submitting."), return ≥ departure, at least one route. 400 with the message. Done: such submits are refused; a valid request submits as before.

4. **List speed** — `travel_request_to_dict`: compute assigned approvers once and participants (and their dicts) once per call and reuse them. Output keys unchanged. Done: same JSON for one record before and after.

5. **Approvals** — `templates/approvals.html` `:3581-3598`: read `data.training_*` / `data.meeting_*` first, then `extractTravelApprovalField` for old records. Done: new records show stored fields; old records unchanged.

6. **Page layout and display** — `templates/travel_request.html` markup.
   - Header: title, request number and status pill, subtitle "Shimadzu Philippines Corporation · Form SPCAcctgtravelrequest 002-2016"; actions Preview Form (when saved), Open Timeline and Restore Travel Blocks (approved), New Request. Remove the separate form-title card.
   - Banners: lock banner; rejection banner with `approval_remarks`, rejected by and date when status is Rejected.
   - Request Information: Request Date read-only (`request_date`; today in Manila time, rendered by the server, for a new form), Department, Status, Request No.
   - Sections in order: Purpose Type, Participants, Routes, Travel Period, Cash Advance, Special Instructions, Attachments, Approval History.
   - Approval History: list from `audit_trail` without `draft_saved` (action label, actor, date, remarks), with the approver signature snapshot above it; empty state "Not submitted yet."
   - Bottom dock (pattern of `.liq-dock` in `_liquidation_base.html`): Total Requested, readiness toggle, Delete Draft (owner only), Save Draft, Submit. Hidden when not editable. Page gets bottom padding so the dock does not cover content; full width below 992 px.
   - Readiness panel: blocking — dates missing, return before departure, no route; warning — total is zero. Submit shows the panel instead of submitting when blocking items exist.
   - My Travel Requests below the form: compact rows (request no., status chip, destination, dates, amount) with a status filter (All / Draft / Submitted / Approved / Rejected / Liquidation); Open, Withdraw (owner only, Submitted), Timeline (approved; `onclick` passes id and date only).
   - Notifications below My Travel Requests, behaviour unchanged.
   - Done: page renders; all element ids used by tests remain.

7. **Page behaviour** — `templates/travel_request.html` script.
   - `collectTravelPayload`: send the seven fields; purpose becomes one line — Client Visit: visit purposes joined with "; " (fallback "Client Visit / Service"); Training: "<type>: <title>"; Meeting: "Meeting: <subject>"; trimmed to 255 on a word boundary. Stop sending `date` and `notes`.
   - `hydrateTravelPurposeFieldsFromRequest`: columns first, purpose-text extraction only when the column is empty.
   - `isTravelEditableStatus`: Draft and Rejected only (plus empty for a new form).
   - Owner check from `requester_user_id` vs `{{ current_user.id }}` for Delete Draft and Withdraw.
   - Preview Form opens `/preview_approved_travel_request_form/<id>` in a new tab.
   - Delete Draft uses `travelConfirmDialog`; remove the inline panel and its functions.
   - Attachments: one "Upload Attachments" button opens the picker; `change` uploads (existing checks and loop); remove `#travel-attachment-selection` and Select Files.
   - Lock: disable every `input, select, textarea, button` inside the form sections with one selector (view-only buttons marked `data-always-enabled`), replacing the hand-listed selectors.
   - Add a `warning` style for status and toast.
   - Remove the dead code listed under Investigation (fallback keys, total rebuild branch, hidden product select mirror — read selected equipment from the checked boxes —, duplicate and unused CSS).
   - Keep the strings the existing tests check (see Investigation).
   - Done: script passes `node --check`; no reference to removed ids or functions remains (search `onclick` too).

8. **Dark mode** — `static/css/app-dark-pages.css`: rules for the header pill, rejection banner, dock, readiness panel, approval history items and status chips. Done: every new light-coloured class has a dark rule.

9. **Tests** — new `tests/test_travel_request_page.py` (source-level, plus the test client where the existing travel tests already set one up):
   - Model and migration contain the seven columns; save reads and dict returns them.
   - Save rejects negative amounts and reversed dates.
   - Submit validates dates and routes before the conflict check.
   - `travel_request_to_dict` calls `get_assigned_approvers_for_requester` once.
   - Approvals reads `data.training_title` before `extractTravelApprovalField`.
   - Template: Preview Form link, rejection banner uses `approval_remarks`, Approval History filters `draft_saved`, dock and readiness present; no `travel-delete-draft-panel`, `visit-product-select`, `lead_requester_name`, `travel-attachment-selection`, or `returned` in the editable check.
   - Update release-entry and service-worker assertions.

10. **Release records.**
    - Service worker `medical-service-pwa-offline-navigation-v241-travel-request-page` (`app.py:27031`), keeping historical marker lines.
    - `static/changelog/releases.json` entry `2026-10-05-travel-request-page` (engineers, category Travel Request): clearer page with the form first, Preview Form, rejection reason and approval history, readiness check before submit, training/meeting details no longer cut off, one-step attachment upload.
    - `changes.md`, and this plan's status with any difference between plan and outcome.

11. **Publish** only on the owner's separate "commit and push".

## Deliberately excluded

- **Rewriting old truncated purposes** — the cut text cannot be recovered; old records keep loading as today.
- **A shared base template** — no sibling page shares this structure.
- **Notifications panel redesign** — behaviour kept, only moved below.
- **CSRF exemptions on the JSON routes** — 91 routes app-wide use `@csrf.exempt`; the session cookie is `SameSite=Lax`. Separate app-wide task.
- **Linking to the liquidation from this page** — My Requests already handles it.
- **Changing the PDF layout** — it benefits from the short purpose without code changes.

## Verification

- Step-9 tests; the new checks fail on the current code (no columns, no validation, inline delete panel present).
- Focused modules: `test_travel_request_page`, `test_travel_request_access`, `test_travel_request_draft_instructions`, `test_travel_request_site_visit`, `test_request_recall`, `test_accounting_attachment_management`, `test_appearance_themes`, `test_approval_center_wording`, `test_approval_notifications`, `test_changelog_workflow`, `test_changelog_coverage`; then one full-suite run against 1,506 / 23 F / 3 E / 5 S (plus the new tests).
- The page renders with `render_template` in a request context; the page script passes `node --check`.
- No browser check by the agent. The owner checks desktop and phone, light and dark: new request (Client Visit, Training, Meeting) saves and reloads with all fields; submit blocked without dates; readiness panel; dock; Preview Form; rejected request shows the reason; approval history; one-step upload; a participant does not see Delete Draft/Withdraw; Approvals shows training fields for a new request.

## After implementation

1. Self-review the diff: removed ids/functions not referenced anywhere; test-checked strings still present.
2. Focused modules, then the full suite, quoting counts against the baseline.
3. Service worker bump and `releases.json` entry.
4. `changes.md` and this plan's status.
5. Commit with explicit staging; exclude `scheduler.db`, handoffs, `.claude/`, `output/`, `tmp/`, the loose handoff file and unrelated `changes.md` entries. Commit and push only on the owner's instruction, then verify `origin/main` and Railway.

## Risks

- **Migration on the live database** — additive nullable columns through the existing idempotent pattern; a failure would show at startup in the Railway log.
- **Submit validation stops a user mid-flow** — only for requests with missing or reversed dates or no route, which were invalid anyway; the readiness panel explains it before the server does.
- **Old records reloaded and re-saved** — fields extracted from the old text are saved into the new columns on the next save; text already cut off stays lost.
- **Pages loaded before the deploy** still post `date`/`notes` (ignored) and lack the new fields until refreshed; the service worker bump refreshes them.

---

# Liquidation Pages: One Receipts Section Instead of Per-Row Uploads

**Status:** Executed — commit `092c4e5`; published to `origin/main` on the owner's "commit and push".
**Finished:** 2026-10-04.
**Execution authorized:** 2026-10-04 — the owner said "go ahead partner. do not overengineer and over check things".
**Approved:** 2026-10-04 — the owner said "approved, go with your recommendation" (Approvals option 1: one receipts list under the expense table).
**Detailed:** 2026-10-04.

**Where the plan and the outcome differed:**

- **Tests are source-level** (plus the existing upload-conversion tests, now pointed at the liquidation-level routes); the fail-first run against the old code was not made.
- **The upload button opens the file picker directly** (no pop-up), as on Reimbursement. If one file of several fails, the files already uploaded still show.
- **Approvals** shows "Receipts (N)" under each liquidation table, with "No receipts uploaded." when empty.
- **Verification:** 9 focused modules, 106 tests, OK; both pages render; page scripts pass `node --check`; full suite 1,506 tests, 23 failures, 3 errors, 5 skips (the baseline's non-passing set). No browser check was made.

## Context

After the shared liquidation page (`9faedf0`), the owner asked to change receipt uploads on both liquidation pages (Travel and Cash Advance) to work like the Reimbursement page: one upload section for the whole liquidation, with no uploads per expense row. Intended outcome: the engineer uploads all receipts in one place; the approver sees the same single list; the receipt compilation PDF and the approval package keep working; no data is moved and no schema changes.

## Decisions taken

1. **One "Uploaded Receipts" section** below the expense table on both pages (Upload Receipts with several files at once, Delete All Receipts, a list with view and delete per file). The per-row Receipt button, the table's Receipts column and the per-row receipt pop-up go.
2. **New uploads are not linked to a row** (`row_id` NULL). Receipts already attached to a row stay attached, show in the same single list, and are still removed when their row is deleted. No data migration.
3. **Approvals (option 1):** the two Approvals liquidation tables drop their per-row Receipts column and show one "Receipts" list of every receipt under the table, beside the existing Receipt Compilation PDF.
4. **Readiness:** "N rows have no receipt" becomes "No receipts uploaded yet" — a warning, not a block (the server does not require receipts).
5. **The per-row upload routes are replaced** by liquidation-level routes; the functions keep their names so existing callers and tests stay recognisable.
6. **No browser automation by the agent** (project rule); the owner checks the pages visually.

## Investigation

Line numbers are as of commit `a54246c`.

- **Schema already allows it.** `TravelLiquidationReceipt.row_id` (`app.py:2663`) and `CashAdvanceLiquidationReceipt.row_id` (`app.py:64803`) are `nullable=True`; the local tables `travel_liquidation_receipt` and `cash_advance_liquidation_receipt` have `row_id INTEGER` with no NOT NULL. Both tables are empty locally.
- **Downstream already handles receipts without a row:**
  - Compilation PDFs: `travel_liquidation_receipt_records_grouped_for_package` / `cash_advance_liquidation_receipt_records_grouped_for_package` return row-grouped and "orphan" receipts; `build_travel_liquidation_receipt_compilation_pdf_bytes` (`app.py:48334`) and `build_cash_advance_liquidation_receipt_compilation_pdf_bytes` (`app.py:70299`) append orphans after the rows under the divider "ADDITIONAL LIQUIDATION RECEIPTS" (`:48410`).
  - Approval package manifests (`build_travel_liquidation_approval_package_manifest` `app.py:48476`, `build_cash_advance_liquidation_approval_package_manifest` `app.py:69059`) query receipts by `liquidation_id`, so the count and list include them. Accounting packages use the compilation PDF.
  - Delete Receipt (`/delete_*_liquidation_receipt/<receipt_id>`) and Delete All Receipts (`/delete_all_*_liquidation_receipts/<liquidation_id>`) work by receipt or liquidation, not by row.
- **Row-based places that miss them:**
  - `travel_liquidation_to_dict` / `cash_advance_liquidation_to_dict` expose receipts only inside `rows[].receipts` (`travel_liquidation_row_to_dict` `app.py:46521`, `cash_advance_liquidation_row_to_dict` `app.py:67576`).
  - `templates/approvals.html` `renderLiquidationRows` (`:3994-4009`) renders `row.receipts` in a Receipts column; it is used by the Travel detail (`renderLiquidationApprovalDetail`, table `:4462-4476`, header `:4471`) and the Cash Advance detail (`renderCashAdvanceLiquidationApprovalDetail`, table `:4946-4960`, header `:4955`). The Reimbursement table at `:5779` / `:5824` is a different renderer and is not touched.
  - The Travel form payload (`build_travel_liquidation_form_payload`, receipts per row at `:46758`) carries row receipt counts; the Excel template does not print receipts, so it is left as is.
- **Upload routes today:** `upload_travel_liquidation_receipt(row_id)` (`app.py:49347`, route `/upload_travel_liquidation_receipt/<int:row_id>`) and `upload_cash_advance_liquidation_receipt(row_id)` (`app.py:68146`); both look up the row, check `can_edit_*`, validate, compress through `reimbursement_prepare_receipt_upload_bytes`, write storage, create the receipt with `row_id=row.id`, audit, and roll back the stored file on failure. `travel_liquidation_secure_receipt_filename(file_obj, row_id)` / `cash_advance_liquidation_secure_receipt_filename` use the id only inside the stored filename.
- **Page:** `templates/_liquidation_base.html` has the Receipts column, `openReceiptModal`, `uploadReceipts`, `#receiptModal`, the row "Receipt" button, the "No receipt" chip and the per-row readiness warning; `deleteReceipt` and `deleteAllLiquidationReceipts` stay.
- **Tests touching this:** `tests/test_shared_pdf_upload_conversion.py:297-353` calls `upload_travel_liquidation_receipt` / `upload_cash_advance_liquidation_receipt` with a row and patches `db.session.get`; `tests/test_liquidation_pages.py` (`'No receipt'`, `'multiple'`, and `def upload_travel_liquidation_receipt` as a slice boundary); `tests/test_reimbursement_liquidation_row_deletion.py:48-53` (slice boundaries `def upload_*_liquidation_receipt`).
- **Versions at planning time:** service worker `medical-service-pwa-offline-navigation-v239-liquidation-pages`; latest release `2026-10-04-liquidation-pages`. Full-suite baseline: 1,505 tests, 23 failures, 3 errors, 5 skips.

## Execution steps

1. **Server upload routes** — `app.py`.
   - `upload_travel_liquidation_receipt`: route becomes `/upload_travel_liquidation_receipts/<int:liquidation_id>`; load with `get_travel_liquidation_for_requester_page(liquidation_id=…)` (404 if none), keep `can_edit_travel_liquidation`, validation, compression, storage and rollback; create the receipt with `row_id=None`; pass `liquidation.id` to the secure-filename helper; drop `row` from the response and the audit metadata.
   - Same for `upload_cash_advance_liquidation_receipt` → `/upload_cash_advance_liquidation_receipts/<int:liquidation_id>` with `cash_advance_liquidation_get_for_requester_page`.
   - Done: a POST with one file to the new route stores a receipt with no row and returns the updated liquidation; the old `/upload_*_liquidation_receipt/<row_id>` routes are gone.

2. **All receipts in the liquidation data** — `travel_liquidation_to_dict`, `cash_advance_liquidation_to_dict`.
   - Add `all_receipts`: every receipt of the liquidation (row-linked and not), newest first, through the existing `*_receipt_to_dict`.
   - Done: both payloads carry `all_receipts`; `rows[].receipts` unchanged.

3. **Compilation wording** — the two compilation builders: the divider for receipts without a row reads "LIQUIDATION RECEIPTS" (they are now the normal case); the approval manifest descriptions that say receipts are "attached to liquidation expense rows" / "grouped by expense row" say "uploaded for this liquidation". Done: no other compilation behaviour changes.

4. **Liquidation page** — `templates/_liquidation_base.html`.
   - Remove the table's Receipts column (header and cell), the row Receipt button, `#receiptModal`, `openReceiptModal`, the "No receipt" chip and its CSS.
   - Add a "Uploaded Receipts" panel below the expense table: hidden file input (`multiple`, `.pdf,.png,.jpg,.jpeg`), Upload Receipts button (disabled when not editable), Delete All Receipts (moved here from the table header), and a list rendered from `all_receipts` (file name link to `preview_url`, upload date, delete button when editable); empty state "No receipts uploaded yet."
   - `uploadReceipts(files)`: same checks as today, posts each file to `upload_*_receipts/<liquidation id>` one after another, one summary toast.
   - Readiness: replace the per-row warning with "No receipts uploaded yet" when `all_receipts` is empty; the submit confirm mentions it in the same case.
   - Done: no per-row upload control remains; uploads, deletes and Delete All work from the panel on both pages.

5. **Approvals** — `templates/approvals.html`.
   - `renderLiquidationRows`: drop the Receipts cell (`colspan` 7 → 6); remove the `<th>Receipts</th>` at `:4471` and `:4955`.
   - Under each of the two tables, render `Receipts (N)` with `renderApprovalReceiptLinks(data.all_receipts || [])` (falls back to "No receipts uploaded").
   - Done: both liquidation approval details list every receipt once; the Reimbursement table is unchanged.

6. **Tests.**
   - `tests/test_shared_pdf_upload_conversion.py`: pass a liquidation instead of a row and patch `get_travel_liquidation_for_requester_page` / `cash_advance_liquidation_get_for_requester_page` to return it; the 400/500 and rollback assertions stay.
   - `tests/test_liquidation_pages.py`: replace the `'No receipt'` check with the panel (`Uploaded Receipts`, `all_receipts`, `upload_*_receipts`) and assert no `openReceiptModal`, `receiptModal`, `'/upload_travel_liquidation_receipt/'` remain; add source checks that both new routes create receipts with `row_id=None`, both dicts return `all_receipts`, and `approvals.html` renders `data.all_receipts`.
   - Slice boundaries that name `def upload_*_liquidation_receipt` keep working (names unchanged).
   - Update the release-entry and service-worker assertions.

7. **Release records.**
   - Service worker `medical-service-pwa-offline-navigation-v240-liquidation-receipts`.
   - `static/changelog/releases.json` entry `2026-10-04-liquidation-receipts` (engineers, category Liquidation): receipts are uploaded in one section for the whole liquidation, like Reimbursement; approvers see one list.
   - `changes.md`, and this plan's status with any difference between plan and outcome.

8. **Publish** only on the owner's separate "commit and push".

## Deliberately excluded

- **Moving existing row-linked receipts** to the liquidation level — they already show in the single list and in the compilation; moving them changes nothing for users.
- **Linking a receipt to a row afterwards** — the owner asked for one section without per-row uploads.
- **Excel form payload receipt counts per row** — the template does not print receipts.
- **Duplicate-receipt detection** (Reimbursement has it) — needs a schema change; separate task.

## Verification

- Step-6 tests; the new source checks fail on the current code (no `all_receipts`, per-row route present).
- Focused modules: `test_liquidation_pages`, `test_shared_pdf_upload_conversion`, `test_accounting_attachment_management`, `test_accounting_branch_codes`, `test_reimbursement_liquidation_row_deletion`, `test_approval_center_wording`, `test_approval_notifications`, `test_changelog_workflow`, `test_changelog_coverage`; then one full-suite run against 1,505 / 23 F / 3 E / 5 S.
- Both pages render with `render_template`; page scripts pass `node --check`.
- No browser check by the agent. The owner checks on both pages, desktop and phone, light and dark: upload several receipts from the panel, view and delete one, Delete All, readiness warning with no receipts, rows show no receipt controls; in Approvals, the Travel and Cash Advance liquidation details show one receipts list and the compilation PDF includes the uploads.

## After implementation

1. Self-review: no reference to the removed route, modal or functions remains (including `onclick`); `deleteAllLiquidationReceipts` still exists (attachment test).
2. Focused modules, then the full suite, quoting counts against the baseline.
3. Service worker bump and `releases.json` entry.
4. `changes.md` and this plan's status.
5. Commit with explicit staging; exclude `scheduler.db`, handoffs, `.claude/`, `output/`, `tmp/`, the loose handoff file and unrelated `changes.md` entries. Commit and push only on the owner's instruction, then verify `origin/main` and Railway.

## Risks

- **An approver relied on seeing which row a receipt belongs to.** Old row-linked receipts keep their link in the compilation PDF; new ones are listed once. This is the owner's chosen trade-off.
- **Bookmarked or cached clients still post to the old per-row route** — a page loaded before the deploy gets 404 on upload; the service worker bump refreshes the page.
- **Deleting a row no longer removes the receipts uploaded for it** (they are not linked). The engineer deletes them from the panel; Delete All is there.

---

# Liquidation Pages (Travel and Cash Advance): Shared Base Template, Reimbursement Parity, Bug Fixes, and Less Code

**Status:** Executed — commit `9faedf0`; published to `origin/main` on the owner's "commit and push".
**Finished:** 2026-10-04.
**Execution authorized:** 2026-10-04 — the owner said "go ahead partner. do not overengineer and over check things".
**Approved:** 2026-10-04 — the owner said "approved, go with your recommendations" after reviewing the proposal and the shared-template explanation.
**Detailed:** 2026-10-04.

**Where the plan and the outcome differed:**

- **Tests are source-level**, per the owner's "do not over check": `tests/test_liquidation_pages.py` (10 tests) checks the server changes in the source plus the parser directly (zero amounts), and the templates as strings. No test-client tests for auto-row delete, approver notification or Cash Advance clear; the fail-first run against the old code was not made. Both pages were rendered with `render_template` in a request context, and both page scripts pass `node --check`.
- **Clear Form on Travel** deletes every row and receipt, then calls the existing seed to re-add Per Diem/Airfare at the approved amounts (simpler than resetting rows in place; same result).
- **Zero-amount errors** use the routes' existing `ValueError` mapping (409), not a new 400.
- **28 alias routes removed**, not 29: `/get_my_cash_advance_liquidation` is listed in an `app.py` path-prefix list (`app.py:280`) and stays.
- **Dark mode:** the new page uses theme tokens and translucent status tints, so `static/css/app-dark-pages.css` needed only removals (old `liq-` / `ca-liq-` / `trip-context` / `reference-card` / lock-banner / `return-reason-box` selectors), no new rules.
- **Preview Form is a plain link** (the exchange rate already saves when changed).
- **Line counts:** templates 1,629 → 727 (base 594, Travel 111, Cash Advance 22).
- **Verification:** 9 liquidation-related modules, 73 tests, OK; full suite 1,505 tests, 23 failures, 3 errors, 5 skips (the baseline's non-passing set, all unrelated). No browser check was made.

## Context

The owner asked for a deep review of both liquidation pages — Travel Liquidation (`/travel_liquidation`, `templates/travel_liquidation.html`) and Cash Advance Liquidation (`/cash_advance_liquidation`, `templates/cash_advance_liquidation.html`) — to align them with the system, bring over every Reimbursement function that applies (liquidation is a form of reimbursement), improve the design, and remove code.

The review found eleven bugs (among them deleted Per Diem/Airfare rows reappearing, a Travel preview that is disabled after submit, Travel submit notifying the wrong approver scope, and approver emails returned to the requester's browser), several Reimbursement functions missing (readiness checklist, saved-signature check, Download Form, styled messages, multi-receipt upload, bottom action bar, phone layout, accent/dark mode), and two templates that are about 80% the same code under different prefixes.

Intended outcome: both pages share one base template so fixes and design land once; each page keeps only what is genuinely different; behaviour matches Reimbursement where it applies; the bugs are fixed; about 700 template lines and about 24 unused server alias routes are removed.

## Decisions taken

1. **Shared base template with two thin page templates** (Jinja inheritance), not one template full of `{% if %}`. `templates/_liquidation_base.html` holds layout, CSS, table, pop-ups and shared script. `templates/travel_liquidation.html` and `templates/cash_advance_liquidation.html` `{% extends %}` it and fill blocks. Page routes, URLs and template file names stay the same.
2. **Small differences come from one settings object** (`window.LIQ`) set by each page; **page-specific rules use optional hooks** (`extraRowPayload`, `extraReadinessChecks`, `rowBadge`, `afterRender`). The shared script never checks which page it is on.
3. **Per Diem / Airfare auto rows can be edited but not deleted.** They show an "Auto" badge and no Delete button; the server refuses to delete them.
4. **Submit is blocked without a saved signature**, as on Reimbursement (check through `/get_my_signature`, with a link to Settings).
5. **Rows missing a receipt are a warning, not a block** (the server does not require receipts today).
6. **One "Clear Form" on both pages.** Travel keeps its route; Cash Advance gets a matching route. On Travel, Clear Form removes manual rows and all receipts and resets auto rows to their approved amounts.
7. **Save Draft buttons are removed** on both pages; every action already saves. A status line says "All changes saved."
8. **After submit the user stays on the page** (locked banner + one toast) on both pages.
9. **No browser automation by the agent** (project rule). Verification uses the Flask test client, source checks and `node --check`; the owner checks the pages visually.

## Investigation

Line numbers are as of commit `48d1b2e`.

**Templates.** `templates/travel_liquidation.html` is 1,104 lines (CSS `:3-59`, markup `:61-379`, script `:381-1102`). `templates/cash_advance_liquidation.html` is 525 lines (CSS `:3-48`, markup `:50-206`, script `:208-523`). Both render the same structure: hero with actions, alert, lock banner, four KPI cards, summary card, expense table (9 columns), and the pop-ups `rowModal`, `receiptModal`, `deleteReceiptModal`, `submitLiquidationModal`, `deleteModal` (Travel also `clearDraftModal`). Their scripts duplicate `esc`, `getCSRFToken`, `showLiqAlert`, `setButtonBusy`, `rowById`, `isDraftLiquidation`, `getStatusMeta`, `updateWorkflowButtons`, row/receipt/submit handlers and `deleteAllLiquidationReceipts`.

**What differs between the pages (verified):**

- Endpoints run in parallel: `/get_|add_|save_|delete_{travel|cash_advance}_liquidation_row…`, `/upload_…_receipt`, `/delete_…_receipt`, `/delete_all_…_receipts`, `/submit_…`, `/preview_…_excel`, `/download_…_excel`. The JSON shape is the same (`travel_liquidation_to_dict` `app.py:46559`, `cash_advance_liquidation_to_dict` `app.py:67616`; rows `:46521` / `:67576`; receipts `:46443` / `:67549`, both with `preview_url` and `download_url`).
- Travel only: currency (`currency_code`, `usd_to_php_rate`, row `source_currency_code` / `source_amount`), the rate panel (`:105-117`) and `/save_travel_liquidation_currency_rate`; the approved reference by bucket with excluded notes (`build_travel_liquidation_reference_summary`); the trip details (period, purpose, destination); auto rows; expense types Transportation, Hotel / Accommodation, Meals, Per Diem / Travel Allowance, Plane Fare / Air Tickets, Supplies, Others; default codes CC04 / DC03 / PC18/PC22 (`app.py:46078-46080`); Clear Form.
- Cash Advance only: reference = approved amount, request/needed date, liquidation days, purpose, payment method/reference (`cash_advance_liquidation_reference_summary`, `app.py:67597`); expense types Transportation, Meals, Supplies, Representation, Others; default codes CC04 / DC03 / PC26 (hard-coded in the template `:166-168`, `:358-360`).

**Bugs (verified):**

- **B1 Deleted auto rows come back.** `get_travel_liquidation_for_requester_page` (`app.py:47276-47294`) calls `travel_liquidation_seed_per_diem_airfare_rows` (`:46158`) on every load, and `/get_travel_liquidation` (`:47571`) commits. The seed adds any approved Per Diem/Airfare line with no row pointing to it (`:46202-46209`), so a row deleted through `/delete_travel_liquidation_row` (`:49251`, no auto-row guard) or `/clear_travel_liquidation` (`:40151`) is re-created on the next load. The Clear Form pop-up says it "removes all actual expense entries".
- **B2 Travel Preview disabled after submit.** `updateWorkflowButtons` disables `previewTemplateTopBtn` when not a draft (`travel_liquidation.html:492`). Cash Advance's preview is a link and stays usable.
- **B3 Travel submit notifies the wrong scope.** `submit_travel_liquidation` notifies `get_assigned_approvers_for_requester(liquidation.user_id, 'travel_request')` with a hard-coded legacy manager fallback (`app.py:40378-40384`). Permission (`can_user_approve_travel_liquidation`, `:11255`) and the queue (`:11274`) accept both `travel_request` and `travel_liquidation` routes, so an approver routed only for Travel Liquidation can approve but is never notified. Cash Advance uses `cash_advance_liquidation_submit_notification_approvers` (`:70724`: liquidation scope, parent scope, `all`, original approver, then the fallback).
- **B4 Travel submit hides the branch reason.** `require_accounting_branch_code` raises `ValueError`; `submit_travel_liquidation` has only a generic `except Exception` (`:40452`) that returns 500 "Unable to submit liquidation for approval." Cash Advance returns 409 with the message (`:68522`).
- **B5 Approver emails sent to the requester.** `submit_cash_advance_liquidation` returns `approval_notification.email_recipients` (`app.py:68519`).
- **B6 Zero or empty amounts accepted.** `travel_liquidation_parse_row_payload` (`:48917`, also used by `cash_advance_liquidation_parse_row_payload` `:67542`) has no amount check.
- **B7 Save Draft does nothing useful.** Cash Advance `saveDraftNotice` only shows a notice (`:229`); Travel `saveDraftTop` (`:980`) re-saves the rate and reloads.
- **B8 Messages.** `showLiqAlert` hides every message, including errors, after 4.5 s (Travel `:437-444`, CA `:221`). Delete All Receipts uses `window.confirm` (Travel `:934`, CA `:487`). Travel redirects to the Accounting Center 650 ms after submit (`:1075-1077`); Cash Advance stays.
- **B9 Internal text shown to users.** Eyebrows "S13C Travel Liquidation" (Travel `:65`) and "F4A5 Standalone Cash Advance Liquidation" (CA `:54`); "Standalone Cash Advance liquidation. This record is separate from Travel Request liquidation." (CA `:93`).
- **B10 Dark mode and accent.** Fixed green hero gradient (`#064e3b,#0f766e`; Travel `:5`, CA `:5`) while Reimbursement uses `--app-primary-strong` / `--app-primary`. `static/css/app-dark-pages.css:779-801` covers only KPI, reference, trip cards, values and labels; status pills, receipt pills, receipt delete buttons, the returned banner, `.return-reason-box`, the table header (`#f8fafc`) and `card-header bg-white` have no dark rules.
- **B11 Inconsistent labels and links.** Completed status is "Liquidated" on Travel (`:471`) and "Completed" on Cash Advance (`:226`). Travel's Back goes to `/accounting_center` (`:78`); the Accounting Center module for Travel liquidations is `liquidations` (`app.py:45566`), handled by `applyAccountingUrlParams` (`accounting_center.html:1303`). Cash Advance's Back (`/accounting_center?module=cash_advances&status=paid`) is correct and stays.

**Reimbursement functions compared:** readiness checklist, saved-signature check (`reimbursement.html:8060-8130`, `/get_my_signature` `app.py:7224`), Download Form, page toast and confirm dialog (`reimToast` `:4693`, `reimConfirmDialog` `:4793`; every page has its own pair, there is no global helper), multi-file receipt upload, bottom dock with Save/Submit (`:3600-3617`), phone layout, accent header. Not applicable or excluded: date-range loading, overlap notice, worksheet zoom and focus view, bulk row selection, notifications and history panels, LPR attachment (`EMBEDDED_LPR_PARENT_MODULES = {'cash_advance', 'travel_request', 'reimbursement'}`, `app.py:72032`), recall (liquidations deliberately excluded, `tests/test_request_recall.py:32-33`, `changes.md` recall entry).

**Dead or removable code (verified by search across `templates/`, `static/`, `tests/` and `app.py`):**

- Travel template: `#heroTripContext` and `.trip-context` (always emptied, `:33`, `:68`, `:615`); `buildTripContext` (`:544-581`) — the dict sends only `purpose`, `request_type`, `destination`, `departure_date`, `return_date`, `requester_name`, so the participant/client/route fallbacks never match; `namesFromParticipants`, `compactNames` (`:529-543`); fallbacks `rejection_reason`, `returned_reason`, `remarks` in `getLiquidationReturnReason` (`:474-482`, not in the dict); client conversion `directRateForSource`, `officialAmountFromSource` and the computed `exchange_rate` / `actual_amount` in `collectRowPayload` (`:405-416`, `:790-810`; the server recomputes in `travel_liquidation_parse_row_payload`); calls to `saveCurrencyRateIfNeeded` before each row save, preview and submit (`:844`, `:1027`, `:1069`; the rate already saves on change, `:1088-1100`); `.form-control-sm` (unused).
- Cash Advance template: `.balance-card`, `.balance-label`, `.balance-amount` (`:35-39`), `.form-control-sm`, `.ca-liq-action-note` once the hero is rebuilt.
- Both: Save Draft buttons and functions.
- `app.py`: `build_travel_liquidation_reference_summary` is called twice per dict (`:46612-46613`).
- `app.py` alias routes with no caller (only the decorator line matches): `/clear_travel_liquidation_draft`, `/submit_travel_liquidation_for_approval`, `/get_my_travel_liquidation`, `/get_travel_liquidation_document_payload`, `/update_travel_liquidation_row`, `/create_travel_liquidation_row`, `/update_travel_liquidation_currency_rate`, `/remove_travel_liquidation_row`, `/attach_travel_liquidation_receipt`, `/remove_travel_liquidation_receipt`, `/open_travel_liquidation_receipt_compilation`, `/open_travel_liquidation_receipt`, `/get_travel_liquidation_package_manifest`, `/open_travel_liquidation_rfp`, `/inline_travel_liquidation_rfp`, `/get_my_cash_advance_liquidation`, `/create_cash_advance_liquidation_row`, `/update_cash_advance_liquidation_row`, `/remove_cash_advance_liquidation_row`, `/attach_cash_advance_liquidation_receipt`, `/remove_cash_advance_liquidation_receipt`, `/open_cash_advance_liquidation_receipt`, `/submit_cash_advance_liquidation_for_approval`, `/get_cash_advance_liquidation_package_manifest`, `/open_cash_advance_liquidation_rfp`, `/inline_cash_advance_liquidation_rfp`, `/open_cash_advance_liquidation_excel`, `/get_cash_advance_liquidation_by_cash_advance`, `/open_cash_advance_liquidation_draft`. Keep every route `templates/approvals.html` or `accounting_center.html` uses (`get_travel_liquidation_form_payload`, `open_travel_liquidation_excel`, `download_travel_liquidation_excel`, `preview_travel_liquidation_receipt_compilation`, `preview_/download_travel_liquidation_rfp`, `preview_cash_advance_liquidation_rfp`, `download_cash_advance_liquidation_excel` (used in `app.py`), `create_cash_advance_liquidation_draft`, the complete routes). Re-check each name with a search immediately before removing it.

**Checked and found sound:** receipt filenames go through `secure_filename` (`app.py:49020`, `:67519`), so the inline `onclick` filename strings are fragile but not exploitable (they move to `data-` attributes anyway); ownership checks on every row/receipt/submit route; server receipt validation and 2 MB optimisation.

**Tests that read these pages:** `tests/test_accounting_branch_codes.py:66-102` (`readonly aria-readonly="true"`, `Derived Branch`, `currentLiquidation?.derived_branch_code` in each template), `tests/test_accounting_attachment_management.py:44-45` (`deleteAllLiquidationReceipts` in each template), `tests/test_reimbursement_liquidation_row_deletion.py:17-20`, `tests/test_request_recall.py`, `tests/test_shared_pdf_upload_conversion.py`; also `tests/test_approval_notifications.py`, `tests/test_approval_center_wording.py`, `tests/test_email_template_settings.py`. Baseline for the first five: **42 tests, OK**. Full-suite baseline from the last plan: 1,495 tests, 23 failures, 3 errors, 5 skips.

**Versions at planning time:** service worker `medical-service-pwa-offline-navigation-v238-reimbursement-cleanup` (`app.py:27031`); latest release `2026-10-04-reimbursement-cleanup`.

## Execution steps

1. **Fail-first tests** — new `tests/test_liquidation_pages.py` (reuse the app/test-client setup used by `tests/test_accounting_branch_codes.py`).
   - Test client: deleting a Travel auto row (one with `travel_request_line_id`) returns 409 and the row remains; a manual row still deletes; after Clear Form and a reload, auto rows exist at their approved amounts and manual rows and receipts are gone.
   - Test client: Travel submit notifies an approver routed only for `travel_liquidation` (system notification row created).
   - Test client: Travel submit with an unresolved branch returns 409 with the branch message.
   - Test client: Cash Advance submit response has no `email_recipients`.
   - Test client: adding a row with amount 0 or empty returns 400 on both pages.
   - Test client: `/clear_cash_advance_liquidation/<id>` clears rows and receipts on a draft and is refused (403) once submitted.
   - Test client: each removed alias returns 404/405.
   - Source/render: both pages render through `_liquidation_base.html`; no `saveDraftTop`, `saveDraftNotice`, `window.confirm`, `S13C`, `F4A5`, `buildTripContext`; Travel preview is not in the locked-disable list.
   - Run against the current code and record which fail. Done: the behavioural tests fail for the right reason.

2. **Server fixes (B1, B3–B6)** — `app.py`.
   - `delete_travel_liquidation_row`: if `row.travel_request_line_id` is set, return 409 "Per Diem and Airfare rows come from the approved Travel Request. Edit the amount instead of deleting the row."
   - `clear_travel_liquidation`: delete only rows without `travel_request_line_id` plus all receipts; reset auto rows to `actual_amount = planned_amount` (and `source_amount` from the request line); message "Form cleared. Per Diem and Airfare were reset to the approved amounts."
   - New helper `travel_liquidation_submit_notification_approvers(liquidation)` mirroring `cash_advance_liquidation_submit_notification_approvers`: scopes `travel_liquidation`, `travel_request`, `all`, excluding the submitter, then the existing legacy fallback; use it in `submit_travel_liquidation`.
   - `submit_travel_liquidation`: add `except ValueError` → rollback, 409 with the message.
   - `submit_cash_advance_liquidation`: drop `email_recipients` from the response (keep counts).
   - `travel_liquidation_parse_row_payload`: raise `ValueError('Please enter an amount greater than zero.')` when `source_amount <= 0`; check that add/save routes for both kinds map `ValueError` to 400 (add the mapping where missing).
   - Done: the step-1 tests for these pass.

3. **Cash Advance Clear Form route** — `app.py`, beside `delete_all_cash_advance_liquidation_receipts`.
   - `/clear_cash_advance_liquidation/<int:liquidation_id>` (POST, same decorators and access checks as the other CA routes): delete all rows and receipts (stored files through `managed_storage_delete` with the CA prefix, after commit, warnings like the delete-row route), recalculate totals, keep status, write `record_universal_approval_audit('cash_advance', …, 'liquidation_cleared', …)` and one `ActivityLog`.
   - Done: step-1 CA clear test passes.

4. **Server cleanup** — `app.py`.
   - Remove the alias decorators listed under Investigation (decorator lines only; functions stay under their primary route).
   - `travel_liquidation_to_dict`: build the reference summary once and reuse it for `approved_request_reference` and `reference_total`.
   - Add constants `LIQUIDATION_PAGE_SETTINGS = {'travel': {...}, 'cash_advance': {...}}` with `api` prefix, title, expense types, default codes (reuse `TRAVEL_LIQUIDATION_DEFAULT_*`; add `CASH_ADVANCE_LIQUIDATION_DEFAULT_PRODUCT_CODE = 'PC26'`), back URL (`/accounting_center?module=liquidations` and `/accounting_center?module=cash_advances&status=paid`), completed label "Completed".
   - `travel_liquidation_page` / `cash_advance_liquidation_page`: pass `liq_settings=LIQUIDATION_PAGE_SETTINGS[kind]`; drop the `os.path.exists` template checks (the templates are part of the repo).
   - Done: the alias tests pass; both pages render.

5. **Shared base template** — new `templates/_liquidation_base.html`.
   - Markup: compact accent hero (eyebrow = page title, `h1` = liquidation number, subtitle = parent number · requester, status pill; actions Preview Form, Download Form, Back); toast container; lock/returned banner (reason, returned by, at); summary strip (Cash Advance · Actual · Balance with "Return to Shimadzu" / "Due to you" / "Fully liquidated"); Details card (`{% block details %}`); approved amounts (`{% block reference %}`, inside a `<details>`); `{% block before_table %}`; expense card with Delete All Receipts and Add Expense Row; table Date · Particulars (type below; badge from `rowBadge`) · Codes (Class·Dept·Product) · Amount · Receipts (amber "No receipt" chip when none) · Actions; bottom dock with Balance, readiness toggle and panel, "All changes saved" status, Clear Form, Submit; signature-required panel (Open Settings / I added my signature — continue); pop-ups row, receipt (file input `multiple`), and one confirm dialog used for delete row, delete receipt, delete all receipts, Clear Form and submit. Row form keeps `readonly aria-readonly="true"` on Branch and the "Derived Branch" label; `{% block row_fields %}` after Amount.
   - CSS: one set of `liq-` classes; colours from theme tokens (`--app-primary`, `--app-primary-strong`, `--app-surface`, `--app-border`, `--app-text`, `--app-muted`); hero gradient as in `.reim-hero`; at ≤768 px table rows stack as cards (`td::before` labels via `data-label`), dock stays fixed, controls ≥44 px.
   - Script: `const LIQ = Object.assign({}, window.LIQ_SETTINGS);` read from `{{ liq_settings|tojson }}` plus page values; shared helpers (`esc`, `money(value, currency)`, `liqApi(path)` building `/${verb}_${LIQ.api}_…`), `liqToast(message, tone)` (errors stay until closed, success auto-hides), `liqConfirm({title, message, confirmLabel, tone})` returning a promise, `loadLiquidation`, `renderLiquidation` (calls `afterRender` hook), row/receipt/delete/clear/submit handlers using `data-` attributes instead of inline strings, `uploadReceipts` (files one after another, one summary toast), `downloadLiquidationForm` (fetch `/download_${api}_excel/<id>`, blob save with `Content-Disposition` filename, server error shown on failure), readiness (`blocking`: no rows, branch unresolved, signature missing, plus `extraReadinessChecks()`; `warning`: rows without receipts), signature check before submit via `/get_my_signature` (same flow as Reimbursement), `updateWorkflowButtons` (Preview and Download always enabled; edit controls only for Draft/Returned/Rejected with a branch). Hooks default to no-ops: `extraRowPayload`, `extraReadinessChecks`, `rowBadge`, `afterRender`, `fillRowForm`.
   - Keep the function name `deleteAllLiquidationReceipts` and the string `currentLiquidation?.derived_branch_code` (existing tests).
   - Done: template compiles; extracted script passes `node --check`.

6. **Travel page** — rewrite `templates/travel_liquidation.html` to `{% extends "_liquidation_base.html" %}`.
   - `details`: Liquidation No., Travel Request, Period (`formatTravelPeriodLabel`), Purpose (`cleanPurposeLabel` of `purpose`/`request_type`), Destination, Derived Branch.
   - `reference`: approved buckets and excluded notes (existing `renderReferenceSummary` logic).
   - `before_table`: USD to PHP rate panel (shown when `currency_code` is USD), saved on change only.
   - `row_fields`: Currency select and the receipt-amount label/help.
   - `page_script`: `extraRowPayload` (source currency and source amount), `fillRowForm` (currency, source amount), `extraReadinessChecks` (USD rate needed when PHP rows exist), `rowBadge` ("Auto" for `travel_request_line_id`, and hide Delete), `afterRender` (rate panel, receipt-currency note).
   - Done: no dead code listed under Investigation remains; the page renders through the test client.

7. **Cash Advance page** — rewrite `templates/cash_advance_liquidation.html` to `{% extends "_liquidation_base.html" %}`.
   - `details`: Liquidation No., Cash Advance, Request / Needed date, Liquidation period, Purpose, Payment reference, Derived Branch.
   - `reference`: approved Cash Advance amount.
   - No other blocks.
   - Done: renders through the test client; all actions call the `cash_advance_liquidation` endpoints.

8. **Dark mode** — `static/css/app-dark-pages.css`.
   - Replace the `.liq-kpi, .ca-liq-kpi, .trip-context-card, .reference-card` / `.liq-value, .ca-liq-value…` / `.liq-label, .ca-liq-label` entries (`:779-801`) with the new base classes, and add rules for status pills, receipt chips, "No receipt" and "Auto" chips, the returned banner and reason box, table header and row cards, dock, readiness panel and confirm dialog.
   - Done: no `ca-liq-` or `trip-context` selector remains; every new light-coloured class has a dark rule.

9. **Update existing tests** that name the templates: `tests/test_accounting_branch_codes.py` (assertions now satisfied by the base template — read base + page), `tests/test_accounting_attachment_management.py` (same), `tests/test_reimbursement_liquidation_row_deletion.py` (point at the base template where the delete-row code now lives). Do not weaken what they check.

10. **Release records.**
    - Service worker `medical-service-pwa-offline-navigation-v239-liquidation-pages` (`app.py:27031`), keeping historical marker lines; update the exact version assertions.
    - `static/changelog/releases.json` entry `2026-10-04-liquidation-pages` (or the execution date): one shared design for Travel and Cash Advance liquidation, readiness and signature check before submit, Download Form, several receipts at once, Per Diem/Airfare can no longer be deleted by mistake, clearer messages, phone layout and dark mode.
    - `changes.md`, and this plan's status with any difference between plan and outcome.

11. **Publish** only on the owner's separate "commit and push".

## Deliberately excluded

- **Recall for liquidations** — excluded earlier by the owner because liquidation status is tied to the parent accounting workflow.
- **LPR attachment** — the parent Travel Request / Cash Advance carries the LPR.
- **Bulk row selection, worksheet zoom, focus view, notifications and history panels** — liquidations have few rows; the Accounting Center and the notification bell cover status.
- **Duplicate-receipt detection** — needs a schema change; a separate task.
- **Concurrent editing by Travel participants** and **CSRF exemptions** — app-wide patterns.
- **RFP preview for the requester** — an Accounting document.
- **Per-category approved-vs-actual comparison** — rows are not mapped to reference buckets; would need a mapping rule.
- **Moving `reimToast` / `reimConfirmDialog` into a global helper** — every page has its own pair; extracting them touches many pages.
- **Approvals and Accounting Center liquidation views** — other pages.

## Verification

- Step-1 tests, with positive controls: B1, B3, B4, B5, B6, the CA clear route and the alias removals fail on the current code; record that before fixing.
- Focused modules: `tests.test_liquidation_pages`, `test_accounting_branch_codes`, `test_accounting_attachment_management`, `test_reimbursement_liquidation_row_deletion`, `test_request_recall`, `test_shared_pdf_upload_conversion`, `test_approval_notifications`, `test_approval_center_wording`, `test_email_template_settings`, `test_changelog_workflow`, `test_changelog_coverage`; then one full-suite run quoted against 1,495 / 23 F / 3 E / 5 S.
- Test-client checks as a requester with a linked engineer profile: both pages render; get, add, save, delete row, upload/delete receipt, delete all receipts, clear, submit, preview and download behave as before apart from the planned changes.
- `node --check` on the extracted shared script plus each page script.
- No browser check by the agent. The owner checks both pages on desktop and at 375 px, light and dark, with another accent: header colour; summary balance wording; auto row has no Delete; Clear Form resets auto rows; several receipts upload at once; readiness lists missing receipts as a warning; submit without signature shows the Settings panel; after submit the page locks and Preview/Download still work; a failed download shows the message on the page; console has no errors.

## After implementation

1. Self-review the diff: every removed ID/function is unreferenced (including `onclick` and `data-` handlers), both pages only differ in their blocks, no dark rule names a removed class, no alias still used by `approvals.html` / `accounting_center.html` was removed.
2. Prove the new tests fail without the fixes, then pass with them.
3. Focused modules, then the full suite, quoting counts against the baseline.
4. Service worker bump and `releases.json` entry.
5. `changes.md` and this plan's status, with any difference between plan and outcome.
6. Commit with explicit staging; exclude `scheduler.db`, handoffs, `.claude/`, `output/`, `tmp/` and the loose handoff file. Commit and push only on the owner's instruction, then verify `origin/main` and Railway's deployment.

## Risks

- **Shared template breaks one page while fixing the other.** Both pages render in the test client and the focused tests read both; the owner's visual check covers both.
- **Removing alias routes breaks a bookmark or an old email link.** None found in templates, static files, tests or `app.py`; primary routes are unchanged. Re-search before each removal.
- **Auto-row delete guard surprises a user who wanted to drop Per Diem.** They can set the amount; the message explains it.
- **Signature block stops someone mid-submit.** Same flow as Reimbursement, with a direct link to Settings.
- **Clear Form semantics change on Travel** (auto rows reset, not removed) — matches what the seed already does on reload; the pop-up text says so.
- **String-contract tests** on the old templates need updating; they are in the focused run.

---

