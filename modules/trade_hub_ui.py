import textwrap
import time
from hashlib import sha256
from html import escape
from typing import Callable, MutableMapping

import pandas as pd
import streamlit as st

from modules import brand_identity
from modules import football_assets, performance, trade_detail_navigation
from modules import premium
from modules import recommendation_trust_ux
from modules import ui_primitives
from modules.design_tokens import DESIGN_TOKEN_CSS
from modules.player_images import get_player_image_url
from modules.html_rendering import render_html_fragment

from modules.player_cards import (
    injury_adjusted_value_html,
    player_prestige_level,
    player_position_badge_html,
    player_team_age_meta,
)

TRADE_SUMMARY_COMPONENT_CSS = DESIGN_TOKEN_CSS + """
* { box-sizing: border-box; }
body { margin: 0; background: transparent; color: var(--color-text-primary); font-family: var(--font-family-sans); }
.trade-summary-card {
    background: var(--color-surface-primary);
    border: var(--border-width-default) solid var(--color-border-strong);
    border-left: var(--border-width-semantic) solid var(--color-information);
    color: var(--color-text-primary);
    cursor: pointer;
    display: grid;
    gap: var(--space-sm);
    max-width: 100%;
    min-height: var(--touch-target-min);
    overflow: hidden;
    padding: var(--space-md);
    width: 100%;
}
.trade-summary-card:hover { background: var(--color-surface-raised); border-color: var(--color-information); }
.trade-summary-card:focus-visible { box-shadow: var(--focus-ring); outline: none; }
.trade-summary-header { align-items: end; display: flex; gap: var(--space-md); justify-content: space-between; min-width: 0; }
.trade-summary-heading { display: grid; gap: var(--space-xs); min-width: 0; }
.trade-summary-category {
    color: var(--color-text-muted);
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    line-height: var(--line-height-badge);
    text-transform: uppercase;
}
.trade-summary-visually-hidden {
    clip: rect(0 0 0 0);
    clip-path: inset(50%);
    height: 1px;
    overflow: hidden;
    position: absolute;
    white-space: nowrap;
    width: 1px;
}
.trade-summary-side-label {
    color: var(--color-text-muted);
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    line-height: var(--line-height-badge);
    text-transform: uppercase;
}
.trade-summary-title {
    color: var(--color-text-primary);
    font: var(--font-card-title);
    margin-top: var(--space-xs);
    overflow-wrap: break-word;
    white-space: normal;
}
.trade-summary-partner { color: var(--color-text-secondary); flex: 0 0 auto; font-size: var(--font-size-caption); }
.trade-summary-package { border-block: var(--border-width-default) solid var(--color-border); padding-block: var(--space-sm); }
.trade-summary-side { align-items: center; display: grid; gap: var(--space-sm); grid-template-columns: 4.5rem minmax(0, 1fr); min-width: 0; }
.trade-summary-side + .trade-summary-side { border-top: var(--border-width-default) solid var(--color-border); margin-top: var(--space-sm); padding-top: var(--space-sm); }
.trade-summary-assets { display: flex; flex-wrap: wrap; gap: var(--space-xs); min-width: 0; }
.trade-summary-asset-chip { align-items: center; display: inline-flex; gap: var(--space-xs); min-width: 0; }
.trade-summary-avatar {
    align-items: center;
    background: var(--color-surface-raised);
    border: var(--border-width-default) solid var(--color-border);
    display: inline-flex;
    flex: 0 0 3rem;
    height: 3rem;
    justify-content: center;
    overflow: hidden;
    width: 3rem;
}
.trade-summary-avatar img { height: 100%; object-fit: cover; width: 100%; }
.trade-summary-avatar--pick { color: var(--color-information); font-size: var(--font-size-badge); font-weight: var(--font-weight-title); }
.trade-summary-asset-name { color: var(--color-text-primary); font-size: var(--font-size-caption); font-weight: var(--font-weight-metadata); overflow-wrap: break-word; }
.trade-summary-value { align-items: center; color: var(--color-text-muted); display: flex; font-size: var(--font-size-caption); justify-content: space-between; }
.trade-summary-value strong { font-size: var(--font-size-display); font-weight: var(--font-weight-display); }
.trade-delta-positive { color: var(--color-success); }
.trade-delta-negative { color: var(--color-danger); }
.trade-delta-neutral { color: var(--color-text-secondary); }
.trade-summary-signals { display: flex; flex-wrap: wrap; gap: var(--space-xs); }
.dg-ui-badge {
    align-items: center;
    border: var(--border-width-default) solid var(--color-border-strong);
    display: inline-flex;
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    line-height: var(--line-height-badge);
    min-height: var(--space-xl);
    padding-inline: var(--space-sm);
    text-transform: uppercase;
}
.dg-ui-badge--neutral { background: var(--color-muted-soft); color: var(--color-text-secondary); }
.dg-ui-badge--information { background: var(--color-information-soft); color: var(--color-information); }
.dg-ui-badge--opportunity { background: var(--color-opportunity-soft); color: var(--color-opportunity); }
.dg-ui-badge--success { background: var(--color-success-soft); color: var(--color-success); }
.dg-ui-badge--caution { background: var(--color-warning-soft); color: var(--color-warning); }
.dg-ui-badge--danger { background: var(--color-danger-soft); color: var(--color-danger); }
.dg-ui-badge--premium { background: var(--color-action-soft); color: var(--color-premium); }
.trade-summary-executive {
    display: grid;
    gap: var(--space-xs);
    min-width: 0;
}
.trade-summary-why {
    color: var(--color-text-primary);
    font-size: var(--font-size-caption);
    font-weight: var(--font-weight-metadata);
    line-height: var(--line-height-body);
    margin: 0;
}
.trade-summary-impact-row {
    align-items: baseline;
    display: flex;
    gap: var(--space-sm);
    justify-content: space-between;
    min-width: 0;
}
.trade-summary-impact-row .trade-summary-value {
    flex: 1 1 auto;
    gap: var(--space-sm);
    justify-content: flex-start;
}
.trade-summary-signals--quiet {
    opacity: 0.88;
}
.trade-summary-rationale {
    color: var(--color-text-secondary);
    display: -webkit-box;
    font-size: var(--font-size-caption);
    line-height: var(--line-height-body);
    margin: 0;
    overflow: hidden;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
}
.trade-summary-affordance {
    border-top: var(--border-width-default) solid var(--color-border);
    color: var(--color-information);
    font-size: var(--font-size-caption);
    font-weight: var(--font-weight-button);
    padding-top: var(--space-sm);
    text-align: right;
}
.trade-summary-footer {
    align-items: center;
    border-top: var(--border-width-default) solid var(--color-border);
    display: flex;
    gap: var(--space-sm);
    justify-content: space-between;
    padding-top: var(--space-sm);
}
.trade-summary-footer .trade-summary-affordance {
    border-top: 0;
    margin: 0;
    padding-top: 0;
}
.trade-summary-brand {
    align-items: center;
    color: var(--color-text-muted);
    display: inline-flex;
    gap: 0.28rem;
    min-width: 0;
}
.trade-summary-brand__mark {
    align-items: center;
    background: #f8fafc;
    color: #0b1220;
    display: inline-flex;
    font-size: 0.42rem;
    font-weight: 900;
    height: 0.9rem;
    justify-content: center;
    letter-spacing: 0.04em;
    min-width: 0.9rem;
    width: 0.9rem;
}
.trade-summary-brand__name {
    font-size: 0.56rem;
    font-weight: 750;
    white-space: nowrap;
}
.trade-summary-brand__badge {
    font-size: 0.48rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    opacity: 0.72;
    text-transform: uppercase;
    white-space: nowrap;
}
@media (max-width: 430px) {
    .trade-summary-card { gap: 0.35rem; min-height: 0; padding: 0.55rem 0.75rem; }
    .trade-summary-header { align-items: start; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--space-sm); }
    .trade-summary-partner { margin-top: 0; max-width: 8rem; text-align: right; }
    .trade-summary-why {
        display: -webkit-box;
        font-size: var(--font-size-caption);
        line-height: var(--line-height-caption);
        overflow: hidden;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 2;
    }
    .trade-summary-rationale { display: none; }
    .trade-summary-value strong { font-size: var(--font-size-section-title); }
    .trade-summary-package { padding-block: 0.35rem; }
    .trade-summary-side { gap: var(--space-xs); grid-template-columns: minmax(0, 1fr); }
    .trade-summary-side + .trade-summary-side { margin-top: 0.35rem; padding-top: 0.35rem; }
    .trade-summary-avatar { flex-basis: 2.75rem; height: 2.75rem; width: 2.75rem; }
    .trade-summary-signals { display: none; }
    .trade-summary-brand__name,
    .trade-summary-brand__badge { display: none; }
    .trade-summary-footer { gap: var(--space-xs); padding-top: 0.35rem; }
}
@media (max-width: 340px) {
    .trade-summary-card { min-height: 0; }
    .trade-summary-header { grid-template-columns: minmax(0, 1fr); }
    .trade-summary-partner { max-width: 100%; text-align: left; }
    .trade-summary-title { font-size: var(--font-size-body); }
}
@media (prefers-reduced-motion: reduce) { .trade-summary-card { transition: none; } }
"""


