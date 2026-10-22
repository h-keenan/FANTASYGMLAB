from dataclasses import dataclass
from typing import Mapping, Sequence

from modules.rankings import injury_level
from modules.semantic_glyphs import glyph_html


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
    # False in leagues that don't run FAAB (Sleeper settings.waiver_type !=
    # 2): there is no bid to make, so every dollar/percent field is zero
    # and ``rationale`` carries the waiver-priority guidance instead.
    applicable: bool = True
    # "faab" | "rolling" | "reverse_standings" | "unknown" — see
    # sleeper_waiver_mode.
    waiver_mode: str = "faab"
    # Short, evidence-backed reasons the bid moved ("3 teams need a RB and 2
    # of them have more FAAB than you"), strongest first. Never invented:
    # each one is emitted only when the input that produced it was present.
    reasons: tuple[str, ...] = ()
    # "high" | "medium" | "low" — how much real market data backed the bid.
    # Low means the competition/demand inputs were missing, so the range is
    # deliberately wider.
    data_confidence: str = "medium"

    @property
    def why(self) -> str:
        """One-line explanation for the UI: the top reasons, else rationale."""

        if self.reasons:
            return "; ".join(self.reasons[:3]) + "."
        return self.rationale

    def as_label(self) -> str:
        if not self.applicable:
            return waiver_mode_label(self.waiver_mode)
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


# --- Waiver mode ------------------------------------------------------------
#
# Sleeper ``league.settings.waiver_type`` (not in Sleeper's public API docs;
# verified against real league payloads 2026-10-21): 2 = FAAB bidding (claims
# carry ``settings.waiver_bid`` and rosters accrue ``waiver_budget_used``),
# 1 = reverse-standings priority (claims carry no bid, every roster's
# ``waiver_budget_used`` stays 0), 0 = rolling priority (Sleeper's default).
SLEEPER_WAIVER_TYPE_ROLLING = 0
SLEEPER_WAIVER_TYPE_REVERSE_STANDINGS = 1
SLEEPER_WAIVER_TYPE_FAAB = 2

WAIVER_MODE_FAAB = "faab"
WAIVER_MODE_ROLLING = "rolling"
WAIVER_MODE_REVERSE_STANDINGS = "reverse_standings"
WAIVER_MODE_UNKNOWN = "unknown"


def sleeper_waiver_mode(league: Mapping | None) -> str:
    """The league's waiver system from Sleeper's ``settings.waiver_type``."""

    settings = (league or {}).get("settings") if isinstance(league, Mapping) else None
    if not isinstance(settings, Mapping) or settings.get("waiver_type") in (None, ""):
        return WAIVER_MODE_UNKNOWN
    try:
        waiver_type = int(settings.get("waiver_type"))
    except (TypeError, ValueError):
        return WAIVER_MODE_UNKNOWN
    return {
        SLEEPER_WAIVER_TYPE_FAAB: WAIVER_MODE_FAAB,
        SLEEPER_WAIVER_TYPE_REVERSE_STANDINGS: WAIVER_MODE_REVERSE_STANDINGS,
        SLEEPER_WAIVER_TYPE_ROLLING: WAIVER_MODE_ROLLING,
    }.get(waiver_type, WAIVER_MODE_UNKNOWN)


def league_uses_faab(league: Mapping | None) -> bool:
    """True unless Sleeper says the league runs priority waivers.

    An unknown waiver type keeps the FAAB behaviour (fail open) so a payload
    missing the field never silently hides bids in a FAAB league.
    """

    return sleeper_waiver_mode(league) in {WAIVER_MODE_FAAB, WAIVER_MODE_UNKNOWN}


def waiver_mode_label(mode: str) -> str:
    if mode == WAIVER_MODE_ROLLING:
        return "Rolling waivers — no FAAB bid"
    if mode == WAIVER_MODE_REVERSE_STANDINGS:
        return "Reverse-standings waivers — no FAAB bid"
    return "No FAAB bid"


def sleeper_min_bid(league: Mapping | None) -> int:
    """Sleeper's ``settings.waiver_bid_min`` (0 when unset)."""

    settings = (league or {}).get("settings") if isinstance(league, Mapping) else None
    if not isinstance(settings, Mapping):
        return 0
    return max(0, _safe_int(settings.get("waiver_bid_min"), 0))


