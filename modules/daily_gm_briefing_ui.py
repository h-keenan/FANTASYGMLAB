"""Streamlit presentation for Today's Game Plan."""

from __future__ import annotations

from html import escape
from typing import Callable

import streamlit as st

from modules import daily_gm_briefing as briefing_mod
from modules import ui_primitives
from modules.html_rendering import render_html_fragment


def _category_kicker(category: str) -> str:
    return escape(briefing_mod.CATEGORY_LABELS.get(category, category.replace("_", " ").title()))


def render_todays_game_plan(
    plan: briefing_mod.DailyGmBriefing,
    *,
    open_item: Callable[[briefing_mod.DailyBriefingItem], None],
    key_prefix: str = "daily_gm_briefing",
) -> None:
    """Render the compact executive morning brief."""

    ui_primitives.render_section_header("Today's Game Plan", weight="primary")
    st.caption("What deserves attention right now in this league.")

    if plan.quiet:
        render_html_fragment(
            "<div class='dg-daily-briefing-quiet' role='status'>"
            "<strong>No move needed right now</strong>"
            f"<span>{escape(plan.quiet_reason)}</span>"
            "</div>"
        )
        return

    for index, item in enumerate(plan.items, start=1):
        rank_html = ""
        if item.player_rank_context:
            rank_html = (
                f"<div class='dg-daily-briefing-rank'>{escape(item.player_rank_context)}</div>"
            )
        render_html_fragment(
            "<div class='dg-daily-briefing-item'>"
            f"<div class='dg-daily-briefing-index' aria-hidden='true'>{index}</div>"
            "<div class='dg-daily-briefing-body'>"
            f"<div class='dg-daily-briefing-kicker'>{_category_kicker(item.category)}</div>"
            f"<div class='dg-daily-briefing-headline'>{escape(item.headline)}</div>"
            f"<div class='dg-daily-briefing-reason'>{escape(item.reason)}</div>"
            f"{rank_html}"
            "</div>"
            "</div>"
        )
        cta = "Open workflow"
        if item.destination == "trade_hub":
            cta = "Open Trade Hub"
        elif item.destination == "waivers":
            cta = "Open Waivers"
        elif item.destination == "my_team":
            cta = "Open My Team"
        elif item.destination == "rankings":
            cta = "Open League Overview"
        st.button(
            cta,
            key=f"{key_prefix}_open_{index}_{item.category}_{item.source_id[:24]}",
            use_container_width=True,
            on_click=open_item,
            args=(item,),
        )
