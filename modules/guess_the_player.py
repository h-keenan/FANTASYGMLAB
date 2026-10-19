""""Whose stats are these?" Dashboard mini-game — real player selection,
real stat line, real multiple-choice distractors.

coridian_'s confirmed spec (2026-10-19, via Discord): a dismissible
Dashboard card shows one real player's real recent week (stats only, name/
photo hidden), the user picks from 3-4 real name options, then the reveal
shows whether they were right. Two hard requirements this module exists to
satisfy:

1. The featured week must be a genuine statistical outlier for THAT PLAYER
   (a normally low-usage player's breakout week) — not merely a star
   player's good week. See ``find_surprise_candidates``.
2. The wrong options must be real, plausible, same-position players with a
   similar normal production level — a genuine guess, not a giveaway. See
   ``build_distractor_options``.

Data source note: modules.sleeper's weekly cache (``get_season_player_stats``
's ``weekly`` rows) retains ``targets``/``receptions``/``rush_attempts``/
``pass_attempts``/``fantasy_points_ppr``/``snap_share``/``games_played`` per
week — real Sleeper box-score fields, but NOT per-week yards/TDs (those are
only ever summed into the season aggregate; see modules/sleeper.py's
``PLAYER_STATS_SUM_FIELDS`` vs ``WEEKLY_RETAIN_FIELD_MAP``). The stat line
this module builds uses only what is genuinely tracked per week — never a
fabricated yards/TD figure.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any, Mapping, Sequence

import pandas as pd

from modules import player_tier_identity, rankings

# A breakout week needs a real "normal" to be surprising relative to — same
# spirit as rankings.recency_trend_display's own >= 4 usable games gate, so
# this module's notion of "usable history" never disagrees with the one the
# rest of the app already shows for "trending" usage.
MIN_USABLE_WEEKS = 4

# The featured week must be a real, absolute-terms big week (not just
# "relatively high for a player who scored near zero all year") ...
MIN_FEATURED_FANTASY_POINTS_PPR = 15.0

# ... AND meaningfully higher than that same player's own other-week
# average this season (the actual "surprise" signal).
MIN_SURPRISE_RATIO = 1.75

# Bottom three of the seven-tier canonical ladder (modules.player_tier_identity) —
# "normally low-profile" per coridian_'s own example ("a low-usage/bench-tier
# player who had a huge week"). Starter and above are excluded so a star
# player's normal great week can never qualify.
LOW_PROFILE_TIER_IDS = frozenset({"contributor", "committee_role", "depth_developmental"})

# (source weekly field, display label) — only real per-week fields, in the
# order a box score usually reads. Omitted from a player's line whenever the
# field is absent/zero for that week (e.g. a WR's pass_attempts).
STAT_LINE_FIELDS: tuple[tuple[str, str], ...] = (
    ("pass_attempts", "Pass Attempts"),
    ("rush_attempts", "Rush Attempts"),
    ("targets", "Targets"),
    ("receptions", "Receptions"),
)

DISTRACTOR_COUNT = 3  # + the real answer = 4 multiple-choice options total


def _is_low_profile(player_row: Mapping[str, Any]) -> bool:
    identity = player_tier_identity.resolve_player_tier_identity(player_row)
    return identity.tier_id in LOW_PROFILE_TIER_IDS


def usable_weeks(weekly: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    """Real participation weeks with a usable fantasy-points reading —
    reuses rankings.week_observation_usable so "did this player actually
    play" is decided exactly once, the same way everywhere in the app."""

    if not weekly:
        return []
    return [
        dict(week)
        for week in weekly
        if isinstance(week, Mapping)
        and rankings.week_observation_usable(week)
        and week.get("fantasy_points_ppr") is not None
    ]


