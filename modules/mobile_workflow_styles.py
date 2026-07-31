"""Final mobile workflow corrections for the shared application workspace."""

MOBILE_WORKFLOW_CSS = """
/* Mobile workflow layer: presentation only, loaded after the shared identity. */
@media (max-width: 700px) {
    main:has(.home-command-shell) .dg-application-workspace {
        grid-template-columns: 2.75rem minmax(0, 1fr) !important;
        margin-bottom: var(--space-sm) !important;
    }

    main:has(.home-command-shell) .dg-ops-rail {
        min-height: 0 !important;
        padding: var(--space-xs) !important;
    }

    main:has(.home-command-shell) .dg-ops-brand span {
        font-size: var(--font-size-caption) !important;
        height: var(--touch-target-min) !important;
        width: 100% !important;
    }

    main:has(.home-command-shell) .dg-workspace-page.dg-ops-briefing {
        align-content: center !important;
        min-height: 5.5rem !important;
        padding: var(--space-sm) var(--space-md) !important;
    }

    main:has(.home-command-shell) .dg-workspace-page-kicker {
        white-space: nowrap;
    }

    main:has(.home-command-shell) .dg-workspace-page-title {
        font-size: clamp(1.75rem, 9vw, 2.35rem) !important;
        line-height: 0.95 !important;
        margin-top: var(--space-xs) !important;
        overflow-wrap: normal !important;
        word-break: normal !important;
    }

    main:has(.home-command-shell) .dg-workspace-page-note {
        display: none;
    }

    main:has(.home-command-shell) .dg-workspace-context.dg-ops-league-context {
        align-items: center !important;
        gap: var(--space-sm) !important;
        grid-template-columns: var(--touch-target-min) minmax(0, 1fr) !important;
        padding: var(--space-sm) var(--space-md) !important;
    }

    main:has(.home-command-shell) .dg-workspace-avatar {
        height: var(--touch-target-min) !important;
        width: var(--touch-target-min) !important;
    }

    main:has(.home-command-shell) .dg-workspace-league {
        font-size: var(--font-size-card-title) !important;
        line-height: 1.05 !important;
        overflow-wrap: break-word !important;
    }

    main:has(.home-command-shell) :is(.dg-workspace-team, .dg-workspace-sync) {
        display: none;
    }

    main:has(.home-command-shell) .dg-workspace-metrics.dg-ops-telemetry {
        grid-template-columns: repeat(4, minmax(6.5rem, 1fr)) !important;
        overflow-x: auto !important;
        overscroll-behavior-inline: contain;
        scrollbar-width: thin;
    }

    main:has(.home-command-shell) .dg-ops-telemetry .dg-workspace-metric {
        border-bottom: 0 !important;
        border-right: var(--border-width-default) solid var(--color-border) !important;
        padding: var(--space-xs) var(--space-sm) !important;
    }

    main:has(.home-command-shell) .dg-workspace-metric-label {
        white-space: nowrap;
    }

    main:has(.home-command-shell) .dg-workspace-metric-value {
        font-size: var(--font-size-body) !important;
        line-height: 1.1 !important;
        overflow-wrap: normal !important;
        word-break: normal !important;
    }

    main:has(.home-command-shell) .dg-workspace-metric-note {
        display: none;
    }

    .home-command-shell,
    .home-command-hero,
    .home-command-grid,
    .home-command-card {
        box-sizing: border-box !important;
        max-width: 100% !important;
        min-width: 0 !important;
        width: 100% !important;
    }

    .home-command-shell {
        display: block !important;
    }

    .home-command-hero {
        gap: 0 !important;
        grid-template-columns: minmax(0, 1fr) !important;
        padding: var(--space-sm) var(--space-md) !important;
    }

    .home-command-hero > div:last-child {
        flex: 1 1 auto !important;
        min-width: 0 !important;
        width: 100% !important;
    }

    .home-command-team {
        font-size: clamp(1.35rem, 7vw, 1.75rem) !important;
        line-height: 1 !important;
        overflow-wrap: normal !important;
        white-space: normal !important;
        word-break: normal !important;
        writing-mode: horizontal-tb !important;
    }

    main:has(.home-command-shell) .home-command-meta {
        font-size: var(--font-size-caption) !important;
        line-height: 1.3 !important;
        margin-top: var(--space-xs) !important;
        max-width: 42ch;
    }

    main:has(.home-command-shell) .home-hero-stats {
        display: grid !important;
        grid-template-columns: repeat(4, minmax(6.25rem, 1fr)) !important;
        margin-top: var(--space-sm) !important;
        overflow-x: auto !important;
        overscroll-behavior-inline: contain;
    }

    main:has(.home-command-shell) .home-hero-stat {
        border-bottom: 0 !important;
        min-width: 0 !important;
        padding: var(--space-xs) var(--space-sm) !important;
    }

    main:has(.home-command-shell) :is(
        .home-hero-stat-label,
        .home-hero-stat-value,
        .dg-ui-section-title,
        .dg-ui-section-subtitle
    ) {
        overflow-wrap: normal !important;
        word-break: normal !important;
    }

    main:has(.home-command-shell) .dg-ui-section-header {
        display: block !important;
        margin-bottom: var(--space-sm) !important;
        min-width: 0 !important;
        width: 100% !important;
    }

    main:has(.home-command-shell) .dg-ui-section-header-copy {
        min-width: 0 !important;
        width: 100% !important;
    }

    main:has(.home-command-shell) .dg-ui-section-title {
        font-size: clamp(1.35rem, 7vw, 1.8rem) !important;
        white-space: nowrap !important;
        word-break: keep-all !important;
    }

    .home-command-grid {
        display: grid !important;
        gap: var(--space-xs) !important;
        grid-template-columns: minmax(0, 1fr) !important;
    }

    .home-command-card,
    .home-command-card:first-child,
    .home-command-card-wide {
        flex: 1 1 100% !important;
        grid-column: 1 / -1 !important;
        min-width: 0 !important;
        padding: var(--space-sm) !important;
    }

    .home-command-card :is(
        .home-command-card-label,
        .home-command-card-value,
        .home-command-card-note,
        .compact-player-name,
        .compact-player-meta,
        .player-asset-card__name,
        .player-asset-card__meta
    ) {
        max-width: 100% !important;
        min-width: 0 !important;
        overflow-wrap: break-word !important;
        white-space: normal !important;
        word-break: normal !important;
        writing-mode: horizontal-tb !important;
    }

    main:has(.home-command-shell) .home-quick-action-note {
        max-width: 40ch;
    }
}

@media (max-width: 380px) {
    main:has(.home-command-shell) .dg-workspace-page-kicker {
        font-size: 0.62rem !important;
    }

    main:has(.home-command-shell) .dg-workspace-page-title {
        font-size: 1.7rem !important;
    }
}

.dg-page-context {
    border-bottom: var(--border-width-default) solid var(--color-border);
    margin: 0 0 var(--space-sm);
    padding: 0 0 var(--space-sm);
}

.dg-page-context .dg-page-meta {
    margin: 0;
}
"""
