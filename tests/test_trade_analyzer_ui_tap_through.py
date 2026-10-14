"""Site-wide tappability audit follow-up (coridian_: "keep working on
everything that is unfinished"): Trade Analyzer's roster-browse "Add" rows
and queued trade-package chips previously rendered a real, data-player-id-
bearing identity chip via a plain st.markdown -- never routed through the
tap-grid component that actually listens for a click -- right next to the
working native Add/x st.button in the same st.columns row.

Each row/chip now gets its own single-row render_tappable_player_html() call
(NOT a batched whole-list grid, which can't have 40 individual native
buttons embedded inside it) sitting beside the unchanged native button, the
same per-row coexistence pattern PR #1059 used for GM Targets' card-level
tap-through alongside its own native "Open player" button.
"""

from __future__ import annotations

from unittest.mock import Mock

import streamlit as st

from modules import trade_analyzer_assembly as assembly
from modules import trade_analyzer_ui as ui


def _player(pid: str, name: str, *, owner: str = "me", position: str = "WR", team: str = "DAL"):
    return {
        "asset_type": "player",
        "player_id": pid,
        "name": name,
        "label": name,
        "position": position,
        "team": team,
        "score": 1200,
        "owner_roster_id": owner,
    }


def _pick(label: str, *, owner: str = "me"):
    return {
        "asset_type": "pick",
        "label": label,
        "name": label,
        "season": 2027,
        "round": 1,
        "score": 800,
        "owner_roster_id": owner,
    }


def _reset_state():
    st.session_state.clear()
    st.session_state[assembly.SEND_KEY] = []
    st.session_state[assembly.RECEIVE_KEY] = []
    st.session_state["toa_send_kind"] = assembly.KIND_PLAYERS
    st.session_state["toa_send_pos"] = "ALL"
    st.session_state["toa_receive_kind"] = assembly.KIND_PLAYERS
    st.session_state["toa_receive_pos"] = "ALL"


def _seed_catalog(*, side: str, assets: list[dict]):
    key = (
        assembly.CATALOG_PLAYERS_PARTNER
        if side == "receive"
        else assembly.CATALOG_PLAYERS_ME
    )
    players = [asset for asset in assets if asset.get("asset_type") != "pick"]
    picks = [asset for asset in assets if asset.get("asset_type") == "pick"]
    st.session_state[key] = players
    pick_key = assembly.CATALOG_PICKS_PARTNER if side == "receive" else assembly.CATALOG_PICKS_ME
    st.session_state[pick_key] = picks


def test_roster_browse_row_routes_player_identity_through_tap_grid():
    _reset_state()
    _seed_catalog(side="send", assets=[_player("p1", "Player A")])
    tap = Mock(return_value="p1")
    open_quick_view = Mock()

    ui._render_side_browser(
        side="send",
        package_key=assembly.SEND_KEY,
        title="You send",
        caption="From your roster",
        empty_text="empty",
        partner_roster_id="partner",
        my_roster_id="me",
        enabled=True,
        disabled_reason="",
        format_score=lambda value: str(value),
        render_tappable_player_html=tap,
        open_player_quick_view=open_quick_view,
    )

    tap.assert_called_once()
    call_kwargs = tap.call_args.kwargs
    assert "data-player-id='p1'" in call_kwargs["html"]
    assert "toa_row_tap_send_" in call_kwargs["key_prefix"]
    open_quick_view.assert_called_once_with(
        "p1",
        source_label="Trade Analyzer",
        source_note="Inspect this player before adding them to the trade.",
    )


def test_roster_browse_row_falls_back_to_plain_markdown_without_tap_callables():
    """Caller not wiring the tap callables must render exactly as before --
    no tap grid invoked, no raised exception from the native Add button."""

    _reset_state()
    _seed_catalog(side="send", assets=[_player("p1", "Player A")])

    # No render_tappable_player_html / open_player_quick_view passed --
    # defaults are None, same as production callers that haven't wired PQV.
    ui._render_side_browser(
        side="send",
        package_key=assembly.SEND_KEY,
        title="You send",
        caption="From your roster",
        empty_text="empty",
        partner_roster_id="partner",
        my_roster_id="me",
        enabled=True,
        disabled_reason="",
        format_score=lambda value: str(value),
    )


