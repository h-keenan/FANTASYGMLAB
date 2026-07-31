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
    gap: var(--space-md);
    padding: var(--space-lg);
    border: var(--border-width-default) solid var(--color-border);
    border-left: var(--border-width-semantic) solid var(--color-information);
    border-radius: var(--radius-none);
    background: var(--color-surface-primary);
    box-shadow: var(--shadow-surface-inset);
}
.dg-intelligence-item__header { display: grid; gap: var(--space-xs); }
.dg-intelligence-item__headline {
    margin: 0;
    color: var(--color-text-primary);
    font: var(--font-card-title);
    overflow-wrap: anywhere;
}
.dg-intelligence-item__headline a { color: inherit; text-decoration-thickness: 1px; text-underline-offset: 3px; }
.dg-intelligence-item__meta,
.dg-intelligence-item__summary {
    margin: 0;
    color: var(--color-text-muted);
    font-size: var(--font-size-caption);
    line-height: var(--line-height-body);
}
.dg-intelligence-item__signals { display: flex; gap: var(--space-xs); flex-wrap: wrap; align-items: center; }
.dg-intelligence-item__player { min-width: 0; }
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
@media (max-width: 640px) {
    .dg-intelligence-item { padding: var(--space-md); gap: var(--space-sm); }
    .dg-intelligence-item__signals { align-items: stretch; }
}
@media (prefers-reduced-motion: reduce) {
    .dg-intelligence-item,
    .dg-intelligence-explanation { transition: none !important; }
}
"""
