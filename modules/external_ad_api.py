"""Adaptive advertising API (read-only) for the desktop ad app.

Everything under ``/v1/external/promo/*``-style routes added here is built from
data the app already verifies (the public dynasty board, nflverse schedule,
Sleeper directory/trending, stored rating/ADP/depth-chart snapshots) and the
two existing clocks: ``modules.season_clock`` (phase/week) and
``modules.league_calendar`` (deadline phase on a *reference* league: no user's
league is ever read).

Contract rules, enforced by ``finalize`` and ``item``:

* every item carries ``timestamp``, ``evidence``, ``methodology``,
  ``confidence``, ``freshness`` and ``unavailable_reason``;
* an endpoint with nothing to say returns ``status: "unavailable"`` with a
  reason, never a filler item;
* no private user data is read, no network call is made by the pure builders
  (``build_*``); the ``endpoint_*`` wrappers do the I/O through the module-level
  ``load_*`` providers, which tests replace.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode

from modules import brand_identity, league_calendar, season_clock
from modules.coerce import float_nan_to_none as _num

CONTRACT_VERSION = "ad-api-v1"
CONFIDENCE_LEVELS = ("low", "medium", "high")
STALE_AFTER_HOURS = 36.0

OFFENSE_POSITIONS = ("QB", "RB", "WR", "TE")
FORMATS = ("1qb", "superflex")
LEAGUE_TYPES = ("dynasty", "redraft", "both")

# Reference league used only to reuse league_calendar's deadline logic for
# phase labelling. Sleeper deadlines are commissioner-set (observed 11-14);
# this is a stated assumption, not any real league.
REFERENCE_TRADE_DEADLINE_WEEK = 12
FANTASY_PLAYOFF_WEEKS = (15, 16, 17)

INJURED_STATUSES = frozenset({"out", "ir", "pup", "doubtful", "sus", "suspended", "nfi"})
STARTER_RANK_LIMIT = {"QB": 16, "RB": 30, "WR": 40, "TE": 14}
# (first, last) position rank where a start/sit call is a real decision.
BORDERLINE_BANDS = {"QB": (9, 20), "RB": (13, 36), "WR": (13, 48), "TE": (6, 14)}
MIN_RATING_DELTA = 2


# --------------------------------------------------------------------------
# Shared contract helpers
# --------------------------------------------------------------------------


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def freshness(as_of: str | datetime | None, now: datetime, *, source: str) -> dict[str, Any]:
    """Honest freshness block. ``as_of`` None means the source gave no date."""

    parsed: datetime | None = None
    if isinstance(as_of, datetime):
        parsed = as_of if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
    elif as_of:
        try:
            parsed = datetime.fromisoformat(str(as_of).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            parsed = None
    if parsed is None:
        return {"data_as_of": None, "age_hours": None, "stale": None, "source": source}
    age = round(max(0.0, (now - parsed).total_seconds()) / 3600.0, 1)
    return {"data_as_of": _iso(parsed), "age_hours": age, "stale": age > STALE_AFTER_HOURS, "source": source}


def evidence_row(source: str, label: str, value: Any, *, as_of: str | None = None) -> dict[str, Any]:
    return {"source": source, "label": label, "value": value, "as_of": as_of}


def item(
    item_id: str,
    kind: str,
    *,
    now: datetime,
    headline: str | None,
    evidence: Sequence[Mapping[str, Any]],
    methodology: str,
    confidence: str,
    fresh: Mapping[str, Any],
    relevance: Mapping[str, str] | None = None,
    unavailable_reason: str | None = None,
    **fields: Any,
) -> dict[str, Any]:
    if confidence not in CONFIDENCE_LEVELS:
        raise ValueError(f"confidence must be one of {CONFIDENCE_LEVELS}")
    out: dict[str, Any] = {
        "id": item_id,
        "kind": kind,
        "timestamp": _iso(now),
        "headline": headline,
        "evidence": [dict(e) for e in evidence],
        "methodology": methodology,
        "confidence": confidence,
        "freshness": dict(fresh),
        "relevance": dict(relevance) if relevance else None,
        "unavailable_reason": unavailable_reason,
    }
    out.update(fields)
    return out


def _stable_id(*parts: object) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:12]


def clock_info(today: date | None = None) -> dict[str, Any]:
    clock = season_clock.season_clock(today)
    return {"season": clock.season, "phase": clock.phase, "week": clock.week, "source": clock.source}


def finalize(
    endpoint: str,
    *,
    now: datetime,
    clock: Mapping[str, Any],
    methodology: str,
    items: list[dict[str, Any]],
    fresh: Mapping[str, Any],
    unavailable_reason: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Standard envelope. Empty -> ``unavailable`` + a reason (never silent)."""

    if not items:
        status = "unavailable"
        reason = unavailable_reason or "No qualifying items were found in the verified data."
    else:
        status = "ok"
        reason = None
    payload: dict[str, Any] = {
        "ok": True,
        "contract_version": CONTRACT_VERSION,
        "endpoint": endpoint,
        "status": status,
        "unavailable_reason": reason,
        "generated_at": _iso(now),
        "season": clock.get("season"),
        "phase": clock.get("phase"),
        "week": clock.get("week"),
        "clock_source": clock.get("source"),
        "methodology": methodology,
        "freshness": dict(fresh),
        "count": len(items),
        "items": items,
    }
    if extra:
        payload.update(extra)
    return payload


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


# --------------------------------------------------------------------------
# 1. Seasonal content plan
# --------------------------------------------------------------------------

MODULES: dict[str, dict[str, str]] = {
    "playoff_sos": {"endpoint": "/v1/external/playoff-sos", "title": "Fantasy playoff strength of schedule", "readiness": "ready"},
    "lineup_decisions": {"endpoint": "/v1/external/lineup/decisions", "title": "Matchup-driven start/sit calls", "readiness": "ready"},
    "waiver_replacements": {"endpoint": "/v1/external/waivers/replacements", "title": "Injury replacement opportunities", "readiness": "ready"},
    "dynasty_value_changes": {"endpoint": "/v1/external/dynasty/value-changes", "title": "Dynasty value risers and fallers", "readiness": "ready"},
    "rookies": {"endpoint": "/v1/external/rookies", "title": "Rookie rankings, ADP and landing spots", "readiness": "prepared"},
    "depth_chart_changes": {"endpoint": "/v1/external/changes", "title": "Depth-chart and team changes", "readiness": "prepared"},
    "roster_construction": {"endpoint": "/v1/external/dynasty/roster-construction", "title": "Dynasty rebuild and roster construction", "readiness": "prepared"},
    "demo_scenarios": {"endpoint": "/v1/external/demo/scenarios", "title": "Product demonstration scenarios", "readiness": "ready"},
}

