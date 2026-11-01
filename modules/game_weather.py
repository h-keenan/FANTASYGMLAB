"""Game-day weather for weekly projections and start/sit suggestions.

Three small, separable pieces:

1. ``forecast_for_game`` - a per-game forecast (wind, gusts, rain, rain
   probability, temperature) for the 4 hours from kickoff, from Open-Meteo's
   free no-key forecast API at the game's stadium (modules.nfl_stadiums).
   Fixed domes are ignored; retractable roofs are treated as unknown (their
   roof is closed in bad weather and not known before kickoff), so neither
   gets a forecast. Results are cached per stadium with a short TTL, and
   EVERY failure path returns ``None`` - weather never blocks a projection.

2. ``weather_adjustment`` - the single place that turns a position and a
   forecast into a multiplier plus a human reason. The per-position effect
   sizes in ``WEATHER_EFFECTS`` come from docs/weather-effects.md
   (scripts/weather_effects_analysis.py): a player-fixed-effects regression on
   2011-2025 outdoor games, shrunk toward zero, kept only where the data
   clears a significance bar. A position/condition without a credible measured
   effect has NO adjustment, by design. The total is capped.

3. ``apply_weather`` - attaches both to a projection summary.

Nothing here touches value scores, rankings or the trust engine; it only
scales the weekly point estimate (and its range) when a real forecast says
conditions are adverse.
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from modules import nfl_stadiums

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_TTL_SECONDS = 45 * 60
FAILURE_TTL_SECONDS = 10 * 60
# Forecasts further out than this are not trusted (Open-Meteo hourly skill
# falls off quickly past about a week) and are not even requested.
MAX_HORIZON = timedelta(days=7)
WINDOW_HOURS = 4  # kickoff hour through +3h, matching the research window

# Effect of each condition on a player's weekly points, as a fraction (-0.08
# = 8% fewer points), AFTER shrinkage. Filled from docs/weather-effects.md.
# Missing position/condition = no measured effect = no adjustment.
WEATHER_EFFECTS: dict[str, dict[str, float]] = {
    # Adopted cells only (docs/weather-effects.md): harmful effect with
    # z <= -2.5, same sign in both halves of 2011-2025, and (wind/cold)
    # corroborated by stadium-reported game-day numbers. RB has none: nothing
    # measured clears the bar, so RBs are never adjusted. QB/WR wind is absent
    # on purpose: the reanalysis-wind effect did not replicate with
    # stadium-reported wind.
    "QB": {"rain_light": -0.070, "rain_heavy": -0.119, "cold_le32": -0.081},
    "WR": {"rain_heavy": -0.107},
    "TE": {"wind_20p": -0.161, "rain_heavy": -0.105},
    "K": {"wind_15_19": -0.075, "cold_le32": -0.091},
}

# A heavier tier with no measured effect of its own inherits the lighter
# tier's (conditions only get worse up the ladder, so this is conservative).
# Retractable roofs: the roof state is unknown before kickoff and these
# venues close in bad weather, so only this share of the measured effect is
# applied, and the label says so.
RETRACTABLE_WEIGHT = 0.35

_TIER_FALLBACK = {"wind_20p": "wind_15_19", "rain_heavy": "rain_light"}

# Never move a projection by more than this, however many conditions stack
# (the shrunk measured effects are 7-12% each; this keeps stacked conditions
# modest).
MAX_TOTAL_REDUCTION = 0.10
# A rounding floor so noise-level effects do not produce a visible chip.
MIN_VISIBLE_EFFECT = 0.015

# Tier thresholds. Must match scripts/weather_effects_analysis.py TIERS.
WIND_MODERATE_MPH = 15.0
WIND_HIGH_MPH = 20.0
RAIN_LIGHT_MM = 1.0
RAIN_HEAVY_MM = 4.0
COLD_F = 32.0

_lock = threading.Lock()
# stadium_id -> {"expires": ts, "hourly": dict|None, "retry_at": ts}
_cache: dict[str, dict[str, Any]] = {}
_inflight: set[str] = set()
_pending: list[Future] = []
_executor: ThreadPoolExecutor | None = None
REFRESH_WORKERS = 8
# Background refreshes use a shorter timeout than the old inline fetch; no
# request ever waits on the network (see _hourly_for_stadium).
REQUEST_TIMEOUT_SECONDS = 2.0


def _disabled() -> bool:
    return os.environ.get("FANTASYDESK_WEATHER_DISABLED", "").strip().lower() in {"1", "true", "yes"}


def clear_cache() -> None:
    with _lock:
        _cache.clear()
        _inflight.clear()
        _pending.clear()


def wait_for_refreshes(timeout: float = 5.0) -> None:
    """Block until queued background refreshes finish (tests only)."""

    with _lock:
        futures = list(_pending)
    for f in futures:
        f.result(timeout=timeout)


def _fetch_hourly(stadium: nfl_stadiums.Stadium) -> dict[str, Any] | None:
    response = requests.get(
        FORECAST_URL,
        params={
            "latitude": stadium.lat,
            "longitude": stadium.lon,
            "hourly": "temperature_2m,wind_speed_10m,wind_gusts_10m,precipitation,precipitation_probability",
            "wind_speed_unit": "mph",
            "temperature_unit": "fahrenheit",
            "precipitation_unit": "mm",
            "timezone": "UTC",
            "forecast_days": 8,
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    hourly = (response.json() or {}).get("hourly")
    if not isinstance(hourly, dict) or not hourly.get("time"):
        return None
    return hourly


def _refresh(stadium_id: str, stadium: nfl_stadiums.Stadium) -> None:
    """Background worker: fetch one stadium and store it. A failure keeps any
    older data being served and backs the next attempt off (no stampede)."""

    now = time.time()
    try:
        hourly = _fetch_hourly(stadium)
    except Exception:
        hourly = None
    with _lock:
        entry = _cache.get(stadium_id) or {"expires": 0.0, "hourly": None, "retry_at": 0.0}
        if hourly:
            entry = {"expires": now + FORECAST_TTL_SECONDS, "hourly": hourly, "retry_at": 0.0}
        else:
            entry["retry_at"] = now + FAILURE_TTL_SECONDS
        _cache[stadium_id] = entry
        _inflight.discard(stadium_id)


def _schedule_refresh(stadium_id: str, stadium: nfl_stadiums.Stadium) -> None:
    """Queue ONE background refresh per stadium; a no-op while one is running."""

    global _executor
    with _lock:
        if stadium_id in _inflight:
            return
        _inflight.add(stadium_id)
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=REFRESH_WORKERS, thread_name_prefix="weather")
        try:
            future = _executor.submit(_refresh, stadium_id, stadium)
        except Exception:
            _inflight.discard(stadium_id)
            return
        _pending[:] = [f for f in _pending if not f.done()] + [future]


def _hourly_for_stadium(
    stadium_id: str, stadium: nfl_stadiums.Stadium
) -> tuple[dict[str, Any] | None, str]:
    """(hourly data, state) with ZERO network on the caller's path.

    Stale-while-revalidate: cached data is served even when expired while a
    background refresh runs. A cold stadium returns (None, "loading") and
    queues a refresh. A stadium whose last fetch failed returns
    (None, "unavailable") until its backoff passes.
    """

    now = time.time()
    with _lock:
        entry = _cache.get(stadium_id)
        due = entry is None or (entry["expires"] <= now and entry["retry_at"] <= now)
    if due:
        _schedule_refresh(stadium_id, stadium)
    if entry is None:
        return None, "loading"
    if entry["hourly"]:
        return entry["hourly"], "ok"
    return None, "unavailable"


def prefetch_stadium_ids(stadium_ids: list[str]) -> None:
    """Warm the cache for these stadiums in parallel in the background.
    Never blocks and never raises."""

    if _disabled():
        return
    for sid in sorted({str(x).upper() for x in stadium_ids if x}):
        stadium = nfl_stadiums.stadium_for(sid)
        if stadium is None or stadium.roof == "dome":
            continue
        now = time.time()
        with _lock:
            entry = _cache.get(sid)
            due = entry is None or (entry["expires"] <= now and entry["retry_at"] <= now)
        if due:
            _schedule_refresh(sid, stadium)


def prefetch_for_games(games: Any, *, now: datetime | None = None) -> None:
    """Warm every outdoor/retractable stadium with a game in the forecast
    horizon, from the nflverse games frame. Cheap, non-blocking, fail soft."""

    try:
        if _disabled() or games is None or getattr(games, "empty", True):
            return
        current = now or datetime.now(timezone.utc)
        lo = (current - timedelta(days=1)).strftime("%Y-%m-%d")
        hi = (current + MAX_HORIZON).strftime("%Y-%m-%d")
        day = games["gameday"].astype(str)
        window = games[(day >= lo) & (day <= hi)]
        prefetch_stadium_ids(window["stadium_id"].dropna().astype(str).tolist())
    except Exception:
        return


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _num(series: Any, i: int) -> float | None:
    try:
        value = series[i]
    except (TypeError, IndexError, KeyError):
        return None
    return float(value) if isinstance(value, (int, float)) else None


def forecast_for_game(
    stadium_id: str | None,
    kickoff_at: str | None,
    *,
    now: datetime | None = None,
    allow_retractable: bool = False,
    state_out: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """The kickoff-window forecast for one game, or None. Never touches the
    network: see _hourly_for_stadium. ``state_out["state"]`` reports "ok",
    "loading" (cold cache, refresh queued) or "unavailable".

    None for: no stadium / unknown stadium, a fixed dome (or a retractable
    roof unless ``allow_retractable``), no kickoff time, a game that has already kicked off or is beyond the
    forecast horizon, weather disabled, or ANY fetch/parse problem.
    """

    if _disabled() or not stadium_id or not kickoff_at:
        return None
    try:
        stadium = nfl_stadiums.stadium_for(stadium_id)
        if stadium is None or stadium.roof == "dome":
            return None
        if stadium.roof == "retractable" and not allow_retractable:
            return None
        kickoff = datetime.fromisoformat(str(kickoff_at))
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        if kickoff <= current or kickoff - current > MAX_HORIZON:
            return None
        hourly, state = _hourly_for_stadium(str(stadium_id).upper(), stadium)
        if state_out is not None:
            state_out["state"] = state
        if not hourly:
            return None
        start = kickoff.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
        wanted = {(start + timedelta(hours=h)).strftime("%Y-%m-%dT%H:00"): h for h in range(WINDOW_HOURS)}
        idx = [i for i, t in enumerate(hourly["time"]) if t in wanted]
        if len(idx) < WINDOW_HOURS:
            return None
        wind = [_num(hourly.get("wind_speed_10m"), i) for i in idx]
        gust = [_num(hourly.get("wind_gusts_10m"), i) for i in idx]
        rain = [_num(hourly.get("precipitation"), i) for i in idx]
        prob = [_num(hourly.get("precipitation_probability"), i) for i in idx]
        temp = [_num(hourly.get("temperature_2m"), i) for i in idx]
        if any(v is None for v in wind + rain + temp):
            return None
        return {
            "source": "open-meteo",
            "wind_mph": round(_mean(wind), 1),
            "gust_mph": round(max(v for v in gust if v is not None), 1) if any(v is not None for v in gust) else None,
            "precip_mm": round(sum(rain), 1),
            "precip_prob_pct": round(max(v for v in prob if v is not None)) if any(v is not None for v in prob) else None,
            "temp_f": round(_mean(temp)),
            "window_hours": WINDOW_HOURS,
        }
    except Exception:
        return None


def forecast_label(forecast: dict[str, Any]) -> str:
    """A short factual summary, e.g. "Rain likely, 18 mph wind, 41F"."""

    parts: list[str] = []
    rain = forecast.get("precip_mm") or 0.0
    prob = forecast.get("precip_prob_pct")
    if rain >= RAIN_LIGHT_MM:
        heavy = "Heavy rain" if rain >= RAIN_HEAVY_MM else "Rain"
        if isinstance(prob, (int, float)) and prob < 50:
            heavy += " possible"
        parts.append(heavy)
    wind = forecast.get("wind_mph")
    if isinstance(wind, (int, float)):
        parts.append(f"{round(wind)} mph wind")
    temp = forecast.get("temp_f")
    if isinstance(temp, (int, float)):
        parts.append(f"{round(temp)}°F")
    return ", ".join(parts)


def _rain_weight(forecast: dict[str, Any]) -> float:
    """How much of the measured rain effect to apply: the chance it actually
    rains. The effect was measured on games where it did rain, so a 40%
    forecast gets 40% of it (an expected value, not a coin flip)."""

    prob = forecast.get("precip_prob_pct")
    if not isinstance(prob, (int, float)):
        return 0.5
    return max(0.0, min(1.0, float(prob) / 100.0))


def weather_adjustment(
    position: str | None, forecast: dict[str, Any] | None, *, weight: float = 1.0
) -> dict[str, Any]:
    """Multiplier (<= 1.0) and reason for one position under one forecast.

    Always returns a dict: ``multiplier`` 1.0 and ``reason`` None whenever
    there is no forecast, no measured effect for this position, or the net
    effect is too small to matter.
    """

    neutral = {"multiplier": 1.0, "reason": None, "factors": []}
    pos = str(position or "").strip().upper()
    effects = WEATHER_EFFECTS.get(pos)
    if not forecast or not effects:
        return neutral
    wind = forecast.get("wind_mph")
    rain = forecast.get("precip_mm")
    temp = forecast.get("temp_f")

    # (key, effect weight, label) for every tier the forecast reaches.
    hit: list[tuple[str, float, str]] = []
    if isinstance(wind, (int, float)):
        if wind >= WIND_HIGH_MPH:
            hit.append(("wind_20p", 1.0, "High wind"))
        elif wind >= WIND_MODERATE_MPH:
            hit.append(("wind_15_19", 1.0, "Strong wind"))
    if isinstance(rain, (int, float)):
        if rain >= RAIN_HEAVY_MM:
            hit.append(("rain_heavy", _rain_weight(forecast), "Heavy rain"))
        elif rain >= RAIN_LIGHT_MM:
            hit.append(("rain_light", _rain_weight(forecast), "Rain"))
    if isinstance(temp, (int, float)) and temp <= COLD_F:
        hit.append(("cold_le32", 1.0, "Freezing cold"))

    factors = []
    total = 0.0
    for key, cond_weight, label in hit:
        effect = effects.get(key)
        if effect is None and key in _TIER_FALLBACK:
            effect = effects.get(_TIER_FALLBACK[key])
        if effect is None or effect >= 0:
            continue
        contribution = effect * cond_weight * weight
        total += contribution
        factors.append({"condition": key, "label": label, "effect": round(contribution, 3)})
    total = max(total, -MAX_TOTAL_REDUCTION)
    if -total < MIN_VISIBLE_EFFECT or not factors:
        return neutral
    factors.sort(key=lambda f: f["effect"])
    lead = factors[0]["label"]
    noun = _OUTLOOK_NOUN.get(pos, "outlook")
    return {
        "multiplier": round(1.0 + total, 3),
        "reason": f"{lead} forecast: {noun} lowered",
        "factors": factors,
    }


_OUTLOOK_NOUN = {
    "QB": "passing outlook",
    "WR": "passing-game outlook",
    "TE": "passing-game outlook",
    "RB": "outlook",
    "K": "kicking outlook",
}


def _signed_pct(multiplier: float) -> str:
    pct = round((multiplier - 1.0) * 100)
    return f"{pct:+d}%".replace("-", "\u2212")


def apply_weather(
    summary: dict[str, Any],
    *,
    position: str | None,
    stadium_id: str | None,
    kickoff_at: str | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Attach a ``weather`` status block to one projection summary and scale
    its numbers when a real forecast warrants it.

    The block always says WHY the projection is what it is, with ``status``:

    - ``outdoor``: forecast used (``applied`` says whether it moved the number)
    - ``retractable``: forecast used at reduced weight, roof status unknown
    - ``dome``: fixed roof, no weather effect
    - ``loading``: forecast cache still cold (a background fetch is queued);
      no adjustment, the next request has it
    - ``unavailable``: outdoor/retractable game inside the forecast window but
      the forecast could not be fetched; no adjustment

    Only an ``ok`` projection for a not-yet-started game with a known stadium
    inside the forecast window gets a block at all; otherwise the summary is
    returned untouched. When ``applied``, the point estimate and range are
    scaled and the pre-weather estimate is kept in ``points_before``.
    """

    if summary.get("status") != "ok" or _disabled() or not stadium_id or not kickoff_at:
        return summary
    try:
        stadium = nfl_stadiums.stadium_for(stadium_id)
        kickoff = datetime.fromisoformat(str(kickoff_at))
    except Exception:
        return summary
    if stadium is None:
        return summary
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    if kickoff <= current or kickoff - current > MAX_HORIZON:
        return summary

    if stadium.roof == "dome":
        summary["weather"] = {
            "status": "dome",
            "label": "Dome: no weather effect",
            "applied": False,
            "multiplier": 1.0,
            "reason": None,
            "forecast": None,
        }
        return summary

    retractable = stadium.roof == "retractable"
    fstate: dict[str, str] = {}
    forecast = forecast_for_game(
        stadium_id, kickoff_at, now=now, allow_retractable=retractable, state_out=fstate
    )
    roof_note = " (retractable roof, status unknown, reduced weight)" if retractable else " (outdoor)"
    if forecast is None:
        loading = fstate.get("state") == "loading"
        summary["weather"] = {
            "status": "loading" if loading else "unavailable",
            "label": "Weather loading: no adjustment" if loading else "Weather unavailable: no adjustment",
            "applied": False,
            "multiplier": 1.0,
            "reason": None,
            "forecast": None,
        }
        return summary

    adjustment = weather_adjustment(position, forecast, weight=RETRACTABLE_WEIGHT if retractable else 1.0)
    conditions = forecast_label(forecast)
    applied = adjustment["reason"] is not None
    if applied:
        noun = _OUTLOOK_NOUN.get(str(position or "").upper(), "outlook")
        label = f"Weather: {conditions}{roof_note} \u2192 {noun} {_signed_pct(adjustment['multiplier'])}"
    else:
        label = f"Weather: {conditions}{roof_note}: no adjustment"
    block: dict[str, Any] = {
        "status": "retractable" if retractable else "outdoor",
        "label": label,
        "applied": applied,
        "multiplier": adjustment["multiplier"],
        "reason": adjustment["reason"],
        "forecast": {**forecast, "label": conditions},
    }
    if applied:
        block["points_before"] = summary.get("point_estimate")
        for key in ("point_estimate", "low", "high"):
            if isinstance(summary.get(key), (int, float)):
                summary[key] = round(float(summary[key]) * adjustment["multiplier"], 1)
    summary["weather"] = block
    return summary
