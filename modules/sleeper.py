import json
import os
import threading
import time
from functools import lru_cache
from typing import Dict, Any, List, Optional
from urllib.parse import quote

import requests

from modules import performance, sleeper_budget
from modules.file_lock import ExclusiveFileLock

SLEEPER_BASE = "https://api.sleeper.app/v1"
PLAYERS_CACHE_PATH = "data/sleeper_players.json"
# Was 60*60 — the entire "Nico Collins still shows as a starter after being
# ruled Out" class of bug traced back to this single number: the mobile
# API's stale-while-revalidate refresh (services/mobile_api_service.py's
# _maybe_schedule_players_refresh, via modules.startup_cold_path /
# modules.players_refresh_flight) only re-checks Sleeper this often, so an
# in-game status change could lag up to an hour. Lowered so a live gameday
# ruling reaches the app in minutes, not up to an hour — the existing
# single-flight + 45s failure-cooldown guard (players_refresh_flight.py)
# already prevents this from hammering Sleeper, so shortening the interval
# doesn't add stampede risk, just a few more cheap background refreshes/hour.
PLAYERS_CACHE_TTL_SECONDS = 5 * 60
PLAYER_STATS_CACHE_TEMPLATE = "data/sleeper_player_stats_{season}.json"
PLAYER_STATS_CACHE_TTL_SECONDS = 12 * 60 * 60
COMPLETED_PLAYER_STATS_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60
# Completed prior seasons are effectively immutable — keep them warm for months.
PRIOR_PLAYER_STATS_CACHE_TTL_SECONDS = 180 * 24 * 60 * 60
SLEEPER_AVATAR_BASE = "https://sleepercdn.com/avatars"

PLAYER_STATS_SUM_FIELDS = {
    "gp": "games_played",
    "rec_tgt": "targets",
    "rec": "receptions",
    "rec_yd": "receiving_yards",
    "rec_td": "receiving_tds",
    "rush_att": "rush_attempts",
    "rush_yd": "rushing_yards",
    "rush_td": "rushing_tds",
    "pass_att": "pass_attempts",
    "pass_yd": "passing_yards",
    "pass_td": "passing_tds",
    "pts_std": "fantasy_points",
    "pts_half_ppr": "fantasy_points_half_ppr",
    "pts_ppr": "fantasy_points_ppr",
    "off_snp": "_offensive_snaps",
    "tm_off_snp": "_team_offensive_snaps",
}

# Compact per-week fields retained from the same fetch (no extra provider calls).
WEEKLY_RETAIN_SOURCE_FIELDS = (
    "gp",
    "rec_tgt",
    "rec",
    "rush_att",
    "pass_att",
    "off_snp",
    "tm_off_snp",
    "pts_ppr",
)
WEEKLY_RETAIN_FIELD_MAP = {
    "gp": "games_played",
    "rec_tgt": "targets",
    "rec": "receptions",
    "rush_att": "rush_attempts",
    "pass_att": "pass_attempts",
    "pts_ppr": "fantasy_points_ppr",
}

# Per-week box-score fields, kept on the SAME weekly rows from the SAME
# Sleeper ``/stats/nfl/regular/{season}/{week}`` payloads this module already
# fetches (no new provider call). Added for the external content-bot API's
# week-result / weekly recap endpoints (docs/external-api-contract.md,
# "Weekly recap"). Before this, per-week yards/TDs/standard points were only
# summed into season totals (``PLAYER_STATS_SUM_FIELDS``) and then dropped
# at the weekly grain.
#
# These are deliberately NOT in ``WEEKLY_RETAIN_SOURCE_FIELDS``: whether a
# weekly row exists is still decided only by those original fields, so
# widening retention never adds a new row (or changes which weeks count as
# "played") for any existing weekly-stats consumer. It only adds keys to
# rows that already existed. Sleeper omits zero-valued stat keys from its
# weekly payload, so an absent key here means "not reported" and is never
# written as a 0.
WEEKLY_BOX_SCORE_FIELD_MAP = {
    "pass_cmp": "passing_completions",
    "pass_yd": "passing_yards",
    "pass_td": "passing_tds",
    "pass_int": "passing_interceptions",
    "rush_yd": "rushing_yards",
    "rush_td": "rushing_tds",
    "rec_yd": "receiving_yards",
    "rec_td": "receiving_tds",
    "fum_lost": "fumbles_lost",
    "fgm": "field_goals_made",
    "fga": "field_goals_attempted",
    "xpm": "extra_points_made",
    "xpa": "extra_points_attempted",
    "pts_std": "fantasy_points_standard",
    "pts_half_ppr": "fantasy_points_half_ppr",
}
# Individual-defensive-player (IDP) weekly fields from the same payloads.
# Verified against real Sleeper payloads (2024 and 2025, weeks 1-18; see
# docs/idp-support.md): defenders carry ``idp_*`` counting stats plus
# ``def_snp`` / ``tm_def_snp`` (defensive snaps and team defensive snaps).
# Sleeper omits zero-valued keys, so an absent key means "not reported" and
# is never written as 0 - the defensive-snap fields tell consumers whether
# the player was actually on the field. ``idp_tkl`` is Sleeper's combined
# tackle total (solo + assist); ``idp_tkl_loss`` is tackles for loss. Values
# stay floats because sacks and tackle credit can be fractional.
WEEKLY_IDP_FIELD_MAP = {
    "idp_tkl_solo": "idp_tkl_solo",
    "idp_tkl_ast": "idp_tkl_ast",
    "idp_tkl": "idp_tkl",
    "idp_tkl_loss": "idp_tkl_loss",
    "idp_sack": "idp_sack",
    "idp_qb_hit": "idp_qb_hit",
    "idp_int": "idp_int",
    "idp_pass_def": "idp_pass_def",
    "idp_ff": "idp_ff",
    "idp_fum_rec": "idp_fum_rec",
    "idp_def_td": "idp_def_td",
    "idp_safe": "idp_safe",
    "idp_blk_kick": "idp_blk_kick",
    "idp_sack_yd": "idp_sack_yd",
    "idp_int_ret_yd": "idp_int_ret_yd",
    "idp_fum_ret_yd": "idp_fum_ret_yd",
    "idp_pass_def_3p": "idp_pass_def_3p",
    "gs": "games_started",
}
# Marker: a weekly row carrying this key was written after IDP retention shipped.
WEEKLY_IDP_SCHEMA_MARKER_FIELD = "defensive_snaps"

# Point totals stay floats; every other box-score field is a whole-number count.
WEEKLY_BOX_SCORE_FLOAT_FIELDS = frozenset({"fantasy_points_standard", "fantasy_points_half_ppr"})
# Sleeper publishes ``pts_half_ppr`` next to ``pts_ppr`` for every player
# with a scored stat line, so a season cache where no weekly row carries the
# mapped key was written before box-score retention shipped (see
# ``season_stats_cache_has_box_scores``).
WEEKLY_BOX_SCORE_SCHEMA_MARKER_FIELD = "fantasy_points_half_ppr"


# Fantasy-point fields Sleeper omits from a weekly payload when a player who
# PLAYED scored exactly 0 under that format. Sleeper drops every zero-valued
# stat key, so a played 0-point game has no ``pts_ppr`` at all; reading that
# absence as "did not play" silently dropped real zeros from every weekly
# consumer (recency trends, projections, usage, box scores).
PLAYED_ZERO_POINT_FIELDS = ("fantasy_points_ppr",)
PLAYED_ZERO_BOX_SCORE_POINT_FIELDS = ("fantasy_points_half_ppr", "fantasy_points_standard")


def week_row_played(row: Dict[str, Any] | None) -> bool:
    """True when a weekly row is a game the player actually appeared in.

    The participation signal is Sleeper's own ``gp`` (games played; kept on
    weekly rows as ``games_played``). It was chosen over the alternatives
    after checking real Sleeper weekly payloads (2024 weeks 1-18):

    - ``gp`` is present only when the player appeared in the game. An
      inactive, injured (e.g. Christian McCaffrey on IR, 2024 week 5) or
      bye-week player's row has no ``gp`` at all, while a player who appeared
      and scored 0 still has ``gp: 1``.
    - ``gms_active`` is ``1`` on every row, inactive players included, so it
      carries no signal.
    - Offensive snaps (``off_snp``, and so ``snap_share``) are never present
      for kickers, and ``tm_off_snp`` is missing from some real weeks, so a
      snap gate drops real games played.

    A game where the player only played special teams counts as played: his
    fantasy result really was 0.
    """

    if not isinstance(row, dict):
        return False
    try:
        return float(row.get("games_played") or 0) >= 1
    except (TypeError, ValueError):
        return False


