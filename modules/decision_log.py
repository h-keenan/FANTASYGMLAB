"""Decision log, outcome grading and "Your track record" (Decision Memory depth).

Three jobs, all honest about sample size and luck:

1. Record what we advised and what the user did (accepted / ignored / did the
   opposite), per user, in `decision_log` (docs/supabase_decision_log.sql).
   Trade ideas also flow through the existing `trade_outcomes` loop, tagged by
   `trade_summary.source` ("advice" for a Trade Hub idea, "own" for the user's
   own Trade Analyzer call), so trades need no new table.
2. Grade each decision with REAL results: PPR points the recommended side
   scored minus the alternative's, over the weeks since (same production
   approximation as modules.trade_outcome_results). The grading sweep runs in
   the existing trade-outcome-result-sweep workflow.
3. Roll graded decisions into a track record and a calibration table.

Honesty rules (each one a deliberate multi-factor guard, not a single rule):
- Nothing is a "win" or "loss" unless the edge clears the same per-week noise
  threshold the trade verdicts use; smaller edges are "even".
- Every number ships with its sample size and a reliability label; below
  MIN_TRACK_SAMPLE we show counts only, below MIN_CALIBRATION_SAMPLE per
  confidence bucket we never touch advice wording.
- "Advice vs your calls" only claims a difference when it is more than ~2
  standard errors; otherwise it says the gap is within noise (luck).
- Trades the user did not make cannot be graded (no real result exists), so
  trade advice quality is measured on executed trades only, and says so.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import requests

from modules import trade_outcome_results as tor

DECISION_LOG_TABLE = "decision_log"
KINDS = ("trade_idea", "waiver_add", "start_sit", "stance")
GRADED_KINDS = ("waiver_add", "start_sit")  # have two player sets we can score
ACTIONS = ("shown", "accepted", "ignored", "opposite")
CONFIDENCES = ("low", "medium", "high")

GRADE_DELAY_DAYS = 21
MIN_TRACK_SAMPLE = 5
MIN_CALIBRATION_SAMPLE = 10
NOISE_PER_WEEK = tor.PRODUCTION_THRESHOLD_PER_WEEK


def _text(value: Any, limit: int = 80) -> str:
    return "" if value is None else str(value).strip()[:limit]


def _id_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [i for i in (_text(v, 64) for v in value[:10]) if i]


def normalize_decision(
    *, kind: str, rec_key: str, league_id: str = "", action: str | None = None,
    confidence: str = "", recommended_ids: Any = None, alternative_ids: Any = None,
    label: str = "", names: Any = None,
) -> dict[str, Any] | None:
    """Validate one client submission into an insert/upsert row, or None.

    `action=None` is a pure "shown" ping: it omits action/acted_at so an
    upsert can never downgrade a row the user has already acted on."""

    kind, key = _text(kind, 20), _text(rec_key, 160)
    if kind not in KINDS or not key:
        return None
    level = _text(confidence, 10).lower()
    row: dict[str, Any] = {
        "kind": kind,
        "rec_key": key,
        "league_id": _text(league_id, 64),
        "confidence": level if level in CONFIDENCES else "",
        "snapshot": {
            "recommended_ids": _id_list(recommended_ids),
            "alternative_ids": _id_list(alternative_ids),
            "label": _text(label, 120),
            "names": [n for n in (_text(v, 60) for v in (names if isinstance(names, list) else [])[:10]) if n],
        },
    }
    if action is not None:
        action = _text(action, 12).lower()
        if action not in ACTIONS:
            return None
        row["action"] = action
        if action != "shown":
            row["acted_at"] = datetime.now(timezone.utc).isoformat()
    return row


def _days_since(iso: Any, now: datetime) -> int | None:
    try:
        when = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except Exception:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0, (now - when).days)


def _outcome_for(per_week: float) -> str:
    return "right" if per_week >= NOISE_PER_WEEK else "wrong" if per_week <= -NOISE_PER_WEEK else "even"


def grade_decision(row: Mapping[str, Any], season_stats: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Pure grade: recommended side's real PPR points minus the alternative's.

    edge_pts > 0 means following the advice would (or did) come out ahead."""

    now = now or datetime.now(timezone.utc)
    snap = row.get("snapshot") if isinstance(row.get("snapshot"), Mapping) else {}
    rec = [{"player_id": i} for i in _id_list(snap.get("recommended_ids"))]
    alt = [{"player_id": i} for i in _id_list(snap.get("alternative_ids"))]
    days = _days_since(row.get("shown_at"), now)
    if not rec or not alt:
        return {"status": "insufficient_data", "reason": "no_alternative", "days": days}
    weeks = tor.weeks_elapsed_for(days)
    rec_p = tor._side_production(rec, season_stats, weeks)
    alt_p = tor._side_production(alt, season_stats, weeks)
    if not (rec_p["has_data"] and alt_p["has_data"]):
        return {"status": "insufficient_data", "reason": "no_stat_data_yet", "days": days}
    n_weeks = max(rec_p["weeks_counted"], alt_p["weeks_counted"], 1)
    edge = round(rec_p["points_ppr"] - alt_p["points_ppr"], 1)
    per_week = round(edge / n_weeks, 2)
    return {
        "status": "ready", "outcome": _outcome_for(per_week), "edge_pts": edge, "avg_edge_per_week": per_week,
        "weeks_counted": n_weeks, "recommended_pts": rec_p["points_ppr"], "alternative_pts": alt_p["points_ppr"],
        "days": days,
    }


