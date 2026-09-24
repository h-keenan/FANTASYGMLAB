"""Route-owned styles for the Live Draft assistant."""

LIVE_DRAFT_CSS = """
.live-draft-route-marker {
    display: none !important;
}

.live-draft-hero,
.live-draft-command,
.live-draft-rec-card,
.live-draft-board {
    background: var(--color-surface-primary);
    border: var(--border-width-default) solid var(--color-border);
    border-radius: var(--radius-panel);
    box-shadow: var(--shadow-card);
}

.live-draft-hero {
    margin: var(--space-sm) 0 var(--space-md);
    padding: var(--space-md) var(--space-lg);
}

.live-draft-kicker,
.live-draft-rec-label {
    color: rgba(103, 232, 249, 0.92);
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

.live-draft-title,
.live-draft-command-title {
    color: var(--color-text-primary, #f8fafc);
    font-size: 1.08rem;
    font-weight: 900;
    line-height: 1.08;
}

.live-draft-copy,
.live-draft-command-meta,
.live-draft-rec-meta,
.live-draft-rec-reason {
    color: rgba(226, 232, 240, 0.70);
    font-size: 0.78rem;
    line-height: 1.28;
}

.live-draft-chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.32rem;
    margin-top: 0.55rem;
}

.live-draft-chip {
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 2px;
    color: rgba(241, 245, 249, 0.86);
    font-size: 0.68rem;
    font-weight: 800;
    padding: 0.18rem 0.36rem;
    text-transform: uppercase;
}

.live-draft-chip-success { border-color: rgba(45, 212, 191, 0.52); color: rgba(153, 246, 228, 0.96); }
.live-draft-chip-warning { border-color: rgba(245, 158, 11, 0.52); color: rgba(253, 230, 138, 0.96); }

.live-draft-command {
    align-items: center;
    border-left: 4px solid rgba(103, 232, 249, 0.84);
    display: grid;
    gap: 0.55rem;
    grid-template-columns: minmax(0, 1fr) minmax(9rem, 0.62fr);
    margin: 0.75rem 0;
    padding: 0.78rem 0.85rem;
}

.live-draft-command-mine {
    border-left-color: rgba(245, 158, 11, 0.88);
}

.live-draft-section-head {
    align-items: baseline;
    display: flex;
    gap: 0.45rem;
    justify-content: space-between;
    margin: 1rem 0 0.42rem;
}

.live-draft-section-head span {
    color: var(--color-text-primary, #f8fafc);
    font-size: 0.9rem;
    font-weight: 900;
}

.live-draft-section-head small {
    color: rgba(148, 163, 184, 0.82);
    font-size: 0.7rem;
    text-align: right;
}

.live-draft-rec-grid {
    display: grid;
    gap: var(--space-sm);
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr));
}

.live-draft-rec-card {
    border-left: var(--border-width-semantic) solid var(--color-opportunity);
    grid-template-columns: minmax(0, 1fr);
}

.live-draft-rec-card .dg-football-asset__body,
.live-draft-rec-card .dg-football-asset__value {
    grid-column: 1;
    min-width: 0;
    text-align: left;
}

.live-draft-rec-name {
    color: var(--color-text-primary);
    font: var(--font-card-title);
}

.live-draft-rec-executive {
    display: grid;
    gap: var(--space-sm);
    margin-top: var(--space-sm);
}

.live-draft-rec-why {
    color: var(--color-text-primary);
    font-size: var(--font-size-body);
    font-weight: var(--font-weight-metadata);
    line-height: var(--line-height-body);
    margin: 0;
}

.live-draft-rec-analysis {
    border-top: var(--border-width-default) solid var(--color-border);
    display: grid;
    gap: var(--space-sm);
    grid-template-columns: repeat(2, minmax(0, 1fr));
    opacity: 0.88;
    padding-top: var(--space-sm);
}

.live-draft-rec-analysis span {
    color: var(--color-text-secondary);
    font-size: var(--font-size-caption);
    line-height: var(--line-height-caption);
}

.live-draft-rec-analysis strong {
    color: var(--color-text-muted);
    display: block;
    font-size: var(--font-size-badge);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}

.live-draft-pick-latest {
    border-color: var(--border-accent);
}

.live-draft-pick-mine {
    border-inline-start: var(--border-width-semantic) solid var(--color-accent);
}

@media (max-width: 680px) {
    .live-draft-command {
        grid-template-columns: 1fr;
    }

    .live-draft-section-head {
        align-items: flex-start;
        flex-direction: column;
        gap: 0.12rem;
    }

    .live-draft-section-head small {
        text-align: left;
    }

    .live-draft-rec-grid,
    .live-draft-rec-analysis {
        grid-template-columns: 1fr;
    }

}
"""
