# Medical Service SMS — Pending Work

Everything started but not finished, plus anything deliberately deferred.
Companion to `changes.md`, which records what **was** done. This file records what is
**still open**.

**Update rule:** only touch this file when the project owner explicitly asks. It is not
maintained automatically the way `changes.md` is.

Last updated: 2026-08-14, at the owner's request, after the Reimbursement Tracker moved to shared
server-owned batches and its filters and export were repaired.

**Start here if you are picking this up cold.** Suite green at **662 tests**. **Do not quote "one
pre-existing skip" — that is not a property of this suite**, and several entries in these journals
have repeated it as though it were. The skip is
`test_latest_user_facing_commit_has_a_changelog_entry`, which **skips when the newest commit touches
only `tests/` or `.md`** and **runs when it touches user-facing paths**. So the number moves with
what was committed last, not with the health of the suite. Quote the test count and treat the skip as
a statement about the last commit. `origin/main` was at `a5f6d3f` when this was written, with the
local branch in sync; the service worker read `v89-analytics-system-start`.
**Confirm all three with `git log --oneline -1`,
`git rev-list --left-right --count origin/main...HEAD`, and by reading `CACHE_VERSION` out of
`app.py` — never from this note.** The tip line has now gone stale six times, once inside an hour.
**A commit hash in a document is a timestamp, not a fact** — and note that a commit *cannot* record
its own hash, because writing it changes it; see section 6. The working tree carries **four** local
artifacts: `scheduler.db`, `output/`, `tmp/`, and the loose 2026-07-26 handoff file.

**`Handoffs/` is tracked**, by the owner's decision on 2026-08-11 — see section 4.

> ### ⚠️ Read before planning any verification: browser automation is no longer available here.
>
> The owner added a **non-negotiable** rule to `AGENTS.md` ("Codex App Safety During Testing") on
> 2026-08-12 and confirmed it directly: **never close, archive, navigate away from, finalize or
> terminate the agent app or task while testing, and do not use in-app browser automation for this
> project.** Browser automation had been terminating the owner's own session, losing their in-flight
> work. Verify with the Flask test client, source-level checks and local HTTP checks instead. If
> browser verification seems essential, **stop and ask** — an approved plan is not permission.
>
> **This is a real loss, and pretending otherwise would be the mistake.** This file records over and
> over that the dominant defect class here is *suite-invisible and browser-obvious*. The answer is
> not to skip that coverage but to convert it into source-level guards that assert the **class** —
> see the theme-token guard in section 6, which now catches in CI what a dark-mode browser check
> used to catch by eye. Where that is genuinely impossible, say so plainly and hand the step to the
> owner, exactly as the `ResizeObserver` item was handed over on 2026-08-09.

**There is no open defect.** Section 1 is empty. But **six things are waiting on the owner rather
than on code** — they are listed first because none of them will resolve themselves:

| Waiting on | Why it matters |
| --- | --- |
| **The tracker migration REWRITES every existing reimbursement row** — added 2026-08-14 | On the first request after deploy, `ensure_reimbursement_tracker_schema()` (`app.py:3732`) forces **every** `reimbursement_tracker_entry` to `BATCH-032`, `batch_sequence = 32`, **and a rebuilt control number**. That was approved in the plan and is ranked as its own risk 1 — but it is the only migration in this project that *rewrites* rows rather than adding to them, and control numbers are what Accounting identifies a reimbursement by. **If Diary has already printed, filed or emailed anything carrying an old control number, it will no longer match.** The local database holds **0 tracker rows**, so this could not be exercised here at all. **Count the rows before and after the deploy, and tell Diary before she notices** |
| **89 of 145 clients have no equipment registered in Products** — added 2026-08-12 | A P.O. now requires a machine, and the picker deliberately offers **no free-text fallback**, so **P.O. entry is blocked for those clients until Products is backfilled**. This is the change users will feel first and it will read as breakage unless someone tells them it is deliberate. **Measured on the tracked local `scheduler.db`, not production** — 145 clients, 99 products, all assigned, across 56 distinct clients. Re-measure against the live database before acting on it |
| **The `reimbursement_tracker_paid_cc` group has zero recipients** | Verified in the live database. The Paid in Full notification therefore reaches the engineer with **nobody copied**. Add recipients in Settings → Email Recipients. The feature works; it is just uncopied |
| **Four engineers have no email address** — Kevin Garoche, Mark Felongco, Jocel Prudente, John Erick Wong | Marking their rows paid saves fine and shows Diary a warning, but nobody is notified. Fix in Personnel |
| **Jocel Prudente still reads `JP` in the local database** | The `JP → JOP` correction runs on the first request after deploy. **The code has now been pushed**, so unlike the previous refresh this is finally *confirmable* — one glance at Personnel in production closes it. Confirm rather than assume |
| **The tracker holds 0 rows** | So the amount-suggestion chips show nothing yet, and the export is empty. Both fill in as Diary files batches — expected, not a fault |

### The Reimbursement Tracker became a shared batch register — six commits, 2026-08-13/14

The largest behavioural change since the tracker shipped, built by Codex from four plans in
`plans.md` and reviewed here. **No code defect was found in either review.**

| Commit | What |
| --- | --- |
| `7847100` | The singleton `reimbursement_tracker_batch_state` table, the one-time BATCH-032 normalization, and a server-owned current batch replacing the old max-plus-one suggestion |
| `6722481` | The page scoped to the current batch, with `batch_scope=current\|all` on the export |
| `47ebd96` | Selectable historical batch views |
| `06ddeab` | Unrelated: Analytics now defaults to the system-start date (2026-05-18) rather than the current month |
| `723333b` | The register fixes — filters, export, and non-scrolling confirmations |
| `7c87be3`, `355cbec`, `a5f6d3f` | The equipment coverage label, and the review fixes |

**Four things to know before touching any of it:**

1. **The batch state is a singleton row and everything fails closed without it.**
   `reimbursement_tracker_current_batch_state()` (`app.py:40553`) raises when row 1 is missing, and
   **all six consumers turn that into a 503 with a clear message** — verified by forcing it. The
   migration also refuses rather than corrupting: any row lacking a submission date or engineer
   initials aborts the whole transaction, so no partial marker is written and the next request
   retries. The error reaches **stdout only**, so a stuck migration is visible in the Railway log and
   as a 503 on the page, nowhere else.
2. **Batch transitions are a compare-and-swap**, `UPDATE … WHERE current_batch_sequence = :expected`
   checking `rowcount` (`app.py:41043`). Two people pressing "Start new batch" cannot both win. Stale
   transitions, stale adds and the BATCH-999 cap are all asserted.
3. **The total cards now follow the filters, and the scope caption underneath them is load-bearing.**
   `#rt-kpi-scope` reads *"Showing all of BATCH-032"* or *"Showing 3 filtered row(s) of BATCH-032"*.
   Without it a filtered ₱ total looks exactly like a batch total — someone copies it and is wrong.
   **Do not remove the caption while keeping the filtered totals.**
4. **The export's `current` scope now means the batch you are viewing**, via an optional
   `batch_sequence` companion. The wire values are still `{current, all}` — the honesty fix is in the
   label, which reads *"This batch (BATCH-032)"*. Exporting a historical batch on its own was
   previously impossible.

**The defect the review found, and it had shipped:** filtering by engineer and pressing Export
produced a **headers-only workbook**. The page sent the engineer's numeric id as `engineer=`, and the
server matched it as a substring of the engineer's *name*. No error; the screen showed N rows and the
file had none. Fixed by matching `engineer_id` exactly, with the legacy name path kept for bookmarks
**and a log line when it receives an all-digit value** so the old shape cannot rot silently.

**The export workbook now carries a literal TOTAL row** in columns F/G, deliberately **not** a
`=SUM()` — openpyxl writes formulas as strings and never evaluates them, so a `data_only=True`
reader would see `None`, and a `#REF` is the one thing that corrupts what Accounting consumes. A test
pins that there are no formulas anywhere; **do not "improve" the total into a formula.** The row sits
**outside** `auto_filter.ref` so sorting in Excel cannot drag the grand total into the data.

**Both registers stopped scrolling to the top on save.** `notify()` no longer calls
`window.scrollTo` and no longer overwrites `className` — the latter had been stripping `d-none` and
`no-print`, permanently reflowing the page on the first message and putting the alert into printouts.
Confirmations are now fixed-position toasts built on real theme tokens, with each page's alert kept
as a `visually-hidden` live region. That last part also fixed a latent a11y bug: `d-none` is
`display: none`, which removes an element from the accessibility tree, so the live region had been
announcing nothing.

### One P.O., many machines — in four commits, one day after the opposite shipped

The owner revised the requirement on 2026-08-13: **a P.O. covers several machines, not one.** Built
by Codex from the plan in `plans.md`, reviewed here. **The review found no defect** — the first time
that has happened in this file's history.

| Commit | What |
| --- | --- |
| `5d7372e` | `PurchaseOrderMachine` association table with a unique pair constraint, an idempotent backfill, chips in the modal, "+N more" in the register, any-machine filtering |
| `f307253` | Analytics split into P.O. units and machine-link units, plus release plumbing |
| `e4c8a40` | Execution outcome in `plans.md` |
| `d8507e2` | **Review fix** — two coverage gaps closed; no behaviour changed |

**Read this before assuming the old shape.** `purchase_order.product_serial` still exists but is a
**write-only mirror**: one writer (`apply_purchase_order_machines`), **zero readers**, kept only so a
rollback to the one-machine release still shows the primary machine. The real data lives in
`purchase_order_machine`. A corruption test pins this — it sets the column to garbage and asserts the
register, export and analytics never surface it. **Do not start reading that column again.**

**Codex caught a hazard the plan missed, and it is worth knowing before touching the write path.**
`apply_purchase_order_machines()` clears the collection and flushes *before* reassigning, because
SQLAlchemy would otherwise INSERT a replacement before deleting the orphan holding the same
`(P.O., serial)` unique key — so an edit from `[A,B]` to `[B]` would 409. Confirmed load-bearing by
removing it. **The unique constraint the plan insisted on is what creates that hazard**; the two
belong together.

**The analytics numbers deliberately no longer add up, and someone will file it as a bug.** Three
units now coexist: **orders** (`total`, `linked_total`, `unlinked_total`, `linked_pct`), **links**
(`by_machine`, `by_model`, `by_coverage`, `machine_link_total`), and **entities** (`machine_total`).
`sum(by_coverage)` equals `machine_link_total`, **not** `linked_total`. That is correct. Do not
"fix" it by de-duplicating per P.O. — that would destroy the per-machine analysis the tab exists for.

### Machine-scoped P.O. records and the Equipment tab, in five commits

Built by Codex from the plan in `plans.md`, reviewed here afterwards. **The review found one real
defect, and it was the same defect this file had already recorded from the previous feature.**

| Commit | What |
| --- | --- |
| `081d647` | Part A — `purchase_order.product_serial`, type-to-search client picker, client-scoped equipment picker, machine column/filter/sort, 13-column export, and the two Products-side guards |
| `fd781b1` | Part B — the Analytics page's first tab structure, plus the Equipment tab |
| `66a2723` | Codex's execution outcome recorded in `plans.md` |
| `73b4467` | **Review fix** — the transposed theme token, plus the guard widened repo-wide, plus the service worker label corrected |
| `fd8625c` | The `AGENTS.md` browser rule and the journals |

**What the review found, and why it matters more than the fix:** `templates/po_details.html` used
`--app-raised-surface`; the token is `--app-surface-raised`. The new equipment picker's hover state
measured **1.01:1 in dark mode** against 14.44:1 in light. That is *the same transposition, of the
same token*, that produced the Reimbursement Tracker's 1.04:1 defect — and this one was slightly
worse. Full mechanism and the durable fix are in section 6.

**Two things Codex got right that this file had flagged as the riskiest parts**, worth recording
because they are the cases where the plan's warnings did their job: the Excel column shift is
arithmetically correct throughout (amount at `row[9]`/column J, `A1:M`, TOTAL `=SUM(J2:Jn)`), and
both Products-side guards were built — `delete_product` now returns 409 on a referenced machine,
and a serial rename repoints P.O. rows before the delete-and-recreate. **Both of those were latent
bugs discovered while planning, not while coding**: `update_product` repointed `Shift.product_id`
and nothing else, and `delete_product` had no reference check at all.

### The Reimbursement Tracker, in four commits

Built by Codex from a plan in `plans.md`, reviewed here after each round. **Both reviews found
something; neither found a defect in the second round.**

| Commit | What |
| --- | --- |
| `018cfd0` | The tracker: register page, capability flag, Excel export — plus four fixes from review, of which the real one was **dark mode at 1.04:1 contrast** from a transposed CSS token |
| `c426cba` | Modal could not be scrolled, so Save was unreachable; batch numbering continued at 032 instead of restarting at 001 |
| `c5e1b64` | The server suggested `BATCH-032` and **the form ignored it** — a test asserted the endpoint and not the field |
| `81b4f1b` / `aaeb579` | Round two: unique engineer initials, export cut to seven columns, Paid in Full email with a CC group, amount-suggestion chips — plus two fixes from review |

`7cc7fe7` landed after that and is **unrelated** — P.O. Details summary cards now show a
`Total amount: ₱…` label. Noted here only so the tip above is not mistaken for tracker work.

**The most useful thing to know before touching any of it:** three of the four defects found across
both reviews were **invisible to the test suite and visible in a browser in seconds** — white-on-white
text, an unscrollable modal, and a form ignoring a value the API returned correctly. The suite was
green for all three.

> ### ⚠️ Correction, 2026-08-11: this file said the backup was broken. It was fixed two days earlier.
>
> The 2026-08-11 journal refresh recorded *"One open defect: the System Backup download fails in
> production"*, kept bug 2a headed **OPEN**, and stated the worker was `v83`. **All of that was
> wrong**, and the same wrong claim propagated into `changes.md`'s 2026-08-11 entry and into
> `Handoffs/08-11-26 handoff.md`, which named it the *"immediate known technical priority"* and
> diagnosed it with code (`call_on_close` deleting the temp file) **that no longer exists on main**.
>
> **A fresh session following that handoff would have re-implemented a feature that already ships.**
> That is the whole cost of a journal being wrong, and it is why this correction is at the top rather
> than buried in section 1.
>
> Verified against the live tree, by running it rather than reading it: `call_on_close` is **gone**;
> `download_system_backup()` serves a stored archive via `current_backup_archive()`; all five
> `/admin/backup*` routes exist; a ranged request returns **206**; a partial + resumed download
> reassembles **byte-identical** to a single-pass download; two full downloads are byte-identical;
> and the database inside the archive passes `PRAGMA quick_check` as a real queryable database.
>
> **How it happened, because the mechanism matters more than the error.** `changes.md`'s own
> 2026-08-09 entry describes the rework correctly. The refresh reconciled the journals against each
> other and against a *remembered* state, not against the code — so one document's stale sentence
> became three documents' agreed fact. **Reconcile journals against the tree, never against another
> journal.** This file already carried the warning in a different form: *"re-measure before acting on
> a number in here."*

**Current release state:** every plan in `plans.md` reads `Executed`, and as of 2026-08-12
everything is **pushed and in sync with `origin/main`** — including the machine-scoped P.O. work,
which deploys on push. No approved plan is waiting to be built.

**The browser-verification picture changed on 2026-08-12 and the old line here is superseded.** It
used to read *"Edge remains the main browser-verification gap; Brave is covered by the owner's daily
use."* Both halves are still true, but they are no longer the point: **browser verification is now
unavailable from this side entirely**, by the owner's rule at the top of this file. Every browser
row in section 3 is therefore an owner task, not a deferred one. Do not plan work that depends on
being able to look at it.

## The 2026-08-09 owner verification pass

The owner drove the app directly and reported back. **Six items closed, one bug opened.** This is
the single most productive entry in this file's history, and all of it came from using the app
rather than reading it.

| Item | Outcome |
| --- | --- |
| LPR printing | **Pass.** Printed on paper — *"LPR printing is good"*. Closes the page-marker and signature-stamp print items |
| Sidebar on mobile | **Pass.** *"looks good now"* — the wrapped header reads correctly on a real phone |
| TSR draft round trip | **Pass.** Draft survives; *"it does not disappear"*. This was the one test that proved the feature does its job |
| Analytics charts on resize | **Pass.** *"charts are good even when dragging the window"* — closes the `ResizeObserver` trigger that was structurally unverifiable from here |
| Brave | **Covered.** The owner uses Brave daily, so it is verified by real use rather than by a pass |
| Analytics print view | **FAIL.** *"print preview looks bad. we should add a proper print button"* — now queued work, section 2 |
| System Backup download | **FAIL.** *"the download keeps failing even when clicking resume"* — now bug 2a, section 1 |

