# Notification Dropdown Restoration Contract (PR #153)

Presentation and interaction architecture only. Does **not** change football logic,
valuations, rankings, recommendation generation/scoring/ordering, Trust, lifecycle
semantics from #148–#151, authentication, entitlements, Stripe, Supabase schema,
or Sleeper behavior.

## Root cause — why Alerts became a giant modal

PR #150 correctly fixed broken mobile click targets by moving Inbox from
`st.popover` to `@st.dialog`. The failure mode before #150 was:

1. Decorative HTML cards looked tappable but were not interactive.
2. Real Streamlit CTAs sat **after** a batch HTML list, outside the scroll /
   interaction layer, so taps never reached `on_click`.

The dialog fix restored reliable deep links, but the surface became a
**full centered modal** with:

- oversized backdrop on desktop;
- duplicate hierarchy (`Inbox` dialog chrome + `FOUNDER BETA` kicker + `Inbox` title);
- a redundant **Close Inbox** button beside native dismiss;
- visual weight inappropriate for a lightweight notification menu.

## Final responsive notification-surface contract

### Interaction model

| Viewport | Surface | Behavior |
| --- | --- | --- |
| Desktop (≥768) | Anchored `st.popover` on Alerts cell | ~380–480px (24–28rem) width; right-biased under Alerts; content height with max ~60vh; internal scroll only when needed |
| Tablet | Same popover | Width capped to `min(92vw, 28rem)` |
| Phone (≤430) | Same popover, largest practical width | `calc(100vw - 2×safe-area)`; max-height ~72dvh; no centered modal backdrop |

- Click outside or click Alerts again closes (native popover dismiss).
- **No** redundant Close Inbox button.
- Header: single **Alerts** title + unread/status (`N unread` / `All caught up`).
- No FOUNDER BETA kicker and no second heading.
- Trigger chrome and panel title both say **Alerts** (legacy “Inbox” customer label removed).
- Product updates remain visually subordinate (`dg-notification-item--product`).
- Empty league activity is a single concise line (`No league activity yet.`).

### Interaction integrity (do not regress #150)

Every actionable notification row is immediately followed by its real
Streamlit control (`st.button` / fixture `st.link_button`) inside
`dg_notify_action_*` containers. Decorative HTML never carries the CTA.

Deep links preserved: Trade Hub, Waivers, Player Quick View, My Team,
League Overview, Live Draft — same handlers and inventory contracts from
#148–#151.

### Overlay layering

| Layer | Z-index | Surfaces |
| --- | ---: | --- |
| Fixed navigation | 1001000 | GM trigger |
| Destination sheet | 1001005 | GM “Where to go” |
| Command popovers | 1001010 | **Alerts dropdown**, Switch League, You |
| Modal / dialog | 1001020 | PQV, Trade Review (not Alerts) |

Opening Alerts CSS-hides the GM trigger while an Alerts `stPopoverBody` (or
harness panel) containing `.dg-notification-panel` is present. Only one
command-bar overlay should own pointer events at the top layer.

### Harness force-open

`?inbox=open` still sets `fixture_notifications_inbox_open` so Chromium can
assert CTAs without depending solely on popover portal timing. The harness panel
reuses `_render_inbox_panel` with distinct action keys — same CTA contract, not
a second information hierarchy.

## Automated validation

`scripts/validate_mobile_ui.py`:

- Opens Alerts via popover trigger; asserts **no** `stDialog` inbox.
- Captures Alerts open at **320 / 390 / 430 / 768 / 1024 / 1440 / 1920**.
- Asserts one Alerts title, no FOUNDER BETA kicker, no Close Inbox, viewport fit,
  desktop width band, first item visible, CTA ≥44px.
- Click-paths exercise real Trade / Waiver / Player (and League when present)
  controls, not mere href strings.

## Modules

- `modules/notification_center.py` — popover + `_render_inbox_panel`
- `modules/executive_command_header_styles.py` — anchored dropdown geometry
- `modules/mobile_interaction_overlay_styles.py` — z-index / phone geometry

## Protobuf note

Restoring always-mounted popover CTAs (required for #150 integrity without a
dialog) bumps cold protobuf ~2KB above the prior dialog-only-when-open baseline.
Budget gate: `MAX_PROTOBUF_BYTES = 520_000`.

## Next performance target

Return to the performance roadmap with **Trade Hub first-useful-result latency**
as the next optimization target (warm session already improved in #152).
