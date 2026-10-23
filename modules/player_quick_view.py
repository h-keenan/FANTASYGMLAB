"""Normalized, presentation-only models for the shared Player Quick View."""

from __future__ import annotations
import math
import re
from dataclasses import dataclass
from typing import Mapping, Sequence
import numpy as np
import pandas as pd
from modules import player_profile_ui
from modules.player_eligibility import filter_current_fantasy_players
from modules.rankings import prime_window_status

@dataclass(frozen=True)
class StatItem:
    label: str
    value: str
    note: str
    tone: str
    #: Position-group percentile rank (1-100) for this stat, or ``None`` when
    #: no trustworthy comparison pool exists. "59 rush yards" is meaningless
    #: without knowing whether that is good for the position; see
    #: ``_stat_percentiles`` for how the pool is qualified.
    percentile: float | None = None


@dataclass(frozen=True)
class SeasonStatView:
    season: int | None
    season_type: str
    games: int | None
    complete: bool | None
    key_stats: tuple[StatItem, ...]
    fantasy: tuple[StatItem, ...]
    usage: tuple[StatItem, ...]
    efficiency: tuple[StatItem, ...] = ()

    @property
    def label(self) -> str:
        if self.season is None:
            return f"{self.season_type} (year unavailable)"
        return f"{self.season} {self.season_type}".strip()


@dataclass(frozen=True)
class PlayerQuickViewStats:
    seasons: tuple[SeasonStatView, ...]
    college: tuple[StatItem, ...]
    college_available: bool
    career_totals_available: bool = False
    position: str = ""
    #: 0-99 headline rating — the player's ``value_score`` percentile within
    #: their position, on the scale a 2K "OVR" badge uses. ``None`` when the
    #: position pool is too thin to rank against, exactly like
    #: ``StatItem.percentile``; see ``_overall_rating``.
    overall_rating: int | None = None
    #: Position's dynasty prime-age window (start_age, end_age, status for
    #: THIS player) — derived from modules.rankings.AGE_CURVE_CONTROL_POINTS,
    #: the same age curve already discounting every player's dynasty value,
    #: not a separately invented projection. ``None`` when position/age is
    #: missing or unrecognized. See modules.rankings.prime_window_status.
    prime_window: dict[str, object] | None = None


@dataclass(frozen=True)
class ExecutiveSnapshot:
    years_in_league: str = ""
    draft_capital: str = ""
    college: str = ""
    height: str = ""
    weight: str = ""
    bye_week: str = ""
    contract_status: str = ""


def build_executive_snapshot(
    row: Mapping[str, object],
    metadata: Mapping[str, object] | None = None,
) -> ExecutiveSnapshot:
    """Normalize verified profile metadata without inventing unavailable fields."""
    source = dict(metadata or {})
    source.update({key: value for key, value in row.items() if _text(value)})

    years_raw = pd.to_numeric(pd.Series([source.get("years_exp")]), errors="coerce").iloc[0]
    years = ""
    if pd.notna(years_raw) and float(years_raw) >= 0:
        seasons = int(float(years_raw))
        years = "Rookie" if seasons == 0 else f"{seasons} season{'s' if seasons != 1 else ''}"

    round_raw = pd.to_numeric(pd.Series([source.get("draft_round")]), errors="coerce").iloc[0]
    pick_raw = pd.to_numeric(
        pd.Series([source.get("draft_slot") or source.get("draft_pick")]),
        errors="coerce",
    ).iloc[0]
    year_raw = pd.to_numeric(pd.Series([source.get("draft_year")]), errors="coerce").iloc[0]
    draft_parts: list[str] = []
    if pd.notna(year_raw):
        draft_parts.append(str(int(float(year_raw))))
    if pd.notna(round_raw):
        draft_parts.append(f"Round {int(float(round_raw))}")
    if pd.notna(pick_raw):
        draft_parts.append(f"Pick {int(float(pick_raw))}")

    height = _text(source.get("height"))
    if height.isdigit():
        total_inches = int(height)
        height = f"{total_inches // 12}'{total_inches % 12}\""
    weight = _text(source.get("weight"))
    if weight and weight.replace(".", "", 1).isdigit():
        weight = f"{int(float(weight))} lb"

    return ExecutiveSnapshot(
        years_in_league=years,
        draft_capital=" / ".join(draft_parts),
        college=_text(source.get("college")),
        height=height,
        weight=weight,
        bye_week=_text(source.get("bye_week")),
        contract_status=_text(source.get("contract_status")),
    )


def _text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _integer(value: object) -> int | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(numeric) else int(numeric)


def _items(items: list[dict]) -> tuple[StatItem, ...]:
    return tuple(
        StatItem(
            label=_text(item.get("label")) or "Metric",
            value=_text(item.get("value")),
            note=_text(item.get("note")),
            tone=_text(item.get("tone")) or "reference",
            percentile=_percentile_value(item.get("percentile")),
        )
        for item in items
    )


def _percentile_value(value: object) -> float | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    return float(numeric)


def _group_items(row: pd.Series) -> dict[str, list[dict]]:
    return {
        label: list(items)
        for label, items in player_profile_ui.player_profile_stat_groups(row)
    }


#: A percentile is only shown when the position group has at least this many
#: players carrying a real value for that column. Below it, "80th percentile"
#: would just mean "4th of 5" — precise-looking and misleading — so the field
#: is omitted entirely instead.
PERCENTILE_MIN_POOL = 10


