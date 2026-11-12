"""3-team trade ideas: search constraints, determinism, caps, gating, admission."""

from __future__ import annotations

import json
from unittest.mock import Mock, patch

import pytest

from modules import admission
from modules import multi_team_trade as mt
from modules import multi_team_trade_engine as engine
from modules import multi_team_trade_finder as finder
from modules import roster_value_model as rvm
from modules import sleeper
from tests.test_multi_team_trade import _auth, league  # noqa: F401  (fixture)
from tests.test_mobile_api_service import _client

NEEDS = {"1": ("WR",), "2": ("RB",), "3": ("QB",)}  # 1 gets WR from 3, 2 gets RB from 1, 3 gets QB from 2
BALANCED = ("F01-17", "F02-14", "F03-10")  # one RB / QB / WR priced equally so a fair cycle exists


def fake_needs(ctx, need_by_rid):
    by = {}
    for rid in ctx.by_rid:
        wants = need_by_rid.get(rid, ())
        by[rid] = {"positions": [
            {"position": pos, "tier": "primary" if pos in wants else "covered", "score": 1.0,
             "starters": {"QB": 1, "RB": 4, "WR": 3, "TE": 1}[pos], "surplus_player_ids": []}
            for pos in ("QB", "RB", "WR", "TE")
        ]}
    ctx._needs = rvm.LeagueNeeds(by_roster=by, status={})


@pytest.fixture()
def ctx(league):
    pl = league["players"]
    for pid in BALANCED:
        for col in ("dynasty_score", "value_score"):
            pl.loc[pl["player_id"].astype(str) == pid, col] = 4000.0
    built = engine.build_context(league_id="fixture-league", lens="Dynasty", players_db_path=":memory:")
    assert not isinstance(built, dict), built
    fake_needs(built, NEEDS)
    return built


def _find(ctx, **kw):
    return finder.find_three_team_ideas(ctx, "1", **kw)


def _says_yes(idea):
    return all(t["tone"] in finder.PASS_TONES for t in idea["teams"])


# --- the search -------------------------------------------------------------


def test_every_team_clears_fair_or_better_by_its_own_verdict(ctx):
    out = _find(ctx)
    assert out["status"] == "ok" and out["ideas"], out["search"]
    for idea in out["ideas"]:
        assert _says_yes(idea)
        assert len(idea["teams"]) == 3 and {t["roster_id"] for t in idea["teams"]} >= {"1"}
        assert idea["teams"][0]["roster_id"] == "1" and idea["teams"][0]["is_perspective"]
        # a closed cycle: everything sent is received by someone else in the deal
        sent = sorted((f["id"], f["to_roster_id"]) for f in idea["flows"])
        got = sorted((r["id"], t["roster_id"]) for t in idea["teams"] for r in t["receives"])
        assert sent == got
        assert idea["user"]["market_delta"] == idea["teams"][0]["market_delta"]
        for t in idea["teams"]:
            assert t["why"][0]["factor"] == "need" and {"flows", "market"} <= {w["factor"] for w in t["why"]}


def test_idea_matches_what_the_analyzer_says_about_the_same_trade(ctx):
    idea = _find(ctx)["ideas"][0]
    request = idea["analyzer_request"]
    graded = engine.analyze_multi_team_trade(
        league_id="fixture-league", transfers=request["transfers"], lens="Dynasty", players_db_path=":memory:",
        perspective_roster_id=request["perspective_roster_id"],
    )
    assert graded["status"] == "ok"
    by_rid = {t["roster_id"]: t for t in graded["teams"]}
    for t in idea["teams"]:
        assert by_rid[t["roster_id"]]["trade_score"] == t["trade_score"]
        assert by_rid[t["roster_id"]]["tone"] == t["tone"]


def test_sends_fit_the_receivers_needs_and_never_touch_untouchables(ctx):
    want = {"1": {"WR"}, "2": {"RB"}, "3": {"QB"}}
    ideas = _find(ctx)["ideas"]
    for idea in ideas:
        for t in idea["teams"]:
            assert {a["position"] for a in t["receives"]} <= want[t["roster_id"]]
    protected = {a["id"] for idea in ideas for a in idea["teams"][0]["sends"]}
    assert protected
    blocked = _find(ctx, untouchable_ids=protected)
    assert not (protected & {a["id"] for i in blocked["ideas"] for a in i["teams"][0]["sends"]})


