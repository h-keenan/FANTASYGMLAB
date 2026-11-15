"""modules.derived_cache and the Desk memo seams built on it: exact reuse, exact invalidation."""

import gc
import threading

import pandas as pd
import pytest

from modules import derived_cache as dc


def test_fingerprint_is_stable_and_content_sensitive():
    a = {"b": [1, 2, {"c": {3, 1, 2}}], "a": (1.5, None, True), "x": float("nan")}
    assert dc.fingerprint(a, "x") == dc.fingerprint({"x": float("nan"), "a": (1.5, None, True), "b": [1, 2, {"c": {2, 3, 1}}]}, "x")
    assert dc.fingerprint(a) != dc.fingerprint({**a, "b": [1, 2, {"c": {3, 1}}]})
    assert dc.fingerprint(1) != dc.fingerprint("1") != dc.fingerprint(1.0)  # types stay distinct
    assert dc.fingerprint(0.0) != dc.fingerprint(-0.0)


def test_fingerprint_refuses_what_it_cannot_identify():
    for bad in (pd.DataFrame({"a": [1]}), object(), lambda: 1):
        with pytest.raises(dc.Unfingerprintable):
            dc.fingerprint(bad)


def test_memo_hits_misses_ttl_lru_and_private_copies():
    now = [0.0]
    memo = dc.Memo("t", max_entries=2, ttl_seconds=10, clock=lambda: now[0])
    calls = []

    def build(tag):
        def _b():
            calls.append(tag)
            return {"tag": tag, "rows": [1, 2]}
        return _b

    first = memo.get_or_compute("a", build("a"))
    second = memo.get_or_compute("a", build("a"))
    assert calls == ["a"] and first == second
    second["rows"].append(99)  # a caller decorating its copy never reaches the stored value
    assert memo.get_or_compute("a", build("a"))["rows"] == [1, 2]
    memo.get_or_compute("b", build("b"))
    memo.get_or_compute("c", build("c"))  # evicts the least recently used ("a")
    memo.get_or_compute("a", build("a2"))
    assert calls == ["a", "b", "c", "a2"]
    now[0] = 11.0  # past the TTL
    memo.get_or_compute("c", build("c2"))
    assert calls[-1] == "c2"


def test_memo_bypasses_without_a_key_when_disabled_and_never_stores_a_failure(monkeypatch):
    memo = dc.Memo("t")
    n = []
    assert memo.get_or_compute(None, lambda: n.append(1) or 1) == 1
    assert memo.get_or_compute(None, lambda: n.append(1) or 1) == 1
    assert len(n) == 2
    with pytest.raises(ValueError):
        memo.get_or_compute("k", lambda: (_ for _ in ()).throw(ValueError("boom")))
    assert memo.get_or_compute("k", lambda: "fine") == "fine"
    monkeypatch.setattr(dc, "ENABLED", False)
    seen = []
    memo.get_or_compute("k", lambda: seen.append(1) or "again")
    memo.get_or_compute("k", lambda: seen.append(1) or "again")
    assert len(seen) == 2


def test_memo_single_flight_computes_once_for_concurrent_callers():
    memo = dc.Memo("t")
    started, release, count = threading.Event(), threading.Event(), []

    def slow():
        count.append(1)
        started.set()
        release.wait(5)
        return [1]

    results = []
    threads = [threading.Thread(target=lambda: results.append(memo.get_or_compute("k", slow))) for _ in range(4)]
    for t in threads:
        t.start()
    started.wait(5)
    release.set()
    for t in threads:
        t.join(5)
    assert len(count) == 1 and results == [[1]] * 4


