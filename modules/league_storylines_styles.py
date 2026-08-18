"""League Storylines styles — injected with History, not on cold APP_CSS."""

LEAGUE_STORYLINES_CSS = """
.dg-ls-panel{display:grid;gap:var(--space-sm);margin:0 0 var(--space-lg);max-width:48rem;min-width:0}
.dg-ls-grid{display:grid;gap:var(--space-sm);grid-template-columns:minmax(0,1fr);min-width:0}
.dg-ls-card{background:var(--color-surface-raised);border:var(--border-width-default) solid var(--color-border);box-sizing:border-box;display:grid;gap:var(--space-2xs);min-width:0;padding:var(--space-sm) var(--space-md)}
.dg-ls-kicker{color:var(--color-text-secondary);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.dg-ls-question{color:var(--color-text-muted);font:var(--type-supporting-metadata)}
.dg-ls-value{color:var(--color-text-primary);font:var(--font-card-title)}
.dg-ls-note{color:var(--color-text-muted);font:var(--type-supporting-metadata)}
.dg-ls-card .dg-lh-team{align-items:center;display:flex;gap:var(--space-xs);max-width:100%;min-width:0}
.dg-ls-card .dg-lh-team .dg-lh-logo,.dg-ls-card .dg-lh-team .team-logo-wrap{flex:0 0 3.5rem;height:3.5rem;overflow:hidden;width:3.5rem}
.dg-ls-card .dg-lh-team .dg-lh-logo img,.dg-ls-card .dg-lh-team .team-logo-wrap img{display:block;height:100%;max-height:3.5rem;max-width:3.5rem;object-fit:cover;width:100%}
.dg-ls-card .dg-compact-asset{max-width:100%}
.dg-ls-teams{display:flex;flex-direction:column;gap:var(--space-xs);min-width:0}
.dg-ls-empty{color:var(--color-text-secondary);font:var(--type-supporting-body);max-width:40rem}
@media (min-width:700px){
.dg-ls-grid{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
.dg-ls-card--wide{grid-column:1 / -1}
}
@media (min-width:1024px){
.dg-ls-panel{max-width:48rem}
}
@media (max-width:430px){
.dg-ls-card{padding:var(--space-sm)}
.dg-ls-grid{grid-template-columns:minmax(0,1fr)}
.dg-ls-card .dg-lh-team .dg-lh-logo,.dg-ls-card .dg-lh-team .team-logo-wrap{flex-basis:3.25rem;height:3.25rem;width:3.25rem}
.dg-ls-card .dg-lh-team .dg-lh-logo img,.dg-ls-card .dg-lh-team .team-logo-wrap img{max-height:3.25rem;max-width:3.25rem}
}
"""
