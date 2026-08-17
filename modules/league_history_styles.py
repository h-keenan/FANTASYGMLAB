"""League Overview History styles — injected on the History route only."""

LEAGUE_HISTORY_CSS = """
.dg-lh-feed{display:grid;gap:var(--space-sm);margin:0 0 var(--space-lg);max-width:48rem;min-width:0}
.dg-lh-item{background:var(--color-surface-raised);border:var(--border-width-default) solid var(--color-border);box-sizing:border-box;display:grid;gap:var(--space-xs);max-width:100%;min-width:0;padding:var(--space-sm) var(--space-md)}
.dg-lh-head{align-items:baseline;display:flex;flex-wrap:wrap;gap:var(--space-xs) var(--space-sm);justify-content:space-between}
.dg-lh-kicker{color:var(--color-text-secondary);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.dg-lh-when{color:var(--color-text-muted);font:var(--type-supporting-metadata)}
.dg-lh-sides{display:grid;gap:var(--space-sm);grid-template-columns:minmax(0,1fr);min-width:0}
.dg-lh-side{min-width:0}
.dg-lh-team{align-items:center;display:flex;gap:var(--space-xs);min-width:0}
.dg-lh-team .team-logo-wrap,.dg-lh-team .dg-lh-logo{flex:0 0 1.75rem;height:1.75rem;overflow:hidden;width:1.75rem}
.dg-lh-team .team-logo-wrap img,.dg-lh-team .dg-lh-logo img{display:block;height:100%;object-fit:cover;width:100%}
.dg-lh-team-copy{min-width:0}
.dg-lh-team-name{color:var(--color-text-primary);font:var(--font-card-title);overflow-wrap:anywhere}
.dg-lh-team-owner{color:var(--color-text-muted);font:var(--type-supporting-metadata)}
.dg-lh-receives,.dg-lh-dropped,.dg-lh-faab{color:var(--color-text-muted);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);margin:var(--space-2xs) 0;text-transform:uppercase}
.dg-lh-assets{display:grid;gap:var(--space-2xs);min-width:0}
.dg-lh-item .dg-compact-asset{width:100%}
.dg-lh-empty{color:var(--color-text-secondary);font:var(--type-supporting-body);max-width:40rem}
@media (min-width:1024px){
.dg-lh-item--trade .dg-lh-sides{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
.dg-lh-feed{max-width:48rem}
}
@media (max-width:430px){
.dg-lh-item{padding:var(--space-sm)}
.dg-lh-sides{grid-template-columns:minmax(0,1fr)}
}
"""
