"""Explicit server-only boundaries; never imported by the production app."""

from contextlib import contextmanager
from unittest.mock import patch


@contextmanager
def server_only_summary_tiles():
    """Exercise production's registration fallback without a browser component.

    AppTest replaces its components.v2 registry on each run but retains imported
    callables. It also cannot execute the component's JavaScript. Model only
    that unavailable registration, retaining the actual HTML renderer and its
    narrow exception handling. Browser validation owns taps and dialogs.
    """
    from modules import workspace_ui

    with patch.object(
        workspace_ui,
        "SUMMARY_TILE_TAP_COMPONENT",
        side_effect=ValueError("Component 'summary_tile_tap_grid' is not registered"),
    ):
        yield


@contextmanager
def server_only_player_quick_view():
    """Exercise the bridge's no-browser/no-request fallback in AppTest."""
    from modules import player_quick_view_bridge

    with patch.object(
        player_quick_view_bridge,
        "PLAYER_QUICK_VIEW_BRIDGE_COMPONENT",
        side_effect=ValueError("Component 'player_quick_view_parent_bridge' is not registered"),
    ):
        yield
