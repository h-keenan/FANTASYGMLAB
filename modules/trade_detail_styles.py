"""Scoped token-backed styles for interactive Trade Hub detail navigation."""

TRADE_DETAIL_CSS = """
/* One-dialog Trade Hub detail and dossier navigation. */
.trade-detail-modal {
    border: var(--border-width-default) solid var(--color-border-strong);
    border-radius: var(--radius-panel);
    overflow: hidden;
}

.trade-detail-modal .trade-card-partner {
    border-bottom: var(--border-width-default) solid var(--color-border);
    color: var(--color-text-secondary);
    font-size: var(--font-size-metadata);
    line-height: var(--line-height-body);
    padding: var(--space-sm) var(--space-md);
}

.trade-detail-modal .trade-side:first-child {
    border-left: var(--border-width-semantic) solid var(--color-danger) !important;
}

.trade-detail-modal .trade-side:last-child {
    border-left: var(--border-width-semantic) solid var(--color-success) !important;
}

.trade-detail-modal .trade-side-header > span {
    color: var(--color-text-primary);
    font-size: var(--font-size-card-title);
    font-weight: var(--font-weight-title);
    letter-spacing: normal;
    text-transform: none;
}

.trade-detail-modal .trade-asset-row-player.player-card-tappable {
    cursor: pointer;
}

.trade-detail-modal .trade-asset-row-player.player-card-tappable:hover {
    background: var(--color-surface-raised) !important;
    border-color: var(--color-information) !important;
}

.trade-detail-modal .trade-asset-row-player.player-card-tappable:focus-visible {
    box-shadow: var(--focus-ring);
    outline: none;
}

.trade-detail-modal .trade-asset-row-pick {
    cursor: default;
}

div[class*="st-key-trade_detail_nav_"] button {
    min-height: var(--touch-target-min);
    text-align: left;
}

div[class*="st-key-trade_detail_nav_"] button:focus-visible {
    box-shadow: var(--focus-ring);
    outline: none;
}

@media (max-width: 700px) {
    .trade-detail-modal .trade-matchup-compact {
        display: grid;
        gap: var(--space-sm);
        grid-template-columns: minmax(0, 1fr);
        padding: var(--space-sm);
    }

    .trade-detail-modal .trade-vs {
        min-height: var(--space-lg);
        padding: 0;
    }

    .trade-detail-modal .trade-side {
        padding: var(--space-sm) !important;
    }

    .trade-detail-modal .trade-asset-row {
        padding: var(--space-sm) !important;
    }

    .trade-card-net-strip {
        padding: var(--space-sm) var(--space-md);
    }

    .trade-reason-panel {
        background: var(--color-surface-muted);
        margin-top: var(--space-sm);
        padding: 0 var(--space-md);
    }

    .trade-reason-row {
        padding: var(--space-sm) 0;
    }
}

/* In-app share thumbnail — export PNG stays 2160×2700. */
.fgl-share-preview {
    max-width: 360px;
}
@media (max-width: 700px) {
    .fgl-share-preview {
        max-width: 280px;
    }
}
"""
