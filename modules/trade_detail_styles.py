"""Scoped token-backed styles for interactive Trade Hub detail navigation."""

TRADE_DETAIL_CSS = """
/* One-dialog Trade Hub detail and dossier navigation. */
.trade-detail-modal {
    border: var(--border-width-default) solid var(--color-border-strong);
    border-radius: var(--radius-panel);
    max-width: 100%;
    overflow-x: clip;
    overflow-y: hidden;
}

.trade-detail-modal .trade-card-partner {
    border-bottom: var(--border-width-default) solid var(--color-border);
    color: var(--color-text-secondary);
    font-size: var(--font-size-metadata);
    line-height: var(--line-height-body);
    padding: var(--space-xs) var(--space-sm);
}

.trade-detail-modal .trade-side:first-child {
    border-left: var(--border-width-semantic) solid var(--color-danger) !important;
}

.trade-detail-modal .trade-side:last-child {
    border-left: var(--border-width-semantic) solid var(--color-success) !important;
}

.trade-detail-modal .trade-side-header > span {
    color: var(--color-text-primary);
    font-size: var(--font-size-caption);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
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

.trade-detail-modal .trade-asset-row-compact {
    align-items: center;
    display: grid;
    gap: var(--space-xs);
    grid-template-columns: 2.5rem minmax(0, 1fr);
    min-height: 2.75rem;
    padding: var(--space-2xs) var(--space-xs) !important;
}

.trade-detail-modal .trade-asset-row-compact .trade-avatar,
.trade-detail-modal .trade-asset-row-compact .trade-avatar-pick {
    height: var(--size-asset-compact, 2.25rem);
    width: var(--size-asset-compact, 2.25rem);
}

.trade-detail-modal .trade-asset-row-compact .trade-asset-name {
    font-size: var(--font-size-body);
    font-weight: var(--font-weight-title);
    line-height: var(--line-height-card);
}

.trade-detail-modal .trade-asset-row-compact .trade-asset-meta {
    font-size: var(--font-size-caption);
    margin-top: 0;
}

.trade-detail-modal .trade-exec-detail {
    margin-top: var(--space-sm);
}

div[class*="st-key-trade_detail_nav_"] button {
    min-height: var(--touch-target-min);
    text-align: left;
}

div[class*="st-key-trade_detail_nav_"] button:focus-visible {
    box-shadow: var(--focus-ring);
    outline: none;
}

/* Keep send/receive as a matchup on phone so the modal stays short. */
@media (max-width: 700px) {
    .trade-detail-modal .trade-matchup-compact {
        display: grid !important;
        gap: var(--space-2xs);
        grid-template-columns: minmax(0, 1fr) 1.25rem minmax(0, 1fr);
        padding: var(--space-xs);
    }

    .trade-detail-modal .trade-vs {
        min-height: auto;
        padding: 0;
    }

    .trade-detail-modal .trade-vs::before,
    .trade-detail-modal .trade-vs::after {
        content: none;
    }

    .trade-detail-modal .trade-side {
        padding: var(--space-2xs) !important;
    }

    .trade-detail-modal .trade-asset-row-compact {
        align-items: center !important;
        flex-direction: row !important;
        gap: var(--space-xs) !important;
        grid-template-columns: 2.5rem minmax(0, 1fr);
    }

    .trade-detail-modal .trade-asset-row {
        min-height: 2.5rem;
        padding: var(--space-2xs) var(--space-xs) !important;
    }

    .trade-reason-panel {
        background: var(--color-surface-muted);
        margin-top: var(--space-xs);
        padding: 0 var(--space-sm);
    }
}

@media (min-width: 1280px) {
    div[data-testid="stDialog"] div[role="dialog"]:has(.trade-detail-modal) {
        max-width: min(72vw, 1080px) !important;
        width: min(72vw, 1080px) !important;
    }

    .trade-detail-modal .trade-matchup-compact {
        gap: var(--space-lg);
        grid-template-columns: minmax(0, 1fr) 3rem minmax(0, 1fr);
        padding: var(--space-md) var(--space-lg);
    }
}

@media (min-width: 1440px) {
    div[data-testid="stDialog"] div[role="dialog"]:has(.trade-detail-modal) {
        max-width: min(68vw, 1200px) !important;
        width: min(68vw, 1200px) !important;
    }

    .trade-detail-modal .trade-matchup-compact {
        gap: var(--space-xl);
        padding: var(--space-lg) var(--space-xl);
    }
}

/* Canonical share PNG displayed compact; source stays 2160×2400. */
.fgl-share-preview {
    max-width: 320px;
}
.fgl-share-preview img {
    display: block;
    height: auto;
    max-width: 100%;
    width: 100%;
}
.fgl-share-preview-caption {
    color: var(--color-text-muted);
    font-size: var(--font-size-caption);
    margin: var(--space-2xs) 0 0;
}
@media (max-width: 700px) {
    .fgl-share-preview {
        max-width: 280px;
    }
}
"""
