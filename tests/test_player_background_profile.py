"""modules.player_background_profile — the Phase 4 "player background
profile" external-API building block (docs/external-api-contract.md,
GET /v1/external/players/{player_id}/background).

Covers the spec's explicit test list: unknown/mismatched player id, a
traded/released player, sparse weekly history (0/1/a few usable weeks),
a missing denominator (snap_share absent for a week) not crashing and not
being backfilled as 0, an unsupported depth-chart claim (no
depth_chart_position/depth_chart_order at all), and the full "ok" shape
with every documented field present and correctly typed. Contract-timeline
coverage is deliberately simple throughout: it is ALWAYS "unavailable" by
design (no licensed source exists anywhere in this codebase) — these tests
assert that, not that it ever becomes "ok".
"""

from __future__ import annotations

import pandas as pd
import pytest

from modules import nfl_schedule, player_background_profile as pbp


# ---------------------------------------------------------------------------
# Schedule fixture — one team (HOU), 4 regular-season weeks, all with final
# scores, so "weeks the real schedule confirms are over" is unambiguous.
# ---------------------------------------------------------------------------


def _schedule_games() -> pd.DataFrame:
    rows = [
        {"season": 2026, "game_type": "REG", "week": 1, "home_team": "HOU", "away_team": "JAX", "home_score": 24.0, "away_score": 10.0},
        {"season": 2026, "game_type": "REG", "week": 2, "home_team": "KC", "away_team": "HOU", "home_score": 20.0, "away_score": 14.0},
        {"season": 2026, "game_type": "REG", "week": 3, "home_team": "HOU", "away_team": "BUF", "home_score": 27.0, "away_score": 9.0},
        {"season": 2026, "game_type": "REG", "week": 4, "home_team": "DEN", "away_team": "HOU", "home_score": None, "away_score": None},
    ]
    return pd.DataFrame(rows)


@pytest.fixture
def houston_schedule(monkeypatch):
    games = _schedule_games()
    monkeypatch.setattr(nfl_schedule, "load_games", lambda **_: games)
    return games


# ---------------------------------------------------------------------------
# Unknown / mismatched player id
# ---------------------------------------------------------------------------


def test_unknown_player_id_returns_full_unavailable_shape():
    result = pbp.build_player_background_profile("does-not-exist", season=2026, players={})

    assert result["status"] == "unknown_player"
    assert result["player_id"] == "does-not-exist"
    assert result["id_namespace"] == "sleeper"
    assert result["display_name"] is None
    assert result["team"] is None
    assert result["position"] is None
    assert result["schema_version"] == "1.0"

    assert result["contract"]["status"] == "unavailable"
    assert result["contract"]["unavailable_reason"]
    assert result["contract"]["signing_date"] is None
    assert result["contract"]["options"] is None

    team_situation = result["team_situation"]
    assert team_situation["teammates"]["status"] == "unavailable"
    assert team_situation["teammates"]["teammates"] is None
    assert team_situation["depth_chart"]["status"] == "unavailable"
    assert team_situation["recent_workload"]["status"] == "unavailable"

    historical = result["historical_production"]
    assert historical["ppr"]["status"] == "unavailable"
    assert historical["standard_and_box_score"]["status"] == "unavailable"
    assert historical["standard_and_box_score"]["fantasy_points_standard"] is None


def test_mismatched_player_id_not_in_players_dict_is_unknown():
    players = {"4046": {"full_name": "Nico Collins", "team": "HOU", "position": "WR"}}
    result = pbp.build_player_background_profile("9999", season=2026, players=players)
    assert result["status"] == "unknown_player"


# ---------------------------------------------------------------------------
# Traded / released player — team_situation and historical_production still
# report correctly for their real current/former context; contract still
# explicitly unavailable.
# ---------------------------------------------------------------------------


