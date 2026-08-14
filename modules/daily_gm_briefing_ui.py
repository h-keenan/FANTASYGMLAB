"""Streamlit presentation for Today's Game Plan."""

from __future__ import annotations

from html import escape
from typing import Callable

import streamlit as st

from modules import daily_gm_briefing as briefing_mod
from modules import compact_fantasy_assets
from modules import ui_primitives
from modules.html_rendering import inject_global_styles, render_html_fragment


# Scoped to Dashboard Game Plan renders — keep off the global cold-path CSS budget.
DAILY_GM_BRIEFING_CSS = """
<style>
.dg-daily-briefing-quiet{align-items:baseline;display:flex;flex-direction:column;gap:var(--space-2xs)}
.dg-daily-briefing-quiet strong{color:var(--color-success);font:var(--font-card-title)}
.dg-daily-briefing-quiet span{color:var(--color-text-secondary);font:var(--font-body);max-width:42rem}
.dg-game-plan-lede{color:var(--color-text-secondary);font:var(--type-caption-emphasis);margin:0}
.dg-game-plan-age{color:var(--color-text-muted);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);margin:0}
.dg-game-plan-card{background:var(--color-surface-primary);border:var(--border-width-default) solid var(--color-border);display:flex;flex-direction:column;gap:var(--space-xs);height:100%;min-width:0;padding:var(--space-sm)}
.dg-game-plan-card-primary{background:var(--color-surface-raised);border-color:var(--color-border-strong);border-inline-start:var(--border-width-semantic) solid var(--color-accent);padding-inline-start:var(--space-md)}
.dg-daily-briefing-kicker{color:var(--color-accent);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.dg-daily-briefing-headline{color:var(--color-text-primary);font:var(--font-card-title)}
.dg-game-plan-card-primary .dg-daily-briefing-headline{font:var(--type-section-title)}
.dg-daily-briefing-reason{color:var(--color-text-secondary);font:var(--type-caption-emphasis)}
.dg-daily-briefing-rank{color:var(--color-text-muted);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge)}
div[class*="st-key-"][class*="_header"] [data-testid=stHorizontalBlock]{align-items:flex-end;gap:var(--space-sm)}
div[class*="_refresh_recommendations"]{display:flex;justify-content:flex-end}
div[class*="_refresh_recommendations"] button{min-width:0;white-space:nowrap!important;width:auto!important}
div[class*="st-key-"][class*="_cards"]{display:grid;gap:var(--space-sm);grid-template-columns:minmax(0,1fr)}
div[class*="st-key-"][class*="_card_"] [data-testid=stButton]>button{width:100%}
div[class*="st-key-"][class*="dg_cta_"]{margin:0}
div[class*="st-key-"][class*="auto_strategy_help"] button,div[class*="st-key-auto_strategy_help"] button{min-height:var(--touch-target-min)!important;width:auto!important;white-space:nowrap!important}
@media (min-width:1024px){
.dg-game-plan-card{padding:var(--space-md)}
div[class*="st-key-"][class*="_cards"]{align-items:stretch;grid-template-columns:minmax(0,1.45fr) minmax(0,1fr)}
div[class*="st-key-"][class*="_card_1"]{grid-column:1;grid-row:1 / span 2}
}
@media (max-width:1023px){
div[class*="st-key-"][class*="_header"] [data-testid=stHorizontalBlock]{flex-direction:column!important;align-items:stretch}
div[class*="_refresh_recommendations"]{width:100%}
div[class*="_refresh_recommendations"] button{min-height:var(--touch-target-min)!important;width:100%!important}
}
@media (max-width:760px){
div[class*="st-key-"][class*="_cards"]{grid-template-columns:minmax(0,1fr)}
div[class*="st-key-"][class*="_card_1"]{grid-column:auto;grid-row:auto}
.dg-daily-briefing-reason{max-width:100%}
}
</style>
"""


def _category_kicker(category: str) -> str:
    return escape(briefing_mod.CATEGORY_LABELS.get(category, category.replace("_", " ").title()))


def render_todays_game_plan(
    plan: briefing_mod.DailyGmBriefing,
    *,
    open_item: Callable[[briefing_mod.DailyBriefingItem], None],
    key_prefix: str = "daily_gm_briefing",
) -> None:
    """Render the compact executive morning brief."""

    inject_global_styles(DAILY_GM_BRIEFING_CSS)
    inject_global_styles(f"<style>{compact_fantasy_assets.COMPACT_FANTASY_ASSET_CSS}</style>")
    with st.container(key=f"{key_prefix}_header"):
        heading_col, refresh_col = st.columns([5, 1], vertical_alignment="bottom")
        with heading_col:
            ui_primitives.render_section_header("Today's Game Plan", weight="primary")
            st.markdown(
                "<p class='dg-game-plan-lede'>Your highest-impact moves right now.</p>",
                unsafe_allow_html=True,
            )
            try:
                from modules import game_plan_package

                package = st.session_state.get(game_plan_package.PACKAGE_KEY)
                age_label = game_plan_package.format_package_age_label(
                    package if isinstance(package, dict) else None
                )
                if age_label:
                    st.markdown(
                        f"<p class='dg-game-plan-age'>{escape(age_label)}</p>",
                        unsafe_allow_html=True,
                    )
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
        with refresh_col:
            try:
                from modules import game_plan_package

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
            "<strong>No move needed right now</strong>"
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
            cta = "Open workflow"
            if item.destination == "trade_hub":
                cta = "Open Trade Hub"
            elif item.destination == "waivers":
                cta = "Open Waivers"
            elif item.destination == "my_team":
                cta = "Open My Team"
            elif item.destination == "rankings":
                cta = "Open League Overview"
            tier = "primary" if is_primary else "secondary"
            with st.container(key=f"{key_prefix}_card_{index}"):
                render_html_fragment(
                    f"<div class='{card_class}'>"
                    f"<div class='dg-daily-briefing-kicker'>{_category_kicker(item.category)}</div>"
                    f"<div class='dg-daily-briefing-headline'>{escape(item.headline)}</div>"
                    f"{visual_html}"
                    f"<div class='dg-daily-briefing-reason'>{escape(item.reason)}</div>"
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
    presentation = item.presentation if isinstance(item.presentation, dict) else None
    if item.category == briefing_mod.CATEGORY_WATCH:
        players = (presentation or {}).get("players") if presentation else None
        return compact_fantasy_assets.identity_chips_html(players)
    if item.destination == "waivers" or item.category == briefing_mod.CATEGORY_WAIVER:
        player = (presentation or {}).get("player") if presentation else None
        if isinstance(player, dict) and player:
            role = str(player.get("role") or "").strip()
            chip = compact_fantasy_assets.compact_asset_html(player, size="compact", show_value=False)
            role_html = (
                f"<div class='dg-daily-briefing-rank'>{escape(role)}</div>" if role else ""
            )
            return f"{chip}{role_html}"
        return ""
    if item.destination == "trade_hub" or item.category == briefing_mod.CATEGORY_TOP_PRIORITY:
        return compact_fantasy_assets.game_plan_trade_visual_html(presentation)
    return ""
