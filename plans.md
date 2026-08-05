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

## Staff type and permission tickboxes on Add Personnel

**Status:** `In progress`
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
