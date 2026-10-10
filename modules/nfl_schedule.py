"""Real NFL schedule — opponent, home/away, and published Vegas market
lines (spread/total) per game, sourced from nflverse's public games.csv
(https://github.com/nflverse/nfldata), the same open dataset widely cited
by fantasy tools. Added because there was no schedule data anywhere in
this codebase before — only a single bye_week value on each player row
(from Sleeper's own player metadata).

Context only, by design: nothing here feeds value_score, Overall rating,
lineup optimization, or any other scoring path. coridian_ was explicit
this should not be overweighted, so this module only surfaces real,
already-published numbers (who plays whom, and the market's own spread/
total) for display — it does not compute a "matchup difficulty" score or
apply any adjustment to existing rankings.
"""

from __future__ import annotations

import functools
import os
import time
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from modules import performance

# nflverse's `gametime` column is published in US Eastern local time
# (the stadium clock, not whatever timezone the server/user happens to be
# in) — see nflverse's games.csv data dictionary. Used only to derive each
# game's real kickoff instant for `game_has_started`; never surfaced as a
# "matchup difficulty" adjustment or scoring input (see module docstring).
_GAME_TIMEZONE = ZoneInfo("America/New_York")

GAMES_CSV_URL = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"
GAMES_CACHE_PATH = "data/nfl_games.csv"
# Lines move as kickoff approaches; a few-times-a-day refresh is plenty for
# a season-long dynasty app (never read as a live in-game feed).
GAMES_CACHE_TTL_SECONDS = 6 * 60 * 60

# nflverse's team codes differ from this app's (Sleeper-sourced) codes only
# for a few relocated/renamed franchises. Historical-only codes (OAK, SD,
# STL) are mapped to their current successor so a player's current team
# code always resolves, even though nflverse keeps the old code on the
# original historical games.
TEAM_CODE_ALIASES = {
    "LA": "LAR",
    "OAK": "LV",
    "SD": "LAC",
    "STL": "LAR",
}


def _ensure_data_dir() -> None:
    if not os.path.exists("data"):
        os.makedirs("data")


def _cache_is_fresh(path: str, ttl: int) -> bool:
    if not os.path.exists(path):
        return False
    try:
        return (time.time() - os.path.getmtime(path)) < ttl
    except Exception:
        return False


def _load_games_uncached(*, refresh: bool = False) -> pd.DataFrame:
    _ensure_data_dir()
    if not refresh and _cache_is_fresh(GAMES_CACHE_PATH, GAMES_CACHE_TTL_SECONDS):
        try:
            return pd.read_csv(GAMES_CACHE_PATH, low_memory=False)
        except Exception:
            pass
    try:
        with performance.time_block("nfl_schedule_fetch", category="external"):
            response = requests.get(GAMES_CSV_URL, timeout=20)
        response.raise_for_status()
        with open(GAMES_CACHE_PATH, "w", encoding="utf-8") as handle:
            handle.write(response.text)
        return pd.read_csv(GAMES_CACHE_PATH, low_memory=False)
    except Exception:
        if os.path.exists(GAMES_CACHE_PATH):
            try:
                return pd.read_csv(GAMES_CACHE_PATH, low_memory=False)
            except Exception:
                pass
        return pd.DataFrame()


# Parsing the whole games CSV from disk (pd.read_csv, then downstream
# groupby/aggregation) on every single call is wasted work within a short
# window: team_defense_strength and team_schedule each call load_games()
# independently, and a single team_defense_points_allowed_by_position
# aggregation (modules.player_projections) calls team_schedule once per
# team — 32 redundant re-reads of the same unchanged file for one request.
# The disk cache above already throttles the network *fetch* to once every
# GAMES_CACHE_TTL_SECONDS (6h); this additionally throttles the CSV *parse*
# itself, using the same live-time-bucket + lru_cache idiom as
# modules.news._enriched_news_pool_cached (an in-process cache, not shared
# across the mobile-api's worker processes — each worker gets its own copy,
# matching how that news cache is deliberately per-process rather than
# Redis-backed).
#
# Deliberately much shorter than the 6h disk TTL, and shorter than
# modules.player_projections.DEFENSE_STRENGTH_TTL_SECONDS (30 min) — this is
# the *schedule* cache, not the defensive-ratings cache. Nothing that
# computes a defensive rating (team_defense_strength here, or
# team_defense_points_allowed_by_position in modules.player_projections) is
# itself cached by this bucket: both recompute from scratch on every call,
# they just read a DataFrame out of this short-lived cache instead of
# re-parsing the CSV from disk each time. So once newly-completed games land
# in the disk cache, ratings reflect them within minutes, not hours.
LOAD_GAMES_INPROCESS_TTL_SECONDS = 5 * 60