def test_no_needs_means_no_ideas_and_no_engine_work(ctx):
    fake_needs(ctx, {})
    with patch.object(engine, "grade_transfers", side_effect=AssertionError("graded")):
        out = _find(ctx)
    assert out["ideas"] == [] and out["search"]["reason"] == "no_fit" and out["search"]["verified"] == 0


def test_small_league_and_unknown_roster_return_empty(ctx):
    assert finder.find_three_team_ideas(ctx, "99")["search"]["reason"] == "league_too_small"


def test_results_are_deterministic_and_ordered_by_weakest_team(ctx):
    first, second = _find(ctx), _find(ctx)
    assert json.dumps(first, sort_keys=True, default=str) == json.dumps(second, sort_keys=True, default=str)
    floors = [min(t["trade_score"] for t in i["teams"]) for i in first["ideas"]]
    assert floors == sorted(floors, reverse=True)
    assert len({i["id"] for i in first["ideas"]}) == len(first["ideas"])
    # the id is a function of the transfers only, whatever order they are listed in
    ts = [mt.Transfer(**{"asset_type": "player", "asset_id": "a", "from_roster": "1", "to_roster": "2"}),
          mt.Transfer("player", "b", "2", "3")]
    assert finder.idea_id(ts) == finder.idea_id(list(reversed(ts)))


def test_caps_bound_partners_candidates_and_verifications(ctx):
    graded = []
    real = engine.grade_transfers

    def spy(*a, **k):
        graded.append(1)
        return real(*a, **k)

    with patch.object(engine, "grade_transfers", side_effect=spy):
        out = _find(ctx, max_verify=1, max_ideas=5)
    assert out["search"]["verified"] == len(graded) <= 1 + finder.MAX_VARIANTS
    assert len(_find(ctx, max_ideas=1)["ideas"]) <= 1
    assert _find(ctx, max_partners=1)["search"]["partners"] == 1
    assert _find(ctx, max_partners=1)["ideas"] == []  # one partner can never close a 3-team cycle
    assert finder.MAX_PARTNERS <= 5 and finder.EDGE_ASSETS <= 3 and finder.MAX_VERIFY <= 12


def test_time_budget_stops_the_search_without_reordering(ctx):
    full = _find(ctx)
    ticks = iter([0.0, 0.0, 99.0, 99.0, 99.0, 99.0, 99.0])
    cut = _find(ctx, time_budget=1.0, clock=lambda: next(ticks, 99.0))
    assert cut["search"]["truncated"] is True and cut["search"]["verified"] <= 1
    assert [i["id"] for i in cut["ideas"]] == [i["id"] for i in full["ideas"]][: len(cut["ideas"])] or not cut["ideas"]
    none = _find(ctx, time_budget=0.0, clock=lambda: 5.0)
    assert none["ideas"] == [] and none["search"]["truncated"] is True and none["search"]["verified"] == 0


def test_per_pair_cap_limits_repeat_partners(ctx):
    out = _find(ctx)
    per_pair: dict[tuple, int] = {}
    for i in out["ideas"]:
        key = tuple(sorted(p["roster_id"] for p in i["partners"]))
        per_pair[key] = per_pair.get(key, 0) + 1
    assert max(per_pair.values()) <= finder.MAX_IDEAS_PER_PAIR


# --- counter variants ---------------------------------------------------------


def test_repair_adds_one_spare_piece_from_the_team_sending_to_the_short_team(ctx):
    league_view = finder._League(ctx, "1", set())
    base = (mt.Transfer("player", "F01-17", "1", "2"), mt.Transfer("player", "F02-14", "2", "3"),
            mt.Transfer("player", "F03-10", "3", "1"))
    short = {"teams": [
        {"roster_id": "1", "tone": "accept", "market_delta": 400},
        {"roster_id": "2", "tone": "counter", "market_delta": -450},
        {"roster_id": "3", "tone": "fair", "market_delta": 50},
    ]}
    fixed = finder._repair(league_view, short, base)
    assert fixed is not None and len(fixed) == len(base) + 1
    extra = fixed[-1]
    assert extra.to_roster == "2" and extra.from_roster == "1"  # the team that sends to the short team
    assert league_view.rows[extra.asset_id].position not in league_view.need_pos["1"]  # not a piece it needs
    assert extra.asset_id not in {t.asset_id for t in base}
    # two failing teams, or a decline, is not a one-edit problem
    two = {"teams": [dict(short["teams"][1]), dict(short["teams"][1], roster_id="3")]}
    assert finder._repair(league_view, two, base) is None
    assert finder._repair(league_view, {"teams": [dict(short["teams"][1], tone="decline")]}, base) is None


