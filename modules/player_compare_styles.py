"""Token-backed presentation for the head-to-head Player Compare surface.

Route-owned CSS (see tests/test_app_css_architecture.py) — injected alongside
PLAYER_QUICK_VIEW_CSS wherever Compare renders, since Compare is reached from
and shares the Player Quick View dialog family. No page-specific colors: every
value below is an existing modules/design_tokens.py token.
"""

PLAYER_COMPARE_CSS = """
.pqv-compare-shell{display:grid;gap:var(--space-md);max-width:44rem;min-width:0;width:100%}
/* Side-by-side identity header: the two cards and the VS divider are
   forced to stay on one row (the generic Streamlit column-stacking
   breakpoint otherwise collapses them to stacked rows below ~700px of
   flow width, same bug class as the pqv_actions_/pqv_detail_nav_rail
   scopes above already work around) so the header reads left/right in
   the same orientation as every comparison row beneath it. Each card
   only gets ~45% of the dialog's width here (vs. roster-list contexts
   that give this same card its full page width), so the roster-core
   portrait token is redefined smaller just in this scope -- at the
   unscoped 5.5rem size the avatar alone ate most of a half-width card,
   leaving no room for the name/value content and forcing single-letter
   line wraps. */
div[class*="st-key-pqv_compare_identity"]{--size-roster-core-portrait:3.25rem}
div[class*="st-key-pqv_compare_identity"] .dg-football-asset.compact-player-row{grid-template-columns:var(--size-roster-core-portrait) minmax(0, 1fr)}
div[class*="st-key-pqv_compare_identity"] .dg-football-asset__value{grid-column:2;text-align:left}
div[class*="st-key-pqv_compare_identity"] [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important}
div[class*="st-key-pqv_compare_identity"] [data-testid="stColumn"]{min-width:0!important}

.pqv-compare-vs{align-items:center;color:var(--color-text-muted);display:flex;font-size:var(--font-size-badge);font-weight:700;justify-content:center;letter-spacing:var(--letter-spacing-badge);padding-top:var(--space-xl)}
.pqv-compare-rows{display:grid;gap:0}
.pqv-compare-row{align-items:center;border-bottom:var(--border-width-default) solid var(--color-border);display:grid;gap:var(--space-xs);grid-template-columns:1fr 6.5rem 1fr;padding-block:var(--space-xs)}
.pqv-compare-row:last-child{border-bottom:none}
.pqv-compare-label{color:var(--color-text-secondary);flex:1;font-size:var(--font-size-badge);font-weight:700;letter-spacing:var(--letter-spacing-badge);padding-inline:var(--space-xs);text-align:center;text-transform:uppercase}
.pqv-compare-cell{display:flex;justify-content:center;min-width:0}
.pqv-compare-pill{border:var(--border-width-default) solid transparent;border-radius:var(--radius-sm);color:var(--color-text-primary);font-size:var(--font-size-body);font-weight:700;padding:var(--space-2xs) var(--space-sm)}
.pqv-compare-pill-win{background:var(--color-success-soft);border-color:var(--color-success);color:var(--color-success)}
.pqv-compare-win-badge{font-weight:700;margin-right:var(--space-2xs)}
.pqv-compare-pill-text{font-size:var(--font-size-caption);font-weight:600;padding-block:var(--space-2xs)}
.pqv-compare-narrative{display:grid;gap:var(--space-md);grid-template-columns:1fr 1fr}
.pqv-compare-narrative-col{min-width:0}
.pqv-compare-narrative-name{color:var(--color-text-muted);font-size:var(--font-size-badge);font-weight:700;letter-spacing:var(--letter-spacing-badge);margin-bottom:var(--space-2xs);text-transform:uppercase}
.pqv-compare-narrative-text{color:var(--color-text-secondary);font-size:var(--font-size-caption);line-height:var(--line-height-body);margin:0}
div[class*="st-key-pqv_compare_reset_"] button{color:var(--color-accent)!important}
"""