def priority_waiver_guidance(
    *,
    mode: str,
    player_score: int,
    is_starter: bool = False,
    rivals_needing: int | None = None,
    available: bool = True,
) -> FaabGuidance:
    """Non-FAAB guidance: whether this player is worth a waiver claim.

    Rolling priority is spent by a successful claim, so it is reserved for a
    player who would start for you; reverse-standings priority resets every
    week, so any useful add is worth a claim. No dollar figures, ever.
    """

    reasons: list[str] = []
    if not available or player_score <= 0:
        rationale = "No claim — player is unavailable or has no usable value."
    elif mode == WAIVER_MODE_ROLLING:
        if is_starter:
            rationale = "Worth your waiver priority: he would start for you."
            if rivals_needing:
                reasons.append(
                    f"{rivals_needing} other team{'s' if rivals_needing != 1 else ''} "
                    "would also start him"
                )
        else:
            rationale = (
                "Rolling waivers: a claim costs your priority. Save it for a "
                "starter — try to add him once he clears to free agency."
            )
    elif mode == WAIVER_MODE_REVERSE_STANDINGS:
        rationale = (
            "Reverse-standings waivers: priority resets weekly, so put in a "
            "claim — no bid needed."
        )
    else:
        rationale = "This league doesn't use FAAB — claims follow waiver priority."
    return FaabGuidance(
        point_bid=0,
        low_bid=0,
        high_bid=0,
        budget_scale=0,
        remaining=None,
        min_bid=0,
        pct_low=0,
        pct_high=0,
        rationale=rationale,
        dollars_known=False,
        applicable=False,
        waiver_mode=mode,
        reasons=tuple(reasons),
        data_confidence="medium",
    )


# --- League market context --------------------------------------------------
#
# FAAB is an auction against leaguemates. The bid should be high enough to
# win when rivals both need the player and can pay, and low when nobody else
# does. Everything below is derived from real Sleeper payloads (rosters'
# ``players``/``reserve``/``taxi`` and ``settings.waiver_budget_used``, the
# league's ``roster_positions`` and ``settings.waiver_budget``) plus the
# valuation frame the waiver page already loads.

# Flex slots and the offensive positions they accept. SUPER_FLEX is treated
# as a QB slot for need purposes; IDP_FLEX is ignored (as in #1330).
_FLEX_ELIGIBILITY = {
    "FLEX": ("RB", "WR", "TE"),
    "WRRB_FLEX": ("RB", "WR"),
    "REC_FLEX": ("WR", "TE"),
    "SUPER_FLEX": ("QB",),
    "OP": ("QB",),
}
_SKILL_POSITIONS = ("QB", "RB", "WR", "TE", "K")


def starting_slots_by_position(roster_positions: Sequence[object] | None) -> dict[str, int]:
    """How many lineup slots a player at each position can realistically fill.

    Dedicated slots plus every flex slot that accepts the position. Generous
    by design: "would this player start for that team?" is answered by
    whether he would rank inside their top-N healthy players at his position.
    """

    slots = {pos: 0 for pos in _SKILL_POSITIONS}
    for raw in roster_positions or ():
        slot = str(raw or "").strip().upper()
        if slot in slots:
            slots[slot] += 1
        for pos in _FLEX_ELIGIBILITY.get(slot, ()):
            slots[pos] += 1
    if not any(slots.values()):
        return {"QB": 1, "RB": 3, "WR": 4, "TE": 2, "K": 1}
    return slots


def would_start(candidate_score: float, healthy_scores: Sequence[float], slots: int) -> bool:
    """True when the candidate would rank inside a roster's top ``slots``."""

    if slots <= 0 or candidate_score <= 0:
        return False
    ordered = sorted((float(s) for s in healthy_scores if s is not None), reverse=True)
    if len(ordered) < slots:
        return True
    return float(candidate_score) > ordered[slots - 1]


@dataclass(frozen=True)
class FaabRival:
    roster_id: str
    remaining: int | None
    # Healthy (not Out/IR/Doubtful) active players' scores per position.
    healthy_scores_by_position: Mapping[str, tuple[float, ...]]


