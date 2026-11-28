"""This week's real-player examples for the no-signup /try/start-sit and /try/waivers ad pages.

A public, anonymous composition of data the Phase 2 external advertising endpoints already verify:

- start/sit: the public dynasty board, the nflverse schedule, recency-weighted opponent points allowed by
  position (``external_ad_api.build_lineup_decisions``' inputs) and ``player_projections.project_player_week``;
- waivers: Sleeper's cross-league trending adds and roster percentages (``external_ad_api.build_waiver_replacements``'
  inputs) priced with ``faab.recommend_faab_guidance``.

Nothing is invented. A section is ``None`` (and the page falls back to the labelled made-up sample league) whenever
the season is not in regular-season play or nothing qualifies. Selection is a pure function of the inputs plus the
season/week, so the same data gives the same pick; the result is cached for the week so the ad pipeline sees
stable content. No user, league or roster data is read.
"""

from __future__ import annotations

import hashlib
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from modules import external_ad_api as ads
from modules import faab, season_clock, start_sit_range

CACHE_TTL_SECONDS = 6 * 60 * 60
MAX_CANDIDATES_PER_POSITION = 10
# A genuinely borderline call: projections within this many points, but never a dead heat.
MAX_PROJECTION_GAP = 1.5
MIN_PROJECTION_GAP = 0.3
MIN_PROJECTION = 6.0
# The matchup data must back the call: the start's opponent allows this many pct points more than the sit's.
MIN_MATCHUP_EDGE_PCT = 8.0
PAIR_POOL = 5
MAX_ROSTER_PCT = 50.0
WAIVER_RANK_SLACK = 1.6
WAIVER_PICKS = 2
FAAB_BUDGET = 100

_lock = threading.Lock()
_cache: dict[tuple[int, int], tuple[float, dict[str, Any]]] = {}


def _pick_key(season: int, week: int, *ids: str) -> str:
    return hashlib.sha256(f"{season}:{week}:" .encode() + "|".join(ids).encode()).hexdigest()


def _healthy(row: Mapping[str, Any]) -> bool:
    return not ads._text(row.get("injury_status")) and ads._text(row.get("status")).lower() in {"", "active"}


def _side(row: Mapping[str, Any], proj: Mapping[str, Any], slot: str) -> dict[str, Any]:
    return {
        "player_id": str(row["player_id"]),
        "name": row.get("name"),
        "position": row.get("position"),
        "team": row.get("team"),
        "tier": "starter",
        "slot": slot,
        "points": round(float(proj["point_estimate"]), 1),
        "projection_status": "ok",
        "injury_label": "",
    }


