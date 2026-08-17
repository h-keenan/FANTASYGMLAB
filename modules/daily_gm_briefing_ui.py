"""Streamlit presentation for Today's Game Plan."""

from __future__ import annotations

import re
from html import escape
from typing import Callable
from collections.abc import Mapping

import streamlit as st

from modules import daily_gm_briefing as briefing_mod
from modules import compact_fantasy_assets
from modules import ui_primitives
from modules.html_rendering import inject_global_styles, render_html_fragment
from modules.semantic_glyphs import glyph_html


# Scoped to Dashboard Game Plan renders — keep off the global cold-path CSS budget.
DAILY_GM_BRIEFING_CSS = """
<style>
.dg-daily-briefing-quiet{display:flex;flex-direction:column;gap:var(--space-2xs)}
.dg-daily-briefing-quiet strong{color:var(--color-success);font:var(--font-card-title)}
.dg-daily-briefing-quiet span{color:var(--color-text-secondary);font:var(--font-body);max-width:42rem}
.dg-game-plan-lede{color:var(--color-text-secondary);font:var(--type-caption-emphasis);margin:0;text-align:left}
.dg-game-plan-utility{align-items:center;color:var(--color-text-muted);display:flex;font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);margin:0;min-height:var(--touch-target-min);text-align:left}
div[class*="st-key-"][class*="_lede"] [data-testid="stCaptionContainer"],div[class*="st-key-"][class*="_lede"] p{color:var(--color-text-secondary);font:var(--type-caption-emphasis);margin:0}
div[class*="st-key-"][class*="_utility"] [data-testid="stCaptionContainer"],div[class*="st-key-"][class*="_utility"] p{color:var(--color-text-muted);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);margin:0}
.dg-game-plan-card{background:var(--color-surface-primary);border:var(--border-width-default) solid var(--color-border);display:flex;flex-direction:column;gap:var(--space-sm);height:auto;min-width:0;padding:var(--space-sm)}
.dg-game-plan-card-primary{background:var(--color-surface-raised);border-color:var(--color-border-strong);border-inline-start:var(--border-width-semantic) solid var(--color-accent);padding-inline-start:var(--space-md)}
.dg-daily-briefing-kicker-row{align-items:center;display:flex;flex-wrap:wrap;gap:var(--space-xs);justify-content:space-between;min-width:0}
.dg-daily-briefing-kicker{color:var(--color-accent);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.dg-daily-briefing-kind{align-items:center;color:var(--color-text-muted);display:inline-flex;font:var(--type-supporting-metadata);gap:var(--space-xs);letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.dg-daily-briefing-kind .dg-glyph{margin-right:0}
.dg-daily-briefing-headline{color:var(--color-text-primary);font:var(--font-card-title)}
.dg-game-plan-card-primary .dg-daily-briefing-headline{font:var(--type-section-title)}
.dg-daily-briefing-reason{color:var(--color-text-secondary);font:var(--type-caption-emphasis);max-width:40rem}
.dg-daily-briefing-rank{color:var(--color-text-muted);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge)}
.dg-game-plan-card .dg-compact-asset--standard{--size-asset-standard:3.25rem}
div[class*="st-key-"][class*="_header"]{align-items:flex-start;display:flex;flex-direction:column;gap:var(--space-2xs);min-width:0;width:100%}
div[class*="st-key-"][class*="_header"] .dg-ui-section-header{margin:0!important;padding:0 0 var(--space-2xs)!important;width:100%}
div[class*="st-key-"][class*="_header"] .dg-ui-section-title{margin:0!important;text-align:left}
div[class*="st-key-"][class*="_lede"],div[class*="st-key-"][class*="_utility"]{flex:0 0 auto;height:auto;min-width:0;overflow:visible;width:auto}
div[class*="st-key-"][class*="_status_row"] [data-testid="stVerticalBlock"]{align-items:center;display:flex;flex-direction:row;flex-wrap:wrap;gap:var(--space-xs);min-width:0;width:100%}
div[class*="st-key-"][class*="_status_row"] [data-testid="stElementContainer"],
div[class*="st-key-"][class*="_status_row"] [data-testid="element-container"]{flex:0 0 auto;max-width:100%;min-width:0;width:auto!important}
div[class*="st-key-"][class*="_refresh_row"]{display:block;flex:0 0 auto;margin:0;max-width:100%;min-width:0;overflow:visible;width:auto}
div[class*="st-key-"][class*="_refresh_row"] [data-testid="stElementContainer"]{height:auto;overflow:visible}
div[class*="_refresh_recommendations"]{display:block;justify-content:flex-start;margin:0;max-width:100%;min-width:0}
div[class*="_refresh_recommendations"] button{max-width:100%;min-width:0;white-space:nowrap!important;width:auto!important}
div[class*="st-key-"][class*="_cards"]{align-items:start;display:grid;gap:var(--space-sm);grid-template-columns:minmax(0,1fr)}
div[class*="st-key-"][class*="_card_"] [data-testid=stButton]>button{width:100%}
div[class*="st-key-"][class*="dg_cta_"]{margin:0}
div[class*="st-key-"][class*="dg_cta_primary"] [data-testid=stButton]>button{border-color:var(--color-accent)!important;font-weight:var(--font-weight-button)}
div[class*="st-key-"][class*="auto_strategy_help"] button,div[class*="st-key-auto_strategy_help"] button{min-height:var(--touch-target-min)!important;width:auto!important;white-space:nowrap!important}
@media (min-width:1024px){
.dg-game-plan-card{padding:var(--space-md)}
div[class*="st-key-"][class*="_cards"]{align-items:start;grid-template-columns:minmax(0,1.7fr) minmax(0,1fr)}
div[class*="st-key-"][class*="_cards"]:not(:has([class*="_card_2"])){grid-template-columns:minmax(0,1fr)}
div[class*="st-key-"][class*="_card_1"]{grid-column:1;grid-row:auto}
div[class*="st-key-"][class*="_cards"]:has([class*="_card_3"]) [class*="_card_1"]{grid-row:1 / span 2}
div[class*="_refresh_recommendations"]{justify-content:flex-start}
}
@media (max-width:1023px){
div[class*="_refresh_recommendations"]{display:block;width:auto}
div[class*="_refresh_recommendations"] button{min-height:var(--touch-target-min)!important;width:auto!important}
}
@media (max-width:760px){
div[class*="st-key-"][class*="_cards"]{grid-template-columns:minmax(0,1fr)}
div[class*="st-key-"][class*="_card_1"]{grid-column:auto;grid-row:auto}
.dg-daily-briefing-reason{max-width:100%}
.dg-game-plan-card-primary .dg-daily-briefing-headline{font:var(--font-card-title)}
}
</style>
"""

