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
    display:flex;
    flex-direction:column;
    gap:var(--space-md);
}
.dg-recap-story{
    border-left:var(--border-width-semantic) solid var(--color-border-strong);
    display:grid;
    gap:var(--space-2xs);
    min-width:0;
    padding:0 0 0 var(--space-sm);
}
/* Routine (non-lead) stories share one grouped surface per category — see
   .dg-recap-group below for the color signal — so an individual card no
   longer repeats a colored left border; a plain divider separates rows
   within a group instead of N identically-bordered cards. */
.dg-recap-group-body .dg-recap-story{
    border-left:none;
    border-top:var(--border-width-default) solid var(--color-border);
    padding:var(--space-sm) 0 0;
}
.dg-recap-group-body .dg-recap-story:first-child{
    border-top:none;
    padding-top:0;
}
/* The lead story (stories[0] — the same story the masthead headline is
   drawn from) is the one card allowed to dominate: elevated surface, a
   full-strength colored border keyed to its own category, and bigger type. */
.dg-recap-story--lead{
    background:var(--color-surface-raised);
    border:var(--border-width-default) solid var(--color-border);
    border-left:var(--border-width-semantic) solid var(--color-accent);
    box-shadow:var(--shadow-card);
    padding:var(--space-md);
}
.dg-recap-story--lead.dg-recap-story--performance,
.dg-recap-story--lead.dg-recap-story--performance_low{border-left-color:var(--color-prestige-elite)}
.dg-recap-story--lead.dg-recap-story--trade{border-left-color:var(--color-accent)}
.dg-recap-story--lead.dg-recap-story--waiver,
.dg-recap-story--lead.dg-recap-story--waiver_low{border-left-color:var(--color-success)}
.dg-recap-story--lead.dg-recap-story--matchup,
.dg-recap-story--lead.dg-recap-story--matchup_close{border-left-color:var(--color-danger)}
.dg-recap-story--lead.dg-recap-story--activity,
.dg-recap-story--lead.dg-recap-story--activity_low{border-left-color:var(--color-warning)}
.dg-recap-story--lead.dg-recap-story--roster_riser{border-left-color:var(--color-accent)}
.dg-recap-story--lead .dg-recap-story-kicker h3{
    font-size:var(--font-size-section-title);
}
.dg-recap-story--lead .dg-recap-summary{
    color:var(--color-text-primary);
}
/* Category group header — one per run of consecutive same-category
   stories below the lead. Mirrors .dg-alerts-group (alerts_activity_styles.py)
   so a routine story's category reads through this label + accent bar
   instead of its own card repeating a colored border. */
.dg-recap-group{
    align-items:center;
    color:var(--color-text-muted);
    display:flex;
    font:var(--type-supporting-metadata);
    gap:var(--space-xs);
    letter-spacing:var(--letter-spacing-badge);
    margin:0 0 var(--space-2xs);
    text-transform:uppercase;
}
.dg-recap-group__bar{
    background:currentColor;
    display:inline-block;
    height:0.8rem;
    width:3px;
}
.dg-recap-group-body{
    display:grid;
    gap:var(--space-2xs);
}
.dg-recap-group--performance{color:var(--color-prestige-elite)}
.dg-recap-group--matchup{color:var(--color-danger)}
.dg-recap-group--waiver{color:var(--color-success)}
.dg-recap-group--trade{color:var(--color-accent)}
.dg-recap-group--activity{color:var(--color-warning)}
.dg-recap-group--roster{color:var(--color-accent)}
.dg-recap-group--other{color:var(--color-text-muted)}
.dg-recap-affordance{
    color:var(--color-accent);
    font:var(--type-supporting-metadata);
    letter-spacing:var(--letter-spacing-badge);
    margin:var(--space-2xs) 0 0;
    text-transform:uppercase;
}
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
