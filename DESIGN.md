---
name: Medical Service SMS
description: Internal service-management system for Shimadzu Philippines' medical imaging department.
colors:
  primary: "#0d6efd"
  primary-shimadzu-red: "#c8102e"
  brand-red-logo: "#ee3239"
  brand-red-text: "#d9262e"
  ground-light: "#f4f7f6"
  surface: "#ffffff"
  surface-raised: "#f8fafc"
  ink: "#172033"
  ink-muted: "#64748b"
  hairline: "#dbe3ea"
  sidebar: "#2c3e50"
  sidebar-deep: "#1a252f"
  sidebar-text: "#cbd5e1"
  sidebar-text-dim: "#a8b6c6"
  auth-ground: "#14181f"
  graphite-ground: "#202124"
  graphite-surface: "#292a2d"
  graphite-raised: "#333438"
  amoled-ground: "#000000"
  amoled-surface: "#101010"
  amoled-raised: "#191919"
  dark-ink: "#ededed"
  dark-hairline: "#626262"
typography:
  body:
    fontFamily: "'Fira Sans', 'Segoe UI', system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  title:
    fontFamily: "'Fira Sans', 'Segoe UI', system-ui, sans-serif"
    fontSize: "1.05rem"
    fontWeight: 700
  label:
    fontFamily: "'Fira Sans', 'Segoe UI', system-ui, sans-serif"
    fontSize: "0.78rem"
    fontWeight: 600
  micro:
    fontFamily: "'Fira Sans', 'Segoe UI', system-ui, sans-serif"
    fontSize: "0.72rem"
    fontWeight: 700
  auth:
    fontFamily: "'Fira Sans', 'Segoe UI', system-ui, sans-serif"
    fontSize: "0.85rem"
    fontWeight: 400
  document:
    fontFamily: "Cambria, 'Times New Roman', serif"
rounded:
  sm: "6px"
  md: "10px"
  lg: "12px"
  card-mobile: "16px"
  card-mobile-page: "14px"
  dialog-mobile: "18px"
  pill: "999px"
spacing:
  touch: "44px"
  mobile-gutter: "14px"
  sidebar-row: "44px"
  sidebar-subrow: "38px"
  sidebar-width: "240px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.md}"
  card-mobile:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.card-mobile}"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
  nav-sidebar:
    backgroundColor: "{colors.sidebar}"
    textColor: "{colors.sidebar-text}"
    height: "{spacing.sidebar-row}"
  nav-sidebar-header:
    backgroundColor: "{colors.sidebar-deep}"
  chip-status:
    rounded: "{rounded.pill}"
  button-auth:
    backgroundColor: "{colors.brand-red-text}"
    textColor: "{colors.surface}"
---

# Design System: Medical Service SMS

## Overview

**Creative North Star: "The Service Logbook"**

A field engineer's logbook made digital: dense, orderly, and trustworthy. Every screen is a working page — schedules, reports, requests, approvals — and the design's job is to make the next entry obvious and the record legible. Expression is kept to precise details; the paper forms the system replaces remain the visual authority for anything that gets printed or generated.

The app is built on Bootstrap 5.3 with a thin token layer (`static/css/app-themes.css`) that every page inherits. A dark slate sidebar frames a pale, cool-grey work area of white panels. The user chooses the mode (light, graphite, AMOLED dark, or system) and one accent from seven; all accent-coloured UI flows from the single `--app-primary` variable, so nothing hardcodes its own blue. Sign-in pages are the one branded moment: charcoal ground, the white Shimadzu logo, Fira Sans, and Shimadzu red.

**Key Characteristics:**
- Operate mode: scanability and consistency over expression.
- One accent variable drives buttons, links, focus, active nav and pagination.
- Four themes; generated documents always render on fixed white.
- Phone-ready: 44px touch targets, 14px safe gutter, stacked cards instead of wide tables.

## Colors

A cool, low-chroma neutral system with one user-selectable accent; colour signals action and state, never decoration.

### Primary
- **Classic Signal Blue** (`primary`): the default accent. Primary buttons, links, focus rings, active sidebar rail, pagination, checked inputs. Hover and active states are derived with `color-mix` toward black (84% / 76%); soft fills and borders mix it into the surface (10% / 24%).
- **Shimadzu Accent Red** (`primary-shimadzu-red`): the "Shimadzu Red" accent option, replacing the primary everywhere when chosen. Other options: Clinical Green `#198754`, Corporate Blue `#2563eb`, Purple `#8b5cf6`, Pink `#be185d`, Teal `#0f766e`.