@dataclass(frozen=True)
class FaabMarket:
    """League-level auction context for one user's FAAB decisions."""

    rivals: tuple[FaabRival, ...]
    my_remaining: int | None
    slots_by_position: Mapping[str, int]
    my_healthy_scores_by_position: Mapping[str, tuple[float, ...]]
    # Same-position wire scores (available, positive-value free agents),
    # highest first.
    wire_scores_by_position: Mapping[str, tuple[float, ...]]
    # player_id -> {"count", "rank"} from Sleeper's global trending-add list.
    trending_adds: Mapping[str, Mapping[str, int]]


@dataclass(frozen=True)
class FaabCompetition:
    rival_count: int
    rivals_needing: int
    rivals_needing_richer: int
    rivals_needing_with_budget: int
    budgets_known: bool


def _healthy_scores_by_position(frame, score_field: str) -> dict[str, tuple[float, ...]]:
    out: dict[str, list[float]] = {}
    if frame is None or getattr(frame, "empty", True):
        return {}
    for _, row in frame.iterrows():
        pos = str(row.get("position") or "").strip().upper()
        if pos not in _SKILL_POSITIONS:
            continue
        if injury_level(str(row.get("status") or ""), str(row.get("injury_status") or "")) in {
            "moderate",
            "major",
        }:
            continue
        try:
            score = float(row.get(score_field) or 0)
        except (TypeError, ValueError):
            continue
        if score != score:  # NaN
            continue
        out.setdefault(pos, []).append(score)
    return {pos: tuple(sorted(values, reverse=True)) for pos, values in out.items()}


def build_faab_market(
    *,
    league: Mapping | None,
    rosters: Sequence[Mapping] | None,
    my_roster_id: object,
    valued,
    score_field: str,
    free_agents=None,
    trending_adds: Mapping[str, Mapping[str, int]] | None = None,
) -> FaabMarket:
    """Assemble the auction context from real league payloads.

    ``valued`` is the league's valued player frame (rostered players
    included); ``free_agents`` the available wire pool.
    """

    try:
        initial = int(((league or {}).get("settings") or {}).get("waiver_budget"))
    except (TypeError, ValueError):
        initial = None

    def _remaining(roster: Mapping) -> int | None:
        try:
            used = int(((roster or {}).get("settings") or {}).get("waiver_budget_used"))
        except (TypeError, ValueError):
            return None
        if initial is None:
            return None
        return max(0, initial - used)

    by_id = None
    if valued is not None and not getattr(valued, "empty", True) and "player_id" in valued.columns:
        by_id = valued.assign(_pid=valued["player_id"].astype(str))
    rivals: list[FaabRival] = []
    my_scores: dict[str, tuple[float, ...]] = {}
    my_remaining: int | None = None
    my_key = str(my_roster_id or "")
    for roster in rosters or ():
        rid = str(roster.get("roster_id") or "")
        if not rid:
            continue
        ids = {str(pid) for pid in (roster.get("players") or []) if pid is not None}
        parked = {str(pid) for pid in (roster.get("reserve") or []) if pid is not None}
        parked |= {str(pid) for pid in (roster.get("taxi") or []) if pid is not None}
        frame = by_id[by_id["_pid"].isin(ids - parked)] if by_id is not None else None
        scores = _healthy_scores_by_position(frame, score_field)
        if rid == my_key:
            my_scores = scores
            my_remaining = _remaining(roster)
            continue
        rivals.append(FaabRival(rid, _remaining(roster), scores))

    wire: dict[str, list[float]] = {}
    if free_agents is not None and not getattr(free_agents, "empty", True):
        for _, row in free_agents.iterrows():
            if bool(row.get("stale_free_agent") or False):
                continue
            pos = str(row.get("position") or "").strip().upper()
            try:
                score = float(row.get(score_field) or 0)
            except (TypeError, ValueError):
                continue
            if score > 0 and pos:
                wire.setdefault(pos, []).append(score)

    return FaabMarket(
        rivals=tuple(rivals),
        my_remaining=my_remaining,
        slots_by_position=starting_slots_by_position((league or {}).get("roster_positions")),
        my_healthy_scores_by_position=my_scores,
        wire_scores_by_position={pos: tuple(sorted(v, reverse=True)) for pos, v in wire.items()},
        trending_adds=dict(trending_adds or {}),
    )