#: Top of the overall-rating scale. 99 (not 100) because the number is read
#: as an NBA 2K "OVR" badge, and a 100 would read as a different, unbounded
#: scale. The floor is 1 for the same reason a percentile's is: a rated
#: player is never a 0.
OVERALL_RATING_MAX = 99


#: Columns the overall rating ranks on, in preference order. rankings.py
#: writes ``value_score`` and ``dynasty_score`` from the same composite
#: ``score`` in one pass (see compose_composite_score), so these are the same
#: number under three names — the fallback chain exists only so a frame
#: assembled by a lighter path still rates.
_OVERALL_SCORE_FIELDS = ("value_score", "dynasty_score", "score")


#: Percentile -> overall-rating control points (piecewise-linear), same
#: pattern as modules.rankings.AGE_CURVE_CONTROL_POINTS. A flat
#: percentile*99 mapping put a mid-pack committee back (~88th percentile of
#: EVERY rosterable player at the position, including backups and deep
#: bench) at "88 overall" — a number that reads as a clear above-average
#: starter on the NBA 2K scale this badge borrows, when the player is
#: actually a middling RB2 in real terms. Real sports-game ratings aren't
#: linear either: most rostered players cluster in the 60s-70s, and only
#: genuine difference-makers clear 85+. These breakpoints compress the
#: bulk of the pool down and reserve the top of the scale for players who
#: are actually near the best at their position, without touching the
#: underlying value_score or the comparison pool itself.
#:
#: A second pass (coridian_'s follow-up: "there seems to be a lot of players
#: 90+") found the first curve's top end still too generous: because the
#: rating ranks WITHIN each position separately, "top 3%" at (0.97, 92) meant
#: every position independently minted its own handful of 90+ players —
#: roughly 5-6% of every position's eligible pool, ~50+ players total across
#: a ~1000-player universe. Real 90+ overalls are rare across the WHOLE
#: player pool, not just rare-per-position. Pushed the 85 and 90+ breakpoints
#: further into the tail (0.97 -> 85, 0.995 -> 90) so 90+ is reserved for
#: roughly the top 0.5% at a position — the true 1-2 difference-makers, not
#: the top 10-20.
_OVERALL_RATING_CURVE: tuple[tuple[float, float], ...] = (
    (0.0, 40.0),
    (0.50, 62.0),
    (0.80, 72.0),
    (0.93, 80.0),
    (0.97, 85.0),
    (0.995, 90.0),
    (1.0, float(OVERALL_RATING_MAX)),
)


def _overall_rating_from_percentile(percentile: float) -> int:
    points = _OVERALL_RATING_CURVE
    clamped = min(1.0, max(0.0, percentile))
    rating = points[-1][1]
    for (p_a, r_a), (p_b, r_b) in zip(points, points[1:]):
        if p_a <= clamped <= p_b:
            frac = 0.0 if p_b == p_a else (clamped - p_a) / (p_b - p_a)
            rating = r_a + frac * (r_b - r_a)
            break
    return int(min(OVERALL_RATING_MAX, max(1, round(rating))))


#: Stat label -> candidate source columns / display format kind, derived
#: directly from player_profile_ui's own stat-group definitions, so neither
#: a percentile nor a formatted value here can ever drift onto a different
#: column/format than the number PQV's Stats tab renders for that same
#: label. Includes "Games" (format/fields only — see _PERCENTILE_STAT_FIELDS
#: below for why it's excluded from percentile ranking).
_LABEL_FIELDS: dict[str, tuple[str, ...]] = {
    label: fields
    for _group_label, _tone, stat_defs in player_profile_ui.PLAYER_PROFILE_STAT_GROUPS
    for label, fields, _format_kind, _note in stat_defs
}


_LABEL_FORMAT_KIND: dict[str, str] = {
    label: format_kind
    for _group_label, _tone, stat_defs in player_profile_ui.PLAYER_PROFILE_STAT_GROUPS
    for label, _fields, format_kind, _note in stat_defs
}


#: Stat label -> candidate source columns, for percentile ranking only.
#: "Games" is deliberately absent: availability is not a performance stat,
#: and a "90th percentile in games played" badge next to a replacement-level
#: player reads as praise.
_PERCENTILE_STAT_FIELDS: dict[str, tuple[str, ...]] = {
    label: fields for label, fields in _LABEL_FIELDS.items() if label != "Games"
}


_GAMES_FIELDS = ("games", "games_played", "gp")


#: Format kind for the five derived per-game/per-touch rate stats below —
#: not in player_profile_ui's own stat groups (they're computed, not a
#: loaded column), so they don't get a format kind from _LABEL_FORMAT_KIND.
_RATIO_STAT_FORMAT_KIND: dict[str, str] = {
    "Targets/Gm": "rate",
    "Rec/Gm": "rate",
    "Yards/Catch": "rate",
    "Carries/Gm": "rate",
    "Yards/Carry": "rate",
}


