# Medical Service SMS — Pending Work

Everything started but not finished, plus anything deliberately deferred.
Companion to `changes.md`, which records what **was** done. This file records what is
**still open**.

**Update rule:** only touch this file when the project owner explicitly asks. It is not
maintained automatically the way `changes.md` is.

Last filled: 2026-07-30 (end of session)

**Where the work lives:** this repository, `medical-service-sms-railway`, working directly.
The sandbox at `Claude-medical-service-sms-railway` still exists, synced to `baefb63`, and
is no longer the default. This repository is push-by-default per AGENTS.md section 3, so
there is no free-experimentation area — if the sandbox is used again,
`git fetch && git reset --hard origin/main` there first, since it drifts the moment anything
lands here.

**Shipped this session** — all pushed to `origin/main`:

| Commit | What |
| --- | --- |
| `a0435f3` | Dashboard phase 2 — scheduler rebuilt as a dispatch workbench |
| `5d5b647` | Dashboard phase 3 — manager rebuilt around decisions and direction |
| `88b88cc` | Dashboard phase 4 — shortcuts consolidated, two unreachable sections retired |

Suite green at **299 tests** (was 252 at the start of the session). Service worker cache at
**`v48-hybrid-focus`**.

**The dashboard redesign is complete.** All four phases are shipped:

| Commit | Phase |
| --- | --- |
| `baefb63` | 1 — engineer, "Today First" |
| `a0435f3` | 2 — scheduler, dispatch workbench |
| `5d5b647` | 3 — manager, decisions and direction |
| `88b88cc` | 4 — shortcuts consolidated, dead sections retired |

---

## 1. Open bugs

**None currently open.**

---

## 2. Queued work

### Role gating predicates need a deliberate decision — HIGHEST VALUE

Phase 4 discovered that `is_manager_dashboard_user()` (`app.py:7412`) returns true for
`is_admin_authorized and not is_scheduler_user`. That single clause swallows every admin
account into the manager view, which made the hybrid admin+engineer sections
**unreachable by construction** — their gate was `admin_view and not manager_view`, which
cannot be satisfied. Confirmed against every account in the database: none could reach them.

Nobody would have chosen that outcome; it is a side effect. `jonamar`, `robert`, `rodito`
and `kevin` all hold engineer profiles, so they are genuinely admin+engineer, and they all
receive the manager view plus the engineer sections stacked beneath it.

The decision to make: **should an admin who also holds an engineer profile get a distinct
view, or is manager + engineer stacked the intended experience?** Phase 4 assumed the
latter and retired the dead sections rather than reviving them. If that is wrong, the
predicate is where to start.

`tests/test_dashboard_hybrid.py` pins the clause deliberately, so any attempt to revive
those sections has to confront the predicate first rather than rediscovering this.

### `recent-activity` is behind the same unsatisfiable gate

`templates/dashboard.html` gates `recent-activity` on
`admin_view and not scheduler_only and not manager_view` — the same condition proven
unsatisfiable above. So the section never renders, and the activity-log poll in
`static/js/app-dashboard.js` **including its 5-second `setInterval`** never runs. Confirmed
against a live server: zero requests logged.

Harmless as it stands, but it is dead weight. Deliberately left out of phase 4 rather than
widening scope beyond the two sections the owner approved. Same fix pattern: retire the
markup, keep the id in `DASHBOARD_SECTION_IDS`, and delete the loader.

### `/get_engineer_dashboard_summary` has zero callers

`app.py:18488`. No references in any `.js` or template; appears only in the perf-log path
list. The same dead-route shape as `/get_scheduler_dispatch_intelligence`, which phase 2
activated, and the two hybrid endpoints phase 4 deleted. Decide whether to wire it up or
remove it.

### What's New — digest: first real send still not done — DO THIS CAREFULLY

**`CHANGELOG_DIGEST_ENABLED` is `true` on Railway** and the feature has been deployed since
`0447392`. **No digest has been sent to anyone yet.**

Before the first real send, in this order:

1. Open What's New → **Email digest** and read the **resolved recipient count** for each
   audience. That count is the safeguard; nothing else stands between a click and real mail.
2. **Send test to me** first — it goes only to the requesting admin's own address. Confirm
   it arrives and reads correctly.
3. Only then a real audience send, with the count confirmed.

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

