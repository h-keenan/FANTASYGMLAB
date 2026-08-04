"""Token-backed styles for the League Intelligence feed."""

LEAGUE_INTELLIGENCE_CSS = """
/* League Intelligence */
.dg-intelligence-group {
    margin: var(--space-xl) 0 var(--space-sm);
    color: var(--color-text-muted);
    font-size: var(--font-size-caption);
    font-weight: var(--font-weight-button);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}
.dg-intelligence-item {
    display: grid;
    gap: var(--space-sm);
    padding: var(--space-md);
    border: var(--border-width-default) solid var(--color-border);
    border-left: var(--border-width-semantic) solid var(--color-information);
    border-radius: var(--radius-none);
    background: var(--color-surface-primary);
    box-shadow: none;
}
.dg-intelligence-item--primary {
    border-left-color: var(--color-opportunity);
}
.dg-intelligence-item__header { display: grid; gap: var(--space-xs); }
.dg-intelligence-item__headline {
    margin: 0;
    color: var(--color-text-primary);
    font: var(--font-card-title);
    overflow-wrap: anywhere;
}
.dg-intelligence-item__headline a { color: inherit; text-decoration-thickness: 1px; text-underline-offset: 3px; }
.dg-intelligence-item__meta {
    margin: 0;
    color: var(--color-text-muted);
    font-size: var(--font-size-badge);
    letter-spacing: var(--letter-spacing-badge);
    line-height: var(--line-height-badge);
    opacity: 0.8;
    text-transform: uppercase;
}
.dg-intelligence-item__summary {
    margin: 0;
    color: var(--color-text-primary);
    font-size: var(--font-size-body);
    line-height: var(--line-height-body);
}
.dg-intelligence-item__signals { display: flex; gap: var(--space-xs); flex-wrap: wrap; align-items: center; }
.dg-intelligence-item__player { min-width: 0; }
.dg-intelligence-item__player .dg-ui-card,
.dg-intelligence-item__player .player-card,
.dg-intelligence-item__player .football-player-card {
    box-shadow: none;
    border-width: var(--border-width-default);
}
.dg-intelligence-explanation {
    margin: 0 0 var(--space-md);
    padding: var(--space-md);
    border-left: var(--border-width-semantic) solid var(--color-border-strong);
    background: var(--color-surface-muted);
    color: var(--color-text-secondary);
    font-size: var(--font-size-body);
    line-height: var(--line-height-body);
}
div[class*="st-key-league_intelligence_"] button { min-height: var(--touch-target-min); }
@media (min-width: 1024px) {
    .dg-intelligence-item {
        align-items: start;
        column-gap: var(--space-lg);
        grid-template-columns: minmax(11rem, 16rem) minmax(0, 1fr);
    }
    .dg-intelligence-item__player {
        grid-row: 1 / span 5;
    }
}
@media (max-width: 640px) {
    .dg-intelligence-item { padding: var(--space-md); gap: var(--space-sm); }
    .dg-intelligence-item__signals { align-items: stretch; }
}
@media (prefers-reduced-motion: reduce) {
    .dg-intelligence-item,
    .dg-intelligence-explanation { transition: none !important; }
}
"""
