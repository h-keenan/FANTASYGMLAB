"""Commissioner trade veto calculator: how outrageous is this trade, for the
WHOLE team on each side, not just the pieces that move.

Owner request (coridian_): "in the commissioner section we need a trade veto
calculator for outrage fairness that takes into account their whole team".

Nothing here is a new valuation model. Each side's number comes from the one
lineup model the Trade Analyzer uses (``roster_value_model.evaluate_swap`` over
that team's real roster, at that team's own posture), so the result agrees with
an Analyzer run of the same package from either seat. What this module adds is
the commissioner's question: is one side being fleeced in a way their own roster
and direction do not explain?

Per side (``SideResult``):

* ``market_delta``: value received minus value sent (players at healthy value,
  picks at the Analyzer's pick price). The "plain trade calculator" number.
* ``team_score``: the Analyzer's posture-weighted trade score for THIS roster
  (lineup points, depth, byes, injuries, holes filled from the pool, plus what
  a contender or rebuilder values). This is the whole-team part.
* ``points_per_week``: expected lineup points per week gained or lost.

Outrage (0-100, one number for the trade) reads the side that comes out worst
for their own roster (``team_score``) and asks how far the market and the team
read are both against them:

* team read fine (``team_score`` within the "essentially even" edge): a market
  gap is explainable (a rebuilder selling a vet for picks, a team with surplus
  at a position), so only 40% of the market gap counts and the band tops out at
  "Uneven but explainable";
* team read bad: 60% market gap + 40% team gap, each normalised to the "hard
  decline" rung of ``trade_value_bands``.
* repeat pattern: when the same side already won earlier lopsided trades from
  the same partner, up to ``HISTORY_MAX`` more points, never enough to move a
  fair trade (history only counts once the trade itself reads 25+).

It is a decision aid. It never calls anything collusion, and every band says
the league's own rules decide.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from modules import trade_value_bands as bands

# Normalisation rung: a side this far behind is "as bad as it gets".
FULL_GAP = float(-bands.HARD)
EXPLAINABLE_MARKET_WEIGHT = 0.4
MARKET_WEIGHT = 0.6
TEAM_WEIGHT = 0.4
HISTORY_PER_TRADE = 6.0
HISTORY_MAX = 15.0
HISTORY_MIN_BASE = 25.0

BAND_FAIR = "fair"
BAND_EXPLAINABLE = "explainable"
BAND_LOPSIDED = "lopsided"
BAND_OUTRAGE = "outrage"

BAND_FLOORS = ((70.0, BAND_OUTRAGE), (45.0, BAND_LOPSIDED), (20.0, BAND_EXPLAINABLE))
BAND_LABELS = {
    BAND_FAIR: "Fair",
    BAND_EXPLAINABLE: "Uneven but explainable",
    BAND_LOPSIDED: "Lopsided: worth a conversation",
    BAND_OUTRAGE: "Outrage-level: review before it processes",
}
BAND_ADVICE = {
    BAND_FAIR: "Nothing here needs a commissioner. Both rosters come out in a reasonable place.",
    BAND_EXPLAINABLE: "One side gives up market value, but their own roster or direction explains most of it. Leave it unless you know something the numbers cannot see.",
    BAND_LOPSIDED: "One side loses real value and the trade does not help their roster enough to explain it. Ask both managers about it before deciding; a veto is your league's call.",
    BAND_OUTRAGE: "One side loses a lot, both on the market and for their own roster. This is the kind of trade leagues usually review. Your league rules decide whether to veto; ask both managers first.",
}
LIMITS = (
    "Values and lineup effects are estimates from projections and the market, not facts.",
    "A manager can have reasons the numbers cannot see (a bye-week plan, a keeper deal, an off-platform side deal that is allowed).",
    "This is a signal to look at a trade, never proof of collusion. Your league's rules decide.",
)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def band_for(outrage: float) -> str:
    for floor, band in BAND_FLOORS:
        if outrage >= floor:
            return band
    return BAND_FAIR


def _gap_norm(delta: float) -> float:
    """0 when the side is not behind, 1 at the "hard decline" rung."""

    return _clamp(-float(delta) / FULL_GAP)


def history_bonus(prior_lopsided_wins: int) -> float:
    return min(HISTORY_MAX, HISTORY_PER_TRADE * max(0, int(prior_lopsided_wins)))


def _direction_text(posture: str) -> str:
    return {"contend": "a contender", "rebuild": "rebuilding", "retool": "retooling"}.get(posture, "")


def side_reasons(side: Mapping[str, Any]) -> list[str]:
    """Plain-English lines for one side, from the numbers the model produced."""

    name = str(side.get("team_name") or "This team")
    out: list[str] = []
    market = float(side.get("market_delta") or 0)
    score = float(side.get("team_score") or 0)
    ppw = float(side.get("points_per_week") or 0)
    posture = _direction_text(str(side.get("posture") or ""))
    if market <= bands.DECLINE:
        out.append(f"{name} gives up {abs(round(market)):,} more in market value than they get back.")
    elif market >= bands.ACCEPT:
        out.append(f"{name} gets {round(market):,} more in market value than they send.")
    if ppw <= -1.0:
        out.append(f"{name}'s lineup loses about {abs(ppw):.1f} points a week.")
    elif ppw >= 1.0:
        out.append(f"{name}'s lineup gains about {ppw:.1f} points a week.")
    worst = side.get("worst_position")
    if worst and float(worst.get("per_week_delta") or 0) <= -1.0:
        out.append(f"The hit lands at {worst['position']} ({worst['per_week_delta']:+.1f} pts/wk).")
    if market <= bands.COUNTER and score >= -bands.EDGE:
        lead = f"As {posture}, {name}" if posture else name
        out.append(f"{lead} still comes out about even on their own roster, which explains much of the gap.")
    if score <= bands.DECLINE:
        out.append(f"For {name}'s whole roster this reads as a clear loss.")
    return out


def assess(
    sides: Sequence[Mapping[str, Any]],
    *,
    prior_lopsided_wins: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Outrage score and band from two evaluated sides.

    ``sides`` carry ``roster_id``, ``team_name``, ``market_delta``,
    ``team_score``, ``points_per_week``, ``posture`` and optionally
    ``worst_position``. ``prior_lopsided_wins`` maps roster id to how many
    earlier lopsided trades that roster won from this same partner."""

    if len(sides) != 2:
        raise ValueError("a veto check needs exactly two sides")
    prior = {str(k): int(v) for k, v in (prior_lopsided_wins or {}).items()}
    loser = min(sides, key=lambda s: (float(s["team_score"]), float(s["market_delta"])))
    winner = next(s for s in sides if s is not loser)
    market_gap = _gap_norm(float(loser["market_delta"]))
    team_gap = _gap_norm(float(loser["team_score"]))
    explained = float(loser["team_score"]) >= -bands.EDGE
    if explained:
        base = 100.0 * EXPLAINABLE_MARKET_WEIGHT * market_gap
    else:
        base = 100.0 * (MARKET_WEIGHT * market_gap + TEAM_WEIGHT * team_gap)
    history = 0.0
    prior_wins = prior.get(str(winner["roster_id"]), 0)
    if base >= HISTORY_MIN_BASE and not explained:
        history = history_bonus(prior_wins)
    outrage = round(_clamp(base + history, 0.0, 100.0), 1)
    band = band_for(outrage)
    reasons = side_reasons(loser)
    if history > 0:
        reasons.append(
            f"{winner.get('team_name') or 'The other team'} also won {prior_wins} earlier lopsided "
            f"trade{'s' if prior_wins != 1 else ''} from {loser.get('team_name') or 'this team'} this season."
        )
    if not reasons:
        reasons = ["Both rosters come out close to even on value and lineup points."]
    return {
        "outrage": outrage,
        "band": band,
        "label": BAND_LABELS[band],
        "advice": BAND_ADVICE[band],
        "explained_by_roster": bool(explained and market_gap > 0),
        "hurt_roster_id": str(loser["roster_id"]),
        "reasons": reasons[:5],
        "history_points": round(history, 1),
        "limits": list(LIMITS),
    }
