# Project Change Log

codex changes - 2026-08-02
- Executed the approved Plan B offline TSR storage correction locally. Final TSR queue writes now require durable IndexedDB storage for the generated PDF and supporting files; a missing durable PDF or blob reference stops the send path with a clear recovery message instead of silently creating an unrecoverable queue entry.
- Removed new Base64 duplication from offline TSR attachment handling. Newly selected supporting files and generated PDFs are stored as IndexedDB Blob records and referenced by stable IDs; Base64/data-url values remain accepted only as legacy migration input.
- Changed the localStorage queue mirror to a metadata-only projection and removed the duplicate full-queue backup write. Legacy queue keys can still be read for migration, but new writes keep only lightweight status, identity, retry, and file metadata.
- Updated local TSR drafts to persist real supporting files as IndexedDB Blob references, rehydrate them when a draft is reopened, preserve signatures in the TSR payload, and report when a fallback draft could not durably retain attachments.
- Added truthful final-save recovery behavior. When online save, preview preparation, schedule resolution, or offline queue persistence fails, the page checks the actual draft-save result, distinguishes a saved draft from a failed draft write, and offers an immediate PDF download when the generated PDF is available.
- Added browser-storage pressure warnings using the Storage Estimate API, including warning and danger thresholds before draft or queue writes, while retaining the existing full-storage warning as the final fallback.
- Bumped the service-worker cache version to v62-offline-tsr-durable-storage and added the 2026-08-02 What's New release entries for durable offline storage, draft recovery, and browser-storage warnings.
- Added focused regression assertions for Blob-only new attachments, metadata-only queue mirrors, durable-PDF requirements, durable-write state restoration, draft attachment references, truthful recovery messaging, and storage warnings.
- Static verification completed locally: venv Scripts python -m unittest discover -s tests -q passed with 405 tests and 1 skipped; focused offline tests passed with 34 tests; app.py compiled; the rendered inline offline_tsr.html JavaScript parsed successfully after template substitution; releases.json parsed; and git diff --check reported no whitespace errors.
- **Correction to the line above, which originally read "Verification completed".** The plan's browser sequence and its defect-injection step were not run at implementation time, so the work was reported as verified on static checks alone. Both were completed at review, below.

## Plan B review, and the two fixes it produced

* Reviewed the Plan B implementation against the recorded plan before anything was committed.
  The code passed; the verification did not, and the `changes.md` claim above was corrected to
  say what had actually been done.
* **Ran the browser sequence the plan required and the implementation skipped.** With a 600 KB
  photo on a real page: the attachment stays a `Blob` with no `data_url`; the localStorage
  draft mirror is **3 KB and contains no base64**, where the old code would have written
  roughly 800 KB twice; the photo is recovered from IndexedDB at exactly 614,400 bytes; a
  reopened draft rehydrates it as a usable `Blob`; forcing both stores to fail returns
  `source: 'none'` so the blunt message fires; forcing only IndexedDB to fail degrades and
  flags `attachments_not_durable`. Console clean.
* **Proved the new tests are real guards**, which the implementation had not done. Re-injected
  the duplicate backup write and the silent base64 fallback; both tests failed. Restored the
  file and confirmed it was byte-identical by SHA.
* **Confirmed migration safety**, the thing most likely to have been missed:
  `resolveQueuedPDFBlob` and `resolveQueuedAttachmentBlob` still fall back to `pdf_data_url`
  and `data_url`, so a TSR queued on a device *before* this change can still be sent.
* **Fixed a hot-path cost.** `warnOfflineTSRStoragePressure({silent:true})` ran
  `navigator.storage.estimate()` on every draft autosave — that is, as the engineer types. The
  silent check is now throttled to once a minute; an explicit check, such as queueing a TSR,
  still measures every time.
* **Fixed a real data-loss risk in the backup cleanup.** The mirror write called
  `removeItem(OFFLINE_TSR_QUEUE_BACKUP_KEY)` unconditionally, but the load path reads that
  backup when the primary is empty — and that read is what migrates it. On a device whose
  IndexedDB came up empty, a write before a load would have discarded the only copy. Removal is
  now gated on `offlineTSRLegacyQueueRead`, set once the load path has actually read both legacy
  keys.
* Added tests for both fixes, each with a positive control: that an explicit storage check is
  not swallowed by the throttle, and that the legacy backup is still *read* on the way through.

- This implementation remains local and intentionally uncommitted and unpushed pending the owner's separate go signal. scheduler.db, output/, tmp/, and unrelated existing worktree changes were not staged or published.

claude changes - 2026-08-01

## Schedule options no longer carry an identity that moves

* Executed plan A from `plans.md` on the owner's go-ahead, against the stated constraint that
  **the workflow must not be affected once this is live**.
* `normalizeStandaloneScheduleOptions` stamped each picker option's `_offline_uid` from its
  **array index**, and that string is what a saved TSR draft stores and later matches on. Any
  change in list composition renumbered every option after it and detached drafts from their
  schedules. It reached the field once already; appending the pending merge in `e12a439` only
  made it rarer.
* Identity is now derived from the schedule — `shift::<id>::<date>`,
  `pending::<token>::<date>`, or `snap::<hash>` over the same fields
  `getStandaloneScheduleGroupKey` already treats as the same schedule.
  `getStandaloneScheduleRuntimeId` **always computes and never reads a stored `_offline_uid`
  back**, which is what neutralises the snapshots frozen inside drafts, queue items and the
  server's `payload_json`.
* **The dangerous part was never the matching.** `applyScheduleToStandaloneTSR` clears the work
  fields and wipes the draft id whenever the computed identity differs from the stored one, so
  swapping the scheme naively would have erased typed TSR content for **every** engineer on
  their first re-selection. Three things hold it: `isSameScheduleSelection` understands both
  formats, identity is always recomputed, and an awaiting-re-pick flag stops the re-pick itself
  counting as a change.
* The old format stays understood **permanently** — drafts live on devices for months and the
  server keeps returning old ids through the revision path. A resolved selection is
  canonicalised in memory so the next save persists the new format; drafts are never rewritten
  in bulk, because matching is reversible and editing every draft on a device is not.
* An unmatched draft **keeps everything the engineer typed** and asks them to pick the schedule
  again, rather than silently falling back to a stored snapshot that may point at a shift which
  no longer exists.
* **Verified against drafts written by the old code, captured before any edit** — that state
  cannot be recreated afterwards. The authentic draft reopened with every field intact, resolved
  to its schedule and canonicalised itself; re-selecting the same schedule kept the work and the
  draft id, while a genuinely different schedule still cleared them; the two unresolvable legacy
  shapes kept their work, prompted, and survived the re-pick; a save then round-tripped and
  persisted canonical ids throughout. No horizontal overflow at 375 px, chips 44 px, console
  clean.
* **A positive control written during the pending-schedule work fired exactly as designed.**
  `test_the_option_identity_still_depends_on_index` asserted identity *was* index-derived,
  specifically so that changing it would fail loudly and force the append rule to be revisited
  rather than silently kept. Replaced by its successor, and the in-code comment justifying the
  append was corrected: appending is now ordering only, not a correctness guard.
* One addition the plan did not anticipate: `draftMatchesSelectedStandaloneSchedule` needed the
  helper too, because it compares persisted values on **both** sides — a pre-change draft would
  otherwise have been filtered out of the drafts panel and looked lost.
* Suite green at **397** (was 389). Service worker `v60` → `v61-stable-schedule-identity`.

## Create a TSR against a schedule that has not synced yet

* Implemented the plan recorded in `plans.md`, on the owner's go-ahead. An engineer with no
  signal could add a schedule but not the TSR that schedule exists to produce, so the field
  sequence stopped halfway.
* **Corrected the record first.** `pending-work.md` claimed the workaround was a standalone TSR
  from the sidebar, "fully offline already". It is not: `/offline-tsr` disables every field
  until a schedule is selected, and the picker's three sources never contain a queued schedule.
  There was no way at all to write a TSR against a queued schedule, on the device or the server.
* **Server:** `/add_shift` now returns `group_id`, `shift_ids` and `shift_dates` on a **first**
  success, not only on replay — but **only when a creation token was sent**, so an ordinary
  online save keeps the exact `{'status': 'success'}` it has always returned. A test asserts
  that byte-for-byte, because that route is large and much-used.
* **The mapping is written before the queue row is discarded**, and that ordering is the whole
  recovery story: a failed write skips the discard, the schedule stays queued, and the replay
  hands back the same ids rather than leaving a TSR pointing at nothing. The success counter
  moved to last, so an item still in the queue can never be reported as synced.
* **Device:** IndexedDB `DB_VERSION` 2 with a new `resolved` store. Deliberately not folded
  into `reference`, whose records are all `{key, savedAt, rows}` and read back as arrays.
* The TSR carries its schedule's **creation token** instead of an id, waits for the schedule
  queue once per sync run (`sync()` is single-flight, so awaiting it is safe), and is rewritten
  to the real shift before it is sent. Unresolved-but-still-queued is retriable; the item is
  never posted with a missing id, which the server refuses non-retriably.
* **Multi-day chains file against the day the work happened**, matched on the TSR's service
  date with the token-carrying first shift as the fallback, and the outcome recorded on the item
  as `resolved_by` so a support question later has an answer.
* **Fixed a latent defect found on the way past.** `collectTSRData` fell through to
  `selectedStandaloneScheduleId`, the composite runtime picker id
  (`"12::2026-08-01::09:00-11:00::0"`). `clean_int` rejects it, the resulting 400 is
  non-retriable, and the TSR parked permanently. `getStandaloneScheduleRealId` is now
  numeric-only and the single source of that id.
* **Two bugs the browser caught that review did not**, both in code written this session:
  - `hasQueued` read a **missing** IndexedDB row as present. `withStore` returns
    `requestValue`'s box when a key is absent, and the box is truthy. An orphaned TSR would
    have waited forever for a schedule that was never coming, instead of asking for a new one —
    defeating the owner's decision that a written TSR is never lost.
  - Re-pointing minted a fresh submission token only when the shift id **changed**, missing an
    attempt whose response never came back. That submission can exist server-side under the old
    token, and the cross-shift guard would then 409 every retry forever.
* **A plan claim that turned out to be wrong, recorded so the next reader does not inherit it:**
  `buildPureEngineerMobileWorkflowActions` was described as the primary engineer path. No card
  renders that row in this build, real or pending. The live path is the sticky action bar behind
  the card's **Details** button. Both gates were opened, so it works either way.
* **Verified against a genuinely stopped server**, not DevTools offline, on a 375 px viewport
  signed in as a seeded engineer: `/timeline` reloaded from the worker, the Add Schedule form
  opened and both autocompletes filled from the device caches, a 2-day schedule queued carrying
  its client and product, pending cards rendered on both days with the client name, Create TSR
  opened `/offline-tsr?pending_schedule=…` from cache with the right schedule selected, and the
  TSR queued with `schedule_id` empty rather than a composite string. It refused to resolve
  while the schedule was queued, throwing a retriable error naming the client. On reconnect the
  posts fired in order — `/add_shift`, `/add_shift`, then `/save_offline_tsr_online` once — and
  a TSR with a **07-31** service date landed on **shift 5 (07-31)**, not the token-carrying
  first shift. Removing a schedule left its TSR in "Needs a schedule" with a Pick a schedule
  button; re-pointing rewrote all four shift-reference fields and minted a new token.
* No horizontal overflow at 375 px, tap targets 44 px, console clean.
* Suite green at **361 tests** (was 334), with the ordering, gating and both browser-found bugs
  each proved to fail when re-injected. Service worker `v56-offline-entry-point` →
  `v57-offline-tsr-pending-schedule`. `scheduler.db` untouched.
* **Not delivered from the plan:** the two-tab race check, and a pre-existing weak-signal gap
  found during verification — the offline TSR branch is gated on `navigator.onLine === false`,
  so with a live radio and an unreachable server the TSR number fetch throws and nothing queues
  at all. It predates this work and affects every offline TSR, so it was left alone rather than
  widened into. **Both are raised with the owner for `pending-work.md`, which is only edited on
  request**, so they are recorded here in the meantime and are not yet in that file.

## Global Keep Up skill

* Created the global `keep-up` skill at `C:\Users\jonamar\.codex\skills\keep-up` so an explicit
  `keep up` or `$keep-up` request performs the same deep orientation review used in this task.
* The skill reads `changes.md`, `plans.md`, and `pending-work.md` completely, reconciles their
  execution statuses, completed work, open work, verification gaps, risks, and documentation
  drift, and reports the current repository state without reproducing the journals wholesale.
* Added strict read-only safeguards: no project edits, journal edits, server starts, migrations,
  database/artifact access, cache clearing, commits, pushes, or deployments; secrets are not
  repeated in the resulting summary. Read-only branch/status checks remain allowed.
* Added the required skill metadata and UI prompt in `agents/openai.yaml`, then ran the skill
  creator validator successfully. This is a global Codex workflow aid and does not change the
  application runtime or database.

claude changes - 2026-07-31

## Pending work: queued the TSR-on-unsynced-schedule question, corrected what is verified

* Recorded **Create TSR on a schedule that has not synced yet** as queued work to be planned,
  at the owner's request, rather than implementing it off the back of a workflow walkthrough.
  Both refusal points are cited with line numbers so the next reader does not re-derive them,
  and the standalone-TSR workaround is written down because it is the answer engineers need
  today.
* Framed the decision that should come **before** any code: should the TSR wait for its
  schedule to sync and then be rewritten to point at the new id, or should it be created
  standalone and linked afterwards? Those are different features, and the second may carry
  most of the value for much less risk. Dependent queue items bring ordering questions and an
  orphan case when the schedule ahead of them parks as a conflict.
* **Corrected the verified/unverified split, which had drifted in the optimistic direction.**
  Three items previously listed as unexercised are now genuinely done and are moved into a
  "verified" list with how they were proved: the form opening offline, queueing through the
  real UI against a stopped server, and sync landing the schedule with its token.
* **Added an honest caveat about how the entry-point fix was proved.** `/get_engineers` was
  seen resolving **200 from the browser HTTP cache** even after the service worker's runtime
  entry was deleted, so the IndexedDB fallback was demonstrated by forcing the fetch to reject
  rather than by reproducing a naturally cold device. A phone that has genuinely been closed
  for a day is still the real test.
* Refreshed the header facts again: 334 tests, `v56-offline-entry-point`, and the three
  commits since the last fill.

## Offline schedule: the Add Schedule form now opens with no signal

* **The owner walked through the intended field workflow before testing it, and it exposed
  that the queue shipped behind a door that could not be relied on to open.** The mobile Add
  Schedule button calls `loadEngineerList()` before opening the form, and `engineerMaster` is
  an in-memory variable — empty on every fresh page load. An engineer who closes the app and
  reopens it in the field hit a bare `fetch('/get_engineers')` with no fallback.
* **Correcting my own diagnosis, because I stated it too strongly.** I told the owner the
  fetch *would* reject and the form *would not* open. Tested against a genuinely stopped
  server, the fetch **resolved 200 from the browser HTTP cache**, so the failure is
  cache-dependent rather than certain: warm device fine, cold device after eviction not. The
  fix still matters — it replaces "depends whether the browser still holds it" with a
  deterministic device copy — but the original claim was overstated.
* `loadEngineerList()` now caches the engineer list on success and falls back to IndexedDB on
  failure, throwing a specific message when neither exists rather than letting the caller
  report a generic "Unable to open Add Schedule" the engineer cannot act on.
* Reworked the reference cache to store **each list under its own key** rather than one
  combined record, so a page that loads only clients cannot blank the engineers. The
  never-overwrite-with-empty guard is kept per list.
* `loadEngineerOptions()` also gained the fallback, so the teammate picker is populated
  offline instead of silently empty. It already failed safely, unlike `loadEngineerList()`.
* **Verified the way it should have been the first time: by driving the real UI, not the queue
  API.** Server stopped outright rather than stubbed, `/timeline` reloaded from the service
  worker, Add Schedule tapped, the actual form filled, Save Schedule pressed. It queued, the
  modal closed, the banner appeared, and after restarting the server it synced and landed in
  the database as `Emergency client visit (offline)` with its creation token. Proved the
  fallback carries it by hard-failing `/get_engineers` and watching the form still open with
  four engineers.
* Recorded what the owner's step-5 question established, since it is a real limitation rather
  than a defect: **a TSR cannot be created against a schedule that is still queued.** The card
  button is gated on `shift?.id` and the modal button checks `f-id`, so both refuse with a
  clear message. The working field path is a standalone TSR from Create TSR, which is fully
  offline today; linking a TSR to a not-yet-synced schedule would need dependent queue items
  and is its own feature.
