from dataclasses import dataclass
from typing import Mapping, Sequence

from modules.rankings import injury_level


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


from modules import runtime_trace


@dataclass(frozen=True)
class FaabGuidance:
    """Rule-of-thumb FAAB presentation — not a precise auction solver."""

    point_bid: int
    low_bid: int
    high_bid: int
    budget_scale: int
    remaining: int | None
    min_bid: int
    pct_low: int
    pct_high: int
    rationale: str
    dollars_known: bool

    def as_label(self) -> str:
        if self.dollars_known and self.remaining is not None:
            return f"${self.low_bid}–${self.high_bid} of ${self.remaining} remaining"
        return f"{self.pct_low}–{self.pct_high}% of remaining FAAB"


@dataclass(frozen=True)
class FaabBudgetContext:
    remaining: int | None
    initial: int | None
    used: int | None
    source: str


def sleeper_faab_budget_context(
    league: Mapping | None,
    rosters: Sequence[Mapping] | None,
    *,
    roster_id: object,
) -> FaabBudgetContext:
    """Resolve Sleeper's league-scoped FAAB authority from loaded payloads."""

    league_settings = dict((league or {}).get("settings") or {})
    try:
        initial = int(league_settings.get("waiver_budget"))
    except (TypeError, ValueError):
        initial = None
    selected = next(
        (
            row
            for row in (rosters or ())
            if str(row.get("roster_id") or "") == str(roster_id or "")
        ),
        None,
    )
    try:
        used = int(((selected or {}).get("settings") or {}).get("waiver_budget_used"))
    except (TypeError, ValueError):
        used = None
    if initial is None or used is None:
        return FaabBudgetContext(None, initial, used, "unavailable")
    return FaabBudgetContext(max(0, initial - used), initial, max(0, used), "sleeper")


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _range_span(confidence: str) -> float:
    key = (confidence or "").strip().casefold()
    if key in {"high", "strong"}:
        return 0.15
    if key in {"low", "weak"}:
        return 0.35
    return 0.25


def format_faab_block_html(guidance: FaabGuidance, *, compact: bool = False) -> str:
    """User-facing FAAB block. Actionable dollars lead when authority exists."""

    from html import escape

    if guidance.dollars_known and guidance.remaining is not None:
        primary = f"${guidance.low_bid}–${guidance.high_bid}"
        secondary = (
            f"{guidance.pct_low}–{guidance.pct_high}% of "
            f"${guidance.remaining} remaining"
        )
    else:
        primary = f"{guidance.pct_low}–{guidance.pct_high}%"
        secondary = "Set remaining FAAB to see a dollar recommendation."
    compact_class = " waiver-faab-block--compact" if compact else ""
    extra = "" if compact else (
        f"<p>{escape(secondary)}</p>"
        f"<p>{escape(guidance.rationale)}</p>"
    )
    return (
        f"<div class='waiver-faab-block{compact_class}'>"
        "<dt>FAAB BID</dt>"
        f"<dd>{escape(primary)}</dd>"
        f"{extra}"
        "</div>"
    )


@runtime_trace.traced("waiver_generation", phase="waiver_generation")
def recommend_faab(
    player_score: int,
    position: str,
    is_starter: bool = False,
    budget: int = 100,
    league_settings: dict | None = None,
    status: str = "",
    injury_status: str = "",
    injury_need_match: bool = False,
    team_injury_pressure: int = 0,
    remaining_budget: int | None = None,
    min_bid: int = 0,
    team_strategy: str = "",
    week: int | None = None,
    roster_need: bool = False,
    confidence: str = "",
    available: bool = True,
) -> int:
    """Deterministic FAAB point estimate. See recommend_faab_guidance for ranges."""

    return recommend_faab_guidance(
        player_score,
        position,
        is_starter=is_starter,
        budget=budget,
        league_settings=league_settings,
        status=status,
        injury_status=injury_status,
        injury_need_match=injury_need_match,
        team_injury_pressure=team_injury_pressure,
        remaining_budget=remaining_budget,
        min_bid=min_bid,
        team_strategy=team_strategy,
        week=week,
        roster_need=roster_need,
        confidence=confidence,
        available=available,
    ).point_bid


