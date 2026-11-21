"""College football prospect scouting — crowdsourced grades and watchlist.

The crowd grades no longer feed draft-class strength: that signal
(DYNASTYGM_COLLEGE_SCOUTING_CLASS_STRENGTH_SIGNAL) was retired 2026-11-19, see
docs/audits/2026-11-college-class-strength-retired.md.

Product shape (coridian_, #college-scouting):
  - SHARED primary system: every signed-in user can submit a scouting grade
    (1-5) + optional round projection + optional note on any prospect. All
    grades for a prospect are pooled into one shared aggregate (avg grade,
    scout count).
  - Personal watchlist layered on top: a simple follow/unfollow list, no
    scouting fields duplicated there (modules.college_scouting only holds
    the shape; the actual watchlist rows live in Supabase table
    ``prospect_watchlist`` — see docs/supabase_college_scouting.sql).

NO FABRICATED DATA
------------------
There is no licensed college recruiting/draft data feed wired into this app
yet. This module must never invent prospect names/positions/schools to fill
that gap — a fabricated name presented alongside real players is
indistinguishable from a real scouting subject to the people using this
screen. ``fetch_all_prospects`` therefore reads only from the real Supabase
``college_prospects`` table (see docs/supabase_college_scouting.sql) and
returns an empty list — never invented rows — when that table isn't
configured, migrated, or reachable. An empty catalog is the honest state
until a real prospect data source is integrated.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import requests
from urllib.parse import quote

from modules import auth_supabase


# ---------------------------------------------------------------------------
# Supabase table names (see docs/supabase_college_scouting.sql for schema/RLS)
# ---------------------------------------------------------------------------
PROSPECTS_TABLE = "college_prospects"
SCOUTING_REPORTS_TABLE = "scouting_reports"
# Read-only projection with no user_id (docs/supabase_scouting_privacy_2026_11.sql): author_display_name is null
# for anonymous reports. Falls back to the table until that SQL is applied.
SCOUTING_REPORTS_PUBLIC_VIEW = "scouting_reports_public"
WATCHLIST_TABLE = "prospect_watchlist"

# ---------------------------------------------------------------------------
# This app has no IDP (individual defensive player) scoring support, and
# offensive tackles have zero fantasy scoring value either — so the
# scouting list only ever surfaces the fantasy-relevant skill positions.
# Mirrors the precedent in modules/draft_prospects.py's
# ``draft_watch_positions`` (``["QB", "RB", "WR", "TE"]``), minus K since a
# kicker is never a college draft-prospect scouting subject. Defined locally
# rather than importing modules.rankings.FANTASY_POSITIONS (which also
# pulls in streamlit/pandas) to keep this module's dependency footprint
# small — services/mobile_api_service.py imports this module directly.
# ---------------------------------------------------------------------------
SCOUTING_RELEVANT_POSITIONS = {"QB", "RB", "WR", "TE"}


def _filter_scouting_relevant_prospects(
    rows: Iterable[Mapping[str, Any]]
) -> List[Dict[str, Any]]:
    """Drop any prospect whose position isn't fantasy-relevant
    (SCOUTING_RELEVANT_POSITIONS). Applied centrally so defensive
    positions/offensive tackles never reach the scouting list even if a bad
    row ends up in the real Supabase college_prospects table.
    """

    filtered: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        position = _safe_text(row.get("position")).upper()
        if position not in SCOUTING_RELEVANT_POSITIONS:
            continue
        filtered.append(row)
    return filtered


# ---------------------------------------------------------------------------
# Grading scale
# ---------------------------------------------------------------------------
MIN_GRADE = 1
MAX_GRADE = 5
MIN_ROUND_PROJECTION = 1
MAX_ROUND_PROJECTION = 7


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def normalize_grade(value: Any) -> int | None:
    try:
        parsed = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    if parsed < MIN_GRADE or parsed > MAX_GRADE:
        return None
    return parsed


def normalize_round_projection(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    if parsed < MIN_ROUND_PROJECTION or parsed > MAX_ROUND_PROJECTION:
        return None
    return parsed


def prospects_by_year(prospects: Iterable[Mapping[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    grouped: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for prospect in prospects:
        try:
            year = int(prospect.get("draft_year"))
        except (TypeError, ValueError):
            continue
        grouped[year].append(dict(prospect))
    return dict(grouped)


def aggregate_prospect_scouting(reports: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Pool per-user scouting reports into one shared signal per prospect.

    Returns ``{prospect_id: {"avg_grade", "scout_count", "avg_round_projection",
    "grade_distribution"}}`` — a prospect with no valid reports simply has no
    key here (never a fabricated neutral/zero entry).
    """

    grades_by_prospect: Dict[str, List[int]] = defaultdict(list)
    rounds_by_prospect: Dict[str, List[int]] = defaultdict(list)
    for report in reports:
        prospect_id = _safe_text(report.get("prospect_id"))
        if not prospect_id:
            continue
        grade = normalize_grade(report.get("grade"))
        if grade is not None:
            grades_by_prospect[prospect_id].append(grade)
        round_projection = normalize_round_projection(report.get("round_projection"))
        if round_projection is not None:
            rounds_by_prospect[prospect_id].append(round_projection)

    result: Dict[str, Dict[str, Any]] = {}
    for prospect_id, grades in grades_by_prospect.items():
        distribution = {grade: 0 for grade in range(MIN_GRADE, MAX_GRADE + 1)}
        for grade in grades:
            distribution[grade] += 1
        rounds = rounds_by_prospect.get(prospect_id) or []
        result[prospect_id] = {
            "avg_grade": round(sum(grades) / len(grades), 2),
            "scout_count": len(grades),
            "avg_round_projection": round(sum(rounds) / len(rounds), 2) if rounds else None,
            "grade_distribution": distribution,
        }
    return result


