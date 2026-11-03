"""Rolling usage trends and role flags, computed from real weekly numbers.

One shared module: Player Quick View, the full profile and the waiver/trade
explanation hooks all call ``build_usage_profile`` so web and mobile can never
disagree about what a player's role is doing.

Inputs (both real, both per week, never estimated):
* Sleeper weekly rows (snap share, targets, receptions, rush attempts, PPR
  points) from ``modules.sleeper``.
* nflverse advanced rows (target share, air-yards share, opportunity share,
  red-zone looks) from ``modules.nflverse_advanced_stats`` (CC BY 4.0).

Windows are the player's last 4 / last 8 *played* games, compared with the
games before the last-4 window ("prior") and the season. Routes run and yards
per route run are NOT computed: no free source with terms that allow a paid
app carries them (see docs/advanced-stats-licensing-2026-11.md); the output
lists them under ``not_available`` instead of approximating.

Minimum-sample rules (all constants below, all enforced in code):
* a rolling average needs >= ``MIN_WINDOW_VALUES`` real values in its window;
* flags need ``MIN_GAMES_FOR_FLAGS`` played games (last 4 + >= 3 prior);
* flags need a season PPR average of ``MIN_RELEVANT_PPG``;
* a window spanning more NFL weeks than ``MAX_WINDOW_SPAN`` (long absence)
  is reported as stale and never flagged.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from modules import model_status
from modules import nflverse_advanced_stats as adv_stats
from modules import sleeper

SHORT_WINDOW = 4
LONG_WINDOW = 8
MIN_WINDOW_VALUES = 3
MIN_PRIOR_GAMES = 3
MIN_GAMES_FOR_FLAGS = SHORT_WINDOW + MIN_PRIOR_GAMES
# last-4 window may span at most 6 NFL weeks (a bye plus one missed game).
MAX_WINDOW_SPAN = {SHORT_WINDOW: 6, LONG_WINDOW: 11}

COVERED_POSITIONS = ("RB", "WR", "TE")

# Absolute change (last 4 vs prior) that counts as a real move, per metric.
# Shares are fractions of 1 (0.08 = 8 percentage points).
MOVE_THRESHOLD = {
    "snap_share": 0.08,
    "target_share": 0.04,
    "air_yards_share": 0.06,
    "opportunity_share": 0.05,
}
OPPS_REL_THRESHOLD = 0.25
OPPS_ABS_THRESHOLD = 2.0
# Below this season PPR average a player's role is not fantasy-relevant, so a
# "role expanding/shrinking" call would only be noise; metrics still show.
MIN_RELEVANT_PPG = 4.0
POINTS_ABS_THRESHOLD = 2.5
POINTS_REL_THRESHOLD = 0.20

PRIMARY_METRICS = {
    "WR": ("snap_share", "target_share", "air_yards_share"),
    "TE": ("snap_share", "target_share", "air_yards_share"),
    "RB": ("snap_share", "opportunity_share"),
}

METRIC_META: dict[str, dict[str, str]] = {
    "snap_share": {"label": "Snap share", "unit": "pct", "source": "sleeper"},
    "target_share": {"label": "Target share", "unit": "pct", "source": "nflverse"},
    "air_yards_share": {"label": "Air yards share", "unit": "pct", "source": "nflverse"},
    "opportunity_share": {"label": "Opportunity share", "unit": "pct", "source": "nflverse"},
    "touches": {"label": "Touches / game", "unit": "count", "source": "sleeper"},
    "opportunities": {"label": "Opportunities / game", "unit": "count", "source": "sleeper"},
    "red_zone_looks": {"label": "Red-zone looks / game", "unit": "count", "source": "nflverse"},
}
RECEIVER_ONLY = {"air_yards_share"}

NOT_AVAILABLE = (
    {
        "key": "routes_run",
        "label": "Routes run / yards per route run",
        "reason": "No free data source with commercial-use terms publishes routes run.",
    },
)

FLAG_COPY = {
    "role_expanding": ("Role expanding", "positive"),
    "role_shrinking": ("Role shrinking", "negative"),
    "positive_regression": ("Usage up, points down", "positive"),
    "unsustainable": ("Points up, usage down", "negative"),
}


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _pts(fraction: float) -> str:
    return f"{fraction * 100:.0f}%"


def _signed_pts(delta: float) -> str:
    return f"{delta * 100:+.0f} pts"


def _played_rows(sleeper_weeks: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_week: dict[int, dict[str, Any]] = {}
    for row in sleeper_weeks or []:
        if not isinstance(row, Mapping) or row.get("week") is None:
            continue
        if sleeper.week_row_fantasy_points_ppr(dict(row)) is None:
            continue
        by_week[int(row["week"])] = dict(row)
    return [by_week[w] for w in sorted(by_week)]


def _num(row: Mapping[str, Any], key: str) -> float:
    # Sleeper omits zero-valued stat keys, so an absent count is a real 0.
    try:
        value = float(row.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return value if value == value else 0.0


def _adv_value(adv_row: Mapping[str, Any] | None, key: str, week: int, through_week: int) -> float | None:
    """Advanced value for one played week. No row for a week the dataset
    already covers means the player recorded no targets/carries (nflverse lists
    only players with a stat), so that is a real zero; a week beyond the
    dataset's coverage is unknown (None), never zero."""

    if adv_row is None:
        return 0.0 if week <= through_week else None
    value = adv_row.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def _weekly_values(
    played: Sequence[dict[str, Any]],
    advanced: Mapping[str, Any],
) -> dict[str, list[tuple[int, float | None]]]:
    available = bool(advanced.get("available"))
    through = int(advanced.get("through_week") or 0)
    adv_weeks: Mapping[int, Mapping[str, Any]] = advanced.get("weeks") or {}
    series: dict[str, list[tuple[int, float | None]]] = {k: [] for k in METRIC_META}
    series["points"] = []
    for row in played:
        week = int(row["week"])
        series["points"].append((week, float(sleeper.week_row_fantasy_points_ppr(row))))
        snap = row.get("snap_share")
        series["snap_share"].append((week, float(snap) if isinstance(snap, (int, float)) else None))
        carries, targets, receptions = _num(row, "rush_attempts"), _num(row, "targets"), _num(row, "receptions")
        series["touches"].append((week, carries + receptions))
        series["opportunities"].append((week, carries + targets))
        adv_row = adv_weeks.get(week) if available else None
        for key in ("target_share", "air_yards_share", "opportunity_share"):
            series[key].append((week, _adv_value(adv_row, key, week, through) if available else None))
        if available:
            if adv_row is None:
                rz = 0.0 if week <= through else None
            else:
                rz = float(adv_row.get("rz_targets") or 0) + float(adv_row.get("rz_carries") or 0)
            series["red_zone_looks"].append((week, rz))
        else:
            series["red_zone_looks"].append((week, None))
    return series


