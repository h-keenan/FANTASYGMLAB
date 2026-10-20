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
    candidates: Sequence[Mapping[str, Any]],
    *,
    seed: str,
    sort_key: Any = None,
) -> dict[str, Any] | None:
    """One candidate, deterministic for a given seed (the calendar date) —
    every backend worker/process picks the identical candidate for the same
    day with no shared cache or lock required for CORRECTNESS (a Redis cache
    around the caller is still worthwhile for the CPU cost of building
    `candidates` in the first place, see services/mobile_api_service.py).

    ``sort_key`` defaults to the original "Whose stats are these?" shape
    (``player_id``/``week``); the name-match mode below reuses this same
    function with its own key rather than duplicating the
    stable-order-then-seeded-choice logic.
    """

    if not candidates:
        return None
    # Stable pre-shuffle order so the same `seed` always indexes the same
    # candidate regardless of dict/set iteration order upstream.
    key_fn = sort_key or (lambda item: (item["player_id"], item["week"]))
    ordered = sorted(candidates, key=key_fn)
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


# ---------------------------------------------------------------------------
# "Who is who?" name-match mode — coridian_'s own pitch (Discord, 2026-10-19,
# describing a SECOND mini-game alongside the one above): "you get two
# players and one player is, you know, a known name that's good, and then
# one player is kind of an unknown name who maybe has better stats than the
# known name, and so you pick and choose who is who."
#
# Deliberately a different mechanic from "Whose stats are these?" above:
# BOTH players' real identity (name/photo/position/team) is shown up front,
# never hidden. What's hidden is which of the two real, UNLABELED stat
# lines ("Slot A"/"Slot B") belongs to which player. The surprise this mode
# is built to guarantee: the obscure player's real stat line is genuinely
# better than the famous player's, in the exact same real week — reuses
# find_surprise_candidates's own "surprising bench-tier week" contract for
# the obscure side, rather than inventing a second selection heuristic.
# ---------------------------------------------------------------------------

# Top two of the seven-tier ladder (modules.player_tier_identity) — the
# real-world "recognizable name" counterpart to LOW_PROFILE_TIER_IDS's
# bottom three. Drawing the famous side only from here means a star having
# a normal great week can never accidentally BE the "surprise" side; the
# surprise always comes from the bottom-tier player per
# find_surprise_candidates's own existing contract.
HIGH_PROFILE_TIER_IDS = frozenset({"generational", "elite"})


def _is_high_profile(player_row: Mapping[str, Any]) -> bool:
    identity = player_tier_identity.resolve_player_tier_identity(player_row)
    return identity.tier_id in HIGH_PROFILE_TIER_IDS


