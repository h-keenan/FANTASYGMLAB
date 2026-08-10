"""Final token-backed Founder Beta navigation and surface consistency layer."""

FOUNDER_BETA_QUICK_FIX_CSS = """

:root {
    --dg-founder-nav-width: min(calc(100vw - (2 * var(--space-md))), 390px);
    --dg-founder-nav-clearance: calc(var(--touch-target-min) + var(--space-xl));
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-floating-trigger-marker),
div[class*="st-key-mobile_gm_sheet_trigger_"] {
    bottom: max(var(--space-md), env(safe-area-inset-bottom, 0px)) !important;
    height: var(--touch-target-min) !important;
    left: max(var(--space-md), env(safe-area-inset-left, 0px)) !important;
    min-height: var(--touch-target-min) !important;
    min-width: var(--touch-target-min) !important;
    width: var(--touch-target-min) !important;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-floating-trigger-marker) [data-testid="stButton"],
div[class*="st-key-mobile_gm_sheet_trigger_"] [data-testid="stButton"] {
    background: transparent !important;
    border: 0 !important;
    border-radius: var(--radius-none) !important;
    box-shadow: var(--shadow-none) !important;
    box-sizing: border-box !important;
    height: var(--touch-target-min) !important;
    min-height: var(--touch-target-min) !important;
    min-width: var(--touch-target-min) !important;
    width: var(--touch-target-min) !important;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-floating-trigger-marker) [data-testid="stButton"] button,
div[class*="st-key-mobile_gm_sheet_trigger_"] [data-testid="stButton"] button {
    align-items: center !important;
    aspect-ratio: 1 / 1 !important;
    background-color: var(--color-shell) !important;
    border: var(--border-width-default) solid var(--color-border-strong) !important;
    border-left: var(--border-width-semantic) solid var(--color-accent) !important;
    border-radius: var(--radius-none) !important;
    box-shadow: var(--shadow-control) !important;
    box-sizing: border-box !important;
    color: transparent !important;
    display: flex !important;
    font-size: 0 !important;
    height: var(--touch-target-min) !important;
    justify-content: center !important;
    letter-spacing: 0 !important;
    line-height: 0 !important;
    min-height: var(--touch-target-min) !important;
    min-width: var(--touch-target-min) !important;
    max-width: var(--touch-target-min) !important;
    overflow: hidden !important;
    padding: 8px !important;
    text-transform: none !important;
    width: var(--touch-target-min) !important;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-floating-trigger-marker) [data-testid="stButton"] button:focus-visible,
div[class*="st-key-mobile_gm_sheet_trigger_"] [data-testid="stButton"] button:focus-visible {
    box-shadow: var(--focus-ring) !important;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) {
    background: var(--color-shell) !important;
    border: var(--border-width-default) solid var(--color-border-strong) !important;
    border-left: var(--border-width-semantic) solid var(--color-accent) !important;
    border-radius: var(--radius-none) !important;
    bottom: calc(max(var(--space-md), env(safe-area-inset-bottom, 0px)) + var(--dg-founder-nav-clearance)) !important;
    box-shadow: var(--shadow-overlay) !important;
    box-sizing: border-box !important;
    isolation: isolate !important;
    left: max(var(--space-md), env(safe-area-inset-left, 0px)) !important;
    max-height: min(72dvh, 640px) !important;
    max-width: var(--dg-founder-nav-width) !important;
    overscroll-behavior: contain !important;
    overflow-x: hidden !important;
    overflow-y: auto !important;
    padding: 0 !important;
    scrollbar-color: var(--color-border-strong) var(--color-shell);
    width: var(--dg-founder-nav-width) !important;
}

.mobile-gm-destination-panel {
    background: var(--color-surface-primary) !important;
    border: 0 !important;
    border-bottom: var(--border-width-default) solid var(--color-border) !important;
    border-radius: var(--radius-none) !important;
    box-shadow: var(--shadow-none) !important;
    margin: 0 !important;
    padding: var(--space-md) var(--space-lg) !important;
}

.mobile-gm-panel-header {
    gap: var(--space-xs) !important;
}

.mobile-gm-sheet-kicker,
.mobile-gm-current-page {
    color: var(--color-text-muted) !important;
    font-size: var(--type-section-eyebrow-size) !important;
    font-weight: var(--font-weight-metadata) !important;
    letter-spacing: var(--letter-spacing-badge) !important;
    line-height: var(--line-height-badge) !important;
    text-transform: uppercase !important;
}

.mobile-gm-sheet-title {
    color: var(--color-text-primary) !important;
    font: var(--type-section-title) !important;
    letter-spacing: -0.02em !important;
    margin: 0 !important;
    text-transform: uppercase !important;
}

.mobile-gm-sheet-note {
    color: var(--color-text-muted) !important;
    font: var(--type-supporting-metadata) !important;
    margin: var(--space-sm) 0 0 !important;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) {
    gap: 0 !important;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stCaptionContainer"] {
    background: var(--color-surface-muted) !important;
    border-bottom: var(--border-width-default) solid var(--color-border) !important;
    color: var(--color-text-muted) !important;
    font-size: var(--type-section-eyebrow-size) !important;
    font-weight: var(--font-weight-title) !important;
    letter-spacing: var(--letter-spacing-badge) !important;
    margin: 0 !important;
    padding: var(--space-sm) var(--space-lg) var(--space-xs) !important;
    text-transform: uppercase !important;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] {
    margin: 0 !important;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] > button {
    align-items: center !important;
    background: var(--color-surface-primary) !important;
    border: 0 !important;
    border-bottom: var(--border-width-default) solid var(--color-border) !important;
    border-left: var(--border-width-semantic) solid transparent !important;
    border-radius: var(--radius-none) !important;
    box-shadow: var(--shadow-none) !important;
    color: var(--color-text-secondary) !important;
    display: flex !important;
    font: var(--font-body) !important;
    font-weight: var(--font-weight-button) !important;
    justify-content: flex-start !important;
    min-height: var(--touch-target-min) !important;
    padding: var(--space-sm) var(--space-lg) !important;
    text-align: left !important;
    width: 100% !important;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] > button::after {
    color: var(--color-text-muted) !important;
    content: "›" !important;
    font-size: var(--font-size-body) !important;
    margin-left: auto !important;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] > button[kind="primary"] {
    background: var(--color-surface-raised) !important;
    border-left-color: var(--color-accent) !important;
    color: var(--color-text-primary) !important;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] > button[kind="primary"]::after {
    color: var(--color-accent) !important;
    content: "CURRENT" !important;
    font-size: var(--font-size-badge) !important;
    font-weight: var(--font-weight-title) !important;
    letter-spacing: var(--letter-spacing-badge) !important;
}

div[class*="st-key-mobile_sheet_close"] [data-testid="stButton"] > button {
    background: var(--color-surface-muted) !important;
    color: var(--color-text-muted) !important;
}

div[class*="st-key-mobile_sheet_close"] [data-testid="stButton"] > button::after {
    content: "×" !important;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] > button:hover {
    background: var(--color-surface-raised) !important;
    color: var(--color-text-primary) !important;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] > button:focus-visible {
    box-shadow: var(--focus-ring) !important;
    outline: none !important;
    position: relative;
    z-index: 1;
}

div[data-testid="stDialog"] {
    background: rgba(0, 0, 0, 0.72) !important;
}

div[data-testid="stDialog"] > div {
    border-radius: var(--radius-none) !important;
}

div[data-testid="stDialog"] > div > div[role="dialog"],
div[role="dialog"] {
    background: var(--color-shell) !important;
    border: var(--border-width-default) solid var(--color-border-strong) !important;
    border-radius: var(--radius-none) !important;
    box-shadow: var(--shadow-overlay) !important;
    box-sizing: border-box !important;
    max-height: min(90dvh, 920px) !important;
    overflow: hidden !important;
    padding: var(--space-lg) !important;
}

div[data-testid="stDialog"] > div > div[role="dialog"] > div:first-child,
div[data-testid="stDialog"] > div > div[role="dialog"] > div:last-child,
div[role="dialog"] > div:first-child,
div[role="dialog"] > div:last-child {
    background: var(--color-shell) !important;
    border-radius: var(--radius-none) !important;
}

div[data-testid="stDialog"] > div > div[role="dialog"] > div:last-child,
div[role="dialog"] > div:last-child {
    max-height: calc(90dvh - (2 * var(--space-lg))) !important;
    overflow-x: hidden !important;
    overflow-y: auto !important;
    overscroll-behavior: contain !important;
}

div[data-testid="stDialog"] button[aria-label="Close"] {
    border-radius: var(--radius-none) !important;
    min-height: var(--touch-target-min) !important;
    min-width: var(--touch-target-min) !important;
}

div[data-testid="stDialog"] h2 {
    font: var(--type-section-title) !important;
    margin: 0 !important;
    padding-right: calc(var(--touch-target-min) + var(--space-sm)) !important;
}

:is(
    .dg-ui-card,
    .dg-ui-callout,
    .dg-ui-empty-state,
    .summary-tile,
    .dg-intelligence-item,
    .trade-summary-card,
    .free-agent-card,
    .trade-detail-modal,
    .trade-detail-modal .trade-side,
    .trade-detail-modal .trade-asset-row,
    .player-quick-view-hero,
    .player-quick-view-header-band.player-quick-view-hero,
    .player-dossier-snapshot,
    .player-dossier-career,
    .player-dossier-recommendation-context,
    div[data-testid="stExpander"],
    [data-testid="stAlert"]
) {
    border-radius: var(--radius-panel) !important;
}

:is(
    [data-testid="stButton"] > button,
    [data-testid="stDownloadButton"] > button,
    [data-testid="stFormSubmitButton"] > button,
    [data-testid="stPopover"] > button,
    [data-baseweb="select"] > div,
    [data-baseweb="input"] > div,
    [data-baseweb="textarea"] > div
) {
    border-radius: var(--radius-none) !important;
}

.dg-ui-section-header,
.section-header {
    margin: var(--space-lg) 0 var(--space-sm) !important;
}

.dg-intelligence-group {
    margin: var(--space-lg) 0 var(--space-xs) !important;
}

.dg-intelligence-item {
    background: var(--color-surface-muted) !important;
    border-left-color: var(--color-border-strong) !important;
    gap: var(--space-sm) !important;
    padding: var(--space-md) !important;
}

.dg-intelligence-item--primary {
    background: var(--color-surface-primary) !important;
    border-left-color: var(--color-information) !important;
}

@media (max-width: 700px) {
    div[data-testid="stDialog"] > div > div[role="dialog"],
    div[role="dialog"] {
        max-height: calc(100dvh - (2 * var(--space-sm))) !important;
        max-width: calc(100vw - (2 * var(--space-sm))) !important;
        padding:
            var(--space-md)
            max(var(--space-md), env(safe-area-inset-right))
            max(var(--space-md), env(safe-area-inset-bottom))
            max(var(--space-md), env(safe-area-inset-left)) !important;
        width: calc(100vw - (2 * var(--space-sm))) !important;
    }

    div[data-testid="stDialog"] > div > div[role="dialog"] > div:last-child,
    div[role="dialog"] > div:last-child {
        max-height: calc(100dvh - (4 * var(--space-md))) !important;
    }

    .dg-ui-section-header,
    .section-header {
        margin-top: var(--space-md) !important;
    }

    .trade-detail-modal .trade-asset-row {
        align-items: flex-start !important;
        flex-direction: column !important;
        gap: var(--space-xs) !important;
    }

    .trade-detail-modal .trade-asset-name,
    .trade-detail-modal .trade-asset-meta {
        max-width: 100% !important;
        overflow-wrap: break-word !important;
        width: 100% !important;
    }
}

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
    .dg-command-header { grid-template-columns: 3rem minmax(0, 1fr) !important; }
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
    .dg-command-header .dg-workspace-sync { display: none !important; }
    .dg-command-header .dg-workspace-league {
        font-size: var(--font-size-body) !important;
        margin-top: 0 !important;
    }
}
"""
