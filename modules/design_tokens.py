"""Canonical semantic design tokens for DynastyGM.

This module is intentionally CSS-only. It owns stable visual primitives while
existing selectors continue to own presentation during incremental migration.
The one Python-side export, ``DESIGN_TOKEN_HEX``, is read back out of that same
CSS so code that must *compute* on a token (contrast, for example) never
restates a hex value.
"""

import re

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
    /* WCAG 1.4.11 non-text contrast: #41464f only cleared 1.76-2.14:1 against
       our surfaces (needs 3:1 for a boundary essential to identifying a
       control). #64748b clears 3.46-4.26:1 across surface-raised/-secondary/
       bg while staying in the same cool-slate family, so card and control
       outlines read as intentional edges instead of a near-invisible line. */
    --color-border-strong: #64748b;
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
    /* Small inverted "founder badge" / brand-mark glyph: a fixed light chip
       (--color-text-primary) with dark ink text, independent of the dark
       theme's normal foreground/background pairing. Was copy-pasted as the
       raw literal #0b1220 across trade_hub_ui, startup_coordinator, and
       brand_identity_styles — promoted here so it has one source instead
       of three. */
    --color-brand-mark-ink: #0b1220;

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

    /* Position identity (chip/accent only — never recolor the player card).
       Matched to Sleeper's own position colors (saturated, not pastel) —
       QB and K were previously swapped hues (QB pale violet, K pale pink)
       against Sleeper's rose-red QB / violet K, and RB/WR were noticeably
       more washed out than Sleeper's bolder fills. */
    --color-position-qb: #fb7185;
    --color-position-rb: #4ade80;
    --color-position-wr: #38bdf8;
    --color-position-te: #fb923c;
    --color-position-k: #a78bfa;
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

    color-scheme: dark;
}
"""


_TOKEN_HEX_DECLARATION = re.compile(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;")

# Literal #rrggbb tokens, resolved from the CSS above — the single source.
DESIGN_TOKEN_HEX: dict[str, str] = {
    name: value.lower() for name, value in _TOKEN_HEX_DECLARATION.findall(DESIGN_TOKEN_CSS)
}

# ---------------------------------------------------------------------------
# Light theme ("Day" mode)
# ---------------------------------------------------------------------------
#
# Color-system audit (2026-09-26, coridian_): the web app had zero light-mode
# infrastructure — DESIGN_TOKEN_CSS defined exactly one (dark) palette. This
# section adds a genuinely independent light palette using the same
# contrast-driven methodology mobile/src/theme.ts's lightColors already
# documents: every leaf color token is re-derived against actual WCAG
# contrast ratios on the *light* surfaces, not produced by inverting or
# lightening the dark hex. Every ratio below was computed (relative
# luminance / (L1+0.05)/(L2+0.05)) against this palette's three tightest
# surfaces — --color-bg #EEF3F6, --color-surface-muted #E6EDF1, and
# --color-surface-primary #FFFFFF — not eyeballed.
#
# Only *leaf* tokens are listed here. Every alias in DESIGN_TOKEN_CSS above
# (--surface-page, --text-primary, --border-subtle, --text-accent, ...) is
# declared once as `var(--color-*)` and is intentionally NOT repeated here:
# CSS custom-property substitution resolves per-element at compute time, so
# when this block's `:root { ... }` rule is injected as a second <style> tag
# (see LIGHT_MODE_CSS below), an alias declared only in DESIGN_TOKEN_CSS's
# `:root` still resolves against *this* block's override of the leaf
# property it points to, by ordinary CSS cascade (same selector specificity,
# later source order wins). Repeating every alias here would be the same
# "one palette, background swapped" anti-pattern UI_COLOR_SYSTEM_AUDIT.md §1
# warns about, just inverted — the fix is deriving the leaves independently,
# which is what the values below do.
#
# Brand-identity constants (--color-brand-accent/-bg/-surface,
# --color-brand-mark-ink) are deliberately NOT overridden: they're a fixed
# marketing/build-identity swatch independent of the active theme (mark-ink's
# own comment already says as much), not a themed surface color.
LIGHT_MODE_TOKENS: dict[str, str] = {
    # Foundation. Dark mode gets *lighter* as a surface is elevated (bg <
    # shell < surface-primary < surface-secondary < surface-raised); light
    # mode inverts which end is "loudest" the way every mainstream light UI
    # does — pure white can't get whiter, so cards read as elevated by being
    # the brightest thing on a tinted ("glacier ice") page instead. bg/shell
    # sit close together (a small step, mirroring dark's own ~0.001-luminance
    # bg->shell gap) and every card-family tier resolves toward white.
    "--color-bg": "#EEF3F6",
    "--color-shell": "#E5ECF1",
    "--color-surface-primary": "#FFFFFF",
    "--color-surface-secondary": "#F5F9FB",
    "--color-surface-raised": "#FFFFFF",
    "--color-surface-muted": "#E6EDF1",
    # Text. text-primary/-secondary clear 15-17:1 / 7.6-9.1:1 against every
    # surface above (huge margin, matching dark's own headroom). text-muted
    # (#57646F) is the one tuned to a floor rather than a ceiling: 5.09:1
    # worst-case (vs --color-surface-muted) — comfortably AA (4.5:1) without
    # reading as a second "secondary" tone.
    "--color-text-primary": "#101820",
    "--color-text-secondary": "#3B4A56",
    "--color-text-muted": "#57646F",
    # Borders. --color-border stays a true hairline (1.37-1.53:1 — same
    # "line, not a boundary" role as dark's 1.39-1.49:1); --color-border-strong
    # is WCAG 1.4.11's 3:1 non-text-contrast floor, same rationale as dark's
    # own #64748b comment above — 4.59-5.48:1 worst-case here (dark: 3.5-4.26:1).
    "--color-border": "#C7D3DA",
    "--color-border-strong": "#5D6B77",

    # Interaction and meaning. Every one of these is the *same hue/saturation*
    # as its dark-mode counterpart with only HSL lightness reduced (via
    # colorsys, not by eye) until it cleared >=5:1 against all three tight
    # surfaces — brand cyan included, so "primary interaction" keeps its
    # identity instead of being reinterpreted as a generic dark blue.
    # --color-information mirrors --color-accent (dark does the same: both
    # #67e8f9), and --color-experimental mirrors --color-diagnostic (dark:
    # both #8b93ff) — preserving the existing "these two are the same brand
    # hue" relationships instead of inventing a new one.
    "--color-accent": "#056E7C",  # from #67e8f9; 5.03-6.00:1
    "--color-accent-strong": "#08616E",  # from #22d3ee; 6.34-7.56:1
    "--color-accent-soft": "rgba(6, 110, 124, 0.16)",
    "--color-success": "#147337",  # from #22c55e; 5.02-6.63:1
    "--color-opportunity": "#0C7065",  # from #14b8a6; 5.04-6.82:1
    "--color-action": "#796103",  # from #facc15; 5.04-6.78:1
    "--color-warning": "#8A5906",  # from #f59e0b; 5.05-6.98:1
    "--color-danger": "#C81111",  # from #ef4444; 5.01-6.87:1
    "--color-information": "#056E7C",
    "--color-diagnostic": "#5F52C8",  # from #8b93ff via mobile's lightColors.violet
    "--color-premium": "#796103",
    "--color-experimental": "#5F52C8",
    # rgba(dark-ink) rather than rgba(light-gray) — same role as dark's
    # rgba(white, .52) muted-text overlay, inverted for a light ground.
    # Deliberately left under AA (mirrors mobile's textDisabled rationale:
    # WCAG's minimums don't apply to disabled text, and disabled needs to
    # read as dimmer than --color-text-muted).
    "--color-muted": "rgba(16, 24, 32, 0.45)",

    # Player prestige. Dark mode's ramp runs from near-white (starter) down
    # to a dim slate (depth) because *lighter* reads as "closer to full
    # text" on a near-black ground. On a light ground the same meaning
    # ("closer to full text = higher tier") requires the ramp to run the
    # other way — starter closest to --color-text-primary, depth closest to
    # (but still 4.81:1+ clear of) the page. All four resolved by bisecting
    # HSL lightness against a plain blue-gray until each cleared >=4.5:1
    # worst-case, so the tier ladder stays legible as *text* (it's used as
    # `color:`, not just a fill, in football_asset_styles.py) instead of
    # trailing off into a decorative-only low-contrast smear.
    "--color-prestige-elite": "#7D5B07",  # gold family, same treatment as --color-premium; 5.26:1
    "--color-prestige-starter": "#34404C",  # 8.95:1 — highest non-elite tier, darkest/strongest
    "--color-prestige-contributor": "#48545F",  # 6.55:1
    "--color-prestige-development": "#56626E",  # 5.27:1
    "--color-prestige-depth": "#5C6874",  # 4.81:1 — lowest tier, still clears AA
    "--color-prestige-replacement": "#B0393D",  # 5.07:1 — distinct shade from --color-danger, same as dark's #ef6a6a vs #ef4444 split

    # Position identity. Ported verbatim from mobile's already-audited
    # positionColorsLight (mobile/src/theme.ts, color-system audit
    # 2026-09-25) rather than re-derived — same cross-platform identity
    # mobile's own comment documents for the *dark* position table
    # ("byte-identical... matched to Sleeper's own position colors"), so the
    # light table stays byte-identical to mobile's for the same reason.
    "--color-position-qb": "#BE123C",
    "--color-position-rb": "#15803D",
    "--color-position-wr": "#0369A1",
    "--color-position-te": "#C2410C",
    "--color-position-k": "#6D28D9",
    "--color-position-dst": "#3F3F46",

    # Semantic soft surfaces. Unlike the solid tokens above, these keep the
    # *original vivid* hue (not the darkened text-safe one) — they're
    # decorative chip/card fills, not text, and a low-alpha wash of the
    # vivid hue over white is what actually reads as a colored tint instead
    # of vanishing. Alpha is raised versus dark's 0.12-0.15 (0.16-0.20 here)
    # specifically because the audit calls out "pale cyan does not
    # disappear" by name — a dark-tuned low alpha over white washes out much
    # faster than the same alpha over near-black. Composited over
    # --color-surface-primary, the matching solid token (e.g. --color-success
    # text on a --color-success-soft chip) still clears 4.80-5.49:1 on top.
    "--color-success-soft": "rgba(34, 197, 94, 0.16)",
    "--color-opportunity-soft": "rgba(20, 184, 166, 0.16)",
    "--color-action-soft": "rgba(250, 204, 21, 0.18)",
    "--color-warning-soft": "rgba(245, 158, 11, 0.16)",
    "--color-danger-soft": "rgba(239, 68, 68, 0.16)",
    "--color-information-soft": "rgba(103, 232, 249, 0.20)",
    "--color-diagnostic-soft": "rgba(139, 147, 255, 0.16)",
    "--color-muted-soft": "rgba(16, 24, 32, 0.06)",

    # Focus ring — same accent hue, raised alpha (dark 0.34 -> light 0.45):
    # a translucent ring needs more opacity to read against a light ground.
    "--focus-ring": "0 0 0 3px rgba(6, 110, 124, 0.45)",
    # Dark mode's inset rim is a light hairline "catching light" on a
    # near-black card (see --shadow-surface-inset's comment intent above);
    # a light card doesn't need a light catch-line, it needs the inverse — a
    # faint dark hairline reading as a top-edge groove instead of a glow.
    "--shadow-surface-inset": "inset 0 1px 0 rgba(10, 30, 45, 0.05)",

    "color-scheme": "light",
}

# Emitted as a second, plain `:root { ... }` rule — not gated behind a
# `[data-theme]` attribute selector. Streamlit is server-rendered, so the
# resolved mode (modules/theme_mode.resolve_is_dark) is already known in
# Python before any CSS is sent; app.py only injects this block's <style> tag
# at all when the resolved mode is light, immediately after DESIGN_TOKEN_CSS's
# <style> tag, so it wins on source order at equal `:root` specificity
# without needing a client-side attribute toggle for the *initial* paint.
LIGHT_MODE_CSS = ":root {\n" + "\n".join(
    f"    {name}: {value};" for name, value in LIGHT_MODE_TOKENS.items()
) + "\n}\n"

# Same extraction as DESIGN_TOKEN_HEX, scoped to the light palette. Not
# consumed anywhere today (DESIGN_TOKEN_HEX's one caller, player_tier_identity.py,
# computes a dark-surface-relative brightness and is unchanged by this task),
# kept for parity / future use and exercised by tests so the two palettes
# can be diffed token-by-token.
DESIGN_TOKEN_HEX_LIGHT: dict[str, str] = {
    name: value.lower() for name, value in _TOKEN_HEX_DECLARATION.findall(LIGHT_MODE_CSS)
}