### Brand (sign-in only)
- **Logo Red** (`brand-red-logo`): measured from the logo; the brand rule (`--brand-rule`): the short rule under the sign-in logo and a 2px inset rule along the bottom of the sidebar header and phone top bar. Never behind text. A chosen accent theme recolours the rule.
- **Deep Brand Red** (`brand-red-text`): the sign-in button colour; white text passes AA on it (4.9:1).

### Neutral
- **Cool Mist Ground** (`ground-light`): the light-mode page background.
- **Paper White** (`surface`) / **Frost Raised** (`surface-raised`): panels and cards / headers, footers, disabled inputs.
- **Deep Navy Ink** (`ink`) / **Slate Muted** (`ink-muted`): body text / secondary text and help text.
- **Hairline** (`hairline`): borders and dividers.
- **Logbook Slate** (`sidebar`) / **Midnight Slate** (`sidebar-deep`): sidebar body / sidebar header; light text tokens `sidebar-text` and `sidebar-text-dim` (4.5:1 for small uppercase group labels).
- **Graphite** (`graphite-*`) and **AMOLED** (`amoled-*`) sets: the two dark palettes, with `dark-ink` text and `dark-hairline` borders.

### Named Rules
**The One Variable Rule.** Accent colour comes only from `--app-primary` (and its derived `--app-primary-soft`, `-strong`, `-text`, `--app-focus`). A hardcoded accent hex breaks the user's chosen theme.

**The White Paper Rule.** Document canvases, PDF and TSR previews, signature pads and print output are always `#fff` on `#000`, in every theme — they represent the official paper form.

**The Semantic Status Rule.** Schedule and status colours stay semantic and are not re-themed by the accent. Rejected and Returned are red (`status-rejected`, light `#fde8ea`/`#a1121f`), never grey; waiting time is a text chip ("N days", slate, red past 30 days; dashboard "N days late"), never colour alone.

## Typography