def build_prospect_views(
    prospects: Sequence[Mapping[str, Any]],
    reports: Sequence[Mapping[str, Any]],
    *,
    my_user_id: str = "",
    my_reports: Sequence[Mapping[str, Any]] | None = None,
    watchlist_prospect_ids: Iterable[str] = (),
) -> List[Dict[str, Any]]:
    """One row per prospect for the mobile scouting/watchlist screen: the
    shared aggregate, the caller's own report (if any), and whether it's on
    the caller's personal watchlist. Sorted by draft year (desc), then
    position, then name for a stable, predictable list.
    """

    aggregate = aggregate_prospect_scouting(reports)
    my_reports_by_prospect: Dict[str, Dict[str, Any]] = {}
    # The caller's own rows come from their own RLS-scoped read (``my_reports``); the shared list carries no user_id.
    own_rows = my_reports if my_reports is not None else (reports if my_user_id else ())
    for report in own_rows:
        if my_reports is None and _safe_text(report.get("user_id")) != my_user_id:
            continue
        pid = _safe_text(report.get("prospect_id"))
        if pid:
            my_reports_by_prospect[pid] = report
    watchlist_ids = {_safe_text(pid) for pid in watchlist_prospect_ids if _safe_text(pid)}

    rows: List[Dict[str, Any]] = []
    for prospect in prospects:
        pid = _safe_text(prospect.get("id"))
        if not pid:
            continue
        my_report = my_reports_by_prospect.get(pid)
        agg = aggregate.get(pid)
        rows.append(
            {
                "id": pid,
                "name": _safe_text(prospect.get("name")),
                "position": _safe_text(prospect.get("position")),
                "school": _safe_text(prospect.get("school")),
                "draft_year": int(prospect.get("draft_year")) if str(prospect.get("draft_year") or "").strip() else None,
                "aggregate": {
                    "avg_grade": agg["avg_grade"] if agg else None,
                    "scout_count": agg["scout_count"] if agg else 0,
                    "avg_round_projection": agg["avg_round_projection"] if agg else None,
                },
                "my_report": (
                    {
                        "grade": normalize_grade(my_report.get("grade")),
                        "round_projection": normalize_round_projection(my_report.get("round_projection")),
                        "note": _safe_text(my_report.get("note"))[:280],
                        # Absent column (SQL not applied) reads as anonymous.
                        "anonymous": my_report.get("anonymous") is not False,
                    }
                    if my_report
                    else None
                ),
                "on_watchlist": pid in watchlist_ids,
                # Post-draft hand-off: once drafted and mapped, the card opens the normal NFL player card.
                "sleeper_player_id": _safe_text(prospect.get("sleeper_player_id")) or None,
            }
        )
    rows.sort(key=lambda row: (-(row["draft_year"] or 0), row["position"], row["name"]))
    return rows


# ---------------------------------------------------------------------------
# Supabase access (shared/cross-user reads use the caller's own JWT — RLS on
# scouting_reports and college_prospects deliberately allows SELECT to any
# authenticated user; see docs/supabase_college_scouting.sql for why).
# ---------------------------------------------------------------------------


