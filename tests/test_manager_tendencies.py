"""Manager Tendencies: evidence-backed per-manager reads off real Sleeper
transaction history, with every signal withheld below its minimum sample."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from modules import manager_tendencies as mt

TS_2025 = int(datetime(2025, 9, 1, tzinfo=timezone.utc).timestamp() * 1000)
TS_2024 = int(datetime(2024, 9, 1, tzinfo=timezone.utc).timestamp() * 1000)

# Ages on 2025-09-01: young (22-23), veterans (29-30).
PLAYERS = {
    "y_wr1": {"full_name": "Young WR One", "position": "WR", "birth_date": "2003-01-01"},
    "y_wr2": {"full_name": "Young WR Two", "position": "WR", "birth_date": "2002-06-01"},
    "y_wr3": {"full_name": "Young WR Three", "position": "WR", "birth_date": "2003-03-01"},
    "y_rb1": {"full_name": "Young RB One", "position": "RB", "birth_date": "2002-02-01"},
    "y_rb2": {"full_name": "Young RB Two", "position": "RB", "birth_date": "2003-02-01"},
    "v_wr1": {"full_name": "Vet WR One", "position": "WR", "birth_date": "1995-01-01"},
    "v_wr2": {"full_name": "Vet WR Two", "position": "WR", "birth_date": "1996-01-01"},
    "v_wr3": {"full_name": "Vet WR Three", "position": "WR", "birth_date": "1995-06-01"},
    "v_rb1": {"full_name": "Vet RB One", "position": "RB", "birth_date": "1996-01-01"},
    "v_rb2": {"full_name": "Vet RB Two", "position": "RB", "birth_date": "1995-05-01"},
    "v_rb3": {"full_name": "Vet RB Three", "position": "RB", "birth_date": "1996-03-01"},
    "fa1": {"full_name": "Wire Guy One", "position": "WR", "birth_date": "2001-01-01"},
    "fa2": {"full_name": "Wire Guy Two", "position": "RB", "birth_date": "2001-01-01"},
    "fa3": {"full_name": "Wire Guy Three", "position": "TE", "birth_date": "2001-01-01"},
}


def _trade(tx_id, ts, adds, drops, picks=(), creator="", week=1, budget=()):
    roster_ids = sorted(
        set(adds.values())
        | set(drops.values())
        | {p["owner_id"] for p in picks}
        | {p["previous_owner_id"] for p in picks}
    )
    return {
        "transaction_id": tx_id,
        "type": "trade",
        "status": "complete",
        "leg": week,
        "status_updated": ts,
        "creator": creator,
        "roster_ids": roster_ids,
        "adds": dict(adds) or None,
        "drops": dict(drops) or None,
        "draft_picks": list(picks),
        "waiver_budget": list(budget),
        "settings": None,
    }


def _pick(season, rnd, to_roster, from_roster, original=None):
    return {
        "season": season,
        "round": rnd,
        "roster_id": original or from_roster,
        "owner_id": to_roster,
        "previous_owner_id": from_roster,
    }


def _wire(tx_id, ts, roster_id, player_id, *, bid=None, kind="waiver", week=2):
    settings = {"seq": 0}
    if bid is not None:
        settings["waiver_bid"] = bid
    return {
        "transaction_id": tx_id,
        "type": kind,
        "status": "complete",
        "leg": week,
        "status_updated": ts,
        "roster_ids": [roster_id],
        "adds": {player_id: roster_id},
        "drops": None,
        "draft_picks": [],
        "waiver_budget": [],
        "settings": settings,
    }


def _league(league_id, season, previous, *, status="in_season", waiver_type=2, budget=100):
    return {
        "league_id": league_id,
        "season": season,
        "status": status,
        "previous_league_id": previous,
        "settings": {
            "leg": 2,
            "last_scored_leg": 2,
            "waiver_type": waiver_type,
            "waiver_budget": budget,
            "draft_rounds": 4,
        },
    }


def _season(league_id, season, previous, owners, transactions, **league_kwargs):
    league = _league(league_id, season, previous, **league_kwargs)
    by_week: dict[int, list] = {}
    for tx in transactions:
        by_week.setdefault(int(tx.get("leg") or 1), []).append(tx)
    rosters = [{"roster_id": rid, "owner_id": owner, "metadata": {}} for rid, owner in owners.items()]
    users = [
        {"user_id": owner, "username": f"user_{owner}", "display_name": f"Team {owner}", "metadata": {}}
        for owner in owners.values()
        if owner
    ]
    return mt.load_season(
        league_id,
        fetch_league=lambda _lid: league,
        fetch_transactions=lambda _lid, week: by_week.get(week, []),
        fetch_rosters=lambda _lid: rosters,
        fetch_users=lambda _lid: users,
    )


OWNERS = {1: "u1", 2: "u2", 3: "u3", 4: "u4"}


def _profile(transactions, owners=OWNERS, prior=None):
    seasons = [_season("L2025", "2025", "L2024" if prior else "L2023", owners, transactions)]
    if prior:
        seasons.append(prior)
    return mt.build_league_tendencies(seasons, PLAYERS)


def _rebuilder_trades():
    """Roster 1 sells veterans for young players and future picks, five
    times, never sending a first."""

    return [
        _trade("t1", TS_2025, {"v_rb1": 2, "y_wr1": 1}, {"v_rb1": 1, "y_wr1": 2}, creator="u2"),
        _trade(
            "t2", TS_2025, {"v_wr1": 3}, {"v_wr1": 1}, picks=[_pick("2026", 1, 1, 3)], creator="u3"
        ),
        _trade(
            "t3",
            TS_2025,
            {"v_rb2": 2, "y_wr2": 1},
            {"v_rb2": 1, "y_wr2": 2},
            picks=[_pick("2026", 2, 1, 2)],
            creator="u1",
        ),
        _trade("t4", TS_2025, {"v_wr2": 4, "y_rb1": 1}, {"v_wr2": 1, "y_rb1": 4}, creator="u4"),
        _trade(
            "t5",
            TS_2025,
            {"v_rb3": 2, "v_wr3": 2, "y_wr3": 1},
            {"v_rb3": 1, "v_wr3": 1, "y_wr3": 2},
            picks=[_pick("2027", 2, 1, 2)],
            creator="u2",
        ),
    ]


# --- Minimum-sample withholding --------------------------------------------


def test_two_trades_is_not_a_tendency_every_trade_signal_is_withheld():
    trades = [
        _trade("a", TS_2025, {"v_rb1": 2, "y_wr1": 1}, {"v_rb1": 1, "y_wr1": 2}),
        _trade("b", TS_2025, {"v_wr1": 3}, {"v_wr1": 1}, picks=[_pick("2026", 1, 1, 3)]),
    ]
    manager = _profile(trades)["managers"][1]
    signals = manager["signals"]
    for key in ("position_preference", "age_preference", "pick_behavior", "package_shape", "posture", "trade_partners"):
        assert signals[key]["status"] == mt.INSUFFICIENT, key
        assert signals[key]["label"] is None
        assert signals[key]["value"] is None
        assert signals[key]["sample_size"] == 2
        assert signals[key]["min_sample"] == mt.MIN_TRADES
        assert "Not enough" in signals[key]["summary"]
    # The evidence is still attached, so the UI can show what does exist.
    assert set(signals["package_shape"]["evidence"]) == {"a", "b"}
    assert manager["headline"].startswith("Not enough trades yet (2 trades)")


def test_trade_frequency_is_withheld_until_the_league_itself_has_trades():
    trades = [_trade("a", TS_2025, {"v_rb1": 2}, {"v_rb1": 1})]
    signal = _profile(trades)["managers"][1]["signals"]["trade_frequency"]
    assert signal["status"] == mt.INSUFFICIENT
    assert signal["min_sample"] == mt.MIN_LEAGUE_TRADES_FOR_FREQUENCY
    assert "1 trade league-wide" in signal["summary"]


def test_age_preference_needs_aged_players_on_both_sides():
    # Three trades, but roster 1 only ever receives picks: no ages acquired.
    trades = [
        _trade("a", TS_2025, {"v_rb1": 2}, {"v_rb1": 1}, picks=[_pick("2026", 2, 1, 2)]),
        _trade("b", TS_2025, {"v_wr1": 3}, {"v_wr1": 1}, picks=[_pick("2026", 3, 1, 3)]),
        _trade("c", TS_2025, {"v_rb2": 4}, {"v_rb2": 1}, picks=[_pick("2027", 2, 1, 4)]),
    ]
    signal = _profile(trades)["managers"][1]["signals"]["age_preference"]
    assert signal["status"] == mt.INSUFFICIENT
    assert signal["min_sample"] == mt.MIN_AGED_PLAYERS_EACH_SIDE
    assert "0 acquired, 3 given up" in signal["summary"]


def test_waiver_activity_is_withheld_in_a_league_with_almost_no_wire_moves():
    wire = [_wire("w1", TS_2025, 1, "fa1", bid=10)]
    signal = _profile(wire)["managers"][1]["signals"]["waiver_activity"]
    assert signal["status"] == mt.INSUFFICIENT
    assert signal["evidence"] == ["w1"]


def test_never_traded_a_first_needs_five_trades_not_three():
    trades = _rebuilder_trades()[:3]
    picks = _profile(trades)["managers"][1]["signals"]["pick_behavior"]
    assert picks["status"] == mt.OK
    assert picks["value"]["never_traded_a_first"] is False


# --- Signals off real trade legs --------------------------------------------


def test_rebuilder_profile_reads_posture_age_picks_and_positions_from_the_trades():
    profile = _profile(_rebuilder_trades())
    manager = profile["managers"][1]
    signals = manager["signals"]

    posture = signals["posture"]
    assert posture["status"] == mt.OK
    assert posture["label"] == "rebuilding"
    assert posture["value"]["rebuild_leaning"] == 5
    assert "May be receptive to rebuilding offers" in posture["summary"]

    age = signals["age_preference"]
    assert age["label"] == "acquires_younger"
    assert age["value"]["acquired_avg_age"] < age["value"]["sent_avg_age"]

    picks = signals["pick_behavior"]
    assert picks["label"] == "buys_picks"
    assert picks["value"]["picks_acquired"] == 3
    assert picks["value"]["picks_sent"] == 0
    assert picks["value"]["firsts_acquired"] == 1
    assert picks["value"]["never_traded_a_first"] is True
    assert set(picks["evidence"]) == {"t2", "t3", "t5"}

    positions = signals["position_preference"]["value"]["by_position"]
    assert positions["RB"] == {"acquired": 1, "sent": 3, "net": -2}
    assert positions["WR"] == {"acquired": 3, "sent": 3, "net": 0}
    assert signals["position_preference"]["value"]["sells"] == ["RB"]

    assert manager["headline"] == "Leaning rebuild lately. Moves RBs out."

    # Every evidence id resolves to a real trade record with both sides.
    detail = mt.manager_detail(profile, 1)
    assert set(detail["transactions"]) == {"t1", "t2", "t3", "t4", "t5"}
    t2 = detail["transactions"]["t2"]
    mine = next(side for side in t2["sides"] if side["roster_id"] == 1)
    assert [a["name"] for a in mine["sent"]] == ["Vet WR One"]
    assert [a["label"] for a in mine["received"]] == ["2026 1st"]


def test_package_shape_counts_two_for_one_consolidations_and_who_proposed():
    trades = [
        _trade("c1", TS_2025, {"v_wr1": 1, "y_wr1": 2, "y_wr2": 2}, {"v_wr1": 2, "y_wr1": 1, "y_wr2": 1}, creator="u2"),
        _trade("c2", TS_2025, {"v_rb1": 1, "y_rb1": 3, "y_rb2": 3}, {"v_rb1": 3, "y_rb1": 1, "y_rb2": 1}, creator="u1"),
        _trade("c3", TS_2025, {"v_wr2": 1, "y_wr3": 4, "fa1": 4}, {"v_wr2": 4, "y_wr3": 1, "fa1": 1}, creator="u4"),
    ]
    shape = _profile(trades)["managers"][1]["signals"]["package_shape"]
    assert shape["label"] == "consolidates"
    assert shape["value"]["by_shape"] == {"2-for-1": 3}
    assert shape["value"]["accepted_from_others"] == 2
    assert shape["value"]["proposed"] == 1
    assert "3 2-for-1 consolidations" in shape["summary"]
    # The other sides of the same trades split.
    assert _profile(trades)["managers"][2]["signals"]["package_shape"]["status"] == mt.INSUFFICIENT


def test_trade_partners_and_frequency_vs_league():
    trades = _rebuilder_trades() + [
        _trade("x1", TS_2025, {"fa1": 3}, {"fa1": 2}),
    ]
    signals = _profile(trades)["managers"][1]["signals"]
    partners = signals["trade_partners"]
    assert partners["label"] == "has_frequent_partners"
    top = partners["value"]["partners"][0]
    assert top["owner_id"] == "u2" and top["trades"] == 3
    assert sorted(top["evidence"]) == ["t1", "t3", "t5"]

    freq = signals["trade_frequency"]
    assert freq["status"] == mt.OK
    # 6 trades x 2 sides over 4 manager-seasons = 3.0 league rate; roster 1 has 5.
    assert freq["value"]["league_trades_per_season"] == 3.0
    assert freq["value"]["trades"] == 5


def test_startup_draft_pick_swaps_are_not_counted_as_pick_behavior():
    # First season (no previous league), same-season picks and deep startup
    # rounds are startup-draft swaps, not future picks.
    league_season = _season(
        "L2025",
        "2025",
        "",
        OWNERS,
        [
            _trade("s1", TS_2025, {}, {}, picks=[_pick("2025", 1, 1, 2), _pick("2025", 3, 2, 1)]),
            _trade("s2", TS_2025, {}, {}, picks=[_pick("2026", 17, 1, 3), _pick("2026", 2, 3, 1)]),
            _trade("s3", TS_2025, {"v_rb1": 1}, {"v_rb1": 4}, picks=[_pick("2026", 1, 4, 1)]),
        ],
    )
    picks = mt.build_league_tendencies([league_season], PLAYERS)["managers"][1]["signals"]["pick_behavior"]
    assert picks["status"] == mt.OK
    assert picks["value"]["picks_acquired"] == 0
    assert [p["label"] for p in picks["value"]["sent"]] == ["2026 2nd", "2026 1st"]
    assert picks["value"]["firsts_sent"] == 1


def test_a_past_season_owned_by_someone_else_is_not_attributed_to_the_current_owner():
    prior = _season(
        "L2024",
        "2024",
        "",
        {1: "previous_owner", 2: "u2", 3: "u3", 4: "u4"},
        [
            _trade("old1", TS_2024, {"v_rb1": 2}, {"v_rb1": 1}),
            _trade("old2", TS_2024, {"v_rb2": 3}, {"v_rb2": 1}),
            _trade("old3", TS_2024, {"v_wr1": 4}, {"v_wr1": 1}),
        ],
        status="complete",
    )
    profile = _profile([_trade("new1", TS_2025, {"v_wr2": 2}, {"v_wr2": 1})], prior=prior)
    manager = profile["managers"][1]
    assert manager["seasons_included"] == ["2025"]
    assert manager["seasons_excluded"] == ["2024"]
    assert manager["sample"]["trades"] == 1
    assert "old1" not in manager["signals"]["package_shape"]["evidence"]
    # Roster 2's owner was present both seasons, so both count for them.
    assert profile["managers"][2]["seasons_included"] == ["2025", "2024"]


def test_faab_aggressiveness_is_relative_to_league_spend():
    wire = []
    for i in range(6):
        wire.append(_wire(f"big{i}", TS_2025, 1, "fa1", bid=12))
    for i in range(14):
        wire.append(_wire(f"small{i}", TS_2025, 2 + (i % 3), "fa2", bid=1))
    signal = _profile(wire)["managers"][1]["signals"]["waiver_activity"]
    assert signal["status"] == mt.OK
    faab = signal["value"]["faab"]
    assert faab["label"] == "aggressive_faab"
    assert faab["winning_bids"] == 6
    assert faab["average_share_of_budget_spent"] == 0.72
    assert "Spends FAAB aggressively" in signal["summary"]
    assert signal["value"]["ratio_to_league"] == 1.2


def test_orphan_roster_gets_no_manager_history():
    owners = {1: "u1", 2: "u2", 3: "", 4: "u4"}
    manager = _profile(_rebuilder_trades(), owners=owners)["managers"][3]
    assert manager["status"] == mt.INSUFFICIENT
    assert all(s["status"] == mt.INSUFFICIENT for s in manager["signals"].values())


def test_league_summary_is_compact():
    rows = mt.league_summary(_profile(_rebuilder_trades()))
    assert [r["roster_id"] for r in rows] == [1, 2, 3, 4]
    assert rows[0]["labels"]["posture"] == "rebuilding"
    assert "evidence" not in rows[0]


# --- Sleeper cost and caching ----------------------------------------------


def test_chain_walk_reads_one_transactions_call_per_week_and_caches(monkeypatch):
    leagues = {
        "L2025": _league("L2025", "2025", "L2024"),
        "L2024": {**_league("L2024", "2024", "", status="complete"), "settings": {"last_scored_leg": 17, "playoff_week_start": 15}},
    }
    tx_calls: list[tuple[str, int]] = []

    def fake_transactions(league_id, week):
        tx_calls.append((league_id, week))
        return []

    monkeypatch.setattr(mt.sleeper, "get_league", lambda lid: leagues.get(lid, {}))
    monkeypatch.setattr(mt.sleeper, "get_transactions", fake_transactions)
    monkeypatch.setattr(mt.sleeper, "get_rosters", lambda lid: [{"roster_id": 1, "owner_id": "u1"}])
    monkeypatch.setattr(mt.sleeper, "get_users", lambda lid: [{"user_id": "u1", "username": "one"}])
    players = Mock(return_value=PLAYERS)
    monkeypatch.setattr(mt.sleeper, "get_players", players)

    first = mt.league_tendencies_cached("L2025")
    # In-season 2025: weeks 1..2; completed 2024: 1..18 (playoffs + 3, capped).
    assert sorted(set(w for lid, w in tx_calls if lid == "L2025")) == [1, 2]
    assert len([c for c in tx_calls if c[0] == "L2024"]) == 18
    assert len(tx_calls) == 20
    assert [s["season"] for s in first["seasons"]] == ["2025", "2024"]

    tx_calls.clear()
    second = mt.league_tendencies_cached("L2025")
    assert tx_calls == []
    assert second == first
    assert players.call_count == 1


def test_completed_past_seasons_get_the_long_ttl_and_the_head_season_the_short_one():
    assert mt._season_ttl("complete", is_head=False) == mt.SEASON_TTL_COMPLETE_SECONDS
    assert mt._season_ttl("complete", is_head=True) == mt.SEASON_TTL_CURRENT_SECONDS
    assert mt._season_ttl("in_season", is_head=False) == mt.SEASON_TTL_CURRENT_SECONDS


# --- API --------------------------------------------------------------------


def _client(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")
    from services import mobile_api_service

    return TestClient(mobile_api_service.app)


def _auth(entitlement):
    auth_user_response = Mock(status_code=200)
    auth_user_response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = [{"entitlement": entitlement, "sleeper_username": "gm"}]
    return [auth_user_response, profile_response]


@pytest.fixture
def profile_stub(monkeypatch):
    profile = _profile(_rebuilder_trades())
    stub = Mock(return_value=profile)
    monkeypatch.setattr(mt, "league_tendencies_cached", stub)
    monkeypatch.setattr("modules.sleeper.get_league", lambda *a, **kw: {"status": "in_season"})
    return stub


def test_tendency_routes_require_auth(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/v1/leagues/abc/managers/tendencies").status_code == 401
    assert client.get("/v1/leagues/abc/managers/1/tendencies").status_code == 401


@pytest.mark.parametrize("path", ["/v1/leagues/abc/managers/tendencies", "/v1/leagues/abc/managers/1/tendencies"])
def test_free_tier_gets_the_upsell_and_never_triggers_the_scan(monkeypatch, profile_stub, path):
    client = _client(monkeypatch)
    with patch("requests.get", side_effect=_auth("free")):
        response = client.get(path, headers={"Authorization": "Bearer good-token"})
    assert response.status_code == 200
    body = response.json()
    assert body["is_premium"] is False
    assert body["upsell"]["title"]
    profile_stub.assert_not_called()


def test_premium_summary_and_detail(monkeypatch, profile_stub):
    client = _client(monkeypatch)
    with patch("requests.get", side_effect=_auth("premium")):
        summary = client.get("/v1/leagues/abc/managers/tendencies", headers={"Authorization": "Bearer good-token"})
    body = summary.json()
    assert summary.status_code == 200
    assert body["is_premium"] is True
    assert body["managers"][0]["headline"] == "Leaning rebuild lately. Moves RBs out."

    with patch("requests.get", side_effect=_auth("premium")):
        detail = client.get("/v1/leagues/abc/managers/1/tendencies", headers={"Authorization": "Bearer good-token"})
    body = detail.json()
    assert detail.status_code == 200
    assert body["manager"]["signals"]["posture"]["label"] == "rebuilding"
    assert "t2" in body["transactions"]
    assert body["thresholds"]["min_trades"] == mt.MIN_TRADES

    with patch("requests.get", side_effect=_auth("premium")):
        missing = client.get("/v1/leagues/abc/managers/99/tendencies", headers={"Authorization": "Bearer good-token"})
    assert missing.status_code == 404