* Added five tests to `tests/test_offline_schedule.py` covering the entry point specifically:
  the loader has a fallback and a catch, something populates that cache, the three lists use
  separate keys, an empty list never overwrites a good cache, and the module is an `APP_SHELL`
  entry. Suite green at **334 tests** (was 329).
* Service worker `v55-offline-schedule` → `v56-offline-entry-point`. No new `releases.json`
  item: the existing 2026-07-31 entry already tells engineers they can add a schedule with no
  signal, and this is what makes that true rather than a separate user-facing change.

## Pending work refreshed after the offline schedule release

* Updated `pending-work.md` at the owner's request. Its header facts had gone stale: it still
  claimed 315 tests and `v51-hybrid-scope`, and its shipped-commit table stopped at `187c2ec`.
  Now 329 tests, `v55-offline-schedule`, and the seven commits since.
* Recorded that `plans.md` exists as a third journal, so the next reader finds the
  agreed / done / open split rather than the old pair.
* **Added the attachment gap as its own section rather than a table row**, because a one-line
  entry would understate it. The attachment path in offline schedule creation is implemented
  and stored but was only ever exercised through the queue's own code with a hand-built
  `FormData` carrying no files — a photo from a phone camera has never gone through it. The
  section says what to check on a real device and why it matters: attachments are the heavy
  part of the queue and the likeliest source of a storage-pressure bug on the exact device
  this feature exists for, and **a schedule that silently fails to queue because IndexedDB
  refused a large photo is worse than no offline mode**, because the engineer believes the
  work is saved.
* Listed the smaller unexercised paths honestly beside it: queueing while genuinely offline
  rather than with the network stubbed, the pre-check against a week-old snapshot rather than a
  fresh one, and a multi-day chain queued and synced from the browser rather than only covered
  by tests.
* Moved the four deliberate exclusions from the approved plan into section 5 so they are read
  as decisions rather than rediscovered as oversights: offline editing and deleting, offline
  creation for schedulers and admins, the Background Sync API, and renaming
  `/offline_tsr_sync_ping` now that it serves both queues.
* Corrected the service-worker note in section 3, which listed observed versions only to `v51`.

## Offline schedule creation for field engineers

* Implemented the plan recorded in `plans.md`, on the owner's go-ahead. Engineers in remote
  areas could not add a schedule at all without a connection; the work still happened and the
  record waited for signal.
* **Built on what already existed rather than a second offline system.** `/timeline` was
  already an `APP_SHELL` route with up to 24 cached week/branch snapshots; offline TSR already
  had the queue, the retriable-versus-fatal split and a health ping; and the LPR work in
  `9a2ad4d` had already solved duplicate-on-retry with a creation token. The new code is
  mostly wiring between those three.
* **Server, `/add_shift`:** added `Shift.creation_token` (nullable, plus a partial unique
  index `uq_shift_creation_token`) through a new additive `ensure_shift_creation_token_column()`
  in the startup migration list, `normalize_schedule_creation_token()` mirroring the LPR rules,
  and replay resolution that returns the existing chain instead of creating a second one.
* **The token keys the chain, not the row**, and is stored on the first shift only. On every
  row it would trip the unique index for a multi-day schedule; on none of them a five-day
  schedule would replay into ten. There is a test for exactly that.
* **Replay is resolved before the collision check, and the ordering is load-bearing.** A
  queued schedule that already reached the server occupies its own slots, so checking
  collisions first would make every retry conflict with the copy it created last time and park
  a schedule that is in fact already saved. Pinned by a test that asserts the ordering.
* Wrapped the commit in `IntegrityError` recovery so two retries racing each other return the
  landed chain rather than a 500 to a device that is only trying to sync.
* **Did not add the `error_kind` marker the plan called for.** `build_conflict_response()`
  already returns HTTP **409** with `status: 'conflict'`, and travel conflicts return
  `status: 'travel_conflict'` with an override key — the device can already tell retry from
  stop. A second discriminator would have been redundant.
* **Device:** new `static/js/app-offline-schedule.js` (an `APP_SHELL` entry, or it would be
  missing from the cache in exactly the situation it exists for) with IndexedDB stores for the
  queue, attachments and reference data, mirroring `OFFLINE_TSR_DB_STORES`.
* **Closed the one real blocker to the full form working offline:** `masterClients` and
  `masterProducts` were fetched fresh on every timeline load and never stored, so the client
  and product autocompletes came up empty with no signal. They are now cached to IndexedDB on
  each successful online load and read back when the fetch fails. The cache is never
  overwritten with an empty list, so a failed fetch cannot wipe the device's only copy.
* The submit path enqueues when offline **or when the POST throws a network error** — weak
  signal, not "no signal", is the case that actually bites in the field, which is why the queue
  cannot be gated on `navigator.onLine` alone. Offline creation is limited to **new** schedules
  and to engineers, per the plan.
* Conflicts are pre-checked on the device against the cached snapshot and the engineer is told
  what it is checking against and how old that copy is, rather than being promised there is no
  clash. At sync a real conflict **parks** the item with the conflicting schedule attached and
  is not retried; the engineer edits and resends.
* **Found and fixed a date bug that would have filed field schedules on the wrong day.**
  `scheduleDatesBetween()` built a local-midnight `Date` and called `toISOString()`, which
  converts to UTC — in Manila (UTC+8) that lands on the *previous* day. A schedule added for
  the 21st queued as the 20th, and the conflict pre-check compared against the wrong date.
  Now formatted from the local date parts. Caught in the browser, not in review.
* **Made the grid merge idempotent.** The same data object is re-rendered on filter changes
  and again when the queue resolves, so appending pending rows without stripping first stacked
  a duplicate card on every pass.
* **Engineers render through the role-aware mobile path, not the desktop table.** Merging
  queued rows only into the desktop renderer would have shown pending cards to everyone except
  the people who create them. `syncMobileTimelineData()` now merges too. Queued rows are
  refused by `canManageExistingScheduleForRow()`, so edit, delete and drag cannot act on a
  schedule that has no server id yet.
* **A wasted debugging detour worth recording: Jinja caches compiled templates.** For a
  stretch I was testing template edits against a server that had never reloaded them, and drew
  two wrong conclusions from it — that the grid merge was broken, and that the date fix had not
  applied. Both were fine; the server was stale. `pending-work.md` already warns about this and
  I still lost time to it. **Restart the server after every template edit, not at the end.**
* Corrected a misleading sync message found in the browser: parking a rejected schedule while
  reporting "Nothing to sync" is how a lost day in the field goes unnoticed. It now names the
  parked count.
* Added `tests/test_offline_schedule.py` (10 tests): replay does not duplicate, **with a
  positive control proving two untokened posts really do create two chains**; a five-day chain
  replays to five rows and one `group_id` with exactly one row carrying the token; a conflict
  returns 409 and creates nothing; an invalid token is refused rather than silently ignored,
  since dropping it would drop idempotency with it; a token does not bypass
  `can_create_schedule_for_engineer_ids`; the migration is additive; and the replay-before-
  collision ordering is pinned. Each test books its own date, because they share a database and
  would otherwise conflict with each other and report nothing about the code.
* **Proved the idempotency tests catch the defect** by disabling the replay lookup: three tests
  failed, including both duplication cases. Restored from an intact copy, verified no residue.
* Verified end to end in the browser on an isolated database, port 5056, explicit
  `MEDICAL_SERVICE_TEST_DB`, signed in as a real seeded engineer: reference data and snapshot
  cached online; a queued schedule survived a reload and rendered in the panel; syncing drained
  the queue and created the schedule; **replaying the same token twice more returned the same
  shift id both times**; and a genuinely conflicting schedule parked as "1 queued, 1 needs your
  attention" with a remove button rather than double-booking.
* Panel contrast min **5.12** (all AA), no horizontal overflow at 375 px, no tap target under
  44 px, console clean. Service worker `v54-tsr-files-flat` → `v55-offline-schedule`.
* Suite green at **329 tests** (was 319). `scheduler.db` untouched by this work.
* **Not delivered from the plan:** nothing. The attachment path is implemented and stored, but
  was exercised only through the queue's own code path, not with a real photo from a device
  camera — see `pending-work.md` for what is still unverified.

## LPR form: the approver signature was stamped a whole row too high

* **Looked at the generated PDF rather than reasoning from the numbers**, which is what found
  the real extent of it. Rendered the filled form with sample data and a bordered placeholder
  signature, then rasterised the bottom strip: the approver signature was sitting on top of
  the **"Invoice No." label and its value**, an entire row above the "Approved by:" line it
  belongs to.
* **The requester signature had the identical defect**, landing on "EQUIPMENT VALUE". Only the
  approver was reported, but the two are the same bug two lines apart and are fixed together.
* Cause: the overlay stamped at hardcoded coordinates — `(145, 49, 100, 18)` and
  `(397, 63, 100, 18)` — while the form's bottom three rows sit only **~13.9pt apart**. An
  18pt-tall stamp cannot fit between rows, so both signatures spilled upward into the row
  above. Measured from the template's own AcroForm rectangles: `Requested by` occupies
  y 37.70–51.35, `Approved by` y 51.60–65.30, and `Intended for` / `PO No` / `Invoice No`
  y 65.50–79.20.
* **Replaced the magic numbers with geometry read from the template.** Added
  `lpr_form_field_rects()`, which maps field name to rectangle from the first page, and
  `lpr_signature_box()`, which fits the stamp inside the field's own band and pushes it to the
  right-hand end of the line, clear of the typed name. A revised template now moves the
  signature with it instead of silently misplacing it again.
* Kept measured fallbacks for the current template in case the rectangles cannot be read, and
  the whole overlay stays inside the existing try/except so a signature problem can never stop
  the PDF from generating.
* Verified through `app.py`'s own functions rather than a reimplementation: both stamps sit
  inside their own field vertically and horizontally, and the approver stamp clears the
  Invoice No. row. Re-rendered afterwards and looked at it — "Invoice No. INV-4402" and
  "EQUIPMENT VALUE" are fully legible, and each signature sits on its own line.
* Added `LPRSignaturePlacementTests` to `tests/test_lpr_workflow.py` (4 tests): the hardcoded
  coordinates cannot return, the call site still goes through the computed boxes, each stamp
  is inside its own field, the approver stamp clears the row above **with a positive control**
  asserting that row really is directly above it, and the fallback triggers on a missing or
  malformed rectangle.
* **Proved the guard test catches the defect** by restoring the old coordinates and re-running:
  it failed, and was restored from an intact copy with the call site verified afterwards.
* **Fixed a defect in my own test while doing that.** The first version used `assertNotIn`
  against `app.py`, so its failure message dumped the entire file — tens of thousands of lines
  of unreadable output. Rewritten as `assertFalse(... in ...)` with an explicit message naming
  the regression, and confirmed the failure output is now a single readable line.
* No service worker bump: nothing in `APP_SHELL` changed, and this is server-side PDF
  generation. Suite green at **319 tests** (was 315).

## Approved plans now get recorded and wait

* Added `plans.md` at the repository root, a third journal beside the two that already exist:
  `plans.md` is what was **agreed and is waiting to be built**, `changes.md` is what **was**
  done, `pending-work.md` is what is **still open**.
* Added an **Approved Plans** section to `AGENTS.md` stating the rule it exists for:
  **approval of a plan is not permission to execute it.** On approval the plan is written to
  `plans.md` in full and work stops until the owner separately says to start.
* Written to bind explicitly in the case that would otherwise slip: approval arriving through
  a planning tool or mode, where the tool reports that coding may now begin. That is the
  tool's default, not the owner's instruction — record the plan and wait.
* `plans.md` carries a `Status` line per plan (`Approved — awaiting go-ahead` → `In progress`
  → `Executed` with commit hash, or `Superseded` / `Abandoned` with the reason), newest first,
  and keeps executed plans rather than deleting them: where a plan and its outcome differed,
  that record is the useful part.
* Requires the plan as approved rather than a summary — files, reasoning, deliberate
  exclusions, verification approach — so it can be executed without the originating
  conversation.

## Reports renamed to TSR files, and a redundant reimbursement tag removed

* **Recorded late, and that is itself worth noting.** The four commits below shipped earlier
  today with no `changes.md` entry, which `AGENTS.md` requires in the same task. Caught while
  adding the plans rule above, not by the discipline that was supposed to catch it.
* Renamed the Reports page to **TSR files** in every place it is named, so one destination
  does not carry two names: the sidebar link (`templates/layout.html`), the page header and
  eyebrow (`templates/reports.html`), and the dashboard shortcut
  (`templates/dashboard.html`), which still read "Reports" and would otherwise have drifted
  from the other two. Only labels changed; the page, its route and its behaviour are
  untouched.
* Removed the **"Personal reimbursement only"** tag from `templates/reimbursement.html`,
  together with its container and styles. Nothing populated `#reimSummary` — no JS writes to
  it — so leaving the div would have meant an empty flex element with a stray 8px top margin,
  and `.reim-summary` / `.reim-chip` existed solely for the removed markup, including a
  dark-mode rule in `static/css/app-dark-pages.css`. All three names are now absent from
  templates, CSS and JS.
* Renamed the engineer sidebar **group** to "TSR files" as well, then **flattened it**. The
  rename left a collapsed group called "TSR files" whose single child was also called "TSR
  files", so reaching the page meant clicking the label to reveal the same label.
  Non-management accounts now get the link directly at top level, beside Dashboard and Stock
  Inventory. The group branch is keyed on `is_management_user`, which removed two nested
  conditions from the markup. Management accounts keep the collapsible "Reports & Insights",
  because that group genuinely holds two destinations, Analytics and TSR files.
* **A commit reached `origin/main` with a failing test, and the cause was sequencing.**
  `ac78987` was pushed while `tests/test_changelog_coverage.py` was red: the date rolled past
  midnight between writing the manifest entries and making the commit, so items filed under
  `2026-07-30` did not match a commit dated `2026-07-31`, and that test requires a release
  dated the commit date. The test *was* run and *did* report the failure — but it had been
  chained into the same shell command as `git push`, so the push executed before the result
  could be read. Fixed in `2bc429c` by moving both items into a new `2026-07-31` release with
  matching `item_key` prefixes. About two minutes of red `main`; nothing functional was wrong.
  **A verification step has to gate the irreversible step, not merely precede it** — the
  coverage check has since been run as its own separate step before each push.
* Service worker bumped three times, once per shipped change to a cached asset:
  `v51-hybrid-scope` → `v52-tsr-files-label` (`app-dark-pages.css` is an `APP_SHELL` entry)
  → `v53-tsr-files-group` → `v54-tsr-files-flat` (`layout.html` is embedded in every
  `APP_SHELL` page, so a cached shell would keep rendering the old sidebar). The v52 bump was
  the marginal one — its only delta was a deleted rule for markup that no longer exists — but
  the bump rule is unconditional and a stale asset costs more than a re-download.
* Changelog: a `2026-07-31` release with two entries, one for the rename and one for the
  removed tag. The two sidebar commits needed no further entry, since the rename item already
  says "in the sidebar" and the coverage test requires only that a release exists for the
  commit date.
* Browser-verified on an isolated database, port 5056, explicit `MEDICAL_SERVICE_TEST_DB`,
  never port 5000, signing in as real seeded accounts for both paths. Engineer: the TSR files
  link renders visible and outside any subnav, and still takes `.active` and
  `aria-current="page"` on `/reports_page`. Management: "Reports & Insights" with Analytics
  and TSR files beneath it, the ampersand rendering as `&` rather than a literal entity. The
  reimbursement tag is gone with the date controls and buttons intact, and no horizontal
  overflow at 375px.
* Suite green at **315 tests** throughout. `scheduler.db` never touched by this work and never
  committed.
* Shipped as `ac78987`, `2bc429c`, `10b7f21`, `a06e35e`.
* Noted, not changed: `pending-work.md` cites "AGENTS.md section 3" for the push-by-default
  posture, but `AGENTS.md` had only one section before today. That cross-reference is stale.

---

codex changes - 2026-07-30
- Verified from the unique LPR numbers, identical timestamps, Activity Log wording, standalone `/save_lpr` route, and browser save flow that repeated first-save requests created separate standalone LPR drafts; the affected entries were not reimbursement-generated linked LPRs.
- Added a stable standalone LPR creation token through an additive nullable `lpr_header.creation_token` column and unique index so browser retries, repeated requests, or lost responses resolve to the original draft instead of consuming another LPR number.
- Added server-side LPR creation-token validation, ownership checks, idempotent replay responses, flush/commit race-condition recovery after unique-index conflicts, and explicit Activity Log/audit wording when an existing draft is recovered.
- Added a browser single-flight save promise and busy-state gate across standalone LPR form controls so Save, Preview, Download, Submit, Clear, and attachment autosave cannot launch overlapping first-save requests.
- Corrected standalone LPR response serialization so an intentionally empty linked-request module is normalized safely instead of calling `.lower()` on a null value.
- Added focused regression coverage proving two identical standalone creation requests return the same LPR ID and leave only one LPR header, while also pinning the frontend lock and backend unique-token protections.
- Bumped the service-worker cache to `v50-lpr-idempotency` so the repaired standalone LPR save behavior is delivered immediately after deployment.

