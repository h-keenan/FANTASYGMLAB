"""Progressive Trade Hub loading — viewport / interaction contracts (PR #154).

Chromium widths mirror scripts/validate_mobile_ui.py. Progressive loading must
not introduce global CSS or fake recommendation skeletons.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIDTHS = (320, 390, 430, 768, 1024, 1280, 1440, 1600, 1920)


def test_trade_hub_progressive_loading_has_no_fake_skeleton_or_global_css():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    hub = app[
        app.index('if current_page == "trade_hub"') : app.index("# TRADE ANALYZER")
    ]
    assert "LOADING_TRADE_IDEAS" in hub
    assert "Building the trade board" not in hub
    assert "skeleton" not in hub.casefold()
    assert "st.markdown(" not in hub or "unsafe_allow_html" in hub  # degraded ESPN only
    # No new global style injection on the Trade Hub route body.
    assert "inject_global_styles" not in hub
    assert "APP_CSS" not in hub


def test_trade_hub_chrome_before_board_generation():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    hub = app[
        app.index('if current_page == "trade_hub"') : app.index("# TRADE ANALYZER")
    ]
    strategy_idx = hub.index("render_trade_strategy_selector(")
    board_idx = hub.index("get_or_build_presentation_board(")
    assert strategy_idx < board_idx
    assert "trade_hub_strategy_ready" in hub
    assert "trade_hub_rec1_ready" in hub


def test_viewport_width_matrix_documented_for_chromium():
    validate = (ROOT / "scripts" / "validate_mobile_ui.py").read_text(encoding="utf-8")
    assert "WIDTHS = (320, 390, 430, 768, 1024, 1280, 1440, 1600, 1920)" in validate
    for width in WIDTHS:
        assert str(width) in validate


def test_trade_board_visual_harness_covers_progressive_summary_surface():
    harness = (ROOT / "scripts" / "trade_board_visual_harness.py").read_text(
        encoding="utf-8"
    )
    assert "render_trade_idea_card" in harness
    assert "trade_board_visual_fixture" in harness
