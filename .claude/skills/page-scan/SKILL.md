---
name: page-scan
description: Deep read-only scan of one page for bugs, broken functions, simplifications, dead code, and missing functions/features. No UI or design. Use when the owner says "scan <page>".
---

# Page Scan

Read-only. Change no files. Fixes go to `plans.md` only after the owner approves.

## Scope
The page's template, its JS, its `app.py` routes and the helpers they call. Skip UI and design (that has its own skill).

## Check
1. Bugs: errors, wrong labels, wrong titles, wrong values.
2. Functions not working properly: try every button and action (save, add, upload, submit, download).
3. Permissions: what each role can see or do, and whether the server enforces it (not just a hidden button).
4. Data safety: double submit, partial saves, unconfirmed deletes, overwrites.
5. Input checks: empty, long, special characters, bad dates or amounts, and whether the server validates too.
6. Generated files: Excel or PDF downloads open, and the right values are in the right cells.
7. Background errors: browser console, failed requests, server log.
8. Consistency: statuses, numbering and workflow steps match other pages.
9. Speed: repeated requests, slow queries, data loaded but not used.
10. Too complicated: functions that can be simpler.
11. Deletable code: dead functions, routes, duplicates. Grep for callers first; if anything still uses it, it stays.
12. Test gaps: functions with no test.
13. Missing: functions that are called but undefined, and features users would expect.

## How
- Use Grep, or Read with offset/limit. Don't read whole templates.
- Browser check: follow AGENTS.md and the browser-check-setup memory (copy of scheduler.db, cleanup afterwards). Use read_page and get_page_text, no screenshots.
- Report only real findings. No guesses, no padding. A section with nothing in it says "None".

## Report
One line per finding: severity (Critical/High/Medium/Low) · what · `file:line` · how to reproduce.
Order: Bugs and broken functions → Simplify → Delete → Add.
End with fixes proposed in small batches, smallest change first.
