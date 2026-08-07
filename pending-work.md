# Medical Service SMS — Pending Work

Everything started but not finished, plus anything deliberately deferred.
Companion to `changes.md`, which records what **was** done. This file records what is
**still open**.

**Update rule:** only touch this file when the project owner explicitly asks. It is not
maintained automatically the way `changes.md` is.

Last updated: 2026-08-07, at the owner's request, after **four open items were closed in one
session** — the chart sizing, the runtime cache decision, the two dead routes, and the digest.

**Start here if you are picking this up cold.** The state is good: **no open bugs**, suite green at
**525**, service worker at **`v77-logout-cache-purge`**, nothing uncommitted but the four known
artifacts.

**A verification pass later the same day closed five more rows from section 3** — offline with the
server genuinely stopped, the two-tab race, engineer stock inventory on a viewport, the What's New
row at 375 px, and P.O. Details in dark mode — and found the `.dashboard-metric-link` entry was
**stale rather than open**. It also found one real defect (`parse_engineer_ids` 500) and two
observations now in section 5b. **What remains is almost entirely things this environment cannot
do:** a real phone, Edge and Brave, a print preview, and keyboard focus.

**What closed on 2026-08-07, and where the residue is:**

1. **Analytics charts are drawn at 1:1 and no longer scroll at 375 px** (section 3). Verified on a
   real viewport. **One part is unverified — the `ResizeObserver` redraw**, because this Browser pane
   does not composite the page and neither `requestAnimationFrame` nor any `ResizeObserver` callback
   runs in it. The geometry is proven; the trigger is not. It is the only thing in this batch needing
   a real browser.
2. **Sign-out now purges the authenticated caches** (section 5, where the old decision is kept and
   marked reversed). Verified end to end. IndexedDB is deliberately untouched and must stay that way
   — the offline queues live there.
3. **The two dead routes are gone**, with a test pinning that `/get_activity_logs` — the endpoint
   `/activity_page` actually uses — is *not* one of them.
4. **The digest went to the real audience.** Note there is **no idempotency**: a second send re-sends
   to everyone who already received it.

**The most useful thing to know before touching the service worker again:** the fetch handler's
branch **order** is load-bearing twice over now. `/export_` and `/logout` are both matched ahead of
the navigate branch because both arrive as navigations, and both would otherwise reach
`fieldNavigationFirst()`, which caches every ok response. Two tests assert the ordering by index
comparison rather than by reading the code.

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

Suite green at **525 tests**. Service worker cache at **`v77-logout-cache-purge`** —
**read the live value out of `app.py` immediately before committing**, never from a note.

**Every review found something, and two were live privilege escalations.** That is the single
most useful fact for the next reader: the implementations were competent, the suites were green,
and the defects were still there. Both escalations passed hundreds of tests because **nothing
exercised the affected account**. See section 6.

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

**None open.** Both bugs found by the 2026-08-06 browser pass were fixed the same day, at the
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

**Four other controls do measure under 44 px at 375 px**, found while checking this and recorded
here rather than fixed, because none was part of the reported item: the skip link (41 px, hidden
until focus), the changelog header button (40 px, and a second instance at 34 px), and an unlabelled
`.toggle-btn` (32 px). They appear on every page, so they belong to the layout shell rather than any
one screen. Worth one deliberate pass rather than four separate fixes.

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

**One thing in this fix is NOT verified, and it is the trigger rather than the geometry.** The
debounced `ResizeObserver` redraw could not be observed: the Browser pane does not composite the
page, `requestAnimationFrame` never runs in it, and a control `ResizeObserver` attached to the same
node did not fire even the initial callback the spec guarantees — both are driven by the rendering
steps. The measurement logic it calls is proven at three widths by re-rendering directly; that the
observer fires is not. **Check it in a real browser** by dragging the window across the breakpoint:
the charts should redraw once per settled width, and the page must not hang.

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
| **Edge and Brave** | every dashboard phase, login redesign, sidebar, What's New, digest modal, P.O. Details, Analytics. **This is now the single largest unverified block in the file** — everything below the line has been driven in one browser only |
| **Skip link visual reveal on real keyboard focus** | layout shell. Structurally unverifiable from here: the pane never advances transitions and its window is never focused, so `:focus` never matches |
| **Offline schedule attachments from a real device camera** | the least-proven part of `709106c` — see below. **The largest genuine risk left in this file** |
| **The provisional-leave supersede notice, in a browser** | `b5dd637` names both leave types on the **approval** path, which the 2026-08-06 pass did not reach — see section 1b |
| **The Analytics print view** | `app-analytics.css` has a real `@media print` block that hides each SVG and reveals its `.analytics-chart-table` as a bordered table. That is a genuinely better print than the page used to produce — and **it has never been print-previewed.** Cheap to check, and the only representation of the charts on paper |
| **Analytics on Edge and Brave** | the SVG charts, the accent-following fills and the print block were checked in one browser only |
| **Analytics keyboard pass** | the filter is a real `<form>` with `Apply` as `type="submit"`, headings run `h1`→`h2`→`h3`, and the scope/error regions are `role="status"` / `role="alert"`. Structure was verified; a full tab-through with visible focus was not |

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
      and the 2026-07-26 handoff document
- [ ] A user-facing change needs a `releases.json` entry dated the commit date, or
      `tests/test_changelog_coverage.py` fails the commit

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

**Running the app for verification:** explicit `MEDICAL_SERVICE_TEST_DB`, never port 5000,
never `preview_start` name-mode, and stop every server afterwards. The Browser pane blocks
origins it has not registered, so open the app with `preview_start` passing the URL.

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
