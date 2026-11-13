"""Dashboard "Bye Week Cover" alert: a projected starter has an NFL bye coming up.

Pure function over data the Dashboard endpoint has already fetched (roster
frame, the suggested lineup, the valued player pool, the league and the
cached nflverse schedule). No network calls and no new valuation: it reuses
``team_eval.suggest_optimal_lineup``'s weekly mode (the same engine the
Matchup screen uses) to ask "who starts in week W if everyone on a bye sits".

Factors, in order (an alert needs all of them; any miss returns None):
  1. The league is in season, is not best ball (Sleeper sets those lineups)
     and has a current week. Offseason / imported / no-schedule leagues
     produce nothing rather than a guessed bye.
  2. The player is in the projected starting lineup and is not already ruled
     out (a ruled-out starter is the Injury Alert's job).
  3. His team's bye (nflverse schedule) falls in this week or the next
     ``HORIZON_WEEKS`` weeks.
  4. The bench does NOT already cover it: re-running the lineup with every
     rostered player on bye that week benched leaves a starting slot open
     that the healthy baseline lineup fills. A bench player who simply slides
     in means no alert.
  5. Fill-ins are healthy free agents at a position the open slot accepts
     (a FLEX slot accepts RB/WR/TE) whose team plays that week, best value
     first. Depth (healthy non-bye players already at the position) is
     reported so the reader sees how thin the position is.
"""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from modules import league_calendar, nfl_schedule
from modules.rankings import is_ruled_out
from modules.team_eval import lineup_open_slots, suggest_optimal_lineup

LABEL = "Bye Week Cover"
HORIZON_WEEKS = 3
MAX_SUGGESTIONS = 3

