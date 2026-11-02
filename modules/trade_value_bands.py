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

# Posture-aware labels (modules.trade_posture). They are NOT rungs of the score
# ladder: they replace an ACCEPT-looking market value when the team's posture
# cost pulls the verdict score below an accept. ui_verdict/tone come from the
# score band the trade actually lands in (FAIR or COUNTER), so old clients that
# only know the four UI verdicts degrade to those and show this as the band note.
VERDICT_VALUE_COSTS_LINEUP = "GOOD VALUE, COSTS YOUR LINEUP"
VERDICT_VALUE_MOVES_REBUILD = "VALUE WIN, MOVES YOU TOWARD A REBUILD"
VERDICT_VALUE_AGAINST_REBUILD = "VALUE WIN, AGAINST YOUR REBUILD"
POSTURE_VERDICTS = (VERDICT_VALUE_COSTS_LINEUP, VERDICT_VALUE_MOVES_REBUILD, VERDICT_VALUE_AGAINST_REBUILD)

UI_VERDICT_ACCEPT = "ACCEPT"
UI_VERDICT_DECLINE = "DECLINE"
UI_VERDICT_COUNTER = "COUNTER"
UI_VERDICT_FAIR = "FAIR"

# Cut points on the trade score (lineup-aware when a lineup model exists,
# the posture-adjusted value delta otherwise).
SMASH = 1500
ACCEPT = 500
EDGE = 150  # inside +/-EDGE the value reads "essentially even"
COUNTER = -400
DECLINE = -1200
HARD = -2200

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


def band_for_score(score: float) -> ScoreBand:
    """The single ladder. Boundary semantics match the original verdict."""

    if score >= SMASH:
        return _BY_ID["smash"]
    if score >= ACCEPT:
        return _BY_ID["accept"]
    if score > EDGE:
        return _BY_ID["edge_you"]
    if score >= -EDGE:
        return _BY_ID["even"]
    if score > COUNTER:
        return _BY_ID["edge_them"]
    if score > DECLINE:
        return _BY_ID["counter"]
    if score > HARD:
        return _BY_ID["decline"]
    return _BY_ID["hard"]


def direction_label(score: float) -> str:
    return band_for_score(score).direction_label


_EDGE_NUM = re.compile(r"([+-]?\d+(?:\.\d+)?)")


def trade_value_band(value: object) -> str:
    """Badge word for a signed edge ("+237", "-991", 450). Unparseable -> Fair."""

    match = _EDGE_NUM.search(str(value if value is not None else "").replace(",", ""))
    if not match:
        return BADGE_FAIR
    return band_for_score(float(match.group(1))).badge


def badge_color_token(badge: str) -> str:
    for band in BANDS:
        if band.badge.casefold() == str(badge or "").strip().casefold():
            return band.color_token
    return COLOR_TOKEN_BY_TONE["fair"]


# Scores that straddle every cut point, for the cross-language golden test.
GOLDEN_SCORES = (-3000, -2200, -2199, -1200, -1199, -401, -400, -399, -151, -150, 0, 150, 151, 499, 500, 1499, 1500, 3000)


def table() -> dict:
    """JSON-able form shipped to the TypeScript clients."""

    return {
        "cuts": {"smash": SMASH, "accept": ACCEPT, "edge": EDGE, "counter": COUNTER, "decline": DECLINE, "hard": HARD},
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
        "golden": [{"score": s, "id": band_for_score(s).id} for s in GOLDEN_SCORES],
    }
