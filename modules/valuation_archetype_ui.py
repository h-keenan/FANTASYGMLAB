"""Canonical presentation for the active valuation archetype."""

from __future__ import annotations

from html import escape

import streamlit as st

from modules import ui_modal
from modules.valuation_archetypes import ValuationArchetype


MODAL_SURFACE = "workspace_valuation_archetype"


def archetype_modal_content(archetype: ValuationArchetype) -> ui_modal.ModalContent:
    return ui_modal.ModalContent(
        title=archetype.display_name,
        eyebrow="Valuation philosophy",
        summary=archetype.description,
        sections=(
            ui_modal.ModalSection("What it optimizes for", archetype.philosophy),
            ui_modal.ModalSection(
                "How to interpret it",
                (
                    "Values and recommendations use FantasyGM Lab's current balanced "
                    "dynasty approach. This label explains the lens; it does not "
                    "change today's calculations."
                ),
            ),
            ui_modal.ModalSection(
                "What's next",
                (
                    "Additional valuation philosophies are planned. Switching is "
                    "not available while Balanced Dynasty is the only active option."
                ),
            ),
        ),
        footer="Recommendations are currently evaluated using the Balanced Dynasty philosophy.",
    )


def render_workspace_archetype_affordance(
    archetype: ValuationArchetype,
    *,
    key: str,
    league_name: str = "",
    team_name: str = "",
    season: str = "",
) -> None:
    """Render compact Dashboard context: league, season, and changeable strategy."""

    identity_bits = [
        str(part).strip()
        for part in (league_name, team_name, season)
        if str(part or "").strip()
    ]
    meta = " · ".join(identity_bits)
    with st.container(key="dashboard_page_context"):
        st.markdown(
            "<div class='dg-dashboard-page-context'>"
            + (
                f"<div class='dg-dashboard-page-identity'>{escape(meta)}</div>"
                if meta
                else ""
            )
            + "</div>",
            unsafe_allow_html=True,
        )
        if st.button(
            f"Strategy: {archetype.display_name}",
            key=f"{key}_explain",
            type="tertiary",
            help=f"Learn how the {archetype.display_name} valuation philosophy is applied.",
        ):
            ui_modal.render_modal(
                archetype_modal_content(archetype),
                surface=MODAL_SURFACE,
            )