#: Position -> the raw season-stat labels Players' Madden-style stat sort
#: surfaces for that position (task: "a reasonable set of position-relevant
#: raw stats", not every stat this app tracks). Its own curation, deliberately
#: not reused from _key_stats' per-position `order` below: this list adds
#: Snap Share and PPG (workload + per-game production, both useful sort
#: columns Madden-style comparisons expect) that PQV's hero Key Stats group
#: doesn't carry the same way. A label only renders here when
#: annotate_rankings_stat_pool below actually has a value for the player
#: (e.g. Pass Att is simply omitted for a RB, never shown as 0/blank).
RANKINGS_STAT_LABELS_BY_POSITION: dict[str, tuple[str, ...]] = {
    "QB": ("Games", "Pass Att", "Pass Yards", "Pass TDs", "Rush Yards", "Rush TDs", "Fantasy Pts", "PPG"),
    "RB": (
        "Games",
        "Rush Att",
        "Rush Yards",
        "Rush TDs",
        "Targets",
        "Receptions",
        "Rec Yards",
        "Rec TDs",
        "Snap Share",
        "PPG",
    ),
    "WR": ("Games", "Targets", "Receptions", "Rec Yards", "Rec TDs", "Snap Share", "Target Share", "PPG"),
    "TE": ("Games", "Targets", "Receptions", "Rec Yards", "Rec TDs", "Snap Share", "Target Share", "PPG"),
}


_DEFAULT_RANKINGS_STAT_LABELS: tuple[str, ...] = ("Games", "Fantasy Pts", "PPG")


def _positive(series: pd.Series | None) -> pd.Series | None:
    """Denominators of zero are absence of workload, not a 0.0 rate."""

    if series is None:
        return None
    return series.where(series > 0)


def _position_pool(
    players_df: pd.DataFrame | None,
    row: Mapping[str, object],
) -> tuple[pd.DataFrame, int] | None:
    """This player's position group inside the canonical eligible pool.

    The one place the "who is this player ranked against" question is
    answered, so every percentile on this screen — the per-stat ones and the
    headline overall rating — shares a single peer group. Returns the group
    frame plus the player's row offset inside it, or ``None`` when no
    trustworthy comparison exists (see ``_stat_percentiles`` for the two
    gates and why they are drawn where they are).
    """

    if players_df is None or not isinstance(players_df, pd.DataFrame) or players_df.empty:
        return None
    if "position" not in players_df.columns or "player_id" not in players_df.columns:
        return None
    position = _text(row.get("position")).upper()
    player_id = _text(row.get("player_id"))
    if not position or not player_id:
        return None

    try:
        pool = filter_current_fantasy_players(
            players_df,
            surface="player_quick_view_percentiles",
        )
    except Exception:
        return None
    if pool is None or pool.empty:
        return None

    group = pool[pool["position"].astype(str).str.upper() == position]
    if len(group) < PERCENTILE_MIN_POOL:
        return None
    located = group["player_id"].astype(str).to_numpy() == player_id
    if not located.any():
        return None
    return group, int(located.argmax())


def _overall_rating(
    players_df: pd.DataFrame | None,
    row: Mapping[str, object],
) -> int | None:
    """One 0-99 headline number for "how good is this player", 2K-style.

    Deliberately *not* a new valuation: it is the player's percentile on the
    exact same ``value_score`` the ranking board, trade engine and Snapshot
    grid already show, re-expressed on the 0-99 scale people read instantly.
    Rank and score answer "where do you sit" and "what are you worth";
    neither answers "out of 99, how good is this" at a glance, which is the
    whole point of the badge.

    Same pool, same position-relative framing and same
    ``PERCENTILE_MIN_POOL`` gate as the per-stat percentiles (``None`` below
    it), so the hero ring can never disagree with the numbers on the Stats
    tab — a 99 overall next to a page of 30th-percentile stats would be the
    app arguing with itself.
    """

    located = _position_pool(players_df, row)
    if located is None:
        return None
    group, offset = located

    column = next((field for field in _OVERALL_SCORE_FIELDS if field in group.columns), "")
    if not column:
        return None
    series = pd.to_numeric(group[column], errors="coerce")
    if int(series.notna().sum()) < PERCENTILE_MIN_POOL:
        return None
    value = series.rank(pct=True).to_numpy()[offset]
    if pd.isna(value):
        return None
    return _overall_rating_from_percentile(float(value))


def overall_ratings_for_pool(
    frame: pd.DataFrame | None,
    *,
    score_column: str,
    position_column: str = "position",
) -> pd.Series:
    """0-99 overall rating for every row of an already-assembled ranked pool.

    List endpoints (rankings, my-team, waivers, ...) already build and hold
    the full per-league, per-position pool they need to answer their own
    request — re-deriving an isolated percentile per row through
    ``_overall_rating``/``_position_pool`` (which re-filters the canonical
    player frame from scratch for every single player) would be both
    wasteful and a second, easily-diverging copy of the same pool logic.
    This is that same computation, vectorized over a pool the caller already
    has in hand: percentile via ``rank(pct=True)`` *within each position
    group in `frame`*, gated by the same ``PERCENTILE_MIN_POOL`` floor, fed
    into the exact same ``_overall_rating_from_percentile`` curve
    ``_overall_rating`` uses — one curve, two entry points, so a player's
    badge never disagrees with itself depending which screen rendered it.

    Returns a ``pandas.Series`` of ``int | None`` aligned to ``frame``'s
    index (``None`` for a row whose position group is missing, unscored, or
    thinner than ``PERCENTILE_MIN_POOL``). Passing ``None``/empty/malformed
    input returns an empty Series rather than raising, matching
    ``_position_pool``'s own "no trustworthy comparison" contract.
    """

    empty = pd.Series(dtype=object)
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        return empty
    if position_column not in frame.columns or score_column not in frame.columns:
        return pd.Series([None] * len(frame), index=frame.index, dtype=object)

    positions = frame[position_column].astype(str).str.upper()
    scores = pd.to_numeric(frame[score_column], errors="coerce")
    pool_sizes = scores.groupby(positions).transform(lambda s: int(s.notna().sum()))
    percentiles = scores.groupby(positions).rank(pct=True)

    def _rating(percentile: float, pool_size: int) -> int | None:
        if pd.isna(percentile) or pool_size < PERCENTILE_MIN_POOL:
            return None
        return _overall_rating_from_percentile(float(percentile))

    return pd.Series(
        [_rating(p, n) for p, n in zip(percentiles, pool_sizes)],
        index=frame.index,
        dtype=object,
    )