def week_row_fantasy_points_ppr(row: Dict[str, Any] | None) -> float | None:
    """A weekly row's real PPR points: Sleeper's ``pts_ppr`` when present, a
    real 0.0 when the player played (``week_row_played``) but Sleeper omitted
    the zero, and None when he did not play (inactive, injured, bye)."""

    if not isinstance(row, dict):
        return None
    value = row.get("fantasy_points_ppr")
    if value is not None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return 0.0 if week_row_played(row) else None


def _fill_played_zero_points(row: Dict[str, Any], *, include_box_score_points: bool) -> None:
    if not week_row_played(row):
        return
    fields = PLAYED_ZERO_POINT_FIELDS
    if include_box_score_points:
        fields = fields + PLAYED_ZERO_BOX_SCORE_POINT_FIELDS
    for field in fields:
        if row.get(field) is None:
            row[field] = 0.0


def backfill_played_zero_points(cached: Dict[str, Any] | None) -> Dict[str, Any] | None:
    """Fill the real 0-point fields on played weekly rows of a season cache
    written before ``_extract_week_observation`` did so itself (in place).

    Half-PPR / standard points are only filled when the cache retained
    box-score fields at all (``season_stats_cache_has_box_scores``); filling
    them on an older cache would make it look as if it had box scores.
    """

    if not isinstance(cached, dict):
        return cached
    include_box = season_stats_cache_has_box_scores(cached)
    for values in cached.values():
        weekly = values.get("weekly") if isinstance(values, dict) else None
        if not isinstance(weekly, list):
            continue
        for row in weekly:
            if isinstance(row, dict):
                _fill_played_zero_points(row, include_box_score_points=include_box)
    return cached


def default_player_stats_season(now: time.struct_time | None = None) -> int:
    """Canonical active NFL stats season (Sep+ → calendar year, else prior year)."""

    current = now or time.localtime()
    return int(current.tm_year if current.tm_mon >= 9 else current.tm_year - 1)


def prior_player_stats_season(now: time.struct_time | None = None) -> int:
    """Immediately previous NFL season relative to the canonical active season."""

    return int(default_player_stats_season(now) - 1)


def _player_stats_cache_ttl(season: int, now: time.struct_time | None = None) -> int:
    current = now or time.localtime()
    active = default_player_stats_season(current)
    season_i = int(season)
    if season_i < active:
        return PRIOR_PLAYER_STATS_CACHE_TTL_SECONDS
    # Active season: short TTL once the NFL regular season calendar starts.
    active_regular_season = season_i == int(current.tm_year) and current.tm_mon >= 9
    return PLAYER_STATS_CACHE_TTL_SECONDS if active_regular_season else COMPLETED_PLAYER_STATS_CACHE_TTL_SECONDS


def _extract_week_observation(week: int, raw_stats: Dict[str, Any]) -> Dict[str, Any] | None:
    """Compact week row from a Sleeper weekly payload. None when empty/unusable raw."""

    if not isinstance(raw_stats, dict):
        return None
    row: Dict[str, Any] = {"week": int(week)}
    saw_value = False
    for source_field in WEEKLY_RETAIN_SOURCE_FIELDS:
        if source_field not in raw_stats or raw_stats.get(source_field) is None:
            continue
        try:
            numeric = float(raw_stats.get(source_field))
        except (TypeError, ValueError):
            continue
        if not (numeric == numeric):  # NaN
            continue
        saw_value = True
        if source_field == "off_snp":
            row["_offensive_snaps"] = numeric
            continue
        if source_field == "tm_off_snp":
            row["_team_offensive_snaps"] = numeric
            continue
        target = WEEKLY_RETAIN_FIELD_MAP.get(source_field)
        if target:
            if target == "games_played":
                row[target] = int(round(numeric))
            else:
                row[target] = float(numeric) if target not in {"games_played"} else int(round(numeric))
                if target in {"targets", "receptions", "rush_attempts", "pass_attempts"}:
                    row[target] = int(round(numeric))
    if not saw_value:
        return None
    for source_field, target in WEEKLY_BOX_SCORE_FIELD_MAP.items():
        if source_field not in raw_stats or raw_stats.get(source_field) is None:
            continue
        try:
            numeric = float(raw_stats.get(source_field))
        except (TypeError, ValueError):
            continue
        if not (numeric == numeric):  # NaN
            continue
        row[target] = float(numeric) if target in WEEKLY_BOX_SCORE_FLOAT_FIELDS else int(round(numeric))
    for source_field, target in WEEKLY_IDP_FIELD_MAP.items():
        if source_field not in raw_stats or raw_stats.get(source_field) is None:
            continue
        try:
            numeric = float(raw_stats.get(source_field))
        except (TypeError, ValueError):
            continue
        if numeric == numeric:
            row[target] = numeric
    try:
        def_snp = float(raw_stats.get("def_snp")) if raw_stats.get("def_snp") is not None else None
        tm_def = float(raw_stats.get("tm_def_snp")) if raw_stats.get("tm_def_snp") is not None else None
    except (TypeError, ValueError):
        def_snp = tm_def = None
    if def_snp is not None and def_snp == def_snp and def_snp >= 0:
        row["defensive_snaps"] = int(round(def_snp))
        if tm_def is not None and tm_def == tm_def and tm_def > 0:
            row["team_defensive_snaps"] = int(round(tm_def))
            row["def_snap_share"] = min(1.0, max(0.0, def_snp / tm_def))
    off_snp = float(row.pop("_offensive_snaps", 0.0) or 0.0)
    tm_off = float(row.pop("_team_offensive_snaps", 0.0) or 0.0)
    if off_snp >= 0 and tm_off > 0:
        row["snap_share"] = min(1.0, max(0.0, off_snp / tm_off))
    # Drop internal-only keys if snaps missing
    row.pop("_offensive_snaps", None)
    row.pop("_team_offensive_snaps", None)
    # A played game with no points key scored a real 0 (see week_row_played).
    _fill_played_zero_points(row, include_box_score_points=True)
    return row if len(row) > 1 else None


