"""Shared portal geometry for major decision-surface dialogs."""

DECISION_SURFACE_DIALOG_CSS = """
div[data-testid="stDialog"] div[role="dialog"]:has(.trade-detail-modal, .player-quick-view-shell) {
    box-sizing: border-box;
    max-width: 100dvw;
    overflow-x: clip;
}

@media (max-width: 700px) {
    div[data-testid="stDialog"] div[role="dialog"]:has(.trade-detail-modal, .player-quick-view-shell) {
        margin-inline: var(--space-xs) !important;
        max-width: calc(100dvw - (2 * var(--space-xs))) !important;
        overflow-x: clip !important;
        padding: var(--space-2xs) !important;
        width: calc(100dvw - (2 * var(--space-xs))) !important;
    }

    div[data-testid="stDialog"] div[role="dialog"]:has(.trade-detail-modal, .player-quick-view-shell)
        > div:has(.trade-detail-modal, .player-quick-view-shell) {
        min-width: 0;
        overflow-x: clip;
        padding-inline: var(--space-xs) !important;
    }
}
"""
