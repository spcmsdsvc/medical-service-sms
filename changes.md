# Project Change Log

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