**The browser blind spot has shrunk but not closed.** Brave is the owner's daily browser, so
everything shipped has in fact been used there. **Edge remains unverified**, and Edge is where the
session-loss report came from, so it is not an idle gap.

## The 2026-08-08 session

Two commits, both pushed. Everything below was closed here rather than deferred.

| Work | Commit | Note |
| --- | --- | --- |
| TSR draft backup opened to every account that can write one | `2e3c2d1` | closes bug 1z |
| A permanent 403 no longer reported as a temporary retry | `2e3c2d1` | the half that kept 1z unreported |
| `/login` honours `next`, with an open-redirect guard | `2e3c2d1` | closes the papercut in section 2 |
| Backup no longer blocks every other user | `d28483d` | Procfile, gthread |
| Offline API reads return 503 rather than the offline page with 200 | `d28483d` | closes the 5b observation |
| Six shell controls raised to 44×44 on touch | `d28483d` | closes the section 3 tap-target note |

**Three claims in this file turned out to be wrong, all of them reassuring rather than alarming** —
each is corrected in place below rather than deleted:

1. The tap-target note called the `.toggle-btn` **unlabelled**. It has carried
   `aria-label="Hide navigation"` the whole time.
2. The same note **missed two controls**, because they were already 44 px tall and only failed on
   width.
3. Section 5b estimated that fixing the offline-200 fallback would "touch every consumer of
   `networkFirst`". It touched one function; the fetch handler's ordering already contained it.

None was careless — each was written from reading rather than measuring, which is the failure mode
worth naming. **Re-measure before acting on a number in here.** A test fixture in the 1z work was
wrong the same way, and was wrong *before* the code was.

## The short version of 2026-08-07

A long session. Four items closed in the morning, a verification pass closed five more, then three
Codex batches landed and were reviewed here.

**Shipped and reviewed:**

| Work | Built by | Reviewed in |
| --- | --- | --- |
| Analytics chart sizing, logout cache purge, two dead routes retired | here | — |
| `parse_engineer_ids` 500 fix + five verification rows closed | here | — |
| Signature stamps enlarged ~1.5× everywhere | Codex `8d97b58` | `92f6e0e`, `5ab6555` |
| Server-backed TSR drafts | Codex `f792d22` | **findings open — section 1** |
| LPR draft recovery after reload | Codex `ac521f4` | clean |
| LPR continuation pages on the official template | Codex `d5e6d60` | clean, one question in section 2 |
| Backup resilience + bucket timeouts | Codex `01e2cfa`, `d3eed50` | superseded by `f08068f` |
| Backup download fixed (service worker) | here `f08068f` | — |

**Every review found something. Two of the three Codex batches shipped with a real defect**, both of
a shape this file already records. That is not a criticism of the work — the implementations were
competent and the suites were green — it is the reason the review step exists.

## The three things most worth knowing before you touch anything

1. **The service worker's navigate branch swallows authenticated downloads, and it has now done it
   twice.** Anything reached by an `<a href>` or `window.location` arrives as a navigation; matched
   after the navigate branch it reaches `fieldNavigationFirst()`, which caches every ok response and
   ends its failure chain at the `/offline` page. That produced the export leak (`v71`) and then the
   backup download failure (`v81`) — where an admin saw *"you are offline"* while online, an 80 MB
   archive was being written into Cache Storage, and a **stale archive could be served as current**.
   There is now a `NETWORK_ONLY_DOWNLOAD_PREFIXES` list; **add to it rather than rediscovering this**.
   And note `Cache-Control: no-store` does **not** keep anything out of Cache Storage — that API
   ignores HTTP cache headers entirely.
2. **A page gate and its endpoint gate must be the same expression.** Section 6 recorded four
   occurrences; the TSR draft work made it **five**. See section 1 — it is open.
3. **IndexedDB is where unsynced field work lives.** The logout purge clears Cache Storage only, and
   must keep doing so. Offline schedule queues, TSR queues and TSR drafts are all in IndexedDB.

**What happened today, in order:**

1. **The 2026-08-05 browser pass was finally done** — all six features driven through a browser.
   That was the largest unverified block in this file and it is closed (section 3). Five passed.
   It found two bugs: the export cache leak and every provisional-leave failure reason being
   discarded. **Both fixed the same day**, `v71` and `v72`.
2. **P.O. Details shipped** (`b01c78c`, `3dd83b1`, Codex), reviewed here (`5b40dde`). Sound, but the
   Settings switch reported an effective permission rather than the stored grant, and the journal
   claimed test coverage that did not exist.
3. **The same write-back was fixed in the stock inventory switches** (`ad463c8`), which **partly
   overturns an entry in section 5** — read that correction before trusting it.
4. **The Analytics upgrade shipped** (`45da21c`, `a762b05`, `d562654`, Codex) and was reviewed here
   (`34f60b9`). Strong work — XSS structurally closed, accent theming live, the access split
   correct. The review fixed a P.O. panel invisible to reports admins and a trend arrow on a metric
   that cannot carry one. **One new item is open in section 3.**

**The single most useful thing to know before touching Analytics again:** `active` is *exactly*
`total − completed`. It is the same measurement negated, so anything true of one is true of the
other with the sign flipped. That is why neither carries a period comparison. See section 6.

Filled previously on 2026-08-05 (end of session) after **six features shipped and were reviewed in
one day**: HR schedule viewer, staff types on Add Personnel, provisional leave, request recall,
grantable admin capabilities, and TSR previews on schedule cards. Every one was built by Codex from
a plan recorded here and reviewed afterwards in this repository. That review found two privilege
escalations and one silent-no-op; all are fixed and pushed.

Filled earlier the same day recording the barcode scanner verified clean and the What's New
digest self-test sent, and on 2026-08-04 after the offline audit and the review of two commits
from another tool.

> **Read this first: you are not the only agent in this repository.** Codex works in the same
> working tree and pushes to the same branch. During the 2026-08-02 session it wrote an entry
> into `changes.md` while work was in flight here, and on 2026-08-03 it landed four commits
> directly. Before starting anything: `git fetch origin`, check `git status --short` for
> changes you did not make, and **stage explicitly** so you never commit someone else's
> half-finished work. If `changes.md` has an entry you did not write, leave it alone.

**Where the work lives:** this repository, `medical-service-sms-railway`, working directly.
The sandbox at `Claude-medical-service-sms-railway` still exists, synced to `baefb63`, and
is no longer the default. This repository is push-by-default per AGENTS.md section 3, so
there is no free-experimentation area — if the sandbox is used again,
`git fetch && git reset --hard origin/main` there first, since it drifts the moment anything
lands here.

**Shipped, all pushed to `origin/main`:**

| Commit | What |
| --- | --- |
| `a0435f3` | Dashboard phase 2 — scheduler rebuilt as a dispatch workbench |
| `5d5b647` | Dashboard phase 3 — manager rebuilt around decisions and direction |
| `88b88cc` | Dashboard phase 4 — shortcuts consolidated, two unreachable sections retired |
| `5de1658` | Hybrid ratified, rodito exempted, developer preview removed |
| `187c2ec` | Journal correction (stale `scheduler.db` claim) |
| `ac78987` `2bc429c` `10b7f21` `a06e35e` | Reports renamed to TSR files, sidebar flattened |
| `23a58fc` | Approved plans must be recorded in `plans.md` and waited on |
| `3da143f` | LPR form signatures put back on their own lines |
| `709106c` | Offline schedule creation for field engineers |
| `9d4721b` | Recorded the unverified offline attachment path |
| `bfacf8f` | Add Schedule form opens offline rather than depending on cache luck |
| `28ba1b0` | Create a TSR against a schedule that has not synced yet |
| `0bb60e3` | Missing column stopped every TSR save — `tsr_number` migration |
| `e12a439` | Schedule picker stopped renumbering saved TSR drafts |
| `f268397` | Weak-signal TSR queueing, and assets survive a cache bump |
| `a01f2b6` | Three contained gaps from the offline audit |
| `515698f` | Schedule option identity no longer depends on list position |
| `ca00803` | Plan B — durable offline TSR storage (Codex, reviewed here) |
| `6d824a5` | Engineer read-only stock inventory (Codex) |
| `aff9001` | Reimbursement package total consistency (Codex) |
| `8f72ce2` | Narrowed a widened branch check; fresh test DB per run |
| `db285d5` | Barcode scanner closed, digest item narrowed |

**The 2026-08-05 run, newest last.** Codex built each feature; the `claude` commits are the
reviews that followed.

| Commit | What |
| --- | --- |
| `9b6effd` `a7560f3` `2ff9181` `d6478a1` | HR read-only schedule viewer (Codex) |
| `5278df2` | **Review fix** — the HR CSV export leaked what the calendar redacted |
| `4516c89` `90f3b2e` | Staff types and permission tickboxes on Add Personnel (Codex) |
| `79d2847` | **Review fix** — pinned three permission rules changed inside a refactor |
| `5c976bb` `35673e1` | Provisional leave plotted from the calendar (Codex) |
| `b5dd637` | **Review fix** — the supersede notice named neither leave type |
| `2c20eed` `6b8021f` | Request recall with a mandatory reason (Codex) |
| `2ce472b` `fb3f37f` | Grantable admin capabilities in Settings (Codex) |
| `54c4aaa` | **Review fix** — regional admin could schedule Manila; worker bumped |
| `5462c38` | Recorded the schedule-card TSR plan |
| `6fa7fe4` `4748cac` | TSR previews from the schedule details popover (Codex) |
| `9b33c02` | **Review fix** — three tests asserted source text, not behaviour |

**The 2026-08-06 run.**

| Commit | What |
| --- | --- |
| `b01c78c` `3dd83b1` | P.O. Details register and its grantable access toggle (Codex) |
| `5b40dde` | **Review fix** — the P.O. Settings switch reported the effective permission, not the stored grant; six missing tests added |
| `ad463c8` | The same write-back fixed in the two stock inventory switches, at the owner's request |
| `e8ede40` (`v71`) | Authenticated exports made network-only, closing bug 1a — the runtime-cache leak |
| `98bd7b4` (`v72`) | Provisional-leave refusals now show the server's reason, closing bug 1b |
| `f59703c` | Recorded the approved Analytics upgrade plan |
| `45da21c` `a762b05` `d562654` (`v73`-`v75`) | Analytics upgrade: trends, themed SVG charts, P.O. reporting (Codex) |
| `34f60b9` (`v76`) | **Review fix** — P.O. panel invisible to reports admins; a trend arrow on a metric that cannot carry one |

**Historical, not current — this paragraph describes the state on 2026-08-09 and is kept only to date
the run above it.** It read 582 tests and worker `v83-offline-api-status` then. For the current
figures see the header at the top of this file, and for the worker **read the live value out of
`app.py` immediately before committing**, never from a note — this line has now gone stale four
times, the fourth being that it sat here reading as current until 2026-08-11.

**Every review found something, and two were live privilege escalations.** That is the single
most useful fact for the next reader: the implementations were competent, the suites were green,
and the defects were still there. Both escalations passed hundreds of tests because **nothing
exercised the affected account**. See section 6. **That held again on 2026-08-07** — the TSR draft
work shipped green with the gap recorded as bug 1z, for exactly the same reason. **1z was fixed on
2026-08-08 by removing the second gate rather than correcting it**, so the pattern now has a durable
answer as well as a diagnosis.

**Every plan in `plans.md` reads `Executed` again** — `d5e6d60`, `f792d22`, `8d97b58`, `e0182a2`.
Nothing is waiting for a go-ahead, but read `git log` rather than a `Status` line, per the warning
below.

**A third journal now exists.** `plans.md` holds what was **agreed and is waiting to be
built**; `changes.md` what **was** done; this file what is **still open**. Approving a plan is
not permission to execute it — see `AGENTS.md`, "Approved Plans".

**Plans are now written to be executed, not read.** Since `73f331d` every plan carries numbered
execution steps naming the files and functions each touches and what "done" looks like, an
investigation section citing `file:line`, and an "After implementation" section covering the
review and release workflow. The required structure is in `plans.md` under "How to use this
file". Plan B is the reference example. **Every plan in `plans.md` now reads `Executed`;
nothing is waiting for a go-ahead.**

**But the "wait for a go-ahead" rule did not hold in practice on 2026-08-05, and the next reader
should know that before trusting a `Status` line.** Two plans were executed while still recorded
as `Approved — awaiting go-ahead` — grantable admin capabilities most clearly, which was written
here with an explicit "nothing built" note and was implemented anyway. Nothing was reverted,
because the work was sound apart from the escalation the review caught. The rule is still the
right one; it simply is not currently a reliable signal, so **read `git log` rather than a status
line to learn what has actually shipped.**

**The dashboard redesign is complete, and the hybrid question that outlived it is now
decided.** All four phases plus the ratification:

| Commit | Phase |
| --- | --- |
| `baefb63` | 1 — engineer, "Today First" |
| `a0435f3` | 2 — scheduler, dispatch workbench |
| `5d5b647` | 3 — manager, decisions and direction |
| `88b88cc` | 4 — shortcuts consolidated, dead sections retired |
| `5de1658` | Ratification — manager + engineer stacked, scope divider, rodito exempt |

**Note for the next reader on service worker versions.** `v49` was skipped in effect: this
repository is worked in directly and `9a2ad4d` bumped to `v50` from outside the session that
had claimed `v49`. If two streams of work are ever in flight again, read the live value out of
`app.py` immediately before committing rather than trusting what an earlier note in that
session recorded.

---

## 1. Open bugs

**None.** Everything below this line is a fixed entry kept for its mechanism.

### ~~2a. The System Backup download fails in production~~ — FIXED, `b4b17fc`

**Fixed 2026-08-09 by the System Backup rework, and this entry was left open in error until
2026-08-11.** See the correction notice at the top of this file.

The answer turned out to be neither of the two options that were on the table. The archive is now
**built ahead of time by a background job and the download serves a finished file**:

- **Resume works**, because there is a stable file to resume from. `send_file`'s `conditional=True`
  and `etag=True` **defaults** supply Range/206 — verified by inspecting the installed Flask 3.1.2
  signature, which means the old route *already advertised* `Accept-Ranges`. **The bug was never a
  missing parameter; it was that the file was deleted.** That is the single most useful sentence in
  this entry.
- **The idle-timeout hypothesis is moot**: nothing is built during the request, so the first byte
  leaves immediately.
- **Streaming was not needed after all.** It would have cost `Content-Length` and both `X-Backup-*`
  headers; build-then-download keeps them *and* gains Range. See section 5, where the decision is
  recorded as superseded rather than reversed.

Also fixed in the same work: the database is now snapshotted through SQLite's backup API rather than
copied as a raw live file, so an archive can no longer contain a torn database — a defect nobody had
reported because it is invisible until a restore.

**Follow-up shipped 2026-08-11** after a review: `/admin/backup` now falls back to the app's offline
page instead of a raw browser error, and the service worker comment that had been orphaned from its
branch was put back. Worker bumped to `v85-backup-offline-fallback`.

The original entry is kept below. Its diagnosis of *why* Resume could never work is still the
clearest worked example in this file of a defect that is structural rather than intermittent.

<details>
<summary>Original entry, retained for the mechanism</summary>

### 2a. The System Backup download fails in production — reported 2026-08-09

**Reported by the owner, in production, on Brave:** the download starts and then fails, and
**pressing Resume does not recover it**. The browser shows *"Check internet connection"* against
`medical_service_backup_20260809_140711.zip`.

**One half is already certain from the code, without any further diagnosis: Resume can never work.**
`download_system_backup()` builds the archive into a `NamedTemporaryFile` and registers
`@response.call_on_close` to `os.remove()` it. The moment the response closes — including when it
fails — **the file the browser would resume from is gone**. Retrying the URL does not resume
anything either; it builds a brand-new archive with a new timestamp and different bytes. So "click
Resume" is not a workaround and never was, and the browser offering the button is misleading.

**The likely cause of the primary failure, stated as a hypothesis and not yet proven:** the archive
is still **built completely before a single byte is sent**. Nothing reaches the browser during the
build, so any idle timeout between the client and the app — Railway's edge proxy being the obvious
candidate — closes a connection that looks dead. That reads to the browser exactly as a dropped
connection, which is the message shown. Production is also much larger than the 39 MB / 3.6 s
measured locally: it has real uploads and a bucket read carrying a 12-second budget of its own.

**This is the trigger for reversing a decision recorded in section 5, and that should be done
deliberately rather than quietly.** On 2026-08-08 streaming the ZIP was rejected on measurement,
with the recorded condition *"revisit only if the archive grows enough for the build itself to
approach the timeout"*. **That condition has now been met by a real report.** Streaming sends bytes
immediately, so no idle timeout can bite. The costs are unchanged and must be accepted with open
eyes: **no `Content-Length`** (so no progress bar), and **no `X-Backup-Complete` /
`X-Backup-Warning-Count`** headers, because the status is committed before any error is known. The
prototype already exists and was proven valid — see section 5.

