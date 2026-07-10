from typing import Any, Mapping

from modules.rankings import injury_level


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _opportunity_confidence_label(value: Any) -> str:
    score = _safe_int(value, 0)
    if score >= 80:
        return "High"
    if score >= 55:
        return "Medium"
    if score > 0:
        return "Low"
    return "Unknown"


def _score_tier(score: int) -> str:
    if score >= 8000:
        return "elite cornerstone asset"
    if score >= 6000:
        return "strong every-week starter"
    if score >= 4000:
        return "solid starter or strong flex"
    if score >= 2200:
        return "depth piece with usable value"
    return "bench-level or speculative hold"


def explain_player_decision(
    player_name: str,
    age: int,
    value: int,
    league_format: str,
    context: str = "",
    *,
    player: Mapping[str, Any] | None = None,
    score_field: str = "dynasty_score",
    score_label: str = "Dynasty Score",
    strategy_label: str = "",
) -> str:
    """
    Lightweight, local explanation for a player's outlook using the same
    canonical player dataset and valuation pipeline the rest of the app uses.
    """
    row = dict(player or {})

    name = _safe_text(row.get("name"), _safe_text(player_name, "Player"))
    position = _safe_text(row.get("position")).upper()
    team = _safe_text(row.get("team"))
    age_value = _safe_float(row.get("age"), _safe_float(age, 0))
    selected_score = _safe_int(row.get(score_field), _safe_int(value, 0))
    dynasty_score = _safe_int(row.get("dynasty_score"), selected_score)
    rebuild_score = _safe_int(row.get("rebuild_score"), selected_score)
    redraft_score = _safe_int(row.get("value_score"), selected_score)
    market_score = _safe_int(row.get("market_score"), 0)
    scarcity_score = _safe_int(row.get("scarcity_score"), 0)
    role_score = _safe_int(row.get("role_score"), 0)
    opportunity_score = _safe_int(row.get("opportunity_score"), 0)
    opportunity_label = _safe_text(row.get("opportunity_label"))
    opportunity_confidence = _safe_int(row.get("opportunity_confidence"), 0)
    opportunity_source_flags = [
        part.replace("_", " ")
        for part in _safe_text(row.get("opportunity_source_flags")).split("|")
        if part.strip()
    ]
    opportunity_explanation = _safe_text(row.get("opportunity_explanation"))
    projected_starter = bool(row.get("projected_starter"))
    workload_trend = _safe_text(row.get("workload_trend"))
    age_curve_score = _safe_int(row.get("age_curve_score"), 0)
    valuation_blend = _safe_text(row.get("valuation_blend"))
    injury_key = injury_level(row.get("status"), row.get("injury_status"))

    parts = [f"{name} - Player Snapshot"]

    header_bits = []
    if position:
        header_bits.append(position)
    if team:
        header_bits.append(team)
    if age_value > 0:
        header_bits.append(f"{age_value:.0f} years old")
    if league_format:
        header_bits.append(league_format)
    if header_bits:
        parts.append(" | ".join(header_bits))

    score_bits = [f"{score_label}: {selected_score}"]
    if dynasty_score and score_field != "dynasty_score":
        score_bits.append(f"Dynasty: {dynasty_score}")
    if rebuild_score and score_field != "rebuild_score":
        score_bits.append(f"Rebuild: {rebuild_score}")
    if redraft_score and score_field != "value_score":
        score_bits.append(f"Current: {redraft_score}")
    if score_bits:
        parts.append(" | ".join(score_bits))

    if strategy_label:
        parts.append(f"Strategy lens: {strategy_label}")

    if context:
        parts.append("")
        parts.append(context)

    profile_bits = [_score_tier(selected_score)]
    if age_value and age_value <= 24:
        profile_bits.append("with a strong age runway")
    elif age_value and age_value >= 29:
        profile_bits.append("with an older age curve")

    if injury_key == "major":
        profile_bits.append("while carrying major injury discount")
    elif injury_key == "moderate":
        profile_bits.append("with meaningful short-term injury risk")
    elif injury_key == "minor":
        profile_bits.append("with minor injury risk")

    parts.append("")
    parts.append(f"In the current model, {name} profiles as a {', '.join(profile_bits)}.")

    valuation_parts = []
    if market_score:
        valuation_parts.append(f"market score {market_score}")
    if age_curve_score:
        valuation_parts.append(f"age-adjusted score {age_curve_score}")
    if scarcity_score:
        valuation_parts.append(f"scarcity score {scarcity_score}")
    if role_score:
        valuation_parts.append(f"role score {role_score}")
    if valuation_parts:
        parts.append("The underlying valuation stack is driven by " + ", ".join(valuation_parts) + ".")

    if opportunity_score or opportunity_label:
        parts.append(
            "Opportunity: "
            + (f"{opportunity_label}" if opportunity_label else "Workload profile")
            + (f" ({opportunity_score})" if opportunity_score else "")
            + "."
        )
    if opportunity_confidence:
        parts.append(
            f"Opportunity confidence: {_opportunity_confidence_label(opportunity_confidence)} ({opportunity_confidence})."
        )
    if projected_starter:
        parts.append("Projected starter: Yes.")
    if workload_trend and workload_trend != "Unknown":
        parts.append(f"Workload trend: {workload_trend}.")
    if opportunity_explanation:
        parts.append(opportunity_explanation)
    if opportunity_source_flags:
        parts.append("Opportunity inputs: " + ", ".join(opportunity_source_flags) + ".")

    if valuation_blend:
        parts.append(f"Pipeline: {valuation_blend}.")

    return "\n".join(parts)