# --- draft picks as pieces ------------------------------------------------------

GROUPS = {"1": "contender", "2": "rebuild", "3": "retool"}


@pytest.fixture()
def pick_ctx(league):
    """The same league with the pick table loaded and postures pinned: 1 contends, 2 rebuilds, 3 retools."""

    pl = league["players"]
    for pid in BALANCED:
        for col in ("dynasty_score", "value_score"):
            pl.loc[pl["player_id"].astype(str) == pid, col] = 4000.0
    built = engine.build_context(league_id="fixture-league", lens="Dynasty", players_db_path=":memory:", load_picks=True)
    assert not isinstance(built, dict), built
    fake_needs(built, NEEDS)
    for rid in built.by_rid:
        group = GROUPS.get(rid, "retool")
        built._postures[rid] = {"key": group, "group": group, "label": group}
    for pick in built.pick_by_id.values():
        if str(pick["owner_roster_id"]) == "1":
            pick["score"] = 4000  # a pick priced like the balanced players
    return built


def _pick_transfers(idea):
    return [t for t in idea["analyzer_request"]["transfers"] if t["type"] == "pick"]


def test_picks_flow_by_posture_contenders_send_and_rebuilders_want(pick_ctx):
    view = finder._League(pick_ctx, "1", set())
    sends = {rid: [a for a in assets if a.kind == "pick"] for rid, assets in view.sendable.items()}
    assert sends["1"] and not sends["2"] and not sends["3"]  # only a contender spends picks
    assert all(a.player_id in pick_ctx.pick_by_id and a.roster_id == "1" for a in sends["1"])
    assert view.pick_want["2"] > view.pick_want["3"] > view.pick_want["1"] == 0.0
    assert [a for a in view.edge("1", "2") if a.kind == "pick"]  # wanted by the rebuilder
    assert not [a for a in view.edge("2", "1") if a.kind == "pick"]  # never sent by it
    assert len([a for a in view.edge("1", "2") if a.kind == "pick"]) <= finder.EDGE_PICKS
    # priced by the pick table the 2-team engine reads, not a number of the finder's own
    pick = next(a for a in sends["1"])
    assert pick.value == float(pick_ctx.pick_by_id[pick.player_id]["score"])


def test_candidates_carry_picks_within_the_caps(pick_ctx):
    view = finder._League(pick_ctx, "1", set())
    cands = finder._candidates(view, ["2", "3"])
    with_pick = [c for c in cands if any(t.asset_type == "pick" for t in c.transfers)]
    assert with_pick
    for c in cands:
        picks = [t for t in c.transfers if t.asset_type == "pick"]
        assert len(picks) <= finder.MAX_PICKS_PER_IDEA
        assert len({(t.from_roster, t.to_roster) for t in picks}) == len(picks)  # at most one per edge
        for t in picks:
            assert str(pick_ctx.pick_by_id[t.asset_id]["owner_roster_id"]) == t.from_roster
            assert view.group[t.from_roster] == "contender" and view.pick_want[t.to_roster] > 0


def test_ideas_with_picks_pass_every_teams_own_verdict_and_explain_the_pick(pick_ctx):
    out = finder.find_three_team_ideas(pick_ctx, "1")
    assert out["search"]["picks_in_play"] > 0
    pick_ideas = [i for i in out["ideas"] if _pick_transfers(i)]
    assert pick_ideas, out["search"]
    for idea in pick_ideas:
        assert _says_yes(idea)
        # the same grading the Analyzer's pipeline gives the same transfers
        again = engine.grade_transfers(
            pick_ctx, [mt.Transfer(t["type"], t["id"], t["from_roster_id"], t["to_roster_id"]) for t in idea["analyzer_request"]["transfers"]],
            perspective_roster_id="1",
        )
        assert {t["roster_id"]: t["tone"] for t in again["teams"]} == {t["roster_id"]: t["tone"] for t in idea["teams"]}
        for t in idea["teams"]:
            gets = [a for a in t["receives"] if a["type"] == "pick"]
            sent = [a for a in t["sends"] if a["type"] == "pick"]
            need = t["why"][0]["text"]
            if gets:
                assert t["posture"]["group"] in ("rebuild", "retool") and "draft capital" in need
            if sent:
                assert t["posture"]["group"] == "contender" and "draft capital a contender can spend" in need
        assert idea["veto"]["band"] in ("fair", "explainable")