def test_released_player_with_no_current_team_reports_honestly(houston_schedule):
    """A released/retired player has no current `team` on record — teammates
    and depth_chart become correctly "unavailable" (not a guess against a
    team that no longer applies), while historical_production still reports
    real past weekly PPR production from when the player WAS rostered
    (recent_workload doesn't depend on a current team at all).
    """

    players = {"4046": {"full_name": "Former Player", "team": None, "position": "WR"}}
    weekly_stats = {
        "4046": {
            "weekly": [
                {"week": 1, "targets": 5, "receptions": 3, "fantasy_points_ppr": 9.4},
                {"week": 2, "targets": 6, "receptions": 4, "fantasy_points_ppr": 11.1},
            ]
        }
    }

    result = pbp.build_player_background_profile(
        "4046", season=2026, players=players, weekly_stats=weekly_stats
    )

    assert result["status"] == "ok"
    assert result["team"] is None
    assert result["contract"]["status"] == "unavailable"

    team_situation = result["team_situation"]
    assert team_situation["teammates"]["status"] == "unavailable"
    assert "no current NFL team" in team_situation["teammates"]["unavailable_reason"]
    assert team_situation["depth_chart"]["status"] in {"unavailable", "ok"}  # independent of team

    # Real past production is still reported — not suppressed just because
    # the player has since left the roster that produced it.
    recent_workload = team_situation["recent_workload"]
    assert recent_workload["status"] == "ok"
    assert recent_workload["sample_size"] == 2

    historical = result["historical_production"]
    assert historical["ppr"]["status"] == "ok"
    assert historical["ppr"]["sample_size"] == 2
    # No current team means the real completed-week schedule can't be
    # cross-referenced to find "weeks with a final score but no stat line" —
    # correctly None, never guessed against the wrong team's calendar.
    assert historical["ppr"]["schedule_reference_team"] is None
    assert historical["ppr"]["weeks_missing_data"] is None


# ---------------------------------------------------------------------------
# Sparse weekly history: 0, 1, and a few usable weeks.
# ---------------------------------------------------------------------------


def test_zero_usable_weeks_is_honestly_unavailable(houston_schedule):
    players = {"4046": {"full_name": "Rookie Guy", "team": "HOU", "position": "WR"}}
    result = pbp.build_player_background_profile(
        "4046", season=2026, players=players, weekly_stats={"4046": {"weekly": []}}
    )

    recent_workload = result["team_situation"]["recent_workload"]
    assert recent_workload["status"] == "unavailable"
    assert recent_workload["sample_size"] == 0
    assert recent_workload["weeks"] == []

    ppr = result["historical_production"]["ppr"]
    assert ppr["status"] == "unavailable"
    assert ppr["sample_size"] == 0
    assert ppr["weeks"] == []


def test_exactly_one_usable_week_reports_that_single_week(houston_schedule):
    players = {"4046": {"full_name": "Single Week Guy", "team": "HOU", "position": "WR"}}
    weekly_stats = {"4046": {"weekly": [{"week": 1, "targets": 8, "receptions": 6, "fantasy_points_ppr": 14.2}]}}

    result = pbp.build_player_background_profile(
        "4046", season=2026, players=players, weekly_stats=weekly_stats
    )

    recent_workload = result["team_situation"]["recent_workload"]
    assert recent_workload["status"] == "ok"
    assert recent_workload["sample_size"] == 1
    assert recent_workload["weeks"][0]["week"] == 1

    ppr = result["historical_production"]["ppr"]
    assert ppr["status"] == "ok"
    assert ppr["sample_size"] == 1
    assert ppr["weeks"] == [{"week": 1, "fantasy_points_ppr": 14.2}]
    # Weeks 2 and 3 are real, completed HOU games with no stat line for this
    # player — flagged, not silently dropped. Week 4 has no final score yet
    # (home_score/away_score are None in the fixture) so it must NOT appear.
    missing_weeks = {row["week"] for row in ppr["weeks_missing_data"]}
    assert missing_weeks == {2, 3}


def test_a_few_usable_weeks_reports_every_real_week_in_order(houston_schedule):
    players = {"4046": {"full_name": "Steady Guy", "team": "HOU", "position": "WR"}}
    weekly_stats = {
        "4046": {
            "weekly": [
                {"week": 2, "targets": 7, "receptions": 5, "fantasy_points_ppr": 12.0},
                {"week": 1, "targets": 8, "receptions": 6, "fantasy_points_ppr": 14.2},
                {"week": 3, "targets": 9, "receptions": 7, "fantasy_points_ppr": 16.5},
            ]
        }
    }

    result = pbp.build_player_background_profile(
        "4046", season=2026, players=players, weekly_stats=weekly_stats
    )

    ppr = result["historical_production"]["ppr"]
    assert ppr["status"] == "ok"
    assert ppr["sample_size"] == 3
    assert [row["week"] for row in ppr["weeks"]] == [1, 2, 3]
    assert ppr["weeks_missing_data"] == []


# ---------------------------------------------------------------------------
# Missing denominator (snap_share absent for a week) — must not crash, and
# must report null, never 0.
# ---------------------------------------------------------------------------


