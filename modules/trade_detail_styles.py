"""Scoped token-backed styles for interactive Trade Hub detail navigation."""

TRADE_DETAIL_CSS = """
/* One-dialog Trade Hub detail and dossier navigation. */
.trade-detail-modal {
    border: var(--border-width-default) solid var(--color-border-strong);
    border-radius: var(--radius-panel);
    max-width: 100%;
    overflow-x: clip;
    overflow-y: auto;
}

.trade-detail-modal .trade-asset-row,
.trade-detail-modal .trade-asset-row-compact {
    align-items: start;
    display: grid !important;
    gap: var(--space-sm);
    grid-template-columns: 3.5rem minmax(0, 1fr);
    min-height: 3.5rem;
    overflow: hidden;
    padding: var(--space-xs) var(--space-sm) !important;
}
.trade-detail-modal .trade-asset-copy {
    min-width: 0;
}
.trade-detail-modal .trade-asset-name {
    margin-top: 0;
}
.trade-detail-modal .trade-asset-row .trade-avatar,
.trade-detail-modal .trade-asset-row .trade-avatar-pick,
.trade-detail-modal .trade-asset-row-compact .trade-avatar,
.trade-detail-modal .trade-asset-row-compact .trade-avatar-pick {
    --avatar-size: 3.5rem;
    flex: 0 0 3.5rem;
    height: 3.5rem !important;
    max-height: 3.5rem !important;
    max-width: 3.5rem !important;
    min-height: 3.5rem !important;
    min-width: 3.5rem !important;
    width: 3.5rem !important;
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

.trade-detail-modal .trade-review-exchange-separator > span {
    display: none;
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
    align-items: start;
    display: grid;
    gap: var(--space-sm);
    grid-template-columns: 3.5rem minmax(0, 1fr);
    min-height: 3.5rem;
    padding: var(--space-xs) var(--space-sm) !important;
}

.trade-detail-modal .trade-asset-row-compact .trade-avatar,
.trade-detail-modal .trade-asset-row-compact .trade-avatar-pick {
    height: 3.5rem;
    width: 3.5rem;
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

/* Keep send/receive stacked on phone — desktop two-column does not fit 390. */
@media (max-width: 700px) {
    .trade-detail-modal .trade-matchup-compact {
        display: flex !important;
        flex-direction: column;
        gap: var(--space-sm);
        grid-template-columns: minmax(0, 1fr);
        padding: var(--space-sm);
    }

    .trade-detail-modal .trade-vs {
        align-items: center;
        justify-content: center;
    }

    .trade-detail-modal .trade-review-exchange-separator {
        align-self: center;
        background: transparent;
        border: 0;
        gap: 0;
        line-height: var(--line-height-badge);
        min-height: 0;
        padding: var(--space-2xs) 0;
        width: auto;
    }

    .trade-detail-modal .trade-review-exchange-separator > span {
        display: inline;
    }

    .trade-detail-modal .trade-review-exchange-separator::before,
    .trade-detail-modal .trade-review-exchange-separator::after {
        content: none;
        display: none;
    }

    .trade-detail-modal .trade-side {
        max-width: 100%;
        min-width: 0;
        padding: var(--space-xs) 0 !important;
        width: 100%;
    }

    .trade-detail-modal .trade-asset-row-compact {
        align-items: start !important;
        flex-direction: row !important;
        gap: var(--space-sm) !important;
        grid-template-columns: 3.5rem minmax(0, 1fr);
        min-width: 0;
        overflow: hidden;
    }

    .trade-detail-modal .trade-asset-row {
        min-height: var(--touch-target-min);
        padding: var(--space-xs) !important;
    }

    .trade-reason-panel {
        background: var(--color-surface-muted);
        margin-top: var(--space-xs);
        padding: 0 var(--space-sm);
    }

    div[data-testid="stDialog"] div[role="dialog"]:has(.trade-detail-modal) .dg-info-verdict-delta {
        display: grid;
        flex: 1 1 100%;
        grid-template-columns: auto auto minmax(9rem, 1fr) auto;
        width: 100%;
    }

    div[data-testid="stDialog"] div[role="dialog"]:has(.trade-detail-modal) .dg-info-verdict-delta .tvl-edge-mark {
        width: 100%;
        height: 6px;
    }
}

@media (min-width: 1280px) {
    div[data-testid="stDialog"] div[role="dialog"]:has(.trade-detail-modal) {
        max-width: min(72vw, 1080px) !important;
        width: min(72vw, 1080px) !important;
    }

    .trade-detail-modal .trade-matchup-compact {
        gap: var(--space-sm);
        grid-template-columns: minmax(0, 1fr) 3rem minmax(0, 1fr);
        padding: var(--space-sm);
    }
}

@media (min-width: 1440px) {
    div[data-testid="stDialog"] div[role="dialog"]:has(.trade-detail-modal) {
        max-width: min(68vw, 1200px) !important;
        width: min(68vw, 1200px) !important;
    }

    .trade-detail-modal .trade-matchup-compact {
        gap: var(--space-md);
        padding: var(--space-sm) var(--space-md);
    }
}

.trade-detail-modal.trade-detail-modal--decision {
    border-color: var(--color-border);
}
.trade-detail-modal .trade-card-partner {
    padding: var(--space-2xs) 0 var(--space-xs);
}
.trade-detail-modal .trade-matchup-compact .trade-side {
    padding: var(--space-xs) 0 !important;
}
.trade-detail-modal .trade-asset-row,
.trade-detail-modal .trade-asset-row-compact {
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
    padding: var(--space-2xs) 0 !important;
}

/* Canonical share PNG displayed compact; source is full-resolution, content-tall. */
.fgl-share-panel {
    margin-inline: auto;
    max-width: min(100%, 26.25rem);
    width: 100%;
}
.fgl-share-kicker {
    color: var(--color-text-muted);
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    margin: 0 0 var(--space-sm);
    text-align: center;
    text-transform: uppercase;
}
.fgl-share-preview {
    margin-inline: auto;
    max-width: 400px;
    width: 100%;
}
.fgl-share-preview img {
    display: block;
    height: auto;
    margin-inline: auto;
    max-width: 100%;
    width: 100%;
}
.fgl-share-preview-caption {
    color: var(--color-text-muted);
    font-size: var(--font-size-caption);
    margin: var(--space-sm) 0 0;
    text-align: center;
}
div:has(> .fgl-share-panel),
div:has(> .fgl-share-panel) ~ div {
    margin-inline: auto;
    max-width: min(100%, 26.25rem);
    width: 100%;
}
@media (max-width: 700px) {
    .fgl-share-preview {
        max-width: 300px;
    }
}

div[class*="st-key-trade_hub_controls"],
div[class*="st-key-trade_hub_board"],
div[class*="st-key-trade_hub_unified_feed_"] {
    max-width: min(76rem, 100%);
    min-width: 0;
    width: 100%;
}
div[class*="st-key-trade_hub_headline"],
div[class*="st-key-trade_hub_more_ideas"],
div[class*="st-key-trade_hub_show_more"] {
    max-width: 100%;
    min-width: 0;
    width: 100%;
}
div[class*="st-key-trade_hub_headline"] iframe,
div[class*="st-key-trade_hub_more_ideas"] iframe,
div[class*="st-key-trade_hub_headline"] [data-testid="stCustomComponentV2"],
div[class*="st-key-trade_hub_more_ideas"] [data-testid="stCustomComponentV2"],
div[class*="st-key-trade_hub_headline"] [class*="stElementContainer"],
div[class*="st-key-trade_hub_more_ideas"] [class*="stElementContainer"],
div[class*="st-key-trade_hub_headline"] [data-testid="stVerticalBlock"],
div[class*="st-key-trade_hub_more_ideas"] [data-testid="stVerticalBlock"] {
    display: block !important;
    max-width: 100% !important;
    min-width: 0 !important;
    width: 100% !important;
}
div[class*="st-key-trade_hub_controls"] {
    max-width: min(36rem, 100%);
}
div[class*="st-key-trade_hub_controls"] [data-testid="stHorizontalBlock"] {
    align-items: end;
    gap: var(--space-xs) !important;
    max-width: 100%;
}
div[class*="st-key-trade_hub_controls"] [data-testid="stPopover"] > button {
    min-height: var(--touch-target-min);
    white-space: nowrap;
}
div[class*="st-key-trade_hub_headline"] {
    grid-column: 1 / -1;
    width: 100%;
}
div[class*="st-key-trade_hub_show_more"] {
    max-width: 100%;
    width: 100%;
}
div[class*="st-key-trade_hub_show_more"] [data-testid="stButton"] {
    max-width: 100%;
    width: 100%;
}
@media (min-width: 1280px) {
    div[class*="st-key-trade_hub_more_ideas"] > div[data-testid="stVerticalBlock"] {
        display: grid !important;
        gap: var(--space-md) !important;
        grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) !important;
    }
}
@media (max-width: 1279px) {
    div[class*="st-key-trade_hub_more_ideas"] > div[data-testid="stVerticalBlock"] {
        display: grid !important;
        grid-template-columns: minmax(0, 1fr) !important;
    }
}
"""
