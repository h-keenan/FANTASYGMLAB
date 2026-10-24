"""Conservative, structured news-driven value events (off by default).

Until now a player's value ignored news until the underlying Sleeper status
changed (``news_factor`` was a hard-coded 0.0).  This module turns a small set of
*structured, high-signal* feed transitions into a bounded, decaying, expiring
value adjustment with full provenance.  It deliberately does NOT read headlines.

Gate: env ``DYNASTYGM_NEWS_VALUE_EVENTS`` (default ``0``).  With the flag off,
nothing here is imported on the hot path and values are byte-identical.

Design rules (evidence in docs/news-value-events-2026-10.md and
scripts/news_value_events_backtest.py):

- Only event types in ``EVENT_TYPES`` with ``enabled=True`` ever move a value.
  A type is enabled only when the walk-forward backtest shows it predicts
  next-4-game output better than the status-quo value in every test season.
- Magnitude is capped per type, decays exponentially with age, and hard-expires
  at ``max_age_days`` or as soon as the live feed no longer carries the status
  (the event "clears").
- The adjustment is *incremental* to the existing injury multiplier
  (``rankings.injury_multiplier``): ``min(1, event_factor / injury_multiplier)``.
  A player the feed already discounts by at least as much gets no second hit,
  but the active event is still reported in the provenance.
- One place: ``rankings.compose_composite_score`` calls ``apply_to_frame``, so
  rankings, Trade Hub, Analyzer and Waivers all see the same number.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

ENV_FLAG = "DYNASTYGM_NEWS_VALUE_EVENTS"
ENV_PATH = "DYNASTYGM_NEWS_VALUE_EVENTS_PATH"
DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "news_value_events.json"
SOURCE_SLEEPER_STATUS = "sleeper_injury_status"

# Share of the composite that is current-season-sensitive
# (rankings COMPOSITE_WEIGHT_PRODUCTION .12 + OPPORTUNITY .10 + ROLE .06).  A short
# availability shock moves those factors, not the long-horizon market/age terms.
CURRENT_SEASON_PASS_THROUGH = 0.28
# Measured on 2021-2025 (backtest): points in the first game after an established
# player is out are 69% below what the control group scores (0.28 vs 0.90 of
# trailing PPG).  Cap = pass-through * that shortfall, rounded down.
AVAILABILITY_OUT_SHORTFALL = 0.69


@dataclass(frozen=True)
class EventType:
    key: str
    enabled: bool
    max_reduction: float  # cap on fractional value reduction (0.19 == -19%)
    half_life_days: float
    max_age_days: float
    evidence: str


EVENT_TYPES: Dict[str, EventType] = {
    "availability_out": EventType(
        key="availability_out",
        enabled=True,
        max_reduction=round(CURRENT_SEASON_PASS_THROUGH * AVAILABILITY_OUT_SHORTFALL, 2),  # 0.19
        # shortfall vs control by game after the event: .69 .53 .41 .41 -> ~4 week half-life
        half_life_days=28.0,
        max_age_days=28.0,  # the backtest only measured four games; never extrapolate past it
        evidence="backtest 2023-2025: beats the static injury multiplier on next-4-game points in 3/3 seasons",
    ),
    "team_change": EventType(
        key="team_change",
        enabled=False,
        max_reduction=0.0,
        half_life_days=28.0,
        max_age_days=28.0,
        evidence="only 16 mid-season team changes across 2021-2025 with usable history; no detectable effect",
    ),
    "depth_chart_role": EventType(
        key="depth_chart_role",
        enabled=False,
        max_reduction=0.0,
        half_life_days=28.0,
        max_age_days=28.0,
        evidence="no point-in-time depth-chart history exists (one weekly snapshot); cannot be validated",
    ),
}

_lock = threading.Lock()


def is_enabled() -> bool:
    return str(os.environ.get(ENV_FLAG, "0")).strip().lower() in {"1", "true", "yes", "on"}


def store_path() -> Path:
    return Path(os.environ.get(ENV_PATH) or DEFAULT_PATH)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def classify_status(status: Any, injury_status: Any = "") -> Optional[str]:
    """Return the availability subtype for a Sleeper status pair, else None.

    Only unambiguous unavailability counts: Out, IR, PUP, Suspended.  Doubtful /
    Questionable are not events.
    """
    s = str(status or "").strip().lower()
    i = str(injury_status or "").strip().lower()
    if s in {"injured reserve", "ir"} or i in {"ir", "injured reserve"}:
        return "ir"
    if s in {"pup", "physically unable to perform"} or i in {"pup", "physically unable to perform"}:
        return "pup"
    if s in {"suspended", "sus"} or i in {"sus", "suspended", "suspension"}:
        return "suspended"
    if i == "out" or s == "out":
        return "out"
    return None


# ------------------------------------------------------------------ store
def load_events(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    p = Path(path) if path else store_path()
    try:
        data = json.loads(p.read_text())
        return [e for e in data if isinstance(e, dict)] if isinstance(data, list) else []
    except Exception:
        return []


def _save_events(events: List[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(events, fh, indent=1, sort_keys=True)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def record_status_changes(
    changes: Iterable[Mapping[str, Any]],
    *,
    now: Optional[datetime] = None,
    path: Optional[Path] = None,
) -> Dict[str, int]:
    """Open/clear events from feed transitions.

    ``changes`` items: ``player_id, old_status, old_injury_status, new_status,
    new_injury_status``.  A transition into an availability state opens an event
    (unless one is already open); a transition out of it clears the open event.
    """
    now = now or _now()
    p = Path(path) if path else store_path()
    opened = cleared = 0
    with _lock:
        events = load_events(p)
        open_by_pid = {e["player_id"]: e for e in events if not e.get("cleared_at")}
        for ch in changes:
            pid = str(ch.get("player_id") or "")
            if not pid:
                continue
            old = classify_status(ch.get("old_status"), ch.get("old_injury_status"))
            new = classify_status(ch.get("new_status"), ch.get("new_injury_status"))
            cur = open_by_pid.get(pid)
            if new and (cur is None):
                ev = {
                    "player_id": pid,
                    "type": "availability_out",
                    "subtype": new,
                    "source": SOURCE_SLEEPER_STATUS,
                    "detected_at": now.isoformat(),
                    "from": {"status": str(ch.get("old_status") or ""), "injury_status": str(ch.get("old_injury_status") or "")},
                    "to": {"status": str(ch.get("new_status") or ""), "injury_status": str(ch.get("new_injury_status") or "")},
                    "cleared_at": None,
                }
                events.append(ev)
                open_by_pid[pid] = ev
                opened += 1
            elif not new and cur is not None and old:
                cur["cleared_at"] = now.isoformat()
                open_by_pid.pop(pid, None)
                cleared += 1
        # keep the store small: drop events cleared or expired long ago
        horizon = 120 * 86400
        events = [
            e for e in events
            if (now - _parse(e["cleared_at"] or e["detected_at"])).total_seconds() < horizon
        ]
        if opened or cleared:
            _save_events(events, p)
    return {"opened": opened, "cleared": cleared}


# ------------------------------------------------------------- adjustment
def event_reduction(event: Mapping[str, Any], now: Optional[datetime] = None) -> float:
    """Fractional value reduction (0..cap) for one event at ``now``; 0 if off/expired/cleared."""
    spec = EVENT_TYPES.get(str(event.get("type")))
    if spec is None or not spec.enabled or event.get("cleared_at"):
        return 0.0
    now = now or _now()
    try:
        age_days = (now - _parse(str(event["detected_at"]))).total_seconds() / 86400.0
    except Exception:
        return 0.0
    if age_days < -1.0 or age_days > spec.max_age_days:  # >1 day in the future = bad timestamp
        return 0.0
    age_days = max(age_days, 0.0)  # tolerate small clock skew between cron host and app
    return spec.max_reduction * math.pow(0.5, age_days / spec.half_life_days)


def apply_to_frame(df, *, now: Optional[datetime] = None, events: Optional[List[Dict[str, Any]]] = None):
    """Adjust ``score`` and set ``news_factor`` / provenance columns.  No-op when the flag is off.

    Expects the frame after ``apply_injury_risk_fields`` (``status``,
    ``injury_status``, ``injury_multiplier``).  Rows whose live feed no longer
    carries an availability status are treated as cleared.
    """
    if df is None or len(df) == 0 or not is_enabled():
        return df
    now = now or _now()
    events = load_events() if events is None else events
    open_ev = {str(e["player_id"]): e for e in events if not e.get("cleared_at") and e.get("player_id")}
    work = df.copy()
    work["news_factor"] = 0.0
    work["news_event_type"] = ""
    work["news_event_provenance"] = ""
    if not open_ev or "player_id" not in work.columns:
        return work
    status = work["status"] if "status" in work.columns else [""] * len(work)
    injury = work["injury_status"] if "injury_status" in work.columns else [""] * len(work)
    inj_mult = work["injury_multiplier"] if "injury_multiplier" in work.columns else [1.0] * len(work)
    new_score = work["score"].astype(float).tolist() if "score" in work.columns else None
    factors, types, prov = [], [], []
    for k, (pid, st, inj, im) in enumerate(zip(work["player_id"].astype(str), status, injury, inj_mult)):
        ev = open_ev.get(pid)
        factor, etype, note = 0.0, "", ""
        if ev is not None and classify_status(st, inj) is not None:  # status still live => not cleared
            red = event_reduction(ev, now)
            if red > 0:
                try:
                    existing = float(im)
                except Exception:
                    existing = 1.0
                incremental = min(1.0, (1.0 - red) / existing) if existing > 0 else 1.0
                factor = incremental - 1.0
                etype = str(ev["type"])
                note = json.dumps(
                    {
                        "event_type": ev["type"],
                        "subtype": ev.get("subtype"),
                        "source": ev.get("source"),
                        "detected_at": ev.get("detected_at"),
                        "from": ev.get("from"),
                        "to": ev.get("to"),
                        "raw_reduction": round(red, 4),
                        "existing_injury_multiplier": existing,
                        "applied_adjustment": round(factor, 4),
                        "expires_at_days": EVENT_TYPES[etype].max_age_days,
                    },
                    sort_keys=True,
                )
                if new_score is not None:
                    new_score[k] = new_score[k] * incremental
        factors.append(round(factor, 4))
        types.append(etype)
        prov.append(note)
    work["news_factor"] = factors
    work["news_event_type"] = types
    work["news_event_provenance"] = prov
    if new_score is not None:
        work["score"] = [max(0, int(round(v))) for v in new_score]
    return work
