"""modules.dashboard_engine — the mobile "Next Move" briefing pipeline.

Mocks requests.get (the I/O boundary for modules.sleeper) but exercises the
real team_eval / trade_analyzer_fit / injury_ui / waivers_ui / daily_gm_briefing
engines, matching the mocking convention used across the mobile API tests.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pandas as pd

from modules import dashboard_engine


SETTINGS = {
    "qb_count": 1,
    "rb_count": 2,
    "wr_count": 2,
    "te_count": 1,
    "superflex_count": 0,
    "flex_count": 1,
    "bench_count": 6,
}


def _player(
    player_id: str,
    position: str,
    *,
    name: str | None = None,
    age: int = 25,
    years_exp: int = 3,
    value: int = 50,
    status: str = "Active",
    injury_status: str = "",
) -> dict:
    return {
        "player_id": player_id,
        "name": name or player_id,
        "position": position,
        "team": "SEA",
        "age": age,
        "years_exp": years_exp,
        "dynasty_score": value,
        "value_score": value,
        "market_score": value,
        "status": status,
        "injury_status": injury_status,
        "opportunity_label": "Strong Opportunity",
    }


def _sleeper_response(payload):
    response = Mock(status_code=200)
    response.json.return_value = payload
    return response


def test_select_need_headline_prefers_true_need_over_balanced():
    from modules.roster_needs import PositionNeedAssessment, TeamNeedsAssessment

    assessment = TeamNeedsAssessment(
        positions=(
            PositionNeedAssessment(
                position="RB",
                severity=0.8,
                classification="short_term_need",
                starter_quality=0.3,
                backup_quality=0.2,
                depth_quality=0.2,
                future_stability=0.4,
                injury_pressure=0.0,
                replacement_gap=0.5,
                required_starters=2,
                reasons=(),
                reason_codes=(),
                data_quality="available",
                true_need=True,
                relative_weakness=False,
                upgrade_opportunity=False,
                temporary_injury_pressure=False,
                future_risk=False,
            ),
        ),
        true_needs=("RB",),
        relative_weaknesses=(),
        upgrade_opportunities=(),
        temporary_injury_pressures=(),
        future_risks=(),
    )
    headline = dashboard_engine.select_need_headline(assessment)
    assert headline["label"] == "Biggest Team Need"
    assert headline["value"] == "RB"
    # Real, already-computed tier word for the priority ladder this headline
    # came from (roster need > injury pressure > future risk > upgrade
    # opportunity) — not a fabricated confidence score.
    assert headline["category"] == "true_need"
    assert headline["tier_label"] == "Priority"


def _empty_assessment(**overrides):
    from modules.roster_needs import TeamNeedsAssessment

    fields = {
        "positions": (),
        "true_needs": (),
        "relative_weaknesses": (),
        "upgrade_opportunities": (),
        "temporary_injury_pressures": (),
        "future_risks": (),
    }
    fields.update(overrides)
    return TeamNeedsAssessment(**fields)


def test_select_need_headline_tier_labels_match_the_priority_ladder():
    # Each rung of the ladder (roster need > injury pressure > future risk >
    # upgrade opportunity > balanced) gets its own real, honest tier word —
    # see modules.dashboard_engine.NEED_TIER_LABELS. A strict step-function,
    # not a numeric confidence score.
    injury = dashboard_engine.select_need_headline(
        _empty_assessment(temporary_injury_pressures=("RB",))
    )
    assert injury["category"] == "injury_pressure"
    assert injury["tier_label"] == "Urgent"

    future_risk = dashboard_engine.select_need_headline(
        _empty_assessment(future_risks=("TE",))
    )
    assert future_risk["category"] == "future_risk"
    assert future_risk["tier_label"] == "Watch"

    upgrade = dashboard_engine.select_need_headline(
        _empty_assessment(upgrade_opportunities=("WR",))
    )
    assert upgrade["category"] == "upgrade"
    assert upgrade["tier_label"] == "Opportunity"

    balanced = dashboard_engine.select_need_headline(_empty_assessment())
    assert balanced["category"] == "balanced"
    assert balanced["tier_label"] == ""


def test_compose_next_move_briefing_returns_a_real_composed_briefing():
    league_id = "dashboard-engine-test-league-1"
    roster_id = "1"
    my_players = [
        _player("qb1", "QB", value=80),
        _player("rb1", "RB", value=70),
        _player("rb2", "RB", value=40),
        _player("wr1", "WR", value=65),
        _player("wr2", "WR", value=30),
        _player("te1", "TE", value=25),
    ]
    other_roster_players = [_player("opp-rb", "RB", value=55)]
    free_agent_players = [_player("fa-wr", "WR", value=45, status="Active")]
    players_df = pd.DataFrame(my_players + other_roster_players + free_agent_players)

    league_payload = _sleeper_response(
        {
            "roster_positions": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX"] + ["BN"] * 6,
            "settings": {"taxi_slots": 0, "reserve_slots": 0},
        }
    )
    rosters_payload = _sleeper_response(
        [
            {
                "roster_id": 1,
                "players": [p["player_id"] for p in my_players],
                "taxi": [],
                "reserve": [],
            },
            {
                "roster_id": 2,
                "players": [p["player_id"] for p in other_roster_players],
                "taxi": [],
                "reserve": [],
            },
        ]
    )

    with patch("requests.get", side_effect=[league_payload, rosters_payload]):
        briefing = dashboard_engine.compose_next_move_briefing(
            league_id=league_id,
            roster_id=roster_id,
            players_df=players_df,
            roster_player_ids={p["player_id"] for p in my_players},
            all_rostered_player_ids={p["player_id"] for p in my_players + other_roster_players},
            league_settings=SETTINGS,
            score_field="dynasty_score",
        )

    assert briefing.league_id == league_id
    assert briefing.roster_id == roster_id
    # Real engine output, not a mocked result — the free-agent WR is the only
    # unrostered player, so the waiver engine should surface it by name. With
    # no `rosters` passed there's no trade candidate, so app.py's default
    # tile order (roster_pressure, waiver, need, injury — see
    # dashboard_engine's module docstring) makes the waiver tile the primary
    # recommendation (category "top_priority"), same as the web app's own
    # `_append(briefing.primary, CATEGORY_TOP_PRIORITY)` — it does not also
    # appear under "waiver_opportunity" since that category only pulls from
    # the intelligence/additional zones, not primary.
    categories = {item.category for item in briefing.items}
    assert categories  # at least one tile survived organize_dashboard_items
    top_priority_items = [item for item in briefing.items if item.category == "top_priority"]
    assert top_priority_items, f"expected a top_priority tile, got categories: {categories}"
    assert any("fa-wr" in (item.route_player_id or "") for item in top_priority_items)
    for item in briefing.items:
        payload = item.to_dict()
        assert payload["headline"]
        assert payload["league_id"] == league_id


def _fake_trade_idea_record(*, partner: str = "Rival GM", gain: int = 40) -> dict:
    return {
        "partner_team_name": partner,
        "rationale": "Clear dynasty upgrade at a position of need.",
        "trade_gain": gain,
        "trade_confidence_label": "High",
        "market_realism_label": "Realistic",
        "reasoning_tags": ["Need-Based"],
        "send_assets": [{"asset_type": "player", "player_id": "my-rb2", "name": "My RB2"}],
        "receive_assets": [
            {"asset_type": "player", "player_id": "target-wr1", "name": "Target WR1", "status": "Active"}
        ],
    }


def test_build_trade_tile_composes_a_top_trade_opportunity_tile():
    tile = dashboard_engine.build_trade_tile(
        _fake_trade_idea_record(),
        league_id="league-1",
        roster_id="1",
        score_field="dynasty_score",
    )
    assert tile is not None
    assert tile["label"] == "Top Trade Opportunity"
    assert tile["tone"] == "trade"
    assert tile["route_key"] == "trade_hub"
    assert tile["route_focus_mode"] == "target_player"
    assert tile["route_player_id"] == "target-wr1"
    assert tile["route_player_name"] == "Target WR1"
    assert tile["note"]
    assert tile["recommendation_narrative"] is not None
    assert tile["recommendation_id"]
    presentation = tile["presentation"]
    assert presentation["trade_gain"] == 40
    assert presentation["partner_team_name"] == "Rival GM"
    package = presentation["trade_package"]
    assert package["send"][0]["name"] == "My RB2"
    assert package["receive"][0]["name"] == "Target WR1"


def test_build_trade_tile_returns_none_without_a_headline_idea():
    assert dashboard_engine.build_trade_tile(None, league_id="l", roster_id="1", score_field="dynasty_score") is None


def test_build_trade_tile_names_injury_in_value_for_non_actionable_receive_asset():
    """This tile's "value" is what modules.push_triggers.run_push_trigger_sweep
    sends verbatim as the push notification body — so a receive-side player
    in a non-actionable status (the same canonical set the waiver push
    already gates on) must never read as a clean opportunity in that short
    text, even though trade generation itself still legitimately surfaces
    the idea (a rebuild/tank buy-low per modules.trade_ideas)."""

    idea = _fake_trade_idea_record()
    idea["receive_assets"][0]["status"] = "Injured Reserve"
    idea["receive_assets"][0]["injury_status"] = "Torn ACL"

    tile = dashboard_engine.build_trade_tile(
        idea, league_id="league-1", roster_id="1", score_field="dynasty_score"
    )

    assert "Torn ACL" in tile["value"]


def test_build_trade_tile_value_unchanged_for_actionable_receive_asset():
    tile = dashboard_engine.build_trade_tile(
        _fake_trade_idea_record(),
        league_id="league-1",
        roster_id="1",
        score_field="dynasty_score",
    )
    assert "(" not in tile["value"]


def test_build_trade_tile_carries_real_player_identity_fields():
    """The receive-side target player's position/team/tier/score should ride
    along on the tile — same raw asset dict compact_package already reads
    them from (modules.trade_ideas._player_asset), not a second source."""

    idea = _fake_trade_idea_record()
    idea["receive_assets"][0].update(
        {"position": "WR", "team": "CIN", "player_tier": "Elite", "score": 88}
    )
    tile = dashboard_engine.build_trade_tile(
        idea, league_id="league-1", roster_id="1", score_field="dynasty_score"
    )
    assert tile["route_player_name"] == "Target WR1"
    assert tile["route_player_position"] == "WR"
    assert tile["route_player_team"] == "CIN"
    assert tile["route_player_tier"] == "Elite"
    assert tile["route_player_score"] == 88


def test_build_trade_tile_leaves_player_identity_fields_empty_without_tier_data():
    """Honest 'no tier data' edge case — the receive asset here has no
    player_tier/position/team/score at all, so the tile must not fabricate
    them, just surface empty/None."""

    tile = dashboard_engine.build_trade_tile(
        _fake_trade_idea_record(),
        league_id="league-1",
        roster_id="1",
        score_field="dynasty_score",
    )
    assert tile["route_player_position"] == ""
    assert tile["route_player_team"] == ""
    assert tile["route_player_tier"] == ""
    assert tile["route_player_score"] is None


def test_build_waiver_tile_carries_real_player_identity_fields():
    top_waiver = pd.Series(
        {
            "player_id": "fa-wr9",
            "name": "Free Agent WR",
            "position": "WR",
            "team": "SEA",
            "player_tier": "Contributor",
            "dynasty_score": 42,
            "position_rank": 5,
            "opportunity_label": "Strong Opportunity",
        }
    )
    tile = dashboard_engine.build_waiver_tile(
        top_waiver, league_id="league-1", roster_id="1", score_field="dynasty_score"
    )
    assert tile is not None
    assert tile["route_player_id"] == "fa-wr9"
    assert tile["route_player_name"] == "Free Agent WR"
    assert tile["route_player_position"] == "WR"
    assert tile["route_player_team"] == "SEA"
    assert tile["route_player_tier"] == "Contributor"
    assert tile["route_player_score"] == 42


def test_build_waiver_tile_leaves_tier_empty_without_tier_data():
    top_waiver = pd.Series(
        {
            "player_id": "fa-wr9",
            "name": "Free Agent WR",
            "position": "WR",
            "team": "SEA",
            "dynasty_score": 42,
            "position_rank": 5,
            "opportunity_label": "Strong Opportunity",
        }
    )
    tile = dashboard_engine.build_waiver_tile(
        top_waiver, league_id="league-1", roster_id="1", score_field="dynasty_score"
    )
    assert tile["route_player_tier"] == ""


def _declining_recency_row(**overrides) -> dict:
    row = {
        "player_id": "p1",
        "name": "Player",
        "position": "RB",
        "team": "SEA",
        "player_tier": "Starter",
        "dynasty_score": 50,
        # Clears rankings.recency_trend_display's own gate (RECENCY_MIN_SAMPLE
        # = 3, RECENCY_DISPLAY_MIN_CONFIDENCE = 0.66, |trend| >= 0.05) — see
        # that function's docstring for why.
        "recency_sample_n": 4,
        "recency_trend": -0.30,
        "recency_confidence": 0.9,
    }
    row.update(overrides)
    return row


def test_build_value_trend_tile_flags_the_highest_value_declining_roster_player():
    """Reuses rankings.recency_trend_display (the same gated read Live
    Draft/Player Compare already narrate per player) to pick the single
    most valuable roster asset currently trending down — never the whole
    roster, never a player who isn't actually declining."""

    roster_df = pd.DataFrame(
        [
            _declining_recency_row(
                player_id="bench-decliner", name="Bench Guy", dynasty_score=40, recency_trend=-0.30
            ),
            _declining_recency_row(
                player_id="star-decliner", name="Star Back", dynasty_score=90, recency_trend=-0.20
            ),
            _declining_recency_row(
                player_id="steady", name="Steady Guy", dynasty_score=60, recency_trend=0.10
            ),
        ]
    )
    tile = dashboard_engine.build_value_trend_tile(roster_df, "dynasty_score")
    assert tile is not None
    assert tile["label"] == "Value Trend"
    assert "Star Back" in tile["value"]
    assert tile["route_player_id"] == "star-decliner"
    assert tile["tone"] == "risk"
    assert tile["route_key"] == "my_team"
    assert "down" in tile["note"].lower()


