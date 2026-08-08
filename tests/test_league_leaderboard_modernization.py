"""League leaderboard presentation modernization — structure only, no ranking math."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import league_workspace_ui


ROOT = Path(__file__).resolve().parents[1]


def test_ranked_row_hierarchy_and_current_team_accent():
    html = league_workspace_ui.ranked_leaderboard_row_html(
        rank_label="#1",
        team_name="War Room",
        owner_text="@founder",
        primary_metric="12,400",
        metric_label="Starter-Weighted Score",
        interpretation="Compete · Flexible contender",
        secondary="Power #1 · Franchise #2",
        logo_html="<div class='power-logo-wrap'>WR</div>",
        top_three=True,
        is_current=True,
    )
    assert "dg-ranked-row" in html
    assert "dg-ranked-row--current" in html
    assert "dg-ranked-row--top" in html
    assert html.index("dg-ranked-rank") < html.index("dg-ranked-team")
    assert html.index("dg-ranked-team") < html.index("dg-ranked-metric")
    assert html.index("dg-ranked-metric") < html.index("dg-ranked-interp")
    assert "12,400" in html
    assert "Starter-Weighted Score" in html


def test_power_board_marks_current_roster_and_shows_primary_metric():
    frame = pd.DataFrame(
        [
            {
                "roster_id": "mine",
                "team_name": "Mine",
                "owner_username": "me",
                "owner_name": "Me",
                "avatar_url": "",
                "power_rank": 2,
                "power_score": 9900,
                "franchise_rank": 1,
                "starter_rank": 2,
                "bench_rank": 2,
                "draft_capital_rank": 3,
                "strategy_display": "Compete",
                "archetype_label": "Contender",
                "mode": "competitive",
                "injured_starters": 0,
            },
            {
                "roster_id": "theirs",
                "team_name": "Theirs",
                "owner_username": "them",
                "owner_name": "Them",
                "avatar_url": "",
                "power_rank": 1,
                "power_score": 11000,
                "franchise_rank": 2,
                "starter_rank": 1,
                "bench_rank": 1,
                "draft_capital_rank": 1,
                "strategy_display": "Reboot",
                "archetype_label": "Rebuilder",
                "mode": "rebuild",
                "injured_starters": 0,
            },
        ]
    )
    captured = {}

    def _capture(*, html: str, key_prefix: str):
        captured["html"] = html
        return None

    league_workspace_ui.render_power_rankings_board(
        frame,
        "Starter-Weighted Score",
        has_meaningful_team_injury_impact=lambda _row: False,
        team_injury_display_label=lambda _row: "",
        team_tap_markup=lambda row: ("", ""),
        render_team_card_tap_grid=_capture,
        open_league_team_from_tap=lambda _clicked: False,
        team_logo_html=lambda *_a, **_k: "<div class='power-logo-wrap'>T</div>",
        current_roster_id="mine",
    )
    html = captured["html"]
    assert "dg-ranked-board" in html
    assert "dg-ranked-row--current" in html
    assert "11,000" in html
    assert "9,900" in html
    assert "power-track" not in html
    assert html.index("Theirs") < html.index("Mine")  # rank order preserved


def test_dead_modules_removed():
    for relative in (
        "modules/app_header.py",
        "modules/executive_visual_finalization_styles.py",
        "modules/executive_info_compression_styles.py",
    ):
        assert not (ROOT / relative).exists(), relative


def test_cleanup_doc_exists():
    doc = ROOT / "docs" / "league-leaderboards-and-repo-cleanup.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "ranked_leaderboard_row_html" in text
    assert "Dead-code audit" in text or "dead-code" in text.casefold()