def estimate_competition(market: FaabMarket, position: str, candidate_score: float) -> FaabCompetition:
    """How many rivals would start this player, and whether they can outbid you."""

    pos = str(position or "").upper()
    slots = int(market.slots_by_position.get(pos, 0))
    needing = [
        rival
        for rival in market.rivals
        if would_start(candidate_score, rival.healthy_scores_by_position.get(pos, ()), slots)
    ]
    budgets_known = market.my_remaining is not None and all(r.remaining is not None for r in market.rivals)
    richer = with_budget = 0
    if budgets_known:
        richer = sum(1 for r in needing if (r.remaining or 0) > (market.my_remaining or 0))
        with_budget = sum(1 for r in needing if (r.remaining or 0) > 0)
    return FaabCompetition(
        rival_count=len(market.rivals),
        rivals_needing=len(needing),
        rivals_needing_richer=richer,
        rivals_needing_with_budget=with_budget,
        budgets_known=budgets_known,
    )


def market_starter_status(market: FaabMarket, position: str, candidate_score: float) -> bool:
    """Would this free agent crack the user's own healthy starting group?"""

    pos = str(position or "").upper()
    return would_start(
        candidate_score,
        market.my_healthy_scores_by_position.get(pos, ()),
        int(market.slots_by_position.get(pos, 0)),
    )


# --- Why the player is on the wire -------------------------------------------

# A "breakout" is the most recent game well above the player's own earlier
# baseline: at least 12 points, and both +8 and 1.8x his prior average.
BREAKOUT_MIN_POINTS = 12.0
BREAKOUT_MIN_JUMP = 8.0
BREAKOUT_MIN_RATIO = 1.8


@dataclass(frozen=True)
class WaiverCatalyst:
    code: str  # "breakout" | "role" | "depth_chart" | "trending"
    text: str
    multiplier: float


def _weekly_points(stat_row: Mapping | None, scoring_key: str) -> list[tuple[int, float]]:
    rows = stat_row.get("weekly") if isinstance(stat_row, Mapping) else None
    out: list[tuple[int, float]] = []
    for entry in rows or ():
        if not isinstance(entry, Mapping):
            continue
        week = _safe_int(entry.get("week"), 0)
        if week <= 0 or not _safe_int(entry.get("games_played"), 1):
            continue
        raw = entry.get(scoring_key, entry.get("fantasy_points_ppr"))
        try:
            out.append((week, float(raw)))
        except (TypeError, ValueError):
            continue
    return sorted(out)


def breakout_catalyst(
    stat_row: Mapping | None,
    *,
    current_week: int | None,
    scoring_key: str = "fantasy_points_ppr",
) -> WaiverCatalyst | None:
    """The last completed week's game vs the player's own prior average."""

    games = _weekly_points(stat_row, scoring_key)
    if not games:
        return None
    last_week, last_points = games[-1]
    if current_week and last_week < int(current_week) - 1:
        return None  # the big game wasn't last week
    prior = [pts for _wk, pts in games[:-1]]
    baseline = (sum(prior) / len(prior)) if prior else 0.0
    if last_points < BREAKOUT_MIN_POINTS or last_points < baseline + BREAKOUT_MIN_JUMP:
        return None
    if baseline > 0 and last_points < baseline * BREAKOUT_MIN_RATIO:
        return None
    if prior:
        text = f"Breakout: {last_points:.1f} pts in Week {last_week} (avg {baseline:.1f} before)"
    else:
        text = f"Breakout: {last_points:.1f} pts in Week {last_week}"
    return WaiverCatalyst("breakout", text, 1.20)


def role_catalysts(row: Mapping | None) -> list[WaiverCatalyst]:
    """Bigger role (the gated usage trend) and depth-chart moves on the row."""

    if row is None:
        return []
    out: list[WaiverCatalyst] = []
    try:
        from modules.rankings import recency_trend_display

        trend = recency_trend_display(row)
    except Exception:
        trend = None
    if trend and trend.get("direction") == "up":
        out.append(WaiverCatalyst("role", f"Usage up {int(trend.get('magnitude_pct') or 0)}% lately", 1.15))
    elif str(row.get("workload_trend") or "").strip() == "Rising":
        out.append(WaiverCatalyst("role", "Role rising", 1.10))
    try:
        delta = int(row.get("depth_chart_order_delta") or 0)
    except (TypeError, ValueError):
        delta = 0
    if delta > 0:
        out.append(
            WaiverCatalyst(
                "depth_chart",
                f"Moved up {delta} spot{'s' if delta != 1 else ''} on the depth chart",
                1.15,
            )
        )
    return out


