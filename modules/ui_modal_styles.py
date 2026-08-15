"""Scoped styles for the canonical DynastyGM modal content structure."""

UI_MODAL_CSS = """
/* Canonical modal content; the outer dialog remains owned by Streamlit. */
.dg-modal-content {
    color: var(--color-text-primary);
    font: var(--font-body);
    min-width: 0;
    overflow-wrap: anywhere;
}

.dg-modal-header {
    border-bottom: var(--border-width-default) solid var(--color-border);
    margin-bottom: var(--space-lg);
    padding-bottom: var(--space-lg);
}

.dg-modal-eyebrow,
.dg-modal-section-label,
.dg-modal-list-heading {
    color: var(--color-text-muted);
    font-size: var(--font-size-caption);
    font-weight: var(--font-weight-metadata);
    letter-spacing: var(--letter-spacing-badge);
    line-height: var(--line-height-caption);
    text-transform: uppercase;
}

.dg-modal-summary {
    color: var(--color-text-primary);
    font-size: var(--font-size-numeric);
    font-weight: var(--font-weight-display);
    line-height: var(--line-height-title);
    margin-top: var(--space-sm);
}

.dg-modal-sections,
.dg-modal-list {
    display: grid;
    gap: var(--space-sm);
}

.dg-modal-section,
.dg-modal-list-row {
    background: var(--color-surface-muted);
    border: var(--border-width-default) solid var(--color-border);
    border-radius: var(--radius-none);
    padding: var(--space-md);
}

.dg-modal-section-body,
.dg-modal-list-note,
.dg-modal-footer {
    color: var(--color-text-muted);
    line-height: var(--line-height-body);
    margin-top: var(--space-xs);
}

.dg-modal-list {
    margin-top: var(--space-lg);
}

.dg-modal-list-row {
    align-items: center;
    display: grid;
    gap: var(--space-sm);
    grid-template-columns: 2.75rem minmax(0, 1fr) auto;
    padding: var(--space-sm);
}

.dg-modal-list-row--highlighted {
    border-left: var(--border-width-semantic) solid var(--color-accent);
}

.dg-modal-list-avatar {
    align-items: center;
    background: var(--color-surface-raised);
    border: var(--border-width-default) solid var(--color-border);
    border-radius: var(--radius-md);
    display: flex;
    height: 2.75rem;
    justify-content: center;
    min-width: 2.75rem;
    overflow: hidden;
    position: relative;
    width: 2.75rem;
}

.dg-modal-list-avatar img {
    height: 100%;
    inset: 0;
    object-fit: cover;
    position: absolute;
    width: 100%;
}

.dg-modal-list-avatar-fallback {
    color: var(--color-text-secondary);
    font: var(--type-supporting-metadata);
    letter-spacing: var(--letter-spacing-badge);
}

.dg-modal-list-copy {
    min-width: 0;
}

.dg-modal-list-kicker {
    color: var(--color-accent);
    font: var(--type-supporting-metadata);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}

.dg-modal-list-title,
.dg-modal-list-value {
    color: var(--color-text-secondary);
    font-weight: var(--font-weight-title);
    overflow-wrap: anywhere;
}

.dg-modal-list-value {
    font-variant-numeric: tabular-nums;
}

.dg-modal-footer {
    border-top: var(--border-width-default) solid var(--color-border);
    margin-top: var(--space-lg);
    padding-top: var(--space-md);
}

@media (max-width: 640px) {
    .dg-modal-list-row {
        grid-template-columns: 2.75rem minmax(0, 1fr);
    }

    .dg-modal-list-value {
        grid-column: 2;
    }
}
"""
