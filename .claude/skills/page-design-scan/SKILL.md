---
name: page-design-scan
description: Read-only UI and design scan of one page. Uses Impeccable and DESIGN.md. No logic or bugs (that is page-scan). Use when the owner says "design scan <page>".
---

# Page Design Scan

Read-only. Change no files. Fixes go to `plans.md` only after the owner approves.

## Before scanning
- Read `DESIGN.md` (the project's design rules) and `.impeccable/critique/ignore.md` (decisions already made). Don't raise ignored items again.
- Check `plans.md`, `pending-work.md` and `.impeccable/critique/` for planned or open UI work on this page.

## Check
1. Layout and hierarchy: what the eye sees first, spacing, alignment, crowding.
2. Text: wording, button labels, empty and error messages that are clear to a field engineer.
3. Consistency: matches DESIGN.md and other pages (status colours, buttons, tables, cards). Request pages (Travel Request, Cash Advance, Reimbursement, and any new request form) use the `.request-page` wrapper and the Page Header: status chip beside the title, New Request (or New Period) button under the subtitle on the left, same 1220px column and left edge.
4. Phone (375px): no horizontal scroll, taps ≥ 44px, cards readable.
5. Dark mode and AMOLED: contrast ≥ 4.5:1 for text, nothing invisible.
6. Accessibility: keyboard use, focus visible, labels on inputs and icons.
7. States: loading, empty, error, disabled, long text.
8. Speed you can feel: layout jumps, slow first paint, heavy images.

## How
- Run one Impeccable critique (only one per session, per AGENTS.md).
- Browser check: follow AGENTS.md and the browser-check-setup memory. Use read_page and get_page_text, and measure with javascript_tool. Screenshots only as final proof.
- Report only real findings, each backed by a measurement or a DESIGN.md rule. No taste-only opinions.

## Report
One line per finding: severity · what · where (`file:line` or element) · measurement or rule broken.
List planned UI work separately from new findings.
End with a closed list of fixes in small batches. That list is the whole job: no new issues are added later (critique-loop rule).