def _aggregate_player_week_stats(
    weekly_payloads: List[Any],
    season: int,
    *,
    retain_weekly: bool = True,
) -> Dict[str, Dict[str, Any]]:
    """Aggregate week payloads into season totals; optionally retain compact weekly rows.

    ``weekly_payloads`` may be a list of week dicts (legacy) or (week_number, dict) pairs.
    Weekly granularity is retained from the same fetch — no extra provider calls.
    """

    aggregate: Dict[str, Dict[str, Any]] = {}
    observed_fields: Dict[str, set[str]] = {}
    weekly_rows: Dict[str, List[Dict[str, Any]]] = {}

    for index, item in enumerate(weekly_payloads):
        if isinstance(item, tuple) and len(item) == 2:
            week_number, payload = int(item[0]), item[1]
        elif isinstance(item, dict):
            week_number, payload = index + 1, item
        else:
            continue
        if not isinstance(payload, dict):
            continue
        for player_id, raw_stats in payload.items():
            if not isinstance(raw_stats, dict):
                continue
            player_key = str(player_id)
            totals = aggregate.setdefault(player_key, {"stats_season": int(season)})
            seen = observed_fields.setdefault(player_key, set())
            for source_field, target_field in PLAYER_STATS_SUM_FIELDS.items():
                if source_field not in raw_stats or raw_stats.get(source_field) is None:
                    continue
                try:
                    numeric = float(raw_stats.get(source_field))
                except (TypeError, ValueError):
                    continue
                totals[target_field] = float(totals.get(target_field, 0.0)) + numeric
                seen.add(target_field)

            if retain_weekly:
                week_row = _extract_week_observation(week_number, raw_stats)
                if week_row is not None:
                    weekly_rows.setdefault(player_key, []).append(week_row)

    cleaned: Dict[str, Dict[str, Any]] = {}
    integer_fields = {
        "games_played",
        "targets",
        "receptions",
        "receiving_tds",
        "rush_attempts",
        "rushing_tds",
        "pass_attempts",
        "passing_tds",
    }
    for player_id, totals in aggregate.items():
        fields_seen = observed_fields.get(player_id, set())
        result: Dict[str, Any] = {"stats_season": int(season)}
        for field_name in fields_seen:
            value = totals.get(field_name)
            if field_name.startswith("_"):
                continue
            result[field_name] = int(round(value)) if field_name in integer_fields else float(value)

        offensive_snaps = float(totals.get("_offensive_snaps", 0.0))
        team_offensive_snaps = float(totals.get("_team_offensive_snaps", 0.0))
        if offensive_snaps >= 0 and team_offensive_snaps > 0:
            result["snap_share"] = min(1.0, max(0.0, offensive_snaps / team_offensive_snaps))

        games_played = result.get("games_played")
        fantasy_points_ppr = result.get("fantasy_points_ppr")
        if games_played and fantasy_points_ppr is None:
            # Sleeper drops zero-valued stat keys, so a player whose every
            # played game scored exactly 0 PPR has no pts_ppr at all. That is
            # a real 0.0, not an unknown: without it ppg stayed null for rows
            # that clearly have games played.
            fantasy_points_ppr = 0.0
            result["fantasy_points_ppr"] = 0.0
        if games_played and fantasy_points_ppr is not None:
            result["ppg"] = float(fantasy_points_ppr) / float(games_played)

        if retain_weekly:
            weeks = weekly_rows.get(player_id) or []
            if weeks:
                # Stable week order; drop empty-only noise later in recency filter.
                result["weekly"] = sorted(weeks, key=lambda row: int(row.get("week") or 0))

        if len(result) > 1:
            cleaned[player_id] = result
    return cleaned


def season_stats_cache_has_weekly(season: int | None = None) -> bool:
    """True when the season aggregate cache retains at least one weekly series."""

    selected = int(season or default_player_stats_season())
    cache_path = PLAYER_STATS_CACHE_TEMPLATE.format(season=selected)
    if not os.path.exists(cache_path):
        return False
    try:
        with open(cache_path, "r", encoding="utf-8") as handle:
            cached = json.load(handle)
        if not isinstance(cached, dict):
            return False
        for values in cached.values():
            if isinstance(values, dict) and isinstance(values.get("weekly"), list) and values.get("weekly"):
                return True
    except Exception:
        return False
    return False


def season_stats_cache_has_box_scores(cached: Dict[str, Any] | None) -> bool:
    """True when a loaded season aggregate (``get_season_player_stats``'s
    return value) has per-week box-score fields on its weekly rows, i.e. it
    was built after ``WEEKLY_BOX_SCORE_FIELD_MAP`` retention shipped. A
    cache written before that (e.g. the committed prior-season files under
    ``data/``) has weekly rows but no box-score keys. Callers must report
    that as unavailable rather than reading the absent keys as zeros.
    """

    if not isinstance(cached, dict):
        return False
    for values in cached.values():
        weekly = values.get("weekly") if isinstance(values, dict) else None
        if not isinstance(weekly, list):
            continue
        for row in weekly:
            if isinstance(row, dict) and WEEKLY_BOX_SCORE_SCHEMA_MARKER_FIELD in row:
                return True
    return False


def season_stats_cache_has_idp(cached: Dict[str, Any] | None) -> bool:
    """True when a loaded season aggregate has per-week defensive snap/IDP
    fields on its weekly rows (written after IDP retention shipped). Older
    caches have defenders' rows but no ``idp_*`` keys; callers must report IDP
    stats as unavailable for them rather than reading absence as zeros."""

    if not isinstance(cached, dict):
        return False
    for values in cached.values():
        weekly = values.get("weekly") if isinstance(values, dict) else None
        if not isinstance(weekly, list):
            continue
        for row in weekly:
            if isinstance(row, dict) and WEEKLY_IDP_SCHEMA_MARKER_FIELD in row:
                return True
    return False


_idp_rebuild_attempted: set[int] = set()


def ensure_season_idp_stats(season: int | None = None) -> Dict[str, Dict[str, Any]]:
    """Season aggregate guaranteed to carry IDP weekly fields where Sleeper has them.

    A cache written before IDP retention has defenders' rows without ``idp_*``
    keys, and a prior-season cache would stay that way for its whole 180-day
    TTL. Only IDP surfaces call this (offense-only paths keep using
    ``get_season_player_stats`` untouched): it rebuilds such a cache once per
    process from the same week endpoints, and never replaces it with a rebuild
    that fetched fewer weeks than the cache already holds.
    """

    selected = int(season or default_player_stats_season())
    cached = get_season_player_stats(selected, retain_weekly=True)
    if season_stats_cache_has_idp(cached) or selected in _idp_rebuild_attempted:
        return cached
    _idp_rebuild_attempted.add(selected)
    prior_weeks = {
        int(row.get("week") or 0)
        for values in cached.values()
        if isinstance(values, dict)
        for row in (values.get("weekly") or [])
        if isinstance(row, dict)
    }
    cache_path = PLAYER_STATS_CACHE_TEMPLATE.format(season=selected)
    weekly_payloads: List[Any] = []
    for week in range(1, 19):
        try:
            payload = _request_json("sleeper_player_stats_week", f"{SLEEPER_BASE}/stats/nfl/regular/{selected}/{week}", timeout=20)
        except Exception:
            continue
        if isinstance(payload, dict):
            weekly_payloads.append((week, payload))
    if not weekly_payloads or len(weekly_payloads) < len(prior_weeks):
        return cached
    rebuilt = _aggregate_player_week_stats(weekly_payloads, selected, retain_weekly=True)
    try:
        with open(cache_path, "w", encoding="utf-8") as handle:
            json.dump(rebuilt, handle)
    except Exception:
        return cached
    return get_season_player_stats(selected, retain_weekly=True)


def season_stats_cache_written_at(season: int | None = None) -> float | None:
    """Epoch mtime of this season's on-disk aggregate cache (when its Sleeper
    weekly payloads were last fetched), or None when there is no cache file.
    Never fetches."""

    selected = int(season or default_player_stats_season())
    cache_path = PLAYER_STATS_CACHE_TEMPLATE.format(season=selected)
    try:
        return float(os.path.getmtime(cache_path))
    except OSError:
        return None


def cached_season_player_weekly(player_id: str, season: int | None = None) -> List[Dict[str, Any]]:
    """Weekly rows already on disk for one player+season — never fetches.

    The read side of ``get_season_player_stats``'s ``retain_weekly`` output,
    for callers that must not block a render on an 18-week rebuild. Empty
    list whenever the cache is missing, unreadable, or was written without
    weekly retention (e.g. an old cache file written before prior seasons
    retained weekly rows, or an explicit ``retain_weekly=False`` rebuild).
    """

    identifier = str(player_id or "").strip()
    if not identifier:
        return []
    selected = int(season or default_player_stats_season())
    cache_path = PLAYER_STATS_CACHE_TEMPLATE.format(season=selected)
    if not os.path.exists(cache_path):
        return []
    try:
        with open(cache_path, "r", encoding="utf-8") as handle:
            cached = json.load(handle)
    except Exception:
        return []
    if not isinstance(cached, dict):
        return []
    record = cached.get(identifier)
    weekly = record.get("weekly") if isinstance(record, dict) else None
    if not isinstance(weekly, list):
        return []
    include_box = season_stats_cache_has_box_scores(cached)
    rows = [row for row in weekly if isinstance(row, dict)]
    for row in rows:
        _fill_played_zero_points(row, include_box_score_points=include_box)
    return rows


