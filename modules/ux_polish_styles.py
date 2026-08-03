FOUNDER_BETA_UX_CSS = """
<style>
:root {
    --dg-ux-radius: var(--radius-panel);
    --dg-ux-card-pad: var(--space-md);
    --dg-ux-section-gap: var(--space-md);
    --dg-ux-control-height: var(--control-min-height);
    --dg-ux-focus-ring: var(--focus-ring);
    --dg-ux-small-type: var(--font-size-caption);
}

.league-switch-card-grid {
    display: grid;
    gap: var(--space-sm);
    margin: var(--space-sm) 0 var(--space-md);
}

.league-switch-card {
    appearance: none;
    background: var(--color-surface-primary);
    border: var(--border-width-default) solid var(--color-border);
    border-radius: var(--dg-ux-radius);
    color: var(--color-text-primary);
    cursor: pointer;
    display: grid;
    gap: var(--space-xs);
    min-height: var(--touch-target-min);
    padding: var(--space-md);
    text-align: left;
    touch-action: manipulation;
    width: 100%;
}

.league-switch-card:hover,
.league-switch-card:focus-visible {
    border-color: var(--color-accent);
    box-shadow: var(--dg-ux-focus-ring);
    outline: none;
}

.league-switch-card-current {
    background: var(--color-information-soft);
    border-color: var(--color-accent);
}

.league-switch-card-loading {
    cursor: wait;
    opacity: 0.72;
}

.league-switch-card-title {
    font: var(--font-card-title);
    overflow-wrap: anywhere;
}

.league-switch-card-meta {
    color: var(--color-text-muted);
    font-size: var(--dg-ux-small-type);
    line-height: var(--line-height-caption);
}

.league-switch-card-badges {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-xs);
    margin-top: var(--space-xs);
}

.league-switch-card-badge,
.injury-adjustment-badge {
    align-items: center;
    border: var(--border-width-default) solid var(--color-border-strong);
    border-radius: var(--radius-pill);
    display: inline-flex;
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    line-height: var(--line-height-badge);
    min-height: var(--space-xl);
    padding: var(--space-xs) var(--space-sm);
    text-transform: uppercase;
}

.league-switch-card-badge-current {
    background: var(--color-information-soft);
    border-color: var(--color-information);
    color: var(--color-text-primary);
}

.league-switch-card-badge-default {
    background: var(--color-muted-soft);
    color: var(--color-text-secondary);
}

.injury-adjustment-badge {
    background: var(--color-warning-soft);
    border-color: var(--color-warning);
    color: var(--color-text-primary);
    margin-left: var(--space-xs);
    vertical-align: middle;
}

.home-command-card-dot,
.summary-tile-dot {
    display: none !important;
}

body:has(.league-actions-sheet-marker) div[data-testid="stPopoverContent"] {
    max-height: min(72dvh, 620px) !important;
    max-width: min(calc(100vw - 24px), 410px) !important;
    overflow-x: hidden !important;
    overflow-y: auto !important;
    padding: var(--space-md) !important;
    width: min(calc(100vw - 24px), 410px) !important;
}

.league-actions-sheet-marker {
    height: 0;
    overflow: hidden;
}

.league-actions-section {
    border-top: var(--border-width-default) solid var(--color-border);
    margin-top: var(--space-md);
    padding-top: var(--space-md);
}

.league-actions-section:first-of-type {
    border-top: 0;
    margin-top: 0;
    padding-top: 0;
}

@media (max-width: 900px) {
    [data-testid="stMainBlockContainer"] {
        padding-left: var(--space-md) !important;
        padding-right: var(--space-md) !important;
    }

    [data-testid="stVerticalBlock"] {
        gap: var(--dg-ux-section-gap);
    }

    .analysis-card,
    .decision-panel,
    .home-command-card,
    .summary-tile,
    .trade-card,
    .free-agent-card,
    .live-rank-row,
    .live-draft-rec-card,
    .draft-review-pick-card {
        border-radius: var(--dg-ux-radius) !important;
        max-width: 100% !important;
        overflow-wrap: anywhere;
    }

    .analysis-card,
    .decision-panel,
    .home-command-card,
    .summary-tile,
    .trade-card,
    .free-agent-card {
        padding: var(--dg-ux-card-pad) !important;
    }

    [data-testid="stButton"] > button,
    [data-testid="stPopover"] > button,
    [data-testid="stFormSubmitButton"] > button {
        min-height: var(--dg-ux-control-height) !important;
    }

    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea,
    [data-baseweb="select"] input,
    [data-baseweb="select"] > div {
        font-size: 16px !important;
    }

    [data-testid="stButton"] > button:focus-visible,
    [data-testid="stPopover"] > button:focus-visible,
    [data-testid="stFormSubmitButton"] > button:focus-visible,
    [role="button"]:focus-visible,
    [role="tab"]:focus-visible {
        box-shadow: var(--dg-ux-focus-ring) !important;
        outline: none !important;
    }

    img {
        max-width: 100%;
    }

    .home-command-card-note,
    .summary-tile-note,
    .live-draft-rec-reason,
    .live-rank-reason {
        font-size: var(--dg-ux-small-type) !important;
        line-height: var(--line-height-caption) !important;
    }

    .trade-card-kicker,
    .trade-card-subtitle,
    .trade-side-header,
    .trade-asset-meta,
    .trade-delta-label,
    .trade-card-value-strip,
    .live-rank-meta,
    .live-rank-score small,
    .summary-tile-kicker,
    .summary-tile-note,
    .player-support-chip,
    .player-status-pill,
    .dg-glyph-chip,
    .dg-tier-chip {
        font-size: var(--dg-ux-small-type) !important;
        line-height: var(--line-height-caption) !important;
    }

    div[data-testid="stHorizontalBlock"]:has(div[class*="st-key-launch_choose_account"]),
    div[data-testid="stHorizontalBlock"]:has(div[class*="st-key-launch_account_login_button"]) {
        align-items: stretch !important;
        flex-direction: column !important;
    }

    body:has(.mobile-gm-sheet-marker) div[class*="_global_feedback_control"],
    body:has(.league-actions-sheet-marker) div[class*="st-key-mobile_gm_sheet_trigger_"],
    body:has(.league-actions-sheet-marker) div[class*="_global_feedback_control"] {
        pointer-events: none !important;
        visibility: hidden !important;
    }

    body:has(div[data-testid="stDialog"]) div[class*="st-key-mobile_gm_sheet_trigger_"],
    body:has(div[data-testid="stDialog"]) div[class*="_global_feedback_control"] {
        display: none !important;
    }
}

/* Canonical command header: one compact product/league landmark. */
.dg-command-header {
    grid-template-columns: 4rem minmax(12rem, 1fr) minmax(14rem, .8fr) !important;
}

.dg-command-header .dg-ops-rail,
.dg-command-header .dg-workspace-page.dg-ops-briefing,
.dg-command-header .dg-workspace-context.dg-ops-league-context {
    min-height: 0 !important;
    padding: var(--space-md) !important;
}

.dg-command-header .dg-workspace-page-title {
    font-size: clamp(1.75rem, 4vw, 2.8rem) !important;
    line-height: 1 !important;
    margin-top: var(--space-xs) !important;
}

@media (max-width: 700px) {
    .dg-command-header {
        grid-template-columns: 3rem minmax(0, 1fr) !important;
    }

    .dg-command-header .dg-workspace-page.dg-ops-briefing {
        min-height: 4.5rem !important;
        padding: var(--space-sm) var(--space-md) !important;
    }

    .dg-command-header .dg-workspace-context.dg-ops-league-context {
        gap: var(--space-xs) !important;
        grid-column: 2 !important;
        grid-template-columns: minmax(0, 1fr) !important;
        padding: 0 var(--space-md) var(--space-sm) !important;
    }

    .dg-command-header .dg-workspace-avatar,
    .dg-command-header .dg-workspace-team,
    .dg-command-header .dg-workspace-sync {
        display: none !important;
    }

    .dg-command-header .dg-workspace-league {
        font-size: var(--font-size-body) !important;
        margin-top: 0 !important;
    }
}

@media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        scroll-behavior: auto !important;
        transition-duration: 0.01ms !important;
    }
}
</style>
"""
