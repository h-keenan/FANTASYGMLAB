"""modules.league_glance: the trimmed per-league "at a glance" card.

Pins per-field correctness of the five glance data points (record, top
waiver add, top trade headline, news/injury count, top need) and that the
composition reads the shared cached valuation/trade engines rather than
re-running the Dashboard pipeline.
"""

from __future__ import annotations

import pandas as pd
import pytest

from modules import league_glance


def _roster_frame() -> pd.DataFrame:
    positions = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "RB", "WR"]
    rows = []
    for i, position in enumerate(positions, start=1):
        rows.append(
            {
                "player_id": f"my{i}",
                "name": f"My Player {i}",
                "position": position,
                "team": "KC",
                "age": 26,
                "years_exp": 4,
                "status": "Active",
                "injury_status": None,
                "score": 2000,
                "dynasty_score": 2000,
                "value_score": 2000,
                "rebuild_score": 2000,
            }
        )
    rows.append(
        {
            "player_id": "target_rb",
            "name": "Target Runner",
            "position": "RB",
            "team": "SF",
            "age": 25,
            "years_exp": 3,
            "status": "Active",
            "injury_status": None,
            "score": 6000,
            "dynasty_score": 6000,
            "value_score": 6000,
            "rebuild_score": 6000,
        }
    )
    return pd.DataFrame(rows)


_LEAGUE = {
    "season": "2026",
    "scoring_settings": {"rec": 1.0},
    "settings": {"type": 2, "playoff_teams": 2, "leg": 5},
    "roster_positions": ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "BN", "BN"],
    "total_rosters": 3,
}


def _rosters(my_players: list[str]) -> list[dict]:
    return [
        {"roster_id": 1, "owner_id": "sleeper-me", "players": my_players,
         "settings": {"wins": 3, "losses": 2, "ties": 0, "fpts": 500}},
        {"roster_id": 2, "owner_id": "sleeper-2", "players": [],
         "settings": {"wins": 4, "losses": 1, "ties": 0, "fpts": 520}},
        {"roster_id": 3, "owner_id": "sleeper-3", "players": [],
         "settings": {"wins": 1, "losses": 4, "ties": 0, "fpts": 410}},
    ]


# --- record ---------------------------------------------------------------


def test_record_reports_standing_rank_and_playoff_status():
    record = league_glance.build_glance_record(
        rosters=_rosters([]), roster_profiles={}, league=_LEAGUE, roster_id="1"
    )
    assert record["wins"] == 3
    assert record["losses"] == 2
    assert record["ties"] == 0
    assert record["record_label"] == "3-2"
    assert record["standing_rank"] == 2
    assert record["team_count"] == 3
    assert record["playoff_status"] == "Playoff seed #2"
    assert record["standings_available"] is True


def test_record_outside_the_playoff_line():
    record = league_glance.build_glance_record(
        rosters=_rosters([]), roster_profiles={}, league=_LEAGUE, roster_id="3"
    )
    assert record["standing_rank"] == 3
    assert record["playoff_status"] == "On the bubble"


def test_record_hides_rank_before_any_games_are_played():
    rosters = [
        {"roster_id": 1, "owner_id": "a", "settings": {"wins": 0, "losses": 0, "ties": 0}},
        {"roster_id": 2, "owner_id": "b", "settings": {"wins": 0, "losses": 0, "ties": 0}},
    ]
    record = league_glance.build_glance_record(rosters=rosters, roster_profiles={}, league=_LEAGUE, roster_id="1")
    assert record["record_label"] == "0-0"
    # Every team is 0-0: a rank here would be an alphabetical artefact.
    assert record["standing_rank"] is None
    assert record["playoff_status"] == ""
    assert record["standings_available"] is False


# --- news / injury count ---------------------------------------------------


def test_news_count_uses_the_alerts_feed_filter_and_counts_injured_players(monkeypatch):
    roster_df = pd.DataFrame(
        [
            {"player_id": "a", "name": "Alpha Back", "team": "KC", "status": "Active", "injury_status": "Questionable"},
            {"player_id": "b", "name": "Bravo Wide", "team": "SF", "status": "Injured Reserve", "injury_status": "IR"},
            {"player_id": "c", "name": "Charlie End", "team": "KC", "status": "Active", "injury_status": None},
        ]
    )
    seen: dict = {}

    def _filter(pool, names, teams):
        seen["names"] = names
        seen["teams"] = teams
        return list(pool)

    def _curate(items, max_items=12):
        seen["max_items"] = max_items
        return items[:2]

    monkeypatch.setattr(league_glance.my_news, "filter_news_for_players", _filter)
    monkeypatch.setattr(league_glance.my_news, "curate_player_news", _curate)

    news = league_glance.build_glance_news(news_pool=[{"title": "x"}] * 5, roster_df=roster_df)

    assert news == {"news_count": 2, "injury_count": 2}
    assert seen["names"] == ["Alpha Back", "Bravo Wide", "Charlie End"]
    assert seen["teams"] == ["KC", "SF"]
    # Same cap the Alerts screen's own endpoint uses, so the badge never
    # promises more than the screen it opens will list.
    assert seen["max_items"] == league_glance.GLANCE_NEWS_ITEM_LIMIT == 12


