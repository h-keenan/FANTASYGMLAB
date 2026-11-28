"""modules.roster_pct_history: idempotent write, prune, trend with gaps. No live calls."""

from datetime import date
from unittest.mock import Mock, patch

import pandas as pd

from modules import roster_pct_history as rph

CFG = rph.Config(url="https://example.supabase.co", service_role_key="k")
TODAY = date(2026, 11, 19)


def _ok():
    return Mock(status_code=201, text="")


def test_build_rows_and_idempotent_daily_write():
    pcts = {"1": {"percent": 88.5}, "2": {"percent": 4.0}, "3": {"percent": 150}}
    rows = rph.build_rows(pcts, {"1": {"count": 900}}, snapshot_date="2026-11-19")
    assert [r["player_id"] for r in rows] == ["1", "2"]
    assert rows[0]["sleeper_trending_adds"] == 900 and rows[1]["sleeper_trending_adds"] is None
    with patch.object(rph.requests, "post", return_value=_ok()) as post:
        first = rph.store_daily_snapshot(CFG, rows)
        second = rph.store_daily_snapshot(CFG, rows)
    assert first["ok"] and second["ok"]
    for call in post.call_args_list:
        assert call.kwargs["params"] == {"on_conflict": "player_id,source,snapshot_date"}
        assert "merge-duplicates" in call.kwargs["headers"]["Prefer"]


def test_store_fails_soft_when_unconfigured_or_empty():
    assert not rph.store_daily_snapshot(rph.Config(), [{"a": 1}])["ok"]
    assert not rph.store_daily_snapshot(CFG, [])["ok"]


def test_prune_uses_400_day_cutoff():
    with patch.object(rph.requests, "delete", return_value=_ok()) as delete:
        stats = rph.prune_old_snapshots(CFG, today=TODAY)
    assert stats["ok"] and stats["cutoff"] == "2025-10-15"
    assert delete.call_args.kwargs["params"] == {"snapshot_date": "lt.2025-10-15"}


def _r(day, pct):
    return {"snapshot_date": day, "roster_pct": pct}


def test_trend_exact_and_gap_tolerance():
    rows = [_r("2026-11-12", 40), _r("2026-11-19", 55)]
    assert rph.compute_trend(rows, today=TODAY)["delta"] == 15
    # baseline missing on the 12th, present on the 11th: within tolerance
    assert rph.compute_trend([_r("2026-11-11", 50), _r("2026-11-19", 55)], today=TODAY)["delta"] == 5


def test_trend_none_when_insufficient():
    assert rph.compute_trend([], today=TODAY) is None
    assert rph.compute_trend([_r("2026-11-19", 55)], today=TODAY) is None
    assert rph.compute_trend([_r("2026-11-09", 50), _r("2026-11-19", 55)], today=TODAY) is None  # gap too large
    assert rph.compute_trend([_r("2026-11-05", 50), _r("2026-11-12", 55)], today=TODAY) is None  # stale current


def test_get_roster_pct_trend_reads_and_never_fabricates():
    data = [{"player_id": "1", **_r("2026-11-12", 40)}, {"player_id": "1", **_r("2026-11-19", 50)},
            {"player_id": "2", **_r("2026-11-19", 9)}]
    resp = Mock(status_code=200)
    resp.json.return_value = data
    with patch.object(rph.requests, "get", return_value=resp):
        out = rph.get_roster_pct_trend(["1", "2", "3"], 7, config=CFG, today=TODAY)
    assert out["1"]["delta"] == 10 and out["2"] is None and out["3"] is None
    assert rph.get_roster_pct_trend(["1"], config=rph.Config()) == {"1": None}


def test_run_mocks_espn_and_sleeper():
    pool = pd.DataFrame([{"player_id": "1"}])
    env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}
    with patch.object(rph, "load_global_rating_pool", return_value=pool), \
         patch.object(rph.public_roster_percentages, "roster_percentages", return_value={"1": {"percent": 70.0}}), \
         patch.object(rph.sleeper, "trending_add_rank_map", return_value={"1": {"count": 5, "rank": 1}}), \
         patch.object(rph.requests, "post", return_value=_ok()), \
         patch.object(rph.requests, "delete", return_value=_ok()):
        stats = rph.run_roster_pct_snapshot(environ=env)
    assert stats["ok"] and stats["rows_sent"] == 1 and stats["pruned"]


def test_latest_only_when_baseline_not_required():
    rows = [_r("2026-11-19", 55)]
    got = rph.compute_trend(rows, today=TODAY, require_baseline=False)
    assert got["current"] == 55 and got["previous"] is None and got["delta"] is None
    # staleness is still enforced: never a stale or future % presented as current
    assert rph.compute_trend([_r("2026-11-12", 55)], today=TODAY, require_baseline=False) is None
    # with a real baseline the trend is unchanged
    assert rph.compute_trend([_r("2026-11-12", 40), _r("2026-11-19", 55)], today=TODAY, require_baseline=False)["delta"] == 15
