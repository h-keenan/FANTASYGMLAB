"""Team posture for the Trade Analyzer: who the user's team IS, and what a trade does to that.

Owner report (coridian_, 2026-11-01, Trade Analyzer on a phone): a contender
SENDS Tee Higgins and RECEIVES an IR rookie WR plus a 2028 R1. The card said
SMASH ACCEPT next to "-90 lineup pts over Weeks 8-17" and "brings back injured
production". "It must know team status." Two root causes, both fixed here
rather than patched:

1. The web client hard-coded ``strategy: "retool"``, so the verdict never knew
   the team was a contender. ``resolve_posture`` makes the SERVER the owner of
   that fact: a declared Team Situation wins, else the auto classification the
   league rankings already compute (roster strength blended with the real
   record by ``record_signal``, age curve and draft capital), else the client's
   value. Nothing new is invented; the existing signals are reused.
2. Even with the right posture, the engine priced lineup points at the
   posture's market weight but had no notion of the *competitive window* or of
   *direction*. ``assess`` adds exactly those two terms, derived from numbers
   the lineup model already produced (docs/trade-engine-v2.md, "Team posture").

Everything here is a consequence of two small tables (``WINDOW_WIN_WEIGHT`` and
``ORIENTATION``) plus a win-probability slope. There is no per-position or
per-player rule, no hard cap on a verdict and no relabelling after the fact:
the window and direction cost are terms of the ONE trade score, so the verdict
band, the UI verdict, the Hub/Finder suggestion bar and the Analyzer all read
the same number against the same rungs. When the market value alone would say
accept and the window cost pulls the score below it, ``window_overrules_value``
reports that as a fact for the words around the verdict; it never changes it.
"""

from __future__ import annotations

import re

import math
from typing import Any, Mapping, Sequence

from modules.team_eval import normalize_team_strategy, team_strategy_label
from modules.trade_lineup_model import STATIC_VALUE_PER_POINT

# --- parameters (all approximate; see docs/trade-engine-v2.md) ----------------

