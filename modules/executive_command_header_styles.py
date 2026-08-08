"""Styles for the Executive Command Header action strip and Notification Center.

Canonical command-cell contract: League, Alerts, and You share one geometry.
No control-specific vertical alignment, translateY, or negative-margin hacks.

Responsive width ownership lives here (see docs/executive-header-responsive-geometry.md).
Identity chrome (brand, Founder Beta) remains in application_shell / brand modules.
"""

# Content-aware Streamlit column weights: League needs the longest label + chevron.
COMMAND_COLUMN_WEIGHTS = (1.35, 1.05, 0.9)

EXECUTIVE_COMMAND_HEADER_CSS = """
/* ── Canonical command rail ── */
div[class*="st-key-executive_command_actions"] {
    align-items: stretch !important;
    background: transparent;
    border: 0;
    display: flex !important;
    flex-wrap: nowrap;
    gap: 0 !important;
    margin: 0 !important;
    min-height: var(--touch-target-min);
    padding: 0 !important;
}

div[class*="st-key-executive_command_actions"] > div {
    margin: 0 !important;
    padding: 0 !important;
}

div[class*="st-key-executive_command_actions"] [data-testid="stHorizontalBlock"] {
    align-items: stretch !important;
    gap: 0 !important;
    margin: 0 !important;
    min-height: var(--touch-target-min);
    width: 100%;
}

div[class*="st-key-executive_command_actions"] [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
    align-items: stretch !important;
    display: flex !important;
    flex: 1 1 0 !important;
    flex-direction: column !important;
    max-width: none !important;
    min-width: 0 !important;
    padding: 0 !important;
    width: auto !important;
}

/* Canonical command cell — equal DOM depth for League / Alerts / You */
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

/* One trigger geometry for every cell — no League/Alerts/You forks */
div[class*="st-key-executive_command_actions"] [data-testid="stPopover"],
div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] > div {
    display: flex !important;
    flex: 1 1 auto !important;
    height: 100% !important;
    margin: 0 !important;
    min-height: var(--touch-target-min) !important;
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

div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] button,
div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button {
    align-items: center !important;
    background: transparent !important;
    border: 0 !important;
    border-inline-start: var(--border-width-default) solid var(--color-border) !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    color: var(--color-text-secondary) !important;
    column-gap: var(--space-xs) !important;
    display: grid !important;
    flex: 1 1 auto !important;
    font-size: var(--font-size-badge) !important;
    font-weight: var(--font-weight-title) !important;
    grid-template-columns: minmax(0, 1fr) 0.75rem !important;
    height: var(--touch-target-min) !important;
    justify-content: stretch !important;
    letter-spacing: var(--letter-spacing-badge) !important;
    line-height: var(--line-height-badge) !important;
    margin: 0 !important;
    min-height: var(--touch-target-min) !important;
    min-width: 0 !important;
    overflow: hidden !important;
    padding-block: 0 !important;
    padding-inline: var(--space-md) !important;
    text-transform: uppercase !important;
    transform: none !important;
    white-space: nowrap !important;
    width: 100% !important;
}

/*
 * Label track may ellipsis; chevron owns the fixed end column.
 * Covers both flat (label div + icon) and nested (label+icon in one wrapper) Streamlit DOMs.
 */
div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] button > div,
div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button > div {
    align-items: center !important;
    display: grid !important;
    grid-column: 1 !important;
    grid-template-columns: minmax(0, 1fr) 0.75rem !important;
    max-width: 100% !important;
    min-width: 0 !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    width: 100% !important;
}

div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] button > div > p,
div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button > div > p,
div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] button > div > span:not([aria-hidden="true"]),
div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button > div > span:not([aria-hidden="true"]) {
    grid-column: 1 !important;
    min-width: 0 !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
}

div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] button svg,
div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button svg,
div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] button [aria-hidden="true"],
div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button [aria-hidden="true"] {
    align-items: center !important;
    display: inline-flex !important;
    flex: 0 0 auto !important;
    font-size: 0.75rem !important;
    grid-column: 2 !important;
    height: 0.75rem !important;
    justify-content: center !important;
    justify-self: end !important;
    line-height: 0.75rem !important;
    margin: 0 !important;
    max-width: 0.75rem !important;
    min-width: 0.75rem !important;
    overflow: hidden !important;
    transform: none !important;
    width: 0.75rem !important;
}

div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] button:hover,
div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button:hover {
    background: var(--color-surface-raised) !important;
    color: var(--color-text-primary) !important;
}

div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] button:focus-visible,
div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button:focus-visible {
    box-shadow: var(--focus-ring) !important;
}

/* Header Feedback control stays in-strip (never the floating FAB) */
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

/* First cell (League): primary text; leading edge owned by rail/row rule, not a double border */
div[class*="st-key-executive_command_actions"] [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:first-child [data-testid="stPopover"] button,
div[class*="st-key-executive_command_actions"] [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:first-child [data-testid="stButton"] > button {
    border-inline-start: 0 !important;
    color: var(--color-text-primary) !important;
}

/* Notification Center — anchored Alerts dropdown (not a centered modal) */
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

/* Right-align dropdown toward the Alerts cell on wide layouts */
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

/* Desktop: identity + command rail share width; rail is not an artificial narrow strip. */
@media (min-width: 761px) {
    div[class*="st-key-executive_workspace_shell"] {
        align-items: stretch !important;
        grid-template-columns: minmax(0, 1fr) minmax(min(100%, 28rem), 1fr) !important;
    }

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
    div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] button,
    div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button {
        column-gap: 0.15rem !important;
        letter-spacing: 0.02em !important;
        padding-inline: var(--space-xs) !important;
    }
}

@media (prefers-reduced-motion: reduce) {
    .dg-notification-item {
        transition: none !important;
    }
}
"""