def _percentile_from_values(values: pd.Series, positions: pd.Series) -> pd.Series:
    """1-100 percentile rank of `values`, computed within each `positions`
    group, gated by PERCENTILE_MIN_POOL — the one shared percentile-ranking
    primitive behind every per-stat percentile this module computes: PQV's
    Stats tab (``_stat_percentiles`` below) and Players list's Madden-style
    stat sort (``annotate_rankings_stat_pool``) both resolve to this same
    rank(pct=True)-with-ties-as-average-and-a-floor logic, so they can never
    disagree about the same player's number. A position group with fewer
    than PERCENTILE_MIN_POOL real values returns ``None`` for every row in
    that group rather than a precise-looking but meaningless rank. Returns
    an ``object``-dtype Series of ``int | None``, aligned to `values`' index.
    """

    pool_sizes = values.groupby(positions).transform(lambda s: int(s.notna().sum()))
    ranks = values.groupby(positions).rank(pct=True)
    return pd.Series(
        [
            int(min(100, max(1, round(float(p) * 100)))) if not pd.isna(p) and n >= PERCENTILE_MIN_POOL else None
            for p, n in zip(ranks, pool_sizes)
        ],
        index=values.index,
        dtype=object,
    )


def _coalesced_numeric_column(frame: pd.DataFrame, fields: Sequence[str]) -> pd.Series | None:
    """Vectorized equivalent of player_profile_ui.first_player_stat_value: for
    every row in `frame`, the first candidate column (in `fields` order)
    carrying a real value for THAT row — same per-row fallback semantics,
    computed for the whole frame at once. In practice a given players frame
    only ever has one of a stat's alias columns actually present (the others
    are older season-schema names), so this reduces to "the one present
    column" for every row identically; it only diverges from resolving a
    single anchor row's column choice and applying it to the whole group
    (what this module did before) in the rare case two alias columns coexist
    with partial coverage — and then it is strictly more correct, since every
    row is ranked on its own real value instead of whichever column one
    anchor player happened to have. Returns ``None`` when no candidate field
    is present in `frame` at all.
    """

    result: pd.Series | None = None
    for field in fields:
        if field not in frame.columns:
            continue
        candidate = pd.to_numeric(frame[field], errors="coerce")
        result = candidate if result is None else result.combine_first(candidate)
    return result


def stat_percentiles_for_pool(
    frame: pd.DataFrame,
    stat_fields: Mapping[str, Sequence[str]],
    *,
    position_column: str = "position",
) -> dict[str, tuple[pd.Series, pd.Series]]:
    """Raw coalesced value + position-relative percentile for every label in
    `stat_fields`, for every row of `frame` at once — the vectorized sibling
    of ``_stat_percentiles`` (one player at a time) and
    ``overall_ratings_for_pool`` (one score column, not a stat-per-label
    map): a list endpoint ranking every row in its response can call this
    once instead of re-filtering/re-ranking a fresh position pool per row.
    Shares ``_percentile_from_values`` so this and ``_stat_percentiles`` can
    never disagree about the same player's percentile.

    Returns ``{label: (value_series, percentile_series)}``, both aligned to
    `frame`'s index; a label is simply absent when none of its candidate
    columns exist in `frame`. Empty/malformed `frame` input returns ``{}``.
    """

    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty or position_column not in frame.columns:
        return {}
    positions = frame[position_column].astype(str).str.upper()
    result: dict[str, tuple[pd.Series, pd.Series]] = {}
    for label, fields in stat_fields.items():
        values = _coalesced_numeric_column(frame, fields)
        if values is None:
            continue
        result[label] = (values, _percentile_from_values(values, positions))
    return result


def _ratio_stat_values_for_pool(frame: pd.DataFrame) -> dict[str, pd.Series | None]:
    """Raw per-game / per-touch rate columns — the same five derived rates
    ``_efficiency_stats`` renders (Targets/Gm, Rec/Gm, Yards/Catch,
    Carries/Gm, Yards/Carry), computed from the same raw counting columns,
    vectorized over the whole pool at once."""

    games = _positive(_coalesced_numeric_column(frame, _GAMES_FIELDS))
    targets = _coalesced_numeric_column(frame, ("targets",))
    receptions = _coalesced_numeric_column(frame, ("receptions",))
    receiving_yards = _coalesced_numeric_column(frame, ("receiving_yards", "receiving_yds"))
    rush_attempts = _coalesced_numeric_column(frame, ("rush_attempts", "rushing_attempts", "carries"))
    rushing_yards = _coalesced_numeric_column(frame, ("rushing_yards", "rush_yards"))

    def _ratio(numerator: pd.Series | None, denominator: pd.Series | None) -> pd.Series | None:
        if numerator is None or denominator is None:
            return None
        return numerator / denominator

    return {
        "Targets/Gm": _ratio(targets, games),
        "Rec/Gm": _ratio(receptions, games),
        "Yards/Catch": _ratio(receiving_yards, _positive(receptions)),
        "Carries/Gm": _ratio(rush_attempts, games),
        "Yards/Carry": _ratio(rushing_yards, _positive(rush_attempts)),
    }


