"""Mobile interaction overlay contract — layering, touch targets, safe areas.

Loaded last so it wins over legacy GM / popover geometry. Presentation only.

Streamlit 1.58+ wraps primary buttons in tooltip spans, so GM orb rules must
target ``button`` as a descendant of ``[data-testid=stButton]`` (not only a
direct child). Otherwise the accessible label ``Open GM menu`` leaks as
clipped ``O`` / ``PE`` text (#235).

GM orb / sheet block selectors MUST use direct-child ``:has(> …)`` scoping.
Unscoped ``:has(.mobile-gm-floating-trigger-marker)`` matches ancestor
``stVerticalBlock`` roots and collapses the entire main content tree into the
fixed orb (#244 / production blank Dashboard).
"""

# CRITICAL (#244): GM orb geometry MUST use a direct-child `:has(> …)` scope.
# An unscoped `:has(.mobile-gm-floating-trigger-marker)` matches every ancestor
# `stVerticalBlock` that contains the orb — including the root main content
# block — and collapses the entire Streamlit page into a fixed 44px orb
# (production blank Dashboard: background + tiny GM control only).
_GM_ORB_BLOCK = (
    'div[data-testid="stVerticalBlock"]'
    ':has(> div[data-testid="stElementContainer"] .mobile-gm-floating-trigger-marker)'
)
_GM_ORB_KEY = 'div[class*="st-key-mobile_gm_sheet_trigger_"]'
_GM_SHEET_BLOCK = (
    'div[data-testid="stVerticalBlock"]'
    ':has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker)'
)