def test_missing_snap_share_for_a_week_is_null_not_zero(houston_schedule):
    players = {"4046": {"full_name": "Partial Data Guy", "team": "HOU", "position": "WR"}}
    weekly_stats = {
        "4046": {
            "weekly": [
                # No snap_share key at all this week — Sleeper simply never
                # published it (e.g. snap counts not yet in for this game).
                {"week": 1, "targets": 8, "receptions": 6, "fantasy_points_ppr": 14.2},
                {"week": 2, "targets": 5, "receptions": 3, "fantasy_points_ppr": 8.1, "snap_share": 0.74},
            ]
        }
    }

    result = pbp.build_player_background_profile(
        "4046", season=2026, players=players, weekly_stats=weekly_stats
    )

    weeks = result["team_situation"]["recent_workload"]["weeks"]
    week_one = next(row for row in weeks if row["week"] == 1)
    week_two = next(row for row in weeks if row["week"] == 2)
    assert week_one["snap_share"] is None
    assert week_two["snap_share"] == 0.74
    # rush_attempts was never reported either week — opportunities/touches
    # must be null, never silently treated as rush_attempts=0.
    assert week_one["rush_attempts"] is None
    assert week_one["opportunities"] is None
    assert week_one["touches"] is None


def test_missing_rush_attempts_does_not_crash_opportunities_or_touches_math(houston_schedule):
    players = {"4046": {"full_name": "Pass Catcher", "team": "HOU", "position": "WR"}}
    weekly_stats = {
        "4046": {"weekly": [{"week": 1, "targets": 10, "receptions": 8, "fantasy_points_ppr": 20.0}]}
    }

    result = pbp.build_player_background_profile(
        "4046", season=2026, players=players, weekly_stats=weekly_stats
    )
    week = result["team_situation"]["recent_workload"]["weeks"][0]
    assert week["targets"] == 10
    assert week["receptions"] == 8
    assert week["rush_attempts"] is None
    assert week["opportunities"] is None
    assert week["touches"] is None


# ---------------------------------------------------------------------------
# Unsupported depth-chart claim: no depth_chart_position/depth_chart_order
# at all → honestly "unavailable", never fabricated.
# ---------------------------------------------------------------------------


def test_depth_chart_unavailable_when_both_fields_missing():
    players = {"4046": {"full_name": "No Depth Chart Guy", "team": "HOU", "position": "WR"}}
    result = pbp.build_player_background_profile(
        "4046", season=2026, players=players, weekly_stats={"4046": {"weekly": []}}
    )
    depth_chart = result["team_situation"]["depth_chart"]
    assert depth_chart["status"] == "unavailable"
    assert depth_chart["depth_chart_position"] is None
    assert depth_chart["depth_chart_order"] is None
    assert depth_chart["unavailable_reason"]


def test_depth_chart_reports_real_fields_when_present():
    players = {
        "4046": {
            "full_name": "Starter Guy",
            "team": "HOU",
            "position": "WR",
            "depth_chart_position": "WR",
            "depth_chart_order": 1,
        }
    }
    result = pbp.build_player_background_profile(
        "4046", season=2026, players=players, weekly_stats={"4046": {"weekly": []}}
    )
    depth_chart = result["team_situation"]["depth_chart"]
    assert depth_chart["status"] == "ok"
    assert depth_chart["depth_chart_position"] == "WR"
    assert depth_chart["depth_chart_order"] == 1
    assert "not a guarantee" in depth_chart["note"].lower() or "not a guarantee" in depth_chart["note"]


# ---------------------------------------------------------------------------
# Teammates — real NFL roster membership, distinct from "is a starter".
# ---------------------------------------------------------------------------


def test_teammates_lists_same_team_players_and_excludes_self_and_other_teams():
    players = {
        "4046": {"full_name": "Target Player", "team": "HOU", "position": "WR"},
        "5001": {"full_name": "Same Team RB", "team": "HOU", "position": "RB"},
        "6002": {"full_name": "Other Team WR", "team": "KC", "position": "WR"},
    }
    result = pbp.build_player_background_profile(
        "4046", season=2026, players=players, weekly_stats={"4046": {"weekly": []}}
    )
    teammates_section = result["team_situation"]["teammates"]
    assert teammates_section["status"] == "ok"
    teammate_ids = {row["player_id"] for row in teammates_section["teammates"]}
    assert teammate_ids == {"5001"}
    assert "starter" in teammates_section["note"].lower()


