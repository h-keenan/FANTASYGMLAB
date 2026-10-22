"""Completed-week actual production for the external content-bot API.

Backs two `/v1/external/*` routes (full contract:
docs/external-api-contract.md, "Weekly recap"):

- ``GET /v1/external/players/{player_id}/week-result`` ->
  ``build_player_week_result``: one player's real stat line for one week.
- ``GET /v1/external/recap`` -> ``build_week_recap``: the week's real top
  performers and notable statistical lines.

Every number here is Sleeper's own published weekly stat line, read from
the per-week box-score fields ``modules.sleeper`` now keeps on its season
stats cache (``WEEKLY_BOX_SCORE_FIELD_MAP``, on the same weekly rows and the
same provider calls as before). That cache is a file under ``data/``, so all
mobile-api worker processes share it; nothing here is process-local
retention. Nothing is a projection, and nothing is this app's own rating.
When a game hasn't finished, the cached stat line was captured before the
game could have finished, or the cache predates box-score retention, the
result says so with a non-``"ok"`` status (or an ``"unavailable"`` box
score) and a reason, never a guessed or zero-filled number.

Business logic lives here; the HTTP routes in
``services/mobile_api_service.py`` are thin wrappers, the same split
``modules.player_background_profile`` uses.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from modules import nfl_schedule, player_projections, sleeper

ID_NAMESPACE = "sleeper"
SEASON_TYPE = "regular"
SOURCE_WEEKLY_STATS = "sleeper_weekly_stats"
SOURCE_PLAYERS = "sleeper_player_directory"
SOURCE_SCHEDULE = "nflverse_games_csv"

# Sleeper's regular-season stats endpoint, and modules.sleeper's season
# cache, both cover weeks 1-18.
MIN_WEEK = 1
MAX_WEEK = 18

# How long after kickoff a cached stat line can first be trusted as the
# finished game's line. A stats cache written before kickoff + this window
# may hold a partial, in-game line, so that player reports
# ``"stats_pending"`` instead of ``"ok"``. NFL games run about 3 to 3.5
# hours; 4 hours is a conservative bound, not a measured one.
FINAL_STATS_SETTLE = timedelta(hours=4)

SCORING_FORMATS = ("ppr", "half_ppr", "standard")
_POINTS_FIELD_BY_FORMAT = {
    "ppr": "fantasy_points_ppr",
    "half_ppr": "fantasy_points_half_ppr",
    "standard": "fantasy_points_standard",
}

# Real per-week fields on a modules.sleeper weekly row, in response order.
BOX_SCORE_FIELDS = (
    "receptions",
    "targets",
    "receiving_yards",
    "receiving_tds",
    "rush_attempts",
    "rushing_yards",
    "rushing_tds",
    "pass_attempts",
    "passing_completions",
    "passing_yards",
    "passing_tds",
    "passing_interceptions",
    "fumbles_lost",
    "field_goals_made",
    "field_goals_attempted",
    "extra_points_made",
    "extra_points_attempted",
)
# Fields kept on weekly rows before box-score retention shipped. A cache
# written before then still has real values for these.
_PRE_BOX_SCORE_FIELDS = frozenset({"receptions", "targets", "rush_attempts", "pass_attempts"})

SCORING_NOTE = (
    "fantasy_points_ppr / fantasy_points_half_ppr / fantasy_points_standard "
    "are Sleeper's own published pts_ppr / pts_half_ppr / pts_std for this "
    "stat line under Sleeper's default league scoring, passed through "
    "unchanged and never recomputed here. The formats differ only in the "
    "per-reception value: PPR = standard + 1.0 per reception, half-PPR = "
    "standard + 0.5 per reception."
)

ZERO_OMISSION_NOTE = (
    "Sleeper omits zero-valued stats from its weekly payload, so a box-score "
    "field is null whenever Sleeper reported nothing for it (most often a "
    "real zero, e.g. no touchdowns). It is never filled in as 0 here."
)

CORRECTION_VERSION_UNAVAILABLE_REASON = (
    "No durable store exists for a monotonic correction counter: the stats "
    "cache under data/ and Redis are both rebuilt on every production "
    "redeploy, so a counter would silently reset. Use stat_line_fingerprint "
    "instead. It is a deterministic hash of this exact stat line, stable "
    "across redeploys, and it changes whenever Sleeper revises the line."
)

BOX_SCORE_NOT_RETAINED_REASON = (
    "This season's cached weekly stats were written before per-week "
    "box-score retention shipped (modules.sleeper.WEEKLY_BOX_SCORE_FIELD_MAP), "
    "so yards, touchdowns, interceptions, kicking and standard/half-PPR "
    "points are not on record for this week. The active season's cache "
    "rebuilds on its normal refresh (at most 12 hours) with these fields; "
    "committed prior-season caches keep their long TTL. Receptions, targets, "
    "attempts and PPR points were retained before and are still real."
)

STATUS_REASONS = {
    "unknown_player": "No player with this id exists in the Sleeper player directory.",
    "unsupported_position": (
        "Week results cover QB/RB/WR/TE/K only, the same positions as the "
        "projections endpoints."
    ),
    "no_team": (
        "This player has no current NFL team in the Sleeper directory, so "
        "the real schedule can't confirm whether a game was played or has "
        "finished."
    ),
    "no_schedule_data": "The real NFL schedule has no game on record for this team and week.",
    "bye_week": "This player's team had a bye this week.",
    "team_schedule_mismatch": (
        "Sleeper has a stat line for this player this week, but his CURRENT "
        "team had a bye. He most likely played for a different team then "
        "(trade or signing), so this week's opponent and finality can't be "
        "confirmed from the current team's schedule."
    ),
    "not_yet_played": "This player's game hasn't kicked off yet.",
    "game_not_final": (
        "This player's game has kicked off but the real schedule has no final "
        "score yet, so any stat line would be partial."
    ),
    "unknown_game_status": (
        "The real schedule has neither a final score nor a kickoff time for "
        "this game, so whether it has been played can't be determined."
    ),
    "stats_pending": (
        "The game is final, but the cached Sleeper stat line was fetched "
        "before the game could have finished (earlier than kickoff + 4h), so "
        "it may be partial. It is replaced on the stats cache's next refresh."
    ),
    "did_not_play": (
        "The game is final and the stats cache was captured after it, but "
        "Sleeper published no games-played stat line for this player that "
        "week (inactive, DNP, or not on this roster that week). Not assumed "
        "to be a zero-point game."
    ),
}

# Notable-line thresholds. These are conventional fantasy milestone lines
# (Sleeper's own payload carries matching bonus_pass_yd_300 /
# bonus_rush_yd_100 / bonus_rec_yd_100 flags). A line is "notable" only
# for a real stat that met one of these, never for the app's own model.
NOTABLE_CRITERIA: tuple[dict[str, Any], ...] = (
    {"code": "passing_300_yards", "field": "passing_yards", "threshold": 300},
    {"code": "passing_4_tds", "field": "passing_tds", "threshold": 4},
    {"code": "rushing_100_yards", "field": "rushing_yards", "threshold": 100},
    {"code": "receiving_100_yards", "field": "receiving_yards", "threshold": 100},
    {"code": "receptions_10", "field": "receptions", "threshold": 10},
    {"code": "scrimmage_2_tds", "field": "scrimmage_tds", "threshold": 2},
    {"code": "field_goals_4", "field": "field_goals_made", "threshold": 4},
)

DEFAULT_TOP_LIMIT = 10
MAX_TOP_LIMIT = 50


def _iso(epoch: float | None) -> str | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _position_group(position: str | None) -> str | None:
    """Same buckets as the projections endpoints'
    ``services.mobile_api_service._external_position_group``."""

    if not position:
        return None
    normalized = str(position).strip().upper()
    if normalized in player_projections.OFFENSIVE_POSITIONS:
        return "skill"
    if normalized == player_projections.KICKER_POSITION:
        return "kicker"
    return "unsupported"


def _display_name(player: Mapping[str, Any]) -> str | None:
    full_name = player.get("full_name")
    if not full_name:
        first = str(player.get("first_name") or "").strip()
        last = str(player.get("last_name") or "").strip()
        full_name = f"{first} {last}".strip() or None
    return str(full_name) if full_name else None


def _week_row(record: Any, week: int) -> dict[str, Any] | None:
    weekly = record.get("weekly") if isinstance(record, dict) else None
    if not isinstance(weekly, list):
        return None
    for row in weekly:
        if isinstance(row, dict) and int(row.get("week") or 0) == int(week):
            return row
    return None


def _team_week_game(
    team: str,
    week: int,
    season: int,
    *,
    games: Any,
    schedule_cache: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    """This team's real game row for the week (a bye row on a bye), or None."""

    if team not in schedule_cache:
        schedule_cache[team] = nfl_schedule.team_schedule(team, season, games=games)
    return next((r for r in schedule_cache[team] if int(r["week"]) == int(week)), None)


