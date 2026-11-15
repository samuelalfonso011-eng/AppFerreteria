---
name: Ferretería El Constructor
description: Tienda de ferretería del Valle de Aburrá donde cada producto y cada acción se lee como una señal de obra.
colors:
  slate-ink: "#0F172A"
  slate-bar: "#1E293B"
  slate-hover: "#334155"
  amber: "#F59E0B"
  amber-hover: "#FBBF24"
  amber-strong: "#D97706"
  amber-soft: "#FEF3C7"
  accent-text: "#B45309"
  safety: "#EA580C"
  safety-text: "#C2410C"
  safety-soft: "#FFEDD5"
  sign-ok: "#166534"
  sign-warn: "#F59E0B"
  sign-stop: "#C2410C"
  sign-info: "#166534"
  sign-ok-soft: "#DCFCE7"
  background: "#F8FAFC"
  background-alt: "#F1F5F9"
  panel: "#FFFFFF"
  border: "#E2E8F0"
  border-strong: "#CBD5E1"
  text-main: "#0F172A"
  muted: "#475569"
  dark-background: "#0B1220"
  dark-background-alt: "#131D30"
  dark-panel: "#172236"
  dark-border: "#283750"
  dark-border-strong: "#3B4D6B"
  dark-text-main: "#F1F5F9"
  dark-muted: "#A9B6CA"
  dark-accent-text: "#FBBF24"
  dark-safety-text: "#FB923C"
typography:
  display:
    fontFamily: "Overpass, Atkinson Hyperlegible, system-ui, sans-serif"
    fontSize: "clamp(2.2rem, 5vw, 3rem)"
    fontWeight: 900
    lineHeight: 1
  headline:
    fontFamily: "Overpass, Atkinson Hyperlegible, system-ui, sans-serif"
    fontSize: "clamp(1.7rem, 4vw, 2.5rem)"
    fontWeight: 900
    lineHeight: 1.12
    letterSpacing: "0em"
  title:
    fontFamily: "Overpass, Atkinson Hyperlegible, system-ui, sans-serif"
    fontSize: "clamp(1.35rem, 2.6vw, 1.75rem)"
    fontWeight: 900
    lineHeight: 1.12
    letterSpacing: "0.01em"
  price:
    fontFamily: "Overpass, Atkinson Hyperlegible, system-ui, sans-serif"
    fontSize: "1.6rem"
    fontWeight: 900
    lineHeight: 1
    fontFeature: "tnum"
  body:
    fontFamily: "Atkinson Hyperlegible, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
  product-name:
    fontFamily: "Atkinson Hyperlegible, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "1rem"
    fontWeight: 700
    lineHeight: 1.3
  label-sign:
    fontFamily: "Overpass, Atkinson Hyperlegible, system-ui, sans-serif"
    fontSize: "0.78rem"
    fontWeight: 900
    lineHeight: 1.1
    letterSpacing: "0.1em"
  label-button:
    fontFamily: "Overpass, Atkinson Hyperlegible, system-ui, sans-serif"
    fontSize: "0.92rem"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "0.04em"
  label-ref:
    fontFamily: "Atkinson Hyperlegible, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
    letterSpacing: "0.05em"
    fontFeature: "tnum"
rounded:
  sm: "6px"
  md: "8px"
  lg: "10px"
  pill: "999px"
spacing:
  gutter: "clamp(16px, 4vw, 40px)"
  page-max: "1360px"
  grid-gap: "16px"
  grid-gap-mobile: "10px"
  card-pad: "10px 12px 12px"
  shelf-gap: "48px"
  touch-min: "44px"