def test_build_value_trend_tile_returns_none_without_a_qualifying_decline():
    roster_df = pd.DataFrame(
        [_declining_recency_row(player_id="steady", name="Steady Guy", recency_trend=0.01)]
    )
    assert dashboard_engine.build_value_trend_tile(roster_df, "dynasty_score") is None


def test_build_value_trend_tile_returns_none_for_an_empty_roster():
    assert dashboard_engine.build_value_trend_tile(pd.DataFrame(), "dynasty_score") is None


def test_build_news_tiles_reads_only_the_disk_cached_pool():
    """build_news_tiles must never hit live RSS — only the disk-cached pool
    (modules.news.load_cached_news_pool), same as app.py's single-league
    Dashboard — so a many-league Portfolio fan-out never blocks on network
    I/O. The dedupe/escalation `session` passed to news_intelligence is a
    plain throwaway dict, never Streamlit's session state."""

    fake_tile = {
        "label": "News Alert",
        "value": "Star Back listed questionable",
        "note": "Questionable with a knee injury.",
        "route_player_id": "star-decliner",
    }
    with patch(
        "modules.dashboard_engine.news_cache.load_cached_news_pool",
        return_value=[{"title": "Star Back listed questionable (Q)"}],
    ) as mock_pool:
        with patch(
            "modules.dashboard_engine.news_intelligence.build_roster_news_alert_tiles",
            return_value=[fake_tile],
        ) as mock_tiles:
            tiles = dashboard_engine.build_news_tiles(
                league_id="league-1",
                league_settings={},
                roster_df=pd.DataFrame([{"player_id": "star-decliner", "name": "Star Back"}]),
                lineup_df=pd.DataFrame(),
                free_agents_df=pd.DataFrame(),
                players_df=pd.DataFrame(),
            )
    assert tiles == [fake_tile]
    mock_pool.assert_called_once_with()
    assert mock_tiles.call_args.kwargs["session"] == {}
    assert mock_tiles.call_args.kwargs["max_tiles"] == 1


