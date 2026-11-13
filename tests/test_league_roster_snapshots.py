from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from modules import league_roster_snapshots as lrs

LEAGUE = {"season": "2026", "status": "in_season", "settings": {"draft_rounds": 4}}


def _rosters(starters=("1", "2"), extra="9"):
    return [
        {"roster_id": 2, "owner_id": "b", "players": ["5", "6", "7", extra], "starters": ["5", "0"], "reserve": ["6"], "taxi": ["7"]},
        {"roster_id": 1, "owner_id": "a", "players": ["1", "2", "3"], "starters": list(starters), "reserve": None, "taxi": None},
    ]


def test_compact_roster_buckets_sorted_and_placeholder_dropped():
    c = lrs.compact_roster(_rosters()[0])
    assert c == {"r": 2, "o": "b", "st": ["5"], "bn": ["9"], "ir": ["6"], "tx": ["7"]}
    assert lrs.compact_roster({"owner_id": "x"}) is None


def test_compact_rosters_sorted_by_roster_id():
    assert [r["r"] for r in lrs.compact_rosters(_rosters())] == [1, 2]


def test_hash_stable_and_sensitive():
    a = lrs.build_document(LEAGUE, _rosters())
    b = lrs.build_document(LEAGUE, list(reversed(_rosters())))
    assert a["content_hash"] == b["content_hash"]  # input order irrelevant
    c = lrs.build_document(LEAGUE, _rosters(extra="10"))
    assert a["content_hash"] != c["content_hash"]
    d = lrs.build_document(LEAGUE, _rosters(), [{"season": "2027", "round": 1, "roster_id": 1, "owner_id": 2}])
    assert a["content_hash"] != d["content_hash"]


def test_build_document_requires_rosters_and_season():
    assert lrs.build_document(LEAGUE, []) is None
    assert lrs.build_document({"status": "x"}, _rosters()) is None
    assert lrs.build_document({}, _rosters()) is None


def test_picks_ledger_and_ownership():
    traded = [
        {"season": "2027", "round": 1, "roster_id": 1, "owner_id": 2},
        {"season": "2027", "round": 2, "roster_id": 2, "owner_id": 2},  # not actually traded
        {"season": "2025", "round": 1, "roster_id": 1, "owner_id": 2},  # before league season: dropped
    ]
    doc = lrs.build_document(LEAGUE, _rosters(), traded)
    assert doc["picks"] == {"rounds": 4, "traded": [[2027, 1, 1, 2]]}
    mine = lrs.picks_owned(doc["picks"], 2, [2027], [1, 2])
    assert (2027, 1, 1) in mine and (2027, 1, 2) in mine and len(mine) == 5
    assert (2027, 1, 1) not in lrs.picks_owned(doc["picks"], 1, [2027], [1, 2])
    assert lrs.picks_owned({"rounds": 0, "traded": []}, 1, [2027], [1]) == []


def test_plan_row_dedupes_only_on_equal_hash():
    doc = lrs.build_document(LEAGUE, _rosters())
    full = lrs.plan_row(league_id="L", week=3, slot="post_waivers", document=doc, previous=None, captured_at="t")
    assert full["unchanged"] is False and full["rosters"] and full["picks"] is not None
    same = lrs.plan_row(league_id="L", week=3, slot="post_waivers", document=doc, previous={"content_hash": doc["content_hash"]}, captured_at="t")
    assert same["unchanged"] is True and same["rosters"] is None and same["picks"] is None
    other = lrs.plan_row(league_id="L", week=3, slot="post_waivers", document=doc, previous={"content_hash": "zzz"}, captured_at="t")
    assert other["unchanged"] is False


def test_pick_previous_same_season_only():
    rows = [
        {"season": 2025, "week": 18, "slot": "pre_kickoff", "content_hash": "old"},
        {"season": 2026, "week": 1, "slot": "pre_kickoff", "content_hash": "a"},
        {"season": 2026, "week": 2, "slot": "post_waivers", "content_hash": "b"},
    ]
    assert lrs.pick_previous(rows, season=2026, week=2, slot="pre_kickoff")["content_hash"] == "b"
    assert lrs.pick_previous(rows, season=2026, week=2, slot="post_waivers")["content_hash"] == "a"
    assert lrs.pick_previous(rows, season=2026, week=1, slot="pre_kickoff") is None  # never crosses seasons


def _store(rows_spec):
    rows = []
    for week, slot, rosters_marker in rows_spec:
        unchanged = rosters_marker is None
        rows.append({
            "league_id": "L", "season": 2026, "week": week, "slot": slot, "captured_at": f"w{week}{slot}",
            "content_hash": rosters_marker or "same", "unchanged": unchanged, "league_status": "in_season",
            "rosters": None if unchanged else [{"r": 1, "marker": rosters_marker}], "picks": None if unchanged else {"rounds": 4, "traded": []},
        })
    return rows


