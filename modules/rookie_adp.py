"""Rookie + dynasty (startup) ADP feed from Fantasy Football Calculator.

Source decision and licence notes: docs/audits/2026-11-rookie-adp-sources.md.
Short version: FFC's public ``/api/v1/adp/{format}`` offers ``rookie`` ("Dynasty
Rookie") and ``dynasty`` for 1QB only (no superflex format exists), is free to use,
and is credited on screen as "Fantasy Football Calculator". The scheduled job
(workflow ``rookie-adp-snapshot.yml``) is the only thing that fetches; it
upserts one row per (format, date, FFC player) into ``adp_snapshots``
(``docs/supabase_adp_snapshots.sql``). The API only *reads* that table, fail-soft.

Honesty rules:
  * An empty FFC window (rookie ADP only exists in the rookie-draft season) stores
    nothing. Nothing is ever invented or carried forward under a new date.
  * Players map to Sleeper ids by exact normalized name + position (+ team to break a
    tie). Ambiguous or unknown names stay unmatched (``sleeper_id`` NULL) and are
    reported by the run; we never guess.
  * ADP is one signal. ``value_vs_adp`` is paired with our own rank, sample size and
    spread so callers never present ADP alone.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping

import requests

from modules import app_config, player_names

SOURCE = "ffc"
SOURCE_LABEL = "Fantasy Football Calculator"
SOURCE_URL = "https://fantasyfootballcalculator.com/adp"
API_BASE = "https://fantasyfootballcalculator.com/api/v1/adp"
ADP_TABLE = "adp_snapshots"
PLAYERS_DB_PATH = "data/players.db"
USER_AGENT = "DynastyGM-adp-feed/1.0"
TEAMS = 12
POSITIONS = ("QB", "RB", "WR", "TE")

# our format key -> FFC endpoint. Superflex is NOT offered by any approved free source.
FORMATS: dict[str, dict[str, str]] = {
    "rookie_1qb": {"endpoint": "rookie", "qb_format": "1qb", "draft_kind": "rookie"},
    "dynasty_1qb": {"endpoint": "dynasty", "qb_format": "1qb", "draft_kind": "startup"},
}

# Thin samples are flagged, not hidden.
THIN_SAMPLE_DRAFTS = 10
ALIGNED_BAND = 3.0
TREND_MIN_DAYS = 7
_UPSERT_CHUNK = 200
_CACHE_TTL_SECONDS = 1800


def user_draft_aggregate_enabled(*, environ: Mapping[str, Any] | None = None) -> bool:
    """HELD feature flag (default OFF): an ADP aggregate from users' connected Sleeper
    leagues. Needs owner approval (Sleeper API terms are non-commercial; privacy policy).
    No collector exists in this codebase; this only documents and gates the seam."""

    value = app_config.config_value("ADP_USER_DRAFT_AGGREGATE", environ=environ)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AdpConfig:
    url: str = ""
    service_role_key: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.url and self.service_role_key)


def load_config(*, environ: Mapping[str, Any] | None = None) -> AdpConfig:
    return AdpConfig(
        url=app_config.config_value("SUPABASE_URL", environ=environ).rstrip("/"),
        service_role_key=app_config.config_value("SUPABASE_SERVICE_ROLE_KEY", environ=environ),
    )


def _headers(config: AdpConfig, *, prefer: str = "") -> dict[str, str]:
    headers = {
        "apikey": config.service_role_key,
        "Authorization": f"Bearer {config.service_role_key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


# --- fetch + parse (pure parse) -------------------------------------------------


def fetch_ffc(fmt: str, year: int, *, teams: int = TEAMS, session: Any = None) -> dict[str, Any] | None:
    endpoint = FORMATS[fmt]["endpoint"]
    getter = (session or requests).get
    try:
        response = getter(
            f"{API_BASE}/{endpoint}",
            params={"teams": teams, "year": year},
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        if response.status_code != 200:
            return None
        payload = response.json()
    except Exception:
        return None
    if not isinstance(payload, dict) or payload.get("status") != "Success":
        return None
    return payload


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def parse_payload(payload: Mapping[str, Any] | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """(meta, players) with only well-formed rows kept. Empty window -> no players."""

    if not isinstance(payload, Mapping):
        return {}, []
    meta = payload.get("meta") if isinstance(payload.get("meta"), Mapping) else {}
    rows: list[dict[str, Any]] = []
    for raw in payload.get("players") or []:
        if not isinstance(raw, Mapping):
            continue
        adp = _num(raw.get("adp"))
        name = str(raw.get("name") or "").strip()
        position = str(raw.get("position") or "").strip().upper()
        if adp is None or adp <= 0 or not name or position not in POSITIONS:
            continue
        rows.append(
            {
                "ffc_player_id": str(raw.get("player_id") or ""),
                "name": name,
                "position": position,
                "team": str(raw.get("team") or "").strip().upper(),
                "adp": round(adp, 2),
                "adp_formatted": str(raw.get("adp_formatted") or ""),
                "times_drafted": int(_num(raw.get("times_drafted")) or 0),
                "high": _num(raw.get("high")),
                "low": _num(raw.get("low")),
                "stdev": _num(raw.get("stdev")),
            }
        )
    return dict(meta), rows


# --- id mapping (exact, never guessed) -------------------------------------------


def load_pool(db_path: str = PLAYERS_DB_PATH) -> list[dict[str, Any]]:
    """Read-only SQL read of the committed player table (never rankings.load_players)."""

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return []
    try:
        cur = conn.execute(
            "select player_id, name, position, team from players "
            "where position in ('QB','RB','WR','TE') and name is not null"
        )
        return [
            {"player_id": str(r[0]), "name": r[1], "position": str(r[2]).upper(), "team": str(r[3] or "").upper()}
            for r in cur.fetchall()
        ]
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def build_name_index(pool: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in pool:
        key = (player_names.normalize_player_name(row.get("name")), str(row.get("position") or "").upper())
        if key[0]:
            index.setdefault(key, []).append(row)
    return index


def match_rows(
    rows: list[dict[str, Any]], pool: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Attach ``sleeper_id`` by exact normalized name + position, team breaking ties.
    Returns (rows, unmatched) where unmatched lists name/reason for the run report."""

    index = build_name_index(pool)
    unmatched: list[dict[str, Any]] = []
    out: list[dict[str, Any]] = []
    for row in rows:
        candidates = index.get((player_names.normalize_player_name(row["name"]), row["position"]), [])
        if len(candidates) > 1 and row.get("team"):
            narrowed = [c for c in candidates if c.get("team") == row["team"]]
            candidates = narrowed or candidates
        sleeper_id: str | None = None
        if len(candidates) == 1:
            sleeper_id = candidates[0]["player_id"]
        else:
            unmatched.append(
                {
                    "name": row["name"],
                    "position": row["position"],
                    "team": row["team"],
                    "reason": "ambiguous" if candidates else "no_match",
                }
            )
        out.append({**row, "sleeper_id": sleeper_id})
    return out, unmatched