**Do not build anything before getting the real error.** `f08068f` removed the offline page that was
masking it, so the true failure is now visible and nobody has looked at it yet. What to collect:

- **Does the request reach the app at all?** Railway logs for `/admin/download-backup` — a gunicorn
  worker timeout, a memory kill and a proxy timeout look completely different there.
- **Is the gthread Procfile change actually deployed?** `d28483d` landed 2026-08-08; if Railway has
  not redeployed, the failure is still being produced by the old single sync worker.
- **How long does it survive, and how big does it get?** A failure at a consistent number of seconds
  points at a timeout; a consistent number of megabytes points at something else entirely.
- **The response headers**, if any arrive — `X-Backup-Complete` tells you the build finished.

**Fixing the Resume half is worth doing regardless of the cause**, because it is a certain defect
rather than a hypothesis: either keep the archive long enough to serve a range request, or make the
response explicitly non-resumable so the browser stops offering a button that cannot work.

</details>

### The rest of section 1 is closed

Everything below this line is a fixed entry kept for its mechanism — each one is a worked example of
a class this project keeps meeting, which is why they are struck through rather than deleted.

### ~~1z. TSR draft backup silently does nothing for five account shapes~~ — FIXED, `2e3c2d1`

**Fixed 2026-08-08.** The page gate and the three endpoint gates are now **one expression**,
`can_back_up_tsr_drafts()`, called by `/offline-tsr` and all three routes. That is the actual fix:
the previous shape let the two drift, which is how this reached `main` for the fifth time. The
message was fixed too — `standaloneTSRServerBackupFailureText()` now separates a permanent 403 from
an expired 401 from a genuine connection failure, so nobody is told to wait for a retry that will
never come.

**The test found a fixture wrong before it found the code wrong, and that is the useful part.**
Building the "stock inventory user" row with `stock_inventory_only=True` failed: an inventory-**only**
account cannot reach `/offline-tsr` at all, fenced off by `restrict_stock_inventory_only_accounts()`.
So the affected shape was a stock-inventory user *without* only-mode. Both fenced shapes
(inventory-only, HR-schedule-only) are now pinned with their **expected refusal status** — 403 from
this gate, 302 from a fence — so a fence quietly disappearing cannot be absorbed as "still refused
somehow".

**Still not verified:** the new 403 message has never been seen on screen. See section 3.

The original entry is kept below: it is the clearest worked example in this file of a page gate and
an endpoint gate disagreeing, and the reproduction table is how the next one should be found.

<details>
<summary>Original entry, retained for the mechanism</summary>

### 1z. TSR draft backup silently does nothing for five account shapes

**This is the one open defect and it is silent.** `f792d22` added server-backed TSR drafts, gating
all three routes on `is_admin_authorized() or role == 'engineer'`. But `/offline-tsr` admits
**everyone except approver-only users**. Verified by calling, not by reading:

| Account | `/offline-tsr` | `/save_tsr_draft` | `/get_tsr_drafts` |
| --- | --- | --- | --- |
| engineer | 200 | 200 | 200 |
| plain staff | 200 | **403** | **403** |
| scheduler | 200 | **403** | **403** |
| personnel admin | 200 | **403** | **403** |
| reports admin | 200 | **403** | **403** |
| stock inventory user | 200 | **403** | **403** |

Those five can open Create TSR and write a draft, and **none of it is ever backed up**. What they
see makes it worse: the panel says *"backed up to your account when online"* unconditionally;
autosave failures are `console.warn` only; and the explicit Save Draft reports *"Account backup is
temporarily unavailable and will retry when the connection returns"* — but a 403 is **permanent**,
so that message is wrong in a way that will keep them from reporting it.

For a feature whose entire purpose is preventing data loss, promising a backup that never happens
is the wrong failure direction. **Not a security hole** — it fails closed, 403 not 200.

**The fix is small:** make the three routes match the page gate (everyone except approver-only), so
anyone who can create a TSR can back one up, and stop describing a permanent 403 as temporary
(`error.requiresLogin` is already set for 401/403 and never used). The reason it shipped is the
reason this file records four times already: `tests/test_tsr_draft_sync.py` builds **two engineer
accounts**, so nothing exercised the affected users. Its owner-isolation test is good — it just
tests the wrong axis.

</details>

### The two from 2026-08-06 — both FIXED, kept for the mechanism

Both bugs found by the 2026-08-06 browser pass were fixed the same day, at the
owner's request — 1a in `v71`, 1b in `v72`. Both entries are kept below with their reproductions,
because each is a clean worked example of a defect class this project keeps meeting: a cache key
that is wrong rather than stale, and two modules that disagree about a payload key.

### ~~1a. The service worker runtime cache serves one account's export to another~~ — FIXED, `v71`

**Fixed the same day.** `/export_` requests are now network-only — matched **before** the
navigation branch, with no cache read and no cache write — and the worker was bumped to
`v71-export-network-only`, which is what actually repairs devices already holding a poisoned
entry, since `activate()` deletes every cache whose name is not the current pair.

**Verified in a browser, both halves.** Online: a superadmin's fetch returned the unredacted CSV
and wrote nothing to any cache; after logout and signing in as HR, the same URL returned the
**redacted** file. Offline — the half that was previously only inferred — with the server genuinely
stopped, no export entry existed in any cache and the request **failed** rather than serving
anyone's copy. `/timeline` still loaded from cache with the server down, so offline mode survived.

Three things worth carrying forward:

- **The ordering was the fix.** The Export button is `window.location.href = ...`, so it arrives as
  a **navigation**. Matched after the navigate branch it would have reached
  `fieldNavigationFirst()` — which caches every ok response and serves it back on network failure —
  so the leak would have survived on exactly the path a real user takes while looking fixed on the
  path used to demonstrate it. A test asserts the ordering by index comparison.
- **The scope test is "does the same URL return different content per role", not "is it a
  download".** All eight `/export_*` routes vary by role and none appears in any offline workflow.
  `/preview_tsr_archive` and `/download_tsr_archive` were deliberately left on `networkFirst`:
  a given file is either allowed or refused for an account, the content does not vary by role, and
  they are part of field use.
- **No fallback `Response` on failure, deliberately** — a synthetic body would be written to disk
  as the downloaded file.

The original reproduction is kept below, because it is the clearest worked example in this file of
a cache key being wrong rather than a cache being stale.

<details>
<summary>Original entry, retained for the mechanism</summary>

### 1a. The service worker runtime cache serves one account's export to another

**Reproduced end to end, online.** As superadmin `jonamar`, `fetch('/export_timeline')`; log
out; log in as an **HR** account; fetch the same URL — and receive the **unredacted** CSV,
containing job titles and equipment. Those are the exact two fields the HR role exists to hide,
and the exact leak `5278df2` fixed server-side.

Confirmed to be the service worker rather than the HTTP cache: `caches.keys()` shows
`/export_timeline` held in the `…-runtime` cache. The route matches none of the network-first
prefixes in the fetch handler (`/get_`, `/api/`, `/preview_tsr_archive`, `/download_tsr_archive`,
`/search_products`, `/search_clients`) and is not `/static/`, so a non-navigation GET falls
through to `staleWhileRevalidate`. **Logout does not clear the runtime cache.**

**Scope, stated precisely, because the two paths differ.** The real Export CSV button is
`window.location.href = '/export_timeline?offset=..&branch=..'` (`templates/timeline.html`), which
is `mode === 'navigate'` and therefore goes to `fieldNavigationFirst` — that is network-first, so
**online the button always returns a correctly redacted file**. But the same function writes every
successful response into the runtime cache and serves `exactCached` whenever the network throws.
The user-reachable form is therefore: shared device, HR user offline or server unreachable, same
`offset`/`branch` as the admin's earlier export. **That offline case is inferred from the code
path plus the confirmed cache entry; the online scripted-fetch leak is demonstrated.** Proving the
offline half needs a deliberate pass with the network genuinely down.

This is the item that **re-opens a section 5 decision** — see the correction there.

</details>

**The section 5 question it raised was answered on 2026-08-07: the cache is now cleared on
sign-out.** Fixing `/export_` fixed the route that was demonstrated; it did not answer the general
question, and the general answer is that authenticated pages should not outlive the session that
fetched them. See section 5, where the decision is recorded as reversed rather than deleted.

### ~~1b. Every provisional-leave failure reason is discarded before the user sees it~~ — FIXED, `v72`

**Fixed the same day, on the client.** Both sides were audited first: the three schedule endpoints
feeding `handleScheduleError()` — `/add_shift`, `/update_shift`, `/move_shift` — use `message`
exclusively, while `leave_feature.py` uses `error` throughout. The helper is the **adapter between
two modules with different conventions**, so it is where they get reconciled; changing the endpoint
would have made one leave route inconsistent with the rest of its own module. `scheduleErrorText()`
now reads `message` first, then `error`, so nothing that already worked changes.

Verified on screen, all three paths: a Sunday now says "The selected range contains no weekdays.";
plotting over an existing provisional says "The selected dates conflict with an existing schedule
or Leave Request."; and a free weekday still saves with its success toast — the control proving the
success path was not disturbed.

**Left as a possible improvement:** routing the 409 to `showConflictWarning()` would name the
conflicting request rather than describing it, but that function expects a schedule-collision
shape. Not bundled into a bug fix.

<details>
<summary>Original entry, retained for the mechanism</summary>

### 1b. Every provisional-leave failure reason is discarded before the user sees it

`handleScheduleError` reads `errorPayload?.message`, but **every** failure return from
`/api/leave-requests/provisional` sets `error`, never `message`. The payload also carries neither
`status: 'conflict'` nor `conflict`, so the conflict branch does not fire either and it falls to
the generic fallback.

Observed: plotting provisional leave on a Sunday returns
`400 {"error": "The selected range contains no weekdays."}` and the screen shows only
**"Action Needed — Unable to record provisional Leave."** Seven actionable reasons are lost this
way, including the most useful one — the 409, which returns `supersedable_provisionals` naming the
conflicting request, its number, type and dates. A superadmin plotting over an existing
provisional block is told it failed and given nothing to act on.

The success path reads `.message` and the endpoint *does* set `message` on success, which is why
this only shows on failure. The fix is one key, but check every caller of `handleScheduleError`
before changing the helper rather than the endpoint.

**Not a broken supersede, and this was nearly recorded as one.** Supersede fires on **approval of
the formal Leave Request**, not on plotting a second provisional, so the 409 is correct behaviour.
The `b5dd637` message naming both leave types lives on that approval path and was **not**
re-verified in a browser — it is server-side text the earlier review proved by calling.

</details>

**Everything else is closed.** The 2026-08-01 offline audit's five items all shipped
(`a01f2b6`, `515698f`, `f268397`, `ca00803`), and the four defects from the 2026-08-05 reviews
are all fixed and pushed.

**Fixed on 2026-08-05, and worth reading even though they are closed — each was live on
`origin/main` with a green suite:**

| What was wrong | Why the suite missed it | Fixed in |
| --- | --- | --- |
| **The regional admin could schedule Manila engineers**, which the code documents as forbidden. Fired with no toggle enabled — a pure regression | `can_manage_any_schedule()` is `is_admin_authorized or flag`, and `is_admin_authorized` **includes** the regional admin. Placed ahead of their narrower branch, it returned True first and the Cebu/Davao check never ran. **No test exercised the regional admin at all** | `54c4aaa` |
| **The HR CSV export returned what the calendar redacted** — job title and equipment, for a role built to see neither | `/export_timeline` builds its own cell text and never called the redaction helper. The test asserted a 200 and that HR personnel were excluded, never that the file was redacted. The fixture also had no product, so an equipment leak read as clean | `5278df2` |
| Ticking **HR Schedule View beside Can Approve Requests** was refused with a message naming two switches that were both off | The message was written before the rule was widened, and no test asserted its content | `79d2847` |
| The **provisional-leave supersede notice named neither leave type** — a superadmin who plotted Vacation Leave was told their record was replaced, not that it became Sick Leave | The type was captured into a variable used only for the `!=` comparison and never reached a message. The test asserted the notification existed, never what it said | `b5dd637` |

**Fixed before that, each of which blocked real work:**

| What broke | Cause | Fixed in |
| --- | --- | --- |
| Every TSR save failed with "Unable to assign the next TSR number" | `ensure_online_tsr_submission_table` never added `tsr_number`, so a live table predating that column raised "no such column" on every read | `0bb60e3` |
| "Selected schedule was not found" on a saved draft | Picker option identity came from the **array index**, so any list change renumbered every option and detached drafts | `e12a439`, then properly in `515698f` |
| A TSR could not be saved in weak signal | The offline branch was gated on `navigator.onLine === false`; a live radio with an unreachable server threw at the number fetch and queued nothing | `f268397` |
| Adding a schedule offline did nothing at all, silently | `saveShift()` runs from an inline `onclick` with no catch, so the rethrown network error became an unhandled rejection | `a01f2b6` |

---

## 2. Queued work

### Reimbursement Tracker — small things left deliberately, raised 2026-08-12

None of these blocks anything. They are recorded so they are decisions rather than oversights.

- **A failed paid-notification is invisible.** `send_email_with_attachments()` returns
  `(False, reason)` and never raises, and the send runs on a daemon thread, so a dead Brevo key or
  an unreachable provider shows up **only in the Railway log** under
  `[EMAIL] Reimbursement Tracker paid notification`. Diary's on-screen warning covers *"this
  engineer has no address on file"* and nothing else. **"No warning" means "we had an address and
  tried", not "it arrived"** — do not let anyone read it as delivery confirmation. Making delivery
  visible means a status column and a synchronous send, which is its own task.
- **The paid email omits the Office and the reimbursement description.** It carries engineer,
  reference, control number, total and transfer date. The description — *"Toll and parking"* — is
  the most human-readable identifier and is the obvious thing to add if an engineer asks "which
  one?".
- **The suggestion chips measure 4.55:1 in light mode**, against the 4.5 AA floor for 11.5 px bold
  text. Passing, with 0.05 to spare. Dark mode is 6.72:1. Worth a nudge if anyone reports squinting.
- **Re-ticking Paid in Full re-sends the email**, by the owner's decision on 2026-08-12: a
  correction is real news because the amount may have changed. An accidental untick-retick therefore
  duplicates the mail. The alternative — notify once ever — needs a `paid_notified_at` column and
  leaves an engineer uninformed when a corrected amount is re-marked paid.

### Analytics needs a real print button, and a print layout worth printing — raised 2026-08-09

**The owner previewed it and it failed:** *"print preview looks bad. we should add a proper print
button."* This closes the "never print-previewed" row that sat in section 3 for two sessions — it
has now been previewed, and the answer is that the print block does not do its job.

**What the owner's preview actually showed**, from the screenshot, because these are the specific
faults to fix rather than "make it nicer":

- **Six sheets of paper** for a page that is mostly four numbers and two tables.
- **Each KPI is a full-width box with a huge empty right-hand side**, so Total / Active / Open /
  Completed consume most of page 1 on their own. They want to be a compact row or a small grid.
- **The browser's own headers and footers are printing** — the date and time, `MEDICAL SERVICE -
  Management System`, the full `https://web-production-…/analytics_page` URL and `1/6`. Those are
  the browser's default margins boxes, not ours, which is a large part of why it looks unfinished.
- The chart data tables print correctly, which is the part that already worked — `@media print`
  hides each SVG and reveals its `.analytics-chart-table`. **Keep that.** The defect is layout and
  density, not the table substitution.

**Two separate pieces of work, and they are worth not conflating:**

1. **A real Print button on the page**, so printing is a deliberate action rather than Ctrl+P. It can
   set up the view before calling `window.print()`.
2. **A print stylesheet that produces a report**, not a screenshot of a dashboard: KPIs on one row,
   page-break control so a chart's table is not split mid-way, and the scope line (date range,
   branch, counts) printed once at the top where a reader needs it.

**The browser header/footer cannot be removed by CSS.** No stylesheet can suppress them — that is a
browser print setting the user controls. What a page *can* do is stop competing with them: set a
sensible `@page` margin so the content does not collide, and put the report's own title, date range
and scope at the top of the first page so the browser's version is redundant rather than the only
label. Do not promise the owner that the URL and page numbers will disappear; they will not unless
they untick "Headers and footers" in the print dialog.

Cheap, self-contained, and entirely verifiable from a print preview.

### ~~System backup: streaming and worker count~~ — WORKER COUNT FIXED, STREAMING DECIDED AGAINST, `d28483d`

**The blocking half is fixed.** `Procfile` is now
`gunicorn --worker-class gthread --workers 1 --threads 8 --timeout 180`. A backup no longer blocks
every other user, and gthread runs the arbiter heartbeat **in the accept loop rather than the
request**, so a slow build can no longer have its worker killed — that, not the raised timeout
number, is what actually closes the timeout risk.