# sub-phase -> module -> (dynasty, redraft, reason)
_PLAN: dict[str, dict[str, tuple[float, float, str]]] = {
    "fantasy_playoffs": {
        "playoff_sos": (0.9, 0.95, "Fantasy playoffs are underway or one week away; schedule strength for weeks 15-17 decides lineups."),
        "lineup_decisions": (0.7, 1.0, "Every start/sit call is elimination-week stakes."),
        "waiver_replacements": (0.5, 0.95, "Injury replacements matter most when a loss ends the season."),
        "dynasty_value_changes": (0.6, 0.2, "Dynasty values keep moving, but redraft managers are focused on this week."),
        "demo_scenarios": (0.4, 0.4, "Evergreen product demos."),
    },
    "playoff_push": {
        "playoff_sos": (0.8, 0.95, "Playoff schedules are the planning question before the bracket starts."),
        "lineup_decisions": (0.7, 0.9, "Seeding is on the line each week."),
        "waiver_replacements": (0.55, 0.9, "Stash and replace before the playoffs begin."),
        "dynasty_value_changes": (0.65, 0.3, "Late-season risers and fallers reshape dynasty boards."),
        "demo_scenarios": (0.4, 0.4, "Evergreen product demos."),
    },
    "deadline_window": {
        "dynasty_value_changes": (0.95, 0.4, "Trade-deadline window: value movement drives buy and sell decisions."),
        "playoff_sos": (0.7, 0.85, "Contenders trade for favorable playoff schedules before the deadline."),
        "waiver_replacements": (0.6, 0.85, "Injuries mid-season create waiver and trade pressure."),
        "lineup_decisions": (0.6, 0.9, "Weekly matchup calls."),
        "demo_scenarios": (0.5, 0.5, "Trade-analyzer style demos fit the deadline."),
    },
    "in_season": {
        "lineup_decisions": (0.6, 0.95, "Weekly start/sit is the core in-season content."),
        "waiver_replacements": (0.55, 0.95, "Waiver and injury replacements every week."),
        "dynasty_value_changes": (0.8, 0.3, "Dynasty values move with usage and production."),
        "playoff_sos": (0.5, 0.6, "Early playoff-schedule previews."),
        "demo_scenarios": (0.5, 0.5, "Evergreen product demos."),
    },
    "season_end": {
        "dynasty_value_changes": (0.9, 0.2, "The season is ending; dynasty valuation resets begin."),
        "roster_construction": (0.7, 0.05, "Offseason roster planning starts."),
        "demo_scenarios": (0.5, 0.4, "Evergreen product demos."),
    },
    "nfl_postseason": {
        "dynasty_value_changes": (0.9, 0.1, "Fantasy seasons are over; dynasty values are the live conversation."),
        "roster_construction": (0.8, 0.05, "Rebuild-or-contend planning for next year."),
        "rookies": (0.6, 0.1, "Draft-class previews begin."),
        "demo_scenarios": (0.6, 0.4, "Offseason is the time to try the product."),
    },
    "free_agency": {
        "depth_chart_changes": (0.85, 0.7, "Free agency and team changes reshape roles."),
        "rookies": (0.8, 0.3, "Draft-class rankings and ADP build toward the draft."),
        "dynasty_value_changes": (0.85, 0.15, "Dynasty values react to signings and trades."),
        "roster_construction": (0.8, 0.05, "Offseason is rebuild planning time."),
        "demo_scenarios": (0.6, 0.4, "Offseason is the time to try the product."),
    },
    "draft_season": {
        "rookies": (1.0, 0.5, "NFL Draft window: rookie rankings, ADP and landing spots."),
        "depth_chart_changes": (0.8, 0.6, "Draft capital changes depth charts."),
        "dynasty_value_changes": (0.8, 0.15, "Rookie pick values move daily."),
        "roster_construction": (0.7, 0.05, "Post-draft roster planning."),
        "demo_scenarios": (0.5, 0.4, "Evergreen product demos."),
    },
    "post_draft": {
        "rookies": (0.95, 0.6, "Rookies have landing spots; rookie ADP is the live question."),
        "depth_chart_changes": (0.8, 0.7, "Early depth charts and competition."),
        "dynasty_value_changes": (0.8, 0.2, "Post-draft value re-pricing."),
        "roster_construction": (0.7, 0.05, "Dynasty roster construction after the draft."),
        "demo_scenarios": (0.55, 0.5, "Evergreen product demos."),
    },
    "training_camp": {
        "depth_chart_changes": (0.85, 0.9, "Camp battles and depth-chart developments."),
        "rookies": (0.8, 0.8, "Rookie camp reports and ADP."),
        "dynasty_value_changes": (0.7, 0.3, "Camp news moves dynasty values."),
        "demo_scenarios": (0.6, 0.6, "Draft season is the time to try the product."),
    },
}


def sub_phase(clock: Mapping[str, Any], today: date) -> str:
    """Map the season clock (+ reference league calendar) to a content sub-phase."""

    phase, week = clock.get("phase"), clock.get("week")
    if phase == season_clock.PHASE_REGULAR and week:
        league = {"status": "in_season", "settings": {"trade_deadline": REFERENCE_TRADE_DEADLINE_WEEK, "leg": int(week)}}
        if int(week) >= max(FANTASY_PLAYOFF_WEEKS):
            return "season_end" if int(week) > max(FANTASY_PLAYOFF_WEEKS) else "fantasy_playoffs"
        if int(week) >= min(FANTASY_PLAYOFF_WEEKS):
            return "fantasy_playoffs"
        if int(week) == min(FANTASY_PLAYOFF_WEEKS) - 1:
            return "playoff_push"
        left = league_calendar.weeks_to_deadline(league)
        if left is not None and left <= 2:
            return "deadline_window"
        return "in_season"
    if phase == season_clock.PHASE_POST:
        return "nfl_postseason"
    if phase == season_clock.PHASE_PRESEASON:
        return "training_camp"
    # offseason: calendar months (Sleeper exposes no draft/FA dates).
    if today.month in (1, 2) or (today.month == 3 and today.day < 10):
        return "free_agency" if today.month == 3 else "nfl_postseason"
    if today.month in (3, 4):
        return "draft_season" if today.month == 4 else "free_agency"
    if season_clock.DRAFT_COMPLETE_MONTH <= today.month <= 6:
        return "post_draft"
    return "training_camp"


def build_content_plan(
    clock: Mapping[str, Any],
    today: date,
    now: datetime,
    *,
    league_type: str = "both",
    exclude_ids: Sequence[str] = (),
    limit: int = 8,
) -> dict[str, Any]:
    if league_type not in LEAGUE_TYPES:
        raise ValueError("league_type must be one of: " + ", ".join(LEAGUE_TYPES))
    sub = sub_phase(clock, today)
    table = _PLAN.get(sub, {})
    excluded = {x for x in exclude_ids if x}
    base_conf = "high" if clock.get("source") == "sleeper" else "medium"
    fresh = freshness(now, now, source=f"season_clock:{clock.get('source')}")
    rows = []
    for module_id, (dyn, red, reason) in table.items():
        if module_id in excluded:
            continue
        score = dyn if league_type == "dynasty" else red if league_type == "redraft" else round((dyn + red) / 2, 3)
        meta = MODULES[module_id]
        rows.append((score, module_id, dyn, red, reason, meta))
    rows.sort(key=lambda r: (-r[0], r[1]))
    items = []
    for score, module_id, dyn, red, reason, meta in rows[:limit]:
        if score <= 0:
            continue
        items.append(
            item(
                module_id,
                "content_module",
                now=now,
                headline=meta["title"],
                evidence=[
                    evidence_row("season_clock", "phase", clock.get("phase")),
                    evidence_row("season_clock", "week", clock.get("week")),
                    evidence_row("content_plan", "sub_phase", sub),
                    evidence_row("league_calendar", "reference_trade_deadline_week", REFERENCE_TRADE_DEADLINE_WEEK),
                ],
                methodology=(
                    "Relevance is a fixed product table keyed on the season-clock phase/week (and a reference league "
                    "calendar for deadline timing), not a prediction of engagement."
                ),
                confidence=base_conf,
                fresh=fresh,
                relevance={"dynasty": _level(dyn), "redraft": _level(red)},
                module=module_id,
                endpoint=meta["endpoint"],
                readiness=meta["readiness"],
                relevance_score=score,
                relevance_dynasty=dyn,
                relevance_redraft=red,
                reason=reason,
            )
        )
    return finalize(
        "/v1/external/promo/plan",
        now=now,
        clock=clock,
        methodology="Phase-aware ranking of the ad API's own content modules. See each item's methodology.",
        items=items,
        fresh=fresh,
        unavailable_reason="No content modules are relevant for the current phase.",
        extra={
            "sub_phase": sub,
            "league_type": league_type,
            "as_of_date": today.isoformat(),
            "reference_calendar": {
                "trade_deadline_week": REFERENCE_TRADE_DEADLINE_WEEK,
                "fantasy_playoff_weeks": list(FANTASY_PLAYOFF_WEEKS),
                "note": "Reference assumptions for planning content. Real leagues set their own deadlines and playoff weeks.",
            },
        },
    )