_KIND_LABELS = {
    briefing_mod.CATEGORY_TOP_PRIORITY: "",
    briefing_mod.CATEGORY_WATCH: "Watch",
    briefing_mod.CATEGORY_WAIVER: "Waiver",
    briefing_mod.CATEGORY_LEAGUE_MOVEMENT: "League",
}


def _category_kicker(category: str) -> str:
    return escape(briefing_mod.CATEGORY_LABELS.get(category, category.replace("_", " ").title()))


def _kind_badge(item: briefing_mod.DailyBriefingItem) -> str:
    if item.destination == "trade_hub" or (
        item.category == briefing_mod.CATEGORY_TOP_PRIORITY
        and item.destination == "trade_hub"
    ):
        return "Trade"
    if item.destination == "waivers" or item.category == briefing_mod.CATEGORY_WAIVER:
        return "Waiver"
    if item.category == briefing_mod.CATEGORY_WATCH:
        return "Watch"
    if item.destination == "my_team":
        return "Roster"
    return _KIND_LABELS.get(item.category, "")


def _cta_label(item: briefing_mod.DailyBriefingItem, *, is_primary: bool) -> str:
    if item.destination == "trade_hub":
        return "Review in Trade Hub" if is_primary else "Open Trade Hub"
    if item.destination == "waivers":
        return "Open Waivers"
    if item.destination == "my_team":
        return "Open My Team"
    if item.destination == "rankings":
        return "Open League Overview"
    return "Open workflow"


