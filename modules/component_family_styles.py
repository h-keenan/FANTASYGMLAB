"""Canonical component-family contracts (token-backed, presentation only).

Owns shared geometry for equivalent roles. Feature modules may specialize
semantics (send/receive, selected, warning) but must not invent alternate
radius/surface languages for the same role.
"""

# Compact form — keep Founder Beta APP_CSS budget headroom.
COMPONENT_FAMILY_CSS = """
/* CTA tiers */
div[class*="st-key-dg_cta_primary_"] [data-testid="stButton"] button,div[class*="st-key-dg_cta_secondary_"] [data-testid="stButton"] button,div[class*="st-key-dg_cta_tertiary_"] [data-testid="stButton"] button,div[class*="st-key-dg_cta_destructive_"] [data-testid="stButton"] button{border-radius:var(--radius-control)!important;min-height:var(--touch-target-min)!important}
div[class*="st-key-dg_cta_primary_"] [data-testid="stButton"] button{background:var(--surface-interactive)!important;border:var(--border-width-default) solid var(--border-accent)!important;color:var(--text-primary)!important}
div[class*="st-key-dg_cta_secondary_"] [data-testid="stButton"] button{background:var(--surface-interactive)!important;border:var(--border-width-default) solid var(--border-standard)!important;color:var(--text-secondary)!important}
div[class*="st-key-dg_cta_tertiary_"] [data-testid="stButton"] button{background:transparent!important;border:0!important;border-block-end:var(--border-width-default) solid var(--border-standard)!important;color:var(--text-secondary)!important}
div[class*="st-key-dg_cta_destructive_"] [data-testid="stButton"] button{background:var(--color-danger-soft)!important;border:var(--border-width-default) solid var(--color-danger)!important;color:var(--text-primary)!important}
/* Cards */
.dg-ui-card,.dg-card-standard,.home-command-card,.summary-tile,.trade-summary-card,.explorer-pick-card{background:var(--surface-1);border:var(--border-width-default) solid var(--border-standard);border-radius:var(--radius-panel);box-shadow:var(--shadow-none)}
.dg-card-raised,.home-command-card-primary,.home-command-card-wide{background:var(--surface-raised);border-color:var(--border-strong)}
.dg-card-quiet,.dg-what-changed-quiet,.dg-daily-briefing-quiet,.dashboard-clear-state,.dg-gm-targets-quiet{background:var(--surface-1);border:var(--border-width-default) solid var(--border-subtle);border-radius:var(--radius-panel)}
/* Disclosure */
div[data-testid="stExpander"]{background:var(--surface-1)!important;border:var(--border-width-default) solid var(--border-standard)!important;border-radius:var(--radius-panel)!important;margin-block:0 var(--space-sm)!important;overflow:hidden;padding:0!important}
div[data-testid="stExpander"] summary,div[data-testid="stExpander"] [data-testid="stExpanderDetails"]{border-radius:var(--radius-none)!important}
div[data-testid="stExpander"] summary{align-items:center!important;background:var(--surface-1)!important;color:var(--text-primary)!important;font:var(--type-card-title)!important;gap:var(--space-sm)!important;min-height:var(--touch-target-min)!important;padding-inline:var(--space-md)!important}
div[data-testid="stExpander"] summary:hover{background:var(--surface-interactive)!important}
div[data-testid="stExpander"] summary:focus-visible{box-shadow:var(--focus-ring)!important;outline:none!important}
div[data-testid="stExpander"][open] summary,div[data-testid="stExpander"] details[open]>summary{background:var(--surface-2)!important;border-block-end:var(--border-width-default) solid var(--border-standard)}
div[data-testid="stExpander"] [data-testid="stExpanderDetails"]{max-height:none!important;overflow:visible!important;padding:var(--space-sm) var(--space-md) var(--space-md)!important}
/* Segmented / Deep Analysis */
[class*="dashboard_deep_analysis_nav"]{background:var(--surface-1);border:var(--border-width-default) solid var(--border-standard);border-radius:var(--radius-panel);overflow:hidden;padding:var(--space-xs)}
[class*="dashboard_deep_analysis_nav"] [data-testid="stButton"] button{background:var(--color-surface-raised)!important;border:var(--border-width-default) solid var(--border-standard)!important;border-radius:var(--radius-control)!important;color:var(--text-secondary)!important;font-size:var(--font-size-badge)!important;font-weight:var(--font-weight-button)!important;letter-spacing:var(--letter-spacing-badge);min-height:var(--touch-target-min)!important;text-transform:uppercase!important}
[class*="dashboard_deep_analysis_nav"] [data-testid="stButton"] button:focus-visible{box-shadow:var(--focus-ring)!important}
/* Filters / inputs — canonical FantasyGM Lab select family (control + menu). */
div[data-testid="stTextInput"] input,div[data-testid="stSelectbox"]>div,div[data-testid="stMultiSelect"]>div,div[data-testid="stSelectbox"] [data-baseweb="select"]>div,div[data-testid="stMultiSelect"] [data-baseweb="select"]>div,div[class*="st-key-player_asset_explorer_"] input,div[class*="st-key-player_asset_explorer_"] [data-baseweb="select"]>div{background:var(--surface-1)!important;border:var(--border-width-default) solid var(--border-standard)!important;border-radius:var(--radius-control)!important;box-shadow:var(--shadow-none)!important;color:var(--text-primary)!important;min-height:var(--touch-target-min)!important}
div[data-testid="stTextInput"] input:focus-visible,div[data-testid="stSelectbox"]>div:focus-within,div[data-testid="stMultiSelect"]>div:focus-within,div[data-testid="stSelectbox"] [data-baseweb="select"]>div:focus-within,div[data-testid="stMultiSelect"] [data-baseweb="select"]>div:focus-within{border-color:var(--border-accent)!important;box-shadow:var(--focus-ring)!important;outline:none!important}
div[data-testid="stSelectbox"] [data-baseweb="select"],div[data-testid="stMultiSelect"] [data-baseweb="select"]{width:100%}
div[data-testid="stSelectbox"] svg,div[data-testid="stMultiSelect"] svg{fill:var(--text-secondary)!important}
/* Open menu / listbox — constrained height, branded surface, compact rows */
ul[role="listbox"],div[data-baseweb="popover"] ul[role="listbox"],div[data-baseweb="menu"]{background:var(--surface-raised)!important;border:var(--border-width-default) solid var(--border-strong)!important;border-radius:var(--radius-panel)!important;box-shadow:var(--shadow-none)!important;max-height:min(42vh,18rem)!important;overflow-y:auto!important}
ul[role="listbox"] li,ul[role="listbox"] li>div,div[data-baseweb="menu"] li,div[role="option"]{background:transparent!important;color:var(--text-primary)!important;font-size:var(--font-size-body)!important;min-height:var(--touch-target-min)!important}
ul[role="listbox"] li:hover,ul[role="listbox"] li[aria-selected="true"],div[role="option"]:hover,div[role="option"][aria-selected="true"]{background:var(--surface-interactive)!important;color:var(--text-primary)!important}
div[data-testid="stPills"] button,[data-baseweb="button-group"] button{border-radius:var(--radius-segment)!important;min-height:var(--touch-target-min)!important}
/* Badges */
.dg-ui-badge,.player-status-pill,.home-status-pill,.free-agent-score-pill,.dg-glyph-chip,.trade-summary-asset-chip{border-radius:var(--radius-pill)}
/* Legal footer — subordinate nav family (not CTA pills) */
.legal-footer-links{align-items:center;display:flex;flex-wrap:wrap;gap:var(--space-xs);margin:var(--space-sm) 0 var(--space-md)}
.legal-footer-link{align-items:center;background:transparent!important;border:var(--border-width-default) solid var(--border-subtle)!important;border-radius:var(--radius-control)!important;box-sizing:border-box;color:var(--text-muted)!important;display:inline-flex!important;font-size:var(--font-size-caption)!important;font-weight:var(--font-weight-metadata)!important;justify-content:center;letter-spacing:.02em;line-height:var(--line-height-caption)!important;min-height:var(--touch-target-min);padding-block:var(--space-xs)!important;padding-inline:var(--space-sm)!important;text-align:center;text-decoration:none!important;text-transform:none!important;white-space:nowrap;width:auto}
.legal-footer-link:hover{background:transparent!important;border-color:var(--border-standard)!important;color:var(--text-secondary)!important;transform:none!important}
.legal-footer-link:focus-visible{box-shadow:var(--focus-ring)!important;outline:none!important}
.legal-footer-link-active{background:var(--color-information-soft)!important;border-color:var(--border-accent)!important;color:var(--text-accent)!important}
/* Trade shell (preserve send/receive rails) */
.trade-summary-card,.trade-detail-modal,.trade-idea-card{background:var(--surface-1)!important;border:var(--border-width-default) solid var(--border-standard)!important;border-radius:var(--radius-panel)!important;box-shadow:var(--shadow-none)!important}
.trade-detail-modal .trade-side:first-child,.trade-summary-side--send{border-inline-start:var(--border-width-semantic) solid var(--color-danger)!important}
.trade-detail-modal .trade-side:last-child,.trade-summary-side--receive{border-inline-start:var(--border-width-semantic) solid var(--color-success)!important}
"""