def select_start_sit(
    board: Sequence[Mapping[str, Any]],
    matchups: Mapping[str, Mapping[str, Any]],
    defense: Mapping[str, Mapping[str, Mapping[str, Any]]],
    project: Callable[[str], Mapping[str, Any] | None],
    *,
    season: int,
    week: int,
) -> dict[str, Any] | None:
    league_avg: dict[str, float] = {}
    for pos in ads.OFFENSE_POSITIONS:
        vals = [ads._num(d.get(pos, {}).get("weighted_points_allowed_per_game")) for d in defense.values()]
        vals = [v for v in vals if v is not None]
        if vals:
            league_avg[pos] = sum(vals) / len(vals)

    pool: dict[str, list[dict[str, Any]]] = {}
    for row in sorted(board, key=lambda r: (r.get("position_rank") or 9999, str(r.get("player_id")))):
        pos = ads._text(row.get("position")).upper()
        band = ads.BORDERLINE_BANDS.get(pos)
        rank = row.get("position_rank")
        if not band or not rank or not (band[0] <= rank <= band[1]) or not _healthy(row) or pos not in league_avg:
            continue
        if len(pool.setdefault(pos, [])) >= MAX_CANDIDATES_PER_POSITION:
            continue
        match = matchups.get(ads._text(row.get("team")))
        entry = defense.get(match["opponent"], {}).get(pos) if match else None
        pa = ads._num((entry or {}).get("weighted_points_allowed_per_game"))
        if not match or pa is None or not (entry or {}).get("tier"):
            continue
        proj = project(str(row["player_id"]))
        if not proj or proj.get("status") != "ok" or proj.get("point_estimate") is None:
            continue
        if float(proj["point_estimate"]) < MIN_PROJECTION or proj.get("low") is None or proj.get("high") is None:
            continue
        pool[pos].append({"row": row, "proj": proj, "match": match, "pa": pa, "gap": (pa / league_avg[pos] - 1.0) * 100.0, "tier": entry["tier"]})

    pairs: list[tuple[float, str, dict, dict]] = []
    for pos, cands in pool.items():
        for i, a in enumerate(cands):
            for b in cands[i + 1 :]:
                hi, lo = (a, b) if a["proj"]["point_estimate"] >= b["proj"]["point_estimate"] else (b, a)
                diff = float(hi["proj"]["point_estimate"]) - float(lo["proj"]["point_estimate"])
                if not (MIN_PROJECTION_GAP <= diff <= MAX_PROJECTION_GAP):
                    continue
                if hi["row"].get("team") == lo["row"].get("team") or hi["gap"] - lo["gap"] < MIN_MATCHUP_EDGE_PCT:
                    continue
                pairs.append((round(diff, 3), _pick_key(season, week, str(hi["row"]["player_id"]), str(lo["row"]["player_id"])), hi, lo))
    if not pairs:
        return None
    pairs.sort(key=lambda p: (p[0], p[1]))
    _, _, hi, lo = min(pairs[:PAIR_POOL], key=lambda p: p[1])

    pos = ads._text(hi["row"].get("position")).upper()
    slot = "FLEX" if pos in {"RB", "WR"} else pos

    def rng(c: Mapping[str, Any]) -> dict[str, Any] | None:
        return start_sit_range.range_for({"name": c["row"].get("name"), "projection": c["proj"]}, float(c["proj"]["point_estimate"]))

    def line(c: Mapping[str, Any]) -> str:
        m = c["match"]
        return (
            f"{c['row'].get('name')} {'vs' if m['is_home'] else '@'} {m['opponent']}: they allow {c['pa']:.1f} PPR points per game "
            f"to {pos} ({c['gap']:+.0f}% vs league average, {c['tier']} defense)"
        )

    return {
        "move": {
            "slot": slot,
            "start": _side(hi["row"], hi["proj"], slot),
            "over": _side(lo["row"], lo["proj"], slot),
            "over_reason": None,
            "gain": round(float(hi["proj"]["point_estimate"]) - float(lo["proj"]["point_estimate"]), 1),
            "locked": False,
            "range": {"start": rng(hi), "over": rng(lo), "stance": None, "lean": None},
        },
        "matchup_note": f"{line(hi)}. {line(lo)}.",
        "method": (
            "Two healthy same-position players in the borderline-starter band, projected within "
            f"{MAX_PROJECTION_GAP:g} points of each other this week, where the opponent's points allowed backs the call."
        ),
    }


def select_waivers(
    board: Sequence[Mapping[str, Any]],
    trending: Sequence[Mapping[str, Any]],
    roster_pct: Mapping[str, Mapping[str, Any] | None],
    *,
    season: int,
    week: int,
) -> dict[str, Any] | None:
    by_id = {str(r.get("player_id")): r for r in board}
    cands: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rank, t in enumerate(trending, start=1):
        pid = ads._text(t.get("player_id"))
        row = by_id.get(pid)
        if not pid or pid in seen or not row:
            continue
        seen.add(pid)
        pos = ads._text(row.get("position")).upper()
        pr = row.get("position_rank")
        pct = (roster_pct.get(pid) or {}).get("current")
        count = int(ads._num(t.get("count")) or 0)
        if pos not in ads.STARTER_RANK_LIMIT or not pr or pr > ads.STARTER_RANK_LIMIT[pos] * WAIVER_RANK_SLACK:
            continue
        if not _healthy(row) or pct is None or pct > MAX_ROSTER_PCT or count <= 0:
            continue
        hurt = next(
            (
                h
                for h in board
                if h.get("team") == row.get("team") and ads._text(h.get("position")).upper() == pos and str(h.get("player_id")) != pid
                and ads._is_injured(h) and (h.get("position_rank") or 9999) <= ads.STARTER_RANK_LIMIT[pos]
            ),
            None,
        )
        cands.append({"row": row, "rank": rank, "count": count, "pct": float(pct), "pos": pos, "hurt": hurt})
    if not cands:
        return None
    # Most-added first; the weekly hash only breaks exact ties so the pick is a pure function of the data.
    cands.sort(key=lambda c: (c["rank"], _pick_key(season, week, str(c["row"]["player_id"]))))
    picks = cands[:WAIVER_PICKS]

    adds = []
    for c in picks:
        row = c["row"]
        pos, pr = c["pos"], row["position_rank"]
        starter = pr <= ads.STARTER_RANK_LIMIT[pos]
        guidance = faab.recommend_faab_guidance(
            player_score=int(round(float(row.get("score") or 0))),
            position=pos,
            is_starter=starter,
            budget=FAAB_BUDGET,
            remaining_budget=FAAB_BUDGET,
            injury_need_match=c["hurt"] is not None,
            week=week,
            catalysts=[x for x in [faab.trending_catalyst({"count": c["count"], "rank": c["rank"]})] if x],
        )
        parts = [f"{c['count']:,} adds on Sleeper in the last 24 hours and only {c['pct']:.0f}% rostered"]
        parts.append(f"ranked {pos}{pr} on the dynasty board")
        if c["hurt"] is not None:
            parts.append(f"{c['hurt'].get('name')} ({ads._text(c['hurt'].get('injury_status'))}) is hurt on his team")
        adds.append(
            {
                "player_id": str(row["player_id"]),
                "name": row.get("name"),
                "position": pos,
                "team": row.get("team"),
                "age": row.get("age"),
                "score": row.get("score"),
                "position_rank": pr,
                "overall_rank": row.get("overall_rank"),
                "overall_rating": row.get("overall_rating"),
                "tier": "starter" if starter else "backup",
                "trending_adds_24h": c["count"],
                "trending_rank": c["rank"],
                "roster_pct": c["pct"],
                "injury_cover_for": ads._text(c["hurt"].get("name")) if c["hurt"] is not None else None,
                "reason": ", ".join(parts) + ".",
                "bid": {"low": guidance.low_bid, "high": guidance.high_bid, "budget": FAAB_BUDGET},
            }
        )
    return {
        "adds": adds,
        "method": (
            "Healthy players on Sleeper's cross-league trending-add list, under "
            f"{MAX_ROSTER_PCT:.0f}% rostered, in starter range on the dynasty board; bids are a typical range on a "
            f"${FAAB_BUDGET} FAAB budget."
        ),
    }


