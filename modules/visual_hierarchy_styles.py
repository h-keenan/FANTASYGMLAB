"""Presentation-only visual hierarchy: executive scanning without equal-weight noise."""

VISUAL_HIERARCHY_CSS = """
/* Header shell geometry is owned solely by APPLICATION_SHELL_CSS.
   Command-cell geometry is owned solely by EXECUTIVE_COMMAND_HEADER_CSS.
   Do not reintroduce shell padding/height/border here. */

/* Section headers orient; they must not overpower primary decisions. */
.dg-ui-section-header,
.section-header {
    margin-block: var(--space-lg) var(--space-sm) !important;
}

.dg-ui-eyebrow,
.section-kicker {
    color: var(--color-text-muted) !important;
    font-size: var(--font-size-badge) !important;
    font-weight: var(--font-weight-title) !important;
    letter-spacing: var(--letter-spacing-badge) !important;
    opacity: 0.84;
}

.dg-ui-section-title,
.section-title {
    color: var(--color-text-secondary) !important;
    font-size: clamp(1.05rem, 2.4vw, 1.28rem) !important;
    font-weight: var(--font-weight-title) !important;
    letter-spacing: 0.01em !important;
    text-transform: none !important;
}

.dg-ui-section-subtitle,
.section-note {
    color: var(--color-text-muted) !important;
    font-size: var(--font-size-caption) !important;
    line-height: var(--line-height-caption) !important;
    max-width: 42rem;
}

/* Primary decision cards dominate secondary peers. */
.home-command-card-primary,
.home-command-card-wide {
    background:
        linear-gradient(180deg, var(--color-surface-raised), var(--color-surface-primary)) !important;
    border-color: var(--color-border-strong) !important;
    border-inline-start: var(--border-width-semantic) solid var(--color-opportunity) !important;
    box-shadow: var(--shadow-surface-inset) !important;
    padding: var(--space-md) var(--space-lg) !important;
}

.home-command-card-primary .home-command-card-value,
.home-command-card-wide .home-command-card-value {
    color: var(--color-text-primary) !important;
    font-size: clamp(1.2rem, 2.6vw, 1.55rem) !important;
    font-weight: var(--font-weight-display) !important;
    line-height: var(--line-height-title) !important;
    margin-top: var(--space-xs) !important;
}

.home-command-card-primary .home-command-card-note,
.home-command-card-wide .home-command-card-note {
    color: var(--color-text-secondary) !important;
    font-size: var(--font-size-body) !important;
    margin-top: var(--space-sm) !important;
}

.home-command-card-secondary {
    background: var(--color-surface-primary) !important;
    border-color: var(--color-border) !important;
    box-shadow: none !important;
    opacity: 0.96;
    padding: var(--space-sm) var(--space-md) !important;
}

.home-command-card-secondary.home-command-card-risk,
.home-command-card-secondary.home-command-card-need {
    border-inline-start: var(--border-width-semantic) solid var(--color-warning);
    opacity: 1;
}

.home-command-card-secondary.home-command-card-risk .home-command-card-value,
.home-command-card-secondary.home-command-card-need .home-command-card-value {
    color: var(--color-text-primary) !important;
}

.home-command-card-secondary .home-command-card-label {
    color: var(--color-text-muted) !important;
    font-size: var(--font-size-badge) !important;
}

.home-command-card-secondary .home-command-card-value {
    color: var(--color-text-secondary) !important;
    font-size: var(--font-size-body) !important;
    font-weight: var(--font-weight-title) !important;
}

.home-command-card-secondary .home-command-card-note {
    color: var(--color-text-muted) !important;
    font-size: var(--font-size-caption) !important;
}

/* Supporting summary tiles stay quieter than decisions. */
.summary-tile {
    background: var(--color-surface-primary) !important;
    border-color: var(--color-border) !important;
    box-shadow: none !important;
    padding: var(--space-sm) var(--space-md) !important;
}

.summary-tile-label {
    color: var(--color-text-muted) !important;
    font-size: var(--font-size-badge) !important;
    letter-spacing: var(--letter-spacing-badge) !important;
    text-transform: uppercase;
}

.summary-tile-value {
    color: var(--color-text-secondary) !important;
    font-size: var(--font-size-body) !important;
    font-weight: var(--font-weight-title) !important;
}

.summary-tile-note {
    color: var(--color-text-muted) !important;
    font-size: var(--font-size-caption) !important;
}

.summary-tile.dg-card-primary {
    border-inline-start: var(--border-width-semantic) solid var(--color-information);
}

/* Decision panels: primary strip stronger than reference panels. */
.decision-panel-strength,
.decision-panel-risk {
    border-inline-start-width: var(--border-width-semantic);
}

.decision-panel-reference {
    border-color: var(--color-border) !important;
    box-shadow: none !important;
    opacity: 0.94;
}

/* Trade board: first card already primary; quiet secondary tiers. */
.trade-idea-secondary.trade-summary-card,
.trade-summary-card.trade-idea-secondary {
    border-color: var(--color-border) !important;
    opacity: 0.92;
}

.trade-summary-card:not(.trade-idea-secondary) {
    border-inline-start-width: var(--border-width-semantic);
}

/* Desktop card type scale — content width/gutters owned by DESKTOP_EXECUTIVE. */
@media (min-width: 1024px) {
    .home-command-grid {
        gap: var(--space-md);
    }

    .summary-tile-grid,
    .summary-tile-grid-compact {
        gap: var(--space-md);
    }

    .home-command-card-primary .home-command-card-value,
    .home-command-card-wide .home-command-card-value {
        font-size: clamp(1.35rem, 1.6vw, 1.7rem) !important;
    }
}

@media (max-width: 760px) {
    .dg-ui-section-title,
    .section-title {
        font-size: clamp(1rem, 4.4vw, 1.18rem) !important;
    }

    .home-command-card-primary .home-command-card-value,
    .home-command-card-wide .home-command-card-value {
        font-size: clamp(1.15rem, 5vw, 1.35rem) !important;
    }
}

.dg-disclosure-hint {
    color: var(--color-text-muted);
    font-size: var(--font-size-caption);
    font-weight: var(--font-weight-metadata);
    margin-inline-start: var(--space-sm);
}

.st-key-my_team_roster_actions .home-command-grid {
    align-items: start;
}

.st-key-my_team_roster_actions .home-command-card {
    align-self: start;
    height: auto;
}

@media (max-width: 760px) {
    .st-key-my_team_roster_actions .home-command-grid {
        grid-template-columns: minmax(0, 1fr) !important;
    }

    .st-key-my_team_roster_actions .home-command-card,
    .st-key-my_team_roster_actions .home-command-card-wide,
    .st-key-my_team_roster_actions .home-command-card-primary {
        grid-column: span 1 !important;
    }
}

@media (prefers-reduced-motion: reduce) {
    .home-command-card-primary,
    .home-command-card-secondary,
    .summary-tile {
        transition: none !important;
    }
}
"""
