import textwrap
import time
from hashlib import sha256
from html import escape
from typing import Callable, Mapping, MutableMapping

import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitAPIException

from modules import brand_identity
from modules import (
    canonical_recommendation_narrative,
    deferred_rendering,
    football_assets,
    performance,
    trade_detail_navigation,
)
from modules import interaction_latency
from modules import premium
from modules import recommendation_trust_ux
from modules import ui_primitives
from modules.design_tokens import DESIGN_TOKEN_CSS
from modules.interaction_contract import TAP_DELEGATION_JS, on_clicked_change
from modules.player_images import get_player_image_url
from modules.html_rendering import inject_global_styles, render_html_fragment
from modules.page_shell import page_body

from modules.compact_fantasy_assets import COMPACT_FANTASY_ASSET_CSS, compact_asset_stack_html
from modules.football_asset_styles import FOOTBALL_ASSET_CSS
from modules.player_cards import (
    injury_adjusted_value_html,
    player_prestige_level,
    player_team_age_meta,
)
from modules.player_tier_identity import resolve_player_tier_identity
from modules.trade_visual_language import (
    exchange_marker_html,
    trade_value_band,
    value_edge_html,
    value_edge_lean_bar_html,
)
from modules.trade_detail_styles import TRADE_DETAIL_CSS
from modules.decision_surface_dialog_styles import DECISION_SURFACE_DIALOG_CSS
from modules.portrait_normalization import card_focus_x
from modules.semantic_glyphs import SEMANTIC_GLYPH_CSS, concept_for, glyph_html

TRADE_SUMMARY_COMPONENT_CSS = DESIGN_TOKEN_CSS + COMPACT_FANTASY_ASSET_CSS + SEMANTIC_GLYPH_CSS + FOOTBALL_ASSET_CSS + """
* { box-sizing: border-box; }
html, body, #trade-summary-tap-root { margin: 0; width: 100%; max-width: 100%; background: transparent; color: var(--color-text-primary); font-family: var(--font-family-sans); --dg-headshot-focus-x: FOCUS_X; --dg-headshot-focus: 18%; }
.trade-summary-card {
    background: var(--color-surface-primary);
    border: var(--border-width-default) solid var(--color-border-strong);
    border-left: var(--border-width-semantic) solid var(--color-information);
    box-sizing: border-box;
    color: var(--color-text-primary);
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
    max-width: 100%;
    min-height: var(--touch-target-min);
    min-width: 0;
    overflow: hidden;
    padding: var(--space-sm);
    width: 100%;
    container-type: inline-size;
    container-name: trade-summary;
}
.trade-summary-card--focused {
    border-left-color: var(--color-accent);
    box-shadow: inset var(--space-2xs) 0 0 var(--color-accent);
}
.trade-summary-card:hover { background: var(--color-surface-raised); border-color: var(--color-information); }
.trade-summary-card:focus-visible { box-shadow: var(--focus-ring); outline: none; }
.trade-summary-header { align-items: baseline; display: flex; flex-wrap: wrap; gap: var(--space-xs) var(--space-md); justify-content: flex-start; max-width: 100%; min-width: 0; order: 1; }
.trade-summary-heading { display: grid; gap: var(--space-xs); max-width: 100%; min-width: 0; }
.trade-summary-category {
    align-items: center;
    color: var(--color-text-muted);
    display: flex;
    font: var(--type-supporting-metadata);
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    gap: var(--space-xs);
    letter-spacing: var(--letter-spacing-badge);
    line-height: var(--line-height-badge);
    opacity: var(--opacity-secondary);
    text-transform: uppercase;
}
/* The category glyph is decorative (the label text already names the
   category); gap above already supplies spacing, so drop dg-glyph's own
   default margin-right to avoid doubling it. */
.trade-summary-category .dg-glyph { margin-right: 0; }
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
    font: var(--type-card-title);
    margin-top: 0;
    min-width: 0;
    overflow-wrap: break-word;
    white-space: normal;
    word-break: normal;
}
.trade-summary-title-row {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-xs);
    min-width: 0;
}
.trade-summary-fairness-pill { flex: 0 0 auto; }
.trade-summary-partner-kicker {
    color: var(--color-text-muted);
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}
.trade-summary-partner { color: var(--color-text-muted); flex: 0 0 auto; font: var(--type-supporting-metadata); }
.trade-summary-value-row {
    align-items: center;
    color: var(--color-text-muted);
    display: flex;
    flex-wrap: wrap;
    font-size: var(--font-size-caption);
    gap: var(--space-sm);
    justify-content: flex-start;
    max-width: 100%;
    min-width: 0;
    order: 2;
}
.trade-summary-value-row .tvl-edge { column-gap: var(--space-sm); }
.trade-summary-value-row .tvl-edge-num { font: var(--type-primary-metric); }
.trade-summary-value-row .tvl-edge-cap { display: none; }
/* Shape reinforcement of the Balance number directly above — same order as
   the value row so it reads as one continuous statement before the package. */
.trade-summary-lean-row { order: 2; }
.trade-summary-package { border-block: var(--border-width-default) solid var(--color-border); display: grid; gap: var(--space-xs); grid-template-columns: minmax(0, 1fr); max-width: 100%; order: 3; overflow-x: clip; padding-block: var(--space-xs); width: 100%; }
.trade-summary-for { align-items: center; color: var(--color-information); display: flex; font: var(--type-supporting-metadata); justify-content: flex-start; letter-spacing: var(--letter-spacing-badge); text-transform: uppercase; }
.trade-summary-side { align-items: start; display: grid; gap: var(--space-2xs); grid-template-columns: minmax(0, 1fr); justify-content: start; min-width: 0; }
.trade-summary-assets .dg-compact-asset--standard,.trade-summary-assets .dg-compact-asset--compact{--size-asset-standard:var(--size-asset-compact);align-items:center;column-gap:var(--space-xs);grid-template-columns:var(--size-asset-compact) minmax(0,1fr);max-width:100%;width:100%}
.trade-summary-assets .dg-compact-asset-stack{align-items:stretch;display:flex;flex-direction:column;gap:var(--space-2xs);max-width:100%;width:100%}
.trade-summary-assets .dg-compact-asset{max-width:100%;min-width:0;width:100%}
.trade-summary-assets .dg-compact-asset-avatar,.trade-summary-assets .dg-compact-pick-plate{flex:0 0 var(--size-asset-compact);max-width:var(--size-asset-compact);min-width:var(--size-asset-compact);width:var(--size-asset-compact)}
.trade-summary-assets .dg-compact-asset-copy{max-width:100%;min-width:0}
.trade-summary-assets .dg-compact-asset-name{overflow-wrap:anywhere;white-space:normal;word-break:normal}
.trade-summary-side-label .tvl-count{display:none}
.trade-summary-package > .trade-summary-side:first-child { border-inline-start: var(--border-width-semantic) solid var(--color-danger); padding-inline-start: var(--space-xs); }
.trade-summary-package > .trade-summary-side:last-child { border-inline-start: var(--border-width-semantic) solid var(--color-success); padding-inline-start: var(--space-xs); }
.trade-summary-side + .trade-summary-side { border-top: 0; margin-top: 0; padding-top: 0; }
.trade-summary-assets { display: block; min-width: 0; width: 100%; max-width: 100%; }
.trade-summary-asset-chip { align-items: center; display: inline-flex; gap: var(--space-xs); min-width: 0; }
.trade-summary-avatar {
    align-items: center;
    background: var(--color-surface-muted);
    border: var(--border-width-default) solid var(--color-border);
    display: inline-flex;
    flex: 0 0 2.75rem;
    height: 2.75rem;
    justify-content: center;
    overflow: hidden;
    padding: 0;
    position: relative;
    width: 2.75rem;
}
.trade-summary-avatar .dg-player-headshot,
.trade-summary-avatar .dg-player-headshot-image,
.trade-summary-avatar img { height: 100%; inset: 0; object-fit: cover; object-position: var(--dg-headshot-focus-x, FOCUS_X) var(--dg-headshot-focus, 18%); position: absolute; transform: scale(1.16); transform-origin: var(--dg-headshot-focus-x, FOCUS_X) var(--dg-headshot-focus, 18%); width: 100%; z-index: 1; }
.trade-summary-avatar .dg-player-headshot-fallback {
    align-items: center;
    color: var(--color-text-secondary);
    display: flex;
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    inset: 0;
    justify-content: center;
    position: absolute;
    z-index: 0;
}
.trade-summary-avatar:has(img.dg-player-headshot-image) .dg-player-headshot-fallback,
.trade-summary-avatar:has(.dg-player-headshot-image.is-loaded) .dg-player-headshot-fallback {
    opacity: 0;
    visibility: hidden;
}
.trade-summary-avatar--pick { color: var(--color-information); font-size: var(--font-size-badge); font-weight: var(--font-weight-title); }
.trade-summary-asset-name { color: var(--color-text-primary); font-size: var(--font-size-body); font-weight: var(--font-weight-title); max-width: 100%; min-width: 0; overflow: visible; overflow-wrap: break-word; text-overflow: clip; white-space: normal; word-break: normal; }
.trade-delta-positive { color: var(--color-success); }
.trade-delta-negative { color: var(--color-danger); }
.trade-delta-neutral { color: var(--color-text-secondary); }
.trade-summary-signals { display: flex; flex-wrap: wrap; gap: var(--space-xs); order: 4; }
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
.trade-summary-secondary {
    color: var(--color-text-muted);
    display: grid;
    gap: var(--space-2xs);
    font: var(--type-supporting-metadata);
    line-height: var(--line-height-caption);
    margin: 0;
    max-width: 100%;
    opacity: 0.82;
    order: 4;
}
.trade-summary-confidence-note {
    color: var(--color-text-muted);
    font: var(--type-supporting-metadata);
    line-height: var(--line-height-caption);
    margin: 0;
    max-width: 100%;
    order: 6;
    overflow-wrap: anywhere;
    white-space: normal;
}
.trade-summary-impact-row {
    align-items: baseline;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-sm);
    justify-content: flex-start;
    max-width: 100%;
    min-width: 0;
}
.trade-summary-impact-row .trade-summary-value {
    flex: 0 1 auto;
    gap: var(--space-sm);
    justify-content: flex-start;
}
.trade-summary-impact-row .dg-ui-badge { opacity: 0.72; }
.trade-summary-signals--quiet {
    opacity: 0.7;
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
    align-items: center;
    color: var(--color-text-primary);
    display: flex;
    font-size: var(--font-size-body);
    font-weight: var(--font-weight-button);
    gap: var(--space-xs);
    justify-content: space-between;
    letter-spacing: var(--letter-spacing-badge);
    text-align: left;
    text-transform: uppercase;
    width: 100%;
}
/* Same "tap this row" chevron already used for GM Sheet navigation rows
   (modules/mobile_interaction_overlay_styles.py, modules/app_styles.py) —
   reused here instead of inventing a second affordance convention, and
   it mirrors the chevron-forward Ionicon mobile puts on nearly every
   tappable row app-wide (MyTeamScreen, WaiverRecommendationCard,
   InsightRow, GmOrb's own destination rows, etc.) — this was the one
   tappable row on web's Trade Hub card without that cue. */
.trade-summary-affordance::after {
    color: var(--color-text-muted);
    content: "›";
    flex: 0 0 auto;
    font-size: 1rem;
    font-weight: 700;
}
.trade-summary-footer {
    align-items: center;
    border-top: var(--border-width-default) solid var(--color-border);
    display: flex;
    gap: var(--space-md);
    justify-content: flex-start;
    max-width: 100%;
    order: 7;
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
    background: var(--color-text-primary);
    color: var(--color-brand-mark-ink);
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
@container trade-summary (min-width: 520px) {
    .trade-summary-title { color: var(--color-text-muted); font-size: var(--font-size-body); font-weight: var(--font-weight-body); }
    .trade-summary-category { opacity: 0.78; }
    .trade-summary-assets .dg-compact-asset--compact,
    .trade-summary-assets .dg-compact-asset--standard {
        --size-asset-compact: 2.75rem;
        --size-asset-standard: 2.75rem;
        column-gap: var(--space-sm);
        grid-template-columns: 2.75rem minmax(0, 1fr);
        width: 100%;
    }
    .trade-summary-assets .dg-compact-asset-avatar,
    .trade-summary-assets .dg-compact-pick-plate {
        flex-basis: 2.75rem;
        height: 2.75rem;
        max-width: 2.75rem;
        min-width: 2.75rem;
        width: 2.75rem;
    }
    .trade-summary-assets .dg-compact-asset-name { font: var(--font-card-title); }
}
@container trade-summary (min-width: 700px) {
    .trade-summary-package { align-items: start; column-gap: var(--space-sm); grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); justify-content: stretch; max-width: 100%; width: 100%; }
    .trade-summary-for { align-self: center; display: flex; justify-content: center; }
    .trade-summary-side + .trade-summary-side { border-top: 0; margin-top: 0; padding-top: 0; }
    /* At this width the card is rendering on a desktop-class column, not a
       narrow phone-width one — the base rule's var(--space-sm) padding is
       the same tight value the <430px tier below uses for a phone-width
       card, so a desktop-wide card ends up reading thin/cramped relative
       to its own size (mobile's equivalent AnimatedCard uses spacing.lg,
       noticeably roomier). Step up one token on the existing scale rather
       than copying mobile's literal px value or touching the shared
       .dg-ui-card base rule other surfaces (summary-tile, explorer-pick-card,
       home-command-card) still rely on. */
    .trade-summary-card { padding: var(--space-md); }
}
@container trade-summary (max-width: 430px) {
    .trade-summary-card { gap: 0.22rem; max-width: 100%; min-height: 0; overflow-x: clip; padding: 0.45rem 0.65rem; width: 100%; }
    .trade-summary-for { display: flex; justify-content: flex-start; }
    .trade-summary-header { align-items: start; display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--space-2xs); max-width: 100%; }
    .trade-summary-category { display: block; overflow-wrap: anywhere; white-space: normal; }
    .trade-summary-rationale { display: none; }
    .trade-summary-confidence-note {
        display: block;
        overflow-wrap: anywhere;
        white-space: normal;
    }
    .trade-summary-title { margin-top: 0; max-width: 100%; overflow-wrap: anywhere; }
    .trade-summary-partner { margin-top: 0; max-width: 100%; text-align: left; }
    .trade-summary-value strong { font-size: var(--font-size-section-title); }
    .trade-summary-package { grid-template-columns: minmax(0, 1fr); max-width: 100%; overflow-x: clip; padding-block: 0.22rem; }
    .trade-summary-side { gap: var(--space-2xs); grid-template-columns: minmax(0, 1fr); min-width: 0; }
    .trade-summary-side + .trade-summary-side { margin-top: 0.22rem; padding-top: 0.22rem; }
    .trade-summary-assets { width: 100%; }
    .trade-summary-assets .dg-compact-asset-stack { display: flex; flex-direction: column; width: 100%; }
    .trade-summary-avatar { flex-basis: var(--size-asset-compact); height: var(--size-asset-compact); width: var(--size-asset-compact); }
    .trade-summary-signals { display: none; }
    .trade-summary-brand,
    .trade-summary-brand__name,
    .trade-summary-brand__badge { display: none; }
    .trade-summary-footer { gap: var(--space-xs); justify-content: flex-start; max-width: 100%; padding-top: 0.22rem; }
}
@container trade-summary (max-width: 340px) {
    .trade-summary-card { min-height: 0; }
    .trade-summary-header { grid-template-columns: minmax(0, 1fr); }
    .trade-summary-partner { max-width: 100%; text-align: left; }
    .trade-summary-title { font-size: var(--font-size-body); }
}
@media (prefers-reduced-motion: reduce) { .trade-summary-card { transition: none; } }
""".replace("FOCUS_X", card_focus_x())