**Threads rather than a second worker process, deliberately.** Two processes would contend on the
same SQLite file with the 60s busy timeout that exists for exactly that reason; threads share one
engine and connection pool and cost far less memory. A test pins `--workers 1`, because "more
workers is better" is the obvious wrong optimisation here.

**Streaming is now a decision, not a queued task — see section 5.** It was prototyped rather than
assumed, and it works; it is simply the wrong trade at 39 MB / 3.6 s. Do not re-raise it without
reading that entry first.

### The Edge session loss — diagnosed, not fixed, and mostly not ours

The owner reported that a bookmarked `/timeline` opens fine on Chrome but redirects to login on Edge
for the same previously-signed-in user. **Nothing server-side explains it.** All three cookies are
persistent and refreshed each request — `medical_service_session` (30 days, `session.permanent`),
`medical_service_remember_token` (30 days), and the signed `medical_service_pwa_login` restore
cookie built for exactly this — and `login_manager.session_protection = None` means a changed IP or
user-agent will not invalidate them. For Edge to bounce, **all three had to be gone**.

**The unifying insight, and the reason this sits next to the vanished-draft report:** whatever
discards cookies also discards IndexedDB. The lost session and the lost TSR draft are very likely
**one cause, not two bugs**. Three candidates, each of which wipes both together:

1. **Edge "Clear browsing data on close"** (`edge://settings/clearBrowsingDataOnClose`), often set by
   enterprise policy — which would explain why Edge and not Chrome on the same machine.
2. **A different origin** — the bookmark pointing at a different scheme/host/port than where they
   signed in. Cookies are host-scoped, IndexedDB is origin-scoped; the page looks identical.
3. **A different Edge profile**, which has its own cookie jar and its own storage.

To tell them apart: compare the exact address-bar origin against Chrome's, check that settings page,
check the profile avatar, and in DevTools → Application → Cookies note the three cookies and their
expiry before shutdown — if they are gone afterwards while the dates were still future, something
cleared them. **If it is clear-on-close, staying signed in is not fixable in code** — the browser has
been told to forget the site.

**~~One genuine papercut that IS ours:~~ FIXED in `2e3c2d1`.** `/login` ignored `next` entirely, so
a bookmarked `/timeline` bounced to sign-in and then landed on the dashboard. It now honours the
target, validated by `resolve_safe_next_target()` — local paths only, rejecting schemes, hosts,
protocol-relative `//evil.com`, the backslash variant `/\evil.com`, control characters and over-long
targets, plus `/logout` and the auth pages as destinations. **That validation is the whole risk of
the change**; without it the fix would have traded a papercut for an open redirect.

The round trip is covered end to end because it is the only thing that sees Flask-Login's actual
`next=%2Ftimeline%3Foffset%3D2` encoding — if that format ever changes, every source-level assertion
stays green while every user silently lands on the dashboard again.

**This does not fix the Edge session loss**, which is the item above and is still almost certainly
browser-side. It only means that when a user *does* get bounced, signing in returns them.

### ~~LPR continuation pages now carry a signature on every page~~ — ANSWERED and SHIPPED, `29b2b9e` / `ca4cacb`

**The owner's answer was not "remove the signatures" but "make the pages belong together":** *"we can
add a page number with the lpr number so that each page won't come off as an individual page."*
Every page now carries `LPR-<no> - ITEMS <a>-<b> - PAGE <n> OF <N>`, including page one, which
previously had no marker at all.

**The total is the part that does the work.** `PAGE 2` says where you are; `PAGE 2 OF 3` says whether
one is missing — which is the actual risk when every page is a complete signed form and any single
sheet reads as a fully approved requisition. Single-page LPRs say `PAGE 1 OF 1` so the marker's
absence never has to be interpreted.

**Printed and confirmed by the owner on 2026-08-09: *"LPR printing is good."*** That also closes the
"enlarged signatures on a real printed page" row that had been open in section 3 since `8d97b58`.

**One consequence worth carrying, recorded in `plans.md` as a correction:** no LPR PDF is stored
anywhere — all eight call sites build it on demand — so **every existing LPR now shows the marker
when re-downloaded** and no longer matches the copy filed at the time. Already-sent procurement
emails hold frozen attachments and are unaffected. Left deliberately, since the change is additive,
but it may be worth telling whoever files them so a difference is not read as tampering.

The original entry is kept below because its rendering measurements are still the reference for how
continuation pages were verified.

<details>
<summary>Original entry, retained for its measurements</summary>

`d5e6d60` rebuilt continuation pages on the official template. Verified by rendering a 20-item LPR:
**3 pages, items 1-8 / 9-16 / 17-20, none missing, none duplicated**, and the AcroForm flattening
works as documented (page 1 keeps its 53 widgets, continuation pages have 0).

But the requester and approver signatures now appear on **every** page — 2 signature-shaped images
on all three. The old hand-drawn continuation pages carried none. It is defensible, since each page
is now a complete official form with its own signature lines, but on a 3-page LPR the approver's
signature appears three times, and that changes what leaves the building. **Ask the owner before
treating it as settled.**

</details>

### ~~P.O. reporting on the Analytics page~~ — BUILT in `45da21c`, reviewed in `34f60b9`

**Done, and the whole Analytics page was upgraded with it** at the owner's request:
*"P.O analytics. but let us also upgrade the whole analytics page."* The plan is in `plans.md`.

The open question this entry flagged — *who sees P.O. reporting, given `/analytics_page` gates on a
different flag from `po_admin_access`* — **was decided and is worth not relitigating**: the panel
shows to `can_view_admin_reports() or can_manage_purchase_orders()`, but through a **separate
`/get_po_analytics` endpoint**. `/get_analytics_summary` stayed on `can_view_admin_reports()` alone,
because it returns engineer names, branches and per-engineer workload that a P.O.-only manager must
not receive. The sidebar needed a **third branch**, not a widened one, because its existing
condition wrapped Analytics and TSR files together.

Also resolved from the notes that used to live here: the unescaped-label problem is gone, and not by
escaping. The charts are now inline SVG built with `createElementNS` + `textContent` via one
`svgElement()` helper, so injection is structurally unreachable rather than escaped by discipline.
There is still **no charting library**, and adding one was declined — it would not inherit the theme
tokens, would be invisible to screen readers, and would print as a bitmap.

`analytics_date_bounds()` is reused unchanged, and the `purchase_order` indexes from `b01c78c` serve
the grouping as expected.

### ~~Create TSR on a schedule that has not synced yet~~ — BUILT in `28ba1b0`

**Done.** An engineer taps Create TSR on a queued schedule card, writes the TSR offline, and
both queue. On reconnect the schedule syncs first, and the TSR behind it is rewritten to the
real shift id before it is sent. Multi-day chains file against the shift matching the TSR's
service date. If the parent schedule is removed, the TSR is kept and asks for a new schedule.

**Correcting what the section below claimed, because it sent readers somewhere that did not
work.** It said the workaround was a standalone TSR from the sidebar, "fully offline already".
That was never true: `/offline-tsr` disables every field until a schedule is selected
(`updateCreateTSRScheduleGate`), and the picker's sources never contained a queued schedule.
There was no way to write a TSR against a queued schedule at all. The original text is kept
below because the two refusal points it cites are still the right places to look.

<details>
<summary>Original entry, retained for its references</summary>

### Create TSR on a schedule that has not synced yet — TO BE PLANNED

**Raised by the project owner on 2026-07-31 while walking through the field workflow. Agreed
to plan it later rather than bolt it on.** Not a defect — the current behaviour is deliberate
and fails cleanly — but it leaves the field sequence half-solved.

**The workflow that exposed it.** An engineer with no signal opens the calendar, finds no
schedule for today, adds one offline, does the work, and then wants to write the TSR on site
while the details are fresh. He cannot. He must wait for signal, let the schedule sync, and
only then create the TSR.

**Why it is blocked, in both places** — verified, not assumed:

- The schedule card's Create TSR button is gated on `shift?.id`
  (`templates/timeline.html:10043`). A queued schedule has no server id, so the button renders
  **disabled**, labelled "Create TSR unavailable".
- The shift modal's Create TSR button calls `openOfflineTSRDraftFromShiftModal()`
  (`templates/timeline.html:18419`), which reads `f-id` first and refuses with "Open an
  existing saved schedule first before creating a TSR."

Both refuse with a clear message rather than breaking, which is why this is a gap and not a
bug.

**The working path today, and it is worth telling engineers about:** open **Create TSR** from
the sidebar and write a **standalone** TSR. That is fully offline already. It simply is not
linked to the queued schedule, so someone reconciles them afterwards.

**Why this needs planning rather than a quick fix.** A TSR must reference a real shift id, and
a queued schedule has none until it syncs. Making this work means **dependent queue items**:
the schedule syncs first, receives its id, and the TSR queued behind it is rewritten to point
at that id before it is sent. That brings its own questions — ordering, what happens when the
schedule parks as a conflict and the TSR behind it is orphaned, and whether a standalone TSR
should be retro-linked instead. `9a2ad4d`'s creation token is the right precedent for the
identity half, but the dependency half is new.

Worth deciding first, before any code: **should the TSR wait for its schedule, or should it be
created standalone and linked afterwards?** Those are different features and the second may be
most of the value for far less risk.

*(Decided: the TSR waits for its schedule. Built in `28ba1b0`.)*

</details>

### ~~`/get_recent_activity` and `/get_engineer_dashboard_summary` have zero callers~~ — REMOVED, 2026-08-07

**Both retired**, with their entries in the perf-log path list, after confirming no reference in any
template, script or test. The comment in `static/js/app-dashboard.js` that recorded the pending
decision was updated rather than left describing a route that no longer exists, and no helper was
orphaned by the deletion — each was checked for remaining callers.

**The distinction that made this safe is now pinned by a test, because it nearly went the other
way.** `/activity_page` carries its own loader against **`/get_activity_logs`** — plural, a
different endpoint — and an earlier plan assumed that was the same route. `RetiredDashboardRouteTests`
asserts both that the two dead routes are unregistered and that `/get_activity_logs` still is, so
deleting one can never take the other with it.

### ~~Mobile tap target: `.dashboard-metric-link` is 25 px tall~~ — ALREADY FIXED, confirmed 2026-08-07

**This entry was stale, not the code.** `.dashboard-metric-link` carries `min-height: 44px`
(`app-dashboard.css:1222`); the fix landed inside the Analytics upgrade, which listed it as step 8,
and the entry here was never struck through. **Re-measured on a real 375 px viewport: 44 px**, at the
same 12.16 px font size the original 25 px measurement cited, with the strip not scrolling and no
page overflow.

Only the `engineer-summary` strip was re-measured — the other two need an account that renders them —
but `min-height` sits on the shared class rather than any one caller, which is what the original
entry established.

**~~Four other controls do measure under 44 px at 375 px~~ — FIXED, `d28483d`, and the note below
was wrong twice.** All are now **44×44**, measured at 375 px: skip link, both changelog bells, both
appearance buttons, and the `.toggle-btn` hamburger. Sidebar header overflow 0, page overflow none.
Desktop re-measured and **unchanged** at 34/34/32 — the rule is scoped to `max-width: 768px`,
because these are compact by design where the pointer is a mouse and the sidebar is only 240 px.

**Two corrections to what was written here, both of which read as reassuring:**

- **The `.toggle-btn` was never unlabelled.** It carries `aria-label="Hide navigation"` and did at
  the time this was written. Whoever wrote it inferred the missing label from the icon.
- **It missed two controls entirely** — both appearance buttons, which were already 44 px *tall* and
  only 34 px and 42 px *wide*. **A target is 44×44, not 44 in whichever direction is convenient.**
  A height-only audit finds four; a height-and-width audit finds six.

`.sidebar-header` now wraps at mobile: the title plus three 44 px controls came to **253 px of
content in a 240 px sidebar**, and without wrapping flex shrinks them straight back under the
minimum the rule exists to enforce.

**Observed while measuring, not fixed:** the `.sidebar` element reports **38 px of horizontal
overflow at 375 px**. Confirmed pre-existing by neutralising the new rules and re-measuring —
identical 38 px with and without them — and no descendant is wider than the sidebar, so it is
likely padding or a scrollbar artifact in the off-canvas drawer. Unrelated to tap targets and
deliberately left out of that change.

### ~~What's New — digest: real audience send~~ — SENT, 2026-08-07

**Closed. The owner sent the digest to the real audience and reported it on 2026-08-07.** All three
steps of the sequence are behind us: the recipient count was the safeguard, the self-test went on
2026-08-05, and the real send has now happened. `CHANGELOG_DIGEST_ENABLED` is `true` on Railway and
the feature has been deployed since `0447392`.

That also closed what section 3 previously listed as unverified: the digest HTML had only ever
been seen in the preview pane, never in an inbox, and mail clients strip and rewrite CSS. It
has now been rendered by a real mail client and delivered to a real audience.

**What the record does not contain**, the same gap as the barcode scanner below: the outcome is the
owner's, reported directly. The resolved recipient count at send time, which audiences were chosen,
and whether every intended recipient received it were **not captured here**. If someone reports a
missing digest later there is no recorded baseline to diff against.

**The limitations below still apply to the next send, and one of them matters more now that a real
send has happened: there is no idempotency, so pressing send again sends the same digest again** to
people who have already received it.

Expect the resolved count to be **higher** than "accounts with a profile email":
`get_user_email_for_notification()` ends in a hardcoded username-to-email map (`diary`,
`hanna`, `kevin`, `jonamar`, `robert`, `rodito` → `@shimadzu.com.ph`), so those accounts
resolve regardless. Accounts with no resolvable address are listed by name in the modal.

**Known limitations, accepted rather than fixed:**

- **No idempotency.** Pressing send twice sends twice.
- **No unsubscribe.**
- The digest is **the latest 5 releases**, not per-recipient unread — someone who has read
  everything still receives a full digest. Making it per-recipient is considerably larger
  work and is deliberately separate.
- **No scheduled or recurring delivery.** Manual only, by design.

Both send paths remain available: audience mode (default) and the Settings-managed
*What's New Announcements* group. Naming a group without a mode still means the group, so an
explicit group send cannot be silently widened to the whole audience.

**Note:** the changelog carries entries up to `sort_order: 180` under the `2026-07-29` release
covering all four dashboard phases, plus a `2026-07-30` release with five entries for the
hybrid ratification. All are `is_published: true` and every one of the 2026-07-30 items is
`audiences: ["admins"]`, so a digest sent to engineers will not include them. A digest sent now
includes everything above.

### ~~Stock inventory barcode scanner~~ — VERIFIED CLEAN, 2026-08-05

**Closed.** Open since the 2026-07-26 handoff: the physical scanner had arrived but had never
been driven against production behaviour. **The owner verified it on 2026-08-05 and it passed
clean. No code change was made and none was needed.**

**What the record does and does not contain.** The outcome is the owner's, reported directly.
The per-item detail the section below asked for — scanner model, the exact scanned string,
whether it sends Enter/CR, the browser used — **was not captured**. So if the scanner
misbehaves later there is no recorded baseline to diff against, and the investigation starts
from the watch-list rather than from known-good values. Worth capturing those the next time
someone has the hardware in hand.

The original checklist is kept below rather than deleted: it came from the 2026-07-26 handoff,
it is the fastest route back into this if a regression appears, and none of it is invalidated
by a passing run.

<details>
<summary>Original entry, retained as the investigation checklist</summary>

### Stock inventory barcode scanner — pre-dates this session

From the 2026-07-26 handoff and still open. The physical scanner arrived but has never been
validated against production behaviour.

Collect before changing any scanner logic: scanner model, the exact scanned string, whether
it sends Enter/CR, the browser used, whether one physical scan opens one modal, whether
focus returns after save or cancel, and any exact API error.

Watch for: no Enter/CR suffix, the barcode field losing focus, rapid scans opening duplicate
modals, stripped leading zeroes, one scan producing duplicate events, branch context not
retained, focus not returning to the scan input after a modal closes.

Reproduce with keyboard input locally first.

</details>

### Spend reporting — deferred by decision in phase 3

Every approval model stores an amount and an `approved_at` date, but **nothing aggregates
money across documents** — no total by month, branch or engineer, and no `group_by` anywhere
in the codebase buckets by date.

Deliberately deferred as its own task because of three real pitfalls: `ReimbursementHeader`
has **no amount column** (totals must sum `ReimbursementRow.row_total`), travel mixes PHP
and USD via `currency_code`, and `LPRHeader` rows with `parent_module IS NOT NULL` are
embedded children that would double-count.

Note the old *Billing Visibility* panel was **not financial** — it string-matched shift
status, title and TSR **filenames** — and was removed in phase 3 for that reason. Do not
resurrect it as a money proxy.

---

## 3. Not yet verified

