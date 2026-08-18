"""League Memory / Weekly Recap V1 — deterministic editorial layer over History."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from modules import league_history as history
from modules import league_recaps
from modules import league_recaps_ui
from modules.app_styles import APP_CSS
from modules.league_recaps_styles import LEAGUE_RECAPS_CSS
from modules.notification_center import compose_activity_inbox
from modules.ui_architecture import PLATFORM_DESTINATIONS


ROOT = Path(__file__).resolve().parents[1]

PROFILES = {
    "1": {"team_name": "War Room", "username": "alpha", "owner_name": "Alpha"},
    "2": {"team_name": "Lakefront", "username": "beta", "owner_name": "Beta"},
    "3": {"team_name": "Quiet Club", "username": "gamma", "owner_name": "Gamma"},
}
PLAYERS = {
    "p1": {"name": "Ja'Marr Chase", "position": "WR", "team": "CIN"},
    "p2": {"name": "Breece Hall", "position": "RB", "team": "NYJ"},
    "p3": {"name": "Trey McBride", "position": "TE", "team": "ARI"},
}


def _tx(raw, *, week=7, season="2025", league_id="L1"):
    return history.normalize_transaction(
        raw,
        league_id=league_id,
        season=season,
        week=week,
        profiles=PROFILES,
        player_lookup=PLAYERS,
    )


def _trade(week=7):
    return _tx(
        {
            "transaction_id": f"t-{week}",
            "type": "trade",
            "status": "complete",
            "status_updated": 1_700_000_000_000,
            "roster_ids": [1, 2],
            "adds": {"p1": 2, "p2": 1},
            "drops": {"p2": 2, "p1": 1},
            "draft_picks": [],
        },
        week=week,
    )


def _waiver(week=7, bid=42, tx_id=""):
    return _tx(
        {
            "transaction_id": tx_id or f"w-{week}-{bid}",
            "type": "waiver",
            "status": "complete",
            "status_updated": 1_700_000_100_000,
            "roster_ids": [1],
            "adds": {"p3": 1},
            "drops": {},
            "settings": {"waiver_bid": bid},
            "draft_picks": [],
        },
        week=week,
    )


def _matchups(week=7):
    return [
        {"week": week, "roster_id": 1, "matchup_id": 10, "points": 148.4, "team_name": "War Room"},
        {"week": week, "roster_id": 2, "matchup_id": 10, "points": 110.2, "team_name": "Lakefront"},
        {"week": week, "roster_id": 3, "matchup_id": 11, "points": 91.0, "team_name": "Quiet Club"},
        {"week": week, "roster_id": 4, "matchup_id": 11, "points": 88.5, "team_name": "Other"},
    ]


def test_completed_week_requires_last_scored_and_points():
    league = {"settings": {"last_scored_leg": 7, "leg": 8}}
    assert league_recaps.completed_recap_week(league, _matchups(7)) == 7
    assert league_recaps.completed_recap_week({"settings": {"leg": 8}}, _matchups(7)) == 0
    incomplete = [
        {"week": 8, "roster_id": 1, "matchup_id": 1, "points": 0},
        {"week": 8, "roster_id": 2, "matchup_id": 1, "points": 0},
    ]
    assert league_recaps.completed_recap_week(
        {"settings": {"last_scored_leg": 8}}, incomplete
    ) == 0


def test_fingerprint_is_stable_and_changes_with_events():
    first = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_trade(), _waiver()],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    second = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_trade(), _waiver()],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    assert first["fingerprint"] == second["fingerprint"]
    changed = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_trade()],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    assert changed["fingerprint"] != first["fingerprint"]


def test_busy_week_omits_nothing_supported_and_does_not_fabricate():
    recap = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_trade(), _waiver(), _waiver(bid=11)],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    types = {story["story_type"] for story in recap["stories"]}
    assert league_recaps.STORY_PERFORMANCE in types
    assert league_recaps.STORY_MATCHUP in types
    assert league_recaps.STORY_WAIVER in types
    assert league_recaps.STORY_TRADE in types
    assert recap["stories"][0]["metric_value"] == "148.4"
    waiver = next(story for story in recap["stories"] if story["story_type"] == "waiver")
    assert "$42" in waiver["metric_value"]
    trade = next(story for story in recap["stories"] if story["story_type"] == "trade")
    assert trade["editorial_label"] == "Too Early to Tell"
    assert trade["historical_value_available"] is False
    assert all(lens["lens"] != league_recaps.VALUE_LENS_AT_TRADE for lens in trade["value_lenses"])


def test_sparse_week_omits_empty_categories():
    recap = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=3,
        transactions=[],
        matchups=_matchups(3),
        profiles=PROFILES,
    )
    types = {story["story_type"] for story in recap["stories"]}
    assert "waiver" not in types
    assert "trade" not in types
    assert "activity" not in types
    assert "performance" in types
    html = league_recaps_ui.recap_edition_html(recap)
    assert "Waiver winner" not in html
    assert "Trade of the week" not in html or "trade" not in types


def test_no_trades_week_and_quiet_activity():
    recap = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_waiver()],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    types = {story["story_type"] for story in recap["stories"]}
    assert "trade" not in types
    assert "activity" not in types
    assert "waiver" in types


def test_most_active_requires_repeated_moves():
    extra = _tx(
        {
            "transaction_id": "fa-7",
            "type": "free_agent",
            "status": "complete",
            "roster_ids": [1],
            "adds": {"p2": 1},
            "drops": {},
            "settings": {"waiver_bid": 1},
            "draft_picks": [],
        }
    )
    recap = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_waiver(), extra],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    activity = next(story for story in recap["stories"] if story["story_type"] == "activity")
    assert activity["primary_team"] == "War Room"
    assert activity["metric_value"] == "2"


def test_archive_orders_this_week_then_previous():
    archive = league_recaps.archive_weeks(latest=7, available=(3, 5, 7, 2))
    assert archive["this_week"] == [7]
    assert archive["previous_weeks"] == [5, 3, 2]


def test_history_deep_links_and_session_cache_do_not_duplicate():
    session: dict = {}
    first = league_recaps.get_or_build_weekly_recap(
        session,
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_trade(), _waiver()],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    second = league_recaps.get_or_build_weekly_recap(
        session,
        league_id="L1",
        season="2025",
        week=7,
        transactions=[_trade(), _waiver()],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    assert first["recap_id"] == second["recap_id"]
    assert len(session[league_recaps.SESSION_CACHE_KEY]) == 1
    notice = league_recaps.recap_notice_record(session)
    assert notice is not None
    assert notice["id"].startswith("league-recap:")
    trade = next(story for story in first["stories"] if story["story_type"] == "trade")
    assert league_recaps_ui.history_deep_link_label(trade) == "View Trade History"
    inbox = compose_activity_inbox(session=session, league_id="L1", include_product_update=False)
    assert any(item.href_hint == "league_recaps" for item in inbox)
    teaser = league_recaps.dashboard_teaser(session, league_id="L1")
    assert teaser is not None
    assert teaser["title"] == "Week 7 is ready"
    assert league_recaps.dashboard_teaser({}, league_id="L1") is None


def test_current_value_lens_is_labeled_and_never_called_historical():
    trade = _trade()
    trade["sides"][0]["receives"][0]["current_value"] = 8400
    recap = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[trade],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    story = next(item for item in recap["stories"] if item["story_type"] == "trade")
    assert story["historical_value_available"] is False
    assert any(lens["lens"] == league_recaps.VALUE_LENS_NOW for lens in story["value_lenses"])
    assert "not reconstructed historical" in story["value_lenses"][0]["note"].casefold()
    html = league_recaps_ui.recap_story_html(story)
    assert "winner" not in html.casefold()
    assert "fleeced" not in html.casefold()


def test_css_is_route_owned_and_destination_exists():
    assert LEAGUE_RECAPS_CSS not in APP_CSS
    assert "dg-recap-edition" in LEAGUE_RECAPS_CSS
    keys = {page.key for page in PLATFORM_DESTINATIONS}
    assert "league_recaps" in keys
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'current_page == "league_recaps"' in app
    assert "st.rerun" not in (ROOT / "modules" / "league_recaps.py").read_text(encoding="utf-8")
    assert "st.rerun" not in (ROOT / "modules" / "league_recaps_ui.py").read_text(encoding="utf-8")
    assert league_recaps_ui.recap_edition_html({"week": 4, "stories": []}).count("Not enough historical data") == 1


def test_performance_story_is_team_score_not_player_performance():
    recap = league_recaps.build_weekly_recap(
        league_id="L1",
        season="2025",
        week=7,
        transactions=[],
        matchups=_matchups(),
        profiles=PROFILES,
    )
    story = next(item for item in recap["stories"] if item["story_type"] == league_recaps.STORY_PERFORMANCE)
    assert story["title"] in league_recaps.PERFORMANCE_STORY_TITLES
    assert "biggest performance" not in story["title"].casefold()
    assert "player" not in story["title"].casefold()
    assert story["primary_team"] == "War Room"
    html = league_recaps_ui.recap_story_html(story)
    assert "Biggest performance" not in html
    for title in league_recaps.PERFORMANCE_STORY_TITLES:
        assert "player" not in title.casefold()


def test_league_recaps_page_header_has_single_owner():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    recaps_block = app.split('if current_page == "league_recaps":', 1)[1].split(
        "# WEEKLY LEAGUE REPORT", 1
    )[0]
    assert 'render_section_header(' not in recaps_block
    assert recaps_block.count("league_recaps_ui.render_league_recaps_page_header") == 2
    assert recaps_block.count("league_recaps_ui.render_league_recaps_page(") == 1
    ui = (ROOT / "modules" / "league_recaps_ui.py").read_text(encoding="utf-8")
    assert ui.count('render_section_header(\n        "League Recaps / History"') == 1
    assert ui.count("render_league_recaps_page_header(render_section_header)") == 1

    headers: list[str] = []

    def _header(title, **_kwargs):
        headers.append(title)

    html_chunks: list[str] = []

    class _Session(dict):
        pass

    session = _Session()
    opened: list[str] = []
    with (
        patch.object(league_recaps_ui.st, "session_state", session),
        patch.object(league_recaps_ui, "inject_global_styles"),
        patch.object(league_recaps_ui, "render_html_fragment", side_effect=lambda html: html_chunks.append(html)),
        patch.object(league_recaps_ui.st, "caption"),
        patch.object(league_recaps_ui.st, "pills", side_effect=["Recaps", "This week · 7", "Recaps", "Recaps"]),
        patch.object(league_recaps_ui.st, "button", return_value=True),
        patch.object(league_recaps_ui.deferred_rendering, "mark_deferred_section_ready"),
        patch.object(
            league_recaps_ui.league_history_ui,
            "cached_season_history_payload",
            return_value={"profiles": PROFILES, "transactions": []},
        ),
        patch.object(
            league_recaps_ui.league_history,
            "normalize_season_payload",
            return_value=[],
        ),
    ):
        league_recaps_ui.render_league_recaps_page(
            home_league_id="L1",
            season="2025",
            league={"settings": {"last_scored_leg": 7}},
            player_lookup=PLAYERS,
            current_profiles=PROFILES,
            matchups=_matchups(),
            movement=None,
            render_section_header=_header,
            open_history=opened.append,
        )
        incomplete_headers: list[str] = []
        league_recaps_ui.render_league_recaps_page(
            home_league_id="L1",
            season="2025",
            league={"settings": {"last_scored_leg": 0}},
            player_lookup=PLAYERS,
            current_profiles=PROFILES,
            matchups=_matchups(),
            movement=None,
            render_section_header=lambda title, **_k: incomplete_headers.append(title),
        )
        empty_headers: list[str] = []
        league_recaps_ui.render_league_recaps_page(
            home_league_id="",
            season="2025",
            league=None,
            player_lookup={},
            current_profiles=None,
            matchups=[],
            movement=None,
            render_section_header=lambda title, **_k: empty_headers.append(title),
        )

    assert headers == ["League Recaps / History"]
    assert incomplete_headers == ["League Recaps / History"]
    assert empty_headers == ["League Recaps / History"]
    assert opened
    joined = "\n".join(html_chunks)
    assert joined.count("dg-recap-edition") == 1
    assert joined.count("dg-recap-masthead") == 1
    assert "No completed week is ready for a recap yet." in joined
    assert "Load league recaps" not in joined.casefold()


def test_gm_orb_lists_league_recaps_under_core_via_category_not_group():
    from modules.ui_architecture import current_platform_destinations

    app = (ROOT / "app.py").read_text(encoding="utf-8")
    sheet = app.split("def render_mobile_destination_sheet", 1)[1].split(
        "def render_mobile_navigation_shell", 1
    )[0]
    assert "page.category == category" in sheet
    assert "page.group ==" not in sheet
    assert '("CORE", "Core")' in sheet
    destinations = current_platform_destinations(startup_mode=False)
    core_keys = [page.key for page in destinations if page.category == "CORE"]
    league_group = [page.key for page in destinations if page.group == "LEAGUE"]
    assert "league_recaps" in core_keys
    assert "league_recaps" in league_group
    assert core_keys.index("rankings") + 1 == core_keys.index("league_recaps")
    harness = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
    nav = harness.split("def _navigation()", 1)[1].split("def _header_geometry()", 1)[0]
    core = nav.split('st.caption("Core")', 1)[1].split('st.caption("Support")', 1)[0]
    support = nav.split('st.caption("Support")', 1)[1]
    assert '"League Recaps / History"' in core
    assert '"League Overview"' in core
    assert core.index("League Overview") < core.index("League Recaps / History")
    assert '"League Recaps / History"' not in support
