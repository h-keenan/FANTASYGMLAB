# Mobile Interaction & Overlay Contract

Presentation and interaction architecture only. Does **not** change football logic,
valuations, rankings, recommendation generation/scoring/ordering, Trust, freshness
rules from #149, authentication, entitlements, Stripe, Supabase schema, or Sleeper
semantics.

## Root cause — unclickable Alerts / Inbox items

1. **Decorative HTML looked tappable but was not interactive**, and **`st.popover` trapped CTAs** — inbox cards were HTML-only while Streamlit buttons sat outside the scroll/interaction layer. On mobile, popover dismissals and z-index conflicts prevented reliable `on_click` delivery.

### Fix (PR #150)

- Move Alerts inbox from **`st.popover` to `st.dialog`** for reliable touch delivery.
- Interleave each inbox card with its wired `st.button` inside the dialog.
- Compress inbox copy via `compact_inbox_presentation()` using shortest canonical fields.

## Overlay layering

| Layer | Z-index token | Surfaces |
| --- | --- | --- |
| Page content | — | Dashboard, routes |
| Fixed navigation | `--dg-overlay-z-nav` (1001000) | GM trigger |
| Destination sheet | `--dg-overlay-z-sheet` (1001005) | GM “Where to go” panel |
| Command popovers | `--dg-overlay-z-popover` (1001010) | Switch League, You |
| Modal / dialog | `--dg-overlay-z-modal` (1001020) | **Alerts Inbox**, Trade Review, PQV, metrics |

**Ownership rule:** Only one overlay owns pointer events at the top layer. Opening
Alerts/League/You hides the GM trigger. Opening GM sheet hides feedback chrome (existing
`ux_polish_styles`).

Module: `modules/mobile_interaction_overlay_styles.py` (loaded last in `APP_CSS`).

## Mobile Inbox geometry (≤430px)

- Width: `calc(100vw - 2 × max(space-sm, safe-area-inset))` — never beyond right edge.
- Max height: `min(72dvh, 100dvh - safe-area-top - 5rem)`.
- Header: title “Inbox” only; kicker + long explanatory note hidden on mobile.
- One scroll container: dialog body (no nested scroll trap).
- No horizontal overflow.

## Touch-target contract

- Minimum **44×44px** for inbox CTA buttons, GM trigger, GM sheet destinations, command
  rail popover triggers.
- Inbox buttons: full-width, `min-height: var(--touch-target-min)`.
- Validated in `scripts/validate_mobile_ui.py` via `_assert_tap_target()`.

## GM/Menu architecture

- Label: **`GM`** (horizontal, uppercase) — not vertical letter stacking.
- Removed redundant `.mobile-gm-orb-hint` “Menu” stack above the control.
- 44×44px fixed square using executive tokens; safe-area aware (`env(safe-area-inset-*)`).
- Opens existing `render_mobile_destination_sheet` — no second navigation system.
- Hidden while dialogs or command popovers are active.

## Safe-area handling

- GM trigger: `bottom: max(space-md, safe-area-inset-bottom)`,
  `left: max(space-md, safe-area-inset-left)`.
- Inbox dialog respects horizontal safe-area insets on ≤430px.
- Shell clearance unchanged from #138 (`--dg-mobile-shell-clearance`).

## Command-bar interaction matrix

| Control | Opens | Tap target | Closes / conflicts |
| --- | --- | --- | --- |
| Switch League | League list popover | Popover trigger + league rows | GM hidden while open |
| Alerts | **Inbox dialog** | Alerts trigger + per-item CTA buttons | GM hidden while open |
| You | Profile / feedback popover | Popover trigger + inner actions | GM hidden while open |
| GM | Destination sheet | GM button + sheet destinations | Hidden when popover/dialog open |

## Automated click-path coverage

`scripts/validate_mobile_ui.py` — `_capture_command_bar_interactions()` at **320 / 390 / 430**:

| Path | Assertion |
| --- | --- |
| Alerts → Open Trade Hub → | `data-fixture-notification-destination='trade_hub'` |
| Alerts → Open Waivers → | `destination='waivers'` |
| Alerts → Open Player → | `destination='player_quick_view'` |
| Switch League → Fixture Alt League | `data-fixture-league-choice` |
| You → Send feedback | expander opens |
| GM → Trade Hub | `data-fixture-gm-destination='trade_hub'` |

Screenshots at 320/390/430: `alerts-inbox-open-{width}.png`, `switch-league-open-{width}.png`,
`you-menu-open-{width}.png`, `dashboard-gm-closed-{width}.png`, `gm-menu-open-{width}.png`.

## Remaining framework limitations

- Streamlit cannot attach click handlers to arbitrary HTML; inbox CTAs must remain
  `st.button` widgets interleaved with card markup inside the dialog.
- Dialog and popover portal DOM varies by Streamlit version; z-index contract targets
  `stDialog`, `stPopoverBody`, and `stPopoverContent`.
- True iOS Safari device testing is not replaced by Chromium emulation, but click-path
  tests catch the regression class that screenshots miss.

## Explicit confirmation

No changes to football logic, valuations, rankings, recommendation generation,
scoring, ordering, Trust, canonical recommendation meaning, freshness rules (#149),
authentication, entitlements, Stripe, Supabase schema, Sleeper semantics, or business
rules.
