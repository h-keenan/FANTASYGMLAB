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

3. **Stats + profile** (same key, same Monday run, after the class listing).
   Fills ``public.college_prospect_stats`` (docs/supabase_college_prospect_stats.sql)
   for the prospects found in step 1: per-season passing/rushing/receiving lines
   (the season-stat feeds step 1 already pulled), PPA + usage, the current
   season's weekly game log, and recruiting (stars, national rank, hometown).
   CFBD free tier = 1000 calls/month, so every call goes through ``CallBudget``:
   bulk endpoints only (no per-player calls), game logs fetch just the newest
   two weeks once a season is partly stored, prior seasons + recruiting refresh
   only on the first Monday of the month, and the offseason skips the rest.
   The month-to-date count lives in the status file and caps the run
   (``MONTHLY_CALL_CAP``). Skipped cleanly when the table is not migrated yet.

3. **Stats + profile** (same key, same Monday run, after the class listing).
   Fills ``public.college_prospect_stats`` (docs/supabase_college_prospect_stats.sql)
   for the prospects found in step 1: per-season passing/rushing/receiving lines
   (the season-stat feeds step 1 already pulled), PPA + usage, the current
   season's weekly game log, and recruiting (stars, national rank, hometown).
   CFBD free tier = 1000 calls/month, so every call goes through ``CallBudget``:
   bulk endpoints only (no per-player calls), game logs fetch just the newest
   two weeks once a season is partly stored, prior seasons + recruiting refresh
   only on the first Monday of the month, and the offseason skips the rest.
   The month-to-date count lives in the status file and caps the run
   (``MONTHLY_CALL_CAP``). Skipped cleanly when the table is not migrated yet.

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
STATS_TABLE = "college_prospect_stats"
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
def _name_team_key(name: Any, team: Any) -> Optional[str]:
    n, t = normalize_name(name), normalize_name(team)
    return f"nt:{n}|{t}" if n and t else None


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
        if value >= MIN_SEASON_YARDS[category]:
            if row.get("playerId") is not None:
                keep.add(str(row["playerId"]))
            nk = _name_team_key(row.get("player"), row.get("team"))
            if nk:
                keep.add(nk)
    return keep


def roster_class_year(row: Mapping[str, Any], season: int, recruit_years: Optional[Mapping[str, int]] = None) -> Optional[int]:
    """Class year (1=freshman..5). CFBD's roster ``year`` field is deprecated and now
    returns the season (or nothing), so only a value in 1..5 is trusted; otherwise the
    class is derived from the player's high-school recruiting year."""

    # The high-school recruiting class is authoritative when we can link it: the
    # deprecated roster ``year`` can hold a stale or default value (e.g. 1 for
    # everyone), which would push every player out of the target draft years.
    ids = [str(row.get("id"))] + [str(r) for r in (row.get("recruitIds") or [])]
    for rid in ids:
        rec_year = (recruit_years or {}).get(rid)
        if rec_year and 1 <= season - rec_year + 1 <= 5:
            return season - rec_year + 1
    raw = _int_or_none(row.get("year"))
    if raw is not None and 1 <= raw <= 5:
        return raw
    return None


