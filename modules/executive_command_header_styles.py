"""Styles for the Executive Command Header action strip and Notification Center.

Canonical command-cell contract: League, Alerts, and You share one geometry.
No control-specific vertical alignment, translateY, or negative-margin hacks.
"""

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

div[class*="st-key-executive_command_actions"] [data-testid="stHorizontalBlock"] > div[data-testid="column"] {
    align-items: stretch !important;
    display: flex !important;
    flex-direction: column !important;
    min-width: 0;
    padding: 0 !important;
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
div[class*="st-key-executive_command_actions"] div[class*="st-key-executive_command_cell_"] > div[data-testid="stVerticalBlock"] {
    flex: 1 1 auto !important;
    gap: 0 !important;
    height: 100% !important;
    margin: 0 !important;
    min-height: var(--touch-target-min) !important;
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

div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] button,
div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button {
    align-items: center !important;
    background: transparent !important;
    border: 0 !important;
    border-inline-start: var(--border-width-default) solid var(--color-border) !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    color: var(--color-text-secondary) !important;
    display: inline-flex !important;
    flex: 1 1 auto !important;
    flex-direction: row !important;
    font-size: var(--font-size-badge) !important;
    font-weight: var(--font-weight-title) !important;
    gap: var(--space-xs) !important;
    height: var(--touch-target-min) !important;
    justify-content: center !important;
    letter-spacing: var(--letter-spacing-badge) !important;
    line-height: var(--line-height-badge) !important;
    margin: 0 !important;
    min-height: var(--touch-target-min) !important;
    overflow: hidden !important;
    padding-block: 0 !important;
    padding-inline: var(--space-md) !important;
    text-overflow: clip !important;
    text-transform: uppercase !important;
    transform: none !important;
    white-space: nowrap !important;
    width: 100% !important;
}

div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] button svg,
div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button svg {
    align-self: center !important;
    display: block !important;
    flex: 0 0 auto !important;
    height: 0.75rem !important;
    margin: 0 !important;
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

/* First cell (League) uses primary text; metrics still come from shared rules */
div[class*="st-key-executive_command_actions"] [data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child [data-testid="stPopover"] button {
    color: var(--color-text-primary) !important;
}

/* Notification Center — floating executive inbox (not a nested page) */
div[data-testid="stPopoverBody"]:has(.dg-notification-panel),
div[data-testid="stPopoverContent"]:has(.dg-notification-panel) {
    box-shadow: var(--shadow-overlay) !important;
    display: flex !important;
    flex-direction: column !important;
    max-height: min(60vh, calc(100dvh - 5rem)) !important;
    max-width: min(92vw, 26rem) !important;
    min-height: min(45vh, calc(100dvh - 8rem)) !important;
    overflow: hidden !important;
    padding: var(--space-md) !important;
    width: min(92vw, 26rem) !important;
}

.dg-notification-panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
    max-height: min(56vh, calc(100dvh - 6rem));
    min-height: 0;
    overflow: hidden;
}

.dg-notification-panel__header {
    display: grid;
    flex: 0 0 auto;
    gap: var(--space-xs);
    padding-block-end: var(--space-xs);
}

.dg-notification-panel__kicker {
    color: var(--color-accent);
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}

.dg-notification-panel__title {
    color: var(--color-text-primary);
    font-size: var(--font-size-section-title);
    font-weight: var(--font-weight-display);
    letter-spacing: -0.02em;
}

.dg-notification-panel__note {
    color: var(--color-text-muted);
    font-size: var(--font-size-caption);
    line-height: var(--line-height-caption);
    max-width: 36ch;
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
    padding: var(--space-md) 0;
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

.dg-notification-item__cta {
    color: var(--color-information);
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    margin-block-start: var(--space-xs);
    text-transform: uppercase;
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

/* Desktop: one rail separator between identity and command cells */
@media (min-width: 761px) {
    div[class*="st-key-executive_workspace_shell"] {
        align-items: stretch !important;
        grid-template-columns: minmax(0, 1fr) auto !important;
    }

    div[class*="st-key-executive_command_actions"] {
        align-self: stretch;
        border-inline-start: var(--border-width-default) solid var(--color-border);
        flex: 0 0 auto;
        max-width: 22.5rem;
        min-width: 16.5rem;
        width: 22.5rem;
    }
}

@media (max-width: 760px) {
    div[class*="st-key-executive_command_actions"] {
        border-block-start: 0;
        width: 100%;
    }

    div[class*="st-key-executive_command_actions"] [data-testid="stHorizontalBlock"] {
        border-block-start: var(--border-width-default) solid var(--color-border);
    }
}

@media (max-width: 430px) {
    div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] button,
    div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button {
        letter-spacing: var(--letter-spacing-badge) !important;
        padding-inline: var(--space-sm) !important;
    }
}

@media (prefers-reduced-motion: reduce) {
    .dg-notification-item {
        transition: none !important;
    }
}
"""
