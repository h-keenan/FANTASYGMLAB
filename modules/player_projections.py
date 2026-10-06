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
3. ``team_qb_quality_by_team`` / ``modules.rankings.team_starting_qb_quality``
   — closes a real gap a read-only projection audit flagged: a WR/TE's
   projection above had zero awareness of its own team's starting QB
   quality/situation, even though a WR's ceiling is capped by how good his
   own team's passing offense actually is. For WR/TE only (never QB/RB —
   see ``TEAM_QB_QUALITY_POSITIONS``), the point estimate is additionally
   nudged by the team's starting QB's existing usage-quality score
   relative to league average, clamped to a narrower, more conservative
   range than the opponent-defense multiplier (see
   ``_TEAM_QB_QUALITY_MULTIPLIER_BOUNDS`` — this signal is newer and less
   validated than the points-allowed-based opponent signal). Deliberately
   scoped to this weekly projection only; never wired into ``value_score``
   or ``modules.rankings``'s composite valuation — a short-term QB injury
   and a genuine long-term downgrade need different guardrails than a
   single-week estimate does, and that disambiguation is explicit future
   follow-up work, not part of this fix.

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
- The team-QB-quality multiplier is clamped even tighter than the opponent
  multiplier (see ``_TEAM_QB_QUALITY_MULTIPLIER_BOUNDS``) for the same
  "small/noisy sample shouldn't swing the number" reason, and additionally
  because this signal cannot yet tell a short-term QB injury apart from a
  genuine long-term downgrade — a conservative clamp limits the damage
  either way.
- ``basis.team_qb_situation_changed_recently`` (WR/TE only) is a best-effort
  derived flag, not new tracked state: it reads back "who started" from
  each QB's own real weekly pass-attempt volume (Sleeper's depth chart is
  only ever a current snapshot, so there is no stored history of past
  starters to compare against). ``None`` when there isn't at least two past
  weeks of QB attempt data for the team to compare.
- A near-zero-usage player's own recent weekly PPR rows can genuinely be
  negative (a catch behind the line of scrimmage, a lost fumble), so
  ``_player_recent_trend``'s weighted average — and therefore the raw,
  pre-floor point estimate — can legitimately come out negative. That is
  not a bug; it is an honest read of a real bad stretch. ``project_player_week``
  still floors the *displayed* ``point_estimate``/``low``/``high`` at 0.0
  (matching the convention most fantasy platforms use: "less than zero
  points expected" is not a usefully different, or honestly communicable,
  forecast from "approximately zero points expected"), while leaving the
  real unfloored trend visible in ``basis.recent_weighted_avg_ppr`` and
  flagging the floor via ``basis.point_estimate_floored``. A near-identical
  small estimate repeating across several consecutive future weeks for a
  player who hasn't played a new game is *also* not a bug by itself: per
  ``_most_recent_played_week``'s "as-of" anchoring (the fix in PR #868),
  the recency window correctly stays anchored on his real last game for
  every future week projected, so the baseline trend is genuinely stable
  until he plays again — only the bounded opponent-defense multiplier
  (``_OPPONENT_MULTIPLIER_BOUNDS``) can move the number week to week, which
  is why it was observed to vary only slightly (e.g. -0.7/-0.7/-0.6/-0.6/
  -0.7) rather than being perfectly identical or wildly different.

Update (the "separate follow-up work" below happened): ``project_player_week``
is wired into the weekly-context consumers this was always meant for —
``services/mobile_api_service.py``'s ``GET /v1/players/{id}/schedule`` (each
remaining week) and the Matchup screen's REAL current-week lineup rows (see
``_weekly_projection_for_player``/``_project_real_starter_row`` there), both
mobile and web (``modules.web_matchup_ui``). It is still deliberately NOT
wired into ``value_score``/``dynasty_score``/rankings/trade-value/waiver-
suggestion, nor into the Matchup/My Team screens' SUGGESTED (season-value)
lineup recommendation or ``modules.team_eval.suggest_optimal_lineup``'s own
slot-assignment ranking — a single week's matchup-dependent point estimate
has no business swinging a long-term dynasty asset value or which player
this app recommends rostering as a starter, which is a season-long-value
question, not a this-week's-matchup one. That split stays deliberate, not
an oversight.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import pandas as pd

from modules import nfl_schedule, rankings, redis_cache, sleeper

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