components:
  button-primary:
    backgroundColor: "{colors.amber}"
    textColor: "{colors.slate-ink}"
    typography: "{typography.label-button}"
    rounded: "{rounded.md}"
    padding: "0 18px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.amber-hover}"
    textColor: "{colors.slate-ink}"
  button-secondary:
    backgroundColor: "{colors.slate-bar}"
    textColor: "{colors.panel}"
    typography: "{typography.label-button}"
    rounded: "{rounded.md}"
    padding: "0 18px"
    height: "44px"
  button-secondary-hover:
    backgroundColor: "{colors.slate-hover}"
    textColor: "{colors.panel}"
  button-outline:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.text-main}"
    typography: "{typography.label-button}"
    rounded: "{rounded.md}"
    padding: "0 18px"
    height: "44px"
  button-danger:
    backgroundColor: "{colors.sign-stop}"
    textColor: "{colors.panel}"
    typography: "{typography.label-button}"
    rounded: "{rounded.md}"
    padding: "0 18px"
    height: "44px"
  cart-button:
    backgroundColor: "{colors.amber}"
    textColor: "{colors.slate-ink}"
    rounded: "{rounded.md}"
    padding: "0 14px"
    height: "44px"
  sign-band-ok:
    backgroundColor: "{colors.sign-ok}"
    textColor: "{colors.panel}"
    typography: "{typography.label-sign}"
    padding: "5px 10px"
    height: "30px"
  sign-band-warn:
    backgroundColor: "{colors.sign-warn}"
    textColor: "{colors.slate-ink}"
    typography: "{typography.label-sign}"
    padding: "5px 10px"
    height: "30px"
  sign-band-stop:
    backgroundColor: "{colors.sign-stop}"
    textColor: "{colors.panel}"
    typography: "{typography.label-sign}"
    padding: "5px 10px"
    height: "30px"
  topbar:
    backgroundColor: "{colors.slate-bar}"
    textColor: "{colors.border}"
    padding: "10px clamp(16px, 4vw, 40px)"
  search-input:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.slate-ink}"
    rounded: "{rounded.md}"
    padding: "0 56px 0 16px"
    height: "48px"
  cat-chip:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.text-main}"
    rounded: "{rounded.md}"
    padding: "0 14px"
    height: "44px"
  cat-chip-active:
    backgroundColor: "{colors.slate-bar}"
    textColor: "{colors.panel}"
  product-card:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.text-main}"
    rounded: "{rounded.lg}"
    padding: "10px 12px 12px"
  input-field:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.text-main}"
    rounded: "{rounded.md}"
    padding: "0 12px"
    height: "44px"
---

# Design System: Ferretería El Constructor

## Overview

**Creative North Star: "Señal de obra"**

The state of every product and every action reads like a construction-site sign (after NTC 1461): a header band carrying one uppercase word, legible at a distance and in full sun. The world is built for the contractor holding a phone on site, with gloves on and the sun on the screen, so information that decides a purchase (availability, REF, price, unit) sits at fixed positions on every card and never has to be hunted for.

The surface is a pale working floor (`background`) with slate structure: a slate bar on top, a near-black slate footer, white panels framed by a 1px rule. Colour is spent on meaning, not decoration. Three sign colours say DISPONIBLE, POCAS UNIDADES and AGOTADO; amber, in addition, marks the one path the visitor is on (add to cart, cart, quote). Hierarchy comes from scale: prices set at sign size in Overpass, reading text in Atkinson Hyperlegible. Density is honest: a 2-column grid on phones, 4 to 5 columns on desktop, and a list view for people who already know what they want.

The world explicitly rejects the white store of soft rounded cards with a promotional banner, and the earlier "slate wall with lettering" of v1.3.

Scope of what is built: the public store (top bar, home, catalog, product detail, toasts, footer) is redesigned in this world. Cart, checkout, auth, account, legal pages and the admin panel inherit the tokens only and have not been redesigned yet; new work on them should adopt the components below rather than their current inline styles.

**Key Characteristics:**
- One shared signature, the sign band, used by product cards, the detail sign, toasts, alerts and empty states.
- Amber only on the active path; everything else is slate, white or semantic sign colour.
- Overpass for bands, headings, prices and figures; Atkinson Hyperlegible for reading.
- 8 to 10px corners, 1px rules, no decorative diffuse shadows.
- 44px minimum touch target everywhere; 48px search; 52px detail add-to-cart.
- One motion moment: the toast entrance and its band wipe.

## Colors

A cool slate-and-paper base with three sign colours and one amber path colour; every saturated pixel carries a meaning.

### Primary
- **Signal Amber** (`amber`): the active path only. Primary buttons, the cart button in the top bar, the detail-page add-to-cart, the "Solicitar cotización" CTA, the focus ring outline, the page progress bar and text selection. Text on amber is always `slate-ink`. Hover lightens to `amber-hover`; `amber-strong` is the caret colour.
- **Burnt Amber Text** (`accent-text`): amber-family text on light surfaces where amber itself would fail contrast (shelf links "Ir al catálogo", filter counts). In dark mode it becomes `dark-accent-text`.

