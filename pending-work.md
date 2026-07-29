# Medical Service SMS — Pending Work

Everything started but not finished, plus anything deliberately deferred.
Companion to `changes.md`, which records what **was** done. This file records what is
**still open**.

**Update rule:** only touch this file when the project owner explicitly asks. It is not
maintained automatically the way `changes.md` is.

Last filled: 2026-07-29 (end of session)

**Where the work lives now:** this repository, `medical-service-sms-railway`. The owner
moved the working directory here on 2026-07-29. The sandbox at
`Claude-medical-service-sms-railway` still exists and is kept, synced to `baefb63`, but is
no longer the default. This repository is push-by-default per AGENTS.md section 3, so there
is no free-experimentation area — if the sandbox is used again, `git fetch && git reset
--hard origin/main` there first, since it drifts the moment anything lands here.

**Shipped this session** — all pushed to `origin/main`:

| Commit | What |
| --- | --- |
| `baefb63` | Logout fix, plus promotion of login/sidebar/dashboard/What's New from the sandbox |
| `69c975c` | What's New email digest made usable, sending still disabled |
| `0447392` | Digest recipients driven by audience, per-send update selection |

Suite green at **252 tests**. Service worker cache at **`v45-digest-audience`**.

---

## 1. Open bugs

**None currently open.**

### ~~Logout does not log users out — HIGH~~ — FIXED 2026-07-29

`/logout` left the remember-me cookie alive, so the next request silently signed the user
back in. Fixed by adding `clear_remember_cookie()` beside `clear_pwa_login_cookie()` and
calling it from the route, rather than the one-line reorder originally proposed here — the
explicit deletion does not depend on Flask-Login internals or handler ordering. Covered by
`tests/test_logout_session.py` (11 tests), proven to fail without the fix. See the
2026-07-29 entry in `changes.md` for the full account.

The side effect this had on verification is also cleared: switching accounts in a browser
works again, so cross-role checks no longer have to go through the Flask test client.

---

## 2. Not yet verified

None of this is known broken — it simply has not been checked.

| Item | Applies to |
| --- | --- |
| **Edge and Brave** | login redesign, sidebar, engineer dashboard, What's New, digest modal |
| **Offline behaviour against a real service worker registration** | login offline shell, dashboard assets, changelog assets — partially exercised on 2026-07-29 (a real worker was registered during logout verification), but the offline path itself was still not tested |
| **Mobile viewport (375px)** | the What's New filter/search row. The digest modal *was* checked at 375px on 2026-07-29 and is fine; the filter row above it still has not been |
| **Skip link visual reveal on real keyboard focus** | layout shell |
| **A real digest email as received** | the HTML was verified as rendered in the preview pane, never in an actual inbox. Mail clients strip and rewrite CSS; check before sending to an audience |
| ~~Cross-role browser checks~~ | **unblocked 2026-07-29** — the logout fix restored account switching |

On the skip link: the Browser pane does not composite frames, so CSS transitions never
advance, and its window is unfocused so `:focus` never matches. Disabling the transition
proved the element positions correctly, but the actual reveal was never seen.

---

## 3. Queued work

### Dashboard — phases 2 to 4 — AGREED NEXT TASK

The owner deferred this on 2026-07-29 to finish the What's New digest first, and named it
as what to return to.

Phase 1 (engineer) is done. The template serves every role from one file, so each phase
must leave the others untouched; `tests/test_dashboard_engineer.py` already guards that.

- **Phase 2 — Scheduler:** `scheduler-core`, `scheduler-dispatch`,
  `scheduler-coordination`, `scheduler-final-note`
- **Phase 3 — Manager:** `manager-executive`, the densest single view; the best test of
  whether tabs are needed rather than the Today-First pattern
- **Phase 4 — Hybrid (admin + engineer):** the owner's own view, and the most cramped —
  originally 11 tiles across 10 sections

**Carry into phase 2:** `templates/dashboard.html` still computes
`dashboard_scheduler_account` from hardcoded `['diary', 'hanna']` — the same anti-pattern
removed from `layout.html`. It was left in place because it gates the scheduler and
manager sections that phase 1 was required not to touch. `is_scheduler_user()` already
exists server-side.

