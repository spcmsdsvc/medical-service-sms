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
    fontFamily: "sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  title:
    fontFamily: "sans-serif"
    fontSize: "1.05rem"
    fontWeight: 700
  label:
    fontFamily: "sans-serif"
    fontSize: "0.78rem"
    fontWeight: 600
  micro:
    fontFamily: "sans-serif"
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
  pill: "999px"
spacing:
  touch: "44px"
  mobile-gutter: "14px"
  sidebar-row: "46px"
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
- **Logo Red** (`brand-red-logo`): measured from the logo; used for the thin rule on sign-in pages, never behind text.
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

**The Semantic Status Rule.** Schedule and status colours stay semantic and are not re-themed by the accent.

## Typography

**Body Font:** generic `sans-serif` (set on `body` in `app-shell.css`; renders as the platform default)
**Sign-in Font:** Fira Sans, self-hosted (with Segoe UI, system-ui)
**Document Font:** Cambria (with Times New Roman) for calibration reports and certificates

**Character:** Plain and utilitarian in the app; a single humanist sans on the branded sign-in pages; a serif only where it mirrors the official printed form.

### Hierarchy
- **Title** (700, ~1.05rem): card, panel and section titles; Bootstrap headings for page titles.
- **Body** (400, 1rem, 1.5): forms, tables, prose.
- **Label** (600, ~0.78–0.86rem): field labels, table meta, nav text, chips.
- **Micro** (700, ~0.66–0.72rem): uppercase sidebar group labels, badges, dense table annotations.

### Named Rules
**The Small-Text Contrast Rule.** Anything under ~0.8rem must still meet 4.5:1 — the sidebar dim text was raised to `#a8b6c6` for exactly this reason.

## Layout

A fixed left sidebar (240px default, user-resizable 200–360px in 20px steps, collapsible to 0) beside a fluid main area using Bootstrap's grid and containers. Rows in the sidebar are 46px (sub-rows 38px). Density is high on desktop: tables carry most data, with frozen columns and a horizontal-scroll hint that appears only when the table actually overflows.

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

Gently rounded, never sharp and never bubbly. Controls and small buttons use 6px; cards 10–12px; phone cards 16px; status chips and swatches are full pills or circles. Cards are borderless on light (shadow only); in dark modes they gain a `dark-hairline` border. The active sidebar item is marked by a 3px accent rail on the left edge.

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
- **Status filter chips:** a row of pill buttons above a table (Product Inventory): status icon, label and a tabular count pill; the pressed chip uses the accent soft fill and border. Counts ignore the status filter itself. On phones the row scrolls sideways and chips are 44px tall.
- **Inventory status pills:** each warranty/contract status has one label, one tone and one icon, defined once (`PRODUCT_STATUS_META` in `templates/products.html`) and reused by the table, phone cards, chips, history modal and the "What do the statuses mean?" legend. Tones: Under Warranty green (shield), Under Contract cyan (signed file), Expired - Under Contract amber (file with alert), Expired - No Contract red (x-circle), No Expiry Set gray (calendar-x). Status meaning never relies on colour alone.

### Cards / Containers
- **Corner Style:** 10px (desktop), 16px (phone cards).
- **Background:** `surface`; headers and footers `surface-raised`.
- **Shadow Strategy:** card rest shadow; see Elevation.
- **Border:** none on light; `dark-hairline` in dark themes.

### Inputs / Fields
- **Style:** Bootstrap fields on `surface` (dark: `--app-input`), `hairline` border.
- **Focus:** accent border + focus ring.
- **Disabled / Read-only:** `surface-raised` background, muted text, full opacity.

### Navigation
- **Sidebar:** Logbook Slate body, Midnight Slate 72px header with the appearance button; rows have a 22px icon, label truncating with ellipsis, `sidebar-text` colour.
- **Hover:** faint white wash (7%), text turns white.
- **Active:** white text, 16% accent wash, 3px accent left rail.
- **Focus-visible:** 2px accent outline inset.
- **Mobile:** sidebar becomes an off-canvas drawer; bottom-safe mobile nav.

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
