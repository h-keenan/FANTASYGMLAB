"""Real per-game (weekly) fantasy point projections.

Before this module, FantasyGM Lab had no per-game projection anywhere — only
``modules.rankings``'s season-long ``value_score`` composite (a dynasty asset
value, not a "how many points will this player score in Week N" number) and,
once a game is live, real already-scored points via ``modules.sleeper.
get_matchups``. This module is the first-pass foundation for an honest
before-the-game weekly projection, built entirely from data already flowing
through the pipeline:

- ``modules.sleeper.get_season_player_stats(..., retain_weekly=True)`` — each
  player's compact per-week rows for the current season (targets, receptions,
  rush/pass attempts, snap share, and PPR fantasy points). See
  ``WEEKLY_RETAIN_SOURCE_FIELDS`` there.
- ``modules.nfl_schedule.team_schedule`` — each team's real opponent per week
  (nflverse's published schedule), used both to know who a defense played
  each week (so we can attribute points allowed) and to find a player's
  upcoming opponent (or bye).

What's new here (nothing like it existed before):

1. ``team_defense_points_allowed_by_position`` — for every NFL team, how many
   PPR fantasy points it has allowed to each offensive skill position
   (QB/RB/WR/TE) recently, recency-weighted so a defense trending worse/better
   lately outweighs early-season noise. This is distinct from
   ``modules.nfl_schedule.team_defense_strength``, which only tracks total
   points allowed per game (not broken out by offensive position) and is
   explicitly documented there as context-only/not a matchup-difficulty
   score. The position breakdown here is the first signal of this kind in
   the codebase (nothing tracked points allowed broken out by position
   before this), and is intentionally still not wired into value_score, rankings,
   or lineup optimization — it exists only to feed the projection below.
2. ``project_player_week`` — a first-pass weekly point projection for one
   player in one upcoming week: the player's own recency-weighted recent
   production, adjusted by the opponent's defense-strength-by-position
   signal for that specific matchup. Returns a point estimate *and* an
   honest low/high range plus a plain confidence label — never a single
   falsely-precise number — matching the "recommendations should be
   stronger than raw data, but never fabricate certainty" pattern used
   elsewhere in this app (see modules.methodology_page's CONFIDENCE_COPY
   and modules.trade_ideas's pick-range bucketing instead of a single
   fake draft slot).

Known, deliberate simplifications (first pass — do not over-engineer):

- A player's *current* Sleeper team is used to look up their opponent for
  every week, including past weeks used to build the defense signal. A
  player traded mid-season will have their pre-trade weeks attributed to
  their current team's schedule. This is a real but narrow inaccuracy
  (affects a small number of traded players' historical weeks feeding the
  defense signal) — acceptable for a first pass, called out here rather
  than silently ignored.
- The opponent multiplier is clamped to a modest range so a small defensive
  sample can't wildly swing a projection (see ``_OPPONENT_MULTIPLIER_BOUNDS``).
- Uncertainty bands are a plain-language "low/mid/high" estimate, not a
  statistically rigorous confidence interval — this codebase does not claim
  precision it does not have (see modules.methodology_page.CONFIDENCE_COPY).
- Kickers (K) get a real projection from the same recent-scoring-trend
  formula as every other position, but never an opponent-defense
  multiplier — ``team_defense_points_allowed_by_position`` intentionally
  doesn't track K (see ``OFFENSIVE_POSITIONS``'s docstring comment), so
  ``_opponent_multiplier`` naturally falls back to its neutral (1.0, no
  signal) default for every kicker matchup. A kicker's confidence is
  therefore capped at "medium" — never "high" — since ``_confidence_label``
  requires a defense signal for "high".

Nothing in this module is wired into any screen, endpoint, or the existing
``value_score``/ranking/lineup-optimization paths — that is deliberately left
for separate follow-up work.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from modules import nfl_schedule, sleeper

# Positions with a real opponent-defense-strength-by-position signal (see
# ``team_defense_points_allowed_by_position``). Kickers are deliberately
# excluded from this set: "points allowed to kickers" isn't a meaningful
# defense-strength signal the way it is for QB/RB/WR/TE — a kicker's scoring
# chances are driven almost entirely by his *own* offense's ability to drive
# into scoring range, not by the opposing defense being specifically weak
# against kickers. Sleeper/nflverse also don't track anything like
# "points allowed to opposing kickers" as a real defensive stat.
OFFENSIVE_POSITIONS: tuple[str, ...] = ("QB", "RB", "WR", "TE")

# A kicker still gets a real weekly projection (see ``project_player_week``)
# built the same way as every other position — his own recency-weighted
# recent-scoring trend — just without an opponent-defense multiplier (see
# ``OFFENSIVE_POSITIONS`` above for why). ``PROJECTABLE_POSITIONS`` is the
# full set of positions ``project_player_week`` will produce a projection
# for; ``OFFENSIVE_POSITIONS`` stays narrower because it also gates the
# defense-strength-by-position aggregation, which only makes sense for
# skill-position offense.
KICKER_POSITION = "K"
PROJECTABLE_POSITIONS: tuple[str, ...] = OFFENSIVE_POSITIONS + (KICKER_POSITION,)

# --- Defense-strength-by-position tuning -----------------------------------
DEFENSE_MAX_WEEKS_BACK = 8
DEFENSE_HALF_LIFE_WEEKS = 3.0
MIN_GAMES_FOR_DEFENSE_TIER = 2

# --- Player recent-trend tuning ---------------------------------------------
PLAYER_MAX_WEEKS_BACK = 6
PLAYER_HALF_LIFE_WEEKS = 2.5
MIN_GAMES_FOR_FULL_CONFIDENCE = 4

# An opponent's defense-strength signal can only nudge a projection within
# this range of the player's own baseline — a thin defensive sample (or a
# genuinely extreme one) should never swing the number more than this.
_OPPONENT_MULTIPLIER_BOUNDS = (0.75, 1.25)

# Floor for the honest range so a single-game sample doesn't produce a
# suspiciously tight band.
_MIN_BAND_HALF_WIDTH = 2.5


def _recency_weight(weeks_ago: int, half_life_weeks: float) -> float:
    """Exponential recency weight — more recent weeks count more.

    ``weeks_ago`` of 0 is the most recent observation. Weight halves every
    ``half_life_weeks``.
    """

    if weeks_ago < 0:
        weeks_ago = 0
    half_life = max(0.1, float(half_life_weeks))
    return 0.5 ** (float(weeks_ago) / half_life)


def _weighted_mean(values_by_week: Dict[int, float], reference_week: int, half_life_weeks: float) -> Optional[float]:
    if not values_by_week:
        return None
    weight_sum = 0.0
    total = 0.0
    for week, value in values_by_week.items():
        weight = _recency_weight(reference_week - int(week), half_life_weeks)
        weight_sum += weight
        total += weight * float(value)
    if weight_sum <= 0:
        return None
    return total / weight_sum


def _stdev(values: List[float]) -> Optional[float]:
    n = len(values)
    if n < 2:
        return None
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    return variance ** 0.5


# ---------------------------------------------------------------------------
# Defense strength by position
# ---------------------------------------------------------------------------


def team_defense_points_allowed_by_position(
    season: int,
    *,
    upto_week: Optional[int] = None,
    weekly_stats: Optional[Dict[str, Dict[str, Any]]] = None,
    players: Optional[Dict[str, Any]] = None,
    max_weeks_back: int = DEFENSE_MAX_WEEKS_BACK,
    half_life_weeks: float = DEFENSE_HALF_LIFE_WEEKS,
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Real PPR fantasy points allowed by every team, broken out per offensive
    skill position, recency-weighted.

    Returns ``{team_code: {position: {"weighted_points_allowed_per_game",
    "simple_points_allowed_per_game", "games_sampled", "low_sample", "rank",
    "tier"}}}``. A team/position pair with zero sampled weeks is omitted
    entirely (never a fabricated 0). ``rank``/``tier`` (1 = toughest / "tough"
    | "average" | "weak") are computed only among teams with
    ``games_sampled >= MIN_GAMES_FOR_DEFENSE_TIER`` for that position — a
    team with a single sampled week gets a value but no rank/tier.

    ``weekly_stats``/``players`` may be injected (tests, or a caller that
    already has them in hand) to avoid a second fetch; both default to the
    real cached sources (``modules.sleeper``).
    """

    weekly_stats = weekly_stats if weekly_stats is not None else sleeper.get_season_player_stats(season=season)
    players = players if players is not None else sleeper.get_players()

    schedule_cache: Dict[str, Dict[int, str]] = {}

    def _week_to_opponent(team: str) -> Dict[int, str]:
        if team not in schedule_cache:
            rows = nfl_schedule.team_schedule(team, season)
            schedule_cache[team] = {
                int(row["week"]): str(row["opponent"])
                for row in rows
                if row.get("opponent")
            }
        return schedule_cache[team]

    # defense_team -> position -> week -> points allowed that week
    raw: Dict[str, Dict[str, Dict[int, float]]] = {}

    for player_id, record in (weekly_stats or {}).items():
        if not isinstance(record, dict):
            continue
        weekly_rows = record.get("weekly")
        if not weekly_rows:
            continue
        player = players.get(str(player_id)) or {}
        position = str(player.get("position") or "").strip().upper()
        team = player.get("team")
        if position not in OFFENSIVE_POSITIONS or not team:
            continue
        week_to_opponent = _week_to_opponent(str(team))
        if not week_to_opponent:
            continue
        for row in weekly_rows:
            if not isinstance(row, dict):
                continue
            week = row.get("week")
            points = row.get("fantasy_points_ppr")
            if week is None or points is None:
                continue
            week = int(week)
            if upto_week is not None and week > int(upto_week):
                continue
            opponent = week_to_opponent.get(week)
            if not opponent:
                continue
            position_map = raw.setdefault(opponent, {}).setdefault(position, {})
            position_map[week] = position_map.get(week, 0.0) + float(points)

    all_weeks = {
        week
        for position_map in raw.values()
        for week_map in position_map.values()
        for week in week_map
    }
    if upto_week is not None:
        reference_week = int(upto_week)
    else:
        reference_week = max(all_weeks) if all_weeks else 0

    results: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for defense_team, position_map in raw.items():
        results[defense_team] = {}
        for position, week_map in position_map.items():
            recent_weeks = {
                week: points
                for week, points in week_map.items()
                if 0 <= reference_week - week < max(1, int(max_weeks_back))
            }
            if not recent_weeks:
                continue
            weighted = _weighted_mean(recent_weeks, reference_week, half_life_weeks)
            if weighted is None:
                continue
            simple = sum(recent_weeks.values()) / len(recent_weeks)
            games_sampled = len(recent_weeks)
            results[defense_team][position] = {
                "weighted_points_allowed_per_game": round(weighted, 2),
                "simple_points_allowed_per_game": round(simple, 2),
                "games_sampled": games_sampled,
                "low_sample": games_sampled < MIN_GAMES_FOR_DEFENSE_TIER,
            }

    # Rank/tier per position, only among teams with enough sample.
    for position in OFFENSIVE_POSITIONS:
        eligible = [
            (team, entries[position]["weighted_points_allowed_per_game"])
            for team, entries in results.items()
            if position in entries and not entries[position]["low_sample"]
        ]
        if not eligible:
            continue
        ranked = sorted(eligible, key=lambda pair: pair[1])
        total = len(ranked)
        tough_cutoff = max(1, round(total / 3))
        weak_cutoff = total - max(1, round(total / 3))
        for index, (team, _value) in enumerate(ranked):
            rank = index + 1
            entry = results[team][position]
            entry["rank"] = rank
            if rank <= tough_cutoff:
                entry["tier"] = "tough"
            elif rank > weak_cutoff:
                entry["tier"] = "weak"
            else:
                entry["tier"] = "average"

    return results


