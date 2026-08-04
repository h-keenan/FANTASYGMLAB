"""Presentation-only visual hierarchy: executive scanning without equal-weight noise."""

VISUAL_HIERARCHY_CSS = """
/* Executive command bar: one visual band for identity + league action. */
div[class*="st-key-executive_workspace_shell"] {
    background: var(--color-surface-primary) !important;
    border: var(--border-width-default) solid var(--color-border-strong) !important;
    border-radius: var(--radius-panel) !important;
    gap: 0 !important;
    margin-block-end: var(--space-xl) !important;
    overflow: hidden;
    padding: 0 !important;
}

div[class*="st-key-executive_workspace_shell"] .dg-executive-shell {
    background: transparent;
    border: 0;
    border-radius: 0;
    min-height: var(--touch-target-min);
    padding: var(--space-sm) var(--space-md);
}

div[class*="st-key-executive_workspace_shell"] div[class*="st-key-top_league_actions"] {
    align-self: stretch;
    border-inline-start: var(--border-width-default) solid var(--color-border);
    display: flex;
    margin: 0;
}

div[class*="st-key-executive_workspace_shell"] div[class*="st-key-top_league_actions"] [data-testid="stPopover"],
div[class*="st-key-executive_workspace_shell"] div[class*="st-key-top_league_actions"] [data-testid="stPopover"] button {
    background: transparent !important;
    border: 0 !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    height: 100%;
    min-height: var(--touch-target-min);
}

div[class*="st-key-executive_workspace_shell"] div[class*="st-key-top_league_actions"] [data-testid="stPopover"] button:hover {
    background: var(--color-surface-raised) !important;
}

div[class*="st-key-executive_workspace_shell"] div[class*="st-key-top_league_actions"] [data-testid="stPopover"] button:focus-visible {
    box-shadow: var(--focus-ring) !important;
}

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

/* Desktop composition: intentional width and breathing room. */
@media (min-width: 1024px) {
    .block-container {
        padding-inline: var(--space-2xl) !important;
    }

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
    div[class*="st-key-executive_workspace_shell"] {
        margin-block-end: var(--space-md) !important;
    }

    div[class*="st-key-executive_workspace_shell"] div[class*="st-key-top_league_actions"] {
        border-inline-start: 0;
        border-block-start: var(--border-width-default) solid var(--color-border);
    }

    .dg-ui-section-title,
    .section-title {
        font-size: clamp(1rem, 4.4vw, 1.18rem) !important;
    }

    .home-command-card-primary .home-command-card-value,
    .home-command-card-wide .home-command-card-value {
        font-size: clamp(1.15rem, 5vw, 1.35rem) !important;
    }
}

@media (prefers-reduced-motion: reduce) {
    .home-command-card-primary,
    .home-command-card-secondary,
    .summary-tile,
    div[class*="st-key-executive_workspace_shell"] {
        transition: none !important;
    }
}
"""
