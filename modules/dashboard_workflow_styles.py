"""Token-backed styles for the five-zone Dashboard briefing."""

DASHBOARD_WORKFLOW_CSS = """
<style>
.st-key-dashboard_workflow {
    contain: layout;
    display: flex;
    flex-direction: column;
    gap: var(--space-lg);
    width: 100%;
}

.st-key-dashboard_page_context,
div[class*="st-key-dashboard_page_context"] {
    display: flex !important;
    flex-direction: column !important;
    flex-wrap: nowrap !important;
    gap: var(--space-xs);
    margin: 0 0 var(--space-sm);
    max-width: 100%;
    min-width: 0;
    width: 100%;
}

div[class*="st-key-dashboard_page_context"] [data-testid="stVerticalBlock"],
div[class*="st-key-dashboard_page_context"] [data-testid="stElementContainer"],
div[class*="st-key-dashboard_page_context"] [data-testid="element-container"] {
    display: block !important;
    height: auto !important;
    max-width: 100%;
    min-height: 0 !important;
    min-width: 0;
    overflow: visible !important;
    position: static !important;
    width: 100%;
}

.dg-dashboard-page-context {
    display: flex;
    flex-direction: column;
    gap: var(--space-2xs);
    max-width: 100%;
    min-width: 0;
    padding-bottom: 0;
    position: relative;
    width: 100%;
}

.dg-dashboard-page-identity,
.dg-dashboard-page-meta {
    color: var(--color-text-muted);
    font: var(--type-supporting-metadata);
    letter-spacing: var(--letter-spacing-badge);
    line-height: var(--line-height-caption);
    overflow-wrap: anywhere;
    text-align: left;
}

.dg-dashboard-page-kicker {
    color: var(--color-text-muted);
    font: var(--type-supporting-metadata);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}

.st-key-dashboard_workflow > div {
    max-width: none;
    width: 100%;
}

.st-key-dashboard_workflow .dg-ui-section-header {
    margin-bottom: 0;
}

.st-key-dashboard_workflow .dg-ui-section-title--glyph .dg-glyph {
    height: 1.4rem;
    width: 1.4rem;
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

div[class*="st-key-dashboard_workflow"] [class*="load_deferred_section_ready__dashboard_what_changed"] button {
    min-height: var(--touch-target-min) !important;
    width: auto !important;
    white-space: nowrap !important;
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
        gap: var(--space-lg);
    }

    @media (min-width: 1440px) {
        .st-key-dashboard_workflow {
            gap: var(--space-lg) !important;
        }
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

div[class*="st-key-dashboard_page_context"] [data-testid="stMarkdown"] {
    margin: 0 !important;
}

div[class*="st-key-dashboard_page_context"] [data-testid="stButton"] {
    margin: 0 !important;
    max-width: 100%;
    min-width: 0;
    width: auto;
}

div[class*="st-key-dashboard_page_context"] [data-testid="stButton"] > button {
    color: var(--color-text-muted) !important;
    font: var(--type-supporting-metadata) !important;
    height: auto !important;
    justify-content: flex-start !important;
    line-height: var(--line-height-caption) !important;
    max-width: 100% !important;
    min-height: var(--touch-target-min) !important;
    min-width: 0 !important;
    overflow-wrap: anywhere !important;
    padding: 0 !important;
    text-align: left !important;
    white-space: normal !important;
    width: auto !important;
}

div[class*="st-key-dashboard_page_context"] [data-testid="stSelectbox"] {
    margin: 0 0 var(--space-2xs) !important;
    max-width: min(100%, 22rem);
    min-width: 0;
    width: 100%;
}

div[class*="st-key-dashboard_page_context"] [data-testid="stSelectbox"] label {
    color: var(--color-text-muted) !important;
    font: var(--type-supporting-metadata) !important;
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase !important;
}

@media (max-width: 760px) {
    .st-key-dashboard_page_context,
    div[class*="st-key-dashboard_page_context"] {
        gap: var(--space-2xs);
        margin: 0 0 var(--space-md);
    }
}

@media (max-width: 700px) {
    div[class*="st-key-dashboard_context_pair"] [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: column !important;
        flex-wrap: nowrap !important;
        gap: var(--space-md) !important;
        width: 100% !important;
    }
    div[class*="st-key-dashboard_context_pair"] [data-testid="stHorizontalBlock"] > div,
    div[class*="st-key-dashboard_context_pair"] [data-testid="column"] {
        flex: 1 1 auto !important;
        max-width: 100% !important;
        min-width: 0 !important;
        width: 100% !important;
    }
    div[class*="st-key-dashboard_league_insights"] .home-command-card-value,
    div[class*="st-key-dashboard_league_insights"] .home-command-card-note,
    div[class*="st-key-dashboard_team_snapshot"] .summary-tile-value,
    div[class*="st-key-dashboard_team_snapshot"] .summary-tile-label {
        overflow-wrap: anywhere;
        white-space: normal !important;
    }

    .st-key-dashboard_workflow {
        gap: var(--space-md);
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
    box-sizing: border-box;
    contain: layout;
    margin: 0.35rem 0 0.75rem;
    min-height: 18.5rem;
    padding: var(--space-sm) var(--space-md);
}
.dashboard-hydrate-skeleton {
    display: grid;
    gap: var(--space-sm);
    margin-top: var(--space-md);
}
.dashboard-hydrate-skeleton-row {
    background: var(--surface-2, var(--color-surface-muted));
    border-radius: var(--radius-panel);
    height: 4.5rem;
    min-height: 4.5rem;
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

div[class*="st-key-dashboard_team_snapshot"] .summary-tile-grid,
div[class*="st-key-dashboard_team_snapshot"] .summary-tile-grid-compact {
    background: var(--border-standard);
    border: var(--border-width-default) solid var(--border-standard);
    border-radius: var(--radius-panel);
    display: grid;
    gap: var(--border-width-default);
    grid-template-columns: 1fr 1fr;
    overflow: hidden;
}
/* Six related roster metrics read as one grouped panel with hairline dividers
   (the grid gap above shows the container background through) rather than six
   separately-bordered cards — each metric keeps its own tone accent via the
   existing dg-card-* top-strip, just without a competing full box border. */
div[class*="st-key-dashboard_team_snapshot"] .summary-tile {
    background: var(--surface-1);
    border: 0;
    border-radius: 0;
    box-shadow: none;
    margin: 0;
    min-height: 0;
    padding: var(--space-xs) var(--space-sm);
}
div[class*="st-key-dashboard_team_snapshot"] .summary-tile-unavailable {
    opacity: 0.55;
}
div[class*="st-key-dashboard_team_snapshot"] .summary-tile-unavailable .summary-tile-value {
    color: var(--color-text-muted);
    font-weight: var(--font-weight-body);
}
div[class*="st-key-dashboard_team_snapshot"] .summary-tile-risk,
div[class*="st-key-dashboard_team_snapshot"] .dg-card-warning {
    grid-column: 1 / -1;
}
div[class*="st-key-dashboard_league_insights"] {
    min-width: 0;
}
div[class*="st-key-dashboard_league_insights"] .home-command-grid {
    grid-template-columns: minmax(0, 1fr);
    width: 100%;
}
div[class*="st-key-dashboard_league_insights"] .home-command-card,
div[class*="st-key-dashboard_league_insights"] .home-command-card-wide,
div[class*="st-key-dashboard_league_insights"] .home-command-card-primary,
div[class*="st-key-dashboard_league_insights"] .home-command-card-secondary {
    grid-column: 1 / -1;
    max-width: none;
    min-width: 0;
    width: 100%;
}
div[class*="st-key-dashboard_league_insights"] .dg-football-asset,
div[class*="st-key-dashboard_league_insights"] .scan-card-compact .scan-card-main {
    grid-template-columns: auto minmax(0, 1fr) auto;
}
div[class*="st-key-dashboard_league_insights"] .dg-football-asset__name,
div[class*="st-key-dashboard_league_insights"] .scan-card-name,
div[class*="st-key-dashboard_league_insights"] .compact-player-name,
div[class*="st-key-dashboard_league_insights"] .home-command-card-value,
div[class*="st-key-dashboard_league_insights"] .dg-football-prestige {
    max-width: 100%;
    min-width: 0;
    overflow: visible;
    overflow-wrap: break-word;
    text-overflow: clip;
    white-space: normal;
    word-break: normal;
}
.dg-recap-teaser {
    margin: 0 0 var(--space-md);
    max-width: 36rem;
}
@media (min-width: 1024px) {
    div[class*="st-key-dashboard_team_snapshot"] .summary-tile-grid,
    div[class*="st-key-dashboard_team_snapshot"] .summary-tile-grid-compact {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    div[class*="st-key-dashboard_league_insights"] .home-command-grid {
        grid-template-columns: minmax(20rem, 1fr);
    }
    div[class*="st-key-dashboard_league_insights"] .home-command-card,
    div[class*="st-key-dashboard_league_insights"] .home-command-card-wide,
    div[class*="st-key-dashboard_league_insights"] .home-command-card-primary,
    div[class*="st-key-dashboard_league_insights"] .home-command-card-secondary {
        min-width: min(100%, 20rem);
    }
    div[class*="st-key-dashboard_league_insights"] .dg-football-asset,
    div[class*="st-key-dashboard_league_insights"] .scan-card-compact .scan-card-main {
        grid-template-columns: auto minmax(0, 1fr);
    }
    div[class*="st-key-dashboard_league_insights"] .dg-football-asset__value,
    div[class*="st-key-dashboard_league_insights"] .scan-card-score {
        grid-column: 2;
        justify-self: start;
        text-align: left;
    }
}
@media (min-width: 1440px) {
    div[class*="st-key-dashboard_team_snapshot"] .summary-tile-grid,
    div[class*="st-key-dashboard_team_snapshot"] .summary-tile-grid-compact {
        grid-template-columns: repeat(5, minmax(0, 1fr));
    }
    div[class*="st-key-dashboard_team_snapshot"] .summary-tile-risk,
    div[class*="st-key-dashboard_team_snapshot"] .dg-card-warning {
        grid-column: auto;
    }
}
</style>
"""