# Positions whose weekly projection is nudged by their own team's starting
# QB passing-offense tier (see ``team_starting_qb_quality`` /
# ``_team_qb_quality_multiplier``). QB and RB are deliberately excluded: a
# QB's own projection has nothing to do with "the team's starting QB" (he
# IS the team's starting QB — this would be circular), and an RB's
# workload/scoring is driven far more by his own role/volume than by how
# good the team's passing offense is, so folding this signal into RB would
# be speculative. WR/TE scoring is much more directly downstream of the
# team's passing-game quality (targets only matter if the QB can hit them).
TEAM_QB_QUALITY_POSITIONS: tuple[str, ...] = ("WR", "TE")

# A team's starting-QB-quality signal can only nudge a WR/TE projection
# within this range — deliberately tighter than ``_OPPONENT_MULTIPLIER_BOUNDS``
# (0.75-1.25). This signal is less validated than the opponent-defense one
# (it is brand new, derived from a 0..1 usage-quality heuristic rather than
# real points allowed) and QB situations can change suddenly (injury,
# benching) in ways this first pass does not try to disambiguate from a
# genuine long-term downgrade — so a thin or noisy read here must move the
# projection even less than a thin defensive sample would.
_TEAM_QB_QUALITY_MULTIPLIER_BOUNDS = (0.85, 1.15)

# A league-average team-QB-quality baseline (the denominator of the ratio
# below, same pattern as ``_league_average_points_allowed``) needs at least
# this many teams with a usable quality score to be meaningful — with only
# one team sampled, "average" is just that one team's own score, which
# would always normalize to a 1.0 ratio and silently masquerade as a real
# signal.
_MIN_TEAMS_FOR_QB_QUALITY_LEAGUE_AVERAGE = 2

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


