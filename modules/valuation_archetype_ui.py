"""Canonical presentation for the active valuation archetype."""

from __future__ import annotations

from html import escape

import streamlit as st

from modules import league_format_context
from modules import ui_modal
from modules.valuation_archetypes import ValuationArchetype


MODAL_SURFACE = "workspace_valuation_archetype"
CANONICAL_LENS_SESSION_KEY = "league_type"
SUPPORTED_VALUATION_LENSES = ("Dynasty", "Rebuild", "Non-Dynasty")
_LENS_OPTION_HELP = {
    "Dynasty": "balanced long-term value",
    "Rebuild": "youth and draft capital",
    "Non-Dynasty": "current-season production",
}


def archetype_modal_content(
    archetype: ValuationArchetype,
    *,
    league_settings: dict | None = None,
) -> ui_modal.ModalContent:
    format_name = league_format_context.format_display_name(league_settings)
    lens = league_format_context.valuation_lens_label(
        archetype.badge, archetype.display_name
    )
    return ui_modal.ModalContent(
        title=f"{format_name} · Valuation: {lens}",
        eyebrow="League format and valuation lens",
        summary=(
            f"This league is {format_name}. {lens} is the valuation philosophy "
            "used to score players — not the league's competitive format, and not "
            "the roster posture (Contender / Rebuild) shown on My Team."
        ),
        sections=(
            ui_modal.ModalSection(
                "Valuation engine",
                f"{archetype.display_name}: {archetype.description}",
            ),
            ui_modal.ModalSection("What the valuation lens optimizes for", archetype.philosophy),
            ui_modal.ModalSection(
                "How to interpret it",
                (
                    "League format is the Sleeper competition type (Redraft, Keeper, or Dynasty). "
                    "Valuation is how FantasyGM Lab scores players. Roster posture is a separate "
                    "construction read of your team."
                ),
            ),
            ui_modal.ModalSection(
                "What's next",
                (
                    "Additional valuation philosophies are planned. Switching is "
                    "not available while Balanced is the only active valuation option."
                ),
            ),
        ),
        footer=f"Format: {format_name}. Valuation: {lens}.",
    )


def current_valuation_lens(session_state=None) -> str:
    """Return the canonical evaluation lens from session state."""

    state = st.session_state if session_state is None else session_state
    lens = str(state.get(CANONICAL_LENS_SESSION_KEY) or "").strip()
    if lens in SUPPORTED_VALUATION_LENSES:
        return lens
    return "Dynasty"


def render_workspace_archetype_affordance(
    archetype: ValuationArchetype,
    *,
    key: str,
    league_name: str = "",
    team_name: str = "",
    season: str = "",
    league_settings: dict | None = None,
) -> None:
    """Render league format plus valuation lens — never as if they were one strategy.

    Desktop and mobile mutate the same Streamlit key ``league_type``. This is the
    only widget that owns that field; the collapsed sidebar must not remount it.
    """

    format_name = league_format_context.format_display_name(league_settings)
    identity_bits = [
        str(part).strip()
        for part in (league_name, team_name, season)
        if str(part or "").strip()
    ]
    meta = " · ".join(identity_bits)
    active_lens = current_valuation_lens()
    if CANONICAL_LENS_SESSION_KEY not in st.session_state:
        st.session_state[CANONICAL_LENS_SESSION_KEY] = active_lens
    with st.container(key="dashboard_page_context"):
        if meta:
            st.markdown(
                "<div class='dg-dashboard-page-context'>"
                f"<div class='dg-dashboard-page-identity'>{escape(meta)}</div>"
                "</div>",
                unsafe_allow_html=True,
            )
        st.selectbox(
            "Valuation lens",
            SUPPORTED_VALUATION_LENSES,
            key=CANONICAL_LENS_SESSION_KEY,
            format_func=lambda lens: (
                f"{lens} — {_LENS_OPTION_HELP.get(str(lens), 'valuation')}"
            ),
        )
        if st.button(
            "How valuation works",
            key=f"{key}_explain",
            type="tertiary",
        ):
            ui_modal.render_modal(
                archetype_modal_content(archetype, league_settings=league_settings),
                surface=MODAL_SURFACE,
            )