def _watch_headline(item: briefing_mod.DailyBriefingItem) -> str:
    headline = item.headline.strip()
    headline = re.sub(r"(?i)injured starters", "starters need attention", headline)
    headline = re.sub(r"(?i)injured starter", "starter needs attention", headline)
    return headline


def _presentation_dict(item: briefing_mod.DailyBriefingItem) -> dict:
    presentation = item.presentation
    if isinstance(presentation, Mapping) and presentation:
        return dict(presentation)
    return {}


def _has_trade_visual(item: briefing_mod.DailyBriefingItem) -> bool:
    presentation = _presentation_dict(item)
    send = presentation.get("send") or []
    receive = presentation.get("receive") or []
    return bool(send or receive)


def _has_player_visual(item: briefing_mod.DailyBriefingItem) -> bool:
    presentation = _presentation_dict(item)
    if item.category == briefing_mod.CATEGORY_WATCH:
        players = presentation.get("players") or []
        return bool(players)
    player = presentation.get("player")
    return isinstance(player, dict) and bool(player)


def _should_show_headline(item: briefing_mod.DailyBriefingItem) -> bool:
    if item.category == briefing_mod.CATEGORY_WATCH:
        return True
    if _has_trade_visual(item) or (
        item.category == briefing_mod.CATEGORY_WAIVER and _has_player_visual(item)
    ):
        return False
    if item.destination in {"trade_hub", "waivers"} and (
        _has_trade_visual(item) or _has_player_visual(item)
    ):
        return False
    return bool(item.headline)


def _should_show_reason(item: briefing_mod.DailyBriefingItem, visual_html: str) -> bool:
    reason = (item.reason or "").strip()
    if not reason:
        return False
    if item.category == briefing_mod.CATEGORY_WATCH and visual_html:
        # Existing injury notes are pipe-delimited identity dumps once portraits exist.
        if " | " in reason or " - " in reason:
            return False
    if reason.casefold() == (item.headline or "").casefold():
        return False
    return True