def test_build_news_tiles_fails_soft_when_the_cache_read_errors():
    with patch(
        "modules.dashboard_engine.news_cache.load_cached_news_pool",
        side_effect=RuntimeError("disk read failed"),
    ):
        tiles = dashboard_engine.build_news_tiles(
            league_id="league-1",
            league_settings={},
            roster_df=pd.DataFrame(),
            lineup_df=pd.DataFrame(),
            free_agents_df=pd.DataFrame(),
            players_df=pd.DataFrame(),
        )
    assert tiles == []


def test_compose_next_move_briefing_includes_trade_tile_when_rosters_given():
    league_id = "dashboard-engine-test-league-2"
    roster_id = "1"
    my_players = [
        _player("qb1", "QB", value=80),
        _player("rb1", "RB", value=70),
        _player("rb2", "RB", value=40),
        _player("wr1", "WR", value=65),
        _player("wr2", "WR", value=30),
        _player("te1", "TE", value=25),
    ]
    other_roster_players = [_player("opp-rb", "RB", value=55)]
    players_df = pd.DataFrame(my_players + other_roster_players)
    rosters = [
        {"roster_id": 1, "players": [p["player_id"] for p in my_players]},
        {"roster_id": 2, "players": [p["player_id"] for p in other_roster_players]},
    ]

    league_payload = _sleeper_response(
        {
            "roster_positions": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX"] + ["BN"] * 6,
            "settings": {"taxi_slots": 0, "reserve_slots": 0},
        }
    )
    rosters_payload = _sleeper_response(rosters)

    with patch("requests.get", side_effect=[league_payload, rosters_payload]):
        with patch(
            "modules.trade_hub_engine.generate_trade_idea_records",
            return_value=[_fake_trade_idea_record()],
        ) as mock_generate:
            briefing = dashboard_engine.compose_next_move_briefing(
                league_id=league_id,
                roster_id=roster_id,
                players_df=players_df,
                roster_player_ids={p["player_id"] for p in my_players},
                all_rostered_player_ids={p["player_id"] for p in my_players + other_roster_players},
                league_settings=SETTINGS,
                score_field="dynasty_score",
                rosters=rosters,
            )

    assert mock_generate.call_args.kwargs["my_roster_id"] == 1
    assert mock_generate.call_args.kwargs["league_id"] == league_id
    trade_items = [item for item in briefing.items if "target-wr1" in (item.route_player_id or "")]
    assert trade_items, f"expected the trade tile's target player to surface, got: {[i.to_dict() for i in briefing.items]}"
    # The rich trade-package data must survive tile -> DailyBriefingItem
    # projection (via the "presentation" field) for the mobile Dashboard's
    # Top Priority card to render player rows, not just narrative prose.
    presentation = trade_items[0].presentation
    assert presentation is not None
    assert presentation["trade_package"]["receive"][0]["player_id"] == "target-wr1"