def trending_catalyst(trending: Mapping[str, int] | None) -> WaiverCatalyst | None:
    """Sleeper's global trending-add list as a demand signal."""

    if not trending:
        return None
    count = _safe_int(trending.get("count"), 0)
    rank = _safe_int(trending.get("rank"), 0)
    if count <= 0:
        return None
    multiplier = 1.25 if 0 < rank <= 10 else 1.10
    return WaiverCatalyst("trending", f"Trending on Sleeper: {count:,} adds in 24h", multiplier)


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _range_span(confidence: str) -> float:
    key = (confidence or "").strip().casefold()
    if key in {"high", "strong"}:
        return 0.15
    if key in {"low", "weak"}:
        return 0.35
    return 0.25


def faab_bid_range_label(guidance: FaabGuidance) -> str:
    """Short headline bid figure only — "$low–$high" when a real budget is
    known, else the percent-of-pool range. Same primary text
    ``format_faab_block_html``'s ``<dd>`` renders, factored out so a caller
    that only has room for one compact number (e.g. the Waivers compact
    row's single inline stat) can show it standalone without the rest of
    the FAAB block."""

    if not guidance.applicable:
        return "Waiver claim"
    if guidance.dollars_known and guidance.remaining is not None:
        return f"${guidance.low_bid}–${guidance.high_bid}"
    return f"{guidance.pct_low}–{guidance.pct_high}%"


