from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from modules import game_weather as gw
from modules import nfl_stadiums

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
KICKOFF = datetime(2026, 11, 2, 18, 0, tzinfo=timezone.utc)

EFFECTS = {
    "QB": {"wind_15_19": -0.04, "wind_20p": -0.10, "rain_light": -0.03, "rain_heavy": -0.08, "cold_le32": -0.02},
    "WR": {"wind_20p": -0.06, "rain_heavy": -0.05},
    "K": {"wind_20p": -0.12},
}


@pytest.fixture
def effects(monkeypatch):
    monkeypatch.setattr(gw, "WEATHER_EFFECTS", EFFECTS)


@pytest.fixture
def weather_on(monkeypatch):
    monkeypatch.delenv("FANTASYDESK_WEATHER_DISABLED", raising=False)


def _fc(**kw):
    base = {"wind_mph": 5.0, "gust_mph": 9.0, "precip_mm": 0.0, "precip_prob_pct": 0, "temp_f": 60}
    base.update(kw)
    return base


def _hourly(wind=5.0, rain=0.0, prob=0, temp=60.0):
    times = [(NOW.replace(hour=0) + timedelta(hours=h)).strftime("%Y-%m-%dT%H:00") for h in range(0, 24 * 4)]
    n = len(times)
    return {
        "time": times,
        "temperature_2m": [temp] * n,
        "wind_speed_10m": [wind] * n,
        "wind_gusts_10m": [wind + 8] * n,
        "precipitation": [rain] * n,
        "precipitation_probability": [prob] * n,
    }


def _warm(stadium="BUF00"):
    """Run the background refresh to completion (inside the caller's patch)."""
    gw.prefetch_stadium_ids([stadium])
    gw.wait_for_refreshes()


def _resp(hourly):
    r = Mock()
    r.raise_for_status = Mock()
    r.json = Mock(return_value={"hourly": hourly})
    return r


# --- adjustment ------------------------------------------------------------


def test_calm_forecast_is_neutral(effects):
    adj = gw.weather_adjustment("QB", _fc())
    assert adj == {"multiplier": 1.0, "reason": None, "factors": []}


def test_no_forecast_is_neutral(effects):
    assert gw.weather_adjustment("QB", None)["multiplier"] == 1.0


def test_position_without_measured_effect_is_untouched(effects):
    # RB has no entry: data too thin means no adjustment, even in a storm.
    adj = gw.weather_adjustment("RB", _fc(wind_mph=30, precip_mm=9, precip_prob_pct=100, temp_f=10))
    assert adj["multiplier"] == 1.0 and adj["reason"] is None


def test_heavy_rain_lowers_qb_with_human_reason(effects):
    adj = gw.weather_adjustment("QB", _fc(precip_mm=6.0, precip_prob_pct=100))
    assert adj["multiplier"] == pytest.approx(0.92)
    assert adj["reason"] == "Heavy rain forecast: passing outlook lowered"


def test_rain_effect_scales_with_chance_of_rain(effects):
    sure = gw.weather_adjustment("QB", _fc(precip_mm=6.0, precip_prob_pct=100))["multiplier"]
    maybe = gw.weather_adjustment("QB", _fc(precip_mm=6.0, precip_prob_pct=40))["multiplier"]
    assert 1.0 > maybe > sure


def test_factors_stack_but_total_is_capped(effects):
    adj = gw.weather_adjustment("QB", _fc(wind_mph=25, precip_mm=8, precip_prob_pct=100, temp_f=20))
    assert adj["multiplier"] == pytest.approx(0.90)
    assert len(adj["factors"]) == 3
    assert adj["reason"].startswith("High wind forecast")
    assert gw.MAX_TOTAL_REDUCTION == 0.10


def test_tiny_net_effect_shows_no_reason(effects, monkeypatch):
    monkeypatch.setattr(gw, "WEATHER_EFFECTS", {"QB": {"wind_15_19": -0.005}})
    assert gw.weather_adjustment("QB", _fc(wind_mph=16))["reason"] is None