def _league_average_points_allowed(
    defense_map: Dict[str, Dict[str, Dict[str, Any]]], position: str
) -> Optional[float]:
    values = [
        entries[position]["weighted_points_allowed_per_game"]
        for entries in defense_map.values()
        if position in entries and not entries[position].get("low_sample")
    ]
    if not values:
        return None
    return sum(values) / len(values)


def _opponent_multiplier(
    defense_map: Dict[str, Dict[str, Dict[str, Any]]],
    opponent: str,
    position: str,
) -> tuple[float, bool]:
    """Multiplier applied to a player's baseline for this specific matchup.

    Returns ``(multiplier, has_reliable_signal)``. Neutral (1.0, False) when
    there is no usable defense-strength data for this opponent/position —
    an unknown matchup should never be treated as "average" with false
    confidence, but it also shouldn't block a projection outright.
    """

    entry = (defense_map.get(opponent) or {}).get(position)
    league_avg = _league_average_points_allowed(defense_map, position)
    if not entry or league_avg is None or league_avg <= 0 or entry.get("low_sample"):
        return 1.0, False
    raw_multiplier = entry["weighted_points_allowed_per_game"] / league_avg
    low, high = _OPPONENT_MULTIPLIER_BOUNDS
    return max(low, min(high, raw_multiplier)), True


