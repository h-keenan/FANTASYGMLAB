"""League standings board — presentation of Sleeper roster settings only."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import league_standings
from modules import league_workspace_ui


ROOT = Path(__file__).resolve().parents[1]


def _roster(
    roster_id: str,
    *,
    wins: int,
    losses: int,
    ties: int = 0,
    fpts: int = 0,
    fpts_decimal: int = 0,
    fpts_against: int = 0,
    fpts_against_decimal: int = 0,
    division: int | None = None,
) -> dict:
    settings = {
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "fpts": fpts,
        "fpts_decimal": fpts_decimal,
        "fpts_against": fpts_against,
        "fpts_against_decimal": fpts_against_decimal,
    }
    if division is not None:
        settings["division"] = division
    return {"roster_id": roster_id, "settings": settings}


def test_standings_sort_uses_wins_then_points_for_without_rank_zero():
    bundle = league_standings.build_league_standings_bundle(
        rosters=[
            _roster("a", wins=5, losses=5, fpts=1000),
            _roster("b", wins=8, losses=2, fpts=900),
            _roster("c", wins=5, losses=5, fpts=1100),
            _roster("d", wins=8, losses=2, fpts=950),
        ],
        roster_profiles={
            "a": {"team_name": "Alpha"},
            "b": {"team_name": "Bravo"},
            "c": {"team_name": "Charlie"},
            "d": {"team_name": "Delta"},
        },
        league={"season": "2026", "settings": {"leg": 10, "playoff_teams": 2}},
    )
    assert bundle["available"] is True
    frame = bundle["frame"]
    assert frame["standing_rank"].tolist() == [1, 2, 3, 4]
    assert 0 not in set(frame["standing_rank"])
    assert frame["roster_id"].tolist() == ["d", "b", "c", "a"]
    assert frame.iloc[0]["playoff_status"] == "Playoff seed #1"
    assert frame.iloc[1]["playoff_status"] == "Playoff seed #2"
    assert frame.iloc[2]["playoff_status"] == "On the bubble"
    assert frame.iloc[3]["playoff_status"] == "Outside playoff line"
    assert bool(frame.iloc[1]["on_playoff_line"]) is True


def test_ties_appear_in_record_and_win_percentage():
    bundle = league_standings.build_league_standings_bundle(
        rosters=[_roster("t", wins=3, losses=3, ties=2, fpts=800)],
        roster_profiles={"t": {"team_name": "Tied"}},
        league={"settings": {"leg": 8}},
    )
    row = bundle["frame"].iloc[0]
    assert row["record_label"] == "3-3-2"
    assert abs(float(row["win_pct"]) - (4 / 8)) < 1e-9
    assert row["win_pct_label"] == "50.0%"


def test_offseason_empty_state_when_no_games():
    bundle = league_standings.build_league_standings_bundle(
        rosters=[_roster("a", wins=0, losses=0, fpts=0)],
        roster_profiles={"a": {"team_name": "Idle"}},
        league={"season": "2026", "settings": {"leg": 0}},
    )
    assert bundle["available"] is False
    assert bundle["empty_reason"] == "offseason"
    assert "regular-season results" in bundle["message"]


def test_missing_manager_and_avatar_still_rank():
    bundle = league_standings.build_league_standings_bundle(
        rosters=[_roster("x", wins=1, losses=0, fpts=100)],
        roster_profiles={},
        league={"settings": {"leg": 1}},
    )
    row = bundle["frame"].iloc[0]
    assert row["standing_rank"] == 1
    assert row["team_name"] == "Team"
    assert row["owner_name"] == "Manager"
    assert row["avatar_url"] == ""


def test_division_groups_without_empty_chrome_when_absent():
    with_div = league_standings.build_league_standings_bundle(
        rosters=[
            _roster("e1", wins=2, losses=0, fpts=200, division=1),
            _roster("e2", wins=1, losses=1, fpts=180, division=1),
            _roster("w1", wins=3, losses=0, fpts=220, division=2),
        ],
        roster_profiles={
            "e1": {"team_name": "East One"},
            "e2": {"team_name": "East Two"},
            "w1": {"team_name": "West One"},
        },
        league={
            "settings": {"leg": 3, "playoff_teams": 2},
            "metadata": {"division_1": "East", "division_2": "West"},
        },
    )
    assert with_div["has_divisions"] is True
    assert [group["label"] for group in with_div["groups"]] == ["East", "West"]
    assert with_div["groups"][0]["frame"]["roster_id"].tolist() == ["e1", "e2"]

    no_div = league_standings.build_league_standings_bundle(
        rosters=[_roster("a", wins=1, losses=0, fpts=100)],
        roster_profiles={"a": {"team_name": "Solo"}},
        league={"settings": {"leg": 1}},
    )
    assert no_div["has_divisions"] is False
    assert len(no_div["groups"]) == 1
    assert no_div["groups"][0]["label"] == ""


def test_odd_and_common_league_sizes_have_unique_ranks():
    for size in (8, 10, 12, 14, 11, 9):
        rosters = [
            _roster(str(i), wins=size - i, losses=i - 1, fpts=1000 - i)
            for i in range(1, size + 1)
        ]
        profiles = {str(i): {"team_name": f"Team {i}"} for i in range(1, size + 1)}
        bundle = league_standings.build_league_standings_bundle(
            rosters=rosters,
            roster_profiles=profiles,
            league={"settings": {"leg": size, "playoff_teams": 6}},
        )
        ranks = bundle["frame"]["standing_rank"].tolist()
        assert ranks == list(range(1, size + 1))
        assert len(set(bundle["frame"]["roster_id"])) == size


def test_standings_board_reuses_ranked_row_and_current_accent():
    bundle = league_standings.build_league_standings_bundle(
        rosters=[
            _roster("mine", wins=6, losses=2, fpts=900),
            _roster("theirs", wins=7, losses=1, fpts=950),
        ],
        roster_profiles={
            "mine": {"team_name": "Mine", "owner_username": "me"},
            "theirs": {"team_name": "Theirs", "owner_username": "them"},
        },
        league={"settings": {"leg": 8, "playoff_teams": 1}},
    )
    captured = {}

    def _capture(*, html: str, key_prefix: str):
        captured["html"] = html
        return None

    league_workspace_ui.render_standings_board(
        bundle,
        team_tap_markup=lambda row: (
            " team-card-tappable",
            f" data-roster-id='{row.get('roster_id')}'",
        ),
        render_team_card_tap_grid=_capture,
        open_league_team_from_tap=lambda _clicked: False,
        team_logo_html=lambda *_a, **_k: "<div class='dg-ranked-logo'>T</div>",
        current_roster_id="mine",
    )
    html = captured["html"]
    assert "dg-ranked-board--standings" in html
    assert "dg-ranked-row--current" in html
    assert "dg-standings-playoff-line" in html
    assert "7-1" in html
    assert "Record" in html
    assert html.index("Theirs") < html.index("Mine")


def test_league_overview_places_standings_before_power_rankings():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    rankings = source[source.index('if league_section == "Rankings":') :]
    standings_index = rankings.index("render_league_standings_board(")
    power_index = rankings.index("render_power_rankings_board(")
    assert standings_index < power_index
    assert "Standings = actual results" in rankings[:5000]


def test_standings_contract_doc_exists():
    doc = ROOT / "docs" / "league-standings-board-contract.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    for marker in (
        "Data source",
        "Playoff-line behavior",
        "Division handling",
        "Relationship to Power Rankings",
        "Performance impact",
        "Limitations",
    ):
        assert marker in text


def test_points_combine_sleeper_decimal_fields():
    assert league_standings.sleeper_points_total(
        {"fpts": 1617, "fpts_decimal": 78}
    ) == 1617.78
    assert league_standings.sleeper_points_total(
        {"fpts_against": 1670, "fpts_against_decimal": 32},
        against=True,
    ) == 1670.32