**Note:** the changelog now carries entries up to `sort_order: 180` under the `2026-07-29`
release, covering all four dashboard phases. A digest sent now will include them.

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

None of this is known broken — it simply has not been checked.

| Item | Applies to |
| --- | --- |
| **Edge and Brave** | every dashboard phase, login redesign, sidebar, What's New, digest modal |
| **Offline behaviour against a real service worker registration** | login offline shell, dashboard assets, changelog assets. Real workers *were* registered during phases 2–4 verification (`v46`, `v47`, `v48` all observed), but the offline path itself has still not been exercised |
| **Mobile viewport (375px)** | the What's New filter/search row. Every dashboard phase was checked at 375px; this row still has not been |
| **Skip link visual reveal on real keyboard focus** | layout shell |
| **A real digest email as received** | the HTML was verified in the preview pane, never in an actual inbox. Mail clients strip and rewrite CSS; check before sending to an audience |

On the skip link: the Browser pane does not composite frames, so CSS transitions never
advance, and its window is unfocused so `:focus` never matches. Disabling the transition
proved the element positions correctly, but the actual reveal was never seen.

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
- [ ] Confirm the commit contents with `git show --name-only` before pushing
- [ ] Focused commit message; push `main`
- [ ] Confirm only known local artifacts remain dirty: `scheduler.db`, `output/`, `tmp/`,
      and the 2026-07-26 handoff document
- [ ] A user-facing change needs a `releases.json` entry dated the commit date, or
      `tests/test_changelog_coverage.py` fails the commit

**`scheduler.db` is tracked.** `.gitignore` lists `*.db`, but that only applies to
*untracked* files, so **gitignore does not protect it**. Exclude it by name at every step.
Same for `.env`, which holds a real Brevo API key.

**Bump the service worker cache** whenever an `APP_SHELL` entry changes, or field devices
keep the old copies. Tests use `assert_cache_version_at_least`, so a bump never breaks them.
Currently `v48-hybrid-focus`.

**Multi-line commit messages:** write them to a file and use `git commit -F <file>`. A
PowerShell here-string breaks on double quotes inside the message and silently reinterprets
the body as pathspecs.

**Running the app for verification:** explicit `MEDICAL_SERVICE_TEST_DB`, never port 5000,
never `preview_start` name-mode, and stop every server afterwards. The Browser pane blocks
origins it has not registered, so open the app with `preview_start` passing the URL.

Two traps that cost real time this session:

- **`/static/` is `cacheFirst` and the service worker re-registers on every page load.**
  Unregister it and clear both caches after *each* asset edit, not once, or you will review
  a stale file and conclude the change did not work.
- **Template edits need a server restart.** Jinja caches compiled templates, so a changed
  `{% if %}` gate will keep evaluating the old way until the process is restarted.

**Test isolation caveat:** every test module pins `MEDICAL_SERVICE_TEST_DB` with
`os.environ.setdefault`, so under `unittest discover` the **first module to import wins and
all modules share one database and one Flask app**. Two cross-module failures came from this:
seeding an account named `rodito` makes `ensure_default_approval_routes()` write
`ApprovalRouting` rows whose NOT NULL requester FK then breaks sibling modules, and a
Completed shift seeded in one module landed inside another module's week-over-week window.
Both modules now clean up in `tearDownClass`. If a new module seeds users or shifts, it must
do the same.

---

## 5. Decided against — do not re-raise

**Reviving the hybrid dashboard sections.** `needs-attention` and `team-intelligence` were
retired in phase 4 rather than made reachable. The manager watchlist already consolidates
severe overdue, aged TSR, blocked jobs, repeat equipment and at-risk clients into one
de-duplicated list with the engineer-workload drill-down beside it, and it renders. Revisit
only as part of the role-gating decision in section 2.

**Inline approve/reject on the manager dashboard.** Considered in phase 3 and declined: it
would mean deciding a money-carrying request without seeing its contents, and it widens the
authorization surface onto the dashboard. Approving stays on `/approvals`.

**A change figure on current-state totals.** Phase 3 added week-over-week deltas to *flow*
metrics only (visits completed, visits scheduled, TSR completion rate). Currently-overdue and
currently-pending-TSR deliberately carry **no** comparison: a shift that was overdue last
week and has since been completed has left the overdue set, so any reconstructed historical
figure is systematically undercounted. That would be a wrong number wearing an authoritative
arrow.

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

## 6. Pattern worth knowing before the next feature

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
