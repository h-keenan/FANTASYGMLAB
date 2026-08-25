"""Late visual hierarchy: primary titles vs muted metadata vs semantic rails.

Loaded after EXECUTIVE_DESIGN_UNIFY so muted !important labels do not win.
Presentation only. Token-backed. No hex/rgba.
"""

CARD_HIERARCHY_CSS = """
.summary-tile-label,.dg-ui-card-title,.analysis-card-title,.advice-title,.free-agent-summary-name,.dg-intel-title,.dg-intel-kicker,.dg-intel-kicker>span{color:var(--color-text-primary)!important;opacity:1}
.summary-tile-value,.home-command-card-value,.home-command-card-secondary .home-command-card-value,.dg-ui-metric-grid .dg-ui-card-body,.dg-intel-metric{color:var(--color-text-primary)!important;font:var(--type-primary-metric)!important}
.analysis-card-label,.advice-label,.decision-panel-label,.home-command-card-label,.free-agent-summary-label,.summary-tile-note,.dg-ui-card-metadata,.dg-intel-note,.dg-intel-owner{color:var(--color-text-muted)!important}
.summary-tile-unavailable .summary-tile-label,.summary-tile-unavailable .summary-tile-value{color:var(--color-text-muted)!important;opacity:var(--opacity-metadata)}
.summary-tile-power,.dg-ui-metric-tile[data-concept=power]{border-inline-start:var(--border-width-semantic) solid var(--color-information)!important}
.summary-tile-franchise,.dg-ui-metric-tile[data-concept=franchise]{border-inline-start:var(--border-width-semantic) solid var(--color-premium)!important}
.dg-ui-metric-tile[data-concept=waiver]{border-inline-start:var(--border-width-semantic) solid var(--color-opportunity)!important}
.dg-ui-metric-tile[data-concept=league]{border-inline-start:var(--border-width-semantic) solid var(--color-diagnostic)!important}
.summary-tile-power .dg-semantic-icon,.summary-tile-power .dg-glyph,.dg-ui-metric-tile[data-concept=power] .dg-glyph{color:var(--color-information)!important}
.summary-tile-franchise .dg-semantic-icon,.summary-tile-franchise .dg-glyph,.dg-ui-metric-tile[data-concept=franchise] .dg-glyph{color:var(--color-premium)!important}
.home-command-card-risk .home-command-card-label,.analysis-card-risk .analysis-card-label{color:var(--color-warning)!important}
.home-command-card-need .home-command-card-label,.analysis-card-weakness .analysis-card-label{color:var(--color-warning)!important}
.dg-intel-kicker .dg-intel-glyph{color:var(--color-information)}
.dg-intel-card[data-intel-family=age] .dg-intel-glyph{color:var(--color-information)}
.dg-intel-card[data-intel-family=contend] .dg-intel-glyph{color:var(--color-opportunity)}
.dg-intel-card[data-intel-family=rebuild] .dg-intel-glyph{color:var(--color-diagnostic)}
.advice-card-strength{border-inline-start:var(--border-width-semantic) solid var(--color-opportunity)}
.advice-card-need,.advice-card-health{border-inline-start:var(--border-width-semantic) solid var(--color-warning)}
.advice-label .dg-glyph{margin-right:var(--space-2xs)}
@media (min-width:1024px){div[class*=st-key-my_team_roster_core] .scan-card-list.scan-card-list-compact{grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--space-sm)}}
@media (max-width:760px){div[class*=st-key-my_team_roster_core] .scan-card-list.scan-card-list-compact{grid-template-columns:1fr}}
"""
