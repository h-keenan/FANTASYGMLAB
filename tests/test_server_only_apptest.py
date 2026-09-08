"""Server-only fallback must be intentional, repeatable, and scoped."""

from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from modules import workspace_ui
from scripts.apptest_support import server_only_summary_tiles
from scripts.apptest_support import server_only_player_quick_view


def test_summary_tiles_server_representation_survives_fresh_registries():
    original = workspace_ui.SUMMARY_TILE_TAP_COMPONENT
    application = AppTest.from_string(
        "from modules.workspace_ui import render_summary_tiles\n"
        "render_summary_tiles([{'label': 'Power Rank', 'value': '#2', "
        "'detail': 'League comparison'}])\n"
    )
    with server_only_summary_tiles():
        for _ in range(2):
            application.run()
            assert not application.exception
            html = '\n'.join(element.value for element in application.markdown)
            assert 'summary-tile-grid' in html
            assert 'Power Rank' in html
            assert '#2' in html
    assert workspace_ui.SUMMARY_TILE_TAP_COMPONENT is original


def test_summary_tiles_does_not_hide_unrelated_component_errors():
    with patch.object(
        workspace_ui, 'SUMMARY_TILE_TAP_COMPONENT', side_effect=ValueError('bad data')
    ), pytest.raises(ValueError, match='bad data'):
        workspace_ui.render_summary_tiles([{'label': 'Power Rank', 'value': '#2'}])


def test_player_bridge_server_fallback_is_scoped_and_has_no_request():
    from modules import player_quick_view_bridge as bridge

    original = bridge.PLAYER_QUICK_VIEW_BRIDGE_COMPONENT
    application = AppTest.from_string(
        "import streamlit as st\n"
        "from modules.player_quick_view_bridge import consume_player_quick_view_request\n"
        "assert consume_player_quick_view_request(st.session_state) == {}\n"
    )
    with server_only_player_quick_view():
        for _ in range(2):
            application.run()
            assert not application.exception
    assert bridge.PLAYER_QUICK_VIEW_BRIDGE_COMPONENT is original
    with patch.object(bridge, "PLAYER_QUICK_VIEW_BRIDGE_COMPONENT", side_effect=ValueError("bad data")):
        with pytest.raises(ValueError, match="bad data"):
            bridge.consume_player_quick_view_request({})