def _window_stat(values: Sequence[tuple[int, float | None]], size: int) -> dict[str, Any]:
    window = list(values)[-size:]
    real = [v for _, v in window if v is not None]
    weeks = [w for w, _ in window]
    span = (weeks[-1] - weeks[0] + 1) if weeks else 0
    stale = len(window) >= size and span > MAX_WINDOW_SPAN[size]
    ok = len(window) >= size and len(real) >= MIN_WINDOW_VALUES and not stale
    return {"value": _mean(real) if ok else None, "n": len(real), "weeks": weeks, "stale": stale}


def _metric_block(key: str, values: Sequence[tuple[int, float | None]]) -> dict[str, Any] | None:
    real_all = [v for _, v in values if v is not None]
    if not real_all:
        return None
    meta = METRIC_META[key]
    short = _window_stat(values, SHORT_WINDOW)
    long_ = _window_stat(values, LONG_WINDOW)
    prior_vals = [v for _, v in list(values)[:-SHORT_WINDOW] if v is not None]
    prior = _mean(prior_vals) if len(prior_vals) >= MIN_PRIOR_GAMES and len(values) > SHORT_WINDOW else None
    delta = (short["value"] - prior) if short["value"] is not None and prior is not None else None
    block = {
        "key": key,
        "label": meta["label"],
        "unit": meta["unit"],
        "source": meta["source"],
        "last4": short["value"],
        "last8": long_["value"],
        "prior": prior,
        "season": _mean(real_all),
        "delta_last4_vs_prior": delta,
        "games_with_data": len(real_all),
    }
    if key == "red_zone_looks":
        block["season_total"] = sum(real_all)
        block["last4_total"] = sum(v for _, v in list(values)[-SHORT_WINDOW:] if v is not None) if short["value"] is not None else None
    return block


