# Changelog Release Manifest

Every user-facing deployment must update `releases.json` before commit and push.

- Use Manila deployment date as `release_key` and `release_date` (`YYYY-MM-DD`).
- Append to the existing daily release when multiple patches ship on the same date.
- Give every item a permanent, unique `item_key`.
- Write user-facing behavior, not filenames, commits, or implementation details.
- Choose one or more audiences: `everyone`, `engineers`, `approvers`, `admins`.
- Accounting workflow changes currently target `engineers`, `approvers`, and `admins`.
- Never remove an old manifest item after it has reached live; hide or correct it through the admin editor.