# ---------------------------------------------------------------------------
# Player recent-trend
# ---------------------------------------------------------------------------


def _player_recent_trend(
    weekly_rows: List[Dict[str, Any]],
    *,
    upto_week: Optional[int],
    max_weeks_back: int = PLAYER_MAX_WEEKS_BACK,
    half_life_weeks: float = PLAYER_HALF_LIFE_WEEKS,
) -> Optional[Dict[str, Any]]:
    usable = [
        row
        for row in (weekly_rows or [])
        if isinstance(row, dict)
        and row.get("week") is not None
        and row.get("fantasy_points_ppr") is not None
        and (upto_week is None or int(row["week"]) <= int(upto_week))
    ]
    if not usable:
        return None
    usable.sort(key=lambda row: int(row["week"]))
    reference_week = int(upto_week) if upto_week is not None else int(usable[-1]["week"])
    recent = [
        row
        for row in usable
        if 0 <= reference_week - int(row["week"]) < max(1, int(max_weeks_back))
    ]
    if not recent:
        return None
    values_by_week = {int(row["week"]): float(row["fantasy_points_ppr"]) for row in recent}
    weighted = _weighted_mean(values_by_week, reference_week, half_life_weeks)
    if weighted is None:
        return None
    points = list(values_by_week.values())
    return {
        "weighted_avg_ppr": weighted,
        "simple_avg_ppr": sum(points) / len(points),
        "games_played": len(points),
        "stdev_ppr": _stdev(points),
        "weeks_used": sorted(values_by_week.keys()),
    }


