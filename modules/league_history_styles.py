"""League Overview History styles — injected on the History route only."""

LEAGUE_HISTORY_CSS = """
.dg-lh-feed{display:grid;gap:var(--space-sm);margin:0 0 var(--space-lg);max-width:min(68rem,100%);min-width:0;width:100%}
.dg-lh-item{background:var(--color-surface-primary);border:var(--border-width-default) solid var(--color-border-strong);box-sizing:border-box;display:grid;gap:var(--space-2xs);max-width:100%;min-width:0;padding:var(--space-xs) var(--space-sm)}
.dg-tx-grades,.dg-tx-waiver-grade,.dg-tx-grade-block{display:grid;gap:2px;grid-template-columns:minmax(0,1fr);margin-top:0}
.dg-tx-side-grade{border-inline-start:var(--border-width-semantic) solid var(--color-information);padding-inline-start:var(--space-sm)}
.dg-tx-grade-heading{color:var(--color-text-secondary);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge)}
.dg-tx-grade-pending{border-inline-start:var(--border-width-semantic) solid var(--color-warning);display:grid;gap:var(--space-2xs);padding-inline-start:var(--space-sm)}
.dg-tx-grade-pending p{color:var(--color-text-secondary);font:var(--type-supporting-metadata);margin:0}
.dg-tx-side-row{align-items:baseline;display:flex;flex-wrap:wrap;gap:var(--space-xs) var(--space-sm);justify-content:space-between}
.dg-tx-side-name{color:var(--color-text-primary);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.dg-tx-grade{display:inline-flex;font:var(--font-card-title);letter-spacing:.04em;min-width:1.75rem}
.dg-tx-grade--success{color:var(--color-success)}
.dg-tx-grade--positive,.dg-tx-grade--accent{color:var(--color-information)}
.dg-tx-grade--neutral{color:var(--color-text-secondary)}
.dg-tx-grade--warning,.dg-tx-grade--risk{color:var(--color-warning)}
.dg-tx-grade--pending{color:var(--color-text-muted)}
.dg-tx-conf,.dg-tx-when{color:var(--color-text-muted);font:var(--type-supporting-metadata)}
.dg-tx-why,.dg-tx-watch{color:var(--color-text-secondary);font:var(--type-supporting-metadata);margin:0}
.dg-tx-why span,.dg-tx-watch span{color:var(--color-text-muted);letter-spacing:var(--letter-spacing-badge);margin-right:var(--space-2xs);text-transform:uppercase}
.dg-lh-head{align-items:baseline;display:flex;flex-wrap:wrap;gap:var(--space-xs) var(--space-sm);justify-content:space-between}
.dg-lh-kicker{color:var(--color-text-secondary);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.dg-lh-when{color:var(--color-text-muted);font:var(--type-supporting-metadata)}
.dg-lh-sides{display:grid;gap:var(--space-sm);grid-template-columns:minmax(0,1fr);min-width:0}
.dg-lh-side{background:transparent;border:0;display:grid;gap:2px;min-width:0;padding:0}
.dg-lh-team{align-items:center;display:flex;gap:var(--space-xs);min-width:0}
.dg-lh-team .team-logo-wrap,.dg-lh-team .dg-lh-logo{flex:0 0 1.75rem;height:1.75rem;overflow:hidden;width:1.75rem}
.dg-lh-team .team-logo-wrap img,.dg-lh-team .dg-lh-logo img{display:block;height:100%;object-fit:cover;width:100%}
.dg-lh-team-copy{min-width:0}
.dg-lh-team-name{color:var(--color-text-primary);font:var(--font-card-title);overflow-wrap:anywhere}
.dg-lh-team-owner{color:var(--color-text-muted);font:var(--type-supporting-metadata)}
.dg-lh-receives,.dg-lh-dropped,.dg-lh-faab{color:var(--color-text-muted);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);margin:var(--space-2xs) 0;text-transform:uppercase}
.dg-lh-assets{display:grid;gap:var(--space-2xs);min-width:0}
.dg-lh-item .dg-compact-asset{width:100%}
.dg-lh-item .dg-compact-asset--standard{--size-asset-standard:3.25rem}
.dg-lh-exchange{align-items:center;color:var(--color-information);display:flex;font:var(--type-supporting-metadata);gap:var(--space-sm);justify-content:center;letter-spacing:var(--letter-spacing-badge);margin:var(--space-xs) 0;text-transform:uppercase}
.dg-lh-exchange::before,.dg-lh-exchange::after{background:var(--color-border);content:"";flex:1 1 auto;height:1px}
.dg-lh-empty{color:var(--color-text-secondary);font:var(--type-supporting-body);max-width:40rem}
div[class*="st-key-league_history_season_"] [data-testid="stPills"],
div[class*="st-key-league_history_season_"] [data-testid="stButtonGroup"],
div[class*="st-key-league_history_season_"] [data-baseweb="button-group"],
div[class*="st-key-league_history_filter_"] [data-testid="stPills"],
div[class*="st-key-league_history_filter_"] [data-testid="stButtonGroup"],
div[class*="st-key-league_history_filter_"] [data-baseweb="button-group"]{
    display:flex;flex-wrap:wrap;gap:0;width:100%;
}
div[class*="st-key-league_history_season_"] [data-testid="stPills"] button,
div[class*="st-key-league_history_season_"] [data-testid="stButtonGroup"] button,
div[class*="st-key-league_history_season_"] [data-baseweb="button-group"] button,
div[class*="st-key-league_history_filter_"] [data-testid="stPills"] button,
div[class*="st-key-league_history_filter_"] [data-testid="stButtonGroup"] button,
div[class*="st-key-league_history_filter_"] [data-baseweb="button-group"] button{
    background:var(--color-surface-muted)!important;
    border:var(--border-width-default) solid var(--color-border)!important;
    border-radius:0!important;
    color:var(--color-text-secondary)!important;
    font:var(--type-supporting-metadata)!important;
    letter-spacing:0.03em;
    min-height:var(--touch-target-min)!important;
    min-width:0!important;
    overflow:hidden;
    padding-inline:0.35rem!important;
    text-overflow:clip;
    white-space:nowrap;
}
div[class*="st-key-league_history_season_"] [data-testid="stPills"] button[kind="primary"],
div[class*="st-key-league_history_season_"] [data-testid="stPills"] button[aria-pressed="true"],
div[class*="st-key-league_history_season_"] [data-testid="stButtonGroup"] button[kind="primary"],
div[class*="st-key-league_history_season_"] [data-testid="stButtonGroup"] button[aria-pressed="true"],
div[class*="st-key-league_history_season_"] [data-baseweb="button-group"] button[aria-pressed="true"],
div[class*="st-key-league_history_filter_"] [data-testid="stPills"] button[kind="primary"],
div[class*="st-key-league_history_filter_"] [data-testid="stPills"] button[aria-pressed="true"],
div[class*="st-key-league_history_filter_"] [data-testid="stButtonGroup"] button[kind="primary"],
div[class*="st-key-league_history_filter_"] [data-testid="stButtonGroup"] button[aria-pressed="true"],
div[class*="st-key-league_history_filter_"] [data-baseweb="button-group"] button[aria-pressed="true"]{
    background:var(--color-information-soft)!important;
    border-color:var(--color-information)!important;
    box-shadow:inset 0 -2px 0 var(--color-information);
    color:var(--color-text-primary)!important;
}
@media (min-width:1024px){
.dg-lh-item--trade .dg-lh-sides{align-items:center;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr)}
.dg-lh-item--trade .dg-lh-exchange{grid-column:auto;margin:0;min-width:2.5rem}
.dg-lh-item--trade .dg-lh-exchange::before,.dg-lh-item--trade .dg-lh-exchange::after{display:none}
.dg-lh-item--trade .dg-tx-grades{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
.dg-lh-feed{max-width:100%}
}
@media (max-width:430px){
.dg-lh-item{padding:var(--space-sm)}
.dg-lh-sides{grid-template-columns:minmax(0,1fr)}
}
"""