# What one EXPECTED REGULAR-SEASON WIN is worth to a team in each posture, as a
# multiple of the market price of the lineup points that make one win: what a
# contender pays to keep its playoff odds (seed, bye, title window), what a
# rebuilder does not care about. It is a multiple of the league's OWN price
# scale -- ``win_value = weight * value_per_point / WIN_PROB_PER_POINT`` (value
# units per point x points per win), not an absolute number of value units. The
# old absolute 700/win was calibrated on a market where a first-round pick was
# ~3k; in a league whose R1 picks price at 5.5-9.8k it was a rounding error.
#
# The scaled weights (0.5 / 0.35 / 0.15) fixed the scale but were still too
# small to be the *whole* window cost: a fringe contender selling its best
# player for two R1s (~156 lineup points, ~2 expected wins, +5.6k market value)
# still scored +1269 (an ACCEPT-level number), and the verdict was patched
# afterwards with a relabel (GOOD VALUE, COSTS YOUR LINEUP) and a forced FAIR UI
# verdict while every consumer of the score (counter search, Hub/Finder gate,
# bot feeds) still saw an accept. The cost now lives in the score: a win-now
# team pays a window premium equal to the market price of the points
# themselves (contender 1.0), on top of the w_now emphasis, with the ladder
# kept in the same proportions as before (x2); retool is not a window team and
# stays at 0.15 (doubling it turned a sensible thin-roster 2-for-1 upgrade from
# COUNTER into DECLINE). Calibration evidence, 4 public
# leagues, "sell the top skill player for two R1s": at x1 the fringe-contender
# sale scored +1269, at x1.5 +456, at x2 -357, at x3 -1984; the same x2 turns
# a +4.2k contender sale that cost 107 lineup points from +252 into -1601. It
# does not touch trades that keep or add lineup (gains are credited at a
# quarter), nor sales that cost under a win and clear a very large value gap.
WINDOW_WIN_WEIGHT: dict[str, float] = {
    "contender": 1.0,
    "fringe_contender": 0.7,
    "retool": 0.15,
    "rebuild": 0.0,
    "tank": 0.0,
}
# Extra weight on REAL lineup points (value units per point = the model's k)
# beyond what ``trade_lineup_model.POSTURE_WEIGHTS`` already applies
# (contender 1.50 ... tank 1.00). A rebuilding team's short-term lineup, up or
# down, is worth less than the market's present-value share says; this takes
# the net point weight to rebuild ~0.65 and tank ~0.40. Contender-side
# emphasis is the wins term below, not this table.
PRESENT_ADJUST: dict[str, float] = {
    "contender": 0.0,
    "fringe_contender": 0.0,
    "retool": 0.0,
    "rebuild": -0.40,
    "tank": -0.60,
}
# Where a posture wants its assets: +1 = present (lineup now), -1 = future
# (youth, picks). Retool is deliberately neutral.
ORIENTATION: dict[str, float] = {
    "contender": 1.0,
    "fringe_contender": 0.6,
    "retool": 0.0,
    "rebuild": -0.8,
    "tank": -1.0,
}
# Share of the *misaligned* present<->future conversion (value units) charged
# as a direction penalty.
DIRECTION_RATE = 0.10
# Playoff odds saturate: a gain in lineup points is credited at this share of
# what the same loss is charged.
GAIN_CREDIT = 0.25
# Weekly team-score standard deviation (points) behind the win-probability
# slope. P(win) vs one opponent ~ Phi(d / (sqrt(2) * sigma)); slope at an even
# matchup = phi(0) / (sqrt(2) * sigma) per point per week.
WEEKLY_TEAM_SD = 22.0
WIN_PROB_PER_POINT = 0.3989422804014327 / (math.sqrt(2.0) * WEEKLY_TEAM_SD)
# A lineup cost is "material" when it costs this many expected wins or this
# share of the roster's projected points over the remaining weeks.
MATERIAL_WINS = 0.35
MATERIAL_LINEUP_SHARE = 0.03
# A conversion between present and future is "a direction change" above this
# many value units (labels), and only the part of a misaligned conversion above
# the deadband is charged (ordinary bench-for-pick churn is not a direction
# change).
DIRECTION_MIN_VALUE = 1500.0
DIRECTION_DEADBAND = 1000.0

GROUP_BY_KEY = {
    "contender": "contender",
    "fringe_contender": "contender",
    "retool": "retool",
    "rebuild": "rebuild",
    "tank": "rebuild",
}
GROUP_LABEL = {"contender": "contender", "retool": "retool", "rebuild": "rebuild"}

# Confidence of an auto classification from the team's league standing and the
# games behind it. Declared is certain by definition. Approximate.
_CLIENT_CONFIDENCE = 0.5


def _confidence_label(conf: float) -> str:
    return "high" if conf >= 0.75 else "medium" if conf >= 0.5 else "low"


def _record_text(record: Mapping[str, Any] | None) -> tuple[str, int]:
    if not isinstance(record, Mapping):
        return "", 0
    try:
        w, l, t = (int(record.get(k) or 0) for k in ("wins", "losses", "ties"))
    except (TypeError, ValueError):
        return "", 0
    games = w + l + t
    if games <= 0:
        return "", 0
    return (f"{w}-{l}" + (f"-{t}" if t else "")), games