def test_calibrated_table_is_sane():
    for pos, table in gw.WEATHER_EFFECTS.items():
        assert pos in {"QB", "RB", "WR", "TE", "K"}
        for key, effect in table.items():
            assert key in {"wind_15_19", "wind_20p", "rain_light", "rain_heavy", "cold_le32"}
            assert -0.25 < effect < 0


# --- forecast + fail soft ---------------------------------------------------


def test_forecast_parses_kickoff_window(weather_on):
    with patch.object(gw.requests, "get", return_value=_resp(_hourly(wind=22, rain=2.0, prob=80, temp=41))) as get:
        _warm()
        f = gw.forecast_for_game("BUF00", KICKOFF.isoformat(), now=NOW)
    assert get.call_count == 1
    assert f["wind_mph"] == 22.0 and f["precip_mm"] == 8.0 and f["precip_prob_pct"] == 80 and f["temp_f"] == 41


def test_forecast_is_cached_per_stadium(weather_on):
    with patch.object(gw.requests, "get", return_value=_resp(_hourly())) as get:
        _warm()
        gw.forecast_for_game("BUF00", KICKOFF.isoformat(), now=NOW)
        gw.forecast_for_game("BUF00", (KICKOFF + timedelta(hours=3)).isoformat(), now=NOW)
        gw.wait_for_refreshes()
    assert get.call_count == 1


def test_cold_cache_returns_immediately_without_network_then_background_populates(weather_on):
    release = threading.Event()

    def slow_get(*a, **k):
        release.wait(5)
        return _resp(_hourly(wind=22))

    state = {}
    with patch.object(gw.requests, "get", side_effect=slow_get) as get:
        t0 = time.monotonic()
        out = gw.forecast_for_game("BUF00", KICKOFF.isoformat(), now=NOW, state_out=state)
        summary = gw.apply_weather(_summary(), position="QB", stadium_id="BUF00", kickoff_at=KICKOFF.isoformat(), now=NOW)
        assert time.monotonic() - t0 < 0.5  # the blocked fetch never held the caller
        assert out is None and state["state"] == "loading"
        assert summary["weather"]["label"] == "Weather loading: no adjustment"
        assert summary["weather"]["status"] == "loading" and summary["point_estimate"] == 20.0
        release.set()
        gw.wait_for_refreshes()
    assert get.call_count == 1  # queued once, not once per caller
    assert gw.forecast_for_game("BUF00", KICKOFF.isoformat(), now=NOW)["wind_mph"] == 22.0


def test_expired_cache_is_served_while_refreshing(weather_on):
    with patch.object(gw.requests, "get", return_value=_resp(_hourly(wind=10))):
        _warm()
    gw._cache["BUF00"]["expires"] = time.time() - 1  # expired
    release = threading.Event()

    def slow_get(*a, **k):
        release.wait(5)
        return _resp(_hourly(wind=30))

    with patch.object(gw.requests, "get", side_effect=slow_get) as get:
        stale = gw.forecast_for_game("BUF00", KICKOFF.isoformat(), now=NOW)
        again = gw.forecast_for_game("BUF00", KICKOFF.isoformat(), now=NOW)
        assert stale["wind_mph"] == 10.0 and again["wind_mph"] == 10.0  # stale, instantly
        release.set()
        gw.wait_for_refreshes()
    assert get.call_count == 1  # one in-flight refresh despite two callers
    assert gw.forecast_for_game("BUF00", KICKOFF.isoformat(), now=NOW)["wind_mph"] == 30.0


def test_failed_refresh_keeps_stale_data_and_does_not_stampede(weather_on):
    with patch.object(gw.requests, "get", return_value=_resp(_hourly(wind=10))):
        _warm()
    gw._cache["BUF00"]["expires"] = time.time() - 1
    with patch.object(gw.requests, "get", side_effect=OSError("down")) as get:
        for _ in range(5):
            f = gw.forecast_for_game("BUF00", KICKOFF.isoformat(), now=NOW)
            gw.wait_for_refreshes()
            assert f["wind_mph"] == 10.0
    assert get.call_count == 1


