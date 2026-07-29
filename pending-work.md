# Medical Service SMS — Pending Work

Everything started but not finished, plus anything deliberately deferred.
Companion to `changes.md`, which records what **was** done. This file records what is
**still open**.

**Update rule:** only touch this file when the project owner explicitly asks. It is not
maintained automatically the way `changes.md` is.

Last filled: 2026-07-29

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
| **Edge and Brave** | login redesign, sidebar, engineer dashboard, What's New |
| **Offline behaviour against a real service worker registration** | login offline shell, dashboard assets, changelog assets — partially exercised on 2026-07-29 (a real worker was registered during logout verification), but the offline path itself was still not tested |
| **Mobile viewport (375px)** | the new What's New filter/search row |
| **Skip link visual reveal on real keyboard focus** | layout shell |
| ~~Cross-role browser checks~~ | **unblocked 2026-07-29** — the logout fix restored account switching |

On the skip link: the Browser pane does not composite frames, so CSS transitions never
advance, and its window is unfocused so `:focus` never matches. Disabling the transition
proved the element positions correctly, but the actual reveal was never seen.

---

## 3. Queued work

### Dashboard — phases 2 to 4

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

### What's New — digest delivery

Built but dormant. `CHANGELOG_DIGEST_ENABLED` defaults to **false** and is checked
independently of `EMAIL_NOTIFICATIONS_ENABLED` (which defaults to true), so a sandbox
holding a real Brevo key cannot email live engineers.

- Preview renders the exact HTML and calls no sender.
- `POST /api/changelog/admin/digest/send` returns 409 while disabled.
- **Not built:** scheduled or recurring delivery. Manual preview only, by design.
- Before enabling in production: confirm the recipient group, send one test to a
  controlled address, and only then turn the flag on.

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

## 4. Promotion to live

Owner decided on 2026-07-29 to promote **everything as one commit**.

**The sandbox was 5 commits behind live** (`b791a3c` vs `e2cae2e`), so this is a merge,
not a file copy. Live had gained half-day leave, reimbursement row removal/restore,
reimbursement range reuse and Approval Center wording — 563 lines of `app.py` alone.

Validated in a throwaway clone of live `main` before touching the real copy:

- [x] Decide what moves — everything, one commit
- [x] 13 of 14 files applied cleanly; **one conflict**, both sides having independently
      bumped the service worker to `v42`. Resolved to **`v43-shell-dashboard-changelog`**;
      leaving it at v42 would have meant clients already on live's v42 never invalidating
- [x] Verified line-by-line that neither side lost work: 354 of live's 355 `app.py`
      additions and 819 of the sandbox's 820 survive, the odd one out on each side being
      the superseded cache-version line
- [x] Added the 2026-07-29 `releases.json` entry (9 items). Required — otherwise
      `tests/test_changelog_coverage.py` fails the commit
- [x] The 2026-07-24 backfill entry (TSR archive sort) is carried across
- [x] Full suite green in the merged tree at **229 tests** (the sandbox's 213 plus live's
      16), zero failures
- [ ] Complete the browser verification listed in section 2
- [ ] Follow the standing push checklist: inspect `git status --short`, inspect the
      diff, stage explicitly, `git diff --cached --check`, focused commit message, push
      `main`, confirm only known local artifacts remain dirty
- [ ] Never stage `scheduler.db`, `output/`, `tmp/`, `.env`

**`scheduler.db` is tracked in both repos.** `.gitignore` lists `*.db`, but that only
applies to untracked files, so gitignore does **not** protect it. It has to be excluded by
name at every step. `.env` was likewise never copied into the merge clone — it holds a
real Brevo API key.

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
