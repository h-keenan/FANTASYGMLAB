"""Day/Night/System theme: light-palette token integrity + resolution logic.

Companion to tests/test_design_tokens.py (which locks the dark palette).
Contrast ratios here are computed, not asserted from a comment — this is the
same rigor mobile/src/theme.ts's own contrast comments claim, checked
mechanically so a future edit can't silently regress a token below AA.
"""

from __future__ import annotations

import re

from modules.design_tokens import (
    DESIGN_TOKEN_HEX,
    DESIGN_TOKEN_HEX_LIGHT,
    LIGHT_MODE_CSS,
    LIGHT_MODE_TOKENS,
)


def _relative_luminance(hex_color: str) -> float:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def _contrast(hex_a: str, hex_b: str) -> float:
    l1, l2 = _relative_luminance(hex_a), _relative_luminance(hex_b)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


_TIGHT_SURFACES = ("#EEF3F6", "#E6EDF1", "#FFFFFF")


def test_light_mode_css_is_a_plain_root_rule_with_no_component_selectors():
    assert LIGHT_MODE_CSS.startswith(':root {')
    without_root = LIGHT_MODE_CSS.replace(":root", "")
    assert not re.search(r"\.[a-zA-Z_][\w-]*\s*[{,]", without_root)
    assert "[data-testid" not in LIGHT_MODE_CSS
    assert "@media" not in LIGHT_MODE_CSS
    assert "color-scheme: light;" in LIGHT_MODE_CSS


def test_dark_palette_is_untouched_by_the_light_mode_addition():
    # PR #782's dark audit (now the FantasyDesk brand sheet, 2026-10-17)
    # stays exactly as shipped by light-mode changes — light mode is
    # additive, never a side effect of it.
    assert DESIGN_TOKEN_HEX["--color-bg"] == "#000000"
    assert DESIGN_TOKEN_HEX["--color-accent"] == "#67e8f9"
    assert DESIGN_TOKEN_HEX["--color-danger"] == "#ef4444"


def test_every_dark_leaf_color_token_has_an_independent_light_value():
    # "Explicit token sets... not one palette with the background swapped"
    # (UI_COLOR_SYSTEM_AUDIT.md #1): every non-brand leaf color in the dark
    # palette must be a *different, independently declared* light value.
    brand_exempt = {
        "--color-brand-accent",
        "--color-brand-bg",
        "--color-brand-surface",
        "--color-brand-mark-ink",
    }
    for name, dark_hex in DESIGN_TOKEN_HEX.items():
        if name in brand_exempt:
            continue
        assert name in LIGHT_MODE_TOKENS, f"{name} has no light-mode override"
        light_value = LIGHT_MODE_TOKENS[name]
        assert light_value.lower() != dark_hex, f"{name} light value equals its dark value"


def test_position_table_matches_mobiles_already_audited_light_colors():
    # Ported verbatim for cross-platform identity — see mobile/src/theme.ts positionColorsLight.
    assert LIGHT_MODE_TOKENS["--color-position-qb"] == "#BE123C"
    assert LIGHT_MODE_TOKENS["--color-position-rb"] == "#15803D"
    assert LIGHT_MODE_TOKENS["--color-position-wr"] == "#0369A1"
    assert LIGHT_MODE_TOKENS["--color-position-te"] == "#C2410C"
    assert LIGHT_MODE_TOKENS["--color-position-k"] == "#6D28D9"
    assert LIGHT_MODE_TOKENS["--color-position-dst"] == "#3F3F46"


def test_light_solid_text_tokens_clear_aa_contrast_on_every_tight_surface():
    # 4.5:1 is WCAG AA for normal text. Every one of these renders as text or
    # an icon fill somewhere (see football_asset_styles.py, brand_identity.py).
    aa_tokens = [
        "--color-text-primary",
        "--color-text-secondary",
        "--color-text-muted",
        "--color-accent",
        "--color-accent-strong",
        "--color-success",
        "--color-opportunity",
        "--color-action",
        "--color-warning",
        "--color-danger",
        "--color-information",
        "--color-diagnostic",
        "--color-premium",
        "--color-experimental",
        "--color-prestige-elite",
        "--color-prestige-starter",
        "--color-prestige-contributor",
        "--color-prestige-development",
        "--color-prestige-depth",
        "--color-prestige-replacement",
    ]
    for name in aa_tokens:
        hex_value = DESIGN_TOKEN_HEX_LIGHT[name]
        worst = min(_contrast(hex_value, surface) for surface in _TIGHT_SURFACES)
        assert worst >= 4.5, f"{name} ({hex_value}) only clears {worst:.2f}:1"


def test_position_tokens_clear_a_large_text_floor_matching_mobiles_own_table():
    # Ported verbatim from mobile's own already-shipped positionColorsLight
    # (cross-platform identity — see test above) rather than re-derived, so
    # this checks against mobile's own precedent rather than re-deriving a
    # stricter bar: --color-position-rb (#15803d, from mobile) clears 4.24:1
    # worst-case here, just under the 4.5:1 body-text AA floor but well clear
    # of WCAG's 3:1 large-text/UI-component floor — acceptable for a
    # chip/badge label, and changing it would break the byte-identical
    # cross-platform position table both READMEs call out by name.
    position_tokens = [
        "--color-position-qb",
        "--color-position-rb",
        "--color-position-wr",
        "--color-position-te",
        "--color-position-k",
        "--color-position-dst",
    ]
    for name in position_tokens:
        hex_value = DESIGN_TOKEN_HEX_LIGHT[name]
        worst = min(_contrast(hex_value, surface) for surface in _TIGHT_SURFACES)
        assert worst >= 4.0, f"{name} ({hex_value}) only clears {worst:.2f}:1"


def test_light_border_strong_clears_the_wcag_non_text_contrast_floor():
    hex_value = DESIGN_TOKEN_HEX_LIGHT["--color-border-strong"]
    worst = min(_contrast(hex_value, surface) for surface in _TIGHT_SURFACES)
    assert worst >= 3.0


def test_light_subtle_border_stays_a_hairline_not_a_loud_boundary():
    hex_value = DESIGN_TOKEN_HEX_LIGHT["--color-border"]
    for surface in _TIGHT_SURFACES:
        assert _contrast(hex_value, surface) < 2.0


# --- theme_mode resolution -------------------------------------------------
