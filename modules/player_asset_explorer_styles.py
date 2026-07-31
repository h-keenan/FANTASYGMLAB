"""Token-backed responsive styles for the unified Player & Asset Explorer."""

PLAYER_ASSET_EXPLORER_CSS = """
.explorer-pick-grid {
    display: grid;
    gap: var(--space-md);
    grid-template-columns: repeat(2, minmax(0, 1fr));
}

.explorer-pick-card {
    min-width: 0;
}

.explorer-pick-card__top {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-xs);
}

.explorer-pick-card__title {
    color: var(--color-text-primary);
    font: var(--font-card-title);
    margin: var(--space-md) 0 var(--space-xs);
    overflow-wrap: anywhere;
}

.explorer-pick-card__meta {
    color: var(--color-text-muted);
    font-size: var(--font-size-caption);
    line-height: var(--line-height-caption);
    overflow-wrap: anywhere;
}

.explorer-pick-card__metrics {
    display: grid;
    gap: var(--space-xs);
    grid-template-columns: repeat(3, minmax(0, 1fr));
    margin: var(--space-md) 0 0;
}

.explorer-pick-card__metrics > div {
    background: var(--color-surface-muted);
    border: var(--border-width-default) solid var(--color-border);
    border-radius: var(--radius-md);
    min-width: 0;
    padding: var(--space-sm);
}

.explorer-pick-card__metrics dt {
    color: var(--color-text-muted);
    font-size: var(--font-size-badge);
}

.explorer-pick-card__metrics dd {
    color: var(--color-text-primary);
    font: var(--font-card-title);
    margin: var(--space-xs) 0 0;
    overflow-wrap: anywhere;
}

div[class*="st-key-player_asset_explorer_"] button,
div[class*="st-key-player_asset_explorer_"] input {
    min-height: var(--touch-target-min);
}

@media (max-width: 700px) {
    .explorer-pick-grid {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 390px) {
    .explorer-pick-card__metrics {
        grid-template-columns: 1fr;
    }
}
"""
