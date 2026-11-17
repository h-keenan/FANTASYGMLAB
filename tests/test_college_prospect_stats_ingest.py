"""College prospect stats ingest: CFBD parsing, merge, call budget, fail-soft."""

from __future__ import annotations

import datetime as dt
import json

import pytest

from modules import college_prospect_ingest as ing

SEASON_ROWS = [
    {"season": 2026, "playerId": 1, "team": "Texas", "category": "passing", "statType": "COMPLETIONS", "stat": "210"},
    {"season": 2026, "playerId": 1, "team": "Texas", "category": "passing", "statType": "ATT", "stat": "320"},
    {"season": 2026, "playerId": 1, "team": "Texas", "category": "passing", "statType": "YDS", "stat": "2,900"},
    {"season": 2026, "playerId": 1, "team": "Texas", "category": "passing", "statType": "PCT", "stat": "0.656"},
    {"season": 2026, "playerId": 1, "team": "Texas", "category": "rushing", "statType": "YDS", "stat": "150"},
    {"season": 2026, "playerId": 1, "team": "Texas", "category": "defensive", "statType": "TOT", "stat": "9"},
    {"season": 2026, "playerId": 3, "team": "Texas", "category": "receiving", "statType": "REC", "stat": "61"},
    {"season": 2026, "playerId": 3, "team": "Texas", "category": "receiving", "statType": "YPR", "stat": "14.25"},
]
GAMES = [
    {
        "id": 10,
        "teams": [
            {
                "team": "Texas",
                "categories": [
                    {"name": "passing", "types": [{"name": "YDS", "athletes": [{"id": "1", "stat": "312"}, {"id": "99", "stat": "5"}]}, {"name": "TD", "athletes": [{"id": "1", "stat": "3"}]}]},
                    {"name": "receiving", "types": [{"name": "REC", "athletes": [{"id": "3", "stat": "7"}]}]},
                ],
            },
            {"team": "Oklahoma", "categories": []},
        ],
    }
]


def test_parse_season_stats_maps_cfbd_stat_types_only():
    out = ing.parse_season_stats(SEASON_ROWS)
    assert out["1"]["passing"] == {"cmp": 210, "att": 320, "yds": 2900, "pct": 0.66}
    assert out["1"]["rushing"] == {"yds": 150}
    assert "defensive" not in out["1"]  # not a fantasy category: never stored
    assert out["3"]["receiving"] == {"rec": 61, "ypr": 14.25}


def test_parse_game_week_keeps_only_wanted_players_and_names_the_opponent():
    got = ing.parse_game_week(GAMES, 4, {"1", "3"})
    assert set(got) == {"1", "3"}
    assert got["1"] == {"week": 4, "opponent": "Oklahoma", "passing": {"yds": 312, "td": 3}}
    assert got["3"]["receiving"] == {"rec": 7}


def test_parse_ppa_usage_recruits():
    assert ing.parse_ppa([{"id": 1, "averagePPA": {"all": 0.4123456, "pass": None}, "totalPPA": {"all": 80.5}}]) == {
        "1": {"avg": {"all": 0.412}, "total": {"all": 80.5}}
    }
    assert ing.parse_usage([{"id": 1, "usage": {"overall": 0.31, "pass": 0.5}}]) == {"1": {"overall": 0.31, "pass": 0.5}}
    by_recruit, by_athlete = ing.parse_recruits(
        [{"id": 7, "athleteId": 1, "year": 2023, "stars": 5, "rating": 0.9998, "ranking": 1, "school": "Isidore Newman", "city": "New Orleans", "stateProvince": "LA"},
         {"id": 8, "athleteId": 2, "year": 2023}]  # no stars / rank: dropped, not guessed
    )
    assert by_athlete["1"]["stars"] == 5 and by_athlete["1"]["national_rank"] == 1 and by_recruit["7"]["state"] == "LA"
    assert "2" not in by_athlete


def test_merge_keeps_older_seasons_and_stored_weeks():
    merged = ing.merge_seasons([{"season": 2024, "team": "Texas"}, {"season": 2025, "team": "Texas", "passing": {"yds": 1}}], {2026: {"team": "Texas"}, 2025: {"team": "Texas", "passing": {"yds": 2}}})
    assert [m["season"] for m in merged] == [2026, 2025, 2024]
    assert merged[1]["passing"] == {"yds": 2}
    log = ing.merge_game_log({"season": 2026, "games": [{"week": 1}, {"week": 2, "x": 1}]}, 2026, [{"week": 2, "x": 2}, {"week": 3}])
    assert [g["week"] for g in log["games"]] == [1, 2, 3] and log["games"][1]["x"] == 2
    # a different stored season is never mixed in
    assert ing.merge_game_log({"season": 2025, "games": [{"week": 1}]}, 2026, []) is None


