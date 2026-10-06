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

import time
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


def test_portfolio_fanout_preserves_saved_league_order_despite_uneven_completion():
    """render_portfolio_page parallelizes the per-league fan-out (stance +
    GM Targets + build_league_summary) across a thread pool instead of the
    old one-league-at-a-time loop. The page must still render leagues/
    failures in the SAME order account_store.fetch_saved_leagues returned
    them — even when a LATER saved league's (mocked) engine call finishes
    before an EARLIER one — proving the render order comes from zipping
    worker results back against `saved_rows`, never from whichever worker
    happens to finish first.
    """

    saved_rows = [
        {"league_id": "league-slow", "league_name": "Slow League"},
        {"league_id": "league-fast", "league_name": "Fast League"},
        {"league_id": "league-skip", "league_name": "Skip League"},
        {"league_id": "league-boom", "league_name": "Boom League"},
    ]

    # Only the FIRST saved league sleeps — everything else resolves near-
    # instantly, so if render order leaked from completion order instead
    # of input order, "Slow League" would render last instead of first.
    SLOW_LEAGUE_DELAY_S = 0.12

    def _fake_build_league_summary(*, league_id, **_kwargs):
        if league_id == "league-slow":
            time.sleep(SLOW_LEAGUE_DELAY_S)
        if league_id == "league-skip":
            return {"ok": False, "reason": "not_a_member_of_league"}
        if league_id == "league-boom":
            raise RuntimeError("Sleeper is unreachable")
        return {
            "ok": True,
            "reason": "",
            "roster_id": "1",
            "team_name": f"Team for {league_id}",
            "wins": 1,
            "losses": 2,
            "ties": 0,
            "health_flag": "Stable",
            "power_rank": 3,
            "power_rank_tied": False,
            "top_item": {
                "category": "need",
                "headline": f"Headline for {league_id}",
                "reason": "",
            },
        }

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
                                with patch(
                                    "modules.portfolio_page.render_html_fragment"
                                ) as mock_render:
                                    with patch("modules.portfolio_page.st.button", return_value=False):
                                        actions = portfolio_page.render_portfolio_page()

    assert actions == {"open_league": None}
    rendered_html = [call.args[0] for call in mock_render.call_args_list]

    # First render is the "couldn't load" banner — failed leagues named in
    # saved-league order (Skip before Boom), not completion order.
    assert "Skip League" in rendered_html[0]
    assert "Boom League" in rendered_html[0]
    assert rendered_html[0].index("Skip League") < rendered_html[0].index("Boom League")

    # Remaining renders are the per-league cards, in saved-league order
    # (Slow before Fast) even though "league-slow" was the one that took
    # longer to resolve.
    assert "Slow League" in rendered_html[1]
    assert "Fast League" in rendered_html[2]


def test_portfolio_fanout_runs_concurrently_and_is_faster_than_sequential():
    """The whole point of parallelizing the per-league fan-out: NUM_LEAGUES
    saved leagues should cost roughly the slowest ONE league's latency, not
    the sum of all of them. Each of the three per-league calls the old
    sequential loop made one at a time (stance, GM Targets,
    build_league_summary) sleeps DELAY_S here, so a sequential loop over
    NUM_LEAGUES leagues would cost roughly NUM_LEAGUES * 3 * DELAY_S;
    parallelized across the fan-out's thread pool (well under its worker
    cap), every league's slowest call overlaps and the whole render should
    finish in close to 3 * DELAY_S regardless of NUM_LEAGUES.
    """

    DELAY_S = 0.1
    NUM_LEAGUES = 6
    saved_rows = [
        {"league_id": f"league-{i}", "league_name": f"League {i}"} for i in range(NUM_LEAGUES)
    ]

    def _slow_stance(*_args, **_kwargs):
        time.sleep(DELAY_S)
        return ""

    def _slow_targets(*_args, **_kwargs):
        time.sleep(DELAY_S)
        return ()

    def _slow_build_league_summary(*, league_id, **_kwargs):
        time.sleep(DELAY_S)
        return {
            "ok": True,
            "reason": "",
            "roster_id": "1",
            "team_name": f"Team {league_id}",
            "wins": 1,
            "losses": 0,
            "ties": 0,
            "health_flag": "Stable",
            "power_rank": 1,
            "power_rank_tied": False,
            "top_item": None,
        }

    # What the OLD one-league-at-a-time loop would have cost — the
    # regression this test guards against.
    sequential_baseline_s = NUM_LEAGUES * 3 * DELAY_S

    with patch("modules.portfolio_page.premium.get_user_entitlement", return_value=premium.PREMIUM):
        with patch("modules.portfolio_page.auth_supabase.current_user_id", return_value="user-123"):
            with patch("modules.portfolio_page.auth_supabase.current_access_token", return_value="tok"):
                with patch(
                    "modules.portfolio_page.account_store.fetch_saved_leagues",
                    return_value=(saved_rows, ""),
                ):
                    with patch(
                        "modules.portfolio_page.team_stance.fetch_stance_for_league",
                        side_effect=_slow_stance,
                    ):
                        with patch(
                            "modules.portfolio_page.gm_targets.fetch_targets_for_league",
                            side_effect=_slow_targets,
                        ):
                            with patch(
                                "modules.portfolio_page.dashboard_engine.build_league_summary",
                                side_effect=_slow_build_league_summary,
                            ):
                                with patch("modules.portfolio_page.render_html_fragment"):
                                    with patch("modules.portfolio_page.st.button", return_value=False):
                                        started = time.perf_counter()
                                        actions = portfolio_page.render_portfolio_page()
                                        elapsed_s = time.perf_counter() - started

    assert actions == {"open_league": None}
    # Comfortably under the sequential baseline — a true parallel run lands
    # near 3 * DELAY_S regardless of NUM_LEAGUES; this generous margin
    # (well over half the sequential sum) absorbs CI scheduling jitter
    # without being able to pass a loop that secretly stayed sequential.
    assert elapsed_s < sequential_baseline_s * 0.6