def test_players_only_when_no_pick_table_is_loaded(ctx):
    out = _find(ctx)
    assert out["search"]["picks_in_play"] == 0
    assert not [i for i in out["ideas"] if _pick_transfers(i)]


def test_a_deal_the_veto_read_flags_is_dropped_even_when_every_verdict_is_fair(pick_ctx):
    assert _find(pick_ctx)["ideas"]
    flagged = {"outrage": 80.0, "band": "outrage", "label": "x", "explained_by_roster": False, "hurt_roster_id": "2"}
    with patch.object(engine.trade_veto, "assess", return_value=flagged):
        out = _find(pick_ctx)
    assert out["ideas"] == [] and out["search"]["vetoed"] > 0
    explainable = dict(flagged, band="explainable", outrage=25.0)
    with patch.object(engine.trade_veto, "assess", return_value=explainable):
        assert _find(pick_ctx)["ideas"]


def test_repair_may_add_a_pick_only_when_the_short_team_wants_draft_capital(pick_ctx):
    view = finder._League(pick_ctx, "1", set())
    base = (mt.Transfer("player", "F01-17", "1", "2"), mt.Transfer("player", "F02-14", "2", "3"),
            mt.Transfer("player", "F03-10", "3", "1"))
    short = {"teams": [
        {"roster_id": "1", "tone": "accept", "market_delta": 400},
        {"roster_id": "2", "tone": "counter", "market_delta": -4000},
        {"roster_id": "3", "tone": "fair", "market_delta": 50},
    ]}
    fixed = finder._repair(view, short, base)
    assert fixed is not None and fixed[-1].asset_type == "pick" and fixed[-1].to_roster == "2"
    assert str(pick_ctx.pick_by_id[fixed[-1].asset_id]["owner_roster_id"]) == "1"
    # a contender that is short does not get a pick it does not want; the repair stays a player
    short_contender = {"teams": [
        {"roster_id": "1", "tone": "counter", "market_delta": -4000},
        {"roster_id": "2", "tone": "fair", "market_delta": 50},
        {"roster_id": "3", "tone": "fair", "market_delta": 50},
    ]}
    fixed = finder._repair(view, short_contender, base)
    assert fixed is None or fixed[-1].asset_type == "player"


def test_endpoint_search_loads_picks_and_falls_back_to_players_when_the_pick_table_is_not_ready(monkeypatch):
    import services.mobile_api_service as svc

    built = []
    sentinel = object()

    def build_context(**kw):
        built.append(kw.get("load_picks", False))
        return {"status": "unavailable"} if kw.get("load_picks") else sentinel

    monkeypatch.setattr(engine, "build_context", build_context)
    monkeypatch.setattr(finder, "find_three_team_ideas", lambda ctx, rid, **k: {"ideas": [], "search": {"reason": "no_fit"}})
    monkeypatch.setattr(sleeper, "get_league", lambda lid: {"league_id": lid})
    monkeypatch.setattr(svc, "_fetch_gm_target_player_ids", lambda *a, **k: ([], []))
    monkeypatch.setattr(svc, "_multi_team_engine_hooks", lambda *a, **k: {})
    monkeypatch.setattr(svc.college_scouting, "class_strength_signal_enabled", lambda: False)
    monkeypatch.setattr(svc.auth_supabase, "get_supabase_config", lambda: None)
    out = svc._compute_multi_team_ideas("abc", "Dynasty", {"id": "u"}, {"roster_id": 1}, True)
    assert built == [True, False] and out["reason"] == "no_fit"


# --- API: Pro gate, caching, admission -----------------------------------------


def test_admission_puts_the_ideas_route_on_the_heavy_lane():
    assert admission.lane_for("/v1/leagues/1/trade-ideas/multi") == "heavy"
    assert admission.lane_for("/v1/leagues/1/trade-ideas/other") is None


