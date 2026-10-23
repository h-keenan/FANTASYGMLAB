import json
from dataclasses import FrozenInstanceError

import pytest

from modules import player_history, player_quick_view


def season(year, *, points=260.0, ppg=16.0, yards=1100, finish=None, games=17, **extra):
    payload = {
        "stats_season": year,
        "games_played": games,
        "fantasy_points_ppr": points,
        "ppg": ppg,
        "receptions": 80,
        "receiving_yards": yards,
        "receiving_tds": 10,
        "position_finish": finish,
    }
    payload.update(extra)
    return payload


def test_models_are_frozen_and_resume_is_deterministic():
    first = player_history.build_career_resume(
        [season(2024, finish=7), season(2025, finish=3)],
        position="WR",
        current_season=2025,
        source_note="fixture",
    )
    second = player_history.build_career_resume(
        [season(2025, finish=3), season(2024, finish=7)],
        position="WR",
        current_season=2025,
        source_note="fixture",
    )
    assert first == second
    assert [item.season for item in first.seasons] == [2025, 2024]
    with pytest.raises(FrozenInstanceError):
        first.source_note = "changed"


def test_achievement_order_prioritizes_significance_then_recency():
    resume = player_history.build_career_resume(
        [
            season(2025, points=240, ppg=14, yards=1005, finish=15),
            season(2024, points=330, ppg=21, yards=1600, finish=1),
        ],
        position="WR",
        current_season=2025,
        source_note="fixture",
    )
    assert resume.prestige_level == "landmark"
    assert resume.achievements[0].label == "WR1 fantasy finish"
    assert any(item.current_season for item in resume.achievements)
    assert all(item.achievement_id for item in resume.achievements)


def test_cached_loader_uses_existing_files_only_and_orders_position_finish(tmp_path):
    payload = {
        "player-a": season(2024, points=280, finish=None),
        "player-b": season(2024, points=300, finish=None),
        "player-c": season(2024, points=100, finish=None),
    }
    cache = tmp_path / "sleeper_player_stats_2024.json"
    cache.write_text(json.dumps(payload), encoding="utf-8")
    before = cache.read_bytes()
    resume = player_history.load_cached_career_resume(
        player_id="player-a",
        current_row={"player_id": "player-a", "position": "WR", **season(2025, points=250)},
        position_lookup={"player-a": "WR", "player-b": "WR", "player-c": "RB"},
        cache_dir=tmp_path,
    )
    assert cache.read_bytes() == before
    older = next(item for item in resume.seasons if item.season == 2024)
    assert older.position_finish == 2
    assert resume.historical_cache_loaded is True


def test_load_cached_career_resume_rejects_positional_player_id(tmp_path):
    """Regression for production TypeError from keyword-only API mismatch."""

    cache = tmp_path / "sleeper_player_stats_2024.json"
    cache.write_text(json.dumps({"x": season(2024)}), encoding="utf-8")
    with pytest.raises(TypeError, match="positional"):
        player_history.load_cached_career_resume(
            "x",
            current_row={"player_id": "x", "position": "WR", **season(2025)},
            position_lookup={"x": "WR"},
            cache_dir=tmp_path,
        )


def test_te_finish_band_stops_at_top_twelve():
    resume = player_history.build_career_resume(
        [season(2024, finish=14, yards=800, points=160)],
        position="TE",
        current_season=2024,
        source_note="fixture",
    )
    assert not any(item.family == "fantasy-finish" for item in resume.achievements)
    resume_top = player_history.build_career_resume(
        [season(2024, finish=6, yards=900, points=180)],
        position="TE",
        current_season=2024,
        source_note="fixture",
    )
    assert any("TE6" in item.label for item in resume_top.achievements)


def test_executive_snapshot_uses_verified_metadata_without_fabrication():
    snapshot = player_quick_view.build_executive_snapshot(
        {"college": "Verified U"},
        {
            "years_exp": 4,
            "draft_year": 2022,
            "draft_round": 2,
            "draft_slot": 41,
            "height": "74",
            "weight": "208",
        },
    )
    assert snapshot.years_in_league == "4 seasons"
    assert snapshot.draft_capital == "2022 / Round 2 / Pick 41"
    assert snapshot.height == "6'2\""
    assert snapshot.weight == "208 lb"
    assert snapshot.contract_status == ""