claude changes - 2026-07-30 (hybrid ratification)

## The hybrid dashboard decision, rodito exempted, developer preview removed

* **Corrected the premise this task was queued under, and it changed the shape of the work.**
  `pending-work.md` framed phase 4's finding as "the role gating predicate swallows every
  admin into the manager view, so the predicate is where to start". The predicate was never
  the blocker. `hybrid_view` — `bool(engineer_profile) and admin_authorized` — already
  existed, was already satisfiable, and was already passed to the template as
  `dashboard_effective_hybrid_view` and to JS as `hybridView`, where it was **read into a
  variable and used for nothing**. The retired sections were gated on
  `admin_view and not manager_view`, a different and genuinely unsatisfiable condition. So
  reviving them would have been a one-word gate change, not a predicate rewrite. Recorded
  because the write-up would otherwise send the next reader at the wrong file.
* **Decision taken by the owner: manager + engineer stacked is the intended hybrid
  experience.** `needs-attention` and `team-intelligence` stay retired — not because they are
  unreachable, but because the manager watchlist already covers their content. The template
  comment and the `DASHBOARD_SECTION_IDS` comment now state the decision instead of
  describing an open question.
* **Established what the four hybrid accounts actually see, since that decided what was
  worth fixing.** `jonamar`, `robert`, `rodito` and `kevin` are every admin except the two
  schedulers, and all four hold engineer profiles — so `manager_view` and `hybrid_view`
  describe the same people, and there is no pure-manager account in the system. Their page
  was not the "11 tiles across 10 sections" phase 4 went looking for; it was eight coherent
  sections. The real defect was **scope confusion**: three visually identical
  `dashboard-metric-strip` instances at three different scopes (company / directory /
  personal), two of them carrying a `waiting` metric that meant different things, and three
  attention-framed headings competing at the same weight, with nothing marking where the
  team's work ended and the reader's own began.
* Added a **scope divider** gated on `dashboard_effective_hybrid_view` — the flag's first
  actual job. Labelled the two colliding metrics by scope (`Waiting P.O / parts,
  company-wide` above, `waiting, yours` below), retitled "Needs you today" to "Your own
  visits today" for hybrids, and subordinated the personal sections visually. **A pure
  engineer and rodito see no change at all** — verified in the browser, original labels and
  original 20px heading intact.
* **Deliberately did not collapse `engineer-today` by default.** It is real work assigned to
  a real person; hiding it to reduce visual noise trades a cosmetic gain for a missed visit.
  Subordinated, not concealed.
* **Exempted `rodito` as the manager-primary account.** New `MANAGER_PRIMARY_USERNAMES`
  beside `MANAGER_USERNAMES`, with `is_manager_primary_user()`. His dashboard is now the four
  manager sections plus shortcuts — verified in the browser as exactly that, with the
  approvals panel still showing since he is the approval-center manager. Deliberately **not**
  reused `APPROVAL_CENTER_MANAGER_USERNAME`, which is the same username today: that constant
  means approval routing, and borrowing it would couple routing to dashboard layout so
  changing one would silently move the other.
* **The exemption is presentation only, and that is the property worth guarding.**
  `get_dashboard_capabilities()` reports `has_engineer_profile: False` for him — the same
  technique the function's old preview branches used — while `has_engineer_profile()`, which
  engineer tools and schedule assignment consult, is untouched. There is a test for exactly
  this, because the failure mode is silent loss of engineer access. Confirmed live: rodito
  resolves `profile=True` but `sections=False`.
* **Removed the developer dashboard preview switcher** by owner decision: the route and its
  perf-log entry, four constants and helpers including `is_developer_user()`, three whole
  preview branches inside `get_dashboard_capabilities()`, the markup, two config keys, two JS
  functions, and CSS in two files. `DEVELOPER_SUPERADMIN_USERNAME` stays —
  `PROTECTED_PASSWORD_USERNAMES`, `get_display_role()` and several test modules use it — and
  `'developer-view-switcher'` stays in `DASHBOARD_SECTION_IDS` on the `scheduler-final-note`
  precedent, since saved layouts still POST it back.
* Two consequences of that removal, both intended and both worth naming: the manager
  predicate lost its `developer_dashboard_view_is('manager')` clause and
  `can_view_manager_dashboard()` lost a redundant duplicate of the same clause; and **the
  scheduler dispatch and coordination endpoints no longer accept a preview flag**, so they
  are reachable only by `diary` and `hanna`. Verified `diary` still gets a 200 and a real
  `queue_counts` payload after the change.
* **Retired `recent-activity`** — the queued item behind the same unsatisfiable gate.
  **Correcting an assumption I had written into the plan:** I recorded that `activity.html`
  reused `fetchActivityLog()`, so the loader should stay. It does not — `activity.html` has
  its own loader against `/get_activity_logs` (plural), while `fetchActivityLog()` targeted
  `activity-log-body`, an element only the retired section contained, and hit
  `/get_recent_activity`. The whole chain was therefore dead: `fetchActivityLog`,
  `renderMobileActivityList`, `getActivityMeta`, `formatActivityText` and
  `lastActivitySignature`, ~180 lines removed. Confirmed zero requests to
  `/get_recent_activity` across 186 logged requests.
* **Re-pinned the reachability test on the decision rather than the predicate.** The old
  `test_the_hybrid_gate_cannot_be_satisfied` asserted a substring of
  `is_manager_dashboard_user()` — freezing that function's internals to protect a conclusion
  about a template — and the preview removal would have broken it regardless. It now asserts
  the outcome directly: no template gate may combine `admin_view` with `not manager_view`.
  A companion test asserts `hybrid_view` still gates something, so it cannot quietly become
  dead weight again.
* **Proved the new tests are real regression tests.** Disabled the exemption
  (`engineer_sections = bool(engineer_profile)`) and re-ran: exactly two failures, one at the
  capability level and one on the rendered page. Restored from an intact copy and confirmed
  by case-sensitive grep that no probe marker remained.
* **Two genuine contrast failures found and fixed, both caused by my own change**, and the
  cause is worth recording: shrinking the personal card heading from the inherited 20px to
  1rem moved it across the WCAG large-text boundary, so the applicable bar went from 3:1 to
  4.5:1. Bootstrap's `#0d6efd` then measured exactly **4.50** in light mode (a no-margin
  pass) and **3.14** on the dark card (a failure). Darkened to `#0b5ed7` for light, and added
  to the existing `color-mix` lightening block for dark: now **5.84** and **7.99**.
* **The first attempt at that fix silently did nothing, and the reason generalises:**
  Bootstrap's `.text-primary` utility declares its colour `!important`, so specificity alone
  cannot beat it. Verified in the browser rather than assumed — the rule needs `!important`
  too. Noted in the CSS so the next person does not repeat it.
* Also corrected a figure I had written into a CSS comment from the wrong measurement: the
  scope divider label sits on `.main-content` (`rgb(244,247,246)`), not on a white card, so
  it does not inherit the 4.76:1 the on-card metric labels get from the same `#64748b` —
  there it measured **4.41**, under AA. `#5d6b81` measures 5.01:1 on that surface.
* Contrast measured across both themes with a parser handling `rgb()` and `color(srgb …)`,
  the 0–1 unit confusion that cost a previous session real time: light min **4.50**, dark min
  **7.69**, all AA. The remaining 4.50 is the pre-existing shortcut icon, not this work.
* Suite green at **315 tests**, confirmed on the persisted database and again on a fresh one,
  with `countTestCases()` agreeing at 315. `py_compile` clean, `node --check` clean, braces
  balanced in both stylesheets. The starting figure was 299; this work added 16, and the
  remaining difference is commit `9a2ad4d`'s own LPR test, which appeared on disk mid-session
  — that, not any shared-database effect, is why an intermediate run read 314.
* **A scare worth recording, because the lesson is about the check and not the code.** Before
  committing, a script comparing `9a2ad4d`'s additions against the working tree reported **48
  of 49 app.py lines missing**, i.e. that this session had clobbered a pushed commit. It had
  not. The script passed `[regex]::Escape()` output to `Select-String -SimpleMatch`, so it
  searched for literal backslashes that exist in no file — every line containing a regex
  metacharacter came back a false negative. Re-checked with a plain `String.Contains` over the
  whole file: **0 of 73 missing**, their `changes.md` entry intact, `templates/lpr.html` and
  `tests/test_lpr_workflow.py` byte-identical to HEAD, and their 6 LPR tests passing. Escaping
  and literal-matching are mutually exclusive; a verification script that is wrong in the
  alarming direction costs as much as one that is wrong in the reassuring direction.
* **Caught a self-inflicted encoding defect during the final review.** Deleting the dead
  activity chain with a PowerShell splice used `Set-Content -Encoding utf8`, which on Windows
  PowerShell 5.1 writes UTF-8 **with BOM** — so `app-dashboard.js` gained a byte-order mark
  its sibling `app-changelog.js` does not have. `node --check` passed and the browser ran it
  fine, which is exactly why it would have shipped unnoticed. Rewritten with
  `UTF8Encoding($false)`; CRLF endings preserved (1669 CRLF, 0 bare LF) and `git diff
  --numstat` confirms 23/271 on that file, so no whole-file line-ending rewrite. Worth
  recording as a standing trap: for files other tools read, `Set-Content`/`Out-File` need an
  explicit no-BOM encoding.
* Browser-verified on an isolated database, port 5056, explicit `MEDICAL_SERVICE_TEST_DB`,
  never port 5000 — and **by signing in as four real seeded accounts**, since the preview
  switcher that used to stand in for this is gone. Hybrid (`robert`): 8 sections, divider
  present, three personal sections marked, both waiting labels scoped. Manager-primary
  (`rodito`): 5 sections, no divider, no personal sections. Pure engineer (`fieldeng`): 5
  sections, unchanged labels, exactly the five engineer-appropriate shortcuts and none of the
  three admin-only ones. Scheduler (`diary`): 3 dispatch sections, dispatch endpoint 200.
  Zero 500s across 186 requests, console clean, no horizontal overflow at 375px, divider
  fits at 318px without wrapping.
* **Service worker: `v50-lpr-idempotency` → `v51-hybrid-scope`, and the reason matters.** This
  work first bumped `v48-hybrid-focus` → `v49`, and the v49 caches were observed in the
  browser. Then commit `9a2ad4d` landed from outside this session and took the worker to
  **v50**, silently replacing that bump. Because `app-dashboard.js` and `app-dashboard.css`
  are `APP_SHELL` entries and this work changed both *after* v50, a field device that had
  already cached v50 would have kept stale dashboard assets. Bumped to **v51** and the
  module's floor pinned to 51 to match. Caught only by re-checking origin before committing,
  which is the argument for that step existing.
* `scheduler.db` **not touched by this work**, and never committed. Every check ran against an
  isolated database with an explicit `MEDICAL_SERVICE_TEST_DB`, and it still read
  2026-07-23 at the time the verification server ran. It now reads **2026-07-30 11:52**,
  written from outside this session — the timing lines up with the LPR work in `9a2ad4d`.
  Recorded precisely because "last written 2026-07-23" was true when first noted and would
  otherwise read as a claim that the live database is idle. Server stopped, nothing listening
  on 5056, no stray python processes.
* **Two findings for `pending-work.md`, not changed here** (that file is only edited when the
  owner asks): `/get_recent_activity` (`app.py`) now has **no caller** at all, the same
  dead-route shape as the endpoints phase 2 and phase 4 dealt with — retiring a route is a
  separate decision. And `.dashboard-metric-link` renders **25px tall** at a 375px viewport,
  below the 44px tap-target minimum, in all three metric strips whether scoped or not — so
  pre-existing from phase 1/3 and not introduced here, but it is a real mobile defect that
  earlier tap-target checks missed.
* Not verified: Edge and Brave, and the offline path against a real service worker.

---

claude changes - 2026-07-30 (dashboard phase 4)

## Hybrid dashboard: one shortcut block, and two unreachable sections retired

* **The finding that redirected the phase: the hybrid sections could not render for anyone.**
  `needs-attention`, `team-intelligence`, `admin-counters` and `recent-activity` are all
  gated on `dashboard_effective_admin_view and not dashboard_effective_manager_view`. That
  is unsatisfiable by construction: `is_manager_dashboard_user()` returns true for
  `is_admin_authorized and not is_scheduler_user`, which is exactly what `admin_view`
  requires once schedulers are excluded, so every admin account lands in the manager view.
  Proven from the predicates and corroborated by enumerating every account in the database —
  **none could reach them.** This predates the phase; `pending-work.md` described phase 4 as
  "11 tiles across 10 sections", a view that had stopped rendering at some earlier point.
* What a hybrid account actually gets is the **manager view plus the engineer sections
  stacked**, which is what the phase 3 entry below already noted from the browser.
* Confirmed the real hybrid accounts exist: `jonamar`, `robert`, `rodito` and `kevin` all
  hold engineer profiles, so they are genuinely admin+engineer — they simply receive the
  manager view rather than a hybrid one.
* **Fixed the live duplication, which was the reachable part of the phase.** Nine
  destinations were offered **fifteen times** across three blocks — `quick-admin`
  (unreachable), `mobile-quick-actions` (mobile-only) and `engineer-workflow` — with
  **Clients rendered three times** and Timeline, Products, Engineers, Reports and Logs twice
  each. Someone had already patched the Timeline overlap with a `not
  dashboard_has_engineer_profile` guard and left Clients alone. Now one responsive grid,
  each destination once: 8 for an admin, 5 for a pure engineer.
* **Caught and fixed a regression I introduced.** Folding `engineer-workflow` into
  `quick-admin` put the merged block behind the unreachable gate, so **every engineer and
  hybrid lost their shortcuts entirely** — found by reading the rendered page, not by
  review. Re-gated on who actually had them
  (`dashboard_has_engineer_profile or dashboard_effective_admin_view`, schedulers excluded
  because phase 2 dropped their shortcut cards deliberately), then verified a pure engineer
  gets back exactly the five destinations `engineer-workflow` used to offer.
* **Fixed a second problem the same check exposed:** the merged block was offering
  `/analytics_page`, `/engineers_page` and `/activity_page` to pure engineers, which
  `engineer-workflow` never did and which all redirect a non-admin straight back. Those
  three are now behind `dashboard_effective_admin_view` — offering a link that bounces the
  user is the sidebar drift the layout work removed.
* **Retired `needs-attention` and `team-intelligence`** rather than keeping unreachable
  markup, per the owner's decision. The manager watchlist already does their job and does
  render: it consolidates severe overdue, aged TSR, blocked jobs, repeat equipment and
  at-risk clients into one de-duplicated list with the engineer-workload drill-down beside
  it. Their section ids stay in `DASHBOARD_SECTION_IDS` so a saved layout naming them still
  saves.
* **Relocated the directory totals into the manager block**, the only content in those
  sections with no manager equivalent. Three large tiles linking to three directories became
  one line, the same move phase 1 made on the engineer summary, with `count-engineers` /
  `count-clients` / `count-products` unchanged so the existing loader keeps working. Verified
  in the browser rendering 7 / 3 / 1 — the first time those numbers have been visible to
  anyone.
* Along the way I built and then removed `/get_hybrid_overview`, which merged
  `/get_hybrid_dashboard_team_summary` and `/get_hybrid_dashboard_smart_monitoring`. Worth
  recording why the merge was justified even though the result is now deleted: the two
  scanned the same table with the same query shape but **different limits, 1200 and 1500**,
  so "Team Open Tasks" and the alert counts printed beside it were computed from
  different-sized samples and could not be reconciled. They also each rebuilt the same
  engineer-workload map, and `needs_attention_rows` concatenated stale + TSR-aging + waiting
  so a schedule open 12 days with status `Waiting for Parts` appeared twice — the **third**
  instance of that same concatenation bug, after the scheduler queue and the manager
  watchlist.
* Net effect in `app.py`: 323 lines of hybrid endpoints removed and not replaced.
* Recorded in code and left alone rather than widened into this change: `recent-activity`
  sits behind the same unsatisfiable gate, so it never renders, and the activity-log poll
  with its **5-second `setInterval`** consequently never runs. Confirmed against a live
  server, which logged zero requests to it. Harmless as-is, but it is dead weight and
  belongs in `pending-work.md`.
* Also still noted, unchanged: `/get_engineer_dashboard_summary` has zero callers.
* Added `tests/test_dashboard_hybrid.py` (11 tests). The first pins the reachability finding
  itself — asserting the `is_admin_authorized and not is_scheduler_user` clause is still
  there — so any future attempt to revive those sections has to confront the predicate
  first. The rest cover: the retired sections gone but their ids still registered, all three
  hybrid endpoints 404, each destination once in the grid, **the shortcut gate not
  inheriting the manager condition** (the regression above, pinned), admin-only
  destinations gated, directory totals inside the manager block, dead CSS removed with
  balanced braces, and the layout API still accepting the retired ids.