def find_surprise_candidates(
    season_stats: Mapping[str, Mapping[str, Any]],
    players_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Every (player, week) pair that is a real outlier relative to that
    SAME player's own other weeks this season, restricted to players whose
    canonical tier reads as normally low-profile.

    Deliberately single-direction (a surprising GOOD week, not a bad one):
    coridian_'s own example ("a low-usage/bench-tier player who had a huge
    week") is the unambiguous headline case, and a "quiet star's bad week"
    reading would require including starter+ tiers, undercutting the "not
    just a star having a normal week" constraint. See this module's
    docstring and the PR description for this as a documented interpretation
    choice, not an oversight.
    """

    candidates: list[dict[str, Any]] = []
    for player_id, stats in season_stats.items():
        if not isinstance(stats, Mapping):
            continue
        player_row = players_by_id.get(str(player_id))
        if not player_row:
            continue
        if not _is_low_profile(player_row):
            continue
        position = str(player_row.get("position") or "").strip().upper()
        if not position:
            continue

        weeks = usable_weeks(stats.get("weekly"))
        if len(weeks) < MIN_USABLE_WEEKS:
            continue

        for index, week in enumerate(weeks):
            others = [w for other_index, w in enumerate(weeks) if other_index != index]
            if len(others) < MIN_USABLE_WEEKS - 1:
                continue
            try:
                actual = float(week.get("fantasy_points_ppr"))
            except (TypeError, ValueError):
                continue
            if actual < MIN_FEATURED_FANTASY_POINTS_PPR:
                continue

            baseline_values = []
            for other in others:
                try:
                    baseline_values.append(float(other.get("fantasy_points_ppr")))
                except (TypeError, ValueError):
                    continue
            if not baseline_values:
                continue
            baseline_avg = sum(baseline_values) / len(baseline_values)

            if baseline_avg <= 0:
                ratio = 999.0 if actual > 0 else 0.0
            else:
                ratio = actual / baseline_avg
            if ratio < MIN_SURPRISE_RATIO:
                continue

            candidates.append(
                {
                    "player_id": str(player_id),
                    "position": position,
                    "week": int(week.get("week") or 0),
                    "season": int(stats.get("stats_season") or 0),
                    "actual_fantasy_points_ppr": round(actual, 1),
                    "baseline_avg_fantasy_points_ppr": round(baseline_avg, 1),
                    "surprise_ratio": round(min(ratio, 999.0), 2),
                    "week_stats": week,
                }
            )
    return candidates


def select_daily_candidate(
    candidates: Sequence[Mapping[str, Any]], *, seed: str
) -> dict[str, Any] | None:
    """One candidate, deterministic for a given seed (the calendar date) —
    every backend worker/process picks the identical candidate for the same
    day with no shared cache or lock required for CORRECTNESS (a Redis cache
    around the caller is still worthwhile for the CPU cost of building
    `candidates` in the first place, see services/mobile_api_service.py)."""

    if not candidates:
        return None
    # Stable pre-shuffle order so the same `seed` always indexes the same
    # candidate regardless of dict/set iteration order upstream.
    ordered = sorted(candidates, key=lambda item: (item["player_id"], item["week"]))
    rng = random.Random(seed)
    return dict(rng.choice(ordered))


def stat_line_for_week(week_stats: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The real per-week fields this player actually has on file, formatted
    for display — never a fabricated yards/TD number (see module docstring:
    those are not retained at weekly granularity in this app's stats
    cache)."""

    lines: list[dict[str, Any]] = []
    for field, label in STAT_LINE_FIELDS:
        value = week_stats.get(field)
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if numeric <= 0:
            continue
        lines.append({"label": label, "value": int(round(numeric))})
    return lines


def _season_ppg(stats: Mapping[str, Any] | None) -> float | None:
    if not isinstance(stats, Mapping):
        return None
    ppg = stats.get("ppg")
    if ppg is not None:
        try:
            return float(ppg)
        except (TypeError, ValueError):
            pass
    try:
        points = float(stats.get("fantasy_points_ppr"))
        games = float(stats.get("games_played"))
    except (TypeError, ValueError):
        return None
    if games <= 0:
        return None
    return points / games


def build_distractor_options(
    players_df: pd.DataFrame,
    *,
    exclude_player_id: str,
    position: str,
    season_stats: Mapping[str, Mapping[str, Any]],
    target_ppg: float | None,
    count: int = DISTRACTOR_COUNT,
    seed: str = "",
) -> list[dict[str, str]]:
    """``count`` real, same-position players, ranked by how close their own
    season PPR-points-per-game is to the real answer's — a genuinely
    plausible guess, not an obvious giveaway. A small amount of seeded
    randomness breaks ties among equally-close candidates so the same
    handful of role players don't always appear together."""

    if players_df is None or players_df.empty:
        return []
    position_key = str(position or "").strip().upper()
    if not position_key:
        return []

    pool = players_df[
        (players_df.get("position", pd.Series(dtype=str)).astype(str).str.upper() == position_key)
        & (players_df.get("player_id", pd.Series(dtype=str)).astype(str) != str(exclude_player_id))
    ]

    baseline = float(target_ppg) if target_ppg is not None else 0.0
    rng = random.Random(seed or exclude_player_id)
    scored: list[tuple[float, float, str, str]] = []
    for _, row in pool.iterrows():
        player_id = str(row.get("player_id") or "").strip()
        name = str(row.get("name") or "").strip()
        if not player_id or not name:
            continue
        candidate_ppg = _season_ppg(season_stats.get(player_id))
        distance = abs((candidate_ppg if candidate_ppg is not None else 0.0) - baseline)
        scored.append((distance, rng.random(), player_id, name))

    scored.sort(key=lambda item: (item[0], item[1]))
    chosen = scored[:count]
    return [{"player_id": player_id, "name": name} for _, _, player_id, name in chosen]


def compute_pick_id(season: int, player_id: str, week: int) -> str:
    """Stable, opaque identity for one day's featured (player, week) pick —
    same "hash of real identity, not raw content" convention as
    services/mobile_api_service.py's `_alert_key_for_link`."""

    raw = f"{int(season)}:{str(player_id)}:{int(week)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def build_daily_pick(
    players_df: pd.DataFrame,
    season_stats: Mapping[str, Mapping[str, Any]],
    *,
    seed: str,
) -> dict[str, Any] | None:
    """The full daily pick: the real answer (kept out of the public
    payload by the caller) plus the public hidden-identity prompt.

    Returns ``None`` when no candidate currently qualifies (e.g. very early
    in a season before anyone has 4 usable weeks) — the caller must then
    report the card as unavailable rather than fabricate one.
    """

    if players_df is None or players_df.empty or not season_stats:
        return None

    players_by_id: dict[str, dict[str, Any]] = {}
    for _, row in players_df.iterrows():
        player_id = str(row.get("player_id") or "").strip()
        if player_id:
            players_by_id[player_id] = row.to_dict()

    candidates = find_surprise_candidates(season_stats, players_by_id)
    picked = select_daily_candidate(candidates, seed=seed)
    if picked is None:
        return None

    player_row = players_by_id.get(picked["player_id"]) or {}
    week_stats = picked["week_stats"]
    stat_line = stat_line_for_week(week_stats)
    if not stat_line:
        # No real per-week field survived (shouldn't happen given the
        # ratio/absolute gates above, but never show an empty stat line).
        return None

    options = build_distractor_options(
        players_df,
        exclude_player_id=picked["player_id"],
        position=picked["position"],
        season_stats=season_stats,
        target_ppg=_season_ppg(season_stats.get(picked["player_id"])),
        seed=seed,
    )
    answer_name = str(player_row.get("name") or "").strip()
    if not answer_name or len(options) < 2:
        # Not enough real distractors to make this a fair multiple-choice
        # question — fail closed rather than ship a 2-option or giveaway
        # guess.
        return None

    all_options = options + [{"player_id": picked["player_id"], "name": answer_name}]
    rng = random.Random(f"{seed}:shuffle")
    rng.shuffle(all_options)

    pick_id = compute_pick_id(picked["season"], picked["player_id"], picked["week"])

    return {
        "pick_id": pick_id,
        "season": picked["season"],
        "week": picked["week"],
        "player_id": picked["player_id"],
        "position": picked["position"],
        "tier": str(player_row.get("player_tier") or "").strip(),
        "team": str(player_row.get("team") or "").strip().upper(),
        "name": answer_name,
        "stat_line": stat_line,
        "fantasy_points_ppr": picked["actual_fantasy_points_ppr"],
        "options": all_options,
    }