def test_frame_tags_follow_the_object_and_die_with_edits_or_gc():
    frame = pd.DataFrame({"player_id": ["1", "2"], "score": [5.0, 7.0]})
    dc.tag_frame(frame, "K")
    assert dc.frame_key(frame) == "K"
    assert dc.frame_key(frame.copy()) == "" and dc.frame_key(frame[frame["score"] > 1]) == ""
    frame["extra"] = 1  # a column added in place: no longer the tagged content
    assert dc.frame_key(frame) == ""
    other = dc.tag_frame(pd.DataFrame({"a": [1.0, 2.0]}), "M")
    other.loc[0, "a"] = 9.0  # numeric cell overwritten in place
    assert dc.frame_key(other) == ""
    third = dc.tag_frame(pd.DataFrame({"a": [1]}), "Z")
    del third
    gc.collect()
    assert not any(entry[1] == "Z" for entry in dc._FRAME_KEYS.values())


def test_derive_frame_key_needs_a_tagged_parent():
    parent = dc.tag_frame(pd.DataFrame({"a": [1]}), "P")
    child = dc.derive_frame_key(parent, pd.DataFrame({"a": [2]}), "op", 1)
    assert dc.frame_key(child) == dc.fingerprint("P", "op", 1)
    orphan = dc.derive_frame_key(pd.DataFrame({"a": [1]}), pd.DataFrame({"a": [2]}), "op")
    assert dc.frame_key(orphan) == ""


def _valued():
    return pd.DataFrame({
        "player_id": [str(i) for i in range(1, 9)],
        "name": [f"P{i}" for i in range(1, 9)],
        "position": ["QB", "RB", "WR", "TE", "RB", "WR", "WR", "QB"],
        "age": [24, 27, 22, 30, 25, 29, 33, 21],
        "dynasty_score": [9000, 7000, 6500, 4000, 3000, 2500, 1500, 1000],
        "value_score": [8000, 7000, 6000, 4100, 3100, 2600, 1600, 1100],
        "rebuild_score": [8500, 6000, 7000, 3000, 3500, 2000, 900, 1400],
    })


def test_strategy_adjusted_valued_matches_the_direct_transform_and_reuses_it():
    from modules import trade_hub_engine
    from services import mobile_api_service as svc

    svc._AGE_CURVE_MEMO.clear()
    base = dc.tag_frame(_valued(), "BASE")
    direct = trade_hub_engine.apply_strategy_age_curve(_valued(), "rebuild", "dynasty_score")
    first = svc._strategy_adjusted_valued(base, "rebuild", "dynasty_score")
    second = svc._strategy_adjusted_valued(base, "rebuild", "dynasty_score")
    pd.testing.assert_frame_equal(first, direct)
    pd.testing.assert_frame_equal(second, direct)
    assert second is not first and svc._AGE_CURVE_MEMO.hits == 1
    assert dc.frame_key(second) == dc.frame_key(first) != ""
    second["scratch"] = 1  # a private copy: editing it leaves the stored frame and the next caller untouched
    pd.testing.assert_frame_equal(svc._strategy_adjusted_valued(base, "rebuild", "dynasty_score"), direct)
    other = svc._strategy_adjusted_valued(base, "contender", "dynasty_score")
    assert dc.frame_key(other) != dc.frame_key(first)  # a different strategy is a different key
    untagged = svc._strategy_adjusted_valued(_valued(), "rebuild", "dynasty_score")
    pd.testing.assert_frame_equal(untagged, direct)
    assert dc.frame_key(untagged) == ""


