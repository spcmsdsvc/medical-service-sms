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