def test_parallel_prefetch_warms_each_stadium_once(weather_on):
    with patch.object(gw.requests, "get", return_value=_resp(_hourly())) as get:
        gw.prefetch_stadium_ids(["BUF00", "GNB00", "BUF00", "DET00", "NOPE", None])
        gw.wait_for_refreshes()
        gw.prefetch_stadium_ids(["BUF00", "GNB00"])
        gw.wait_for_refreshes()
    assert get.call_count == 2  # dome and unknown skipped, warm cache not refetched


def test_prefetch_for_games_reads_horizon_stadiums(weather_on):
    import pandas as pd

    games = pd.DataFrame(
        [
            {"gameday": "2026-11-02", "stadium_id": "BUF00"},
            {"gameday": "2026-11-03", "stadium_id": "GNB00"},
            {"gameday": "2027-02-01", "stadium_id": "SEA00"},
        ]
    )
    with patch.object(gw.requests, "get", return_value=_resp(_hourly())) as get:
        gw.prefetch_for_games(games, now=NOW)
        gw.wait_for_refreshes()
    assert get.call_count == 2


@pytest.mark.parametrize("stadium_id", ["DET00", "LAX01", "DAL00", "IND00", "NOPE99", None])
def test_domes_retractable_and_unknown_get_no_forecast(weather_on, stadium_id):
    with patch.object(gw.requests, "get") as get:
        assert gw.forecast_for_game(stadium_id, KICKOFF.isoformat(), now=NOW) is None
    get.assert_not_called()


def test_started_or_far_future_games_get_no_forecast(weather_on):
    with patch.object(gw.requests, "get") as get:
        assert gw.forecast_for_game("BUF00", (NOW - timedelta(hours=1)).isoformat(), now=NOW) is None
        assert gw.forecast_for_game("BUF00", (NOW + timedelta(days=12)).isoformat(), now=NOW) is None
    get.assert_not_called()


def test_network_failure_fails_soft_and_is_negative_cached(weather_on):
    with patch.object(gw.requests, "get", side_effect=OSError("down")) as get:
        _warm()
        assert gw.forecast_for_game("BUF00", KICKOFF.isoformat(), now=NOW) is None
        assert gw.forecast_for_game("BUF00", KICKOFF.isoformat(), now=NOW) is None
        gw.wait_for_refreshes()
    assert get.call_count == 1


def test_malformed_payload_fails_soft(weather_on):
    with patch.object(gw.requests, "get", return_value=_resp({"time": ["x"]})):
        _warm()
        assert gw.forecast_for_game("BUF00", KICKOFF.isoformat(), now=NOW) is None


def test_disabled_flag_skips_network():
    with patch.object(gw.requests, "get") as get:
        assert gw.forecast_for_game("BUF00", KICKOFF.isoformat(), now=NOW) is None
    get.assert_not_called()


# --- apply_weather / payload -----------------------------------------------


def _summary(points=20.0):
    return {"status": "ok", "point_estimate": points, "low": 12.0, "high": 28.0, "confidence": "medium"}


def _apply(position="QB", stadium="BUF00", summary=None):
    return gw.apply_weather(summary or _summary(), position=position, stadium_id=stadium, kickoff_at=KICKOFF.isoformat(), now=NOW)


def test_outdoor_forecast_scales_projection_and_states_why(effects, weather_on):
    with patch.object(gw.requests, "get", return_value=_resp(_hourly(wind=18, rain=2.0, prob=100))):
        _warm()
        out = _apply()
    w = out["weather"]
    assert w["status"] == "outdoor" and w["applied"]
    assert w["reason"] == "Heavy rain forecast: passing outlook lowered"
    assert w["label"] == "Weather: Heavy rain, 18 mph wind, 60\u00b0F (outdoor) \u2192 passing outlook \u221210%"
    assert out["point_estimate"] == 18.0 and w["points_before"] == 20.0


