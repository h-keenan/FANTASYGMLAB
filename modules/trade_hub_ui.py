import textwrap
import time
from html import escape
from typing import Callable

import pandas as pd
import streamlit as st

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
            idea.get("hub_partner_reason")
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
    def trade_confidence_tone(label: str) -> str:
        label_key = _safe_text(label).strip().lower()
        if label_key == "high":
            return "success"
        if label_key == "medium":
            return "premium"
        return "warning"

    def trade_market_tone(label: str) -> str:
        label_key = _safe_text(label).strip().lower()
        if label_key == "likely":
            return "success"
        if label_key == "plausible":
            return "premium"
        return "warning"

    send_assets = idea.get("send_assets") or []
    receive_assets = idea.get("receive_assets") or []
    send_score = int(idea.get("my_score") or 0)
    receive_score = int(idea.get("their_score") or 0)
    trade_gain = int(idea.get("trade_gain") or 0)
    max_score = max(send_score, receive_score, 1)
    send_pct = max(3, min(100, int(round((send_score / max_score) * 100)))) if send_score else 0
    receive_pct = max(3, min(100, int(round((receive_score / max_score) * 100)))) if receive_score else 0

    if trade_gain > 0:
        delta_class = "trade-delta-positive"
        delta_text = f"+{format_score(trade_gain)} score"
    elif trade_gain < 0:
        delta_class = "trade-delta-negative"
        delta_text = f"-{format_score(abs(trade_gain))} score"
    else:
        delta_class = "trade-delta-neutral"
        delta_text = "Even score"

    partner_text = _safe_text(idea.get("partner_team_name"), "Trade partner")
    tag_text = _safe_text(idea.get("tag"), "Trade idea")
    my_mode_text = _safe_text(idea.get("my_strategy"), tidy_label(_safe_text(idea.get("my_mode"), "unknown")))
    partner_mode_text = _safe_text(idea.get("partner_strategy"), tidy_label(_safe_text(idea.get("partner_mode"), "unknown")))
    partner = escape(partner_text)
    tag = escape(tag_text)
    my_mode = escape(my_mode_text)
    partner_mode = escape(partner_mode_text)
    rationale = escape(_safe_text(idea.get("rationale")))
    partner_tendencies = escape(_safe_text(idea.get("partner_tendencies_summary")))
    partner_trade_implication = escape(_safe_text(idea.get("partner_trade_implication")))
    market_summary = escape(_safe_text(idea.get("market_realism_summary")))
    fit_summary = escape(_safe_text(idea.get("fit_summary") or idea.get("reasoning_summary") or idea.get("rationale")))
    confidence_summary = escape(_safe_text(idea.get("trade_confidence_summary")))
    strategy_fit_reason = escape(_safe_text(idea.get("strategy_fit_reason")))
    strategy_profile = escape(
        _safe_text(
            idea.get("strategy_archetype")
            or idea.get("strategy_profile_label")
            or idea.get("my_strategy")
        )
    )
    strategy_risk_label = _safe_text(idea.get("strategy_risk_label"))
    target_reason = escape(trade_target_reason(idea))
    partner_reason = escape(trade_partner_reason(idea))
    confidence_reason = escape(trade_confidence_reason(idea))
    value_grade_text = trade_value_verdict(trade_gain)
    fit_grade_text = _safe_text(idea.get("fit_grade"), "Fit Pending")
    market_grade_text = _safe_text(idea.get("market_realism_label"), "Thin")
    confidence_grade_text = trade_display_confidence_label(idea)
    trade_health_context = injury_display_context(idea)
    reason_tags = idea.get("reasoning_tags") or [idea.get("tag", "Trade idea")]
    reason_tags_html = "".join(
        f"<span class='trade-reason-tag'>{escape(_safe_text(reason_tag))}</span>"
        for reason_tag in reason_tags
        if _safe_text(reason_tag)
    )
    reason_tags_row = f"<div class='trade-reason-tags'>{reason_tags_html}</div>" if reason_tags_html else ""
    value_tone = "success" if trade_gain >= 0 else "warning"
    fit_tone = "success" if fit_grade_text in {"Strong", "Solid"} else "warning"
    market_tone = trade_market_tone(market_grade_text)
    confidence_tone = trade_confidence_tone(confidence_grade_text)
    meta_chips = "".join(
        [
            glyph_chip_html(f"Value {value_grade_text}", value_tone),
            glyph_chip_html(f"Fit {fit_grade_text}", fit_tone),
            glyph_chip_html(f"Market {market_grade_text}", market_tone),
            glyph_chip_html(f"Confidence {confidence_grade_text}", confidence_tone),
            (
                glyph_chip_html(strategy_risk_label, "warning")
                if strategy_risk_label
                else ""
            ),
        ]
    )
    meta_row = f"<div class='trade-card-meta-row'>{meta_chips}</div>"
    is_secondary = _safe_text(idea.get("trade_surface_tier"), "primary").strip().lower() == "secondary"
    card_tone_class = " trade-idea-positive" if trade_gain > 0 else " trade-idea-negative" if trade_gain < 0 else " trade-idea-neutral"
    if is_secondary:
        card_tone_class += " trade-idea-secondary"
    outgoing_focus = escape(_safe_text(idea.get("my_player"), "Package"))
    incoming_focus = escape(_safe_text(idea.get("their_player"), "Target"))
    focus_row = (
        "<div class='trade-card-focus-row'>"
        + "<div class='trade-card-focus-item'>"
        + "<div class='trade-card-focus-label'>Outgoing</div>"
        + f"<div class='trade-card-focus-value'>{outgoing_focus}</div>"
        + "</div>"
        + "<div class='trade-card-focus-item'>"
        + "<div class='trade-card-focus-label'>Target</div>"
        + f"<div class='trade-card-focus-value'>{incoming_focus}</div>"
        + "</div>"
        + "<div class='trade-card-focus-item'>"
        + "<div class='trade-card-focus-label'>Confidence</div>"
        + f"<div class='trade-card-focus-value'>{escape(confidence_grade_text)}</div>"
        + "</div>"
        + "</div>"
    )
    secondary_banner = (
        "<div class='trade-secondary-banner'>Secondary path: fits the engine, but market confidence is lighter.</div>"
        if is_secondary
        else ""
    )
    health_banner = (
        f"<div class='trade-secondary-banner'>{escape(trade_health_context['label'])}: "
        f"{escape(trade_health_context['note'])}</div>"
        if trade_health_context["risk"]
        else ""
    )
    why_items = [
        (
            "Target",
            target_reason or "Best available fit under your current roster lens.",
        ),
        (
            "Partner",
            partner_reason or "This partner is the cleanest current roster match for the package.",
        ),
        ("Confidence", confidence_reason),
    ]
    if strategy_fit_reason:
        strategy_label = f"Strategy ({strategy_profile})" if strategy_profile else "Strategy"
        why_items.append((strategy_label, strategy_fit_reason))
    explanation_cards_html = "".join(
        "<div class='trade-explain-card'>"
        + f"<div class='trade-explain-label'>{escape(label)}</div>"
        + f"<div class='trade-explain-copy'>{copy}</div>"
        + "</div>"
        for label, copy in why_items[:4]
        if copy
    )
    score_items = [
        ("Value", value_grade_text, f"Send {format_score(send_score)} | Get {format_score(receive_score)}"),
        ("Fit", fit_grade_text, fit_summary or escape(_safe_text(idea.get("reasoning_summary")))),
        (
            "Market",
            market_grade_text,
            market_summary or "Partner motivation and market perception clear the current bar.",
        ),
        (
            "Confidence",
            confidence_grade_text,
            confidence_summary or "Blends fit, partner motivation, and market realism.",
        ),
    ]
    score_chip_row = (
        "<div class='trade-score-chip-row'>"
        + "".join(
            "<span class='trade-score-chip'>"
            + f"<span class='trade-score-chip-label'>{escape(label)}</span>"
            + f"<strong>{escape(value)}</strong>"
            + "</span>"
            for label, value, note in score_items
        )
        + "</div>"
    )
    detail_summary = (
        "<div class='trade-detail-summary'>"
        "<div class='trade-detail-title'>Why this trade</div>"
        f"<div class='trade-explain-grid'>{explanation_cards_html}</div>"
        f"{score_chip_row}"
        "</div>"
        if explanation_cards_html
        else ""
    )
    detail_texts = [
        _safe_text(copy).strip().lower()
        for _, copy in why_items
        if _safe_text(copy).strip()
    ]
    detail_texts.extend(
        _safe_text(note).strip().lower()
        for _, _, note in score_items
        if _safe_text(note).strip()
    )

    def is_repeated_detail(text: str) -> bool:
        normalized = _safe_text(text).strip().lower()
        if not normalized:
            return True
        return any(
            normalized == detail
            or normalized in detail
            or (detail and detail in normalized)
            for detail in detail_texts
        )

    rationale_html = (
        f"<div class='trade-rationale trade-rationale-compact'>{rationale}</div>"
        if rationale and not is_repeated_detail(rationale)
        else ""
    )
    partner_implication_html = (
        f"<div class='trade-rationale trade-rationale-compact'><strong>Trade implication:</strong> {partner_trade_implication}</div>"
        if partner_trade_implication and not is_repeated_detail(partner_trade_implication)
        else ""
    )

    card_html = textwrap.dedent(f"""
    <div class="trade-idea-card dg-card-primary{card_tone_class}" id="trade-idea-{idea_idx}">
        <div class="trade-card-top">
            <div>
                <div class="trade-card-kicker">Trade with {partner}</div>
                <div class="trade-card-title">{tag}</div>
                {meta_row}
                <div class='trade-card-subtitle'>My {my_mode} | Their {partner_mode}</div>
                {f"<div class='trade-card-subtitle'>Manager tendencies: {partner_tendencies}</div>" if partner_tendencies else ""}
                {reason_tags_row}
                {focus_row}
                {secondary_banner}
                {health_banner}
            </div>
            <div class="trade-delta-pill {delta_class}">{delta_text}</div>
        </div>
        <div class="trade-matchup">
            <div class="trade-side">
                <div class="trade-side-header"><span>You send</span><span class="trade-side-value">{format_score(send_score)}</span></div>
                {assets_html(send_assets)}
            </div>
            <div class="trade-vs">FOR</div>
            <div class="trade-side">
                <div class="trade-side-header"><span>You get</span><span class="trade-side-value">{format_score(receive_score)}</span></div>
                {assets_html(receive_assets)}
            </div>
        </div>
        {detail_summary}
        <div class="trade-value-meter">
            <div class="trade-meter-row">
                <div class="trade-meter-label">Send</div>
                <div class="trade-meter-track"><div class="trade-meter-fill trade-meter-send" style="width:{send_pct}%"></div></div>
                <div class="trade-meter-number">{format_score(send_score)}</div>
            </div>
            <div class="trade-meter-row">
                <div class="trade-meter-label">Get</div>
                <div class="trade-meter-track"><div class="trade-meter-fill trade-meter-receive" style="width:{receive_pct}%"></div></div>
                <div class="trade-meter-number">{format_score(receive_score)}</div>
            </div>
        </div>
        {rationale_html}
        {partner_implication_html}
    </div>
    """).strip()
    render_trade_html_with_player_taps(
        card_html,
        send_assets + receive_assets,
        key_prefix=f"{key_prefix}_{idea_idx}",
        source_label="Trade Hub",
        render_tappable_player_html=render_tappable_player_html,
        open_player_quick_view=open_player_quick_view,
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
    render_player_detail_button_grid(
        player_rows,
        key_prefix=key_prefix,
        return_page=return_page,
        source_label=source_label,
        title="Inspect players in this path",
        max_buttons=6,
        open_mode="quick_view",
    )
    report_assets = [
        asset
        for asset in (idea.get("send_assets") or []) + (idea.get("receive_assets") or [])
        if _safe_text(asset.get("asset_type"), "player") == "player"
    ]
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