def fetch_all_prospects(
    config: dict, access_token: str, *, timeout: float = 15
) -> Tuple[List[Dict[str, Any]], str]:
    """The shared prospect catalog, read from the real Supabase
    ``college_prospects`` table only — see the module docstring's "NO
    FABRICATED DATA" section. Returns ``(rows, error)``: ``error`` is ``""``
    on success (including a legitimately empty, real, migrated table) or a
    reason string ("not_configured"/"not_available") when the real catalog
    isn't configured, migrated, or reachable. There is no invented-data
    fallback — an unreachable catalog simply returns an empty list, the same
    fail-soft shape as fetch_all_scouting_reports below.

    Rows are filtered to SCOUTING_RELEVANT_POSITIONS before returning: this
    app has no IDP support, so defensive positions/offensive tackles must
    never reach the scouting list even if they exist in Supabase.
    """

    if not auth_supabase.is_configured(config):
        return [], "not_configured"
    response = None
    # Ask for the post-draft flag first; fall back to the base columns when the
    # optional migration (docs/supabase_college_prospects_ingest.sql) is absent.
    for select in (
        "select=id,name,position,school,draft_year,drafted,nfl_team,sleeper_player_id",
        "select=id,name,position,school,draft_year,drafted",
        "select=id,name,position,school,draft_year",
    ):
        try:
            response = requests.get(
                auth_supabase.rest_api_url(config, PROSPECTS_TABLE, select),
                headers=auth_supabase.auth_headers(config, access_token),
                timeout=timeout,
            )
        except Exception:
            return [], "not_available"
        if response.status_code < 400:
            break
    if response is None or response.status_code >= 400:
        return [], "not_available"
    try:
        rows = response.json()
    except Exception:
        return [], "not_available"
    if not isinstance(rows, list):
        return [], "not_available"
    # Drafted prospects are retired (hidden), never deleted.
    rows = [r for r in rows if not (isinstance(r, dict) and r.get("drafted") is True)]
    return _filter_scouting_relevant_prospects(rows), ""


def fetch_all_scouting_reports(
    config: dict, access_token: str, *, timeout: float = 15
) -> Tuple[List[Dict[str, Any]], str]:
    """Every user's scouting report — used both to render the shared
    aggregate. Fails soft to an
    empty list (never raises) if the table isn't reachable yet.
    """

    if not auth_supabase.is_configured(config):
        return [], "not_configured"
    # Never selects user_id: the shared pool is anonymous aggregate input plus, for non-anonymous authors, a
    # display name. Prefer the public view; fall back to the table (still without user_id) before the SQL is applied.
    response = None
    for table, columns in (
        (SCOUTING_REPORTS_PUBLIC_VIEW, "prospect_id,grade,round_projection,note,author_display_name"),
        (SCOUTING_REPORTS_TABLE, "prospect_id,grade,round_projection,note"),
    ):
        try:
            response = requests.get(
                auth_supabase.rest_api_url(config, table, f"select={columns}"),
                headers=auth_supabase.auth_headers(config, access_token),
                timeout=timeout,
            )
        except Exception:
            return [], "not_available"
        if response.status_code < 400:
            break
    if response is None or response.status_code >= 400:
        return [], "not_available"
    try:
        rows = response.json()
    except Exception:
        return [], "not_available"
    if not isinstance(rows, list):
        return [], "not_available"
    return [row for row in rows if isinstance(row, dict)], ""


# In-process TTL cache for the raw
# prospects/reports lists it's built from). This is shared, slow-moving,
# cross-user data (identical for every caller — pooled grades, not anything
# scoped to the requesting user), so refetching it from Supabase on every
# single request would be pure waste against a performance-sensitive hot
# path (modules/trade_ideas.py's pick valuation is explicitly
# profiled/instrumented elsewhere for exactly this reason). Before this,
# modules.college_scouting_ui's College Scouting page called
# fetch_all_prospects/fetch_all_scouting_reports directly on every single
# page render — two uncached Supabase round-trips per view, the same bug
# class as the Player Detail News blocking-RSS-fetch fix (#958) and the
# NFL-schedule CSV re-parse fix (#960).
CACHE_TTL_SECONDS = 600.0
_prospects_cache: Dict[str, Any] = {"data": None, "fetched_at": 0.0}
_reports_cache: Dict[str, Any] = {"data": None, "fetched_at": 0.0}


