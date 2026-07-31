"""Token-backed presentation for the canonical Player Quick View dossier."""

PLAYER_QUICK_VIEW_CSS = """
/* Player Quick View 2.0: Front Office Dossier */
.player-dossier-snapshot,
.player-dossier-career,
.player-dossier-recommendation-context {
    background: var(--color-surface-muted);
    border: var(--border-width-default) solid var(--color-border);
    border-radius: var(--radius-panel);
    margin: var(--space-sm) 0;
    overflow: hidden;
}

.player-dossier-snapshot-title,
.player-dossier-section-heading {
    border-bottom: var(--border-width-default) solid var(--color-border);
    border-left: var(--border-width-semantic) solid var(--color-information);
    padding: var(--space-sm) var(--space-md);
}

.player-dossier-snapshot-title,
.player-dossier-section-heading h3 {
    color: var(--color-text-primary);
    font-size: var(--font-size-card-title);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    line-height: var(--line-height-card);
    margin: 0;
    text-transform: uppercase;
}

.player-dossier-section-heading p {
    color: var(--color-text-muted);
    font-size: var(--font-size-caption);
    line-height: var(--line-height-caption);
    margin: var(--space-xs) 0 0;
}

.player-dossier-snapshot-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
}

.player-dossier-snapshot-metric {
    border-right: var(--border-width-default) solid var(--color-border);
    display: grid;
    gap: var(--space-xs);
    min-width: 0;
    padding: var(--space-sm) var(--space-md);
}

.player-dossier-snapshot-metric:last-child {
    border-right: 0;
}

.player-dossier-snapshot-metric span,
.player-dossier-decision span {
    color: var(--color-text-muted);
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-button);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}

.player-dossier-snapshot-metric strong {
    color: var(--color-text-primary);
    font-size: var(--font-size-card-title);
    line-height: var(--line-height-card);
    overflow-wrap: anywhere;
}

.player-dossier-decision {
    border-left: var(--border-width-semantic) solid var(--color-information);
    border-top: var(--border-width-default) solid var(--color-border);
    display: grid;
    gap: var(--space-xs);
    padding: var(--space-sm) var(--space-md);
}

.player-dossier-decision--opportunity {
    border-left-color: var(--color-opportunity);
}

.player-dossier-decision--risk {
    border-left-color: var(--color-warning);
}

.player-dossier-decision strong {
    color: var(--color-text-primary);
    font-size: var(--font-size-section-title);
}

.player-dossier-decision p,
.player-dossier-context-summary,
.player-dossier-context-note,
.player-dossier-career-empty {
    color: var(--color-text-secondary);
    font-size: var(--font-size-body);
    line-height: var(--line-height-body);
    margin: 0;
}

.player-dossier-career-empty,
.player-dossier-career-group,
.player-dossier-context-summary,
.player-dossier-context-note {
    padding: var(--space-sm) var(--space-md);
}

.player-dossier-context-note {
    border-top: var(--border-width-default) solid var(--color-border);
    color: var(--color-text-muted);
}

.player-dossier-career-group h4 {
    color: var(--color-text-primary);
    font-size: var(--font-size-body);
    margin: 0 0 var(--space-xs);
}

.player-dossier-career-group ul {
    color: var(--color-text-secondary);
    margin: 0;
    padding-left: var(--space-lg);
}

div[data-testid="stDialog"] div[role="dialog"]:has(.player-quick-view-shell) {
    max-height: min(88vh, 920px) !important;
}

div[data-testid="stDialog"] div[role="dialog"]:has(.player-quick-view-shell) > div:last-child {
    overflow-y: auto !important;
    overscroll-behavior: contain;
}

@media (max-width: 900px) {
    .player-dossier-snapshot-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .player-dossier-snapshot-metric:nth-child(2) {
        border-right: 0;
    }

    .player-dossier-snapshot-metric:nth-child(-n + 2) {
        border-bottom: var(--border-width-default) solid var(--color-border);
    }

    .player-dossier-section-heading,
    .player-dossier-snapshot-title,
    .player-dossier-snapshot-metric,
    .player-dossier-decision,
    .player-dossier-career-empty,
    .player-dossier-career-group,
    .player-dossier-context-summary,
    .player-dossier-context-note {
        padding-left: var(--space-sm);
        padding-right: var(--space-sm);
    }
}

@media (prefers-reduced-motion: reduce) {
    .player-dossier-snapshot *,
    .player-dossier-career *,
    .player-dossier-recommendation-context * {
        animation: none !important;
        transition: none !important;
    }
}
"""
