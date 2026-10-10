"""Contracts for RC performance audit engineering optimizations."""

from pathlib import Path

from modules.rankings import _injury_level_cached, injury_level


ROOT = Path(__file__).resolve().parents[1]


def test_injury_level_cache_preserves_classification_and_hits():
    _injury_level_cached.cache_clear()
    assert injury_level("Out", "Questionable") == injury_level("out", "questionable")
    assert injury_level("IR", "") == "major"
    assert injury_level("Active", "") == "healthy"
    info = _injury_level_cached.cache_info()
    assert info.hits >= 1
    assert info.misses >= 1


def test_trade_hub_reuses_roster_map_instead_of_second_sleeper_fetch():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    hub = source[
        source.index('if current_page == "trade_hub"') : source.index("# TRADE ANALYZER")
    ]
    # Owned roster IDs come from shared-context roster_player_map (my_player_ids),
    # not a second Sleeper get_roster_player_ids fetch.
    assert "my_player_ids = {" in hub
    assert "roster_player_map.get(str(my_roster_id)" in hub
    assert "get_shared_league_context(" in hub
    assert "get_roster_player_ids(selected_league_id, my_roster_id)" not in hub

def test_my_team_prefers_shared_league_roster_map():
    # The "news" route's roster-aware shared-context reuse (news_context =
    # get_shared_league_context(...)) was retired when News graduated to a
    # general, non-roster-scoped feed (web counterpart to mobile's
    # NewsScreen) — it no longer fetches a league/roster map at all, so that
    # perf guard no longer applies to it. My Team's own reuse still does.
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    my_team = source[
        source.index("# MY TEAM") : source.index("# LEAGUE OVERVIEW")
        if "# LEAGUE OVERVIEW" in source
        else source.index("if current_page == \"league\"")
    ]
    assert "roster_player_map_my_team = league_context_my_team.get(\"roster_player_map\")" in my_team


def test_waivers_reuse_roster_map_built_from_fetched_rosters():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    waivers = source[
        source.index("# WAIVERS & FAAB") : source.index("# MY TEAM")
    ]
    assert "waiver_roster_player_map = _build_roster_player_map(rosters)" in waivers
    assert "waiver_roster_player_map.get(str(my_roster_id)" in waivers
