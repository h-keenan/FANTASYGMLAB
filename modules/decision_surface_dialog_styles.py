"""Shared portal geometry for major decision-surface dialogs."""

DECISION_SURFACE_DIALOG_CSS = """
div[data-testid="stDialog"] [role="dialog"]:has(.trade-detail-modal, .player-quick-view-shell) {
    box-sizing: border-box;
    max-width: 100dvw;
    overflow-x: clip;
}

@media (max-width: 700px) {
    /* Width/max-width are intentionally relative to this element's own
       flow parent (100%), not the viewport (100dvw): the parent div
       Streamlit renders already caps itself to calc(100% - 32px) of the
       viewport, so a dvw-based width here would overflow that parent
       (and the viewport) by the parent's own side margins. */
    div[data-testid="stDialog"] [role="dialog"]:has(.trade-detail-modal, .player-quick-view-shell) {
        margin-inline: var(--space-xs) !important;
        max-width: 100% !important;
        overflow-x: clip !important;
        padding: var(--space-2xs) !important;
        width: 100% !important;
    }

    div[data-testid="stDialog"] [role="dialog"]:has(.trade-detail-modal, .player-quick-view-shell)
        > div:has(.trade-detail-modal, .player-quick-view-shell) {
        min-width: 0;
        overflow-x: clip;
        padding-inline: var(--space-xs) !important;
    }
}
"""