def test_total_reduction_is_modest_and_capped(effects, weather_on):
    with patch.object(gw.requests, "get", return_value=_resp(_hourly(wind=25, rain=2.0, prob=100, temp=20))):
        _warm()
        out = _apply()
    assert out["weather"]["multiplier"] == pytest.approx(0.90)
    assert out["point_estimate"] == 18.0


def test_dome_gets_status_and_no_adjustment(effects, weather_on):
    with patch.object(gw.requests, "get") as get:
        out = _apply(stadium="DET00")
    get.assert_not_called()
    assert out["point_estimate"] == 20.0
    assert out["weather"]["status"] == "dome" and out["weather"]["label"] == "Dome: no weather effect"


def test_retractable_roof_uses_reduced_weight_and_says_so(effects, weather_on):
    with patch.object(gw.requests, "get", return_value=_resp(_hourly(wind=5, rain=2.0, prob=100))):
        _warm("HOU00")
        out = _apply(stadium="HOU00")
    w = out["weather"]
    assert w["status"] == "retractable" and w["applied"]
    assert "retractable roof, status unknown, reduced weight" in w["label"]
    assert w["multiplier"] == pytest.approx(1 - 0.08 * gw.RETRACTABLE_WEIGHT, abs=0.001)
    assert w["multiplier"] > 0.95


def test_unavailable_forecast_states_no_adjustment(effects, weather_on):
    with patch.object(gw.requests, "get", side_effect=OSError):
        _warm()
        out = _apply()
    assert out["point_estimate"] == 20.0
    assert out["weather"]["status"] == "unavailable"
    assert out["weather"]["label"] == "Weather unavailable: no adjustment"


def test_calm_forecast_reports_but_does_not_change(effects, weather_on):
    with patch.object(gw.requests, "get", return_value=_resp(_hourly())):
        _warm()
        out = _apply()
    assert out["point_estimate"] == 20.0 and out["weather"]["applied"] is False
    assert out["weather"]["label"].endswith("(outdoor): no adjustment")


def test_no_block_when_game_started_far_out_or_stadium_unknown(effects, weather_on):
    with patch.object(gw.requests, "get") as get:
        past = gw.apply_weather(_summary(), position="QB", stadium_id="BUF00", kickoff_at=(NOW - timedelta(hours=2)).isoformat(), now=NOW)
        far = gw.apply_weather(_summary(), position="QB", stadium_id="BUF00", kickoff_at=(NOW + timedelta(days=20)).isoformat(), now=NOW)
        unknown = _apply(stadium="ZZZ99")
        none = _apply(stadium=None)
    get.assert_not_called()
    for out in (past, far, unknown, none):
        assert out == _summary()


def test_disabled_flag_adds_nothing():
    assert _apply() == _summary()


def test_non_ok_projection_is_never_touched(effects, weather_on):
    assert _apply(summary={"status": "bye_week"}) == {"status": "bye_week"}


def test_team_home_stadium_table_resolves():
    assert set(nfl_stadiums.HOME_STADIUM_BY_TEAM) >= {"TB", "GB", "KC", "LV", "LAR", "ARI"}
    for sid in nfl_stadiums.HOME_STADIUM_BY_TEAM.values():
        assert nfl_stadiums.stadium_for(sid) is not None
    assert nfl_stadiums.stadium_for(nfl_stadiums.HOME_STADIUM_BY_TEAM["TB"]).roof == "outdoor"
    assert nfl_stadiums.stadium_for(nfl_stadiums.HOME_STADIUM_BY_TEAM["LV"]).roof == "dome"
    # international / neutral-site venues are present by stadium_id
    for sid in ("LON00", "LON02", "MUN01", "GER00", "MEX00", "SAO00", "MAD01", "MEL00"):
        assert nfl_stadiums.stadium_for(sid) is not None


def test_stadium_table_roof_kinds():
    assert nfl_stadiums.stadium_for("lax01").roof == "dome"
    assert nfl_stadiums.stadium_for("GNB00").roof == "outdoor"
    assert nfl_stadiums.stadium_for("HOU00").roof == "retractable"