TRADE_SUMMARY_TAP_COMPONENT = st.components.v2.component(
    "trade_summary_tap",
    html='<div id="trade-summary-tap-root"></div>',
    css=TRADE_SUMMARY_COMPONENT_CSS,
    js="""
    export default function(component) {
      const { data, parentElement, setTriggerValue } = component
      const root = parentElement.querySelector("#trade-summary-tap-root")
      if (!root) return
      root.innerHTML = (data && data.html) || ""
      const card = root.querySelector(".trade-summary-card")
      if (!card) return
      card.setAttribute("role", "button")
      card.setAttribute("tabindex", "0")
      card.onclick = () => setTriggerValue("clicked", { key: data.key, ts: Date.now() })
      card.onkeydown = (event) => {
        if (event.key !== "Enter" && event.key !== " ") return
        event.preventDefault()
        setTriggerValue("clicked", { key: data.key, ts: Date.now() })
      }
    }
    """,
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


def _badge_variant_for_tone(tone: object) -> str:
    return {
        "premium": "premium",
        "elite": "premium",
        "star": "success",
        "core": "success",
        "starter": "information",
        "contributor": "information",
        "rise": "opportunity",
        "move": "caution",
        "hold": "neutral",
        "drop": "danger",
        "risk": "danger",
        "warning": "caution",
        "success": "success",
    }.get(_safe_text(tone).casefold(), "neutral")


def _safe_text(value, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return str(value)


def _compact_copy(value: object, *, limit: int = 180, default: str = "") -> str:
    text = " ".join(_safe_text(value, default).split())
    if len(text) <= limit:
        return text
    return textwrap.shorten(text, width=limit, placeholder="...")


def _compact_summary_sentence(value: object, *, default: str) -> str:
    """Return one scan-safe sentence without changing the detailed rationale."""

    text = " ".join(_safe_text(value, default).split())
    sentence = text.split(". ", 1)[0].rstrip(".!? ")
    return _compact_copy(f"{sentence}.", limit=112, default=default)


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
    if resolved["manual"]:
        st.caption(f"Active lens: {active_context} (auto: {automatic_context}).")
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
) -> str:
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
    ):
        render_trade_html(normalized_html)
        return ""

    clicked_player_id = render_tappable_player_html(
        html=normalized_html,
        key_prefix=key_prefix,
    )
    if clicked_player_id in player_meta:
        meta = player_meta[clicked_player_id]
        if open_player_quick_view is not None:
            open_player_quick_view(
                clicked_player_id,
                source_label=source_label,
                source_note=f"Inspect {meta['name']} from this trade package.",
                status_label=meta["status"],
            )
        return clicked_player_id
    return ""


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
        status_row = (
            "<div class='trade-asset-status-row'>"
            + ui_primitives.status_badge_html(
                status_style["label"],
                variant=_badge_variant_for_tone(status_style["tone"]),
            )
            + position_badge
            + "</div>"
        )
        row_class += f" trade-asset-row-player trade-asset-row-tone-{status_style['tone']}"

        detail_parts = [
            escape(part)
            for part in meta_parts[1:-1]
            if part
        ]
        details_html = (
            f"<div class='trade-asset-meta'>{' | '.join(detail_parts)}</div>"
            + health_note_html
        )
        formatted_age = format_age(asset.get("age"))
        return football_assets.player_card_html(
            football_assets.FootballPlayerAsset(
                player_id=player_id,
                display_name=display_label,
                position=position,
                team=team,
                prestige_label=status_style["label"],
                prestige_level=player_prestige_level(status_style["label"]),
                value_label="Score",
                value=score,
                age=f"Age {formatted_age}" if formatted_age else "",
            ),
            density="dense",
            mode="action-enabled" if player_id else "read-only",
            avatar_html=avatar,
            tags_html=chip_row,
            position_html=position_badge,
            value_html=injury_adjusted_value_html(
                "Score",
                score,
                asset,
                css_class="trade-asset-value",
            ),
            details_html=details_html,
            extra_classes=tuple(row_class.split()),
        )

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
    # Normalize so casing/whitespace never accidentally apply Free truncation.
    is_premium = str(entitlement or "").strip().casefold() == premium.PREMIUM
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
                "Trust approved 1 recommendation for this board. "
                "Premium shows every entitled idea — nothing is hidden by entitlement."
            )
        return (
            f"Premium board: {approved_count} approved ideas in one ranked feed "
            f"({max(1, int(section_count))} categories). "
            "Category badges label each package; ordering is unchanged."
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
    """Render entitlement context as a quiet one-line note above the ranked feed."""

    st.caption(
        trade_hub_entitlement_summary(
            presentation,
            section_count=section_count,
        )
    )


def _trade_idea_identity(idea: dict) -> tuple:
    def asset_identity(asset: dict) -> tuple[str, ...]:
        return (
            _safe_text(asset.get("asset_type"), "player"),
            _safe_text(asset.get("player_id")),
            _safe_text(asset.get("pick_id")),
            _safe_text(asset.get("season")),
            _safe_text(asset.get("round")),
            _safe_text(asset.get("name"), _safe_text(asset.get("label"))),
        )

    return (
        _safe_text(idea.get("partner_roster_id")),
        tuple(asset_identity(asset) for asset in (idea.get("send_assets") or [])),
        tuple(asset_identity(asset) for asset in (idea.get("receive_assets") or [])),
        int(idea.get("my_score") or 0),
        int(idea.get("their_score") or 0),
        _safe_text(idea.get("tag")),
    )


def trade_summary_key(
    idea: dict,
    *,
    page_context: str,
    instance_token: object = "",
) -> str:
    """Return a stable, page-scoped key for one tappable trade summary."""

    identity_digest = sha256(repr(_trade_idea_identity(idea)).encode("utf-8")).hexdigest()[:16]
    context_digest = sha256(str(page_context).encode("utf-8")).hexdigest()[:10]
    instance_digest = sha256(str(instance_token).encode("utf-8")).hexdigest()[:6]
    return f"trade_summary_{context_digest}_{identity_digest}_{instance_digest}"


def _trade_summary_assets_html(assets: list[dict]) -> str:
    if not assets:
        return "<div class='trade-summary-assets'><span class='trade-summary-asset-name'>No assets</span></div>"
    rows = []
    for asset in assets:
        label = _safe_text(asset.get("name"), _safe_text(asset.get("label"), "Asset"))
        if _safe_text(asset.get("asset_type"), "player") == "pick":
            avatar = "<span class='trade-summary-avatar trade-summary-avatar--pick' aria-hidden='true'>PICK</span>"
        else:
            player_id = _safe_text(asset.get("player_id")).strip()
            image_url = get_player_image_url(player_id) if player_id else ""
            avatar = (
                f"<span class='trade-summary-avatar'><img src='{escape(image_url, quote=True)}' "
                f"alt='' loading='lazy' decoding='async'></span>"
                if image_url
                else f"<span class='trade-summary-avatar' aria-hidden='true'>{escape(asset_initials(label))}</span>"
            )
        rows.append(
            "<span class='trade-summary-asset-chip'>"
            + avatar
            + f"<span class='trade-summary-asset-name'>{escape(label)}</span></span>"
        )
    return "<div class='trade-summary-assets'>" + "".join(rows) + "</div>"


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


def annotate_trade_hub_feed_categories(
    ideas: list[dict],
    *,
    headline_idea: dict | None = None,
) -> list[dict]:
    """Attach display category badges while preserving incoming board order.

    Callers must pass an already surface-ranked board. Category badges never
    re-order the feed.
    """

    headline_identity = _trade_idea_identity(headline_idea) if headline_idea else None
    headline_used = False
    annotated: list[dict] = []
    for idea in ideas or []:
        display_idea = dict(idea)
        if (
            headline_identity is not None
            and not headline_used
            and _trade_idea_identity(idea) == headline_identity
        ):
            display_idea["_display_section"] = "Headline Recommendation"
            headline_used = True
        else:
            display_idea["_display_section"] = trade_hub_display_section(idea)
        annotated.append(display_idea)
    return annotated


def order_trade_hub_visible_ideas(ideas: list[dict]) -> list[dict]:
    """Defensive presentation sort: highest executive usefulness first.

    Primary key remains `_trade_surface_sort_key` (headline readiness, tier,
    confidence, market/fit/strategy, priority). Categories never participate.

    `trade_gain` is only a last-resort presentation tie-break when surface keys
    are identical — it does not override Trust, tier, or confidence. Membership,
    scores, and football logic are unchanged.
    """

    from modules.trade_ideas import _trade_surface_sort_key

    def _presentation_key(idea: dict) -> tuple:
        return (
            *_trade_surface_sort_key(idea),
            int(idea.get("trade_gain") or 0),
        )

    return sorted(list(ideas or []), key=_presentation_key, reverse=True)


def trade_hub_empty_state_copy(active_section: str = "") -> dict[str, str]:
    section = _safe_text(active_section)
    if section:
        return {
            "title": f"No {section.lower()} trades right now",
            "reason": "No existing recommendation cleared the current value, fit, confidence, and partner-market rules for this view.",
            "suggestion": "Adjust the team lens or search a player path. The underlying recommendation rules have not been relaxed.",
        }
    return {
        "title": "No trade ideas right now",
        "reason": "No existing recommendation cleared the current value, fit, confidence, and partner-market rules.",
        "suggestion": "Adjust the team lens or search a player path. The underlying recommendation rules have not been relaxed.",
    }


def render_trade_hub_section_header(
    title: str,
    *,
    eyebrow: str,
    subtitle: str,
    heading_level: int = 2,
) -> None:
    ui_primitives.render_section_header(
        title,
        eyebrow=eyebrow,
        subtitle=subtitle,
        heading_level=heading_level,
    )


def render_trade_hub_empty_state(active_section: str = "") -> None:
    copy = trade_hub_empty_state_copy(active_section)
    ui_primitives.render_empty_state_panel(
        copy["title"],
        copy["reason"],
        kind="filtered-empty" if active_section else "no-data",
        recovery_guidance=copy["suggestion"],
    )


def trade_hub_section_inventory(grouped_ideas: dict[str, list[dict]]) -> dict:
    """Reconcile section counts with the exact recommendations a user can access."""
    counts = {
        section: len(grouped_ideas.get(section, []))
        for section in TRADE_HUB_SECTION_ORDER
        if grouped_ideas.get(section)
    }
    return {
        "counts": counts,
        "accessible_count": sum(counts.values()),
        "section_count": len(counts),
    }


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
    render_player_dossier: Callable | None = None,
    render_detail_actions: Callable[[dict, str], None] | None = None,
) -> None:
    """Render a compact summary and lazily mount the complete trade dossier."""

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
    section = escape(
        _safe_text(idea.get("_display_section"))
        or trade_hub_display_section(idea)
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
    confidence_badge = ui_primitives.status_badge_html(
        f"{confidence} confidence",
        variant=_badge_variant_for_tone(confidence_tone),
    )
    compact_chips = "".join((
        ui_primitives.status_badge_html(
            f"{fit} fit", variant=_badge_variant_for_tone(fit_tone)
        ),
        ui_primitives.status_badge_html(
            f"{market} market", variant=_badge_variant_for_tone(market_tone)
        ),
    ))
    why_sentence = escape(
        _compact_summary_sentence(
            recommendation_trust_ux.trade_problem_sentence(idea),
            default="Addresses a current roster need under your active lens.",
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
    summary_key = trade_summary_key(
        idea,
        page_context=key_prefix,
        instance_token=idea_idx,
    )
    summary_html = textwrap.dedent(
        f"""
        <article class="trade-summary-card dg-ui-card dg-ui-card--elevated{tone_class}{secondary_class}" data-trade-summary-key="{summary_key}" aria-label="View trade details: {tag} with {partner}">
            <header class="trade-summary-header">
                <div class="trade-summary-heading">
                    <div class="trade-summary-category">{section}</div>
                    <div class="trade-summary-title" title="{tag}">{tag}</div>
                </div>
                <div class="trade-summary-partner"><span class="trade-summary-visually-hidden">Trade partner: </span><strong>{partner}</strong></div>
            </header>
            <div class="trade-summary-executive">
                <p class="trade-summary-why">{why_sentence}</p>
                <div class="trade-summary-impact-row">
                    <div class="trade-summary-value">
                        <span>Value delta</span>
                        <strong class="{delta_class}">{delta_text}</strong>
                    </div>
                    {confidence_badge}
                </div>
            </div>
            <div class="trade-summary-package">
                <div class="trade-summary-side"><span class="trade-summary-side-label">Sending</span>{_trade_summary_assets_html(send_assets)}</div>
                <div class="trade-summary-side"><span class="trade-summary-side-label">Receiving</span>{_trade_summary_assets_html(receive_assets)}</div>
            </div>
            <div class="trade-summary-signals trade-summary-signals--quiet">{compact_chips}</div>
            <div class="trade-summary-footer">
                {brand_identity.trade_screenshot_brand_html()}
                <div class="trade-summary-affordance" aria-hidden="true">Review package →</div>
            </div>
        </article>
        """
    ).strip()
    try:
        summary_result = TRADE_SUMMARY_TAP_COMPONENT(
            key=f"{summary_key}_open",
            data={"html": normalize_trade_html(summary_html), "key": summary_key},
            width="stretch",
            height="content",
            on_clicked_change=lambda: None,
        )
        summary_clicked = bool(getattr(summary_result, "clicked", None))
    except ValueError as exc:
        if "is not registered" not in str(exc):
            raise
        render_trade_html(summary_html)
        summary_clicked = st.button(
            "View trade →",
            key=f"{summary_key}_open_fallback",
            help=f"View full trade details with {_safe_text(idea.get('partner_team_name'), 'trade partner')}",
            type="tertiary",
            width="content",
        )

    if summary_clicked is True:
        trade_detail_navigation.open_trade(st.session_state, summary_key)

    navigation = trade_detail_navigation.current(st.session_state)
    if navigation.trade_key == summary_key:
        dialog_state = st.session_state

        def _dismiss_trade_detail() -> None:
            trade_detail_navigation.close(dialog_state, summary_key)

        @st.dialog(
            _safe_text(idea.get("tag"), "Trade details"),
            width="large",
            dismissible=True,
            on_dismiss=_dismiss_trade_detail,
        )
        def _trade_detail_dialog() -> None:
            current_navigation = trade_detail_navigation.current(st.session_state)
            if current_navigation.showing_player and render_player_dossier is not None:
                st.button(
                    "← Back to trade",
                    key=trade_detail_navigation.control_key(summary_key, "back"),
                    type="tertiary",
                    use_container_width=False,
                    on_click=trade_detail_navigation.back_to_trade,
                    args=(st.session_state, summary_key),
                )
                render_player_dossier(
                    current_navigation.player_id,
                    source_label="Trade Hub",
                    source_note="Inspect this player without leaving the active trade.",
                )
                return

            my_mode = escape(_safe_text(
                idea.get("my_strategy"),
                tidy_label(_safe_text(idea.get("my_mode"), "unknown")),
            ))
            detail_html = textwrap.dedent(
                f"""
                <div class="trade-detail-modal" data-trade-detail-key="{summary_key}">
                    <div class="trade-card-partner">Trade with <strong>{partner}</strong> · {my_mode} lens</div>
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
                    <div class="trade-card-net-strip"><span>Estimated value difference</span><strong class="{delta_class}">{delta_text}</strong></div>
                    {brand_identity.trade_screenshot_brand_html(css_class="trade-detail-brand")}
                </div>
                """
            ).strip()
            clicked_player_id = render_trade_html_with_player_taps(
                detail_html,
                send_assets + receive_assets,
                key_prefix=f"{summary_key}_assets",
                source_label="Trade Hub",
                render_tappable_player_html=render_tappable_player_html,
                open_player_quick_view=(
                    None if render_player_dossier is not None else open_player_quick_view
                ),
            )
            if clicked_player_id and render_player_dossier is not None:
                trade_detail_navigation.open_player(
                    st.session_state,
                    trade_key=summary_key,
                    player_id=clicked_player_id,
                )
                st.rerun()
            target_reason = _safe_text(trade_target_reason(idea))
            partner_reason = _safe_text(trade_partner_reason(idea))
            confidence_reason = _safe_text(trade_confidence_reason(idea))
            value_summary = (
                f"{trade_value_verdict(trade_gain)} · Net {delta_text}"
            )
            evidence_parts = recommendation_trust_ux.dedupe_explanation_texts(
                (
                    partner_reason,
                    idea.get("trust_evidence_note"),
                )
            )
            supporting_metrics = recommendation_trust_ux.normalize_sentence(
                f"{fit} fit · {confidence} confidence · {market} market · "
                f"Send {format_score(send_score)} · Receive {format_score(receive_score)}"
            )
            health_context = injury_display_context(idea)
            risk_parts = recommendation_trust_ux.dedupe_explanation_texts(
                (
                    confidence_reason,
                    (
                        f"{health_context.get('label', 'Health watch')}: "
                        f"{health_context.get('note', '')}"
                        if health_context.get("risk")
                        else ""
                    ),
                )
            )
            explanation_html = recommendation_trust_ux.executive_trade_detail_html(
                {
                    "Reason": target_reason,
                    "Evidence": " ".join(evidence_parts),
                    "Risk": " ".join(risk_parts),
                    "Expected outcome": value_summary,
                    "Supporting metrics": supporting_metrics,
                },
                verdict=trade_value_verdict(trade_gain),
                value_delta=delta_text,
                confidence=f"{confidence} confidence",
            )
            render_html_fragment(explanation_html)
            # Health risk stays in the Risk row only — no duplicate st.warning.
            if render_detail_actions is not None:
                render_detail_actions(idea, f"{summary_key}_actions")

        with performance.time_block("trade_hub_detail_modal", category="render"):
            _trade_detail_dialog()


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
    render_player_dossier: Callable | None = None,
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
        render_player_dossier=render_player_dossier,
    )
    render_trade_idea_player_actions(
        idea,
        key_prefix=f"{key_prefix}_{idea_idx}",
        return_page="trade_hub",
        source_label="Trade Hub",
    )
