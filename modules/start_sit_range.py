"""Start/sit floor and ceiling: show each player's range and say when it matters.

Inputs are numbers the Matchup page already has:

- each player's weekly ``projection`` (``point_estimate`` plus the ``low`` and
  ``high`` of the projection's typical-week range; see
  ``player_projections._band_half_width``, a recency-weighted standard
  deviation either side of the estimate, widened for small samples), and
- this matchup's win probability (``matchup_win_probability``).

``low`` and ``high`` are labeled exactly that: a typical-week range, not a
percentile, not a boom/bust probability and not a guaranteed floor or ceiling.
No distribution is assumed beyond what the win-probability model already uses.

The lean (when it fires) is plain arithmetic over those numbers:

- a heavy underdog needs a big week, so the higher ``high`` is favored;
- a heavy favorite needs to protect the lead, so the higher ``low`` is favored;
- either lean only overrides the projection when the range edge clearly
  outweighs the projected points given up (``MAX_GIVEUP_RATIO``), and never
  when the edge is inside rounding noise (``MIN_RANGE_EDGE``);
- in between (a toss-up), or with no win probability, there is no lean and the
  client just shows the numbers.

The thresholds are product judgment calls, named here so they can be tuned in
one place.
"""

from __future__ import annotations

from typing import Any, Mapping

# "Heavy" underdog/favorite: this matchup's win probability at or beyond these.
HEAVY_UNDERDOG_AT_OR_BELOW = 0.30
HEAVY_FAVORITE_AT_OR_ABOVE = 0.70
# A range edge smaller than this many points is noise.
MIN_RANGE_EDGE = 1.5
# The player with the better range may give up at most this fraction of the
# range edge in projected points and still be the lean.
MAX_GIVEUP_RATIO = 0.5


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _a(pct: int) -> str:
    """"a" or "an" before a spoken percentage (an 8, 11, 18 or 80s percent)."""

    return "an" if pct in (8, 11, 18) or 80 <= pct <= 89 else "a"


def range_for(player: Mapping[str, Any] | None, points: float | None) -> dict[str, Any] | None:
    """{name, projected, low, high} for one player, or None with no real range.

    `points` is the same expected-points figure the win probability uses
    (``matchup_win_probability.starter_expected_points``); a bye/out player
    passes 0.0 and has no range. low/high are only ever read from a projection
    whose status is "ok" and whose game has not kicked off.
    """

    if player is None or points is None:
        return None
    if player.get("game_started") is True:
        return None  # a started game's points are partly real; the pregame range no longer applies
    projection = player.get("projection") or {}
    if projection.get("status") != "ok":
        return None
    low, high = _number(projection.get("low")), _number(projection.get("high"))
    if low is None or high is None or high < low:
        return None
    return {
        "name": str(player.get("name") or ""),
        "projected": round(float(points), 1),
        "low": round(low, 1),
        "high": round(high, 1),
    }


def stance(win_probability: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """The matchup stance from the real win probability, or None if unavailable."""

    if not win_probability or win_probability.get("available") is not True:
        return None
    probability = _number(win_probability.get("probability"))
    if probability is None:
        return None
    if probability <= HEAVY_UNDERDOG_AT_OR_BELOW:
        kind = "underdog"
    elif probability >= HEAVY_FAVORITE_AT_OR_ABOVE:
        kind = "favorite"
    else:
        kind = "toss_up"
    return {"kind": kind, "win_pct": round(probability * 100)}


def lean(
    first: Mapping[str, Any] | None,
    second: Mapping[str, Any] | None,
    matchup_stance: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Which of two ranges to favor and why, or None when there is no lean.

    ``first``/``second`` are ``range_for`` dicts. Returns {"kind": "ceiling" |
    "floor", "favors": "first" | "second", "why": str}.
    """

    if not first or not second or not matchup_stance:
        return None
    mode = matchup_stance.get("kind")
    if mode == "underdog":
        key, kind, word = "high", "ceiling", "ceiling"
        frame = f"You are {_a(matchup_stance['win_pct'])} {matchup_stance['win_pct']}% underdog this week, so you need a big game"
    elif mode == "favorite":
        key, kind, word = "low", "floor", "floor"
        frame = f"You are {_a(matchup_stance['win_pct'])} {matchup_stance['win_pct']}% favorite this week, so protect the lead"
    else:
        return None

    edge = first[key] - second[key]  # positive: first has the better range
    if abs(edge) < MIN_RANGE_EDGE:
        return None
    better, worse, favors = (first, second, "first") if edge > 0 else (second, first, "second")
    giveup = round(worse["projected"] - better["projected"], 1)  # projected points the better range costs
    if giveup > MAX_GIVEUP_RATIO * abs(edge):
        return None

    label = f"{key} {better[key]:.0f} vs {worse[key]:.0f}"
    if giveup <= 0:
        detail = f"{better['name']} has the higher {word} ({label}) and the higher projection."
    else:
        detail = (
            f"{better['name']} has the higher {word} ({label}) for {giveup:.1f} fewer projected points, "
            f"which is worth it here."
        )
    return {"kind": kind, "favors": favors, "why": f"{frame}. {detail}"}


def compare(
    first_player: Mapping[str, Any] | None,
    first_points: float | None,
    second_player: Mapping[str, Any] | None,
    second_points: float | None,
    win_probability: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Side-by-side ranges for two players plus the stance-aware lean."""

    first = range_for(first_player, first_points)
    second = range_for(second_player, second_points)
    matchup_stance = stance(win_probability)
    return {
        "first": first,
        "second": second,
        "stance": matchup_stance,
        "lean": lean(first, second, matchup_stance),
    }