def ratio_stat_percentiles_for_pool(
    frame: pd.DataFrame,
    *,
    position_column: str = "position",
) -> dict[str, tuple[pd.Series, pd.Series]]:
    """``stat_percentiles_for_pool``'s sibling for the five derived rate
    stats, which have no single source column to coalesce (see
    ``_ratio_stat_values_for_pool``)."""

    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty or position_column not in frame.columns:
        return {}
    positions = frame[position_column].astype(str).str.upper()
    result: dict[str, tuple[pd.Series, pd.Series]] = {}
    for label, values in _ratio_stat_values_for_pool(frame).items():
        if values is None:
            continue
        result[label] = (values, _percentile_from_values(values, positions))
    return result


def _slugify_stat_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_") or "stat"


def annotate_rankings_stat_pool(
    frame: pd.DataFrame,
    *,
    position_column: str = "position",
) -> pd.DataFrame:
    """Adds hidden ``__stat_value__<slug>`` / ``__stat_pct__<slug>`` columns
    to `frame` for every stat label referenced by
    ``RANKINGS_STAT_LABELS_BY_POSITION``, computed once over the whole pool —
    the same "compute on the full ranked pool before any limit=N truncation"
    pattern ``overall_ratings_for_pool`` already follows, just for Players'
    per-stat sort/percentile columns instead of the single overall-rating
    badge. Mutates and returns `frame`; a no-op when `frame` is empty/
    malformed or missing a position column, matching every other pool
    helper's fail-open contract in this module. Read back a row's entries
    with ``rankings_stat_entries_for_row``.

    "Games" gets a value column but never a percentile — same reasoning as
    ``_PERCENTILE_STAT_FIELDS``'s own exclusion of it: availability is not a
    performance stat, so it's handled as its own pass below rather than
    through the shared percentile pools.
    """

    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty or position_column not in frame.columns:
        return frame

    wanted_labels = set(_DEFAULT_RANKINGS_STAT_LABELS) | {
        label for labels in RANKINGS_STAT_LABELS_BY_POSITION.values() for label in labels
    }
    percentile_eligible_labels = wanted_labels - {"Games"}
    plain_fields = {label: fields for label, fields in _LABEL_FIELDS.items() if label in percentile_eligible_labels}
    pools = {
        **stat_percentiles_for_pool(frame, plain_fields, position_column=position_column),
        **ratio_stat_percentiles_for_pool(frame, position_column=position_column),
    }
    for label, (values, percentiles) in pools.items():
        if label not in wanted_labels:
            continue
        slug = _slugify_stat_label(label)
        frame[f"__stat_value__{slug}"] = values
        frame[f"__stat_pct__{slug}"] = percentiles

    if "Games" in wanted_labels:
        games_values = _coalesced_numeric_column(frame, _LABEL_FIELDS["Games"])
        if games_values is not None:
            slug = _slugify_stat_label("Games")
            frame[f"__stat_value__{slug}"] = games_values
            frame[f"__stat_pct__{slug}"] = pd.Series([None] * len(frame), index=frame.index, dtype=object)
    return frame


_NATIVE_NUMERIC_TYPES = (bool, int, float, np.bool_, np.integer, np.floating)


def _numeric_or_none(value: object) -> float | None:
    # Performance audit, 2026-10-21: this runs twice per stat label for every
    # row GET /v1/leagues/{id}/rankings returns (~4,500 calls for a 300-row
    # page), and building a one-element Series per call was ~60% of that
    # endpoint's CPU on every request, warm or cold. Plain numbers (what the
    # annotated __stat_value__/__stat_pct__ columns hold) take the direct
    # path; anything else (strings, pd.NA, Decimal, ...) still goes through
    # the original to_numeric coercion, so results are unchanged.
    if value is None:
        return None
    if isinstance(value, _NATIVE_NUMERIC_TYPES):
        numeric = float(value)
        return None if math.isnan(numeric) else numeric
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(numeric) else float(numeric)


def rankings_stat_entries_for_row(row: pd.Series) -> list[dict]:
    """Position-relevant stat entries (key/label/value/format/percentile) for
    one row of a frame already annotated by ``annotate_rankings_stat_pool`` —
    Players' Madden-style stat columns. A label is omitted entirely when this
    player has no real value for it (e.g. Pass Att for a RB), never shown as
    a 0/blank. A row from a frame that was never annotated (every
    ``__stat_value__*`` column absent) simply returns ``[]`` rather than
    raising, same fail-open contract as ``rank_unavailable_reason`` elsewhere
    on this row.
    """

    position = _text(row.get("position")).upper()
    labels = RANKINGS_STAT_LABELS_BY_POSITION.get(position, _DEFAULT_RANKINGS_STAT_LABELS)
    entries: list[dict] = []
    for label in labels:
        slug = _slugify_stat_label(label)
        value_col = f"__stat_value__{slug}"
        if value_col not in row.index:
            continue
        value = _numeric_or_none(row.get(value_col))
        if value is None:
            continue
        format_kind = _LABEL_FORMAT_KIND.get(label) or _RATIO_STAT_FORMAT_KIND.get(label) or "count"
        if format_kind == "share" and abs(value) <= 1.0:
            value *= 100.0
        percentile_numeric = _numeric_or_none(row.get(f"__stat_pct__{slug}"))
        percentile = None if percentile_numeric is None else int(percentile_numeric)
        entries.append(
            {
                "key": slug,
                "label": label,
                "value": round(value, 2),
                "format": format_kind,
                "percentile": percentile,
            }
        )
    return entries