# --- store ----------------------------------------------------------------------


def build_db_rows(
    fmt: str, meta: Mapping[str, Any], matched: list[dict[str, Any]], *, snapshot_date: str
) -> list[dict[str, Any]]:
    spec = FORMATS[fmt]
    fetched_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for row in matched:
        rows.append(
            {
                "source": SOURCE,
                "format": fmt,
                "qb_format": spec["qb_format"],
                "snapshot_date": snapshot_date,
                "ffc_player_id": row["ffc_player_id"],
                "sleeper_id": row.get("sleeper_id"),
                "name": row["name"],
                "position": row["position"],
                "team": row["team"] or None,
                "adp": row["adp"],
                "adp_formatted": row["adp_formatted"] or None,
                "times_drafted": row["times_drafted"],
                "high": row["high"],
                "low": row["low"],
                "stdev": row["stdev"],
                "teams": meta.get("teams"),
                "total_drafts": meta.get("total_drafts"),
                "window_start": meta.get("start_date"),
                "window_end": meta.get("end_date"),
                "fetched_at": fetched_at,
            }
        )
    return rows


def store_rows(config: AdpConfig, rows: list[dict[str, Any]]) -> dict[str, Any]:
    stats: dict[str, Any] = {"rows_sent": 0, "errors": []}
    for start in range(0, len(rows), _UPSERT_CHUNK):
        chunk = rows[start : start + _UPSERT_CHUNK]
        try:
            response = requests.post(
                f"{config.url}/rest/v1/{ADP_TABLE}",
                headers=_headers(config, prefer="resolution=merge-duplicates,return=minimal"),
                params={"on_conflict": "source,format,snapshot_date,ffc_player_id"},
                json=chunk,
                timeout=30,
            )
        except Exception as exc:
            stats["errors"].append(f"request failed: {exc}")
            continue
        if response.status_code >= 400:
            stats["errors"].append(f"status {response.status_code}: {str(getattr(response, 'text', ''))[:200]}")
            continue
        stats["rows_sent"] += len(chunk)
    return stats


