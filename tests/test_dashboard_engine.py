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
    assert tile["note"]
    assert tile["recommendation_narrative"] is not None
    assert tile["recommendation_id"]


def test_build_trade_tile_returns_none_without_a_headline_idea():
    assert dashboard_engine.build_trade_tile(None, league_id="l", roster_id="1", score_field="dynasty_score") is None


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
    assert any(
        "target-wr1" in (item.route_player_id or "") for item in briefing.items
    ), f"expected the trade tile's target player to surface, got: {[i.to_dict() for i in briefing.items]}"


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
