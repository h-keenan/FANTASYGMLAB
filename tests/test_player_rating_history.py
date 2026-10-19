"""modules.player_rating_history — daily 0-99 overall-rating snapshots.

Mocks requests (the Supabase service-role I/O boundary), matching the
mocking convention used in tests/test_trade_outcome_results.py.
build_snapshot_rows/explain_rating_change/snapshot_rating are pure (no I/O)
and are exercised directly with plain dicts/frames.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pandas as pd

from modules import player_rating_history as prh


def _config() -> prh.RatingSnapshotConfig:
    return prh.RatingSnapshotConfig(url="https://example.supabase.co", service_role_key="service-role-key")


# --- config -----------------------------------------------------------------


def test_load_rating_snapshot_config_reads_expected_env_vars():
    config = prh.load_rating_snapshot_config(
        environ={"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
    )
    assert config.configured
    assert config.url == "https://x.supabase.co"


def test_load_rating_snapshot_config_not_configured_without_service_role_key():
    config = prh.load_rating_snapshot_config(environ={"SUPABASE_URL": "https://x.supabase.co"})
    assert not config.configured


# --- build_snapshot_rows (pure) ----------------------------------------------


def test_build_snapshot_rows_keeps_only_real_scoreable_players():
    frame = pd.DataFrame(
        [
            {"player_id": "1", "overall_rating": 87},
            {"player_id": "2", "overall_rating": None},  # unscoreable (thin pool)
            {"player_id": "", "overall_rating": 50},  # blank id
            {"player_id": "3", "overall_rating": 150},  # out of 0-99 range
            {"player_id": "4", "overall_rating": 0},  # real, boundary-valid
        ]
    )
    rows = prh.build_snapshot_rows(frame, snapshot_date="2026-10-19")
    assert rows == [
        {"player_id": "1", "snapshot_date": "2026-10-19", "overall_rating": 87},
        {"player_id": "4", "snapshot_date": "2026-10-19", "overall_rating": 0},
    ]


def test_build_snapshot_rows_dedupes_repeated_player_id():
    frame = pd.DataFrame(
        [
            {"player_id": "1", "overall_rating": 80},
            {"player_id": "1", "overall_rating": 81},
        ]
    )
    rows = prh.build_snapshot_rows(frame, snapshot_date="2026-10-19")
    assert len(rows) == 1
    assert rows[0]["overall_rating"] == 80


def test_build_snapshot_rows_defaults_to_todays_utc_date_when_unspecified():
    from datetime import datetime, timezone

    frame = pd.DataFrame([{"player_id": "1", "overall_rating": 80}])
    rows = prh.build_snapshot_rows(frame)
    assert rows[0]["snapshot_date"] == datetime.now(timezone.utc).date().isoformat()


def test_build_snapshot_rows_empty_or_malformed_frame_returns_empty_list():
    assert prh.build_snapshot_rows(None) == []
    assert prh.build_snapshot_rows(pd.DataFrame()) == []
    assert prh.build_snapshot_rows(pd.DataFrame([{"player_id": "1"}])) == []  # no overall_rating column


# --- store_daily_snapshot ----------------------------------------------------


def test_store_daily_snapshot_not_configured():
    with patch("requests.post") as mock_post:
        stats = prh.store_daily_snapshot(prh.RatingSnapshotConfig(), pd.DataFrame([{"player_id": "1", "overall_rating": 80}]))
    assert stats["ok"] is False
    assert not stats["configured"]
    mock_post.assert_not_called()


def test_store_daily_snapshot_empty_pool_is_a_recorded_error_not_a_crash():
    stats = prh.store_daily_snapshot(_config(), pd.DataFrame())
    assert stats["ok"] is False
    assert stats["rows_sent"] == 0
    assert stats["errors"]


def test_store_daily_snapshot_upserts_with_on_conflict_and_merge_duplicates_prefer():
    frame = pd.DataFrame([{"player_id": "1", "overall_rating": 87}, {"player_id": "2", "overall_rating": 62}])
    response = Mock(status_code=200)
    with patch("requests.post", return_value=response) as mock_post:
        stats = prh.store_daily_snapshot(_config(), frame, snapshot_date="2026-10-19")

    assert stats["ok"] is True
    assert stats["rows_sent"] == 2
    call = mock_post.call_args
    assert "player_rating_snapshots" in call.args[0]
    assert call.kwargs["params"] == {"on_conflict": "player_id,snapshot_date"}
    assert call.kwargs["headers"]["Prefer"] == "resolution=merge-duplicates,return=minimal"
    sent_rows = call.kwargs["json"]
    assert {row["player_id"] for row in sent_rows} == {"1", "2"}
    assert all(row["snapshot_date"] == "2026-10-19" for row in sent_rows)
    assert all("computed_at" in row for row in sent_rows)


def test_store_daily_snapshot_records_error_on_http_failure_without_raising():
    frame = pd.DataFrame([{"player_id": "1", "overall_rating": 87}])
    response = Mock(status_code=500, text="server error")
    with patch("requests.post", return_value=response):
        stats = prh.store_daily_snapshot(_config(), frame)
    assert stats["ok"] is False
    assert stats["rows_sent"] == 0
    assert stats["errors"]


def test_store_daily_snapshot_fails_soft_on_request_exception():
    frame = pd.DataFrame([{"player_id": "1", "overall_rating": 87}])
    with patch("requests.post", side_effect=Exception("network down")):
        stats = prh.store_daily_snapshot(_config(), frame)
    assert stats["ok"] is False
    assert stats["errors"]


# --- fetch_rating_history -----------------------------------------------------


def test_fetch_rating_history_not_configured_returns_empty_without_calling_requests():
    with patch("requests.get") as mock_get:
        rows = prh.fetch_rating_history(prh.RatingSnapshotConfig(), "9001")
    assert rows == []
    mock_get.assert_not_called()


def test_fetch_rating_history_blank_player_id_returns_empty():
    with patch("requests.get") as mock_get:
        rows = prh.fetch_rating_history(_config(), "")
    assert rows == []
    mock_get.assert_not_called()


def test_fetch_rating_history_returns_newest_first_rows_and_uses_expected_query():
    response = Mock(status_code=200)
    response.json.return_value = [
        {"player_id": "9001", "snapshot_date": "2026-10-19", "overall_rating": 80, "computed_at": "x"},
        {"player_id": "9001", "snapshot_date": "2026-10-18", "overall_rating": 76, "computed_at": "y"},
    ]
    with patch("requests.get", return_value=response) as mock_get:
        rows = prh.fetch_rating_history(_config(), "9001", limit=2)

    assert len(rows) == 2
    assert rows[0]["snapshot_date"] == "2026-10-19"
    params = mock_get.call_args.kwargs["params"]
    assert params["player_id"] == "eq.9001"
    assert params["order"] == "snapshot_date.desc"
    assert params["limit"] == "2"


def test_fetch_rating_history_fails_soft_when_table_does_not_exist_yet():
    """Before docs/supabase_player_rating_snapshots.sql has been run,
    Supabase/PostgREST returns a 4xx for the unknown table — this must read
    exactly like "no history yet," never crash the caller."""

    response = Mock(status_code=404, text="relation does not exist")
    with patch("requests.get", return_value=response):
        rows = prh.fetch_rating_history(_config(), "9001")
    assert rows == []


def test_fetch_rating_history_fails_soft_on_request_exception():
    with patch("requests.get", side_effect=Exception("network down")):
        rows = prh.fetch_rating_history(_config(), "9001")
    assert rows == []


def test_fetch_rating_history_fails_soft_on_non_list_body():
    response = Mock(status_code=200)
    response.json.return_value = {"message": "unexpected"}
    with patch("requests.get", return_value=response):
        rows = prh.fetch_rating_history(_config(), "9001")
    assert rows == []


# --- snapshot_rating (pure) ---------------------------------------------------


def test_snapshot_rating_parses_a_real_in_range_value():
    assert prh.snapshot_rating({"overall_rating": 87}) == 87
    assert prh.snapshot_rating({"overall_rating": "62"}) == 62


def test_snapshot_rating_rejects_missing_or_out_of_range_value():
    assert prh.snapshot_rating(None) is None
    assert prh.snapshot_rating({}) is None
    assert prh.snapshot_rating({"overall_rating": None}) is None
    assert prh.snapshot_rating({"overall_rating": -1}) is None
    assert prh.snapshot_rating({"overall_rating": 100}) is None


# --- explain_rating_change (pure) ---------------------------------------------


def test_explain_rating_change_zero_delta():
    assert prh.explain_rating_change(delta=0) == "No meaningful rating change since the last snapshot."


def test_explain_rating_change_no_corroboration_is_honest_about_it():
    explanation = prh.explain_rating_change(delta=4)
    assert "increased 4 points" in explanation
    assert prh.NO_SIGNIFICANT_DRIVER in explanation


def test_explain_rating_change_decreasing_singular_point_wording():
    explanation = prh.explain_rating_change(delta=-1)
    assert "decreased 1 point " in explanation  # singular, not "1 points"


def test_explain_rating_change_cites_the_first_corroborating_event():
    explanation = prh.explain_rating_change(
        delta=-6,
        corroborating_events=[
            {"description": "Ruled out for Sunday with a hamstring injury"},
            {"description": "A second, lower-priority event"},
        ],
    )
    assert "decreased 6 points" in explanation
    assert "Ruled out for Sunday with a hamstring injury" in explanation
    assert "A second, lower-priority event" not in explanation


# --- load_global_rating_pool ---------------------------------------------------


def test_load_global_rating_pool_returns_empty_frame_when_no_players_available():
    with patch("modules.rankings.load_players", return_value=pd.DataFrame()):
        with patch("modules.rankings.build_players_table", return_value=pd.DataFrame()):
            pool = prh.load_global_rating_pool()
    assert pool.empty


def test_load_global_rating_pool_filters_to_canonical_positions_and_attaches_rating():
    raw = pd.DataFrame(
        [
            {"player_id": "1", "name": "A", "position": "RB", "score": 90},
            {"player_id": "2", "name": "B", "position": "DEF", "score": 10},
        ]
    )
    with patch("modules.rankings.load_players", return_value=raw):
        with patch(
            "modules.player_eligibility.filter_current_fantasy_players", side_effect=lambda frame, **kwargs: frame
        ):
            pool = prh.load_global_rating_pool()
    assert set(pool["position"]) == {"RB"}
    assert "overall_rating" in pool.columns


# --- run_player_rating_snapshot_sweep ------------------------------------------


def test_run_player_rating_snapshot_sweep_not_configured():
    stats = prh.run_player_rating_snapshot_sweep(environ={})
    assert stats["ok"] is False
    assert not stats["configured"]


def test_run_player_rating_snapshot_sweep_success_path():
    pool = pd.DataFrame([{"player_id": "1", "overall_rating": 80}])
    environ = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
    response = Mock(status_code=200)
    with patch.object(prh, "load_global_rating_pool", return_value=pool):
        with patch("requests.post", return_value=response):
            stats = prh.run_player_rating_snapshot_sweep(environ=environ)
    assert stats["ok"] is True
    assert stats["players_in_pool"] == 1
    assert stats["rows_sent"] == 1


def test_run_player_rating_snapshot_sweep_records_pool_build_failure_without_raising():
    environ = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
    with patch.object(prh, "load_global_rating_pool", side_effect=Exception("sleeper is down")):
        stats = prh.run_player_rating_snapshot_sweep(environ=environ)
    assert stats["ok"] is False
    assert stats["errors"]
