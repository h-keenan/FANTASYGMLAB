"""College football prospect scouting — crowdsourced signal feeding the
existing rookie draft-class-strength calculation (modules/trade_ideas.py's
``DEFAULT_CLASS_STRENGTH_BY_YEAR`` / ``_rookie_class_strength_multiplier``).

Product shape (coridian_, #college-scouting):
  - SHARED primary system: every signed-in user can submit a scouting grade
    (1-5) + optional round projection + optional note on any prospect. All
    grades for a prospect are pooled into one shared aggregate (avg grade,
    scout count) — that aggregate, never any single user's opinion, is what
    can influence draft-class strength.
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

Confidence discipline
----------------------
Same "don't fabricate confidence" posture as modules/player_projections.py's
honest low/high + confidence-label pattern: a prospect (or an entire draft
class) with zero scouting reports contributes nothing — not a "weak" signal,
not a "strong" one, just absent — and a class with only a handful of reports
has its influence shrunk toward neutral (1.0x) rather than trusted at full
strength. Only a healthy sample size earns full weight.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import requests

from modules import auth_supabase
from modules import experimental_graduation

# Live-fetch gate for the draft-class-strength wiring specifically (separate
# from the scouting/watchlist CRUD endpoints, which are always available).
# Defaults OFF — unlike this codebase's usual graduated-default-ON kill
# switches, this one adds a real (cached, but real) network round trip to
# two performance-sensitive valuation endpoints
# (services/mobile_api_service.py's draft-picks and trade-analyzer
# handlers) for a signal that is a provable no-op (empty dict, neutral
# 1.0x) until real users have actually submitted scouting reports. Flip
# DYNASTYGM_COLLEGE_SCOUTING_CLASS_STRENGTH_SIGNAL=1 on once there's a real
# scouting pool worth blending in.
CLASS_STRENGTH_SIGNAL_ENV_KEY = "DYNASTYGM_COLLEGE_SCOUTING_CLASS_STRENGTH_SIGNAL"


def class_strength_signal_enabled(*, environ: Mapping[str, str] | None = None) -> bool:
    return experimental_graduation.graduated_kill_switch_enabled(
        CLASS_STRENGTH_SIGNAL_ENV_KEY, environ=environ, default=False
    )

# ---------------------------------------------------------------------------
# Supabase table names (see docs/supabase_college_scouting.sql for schema/RLS)
# ---------------------------------------------------------------------------
PROSPECTS_TABLE = "college_prospects"
SCOUTING_REPORTS_TABLE = "scouting_reports"
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
NEUTRAL_GRADE = 3.0
MIN_ROUND_PROJECTION = 1
MAX_ROUND_PROJECTION = 7

# ---------------------------------------------------------------------------
# Confidence thresholds for the crowd -> class-strength signal. Mirrors
# modules/player_projections.py's small-sample-penalty posture rather than
# copying its exact numbers (a different signal, different sample sizes).
# ---------------------------------------------------------------------------
MIN_SCOUTS_FOR_MEDIUM_CONFIDENCE = 3
MIN_SCOUTS_FOR_FULL_CONFIDENCE = 8

# How much one full-confidence grade point (away from neutral) moves the
# class-strength multiplier. 0.1/point means an average grade of 5.0 reaches
# +0.2 (1.2x) and an average of 1.0 reaches -0.2 (0.8x) — sized so a single,
# confident crowd class-strength signal stays within
# modules.trade_ideas's existing [0.8, 1.25] clamp on its own, before it is
# even multiplied against the separate editorial class_strength_by_year.
CLASS_STRENGTH_GRADE_SCALE = 0.1
CLASS_STRENGTH_CLAMP = (0.8, 1.25)


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


def _confidence_label(scout_count: int) -> str:
    if scout_count >= MIN_SCOUTS_FOR_FULL_CONFIDENCE:
        return "high"
    if scout_count >= MIN_SCOUTS_FOR_MEDIUM_CONFIDENCE:
        return "medium"
    return "low"


def crowd_class_strength_by_year(
    prospects: Sequence[Mapping[str, Any]],
    reports: Sequence[Mapping[str, Any]],
) -> Dict[int, Dict[str, Any]]:
    """The shared scouting pool's opinion of each draft class, as a
    multiplier meant to be combined with (not replace) the existing editorial
    ``DEFAULT_CLASS_STRENGTH_BY_YEAR`` in modules/trade_ideas.py.

    A draft year with zero valid scouting reports is omitted entirely — the
    caller (modules.trade_ideas._rookie_class_strength_multiplier) treats an
    absent year as neutral (1.0x, no effect), never as a strong or weak
    signal. Small samples are shrunk toward neutral rather than clamped
    straight to the raw average, same discipline as
    modules/player_projections.py's small-sample penalty.
    """

    year_by_prospect_id = {
        _safe_text(p.get("id")): int(p["draft_year"])
        for p in prospects
        if _safe_text(p.get("id")) and str(p.get("draft_year") or "").strip()
    }
    total_prospects_by_year: Dict[int, int] = defaultdict(int)
    for year in year_by_prospect_id.values():
        total_prospects_by_year[year] += 1

    grades_by_year: Dict[int, List[int]] = defaultdict(list)
    scouted_prospects_by_year: Dict[int, set] = defaultdict(set)
    for report in reports:
        prospect_id = _safe_text(report.get("prospect_id"))
        year = year_by_prospect_id.get(prospect_id)
        if year is None:
            continue
        grade = normalize_grade(report.get("grade"))
        if grade is None:
            continue
        grades_by_year[year].append(grade)
        scouted_prospects_by_year[year].add(prospect_id)

    result: Dict[int, Dict[str, Any]] = {}
    for year, grades in grades_by_year.items():
        scout_count = len(grades)
        if scout_count == 0:
            continue
        avg_grade = sum(grades) / scout_count
        raw_multiplier = 1.0 + ((avg_grade - NEUTRAL_GRADE) * CLASS_STRENGTH_GRADE_SCALE)
        confidence_weight = min(1.0, scout_count / MIN_SCOUTS_FOR_FULL_CONFIDENCE)
        blended = 1.0 + ((raw_multiplier - 1.0) * confidence_weight)
        low, high = CLASS_STRENGTH_CLAMP
        clamped = max(low, min(high, blended))
        result[year] = {
            "multiplier": round(clamped, 4),
            "confidence": _confidence_label(scout_count),
            "scout_count": scout_count,
            "avg_grade": round(avg_grade, 2),
            "prospects_scouted": len(scouted_prospects_by_year[year]),
            "total_prospects_in_class": total_prospects_by_year.get(year, 0),
        }
    return result


def build_prospect_views(
    prospects: Sequence[Mapping[str, Any]],
    reports: Sequence[Mapping[str, Any]],
    *,
    my_user_id: str = "",
    watchlist_prospect_ids: Iterable[str] = (),
) -> List[Dict[str, Any]]:
    """One row per prospect for the mobile scouting/watchlist screen: the
    shared aggregate, the caller's own report (if any), and whether it's on
    the caller's personal watchlist. Sorted by draft year (desc), then
    position, then name for a stable, predictable list.
    """

    aggregate = aggregate_prospect_scouting(reports)
    my_reports: Dict[str, Dict[str, Any]] = {}
    if my_user_id:
        for report in reports:
            if _safe_text(report.get("user_id")) == my_user_id:
                pid = _safe_text(report.get("prospect_id"))
                if pid:
                    my_reports[pid] = report
    watchlist_ids = {_safe_text(pid) for pid in watchlist_prospect_ids if _safe_text(pid)}

    rows: List[Dict[str, Any]] = []
    for prospect in prospects:
        pid = _safe_text(prospect.get("id"))
        if not pid:
            continue
        my_report = my_reports.get(pid)
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
                    }
                    if my_report
                    else None
                ),
                "on_watchlist": pid in watchlist_ids,
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
    try:
        response = requests.get(
            auth_supabase.rest_api_url(config, PROSPECTS_TABLE, "select=id,name,position,school,draft_year"),
            headers=auth_supabase.auth_headers(config, access_token),
            timeout=timeout,
        )
    except Exception:
        return [], "not_available"
    if response.status_code >= 400:
        return [], "not_available"
    try:
        rows = response.json()
    except Exception:
        return [], "not_available"
    if not isinstance(rows, list):
        return [], "not_available"
    return _filter_scouting_relevant_prospects(rows), ""


def fetch_all_scouting_reports(
    config: dict, access_token: str, *, timeout: float = 15
) -> Tuple[List[Dict[str, Any]], str]:
    """Every user's scouting report — used both to render the shared
    aggregate and to feed crowd_class_strength_by_year. Fails soft to an
    empty list (never raises) if the table isn't reachable yet.
    """

    if not auth_supabase.is_configured(config):
        return [], "not_configured"
    try:
        response = requests.get(
            auth_supabase.rest_api_url(
                config, SCOUTING_REPORTS_TABLE, "select=user_id,prospect_id,grade,round_projection,note"
            ),
            headers=auth_supabase.auth_headers(config, access_token),
            timeout=timeout,
        )
    except Exception:
        return [], "not_available"
    if response.status_code >= 400:
        return [], "not_available"
    try:
        rows = response.json()
    except Exception:
        return [], "not_available"
    if not isinstance(rows, list):
        return [], "not_available"
    return [row for row in rows if isinstance(row, dict)], ""


# In-process TTL cache for the crowd class-strength signal (and the raw
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
_class_strength_cache: Dict[str, Any] = {"data": None, "fetched_at": 0.0}
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


def get_cached_crowd_class_strength_by_year(
    config: dict,
    access_token: str,
    *,
    now: float | None = None,
) -> Dict[int, Dict[str, Any]]:
    """Cached wrapper around crowd_class_strength_by_year for request-time
    callers (services/mobile_api_service.py). Returns {} (neutral — no
    effect on valuations) on any fetch failure rather than raising.
    """

    current_time = time.time() if now is None else now
    cached = _class_strength_cache.get("data")
    fetched_at = float(_class_strength_cache.get("fetched_at") or 0.0)
    if cached is not None and (current_time - fetched_at) < CACHE_TTL_SECONDS:
        return cached

    prospects, _ = get_cached_all_prospects(config, access_token, now=current_time)
    reports, error = get_cached_all_scouting_reports(config, access_token, now=current_time)
    if error:
        # Don't cache a failure as if it were "no data forever" — just
        # return neutral for this call and try again next time.
        return {}
    signal = crowd_class_strength_by_year(prospects, reports)
    _class_strength_cache["data"] = signal
    _class_strength_cache["fetched_at"] = current_time
    return signal


def _reset_cache_for_tests() -> None:
    """Test-only helper — production code never calls this."""

    _class_strength_cache["data"] = None
    _class_strength_cache["fetched_at"] = 0.0
    _prospects_cache["data"] = None
    _prospects_cache["fetched_at"] = 0.0
    _reports_cache["data"] = None
    _reports_cache["fetched_at"] = 0.0