def _stat_percentiles(
    players_df: pd.DataFrame | None,
    row: Mapping[str, object],
) -> dict[str, float]:
    """Percentile rank (1-100) of this player's stats within their position.

    Two correctness gates, both deliberate:

    1. The pool is ``modules.player_eligibility.filter_current_fantasy_players``
       — the same "who counts as a current fantasy asset" definition every
       other surface (Waivers, Trade search, the ranking board) already uses.
       Inventing a second standard here would mean a player could be 40th
       percentile on this screen and a different 40th percentile everywhere
       else. Frames from ``rankings.load_players`` are already annotated, so
       this is a mask over a precomputed column rather than a re-validation.
    2. Any column with fewer than ``PERCENTILE_MIN_POOL`` real values inside
       the position group is dropped (see that constant).

    Ties use pandas' default ``method="average"``: two players with identical
    yardage land on the same percentile, which is the honest answer.

    Returns a mapping keyed by the *source* stat label (the label
    player_profile_ui produced, before the display renames in
    ``_fantasy_stats`` / ``_usage_stats``) plus the derived rate labels from
    ``_efficiency_stats``. A player outside the eligible pool gets ``{}`` —
    there is no meaningful peer group to rank a retired player against.

    Delegates the actual ranking to ``stat_percentiles_for_pool``/
    ``ratio_stat_percentiles_for_pool`` (the vectorized, whole-pool-at-once
    versions Players' Madden-style stat sort also uses), scoped down to this
    one player's position group and offset — see those functions' docstrings
    for the shared gating/ranking logic.
    """

    located = _position_pool(players_df, row)
    if located is None:
        return {}
    group, offset = located

    pools: dict[str, tuple[pd.Series, pd.Series]] = {
        **stat_percentiles_for_pool(group, _PERCENTILE_STAT_FIELDS),
        **ratio_stat_percentiles_for_pool(group),
    }

    percentiles: dict[str, float] = {}
    for label, (_values, percentile_series) in pools.items():
        value = percentile_series.iloc[offset]
        if value is None:
            continue
        percentiles[label] = float(value)
    return percentiles


#: Composite value-score inputs to narrate, in the exact order the "How We
#: Evaluate" weights (modules.methodology_page) present them — market first
#: (the dominant weight), then scarcity/opportunity, then role. Age is
#: deliberately excluded: age_penalty is a signed delta (age_curve - market),
#: not a higher-is-better score like the other four, so it can't share this
#: percentile-and-band treatment without a separate, differently-signed path.
_DECISION_FIT_FACTORS: tuple[tuple[str, str], ...] = (
    ("market value", "market_score"),
    ("positional scarcity", "scarcity_score"),
    ("opportunity", "opportunity_score"),
    ("role", "role_score"),
)


_DECISION_FIT_MIN_FACTORS = 2


_DECISION_FIT_WEAKNESS_CEILING = 40


def _ordinal(value: int) -> str:
    if 10 <= value % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def _column_percentile(group: pd.DataFrame, offset: int, column: str) -> int | None:
    """Percentile rank (1-100) of one composite-score input column, for the
    player at `offset` inside `group` (already this player's position-
    filtered pool from ``_position_pool``). Same ``PERCENTILE_MIN_POOL`` gate
    and ``rank(pct=True)`` machinery as ``_stat_percentiles``, just applied to
    a composite-score input instead of a raw stat. Shared by
    ``decision_fit_narrative`` (the "why" sentence) and ``sub_ratings`` (the
    Model tab's chip row) so the two surfaces can never disagree about the
    exact same number.
    """

    if column not in group.columns:
        return None
    series = pd.to_numeric(group[column], errors="coerce")
    if int(series.notna().sum()) < PERCENTILE_MIN_POOL:
        return None
    value = series.rank(pct=True).to_numpy()[offset]
    if pd.isna(value):
        return None
    return int(min(100, max(1, round(float(value) * 100))))


def decision_fit_narrative(
    players_df: pd.DataFrame | None,
    row: Mapping[str, object],
) -> str | None:
    """One sentence naming the real driver(s) behind this player's value.

    Percentiles only — same pool, same PERCENTILE_MIN_POOL gate, same
    rank(pct=True) machinery as _stat_percentiles, just applied to the
    composite score inputs instead of raw stats. Never invents a factor:
    fewer than _DECISION_FIT_MIN_FACTORS resolving (missing columns, thin
    pool) returns None rather than a sentence built on partial signal.
    """

    located = _position_pool(players_df, row)
    if located is None:
        return None
    group, offset = located
    position = _text(row.get("position")).upper()

    resolved: list[tuple[str, int]] = []
    for label, column in _DECISION_FIT_FACTORS:
        pctile = _column_percentile(group, offset, column)
        if pctile is None:
            continue
        resolved.append((label, pctile))

    if len(resolved) < _DECISION_FIT_MIN_FACTORS:
        return None

    strongest_label, strongest_pctile = max(resolved, key=lambda item: item[1])
    weakest_label, weakest_pctile = min(resolved, key=lambda item: item[1])

    sentence = (
        f"{strongest_label.capitalize()} ({_ordinal(strongest_pctile)} percentile at {position}) "
        "is the biggest driver of this valuation."
    )
    if weakest_label != strongest_label and weakest_pctile <= _DECISION_FIT_WEAKNESS_CEILING:
        sentence += f" {weakest_label.capitalize()} ({_ordinal(weakest_pctile)}) is the softest input."
    return sentence