def _direction(key: str, block: Mapping[str, Any] | None) -> str:
    """'up' | 'down' | 'flat' | 'unknown' for one metric."""

    if not block or block.get("delta_last4_vs_prior") is None:
        return "unknown"
    if key not in MOVE_THRESHOLD and key != "opportunities":
        return "unknown"  # shown for context; no tested threshold, so no direction
    delta = float(block["delta_last4_vs_prior"])
    if key == "opportunities":
        prior = float(block["prior"] or 0.0)
        threshold = max(OPPS_ABS_THRESHOLD, OPPS_REL_THRESHOLD * prior)
    else:
        threshold = MOVE_THRESHOLD[key]
    if delta >= threshold:
        return "up"
    if delta <= -threshold:
        return "down"
    return "flat"


def _describe(key: str, block: Mapping[str, Any]) -> str:
    label = block["label"].lower()
    if block["unit"] == "pct":
        return (
            f"{label} is {_pts(block['last4'])} over the last {SHORT_WINDOW} games "
            f"vs {_pts(block['prior'])} before ({_signed_pts(block['delta_last4_vs_prior'])})"
        )
    return (
        f"{label.replace(' / game', '')} per game is {block['last4']:.1f} over the last {SHORT_WINDOW} "
        f"vs {block['prior']:.1f} before"
    )


def _points_direction(points_series: Sequence[tuple[int, float | None]]) -> dict[str, Any]:
    block = _metric_block_points(points_series)
    if block is None:
        return {"direction": "unknown"}
    delta = block["delta"]
    threshold = max(POINTS_ABS_THRESHOLD, POINTS_REL_THRESHOLD * max(block["prior"], 0.0))
    direction = "up" if delta >= threshold else "down" if delta <= -threshold else "flat"
    return {**block, "direction": direction}


def _metric_block_points(series: Sequence[tuple[int, float | None]]) -> dict[str, float] | None:
    short = _window_stat(series, SHORT_WINDOW)
    prior_vals = [v for _, v in list(series)[:-SHORT_WINDOW] if v is not None]
    if short["value"] is None or len(prior_vals) < MIN_PRIOR_GAMES:
        return None
    prior = _mean(prior_vals)
    return {"last4": short["value"], "prior": prior, "delta": short["value"] - prior}


def _flags(position: str, blocks: Mapping[str, Mapping[str, Any]], points: Mapping[str, Any]) -> list[dict[str, Any]]:
    primary = list(PRIMARY_METRICS[position])
    # A running back's opportunity share needs the advanced file; without it
    # fall back to raw opportunities per game from Sleeper's box score.
    if position == "RB" and "opportunity_share" not in blocks:
        primary = ["snap_share", "opportunities"]
    directions = {k: _direction(k, blocks.get(k)) for k in primary}
    measured = [k for k, d in directions.items() if d != "unknown"]
    if not measured or points.get("direction") in (None, "unknown"):
        return []
    ups = [k for k in measured if directions[k] == "up"]
    downs = [k for k in measured if directions[k] == "down"]

    def decided(side: list[str], other: list[str]) -> bool:
        if other or not side:
            return False
        # A role call needs corroboration: two independent usage metrics moving
        # the same way, or the only metric we could measure.
        return len(side) >= 2 or len(measured) == 1

    usage = "up" if decided(ups, downs) else "down" if decided(downs, ups) else "steady"
    pts_dir = points["direction"]
    flag_key = None
    if usage == "up":
        flag_key = "positive_regression" if pts_dir == "down" else "role_expanding"
    elif usage == "down":
        flag_key = "unsustainable" if pts_dir == "up" else "role_shrinking"
    if flag_key is None:
        return []
    movers = ups if usage == "up" else downs
    evidence = [_describe(k, blocks[k]) for k in movers]
    ppg = f"PPR points per game are {points['last4']:.1f} over the last {SHORT_WINDOW} vs {points['prior']:.1f} before"
    explanation = {
        "role_expanding": "His role is growing: " + "; ".join(evidence) + f". {ppg}.",
        "role_shrinking": "His role is shrinking: " + "; ".join(evidence) + f". {ppg}.",
        "positive_regression": (
            "Opportunity is rising but points have not followed yet: " + "; ".join(evidence)
            + f". {ppg}. Production often catches up to opportunity, though it is not guaranteed."
        ),
        "unsustainable": (
            "Points are up while opportunity is down: " + "; ".join(evidence)
            + f". {ppg}. Production built on less opportunity is harder to keep up."
        ),
    }[flag_key]
    label, tone = FLAG_COPY[flag_key]
    return [{
        "key": flag_key,
        "label": label,
        "tone": tone,
        "explanation": explanation,
        "evidence_metrics": movers,
    }]


