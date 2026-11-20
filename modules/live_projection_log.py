"""Forward log of live projected finals and matchup win probabilities, plus the weekly scorer.

coridian_: "audit our live game projections ... against real results" (docs/audits/2026-11-live-projection-calibration.md).

Volume is deliberately small: starters only, and at most one row per
(league, season, week, matchup, player, clock bucket), where the clock bucket is
the real game clock in 5-game-minute steps (0..11, see ``clock_bucket``), not the poll
cadence. A matchup-level row (``player_id = ''``) carries the win probability
for the same bucket. Bucket 99 is the final row (game over: ``actual`` is his final
score). The DB primary key makes duplicates impossible; writes use
``resolution=ignore-duplicates`` and an in-process set skips keys already sent.

Everything is fail-soft and off the request path (a daemon thread); the kill switch is
``DYNASTYGM_LIVE_PROJECTION_LOG`` (FLAG_REGISTRY, owner Zach). Table DDL:
docs/supabase_live_projection_snapshots.sql (service-role only, RLS on, no policies).
"""

from __future__ import annotations

import math
import threading
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

import requests

from modules import app_config, matchup_win_probability
from modules.coerce import float_finite_or_none as _num

FLAG = "DYNASTYGM_LIVE_PROJECTION_LOG"
TABLE = "live_projection_snapshots"
REPORT_TABLE = "live_projection_reports"
RETENTION_DAYS = 400
BUCKET_GAME_MINUTES = 5
FINAL_BUCKET = 99
_MAX_SENT_KEYS = 50_000
_CHUNK = 500

_lock = threading.Lock()
_sent: set[tuple] = set()


def enabled(*, environ: Mapping[str, Any] | None = None) -> bool:
    from modules.experimental_graduation import graduated_kill_switch_enabled

    return graduated_kill_switch_enabled(FLAG, environ=environ)


class Config:
    def __init__(self, url: str = "", key: str = "") -> None:
        self.url, self.key = url, key

    @property
    def configured(self) -> bool:
        return bool(self.url and self.key)


def load_config(*, environ: dict | None = None) -> Config:
    return Config(app_config.config_value("SUPABASE_URL", environ=environ),
                  app_config.config_value("SUPABASE_SERVICE_ROLE_KEY", environ=environ))


def _headers(config: Config, prefer: str = "") -> dict[str, str]:
    headers = {"apikey": config.key, "Authorization": f"Bearer {config.key}", "Content-Type": "application/json"}
    if prefer:
        headers["Prefer"] = prefer
    return headers


def clock_bucket(remaining: float) -> int:
    """Real-clock bucket: 0 = first 5 game minutes ... 11 = minutes 55-60, 12 = overtime/beyond. ``remaining`` is the 0-1 share of the game left."""

    elapsed_minutes = (1.0 - float(remaining)) * 60.0
    return max(0, min(12, int(math.floor(elapsed_minutes / BUCKET_GAME_MINUTES + 1e-9))))