def render_todays_game_plan(
    plan: briefing_mod.DailyGmBriefing,
    *,
    open_item: Callable[[briefing_mod.DailyBriefingItem], None],
    key_prefix: str = "daily_gm_briefing",
) -> None:
    """Render the compact executive morning brief."""

    inject_global_styles(DAILY_GM_BRIEFING_CSS)
    inject_global_styles(f"<style>{compact_fantasy_assets.COMPACT_FANTASY_ASSET_CSS}</style>")
    from modules import render_ownership

    render_ownership.claim(st.session_state, render_ownership.OWNER_DASHBOARD_HERO)
    age_label = ""
    try:
        from modules import game_plan_package

        package = st.session_state.get(game_plan_package.PACKAGE_KEY)
        age_label = game_plan_package.format_package_age_label(
            package if isinstance(package, dict) else None
        )
    except Exception:
        age_label = ""
    with st.container(key=f"{key_prefix}_header"):
        ui_primitives.render_section_header("Today's Game Plan", weight="primary")
        with st.container(key=f"{key_prefix}_lede"):
            st.caption("Your highest-impact moves right now.")
        with st.container(key=f"{key_prefix}_status_row"):
            if age_label:
                with st.container(key=f"{key_prefix}_utility"):
                    st.caption(age_label)
            try:
                from modules import game_plan_package

                if st.session_state.get("dg_show_dev_diagnostics"):
                    status = str(
                        st.session_state.get(game_plan_package.LAST_CACHE_STATUS_KEY) or ""
                    ).upper() or "UNKNOWN"
                    reason = str(
                        st.session_state.get(game_plan_package.LAST_MISS_REASON_KEY) or ""
                    )
                    sig = str(st.session_state.get(game_plan_package.PACKAGE_SIG_KEY) or "")[:12]
                    st.caption(
                        f"recommendation: {status}"
                        + (f" · {reason}" if reason else "")
                        + (f" · fp {sig}" if sig else "")
                    )
            except Exception:
                pass
            with st.container(key=f"{key_prefix}_refresh_row"):
                try:
                    from modules import game_plan_package

                    render_ownership.claim(
                        st.session_state, render_ownership.OWNER_REFRESH
                    )
                    if st.button(
                        "Refresh",
                        key=f"{key_prefix}_refresh_recommendations",
                        type="tertiary",
                        use_container_width=False,
                    ):
                        game_plan_package.invalidate_recommendation_packages(st.session_state)
                        st.rerun()
                except Exception:
                    pass

    if plan.quiet:
        render_html_fragment(
            "<div class='dg-daily-briefing-quiet' role='status'>"
            "<strong>No urgent roster issues right now.</strong>"
            f"<span>{escape(plan.quiet_reason)}</span>"
            "</div>"
        )
        return

    with st.container(key=f"{key_prefix}_cards"):
        for index, item in enumerate(plan.items, start=1):
            rank_html = ""
            if item.player_rank_context:
                rank_html = (
                    f"<div class='dg-daily-briefing-rank'>{escape(item.player_rank_context)}</div>"
                )
            is_primary = item.category == briefing_mod.CATEGORY_TOP_PRIORITY or index == 1
            card_class = "dg-game-plan-card"
            if is_primary:
                card_class += " dg-game-plan-card-primary"
            visual_html = _card_visual_html(item)
            headline = (
                _watch_headline(item)
                if item.category == briefing_mod.CATEGORY_WATCH
                else item.headline
            )
            headline_html = ""
            if _should_show_headline(item):
                headline_html = (
                    f"<div class='dg-daily-briefing-headline'>{escape(headline)}</div>"
                )
            reason_html = ""
            if _should_show_reason(item, visual_html):
                reason_html = (
                    f"<div class='dg-daily-briefing-reason'>{escape(item.reason)}</div>"
                )
            kind = _kind_badge(item)
            kind_html = ""
            if kind:
                kind_concept = {
                    "Trade": "trade",
                    "Waiver": "waiver",
                    "Roster": "roster",
                    "Watch": "health",
                    "League": "insights",
                }.get(kind, "more")
                kind_html = (
                    f"<div class='dg-daily-briefing-kind'>"
                    f"{glyph_html(kind_concept, size='kicker')}"
                    f"<span>{escape(kind)}</span></div>"
                )
            cta = _cta_label(item, is_primary=is_primary)
            tier = "primary" if is_primary else "secondary"
            with st.container(key=f"{key_prefix}_card_{index}"):
                render_html_fragment(
                    f"<div class='{card_class}'>"
                    "<div class='dg-daily-briefing-kicker-row'>"
                    f"<div class='dg-daily-briefing-kicker'>{_category_kicker(item.category)}</div>"
                    f"{kind_html}"
                    "</div>"
                    f"{headline_html}"
                    f"{visual_html}"
                    f"{reason_html}"
                    f"{rank_html}"
                    "</div>"
                )
                with st.container(key=f"dg_cta_{tier}_{key_prefix}_{index}"):
                    st.button(
                        cta,
                        key=f"{key_prefix}_open_{index}_{item.category}_{item.source_id[:24]}",
                        use_container_width=True,
                        on_click=open_item,
                        args=(item,),
                    )


def _card_visual_html(item: briefing_mod.DailyBriefingItem) -> str:
    presentation = _presentation_dict(item) or None
    if item.category == briefing_mod.CATEGORY_WATCH:
        players = (presentation or {}).get("players") if presentation else None
        return compact_fantasy_assets.watch_attention_html(players)
    if item.destination == "waivers" or item.category == briefing_mod.CATEGORY_WAIVER:
        player = (presentation or {}).get("player") if presentation else None
        if isinstance(player, dict) and player:
            chip = compact_fantasy_assets.compact_asset_html(
                player, size="standard", show_value=False
            )
            return f"<div class='dg-gp-identity-row'>{chip}</div>" if chip else ""
        return ""
    if item.destination == "trade_hub" or item.category == briefing_mod.CATEGORY_TOP_PRIORITY:
        return compact_fantasy_assets.game_plan_trade_visual_html(presentation)
    return ""