def build_usage_profile(
    position: str,
    sleeper_weeks: Sequence[Mapping[str, Any]],
    advanced: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """The shared usage profile for one player. Pure function of its inputs.

    ``status``: ``not_covered`` (position), ``no_data`` (no played games),
    ``building_sample`` (metrics shown, flags need more games), ``low_usage``
    (too little fantasy relevance to call a trend) or ``ok``.
    ``flags`` is only ever non-empty when ``status == "ok"``.
    """

    pos = str(position or "").strip().upper()
    advanced = dict(advanced or {"available": False, "reason": "advanced_stats_not_provided"})
    base = {
        "position": pos,
        "windows": {"short": SHORT_WINDOW, "long": LONG_WINDOW},
        "not_available": [dict(item) for item in NOT_AVAILABLE],
        "advanced": {
            "available": bool(advanced.get("available")),
            "reason": advanced.get("reason"),
            "through_week": advanced.get("through_week"),
            "as_of": advanced.get("as_of"),
        },
        "attribution": {"text": adv_stats.ATTRIBUTION_TEXT, "url": adv_stats.ATTRIBUTION_URL, "license": adv_stats.LICENSE_NAME},
        "metrics": [],
        "flags": [],
        "headline": None,
    }
    if pos not in COVERED_POSITIONS:
        return {**base, "status": "not_covered", "games_played": 0}
    played = _played_rows(sleeper_weeks)
    if not played:
        return {**base, "status": "no_data", "games_played": 0}

    series = _weekly_values(played, advanced)
    blocks: dict[str, dict[str, Any]] = {}
    for key in METRIC_META:
        if key in RECEIVER_ONLY and pos == "RB":
            continue
        block = _metric_block(key, series[key])
        if block:
            block["direction"] = _direction(key, block)
            blocks[key] = block
    games = len(played)
    short_stale = _window_stat(series["points"], SHORT_WINDOW)["stale"]
    points = _points_direction(series["points"])
    season_ppg = _mean([v for _, v in series["points"] if v is not None]) or 0.0
    irrelevant = season_ppg < MIN_RELEVANT_PPG
    can_flag = games >= MIN_GAMES_FOR_FLAGS and not short_stale and not irrelevant
    flags = _flags(pos, blocks, points) if can_flag else []
    if irrelevant and games >= MIN_GAMES_FOR_FLAGS:
        status_note = f"Averaging under {MIN_RELEVANT_PPG:.0f} PPR points a game, so a role trend would be noise."
    elif short_stale:
        status_note = "Recent games are spread across a long absence, so trend flags are held back."
    elif games < MIN_GAMES_FOR_FLAGS:
        status_note = f"Trend flags need {MIN_GAMES_FOR_FLAGS} played games; this player has {games}."
    else:
        status_note = None
    return {
        **base,
        "status": "ok" if can_flag else ("low_usage" if irrelevant and games >= MIN_GAMES_FOR_FLAGS else "building_sample"),
        "season_ppg": season_ppg,
        "status_note": status_note,
        "games_played": games,
        "metrics": [blocks[k] for k in METRIC_META if k in blocks],
        "points": {k: v for k, v in points.items()} if points.get("direction") != "unknown" else None,
        "flags": flags,
        "headline": flags[0]["explanation"] if flags else None,
    }


def profile_for_player(sleeper_id: Any, position: str, *, season: int | None = None) -> dict[str, Any]:
    """Convenience loader: cached Sleeper weeks + the advanced file, no network."""

    selected = int(season or sleeper.default_player_stats_season())
    weeks = sleeper.cached_season_player_weekly(str(sleeper_id or ""), selected)
    advanced = adv_stats.weekly_for_sleeper_id(sleeper_id, selected)
    profile = build_usage_profile(position, weeks, advanced)
    profile["season"] = selected
    return profile


# --------------------------------------------------------------------------
# Pro gate (owner decision 2026-11-03): advanced usage is a Pro feature.
#
# Free keeps the player's own Sleeper-basic usage that is already free in the
# profile/rankings (snap share, target share, touches and opportunities per
# game, season values only). Everything else is withheld on the server, never
# by the client: air-yards share, opportunity share, red-zone looks, the
# last-4 / last-8 windows and deltas, the points-vs-usage read, and every role
# flag. The Free payload carries a gating marker and a static list of what Pro
# unlocks (no data-dependent hint such as "this player has a flag").

FREE_METRIC_KEYS = ("snap_share", "target_share", "touches", "opportunities")
FREE_METRIC_FIELDS = ("key", "label", "unit", "source", "season", "games_with_data")
#: percentile-explorer stats that exist only for advanced usage metrics.
ADVANCED_EXPLORER_STATS = frozenset({"air_yards_share", "opportunity", "red_zone_looks"})
PRO_UNLOCKS = (
    "Air-yards share",
    "Opportunity share",
    "Red-zone looks per game",
    "Last-4 and last-8 game trends",
    "Role flags: expanding, shrinking, usage vs points",
)
PRO_GATE = {
    "gated": True,
    "required": "pro",
    "unlocks": list(PRO_UNLOCKS),
    "upsell": {
        "title": "Advanced usage is a Pro feature",
        "body": "Pro adds air-yards share, red-zone looks, last-4 and last-8 trends and role flags to every player.",
    },
}
#: Keys that must never appear in a Free usage payload (tests pin this).
ADVANCED_PROFILE_KEYS = frozenset({"last4", "last8", "prior", "delta_last4_vs_prior", "direction", "season_total", "last4_total"})


def free_view(profile: Mapping[str, Any]) -> dict[str, Any]:
    """The Free-safe copy of a usage profile (see the Pro gate above)."""

    if profile.get("status") in {"unavailable", "not_covered"}:
        return {**{k: v for k, v in profile.items() if k in {"status", "reason", "position", "season"}},
                "metrics": [], "flags": [], "headline": None, "gating": dict(PRO_GATE), "gated": True}
    metrics = [
        {k: m.get(k) for k in FREE_METRIC_FIELDS}
        for m in profile.get("metrics", [])
        if m.get("key") in FREE_METRIC_KEYS
    ]
    return {
        "status": "pro_required" if not metrics else "free",
        "position": profile.get("position"),
        "season": profile.get("season"),
        "games_played": profile.get("games_played"),
        "season_ppg": profile.get("season_ppg"),
        "not_available": [dict(item) for item in NOT_AVAILABLE],
        "attribution": profile.get("attribution"),
        "metrics": metrics,
        "flags": [],
        "headline": None,
        "gated": True,
        "gating": dict(PRO_GATE),
    }


def role_change_line(name: str, flag: Mapping[str, Any] | None) -> str | None:
    """One display-only line for a role flag (Pro surfaces only; never a score)."""

    if not flag or not flag.get("label") or not flag.get("explanation"):
        return None
    return f"{name}: {str(flag['label']).lower()}. {flag['explanation'][:1].upper()}{flag['explanation'][1:]}."


def role_change_line_for_player(player_id: Any, position: str, name: str, *, season: int | None = None) -> str | None:
    """Role line from cached Sleeper weeks + the advanced file (no network)."""

    if str(position or "").upper() not in COVERED_POSITIONS:
        return None
    try:
        profile = profile_for_player(player_id, position, season=season)
    except model_status.LOOKUP_ERRORS:
        return None
    flags = profile.get("flags") or []
    return role_change_line(name, flags[0]) if flags else None


# --------------------------------------------------------------------------
# Season-level pool: one row per covered player, for percentiles + explorer.

#: Games a player needs before his season average may enter a percentile pool.
MIN_POOL_GAMES = 4
#: metric key -> percentile explorer stat key (modules.percentile_explorer).
EXPLORER_KEYS = {
    "snap_share": "snap",
    "target_share": "target_share",
    "air_yards_share": "air_yards_share",
    "opportunity_share": "opportunity",
    "red_zone_looks": "red_zone_looks",
}
POOL_METRICS = tuple(EXPLORER_KEYS)

_POOL_CACHE: dict[tuple, Any] = {}


def _season_cache_path(season: int) -> str:
    return sleeper.PLAYER_STATS_CACHE_TEMPLATE.format(season=season)


def season_pool_table(season: int | None = None):
    """DataFrame indexed by Sleeper id: ``games`` plus each pool metric's season
    mean over played games, for every RB/WR/TE with at least ``MIN_POOL_GAMES``
    games. Built from the same weekly series as ``build_usage_profile`` so a
    player's displayed season number equals his pool value. Empty (not an
    error) when the Sleeper cache is missing. Re-read only when either source
    file changes."""

    import json
    import os

    import pandas as pd

    selected = int(season or sleeper.default_player_stats_season())
    cache_path = _season_cache_path(selected)
    adv_path = adv_stats.DATA_PATH_TEMPLATE.format(season=selected)

    def _mtime(path: str) -> float:
        try:
            return os.path.getmtime(path)
        except OSError:
            return -1.0

    key = (selected, _mtime(cache_path), _mtime(adv_path))
    cached = _POOL_CACHE.get("table")
    if cached and cached[0] == key:
        return cached[1]
    columns = ["position", "games", *POOL_METRICS]
    rows: dict[str, dict[str, Any]] = {}
    if key[1] >= 0:
        with open(cache_path, "r", encoding="utf-8") as handle:
            season_stats = json.load(handle)
        payload = adv_stats.load_season(selected)
        by_sid = {}
        if payload:
            by_sid = {rec["sleeper_id"]: rec for rec in payload.get("players", {}).values() if rec.get("sleeper_id")}
        for sid, record in season_stats.items():
            weekly = record.get("weekly") if isinstance(record, Mapping) else None
            rec = by_sid.get(sid)
            position = (rec or {}).get("position") or str(record.get("position") or "").upper()
            if not weekly or position not in COVERED_POSITIONS:
                continue
            played = _played_rows(weekly)
            if len(played) < MIN_POOL_GAMES:
                continue
            advanced = (
                {
                    "available": True,
                    "through_week": int(payload.get("through_week") or 0),
                    "weeks": {int(w): row for w, row in rec["weeks"].items()},
                }
                if rec
                else {"available": False}
            )
            series = _weekly_values(played, advanced)
            row: dict[str, Any] = {"position": position, "games": len(played)}
            for metric in POOL_METRICS:
                vals = [v for _, v in series[metric] if v is not None]
                row[metric] = _mean(vals) if vals else None
            rows[str(sid)] = row
    table = pd.DataFrame.from_dict(rows, orient="index", columns=columns)
    _POOL_CACHE["table"] = (key, table)
    return table

def explanation_hook(
    player_id: Any,
    position: str,
    season_stats: Mapping[str, Any] | None,
    *,
    season: int | None = None,
) -> dict[str, Any]:
    """Display-only usage flag for recommendation surfaces (waivers, trades).

    Takes the season stats the caller already loaded (``retain_weekly``) so a
    list of players costs no extra file reads. Returns ``{"status", "flag"}``:
    ``flag`` is the first role flag (key/label/tone/explanation) or ``None``;
    ``status`` says *why* there is no flag (``building_sample``, ``low_usage``,
    ``ok`` meaning evaluated and nothing notable, ``no_data``, ``not_covered``)
    or ``unavailable`` when the caller had no weekly stats at all. It never
    feeds a score or ranking.
    """

    record = (season_stats or {}).get(str(player_id or ""))
    weekly = record.get("weekly") if isinstance(record, Mapping) else None
    if not weekly:
        return {"status": "unavailable", "flag": None}
    selected = int(season or sleeper.default_player_stats_season())
    profile = build_usage_profile(position, weekly, adv_stats.weekly_for_sleeper_id(player_id, selected))
    flag = profile["flags"][0] if profile["flags"] else None
    return {
        "status": profile["status"],
        "flag": {k: flag[k] for k in ("key", "label", "tone", "explanation")} if flag else None,
    }


def profile_from_season_stats(
    player_id: Any,
    position: str,
    season_stats: Mapping[str, Any] | None,
    *,
    season: int | None = None,
) -> dict[str, Any] | None:
    """The full usage profile for a player from already-loaded season stats
    (``retain_weekly``), or ``None`` when no weekly rows are loaded for him.

    Same inputs and gate as ``explanation_hook``; used by the drop engine as a
    guard (never as a score)."""

    record = (season_stats or {}).get(str(player_id or ""))
    weekly = record.get("weekly") if isinstance(record, Mapping) else None
    if not weekly:
        return None
    selected = int(season or sleeper.default_player_stats_season())
    return build_usage_profile(position, weekly, adv_stats.weekly_for_sleeper_id(player_id, selected))
