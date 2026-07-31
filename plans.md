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

## Offline schedule creation for field engineers

**Status:** `Approved — awaiting go-ahead`
**Approved:** 2026-07-31
**Not started.** Do not begin this work until the owner says to.

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
