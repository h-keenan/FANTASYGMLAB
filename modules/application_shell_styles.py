"""Scoped, token-backed styles for the canonical executive workspace shell."""

APPLICATION_SHELL_CSS = """
/* Canonical executive shell and cross-page rhythm. */
.block-container {
    /* Width contract finalized by DESKTOP_EXECUTIVE_LAYOUT_CSS. */
    max-width: 1180px !important;
    padding: var(--space-lg) var(--space-xl) var(--space-3xl) !important;
}

div[class*="st-key-executive_workspace_shell"] {
    align-items: stretch;
    background: var(--color-surface-primary);
    border: var(--border-width-default) solid var(--color-border);
    border-radius: var(--radius-panel);
    display: grid !important;
    gap: 0;
    grid-template-columns: minmax(0, 1fr) auto;
    margin-block-end: var(--space-lg);
    overflow: hidden;
}

.dg-executive-shell {
    align-items: center;
    background: transparent;
    border: 0;
    border-radius: 0;
    display: grid;
    gap: var(--space-md);
    grid-template-columns: var(--touch-target-min) minmax(0, 1fr);
    min-height: var(--touch-target-min);
    padding: var(--space-sm) var(--space-md);
}

.dg-executive-shell__brand {
    align-items: center;
    align-self: stretch;
    background: var(--color-text-primary);
    border-inline-start: var(--border-width-semantic) solid var(--color-information);
    color: var(--color-bg);
    display: flex;
    font: var(--font-card-title);
    justify-content: center;
    min-height: var(--touch-target-min);
    width: var(--touch-target-min);
}

.dg-executive-shell__brief {
    align-items: center;
    display: grid;
    gap: var(--space-xs) var(--space-lg);
    grid-template-columns: minmax(10rem, auto) minmax(0, 1fr) auto;
    min-width: 0;
}

.dg-executive-shell__title-row {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-sm);
    grid-row: 1 / 3;
    min-width: 0;
}

.dg-executive-shell__title {
    color: var(--color-text-primary);
    font: var(--font-page-title) !important;
    line-height: var(--line-height-card) !important;
    margin: 0;
    overflow-wrap: anywhere;
}

.dg-executive-shell__context {
    align-items: baseline;
    display: flex;
    gap: var(--space-sm);
    min-width: 0;
}

.dg-executive-shell__room {
    color: var(--color-information);
    flex: 0 0 auto;
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    line-height: var(--line-height-badge);
    text-transform: uppercase;
}

.dg-executive-shell__league {
    color: var(--color-text-secondary);
    font: var(--font-card-title);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.dg-executive-shell__status {
    align-items: center;
    color: var(--color-text-muted);
    display: flex;
    font-size: var(--font-size-caption);
    gap: var(--space-xs);
    grid-column: 2;
    line-height: var(--line-height-caption);
    min-width: 0;
}

div[class*="st-key-executive_workspace_shell"] div[class*="st-key-top_league_actions"] {
    align-self: stretch;
    margin: 0;
}

div[class*="st-key-executive_workspace_shell"] div[class*="st-key-top_league_actions"] [data-testid="stPopover"],
div[class*="st-key-executive_workspace_shell"] div[class*="st-key-top_league_actions"] [data-testid="stPopover"] button {
    height: 100%;
}

div[class*="st-key-executive_workspace_shell"] div[class*="st-key-top_league_actions"] [data-testid="stPopover"] button {
    background: transparent;
    border: 0;
    border-radius: 0;
    min-height: var(--touch-target-min);
    padding-inline: var(--space-lg);
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

    div[class*="st-key-executive_workspace_shell"] {
        gap: 0;
        grid-template-columns: minmax(0, 1fr);
        margin-block-end: var(--space-md);
    }

    .dg-executive-shell {
        gap: var(--space-xs);
        padding: var(--space-xs) var(--space-sm);
    }

    .dg-executive-shell__brief {
        gap: 2px var(--space-sm);
        grid-template-columns: minmax(0, 1fr);
    }

    .dg-executive-shell__title-row {
        grid-column: 1 / -1;
        grid-row: auto;
        width: 100%;
    }

    .dg-executive-shell__title {
        font-size: var(--font-size-section-title) !important;
        line-height: 1.1 !important;
    }

    .dg-executive-shell__context {
        gap: var(--space-xs);
        min-width: 0;
    }

    .dg-executive-shell__league {
        font-size: var(--font-size-caption);
    }

    /* Account/Premium live in You; Alerts owns unread — drop redundant status band */
    .dg-executive-shell__status {
        display: none;
    }

    .dg-executive-shell__chip {
        display: none;
    }

    div[class*="st-key-executive_workspace_shell"] div[class*="st-key-top_league_actions"] [data-testid="stPopover"],
    div[class*="st-key-executive_workspace_shell"] div[class*="st-key-top_league_actions"] [data-testid="stPopover"] button {
        width: 100%;
    }

    div[class*="st-key-executive_workspace_shell"] div[class*="st-key-top_league_actions"] [data-testid="stPopover"] button {
        padding-inline: var(--space-md);
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

@media (prefers-reduced-motion: reduce) {
    .dg-executive-shell *,
    .dg-ui-card,
    .trade-idea-card {
        animation: none !important;
        scroll-behavior: auto !important;
        transition-duration: 0.01ms !important;
    }
}
"""
