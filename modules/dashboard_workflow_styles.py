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

.st-key-dashboard_workflow .home-command-card-wide {
    border-color: var(--color-border-strong);
    min-height: 0;
    box-shadow: var(--shadow-surface-inset);
}

.st-key-dashboard_workflow .home-command-card-wide .home-command-card-value {
    font-size: var(--font-size-section-title);
    line-height: var(--line-height-title);
}

.st-key-dashboard_workflow .home-command-card:not(.home-command-card-wide) .home-command-card-note,
.st-key-dashboard_workflow .summary-tile-note {
    color: var(--color-text-muted);
}

.st-key-dashboard_workflow .dg-ui-section-title {
    letter-spacing: -0.01em;
}

@media (min-width: 1024px) {
    .st-key-dashboard_workflow {
        gap: calc(var(--space-xl) + var(--space-xs));
    }

    .st-key-dashboard_workflow .summary-tile-grid-compact {
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: var(--space-md);
    }

    .st-key-dashboard_workflow .home-command-grid {
        gap: var(--space-md);
    }
}

.dashboard-clear-state {
    align-items: baseline;
    background: var(--color-surface-primary);
    border: var(--border-width-default) solid var(--color-border);
    display: flex;
    gap: var(--space-sm);
    padding: var(--space-sm) var(--space-md);
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
</style>
"""