None of this is known broken — it simply has not been checked. **One item here is a known
deviation rather than an unknown, and it is listed first.**

### ~~Analytics charts scroll horizontally at 375 px~~ — FIXED, `v77`

**Fixed on 2026-08-07.** Both renderers now measure the frame and draw 1 user unit = 1 CSS px, which
is what the approved plan specified. Verified at 375 px: no frame scrolls sideways, no page overflow,
and rendered width equals the `width` attribute equals the `viewBox` on all three charts. Re-measured
at three container widths and the chart matched its container each time.

Two things worth carrying forward. **The `min-width: 560px` was a brace, not the bug** — it existed
to stop the fixed `viewBox` scaling `<text>` to ~6 px, so removing it alone would have traded a
scroll for unreadable labels. And **SVG has no `text-overflow`**, so measuring made label truncation
mandatory: an untruncated branch name draws over the bars. The full text stays in the row `<title>`
and the hidden data table.

**~~One thing in this fix is NOT verified~~ — CLOSED by the owner on 2026-08-09:** *"charts are good
even when dragging the window."* The debounced `ResizeObserver` redraw could not be observed from
here at all — the Browser pane does not composite the page, `requestAnimationFrame` never runs in
it, and a control observer on the same node did not fire even the initial callback the spec
guarantees, because both are driven by the rendering steps. The measurement logic was proven at
three widths by re-rendering directly; only a real browser could ever prove the observer fires.

**Worth keeping as a pattern:** this sat open for two sessions purely because the tooling here
cannot run a browser's rendering loop. When something is *structurally* unverifiable rather than
merely unchecked, say so plainly and hand it to whoever has a real browser — it will not resolve
itself with more effort on this side.

### Verified on 2026-08-07 — five rows closed off this table

Driven against a throwaway database at 375 px and desktop. Measured geometry and computed style,
not screenshots; the pane still does not composite.

| Item | Outcome |
| --- | --- |
| **Offline with the server genuinely stopped** | **Pass**, and this was the oldest item here. With the process killed, `/timeline` reloaded from cache with its calendar, the dashboard rendered with all six static assets from cache and none failing, the changelog button was present, and `window.offlineSchedule` was live — the exact regression the `?v=` fallback exists to prevent. The signed-out `/login` shell served with its password field intact. Note an uncached API GET resolves **200 with the `/offline` HTML**, not a rejection, so a caller doing `res.json()` gets a parse error rather than a clean offline signal — see the new observation in section 6 |
| **The two-tab race** | **Pass on the outcome, with a correction to the premise** — see below |
| **Engineer read-only stock inventory, in a browser** | **Pass.** Page and the **Currently Borrowed Items** panel both render at 375 px, no page overflow, and **no write control is visible** to the engineer — Register / Record Movement / Edit / Reverse exist only as modal headings with no reachable trigger. Complements the API result (reads 200, all four writes 403) |
| **What's New filter/search row at 375 px** | **Pass.** `.changelog-filters` does not scroll, nothing extends past the viewport, and **every control measures exactly 44 px** — search, category select, Acknowledge All, Refresh, Got It, Previous/Next |
| **P.O. Details in dark mode** | **Pass.** Every panel, filter and KPI surface goes dark with high-contrast text; no white slab; no overflow at 375 px. **Edge and Brave remain unverified** and stay on the list below |

**The two-tab race, stated precisely, because the item asked the wrong question.** It asked whether
"the single-flight guard holds". It cannot: `syncInFlight` (`app-offline-schedule.js:32`) is an
in-memory, **per-tab** variable, so two tabs have two independent guards and nothing in the client
coordinates them. What was observed and what actually protects the data:

- Both tabs see the same queue — it is IndexedDB, shared across tabs.
- In practice only one tab sent, twice over. Background-tab timer throttling serialised the two
  `online` handlers, and the second tab then re-read the shared queue, found the item already
  gone, and sent nothing. That is real browser behaviour, but it is **luck, not a guarantee**.
- **The guarantee is server-side.** Two genuinely concurrent `POST /add_shift` with the same
  `creation_token` — both in flight before either resolved — **both returned shift `82`**, and the
  database holds exactly one row for it. A `GROUP BY creation_token HAVING COUNT(*) > 1` across the
  whole table returns nothing.

So the answer is: exactly one schedule per queued item, guaranteed by the creation token rather
than by the client guard. **Do not "strengthen" the client guard and consider this hardened** — the
token is what makes it safe, and it is what a second device, a refresh mid-sync or a retry relies on
too.

### The rest

| Item | Applies to |
| --- | --- |
| **Reimbursement totals against real data** | `aff9001` changes which number appears on the PCV, RFP, Excel and ZIP. Verified against fixtures and a smoke case, not against a real reimbursement with attachments |
| **Microsoft Edge** | every dashboard phase, login redesign, sidebar, What's New, digest modal, P.O. Details, Analytics. **Narrowed on 2026-08-09: Brave is closed**, because the owner uses it daily, so everything shipped has been used there. Edge is the remaining gap and is not idle — the session-loss report in section 2 came from Edge |
| **Skip link visual reveal on real keyboard focus** | layout shell. Structurally unverifiable from here: the pane never advances transitions and its window is never focused, so `:focus` never matches |
| **Offline schedule attachments from a real device camera** | the least-proven part of `709106c` — see below. **Now the largest genuine risk left in this file**, since the browser block has shrunk to Edge alone |
| **The provisional-leave supersede notice, in a browser** | `b5dd637` names both leave types on the **approval** path, which the 2026-08-06 pass did not reach — see section 1b |
| **The new TSR draft 403 message, on screen** | `2e3c2d1` separates a permanent 403 from an expired 401 from a real connection failure. The wording is asserted by test and was never *seen*. Reaching it now needs an approver-only account, since every other shape is permitted — which also means this is a low-frequency path worth checking once rather than watching |
| **Analytics keyboard pass** | the filter is a real `<form>` with `Apply` as `type="submit"`, headings run `h1`→`h2`→`h3`, and the scope/error regions are `role="status"` / `role="alert"`. Structure was verified; a full tab-through with visible focus was not |
| **A Paid in Full email actually arriving** — added 2026-08-12 | The whole chain is proven *except* the last hop. Verified by running: the transition fires once, the engineer is on `To`, the CC group is on `cc`, and the body carries the right fields — with the provider **replaced by a capture**. No message has been through Brevo to a real inbox. Send one to yourself first: add your address to `reimbursement_tracker_paid_cc`, tick a row, and check the log line |
| **The `JP → JOP` correction applying in production** — added 2026-08-12 | Proven in tests and against a seeded copy, both anchored on `employee_id 00021`. It runs on the first request after deploy. **The live database still reads `JP` here**, so nobody has yet seen it apply for real. One glance at Personnel after the deploy closes this |
| **The Accounting export opened in Excel, not openpyxl** — added 2026-08-12 | The layout is asserted by test and by a read-back: one header row, seven columns, and a Total that is a number rather than a formula. **Diary has not opened one.** She is the only consumer, and the reason for the rewrite was that the old one carried too much — worth one look before she relies on it |

**Everything below was added on 2026-08-12 with the machine-scoped P.O. work. All five are now
owner tasks rather than deferred ones**, because browser verification is no longer available here —
see the rule at the top of this file.

| Item | Applies to |
| --- | --- |
| **The P.O. Add/Edit modal has never been opened in a browser** | The single largest gap in this feature. Part B got a browser pass; **Part A did not** — its journal records only `unittest`, `py_compile` and `git diff --check`. Every behaviour is proven by the test client. What that cannot prove is the interaction itself: that the client box searches, that the equipment box stays **disabled** until a client is chosen, and above all **that picking a machine and then changing the client clears and re-scopes the machine**. That last one is where a design like this usually breaks |
| **The dark-mode fix is proven by arithmetic, not by eye** | The token now resolves and the contrast computes to 12.91:1, and a repo-wide test stops it regressing. **Nobody has looked at the dropdown in dark mode.** The arithmetic is strong evidence — stronger than a screenshot for contrast specifically — but it says nothing about whether the hover state looks right |
| **The equipment picker at 375 px** | The modal gained `modal-dialog-scrollable` and a `max-height` in the same change. Section 6 records that a `.modal.fade` measures zero on every child in the pane, so this was never measurable from here even before the browser rule |
| **`[DB MIGRATION] Added purchase_order.product_serial` in the production log** | It runs on the first request after deploy and was pushed on 2026-08-12. Confirm it appears **exactly once**, that nothing appears on restart, and that the P.O. row count is unchanged either side |
| **The Equipment tab against real data** | Verified against fixtures with `linked + unlinked == total`. **The tracked local `scheduler.db` holds 0 purchase orders**, so from here the tab reads 0/0 and proves nothing. Check what the production register actually holds — see the row below, which turns on the same question |
| **Whether any legacy P.O. rows exist at all** | The whole legacy-row design — readable without a machine, required on edit — assumes rows predating the change. **Locally there are none: 0 P.O. rows, and the `product_serial` column has not even been created yet** because the migration runs on first request. If production is also near-empty, that machinery is correct but unexercised, and the "Missing a machine" worklist will simply be empty. Worth one query before anyone treats an empty list as a bug |

**Added 2026-08-13 with the multi-machine change.** The modal row above got **larger**, not smaller:
it now carries a chip list as well as the combobox, and still nobody has opened it.

| Item | Applies to |
| --- | --- |
| **The machine chips inside the scrollable modal** | The one risk the plan accepted knowingly. The modal is `modal-dialog-scrollable` with `overflow-y: auto`, and an absolutely-positioned dropdown inside a scrolling body can clip at the edge. The existing `.search-results` was chosen **because** it is already proven in that container rather than porting the travel checklist, which has never run inside one — but "already proven" was reasoning, not a look. Check six or more chips wrapping, and that the suggestion list is not cut off |
| **The "+N more" cell at real column width** | The register shows the first machine plus a count, with the full list in a `title` tooltip, specifically to keep row height stable. Whether `SN-1234 — CT-500 +2 more` actually fits the column on a laptop is unmeasured |
| **The export opened in real Excel** | Machines are joined with `'\n'` inside the existing Machine Serial / Machine Name cells, relying on `wrap_text=True` to stack them and on rows auto-heighting. `openpyxl` round-trips prove the string; only Excel proves the rendering. **Diary is the consumer** |
| **The Equipment tab with five metric tiles** | A fifth tile (`machine_link_total`) joined a grid built for four. Whether it wraps cleanly at desktop and 375 px is unchecked |
| **`[DB MIGRATION]` for `purchase_order_machine` in production** — the one that matters most | The new table and its **backfill** run on the first request after deploy. Verified locally: three consecutive `ensure_purchase_order_schema()` runs seed exactly one link from a legacy row, and `PRAGMA index_list` shows the unique pair index physically. **In production, confirm the row counts either side**: P.O.s with a non-blank `product_serial` before must equal `purchase_order_machine` rows after, and a `LEFT JOIN` on both id and serial must return zero unmatched rows |

**Added 2026-08-14 with the tracker batch work and the register fixes.** The first row is the one
that touches real money.

| Item | Applies to |
| --- | --- |
| **The BATCH-032 normalization against real tracker rows** — the highest-stakes unverified item in this file | It rewrites `reference`, `batch_sequence` **and `control_number`** on every existing row, on the first request after deploy. Locally the tracker holds **0 rows**, so the rewrite has never run against real data — only the refusal path was exercised (a row lacking initials aborts the whole transaction and writes no marker). **Count rows before and after, confirm the `[DB MIGRATION] Initialized shared reimbursement batch state and normalized N tracker row(s)` line appears exactly once, and nothing on restart.** See the first row of the waiting-on-owner table |
| **The toasts, in a browser** | Fixed-position confirmations replaced the scroll-to-top on both registers. Contrast is proven by arithmetic — body 12.91:1 in dark, every tone bar and icon ≥3:1 in both themes, all pinned by a test — but **nobody has looked at one**. Specifically unchecked: that a toast does not cover the modal's Save button on a phone, and that several stacked toasts behave |
| **The register export opened in real Excel** | The seven-column file now ends with a literal TOTAL row in F/G, outside the autofilter range. `openpyxl` proves the values and the range; only Excel proves it *looks* like a total and that sorting cannot drag it into the data. **Diary is the consumer** |
| **The whole batch workflow used by Diary once** | Start a batch, file rows into it, switch to a historical batch, export each. Every piece is covered by the test client, but the workflow has never been driven end to end by the person whose job it is. The first real transition is also the first time "Start new batch" is pressed against live data |
| **The Analytics default range change** | Analytics now opens on 2026-05-18 → today instead of month-to-date. The Reports page still opens on month-to-date and has its own client-side default, so **the two pages now disagree about what "default" means**. Nothing is broken — neither UI reaches the server default — but a manager comparing them will see different numbers for what looks like the same view. Worth a decision rather than a discovery |

**Closed by the owner's 2026-08-09 pass**, listed so nobody re-opens them from an old copy of this
file:

| Item | Outcome |
| --- | --- |
| ~~The whole TSR draft round trip, on a real browser~~ | **Pass.** *"tested TSR draft. it does not disappear."* This was the one test that proved the feature does its job |
| ~~The enlarged signatures on a real printed page~~ | **Pass**, via the LPR print — *"LPR printing is good."* Open since `8d97b58` |
| ~~The 44 px shell controls on a real phone~~ | **Pass.** *"sidebar on mobile looks good now"* — the wrapped header reads correctly |
| ~~The `ResizeObserver` redraw on Analytics~~ | **Pass.** *"charts are good even when dragging the window."* This was structurally unverifiable from here — the pane never runs the rendering steps — so only a real browser could ever close it |
| ~~Brave~~ | **Covered by daily use**, not by a pass |
| ~~The Analytics print view~~ | **Previewed, and it FAILED.** Now queued work in section 2 rather than an unknown |
| ~~The backup download end to end from a browser~~ | **Clicked, and it FAILED.** Now bug 2a in section 1 |

### ~~The 2026-08-05 features were proven by calling, not by using~~ — DONE, 2026-08-06

**All six were driven through a browser** at desktop and, where it mattered, 375 px. This was the
largest unverified block in the file. **Five passed.** The pass found the two bugs now in section 1.

Screenshots were unavailable — the Browser pane does not composite frames — so verification used
the accessibility tree, real click handlers, and measured geometry (`getBoundingClientRect` /
`getComputedStyle`). **For tap targets that is stronger evidence than a screenshot**; for pure
visual polish it is weaker, and that limit is why the dark-mode and other-browser row above stays open.

| Feature | Outcome on a real viewport |
| --- | --- |
| Schedule-card TSR previews | **Pass.** Details lists only the recognised TSR and counts the other attachment separately, so photos are not presented as service reports; the link opens the right PDF; 66 px rendered on `min-height: 44px`; at 375 px the lite sheet shows the same list and **View Files opens no modal** — the Edit-modal workaround is genuinely gone |
| HR schedule viewer | **Pass on screen**, but see section 1a. Sidebar stripped to Calendar + Password Settings, calendar redacted, five routes 403, the Details popover carries no attachments section. Its Edit/Delete/Send TSR buttons render but are `disabled` — cosmetic, not a hole |
| Staff types on Add Personnel | **Pass.** Engineer / HR / Approver each show and hide the right fields; creating an HR account gave an accurate message. The `79d2847` refusal is reachable from Settings → Approval Routing, not the modal, and names "Can Approve Requests" — the switch actually ticked |
| Grantable admin capabilities | **Pass.** Toggles persist; the grantee's sidebar gains Reports and Personnel. **`54c4aaa` holds**: as the regional admin with the branch filter on Manila, every row is View-only with zero Add/Edit/Delete, against a superadmin control showing those same rows editable |
| Request recall | **Pass.** Withdraw appears only on Submitted rows; empty reason refused client-side with **no network call**; with a reason the request went Submitted → Draft with the provisional block untouched; at mobile width all three buttons 44 px, no overflow |
| Provisional leave | **Works, but see section 1b.** Category → Leave reveals the type selector and notes; a Sick Leave block was recorded from the real Add Schedule modal |

**Two fixture traps nearly became false findings**, both failing in the reassuring direction:
`/export_timeline` joins `ShiftEngineer` while the calendar reads `Shift.engineer_id`, so a fixture
setting only the latter renders a full calendar and an all-`-` export — which reads exactly like an
over-redaction bug; and a long-lived Flask session held a stale SQLite snapshot, so rows inserted by
a separate process stayed invisible until the server was restarted, which reads exactly like a write
that silently failed. A third was pure measurement error: the sidebar's Reports and Resources groups
are **collapsed accordions**, so filtering nav links on `offsetParent !== null` hid them and made a
correctly-provisioned grantee look denied.

On the skip link: the Browser pane does not composite frames, so CSS transitions never
advance, and its window is unfocused so `:focus` never matches. Disabling the transition
proved the element positions correctly, but the actual reveal was never seen.

