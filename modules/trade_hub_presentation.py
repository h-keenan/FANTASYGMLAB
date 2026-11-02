import time
from typing import Callable, Mapping
import pandas as pd
from modules import canonical_recommendation_narrative
from modules import recommendation_trust_ux
from modules.player_state_authority import is_suspended

def _safe_text(value, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return str(value)


def trade_target_reason(
    idea: dict,
    *,
    recommendation_reason_text: Callable[[str, int], str],
) -> str:
    return recommendation_reason_text(
        _safe_text(
            idea.get("hub_target_fit_reason")
            or idea.get("fit_summary")
            or idea.get("reasoning_summary")
            or idea.get("rationale")
        ),
        130,
    )


def trade_partner_reason(
    idea: dict,
    *,
    recommendation_reason_text: Callable[[str, int], str],
) -> str:
    return recommendation_reason_text(
        _safe_text(
            idea.get("partner_evidence_reason")
            or idea.get("hub_partner_reason")
            or idea.get("hub_candidate_reason")
            or idea.get("partner_trade_implication")
            or idea.get("market_realism_summary")
        ),
        130,
    )


def trade_confidence_reason(
    idea: dict,
    *,
    recommendation_reason_text: Callable[[str, int], str],
    injury_display_context: Callable[[dict], dict],
) -> str:
    summary = recommendation_reason_text(
        _safe_text(idea.get("trade_confidence_summary")),
        130,
    )
    if summary:
        base_reason = summary
    else:
        confidence_label = _safe_text(
            idea.get("trade_confidence_label"),
            "Low",
        ).strip().lower()
        market_label = _safe_text(
            idea.get("market_realism_label"),
            "Thin",
        ).strip().lower()
        base_reason = recommendation_trust_ux.quieter_confidence_fallback(
            confidence_label=confidence_label,
            market_label=market_label,
        )
    health_context = injury_display_context(idea)
    if health_context["risk"]:
        return recommendation_reason_text(
            f"{base_reason} Health caveat: {health_context['note']}",
            260,
        )
    return base_reason


def trade_display_confidence_label(
    idea: dict,
    *,
    injury_display_context: Callable[[dict], dict],
) -> str:
    confidence = _safe_text(idea.get("trade_confidence_label"), "Low")
    if "confidence" not in confidence.casefold():
        confidence = f"{confidence} confidence"
    health_context = injury_display_context(idea)
    if health_context["risk"]:
        return f"{confidence} ({health_context['confidence_suffix']})"
    return confidence


def trade_asset_injury_context(
    asset: dict,
    *,
    injury_level: Callable,
) -> dict:
    if _safe_text(asset.get("asset_type"), "player") != "player":
        return {
            "level": "healthy",
            "risk": False,
            "uncertain": False,
            "label": "",
            "note": "",
        }

    level = injury_level(asset.get("status"), asset.get("injury_status"))
    reported_level = _safe_text(asset.get("injury_level")).strip().lower()
    if reported_level in {"major", "moderate", "minor"}:
        level = reported_level
    risk = level in {"major", "moderate"}
    uncertain = False
    if risk:
        news_updated = pd.to_numeric(pd.Series([asset.get("news_updated")]), errors="coerce").iloc[0]
        if pd.isna(news_updated):
            uncertain = True
        else:
            updated_at = float(news_updated)
            if updated_at > 10_000_000_000:
                updated_at /= 1000.0
            uncertain = updated_at <= 0 or time.time() - updated_at > 60 * 24 * 60 * 60

    if level == "major" and is_suspended(asset.get("status"), asset.get("injury_status")):
        label = "Suspended"
        note = "Suspended for a known length of time, not injured; treat as fully unavailable dynasty value until the suspension ends."
    elif level == "major":
        label = "Major Injury Risk"
        note = "Long-term or reserve-level injury signal; treat this as an injury-discount dynasty target, not clean current production."
    elif level == "moderate":
        label = "Current Health Risk"
        note = "Out/doubtful-level availability risk qualifies the current opportunity and trade confidence."
    elif level == "minor":
        label = "Injury Watch"
        note = "Minor availability concern."
    else:
        label = ""
        note = ""
    if uncertain and risk:
        label = f"{label} - Status Uncertain"
        note += " The supporting injury update is missing or stale, so the timeline should be verified."
    try:
        from modules import signal_freshness

        sync = signal_freshness.status_sync_freshness()
        sync_label = str(sync.get("label") or "").strip()
    except Exception:
        sync_label = ""
    if sync_label and "happened" not in sync_label.casefold() and (risk or label):
        note = f"{note} · {sync_label}".strip(" ·")
    return {
        "level": level,
        "risk": risk,
        "uncertain": uncertain,
        "label": label,
        "note": note,
    }


def trade_idea_injury_display_context(
    idea: dict,
    *,
    asset_injury_context: Callable[[dict], dict],
) -> dict:
    incoming = [
        asset_injury_context(asset)
        for asset in (idea.get("receive_assets") or [])
        if _safe_text(asset.get("asset_type"), "player") == "player"
    ]
    risky = [context for context in incoming if context.get("risk")]
    if not risky:
        return {"risk": False, "label": "", "note": "", "confidence_suffix": ""}
    has_major = any(context.get("level") == "major" for context in risky)
    uncertain = any(context.get("uncertain") for context in risky)
    label = "Injury-Discount Target" if has_major else "Health-Risk Target"
    if uncertain:
        label += " - Status Uncertain"
    note = (
        "The incoming package includes a major/long-term injury signal. Dynasty upside may remain, "
        "but the displayed confidence is conditional on recovery and updated health information."
        if has_major
        else "The incoming package includes an out/doubtful-level health signal, so current opportunity and confidence are conditional."
    )
    if uncertain:
        note += " The latest supporting injury update is missing or stale."
    return {
        "risk": True,
        "label": label,
        "note": note,
        "confidence_suffix": "Major Health Risk" if has_major else "Health Risk",
    }


FREE_VISIBLE_IDEAS = 2


FEATURED_DIVERSITY_SLOTS = 2


def explicit_acquisition_structure_label(idea: dict) -> str:
    path = _safe_text(idea.get("hub_path"), _safe_text(idea.get("tag"), "Acquisition path"))
    lowered = path.casefold()
    prefix = "harder to execute"
    if lowered.startswith(prefix):
        remainder = path[len(prefix) :].lstrip(" ·-–—")
        path = remainder or path
    return path or "Acquisition path"


def is_explicit_player_search_idea(idea: Mapping | None) -> bool:
    if not isinstance(idea, Mapping):
        return False
    mode = _safe_text(idea.get("hub_mode")).casefold()
    if mode in {"target_player", "my_player"}:
        return True
    if _safe_text(idea.get("hub_search_source")):
        return True
    if _safe_text(idea.get("hub_path")):
        return True
    return False


def _explicit_search_injury_relief_allowed(idea: dict) -> bool:
    if not idea.get("injury_motivated"):
        return False
    tags = [_safe_text(tag) for tag in (idea.get("reasoning_tags") or [])]
    return "Health Relief" in tags


def trade_hub_display_section(idea: dict) -> str:
    """Classify an existing recommendation for display without changing its score or order."""
    if is_explicit_player_search_idea(idea):
        if _explicit_search_injury_relief_allowed(idea):
            return "Health Relief"
        return explicit_acquisition_structure_label(idea)
    searchable = " ".join(
        _safe_text(idea.get(field))
        for field in (
            "tag",
            "hub_path",
            "reasoning_summary",
            "fit_summary",
            "strategy_fit_reason",
            "my_strategy",
            "strategy_archetype",
        )
    ).casefold()
    reason_tags = " ".join(
        _safe_text(tag) for tag in (idea.get("reasoning_tags") or [])
    ).casefold()
    searchable = f"{searchable} {reason_tags}"
    health_hit = any(token in searchable for token in ("injury", "health", "ir ", "relief"))
    if health_hit:
        return "Health Relief"
    if any(token in searchable for token in ("draft capital", "future pick", "pick value", "rookie pick")):
        return "Draft Capital"
    if any(token in searchable for token in ("age ", "younger", "youth", "veteran", "age curve")):
        return "Age Optimization"
    if any(token in searchable for token in ("rebuild", "tank", "long-term")):
        return "Rebuild"
    if any(token in searchable for token in ("contender", "win-now", "win now", "title push")):
        return "Contender"
    if any(token in searchable for token in ("need", "roster fit", "thin position", "position fit")):
        return "Need-Based"
    if _safe_text(idea.get("trade_confidence_label")).strip().casefold() == "high":
        return "High Confidence"
    return "Need-Based"


def _trade_confidence_rank(idea: dict) -> int:
    return {
        "Low": 0,
        "Medium": 1,
        "High": 2,
    }.get(str(idea.get("trade_confidence_label") or "Low").strip(), 0)


def _partner_diversity_key(idea: dict) -> str:
    return str(idea.get("partner_roster_id") or idea.get("partner_team_name") or "").strip().casefold()


def _outgoing_centerpiece_key(idea: dict) -> str:
    for asset in idea.get("send_assets") or []:
        if str(asset.get("asset_type") or "player").strip().casefold() == "pick":
            continue
        player_id = str(asset.get("player_id") or "").strip()
        if player_id:
            return f"player:{player_id}"
    for asset in idea.get("send_assets") or []:
        token = str(
            asset.get("player_id")
            or asset.get("pick_id")
            or asset.get("name")
            or asset.get("label")
            or ""
        ).strip()
        if token:
            return f"asset:{token.casefold()}"
    return ""


def apply_trade_hub_featured_diversity(
    ideas: list[dict],
    *,
    featured_slots: int = FEATURED_DIVERSITY_SLOTS,
) -> list[dict]:
    """Move duplicate outgoing players or partners below the featured window.

    Never drops ideas. Never promotes a weaker-confidence alternative over a
    stronger duplicate. Deterministic given the incoming ranked list.
    """

    ranked = list(ideas or [])
    slots = max(1, int(featured_slots or 1))
    if len(ranked) <= 1:
        return ranked
    selected: list[dict] = []
    deferred: list[dict] = []
    index = 0
    while index < len(ranked) and len(selected) < slots:
        idea = ranked[index]
        rest = ranked[index + 1 :]
        used_centerpieces = {
            _outgoing_centerpiece_key(item)
            for item in selected
            if _outgoing_centerpiece_key(item)
        }
        used_partners = {
            _partner_diversity_key(item)
            for item in selected
            if _partner_diversity_key(item)
        }
        center = _outgoing_centerpiece_key(idea)
        partner = _partner_diversity_key(idea)
        duplicate_centerpiece = bool(center and center in used_centerpieces)
        duplicate_partner = bool(partner and partner in used_partners)
        if duplicate_centerpiece or duplicate_partner:
            alternative = next(
                (
                    candidate
                    for candidate in rest
                    if (
                        not duplicate_centerpiece
                        or (
                            _outgoing_centerpiece_key(candidate)
                            and _outgoing_centerpiece_key(candidate) not in used_centerpieces
                        )
                    )
                    and (
                        not duplicate_partner
                        or (
                            _partner_diversity_key(candidate)
                            and _partner_diversity_key(candidate) not in used_partners
                        )
                    )
                ),
                None,
            )
            idea_rank = _trade_confidence_rank(idea)
            alt_rank = _trade_confidence_rank(alternative) if alternative is not None else -1
            if alternative is not None and alt_rank >= idea_rank:
                deferred.append(idea)
                index += 1
                continue
        selected.append(idea)
        index += 1
    leftover = list(ranked[index:])
    fill_from = leftover + deferred
    filled_tail: list[dict] = []
    for idea in fill_from:
        if len(selected) < slots:
            selected.append(idea)
        else:
            filled_tail.append(idea)
    return selected + filled_tail


def order_trade_hub_visible_ideas(ideas: list[dict]) -> list[dict]:
    """Defensive presentation sort: highest executive usefulness first.

    Primary key remains `_trade_surface_sort_key` (headline readiness, tier,
    confidence, market/fit/strategy, priority). Categories never participate.

    `trade_gain` is only a last-resort presentation tie-break when surface keys
    are identical — it does not override Trust, tier, or confidence. Membership,
    scores, and football logic are unchanged.

    Featured-window diversity then prefers a different outgoing centerpiece
    and partner when an equal-or-better alternative exists.
    """

    from modules.trade_ideas import _trade_surface_sort_key

    from modules import trade_posture

    def _presentation_key(idea: dict) -> tuple:
        # Team posture first (modules.trade_posture.sort_rank): ideas that fit
        # the team's status lead, ideas that cost it trail. Ungraded ideas are
        # neutral, so the established surface key decides as before.
        return (
            *trade_posture.sort_rank(idea),
            *_trade_surface_sort_key(idea),
            int(idea.get("trade_gain") or 0),
        )

    ranked = sorted(list(ideas or []), key=_presentation_key, reverse=True)
    return apply_trade_hub_featured_diversity(
        ranked,
        featured_slots=FEATURED_DIVERSITY_SLOTS,
    )


def idea_recommendation_id(idea: Mapping | None) -> str:
    """Canonical trade identity, independent of display headline."""

    if not isinstance(idea, Mapping):
        return ""
    direct = _safe_text(idea.get("recommendation_id"))
    if direct:
        return direct
    return canonical_recommendation_narrative.trade_recommendation_id(idea)
