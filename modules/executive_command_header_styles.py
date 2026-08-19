"""Styles for the Executive Command Header action strip and Notification Center.

Canonical command-cell contract: League, Alerts, and You share one geometry.
No control-specific vertical alignment, translateY, or negative-margin hacks.

Responsive width ownership lives here (see docs/executive-header-responsive-geometry.md).
CI surface: header-geometry.
Identity chrome (brand, Founder Beta) remains in application_shell / brand modules.
"""

# Content-aware Streamlit column weights: League label is short; keep Alerts room for counts.
COMMAND_COLUMN_WEIGHTS = (1.15, 1.15, 0.95)

EXECUTIVE_COMMAND_HEADER_CSS = """

div[class*="st-key-executive_command_actions"] {
    align-items: stretch !important;
    align-self: stretch !important;
    background: transparent;
    border: 0;
    display: flex !important;
    flex: 1 1 auto !important;
    flex-direction: column !important;
    flex-wrap: nowrap;
    gap: 0 !important;
    height: 100% !important;
    margin: 0 !important;
    min-height: var(--touch-target-min);
    padding: 0 !important;
}

div[class*="st-key-executive_command_actions"] > div {
    flex: 1 1 auto !important;
    height: 100% !important;
    margin: 0 !important;
    min-height: 0 !important;
    padding: 0 !important;
}

/* The parent PQV event bridge is a zero-layout listener, not a command-row
   child. Without this ownership it inherits the generic 100% child height and
   leaves a visible strip under League / Alerts / You on mobile. */
div[class*="st-key-executive_command_actions"] div[class*="st-key-player_quick_view_parent_bridge"] {
    display: none !important;
    flex: 0 0 0 !important;
    height: 0 !important;
    margin: 0 !important;
    max-height: 0 !important;
    min-height: 0 !important;
    overflow: hidden !important;
    padding: 0 !important;
}

div[class*="st-key-executive_command_actions"] [data-testid="stHorizontalBlock"] {
    align-items: stretch !important;
    flex: 1 1 auto !important;
    gap: 0 !important;
    height: 100% !important;
    margin: 0 !important;
    min-height: var(--touch-target-min);
    width: 100%;
}

div[class*="st-key-executive_command_actions"] [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
    align-items: stretch !important;
    display: flex !important;
    flex: 1 1 0 !important;
    flex-direction: column !important;
    height: 100% !important;
    max-width: none !important;
    min-height: var(--touch-target-min) !important;
    min-width: 0 !important;
    padding: 0 !important;
    width: auto !important;
}

/* Streamlit wraps each cell in stLayoutWrapper with flex:0 1 auto — stretch it. */
div[class*="st-key-executive_command_actions"] [data-testid="stColumn"] > div,
div[class*="st-key-executive_command_actions"] [data-testid="stColumn"] [data-testid="stLayoutWrapper"],
div[class*="st-key-executive_command_actions"] [data-testid="stColumn"] > div[data-testid="stVerticalBlock"] {
    align-self: stretch !important;
    display: flex !important;
    flex: 1 1 auto !important;
    flex-direction: column !important;
    height: 100% !important;
    margin: 0 !important;
    min-height: 0 !important;
    padding: 0 !important;
    width: 100% !important;
}

div[class*="st-key-executive_command_actions"] div[class*="st-key-executive_command_cell_"] {
    align-items: stretch !important;
    display: flex !important;
    flex: 1 1 auto !important;
    flex-direction: column !important;
    gap: 0 !important;
    height: 100% !important;
    margin: 0 !important;
    min-height: var(--touch-target-min) !important;
    padding: 0 !important;
    width: 100% !important;
}

div[class*="st-key-executive_command_actions"] div[class*="st-key-executive_command_cell_"] > div[data-testid="stElementContainer"],
div[class*="st-key-executive_command_actions"] div[class*="st-key-executive_command_cell_"] > div[data-testid="stVerticalBlock"],
div[class*="st-key-executive_command_actions"] div[class*="st-key-executive_command_cell_"] > div[data-testid="stLayoutWrapper"] {
    flex: 1 1 auto !important;
    gap: 0 !important;
    margin: 0 !important;
    min-height: 0 !important;
    padding: 0 !important;
    width: 100% !important;
}

div[class*="st-key-executive_command_actions"] .dg-command-cell {
    display: none !important;
}

/* Popover shell fills the command cell. One trigger only — never flex-row
   duplicate buttons (Streamlit help= historically injected a second
   stPopoverButton sibling that collided with the next command column). */
div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] {
    display: flex !important;
    flex: 1 1 auto !important;
    flex-direction: column !important;
    height: 100% !important;
    margin: 0 !important;
    min-height: var(--touch-target-min) !important;
    padding: 0 !important;
    width: 100% !important;
    border-radius: 0 !important;
}

/* The visible BaseWeb trigger surface differs across Streamlit releases.
   Own every wrapper in the command rail, not only one historical child path. */
div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] > div[aria-haspopup="true"],
div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] > div[aria-haspopup="menu"],
div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] button[data-testid="stPopoverButton"],
div[class*="st-key-executive_command_actions"] [data-baseweb="button"],
div[class*="st-key-executive_command_actions"] [role="button"] {
    border-radius: 0 !important;
}

/* Defensive: if a framework tooltip still injects a sibling trigger, do not
   participate in layout. Canonical triggers omit help= on this rail. */
div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] button[data-testid="stPopoverButton"] ~ button[data-testid="stPopoverButton"] {
    display: none !important;
    flex: 0 0 0 !important;
    height: 0 !important;
    margin: 0 !important;
    max-height: 0 !important;
    max-width: 0 !important;
    min-height: 0 !important;
    min-width: 0 !important;
    opacity: 0 !important;
    overflow: hidden !important;
    padding: 0 !important;
    pointer-events: none !important;
    position: absolute !important;
    width: 0 !important;
}

/* Tooltip wrappers (legacy help=) must not invent a second horizontal track. */
div[class*="st-key-executive_command_actions"] [data-testid="stTooltipIcon"],
div[class*="st-key-executive_command_actions"] [data-testid="stTooltipHoverTarget"] {
    align-items: stretch !important;
    align-self: stretch !important;
    box-sizing: border-box !important;
    display: flex !important;
    flex: 1 1 auto !important;
    flex-direction: column !important;
    height: 100% !important;
    margin: 0 !important;
    max-width: 100% !important;
    min-height: var(--touch-target-min) !important;
    min-width: 0 !important;
    padding: 0 !important;
    width: 100% !important;
}

div[class*="st-key-executive_command_actions"] [data-testid="stButton"],
div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > div {
    display: flex !important;
    flex: 1 1 auto !important;
    height: 100% !important;
    margin: 0 !important;
    min-height: var(--touch-target-min) !important;
    padding: 0 !important;
    width: 100% !important;
}

div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] > div[aria-haspopup="true"] > button[data-testid="stPopoverButton"],
div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button {
    align-items: center !important;
    background: transparent !important;
    border: 0 !important;
    border-block-end: var(--border-width-default) solid var(--color-border-strong) !important;
    border-inline-start: var(--border-width-default) solid var(--color-border) !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    box-sizing: border-box !important;
    color: var(--color-text-secondary) !important;
    column-gap: var(--space-xs) !important;
    display: grid !important;
    flex: 1 1 auto !important;
    font-size: var(--font-size-badge) !important;
    font-weight: var(--font-weight-title) !important;
    /* Center label+chevron as one optical unit; fill band so dividers span height */
    grid-template-columns: minmax(0, auto) 0.75rem !important;
    height: 100% !important;
    justify-content: center !important;
    justify-items: center !important;
    letter-spacing: var(--letter-spacing-badge) !important;
    /* Tight line-box so glyph optical center matches flex/grid cell center. */
    line-height: 1 !important;
    margin: 0 !important;
    min-height: var(--touch-target-min) !important;
    min-width: 0 !important;
    overflow: hidden !important;
    padding-block: 0 !important;
    padding-inline: var(--space-sm) !important;
    text-transform: uppercase !important;
    top: auto !important;
    transform: none !important;
    white-space: nowrap !important;
    width: 100% !important;
}

div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] > div[aria-haspopup="true"] > button[data-testid="stPopoverButton"] > div,
div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button > div {
    align-items: center !important;
    column-gap: var(--space-xs) !important;
    display: inline-grid !important;
    grid-column: 1 / -1 !important;
    grid-template-columns: minmax(0, auto) 0.75rem !important;
    justify-content: center !important;
    max-width: 100% !important;
    min-width: 0 !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    width: auto !important;
}

div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] > div[aria-haspopup="true"] > button[data-testid="stPopoverButton"] > div > p,
div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button > div > p,
div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] > div[aria-haspopup="true"] > button[data-testid="stPopoverButton"] > div > span:not([aria-hidden="true"]),
div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button > div > span:not([aria-hidden="true"]) {
    align-items: center !important;
    display: inline-flex !important;
    grid-column: 1 !important;
    line-height: 1 !important;
    margin: 0 !important;
    min-width: 0 !important;
    overflow: hidden !important;
    padding: 0 !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
}

div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] > div[aria-haspopup="true"] > button[data-testid="stPopoverButton"] svg,
div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button svg,
div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] > div[aria-haspopup="true"] > button[data-testid="stPopoverButton"] [aria-hidden="true"],
div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button [aria-hidden="true"] {
    align-items: center !important;
    display: inline-flex !important;
    flex: 0 0 auto !important;
    font-size: 0.75rem !important;
    grid-column: 2 !important;
    height: 0.75rem !important;
    justify-content: center !important;
    justify-self: end !important;
    line-height: 1 !important;
    margin: 0 !important;
    max-width: 0.75rem !important;
    min-width: 0.75rem !important;
    overflow: hidden !important;
    padding: 0 !important;
    transform: none !important;
    width: 0.75rem !important;
}

div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] > div[aria-haspopup="true"] > button[data-testid="stPopoverButton"]:hover,
div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button:hover {
    background: var(--color-surface-raised) !important;
    color: var(--color-text-primary) !important;
}

div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] > div[aria-haspopup="true"] > button[data-testid="stPopoverButton"]:focus-visible,
div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button:focus-visible {
    box-shadow: var(--focus-ring) !important;
}

div[class*="st-key-executive_command_actions"] div[class*="_header_feedback_control"],
div[class*="st-key-executive_command_actions"] div[class*="_global_feedback_control"] {
    bottom: auto !important;
    left: auto !important;
    max-width: none !important;
    pointer-events: auto !important;
    position: static !important;
    right: auto !important;
    top: auto !important;
    transform: none !important;
    width: 100% !important;
    z-index: auto !important;
}

div[class*="st-key-executive_command_actions"] div[class*="_header_feedback_control"] [data-testid="stPopover"] > button,
div[class*="st-key-executive_command_actions"] div[class*="_global_feedback_control"] [data-testid="stPopover"] > button {
    max-width: none !important;
    min-width: 0 !important;
    width: 100% !important;
}

div[class*="st-key-executive_command_actions"] div[class*="_header_feedback_control"] [data-testid="stPopover"] > button::before,
div[class*="st-key-executive_command_actions"] div[class*="_global_feedback_control"] [data-testid="stPopover"] > button::before {
    content: none !important;
}

div[class*="st-key-executive_command_actions"] [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:first-child [data-testid="stPopover"] > div[aria-haspopup="true"] > button[data-testid="stPopoverButton"],
div[class*="st-key-executive_command_actions"] [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:first-child [data-testid="stButton"] > button {
    border-inline-start: 0 !important;
    color: var(--color-text-primary) !important;
}

div[data-testid="stPopoverBody"]:has(.dg-notification-panel),
div[data-testid="stPopoverContent"]:has(.dg-notification-panel) {
    box-shadow: var(--shadow-overlay) !important;
    display: flex !important;
    flex-direction: column !important;
    max-height: min(60vh, calc(100dvh - 5rem)) !important;
    max-width: min(92vw, 28rem) !important;
    min-height: 0 !important;
    min-width: min(92vw, 24rem) !important;
    overflow-x: hidden !important;
    overflow-y: auto !important;
    overscroll-behavior: contain !important;
    padding: var(--space-md) !important;
    width: min(92vw, 26rem) !important;
    z-index: var(--dg-overlay-z-popover, 1001010) !important;
}

@media (min-width: 768px) {
    div[data-testid="stPopoverBody"]:has(.dg-notification-panel),
    div[data-testid="stPopoverContent"]:has(.dg-notification-panel) {
        max-width: 28rem !important;
        min-width: 24rem !important;
        width: 26rem !important;
    }
}

.dg-notification-panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
    min-height: 0;
}

.dg-notification-panel__header {
    display: grid;
    flex: 0 0 auto;
    gap: var(--space-2xs);
    padding-block-end: var(--space-2xs);
}

.dg-notification-panel__title-row {
    align-items: baseline;
    display: flex;
    gap: var(--space-sm);
    justify-content: space-between;
}

.dg-notification-panel__title {
    color: var(--color-text-primary);
    font-size: var(--font-size-body);
    font-weight: var(--font-weight-display);
    letter-spacing: -0.02em;
    margin: 0;
}

.dg-notification-panel__status {
    color: var(--color-text-muted);
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
    white-space: nowrap;
}

.dg-notification-panel__note {
    color: var(--color-text-muted);
    font-size: var(--font-size-caption);
    line-height: var(--line-height-caption);
    max-width: 42ch;
}

.dg-notification-panel__list {
    display: grid;
    flex: 1 1 auto;
    gap: var(--space-sm);
    min-height: 0;
    overflow-x: hidden;
    overflow-y: auto;
    overscroll-behavior: contain;
    padding-block-end: var(--space-xs);
    scrollbar-gutter: stable;
}

.dg-notification-panel__empty {
    color: var(--color-text-muted);
    font-size: var(--font-size-caption);
    margin: 0;
    padding: var(--space-sm) 0;
}

.dg-notification-harness-open {
    display: none;
}

div[class*="st-key-fixture_notifications_inbox_harness_open"] .dg-notification-panel,
div[class*="st-key-_inbox_harness_open"] .dg-notification-panel {
    border: var(--border-width-default) solid var(--color-border);
    box-shadow: var(--shadow-overlay);
    margin-block-start: var(--space-xs);
    max-height: min(60vh, calc(100dvh - 5rem));
    max-width: min(92vw, 28rem);
    overflow-x: hidden;
    overflow-y: auto;
    padding: var(--space-md);
    width: min(92vw, 26rem);
}

.dg-notification-item {
    background: var(--color-surface-primary);
    border: var(--border-width-default) solid var(--color-border);
    border-inline-start: var(--border-width-semantic) solid var(--color-border-strong);
    display: grid;
    gap: var(--space-2xs);
    margin: 0;
    padding: var(--space-sm) var(--space-md);
}

.dg-notification-item.is-unread,
.dg-notification-item--action.is-unread {
    background: var(--color-surface-raised);
    border-inline-start-color: var(--color-information);
}

.dg-notification-item.is-stale {
    opacity: 0.72;
}

.dg-notification-item__stale {
    color: var(--color-warning);
    font-size: var(--font-size-caption);
    line-height: var(--line-height-caption);
}

.dg-notification-item--action .dg-notification-item__title {
    font-weight: var(--font-weight-display);
}

.dg-notification-item--routine {
    opacity: 0.92;
}

.dg-notification-item--product {
    opacity: 0.78;
}

.dg-notification-item--product .dg-notification-item__title {
    font-size: var(--font-size-caption);
    font-weight: var(--font-weight-title);
    line-height: var(--line-height-caption);
}

.dg-notification-item__meta {
    align-items: center;
    display: flex;
    gap: var(--space-sm);
    justify-content: space-between;
}

.dg-notification-item__category {
    color: var(--color-text-muted);
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}

.dg-notification-item__age {
    color: var(--color-text-muted);
    font-size: var(--font-size-badge);
    opacity: var(--opacity-metadata);
}

.dg-notification-item__title {
    color: var(--color-text-primary);
    font: var(--font-card-title);
}

.dg-notification-item__body {
    color: var(--color-text-secondary);
    font-size: var(--font-size-caption);
    line-height: var(--line-height-caption);
    margin: 0;
}

.dg-notification-item__action-line {
    color: var(--color-text-primary);
    font-size: var(--font-size-caption);
    font-weight: var(--font-weight-title);
    line-height: var(--line-height-caption);
}

.dg-profile-panel {
    display: grid;
    gap: var(--space-sm);
    margin-block-end: var(--space-sm);
}

.dg-profile-panel__title {
    color: var(--color-text-primary);
    font: var(--font-card-title);
}

.dg-profile-panel__meta {
    color: var(--color-text-muted);
    font-size: var(--font-size-caption);
    line-height: var(--line-height-caption);
}

@media (min-width: 761px) {
    /* Shell grid columns stay in APPLICATION_SHELL_CSS — do not re-own here. */
    div[class*="st-key-executive_command_actions"] {
        align-self: stretch;
        border-inline-start: var(--border-width-default) solid var(--color-border);
        flex: 1 1 auto;
        max-width: none;
        min-width: 0;
        width: 100%;
    }
}

@media (max-width: 760px) {
    div[class*="st-key-executive_command_actions"] {
        border-block-start: 0;
        max-width: none;
        min-width: 0;
        width: 100%;
    }

    div[class*="st-key-executive_command_actions"] [data-testid="stHorizontalBlock"] {
        border-block-start: var(--border-width-default) solid var(--color-border);
        display: flex !important;
        width: 100% !important;
    }

    div[class*="st-key-executive_command_actions"] [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        flex: 1 1 0 !important;
        max-width: none !important;
        min-width: 0 !important;
        width: auto !important;
    }
}

@media (max-width: 430px) {
    div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] > div[aria-haspopup="true"] > button[data-testid="stPopoverButton"],
    div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button {
        column-gap: 0.12rem !important;
        letter-spacing: 0.02em !important;
        padding-inline: var(--space-2xs) !important;
    }

    div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] > div[aria-haspopup="true"] > button[data-testid="stPopoverButton"] > div,
    div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button > div {
        grid-template-columns: minmax(0, auto) 0.7rem !important;
    }
}

@media (prefers-reduced-motion: reduce) {
    .dg-notification-item {
        transition: none !important;
    }
}
"""