def format_faab_block_html(guidance: FaabGuidance, *, compact: bool = False) -> str:
    """User-facing FAAB block. Actionable dollars lead when authority exists."""

    from html import escape

    compact_class = " waiver-faab-block--compact" if compact else ""
    if not guidance.applicable:
        # Non-FAAB league: no dollars anywhere, only claim guidance.
        claim_glyph_html = glyph_html("waiver", size="kicker", extra_class="waiver-faab-block-glyph")
        detail = "" if compact else f"<p>{escape(guidance.rationale)}</p>"
        return (
            f"<div class='waiver-faab-block{compact_class}'>"
            f"<dt>{claim_glyph_html}WAIVERS</dt>"
            f"<dd>{escape(waiver_mode_label(guidance.waiver_mode))}</dd>"
            f"{detail}"
            "</div>"
        )
    primary = faab_bid_range_label(guidance)
    if guidance.dollars_known and guidance.remaining is not None:
        secondary = (
            f"{guidance.pct_low}–{guidance.pct_high}% of "
            f"${guidance.remaining} remaining"
        )
    else:
        secondary = "Set remaining FAAB to see a dollar recommendation."
    extra = "" if compact else (
        f"<p>{escape(secondary)}</p>"
        f"<p>{escape(guidance.why)}</p>"
    )
    # Mobile's FAABGuidance pairs this exact "bid this much" line with a
    # cash-outline icon (colors.success — same green as web's "waiver"
    # glyph below). Reuses the existing restrained glyph set rather than
    # adding a new concept; decorative only, "FAAB BID" is still the label.
    faab_glyph_html = glyph_html("waiver", size="kicker", extra_class="waiver-faab-block-glyph")
    return (
        f"<div class='waiver-faab-block{compact_class}'>"
        f"<dt>{faab_glyph_html}FAAB BID</dt>"
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
    **market_inputs,
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
        **market_inputs,
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
    waiver_mode: str = WAIVER_MODE_FAAB,
    wire_scores: Sequence[float] | None = None,
    competition: FaabCompetition | None = None,
    catalysts: Sequence[WaiverCatalyst] = (),
) -> FaabGuidance:
    """Percent-of-pool heuristic. Does not invent projections or mutate value.

    The bid is a slice of the remaining budget that scales linearly with the
    player's real value (no floor: a 100-value scrub is a minimum bid, not
    the same bid as a 2500-value player), then moves with the evidence that
    is actually present: where he sits on this wire (``wire_scores``), why
    he is there (``catalysts``), how many leaguemates would start him and
    can pay (``competition``), and whether he starts for you. Every move
    that fires is named in ``reasons``. Non-FAAB leagues (``waiver_mode``
    rolling/reverse_standings) get priority guidance and no dollars.
    """

    if waiver_mode in {WAIVER_MODE_ROLLING, WAIVER_MODE_REVERSE_STANDINGS}:
        return priority_waiver_guidance(
            mode=waiver_mode,
            player_score=_safe_int(player_score, 0),
            is_starter=is_starter,
            rivals_needing=competition.rivals_needing if competition else None,
            available=available,
        )

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

    reasons: list[str] = []
    # Own need: a player who would start for you is worth more to you, and
    # one who fills an actual hole in your starting lineup most of all.
    if is_starter and (roster_need or injury_need_match):
        base_pct *= 2.0
        reasons.append(f"Fills a starting {pos or 'lineup'} need for you")
    elif is_starter:
        base_pct *= 1.5
        reasons.append(f"Would start at {pos} for you" if pos else "Would start for you")

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

    if roster_need and not is_starter:
        base_pct *= 1.12

    strategy = (team_strategy or str(settings.get("team_strategy") or "")).strip().casefold()
    if strategy in {"contend", "contender", "fringe_contender", "win-now", "win now"}:
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

    # Value: linear in the player's real score with NO floor. The old 0.5
    # floor gave a 100-value scrub the same bid as a 2500-value player.
    score_factor = min(max(player_score / 5000.0, 0.0), 2.0)
    pct = base_pct * score_factor

    # Where he sits on this wire: the clear best available at his position
    # is worth competing for; one of several near-identical options is not.
    wire = sorted((float(v) for v in (wire_scores or ()) if v and float(v) > 0), reverse=True)
    if wire:
        others = list(wire)
        for index, value in enumerate(others):
            if abs(value - player_score) <= 1e-6:
                del others[index]  # drop this player himself, once
                break
        best_other = others[0] if others else 0.0
        substitutes = sum(1 for v in others if v >= 0.9 * player_score)
        if player_score >= best_other * 1.25:
            pct *= 1.25
            reasons.append(f"Clear best {pos or 'player'} on the wire")
        elif substitutes >= 3:
            pct *= 0.8
            shown = f"{substitutes}" if substitutes < 10 else "10+"
            reasons.append(f"{shown} similar {pos or 'player'}s are also available")

    # Why he's on the wire: a breakout game, a bigger role, a depth-chart
    # move, or league-wide demand. Combined lift capped so stacked signals
    # can't run away.
    catalyst_lift = 1.0
    for catalyst in catalysts or ():
        catalyst_lift *= max(1.0, float(catalyst.multiplier))
        reasons.append(catalyst.text)
    pct *= min(catalyst_lift, 1.45)

    # Competition: FAAB is an auction. Bid up when rivals would start him and
    # have money; bid low when nobody else needs him.
    if competition is not None and competition.rival_count > 0:
        needing = competition.rivals_needing
        if needing == 0:
            pct *= 0.5
            reasons.insert(0, f"No other team would start him at {pos} — a low bid should win")
        else:
            pct *= 1.0 + 0.12 * min(needing, 5)
            team_word = "team needs" if needing == 1 else "teams need"
            if competition.budgets_known:
                richer = competition.rivals_needing_richer
                pct *= 1.0 + 0.08 * min(richer, 3)
                if richer:
                    reasons.insert(
                        0,
                        f"{needing} {team_word} a {pos} and {richer} of them "
                        f"{'has' if richer == 1 else 'have'} more FAAB than you",
                    )
                elif competition.rivals_needing_with_budget == 0:
                    pct *= 0.7
                    reasons.insert(0, f"{needing} {team_word} a {pos}, but none has FAAB left")
                else:
                    reasons.insert(0, f"{needing} {team_word} a {pos}; none has more FAAB than you")
            else:
                reasons.insert(0, f"{needing} {team_word} a {pos}")

    # Never sink more than 60% of the remaining pool into one claim.
    pct = min(pct, 0.60)
    faab = int(round(spend_pool * pct))
    faab = _clamp(faab, 0, spend_pool)
    if faab > 0:
        faab = max(faab, min(min_bid_i, spend_pool)) if min_bid_i else faab
    elif player_score > 0 and min_bid_i > 0 and min_bid_i <= spend_pool:
        faab = min_bid_i

    # Honest ranges: widen when the market inputs were missing.
    market_inputs = sum(
        1
        for present in (competition is not None and competition.rival_count > 0, bool(wire), dollars_known)
        if present
    )
    data_confidence = "high" if market_inputs == 3 else ("medium" if market_inputs == 2 else "low")
    span = _range_span(confidence)
    if data_confidence == "low":
        span = min(0.45, span + 0.10)
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
    minimum_bid_only = faab <= max(1, min_bid_i)
    if faab == 0 and player_score > 0:
        # Replacement-level value: a minimum bid, shown as an honest range
        # rather than a bare "$0" that reads like "don't claim".
        low = min(min_bid_i, spend_pool)
        high = _clamp(max(min_bid_i, 1), low, spend_pool)
    if high == 0 and faab == 0:
        pct_low = pct_high = 0
    else:
        pct_low = _clamp(int(round(100.0 * low / spend_pool)), 0, 100)
        pct_high = _clamp(int(round(100.0 * high / spend_pool)), 0, 100)
        if pct_high <= pct_low and faab > 0:
            pct_high = _clamp(pct_low + 1, 0, 100)
            if pct_high == pct_low and pct_low > 0:
                pct_low = _clamp(pct_low - 1, 0, 100)

    if minimum_bid_only and not is_starter:
        rationale = "Replacement-level value — a minimum bid is enough; claim only if the roster spot is free."
    elif is_starter and (roster_need or injury_need_match):
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
        reasons=tuple(dict.fromkeys(reasons)),
        data_confidence=data_confidence,
    )


