"""Scoped styles for the canonical DynastyGM UI primitives."""

UI_PRIMITIVE_CSS = """
/* DynastyGM UI primitives: all values resolve through semantic tokens. */
.dg-ui-section-header,
.dg-ui-card,
.dg-ui-callout,
.dg-ui-empty-state {
    box-sizing: border-box;
    color: var(--color-text-primary);
    font: var(--font-body);
}

.dg-ui-player-card:is(.compact-player-row) {
    background: var(--color-surface-primary);
    border: var(--border-width-default) solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-surface-inset);
    min-height: var(--touch-target-min);
    overflow: hidden;
}

.dg-ui-player-card:is(.compact-player-row):hover {
    background: var(--color-surface-raised);
    border-color: var(--color-border-strong);
}

.dg-ui-player-card:is(.compact-player-row):focus-visible {
    box-shadow: var(--focus-ring);
    outline: none;
}

.dg-ui-section-header {
    align-items: flex-start;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-md);
    justify-content: space-between;
    margin: 0 0 var(--space-lg);
}

.dg-ui-section-header-copy {
    flex: 1 1 16rem;
    min-width: 0;
}

.dg-ui-eyebrow,
.dg-ui-card-metadata {
    color: var(--color-text-muted);
    font-size: var(--font-size-caption);
    font-weight: var(--font-weight-metadata);
    line-height: var(--line-height-caption);
}

.dg-ui-eyebrow,
.dg-ui-badge {
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}

.dg-ui-section-title {
    color: var(--color-text-primary);
    font-size: var(--font-size-section-title);
    font-weight: var(--font-weight-title);
    line-height: var(--line-height-title);
    margin: var(--space-xs) 0 0;
}

.dg-ui-section-subtitle,
.dg-ui-card-body,
.dg-ui-callout-body,
.dg-ui-empty-state-body,
.dg-ui-empty-state-recovery {
    color: var(--color-text-muted);
    line-height: var(--line-height-body);
    margin: var(--space-sm) 0 0;
}

.dg-ui-section-action,
.dg-ui-inline-action {
    align-items: center;
    border: var(--border-width-default) solid var(--color-border-strong);
    border-radius: var(--radius-md);
    color: var(--color-accent);
    display: inline-flex;
    font-size: var(--font-size-body);
    font-weight: var(--font-weight-button);
    min-height: var(--control-min-height);
    padding: 0 var(--space-lg);
    text-decoration: none;
}

.dg-ui-section-action:hover,
.dg-ui-inline-action:hover {
    background: var(--color-accent-soft);
    border-color: var(--color-accent);
}

.dg-ui-section-action:focus-visible,
.dg-ui-inline-action:focus-visible {
    box-shadow: var(--focus-ring);
    outline: none;
}

.dg-ui-card,
.dg-ui-callout,
.dg-ui-empty-state {
    background: var(--color-surface-primary);
    border: var(--border-width-default) solid var(--color-border);
    border-radius: var(--radius-lg);
    overflow-wrap: anywhere;
    padding: var(--space-lg);
}

.dg-ui-card--elevated {
    box-shadow: var(--shadow-card);
}

.dg-ui-card--interactive {
    border-color: var(--color-border-strong);
    transition: border-color var(--motion-fast), background var(--motion-fast);
}

.dg-ui-card-link {
    color: inherit;
    display: block;
    text-decoration: none;
}

.dg-ui-card-link:hover .dg-ui-card--interactive {
    background: var(--color-surface-raised);
    border-color: var(--color-accent);
}

.dg-ui-card-link:focus-visible {
    border-radius: var(--radius-lg);
    box-shadow: var(--focus-ring);
    outline: none;
}

.dg-ui-card--premium,
.dg-ui-callout--premium {
    border-left: var(--border-width-semantic) solid var(--color-premium);
}

.dg-ui-card--experimental,
.dg-ui-callout--experimental {
    border-left: var(--border-width-semantic) solid var(--color-experimental);
}

.dg-ui-card--warning,
.dg-ui-callout--caution {
    border-left: var(--border-width-semantic) solid var(--color-warning);
}

.dg-ui-card-title,
.dg-ui-callout-title,
.dg-ui-empty-state-title {
    color: var(--color-text-secondary);
    font: var(--font-card-title);
    margin: 0;
}

.dg-ui-card-metadata {
    margin-top: var(--space-sm);
}

.dg-ui-card-list {
    display: grid;
    gap: var(--space-sm) var(--space-lg);
    grid-template-columns: repeat(2, minmax(0, 1fr));
    margin: var(--space-md) 0 0;
    padding-left: var(--space-xl);
}

.dg-ui-card-list-item {
    color: var(--color-text-secondary);
    line-height: var(--line-height-body);
    min-width: 0;
    overflow-wrap: anywhere;
    padding-left: var(--space-xs);
}

.dg-ui-card-footer {
    border-top: var(--border-width-default) solid var(--color-border);
    margin-top: var(--space-lg);
    padding-top: var(--space-md);
}

.dg-ui-badge {
    align-items: center;
    border: var(--border-width-default) solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    display: inline-flex;
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    line-height: var(--line-height-badge);
    min-height: var(--space-xl);
    padding: 0 var(--space-sm);
}

.dg-ui-badge--neutral { background: var(--color-muted-soft); color: var(--color-text-secondary); }
.dg-ui-badge--information { background: var(--color-information-soft); color: var(--color-information); }
.dg-ui-badge--opportunity { background: var(--color-opportunity-soft); color: var(--color-opportunity); }
.dg-ui-badge--success { background: var(--color-success-soft); color: var(--color-success); }
.dg-ui-badge--caution { background: var(--color-warning-soft); color: var(--color-warning); }
.dg-ui-badge--danger { background: var(--color-danger-soft); color: var(--color-danger); }
.dg-ui-badge--premium { background: var(--color-action-soft); color: var(--color-premium); }
.dg-ui-badge--experimental { background: var(--color-diagnostic-soft); color: var(--color-experimental); }

.dg-ui-callout {
    background: var(--color-information-soft);
    border-left: var(--border-width-semantic) solid var(--color-information);
}

.dg-ui-callout--success { background: var(--color-success-soft); border-left-color: var(--color-success); }
.dg-ui-callout--caution { background: var(--color-warning-soft); border-left-color: var(--color-warning); }
.dg-ui-callout--danger { background: var(--color-danger-soft); border-left-color: var(--color-danger); }
.dg-ui-callout--premium { background: var(--color-action-soft); }
.dg-ui-callout--experimental { background: var(--color-diagnostic-soft); }

.dg-ui-callout-marker {
    color: var(--color-text-secondary);
    font-weight: var(--font-weight-metadata);
    margin-right: var(--space-xs);
}

.dg-ui-empty-state {
    background: var(--color-surface-muted);
    text-align: center;
}

.dg-ui-empty-state-actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-sm);
    justify-content: center;
    margin-top: var(--space-lg);
}

.dg-ui-inline-action--primary {
    background: var(--color-accent-soft);
    border-color: var(--color-accent);
}

.dg-ui-inline-action--secondary {
    color: var(--color-text-secondary);
}

@media (max-width: 640px) {
    .dg-ui-section-header,
    .dg-ui-empty-state-actions {
        align-items: stretch;
        flex-direction: column;
    }

    .dg-ui-section-action,
    .dg-ui-inline-action {
        justify-content: center;
        width: 100%;
    }

    .dg-ui-card-list {
        grid-template-columns: 1fr;
    }
}

@media (prefers-reduced-motion: reduce) {
    .dg-ui-card--interactive {
        transition: none;
    }
}
"""