def test_news_count_is_zero_without_a_news_pool():
    roster_df = pd.DataFrame([{"player_id": "a", "name": "Alpha", "team": "KC", "status": "Active", "injury_status": None}])
    assert league_glance.build_glance_news(news_pool=None, roster_df=roster_df) == {
        "news_count": 0,
        "injury_count": 0,
    }


# --- projections ----------------------------------------------------------


def test_projections_trim_tiles_to_the_glance_fields():
    waiver = league_glance.project_waiver_tile(
        {
            "label": "Top Waiver Opportunity",
            "value": "Target Runner",
            "note": "Fills your RB need right now.",
            "route_player_id": "target_rb",
            "route_player_name": "Target Runner",
            "route_player_position": "RB",
            "route_player_team": "SF",
            "recommendation_narrative": {"huge": "payload"},
        }
    )
    assert waiver == {
        "player_id": "target_rb",
        "name": "Target Runner",
        "position": "RB",
        "team": "SF",
        "reason": "Fills your RB need right now.",
    }

    trade = league_glance.project_trade_tile(
        {"value": "Get Star Back", "note": "long", "presentation": {"partner_team_name": "Rivals", "trade_package": {}}}
    )
    assert trade == {"headline": "Get Star Back", "partner_team_name": "Rivals"}

    need = league_glance.project_need_tile(
        {"category": "true_need", "label": "Biggest Team Need", "value": "TE", "note": "long", "tier_label": "Need"}
    )
    assert need == {"category": "true_need", "label": "Biggest Team Need", "value": "TE", "tier_label": "Need"}

    assert league_glance.project_waiver_tile(None) is None
    assert league_glance.project_trade_tile({"value": ""}) is None
    assert league_glance.project_need_tile(None) is None


# --- full composition -----------------------------------------------------


def _patch_sleeper(monkeypatch, *, rosters, league=_LEAGUE):
    monkeypatch.setattr(league_glance.sleeper_leagues, "resolve_sleeper_user_id", lambda _u: "sleeper-me")
    monkeypatch.setattr(league_glance.sleeper, "get_league", lambda _id: league)
    monkeypatch.setattr(league_glance.sleeper, "get_rosters", lambda _id: rosters)
    monkeypatch.setattr(
        league_glance.sleeper, "get_league_roster_profiles", lambda _id: {"1": {"team_name": "My Squad"}}
    )


@pytest.mark.parametrize(
    ("username", "user_id", "league", "rosters", "reason"),
    [
        ("", "sleeper-me", _LEAGUE, _rosters(["my1"]), "no_sleeper_username_linked"),
        ("gm", None, _LEAGUE, _rosters(["my1"]), "sleeper_user_not_found"),
        ("gm", "sleeper-me", None, _rosters(["my1"]), "league_not_found"),
        ("gm", "someone-else", _LEAGUE, _rosters(["my1"]), "not_a_member_of_league"),
        ("gm", "sleeper-me", _LEAGUE, _rosters([]), "empty_roster"),
    ],
)
def test_everyday_skip_states_return_a_reason_not_an_error(monkeypatch, username, user_id, league, rosters, reason):
    monkeypatch.setattr(league_glance.sleeper_leagues, "resolve_sleeper_user_id", lambda _u: user_id)
    monkeypatch.setattr(league_glance.sleeper, "get_league", lambda _id: league)
    monkeypatch.setattr(league_glance.sleeper, "get_rosters", lambda _id: rosters)
    result = league_glance.build_league_glance(
        league_id="L1", lens="Dynasty", sleeper_username=username, players_db_path="db"
    )
    assert result == {"ok": False, "reason": reason}


