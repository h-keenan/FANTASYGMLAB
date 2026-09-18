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
        logo_html="<div class='dg-ranked-logo'>WR</div>",
        top_three=True,
        is_current=True,
    )
    assert "dg-ranked-row" in html
    assert "dg-ranked-row--current" in html
    assert "dg-ranked-row--top" in html
    assert html.index("dg-ranked-rank") < html.index("dg-ranked-team")
    assert html.index("dg-ranked-team") < html.index("dg-ranked-metric")
    assert html.index("dg-ranked-metric") < html.index("dg-ranked-interp")
    assert "Starter score" in html
    assert "12,400" in html


def _ranked_row(rank: int) -> str:
    return league_workspace_ui.ranked_leaderboard_row_html(
        rank_label=f"#{rank}",
        team_name=f"Team {rank}",
        owner_text="@manager",
        primary_metric="10-3",
        metric_label="Record",
        logo_html="<div class='dg-ranked-logo'>T</div>",
        top_three=rank <= 3,
        first_place=rank == 1,
    )


def test_rank_one_gets_the_gold_leader_treatment_and_ranks_two_three_do_not():
    from modules.app_styles import APP_CSS
    from modules.dense_list_styles import DENSE_LIST_CSS

    first = _ranked_row(1)
    assert "dg-ranked-row--first" in first
    # Layered on the shared top-three border, not a replacement for it.
    assert "dg-ranked-row--top" in first

    for rank in (2, 3, 4):
        row = _ranked_row(rank)
        assert "dg-ranked-row--first" not in row, rank
        assert ("dg-ranked-row--top" in row) is (rank <= 3), rank

    # Gold comes from the existing premium token — no new hex, and distinct
    # from the neutral accent every top-three row shares.
    assert ".dg-ranked-row.dg-ranked-row--first," in DENSE_LIST_CSS
    leader_rule = DENSE_LIST_CSS.split(".dg-ranked-row.dg-ranked-row--first,")[1].split(
        "{", 1
    )[1].split("}")[0]
    assert "var(--color-premium)" in leader_rule
    assert "#" not in leader_rule
    assert "var(--border-accent)" not in leader_rule
    assert ".dg-ranked-row--first" in APP_CSS


def test_standings_board_flags_only_the_first_place_row():
    frame = pd.DataFrame(
        [
            {
                "roster_id": "1",
                "team_name": "Leader",
                "owner_name": "Owner A",
                "standing_rank": 1,
                "wins": 10,
                "losses": 3,
                "ties": 0,
            },
            {
                "roster_id": "2",
                "team_name": "Runner Up",
                "owner_name": "Owner B",
                "standing_rank": 2,
                "wins": 9,
                "losses": 4,
                "ties": 0,
            },
            {
                "roster_id": "3",
                "team_name": "Third",
                "owner_name": "Owner C",
                "standing_rank": 3,
                "wins": 8,
                "losses": 5,
                "ties": 0,
            },
        ]
    )
    rows = [
        league_workspace_ui.ranked_leaderboard_row_html(
            rank_label=f"#{int(row['standing_rank'])}",
            team_name=str(row["team_name"]),
            owner_text=str(row["owner_name"]),
            primary_metric=f"{int(row['wins'])}-{int(row['losses'])}",
            metric_label="Record",
            logo_html="",
            top_three=bool(row["standing_rank"] <= 3),
            first_place=bool(row["standing_rank"] == 1),
        )
        for _, row in frame.iterrows()
    ]
    assert sum("dg-ranked-row--first" in row for row in rows) == 1
    assert "dg-ranked-row--first" in rows[0]
    assert all("dg-ranked-row--top" in row for row in rows)


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
        team_logo_html=lambda *_a, **_k: "<div class='dg-ranked-logo'>T</div>",
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
        "modules/age_model.py",
        "modules/news_factor.py",
    ):
        assert not (ROOT / relative).exists(), relative


def test_cleanup_doc_exists():
    doc = ROOT / "docs" / "league-leaderboards-and-repo-cleanup.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "ranked_leaderboard_row_html" in text
    assert "Dead-code audit" in text or "dead-code" in text.casefold()
