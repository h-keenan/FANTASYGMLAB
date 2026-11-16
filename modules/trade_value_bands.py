"""The ONE definition of how a trade score is worded, badged and colored.

Why this exists (audit C1/C1b): the verdict is decided from the lineup-aware
``trade_score``, but the sentence under it, the Hub/Finder edge badge and the
badge colors each carried their own cut points (500/150/-150/-1200,
500/-500/-1500, per-platform color maps). A trade could read "essentially
even" under ACCEPT or "Fair" next to COUNTER.

Everything now derives from ``band_for_score``:

* verdict band / UI verdict / tone  (``decide_offer_verdict``)
* the direction sentence            (``direction_label``)
* the edge badge                    (``trade_value_band``: Favorable / Fair /
  Slight Overpay / Major Overpay)
* the semantic color                (``color_token``: success / neutral /
  warning / danger)

TypeScript (web + mobile) gets the same table via
``scripts/sync_trade_value_bands.py`` -> ``tradeValueBands.generated.ts``, and
a golden-score test fails if the two ladders ever disagree.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

VERDICT_SMASH_ACCEPT = "SMASH ACCEPT"
VERDICT_ACCEPT = "ACCEPT"
VERDICT_FAIR = "FAIR / PREFERENCE"
VERDICT_COUNTER = "COUNTER"
VERDICT_DECLINE = "DECLINE"
VERDICT_HARD_DECLINE = "HARD DECLINE"

UI_VERDICT_ACCEPT = "ACCEPT"
UI_VERDICT_DECLINE = "DECLINE"
UI_VERDICT_COUNTER = "COUNTER"
UI_VERDICT_FAIR = "FAIR"

# Cut points on the trade score (lineup-aware when a lineup model exists,
# the posture-adjusted value delta otherwise), expressed as a SHARE OF THE DEAL
# (audit P1-3). The old absolute ladder (+-150 / 500 / 1200 ...) read the same
# 10 percent loss as "even" on a 500-point swap and COUNTER on a 10,000-point
# one, and it was lopsided (accept at +500, counter at -400).
#
# Decision (product owner, 2026-11-16): symmetric ladder, scaled to the larger
# side of the trade. The shares were set so a typical 5,000-point one-for-one
# deal lands within about 10 percent of the old cut points (edge 200, accept and
# counter 400, smash and decline 1,000, hard 1,750), and so a loss of about 10
# percent always reads as losing (counter or worse) at every deal size.
EDGE_SHARE = 0.04  # inside +/- this share of the deal the value reads "essentially even"
VERDICT_SHARE = 0.08  # accept above it, counter below minus it (symmetric on purpose)
SMASH_SHARE = 0.20  # smash accept
BIG_SHARE = 0.20  # decline
HARD_SHARE = 0.35  # hard decline
CLOSE_SHARE = 0.14  # legacy (no lineup model) close-call width

# Floor for the deal size: below it every cut stops shrinking, so a 100-point
# bench swap is not graded on a few points of noise. 400 keeps a 10 percent loss
# on a 500-point deal (50 points) past the counter cut (32 points).
MIN_DEAL_SIZE = 400.0
# Used only by callers that genuinely have no asset values (a bare score string
# on an edge badge): about the size of one mid-tier starter for another.
REFERENCE_DEAL_SIZE = 5000.0


@dataclass(frozen=True)
class Cuts:
    """The ladder's cut points, in trade-score points, for one deal size."""

    deal_size: float
    smash: float
    accept: float
    edge: float
    counter: float
    decline: float
    hard: float
    close: float


def deal_size_for(send_total: object, receive_total: object) -> float:
    """Deal size = the larger side's total value (never below the floor)."""

    def _num(value: object) -> float:
        try:
            return max(0.0, float(value))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0

    return max(_num(send_total), _num(receive_total))


def cuts_for(deal_size: object = None) -> Cuts:
    """Cut points for a deal. ``None``/unparseable -> the reference deal."""

    try:
        size = float(deal_size)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        size = REFERENCE_DEAL_SIZE
    if size != size or size <= 0:  # NaN or "no asset values known"
        size = REFERENCE_DEAL_SIZE
    size = max(size, MIN_DEAL_SIZE)
    return Cuts(
        deal_size=size,
        smash=size * SMASH_SHARE,
        accept=size * VERDICT_SHARE,
        edge=size * EDGE_SHARE,
        counter=-size * VERDICT_SHARE,
        decline=-size * BIG_SHARE,
        hard=-size * HARD_SHARE,
        close=size * CLOSE_SHARE,
    )

BADGE_FAVORABLE = "Favorable"
BADGE_FAIR = "Fair"
BADGE_SLIGHT_OVERPAY = "Slight Overpay"
BADGE_MAJOR_OVERPAY = "Major Overpay"

# Semantic color token per verdict tone; clients map the token to their theme.
COLOR_TOKEN_BY_TONE = {
    "accept": "success",
    "fair": "neutral",
    "counter": "warning",
    "decline": "danger",
}


