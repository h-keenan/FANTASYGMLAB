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
    grid-template-columns: minmax(0, 1fr) minmax(min(100%, 28rem), 1fr);
    margin-block-end: var(--space-md);
    overflow: hidden;
}

.dg-executive-shell {
    align-items: center;
    background: transparent;
    border: 0;
    border-radius: 0;
    display: grid;
    gap: var(--space-sm);
    grid-template-columns: var(--touch-target-min) minmax(0, 1fr);
    min-height: var(--touch-target-min);
    padding-block: 0;
    padding-inline: var(--space-md);
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

/* Founder Beta stays readable but must not starve the command rail */
.dg-executive-shell__title-row .dg-founder-badge {
    flex: 0 1 auto;
    max-width: 9.75rem;
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

.dg-ui-section-header,
.section-header {
    margin-block: var(--space-xl) var(--space-md) !important;
}

.dg-ui-card,
.dg-ui-empty-state,
[data-testid="stAlert"],
div[data-testid="stExpander"]{
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
            max(var(--space-md), env(safe-area-inset-top, 0px))
            max(var(--space-md), env(safe-area-inset-right, 0px))
            max(var(--space-3xl), env(safe-area-inset-bottom, 0px))
            max(var(--space-md), env(safe-area-inset-left, 0px)) !important;
    }

    div[class*="st-key-executive_workspace_shell"] {
        gap: 0;
        grid-template-columns: minmax(0, 1fr);
        margin-block-end: var(--space-sm);
    }

    .dg-executive-shell {
        gap: var(--space-xs);
        min-height: 0;
        padding-block: var(--space-2xs);
        padding-inline: var(--space-sm);
    }

    .dg-executive-shell__brand {
        min-height: 2.5rem;
        width: 2.5rem;
    }

    .dg-executive-shell__brief {
        align-content: center;
        gap: 0;
        grid-template-columns: minmax(0, 1fr);
        min-width: 0;
    }

    .dg-executive-shell__title-row {
        flex-wrap: nowrap;
        gap: var(--space-xs);
        grid-column: 1 / -1;
        grid-row: auto;
        min-width: 0;
        width: 100%;
    }

    .dg-executive-shell__title-row .dg-founder-badge {
        display: none;
    }

    .dg-executive-shell__title {
        font-size: clamp(0.95rem, 3.6vw, 1.15rem) !important;
        font-weight: var(--font-weight-display) !important;
        letter-spacing: -0.02em !important;
        line-height: 1.15 !important;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .dg-executive-shell__context {
        gap: var(--space-xs);
        min-width: 0;
        width: 100%;
    }

    /* War Room competes with league identity on narrow widths — hide; league is enough. */
    .dg-executive-shell__room {
        display: none;
    }

    .dg-executive-shell__league {
        font-size: var(--font-size-caption);
        font-weight: var(--font-weight-title);
        max-width: 100%;
        min-width: 0;
    }

    /* Account/Premium live in You; Alerts owns unread — drop redundant status band */
    .dg-executive-shell__status {
        display: none;
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
