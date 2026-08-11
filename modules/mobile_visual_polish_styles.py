"""Mobile visual hierarchy polish (#231/#236). Injected after APP_CSS (not concatenated into it)."""

MOBILE_VISUAL_POLISH_CSS = """
.dg-surface-l0{background:var(--color-bg)}
.dg-surface-l1{background:var(--color-surface-primary);border:var(--border-width-default) solid var(--color-border)}
.dg-surface-l2{background:var(--color-surface-raised);border:var(--border-width-default) solid var(--color-border-strong)}
div[class*="st-key-dg_cta_primary_"] [data-testid="stButton"] button{background:var(--color-surface-raised)!important;border:var(--border-width-default) solid var(--color-accent)!important;min-height:var(--touch-target-min)!important}
div[class*="st-key-dg_cta_secondary_"] [data-testid="stButton"] button{background:var(--color-surface-raised)!important;border:var(--border-width-default) solid var(--color-border)!important;min-height:var(--touch-target-min)!important}
div[class*="st-key-dg_cta_tertiary_"] [data-testid="stButton"] button,
div[class*="st-key-decision_history"] [data-testid="stButton"] button{background:transparent!important;border:0!important;border-block-end:var(--border-width-default) solid var(--color-border)!important;border-radius:var(--radius-none)!important;color:var(--color-text-secondary)!important;min-height:var(--touch-target-min)!important;text-align:left!important}
@media (max-width:900px){div[class*="st-key-dg_cta_"] [data-testid="stButton"] button{min-height:var(--touch-target-min)!important}}
[class*="dashboard_deep_analysis_nav"]{background:var(--color-surface-primary);border:var(--border-width-default) solid var(--color-border);height:auto!important;margin:0 0 var(--space-sm);min-height:0!important;overflow:hidden;padding:var(--space-xs)}
[class*="dashboard_deep_analysis_nav"] :is([data-testid="stVerticalBlock"],[data-testid="stHorizontalBlock"],[data-testid="stColumn"],[data-testid="stElementContainer"],[data-testid="stButton"]){height:auto!important;margin:0!important;min-height:0!important}
[class*="dashboard_deep_analysis_nav"] :is([data-testid="stHorizontalBlock"],[data-testid="stVerticalBlock"]){gap:var(--space-xs)!important}
[class*="dashboard_deep_analysis_nav"] [data-testid="stColumn"]{flex:1 1 calc(50% - .5rem)!important;max-width:calc(50% - .25rem)!important;min-width:0!important;width:auto!important}
.home-quick-actions-shell,.home-quick-nav-label,.home-quick-action-note{display:none!important}
[class*="dashboard_deep_analysis_nav"] [data-testid="stButton"] button{background:var(--color-surface-raised)!important;border:var(--border-width-default) solid var(--color-border)!important;border-radius:var(--radius-none)!important;color:var(--color-text-secondary)!important;font-size:var(--font-size-badge)!important;font-weight:var(--font-weight-button)!important;min-height:var(--touch-target-min)!important;padding:var(--space-xs) var(--space-sm)!important;text-align:center!important;text-transform:uppercase!important;white-space:nowrap!important}
@media (max-width:430px){[class*="dashboard_deep_analysis_nav"] [data-testid="stButton"] button{font-size:var(--font-size-caption,.68rem)!important;padding:var(--space-2xs) var(--space-xs)!important}}
div[data-testid="stExpander"]{background:var(--color-surface-primary)!important;border:var(--border-width-default) solid var(--color-border)!important;border-radius:var(--radius-panel)!important;margin-block:0 var(--space-sm)!important;padding:0!important}
div[data-testid="stExpander"] summary{min-height:var(--touch-target-min)!important}
/* Shared quiet status surface — What Changed / Game Plan quiet / clear-state */
.dg-what-changed-quiet,.dg-daily-briefing-quiet,.dashboard-clear-state{background:var(--color-surface-primary)!important;border:var(--border-width-default) solid var(--color-border)!important;border-radius:var(--radius-panel)!important;box-sizing:border-box;gap:var(--space-2xs)!important;padding:var(--space-sm) var(--space-md)!important}
.draft-review-pick-card{background:var(--color-surface-raised);border:var(--border-width-default) solid var(--color-border);border-inline-start:var(--border-width-semantic) solid var(--color-accent);padding:var(--space-xs) var(--space-sm)}
@media (max-width: 760px){.dg-executive-shell{background:transparent!important;border:0!important;box-shadow:none!important;padding-block:var(--space-2xs)!important;padding-inline:0!important}.dg-executive-shell__league{color:var(--color-text-muted)!important;font-size:var(--font-size-caption)!important;text-transform:none!important}div[class*="st-key-executive_command_actions"] [data-testid="stButton"] button svg{opacity:.55!important}}
"""