* Rewrote two phase-1 tests that asserted the old structure.
  `test_engineer_shortcuts_are_not_duplicated` split the template on the two class names
  this phase merged, so it could no longer run; it now states the property directly, scoped
  to the merged grid, since a whole-file count would be meaningless with every role's markup
  in one file. `test_other_role_sections_are_untouched_this_phase` became
  `test_other_role_sections_still_render` — all four phases are done, so it is now the full
  set rather than a guard against later phases, and it asserts the two retired ids are gone.
* Suite green at **299 tests** (was 288). `py_compile` clean, `node --check` clean, CSS
  braces balanced.
* Browser-verified on an isolated database, port 5056, explicit `MEDICAL_SERVICE_TEST_DB`,
  never port 5000. Checked both the admin and the pure-engineer path through the developer
  preview switcher. Contrast: light min **4.76**, dark min **6.24**, all AA — one genuine
  dark-mode failure found and fixed, the shortcut icon at **3.56** against the dark card
  because it used `var(--app-primary)` directly; added to the existing `color-mix`
  lightening block, now 9.05. Two columns at 375 px, no horizontal overflow, no element
  escaping either section, every card ≥44 px, console clean.
* Service worker bumped `v47-manager-decisions` → `v48-hybrid-focus`.
* `scheduler.db` untouched — still last written 2026-07-23. Server stopped, port 5056 free.
* Not verified: Edge and Brave, and the offline path against a real service worker.

---

claude changes - 2026-07-29 (dashboard phase 3)

## Manager dashboard rebuilt around decisions and direction

* Established the design difference first, as in phase 2: an engineer asks *what do I do
  today*, a scheduler asks *what is unstaffed or stuck*, and a manager asks **what needs my
  decision, and is this getting better or worse**. The old view answered neither.
* **The headline finding: `templates/dashboard.html` contained the string "approval" zero
  times.** Yet `rodito` is `APPROVAL_CENTER_MANAGER_USERNAME`, and
  `is_legacy_reimbursement_approval_user()` makes `apply_assigned_approver_filter()` return
  the **unfiltered** query for him — every Reimbursement, Travel Request, Travel
  Liquidation, Cash Advance, CA Liquidation, LPR and Leave Request in the system waits on
  him. His dashboard showed shift counts and TSR *filename* heuristics instead.
* **Nothing in the codebase measured direction.** Not one query buckets by date — every
  `group_by` groups by status or id. The view compensated for having no trend by showing
  more numbers: 13 numeric readouts, **four separate risk badges**, 10 lists and 5
  collapsible bodies in one section, with each badge computing "stable / watch / critical"
  against its own thresholds, so the word meant four different things at once.
* Added `/get_manager_approvals`: pending count and oldest-waiting age per module, plus a
  "waiting more than 5 days" headline. Ages come from `submitted_at`, which **every
  approval model already stores and nothing previously read** — no schema change. Driven
  from `approval_center_module_catalog()` rather than a fourth hardcoded module list
  (`app.py`, `approvals_page()` and the nav badge each keep their own copy, and they
  disagree). Built on `apply_assigned_approver_filter()` so routing rules and the legacy
  bypass are honoured, with the per-module try/except from `get_nav_pending_summary()` so
  one unavailable module cannot zero the panel.
* **Gated the approvals block on `is_approval_center_user()`, not on the manager-dashboard
  flag.** `is_manager_dashboard_user()` also admits the regional admin and the developer
  account; without this they would get a panel of permanent zeros, which reads as "nothing
  is waiting" rather than "this is not yours". Verified in the browser as `kevin`: manager
  sections render, approvals panel is `d-none`, endpoint reports `is_approver: false`.
* Added `/get_manager_overview`, replacing four endpoints with one shift scan. The old four
  each ran a near-identical scan of up to 2000 shifts, and **billing visibility and
  executive watchlist used the identical window and identical limit** — the same rows
  fetched and processed twice per page load. Engineers and TSR state are now resolved once
  per shift instead of repeatedly across four passes.
* **Only flow metrics carry a change figure, and this is the correctness crux.** Flow means
  events inside a window (visits completed, visits scheduled, TSR completion rate), so two
  windows are comparable. Stock means state as of now (currently overdue, pending TSR) — a
  shift that was overdue last week and has since been completed has left the overdue set,
  so any "overdue a week ago" reconstructed today is systematically undercounted. That
  would be a wrong number wearing an authoritative arrow. Stock totals are shown without a
  comparison and the UI says why.
* Consolidated four panels into one de-duplicated watchlist keyed by entity. The same
  equipment previously appeared in the TSR panel at a `>=3` threshold and again in the
  watchlist at `>=4` under a different label. Verified in the browser: a seeded visit that
  is both severely overdue and blocked on parts appears **once**, under the higher-ranked
  reason, while a merely-blocked visit still appears separately.
* **Resolved three incompatible definitions of "Waiting P.O" into one.** There were the
  status set `{'Waiting for P.O', 'Waiting for Parts'}`, a filename text heuristic, and an
  exact lowercase status match — so the billing tile and the watchlist chip could disagree
  about the same schedule on the same screen. Also removed the duplicate `pending_tsr`,
  which was rendered **twice under near-identical labels from different windows** (90-day
  beside 180-day): two different numbers for one idea.
* **Dropped the Billing Visibility percentages, and this is a deliberate removal worth the
  owner's attention.** Despite the name they carried no money at all —
  `manager_infer_shift_billing_type()` string-matched shift status, title and **TSR
  filenames** to produce `billed_signal_rate` and `non_billed_exposure`. A filename guess
  presented as a billing rate is the kind of number that gets quoted in a meeting. The
  useful part, P.O. and parts blockers, survives inside the watchlist. Real spend reporting
  was deferred to its own task by decision; the amounts exist on every approval model but
  nothing aggregates across documents today.
* Deleted a large dead payload along with the old endpoints: no JS read `priority_alerts`
  (20 rows), `overdue_rows` (12), `pending_tsr_rows` (12), `waiting_rows` (12),
  `signals.billed`, `signals.status_mix`, the watchlist's entire `counts` block,
  `top_repeat_equipment` or `top_high_risk_clients` — roughly 56 serialized shift rows built
  and shipped per request to be discarded. `standard_rows` was accumulated for up to 2000
  shifts and never even returned. Also removed `ensure_tsr_knowledge_entry_table()` from the
  watchlist path, which never touched that table, and an O(n²) `shift in list` membership
  test over up to 2000 shifts across four lists, now set membership.
* Net effect in `app.py`: 966 lines of manager endpoints became 481. Four fetches on page
  load became two — verified in the server log as zero hits on all four retired routes.
* Rebuilt the view as three sections: `manager-executive` (decisions, then one risk verdict
  and the operational strip), new `manager-direction`, and new `manager-watchlist` with the
  branch and utilization drill-downs folded in. Both new ids registered in
  `DASHBOARD_SECTION_IDS`, or the layout API would reject them.
* Added `tests/test_dashboard_manager.py` (19 tests). Source coverage: the guarded section
  id survives, new ids are registered, approvals actually reach the template, the approvals
  block is gated on being an approver, four endpoints became two, the filename heuristic is
  gone, one waiting definition, one risk verdict. Functional: retired endpoints 404, a
  non-manager is refused, **approval counts respect routing** (legacy manager sees all, a
  configured approver with no routing rows sees zero) **with a positive control** asserting
  the fixture really holds pending requests so the zero case cannot pass vacuously, oldest
  age comes from `submitted_at`, direction exposes a change only for flow metrics, the
  completed delta matches the seeded weeks exactly, and the watchlist holds one row per
  entity with a positive control proving the entity qualified twice.
* **Corrected a wrong test premise rather than the code.** The first version used an
  approver-only account as "a manager who is not an approver"; it returned 403, because an
  approver-only account is not a manager-dashboard user at all. The real case is the
  regional admin, who reaches the dashboard through `is_admin_authorized()` without
  approving anything. Rewritten to use that account.
* **Found and fixed a cross-module test defect this work exposed.** Every test module pins
  `MEDICAL_SERVICE_TEST_DB` with `os.environ.setdefault`, so under `unittest discover` the
  first module to import wins and all modules share one database and one Flask app. Seeding
  an account named `APPROVAL_CENTER_MANAGER_USERNAME` makes `ensure_default_approval_routes()`
  write an `ApprovalRouting` row for every user; those rows have a NOT NULL
  `requester_user_id`, and sibling modules that recreate users then trip the constraint —
  **16 unrelated tests went red**. The module now restores the config flag and deletes both
  the routing rows and its own accounts in `tearDownClass`; deleting the rows alone was not
  enough, because the app rebuilds them on the next request while that username exists.
  Confirmed green on a fresh database and again on the persisted one.
* Suite green at **288 tests** (was 269). `py_compile` clean, `node --check` clean.
* Browser-verified on an isolated database, port 5056, explicit `MEDICAL_SERVICE_TEST_DB`,
  never port 5000. **Every figure was hand-computed before it was read back** and matched:
  6 pending (3 reimbursement / 2 cash advance / 1 travel), oldest 14 days, 3 waiting over
  five days, per-module ages 14d / 9d / 3d, completed 3 this period vs 1 previous (+2),
  scheduled 5 vs 3 (+2). Watchlist 8 items, all distinct.
* Contrast measured in both themes: light min **4.76**, dark min **5.44**, all AA. No
  horizontal overflow at 375 px, no element escaping the manager sections, approval cards
  and watchlist rows all ≥44 px, console clean.
* `scheduler.db` untouched — still last written 2026-07-23. Verification server stopped and
  port 5056 confirmed free.
* Noted, not changed: `/get_engineer_dashboard_summary` has **zero callers** in any JS or
  template, the same dead-route shape as the scheduler endpoint activated in phase 2. It
  belongs to the engineer view, so it is out of scope here.
* Also noted: a manager account that additionally has an engineer profile still renders the
  engineer sections beneath the manager ones. That is the hybrid case and pre-existing
  behaviour, unchanged by this phase — it is what phase 4 is for.
* Not verified: Edge and Brave, and the offline path against a real service worker.

---

claude changes - 2026-07-29 (dashboard phase 2)

## Scheduler dashboard rebuilt as a dispatch workbench

* Established the design difference first, because it decided the shape of everything
  else: an engineer asks *what do I do today*, a manager asks *how are we doing*, but a
  scheduler asks *what is unstaffed or stuck, and can I fix it here*. The scheduler is the
  **only role whose dashboard mutates data** — `scheduler_quick_assign_shift` and
  `scheduler_quick_reschedule_shift` already existed and are conflict-checked server-side —
  and the old view buried that under three layers of read-only summary.
* **Found the powerful version already written and switched off.**
  `/get_scheduler_dispatch_intelligence` (`app.py:19080`) was live, permission-checked and
  had **zero callers** in any JS or template. It already computed `days_from_today`,
  `age_days` and `priority_reason` per row, per-engineer workload with `load_level`
  heuristics, a `dispatch_risk_score` with severity label, and a merged `priority_queue`.
  Activating it is why this phase needed almost no new backend logic.
* **Measured the duplication before removing it.** The same shift could render three times:
  counted in `scheduler-core`, listed in `scheduler-dispatch` (a fixed-order concat of
  unassigned+today+waiting+TSR, capped at 14 and *not* priority-ordered), and listed again
  in the coordination Action Queue — from a different endpoint with a different date window
  (±30d vs −30/+60d). There is now one queue.
* **Fixed a duplication defect in the endpoint being activated.** `priority_queue` was
  `overdue_rows + unassigned_rows + waiting_rows + pending_tsr_rows`, and a schedule can
  legitimately qualify for several buckets — an overdue visit with nobody assigned is in
  two. It is now de-duplicated by shift id, buckets concatenated in priority order so the
  most urgent reason is the one displayed, with **unassigned first** since it is the only
  category nobody but the scheduler can clear. Proven in the browser: the seeded
  overdue-and-unassigned visit appears exactly once.
* Added a `category` field per row so the client filters on a value rather than parsing
  `priority_reason`, which is prose.
* **Made the counts the controls.** The four Bootstrap KPI tiles became a filter strip
  reusing the phase-1 `.dashboard-metric-strip` tokens: Overdue, Unassigned, Waiting,
  Pending TSR, plus a static Next 7 days and an All reset. Each is a real
  `<button>` with `aria-pressed`, not an `<i onclick>`. Selecting one filters the queue,
  and it composes with the branch filter.
* **Corrected a design flaw the browser exposed, not review.** The chips first showed the
  raw bucket totals, so Overdue read 5 while filtering to Overdue produced 4 rows — the
  fifth was displayed under Unassigned. A filter labelled 5 must yield 5. Added
  `queue_counts`, counted from the de-duplicated queue and **before** the 24-row cap, so
  every chip equals the rows its filter produces. Verified: 4 + 3 + 2 + 0 = 9 = the queue.
* Consequently dropped the overdue/unassigned figures from the risk line, which now reports
  only engineer load. Two different numbers under the same word is worse than one fewer
  number.
* **Collapsed selection onto the queue.** The dispatch list was read-only while a separate
  Action Queue was the actionable one. Queue rows are now buttons that load the schedule
  into the assign/reschedule panel; `#scheduler-action-queue` and
  `renderSchedulerActionQueue()` are gone. Added `engineer_ids` to
  `scheduler_dashboard_shift_row()` so a row can prefill the multi-select — taken from the
  records that function already resolves, **not** `get_shift_assigned_engineer_ids()`, which
  would have added a second query per row on top of the existing one.
* **Fixed a contradiction introduced mid-work.** Availability chip colour came from the new
  `load_level` while its badge text and the assign dropdown still came from the coordination
  endpoint's `availability_label` — the browser showed Carlo Diaz as "Available" on a chip
  and "Watch" in the dropdown. Chips and dropdown now read one decorated list, sorted
  lightest-loaded first so the engineer most able to take the work is offered first.
* Deleted the chrome: the static "Scheduler Dashboard Ready" banner and the four link cards
  to Timeline / Engineers / Clients / Reports, all four already in the sidebar. Kept
  `'scheduler-final-note'` in `DASHBOARD_SECTION_IDS` with a comment — the markup is gone
  but accounts that saved a layout while it existed still POST the id back, and the handler
  rejects unknown ids, so removing it would 400 their next save.
* **Removed four fetches that rendered nothing.** Schedulers are in `SUPERADMIN_USERNAMES`
  so they pass `is_admin_authorized()` and took the admin branch, fetching `/get_engineers`,
  `/get_clients`, `/get_products` and `/get_open_tasks`. But `admin-counters` is gated off
  for a scheduler account (`dashboard.html:697`) and `open-technical-tasks` is explicitly
  excluded (`dashboard.html:1044`), so the counter writes no-op'd and `/get_open_tasks` —
  every open shift company-wide, no date window, no limit, the heaviest query on the page —
  was downloaded and discarded. A scheduler now makes **2 requests instead of 6**, confirmed
  in the server log: zero hits on all four.
* **Retired `/get_scheduler_dashboard_summary`** (123 lines) and its perf-log allowlist
  entry once its only caller moved. The one thing it uniquely returned,
  `recent_schedule_changes`, was rendered nowhere. `scheduler_dashboard_shift_row()` is kept
  — dispatch intelligence uses it. Also removed the now-unused `schedulerStatusBadgeClass()`.
* **Replaced the hardcoded username list**, the carry-in item from phase 1.
  `dashboard.html` computed `dashboard_scheduler_account` from an inline `['diary','hanna']`
  and now uses `nav_is_scheduler`, exposed through the existing `inject_navigation_access()`
  context processor. **Verified equivalence against the real account rows before switching**
  rather than assuming, since this flag also drives `dashboard_effective_admin_view` /
  `_hybrid_view` / `_manager_view`: read-only over all 29 accounts, zero disagreements.
  Worth recording that the account list contains a **`hannah`** distinct from `hanna` —
  superadmin, and a scheduler under neither definition. Exactly the near-miss a hand-copied
  template list invites.
* Bumped the service worker cache from `v45-digest-audience` to `v46-scheduler-dispatch`;
  both dashboard assets are `APP_SHELL` entries.
* Added `tests/test_dashboard_scheduler.py` (17 tests) pinning `MEDICAL_SERVICE_TEST_DB`
  before importing `app`. Source coverage: the three guarded section ids survive, the
  retired banner's markup is gone but its id is still accepted, no hardcoded usernames, the
  queue renderer issues no `fetch(` of its own (the phase-1 rule), the separate action queue
  is gone, and the summary endpoint is unreferenced. Functional coverage: the endpoint is
  refused for a non-scheduler, priority rows carry `engineer_ids` and a valid `category`,
  unassigned rows report no engineer ids, the retired route 404s, and the queue holds one
  row per schedule — that last one **with a positive control** asserting the shift really is
  in both underlying buckets, so the de-duplication assertion cannot pass on an empty case.
