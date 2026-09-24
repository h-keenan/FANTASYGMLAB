"""Trade Analyzer assembly UI — roster browse, not search-first dropdowns.

The assembly and Analyze owner intentionally share one normal Streamlit run.
Fragment-only mutation left the outer Analyze button stale in production.
"""

from __future__ import annotations

from html import escape
from typing import Any, Callable

import streamlit as st

from modules import trade_analyzer_assembly as assembly
from modules import trade_analyzer_builder as analyzer_builder
from modules.html_rendering import render_html_fragment
from modules.league_workspace_ui import _format_score as default_format_score


def _ensure_filter_defaults(side: str) -> None:
    kind_key = f"toa_{side}_kind"
    pos_key = f"toa_{side}_pos"
    if st.session_state.get(kind_key) not in assembly.KIND_OPTIONS:
        st.session_state[kind_key] = assembly.KIND_PLAYERS
    if st.session_state.get(pos_key) not in assembly.POSITION_OPTIONS:
        st.session_state[pos_key] = "ALL"


def _render_selected_package(
    *,
    package_key: str,
    side: str,
    empty_text: str,
    format_score: Callable[[Any], str],
) -> None:
    assets = list(st.session_state.get(package_key) or [])
    if not assets:
        render_html_fragment(f"<div class='toa-empty-package'>{empty_text}</div>")
        return
    st.markdown("<div class='toa-chip-list'>", unsafe_allow_html=True)
    for idx, asset in enumerate(assets):
        identity = analyzer_builder.asset_identity(asset)
        token = analyzer_builder.widget_key_token(identity or f"{side}_{idx}")
        chip_cols = st.columns([5, 1])
        with chip_cols[0]:
            st.markdown(
                analyzer_builder.chip_html(asset, format_score=format_score),
                unsafe_allow_html=True,
            )
        with chip_cols[1]:
            st.button(
                "×",
                key=f"toa_rm_{side}_{idx}_{token}",
                use_container_width=True,
                help="Remove asset",
                on_click=assembly.mutate_package,
                kwargs={
                    "state": st.session_state,
                    "package_key": package_key,
                    "action": "remove",
                    "index": idx,
                },
            )
    st.markdown("</div>", unsafe_allow_html=True)


def _render_filter_toolbar(*, side: str) -> str:
    render_html_fragment(
        "<div class='toa-toolbar' data-toa-toolbar='1'>"
        "<span class='toa-toolbar-kicker'>Roster</span>"
        "</div>"
    )
    kind = st.radio(
        "Players or picks",
        list(assembly.KIND_OPTIONS),
        key=f"toa_{side}_kind",
        horizontal=True,
        label_visibility="collapsed",
    )
    kind_text = str(kind or assembly.KIND_PLAYERS)
    if kind_text == assembly.KIND_PLAYERS:
        st.radio(
            "Position",
            list(assembly.POSITION_OPTIONS),
            key=f"toa_{side}_pos",
            horizontal=True,
            label_visibility="collapsed",
        )
    return kind_text


