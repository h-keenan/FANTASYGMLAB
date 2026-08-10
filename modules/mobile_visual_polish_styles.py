"""Mobile visual hierarchy polish (#231). Injected after APP_CSS (not concatenated into it)."""

MOBILE_VISUAL_POLISH_CSS = """
.dg-surface-l0{background:var(--color-bg)}
.dg-surface-l1{background:var(--color-surface-primary);border:var(--border-width-default) solid var(--color-border)}
.dg-surface-l2{background:var(--color-surface-raised);border:var(--border-width-default) solid var(--color-border-strong)}
div[class*="st-key-dg_cta_primary_"] [data-testid="stButton"]>button{background:var(--color-surface-raised)!important;border:var(--border-width-default) solid var(--color-accent)!important;min-height:var(--touch-target-min)!important}
div[class*="st-key-dg_cta_secondary_"] [data-testid="stButton"]>button{background:var(--color-surface-raised)!important;border:var(--border-width-default) solid var(--color-border)!important;min-height:var(--touch-target-min)!important}
div[class*="st-key-dg_cta_tertiary_"] [data-testid="stButton"]>button{background:transparent!important;border:0!important;border-block-end:var(--border-width-default) solid var(--color-border)!important;border-radius:0!important;color:var(--color-text-secondary)!important;min-height:var(--touch-target-min)!important;text-align:left!important}
@media (max-width:900px){div[class*="st-key-dashboard_deep_analysis_nav"] [data-testid="stButton"]>button,div[class*="st-key-dg_cta_"] [data-testid="stButton"]>button{min-height:var(--touch-target-min)!important}}
div[class*="st-key-dashboard_deep_analysis_nav"],.home-quick-actions-shell{background:var(--color-surface-primary);border:var(--border-width-default) solid var(--color-border);padding:var(--space-2xs) var(--space-xs)}
.home-quick-nav-label,.home-quick-action-note{display:none!important}
div[class*="st-key-dashboard_deep_analysis_nav"] [data-testid="stButton"]>button{background:transparent!important;border:0!important;color:var(--color-text-secondary)!important;font-size:var(--font-size-badge)!important;font-weight:var(--font-weight-title)!important;min-height:var(--touch-target-min)!important;text-transform:uppercase!important}
div[data-testid="stExpander"]{background:var(--color-surface-primary)!important;border:var(--border-width-default) solid var(--color-border)!important;margin-block:0 var(--space-sm)!important}
div[data-testid="stExpander"] summary{min-height:var(--touch-target-min)!important}
.draft-review-pick-card{background:var(--color-surface-raised);border:var(--border-width-default) solid var(--color-border);border-inline-start:var(--border-width-semantic) solid var(--color-accent);padding:var(--space-xs) var(--space-sm)}
div[class*="st-key-decision_history"] [data-testid="stButton"]>button{background:transparent!important;border:0!important;border-block-end:var(--border-width-default) solid var(--color-border)!important;color:var(--color-text-secondary)!important;min-height:var(--touch-target-min)!important}
@media (max-width: 760px){.dg-executive-shell{background:transparent!important;border:0!important;box-shadow:none!important;padding-block:var(--space-2xs)!important;padding-inline:0!important}.dg-executive-shell__league{color:var(--color-text-muted)!important;font-size:var(--font-size-caption)!important;text-transform:none!important}div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] button svg,div[class*="st-key-executive_command_actions"] [data-testid="stButton"]>button svg{opacity:.55!important}}
"""
