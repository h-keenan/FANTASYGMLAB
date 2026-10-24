"""Games: the Season Simulator what-if and the league Pick'em.

Both are built on data the app already has, never invented numbers:

- **Season Simulator what-if**: re-runs the existing Monte Carlo
  (``modules.playoff_simulator``) with the user's own Roster Power swapped for
  the power the roster would have after an add/drop. Power comes from the same
  starter-weighted scorer the Teams screen uses
  (``team_eval._score_starter_weighted_roster``), so a hypothetical roster is
  scored exactly like a real one. Baseline and scenario use equally seeded
  random draws, so the difference is the roster change, not simulation noise.
- **Pick'em**: weekly, inside the user's own league. Matchups, scores and
  results come from Sleeper (``modules.sleeper.get_matchups``); picks are the
  only thing stored (``docs/supabase_games.sql``). Grading is computed from the
  real results on read, so nothing about a result is ever stored or guessed.
  No money, no prizes.

Storage is optional: a missing table raises ``Unavailable`` and callers answer
``available: false`` (same dormant pattern as ``modules.community_shared_trades``).
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence
from urllib.parse import quote

import pandas as pd
import requests

from modules import app_config, auth_supabase, team_eval
from modules.community_shared_trades import is_missing_table

PICKS_TABLE = "games_pickem_picks"
SETUP_DOC = "docs/supabase_games.sql"

WHAT_IF_MAX_PLAYERS = 3
# Monte Carlo standard error on a playoff probability near 50% is ~0.9 points
# at 3,000 trials. Changes inside twice that are reported as "within noise".
NOISE_POINTS = 2.0


class Unavailable(RuntimeError):
    """Storage missing or unreachable; callers degrade quietly."""


# ---------------------------------------------------------------------------
# Season simulator what-if (pure)
# ---------------------------------------------------------------------------


def score_roster(
    players_df: pd.DataFrame,
    player_ids: Sequence[str],
    score_field: str,
    lineup_settings: Mapping[str, Any] | None,
) -> dict[str, float]:
    """Starter-weighted roster score for exactly ``player_ids`` (same scorer as
    the Teams screen's Roster Power). Unknown ids are ignored."""

    ids = {str(pid) for pid in player_ids}
    if players_df.empty or "player_id" not in players_df.columns:
        return team_eval._score_starter_weighted_roster(players_df.iloc[0:0], score_field, dict(lineup_settings or {}))
    frame = players_df[players_df["player_id"].astype(str).isin(ids)].copy()
    return team_eval._score_starter_weighted_roster(frame, score_field, dict(lineup_settings or {}))


def apply_roster_change(
    current_ids: Sequence[str], add_ids: Sequence[str], drop_ids: Sequence[str]
) -> list[str]:
    drop = {str(pid) for pid in drop_ids}
    out = [str(pid) for pid in current_ids if str(pid) not in drop]
    for pid in add_ids:
        if str(pid) not in out:
            out.append(str(pid))
    return out


def validate_roster_change(
    current_ids: Sequence[str],
    add_ids: Sequence[str],
    drop_ids: Sequence[str],
    known_ids: set[str],
) -> str:
    """"" when valid, else a short user-facing reason."""

    current = {str(pid) for pid in current_ids}
    adds = [str(pid) for pid in add_ids]
    drops = [str(pid) for pid in drop_ids]
    if not adds and not drops:
        return "Pick a player to add or drop."
    if len(adds) > WHAT_IF_MAX_PLAYERS or len(drops) > WHAT_IF_MAX_PLAYERS:
        return f"Up to {WHAT_IF_MAX_PLAYERS} players on each side."
    if len(set(adds)) != len(adds) or len(set(drops)) != len(drops):
        return "Each player can only be listed once."
    if any(pid in current for pid in adds):
        return "That player is already on your roster."
    if any(pid not in current for pid in drops):
        return "You can only drop players on your roster."
    if any(pid not in known_ids for pid in adds):
        return "Unknown player."
    return ""


def compare_odds(baseline: Mapping[str, Any], scenario: Mapping[str, Any]) -> dict[str, Any]:
    """Change between two simulator team rows for the same team."""

    def num(row: Mapping[str, Any], key: str) -> float:
        try:
            return float(row.get(key) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    playoff = round(num(scenario, "playoff_probability") - num(baseline, "playoff_probability"), 1)
    return {
        "playoff_probability": playoff,
        "median_final_wins": round(num(scenario, "median_final_wins") - num(baseline, "median_final_wins")),
        "median_seed": int(num(scenario, "median_seed") - num(baseline, "median_seed")),
        "within_noise": abs(playoff) < NOISE_POINTS,
    }


def what_if_factors(
    before: Mapping[str, float],
    after: Mapping[str, float],
    *,
    remaining_games: int,
    weeks_remaining: int,
    slope_fitted: bool,
    games_used_for_fit: int,
) -> list[dict[str, str]]:
    """The several real inputs behind the answer, so a single number never
    stands alone: lineup strength, depth, how much season is left to use it,
    and how well the win model is calibrated to this league."""

    starter = after.get("starter_score", 0.0) - before.get("starter_score", 0.0)
    bench = after.get("bench_score", 0.0) - before.get("bench_score", 0.0)
    total = after.get("total_score", 0.0) - before.get("total_score", 0.0)
    out = [
        {"label": "Lineup strength", "detail": f"{starter:+.0f} starter value"},
        {"label": "Depth", "detail": f"{bench:+.0f} bench value"},
        {"label": "Roster Power", "detail": f"{total:+.0f} total"},
        {
            "label": "Season left",
            "detail": f"{remaining_games} games over {weeks_remaining} weeks"
            if remaining_games
            else "No games left to play",
        },
        {
            "label": "Win model",
            "detail": f"Fitted to {games_used_for_fit} games in this league"
            if slope_fitted
            else "Default shape; too few games played to fit this league",
        },
    ]
    return out


# ---------------------------------------------------------------------------
# Pick'em (pure)
# ---------------------------------------------------------------------------


def _rid(value: Any) -> str:
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return str(value) if value is not None else ""


def _points(entry: Mapping[str, Any]) -> float:
    try:
        return float(entry.get("points") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def group_week_matchups(
    matchups: Sequence[Mapping[str, Any]], profiles: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Head-to-head pairings for a week. A bye (no matchup_id) or an unpaired
    entry is left out; with league-median scoring there are no extra pairs to
    pick, so only real two-team matchups appear."""

    groups: dict[Any, list[Mapping[str, Any]]] = {}
    for entry in matchups or []:
        matchup_id = entry.get("matchup_id")
        if matchup_id is None or not _rid(entry.get("roster_id")):
            continue
        groups.setdefault(matchup_id, []).append(entry)
    out: list[dict[str, Any]] = []
    for matchup_id, members in groups.items():
        if len(members) != 2:
            continue
        teams = []
        for member in members:
            rid = _rid(member.get("roster_id"))
            profile = profiles.get(rid) or {}
            teams.append(
                {
                    "roster_id": rid,
                    "team_name": str(profile.get("team_name") or f"Team {rid}"),
                    "owner_name": profile.get("owner_name"),
                    "avatar_url": profile.get("avatar_url"),
                    "points": round(_points(member), 2),
                }
            )
        out.append({"matchup_id": str(matchup_id), "teams": teams})
    out.sort(key=lambda m: int(m["matchup_id"]) if m["matchup_id"].lstrip("-").isdigit() else 0)
    return out


def week_phase(week: int, current_week: int, grouped: Sequence[Mapping[str, Any]]) -> str:
    """"open" (before the first score lands), "locked" (the week has started) or
    "final" (an earlier week). Sleeper publishes no fantasy kickoff time; the
    first non-zero score in the week is the earliest honest signal that games
    have started, so picks lock at that point."""

    if week < current_week:
        return "final"
    if any(team["points"] > 0 for m in grouped for team in m["teams"]):
        return "locked"
    return "open"


def matchup_winner(matchup: Mapping[str, Any]) -> str | None:
    a, b = matchup["teams"]
    if a["points"] == b["points"]:
        return None
    return a["roster_id"] if a["points"] > b["points"] else b["roster_id"]


def build_week_view(
    week: int,
    current_week: int,
    grouped: list[dict[str, Any]],
    my_picks: Mapping[str, str],
) -> dict[str, Any]:
    """Matchups for one week with the caller's pick and, once the week is
    final, whether it was right."""

    phase = week_phase(week, current_week, grouped)
    matchups = []
    correct = graded = 0
    for matchup in grouped:
        pick = my_picks.get(matchup["matchup_id"])
        winner = matchup_winner(matchup) if phase == "final" else None
        result: bool | None = None
        if pick and winner:
            result = pick == winner
            graded += 1
            correct += 1 if result else 0
        matchups.append({**matchup, "my_pick": pick, "winner_roster_id": winner, "correct": result})
    return {
        "week": week,
        "phase": phase,
        "matchups": matchups,
        "picked": sum(1 for m in matchups if m["my_pick"]),
        "correct": correct,
        "graded": graded,
    }


def pick_error(grouped: Sequence[Mapping[str, Any]], matchup_id: str, roster_id: str) -> str:
    """"" if picking ``roster_id`` in ``matchup_id`` is valid, else why not."""

    matchup = next((m for m in grouped if m["matchup_id"] == matchup_id), None)
    if matchup is None:
        return "That matchup does not exist."
    if roster_id not in {team["roster_id"] for team in matchup["teams"]}:
        return "Pick one of the two teams in the matchup."
    return ""


def grade_picks(
    picks: Sequence[Mapping[str, Any]], winners_by_week: Mapping[int, Mapping[str, str | None]]
) -> dict[str, int]:
    correct = graded = 0
    for pick in picks:
        try:
            week = int(pick.get("week"))
        except (TypeError, ValueError):
            continue
        winner = (winners_by_week.get(week) or {}).get(str(pick.get("matchup_id")))
        if not winner:
            continue
        graded += 1
        if _rid(pick.get("picked_roster_id")) == winner:
            correct += 1
    return {"correct": correct, "graded": graded}


def build_leaderboard(
    rows: Sequence[Mapping[str, Any]],
    winners_by_week: Mapping[int, Mapping[str, str | None]],
    profiles: Mapping[str, Mapping[str, Any]],
    viewer_user_id: str,
) -> list[dict[str, Any]]:
    """Season standings among the league members who made picks. Never exposes
    user ids or raw picks, only graded totals per team."""

    by_user: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        by_user.setdefault(str(row.get("user_id") or ""), []).append(row)
    board: list[dict[str, Any]] = []
    for user_id, picks in by_user.items():
        if not user_id:
            continue
        grade = grade_picks(picks, winners_by_week)
        if grade["graded"] == 0:
            continue
        rid = _rid(picks[0].get("picker_roster_id"))
        profile = profiles.get(rid) or {}
        board.append(
            {
                "roster_id": rid,
                "team_name": str(profile.get("team_name") or f"Team {rid}"),
                "owner_name": profile.get("owner_name"),
                "avatar_url": profile.get("avatar_url"),
                "correct": grade["correct"],
                "graded": grade["graded"],
                "accuracy": round(grade["correct"] / grade["graded"] * 100),
                "mine": user_id == viewer_user_id,
            }
        )
    board.sort(key=lambda r: (-r["correct"], -r["accuracy"], r["team_name"]))
    for index, row in enumerate(board):
        row["rank"] = index + 1
    return board


# ---------------------------------------------------------------------------
# Pick'em storage (Supabase REST)
# ---------------------------------------------------------------------------


def _check(response: requests.Response) -> None:
    if response.status_code >= 400:
        raise Unavailable(SETUP_DOC if is_missing_table(response) else "request_failed")


def fetch_my_picks(config: dict, token: str, user_id: str, league_id: str, season: str) -> list[dict[str, Any]]:
    query = (
        f"select=week,matchup_id,picked_roster_id,picker_roster_id"
        f"&user_id=eq.{quote(user_id, safe='')}&league_id=eq.{quote(league_id, safe='')}&season=eq.{quote(season, safe='')}&limit=1000"
    )
    try:
        response = requests.get(
            auth_supabase.rest_api_url(config, PICKS_TABLE, query),
            headers=auth_supabase.auth_headers(config, token),
            timeout=15,
        )
    except Exception as exc:
        raise Unavailable("unreachable") from exc
    _check(response)
    rows = response.json()
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def upsert_pick(config: dict, token: str, row: dict[str, Any]) -> None:
    headers = auth_supabase.auth_headers(config, token)
    headers["Prefer"] = "return=minimal,resolution=merge-duplicates"
    try:
        response = requests.post(
            auth_supabase.rest_api_url(config, PICKS_TABLE, "on_conflict=user_id,league_id,season,week,matchup_id"),
            headers=headers,
            json=row,
            timeout=15,
        )
    except Exception as exc:
        raise Unavailable("unreachable") from exc
    _check(response)


def fetch_league_picks(league_id: str, season: str) -> list[dict[str, Any]] | None:
    """Every member's picks for the league leaderboard (service role, because
    members cannot read each other's picks under RLS: that would reveal picks
    before the lock). Only graded totals ever leave the API. Returns None when
    no service-role key is configured, so callers fall back to the caller's own
    picks."""

    url = app_config.config_value("SUPABASE_URL")
    key = app_config.config_value("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    query = (
        f"select=user_id,week,matchup_id,picked_roster_id,picker_roster_id"
        f"&league_id=eq.{quote(league_id, safe='')}&season=eq.{quote(season, safe='')}&limit=10000"
    )
    try:
        response = requests.get(
            f"{url.rstrip('/')}/rest/v1/{PICKS_TABLE}?{query}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=15,
        )
    except Exception as exc:
        raise Unavailable("unreachable") from exc
    _check(response)
    rows = response.json()
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