**App Font:** Fira Sans, self-hosted (400/500/600, with Segoe UI, system-ui), one family for the whole app including sign-in, via `--app-font` in `app-themes.css` (also Bootstrap's `--bs-body-font-family`). Weights above 600 render as 600. Tables use tabular figures.
**Document Font:** Cambria (with Times New Roman) for calibration reports and certificates

**Shell scale:** the sidebar, flyouts and phone bar use three steps from `app-shell.css`: `--shell-text-row` 0.9rem (rows, flyout rows, phone bar title), `--shell-text-subrow` 0.84rem (sub-rows, account name, hover name label), `--shell-text-micro` 0.72rem (group labels, flyout titles, role, count badges, initials); the rail's icon captions use micro too and wrap to a second line rather than shorten a label; the pinned brand name is 1rem.

**Character:** One humanist sans, close to the logo's subline, across app and sign-in; a serif only where it mirrors the official printed form.

**Logbook detail:** record numbers (My Requests) and entry dates (Dashboard) use `.logbook-ref` in `app-dashboard.css`: a system monospace stack (ui-monospace, Consolas) with tabular numbers and 0.02em tracking, so they read like logbook entries and line up. It is the one signature detail; no logo, brand red or greeting in work areas.

### Hierarchy
- **Title** (700, ~1.05rem): card, panel and section titles; Bootstrap headings for page titles.
- **Body** (400, 1rem, 1.5): forms, tables, prose.
- **Label** (600, ~0.78–0.86rem): field labels, table meta, nav text, chips.
- **Micro** (700, ~0.66–0.72rem): uppercase sidebar group labels, badges, dense table annotations.

### Named Rules
**The Small-Text Contrast Rule.** Anything under ~0.8rem must still meet 4.5:1 — the sidebar dim text was raised to `#a8b6c6` for exactly this reason.

## Layout

On desktop (≥993px) the navigation is the pinned labelled sidebar by default at 1440px wide and up, and a 72px icon rail below that (a saved pin/collapse choice wins), beside a fluid main area using Bootstrap's grid and containers; hovering, focusing or tapping a group icon opens that group's links in a flyout beside the rail without moving the page, and pinning keeps it open and pushing the page (user-resizable 200–360px in 20px steps, pinned only). Fixed page docks follow `--shell-offset` (rail, pinned width, or 0 on phones). Rows in the sidebar are 44px (sub-rows 38px). Density is high on desktop: tables carry most data, with frozen columns and a horizontal-scroll hint that appears only when the table actually overflows.

Breakpoints follow Bootstrap: the main collapse happens at 768px, with further adjustments at 992, 640, 576 and 420px. At ≤768px the shell switches to a mobile nav, tables become stacked cards (16px radius), page panels drop their padding so cards sit on the shell gutter, and all tappable controls are at least 44px tall. Safe-area insets are respected top and bottom.

## Elevation & Depth

Mostly flat with soft ambient lift. Cards carry a barely-there shadow; themed panels use `--app-shadow`; in dark modes depth comes from the ground → surface → raised tonal steps rather than shadow.

### Shadow Vocabulary
- **Card rest** (`0 4px 6px rgba(0,0,0,.05)`): default Bootstrap card.
- **Panel** (`0 8px 24px rgba(15,23,42,.08)`, dark: `0 10px 28px rgba(0,0,0,.5)`): `--app-shadow`, themed panels.
- **Focus ring** (`0 0 0 .25rem var(--app-focus)`): inputs, selects, checkboxes, buttons on focus.
- **Selected option** (`inset 0 0 0 2px var(--app-primary)`): chosen appearance mode / accent tile.

### Named Rules
**The Tonal Dark Rule.** In graphite and AMOLED, separate layers with the surface tokens, not heavier shadows.

## Shapes

Gently rounded, never sharp and never bubbly. Controls and small buttons use 6px; cards 10–12px; phone cards 16px (phone page panels 14px, phone dialogs 18px, recorded as they ship, owner 2026-10-09); keyboard keys in the Menu guide 4px and the skip link's bottom corners 8px; status chips and swatches are full pills or circles. Other shell values the detector flags are recorded here too: the 0.95rem phone headings and icons, the `#e5e7eb` hairline on the phone docked bar, and shadows and scrims built on slate `rgba(15, 23, 42, α)`. Cards are borderless on light (shadow only); in dark modes they gain a `dark-hairline` border. The active sidebar item is marked by a 3px accent rail on the left edge.

## Components

### Buttons
- **Shape:** gently rounded (Bootstrap default ~6px).
- **Primary:** accent fill, white text; hover darkens to 84% accent, active to 76%.
- **Outline primary:** accent-text label and border, fills with accent on hover.
- **Focus:** accent border plus the 0.25rem focus ring.
- **Sign-in button:** Deep Brand Red (or the chosen accent, darkened for lighter accents).
- **Add / create (exception):** Bootstrap success green for Add buttons and their modal headers, e.g. Product Inventory. Owner decision 2026-10-07; the only allowed exception to the One Variable Rule.

### Chips / Badges
- **Style:** pill (999px), small label weight; status colours are semantic (Bootstrap success / warning / danger / info / secondary).
- **Dashboard task status** (`.dashboard-status-chip`, `static/css/app-dashboard.css`): fixed pairs that carry their own background, at least 0.75rem and 4.5:1 in every theme: In Progress `#3730a3` on `#eef2ff`, Waiting for P.O `#946200` on `#fff6db`, Waiting for Parts `#0369a1` on `#e0f2fe`, For Continuation `#334155` on `#f1f5f9`. Past-due adds a text chip ("N days late", `#a1121f` on `#fde8ea`) and a red left edge, never colour alone.
- **Inventory status** (`.product-status-pill`, `templates/products.html`; table, phone cards and count chips): soft pairs, 0.75rem/600, ≥4.5:1 in every theme. Light: Under Warranty `#166534` on `#dcfce7`, Under Contract and Expired - Under Contract `#854d0e` on `#fef3c7`, Expired - No Contract `#a1121f` on `#fde8ea`, No Expiry Set `#334155` on `#f1f5f9`. Dark: `#bbf7d0`/`#14532d`, `#fde68a`/`#4a3612`, `#fecdd3`/`#5c1a22`, `#e2e8f0`/`#334155`. Red only for Expired - No Contract, never a solid red fill (owner 2026-10-15).
- **PM action** (`.product-row-pm` desktop icon button, `.product-mobile-pm` phone button; Genoray/Vieworks only): teal. Light `#0f766e` on `#f0fdfa` (desktop, 6.40:1) and `#115e59` on `#ccfbf1` (phone, 5.92:1). Dark: `#5eead4` on `rgba(20,184,166,.16)` with a `#2dd4bf` border (8.4:1 Graphite, 11.9:1 AMOLED).
- **PM visit status** (`.pm-status`, `templates/inventory_pm.html`; Genoray PM and Vieworks PM): pills 0.75rem/600, ≥4.5:1 in every theme. Light: Planned `#1d4ed8` on `#dbeafe`, Overdue `#a1121f` on `#fde8ea`, Completed `#166534` on `#dcfce7`. Dark: `#bfdbfe`/`#1e3a8a`, `#fecdd3`/`#5c1a22`, `#bbf7d0`/`#14532d`. The page takes every other colour from the theme tokens and its table headers from `--app-primary`.
- **P.O. frequency** (`.po-type-badge`, `templates/po_details.html`): pills 0.72rem/600, ≥4.5:1 in every theme. Light: Single `#135bb4` on `#e0edff` (5.57:1), Semi Annual `#8a5700` on `#fff1d6` (5.46:1), Quarterly `#5b31a8` on `#e9e1ff` (6.81:1). Dark: `#bfdbfe`/`#1e3a8a`, `#fde68a`/`#4a3612`, `#ddd6fe`/`#3b2470`. Legacy Contract and Single Visit keep their own pairs.

### Cards / Containers
- **Corner Style:** 10px (desktop), 16px (phone cards).
- **Background:** `surface`; headers and footers `surface-raised`.
- **Shadow Strategy:** card rest shadow; see Elevation.
- **Border:** none on light; `dark-hairline` in dark themes.

### Page Header (dashboard)
- **Header** (`.dash-page-header`): a visible 1.75rem/600 "Dashboard" title (1.5rem on phones), a 0.9rem muted role subtitle (`.dash-page-sub`: `--app-muted` mixed 85% with `--app-text`, 5.33:1 light, 10.7:1 AMOLED, 9.04:1 graphite; plain muted was 4.41:1 on the ground) with the Manila date ("Your work, Sunday, October 11"), and on the right one primary button for the role (Create TSR, Open approvals or Open analytics, Open calendar). Customize and Reset are quiet outline buttons, desktop only. No clock badge.
- **Also used by Travel Request** (`templates/travel_request.html`): links `app-dashboard.css` for `.dash-page-header` / `.dash-page-h1` / `.dash-page-sub` / `.dash-page-actions` (outline header buttons, status as a `travel-status-chip`), so a header change reaches that page too.
- **Also used by Cash Advance** (`templates/cash_advance.html`): the same Page Header (status as the `cash-status-pill` beside the title, outline New Request) plus five `.dash-stat` cards (Rejected toned red only above zero) and `.logbook-ref` CA numbers.
- **Request pages** (Travel Request, Cash Advance, Reimbursement, Leave Request): the page wrapper also carries `.request-page` (`app-dashboard.css`): one centred 1220px column, and the header button stacked under the subtitle on the left whatever the subtitle's length. Each shows its status chip beside the title; the header button is New Request (Reimbursement: New Period, which reopens the date range). New request pages use the same.

### Stat Cards (dashboard, shadcn model)
- **Card** (`.dash-stat`): `surface`, hairline border, 12px radius, 1.25rem padding (1rem on phones). Top row: 0.82rem/500 muted label left, an optional pill badge right (`.dash-stat-badge`, 0.72rem, hairline border). Then a 2rem/600 tabular number (1.6rem on phones), a 0.86rem/500 sentence and a 0.76rem muted helper line. Four across at 1200px and up, two across below.
- **Tone:** the number (or a count inside the helper) takes the alert or warn pair only above zero, as in KPI Tiles; never the accent. A badge that reports an improvement is green text (`#15803d`, dark `#4ade80`).
- **Class names** avoid `-stat-value`, `-stat-label` and `-kpi-value`, which `app-dark-pages.css` forces to plain text in dark mode.
- **Filter cards** (scheduler, `.scheduler-metric.dash-stat`): a Stat Card that is the queue's filter button, with no badge (no recorded history). Six across at 1200px and up, three from 768px, two on phones. The active filter gets a light ink wash, the 2px accent underline and `aria-pressed`. A count that is not a filter (Next 7 days) is the same card as a plain `span`.
- **Card headings** on the dashboard: `.dash-card-title` (1rem/600) with a muted `.dash-card-sub`, no icon; a region inside a section uses `.dash-panel` with a `.dash-panel-head`.

### Area Chart (dashboard)
- **Chart** (`.dash-chart`, drawn by `renderDashboardAreaChart`): one card, title plus a muted range subtitle, a segmented 3 months / 30 days / 7 days switch (`.dash-segment`, 10px radius, pressed segment a 9% ink wash; 44px tall on phones). A 2px accent line with a 12% accent fill (in dark themes the accent mixed 70% with white), three hairline gridlines with 0.72rem muted labels, and three to five date labels. Three months is drawn as weekly totals; 30 and 7 days are daily.
- **Reading:** a readout line under the chart (`role="status"`) shows the range total, or the day or week under the pointer, tap or arrow keys, with a dashed cursor and a ringed dot. An empty range shows one sentence, never a flat line.
- **Motion:** draws once on load (line 0.9s exponential ease-out, then the fill fades in); off under `prefers-reduced-motion`.
- **Comparison line** (manager chart, visits scheduled): a 1.5px muted dashed line (4 3), no fill, no draw-in, on the same y-scale as the accent line. A key under the subtitle shows both line styles as text plus swatches; the readout names both values ("Week of Aug 4 · 6 scheduled · 2 completed") and the summary reads "N of M scheduled visits completed".

### Tabs and Detail Panel (dashboard work orders)
- **Tabs** (`.work-orders-tab`): pill tabs with their count (36px, 44px on phones), hairline border and muted text; the selected tab gets a 9% ink wash and `--app-text`. They scroll sideways on phones rather than wrap.
- **Detail panel** (`.work-order-panel`): a 22rem column right of the list at 992px and up; below that a full-screen sheet on `surface` with a sticky header and a 44px Close. It opens from a row, closes with Esc or Close, and returns focus to the row. One primary action at its foot.

### My Requests (`templates/accounting_center.html`)
- **Shared classes:** links `app-dashboard.css` and reuses the Page Header, the pill tabs, Stat Cards, `.dash-card` and `.dash-segment`; changes to those classes reach this page too. Only the list's own parts are page-local, on theme variables.
- **Layout:** header (title, one-line subtitle, Refresh as an outline button), request-type pill tabs with counts ("Needs your action" first), three stat cards (one compact row each on phones: label and caption left, number right), then one list card with title, subtitle and the status filter as a segmented control (`aria-pressed`; hidden on Needs your action).
- **Tone:** To fix (alert) and Your next step (warn) only on Needs your action and only above zero; never the accent.
- **Columns:** no Requester column (only the user's own records are listed). Needs your action has no Details column; heading rows (`.action-group-row`, "To fix · N") split the list by group, and its subtitle says "N need your action · M to confirm when received" because the tab badge leaves out the confirm group.
- **Downloads:** one `formLink()` helper adds an outline Form button (Package for reimbursements) where a form exists and the status allows it: travel request PDF approved or later, travel and cash advance liquidation Excel once submitted, leave PDF always, none for cash advances themselves.
- **Phone rows (≤768px):** each table row is a 16px-radius card. The record is the card title; secondary columns listed in the module's `phoneHidden` are hidden (`cell-phone-hidden`, set by `labelQueueCells()`); every other value has its muted 0.72rem label beside it (`data-label`). Action buttons share a row, text only, 44px tall. The page outranks `app-dashboard.css`'s phone rule that hides `.table-responsive table`.
- **Pills:** status pills and row notes keep fixed semantic pairs with dark-theme pairs, at least 4.5:1.
- **Dialogs:** plain headers with the default close button; colour only on the confirm button (green for Confirm Received and Mark Completed, accent for Travel Completed).

### P.O. Details (`templates/po_details.html`)
- Uses the Page Header ("P.O. Details", one-line subtitle, green Add P.O.) and five Stat Cards (`app-dashboard.css`; numbers show "–" with `aria-busy` until loaded). Table headers take `--app-primary` (raised surface in dark themes), like the PM pages. On phones the filters fold behind a 44px Filters button (`aria-expanded`, "Filters · N" when N are active).

### Approvals (`templates/approvals.html`)
- **Order:** the Page Header (`.dash-page-header` from `app-shell.css`: "Approvals", a status subtitle "N waiting on you · oldest X days", "N awaiting approval" for view-only users, outline Refresh), the notifications strip only while something is unread, then one panel: pill tabs with counts (Pending, Approved, Returned / Rejected; `role="tab"`, 44px on phones), filters, the card list, pagination under the list. No banner, KPI cards or module tiles; the Module filter replaces them. On phones only search shows beside a 44px Filters button (`aria-expanded`).
- **Card anatomy** (`approvalCardHtml`, every module): reference number in the logbook monospace with the requester under it and the type badge on the right; up to four label/value facts; then the footer: on Pending the waiting-time chip (`.approval-age-chip`, "Today" / "N days", slate `#334155` on `#f1f5f9`, past 30 days `#a1121f` on `#fde8ea`; dark `#e2e8f0`/`#334155` and `#fecdd3`/`#5c1a22`), on history the decision pill (Returned is red) with date, approver and remarks; one primary Review / View Details button bottom right. Type badges are soft pairs, 0.72rem/600: Travel Request accent soft, Reimbursement `#166534`/`#dcfce7`, Travel Liquidation `#5b21b6`/`#ede9fe`, Cash Advance `#9a3412`/`#ffedd5`, Cash Advance Liquidation `#92400e`/`#fef3c7`, Calibration `#075985`/`#e0f2fe`, Leave Request `#334155`/`#f1f5f9`, LPR `#9d174d`/`#fce7f3`.
- **Review window:** a dialog (`role="dialog"`, `aria-modal`) that takes focus on open, closes with Escape or Close and returns focus to the card. The decision bar stays in view at the bottom: a red "Package incomplete: … missing." line for liquidations not ready for review (Approve then asks "Approve with an incomplete package?"), the remarks field, an "Open next pending after deciding" checkbox (remembered per browser), and the actions.

### Reports (`templates/reports.html`)
- **Order:** the Page Header ("Reports", one-line subtitle, outline Refresh). Then TSR files for everyone (admins: Branch and search; engineers: Show My / All TSRs and search). Admins then get Missing TSRs as a closed `<details>` section whose summary shows the count in range (alert red above zero); opened, it holds the monitoring range, outline Export CSV, four stats and the list (owner, 2026-10-21: TSR files first, Missing TSRs collapsible only). Then Most-serviced products beside TSR emails sent.
- **TSR file cell:** the TSR number in the monitoring monospace (or the file's kind when it has none), one muted line "kind · PDF · size · Saved date", and Preview (outline) / Download (filled accent) beside it; the full generated filename is the hover title and part of each link's accessible name, and a truncated line on phone cards. A locked print copy shows "Admin download only".
- **Lists (follow-up 2026-10-21):** TSR files tools add Type (All / TSRs / Calibration certificates / Calibration reports) and Service from / to; the summary loads only after the TSR files list. Missing TSR rows carry the Approvals "N days" chip (slate `#334155`/`#f1f5f9`, red past 30 days `#a1121f`/`#fde8ea`; dark `#e2e8f0`/`#334155`, `#fecdd3`/`#5c1a22`) and "Open in Timeline" (`/timeline?date=`) for users who may open the Timeline. TSR emails sent is one line: Sent · By · Task · "N to · N CC" (addresses on hover, or a disclosure on phones). Most-serviced products is a plain list, top 5: name · client and the count; serial and last service on hover.
- **States:** stats and counts show "–" until loaded (`aria-busy`); the archive keeps a minimum height while loading; the alert above the lists appears only for errors. The Missing TSR count turns alert red (`#a1121f`, dark `#fecdd3`) only above zero.
- **Colour:** theme variables only; the alert pair is the page's one fixed colour.

### Analytics (`templates/analytics.html`)
- **Order:** the Page Header ("Analytics", a subtitle naming the range and branch, "Updated" time and outline Export), the filter card (From, To, branch, Apply and a `.dash-segment` of Since system start / This week / This month with `aria-pressed`; a hand-picked date clears it), pill tabs (Service activity, Purchase orders, Equipment; 44px and sideways scroll on phones). Service activity: one muted scope line, four Stat Cards (Total schedules, Overdue client work, Open client work, Completed), a chip row of open client work by status, the daily trend, a three-column row (Service mix, Top clients, Branch concentration; two columns below 1200px, one below 992px), then Engineer workload (top 8, "Show all N" with `aria-expanded`; Total, Field days, Active, Completed).
- **Comparison:** only Total schedules and the chart rows carry a previous-period figure, and only when the previous period starts on or after the system start (2026-05-18); otherwise the scope line says so and no arrow, previous bar or legend key is drawn. Arrows are ink-muted with sign and arrow, never red or green (volume has no good direction). Overdue client work takes the alert pair only above zero, with its 1–7 / 8–30 / over 30 day split in the helper line.
- **Colour:** theme variables only. Small muted text uses the `.dash-page-sub` mix (≥5.3:1 light); previous-period bars are muted mixed 85% into the frame (3.44:1 light), current bars the accent (mixed 70% with white in dark themes, 4.71:1 Graphite). Weights 500/600 only. Rows empty in both periods are not drawn; the hidden data tables keep them for print and screen readers.
- **Phone (≤768px):** the filter card folds into one "Range · Branch" row with a 44px Filters button (`aria-expanded`); the first number sits inside the first screen. Workload becomes 16px cards with four stats in two columns.

### KPI Tiles (manager dashboard)
- **Tile** (`.manager-kpi.dash-stat`): a Stat Card (see Stat Cards) that keeps the tile's link or filter button; number class `.manager-kpi-num` plus `.dash-stat-num`. Auto-fit grid of 12rem cards, 1rem gap; two columns on phones.
- **Tone:** the number takes the existing alert (overdue) or warn (TSR, waiting) colour, light and dark pairs; a tile at zero stays neutral (`.is-zero`). Never the accent.
- **Action:** a tile is a link (Approvals) or a filter button for the list it summarises; the active filter gets the 2px accent underline and `aria-pressed`, pressing it again clears it.
- **KPI trend:** the corner badge holds the arrow and the size of the change ("↑ 4", "Same"; `aria-hidden`), and the card's sentence says it in words ("Up 4 from last week"). No sparkline: the area chart is the picture. Ink-muted by default; red only when a lower-is-better count rose, green text when it fell. Without a recorded value from a week ago the sentence says "Trend from <date>"; never estimated. A ratio to a limit (PM done/due) gets a 6px accent meter as its helper line.
- **Age bars** (`.manager-age`): the smaller card beside the company Visits completed chart (two-thirds / one-third at 1200px and up, stacked below), four bar buttons (count above, ≤36px bar, label below) on a hairline baseline. Below the watchlist threshold the bar is slate; past it, one red deepens step by step. Pressing a bar filters the list like a tile.
- **Motion:** one load moment only. Tiles settle (opacity 0.35→1, 6px rise, staggered 60ms), numbers count up (700ms, exponential ease-out, with a timeout so a background tab still lands on the real value), and bars grow from the baseline. The "Updated" dot pulses three times after each refresh, never on a loop. All of it is off under `prefers-reduced-motion`.

### Inputs / Fields
- **Style:** Bootstrap fields on `surface` (dark: `--app-input`), `hairline` border.
- **Focus:** accent border + focus ring.
- **Disabled / Read-only:** `surface-raised` background, muted text, full opacity.

### Navigation
- **Brand:** the Shimadzu mark (cropped from the white logo image by `.shell-brand-mark`, never redrawn) heads the sidebar: 28px above the pin button in the rail, beside "Medical Service" on one line when pinned (it wraps to two lines below 240px, never hides). The phone top bar shows the 24px mark and the current section's name at 0.9rem (e.g. Inventory; pages outside a section show their own name), since the page's heading below names the page; the tab title reads "Page · Medical Service". Both come from the active sidebar link.
- **Order:** three groups, by what people come to do. MAIN: Dashboard, Approvals (approvers), My Requests, Calendar, Create TSR (approver-only accounts keep Calendar, view-only, but no Create TSR or WORK group). WORK: Forms (the request forms), Clients (Client List, Calibration Center), Inventory (Product Inventory, Genoray, Vieworks | their PM pages | Stock Inventory, split by thin dividers; stock-only accounts see Stock in MAIN). MANAGE for administrators, MORE for everyone else: Reports (Analytics, Reports), Office (Personnel, P.O. Details, Reimbursement Tracker), Admin (Activity Logs, Settings) or Settings alone. One name per item: the rail caption is the label (stock-only and HR-schedule accounts keep "Stock" and "Password"). A group that would show one link to someone shows that link directly, and opening a group in the pinned sidebar or phone menu closes the others except the one holding the current page. The group headings are announced to screen readers. Calendar has no arrow or flyout. Who sees what is decided by the server's access helpers, never by the template. A "?" (pinned header, account panel, phone account row) opens the Menu guide: this user's own sections, each page as a link with a one-line description, plus the slim menu's keys on desktop. The two modes are called the "full menu" and the "slim menu" everywhere.
- **Sidebar:** Logbook Slate body (kept dark, owner choice 2026-10-07), Midnight Slate 72px header holding only the brand and the pin control (« collapse, » open); the pinned footer shows the initials, name and role and a chevron, which open the account panel above it; rows are 44px with a 22px icon, label truncating with ellipsis, `sidebar-text` colour, weight 600 (sub-rows 500), and no divider between rows.
- **Icon rail (desktop default):** 72px, 52px captioned rows; each top-level icon carries a short caption below it (it is the label itself, e.g. Dashboard, My Requests, Forms, Clients, Inventory, Reports, Office, Admin; two-word labels wrap to two lines; the caption is decorative and the link keeps the name for screen readers; rows tighten to 48px on windows 720px tall or less), group labels become thin separators, count badges become 16px one-digit badges (9+) on the icon's corner, the footer shows initials. Hover, focus or tap a group icon for a flyout with the group name and its links; single links show a name label. The initials open the account panel (rail and pinned): name, role, then labelled 44px rows Theme ("Theme: <current mode>"), What's New, Menu guide, Log out. Unread What's New updates show as an 8px soft white dot (`--shell-focus-ring`) on the account initials on desktop and on the phone top-bar bell; the count is in their labels ("Account, N unread updates") and badges show 9+ at most. Opening What's New marks its updates read. Count badges and initials sit on `--shell-on-accent-bg` (the accent darkened) so their white text reaches 4.5:1. A soft fade at the menu's bottom edge shows when more is below, in every mode. Offline, an amber OFFLINE tag (0.72rem) sits centred on the sidebar header's brand rule, and the phone top bar grows a full-width strip "Offline · Create TSR still works", and screen readers hear that Create TSR still works offline. Amber in the shell means only offline; Log out is neutral. Flyouts use the sidebar surface with a soft offset shadow; Escape or a tap outside closes; the ☰ control pins or collapses.
- **Hover:** faint white wash (7%), text turns white.
- **Active:** white text, 16% accent wash, 3px left rail in `--sidebar-active-marker` (the accent mixed 55% with white, ≥3:1 on the dark sidebar) on the current page only; its open parent group just brightens. In the rail, the parent group icon carries the rail when its child page is active.
- **Focus-visible:** 2px accent outline inset.
- **Mobile:** sidebar becomes an off-canvas drawer (min(86vw, 320px)) that slides in from the right (the Menu button's side) below the top bar, with the account row (name, role) at its top and a labelled Log out row at its foot, away from the Close button (whose Menu button reads Close while open), above fixed page docks, over a dimmed tap-to-close backdrop; the drawer has no header of its own (the top bar carries the title, What's New and Menu, in the theme's sidebar colour); the drawer's account row holds Theme and the Menu guide as 44px icons; bottom-safe mobile nav.

### Appearance Picker (signature)
A grid of mode tiles (4 across, 2 on phones) and accent tiles with a 26px circular swatch; the selected tile gets an inset 2px accent ring.

## Do's and Don'ts

### Do:
- **Do** take every accent colour from `--app-primary` and its derived tokens.
- **Do** use the theme variables (`--app-surface`, `--app-text`, `--app-border`, …) so a page works in light, graphite and AMOLED.
- **Do** keep tappable controls ≥44px on phones and turn wide tables into stacked cards at ≤768px.
- **Do** keep document previews and print output white with black text.
- **Do** use the white Shimadzu logo image only on dark grounds; never retype the logotype.

### Don't:
- **Don't** hardcode an accent hex in a page template.
- **Don't** put white text on Logo Red `#ee3239` (4.1:1); use Deep Brand Red `#d9262e`.
- **Don't** re-theme schedule or status colours with the accent.
- **Don't** use `transition: all`; animate only the properties that change.
- **Don't** invent further Shimadzu brand rules until the official brand guide is in the repository.