def test_endpoint_requires_auth_and_a_known_lens(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/v1/leagues/abc/trade-ideas/multi").status_code == 401
    with patch("requests.get", side_effect=_auth()):
        r = client.get("/v1/leagues/abc/trade-ideas/multi?lens=Nope", headers={"Authorization": "Bearer t"})
    assert r.status_code == 422


IDEAS = [{"id": "m3-a", "teams": [], "analyzer_request": {"transfers": [], "perspective_roster_id": "1"}},
         {"id": "m3-b", "teams": [], "analyzer_request": {"transfers": [], "perspective_roster_id": "1"}}]


def _wire(monkeypatch, ideas):
    import services.mobile_api_service as svc

    client = _client(monkeypatch)
    calls = []
    monkeypatch.setattr(svc, "_resolve_my_roster", lambda user, lid: ({"roster_id": 1, "players": []}, ""))
    monkeypatch.setattr(sleeper, "get_league", lambda lid: {"league_id": lid, "settings": {}})
    monkeypatch.setattr(svc.league_calendar, "trade_window", lambda league: {"trade_deadline_passed": False})

    def compute(*a, **k):
        calls.append(a)
        return {"ok": True, "ideas": list(ideas), "reason": "" if ideas else "no_fit", "search": {"verified": 2}}

    monkeypatch.setattr(svc, "_compute_multi_team_ideas", compute)
    return svc, client, calls


def _get(client, entitlement):
    with patch("requests.get", side_effect=_auth(entitlement)):
        return client.get("/v1/leagues/abc/trade-ideas/multi", headers={"Authorization": "Bearer t"})


def test_pro_sees_ideas_and_free_sees_a_locked_count(monkeypatch):
    svc, client, _calls = _wire(monkeypatch, IDEAS)
    for pro in (True, False):
        monkeypatch.setattr(svc, "_is_pro_caller", lambda user, _p=pro: _p)
        r = _get(client, "pro" if pro else "free")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["idea_count"] == 2 and data["is_premium"] is pro
        if pro:
            assert [i["id"] for i in data["ideas"]] == ["m3-a", "m3-b"] and data["locked"] is False and data["upsell"] is None
        else:
            assert data["ideas"] == [] and data["locked"] is True and data["upsell"]["title"]
            assert "m3-a" not in json.dumps(data)  # nothing about the ideas leaks to Free


def test_free_with_no_ideas_is_not_shown_a_lock(monkeypatch):
    svc, client, _calls = _wire(monkeypatch, [])
    monkeypatch.setattr(svc, "_is_pro_caller", lambda user: False)
    data = _get(client, "free").json()
    assert data["idea_count"] == 0 and data["locked"] is False and data["reason"] == "no_fit"


def test_tiers_share_one_computation(monkeypatch):
    svc, client, calls = _wire(monkeypatch, IDEAS)
    seen = {}
    real = svc.redis_cache.redis_single_flight_cache

    def single_flight(**kw):
        seen["key"] = kw["cache_key"]
        seen["ttl"] = kw["ttl_seconds"]
        return real(**kw)

    monkeypatch.setattr(svc.redis_cache, "redis_single_flight_cache", single_flight)
    monkeypatch.setattr(svc, "_is_pro_caller", lambda user: False)
    assert _get(client, "free").status_code == 200
    # Free and Pro read the same cache key shape: the tier is not part of it.
    assert "free" not in seen["key"] and seen["ttl"] > 0
    assert len(calls) == 1
    assert calls[0][-1] is True  # the shared computation is never tier-specific


def test_deadline_passed_and_unlinked_roster_short_circuit(monkeypatch):
    svc, client, calls = _wire(monkeypatch, IDEAS)
    monkeypatch.setattr(svc.league_calendar, "trade_window", lambda league: {"trade_deadline_passed": True})
    data = _get(client, "pro").json()
    assert data["ideas"] == [] and data["reason"] == svc.league_calendar.TRADE_DEADLINE_PASSED_REASON and not calls
    monkeypatch.setattr(svc, "_resolve_my_roster", lambda user, lid: (None, "sleeper_not_linked"))
    assert _get(client, "pro").json()["reason"] == "sleeper_not_linked"