def _team_defense_points_allowed_by_position_uncached(
    season: int,
    *,
    upto_week: Optional[int] = None,
    weekly_stats: Optional[Dict[str, Dict[str, Any]]] = None,
    players: Optional[Dict[str, Any]] = None,
    max_weeks_back: int = DEFENSE_MAX_WEEKS_BACK,
    half_life_weeks: float = DEFENSE_HALF_LIFE_WEEKS,
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Real work behind ``team_defense_points_allowed_by_position`` — see
    that function's docstring for the contract. Split out so the cached
    front door below can wrap just the expensive aggregation in
    ``redis_single_flight_cache`` without duplicating it."""

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


# Walks every player's weekly stat rows for the whole season to build the
# per-team/per-position recency-weighted map above — real work, and (like
# modules.trade_hub_engine/modules.playoff_simulator/modules.league_rankings)
# identical output for every caller hitting the same (season, upto_week)
# within the window below, yet until now it was recomputed from scratch on
# EVERY call — including services/mobile_api_service.py's hot
# GET /v1/players/{player_id}/schedule path, which calls this once per
# request. Same live-time-bucket idiom those three already use for their
# own Redis caches (see docker-compose.yml's mobile-api comment for the
# full "why": one GIL per uvicorn worker means one CPU-heavy request here
# could otherwise stall every other concurrent request on that worker).
DEFENSE_STRENGTH_TTL_SECONDS = 30 * 60


def _defense_strength_cache_bucket() -> int:
    return int(time.time() // DEFENSE_STRENGTH_TTL_SECONDS)


# Redis-backed single-flight + cache (modules.redis_cache.redis_single_flight_cache)
# — same pattern, and same reason, as modules.trade_hub_engine's/
# modules.playoff_simulator's/modules.league_rankings's own caches: without
# a single-flight guard, N concurrent requests that all miss the same
# (season, upto_week, max_weeks_back, half_life_weeks, bucket) key before
# the first one finishes would each independently redo the full
# season-long aggregation instead of sharing one.
#
# ``weekly_stats``/``players`` are deliberately NOT part of the cache key
# (and never touch Redis — only the small aggregated result does): both
# default to, and in practice always resolve to, modules.sleeper's own
# already-cached season stats/players snapshot, so every real caller for
# the same (season, upto_week) within this TTL window is aggregating the
# same underlying data regardless of which one happened to fetch it (see
# ``team_defense_points_allowed_by_position``'s docstring). A caller that
# injects deliberately different data (this module's own tests) still gets
# a correct, freshly-computed result keyed off the same tuple, because
# each test run starts with its own empty fakeredis instance (see
# tests/conftest.py) — there is never a same-process collision between two
# different injected-data calls sharing a cache key within one test.
_DEFENSE_STRENGTH_LOCK_TIMEOUT_SECONDS = 15.0


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

    Cached front door — see ``DEFENSE_STRENGTH_TTL_SECONDS``'s comment
    above and ``modules.redis_cache.redis_single_flight_cache`` for the
    shared caching mechanics (also used by modules.trade_hub_engine,
    modules.playoff_simulator, and modules.league_rankings). Single-flight
    + cache, shared across every mobile-api worker via Redis.
    """

    key = (
        season,
        upto_week,
        max_weeks_back,
        half_life_weeks,
        _defense_strength_cache_bucket(),
    )
    cache_key = redis_cache.build_cache_key("team_defense_points_allowed_by_position", *key)
    return redis_cache.redis_single_flight_cache(
        cache_key=cache_key,
        ttl_seconds=DEFENSE_STRENGTH_TTL_SECONDS,
        compute=lambda: _team_defense_points_allowed_by_position_uncached(
            season,
            upto_week=upto_week,
            weekly_stats=weekly_stats,
            players=players,
            max_weeks_back=max_weeks_back,
            half_life_weeks=half_life_weeks,
        ),
        lock_timeout_seconds=_DEFENSE_STRENGTH_LOCK_TIMEOUT_SECONDS,
    )


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
# Team starting-QB quality (WR/TE only — see TEAM_QB_QUALITY_POSITIONS)
# ---------------------------------------------------------------------------
#
# A gap the read-only projection audit flagged: a WR/TE's weekly projection
# above only ever looks at the player's own recent trend and the opponent's
# defense-by-position tier — it has zero awareness of its OWN team's
# starting QB quality/situation. A great WR stuck with a backup-caliber QB
# (or who just lost his starter to injury) should project a little lower
# than the same WR's raw recent trend implies; a WR who just inherited an
# upgrade at QB should project a little higher. This section builds that
# signal and ``_team_qb_quality_multiplier`` below turns it into a bounded
# nudge, following the exact same "ratio to league average, then clamp"
# shape as ``_opponent_multiplier``/``_league_average_points_allowed`` above.
#
# Deliberately scoped to the weekly projection only (never value_score or
# modules.rankings's composite valuation) — per the audit, a short-term QB
# injury and a genuine long-term downgrade need different guardrails than a
# single-week point estimate does, and disambiguating those is explicit
# future follow-up work, not part of this fix.


def _team_qb_quality_pool_frame(
    players: Dict[str, Any],
    weekly_stats: Dict[str, Dict[str, Any]],
) -> pd.DataFrame:
    """A minimal QB-only frame with exactly the columns
    ``modules.rankings.team_starting_qb_quality`` needs (position, team,
    depth_chart_position, depth_chart_order, pass_attempts, games_played,
    rushing_yards) — built from the same raw sources
    (``modules.sleeper.get_players`` / ``get_season_player_stats``) this
    module already uses elsewhere, not ``modules.rankings.load_players``/
    ``build_players_table`` (real DB I/O plus the full composite-valuation
    pipeline — far more than this signal needs, and exactly the
    rankings/value_score machinery this fix is scoped to stay out of).
    """

    rows: List[Dict[str, Any]] = []
    for player_id, player in (players or {}).items():
        if not isinstance(player, dict):
            continue
        if str(player.get("position") or "").strip().upper() != "QB":
            continue
        team = player.get("team")
        if not team:
            continue
        stats = (weekly_stats or {}).get(str(player_id))
        stats = stats if isinstance(stats, dict) else {}
        rows.append(
            {
                "player_id": str(player_id),
                "position": "QB",
                "team": str(team),
                "depth_chart_position": player.get("depth_chart_position"),
                "depth_chart_order": player.get("depth_chart_order"),
                "pass_attempts": stats.get("pass_attempts"),
                "games_played": stats.get("games_played"),
                "rushing_yards": stats.get("rushing_yards"),
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "player_id",
            "position",
            "team",
            "depth_chart_position",
            "depth_chart_order",
            "pass_attempts",
            "games_played",
            "rushing_yards",
        ],
    )


def _team_qb_quality_by_team_uncached(
    season: int,
    *,
    weekly_stats: Optional[Dict[str, Dict[str, Any]]] = None,
    players: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Real work behind ``team_qb_quality_by_team`` — see that function's
    docstring for the contract."""

    weekly_stats = weekly_stats if weekly_stats is not None else sleeper.get_season_player_stats(season=season)
    players = players if players is not None else sleeper.get_players()

    qb_pool = _team_qb_quality_pool_frame(players, weekly_stats)
    if qb_pool.empty:
        return {}

    teams = sorted({str(team) for team in qb_pool["team"].dropna().tolist()})
    results: Dict[str, Dict[str, Any]] = {}
    for team in teams:
        quality, info = rankings.team_starting_qb_quality(team, qb_pool)
        results[team] = {"quality": quality, **info}
    return results


# Same live-time-bucket cadence as DEFENSE_STRENGTH_TTL_SECONDS above, for
# the same reason: this aggregates across every QB in the league, so it
# should be computed at most once per bucket window cluster-wide, not once
# per WR/TE projected.
TEAM_QB_QUALITY_TTL_SECONDS = 30 * 60


def _team_qb_quality_cache_bucket() -> int:
    return int(time.time() // TEAM_QB_QUALITY_TTL_SECONDS)


_TEAM_QB_QUALITY_LOCK_TIMEOUT_SECONDS = 15.0


def team_qb_quality_by_team(
    season: int,
    *,
    weekly_stats: Optional[Dict[str, Dict[str, Any]]] = None,
    players: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Every team's starting-QB-quality signal (see
    ``modules.rankings.team_starting_qb_quality``), keyed by team code.

    Returns ``{team: {"quality": float | None, "qb_count", "selected_player_id",
    "selection_method", "pass_att_pg", "quality_detail"}}`` — ``info`` from
    ``team_starting_qb_quality`` merged with its own ``quality`` score. A
    team with no QB on the roster at all is simply omitted.

    ``weekly_stats``/``players`` may be injected (tests, or a caller who
    already has them in hand); both default to the real cached sources
    (``modules.sleeper``), same as ``team_defense_points_allowed_by_position``.

    Cached front door (``TEAM_QB_QUALITY_TTL_SECONDS``/
    ``redis_cache.redis_single_flight_cache``) — same single-flight + TTL
    bucket mechanics as ``team_defense_points_allowed_by_position`` above,
    for the same reason: an uncached per-request rebuild would redo a
    league-wide scan on every WR/TE projected.
    """

    cache_key = redis_cache.build_cache_key(
        "team_qb_quality_by_team", season, _team_qb_quality_cache_bucket()
    )
    return redis_cache.redis_single_flight_cache(
        cache_key=cache_key,
        ttl_seconds=TEAM_QB_QUALITY_TTL_SECONDS,
        compute=lambda: _team_qb_quality_by_team_uncached(
            season, weekly_stats=weekly_stats, players=players
        ),
        lock_timeout_seconds=_TEAM_QB_QUALITY_LOCK_TIMEOUT_SECONDS,
    )


def _team_qb_quality_multiplier(
    team_qb_quality_map: Dict[str, Dict[str, Any]],
    team: str,
) -> tuple[float, bool]:
    """Multiplier applied to a WR/TE's baseline from their own team's
    starting-QB-quality tier, relative to league average.

    Returns ``(multiplier, has_reliable_signal)`` — neutral (1.0, False)
    when there's no usable quality score for ``team``, or fewer than
    ``_MIN_TEAMS_FOR_QB_QUALITY_LEAGUE_AVERAGE`` teams have one (so "league
    average" would not be meaningful) — same "never fabricate a signal from
    nothing" contract as ``_opponent_multiplier``.
    """

    entry = (team_qb_quality_map or {}).get(str(team))
    quality = entry.get("quality") if entry else None
    if quality is None:
        return 1.0, False

    qualities = [
        v.get("quality")
        for v in (team_qb_quality_map or {}).values()
        if v.get("quality") is not None
    ]
    if len(qualities) < _MIN_TEAMS_FOR_QB_QUALITY_LEAGUE_AVERAGE:
        return 1.0, False
    league_avg = sum(qualities) / len(qualities)
    if league_avg <= 0:
        return 1.0, False

    raw_multiplier = float(quality) / league_avg
    low, high = _TEAM_QB_QUALITY_MULTIPLIER_BOUNDS
    return max(low, min(high, raw_multiplier)), True


def _team_starting_qb_changed_recently(
    team: str,
    *,
    before_week: int,
    weekly_stats: Dict[str, Dict[str, Any]],
    players: Dict[str, Any],
) -> Optional[bool]:
    """Secondary/optional signal the audit also flagged: did this team's
    starting QB (by weekly pass-attempt plurality among its own QBs) change
    between the two most recent weeks with recorded QB data, strictly
    before ``before_week``? Built entirely from weekly pass-attempt rows
    this module already has in hand for every QB (no new state tracking —
    Sleeper's depth chart is only ever a current snapshot, so "who started
    last week" is read back out of real per-week pass-attempt volume
    instead, the same signal weekly fantasy sites use to infer a change in
    starter).

    Returns ``None`` (never a fabricated True/False) when there are fewer
    than two past weeks of QB pass-attempt data for this team, or either of
    the two most recent weeks has no attempts recorded for any of its QBs.
    """

    by_week: Dict[int, Dict[str, float]] = {}
    for player_id, player in (players or {}).items():
        if not isinstance(player, dict):
            continue
        if str(player.get("position") or "").strip().upper() != "QB":
            continue
        if str(player.get("team") or "") != str(team):
            continue
        record = (weekly_stats or {}).get(str(player_id))
        weekly_rows = record.get("weekly") if isinstance(record, dict) else None
        for row in weekly_rows or []:
            if not isinstance(row, dict):
                continue
            week = row.get("week")
            attempts = row.get("pass_attempts")
            if week is None or attempts is None or int(week) >= int(before_week):
                continue
            by_week.setdefault(int(week), {})[str(player_id)] = float(attempts)

    past_weeks = sorted(by_week.keys())
    if len(past_weeks) < 2:
        return None

    def _leader(week: int) -> Optional[str]:
        attempts_by_qb = by_week.get(week) or {}
        if not attempts_by_qb:
            return None
        return max(attempts_by_qb.items(), key=lambda pair: pair[1])[0]

    last_leader = _leader(past_weeks[-1])
    prior_leader = _leader(past_weeks[-2])
    if last_leader is None or prior_leader is None:
        return None
    return last_leader != prior_leader


# ---------------------------------------------------------------------------
# Player recent-trend
# ---------------------------------------------------------------------------


def _most_recent_played_week(weekly_rows: List[Dict[str, Any]], *, before_week: int) -> int:
    """The real "as-of" week to anchor a player's recency window on.

    This is the latest week actually reflected in ``weekly_rows`` (strictly
    before ``before_week``, the week being projected) — NOT
    ``before_week - 1`` itself. Anchoring the lookback window on the week
    being projected (as this module used to do) silently ages games out of
    the window purely because a *later* week is being projected, even
    though no additional real time — and no additional games — has
    actually passed since those games were played. A player last seen in
    week 3 must get the exact same recency-weighted trend whether he's
    being projected for week 4 or week 9; only the opponent (and its
    matchup multiplier) should vary across a loop like
    ``services.mobile_api_service.get_player_schedule``'s per-remaining-
    week projection loop. Falls back to ``before_week - 1`` when there is
    no usable row at all, so ``_player_recent_trend`` still returns
    ``None`` (and ``project_player_week`` still reports
    ``"insufficient_player_data"``) exactly as before for a player with no
    recorded games.
    """

    played_weeks = [
        int(row["week"])
        for row in (weekly_rows or [])
        if isinstance(row, dict)
        and row.get("week") is not None
        and row.get("fantasy_points_ppr") is not None
        and int(row["week"]) < int(before_week)
    ]
    return max(played_weeks) if played_weeks else int(before_week) - 1


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
    team_qb_quality: Optional[Dict[str, Dict[str, Any]]] = None,
    weekly_stats: Optional[Dict[str, Dict[str, Any]]] = None,
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

    For WR/TE only (see ``TEAM_QB_QUALITY_POSITIONS``), the point estimate
    is additionally nudged by the player's own team's starting-QB-quality
    tier relative to league average (``basis.team_qb_quality_multiplier``,
    bounded by ``_TEAM_QB_QUALITY_MULTIPLIER_BOUNDS`` — see
    ``_team_qb_quality_multiplier``/``modules.rankings.team_starting_qb_quality``).
    QB and RB projections are completely unaffected by this signal — it is
    never computed, let alone applied, for those positions.

    ``season`` defaults to the canonical active Sleeper season
    (``modules.sleeper.default_player_stats_season``). ``players``,
    ``player_weekly_rows``, ``defense_strength``, ``team_qb_quality``, and
    ``weekly_stats`` may be injected (tests, or a caller batching many
    players who already has these in hand); each otherwise defaults to the
    real cached source. ``weekly_stats`` is only ever read for WR/TE (to
    default-compute ``team_qb_quality`` and the optional
    ``team_qb_situation_changed_recently`` basis flag) — it is never
    fetched at all for QB/RB/K.
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
    # Anchor the recency window on the real "as-of" week — the latest week
    # actually reflected in this player's own weekly rows — not on
    # ``week - 1``, the target week being projected. Otherwise, projecting
    # far enough ahead of a player's last real game silently ages real
    # games out of the lookback window (or drops the trend to
    # "insufficient_player_data" entirely) even though zero real time has
    # passed since those games. See ``_most_recent_played_week``.
    as_of_week = _most_recent_played_week(weekly_rows, before_week=week)
    trend = _player_recent_trend(weekly_rows, upto_week=as_of_week)
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

    # Team starting-QB-quality nudge — WR/TE only (see
    # TEAM_QB_QUALITY_POSITIONS's docstring comment for why QB/RB are
    # excluded). Never even computed for other positions, so QB/RB/K
    # projections are completely unaffected — not just neutral, but
    # literally untouched by any of this code.
    team_qb_quality_multiplier = 1.0
    team_qb_quality_has_signal = False
    team_qb_quality_score: Optional[float] = None
    team_qb_quality_selected_player_id: Optional[str] = None
    team_qb_situation_changed_recently: Optional[bool] = None
    if position in TEAM_QB_QUALITY_POSITIONS:
        resolved_weekly_stats = (
            weekly_stats if weekly_stats is not None else sleeper.get_season_player_stats(season=season)
        )
        team_qb_quality_map = (
            team_qb_quality
            if team_qb_quality is not None
            else team_qb_quality_by_team(season, weekly_stats=resolved_weekly_stats, players=players)
        )
        team_qb_quality_multiplier, team_qb_quality_has_signal = _team_qb_quality_multiplier(
            team_qb_quality_map, str(team)
        )
        team_entry = (team_qb_quality_map or {}).get(str(team))
        if team_entry:
            team_qb_quality_score = team_entry.get("quality")
            team_qb_quality_selected_player_id = team_entry.get("selected_player_id")
        team_qb_situation_changed_recently = _team_starting_qb_changed_recently(
            str(team), before_week=week, weekly_stats=resolved_weekly_stats, players=players
        )

    # A player's real recent-week PPR rows can be genuinely negative — a
    # catch behind the line of scrimmage, a lost fumble — so
    # ``trend["weighted_avg_ppr"]`` (and therefore the raw multiplied
    # estimate below) is not itself a bug when it lands below zero; it is
    # an honest reflection of a real bad recent stretch. See Chimere Dike
    # (2026 WR, TEN): weeks 1 and 3 both carry a real negative
    # ``fantasy_points_ppr`` row (a negative-yardage catch each time), so
    # his recency-weighted average is genuinely negative on the real data.
    #
    # But a *forward-looking projection* is a different claim than a
    # historical fact, and every mainstream fantasy platform floors a
    # projection at 0 — "we expect less than zero points" isn't a
    # meaningfully different (or honestly communicable) forecast from "we
    # expect approximately zero points," and a precise-looking negative
    # decimal (e.g. "-0.7") reads as false confidence about an outcome that
    # is actually just "basically no usage expected." Floor the *displayed*
    # estimate/range here, at the output layer — never mutate ``trend``
    # itself (preserved below in ``basis.recent_weighted_avg_ppr`` so the
    # real underlying negative data stays visible/auditable).
    raw_point_estimate = trend["weighted_avg_ppr"] * multiplier * team_qb_quality_multiplier
    point_estimate = max(0.0, raw_point_estimate)
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
            "team_qb_quality_multiplier": round(team_qb_quality_multiplier, 3),
            "team_qb_quality_has_signal": team_qb_quality_has_signal,
            "team_qb_quality_score": (
                round(team_qb_quality_score, 3) if team_qb_quality_score is not None else None
            ),
            "team_starting_qb_player_id": team_qb_quality_selected_player_id,
            "team_qb_situation_changed_recently": team_qb_situation_changed_recently,
            # True when the real recency-weighted trend × opponent
            # multiplier × team-QB-quality multiplier was negative and got
            # floored to 0 for display — lets a caller distinguish
            # "genuinely projected ~0" from "recent production was actually
            # negative" without re-deriving it from recent_weighted_avg_ppr
            # itself.
            "point_estimate_floored": raw_point_estimate < 0.0,
        },
    }
