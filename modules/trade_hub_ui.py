import textwrap
import time
from hashlib import sha256
from html import escape
from typing import Callable, MutableMapping

import pandas as pd
import streamlit as st

from modules import performance
from modules import premium
from modules import ui_primitives
from modules.html_rendering import render_html_fragment

from modules.player_cards import (
    injury_adjusted_value_html,
    player_position_badge_html,
    player_team_age_meta,
)


TRADE_STRATEGY_OPTIONS = (
    "Auto / Best guess",
    "Contender / Win-now",
    "Rebuild / Tank",
    "Retool",
    "Balanced",
    "Young powerhouse / Consolidate",
    "Aging contender",
)

TRADE_STRATEGY_PRESETS = {
    "Contender / Win-now": {
        "strategy": "contender",
        "archetype": "Win-Now",
    },
    "Rebuild / Tank": {
        "strategy": "rebuild",
        "archetype": "Full Rebuild",
    },
    "Retool": {
        "strategy": "retool",
        "archetype": "Retool Candidate",
    },
    "Balanced": {
        "strategy": "fringe_contender",
        "archetype": "Balanced Contender",
    },
    "Young powerhouse / Consolidate": {
        "strategy": "fringe_contender",
        "archetype": "Young Competitive Team",
    },
    "Aging contender": {
        "strategy": "contender",
        "archetype": "Aging Contender",
    },
}