SLOT_POSITIONS: dict[str, tuple[str, ...]] = {
    "QB": ("QB",),
    "RB": ("RB",),
    "WR": ("WR",),
    "TE": ("TE",),
    "K": ("K",),
    "DEF": ("DEF",),
    "WR/RB": ("RB", "WR"),
    "REC_FLEX": ("WR", "TE"),
    "FLEX": ("RB", "WR", "TE"),
    "SUPER_FLEX": ("QB", "RB", "WR", "TE"),
    "DL": ("DL",),
    "LB": ("LB",),
    "DB": ("DB",),
    "IDP_FLEX": ("DL", "LB", "DB"),
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _score(row: Mapping[str, Any], score_field: str) -> float:
    try:
        value = float(row.get(score_field))
    except (TypeError, ValueError):
        return 0.0
    return value if value == value else 0.0


def _healthy(row: Mapping[str, Any]) -> bool:
    status = _text(row.get("status"))
    injury = _text(row.get("injury_status"))
    if is_ruled_out(status, injury):
        return False
    return injury.lower() != "doubtful"


def _bye_week(team: str, season: int, games: pd.DataFrame, memo: dict[str, int | None]) -> int | None:
    team = team.strip().upper()
    if not team:
        return None
    if team not in memo:
        try:
            memo[team] = nfl_schedule.team_bye_week(team, season, games=games)
        except Exception:
            memo[team] = None
    return memo[team]


def _identity(row: Mapping[str, Any]) -> dict[str, str]:
    return {
        "player_id": _text(row.get("player_id")),
        "name": _text(row.get("name")),
        "position": _text(row.get("position")),
        "team": _text(row.get("team")),
        "player_tier": _text(row.get("player_tier")),
        "injury_status": _text(row.get("injury_status")),
    }


def _multiset_extra(after: list[str], before: list[str]) -> list[str]:
    remaining = list(before)
    extra: list[str] = []
    for slot in after:
        if slot in remaining:
            remaining.remove(slot)
        else:
            extra.append(slot)
    return extra


def build_bye_cover_tile(
    *,
    league: Mapping[str, Any] | None,
    roster_df: pd.DataFrame,
    lineup_df: pd.DataFrame,
    free_agents_df: pd.DataFrame,
    league_settings: Mapping[str, Any] | None,
    score_field: str,
    games: pd.DataFrame | None = None,
) -> dict[str, Any] | None:
    """The Bye Week Cover tile (dashboard_engine tile shape), or None."""

    if not league_calendar.is_in_season(league) or league_calendar.is_best_ball(league):
        return None
    week = league_calendar.current_league_week(league)
    if not week or roster_df is None or roster_df.empty or lineup_df is None or lineup_df.empty:
        return None
    try:
        season = int((league or {}).get("season") or 0)
    except (TypeError, ValueError):
        season = 0
    if not season:
        return None
    if games is None:
        games = nfl_schedule.load_games()
    if games is None or games.empty:
        return None

    memo: dict[str, int | None] = {}
    horizon = range(week, week + HORIZON_WEEKS + 1)
    byes: dict[str, int] = {}
    for _, row in roster_df.iterrows():
        pid = _text(row.get("player_id"))
        bye = _bye_week(_text(row.get("team")), season, games, memo)
        if pid and bye is not None:
            byes[pid] = bye
    if not byes:
        return None

    starters = lineup_df[lineup_df["suggested_starter"].astype(bool)] if "suggested_starter" in lineup_df.columns else lineup_df.iloc[0:0]
    starter_rows = [
        row for _, row in starters.iterrows()
        if _text(row.get("player_id")) in byes and not bool(row.get("ruled_out")) and byes[_text(row.get("player_id"))] in horizon
    ]
    if not starter_rows:
        return None

    try:
        baseline_open = lineup_open_slots(
            suggest_optimal_lineup(roster_df, dict(league_settings or {}), score_field=score_field, bye_player_ids=()),
            dict(league_settings or {}),
        )
    except Exception:
        return None

    for bye_week in sorted({byes[_text(r.get("player_id"))] for r in starter_rows}):
        on_bye_ids = {pid for pid, wk in byes.items() if wk == bye_week}
        affected = sorted(
            (r for r in starter_rows if _text(r.get("player_id")) in on_bye_ids),
            key=lambda r: _score(r, score_field),
            reverse=True,
        )
        try:
            weekly = suggest_optimal_lineup(
                roster_df, dict(league_settings or {}), score_field=score_field, bye_player_ids=on_bye_ids
            )
            newly_open = _multiset_extra(lineup_open_slots(weekly, dict(league_settings or {})), baseline_open)
        except Exception:
            continue
        if not newly_open:
            continue  # the bench already covers this bye

        head = affected[0]
        head_id = _text(head.get("player_id"))
        position = _text(head.get("position"))
        eligible = {pos for slot in newly_open for pos in SLOT_POSITIONS.get(slot, ())}
        if position and position not in eligible:
            eligible.add(position)
        rank_pool = sorted(
            (r for _, r in roster_df.iterrows() if _text(r.get("position")) == position),
            key=lambda r: _score(r, score_field),
            reverse=True,
        )
        rank = next((i for i, r in enumerate(rank_pool, start=1) if _text(r.get("player_id")) == head_id), 0)
        label = f"{position}{rank}" if position and rank else (position or "starter")

        suggestions: list[dict[str, str]] = []
        if free_agents_df is not None and not free_agents_df.empty and "position" in free_agents_df.columns:
            pool = free_agents_df[free_agents_df["position"].isin(eligible)]
            if score_field in pool.columns:
                pool = pool.assign(_s=pd.to_numeric(pool[score_field], errors="coerce").fillna(0)).sort_values("_s", ascending=False)
            for _, fa in pool.iterrows():
                if len(suggestions) >= MAX_SUGGESTIONS:
                    break
                team = _text(fa.get("team"))
                if not team or not _text(fa.get("name")) or _score(fa, score_field) <= 0 or not _healthy(fa):
                    continue
                if _bye_week(team, season, games, memo) == bye_week:
                    continue
                suggestions.append(_identity(fa))

        depth = sum(
            1
            for _, r in roster_df.iterrows()
            if _text(r.get("position")) == position
            and _text(r.get("player_id")) not in on_bye_ids
            and _healthy(r)
        )
        weeks_away = bye_week - week
        when = "this week" if weeks_away == 0 else f"in Week {bye_week}"
        name = _text(head.get("name"))
        value = f"Your {label} ({name}) is on bye in Week {bye_week}"
        thin = (
            f"You have no other healthy {position} to start" if depth == 0
            else f"Only {depth} other healthy {position} on your roster, and the bench can't fill the slot"
        )
        more = len(affected) - 1
        extra = f" {more} more projected starter{'s' if more != 1 else ''} also {'are' if more != 1 else 'is'} on bye that week." if more > 0 else ""
        if suggestions:
            fill = "Look at the waiver wire for a fill-in: " + ", ".join(s["name"] for s in suggestions) + "."
        else:
            fill = f"No healthy {position} on waivers fits that week, so check the trade market."
        note = f"{fill} {thin}.{extra}"
        return {
            "label": LABEL,
            "value": value,
            "note": note,
            "tone": "risk" if weeks_away <= 1 else "waiver",
            "route_key": "waivers",
            "route_player_id": head_id,
            "route_player_name": name,
            "route_player_position": position,
            "route_player_team": _text(head.get("team")),
            "route_player_tier": _text(head.get("player_tier")),
            "route_player_score": head.get(score_field),
            "route_player_injury_status": "",
            "mentioned_players": suggestions,
            "weeks_away": weeks_away,
            "presentation": {
                "bye_cover": {
                    "week": bye_week,
                    "weeks_away": weeks_away,
                    "slot_label": label,
                    "when": when,
                    "depth": depth,
                    "also_on_bye": more,
                    "suggestions": suggestions,
                }
            },
        }
    return None
