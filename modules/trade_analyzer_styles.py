"""Route-scoped Trade Analyzer styles (lazy-injected — not APP_CSS)."""

from modules.compact_fantasy_assets import COMPACT_FANTASY_ASSET_CSS

TRADE_ANALYZER_CSS = COMPACT_FANTASY_ASSET_CSS + """
/* Incoming-offer Trade Analyzer — uses design tokens only. */
.toa-share-card {
  background: var(--surface-1, #0f1114);
  border: var(--border-width-default, 1px) solid var(--border-standard, #2a2e35);
  border-radius: var(--radius-panel, 0);
  color: var(--color-text-primary, #f8fafc);
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

.toa-brand-name {
  color: var(--color-text-primary, #f8fafc);
  font-size: var(--font-size-body, 0.95rem);
  font-weight: var(--font-weight-title, 700);
}

.toa-kicker {
  color: var(--color-text-secondary, #e5e7eb);
  font-size: var(--font-size-metadata, 0.75rem);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.toa-partner {
  color: var(--color-text-secondary, #e5e7eb);
  font-size: var(--font-size-body, 0.95rem);
}

.toa-verdict {
  font-size: clamp(1.75rem, 6vw, 2.4rem);
  font-weight: 800;
  letter-spacing: 0.02em;
  line-height: 1.05;
}

/* Tone -> color follows the same mapping as mobile's canonical
   accept/decline/counter/fair verdict (never a raw value-sign lookup):
   accept=success, decline=danger, counter=accent, fair=neutral. Counter and
   fair used to share one amber, making two distinct verdicts read as one. */
.toa-tone-accept .toa-verdict { color: var(--color-success, #22c55e); }
.toa-tone-counter .toa-verdict { color: var(--color-accent-strong, #22d3ee); }
.toa-tone-fair .toa-verdict { color: var(--color-text-secondary, #e5e7eb); }
.toa-tone-decline .toa-verdict { color: var(--color-danger, #ef4444); }

.toa-band,
.toa-confidence {
  color: var(--color-text-secondary, #e5e7eb);
  font-size: var(--font-size-metadata, 0.75rem);
}

.toa-side {
  background: var(--surface-2, #15171b);
  border-left: 3px solid var(--border-standard, #2a2e35);
  border-radius: var(--radius-control, 12px);
  padding: var(--space-sm, 0.65rem);
}

/* Receive=success/send=danger, matching trade_visual_language.py's shared
   .dg-trade-side--get/--give convention (also used by Trade Hub) and
   mobile's You Receive/You Send dot colors. This used to override receive
   to accent-strong here, disagreeing with the shared module's green for the
   very same element (compact_matchup_html emits both class names). */
.toa-side-receive { border-left-color: var(--color-success, #22c55e); }
.toa-side-send { border-left-color: var(--color-danger, #ef4444); }

.toa-side-label {
  color: var(--color-text-secondary, #e5e7eb);
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
  color: var(--color-text-secondary, #e5e7eb);
  font-size: 0.78rem;
}

.toa-section-label {
  color: var(--color-text-secondary, #e5e7eb);
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
  color: var(--color-text-secondary, #e5e7eb);
  font-size: 0.78rem;
}

.toa-footer {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  color: var(--color-accent-strong);
  padding-top: 0.45rem;
}

.toa-value-edge:not(.tvl-edge) {
  color: var(--color-text-secondary, #e5e7eb);
  font-size: var(--font-size-metadata, 0.75rem);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.toa-value-edge:not(.tvl-edge) strong {
  color: var(--color-text-primary, #f8fafc);
  font-size: var(--font-size-body, 0.95rem);
  letter-spacing: 0;
  text-transform: none;
}

.toa-more {
  background: var(--surface-2, #15171b);
  padding: var(--space-xs, 0.35rem) var(--space-sm, 0.55rem);
}

.toa-more > summary {
  color: var(--color-text-secondary, #e5e7eb);
  cursor: pointer;
  font-size: var(--font-size-metadata, 0.75rem);
  letter-spacing: 0.05em;
  list-style: none;
  min-height: var(--touch-target-min, 44px);
  text-transform: uppercase;
}

.toa-more > summary::-webkit-details-marker { display: none; }

.toa-stage-kicker,
.toa-workspace-kicker,
.toa-block-kicker,
.toa-toolbar-kicker,
.toa-review-kicker {
  color: var(--color-text-secondary, #e5e7eb);
  font-size: var(--font-size-metadata, 0.72rem);
  font-weight: 750;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.toa-workspace {
  margin: 0 0 var(--space-sm, 0.65rem);
  max-width: 72rem;
  min-width: 0;
}

.toa-workspace-swap {
  color: var(--color-text-secondary, #e5e7eb);
  font-size: 0.78rem;
  margin: 0.15rem 0 0;
}

.toa-partner-block {
  margin: 0 0 var(--space-sm, 0.65rem);
  max-width: 28rem;
  min-width: 0;
}

.toa-partner-block + div[data-testid="stSelectbox"],
div[data-testid="stVerticalBlock"]:has(.toa-partner-block) [data-testid="stSelectbox"] {
  max-width: 28rem;
}

.toa-block {
  background: var(--surface-1, #0f1114);
  border: var(--border-width-default, 1px) solid var(--border-standard, #2a2e35);
  border-radius: var(--radius-panel, 0);
  margin: 0 0 var(--space-sm, 0.65rem);
  max-width: 100%;
  min-width: 0;
  padding: var(--space-sm, 0.65rem) var(--space-md, 1rem);
}

.toa-block-title {
  color: var(--color-text-primary, #f8fafc);
  font-size: 0.95rem;
  font-weight: 750;
  letter-spacing: 0.02em;
  margin: 0 0 0.15rem;
  text-transform: uppercase;
}

/* Same receive=success/send=danger convention as .toa-side-receive/-send
   above, so the builder columns and the result card agree on what
   "receive" means instead of one reading green and the other cyan. */
.toa-block-receive { border-inline-start: 3px solid var(--color-success, #22c55e); }
.toa-block-send { border-inline-start: 3px solid var(--color-danger, #ef4444); }

.toa-chip-list { display: grid; gap: 0.4rem; margin: 0.35rem 0 0.55rem; }

.toa-chip {
  background: var(--surface-2, #15171b);
  border: var(--border-width-default, 1px) solid var(--border-standard, #2a2e35);
  min-width: 0;
  padding: var(--space-xs, 0.35rem) var(--space-sm, 0.55rem);
  width: max-content;
  max-width: 100%;
}

.toa-chip-copy { min-width: 0; }

.toa-chip-name {
  color: var(--color-text-primary, #f8fafc);
  font-size: 0.92rem;
  font-weight: 650;
  overflow-wrap: anywhere;
}

.toa-chip-meta {
  color: var(--color-text-secondary, #e5e7eb);
  font-size: 0.75rem;
}

.toa-chip-value {
  color: var(--color-text-muted, rgba(229, 231, 235, 0.52));
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.toa-result-row {
  min-width: 0;
  padding: 0.2rem 0;
  width: max-content;
  max-width: 100%;
}

.toa-result-row--selected {
  background: var(--color-muted-soft, rgba(148, 163, 184, 0.12));
  border-radius: var(--radius-control, 12px);
  padding: 0.25rem 0.35rem;
}

.toa-empty-package {
  color: var(--color-text-secondary, #e5e7eb);
  font-size: 0.8rem;
  margin: 0.25rem 0 0.5rem;
}

.toa-analyze-row { margin-top: var(--space-md, 1rem); max-width: 22rem; }

.toa-analyze-row + div [data-testid="stButton"] button {
  min-height: var(--touch-target-min, 44px);
  min-width: 11rem;
}

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
  color: var(--color-text-secondary, #e5e7eb);
  font-size: 0.78rem;
  font-weight: 500;
  letter-spacing: 0;
  margin: 0.1rem 0 0;
  text-transform: none;
}

.toa-toolbar { margin: 0.35rem 0 0.15rem; }

div[class*="st-key-toa_roster_"] {
  max-height: min(40vh, 16.5rem);
  min-width: 0;
  overflow-x: hidden;
  overflow-y: auto;
}

div[data-testid="stVerticalBlock"]:has(.toa-assembly-stack) [role="radiogroup"] {
  flex-wrap: wrap !important;
  gap: 0.2rem 0.35rem;
  min-width: 0;
}

div[data-testid="stVerticalBlock"]:has(.toa-assembly-stack) [data-testid="stTextInput"] {
  max-width: 22rem;
}

div[data-testid="stVerticalBlock"]:has(.toa-assembly-stack) [data-testid="stTextInput"] input {
  min-height: var(--touch-target-min, 44px);
  min-width: 0;
}

/* Chip/result rows only — never the outer You send | You receive columns. */
div[data-testid="stHorizontalBlock"]:has(.toa-chip):not(:has(.toa-block)),
div[data-testid="stHorizontalBlock"]:has(.toa-result-row):not(:has(.toa-block)) {
  align-items: center;
  flex-direction: row !important;
  flex-wrap: nowrap !important;
  gap: 0.35rem !important;
  justify-content: flex-start !important;
  max-width: 100%;
  width: max-content;
}

div[data-testid="stHorizontalBlock"]:has(.toa-chip):not(:has(.toa-block)) > div:first-child,
div[data-testid="stHorizontalBlock"]:has(.toa-result-row):not(:has(.toa-block)) > div:first-child {
  flex: 1 1 auto !important;
  min-width: 0 !important;
  width: auto !important;
}

div[data-testid="stHorizontalBlock"]:has(.toa-chip):not(:has(.toa-block)) > div:last-child {
  flex: 0 0 2.85rem !important;
  max-width: 2.85rem !important;
  min-width: 2.85rem !important;
  width: 2.85rem !important;
}

div[data-testid="stHorizontalBlock"]:has(.toa-result-row):not(:has(.toa-block)) > div:last-child {
  flex: 0 0 5.25rem !important;
  max-width: 5.25rem !important;
  min-width: 5.25rem !important;
  width: 5.25rem !important;
}

/* Desktop two-side workspace; stack below 1024 so 320/390/430 never sit 50/50. */
div[data-testid="stHorizontalBlock"]:has(.toa-block-send):has(.toa-block-receive) {
  align-items: stretch;
  gap: var(--space-md, 1rem) !important;
  max-width: 72rem;
}

@media (max-width: 1023px) {
  div[data-testid="stHorizontalBlock"]:has(.toa-block-send):has(.toa-block-receive) {
    flex-direction: column !important;
    flex-wrap: wrap !important;
  }
  div[data-testid="stHorizontalBlock"]:has(.toa-block-send):has(.toa-block-receive) > div {
    min-width: 0 !important;
    width: 100% !important;
  }
  .toa-workspace-swap { display: none; }
}

@media (min-width: 1024px) {
  div[data-testid="stHorizontalBlock"]:has(.toa-block-send):has(.toa-block-receive) {
    flex-wrap: nowrap !important;
  }
  div[data-testid="stHorizontalBlock"]:has(.toa-block-send):has(.toa-block-receive) > div {
    min-width: 0 !important;
  }
}

@media (max-width: 768px) {
  div[data-testid="stHorizontalBlock"]:has(.toa-chip):not(:has(.toa-block)),
  div[data-testid="stHorizontalBlock"]:has(.toa-result-row):not(:has(.toa-block)) {
    flex-flow: row nowrap !important;
    width: 100%;
  }
}
"""