def recruit_year_map(rows: Iterable[Mapping[str, Any]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for row in rows or []:
        year = _int_or_none(row.get("year"))
        if not year:
            continue
        for k in ("id", "athleteId"):
            if row.get(k) is not None:
                out[str(row[k])] = year
    return out


def parse_roster(
    roster_rows: Iterable[Mapping[str, Any]],
    *,
    season: int,
    producers: set,
    draft_years: Sequence[int],
    recruit_years: Optional[Mapping[str, int]] = None,
    counts: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    c = counts if counts is not None else {}

    def bump(k: str) -> None:
        c[k] = c.get(k, 0) + 1

    for row in roster_rows or []:
        bump("rows")
        position = str(row.get("position") or "").upper()
        position = POSITION_ALIASES.get(position, position)
        if position not in RELEVANT_POSITIONS:
            continue
        bump("position_ok")
        pid = row.get("id")
        name = " ".join(str(row.get(k) or "").strip() for k in ("firstName", "lastName")).strip()
        school = str(row.get("team") or "").strip()
        if not ((pid is not None and str(pid) in producers) or _name_team_key(name, school) in producers):
            continue
        bump("producer_ok")
        class_year = roster_class_year(row, season, recruit_years)
        year = draft_year_for(class_year, season)
        # Distribution diagnostics (counts only, no names) for the run log.
        raw_hist = c.setdefault("raw_year_hist", {})
        raw_key = str(row.get("year"))
        raw_hist[raw_key] = raw_hist.get(raw_key, 0) + 1
        dy_hist = c.setdefault("draft_year_hist", {})
        dy_hist[str(year)] = dy_hist.get(str(year), 0) + 1
        if class_year is None:
            bump("no_class_year")
            samples = c.setdefault("samples", [])
            if len(samples) < 3:
                samples.append({"year": row.get("year"), "pos": position, "recruitIds": len(row.get("recruitIds") or [])})
        if not name or not school or year not in draft_years:
            if year is not None:
                bump("draft_year_out_of_range")
            continue
        city = str(row.get("homeCity") or "").strip()
        state = str(row.get("homeState") or "").strip()
        out.append(
            {
                "name": name,
                "position": position,
                "school": school,
                "draft_year": year,
                "cfbd_id": str(pid),
                "class_year": class_year,
                "height_in": _int_or_none(row.get("height")),
                "weight_lb": _int_or_none(row.get("weight")),
                "hometown": ", ".join(p for p in (city, state) if p) or None,
                "recruit_ids": [str(r) for r in (row.get("recruitIds") or [])],
            }
        )
    return out


def _int_or_none(value: Any) -> Optional[int]:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _num_or_none(value: Any) -> Optional[float]:
    try:
        number = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return number if number == number else None


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
    key: str,
    season: int,
    *,
    getter: Callable[..., Any] = _cfbd_get,
    delay: float = 0.2,
    log: Callable[[str], None] = print,
    sink: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Candidates for the next two draft classes. ``sink`` (optional) receives the
    raw season-stat rows and school logos these same calls already returned, so the
    stats step costs no extra CFBD calls for them."""

    draft_years = target_draft_years(season)
    producers: set = set()
    stat_rows: List[Mapping[str, Any]] = []
    for category in MIN_SEASON_YARDS:
        rows = getter("/stats/player/season", {"year": season, "category": category}, key)
        stat_rows.extend(rows or [])
        producers |= parse_production(rows)
    teams = getter("/teams/fbs", {"year": season}, key)
    if sink is not None:
        sink["season_stat_rows"] = stat_rows
        sink["logos"] = {t.get("school"): (t.get("logos") or [None])[0] for t in teams if t.get("school")}
    rosters: List[Any] = []
    for team in teams:
        school = team.get("school")
        if not school:
            continue
        try:
            roster = getter("/roster", {"team": school, "year": season}, key)
        except Exception as exc:  # one bad team must not sink the run
            log(f"roster fetch failed for {school}: {type(exc).__name__}")
            continue
        rosters.append(roster or [])
        time.sleep(delay)
    recruit_years: Dict[str, int] = {}
    needs_recruits = any(
        not (_int_or_none(r.get("year")) and 1 <= _int_or_none(r.get("year")) <= 5) for roster in rosters for r in roster
    )
    if needs_recruits:  # roster class year unusable: derive it from recruiting year (5 extra calls)
        for y in range(season - 4, season + 1):
            try:
                recruit_years.update(recruit_year_map(getter("/recruiting/players", {"year": y, "classification": "HighSchool"}, key)))
            except Exception as exc:
                log(f"recruiting fetch failed for {y}: {type(exc).__name__}")
    candidates: List[Dict[str, Any]] = []
    counts: Dict[str, Any] = {}
    for roster in rosters:
        candidates.extend(
            parse_roster(
                roster, season=season, producers=producers, draft_years=draft_years,
                recruit_years=recruit_years, counts=counts,
            )
        )
    log(f"roster stages: {counts}")
    log(
        f"candidates: producers={len(producers)} teams={len(teams)} rosters={len(rosters)} "
        f"recruit_years={len(recruit_years)} candidates={len(candidates)}"
    )
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
            "cfbd_id": c["cfbd_id"],
            "_meta": {k: c.get(k) for k in ("class_year", "height_in", "weight_lb", "hometown", "recruit_ids")},
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
# Stats + profile step (CFBD, call-budgeted)
# ---------------------------------------------------------------------------
MONTHLY_CALL_CAP = 900  # of CFBD's 1000/month free tier: 100 spare for manual runs
CLASS_LISTING_CALLS_ESTIMATE = 150  # 3 season-stat feeds + teams + ~136 FBS rosters
RUN_STATS_CALL_CAP = 40  # the stats step alone never spends more than this in one run
GAME_LOG_RECENT_WEEKS = 2  # once a season is partly stored, refetch only the newest weeks
LAST_REGULAR_WEEK = 15

# CFBD statType -> compact key, per category. Only real CFBD stat names; nothing derived here.
STAT_KEYS: Dict[str, Dict[str, str]] = {
    "passing": {"COMPLETIONS": "cmp", "ATT": "att", "YDS": "yds", "TD": "td", "INT": "int", "PCT": "pct", "YPA": "ypa"},
    "rushing": {"CAR": "car", "YDS": "yds", "TD": "td", "YPC": "ypc", "LONG": "long"},
    "receiving": {"REC": "rec", "YDS": "yds", "TD": "td", "YPR": "ypr", "LONG": "long"},
}
# /games/players box-score "types" -> the same compact keys
BOX_KEYS: Dict[str, Dict[str, str]] = {
    "passing": {"YDS": "yds", "TD": "td", "INT": "int", "AVG": "ypa"},
    "rushing": {"CAR": "car", "YDS": "yds", "TD": "td", "AVG": "ypc", "LONG": "long"},
    "receiving": {"REC": "rec", "YDS": "yds", "TD": "td", "AVG": "ypr", "LONG": "long"},
}
RATE_KEYS = ("pct", "ypa", "ypc", "ypr")


class BudgetExceeded(RuntimeError):
    pass


class CallBudget:
    """Counts CFBD calls and refuses to exceed ``cap`` (raises ``BudgetExceeded``)."""

    def __init__(self, cap: int) -> None:
        self.cap = int(cap)
        self.used = 0

    def wrap(self, getter: Callable[..., Any]) -> Callable[..., Any]:
        def counted(path: str, params: Mapping[str, Any], key: str, *args: Any, **kwargs: Any) -> Any:
            if self.used >= self.cap:
                raise BudgetExceeded(path)
            self.used += 1
            return getter(path, params, key, *args, **kwargs)

        return counted


def month_key(today: _dt.date) -> str:
    return today.strftime("%Y-%m")


def month_calls_so_far(previous_status: Optional[Mapping[str, Any]], today: _dt.date) -> int:
    usage = (previous_status or {}).get("cfbd_usage") or {}
    return int(usage.get("calls") or 0) if usage.get("month") == month_key(today) else 0


def in_season(today: _dt.date) -> bool:
    """Games are being played or just finished (Aug 1 - Jan 25)."""

    return today.month >= 8 or (today.month == 1 and today.day <= 25)


def is_slow_refresh(today: _dt.date, *, have_rows: bool, force: bool) -> bool:
    """Prior seasons + recruiting barely change: first Monday of the month, first fill, or a manual run."""

    return force or not have_rows or today.day <= 7


def current_week(today: _dt.date, season: int) -> int:
    """Rough CFB regular-season week (0-15) from the calendar; only bounds which weeks to ask for."""

    return max(0, min(LAST_REGULAR_WEEK, (today - _dt.date(season, 8, 24)).days // 7))


def _stat_value(key: str, value: float) -> Any:
    return round(value, 2) if key in RATE_KEYS or not float(value).is_integer() else int(value)


def parse_season_stats(rows: Iterable[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """CFBD /stats/player/season rows -> {playerId: {"team", "passing": {...}, "rushing": {...}, "receiving": {...}}}."""

    out: Dict[str, Dict[str, Any]] = {}
    for row in rows or []:
        category = str(row.get("category") or "").lower()
        keys = STAT_KEYS.get(category)
        if keys is None or row.get("playerId") is None:
            continue
        key = keys.get(str(row.get("statType") or "").upper())
        value = _num_or_none(row.get("stat"))
        if key is None or value is None:
            continue
        entry = out.setdefault(str(row["playerId"]), {"team": row.get("team")})
        entry.setdefault(category, {})[key] = _stat_value(key, value)
    return out


def _round_map(values: Mapping[str, Any]) -> Dict[str, float]:
    return {k: round(float(v), 3) for k, v in (values or {}).items() if _num_or_none(v) is not None}


def parse_ppa(rows: Iterable[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """CFBD /ppa/players/season -> {playerId: {"avg": {...}, "total": {...}}} (predicted points added)."""

    out: Dict[str, Dict[str, Any]] = {}
    for row in rows or []:
        if row.get("id") is None:
            continue
        out[str(row["id"])] = {"avg": _round_map(row.get("averagePPA") or {}), "total": _round_map(row.get("totalPPA") or {})}
    return out


def parse_usage(rows: Iterable[Mapping[str, Any]]) -> Dict[str, Dict[str, float]]:
    """CFBD /player/usage -> {playerId: {"overall": share of team plays, "pass": ..., "rush": ...}}."""

    out: Dict[str, Dict[str, float]] = {}
    for row in rows or []:
        if row.get("id") is None:
            continue
        usage = _round_map(row.get("usage") or {})
        if usage:
            out[str(row["id"])] = usage
    return out


def parse_game_week(games: Iterable[Mapping[str, Any]], week: int, wanted: set) -> Dict[str, Dict[str, Any]]:
    """CFBD /games/players for one week -> {playerId: {"week", "opponent", category: {...}}} for ``wanted`` ids."""

    out: Dict[str, Dict[str, Any]] = {}
    for game in games or []:
        teams = game.get("teams") or []
        for team in teams:
            opponent = next((t.get("team") for t in teams if t is not team), None)
            for cat in team.get("categories") or []:
                category = str(cat.get("name") or "").lower()
                keys = BOX_KEYS.get(category)
                if keys is None:
                    continue
                for typ in cat.get("types") or []:
                    key = keys.get(str(typ.get("name") or "").upper())
                    if key is None:
                        continue
                    for athlete in typ.get("athletes") or []:
                        pid = str(athlete.get("id")) if athlete.get("id") is not None else ""
                        value = _num_or_none(athlete.get("stat"))
                        if pid not in wanted or value is None:
                            continue
                        entry = out.setdefault(pid, {"week": week, "opponent": opponent})
                        entry.setdefault(category, {})[key] = _stat_value(key, value)
    return out


def parse_recruits(rows: Iterable[Mapping[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """CFBD /recruiting/players -> (by recruit id, by athlete id) compact records."""

    by_recruit: Dict[str, Dict[str, Any]] = {}
    by_athlete: Dict[str, Dict[str, Any]] = {}
    for row in rows or []:
        record = {
            "year": _int_or_none(row.get("year")),
            "stars": _int_or_none(row.get("stars")),
            "rating": _num_or_none(row.get("rating")),
            "national_rank": _int_or_none(row.get("ranking")),
            "high_school": str(row.get("school") or "").strip() or None,
            "city": str(row.get("city") or "").strip() or None,
            "state": str(row.get("stateProvince") or "").strip() or None,
        }
        if record["stars"] is None and record["national_rank"] is None:
            continue
        if row.get("id") is not None:
            by_recruit[str(row["id"])] = record
        if row.get("athleteId") is not None:
            by_athlete[str(row["athleteId"])] = record
    return by_recruit, by_athlete


def merge_seasons(existing: Optional[Sequence[Mapping[str, Any]]], new_entries: Mapping[int, Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Replace/add season entries by year, newest first. Older seasons already stored are kept."""

    by_year: Dict[int, Dict[str, Any]] = {}
    for entry in existing or []:
        if isinstance(entry, Mapping) and _int_or_none(entry.get("season")):
            by_year[int(entry["season"])] = dict(entry)
    for year, entry in new_entries.items():
        by_year[int(year)] = {"season": int(year), **entry}
    return [by_year[y] for y in sorted(by_year, reverse=True)]


def merge_game_log(existing: Optional[Mapping[str, Any]], season: int, new_games: Iterable[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """Keep the stored weeks of ``season``, replace/add the newly fetched ones (by week)."""

    games: Dict[int, Dict[str, Any]] = {}
    if existing and existing.get("season") == season:
        for g in existing.get("games") or []:
            if g.get("week") is not None:
                games[int(g["week"])] = dict(g)
    for g in new_games:
        games[int(g["week"])] = dict(g)
    if not games:
        return None
    return {"season": season, "games": [games[w] for w in sorted(games)]}


def _stats_url(url: str, query: str = "") -> str:
    return _table_url(url, query).replace(f"/{PROSPECTS_TABLE}", f"/{STATS_TABLE}", 1)


def select_existing_stats(url: str, key: str) -> Optional[Dict[str, Dict[str, Any]]]:
    """Stored stats rows by prospect id, or None when the table is not migrated yet."""

    r = requests.get(_stats_url(url, "select=prospect_id,seasons,game_log,recruiting&limit=10000"), headers=_headers(key), timeout=30)
    if r.status_code >= 400:
        return None
    return {str(row["prospect_id"]): row for row in r.json() if isinstance(row, dict) and row.get("prospect_id")}


def upsert_stats(url: str, key: str, rows: Sequence[Mapping[str, Any]], *, batch: int = 100) -> int:
    """Upsert on prospect_id. Rows are grouped by key set so a partial refresh never nulls
    a column it did not send. Returns rows sent."""

    groups: Dict[frozenset, List[Mapping[str, Any]]] = {}
    for row in rows:
        groups.setdefault(frozenset(row), []).append(row)
    sent = 0
    for group in groups.values():
        for i in range(0, len(group), batch):
            chunk = list(group[i : i + batch])
            r = requests.post(_stats_url(url, "on_conflict=prospect_id"), headers=_headers(key, upsert=True), data=json.dumps(chunk), timeout=60)
            r.raise_for_status()
            sent += len(chunk)
    return sent


def stats_source(season: int, cfbd_id: str) -> Tuple[str, str]:
    return (
        f"College Football Data API (season stats, PPA, usage, game logs, recruiting; {season} season), player {cfbd_id}",
        f"https://collegefootballdata.com/player/{cfbd_id}",
    )


def build_stats_rows(
    prospects: Sequence[Mapping[str, Any]],
    *,
    season: int,
    sink: Mapping[str, Any],
    existing: Mapping[str, Mapping[str, Any]],
    ppa: Optional[Mapping[str, Mapping[str, Any]]],
    usage: Optional[Mapping[str, Mapping[str, Any]]],
    game_weeks: Optional[Mapping[str, Mapping[str, Any]]],
    prior_seasons: Optional[Mapping[int, Mapping[str, Mapping[str, Any]]]],
    recruits: Optional[Tuple[Mapping[str, Any], Mapping[str, Any]]],
    now_iso: str,
) -> List[Dict[str, Any]]:
    """One stats row per prospect. ``None`` for a piece = it was not fetched this run, so the
    column is left out of the row entirely (the stored value stays)."""

    current = parse_season_stats(sink.get("season_stat_rows") or [])
    logos = sink.get("logos") or {}
    rows: List[Dict[str, Any]] = []
    for p in prospects:
        cid = str(p.get("cfbd_id") or "")
        pid = p["id"]
        if not cid:
            continue
        meta = p.get("_meta") or {}
        old = existing.get(pid) or {}
        entries: Dict[int, Dict[str, Any]] = {}
        if cid in current:
            entries[season] = {"team": p.get("school"), **{k: v for k, v in current[cid].items() if k != "team"}}
        for year, by_player in (prior_seasons or {}).items():
            if cid in by_player:
                entries[year] = {"team": by_player[cid].get("team"), **{k: v for k, v in by_player[cid].items() if k != "team"}}
        source, source_url = stats_source(season, cid)
        row: Dict[str, Any] = {
            "prospect_id": pid,
            "cfbd_player_id": cid,
            "stats_season": season,
            "class_year": meta.get("class_year"),
            "height_in": meta.get("height_in"),
            "weight_lb": meta.get("weight_lb"),
            "hometown": meta.get("hometown"),
            "school_logo_url": logos.get(p.get("school")),
            "seasons": merge_seasons(old.get("seasons"), entries),
            "source": source,
            "source_url": source_url,
            "ingested_at": now_iso,
        }
        if ppa is not None or usage is not None:
            has_adv = (ppa or {}).get(cid) or (usage or {}).get(cid)
            row["advanced"] = {"season": season, "ppa": (ppa or {}).get(cid), "usage": (usage or {}).get(cid)} if has_adv else None
        if game_weeks is not None:
            row["game_log"] = merge_game_log(old.get("game_log"), season, [g[cid] for g in game_weeks.values() if cid in g])
        if recruits is not None:
            by_recruit, by_athlete = recruits
            row["recruiting"] = by_athlete.get(cid) or next((by_recruit[r] for r in meta.get("recruit_ids") or [] if r in by_recruit), None)
        rows.append(row)
    return rows


def fetch_stats_bundle(
    key: str,
    season: int,
    wanted: set,
    *,
    today: _dt.date,
    slow: bool,
    have_game_log: bool,
    getter: Callable[..., Any],
    log: Callable[[str], None] = print,
) -> Dict[str, Any]:
    """The CFBD calls for the stats step (``getter`` is already budget-wrapped). Each piece fails
    soft on its own: a failed piece is reported in ``errors`` and left unfetched (None)."""

    out: Dict[str, Any] = {"ppa": None, "usage": None, "game_weeks": None, "prior_seasons": None, "recruits": None, "errors": []}

    def attempt(name: str, fn: Callable[[], Any]) -> Any:
        try:
            return fn()
        except BudgetExceeded:
            out["errors"].append(f"{name}:budget")
        except Exception as exc:
            out["errors"].append(f"{name}:{type(exc).__name__}")
            log(f"stats piece {name} failed: {type(exc).__name__}")
        return None

    live = in_season(today)
    if live or slow:
        out["ppa"] = attempt("ppa", lambda: parse_ppa(getter("/ppa/players/season", {"year": season}, key)))
        out["usage"] = attempt("usage", lambda: parse_usage(getter("/player/usage", {"year": season}, key)))

    def game_weeks() -> Dict[str, Dict[str, Any]]:
        in_progress = season == college_season(today) and today.month >= 8
        last = current_week(today, season) if in_progress else LAST_REGULAR_WEEK
        first = max(0, last - GAME_LOG_RECENT_WEEKS + 1) if have_game_log else 0
        weeks: Dict[str, Dict[str, Any]] = {}
        for week in range(first, last + 1):
            data = getter("/games/players", {"year": season, "week": week, "seasonType": "regular"}, key)
            weeks[f"r{week}"] = parse_game_week(data, week, wanted)
        if today.month in (12, 1) and (today.month == 1 or today.day >= 10):
            data = getter("/games/players", {"year": season, "week": 1, "seasonType": "postseason"}, key)
            weeks["post"] = parse_game_week(data, LAST_REGULAR_WEEK + 1, wanted)
        return weeks

    if live or slow:
        weeks = attempt("game_log", game_weeks)
        if weeks is not None:
            out["game_weeks"] = weeks

    if slow:
        prior: Dict[int, Dict[str, Any]] = {}
        for year in (season - 1, season - 2):
            rows: List[Mapping[str, Any]] = []
            ok = True
            for category in MIN_SEASON_YARDS:
                got = attempt(f"season{year}_{category}", lambda c=category, y=year: getter("/stats/player/season", {"year": y, "category": c}, key))
                if got is None:
                    ok = False
                    break
                rows.extend(got)
            if ok:
                prior[year] = parse_season_stats(rows)
        out["prior_seasons"] = prior or None

        def recruits() -> Tuple[Dict[str, Any], Dict[str, Any]]:
            by_recruit: Dict[str, Any] = {}
            by_athlete: Dict[str, Any] = {}
            for year in range(season - 4, season + 1):
                a, b = parse_recruits(getter("/recruiting/players", {"year": year, "classification": "HighSchool"}, key))
                by_recruit.update(a)
                by_athlete.update(b)
            return by_recruit, by_athlete

        out["recruits"] = attempt("recruiting", recruits)
    return out


def run_stats_step(
    supa_url: str,
    supa_key: str,
    cfbd_key: str,
    prospects: Sequence[Mapping[str, Any]],
    sink: Mapping[str, Any],
    *,
    season: int,
    today: _dt.date,
    now_iso: str,
    force: bool,
    month_calls: int,
    getter: Callable[..., Any] = _cfbd_get,
    log: Callable[[str], None] = print,
) -> Dict[str, Any]:
    """Run the stats step and return its status block (never raises)."""

    try:
        existing = select_existing_stats(supa_url, supa_key)
        if existing is None:
            return {"status": "skipped_migration_pending", "calls": 0}
        remaining = MONTHLY_CALL_CAP - month_calls
        if remaining <= 0:
            return {"status": "skipped_monthly_budget", "calls": 0}
        budget = CallBudget(min(RUN_STATS_CALL_CAP, remaining))
        slow = is_slow_refresh(today, have_rows=bool(existing), force=force)
        have_game_log = any((r.get("game_log") or {}).get("season") == season for r in existing.values())
        wanted = {str(p["cfbd_id"]) for p in prospects if p.get("cfbd_id")}
        bundle = fetch_stats_bundle(
            cfbd_key, season, wanted, today=today, slow=slow, have_game_log=have_game_log, getter=budget.wrap(getter), log=log
        )
        rows = build_stats_rows(
            prospects,
            season=season,
            sink=sink,
            existing=existing,
            ppa=bundle["ppa"],
            usage=bundle["usage"],
            game_weeks=bundle["game_weeks"],
            prior_seasons=bundle["prior_seasons"],
            recruits=bundle["recruits"],
            now_iso=now_iso,
        )
        sent = upsert_stats(supa_url, supa_key, rows) if rows else 0
        return {"status": "ok", "rows": sent, "calls": budget.used, "slow": slow, "errors": bundle["errors"]}
    except Exception as exc:
        return {"status": "error", "error": type(exc).__name__, "calls": 0}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run(
    *,
    environ: Optional[Mapping[str, str]] = None,
    today: Optional[_dt.date] = None,
    force_classes: bool = False,
    log: Callable[[str], None] = print,
    previous_status: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    env = os.environ if environ is None else environ
    today = today or _dt.date.today()
    now_iso = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    supa_url = env.get("SUPABASE_URL", "").strip()
    supa_key = env.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    cfbd_key = env.get("CFBD_API_KEY", "").strip()
    season = college_season(today)
    status: Dict[str, Any] = {"ran_at": now_iso, "season": season, "ok": True, "classes": {}, "stats": {}, "retire": {}}
    month_before = month_calls_so_far(previous_status, today)
    listing_calls = CallBudget(10**6)  # counts what step 1 really spends
    if not (supa_url and supa_key):
        status.update(ok=False, error="supabase_not_configured")
        return status

    extended = True
    # Step 1: class listing (CFBD, key-gated, Mondays unless forced)
    if not cfbd_key:
        status["classes"] = {"status": "skipped_no_key"}
    elif today.weekday() != 0 and not force_classes:
        status["classes"] = {"status": "skipped_not_monday"}
    elif month_before + CLASS_LISTING_CALLS_ESTIMATE > MONTHLY_CALL_CAP:
        status["classes"] = {"status": "skipped_monthly_budget", "month_calls": month_before}
    else:
        try:
            sink: Dict[str, Any] = {}
            candidates = fetch_candidates(cfbd_key, season, log=log, sink=sink, getter=listing_calls.wrap(_cfbd_get))
            if not candidates:
                status["classes"] = {"status": "empty", "fetched": 0}
                status["ok"] = False
            else:
                existing, extended = select_existing(supa_url, supa_key, extended=True)
                rows = reconcile(candidates, existing, season=season, now_iso=now_iso)
                sent, extended = upsert_with_fallback(supa_url, supa_key, rows)
                status["classes"] = {"status": "ok", "fetched": len(candidates), "upserted": sent, "extended_columns": extended}
                status["stats"] = run_stats_step(
                    supa_url, supa_key, cfbd_key, rows, sink,
                    season=season, today=today, now_iso=now_iso, force=force_classes,
                    month_calls=month_before + listing_calls.used, log=log,
                )
        except Exception as exc:
            status["classes"] = {"status": "error", "error": type(exc).__name__}
            status["ok"] = False

    status["cfbd_usage"] = {
        "month": month_key(today),
        "calls": month_before + listing_calls.used + int((status.get("stats") or {}).get("calls") or 0),
    }

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