### Secondary
- **Slate Bar** (`slate-bar`): top bar, active category chip, active view-switch button, secondary buttons (including the card add-to-cart). Hover steps to `slate-hover`.
- **Slate Ink** (`slate-ink`): body text, text on amber, the cart count badge, the footer background and the 3px rule that heads each shelf.

### Tertiary (sign colours, semantic only)
- **Signal Green** (`sign-ok`, also `sign-info`): DISPONIBLE and INFORMACIÓN bands, success toasts, the delivery-strip truck icon. White text.
- **Caution Amber** (`sign-warn`): POCAS UNIDADES / PRECAUCIÓN bands and warning toasts. Ink text, never white.
- **Stop Orange** (`sign-stop` / `safety-text`): AGOTADO / ERROR bands, danger buttons, error toasts and the out-of-stock notice text. White text.
- **Safety Orange** (`safety`): the owner's binding brand orange. Kept as a token; not used under text, because white on it measures about 3.6:1.
- Soft tints (`sign-ok-soft`, `amber-soft`, `safety-soft`) back flash alerts only, with dark text.

### Neutral
- **Site Paper** (`background`) page floor; **Site Paper Alt** (`background-alt`) image wells, specs blocks, empty-state icon tiles.
- **Panel White** (`panel`) cards, rails, filter panel, toasts.
- **Hairline** (`border`) quiet dividers; **Frame Rule** (`border-strong`) card, panel and input frames.
- **Muted Slate** (`muted`) REF codes, units, secondary copy.
- Dark theme swaps these for `dark-background`, `dark-background-alt`, `dark-panel`, `dark-border`, `dark-border-strong`, `dark-text-main`, `dark-muted`; the bar becomes `slate-ink`, the footer `#060B16`. Sign colours do not change between themes. In dark mode secondary buttons and active chips invert to light slate (`#E2E8F0`) with ink text.

### Named Rules
**The Active Path Rule.** Amber marks only where the visitor is going: primary action, cart button, detail add-to-cart, quote CTA. Card add buttons are slate secondary. If two amber buttons compete on one screen, one is wrong.

**The Sign Means Something Rule.** Green, caution amber and stop orange appear only as state: DISPONIBLE / INFORMACIÓN, POCAS UNIDADES / PRECAUCIÓN, AGOTADO / ERROR. A band never decorates a section and never acts as an eyebrow above a heading.