def _level(score: float) -> str:
    return "high" if score >= 0.75 else "medium" if score >= 0.4 else "low"


# --------------------------------------------------------------------------
# 2. Fantasy playoff strength of schedule
# --------------------------------------------------------------------------


def _confidence_from_sample(games_sampled: Sequence[int], rated: int, total: int) -> str:
    if not games_sampled or rated == 0:
        return "low"
    avg = sum(games_sampled) / len(games_sampled)
    if rated == total and avg >= 8:
        return "high"
    if avg >= 4:
        return "medium"
    return "low"


def build_playoff_sos(
    games: Any,
    defense: Mapping[str, Mapping[str, Mapping[str, Any]]],
    *,
    season: int,
    weeks: Sequence[int],
    now: datetime,
    defense_as_of: str | None,
    team_aliases: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """One item per team. ``defense`` is team_defense_points_allowed_by_position's shape."""

    if games is None or getattr(games, "empty", True) or not defense:
        return []
    aliases = team_aliases or {}
    df = games[games["season"] == season]
    if "game_type" in df.columns:
        df = df[df["game_type"] == "REG"]
    df = df[df["week"].isin(list(weeks))]
    if df.empty:
        return []
    schedule: dict[str, dict[int, tuple[str, bool]]] = {}
    for _, g in df.iterrows():
        home = aliases.get(str(g["home_team"]), str(g["home_team"]))
        away = aliases.get(str(g["away_team"]), str(g["away_team"]))
        schedule.setdefault(home, {})[int(g["week"])] = (away, True)
        schedule.setdefault(away, {})[int(g["week"])] = (home, False)

    league_avg: dict[str, float] = {}
    for pos in OFFENSE_POSITIONS:
        vals = [_num(d.get(pos, {}).get("weighted_points_allowed_per_game")) for d in defense.values()]
        vals = [v for v in vals if v is not None]
        if vals:
            league_avg[pos] = sum(vals) / len(vals)

    fresh = freshness(defense_as_of, now, source="nflverse_games+sleeper_weekly_stats")
    team_rows: list[dict[str, Any]] = []
    for team in sorted(schedule):
        opponents = [
            {"week": w, "opponent": schedule[team][w][0], "is_home": schedule[team][w][1]}
            if w in schedule[team]
            else {"week": w, "opponent": None, "is_home": None, "bye": True}
            for w in weeks
        ]
        by_pos: dict[str, Any] = {}
        sampled: list[int] = []
        rated_total = 0
        for pos in OFFENSE_POSITIONS:
            vals = []
            for opp in opponents:
                if opp.get("opponent") is None:
                    continue
                entry = defense.get(opp["opponent"], {}).get(pos)
                v = _num((entry or {}).get("weighted_points_allowed_per_game"))
                if v is None:
                    continue
                vals.append(v)
                sampled.append(int(entry.get("games_sampled") or 0))
            n_opps = sum(1 for o in opponents if o.get("opponent"))
            if not vals or pos not in league_avg:
                by_pos[pos] = {"avg_points_allowed": None, "vs_league_avg_pct": None, "rated_opponents": len(vals), "unavailable_reason": "No opponent in these weeks has a rated defense at this position."}
                continue
            avg = sum(vals) / len(vals)
            rated_total += len(vals)
            by_pos[pos] = {
                "avg_points_allowed": round(avg, 2),
                "vs_league_avg_pct": round((avg / league_avg[pos] - 1.0) * 100.0, 1),
                "rated_opponents": len(vals),
                "scheduled_opponents": n_opps,
                "unavailable_reason": None,
            }
        if all(v["avg_points_allowed"] is None for v in by_pos.values()):
            continue
        team_rows.append({"team": team, "opponents": opponents, "by_position": by_pos, "_sampled": sampled, "_rated": rated_total})

    # rank 1 = easiest (most points allowed on average)
    for pos in OFFENSE_POSITIONS:
        ranked = sorted((r for r in team_rows if r["by_position"][pos]["avg_points_allowed"] is not None), key=lambda r: (-r["by_position"][pos]["avg_points_allowed"], r["team"]))
        for i, r in enumerate(ranked, start=1):
            r["by_position"][pos]["rank_easiest"] = i
            r["by_position"][pos]["of"] = len(ranked)

    items = []
    for r in team_rows:
        total_scheduled = sum(1 for o in r["opponents"] if o.get("opponent")) * len(OFFENSE_POSITIONS)
        conf = _confidence_from_sample(r["_sampled"], r["_rated"], total_scheduled)
        ranks = {p: v.get("rank_easiest") for p, v in r["by_position"].items() if v.get("rank_easiest")}
        best = min(ranks, key=lambda p: (ranks[p], p)) if ranks else None
        items.append(
            item(
                f"playoff_sos:{season}:{r['team']}:{weeks[0]}-{weeks[-1]}",
                "playoff_sos",
                now=now,
                headline=(f"{r['team']} has the #{ranks[best]} easiest {best} playoff schedule" if best else None),
                evidence=[
                    evidence_row("nflverse_games", f"week {o['week']} opponent", o.get("opponent") or "BYE")
                    for o in r["opponents"]
                ]
                + [evidence_row("sleeper_weekly_stats", "opponent points allowed by position (recency-weighted PPR)", {p: v["avg_points_allowed"] for p, v in r["by_position"].items()}, as_of=defense_as_of)],
                methodology=(
                    "Mean of the opponents' recency-weighted PPR points allowed per game to each position over the "
                    "listed weeks, compared with the league mean; rank 1 is the easiest schedule. Opponents without a "
                    "rated defense are skipped and counted in rated_opponents. Not a projection."
                ),
                confidence=conf,
                fresh=fresh,
                relevance={"dynasty": "medium", "redraft": "high"},
                team=r["team"],
                season=season,
                weeks=list(weeks),
                opponents=r["opponents"],
                by_position=r["by_position"],
            )
        )
    return items


def endpoint_playoff_sos(
    *, season: int | None, start_week: int, end_week: int, position: str | None, limit: int | None, now: datetime | None = None
) -> dict[str, Any]:
    if not (1 <= start_week <= end_week <= 18) or end_week - start_week > 3:
        raise ValueError("start_week/end_week must satisfy 1 <= start <= end <= 18 and span at most 4 weeks.")
    pos = position.strip().upper() if position else None
    if pos and pos not in OFFENSE_POSITIONS:
        raise ValueError("position must be one of QB, RB, WR, TE.")
    now = now or datetime.now(timezone.utc)
    clock = clock_info()
    use_season = int(season) if season is not None else clock["season"]
    weeks = list(range(start_week, end_week + 1))
    items = build_playoff_sos(
        load_games(), load_defense(use_season), season=use_season, weeks=weeks, now=now, defense_as_of=_iso(now),
        team_aliases=_team_aliases(),
    )
    if pos:
        items = [i for i in items if i["by_position"][pos]["avg_points_allowed"] is not None]
        items.sort(key=lambda i: i["by_position"][pos]["rank_easiest"])
    if limit:
        items = items[:limit]
    return finalize(
        "/v1/external/playoff-sos",
        now=now,
        clock=clock,
        methodology="Opponent points-allowed by position across the requested fantasy-playoff weeks (default 15-17).",
        items=items,
        fresh=freshness(now, now, source="nflverse_games+sleeper_weekly_stats"),
        unavailable_reason=f"No completed {use_season} games with rated defenses exist yet, or no schedule is published for weeks {start_week}-{end_week}.",
        extra={"requested": {"season": use_season, "weeks": weeks, "position": pos}},
    )


# --------------------------------------------------------------------------
# 3. Waiver / injury replacement opportunities
# --------------------------------------------------------------------------


def _is_injured(row: Mapping[str, Any]) -> bool:
    return _text(row.get("injury_status")).lower() in INJURED_STATUSES


def build_waiver_replacements(
    board: Sequence[Mapping[str, Any]],
    trending: Sequence[Mapping[str, Any]],
    roster_pct: Mapping[str, Mapping[str, Any] | None],
    *,
    now: datetime,
    board_as_of: str | None,
    max_roster_pct: float = 50.0,
    per_player: int = 3,
) -> list[dict[str, Any]]:
    by_id = {str(r.get("player_id")): r for r in board}
    adds = {}
    for rank, row in enumerate(trending, start=1):
        pid = _text(row.get("player_id"))
        if pid and pid not in adds:
            adds[pid] = {"count": int(_num(row.get("count")) or 0), "rank": rank}
    fresh = freshness(board_as_of, now, source="public_dynasty_board+sleeper_trending_adds")
    have_pct = any(v for v in roster_pct.values())
    items: list[dict[str, Any]] = []
    for hurt in board:
        pos = _text(hurt.get("position")).upper()
        rank = hurt.get("position_rank")
        if pos not in STARTER_RANK_LIMIT or not _is_injured(hurt) or not rank or rank > STARTER_RANK_LIMIT[pos]:
            continue
        cands = []
        for pid, add in adds.items():
            row = by_id.get(pid)
            if not row or pid == str(hurt.get("player_id")) or _text(row.get("position")).upper() != pos or _is_injured(row):
                continue
            pct = (roster_pct.get(pid) or {}).get("current")
            if pct is not None and pct > max_roster_pct:
                continue
            cands.append((add["rank"], row, add, pct))
        cands.sort(key=lambda c: (c[0], -(_num(c[1].get("score")) or 0)))
        picks = cands[:per_player]
        if not picks:
            continue
        verified = [p for p in picks if p[3] is not None]
        conf = "medium" if verified else "low"
        items.append(
            item(
                f"waiver:{hurt.get('player_id')}",
                "injury_replacement",
                now=now,
                headline=f"{hurt.get('name')} ({_text(hurt.get('injury_status'))}): {len(picks)} widely trending replacement(s) at {pos}",
                evidence=[
                    evidence_row("sleeper_player_directory", "injury_status", _text(hurt.get("injury_status")), as_of=board_as_of),
                    evidence_row("public_dynasty_board", f"{pos} rank of injured player", rank, as_of=board_as_of),
                ]
                + [
                    evidence_row("sleeper_trending_adds", f"{r.get('name')} adds (24h) / rank", {"adds": a["count"], "trend_rank": a["rank"], "roster_pct": p}, as_of=_iso(now))
                    for _, r, a, p in picks
                ],
                methodology=(
                    "Injured player: Sleeper injury designation in {Out, IR, PUP, Doubtful, Suspended} AND a starter-range "
                    "rank on the public dynasty board. Replacements: same-position players on Sleeper's cross-league "
                    "trending-add list, healthy, below 50% rostered when roster percentage is on record. League-agnostic: "
                    "availability in any one league is not known. Starter range uses dynasty-board rank as the proxy."
                ),
                confidence=conf,
                fresh=fresh,
                relevance={"dynasty": "medium", "redraft": "high"},
                injured_player={k: hurt.get(k) for k in ("player_id", "name", "position", "team", "injury_status", "position_rank")},
                replacements=[
                    {
                        "player_id": r.get("player_id"), "name": r.get("name"), "position": r.get("position"), "team": r.get("team"),
                        "trending_adds_24h": a["count"], "trending_rank": a["rank"], "roster_pct": p,
                        "same_team": _text(r.get("team")) == _text(hurt.get("team")),
                        "availability_verified": p is not None,
                    }
                    for _, r, a, p in picks
                ],
                roster_pct_available=have_pct,
            )
        )
    return items


def endpoint_waiver_replacements(*, db_path: str, fmt: str, limit: int, now: datetime | None = None) -> dict[str, Any]:
    _check_format(fmt)
    now = now or datetime.now(timezone.utc)
    clock = clock_info()
    board, as_of = load_board(db_path, fmt)
    reason = None
    items: list[dict[str, Any]] = []
    if not board:
        reason = "The public dynasty board is unavailable."
    elif clock["phase"] != season_clock.PHASE_REGULAR:
        reason = f"Waiver replacements are in-season content; the season clock phase is {clock['phase']}."
    else:
        trending = load_trending()
        if not trending:
            reason = "Sleeper's trending-add list is unavailable."
        else:
            board_ids = {str(r["player_id"]) for r in board}
            pct = load_roster_pct([p for p in (str(t.get("player_id")) for t in trending) if p in board_ids])
            items = build_waiver_replacements(board, trending, pct, now=now, board_as_of=as_of)[:limit]
            if not items:
                reason = "No injured starter-range players have a healthy same-position replacement on the trending-add list."
    return finalize(
        "/v1/external/waivers/replacements", now=now, clock=clock, items=items,
        methodology="Injured starter-range players paired with trending healthy same-position adds. See item methodology.",
        fresh=freshness(as_of, now, source="public_dynasty_board"), unavailable_reason=reason,
    )


# --------------------------------------------------------------------------
# 4. Matchup-driven lineup decisions
# --------------------------------------------------------------------------


def week_matchups(games: Any, season: int, week: int, aliases: Mapping[str, str] | None = None) -> dict[str, dict[str, Any]]:
    aliases = aliases or {}
    if games is None or getattr(games, "empty", True):
        return {}
    df = games[(games["season"] == season) & (games["week"] == week)]
    if "game_type" in df.columns:
        df = df[df["game_type"] == "REG"]
    out: dict[str, dict[str, Any]] = {}
    for _, g in df.iterrows():
        home = aliases.get(str(g["home_team"]), str(g["home_team"]))
        away = aliases.get(str(g["away_team"]), str(g["away_team"]))
        gid = (_text(g["game_id"]) if "game_id" in g.index else "") or None
        out[home] = {"opponent": away, "is_home": True, "game_id": gid}
        out[away] = {"opponent": home, "is_home": False, "game_id": gid}
    return out


def build_lineup_decisions(
    board: Sequence[Mapping[str, Any]],
    matchups: Mapping[str, Mapping[str, Any]],
    defense: Mapping[str, Mapping[str, Mapping[str, Any]]],
    *,
    season: int,
    week: int,
    now: datetime,
    board_as_of: str | None,
    limit: int = 10,
    min_gap_pct: float = 8.0,
) -> list[dict[str, Any]]:
    league_avg: dict[str, float] = {}
    for pos in OFFENSE_POSITIONS:
        vals = [_num(d.get(pos, {}).get("weighted_points_allowed_per_game")) for d in defense.values()]
        vals = [v for v in vals if v is not None]
        if vals:
            league_avg[pos] = sum(vals) / len(vals)
    fresh = freshness(board_as_of, now, source="public_dynasty_board+nflverse_games+sleeper_weekly_stats")
    starts: list[tuple[float, dict]] = []
    sits: list[tuple[float, dict]] = []
    for row in board:
        pos = _text(row.get("position")).upper()
        rank = row.get("position_rank")
        band = BORDERLINE_BANDS.get(pos)
        if not band or not rank or not (band[0] <= rank <= band[1]) or _is_injured(row):
            continue
        match = matchups.get(_text(row.get("team")))
        entry = defense.get(match["opponent"], {}).get(pos) if match else None
        if not match or not entry or not entry.get("tier") or pos not in league_avg:
            continue
        pa = _num(entry.get("weighted_points_allowed_per_game"))
        if pa is None:
            continue
        gap = (pa / league_avg[pos] - 1.0) * 100.0
        if abs(gap) < min_gap_pct or entry["tier"] == "average":
            continue
        verdict = "start" if gap > 0 else "sit"
        questionable = _text(row.get("injury_status")).lower() in {"questionable", "q"}
        conf = "medium" if (not entry.get("low_sample") and abs(gap) >= 15 and not questionable) else "low"
        rec = item(
            f"lineup:{season}:{week}:{row.get('player_id')}",
            "lineup_decision",
            now=now,
            headline=f"{verdict.upper()}: {row.get('name')} ({pos}{rank}) vs {match['opponent']}, a {entry['tier']} {pos} defense",
            evidence=[
                evidence_row("nflverse_games", "opponent / home", {"opponent": match["opponent"], "is_home": match["is_home"]}),
                evidence_row("sleeper_weekly_stats", f"{match['opponent']} PPR allowed to {pos} per game (weighted)", round(pa, 2), as_of=_iso(now)),
                evidence_row("sleeper_weekly_stats", "vs league average pct", round(gap, 1)),
                evidence_row("sleeper_weekly_stats", f"defense rank vs {pos} (1 = toughest) / tier", {"rank": entry.get("rank"), "tier": entry.get("tier")}),
                evidence_row("public_dynasty_board", f"{pos} position rank", rank, as_of=board_as_of),
                evidence_row("sleeper_player_directory", "injury_status", _text(row.get("injury_status")) or None),
            ],
            methodology=(
                "Borderline-starter band at each position only (clear starters are never flagged). Verdict follows the "
                "opponent's recency-weighted PPR points allowed to that position vs the league mean, requiring a gap of "
                "8% or more and a non-average tier. Matchup context, not a player projection; confidence never exceeds "
                "medium, and weather, injuries to teammates and game script are not modeled."
            ),
            confidence=conf,
            fresh=fresh,
            relevance={"dynasty": "low", "redraft": "high"},
            verdict=verdict,
            player={k: row.get(k) for k in ("player_id", "name", "position", "team", "position_rank")},
            opponent=match["opponent"],
            is_home=match["is_home"],
            game_id=match.get("game_id"),
            matchup_gap_pct=round(gap, 1),
        )
        (starts if verdict == "start" else sits).append((abs(gap), rec))
    starts.sort(key=lambda t: (-t[0], t[1]["id"]))
    sits.sort(key=lambda t: (-t[0], t[1]["id"]))
    half = max(1, limit // 2)
    chosen = [r for _, r in starts[:half]] + [r for _, r in sits[:half]]
    spare = [r for _, r in starts[half:] + sits[half:]]
    chosen += spare[: max(0, limit - len(chosen))]
    chosen.sort(key=lambda r: (-abs(r["matchup_gap_pct"]), r["id"]))
    return chosen[:limit]


def endpoint_lineup_decisions(
    *, db_path: str, fmt: str, week: int | None, season: int | None, limit: int, now: datetime | None = None
) -> dict[str, Any]:
    _check_format(fmt)
    now = now or datetime.now(timezone.utc)
    clock = clock_info()
    use_season = int(season) if season is not None else clock["season"]
    use_week = int(week) if week is not None else clock["week"]
    reason = None
    items: list[dict[str, Any]] = []
    board, as_of = load_board(db_path, fmt)
    if use_week is None or not 1 <= use_week <= 18:
        reason = f"No regular-season week to decide for (season clock phase is {clock['phase']}); pass week=1..18 to preview."
    elif not board:
        reason = "The public dynasty board is unavailable."
    else:
        matchups = week_matchups(load_games(), use_season, use_week, _team_aliases())
        if not matchups:
            reason = f"No nflverse schedule rows for season {use_season} week {use_week}."
        else:
            defense = load_defense(use_season)
            if not defense:
                reason = f"No completed {use_season} games to rate opposing defenses yet."
            else:
                items = build_lineup_decisions(board, matchups, defense, season=use_season, week=use_week, now=now, board_as_of=as_of, limit=limit)
                if not items:
                    reason = "No borderline starters face a meaningfully weak or tough defense this week."
    return finalize(
        "/v1/external/lineup/decisions", now=now, clock=clock, items=items,
        methodology="Matchup-driven start/sit for borderline starters from opponent points allowed by position.",
        fresh=freshness(as_of, now, source="public_dynasty_board"), unavailable_reason=reason,
        extra={"requested": {"season": use_season, "week": use_week}},
    )


# --------------------------------------------------------------------------
# 5. Dynasty value changes
# --------------------------------------------------------------------------


def build_value_changes(
    latest: Mapping[str, int],
    baseline: Mapping[str, int],
    board: Sequence[Mapping[str, Any]],
    *,
    latest_date: str,
    baseline_date: str,
    now: datetime,
    min_delta: int = MIN_RATING_DELTA,
    limit: int = 10,
) -> list[dict[str, Any]]:
    by_id = {str(r.get("player_id")): r for r in board}
    span = (date.fromisoformat(latest_date) - date.fromisoformat(baseline_date)).days
    fresh = freshness(f"{latest_date}T00:00:00+00:00", now, source="player_rating_snapshots")
    movers = []
    for pid, cur in latest.items():
        prev = baseline.get(pid)
        row = by_id.get(pid)
        if prev is None or row is None:
            continue
        delta = int(cur) - int(prev)
        if abs(delta) >= min_delta:
            movers.append((delta, pid, row, int(prev), int(cur)))
    risers = sorted((m for m in movers if m[0] > 0), key=lambda m: (-m[0], m[1]))[:limit]
    fallers = sorted((m for m in movers if m[0] < 0), key=lambda m: (m[0], m[1]))[:limit]
    items = []
    for direction, group in (("riser", risers), ("faller", fallers)):
        for delta, pid, row, prev, cur in group:
            items.append(
                item(
                    f"value:{latest_date}:{span}d:{pid}",
                    "dynasty_value_change",
                    now=now,
                    headline=f"{row.get('name')} ({row.get('position')}): rating {prev} to {cur} ({delta:+d}) over {span} days",
                    evidence=[
                        evidence_row("player_rating_snapshots", f"overall rating on {baseline_date}", prev, as_of=baseline_date),
                        evidence_row("player_rating_snapshots", f"overall rating on {latest_date}", cur, as_of=latest_date),
                        evidence_row("public_dynasty_board", "overall rank / position rank", {"overall": row.get("overall_rank"), "position": row.get("position_rank")}),
                    ],
                    methodology=(
                        "Difference between two stored daily 0-99 overall-rating snapshots (same canonical pool as the "
                        "rating-history endpoint), restricted to players on the current public board. Moves under "
                        f"{min_delta} points are ignored. The cause of a move is not asserted."
                    ),
                    confidence="high" if abs(delta) >= 5 else "medium",
                    fresh=fresh,
                    relevance={"dynasty": "high", "redraft": "low"},
                    direction=direction,
                    player={k: row.get(k) for k in ("player_id", "name", "position", "team", "age")},
                    rating_previous=prev, rating_current=cur, rating_delta=delta,
                    window={"baseline_date": baseline_date, "latest_date": latest_date, "span_days": span},
                )
            )
    return items


def endpoint_value_changes(*, db_path: str, fmt: str, days: int, limit: int, now: datetime | None = None) -> dict[str, Any]:
    _check_format(fmt)
    if not 7 <= days <= 30:
        raise ValueError("days must be between 7 and 30.")
    now = now or datetime.now(timezone.utc)
    clock = clock_info()
    board, as_of = load_board(db_path, fmt)
    reason, items = None, []
    snap = load_rating_snapshots(days)
    if not board:
        reason = "The public dynasty board is unavailable."
    elif snap.get("reason"):
        reason = snap["reason"]
    else:
        items = build_value_changes(snap["latest"], snap["baseline"], board, latest_date=snap["latest_date"], baseline_date=snap["baseline_date"], now=now, limit=limit)
        if not items:
            reason = "No board players moved at least the minimum rating delta in the window."
    return finalize(
        "/v1/external/dynasty/value-changes", now=now, clock=clock, items=items,
        methodology="Risers and fallers from two stored daily rating snapshots.",
        fresh=freshness(as_of, now, source="public_dynasty_board"), unavailable_reason=reason,
        extra={"requested": {"days": days}},
    )


# --------------------------------------------------------------------------
# 6. Prepared year-round capabilities
# --------------------------------------------------------------------------


def build_rookies(
    board: Sequence[Mapping[str, Any]],
    adp_snapshot: Mapping[str, Any] | None,
    sleeper_players: Mapping[str, Mapping[str, Any]],
    *,
    now: datetime,
    board_as_of: str | None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    rookies = [r for r in board if r.get("years_exp") == 0 and _text(r.get("team")) and r.get("position") in OFFENSE_POSITIONS]
    rookies.sort(key=lambda r: -(_num(r.get("score")) or 0))
    adp_players = (adp_snapshot or {}).get("players") or {}
    adp_as_of = (adp_snapshot or {}).get("as_of")
    fresh = freshness(board_as_of, now, source="public_dynasty_board")
    incumbents: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for r in board:
        incumbents.setdefault((_text(r.get("team")), _text(r.get("position"))), []).append(r)
    items = []
    for rank, row in enumerate(rookies[:limit], start=1):
        pid = str(row.get("player_id"))
        adp = adp_players.get(pid) or {}
        sp = sleeper_players.get(pid) or {}
        order = sp.get("depth_chart_order")
        ahead = sorted(
            (r for r in incumbents.get((_text(row.get("team")), _text(row.get("position"))), []) if str(r.get("player_id")) != pid and (_num(r.get("score")) or 0) > (_num(row.get("score")) or 0)),
            key=lambda r: -(_num(r.get("score")) or 0),
        )[:3]
        has_adp = _num(adp.get("adp")) is not None
        items.append(
            item(
                f"rookie:{pid}", "rookie", now=now,
                headline=f"{row.get('name')} ({row.get('position')}, {row.get('team')}): our rookie rank {rank}" + (f", ADP {adp.get('adp')}" if has_adp else ""),
                evidence=[
                    evidence_row("public_dynasty_board", "dynasty score / position rank", {"score": row.get("score"), "position_rank": row.get("position_rank")}, as_of=board_as_of),
                    evidence_row("sleeper_player_directory", "depth_chart_order", order),
                    evidence_row("fantasy_football_calculator_adp", "rookie ADP", adp.get("adp") if has_adp else None, as_of=adp_as_of),
                ],
                methodology="Rookies = players with zero years of experience on a team, ranked by the public dynasty score. ADP is Fantasy Football Calculator's rookie-draft snapshot when available. Landing spot = team, depth-chart order and higher-valued same-position teammates; draft capital is not modeled here.",
                confidence="medium" if has_adp and (adp.get("drafts") or 0) >= 10 else "low",
                fresh=fresh,
                relevance={"dynasty": "high", "redraft": "medium"},
                player={k: row.get(k) for k in ("player_id", "name", "position", "team", "age")},
                our_rank=rank,
                adp=adp.get("adp") if has_adp else None,
                adp_drafts=adp.get("drafts") if has_adp else None,
                adp_as_of=adp_as_of if has_adp else None,
                landing_spot={"team": row.get("team"), "depth_chart_order": order, "higher_valued_teammates": [{"player_id": r.get("player_id"), "name": r.get("name")} for r in ahead]},
                draft_capital=None,
                draft_capital_unavailable_reason="Draft round/pick is not part of the verified player board.",
            )
        )
    return items


def endpoint_rookies(*, db_path: str, fmt: str, limit: int, now: datetime | None = None) -> dict[str, Any]:
    _check_format(fmt)
    now = now or datetime.now(timezone.utc)
    clock = clock_info()
    board, as_of = load_board(db_path, fmt)
    items = build_rookies(board, load_rookie_adp(), load_sleeper_players(), now=now, board_as_of=as_of, limit=limit) if board else []
    reason = None if items else ("The public dynasty board is unavailable." if not board else "No rookies (zero years of experience, assigned to a team) are on the current board, which is expected before the NFL Draft.")
    return finalize(
        "/v1/external/rookies", now=now, clock=clock, items=items,
        methodology="Rookie rankings, ADP and landing spots from the public board, Sleeper depth chart and rookie ADP snapshot.",
        fresh=freshness(as_of, now, source="public_dynasty_board"), unavailable_reason=reason,
    )


def build_depth_chart_changes(
    snapshots: Mapping[str, Mapping[str, int]], board: Sequence[Mapping[str, Any]], *, now: datetime, limit: int = 15
) -> list[dict[str, Any]]:
    keys = sorted(k for k, v in snapshots.items() if isinstance(v, Mapping) and v)
    if len(keys) < 2:
        return []
    cur_key, prev_key = keys[-1], keys[-2]
    cur, prev = snapshots[cur_key], snapshots[prev_key]
    by_id = {str(r.get("player_id")): r for r in board}
    moves = []
    for pid, order in cur.items():
        if pid in prev and pid in by_id and int(prev[pid]) != int(order):
            moves.append((int(prev[pid]) - int(order), pid))
    moves.sort(key=lambda m: (-abs(m[0]), m[1]))
    fresh = {"data_as_of": None, "age_hours": None, "stale": None, "source": "depth_chart_snapshots", "snapshot_weeks": [prev_key, cur_key]}
    items = []
    for delta, pid in moves[:limit]:
        row = by_id[pid]
        items.append(
            item(
                f"depth:{cur_key}:{pid}", "depth_chart_change", now=now,
                headline=f"{row.get('name')} ({row.get('position')}, {row.get('team')}): depth chart {prev[pid]} to {cur[pid]}",
                evidence=[evidence_row("depth_chart_snapshots", f"depth_chart_order {prev_key}", int(prev[pid])), evidence_row("depth_chart_snapshots", f"depth_chart_order {cur_key}", int(cur[pid]))],
                methodology="Difference between the two most recent weekly snapshots of Sleeper's depth_chart_order, for players on the current board. A move is not a confirmed role change.",
                confidence="low" if abs(delta) == 1 else "medium",
                fresh=fresh, relevance={"dynasty": "medium", "redraft": "high"},
                player={k: row.get(k) for k in ("player_id", "name", "position", "team")},
                previous_order=int(prev[pid]), current_order=int(cur[pid]), direction="up" if delta > 0 else "down",
            )
        )
    return items


def endpoint_changes(*, db_path: str, fmt: str, limit: int, now: datetime | None = None) -> dict[str, Any]:
    _check_format(fmt)
    now = now or datetime.now(timezone.utc)
    clock = clock_info()
    board, as_of = load_board(db_path, fmt)
    items = build_depth_chart_changes(load_depth_snapshots(), board, now=now, limit=limit) if board else []
    team_section = {
        "status": "unavailable",
        "unavailable_reason": "No team-affiliation history is retained (only the current Sleeper team and weekly depth-chart order are stored), so free-agency and trade moves cannot be diffed without guessing.",
        "items": [],
    }
    reason = None if items else ("The public dynasty board is unavailable." if not board else "Fewer than two weekly depth-chart snapshots are stored, or no board player's depth-chart order changed.")
    return finalize(
        "/v1/external/changes", now=now, clock=clock, items=items,
        methodology="Depth-chart movement from stored weekly snapshots; team changes unavailable.",
        fresh=freshness(as_of, now, source="public_dynasty_board"), unavailable_reason=reason,
        extra={"sections": {"depth_chart": {"status": "ok" if items else "unavailable", "unavailable_reason": reason}, "team_changes": team_section}},
    )


def endpoint_roster_construction(*, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    return finalize(
        "/v1/external/dynasty/roster-construction", now=now, clock=clock_info(), items=[],
        methodology="Not available.", fresh=freshness(None, now, source="none"),
        unavailable_reason=(
            "Rebuild and roster-construction analysis requires a specific roster, and this API reads no user or league "
            "data by design. For league-agnostic dynasty content use /v1/external/trades/interesting (sell-window and "
            "age-cliff trades) and /v1/external/dynasty/value-changes."
        ),
    )


# --------------------------------------------------------------------------
# 7. Deterministic demo scenarios
# --------------------------------------------------------------------------

DEMO_DISCLAIMER = (
    "Illustrative, synthetic scenarios with fictional players. They are fixed (identical on every call), are not "
    "current player values or advice, and must not be presented as real recommendations."
)
_DEMO_UTM = "utm_source=desktop_ad_app&utm_medium=demo&utm_campaign=demo_scenarios"

# No-signup "try" links (web-next /try/<topic>; app: fantasygmlab://try/<topic>). They open the real feature on the
# shared sample data and end in one connect/signup CTA. UTM convention for these links: utm_source is ALWAYS "ad_app";
# utm_medium / utm_campaign / utm_content / utm_term are the caller's values passed through (sanitized like
# web-next/src/lib/attribution.ts cleanToken), defaulting to demo / demo_scenarios / <scenario id>.
TRY_UTM_SOURCE = "ad_app"
TRY_UTM_PASSTHROUGH = ("utm_medium", "utm_campaign", "utm_content", "utm_term")
TRY_TOPICS: tuple[dict[str, str], ...] = (
    {"topic": "start-sit", "path": "/try/start-sit", "shows": "Start/sit suggested move with weekly range, on the sample league"},
    {"topic": "trade", "path": "/try/trade", "shows": "Trade analyzer with a preset realistic dynasty trade"},
    {"topic": "waivers", "path": "/try/waivers", "shows": "Waiver board with priority adds, on the sample league"},
    {"topic": "playoffs", "path": "/try/playoffs", "shows": "Fantasy playoff strength of schedule by position"},
    {"topic": "dynasty-values", "path": "/try/dynasty-values", "shows": "Dynasty trade value chart, 1QB and Superflex"},
)
_SCENARIO_TRY_TOPIC = {"start_sit": "start-sit", "waiver_claim": "waivers", "trade": "trade"}


def _clean_utm(value: Any) -> str:
    return re.sub(r"[^a-z0-9_.-]", "", str(value or "").lower())[:40]


def try_url(topic: str, *, utm: Mapping[str, Any] | None = None, default_content: str = "") -> str:
    """Absolute try URL for a topic with the documented UTM convention (see TRY_UTM_SOURCE)."""

    path = next((t["path"] for t in TRY_TOPICS if t["topic"] == topic), None)
    if path is None:
        raise ValueError("unknown try topic: " + topic)
    params = {"utm_source": TRY_UTM_SOURCE, "utm_medium": "demo", "utm_campaign": "demo_scenarios"}
    if default_content:
        params["utm_content"] = _clean_utm(default_content)
    for key in TRY_UTM_PASSTHROUGH:
        value = _clean_utm((utm or {}).get(key))
        if value:
            params[key] = value
    return f"{brand_identity.PRODUCT_URL}{path}?{urlencode(params)}"

_SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "id": "demo-start-sit-1", "type": "start_sit", "title": "Start/sit: the borderline flex",
        "setup": "Two flex options with similar season averages; one faces the league's weakest run defense.",
        "options": [
            {"name": "Demo Runner A", "position": "RB", "avg_ppr": 11.8, "opponent_points_allowed_pct_vs_league": 18.0},
            {"name": "Demo Runner B", "position": "RB", "avg_ppr": 12.1, "opponent_points_allowed_pct_vs_league": -14.0},
        ],
        "rule": "Start the option with the larger opponent_points_allowed_pct_vs_league when season averages are within 1.0 point.",
    },
    {
        "id": "demo-waiver-1", "type": "waiver_claim", "title": "Waiver claim after a starter injury",
        "setup": "A starting WR is ruled out; a same-team backup is the top trending add.",
        "options": [
            {"name": "Demo Receiver X", "position": "WR", "status": "Out", "role": "injured starter"},
            {"name": "Demo Receiver Y", "position": "WR", "status": "Active", "role": "same-team backup", "trending_adds_24h": 5400, "roster_pct": 12.0},
        ],
        "rule": "Claim the healthy same-team replacement when he is under 50% rostered and trending.",
    },
    {
        "id": "demo-trade-1", "type": "trade", "title": "Trade check: two mid assets for one star",
        "setup": "A consolidation offer in a dynasty league.",
        "options": [
            {"side": "give", "assets": [{"name": "Demo Back C", "value": 4200}, {"name": "Demo Wideout D", "value": 3900}]},
            {"side": "get", "assets": [{"name": "Demo Star E", "value": 8600}]},
        ],
        "rule": "Accept when the received total exceeds the given total by at least 5%.",
    },
)


def _demo_verdict(s: Mapping[str, Any]) -> dict[str, Any]:
    if s["type"] == "start_sit":
        a, b = s["options"]
        pick = a if a["opponent_points_allowed_pct_vs_league"] > b["opponent_points_allowed_pct_vs_league"] else b
        return {"verdict": f"Start {pick['name']}", "basis": "Larger opponent points-allowed gap with season averages within 1.0 point."}
    if s["type"] == "waiver_claim":
        return {"verdict": f"Claim {s['options'][1]['name']}", "basis": "Healthy same-team replacement, under 50% rostered, trending."}
    give = sum(a["value"] for a in s["options"][0]["assets"])
    get = sum(a["value"] for a in s["options"][1]["assets"])
    margin = round((get / give - 1.0) * 100.0, 1)
    return {"verdict": "Accept" if margin >= 5.0 else "Decline", "basis": f"Received total {get} vs given {give} ({margin:+.1f}%)."}


def build_demo_scenarios(
    *, now: datetime, scenario_type: str | None = None, utm: Mapping[str, Any] | None = None
) -> list[dict[str, Any]]:
    base = brand_identity.PRODUCT_URL
    items = []
    for s in _SCENARIOS:
        if scenario_type and s["type"] != scenario_type:
            continue
        verdict = _demo_verdict(s)
        topic = _SCENARIO_TRY_TOPIC[s["type"]]
        matching_try_url = try_url(topic, utm=utm, default_content=s["id"])
        items.append(
            item(
                s["id"], "demo_scenario", now=now, headline=s["title"],
                evidence=[evidence_row("demo_fixture", "scenario setup", s["setup"]), evidence_row("demo_fixture", "options", s["options"]), evidence_row("demo_fixture", "rule", s["rule"])],
                methodology="Fixed fixture evaluated by the stated rule; deterministic, no live data. " + DEMO_DISCLAIMER,
                confidence="high", fresh={"data_as_of": None, "age_hours": None, "stale": False, "source": "static_fixture"},
                relevance={"dynasty": "medium", "redraft": "medium"},
                scenario_type=s["type"], setup=s["setup"], options=s["options"], rule=s["rule"], verdict=verdict["verdict"], verdict_basis=verdict["basis"],
                synthetic=True,
                try_topic=topic, try_url=matching_try_url,
                links={
                    "sample_league": f"{base}/sample-league?{_DEMO_UTM}&utm_content={s['id']}",
                    "quickstart_game": f"{base}/gm-game?quickstart=1&{_DEMO_UTM}&utm_content={s['id']}",
                },
            )
        )
    return items


def endpoint_demo_scenarios(
    *, scenario_type: str | None, now: datetime | None = None, utm: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    if scenario_type and scenario_type not in {s["type"] for s in _SCENARIOS}:
        raise ValueError("type must be one of: " + ", ".join(sorted({s["type"] for s in _SCENARIOS})))
    now = now or datetime.now(timezone.utc)
    return finalize(
        "/v1/external/demo/scenarios", now=now, clock=clock_info(),
        items=build_demo_scenarios(now=now, scenario_type=scenario_type, utm=utm),
        methodology="Deterministic synthetic scenarios. " + DEMO_DISCLAIMER,
        fresh={"data_as_of": None, "age_hours": None, "stale": False, "source": "static_fixture"},
        extra={
            "disclaimer": DEMO_DISCLAIMER,
            "try_utm_convention": "utm_source=ad_app; utm_medium/utm_campaign/utm_content/utm_term are passed through from the request.",
            "try_links": [{**t, "url": try_url(t["topic"], utm=utm)} for t in TRY_TOPICS],
        },
    )


def endpoint_plan(*, as_of: str | None, league_type: str, exclude_ids: Sequence[str], limit: int, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if as_of:
        try:
            today = date.fromisoformat(as_of)
        except ValueError as exc:
            raise ValueError("as_of must be YYYY-MM-DD.") from exc
        clock = clock_info(today)
    else:
        today = now.date()
        clock = clock_info()
    return build_content_plan(clock, today, now, league_type=league_type, exclude_ids=exclude_ids, limit=limit)


# --------------------------------------------------------------------------
# Providers (I/O). Tests replace these; builders above never touch them.
# --------------------------------------------------------------------------


def _check_format(fmt: str) -> None:
    if fmt not in FORMATS:
        raise ValueError("format must be one of: " + ", ".join(FORMATS))


def _team_aliases() -> Mapping[str, str]:
    from modules import nfl_teams

    return nfl_teams.TEAM_CODE_ALIASES


def load_games() -> Any:
    from modules import nfl_schedule

    return nfl_schedule.load_games()


def load_defense(season: int) -> dict[str, dict[str, dict[str, Any]]]:
    from modules import player_projections

    try:
        return player_projections.team_defense_points_allowed_by_position(season) or {}
    except Exception:
        return {}


def load_board(db_path: str, fmt: str) -> tuple[list[dict[str, Any]], str | None]:
    """The cached public dynasty board (same source as /v1/public/dynasty-values)."""

    from modules import public_dynasty_values

    try:
        payload = public_dynasty_values.get_public_dynasty_values(db_path, fmt)
    except Exception:
        payload = None
    if not payload:
        return [], None
    return list(payload.get("players") or []), payload.get("source_updated_at")


def load_trending() -> list[dict[str, Any]]:
    from modules import sleeper

    return sleeper.get_trending_players("add", lookback_hours=24, limit=100)


def load_roster_pct(player_ids: Sequence[str], *, require_baseline: bool = True) -> dict[str, Any]:
    from modules import roster_pct_history

    try:
        return roster_pct_history.get_roster_pct_trend(list(player_ids), 7, require_baseline=require_baseline)
    except Exception:
        return {}


def load_sleeper_players() -> Mapping[str, Mapping[str, Any]]:
    from modules import sleeper

    try:
        return sleeper.get_players() or {}
    except Exception:
        return {}


def load_rookie_adp() -> Mapping[str, Any]:
    from modules import rookie_adp

    try:
        return rookie_adp.latest_cached("rookie_1qb")
    except Exception:
        return {}


def load_depth_snapshots() -> Mapping[str, Any]:
    from modules import depth_chart_history

    return depth_chart_history.load_depth_chart_snapshots()


def load_rating_snapshots(days: int) -> dict[str, Any]:
    from datetime import timedelta

    from modules import player_rating_history as prh

    config = prh.load_rating_snapshot_config()
    if not config.configured:
        return {"reason": "Rating snapshot storage is not configured on this server."}
    bounds = prh.fetch_snapshot_date_bounds(config)
    if bounds is None:
        return {"reason": "No rating snapshots have been stored yet."}
    latest = bounds[1]
    latest_day = date.fromisoformat(latest)
    baseline = prh.fetch_baseline_date(
        config, not_after=(latest_day - timedelta(days=days)).isoformat(), not_before=(latest_day - timedelta(days=days + 7)).isoformat()
    )
    if not baseline:
        return {"reason": f"No stored snapshot is at least {days} days older than the latest ({latest}); history is still building."}
    latest_map = prh.fetch_snapshot_day(config, latest)
    base_map = prh.fetch_snapshot_day(config, baseline)
    if not latest_map or not base_map:
        return {"reason": "A snapshot day could not be read completely; no partial comparison is made."}
    return {"latest": latest_map, "baseline": base_map, "latest_date": latest, "baseline_date": baseline}