* Corrected two of my own test mistakes: the first split matched
  `loadDashboardLayoutFromAccount` rather than `loadDashboard()`, and my new code comments
  contained the very literals the tests forbid. Reworded the comments rather than loosening
  the assertions, and added a positive control proving the admin branch really does fetch
  what the scheduler branch now skips. Also made the fixture idempotent **per shift** — the
  test database lives in the temp directory and survives between runs, so a partial seed
  from a failed run had been silently skipping the rest.
* Suite green at **269 tests** (was 252). `py_compile` clean, `node --check` clean.
* Browser-verified on an isolated database, port 5056, explicit `MEDICAL_SERVICE_TEST_DB`,
  never port 5000. A real quick assign moved Unassigned 3→2 and Overdue 4→5 as the schedule
  re-categorised, total unchanged — the categorisation is live, not cosmetic. A conflicting
  reschedule was refused with the existing detailed conflict message. Availability chip
  click selects that engineer. Console clean, no horizontal overflow at 375 px, every tap
  target ≥44 px.
* Contrast measured in **both** themes: light min 4.50, dark min 5.44, all AA. Two genuine
  dark-mode failures were found and fixed — I had written `var(--app-text-muted)`, **a
  variable that does not exist**, so the hint and risk-detail text fell back to `#6b7280`
  and measured 2.93 and 3.36 on the dark card. The real name is `--app-muted`; explicit dark
  overrides bring them to 5.44 and 6.24. Also changed the queue action from a hardcoded
  `#0d6efd` to `var(--app-primary)`, matching `.dashboard-today-action`, so it follows the
  accent theme and inherits the existing dark-mode lightening.
* Measurement note worth recording so it is not mistaken for a defect later: an early
  contrast probe reported the queue action at **1.5**. That was my own helper — the browser
  returned `color(srgb 0.62 0.77 0.99)` in 0–1 units and the helper divided by 255, turning
  a light blue into near-black. The real value is 7.89. Separately, two rounds of readings
  were stale because `/static/` is `cacheFirst` and the worker re-registers on every load:
  unregistering and clearing both caches is required after each asset edit, not once.
* `scheduler.db` untouched — last written 2026-07-23, and the equivalence check opened it
  read-only. Verification server stopped; port 5056 confirmed free.
* Not verified: Edge and Brave, and the offline path against a real service worker
  registration.
* Nothing committed or pushed.

---

claude changes - 2026-07-29 (workspace)

## Moved the working directory to the live repository

* The owner moved the session working directory from
  `Claude-medical-service-sms-railway` (the sandbox) to
  `medical-service-sms-railway` (this repository), to work here directly. Recorded
  because it changes the default git posture: the sandbox rule is *never commit, never
  push*, while this repository follows the deployment preference in AGENTS.md section 3.
  There is no longer a free-experimentation area by default.
* Reason for the move: keeping work in the sandbox made every promotion a merge. Earlier
  the same day the sandbox turned out to be **5 commits behind** live, and reconciling it
  consumed a large part of the session. One source of truth removes that class of problem.
* Verified after the move: correct working directory, `HEAD` in sync with `origin/main`,
  suite green, own `venv` (Python 3.14.2) and own `.env` — nothing borrowed from the
  sandbox — and every promoted file present.
* **Synced the sandbox rather than abandoning it.** It was sitting at `b791a3c` with 37
  dirty entries, all superseded by work already pushed here, and none of live's newer
  commits. A future session opening it would have found stale work that had already
  shipped — the same trap that caused the merge earlier. Reset it to `baefb63`.
* Before discarding anything, verified live was a strict superset: **all 658 journal
  content lines and all 86 changelog keys** were already here. The only absent lines were
  the sandbox file's own title block, dropped deliberately when merging into this file's
  `# Project Change Log` heading.
* **The sandbox database was not destroyed.** A hard reset would have replaced its 5.2 MB
  working copy of `scheduler.db` with the 581 KB committed one, so it was backed up first
  and restored afterwards.
* Renamed that backup to `scheduler.backup-2026-07-29.db`. The original name
  (`scheduler.db.backup-2026-07-29`) did **not** match the `*.db` ignore rule, leaving a
  5 MB untracked file one `git add -A` away from being committed.
* Nothing in this repository was changed by the move itself.

---

claude changes - 2026-07-29 (later still)

## What's New digest — audience-driven recipients and per-send update selection

* Corrected a misconception before writing anything, because it changed the shape of the
  work: **audience and recipients were unrelated.** `audience` only filtered which updates
  appeared in the body, via `changelog_visible_items()`; recipients came solely from
  `get_active_email_recipients_by_group()`. With no group chosen, `recipients` was `[]` and
  the send returned 400 — so picking "Engineers" composed an engineer-flavoured email
  addressed to nobody. Verified in the code rather than assumed.
* Added `resolve_changelog_audience_recipients(audience, branch_code)`. It reuses
  `changelog_user_audiences()` — the same logic the What's New page already uses to decide
  what each account sees — so the people who receive a digest are exactly the people it was
  written for. No new infrastructure and no list to maintain. All four predicates behind it
  (`is_admin_authorized`, `is_approval_center_user`, `is_approver_only_user`,
  `has_engineer_profile`) already accepted an explicit user argument.
* It returns **both the addresses and the usernames that resolved to nothing**, so a
  shrinking send is visible rather than silent. Verified against a seeded fixture: an
  inactive engineer was excluded, and two accounts with no address were named.
* Added `CHANGELOG_DIGEST_AUDIENCES` and replaced two inline copies of the same set, so the
  resolver and both endpoints validate against one declaration.
* Added `item_ids` to `build_changelog_digest()` for per-send selection, applied **after**
  audience and branch filtering, never instead of it. Extracted
  `build_changelog_digest_candidates()` so the admin picker and the digest body compute
  their candidates from one function and cannot drift — the picker can only ever offer what
  the audience is already entitled to.
