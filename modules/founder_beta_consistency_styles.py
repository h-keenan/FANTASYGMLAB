"""Final shared hierarchy and mobile rhythm for the Founder Beta surfaces."""

FOUNDER_BETA_CONSISTENCY_CSS = """

.dg-workspace-page-kicker,
.dg-ui-eyebrow {
    font-size: var(--type-page-eyebrow-size) !important;
    line-height: var(--line-height-badge) !important;
}

.dg-workspace-page-title{
    font: var(--type-page-title) !important;
    letter-spacing: -0.035em !important;
    max-width: none !important;
    overflow-wrap: break-word !important;
    text-transform: uppercase;
    word-break: normal !important;
}

.dg-workspace-page-note{
    color: var(--color-text-secondary) !important;
    font: var(--type-body-explanation) !important;
}

.dg-ui-section-title,
.section-title,
.team-section-title {
    font: var(--type-section-title) !important;
    letter-spacing: -0.02em !important;
    text-transform: uppercase;
}

.dg-ui-section-subtitle,
.section-note {
    color: var(--color-text-muted) !important;
    font: var(--type-supporting-metadata) !important;
    opacity: var(--opacity-metadata);
}

.dg-ui-card-title,
.trade-summary-title,
.home-command-card-value,
.waiver-player-name,
.player-asset-card__name {
    font: var(--type-card-title) !important;
}

.summary-tile-value,
.team-rank-value,
.trade-summary-value strong,
.waiver-metric-row dd {
    font: var(--type-primary-metric) !important;
}

.dg-ui-card-metadata,
.summary-tile-note,
.trade-summary-partner,
.trade-summary-value,
.player-asset-card__meta {
    color: var(--color-text-muted) !important;
    font: var(--type-supporting-metadata) !important;
    opacity: var(--opacity-metadata);
}

.dg-ui-card-body,
.dg-ui-callout-body,
.trade-summary-rationale {
    font: var(--type-body-explanation) !important;
}

.dg-ui-badge,
.dg-glyph-chip {
    font-size: var(--type-badge-size) !important;
}

.st-key-dashboard_orientation_panel {
    border-left: var(--border-width-semantic) solid var(--color-information);
    margin: var(--space-sm) 0 var(--space-md);
    padding-left: var(--space-sm);
}

.st-key-dashboard_orientation_panel .dg-ui-badge {
    margin-bottom: var(--space-xs);
}

.st-key-dashboard_orientation_panel .dg-ui-card {
    padding: var(--space-md) !important;
}

.st-key-dashboard_orientation_panel .dg-ui-card-list {
    gap: var(--space-xs) var(--space-lg);
    margin-top: var(--space-sm);
}

.st-key-dashboard_orientation_panel .dg-ui-card-footer {
    margin-top: var(--space-sm);
    padding-top: var(--space-sm);
}

.dg-application-workspace {
    gap: var(--space-md) !important;
    margin-bottom: var(--space-md) !important;
}

.dg-workspace-page.dg-ops-briefing {
    min-height: 8.5rem !important;
    padding: var(--space-lg) var(--space-xl) !important;
}

.dg-workspace-page-note {
    margin-top: var(--space-sm) !important;
}

.dg-ui-section-header,
.section-header {
    margin: var(--space-xl) 0 var(--space-md) !important;
}

.dg-ui-card,
.dg-ui-callout,
.dg-ui-empty-state,
.summary-tile,
.home-command-card,
.trade-summary-card,
.free-agent-card,
.player-asset-card {
    border: var(--border-width-default) solid var(--color-border) !important;
    border-radius: var(--radius-panel) !important;
    box-shadow: var(--shadow-none) !important;
}

.dg-ui-card,
.dg-ui-callout,
.dg-ui-empty-state,
.summary-tile,
.home-command-card,
.free-agent-card,
.player-asset-card {
    padding: var(--space-md) !important;
}

.dg-ui-card .dg-ui-card,
.home-command-card .dg-ui-card,
.trade-detail-modal .dg-ui-card {
    background: var(--color-surface-muted) !important;
    border-width: 0 0 0 var(--border-width-default) !important;
    margin-bottom: var(--space-sm) !important;
}

@media (max-width: 700px) {
    .block-container {
        padding-inline:
            max(var(--space-md), env(safe-area-inset-left))
            max(var(--space-md), env(safe-area-inset-right)) !important;
    }

    .dg-application-workspace {
        grid-template-columns: 2.5rem minmax(0, 1fr) !important;
    }

    .dg-ops-rail {
        min-height: 0 !important;
        padding: var(--space-xs) !important;
    }

    .dg-workspace-page.dg-ops-briefing {
        align-content: center !important;
        min-height: 5.25rem !important;
        padding: var(--space-sm) var(--space-md) !important;
    }

    .dg-workspace-page-title{
        font-size: clamp(1.55rem, 8vw, 2.05rem) !important;
        line-height: 0.98 !important;
    }

    .dg-workspace-page-note {
        display: none;
    }

    .st-key-dashboard_orientation_panel .dg-ui-card-list {
        grid-template-columns: minmax(0, 1fr);
    }

    .st-key-dashboard_orientation_panel .dg-ui-card-body,
    .st-key-dashboard_orientation_panel .dg-ui-card-footer {
        font-size: var(--font-size-caption) !important;
    }

    .dg-workspace-context.dg-ops-league-context {
        padding: var(--space-sm) var(--space-md) !important;
    }

    .dg-ui-section-header,
    .section-header {
        display: block !important;
        margin-top: var(--space-lg) !important;
        width: 100% !important;
    }

    .dg-ui-section-title,
    .section-title,
    .team-section-title {
        font-size: clamp(1.05rem, 5.4vw, 1.35rem) !important;
        overflow-wrap: break-word !important;
        white-space: normal !important;
        word-break: normal !important;
    }

    :is(
        .dg-ui-card,
        .dg-ui-callout,
        .dg-ui-empty-state,
        .summary-tile,
        .home-command-card,
        .trade-summary-card,
        .free-agent-card,
        .player-asset-card
    ) {
        box-sizing: border-box !important;
        max-width: 100% !important;
        min-width: 0 !important;
        width: 100% !important;
    }

    :is(
        .summary-tile-grid,
        .home-command-grid,
        .free-agent-summary-grid,
        .explorer-pick-grid
    ) {
        grid-template-columns: minmax(0, 1fr) !important;
        width: 100% !important;
    }

    :is(
        .dg-workspace-page-title,
        .dg-ui-section-title,
        .section-title,
        .dg-ui-card-title,
        .summary-tile-value,
        .trade-summary-title
    ) {
        writing-mode: horizontal-tb !important;
    }
}

@media (max-width: 340px) {
    .dg-workspace-page-title{
        font-size: 1.5rem !important;
    }
}
"""