def test_league_waiver_pool_reuses_only_for_identical_tagged_inputs(monkeypatch):
    from modules import trade_grade
    from services import mobile_api_service as svc

    svc._LEAGUE_POOL_MEMO.clear()
    rosters = [{"roster_id": 1, "players": ["1", "2"]}, {"roster_id": 2, "players": ["3"]}]
    state = {"rosters": rosters}
    computed = []

    def fake_pool(rs, valued):
        computed.append([r["players"] for r in rs])
        rostered = {p for r in rs for p in r["players"]}
        return valued[~valued["player_id"].isin(rostered)]

    monkeypatch.setattr(svc.sleeper, "get_rosters", lambda league_id: state["rosters"])
    monkeypatch.setattr(trade_grade, "league_waiver_pool", fake_pool)
    valued = dc.tag_frame(_valued(), "V1")

    a = svc._league_waiver_pool("L1", valued)
    b = svc._league_waiver_pool("L1", valued)
    assert len(computed) == 1 and list(a["player_id"]) == list(b["player_id"]) and a is not b
    state["rosters"] = [{"roster_id": 1, "players": ["1", "2", "4"]}, {"roster_id": 2, "players": ["3"]}]  # a transaction
    c = svc._league_waiver_pool("L1", valued)
    assert len(computed) == 2 and "4" not in set(c["player_id"])
    svc._league_waiver_pool("L1", _valued())  # untagged: always computed
    svc._league_waiver_pool("L1", _valued())
    assert len(computed) == 4
    valued["player_id"] = valued["player_id"]  # no-op edit keeps the tag
    edited = valued.copy()
    edited.loc[0, "dynasty_score"] = 1
    dc.tag_frame(edited, "V1")
    edited.loc[1, "dynasty_score"] = 2  # edited in place after tagging: the tag no longer matches, so it recomputes
    svc._league_waiver_pool("L1", edited)
    assert len(computed) == 5


def test_waiver_bundle_is_reused_for_identical_inputs_and_rebuilt_on_any_change(monkeypatch):
    from modules import roster_value_model, trade_grade, trade_hub_engine
    from services import mobile_api_service as svc

    svc._WAIVER_BUNDLE_MEMO.clear()
    builds = []
    posture = {"key": "retool", "model_status": {"degraded": False, "reasons": []}}
    monkeypatch.setattr(svc, "_resolve_trade_posture", lambda *a, **k: dict(posture))
    monkeypatch.setattr(trade_grade, "season_window", lambda settings: ("window", 1))
    monkeypatch.setattr(trade_hub_engine, "apply_strategy_age_curve", lambda df, strategy, field: df)
    monkeypatch.setattr(svc, "_attach_projection_ppg", lambda valued, pool, ids, field, lineup_settings=None: (valued, pool))

    class Ctx:
        model_ctx = object()

    def build_context(**kwargs):
        builds.append(1)
        return Ctx()

    monkeypatch.setattr(roster_value_model, "build_context", build_context)
    monkeypatch.setattr(roster_value_model, "league_position_table", lambda *a, **k: {"table": True})

    valued, pool = dc.tag_frame(_valued(), "V"), dc.tag_frame(_valued().assign(stale_free_agent=False), "FA")
    mine = {"roster_id": 1, "players": ["1", "2"]}
    rosters = [mine, {"roster_id": 2, "players": ["3"]}]
    league = {"league_id": "L", "settings": {"leg": 4}}

    def call(**over):
        args = dict(user={"id": "u"}, league_id="L", league=league, settings={"x": 1}, valued=valued, free_agents=pool,
                    my_roster=mine, rosters=rosters, lens="Dynasty", score_field="dynasty_score", config={})
        args.update(over)
        return svc._waiver_roster_value_bundle(**args)

    first, second = call(), call()
    assert len(builds) == 1 and first["rvc"] is second["rvc"] and first["league_table"] == {"table": True}
    call(my_roster={"roster_id": 1, "players": ["1", "2", "4"]})  # my roster changed
    call(rosters=[mine, {"roster_id": 2, "players": ["3", "5"]}])  # someone else's roster changed
    call(league={**league, "settings": {"leg": 5}})  # the league moved a week
    call(settings={"x": 2})  # scoring/lineup settings
    call(lens="Redraft")
    call(valued=dc.tag_frame(_valued(), "V2"))  # a new cached pool entry
    posture["key"] = "rebuild"
    call()  # the user's posture changed
    assert len(builds) == 8
    call(valued=_valued())  # an untagged frame never reuses anything
    call(valued=_valued())
    assert len(builds) == 10


