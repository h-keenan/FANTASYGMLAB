"""Token-backed layout adapters for the canonical Waivers presentation."""

WAIVERS_PRESENTATION_CSS = """
/* Waivers migration: canonical primitives with a compact decision hierarchy. */
.waiver-section-header .dg-ui-section-header {
    margin-bottom: var(--space-md);
}

.free-agent-list {
    display: grid;
    gap: var(--space-md);
}

.free-agent-card.dg-ui-card {
    border-color: var(--color-border) !important;
    border-radius: var(--radius-lg) !important;
    box-shadow: var(--shadow-card), var(--shadow-surface-inset) !important;
    clip-path: none !important;
    margin: 0 !important;
    min-height: var(--touch-target-min);
    overflow: hidden;
    padding: var(--space-lg) !important;
}

.free-agent-card.player-card-tappable:hover {
    background: var(--color-surface-raised) !important;
    border-color: var(--color-border-strong) !important;
}

.free-agent-card.player-card-tappable:focus-visible {
    box-shadow: var(--focus-ring) !important;
    outline: none;
}

.free-agent-main {
    align-items: start;
    display: grid;
    gap: var(--space-md);
    grid-template-columns: var(--space-3xl) minmax(0, 1fr);
}

.free-agent-copy,
.free-agent-name-block {
    min-width: 0;
}

.free-agent-top {
    align-items: start;
    display: flex;
    gap: var(--space-md);
    justify-content: space-between;
}

.free-agent-status-row,
.free-agent-tags {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-xs);
}

.free-agent-name {
    color: var(--color-text-primary);
    font: var(--font-card-title);
    margin-top: var(--space-sm);
    overflow-wrap: anywhere;
}

.free-agent-meta {
    color: var(--color-text-muted);
    font-size: var(--font-size-caption);
    line-height: var(--line-height-caption);
    margin-top: var(--space-xs);
}

.free-agent-tags {
    margin-top: var(--space-sm);
}

.free-agent-score-pill {
    flex: 0 0 auto;
}

.waiver-decision-summary {
    background: var(--color-opportunity-soft);
    border-left: var(--border-width-semantic) solid var(--color-opportunity);
    border-radius: var(--radius-md);
    margin-top: var(--space-md);
    padding: var(--space-sm) var(--space-md);
}

.waiver-card-label {
    color: var(--color-text-muted);
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    line-height: var(--line-height-badge);
    text-transform: uppercase;
}

.waiver-decision-summary p,
.waiver-context-block p {
    color: var(--color-text-secondary);
    font-size: var(--font-size-body);
    line-height: var(--line-height-body);
    margin: var(--space-xs) 0 0;
    overflow-wrap: anywhere;
}

.waiver-context-grid {
    display: grid;
    gap: var(--space-sm);
    grid-template-columns: repeat(2, minmax(0, 1fr));
    margin-top: var(--space-sm);
}

.waiver-context-block {
    background: var(--color-surface-muted);
    border: var(--border-width-default) solid var(--color-border);
    border-radius: var(--radius-md);
    min-width: 0;
    padding: var(--space-sm) var(--space-md);
}

.waiver-context-block strong {
    color: var(--color-text-primary);
    display: block;
    font: var(--font-card-title);
    margin-top: var(--space-xs);
    overflow-wrap: anywhere;
}

.waiver-metric-row {
    display: grid;
    gap: var(--space-xs);
    grid-template-columns: repeat(4, minmax(0, 1fr));
    margin: var(--space-sm) 0 0;
}

.waiver-metric-row > div {
    background: var(--color-surface-muted);
    border: var(--border-width-default) solid var(--color-border);
    border-radius: var(--radius-md);
    min-width: 0;
    padding: var(--space-sm);
}

.waiver-metric-row dt {
    color: var(--color-text-muted);
    font-size: var(--font-size-badge);
    line-height: var(--line-height-caption);
}

.waiver-metric-row dd {
    color: var(--color-text-primary);
    font: var(--font-card-title);
    margin: var(--space-xs) 0 0;
    overflow-wrap: anywhere;
}

.waiver-card-action {
    align-items: center;
    border-top: var(--border-width-default) solid var(--color-border);
    color: var(--color-accent);
    display: flex;
    font-size: var(--font-size-caption);
    font-weight: var(--font-weight-button);
    justify-content: flex-end;
    margin-top: var(--space-md);
    min-height: var(--touch-target-min);
    padding-top: var(--space-sm);
}

.free-agent-summary-card {
    border-color: var(--color-border) !important;
    border-radius: var(--radius-lg) !important;
    box-shadow: var(--shadow-surface-inset) !important;
    clip-path: none !important;
}

@media (max-width: 700px) {
    .free-agent-card.dg-ui-card {
        padding: var(--space-md) !important;
    }

    .free-agent-main {
        grid-template-columns: var(--space-3xl) minmax(0, 1fr);
    }

    .free-agent-top {
        align-items: stretch;
        flex-direction: column;
    }

    .free-agent-score-pill {
        align-self: flex-start;
    }

    .waiver-context-grid,
    .waiver-metric-row {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .waiver-card-action {
        justify-content: center;
    }
}

@media (max-width: 390px) {
    .waiver-context-grid,
    .waiver-metric-row {
        grid-template-columns: 1fr;
    }
}
"""