### Offline schedule attachments — verify on a real device before engineers rely on it

The attachment path in offline schedule creation is **implemented and stored, but was only
ever exercised through the queue's own code**. Every browser check drove
`window.offlineSchedule.enqueue()` with a hand-built `FormData` carrying no files. A photo
taken on a phone has never gone through it.

**Why this one is worth a deliberate pass rather than assuming it works:** attachments are the
heavy part of the queue and the most likely source of a storage-pressure bug on a field phone,
which is exactly the device this feature exists for. A schedule that silently fails to queue
because IndexedDB refused a 12 MB photo is worse than no offline mode, because the engineer
believes the work is saved.

What to check, on a real phone rather than a desktop browser:

- A photo straight from the camera — several megabytes, not a test fixture — queues, survives
  a reload, and still syncs.
- Several photos on one schedule, and several queued schedules each carrying photos.
- What happens when the device is genuinely low on storage. IndexedDB rejects the write; the
  engineer must be told the schedule was **not** saved, not left believing it was.
- The blob survives a browser restart, not only a page reload.
- After a successful sync the attachments are actually dropped from the device
  (`discard()` removes them), or the queue becomes a slow storage leak.

The TSR queue already stores attachments as blob references and has been through real field
use; if this needs rework, copy what `templates/offline_tsr.html` does rather than inventing a
second approach.

### Offline schedule creation — what is now verified, and what is still not

**Verified on 2026-07-31 in `bfacf8f`, by driving the real UI against a genuinely stopped
server** — not by calling the queue API and not with the network stubbed:

- `/timeline` reloads from the service worker with the server down.
- **Add Schedule opens**, populated from the device copy of the engineer list.
- The real form fills and **Save Schedule** queues the schedule, with the banner shown.
- It survives a reload, and syncs on reconnect, landing in the database with its token.
- Replaying the same token returns the same shift id rather than creating a duplicate.
- A genuinely conflicting schedule parks as "needs your attention" instead of double-booking.

Still not exercised:

- **Attachments from a real device camera** — the section above. Unchanged and still the
  largest gap.
- **The pre-check against a stale snapshot.** It was verified against a fresh one. The case
  that matters is an engineer offline for a week, where the snapshot is a week old and the
  warning may be wrong in either direction.
- **Multi-day chains through the device queue.** Replay of a five-day chain is covered by
  `tests/test_offline_schedule.py`, but a multi-day schedule has not been queued and synced
  from the browser.
- **A cold device with no HTTP cache.** `/get_engineers` was observed resolving **200 from the
  browser cache** even with the service worker's runtime entry deleted, so the IndexedDB
  fallback added in `bfacf8f` was proved by forcing the fetch to reject rather than by
  reproducing a naturally cold device. Worth confirming on a phone that has genuinely been
  closed for a day.

---

## 4. Committing here — standing rules

Work happens in this repository directly, so every commit is one step from deployment.

Standing checklist for any commit here:

- [ ] `git fetch origin`, then `git rev-list --left-right --count origin/main...HEAD` to
      confirm no divergence before anything reaches origin
- [ ] `git status --short`, then inspect the diff
- [ ] Stage **explicitly, file by file** — never `git add -A`
- [ ] `git diff --cached --check` for whitespace, and `--numstat` to confirm no accidental
      whole-file line-ending rewrite
- [ ] Re-read `origin/main` **after** finishing the work, not only before starting. `9a2ad4d`
      landed mid-session from outside and quietly replaced a service worker bump; the only
      thing that caught it was checking again at commit time
- [ ] Confirm the commit contents with `git show --name-only` before pushing
- [ ] Focused commit message; push `main`
- [ ] Confirm only known local artifacts remain dirty: `scheduler.db`, `output/`, `tmp/`,
      and the loose 2026-07-26 handoff document
- [ ] A user-facing change needs a `releases.json` entry dated the commit date, or
      `tests/test_changelog_coverage.py` fails the commit
- [ ] If the work makes a line in `Handoffs/` stale, **fix it in the same commit** — see below

**`Handoffs/` is tracked, changed by the owner on 2026-08-11.** Handoff documents are published
with the code rather than kept as local scratch, so they carry the same obligation as `changes.md`:
a stale line now travels to everyone who clones the repository.

**The reason this changed is worth keeping.** `Handoffs/08-11-26 handoff.md` confidently described
the System Backup download as the immediate priority, in detail, citing `response.call_on_close`
code that had already been deleted — because it was written by reconciling journals against each
other rather than against the tree. It was untracked, so the correction would have lived on one
machine while the wrong version was what any fresh session actually read. Tracking it means the
correction travels with the mistake.

**The loose `medical-service-sms-detailed-handoff-2026-07-26.md` at the repo root stays untracked.**
It predates the convention and is superseded; leave it alone rather than tidying it in.

**`scheduler.db` is tracked.** `.gitignore` lists `*.db`, but that only applies to
*untracked* files, so **gitignore does not protect it**. Exclude it by name at every step.
Same for `.env`, which holds a real Brevo API key.

**Bump the service worker cache** whenever an `APP_SHELL` entry changes, or field devices keep
the old copies. Tests use `assert_cache_version_at_least`, a **floor**, so a bump never breaks
them — do not pin an exact version in a test, which makes the required bump fail the suite.

**No current version is written here on purpose.** This line has gone stale twice and been
corrected twice, inside the very paragraph telling you not to trust notes. **Read the live value
out of `app.py` immediately before committing.** `v49` was claimed and then overwritten by a
`v50` bump from outside that session, and the stale assumption nearly shipped old dashboard
assets to field devices.

**What counts as an `APP_SHELL` change is wider than it looks.** `/timeline` is the first entry,
so any edit to `templates/timeline.html` qualifies — including CSS. `templates/layout.html` is
embedded in every shell page, so it qualifies too. One 2026-08-05 commit shipped a whole
capability without a bump, its journal asserting no `APP_SHELL` asset had changed; a cached
device would have had the permission and none of the buttons.

**Multi-line commit messages:** write them to a file and use `git commit -F <file>`. A
PowerShell here-string breaks on double quotes inside the message and silently reinterprets
the body as pathspecs.

**`Set-Content -Encoding utf8` writes a BOM** on Windows PowerShell 5.1. Rewriting
`static/js/app-dashboard.js` that way added a byte-order mark its sibling `app-changelog.js`
does not have — `node --check` passed and the browser ran it fine, which is exactly why it
almost shipped. Use `[System.IO.File]::WriteAllText($path, $text, (New-Object
System.Text.UTF8Encoding($false)))` for any file another tool reads, and check the first three
bytes are not `239 187 191` afterwards.

**Do not combine `[regex]::Escape()` with `Select-String -SimpleMatch`.** They are mutually
exclusive: the escaped backslashes are then searched for literally, so every line containing a
regex metacharacter comes back as a false negative. A clobber check written that way reported
48 of 49 lines of a pushed commit missing when none were. For literal whole-file checks use
`[System.IO.File]::ReadAllText($path).Contains($line)`.

**Python's `read_text()` / `write_text(newline='')` round trip silently converts CRLF to LF**, and a
SHA check will not catch it. `pathlib.read_text()` applies universal newlines, so the CRLFs become
LFs in memory; writing back with `newline=''` writes those literally. Comparing the re-read against
the same in-memory string passes, because both sides were converted. On 2026-08-13 an injection
harness restored `app.py` this way, reported a matching hash, and left the whole file LF-only. **Git
normalised it on read so nothing reached the commit** — `git diff` was empty — but `git status`
showed the file modified, and it needed `git checkout -- app.py`. Use `read_bytes`/`write_bytes` for
a byte-exact round trip, and **check `git status` after any scripted edit rather than trusting the
hash**. This is the third tool recorded here that rewrites a file while reporting success.

> **SUPERSEDED 2026-08-12 — do not follow the paragraph below.** The owner's `AGENTS.md` rule
> ("Codex App Safety During Testing") forbids in-app browser automation on this project, so
> `preview_start` and the Browser pane are **not** to be used here at all. The database and port
> hygiene below still applies to a plain local server; the browser half does not. **Ask the owner
> before any browser verification** — an approved plan is not permission. See the notice at the top
> of this file for why, and section 6 for what to build instead.

**Running the app for verification:** explicit `MEDICAL_SERVICE_TEST_DB`, never port 5000,
never `preview_start` name-mode, and stop every server afterwards. The Browser pane blocks
origins it has not registered, so open the app with `preview_start` passing the URL.

**Process hygiene, added 2026-08-12 with the same rule:** never issue process commands against the
agent app, ChatGPT/OpenAI or their children. A process may be stopped **only** when it is an
explicitly identified temporary project test server, its PID and command line were verified
immediately beforehand, and stopping it is required for cleanup.

**Confirm a defect injection actually applied before trusting what the test says.** Proving a
new test fails without its fix is the standard here, and the check itself can lie: a
`str.replace` using `\n` search strings against these CRLF files silently does nothing, the
suite stays green, and it reads as "the tests are vacuous". Print whether the replacement
changed the text, or compare a hash, before drawing any conclusion.

**An authorization rule asserted as a source string is not tested.** `test_stock_inventory.py`
pinned the exact line `return normalize_stock_inventory_branch(getattr(profile, 'branch', None))`;
refactoring that line into a safer helper broke the test while the behaviour improved. Guards
that decide access should be exercised by **calling** them — build a user, hit the endpoint,
assert the status code. That is how the read-only engineer work was actually confirmed: reads
200, all four writes 403, and a request for another branch served the engineer's own.

Two traps that cost real time in the offline schedule work:

- **`/static/` is `cacheFirst` and the service worker re-registers on every page load.**
  Unregister it and clear both caches after *each* asset edit, not once, or you will review
  a stale file and conclude the change did not work.
- **Template edits need a server restart.** Jinja caches compiled templates, so a changed
  `{% if %}` gate will keep evaluating the old way until the process is restarted.

**Test isolation — the database is now fresh per run.** `tests/__init__.py` pins a unique
`MEDICAL_SERVICE_TEST_DB` before any module imports, so every module's `os.environ.setdefault`
is a no-op and they all share **one clean database per run**. An explicit environment value
still wins if you want to inspect one afterwards.

Before that fix the file lived in the temp directory and survived between runs, so state
accumulated: `python -m unittest discover -s tests` could fail on data an earlier run left
behind — `test_completed_delta_matches_the_seeded_weeks` with `0 != 1` — while the same module
passed alone. **Verifying with a hand-pinned brand-new database hides this**, which is exactly
how it went unnoticed. Run the documented command, on the machine as it is.

Modules still share one database and one Flask app **within** a run, so the old hazards remain:
seeding an account named `rodito` makes `ensure_default_approval_routes()` write
`ApprovalRouting` rows whose NOT NULL requester FK breaks sibling modules, and a Completed
shift seeded in one module can land inside another's week-over-week window. Keep cleaning up in
`tearDownClass`; the per-run database only stops a missed cleanup poisoning the *next* run.

---

## 5. Decided against — do not re-raise

**The four machine-scoped P.O. decisions, settled with the owner on 2026-08-12.** All four were
asked and answered before any code; the full reasoning is in the plan in `plans.md`.

> **One of these four was REVERSED on 2026-08-13, the day after it shipped** — the first entry below.
> The other three still stand and are still current. **Read the strikethrough before quoting any of
> this.**

- ~~**More than one machine per P.O.** A P.O. is issued *per machine*, so it is one nullable FK
  column, not a link table. A contract covering three machines is three P.O. rows. If this is ever
  revisited, `templates/travel_request.html:2788-2801` already holds the multi-select equipment
  checklist pattern.~~ — **REVERSED 2026-08-13.** The owner revised the requirement: one P.O. now
  covers several machines, via the `purchase_order_machine` association table. **The decision was
  not wrong when it was taken** — the multi-machine option was costed and declined on the day, and
  what changed was the requirement, not the reasoning. The useful part is the last sentence: it named
  the pattern to use *"if this is ever revisited"*, and that is exactly the pattern the replacement
  plan evaluated. **A deliberate exclusion that carries its own way back is worth writing that way**
  — it turned a reversal into an afternoon instead of a re-investigation.
- **A free-text machine fallback** when a client has no registered equipment. Refused deliberately,
  and it is enforced *structurally* rather than by validation: `saveForm` reads only the hidden
  field, so a typed value **cannot** reach the server. The cost is real and is the first row of the
  waiting-on-owner table — but the same machine spelled three ways destroys the per-machine
  reporting the change exists to enable.
- **Backfilling a machine onto existing P.O. rows.** Nothing is auto-assigned; there is no
  defensible way to guess which machine an old P.O. covered. Legacy rows stay readable and are asked
  for a machine only on edit — the same shape as a legacy Contract missing its End Date.
- **A database-level FK constraint.** SQLite cannot add one via `ALTER TABLE` without a full
  rebuild, and this app never sets `PRAGMA foreign_keys`, so it would not be enforced even where it
  exists. Integrity lives in `validate_purchase_order_payload` plus the two Products-side guards.
  **Do not "fix" this with a table rebuild** — the migration says so in a comment for that reason.

**Honouring the branch filter on the P.O. or Equipment analytics tabs.** `PurchaseOrder` has no
branch dimension — branch lives on `Engineer` — and `/get_po_analytics` deliberately skips
`analytics_scope_query`. Both tabs are labelled `Company-wide` so the numbers are not misread.

**Blocking a machine's reassignment to another client** while P.O.s reference it. It would make
ordinary inventory corrections impossible. The count is logged, and the modal explains the mismatch
on the next edit via `product_client_id` rather than failing with a bare 400.

**Streaming the system backup ZIP.** Queued in section 2 for two sessions as "the durable fix", and
rejected on 2026-08-08 **after prototyping it rather than after arguing about it**. The prototype
works: a queue-backed non-seekable ZIP produced a valid archive — `testzip()` clean, the large file
byte-identical after a round trip, memory flat at ~16 KB chunks — and Windows `Expand-Archive` read
its data descriptors without complaint. It was rejected on what it costs, not on whether it works:

- Since the data-only change the archive is **39 MB built in 3.6 s**, nowhere near the 180 s
  timeout. Streaming solves a problem that is not currently occurring.
- It would lose the **`Content-Length`**, and with it the real progress bar on a 39 MB download.
- It would lose **`X-Backup-Complete`** and **`X-Backup-Warning-Count`**, which cannot be set once
  the body has started and are the only machine-readable signal that a backup came back partial.
  Streaming commits `200` before any error is known.
- Both symptoms that motivated it — blocking other users, and the worker being killed — are fixed
  in the Procfile instead, at no cost.

**Revisit only if the build itself approaches the timeout**, and expect to trade the progress bar
and those two headers for it. The reasoning is duplicated in the `/admin/download-backup` docstring
deliberately, because that is where someone will be standing when they reconsider.

> **THAT TRIGGER FIRED ON 2026-08-09 — one day later.** The owner reported the production download
> failing, with Resume not recovering it. See **bug 2a in section 1**, which is where the work lives.
>
> **The decision was still correct when it was made, and this is the useful part of the record.** It
> was taken on measurement — 39 MB in 3.6 s, locally — and the measurement was true. What it did not
> account for was that **production is not the local machine**: real uploads, a bucket read with its
> own 12-second budget, and a proxy between the client and the app that the local test does not have.
> A number measured in the wrong environment is not a wrong number, it is a number about something
> else.
>
> **Do not simply reverse it on the strength of this note.** The costs are unchanged and real, and
> the cause of the failure is still a hypothesis — get the production error first, per bug 2a. If it
> turns out to be a proxy idle timeout during the build, streaming is the right answer and the
> prototype above is ready. If it turns out to be memory, or a deploy that never picked up the
> gthread Procfile, streaming would be a large change that fixes nothing.
>
> ### OUTCOME, 2026-08-09: the decision was SUPERSEDED, not reversed. Streaming was never built.
>
> `b4b17fc` shipped **build-then-download** instead: a background job builds the archive ahead of
> time and the route serves a finished file. That answer was not on the table when this decision was
> written, and it dominates both options that were:
>
> | | Buffer in the request (old) | Stream (rejected) | **Build ahead (shipped)** |
> | --- | --- | --- | --- |
> | `Content-Length` / progress bar | yes | **no** | **yes** |
> | `X-Backup-*` completeness headers | yes | **no** | **yes** |
> | First byte is immediate | **no** | yes | **yes** |
> | Range / Resume | **no** (file deleted) | no | **yes** |
>
> **The lesson worth keeping is about the question, not the answer.** This entry framed it as a
> binary — keep the headers or keep the timeout margin — and spent real effort measuring and
> prototyping *within* that frame. The frame was the mistake. When a decision record reads as a
> straight trade-off between two costs, that is the moment to ask what a third option would look
> like, because the strongest answer here gave up nothing at all.
>
> The streaming prototype remains valid and is still recorded above. It is simply not needed.

