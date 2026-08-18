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
@media (min-width:1024px){
    .dg-recap-edition{max-width:none}
    .dg-recap-board{grid-template-columns:repeat(2,minmax(0,1fr))}
    .dg-recap-story:first-child{grid-column:1/-1}
}
@media (max-width:430px){
    .dg-recap-board{grid-template-columns:minmax(0,1fr)}
}
"""
