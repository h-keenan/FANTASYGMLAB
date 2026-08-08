"""Final, shared visual architecture for DynastyGM's reimagined interface."""

INTERFACE_REIMAGINING_CSS = """
/* PR #75 — DynastyGM Interface Reimagining.
   This layer owns presentation only and intentionally follows every legacy rule. */
:root {
    --ops-grid-line: color-mix(in srgb, var(--color-border) 62%, transparent);
    --ops-panel-deep: color-mix(in srgb, var(--color-surface-primary) 86%, var(--color-bg));
    --ops-panel-raised: color-mix(in srgb, var(--color-surface-raised) 78%, var(--color-bg));
    --ops-text-dim: color-mix(in srgb, var(--color-text-muted) 78%, transparent);
    --ops-column: minmax(0, 1fr);
    color-scheme: dark;
}

.stApp {
    background:
        linear-gradient(90deg, transparent 0, transparent calc(100% - 1px), var(--ops-grid-line) 100%),
        linear-gradient(180deg, transparent 0, transparent calc(100% - 1px), var(--ops-grid-line) 100%),
        var(--color-bg) !important;
    background-size: 72px 72px !important;
}

.block-container {
    /* Desktop max-width is owned by the executive layout composition layer. */
    max-width: 1180px !important;
    padding: var(--space-md) var(--space-lg) var(--space-3xl) !important;
}

[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {
    gap: var(--space-sm) !important;
}

.dg-application-workspace :is(button, a, [tabindex]):focus-visible,
.dg-page-shell :is(button, a, [tabindex]):focus-visible {
    box-shadow: var(--focus-ring) !important;
    outline: none !important;
}

/* The workspace is now a football-operations masthead, not a card. */
.dg-application-workspace {
    background: var(--color-bg) !important;
    border: var(--border-width-default) solid var(--color-border-strong) !important;
    border-left: 0 !important;
    border-right: 0 !important;
    border-top: 0 !important;
    box-shadow: var(--shadow-none) !important;
    display: grid !important;
    gap: 0 !important;
    grid-template-columns: minmax(12rem, 0.42fr) minmax(23rem, 1.35fr) minmax(18rem, 0.8fr) !important;
    margin: 0 0 var(--space-md) !important;
    overflow: visible !important;
    padding: 0 !important;
}

.dg-ops-rail {
    align-content: space-between;
    background: var(--color-text-primary);
    color: var(--color-bg);
    display: grid;
    gap: var(--space-lg);
    min-height: 188px;
    padding: var(--space-lg);
}

.dg-ops-brand {
    align-items: center;
    display: flex;
    gap: var(--space-sm);
}

.dg-ops-brand span {
    align-items: center;
    background: var(--color-bg);
    color: var(--color-text-primary);
    display: inline-flex;
    font-size: var(--font-size-card-title);
    font-weight: var(--font-weight-display);
    height: var(--space-2xl);
    justify-content: center;
    width: var(--space-2xl);
}

.dg-ops-brand strong,
.dg-ops-rail-copy {
    font-size: var(--font-size-caption);
    font-weight: var(--font-weight-display);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}

.dg-ops-rail-copy {
    color: color-mix(in srgb, var(--color-bg) 68%, transparent);
    max-width: 14ch;
}

.dg-ops-system-status {
    align-items: center;
    display: flex;
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-button);
    gap: var(--space-xs);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}

.dg-ops-system-status span {
    background: var(--color-success);
    height: var(--space-sm);
    width: var(--space-sm);
}

.dg-workspace-page.dg-ops-briefing {
    align-content: end;
    background: var(--ops-panel-deep);
    border-right: var(--border-width-default) solid var(--color-border-strong);
    display: grid;
    min-height: 188px;
    padding: var(--space-xl);
}

.dg-workspace-page-kicker {
    color: var(--color-information) !important;
    font-size: var(--font-size-badge) !important;
}

.dg-workspace-page-title {
    font-size: clamp(2.4rem, 5vw, 5rem) !important;
    font-weight: var(--font-weight-display) !important;
    letter-spacing: -0.055em !important;
    line-height: 0.86 !important;
    margin: var(--space-md) 0 0 !important;
    max-width: 12ch;
    overflow-wrap: anywhere;
    text-transform: uppercase;
}

.dg-workspace-page-note {
    color: var(--color-text-secondary) !important;
    font-size: var(--font-size-body) !important;
    line-height: 1.35 !important;
    margin-top: var(--space-lg) !important;
    max-width: 68ch !important;
}

.dg-workspace-context.dg-ops-league-context {
    align-content: end;
    align-items: end;
    background: var(--color-surface-muted) !important;
    border: 0 !important;
    border-radius: var(--radius-none) !important;
    display: grid;
    gap: var(--space-md);
    grid-template-columns: var(--space-3xl) minmax(0, 1fr);
    padding: var(--space-xl) !important;
}

.dg-workspace-avatar {
    border: var(--border-width-default) solid var(--color-border-strong) !important;
    border-radius: var(--radius-none) !important;
}

.dg-workspace-platform {
    color: var(--color-text-muted) !important;
}

.dg-workspace-league {
    font-size: var(--font-size-section-title) !important;
    font-weight: var(--font-weight-display) !important;
    letter-spacing: -0.02em;
    overflow-wrap: anywhere;
    text-transform: uppercase;
}

.dg-workspace-team,
.dg-workspace-sync {
    font-family: ui-monospace, "SFMono-Regular", Consolas, monospace;
}

.dg-workspace-metrics.dg-ops-telemetry {
    border-top: var(--border-width-default) solid var(--color-border-strong);
    display: grid !important;
    gap: 0 !important;
    grid-column: 1 / -1 !important;
    grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
}

.dg-ops-telemetry .dg-workspace-metric {
    background: var(--color-surface-primary) !important;
    border: 0 !important;
    border-right: var(--border-width-default) solid var(--color-border) !important;
    border-radius: var(--radius-none) !important;
    padding: var(--space-md) var(--space-lg) !important;
}

.dg-ops-telemetry .dg-workspace-metric:last-child {
    border-right: 0 !important;
}

.dg-workspace-metric-value {
    font-family: ui-monospace, "SFMono-Regular", Consolas, monospace;
    font-size: var(--font-size-section-title) !important;
    font-weight: var(--font-weight-display) !important;
}

/* Secondary page briefs are compact assignment rails beneath the masthead. */
.dg-page-shell {
    align-items: stretch !important;
    background: var(--color-surface-primary) !important;
    border: 0 !important;
    border-bottom: var(--border-width-default) solid var(--color-border-strong) !important;
    border-left: var(--border-width-semantic) solid var(--color-information) !important;
    border-radius: var(--radius-none) !important;
    box-shadow: var(--shadow-none) !important;
    display: grid !important;
    gap: 0 !important;
    grid-template-columns: 4.5rem minmax(0, 1fr) !important;
    margin: 0 0 var(--space-lg) !important;
    padding: 0 !important;
}

.dg-page-glyph {
    align-items: center !important;
    background: var(--color-text-primary) !important;
    border: 0 !important;
    border-radius: var(--radius-none) !important;
    color: var(--color-bg) !important;
    display: flex !important;
    font-family: ui-monospace, "SFMono-Regular", Consolas, monospace;
    font-size: var(--font-size-section-title) !important;
    font-weight: var(--font-weight-display) !important;
    justify-content: center !important;
    min-height: 100% !important;
}

.dg-page-copy {
    padding: var(--space-md) var(--space-lg) !important;
}

.dg-page-kicker {
    color: var(--color-information) !important;
    font-size: var(--font-size-badge) !important;
    letter-spacing: var(--letter-spacing-badge) !important;
    text-transform: uppercase;
}

.dg-page-title {
    color: var(--color-text-primary) !important;
    font-size: clamp(1.35rem, 2.2vw, 2rem) !important;
    font-weight: var(--font-weight-display) !important;
    letter-spacing: -0.035em !important;
    line-height: 1 !important;
    margin: var(--space-xs) 0 0 !important;
    text-transform: uppercase;
}

.dg-page-subtitle {
    color: var(--color-text-muted) !important;
    font-size: var(--font-size-caption) !important;
    margin-top: var(--space-sm) !important;
    max-width: 86ch;
}

/* Shared content rhythm: slabs and data rows instead of floating SaaS cards. */
.dg-ui-section-header,
.section-header,
.waiver-section-header .dg-ui-section-header {
    align-items: end;
    border-bottom: var(--border-width-default) solid var(--color-border-strong) !important;
    border-left: 0 !important;
    display: grid !important;
    gap: var(--space-xs) !important;
    grid-template-columns: minmax(0, 1fr) auto;
    margin: var(--space-xl) 0 var(--space-sm) !important;
    padding: 0 0 var(--space-sm) !important;
}

.dg-ui-eyebrow,
.section-kicker,
.waiver-card-label,
.trade-card-kicker,
.dg-intelligence-group {
    font-family: ui-monospace, "SFMono-Regular", Consolas, monospace;
}

.dg-ui-section-title,
.section-title {
    font-size: clamp(1.15rem, 2vw, 1.65rem) !important;
    font-weight: var(--font-weight-display) !important;
    letter-spacing: -0.025em !important;
    line-height: 1 !important;
    text-transform: uppercase;
}

.dg-ui-card,
.dg-ui-callout,
.dg-ui-empty-state,
.summary-tile,
.home-command-card,
.trade-idea-card,
.free-agent-card,
.explorer-pick-card,
.dg-intelligence-item {
    border-radius: var(--radius-none) !important;
    box-shadow: var(--shadow-none) !important;
}

.summary-tile-grid,
.home-command-grid,
.free-agent-summary-grid,
.explorer-pick-grid {
    gap: var(--space-xs) !important;
}

.summary-tile,
.home-command-card {
    min-height: 0 !important;
    padding: var(--space-md) !important;
}

.summary-tile-value,
.home-command-card-value,
.trade-delta,
.waiver-metric-row dd,
.explorer-pick-card__metrics dd {
    font-family: ui-monospace, "SFMono-Regular", Consolas, monospace;
    font-variant-numeric: tabular-nums;
}

/* Dashboard: an executive briefing with an asymmetric decision board. */
.home-command-shell {
    display: grid;
    gap: var(--space-sm) !important;
}

.home-command-hero {
    background: var(--color-surface-primary) !important;
    border: 0 !important;
    border-bottom: var(--border-width-default) solid var(--color-border-strong) !important;
    border-left: var(--border-width-semantic) solid var(--color-information) !important;
    border-radius: var(--radius-none) !important;
    display: grid !important;
    grid-template-columns: 5rem minmax(0, 1fr) !important;
    min-height: 0 !important;
    padding: var(--space-lg) !important;
}

.home-hero-logo {
    border-radius: var(--radius-none) !important;
    filter: grayscale(1);
}

.home-command-team {
    font-size: clamp(1.8rem, 4vw, 3.4rem) !important;
    font-weight: var(--font-weight-display) !important;
    letter-spacing: -0.045em !important;
    line-height: 0.95 !important;
    text-transform: uppercase;
}

.home-hero-stats {
    border-top: var(--border-width-default) solid var(--color-border);
    gap: 0 !important;
    grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
    margin-top: var(--space-md) !important;
}

.home-hero-stat {
    background: transparent !important;
    border: 0 !important;
    border-right: var(--border-width-default) solid var(--color-border) !important;
    padding: var(--space-sm) var(--space-md) !important;
}

.home-action-center-label,
.home-league-pulse-label {
    border-bottom: var(--border-width-default) solid var(--color-border-strong) !important;
    color: var(--color-text-primary) !important;
    font-size: var(--font-size-section-title) !important;
    letter-spacing: -0.02em !important;
    margin-top: var(--space-xl) !important;
    padding: 0 0 var(--space-sm) !important;
}

.home-command-grid {
    grid-template-columns: repeat(12, minmax(0, 1fr)) !important;
}

.home-command-card {
    border: var(--border-width-default) solid var(--color-border) !important;
    border-top: var(--border-width-semantic) solid var(--color-border-strong) !important;
    grid-column: span 4;
}

.home-command-card:first-child,
.home-command-card-wide {
    grid-column: span 8 !important;
}

.home-command-card-value {
    font-size: clamp(1.15rem, 2vw, 1.7rem) !important;
}

/* Trade Hub: two-sided negotiation briefs with values as the center rail. */
main:has(.dg-page-shell--trade-hub) .trade-idea-card {
    background: var(--ops-panel-deep) !important;
    border: var(--border-width-default) solid var(--color-border-strong) !important;
    border-left: var(--border-width-semantic) solid var(--color-information) !important;
    margin: 0 0 var(--space-sm) !important;
    padding: var(--space-lg) !important;
}

main:has(.dg-page-shell--trade-hub) .trade-card-top {
    align-items: end !important;
    border-bottom: var(--border-width-default) solid var(--color-border);
    display: grid !important;
    gap: var(--space-md) !important;
    grid-template-columns: minmax(0, 1.45fr) minmax(12rem, 0.55fr) !important;
    padding-bottom: var(--space-md) !important;
}

main:has(.dg-page-shell--trade-hub) .trade-card-title {
    font-size: clamp(1.35rem, 2.7vw, 2.3rem) !important;
    font-weight: var(--font-weight-display) !important;
    letter-spacing: -0.04em !important;
    line-height: 0.96 !important;
    text-transform: uppercase;
}

main:has(.dg-page-shell--trade-hub) .trade-card-focus-row,
main:has(.dg-page-shell--trade-hub) .trade-value-ledger {
    gap: 0 !important;
    grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
}

main:has(.dg-page-shell--trade-hub) .trade-card-focus-item,
main:has(.dg-page-shell--trade-hub) .trade-value-ledger > * {
    background: var(--color-surface-muted) !important;
    border: 0 !important;
    border-right: var(--border-width-default) solid var(--color-border) !important;
    padding: var(--space-md) !important;
}

main:has(.dg-page-shell--trade-hub) .trade-side {
    background: transparent !important;
    border: 0 !important;
}

/* Waivers: a compact scouting board with action and evidence aligned. */
main:has(.waiver-section-header) .free-agent-card {
    background: var(--ops-panel-deep) !important;
    border: var(--border-width-default) solid var(--color-border) !important;
    border-left: var(--border-width-semantic) solid var(--color-border-strong) !important;
    margin-bottom: var(--space-xs) !important;
    padding: var(--space-md) !important;
}

main:has(.waiver-section-header) .waiver-decision-summary {
    background: var(--color-surface-muted) !important;
    border: 0 !important;
    border-left: var(--border-width-semantic) solid var(--color-opportunity) !important;
    padding: var(--space-sm) var(--space-md) !important;
}

main:has(.waiver-section-header) .waiver-context-grid {
    gap: 0 !important;
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
}

main:has(.waiver-section-header) .waiver-context-block {
    background: transparent !important;
    border: 0 !important;
    border-right: var(--border-width-default) solid var(--color-border) !important;
    padding: var(--space-md) !important;
}

main:has(.waiver-section-header) .waiver-metric-row {
    background: var(--color-bg) !important;
    border: var(--border-width-default) solid var(--color-border) !important;
    gap: 0 !important;
}

main:has(.waiver-section-header) .waiver-metric-row > div {
    border-right: var(--border-width-default) solid var(--color-border);
    padding: var(--space-sm);
}

/* Explorer: a search terminal and dense asset database. */
main:has(.dg-page-shell--players) [data-testid="stTextInput"],
main:has(.dg-page-shell--players) [data-testid="stSelectbox"],
main:has(.dg-page-shell--players) [data-testid="stMultiSelect"],
main:has(.dg-page-shell--players) [data-testid="stButtonGroup"] {
    background: var(--color-surface-muted);
    border-top: var(--border-width-default) solid var(--color-border);
    padding: var(--space-sm);
}

main:has(.dg-page-shell--players) .scan-card,
main:has(.dg-page-shell--players) .compact-player-row,
main:has(.dg-page-shell--players) .player-asset-card {
    background: var(--ops-panel-deep) !important;
    border-bottom: var(--border-width-default) solid var(--color-border) !important;
    border-left: var(--border-width-semantic) solid var(--color-border-strong) !important;
    margin: 0 !important;
}

main:has(.dg-page-shell--players) .explorer-pick-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
}

.explorer-pick-card__title {
    font-size: var(--font-size-section-title) !important;
    text-transform: uppercase;
}

/* League Intelligence: an overnight brief on a continuous timeline. */
.dg-intelligence-group {
    border-bottom: var(--border-width-default) solid var(--color-border-strong);
    color: var(--color-text-primary) !important;
    font-size: var(--font-size-badge) !important;
    letter-spacing: var(--letter-spacing-badge);
    margin: var(--space-xl) 0 0 !important;
    padding: 0 0 var(--space-sm) !important;
    text-transform: uppercase;
}

.dg-intelligence-item {
    background: var(--ops-panel-deep) !important;
    border: 0 !important;
    border-bottom: var(--border-width-default) solid var(--color-border) !important;
    border-left: var(--border-width-semantic) solid var(--color-information) !important;
    display: grid;
    gap: var(--space-sm);
    grid-template-columns: minmax(12rem, 0.65fr) minmax(0, 1.35fr);
    margin: 0 !important;
    padding: var(--space-md) !important;
}

.dg-intelligence-item__header,
.dg-intelligence-item__player {
    grid-column: 1;
}

.dg-intelligence-item__headline {
    font-size: var(--font-size-section-title) !important;
    line-height: 1.05 !important;
    text-transform: uppercase;
}

.dg-intelligence-item__meta,
.dg-intelligence-item__summary,
.dg-intelligence-item__signals {
    grid-column: 2;
}

.dg-intelligence-item__summary {
    color: var(--color-text-secondary) !important;
    font-size: var(--font-size-body) !important;
    margin: 0 !important;
}

/* Native controls and dialogs belong to the same operations system. */
.stButton > button,
.stDownloadButton > button,
[data-testid="stPopover"] > button,
[data-baseweb="select"] > div,
[data-baseweb="input"] > div,
[data-baseweb="textarea"] > div {
    background: var(--color-surface-primary) !important;
    border: var(--border-width-default) solid var(--color-border-strong) !important;
    border-radius: var(--radius-none) !important;
    box-shadow: var(--shadow-none) !important;
}

.stButton > button:hover,
.stDownloadButton > button:hover,
[data-testid="stPopover"] > button:hover {
    background: var(--color-text-primary) !important;
    color: var(--color-bg) !important;
}

div[data-testid="stDialog"] div[role="dialog"] {
    border: var(--border-width-default) solid var(--color-text-secondary) !important;
    border-radius: var(--radius-none) !important;
    box-shadow: var(--shadow-overlay) !important;
}

div[data-testid="stExpander"] {
    border-left: var(--border-width-semantic) solid var(--color-border-strong) !important;
}

[data-testid="stAlert"] {
    border-left-width: var(--border-width-semantic) !important;
}

.dg-build-identity {
    color: var(--color-text-muted);
    font-family: ui-monospace, "SFMono-Regular", Consolas, monospace;
    font-size: var(--font-size-badge);
    letter-spacing: var(--letter-spacing-badge);
    margin-top: var(--space-sm);
    text-align: right;
    text-transform: uppercase;
}

/* Mobile remains dense but changes from multi-column command room to scan rail. */
@media (max-width: 900px) {
    .block-container {
        padding:
            var(--space-sm)
            max(var(--space-sm), env(safe-area-inset-right))
            max(var(--space-3xl), env(safe-area-inset-bottom))
            max(var(--space-sm), env(safe-area-inset-left)) !important;
    }

    .dg-application-workspace {
        grid-template-columns: 4rem minmax(0, 1fr) !important;
    }

    .dg-ops-rail {
        align-content: start;
        min-height: 0;
        padding: var(--space-sm);
    }

    .dg-ops-brand {
        display: grid;
    }

    .dg-ops-brand strong,
    .dg-ops-rail-copy,
    .dg-ops-system-status {
        display: none;
    }

    .dg-workspace-page.dg-ops-briefing {
        border-right: 0;
        min-height: 144px;
        padding: var(--space-md);
    }

    .dg-workspace-page-title {
        font-size: clamp(2.05rem, 11vw, 3.25rem) !important;
        max-width: 100%;
    }

    .dg-workspace-page-note {
        font-size: var(--font-size-caption) !important;
        margin-top: var(--space-sm) !important;
    }

    .dg-workspace-context.dg-ops-league-context {
        border-top: var(--border-width-default) solid var(--color-border);
        grid-column: 1 / -1;
        padding: var(--space-md) !important;
    }

    .dg-workspace-metrics.dg-ops-telemetry {
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    }

    .dg-ops-telemetry .dg-workspace-metric:nth-child(2) {
        border-right: 0 !important;
    }

    .dg-ops-telemetry .dg-workspace-metric:nth-child(-n + 2) {
        border-bottom: var(--border-width-default) solid var(--color-border) !important;
    }

    .dg-page-shell {
        grid-template-columns: 3.25rem minmax(0, 1fr) !important;
    }

    .dg-page-copy {
        padding: var(--space-sm) var(--space-md) !important;
    }

    .home-command-hero {
        grid-template-columns: 3.5rem minmax(0, 1fr) !important;
        padding: var(--space-md) !important;
    }

    .home-hero-stats {
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    }

    .home-command-grid {
        grid-template-columns: 1fr !important;
    }

    .home-command-card,
    .home-command-card:first-child,
    .home-command-card-wide {
        grid-column: 1 !important;
    }

    main:has(.dg-page-shell--trade-hub) .trade-card-top,
    .dg-intelligence-item {
        grid-template-columns: 1fr !important;
    }

    .dg-intelligence-item__header,
    .dg-intelligence-item__player,
    .dg-intelligence-item__meta,
    .dg-intelligence-item__summary,
    .dg-intelligence-item__signals {
        grid-column: 1;
    }

    main:has(.waiver-section-header) .waiver-context-grid,
    main:has(.dg-page-shell--players) .explorer-pick-grid {
        grid-template-columns: 1fr !important;
    }

    main:has(.waiver-section-header) .waiver-context-block {
        border-bottom: var(--border-width-default) solid var(--color-border) !important;
        border-right: 0 !important;
    }

    .dg-build-identity {
        text-align: left;
    }
}

@media (prefers-reduced-motion: reduce) {
    .dg-application-workspace *,
    .dg-page-shell *,
    .home-command-shell *,
    .trade-idea-card *,
    .free-agent-card *,
    .dg-intelligence-item * {
        animation: none !important;
        scroll-behavior: auto !important;
        transition: none !important;
    }
}
"""