def _safe_text(value, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return str(value)


def resolve_trade_strategy_selection(
    selection: str,
    *,
    automatic_strategy: str,
    automatic_archetype: str = "",
) -> dict:
    selected_label = (
        selection
        if selection in TRADE_STRATEGY_OPTIONS
        else "Auto / Best guess"
    )
    if selected_label == "Auto / Best guess":
        return {
            "selection": selected_label,
            "strategy": _safe_text(automatic_strategy, "retool"),
            "archetype": _safe_text(automatic_archetype),
            "manual": False,
        }
    preset = TRADE_STRATEGY_PRESETS[selected_label]
    return {
        "selection": selected_label,
        "strategy": preset["strategy"],
        "archetype": preset["archetype"],
        "manual": True,
    }


def render_trade_strategy_selector(
    *,
    automatic_strategy: str,
    automatic_strategy_label: str,
    automatic_archetype: str = "",
    key: str,
) -> dict:
    selected_label = st.selectbox(
        "Trade Strategy / Team Lens",
        TRADE_STRATEGY_OPTIONS,
        key=key,
        help="Auto uses the evaluated team direction. Manual lenses re-rank otherwise valid trade ideas without bypassing value or market-realism checks.",
    )
    resolved = resolve_trade_strategy_selection(
        selected_label,
        automatic_strategy=automatic_strategy,
        automatic_archetype=automatic_archetype,
    )
    automatic_context = automatic_strategy_label
    if automatic_archetype:
        automatic_context += f" | {automatic_archetype}"
    active_context = resolved["selection"] if resolved["manual"] else automatic_context
    st.caption(
        f"Automatic lens: {automatic_context}. Active Trade Hub lens: {active_context}."
    )
    return resolved


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
        if confidence_label == "high":
            base_reason = (
                "Fit and partner motivation both cleared the stronger confidence bar, "
                f"with {market_label} market realism."
            )
        elif confidence_label == "medium":
            base_reason = (
                f"Core fit is there, but this path still depends on {market_label} market conditions."
            )
        else:
            base_reason = (
                "This path is more speculative because either fit or partner motivation "
                "is still thin under the current market read."
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
    health_context = injury_display_context(idea)
    if health_context["risk"]:
        return f"{confidence} ({health_context['confidence_suffix']})"
    return confidence


def normalize_trade_html(html: str) -> str:
    """Normalize generated trade markup so nested HTML cannot become Markdown code."""
    dedented = textwrap.dedent(_safe_text(html)).strip()
    return "\n".join(
        line.strip()
        for line in dedented.splitlines()
        if line.strip()
    )


def render_trade_html(html: str) -> None:
    render_html_fragment(normalize_trade_html(html))


def render_trade_html_with_player_taps(
    html: str,
    assets: list[dict],
    *,
    key_prefix: str,
    source_label: str,
    render_tappable_player_html: Callable | None = None,
    open_player_quick_view: Callable | None = None,
) -> None:
    player_meta = {
        _safe_text(asset.get("player_id")).strip(): {
            "name": _safe_text(asset.get("name"), _safe_text(asset.get("label"), "Player")),
            "status": _safe_text(asset.get("role") or asset.get("player_tier")),
        }
        for asset in assets
        if _safe_text(asset.get("asset_type"), "player") == "player"
        and _safe_text(asset.get("player_id")).strip()
    }
    normalized_html = normalize_trade_html(html)
    if (
        not player_meta
        or render_tappable_player_html is None
        or open_player_quick_view is None
    ):
        render_trade_html(normalized_html)
        return

    clicked_player_id = render_tappable_player_html(
        html=normalized_html,
        key_prefix=key_prefix,
    )
    if clicked_player_id in player_meta:
        meta = player_meta[clicked_player_id]
        open_player_quick_view(
            clicked_player_id,
            source_label=source_label,
            source_note=f"Inspect {meta['name']} from this trade package.",
            status_label=meta["status"],
        )


def trade_assets_html(
    assets: list[dict],
    *,
    asset_html_builder: Callable[[dict], str],
) -> str:
    if not assets:
        return (
            "<div class='trade-asset-row'>"
            "<div class='trade-asset-copy'>No assets</div>"
            "</div>"
        )
    return (
        "<div class='trade-assets'>"
        + "".join(asset_html_builder(asset) for asset in assets)
        + "</div>"
    )


def asset_bundle_summary(assets: list[dict], max_assets: int = 2) -> str:
    if not assets:
        return "No return package"
    labels = []
    for asset in assets[:max_assets]:
        label = _safe_text(
            asset.get("label"),
            _safe_text(asset.get("name"), "Asset"),
        )
        if label:
            labels.append(label)
    extra = max(0, len(assets) - len(labels))
    if extra:
        labels.append(f"+{extra} more")
    return " + ".join(labels) if labels else "No return package"


def _asset_initials(label: str) -> str:
    parts = [part for part in label.replace("+", " ").split() if part]
    return "".join(part[0] for part in parts[:2]).upper() or "?"


asset_initials = _asset_initials


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

    if level == "major":
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


def trade_asset_html(
    asset: dict,
    *,
    injury_marker: str,
    is_injury_status: Callable,
    format_score: Callable,
    resolve_player_status: Callable,
    asset_injury_context: Callable,
    cached_headshot_data_url: Callable,
    avatar_html: Callable,
    format_age: Callable,
    canonical_player_status: Callable,
    tier_chip_html: Callable,
    player_support_chip_html: Callable,
    player_status_pill_html: Callable,
) -> str:
    asset_type = _safe_text(asset.get("asset_type"), "player")
    label = _safe_text(asset.get("label"), _safe_text(asset.get("name"), "Asset"))
    display_label = label
    score = format_score(asset.get("score", 0))
    chip_row = ""
    row_class = "trade-asset-row"
    status_row = ""
    health_note_html = ""
    player_id = ""

    if asset_type == "pick":
        row_class += " trade-asset-row-pick"
        avatar = "<div class='trade-avatar trade-avatar-pick'>PICK</div>"
        owner_team = _safe_text(asset.get("owner_team_name")).strip()
        original_team = _safe_text(asset.get("original_team_name")).strip()
        meta_parts = [owner_team if owner_team else "Draft pick"]
        if original_team and original_team != owner_team:
            meta_parts.append(f"Original {original_team}")
        season = _safe_text(asset.get("season")).strip()
        round_num = _safe_text(asset.get("round")).strip()
        if season and round_num:
            meta_parts.append(f"{season} R{round_num}")
        meta_parts.append(f"Score {score}")
    else:
        status_style = resolve_player_status(asset)
        health_context = asset_injury_context(asset)
        player_id = _safe_text(asset.get("player_id"))
        if player_id:
            row_class += " player-card-tappable"
        image_url = cached_headshot_data_url(player_id) if player_id else ""
        avatar = avatar_html(
            image_url,
            asset_initials(label),
            css_class=f"trade-avatar avatar-tone-{status_style['tone']}",
        )

        position = _safe_text(asset.get("position")).strip().upper()
        team = _safe_text(asset.get("team")).strip().upper() or "FA"
        meta_parts = [player_team_age_meta(team, format_age(asset.get("age")))]
        owner_team = _safe_text(asset.get("owner_team_name")).strip()
        if owner_team:
            meta_parts.append(f"Roster {owner_team}")
        position_badge = player_position_badge_html(position, css_class="player-position-badge trade-asset-position-badge")
        player_tier = _safe_text(asset.get("player_tier")).strip()
        chips = []
        if player_tier and canonical_player_status(player_tier).lower() != status_style["label"].lower():
            chips.append(tier_chip_html(player_tier))
        opportunity_label = _safe_text(asset.get("opportunity_label")).strip()
        if opportunity_label and opportunity_label in {
            "Elite Opportunity",
            "Strong Opportunity",
            "Starter At Risk",
            "Backup With Upside",
        }:
            opportunity_display = (
                f"{opportunity_label} (Health Risk)"
                if health_context["risk"]
                else opportunity_label
            )
            chips.append(
                player_support_chip_html(
                    opportunity_display,
                    "warning" if health_context["risk"] else "success",
                )
            )
        elif opportunity_label == "Starter At Risk":
            chips.append(player_support_chip_html(opportunity_label, "warning"))
        if health_context["risk"]:
            chips.append(player_support_chip_html(health_context["label"], "risk"))
            health_note_html = (
                f"<div class='trade-asset-health-note'>{escape(health_context['note'])}</div>"
            )
        role = _safe_text(asset.get("role")).strip()
        if role:
            meta_parts.append(role)
        meta_parts.append(
            injury_adjusted_value_html(
                "Score",
                score,
                asset,
                css_class="trade-asset-value",
            )
        )
        chip_row = f"<div class='trade-asset-tags'>{''.join(chips)}</div>" if chips else ""
        status_row = f"<div class='trade-asset-status-row'>{player_status_pill_html(status_style['label'])}{position_badge}</div>"
        row_class += f" trade-asset-row-player trade-asset-row-tone-{status_style['tone']}"

    meta = " | ".join(
        part if "trade-asset-value" in part else escape(part)
        for part in meta_parts
        if part
    )
    player_data_attr = (
        f" data-player-id='{escape(player_id, quote=True)}'"
        if asset_type != "pick" and player_id
        else ""
    )
    return (
        f"<div class='{row_class}'{player_data_attr}>"
        f"{avatar}"
        "<div class='trade-asset-copy'>"
        f"{status_row}"
        f"<div class='trade-asset-name'>{escape(display_label)}</div>"
        f"{chip_row}"
        f"<div class='trade-asset-meta'>{meta}</div>"
        f"{health_note_html}"
        "</div>"
        "</div>"
    )



TRADE_HUB_SECTION_ORDER = (
    "Headline Recommendation",
    "High Confidence",
    "Need-Based",
    "Contender",
    "Rebuild",
    "Draft Capital",
    "Age Optimization",
    "Health Relief",
)


def trade_explanation_disclosure_key(idea: dict, *, key_prefix: str) -> str:
    """Return a stable per-surface key without exposing trade identity values."""

    identity = "\x1f".join(str(value) for value in _trade_idea_identity(idea))
    identity_digest = sha256(identity.encode("utf-8")).hexdigest()[:16]
    surface_digest = sha256(str(key_prefix).encode("utf-8")).hexdigest()[:8]
    return f"trade_why_{surface_digest}_{identity_digest}"


def toggle_trade_explanation(
    state_key: str,
    *,
    state: MutableMapping | None = None,
) -> None:
    """Toggle one card's disclosure state; the optional mapping supports tests."""

    target = st.session_state if state is None else state
    target[state_key] = not bool(target.get(state_key, False))


def trade_hub_entitlement_presentation(
    primary_ideas: list[dict],
    secondary_ideas: list[dict],
    *,
    entitlement: object,
) -> dict:
    """Apply the established post-Trust Trade Hub presentation contract."""

    primary = list(primary_ideas or [])
    secondary = list(secondary_ideas or [])
    approved_count = len(primary) + len(secondary)
    is_premium = entitlement == premium.PREMIUM
    visible_ideas = primary + secondary if is_premium else primary[:2]
    hidden_count = approved_count - len(visible_ideas)
    return {
        "entitlement": premium.PREMIUM if is_premium else premium.FREE,
        "is_premium": is_premium,
        "approved_count": approved_count,
        "visible_ideas": visible_ideas,
        "visible_count": len(visible_ideas),
        "hidden_count": hidden_count,
        "show_board_upgrade": not is_premium and hidden_count > 0,
    }


def trade_hub_entitlement_summary(
    presentation: dict,
    *,
    section_count: int,
) -> str:
    approved_count = int(presentation.get("approved_count") or 0)
    visible_count = int(presentation.get("visible_count") or 0)
    hidden_count = int(presentation.get("hidden_count") or 0)
    if presentation.get("is_premium"):
        if approved_count == 1:
            return (
                "Premium board: 1 approved idea cleared generation and Trust. "
                "No recommendations are hidden by entitlement."
            )
        return (
            f"Premium board: {approved_count} approved ideas across "
            f"{max(1, int(section_count))} sections. "
            "Use the section selector to view the complete board."
        )
    if hidden_count > 0:
        return (
            f"Free preview: {visible_count} of {approved_count} approved ideas "
            "are available here. Premium unlocks the remaining board."
        )
    return (
        f"Free preview: all {approved_count} approved "
        f"{'idea is' if approved_count == 1 else 'ideas are'} available here. "
        "No recommendations are hidden by entitlement."
    )


def render_trade_hub_entitlement_summary(
    presentation: dict,
    *,
    section_count: int,
) -> None:
    """Render the existing entitlement copy through the canonical callout primitive."""

    ui_primitives.render_informational_callout(
        trade_hub_entitlement_summary(
            presentation,
            section_count=section_count,
        ),
        variant="premium" if presentation.get("show_board_upgrade") else "information",
        title="Trade Hub access",
    )


def _trade_idea_identity(idea: dict) -> tuple:
    return (
        _safe_text(idea.get("partner_roster_id")),
        _safe_text(idea.get("my_player")),
        _safe_text(idea.get("their_player")),
        int(idea.get("my_score") or 0),
        int(idea.get("their_score") or 0),
        _safe_text(idea.get("tag")),
    )


def trade_hub_display_section(idea: dict) -> str:
    """Classify an existing recommendation for display without changing its score or order."""
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

    if any(token in searchable for token in ("injury", "health", "ir ", "relief")):
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


def group_trade_hub_ideas(
    ideas: list[dict],
    *,
    headline_idea: dict | None = None,
) -> dict[str, list[dict]]:
    """Build ordered, non-empty presentation sections from an already-ranked board."""
    grouped = {section: [] for section in TRADE_HUB_SECTION_ORDER}
    headline_identity = _trade_idea_identity(headline_idea) if headline_idea else None
    headline_used = False
    for idea in ideas:
        if (
            headline_identity is not None
            and not headline_used
            and _trade_idea_identity(idea) == headline_identity
        ):
            grouped["Headline Recommendation"].append(idea)
            headline_used = True
            continue
        grouped[trade_hub_display_section(idea)].append(idea)
    return {section: grouped[section] for section in TRADE_HUB_SECTION_ORDER if grouped[section]}


def trade_hub_empty_state_copy(active_section: str = "") -> dict[str, str]:
    section = _safe_text(active_section, "this view")
    return {
        "title": f"No {section.lower()} trades right now",
        "reason": "No existing recommendation cleared the current value, fit, confidence, and partner-market rules for this view.",
        "suggestion": "Try another section or adjust the team lens. The underlying recommendation rules have not been relaxed.",
    }


def render_trade_hub_section_filter(
    grouped_ideas: dict[str, list[dict]],
    *,
    key: str,
) -> str:
    options = [section for section in TRADE_HUB_SECTION_ORDER if grouped_ideas.get(section)]
    if not options:
        return ""
    current = st.session_state.get(key)
    if current not in options:
        current = options[0]
    selected = st.pills(
        "Trade board",
        options,
        default=current,
        key=key,
        format_func=lambda section: f"{section} · {len(grouped_ideas.get(section, []))}",
    )
    return selected or current


def trade_card_presentation_contract(idea: dict) -> dict:
    """Return the unchanged recommendation fields used by the compact card."""

    return {
        "send_assets": [dict(asset) for asset in (idea.get("send_assets") or [])],
        "receive_assets": [dict(asset) for asset in (idea.get("receive_assets") or [])],
        "send_score": int(idea.get("my_score") or 0),
        "receive_score": int(idea.get("their_score") or 0),
        "trade_gain": int(idea.get("trade_gain") or 0),
        "confidence": idea.get("trade_confidence_label"),
        "ordering_score": idea.get("trade_idea_score"),
    }


def render_trade_idea_card(
    idea: dict,
    idea_idx: int,
    *,
    format_score: Callable,
    tidy_label: Callable,
    trade_target_reason: Callable,
    trade_partner_reason: Callable,
    trade_confidence_reason: Callable,
    trade_value_verdict: Callable,
    trade_display_confidence_label: Callable,
    injury_display_context: Callable,
    glyph_chip_html: Callable,
    assets_html: Callable,
    key_prefix: str = "trade_idea",
    render_tappable_player_html: Callable | None = None,
    open_player_quick_view: Callable | None = None,
) -> None:
    presentation = trade_card_presentation_contract(idea)
    send_assets = presentation["send_assets"]
    receive_assets = presentation["receive_assets"]
    send_score = presentation["send_score"]
    receive_score = presentation["receive_score"]
    trade_gain = presentation["trade_gain"]
    confidence = trade_display_confidence_label(idea)
    market = _safe_text(idea.get("market_realism_label"), "Thin")
    fit = _safe_text(idea.get("fit_grade"), "Fit Pending")
    partner = escape(_safe_text(idea.get("partner_team_name"), "Trade partner"))
    tag = escape(_safe_text(idea.get("tag"), "Trade idea"))
    section = escape(_safe_text(idea.get("_display_section"), "Trade Board"))
    my_mode = escape(
        _safe_text(
            idea.get("my_strategy"),
            tidy_label(_safe_text(idea.get("my_mode"), "unknown")),
        )
    )

    if trade_gain > 0:
        delta_class = "trade-delta-positive"
        delta_text = f"+{format_score(trade_gain)}"
    elif trade_gain < 0:
        delta_class = "trade-delta-negative"
        delta_text = f"-{format_score(abs(trade_gain))}"
    else:
        delta_class = "trade-delta-neutral"
        delta_text = "Even"

    confidence_tone = (
        "success"
        if _safe_text(confidence).casefold().startswith("high")
        else "premium"
        if _safe_text(confidence).casefold().startswith("medium")
        else "warning"
    )
    market_tone = (
        "success"
        if market.casefold() == "likely"
        else "premium"
        if market.casefold() == "plausible"
        else "warning"
    )
    fit_tone = "success" if fit in {"Strong", "Solid"} else "warning"
    strategy_risk_label = _safe_text(idea.get("strategy_risk_label")).strip()
    compact_chips = "".join(
        (
            glyph_chip_html(f"{confidence} confidence", confidence_tone),
            glyph_chip_html(f"{fit} fit", fit_tone),
            glyph_chip_html(f"{market} market", market_tone),
            (
                glyph_chip_html(strategy_risk_label, "warning")
                if strategy_risk_label
                else ""
            ),
        )
    )
    secondary_class = (
        " trade-idea-secondary"
        if _safe_text(idea.get("trade_surface_tier"), "primary").casefold() == "secondary"
        else ""
    )
    tone_class = (
        " trade-idea-positive"
        if trade_gain > 0
        else " trade-idea-negative"
        if trade_gain < 0
        else " trade-idea-neutral"
    )

    card_html = textwrap.dedent(
        f"""
        <article class="trade-idea-card trade-idea-card-compact dg-card-primary{tone_class}{secondary_class}" id="trade-idea-{idea_idx}">
            <header class="trade-card-top trade-card-top-compact">
                <div class="trade-card-kicker">{section}</div>
                <div class="trade-card-title">{tag}</div>
                <div class="trade-card-partner">Trade with <strong>{partner}</strong> · {my_mode} lens</div>
                <div class="trade-card-meta-row">{compact_chips}</div>
            </header>
            <div class="trade-matchup trade-matchup-compact">
                <section class="trade-side">
                    <div class="trade-side-header"><span>You send</span><strong class="trade-side-value trade-value-send">{format_score(send_score)}</strong></div>
                    {assets_html(send_assets)}
                </section>
                <div class="trade-vs" aria-label="for">FOR</div>
                <section class="trade-side">
                    <div class="trade-side-header"><span>You receive</span><strong class="trade-side-value trade-value-receive">{format_score(receive_score)}</strong></div>
                    {assets_html(receive_assets)}
                </section>
            </div>
            <div class="trade-card-net-strip">
                <span>Net result</span>
                <strong class="{delta_class}">{delta_text}</strong>
            </div>
        </article>
        """
    ).strip()
    render_trade_html_with_player_taps(
        card_html,
        send_assets + receive_assets,
        key_prefix=f"{key_prefix}_{idea_idx}",
        source_label="Trade Hub",
        render_tappable_player_html=render_tappable_player_html,
        open_player_quick_view=open_player_quick_view,
    )

    explanation_key = trade_explanation_disclosure_key(
        idea,
        key_prefix=key_prefix,
    )
    explanation_state_key = f"{explanation_key}_open"
    show_explanation = bool(st.session_state.get(explanation_state_key, False))
    st.button(
        f"{'▾' if show_explanation else '▸'} Why this trade",
        key=f"{explanation_key}_control",
        help=(
            "Collapse the explanation for this trade"
            if show_explanation
            else "Expand the explanation for this trade"
        ),
        on_click=toggle_trade_explanation,
        args=(explanation_state_key,),
        type="tertiary",
        width="content",
    )
    if show_explanation:
        with performance.time_block(
            "trade_hub_explanation_expansion",
            category="render",
        ):
            target_reason = escape(_safe_text(trade_target_reason(idea)))
            partner_reason = escape(_safe_text(trade_partner_reason(idea)))
            confidence_reason = escape(_safe_text(trade_confidence_reason(idea)))
            value_summary = escape(
                f"{trade_value_verdict(trade_gain)} · Send {format_score(send_score)} · "
                f"Receive {format_score(receive_score)} · Net {delta_text}"
            )
            evidence_note = escape(_safe_text(idea.get("trust_evidence_note")))
            evidence_row = (
                f'<div class="trade-reason-row"><span>Evidence note</span><p>{evidence_note}</p></div>'
                if evidence_note
                else ""
            )
            explanation_html = textwrap.dedent(
                f"""
                <div class="trade-reason-panel">
                    <div class="trade-reason-row"><span>Why it helps you</span><p>{target_reason}</p></div>
                    <div class="trade-reason-row"><span>Why the partner might consider it</span><p>{partner_reason}</p></div>
                    <div class="trade-reason-row"><span>Confidence caveat</span><p>{confidence_reason}</p></div>
                    {evidence_row}
                    <div class="trade-reason-row"><span>Value summary</span><p>{value_summary}</p></div>
                </div>
                """
            ).strip()
            render_html_fragment(explanation_html)
            health_context = injury_display_context(idea)
            if health_context.get("risk"):
                st.warning(
                    f"{health_context.get('label', 'Health watch')}: "
                    f"{health_context.get('note', '')}"
                )


def render_trade_idea_player_actions(
    idea: dict,
    *,
    key_prefix: str,
    return_page: str,
    source_label: str,
    render_player_detail_button_grid: Callable,
    render_recommendation_feedback: Callable,
    trade_target_reason: Callable,
    trade_partner_reason: Callable,
    trade_confidence_reason: Callable,
) -> None:
    player_rows = []
    for asset in (idea.get("send_assets") or []) + (idea.get("receive_assets") or []):
        if _safe_text(asset.get("asset_type"), "player") != "player":
            continue
        player_id = _safe_text(asset.get("player_id")).strip()
        if not player_id:
            continue
        player_rows.append(
            {
                "player_id": player_id,
                "name": _safe_text(asset.get("name"), _safe_text(asset.get("label"), "Player")),
            }
        )
    report_assets = [
        asset
        for asset in (idea.get("send_assets") or []) + (idea.get("receive_assets") or [])
        if _safe_text(asset.get("asset_type"), "player") == "player"
    ]
    with st.expander("Player actions", expanded=False):
        render_player_detail_button_grid(
            player_rows,
            key_prefix=key_prefix,
            return_page=return_page,
            source_label=source_label,
            title="Inspect players",
            max_buttons=6,
            open_mode="quick_view",
        )
        render_recommendation_feedback(
            page="trade_hub",
            surface="Trade Hub Trade Idea",
            recommendation_type="trade_idea",
            key_prefix=f"{key_prefix}_feedback",
            recommendation_title=_safe_text(idea.get("tag"), "Trade idea"),
            recommendation_summary=_safe_text(idea.get("rationale") or idea.get("reasoning_summary")),
            player_ids=[asset.get("player_id") for asset in report_assets],
            player_names=[asset.get("name") or asset.get("label") for asset in report_assets],
            score_fields={
                "send_score": idea.get("my_score"),
                "receive_score": idea.get("their_score"),
                "trade_gain": idea.get("trade_gain"),
                "fit_grade": idea.get("fit_grade"),
                "market_realism_score": idea.get("market_realism_score"),
            },
            confidence_fields={
                "confidence": idea.get("trade_confidence_label"),
                "market_realism": idea.get("market_realism_label"),
                "headline_ready": idea.get("trade_headline_ready"),
            },
            reason_fields={
                "partner_team": idea.get("partner_team_name"),
                "target_reason": trade_target_reason(idea),
                "partner_reason": trade_partner_reason(idea),
                "confidence_reason": trade_confidence_reason(idea),
            },
            team_id=_safe_text(idea.get("partner_roster_id")),
        )
    st.markdown(
        "<div class='trade-idea-end-marker' aria-hidden='true'></div>",
        unsafe_allow_html=True,
    )


def render_player_trade_hub_card(
    idea: dict,
    idea_idx: int,
    *,
    key_prefix: str = "player_hub_profile",
    recommendation_reason_text: Callable,
    render_trade_idea_card: Callable,
    render_trade_idea_player_actions: Callable,
) -> None:
    path = _safe_text(idea.get("hub_path"), _safe_text(idea.get("tag"), "Trade path"))
    reason_a = _safe_text(
        idea.get("hub_partner_reason")
        or idea.get("partner_trade_implication")
        or idea.get("hub_candidate_reason")
        or idea.get("reasoning_summary")
    )
    reason_b = _safe_text(
        idea.get("hub_target_fit_reason")
        or idea.get("hub_solution_reason")
    )
    if path:
        st.markdown(f"#### {path}")
    if reason_a:
        st.caption("Why this partner: " + recommendation_reason_text(reason_a, 132))
    if reason_b:
        st.caption("Why this target: " + recommendation_reason_text(reason_b, 132))
    render_trade_idea_card(
        idea,
        idea_idx,
        key_prefix=f"{key_prefix}_{idea_idx}_card",
    )
    render_trade_idea_player_actions(
        idea,
        key_prefix=f"{key_prefix}_{idea_idx}",
        return_page="trade_hub",
        source_label="Trade Hub",
    )
