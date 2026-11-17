"""Automated college prospect ingest for ``public.college_prospects``.

Run by ``.github/workflows/college-prospect-ingest.yml``; zero manual steps.

Two independent steps
---------------------
1. **Class listing** (needs the ``CFBD_API_KEY`` secret). College Football
   Data (collegefootballdata.com) rosters give real player name, position,
   school and class year; its season stats gate out non-contributors. Keeps the
   next two draft classes (``season+1`` and ``season+2``) populated. Skipped
   cleanly, never failed, when the key is absent (forks, local runs).
   Runs only on Mondays unless forced, so the free CFBD quota (1000 calls/mo)
   is never at risk from the daily draft-window runs.
2. **Post-draft retirement** (keyless). nflverse ``draft_picks.csv`` (free,
   no account) identifies prospects who were drafted; they are flagged
   (``drafted``, NFL team, round/pick, GSIS id, Sleeper id) and hidden by the
   Prospects list. Rows are NEVER deleted: a delete would cascade to users'
   scouting reports and watchlists.

NO FABRICATED DATA (#887): every row comes from a cited source; the source is
stored per row (``source`` / ``source_url``) when the optional columns from
``docs/supabase_college_prospects_ingest.sql`` exist. Before that migration
is applied the upsert fails soft to the base columns and retirement is
skipped.
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import json
import os
import re
import time
import unicodedata
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import requests

PROSPECTS_TABLE = "college_prospects"
CFBD_BASE = "https://api.collegefootballdata.com"
NFLVERSE_DRAFT_PICKS_URL = "https://github.com/nflverse/nflverse-data/releases/download/draft_picks/draft_picks.csv"
SLEEPER_PLAYERS_URL = "https://api.sleeper.app/v1/players/nfl"
STATUS_FILE = os.path.join("data", "college_prospects_ingest_status.json")
USER_AGENT = "FantasyDeskProspectIngest/1.0 (+https://github.com/h-keenan/FANTASYGMLAB)"

RELEVANT_POSITIONS = ("QB", "RB", "WR", "TE")
BASE_COLUMNS = ("id", "name", "position", "school", "draft_year")
EXTENDED_COLUMNS = ("source", "source_url", "ingested_at")
RETIRE_COLUMNS = ("drafted", "nfl_team", "draft_round", "draft_pick", "nfl_gsis_id", "sleeper_player_id")

# Production gate: a roster listing alone includes every walk-on. Only players
# with real season output from CFBD's stats feed are listed.
MIN_SEASON_YARDS = {"passing": 500, "rushing": 150, "receiving": 150}
POSITION_ALIASES = {"FB": "RB", "HB": "RB", "TB": "RB"}


# ---------------------------------------------------------------------------
# Text / id helpers (same rules as scripts/build_college_prospects_seed.py so
# ids stay stable and never collide with the seeded rows)
# ---------------------------------------------------------------------------
_SUFFIX_RE = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b\.?", re.IGNORECASE)


def _ascii_fold(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'")
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def normalize_name(name: str) -> str:
    text = _SUFFIX_RE.sub(" ", _ascii_fold(str(name or "")).lower())
    return re.sub(r"[^a-z]", "", text)


def slugify(text: str) -> str:
    text = _ascii_fold(str(text or "")).lower().replace("&", " and ")
    text = re.sub(r"['.]", "", text)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def make_prospect_id(name: str, school: str, draft_year: int) -> str:
    return f"{int(draft_year)}-{slugify(name)}-{slugify(school)}"


def college_season(today: Optional[_dt.date] = None) -> int:
    """CFB season in progress (or just finished): Aug-Dec -> this year, Jan-Jul -> last year."""

    today = today or _dt.date.today()
    return today.year if today.month >= 8 else today.year - 1


def target_draft_years(season: int) -> Tuple[int, int]:
    return (season + 1, season + 2)


def draft_year_for(class_year: Any, season: int) -> Optional[int]:
    """First NFL draft a player is eligible for (3 years removed from HS)."""

    try:
        years = int(class_year)
    except (TypeError, ValueError):
        return None
    if years < 1:
        return None
    return season + max(1, 4 - years)


# ---------------------------------------------------------------------------
# CFBD parsing
# ---------------------------------------------------------------------------
def parse_production(stat_rows: Iterable[Mapping[str, Any]]) -> set:
    """Set of CFBD playerIds whose season yardage clears the production gate."""

    keep = set()
    for row in stat_rows or []:
        category = str(row.get("category") or "").lower()
        if category not in MIN_SEASON_YARDS or str(row.get("statType") or "").upper() != "YDS":
            continue
        try:
            value = float(row.get("stat"))
        except (TypeError, ValueError):
            continue
        if value >= MIN_SEASON_YARDS[category] and row.get("playerId") is not None:
            keep.add(str(row["playerId"]))
    return keep


def parse_roster(
    roster_rows: Iterable[Mapping[str, Any]],
    *,
    season: int,
    producers: set,
    draft_years: Sequence[int],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in roster_rows or []:
        position = str(row.get("position") or "").upper()
        position = POSITION_ALIASES.get(position, position)
        if position not in RELEVANT_POSITIONS:
            continue
        pid = row.get("id")
        if pid is None or str(pid) not in producers:
            continue
        name = " ".join(str(row.get(k) or "").strip() for k in ("firstName", "lastName")).strip()
        school = str(row.get("team") or "").strip()
        year = draft_year_for(row.get("year"), season)
        if not name or not school or year not in draft_years:
            continue
        out.append({"name": name, "position": position, "school": school, "draft_year": year, "cfbd_id": str(pid)})
    return out


def cfbd_source(season: int, cfbd_id: str) -> Tuple[str, str]:
    return (
        f"College Football Data API (rosters + {season} season stats), player {cfbd_id}",
        f"https://collegefootballdata.com/player/{cfbd_id}",
    )


def _cfbd_get(path: str, params: Mapping[str, Any], key: str, timeout: float = 30) -> Any:
    response = requests.get(
        CFBD_BASE + path,
        params=params,
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json", "User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def fetch_candidates(
    key: str, season: int, *, getter: Callable[..., Any] = _cfbd_get, delay: float = 0.2, log: Callable[[str], None] = print
) -> List[Dict[str, Any]]:
    draft_years = target_draft_years(season)
    producers: set = set()
    for category in MIN_SEASON_YARDS:
        producers |= parse_production(getter("/stats/player/season", {"year": season, "category": category}, key))
    teams = getter("/teams/fbs", {"year": season}, key)
    candidates: List[Dict[str, Any]] = []
    for team in teams:
        school = team.get("school")
        if not school:
            continue
        try:
            roster = getter("/roster", {"team": school, "year": season}, key)
        except Exception as exc:  # one bad team must not sink the run
            log(f"roster fetch failed for {school}: {type(exc).__name__}")
            continue
        candidates.extend(parse_roster(roster, season=season, producers=producers, draft_years=draft_years))
        time.sleep(delay)
    return candidates


# ---------------------------------------------------------------------------
# Reconcile with existing rows + payload (idempotent upsert, never delete)
# ---------------------------------------------------------------------------
def reconcile(
    candidates: Sequence[Mapping[str, Any]], existing: Sequence[Mapping[str, Any]], *, season: int, now_iso: str
) -> List[Dict[str, Any]]:
    """Reuse an existing row's id when the same player (name+draft year, or
    name+school) is already present so scouting reports keep pointing at him."""

    by_year = {(normalize_name(r.get("name")), r.get("draft_year")): r.get("id") for r in existing}
    by_school = {(normalize_name(r.get("name")), slugify(r.get("school"))): r.get("id") for r in existing}
    rows: Dict[str, Dict[str, Any]] = {}
    for c in candidates:
        n = normalize_name(c["name"])
        pid = (
            by_year.get((n, c["draft_year"]))
            or by_school.get((n, slugify(c["school"])))
            or make_prospect_id(c["name"], c["school"], c["draft_year"])
        )
        source, url = cfbd_source(season, c["cfbd_id"])
        rows[pid] = {
            "id": pid,
            "name": c["name"],
            "position": c["position"],
            "school": c["school"],
            "draft_year": c["draft_year"],
            "source": source,
            "source_url": url,
            "ingested_at": now_iso,
        }
    return list(rows.values())


def build_payload(rows: Sequence[Mapping[str, Any]], *, extended: bool) -> List[Dict[str, Any]]:
    cols = BASE_COLUMNS + (EXTENDED_COLUMNS if extended else ())
    return [{c: r.get(c) for c in cols} for r in rows]


# ---------------------------------------------------------------------------
# Retirement mapping (nflverse draft picks -> prospects)
# ---------------------------------------------------------------------------
def parse_draft_picks(csv_text: str) -> List[Dict[str, Any]]:
    out = []
    for r in csv.DictReader(io.StringIO(csv_text)):
        try:
            out.append(
                {
                    "season": int(r["season"]),
                    "round": int(r["round"]),
                    "pick": int(r["pick"]),
                    "team": r.get("team") or None,
                    "gsis_id": (r.get("gsis_id") or "").strip() or None,
                    "name": r.get("pfr_player_name") or "",
                    "position": str(r.get("position") or "").upper(),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


def map_retirements(
    prospects: Sequence[Mapping[str, Any]],
    picks: Sequence[Mapping[str, Any]],
    *,
    sleeper_by_gsis: Optional[Mapping[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Prospects (not yet drafted) matched to a pick of their draft year by
    normalized name + same fantasy position. Ambiguous matches are skipped."""

    index: Dict[Tuple[str, int], List[Mapping[str, Any]]] = {}
    for p in picks:
        index.setdefault((normalize_name(p["name"]), p["season"]), []).append(p)
    sleeper_by_gsis = sleeper_by_gsis or {}
    updates = []
    for pr in prospects:
        if pr.get("drafted"):
            continue
        matches = [
            p
            for p in index.get((normalize_name(pr.get("name")), pr.get("draft_year")), [])
            if POSITION_ALIASES.get(p["position"], p["position"]) == pr.get("position")
        ]
        if len(matches) != 1:
            continue
        m = matches[0]
        updates.append(
            {
                "id": pr["id"],
                "name": pr["name"],
                "position": pr["position"],
                "school": pr["school"],
                "draft_year": pr["draft_year"],
                "drafted": True,
                "nfl_team": m["team"],
                "draft_round": m["round"],
                "draft_pick": m["pick"],
                "nfl_gsis_id": m["gsis_id"],
                "sleeper_player_id": sleeper_by_gsis.get(m["gsis_id"] or ""),
            }
        )
    return updates


