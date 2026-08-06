from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import app
from modules import draft_assistant, live_draft
from modules.player_eligibility import (
    eligibility_diagnostics,
    filter_current_fantasy_players,
    player_eligibility,
)


NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)
RECENT_NEWS_MS = int(NOW.timestamp() * 1000)


def _player(
    player_id: str,
    name: str,
    *,
    active=True,
    status="Active",
    team="KC",
    position="QB",
    years_exp=5,
    news_updated=RECENT_NEWS_MS,
    fantasycalc_value=4000,
    value_score=4000,
    age=28,
):
    return {
        "player_id": player_id,
        "name": name,
        "full_name": name,
        "sport": "nfl",
        "active": active,
        "status": status,
        "team": team,
        "position": position,
        "fantasy_positions": [position],
        "years_exp": years_exp,
        "news_updated": news_updated,
        "depth_chart_order": 0,
        "depth_chart_position": "",
        "stats_season": None,
        "fantasycalc_value": fantasycalc_value,
        "value": value_score,
        "market_score": value_score,
        "dynasty_score": value_score,
        "value_score": value_score,
        "rebuild_score": value_score,
        "scarcity_score": 0,
        "role_score": value_score,
        "opportunity_score": value_score,
        "age": age,
        "injury_status": "",
        "injury_level": "healthy",
        "risk_multiplier": 1.0,
        "opportunity_label": "Starter",
    }


def _stale_roethlisberger_record():
    return _player(
        "138",
        "Ben Roethlisberger",
        active=True,
        status="Active",
        team="PIT",
        position="QB",
        years_exp=18,
        news_updated=1643296817250,
        fantasycalc_value=0,
        value_score=9999,
        age=39,
    )


def _decision_pool():
    return pd.DataFrame(
        [
            _stale_roethlisberger_record(),
            _player("current-1", "Current Veteran", value_score=5000),
            _player(
                "rookie-1",
                "Unsigned Rookie",
                status="",
                team="",
                position="WR",
                years_exp=0,
                news_updated=None,
                fantasycalc_value=0,
                value_score=4500,
                age=21,
            ),
        ]
    )


def test_stale_active_source_record_is_not_currently_eligible():
    result = player_eligibility(_stale_roethlisberger_record(), now=NOW)

    assert result == {
        "eligible": False,
        "reason": "missing_current_player_corroboration",
        "current_signal": False,
    }


def test_explicit_retired_and_inactive_players_are_excluded():
    players = pd.DataFrame(
        [
            _player("retired", "Retired Player", status="Retired"),
            _player("inactive", "Inactive Player", active=False, status="Active"),
            _player("current", "Current Player"),
        ]
    )

    filtered = filter_current_fantasy_players(players, now=NOW)

    assert filtered["player_id"].tolist() == ["current"]


def test_active_free_agent_and_unsigned_rookie_remain_eligible():
    players = pd.DataFrame(
        [
            _player("fa", "Current Free Agent", status="Free Agent", team="FA"),
            _player(
                "rookie",
                "Unsigned Rookie",
                status="",
                team="",
                position="WR",
                years_exp=0,
                news_updated=None,
                fantasycalc_value=0,
            ),
        ]
    )

    filtered = filter_current_fantasy_players(players, now=NOW)

    assert filtered["player_id"].tolist() == ["fa", "rookie"]
    assert eligibility_diagnostics(filtered)["retained_current_free_agents"] == 2


def test_missing_status_is_not_assumed_active_without_current_signal():
    player = _player(
        "unknown",
        "Uncorroborated Player",
        status="",
        news_updated=None,
        fantasycalc_value=0,
        years_exp=6,
        value_score=10000,
    )

    assert player_eligibility(player, now=NOW)["eligible"] is False


def test_stale_value_score_cannot_override_inactive_status():
    player = _player(
        "stale-value",
        "Stale High Value",
        status="Inactive",
        fantasycalc_value=9999,
        value_score=9999,
    )

    assert player_eligibility(player, now=NOW)["eligible"] is False


def test_live_draft_filters_before_ranking_labels():
    pool = live_draft.available_player_pool(
        _decision_pool(),
        picks=[],
        score_field="dynasty_score",
    )
    rankings = live_draft.build_live_draft_rankings(
        pool,
        roster_df=pd.DataFrame(),
        league_settings={"league_format": "Dynasty", "qb_format": "1QB"},
        score_field="dynasty_score",
    )

    assert rankings["player_id"].tolist() == ["current-1", "rookie-1"]
    assert "Best Available" in rankings["recommendation_label"].tolist()
    assert "138" not in rankings["player_id"].astype(str).tolist()