def _confidence_label(games_played: int, defense_has_signal: bool) -> str:
    if games_played >= MIN_GAMES_FOR_FULL_CONFIDENCE and defense_has_signal:
        return "high"
    if games_played >= 2:
        return "medium"
    return "low"


def _band_half_width(trend: Dict[str, Any], *, defense_has_signal: bool) -> float:
    games_played = trend["games_played"]
    stdev = trend.get("stdev_ppr")
    if stdev is not None:
        base = stdev
    else:
        # Single-game sample: no variance to measure — fall back to a
        # fraction of the observed average rather than pretending the one
        # data point is exact.
        base = max(trend["weighted_avg_ppr"] * 0.5, _MIN_BAND_HALF_WIDTH)

    # Small-sample penalty: widen further the fewer games we have to go on.
    if games_played < MIN_GAMES_FOR_FULL_CONFIDENCE:
        shortfall = MIN_GAMES_FOR_FULL_CONFIDENCE - games_played
        base *= 1.0 + (0.25 * shortfall)

    if not defense_has_signal:
        base *= 1.15

    return max(base, _MIN_BAND_HALF_WIDTH)


# ---------------------------------------------------------------------------
# Public projection entry point
# ---------------------------------------------------------------------------


def project_player_week(
    player_id: str,
    week: int,
    season: Optional[int] = None,
    *,
    players: Optional[Dict[str, Any]] = None,
    player_weekly_rows: Optional[List[Dict[str, Any]]] = None,
    defense_strength: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """A first-pass real weekly point projection for one player, one week.

    Always returns a dict with a ``status`` key:

    - ``"ok"`` — a projection was produced. Carries ``point_estimate``,
      ``low``, ``high`` (all PPR points), ``confidence`` ("low"/"medium"/
      "high"), ``opponent``, and a ``basis`` dict explaining the inputs.
    - ``"bye_week"`` — the player's team has no game that week. No point
      estimate is returned (never a fabricated 0).
    - ``"no_opponent"`` / ``"no_schedule_data"`` — the schedule has no game
      on record for that team/week (also no fabricated 0).
    - ``"insufficient_player_data"`` — no usable recent-week production to
      build a trend from (new player, or none played the relevant weeks
      yet). No projection is fabricated from nothing.
    - ``"unsupported_position"`` — position isn't one of QB/RB/WR/TE/K (no
      recent-scoring-trend projection is attempted for DEF/IDP). A kicker
      (K) still gets a real ``"ok"`` projection from his own recent-scoring
      trend; he just never gets an opponent-defense-strength multiplier
      (``basis.opponent_defense_has_signal`` is always ``False`` for K — see
      ``OFFENSIVE_POSITIONS``'s docstring comment for why), so his
      confidence can reach at most "medium", never "high".
    - ``"unknown_player"`` / ``"no_team"`` — player not found, or has no
      current team (free agent/retired) so no schedule applies.

    ``season`` defaults to the canonical active Sleeper season
    (``modules.sleeper.default_player_stats_season``). ``players``,
    ``player_weekly_rows``, and ``defense_strength`` may be injected (tests,
    or a caller batching many players who already has these in hand); each
    otherwise defaults to the real cached source.
    """

    player_id = str(player_id)
    season = int(season) if season is not None else sleeper.default_player_stats_season()
    week = int(week)

    players = players if players is not None else sleeper.get_players()
    player = players.get(player_id)
    if not player:
        return {"status": "unknown_player", "player_id": player_id}

    position = str(player.get("position") or "").strip().upper()
    team = player.get("team")

    if position not in PROJECTABLE_POSITIONS:
        return {"status": "unsupported_position", "player_id": player_id, "position": position or None}

    if not team:
        return {"status": "no_team", "player_id": player_id, "position": position}

    schedule = nfl_schedule.team_schedule(str(team), season)
    matchup = next((row for row in schedule if int(row["week"]) == week), None)
    if matchup is None:
        return {
            "status": "no_schedule_data",
            "player_id": player_id,
            "position": position,
            "week": week,
            "season": season,
        }
    if matchup.get("bye"):
        return {
            "status": "bye_week",
            "player_id": player_id,
            "position": position,
            "week": week,
            "season": season,
        }
    opponent = matchup.get("opponent")
    if not opponent:
        return {
            "status": "no_opponent",
            "player_id": player_id,
            "position": position,
            "week": week,
            "season": season,
        }

    weekly_rows = (
        player_weekly_rows
        if player_weekly_rows is not None
        else sleeper.cached_season_player_weekly(player_id, season)
    )
    trend = _player_recent_trend(weekly_rows, upto_week=week - 1)
    if trend is None:
        return {
            "status": "insufficient_player_data",
            "player_id": player_id,
            "position": position,
            "week": week,
            "season": season,
            "opponent": opponent,
        }

    defense_strength = (
        defense_strength
        if defense_strength is not None
        else team_defense_points_allowed_by_position(season, upto_week=week - 1)
    )
    multiplier, defense_has_signal = _opponent_multiplier(defense_strength, str(opponent), position)

    point_estimate = trend["weighted_avg_ppr"] * multiplier
    half_width = _band_half_width(trend, defense_has_signal=defense_has_signal)
    low = max(0.0, point_estimate - half_width)
    high = max(low, point_estimate + half_width)
    confidence = _confidence_label(trend["games_played"], defense_has_signal)

    defense_entry = (defense_strength.get(str(opponent)) or {}).get(position)

    return {
        "status": "ok",
        "player_id": player_id,
        "position": position,
        "team": str(team),
        "week": week,
        "season": season,
        "opponent": str(opponent),
        "point_estimate": round(point_estimate, 1),
        "low": round(low, 1),
        "high": round(high, 1),
        "confidence": confidence,
        "basis": {
            "recent_games_played": trend["games_played"],
            "recent_weeks_used": trend["weeks_used"],
            "recent_weighted_avg_ppr": round(trend["weighted_avg_ppr"], 2),
            "opponent_multiplier": round(multiplier, 3),
            "opponent_defense_has_signal": defense_has_signal,
            "opponent_defense_games_sampled": (defense_entry or {}).get("games_sampled", 0),
            "opponent_defense_tier": (defense_entry or {}).get("tier"),
        },
    }