def _ordinal_rank(rank: Any) -> int | None:
    try:
        value = int(float(rank))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def resolve_posture(
    *,
    declared_strategy: str = "",
    auto_strategy: str = "",
    client_strategy: str = "",
    power_rank: Any = None,
    league_size: Any = None,
    record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The ONE posture for the user's team.

    Order: declared Team Situation (the user said so) > auto classification
    (``team_eval``: roster strength + real record + age + draft capital) >
    whatever the client sent. ``client_strategy`` of "retool"/"auto"/"" is the
    old unset default and never overrides an auto classification.
    """

    declared = str(declared_strategy or "").strip().lower()
    auto = str(auto_strategy or "").strip().lower()
    client = str(client_strategy or "").strip().lower()
    record_text, games = _record_text(record)
    rank = _ordinal_rank(power_rank)
    try:
        size = int(float(league_size)) if league_size else 0
    except (TypeError, ValueError):
        size = 0

    if declared:
        key, source, conf = normalize_team_strategy(declared), "declared", 1.0
    elif auto:
        key, source = normalize_team_strategy(auto), "auto"
        # Conviction: how far from the middle of the league the team sits,
        # damped while few games back the record.
        if rank and size > 1:
            pct = (rank - 1) / (size - 1)
            spread = min(1.0, abs(pct - 0.5) / 0.35)
        else:
            spread = 0.3
        conf = (0.45 + 0.4 * spread) * (0.75 + 0.25 * min(1.0, games / 4.0))
        if key == "retool":
            conf = min(conf, 0.65)
    else:
        key = normalize_team_strategy(client or "retool")
        source, conf = "client", _CLIENT_CONFIDENCE
    conf = round(max(0.0, min(1.0, conf)), 2)

    label = team_strategy_label(key)
    standing = []
    if rank and size:
        standing.append(f"#{rank} of {size}")
    elif rank:
        standing.append(f"#{rank}")
    if record_text:
        standing.append(record_text)
    standing_text = ", ".join(standing)
    if source == "declared":
        why = "You set this in Team Situation" + (f" ({standing_text})" if standing_text else "")
    elif source == "auto":
        why = f"From your roster strength, record and age curve" + (f" ({standing_text})" if standing_text else "")
    else:
        why = "Default lens; set Team Situation to make this exact"
    return {
        "key": key,
        "group": GROUP_BY_KEY.get(key, "retool"),
        "label": label,
        "source": source,
        "confidence": conf,
        "confidence_label": _confidence_label(conf),
        "rank": rank,
        "league_size": size or None,
        "record": record_text,
        "standing": standing_text,
        "why": why,
    }


def posture_from_strategy(strategy: Any) -> dict[str, Any]:
    """Posture when only a strategy key is known (Trade Hub / counter search)."""

    return resolve_posture(client_strategy=str(strategy or ""))


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def assess(posture: Mapping[str, Any], lineup_model: Mapping[str, Any] | None) -> dict[str, Any]:
    """Competitive-window and direction terms for one trade, in score units.

    Inputs are only numbers the lineup model already computed:
    ``points.ros_delta`` (expected lineup points over the remaining weeks),
    ``points.ros_before`` (the margin those points are measured against),
    ``win_now_delta`` / ``future_delta`` (this-season vs future value, posture
    weighted). Returns ``adjustment`` (added to the lineup model's trade score)
    and the facts the card words.
    """

    key = normalize_team_strategy(str((posture or {}).get("key") or "retool"))
    out: dict[str, Any] = {
        "available": False,
        "posture": key,
        "window_term": 0,
        "direction_term": 0,
        "present_term": 0,
        "adjustment": 0,
        "wins_delta": 0.0,
        "lineup_points": 0.0,
        "lineup_share": 0.0,
        "lineup_costly": False,
        "direction": "neutral",
        "direction_misaligned": False,
        "conversion": 0,
    }
    if not lineup_model or not lineup_model.get("available", True):
        return out
    pts = lineup_model.get("points") or {}
    ros_delta = _num(pts.get("ros_delta"))
    ros_before = max(_num(pts.get("ros_before")), 1.0)
    wins_delta = ros_delta * WIN_PROB_PER_POINT
    win_weight = WINDOW_WIN_WEIGHT.get(key, WINDOW_WIN_WEIGHT["retool"])
    k = _num(lineup_model.get("value_per_point"))
    # Value units per expected win in THIS league's price scale.
    win_value = win_weight * (k or STATIC_VALUE_PER_POINT) / WIN_PROB_PER_POINT
    window_term = win_value * (wins_delta if wins_delta < 0 else GAIN_CREDIT * wins_delta)

    present_term = PRESENT_ADJUST.get(key, 0.0) * k * ros_delta

    present = _num(lineup_model.get("win_now_delta"))
    future = _num(lineup_model.get("future_delta"))
    # >0 converts future into present, <0 converts present into future.
    conversion = (present - future) / 2.0
    orientation = ORIENTATION.get(key, 0.0)
    misaligned = max(0.0, -orientation * conversion - DIRECTION_DEADBAND)
    direction_term = -DIRECTION_RATE * misaligned
    direction = "toward_present" if conversion > DIRECTION_MIN_VALUE else "toward_future" if conversion < -DIRECTION_MIN_VALUE else "neutral"

    share = max(0.0, -ros_delta) / ros_before
    costly = win_weight >= WINDOW_WIN_WEIGHT["fringe_contender"] and (
        wins_delta <= -MATERIAL_WINS or share >= MATERIAL_LINEUP_SHARE
    ) and ros_delta < 0
    out.update(
        available=True,
        window_term=round(window_term),
        direction_term=round(direction_term),
        present_term=round(present_term),
        adjustment=round(window_term) + round(direction_term) + round(present_term),
        wins_delta=round(wins_delta, 2),
        lineup_points=round(ros_delta, 1),
        lineup_share=round(share, 3),
        lineup_costly=bool(costly),
        direction=direction,
        direction_misaligned=bool(misaligned > 0 and direction != "neutral"),
        conversion=round(conversion),
        present_delta=round(present),
        future_delta=round(future),
    )
    return out


_PHRASE = {
    "contender": "a contender",
    "fringe_contender": "a fringe contender",
    "retool": "retooling",
    "rebuild": "rebuilding",
    "tank": "tanking",
}


def posture_sentence(posture: Mapping[str, Any], assessment: Mapping[str, Any], *, weeks_text: str = "") -> str:
    """One honest sentence naming the posture and the trade-off, or "" when the
    posture does not change the story."""

    if not assessment.get("available"):
        return ""
    group = posture.get("group")
    standing = posture.get("standing")
    who = "You're " + _PHRASE.get(str(posture.get("key")), "a contender") + (f" ({standing})" if standing else "")
    pts = abs(_num(assessment.get("lineup_points")))
    wins = abs(_num(assessment.get("wins_delta")))
    span = f" {weeks_text}" if weeks_text else ""
    if assessment.get("lineup_costly"):
        sentence = f"{who}: this costs ~{pts:.0f} lineup points{span}"
        if wins >= 0.1:
            sentence += f" (about {wins:.1f} fewer wins)"
        if assessment.get("direction") == "toward_future":
            sentence += " and trades your present for future value, a step toward a rebuild"
        return sentence + "."
    if assessment.get("direction_misaligned") and assessment.get("direction") == "toward_future" and group == "contender":
        return f"{who}: this moves value from your lineup to the future, a step toward a rebuild."
    if assessment.get("direction_misaligned") and assessment.get("direction") == "toward_present" and group == "rebuild":
        return f"{who}: this spends future value on win-now players, away from your rebuild."
    ros = _num(assessment.get("lineup_points"))
    if group == "rebuild" and ros <= -5:
        return f"{who}: the ~{abs(ros):.0f} lineup points it costs{span} matter little to your timeline."
    return ""


def window_overrules_value(
    value_delta: float, trade_score: float, assessment: Mapping[str, Any] | None
) -> bool:
    """True when the market value alone would say accept but the posture
    (window / direction / present) terms pulled the SAME score below an accept.

    A fact about two numbers the verdict already has, used for the words around
    it (the line under the verdict keeps saying what the market says, the
    heading becomes "The trade-off"). It decides nothing: band, UI verdict and
    tone are always the rung ``trade_score`` lands in.
    """

    from modules import trade_value_bands as bands

    if not assessment or _num(assessment.get("adjustment")) >= 0:
        return False
    return (
        bands.band_for_score(value_delta).id in {"smash", "accept"}
        and bands.band_for_score(trade_score).id not in {"smash", "accept"}
    )


def tradeoff_tag(posture: Mapping[str, Any] | None, assessment: Mapping[str, Any] | None) -> str:
    """Short descriptive tag for a card whose posture terms are material.

    Not a verdict: the tag sits next to the score's own rung and names the
    reason from facts ``assess`` computed. "" when nothing is material.
    """

    if not assessment or not assessment.get("available"):
        return ""
    group = (posture or {}).get("group")
    direction = assessment.get("direction")
    misaligned = bool(assessment.get("direction_misaligned"))
    if assessment.get("lineup_costly"):
        return "Costs your lineup"
    if group == "contender" and misaligned and direction == "toward_future":
        return "Moves you toward a rebuild"
    if group == "rebuild" and misaligned and direction == "toward_present":
        return "Against your rebuild"
    return ""


def adjusted_confidence(lineup_model: Mapping[str, Any], adjusted_score: float) -> tuple[float, str]:
    """P(sign of the adjusted score is right) using the model's own sigma."""

    unc = lineup_model.get("uncertainty") or {}
    sigma = _num(unc.get("sigma")) or 1.0
    p = min(_phi(abs(adjusted_score) / sigma), 0.99)
    label = "High confidence" if p >= 0.88 else "Moderate confidence" if p >= 0.70 else "Close call"
    return round(p * 100, 1), label


# --- Trade Hub / Finder / Dashboard: ideas graded and ranked by posture ---------
#
# Every generated idea is already graded by the Analyzer's own pipeline
# (``trade_ideas._UserSideAnalyzerGate`` -> ``trade_grade.grade_trade_for_user``),
# which is posture-aware since #1597 as soon as it is given the posture KEY. These
# helpers only (1) copy what that verdict already says onto the idea, (2) order
# ideas by how well they fit the posture, and (3) stamp the user's full resolved
# posture (declared/auto/client, standing) onto cached records outside the cache
# boundary. No new per-idea modelling.

# Lineup points an idea must ADD (expected over the remaining weeks) for a
# win-now team to call it "improves your lineup now".
IMPROVES_LINEUP_POINTS = 5.0
ALIGNED, NEUTRAL, COSTLY = "aligned", "neutral", "costly"
ALIGNMENT_RANK = {ALIGNED: 1, NEUTRAL: 0, COSTLY: -1}
IDEA_FIELDS = (
    "posture",
    "posture_note",
    "posture_label",
    "posture_alignment",
    "posture_lineup_points",
    "posture_wins_delta",
    "posture_assessment",
    "analyzer_weeks_text",
)


def alignment(posture: Mapping[str, Any] | None, assessment: Mapping[str, Any] | None) -> str:
    """How well one trade fits the team's posture, from ``assess`` numbers only.

    costly: a material lineup cost for a team that plays for wins, or a
    conversion in the direction the posture does not want. aligned: a win-now
    team gaining real lineup points, or a rebuilding team moving toward the
    future. Everything else is neutral (and ranks by the usual surface key).
    """

    if not assessment or not assessment.get("available"):
        return NEUTRAL
    group = str((posture or {}).get("group") or GROUP_BY_KEY.get(str((posture or {}).get("key") or "retool"), "retool"))
    pts = _num(assessment.get("lineup_points"))
    direction = assessment.get("direction")
    if assessment.get("lineup_costly") or (assessment.get("direction_misaligned") and group != "retool"):
        return COSTLY
    if group == "contender" and pts >= IMPROVES_LINEUP_POINTS and direction != "toward_future":
        return ALIGNED
    if group == "rebuild" and direction == "toward_future":
        return ALIGNED
    return NEUTRAL


def idea_fields_from_verdict(verdict: Any, *, weeks_text: str = "") -> dict[str, Any]:
    """The posture facts of an Analyzer ``OfferVerdict`` to carry on an idea."""

    posture = dict(getattr(verdict, "posture", None) or {})
    assessment = dict(getattr(verdict, "posture_assessment", None) or {})
    return {
        "posture": posture or None,
        "posture_assessment": assessment or None,
        "posture_note": str(getattr(verdict, "posture_note", "") or ""),
        "posture_label": tradeoff_tag(posture, assessment),
        "posture_alignment": alignment(posture, assessment),
        "posture_lineup_points": assessment.get("lineup_points"),
        "posture_wins_delta": assessment.get("wins_delta"),
        "analyzer_weeks_text": weeks_text,
    }


def sort_rank(idea: Mapping[str, Any]) -> tuple[int, int]:
    """Leading ranking key: (alignment, analyzer trade score band).

    Ideas without an Analyzer grade rank neutral, so old callers and ideas the
    Analyzer could not grade keep their existing order. The score is bucketed
    to 500 value units so the established surface key (readiness, tier,
    confidence, realism, fit) still decides between comparable ideas.
    """

    rank = ALIGNMENT_RANK.get(str(idea.get("posture_alignment") or NEUTRAL), 0)
    score = idea.get("analyzer_trade_score")
    bucket = 0
    if rank >= 0 and score is not None:
        try:
            bucket = int(max(-4, min(4, round(float(score) / 500.0)))) if rank > 0 else 0
        except (TypeError, ValueError):
            bucket = 0
    return rank, bucket


def public_posture(posture: Mapping[str, Any]) -> dict[str, Any]:
    keys = ("key", "group", "label", "source", "confidence", "confidence_label", "rank", "league_size", "record", "standing", "why")
    pub = {k: posture.get(k) for k in keys}
    if posture.get("degraded_reason"):
        # The posture is a default because its lookup failed (see
        # trade_hub_engine.roster_posture); clients show a "limited data" note.
        pub["degraded_reason"] = posture["degraded_reason"]
    return pub


def stamp_records(records: list[dict[str, Any]], posture: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Attach the user's resolved posture (and the standing-aware note) to
    cached idea records. Copies, so the shared cache entry is never mutated."""

    if not posture:
        return records
    pub = public_posture(posture)
    out: list[dict[str, Any]] = []
    for idea in records:
        if not isinstance(idea, dict):
            out.append(idea)
            continue
        new = dict(idea)
        new["posture"] = pub
        assessment = new.get("posture_assessment")
        if isinstance(assessment, Mapping):
            note = posture_sentence(pub, assessment, weeks_text=str(new.get("analyzer_weeks_text") or ""))
            new["posture_note"] = note
            new["posture_alignment"] = alignment(pub, assessment)
        out.append(new)
    return out


_YOUNG_CORE_MAX_AGE = 24
_ROUND_RE = re.compile(r"round\s*(\d)", re.IGNORECASE)


def _asset_score(asset: Mapping[str, Any]) -> float:
    return _num(asset.get("score", asset.get("value_score")))


def young_core_for_picks_caution(
    posture: Mapping[str, Any] | None,
    send_assets: Sequence[Mapping[str, Any]] | None,
    receive_assets: Sequence[Mapping[str, Any]] | None,
) -> str:
    """Words only (never moves the score): a rebuilding team sending its best
    young player out for picks that are all after round 1. A pile of 2nds can
    out-add one young starter on the value chart while rarely producing one."""

    key = normalize_team_strategy(str((posture or {}).get("key") or ""))
    if key not in {"rebuild", "tank"}:
        return ""
    sent = [a for a in send_assets or () if isinstance(a, Mapping)]
    got = [a for a in receive_assets or () if isinstance(a, Mapping)]
    young = [
        a
        for a in sent
        if a.get("asset_type") == "player"
        and _num(a.get("age")) and 0 < _num(a.get("age")) <= _YOUNG_CORE_MAX_AGE
    ]
    picks = [a for a in got if a.get("asset_type") == "pick"]
    if not young or not picks or not sent:
        return ""
    best_young = max(young, key=_asset_score)
    if _asset_score(best_young) < max(_asset_score(a) for a in sent):
        return ""
    rounds = []
    for pick in picks:
        numeric = int(_num(pick.get("round")))
        match = _ROUND_RE.search(str(pick.get("label") or pick.get("name") or ""))
        rounds.append(numeric or (int(match.group(1)) if match else 0))
    if not rounds or min(rounds) < 2:  # an unreadable label or any 1st: no caution
        return ""
    name = str(best_young.get("name") or best_young.get("label") or "A young starter")
    return (
        f"Rebuild caution: {name} (age {int(_num(best_young.get('age')))}) is a young core piece, and the picks coming "
        "back are all 2nd round or later, which rarely turn into starters. The value adds up on paper; "
        "the long-term fit may not."
    )