def get_cached_all_prospects(
    config: dict,
    access_token: str,
    *,
    now: float | None = None,
) -> Tuple[List[Dict[str, Any]], str]:
    """Cached wrapper around ``fetch_all_prospects``.

    The prospect catalog is identical for every caller (no per-user
    filtering), so a successful fetch is reused for
    ``CACHE_TTL_SECONDS`` instead of re-hitting Supabase on every page
    render/request. A failed fetch is never cached (so the page recovers
    on the very next view once the table is reachable again).
    """

    current_time = time.time() if now is None else now
    cached = _prospects_cache.get("data")
    fetched_at = float(_prospects_cache.get("fetched_at") or 0.0)
    if cached is not None and (current_time - fetched_at) < CACHE_TTL_SECONDS:
        return cached, ""

    prospects, error = fetch_all_prospects(config, access_token)
    if error:
        return prospects, error
    _prospects_cache["data"] = prospects
    _prospects_cache["fetched_at"] = current_time
    return prospects, error


def get_cached_all_scouting_reports(
    config: dict,
    access_token: str,
    *,
    now: float | None = None,
) -> Tuple[List[Dict[str, Any]], str]:
    """Cached wrapper around ``fetch_all_scouting_reports`` — see
    ``get_cached_all_prospects`` for why this is safe to share across
    callers/users."""

    current_time = time.time() if now is None else now
    cached = _reports_cache.get("data")
    fetched_at = float(_reports_cache.get("fetched_at") or 0.0)
    if cached is not None and (current_time - fetched_at) < CACHE_TTL_SECONDS:
        return cached, ""

    reports, error = fetch_all_scouting_reports(config, access_token)
    if error:
        return reports, error
    _reports_cache["data"] = reports
    _reports_cache["fetched_at"] = current_time
    return reports, error


def _reset_cache_for_tests() -> None:
    """Test-only helper — production code never calls this."""

    _prospects_cache["data"] = None
    _prospects_cache["fetched_at"] = 0.0
    _reports_cache["data"] = None
    _reports_cache["fetched_at"] = 0.0


# ---------------------------------------------------------------------------
# Prospect detail sheet (stats + profile) — reads public.college_prospect_stats,
# filled weekly by modules/college_prospect_ingest.py from College Football Data.
# Every number is CFBD's; fantasy points are derived from CFBD stat lines here and
# labelled as derived. Fail-soft: no table / no row = "no stats yet", never invented.
# ---------------------------------------------------------------------------
STATS_TABLE = "college_prospect_stats"
STATS_SOURCE_NAME = "College Football Data"
STATS_SOURCE_URL = "https://collegefootballdata.com"
# College PPR-style fantasy scoring. CFBD has no fumbles / 2-pt data, so those are not scored.
COLLEGE_FANTASY_RULES = (
    "PPR: 0.04 per pass yd, 4 per pass TD, -2 per INT, 0.1 per rush/rec yd, 6 per rush/rec TD, "
    "1 per catch. No fumbles or 2-pt (CFBD does not carry them)."
)


def college_fantasy_points(line: Mapping[str, Any] | None) -> float | None:
    """Derived PPR-style points from one CFBD stat line ({passing, rushing, receiving}); None with no scoring stats."""

    if not isinstance(line, Mapping):
        return None
    total = 0.0
    seen = False
    for category, weights in (
        ("passing", {"yds": 0.04, "td": 4.0, "int": -2.0}),
        ("rushing", {"yds": 0.1, "td": 6.0}),
        ("receiving", {"yds": 0.1, "td": 6.0, "rec": 1.0}),
    ):
        part = line.get(category)
        if not isinstance(part, Mapping):
            continue
        for key, weight in weights.items():
            try:
                value = float(part.get(key))
            except (TypeError, ValueError):
                continue
            seen = True
            total += value * weight
    return round(total, 1) if seen else None


def fetch_prospect_row(config: dict, access_token: str, prospect_id: str, *, timeout: float = 10) -> Dict[str, Any] | None:
    if not auth_supabase.is_configured(config) or not prospect_id:
        return None
    for select in (
        "select=id,name,position,school,draft_year,drafted,nfl_team,draft_round,draft_pick,sleeper_player_id",
        "select=id,name,position,school,draft_year",
    ):
        try:
            response = requests.get(
                auth_supabase.rest_api_url(config, PROSPECTS_TABLE, f"{select}&id=eq.{quote(prospect_id, safe='')}&limit=1"),
                headers=auth_supabase.auth_headers(config, access_token),
                timeout=timeout,
            )
            if response.status_code >= 400:
                continue
            rows = response.json()
        except Exception:
            return None
        return rows[0] if isinstance(rows, list) and rows and isinstance(rows[0], dict) else None
    return None