# ---------------------------------------------------------------------------
# Supabase (service role) I/O — upsert and select only; there is no delete.
# ---------------------------------------------------------------------------
def _headers(key: str, *, upsert: bool = False) -> Dict[str, str]:
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if upsert:
        h["Prefer"] = "resolution=merge-duplicates,return=minimal"
    return h


def _table_url(url: str, query: str = "") -> str:
    base = url.rstrip("/")
    for suffix in ("/rest/v1", "/rest"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    return f"{base}/rest/v1/{PROSPECTS_TABLE}" + (f"?{query}" if query else "")


def select_existing(url: str, key: str, *, extended: bool) -> Tuple[List[Dict[str, Any]], bool]:
    """Existing rows; falls back to base columns if the migration is not applied.
    Returns (rows, extended_columns_available)."""

    cols = list(BASE_COLUMNS) + (["drafted"] if extended else [])
    r = requests.get(_table_url(url, f"select={','.join(cols)}&limit=10000"), headers=_headers(key), timeout=30)
    if r.status_code >= 400 and extended:
        return select_existing(url, key, extended=False)[0], False
    r.raise_for_status()
    return r.json(), extended


def upsert_rows(url: str, key: str, rows: Sequence[Mapping[str, Any]], *, batch: int = 200) -> int:
    """Idempotent ``on conflict (id) do update`` upsert. Returns rows sent."""

    sent = 0
    for i in range(0, len(rows), batch):
        chunk = list(rows[i : i + batch])
        r = requests.post(_table_url(url, "on_conflict=id"), headers=_headers(key, upsert=True), data=json.dumps(chunk), timeout=60)
        r.raise_for_status()
        sent += len(chunk)
    return sent


def upsert_with_fallback(url: str, key: str, rows: Sequence[Mapping[str, Any]]) -> Tuple[int, bool]:
    """Try the extended payload; if the optional columns do not exist yet
    (migration pending) retry with base columns. Returns (sent, extended_used)."""

    try:
        return upsert_rows(url, key, build_payload(rows, extended=True)), True
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code in (400, 404):
            return upsert_rows(url, key, build_payload(rows, extended=False)), False
        raise


def fetch_sleeper_gsis_map(timeout: float = 60) -> Dict[str, str]:
    try:
        r = requests.get(SLEEPER_PLAYERS_URL, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        r.raise_for_status()
        return {str(v["gsis_id"]): str(k) for k, v in r.json().items() if isinstance(v, dict) and v.get("gsis_id")}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run(
    *,
    environ: Optional[Mapping[str, str]] = None,
    today: Optional[_dt.date] = None,
    force_classes: bool = False,
    log: Callable[[str], None] = print,
) -> Dict[str, Any]:
    env = os.environ if environ is None else environ
    today = today or _dt.date.today()
    now_iso = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    supa_url = env.get("SUPABASE_URL", "").strip()
    supa_key = env.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    cfbd_key = env.get("CFBD_API_KEY", "").strip()
    season = college_season(today)
    status: Dict[str, Any] = {"ran_at": now_iso, "season": season, "ok": True, "classes": {}, "retire": {}}
    if not (supa_url and supa_key):
        status.update(ok=False, error="supabase_not_configured")
        return status

    extended = True
    # Step 1: class listing (CFBD, key-gated, Mondays unless forced)
    if not cfbd_key:
        status["classes"] = {"status": "skipped_no_key"}
    elif today.weekday() != 0 and not force_classes:
        status["classes"] = {"status": "skipped_not_monday"}
    else:
        try:
            candidates = fetch_candidates(cfbd_key, season, log=log)
            if not candidates:
                status["classes"] = {"status": "empty", "fetched": 0}
                status["ok"] = False
            else:
                existing, extended = select_existing(supa_url, supa_key, extended=True)
                rows = reconcile(candidates, existing, season=season, now_iso=now_iso)
                sent, extended = upsert_with_fallback(supa_url, supa_key, rows)
                status["classes"] = {"status": "ok", "fetched": len(candidates), "upserted": sent, "extended_columns": extended}
        except Exception as exc:
            status["classes"] = {"status": "error", "error": type(exc).__name__}
            status["ok"] = False

    # Step 2: retirement (keyless nflverse), only once the draft data exists
    try:
        picks = [p for p in parse_draft_picks(requests.get(NFLVERSE_DRAFT_PICKS_URL, headers={"User-Agent": USER_AGENT}, timeout=60).text) if p["season"] >= today.year - 1]
        existing, has_ext = select_existing(supa_url, supa_key, extended=True)
        if not has_ext:
            status["retire"] = {"status": "skipped_migration_pending"}
        else:
            updates = map_retirements(existing, picks, sleeper_by_gsis=fetch_sleeper_gsis_map() if picks else None)
            sent = upsert_rows(supa_url, supa_key, updates) if updates else 0
            status["retire"] = {"status": "ok", "picks_seen": len(picks), "retired": sent}
    except Exception as exc:
        status["retire"] = {"status": "error", "error": type(exc).__name__}
        status["ok"] = False
    return status


def write_status(status: Mapping[str, Any], path: str = STATUS_FILE) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(status, fh, indent=2, sort_keys=True)
        fh.write("\n")