def build_examples(
    *,
    board: Sequence[Mapping[str, Any]],
    matchups: Mapping[str, Mapping[str, Any]],
    defense: Mapping[str, Mapping[str, Mapping[str, Any]]],
    trending: Sequence[Mapping[str, Any]],
    roster_pct: Mapping[str, Any],
    project: Callable[[str], Mapping[str, Any] | None],
    season: int,
    week: int,
    now: datetime,
) -> dict[str, Any]:
    return {
        "ok": True,
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "season": season,
        "week": week,
        "start_sit": select_start_sit(board, matchups, defense, project, season=season, week=week) if matchups and defense else None,
        "waivers": select_waivers(board, trending, roster_pct, season=season, week=week) if trending else None,
    }


def _unavailable(reason: str, clock: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    return {
        "ok": True,
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "season": clock.get("season"),
        "week": clock.get("week"),
        "start_sit": None,
        "waivers": None,
        "unavailable_reason": reason,
    }


def get_public_try_examples(db_path: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Cached for the week; never caches an answer with neither section."""

    now = now or datetime.now(timezone.utc)
    clock = ads.clock_info()
    if clock["phase"] != season_clock.PHASE_REGULAR or not clock.get("week"):
        return _unavailable(f"Real-player examples are in-season content; the season clock phase is {clock['phase']}.", clock, now)
    season, week = int(clock["season"]), int(clock["week"])
    key = (season, week)
    mono = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit and mono - hit[0] < CACHE_TTL_SECONDS:
            return hit[1]
    board, _ = ads.load_board(db_path, "1qb")
    if not board:
        return _unavailable("The public dynasty board is unavailable.", clock, now)
    trending = ads.load_trending()
    ids = {str(r["player_id"]) for r in board}
    # Only the latest verified (today/yesterday) snapshot %; no 7-day trend is claimed, so no baseline is required.
    pct = ads.load_roster_pct([p for p in (str(t.get("player_id")) for t in trending) if p in ids], require_baseline=False) if trending else {}
    matchups = ads.week_matchups(ads.load_games(), season, week, ads._team_aliases())
    defense = ads.load_defense(season) if matchups else {}

    def project(player_id: str) -> Mapping[str, Any] | None:
        from modules import player_projections

        try:
            return player_projections.project_player_week(player_id, week, season)
        except Exception:
            return None

    out = build_examples(board=board, matchups=matchups, defense=defense, trending=trending, roster_pct=pct, project=project, season=season, week=week, now=now)
    if not out["start_sit"] and not out["waivers"]:
        out["unavailable_reason"] = "Nothing qualified in the verified data this week."
        return out
    with _lock:
        _cache[key] = (mono, out)
    return out