def test_startup_draft_center_excludes_ineligible_player():
    board = app.build_startup_draft_board(
        _decision_pool(),
        score_field="dynasty_score",
        strategy_label="Balanced",
        current_round=1,
        league_settings={"qb_format": "1QB", "te_premium": False},
        excluded_player_ids=set(),
    )

    assert board["player_id"].tolist() == ["current-1", "rookie-1"]


def test_draft_assistant_filters_every_path_and_recommendation_bucket():
    source = _decision_pool()
    long_draft_pool = draft_assistant.apply_draft_pool_filter(
        source,
        {"draft_rounds": 20},
    )
    available = draft_assistant.build_available_player_pool(
        source,
        drafted_player_ids=[],
        score_field="dynasty_score",
    )
    recommendations = draft_assistant.build_recommendation_buckets(
        source,
        score_field="dynasty_score",
    )

    assert long_draft_pool["player_id"].tolist() == ["current-1", "rookie-1"]
    assert available["player_id"].tolist() == ["current-1", "rookie-1"]
    assert all(str(item.get("player_id")) != "138" for item in recommendations)


def test_waiver_and_dashboard_free_agent_entry_points_use_canonical_filter():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert 'surface="waiver_free_agents"' in app_source
    assert 'surface="dashboard_free_agents"' in app_source
    filtered = filter_current_fantasy_players(
        _decision_pool(),
        surface="waiver_free_agents",
        now=NOW,
    )
    assert "138" not in filtered["player_id"].astype(str).tolist()


def test_veteran_unsigned_news_only_is_not_eligible():
    player = _player(
        "536",
        "Veteran Unsigned News Only",
        team="",
        years_exp=12,
        news_updated=RECENT_NEWS_MS,
        fantasycalc_value=0,
        age=37,
    )

    result = player_eligibility(player, now=NOW)

    assert result["eligible"] is False
    assert result["reason"] == "missing_current_player_corroboration"


def test_veteran_unsigned_with_market_value_remains_eligible():
    player = _player(
        "fa-vet",
        "Veteran Free Agent",
        team="FA",
        years_exp=12,
        news_updated=RECENT_NEWS_MS,
        fantasycalc_value=1200,
        age=34,
    )

    assert player_eligibility(player, now=NOW)["eligible"] is True


def test_antonia_brown_sleeper_fixture_is_not_waiver_eligible():
    import json
    from pathlib import Path

    sleeper = json.loads(Path("data/sleeper_players.json").read_text(encoding="utf-8"))
    ab = sleeper.get("536")
    assert ab is not None
    result = player_eligibility(ab, now=NOW)
    assert result["eligible"] is False
    filtered = filter_current_fantasy_players(
        pd.DataFrame([ab]),
        surface="waiver_free_agents",
        now=NOW,
    )
    assert filtered.empty


def test_existing_order_among_eligible_players_is_unchanged():
    players = pd.DataFrame(
        [
            _player("a", "A", value_score=100),
            _stale_roethlisberger_record(),
            _player("b", "B", value_score=300),
            _player("c", "C", value_score=200),
        ]
    )

    filtered = filter_current_fantasy_players(players, now=NOW)

    assert filtered["player_id"].tolist() == ["a", "b", "c"]


def test_no_player_name_is_hardcoded_in_eligibility_implementation():
    implementation = Path("modules/player_eligibility.py").read_text(encoding="utf-8").casefold()

    assert "roethlisberger" not in implementation
    assert "ben " not in implementation


def test_surface_wiring_covers_all_active_decision_pools():
    app_source = Path("app.py").read_text(encoding="utf-8")
    live_source = Path("modules/live_draft.py").read_text(encoding="utf-8")
    assistant_source = Path("modules/draft_assistant.py").read_text(encoding="utf-8")

    for surface in (
        "startup_draft_center",
        "startup_manual_exclusions",
        "startup_best_available",
        "waiver_free_agents",
        "dashboard_free_agents",
    ):
        assert f'surface="{surface}"' in app_source
    assert 'surface="live_draft_available_pool"' in live_source
    assert 'surface="live_draft_rankings"' in live_source
    assert 'surface="draft_assistant_available_pool"' in assistant_source
    assert 'surface="draft_assistant_recommendations"' in assistant_source