def get_season_player_stats(
    season: int | None = None,
    *,
    refresh: bool = False,
    max_week: int = 18,
    retain_weekly: bool | None = None,
) -> Dict[str, Dict[str, Any]]:
    """Load cached Sleeper weekly production and aggregate it into season totals.

    When rebuilding from the network, weekly observations are retained on each
    player record under ``weekly`` (same provider calls as before, no extra
    fetches) — including prior-season rebuilds. The self-hosted deployment has
    abundant local disk, so there is no longer a storage-size reason to evict
    prior-season weekly granularity; each season's aggregate (with its weekly
    rows) is cached on disk at ``PLAYER_STATS_CACHE_TEMPLATE`` and only the
    requested season is read into memory per call, so retaining history here
    does not grow process memory over time.
    """
    _ensure_data_dir()
    selected_season = int(season or default_player_stats_season())
    cache_path = PLAYER_STATS_CACHE_TEMPLATE.format(season=selected_season)
    keep_weekly = bool(retain_weekly) if retain_weekly is not None else True

    if not refresh and os.path.exists(cache_path):
        try:
            cache_age = time.time() - os.path.getmtime(cache_path)
            if cache_age < _player_stats_cache_ttl(selected_season):
                try:
                    mtime_ns = os.stat(cache_path).st_mtime_ns
                except Exception:
                    mtime_ns = -1
                if mtime_ns != -1:
                    with _season_stats_memo_lock:
                        memoized = _season_stats_memo.get(cache_path)
                        memo_fresh = _season_stats_memo_mtime_ns.get(cache_path) == mtime_ns
                        memo_has_weekly = _season_stats_memo_has_weekly.get(cache_path, False)
                    if memoized is not None and memo_fresh and (not keep_weekly or memo_has_weekly):
                        return memoized
                with open(cache_path, "r", encoding="utf-8") as handle:
                    cached = json.load(handle)
                if isinstance(cached, dict):
                    backfill_played_zero_points(cached)
                    has_weekly = any(
                        isinstance(values, dict)
                        and isinstance(values.get("weekly"), list)
                        and bool(values.get("weekly"))
                        for values in cached.values()
                    )
                    # Active season without weekly rows → rebuild once using the
                    # same week endpoints (no additional call volume vs a normal refresh).
                    if keep_weekly and not has_weekly:
                        pass
                    else:
                        if mtime_ns != -1:
                            with _season_stats_memo_lock:
                                _season_stats_memo[cache_path] = cached
                                _season_stats_memo_mtime_ns[cache_path] = mtime_ns
                                _season_stats_memo_has_weekly[cache_path] = has_weekly
                        return cached
        except Exception:
            pass

    weekly_payloads: List[Any] = []
    for week in range(1, max(1, int(max_week)) + 1):
        url = f"{SLEEPER_BASE}/stats/nfl/regular/{selected_season}/{week}"
        try:
            payload = _request_json("sleeper_player_stats_week", url, timeout=20)
            if isinstance(payload, dict):
                weekly_payloads.append((week, payload))
        except Exception:
            continue

    if weekly_payloads:
        aggregated = _aggregate_player_week_stats(
            weekly_payloads,
            selected_season,
            retain_weekly=keep_weekly,
        )
        try:
            with open(cache_path, "w", encoding="utf-8") as handle:
                json.dump(aggregated, handle)
            fresh_mtime_ns = os.stat(cache_path).st_mtime_ns
            with _season_stats_memo_lock:
                _season_stats_memo[cache_path] = aggregated
                _season_stats_memo_mtime_ns[cache_path] = fresh_mtime_ns
                _season_stats_memo_has_weekly[cache_path] = keep_weekly
        except Exception:
            pass
        return aggregated

    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as handle:
                cached = json.load(handle)
            if isinstance(cached, dict):
                return backfill_played_zero_points(cached)
        except Exception:
            pass
    return {}


def get_prior_season_player_stats(
    *,
    refresh: bool = False,
    max_week: int = 18,
) -> Dict[str, Dict[str, Any]]:
    """Load the prior NFL season aggregate via the same Sleeper week→cache path.

    Fail-neutral: returns {} when the prior season cannot be loaded. Never invents
    player rows. Uses the longer prior-season TTL once cached. Weekly rows are
    retained on disk here too (self-hosted storage is abundant; see
    ``get_season_player_stats``'s docstring) — callers that only want season
    aggregates can simply ignore the ``weekly`` key on each record.
    """

    try:
        return get_season_player_stats(
            season=prior_player_stats_season(),
            refresh=refresh,
            max_week=max_week,
            retain_weekly=True,
        )
    except Exception:
        return {}


def prior_season_stats_cache_available(now: time.struct_time | None = None) -> bool:
    """True when a non-empty prior-season aggregate file is already on disk."""

    cache_path = PLAYER_STATS_CACHE_TEMPLATE.format(season=prior_player_stats_season(now))
    if not os.path.exists(cache_path):
        return False
    try:
        with open(cache_path, "r", encoding="utf-8") as handle:
            cached = json.load(handle)
        return isinstance(cached, dict) and bool(cached)
    except Exception:
        return False


def normalize_username(username: str) -> str:
    return (username or "").strip().casefold()


def _ensure_data_dir():
    # exist_ok: several worker processes can get here at the same moment.
    os.makedirs("data", exist_ok=True)


def _provider_category(label: str) -> str:
    text = str(label or "").casefold()
    if "user_lookup" in text or text.endswith("_user"):
        return "provider_user_lookup"
    if "league_users" in text or text.endswith("_users"):
        return "provider_users"
    if "rosters" in text:
        return "provider_rosters"
    if "transactions" in text:
        return "provider_transactions"
    if "players" in text:
        return "provider_players"
    if "league" in text or "draft" in text or "matchup" in text or "traded" in text:
        return "provider_leagues"
    return "provider_other"


def _note_provider_timing(
    label: str,
    duration_ms: float,
    *,
    cache_status: str = "miss",
    timeout: bool = False,
) -> None:
    """Provider-timing hook (intentional no-op).

    These diagnostics were recorded into a per-browser-session store that only
    existed in the retired Streamlit app; the API services have no such
    session, so nothing is recorded. Call sites are kept so provider
    timing can be re-attached to a request-scoped sink later.
    """

    return None


def _safe_provider_endpoint(label: str) -> str:
    """Stable non-PII endpoint label for duplicate-call diagnosis."""

    text = str(label or "").strip().casefold()
    cleaned = "".join(ch if ch.isalnum() or ch in "._:-" else "_" for ch in text)
    return cleaned[:48]


# Retry only genuinely transient conditions: network errors, timeouts, and
# 5xx/429 responses from Sleeper. A real 4xx (bad request, not found, ...)
# means the request itself is wrong and retrying it would just waste time
# and hammer Sleeper for no benefit, so those still fail fast exactly like
# before. Small retry budget + short backoff: enough to ride out a blip
# without turning one flaky call into a multi-second pileup for the
# request/thread that's waiting on it.
SLEEPER_REQUEST_MAX_RETRIES = int(os.environ.get("SLEEPER_REQUEST_MAX_RETRIES", "2"))
SLEEPER_REQUEST_RETRY_BACKOFF_SECONDS = float(
    os.environ.get("SLEEPER_REQUEST_RETRY_BACKOFF_SECONDS", "0.25")
)
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def _request_json(label: str, url: str, *, timeout: int = 5, max_retries: int | None = None):
    """GET ``url`` as JSON, retrying transient failures with backoff.

    Return contract unchanged from before this fix: ``None`` on any failure
    (bad status, exhausted retries, network error) — never raises for a
    request-level failure. Callers that already wrap this in
    ``try/except Exception`` keep working unmodified; the only behavior
    change is that a Timeout, which used to propagate immediately, is now
    retried first and then also converges to ``None`` like every other
    failure mode, rather than being a special case.
    """

    retries = SLEEPER_REQUEST_MAX_RETRIES if max_retries is None else max_retries
    started = time.perf_counter()
    timed_out = False
    cache_status = "miss"
    attempt = 0

    # Over the soft call-rate threshold: pausable work (warm-ups, background
    # refresh, free-tier requests) serves the last real payload instead of
    # spending budget; background work with nothing cached just skips.
    if sleeper_budget.should_defer():
        known = sleeper_budget.last_known(url)
        sleeper_budget.note_deferred()
        if known is not None:
            sleeper_budget.note_stale_served(url, known[1])
            _note_provider_timing(label, 0.0, cache_status="stale_deferred")
            return known[0]
        if sleeper_budget.should_skip_outright():
            _note_provider_timing(label, 0.0, cache_status="skipped_budget")
            return None

    def _last_known_or_none():
        known = sleeper_budget.last_known(url)
        if known is None:
            return None
        sleeper_budget.note_stale_served(url, known[1])
        return known[0]

    try:
        while True:
            timed_out = False
            try:
                sleeper_budget.record_call()
                with performance.time_block(label, category="sleeper"):
                    response = requests.get(url, timeout=timeout)
            except requests.Timeout:
                timed_out = True
                if attempt < retries:
                    attempt += 1
                    time.sleep(SLEEPER_REQUEST_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1)))
                    continue
                cache_status = "timeout"
                return _last_known_or_none()
            except requests.RequestException:
                # Network-level failure (connection error, etc.) — same
                # transient treatment as a timeout.
                if attempt < retries:
                    attempt += 1
                    time.sleep(SLEEPER_REQUEST_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1)))
                    continue
                cache_status = "error"
                return _last_known_or_none()

            if response.status_code == 200:
                payload = response.json()
                sleeper_budget.remember(url, payload)
                return payload
            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < retries:
                attempt += 1
                time.sleep(SLEEPER_REQUEST_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1)))
                continue
            # Exhausted 429/5xx: serve the last real payload (with its
            # fetch time) when we have one. A genuine 4xx fails fast.
            if response.status_code in _RETRYABLE_STATUS_CODES:
                cache_status = "rate_limited" if response.status_code == 429 else "error"
                return _last_known_or_none()
            return None
    finally:
        _note_provider_timing(
            label,
            (time.perf_counter() - started) * 1000.0,
            cache_status=cache_status,
            timeout=timed_out,
        )


