# Canonical Command-Bar Layout Contract

| Field | Value |
| --- | --- |
| Baseline | `0c5ba3387e87004deaa6a859d9f7a97e69ef47e4` |
| Scope | Presentation-only executive command bar geometry |
| Explicit non-changes | Football, rankings, valuations, recommendations, Trust, auth, entitlements, Stripe, Supabase, Sleeper, caching, workflow continuity, business rules |

## Previous competing contracts

| Contract | Source | Conflict |
| --- | --- | --- |
| Shell base | `application_shell_styles.py` | `padding-block: 0`, League-only `height: 100%` stretch |
| Visual hierarchy | `visual_hierarchy_styles.py` | Re-padded `.dg-executive-shell` with `space-sm`; League-only border + stretch; `margin-block-end: space-xl` |
| Brand desktop hack | `brand_identity_styles.py` | Raw rem `padding: 0.7rem 0.9rem` at ≥1024 |
| Command strip | `executive_command_header_styles.py` | Fixed 44px triggers; late-injected |
| Legacy League neutralize | `app_styles.py` | `st-key-top_league_actions` leftover |
| Unify badge | `executive_design_unify_styles.py` | Founder badge `min-height: touch-target` inflated identity |

Asymmetric DOM: League was a bare keyed popover; Alerts/You used outer `*_control` containers.

## Root cause

Three height models fought inside one bordered band: identity padding restored by Visual Hierarchy, League stretch-to-parent, Alerts/You locked at 44px with deeper wrappers. Separators stacked (rail + League wrapper + per-button). No single command-cell owner.

## Final primitive

**Owner:** `modules/executive_command_header_styles.py` (`EXECUTIVE_COMMAND_HEADER_CSS`)

**Markup:** League, Alerts, and You each wrap in `st.container(key="executive_command_cell_*")` so Streamlit emits a shared `st-key-executive_command_cell_*` class. No extra markdown marker blocks (those inflate cell height).

Shared trigger geometry:

- `height` / `min-height: var(--touch-target-min)`
- `padding-block: 0`
- `padding-inline: var(--space-sm)` (≤430 keeps `space-sm`)
- `line-height: 1` (tight line-box so glyph optical center matches cell center)
- `display: grid` + `align-items: center` + label/chevron `inline-flex`
- chevron SVG `0.75rem`, `transform: none`
- one separator: per-button `border-inline-start` + desktop rail `border-inline-start` (no League-only border)

Identity shell (`.dg-executive-shell`): `padding-block: 0`, `min-height: var(--touch-target-min)`, `align-items: center` — same vertical rhythm as the command rail.

## CSS removed

- Visual Hierarchy League-only stretch/border/hover and shell vertical padding
- Application Shell League-only `height: 100%` / stretch rules
- Brand ≥1024 `.dg-executive-shell` rem padding/gap hack
- `app_styles.py` `st-key-top_league_actions` neutralize leftover
- Founder badge forced `min-height: touch-target` (now `min-height: 0`)
- League-specific padding overrides duplicated under mobile breakpoints

## Responsive rules

| Width | Behavior |
| --- | --- |
| ≤430 | Shared `padding-inline: space-sm` on all cells |
| ≤760 | Actions wrap under identity as a full-width equal three-column row; one `border-block-start` on the horizontal block |
| ≥761 | Identity \| rail grid: `minmax(0, 1fr) minmax(min(100%, 28rem), 1fr)` so the command rail shares available width instead of a fixed narrow strip |
| 1024–1920 | Same cell geometry; rail continues to grow with the shell; no desktop padding reintroduction |

Chevron contract: trigger buttons are `inline-flex`; the label wrapper may ellipsis (`min-width: 0`); the chevron is `flex: 0 0 auto` and must remain fully visible inside the button box. Do not “fix” clipped chevrons with per-control `translateY`, negative margins, or one-off widths.

Validated: 320, 390, 430, 768, 1024, 1280, 1440, 1600, 1920 — including long league context, `Alerts (12)`, and account labels longer than `You`.

## Remaining limitations

1. Streamlit still injects nested `stVerticalBlock` / `stElementContainer` / `stLayoutWrapper` nodes; CSS flattens them but cannot remove the nodes.
2. Popover chevrons are framework-owned (material `expand_more` / optional SVG); we only size/align them via the shared cell rule.
3. Extremely long trigger labels ellipsis inside the equal-width cell rather than grow cell height — intentional for the 44px contract; the chevron stays visible.
4. Delivery Validation merge depends on GitHub Actions; runner outages are outside this contract.

## Rollback

Revert the merge commit introducing this contract.

## Related

Responsive width composition and long-content fixtures are documented in
`docs/executive-header-responsive-geometry.md` (#185 family).
