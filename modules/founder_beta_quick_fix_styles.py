"""Founder Beta dialog, intelligence-item, and surface radius consistency.

GM orb/sheet chrome is owned solely by MOBILE_INTERACTION_OVERLAY_CSS.
Global button geometry is owned by COMMAND_CENTER_CSS (visual_identity).
"""

FOUNDER_BETA_QUICK_FIX_CSS = """

div[data-testid="stDialog"] {
    background: rgba(0, 0, 0, 0.72) !important;
}

div[data-testid="stDialog"] > div {
    border-radius: var(--radius-none) !important;
}

div[data-testid="stDialog"] > div > div[role="dialog"],
div[role="dialog"] {
    background: var(--color-shell) !important;
    border: var(--border-width-default) solid var(--color-border-strong) !important;
    border-radius: var(--radius-none) !important;
    box-shadow: var(--shadow-overlay) !important;
    box-sizing: border-box !important;
    max-height: min(90dvh, 920px) !important;
    overflow: hidden !important;
    padding: var(--space-lg) !important;
}

div[data-testid="stDialog"] > div > div[role="dialog"] > div:first-child,
div[data-testid="stDialog"] > div > div[role="dialog"] > div:last-child,
div[role="dialog"] > div:first-child,
div[role="dialog"] > div:last-child {
    background: var(--color-shell) !important;
    border-radius: var(--radius-none) !important;
}

div[data-testid="stDialog"] > div > div[role="dialog"] > div:last-child,
div[role="dialog"] > div:last-child {
    max-height: calc(90dvh - (2 * var(--space-lg))) !important;
    overflow-x: hidden !important;
    overflow-y: auto !important;
    overscroll-behavior: contain !important;
}

div[data-testid="stDialog"] button[aria-label="Close"] {
    border-radius: var(--radius-none) !important;
    min-height: var(--touch-target-min) !important;
    min-width: var(--touch-target-min) !important;
}

div[data-testid="stDialog"] h2 {
    font: var(--type-section-title) !important;
    margin: 0 !important;
    padding-right: calc(var(--touch-target-min) + var(--space-sm)) !important;
}

:is(
    .dg-ui-card,
    .dg-ui-callout,
    .dg-ui-empty-state,
    .summary-tile,
    .dg-intelligence-item,
    .trade-summary-card,
    .free-agent-card,
    .trade-detail-modal,
    .trade-detail-modal .trade-side,
    .trade-detail-modal .trade-asset-row,
    .player-quick-view-hero,
    .player-quick-view-header-band.player-quick-view-hero,
    .player-dossier-snapshot,
    .player-dossier-career,
    .player-dossier-recommendation-context,
    div[data-testid="stExpander"],
    [data-testid="stAlert"]
) {
    border-radius: var(--radius-panel) !important;
}

/* Global button radius owned by COMMAND_CENTER_CSS — do not redeclare here. */
/* BaseWeb inputs keep radius-none for Streamlit control chrome. */
:is(
    [data-baseweb="select"] > div,
    [data-baseweb="input"] > div,
    [data-baseweb="textarea"] > div
) {
    border-radius: var(--radius-none) !important;
}
/* stPopover triggers: executive command rail owned by EXECUTIVE_COMMAND_HEADER_CSS. */

.dg-ui-section-header,
.section-header {
    margin: var(--space-lg) 0 var(--space-sm) !important;
}

.dg-intelligence-group {
    margin: var(--space-lg) 0 var(--space-xs) !important;
}

.dg-intelligence-item {
    background: var(--color-surface-muted) !important;
    border-left-color: var(--color-border-strong) !important;
    gap: var(--space-sm) !important;
    padding: var(--space-md) !important;
}

.dg-intelligence-item--primary {
    background: var(--color-surface-primary) !important;
    border-left-color: var(--color-information) !important;
}

@media (max-width: 700px) {
    div[data-testid="stDialog"] > div > div[role="dialog"],
    div[role="dialog"] {
        max-height: calc(100dvh - (2 * var(--space-sm))) !important;
        max-width: calc(100vw - (2 * var(--space-sm))) !important;
        padding:
            var(--space-md)
            max(var(--space-md), env(safe-area-inset-right))
            max(var(--space-md), env(safe-area-inset-bottom))
            max(var(--space-md), env(safe-area-inset-left)) !important;
        width: calc(100vw - (2 * var(--space-sm))) !important;
    }

    div[data-testid="stDialog"] > div > div[role="dialog"] > div:last-child,
    div[role="dialog"] > div:last-child {
        max-height: calc(100dvh - (4 * var(--space-md))) !important;
    }

    .dg-ui-section-header,
    .section-header {
        margin-top: var(--space-md) !important;
    }

    .trade-detail-modal .trade-asset-row {
        align-items: flex-start !important;
        flex-direction: column !important;
        gap: var(--space-xs) !important;
    }

    .trade-detail-modal .trade-asset-name,
    .trade-detail-modal .trade-asset-meta {
        max-width: 100% !important;
        overflow-wrap: break-word !important;
        width: 100% !important;
    }
}
"""