TRADE_SUMMARY_TAP_COMPONENT = st.components.v2.component(
    "trade_summary_tap",
    html='<div id="trade-summary-tap-root"></div>',
    css=TRADE_SUMMARY_COMPONENT_CSS,
    js=TAP_DELEGATION_JS,
)


TRADE_SETUP_CAPTION = (
    "Strategy shapes which trades are generated · Evaluation changes how packages are scored"
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


def _team_name_from_summary(summary: pd.DataFrame, roster_id: str) -> str:
    if summary is None or getattr(summary, "empty", True) or "roster_id" not in summary.columns:
        return ""
    rid = str(roster_id or "").strip()
    if not rid:
        return ""
    matched = summary.loc[summary["roster_id"].astype(str) == rid]
    if matched.empty:
        return ""
    for column in ("team_name", "display_name", "owner_name"):
        if column not in matched.columns:
            continue
        name = str(matched.iloc[0].get(column) or "").strip()
        if name:
            return name
    return ""


def authenticated_team_display_name(
    session: MutableMapping | None = None,
    *,
    idea: Mapping | None = None,
    roster_id: str = "",
) -> str:
    """Resolve the signed-in roster's public team name. Not League Teams browse state."""

    payload = idea or {}
    named = str(payload.get("my_team_name") or "").strip()
    if named:
        return named
    state = session if session is not None else getattr(st, "session_state", {})
    rid = str(roster_id or "").strip() or str(state.get("my_roster_id") or "").strip()
    if not rid:
        return ""
    try:
        from modules import prepared_player_frame

        store = state.get(prepared_player_frame.SHARED_CONTEXT_KEY)
    except Exception:
        store = None
    frames: list[pd.DataFrame] = []
    if isinstance(store, dict):
        league_id = str(state.get("selected_league_id") or "").strip()
        for memo_key, item in store.items():
            if not isinstance(item, dict):
                continue
            summary = item.get("team_direction_summary")
            if not isinstance(summary, pd.DataFrame) or summary.empty:
                continue
            if not league_id or league_id in str(memo_key):
                frames.insert(0, summary)
            else:
                frames.append(summary)
    for summary in frames:
        found = _team_name_from_summary(summary, rid)
        if found:
            return found
    return ""


def _compact_copy(value: object, *, limit: int = 180, default: str = "") -> str:
    text = " ".join(_safe_text(value, default).split())
    if len(text) <= limit:
        return text
    return textwrap.shorten(text, width=limit, placeholder="...")


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
    compact: bool = False,
) -> dict:
    inject_global_styles(DECISION_SURFACE_DIALOG_CSS + TRADE_DETAIL_CSS)
    from modules import render_ownership

    render_ownership.claim(st.session_state, render_ownership.OWNER_TRADE_STRATEGY)
    auto_display = f"Auto · {automatic_strategy_label or 'Best guess'}"

    def _format_strategy(option: str) -> str:
        if str(option).startswith("Auto"):
            return auto_display
        return str(option)

    with st.container(key="trade_hub_controls"):
        strategy_cols = st.columns([4, 1], gap="small")
        with strategy_cols[0]:
            selected_label = st.selectbox(
                "Strategy",
                TRADE_STRATEGY_OPTIONS,
                key=key,
                format_func=_format_strategy,
            )
        with strategy_cols[1]:
            ui_primitives.render_auto_strategy_help(key=f"{key}_what_is_auto")
    resolved = resolve_trade_strategy_selection(
        selected_label,
        automatic_strategy=automatic_strategy,
        automatic_archetype=automatic_archetype,
    )
    if not compact:
        automatic_context = automatic_strategy_label
        if automatic_archetype:
            automatic_context += f" · {automatic_archetype}"
        if resolved["manual"]:
            st.caption(f"Strategy focus: {resolved['selection']}.")
        else:
            st.caption(f"{auto_display}.")
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
    if "confidence" not in confidence.casefold():
        confidence = f"{confidence} confidence"
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
    recommendation_narrative: Mapping | None = None,
    bridge_player_opens: bool = False,
    trade_key: str = "",
    render_interactive_html: Callable[..., dict] | None = None,
    route: str = "",
    route_label: str = "",
    on_route: Callable[[str], None] | None = None,
) -> str:
    """Render trade/visual HTML with player chips tappable into Quick View.

    ``render_interactive_html`` + ``route`` (coridian_, 2026-10-14) let a
    caller additionally make the WHOLE rendered block a single whole-card
    tap target (home-command-route-card contract) — e.g. Today's Game
    Plan's "Open Trade Hub"/"Open Waivers" cards — in the same render pass
    that already wires the player chips inside it, instead of a separate
    inert-HTML-plus-button pair. Falls back to the original player-chip-only
    behavior when ``render_interactive_html``/``route`` aren't supplied.
    """

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

    if render_interactive_html is not None and route:
        wrapped_html = (
            "<div class='home-command-route-card' "
            f"data-route='{escape(route, quote=True)}' role='button' tabindex='0' "
            f"aria-label='{escape(route_label or route, quote=True)}'>"
            f"{normalized_html}"
            "</div>"
        )
        clicked = render_interactive_html(
            html=wrapped_html,
            key_prefix=key_prefix,
            bridge_player_opens=bridge_player_opens,
            trade_key=trade_key,
            source_label=source_label,
        )
        clicked_player_id = (
            str(clicked.get("player_id") or "").strip() if isinstance(clicked, dict) else ""
        )
        clicked_route = (
            str(clicked.get("route") or "").strip() if isinstance(clicked, dict) else ""
        )
        if clicked_player_id in player_meta and open_player_quick_view is not None:
            meta = player_meta[clicked_player_id]
            open_kwargs = {
                "source_label": source_label,
                "source_note": (
                    canonical_recommendation_narrative.shorten_narrative_text(
                        (recommendation_narrative or {}).get("reason")
                        if isinstance(recommendation_narrative, Mapping)
                        else "",
                        160,
                    )
                    or f"Inspect {meta['name']} from this trade package."
                ),
                "status_label": (
                    _safe_text((recommendation_narrative or {}).get("action"))
                    if isinstance(recommendation_narrative, Mapping)
                    else ""
                )
                or meta["status"],
            }
            if recommendation_narrative is not None:
                open_kwargs["recommendation_narrative"] = recommendation_narrative
            open_player_quick_view(clicked_player_id, **open_kwargs)
            return clicked_player_id
        if clicked_route == route and on_route is not None:
            on_route(route)
        return ""

    if (
        not player_meta
        or render_tappable_player_html is None
    ):
        render_trade_html(normalized_html)
        return ""

    clicked_player_id = render_tappable_player_html(
        html=normalized_html,
        key_prefix=key_prefix,
        bridge_player_opens=bridge_player_opens,
        trade_key=trade_key,
        source_label=source_label,
    )
    if clicked_player_id in player_meta:
        meta = player_meta[clicked_player_id]
        if open_player_quick_view is not None:
            open_kwargs = {
                "source_label": source_label,
                "source_note": (
                    canonical_recommendation_narrative.shorten_narrative_text(
                        (recommendation_narrative or {}).get("reason")
                        if isinstance(recommendation_narrative, Mapping)
                        else "",
                        160,
                    )
                    or f"Inspect {meta['name']} from this trade package."
                ),
                "status_label": (
                    _safe_text((recommendation_narrative or {}).get("action"))
                    if isinstance(recommendation_narrative, Mapping)
                    else ""
                )
                or meta["status"],
            }
            if recommendation_narrative is not None:
                open_kwargs["recommendation_narrative"] = recommendation_narrative
            open_player_quick_view(clicked_player_id, **open_kwargs)
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
    compact: bool = False,
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
        image_url = ""
        if player_id:
            if compact:
                # Modal first paint must not wait on headshot byte fetch/base64.
                image_url = get_player_image_url(player_id)
            if not image_url:
                image_url = cached_headshot_data_url(player_id)
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
        # Colored position pill (mobile PlayerIdentityRow parity) — this is
        # what now lands inline in player_card_html's meta row via
        # position_html below, not a plain-text badge.
        position_badge = football_assets.position_badge_html(position)
        if compact:
            chips = []
            if health_context["risk"]:
                chips.append(player_support_chip_html(health_context["label"], "risk"))
            chip_row = f"<div class='trade-asset-tags'>{''.join(chips)}</div>" if chips else ""
            row_class += (
                f" trade-asset-row-player trade-asset-row-tone-{status_style['tone']} "
                "trade-asset-row-compact"
            )
            identity = " · ".join(
                part
                for part in (
                    position,
                    team,
                    f"Age {format_age(asset.get('age'))}" if format_age(asset.get("age")) else "",
                )
                if part
            )
            player_data_attr = (
                f" data-player-id='{escape(player_id, quote=True)}'" if player_id else ""
            )
            return (
                f"<div class='{row_class}'{player_data_attr}>"
                f"{avatar}"
                "<div class='trade-asset-copy'>"
                f"<div class='trade-asset-name'>{escape(display_label)}</div>"
                f"<div class='trade-asset-meta'>{escape(identity)}"
                f" · {injury_adjusted_value_html('Score', score, asset, css_class='trade-asset-value')}"
                "</div>"
                f"{chip_row}"
                "</div>"
                "</div>"
            )
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
            identity=resolve_player_tier_identity(asset),
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



