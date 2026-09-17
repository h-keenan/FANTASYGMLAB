"""modules.trade_hub_engine — the mobile Trade Hub idea-generation pipeline.

modules.trade_ideas.build_trade_ideas itself is a large, extensively
heuristic-gated search engine already covered by its own test suite —
these tests mock it at that boundary for the wiring/enforcement/projection
tests (does this module call it with the right arguments, and correctly
enforce + project whatever it returns), plus one full real-engine smoke
test that never mocks build_trade_ideas, to prove the whole pipeline runs
without crashing end to end.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from modules import trade_hub_engine


SETTINGS = {
    "qb_count": 1,
    "rb_count": 2,
    "wr_count": 2,
    "te_count": 1,
    "flex_count": 1,
    "bench_count": 6,
}


def _player(player_id: str, position: str, *, value: int = 50, age: int = 25) -> dict:
    return {
        "player_id": player_id,
        "name": player_id,
        "position": position,
        "team": "SEA",
        "age": age,
        "years_exp": 3,
        "dynasty_score": value,
        "value_score": value,
        "status": "Active",
        "injury_status": "",
        # Real trades get these from modules.player_eligibility's trust
        # annotation pass (already run on players_df before this module
        # sees it, same as the mobile Trade Analyzer/Dashboard endpoints) —
        # set directly here since this fixture skips that real pipeline.
        "trust_enforcement": "pass",
        "trust_evidence_confidence": "high",
    }


def _rosters():
    return [
        {"roster_id": 1, "owner_id": "u1", "players": ["my-qb", "my-rb"]},
        {"roster_id": 2, "owner_id": "u2", "players": ["opp-rb", "opp-wr"]},
    ]


def _users():
    return [
        {"user_id": "u1", "display_name": "Me"},
        {"user_id": "u2", "display_name": "Rival GM"},
    ]


def test_apply_strategy_age_curve_favors_youth_for_rebuild():
    df = pd.DataFrame(
        [
            _player("young", "RB", value=100, age=22),
            _player("old", "RB", value=100, age=30),
        ]
    )
    curved = trade_hub_engine.apply_strategy_age_curve(df, "rebuild", "dynasty_score")
    young_score = curved.loc[curved["player_id"] == "young", "dynasty_score"].iloc[0]
    old_score = curved.loc[curved["player_id"] == "old", "dynasty_score"].iloc[0]
    # Real engine output, not a mocked result — rebuild explicitly discounts
    # aging RBs and boosts young ones from the same starting value.
    assert young_score > old_score


def test_strategy_adjusted_pick_score_multiplier_matches_known_table():
    assert trade_hub_engine.strategy_adjusted_pick_score_multiplier(1.0, "rebuild") == 1.16
    # Unrecognized strategies normalize to "retool" (modules.team_eval's own
    # fallback), not a no-op 1.0 — matching the real engine, not a guess.
    assert trade_hub_engine.strategy_adjusted_pick_score_multiplier(1.0, "unknown-strategy") == 1.02


def test_build_roster_player_map_normalizes_ids():
    result = trade_hub_engine.build_roster_player_map(_rosters())
    assert result == {"1": ("my-qb", "my-rb"), "2": ("opp-rb", "opp-wr")}


def test_generate_trade_ideas_calls_engine_with_expected_arguments_and_projects_result():
    players_df = pd.DataFrame(
        [_player("my-qb", "QB", value=80), _player("my-rb", "RB", value=40), _player("opp-rb", "RB", value=70), _player("opp-wr", "WR", value=60)]
    )
    fake_idea = {
        "partner_team_name": "Rival GM",
        "rationale": "Clear value upgrade at a position of need.",
        "trade_gain": 25,
        "trade_confidence_label": "High",
        "market_realism_label": "Realistic",
        "reasoning_tags": ["Need-Based"],
        "send_assets": [{"asset_type": "player", "player_id": "my-rb", "name": "my-rb"}],
        "receive_assets": [{"asset_type": "player", "player_id": "opp-rb", "name": "opp-rb"}],
    }

    with patch("modules.sleeper.get_rosters", return_value=_rosters()):
        with patch("modules.sleeper.get_users", return_value=_users()):
            with patch(
                "modules.trade_ideas.build_trade_ideas", return_value=[fake_idea]
            ) as mock_build:
                cards = trade_hub_engine.generate_trade_ideas(
                    league_id="league-1",
                    my_roster_id=1,
                    players_df=players_df,
                    rosters=_rosters(),
                    league_settings=SETTINGS,
                    score_field="dynasty_score",
                    team_strategy="contender",
                )

    assert mock_build.call_args.kwargs["league_id"] == "league-1"
    assert mock_build.call_args.kwargs["my_roster_id"] == 1
    assert mock_build.call_args.kwargs["team_strategy"] == "contender"
    assert not mock_build.call_args.kwargs["df_summary"].empty

    assert len(cards) == 1
    card = cards[0].to_dict()
    assert card["partner_team_name"] == "Rival GM"
    assert card["trade_gain"] == 25
    assert card["package"]["send"]
    assert card["package"]["receive"]


def test_generate_trade_ideas_runs_the_real_search_engine_without_crashing():
    players_df = pd.DataFrame(
        [_player("my-qb", "QB", value=80), _player("my-rb", "RB", value=40), _player("opp-rb", "RB", value=70), _player("opp-wr", "WR", value=60)]
    )

    with patch("modules.sleeper.get_rosters", return_value=_rosters()):
        with patch("modules.sleeper.get_users", return_value=_users()):
            cards = trade_hub_engine.generate_trade_ideas(
                league_id="league-2",
                my_roster_id=1,
                players_df=players_df,
                rosters=_rosters(),
                league_settings=SETTINGS,
                score_field="dynasty_score",
                team_strategy="retool",
            )

    # A tiny two-team, four-player league may or may not clear the real
    # engine's fit/reasoning thresholds — the point of this test is that
    # the whole pipeline (league summary -> strategy curve -> real search
    # -> trust enforcement -> projection) runs end to end without raising.
    assert isinstance(cards, list)
    for card in cards:
        assert card.to_dict()["package"]


def _fake_idea(**overrides):
    idea = {
        "partner_team_name": "Rival GM",
        "rationale": "Clear value upgrade at a position of need.",
        "trade_gain": 25,
        "trade_confidence_label": "High",
        "market_realism_label": "Realistic",
        "reasoning_tags": ["Need-Based"],
        "send_assets": [
            {
                "asset_type": "player",
                "player_id": "my-rb",
                "name": "my-rb",
                "position": "RB",
                "team": "KC",
                "age": 27,
                "injury_status": "Questionable",
                "injury_level": "minor",
                "opportunity_explanation": "Locked in as the early-down back.",
            }
        ],
        "receive_assets": [{"asset_type": "player", "player_id": "opp-rb", "name": "opp-rb"}],
    }
    idea.update(overrides)
    return idea


def test_project_trade_idea_card_includes_category_and_value_edge_band():
    card = trade_hub_engine.project_trade_idea_card(_fake_idea(trade_gain=800))
    payload = card.to_dict()
    # +800 clears the >=500 threshold in modules.trade_visual_language's band.
    assert payload["value_edge_band"] == "Favorable"
    # Non-headline: falls back to trade_hub_ui.trade_hub_display_section's
    # classification (high confidence here, since trade_confidence_label="High"
    # and nothing else in the searchable text matches an earlier category).
    assert payload["category"] == "High Confidence"


def test_project_trade_idea_card_marks_the_headline_slot_explicitly():
    card = trade_hub_engine.project_trade_idea_card(_fake_idea(), is_headline=True)
    assert card.to_dict()["category"] == "Headline Recommendation"


def test_project_trade_idea_card_forwards_injury_and_opportunity_detail_on_assets():
    card = trade_hub_engine.project_trade_idea_card(_fake_idea())
    sent = card.to_dict()["package"]["send"][0]
    assert sent["injury_level"] == "minor"
    assert sent["opportunity_explanation"] == "Locked in as the early-down back."


def test_project_trade_idea_card_maps_negative_gain_to_an_overpay_band():
    card = trade_hub_engine.project_trade_idea_card(_fake_idea(trade_gain=-2000))
    assert card.to_dict()["value_edge_band"] == "Major Overpay"