def _load_games_cache_bucket() -> int:
    return int(time.time() // LOAD_GAMES_INPROCESS_TTL_SECONDS)


@functools.lru_cache(maxsize=4)
def _load_games_cached(_bucket: int) -> pd.DataFrame:
    return _load_games_uncached()


def clear_load_games_cache() -> None:
    """Drop the in-process games-table cache — tests, and any manual refresh hook."""

    _load_games_cached.cache_clear()


def load_games(*, refresh: bool = False) -> pd.DataFrame:
    """Every real NFL game on record, including this week's not-yet-played
    games with their real Vegas lines. Disk-cached like
    modules.sleeper.get_players — a fetch failure falls back to whatever is
    already on disk (or an empty frame) rather than raising.

    The non-refresh path additionally goes through a short-lived in-process
    cache (see LOAD_GAMES_INPROCESS_TTL_SECONDS above) so repeated lookups
    within the same few minutes don't each re-parse the CSV from disk.
    ``refresh=True`` always bypasses both caches and reads straight from
    disk/network — this is what a caller reaches for when it deliberately
    wants the current on-disk state, not a possibly-stale in-process copy.
    """

    if refresh:
        return _load_games_uncached(refresh=True)
    return _load_games_cached(_load_games_cache_bucket())


def _normalize_team_code(games: pd.DataFrame) -> pd.DataFrame:
    df = games.copy()
    for column in ("home_team", "away_team"):
        if column in df.columns:
            df[column] = df[column].map(lambda code: TEAM_CODE_ALIASES.get(str(code), str(code)))
    return df


def _kickoff_at_utc(game: pd.Series) -> str | None:
    """This game's real kickoff instant, in UTC ISO-8601 — combines
    nflverse's `gameday` (date) and `gametime` (Eastern-time local kickoff)
    columns. None when either is missing/unparseable rather than a guessed
    time; `game_has_started` falls back to the `played` flag (or lets the
    caller fall back further) when this is unavailable.
    """
    gameday = game.get("gameday")
    gametime = game.get("gametime")
    if gameday is None or pd.isna(gameday) or gametime is None or pd.isna(gametime):
        return None
    try:
        naive = pd.Timestamp(f"{gameday} {gametime}")
        if pd.isna(naive):
            return None
        localized = naive.tz_localize(_GAME_TIMEZONE)
        return localized.tz_convert(timezone.utc).isoformat()
    except Exception:
        return None


def _row_from_game(game: pd.Series, *, team_is_home: bool) -> dict[str, Any]:
    opponent = game["away_team"] if team_is_home else game["home_team"]
    team_score = game["home_score"] if team_is_home else game["away_score"]
    opponent_score = game["away_score"] if team_is_home else game["home_score"]
    raw_spread = game.get("spread_line")
    # spread_line is published from the home team's perspective (negative =
    # home favored) — flip the sign for the away team so "spread_line" in
    # this module's output always reads from the requested team's own
    # perspective (negative = this team favored).
    team_spread = None
    if raw_spread is not None and not pd.isna(raw_spread):
        team_spread = float(raw_spread) if team_is_home else -float(raw_spread)
    total_line = game.get("total_line")
    played = team_score is not None and not pd.isna(team_score)
    return {
        "week": int(game["week"]),
        "opponent": str(opponent),
        "is_home": bool(team_is_home),
        "spread_line": team_spread,
        "total_line": None if total_line is None or pd.isna(total_line) else float(total_line),
        "played": bool(played),
        "team_score": float(team_score) if played else None,
        "opponent_score": float(opponent_score) if played and opponent_score is not None and not pd.isna(opponent_score) else None,
        "bye": False,
        # Real kickoff instant (UTC) for this one game — see
        # `_kickoff_at_utc`/`game_has_started`. None for older seasons or
        # any row missing gameday/gametime.
        "kickoff_at": _kickoff_at_utc(game),
    }


def team_schedule(
    team: str,
    season: int,
    *,
    games: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    """This team's real regular-season games for one season, week-ordered.

    Playoff rounds (game_type != "REG") are excluded — fantasy rosters and
    this app's "week" concept both stop mattering the same way once a
    league's own bracket takes over, and nflverse's playoff "weeks" don't
    share a numbering space with the regular season anyway.
    """

    df = games if games is not None else load_games()
    if df.empty or "season" not in df.columns:
        return []
    team_code = TEAM_CODE_ALIASES.get(str(team).upper().strip(), str(team).upper().strip())
    season_games = _normalize_team_code(df[df["season"] == season])
    if "game_type" in season_games.columns:
        season_games = season_games[season_games["game_type"] == "REG"]

    rows = [_row_from_game(g, team_is_home=True) for _, g in season_games[season_games["home_team"] == team_code].iterrows()]
    rows += [_row_from_game(g, team_is_home=False) for _, g in season_games[season_games["away_team"] == team_code].iterrows()]
    # nflverse's games.csv has no explicit bye-week row for a team — it's
    # just the one week number missing from that team's home/away rows
    # within its own season span. Synthesized here (never as an extra fetch)
    # so the schedule doesn't silently skip straight from one week to the
    # next with no visual sign the team didn't play that week.
    if rows:
        present_weeks = {row["week"] for row in rows}
        first_week, last_week = min(present_weeks), max(present_weeks)
        for week in range(first_week, last_week + 1):
            if week not in present_weeks:
                rows.append(
                    {
                        "week": week,
                        "opponent": None,
                        "is_home": None,
                        "spread_line": None,
                        "total_line": None,
                        "played": False,
                        "team_score": None,
                        "opponent_score": None,
                        "bye": True,
                        "kickoff_at": None,
                    }
                )
    rows.sort(key=lambda row: row["week"])
    return rows


def team_defense_strength(season: int, *, games: pd.DataFrame | None = None) -> dict[str, dict[str, Any]]:
    """Every team's real defensive strength this season, from actual points
    allowed in completed games — not a fabricated per-player grade. This app
    has no individual-defender data or IDP scoring at all (it's built
    entirely around skill-position offense), so "impact defender is hurt"
    isn't something this can model directly; a defense trending worse
    lately (whatever the cause) shows up here instead, by blending the
    season-long average with a recent-games average rather than only the
    season number alone.

    Returns {team_code: {"points_allowed_avg", "recent_points_allowed_avg"
    (None until at least 2 games), "games_played", "rank" (1 = toughest),
    "tier" ("tough" | "average" | "weak")} for every team with at least one
    completed game. Teams with no completed games yet aren't included —
    no fabricated rank for a team nothing is known about yet.
    """
    df = games if games is not None else load_games()
    if df.empty or "season" not in df.columns:
        return {}
    season_games = _normalize_team_code(df[df["season"] == season])
    if "game_type" in season_games.columns:
        season_games = season_games[season_games["game_type"] == "REG"]
    played = season_games[season_games["home_score"].notna() & season_games["away_score"].notna()]
    if played.empty:
        return {}

    # One row per (team, week, points allowed that week) — grouping on the
    # team's own game count (not calendar week) so "recent" means this
    # team's last N games regardless of where its bye fell.
    rows: list[dict[str, Any]] = []
    for _, game in played.iterrows():
        rows.append({"team": game["home_team"], "week": game["week"], "points_allowed": game["away_score"]})
        rows.append({"team": game["away_team"], "week": game["week"], "points_allowed": game["home_score"]})
    long_df = pd.DataFrame(rows)

    recent_games = 3
    entries: dict[str, dict[str, Any]] = {}
    weighted_by_team: dict[str, float] = {}
    for team, group in long_df.groupby("team"):
        ordered = group.sort_values("week")
        season_avg = float(ordered["points_allowed"].mean())
        recent = ordered.tail(recent_games)
        recent_avg = float(recent["points_allowed"].mean()) if len(recent) >= 2 else None
        weighted = (season_avg + recent_avg) / 2 if recent_avg is not None else season_avg
        entries[str(team)] = {
            "points_allowed_avg": round(season_avg, 1),
            "recent_points_allowed_avg": round(recent_avg, 1) if recent_avg is not None else None,
            "games_played": int(len(ordered)),
        }
        weighted_by_team[str(team)] = weighted

    ranked_teams = sorted(weighted_by_team, key=lambda team: weighted_by_team[team])
    total = len(ranked_teams)
    tough_cutoff = max(1, round(total / 3))
    weak_cutoff = total - max(1, round(total / 3))
    for index, team in enumerate(ranked_teams):
        rank = index + 1
        entries[team]["rank"] = rank
        if rank <= tough_cutoff:
            entries[team]["tier"] = "tough"
        elif rank > weak_cutoff:
            entries[team]["tier"] = "weak"
        else:
            entries[team]["tier"] = "average"

    return entries


def team_matchup_for_week(
    team: str,
    week: int,
    season: int,
    *,
    games: pd.DataFrame | None = None,
) -> dict[str, Any] | None:
    """One real game — this team's opponent, home/away, and the market's
    own spread/total for that specific week, or None when nothing is on
    record (bye week, or the schedule simply doesn't have that week yet)."""

    for row in team_schedule(team, season, games=games):
        if row["week"] == week:
            return row
    return None


def game_has_started(game_row: dict[str, Any] | None, *, now: datetime | None = None) -> bool | None:
    """Whether a specific game (one `team_matchup_for_week` row) has
    actually kicked off — not whether the WEEK has started, since games
    across a week start at different times (Thursday/Sunday-early/Sunday-
    late/Sunday-night/Monday). Used by the Matchup screen to decide whether
    a starter's `0.0` real points is a genuine not-yet-played zero or just
    "his game hasn't begun yet" (see services.mobile_api_service's
    `_player_game_started`).

    True once the real kickoff instant (`kickoff_at`) has passed, or
    unconditionally once nflverse reports a final score (`played`) even if
    the kickoff math is somehow off. None when there's no row at all (bye)
    or `kickoff_at` couldn't be computed (older data, missing columns) —
    callers fall back to another signal rather than guessing.
    """

    if game_row is None:
        return None
    if game_row.get("played"):
        return True
    kickoff_at = game_row.get("kickoff_at")
    if not kickoff_at:
        return None
    try:
        kickoff = datetime.fromisoformat(kickoff_at)
    except ValueError:
        return None
    reference = now if now is not None else datetime.now(timezone.utc)
    return reference >= kickoff