def test_resolve_carries_forward_unchanged_and_flags_exactness():
    rows = _store([(1, "pre_kickoff", "A"), (2, "post_waivers", None), (3, "post_waivers", "B"), (3, "pre_kickoff", None)])
    s = lrs.resolve_roster_snapshot(rows, 2026, 2)
    assert s["rosters"][0]["marker"] == "A" and s["week"] == 2 and s["exact"]
    s = lrs.resolve_roster_snapshot(rows, 2026, 3, "post_waivers")
    assert s["rosters"][0]["marker"] == "B"
    s = lrs.resolve_roster_snapshot(rows, 2026, 3)  # later slot wins
    assert s["slot"] == "pre_kickoff" and s["rosters"][0]["marker"] == "B"
    s = lrs.resolve_roster_snapshot(rows, 2026, 7)  # nothing for week 7: latest earlier, not exact
    assert s["week"] == 3 and not s["exact"]
    assert lrs.resolve_roster_snapshot(rows, 2026, 0) is None
    assert lrs.resolve_roster_snapshot(rows, 2025, 5) is None


def test_resolve_season_start_prefers_week1_pre_kickoff():
    rows = _store([(0, "post_waivers", "OFF"), (1, "pre_kickoff", "WK1"), (2, "post_waivers", "WK2")])
    assert lrs.resolve_season_start(rows, 2026)["rosters"][0]["marker"] == "WK1"
    assert lrs.resolve_season_start(_store([(0, "post_waivers", "OFF")]), 2026)["rosters"][0]["marker"] == "OFF"
    assert lrs.resolve_season_start([], 2026) is None


def test_sharding_partitions_exactly_and_is_stable():
    ids = [str(100000 + i) for i in range(500)]
    parts = [lrs.shard_leagues(ids, 4, i) for i in range(4)]
    assert sorted(sum(parts, [])) == sorted(ids)
    assert all(len(p) > 60 for p in parts)
    assert lrs.shard_leagues(ids, 4, 2) == parts[2]
    assert lrs.shard_leagues(ids, 1, 0) == ids


def test_load_shard_rejects_bad_values():
    assert lrs.load_shard(environ={"ROSTER_SNAPSHOT_SHARDS": "4", "ROSTER_SNAPSHOT_SHARD_INDEX": "3"}) == (4, 3)
    assert lrs.load_shard(environ={"ROSTER_SNAPSHOT_SHARDS": "4", "ROSTER_SNAPSHOT_SHARD_INDEX": "4"}) == (1, 0)
    assert lrs.load_shard(environ={"ROSTER_SNAPSHOT_SHARDS": "abc"}) == (1, 0)
    assert lrs.load_shard(environ={"ROSTER_SNAPSHOT_SHARDS": "99"}) == (1, 0)


def test_visit_order_stable_per_slot_but_rotates():
    ids = [str(i) for i in range(50)]
    a = lrs.visit_order(ids, season=2026, week=3, slot="post_waivers")
    assert a == lrs.visit_order(ids, season=2026, week=3, slot="post_waivers")
    assert a != lrs.visit_order(ids, season=2026, week=4, slot="post_waivers")


def test_slot_scheduling_helpers():
    assert lrs.auto_slot(datetime(2026, 11, 8, 15, tzinfo=timezone.utc)) == "pre_kickoff"  # Sunday
    assert lrs.auto_slot(datetime(2026, 11, 11, 12, tzinfo=timezone.utc)) == "post_waivers"  # Wednesday
    assert lrs.snapshot_week("regular", 9) == 9 and lrs.snapshot_week("offseason", None) == 0
    assert lrs.snapshot_week("pre", 1) == 0
    assert lrs.slot_applies("pre_kickoff", "offseason") is False
    assert lrs.slot_applies("post_waivers", "offseason") is True


def test_distinct_league_ids_drops_external_and_blank():
    rows = [{"league_id": "1"}, {"league_id": "1"}, {"league_id": "espn:5:2026"}, {"league_id": ""}, {"league_id": "mfl:1"}, {"league_id": "2"}]
    assert lrs.distinct_league_ids(rows) == ["1", "2"]


def test_throttle_spaces_calls():
    t = [0.0]
    slept = []
    th = lrs.CallThrottle(60, clock=lambda: t[0], sleep=lambda s: (slept.append(s), t.__setitem__(0, t[0] + s)))
    th.wait(); th.wait(); th.wait()
    assert slept == [1.0, 1.0]  # 1 call/sec


class FakeSleeper:
    def __init__(self, leagues, fail=()):
        self.leagues, self.fail, self.calls = leagues, set(fail), []

    def get_league(self, lid):
        self.calls.append(("league", lid))
        return {} if lid in self.fail else dict(LEAGUE)

    def get_rosters(self, lid):
        self.calls.append(("rosters", lid))
        return _rosters(extra=self.leagues.get(lid, "9"))

    def get_traded_picks(self, lid):
        return []