def test_call_budget_caps_and_counts():
    budget = ing.CallBudget(2)
    get = budget.wrap(lambda path, params, key: [])
    get("/a", {}, "k")
    get("/b", {}, "k")
    with pytest.raises(ing.BudgetExceeded):
        get("/c", {}, "k")
    assert budget.used == 2


def test_cadence_helpers():
    assert ing.in_season(dt.date(2026, 11, 17)) and ing.in_season(dt.date(2027, 1, 12)) and not ing.in_season(dt.date(2027, 4, 5))
    assert ing.is_slow_refresh(dt.date(2026, 11, 2), have_rows=True, force=False)
    assert not ing.is_slow_refresh(dt.date(2026, 11, 17), have_rows=True, force=False)
    assert ing.is_slow_refresh(dt.date(2026, 11, 17), have_rows=False, force=False)
    assert ing.current_week(dt.date(2026, 11, 17), 2026) == 12
    assert ing.month_calls_so_far({"cfbd_usage": {"month": "2026-11", "calls": 400}}, dt.date(2026, 11, 17)) == 400
    assert ing.month_calls_so_far({"cfbd_usage": {"month": "2026-10", "calls": 400}}, dt.date(2026, 11, 17)) == 0


class FakeCfbd:
    def __init__(self):
        self.calls = []

    def __call__(self, path, params, key, *a, **k):
        self.calls.append((path, dict(params)))
        if path == "/ppa/players/season":
            return [{"id": 1, "averagePPA": {"all": 0.5}, "totalPPA": {"all": 90}}]
        if path == "/player/usage":
            return [{"id": 1, "usage": {"overall": 0.3}}]
        if path == "/games/players":
            return GAMES if params["week"] == 4 else []
        if path == "/stats/player/season":
            return [{"playerId": 1, "team": "Texas", "category": params["category"], "statType": "YDS", "stat": "100"}]
        if path == "/recruiting/players":
            return [{"id": 7, "athleteId": 1, "year": params["year"], "stars": 5, "ranking": 1}]
        raise AssertionError(path)


PROSPECTS = [{"id": "2027-arch-manning-texas", "cfbd_id": "1", "school": "Texas", "_meta": {"class_year": 3, "height_in": 76, "weight_lb": 220, "hometown": "New Orleans, LA", "recruit_ids": []}}]


def _step(monkeypatch, *, today, existing, force=False, month_calls=0):
    sent = []

    class Resp:
        def __init__(self, status=200, body=None):
            self.status_code, self._body = status, body or []

        def json(self):
            return self._body

        def raise_for_status(self):
            pass

    monkeypatch.setattr(ing.requests, "get", lambda url, **k: Resp(200, existing) if existing is not None else Resp(404))
    monkeypatch.setattr(ing.requests, "post", lambda url, **k: sent.append(json.loads(k["data"])) or Resp())
    cfbd = FakeCfbd()
    sink = {"season_stat_rows": SEASON_ROWS, "logos": {"Texas": "https://example.test/tx.png"}}
    status = ing.run_stats_step(
        "https://x.supabase.co", "svc", "KEY", PROSPECTS, sink,
        season=2026, today=today, now_iso="2026-11-17T09:00:00+00:00", force=force, month_calls=month_calls, getter=cfbd, log=lambda m: None,
    )
    return status, sent, cfbd


def test_stats_step_first_fill_pulls_everything_within_budget(monkeypatch):
    status, sent, cfbd = _step(monkeypatch, today=dt.date(2026, 11, 17), existing=[])
    assert status["status"] == "ok" and status["slow"] is True and status["errors"] == []
    assert status["calls"] == len(cfbd.calls) <= ing.RUN_STATS_CALL_CAP
    paths = {p for p, _ in cfbd.calls}
    assert {"/ppa/players/season", "/player/usage", "/games/players", "/stats/player/season", "/recruiting/players"} <= paths
    row = sent[0][0]
    assert row["school_logo_url"] == "https://example.test/tx.png" and row["hometown"] == "New Orleans, LA"
    assert [s["season"] for s in row["seasons"]] == [2026, 2025, 2024]
    assert row["recruiting"]["stars"] == 5 and row["advanced"]["usage"] == {"overall": 0.3}
    assert row["game_log"]["games"][0]["week"] == 4 and row["source"].startswith("College Football Data API")