**Reimbursement rows where the component columns and the saved `row_total` disagree.** Since
`aff9001` the generated PCV, RFP, Excel and ZIP all use the **component sum**, not the saved
total, and surface a mismatch warning. Raised with the owner as a business decision rather than
a technical one — the smoke case differed by ₱18,339 — and **the owner rectified it separately
and confirmed the rule stands**. Do not "fix" this back to `row_total`.

> **Corrected 2026-08-06 — the entry below still stands, but only for the predicate.** The
> *serializer* beside it did not. `approval_user_to_dict()` reported
> `can_manage_stock_inventory(user)` and `is_stock_inventory_only_user(user)` rather than the
> stored columns, and because that dict renders the Settings switches while `saveApprovalUser()`
> posts the rendered state straight back, a computed value silently rewrote what it displayed:
> the inventory switch showed **checked** for every superadmin with nothing granted, and saving
> any unrelated change on their card then wrote `can_manage_stock_inventory=True` plus an audit
> line for a grant nobody performed. `stock_inventory_only` was wrong in the **opposite**
> direction — stored True, shown False whenever access was False — so a save would have silently
> *cleared* a grant an admin did set. Both fixed in `ad463c8`; the predicate is untouched and
> `StockInventorySuperadminBypassTests` still pins it. A superadmin's switch now renders
> unchecked **and** that account still gets 200 on `/stock_inventory`.
>
> `approver_only` was deliberately left computed and now has a test guarding that: it has no
> column, being derived from `role` plus `can_approve_requests`, and the save route flips the role
> from it. **The rule the three fields together teach: report the stored grant when a column backs
> it, and only compute when nothing does.**

**The superadmin bypass in `can_manage_stock_inventory`.** It returns true for superadmins
regardless of the stored toggle. That looks like a hole and is not: `is_superadmin_user` is a
hardcoded username allowlist rather than a settable flag, and `stock_inventory_can_administer`
already grants those accounts the admin surface, so un-ticking the toggle never withheld
anything. Reviewed, documented in place, and pinned by a test whose positive control proves an
ordinary account without the flag is still refused.

**Editing or deleting a schedule offline.** Excluded from `709106c` by decision. Offline
creation is a new row and needs no reconciliation; an offline *edit* must resolve against a
row that may have changed on the server in the meantime, which is a materially harder problem.
Queued rows are refused by `canManageExistingScheduleForRow()` precisely so edit, delete and
drag cannot act on a schedule that has no server id yet. Revisit only as its own task.

**Offline schedule creation for schedulers and admins.** Excluded by decision. They create
schedules for many engineers at once, which multiplies the conflict surface, and they are
typically on a connection. The permission gate is `isEngineer` on the device plus
`can_create_schedule_for_engineer_ids()` on the server, which is re-checked at sync and is not
bypassed by the creation token.

**The Background Sync API for the schedule queue.** Excluded by decision; sync is manual and
on-reconnect, matching the TSR queue. Adding a background sync worker brings its own
reliability questions and belongs in its own task if it is ever wanted.

**Renaming `/offline_tsr_sync_ping`.** It now serves both the TSR queue and the schedule
queue, so the name is narrower than the job. Left alone deliberately — renaming a route used
by field devices to fix a name is not worth the deployment risk.

**Reviving the hybrid dashboard sections.** `needs-attention` and `team-intelligence` were
retired in phase 4 rather than made reachable. The manager watchlist already consolidates
severe overdue, aged TSR, blocked jobs, repeat equipment and at-risk clients into one
de-duplicated list with the engineer-workload drill-down beside it, and it renders. **Settled
in `5de1658`, so this is now closed rather than pending a decision** — their content is
redundant, not merely unreachable.

Correcting the record on *why*, since the earlier version of this file sent readers at the
wrong file: the fix was never the role-gating predicate. `hybrid_view` — `bool(engineer_profile)
and admin_authorized` — already existed and was already satisfiable; the retired sections had
simply been gated on `admin_view and not manager_view`, a different condition that no account
can satisfy. Reviving them would have been a one-word gate change. They stay retired on merit.

`hybrid_view` now has a real job: it gates the "Your own work" scope divider and the
subordination of the personal sections. `tests/test_dashboard_hybrid.py` asserts it still gates
something, so it cannot quietly become dead weight again, and asserts the *outcome* — that no
gate combines `admin_view` with `not manager_view` — rather than pinning a substring of
`is_manager_dashboard_user()` the way the earlier test did.

**A distinct hybrid view.** Considered and declined during the ratification. Every admin
non-scheduler (`jonamar`, `robert`, `kevin`, and `rodito` before his exemption) holds an
engineer profile, so `manager_view` and `hybrid_view` describe the same people and there is no
pure-manager account in the system. Building a third view would have meant inventing content,
not reviving it, with no unmet need identified. The scope divider addresses the actual
complaint, which was that the two halves of the page were indistinguishable.

**Narrowing `is_manager_dashboard_user()` so `kevin` and `jonamar` stop getting a manager
dashboard.** Raised and set aside during the ratification as a larger blast radius than the
problem warranted: the predicate also drives `can_view_manager_dashboard()`, and panels that
only suit a real manager are already gated on something narrower — the approvals block gates on
`is_approval_center_user()`, which is why `kevin` correctly sees it hidden. Revisit only if a
pure-admin account is ever created and its dashboard looks wrong.

**Coupling `MANAGER_PRIMARY_USERNAMES` to the other `'rodito'` literals.** Both
`APPROVAL_CENTER_MANAGER_USERNAME` and the hardcoded `'rodito' -> 'Manager'` branch in
`get_display_role()` (`app.py:7430`) happen to name the same account today. They mean different
things — approval routing, display label, dashboard layout — and unifying them would make a
change to one silently move the others. Left as three separate declarations deliberately. This
is the one place the "no duplicated username literals" rule from phase 2 does **not** apply.

**Inline approve/reject on the manager dashboard.** Considered in phase 3 and declined: it
would mean deciding a money-carrying request without seeing its contents, and it widens the
authorization surface onto the dashboard. Approving stays on `/approvals`.

**A change figure on current-state totals.** Phase 3 added week-over-week deltas to *flow*
metrics only (visits completed, visits scheduled, TSR completion rate). Currently-overdue and
currently-pending-TSR deliberately carry **no** comparison: a shift that was overdue last
week and has since been completed has left the overdue set, so any reconstructed historical
figure is systematically undercounted. That would be a wrong number wearing an authoritative
arrow.

> **REVERSED 2026-08-07, in `v77`. The entry below is kept as the record of a decision that was
> right when it was made and stopped being right.** Sign-out now purges the whole `RUNTIME_CACHE`
> plus `/timeline` and `/offline-tsr` from the app shell — the shell mattered too, because
> `precacheShellEntry()` fetches those with credentials. `/login`, `/offline` and every static asset
> are deliberately kept, or an offline sign-out has nothing to land on.
>
> **What changed between 2026-07-28 and now was not the argument but the facts under it.** The
> original decision rested on 1:1 devices and was written about cached **HTML**. Then the HR role
> arrived — the first role whose entire purpose is to see *less* than another role on the same
> screen, so the redaction contract became per-account while the cache key still had no account in
> it — and the 2026-08-06 pass demonstrated the same cache serving an authenticated export across
> accounts. `v71` closed that one route; this closes the mechanism.
>
> **Both residuals below are also gone**, the first as a direct consequence: `/logout` is now
> network-only, so it is no longer cached; and `staleWhileRevalidate` has nothing account-specific
> left to serve after a sign-out. `staleWhileRevalidate` itself was deliberately not rewritten —
> with the cache cleared at sign-out the exposure is gone, and rewriting the default handler is a
> much wider blast radius.
>
> **The one thing deliberately NOT cleared, and it must stay that way: IndexedDB.** The offline
> schedule and TSR queues live there and hold work an engineer has done and not yet synced. Clearing
> them at sign-out would lose real field work — a worse failure than the one being fixed. This is
> also why `Clear-Site-Data`, the tidy server-side equivalent, was rejected: it takes IndexedDB with
> everything else. A test pins the exclusion.

**Clearing the service worker runtime cache on logout.** Authenticated HTML persists in
`RUNTIME_CACHE` after sign-out, so on a shared device an offline user could see the previous
user's cached pages. The owner confirmed on 2026-07-28 that engineers are issued **1:1
devices**, so the scenario does not occur in practice.

Two minor residual behaviours were accepted rather than fixed: `/logout` is itself cached in
the runtime cache, so an offline logout may not reach the server; and
`staleWhileRevalidate()` can return slightly stale HTML for same-origin non-navigation GETs.
Neither is an exposure on a personal device. Revisit only if loaner or shared laptops become
routine.

---

## 5b. Observations from the 2026-08-07 verification pass — recorded, not fixed

### ~~An uncached API GET resolves 200 with the `/offline` page~~ — FIXED, `d28483d`

`networkFirst()` now ends at `offlineApiResponse()`: **503**, `application/json`, `offline: true`,
with both `error` and `message` set to the same text because consumers here read one or the other
(`app-analytics.js` renders `message`, the schedule and leave paths read `error`).

**The estimate below was wrong about the cost, and the correction is the useful part.** This entry
said fixing it "touches every consumer of `networkFirst`". It does not: the **navigate branch is
matched before the networkFirst prefixes**, so only programmatic fetches ever reach that fallback.
Nothing that renders HTML does. `fieldNavigationFirst()` still returns the offline page and a test
pins that it does — a page must still get a page. What looked like a wide, risky change was a
contained one, and it was the *ordering* in the fetch handler that made it so.

Verified in a browser against a genuinely stopped server: the API read returned 503 with parseable
JSON, navigating to `/timeline` still landed on the offline page, and `/static/` still served from
cache.

<details>
<summary>Original entry, retained for the mechanism and the wrong estimate</summary>

**An uncached API GET resolves 200 with the `/offline` page.** With the server down,
`fetch('/get_engineers?anything')` returns **status 200 carrying the offline HTML**, because
`networkFirst()` ends in `return caches.match('/offline')`. A caller that checks `response.ok`
concludes success and then fails at `res.json()` with a `SyntaxError` — which is how it first
surfaced during this pass, as a JSON parse error that looked like a corrupt payload.

No field workflow is known to be harmed: the queues use their own error paths, and this is
long-standing behaviour rather than anything new. But `app-analytics.js` would take `{}` from its
`.catch(() => ({}))` and then read `data.range`, so an admin who opens Analytics offline is likelier
to get a broken render than the honest "could not be loaded" message that page works hard to show.
Fixing it properly means giving the fallback a non-200 status, which touches every consumer of
`networkFirst` — its own task, and a decision rather than a cleanup.

</details>

**Dark mode cannot be judged by computed style alone in this pane, and it nearly produced a false
bug report.** Toggling `data-app-theme` and reading `getComputedStyle(document.body)` showed the page
background stuck light while every panel went dark — which reads exactly like a broken dark-mode
rule, and the `!important` rule at `app-dark-pages.css:29` made it look like a specificity fight.
The real cause: `body` carries `transition: background-color 0.3s`, and **this pane never advances
the animation timeline**, so the computed value stays at the *from* colour forever. Disabling
transitions resolved it to `#0f1722` immediately. **Before reporting any colour as wrong here,
disable transitions first** — the properties most likely to be transitioned are exactly the
theme-driven ones.

## 6. Patterns worth knowing before the next feature

### The three from the register fixes, 2026-08-14

**1. A fixed colour on a themed surface has two contrast ratios, and no existing guard catches it.**
The register toasts carry tone on a left border and an icon rather than a tinted background —
deliberately, because a fixed-light background inverts under themed text, which is the defect this
file records shipping twice. That decision was right, and it still was not enough: the *warning*
colour `#fd7e14` measured **5.50:1 on the dark surface and 2.46:1 on the light one**, under the 3:1
floor WCAG 1.4.11 sets for a border or an icon. **The repo-wide token guard could never have caught
it — that test only sees *undefined* tokens, and a hardcoded literal is by definition defined.**
The durable answer is the same shape as the token guard: a test that reads `--app-surface-raised`
from **both** theme blocks and every declared tone, and computes the ratio — so it also fails if the
surface token is retuned underneath colours that pass today. Two of the three tones clear the floor
by 0.12, so that is not hypothetical.

**Corollary about reviewing, learned the same day:** the review that raised this said three colours
were short. **Only one was.** Success and danger measure 3.12:1 and pass; the reviewer eyeballed
"3.12 is close to 3" as a failure without computing the threshold. **Compute before characterising
severity** — an overstated finding costs the same credibility as a missed one.

**2. A commit cannot record its own hash.** Writing the hash into the file changes the hash, so the
recorded value names a commit that is no longer on the branch. `changes.md` credited a P.O. fix to
`a0e06bf`; the shipped commit is `7c87be3`, and the **only** difference between the two objects is
the line adding that hash. The pattern that works is already in this repository and was used nine
seconds earlier: commit the entry reading *"commit pending"*, then let the follow-up journal commit
fill in the real hash — which is exactly what the `Record … execution` commits are for. **Either use
that, or cite nothing.**

**3. A number repeated across journals can describe something other than what it claims.** Every
entry for weeks — including several written here — reported the suite as *"N tests, one pre-existing
skip"*, as though the skip were a standing property. It is not. It is
`test_latest_user_facing_commit_has_a_changelog_entry`, which **skips when the newest commit touches
only `tests/` or `.md`** and runs otherwise. The count tracks *what was committed last*. It even
demonstrated itself: a code commit reported 662 with no skip, and the `.md`-only follow-up minutes
later reported `OK (skipped=1)`. **When a figure appears in every entry unchanged, that is a reason
to re-derive it, not evidence that it is stable.** This file already says re-measure before acting
on a number in here; this is the version where the number was not even measuring what it named.

### The four from the multi-machine migration, 2026-08-13

**1. A hazard belongs to a construction, not to a feature — and this file caused the error it is now
recording.** The plan ranked "a `joinedload` on the machines collection makes a 3-machine P.O. count
as three purchase orders" as the single nastiest available bug, citing this file's own
`analytics_scope_query` entry. **Measured, it is not reachable**: `len(orders)` is `1` under both
`selectinload` and `joinedload`, because the repo uses the legacy `Model.query…all()` API, which
de-duplicates parent entities. Swapping them breaks no test. The multiplication hazard is real for a
**SQL-level count over a join** — which is why `analytics_scope_query` uses a correlated `EXISTS` and
`analytics_branch_counts` uses `count(distinct …)` — and it was transferred to `len()` over ORM
entities, where it does not apply. `selectinload` is still correct here, but as a *performance*
choice. **When quoting a recorded hazard, check the new code is the same construction, not merely the
same subject.** This file's warnings are load-bearing precisely because they are specific.