def _clock(phase="regular", week=9, season=2026):
    return lambda: SimpleNamespace(season=season, phase=phase, week=week)


ENV = {"SUPABASE_URL": "http://x", "SUPABASE_SERVICE_ROLE_KEY": "k"}
NOW = datetime(2026, 11, 11, 12, 17, tzinfo=timezone.utc)


def _sweep(monkeypatch, api, ids, recent=None, **kw):
    written = []
    monkeypatch.setattr(lrs, "fetch_recent_rows", lambda c, ids_, now: recent or {})
    monkeypatch.setattr(lrs, "write_rows", lambda c, rows: (written.extend(rows) or (len(rows), [])))
    stats = lrs.run_sweep(now=NOW, environ={**ENV, **kw.pop("env", {})}, sleeper_api=api, clock_fn=kw.pop("clock_fn", _clock()), league_ids=ids,
                          sleep=lambda s: None, **kw)
    return stats, written


def test_sweep_writes_full_rows_first_then_unchanged(monkeypatch):
    api = FakeSleeper({})
    stats, rows = _sweep(monkeypatch, api, ["10", "11"])
    assert stats["ok"] and stats["full_rows"] == 2 and all(r["rosters"] for r in rows)
    assert {r["slot"] for r in rows} == {"post_waivers"} and rows[0]["week"] == 9
    prev = {r["league_id"]: [{"season": 2026, "week": 8, "slot": "pre_kickoff", "content_hash": r["content_hash"]}] for r in rows}
    stats2, rows2 = _sweep(monkeypatch, FakeSleeper({}), ["10", "11"], recent=prev)
    assert stats2["unchanged_rows"] == 2 and all(r["rosters"] is None for r in rows2)


def test_sweep_changed_roster_writes_full_row(monkeypatch):
    base_hash = lrs.build_document(LEAGUE, _rosters())["content_hash"]
    prev = {"10": [{"season": 2026, "week": 8, "slot": "pre_kickoff", "content_hash": base_hash}]}
    stats, rows = _sweep(monkeypatch, FakeSleeper({"10": "77"}), ["10"], recent=prev)
    assert stats["full_rows"] == 1 and rows[0]["unchanged"] is False


def test_sweep_resumes_skipping_done_leagues_unless_forced(monkeypatch):
    done = {"10": [{"season": 2026, "week": 9, "slot": "post_waivers", "content_hash": "h"}]}
    api = FakeSleeper({})
    stats, rows = _sweep(monkeypatch, api, ["10", "11"], recent=done)
    assert stats["already_done"] == 1 and [r["league_id"] for r in rows] == ["11"]
    stats, rows = _sweep(monkeypatch, FakeSleeper({}), ["10", "11"], recent=done, force=True)
    assert len(rows) == 2


def test_sweep_dry_run_never_writes(monkeypatch):
    called = []
    monkeypatch.setattr(lrs, "fetch_recent_rows", lambda c, i, now: {})
    monkeypatch.setattr(lrs, "write_rows", lambda c, r: called.append(r) or (0, []))
    stats = lrs.run_sweep(now=NOW, environ=ENV, sleeper_api=FakeSleeper({}), clock_fn=_clock(), league_ids=["1"], dry_run=True, sleep=lambda s: None)
    assert stats["snapshotted"] == 1 and not called and stats["rows_written"] == 0


def test_sweep_skips_inapplicable_slot_and_stale_leagues(monkeypatch):
    stats, rows = _sweep(monkeypatch, FakeSleeper({}), ["1"], slot="pre_kickoff", clock_fn=_clock("offseason", None))
    assert "does not apply" in stats["skipped"] and not rows
    stale = lambda: SimpleNamespace(season=2027, phase="regular", week=2)  # league payload says 2026
    stats, rows = _sweep(monkeypatch, FakeSleeper({}), ["1"], clock_fn=stale)
    assert stats["skipped_stale"] == 1 and not rows


def test_sweep_circuit_breaker_and_failure_alarm(monkeypatch):
    ids = [str(i) for i in range(30)]
    api = FakeSleeper({}, fail=ids)
    stats, rows = _sweep(monkeypatch, api, ids, probe=lambda lid: "sleeper_http_503")
    assert stats["circuit_open"] and stats["ok"] is False and not rows and stats["failed"] == lrs.CIRCUIT_BREAKER_FAILURES