def recommend_faab_guidance(
    player_score: int,
    position: str,
    is_starter: bool = False,
    budget: int = 100,
    league_settings: dict | None = None,
    status: str = "",
    injury_status: str = "",
    injury_need_match: bool = False,
    team_injury_pressure: int = 0,
    remaining_budget: int | None = None,
    min_bid: int = 0,
    team_strategy: str = "",
    week: int | None = None,
    roster_need: bool = False,
    confidence: str = "",
    available: bool = True,
) -> FaabGuidance:
    """Percent-of-pool heuristic. Does not invent projections or mutate value."""

    budget_scale = max(0, _safe_int(budget, 100) or 100)
    min_bid_i = max(0, _safe_int(min_bid, 0))
    remaining = None if remaining_budget is None else max(0, _safe_int(remaining_budget, 0))
    spend_pool = remaining if remaining is not None else budget_scale
    dollars_known = remaining is not None

    empty = FaabGuidance(
        point_bid=0,
        low_bid=0,
        high_bid=0,
        budget_scale=budget_scale,
        remaining=remaining,
        min_bid=min_bid_i,
        pct_low=0,
        pct_high=0,
        rationale="No bid — player is unavailable or has no usable dynasty value.",
        dollars_known=dollars_known,
    )
    if not available or player_score <= 0 or spend_pool <= 0:
        return empty
    if min_bid_i > spend_pool:
        return empty

    # Baseline % by position, loosely inspired by typical FAAB strategy ranges.
    base_pct = 0.03  # 3%

    pos = (position or "").upper()
    if pos == "RB":
        base_pct = 0.10
    elif pos == "WR":
        base_pct = 0.07
    elif pos == "TE":
        base_pct = 0.05
    elif pos == "QB":
        base_pct = 0.02

    if is_starter:
        base_pct *= 1.5

    settings = dict(league_settings or {})
    league_format = str(settings.get("league_format") or "Dynasty")
    scoring_format = str(settings.get("scoring_format") or "PPR")
    qb_format = str(settings.get("qb_format") or "1QB")
    te_premium = bool(settings.get("te_premium"))
    league_size = max(8, min(18, _safe_int(settings.get("league_size"), 12) or 12))
    starter_count = max(6, _safe_int(settings.get("starter_count"), 9) or 9)
    flex_count = max(0, _safe_int(settings.get("flex_count"), 2))
    bench_count = max(0, _safe_int(settings.get("bench_count"), 0))
    taxi_count = max(0, _safe_int(settings.get("taxi_count"), 0))
    ir_count = max(0, _safe_int(settings.get("ir_count"), 0))
    reserve_depth = bench_count + taxi_count + ir_count

    if pos == "QB":
        if qb_format == "2QB":
            base_pct *= 2.25
        elif qb_format == "Superflex":
            base_pct *= 1.85

    if scoring_format == "Standard":
        if pos == "RB":
            base_pct *= 1.08
        elif pos in {"WR", "TE"}:
            base_pct *= 0.95
    elif scoring_format == "Half-PPR":
        if pos == "RB":
            base_pct *= 1.03
        elif pos == "WR":
            base_pct *= 0.99
    elif scoring_format == "PPR":
        if pos == "WR":
            base_pct *= 1.03
        elif pos == "TE":
            base_pct *= 1.02

    if te_premium and pos == "TE":
        base_pct *= 1.12

    if league_format == "Redraft" and not is_starter:
        base_pct *= 0.88
    elif league_format == "Dynasty" and not is_starter and pos in {"RB", "WR", "TE"}:
        base_pct *= 1.05

    base_pct *= 1 + max(-3, min(6, league_size - 12)) * 0.04
    lineup_pressure = max(-3, min(6, (starter_count - 9) + (flex_count - 2)))
    if pos in {"RB", "WR", "TE"}:
        base_pct *= 1 + (lineup_pressure * 0.015)
    elif pos == "QB" and qb_format in {"Superflex", "2QB"}:
        base_pct *= 1 + max(0, lineup_pressure) * 0.010
    if reserve_depth >= 12:
        base_pct *= 1.12
    elif reserve_depth >= 8:
        base_pct *= 1.06

    injury_key = injury_level(status, injury_status)
    injury_discount = {
        "healthy": 1.0,
        "minor": 0.88,
        "moderate": 0.66,
        "major": 0.48,
    }.get(injury_key, 1.0)
    if league_format == "Dynasty" and not is_starter and injury_key in {"moderate", "major"}:
        injury_discount *= 1.12
    base_pct *= injury_discount

    if injury_need_match and injury_key == "healthy":
        base_pct *= 1.15
        if _safe_int(team_injury_pressure, 0) >= 2:
            base_pct *= 1.08

    if roster_need:
        base_pct *= 1.12

    strategy = (team_strategy or str(settings.get("team_strategy") or "")).strip().casefold()
    if strategy in {"contend", "contender", "win-now", "win now"}:
        base_pct *= 1.10 if is_starter else 0.92
    elif strategy in {"rebuild", "rebuilding", "tank"}:
        base_pct *= 0.90 if is_starter else 1.08

    resolved_week = week
    if resolved_week is None and settings.get("week") not in (None, ""):
        resolved_week = _safe_int(settings.get("week"), 0) or None
    if resolved_week is not None and int(resolved_week) >= 12:
        if league_format == "Redraft" and not is_starter:
            base_pct *= 0.75
        elif league_format == "Dynasty" and not is_starter:
            base_pct *= 0.95

    score_factor = min(max(player_score / 5000.0, 0.5), 2.0)
    pct = base_pct * score_factor
    faab = int(round(spend_pool * pct))
    faab = _clamp(faab, 0, spend_pool)
    if faab > 0:
        faab = max(faab, min(min_bid_i, spend_pool)) if min_bid_i else faab
    elif player_score > 0 and min_bid_i > 0 and min_bid_i <= spend_pool:
        faab = min_bid_i

    span = _range_span(confidence)
    low = _clamp(int(round(faab * (1.0 - span))), 0, spend_pool)
    high = _clamp(int(round(faab * (1.0 + span))), 0, spend_pool)
    if faab > 0 and min_bid_i:
        low = max(low, min(min_bid_i, spend_pool))
        high = max(high, low)
    if high < low:
        high = low
    if low == high and faab > 0:
        pad = max(1, int(round(faab * max(span, 0.15))))
        low = _clamp(faab - pad, min_bid_i if min_bid_i else 0, spend_pool)
        high = _clamp(faab + pad, low, spend_pool)
    if high == 0 and faab == 0:
        pct_low = pct_high = 0
    else:
        pct_low = _clamp(int(round(100.0 * low / spend_pool)), 0, 100)
        pct_high = _clamp(int(round(100.0 * high / spend_pool)), 0, 100)
        if pct_high <= pct_low and faab > 0:
            pct_high = _clamp(pct_low + 1, 0, 100)
            if pct_high == pct_low and pct_low > 0:
                pct_low = _clamp(pct_low - 1, 0, 100)

    if is_starter and (roster_need or injury_need_match):
        rationale = "Aggressive add because it fills a starting or injury-driven need."
    elif is_starter:
        rationale = "Startable add — bid to win the claim, not to empty the budget."
    elif roster_need:
        rationale = "Roster-need depth — spend a meaningful slice, not a token bid."
    elif player_score >= 7000:
        rationale = "High dynasty value on the wire — compete, but leave budget for later."
    else:
        rationale = "Speculative / depth add — keep the bid proportional to remaining FAAB."

    return FaabGuidance(
        point_bid=faab,
        low_bid=low,
        high_bid=high,
        budget_scale=budget_scale,
        remaining=remaining,
        min_bid=min_bid_i,
        pct_low=pct_low,
        pct_high=pct_high,
        rationale=rationale,
        dollars_known=dollars_known,
    )
