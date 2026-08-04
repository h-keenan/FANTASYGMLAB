"""Contracts for executive visual hierarchy (presentation only)."""

from pathlib import Path

from modules.app_styles import APP_CSS
from modules.visual_hierarchy_styles import VISUAL_HIERARCHY_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_visual_hierarchy_css_is_token_backed_and_loaded_late():
    assert "home-command-card-primary" in VISUAL_HIERARCHY_CSS
    assert "home-command-card-secondary" in VISUAL_HIERARCHY_CSS
    assert "st-key-executive_workspace_shell" in VISUAL_HIERARCHY_CSS
    assert "var(--color-opportunity)" in VISUAL_HIERARCHY_CSS
    assert "#" not in VISUAL_HIERARCHY_CSS
    assert "rgba(" not in VISUAL_HIERARCHY_CSS
    assert VISUAL_HIERARCHY_CSS in APP_CSS
    # Hierarchy overrides land after the executive shell base styles.
    assert APP_CSS.rindex("home-command-card-primary") > APP_CSS.index(".dg-executive-shell")


def test_home_command_tiles_mark_primary_and_secondary_weight(monkeypatch):
    from modules import workspace_ui
    import streamlit as st

    calls = []
    monkeypatch.setattr(st, "markdown", lambda html, **k: calls.append(html))
    workspace_ui.render_home_command_tiles(
        [
            {"label": "Need", "value": "QB", "note": "Depth", "tone": "need"},
            {
                "label": "Next Move",
                "value": "Trade up",
                "note": "Primary path",
                "tone": "trade",
                "wide": True,
            },
        ],
        player_scan_card_html=lambda *a, **k: "",
    )
    html = "\n".join(calls)
    assert "home-command-card-primary" in html
    assert "home-command-card-secondary" in html
    assert "home-command-card-wide" in html
    assert html.index("home-command-card-secondary") < html.index("home-command-card-primary")


def test_executive_shell_docs_describe_single_command_bar():
    docs = (ROOT / "docs" / "executive-workspace-shell.md").read_text(encoding="utf-8")
    assert "single executive command bar" in docs
