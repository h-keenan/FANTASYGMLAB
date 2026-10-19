"""modules.community_trades — the anonymized Community Trade Feed projection.

Mocks requests (the service-role Supabase I/O boundary), matching the
mocking convention used across tests/test_trade_outcome_results.py and
tests/test_push_triggers.py. build_community_feed_items is pure (no I/O) and
is exercised directly with plain dicts, same as
trade_outcome_results.compute_trade_result.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

from modules import community_trades as ct


def _config() -> ct.CommunityFeedConfig:
    return ct.CommunityFeedConfig(url="https://example.supabase.co", service_role_key="service-role-key")


def _ready_row(
    *,
    outcome_id: str = "outcome-1",
    user_id: str = "user-1",
    verdict: str = "worked_out",
    confidence: str = "high",
    avg_per_week: float = 6.0,
    net_delta_pct: float = 20.0,
    occurred_at: str = "2026-09-01T00:00:00Z",
    partner_team_name: str = "The Gridiron Gurus",
) -> dict:
    return {
        "id": outcome_id,
        "user_id": user_id,
        "league_id": "league-123",
        "partner_team_name": partner_team_name,
        "trade_summary": {
            "partner_team_name": partner_team_name,
            "send": [{"name": "Sender Guy", "position": "WR", "player_id": "100", "value_score": 70}],
            "receive": [{"name": "Receiver Guy", "position": "RB", "player_id": "200", "value_score": 90}],
        },
        "outcome_recorded_at": occurred_at,
        "shared_at": "2026-08-01T00:00:00Z",
        "result_summary": {
            "status": "ready",
            "verdict": verdict,
            "verdict_label": "This trade has worked out" if verdict == "worked_out" else "This trade hasn't paid off yet",
            "confidence": confidence,
            "production": {"net_points_ppr": 30, "avg_net_per_week": avg_per_week, "weeks_counted": 5},
            "value": {"sent_delta_pct": -4, "received_delta_pct": 16, "net_delta_pct": net_delta_pct},
        },
        "result_computed_at": "2026-09-05T00:00:00Z",
    }


# --- config -------------------------------------------------------------


def test_load_community_feed_config_reads_expected_env_vars():
    config = ct.load_community_feed_config(
        environ={"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
    )
    assert config.configured
    assert config.url == "https://x.supabase.co"


def test_load_community_feed_config_not_configured_without_service_role_key():
    config = ct.load_community_feed_config(environ={"SUPABASE_URL": "https://x.supabase.co"})
    assert not config.configured


# --- fetch (service-role I/O) --------------------------------------------


def test_fetch_interesting_trade_outcomes_queries_high_confidence_verdicts():
    response = Mock(status_code=200)
    response.json.return_value = [_ready_row()]
    with patch("requests.get", return_value=response) as mock_get:
        rows = ct.fetch_interesting_trade_outcomes(_config())
    assert len(rows) == 1
    params = mock_get.call_args.kwargs["params"]
    assert params["outcome"] == "eq.yes"
    assert params["result_summary->>confidence"] == "eq.high"
    assert params["result_summary->>verdict"] == "in.(worked_out,didnt_pan_out)"


def test_fetch_interesting_trade_outcomes_returns_empty_when_not_configured():
    with patch("requests.get") as mock_get:
        rows = ct.fetch_interesting_trade_outcomes(ct.CommunityFeedConfig())
    assert rows == []
    mock_get.assert_not_called()


def test_fetch_interesting_trade_outcomes_fails_soft_on_error_status():
    response = Mock(status_code=500)
    with patch("requests.get", return_value=response):
        rows = ct.fetch_interesting_trade_outcomes(_config())
    assert rows == []


def test_fetch_opted_out_user_ids_reads_community_trades_opt_out_key():
    response = Mock(status_code=200)
    response.json.return_value = [
        {"user_id": "u1", "settings": {"community_trades_opt_out": True}},
        {"user_id": "u2", "settings": {"community_trades_opt_out": False}},
        {"user_id": "u3", "settings": {}},
    ]
    with patch("requests.get", return_value=response):
        opted_out = ct.fetch_opted_out_user_ids(_config())
    assert opted_out == {"u1"}


def test_fetch_opted_out_user_ids_returns_empty_set_on_error():
    response = Mock(status_code=404)
    with patch("requests.get", return_value=response):
        opted_out = ct.fetch_opted_out_user_ids(_config())
    assert opted_out == set()


def test_fetch_reaction_rows_queries_outcome_ids_in_filter():
    response = Mock(status_code=200)
    response.json.return_value = [{"outcome_id": "outcome-1", "user_id": "u1", "emoji": "\U0001f525"}]
    with patch("requests.get", return_value=response) as mock_get:
        rows = ct.fetch_reaction_rows(_config(), ["outcome-1", "outcome-2"])
    assert len(rows) == 1
    params = mock_get.call_args.kwargs["params"]
    assert params["outcome_id"] == "in.(outcome-1,outcome-2)"


def test_fetch_reaction_rows_returns_empty_without_ids():
    with patch("requests.get") as mock_get:
        rows = ct.fetch_reaction_rows(_config(), [])
    assert rows == []
    mock_get.assert_not_called()


# --- build_community_feed_items (pure) ------------------------------------


def test_build_community_feed_items_anonymizes_and_never_leaks_identity():
    rows = [_ready_row()]
    items = ct.build_community_feed_items(rows)
    assert len(items) == 1
    item = items[0]
    # Never present anywhere in the anonymized output:
    serialized_keys = set(item.keys())
    assert "user_id" not in serialized_keys
    assert "league_id" not in serialized_keys
    assert "partner_team_name" not in serialized_keys
    # Player content (public NFL-player facts) still comes through:
    assert item["send"][0]["name"] == "Sender Guy"
    assert item["receive"][0]["name"] == "Receiver Guy"
    assert item["verdict"] == "worked_out"


def test_build_community_feed_items_excludes_opted_out_users():
    rows = [_ready_row(outcome_id="a", user_id="opted-out-user"), _ready_row(outcome_id="b", user_id="visible-user")]
    items = ct.build_community_feed_items(rows, opted_out_user_ids={"opted-out-user"})
    assert [item["id"] for item in items] == ["b"]


def test_build_community_feed_items_excludes_non_high_confidence_or_mixed_verdicts():
    rows = [
        _ready_row(outcome_id="low-confidence", confidence="medium"),
        _ready_row(outcome_id="mixed-verdict", verdict="mixed"),
        _ready_row(outcome_id="neutral-verdict", verdict="neutral"),
        _ready_row(outcome_id="kept"),
    ]
    items = ct.build_community_feed_items(rows)
    assert [item["id"] for item in items] == ["kept"]


def test_build_community_feed_items_sorts_by_magnitude_then_recency():
    small_edge = _ready_row(outcome_id="small", avg_per_week=1.0, net_delta_pct=5.0, occurred_at="2026-09-10T00:00:00Z")
    big_edge = _ready_row(outcome_id="big", avg_per_week=9.0, net_delta_pct=5.0, occurred_at="2026-09-01T00:00:00Z")
    items = ct.build_community_feed_items([small_edge, big_edge])
    assert [item["id"] for item in items] == ["big", "small"]


def test_build_community_feed_items_recency_tiebreaks_equal_magnitude():
    older = _ready_row(outcome_id="older", avg_per_week=5.0, net_delta_pct=5.0, occurred_at="2026-09-01T00:00:00Z")
    newer = _ready_row(outcome_id="newer", avg_per_week=5.0, net_delta_pct=5.0, occurred_at="2026-09-10T00:00:00Z")
    items = ct.build_community_feed_items([older, newer])
    assert [item["id"] for item in items] == ["newer", "older"]


def test_build_community_feed_items_respects_limit():
    rows = [_ready_row(outcome_id=f"outcome-{i}") for i in range(5)]
    items = ct.build_community_feed_items(rows, limit=2)
    assert len(items) == 2


def test_build_community_feed_items_folds_in_reaction_counts_and_viewer_reactions():
    rows = [_ready_row(outcome_id="outcome-1")]
    reaction_rows = [
        {"outcome_id": "outcome-1", "user_id": "viewer", "emoji": "\U0001f525"},
        {"outcome_id": "outcome-1", "user_id": "someone-else", "emoji": "\U0001f525"},
        {"outcome_id": "outcome-1", "user_id": "someone-else", "emoji": "\U0001f480"},
    ]
    items = ct.build_community_feed_items(rows, reaction_rows=reaction_rows, viewer_user_id="viewer")
    item = items[0]
    assert item["reactions"] == {"\U0001f525": 2, "\U0001f480": 1}
    assert item["my_reactions"] == ["\U0001f525"]


def test_build_community_feed_items_ignores_reactions_with_unknown_emoji():
    rows = [_ready_row(outcome_id="outcome-1")]
    reaction_rows = [{"outcome_id": "outcome-1", "user_id": "u1", "emoji": "not-a-real-emoji"}]
    items = ct.build_community_feed_items(rows, reaction_rows=reaction_rows)
    assert items[0]["reactions"] == {}


def test_build_community_feed_items_skips_rows_missing_id():
    rows = [{**_ready_row(), "id": ""}]
    items = ct.build_community_feed_items(rows)
    assert items == []