def find_name_match_candidates(
    season_stats: Mapping[str, Mapping[str, Any]],
    players_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Every (obscure, famous) pairing where, in the exact SAME real week,
    a genuine surprise week from a normally low-profile player
    (find_surprise_candidates's own selection contract, reused unchanged)
    actually outscored a real high-profile player's own real stat line for
    that identical week.

    Anchoring both sides to the SAME week (rather than picking each
    player's own best week independently) keeps the comparison honest: the
    inversion is a genuine same-week fact, never two different,
    cherry-picked weeks stitched together to manufacture a surprise.
    """

    pairings: list[dict[str, Any]] = []
    for obscure in find_surprise_candidates(season_stats, players_by_id):
        season = obscure["season"]
        week = obscure["week"]
        obscure_points = obscure["actual_fantasy_points_ppr"]
        for famous_player_id, stats in season_stats.items():
            if not isinstance(stats, Mapping):
                continue
            if str(famous_player_id) == obscure["player_id"]:
                continue
            try:
                stats_season = int(stats.get("stats_season") or 0)
            except (TypeError, ValueError):
                continue
            if stats_season != season:
                continue
            famous_row = players_by_id.get(str(famous_player_id))
            if not famous_row or not _is_high_profile(famous_row):
                continue

            famous_week = next(
                (w for w in usable_weeks(stats.get("weekly")) if int(w.get("week") or 0) == week),
                None,
            )
            if famous_week is None:
                continue
            try:
                famous_points = float(famous_week.get("fantasy_points_ppr"))
            except (TypeError, ValueError):
                continue
            if famous_points >= obscure_points:
                # Must be a genuine inversion — the famous player actually
                # losing that week — never a tie or a famous-player win.
                continue

            pairings.append(
                {
                    "season": season,
                    "week": week,
                    "obscure_player_id": obscure["player_id"],
                    "obscure_position": obscure["position"],
                    "obscure_week_stats": obscure["week_stats"],
                    "obscure_actual_fantasy_points_ppr": obscure_points,
                    "famous_player_id": str(famous_player_id),
                    "famous_week_stats": famous_week,
                    "famous_actual_fantasy_points_ppr": round(famous_points, 1),
                }
            )
    return pairings


def compute_name_match_pick_id(season: int, famous_player_id: str, obscure_player_id: str, week: int) -> str:
    """Stable, opaque identity for one day's name-match pairing — same
    "hash of real identity, not raw content" convention as
    compute_pick_id, namespaced so it can never collide with that
    function's own pick_id for the original game."""

    raw = f"name_match:{int(season)}:{str(famous_player_id)}:{str(obscure_player_id)}:{int(week)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def build_daily_name_match_pick(
    players_df: pd.DataFrame,
    season_stats: Mapping[str, Mapping[str, Any]],
    *,
    seed: str,
) -> dict[str, Any] | None:
    """The full daily name-match pick: both real identities, both real
    per-week stat lines, and which opaque slot ("A"/"B") each one actually
    belongs to (kept out of the public payload by the caller until
    answered). Returns ``None`` when no genuine same-week inversion exists
    today — the caller must report the card as unavailable rather than
    fabricate one.
    """

    if players_df is None or players_df.empty or not season_stats:
        return None

    players_by_id: dict[str, dict[str, Any]] = {}
    for _, row in players_df.iterrows():
        player_id = str(row.get("player_id") or "").strip()
        if player_id:
            players_by_id[player_id] = row.to_dict()

    pairings = find_name_match_candidates(season_stats, players_by_id)
    picked = select_daily_candidate(
        pairings,
        seed=seed,
        sort_key=lambda item: (item["famous_player_id"], item["obscure_player_id"], item["week"]),
    )
    if picked is None:
        return None

    famous_row = players_by_id.get(picked["famous_player_id"]) or {}
    obscure_row = players_by_id.get(picked["obscure_player_id"]) or {}
    famous_name = str(famous_row.get("name") or "").strip()
    obscure_name = str(obscure_row.get("name") or "").strip()
    famous_stat_line = stat_line_for_week(picked["famous_week_stats"])
    obscure_stat_line = stat_line_for_week(picked["obscure_week_stats"])
    if not famous_name or not obscure_name or not famous_stat_line or not obscure_stat_line:
        # Fail closed rather than ship a half-identified or empty-stat-line
        # pairing (shouldn't happen given the gates above, but never guess).
        return None

    rng = random.Random(f"{seed}:name_match:slot")
    famous_slot = rng.choice(["A", "B"])
    obscure_slot = "B" if famous_slot == "A" else "A"

    pick_id = compute_name_match_pick_id(
        picked["season"], picked["famous_player_id"], picked["obscure_player_id"], picked["week"]
    )

    return {
        "pick_id": pick_id,
        "season": picked["season"],
        "week": picked["week"],
        "famous_player_id": picked["famous_player_id"],
        "famous_name": famous_name,
        "famous_team": str(famous_row.get("team") or "").strip().upper(),
        "famous_position": str(famous_row.get("position") or "").strip().upper(),
        "famous_tier": str(famous_row.get("player_tier") or "").strip(),
        "obscure_player_id": picked["obscure_player_id"],
        "obscure_name": obscure_name,
        "obscure_team": str(obscure_row.get("team") or "").strip().upper(),
        "obscure_position": picked["obscure_position"],
        "obscure_tier": str(obscure_row.get("player_tier") or "").strip(),
        "famous_slot": famous_slot,
        "obscure_slot": obscure_slot,
        "slots": {
            famous_slot: {
                "stat_line": famous_stat_line,
                "fantasy_points_ppr": picked["famous_actual_fantasy_points_ppr"],
            },
            obscure_slot: {
                "stat_line": obscure_stat_line,
                "fantasy_points_ppr": picked["obscure_actual_fantasy_points_ppr"],
            },
        },
    }