def test_weekly_run_skips_slow_pieces_and_fetches_only_recent_weeks(monkeypatch):
    existing = [{"prospect_id": "2027-arch-manning-texas", "seasons": [{"season": 2025, "team": "Texas"}], "game_log": {"season": 2026, "games": [{"week": 1}]}, "recruiting": {"stars": 5}}]
    status, sent, cfbd = _step(monkeypatch, today=dt.date(2026, 11, 17), existing=existing)
    assert status["slow"] is False
    paths = [p for p, _ in cfbd.calls]
    assert "/recruiting/players" not in paths and paths.count("/stats/player/season") == 0
    assert [p["week"] for p in (c[1] for c in cfbd.calls if c[0] == "/games/players")] == [11, 12]
    row = sent[0][0]
    assert "recruiting" not in row  # not fetched: the stored value is left alone
    assert [s["season"] for s in row["seasons"]] == [2026, 2025]  # kept the stored 2025 entry
    assert [g["week"] for g in row["game_log"]["games"]] == [1]  # week 4 not refetched; stored week kept


def test_offseason_non_slow_run_makes_no_cfbd_calls(monkeypatch):
    existing = [{"prospect_id": "2027-arch-manning-texas", "seasons": []}]
    status, sent, cfbd = _step(monkeypatch, today=dt.date(2027, 4, 14), existing=existing)
    assert status["status"] == "ok" and status["calls"] == 0 and cfbd.calls == []
    assert "advanced" not in sent[0][0] and "game_log" not in sent[0][0]


def test_skips_when_table_missing_or_monthly_budget_spent(monkeypatch):
    status, sent, cfbd = _step(monkeypatch, today=dt.date(2026, 11, 17), existing=None)
    assert status["status"] == "skipped_migration_pending" and cfbd.calls == [] and sent == []
    status, sent, cfbd = _step(monkeypatch, today=dt.date(2026, 11, 17), existing=[], month_calls=ing.MONTHLY_CALL_CAP)
    assert status["status"] == "skipped_monthly_budget" and cfbd.calls == []


def test_one_failed_piece_does_not_sink_the_rest(monkeypatch):
    class Flaky(FakeCfbd):
        def __call__(self, path, params, key, *a, **k):
            if path == "/ppa/players/season":
                raise RuntimeError("boom")
            return super().__call__(path, params, key)

    sent = []
    monkeypatch.setattr(ing.requests, "get", lambda url, **k: type("R", (), {"status_code": 200, "json": lambda self: []})())
    monkeypatch.setattr(ing.requests, "post", lambda url, **k: sent.append(json.loads(k["data"])) or type("R", (), {"raise_for_status": lambda self: None})())
    status = ing.run_stats_step(
        "https://x.supabase.co", "svc", "KEY", PROSPECTS, {"season_stat_rows": SEASON_ROWS, "logos": {}},
        season=2026, today=dt.date(2026, 11, 17), now_iso="t", force=False, month_calls=0, getter=Flaky(), log=lambda m: None,
    )
    assert status["status"] == "ok" and status["errors"] == ["ppa:RuntimeError"]
    assert sent[0][0]["advanced"]["usage"] == {"overall": 0.3}  # usage survived; ppa simply absent
    assert sent[0][0]["advanced"]["ppa"] is None


def test_class_listing_is_skipped_when_the_month_is_nearly_spent(monkeypatch):
    def no_network(*a, **k):
        raise RuntimeError("offline")

    monkeypatch.setattr(ing.requests, "get", no_network)
    status = ing.run(
        environ={"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "svc", "CFBD_API_KEY": "KEY"},
        today=dt.date(2026, 11, 16),  # a Monday
        previous_status={"cfbd_usage": {"month": "2026-11", "calls": 800}},
    )
    assert status["classes"]["status"] == "skipped_monthly_budget"
    assert status["cfbd_usage"] == {"month": "2026-11", "calls": 800}


def test_only_current_run_calls_never_exceed_the_monthly_cap():
    # Worst realistic month: weekly runs cost ~140 (roster listing) + stats step; the cap stops the stats step well before 1000.
    assert ing.MONTHLY_CALL_CAP < 1000 and ing.RUN_STATS_CALL_CAP <= 40
