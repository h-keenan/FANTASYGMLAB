"""Server-only fallback must be intentional, repeatable, and scoped."""

from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from modules import workspace_ui
from scripts.apptest_support import server_only_summary_tiles


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
