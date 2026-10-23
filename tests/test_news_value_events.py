from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from modules import news_value_events as nve
from modules import rankings

T0 = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def _frame(status="Active", injury="", inj_mult=1.0, score=1000):
    return pd.DataFrame(
        [{"player_id": "1", "status": status, "injury_status": injury, "injury_multiplier": inj_mult, "score": score}]
    )


def _event(subtype="ir", detected=T0, cleared=None, type_="availability_out"):
    return {"player_id": "1", "type": type_, "subtype": subtype, "source": nve.SOURCE_SLEEPER_STATUS,
            "detected_at": detected.isoformat(), "from": {}, "to": {}, "cleared_at": cleared}


@pytest.fixture
def on(monkeypatch, tmp_path):
    monkeypatch.setenv(nve.ENV_FLAG, "1")
    monkeypatch.setenv(nve.ENV_PATH, str(tmp_path / "events.json"))


def test_off_by_default_changes_nothing(monkeypatch):
    monkeypatch.delenv(nve.ENV_FLAG, raising=False)
    df = _frame("Active", "Out")
    out = nve.apply_to_frame(df, now=T0, events=[_event("out")])
    assert out.equals(df) and "news_event_type" not in out.columns


def test_cap_and_incremental_no_double_count(on):
    cap = nve.EVENT_TYPES["availability_out"].max_reduction
    assert cap <= 0.20
    # feed shows no existing discount: full capped reduction at t0
    out = nve.apply_to_frame(_frame("Active", "Out", 1.0), now=T0, events=[_event("out")])
    assert out.score[0] == round(1000 * (1 - cap))
    assert out.news_factor[0] == pytest.approx(-cap, abs=1e-3)
    # feed already discounts more (IR major 0.68): no second hit
    out = nve.apply_to_frame(_frame("Injured Reserve", "", 0.68), now=T0, events=[_event("ir")])
    assert out.score[0] == 1000 and out.news_factor[0] == 0.0
    assert json.loads(out.news_event_provenance[0])["existing_injury_multiplier"] == 0.68


def test_decay_halves_at_half_life(on):
    spec = nve.EVENT_TYPES["availability_out"]
    r0 = nve.event_reduction(_event(), T0)
    rh = nve.event_reduction(_event(), T0 + timedelta(days=spec.half_life_days))
    assert rh == pytest.approx(r0 / 2, rel=1e-6)
    assert r0 > nve.event_reduction(_event(), T0 + timedelta(days=7)) > 0


def test_expires_after_max_age_and_when_cleared(on):
    spec = nve.EVENT_TYPES["availability_out"]
    assert nve.event_reduction(_event(), T0 + timedelta(days=spec.max_age_days + 0.1)) == 0.0
    assert nve.event_reduction(_event(cleared=T0.isoformat()), T0) == 0.0
    # feed no longer carries an availability status => treated as cleared even if store is stale
    out = nve.apply_to_frame(_frame("Active", "", 1.0), now=T0, events=[_event("out")])
    assert out.score[0] == 1000 and out.news_factor[0] == 0.0


def test_disabled_types_never_move_value(on):
    for t in ("team_change", "depth_chart_role"):
        assert not nve.EVENT_TYPES[t].enabled
        assert nve.event_reduction(_event(type_=t), T0) == 0.0


def test_provenance_exposed(on):
    out = nve.apply_to_frame(_frame("Active", "Out", 1.0), now=T0, events=[_event("out")])
    prov = json.loads(out.news_event_provenance[0])
    assert prov["event_type"] == "availability_out" and prov["subtype"] == "out"
    assert prov["source"] == nve.SOURCE_SLEEPER_STATUS and prov["detected_at"] == T0.isoformat()
    assert out.news_event_type[0] == "availability_out"


def test_record_open_clear_roundtrip(on, tmp_path):
    p = tmp_path / "e.json"
    ch = {"player_id": "1", "old_status": "Active", "old_injury_status": "Questionable",
          "new_status": "Active", "new_injury_status": "Out"}
    assert nve.record_status_changes([ch], now=T0, path=p) == {"opened": 1, "cleared": 0}
    assert nve.record_status_changes([ch], now=T0, path=p)["opened"] == 0  # no duplicate open
    back = {"player_id": "1", "old_status": "Active", "old_injury_status": "Out",
            "new_status": "Active", "new_injury_status": ""}
    assert nve.record_status_changes([back], now=T0 + timedelta(days=3), path=p)["cleared"] == 1
    ev = nve.load_events(p)
    assert ev[0]["cleared_at"] and ev[0]["source"] == nve.SOURCE_SLEEPER_STATUS
    # questionable/doubtful are not events
    q = {"player_id": "2", "old_status": "Active", "old_injury_status": "",
         "new_status": "Active", "new_injury_status": "Questionable"}
    assert nve.record_status_changes([q], now=T0, path=p)["opened"] == 0


def test_classify_status():
    assert nve.classify_status("Injured Reserve", "") == "ir"
    assert nve.classify_status("Active", "Sus") == "suspended"
    assert nve.classify_status("Active", "PUP") == "pup"
    assert nve.classify_status("Active", "Out") == "out"
    assert nve.classify_status("Active", "Doubtful") is None
    assert nve.classify_status("Active", "NA") is None


def test_central_hook_compose_composite_score(on, monkeypatch):
    """The single central path (rankings.compose_composite_score) applies the event."""
    base = pd.DataFrame([{
        "player_id": "1", "status": "Active", "injury_status": "Out", "team": "KC", "search_rank": 50,
        "market_score": 5000.0, "age_curve_score": 5000.0, "scarcity_score": 5000.0, "role_score": 5000.0,
        "production_score": 5000.0, "opportunity_score": 5000.0,
        "risk_multiplier": 1.0, "non_injury_risk_multiplier": 1.0, "injury_multiplier": 1.0,
    }])
    monkeypatch.setattr(nve, "load_events", lambda path=None: [_event("out", detected=datetime.now(timezone.utc))])
    on_score = int(rankings.compose_composite_score(base).score[0])
    monkeypatch.setenv(nve.ENV_FLAG, "0")
    off = rankings.compose_composite_score(base)
    assert on_score < int(off.score[0]) and off.news_factor[0] == 0.0
    assert "news_event_type" not in off.columns
