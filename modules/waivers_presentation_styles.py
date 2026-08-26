"""Token-backed layout adapters for the canonical Waivers presentation."""

WAIVERS_PRESENTATION_CSS = """
.waiver-section-header .dg-ui-section-header {
    margin-bottom: var(--space-md);
}

.free-agent-list {
    display: grid;
    gap: var(--space-sm);
}

.free-agent-card.dg-ui-card {
    border-color: var(--color-border) !important;
    border-radius: var(--radius-none) !important;
    box-shadow: var(--shadow-card), var(--shadow-surface-inset) !important;
    clip-path: none !important;
    margin: 0 !important;
    min-height: var(--touch-target-min);
    overflow: hidden;
    padding: var(--space-md) !important;
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
    grid-template-columns: var(--size-roster-core-portrait) minmax(0, 1fr);
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
    border-radius: var(--radius-none);
    margin-top: var(--space-sm);
    padding: var(--space-xs) var(--space-sm);
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
.waiver-decision-why,
.waiver-context-block p {
    color: var(--color-text-primary);
    font-size: var(--font-size-caption);
    font-weight: var(--font-weight-metadata);
    line-height: var(--line-height-caption);
    margin: var(--space-2xs) 0 0;
    overflow: visible;
    overflow-wrap: anywhere;
    white-space: normal;
}

.waiver-compact-metrics {
    color: var(--color-text-muted);
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-xs) var(--space-sm);
    font-size: var(--font-size-caption);
    margin-top: var(--space-sm);
    opacity: 0.9;
}

.waiver-snapshot-avatar {
    border-radius: var(--radius-none);
    height: var(--size-roster-core-portrait);
    width: var(--size-roster-core-portrait);
}

.waiver-snapshot-avatar img {
    height: 100%;
    object-fit: cover;
    width: 100%;
}

.free-agent-avatar {
    height: var(--size-roster-core-portrait);
    width: var(--size-roster-core-portrait);
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
    border-radius: var(--radius-none);
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
    border-radius: var(--radius-none);
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
    margin-top: var(--space-sm);
    min-height: var(--touch-target-min);
    padding-top: var(--space-xs);
}

.waiver-recommendation-row {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-xs);
    margin-top: var(--space-sm);
}

.waiver-card-decision-grid {
    display: grid;
    gap: var(--space-sm);
    min-width: 0;
}

div[class*="st-key-waiver_recommendation_"] {
    border: var(--border-width-default) solid var(--color-border);
    border-radius: var(--radius-none);
    margin-bottom: var(--space-sm);
    padding: var(--space-sm);
}

div[class*="st-key-waiver_recommendation_"] .free-agent-card.dg-ui-card {
    border: 0 !important;
    box-shadow: none !important;
}

div[class*="st-key-waiver_recommendation_"] div[data-testid="stButton"] {
    display: flex;
    justify-content: flex-end;
    margin-top: var(--space-2xs);
}

div[class*="st-key-waiver_recommendation_"] div[data-testid="stButton"] button {
    min-height: var(--touch-target-min);
    width: auto;
}

.waiver-faab-block dt {
    color: var(--color-text-muted);
    font-size: var(--font-size-badge);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}

.waiver-faab-block dd {
    color: var(--color-text-primary);
    font: var(--font-card-title);
    margin: var(--space-2xs) 0 0;
}

.waiver-faab-block p {
    color: var(--color-text-secondary);
    font-size: var(--font-size-caption);
    line-height: var(--line-height-caption);
    margin: var(--space-2xs) 0 0;
}

.waiver-faab-block--compact {
    margin-top: var(--space-xs);
}

.waiver-faab-block dd {
    color: var(--color-text-primary);
    font: var(--font-card-title);
    margin: var(--space-2xs) 0 0;
}

.waiver-faab-block p {
    color: var(--color-text-secondary);
    font-size: var(--font-size-caption);
    line-height: var(--line-height-caption);
    margin: var(--space-2xs) 0 0;
}

.free-agent-summary-card {
    border-color: var(--color-border) !important;
    border-radius: var(--radius-none) !important;
    box-shadow: var(--shadow-surface-inset) !important;
    clip-path: none !important;
    opacity: 0.96;
}

.free-agent-card.dg-ui-card {
    border-inline-start: var(--border-width-semantic) solid var(--color-opportunity);
}

.free-agent-summary-grid {
    display: grid;
    gap: var(--space-sm);
    grid-template-columns: minmax(0, 1fr);
    margin: var(--space-sm) 0;
}

@media (min-width: 72rem) {
    .free-agent-summary-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .free-agent-card .waiver-card-decision-grid {
        align-items: start;
        grid-template-columns: minmax(0, 1fr) minmax(0, 1.35fr) auto;
        margin-top: var(--space-md);
    }

    .free-agent-card .waiver-recommendation-row,
    .free-agent-card .waiver-compact-metrics,
    .free-agent-card .waiver-faab-block,
    .free-agent-card .waiver-decision-summary,
    .free-agent-card .waiver-card-action {
        margin-top: 0;
    }

    .free-agent-card .waiver-card-action {
        min-height: var(--touch-target-min);
    }
}

@media (min-width: 90rem) {
    .free-agent-summary-grid {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }
}

@media (max-width: 700px) {
    .free-agent-card.dg-ui-card {
        padding: var(--space-md) !important;
    }

    .free-agent-main {
        grid-template-columns: var(--size-roster-core-portrait) minmax(0, 1fr);
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

    .waiver-decision-why {
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 2;
        display: -webkit-box;
        overflow: hidden;
    }

    .free-agent-summary-grid {
        grid-template-columns: minmax(0, 1fr) !important;
    }

    .dg-football-asset.free-agent-summary-card,
    .dg-football-asset.free-agent-card {
        align-items: start;
        grid-template-columns: auto minmax(0, 1fr);
    }

    .dg-football-asset.free-agent-summary-card .dg-football-asset__value,
    .dg-football-asset.free-agent-card .dg-football-asset__value {
        grid-column: 1 / -1;
        margin-top: var(--space-sm);
        text-align: left;
    }

    .dg-football-asset.free-agent-summary-card .dg-football-asset__name,
    .dg-football-asset.free-agent-card .dg-football-asset__name {
        hyphens: none;
        overflow-wrap: break-word;
        word-break: normal;
    }

    .waiver-faab-block {
        margin-top: var(--space-xs);
    }

    div[class*="st-key-waiver_recommendation_"] div[data-testid="stButton"] {
        justify-content: flex-end;
    }

    div[class*="st-key-waiver_recommendation_"] div[data-testid="stButton"] button {
        width: auto;
    }
}

@media (max-width: 430px) {
    .free-agent-card.dg-ui-card {
        padding: var(--space-sm) var(--space-md) !important;
    }

    .waiver-decision-why {
        -webkit-line-clamp: 2;
    }
}

@media (max-width: 390px) {
    .waiver-context-grid,
    .waiver-metric-row {
        grid-template-columns: 1fr;
    }
}
"""