# ---------------------------------------------------------------------------
# Full "ok" shape — every documented field present and correctly typed.
# ---------------------------------------------------------------------------


def test_full_ok_shape_has_every_documented_field(houston_schedule):
    players = {
        "4046": {
            "full_name": "Nico Collins",
            "team": "HOU",
            "position": "WR",
            "depth_chart_position": "WR",
            "depth_chart_order": 1,
        },
        "5001": {"full_name": "Same Team RB", "team": "HOU", "position": "RB"},
    }
    weekly_stats = {
        "4046": {
            "weekly": [
                {"week": 1, "targets": 8, "receptions": 6, "rush_attempts": 1, "pass_attempts": 0, "snap_share": 0.81, "fantasy_points_ppr": 14.2},
            ]
        }
    }

    result = pbp.build_player_background_profile(
        "4046", season=2026, players=players, weekly_stats=weekly_stats
    )

    # Top level
    for key in ("player_id", "id_namespace", "display_name", "team", "position", "as_of", "schema_version", "status"):
        assert key in result
    assert result["id_namespace"] == "sleeper"
    assert result["status"] == "ok"
    assert result["schema_version"] == "1.0"

    # Contract — always unavailable, but every field present and typed.
    contract = result["contract"]
    for key in (
        "status", "unavailable_reason", "source", "checked_at", "signing_date", "effective_date",
        "current_contractual_team", "last_contracted_season", "remaining_seasons", "reference_season",
        "reference_date", "current_season_included_in_remaining", "free_agency_year",
        "free_agency_designation", "options", "void_years", "real_contract_years",
        "guaranteed_years", "provenance", "conflict_state",
    ):
        assert key in contract
    assert contract["status"] == "unavailable"

    # Team situation
    team_situation = result["team_situation"]
    teammates = team_situation["teammates"]
    assert teammates["status"] == "ok"
    assert isinstance(teammates["teammates"], list)
    assert teammates["teammates"][0]["player_id"] == "5001"

    depth_chart = team_situation["depth_chart"]
    assert depth_chart["status"] == "ok"
    assert depth_chart["depth_chart_position"] == "WR"
    assert depth_chart["depth_chart_order"] == 1

    recent_workload = team_situation["recent_workload"]
    assert recent_workload["status"] == "ok"
    assert recent_workload["sample_size"] == 1
    week_row = recent_workload["weeks"][0]
    for key in ("week", "targets", "receptions", "rush_attempts", "pass_attempts", "snap_share", "opportunities", "touches"):
        assert key in week_row
    assert week_row["opportunities"] == 9  # rush_attempts(1) + targets(8)
    assert week_row["touches"] == 7  # rush_attempts(1) + receptions(6)

    # Historical production
    historical = result["historical_production"]
    assert historical["status"] == "ok"
    ppr = historical["ppr"]
    assert ppr["status"] == "ok"
    assert ppr["scoring_format"] == "ppr"
    assert ppr["weeks"] == [{"week": 1, "fantasy_points_ppr": 14.2}]

    standard = historical["standard_and_box_score"]
    assert standard["status"] == "unavailable"
    assert standard["unavailable_reason"]
    for key in (
        "fantasy_points_standard", "receiving_yards", "rushing_yards", "passing_yards",
        "receiving_tds", "rushing_tds", "passing_tds",
    ):
        assert standard[key] is None


def test_reads_from_cached_season_player_weekly_when_weekly_stats_not_provided(monkeypatch, houston_schedule):
    """When the caller doesn't pre-fetch weekly_stats (the real single-player
    route's own call path), this module reads straight off
    sleeper.cached_season_player_weekly — never forcing a full season
    rebuild via get_season_player_stats.
    """

    from modules import sleeper

    players = {"4046": {"full_name": "Nico Collins", "team": "HOU", "position": "WR"}}
    fake_weekly = [{"week": 1, "targets": 8, "receptions": 6, "fantasy_points_ppr": 14.2}]

    called = {}

    def fake_cached(player_id, season=None):
        called["player_id"] = player_id
        called["season"] = season
        return fake_weekly

    monkeypatch.setattr(sleeper, "cached_season_player_weekly", fake_cached)
    monkeypatch.setattr(
        sleeper, "get_season_player_stats", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not rebuild"))
    )

    result = pbp.build_player_background_profile("4046", season=2026, players=players)

    assert called == {"player_id": "4046", "season": 2026}
    assert result["historical_production"]["ppr"]["sample_size"] == 1