PLAYER_SEARCH_EXPLORATORY_NOTE = (
    "Low confidence until a partner has a reason to move the target."
)
PLAYER_SEARCH_OTHER_NOTE = (
    "Expanded match. Confidence follows the package label."
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
    """Apply the post-Trust Trade Hub presentation contract.

    Ranking and Free gating operate on the already-approved candidate pool.
    Canonical league-format context, expired/completed-pick filtering, and
    redraft future-capital rules are owned upstream (`league_format_context`
    / Trust). This layer must not recreate those rules, invent replacements,
    or reintroduce removed ideas. It remains correct if the pool shrinks.
    """

    approved = list(primary_ideas or []) + list(secondary_ideas or [])
    ranked = order_trade_hub_visible_ideas(approved)
    approved_count = len(ranked)
    # Unlimited Trade Hub + trade ideas board is a GM Pro feature (Front
    # Office includes everything Pro has) — not Pro-exclusive.
    is_premium = premium.is_at_least(entitlement, premium.PRO)
    visible_ideas = ranked if is_premium else ranked[:FREE_VISIBLE_IDEAS]
    hidden_count = approved_count - len(visible_ideas)
    visible_labels = [
        str(idea.get("trade_confidence_label") or "").strip().casefold()
        for idea in visible_ideas
    ]
    only_low_confidence = bool(visible_labels) and all(
        label == "low" for label in visible_labels
    )
    return {
        "entitlement": premium.canonical_tier(entitlement) if is_premium else premium.FREE,
        "is_premium": is_premium,
        "approved_count": approved_count,
        "visible_ideas": visible_ideas,
        "visible_count": len(visible_ideas),
        "hidden_count": hidden_count,
        "show_board_upgrade": not is_premium and hidden_count > 0,
        "only_low_confidence": only_low_confidence,
    }


def trade_hub_entitlement_summary(
    presentation: dict,
    *,
    section_count: int,
) -> str:
    approved_count = int(presentation.get("approved_count") or 0)
    visible_count = int(presentation.get("visible_count") or 0)
    hidden_count = int(presentation.get("hidden_count") or 0)
    if approved_count == 1:
        return (
            "One trade currently clears FantasyGM Lab's approval threshold."
        )
    if presentation.get("is_premium"):
        return (
            f"Premium board: {approved_count} trade ideas in one ranked feed "
            f"({max(1, int(section_count))} categories). "
            "Category badges label each package; ordering is unchanged."
        )
    if hidden_count > 0:
        if presentation.get("only_low_confidence"):
            return (
                f"{visible_count} of {approved_count} trade ideas. "
                "You're seeing the strongest available recommendations; "
                "confidence is limited on this board."
            )
        return (
            f"{visible_count} of {approved_count} trade ideas. "
            "You're seeing the top recommendations."
        )
    return (
        f"Showing all {approved_count} "
        f"{'trade idea' if approved_count == 1 else 'trade ideas'} available here. "
        "Nothing is hidden on Free for this board."
    )


def split_player_search_ideas(
    ideas: list | None,
) -> tuple[list, list, list]:
    best: list = []
    other: list = []
    exploratory: list = []
    for idea in list(ideas or []):
        source = str(idea.get("hub_search_source") or "primary")
        if source == "exploratory" or bool(idea.get("hub_exploratory")):
            exploratory.append(idea)
        elif source == "expanded":
            other.append(idea)
        else:
            best.append(idea)
    return best, other, exploratory


def present_player_search_ideas(ideas: list | None) -> dict:
    """Player-search display contract. Does not require headline-ready or primary tier."""

    ordered = list(ideas or [])
    best, other, exploratory = split_player_search_ideas(ordered)
    return {
        "best": best,
        "other": other,
        "exploratory": exploratory,
        "visible_ideas": ordered,
        "visible_count": len(ordered),
        "show_empty": not (best or other or exploratory),
    }


def player_search_focal_on_expected_side(
    idea: Mapping | None,
    *,
    player_id: str,
    mode: str,
) -> bool:
    """Confirm the focused player stays on the searched side after presentation."""

    selected = str(player_id or "").strip()
    if not selected or not isinstance(idea, Mapping):
        return False
    send_ids = {
        str(asset.get("player_id") or "").strip()
        for asset in (idea.get("send_assets") or [])
        if isinstance(asset, Mapping)
    }
    receive_ids = {
        str(asset.get("player_id") or "").strip()
        for asset in (idea.get("receive_assets") or [])
        if isinstance(asset, Mapping)
    }
    mode_key = str(mode or "").strip().lower()
    if mode_key == "my_player":
        return selected in send_ids
    if mode_key == "target_player":
        return selected in receive_ids
    return False


FREE_VISIBLE_IDEAS = 2
FEATURED_DIVERSITY_SLOTS = 2
TRADE_HUB_FREE_GATE_TITLE = "Unlock the full Trade Board"
TRADE_HUB_FREE_GATE_BODY = (
    "Premium unlocks the rest of this ranked board so you can compare more "
    "partners and packages."
)
TRADE_HUB_FREE_GATE_CTA = "Unlock full Trade Board"
LOW_CONFIDENCE_USER_NOTE = (
    "More dependent on partner preference and market fit."
)
TRADE_HUB_ORDERING_CAPTION = (
    "Ordered by overall trade quality: roster fit, partner plausibility, "
    "value, and confidence. Market balance is one ingredient, not the sort."
)
TRADE_BOARD_EDUCATION = (
    "Confidence reflects how believable the path looks — fit, partner "
    "motivation, and market — not a guarantee. Value change shows whether "
    "the package favors your side."
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
    if int(presentation.get("visible_count") or 0) > 0:
        with st.expander("How this board is ranked", expanded=False):
            st.caption(TRADE_HUB_ORDERING_CAPTION)
            st.caption(TRADE_BOARD_EDUCATION)


def trade_hub_locked_preview_html(hidden_count: int) -> str:
    """Abstract remaining-count teaser. Does not reveal Premium recommendation data."""

    remaining = max(0, int(hidden_count or 0))
    if remaining <= 0:
        return ""
    slots = min(3, remaining)
    bars = "".join(
        "<div class='trade-hub-locked-row' aria-hidden='true'>"
        "<span></span><span></span><span></span>"
        "</div>"
        for _ in range(slots)
    )
    label = f"{remaining} more idea" if remaining == 1 else f"{remaining} more ideas"
    return (
        "<div class='trade-hub-locked-preview'>"
        f"<p class='trade-hub-locked-label'>{escape(label)} behind Premium</p>"
        f"{bars}"
        "</div>"
    )


def render_trade_hub_free_gate(presentation: dict) -> None:
    """Conversion moment immediately after the Free teaser cards."""

    if not presentation.get("show_board_upgrade"):
        return
    html = trade_hub_locked_preview_html(int(presentation.get("hidden_count") or 0))
    if html:
        render_html_fragment(html)


def _trade_idea_identity(idea: dict) -> tuple:
    """Package identity: within-side asset order does not create a second idea."""

    return canonical_recommendation_narrative.trade_idea_identity_tuple(idea)


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
    # Mobile's TradeIdeaCard renders every send/receive asset through the
    # shared, flippable `PlayerCard` (coridian_'s own spec for it: "incorporate
    # the prestige around the border... put an overall in the top right
    # corner") directly on the scannable feed card, not behind a tap — a
    # tier-colored portrait ring plus a colored position pill, always visible.
    # This summary card previously rendered its assets through the same
    # `compact_asset_stack_html` primitive but without `avatar_ring`/
    # `position_pill` (both already opt-in flags this exact function exposes,
    # already used by game_plan_trade_visual_html/game_plan_top_priority_
    # trade_html), so player identity read flatter here than it does in the
    # app or in web's own tap-through detail dialog (whose full
    # `football_assets.player_card_html` rows already resolve the real
    # per-player tier color via `resolve_player_tier_identity`).
    #
    # `show_overall_rating=True` closes the last gap with mobile's spec above:
    # each player asset already carries an `overall_rating` field all the way
    # from trade_hub_engine.generate_trade_idea_records (coridian_'s OVR
    # comment there) through trade_ideas._player_asset and
    # compact_fantasy_assets.presentation_asset — it just was not rendered
    # here yet. Picks never carry this field, so they render unchanged.
    # coridian_ 2026-10-14 (Trade Ideas feedback): "for trade ideas, I would
    # like the overall to be on the player card" — the pick-value half of
    # that same feedback ("the value of pics... I don't know how we wanna do
    # that") is a deliberately open product question, not implemented here.
    return (
        "<div class='trade-summary-assets'>"
        + compact_asset_stack_html(
            assets,
            size="standard",
            show_value=False,
            show_role=False,
            position_pill=True,
            avatar_ring=True,
            show_overall_rating=True,
        )
        + "</div>"
    )


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


def trade_summary_card_category(idea: dict) -> str:
    """Category rendered above YOU SEND / YOU GET on the trade-summary card.

    Explicit Search Around / League Target ideas recompute this at render time so
    a cached ``_display_section``, leftover Health Relief tag, or generic
    "healthy help" phrase cannot freeze the automatic-board taxonomy onto the card.
    """

    if is_explicit_player_search_idea(idea):
        if _explicit_search_injury_relief_allowed(idea):
            return "Health Relief"
        return ""
    annotated = _safe_text(idea.get("_display_section"))
    if annotated:
        return annotated
    return trade_hub_display_section(idea)


_TRADE_FAIRNESS_BAND_TONE = {
    "favorable": "success",
    "fair": "neutral",
    "slight overpay": "caution",
    "major overpay": "danger",
}


def trade_fairness_pill_html(delta_text: object) -> str:
    """Scannable fairness verdict badge, decoupled from the raw value-edge color.

    Pass the same formatted delta string given to ``value_edge_html`` so the
    two never disagree on the band. The badge's tone is chosen from the band
    itself (Favorable/Fair/Slight Overpay/Major Overpay) rather than the
    number's raw sign, so a marginally positive "Fair" trade doesn't read as
    success-green and a marginally negative "Slight Overpay" doesn't read as
    danger-red.
    """

    band = trade_value_band(delta_text)
    tone = _TRADE_FAIRNESS_BAND_TONE.get(band.strip().casefold(), "neutral")
    return (
        f"<span class='dg-ui-badge dg-ui-badge--{tone} trade-summary-fairness-pill' "
        f"aria-label='Trade fairness: {escape(band, quote=True)}'>{escape(band)}</span>"
    )


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

    def _presentation_key(idea: dict) -> tuple:
        return (
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


def apply_handoff_recommendation(
    ideas: list[dict] | None,
    recommendation_id: str,
) -> tuple[list[dict], str]:
    """Pin a handed-off recommendation first without regenerating ideas.

    Returns ``(ideas, status)`` where status is ``absent``, ``focused``, or
    ``stale``. Stale means the identity is no longer in the current Trust board.
    """

    ranked = list(ideas or [])
    rec_id = _safe_text(recommendation_id)
    if not rec_id:
        return ranked, "absent"
    match_index = next(
        (
            index
            for index, idea in enumerate(ranked)
            if idea_recommendation_id(idea) == rec_id
        ),
        None,
    )
    if match_index is None:
        return ranked, "stale"
    if match_index > 0:
        ranked.insert(0, ranked.pop(match_index))
    return ranked, "focused"


def revalidate_handoff_candidate(
    ideas: list[dict] | None,
    recommendation_id: str,
    handoff_idea: Mapping | None,
    *,
    validator: Callable[[list[dict]], list[dict]],
) -> tuple[list[dict], str]:
    """Resolve an omitted Dashboard package through current canonical guards."""

    current = list(ideas or [])
    rec_id = _safe_text(recommendation_id)
    if not rec_id:
        return current, "absent"
    if any(idea_recommendation_id(idea) == rec_id for idea in current):
        return current, "focused_current"
    if (
        not isinstance(handoff_idea, Mapping)
        or canonical_recommendation_narrative.trade_recommendation_id(handoff_idea)
        != rec_id
    ):
        return current, "stale"
    validated = list(validator([dict(handoff_idea)]) or [])
    match = next(
        (idea for idea in validated if idea_recommendation_id(idea) == rec_id),
        None,
    )
    if match is None:
        return current, "stale"
    return [match] + current, "focused_revalidated"


def resolve_handoff_trade_detail(
    ideas: list[dict] | None,
    recommendation_id: str,
    *,
    page_context: str,
) -> tuple[list[dict], str, str]:
    """Resolve one canonical handoff to the real feed card identity."""

    ranked, status = apply_handoff_recommendation(ideas, recommendation_id)
    if status != "focused" or not ranked:
        return ranked, status, ""
    return (
        ranked,
        status,
        trade_summary_key(
            ranked[0],
            page_context=page_context,
            instance_token=0,
        ),
    )


def handoff_stale_copy() -> str:
    return (
        "That trade is no longer a current recommendation. "
        "Showing the best available Trade Hub ideas."
    )


def trade_hub_empty_state_copy(active_section: str = "") -> dict[str, str]:
    section = _safe_text(active_section)
    if section:
        return {
            "title": f"No {section.lower()} trades right now",
            "reason": "No trade looks fair enough for both sides in this view right now.",
            "suggestion": "Try a different strategy focus, or search around one of your players.",
        }
    return {
        "title": "No trade ideas right now",
        "reason": "No trade looks fair enough for both sides right now.",
        "suggestion": "Try a different strategy focus, or search around one of your players.",
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
    compact_assets_html: Callable | None = None,
    key_prefix: str = "trade_idea",
    render_tappable_player_html: Callable | None = None,
    open_player_quick_view: Callable | None = None,
    render_player_dossier: Callable | None = None,
    render_detail_actions: Callable[[dict, str], None] | None = None,
) -> None:
    """Render a compact summary and lazily mount the complete trade dossier."""
    inject_global_styles(DECISION_SURFACE_DIALOG_CSS + TRADE_DETAIL_CSS)

    summary_key = trade_summary_key(
        idea,
        page_context=key_prefix,
        instance_token=idea_idx,
    )
    active_trade_key = trade_detail_navigation.current(st.session_state).trade_key
    if active_trade_key and active_trade_key != summary_key:
        return

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
    category_raw = trade_summary_card_category(idea)
    section = escape(category_raw)
    # Mobile's Trade Hub pairs every category/impact tag with a small icon
    # (ImpactBadge's flash/trending icons, the summary-row tiles) — web's
    # category line was text-only. Reuse the existing restrained glyph set
    # (modules/semantic_glyphs.py) instead of inventing new iconography;
    # decorative only, the label text still carries the information.
    category_glyph_html = (
        glyph_html(concept_for(category_raw), size="kicker") if category_raw else ""
    )

    if trade_gain > 0:
        delta_text = f"+{format_score(trade_gain)}"
    elif trade_gain < 0:
        delta_text = f"-{format_score(abs(trade_gain))}"
    else:
        delta_text = "Even"

    # show_magnitude_mark=False: the lean bar below already renders this same
    # magnitude signal as a full track+fill bar directly under this badge, so
    # the badge's own inline mark would be a second, visually conflicting bar
    # stacked on top of it rather than one coherent meter.
    edge_html = value_edge_html(delta_text, show_magnitude_mark=False)
    # send_score/receive_score (my_score/their_score) are the full,
    # untruncated per-side totals trade_gain is itself derived from — see
    # modules/trade_ideas.py's _make_idea. Web renders directly from this
    # dict, unlike mobile's API response (compact_package truncates each
    # side to 3 assets before scoring reaches the client), so this bar can
    # use the real split instead of mobile's net-delta-only approximation.
    lean_bar_html = value_edge_lean_bar_html(send_score, receive_score)
    narrative = canonical_recommendation_narrative.build_trade_narrative(
        idea,
        league_id=_safe_text(idea.get("_narrative_league_id") or st.session_state.get("selected_league_id")),
        roster_id=_safe_text(idea.get("_narrative_roster_id") or st.session_state.get("my_roster_id")),
        valuation_lens=_safe_text(idea.get("_narrative_valuation_lens")),
        source_surface="trade_hub",
        target_reason=_safe_text(trade_target_reason(idea)),
        partner_reason=_safe_text(trade_partner_reason(idea)),
        confidence_reason=_safe_text(trade_confidence_reason(idea)),
        confidence_label=_safe_text(confidence),
        value_verdict=_safe_text(trade_value_verdict(trade_gain)),
        value_delta=delta_text,
        health_context=injury_display_context(idea),
    )
    narrative_payload = narrative.to_dict()
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
    idea_rec_id = idea_recommendation_id(idea)
    league_id = _safe_text(st.session_state.get("selected_league_id"))
    handoff_id = _safe_text(
        st.session_state.get(f"trade_hub_focus_recommendation_id_{league_id}")
    )
    focused = bool(handoff_id and idea_rec_id == handoff_id)
    focused_class = " trade-summary-card--focused" if focused else ""
    focus_kicker = (
        "<div class='trade-summary-category'>Continuing your top trade</div>"
        if focused
        else ""
    )
    # Header hierarchy: recommendation type (category) leads, then team name
    # paired with a fairness verdict pill, then the value-change number gets
    # its own prominent row before the send/receive package — mirroring the
    # mobile Trade Hub redesign's card order (category -> team+fairness pill
    # -> value-change number) instead of burying the verdict below the assets.
    # Derive the pill from the same formatted delta_text that value_edge_html
    # buckets internally, so the two never disagree on the band for one idea.
    #
    # V2 architecture reset (UI_V2_ARCHITECTURE_RESET.md): the Magna Carta's
    # own Trade Hub example (§4) and Trade UI spec (§30) both put rationale
    # ("why does it work") ahead of confidence/realism ("how realistic is
    # it"). The prior pass demoted confidence below the send/receive package
    # but left it ahead of the "why" cue, which still inverted that order.
    # Below, the why cue is emitted (and CSS-ordered) before the confidence
    # block so a reader sees the reasoning before the confidence verdict,
    # matching partner -> assets -> value -> reasoning -> confidence -> action.
    fairness_pill_html = trade_fairness_pill_html(delta_text)
    # Risk flag, not an analytics score — kept visible on the quick-view card
    # even after the confidence/realism gauges and "why" rationale moved to
    # the tap-through detail only (coridian_, 2026-10-13: quick views should
    # show identity + headline verdict, full analysis behind the tap). A
    # genuinely low-confidence trade still needs to read as risky at a
    # glance; see test_low_confidence_note_is_on_cards_and_kept_on_mobile.
    confidence_note_html = ""
    if _safe_text(idea.get("trade_confidence_label")).strip().casefold() == "low":
        confidence_note_html = (
            f"<p class='trade-summary-confidence-note'>{escape(LOW_CONFIDENCE_USER_NOTE)}</p>"
        )
    summary_html = textwrap.dedent(
        f"""
        <article class="trade-summary-card dg-ui-card dg-ui-card--elevated{tone_class}{secondary_class}{focused_class}" data-trade-summary-key="{summary_key}" data-recommendation-id="{escape(idea_rec_id, quote=True)}" aria-label="View trade details: {tag} with {partner}">
            <header class="trade-summary-header">
                <div class="trade-summary-heading">
                    {focus_kicker}
                    <div class="trade-summary-category">{category_glyph_html}{section}</div>
                    <div class="trade-summary-title-row">
                        <div class="trade-summary-title">{partner}</div>
                        {fairness_pill_html}
                    </div>
                </div>
            </header>
            <div class="trade-summary-value-row"><span class="trade-summary-side-label">Balance</span>{edge_html}</div>
            <div class="trade-summary-lean-row">{lean_bar_html}</div>
            <div class="trade-summary-package">
                <div class="trade-summary-side" data-trade-chrome="1"><span class="trade-summary-side-label">You send</span>{_trade_summary_assets_html(send_assets)}</div>
                <div class="trade-summary-for" data-trade-chrome="1" aria-hidden="true">{exchange_marker_html()}</div>
                <div class="trade-summary-side" data-trade-chrome="1"><span class="trade-summary-side-label">You get</span>{_trade_summary_assets_html(receive_assets)}</div>
            </div>
            {confidence_note_html}
            <div class="trade-summary-footer">
                <div class="trade-summary-affordance" aria-hidden="true">Review package</div>
            </div>
        </article>
        """
    ).strip()
    try:
        summary_result = TRADE_SUMMARY_TAP_COMPONENT(
            key=f"{summary_key}_open",
            data={
                "html": normalize_trade_html(summary_html),
                "key": summary_key,
                "rootId": "trade-summary-tap-root",
                "bridgePlayerOpens": True,
                "tradeKey": "",
                "sourceLabel": "Trade Hub",
            },
            width="stretch",
            height="content",
            on_clicked_change=on_clicked_change,
        )
        clicked_payload = getattr(summary_result, "clicked", None)
        clicked_kind = ""
        clicked_player = ""
        if isinstance(clicked_payload, dict):
            clicked_kind = str(clicked_payload.get("kind") or "").strip().lower()
            clicked_player = str(clicked_payload.get("player_id") or "").strip()
            if not clicked_kind and clicked_payload.get("open"):
                clicked_kind = "trade"
            if not clicked_kind and clicked_payload.get("key"):
                clicked_kind = "trade"
        summary_clicked = clicked_kind == "trade" and not clicked_player
        if clicked_player and open_player_quick_view is not None:
            open_player_quick_view(
                clicked_player,
                source_label="Trade Hub",
                source_note=narrative.shorten("reason", 160)
                or "Inspect this player from the trade package.",
                recommendation_narrative=narrative_payload,
            )
            trade_detail_navigation.close(st.session_state, summary_key)
    except (ValueError, StreamlitAPIException) as exc:
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
        st.session_state["_trade_modal_t0"] = time.perf_counter()
        canonical_recommendation_narrative.bind_narrative(
            st.session_state,
            narrative,
        )
        trade_detail_navigation.open_trade(st.session_state, summary_key)
        try:
            from modules import launch_analytics

            launch_analytics.track_event(
                "trade_review_opened",
                props=launch_analytics.build_context_props(
                    st.session_state,
                    route="trade_hub",
                    source_surface="trade_hub_card",
                ),
                state=st.session_state,
            )
        except Exception:
            pass
    navigation = trade_detail_navigation.current(st.session_state)
    if navigation.trade_key == summary_key:
        # Keep Trade Review / detail provenance aligned with this card's idea.
        canonical_recommendation_narrative.bind_narrative(
            st.session_state,
            narrative,
        )
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
            from modules.share_recommendation_cards import in_app_trade_side_labels as _side_labels

            mine = authenticated_team_display_name(st.session_state, idea=idea)
            send_label, receive_label = _side_labels(
                my_team_name=mine,
                partner_name=_safe_text(idea.get("partner_team_name")),
            )
            package_html = compact_assets_html or assets_html
            detail_html = textwrap.dedent(
                f"""
                <div class="trade-detail-modal trade-detail-modal--decision" data-trade-detail-key="{summary_key}">
                    {brand_identity.decision_surface_brand_html(css_class="trade-detail-brand")}
                    <div class="trade-card-partner">Trade with <strong>{partner}</strong></div>
                    <div class="trade-matchup trade-matchup-compact">
                        <section class="trade-side trade-side--send">
                            <div class="trade-side-header"><span>{escape(send_label)}</span><strong class="trade-side-value trade-value-send">{format_score(send_score)}</strong></div>
                            {package_html(send_assets)}
                        </section>
                        <div class="trade-vs trade-review-exchange-separator" role="separator" aria-label="Trade exchange">FOR<span aria-hidden="true"> ↓</span></div>
                        <section class="trade-side trade-side--receive">
                            <div class="trade-side-header"><span>{escape(receive_label)}</span><strong class="trade-side-value trade-value-receive">{format_score(receive_score)}</strong></div>
                            {package_html(receive_assets)}
                        </section>
                    </div>
                </div>
                """
            ).strip()
            clicked_player_id = render_trade_html_with_player_taps(
                detail_html,
                send_assets + receive_assets,
                key_prefix=f"{summary_key}_assets",
                source_label="Trade Hub",
                render_tappable_player_html=render_tappable_player_html,
                open_player_quick_view=open_player_quick_view,
                recommendation_narrative=narrative_payload,
                bridge_player_opens=True,
                trade_key=summary_key,
            )
            if not isinstance(clicked_player_id, str):
                clicked_player_id = ""
            if clicked_player_id:
                if open_player_quick_view is not None:
                    open_player_quick_view(
                        clicked_player_id,
                        source_label="Trade Hub",
                        source_note=narrative.shorten("reason", 160)
                        or "Inspect this player from the trade package.",
                        recommendation_narrative=narrative_payload,
                    )
                canonical_recommendation_narrative.bind_narrative(
                    st.session_state,
                    narrative,
                )
                trade_detail_navigation.close(st.session_state, summary_key)
                return
            explanation_fields = narrative.explanation_fields()
            market_copy = recommendation_trust_ux.normalize_sentence(
                f"{fit} fit · {market} market"
            )
            if market_copy:
                explanation_fields["Supporting metrics"] = market_copy
            interaction_latency.mark_interaction_milestone("trade_review_open_received")
            explanation_html = recommendation_trust_ux.executive_trade_detail_html(
                explanation_fields,
                verdict=trade_value_verdict(trade_gain),
                value_delta=delta_text,
                confidence=f"{confidence} confidence",
                include_supporting=True,
            )
            render_html_fragment(explanation_html)
            st.session_state["_trade_modal_t4"] = time.perf_counter()
            t0 = st.session_state.get("_trade_modal_t0")
            if t0:
                performance.record_timing(
                    "trade_modal_click_to_html",
                    (st.session_state["_trade_modal_t4"] - float(t0)) * 1000,
                    category="render",
                )
            interaction_latency.mark_interaction_milestone("trade_review_first_useful")
            try:
                from modules import share_recommendation_cards as share_cards
                from modules import share_recommendation_ui

                if share_cards.experiment_enabled():
                    share_card = share_cards.build_trade_share_card(
                        idea,
                        source_surface="trade_review",
                        my_team_name=authenticated_team_display_name(
                            st.session_state, idea=idea
                        ),
                    )
                    # Recommendation-clarity audit (UI_V2_ARCHITECTURE_RESET.md):
                    # Trade Hub has no in-app trade-submission API, so sending
                    # this card to the partner is the real, working action a
                    # user can take on a recommendation here — not just an
                    # export/screenshot convenience. Say that explicitly so the
                    # button doesn't read as a secondary, easy-to-skip extra.
                    st.caption(
                        "There's no in-app trade submission here — sharing "
                        "this card is how you actually send the offer to "
                        "your partner."
                    )
                    share_recommendation_ui.render_share_controls(
                        share_card,
                        key=f"{summary_key}_share",
                        state=st.session_state,
                        button_label=share_cards.TRADE_HUB_SHARE_LABEL,
                    )
                    # Additive growth card: both sides' value, an A-F
                    # letter grade, and who won — distinct from the trade
                    # idea card above (same underlying data, different
                    # fixed 1080x1350 presentation). Never gated by
                    # entitlement (modules.premium.can_export_share_card).
                    from modules import growth_share_cards

                    growth_share_cards.render_trade_grade_share_controls(
                        share_card,
                        key=f"{summary_key}_grade_share",
                        state=st.session_state,
                        source_surface="trade_review",
                    )
            except Exception:
                pass
            # Health risk stays in the Risk row only — no duplicate st.warning.
            if render_detail_actions is not None:
                render_detail_actions(idea, f"{summary_key}_actions")

        try:
            from modules import hot_path_profile as _hot_path
        except Exception:
            _hot_path = None
        with performance.time_block("trade_hub_detail_modal", category="render"):
            if _hot_path is not None:
                with _hot_path.span(
                    "trade_modal_dialog",
                    kind="render",
                    session_state=st.session_state,
                ):
                    _trade_detail_dialog()
            else:
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
    st.caption("Tap a player in the package to inspect. Shortcuts stay here.")
    render_player_detail_button_grid(
        player_rows,
        key_prefix=key_prefix,
        return_page=return_page,
        source_label=source_label,
        title="",
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
        ui_primitives.render_section_header(
            path,
            eyebrow="Trade path",
            heading_level=3,
        )
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


# Extracted from app.py's `if current_page == "trade_hub":` route-dispatch
# block (pure mechanical extraction -- no behavior change). Every keyword
# parameter below corresponds to a name the block previously read from
# app.py's main() local scope (route/session state, cached-frame locals,
# or app.py-local helper functions/closures that cannot be imported here
# without a circular import on app.py). The only non-literal change from
# the original inline code is that calls previously made as
# `trade_hub_ui.<name>(...)` are now unqualified `<name>(...)` calls, since
# this function now lives in the same module that defines those helpers.
def render_trade_hub_workspace(
    *,
    _format_rank,
    _render_player_search_empty_state,
    _render_player_search_founder_diagnostics,
    _render_player_search_grouped_cards,
    _route_body,
    _safe_text,
    _supabase_config,
    _trade_display_confidence_label,
    application_shell,
    apply_strategy_age_curve,
    cached_player_trade_hub_ideas,
    cached_trade_ideas,
    current_user_entitlement,
    current_user_is_premium,
    df_players,
    draft_pick_valuation_settings_items,
    enforce_cached_trade_ideas,
    enrich_trade_ideas_with_manager_tendencies,
    game_plan_package,
    game_plan_process_cache,
    get_shared_league_context,
    get_team_vs_league,
    guest_conversion,
    increment_session_counter,
    league_value_settings,
    league_value_settings_key,
    load_profile_key,
    my_roster_id,
    owner_handle,
    partial,
    pick_score_multiplier,
    player_display_name,
    player_trade_hub_option_label,
    player_trade_hub_selected_summary,
    prepared_frame_signature,
    prepared_player_frame,
    product_copy,
    recommendation_lifecycle,
    render_dense_metric_strip,
    render_onboarding_handoff,
    render_player_detail_button_grid,
    render_premium_lock,
    render_summary_tiles,
    render_trade_idea_card,
    render_trade_player_dossier_content,
    render_trade_return_explorer,
    render_workflow_continuity_bar,
    resolve_team_strategy,
    route_body_container,
    runtime_trace,
    score_field,
    scoring_rank_context,
    select_trade_hub_headline_idea,
    selected_league_id,
    selected_league_name,
    shell_chrome_schema,
    startup_mode,
    strategy_adjusted_pick_score_multiplier,
    team_stance,
    team_strategy_label,
    trade_hub_first_useful,
    username,
    valuation_archetype_ui,
    workspace_notices,
) -> None:
    with page_body("trade_hub_workspace", gap="md"):
        if st.session_state.pop("_pqv_trade_hub_nav", None):
            interaction_latency.mark_interaction_milestone("trade_hub_route_ready")
        trade_hub_first_useful.mark_trade_hub_milestone("trade_hub_nav_received")
        trade_hub_focus_player_id = (
            _safe_text(st.session_state.get(f"trade_hub_focus_player_id_{selected_league_id}")).strip()
            if selected_league_id
            else ""
        )
        trade_hub_focus_mode = (
            _safe_text(st.session_state.get(f"trade_hub_focus_mode_{selected_league_id}")).strip()
            if selected_league_id
            else ""
        )
        legacy_trade_hub_player_id = _safe_text(
            st.session_state.pop("trade_hub_player_id", None)
        ).strip()
        if selected_league_id and legacy_trade_hub_player_id and not trade_hub_focus_player_id:
            trade_hub_focus_player_id = legacy_trade_hub_player_id
            trade_hub_focus_mode = trade_hub_focus_mode or "target_player"
            st.session_state[f"trade_hub_focus_player_id_{selected_league_id}"] = (
                trade_hub_focus_player_id
            )
            st.session_state[f"trade_hub_focus_mode_{selected_league_id}"] = (
                trade_hub_focus_mode
            )
        # Page title and War Room context live in the executive command bar.
        render_workflow_continuity_bar(
            "trade_hub",
            selected_league_id=_safe_text(selected_league_id),
            extra_note=_safe_text(
                st.session_state.get(f"trade_hub_home_source_note_{selected_league_id}")
            ),
        )

        if startup_mode and selected_league_id:
            workspace_notices.render_startup_blocked_notice(
                "Trade discovery unlocks after the startup draft completes."
            )
        elif (
            st.session_state.get("active_platform") == "espn"
            and st.session_state.get("espn_limited_mode")
            and not selected_league_id
        ):
            render_trade_hub_section_header(
                "ESPN limited review mode",
                eyebrow="ESPN Import",
                subtitle="Trade Hub is gated for ESPN until free-agent, transaction, and trade partner paths are validated.",
            )
            st.markdown(
                "<div class='app-degraded-state'>Sleeper remains the full Trade Hub path. ESPN imports can currently show mapping review and limited status, but they do not yet unlock trade recommendations.</div>",
                unsafe_allow_html=True,
            )
        elif not username or not selected_league_id:
            render_onboarding_handoff(
                username=username,
                selected_league_id=selected_league_id,
                note="Import your Sleeper league to see trade ideas for your roster.",
            )
            _route_body.exit_route_body(route_body_container, st.session_state)
            st.stop()
        elif my_roster_id is None:
            workspace_notices.render_roster_mismatch_notice()
        else:
            # Board path does not consume league intelligence; keep Trust / roster /
            # maturity. Avoid rebuilding intel on cold Trade Hub after Dashboard.
            trade_hub_pending = st.empty()
            _trade_hub_warm = bool(
                st.session_state.get(prepared_player_frame.SHARED_CONTEXT_KEY)
            ) or game_plan_process_cache.process_league_context_warm()
            if not _trade_hub_warm:
                trade_hub_pending.markdown(
                    application_shell.surface_pending_html(
                        surface="Trade Hub",
                        league_name=_safe_text(selected_league_name, "your league"),
                        message="Loading trade paths for this league. Other destinations stay deferred.",
                    ),
                    unsafe_allow_html=True,
                )
            with trade_hub_first_useful.stage_timer("canonical_context_resolution"):
                from modules import hot_path_profile as _hot_path

                with _hot_path.span(
                    "trade_hub_shared_context",
                    kind="cpu",
                    session_state=st.session_state,
                ) as _th_ctx_meta:
                    trade_hub_context = get_shared_league_context(
                        include_intelligence=False,
                    )
                    _th_ctx_meta["cache_status"] = "resolved"
            trade_hub_first_useful.mark_trade_hub_milestone("trade_hub_context_ready")
            trade_hub_pending.empty()
            df_summary = trade_hub_context.get("team_direction_summary", pd.DataFrame())
            hub_display = trade_hub_context.get("league_detail_ranks", pd.DataFrame())
            roster_profiles = trade_hub_context.get("roster_profiles", {})
            roster_player_map = trade_hub_context.get("roster_player_map", {})
            profile = load_profile_key(username, selected_league_id)
            untouchables = profile.get("untouchables", [])
            role_map = st.session_state.get("role_map", {})
            with trade_hub_first_useful.stage_timer("roster_team_context"):
                metrics = get_team_vs_league(df_summary, my_roster_id)
                _, automatic_trade_hub_strategy, _ = resolve_team_strategy(metrics, profile)
            automatic_trade_hub_archetype = _safe_text(
                (metrics or {}).get("archetype_label")
                or (metrics or {}).get("archetype")
            )
            # Compact Trade setup: strategy + evaluation before first recommendation.
            with st.container(key="trade_hub_setup"):
                setup_cols = st.columns(2, gap="small")
                with setup_cols[0]:
                    trade_hub_lens = render_trade_strategy_selector(
                        automatic_strategy=automatic_trade_hub_strategy,
                        automatic_strategy_label=team_strategy_label(automatic_trade_hub_strategy),
                        automatic_archetype=automatic_trade_hub_archetype,
                        key=f"trade_hub_strategy_lens_{selected_league_id}_{my_roster_id}",
                        compact=True,
                    )
                with setup_cols[1]:
                    valuation_archetype_ui.render_evaluation_lens_control(
                        key=f"trade_hub_evaluate_{selected_league_id}",
                        label="Evaluation",
                        container_key="trade_hub_valuation_lens",
                        show_generation_disclaimer=False,
                        compact=True,
                    )
                st.caption(TRADE_SETUP_CAPTION)
            trade_hub_strategy = trade_hub_lens["strategy"]
            trade_hub_archetype = trade_hub_lens["archetype"]
            trade_hub_lens_label = (
                trade_hub_lens["selection"]
                if trade_hub_lens["manual"]
                else (
                    f"Auto · {team_strategy_label(trade_hub_strategy)}"
                    + (
                        f" · {automatic_trade_hub_archetype}"
                        if automatic_trade_hub_archetype
                        else ""
                    )
                )
            )
            trade_hub_first_useful.mark_trade_hub_milestone("trade_hub_strategy_ready")
            strategy_frame_signature = trade_hub_first_useful.build_strategy_frame_signature(
                frame_signature=prepared_frame_signature,
                strategy=trade_hub_strategy,
                score_field=score_field,
            )
            with trade_hub_first_useful.stage_timer("strategy_lens_resolution"):
                trade_hub_df, _strategy_frame_hit = trade_hub_first_useful.get_or_build_strategy_frame(
                    st.session_state,
                    signature=strategy_frame_signature,
                    builder=lambda: apply_strategy_age_curve(
                        df_players, trade_hub_strategy, score_field
                    ),
                )
            trade_hub_pick_multiplier = strategy_adjusted_pick_score_multiplier(
                pick_score_multiplier,
                trade_hub_strategy,
            )
            trade_player_dossier_renderer = partial(
                render_trade_player_dossier_content,
                df_players=df_players,
                username=username,
                selected_league_id=selected_league_id,
                my_roster_id=my_roster_id,
                league_settings=league_value_settings,
                score_field=score_field,
                active_team_strategy=trade_hub_strategy,
                pick_score_multiplier=trade_hub_pick_multiplier,
            )
            my_player_ids = {
                str(pid)
                for pid in roster_player_map.get(str(my_roster_id), ())
                if pid is not None
            }
            runtime_trace.count("ownership_map_construction")
            owned_player_to_roster = {
                str(pid): roster_id
                for roster_id, player_ids in roster_player_map.items()
                for pid in player_ids
                if pid is not None
            }
            trade_hub_untouchables_key = tuple(sorted(str(name) for name in untouchables))
            trade_hub_role_items = tuple(
                sorted((str(pid), str(role)) for pid, role in role_map.items())
            )
            trade_hub_entitlement = current_user_entitlement()
            lifecycle_fp = recommendation_lifecycle.load_context_fingerprint(st.session_state)
            presentation_board_signature = (
                trade_hub_first_useful.build_presentation_board_signature(
                    lifecycle_digest=_safe_text(
                        getattr(lifecycle_fp, "digest", "") if lifecycle_fp else ""
                    ),
                    account_scope=_safe_text(
                        getattr(lifecycle_fp, "account_scope", "") if lifecycle_fp else ""
                    ),
                    league_id=_safe_text(selected_league_id),
                    roster_id=_safe_text(my_roster_id),
                    season=_safe_text(
                        st.session_state.get("stats_season")
                        or league_value_settings.get("season")
                    ),
                    week=_safe_text(league_value_settings.get("week")),
                    scoring_format=_safe_text(scoring_rank_context.scoring_format),
                    valuation_lens=_safe_text(score_field),
                    roster_state_version=_safe_text(
                        st.session_state.get(
                            recommendation_lifecycle.ROSTER_STATE_VERSION_SESSION_KEY
                        )
                    ),
                    provider_data_version=league_value_settings_key(league_value_settings),
                    frame_signature=prepared_frame_signature,
                    strategy=trade_hub_strategy,
                    archetype=trade_hub_archetype,
                    score_field=score_field,
                    pick_score_multiplier=trade_hub_pick_multiplier,
                    league_settings_key=league_value_settings_key(league_value_settings),
                    untouchables=trade_hub_untouchables_key,
                    role_items=trade_hub_role_items,
                    entitlement=trade_hub_entitlement,
                    max_ideas=8,
                )
            )

            def render_top_trade_opportunities() -> None:
                from modules import lifecycle_render_trace as _lifecycle
                from modules import render_ownership as _render_own

                board_status = st.empty()
                board_cached = trade_hub_first_useful.presentation_board_cached(
                    st.session_state,
                    signature=presentation_board_signature,
                )
                if not board_cached and _render_own.claim(
                    st.session_state, _render_own.OWNER_TRADE_HUB_LOADING
                ):
                    board_status.caption(product_copy.LOADING_TRADE_IDEAS)
                _lifecycle.mark(st.session_state, "T5_page_expensive_begin")

                def _build_presentation_board() -> dict:
                    with trade_hub_first_useful.stage_timer("recommendation_generation"):
                        runtime_trace.count("cached_trade_ideas_calls")
                        ideas = cached_trade_ideas(
                            df_players=trade_hub_df,
                            league_id=selected_league_id,
                            df_summary=df_summary,
                            my_roster_id=my_roster_id,
                            untouchables=trade_hub_untouchables_key,
                            role_items=trade_hub_role_items,
                            score_field=score_field,
                            pick_score_multiplier=trade_hub_pick_multiplier,
                            team_strategy=trade_hub_strategy,
                            team_archetype=trade_hub_archetype,
                            league_settings_items=draft_pick_valuation_settings_items(
                                league_value_settings
                            ),
                            max_ideas=8,
                        )
                    with trade_hub_first_useful.stage_timer("trust_approval_filtering"):
                        ideas = enforce_cached_trade_ideas(
                            ideas,
                            df_players=trade_hub_df,
                            league_id=selected_league_id,
                            df_summary=df_summary,
                            my_roster_id=my_roster_id,
                            untouchables=trade_hub_untouchables_key,
                            trust_context=trade_hub_context.get("trade_trust_context"),
                            team_stance=team_stance.fetch_stance_for_league(
                                st.session_state, league_id=_safe_text(selected_league_id)
                            ),
                        )
                    # Manager tendencies are presentation enrichment only; they do
                    # not affect Trust, scores, or ordering. Still applied before
                    # #1 paint so canonical narratives stay identical.
                    with trade_hub_first_useful.stage_timer("manager_tendency_enrichment"):
                        ideas = enrich_trade_ideas_with_manager_tendencies(
                            ideas,
                            df_summary,
                            trade_hub_context.get("league_maturity", {}),
                        )
                    if not ideas:
                        return {
                            "eligible_ideas": [],
                            "presentation": None,
                            "ranked_feed": [],
                            "headline_idea": None,
                            "board_inventory": None,
                            "equivalence_fingerprint": trade_hub_first_useful.idea_equivalence_fingerprint(
                                []
                            ),
                        }
                    with trade_hub_first_useful.stage_timer("presentation_ordering"):
                        ranked_ideas = order_trade_hub_visible_ideas(ideas)
                    trade_hub_presentation = trade_hub_entitlement_presentation(
                        ranked_ideas,
                        [],
                        entitlement=trade_hub_entitlement,
                    )
                    eligible_ideas = list(trade_hub_presentation["visible_ideas"])
                    headline_idea = select_trade_hub_headline_idea(eligible_ideas)
                    grouped_ideas = group_trade_hub_ideas(
                        eligible_ideas,
                        headline_idea=headline_idea,
                    )
                    board_inventory = trade_hub_section_inventory(grouped_ideas)
                    if board_inventory["accessible_count"] != trade_hub_presentation["visible_count"]:
                        raise RuntimeError("Trade Hub presentation count mismatch")
                    ranked_feed = annotate_trade_hub_feed_categories(
                        eligible_ideas,
                        headline_idea=headline_idea,
                    )
                    return {
                        "eligible_ideas": eligible_ideas,
                        "presentation": trade_hub_presentation,
                        "ranked_feed": ranked_feed,
                        "headline_idea": headline_idea,
                        "board_inventory": board_inventory,
                        "equivalence_fingerprint": trade_hub_first_useful.idea_equivalence_fingerprint(
                            eligible_ideas
                        ),
                    }

                from modules import hot_path_profile as _hot_path

                with _hot_path.span(
                    "trade_hub_presentation_board",
                    kind="cpu",
                    session_state=st.session_state,
                ) as _board_meta:
                    board_payload, board_cache_hit = (
                        trade_hub_first_useful.get_or_build_presentation_board(
                            st.session_state,
                            signature=presentation_board_signature,
                            builder=_build_presentation_board,
                        )
                    )
                    _board_meta["cache_status"] = "hit" if board_cache_hit else "miss"
                board_status.empty()
                _lifecycle.mark(st.session_state, "T6_page_expensive_end")
                if board_cache_hit:
                    runtime_trace.count("trade_hub_warm_board_reuse")

                trade_hub_presentation = board_payload.get("presentation")
                eligible_ideas = list(board_payload.get("eligible_ideas") or [])
                ranked_feed = list(board_payload.get("ranked_feed") or [])
                headline_idea = board_payload.get("headline_idea")
                board_inventory = board_payload.get("board_inventory")
                handoff_rec_id = _safe_text(
                    st.session_state.get(
                        f"trade_hub_focus_recommendation_id_{selected_league_id}"
                    )
                )
                handoff_context_key = (
                    f"trade_hub_focus_recommendation_context_{selected_league_id}"
                )
                handoff_context = st.session_state.get(handoff_context_key)
                handoff_idea = (
                    handoff_context.get("idea")
                    if isinstance(handoff_context, dict)
                    and isinstance(handoff_context.get("idea"), dict)
                    else None
                )
                def _validate_dashboard_handoff(candidates: list[dict]) -> list[dict]:
                    validated = enforce_cached_trade_ideas(
                        candidates,
                        df_players=trade_hub_df,
                        league_id=selected_league_id,
                        df_summary=df_summary,
                        my_roster_id=my_roster_id,
                        untouchables=trade_hub_untouchables_key,
                        trust_context=trade_hub_context.get("trade_trust_context"),
                    )
                    return enrich_trade_ideas_with_manager_tendencies(
                        validated,
                        df_summary,
                        trade_hub_context.get("league_maturity", {}),
                    )

                # Dashboard uses a bounded one-result search while Trade Hub
                # builds a broader board. Revalidate the exact handed-off
                # package against current canonical Trust/ownership instead of
                # declaring it stale merely because generation omitted it.
                eligible_ideas, handoff_revalidation = (
                    revalidate_handoff_candidate(
                        eligible_ideas,
                        handoff_rec_id,
                        handoff_idea,
                        validator=_validate_dashboard_handoff,
                    )
                )
                if handoff_revalidation == "focused_revalidated":
                    ranked_feed = annotate_trade_hub_feed_categories(
                        eligible_ideas,
                        headline_idea=eligible_ideas[0],
                    )
                    if trade_hub_presentation is None:
                        trade_hub_presentation = (
                            trade_hub_entitlement_presentation(
                                eligible_ideas,
                                [],
                                entitlement=trade_hub_entitlement,
                            )
                        )
                        board_inventory = trade_hub_section_inventory(
                            group_trade_hub_ideas(
                                eligible_ideas,
                                headline_idea=eligible_ideas[0],
                            )
                        )
                eligible_ideas, handoff_status = (
                    apply_handoff_recommendation(
                        eligible_ideas, handoff_rec_id
                    )
                )
                ranked_feed, ranked_handoff_status, handoff_trade_key = (
                    resolve_handoff_trade_detail(
                        ranked_feed,
                        handoff_rec_id,
                        page_context="trade_hub_feed",
                    )
                )
                if handoff_status == "focused" and eligible_ideas:
                    headline_idea = eligible_ideas[0]
                if handoff_status == "focused" and ranked_handoff_status != "focused":
                    handoff_status = "stale"
                if (
                    handoff_status == "focused"
                    and ranked_handoff_status == "focused"
                    and handoff_trade_key
                ):
                    # The Dashboard handoff identifies a canonical package, not
                    # merely the Trade Hub route. Open the exact ranked card once
                    # using the same key contract as the real feed renderer.
                    trade_detail_navigation.open_trade(
                        st.session_state,
                        handoff_trade_key,
                    )
                    st.session_state.pop(
                        f"trade_hub_focus_recommendation_id_{selected_league_id}",
                        None,
                    )
                    st.session_state.pop(handoff_context_key, None)
                st.session_state[
                    f"trade_hub_focus_recommendation_status_{selected_league_id}"
                ] = handoff_status

                if not eligible_ideas or trade_hub_presentation is None:
                    render_trade_hub_empty_state()
                    trade_hub_first_useful.mark_trade_hub_milestone("trade_hub_board_ready")
                    return

                _dialog_open = bool(
                    trade_detail_navigation.current(st.session_state).trade_key
                )
                if (
                    not _dialog_open
                    and handoff_rec_id
                    and handoff_status == "stale"
                ):
                    st.caption(handoff_stale_copy())
                    dashboard_trade_signature = (
                        _safe_text(handoff_context.get("dashboard_trade_signature"))
                        if isinstance(handoff_context, dict)
                        else ""
                    )
                    game_plan_process_cache.invalidate_trade_headline(
                        dashboard_trade_signature
                    )
                    game_plan_package.invalidate_cached_package_only(
                        st.session_state
                    )
                    st.session_state.pop(
                        f"trade_hub_focus_recommendation_id_{selected_league_id}",
                        None,
                    )
                    st.session_state.pop(handoff_context_key, None)
                if not _dialog_open:
                    render_trade_hub_entitlement_summary(
                        trade_hub_presentation,
                        section_count=int((board_inventory or {}).get("section_count") or 1),
                    )
                feed_key = (
                    f"trade_hub_unified_feed_{selected_league_id}_{my_roster_id}_"
                    f"{trade_hub_strategy}"
                )
                visible_count_key = f"{feed_key}_visible"
                # Default reveal two approved ideas when inventory allows; never fabricate.
                default_visible = min(2, max(1, len(ranked_feed))) if ranked_feed else 1
                visible_count = max(
                    1,
                    int(st.session_state.get(visible_count_key, default_visible)),
                )
                if ranked_feed:
                    visible_count = min(visible_count, len(ranked_feed))
                trade_hub_first_useful.mark_trade_hub_milestone("trade_hub_rec1_ready")
                if ranked_feed:
                    @st.fragment
                    def _trade_hub_visible_feed() -> None:
                        # Fragment-scoped reveal: Show more must not rebuild Trade Ideas.
                        local_visible = max(
                            1,
                            int(st.session_state.get(visible_count_key, default_visible)),
                        )
                        local_visible = min(local_visible, len(ranked_feed))
                        trade_hub_render_started = time.perf_counter()
                        open_trade_key = trade_detail_navigation.current(
                            st.session_state
                        ).trade_key
                        with trade_hub_first_useful.stage_timer(
                            "canonical_narrative_construction",
                            category="render",
                        ):
                            visible_ideas = list(ranked_feed[:local_visible])
                            with st.container(key="trade_hub_board"):
                                if open_trade_key:
                                    for idea_idx, display_idea in enumerate(visible_ideas):
                                        card_key = trade_summary_key(
                                            display_idea,
                                            page_context="trade_hub_feed",
                                            instance_token=idea_idx,
                                        )
                                        if card_key != open_trade_key:
                                            continue
                                        render_trade_idea_card(
                                            display_idea,
                                            idea_idx,
                                            key_prefix="trade_hub_feed",
                                            render_player_dossier=trade_player_dossier_renderer,
                                        )
                                        if idea_idx == 0:
                                            trade_hub_first_useful.mark_trade_hub_milestone(
                                                "trade_hub_rec1_rendered"
                                            )
                                elif visible_ideas:
                                    with st.container(key="trade_hub_headline"):
                                        render_trade_idea_card(
                                            visible_ideas[0],
                                            0,
                                            key_prefix="trade_hub_feed",
                                            render_player_dossier=trade_player_dossier_renderer,
                                        )
                                        trade_hub_first_useful.mark_trade_hub_milestone(
                                            "trade_hub_rec1_rendered"
                                        )
                                    rest = visible_ideas[1:]
                                    if rest:
                                        with st.container(key="trade_hub_more_ideas"):
                                            for idea_idx, display_idea in enumerate(rest, start=1):
                                                render_trade_idea_card(
                                                    display_idea,
                                                    idea_idx,
                                                    key_prefix="trade_hub_feed",
                                                    render_player_dossier=trade_player_dossier_renderer,
                                                )
                        performance.record_timing(
                            "trade_hub_visible_cards_render",
                            (time.perf_counter() - trade_hub_render_started) * 1000,
                            category="render",
                            result_size=min(len(ranked_feed), local_visible),
                        )
                        if not open_trade_key and len(ranked_feed) > local_visible:
                            reveal_count = min(3, len(ranked_feed) - local_visible)
                            with st.container(key="trade_hub_show_more"):
                                st.button(
                                    f"Show {reveal_count} more",
                                    key=f"{visible_count_key}_more",
                                    use_container_width=True,
                                    on_click=increment_session_counter,
                                    args=(visible_count_key, reveal_count, local_visible),
                                )

                    _trade_hub_visible_feed()
                else:
                    render_trade_hub_empty_state()

                trade_hub_first_useful.mark_trade_hub_milestone("trade_hub_board_ready")

                _dialog_open_after_board = bool(
                    trade_detail_navigation.current(st.session_state).trade_key
                )
                if not _dialog_open_after_board:
                    if trade_hub_presentation["show_board_upgrade"]:
                        render_trade_hub_free_gate(trade_hub_presentation)
                        render_premium_lock(
                            TRADE_HUB_FREE_GATE_TITLE,
                            TRADE_HUB_FREE_GATE_BODY,
                            feature="Premium Trade Hub",
                            cta=TRADE_HUB_FREE_GATE_CTA,
                        )
                    guest_conversion.render_soft_signup_prompt(
                        surface="trade_hub",
                        config=_supabase_config(),
                    )

            def render_search_around_player() -> None:
                from modules import render_ownership as _render_own
                from modules import trade_hub_player_search as player_search

                if not _render_own.claim(
                    st.session_state, _render_own.OWNER_SECONDARY_SEARCH
                ):
                    return
                if trade_detail_navigation.current(st.session_state).trade_key:
                    player_search.note_skip("trade_dialog_open")
                    return
                executed = player_search.executed_signature(st.session_state)
                expanded = bool(
                    executed and executed.startswith(f"{str(selected_league_id)}|")
                ) or player_search.has_queued_player_focus(
                    st.session_state,
                    league_id=str(selected_league_id or ""),
                )
                st.markdown(
                    '<div data-dg-scroll-anchor="trade-hub-player-search" '
                    'class="trade-hub-semantic-anchor" aria-hidden="true"></div>',
                    unsafe_allow_html=True,
                )
                with st.expander(
                    "Search Around a Player — secondary tool",
                    expanded=expanded,
                ):
                    _render_search_around_player_body()

            def _mark_trade_player_search_ready() -> None:
                st.markdown(
                    '<div data-dg-scroll-ready="trade-hub-player-search" '
                    'class="trade-hub-semantic-ready" aria-hidden="true"></div>',
                    unsafe_allow_html=True,
                )

            def _render_search_around_player_body() -> None:
                render_trade_hub_section_header(
                    "Search Around a Player",
                    eyebrow="Secondary Tool",
                    subtitle="Every result stays centered on the selected player. Choose whether you are trading them away or trying to acquire them.",
                )
                search_mode_key = f"player_trade_hub_mode_{selected_league_id}"
                if trade_hub_focus_mode == "my_player":
                    st.session_state[search_mode_key] = "Your Player"
                elif trade_hub_focus_mode == "target_player":
                    st.session_state[search_mode_key] = "League Target"
                elif search_mode_key not in st.session_state:
                    st.session_state[search_mode_key] = "Your Player"

                hub_mode_label = st.radio(
                    "Direction",
                    ["Your Player", "League Target"],
                    horizontal=True,
                    key=search_mode_key,
                )
                st.caption(
                    "Your Player: packages that send this player. "
                    "League Target: packages that acquire this player."
                )
                hub_mode = "my_player" if hub_mode_label == "Your Player" else "target_player"

                if hub_mode == "my_player":
                    my_trade_pool = trade_hub_df[trade_hub_df["player_id"].astype(str).isin(my_player_ids)].copy()
                    if my_trade_pool.empty:
                        st.info("No roster players are available for player search right now.")
                    else:
                        my_rank_row = shell_chrome_schema.select_roster_row(
                            hub_display, my_roster_id
                        )
                        render_summary_tiles(
                            [
                                {
                                    "label": "Team Context",
                                    "value": (
                                        f"Roster Power {_format_rank(my_rank_row.get('power_rank'), tied=bool(my_rank_row.get('power_rank_tied')))} | "
                                        f"Franchise {_format_rank(my_rank_row.get('franchise_rank'), tied=bool(my_rank_row.get('franchise_rank_tied')))}"
                                    ),
                                    "note": f"Trade lens: {trade_hub_lens_label}.",
                                    "tone": "strategy",
                                },
                            ],
                            compact=True,
                        )
                        render_trade_return_explorer(
                            all_players_df=trade_hub_df,
                            owned_player_df=my_trade_pool,
                            league_id=selected_league_id,
                            df_summary=df_summary,
                            my_roster_id=my_roster_id,
                            untouchables=untouchables,
                            role_map=role_map,
                            score_field=score_field,
                            pick_score_multiplier=trade_hub_pick_multiplier,
                            team_strategy=trade_hub_strategy,
                            team_archetype=trade_hub_archetype,
                            team_lens_label=trade_hub_lens_label,
                            league_settings=league_value_settings,
                            key_prefix=f"player_trade_hub_{selected_league_id}_{my_roster_id}",
                            max_ideas=6,
                            compact=True,
                            show_header=False,
                            preselected_player_id=trade_hub_focus_player_id if trade_hub_focus_mode == "my_player" else "",
                            card_key_prefix=f"player_trade_hub_cards_{selected_league_id}_{my_roster_id}",
                            trust_context=trade_hub_context.get("trade_trust_context"),
                            render_player_dossier=trade_player_dossier_renderer,
                            roster_player_map=roster_player_map,
                            draft_pick_assets=trade_hub_context.get("draft_pick_assets"),
                        )
                        render_player_detail_button_grid(
                            my_trade_pool.sort_values(score_field, ascending=False).head(6),
                            key_prefix=f"player_hub_my_targets_{selected_league_id}_{my_roster_id}",
                            return_page="trade_hub",
                            source_label="Trade Hub",
                            title="Quick view one of your players",
                            max_buttons=6,
                            open_mode="quick_view",
                        )
                        _mark_trade_player_search_ready()
                    return

                target_pool = trade_hub_df[
                    trade_hub_df["player_id"].astype(str).isin(owned_player_to_roster.keys())
                    & ~trade_hub_df["player_id"].astype(str).isin(my_player_ids)
                ].copy()
                target_pool = target_pool[
                    pd.to_numeric(target_pool.get(score_field, 0), errors="coerce").fillna(0) > 0
                ].copy()
                if target_pool.empty:
                    st.info("No valid league targets are available right now.")
                    return

                target_pool = target_pool.sort_values(score_field, ascending=False)
                target_labels = {
                    player_trade_hub_option_label(row, score_field): str(row["player_id"])
                    for _, row in target_pool.iterrows()
                }
                target_options = list(target_labels.keys())
                default_target_index = 0
                if trade_hub_focus_mode == "target_player" and trade_hub_focus_player_id:
                    for idx, label in enumerate(target_options):
                        if target_labels.get(label) == trade_hub_focus_player_id:
                            default_target_index = idx
                            break
                target_selectbox_key = f"player_trade_hub_target_player_{selected_league_id}"
                if trade_hub_focus_mode == "target_player" and target_options:
                    st.session_state[target_selectbox_key] = target_options[default_target_index]
                elif target_selectbox_key not in st.session_state and target_options:
                    st.session_state[target_selectbox_key] = target_options[0]
                selected_label = st.selectbox(
                    "Select any league player",
                    target_options,
                    key=target_selectbox_key,
                )
                selected_player_id = target_labels[selected_label]
                selected_row = target_pool[target_pool["player_id"].astype(str) == selected_player_id].iloc[0]
                target_roster_id = owned_player_to_roster.get(selected_player_id, "")
                target_profile = roster_profiles.get(str(target_roster_id), {})
                target_team_name = _safe_text(target_profile.get("team_name"), "League roster")
                target_owner_name = owner_handle(target_profile.get("username"), target_profile.get("owner_name", "Owner"))
                target_rank_row = shell_chrome_schema.select_roster_row(
                    hub_display, target_roster_id
                )

                render_summary_tiles(
                    [
                        {
                            "label": "Selected Target",
                            "value": player_display_name(selected_row),
                            "note": player_trade_hub_selected_summary(selected_row, score_field),
                            "tone": "opportunity",
                        },
                        {
                            "label": "Current Team",
                            "value": target_team_name,
                            "note": (
                                f"{target_owner_name} | Roster Power {_format_rank(target_rank_row.get('power_rank'), tied=bool(target_rank_row.get('power_rank_tied')))} | "
                                f"Franchise {_format_rank(target_rank_row.get('franchise_rank'), tied=bool(target_rank_row.get('franchise_rank_tied')))}"
                                + (
                                    f" | {_safe_text(target_rank_row.get('manager_tendencies_summary'))}"
                                    if _safe_text(target_rank_row.get('manager_tendencies_summary'))
                                    else ""
                                )
                            ),
                            "tone": "franchise",
                        },
                        {
                            "label": "Current Strategy",
                            "value": trade_hub_lens_label,
                            "note": "This lens shapes which acquisition paths are preferred for your roster.",
                            "tone": "strategy",
                        },
                    ],
                    compact=True,
                )
                render_player_detail_button_grid(
                    [selected_row],
                    key_prefix=f"player_hub_target_{selected_league_id}_{selected_player_id}",
                    return_page="trade_hub",
                    source_label="Trade Hub",
                    title="Quick view the selected target",
                    max_buttons=1,
                    open_mode="quick_view",
                )

                from modules import trade_hub_player_search as player_search

                target_search_sig = player_search.search_signature(
                    league_id=str(selected_league_id or ""),
                    roster_id=str(my_roster_id or ""),
                    strategy=str(trade_hub_strategy or ""),
                    mode="target_player",
                    player_id=str(selected_player_id or ""),
                    score_field=str(score_field or ""),
                    pick_score_multiplier=trade_hub_pick_multiplier,
                    value_version=str(trade_hub_archetype or ""),
                )
                focused_search = player_search.execute_queued_player_focus(
                    st.session_state,
                    league_id=str(selected_league_id or ""),
                    player_id=str(selected_player_id or ""),
                    signature=target_search_sig,
                )
                if focused_search:
                    st.session_state.pop(f"trade_hub_focus_player_id_{selected_league_id}", None)
                    st.session_state.pop(f"trade_hub_focus_mode_{selected_league_id}", None)
                target_find_clicked = st.button(
                    player_search.FIND_BUTTON_LABEL,
                    key=f"player_trade_hub_target_find_{selected_league_id}",
                    type="primary",
                    use_container_width=False,
                )
                if target_find_clicked:
                    player_search.mark_executed(st.session_state, target_search_sig)
                if not player_search.is_executed(st.session_state, target_search_sig):
                    player_search.note_skip(
                        "stale_selection"
                        if player_search.executed_signature(st.session_state)
                        else "not_requested"
                    )
                    st.caption(player_search.instruction_for(st.session_state, target_search_sig))
                    return

                search_started = time.perf_counter()
                with player_search.exclusive_find_block(st.session_state, "player_search_signature"):
                    _ = target_search_sig
                with player_search.exclusive_find_block(
                    st.session_state, "player_search_cache_lookup"
                ) as _cache_meta:
                    cached_hub_payload = player_search.cache_get(st.session_state, target_search_sig)
                    _cache_meta["cache_status"] = (
                        "hit" if cached_hub_payload is not None else "miss"
                    )
                if cached_hub_payload is None:
                    from modules import dashboard_loading_state as _dash_load

                    with _dash_load.hydrate_placeholder(
                        _dash_load.ROUTE_TRADE_HUB_ACQUISITION_SEARCH,
                        title="Searching acquisition paths...",
                    ):
                        hub_search_result = cached_player_trade_hub_ideas(
                            df_players=trade_hub_df,
                            league_id=selected_league_id,
                            df_summary=df_summary,
                            my_roster_id=my_roster_id,
                            untouchables=tuple(sorted(untouchables)),
                            role_items=tuple(sorted((str(pid), str(role)) for pid, role in role_map.items())),
                            score_field=score_field,
                            pick_score_multiplier=trade_hub_pick_multiplier,
                            team_strategy=trade_hub_strategy,
                            team_archetype=trade_hub_archetype,
                            mode="target_player",
                            selected_player_id=selected_player_id,
                            league_settings_items=draft_pick_valuation_settings_items(league_value_settings),
                            max_ideas=8,
                            prefetched_roster_map=roster_player_map,
                            prefetched_pick_assets=trade_hub_context.get("draft_pick_assets"),
                            hot_path_state=st.session_state,
                        )
                    with player_search.exclusive_find_block(
                        st.session_state, "player_search_cache_write"
                    ):
                        player_search.cache_put(st.session_state, target_search_sig, hub_search_result)
                    cache_status = "miss"
                else:
                    hub_search_result = cached_hub_payload
                    cache_status = "hit"
                player_search.note_run(
                    cache_status=cache_status,
                    elapsed_ms=(time.perf_counter() - search_started) * 1000,
                    signature=target_search_sig,
                )
                performance.record_timing(
                    "trade_hub_secondary_search",
                    (time.perf_counter() - search_started) * 1000,
                    category="analysis",
                    result_size=len(hub_search_result.get("ideas") or []),
                )
                with player_search.exclusive_find_block(st.session_state, "player_search_trust"):
                    target_diag = dict(hub_search_result.get("diagnostics") or {})
                    hub_search_result = {
                        **hub_search_result,
                        "ideas": enforce_cached_trade_ideas(
                            hub_search_result.get("ideas") or [],
                            df_players=trade_hub_df,
                            league_id=selected_league_id,
                            df_summary=df_summary,
                            my_roster_id=my_roster_id,
                            untouchables=tuple(sorted(str(name) for name in untouchables)),
                            trust_context=trade_hub_context.get("trade_trust_context"),
                            explicit_player_focus=True,
                            focused_player_ids=(str(selected_player_id),),
                            explicit_acquisition_target=True,
                            diagnostics=target_diag,
                        ),
                        "diagnostics": target_diag,
                    }
                with player_search.exclusive_find_block(
                    st.session_state, "player_search_presentation_prepare"
                ):
                    hub_ideas = enrich_trade_ideas_with_manager_tendencies(
                        hub_search_result.get("ideas") or [],
                        df_summary,
                        trade_hub_context.get("league_maturity", {}),
                    )
                target_diag = dict(hub_search_result.get("diagnostics") or {})
                target_diag["session_cache_status"] = cache_status
                hub_search_result = {**hub_search_result, "diagnostics": target_diag}
                player_search.emit_find_parent_summary(
                    st.session_state,
                    duration_ms=(time.perf_counter() - search_started) * 1000,
                    cache_status=cache_status,
                )

                if hub_ideas:
                    if hub_search_result.get("fallback_used"):
                        st.caption(
                            "Expanded market search used because smaller packages did not clear."
                        )
                    render_trade_hub_section_header(
                        "Suggested Paths",
                        eyebrow="Acquisition Board",
                        subtitle="Realistic packages that could acquire the selected player.",
                    )
                    ordered_hub_ideas, _hub_handoff = (
                        apply_handoff_recommendation(
                            order_trade_hub_visible_ideas(hub_ideas),
                            _safe_text(
                                st.session_state.get(
                                    f"trade_hub_focus_recommendation_id_{selected_league_id}"
                                )
                            ),
                        )
                    )
                    best_hub, other_hub, _exploratory_hub = split_player_search_ideas(
                        ordered_hub_ideas
                    )
                    headline_hub_idea = select_trade_hub_headline_idea(best_hub or other_hub)
                    if headline_hub_idea is not None:
                        render_dense_metric_strip(
                            [
                                {
                                    "label": "Best Partner",
                                    "value": _safe_text(headline_hub_idea.get("partner_team_name"), target_team_name),
                                },
                                {
                                    "label": "Best Offer Out",
                                    "value": _safe_text(headline_hub_idea.get("my_player"), "Package"),
                                },
                                {
                                    "label": "Confidence",
                                    "value": _trade_display_confidence_label(headline_hub_idea),
                                },
                            ]
                        )

                    _render_player_search_grouped_cards(
                        ordered_hub_ideas,
                        card_key_prefix=f"target_trade_hub_cards_{selected_league_id}_{selected_player_id}",
                        render_player_dossier=trade_player_dossier_renderer,
                    )
                    _render_player_search_founder_diagnostics(
                        hub_search_result, key_prefix="trade_hub_target"
                    )
                    _mark_trade_player_search_ready()
                    return

                _render_player_search_empty_state(hub_search_result)
                _mark_trade_player_search_ready()

            render_top_trade_opportunities()
            # Re-read after the board so a card tap in this rerun skips secondary search.
            from modules import trade_hub_player_search as player_search

            if not trade_detail_navigation.current(st.session_state).trade_key:
                st.divider()
                if current_user_is_premium():
                    render_search_around_player()
                else:
                    render_premium_lock(
                        "Player-focused trade search",
                        "Search returns or acquisition paths around a specific player after you spot a board idea worth pursuing.",
                        feature="Premium Trade Hub",
                    )
            else:
                player_search.note_skip("trade_dialog_open")
            trade_hub_first_useful.mark_trade_hub_milestone("trade_hub_route_complete")
