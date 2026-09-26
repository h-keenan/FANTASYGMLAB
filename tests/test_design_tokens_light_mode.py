"""Day/Night/System theme: light-palette token integrity + resolution logic.

Companion to tests/test_design_tokens.py (which locks the dark palette).
Contrast ratios here are computed, not asserted from a comment — this is the
same rigor mobile/src/theme.ts's own contrast comments claim, checked
mechanically so a future edit can't silently regress a token below AA.
"""

from __future__ import annotations

import re

from modules import theme_mode
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
    # PR #782's dark audit stays exactly as shipped — light mode is additive.
    assert DESIGN_TOKEN_HEX["--color-bg"] == "#050607"
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


def test_stored_mode_defaults_to_dark_and_validates_the_value_set():
    assert theme_mode.stored_mode(None) == "dark"
    assert theme_mode.stored_mode({"settings": {"theme_mode": "light"}}) == "light"
    assert theme_mode.stored_mode({"settings": {"theme_mode": "bogus"}}) == "dark"


def test_current_mode_prefers_the_live_widget_value_over_everything_else():
    session = {
        theme_mode.RADIO_WIDGET_KEY: "light",
        theme_mode.LOCAL_OVERRIDE_KEY: "dark",
        "account_user_settings": {"settings": {"theme_mode": "auto"}},
    }
    assert theme_mode.current_mode(session) == "light"


def test_current_mode_falls_back_to_local_override_then_stored():
    assert theme_mode.current_mode({theme_mode.LOCAL_OVERRIDE_KEY: "light"}) == "light"
    assert theme_mode.current_mode(
        {"account_user_settings": {"settings": {"theme_mode": "auto"}}}
    ) == "auto"
    assert theme_mode.current_mode({}) == "dark"


def test_resolve_is_dark_for_explicit_modes():
    assert theme_mode.resolve_is_dark({theme_mode.RADIO_WIDGET_KEY: "dark"}) is True
    assert theme_mode.resolve_is_dark({theme_mode.RADIO_WIDGET_KEY: "light"}) is False


def test_resolve_is_dark_for_system_mode_uses_probe_then_defaults_dark():
    auto_session = {theme_mode.RADIO_WIDGET_KEY: "auto"}
    assert theme_mode.resolve_is_dark(auto_session) is True  # no probe reading yet
    auto_session[theme_mode.SYSTEM_PREFERS_DARK_KEY] = False
    assert theme_mode.resolve_is_dark(auto_session) is False


def test_with_theme_mode_merges_without_dropping_other_settings():
    updated = theme_mode.with_theme_mode({"settings": {"other_pref": 1}}, mode="light")
    assert updated == {"settings": {"other_pref": 1, "theme_mode": "light"}}


def test_persist_authenticated_theme_mode_requires_auth():
    error = theme_mode.persist_authenticated_theme_mode(config={}, session_state={}, mode="light")
    assert error == "Authentication is required."


def test_set_mode_applies_locally_even_when_signed_out():
    session: dict = {}
    error = theme_mode.set_mode(config={}, session_state=session, mode="light")
    assert error == ""
    assert session[theme_mode.LOCAL_OVERRIDE_KEY] == "light"