**Explicitly deferred by the owner:** lazy fetching of collapsed dashboard sections.
Phase 1 was "show less, fetch the same" — endpoints and data logic untouched.

### What's New — digest: first real send not yet done — DO THIS CAREFULLY

**`CHANGELOG_DIGEST_ENABLED` is now `true` on Railway.** The owner set it on 2026-07-29.
The buttons are live once `0447392` deploys. No digest has actually been sent to anyone yet.

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

- **No idempotency.** Pressing send twice sends twice. This matters more now that audience
  mode reaches every matching account rather than a short curated list.
- **No unsubscribe.**
- The digest is **the latest 5 releases**, not per-recipient unread — someone who has read
  everything still receives a full digest. Making it per-recipient is a considerably larger
  change and is deliberately separate work.
- **No scheduled or recurring delivery.** Manual only, by design.

Both send paths remain available: audience mode (default) and the Settings-managed
*What's New Announcements* group. Naming a group without a mode still means the group, so an
explicit group send cannot be silently widened to the whole audience.

### Stock inventory barcode scanner — pre-dates this session

From the 2026-07-26 handoff and still open. The physical scanner arrived but has never
been validated against production behaviour.

Collect before changing any scanner logic: scanner model, the exact scanned string,
whether it sends Enter/CR, the browser used, whether one physical scan opens one modal,
whether focus returns after save or cancel, and any exact API error.

Watch for: no Enter/CR suffix, the barcode field losing focus, rapid scans opening
duplicate modals, stripped leading zeroes, one scan producing duplicate events, branch
context not retained, focus not returning to the scan input after a modal closes.

Reproduce with keyboard input locally first.

---

## 4. Committing here — standing rules

The sandbox-to-live promotion is **done** (`baefb63`, 2026-07-29). Work now happens in this
repository directly, so every commit is one step from deployment.

Standing checklist for any commit here:

- [ ] `git status --short`, then inspect the diff
- [ ] Stage **explicitly, file by file** — never `git add -A`
- [ ] `git diff --cached --check` for whitespace
- [ ] Confirm the commit contents with `git show --name-only` before pushing
- [ ] Focused commit message; push `main`
- [ ] Confirm only known local artifacts remain dirty: `scheduler.db`, `output/`, `tmp/`,
      and the 2026-07-26 handoff document
- [ ] A user-facing change needs a `releases.json` entry dated the commit date, or
      `tests/test_changelog_coverage.py` fails the commit

**`scheduler.db` is tracked.** `.gitignore` lists `*.db`, but that only applies to
*untracked* files, so **gitignore does not protect it**. Exclude it by name at every step.
Same for `.env`, which holds a real Brevo API key — it was never copied into the merge
clone during promotion for that reason.

**Bump the service worker cache version** whenever an `APP_SHELL` entry changes, or field
devices keep the old copies. Tests use `assert_cache_version_at_least`, so a bump never
breaks them. Currently `v45-digest-audience`.

**Running the app for verification:** explicit `MEDICAL_SERVICE_TEST_DB`, never port 5000,
never `preview_start` name-mode, and stop every server afterwards. The Browser pane blocks
origins it has not registered, so open the app with `preview_start` passing the URL. Note
`/static/` is `cacheFirst` in the service worker — after changing a static asset, unregister
the worker and clear caches or you will be looking at the old file.

---

## 5. Decided against — do not re-raise

**Clearing the service worker runtime cache on logout.** Authenticated HTML persists in
`RUNTIME_CACHE` after sign-out, so on a shared device an offline user could see the
previous user's cached pages. The owner confirmed on 2026-07-28 that engineers are issued
**1:1 devices**, so the scenario does not occur in practice.

Two minor residual behaviours were accepted rather than fixed: `/logout` is itself cached
in the runtime cache, so an offline logout may not reach the server; and
`staleWhileRevalidate()` can return slightly stale HTML for same-origin non-navigation
GETs. Neither is an exposure on a personal device.

Revisit only if loaner or shared laptops become routine.
