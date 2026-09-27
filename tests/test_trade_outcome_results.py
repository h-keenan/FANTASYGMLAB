"""modules.trade_outcome_results — the quiet "did this trade work?" sweep.

Mocks requests (the Supabase service-role I/O boundary) and
load_valued_players_for_result/sleeper calls, matching the mocking
convention used across tests/test_push_triggers.py. compute_trade_result is
pure (no I/O) and is exercised directly with plain dicts.

Safety rule: this file must NEVER call modules.rankings.load_players or
modules.rankings.build_players_table — every test that reaches
run_trade_outcome_result_sweep monkeypatches
trade_outcome_results.load_valued_players_for_result instead of letting it
run for real.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pandas as pd

from modules import trade_outcome_results as tor


def _config() -> tor.ResultSweepConfig:
    return tor.ResultSweepConfig(url="https://example.supabase.co", service_role_key="service-role-key")


# --- config -----------------------------------------------------------------


def test_load_result_sweep_config_reads_expected_env_vars():
    config = tor.load_result_sweep_config(
        environ={"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
    )
    assert config.configured
    assert config.url == "https://x.supabase.co"


def test_load_result_sweep_config_not_configured_without_service_role_key():
    config = tor.load_result_sweep_config(environ={"SUPABASE_URL": "https://x.supabase.co"})
    assert not config.configured


# --- fetch/store --------------------------------------------------------------


def test_fetch_pending_trade_outcome_results_returns_rows():
    response = Mock(status_code=200)
    response.json.return_value = [
        {"id": "outcome-1", "user_id": "u1", "league_id": "league-1", "trade_summary": {}, "outcome_recorded_at": "x"},
    ]
    with patch("requests.get", return_value=response) as mock_get:
        rows = tor.fetch_pending_trade_outcome_results(_config())
    assert len(rows) == 1
    params = mock_get.call_args.kwargs["params"]
    assert params["outcome"] == "eq.yes"
    assert params["result_computed_at"] == "is.null"
    assert params["outcome_recorded_at"].startswith("lte.")


def test_fetch_pending_trade_outcome_results_empty_when_not_configured():
    with patch("requests.get") as mock_get:
        rows = tor.fetch_pending_trade_outcome_results(tor.ResultSweepConfig())
    assert rows == []
    mock_get.assert_not_called()


def test_store_trade_outcome_result_patches_the_row():
    with patch("requests.patch") as mock_patch:
        tor.store_trade_outcome_result(_config(), outcome_id="outcome-1", result_summary={"status": "ready"})
    call = mock_patch.call_args
    assert "trade_outcomes" in call.args[0]
    assert call.kwargs["params"] == {"id": "eq.outcome-1"}
    assert call.kwargs["json"]["result_summary"] == {"status": "ready"}
    assert "result_computed_at" in call.kwargs["json"]


# --- compute_trade_result (pure) ---------------------------------------------


def _iso_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def test_compute_trade_result_insufficient_without_any_tracked_player():
    summary = {
        "send": [{"name": "A", "position": "RB"}],
        "receive": [{"name": "B", "position": "WR"}],
    }
    result = tor.compute_trade_result(
        trade_summary=summary,
        outcome_recorded_at=_iso_days_ago(30),
        current_value_by_player={},
        season_stats={},
    )
    assert result["status"] == "insufficient_data"
    assert result["reason"] == "no_tracked_players"
    assert result["verdict"] is None


def test_compute_trade_result_insufficient_when_no_stats_or_value_data():
    summary = {
        "send": [{"name": "A", "position": "RB", "player_id": "1"}],
        "receive": [{"name": "B", "position": "WR", "player_id": "2"}],
    }
    result = tor.compute_trade_result(
        trade_summary=summary,
        outcome_recorded_at=_iso_days_ago(30),
        current_value_by_player={},
        season_stats={},
    )
    assert result["status"] == "insufficient_data"
    assert result["reason"] == "no_stat_data_yet"
    assert result["verdict"] is None


def test_compute_trade_result_production_signal_clearly_worked_out():
    summary = {
        "send": [{"name": "A", "position": "RB", "player_id": "1"}],
        "receive": [{"name": "B", "position": "WR", "player_id": "2"}],
    }
    season_stats = {
        "1": {"weekly": [{"week": 1, "fantasy_points_ppr": 2.0}, {"week": 2, "fantasy_points_ppr": 3.0}]},
        "2": {"weekly": [{"week": 1, "fantasy_points_ppr": 20.0}, {"week": 2, "fantasy_points_ppr": 18.0}]},
    }
    result = tor.compute_trade_result(
        trade_summary=summary,
        outcome_recorded_at=_iso_days_ago(28),
        current_value_by_player={},
        season_stats=season_stats,
    )
    assert result["status"] == "ready"
    assert result["verdict"] == "worked_out"
    assert result["production"]["net_points_ppr"] > 0
    # Only one signal available (no value data) -> low confidence.
    assert result["confidence"] == "low"


def test_compute_trade_result_didnt_pan_out_when_production_clearly_negative():
    summary = {
        "send": [{"name": "A", "position": "RB", "player_id": "1"}],
        "receive": [{"name": "B", "position": "WR", "player_id": "2"}],
    }
    season_stats = {
        "1": {"weekly": [{"week": 1, "fantasy_points_ppr": 20.0}]},
        "2": {"weekly": [{"week": 1, "fantasy_points_ppr": 1.0}]},
    }
    result = tor.compute_trade_result(
        trade_summary=summary,
        outcome_recorded_at=_iso_days_ago(28),
        current_value_by_player={},
        season_stats=season_stats,
    )
    assert result["verdict"] == "didnt_pan_out"


def test_compute_trade_result_agreeing_signals_yield_high_confidence():
    summary = {
        "send": [{"name": "A", "position": "RB", "player_id": "1", "value_score": 1000.0}],
        "receive": [{"name": "B", "position": "WR", "player_id": "2", "value_score": 1000.0}],
    }
    season_stats = {
        "1": {"weekly": [{"week": 1, "fantasy_points_ppr": 2.0}]},
        "2": {"weekly": [{"week": 1, "fantasy_points_ppr": 20.0}]},
    }
    # Received player's current value way up, sent player's current value flat.
    current_value_by_player = {"1": 1000.0, "2": 1300.0}
    result = tor.compute_trade_result(
        trade_summary=summary,
        outcome_recorded_at=_iso_days_ago(28),
        current_value_by_player=current_value_by_player,
        season_stats=season_stats,
    )
    assert result["verdict"] == "worked_out"
    assert result["confidence"] == "high"
    assert result["value"]["net_delta_pct"] > 0


def test_compute_trade_result_conflicting_signals_are_mixed():
    summary = {
        "send": [{"name": "A", "position": "RB", "player_id": "1", "value_score": 1000.0}],
        "receive": [{"name": "B", "position": "WR", "player_id": "2", "value_score": 1000.0}],
    }
    # Production says "worked out" (received player way outscoring).
    season_stats = {
        "1": {"weekly": [{"week": 1, "fantasy_points_ppr": 2.0}]},
        "2": {"weekly": [{"week": 1, "fantasy_points_ppr": 20.0}]},
    }
    # But value_score says the opposite (received player's value cratered).
    current_value_by_player = {"1": 1000.0, "2": 700.0}
    result = tor.compute_trade_result(
        trade_summary=summary,
        outcome_recorded_at=_iso_days_ago(28),
        current_value_by_player=current_value_by_player,
        season_stats=season_stats,
    )
    assert result["verdict"] == "mixed"
    assert result["confidence"] == "low"


def test_compute_trade_result_neutral_when_deltas_are_within_noise():
    summary = {
        "send": [{"name": "A", "position": "RB", "player_id": "1"}],
        "receive": [{"name": "B", "position": "WR", "player_id": "2"}],
    }
    season_stats = {
        "1": {"weekly": [{"week": 1, "fantasy_points_ppr": 10.0}]},
        "2": {"weekly": [{"week": 1, "fantasy_points_ppr": 10.5}]},
    }
    result = tor.compute_trade_result(
        trade_summary=summary,
        outcome_recorded_at=_iso_days_ago(28),
        current_value_by_player={},
        season_stats=season_stats,
    )
    assert result["verdict"] == "neutral"


def test_compute_trade_result_excludes_untracked_assets_from_totals():
    summary = {
        "send": [
            {"name": "A", "position": "RB", "player_id": "1"},
            {"name": "PickOrUntracked", "position": "PICK"},
        ],
        "receive": [{"name": "B", "position": "WR", "player_id": "2"}],
    }
    season_stats = {
        "1": {"weekly": [{"week": 1, "fantasy_points_ppr": 5.0}]},
        "2": {"weekly": [{"week": 1, "fantasy_points_ppr": 5.0}]},
    }
    result = tor.compute_trade_result(
        trade_summary=summary,
        outcome_recorded_at=_iso_days_ago(28),
        current_value_by_player={},
        season_stats=season_stats,
    )
    assert result["total_send_count"] == 2
    assert result["tracked_send_count"] == 1


def test_weeks_elapsed_for_bounds():
    assert tor.weeks_elapsed_for(None) == tor.RESULT_DELAY_DAYS // 7
    assert tor.weeks_elapsed_for(0) == 1
    assert tor.weeks_elapsed_for(400) == tor.MAX_WEEKS_CONSIDERED


# --- run_trade_outcome_result_sweep (orchestration) --------------------------


def test_run_trade_outcome_result_sweep_fails_soft_when_not_configured():
    stats = tor.run_trade_outcome_result_sweep(environ={})
    assert stats["ok"] is False
    assert stats["configured"] is False
    assert stats["results_computed"] == 0
    assert stats["errors"]


def test_run_trade_outcome_result_sweep_stores_insufficient_data_without_touching_rankings_or_sleeper():
    config_env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
    pending_response = Mock(status_code=200)
    pending_response.json.return_value = [
        {
            "id": "outcome-1",
            "user_id": "u1",
            "league_id": "league-1",
            "trade_summary": {"send": [{"name": "A", "position": "RB"}], "receive": [{"name": "B", "position": "WR"}]},
            "outcome_recorded_at": _iso_days_ago(30),
        },
    ]
    with patch("requests.get", return_value=pending_response):
        with patch("requests.patch") as mock_patch:
            with patch("modules.sleeper.get_season_player_stats") as mock_stats:
                with patch.object(tor, "load_valued_players_for_result") as mock_load:
                    stats = tor.run_trade_outcome_result_sweep(environ=config_env)

    assert stats["configured"] is True
    assert stats["outcomes_checked"] == 1
    assert stats["results_computed"] == 1
    assert not stats["errors"]
    mock_stats.assert_not_called()
    mock_load.assert_not_called()
    mock_patch.assert_called_once()
    assert mock_patch.call_args.kwargs["json"]["result_summary"]["reason"] == "no_tracked_players"


def test_run_trade_outcome_result_sweep_computes_a_real_result_and_caches_valuation_per_league_lens():
    config_env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
    pending_response = Mock(status_code=200)
    pending_response.json.return_value = [
        {
            "id": "outcome-1",
            "user_id": "u1",
            "league_id": "league-1",
            "trade_summary": {
                "send": [{"name": "A", "position": "RB", "player_id": "1", "value_score": 1000.0}],
                "receive": [{"name": "B", "position": "WR", "player_id": "2", "value_score": 1000.0}],
                "valuation_lens": "Dynasty",
            },
            "outcome_recorded_at": _iso_days_ago(30),
        },
        {
            "id": "outcome-2",
            "user_id": "u1",
            "league_id": "league-1",
            "trade_summary": {
                "send": [{"name": "C", "position": "QB", "player_id": "3", "value_score": 500.0}],
                "receive": [{"name": "D", "position": "TE", "player_id": "4", "value_score": 500.0}],
                "valuation_lens": "Dynasty",
            },
            "outcome_recorded_at": _iso_days_ago(35),
        },
    ]
    valued_df = pd.DataFrame(
        {"player_id": ["1", "2", "3", "4"], "dynasty_score": [900.0, 1400.0, 480.0, 520.0]}
    )

    with patch("requests.get", return_value=pending_response):
        with patch("requests.patch") as mock_patch:
            with patch("modules.sleeper.get_season_player_stats", return_value={}) as mock_stats:
                with patch("modules.sleeper.get_league", return_value={"name": "Test League"}) as mock_league:
                    with patch.object(
                        tor, "load_valued_players_for_result", return_value=(valued_df, "dynasty_score")
                    ) as mock_load:
                        stats = tor.run_trade_outcome_result_sweep(environ=config_env)

    assert stats["results_computed"] == 2
    assert not stats["errors"]
    # season stats fetched once and reused across both rows.
    mock_stats.assert_called_once()
    # Both rows share the same (league_id, lens) -> valuation loaded once.
    assert mock_load.call_count == 1
    assert mock_load.call_args[0][0] == "Dynasty"
    assert mock_league.call_count == 1
    assert mock_patch.call_count == 2
    first_result = mock_patch.call_args_list[0].kwargs["json"]["result_summary"]
    assert first_result["status"] == "ready"
    assert first_result["verdict"] == "worked_out"
