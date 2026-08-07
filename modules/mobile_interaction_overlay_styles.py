"""Mobile interaction overlay contract — layering, touch targets, safe areas.

Loaded last so it wins over legacy GM / popover geometry. Presentation only.
"""

MOBILE_INTERACTION_OVERLAY_CSS = """
:root {
    --dg-overlay-z-nav: 1001000;
    --dg-overlay-z-sheet: 1001005;
    --dg-overlay-z-popover: 1001010;
    --dg-overlay-z-modal: 1001020;
}
.mobile-gm-orb-hint { display: none !important; }
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-floating-trigger-marker),
div[class*="st-key-mobile_gm_sheet_trigger_"] {
    bottom: max(var(--space-md), env(safe-area-inset-bottom, 0px)) !important;
    left: max(var(--space-md), env(safe-area-inset-left, 0px)) !important;
    position: fixed !important;
    z-index: var(--dg-overlay-z-nav) !important;
}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-floating-trigger-marker) [data-testid="stButton"] > button,
div[class*="st-key-mobile_gm_sheet_trigger_"] [data-testid="stButton"] > button {
    border-radius: var(--radius-none) !important;
    font-size: var(--font-size-badge) !important;
    font-weight: var(--font-weight-display) !important;
    letter-spacing: var(--letter-spacing-badge) !important;
    line-height: 1 !important;
    min-height: var(--touch-target-min) !important;
    min-width: var(--touch-target-min) !important;
    padding: 0 var(--space-sm) !important;
    text-transform: uppercase !important;
    white-space: nowrap !important;
    writing-mode: horizontal-tb !important;
    word-break: keep-all !important;
}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) {
    z-index: var(--dg-overlay-z-sheet) !important;
}
div[data-testid="stDialog"]:has(.dg-notification-panel) {
    isolation: isolate !important;
    z-index: var(--dg-overlay-z-modal) !important;
}
body:has(div[data-testid="stDialog"] .dg-notification-panel) div[class*="st-key-mobile_gm_sheet_trigger_"],
body:has(.dg-notification-panel) div[class*="st-key-mobile_gm_sheet_trigger_"],
body:has(.league-actions-sheet-marker) div[class*="st-key-mobile_gm_sheet_trigger_"],
body:has(.dg-profile-panel) div[class*="st-key-mobile_gm_sheet_trigger_"] {
    opacity: 0 !important;
    pointer-events: none !important;
    visibility: hidden !important;
}
@media (max-width: 430px) {
    div[data-testid="stDialog"]:has(.dg-notification-panel) > div > div[role="dialog"] {
        box-sizing: border-box !important;
        inset-inline-end: max(var(--space-sm), env(safe-area-inset-right, 0px)) !important;
        inset-inline-start: max(var(--space-sm), env(safe-area-inset-left, 0px)) !important;
        margin-inline: 0 !important;
        max-height: min(72dvh, calc(100dvh - env(safe-area-inset-top, 0px) - 5rem)) !important;
        max-width: calc(100vw - (2 * max(var(--space-sm), env(safe-area-inset-left, 0px)))) !important;
        min-height: 0 !important;
        overflow: hidden !important;
        padding: var(--space-sm) !important;
        width: calc(100vw - (2 * max(var(--space-sm), env(safe-area-inset-left, 0px)))) !important;
    }
    .dg-notification-panel {
        max-height: min(68dvh, calc(100dvh - env(safe-area-inset-top, 0px) - 6rem)) !important;
    }
    .dg-notification-panel__note,
    .dg-notification-panel__kicker { display: none !important; }
    .dg-notification-panel__title {
        font-size: var(--font-size-body) !important;
        margin: 0 !important;
    }
    .dg-notification-panel__header { padding-block-end: var(--space-2xs) !important; }
    .dg-notification-item { padding: var(--space-xs) var(--space-sm) !important; }
    .dg-notification-item__body {
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 2;
        display: -webkit-box;
        overflow: hidden;
    }
}
div[class*="st-key-dg_notify_action_"] [data-testid="stButton"] {
    margin: 0 0 var(--space-xs) !important;
    width: 100% !important;
}
div[class*="st-key-dg_notify_action_"] [data-testid="stButton"] > button,
div[class*="st-key-dg_notify_action_"] [data-testid="stLinkButton"] > a {
    align-items: center !important;
    background: var(--color-surface-raised) !important;
    border: var(--border-width-default) solid var(--color-border) !important;
    border-inline-start: var(--border-width-semantic) solid var(--color-information) !important;
    box-sizing: border-box !important;
    color: var(--color-information) !important;
    display: flex !important;
    font-size: var(--font-size-badge) !important;
    font-weight: var(--font-weight-title) !important;
    justify-content: space-between !important;
    letter-spacing: var(--letter-spacing-badge) !important;
    min-height: var(--touch-target-min) !important;
    padding: var(--space-sm) var(--space-md) !important;
    text-decoration: none !important;
    text-transform: uppercase !important;
    width: 100% !important;
}
@media (min-width: 431px) {
    .dg-notification-panel__note--mobile-only { display: none !important; }
}
@media (max-width: 430px) {
    .dg-notification-panel__note--desktop-only { display: none !important; }
}
"""
