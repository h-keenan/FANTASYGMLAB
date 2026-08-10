"""Streamlit presentation for Today's Game Plan."""

from __future__ import annotations

from html import escape
from typing import Callable

import streamlit as st

from modules import daily_gm_briefing as briefing_mod
from modules import ui_primitives
from modules.html_rendering import inject_global_styles, render_html_fragment


# Scoped to Dashboard Game Plan renders — keep off the global cold-path CSS budget.
DAILY_GM_BRIEFING_CSS = """
<style>
.dg-daily-briefing-shell{background:var(--color-surface-primary);border:var(--border-width-default) solid var(--color-border);padding:var(--space-sm) var(--space-md);margin-block-end:var(--space-md)}
.dg-daily-briefing-quiet{align-items:baseline;background:var(--color-surface-primary);border:var(--border-width-default) solid var(--color-border);display:flex;flex-direction:column;gap:var(--space-2xs);padding:var(--space-sm) var(--space-md)}
.dg-daily-briefing-quiet strong{color:var(--color-success);font:var(--font-card-title)}
.dg-daily-briefing-quiet span{color:var(--color-text-secondary);font:var(--font-body);max-width:42rem}
.dg-daily-briefing-item{align-items:flex-start;border-block-end:var(--border-width-default) solid var(--color-border);display:grid;gap:var(--space-xs);grid-template-columns:auto minmax(0,1fr);padding-block:var(--space-xs) var(--space-sm)}
.dg-daily-briefing-item-primary{background:var(--color-surface-raised);border:var(--border-width-default) solid var(--color-border-strong);border-inline-start:3px solid var(--color-accent);margin-block-end:var(--space-sm);padding:var(--space-sm);padding-inline-start:var(--space-md)}
.dg-daily-briefing-item:not(.dg-daily-briefing-item-primary){padding-inline-start:var(--space-2xs)}
.dg-daily-briefing-index{color:var(--color-text-muted);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);min-width:1.1rem;padding-block-start:.15rem}
.dg-daily-briefing-kicker{color:var(--color-accent);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.dg-daily-briefing-headline{color:var(--color-text-primary);font:var(--font-card-title)}
.dg-daily-briefing-item-primary .dg-daily-briefing-headline{font:var(--font-section-title)}
.dg-daily-briefing-item-primary .dg-daily-briefing-kicker{color:var(--color-accent)}
.dg-daily-briefing-reason{color:var(--color-text-secondary);font:var(--type-caption-emphasis);max-width:36rem}
.dg-daily-briefing-rank{color:var(--color-text-muted);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);margin-block-start:var(--space-2xs)}
@media (max-width:430px){.dg-daily-briefing-reason{max-width:100%}}
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
    ui_primitives.render_section_header("Today's Game Plan", weight="primary")
    st.caption("Highest-signal actions for this league — open the owner surface to act.")

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
        is_primary = item.category == briefing_mod.CATEGORY_TOP_PRIORITY or index == 1
        primary_class = " dg-daily-briefing-item-primary" if is_primary else ""
        render_html_fragment(
            f"<div class='dg-daily-briefing-item{primary_class}'>"
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
        tier = "primary" if is_primary else "secondary"
        with st.container(key=f"dg_cta_{tier}_{key_prefix}_{index}"):
            st.button(
                cta,
                key=f"{key_prefix}_open_{index}_{item.category}_{item.source_id[:24]}",
                use_container_width=True,
                on_click=open_item,
                args=(item,),
            )