def build_rows(league_id: str, season: int, week: int, my_roster_id: str, opponent_roster_id: str,
               my_starters: Sequence[Mapping[str, Any]], opponent_starters: Sequence[Mapping[str, Any]],
               win_probability: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Pure: one matchup payload -> deduplicable rows (may be empty)."""

    a_is_me = str(my_roster_id) <= str(opponent_roster_id)
    roster_a, roster_b = (my_roster_id, opponent_roster_id) if a_is_me else (opponent_roster_id, my_roster_id)
    sides = (("a", my_starters if a_is_me else opponent_starters), ("b", opponent_starters if a_is_me else my_starters))
    base = {"league_id": str(league_id), "season": int(season), "week": int(week), "roster_a": str(roster_a), "roster_b": str(roster_b)}
    rows: list[dict[str, Any]] = []
    live_remaining: list[float] = []
    all_final = True
    count = 0
    for side, starters in sides:
        for s in starters or []:
            count += 1
            pid = str(s.get("player_id") or "").strip()
            started, final = s.get("game_started") is True, s.get("game_final") is True
            if not (started and final):
                all_final = False
            if not pid or not started:
                continue
            actual = _num(s.get("actual_points"))
            if actual is None:
                continue
            row = {**base, "player_id": pid, "side": side, "position": str(s.get("position") or "")[:8] or None, "actual": actual}
            if final:
                rows.append({**row, "clock_bucket": FINAL_BUCKET, "remaining": 0.0})
                continue
            remaining = matchup_win_probability.game_fraction_remaining(s)
            if remaining is None or remaining <= 0.0:
                continue
            live_remaining.append(remaining)
            proj = s.get("projection") or {}
            projection = _num(proj.get("point_estimate")) if proj.get("status") == "ok" else None
            rows.append({**row, "clock_bucket": clock_bucket(remaining), "remaining": round(remaining, 4), "projection": projection,
                         "projected_final": _num(s.get("projected_final"))})
    wp = win_probability or {}
    if wp.get("available") is True and count and (live_remaining or all_final):
        p_me = _num(wp.get("probability"))
        if p_me is not None:
            mean_remaining = 0.0 if all_final else sum(live_remaining) / len(live_remaining)
            my_total, opp_total = _num(wp.get("my_projected_total")), _num(wp.get("opponent_projected_total"))
            rows.append({**base, "player_id": "", "side": "m", "clock_bucket": FINAL_BUCKET if all_final else clock_bucket(mean_remaining),
                         "remaining": round(mean_remaining, 4), "win_prob_a": round(p_me if a_is_me else 1.0 - p_me, 4),
                         "total_a": my_total if a_is_me else opp_total, "total_b": opp_total if a_is_me else my_total})
    return rows


def _key(row: Mapping[str, Any]) -> tuple:
    return (row["league_id"], row["season"], row["week"], row["roster_a"], row["roster_b"], row["player_id"], row["clock_bucket"])


def _post(config: Config, rows: list[dict[str, Any]]) -> None:
    for start in range(0, len(rows), _CHUNK):
        chunk = rows[start:start + _CHUNK]
        try:
            response = requests.post(
                f"{config.url}/rest/v1/{TABLE}", headers=_headers(config, "resolution=ignore-duplicates,return=minimal"),
                params={"on_conflict": "league_id,season,week,roster_a,roster_b,player_id,clock_bucket"}, json=chunk, timeout=10)
            ok = response.status_code < 400
        except Exception:
            ok = False
        if not ok:
            with _lock:
                for row in chunk:
                    _sent.discard(_key(row))


def maybe_log(league_id: str, season: Any, week: Any, my_roster_id: str, opponent_roster_id: str,
              my_starters: Sequence[Mapping[str, Any]], opponent_starters: Sequence[Mapping[str, Any]],
              win_probability: Mapping[str, Any] | None, *, environ: dict | None = None, background: bool = True) -> int:
    """Queue any new (not yet sent) rows for this matchup poll. Never raises; returns the number queued."""

    try:
        if not enabled(environ=environ):
            return 0
        config = load_config(environ=environ)
        if not config.configured or season is None or week is None or not my_roster_id or not opponent_roster_id:
            return 0
        rows = build_rows(league_id, int(season), int(week), my_roster_id, opponent_roster_id, my_starters, opponent_starters, win_probability)
        with _lock:
            fresh = [r for r in rows if _key(r) not in _sent]
            if len(_sent) > _MAX_SENT_KEYS:
                _sent.clear()
            _sent.update(_key(r) for r in fresh)
        if not fresh:
            return 0
        if background:
            threading.Thread(target=_post, args=(config, fresh), daemon=True).start()
        else:
            _post(config, fresh)
        return len(fresh)
    except Exception:
        return 0


# ----------------------------------------------------------------------------- weekly scoring (pure)
def _bucket_label(elapsed: float) -> str:
    return "0-25" if elapsed < 0.25 else "25-50" if elapsed < 0.5 else "50-75" if elapsed < 0.75 else "75-100"


def score_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Pure: snapshot rows for ONE season-week -> projection error and win-probability calibration vs the final rows."""

    finals: dict[tuple, float] = {}
    for r in rows:
        if r.get("player_id") and r.get("clock_bucket") == FINAL_BUCKET:
            finals[(r["league_id"], r["roster_a"], r["roster_b"], r["player_id"])] = float(r["actual"])
    stats: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in rows:
        if not r.get("player_id") or r.get("clock_bucket") == FINAL_BUCKET:
            continue
        final = finals.get((r["league_id"], r["roster_a"], r["roster_b"], r["player_id"]))
        pf, proj, rem, act = _num(r.get("projected_final")), _num(r.get("projection")), _num(r.get("remaining")), _num(r.get("actual"))
        if final is None or pf is None or proj is None or rem is None or act is None:
            continue
        b = stats[_bucket_label(1.0 - rem)]
        b["n"] += 1
        for name, value in (("live", pf), ("pregame", proj), ("naive", act + rem * proj)):
            b[f"{name}_abs"] += abs(value - final)
            b[f"{name}_err"] += value - final
    projection = {k: {"n": int(v["n"]), **{f"{m}_{kind}": round(v[f"{m}_{'abs' if kind == 'mae' else 'err'}"] / v["n"], 3)
                                           for m in ("live", "pregame", "naive") for kind in ("mae", "bias")}} for k, v in stats.items()}
    team_final: dict[tuple, dict[str, float]] = defaultdict(lambda: {"a": 0.0, "b": 0.0})
    for r in rows:
        if r.get("player_id") and r.get("clock_bucket") == FINAL_BUCKET and r.get("side") in ("a", "b"):
            team_final[(r["league_id"], r["roster_a"], r["roster_b"])][r["side"]] += float(r["actual"])
    brier_sum, n_wp = defaultdict(float), defaultdict(int)
    bins = [[0, 0.0, 0.0] for _ in range(10)]
    for r in rows:
        if r.get("player_id") or r.get("clock_bucket") == FINAL_BUCKET:
            continue
        p = _num(r.get("win_prob_a"))
        tf = team_final.get((r["league_id"], r["roster_a"], r["roster_b"]))
        rem = _num(r.get("remaining"))
        if p is None or tf is None or rem is None or tf["a"] == tf["b"]:
            continue
        y = 1.0 if tf["a"] > tf["b"] else 0.0
        label = _bucket_label(1.0 - rem)
        brier_sum[label] += (p - y) ** 2
        n_wp[label] += 1
        for pp, yy in ((p, y), (1.0 - p, 1.0 - y)):
            i = min(9, int(pp * 10))
            bins[i][0] += 1
            bins[i][1] += pp
            bins[i][2] += yy
    return {
        "projection_by_elapsed": projection,
        "win_prob_brier_by_elapsed": {k: {"n": n_wp[k], "brier": round(brier_sum[k] / n_wp[k], 4)} for k in n_wp},
        "win_prob_reliability": [{"bin": f"{i * 10}-{i * 10 + 10}", "n": int(n), "predicted": round(sp / n, 3), "actual": round(sy / n, 3)}
                                 for i, (n, sp, sy) in enumerate(bins) if n],
        "final_starters": len(finals),
        "scored_matchups": len([1 for t in team_final.values() if t["a"] != t["b"]]),
    }


def render_markdown(season: int, week: int, scored: Mapping[str, Any]) -> str:
    lines = [f"### {season} week {week}: {scored.get('scored_matchups', 0)} matchups, {scored.get('final_starters', 0)} final starter rows", "",
             "| elapsed | n | live MAE | naive MAE | pregame MAE | live bias |", "|---|---|---|---|---|---|"]
    for label in ("0-25", "25-50", "50-75", "75-100"):
        v = (scored.get("projection_by_elapsed") or {}).get(label)
        if v:
            lines.append(f"| {label}% | {v['n']} | {v['live_mae']} | {v['naive_mae']} | {v['pregame_mae']} | {v['live_bias']} |")
    lines += ["", "| elapsed | matchup rows | Brier |", "|---|---|---|"]
    for label, v in sorted((scored.get("win_prob_brier_by_elapsed") or {}).items()):
        lines.append(f"| {label}% | {v['n']} | {v['brier']} |")
    lines += ["", "| predicted bin | n | predicted | actual |", "|---|---|---|---|"]
    for b in scored.get("win_prob_reliability") or []:
        lines.append(f"| {b['bin']}% | {b['n']} | {b['predicted']} | {b['actual']} |")
    return "\n".join(lines)


# ----------------------------------------------------------------------------- weekly scoring (I/O)
def fetch_rows(config: Config, since: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    offset = 0
    while True:
        response = requests.get(
            f"{config.url}/rest/v1/{TABLE}", headers=_headers(config), timeout=30,
            params={"select": "*", "snapshot_at": f"gte.{since}", "order": "snapshot_at.asc", "limit": "1000", "offset": str(offset)})
        response.raise_for_status()
        page = response.json()
        out.extend(page)
        if len(page) < 1000:
            return out
        offset += 1000


def prune(config: Config, *, today: date | None = None) -> bool:
    cutoff = ((today or datetime.now(timezone.utc).date()) - timedelta(days=RETENTION_DAYS)).isoformat()
    try:
        r1 = requests.delete(f"{config.url}/rest/v1/{TABLE}", headers=_headers(config, "return=minimal"), params={"snapshot_at": f"lt.{cutoff}"}, timeout=30)
        r2 = requests.delete(f"{config.url}/rest/v1/{REPORT_TABLE}", headers=_headers(config, "return=minimal"), params={"scored_at": f"lt.{cutoff}"}, timeout=30)
    except Exception:
        return False
    return r1.status_code < 400 and r2.status_code < 400


def run_weekly_scoring(*, environ: dict | None = None, lookback_days: int = 9) -> dict[str, Any]:
    """Score every (season, week) with snapshots in the lookback window; upsert one report row per season-week (idempotent)."""

    config = load_config(environ=environ)
    stats: dict[str, Any] = {"ok": False, "configured": config.configured, "weeks": [], "errors": [], "markdown": ""}
    if not config.configured:
        stats["errors"].append("Supabase service-role is not configured.")
        return stats
    since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
    try:
        rows = fetch_rows(config, since)
    except Exception as exc:
        stats["errors"].append(f"read failed: {exc}")
        return stats
    by_week: dict[tuple, list] = defaultdict(list)
    for r in rows:
        by_week[(int(r["season"]), int(r["week"]))].append(r)
    parts = []
    for (season, week), week_rows in sorted(by_week.items()):
        scored = score_rows(week_rows)
        parts.append(render_markdown(season, week, scored))
        payload = {"season": season, "week": week, "scored_at": datetime.now(timezone.utc).isoformat(), "metrics": scored}
        try:
            response = requests.post(f"{config.url}/rest/v1/{REPORT_TABLE}", headers=_headers(config, "resolution=merge-duplicates,return=minimal"),
                                     params={"on_conflict": "season,week"}, json=[payload], timeout=30)
            if response.status_code >= 400:
                stats["errors"].append(f"report upsert {season}-{week}: status {response.status_code}")
        except Exception as exc:
            stats["errors"].append(f"report upsert failed: {exc}")
        stats["weeks"].append({"season": season, "week": week, "scored_matchups": scored["scored_matchups"]})
    stats["markdown"] = "\n\n".join(parts) or "No live snapshots in the window."
    stats["pruned"] = prune(config)
    stats["ok"] = not stats["errors"]
    return stats
