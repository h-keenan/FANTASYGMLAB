def _number(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _resolved_context(context):
    if context is None:
        return {}
    try:
        resolved = dict(context)
    except Exception:
        resolved = context
    nested = resolved.get("injury_role_context") if hasattr(resolved, "get") else None
    if isinstance(nested, dict):
        resolved.update(nested)
    return resolved


def resolve_team_injury_context(context):
    return _resolved_context(context)


def injury_data_is_uncertain(context) -> bool:
    context = _resolved_context(context)
    quality = str(context.get("injury_data_quality") or "available").strip().lower()
    return quality in {"missing", "uncertain", "stale", "unavailable"}


def has_meaningful_team_injury_impact(context) -> bool:
    context = _resolved_context(context)
    impact_score = _number(
        context.get("injury_impact_score", context.get("injury_value_impact")),
    )
    active_impact = _number(
        context.get("active_injury_impact_score", impact_score),
    )
    future_impact = _number(context.get("future_injury_impact_score"))
    major_starters = _integer(
        context.get("major_active_injured_starters", context.get("major_injured_starters"))
    )
    injured_starters = _integer(
        context.get("active_injured_starters", context.get("injured_starters"))
    )
    return (
        major_starters >= 1
        or active_impact >= 35.0
        or future_impact >= 35.0
        or (injured_starters >= 1 and active_impact >= 18.0)
    )


def is_acute_injury_pressure(context) -> bool:
    context = _resolved_context(context)
    active_impact = _number(
        context.get(
            "active_injury_impact_score",
            context.get("injury_impact_score", context.get("injury_value_impact")),
        ),
    )
    major_starters = _integer(
        context.get("major_active_injured_starters", context.get("major_injured_starters"))
    )
    injured_starters = _integer(
        context.get("active_injured_starters", context.get("injured_starters"))
    )
    return (
        major_starters >= 1
        or active_impact >= 70.0
        or (injured_starters >= 2 and active_impact >= 35.0)
    )


def team_injury_display_label(context, *, include_uncertainty: bool = False) -> str:
    context = _resolved_context(context)
    if has_meaningful_team_injury_impact(context):
        label = str(context.get("injury_impact_flag") or "").strip()
        if not label or label in {
            "Stable",
            "Injury Data Unavailable",
            "Health Status Uncertain",
            "Health Watch",
        }:
            active_impact = _number(
                context.get("active_injury_impact_score", context.get("injury_impact_score"))
            )
            future_impact = _number(context.get("future_injury_impact_score"))
            injured_starters = _integer(
                context.get("active_injured_starters", context.get("injured_starters"))
            )
            if injured_starters >= 1 or active_impact >= 35.0:
                label = "Starter Availability Concern"
            elif future_impact >= 35.0:
                label = "Future Asset Health Watch"
            else:
                label = "Health Watch"
        if injury_data_is_uncertain(context) and "uncertain" not in label.lower():
            return f"{label} (Status Uncertain)"
        return label
    if include_uncertainty and injury_data_is_uncertain(context):
        return "Injury Data Uncertain"
    return ""


def team_injury_display_note(context) -> str:
    context = _resolved_context(context)
    if injury_data_is_uncertain(context):
        uncertainty_note = str(context.get("injury_data_note") or "").strip()
    else:
        uncertainty_note = ""
    impact_summary = str(
        context.get("actionable_injury_summary")
        or context.get("top_injury_impact_summary")
        or ""
    ).strip()
    if impact_summary and uncertainty_note:
        return f"{impact_summary} {uncertainty_note}"
    return impact_summary or uncertainty_note


def team_injury_focus(context) -> str:
    context = _resolved_context(context)
    active_starters = _integer(
        context.get("active_injured_starters", context.get("injured_starters"))
    )
    active_impact = _number(
        context.get("active_injury_impact_score", context.get("injury_impact_score"))
    )
    future_count = _integer(context.get("future_asset_injury_count"))
    future_impact = _number(context.get("future_injury_impact_score"))
    if active_starters > 0 or active_impact >= 18.0:
        return "active"
    if future_count > 0 or future_impact >= 18.0:
        return "future"
    if injury_data_is_uncertain(context):
        return "uncertain"
    return "stable"


def team_injury_advice(context) -> dict:
    context = _resolved_context(context)
    focus = team_injury_focus(context)
    label = team_injury_display_label(context, include_uncertainty=True) or "Stable"
    active_positions = list(context.get("active_injury_positions") or [])
    future_positions = list(context.get("future_injury_positions") or [])
    covered_future = set(context.get("covered_future_injury_positions") or [])
    actionable = str(context.get("actionable_injury_summary") or "").strip()

    if focus == "future":
        positions = " / ".join(future_positions[:2]) or "young assets"
        covered = bool(covered_future.intersection(future_positions))
        body = (
            f"Monitor the developmental/core-future asset at {positions}. "
            + (
                "The active room currently has playable cover, so this is not a weekly starter crisis."
                if covered
                else "This is primarily a future-value health watch, not proof that the active room is broken."
            )
        )
        return {
            "focus": focus,
            "label": label,
            "title": "Future asset health watch",
            "body": body,
            "summary": actionable,
        }
    if focus == "active":
        positions = " / ".join(active_positions[:2]) or "the weekly lineup"
        return {
            "focus": focus,
            "label": label,
            "title": "Monitor starter availability",
            "body": f"{label} is affecting {positions}. Keep viable weekly cover available while the status is unresolved.",
            "summary": actionable,
        }
    if focus == "uncertain":
        return {
            "focus": focus,
            "label": label,
            "title": "Health status needs confirmation",
            "body": str(context.get("injury_data_note") or "Current injury data is incomplete or stale."),
            "summary": actionable,
        }
    return {
        "focus": "stable",
        "label": "Stable",
        "title": "",
        "body": "No current high-value injury concern.",
        "summary": "",
    }


def my_team_injury_alert(context) -> dict:
    context = _resolved_context(context)
    starter_count = _integer(
        context.get(
            "lineup_injured_starters",
            context.get("injured_starters"),
        )
    )
    weekly_count = _integer(context.get("active_injured_starters"))
    future_count = _integer(context.get("future_asset_injury_count"))
    injured_depth = _integer(context.get("injured_bench_players"))
    advice = team_injury_advice(context)
    actionable = list(context.get("actionable_injury_players") or [])

    role_summaries = []
    for item in actionable[:3]:
        name = str(item.get("name") or "").strip()
        position = str(item.get("position") or "").strip().upper()
        relevance = str(item.get("roster_relevance") or "depth").strip()
        if not name:
            continue
        role_summaries.append(
            f"{name} ({position or 'Player'}) - {relevance}"
        )
    role_note = " | ".join(role_summaries)

    if starter_count > 0:
        value = (
            f"{starter_count} injured starter"
            + ("s" if starter_count != 1 else "")
        )
    elif weekly_count > 0:
        value = (
            f"{weekly_count} weekly contributor"
            + ("s" if weekly_count != 1 else "")
            + " on injury watch"
        )
    elif future_count > 0:
        value = "Future asset injury watch"
    elif injured_depth > 0 and has_meaningful_team_injury_impact(context):
        value = "Depth injury watch"
    else:
        value = team_injury_display_label(
            context,
            include_uncertainty=True,
        ) or "Stable"

    note = role_note or str(advice.get("body") or "").strip()
    if not note:
        note = team_injury_display_note(context)
    if not note:
        note = "No acute injury pressure is standing out on the current roster."
    try:
        from modules import signal_freshness

        sync = signal_freshness.status_sync_freshness()
        sync_label = str(sync.get("label") or "").strip()
    except Exception:
        sync_label = ""
    if sync_label and "happened" not in sync_label.casefold():
        note = f"{note} · {sync_label}"
    return {
        "value": value,
        "note": note,
        "starter_count": starter_count,
        "weekly_count": weekly_count,
        "future_count": future_count,
        "focus": advice.get("focus", "stable"),
    }
