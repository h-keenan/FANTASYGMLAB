"""Mobile interaction overlay contract — layering, touch targets, safe areas.

Loaded last — sole owner of GM orb geometry and GM sheet structure/chrome.
Presentation only.

Streamlit 1.58+ wraps primary buttons in tooltip spans, so GM orb rules must
target ``button`` as a descendant of ``[data-testid=stButton]`` (not only a
direct child). Otherwise the accessible label ``Open GM menu`` leaks as
clipped ``O`` / ``PE`` text (#235).

GM orb / sheet block selectors MUST use direct-child ``:has(> …)`` scoping.
Unscoped ``:has(.mobile-gm-floating-trigger-marker)`` matches ancestor
``stVerticalBlock`` roots and collapses the entire main content tree into the
fixed orb (#244 / production blank Dashboard).

Viewport clipping root cause (UI consistency polish): Streamlit's
``stVerticalBlock`` defaults to ``display:flex`` with a 1rem gap. The marker
markdown container + button container therefore stacked with a 16px gap inside
the fixed 44×44 orb, so ``overflow:hidden`` + ``bottom`` inset clipped the
circle past the viewport edge. This module zeros gap and absolutely pins the
button container to the orb box.
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
    /* Streamlit stVerticalBlock defaults to flex + 1rem gap. That gap pushed the
       orb button 16px below the fixed 44×44 box so overflow:hidden + bottom
       inset clipped the circle past the viewport edge. Zero the gap and pin
       children before applying geometry. */
    align-content: stretch !important;
    align-items: stretch !important;
    bottom: max(var(--space-md), env(safe-area-inset-bottom, 0px)) !important;
    box-sizing: border-box !important;
    column-gap: 0 !important;
    display: block !important;
    gap: 0 !important;
    height: var(--dg-gm-orb-size) !important;
    justify-content: flex-start !important;
    left: max(var(--space-md), env(safe-area-inset-left, 0px)) !important;
    margin: 0 !important;
    max-height: var(--dg-gm-orb-size) !important;
    max-width: var(--dg-gm-orb-size) !important;
    min-height: var(--touch-target-min) !important;
    min-width: var(--touch-target-min) !important;
    overflow: hidden !important;
    padding: 0 !important;
    position: fixed !important;
    right: auto !important;
    row-gap: 0 !important;
    top: auto !important;
    transform: none !important;
    width: var(--dg-gm-orb-size) !important;
    z-index: var(--dg-overlay-z-nav) !important;
}}
/* Marker markdown container must not consume layout or flex gap. */
{_GM_ORB_BLOCK} > div[data-testid="stElementContainer"]:has(.mobile-gm-floating-trigger-marker),
{_GM_ORB_KEY} > div[data-testid="stElementContainer"]:has(.mobile-gm-floating-trigger-marker) {{
    height: 0 !important;
    margin: 0 !important;
    max-height: 0 !important;
    max-width: 0 !important;
    min-height: 0 !important;
    min-width: 0 !important;
    overflow: hidden !important;
    padding: 0 !important;
    pointer-events: none !important;
    position: absolute !important;
    width: 0 !important;
}}
/* Button container fills the fixed orb box — no Streamlit gap offset. */
{_GM_ORB_BLOCK} > div[data-testid="stElementContainer"]:has([data-testid="stButton"]),
{_GM_ORB_KEY} > div[data-testid="stElementContainer"]:has([data-testid="stButton"]) {{
    bottom: 0 !important;
    box-sizing: border-box !important;
    height: var(--dg-gm-orb-size) !important;
    left: 0 !important;
    margin: 0 !important;
    max-height: var(--dg-gm-orb-size) !important;
    max-width: var(--dg-gm-orb-size) !important;
    min-height: var(--dg-gm-orb-size) !important;
    min-width: var(--dg-gm-orb-size) !important;
    overflow: hidden !important;
    padding: 0 !important;
    position: absolute !important;
    right: 0 !important;
    top: 0 !important;
    width: var(--dg-gm-orb-size) !important;
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
    position: relative !important;
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
    border: var(--border-width-default, 1px) solid var(--color-border-strong, rgba(226, 232, 240, 0.4)) !important;
    border-radius: 50% !important;
    box-shadow: var(--shadow-overlay, 0 10px 28px rgba(0, 0, 0, 0.3)) !important;
    box-sizing: border-box !important;
    color: transparent !important;
    display: inline-flex !important;
    font-size: 0 !important;
    font-weight: 400 !important;
    height: var(--dg-gm-orb-size) !important;
    justify-content: center !important;
    left: 0 !important;
    letter-spacing: 0 !important;
    line-height: 0 !important;
    margin: 0 !important;
    max-height: var(--dg-gm-orb-size) !important;
    max-width: var(--dg-gm-orb-size) !important;
    min-height: var(--touch-target-min) !important;
    min-width: var(--touch-target-min) !important;
    overflow: hidden !important;
    padding: 8px !important;
    position: relative !important;
    text-indent: -9999px !important;
    text-transform: none !important;
    top: 0 !important;
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
    transform: none !important;
}}
{_GM_ORB_BLOCK} [data-testid="stButton"] button:focus-visible,
{_GM_ORB_KEY} [data-testid="stButton"] button:focus-visible,
{_GM_ORB_BLOCK} button[data-testid^="stBaseButton"]:focus-visible,
{_GM_ORB_KEY} button[data-testid^="stBaseButton"]:focus-visible {{
    box-shadow: var(--focus-ring, 0 0 0 2px rgba(56, 189, 248, 0.55)) !important;
    color: transparent !important;
    transform: none !important;
}}
/* GM sheet structure + chrome — sole owner (was DESKTOP ↔ QUICK_FIX cascade). */
:root {{
    --dg-founder-nav-width: min(calc(100vw - (2 * var(--space-md))), 390px);
    --dg-founder-nav-clearance: calc(var(--touch-target-min) + var(--space-xl));
}}
body:has(.mobile-gm-sheet-marker)::before {{
    background: color-mix(in srgb, var(--color-bg) 72%, transparent);
    content: "";
    inset: 0;
    pointer-events: none;
    position: fixed;
    z-index: 40;
}}
@media (max-width: 760px) {{
    body:has(.mobile-gm-sheet-marker)::before {{
        background: color-mix(in srgb, var(--color-bg) 78%, transparent);
    }}
}}
{_GM_SHEET_BLOCK} {{
    animation: dg-gm-sheet-enter 160ms ease-out;
    background: var(--color-shell) !important;
    border: var(--border-width-default) solid var(--color-border-strong) !important;
    border-radius: var(--radius-none) !important;
    bottom: calc(max(var(--space-md), env(safe-area-inset-bottom, 0px)) + var(--dg-founder-nav-clearance)) !important;
    box-shadow: var(--shadow-overlay) !important;
    box-sizing: border-box !important;
    gap: 0 !important;
    isolation: isolate !important;
    left: max(var(--space-md), env(safe-area-inset-left, 0px)) !important;
    max-height: min(72dvh, 640px) !important;
    max-width: var(--dg-founder-nav-width) !important;
    overflow-x: hidden !important;
    overflow-y: auto !important;
    overscroll-behavior: contain !important;
    /* Preserve prior DESKTOP-winning pad over QUICK_FIX padding:0. */
    padding: var(--space-md) !important;
    position: fixed !important;
    scrollbar-color: var(--color-border-strong) var(--color-shell);
    width: var(--dg-founder-nav-width) !important;
    z-index: var(--dg-overlay-z-sheet) !important;
}}
@keyframes dg-gm-sheet-enter {{
    from {{ opacity: 0; transform: translateY(8px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}
@media (prefers-reduced-motion: reduce) {{
    {_GM_SHEET_BLOCK} {{
        animation: none !important;
        transition: none !important;
    }}
}}
.mobile-gm-destination-panel {{
    background: var(--color-surface-primary) !important;
    border: 0 !important;
    border-bottom: var(--border-width-default) solid var(--color-border) !important;
    border-radius: var(--radius-none) !important;
    box-shadow: var(--shadow-none) !important;
    gap: var(--space-xs);
    margin: 0 !important;
    margin-block-end: var(--space-sm);
    padding: var(--space-md) var(--space-lg) !important;
}}
.mobile-gm-panel-header {{
    gap: var(--space-xs) !important;
    margin-block-end: var(--space-sm);
}}
.mobile-gm-sheet-kicker,
.mobile-gm-current-page {{
    color: var(--color-text-muted) !important;
    font-size: var(--type-section-eyebrow-size) !important;
    font-weight: var(--font-weight-metadata) !important;
    letter-spacing: var(--letter-spacing-badge) !important;
    line-height: var(--line-height-badge) !important;
    text-transform: uppercase !important;
}}
.mobile-gm-sheet-kicker {{
    color: var(--color-accent) !important;
    font-weight: var(--font-weight-title) !important;
}}
.mobile-gm-sheet-title {{
    color: var(--color-text-primary) !important;
    font: var(--type-section-title) !important;
    letter-spacing: -0.02em !important;
    margin: 0 !important;
    text-transform: uppercase !important;
}}
.mobile-gm-sheet-note {{
    color: var(--color-text-muted) !important;
    font: var(--type-supporting-metadata) !important;
    margin: var(--space-sm) 0 0 !important;
}}
.mobile-gm-experimental-note {{
    border-inline-start: var(--border-width-semantic) solid var(--color-warning);
    color: var(--color-text-muted) !important;
    font-size: var(--font-size-caption) !important;
    margin: var(--space-xs) 0 var(--space-sm);
    padding-inline-start: var(--space-sm);
}}
{_GM_SHEET_BLOCK} [data-testid="stCaptionContainer"] {{
    background: var(--color-surface-muted) !important;
    border-bottom: var(--border-width-default) solid var(--color-border) !important;
    color: var(--color-text-muted) !important;
    font-size: var(--type-section-eyebrow-size) !important;
    font-weight: var(--font-weight-title) !important;
    letter-spacing: var(--letter-spacing-badge) !important;
    margin: 0 !important;
    padding: var(--space-sm) var(--space-lg) var(--space-xs) !important;
    text-transform: uppercase !important;
}}
{_GM_SHEET_BLOCK} [data-testid="stButton"] {{
    margin: 0 !important;
}}
{_GM_SHEET_BLOCK} [data-testid="stButton"] > button {{
    align-items: center !important;
    background: var(--color-surface-primary) !important;
    border: 0 !important;
    border-bottom: var(--border-width-default) solid var(--color-border) !important;
    border-left: var(--border-width-semantic) solid transparent !important;
    border-radius: var(--radius-none) !important;
    box-shadow: var(--shadow-none) !important;
    box-sizing: border-box !important;
    color: var(--color-text-secondary) !important;
    display: flex !important;
    font: var(--font-body) !important;
    font-weight: var(--font-weight-button) !important;
    justify-content: flex-start !important;
    min-height: calc(var(--touch-target-min) + 1px) !important;
    padding: var(--space-sm) var(--space-lg) !important;
    text-align: left !important;
    width: 100% !important;
}}
{_GM_SHEET_BLOCK} [data-testid="stButton"] > button::after {{
    color: var(--color-text-muted) !important;
    content: "›" !important;
    font-size: var(--font-size-body) !important;
    margin-left: auto !important;
}}
{_GM_SHEET_BLOCK} [data-testid="stButton"] > button[kind="primary"] {{
    background: var(--color-surface-raised) !important;
    border-left-color: var(--color-accent) !important;
    box-shadow: var(--shadow-surface-inset) !important;
    color: var(--color-text-primary) !important;
}}
{_GM_SHEET_BLOCK} [data-testid="stButton"] > button[kind="primary"]::after {{
    color: var(--color-accent) !important;
    content: "CURRENT" !important;
    font-size: var(--font-size-badge) !important;
    font-weight: var(--font-weight-title) !important;
    letter-spacing: var(--letter-spacing-badge) !important;
}}
{_GM_SHEET_BLOCK} [data-testid="stButton"] > button:hover {{
    background: var(--color-surface-raised) !important;
    color: var(--color-text-primary) !important;
}}
{_GM_SHEET_BLOCK} [data-testid="stButton"] > button:focus-visible {{
    box-shadow: var(--focus-ring) !important;
    outline: none !important;
    position: relative;
    z-index: 1;
}}
/* Header × close — accessible name remains "Close"; visual glyph is ×. */
div[class*="st-key-mobile_sheet_close"] {{
    position: absolute !important;
    right: var(--space-sm, 8px) !important;
    top: var(--space-sm, 8px) !important;
    width: var(--touch-target-min) !important;
    z-index: 2 !important;
}}
div[class*="st-key-mobile_sheet_close"] [data-testid="stButton"],
div[class*="st-key-mobile_sheet_close"] [data-testid="stButton"] > div {{
    margin: 0 !important;
    width: var(--touch-target-min) !important;
}}
div[class*="st-key-mobile_sheet_close"] [data-testid="stButton"] button,
div[class*="st-key-mobile_sheet_close"] button[data-testid^="stBaseButton"] {{
    align-items: center !important;
    background: transparent !important;
    border: 0 !important;
    border-bottom: 0 !important;
    border-inline-start: 0 !important;
    border-radius: var(--radius-none, 0) !important;
    box-shadow: none !important;
    color: transparent !important;
    display: inline-flex !important;
    font-size: 0 !important;
    justify-content: center !important;
    letter-spacing: 0 !important;
    line-height: 0 !important;
    min-height: var(--touch-target-min) !important;
    min-width: var(--touch-target-min) !important;
    padding: 0 !important;
    position: relative !important;
    text-transform: none !important;
    width: var(--touch-target-min) !important;
}}
div[class*="st-key-mobile_sheet_close"] [data-testid="stButton"] button::before,
div[class*="st-key-mobile_sheet_close"] button[data-testid^="stBaseButton"]::before {{
    color: var(--color-text-secondary, #e5e7eb) !important;
    content: "×" !important;
    font-size: 1.35rem !important;
    font-weight: 400 !important;
    line-height: 1 !important;
}}
div[class*="st-key-mobile_sheet_close"] [data-testid="stButton"] button::after,
div[class*="st-key-mobile_sheet_close"] button[data-testid^="stBaseButton"]::after {{
    content: none !important;
}}
div[class*="st-key-mobile_sheet_close"] [data-testid="stButton"] button:hover,
div[class*="st-key-mobile_sheet_close"] button[data-testid^="stBaseButton"]:hover {{
    background: var(--color-surface-raised, rgba(255, 255, 255, 0.04)) !important;
    color: transparent !important;
}}
div[class*="st-key-mobile_sheet_close"] [data-testid="stButton"] button:focus-visible,
div[class*="st-key-mobile_sheet_close"] button[data-testid^="stBaseButton"]:focus-visible {{
    box-shadow: var(--focus-ring) !important;
    color: transparent !important;
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