MOBILE_INTERACTION_OVERLAY_CSS = f"""
:root {{
    --dg-overlay-z-nav: 1001000;
    --dg-overlay-z-sheet: 1001005;
    --dg-overlay-z-popover: 1001010;
    --dg-overlay-z-modal: 1001020;
    --dg-gm-orb-size: var(--touch-target-min);
}}
.mobile-gm-orb-hint {{ display: none !important; }}

{_GM_ORB_BLOCK},
{_GM_ORB_KEY} {{
    bottom: max(var(--space-md), env(safe-area-inset-bottom, 0px)) !important;
    height: var(--dg-gm-orb-size) !important;
    left: max(var(--space-md), env(safe-area-inset-left, 0px)) !important;
    margin: 0 !important;
    min-height: var(--touch-target-min) !important;
    overflow: hidden !important;
    padding: 0 !important;
    position: fixed !important;
    right: auto !important;
    width: var(--dg-gm-orb-size) !important;
    z-index: var(--dg-overlay-z-nav) !important;
}}
{_GM_ORB_BLOCK} [data-testid="stButton"],
{_GM_ORB_KEY} [data-testid="stButton"],
{_GM_ORB_BLOCK} [data-testid="stTooltipHoverTarget"],
{_GM_ORB_KEY} [data-testid="stTooltipHoverTarget"],
{_GM_ORB_BLOCK} [data-testid="stTooltipIcon"],
{_GM_ORB_KEY} [data-testid="stTooltipIcon"],
{_GM_ORB_BLOCK} [data-testid="stButton"] > div,
{_GM_ORB_KEY} [data-testid="stButton"] > div {{
    height: var(--dg-gm-orb-size) !important;
    margin: 0 !important;
    max-height: var(--dg-gm-orb-size) !important;
    max-width: var(--dg-gm-orb-size) !important;
    min-height: var(--dg-gm-orb-size) !important;
    min-width: var(--dg-gm-orb-size) !important;
    overflow: hidden !important;
    padding: 0 !important;
    width: var(--dg-gm-orb-size) !important;
}}
{_GM_ORB_BLOCK} [data-testid="stButton"] button,
{_GM_ORB_KEY} [data-testid="stButton"] button,
{_GM_ORB_BLOCK} button[data-testid^="stBaseButton"],
{_GM_ORB_KEY} button[data-testid^="stBaseButton"] {{
    align-items: center !important;
    background-color: var(--color-shell, #0f1114) !important;
    background-origin: content-box !important;
    background-position: center !important;
    background-repeat: no-repeat !important;
    background-size: contain !important;
    border: 1px solid rgba(226, 232, 240, 0.4) !important;
    border-radius: 50% !important;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.3) !important;
    color: transparent !important;
    display: inline-flex !important;
    font-size: 0 !important;
    font-weight: 400 !important;
    height: var(--dg-gm-orb-size) !important;
    justify-content: center !important;
    letter-spacing: 0 !important;
    line-height: 0 !important;
    max-height: var(--dg-gm-orb-size) !important;
    max-width: var(--dg-gm-orb-size) !important;
    min-height: var(--touch-target-min) !important;
    min-width: var(--touch-target-min) !important;
    overflow: hidden !important;
    padding: 8px !important;
    text-indent: -9999px !important;
    text-transform: none !important;
    transform: none !important;
    white-space: nowrap !important;
    width: var(--dg-gm-orb-size) !important;
}}
{_GM_ORB_BLOCK} [data-testid="stButton"] button > *,
{_GM_ORB_KEY} [data-testid="stButton"] button > *,
{_GM_ORB_BLOCK} button[data-testid^="stBaseButton"] > *,
{_GM_ORB_KEY} button[data-testid^="stBaseButton"] > * {{
    color: transparent !important;
    font-size: 0 !important;
    height: 0 !important;
    letter-spacing: 0 !important;
    line-height: 0 !important;
    margin: 0 !important;
    max-height: 0 !important;
    max-width: 0 !important;
    opacity: 0 !important;
    overflow: hidden !important;
    padding: 0 !important;
    pointer-events: none !important;
    position: absolute !important;
    width: 0 !important;
}}
{_GM_ORB_BLOCK} [data-testid="stButton"] button:hover,
{_GM_ORB_KEY} [data-testid="stButton"] button:hover,
{_GM_ORB_BLOCK} button[data-testid^="stBaseButton"]:hover,
{_GM_ORB_KEY} button[data-testid^="stBaseButton"]:hover {{
    background-color: rgba(15, 23, 42, 0.96) !important;
    border-color: rgba(56, 189, 248, 0.55) !important;
    color: transparent !important;
}}
{_GM_ORB_BLOCK} [data-testid="stButton"] button:focus-visible,
{_GM_ORB_KEY} [data-testid="stButton"] button:focus-visible,
{_GM_ORB_BLOCK} button[data-testid^="stBaseButton"]:focus-visible,
{_GM_ORB_KEY} button[data-testid^="stBaseButton"]:focus-visible {{
    box-shadow: var(--focus-ring, 0 0 0 2px rgba(56, 189, 248, 0.55)) !important;
    color: transparent !important;
}}
{_GM_SHEET_BLOCK} {{
    z-index: var(--dg-overlay-z-sheet) !important;
}}
""" + """
div[data-testid="stPopoverBody"]:has(.dg-notification-panel),
div[data-testid="stPopoverContent"]:has(.dg-notification-panel) {
    isolation: isolate !important;
    z-index: var(--dg-overlay-z-popover) !important;
}

body:has(div[data-testid="stPopoverBody"]:has(.dg-notification-panel))
    div[class*="st-key-mobile_gm_sheet_trigger_"],
body:has(div[data-testid="stPopoverContent"]:has(.dg-notification-panel))
    div[class*="st-key-mobile_gm_sheet_trigger_"],
body:has([class*="inbox_harness_open"] .dg-notification-panel)
    div[class*="st-key-mobile_gm_sheet_trigger_"],
body:has(.league-actions-sheet-marker) div[class*="st-key-mobile_gm_sheet_trigger_"],
body:has(.dg-profile-panel) div[class*="st-key-mobile_gm_sheet_trigger_"],
body:has(div[data-testid="stDialog"]) div[class*="st-key-mobile_gm_sheet_trigger_"] {
    opacity: 0 !important;
    pointer-events: none !important;
    visibility: hidden !important;
}
@media (max-width: 430px) {
    div[data-testid="stPopoverBody"]:has(.dg-notification-panel),
    div[data-testid="stPopoverContent"]:has(.dg-notification-panel) {
        box-sizing: border-box !important;
        max-height: min(72dvh, calc(100dvh - env(safe-area-inset-top, 0px) - 5rem)) !important;
        max-width: calc(100vw - (2 * max(var(--space-sm), env(safe-area-inset-left, 0px)))) !important;
        min-width: 0 !important;
        overflow: hidden auto !important;
        padding: var(--space-sm) !important;
        width: calc(100vw - (2 * max(var(--space-sm), env(safe-area-inset-left, 0px)))) !important;
    }
    .dg-notification-panel {
        max-height: min(68dvh, calc(100dvh - env(safe-area-inset-top, 0px) - 6rem)) !important;
    }
    .dg-notification-panel__note { display: none !important; }
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
div[class*="st-key-dg_notify_action_"] [data-testid="stButton"] button,
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
"""
