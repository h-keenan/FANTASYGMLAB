"""Token-backed styles for the five-zone Dashboard briefing."""

DASHBOARD_WORKFLOW_CSS = """
<style>
.st-key-dashboard_workflow {
    display: grid;
    gap: var(--space-xl);
}

.dashboard-workflow-shell {
    height: 0;
    overflow: hidden;
}

.st-key-dashboard_workflow .dg-ui-section-header {
    margin-bottom: 0;
}

.st-key-dashboard_workflow .home-command-grid {
    margin: 0;
}

.st-key-dashboard_workflow .home-command-card-wide,
.st-key-dashboard_workflow .home-command-card-primary {
    border-color: var(--color-border-strong);
    min-height: 0;
    box-shadow: var(--shadow-surface-inset);
}

.st-key-dashboard_workflow .home-command-card-wide .home-command-card-value,
.st-key-dashboard_workflow .home-command-card-primary .home-command-card-value {
    font-size: var(--font-size-section-title);
    line-height: var(--line-height-title);
}

.st-key-dashboard_workflow .home-command-card-secondary {
    min-height: 0;
}

.st-key-dashboard_workflow .dg-ui-section-subtitle {
    max-width: 36rem;
}

@media (min-width: 1024px) {
    .st-key-dashboard_workflow .dg-ui-section-subtitle {
        max-width: none;
    }
}

.st-key-dashboard_workflow .summary-tile-grid-compact .summary-tile {
    min-height: 0;
}

.st-key-dashboard_workflow .home-command-card:not(.home-command-card-wide):not(.home-command-card-primary) .home-command-card-note,
.st-key-dashboard_workflow .summary-tile-note {
    color: var(--color-text-muted);
}

.st-key-dashboard_workflow .dg-ui-section-title {
    letter-spacing: 0.01em;
}

@media (min-width: 1024px) {
    .st-key-dashboard_workflow {
        gap: calc(var(--space-xl) + var(--space-xs));
    }

    /* Desktop home-command/summary grid geometry owned by
       DESKTOP_EXECUTIVE_LAYOUT_CSS + RECOMMENDATION_TRUST_CSS. */

    .st-key-dashboard_workflow .dg-ui-section-title {
        font-size: clamp(1.2rem, 1.5vw, 1.45rem) !important;
    }
}

.dashboard-clear-state {
    align-items: baseline;
    display: flex;
    gap: var(--space-sm);
}

.dashboard-clear-state strong {
    color: var(--color-success);
    font: var(--font-card-title);
    white-space: nowrap;
}

.dashboard-clear-state span {
    color: var(--color-text-secondary);
    font: var(--font-body);
}

.st-key-dashboard_workflow .summary-tile-grid-compact {
    grid-template-columns: repeat(3, minmax(0, 1fr));
}

.st-key-dashboard_workflow details summary {
    min-height: var(--touch-target-min);
}

@media (max-width: 700px) {
    .st-key-dashboard_workflow {
        gap: var(--space-lg);
    }

    .st-key-dashboard_workflow .dg-ui-section-title {
        font-size: clamp(1.05rem, 4.6vw, 1.25rem) !important;
        white-space: normal !important;
    }

    .st-key-dashboard_workflow .home-command-card-note,
    .st-key-dashboard_workflow .summary-tile-note {
        font-size: var(--font-size-caption);
        line-height: var(--line-height-caption);
    }

    .st-key-dashboard_workflow .summary-tile-grid-compact {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .st-key-dashboard_workflow .summary-tile,
    .st-key-dashboard_workflow .home-command-card {
        min-width: 0;
        width: 100%;
    }

    .dashboard-clear-state {
        align-items: flex-start;
        flex-direction: column;
        gap: var(--space-xs);
    }
}

/* Clear-then-hydrate owner — replaces stale Streamlit body during post-dismiss work. */
.dashboard-hydrate-placeholder {
    background: var(--surface-1);
    border: var(--border-width-default) solid var(--border-standard);
    border-radius: var(--radius-panel);
    margin: 0.35rem 0 0.75rem;
    padding: var(--space-sm) var(--space-md);
}
.dashboard-hydrate-kicker {
    color: var(--color-accent, var(--text-secondary));
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}
.dashboard-hydrate-title {
    color: var(--text-primary);
    font-size: var(--font-size-section-title);
    font-weight: var(--font-weight-title);
    margin-top: var(--space-2xs);
}
.dashboard-hydrate-copy {
    color: var(--text-secondary);
    font-size: var(--font-size-caption);
    line-height: var(--line-height-caption);
    margin-top: var(--space-2xs);
    max-width: 40rem;
}
</style>
"""