def test_build_league_glance_composes_all_five_fields(monkeypatch):
    my_players = [f"my{i}" for i in range(1, 10)]
    _patch_sleeper(monkeypatch, rosters=_rosters(my_players))

    valued_calls: list[dict] = []

    def _valued(**kwargs):
        valued_calls.append(kwargs)
        return _roster_frame()

    monkeypatch.setattr(league_glance.league_value_settings, "build_valued_players_frame_cached", _valued)

    trade_calls: list[dict] = []
    ideas = [{"id": "weak", "rank": 2}, {"id": "best", "rank": 1}]

    def _trade_records(**kwargs):
        trade_calls.append(kwargs)
        return ideas

    monkeypatch.setattr(league_glance.trade_hub_engine, "generate_trade_idea_records_cached", _trade_records)
    monkeypatch.setattr(
        league_glance.trade_hub_ui,
        "order_trade_hub_visible_ideas",
        lambda records: sorted(records, key=lambda idea: idea["rank"]),
    )
    monkeypatch.setattr(
        league_glance.dashboard_engine,
        "build_trade_tile",
        lambda idea, **_k: {"value": f"Headline for {idea['id']}", "presentation": {"partner_team_name": "Rivals"}},
    )
    monkeypatch.setattr(league_glance.my_news, "filter_news_for_players", lambda pool, names, teams: list(pool))
    monkeypatch.setattr(league_glance.my_news, "curate_player_news", lambda items, max_items=12: items[:max_items])

    result = league_glance.build_league_glance(
        league_id="L1",
        lens="Dynasty",
        sleeper_username="gm",
        players_db_path="db",
        news_pool=[{"title": "a"}, {"title": "b"}, {"title": "c"}],
        team_stance_value="Competing",
        gm_target_player_ids=("t1",),
        gm_untouchable_player_ids=("u1",),
    )

    assert result["ok"] is True
    assert result["roster_id"] == "1"
    assert result["team_name"] == "My Squad"

    # 1. record
    assert result["record"]["record_label"] == "3-2"
    assert result["record"]["standing_rank"] == 2
    assert result["record"]["playoff_status"] == "Playoff seed #2"

    # 2. waiver: the only unrostered player is the top add (real
    # select_top_waiver_opportunity + build_waiver_tile, not mocked).
    assert result["waiver"]["player_id"] == "target_rb"
    assert result["waiver"]["name"] == "Target Runner"
    assert result["waiver"]["position"] == "RB"
    assert result["waiver"]["reason"]

    # 3. trade: the TOP-ordered idea's headline, not the first raw record.
    assert result["trade"] == {"headline": "Headline for best", "partner_team_name": "Rivals"}
    assert trade_calls and trade_calls[0]["league_id"] == "L1"
    assert trade_calls[0]["roster_id"] == 1
    assert trade_calls[0]["lens"] == "Dynasty"
    assert trade_calls[0]["gm_target_player_ids"] == ("t1",)
    assert trade_calls[0]["untouchable_player_ids"] == ("u1",)
    assert trade_calls[0]["team_stance"] == "Competing"

    # 4. news/injury
    assert result["news"] == {"news_count": 3, "injury_count": 0}

    # 5. need: real roster_needs headline with label + value.
    assert result["need"]["label"]
    assert result["need"]["value"]
    assert result["need"]["category"] in {"true_need", "injury_pressure", "future_risk", "upgrade", "balanced"}

    # Reads the shared (league_id, lens)-cached valuation frame exactly once.
    assert valued_calls == [{"league_id": "L1", "lens": "Dynasty", "players_db_path": "db"}]


def test_build_league_glance_without_trade_ideas_leaves_trade_empty(monkeypatch):
    _patch_sleeper(monkeypatch, rosters=_rosters([f"my{i}" for i in range(1, 10)]))
    monkeypatch.setattr(
        league_glance.league_value_settings, "build_valued_players_frame_cached", lambda **_k: _roster_frame()
    )
    monkeypatch.setattr(league_glance.trade_hub_engine, "generate_trade_idea_records_cached", lambda **_k: [])

    result = league_glance.build_league_glance(
        league_id="L1", lens="Dynasty", sleeper_username="gm", players_db_path="db"
    )
    assert result["ok"] is True
    assert result["trade"] is None
    assert result["news"]["news_count"] == 0


def test_build_league_glance_reports_no_player_data(monkeypatch):
    _patch_sleeper(monkeypatch, rosters=_rosters(["my1"]))
    monkeypatch.setattr(
        league_glance.league_value_settings, "build_valued_players_frame_cached", lambda **_k: pd.DataFrame()
    )
    result = league_glance.build_league_glance(
        league_id="L1", lens="Dynasty", sleeper_username="gm", players_db_path="db"
    )
    assert result == {"ok": False, "reason": "no_player_data"}
