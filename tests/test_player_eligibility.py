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


def _pre_annotated(rows: list[dict]) -> pd.DataFrame:
    """A players frame that already carries the trust/annotation columns —
    exercises filter_current_fantasy_players' own DEF/league filtering in
    isolation from annotate_player_eligibility's separate current-player
    heuristics (which a synthetic DEF/team-defense fixture row doesn't
    realistically satisfy and isn't what this is testing)."""
    frame = pd.DataFrame(rows)
    frame["is_current_fantasy_eligible"] = True
    frame["player_eligibility_reason"] = "test"
    frame["trust_enforcement"] = "test"
    frame["trust_evidence_confidence"] = "test"
    frame["trust_block_reason"] = ""
    frame["trust_validation_fingerprint"] = "test"
    return frame


def test_def_players_are_dropped_for_a_league_with_no_def_roster_slot():
    players = _pre_annotated(
        [
            {"player_id": "kc-def", "position": "DEF"},
            {"player_id": "current", "position": "RB"},
        ]
    )
    league = {"roster_positions": ["QB", "RB", "WR", "TE", "FLEX", "BN"]}

    filtered = filter_current_fantasy_players(players, league=league)

    assert filtered["player_id"].tolist() == ["current"]


def test_def_players_are_kept_for_a_league_with_a_def_roster_slot():
    players = _pre_annotated(
        [
            {"player_id": "kc-def", "position": "DEF"},
            {"player_id": "current", "position": "RB"},
        ]
    )
    league = {"roster_positions": ["QB", "RB", "WR", "TE", "DEF", "FLEX", "BN"]}

    filtered = filter_current_fantasy_players(players, league=league)

    assert set(filtered["player_id"].tolist()) == {"kc-def", "current"}


def test_def_players_are_kept_when_no_league_is_passed_at_all():
    # Default (no `league` kwarg) must keep every existing caller's exact
    # current behavior — this is opt-in per call site, never a blanket change.
    players = _pre_annotated(
        [
            {"player_id": "kc-def", "position": "DEF"},
            {"player_id": "current", "position": "RB"},
        ]
    )

    filtered = filter_current_fantasy_players(players)

    assert set(filtered["player_id"].tolist()) == {"kc-def", "current"}


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


def test_active_unsigned_veteran_with_current_structured_news_is_eligible():
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

    assert result["eligible"] is True
    assert result["reason"] == "corroborated_current_player"


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
        "prepared_player_frame",
        "trade_search_pool",
    ):
        assert f'surface="{surface}"' in app_source
    explorer_source = Path("modules/player_asset_explorer_ui.py").read_text(encoding="utf-8")
    assert "is_current_fantasy_eligible" in explorer_source
    assert 'surface="live_draft_available_pool"' in live_source
    assert 'surface="live_draft_rankings"' in live_source
    assert 'surface="draft_assistant_available_pool"' in assistant_source
    assert 'surface="draft_assistant_recommendations"' in assistant_source


def test_sleeper_fixture_retired_veteran_is_not_a_current_asset():
    import json

    from modules.player_eligibility import is_current_fantasy_asset
    from modules.player_asset_explorer_ui import ranked_player_frame

    sleeper = json.loads(Path("data/sleeper_players.json").read_text(encoding="utf-8"))
    record = sleeper["138"]
    assert is_current_fantasy_asset(record, now=NOW) is False
    frame = filter_current_fantasy_players(
        pd.DataFrame(
            [
                {
                    **_stale_roethlisberger_record(),
                    "fantasycalc_value": 8000,
                    "value_score": 8000,
                },
                _player("current-1", "Current Veteran", value_score=5000),
            ]
        ),
        now=NOW,
        surface="player_asset_explorer",
    )
    visible = ranked_player_frame(frame, "value_score")
    assert "138" not in visible["player_id"].astype(str).tolist()
    assert visible["player_id"].tolist() == ["current-1"]


def test_injured_reserve_and_active_free_agent_stay_eligible():
    ir = _player(
        "ir-1",
        "Injured Starter",
        status="Injured Reserve",
        team="KC",
        years_exp=11,
        age=32,
    )
    ir["injury_status"] = "IR"
    fa = _player(
        "fa-young",
        "Cut Veteran",
        status="Free Agent",
        team="FA",
        years_exp=6,
        age=28,
        news_updated=RECENT_NEWS_MS,
        fantasycalc_value=900,
    )
    incomplete = _player(
        "unknown-meta",
        "Incomplete Record",
        status="",
        team="",
        news_updated=None,
        fantasycalc_value=0,
        years_exp=4,
        age=26,
    )
    assert player_eligibility(ir, now=NOW)["eligible"] is True
    assert player_eligibility(fa, now=NOW)["eligible"] is True
    assert player_eligibility(incomplete, now=NOW)["eligible"] is False


def test_filter_reuses_existing_eligibility_flag_without_reannotation():
    from unittest.mock import patch

    annotated = filter_current_fantasy_players(_decision_pool(), now=NOW)
    assert "138" not in annotated["player_id"].astype(str).tolist()
    with patch(
        "modules.player_eligibility.player_eligibility",
        side_effect=AssertionError("eligibility must not re-run on annotated frames"),
    ):
        reused = filter_current_fantasy_players(
            annotated,
            now=NOW,
            surface="waiver_free_agents",
        )
    assert reused["player_id"].tolist() == annotated["player_id"].tolist()


def test_practice_squad_and_pup_are_not_treated_as_retired():
    pup = _player("pup-1", "PUP Veteran", status="PUP", years_exp=8, age=29)
    pup["injury_status"] = "PUP"
    practice = _player(
        "ps-1",
        "Practice Squad",
        status="Practice Squad",
        years_exp=2,
        age=24,
        fantasycalc_value=200,
    )
    assert player_eligibility(pup, now=NOW)["eligible"] is True
    assert player_eligibility(practice, now=NOW)["eligible"] is True


def test_trade_search_and_recommendation_pools_drop_retired_assets():
    pool = filter_current_fantasy_players(
        _decision_pool(),
        surface="trade_search_pool",
        now=NOW,
    )
    recommendations = draft_assistant.build_recommendation_buckets(
        _decision_pool(),
        score_field="dynasty_score",
    )
    assert "138" not in pool["player_id"].astype(str).tolist()
    assert all(str(item.get("player_id")) != "138" for item in recommendations)


def test_shop_next_move_routes_owned_player_as_send_asset():
    my_team = Path("modules/my_team_ui.py").read_text(encoding="utf-8")
    app = Path("app.py").read_text(encoding="utf-8")
    assert 'route_focus_mode": "my_player"' in my_team
    assert "next_move_shop_player_id" in my_team
    assert '"route_focus_mode": "my_player"' in app
    assert "next_move_shop_player_id=next_move_shop_player_id" in app
    assert 'st.session_state["waivers_focus_player_id"]' in app
    assert "route_player_id" in my_team


def test_roster_actions_grid_is_content_height():
    css = Path("modules/visual_hierarchy_styles.py").read_text(encoding="utf-8")
    assert "st-key-my_team_roster_actions" in css
    assert "height: auto" in css
    workspace = Path("modules/my_team_ui.py").read_text(encoding="utf-8")
    assert 'key="my_team_roster_actions"' in workspace
