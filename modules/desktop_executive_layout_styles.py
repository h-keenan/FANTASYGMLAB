"""Release-candidate desktop composition and final UI consistency layer.

Presentation only — no football, entitlement, billing, or auth logic.
Loaded last so it unifies width, gutters, hierarchy, GM Orb, and transitions.
"""

DESKTOP_EXECUTIVE_LAYOUT_CSS = """

:root {
    --dg-exec-content-max: 1180px;
    --dg-exec-content-max-wide: 1220px;
    --dg-exec-content-max-ultra: 1280px;
    --dg-exec-gutter: var(--space-2xl);
    --dg-exec-section-gap: var(--space-xl);
    --dg-exec-column-gap: var(--space-md);
}

.block-container {
    margin-inline: auto !important;
    max-width: var(--dg-exec-content-max) !important;
    padding-block-start: 0 !important;
    padding-inline: var(--dg-exec-gutter) !important;
    width: 100% !important;
}

@media (min-width: 1024px) {
    .block-container {
        max-width: var(--dg-exec-content-max) !important;
        padding-block-start: 0 !important;
        padding-inline: var(--dg-exec-gutter) !important;
    }

    [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {
        gap: var(--space-md) !important;
    }


    .home-command-grid {
        gap: var(--dg-exec-column-gap) !important;
        grid-template-columns: repeat(12, minmax(0, 1fr)) !important;
    }

    .home-command-card,
    .home-command-card-secondary {
        grid-column: span 4;
    }

    .home-command-card-primary,
    .home-command-card-wide {
        grid-column: span 8 !important;
    }


    .home-command-card:first-child:not(.home-command-card-primary):not(.home-command-card-wide) {
        grid-column: span 4 !important;
    }


    .st-key-dashboard_workflow .home-command-card-primary,
    .st-key-dashboard_workflow .home-command-card-wide {
        grid-column: span 8 !important;
    }

    .st-key-dashboard_workflow .home-command-card-secondary {
        grid-column: span 4 !important;
        opacity: 0.94;
    }

    .st-key-dashboard_workflow .home-command-card-secondary.home-command-card-risk,
    .st-key-dashboard_workflow .home-command-card-secondary.home-command-card-need {
        border-inline-start: var(--border-width-semantic) solid var(--color-warning);
        opacity: 1;
    }

    .summary-tile-grid,
    .summary-tile-grid-compact,
    .decision-panel-grid,
    .analysis-grid {
        gap: var(--dg-exec-column-gap) !important;
        grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
    }

    .home-hero-stats {
        grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
    }


    main:has(.dg-page-shell--trade-hub) .trade-summary-card,
    main:has(.dg-page-shell--trade-hub) .trade-idea-card {
        max-width: 100%;
    }


    main:has(.dg-page-shell--waivers) .waiver-board,
    main:has(.dg-page-shell--waivers) .free-agent-list {
        max-width: 100%;
    }


    .dg-intelligence-item {
        align-items: start;
        column-gap: var(--space-lg);
        grid-template-columns: minmax(12rem, 17rem) minmax(0, 1fr) !important;
    }


    .live-draft-hero,
    .live-draft-command,
    .live-draft-board {
        border-radius: var(--radius-panel) !important;
        max-width: 100%;
    }


    .premium-page {
        margin-inline: auto;
        max-width: 56rem;
    }


    .dg-ui-section-header,
    .section-header,
    .home-action-center-label,
    .home-league-pulse-label {
        margin-block: var(--dg-exec-section-gap) var(--space-sm) !important;
    }

    .dg-ui-section-title,
    .section-title,
    .home-action-center-label,
    .home-league-pulse-label {
        color: var(--color-text-primary) !important;
        font-size: clamp(1.15rem, 1.4vw, 1.4rem) !important;
        font-weight: var(--font-weight-display) !important;
        letter-spacing: -0.02em !important;
        text-transform: none !important;
    }

    .dg-ui-eyebrow,
    .section-kicker,
    .home-command-kicker {
        color: var(--color-text-muted) !important;
        font-size: var(--font-size-badge) !important;
        letter-spacing: var(--letter-spacing-badge) !important;
        opacity: var(--opacity-metadata);
        text-transform: uppercase;
    }

    .dg-ui-section-subtitle,
    .section-note,
    .home-command-meta {
        color: var(--color-text-muted) !important;
        font-size: var(--font-size-caption) !important;
        max-width: 44rem;
    }
}

@media (min-width: 1440px) {
    :root {
        --dg-exec-content-max: var(--dg-exec-content-max-wide);
        --dg-exec-gutter: var(--space-3xl);
    }

    .block-container {
        max-width: var(--dg-exec-content-max-wide) !important;
        padding-inline: var(--dg-exec-gutter) !important;
    }

    .home-command-grid {
        gap: var(--space-lg) !important;
    }

    .summary-tile-grid,
    .summary-tile-grid-compact,
    .decision-panel-grid,
    .analysis-grid {
        gap: var(--space-lg) !important;
    }
}

@media (min-width: 1600px) {
    .block-container {
        max-width: var(--dg-exec-content-max-ultra) !important;
        margin-inline: auto !important;
    }
}

@media (min-width: 1800px) {
    .block-container {
        max-width: var(--dg-exec-content-max-ultra) !important;
    }
}

.section-header {
    background: transparent !important;
    border: 0 !important;
    border-block-end: var(--border-width-default) solid var(--color-border) !important;
    border-radius: var(--radius-none) !important;
    box-shadow: none !important;
    padding: 0 0 var(--space-sm) !important;
}

.summary-tile,
.decision-panel,
.analysis-card,
.free-agent-card,
.waiver-card,
.dg-intelligence-item,
.trade-summary-card,
.home-command-card {
    border-radius: var(--radius-panel) !important;
}

.summary-tile,
.decision-panel-reference,
.analysis-card {
    box-shadow: none !important;
}

.dg-ui-caption,
.stCaptionContainer p,
[data-testid="stCaptionContainer"] p {
    color: var(--color-text-muted) !important;
    font-size: var(--font-size-caption) !important;
    line-height: var(--line-height-caption) !important;
}

.home-command-card-label,
.summary-tile-label,
.decision-panel-label,
.trade-summary-partner,
.dg-intelligence-item__meta {
    color: var(--color-text-muted) !important;
    font-size: var(--font-size-badge) !important;
    letter-spacing: var(--letter-spacing-badge) !important;
    opacity: var(--opacity-metadata);
    text-transform: uppercase;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-floating-trigger-marker),
div[class*="st-key-mobile_gm_sheet_trigger_"] {
    z-index: 46;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-floating-trigger-marker) [data-testid="stButton"] button,
div[class*="st-key-mobile_gm_sheet_trigger_"] [data-testid="stButton"] button {
    border-radius: var(--radius-panel) !important;
    min-height: var(--touch-target-min) !important;
    min-width: var(--touch-target-min) !important;
    transition:
        background-color 140ms ease,
        border-color 140ms ease,
        box-shadow 140ms ease,
        transform 140ms ease !important;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-floating-trigger-marker) [data-testid="stButton"] button:hover,
div[class*="st-key-mobile_gm_sheet_trigger_"] [data-testid="stButton"] button:hover {
    /* Keep transform none — translateY pushes the orb toward/past the viewport edge. */
    transform: none;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-floating-trigger-marker) [data-testid="stButton"] button:focus-visible,
div[class*="st-key-mobile_gm_sheet_trigger_"] [data-testid="stButton"] button:focus-visible {
    box-shadow: var(--focus-ring) !important;
    outline: none !important;
}

body:has(.mobile-gm-sheet-marker)::before {
    background: color-mix(in srgb, var(--color-bg) 72%, transparent);
    content: "";
    inset: 0;
    pointer-events: none;
    position: fixed;
    z-index: 40;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) {
    animation: dg-gm-sheet-enter 160ms ease-out;
    background: var(--color-shell) !important;
    border: var(--border-width-default) solid var(--color-border-strong) !important;
    border-radius: var(--radius-panel) !important;
    box-shadow: var(--shadow-overlay) !important;
    padding: var(--space-md) !important;
    z-index: 45 !important;
}

.mobile-gm-destination-panel,
.mobile-gm-panel-header {
    gap: var(--space-xs);
    margin-block-end: var(--space-sm);
}

.mobile-gm-sheet-kicker {
    color: var(--color-accent) !important;
    font-size: var(--font-size-badge) !important;
    font-weight: var(--font-weight-title) !important;
    letter-spacing: var(--letter-spacing-badge) !important;
    text-transform: uppercase;
}

.mobile-gm-sheet-title {
    color: var(--color-text-primary) !important;
    font-size: var(--font-size-page-title) !important;
    font-weight: var(--font-weight-display) !important;
    letter-spacing: -0.02em;
    line-height: var(--line-height-title);
}

.mobile-gm-current-page {
    color: var(--color-text-secondary) !important;
    font-size: var(--font-size-caption) !important;
}

.mobile-gm-sheet-note {
    color: var(--color-text-muted) !important;
    font-size: var(--font-size-caption) !important;
    line-height: var(--line-height-caption);
}

.mobile-gm-experimental-note {
    border-inline-start: var(--border-width-semantic) solid var(--color-warning);
    color: var(--color-text-muted) !important;
    font-size: var(--font-size-caption) !important;
    margin: var(--space-xs) 0 var(--space-sm);
    padding-inline-start: var(--space-sm);
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] > button {

    min-height: calc(var(--touch-target-min) + 1px) !important;
    border-radius: var(--radius-panel) !important;
    box-sizing: border-box !important;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] > button[kind="primary"] {
    border-color: var(--color-accent) !important;
    box-shadow: var(--shadow-surface-inset) !important;
}

@keyframes dg-gm-sheet-enter {
    from {
        opacity: 0;
        transform: translateY(8px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.league-switch-card {
    transition:
        opacity 120ms ease,
        border-color 120ms ease,
        background-color 120ms ease !important;
}

.league-switch-card-loading {
    background: var(--color-information-soft) !important;
    border-color: var(--color-accent) !important;
    cursor: wait !important;
    opacity: 0.78 !important;
    pointer-events: none;
}

.league-switch-card-loading .league-switch-card-meta {
    color: var(--color-accent) !important;
    font-weight: var(--font-weight-title);
}

.dg-shell-ack,
.dg-league-switch-ack {
    align-items: center;
    animation: dg-league-switch-ack-fade 2.4s ease forwards;
    background: var(--color-information-soft);
    border: var(--border-width-default) solid var(--color-border);
    border-inline-start: var(--border-width-semantic) solid var(--color-information);
    color: var(--color-text-secondary);
    display: flex;
    font-size: var(--font-size-caption);
    gap: var(--space-sm);
    line-height: var(--line-height-caption);
    margin: 0 0 var(--space-sm);
    max-width: 42rem;
    padding: var(--space-xs) var(--space-sm);
}
.dg-shell-ack__label,
.dg-league-switch-ack__label {
    color: var(--color-text-primary);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
    white-space: nowrap;
}

@keyframes dg-league-switch-ack-fade {
    0%, 70% { opacity: 1; }
    100% { opacity: 0; max-height: 0; margin: 0; padding-block: 0; overflow: hidden; }
}

@media (max-width: 760px) {
    .block-container {
        max-width: 100% !important;
        padding-inline: var(--space-md) !important;
    }

    .home-command-grid,
    .summary-tile-grid,
    .summary-tile-grid-compact,
    .decision-panel-grid,
    .analysis-grid {
        grid-template-columns: minmax(0, 1fr) !important;
    }

    .home-command-card,
    .home-command-card-primary,
    .home-command-card-wide,
    .home-command-card-secondary,
    .home-command-card:first-child {
        grid-column: span 1 !important;
    }

    .dg-intelligence-item {
        grid-template-columns: minmax(0, 1fr) !important;
    }

    body:has(.mobile-gm-sheet-marker)::before {
        background: color-mix(in srgb, var(--color-bg) 78%, transparent);
    }
}

@media (min-width: 768px) and (max-width: 1023px) {
    .block-container {
        max-width: 100% !important;
        padding-inline: var(--space-xl) !important;
    }

    .home-command-grid {
        grid-template-columns: repeat(6, minmax(0, 1fr)) !important;
    }

    .home-command-card,
    .home-command-card-secondary {
        grid-column: span 3;
    }

    .home-command-card-primary,
    .home-command-card-wide {
        grid-column: span 6 !important;
    }

    .home-command-card:first-child:not(.home-command-card-primary):not(.home-command-card-wide) {
        grid-column: span 3 !important;
    }

    .summary-tile-grid,
    .summary-tile-grid-compact,
    .decision-panel-grid,
    .analysis-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    }

}

@media (prefers-reduced-motion: reduce) {
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker),
    .league-switch-card,
    .dg-shell-ack,
    .dg-league-switch-ack,
    div[class*="st-key-mobile_gm_sheet_trigger_"] [data-testid="stButton"] button {
        animation: none !important;
        transition: none !important;
    }
}
"""