def faab_guidance_for_free_agent(
    row: Mapping,
    *,
    score_field: str,
    league_settings: Mapping | None,
    waiver_mode: str,
    market: FaabMarket | None,
    budget_initial: int | None,
    remaining_budget: int | None,
    needed_positions: Sequence[str] = (),
    min_bid: int = 0,
    week: int | None = None,
    team_strategy: str = "",
    season_stats: Mapping[str, Mapping] | None = None,
    scoring_key: str = "fantasy_points_ppr",
) -> FaabGuidance:
    """Full-context FAAB guidance for one wire player.

    One place that derives every market input from real data (starter
    status, competition, wire depth, catalysts) so the mobile/web-next
    endpoint and any other caller can't drift on which modifiers apply.
    """

    try:
        score_raw = float(row.get(score_field) or 0)
    except (TypeError, ValueError):
        score_raw = 0.0
    if score_raw != score_raw:  # NaN
        score_raw = 0.0
    player_score = int(round(score_raw))
    position = str(row.get("position") or "").strip().upper()
    needed = {str(pos).upper() for pos in needed_positions or ()}
    player_id = str(row.get("player_id") or "")

    competition = estimate_competition(market, position, player_score) if market and market.rivals else None
    is_starter = market_starter_status(market, position, player_score) if market else False

    catalysts: list[WaiverCatalyst] = []
    if season_stats and player_id:
        breakout = breakout_catalyst(season_stats.get(player_id), current_week=week, scoring_key=scoring_key)
        if breakout:
            catalysts.append(breakout)
    catalysts.extend(role_catalysts(row))
    trending = trending_catalyst((market.trending_adds if market else {}).get(player_id))
    if trending:
        catalysts.append(trending)

    return recommend_faab_guidance(
        player_score=player_score,
        position=position,
        is_starter=is_starter,
        budget=budget_initial or 100,
        league_settings=dict(league_settings or {}),
        status=str(row.get("status") or ""),
        injury_status=str(row.get("injury_status") or ""),
        injury_need_match=bool(row.get("injury_replacement_fit")),
        remaining_budget=remaining_budget,
        min_bid=min_bid,
        team_strategy=team_strategy,
        week=week,
        roster_need=position in needed,
        confidence=str(row.get("opportunity_confidence") or ""),
        available=not bool(row.get("stale_free_agent")),
        waiver_mode=waiver_mode,
        wire_scores=(market.wire_scores_by_position.get(position, ()) if market else None),
        competition=competition,
        catalysts=catalysts,
    )