def test_compose_next_move_briefing_flags_roster_pressure_when_over_limit():
    league_id = "dashboard-engine-test-league-2"
    roster_id = "1"
    # Ten rostered players against a tiny 3-slot league — guaranteed over limit.
    my_players = [_player(f"p{i}", "WR", value=10) for i in range(10)]
    players_df = pd.DataFrame(my_players)

    league_payload = _sleeper_response(
        {"roster_positions": ["WR", "BN"], "settings": {"taxi_slots": 0, "reserve_slots": 0}}
    )
    rosters_payload = _sleeper_response(
        [{"roster_id": 1, "players": [p["player_id"] for p in my_players], "taxi": [], "reserve": []}]
    )

    with patch("requests.get", side_effect=[league_payload, rosters_payload]):
        briefing = dashboard_engine.compose_next_move_briefing(
            league_id=league_id,
            roster_id=roster_id,
            players_df=players_df,
            roster_player_ids={p["player_id"] for p in my_players},
            all_rostered_player_ids={p["player_id"] for p in my_players},
            league_settings=SETTINGS,
            score_field="dynasty_score",
        )

    assert not briefing.quiet
    assert briefing.items[0].category == "top_priority"
    assert "Over" in briefing.items[0].headline or "roster" in briefing.items[0].reason.lower()