def test_move_payload_carries_weather_status(effects, weather_on):
    from services import mobile_api_service as svc

    label = "Weather: Heavy rain, 12 mph wind, 48\u00b0F (outdoor) \u2192 passing outlook \u22128%"
    rainy = {"player_id": "qb1", "name": "QB One", "position": "QB", "slot": "QB", "actual_points": None,
             "projection": {"status": "ok", "point_estimate": 14.0, "low": 8.0, "high": 20.0,
                            "weather": {"status": "outdoor", "applied": True, "label": label,
                                        "reason": "Heavy rain forecast: passing outlook lowered"}}}
    dome = {"player_id": "qb2", "name": "QB Two", "position": "QB", "slot": "QB", "actual_points": None,
            "projection": {"status": "ok", "point_estimate": 15.0, "low": 9.0, "high": 21.0,
                           "weather": {"status": "dome", "applied": False, "label": "Dome: no weather effect", "reason": None}}}
    side = {"has_live_data": True, "starters": [dome], "real_starters": [rainy], "real_empty_slots": []}
    (move,) = svc._suggested_lineup_moves(side)
    assert move["over"]["weather_reason"] == "Heavy rain forecast: passing outlook lowered"
    assert move["start"]["weather_reason"] is None
    assert move["weather_notes"] == [
        {"role": "start", "player": "QB Two", "status": "dome", "applied": False, "label": "Dome: no weather effect", "reason": None},
        {"role": "over", "player": "QB One", "status": "outdoor", "applied": True, "label": label,
         "reason": "Heavy rain forecast: passing outlook lowered"},
    ]


def test_move_without_forecast_has_no_weather_notes():
    from services import mobile_api_service as svc

    a = {"player_id": "a", "name": "A", "position": "RB", "slot": "RB", "actual_points": None,
         "projection": {"status": "ok", "point_estimate": 5.0, "low": 3.0, "high": 7.0}}
    b = {**a, "player_id": "b", "name": "B", "projection": {"status": "ok", "point_estimate": 9.0, "low": 6.0, "high": 12.0}}
    side = {"has_live_data": True, "starters": [b], "real_starters": [a], "real_empty_slots": []}
    (move,) = svc._suggested_lineup_moves(side)
    assert move["weather_notes"] == []


def test_weekly_projection_helper_fails_soft(effects, weather_on):
    from services import mobile_api_service as svc

    result = {"position": "QB", "game_id": "2026_09_X_Y", "kickoff_at": KICKOFF.isoformat()}
    with patch.object(svc.game_weather, "apply_weather", side_effect=RuntimeError("boom")):
        assert svc._with_game_weather(_summary(), result) == _summary()


def test_measured_table_rb_untouched_qb_lowered_in_downpour():
    storm = _fc(wind_mph=18, precip_mm=9.0, precip_prob_pct=100, temp_f=45)
    assert gw.weather_adjustment("RB", storm)["multiplier"] == 1.0
    qb = gw.weather_adjustment("QB", storm)
    assert 0.85 <= qb["multiplier"] < 0.95
    assert qb["reason"] == "Heavy rain forecast: passing outlook lowered"
    assert gw.weather_adjustment("DEF", storm)["multiplier"] == 1.0


def test_heavier_tier_inherits_lighter_effect_when_unmeasured(monkeypatch):
    monkeypatch.setattr(gw, "WEATHER_EFFECTS", {"K": {"wind_15_19": -0.06}})
    assert gw.weather_adjustment("K", _fc(wind_mph=25))["multiplier"] == pytest.approx(0.94)


def test_stadium_id_for_game_lookup():
    import pandas as pd
    from modules import nfl_schedule

    games = pd.DataFrame([{"game_id": "g1", "stadium_id": "GNB00"}, {"game_id": "g2", "stadium_id": None}])
    assert nfl_schedule.stadium_id_for_game("g1", games=games) == "GNB00"
    assert nfl_schedule.stadium_id_for_game("g2", games=games) is None
    assert nfl_schedule.stadium_id_for_game("nope", games=games) is None
    assert nfl_schedule.stadium_id_for_game(None, games=games) is None
