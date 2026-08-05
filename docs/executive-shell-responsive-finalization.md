# Executive Shell & Responsive Header Finalization

## Scope

Presentation only. Baseline `e338e94` (post PR #129).

No football logic, rankings, valuations, Trust, recommendation generation or
ordering, authentication, entitlements, Stripe, Supabase, caching, or business
rules.

## Inconsistencies discovered and resolved

### Command bar geometry
- Shell landmark padding collapsed to token `padding-block: 0` /
  `padding-inline: --space-md` so FGL tile and League / Alerts / You share one
  44px control band
- Command-strip buttons use identical padding, centered labels, and centered
  chevron SVGs with shared `gap: --space-xs`
- Desktop action rail uses a fixed `22.5rem` width so controls do not drift
  apart on wide canvases
- Narrow ≤430 padding uses `--space-sm` and `--letter-spacing-badge` (no
  hardcoded `0.04em`)
- Notification item gaps use `--space-2xs` instead of raw `2px`

### Responsive scaling
- Small (≤760): compact stacked shell + full-width action strip
- Tablet (768–1023): existing balanced gutters retained
- Desktop (1024 / 1280): fixed executive content max (`1180px`)
- Wide (1440): `1220px` content contract
- Ultrawide (1600+ / 1800): centered `1280px` ultra contract — content does not
  stretch to fill the viewport

### Valuation lens
- Removed detached floating affordance under the shell
- Moved into Dashboard page context (`dashboard_page_context`) as quiet
  metadata: `Lens · {name}`
- No page-specific floating chrome; hidden-on-mobile exception removed so the
  same page-context control is available across breakpoints

### Success / status messages
- Routine `Loaded saved league…` / preference notices use compact
  `dg-shell-ack` (same family as league-switch ack)
- Large Streamlit success banners reserved for errors / required actions
- `stAlert` residual radius/shadow overridden to executive tokens

### First viewport
- Shell bottom margin reduced `space-lg` → `space-md`
- Primary section headers keep `margin-top: 0` so Immediate Action / Next Move
  begin higher without crowding the command surface

## Rollback

Revert the merge commit on `main` (boundary: `e338e94`).