def fetch_prospect_stats_row(config: dict, access_token: str, prospect_id: str, *, timeout: float = 10) -> Dict[str, Any] | None:
    """The stats row, or None when absent / the migration (docs/supabase_college_prospect_stats.sql) is not applied."""

    if not auth_supabase.is_configured(config) or not prospect_id:
        return None
    try:
        response = requests.get(
            auth_supabase.rest_api_url(config, STATS_TABLE, f"select=*&prospect_id=eq.{quote(prospect_id, safe='')}&limit=1"),
            headers=auth_supabase.auth_headers(config, access_token),
            timeout=timeout,
        )
        if response.status_code >= 400:
            return None
        rows = response.json()
    except Exception:
        return None
    return rows[0] if isinstance(rows, list) and rows and isinstance(rows[0], dict) else None


def _clean_season(entry: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"season": entry.get("season"), "team": entry.get("team")}
    for category in ("passing", "rushing", "receiving"):
        if isinstance(entry.get(category), Mapping) and entry[category]:
            out[category] = dict(entry[category])
    out["fantasy_points"] = college_fantasy_points(out)
    return out


def build_prospect_profile(
    prospect: Mapping[str, Any],
    stats_row: Mapping[str, Any] | None,
    *,
    is_pro: bool,
    adp: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """The prospect detail payload. Basics (season lines, weekly log, bio, recruiting, ADP) are free;
    advanced metrics (PPA, usage) are withheld server-side unless the caller is Pro."""

    row = stats_row or {}
    seasons = [_clean_season(e) for e in (row.get("seasons") or []) if isinstance(e, Mapping)]
    seasons = [s for s in seasons if any(k in s for k in ("passing", "rushing", "receiving"))]
    seasons.sort(key=lambda s: -(int(s["season"]) if str(s.get("season") or "").isdigit() else 0))
    log = row.get("game_log") if isinstance(row.get("game_log"), Mapping) else None
    weekly = None
    if log and log.get("games"):
        games = []
        for g in log["games"]:
            if not isinstance(g, Mapping) or g.get("week") is None:
                continue
            clean = {"week": g.get("week"), "opponent": g.get("opponent")}
            for category in ("passing", "rushing", "receiving"):
                if isinstance(g.get(category), Mapping):
                    clean[category] = dict(g[category])
            clean["fantasy_points"] = college_fantasy_points(clean)
            games.append(clean)
        weekly = {"season": log.get("season"), "games": games} if games else None
    advanced = row.get("advanced") if isinstance(row.get("advanced"), Mapping) else None
    has_advanced = bool(advanced and (advanced.get("ppa") or advanced.get("usage")))
    ingested = row.get("ingested_at")
    return {
        "ok": True,
        "prospect": {
            "id": _safe_text(prospect.get("id")),
            "name": _safe_text(prospect.get("name")),
            "position": _safe_text(prospect.get("position")),
            "school": _safe_text(prospect.get("school")),
            "draft_year": prospect.get("draft_year"),
            "drafted": prospect.get("drafted") is True,
            "nfl_team": prospect.get("nfl_team"),
            "draft_round": prospect.get("draft_round"),
            "draft_pick": prospect.get("draft_pick"),
            "sleeper_player_id": _safe_text(prospect.get("sleeper_player_id")) or None,
        },
        "bio": {
            "class_year": row.get("class_year"),
            "height_in": row.get("height_in"),
            "weight_lb": row.get("weight_lb"),
            "hometown": row.get("hometown"),
            "school_logo_url": row.get("school_logo_url"),
        },
        "stats_available": bool(seasons or weekly),
        "seasons": seasons,
        "weekly": weekly,
        "fantasy_rules": COLLEGE_FANTASY_RULES,
        "advanced": dict(advanced) if (has_advanced and is_pro) else None,
        "advanced_available": has_advanced,
        "advanced_locked": bool(has_advanced and not is_pro),
        "recruiting": row.get("recruiting") if isinstance(row.get("recruiting"), Mapping) else None,
        "adp": dict(adp) if adp else None,
        "source": {
            "name": STATS_SOURCE_NAME,
            "url": row.get("source_url") or STATS_SOURCE_URL,
            "detail": row.get("source"),
            "as_of": str(ingested)[:10] if ingested else None,
        },
    }