def test_roster_browse_row_does_not_tap_grid_a_pick():
    """Picks have no player_id / data-player-id, so a click target would be
    inert anyway -- the row must keep its plain render, not spin up a tap
    grid for nothing."""

    _reset_state()
    _seed_catalog(side="send", assets=[_pick("2027 1st")])
    tap = Mock(return_value="")
    open_quick_view = Mock()

    ui._render_side_browser(
        side="send",
        package_key=assembly.SEND_KEY,
        title="You send",
        caption="From your roster",
        empty_text="empty",
        partner_roster_id="partner",
        my_roster_id="me",
        enabled=True,
        disabled_reason="",
        format_score=lambda value: str(value),
        render_tappable_player_html=tap,
        open_player_quick_view=open_quick_view,
    )

    tap.assert_not_called()
    open_quick_view.assert_not_called()


def test_roster_browse_row_wires_interactive_flag_into_injected_compact_player_row_html():
    """When the caller also injects compact_player_row_html (the production
    shape, from app.py's _compact_player_row_html), the row must ask for
    interactive=True so football_assets.player_card_html() actually emits
    the data-player-id/player-card-tappable markup -- this was the literal
    gap: the callable existed and was wired, but nothing ever told it the
    row should be interactive."""

    _reset_state()
    _seed_catalog(side="send", assets=[_player("p1", "Player A")])
    calls: list[dict] = []

    def _fake_compact_player_row_html(row, **kwargs):
        calls.append(kwargs)
        return f"<div class='compact-player-row' data-player-id='{row.get('player_id')}'>{row.get('name')}</div>"

    tap = Mock(return_value="")
    ui._render_side_browser(
        side="send",
        package_key=assembly.SEND_KEY,
        title="You send",
        caption="From your roster",
        empty_text="empty",
        partner_roster_id="partner",
        my_roster_id="me",
        enabled=True,
        disabled_reason="",
        format_score=lambda value: str(value),
        compact_player_row_html=_fake_compact_player_row_html,
        render_tappable_player_html=tap,
        open_player_quick_view=Mock(),
    )

    assert calls[0]["interactive"] is True


def test_queued_package_chip_routes_player_identity_through_tap_grid():
    _reset_state()
    st.session_state[assembly.SEND_KEY] = [_player("p1", "Player A")]
    tap = Mock(return_value="p1")
    open_quick_view = Mock()

    ui._render_selected_package(
        package_key=assembly.SEND_KEY,
        side="send",
        empty_text="empty",
        format_score=lambda value: str(value),
        render_tappable_player_html=tap,
        open_player_quick_view=open_quick_view,
    )

    tap.assert_called_once()
    call_kwargs = tap.call_args.kwargs
    assert "data-player-id='p1'" in call_kwargs["html"]
    assert "toa_chip_tap_send_" in call_kwargs["key_prefix"]
    open_quick_view.assert_called_once_with(
        "p1",
        source_label="Trade Analyzer",
        source_note="Inspect this player queued in your trade package.",
    )


def test_queued_package_chip_does_not_tap_grid_a_pick():
    _reset_state()
    st.session_state[assembly.SEND_KEY] = [_pick("2027 1st")]
    tap = Mock(return_value="")
    open_quick_view = Mock()

    ui._render_selected_package(
        package_key=assembly.SEND_KEY,
        side="send",
        empty_text="empty",
        format_score=lambda value: str(value),
        render_tappable_player_html=tap,
        open_player_quick_view=open_quick_view,
    )

    tap.assert_not_called()
    open_quick_view.assert_not_called()


def test_queued_package_chip_falls_back_to_plain_markdown_without_tap_callables():
    _reset_state()
    st.session_state[assembly.SEND_KEY] = [_player("p1", "Player A")]

    ui._render_selected_package(
        package_key=assembly.SEND_KEY,
        side="send",
        empty_text="empty",
        format_score=lambda value: str(value),
    )
