# Project Change Log

codex changes - 2026-07-28
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
