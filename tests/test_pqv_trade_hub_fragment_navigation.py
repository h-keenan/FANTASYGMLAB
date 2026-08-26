"""PQV Open in Trade Hub must leave the dialog fragment via a full-app rerun."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
APP_SRC = (ROOT / "app.py").read_text(encoding="utf-8")


def test_pqv_open_in_trade_hub_promotes_fragment_click_to_app_rerun():
    content = APP_SRC[
        APP_SRC.index("def render_player_quick_view_content(") : APP_SRC.index(
            "def render_player_detail_content("
        )
    ]
    opener = APP_SRC[
        APP_SRC.index("def _open_trade_hub_for_player_focus(") : APP_SRC.index(
            "def render_player_detail_picker("
        )
    ]
    assert "on_click=_pqv_open_trade_hub" not in content
    assert "on_click=" not in content.split("Open in Trade Hub", 1)[1].split("st.button(", 1)[0]
    assert "trade_hub_clicked = st.button(" in content
    assert "if trade_hub_clicked:" in content
    assert "_open_trade_hub_for_player_focus(" in content
    assert 'st.rerun(scope="app")' in content
    assert content.index("trade_hub_clicked = st.button(") < content.index(
        "_open_trade_hub_for_player_focus("
    )
    assert content.index("_open_trade_hub_for_player_focus(") < content.index(
        'st.rerun(scope="app")'
    )
    assert "st.rerun(" not in opener
    assert "_clear_player_quick_view(" in opener
    assert '_commit_platform_destination("trade_hub", source="player_quick_view")' in opener
    assert 'st.session_state["_pqv_trade_hub_nav"] = True' in opener
    assert 'mark_interaction_milestone("pqv_trade_hub_click")' in content
    assert 'mark_interaction_milestone("full_app_rerun_requested")' in content
    assert 'mark_interaction_milestone("pqv_closed")' in opener
    assert 'mark_interaction_milestone("destination_committed")' in opener
    assert 'pop("_pqv_trade_hub_nav"' in APP_SRC
    assert 'mark_interaction_milestone("trade_hub_route_ready")' in APP_SRC


def test_pqv_trade_hub_commit_clears_dialog_before_full_rerun():
    import app

    state = {
        "platform_nav_page": "my_team",
        "player_quick_view_player_id": "p1",
        "player_quick_view_source_label": "Roster",
        "selected_league_name": "League A",
    }
    marks: list[str] = []
    with (
        patch.object(app.st, "session_state", state),
        patch("streamlit.session_state", state),
        patch.object(
            app,
            "resolve_active_league_context",
            return_value={
                "selected_league_id": "A",
                "selected_league_name": "League A",
                "username": "fixture",
            },
        ),
        patch.object(app, "_player_on_active_roster", return_value=True),
        patch.object(app, "_capture_workflow_handoff"),
        patch.object(app, "_commit_platform_destination"),
        patch.object(
            app.interaction_latency,
            "mark_interaction_milestone",
            side_effect=lambda name: marks.append(str(name)),
        ),
        patch("streamlit.rerun") as rerun,
    ):
        app._open_trade_hub_for_player_focus(
            player_row=pd.Series({"player_id": "p1", "name": "Player"}),
            selected_league_id="A",
            my_roster_id=1,
            username="fixture",
        )
        rerun.assert_not_called()

    for key in app.PLAYER_QUICK_VIEW_STATE_KEYS:
        assert key not in state
    assert state.get("platform_nav_page") == "my_team"
    assert state["trade_hub_focus_player_id_A"] == "p1"
    assert state["trade_hub_focus_mode_A"] == "my_player"
    assert state["_pqv_trade_hub_nav"] is True
    assert "pqv_closed" in marks
    assert "destination_committed" in marks
    assert marks.index("pqv_closed") < marks.index("destination_committed")

    if state.pop("_pqv_trade_hub_nav", None):
        app.interaction_latency.mark_interaction_milestone("trade_hub_route_ready")
    assert "_pqv_trade_hub_nav" not in state
