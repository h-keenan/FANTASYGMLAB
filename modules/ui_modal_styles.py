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
    align-items: start;
    display: grid;
    gap: var(--space-sm);
    grid-template-columns: minmax(0, 1fr) auto;
}

.dg-modal-list-row--highlighted {
    border-left: var(--border-width-semantic) solid var(--color-accent);
}

.dg-modal-list-title,
.dg-modal-list-value {
    color: var(--color-text-secondary);
    font-weight: var(--font-weight-title);
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
        grid-template-columns: 1fr;
    }
}
"""
