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

import os
import time
from typing import Any

import pandas as pd
import requests

from modules import performance

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


def load_games(*, refresh: bool = False) -> pd.DataFrame:
    """Every real NFL game on record, including this week's not-yet-played
    games with their real Vegas lines. Disk-cached like
    modules.sleeper.get_players — a fetch failure falls back to whatever is
    already on disk (or an empty frame) rather than raising."""

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


def _normalize_team_code(games: pd.DataFrame) -> pd.DataFrame:
    df = games.copy()
    for column in ("home_team", "away_team"):
        if column in df.columns:
            df[column] = df[column].map(lambda code: TEAM_CODE_ALIASES.get(str(code), str(code)))
    return df


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
                    }
                )
    rows.sort(key=lambda row: row["week"])
    return rows


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
