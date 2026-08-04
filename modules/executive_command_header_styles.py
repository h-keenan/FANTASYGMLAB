"""Styles for the Executive Command Header action strip and Notification Center."""

EXECUTIVE_COMMAND_HEADER_CSS = """
/* Executive command actions: league, alerts, profile, feedback */
div[class*="st-key-executive_command_actions"] {
    align-items: stretch;
    background: transparent;
    border: 0;
    display: flex !important;
    flex-wrap: nowrap;
    gap: 0 !important;
    margin: 0 !important;
    min-height: var(--touch-target-min);
}

div[class*="st-key-executive_command_actions"] > div {
    margin: 0 !important;
}

div[class*="st-key-executive_command_actions"] [data-testid="stHorizontalBlock"] {
    gap: 0 !important;
    width: 100%;
}

div[class*="st-key-executive_command_actions"] [data-testid="stHorizontalBlock"] > div {
    min-width: 0;
}

div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] button,
div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button {
    background: transparent !important;
    border: 0 !important;
    border-inline-start: var(--border-width-default) solid var(--color-border) !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    color: var(--color-text-secondary) !important;
    font-size: var(--font-size-badge) !important;
    font-weight: var(--font-weight-title) !important;
    letter-spacing: var(--letter-spacing-badge) !important;
    min-height: var(--touch-target-min) !important;
    overflow: hidden !important;
    padding-inline: var(--space-md) !important;
    text-overflow: clip !important;
    text-transform: uppercase !important;
    white-space: nowrap !important;
    width: 100%;
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
    background: transparent !important;
    border: 0 !important;
    border-inline-start: var(--border-width-default) solid var(--color-border) !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    font-size: var(--font-size-badge) !important;
    height: auto !important;
    max-width: none !important;
    min-height: var(--touch-target-min) !important;
    min-width: 0 !important;
    padding-inline: var(--space-md) !important;
    width: 100% !important;
}

div[class*="st-key-executive_command_actions"] div[class*="_header_feedback_control"] [data-testid="stPopover"] > button::before,
div[class*="st-key-executive_command_actions"] div[class*="_global_feedback_control"] [data-testid="stPopover"] > button::before {
    content: none !important;
}

/* Keep league switcher as the primary action in the strip */
div[class*="st-key-executive_command_actions"] div[class*="st-key-top_league_actions"] [data-testid="stPopover"] button {
    color: var(--color-text-primary) !important;
}

/* Founder badge + chips inside the shell landmark */
.dg-executive-shell__title-row {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-sm);
    grid-row: 1 / 3;
    min-width: 0;
}

.dg-executive-shell__title-row .dg-executive-shell__title {
    grid-row: auto;
}

.dg-executive-shell__title-row .dg-founder-badge {
    flex: 0 0 auto;
}

.dg-executive-shell__chip {
    align-items: center;
    border: var(--border-width-default) solid var(--color-border);
    color: var(--color-text-secondary);
    display: inline-flex;
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    line-height: var(--line-height-badge);
    margin-inline-start: var(--space-xs);
    padding: var(--space-xs) var(--space-sm);
    text-transform: uppercase;
    white-space: nowrap;
}

.dg-executive-shell__chip--premium {
    border-color: var(--color-premium);
    color: var(--color-premium);
}

.dg-executive-shell__chip--alerts {
    border-color: var(--color-information);
    color: var(--color-information);
}

/* Notification Center panel */
.dg-notification-panel {
    display: grid;
    gap: var(--space-sm);
    margin-block-end: var(--space-sm);
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
}

.dg-notification-panel__categories {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-xs);
}

.dg-notification-chip {
    border: var(--border-width-default) solid var(--color-border);
    color: var(--color-text-muted);
    font-size: var(--font-size-badge);
    letter-spacing: var(--letter-spacing-badge);
    padding: var(--space-xs) var(--space-sm);
    text-transform: uppercase;
}

.dg-notification-item {
    background: var(--color-surface-primary);
    border: var(--border-width-default) solid var(--color-border);
    border-inline-start: var(--border-width-semantic) solid var(--color-border-strong);
    display: grid;
    gap: var(--space-xs);
    margin: 0 0 var(--space-sm);
    padding: var(--space-sm) var(--space-md);
}

.dg-notification-item.is-unread {
    border-inline-start-color: var(--color-information);
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

/* Desktop: actions sit as one command rail on the right */
@media (min-width: 761px) {
    div[class*="st-key-executive_workspace_shell"] {
        grid-template-columns: minmax(0, 1fr) auto !important;
    }

    div[class*="st-key-executive_command_actions"] {
        border-inline-start: var(--border-width-default) solid var(--color-border);
        max-width: 34rem;
        min-width: 22rem;
    }
}

@media (max-width: 760px) {
    .dg-executive-shell__title-row {
        grid-row: auto;
        width: 100%;
    }

    .dg-executive-shell__title-row .dg-founder-badge {
        display: none;
    }

    .dg-executive-shell__chip {
        display: none;
    }

    div[class*="st-key-executive_command_actions"] {
        border-block-start: var(--border-width-default) solid var(--color-border);
        width: 100%;
    }

    div[class*="st-key-executive_command_actions"] [data-testid="stPopover"] button,
    div[class*="st-key-executive_command_actions"] [data-testid="stButton"] > button {
        font-size: 0.62rem !important;
        padding-inline: var(--space-sm) !important;
    }
}

@media (prefers-reduced-motion: reduce) {
    .dg-notification-item,
    .dg-executive-shell__chip {
        transition: none !important;
    }
}
"""
