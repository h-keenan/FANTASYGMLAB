"""Web Trade History page — gating, empty states, and row rendering.

modules.trade_outcomes_page is a pure web-side exposure of an already-built
backend/mobile feature (modules.trade_outcome_results +
services/mobile_api_service.py's /v1/trade-outcomes endpoints +
mobile/src/screens/TradeHistoryScreen.tsx). These tests pin that this module
reads the same `trade_outcomes` table the same way, gates on sign-in only
(no Premium gate, matching the mobile screen), and renders exactly the
honest "no verdict unless ready" behavior the mobile screen already has —
never a fabricated "checking..." placeholder.
"""

from __future__ import annotations

from unittest.mock import patch

from modules import trade_outcomes_page as page
from modules.ui_architecture import PLATFORM_DESTINATIONS


def test_trade_history_is_registered_in_nav():
    destinations = {entry.key: entry for entry in PLATFORM_DESTINATIONS}
    assert page.PAGE_KEY in destinations
    entry = destinations[page.PAGE_KEY]
    assert entry.label == page.NAV_LABEL
    assert entry.category == "CORE"


def test_signed_out_user_sees_sign_in_prompt_and_never_fetches():
    with patch("modules.trade_outcomes_page.auth_supabase.current_user_id", return_value=""):
        with patch(
            "modules.trade_outcomes_page.account_store.fetch_rows"
        ) as mock_fetch:
            with patch("modules.trade_outcomes_page.render_html_fragment") as mock_render:
                page.render_trade_history_page()

    mock_fetch.assert_not_called()
    mock_render.assert_called_once()
    assert "Sign in to see your Trade History" in mock_render.call_args.args[0]


def test_fetch_error_shows_unavailable_state():
    with patch("modules.trade_outcomes_page.auth_supabase.current_user_id", return_value="user-1"):
        with patch(
            "modules.trade_outcomes_page.auth_supabase.current_access_token", return_value="tok"
        ):
            with patch(
                "modules.trade_outcomes_page.account_store.fetch_rows",
                return_value=([], "boom"),
            ):
                with patch("modules.trade_outcomes_page.render_html_fragment") as mock_render:
                    page.render_trade_history_page()

    assert mock_render.call_count == 1
    assert "temporarily unavailable" in mock_render.call_args.args[0]


def test_no_rows_shows_no_history_yet_empty_state():
    with patch("modules.trade_outcomes_page.auth_supabase.current_user_id", return_value="user-1"):
        with patch(
            "modules.trade_outcomes_page.auth_supabase.current_access_token", return_value="tok"
        ):
            with patch(
                "modules.trade_outcomes_page.account_store.fetch_rows",
                return_value=([], ""),
            ):
                with patch("modules.trade_outcomes_page.render_html_fragment") as mock_render:
                    page.render_trade_history_page()

    assert mock_render.call_count == 1
    assert "No trade history yet" in mock_render.call_args.args[0]


def _row(**overrides):
    base = {
        "id": "outcome-1",
        "league_id": "league-1",
        "partner_team_name": "Team Chaos",
        "trade_summary": {
            "partner_team_name": "Team Chaos",
            "send": [{"name": "Player Sent", "position": "WR", "player_id": "1"}],
            "receive": [{"name": "Player Received", "position": "RB", "player_id": "2"}],
        },
        "outcome": "yes",
        "shared_at": "2025-01-05T00:00:00Z",
        "outcome_recorded_at": "2025-01-06T00:00:00Z",
        "result_summary": None,
        "result_computed_at": None,
    }
    base.update(overrides)
    return base


def test_ready_verdict_renders_badge_and_detail_text():
    row = _row(
        result_summary={
            "status": "ready",
            "verdict": "worked_out",
            "verdict_label": "This trade has worked out",
            "production": {"avg_net_per_week": 3.2},
            "value": {"net_delta_pct": 15.0},
        }
    )
    with patch("modules.trade_outcomes_page.auth_supabase.current_user_id", return_value="user-1"):
        with patch(
            "modules.trade_outcomes_page.auth_supabase.current_access_token", return_value="tok"
        ):
            with patch(
                "modules.trade_outcomes_page.account_store.fetch_rows",
                return_value=([row], ""),
            ):
                with patch("modules.trade_outcomes_page.render_html_fragment") as mock_render:
                    page.render_trade_history_page()

    rendered = " ".join(call.args[0] for call in mock_render.call_args_list)
    assert "Made it" in rendered
    assert "This trade has worked out" in rendered
    assert "+3.2 PPR pts/wk edge since the trade" in rendered
    assert "+15% value trend edge" in rendered
    assert "Player Sent" in rendered and "Player Received" in rendered


def test_insufficient_data_shows_no_verdict_badge_or_body():
    row = _row(result_summary={"status": "insufficient_data", "verdict": None})
    with patch("modules.trade_outcomes_page.auth_supabase.current_user_id", return_value="user-1"):
        with patch(
            "modules.trade_outcomes_page.auth_supabase.current_access_token", return_value="tok"
        ):
            with patch(
                "modules.trade_outcomes_page.account_store.fetch_rows",
                return_value=([row], ""),
            ):
                with patch("modules.trade_outcomes_page.render_html_fragment") as mock_render:
                    page.render_trade_history_page()

    rendered = " ".join(call.args[0] for call in mock_render.call_args_list)
    assert "Made it" in rendered
    assert "worked out" not in rendered.replace("This trade has worked out", "")
    assert "pts/wk edge" not in rendered


def test_non_yes_outcome_never_shows_a_verdict_even_if_result_present():
    row = _row(
        outcome="no",
        result_summary={
            "status": "ready",
            "verdict": "worked_out",
            "verdict_label": "This trade has worked out",
        },
    )
    with patch("modules.trade_outcomes_page.auth_supabase.current_user_id", return_value="user-1"):
        with patch(
            "modules.trade_outcomes_page.auth_supabase.current_access_token", return_value="tok"
        ):
            with patch(
                "modules.trade_outcomes_page.account_store.fetch_rows",
                return_value=([row], ""),
            ):
                with patch("modules.trade_outcomes_page.render_html_fragment") as mock_render:
                    page.render_trade_history_page()

    rendered = " ".join(call.args[0] for call in mock_render.call_args_list)
    assert "Didn&#x27;t make it" in rendered or "Didn't make it" in rendered
    assert "This trade has worked out" not in rendered


def test_asset_list_text_falls_back_to_nothing():
    assert page._asset_list_text(None) == "Nothing"
    assert page._asset_list_text([]) == "Nothing"
    assert page._asset_list_text([{"name": ""}]) == "Nothing"
    assert page._asset_list_text([{"name": "Real Player", "position": "QB"}]) == "Real Player (QB)"


def test_format_date_handles_bad_and_missing_input():
    assert page._format_date(None) == ""
    assert page._format_date("not-a-date") == ""
    assert page._format_date("2025-01-05T00:00:00Z") == "Jan 05, 2025"