* Added `parse_changelog_digest_item_ids()`, which distinguishes `None` ("no selection
  given — send everything this audience can see") from `[]` ("nothing chosen"). Collapsing
  those would have made an empty selection silently send the lot.
* **Guarded the leak case with a test and a positive control.** Passing the id of an
  admins-only item with `audience='engineers'` yields `item_count=0` and the item is not
  even offered by the picker; the same item with `audience='admins'` yields `item_count=1`
  with its text present. Without the positive control the negative assertion could have
  passed on a broken fixture.
* **Closed a hazard introduced by the new default.** Audience is now the default mode, but a
  caller passing `recipient_group` and no `recipient_mode` meant the group — defaulting
  those to the audience would quietly widen a send from a short curated list to every
  matching account. Naming a group without a mode still means the group, and the two
  existing group tests then passed unmodified, which is the compatibility proving itself.
* Extended the preview response with `selectable_items`, `audience_recipient_count` and
  `audience_missing_email`. Missing accounts are **named, not just counted** — "which ones"
  is the first question anyone asks. Addresses are still never returned.
* Extended the digest modal: a Send-to mode selector (audience or a specific group, with the
  group row hidden unless needed), a recipient line that turns amber when accounts are being
  skipped and red when the audience reaches nobody, and an update picker grouped by release
  with select all / none. The confirmation now states both the recipient count and the
  number of updates, since both vary per send.
* Fixed a defect found in the browser, not in review: switching to group mode left the
  recipient line reading "This will email 8 accounts in the everyone audience" — misleading
  in exactly the place that guards a send. `updateChangelogDigestMode()` now re-renders it.
* Note on finding that bug: the first attempt to confirm the fix still showed the old text,
  because `/static/` is `cacheFirst` in the service worker and the page was serving the
  previous `app-changelog.js`. Unregistering the worker and clearing both caches was needed.
  Recorded because a stale asset can easily read as "the fix did not work".
* Bumped the service worker cache from `v44-changelog-digest` to `v45-digest-audience`.
* Suite green at **252 tests** (was 243). New coverage: inactive accounts excluded, accounts
  without email reported not dropped, audience send reaching exactly the resolved addresses,
  an unresolvable audience refused before any send, selection narrowing the body, selection
  unable to widen past the audience filter, an empty selection sending nothing, and preview
  reporting audience recipients.
* Browser-verified on an isolated database, port 5056, explicit `MEDICAL_SERVICE_TEST_DB`.
  Audience switching moved the recipient line between 8 / 6 / 6 accounts and the item count
  between 17 and 19 — engineers correctly see more than "everyone", since their audience set
  includes it. Unticking one update moved 17 to 16; select-none produced "Nothing to send"
  and disabled the send. Contrast passes AA in light and dark (recipients 6.99 / 10.49,
  picker title 4.76 / 8.32, items 16.27 / 8.40), no horizontal overflow, mobile checkboxes
  44 px tall, picker scrolls in its own box, console clean.
* **The UI is still not the guard.** All three forced sends — audience, group and test —
  returned **409** when called directly past the disabled buttons.
* **Zero emails attempted.** 0 `[EMAIL]` lines in the server log and 3 logged refusals.
* Standing risk recorded: `CHANGELOG_DIGEST_ENABLED` was set to **true** on Railway before
  this work. Once deployed, audience mode can reach every matching account, so the recipient
  count shown before a send is the real safeguard. There is still no idempotency (pressing
  send twice sends twice) and no unsubscribe.
* Note for whoever reads a resolved count and finds it larger than expected:
  `get_user_email_for_notification()` ends in a **hardcoded username-to-email map**
  (`diary`, `hanna`, `kevin`, `jonamar`, `robert`, `rodito` -> `@shimadzu.com.ph`), so those
  accounts resolve even with no profile email.

---

claude changes - 2026-07-29 (later)

## What's New email digest — made usable, still switched off

* Established first what actually existed, because the working assumption was that the
  digest merely needed its flag flipped. It did not. `grep -i digest` across all of
  `templates/` and `static/` returned **nothing** — the feature was two API endpoints with
  no UI anywhere in the app. Last session it was exercised through direct API calls, which
  is why the gap was not obvious.
* Found the second blocker: **no recipient group fitted.** All ten entries in
  `EMAIL_RECIPIENT_GROUPS` are workflow handoffs — TSR Client CC, Accounting Handoff,
  Travel/Cash Advance Accounting, LPR Procurement, Leave Request HR and so on. Announcing
  a product update would have meant addressing it to one of those lists.
* Added a `changelog_announcements` group — "What's New Announcements" — to
  `EMAIL_RECIPIENT_GROUPS` and `EMAIL_RECIPIENT_GROUP_ORDER`. No migration was needed:
  `EmailRecipientSetting` rows are keyed by string, and Settings renders whatever
  `get_email_recipient_groups_payload()` returns, so the group appears there for free.
  Added `CHANGELOG_ANNOUNCEMENT_GROUP_KEY` so the default is named once.
* **Fixed a defect that corrupted the audit trail.** `send_changelog_digest()` called
  `add_activity_log_entry("Sent What's New digest…")` unconditionally, before checking the
  result. A provider rejection still recorded a successful send — worse than recording
  nothing, because the log looked authoritative. Success and failure are now logged
  distinctly, after the outcome is known, with the provider message included on failure.
* **Fixed silently dropped branch targeting.** The preview endpoint accepted and honoured
  a `branch` parameter; the send called `build_changelog_digest(audience=audience)` with no
  branch at all. A Cebu-targeted preview would have sent to every branch. Send now
  validates `branch` against `STOCK_INVENTORY_BRANCHES` exactly as preview does.
* Added `test_only` mode. It resolves the requesting admin's own address through the
  existing `get_user_email_for_notification()` and sends only there, so the first real send
  never requires temporarily editing the recipient group — which would otherwise mean
  putting a personal address into a shared list and remembering to remove it. It refuses
  with 400 rather than falling back to the group when no address is on file, and it is
  behind the same flag: test mode must not be a way around the guard.
* Extended the preview response with per-group **active recipient counts**, the default
  group key, and the resolved test address. Counts inform the decision to send; the
  addresses themselves are deliberately not returned, since Settings is where the list is
  managed.
* Built the admin UI: an "Email digest" button on the What's New page opening a modal with
  audience and branch selectors, a live preview of the real message HTML, the recipient
  count for the chosen group, and **two separate actions** — "Send test to me" and "Send to
  group" — the second behind a confirmation naming the group and the recipient count.
  Markup in `templates/changelog.html`, handlers appended to `static/js/app-changelog.js`,
  styles in `static/css/app-changelog.css`, following the existing extraction pattern with
  no Jinja in the static files (verified: zero `{{` or `{%`).
* The UI mirrors the flag but **is not the guard**. Verified by bypassing the disabled
  buttons and calling both endpoints directly from the page: each returned **409**.
* Bumped the service worker cache from `v43-shell-dashboard-changelog` to
  `v44-changelog-digest`, because `app-changelog.js` and `app-changelog.css` are both
  `APP_SHELL` entries and field devices would otherwise keep the old copies.
* Added 14 tests to `tests/test_changelog_workflow.py`, including a
  `ChangelogDigestEnabledPathTests` class that runs the send path **with the flag on and
  `send_email_notification` replaced by a capture function**, restoring both in
  `tearDown`. It proves the group send reaches exactly the active recipients, an empty
  group is refused before any send, test mode goes only to the requesting admin and never
  the group, a failed send is logged as `FAILED` while a successful one is logged as sent,
  and preview never reaches a provider. Previously only the disabled path had coverage,
  which proved nothing escaped but never proved the feature worked.
* Corrected my own test mistake: the enabled-path class initially subclassed
  `ChangelogApiTests`, which re-ran that class's disabled-path assertions with the flag
  turned on and produced three spurious failures. It is now standalone with its own client
  helper, and carries a comment saying why it must not inherit.
* **Proved the new tests catch the real defect** by reverting the activity-log fix and
  re-running: two tests failed, one source-level and one functional. Restored from an
  intact copy and confirmed by grep that no probe remained.
* Verified: `py_compile` clean, suite green at **243 tests** (was 229).
* Browser-verified on an isolated database, port 5056, explicit `MEDICAL_SERVICE_TEST_DB`.
  The modal defaulted to the new group showing "2 active recipients", summarised
  "5 releases, 17 updates", rendered a 4,989-character preview, and kept **both send
  buttons disabled** behind an explanatory banner. Switching audience to Approvers
  re-rendered live from 17 to 26 updates. Contrast passes AA in light and dark (banner
  6.99 / 10.49, summary 15.55 / 12.91), no horizontal overflow, mobile stacks to
  full-width buttons with the preview scrolling in its own box, console clean.
* **Zero emails were attempted at any point.** The server log recorded 0 `[EMAIL]` lines
  and 2 logged refusals. `CHANGELOG_DIGEST_ENABLED` is not present in `.env` and still
  defaults to false.
* Noted, not changed: the digest is "the latest 5 releases", not per-recipient unread, so
  someone who has read everything still receives a full digest. There is no idempotency —
  pressing send twice sends twice — and no unsubscribe. Making it per-recipient would be a
  considerably larger change and is deliberately separate work.
* Note on the resolved test address: the seeded superadmin account resolved to a **real**
  address (`diary@shimadzu.com.ph`), which is why every check ran against a disposable
  database rather than `scheduler.db`.

---

claude changes - 2026-07-29

## Logout now actually ends the session (the HIGH open bug is closed)

* Fixed `/logout` (`app.py`), which did not log anyone out. Confirmed the mechanism
  against the installed Flask-Login **0.6.3** source rather than assuming it:
  `logout_user()` does not delete the remember cookie. It writes
  `session["_remember"] = "clear"` and leaves the deletion to
  `LoginManager._update_remember_cookie()`, an `after_request` handler. The route's very
  next line, `session.clear()`, erased that flag, so no deletion was ever emitted and
  `medical_service_remember_token` survived. Since `/login` always passes `remember=True`
  and `REMEMBER_DAYS` defaults to 30, every user carried a 30-day token: they were
  redirected to the sign-in page, looked signed out, and the next request silently
  re-authenticated them.
* Added `clear_remember_cookie(response)` beside `clear_pwa_login_cookie()`
  (`app.py`, near the auth cookie helpers), and called it from `/logout` alongside the
  existing PWA cookie deletion, so all three sign-in credentials are now cleared: the
  session cookie via `session.clear()`, the remember token, and the PWA restore cookie.
* **Chose the explicit deletion over the one-line reorder** recorded in `pending-work.md`.
  Swapping to `session.clear()` then `logout_user()` does work — verified against the
  0.6.3 source — but it depends on three library internals staying true: that
  `logout_user()` reads the cookie name from `request.cookies` rather than the session,
  that the `after_request` handler still runs, and that
  `REMEMBER_COOKIE_REFRESH_EACH_REQUEST = True` (`app.py:147`) does not re-set the cookie
  on the way out. (It does not: after `session.clear()` the handler sets
  `_remember = 'set'`, finds no `_user_id`, and writes nothing.) The explicit deletion is
  deterministic, mirrors the existing `clear_pwa_login_cookie()` pattern, and is directly
  assertable in a test. The helper reads `REMEMBER_COOKIE_NAME`, `REMEMBER_COOKIE_PATH`
  and `REMEMBER_COOKIE_DOMAIN` from config — never a literal — because the cookie name is
  overridable by environment variable, and carries the same `TypeError` fallback as
  `clear_pwa_login_cookie()` for older Werkzeug `delete_cookie` signatures.
* **Traced the offline path before writing anything**, since not breaking it was the
  explicit constraint. `/logout` is only reachable from deliberate user actions — the
  sidebar link (`templates/layout.html:292`) and `templates/settings.html:1078`; nothing
  auto-logs-out. Offline TSR state lives in IndexedDB, which cookies cannot reach.
  `restore_user_from_pwa_login_cookie()` already returns early for `/logout`
  (`app.py:4199`). `/logout` returns a 302, so `isLoginLikeResponse()` refuses to cache it.
  No `APP_SHELL` entry changed, so **the service worker cache version was deliberately not
  bumped** — no forced re-download for field devices, and no test needed touching because
  the assertions use `assert_cache_version_at_least`.
* **Decided: offline logout stays as-is.** Offline the `/logout` navigation fails and
  falls through to the `/offline` page with the user still signed in. That is unchanged
  pre-existing behaviour; handling it properly would mean touching the offline path.
* Added `tests/test_logout_session.py` (11 tests), pinning `MEDICAL_SERVICE_TEST_DB` before
  importing `app` so the suite can never open the real `scheduler.db`. Functional coverage
  signs in for real and inspects what the browser is left holding: signing in issues a
  remember token (guarding the premise), logout emits a deletion for it, the session and
  PWA cookies are still deleted, the token is gone from the client cookie jar, the request
  immediately after logout is unauthenticated, a deactivated account cannot ride a stale
  token back in, logout without a session does not error, and the response is `no-store`.
  A `deleted_cookie_names()` helper matches on empty value plus `Max-Age=0`/1970 expiry
  rather than on one exact spelling. Source assertions pin the helper being called and the
  cookie name coming from config.
* Disabled `limiter` in the test class `setUpClass`. Several real sign-ins in one class
  would otherwise trip `/login`'s `10 per minute` limit and fail for a reason none of
  these tests care about.
* **Proved the tests are real regression tests** by temporarily disabling the fix and
  re-running them: 4 of 8 functional tests failed, including `/auth_status` returning
  **200 instead of 302** after logout. The probe was removed and its absence verified by
  grep before the suite was re-run.
* Verified: `python -m py_compile app.py` clean; `python -m unittest discover -s tests`
  green at **213 tests** (was 202), zero failures.
* Browser-verified against an isolated database in the scratchpad, on **port 5055** with
  an explicit `MEDICAL_SERVICE_TEST_DB`, per the AGENTS.md rule added after the port-5000
  incident. Signed in as an engineer, signed out via the real sidebar link, confirmed the
  server reports unauthenticated, confirmed a fresh navigation to `/` lands on the sign-in
  page, then **signed in as a second role (`regional_admin`) in the same browser** — the
  account switching this bug has blocked all session. `restored_from_pwa_cookie` was
  `false`, all cookies were HttpOnly (`document.cookie` empty), console clean. Server
  stopped afterwards and `scheduler.db` confirmed untouched.
* Measurement note worth recording so it is not mistaken for a bug later: a first probe of
  `/auth_status` after logout returned **200**, which looked like the fix had failed. It
  was the **service worker's runtime cache** replaying the pre-logout response —
  `/auth_status` is not under `/api/` or `/get_`, so it falls through to
  `staleWhileRevalidate()`. Re-fetching with a cache-busting query returned
  `opaqueredirect` (status 0), proving the server redirects to `/login`. This is the
  accepted `staleWhileRevalidate` staleness already decided against fixing on 2026-07-28,
  not a new defect. Incidentally this ran with a **real service worker registered**
  (`v42-changelog-workflow`, both caches present), which is the first time this session
  that has been true.
* Not done here, deliberately: the user-facing `releases.json` entry for this fix. It is
  being written as part of the promotion step so its date matches the commit that ships it.
* Nothing committed or pushed — this folder is the local sandbox.

---

claude changes - 2026-07-28

## Login page redesign and reliability repair

* Fixed the silent deactivated-account failure in `/login` (`app.py`). `User.is_active`
  shadows `UserMixin.is_active`, so Flask-Login's `login_user()` refuses inactive users
  and returns `False` — but the route discarded that return value and redirected to the
  dashboard anyway, so a deactivated user was bounced back by `@login_required` with no
  message at all, looking exactly like a wrong password. The route now checks
  `is_active` explicitly before calling `login_user`, captures the return value as a
  second guard, and flashes "This account has been deactivated. Please contact your
  administrator."
* Added `find_user_by_username()` (`app.py`, near the auth helpers). Strips whitespace
  and falls back to a case-insensitive lookup via
  `db.func.lower(User.username) == cleaned.lower()`. Mobile keyboards capitalise the
  first letter and append trailing spaces, which previously rejected entirely correct
  credentials. Stored usernames are unchanged; only the lookup is normalised.
* Added `DUMMY_PASSWORD_HASH` and made `/login` run a hash comparison even when the
  username does not exist, so response timing no longer reveals which accounts are real.
* Wired up Flask-Limiter, which was listed in `requirements.txt` but never imported —
  `Limiter` appeared zero times in `app.py`, meaning `/login` accepted unlimited
  password attempts against a public Railway URL. Added the import, initialised
  `limiter` next to `CSRFProtect(app)`, and applied
  `@limiter.limit('10 per minute; 60 per hour', methods=['POST'])` to `/login`,
  `5 per minute; 20 per hour` to `/forgot_password`, and `10 per minute; 40 per hour`
  to `/reset_password`. Deliberately no `default_limits` — a blanket limit across 356
  routes would break offline TSR sync and attachment retries. Storage is `memory://`
  because Railway runs a single web instance; a comment records that scaling to
  multiple instances would require shared storage.
* Added an `@app.errorhandler(429)` that re-renders the login page with "Too many
  attempts. Please wait a minute and try again." for auth paths only, so a throttled
  engineer sees the normal page instead of a raw error page.
* Added `User.last_login_at` (DateTime, nullable) with an additive startup migration
  `ALTER TABLE user ADD COLUMN last_login_at DATETIME`, appended to the existing user
  migration list in `app.py`. Set on each successful sign-in inside a try/except so a
  write failure can never block a login.
* Rewrote `templates/login.html` to the approved Option A design and extracted the
  shared styling into a new `static/css/app-auth.css`, so the three signed-out pages
  share one stylesheet and a dark-mode or accent fix lands on all of them at once.
* Replaced the hardcoded `#d63384` pink and pink-to-blue gradient with the accent
  theme variables. The page now defaults to the Shimadzu brand red `#c8102e`, and an
  explicit Classic / Shimadzu Red / Clinical Green / Corporate Blue choice overrides it.
  Correction to an earlier claim made this session: the login card *was* already
  dark-mode aware through `app-themes.css:155`, which styles `.login-card` with
  `!important`. What was genuinely ignored was the accent theme, not light/dark.
* Added mobile input hardening to `login.html`: `autocomplete="username"` and
  `autocomplete="current-password"` for password managers and autofill, plus
  `autocapitalize="none"`, `autocorrect="off"`, and `spellcheck="false"` on the
  username field, which combined with the case-sensitive lookup above was rejecting
  valid credentials on phones.
* Added a password visibility toggle as a real `<button type="button">` with
  `aria-label` and `aria-pressed` (per the frontend baseline, so it can never submit
  the form), a caps-lock warning driven by `getModifierState('CapsLock')`, a
  double-submit guard that disables the button with a 12-second re-enable timeout so a
  dropped request cannot leave the form stuck, and an online/offline status footer.
* Added `/login` and `/static/css/app-auth.css` to `APP_SHELL` and bumped the service
  worker cache version from `v38-schedule-product-coverage` to `v39-login-refresh`.
  `/login` was previously absent from the shell, so a session dropping while offline
  produced a browser error page.
* Adjusted `fieldNavigationFirst` in the service worker so a failed offline navigation
  to `/login` falls back to the clean signed-out copy in the app shell instead of
  `/offline`. Login stays network-first and is still never written to the runtime
  cache, and `isLoginLikeResponse` is untouched, so the original protection against
  serving a login page in place of a protected route is preserved.
* Repaired `prevent_login_redirect_cache` (`app.py:1278`), found during smoke testing.
  It forced `no-store` on every `/login` response, which silently defeated the offline
  shell caching above. Redirects and non-GET responses stay strictly `no-store` — that
  was the original hazard, a 302 to `/login` being cached under `/timeline` — but a
  signed-out `GET /login` returning 200 now uses `no-cache, must-revalidate`, which
  still revalidates whenever the network is reachable and carries no account data.
* Built self-service password reset with no new model or table. `/forgot_password` and
  `/reset_password/<token>` reuse the existing `URLSafeTimedSerializer` pattern from
  `get_pwa_login_serializer()` with a distinct salt and a 30-minute expiry, embedding
  the last 16 characters of the password hash as a marker exactly as
  `build_pwa_login_cookie_value()` does — so changing the password retires any
  outstanding token and makes it single-use for free. Email resolution reuses
  `get_user_email_for_notification()` and delivery reuses `send_email_notification()`.
* Made the reset flow enumeration-safe: the confirmation message is identical whether
  or not the account exists, and email delivery failures are logged rather than
  surfaced. `User` has no email column, so accounts whose address cannot be resolved
  through `engineer_profile` cannot self-serve — the confirmation directs them to their
  administrator, and the existing admin reset at `/reset_user_password/<int:user_id>`
  remains the fallback.
* Added `templates/forgot_password.html` and `templates/reset_password.html`, both
  using the shared auth stylesheet, with `autocomplete="new-password"`, a confirm field
  with inline mismatch feedback, and server-side validation of length and match.
* Fixed two defects found by inspecting computed styles in a real browser rather than
  reading the markup: `app-themes.css:156` forces every label inside `.login-card` to
  `--app-text !important`, flattening the label hierarchy in dark mode (overridden with
  a more specific rule), and the "Forgot password?" link measured only 3.1:1 contrast
  on the dark card (now 8.9:1 via a `color-mix` tint with a plain `#cbd5e1` fallback
  for browsers without `color-mix` support).
* Enlarged the password toggle tap target from 30x28 px to 44x44 px after measuring it
  at a 375 px mobile viewport. Engineers tap this on phones and the original target was
  below the usable minimum.
* Added `tests/test_login_page.py` — 17 tests in the existing house style (source-text
  assertions plus functional coverage). The module pins `MEDICAL_SERVICE_TEST_DB` to a
  temp path *before* importing `app`, so the suite can never open the real
  `scheduler.db`. Functional tests cover username normalisation, reset token
  round-trip, single-use invalidation, tampering, and deactivated accounts.
* Verified with `python -m py_compile app.py` and
  `python -m unittest discover -s tests` using the project venv: 148 tests, all 17 new
  tests passing. Five failures remain, all pre-existing and unrelated — they hardcode
  the stale cache version `v35-tsr-email-preview-cc` and were already broken by the
  earlier v36/v37/v38 bumps. Flagged as a separate task rather than fixed here.
* Ran a request-level smoke test (scratchpad only, not added to the repo) covering 21
  checks: wrong password, deactivated account, messy-cased username, `last_login_at`
  stamping, rate-limit trip and friendly 429, enumeration-safe reset confirmations, and
  the full reset token lifecycle including reuse and tampering. All 21 passed.
* Browser verification performed at desktop and 375 px mobile, in light and dark, with
  Classic and Corporate Blue accents: contrast measured (all AA-passing), no horizontal
  overflow, toggle works in both directions without submitting the form, clean console.
  Not yet verified in Edge or Brave, and the offline path was not exercised against a
  real service worker registration — both still need manual testing.
* Added `.claude/launch.json` so the app can be started for browser verification.
* Note on the local database: running the app locally applied the additive
  `last_login_at` migration to `scheduler.db`. This is additive and non-destructive, and
  is what any normal local run would do, but recording it since that file is sensitive.
  It was not committed, pushed, replaced, or deleted.
* Nothing was committed or pushed — this folder is the local sandbox.

## INCIDENT — verification server impersonated the real app (no data lost)

* **What the owner saw:** their password was rejected at `localhost:5000`; after doing a
  password reset and getting in, the system appeared empty. It looked like the database
  had been deleted or wiped.
* **What actually happened:** agent-run verification servers were bound to **port 5000**
  while serving throwaway databases (`tmp/layout_ui.db`, then `tmp/cl_ui.db`) via
  `MEDICAL_SERVICE_TEST_DB`. Those databases are near-empty and the app seeds fresh
  accounts with random temporary passwords on first run. The owner was looking at a test
  fixture at the real app's address — not at their system.
* **Nothing was deleted and nothing was changed.** Verified read-only against both
  copies: `Claude-medical-service-sms-railway\scheduler.db` and
  `medical-service-sms-railway\scheduler.db` both hold 29 users, 27 engineers, 145
  clients, 99 products, 543 shifts, 25 TSRs, 7 reimbursements and 15 travel requests.
  The user lists are identical, and **no password hash differs between them** — so the
  owner's original password still works and their reset went into the throwaway
  database, not `scheduler.db`.
* **Root cause:** `.claude/launch.json`, created earlier in the session, ran
  `venv/Scripts/python.exe app.py` on **port 5000 with no `MEDICAL_SERVICE_TEST_DB`**.
  Used via `preview_start`, it both took the owner's port and opened the real database
  (which is what modified `scheduler.db` at 14:05 — additive changelog migrations only).
  The file format has no field for environment variables, so it cannot be made safe.
* **Fixes applied:**
  - Deleted `.claude/launch.json`.
  - Added a rule to AGENTS.md section 3: never bind port 5000, always pass an explicit
    `MEDICAL_SERVICE_TEST_DB`, never use `preview_start` name-mode for this project,
    stop every server started, and if two servers appear on one port assume responses
    come from the wrong one until proven otherwise. Canonical command documented.
  - Cross-referenced the rule from the browser-verification checklist in section 8.
* The correct pattern was already proven later in the same session: the changelog work
  ran on `FLASK_PORT=5055` with an explicit test database and caused no interference.
* Lesson recorded rather than just fixed: an isolated database is not enough on its own.
  If it is served at the address the owner uses, it is indistinguishable from their real
  system, and the failure mode is one that reasonably reads as catastrophic data loss.

## What's New — authoring workflow and reading experience

* Evidenced the problem before changing anything: the manifest's newest entry was
  **2026-07-23** while `b791a3c` shipped **2026-07-24** ("Sort TSR archive by recently
  added") with no entry at all. Twelve releases and 72 items had been hand-written over
  16 days, and the discipline broke within days.
* Added the missing authoring verbs to `app.py`. The admin API was **PUT-only**, so
  nothing could be announced without a code deploy: `POST /api/changelog/admin/releases`,
  `POST /api/changelog/admin/releases/<id>/items`, `DELETE` for both, and
  `POST /api/changelog/admin/items/<id>/revert`. All guarded by `is_admin_authorized()`
  and logged through `add_activity_log_entry()`, matching the existing endpoints.
* In-app entries mint keys in a reserved `app-` namespace, and
  `sync_changelog_release_manifest()` skips that namespace entirely, so a file-based
  release can never collide with or clobber something published from the app. Deleting a
  manifest-sourced entry is refused with a message pointing at `releases.json`.
* Made the manifest/in-app divergence visible and reversible. `admin_edited` already
  locked an item against future syncs, silently and permanently. The sync now records
  `manifest_snapshot_json` on every pass whether or not it applies the value, giving
  revert something to restore, and the UI shows an "edited in app" flag on affected
  items with a "Revert to manifest" action.
* Added scheduling: `ChangelogRelease.publish_at` with an additive migration. A release
  reaches users only when published **and** past its scheduled time, applied in the
  single place `get_visible_changelog_release_dicts()`. Admins still see scheduled
  entries so a schedule can be reviewed or cancelled. The header bell badge inherited
  this for free since it already routes through the same function.
* Added preview-as-role. The admin view showed everything, which is not what any user
  sees. `changelog_visible_items()` now takes overridable `audiences` and `branch_code`
  rather than always deriving them from `current_user`, so the owner can render the feed
  exactly as an engineer or approver will receive it.
* Added optional branch targeting via `ChangelogItem.branches_json`, reusing
  `STOCK_INVENTORY_BRANCHES` rather than a second hardcoded list. Empty means every
  branch, which is how all existing items behave, so nothing needed backfilling.
* Added `ChangelogItem.is_minor`, excluded from `changelog_visible_content_hash()`. A
  typo correction previously re-flagged an entire release as unread for everyone who had
  already read it.
* Reworked the reading experience: server-side pagination at 10 releases per page
  (matching the Reports archive convention), search across description, category, title
  and summary, and a category filter built from the categories actually present. The
  page previously rendered every release and item in one `innerHTML` with no way to find
  anything.
* Extracted the page's inline assets into `static/css/app-changelog.css` and
  `static/js/app-changelog.js`, following the `app-shell` and `app-dashboard`
  extractions. `changelog.html` went from 342 lines to about 130, with the single
  template-injected constant now passed via `window.__changelogConfig`. Registered both
  in `APP_SHELL` and bumped the cache version from `v41-dashboard-assets` to
  `v42-changelog-workflow`.
* Built the Brevo digest **with sending disabled**, per the owner's instruction that
  this is a local upgrade. `EMAIL_NOTIFICATIONS_ENABLED` defaults to **true**, so it is
  not a safe guard on its own — a sandbox holding a real Brevo key could otherwise email
  live engineers. Added an independent `CHANGELOG_DIGEST_ENABLED` flag defaulting to
  **false**, checked before any send path is reachable. Preview renders the exact HTML
  and calls nothing; send returns 409 with a clear message. Reuses
  `get_active_email_recipients_by_group()` and `send_email_notification()` only behind
  the flag. No scheduler or cron was added.
* Added `tests/test_changelog_coverage.py` as the safety net: it fails when the most
  recent commit touched user-facing paths but `releases.json` has no release for that
  date, with a message naming the commit, subject and files. Exempt paths cover
  `tests/`, `docs/`, `.claude/`, `changes.md` and other non-user-facing files. It also
  validates manifest JSON, unique keys, and that the file never uses the reserved `app-`
  prefix (which the sync would silently skip).
* **The safety net immediately caught the real gap it was written for** — `b791a3c` on
  2026-07-24 — so the missing entry was backfilled into `releases.json` describing the
  TSR archive sort change. That is the correct resolution rather than suppressing the
  check.
* Added `tests/test_changelog_workflow.py` (18 tests) covering authorization on every
  new verb, reserved-namespace key minting, manifest sync leaving in-app entries alone,
  refusal to delete manifest entries, scheduling visibility, branch filtering with empty
  meaning all, revert restoring the manifest value, revert refused for in-app items,
  pagination, search, minor items not changing the acknowledgement hash, and three
  digest guards including one that patches `send_email_notification` and asserts it is
  **never called** while the flag is off.
* Fixed a real bug the tests caught before it could ship: `get_manila_time()` returns a
  timezone-aware datetime but SQLite hands `publish_at` back naive, so comparing them
  raised `TypeError`. Unfixed, this would have made the entire What's New page return
  500 for anyone once a scheduled release existed. Added `as_naive_datetime()` and
  normalised both sides.
* Verified in a browser against an isolated database, never `scheduler.db`: composed and
  published "Submit July liquidations by Friday" with no deploy and saw it appear at the
  top flagged in-app; search narrowed 14 releases to 2; pagination showed 10 per page
  across 2 pages; preview-as-approver correctly hid the engineers-only reminder while
  preview-as-engineer showed it; the digest preview rendered 10 updates while the send
  returned **409 with sending disabled**. Confirmed from the server log that **zero
  `[EMAIL]` lines were emitted** and one refusal was logged — the send path was never
  entered. Dark mode passes AA on the new controls (search 15.98, select 8.32, page
  label 8.57, flags 6.72). Clean console throughout.
* Suite green at **202 tests**. Nothing committed or pushed.
* Not verified: Edge and Brave, mobile viewport for the new filter row, and the offline
  path against a real service worker registration.
* Note: browser verification had to move to port 5055 after a stale server process kept
  an unreleased socket on 5000, and account switching remains blocked by the open logout
  bug below. A leftover `tmp/cl_ui.db` could not be deleted while its file handle was
  still closing; it is a gitignored local artifact.

## Dashboard phase 1 — engineer view

* Measured the density problem before changing anything: a hybrid admin+engineer account
  rendered **11 large number tiles across three stacked rows before the first actionable
  list**, then seven more sections. `templates/dashboard.html` was 4,368 lines / 187 KB
  serving every role variant from one file.
* Extracted the inline assets first, as a deliberately behaviour-neutral step, so the
  redesign would be reviewable. Moved two `<style>` blocks (30 KB) to
  `static/css/app-dashboard.css` and three `<script>` blocks (88 KB) to
  `static/js/app-dashboard.js`. **dashboard.html went from 4,368 to ~1,220 lines.**
* The extracted JS had 12 template-injected constants. Rather than leave Jinja in a
  static file, the template now emits `window.__dashboardConfig` in a small inline block
  and the JS reads from it, so the file caches as a normal static asset.
* Added a `{% block page_head %}` to `layout.html` so pages can contribute stylesheets
  to `<head>`. It sits after the shell CSS and before the dark-page overrides at the end
  of body, preserving the existing rule that dark mode wins.
* Verified the extraction changed nothing before touching the design: CSS and JS loading
  from static files, zero inline `<style>` tags, config injected correctly, clock
  running, the same five engineer sections present, clean console.
* Replaced the four engineer summary tiles with one inline metric strip. All four tiles
  linked to the same destination (`/timeline`), so the strip carries a single link
  instead of four. The count element ids are unchanged, so
  `updateEngineerSummaryCards()` keeps working untouched.
* Added a "Needs you today" panel as the lead element, built entirely from tasks already
  loaded for the tables below — no new endpoints and no changed queries, matching the
  agreed "show less, fetch the same" scope. It surfaces overdue visits, today's visits,
  continuation jobs and parts/P.O. waits, omitting any category with nothing in it.
* Consolidated the duplicated engineer shortcuts. `mobile-quick-actions` and
  `engineer-workflow` rendered the **same five destinations** in two markup blocks
  toggled by viewport. The engineer path now uses one responsive block; the other
  remains for admin/scheduler/manager, which this phase does not touch.
* Collapsed the company-wide "All open technical tasks" table by default for engineers —
  it is reference material, and their own assignments already appear above. Caught an id
  collision while doing it: the wrapper initially used `open-tasks-body`, which is the
  `<tbody>` the task renderer writes into; renamed to `open-tasks-panel`.
* Added account-synced dashboard layout preferences, mirroring
  `appearance_preferences_api()`. New `User.ui_dashboard_layout_json` column with an
  additive startup migration, and `/api/preferences/dashboard-layout` (GET/POST) storing
  `{order, hidden}`. Section ids are validated against `DASHBOARD_SECTION_IDS` so a stale
  or crafted payload cannot persist junk. localStorage remains the pre-render cache; the
  account copy wins. Previously the order lived only in localStorage and could not hide
  anything, so it never followed an engineer to their phone.
* Fixed a real ordering defect found while verifying cross-device sync:
  `applySavedDashboardOrder()` appended only the sections named in the saved order, which
  silently floated any unlisted section to the top. A saved layout can legitimately be
  partial when it comes from a device or role that rendered fewer sections. It now
  appends the saved order followed by everything else in its existing DOM order.
* Fixed a dark-mode contrast failure measured in the browser: the metric strip link and
  the today-panel action links sat at **2.72:1** against the dark card (accent on dark),
  below the 4.5 threshold. Now 7.63:1 via a `color-mix` tint with a plain `#cbd5e1`
  fallback — the same pattern used on the login page.
* Fixed a mobile density regression I introduced: the consolidated shortcut row used
  `auto-fit`, which wrapped to three rows and **222 px** at 375 px — taller than the
  layout it replaced. Pinned to five equal columns like the original mobile block, now
  one row at **94 px**.
* Registered both new assets in `APP_SHELL` and bumped the service worker cache version
  from `v40-shell-sidebar` to `v41-dashboard-assets`.
* Added `tests/test_dashboard_engineer.py` (15 tests): extraction is complete and the JS
  carries no template syntax, the summary is a strip with the count ids preserved, the
  shortcut duplication is gone, the today panel issues no fetch of its own and has an
  empty state, the reference table collapses without reusing the tbody id, **the
  scheduler / manager / admin-counters / needs-attention / team-intelligence sections
  still exist** (guarding later phases against accidental edits), the migration is
  additive, and the layout endpoint round-trips, rejects unknown section ids and
  non-list payloads, de-duplicates while preserving order, requires login, and survives
  an unreadable stored value.
* Verified in a browser against an isolated database, never `scheduler.db`: metric strip
  and today panel render with real seeded data (4 actionable rows from 5 shifts), the
  empty state shows one calm line rather than four empty cards, collapse toggles both
  ways with `aria-expanded` syncing, dark mode passes AA throughout, mobile is one row
  with no horizontal overflow, hiding a section persists to the account and leaves the
  destination reachable from the sidebar, and a layout set on the account applies after
  wiping every local key. Console clean throughout.
* Suite green at **181 tests** on fresh databases. Nothing committed or pushed.
* Not verified: Edge and Brave, and the offline path against a real service worker
  registration. Cross-role browser checks were done through the Flask test client rather
  than the browser, because the logout bug below prevented switching accounts.
* Noted for the scheduler phase, not changed: `dashboard.html` computes
  `dashboard_scheduler_account` from the hardcoded usernames `['diary', 'hanna']`, the
  same anti-pattern removed from `layout.html` earlier today. It drives the
  `dashboard_effective_*` flags that gate the scheduler and manager sections this phase
  was required to leave untouched, so changing it here would have altered those
  variants. `is_scheduler_user()` already exists server-side for this.

## OPEN BUG (logged, not fixed) — logout leaves users signed in

* **`/logout` does not end the session.** Found while switching accounts during dashboard
  verification. Owner decided to log it and schedule the fix separately.
* Mechanism, in the `/logout` route in `app.py`:

  ```python
  logout_user()      # sets session['_remember'] = 'clear'
  session.clear()    # immediately wipes that instruction
  ```

  Flask-Login's `logout_user()` does not delete the remember cookie itself. It writes
  `session["_remember"] = "clear"` and relies on its own `after_request` handler to act
  on it. `session.clear()` on the next line erases the flag, so the handler does nothing
  and the cookie survives. Confirmed against `flask_login.logout_user` source.
* Evidence: logout emits `Set-Cookie` deletions for `medical_service_pwa_login` and
  `medical_service_session` only — there is **no** deletion for
  `medical_service_remember_token` — and a request immediately after logout returns
  `authenticated`. Reproduced with the Flask test client and in a real browser.
* Ruled out as causes: the service worker (unregistered, all caches cleared, real
  navigation, server logged `GET /logout 302`) and the PWA restore cookie
  (`restored_from_pwa_cookie: false`).
* Scope: affects every user. `/login` always passes `remember=True` and `REMEMBER_DAYS`
  defaults to 30, so everyone carries a 30-day token. The user is redirected to the
  sign-in page and appears logged out, then the next request silently re-authenticates
  them. It also weakens the deactivated-account fix made earlier today: deactivating an
  account does not dislodge an existing remember token.
* Proposed fix (one line, not applied): swap the order to
  `session.clear()` then `logout_user()`. `logout_user()` reads the cookie name from
  `request.cookies` rather than the session, so it still sets the clear flag correctly
  and Flask-Login then deletes the cookie. Needs a regression test asserting logout
  emits a deletion for the remember cookie and that the following request is
  unauthenticated.
* Side effect during this session: browser-based role switching was blocked by this bug,
  so cross-role dashboard verification was done through the Flask test client instead.

## Sidebar and layout shell — refinement and authorization alignment

* Added `inject_navigation_access()` to `app.py` as a second context processor, exposing
  the real authorization helpers to templates as `nav_is_admin` (`is_admin_authorized`),
  `nav_is_superadmin` (`is_superadmin_user`), `nav_is_approval_center_user`
  (`is_approval_center_user`), `nav_is_approver_only` (`is_approver_only_user`),
  `nav_can_access_accounting_center` (`can_access_accounting_center`), plus
  `nav_is_engineer` and `nav_authenticated`. No new authorization logic was written —
  these are the same functions the routes already guard themselves with.
* Replaced the inline role logic in `templates/layout.html` with those injected values.
  The old template computed its own flags and they were **looser than the server**, so
  the sidebar offered links that the route then redirected away from. Concretely:
  `role in ['superadmin','regional_admin']` ignored the `SUPERADMIN_USERNAMES`
  membership that `is_superadmin_user()` requires, and the approver flags omitted the
  `is_active` checks. Verified in a browser that an account with `role='superadmin'`
  outside the allowlist previously would have been shown Admin, Analytics and
  Personnel, while `/activity_page` and `/analytics_page` both redirect to `/` for it.
* Deleted the hardcoded usernames `'rodito'`, `'hanna'` and `'diary'` from the template.
  `app.py` already centralises these as `APPROVAL_CENTER_MANAGER_USERNAME` and
  `SUPERADMIN_USERNAMES`; the template held a second, drifting copy.
* Deleted the dead template variables `is_scheduler_user` and `approval_paths`, both
  computed and never used.
* Added a `nav_link()` Jinja macro that renders every sidebar link, so the `active`
  class and `aria-current="page"` are emitted together and cannot drift apart. This
  fixes Cash Advance, which was the only nav item with no active state at all — by
  construction rather than by adding one more hand-written conditional.
* Extracted the entire inline `<style>` block from `layout.html` into a new
  `static/css/app-shell.css`, removing 811 lines from the template (1,261 lines down to
  506). The inline block held **three overlapping generations** of sidebar CSS: the
  original rules, a later "M2C visual cleanup" block that redefined nearly all of them,
  and a mobile scroll-polish block. `.sidebar-subnav`, `.sidebar-subnav a` and
  `.sidebar-subnav a.active` were each declared three times; `.sidebar-calendar-row` and
  `.sidebar a.text-warning` twice. The M2C generation was the one actually rendering, so
  its values were carried forward as the source of truth.
* Removed the hardcoded pink `#d63384` from the sidebar CSS. Correcting an assumption
  worth recording: this was **not** a live theming bug — `app-themes.css:113` already
  overrode the active border with `var(--app-primary) !important`, so the accent theme
  was being honoured. It was dead code, and is now deleted rather than merely overridden.
* Moved the genuinely unthemed values onto variables: hover `#34495e`, link `#cbd5e1`
  and the subnav background are now `--sidebar-hover`, `--sidebar-text` and
  `--sidebar-subnav-bg`, with dark-mode overrides, so hover no longer stays light-blue
  when the sidebar background darkens.
* Changed the fixed `height: 58px` rows to `min-height` at 46px so long labels can grow
  instead of being ellipsised, and replaced `transition: all 0.3s` on `body` with
  `background-color` and `color` only — the blanket transition animated every property.
* Applied the approved Option A design: uppercase group labels (Main / Operations /
  Records) marked `aria-hidden` so they are not focusable, 46px rows with 38px subnav
  rows, an accent-tinted active background alongside the existing left accent bar, and a
  user identity footer (initials avatar, username, resolved role label, logout control)
  replacing the yellow `Logout (username)` nav row. The logout control remains a real
  link to `/logout`.
* Accessibility: converted the desktop toggle from `<i onclick=...>` to a real
  `<button>` with `aria-label`, `aria-expanded` and `aria-controls` that stay in sync
  when toggled; added `aria-current="page"` on the active link; added `aria-label="Main"`
  to the nav landmark; added a skip-to-content link targeting a focusable
  `#main-content`; gave the mobile drawer Escape-to-close, focus movement into the
  drawer on open (preferring the active nav item) and focus restoration to the Menu
  button on close; and the active item is scrolled into view with
  `scrollIntoView({block: 'nearest'})` so the page itself never jumps.
* Routed the pre-existing mobile scripts through the new `setMobileSidebar()` helper so
  `aria-expanded` cannot desync when the drawer closes via outside-click, resize, or a
  nav click.
* Added `/api/nav/pending-summary` and wired count badges onto Approvals and My
  Requests, reusing the one-shot fetch pattern already used by
  `refreshGlobalChangelogBadge()`. The endpoint is deliberately **not** built on the
  existing approval summary near `approval_center_summary()`: that route materialises
  every row across six modules to build a full status breakdown, which is acceptable for
  the Approvals page but not for something running on every page load. This one uses
  `.count()` queries only, scoped with the existing `apply_assigned_approver_filter()`,
  returns zeros rather than an error for users without approval access, and wraps each
  module in try/except so one unavailable module cannot zero out or break the badge.
* Registered `/static/css/app-shell.css` in `APP_SHELL` and bumped the service worker
  cache version from `v39-login-refresh` to `v40-shell-sidebar`.
* Fixed a contrast failure found by measuring computed styles in the browser: the
  uppercase group labels used `--sidebar-text-dim: #8a9bb0`, which is only 3.87:1
  against the light-mode sidebar `#2c3e50` — below the 4.5:1 required at that size.
  Changed to `#a8b6c6`, now measured at 5.32:1 light and 5.58:1 dark.
* Updated five existing tests that asserted literal markup the macro refactor changed:
  `test_leave_request_workflow`, `test_lpr_workflow` and `test_stock_inventory` now
  assert the `nav_link(...)` invocation instead of a literal `href`, and
  `test_appearance_themes` reads the header-button rules from `app-shell.css` rather
  than from the template. These were correct assertions about the wrong location, not
  regressions — the rendered markup is unchanged.
* Fixed my own `test_login_page` assertion that hardcoded `v39-login-refresh`. It was
  the same anti-pattern removed from five other tests earlier today, and it broke on the
  very next cache bump. It now calls `assert_cache_version_at_least(self, 39, ...)`.
* Added `tests/test_layout_sidebar.py` (18 tests). Source assertions cover the injected
  helpers, the banned literals, the macro, the accessibility markup, single-declaration
  CSS, and the endpoint using `.count()` and never `.all()`. A second class renders the
  real shell through the Flask test client for engineer, non-allowlisted superadmin and
  approver roles, because grepping template source cannot prove what a role actually
  sees once links come from a macro.
* Verified in a real browser against an **isolated test database** (`tmp/layout_ui.db`),
  never `scheduler.db`, with seeded accounts for each role. Every visible sidebar link
  was fetched and its final path compared: **zero dead ends** across all four roles —
  allowlisted superadmin (17 links), regional admin (17), non-allowlisted superadmin
  role (13, no Admin or Analytics), and approver-only (4). Also verified light and dark
  with Shimadzu Red and Clinical Green accents (active state follows the accent), 46px
  rows, no truncated labels, no horizontal overflow at 375px, drawer open/Escape/focus
  restoration, desktop toggle aria sync, and a clean console.
* Two measurement artifacts worth recording so they are not mistaken for bugs later: the
  Browser pane does not composite frames, so CSS transitions never advance and
  `getComputedStyle` returns the pre-transition value; and the pane's window is not
  focused, so `:focus` does not match even when `document.activeElement` is correct.
  Both made the skip link look broken until the transition was disabled, at which point
  it positioned correctly. The skip link's visual reveal on real keyboard focus was
  therefore **not** fully verified and should be checked manually.
* Found but did not fix (flagged as a separate task): the service worker's
  `RUNTIME_CACHE` is never cleared on logout, so authenticated HTML for many routes
  persists after sign-out. Combined with `staleWhileRevalidate()` being the fallback for
  same-origin non-navigation HTML GETs, one user's cached dashboard was observed being
  returned while a different user was authenticated. Normal browsing is unaffected
  because navigations are network-first, but on a shared field device an offline user
  could see the previous user's cached pages. Pre-existing, not introduced here.
* **Decision — do not fix the service worker runtime cache on logout.** The owner
  confirmed engineers are issued 1:1 devices, so the shared-device scenario that
  motivated it does not occur in practice. Confirmed while assessing this that offline
  TSR data is unaffected either way: drafts, the sync queue, attachment blobs and
  metadata all live in IndexedDB (`medical_service_offline_tsr_db`, stores `tsr_drafts`,
  `tsr_queue`, `tsr_attachments`, `tsr_metadata`), which the Cache API cannot reach, and
  `/timeline`, `/offline-tsr`, `/offline` and `/login` sit in `APP_SHELL_CACHE` rather
  than `RUNTIME_CACHE`. Two minor residual behaviours were accepted rather than fixed:
  `/logout` is cached in the runtime cache so an offline logout may not reach the
  server, and `staleWhileRevalidate()` can return slightly stale HTML for same-origin
  non-navigation GETs. Neither is an exposure on a personal device. Revisit only if
  loaner or shared laptops become routine.
* Not yet verified: Edge and Brave, and the offline path against a real service worker
  registration. Both still need manual testing.
* Full suite green at 166 tests. `python -m py_compile app.py` clean. Nothing committed
  or pushed — this folder is the local sandbox. `scheduler.db` was not opened at any
  point during this work; all browser verification used a disposable database.

## Test suite: robust service worker cache version assertions

* Fixed the five pre-existing test failures flagged earlier today. They each asserted
  the literal string `medical-service-pwa-offline-navigation-v35-tsr-email-preview-cc`,
  which pins one exact cache version. Because the version legitimately moves on every
  offline-affecting change, these tests broke silently at v36, v37 and v38, and stayed
  broken — five unrelated feature tests failing for a reason none of them cared about.
* Added `tests/sw_cache_version.py` with `get_cache_version()` and
  `assert_cache_version_at_least()`. The helper regex-parses
  `const CACHE_VERSION = 'medical-service-pwa-offline-navigation-vNN-<label>';` out of
  `app.py` and asserts the number is greater than or equal to the version the calling
  feature shipped in. Later bumps pass; a missing, malformed, wrong-prefix, or
  backwards version still fails.
* Replaced the literal assertion with `assert_cache_version_at_least(self, 35, ...)` in
  `tests/test_appearance_themes.py`, `tests/test_tsr_assigned_engineers_layout.py`,
  `tests/test_tsr_filename_template.py`, `tests/test_tsr_subject_scenarios.py`, and
  `tests/test_tsr_email_preview_cc.py`. All five features shipped at v35, so 35 is the
  floor in each. Every `releases.json` changelog assertion was left untouched — those
  are feature-specific and correct.
* Added `tests/__init__.py` to make `tests` a real package. Verified empirically with a
  throwaway probe that `from tests.sw_cache_version import ...` resolves under both
  `unittest discover -s tests` and `unittest tests.<module>`, whereas a flat
  `from sw_cache_version import ...` only works under discover. The probe was deleted
  after the check. Discovery of the existing modules is unaffected.
* Added `tests/test_sw_cache_version.py` (5 tests) guarding the helper itself, so a
  future edit cannot quietly turn it into an assertion that passes on anything. It pins
  the parse result, the live `app.py` value, passing at and above the floor, rejection
  of an older version, and rejection of missing, malformed, and wrong-prefix constants.
* Verified: `python -m unittest discover -s tests` now reports 153 tests, all passing,
  with zero failures — the suite is green for the first time this session. Also
  confirmed the module-invocation form passes. Used the project venv at
  `venv/Scripts/python.exe`; the system Python 3.14 lacks the dependencies.
* Not committed and not pushed — this folder is the local sandbox.

## Session setup and documentation

* Reviewed `medical-service-sms-detailed-handoff-2026-07-26.md` in full and verified
  its claims against the live workspace — confirmed `app.py` at 50,255 lines with 356
  routes and ~43 `db.Model` classes, `leave_feature.py` (971 lines) and
  `storage_backend.py` (295 lines) as the only extracted modules, and the service
  worker cache version `medical-service-pwa-offline-navigation-v38-schedule-product-coverage`
  emitted from `app.py:13968`.
* Created global `C:\Users\jonamar\.claude\AGENTS.md` — a machine-wide operating guide
  covering the owner's working style and communication preferences, project overview
  and stack, non-negotiable git/database rules, architecture constraints (SQLite
  additive migrations, Railway bucket storage modes, Brevo settings-driven email,
  `NEW_WORKFLOWS_ENABLED`, offline/PWA), the frontend reliability baseline, per-module
  rules, decisions not to undo, testing expectations, skills/environment notes, and
  secret handling. No application code was touched.
* Recorded in AGENTS.md that `static/changelog/README.md` mandates a `releases.json`
  update before every user-facing commit — this obligation was not stated in the
  handoff document and was found only by reading the changelog README directly.
* Noted in AGENTS.md that `NEW_WORKFLOWS_ENABLED` is present in the local `.env`, so
  accounting workflows are enabled locally — the handoff had warned they might appear
  missing in local development.
* Flagged in AGENTS.md that the skills named in handoff section 12
  (`frontend-repair-baseline`, `web-app-security-hardening`, `github:github`,
  `github:yeet`) are not installed in this Claude Code environment. Inlined the full
  frontend reliability baseline as AGENTS.md section 5 so those rules survive without
  the skill, and directed use of local `git`/`gh` instead of a GitHub skill.
* Reviewed `D:\Shimadzu\Projects\SHIMADZU\Claude Cowork - Work\claude additional.md`
  (a generic WAT — Workflows/Agents/Tools — framework template) for possible inclusion
  in AGENTS.md. Recommended against it: the `tools/`, `workflows/`, and `.tmp/`
  directories it assumes do not exist in this project, its delegate-to-scripts
  operating model conflicts with direct editing of the Flask monolith, and its
  "deliverables live in cloud services, local files are disposable" principle
  contradicts this repository being the source of truth. Owner confirmed to disregard
  it. Nothing from that file was added.
* Added the `changes.md` change-journal rule to AGENTS.md as a subsection of section 3
  (Git and Data Rules): read this file before any change, write a detailed entry after
  every change, one dated block per day with newest at top, same-date changes append
  to the existing block, Manila dates, record reverts and abandoned approaches, note
  commit hashes or state plainly when unpushed, and commit `changes.md` alongside the
  change it describes. Also referenced the rule in AGENTS.md section 11 (Definition of
  a Good Session).
* Created this `changes.md` at the project root. Not committed — see the sandbox rule
  below; nothing in this folder gets committed.
* Owner designated this folder
  (`D:\Shimadzu\Projects\SHIMADZU\Claude-medical-service-sms-railway`) as a **local
  sandbox for tests only — never commit, never push** unless the owner explicitly says
  so for a specific action. Added this to AGENTS.md section 3 as a "Which workspace am
  I in?" table distinguishing this sandbox from the live working copy at
  `D:\Shimadzu\Projects\SHIMADZU\medical-service-sms-railway`, which keeps the original
  push-by-default behavior. Also scoped the "Default deployment preference" subsection
  to the live copy only, and amended the `changes.md` rule so this file is committed in
  the live copy but stays local here.
* Recorded in AGENTS.md that read-only git commands (`status`, `log`, `diff`, `show`)
  remain allowed in the sandbox, but `add`, `commit`, `push`, `stash`, `reset --hard`,
  and `checkout --` are not — so git state here is never altered.
* Resolved the open question from earlier today about whether `changes.md` should be
  committed: in this folder it will not be, which makes it the sole record of sandbox
  work and raises the importance of keeping it detailed.

codex changes - 2026-07-28
- Changed Reimbursement Load Schedules behavior so matching Submitted, Approved, and Paid date ranges no longer reopen or lock the worksheet; only an existing Draft or Rejected record is resumed automatically.
- Added exact `reimbursement_id` record loading throughout Reimbursement history, notifications, draft save, submit, deletion, clearing, receipt management, LPR review, and package downloads so multiple requests can safely share the same start and end dates.
- Kept locked Reimbursement records as immutable historical snapshots that open only through their specific history or notification record, with their original rows, receipts, linked LPR, approvals, and generated forms.
- Refined claimed-schedule filtering to exclude only exact schedule IDs with positive reimbursement amounts in Submitted, Approved, or Paid records; zero-value rows, broad header ranges, package receipts, and legacy row receipts no longer claim unrelated schedules.
- Filtered stale Draft/Rejected rows against the latest claimed schedule IDs during reload so a schedule claimed in another locked request cannot reappear from older editable worksheet data.
- Added available and excluded schedule counts to Reimbursement schedule-load responses and status messaging, while preserving independent schedules that occur on the same date.
- Added server-side claimed-schedule revalidation during Save Draft and Submit, plus ordered schedule-row locking during final submission, to prevent stale or simultaneous browser tabs from claiming the same schedule.
- Added focused regression coverage proving that a locked monthly record cannot replace an editable record with the same range and that zero-value rows do not claim their schedules.
- Added a July 28 What's New entry for reusable reimbursement ranges and bumped the service-worker cache to `v42-reimbursement-range-reuse`.
- Added visible Delete controls to every editable Reimbursement schedule row and manual item on desktop and mobile, with confirmation that Calendar schedules and package-level receipts remain untouched.
- Added a persistent Removed Rows panel to Reimbursement with removed-row counts, individual Restore, and Restore All actions that preserve each row's prior amounts and remarks.
- Added an additive `reimbursement_header.excluded_rows_json` field and controlled runtime migration so removed schedule rows remain excluded after draft save, page navigation, and reload without replacing the database.
- Added server-side validation that removed schedule rows belong to the logged-in engineer and selected reimbursement date range, while limiting stored snapshots to safe worksheet data required for restoration.
- Updated Reimbursement draft save/load APIs to persist active rows and excluded snapshots atomically, report removed-row counts, and prevent the same schedule from being both active and excluded.
- Added Reimbursement approval-audit and Activity Log details for worksheet row removal/restoration, while keeping deletion and restoration unavailable on Submitted, Approved, Paid, and other locked records.
- Reconciled editable auto-generated Reimbursement LPRs during row deletion and restoration so Office/Field Items source lines and totals follow the active worksheet rows.
- Standardized Travel and Cash Advance Liquidation row deletion confirmation text, duplicate-click protection, result feedback, and linked-receipt counts across desktop, mobile, and dark mode.
- Changed both Liquidation row deletion paths to commit row and receipt-record removal before cleaning bucket or legacy files, then return a clear administrator-cleanup warning if physical storage deletion fails.
- Added Liquidation row-deletion Activity Logs while retaining universal approval-audit entries and automatic recalculation of totals, due-to-company, and due-to-employee balances.
- Added July 28 What's New entries for Reimbursement row restoration and safer Liquidation row cleanup, and bumped the service-worker cache to `v41-row-deletion`.
- Replaced the Approval Center's Reimbursement-specific default modal heading with a neutral request-review state so failed Travel Request, Liquidation, Cash Advance, LPR, and Leave Request loads cannot display stale Reimbursement wording.
- Added centralized module-specific Approval Center wording for Reimbursement, Travel Request, Travel Liquidation, Cash Advance, Cash Advance Liquidation, LPR, and Leave Request.
- Added a modal load sequence guard that ignores stale asynchronous responses when approvers switch quickly between request cards or modules.
- Added module-specific failure headings and subtitles so authorization or loading errors identify the request type that actually failed.
- Standardized correction workflows on `Return for Correction` or `Return for Revision`, while preserving `Reject` specifically for Leave Requests.
- Renamed shared `Manager Remarks` wording to `Approver Remarks` and aligned each remarks placeholder with its module's Return or Reject behavior.
- Replaced ambiguous `Liquidation` and `CA Liquidation` labels with `Travel Liquidation` and `Cash Advance Liquidation`.
- Updated Approval Center queue and history descriptions to include every active workflow, and added Leave Request to the Active Modules summary.
- Updated Reimbursement review headings to use the request number when available instead of displaying only the database record ID.
- Added Approval Center wording regression tests, a What's New entry, and a service-worker cache bump for immediate frontend delivery.
- Added Full Day and Half Day duration controls to Leave Request, with a required AM or PM selection for half-day requests.
- Restricted half-day Leave Requests to one weekday and synchronized the From and To dates automatically in the form and backend validation.
- Added additive `duration_type` and `half_day_period` Leave Request fields while preserving the existing integer weekday count for historical compatibility.
- Added effective leave-duration labels and values across Leave Request history, My Requests, Approval Center, and related API responses.
- Made Leave Request conflict checking time-aware so AM and PM requests block only overlapping schedules or active leave periods while allowing the opposite half of the day.
- Updated protected Leave Request Calendar entries to use 8:00 AM-12:00 PM for AM leave, 1:00 PM-5:00 PM for PM leave, and clear half-day titles.
- Updated Form-to-Follow, formal submission, approval rechecks, rejection recovery, and resubmission to preserve half-day periods without duplicate Calendar entries.
- Updated the official Leave Form PDF Inclusive field to print `0.5 Day (AM)` or `0.5 Day (PM)` and updated HR email template values to use `0.5`.
- Added a July 28 What's New entry for Half-Day Leave Requests and bumped the service-worker cache to deliver the updated workflow.
- Added focused regression coverage for half-day persistence, validation, conflict rules, Calendar times, PDF output, and user-facing displays.
- Added a project-level `AGENTS.md` instruction requiring Codex to read this change log before every modifying request.
- Established mandatory detailed change logging for every project or system addition, edit, deletion, rename, move, generated artifact, behavior change, test change, migration, or deployment-relevant update.
- Defined the dated `codex changes - YYYY-MM-DD` format, newest-first ordering, same-day entry appending, secret-redaction requirements, and the exception for read-only work that does not alter project files or system state.