#: Composite-score inputs that get the OVR ring's percentile-and-rating
#: treatment on the Model tab's sub-rating chip row. Same four factors
#: decision_fit_narrative names (_DECISION_FIT_FACTORS) — kept as a
#: separate tuple keyed to the short field-name prefix the API/mobile chip
#: row uses ("market_rating", "opportunity_rating", ...) rather than
#: overloading that tuple's own long-form-label shape.
_SUB_RATING_FACTORS: tuple[tuple[str, str], ...] = (
    ("market", "market_score"),
    ("opportunity", "opportunity_score"),
    ("scarcity", "scarcity_score"),
    ("role", "role_score"),
)


def sub_ratings(
    players_df: pd.DataFrame | None,
    row: Mapping[str, object],
) -> dict[str, int | None]:
    """Market/Opportunity/Scarcity/Role/Durability, each re-expressed on the
    same 0-99 "how good, out of 99" scale as the headline OVR ring badge —
    the Model tab's sub-rating chip row (e.g. "MKT 91 - OPP 84 - SCR 62 -
    ROLE 73 - DUR 58").

    Market/Opportunity/Scarcity/Role: each composite-score input is first
    turned into a percentile within the player's position pool — identical
    math and PERCENTILE_MIN_POOL gate to decision_fit_narrative's own
    per-factor percentiles (``_column_percentile``), so the chip row and the
    narrative sentence can never disagree about the same number — then run
    through the EXACT SAME ``_overall_rating_from_percentile`` curve the OVR
    badge itself uses, so "MKT 91" sits on the identical scale as "91 OVR".
    ``None`` for any factor whose column is missing or whose position pool
    is too thin to rank against (same gate, same reason, as every other
    percentile on this screen) — never a fabricated rating.

    Durability is a different kind of input, not a peer-ranked one:
    ``injury_multiplier`` and ``non_injury_risk_multiplier`` (modules.
    rankings) are already an intrinsic 0-1 "how available is this player
    right now" rate — a healthy backup and a healthy star are both fully
    available, so ranking durability against the position pool would just
    bucket almost everyone at the ceiling and bury the one signal that
    actually matters (an injury). It is scaled directly onto the 0-99
    display range instead of being position-ranked. ``None`` only when
    neither multiplier is present on the row at all.
    """

    located = _position_pool(players_df, row)
    ratings: dict[str, int | None] = {}
    if located is not None:
        group, offset = located
        for label, column in _SUB_RATING_FACTORS:
            pctile = _column_percentile(group, offset, column)
            ratings[f"{label}_rating"] = (
                _overall_rating_from_percentile(pctile / 100.0) if pctile is not None else None
            )
    else:
        for label, _column in _SUB_RATING_FACTORS:
            ratings[f"{label}_rating"] = None

    injury_mult = _percentile_value(row.get("injury_multiplier"))
    non_injury_mult = _percentile_value(row.get("non_injury_risk_multiplier"))
    if injury_mult is None and non_injury_mult is None:
        ratings["durability_rating"] = None
    else:
        durability = (1.0 if injury_mult is None else injury_mult) * (
            1.0 if non_injury_mult is None else non_injury_mult
        )
        ratings["durability_rating"] = int(
            min(OVERALL_RATING_MAX, max(1, round(durability * OVERALL_RATING_MAX)))
        )
    return ratings


def _with_percentile(item: Mapping[str, object], percentile: float | None) -> dict:
    cloned = dict(item)
    if percentile is not None:
        cloned["percentile"] = percentile
    return cloned


def _key_stats(
    row: pd.Series,
    groups: Mapping[str, list[dict]],
    percentiles: Mapping[str, float] | None = None,
) -> list[dict]:
    ranks = percentiles or {}
    by_label = {str(item.get("label")): item for item in groups.get("NFL Stats", [])}
    position = _text(row.get("position")).upper()
    order = {
        "QB": ["Games", "Pass Att", "Pass Yards", "Pass TDs", "Rush Yards", "Rush TDs"],
        "RB": ["Games", "Rush Att", "Rush Yards", "Rush TDs", "Targets", "Receptions", "Rec Yards", "Rec TDs"],
        "WR": ["Games", "Targets", "Receptions", "Rec Yards", "Rec TDs", "Rush Yards", "Rush TDs"],
        "TE": ["Games", "Targets", "Receptions", "Rec Yards", "Rec TDs", "Rush Yards", "Rush TDs"],
    }.get(
        position,
        ["Games", "Targets", "Receptions", "Rec Yards", "Rec TDs", "Rush Att", "Rush Yards", "Rush TDs", "Pass Yards", "Pass TDs"],
    )
    return [
        _with_percentile(by_label[label], ranks.get(label))
        for label in order
        if label in by_label
    ]


