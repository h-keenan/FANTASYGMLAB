"""Dashboard Game Plan schema guard after #219 lightweight intelligence (#220)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from modules import game_plan_package
from modules import shell_chrome_schema


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
DOC = (ROOT / "docs" / "game-plan-package-memo.md").read_text(encoding="utf-8")


def test_legacy_intelligence_row_lookup_raises_without_roster_id():
    """Exact production crash shape from #219 lightweight Game Plan context."""

    df_intel = pd.DataFrame()  # empty / RangeIndex-only — no roster_id column
    with pytest.raises(KeyError, match="roster_id"):
        shell_chrome_schema.legacy_intelligence_row_lookup(df_intel, 7)


def test_select_roster_row_safe_on_lightweight_intelligence_frames():
    empty = pd.DataFrame()
    assert shell_chrome_schema.select_roster_row(empty, 7) == {}

    range_only = pd.DataFrame(index=range(3))
    assert "roster_id" not in range_only.columns
    assert shell_chrome_schema.select_roster_row(range_only, 7) == {}

    partial = pd.DataFrame({"team_name": ["A"], "power_rank": [1]})
    assert shell_chrome_schema.select_roster_row(partial, 7) == {}


def test_select_roster_row_matches_full_intelligence_schema():
    frame = pd.DataFrame(
        {
            "roster_id": [7, 9],
            "team_name": ["Mine", "Theirs"],
            "key_injuries_summary": ["QB IR", ""],
            "archetype_label": ["Contender", "Rebuild"],
        }
    )
    row = shell_chrome_schema.select_roster_row(frame, "7")
    assert row["roster_id"] == 7
    assert row["key_injuries_summary"] == "QB IR"
    assert shell_chrome_schema.select_roster_row(frame, 99) == {}


def test_dashboard_game_plan_uses_safe_intel_row_selector():
    dash = APP.split("def render_home_dashboard(", 1)[1].split(
        "STARTUP_DRAFT_STRATEGIES", 1
    )[0]
    assert "shell_chrome_schema.select_roster_row(df_intel" in dash
    assert "shell_chrome_schema.select_roster_row(df_display" in dash
    # Must not keep the hard KeyError pattern on df_intel inside Dashboard.
    assert 'df_intel[df_intel["roster_id"]' not in dash


def test_game_plan_path_keeps_intelligence_disabled():
    assert game_plan_package.GAME_PLAN_CONTEXT_FLAGS[0] is False
    assert "include_intelligence=flags[0]" in APP
    assert "GAME_PLAN_CONTEXT_FLAGS" in APP
    # Critical path must not flip intelligence back on for Game Plan loader.
    loader = APP.split("def _load_game_plan_league_context()", 1)[1].split(
        "render_home_dashboard(", 1
    )[0]
    assert "include_intelligence=flags[0]" in loader
    assert "include_intelligence=True" not in loader


def test_docs_cover_lightweight_intelligence_contract():
    assert "lightweight" in DOC.casefold()
    assert "roster_id" in DOC
    assert "select_roster_row" in DOC or "schema guard" in DOC.casefold()


def test_package_hit_path_does_not_index_intel_roster_id():
    hit = APP.split("game_plan_package_hit", 1)[1].split("else:", 1)[0]
    assert 'df_intel["roster_id"]' not in hit
    assert "cached_dashboard_trade_headline(" not in hit
