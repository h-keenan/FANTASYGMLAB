"""Web Portfolio page — gating + aggregation/isolation behavior.

modules.portfolio_page.render_portfolio_page reuses
modules.dashboard_engine.build_league_summary (the same per-league engine
GET /v1/leagues/{id}/dashboard and GET /v1/portfolio already use) once per
saved league. These tests pin the web page's own gating/aggregation loop —
Free gets an upsell and never runs the (expensive) per-league engine,
Premium gets one row per saved league, and one broken league never blanks
the rest. Engine-composition correctness itself is covered by the Dashboard
tests in tests/test_mobile_api_service.py.
"""

from __future__ import annotations

from unittest.mock import patch

from modules import portfolio_page, premium
from modules.ui_architecture import PLATFORM_DESTINATIONS


def test_portfolio_is_registered_in_nav():
    destinations = {page.key: page for page in PLATFORM_DESTINATIONS}
    assert portfolio_page.PAGE_KEY in destinations
    page = destinations[portfolio_page.PAGE_KEY]
    assert page.label == portfolio_page.NAV_LABEL
    assert page.category == "CORE"


def test_portfolio_free_user_gets_an_upsell_and_never_builds_summaries():
    def _must_not_run(**_kwargs):
        raise AssertionError("build_league_summary should not run for a Free caller")

    with patch("modules.portfolio_page.premium.get_user_entitlement", return_value=premium.FREE):
        with patch("modules.portfolio_page.dashboard_engine.build_league_summary", _must_not_run):
            with patch("modules.portfolio_page.premium.render_premium_lock") as mock_lock:
                actions = portfolio_page.render_portfolio_page()

    assert actions == {"open_league": None}
    mock_lock.assert_called_once()
    assert mock_lock.call_args.args[0] == portfolio_page.PORTFOLIO_UPSELL_TITLE


def test_portfolio_premium_user_with_no_saved_leagues_is_empty_not_broken():
    with patch("modules.portfolio_page.premium.get_user_entitlement", return_value=premium.PREMIUM):
        with patch("modules.portfolio_page.auth_supabase.current_user_id", return_value="user-123"):
            with patch("modules.portfolio_page.auth_supabase.current_access_token", return_value="tok"):
                with patch(
                    "modules.portfolio_page.account_store.fetch_saved_leagues",
                    return_value=([], ""),
                ):
                    with patch("modules.portfolio_page.render_html_fragment") as mock_render:
                        actions = portfolio_page.render_portfolio_page()

    assert actions == {"open_league": None}
    # The "no saved leagues yet" empty state, not a Premium upsell or an error.
    assert mock_render.call_count == 1
    assert "No saved leagues yet" in mock_render.call_args.args[0]


def test_portfolio_aggregates_across_saved_leagues_and_isolates_one_failure():
    saved_rows = [
        {"league_id": "league-ok", "league_name": "The Ok League"},
        {"league_id": "league-skip", "league_name": "The Skip League"},
        {"league_id": "league-boom", "league_name": "The Boom League"},
    ]

    def _fake_build_league_summary(*, league_id, **_kwargs):
        if league_id == "league-ok":
            return {
                "ok": True,
                "reason": "",
                "roster_id": "1",
                "team_name": "Ok Team",
                "wins": 7,
                "losses": 3,
                "ties": 0,
                "health_flag": "Stable",
                "power_rank": 2,
                "power_rank_tied": False,
                "top_item": {
                    "category": "need",
                    "headline": "Add RB2 depth",
                    "reason": "Thin behind your starter.",
                },
            }
        if league_id == "league-skip":
            return {"ok": False, "reason": "not_a_member_of_league"}
        raise RuntimeError("Sleeper is unreachable")

    with patch("modules.portfolio_page.premium.get_user_entitlement", return_value=premium.PREMIUM):
        with patch("modules.portfolio_page.auth_supabase.current_user_id", return_value="user-123"):
            with patch("modules.portfolio_page.auth_supabase.current_access_token", return_value="tok"):
                with patch(
                    "modules.portfolio_page.account_store.fetch_saved_leagues",
                    return_value=(saved_rows, ""),
                ):
                    with patch(
                        "modules.portfolio_page.team_stance.fetch_stance_for_league", return_value=""
                    ):
                        with patch(
                            "modules.portfolio_page.gm_targets.fetch_targets_for_league", return_value=()
                        ):
                            with patch(
                                "modules.portfolio_page.dashboard_engine.build_league_summary",
                                side_effect=_fake_build_league_summary,
                            ):
                                with patch("modules.portfolio_page.render_html_fragment") as mock_render:
                                    with patch("modules.portfolio_page.st.button", return_value=False):
                                        actions = portfolio_page.render_portfolio_page()

    assert actions == {"open_league": None}
    rendered_html = "\n".join(call.args[0] for call in mock_render.call_args_list)
    # The one league that succeeded is rendered...
    assert "Ok Team" in rendered_html
    assert "The Ok League" in rendered_html
    assert "Add RB2 depth" in rendered_html
    # ...and the two that didn't are named in the "couldn't load" note rather
    # than silently vanishing or blanking the whole page.
    assert "The Skip League" in rendered_html
    assert "The Boom League" in rendered_html
    assert "Couldn&#x27;t load 2 leagues" in rendered_html