def run_snapshot(
    *, environ: Mapping[str, Any] | None = None, today: date | None = None, db_path: str = PLAYERS_DB_PATH
) -> dict[str, Any]:
    """The whole scheduled job. ``ok`` is False only for real failures (unconfigured
    Supabase, store errors, FFC unreachable for every format). An empty FFC window is
    reported as ``empty`` and is not a failure."""

    today = today or datetime.now(timezone.utc).date()
    config = load_config(environ=environ)
    report: dict[str, Any] = {"ok": True, "configured": config.configured, "formats": {}, "unmatched": []}
    if not config.configured:
        report["ok"] = False
        report["error"] = "Supabase service-role is not configured."
        return report
    pool = load_pool(db_path)
    reachable = 0
    for fmt in FORMATS:
        payload = fetch_ffc(fmt, today.year)
        if payload is None:
            report["formats"][fmt] = {"status": "fetch_failed"}
            continue
        reachable += 1
        meta, rows = parse_payload(payload)
        if not rows:
            report["formats"][fmt] = {"status": "empty", "window": [meta.get("start_date"), meta.get("end_date")]}
            continue
        matched, unmatched = match_rows(rows, pool)
        result = store_rows(config, build_db_rows(fmt, meta, matched, snapshot_date=today.isoformat()))
        report["formats"][fmt] = {
            "status": "stored" if not result["errors"] else "store_failed",
            "players": len(rows),
            "matched": sum(1 for r in matched if r.get("sleeper_id")),
            "total_drafts": meta.get("total_drafts"),
            **result,
        }
        report["unmatched"].extend({"format": fmt, **u} for u in unmatched)
        if result["errors"]:
            report["ok"] = False
    if reachable == 0:
        report["ok"] = False
        report["error"] = "FFC unreachable for every format."
    return report


# --- read (fail-soft, cached) -----------------------------------------------------

_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _get(config: AdpConfig, params: dict[str, str]) -> list[dict[str, Any]] | None:
    try:
        response = requests.get(
            f"{config.url}/rest/v1/{ADP_TABLE}", headers=_headers(config), params=params, timeout=6
        )
        if response.status_code != 200:
            return None
        data = response.json()
    except Exception:
        return None
    return data if isinstance(data, list) else None


