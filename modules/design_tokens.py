"""Canonical semantic design tokens for DynastyGM.

This module is intentionally CSS-only. It owns stable visual primitives while
existing selectors continue to own presentation during incremental migration.
"""

DESIGN_TOKEN_CSS = """
/* DynastyGM semantic design tokens */
:root {
    /* Foundation */
    --color-bg: #010204;
    --color-shell: #050608;
    --color-surface-primary: rgba(13, 14, 17, 0.94);
    --color-surface-secondary: rgba(22, 23, 27, 0.78);
    --color-surface-raised: rgba(30, 31, 36, 0.82);
    --color-surface-muted: rgba(10, 11, 14, 0.72);
    --color-text-primary: #f8fafc;
    --color-text-secondary: #e5e7eb;
    --color-text-muted: #a8adb7;
    --color-border: rgba(248, 250, 252, 0.11);
    --color-border-strong: rgba(248, 250, 252, 0.18);

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

    /* Geometry */
    --radius-none: 0;
    --radius-sm: 2px;
    --radius-md: 7px;
    --radius-lg: 9px;
    --radius-panel: 11px;
    --radius-pill: 999px;

    /* Elevation */
    --shadow-none: none;
    --shadow-control: 0 8px 20px rgba(0, 0, 0, 0.18);
    --shadow-card: 0 14px 34px rgba(0, 0, 0, 0.28);
    --shadow-overlay: 0 20px 54px rgba(0, 0, 0, 0.34);
    --shadow-surface-inset: inset 0 1px 0 rgba(248, 250, 252, 0.035);

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
    --font-weight-title: 850;
    --font-weight-display: 900;
    --line-height-display: 1.05;
    --line-height-title: 1.1;
    --line-height-card: 1.2;
    --line-height-body: 1.45;
    --line-height-caption: 1.35;
    --font-page-title: var(--font-weight-display) var(--font-size-page-title) / var(--line-height-title) var(--font-family-sans);
    --font-card-title: var(--font-weight-title) var(--font-size-card-title) / var(--line-height-card) var(--font-family-sans);
    --font-body: var(--font-weight-body) var(--font-size-body) / var(--line-height-body) var(--font-family-sans);

    /* Focus, controls, and motion */
    --focus-ring: 0 0 0 3px rgba(103, 232, 249, 0.34);
    --control-min-height: 44px;
    --touch-target-min: 44px;
    --motion-fast: 120ms;
    --motion-standard: 180ms;
}
"""