@dataclass(frozen=True)
class ScoreBand:
    id: str
    verdict: str
    ui_verdict: str
    tone: str
    direction_label: str
    badge: str

    @property
    def color_token(self) -> str:
        return COLOR_TOKEN_BY_TONE[self.tone]


BANDS: tuple[ScoreBand, ...] = (
    ScoreBand("smash", VERDICT_SMASH_ACCEPT, UI_VERDICT_ACCEPT, "accept", "You win big on value", BADGE_FAVORABLE),
    ScoreBand("accept", VERDICT_ACCEPT, UI_VERDICT_ACCEPT, "accept", "You win on value", BADGE_FAVORABLE),
    ScoreBand("edge_you", VERDICT_FAIR, UI_VERDICT_FAIR, "fair", "Slight value edge to you", BADGE_FAIR),
    ScoreBand("even", VERDICT_FAIR, UI_VERDICT_FAIR, "fair", "Value is essentially even", BADGE_FAIR),
    ScoreBand("edge_them", VERDICT_FAIR, UI_VERDICT_FAIR, "fair", "Slight value edge to them", BADGE_FAIR),
    ScoreBand("counter", VERDICT_COUNTER, UI_VERDICT_COUNTER, "counter", "You're giving up value", BADGE_SLIGHT_OVERPAY),
    ScoreBand("decline", VERDICT_DECLINE, UI_VERDICT_DECLINE, "decline", "Large value gap against you", BADGE_MAJOR_OVERPAY),
    ScoreBand("hard", VERDICT_HARD_DECLINE, UI_VERDICT_DECLINE, "decline", "Very large value gap against you", BADGE_MAJOR_OVERPAY),
)
_BY_ID = {band.id: band for band in BANDS}


def band_by_id(band_id: str) -> ScoreBand:
    return _BY_ID[band_id]


def band_for_score(score: float, deal_size: object = None) -> ScoreBand:
    """The single ladder, scaled to the deal. Boundary semantics match the
    original verdict (a score exactly on a cut lands in the outer band)."""

    c = cuts_for(deal_size)
    if score >= c.smash:
        return _BY_ID["smash"]
    if score >= c.accept:
        return _BY_ID["accept"]
    if score > c.edge:
        return _BY_ID["edge_you"]
    if score >= -c.edge:
        return _BY_ID["even"]
    if score > c.counter:
        return _BY_ID["edge_them"]
    if score > c.decline:
        return _BY_ID["counter"]
    if score > c.hard:
        return _BY_ID["decline"]
    return _BY_ID["hard"]


def direction_label(score: float, deal_size: object = None) -> str:
    return band_for_score(score, deal_size).direction_label


_EDGE_NUM = re.compile(r"([+-]?\d+(?:\.\d+)?)")


def trade_value_band(value: object, deal_size: object = None) -> str:
    """Badge word for a signed edge ("+237", "-991", 450). Unparseable -> Fair.
    Pass ``deal_size`` whenever the trade's asset values are known."""

    match = _EDGE_NUM.search(str(value if value is not None else "").replace(",", ""))
    if not match:
        return BADGE_FAIR
    return band_for_score(float(match.group(1)), deal_size).badge


def badge_color_token(badge: str) -> str:
    for band in BANDS:
        if band.badge.casefold() == str(badge or "").strip().casefold():
            return band.color_token
    return COLOR_TOKEN_BY_TONE["fair"]


# Scores that straddle every cut point at three deal sizes, for the cross-language
# golden test (the cuts scale with the deal, so the probes do too).
GOLDEN_DEAL_SIZES = (500, 5000, 20000)
GOLDEN_SHARES = (-0.5, -0.35, -0.3499, -0.2, -0.1999, -0.1, -0.0801, -0.08, -0.0799, -0.0401, -0.04, 0, 0.04, 0.0401, 0.0799, 0.08, 0.1999, 0.2, 0.5)


def golden_cases() -> list[dict]:
    cases = []
    for deal in GOLDEN_DEAL_SIZES:
        for share in GOLDEN_SHARES:
            score = round(share * deal, 6)
            cases.append({"deal_size": deal, "score": score, "id": band_for_score(score, deal).id})
    cases.append({"deal_size": None, "score": 100, "id": band_for_score(100).id})
    return cases


def table() -> dict:
    """JSON-able form shipped to the TypeScript clients."""

    return {
        "shares": {
            "smash": SMASH_SHARE, "accept": VERDICT_SHARE, "edge": EDGE_SHARE, "counter": -VERDICT_SHARE,
            "decline": -BIG_SHARE, "hard": -HARD_SHARE, "close": CLOSE_SHARE,
        },
        "min_deal_size": MIN_DEAL_SIZE,
        "reference_deal_size": REFERENCE_DEAL_SIZE,
        "bands": [
            {
                "id": b.id,
                "verdict": b.verdict,
                "ui_verdict": b.ui_verdict,
                "tone": b.tone,
                "color_token": b.color_token,
                "direction_label": b.direction_label,
                "badge": b.badge,
            }
            for b in BANDS
        ],
        "golden": golden_cases(),
    }
