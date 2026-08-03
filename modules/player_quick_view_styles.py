"""Token-backed presentation for the canonical Player Quick View dossier."""

PLAYER_QUICK_VIEW_CSS = """
/* Player Quick View 2.0: Front Office Dossier */
.player-dossier-snapshot,
.player-dossier-executive,
.player-dossier-career,
.player-dossier-recommendation-context {
    background: var(--color-surface-muted);
    border: var(--border-width-default) solid var(--color-border);
    border-radius: var(--radius-none);
    margin: var(--space-sm) 0;
    overflow: hidden;
}

.player-dossier-executive-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
}

.player-dossier-executive-metric {
    border-right: var(--border-width-default) solid var(--color-border);
    border-top: var(--border-width-default) solid var(--color-border);
    display: grid;
    gap: var(--space-xs);
    min-width: 0;
    padding: var(--space-sm) var(--space-md);
}

.player-dossier-executive-metric:nth-child(3n) {
    border-right: 0;
}

.player-dossier-executive-metric span,
.player-dossier-resume-meta span,
.player-dossier-resume-meta small,
.player-dossier-achievement-copy small,
.player-dossier-timeline-context,
.player-dossier-timeline-copy small {
    color: var(--color-text-muted);
    font-size: var(--font-size-badge);
    letter-spacing: var(--letter-spacing-badge);
}

.player-dossier-executive-metric strong,
.player-dossier-resume-meta strong {
    color: var(--color-text-primary);
    font-size: var(--font-size-body);
    overflow-wrap: anywhere;
}

.player-dossier-resume-meta {
    align-items: center;
    border-bottom: var(--border-width-default) solid var(--color-border);
    display: grid;
    gap: var(--space-xs);
    grid-template-columns: auto 1fr auto;
    padding: var(--space-sm) var(--space-md);
}

.player-dossier-achievement-list,
.player-dossier-timeline {
    list-style: none;
    margin: 0;
    padding: 0;
}

.player-dossier-achievement,
.player-dossier-timeline-season {
    align-items: start;
    border-bottom: var(--border-width-default) solid var(--color-border);
    display: grid;
    gap: var(--space-sm);
    grid-template-columns: auto minmax(0, 1fr);
    padding: var(--space-sm) var(--space-md);
}

.player-dossier-achievement:last-child,
.player-dossier-timeline-season:last-child {
    border-bottom: 0;
}

.player-dossier-achievement-icon {
    align-items: center;
    border: var(--border-width-default) solid currentColor;
    color: var(--color-prestige-development);
    display: inline-flex;
    height: var(--touch-target-min);
    justify-content: center;
    width: var(--touch-target-min);
}

.player-dossier-achievement--landmark .player-dossier-achievement-icon {
    color: var(--color-prestige-elite);
}

.player-dossier-achievement--elite .player-dossier-achievement-icon {
    color: var(--color-prestige-starter);
}

.player-dossier-achievement--standout .player-dossier-achievement-icon {
    color: var(--color-prestige-contributor);
}

.player-dossier-achievement-copy,
.player-dossier-timeline-copy {
    display: grid;
    gap: var(--space-xs);
    min-width: 0;
}

.player-dossier-achievement-copy strong,
.player-dossier-timeline-year strong {
    color: var(--color-text-primary);
    font-size: var(--font-size-body);
}

.player-dossier-achievement-current,
.player-dossier-timeline-year span {
    border-left: var(--border-width-semantic) solid var(--color-opportunity);
    color: var(--color-text-secondary);
    font-size: var(--font-size-badge);
    padding-left: var(--space-xs);
    text-transform: uppercase;
}

.player-dossier-timeline-season {
    grid-template-columns: minmax(4rem, auto) minmax(0, 1fr);
}

.player-dossier-timeline-year {
    display: grid;
    gap: var(--space-xs);
}

.player-dossier-timeline-copy p {
    color: var(--color-text-secondary);
    font-size: var(--font-size-body);
    line-height: var(--line-height-body);
    margin: 0;
    overflow-wrap: anywhere;
}

div[data-testid="stDialog"] .player-quick-view-avatar {
    height: clamp(5rem, 18vw, 7rem) !important;
    width: clamp(5rem, 18vw, 7rem) !important;
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

    .player-dossier-executive-grid {
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

    .player-dossier-executive-metric,
    .player-dossier-resume-meta,
    .player-dossier-achievement,
    .player-dossier-timeline-season {
        padding-left: var(--space-sm);
        padding-right: var(--space-sm);
    }
}

@media (prefers-reduced-motion: reduce) {
    .player-dossier-snapshot *,
    .player-dossier-executive *,
    .player-dossier-career *,
    .player-dossier-recommendation-context * {
        animation: none !important;
        transition: none !important;
    }
}
"""