**2. A fixture where two quantities coincide cannot tell them apart.** The multi-machine analytics
test produced three P.O.s **and** three machine links, so asserting the headline `total` there would
have passed whether it counted orders or links. Pinning it required a fixture where the two must
differ — three machines on **one** P.O. This is the same shape as the 2026-08-06 lesson below ("two
fixtures that agree cannot test the thing that separates them"), now in arithmetic rather than
permissions. **Before asserting a number, check the fixture makes the wrong answer a different
number.**

**3. A constraint you add can create the hazard the next person has to handle.** The plan insisted on
a `UniqueConstraint` on `(purchase_order_id, product_serial)` — correctly, citing `ShiftEngineer`.
That constraint is exactly what makes replacing a collection dangerous: SQLAlchemy will INSERT the
replacement before deleting the orphan holding the same key, so an edit from `[A,B]` to `[B]` 409s.
Codex caught it and clears-and-flushes first; the plan did not. **When you add uniqueness to a set
that is replaced wholesale, the replace becomes ordering-sensitive.** The two decisions belong in the
same paragraph, not in different sections.

**4. A SHA comparison only proves what you compared.** The injection harness restored `app.py`,
verified the hash matched, and had still converted the whole file from CRLF to LF —
`pathlib.read_text()` applies universal newlines, so writing back with `newline=''` writes the
converted content, and both sides of the comparison were converted identically. Git normalises on
read so nothing reached the commit, but `git status` showed the file dirty. This is the **third**
tool in this file to silently rewrite a file while reporting success, after `Set-Content -Encoding
utf8` (BOM) and `[regex]::Escape` with `-SimpleMatch`. **For a byte-exact round trip use
`read_bytes`/`write_bytes`, and check `git status` rather than trusting the hash.**

### The four from machine-scoped P.O. records, 2026-08-12

**1. The same defect shipped twice, and the guard written to prevent it was scoped to one page.**
`--app-raised-surface` for `--app-surface-raised` — a transposition — reached `main` on the
Reimbursement Tracker, was fixed, and then reached `main` again on P.O. Details at **1.01:1**. The
test written after the first occurrence, `test_every_theme_token_the_page_uses_is_actually_defined`,
read **`reimbursement_tracker.html` and nothing else**, while its own docstring claimed it asserted
*"the class, not the one instance"*. **A guard's docstring is not its scope. Read what it globs.**
It is now repo-wide over every template, stylesheet and script, and the page-scoped copy was
**deleted** rather than left beside it — two guards that must agree is the shape that caused this.

**2. Widening a guard is worth doing for what it finds today, not only for what it prevents.**
Making it repo-wide immediately exposed a **second live defect nobody had reported**: the recall
modal's Cancel button set a light `background` under `var(--app-text)` — **1.13:1 in dark mode**, on
all five request pages. If the widening had been deferred as "cleanup", that would still be
shipping. A guard that finds nothing on the day you widen it is the exception, not the rule.

**3. This defect class is one-directional, and that is why it survives review.** The fallback is
always a light colour chosen to look right in light mode, so **light mode is perfect and only dark
mode breaks** — 14.44:1 against 1.01:1 for the same rule. A browser pass in light mode reports
"pass" with complete honesty. Nothing errors, nothing logs, and `getComputedStyle` in the pane lies
about it separately (see the transition trap below). **The only reliable detector is the token
spelling, which is why the fix is a test and not a look.** Corollary worth carrying: **a token used
as a `background:` almost never qualifies for the undefined-token exemption list**, because an
unresolved background inverts against themed text; a foreground-only fixed brand colour does.

**4. The plan's riskiest-items list did its job, and that is repeatable.** Two of the flagged risks
were latent bugs found *while planning* rather than while coding — `update_product` repointed
`Shift.product_id` and nothing else, and `delete_product` had no reference check at all — and both
were built correctly because they were named up front. The Excel column shift, flagged as "still
opens while being quietly wrong", came through arithmetically correct. **Ranking risks by "would
ship and nobody notices" before writing code is what made those three land.** The one that got
through was the one nobody thought to rank, because the guard against it was believed to exist.

### The five from the Reimbursement Tracker, 2026-08-11 to 08-12

**1. Three of the four defects found across both reviews were suite-invisible and browser-obvious.**
White-on-white text at 1.04:1 contrast, a modal that could not be scrolled so Save was unreachable,
and a form ignoring a value its own API returned correctly. **The suite was green for all three**,
and each took seconds to see in a browser. When a change touches a page, the browser pass is not a
formality after the tests — for this class of defect it is the only thing that works.

**2. Asserting the endpoint is not asserting the feature.** The server correctly returned
`BATCH-032`; the form cleared the field and showed a hard-coded `BATCH-001` placeholder. A test
asserted the API response and **passed the entire time the page ignored it**. This is the
page-gate/endpoint-gate defect this file records five times, in data rather than access: two places
had to agree and only one was checked. **When a value crosses from server to screen, assert the
consumer.**

**3. A misspelled CSS custom property is invisible — it silently takes its fallback.**
`--app-raised-surface` does not exist; the token is `--app-surface-raised`. Nothing errors, nothing
logs, and the element keeps a light background while its text follows the theme. The durable fix was
**a test asserting the class, not the instance**: every `var(--app-*)` the page uses must be defined
in `static/css/app-themes.css`, with deliberate exemptions named. A test pinning the one misspelling
would have caught one bug; this catches the next one too.

**4. An injection that aborts looks exactly like an injection that worked.** A defect injection here
reported RED while the test had never run — the class name was wrong, `unittest` failed to *load*
it, and the runner exited non-zero. **The exit code cannot tell those apart; the failure message
can.** This file has warned about the CRLF version of this trap for weeks and it still caught a
careful attempt in a new form. Read the assertion text, and keep a passing control.

**5. `.modal.fade` measures zero on every child in the Browser pane.** The pane never advances
transitions, so an unopened-looking modal returns `clientHeight: 0` everywhere and the bug reads as
absent. **Disable transitions before measuring anything animated** — the same trap already recorded
for dark mode, now confirmed for Bootstrap modals. Two measurement attempts came back all-zeros and
looked like "no bug".

### The four from 2026-08-08

**1. The gate mismatch was fixed by deleting the second gate, not by correcting it.** Five previous
occurrences were all fixed by editing one expression to match the other — which leaves two
expressions that must be kept in agreement by whoever edits next, and is why it kept recurring.
`can_back_up_tsr_drafts()` is now called by the page *and* all three endpoints, so there is nothing
left to drift. **When two places must agree about who sees something, the durable fix is one place.**
Compare the `stock` block in the Analytics work: a value that must not be shown should not exist.

**2. This file was wrong three times, always in the reassuring direction.** The tap-target note
called a button unlabelled that carries an `aria-label`; it missed two controls that passed on
height and failed on width; and the 5b entry estimated a change would "touch every consumer" when
the fetch handler's ordering made it contained. None of these was a lie — each was a careful note
written from reading rather than measuring. **Re-measure before acting on a number in here.** The
`.dashboard-metric-link` entry was already stale in exactly this way on 2026-08-07.

**3. Prototype the thing you are about to reject, before rejecting it.** Streaming the backup could
have been dismissed on reasoning alone; building it took one throwaway script and produced a much
better answer — *it works, and here is what it costs*. That turns "we decided not to" into "we
measured the trade", which is the difference between a decision the next reader can evaluate and one
they will simply re-litigate. The same script also proved the compatibility worry (data descriptors)
was unfounded, which reasoning would never have settled.

**4. A tap target is 44×44, and a height-only audit will tell you it is fine.** Both appearance
buttons were already 44 px tall and failed at 34 px and 42 px wide. The controls that pass one
dimension and fail the other are precisely the ones a quick check misses, because the number you
look at first is the right one. Assert both, and assert them against the shared token
(`--mobile-touch-height`) so one edit cannot silently lower all of them.

### The four from 2026-08-07, in order of how much they will save you

**1. Anything reached by a link is a navigation, and the service worker will eat it.** This has now
caused two production faults. `/export_` leaked one account's CSV to another (`v71`); the backup
download showed an admin *"you are offline"* while online, wrote an 80 MB archive into Cache
Storage, and could return a **stale archive as if it were current** (`v81`). Both because the route
was matched *after* the navigate branch and fell into `fieldNavigationFirst()`, which caches every
ok response and ends its failure chain at `/offline`. There is now a
`NETWORK_ONLY_DOWNLOAD_PREFIXES` list matched ahead of that branch — **put new authenticated
downloads in it.** Two further things worth carrying:

- **`Cache-Control: no-store` does not keep anything out of Cache Storage.** That API ignores HTTP
  cache headers; `cache.put()` stores whatever it is handed. The route had the header the whole time.
- **The offline page is an excellent way to hide a bug.** Two commits of backup hardening shipped
  while nobody could see the real error, because the worker had replaced it. When a symptom is "it
  says I'm offline", suspect the worker before the network.

**2. The gate mismatch reached `main` for the fifth time.** A page that admits N roles and an
endpoint that admits fewer is not a security bug — it fails closed — but it silently disables a
feature for real users, and the UI usually keeps promising it works. Every previous occurrence was
found the same way: **build one account of each shape and call the route.** That is four lines of
test and it has now caught five defects. See section 1z, which is open.

**3. Two "before/after" numbers are worth more than a paragraph of reasoning.** The backup was
diagnosed by generating the real archive and printing its composition: 56 MB of source, 47 MB of it
duplicated, of an 82 MB total. That immediately showed both what was wrong and what to remove, and
gave an unarguable 82 → 39 MB to verify against afterwards. Prefer measuring the artifact to
reading the code that produces it.

**4. An invalid injection is not a vacuous test, and telling them apart matters.** Three injections
this session came back green or aborted, and **none of them meant the test was worthless**:
disabling a branch with `false &&` leaves the marker in place, so no test claiming to check the
branch's *content* can catch it; pinning the travel signature group's width keeps the name clear
because the name is derived from the group. In each case the injection did not reproduce the defect
the test guards. **Before concluding a test is decorative, check that the defect you injected is the
one it claims to catch.** The genuinely vacuous case is different and did occur — a PCV test that
recomputed the formula instead of calling the code, and passed with the defect injected.

### Two smaller ones from the same day

**A test that punishes a mandatory step will be worked around.** `test_service_worker_cache_is_bumped_for_server_drafts`
pinned the exact `v80` string, so the next required worker bump failed the suite. This file already
recorded that anti-pattern once; it came back. Use `assert_cache_version_at_least` — a **floor**.

**When a value must be derived from another, derive it.** Three separate defects this session were
the same shape: a constant that used to agree with something it no longer tracked. The TSR footer
reserve was hardcoded `247` — exactly the old footer height — and broke when the signature grew; the
traveller name's 410 pt width stopped clearing the signature group when the group moved left; the
LPR fallback boxes kept pre-enlargement sizes. Each fix replaced the literal with the calculation.

### From the Analytics review, and the first one generalises well beyond it

**1. A metric's complement inherits its bias, sign flipped.** The Analytics page correctly withheld
a period-over-period arrow from **Completed** — recent work has had less time to finish, so a
comparison would read as a change in performance when it is not — and printed *"No recency arrow;
status stock"* to say so. Then it put an arrow on **Active**, captioned "Not completed". But
`active` is *exactly* `total − completed`: `active 2 + completed 2 = total 4`, and
`previous_active = previous_total − previous_completed`. If `completed` is biased low, `active` is
biased high **by the same amount**. Half a rule applied is a rule that looks principled and is not.
Before exempting a metric from a comparison, write down what it is arithmetically and check whether
anything else on the page is that same quantity rearranged.

The enforcement is worth copying: `active`, `open_client_work` and `completed` now sit in a `stock`
block whose members carry a `basis` string and **no `previous` key computed at all**, and the
renderer draws an arrow **iff** `previous` is present. A value that must not be shown should not
exist. Compare that with a comment saying "do not show this" — comments do not survive a refactor.

**2. A panel's gate must be the same expression as its endpoint's gate.** `/get_po_analytics` was
opened to `can_view_admin_reports() or can_manage_purchase_orders()`; the template flag was set from
`can_manage_purchase_orders()` alone. A reports-admin therefore got **200 with real data** from the
endpoint and **no panel** on the page. Superadmins pass either way, so it looked fine to whoever
tested it, and the shipped test checked that account's *schedule* surface but never the P.O. panel.
**When two places must agree about who sees something, assert them together against the granted
account** — this is the fourth time an admin-passes/grantee-fails gap has reached `main`.

**3. Structural beats escaped.** The XSS fix here is not `escapeHtml()` at every call site — it is
one `svgElement()` helper using `createElementNS` + `setAttribute` + `textContent`, so there is no
string-interpolation path to forget. Verified by setting an `Engineer.branch` to
`"><img src=x onerror=alert(1)><script>alert(2)</script>` and finding literal text in the chart, the
table, the mobile cards and the tooltip. If you extend those charts, keep the rule: **never
`innerHTML` with data**, and the class of bug stays unreachable rather than merely handled.

**4. The CRLF trap is real, and the guard against it is a match count.** Two defect injections during
this review **aborted instead of passing** because their multi-line needles used `\n` against these
CRLF files. Section 4 has warned about this for weeks; it still caught a careful attempt. The reason
it surfaced as an abort rather than a false green is that the harness asserts the needle occurs
**exactly once** before writing, and re-checks the SHA changed. Keep both checks in any injection
script — without them a silently-matched-nothing injection reads exactly like a healthy control.

### The three from 2026-08-06

**1. A value that is displayed and then posted back must be the stored value, not a computed one.**
This is a whole *class*, not one bug: it was found in `po_admin_access`, then in
`can_manage_stock_inventory` and `stock_inventory_only` beside it. `approval_user_to_dict()` renders
the Settings switches and `saveApprovalUser()` posts the rendered state straight back, so any field
reported as an effective permission silently **rewrites** what it displayed — persisting a flag
nobody set and writing an audit line for a grant nobody performed. It is not an escalation, because
the accounts already held the access; the damage is to the record of *intent*, in the one log that
answers "who was given what". The rule: **report the stored grant wherever a column backs it, and
compute only where nothing does.** `approver_only` is the legitimate exception — it has no column —
and now carries a test saying so, because the next reader will otherwise "fix" it too.

**2. Ask whether an odd-looking choice is a fresh fault or a replicated one, before grading it.**
The P.O. serializer looked like a clear regression against its three siblings. Probing
`can_manage_stock_inventory` showed identical behaviour — so it was a *precedent* being followed,
just the older and odder one. That changed the finding from "Codex introduced a bug" to "this
replicates a known wart", which is a different conversation with the owner and a different fix
scope. One probe, and it was the difference between an accurate report and an unfair one.

**3. Two fixtures that agree cannot test the thing that separates them.** The first version of the
stock-inventory test passed whether `stock_inventory_only` reported the stored or the computed
value, because in both fixtures those agreed. It read as complete coverage. It took a third account
— only-mode stored True with access False, the single combination where the two diverge — to make
the injection go red. When a fix changes *which* of two sources a value comes from, the fixture
must contain a case where those two sources **disagree**, or the test is decoration. Related: run
each field's injection **separately**; reverting both at once would have hidden this.

### The four lessons from 2026-08-05, in order of how much time they will save you

**1. A broad admin predicate placed ahead of a narrower role branch deletes the narrower rule.**
This is the shape of the worst defect found all day. `can_manage_any_schedule()` was written as
`is_admin_authorized(target) or flag` so that existing admins would keep their access — sensible
in isolation. Dropped into the four schedule helpers *above* the regional-admin branch, it
returned True first and silently removed the "Cebu and Davao only, never Manila" rule. The fix
was a second predicate, `has_schedule_admin_capability()`, carrying the flag **alone**. Before
adding any capability check to a function that already branches on roles, ask what comes *after*
it and whether that branch narrows anything.

**2. "The tests still pass" is not evidence during a refactor of live authorization rules.**
Extracting `resolve_staff_permission_request()` was specified as pure movement and changed three
rules; the existing Settings tests passed because none of them covered those inputs. Both
escalations survived hundreds of green tests for the same reason: **nothing exercised the
affected account.** When you move authorization logic, list the accounts the rules distinguish
between and assert each one before and after — the regional admin, an approver-only account, a
plain engineer. A suite only proves what it exercises.

**3. An assertion on source text is not a test, and this repo has now produced five.**
`test_stock_inventory` pinned a line that a safe refactor broke; `test_admin_capabilities`
asserted a raw-role string was absent; `test_request_recall` pinned the exact cache version so
that bumping the worker — a **required** step — failed the suite; `test_timeline_tsr_file_details`
claimed to test HR redaction by checking that `'file_details': [],` appears somewhere in
`app.py`. Each was replaced with a behavioural assertion plus a positive control. The rule:
**build the account, call the route, assert the response.** The narrow exception is inline
template JavaScript, where there is no JS runner — there, assert an *outcome* (that a function no
longer calls `openEditModal`) rather than pinning how the replacement is written, and say so in a
comment.

**4. An injection that does not reproduce the defect proves nothing — and it looks like success.**
Proving the endpoint-shape test required diverging one endpoint. The first attempt edited the
*shared* serializer, so both feeds changed together, stayed identical, and the test correctly
passed. It read exactly like a healthy control. This is the same family as the CRLF trap in
section 4: **verification steps can fail in the reassuring direction.** After every injection,
confirm it applied (SHA the file) *and* that the test failed **for the reason you expected** —
read the assertion message, not just the exit code.

### Two smaller ones from the same day

**Redaction that stops at one exit.** The HR calendar hid job titles and equipment; the CSV export
of the same data did not, because it built its own cell text. If you redact something, find every
path that serialises it — screen, export, email, PDF — and make them read one function.

**Bump the worker when a template changes, even if it feels like CSS.** `templates/timeline.html`
is `APP_SHELL` entry #1 and `layout.html` is embedded in every shell page, so a cached device
keeps the old markup. One commit shipped a whole capability with no bump and a journal entry
asserting no `APP_SHELL` asset had changed. A one-line CSS fix in `timeline.html` needs a bump too.

### The de-duplication pattern

The same defect appeared **three times independently** across the dashboard endpoints:
buckets of rows concatenated without de-duplication, so an item qualifying for two buckets
rendered twice. The scheduler priority queue, the manager watchlist and the hybrid attention
list each had it, each written separately.

All three are now de-duplicated by entity key with the highest-ranked reason winning, and
each has a test with a **positive control** proving the item genuinely qualified twice — so
the assertion cannot pass on an empty fixture. If you build another list that merges signal
buckets, de-duplicate it and test it the same way.

A related one: where a count labels a filter control, compute the count from the
**de-duplicated list and before any cap**, or the button will promise more rows than it
produces. Phase 2 shipped that bug and fixed it in the browser; phase 4's tests assert it.
