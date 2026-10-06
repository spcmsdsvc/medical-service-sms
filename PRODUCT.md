# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

Installable PWA (manifest + service worker with offline navigation). Used on desktop and on phones.

## Users

Design decisions favor, in order of priority:

- **The superadmin / developer** — builds and runs the system; needs every screen inspectable and maintainable.
- **Managers** — plan work, approve requests, review reports and money movements.
- **Senior engineers** — field service engineers doing installs, PM, repairs and calibration at hospitals; schedule, TSRs, travel and liquidation paperwork, often from a phone.

Other roles in the system: admin, scheduler, accounting, engineer.

## Product Purpose

Internal management system for Shimadzu's medical (imaging) service department. It schedules field engineers, records service work, and replaces the department's paper forms and approval chains.

Success means:

- **Replaces paper forms** — generated documents match the official company forms (`forms/`).
- **Fast approvals** — requests move through approval without chasing people.
- **Schedule visibility** — who is where, on which job, at a glance.
- **Audit trail** — every change and money movement is traceable.

## Operating Context

- Workflows: Timeline/calendar scheduling, Technical Service Reports (TSR, incl. offline TSR), calibration reports and certificates, inventory and PM (Genoray, Vieworks), stock inventory, clients, products, POs.
- Paperwork with approvals: Travel Request, Cash Advance, Travel and Cash Advance Liquidation, Reimbursement, Leave, LPR, petty cash; Approvals and Accounting Center queues.
- Engineers work on hospital sites and while traveling; office roles work on desktop.

## Capabilities and Constraints

- Stack: Flask + SQLAlchemy, Jinja templates, Bootstrap, Font Awesome; deployed on Railway from `main`.
- Themes: light, graphite, dark, system.
- Official form templates are binding sources for generated output: `forms/*.pdf`, `forms/*.xlsx`, `forms/*.xlsm`, `static/templates/`.
- Timezone: Manila.

## Brand Commitments

- Must follow the **Shimadzu corporate brand identity**.
- Logo on hand: `static/images/brand/shimadzu-philippines-logo-white.webp` (Shimadzu Philippines Corporation; red square mark, white logotype and subline on transparent, so use it on dark backgrounds only). The SHIMADZU logotype is custom lettering: always use the image, never retype it.
- Brand red measured from that logo: `#EE3239`. White text on it is 4.1:1, so text-bearing controls use the deeper `#D9262E` (4.9:1).
- Fira Sans (self-hosted, `static/fonts/fira-sans/`) is the closest free match to the logo's subline, used on the sign-in pages; not confirmed as the official typeface.
- Open: the official brand guide (full colour set, typeface, dark-text logo) is still not in the repository. Do not approximate further brand rules from memory.

## Evidence on Hand

- Official forms: `forms/`.
- Calibration report/certificate templates: `static/templates/`.
- Release history: `static/changelog/releases.json`; change journal `changes.md`.
- Shimadzu Philippines logo (white version): `static/images/brand/`. No brand guide on hand.

## Product Principles

1. The official paper form is the spec — on screen and in generated documents.
2. Never lose an approval or a peso: every state change is recorded and visible.
3. Next action obvious: each role sees what is waiting on them first.
4. Field-ready: engineer flows work on a phone with a weak connection.