def test_sweep_time_budget_and_shard(monkeypatch):
    ids = [str(i) for i in range(40)]
    stats, rows = _sweep(monkeypatch, FakeSleeper({}), ids, env={"ROSTER_SNAPSHOT_SHARDS": "2", "ROSTER_SNAPSHOT_SHARD_INDEX": "1"})
    assert stats["leagues_in_shard"] == len(lrs.shard_leagues(ids, 2, 1)) == len(rows)
    stats, rows = _sweep(monkeypatch, FakeSleeper({}), ids, env={"ROSTER_SNAPSHOT_TIME_BUDGET_SECONDS": "0.0000001"})
    assert stats["snapshotted"] + stats["skipped_budget"] == 40


def test_sweep_disable_and_unconfigured(monkeypatch):
    stats, rows = _sweep(monkeypatch, FakeSleeper({}), ["1"], env={"ROSTER_SNAPSHOT_DISABLE": "1"})
    assert stats["skipped"] == "disabled" and not rows
    stats = lrs.run_sweep(now=NOW, environ={"SUPABASE_URL": "", "SUPABASE_SERVICE_ROLE_KEY": ""}, clock_fn=_clock())
    assert stats["ok"] is False


def test_no_pii_columns_in_rows(monkeypatch):
    _, rows = _sweep(monkeypatch, FakeSleeper({}), ["1"])
    assert set(rows[0]) == {"league_id", "season", "week", "slot", "captured_at", "content_hash", "unchanged", "league_status", "rosters", "picks"}


def test_league_ref_truncates_and_classify_probe():
    assert lrs.league_ref("1124841399277105152") == "112484...152"
    assert lrs.league_ref("123") == "123"
    assert lrs.classify_probe(404, None) == "league_not_found"
    assert lrs.classify_probe(200, None) == "league_not_found"  # Sleeper: 200 + null for deleted leagues
    assert lrs.classify_probe(200, {"league_id": "1"}) == lrs.REASON_TRANSIENT
    assert lrs.classify_probe(429, None) == "sleeper_http_429"
    assert lrs.classify_probe(None, None) == "sleeper_unreachable"


def test_deleted_league_is_skipped_with_reason_not_failed(monkeypatch, capsys):
    api = FakeSleeper({}, fail=["1124841399277105152"])
    stats, rows = _sweep(monkeypatch, api, ["1124841399277105152", "11"], probe=lambda lid: "league_not_found")
    assert stats["skipped_gone"] == 1 and stats["failed"] == 0 and stats["ok"] is True
    assert stats["skipped_leagues"] == [{"league": "112484...152", "reason": "league_not_found"}]
    assert stats["errors"] == [] and stats["snapshotted"] == 1
    assert "skip 112484...152: league_not_found" in capsys.readouterr().err


def test_many_deleted_leagues_never_trip_breaker_or_alert(monkeypatch):
    ids = [str(100000 + i) for i in range(40)]
    stats, _ = _sweep(monkeypatch, FakeSleeper({}, fail=ids), ids, probe=lambda lid: "league_not_found")
    assert stats["ok"] and not stats["circuit_open"] and stats["skipped_gone"] == 40


def test_transient_failure_reported_with_reason_and_counts_as_failure(monkeypatch):
    stats, _ = _sweep(monkeypatch, FakeSleeper({}, fail=["99"]), ["99", "11"], probe=lambda lid: "sleeper_http_429")
    assert stats["failed"] == 1 and stats["errors"] == ["99: sleeper_http_429"]


def test_exception_reason_and_stale_reason(monkeypatch):
    class Boom(FakeSleeper):
        def get_rosters(self, lid):
            raise ValueError("x")

    stats, _ = _sweep(monkeypatch, Boom({}), ["5"])
    assert stats["errors"] == ["5: exception:ValueError"]
    stale = lambda: SimpleNamespace(season=2027, phase="regular", week=2)
    stats, _ = _sweep(monkeypatch, FakeSleeper({}), ["5"], clock_fn=stale)
    assert stats["skipped_leagues"][0]["reason"] == "season_mismatch_previous_season_league: league=2026 clock=2027"


def test_empty_rosters_and_unreadable_season_reasons(monkeypatch):
    class NoRosters(FakeSleeper):
        def get_rosters(self, lid):
            return []

    stats, _ = _sweep(monkeypatch, NoRosters({}), ["5"])
    assert stats["errors"] == ["5: rosters_empty"]

    class NoSeason(FakeSleeper):
        def get_league(self, lid):
            return {"status": "x"}

    stats, _ = _sweep(monkeypatch, NoSeason({}), ["5"])
    assert stats["errors"] == ["5: league_season_unreadable"]


def test_read_failure_reason_includes_status(monkeypatch):
    class R:
        status_code = 500

    monkeypatch.setattr(lrs.requests, "get", lambda *a, **k: R())
    cfg = lrs.SnapshotConfig("http://x", "k")
    assert lrs.fetch_saved_league_ids(cfg) is None
    assert lrs.last_get_error() == "saved_leagues: HTTP 500"
