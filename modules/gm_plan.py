"""GM Plan — a season-phase-aware roadmap layer (Decision Memory v1 follow-up).

Additive aggregation/framing only. This module invents no new valuation
math, loads no player data of its own, and never touches value_score,
composite scoring, or rankings. It takes ALREADY-COMPUTED outputs from the
app's existing engines and arranges them into a season-arc "GM Plan":

  - Season phase is derived from a real week number the caller already has
    (see `derive_season_phase`) — it does not fetch or infer a week itself.
  - Stance conditioning reads the user's declared Team Situation
    (modules.team_stance — Rebuilding/Competing/Balanced), the SAME
    user-facing declaration modules.trade_ideas.apply_team_stance_framing
    already uses for rationale text. This is deliberately NOT the older,
    separate "GM Stance" / team strategy system (modules.team_eval /
    modules.trade_hub_engine.apply_strategy_age_curve) that rewrites
    value_score via an age curve — GM Plan never reads or writes that.
  - Every recommendation item this module surfaces is copied straight off
    an already-built signal the caller passes in (a trade idea record from
    modules.trade_ideas / modules.trade_hub_engine, or a rank row from
    modules.league_rankings). When a category has no real signal, the
    focus area is marked `status="no_signal"` with a generic, honest
    "here's what to watch for" note — never fabricated per-team advice.
    Same discipline as modules.player_projections' honest-uncertainty
    statuses (never a fake number when the data isn't there).

Callers (e.g. services/mobile_api_service.py) are responsible for actually
fetching the inputs from the existing engines; this module is pure and has
no I/O, so it's cheap to unit test without a live league.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from modules import team_stance as team_stance_module
from modules.rankings import injury_display_label

# --- Season phase detection -------------------------------------------------

PHASE_EARLY_SEASON = "early_season"
PHASE_TRADE_DEADLINE_APPROACH = "trade_deadline_approach"
PHASE_PLAYOFF_PUSH = "playoff_push"
PHASE_OFFSEASON_ADJACENT = "offseason_adjacent"

SEASON_PHASES: tuple[str, ...] = (
    PHASE_EARLY_SEASON,
    PHASE_TRADE_DEADLINE_APPROACH,
    PHASE_PLAYOFF_PUSH,
    PHASE_OFFSEASON_ADJACENT,
)

PHASE_LABELS: dict[str, str] = {
    PHASE_EARLY_SEASON: "Early Season",
    PHASE_TRADE_DEADLINE_APPROACH: "Trade Deadline Approaching",
    PHASE_PLAYOFF_PUSH: "Playoff Push",
    PHASE_OFFSEASON_ADJACENT: "Offseason-Adjacent",
}

# Matches modules.league_recaps / modules.league_history's own
# `_safe_positive_int(settings.get("playoff_week_start"), 15)` default —
# reused here rather than invented, so GM Plan agrees with the rest of the
# app about when playoffs start absent an explicit league setting.
DEFAULT_PLAYOFF_WEEK_START = 15

# Matches modules.league_maturity.classify_league_maturity's own
# "playoff push" threshold (`games_per_team >= playoff_week_start - 3`).
PLAYOFF_PUSH_LOOKBACK_WEEKS = 3

# Weeks 1-3 read as "early season" — a simple, honest bucket boundary; not
# derived from any league setting because none exists for this.
EARLY_SEASON_WEEK_CEILING = 3

# Last realistic NFL/Sleeper regular-season-or-playoffs week. A week outside
# (0, MAX_LEAGUE_WEEK] reads as "no live week data" (offseason-adjacent)
# rather than a fabricated in-season phase.
MAX_LEAGUE_WEEK = 18


def _safe_week_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return parsed


def derive_season_phase(current_week: Any, playoff_week_start: Any = None) -> str:
    """Bucket a real week number into a coarse season-arc phase.

    `current_week` should be derived by the caller the same way
    modules.league_standings already does
    (`league_settings.get("leg") or league_settings.get("week")`) — this
    function does not fetch or infer a week on its own, only buckets one.

    Returns one of PHASE_EARLY_SEASON, PHASE_TRADE_DEADLINE_APPROACH,
    PHASE_PLAYOFF_PUSH, or PHASE_OFFSEASON_ADJACENT (the honest fallback
    when there's no usable week — before week 1, past a realistic season
    length, or simply missing).
    """

    week = _safe_week_int(current_week)
    if week <= 0 or week > MAX_LEAGUE_WEEK:
        return PHASE_OFFSEASON_ADJACENT

    pws = _safe_week_int(playoff_week_start)
    if pws <= 0:
        pws = DEFAULT_PLAYOFF_WEEK_START

    if week >= max(1, pws - PLAYOFF_PUSH_LOOKBACK_WEEKS):
        return PHASE_PLAYOFF_PUSH
    if week <= EARLY_SEASON_WEEK_CEILING:
        return PHASE_EARLY_SEASON
    return PHASE_TRADE_DEADLINE_APPROACH


def phase_label(phase: str) -> str:
    return PHASE_LABELS.get(phase, PHASE_LABELS[PHASE_OFFSEASON_ADJACENT])


# --- Framing copy (fixed templates, conditioned on stance x phase) ---------
#
# These are generic framing sentences, not per-team advice — the actual
# "recommendations" are the real signal items assembled below. Keeping
# these as small composable clauses (phase clause + stance clause) instead
# of one string per (stance, phase) pair avoids a 16-entry copy matrix.

PHASE_HEADLINES: dict[str, str] = {
    PHASE_EARLY_SEASON: "Early season — the picture is still forming.",
    PHASE_TRADE_DEADLINE_APPROACH: "The trade market is most active right now.",
    PHASE_PLAYOFF_PUSH: "Playoff push — decisions carry more weight from here.",
    PHASE_OFFSEASON_ADJACENT: "No live week detected — this reads as an offseason-adjacent plan.",
}

STANCE_PLAN_CLAUSES: dict[str, str] = {
    team_stance_module.STANCE_REBUILDING: (
        "Your declared rebuild means this plan leans toward youth and future draft capital."
    ),
    team_stance_module.STANCE_COMPETING: (
        "Your declared win-now stance means this plan leans toward immediate roster impact."
    ),
    team_stance_module.STANCE_BALANCED: (
        "Your declared balanced stance means this plan weighs both immediate value and future flexibility."
    ),
}
NO_STANCE_PLAN_CLAUSE = (
    "Declare a Team Situation stance (Rebuilding, Competing, or Balanced) to sharpen this plan."
)

TRADE_STANCE_EMPHASIS: dict[str, str] = {
    team_stance_module.STANCE_REBUILDING: "Prioritize offers that add youth and future draft capital.",
    team_stance_module.STANCE_COMPETING: "Prioritize offers that upgrade immediate starting production.",
    team_stance_module.STANCE_BALANCED: "Weigh offers on both immediate impact and future flexibility.",
}
NO_TRADE_STANCE_EMPHASIS = "Declare a Team Situation stance to sharpen how these are framed."

TRADE_NO_SIGNAL_WATCH_FOR = (
    "No specific trade opportunities surfaced this week — here's what to watch for: a "
    "partner with surplus at one of your weaker spots, or a market shift once waivers "
    "process or injury news lands."
)

STANDING_NO_SIGNAL_WATCH_FOR = "No power rank data is available for this league yet."

ROSTER_NO_SIGNAL_WATCH_FOR = "No roster construction ranking is available for this league yet."


def _headline(stance: str, phase: str) -> str:
    phase_text = PHASE_HEADLINES.get(phase, PHASE_HEADLINES[PHASE_OFFSEASON_ADJACENT])
    stance_text = STANCE_PLAN_CLAUSES.get(stance, NO_STANCE_PLAN_CLAUSE)
    return f"{phase_text} {stance_text}"


# --- Focus areas -------------------------------------------------------------

FOCUS_STANDING = "standing"
FOCUS_TRADE = "trade_opportunities"
FOCUS_ROSTER = "roster_construction"

STATUS_SIGNAL_FOUND = "signal_found"
STATUS_NO_SIGNAL = "no_signal"

# (rank field, tie field, display label) on a modules.league_rankings row —
# see build_league_rankings_frame / add_league_detail_ranks / PR #799's
# modules.rank_tie_metadata.add_rank_tie_metadata for exactly these fields.
ROSTER_RANK_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("starter_rank", "starter_rank_tied", "Starter Strength"),
    ("bench_rank", "bench_rank_tied", "Bench Depth"),
    ("age_rank", "age_rank_tied", "Roster Age"),
)


def _rank_fact(
    rankings_row: Mapping[str, Any] | None,
    rank_key: str,
    tie_key: str,
    total_teams: int | None,
    label: str,
) -> dict[str, Any] | None:
    if not rankings_row:
        return None
    rank = rankings_row.get(rank_key)
    if rank is None:
        return None
    try:
        rank_int = int(rank)
    except (TypeError, ValueError):
        return None
    return {
        "label": label,
        "rank": rank_int,
        "total_teams": int(total_teams) if total_teams else None,
        "tied": bool(rankings_row.get(tie_key)),
    }


def _standing_focus_area(
    rankings_row: Mapping[str, Any] | None,
    total_teams: int | None,
    record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    power_fact = _rank_fact(rankings_row, "power_rank", "power_rank_tied", total_teams, "Power Rank")
    if power_fact:
        power_fact["source"] = "modules.league_rankings.build_league_rankings_frame"
        items.append(power_fact)

    capital_fact = _rank_fact(
        rankings_row, "draft_capital_rank", "draft_capital_rank_tied", total_teams, "Draft Capital Rank"
    )
    if capital_fact:
        capital_fact["source"] = "modules.league_rankings.build_draft_capital_summary"
        items.append(capital_fact)

    if record:
        wins = record.get("wins")
        losses = record.get("losses")
        if wins is not None or losses is not None:
            items.append(
                {
                    "label": "Record",
                    "wins": wins,
                    "losses": losses,
                    "ties": record.get("ties"),
                    "source": "sleeper roster settings",
                }
            )

    status = STATUS_SIGNAL_FOUND if items else STATUS_NO_SIGNAL
    return {
        "key": FOCUS_STANDING,
        "title": "Where You Stand",
        "status": status,
        "items": items,
        "watch_for": "" if items else STANDING_NO_SIGNAL_WATCH_FOR,
    }


def _trade_focus_area(
    stance: str,
    trade_ideas: Sequence[Mapping[str, Any]],
    max_ideas: int,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for idea in list(trade_ideas)[: max(0, max_ideas)]:
        if not isinstance(idea, Mapping):
            continue
        # The receive-side ("their_player") asset dict — modules.trade_ideas'
        # _player_asset already carries real status/injury_status on every
        # idea it builds; GM Plan previously discarded it here, leaving this
        # item type with zero player identity/injury signal (the gap flagged
        # by the injury-awareness audit). Reuse that same asset dict rather
        # than re-deriving anything.
        receive_assets = [
            asset for asset in (idea.get("receive_assets") or []) if isinstance(asset, Mapping)
        ]
        their_player_asset = next(
            (asset for asset in receive_assets if asset.get("asset_type") == "player"), None
        )
        # modules.rankings.injury_display_label() is the app's one injury
        # vocabulary (same helper modules.gm_targets uses for its own
        # `injury_display` field) — "" means healthy/no data, never fabricated.
        their_player_injury_display = (
            injury_display_label(
                their_player_asset.get("status"), their_player_asset.get("injury_status")
            )
            if their_player_asset
            else ""
        )
        items.append(
            {
                "partner_team_name": idea.get("partner_team_name") or "",
                "my_player": idea.get("my_player") or "",
                "their_player": idea.get("their_player") or "",
                "my_player_id": str(idea.get("my_player_id") or ""),
                "their_player_id": str(idea.get("their_player_id") or ""),
                "their_player_injury_display": their_player_injury_display,
                "rationale": idea.get("rationale") or "",
                "trade_confidence_label": idea.get("trade_confidence_label") or "",
                "priority": idea.get("priority"),
                "source": "modules.trade_ideas / modules.trade_hub_engine.generate_trade_idea_records_cached",
            }
        )

    status = STATUS_SIGNAL_FOUND if items else STATUS_NO_SIGNAL
    return {
        "key": FOCUS_TRADE,
        "title": "Trade Opportunities",
        "framing": TRADE_STANCE_EMPHASIS.get(stance, NO_TRADE_STANCE_EMPHASIS),
        "status": status,
        "items": items,
        "watch_for": "" if items else TRADE_NO_SIGNAL_WATCH_FOR,
    }


def _roster_focus_area(
    rankings_row: Mapping[str, Any] | None,
    total_teams: int | None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    if rankings_row and total_teams:
        for rank_key, tie_key, label in ROSTER_RANK_FIELDS:
            fact = _rank_fact(rankings_row, rank_key, tie_key, total_teams, label)
            if not fact:
                continue
            fact["source"] = "modules.league_rankings.add_league_detail_ranks"
            # Bottom third of the league on this axis reads as a relative
            # weak spot — a plain arithmetic bucketing of a real rank, not
            # an invented judgment.
            fact["relative_weak_spot"] = fact["rank"] > max(1, (2 * int(total_teams)) // 3)
            items.append(fact)

    status = STATUS_SIGNAL_FOUND if items else STATUS_NO_SIGNAL
    return {
        "key": FOCUS_ROSTER,
        "title": "Roster Construction",
        "status": status,
        "items": items,
        "watch_for": "" if items else ROSTER_NO_SIGNAL_WATCH_FOR,
    }


def build_gm_plan(
    *,
    team_stance: str = "",
    season_phase: str,
    rankings_row: Mapping[str, Any] | None = None,
    total_teams: int | None = None,
    record: Mapping[str, Any] | None = None,
    trade_ideas: Sequence[Mapping[str, Any]] | None = None,
    max_trade_ideas: int = 3,
) -> dict[str, Any]:
    """Assemble a GM Plan from already-computed signals.

    Pure aggregation/framing: no I/O, no new scoring. `rankings_row` is
    expected to be one row (as a mapping) from
    modules.league_rankings.build_league_rankings_frame /
    build_league_rankings_frame_cached (already includes PR #799's tie
    metadata columns); `trade_ideas` is expected to be the (already
    Team-Situation-framed) output of
    modules.trade_hub_engine.generate_trade_idea_records_cached or
    modules.trade_ideas.build_trade_ideas.
    """

    stance = team_stance_module.normalize_stance(team_stance)
    phase = season_phase if season_phase in SEASON_PHASES else PHASE_OFFSEASON_ADJACENT

    return {
        "season_phase": phase,
        "season_phase_label": phase_label(phase),
        "team_stance": stance,
        "team_stance_label": team_stance_module.STANCE_LABELS.get(stance, ""),
        "headline": _headline(stance, phase),
        "focus_areas": [
            _standing_focus_area(rankings_row, total_teams, record),
            _trade_focus_area(stance, trade_ideas or [], max_trade_ideas),
            _roster_focus_area(rankings_row, total_teams),
        ],
    }
