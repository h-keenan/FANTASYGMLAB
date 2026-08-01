"""Deterministic Streamlit interaction-floor harness with no customer data."""

from __future__ import annotations

import time

import streamlit as st


SCRIPT_STARTED = time.perf_counter()

st.set_page_config(page_title="Interaction latency harness", layout="centered")
st.title("Interaction latency harness")
st.caption("Synthetic controls only. No account, league, player, or network data.")

st.markdown(
    """
    <details data-interaction="local-disclosure">
      <summary>Local disclosure</summary>
      <p data-interaction-ready="local-disclosure">Local detail ready</p>
    </details>
    """,
    unsafe_allow_html=True,
)

with st.popover("Open navigation"):
    st.markdown('<span data-interaction-ready="navigation">Navigation ready</span>', unsafe_allow_html=True)


def _increment_state() -> None:
    st.session_state["interaction_state_version"] = (
        int(st.session_state.get("interaction_state_version", 0)) + 1
    )


st.button("Change local state", on_click=_increment_state)
state_version = int(st.session_state.get("interaction_state_version", 0))
st.markdown(
    (
        '<span data-interaction-ready="state" '
        f'data-version="{state_version}" '
        f'data-server-ms="{(time.perf_counter() - SCRIPT_STARTED) * 1000:.3f}">'
        f"State {state_version}</span>"
    ),
    unsafe_allow_html=True,
)


def _open_modal() -> None:
    st.session_state["interaction_modal_open"] = True


def _close_modal() -> None:
    st.session_state["interaction_modal_open"] = False


st.button("Open prepared modal", on_click=_open_modal)
if st.session_state.get("interaction_modal_open"):

    @st.dialog("Prepared detail", width="small", on_dismiss=_close_modal)
    def _prepared_dialog() -> None:
        st.markdown(
            (
                '<span data-interaction-ready="modal" '
                f'data-server-ms="{(time.perf_counter() - SCRIPT_STARTED) * 1000:.3f}">'
                "Prepared detail ready</span>"
            ),
            unsafe_allow_html=True,
        )

    _prepared_dialog()
