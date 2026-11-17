"""modules.rookie_adp: FFC parse, exact id mapping, store/run, multi-factor read."""

from __future__ import annotations

from datetime import date
from unittest.mock import Mock, patch

from modules import data_freshness, rookie_adp
from services import mobile_api_service as api

PAYLOAD = {
    "status": "Success",
    "meta": {"type": "Dynasty Rookie", "teams": 12, "total_drafts": 61, "start_date": "2026-08-01", "end_date": "2026-09-01"},
    "players": [
        {"player_id": 1, "name": "Ashton Jeanty", "position": "RB", "team": "LV", "adp": 1.2, "adp_formatted": "1.01", "times_drafted": 16, "high": 1, "low": 2, "stdev": 0.4},
        {"player_id": 2, "name": "Mystery Guy", "position": "WR", "team": "NYJ", "adp": 5.0, "adp_formatted": "1.05", "times_drafted": 9, "high": 2, "low": 9, "stdev": 2.0},
        {"player_id": 3, "name": "Twin Name", "position": "WR", "team": "DAL", "adp": 7.0, "times_drafted": 5},
        {"player_id": 4, "name": "Some Kicker", "position": "K", "adp": 12.0},
        {"player_id": 5, "name": "No Adp", "position": "RB", "adp": None},
    ],
}
POOL = [
    {"player_id": "100", "name": "Ashton Jeanty", "position": "RB", "team": "LV"},
    {"player_id": "200", "name": "Twin Name", "position": "WR", "team": "DAL"},
    {"player_id": "201", "name": "Twin Name", "position": "WR", "team": "DAL"},
]


def test_parse_keeps_only_real_skill_rows():
    meta, rows = rookie_adp.parse_payload(PAYLOAD)
    assert meta["total_drafts"] == 61
    assert [r["name"] for r in rows] == ["Ashton Jeanty", "Mystery Guy", "Twin Name"]


def test_empty_window_parses_to_no_rows():
    assert rookie_adp.parse_payload({"status": "Success", "meta": {}, "players": []})[1] == []
    assert rookie_adp.parse_payload(None) == ({}, [])


def test_match_is_exact_and_never_guesses():
    _meta, rows = rookie_adp.parse_payload(PAYLOAD)
    matched, unmatched = rookie_adp.match_rows(rows, POOL)
    by_name = {r["name"]: r["sleeper_id"] for r in matched}
    assert by_name == {"Ashton Jeanty": "100", "Mystery Guy": None, "Twin Name": None}
    reasons = {u["name"]: u["reason"] for u in unmatched}
    assert reasons == {"Mystery Guy": "no_match", "Twin Name": "ambiguous"}


def test_value_vs_adp_is_multi_factor_and_flags_thin_samples():
    read = rookie_adp.value_vs_adp(2, {"adp": 9.0, "drafts": 4, "high": 3, "low": 20, "stdev": 7.0, "trend": -2.0, "trend_since": "2026-09-01"})
    assert read["verdict"] == "value" and read["delta"] == 7.0 and read["thin_sample"] is True
    for part in ("thin sample", "wide spread", "rising"):
        assert part in read["read"]
    assert rookie_adp.value_vs_adp(5, {"adp": 6.0, "drafts": 30})["verdict"] == "aligned"
    assert rookie_adp.value_vs_adp(10, {"adp": 3.0, "drafts": 30})["verdict"] == "reach"
    assert rookie_adp.value_vs_adp(1, None)["adp"] is None


def test_board_lists_players_without_adp_honestly():
    snapshot = {"players": {"a": {"adp": 2.0, "drafts": 20}}}
    board = rookie_adp.build_rookie_board(
        [{"player_id": "a", "name": "A", "score": 50}, {"player_id": "b", "name": "B", "score": 90}], snapshot
    )
    assert [r["player_id"] for r in board] == ["b", "a"]
    assert board[0]["adp"] is None and board[1]["adp"] == 2.0 and board[1]["our_rank"] == 2


def test_run_snapshot_unconfigured_fails_soft():
    assert rookie_adp.run_snapshot(environ={})["ok"] is False


def test_run_snapshot_stores_and_reports_unmatched(tmp_path):
    env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}
    empty = {"status": "Success", "meta": {}, "players": []}
    with patch.object(rookie_adp, "load_pool", return_value=POOL), patch.object(
        rookie_adp, "fetch_ffc", side_effect=[PAYLOAD, empty]
    ), patch.object(rookie_adp.requests, "post", return_value=Mock(status_code=201)) as post:
        report = rookie_adp.run_snapshot(environ=env, today=date(2026, 9, 5))
    assert report["ok"] is True
    assert report["formats"]["rookie_1qb"]["matched"] == 1
    assert report["formats"]["dynasty_1qb"]["status"] == "empty"
    sent = post.call_args.kwargs["json"]
    assert {r["snapshot_date"] for r in sent} == {"2026-09-05"} and len(sent) == 3
    assert {u["name"] for u in report["unmatched"]} == {"Mystery Guy", "Twin Name"}


def test_fetch_latest_is_fail_soft_without_supabase():
    assert rookie_adp.fetch_latest("rookie_1qb", config=rookie_adp.AdpConfig()) == {}
    with patch.object(rookie_adp.requests, "get", side_effect=RuntimeError("boom")):
        cfg = rookie_adp.AdpConfig(url="https://x", service_role_key="k")
        assert rookie_adp.fetch_latest("rookie_1qb", config=cfg) == {}