# ---- unified graded items -------------------------------------------------

def items_from_trades(trade_rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Confirmed trades with a real computed result -> track-record items."""

    items = []
    for row in trade_rows:
        if row.get("outcome") != "yes":
            continue
        result = row.get("result_summary") if isinstance(row.get("result_summary"), Mapping) else None
        prod = result.get("production") if result and result.get("status") == "ready" else None
        if not isinstance(prod, Mapping) or prod.get("net_points_ppr") is None:
            continue
        summary = row.get("trade_summary") if isinstance(row.get("trade_summary"), Mapping) else {}
        per_week = float(prod.get("avg_net_per_week") or 0.0)
        items.append({
            "kind": "trade_idea",
            "source": "advice" if summary.get("source") == "advice" else "own",
            "followed": True,
            "edge_pts": float(prod["net_points_ppr"]),
            "outcome": _outcome_for(per_week),
            "confidence": str(summary.get("confidence") or ""),
        })
    return items


def items_from_decisions(decision_rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    items = []
    for row in decision_rows:
        result = row.get("result") if isinstance(row.get("result"), Mapping) else None
        if not result or result.get("status") != "ready":
            continue
        action = str(row.get("action") or "shown")
        if action == "shown":
            continue  # unanswered: not yet a decision
        items.append({
            "kind": str(row.get("kind") or ""), "source": "advice", "followed": action == "accepted",
            "edge_pts": float(result.get("edge_pts") or 0.0), "outcome": str(result.get("outcome") or "even"),
            "confidence": str(row.get("confidence") or ""),
        })
    return items


def _reliability(n: int) -> str:
    return "too_early" if n < MIN_TRACK_SAMPLE else "early" if n < MIN_CALIBRATION_SAMPLE else "solid"


def _mean_se(values: list[float]) -> tuple[float, float]:
    n = len(values)
    if n == 0:
        return 0.0, 0.0
    mean = sum(values) / n
    if n < 2:
        return mean, float("inf")
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return mean, math.sqrt(var / n)


def _hit_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    decided = [i for i in items if i["outcome"] in ("right", "wrong")]
    n = len(items)
    right = sum(1 for i in decided if i["outcome"] == "right")
    return {
        "n": n, "right": right, "wrong": len(decided) - right, "even": n - len(decided),
        "hit_rate": round(right / len(decided), 3) if len(decided) >= MIN_TRACK_SAMPLE else None,
        "mean_edge_pts": round(sum(i["edge_pts"] for i in items) / n, 1) if n else None,
        "reliability": _reliability(n),
    }


def _compare(a: list[float], b: list[float]) -> dict[str, Any]:
    """Advice-followed vs own calls. Claims a gap only past ~2 SE."""

    if len(a) < MIN_TRACK_SAMPLE or len(b) < MIN_TRACK_SAMPLE:
        return {"verdict": "too_early"}
    ma, sa = _mean_se(a)
    mb, sb = _mean_se(b)
    se = math.sqrt(sa * sa + sb * sb)
    diff = ma - mb
    if se == 0 or abs(diff) < 2 * se:
        return {"verdict": "within_noise", "diff_pts": round(diff, 1)}
    return {"verdict": "advice_ahead" if diff > 0 else "own_ahead", "diff_pts": round(diff, 1)}


def build_track_record(
    trade_rows: list[Mapping[str, Any]], decision_rows: list[Mapping[str, Any]], *, is_pro: bool,
) -> dict[str, Any]:
    """Basic outcome history is free; advanced analytics are Pro."""

    trade_items = items_from_trades(trade_rows)
    confirmed = sum(1 for r in trade_rows if r.get("outcome") == "yes")
    record: dict[str, Any] = {
        "ok": True,
        "basic": {
            "trades_confirmed": confirmed,
            "trades_graded": len(trade_items),
            "worked_out": sum(1 for i in trade_items if i["outcome"] == "right"),
            "didnt_pan_out": sum(1 for i in trade_items if i["outcome"] == "wrong"),
            "even": sum(1 for i in trade_items if i["outcome"] == "even"),
            "net_points_total": round(sum(i["edge_pts"] for i in trade_items), 1),
            "reliability": _reliability(len(trade_items)),
        },
        "is_pro": is_pro,
        "advanced": None,
    }
    if not is_pro:
        return record

    items = trade_items + items_from_decisions(decision_rows)
    advice = [i for i in items if i["source"] == "advice"]
    own = [i for i in items if i["source"] == "own"]
    followed = [i for i in advice if i["followed"]]
    skipped = [i for i in advice if not i["followed"]]
    calibration = {}
    for level in CONFIDENCES:
        bucket = [i for i in advice if i["confidence"] == level]
        calibration[level] = {**_hit_summary(bucket), "supported": len(bucket) >= MIN_CALIBRATION_SAMPLE}
    by_kind = {k: _hit_summary([i for i in advice if i["kind"] == k]) for k in KINDS if any(i["kind"] == k for i in advice)}
    record["advanced"] = {
        "advice": _hit_summary(advice),
        "own_calls": _hit_summary(own),
        "followed": _hit_summary(followed),
        "skipped": _hit_summary(skipped),
        "compare": _compare([i["edge_pts"] for i in followed], [i["edge_pts"] for i in own]),
        "calibration": calibration,
        "by_kind": by_kind,
        "caveat": "Only trades you made can be graded, so trade advice is judged on executed trades.",
    }
    return record


# ---- grading sweep (service role) -----------------------------------------

def fetch_ungraded_decisions(config: tor.ResultSweepConfig) -> list[dict[str, Any]]:
    if not config.configured:
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=GRADE_DELAY_DAYS)).isoformat()
    try:
        response = requests.get(
            f"{config.url}/rest/v1/{DECISION_LOG_TABLE}", headers=tor._headers(config), timeout=15,
            params={"select": "id,kind,action,snapshot,shown_at", "graded_at": "is.null",
                    "kind": f"in.({','.join(GRADED_KINDS)})", "shown_at": f"lte.{cutoff}", "limit": "500"},
        )
        rows = response.json() if response.status_code < 400 else []
    except Exception:
        return []
    return [r for r in rows if isinstance(r, Mapping)] if isinstance(rows, list) else []


def store_decision_grade(config: tor.ResultSweepConfig, *, decision_id: str, result: dict[str, Any]) -> None:
    if not config.configured or not decision_id:
        return
    try:
        requests.patch(
            f"{config.url}/rest/v1/{DECISION_LOG_TABLE}", headers=tor._headers(config, prefer="return=minimal"),
            params={"id": f"eq.{decision_id}"}, timeout=15,
            json={"result": result, "graded_at": datetime.now(timezone.utc).isoformat()},
        )
    except Exception:
        pass


def run_decision_grading_sweep(*, environ: dict | None = None, secrets: Any = None) -> dict[str, Any]:
    """Grade due decision_log rows. Never raises; fails soft before the SQL is applied."""

    from modules import sleeper

    config = tor.load_result_sweep_config(environ=environ, secrets=secrets)
    stats: dict[str, Any] = {"configured": config.configured, "checked": 0, "graded": 0, "errors": []}
    if not config.configured:
        return stats
    rows = fetch_ungraded_decisions(config)
    if not rows:
        return stats
    season_stats = sleeper.get_season_player_stats(retain_weekly=True) or {}
    for row in rows:
        stats["checked"] += 1
        try:
            result = grade_decision(row, season_stats)
            store_decision_grade(config, decision_id=str(row.get("id") or ""), result=result)
            stats["graded"] += 1
        except Exception as exc:
            stats["errors"].append(f"{row.get('id')}: {exc}")
    return stats
