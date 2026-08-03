"""Scoped, token-backed styles for the canonical application workspace."""

APPLICATION_SHELL_CSS = """
/* Canonical application shell and cross-page rhythm. */
.block-container {
    max-width: 1280px !important;
    padding: var(--space-lg) var(--space-xl) var(--space-3xl) !important;
}

.dg-application-workspace {
    align-items: stretch;
    background: var(--color-surface-primary);
    border: var(--border-width-default) solid var(--color-border);
    border-radius: var(--radius-panel);
    box-shadow: var(--shadow-card), var(--shadow-surface-inset);
    display: grid;
    gap: var(--space-md);
    grid-template-columns: minmax(11rem, .65fr) minmax(15rem, 1fr);
    margin: 0 0 var(--space-lg);
    overflow: hidden;
    padding: var(--space-md);
}

.dg-workspace-page,
.dg-workspace-context,
.dg-workspace-context-copy {
    min-width: 0;
}

.dg-workspace-page-kicker,
.dg-workspace-platform,
.dg-workspace-metric-label {
    color: var(--color-information);
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    line-height: var(--line-height-badge);
    text-transform: uppercase;
}

.dg-workspace-page-title {
    color: var(--color-text-primary);
    font: var(--font-page-title);
    margin: var(--space-sm) 0 0;
    overflow-wrap: anywhere;
}

.dg-workspace-page-note {
    color: var(--color-text-muted);
    font: var(--font-body);
    margin: var(--space-sm) 0 0;
    max-width: 62ch;
}

.dg-workspace-context {
    align-items: center;
    background: var(--color-surface-muted);
    border: var(--border-width-default) solid var(--color-border);
    border-radius: var(--radius-sm);
    display: grid;
    gap: var(--space-md);
    grid-template-columns: var(--space-3xl) minmax(0, 1fr);
    padding: var(--space-md);
}

.dg-workspace-avatar {
    align-items: center;
    background: var(--color-surface-raised);
    border: var(--border-width-default) solid var(--color-border-strong);
    border-radius: var(--radius-md);
    display: flex;
    height: var(--space-3xl);
    justify-content: center;
    overflow: hidden;
    width: var(--space-3xl);
}

.dg-workspace-avatar img {
    height: 100%;
    object-fit: cover;
    width: 100%;
}

.dg-workspace-avatar--fallback {
    color: var(--color-text-secondary);
    font-weight: var(--font-weight-title);
}

.dg-workspace-league {
    color: var(--color-text-primary);
    font: var(--font-card-title);
    margin-top: var(--space-xs);
    overflow-wrap: anywhere;
}

.dg-workspace-team,
.dg-workspace-sync,
.dg-workspace-metric-note {
    color: var(--color-text-muted);
    font-size: var(--font-size-caption);
    line-height: var(--line-height-caption);
    margin-top: var(--space-xs);
    overflow-wrap: anywhere;
}

.dg-workspace-sync {
    color: var(--color-text-secondary);
}

.dg-workspace-metrics {
    display: grid;
    gap: var(--space-sm);
    grid-column: 1 / -1;
    grid-template-columns: repeat(4, minmax(0, 1fr));
}

.dg-workspace-metric {
    background: var(--color-surface-muted);
    border: var(--border-width-default) solid var(--color-border);
    border-radius: var(--radius-md);
    min-width: 0;
    padding: var(--space-sm) var(--space-md);
}

.dg-workspace-metric-value {
    color: var(--color-text-primary);
    font: var(--font-card-title);
    margin-top: var(--space-xs);
    overflow-wrap: anywhere;
}

div[class*="st-key-top_league_actions"] {
    margin: calc(var(--space-sm) * -1) 0 var(--space-xl);
}

div[class*="st-key-top_league_actions"] [data-testid="stPopover"] > button {
    min-height: var(--touch-target-min);
}

.dg-ui-section-header,
.section-header {
    margin-block: var(--space-xl) var(--space-md) !important;
}

.dg-ui-card,
.dg-ui-callout,
.dg-ui-empty-state,
[data-testid="stAlert"],
div[data-testid="stExpander"] {
    margin-block: 0 var(--space-md);
}

[data-testid="stAlert"] {
    background: var(--color-surface-muted) !important;
    border: var(--border-width-default) solid var(--color-border) !important;
    border-radius: var(--radius-lg) !important;
    box-shadow: var(--shadow-none) !important;
}

[data-testid="stSpinner"] {
    color: var(--color-text-secondary);
    min-height: var(--touch-target-min);
}

div[data-testid="stDialog"] div[role="dialog"] {
    padding: var(--space-xl) !important;
}

:is(button, a, [role="button"]):focus-visible {
    box-shadow: var(--focus-ring) !important;
    outline: none;
}

@media (max-width: 760px) {
    .block-container {
        padding:
            var(--space-md)
            max(var(--space-md), env(safe-area-inset-right))
            max(var(--space-3xl), env(safe-area-inset-bottom))
            max(var(--space-md), env(safe-area-inset-left)) !important;
    }

    .dg-application-workspace {
        gap: var(--space-sm);
        grid-template-columns: 1fr;
        padding: var(--space-sm) var(--space-md);
    }

    .dg-workspace-page-note { display: none; }
    .dg-workspace-context { padding: var(--space-sm); }
    .dg-workspace-page-title { margin-top: var(--space-xs); }

    .dg-workspace-metrics {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    div[data-testid="stDialog"] div[role="dialog"] {
        max-height: calc(100dvh - (2 * var(--space-md)));
        max-width: calc(100vw - (2 * var(--space-md)));
        padding:
            var(--space-lg)
            max(var(--space-lg), env(safe-area-inset-right))
            max(var(--space-lg), env(safe-area-inset-bottom))
            max(var(--space-lg), env(safe-area-inset-left)) !important;
    }
}

@media (max-width: 390px) {
    .dg-workspace-metrics {
        grid-template-columns: 1fr;
    }
}

@media (prefers-reduced-motion: reduce) {
    .dg-application-workspace *,
    .dg-ui-card,
    .trade-idea-card {
        animation: none !important;
        scroll-behavior: auto !important;
        transition-duration: 0.01ms !important;
    }
}
"""