def test_fetch_latest_computes_trend_from_older_snapshot():
    cfg = rookie_adp.AdpConfig(url="https://x", service_role_key="k")
    responses = [
        [{"snapshot_date": "2026-09-20"}],
        [{"sleeper_id": "100", "adp": 3.0, "times_drafted": 20, "snapshot_date": "2026-09-20", "total_drafts": 50}],
        [{"sleeper_id": "100", "adp": 5.0, "snapshot_date": "2026-09-10"}],
    ]
    mocks = [Mock(status_code=200, json=Mock(return_value=r)) for r in responses]
    with patch.object(rookie_adp.requests, "get", side_effect=mocks):
        result = rookie_adp.fetch_latest("rookie_1qb", config=cfg)
    assert result["players"]["100"]["trend"] == -2.0
    assert rookie_adp.attribution("rookie_1qb", result)["source"] == "Fantasy Football Calculator"


def test_user_draft_aggregate_flag_defaults_off():
    assert rookie_adp.user_draft_aggregate_enabled(environ={}) is False
    assert rookie_adp.user_draft_aggregate_enabled(environ={"ADP_USER_DRAFT_AGGREGATE": "1"}) is True


def test_draft_kind_picks_format():
    assert rookie_adp.format_for_draft_kind("rookie") == "rookie_1qb"
    assert rookie_adp.format_for_draft_kind("startup") == "dynasty_1qb"


def test_api_adp_fields_are_none_without_data_and_real_with_it():
    assert api._adp_fields("1", 3, {})["adp"] is None
    fields = api._adp_fields("1", 3, {"1": {"adp": 8.0, "drafts": 30}})
    assert fields["adp"] == 8.0 and fields["adp_delta"] == 5.0 and fields["adp_verdict"] == "value"


def test_freshness_row_warns_never_fails(monkeypatch):
    monkeypatch.setattr(rookie_adp, "load_config", lambda **kw: rookie_adp.AdpConfig())
    row = data_freshness.adp_snapshot_row(1_000_000.0)
    assert row["status"] == "warn"
    monkeypatch.setattr(rookie_adp, "load_config", lambda **kw: rookie_adp.AdpConfig(url="u", service_role_key="k"))
    monkeypatch.setattr(rookie_adp, "newest_snapshot_date", lambda config=None: None)
    assert data_freshness.adp_snapshot_row(1_000_000.0)["status"] == "warn"
    monkeypatch.setattr(rookie_adp, "newest_snapshot_date", lambda config=None: "1970-01-12")
    assert data_freshness.adp_snapshot_row(12 * 86400 + 3600.0)["status"] == "ok"


def test_est_sf_moves_qbs_up_and_is_stable():
    players = {
        "rb": {"adp": 1.0}, "wr": {"adp": 2.0}, "qb1": {"adp": 5.0}, "te": {"adp": 6.0}, "qb2": {"adp": 9.0},
    }
    ratios = {"qb1": 3.0, "qb2": 3.0, "rb": 1.0, "wr": 1.0, "te": 1.0}
    est = rookie_adp.estimate_sf_adp(players, ratios)
    assert est["qb1"] < 5.0 and est["qb2"] < 9.0
    assert est["qb1"] == 2.0 and est["qb2"] == 6.0  # QBs take earlier real slots
    # same slot scale: the multiset of ADP values is unchanged
    assert sorted(est.values()) == sorted(p["adp"] for p in players.values())
    # non-QBs keep their relative order, and the result is deterministic
    assert est["rb"] < est["wr"] < est["te"]
    assert rookie_adp.estimate_sf_adp(players, ratios) == est
    # no ratios => identical to real 1QB ADP
    assert rookie_adp.estimate_sf_adp(players, {}) == {k: v["adp"] for k, v in players.items()}


def test_est_sf_only_in_superflex_leagues_and_labelled(monkeypatch):
    snap = {"players": {"q": {"adp": 6.0, "drafts": 20}, "r": {"adp": 1.0, "drafts": 20}, "w": {"adp": 3.0, "drafts": 20}}}
    monkeypatch.setattr(rookie_adp, "sf_value_ratios", lambda: {"q": 3.0})
    assert api._est_sf_map("1QB", snap) == {}
    est = api._est_sf_map("Superflex", snap)
    assert est["q"] == 3.0 and est["w"] == 6.0
    fields = api._adp_fields("q", 2, snap["players"], est)
    assert fields["adp"] == 6.0 and fields["adp_label"] == "1QB ADP"
    assert fields["adp_est_sf"] == 3.0 and fields["adp_est_sf_label"] == "Est. SF"
    assert api._adp_fields("q", 2, snap["players"], {})["adp_est_sf"] is None


def test_find_prospect_adp_matches_by_name_and_position_only_when_unambiguous():
    snap = {
        "as_of": "2027-04-20",
        "total_drafts": 40,
        "rows": [
            {"name": "Arch Manning", "position": "QB", "sleeper_id": None, "adp": 1.4, "adp_formatted": "1.04", "times_drafted": 38},
            {"name": "Sam Same", "position": "WR", "sleeper_id": None, "adp": 5.0},
            {"name": "Sam Same", "position": "WR", "sleeper_id": None, "adp": 7.0},
        ],
    }
    hit = rookie_adp.find_prospect_adp("Arch Manning Jr.", "QB", snapshot=snap)
    assert hit["adp"] == 1.4 and hit["label"] == "1QB ADP" and hit["source"]["as_of"] == "2027-04-20"
    assert rookie_adp.find_prospect_adp("Arch Manning", "WR", snapshot=snap) is None  # wrong position
    assert rookie_adp.find_prospect_adp("Sam Same", "WR", snapshot=snap) is None  # ambiguous: never guessed
    assert rookie_adp.find_prospect_adp("Arch Manning", "QB", snapshot={}) is None  # off-season: "No ADP yet"