def _game_status(game: dict[str, Any] | None, *, now: datetime) -> str:
    if game is None:
        return "unknown"
    if game.get("bye"):
        return "bye"
    if game.get("played"):
        return "final"
    started = nfl_schedule.game_has_started(game, now=now)
    if started is True:
        return "in_progress_or_awaiting_final"
    if started is False:
        return "upcoming"
    return "unknown"


def _stats_captured_after_final(game: dict[str, Any] | None, stats_written_at: float | None) -> bool | None:
    """Whether the cached stat line was fetched late enough to be the
    finished game's line. None when the kickoff time is unknown."""

    if stats_written_at is None:
        return False
    kickoff_at = (game or {}).get("kickoff_at")
    if not kickoff_at:
        return None
    try:
        kickoff = datetime.fromisoformat(kickoff_at)
    except ValueError:
        return None
    return datetime.fromtimestamp(stats_written_at, tz=timezone.utc) >= kickoff + FINAL_STATS_SETTLE


def _fingerprint(values: Mapping[str, Any]) -> str:
    canonical = json.dumps(dict(values), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _stat_line(row: Mapping[str, Any], *, has_box_scores: bool) -> dict[str, Any]:
    """Box score + points for an ``"ok"`` result. With a pre-retention cache,
    only the fields that cache really kept are filled; the rest stay null
    and the box score is marked unavailable."""

    box_score: dict[str, Any] = {}
    for field in BOX_SCORE_FIELDS:
        if not has_box_scores and field not in _PRE_BOX_SCORE_FIELDS:
            box_score[field] = None
            continue
        value = row.get(field)
        box_score[field] = int(value) if value is not None else None
    points = {
        "fantasy_points_ppr": row.get("fantasy_points_ppr"),
        "fantasy_points_half_ppr": row.get("fantasy_points_half_ppr") if has_box_scores else None,
        "fantasy_points_standard": row.get("fantasy_points_standard") if has_box_scores else None,
    }
    snap_share = row.get("snap_share")
    return {
        "box_score_status": "ok" if has_box_scores else "unavailable",
        "box_score_unavailable_reason": None if has_box_scores else BOX_SCORE_NOT_RETAINED_REASON,
        "box_score": box_score,
        "snap_share": round(float(snap_share), 4) if snap_share is not None else None,
        **points,
        "stat_line_fingerprint": _fingerprint({**box_score, **points}),
    }


def _empty_stat_line() -> dict[str, Any]:
    return {
        "box_score_status": "unavailable",
        "box_score_unavailable_reason": None,
        "box_score": {field: None for field in BOX_SCORE_FIELDS},
        "snap_share": None,
        "fantasy_points_ppr": None,
        "fantasy_points_half_ppr": None,
        "fantasy_points_standard": None,
        "stat_line_fingerprint": None,
    }


def _result_for_player(
    player_id: str,
    week: int,
    season: int,
    *,
    players: Mapping[str, Any],
    weekly_stats: Mapping[str, Any],
    has_box_scores: bool,
    stats_written_at: float | None,
    games: Any,
    schedule_cache: dict[str, list[dict[str, Any]]],
    now: datetime,
) -> dict[str, Any]:
    player = players.get(str(player_id))
    payload: dict[str, Any] = {
        "player_id": str(player_id),
        "id_namespace": ID_NAMESPACE,
        "season": int(season),
        "week": int(week),
        "season_type": SEASON_TYPE,
        "status": "unknown_player",
        "unavailable_reason": None,
        "display_name": None,
        "team": None,
        "team_basis": None,
        "position": None,
        "position_group": None,
        "active": None,
        "opponent": None,
        "is_home": None,
        "bye": None,
        "game_id": None,
        "kickoff_at": None,
        "game_status": "unknown",
        "week_complete": None,
        "team_score": None,
        "opponent_score": None,
        "stats_captured_after_final": None,
        **_empty_stat_line(),
        "correction_version": None,
        "correction_version_unavailable_reason": CORRECTION_VERSION_UNAVAILABLE_REASON,
        "scoring_note": SCORING_NOTE,
        "zero_omission_note": ZERO_OMISSION_NOTE,
        "source": {
            "weekly_stats": SOURCE_WEEKLY_STATS,
            "players": SOURCE_PLAYERS,
            "schedule": SOURCE_SCHEDULE,
        },
        "stats_as_of": _iso(stats_written_at),
    }

    def _finish(status: str) -> dict[str, Any]:
        payload["status"] = status
        if status != "ok":
            payload["unavailable_reason"] = STATUS_REASONS.get(status)
            payload["box_score_unavailable_reason"] = (
                f"No real final stat line for this week (status: {status})."
            )
        return payload

    if not isinstance(player, Mapping) or not player:
        return _finish("unknown_player")

    position = str(player.get("position") or "").strip().upper() or None
    team = str(player.get("team") or "").strip().upper() or None
    payload.update(
        {
            "display_name": _display_name(player),
            "team": team,
            "team_basis": "current_sleeper_directory_team" if team else None,
            "position": position,
            "position_group": _position_group(position),
            "active": player.get("active") if player.get("active") is not None else None,
        }
    )
    if position not in player_projections.PROJECTABLE_POSITIONS:
        return _finish("unsupported_position")
    if not team:
        return _finish("no_team")

    row = _week_row(weekly_stats.get(str(player_id)), week)
    played_stat_line = bool(row) and int(row.get("games_played") or 0) >= 1

    game = _team_week_game(team, week, season, games=games, schedule_cache=schedule_cache)
    if game is None:
        return _finish("no_schedule_data")
    if game.get("bye"):
        payload["bye"] = True
        payload["game_status"] = "bye"
        return _finish("team_schedule_mismatch" if played_stat_line else "bye_week")

    status_of_game = _game_status(game, now=now)
    payload.update(
        {
            "opponent": game.get("opponent"),
            "is_home": game.get("is_home"),
            "bye": False,
            "game_id": game.get("game_id"),
            "kickoff_at": game.get("kickoff_at"),
            "game_status": status_of_game,
            "week_complete": bool(game.get("played")),
            "team_score": game.get("team_score"),
            "opponent_score": game.get("opponent_score"),
        }
    )
    if status_of_game == "upcoming":
        return _finish("not_yet_played")
    if status_of_game == "in_progress_or_awaiting_final":
        return _finish("game_not_final")
    if status_of_game != "final":
        return _finish("unknown_game_status")

    captured = _stats_captured_after_final(game, stats_written_at)
    payload["stats_captured_after_final"] = captured
    if captured is False:
        return _finish("stats_pending")
    if not played_stat_line:
        return _finish("did_not_play")

    payload.update(_stat_line(row, has_box_scores=has_box_scores))
    return _finish("ok")


def _load_inputs(season: int) -> tuple[dict[str, Any], dict[str, Any], bool, float | None, Any]:
    players = sleeper.get_players()
    weekly_stats = sleeper.get_season_player_stats(season=season, retain_weekly=True)
    has_box_scores = sleeper.season_stats_cache_has_box_scores(weekly_stats)
    stats_written_at = sleeper.season_stats_cache_written_at(season)
    games = nfl_schedule.load_games()
    return players, weekly_stats, has_box_scores, stats_written_at, games


def validate_week(week: int) -> None:
    if not (MIN_WEEK <= int(week) <= MAX_WEEK):
        raise ValueError(f"week must be between {MIN_WEEK} and {MAX_WEEK}.")


def build_player_week_result(
    player_id: str,
    week: int,
    season: int | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """One player's real stat line for one regular-season week. Always a
    full payload with a ``status``; see ``STATUS_REASONS`` for every
    non-``"ok"`` status."""

    validate_week(week)
    resolved_season = int(season) if season is not None else sleeper.default_player_stats_season()
    players, weekly_stats, has_box_scores, stats_written_at, games = _load_inputs(resolved_season)
    result = _result_for_player(
        str(player_id),
        int(week),
        resolved_season,
        players=players,
        weekly_stats=weekly_stats,
        has_box_scores=has_box_scores,
        stats_written_at=stats_written_at,
        games=games,
        schedule_cache={},
        now=now or datetime.now(timezone.utc),
    )
    result["generated_at"] = (now or datetime.now(timezone.utc)).isoformat()
    return result


def _week_schedule_status(
    season: int,
    week: int,
    games: Any,
    *,
    stats_written_at: float | None,
    schedule_cache: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Real game-level status for the whole week, from nflverse's schedule
    (each game read once, from its home team's ``team_schedule`` row)."""

    final_ids: list[str] = []
    pending_ids: list[str] = []
    captured_flags: list[bool | None] = []
    scheduled = 0
    rows: list[dict[str, Any]] = []
    try:
        frame = games[(games["season"] == season) & (games["week"] == week)]
        if "game_type" in frame.columns:
            frame = frame[frame["game_type"] == "REG"]
        home_teams = sorted({str(code) for code in frame["home_team"].tolist()})
    except Exception:
        home_teams = []
    for home_team in home_teams:
        game = _team_week_game(home_team, week, season, games=games, schedule_cache=schedule_cache)
        if game is not None and not game.get("bye") and game.get("is_home"):
            rows.append(game)
    for row in rows:
        scheduled += 1
        game_id = row.get("game_id") or f"{season}_{week}_unknown_{scheduled}"
        if row.get("played"):
            final_ids.append(str(game_id))
            captured_flags.append(_stats_captured_after_final(row, stats_written_at))
        else:
            pending_ids.append(str(game_id))
    week_complete = scheduled > 0 and not pending_ids
    if not captured_flags:
        all_captured: bool | None = None
    elif any(flag is False for flag in captured_flags):
        all_captured = False
    elif any(flag is None for flag in captured_flags):
        all_captured = None
    else:
        all_captured = True
    return {
        "games_scheduled": scheduled,
        "games_final": len(final_ids),
        "final_game_ids": sorted(final_ids),
        "pending_game_ids": sorted(pending_ids),
        "week_complete": week_complete,
        "stats_captured_after_all_final_games": all_captured,
    }


def _scrimmage_tds(box_score: Mapping[str, Any]) -> int | None:
    rush = box_score.get("rushing_tds")
    rec = box_score.get("receiving_tds")
    if rush is None and rec is None:
        return None
    return int(rush or 0) + int(rec or 0)


def _notable_reasons(item: Mapping[str, Any]) -> list[dict[str, Any]]:
    if item.get("box_score_status") != "ok":
        return []
    box_score = dict(item.get("box_score") or {})
    box_score["scrimmage_tds"] = _scrimmage_tds(box_score)
    reasons: list[dict[str, Any]] = []
    for criterion in NOTABLE_CRITERIA:
        value = box_score.get(criterion["field"])
        if value is not None and value >= criterion["threshold"]:
            reasons.append(
                {
                    "code": criterion["code"],
                    "stat": criterion["field"],
                    "value": value,
                    "threshold": criterion["threshold"],
                }
            )
    return reasons


def build_week_recap(
    week: int,
    season: int | None = None,
    *,
    position: str | None = None,
    scoring_format: str = "ppr",
    limit: int = DEFAULT_TOP_LIMIT,
    now: datetime | None = None,
) -> dict[str, Any]:
    """The week's real results: top performers (overall and per position)
    and notable statistical lines, ranked by Sleeper's own published points
    for ``scoring_format``. Only players with an ``"ok"`` week result (a
    final game, a stat line captured after it, and a games-played line) are
    ranked; everyone else is counted by status, never ranked on a guess."""

    validate_week(week)
    if scoring_format not in SCORING_FORMATS:
        raise ValueError("scoring_format must be one of ppr, half_ppr, standard.")
    if not (1 <= int(limit) <= MAX_TOP_LIMIT):
        raise ValueError(f"limit must be between 1 and {MAX_TOP_LIMIT}.")
    position_filter = str(position).strip().upper() if position else None
    if position_filter and position_filter not in player_projections.PROJECTABLE_POSITIONS:
        raise ValueError("position must be one of QB, RB, WR, TE, K.")

    reference_now = now or datetime.now(timezone.utc)
    resolved_season = int(season) if season is not None else sleeper.default_player_stats_season()
    players, weekly_stats, has_box_scores, stats_written_at, games = _load_inputs(resolved_season)
    positions = (position_filter,) if position_filter else player_projections.PROJECTABLE_POSITIONS

    points_field = _POINTS_FIELD_BY_FORMAT[scoring_format]
    ranking_available = scoring_format == "ppr" or has_box_scores
    schedule_cache: dict[str, list[dict[str, Any]]] = {}
    ok_items: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    # Only players with a real Sleeper stat line this week can be a recap
    # performer; iterating those (not all ~11k directory rows) keeps this
    # cheap, and the week-level schedule status below covers the rest.
    for player_id, record in weekly_stats.items():
        if _week_row(record, int(week)) is None:
            continue
        player = players.get(str(player_id))
        player_position = str((player or {}).get("position") or "").strip().upper()
        if player_position not in positions:
            continue
        item = _result_for_player(
            str(player_id),
            int(week),
            resolved_season,
            players=players,
            weekly_stats=weekly_stats,
            has_box_scores=has_box_scores,
            stats_written_at=stats_written_at,
            games=games,
            schedule_cache=schedule_cache,
            now=reference_now,
        )
        status_counts[item["status"]] = status_counts.get(item["status"], 0) + 1
        if item["status"] == "ok" and item.get(points_field) is not None:
            ok_items.append(item)

    ok_items.sort(key=lambda item: (-float(item[points_field]), str(item["player_id"])))

    def _ranked(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{"rank": index + 1, **item} for index, item in enumerate(items[: int(limit)])]

    by_position = {
        pos: _ranked([item for item in ok_items if item.get("position") == pos]) for pos in positions
    }
    notable = []
    for item in ok_items:
        reasons = _notable_reasons(item)
        if reasons:
            notable.append({**item, "notable_reasons": reasons})

    week_status = _week_schedule_status(
        resolved_season, int(week), games, stats_written_at=stats_written_at, schedule_cache=schedule_cache
    )
    generated_at = reference_now.isoformat()
    return {
        "season": resolved_season,
        "week": int(week),
        "season_type": SEASON_TYPE,
        "id_namespace": ID_NAMESPACE,
        "generated_at": generated_at,
        "source": {
            "weekly_stats": SOURCE_WEEKLY_STATS,
            "players": SOURCE_PLAYERS,
            "schedule": SOURCE_SCHEDULE,
            "stats_as_of": _iso(stats_written_at),
        },
        "position_scope": list(positions),
        "scoring_format": scoring_format,
        "scoring_note": SCORING_NOTE,
        "zero_omission_note": ZERO_OMISSION_NOTE,
        "limit": int(limit),
        "week_status": week_status,
        "box_score_status": "ok" if has_box_scores else "unavailable",
        "box_score_unavailable_reason": None if has_box_scores else BOX_SCORE_NOT_RETAINED_REASON,
        "ranking_status": "ok" if ranking_available else "unavailable",
        "ranking_unavailable_reason": (
            None
            if ranking_available
            else f"{points_field} is not retained in this season's cached weekly stats. "
            + BOX_SCORE_NOT_RETAINED_REASON
        ),
        "counts": {
            "ranked_players": len(ok_items),
            "stat_lines_by_status": dict(sorted(status_counts.items())),
        },
        "top_performers": {
            "overall": _ranked(ok_items),
            "by_position": by_position,
        },
        "notable_criteria": [dict(criterion) for criterion in NOTABLE_CRITERIA],
        "notable_lines": notable,
    }