def _first_per_player(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:  # already ordered newest-first
        sid = str(row.get("sleeper_id") or "")
        if sid and sid not in seen:
            seen[sid] = row
    return seen


def fetch_latest(fmt: str, *, config: AdpConfig | None = None) -> dict[str, Any]:
    """{"as_of", "total_drafts", "players": {sleeper_id: {adp, ..., trend}}} or {}.

    ``trend`` = ADP now minus ADP at the newest snapshot at least TREND_MIN_DAYS older
    (negative = rising, going earlier). None until two such snapshots exist."""

    config = config or load_config()
    if not config.configured or fmt not in FORMATS:
        return {}
    base = {"source": f"eq.{SOURCE}", "format": f"eq.{fmt}"}
    head = _get(config, {**base, "select": "snapshot_date", "order": "snapshot_date.desc", "limit": "1"})
    if not head:
        return {}
    as_of = str(head[0].get("snapshot_date") or "")
    current = _get(config, {**base, "snapshot_date": f"eq.{as_of}", "select": "*", "limit": "1000"})
    if not current:
        return {}
    try:
        cutoff = (date.fromisoformat(as_of) - timedelta(days=TREND_MIN_DAYS)).isoformat()
    except ValueError:
        cutoff = ""
    baseline: dict[str, dict[str, Any]] = {}
    if cutoff:
        older = _get(
            config,
            {
                **base,
                "snapshot_date": f"lte.{cutoff}",
                "select": "sleeper_id,adp,snapshot_date",
                "order": "snapshot_date.desc",
                "limit": "1000",
            },
        )
        baseline = _first_per_player(older or [])
    players: dict[str, dict[str, Any]] = {}
    for sid, row in _first_per_player(current).items():
        prev = baseline.get(sid)
        adp = _num(row.get("adp"))
        prev_adp = _num(prev.get("adp")) if prev else None
        players[sid] = {
            "adp": adp,
            "adp_formatted": row.get("adp_formatted"),
            "drafts": row.get("times_drafted"),
            "high": row.get("high"),
            "low": row.get("low"),
            "stdev": row.get("stdev"),
            "trend": round(adp - prev_adp, 1) if adp is not None and prev_adp is not None else None,
            "trend_since": prev.get("snapshot_date") if prev else None,
        }
    return {
        "as_of": as_of,
        "total_drafts": current[0].get("total_drafts"),
        "window_end": current[0].get("window_end"),
        "players": players,
    }


def latest_rows(fmt: str, *, config: AdpConfig | None = None) -> dict[str, Any]:
    """{"as_of", "total_drafts", "rows": [raw newest-snapshot rows incl. unmapped ones]} or {}.
    Unlike ``fetch_latest`` this keeps rows with no Sleeper id (college prospects, not yet NFL players)."""

    config = config or load_config()
    if not config.configured or fmt not in FORMATS:
        return {}
    base = {"source": f"eq.{SOURCE}", "format": f"eq.{fmt}"}
    head = _get(config, {**base, "select": "snapshot_date", "order": "snapshot_date.desc", "limit": "1"})
    if not head:
        return {}
    as_of = str(head[0].get("snapshot_date") or "")
    rows = _get(
        config,
        {**base, "snapshot_date": f"eq.{as_of}", "select": "name,position,team,sleeper_id,adp,adp_formatted,times_drafted,total_drafts", "limit": "1000"},
    )
    if not rows:
        return {}
    return {"as_of": as_of, "total_drafts": rows[0].get("total_drafts"), "rows": rows}


_rows_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def latest_rows_cached(fmt: str, *, config: AdpConfig | None = None) -> dict[str, Any]:
    now = time.time()
    hit = _rows_cache.get(fmt)
    if hit and now - hit[0] < _CACHE_TTL_SECONDS:
        return hit[1]
    try:
        value = latest_rows(fmt, config=config)
    except Exception:
        value = {}
    _rows_cache[fmt] = (now, value)
    return value


def find_prospect_adp(name: str, position: str, sleeper_id: str | None = None, *, snapshot: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    """Rookie ADP for one prospect: by Sleeper id when drafted and mapped, else by exact normalized
    name + position, only when that is unambiguous. None = "No ADP yet" (off-season, or not in the
    window). Never a guess and never a carried-forward value."""

    snap = snapshot if snapshot is not None else latest_rows_cached("rookie_1qb")
    rows = (snap or {}).get("rows") or []
    if not rows:
        return None
    hit = [r for r in rows if sleeper_id and str(r.get("sleeper_id") or "") == str(sleeper_id)]
    if not hit:
        key = player_names.normalize_player_name(name)
        hit = [r for r in rows if player_names.normalize_player_name(r.get("name") or "") == key and str(r.get("position") or "").upper() == str(position or "").upper()]
    if len(hit) != 1:
        return None
    adp = _num(hit[0].get("adp"))
    if adp is None:
        return None
    return {
        "adp": adp,
        "adp_formatted": hit[0].get("adp_formatted"),
        "drafts": hit[0].get("times_drafted"),
        "label": ONE_QB_LABEL,
        "source": attribution("rookie_1qb", {"as_of": snap.get("as_of"), "total_drafts": snap.get("total_drafts"), "players": {"x": 1}}),
    }


def newest_snapshot_date(config: AdpConfig | None = None) -> str | None:
    """Newest stored snapshot date across formats (cheap one-row query), or None."""

    config = config or load_config()
    if not config.configured:
        return None
    head = _get(config, {"source": f"eq.{SOURCE}", "select": "snapshot_date", "order": "snapshot_date.desc", "limit": "1"})
    return str(head[0].get("snapshot_date")) if head else None


def latest_cached(fmt: str, *, config: AdpConfig | None = None) -> dict[str, Any]:
    now = time.time()
    hit = _cache.get(fmt)
    if hit and now - hit[0] < _CACHE_TTL_SECONDS:
        return hit[1]
    try:
        value = fetch_latest(fmt, config=config)
    except Exception:
        value = {}
    _cache[fmt] = (now, value)
    return value


def format_for_draft_kind(kind: str | None) -> str:
    return "rookie_1qb" if str(kind or "").lower() == "rookie" else "dynasty_1qb"


def attribution(fmt: str, snapshot: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not snapshot or not snapshot.get("players"):
        return None
    return {
        "source": SOURCE_LABEL,
        "url": SOURCE_URL,
        "format": fmt,
        "qb_format": FORMATS[fmt]["qb_format"],
        "as_of": snapshot.get("as_of"),
        "total_drafts": snapshot.get("total_drafts"),
    }


# --- multi-factor read (pure) ----------------------------------------------------


def value_vs_adp(our_rank: float | None, entry: Mapping[str, Any] | None) -> dict[str, Any]:
    """ADP next to our rank. Positive ``delta`` = ADP is later than our rank (we like him
    more than the room does). Always carries sample size and spread so ADP is never alone."""

    entry = entry or {}
    adp = _num(entry.get("adp"))
    if adp is None:
        return {"adp": None, "delta": None, "verdict": None, "thin_sample": None, "trend": None, "read": None}
    drafts = int(_num(entry.get("drafts")) or 0)
    thin = drafts < THIN_SAMPLE_DRAFTS
    delta = round(adp - our_rank, 1) if our_rank else None
    if delta is None:
        verdict = None
    elif abs(delta) <= ALIGNED_BAND:
        verdict = "aligned"
    else:
        verdict = "value" if delta > 0 else "reach"
    parts: list[str] = []
    if delta is not None and verdict:
        label = {
            "aligned": "Our rank and ADP agree",
            "value": "We rank him higher than ADP",
            "reach": "ADP is higher than our rank",
        }[verdict]
        parts.append(f"{label} ({delta:+.1f})")
    low, high, stdev = entry.get("low"), entry.get("high"), _num(entry.get("stdev"))
    if low is not None and high is not None:
        parts.append(f"range {high:g}-{low:g}")
    if stdev is not None and stdev >= 6:
        parts.append("wide spread, drafters disagree")
    parts.append(f"{drafts} drafts" + (" (thin sample)" if thin else ""))
    trend = _num(entry.get("trend"))
    if trend is not None and abs(trend) >= 1:
        parts.append(f"ADP {'rising' if trend < 0 else 'falling'} {abs(trend):.1f} since {entry.get('trend_since')}")
    return {
        "adp": adp,
        "delta": delta,
        "verdict": verdict,
        "thin_sample": thin,
        "trend": trend,
        "read": "; ".join(parts),
    }


def build_rookie_board(
    rookies: list[dict[str, Any]], snapshot: Mapping[str, Any] | None, *, limit: int = 40
) -> list[dict[str, Any]]:
    """``rookies``: dicts with player_id/name/position/team/score. Our rookie rank comes from
    score order; ADP from the snapshot. Players without ADP stay listed with adp None."""

    ordered = sorted(rookies, key=lambda r: -(_num(r.get("score")) or 0))
    players = (snapshot or {}).get("players") or {}
    board = []
    for rank, row in enumerate(ordered, start=1):
        entry = players.get(str(row.get("player_id")))
        board.append(
            {
                "player_id": row.get("player_id"),
                "name": row.get("name"),
                "position": row.get("position"),
                "team": row.get("team"),
                "our_rank": rank,
                **value_vs_adp(rank, entry),
                "drafts": (entry or {}).get("drafts"),
            }
        )
    return board[:limit]


# --- Est. SF ADP (MODELED, never real ADP, never stored) ----------------------------

EST_SF_LABEL = "Est. SF"
EST_SF_NOTE = (
    "Estimated, not real ADP: Fantasy Football Calculator's 1QB ADP re-ordered with our "
    "FantasyCalc-based superflex vs 1QB values (QBs gain in superflex). No approved source "
    "publishes real superflex ADP."
)
ONE_QB_LABEL = "1QB ADP"
_RATIO_MIN, _RATIO_MAX = 0.5, 3.0
_RATIO_TTL_SECONDS = 6 * 3600
_ratio_cache: tuple[float, dict[str, float]] | None = None


def is_superflex(qb_format: Any) -> bool:
    return str(qb_format or "").strip().lower() in {"superflex", "sf", "2qb", "super flex"}


def _fantasycalc_values(num_qbs: int) -> dict[str, float]:
    try:
        response = requests.get(
            "https://api.fantasycalc.com/values/current",
            params={"isDynasty": "true", "numQbs": num_qbs, "numTeams": TEAMS, "ppr": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=4,
        )
        data = response.json() if response.status_code == 200 else []
    except Exception:
        return {}
    out: dict[str, float] = {}
    for item in data if isinstance(data, list) else []:
        player = item.get("player") if isinstance(item, Mapping) else None
        sid = str((player or {}).get("sleeperId") or "")
        value = _num(item.get("value"))
        if sid and value and value > 0:
            out[sid] = value
    return out


def sf_value_ratios() -> dict[str, float]:
    """{sleeper_id: superflex value / 1QB value}, cached; {} when unavailable (no estimate)."""

    global _ratio_cache
    now = time.time()
    if _ratio_cache and now - _ratio_cache[0] < _RATIO_TTL_SECONDS:
        return _ratio_cache[1]
    one, two = _fantasycalc_values(1), _fantasycalc_values(2)
    ratios = {
        sid: max(_RATIO_MIN, min(_RATIO_MAX, two[sid] / one[sid])) for sid in one if sid in two
    }
    _ratio_cache = (now, ratios)
    return ratios


def estimate_sf_adp(players: Mapping[str, Mapping[str, Any]], ratios: Mapping[str, float]) -> dict[str, float]:
    """{sleeper_id: est. SF ADP}. The set of ADP slots is unchanged (so the scale stays
    real); players are re-ordered by ``adp / ratio`` and take the slots in that order.
    Missing ratio = 1.0 (no change). All ratios 1 reproduces the 1QB order exactly; the
    sort is deterministic (ties fall back to 1QB ADP, then id)."""

    items = [(sid, _num(e.get("adp"))) for sid, e in players.items()]
    items = [(sid, adp) for sid, adp in items if adp is not None]
    slots = sorted(adp for _sid, adp in items)
    ordered = sorted(items, key=lambda it: (it[1] / float(ratios.get(it[0], 1.0) or 1.0), it[1], it[0]))
    return {sid: round(slots[i], 1) for i, (sid, _adp) in enumerate(ordered)}
