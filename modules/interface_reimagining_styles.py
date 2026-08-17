"""Final, shared visual architecture for DynastyGM's reimagined interface."""

INTERFACE_REIMAGINING_CSS = """

:root {
    --ops-panel-deep: color-mix(in srgb, var(--color-surface-primary) 86%, var(--color-bg));
    --ops-panel-raised: color-mix(in srgb, var(--color-surface-raised) 78%, var(--color-bg));
    --ops-text-dim: color-mix(in srgb, var(--color-text-muted) 78%, transparent);
    --ops-column: minmax(0, 1fr);
    color-scheme: dark;
}

.stApp {
    --ops-grid-line: color-mix(in srgb, var(--color-border) 62%, transparent);
    background:
        linear-gradient(90deg, transparent 0, transparent calc(100% - 1px), var(--ops-grid-line) 100%),
        linear-gradient(180deg, transparent 0, transparent calc(100% - 1px), var(--ops-grid-line) 100%),
        var(--color-bg) !important;
    background-size: 72px 72px !important;
}

[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {
    gap: var(--space-sm) !important;
}

.dg-page-shell :is(button, a, [tabindex]):focus-visible{
    box-shadow: var(--focus-ring) !important;
    outline: none !important;
}

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
.dg-ui-empty-state,
.summary-tile,
.home-command-card,
.trade-idea-card,
.free-agent-card,
.explorer-pick-card,
.dg-intelligence-item{
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
.waiver-metric-row dd {
    font-family: ui-monospace, "SFMono-Regular", Consolas, monospace;
    font-variant-numeric: tabular-nums;
}

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

main:has(.dg-page-shell--players) [data-testid="stTextInput"],
main:has(.dg-page-shell--players) [data-testid="stSelectbox"],
main:has(.dg-page-shell--players) [data-testid="stMultiSelect"],
main:has(.dg-page-shell--players) [data-testid="stButtonGroup"] {
    background: var(--color-surface-muted);
    border-top: var(--border-width-default) solid var(--color-border);
    padding: var(--space-sm);
}

main:has(.dg-page-shell--players) .scan-card,
main:has(.dg-page-shell--players) .compact-player-row{
    background: var(--ops-panel-deep) !important;
    border-bottom: var(--border-width-default) solid var(--color-border) !important;
    border-left: var(--border-width-semantic) solid var(--color-border-strong) !important;
    margin: 0 !important;
}

.dg-intelligence-group {
    border-bottom: var(--border-width-default) solid var(--color-border-strong);
    color: var(--color-text-primary) !important;
    font-size: var(--font-size-badge) !important;
    letter-spacing: var(--letter-spacing-badge);
    margin: var(--space-xl) 0 0 !important;
    padding: 0 0 var(--space-sm) !important;
    text-transform: uppercase;
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

@media (max-width: 900px) {
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

    main:has(.dg-page-shell--trade-hub) .trade-card-top {
        grid-template-columns: 1fr !important;
    }

    main:has(.waiver-section-header) .waiver-context-grid {
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
    .dg-page-shell *,
.home-command-shell *,
.trade-idea-card *,
.free-agent-card *,
.dg-intelligence-item *{
        animation: none !important;
        scroll-behavior: auto !important;
        transition: none !important;
    }
}
"""
