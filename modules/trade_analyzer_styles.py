"""Route-scoped Trade Analyzer styles (lazy-injected — not APP_CSS)."""

from modules.compact_fantasy_assets import COMPACT_FANTASY_ASSET_CSS

TRADE_ANALYZER_CSS = COMPACT_FANTASY_ASSET_CSS + """
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
  color: var(--color-accent-strong, #22d3ee);
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

.toa-tone-accept .toa-verdict { color: var(--color-accent-strong, #22d3ee); }
.toa-tone-counter .toa-verdict,
.toa-tone-fair .toa-verdict { color: var(--color-warning, #f59e0b); }
.toa-tone-decline .toa-verdict { color: var(--color-danger, #ef4444); }

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

.toa-value-edge {
  color: var(--color-text-secondary, #9ca3af);
  font-size: var(--font-size-metadata, 0.75rem);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.toa-value-edge strong {
  color: var(--color-text-primary, #eceef2);
  font-size: var(--font-size-body, 0.95rem);
  letter-spacing: 0;
  text-transform: none;
}

.toa-more {
  background: var(--surface-2, #15181d);
  padding: var(--space-xs, 0.35rem) var(--space-sm, 0.55rem);
}

.toa-more > summary {
  color: var(--color-text-secondary, #9ca3af);
  cursor: pointer;
  font-size: var(--font-size-metadata, 0.75rem);
  letter-spacing: 0.05em;
  list-style: none;
  min-height: var(--touch-target-min, 44px);
  text-transform: uppercase;
}

.toa-more > summary::-webkit-details-marker { display: none; }

.toa-analyze-row + div [data-testid="stButton"] button {
  min-height: var(--touch-target-min, 44px);
}

.toa-entry-note {
  color: var(--color-text-secondary, #9ca3af);
  font-size: 0.9rem;
  margin: 0 0 var(--space-sm, 0.65rem);
}

.toa-block {
  background: var(--surface-1, #0f1114);
  border: var(--border-width-default, 1px) solid var(--border-standard, #2a2e36);
  border-radius: var(--radius-panel, 16px);
  margin: 0 0 var(--space-sm, 0.65rem);
  padding: var(--space-sm, 0.65rem) var(--space-md, 1rem);
}

.toa-block-title {
  color: var(--color-text-primary, #eceef2);
  font-size: 0.95rem;
  font-weight: 750;
  letter-spacing: 0.02em;
  margin: 0 0 0.35rem;
  text-transform: uppercase;
}

.toa-block-receive { border-inline-start: 3px solid var(--color-accent-strong, #22d3ee); }
.toa-block-send { border-inline-start: 3px solid var(--color-danger, #ef4444); }

.toa-chip-list { display: grid; gap: 0.4rem; margin: 0.35rem 0 0.55rem; }

.toa-chip {
  background: var(--surface-2, #15181d);
  border: var(--border-width-default, 1px) solid var(--border-standard, #2a2e36);
  min-width: 0;
  padding: var(--space-xs, 0.35rem) var(--space-sm, 0.55rem);
}

.toa-chip-copy { min-width: 0; }

.toa-chip-name {
  color: var(--color-text-primary, #eceef2);
  font-size: 0.92rem;
  font-weight: 650;
  overflow-wrap: anywhere;
}

.toa-chip-meta {
  color: var(--color-text-secondary, #9ca3af);
  font-size: 0.75rem;
}

.toa-chip-value {
  color: var(--color-text-muted, #9ca3af);
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.toa-result-row {
  min-width: 0;
  padding: 0.15rem 0;
}

.toa-empty-package {
  color: var(--color-text-secondary, #9ca3af);
  font-size: 0.8rem;
  margin: 0.25rem 0 0.5rem;
}

.toa-partner-block { margin: 0 0 var(--space-sm, 0.65rem); }

.toa-analyze-row { margin-top: var(--space-md, 1rem); }

.toa-add-feedback {
  color: var(--color-accent-strong, #22d3ee);
  font-size: 0.8rem;
  margin: 0.2rem 0 0.45rem;
}

.toa-assembly-stack,
.toa-side-caption {
  min-width: 0;
}

.toa-side-caption {
  color: var(--color-text-secondary, #9ca3af);
  font-size: 0.78rem;
  font-weight: 500;
  letter-spacing: 0;
  margin: 0.1rem 0 0;
  text-transform: none;
}

div[class*="st-key-toa_roster_"] {
  max-height: min(40vh, 16.5rem);
  min-width: 0;
  overflow-x: hidden;
  overflow-y: auto;
}

div[data-testid="stVerticalBlock"]:has(.toa-assembly-stack) [role="radiogroup"] {
  flex-wrap: wrap !important;
  gap: 0.2rem 0.45rem;
  min-width: 0;
}

div[data-testid="stVerticalBlock"]:has(.toa-assembly-stack) [data-testid="stTextInput"] input {
  min-width: 0;
}

@media (max-width: 700px) {
  div[data-testid="stVerticalBlock"]:has(.toa-builder-marker) > div > [data-testid="stHorizontalBlock"] {
    flex-direction: column !important;
  }
  div[data-testid="stVerticalBlock"]:has(.toa-builder-marker) > div > [data-testid="stHorizontalBlock"] > div {
    min-width: 0 !important;
    width: 100% !important;
  }
}

/* Chip/result rows only — never the outer You receive | You send columns. */
div[data-testid="stHorizontalBlock"]:has(.toa-chip):not(:has(.toa-block)),
div[data-testid="stHorizontalBlock"]:has(.toa-result-row):not(:has(.toa-block)) {
  align-items: center;
  flex-wrap: nowrap !important;
  gap: 0.35rem !important;
}

div[data-testid="stHorizontalBlock"]:has(.toa-chip):not(:has(.toa-block)) > div:first-child,
div[data-testid="stHorizontalBlock"]:has(.toa-result-row):not(:has(.toa-block)) > div:first-child {
  flex: 1 1 auto !important;
  min-width: 0 !important;
  width: auto !important;
}

div[data-testid="stHorizontalBlock"]:has(.toa-chip):not(:has(.toa-block)) > div:last-child,
div[data-testid="stHorizontalBlock"]:has(.toa-result-row):not(:has(.toa-block)) > div:last-child {
  flex: 0 0 2.85rem !important;
  max-width: 2.85rem !important;
  min-width: 2.85rem !important;
  width: 2.85rem !important;
}
"""
