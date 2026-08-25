"""Canonical semantic design tokens for DynastyGM.

This module is intentionally CSS-only. It owns stable visual primitives while
existing selectors continue to own presentation during incremental migration.
"""

DESIGN_TOKEN_CSS = """
/* DynastyGM semantic design tokens */
:root {
    /* Foundation */
    --color-bg: #050607;
    --color-shell: #090a0c;
    --color-surface-primary: #0f1114;
    --color-surface-secondary: #15171b;
    --color-surface-raised: #1b1e23;
    --color-surface-muted: #0b0c0f;
    --color-text-primary: #f8fafc;
    --color-text-secondary: #e5e7eb;
    --color-text-muted: #a8adb7;
    --color-border: #2a2e35;
    --color-border-strong: #41464f;
    --border-width-default: 1px;
    --border-width-semantic: 3px;

    /* Semantic surface / text / border aliases (single source; do not redefine values) */
    --surface-page: var(--color-bg);
    --surface-1: var(--color-surface-primary);
    --surface-2: var(--color-surface-secondary);
    --surface-raised: var(--color-surface-raised);
    --surface-interactive: var(--color-surface-raised);
    --surface-selected: var(--color-accent-soft);
    --text-primary: var(--color-text-primary);
    --text-secondary: var(--color-text-secondary);
    --text-muted: var(--color-text-muted);
    --text-disabled: var(--color-muted);
    --text-accent: var(--color-accent);
    --text-positive: var(--color-success);
    --text-warning: var(--color-warning);
    --text-negative: var(--color-danger);
    --border-subtle: var(--color-border);
    --border-standard: var(--color-border);
    --border-strong: var(--color-border-strong);
    --border-accent: var(--color-accent);

    /* Brand accent aliases (FantasyGM Lab identity — keep in sync with brand_identity.py) */
    --color-brand-accent: #22d3ee;
    --color-brand-bg: #050607;
    --color-brand-surface: #0f1114;
    /* Trajectory motif (brand language only — do not map to Trust/rank/advice) */
    --color-brand-trajectory-analyze: #22d3ee;
    --color-brand-trajectory-project: #facc15;
    --color-brand-trajectory-execute: #ef4444;

    /* Interaction and meaning */
    --color-accent: #67e8f9;
    --color-accent-strong: #22d3ee;
    --color-accent-soft: rgba(103, 232, 249, 0.14);
    --color-success: #22c55e;
    --color-opportunity: #14b8a6;
    --color-action: #facc15;
    --color-warning: #f59e0b;
    --color-danger: #ef4444;
    --color-information: #67e8f9;
    --color-diagnostic: #8b93ff;
    --color-premium: #facc15;
    --color-experimental: #8b93ff;
    --color-muted: rgba(229, 231, 235, 0.52);

    /* Player prestige: consistent everywhere, independent of page context */
    --color-prestige-elite: #d8b85a;
    --color-prestige-starter: #d7dbe2;
    --color-prestige-contributor: #9da4ae;
    --color-prestige-development: #79818c;
    --color-prestige-depth: #626a75;
    --color-prestige-replacement: #ef6a6a;

    /* Position identity (chip/accent only — never recolor the player card) */
    --color-position-qb: #c4b5fd;
    --color-position-rb: #86efac;
    --color-position-wr: #7dd3fc;
    --color-position-te: #fcd34d;
    --color-position-k: #fda4af;
    --color-position-dst: #d4d4d8;

    /* Semantic soft surfaces */
    --color-success-soft: rgba(34, 197, 94, 0.15);
    --color-opportunity-soft: rgba(20, 184, 166, 0.14);
    --color-action-soft: rgba(250, 204, 21, 0.14);
    --color-warning-soft: rgba(245, 158, 11, 0.14);
    --color-danger-soft: rgba(239, 68, 68, 0.15);
    --color-information-soft: rgba(103, 232, 249, 0.12);
    --color-diagnostic-soft: rgba(139, 147, 255, 0.12);
    --color-muted-soft: rgba(229, 231, 235, 0.06);

    /* Spacing */
    --space-xs: 4px;
    --space-sm: 8px;
    --space-md: 12px;
    --space-lg: 16px;
    --space-xl: 24px;
    --space-2xl: 32px;
    --space-3xl: 48px;
    --space-4xl: 64px;
    --space-2xs: 2px;

    /* Canonical fantasy-asset portrait sizes (HTML surfaces). Share PNG uses its own scale. */
    --size-asset-chip: 1.5rem;
    --size-asset-compact: 2.25rem;
    --size-asset-standard: 2.75rem;
    /* My Team roster-core identity portraits (side-by-side, not list avatars). */
    --size-roster-core-portrait: 5.5rem;
    --size-roster-core-portrait-lg: 6rem;

    /* Geometry — small intentional scale (square / control / panel / pill / segment) */
    --radius-none: 0;
    --radius-square: 0;
    --radius-sm: 0;
    --radius-md: 0;
    --radius-lg: 0;
    --radius-control: 0;
    --radius-panel: 0;
    --radius-pill: 2px;
    /* Segmented filter chips only (st.pills / genuine filter segments) */
    --radius-segment: 999px;

    /* Elevation */
    --shadow-none: none;
    --shadow-control: 0 2px 0 rgba(0, 0, 0, 0.32);
    --shadow-card: 0 3px 0 rgba(0, 0, 0, 0.34);
    --shadow-overlay: 0 8px 24px rgba(0, 0, 0, 0.46);
    --shadow-surface-inset: inset 0 1px 0 rgba(248, 250, 252, 0.025);

    /* Opacity */
    --opacity-primary: 1;
    --opacity-secondary: 0.82;
    --opacity-metadata: 0.68;
    --opacity-disabled: 0.5;
    --opacity-divider: 0.12;

    /* Typography */
    --font-family-sans: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    --font-size-display: 2rem;
    --font-size-page-title: 1.5rem;
    --font-size-section-title: 1.125rem;
    --font-size-card-title: 0.875rem;
    --font-size-body: 0.875rem;
    --font-size-caption: 0.75rem;
    --font-size-badge: 0.6875rem;
    --font-size-numeric: 1.375rem;
    --font-weight-body: 500;
    --font-weight-metadata: 650;
    --font-weight-button: 750;
    --font-weight-title: 800;
    --font-weight-display: 900;
    --line-height-display: 1.05;
    --line-height-title: 1.1;
    --line-height-card: 1.2;
    --line-height-body: 1.45;
    --line-height-caption: 1.35;
    --line-height-badge: 1;
    --letter-spacing-badge: 0.085em;
    --font-page-title: var(--font-weight-display) var(--font-size-page-title) / var(--line-height-title) var(--font-family-sans);
    --font-card-title: var(--font-weight-title) var(--font-size-card-title) / var(--line-height-card) var(--font-family-sans);
    --font-body: var(--font-weight-body) var(--font-size-body) / var(--line-height-body) var(--font-family-sans);

    /* Founder Beta information hierarchy */
    --type-page-eyebrow-size: var(--font-size-badge);
    --type-page-title-size: clamp(1.85rem, 4.5vw, 2.75rem);
    --type-page-description-size: var(--font-size-body);
    --type-section-eyebrow-size: var(--font-size-badge);
    --type-section-title-size: clamp(1.35rem, 2.5vw, 1.75rem);
    --type-card-title-size: 1rem;
    --type-primary-metric-size: clamp(1.5rem, 2vw, 1.85rem);
    --type-supporting-metadata-size: 0.6875rem;
    --type-body-explanation-size: var(--font-size-body);
    --type-badge-size: var(--font-size-badge);
    --type-caption-emphasis: var(--font-weight-metadata) var(--font-size-caption) / var(--line-height-caption) var(--font-family-sans);
    --type-page-title: var(--font-weight-display) var(--type-page-title-size) / 1 var(--font-family-sans);
    --type-section-title: var(--font-weight-display) var(--type-section-title-size) / var(--line-height-title) var(--font-family-sans);
    --type-card-title: var(--font-weight-title) var(--type-card-title-size) / var(--line-height-card) var(--font-family-sans);
    --type-primary-metric: var(--font-weight-display) var(--type-primary-metric-size) / var(--line-height-title) var(--font-family-sans);
    --type-supporting-metadata: var(--font-weight-metadata) var(--type-supporting-metadata-size) / var(--line-height-caption) var(--font-family-sans);
    --type-body-explanation: var(--font-weight-body) var(--type-body-explanation-size) / var(--line-height-body) var(--font-family-sans);

    /* Focus, controls, and motion */
    --focus-ring: 0 0 0 3px rgba(103, 232, 249, 0.34);
    --control-min-height: 44px;
    --touch-target-min: 44px;
    --motion-fast: 120ms;
    --motion-standard: 180ms;

    /* Streamlit theme bridge — widgets inherit tokens, not leftover config blues */
    --primary-color: var(--color-accent-strong);
    --background-color: var(--color-bg);
    --secondary-background-color: var(--color-surface-primary);
    --text-color: var(--color-text-primary);
}
"""
