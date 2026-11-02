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

Everything here is a consequence of two small tables (``WINDOW_WIN_VALUE`` and
``ORIENTATION``) plus a win-probability slope. There is no per-position or
per-player rule, and no hard cap on a verdict: the score moves, and the label
simply reports when the score and the market value disagree.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from modules.team_eval import normalize_team_strategy, team_strategy_label

# --- parameters (all approximate; see docs/trade-engine-v2.md) ----------------

# Value units one EXPECTED REGULAR-SEASON WIN is worth to a team in each
# posture: what a contender pays to keep its playoff odds (seed, bye, title
# window), what a rebuilder does not care about. Same scale as the trade score
# (value units; the lineup model's k converts points to these).
WINDOW_WIN_VALUE: dict[str, float] = {
    "contender": 700.0,
    "fringe_contender": 450.0,
    "retool": 200.0,
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
    win_value = WINDOW_WIN_VALUE.get(key, WINDOW_WIN_VALUE["retool"])
    window_term = win_value * (wins_delta if wins_delta < 0 else GAIN_CREDIT * wins_delta)

    k = _num(lineup_model.get("value_per_point"))
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
    costly = win_value >= WINDOW_WIN_VALUE["fringe_contender"] and (
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


def verdict_label_override(
    *, value_band_id: str, final_band_id: str, posture: Mapping[str, Any], assessment: Mapping[str, Any]
) -> str:
    """Honest verdict label when the market value says accept but the posture
    cost pulled the score below an accept. "" when no override applies."""

    from modules import trade_value_bands as bands

    if value_band_id not in {"smash", "accept"} or final_band_id in {"smash", "accept"}:
        return ""
    if assessment.get("adjustment", 0) >= 0:
        return ""
    group = posture.get("group")
    if group == "contender" and assessment.get("lineup_costly"):
        return bands.VERDICT_VALUE_COSTS_LINEUP
    if group == "contender" and assessment.get("direction") == "toward_future":
        return bands.VERDICT_VALUE_MOVES_REBUILD
    if group == "rebuild" and assessment.get("direction") == "toward_present":
        return bands.VERDICT_VALUE_AGAINST_REBUILD
    if assessment.get("lineup_costly"):
        return bands.VERDICT_VALUE_COSTS_LINEUP
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

    from modules import trade_value_bands as bands

    posture = dict(getattr(verdict, "posture", None) or {})
    assessment = dict(getattr(verdict, "posture_assessment", None) or {})
    band = str(getattr(verdict, "band", "") or "")
    return {
        "posture": posture or None,
        "posture_assessment": assessment or None,
        "posture_note": str(getattr(verdict, "posture_note", "") or ""),
        "posture_label": band if band in bands.POSTURE_VERDICTS else "",
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
    return {k: posture.get(k) for k in keys}


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
