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
| **Verification** | Tests to add, each with the positive control that proves it can fail; the browser sequence; the standing bar (375 px, tap targets, console). Run the focused test modules for what changed; run the full suite only once, before publishing. |
| **After implementation** | The review and release workflow below, made concrete for this plan. |
| **Risks** | What could go wrong, what the blast radius is, and what the safety net is. |

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