def test_attach_projection_ppg_memoized_reuses_identical_requests_and_keeps_frame_attrs(monkeypatch):
    from modules import model_status
    from services import mobile_api_service as svc

    svc._ATTACH_MEMO.clear()
    calls = []

    def fake_attach(valued, pool, ids, score_field, lineup_settings=None):
        calls.append(sorted(ids))
        out = valued.copy()
        out["proj_ppg"] = 1.5
        return model_status.mark_frame(out, "projection_baselines_failed"), pool

    monkeypatch.setattr(svc, "_attach_projection_ppg", fake_attach)
    valued = dc.tag_frame(_valued(), "V")
    pool = dc.tag_frame(_valued().iloc[:3].copy(), "P")
    first = svc._attach_projection_ppg_memoized(valued, pool, {"1", "2"}, "dynasty_score", {"scoring": 1})
    again = svc._attach_projection_ppg_memoized(valued, pool, {"2", "1"}, "dynasty_score", {"scoring": 1})
    assert len(calls) == 1
    pd.testing.assert_frame_equal(first[0], again[0])
    assert model_status.frame_codes(again[0]) == model_status.frame_codes(first[0]) == ["projection_baselines_failed"]
    assert again[0] is not first[0] and dc.frame_key(again[0]) == dc.frame_key(first[0]) != ""
    svc._attach_projection_ppg_memoized(valued, pool, {"1", "3"}, "dynasty_score", {"scoring": 1})  # different asked-for ids
    svc._attach_projection_ppg_memoized(valued, pool, {"1", "2"}, "dynasty_score", {"scoring": 2})  # different scoring
    svc._attach_projection_ppg_memoized(valued, None, {"1", "2"}, "dynasty_score", {"scoring": 1})  # no pool
    assert len(calls) == 4
    svc._attach_projection_ppg_memoized(_valued(), pool, {"1"}, "dynasty_score", None)  # untagged frame: always computed
    svc._attach_projection_ppg_memoized(_valued(), pool, {"1"}, "dynasty_score", None)
    assert len(calls) == 6


def test_league_needs_memoized_carries_the_callers_status_like_the_function_does(monkeypatch):
    from modules import model_status, roster_value_model
    from services import mobile_api_service as svc

    svc._LEAGUE_NEEDS_MEMO.clear()
    runs = []

    def fake_needs(*, valued, rosters, league, settings, score_field, status=None, **_):
        runs.append(1)
        out = model_status.merge(status)
        model_status.add(out, "need_model_failed")
        return roster_value_model.LeagueNeeds(by_roster={"1": {"headline": "x"}}, status=out)

    monkeypatch.setattr(roster_value_model, "league_needs", fake_needs)
    valued = dc.tag_frame(_valued(), "V")
    rosters = [{"roster_id": 1, "players": ["1"]}]
    args = dict(valued=valued, rosters=rosters, league={"l": 1}, settings={"s": 1}, score_field="dynasty_score")
    caller = model_status.ok()
    model_status.add(caller, "projection_baselines_failed")
    first = svc._league_needs_memoized(status=caller, **args)
    second = svc._league_needs_memoized(status=model_status.ok(), **args)
    assert len(runs) == 1
    assert model_status.codes(first.status) == ["projection_baselines_failed", "need_model_failed"]
    assert model_status.codes(second.status) == ["need_model_failed"]  # no leakage from the first caller's status
    assert first.for_roster(1) == second.for_roster(1) == {"headline": "x"}
    second.for_roster(1)["headline"] = "edited"
    assert svc._league_needs_memoized(status=model_status.ok(), **args).for_roster(1)["headline"] == "x"
    svc._league_needs_memoized(status=model_status.ok(), **{**args, "rosters": [{"roster_id": 1, "players": ["1", "2"]}]})
    assert len(runs) == 2
