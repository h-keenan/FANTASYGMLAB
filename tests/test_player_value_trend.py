"""Player value history: real-snapshot chart series and buy-low / sell-high."""

from __future__ import annotations

import pandas as pd
import pytest

from modules import player_value_trend as pvt


def _rows(pairs):
    return [{"snapshot_date": d, "overall_rating": r} for d, r in pairs]


def test_history_points_sorts_dedupes_and_drops_malformed():
    pts = pvt.history_points(
        _rows([("2026-10-03", 70), ("2026-10-01", 65), ("2026-10-02", "x"), ("2026-10-04", 120), ("", 50)])
    )
    assert pts == [{"date": "2026-10-01", "rating": 65}, {"date": "2026-10-03", "rating": 70}]


def test_short_history_reports_real_span_without_changes():
    one = pvt.history_summary(pvt.history_points(_rows([("2026-10-01", 65)])))
    assert one["status"] == "insufficient_history" and one["span_days"] == 0 and one["change"] is None
    three = pvt.history_summary(pvt.history_points(_rows([("2026-10-01", 65), ("2026-10-02", 66), ("2026-10-04", 70)])))
    assert three["status"] == "ok" and three["span_days"] == 3
    assert three["changes"] == []  # no 7d/30d claim without a snapshot that old
    assert three["change"] == {"days": 3, "delta": 5}


def test_changes_only_for_windows_with_real_baseline():
    pts = pvt.history_points(_rows([("2026-10-01", 60), ("2026-10-10", 64), ("2026-10-12", 70)]))
    summary = pvt.history_summary(pts)
    assert [c["days"] for c in summary["changes"]] == [11]
    assert summary["changes"][0]["delta"] == 10


def _pool(n=12):
    rows = []
    for i in range(n):
        rows.append(
            {
                "player_id": str(i),
                "name": f"P{i}",
                "position": "WR",
                "team": "SF",
                "age": 25,
                "dynasty_score": 100.0 + i * 10,  # value rises with i
                "ppg": 5.0 + i,  # production rises with i
                "games_played": 8,
                "injury_status": None,
            }
        )
    return pd.DataFrame(rows)


def test_buy_low_needs_falling_value_and_production_ahead_of_value():
    frame = _pool()
    # Player 10: production pct high, but make value score low so value pct is low.
    frame.loc[frame.player_id == "10", "dynasty_score"] = 105.0
    latest = {str(i): 60 for i in range(12)}
    baseline = {str(i): 60 for i in range(12)}
    baseline["10"] = 66  # value fell 6
    out = pvt.compute_signals(frame, latest, baseline, latest_date="2026-10-20", baseline_date="2026-10-10")
    assert [i["player_id"] for i in out["buy_low"]] == ["10"]
    item = out["buy_low"][0]
    assert item["rating_change"] == -6 and item["production_percentile"] > item["value_percentile"]
    assert {f["label"] for f in item["factors"]} >= {"Value trend", "Production", "Sample"}
    assert out["sell_high"] == []


def test_sell_high_and_exclusions():
    frame = _pool()
    frame.loc[frame.player_id == "10", "ppg"] = 4.0  # poor production, top-ish value
    latest = {str(i): 60 for i in range(12)}
    baseline = dict(latest)
    baseline["10"] = 52  # value rose 8
    out = pvt.compute_signals(frame, latest, baseline, latest_date="2026-10-20", baseline_date="2026-10-10")
    assert [i["player_id"] for i in out["sell_high"]] == ["10"]
    # Injured out players never qualify.
    frame.loc[frame.player_id == "10", "injury_status"] = "Out"
    assert pvt.compute_signals(frame, latest, baseline, latest_date="2026-10-20", baseline_date="2026-10-10")["sell_high"] == []


def test_no_signal_without_both_snapshots_or_small_sample():
    frame = _pool()
    frame["games_played"] = 2
    latest = {str(i): 60 for i in range(12)}
    baseline = {str(i): 70 for i in range(12)}
    out = pvt.compute_signals(frame, latest, baseline, latest_date="2026-10-20", baseline_date="2026-10-10")
    assert out == {"buy_low": [], "sell_high": []}
    assert pvt.compute_signals(None, latest, baseline, latest_date="a", baseline_date="b") == {"buy_low": [], "sell_high": []}


@pytest.fixture()
def client(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")
    from services import mobile_api_service as svc

    svc.app.dependency_overrides[svc.require_user] = lambda: {"id": "u1", "_access_token": "t"}
    yield TestClient(svc.app), svc
    svc.app.dependency_overrides.clear()


def test_rating_history_endpoint_requires_auth_and_degrades(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")
    from services import mobile_api_service as svc

    c = TestClient(svc.app)
    assert c.get("/v1/players/1/rating-history").status_code == 401
    assert c.get("/v1/players/value-signals").status_code == 401


def test_rating_history_endpoint_returns_real_points_and_unavailable(client, monkeypatch):
    c, svc = client
    cfg = svc.player_rating_history.RatingSnapshotConfig(url="https://x", service_role_key="k")
    monkeypatch.setattr(svc.player_rating_history, "load_rating_snapshot_config", lambda: cfg)
    from datetime import date

    today = date.today()
    rows = [
        {"snapshot_date": today.isoformat(), "overall_rating": 71},
        {"snapshot_date": (today.replace(day=1)).isoformat(), "overall_rating": 68},
    ]
    monkeypatch.setattr(svc.player_rating_history, "fetch_rating_history", lambda *_a, **_k: rows)
    body = c.get("/v1/players/9/rating-history?days=90").json()
    assert body["status"] in {"ok", "insufficient_history"}
    assert all(set(p) == {"date", "rating"} for p in body["points"])
    assert c.get("/v1/players/9/rating-history?days=3").status_code == 422
    monkeypatch.setattr(
        svc.player_rating_history, "load_rating_snapshot_config", lambda: svc.player_rating_history.RatingSnapshotConfig()
    )
    assert c.get("/v1/players/9/rating-history").json()["status"] == "unavailable"


def test_value_signals_history_building_reports_real_span(client, monkeypatch):
    c, svc = client
    cfg = svc.player_rating_history.RatingSnapshotConfig(url="https://x", service_role_key="k")
    monkeypatch.setattr(svc.player_rating_history, "load_rating_snapshot_config", lambda: cfg)
    monkeypatch.setattr(svc.redis_cache, "redis_single_flight_cache", lambda **k: k["compute"]())
    monkeypatch.setattr(svc.player_rating_history, "fetch_snapshot_date_bounds", lambda _c: ("2026-10-28", "2026-11-01"))
    monkeypatch.setattr(svc.player_rating_history, "fetch_baseline_date", lambda *_a, **_k: None)
    body = c.get("/v1/players/value-signals").json()
    assert body["status"] == "history_building" and body["span_days"] == 4
    assert body["buy_low"] == [] and body["sell_high"] == []
