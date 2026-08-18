"""League Recaps / League Memory styles — injected on the Recaps route only."""

LEAGUE_RECAPS_CSS = """
.dg-recap-edition,.dg-recap-teaser{
    max-width:52rem;
    min-width:0;
    width:100%;
}
.dg-recap-masthead{
    border-bottom:var(--border-width-default) solid var(--color-border);
    margin:0 0 var(--space-md);
    padding:0 0 var(--space-sm);
}
.dg-recap-kicker{
    align-items:center;
    color:var(--color-text-muted);
    display:flex;
    font-size:var(--font-size-badge);
    gap:var(--space-xs);
    letter-spacing:var(--letter-spacing-badge);
    margin:0 0 var(--space-2xs);
    text-transform:uppercase;
}
.dg-recap-masthead h2{
    color:var(--color-text-primary);
    font:var(--type-section-title);
    letter-spacing:-0.02em;
    margin:0;
    text-transform:uppercase;
}
.dg-recap-headline{
    color:var(--color-text-secondary);
    font:var(--font-body);
    margin:var(--space-xs) 0 0;
}
.dg-recap-board{
    display:grid;
    gap:var(--space-md);
    grid-template-columns:minmax(0,1fr);
}
.dg-recap-story{
    border-left:var(--border-width-semantic) solid var(--color-border-strong);
    display:grid;
    gap:var(--space-2xs);
    min-width:0;
    padding:0 0 0 var(--space-sm);
}
.dg-recap-story--performance{border-left-color:var(--color-prestige-elite)}
.dg-recap-story--trade{border-left-color:var(--color-accent)}
.dg-recap-story--waiver{border-left-color:var(--color-success)}
.dg-recap-story--matchup{border-left-color:var(--color-information)}
.dg-recap-story--activity{border-left-color:var(--color-warning)}
.dg-recap-story-kicker{
    align-items:center;
    display:flex;
    gap:var(--space-xs);
}
.dg-recap-story-kicker h3{
    color:var(--color-text-primary);
    font-size:var(--font-size-card-title);
    letter-spacing:var(--letter-spacing-badge);
    margin:0;
    text-transform:uppercase;
}
.dg-recap-identity,.dg-recap-editorial{
    color:var(--color-text-primary);
    font-size:var(--font-size-body);
    font-weight:var(--font-weight-title);
    margin:0;
}
.dg-recap-summary,.dg-recap-lens,.dg-recap-empty,.dg-recap-teaser-note{
    color:var(--color-text-secondary);
    font-size:var(--font-size-body);
    line-height:var(--line-height-body);
    margin:0;
}
.dg-recap-metric{
    display:grid;
    gap:2px;
}
.dg-recap-metric span{
    color:var(--color-text-muted);
    font-size:var(--font-size-badge);
    letter-spacing:var(--letter-spacing-badge);
    text-transform:uppercase;
}
.dg-recap-metric strong{
    color:var(--color-text-primary);
    font-size:var(--font-size-section-title);
}
.dg-recap-players{
    display:flex;
    flex-wrap:wrap;
    gap:var(--space-xs);
}
.dg-recap-player{
    border-left:var(--border-width-semantic) solid var(--color-border-strong);
    color:var(--color-text-primary);
    font-size:var(--font-size-caption);
    padding-left:var(--space-xs);
}
.dg-recap-teaser{
    border-left:var(--border-width-semantic) solid var(--color-accent);
    margin:0 0 var(--space-md);
    padding:0 0 0 var(--space-sm);
}
.dg-recap-teaser-title{
    color:var(--color-text-primary);
    font:var(--font-card-title);
    margin:0;
}
.dg-recap-grades{
    align-items:center;
    color:var(--color-text-muted);
    display:flex;
    flex-wrap:wrap;
    font-size:var(--font-size-badge);
    gap:var(--space-xs);
    letter-spacing:var(--letter-spacing-badge);
    text-transform:uppercase;
}
.dg-recap-grade{color:var(--color-text-secondary)}
.dg-tx-grade{display:inline-flex;font:var(--font-card-title);letter-spacing:.04em}
.dg-tx-grade--success{color:var(--color-success)}
.dg-tx-grade--positive,.dg-tx-grade--accent{color:var(--color-information)}
.dg-tx-grade--neutral{color:var(--color-text-secondary)}
.dg-tx-grade--warning,.dg-tx-grade--risk{color:var(--color-warning)}
.dg-tx-grade--pending{color:var(--color-text-muted)}
@media (min-width:1024px){
    .dg-recap-edition{max-width:none}
    .dg-recap-board{grid-template-columns:repeat(2,minmax(0,1fr))}
    .dg-recap-story:first-child{grid-column:1/-1}
}
@media (max-width:430px){
    .dg-recap-board{grid-template-columns:minmax(0,1fr)}
}
div[class*="st-key-league_memory_view_"] [data-testid="stPills"],
div[class*="st-key-league_memory_view_"] [data-testid="stButtonGroup"],
div[class*="st-key-league_memory_view_"] [data-baseweb="button-group"],
div[class*="st-key-league_recaps_archive_"] [data-testid="stPills"],
div[class*="st-key-league_recaps_archive_"] [data-testid="stButtonGroup"],
div[class*="st-key-league_recaps_archive_"] [data-baseweb="button-group"]{
    display:flex;gap:0;width:100%;
}
div[class*="st-key-league_memory_view_"] [data-testid="stPills"] > div,
div[class*="st-key-league_memory_view_"] [data-testid="stButtonGroup"] > div,
div[class*="st-key-league_recaps_archive_"] [data-testid="stPills"] > div,
div[class*="st-key-league_recaps_archive_"] [data-testid="stButtonGroup"] > div{
    display:flex;flex:1 1 0;gap:0;width:100%;
}
div[class*="st-key-league_memory_view_"] [data-testid="stPills"] button,
div[class*="st-key-league_memory_view_"] [data-testid="stButtonGroup"] button,
div[class*="st-key-league_memory_view_"] [data-baseweb="button-group"] button,
div[class*="st-key-league_recaps_archive_"] [data-testid="stPills"] button,
div[class*="st-key-league_recaps_archive_"] [data-testid="stButtonGroup"] button,
div[class*="st-key-league_recaps_archive_"] [data-baseweb="button-group"] button{
    background:var(--color-surface-muted)!important;
    border:var(--border-width-default) solid var(--color-border)!important;
    border-radius:0!important;
    color:var(--color-text-secondary)!important;
    flex:1 1 0;
    font:var(--type-supporting-metadata)!important;
    letter-spacing:0.03em;
    min-height:var(--touch-target-min)!important;
    min-width:0!important;
    overflow:hidden;
    padding-inline:0.35rem!important;
    text-overflow:clip;
    white-space:nowrap;
}
div[class*="st-key-league_memory_view_"] [data-testid="stPills"] button[kind="primary"],
div[class*="st-key-league_memory_view_"] [data-testid="stPills"] button[aria-pressed="true"],
div[class*="st-key-league_memory_view_"] [data-testid="stButtonGroup"] button[kind="primary"],
div[class*="st-key-league_memory_view_"] [data-testid="stButtonGroup"] button[aria-pressed="true"],
div[class*="st-key-league_memory_view_"] [data-baseweb="button-group"] button[aria-pressed="true"],
div[class*="st-key-league_recaps_archive_"] [data-testid="stPills"] button[kind="primary"],
div[class*="st-key-league_recaps_archive_"] [data-testid="stPills"] button[aria-pressed="true"],
div[class*="st-key-league_recaps_archive_"] [data-testid="stButtonGroup"] button[kind="primary"],
div[class*="st-key-league_recaps_archive_"] [data-testid="stButtonGroup"] button[aria-pressed="true"],
div[class*="st-key-league_recaps_archive_"] [data-baseweb="button-group"] button[aria-pressed="true"]{
    background:var(--color-information-soft)!important;
    border-color:var(--color-information)!important;
    box-shadow:inset 0 -2px 0 var(--color-information);
    color:var(--color-text-primary)!important;
}
"""
