"""GM Orb viewport anchoring + #244 scope regression (UI consistency polish)."""

from __future__ import annotations

import re
from pathlib import Path

from modules.app_styles import APP_CSS
from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS


ROOT = Path(__file__).resolve().parents[1]
SCOPED = (
    'stVerticalBlock"]:has(> div[data-testid="stElementContainer"] '
    ".mobile-gm-floating-trigger-marker)"
)
UNSCOPED = 'stVerticalBlock"]:has(.mobile-gm-floating-trigger-marker)'


def test_orb_overlay_keeps_narrow_has_scope():
    assert SCOPED in MOBILE_INTERACTION_OVERLAY_CSS
    assert SCOPED in APP_CSS
    assert UNSCOPED not in MOBILE_INTERACTION_OVERLAY_CSS
    assert UNSCOPED not in APP_CSS
    # No broad unscoped :has that can match the root Streamlit block.
    assert re.search(
        r'stVerticalBlock"\]:has\(\.mobile-gm-floating-trigger-marker\)',
        APP_CSS,
    ) is None


def test_orb_neutralizes_streamlit_flex_gap_offset():
    """Streamlit stVerticalBlock defaults to flex + 1rem gap, which pushed the
    button 16px below the fixed 44×44 box and clipped it past the viewport."""

    compact = MOBILE_INTERACTION_OVERLAY_CSS.replace(" ", "")
    assert "gap:0!important" in compact
    assert "row-gap:0!important" in compact
    assert "display:block!important" in compact
    assert (
        'stElementContainer"]:has([data-testid="stButton"])'
        in MOBILE_INTERACTION_OVERLAY_CSS
    )
    assert "position: absolute !important" in MOBILE_INTERACTION_OVERLAY_CSS
    assert "transform: none !important" in MOBILE_INTERACTION_OVERLAY_CSS


def test_orb_desktop_hover_does_not_translate_out_of_viewport():
    desktop = (
        ROOT / "modules" / "desktop_executive_layout_styles.py"
    ).read_text(encoding="utf-8")
    assert "mobile_gm_sheet_trigger_" in desktop
    hover_block = desktop.split(
        'mobile-gm-floating-trigger-marker) [data-testid="stButton"] button:hover',
        1,
    )
    assert len(hover_block) == 2
    rule_body = hover_block[1].split("}", 1)[0]
    # Ignore comments; require an explicit transform:none declaration.
    code = "\n".join(
        line for line in rule_body.splitlines() if "/*" not in line and "*/" not in line
    )
    assert "translateY(" not in code
    assert "transform: none" in code


def test_presentation_polish_does_not_touch_football_or_cache_modules():
    """Hard scope: this pass is CSS / presentation keys only."""

    changed_markers = (
        "Game Plan package",
        "cache fingerprint",
        "provider call",
    )
    overlay = MOBILE_INTERACTION_OVERLAY_CSS.lower()
    for marker in changed_markers:
        assert marker.lower() not in overlay