def players_map_is_valid(data: Any) -> bool:
    """True when ``data`` looks like Sleeper's id -> player-record map.

    Guards the on-disk dump against being overwritten (or committed) with an
    unrelated JSON object, e.g. a test fixture such as
    ``{"id": "user-123", "email": ...}`` whose values are strings. Every
    consumer indexes ``players[pid].get(...)``, so a non-dict value anywhere
    is fatal downstream.
    """

    if not isinstance(data, dict) or not data:
        return False
    return all(isinstance(value, dict) for value in data.values())


def load_cached_players_disk(
    path: str | None = None,
) -> tuple[Dict[str, Any], int]:
    """Read ``sleeper_players.json`` only. Never fetches.

    Returns ``(players_by_id, mtime_ns)``. Missing or unreadable cache yields
    ``({}, 0)``. Used by structured football freshness so startup can patch
    status/injury/depth without calling ``get_players(refresh=...)``.
    """

    cache_path = path or PLAYERS_CACHE_PATH
    if not os.path.exists(cache_path):
        return {}, 0
    try:
        stat = os.stat(cache_path)
        mtime_ns = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)))
        with open(cache_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if players_map_is_valid(data):
            _note_provider_timing("sleeper_players_disk_only", 0.0, cache_status="hit")
            return data, mtime_ns
    except Exception:
        return {}, 0
    return {}, 0


#   Every real request-latency caller of get_players() only ever reads the
#   returned dict (indexes into it / iterates .items()) — never mutates a
#   player entry in place — so sharing the same in-process object across
#   calls/requests is safe; see the self-hosted perf audit that added this.
_players_memo_lock = threading.Lock()
_players_memo: Optional[Dict[str, Any]] = None
_players_memo_mtime_ns: int = -1

# get_season_player_stats()'s disk cache (~2.3MB/season in production) had the
# same gap get_players() used to have above: a fresh-within-TTL cache hit
# still did a full open()+json.load() on *every* call, with no in-process
# memoization. Measured ~20ms of synchronous disk I/O + JSON decode per call
# (python3 -c timing against the real on-disk cache file). Several hot mobile
# endpoints call this once per request (Matchup, Player Detail weekly-stats/
# schedule/external-projections, Waivers' defense-strength lookup, Rankings),
# so this was real repeated work for identical data within a cache file's TTL
# window, same class of bug as the get_players() fix above. Keyed by
# cache_path (which already encodes season) and its mtime, same invalidation
# contract as the memo above: a real cache-file rewrite (refresh=True, or the
# TTL lapsing and triggering a rebuild) naturally busts it.
_season_stats_memo_lock = threading.Lock()
_season_stats_memo: Dict[str, Dict[str, Any]] = {}
_season_stats_memo_mtime_ns: Dict[str, int] = {}
_season_stats_memo_has_weekly: Dict[str, bool] = {}


# Cross-process single flight for the ~16MB players dump: every mobile-API
# worker and the players.db rebuild subprocess share one
# data/sleeper_players.json, so refreshes take an flock on a sibling
# ``<cache>.lock`` (modules.file_lock). Without flock (Windows dev) the
# atomic replace below still keeps readers safe; only the dedupe is lost.

# How long a synchronous caller (missing cache file, or refresh=True) waits
# for another process's in-flight download before fetching itself. Covers the
# 20s request timeout plus parse/write time.
PLAYERS_REFRESH_LOCK_WAIT_SECONDS = 30.0
# After a failed background download, don't re-attempt on every request.
PLAYERS_BACKGROUND_REFRESH_FAILURE_COOLDOWN_SECONDS = 30.0
# Long-lived servers opt in (services/mobile_api_service.py): an aged cache is
# then served as-is while one background thread re-downloads it, so a request
# never waits on Sleeper for this. Off by default because one-shot scripts
# (e.g. scripts/sync_injury_status.py) exit before a daemon thread finishes
# and so must keep the synchronous refresh-on-stale behavior.
PLAYERS_BACKGROUND_REFRESH = False

_players_bg_guard = threading.Lock()
_players_bg_in_flight = False
_players_bg_last_failure_mono = 0.0


def _players_refresh_lock(*, wait_seconds: float) -> ExclusiveFileLock:
    return ExclusiveFileLock(f"{PLAYERS_CACHE_PATH}.lock", wait_seconds=wait_seconds)


def _players_cache_mtime_ns() -> int:
    try:
        return int(os.stat(PLAYERS_CACHE_PATH).st_mtime_ns)
    except OSError:
        return -1


def _players_validation_path(cache_path: str | None = None) -> str:
    return f"{cache_path or PLAYERS_CACHE_PATH}.validation.json"


def _read_players_validation(cache_path: str | None = None) -> Dict[str, Any]:
    try:
        with open(_players_validation_path(cache_path), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_players_validation(etag: str, *, cache_path: str | None = None) -> None:
    """Record the dump's ETag together with the exact file it describes.

    The file's own mtime must not move when Sleeper confirms nothing changed
    (it is part of the public-player cache fingerprint, so touching it would
    rebuild every derived frame for identical data). This sidecar's mtime is
    the "last confirmed current" time instead.
    """

    target = cache_path or PLAYERS_CACHE_PATH
    try:
        stat = os.stat(target)
    except OSError:
        return
    path = _players_validation_path(target)
    tmp_path = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(
                {"etag": etag, "size": int(stat.st_size), "mtime_ns": int(stat.st_mtime_ns)},
                handle,
            )
        os.replace(tmp_path, path)
    except OSError:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def players_cache_validated_at(cache_path: str | None = None) -> float:
    """Newest of: the dump's mtime, or a later conditional-GET confirmation
    (HTTP 304) that the dump is still what Sleeper serves. 0.0 when missing."""

    target = cache_path or PLAYERS_CACHE_PATH
    try:
        stat = os.stat(target)
    except OSError:
        return 0.0
    validated = float(stat.st_mtime)
    info = _read_players_validation(target)
    if info.get("size") == int(stat.st_size) and info.get("mtime_ns") == int(stat.st_mtime_ns):
        try:
            validated = max(validated, float(os.path.getmtime(_players_validation_path(target))))
        except OSError:
            pass
    return validated


def _players_cache_is_fresh() -> bool:
    validated_at = players_cache_validated_at()
    if validated_at <= 0:
        return False
    return (time.time() - validated_at) < PLAYERS_CACHE_TTL_SECONDS


def _read_players_cache_file(*, label: str) -> Optional[Dict[str, Any]]:
    """Memo-aware read of the on-disk dump; None when missing/unreadable."""

    global _players_memo, _players_memo_mtime_ns
    mtime_ns = _players_cache_mtime_ns()
    if mtime_ns == -1:
        return None
    with _players_memo_lock:
        if _players_memo is not None and mtime_ns == _players_memo_mtime_ns:
            _note_provider_timing("sleeper_players_memo", 0.0, cache_status="hit")
            return _players_memo
    try:
        with open(PLAYERS_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    if not players_map_is_valid(data):
        return None
    _note_provider_timing(label, 0.0, cache_status="hit")
    with _players_memo_lock:
        _players_memo = data
        _players_memo_mtime_ns = mtime_ns
    return data


def _write_players_cache_atomically(players: Dict[str, Any]) -> None:
    """Write to a sibling temp file, then ``os.replace`` it into place.

    The old in-place ``open(path, "w")`` truncated the live file first, so a
    concurrent reader (another worker, or the players.db rebuild) could parse
    an empty or half-written dump. ``os.replace`` is atomic on POSIX and
    Windows: readers see either the old file or the complete new one.
    """

    global _players_memo, _players_memo_mtime_ns
    directory = os.path.dirname(os.path.abspath(PLAYERS_CACHE_PATH))
    tmp_path = os.path.join(
        directory,
        f".{os.path.basename(PLAYERS_CACHE_PATH)}.{os.getpid()}.{threading.get_ident()}.tmp",
    )
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(players, f)
        os.replace(tmp_path, PLAYERS_CACHE_PATH)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    fresh_mtime_ns = _players_cache_mtime_ns()
    with _players_memo_lock:
        _players_memo = players
        _players_memo_mtime_ns = fresh_mtime_ns


def _download_players() -> Dict[str, Any]:
    """Fetch the dump and persist it atomically. Raises on fetch failure."""

    url = f"{SLEEPER_BASE}/players/nfl"
    started = time.perf_counter()
    # Conditional GET: when the on-disk dump is exactly the one this ETag
    # described, Sleeper answers 304 with no body, so nothing is downloaded,
    # parsed, rewritten or re-derived. The dump is no staler than a full
    # download would have been: the server just confirmed it is current.
    headers: Dict[str, str] = {}
    info = _read_players_validation()
    if info.get("etag"):
        try:
            stat = os.stat(PLAYERS_CACHE_PATH)
        except OSError:
            stat = None
        if (
            stat is not None
            and info.get("size") == int(stat.st_size)
            and info.get("mtime_ns") == int(stat.st_mtime_ns)
        ):
            headers["If-None-Match"] = str(info["etag"])
    try:
        sleeper_budget.record_call()
        with performance.time_block("sleeper_players_fetch", category="sleeper"):
            resp = (
                requests.get(url, timeout=20, headers=headers)
                if headers
                else requests.get(url, timeout=20)
            )
            if headers and getattr(resp, "status_code", None) == 304:
                current = _read_players_cache_file(label="sleeper_players_disk")
                if current is not None:
                    _write_players_validation(headers["If-None-Match"])
                    _note_provider_timing(
                        "sleeper_players_fetch",
                        (time.perf_counter() - started) * 1000.0,
                        cache_status="not_modified",
                    )
                    return current
                resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            players = resp.json()
    except Exception:
        _note_provider_timing(
            "sleeper_players_fetch",
            (time.perf_counter() - started) * 1000.0,
            cache_status="error",
        )
        raise
    if not players_map_is_valid(players):
        # Never replace a good dump with an empty/garbage one; callers fall
        # back to the existing file (or {} when there is none, as before).
        _note_provider_timing(
            "sleeper_players_fetch",
            (time.perf_counter() - started) * 1000.0,
            cache_status="error",
        )
        raise ValueError("Sleeper players dump was empty or not an id -> player-record map")
    try:
        _write_players_cache_atomically(players)
        etag = ""
        try:
            raw_etag = resp.headers.get("ETag")
            etag = raw_etag if isinstance(raw_etag, str) else ""
        except Exception:
            etag = ""
        if etag:
            _write_players_validation(etag)
    except Exception:
        pass
    _note_provider_timing(
        "sleeper_players_fetch",
        (time.perf_counter() - started) * 1000.0,
        cache_status="miss",
    )
    return players


def _refresh_players_blocking() -> Dict[str, Any]:
    """Synchronous single-flight refresh (missing cache or ``refresh=True``).

    Waits for another process's in-flight download instead of starting a
    second one; if that download replaced the file while we waited, its
    result is used (it is newer than this call). Waiting past
    ``PLAYERS_REFRESH_LOCK_WAIT_SECONDS`` fails open to fetching directly.
    """

    observed_mtime_ns = _players_cache_mtime_ns()
    try:
        with _players_refresh_lock(wait_seconds=PLAYERS_REFRESH_LOCK_WAIT_SECONDS):
            current_mtime_ns = _players_cache_mtime_ns()
            if current_mtime_ns != -1 and current_mtime_ns != observed_mtime_ns:
                fresh = _read_players_cache_file(label="sleeper_players_disk")
                if fresh is not None:
                    return fresh
            return _download_players()
    except Exception:
        fallback = _read_players_cache_file(label="sleeper_players_disk")
        return fallback if fallback is not None else {}


def _background_players_refresh_worker() -> None:
    global _players_bg_in_flight, _players_bg_last_failure_mono
    failed = False
    try:
        with sleeper_budget.low_priority():
            if sleeper_budget.should_skip_outright():
                # Over the soft call-rate threshold: the dump is only a
                # background refresh; the on-disk copy keeps serving.
                sleeper_budget.note_deferred()
                return
            with _players_refresh_lock(wait_seconds=0.0) as lock:
                # Lock held elsewhere: that process is already downloading
                # and will replace the file, so this one has nothing to do.
                if lock.acquired and not _players_cache_is_fresh():
                    _download_players()
    except Exception:
        failed = True
    finally:
        with _players_bg_guard:
            _players_bg_in_flight = False
            if failed:
                _players_bg_last_failure_mono = time.monotonic()


def _schedule_background_players_refresh() -> bool:
    """Start at most one background download per process; never blocks."""

    global _players_bg_in_flight
    with _players_bg_guard:
        if _players_bg_in_flight:
            return False
        if (
            _players_bg_last_failure_mono
            and time.monotonic() - _players_bg_last_failure_mono
            < PLAYERS_BACKGROUND_REFRESH_FAILURE_COOLDOWN_SECONDS
        ):
            return False
        _players_bg_in_flight = True
    try:
        threading.Thread(
            target=_background_players_refresh_worker,
            name="dgm-sleeper-players-refresh",
            daemon=True,
        ).start()
    except Exception:
        with _players_bg_guard:
            _players_bg_in_flight = False
        return False
    return True


def get_players(refresh: bool = False) -> Dict[str, Any]:
    """
    Fetch all NFL players from Sleeper, with basic local caching.
    Returns dict keyed by player_id -> player_object.[web:4]

    On a disk-cache hit (the common case — ``PLAYERS_CACHE_TTL_SECONDS`` is
    5 minutes and nothing proactively evicts between refreshes), this used
    to re-``json.load()`` the on-disk cache file (currently ~16MB) on
    *every single call* — no in-process memoization at all, despite several
    hot mobile-API endpoints (``/v1/players``, matchup, my-team, schedule)
    calling this once or more per request. Measured ~95ms of synchronous
    disk I/O + JSON decode per call. This process-wide memo, keyed by the
    cache file's mtime, cuts that to one parse per actual file change
    (write from a real refresh) instead of one parse per call — a real
    request can still call this multiple times (e.g. the matchup endpoint
    calls it twice) and now pays for the parse at most once per process
    between refreshes.

    Refreshes are atomic (temp file + ``os.replace``) and single-flight
    across processes (flock on ``<cache>.lock``). With
    ``PLAYERS_BACKGROUND_REFRESH`` on, an aged cache is returned immediately
    and one background thread re-downloads it.
    """
    _ensure_data_dir()

    if not refresh and os.path.exists(PLAYERS_CACHE_PATH):
        fresh = _players_cache_is_fresh()
        if fresh or PLAYERS_BACKGROUND_REFRESH:
            cached = _read_players_cache_file(label="sleeper_players_disk")
            if cached is not None:
                if not fresh:
                    _schedule_background_players_refresh()
                return cached

    return _refresh_players_blocking()


@lru_cache(maxsize=256)
def get_user_id(username: str) -> Optional[str]:
    """
    Look up a Sleeper user_id from username.[web:4]
    """
    username = (username or "").strip()
    if not username:
        return None

    candidates = []
    for candidate in [username, username.lower(), username.casefold()]:
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    for candidate in candidates:
        url = f"{SLEEPER_BASE}/user/{quote(candidate, safe='')}"
        try:
            data = _request_json("sleeper_user_lookup", url, timeout=5)
            if isinstance(data, dict) and data.get("user_id"):
                return data.get("user_id")
        except Exception:
            continue
    return None


# These three live endpoints change constantly (rosters via trades/waivers/
# drops, users/league settings less often but still live) — a bare
# lru_cache here would cache them for the rest of the process's life,
# refreshed only by clear_live_league_endpoint_caches() below. The web app
# calls that on its own Game Plan TTL/manual-refresh, but services/
# mobile_api_service.py (a separate long-running process) never does —
# without this, a mobile Render instance would serve one stale roster
# snapshot per league for its entire uptime between deploys. The time
# bucket in the cache key makes every entry expire on its own after
# LIVE_LEAGUE_ENDPOINT_TTL_SECONDS regardless of whether anything ever
# calls clear_live_league_endpoint_caches() for this process.
LIVE_LEAGUE_ENDPOINT_TTL_SECONDS = 30


def _live_league_cache_bucket() -> int:
    return int(time.time() // LIVE_LEAGUE_ENDPOINT_TTL_SECONDS)


@lru_cache(maxsize=128)
def _get_users_cached(league_id: str, _bucket: int) -> List[Dict[str, Any]]:
    if not league_id:
        return []
    url = f"{SLEEPER_BASE}/league/{league_id}/users"
    try:
        users = _request_json("sleeper_league_users", url, timeout=5)
        return users if isinstance(users, list) else []
    except Exception:
        return []


def _is_espn_league(league_id: Any) -> bool:
    """ESPN leagues are keyed "espn:{id}:{season}" (modules.espn_leagues).

    The league getters below hand those keys to the ESPN snapshot, which is
    already shaped like Sleeper's payloads, so every engine that reads a
    league through this module runs unchanged on an ESPN roster. The
    Sleeper-only getters (drafts, traded picks, transactions, matchups)
    return empty for an ESPN key instead of sending it to Sleeper's API;
    the API refuses the features that depend on them for ESPN leagues."""

    return isinstance(league_id, str) and league_id.startswith(("espn:", "fleaflicker:", "mfl:"))


def _espn_leagues():
    # Despite the name: the dispatcher for every imported platform (ESPN,
    # Fleaflicker, MFL), see modules.external_leagues.
    from modules import external_leagues

    return external_leagues


def get_users(league_id: str) -> List[Dict[str, Any]]:
    """
    Get all users in a league.[web:4]
    """
    if _is_espn_league(league_id):
        return _espn_leagues().users_payload(league_id)
    return _get_users_cached(league_id, _live_league_cache_bucket())


@lru_cache(maxsize=128)
def _get_rosters_cached(league_id: str, _bucket: int) -> List[Dict[str, Any]]:
    if not league_id:
        return []
    url = f"{SLEEPER_BASE}/league/{league_id}/rosters"
    try:
        rosters = _request_json("sleeper_league_rosters", url, timeout=5)
        return rosters if isinstance(rosters, list) else []
    except Exception:
        return []


def get_rosters(league_id: str) -> List[Dict[str, Any]]:
    """
    Get all rosters in a league.[web:4]
    """
    if _is_espn_league(league_id):
        return _espn_leagues().rosters_payload(league_id)
    return _get_rosters_cached(league_id, _live_league_cache_bucket())


@lru_cache(maxsize=128)
def _get_league_cached(league_id: str, _bucket: int) -> Dict[str, Any]:
    if not league_id:
        return {}
    url = f"{SLEEPER_BASE}/league/{league_id}"
    try:
        league = _request_json("sleeper_league", url, timeout=5)
        return league if isinstance(league, dict) else {}
    except Exception:
        return {}


def get_league(league_id: str) -> Dict[str, Any]:
    """
    Get league metadata/settings from Sleeper.
    """
    if _is_espn_league(league_id):
        return _espn_leagues().league_payload(league_id)
    return _get_league_cached(league_id, _live_league_cache_bucket())


@lru_cache(maxsize=128)
def get_league_drafts(league_id: str) -> List[Dict[str, Any]]:
    """
    Get all draft objects attached to a league.
    """
    if not league_id or _is_espn_league(league_id):
        return []
    url = f"{SLEEPER_BASE}/league/{league_id}/drafts"
    try:
        drafts = _request_json("sleeper_league_drafts", url, timeout=5)
        return drafts if isinstance(drafts, list) else []
    except Exception:
        return []


@lru_cache(maxsize=256)
def get_draft(draft_id: str) -> Dict[str, Any]:
    """
    Get metadata for a Sleeper draft.
    """
    if not draft_id:
        return {}
    url = f"{SLEEPER_BASE}/draft/{draft_id}"
    try:
        draft = _request_json("sleeper_draft", url, timeout=5)
        return draft if isinstance(draft, dict) else {}
    except Exception:
        return {}


@lru_cache(maxsize=256)
def get_draft_picks(draft_id: str) -> List[Dict[str, Any]]:
    """
    Get all picks made in a Sleeper draft.
    """
    if not draft_id:
        return []
    url = f"{SLEEPER_BASE}/draft/{draft_id}/picks"
    try:
        picks = _request_json("sleeper_draft_picks", url, timeout=10)
        return picks if isinstance(picks, list) else []
    except Exception:
        return []


@lru_cache(maxsize=128)
def _get_traded_picks_cached(league_id: str, _bucket: int) -> List[Dict[str, Any]]:
    if not league_id or _is_espn_league(league_id):
        return []
    url = f"{SLEEPER_BASE}/league/{league_id}/traded_picks"
    try:
        picks = _request_json("sleeper_traded_picks", url, timeout=5)
        return picks if isinstance(picks, list) else []
    except Exception:
        return []


def get_traded_picks(league_id: str) -> List[Dict[str, Any]]:
    """
    Get traded draft picks for a league. Untraded picks are not returned by
    Sleeper, so callers should assume original ownership unless listed here.

    Time-bucketed like get_league/get_rosters/get_users above — a trade
    changes pick ownership immediately, and services/mobile_api_service.py's
    long-lived process has no other invalidation hook for it.
    """
    return _get_traded_picks_cached(league_id, _live_league_cache_bucket())


@lru_cache(maxsize=512)
def _get_transactions_cached(league_id: str, round_num: int, _bucket: int) -> List[Dict[str, Any]]:
    if not league_id or round_num is None or _is_espn_league(league_id):
        return []
    try:
        round_num = int(round_num)
    except Exception:
        return []
    if round_num <= 0:
        return []

    url = f"{SLEEPER_BASE}/league/{league_id}/transactions/{round_num}"
    try:
        transactions = _request_json("sleeper_transactions", url, timeout=5)
        return transactions if isinstance(transactions, list) else []
    except Exception:
        return []


def get_transactions(league_id: str, round_num: int) -> List[Dict[str, Any]]:
    """
    Get league transactions for a specific round/week from Sleeper.

    Time-bucketed — waiver claims and adds/drops land on this endpoint in
    real time, and mobile's long-lived process has no other way to see them.
    """
    return _get_transactions_cached(league_id, round_num, _live_league_cache_bucket())


def clear_live_league_endpoint_caches() -> None:
    """Drop in-process LRU for live Sleeper league endpoints.

    Username lookup and the static players dump stay cached. Call on
    recommendation refresh, Game Plan TTL expiry, and tests — never from
    anonymous presentation-only reruns.
    """

    _get_users_cached.cache_clear()
    _get_rosters_cached.cache_clear()
    _get_league_cached.cache_clear()
    get_league_drafts.cache_clear()
    get_draft.cache_clear()
    get_draft_picks.cache_clear()
    _get_traded_picks_cached.cache_clear()
    _get_transactions_cached.cache_clear()
    _get_matchups_cached.cache_clear()


@lru_cache(maxsize=512)
def _get_matchups_cached(league_id: str, round_num: int, _bucket: int) -> List[Dict[str, Any]]:
    if not league_id or round_num is None or _is_espn_league(league_id):
        return []
    try:
        round_num = int(round_num)
    except Exception:
        return []
    if round_num <= 0:
        return []

    url = f"{SLEEPER_BASE}/league/{league_id}/matchups/{round_num}"
    try:
        matchups = _request_json("sleeper_matchups", url, timeout=5)
        return matchups if isinstance(matchups, list) else []
    except Exception:
        return []


def get_matchups(league_id: str, round_num: int) -> List[Dict[str, Any]]:
    """
    Get league matchups for a specific round/week from Sleeper.

    Time-bucketed — scores update live during games, and mobile's long-lived
    process has no other invalidation hook for this endpoint.
    """
    return _get_matchups_cached(league_id, round_num, _live_league_cache_bucket())


def get_user_roster_id(league_id: str, username: str) -> Optional[int]:
    """
    Returns the roster_id for this username in a league, or None if not found.[web:4]
    """
    normalized_username = normalize_username(username)
    if not league_id or not normalized_username:
        return None

    users = get_users(league_id)
    user_id = None
    for u in users or []:
        sleeper_username = normalize_username(u.get("username"))
        display_name = normalize_username(u.get("display_name"))
        if (
            sleeper_username == normalized_username
            or display_name == normalized_username
        ):
            user_id = u.get("user_id")
            break

    if not user_id:
        return None

    rosters = get_rosters(league_id)
    for r in rosters or []:
        if str(r.get("owner_id")) == str(user_id):
            return r.get("roster_id")

    return None


def get_roster_player_ids(league_id: str, roster_id: int) -> List[str]:
    """
    Returns a list of Sleeper player_ids on this roster.
    Never returns None; returns [] on any failure.[web:4]
    """
    if not league_id or roster_id is None:
        return []

    rosters = get_rosters(league_id)
    for r in rosters or []:
        if str(r.get("roster_id")) == str(roster_id):
            players = r.get("players") or []
            if not isinstance(players, list):
                return []
            return [str(pid) for pid in players if pid is not None]

    return []


def get_sleeper_avatar_url(avatar_id: str, thumb: bool = False) -> str:
    avatar_id = (avatar_id or "").strip()
    if not avatar_id:
        return ""
    if avatar_id.startswith("http://") or avatar_id.startswith("https://"):
        return avatar_id
    avatar_path = f"thumbs/{avatar_id}" if thumb else avatar_id
    return f"{SLEEPER_AVATAR_BASE}/{avatar_path}"


def get_league_roster_profiles(league_id: str) -> Dict[str, Dict[str, Any]]:
    """
    Build roster/team identity details once per league.
    """
    if not league_id:
        return {}

    rosters = get_rosters(league_id)
    users = get_users(league_id)
    users_by_id = {
        str(user.get("user_id") or ""): user
        for user in users or []
    }

    profiles: Dict[str, Dict[str, Any]] = {}
    for roster in rosters or []:
        roster_id = str(roster.get("roster_id") or "")
        owner_id = str(roster.get("owner_id") or "")
        user = users_by_id.get(owner_id, {})
        roster_meta = roster.get("metadata") if isinstance(roster.get("metadata"), dict) else {}
        user_meta = user.get("metadata") if isinstance(user.get("metadata"), dict) else {}

        team_name = (
            roster_meta.get("team_name")
            or user_meta.get("team_name")
            or user.get("display_name")
            or user.get("username")
            or f"Team {roster_id}"
        )
        avatar_id = (
            roster_meta.get("avatar")
            or roster_meta.get("team_avatar")
            or user_meta.get("avatar")
            or user.get("avatar")
            or ""
        )
        profiles[roster_id] = {
            "team_name": team_name,
            "owner_name": user.get("display_name") or user.get("username") or "Unknown",
            "username": user.get("username") or "",
            "avatar_id": avatar_id,
            "avatar_url": get_sleeper_avatar_url(avatar_id),
            "roster_id": roster.get("roster_id"),
            "owner_id": owner_id,
        }

    return profiles


def get_roster_profile(league_id: str, roster_id: int) -> Dict[str, Any]:
    """
    Return team identity details for a roster from Sleeper users/rosters data.
    """
    if not league_id or roster_id is None:
        return {}

    profiles = get_league_roster_profiles(league_id)
    return profiles.get(str(roster_id), {})


# Sleeper's trending endpoint (/players/nfl/trending/{add|drop}) is a
# CROSS-LEAGUE, GLOBAL signal — "how many Sleeper rosters across every
# league adopted/dropped this player in the last N hours," not anything
# scoped to one league. It is deliberately a different, global cache from
# the per-league LIVE_LEAGUE_ENDPOINT_TTL_SECONDS bucket above: this data
# has no single league to key on, and global add/drop velocity does not
# need 30s freshness the way a live roster does, so it gets its own, longer
# TTL bucket instead of reusing _live_league_cache_bucket.
TRENDING_ENDPOINT_TTL_SECONDS = 10 * 60


def _trending_cache_bucket() -> int:
    return int(time.time() // TRENDING_ENDPOINT_TTL_SECONDS)


@lru_cache(maxsize=8)
def _get_trending_players_cached(
    trend_type: str, lookback_hours: int, limit: int, _bucket: int
) -> List[Dict[str, Any]]:
    url = (
        f"{SLEEPER_BASE}/players/nfl/trending/{trend_type}"
        f"?lookback_hours={lookback_hours}&limit={limit}"
    )
    try:
        data = _request_json(f"sleeper_trending_{trend_type}", url, timeout=5)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def get_trending_players(
    trend_type: str = "add",
    *,
    lookback_hours: int = 24,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Sleeper's global trending players over the last ``lookback_hours``.

    This is explicitly NOT a league-scoped signal — it's cross-league add/drop
    velocity across the whole Sleeper platform ("how many Sleeper rosters
    everywhere picked this player up"), the same list Sleeper's own waiver
    wire UI surfaces as "Trending". Returns Sleeper's raw
    ``[{"player_id": "...", "count": N}, ...]`` list, already ordered by
    Sleeper (most-added/dropped first). ``trend_type`` is ``"add"`` or
    ``"drop"``; anything else is treated as ``"add"``. Fail-neutral: ``[]``
    on any provider failure, never raises.
    """

    normalized_type = trend_type if trend_type in ("add", "drop") else "add"
    normalized_hours = max(1, int(lookback_hours or 24))
    normalized_limit = max(1, min(int(limit or 50), 200))
    return _get_trending_players_cached(
        normalized_type,
        normalized_hours,
        normalized_limit,
        _trending_cache_bucket(),
    )


def trending_add_rank_map(*, lookback_hours: int = 24, limit: int = 50) -> Dict[str, Dict[str, int]]:
    """``player_id -> {"count": int, "rank": int}`` from Sleeper's global trending-add list.

    ``rank`` is 1-indexed position within Sleeper's own ordering (1 = most
    globally added in the last ``lookback_hours``). Convenience wrapper for
    callers (web Waivers, mobile's waivers endpoint) that just want to flag
    "this free agent is on Sleeper's global trending-add list right now"
    without re-deriving rank/count from the raw list themselves. Players not
    on the list are simply absent from the returned mapping.
    """

    rows = get_trending_players("add", lookback_hours=lookback_hours, limit=limit)
    mapping: Dict[str, Dict[str, int]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        player_id = str(row.get("player_id") or "").strip()
        if not player_id or player_id in mapping:
            continue
        try:
            count = int(row.get("count") or 0)
        except (TypeError, ValueError):
            count = 0
        mapping[player_id] = {"count": count, "rank": index + 1}
    return mapping


def clear_trending_player_caches() -> None:
    """Drop the in-process cache for Sleeper's global trending-add/drop lists.

    Separate from clear_live_league_endpoint_caches() (trending has no
    league to key on) — exposed mainly for tests; the time-bucketed TTL
    above already self-expires this in both the web app and mobile's
    long-lived process without anyone calling this.
    """

    _get_trending_players_cached.cache_clear()
