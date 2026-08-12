"""Route-scoped Trade Analyzer styles (lazy-injected — not APP_CSS)."""

TRADE_ANALYZER_CSS = """
/* Incoming-offer Trade Analyzer — uses design tokens only. */
.toa-share-card {
  background: var(--surface-1, #0f1114);
  border: var(--border-width-default, 1px) solid var(--border-standard, #2a2e36);
  border-radius: var(--radius-panel, 16px);
  color: var(--color-text-primary, #eceef2);
  display: grid;
  gap: var(--space-sm, 0.65rem);
  margin: 0;
  max-width: 40rem;
  padding: var(--space-md, 1rem);
}

.toa-brand {
  align-items: center;
  display: flex;
  gap: 0.55rem;
}

.toa-mark {
  color: #22d3ee;
  font-size: var(--font-size-card-title, 1.05rem);
  font-weight: var(--font-weight-title, 700);
  letter-spacing: 0.04em;
}

.toa-brand-name {
  color: var(--color-text-primary, #eceef2);
  font-size: var(--font-size-body, 0.95rem);
  font-weight: var(--font-weight-title, 700);
}

.toa-kicker {
  color: var(--color-text-secondary, #9ca3af);
  font-size: var(--font-size-metadata, 0.75rem);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.toa-partner {
  color: var(--color-text-secondary, #9ca3af);
  font-size: var(--font-size-body, 0.95rem);
}

.toa-verdict {
  font-size: clamp(1.75rem, 6vw, 2.4rem);
  font-weight: 800;
  letter-spacing: 0.02em;
  line-height: 1.05;
}

.toa-tone-accept .toa-verdict { color: #22d3ee; }
.toa-tone-counter .toa-verdict,
.toa-tone-fair .toa-verdict { color: #facc15; }
.toa-tone-decline .toa-verdict { color: #ef4444; }

.toa-band,
.toa-confidence {
  color: var(--color-text-secondary, #9ca3af);
  font-size: var(--font-size-metadata, 0.75rem);
}

.toa-rationale {
  font-size: var(--font-size-body, 0.98rem);
  line-height: 1.45;
}

.toa-sides {
  display: grid;
  gap: var(--space-sm, 0.65rem);
  grid-template-columns: minmax(0, 1fr);
}

@media (min-width: 700px) {
  .toa-sides {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  }
}

.toa-side {
  background: var(--surface-2, #15181d);
  border-left: 3px solid var(--border-standard, #2a2e36);
  border-radius: var(--radius-control, 12px);
  padding: var(--space-sm, 0.65rem);
}

.toa-side-receive { border-left-color: #22d3ee; }
.toa-side-send { border-left-color: #ef4444; }

.toa-side-label {
  color: var(--color-text-secondary, #9ca3af);
  font-size: var(--font-size-metadata, 0.72rem);
  letter-spacing: 0.05em;
  margin-bottom: 0.35rem;
  text-transform: uppercase;
}

.toa-asset {
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  padding: 0.35rem 0;
}

.toa-asset:first-of-type { border-top: 0; }

.toa-asset-name {
  font-size: 0.95rem;
  font-weight: 650;
}

.toa-asset-meta,
.toa-asset-empty {
  color: var(--color-text-secondary, #9ca3af);
  font-size: 0.78rem;
}

.toa-section-label {
  color: var(--color-text-secondary, #9ca3af);
  font-size: var(--font-size-metadata, 0.72rem);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.toa-section-body {
  font-size: 0.9rem;
  line-height: 1.4;
}

.toa-context,
.toa-footer {
  color: var(--color-text-secondary, #9ca3af);
  font-size: 0.78rem;
}

.toa-footer {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  color: #22d3ee;
  padding-top: 0.45rem;
}

.toa-entry-note {
  color: var(--color-text-secondary, #9ca3af);
  font-size: 0.9rem;
  margin: 0 0 var(--space-sm, 0.65rem);
}
"""
