"""Final shared hierarchy and mobile rhythm for the Founder Beta surfaces."""

FOUNDER_BETA_CONSISTENCY_CSS = """

.dg-ui-eyebrow{
    font-size: var(--type-page-eyebrow-size) !important;
    line-height: var(--line-height-badge) !important;
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
.home-command-card-value{
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
.trade-summary-value{
    color: var(--color-text-muted) !important;
    font: var(--type-supporting-metadata) !important;
    opacity: var(--opacity-metadata);
}

.dg-ui-card-body,
.trade-summary-rationale{
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

.dg-ui-section-header,
.section-header {
    margin: var(--space-xl) 0 var(--space-md) !important;
}

.dg-ui-card,
.dg-ui-empty-state,
.summary-tile,
.home-command-card,
.trade-summary-card,
.free-agent-card{
    border: var(--border-width-default) solid var(--color-border) !important;
    border-radius: var(--radius-panel) !important;
    box-shadow: var(--shadow-none) !important;
}

.dg-ui-card,
.dg-ui-empty-state,
.summary-tile,
.home-command-card,
.free-agent-card{
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
    /* .block-container padding owned by DESKTOP_EXECUTIVE_LAYOUT_CSS. */

    .st-key-dashboard_orientation_panel .dg-ui-card-list {
        grid-template-columns: minmax(0, 1fr);
    }

    .st-key-dashboard_orientation_panel .dg-ui-card-body,
    .st-key-dashboard_orientation_panel .dg-ui-card-footer {
        font-size: var(--font-size-caption) !important;
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
        .summary-tile-grid,
        .home-command-grid,
        .free-agent-summary-grid,
        .explorer-pick-grid
    ) {
        grid-template-columns: minmax(0, 1fr) !important;
        width: 100% !important;
    }
}

/* Streamlit heading copy/anchor controls are not product affordances. */
[data-testid="stHeaderActionElements"],
[data-testid="stHeadingWithActionElements"] [data-testid="stHeaderActionElements"],
.stHeading [data-testid="stHeaderActionElements"],
.stMarkdown h1 a.anchor-link,
.stMarkdown h2 a.anchor-link,
.stMarkdown h3 a.anchor-link,
.stMarkdown h4 a.anchor-link,
header[data-testid="stHeader"] [data-testid="stHeaderActionElements"] {
    display: none !important;
    pointer-events: none !important;
    visibility: hidden !important;
    width: 0 !important;
    height: 0 !important;
    overflow: hidden !important;
}

.draft-review-pick-top {
    align-items: baseline;
    display: grid;
    gap: var(--space-xs);
    grid-template-columns: auto auto minmax(0, 1fr) auto;
}
.draft-review-reason {
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    color: var(--color-text-muted);
    display: -webkit-box;
    overflow: hidden;
}

@media (max-width: 340px) {
    .dg-ui-section-title,
    .section-title,
    .team-section-title {
        font-size: clamp(1rem, 5vw, 1.2rem) !important;
    }
}
"""