def _fantasy_stats(
    groups: Mapping[str, list[dict]],
    games: int | None,
    percentiles: Mapping[str, float] | None = None,
) -> list[dict]:
    ranks = percentiles or {}
    by_label = {str(item.get("label")): item for item in groups.get("Fantasy Stats", [])}
    formats = [
        ("Fantasy PPR", "PPR"),
        ("Half PPR", "Half PPR"),
        ("Fantasy Pts", "Standard"),
    ]
    present = [(source, label, by_label[source]) for source, label in formats if source in by_label]
    distinct_values = {str(item.get("value")) for _source, _label, item in present}
    suffix = f" across {games} games." if games is not None else "."
    if len(present) > 1 and len(distinct_values) == 1:
        source, _label, item = present[-1]
        collapsed = _with_percentile(item, ranks.get(source))
        collapsed["label"] = "Fantasy Points"
        collapsed["note"] = f"Scoring totals are identical across loaded formats{suffix}"
        output = [collapsed]
    else:
        output = []
        for source, label, item in present:
            cloned = _with_percentile(item, ranks.get(source))
            cloned["label"] = label
            cloned["note"] = f"{label} season total{suffix}"
            output.append(cloned)
    if "PPG" in by_label:
        ppg = _with_percentile(by_label["PPG"], ranks.get("PPG"))
        ppg["label"] = "PPR PPG"
        ppg["note"] = f"PPR points per game{suffix}"
        output.append(ppg)
    return output


def _rate(numerator: object, denominator: object) -> float | None:
    num = pd.to_numeric(pd.Series([numerator]), errors="coerce").iloc[0]
    den = pd.to_numeric(pd.Series([denominator]), errors="coerce").iloc[0]
    if pd.isna(num) or pd.isna(den) or den <= 0:
        return None
    return float(num) / float(den)


def _efficiency_stats(
    row: pd.Series,
    games: int | None,
    percentiles: Mapping[str, float] | None = None,
) -> list[dict]:
    """Per-game and per-touch rate stats — season totals alone (e.g. 62
    receptions) don't say whether that came from a bell-cow workload or a
    committee, and coridian_ asked for exactly this: targets/carries per
    game, plus yards per catch/carry. Computed directly from the same raw
    counting columns build_stats_view's other sections already read, not a
    new data source.
    """

    targets = row.get("targets")
    receptions = row.get("receptions")
    receiving_yards = row.get("receiving_yards")
    rush_attempts = row.get("rush_attempts")
    rushing_yards = row.get("rushing_yards")

    candidates: list[tuple[str, float | None, str]] = [
        ("Targets/Gm", _rate(targets, games), "Targets per game played."),
        ("Rec/Gm", _rate(receptions, games), "Receptions per game played."),
        ("Yards/Catch", _rate(receiving_yards, receptions), "Receiving yards per reception."),
        ("Carries/Gm", _rate(rush_attempts, games), "Rush attempts per game played."),
        ("Yards/Carry", _rate(rushing_yards, rush_attempts), "Rushing yards per attempt."),
    ]
    ranks = percentiles or {}
    return [
        _with_percentile(
            {"label": label, "value": f"{value:.1f}", "note": note, "tone": "reference"},
            ranks.get(label),
        )
        for label, value, note in candidates
        if value is not None
    ]


def _usage_stats(
    groups: Mapping[str, list[dict]],
    percentiles: Mapping[str, float] | None = None,
) -> list[dict]:
    ranks = percentiles or {}
    by_label = {str(item.get("label")): item for item in groups.get("Usage", [])}
    return [
        {**_with_percentile(by_label[source], ranks.get(source)), "label": label}
        for source, label in (
            ("Snap Share", "Snap %"),
            ("Route Part.", "Route %"),
            ("Target Share", "Target Share"),
            ("Rush Share", "Carry Share"),
            ("Opportunity Share", "Opportunity"),
        )
        if source in by_label
    ]


def build_stats_view(
    row: pd.Series,
    players_df: pd.DataFrame | None = None,
) -> PlayerQuickViewStats:
    """Build the view from the one regular-season aggregate loaded today.

    The production loader joins exactly one ``stats_season`` record per player.
    It does not retain weekly rows or prior seasons, so this model deliberately
    exposes one season and never invents career totals.

    ``players_df`` is optional and purely additive: when a caller already holds
    the full player frame (the quick-view endpoint loads it to find this row in
    the first place), every stat also carries its position-group percentile so
    "59 rush yards" reads as "59 · 40th pct", and the view carries the 0-99
    ``overall_rating`` summarizing the same pool. Omitting it leaves every
    ``StatItem.percentile`` and ``overall_rating`` as ``None`` and changes
    nothing else.
    """

    groups = _group_items(row)
    games = _integer(row.get("games_played"))
    season = _integer(row.get("stats_season"))
    percentiles = _stat_percentiles(players_df, row)
    season_view = SeasonStatView(
        season=season,
        season_type="Regular Season",
        games=games,
        complete=None,
        key_stats=_items(_key_stats(row, groups, percentiles)),
        fantasy=_items(_fantasy_stats(groups, games, percentiles)),
        usage=_items(_usage_stats(groups, percentiles)),
        efficiency=_items(_efficiency_stats(row, games, percentiles)),
    )
    college = _items(groups.get("College Stats", []))
    has_professional_stats = bool(
        season_view.key_stats or season_view.fantasy or season_view.usage or season_view.efficiency
    )
    return PlayerQuickViewStats(
        seasons=(season_view,) if has_professional_stats else (),
        college=college,
        college_available=bool(college),
        position=_text(row.get("position")),
        overall_rating=_overall_rating(players_df, row),
        prime_window=prime_window_status(row.get("position"), row.get("age")),
    )