**The Legible Orange Rule.** Any band or button that carries text in the stop state uses `sign-stop` (#C2410C) with white text, not `safety` (#EA580C), because white on #EA580C is about 3.6:1 and fails AA.

## Typography

**Display Font:** Overpass 600/800/900 (with Atkinson Hyperlegible, system-ui), self-hosted woff2
**Body Font:** Atkinson Hyperlegible 400/400 italic/700 (with system-ui, -apple-system, Segoe UI), self-hosted woff2

**Character:** Overpass is road-sign lettering: heavy, upright, uppercase-friendly, made to be read at speed. Atkinson Hyperlegible was drawn for low-vision legibility, which is what reading in direct sun needs.

### Hierarchy
- **Display** (900, clamp 2.2–3rem, 1): the price on the product detail sign. Prices are set at sign size because price decides the purchase.
- **Headline** (900, clamp 1.7–2.5rem, 1.12): catalog H1 (uppercase), detail title (clamp 1.6–2.5rem), page heads (clamp 1.75–2.75rem).
- **Title** (900, clamp 1.35–1.75rem, uppercase, 0.01em): shelf headings ("PRODUCTOS DESTACADOS") under a 3px ink rule.
- **Price** (900, 1.6rem, 1.35rem at ≤640px, tabular): card price, always above its unit line "precio por unidad".
- **Body** (400, 1rem, 1.55): reading text; descriptions capped at 60–70ch.
- **Product name** (700 Atkinson, 1rem, 1.3): two-line clamp with a fixed 2.6em minimum so prices align across a row.
- **Label: sign** (Overpass 900, 0.78rem, 0.1em, uppercase): band words. Band meta (counts) at 800, 0.06em, tabular.
- **Label: button** (Overpass 800, 0.92rem, 0.04em, uppercase): all buttons and category chips.
- **Label: REF** (0.75rem, 0.05em, uppercase, tabular, muted): the REF code, the one product code shown along the whole journey.

### Named Rules
**The Two Voices Rule.** Overpass speaks in signs, headings, prices, counts and buttons; Atkinson speaks in sentences and product names. Never set paragraphs in Overpass.

**The Tabular Figures Rule.** Prices, stock counts, cart badge, REF and table figures use tabular numerals so columns of numbers do not jitter.

## Layout

Pages sit in a centred container (`page-max`, side padding `gutter`). The top bar is sticky: brand left, search, nav, then theme toggle, language switch and the amber cart button. At ≤1180px the search drops to its own full-width row and navigation moves into a left drawer (min(320px, 86vw), 52px items). Under the bar on the home page come a 44px delivery notice strip and a horizontally scrolling category rail with scroll snap (one axis at a time on mobile).

The product grid auto-fills columns of at least 228px with a 16px gap (4–5 columns on desktop) and is a fixed 2-column grid with a 10px gap at ≤640px; it falls to 1 column under 360px. Shelves are separated by 48px. Card images keep a fixed 4:3 well so that REF, name, price and button land on a common baseline across each row.

List view (`is-list`) is one column with a 10px gap: band across the top, a 112px square image (84px on mobile), and body areas ref / name / price / add; at ≥861px the price and add button sit in their own columns to the right.

The catalog uses a 260px sticky filter panel beside the grid; at ≤900px it stacks and the filter becomes a collapsible `<details>` that JS opens automatically at ≥861px. The detail page is two equal columns (image, info) and stacks at ≤900px. Toasts sit top-right under the bar on desktop and move to the bottom (above the safe area) at ≤900px.

**The Shared Baseline Rule.** Every card in a row puts its price on the same line: fixed image ratio, fixed two-line name height, price row pushed to the bottom.

## Elevation & Depth

Flat by default. Depth comes from the 1px frame rule and the contrast between page paper and white panels, not from shadows. Shadows appear only as response or as a floating layer.

### Shadow Vocabulary
- **Hover lift** (`box-shadow: 0 4px 12px -2px rgba(15, 23, 42, 0.14)`): product card hover, together with the border darkening to ink; disabled on touch devices.
- **Floating layer** (`box-shadow: 0 12px 28px -6px rgba(15, 23, 42, 0.24)`): toasts only.
- **Focus** (`outline: 3px solid amber; outline-offset: 2px; box-shadow: 0 0 0 5px slate-ink`): every focus-visible element, a two-tone ring that reads on both light and dark ground.

### Named Rules
**The Rule-Not-Shadow Rule.** Panels are framed by a 1px `border-strong` line and sit flat. A shadow at rest is a defect.

## Shapes

Corners are gently squared: 6px (`sm`) for inner wells, small controls and inline bands; 8px (`md`) for buttons, chips, inputs, search; 10px (`lg`) for cards, panels, filter panel, toasts, empty states and the detail sign. Full pills (`pill`) only for the cart count badge. A sign band inside a framed container is clipped by the container's radius (overflow hidden) and has square corners itself; a free-standing inline band takes the 6px corner. Borders are 1px; the only heavy line is the 3px ink rule that heads each shelf.

## Components

### Sign band (signature)
The world's one distinctive device: a full-width strip at the top of its container, one uppercase word on the left and, where relevant, a tabular count on the right.
- **States:** state is computed from stock: `stock <= 0` → stop (AGOTADO); `stock <= min_stock_alert` → warn (POCAS UNIDADES · QUEDAN N); otherwise ok (DISPONIBLE · N UND).
- **Size:** 30px minimum on cards; 34px on empty states and panels; 36px on the detail sign and toasts.
- **Narrow-card adaptation:** in the 2-column grid at ≤640px the caution band shows only "QUEDAN N"; at about 160px of card width "POCAS UNIDADES" would wrap and break the shared band height, so the colour carries the caution. The detail page and list view keep the full label. At ≤640px bands are 0.7rem, 0.07em, no wrapping.
- **Used by:** product cards, detail sign, toasts (LISTO / PRECAUCIÓN / ERROR / AVISO), empty states.

### Buttons
- **Shape:** gently squared (8px), 44px minimum height, Overpass 800 uppercase.
- **Primary:** amber with ink text; the active path only.
- **Secondary:** slate with white text (light slate with ink text in dark mode); card add-to-cart, "Ver mis pedidos", "Regístrate".
- **Outline:** white panel, 1px frame rule, darkens to ink on hover; secondary choices next to a primary and "Ver detalle" on sold-out cards.
- **Danger:** stop orange, hover `#9A3412`.
- **States:** colour transitions 0.15s; press nudges down 1px; disabled at 55% opacity; loading hides the label behind an 18px spinner with an amber arc.
- **Cart button:** amber, Overpass 900 uppercase, with an ink pill count that bumps (scale 1.3) when an item is added; the label hides at ≤640px leaving icon and count.

### Chips (category rail)
- **Style:** white panel, 1px frame rule, 44px high, Overpass 800 uppercase, with a muted tabular count.
- **State:** active is solid slate with white text (inverted in dark mode); hover darkens the frame to ink.

### Cards / Containers
- **Product card:** white panel, 1px frame rule, 10px corners, sign band on top, 4:3 image well in `background-alt` (contain-fit, 10px inset), REF line, two-line name, price, unit, full-width slate add button. Sold-out cards dim and desaturate the image and swap the add button for an outline "Ver detalle".
- **Detail sign:** the same anatomy at detail scale: 36px band, display-size price, unit, quantity field (52px) beside a 52px amber add button; sold-out shows a stop-orange notice and an outline quote button.
- **Quote panel:** white framed panel with headline, muted copy and primary + outline actions.
- **Empty state:** framed panel with a full-width band on top, headline, muted copy and an action.
- **Toast:** framed panel with floating shadow, a 36px band with icon, word and close button, then the message.

### Inputs / Fields
- **Search:** 48px, white with ink text in both themes, 2px transparent border that turns amber on focus, an inset 44px slate search button.
- **Fields:** 44px, 1px frame rule, 8px corners, white panel. Inputs go to 16px font at ≤900px to prevent zoom.
- **Focus:** the global amber-and-ink ring.

### Navigation
- **Top bar:** slate, sticky, 1px darker bottom rule. Nav items are 44px, Atkinson 700, light slate text, hover white on an 8% white wash. Language switch: segmented, active segment white with ink text.
- **Mobile:** drawer from the left in slate, items 52px Overpass 800 uppercase, overlay at 65% slate-ink; account actions move into the drawer.
- **View switch:** segmented grid/list control, active segment slate with white text.
- **Footer:** slate-ink, uppercase white column heads, light slate links at 40px minimum height.

### Motion
The only motion moment is the toast: it enters with a 0.32s fade-and-drop (`cubic-bezier(0.16, 1, 0.3, 1)`) and its band wipes in from left to right with a 0.42s clip-path reveal, 0.05s delayed. Leaving fades and lifts in 0.2s. Everything else is state feedback (colour transitions, the 1px press, the badge bump). `prefers-reduced-motion` collapses all animation and transition durations.

## Do's and Don'ts

### Do:
- **Do** put a sign band at the top of every product card, detail sign, toast and empty state, with the state computed from stock (stop at 0, warn at or below the minimum alert, ok otherwise).
- **Do** keep amber for the active path: primary action, cart button, detail add-to-cart, quote CTA.
- **Do** use `sign-stop` (#C2410C) under white text for AGOTADO / ERROR.
- **Do** set ink text, not white, on caution amber.
- **Do** keep REF, name, price and unit at fixed positions so prices align across a row.
- **Do** give every interactive element a 44px minimum target and the amber-and-ink focus ring.
- **Do** show the REF code as the single product code throughout the journey.

### Don't:
- **Don't** use a sign band as decoration, a section label or an eyebrow above a heading.
- **Don't** put white text on `safety` (#EA580C); it is about 3.6:1.
- **Don't** make card add buttons amber; they are slate secondary.
- **Don't** add resting shadows to panels or cards; frame them with the 1px rule.
- **Don't** add motion beyond the toast entrance and band wipe without a reason tied to state.
- **Don't** introduce stock photography or invented product imagery; the category pictograms in `app/static/img/temp/` are interim until the owner supplies real product photos.