def _render_side_browser(
    *,
    side: str,
    package_key: str,
    title: str,
    caption: str,
    empty_text: str,
    partner_roster_id: str,
    my_roster_id: str,
    enabled: bool,
    disabled_reason: str,
    format_score: Callable[[Any], str],
) -> None:
    block_mod = "toa-block-receive" if side == "receive" else "toa-block-send"
    render_html_fragment(
        f"<div class='toa-block {block_mod}'>"
        f"<div class='toa-block-kicker'>Side</div>"
        f"<div class='toa-block-title'>{title}</div>"
        f"<div class='toa-side-caption'>{caption}</div>"
        "</div>"
    )
    _render_selected_package(
        package_key=package_key,
        side=side,
        empty_text=empty_text,
        format_score=format_score,
    )
    if not enabled:
        st.caption(disabled_reason)
        return
    _ensure_filter_defaults(side)
    kind = _render_filter_toolbar(side=side)
    search_key = f"trade_{side}_search_query"
    query = st.text_input(
        "Search roster",
        key=search_key,
        placeholder="Search roster",
        autocomplete="off",
        label_visibility="collapsed",
    )
    catalog = assembly.catalog_for_side(st.session_state, side=side)
    this_selected = analyzer_builder.package_identities(st.session_state.get(package_key))
    other_key = (
        assembly.SEND_KEY if package_key == assembly.RECEIVE_KEY else assembly.RECEIVE_KEY
    )
    other_selected = analyzer_builder.package_identities(st.session_state.get(other_key))
    visible = assembly.filter_assets(
        catalog,
        kind=kind,
        position=str(st.session_state.get(f"toa_{side}_pos") or "ALL"),
        query=str(query or ""),
        exclude_identities=other_selected,
    )
    noun = "picks" if kind == assembly.KIND_PICKS else "players"
    st.caption(f"{len(visible)} {noun} on this roster")
    with st.container(key=f"toa_roster_{side}"):
        if not visible:
            st.caption("No matching assets on this roster.")
        for asset in visible:
            identity = analyzer_builder.asset_identity(asset)
            selected = bool(identity and identity in this_selected)
            token = analyzer_builder.widget_key_token(identity)
            row_cols = st.columns([6, 1])
            with row_cols[0]:
                st.markdown(
                    analyzer_builder.result_row_html(
                        asset, selected=selected, format_score=format_score
                    ),
                    unsafe_allow_html=True,
                )
            with row_cols[1]:
                st.button(
                    "Added" if selected else "Add",
                    key=f"toa_add_{side}_{token}",
                    use_container_width=True,
                    disabled=selected,
                    help="Already in this package" if selected else "Add to package",
                    on_click=assembly.mutate_package,
                    kwargs={
                        "state": st.session_state,
                        "asset": asset,
                        "package_key": package_key,
                        "action": "add",
                        "partner_roster_id": partner_roster_id,
                        "my_roster_id": my_roster_id,
                    },
                )


def render_trade_analyzer_assembly(
    *,
    my_roster_id: str,
    partner_roster_id: str,
    partner_name: str = "",
    league_ready: bool = True,
    format_score: Callable[[Any], str] | None = None,
) -> None:
    """You send ↔ You receive workspace under the page's canonical state owner."""

    score_fn = format_score or default_format_score

    def _trade_analyzer_assembly() -> None:
        notice = str(st.session_state.get("trade_receive_notice") or "")
        feedback = st.session_state.pop("trade_analyzer_add_feedback", {}) or {}
        added_identity = str(feedback.get("identity") or "") if isinstance(feedback, dict) else ""
        added = str(feedback.get("label") or "") if isinstance(feedback, dict) else ""
        canonical_identities = analyzer_builder.package_identities(
            list(st.session_state.get(assembly.SEND_KEY) or [])
            + list(st.session_state.get(assembly.RECEIVE_KEY) or [])
        )
        if added and added_identity and added_identity in canonical_identities:
            render_html_fragment(
                f"<div class='toa-add-feedback'>Added {escape(added)}</div>"
            )
        receive_caption = (
            f"Browsing {partner_name}"
            if partner_name
            else "Browsing the partner roster"
        )
        st.markdown(
            "<div class='toa-workspace toa-assembly-stack' data-toa-workspace='1'>"
            "<div class='toa-workspace-kicker'>Build the trade</div>"
            "<div class='toa-workspace-swap' aria-hidden='true'>You send ↔ You receive</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        send_col, receive_col = st.columns(2)
        with send_col:
            _render_side_browser(
                side="send",
                package_key=assembly.SEND_KEY,
                title="You send",
                caption="From your roster",
                empty_text="Nothing queued to send. Add from your roster below.",
                partner_roster_id=str(partner_roster_id or ""),
                my_roster_id=str(my_roster_id or ""),
                enabled=bool(league_ready and my_roster_id),
                disabled_reason="Select a league and load your roster first.",
                format_score=score_fn,
            )
        with receive_col:
            _render_side_browser(
                side="receive",
                package_key=assembly.RECEIVE_KEY,
                title="You receive",
                caption=escape(receive_caption),
                empty_text="Nothing queued to receive. Add from their roster below.",
                partner_roster_id=str(partner_roster_id or ""),
                my_roster_id=str(my_roster_id or ""),
                enabled=bool(league_ready and partner_roster_id),
                disabled_reason=(
                    "Select a partner to browse their roster."
                    if league_ready
                    else "Select a league and load your roster first."
                ),
                format_score=score_fn,
            )
        if notice:
            st.warning(notice)

    _trade_analyzer_assembly()
