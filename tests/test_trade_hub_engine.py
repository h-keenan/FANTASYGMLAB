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

import threading
import time
from unittest.mock import patch

import pandas as pd

from modules import league_value_settings, player_eligibility, rankings, sleeper, trade_hub_engine


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


def test_generate_trade_idea_records_resolves_untouchable_ids_to_names_and_blocks_them():
    """GM Targets' untouchable flag is player_id-keyed; the engine's own
    protection list (modules.trade_ideas.build_trade_ideas) is name-keyed —
    this confirms the resolution happens and both the search and the Trust
    enforcement pass receive it."""

    players_df = pd.DataFrame(
        [_player("my-qb", "QB", value=80), _player("my-rb", "RB", value=40), _player("opp-rb", "RB", value=70), _player("opp-wr", "WR", value=60)]
    )
    fake_idea = {
        "partner_team_name": "Rival GM",
        "rationale": "x",
        "trade_gain": 10,
        "trade_confidence_label": "High",
        "market_realism_label": "Realistic",
        "reasoning_tags": [],
        "send_assets": [],
        "receive_assets": [{"asset_type": "player", "player_id": "opp-rb", "name": "opp-rb"}],
    }

    with patch("modules.sleeper.get_rosters", return_value=_rosters()):
        with patch("modules.sleeper.get_users", return_value=_users()):
            with patch(
                "modules.trade_ideas.build_trade_ideas", return_value=[fake_idea]
            ) as mock_build:
                with patch.object(
                    trade_hub_engine,
                    "enforce_generated_trade_ideas",
                    side_effect=lambda ideas, **kwargs: ideas,
                ) as mock_enforce:
                    trade_hub_engine.generate_trade_idea_records(
                        league_id="league-1",
                        my_roster_id=1,
                        players_df=players_df,
                        rosters=_rosters(),
                        league_settings=SETTINGS,
                        score_field="dynasty_score",
                        team_strategy="contender",
                        untouchable_player_ids=("my-rb",),
                    )

    assert mock_build.call_args.kwargs["untouchable_names"] == ["my-rb"]
    assert mock_enforce.call_args.kwargs["untouchables"] == ("my-rb",)


def test_generate_trade_idea_records_skips_the_full_league_summary_pass_when_precomputed():
    """coridian_, 2026-10-18: "it still takes too long to load" — Dashboard's
    ~11s cold load traced to this exact per-roster league summary
    (modules.team_eval.build_league_summary) being redone from scratch on
    every cache miss. A precomputed df_summary (what
    _generate_trade_idea_records_cached now passes, from the already-cached
    modules.league_rankings.build_league_summary_and_draft_capital_cached)
    must skip that recomputation entirely."""

    players_df = pd.DataFrame(
        [_player("my-qb", "QB", value=80), _player("opp-rb", "RB", value=70)]
    )
    precomputed_summary = pd.DataFrame(
        [{"league_id": "league-1", "roster_id": 1, "owner_id": "u1", "team_name": "Mine", "total_score": 80}]
    )

    with patch("modules.sleeper.get_rosters", return_value=_rosters()):
        with patch("modules.sleeper.get_users", return_value=_users()):
            with patch.object(trade_hub_engine, "build_league_summary") as mock_build_summary:
                with patch("modules.trade_ideas.build_trade_ideas", return_value=[]):
                    trade_hub_engine.generate_trade_idea_records(
                        league_id="league-1",
                        my_roster_id=1,
                        players_df=players_df,
                        rosters=_rosters(),
                        league_settings=SETTINGS,
                        score_field="dynasty_score",
                        df_summary=precomputed_summary,
                    )

    mock_build_summary.assert_not_called()


def test_generate_trade_idea_records_computes_the_league_summary_fresh_when_not_precomputed():
    players_df = pd.DataFrame(
        [_player("my-qb", "QB", value=80), _player("opp-rb", "RB", value=70)]
    )

    with patch("modules.sleeper.get_rosters", return_value=_rosters()):
        with patch("modules.sleeper.get_users", return_value=_users()):
            with patch.object(
                trade_hub_engine, "build_league_summary", wraps=trade_hub_engine.build_league_summary
            ) as mock_build_summary:
                with patch("modules.trade_ideas.build_trade_ideas", return_value=[]):
                    trade_hub_engine.generate_trade_idea_records(
                        league_id="league-1",
                        my_roster_id=1,
                        players_df=players_df,
                        rosters=_rosters(),
                        league_settings=SETTINGS,
                        score_field="dynasty_score",
                    )

    mock_build_summary.assert_called_once()


def test_generate_trade_idea_records_resolves_trade_block_ids_to_names():
    """Trade Finder's trade_block_player_ids is player_id-keyed; the
    engine's own trade_block_names restriction (modules.trade_ideas.
    build_trade_ideas) is name-keyed — confirms the resolution happens."""

    players_df = pd.DataFrame(
        [_player("my-qb", "QB", value=80), _player("my-rb", "RB", value=40), _player("opp-rb", "RB", value=70), _player("opp-wr", "WR", value=60)]
    )

    with patch("modules.sleeper.get_rosters", return_value=_rosters()):
        with patch("modules.sleeper.get_users", return_value=_users()):
            with patch("modules.trade_ideas.build_trade_ideas", return_value=[]) as mock_build:
                trade_hub_engine.generate_trade_idea_records(
                    league_id="league-1",
                    my_roster_id=1,
                    players_df=players_df,
                    rosters=_rosters(),
                    league_settings=SETTINGS,
                    score_field="dynasty_score",
                    team_strategy="contender",
                    trade_block_player_ids=("my-rb",),
                )

    assert mock_build.call_args.kwargs["trade_block_names"] == ["my-rb"]


def test_generate_trade_idea_records_allows_a_protected_starter_when_explicitly_selected():
    """Regression: selecting a core/protected starter (a QB1, a locked-in
    WR1) in Trade Finder used to silently return zero ideas no matter what
    was picked — build_trade_ideas' own protected-player guard emptied the
    trade-block pool before any search ran. An explicit selection has to
    override that guard, per build_trade_ideas' own
    "only an intentional player-focused search may evaluate a protected
    outgoing asset" contract."""

    players_df = pd.DataFrame(
        [_player("my-qb", "QB", value=80), _player("my-rb", "RB", value=40), _player("opp-rb", "RB", value=70), _player("opp-wr", "WR", value=60)]
    )

    with patch("modules.sleeper.get_rosters", return_value=_rosters()):
        with patch("modules.sleeper.get_users", return_value=_users()):
            with patch("modules.trade_ideas.build_trade_ideas", return_value=[]) as mock_build:
                trade_hub_engine.generate_trade_idea_records(
                    league_id="league-1",
                    my_roster_id=1,
                    players_df=players_df,
                    rosters=_rosters(),
                    league_settings=SETTINGS,
                    score_field="dynasty_score",
                    team_strategy="contender",
                    trade_block_player_ids=("my-qb",),
                )

    assert mock_build.call_args.kwargs["allow_protected_focus"] is True


def test_generate_trade_idea_records_defaults_to_an_unrestricted_trade_block():
    players_df = pd.DataFrame(
        [_player("my-qb", "QB", value=80), _player("my-rb", "RB", value=40), _player("opp-rb", "RB", value=70), _player("opp-wr", "WR", value=60)]
    )

    with patch("modules.sleeper.get_rosters", return_value=_rosters()):
        with patch("modules.sleeper.get_users", return_value=_users()):
            with patch("modules.trade_ideas.build_trade_ideas", return_value=[]) as mock_build:
                trade_hub_engine.generate_trade_idea_records(
                    league_id="league-1",
                    my_roster_id=1,
                    players_df=players_df,
                    rosters=_rosters(),
                    league_settings=SETTINGS,
                    score_field="dynasty_score",
                    team_strategy="contender",
                )

    assert mock_build.call_args.kwargs["trade_block_names"] == []
    assert mock_build.call_args.kwargs["allow_protected_focus"] is False


def test_generate_trade_finder_records_wires_the_selection_through_to_the_engine():
    players_df = pd.DataFrame(
        [_player("my-qb", "QB", value=80), _player("my-rb", "RB", value=40), _player("opp-rb", "RB", value=70), _player("opp-wr", "WR", value=60)]
    )

    with patch("modules.sleeper.get_league", return_value={"roster_positions": ["QB", "RB", "WR"]}):
        with patch("modules.rankings.load_players", return_value=players_df):
            with patch(
                "modules.player_eligibility.filter_current_fantasy_players",
                side_effect=lambda df, **kwargs: df,
            ):
                with patch("modules.sleeper.get_rosters", return_value=_rosters()):
                    with patch(
                        "modules.trade_hub_engine.generate_trade_idea_records",
                        return_value=[],
                    ) as mock_generate:
                        trade_hub_engine.generate_trade_finder_records(
                            league_id="league-1",
                            roster_id=1,
                            strategy="contender",
                            lens="Dynasty",
                            players_db_path="unused.db",
                            trade_block_player_ids=("my-rb",),
                        )

    assert mock_generate.call_args.kwargs["trade_block_player_ids"] == ("my-rb",)
    assert mock_generate.call_args.kwargs["my_roster_id"] == 1
    assert mock_generate.call_args.kwargs["league_id"] == "league-1"


def test_generate_trade_finder_records_returns_empty_for_an_unknown_league():
    with patch("modules.sleeper.get_league", return_value=None):
        result = trade_hub_engine.generate_trade_finder_records(
            league_id="ghost-league",
            roster_id=1,
            strategy="contender",
            lens="Dynasty",
            players_db_path="unused.db",
            trade_block_player_ids=("my-rb",),
        )

    assert result == []


def test_generate_trade_idea_records_tags_ideas_that_land_a_gm_target():
    players_df = pd.DataFrame(
        [_player("my-qb", "QB", value=80), _player("my-rb", "RB", value=40), _player("opp-rb", "RB", value=70), _player("opp-wr", "WR", value=60)]
    )
    landing_idea = {
        "partner_team_name": "Rival GM",
        "rationale": "x",
        "trade_gain": 10,
        "trade_confidence_label": "High",
        "market_realism_label": "Realistic",
        "reasoning_tags": [],
        "send_assets": [],
        "receive_assets": [{"asset_type": "player", "player_id": "opp-rb", "name": "opp-rb"}],
    }
    other_idea = {
        "partner_team_name": "Other GM",
        "rationale": "x",
        "trade_gain": 5,
        "trade_confidence_label": "Low",
        "market_realism_label": "Thin",
        "reasoning_tags": [],
        "send_assets": [],
        "receive_assets": [{"asset_type": "player", "player_id": "opp-wr", "name": "opp-wr"}],
    }

    with patch("modules.sleeper.get_rosters", return_value=_rosters()):
        with patch("modules.sleeper.get_users", return_value=_users()):
            with patch(
                "modules.trade_ideas.build_trade_ideas",
                return_value=[landing_idea, other_idea],
            ):
                with patch.object(
                    trade_hub_engine,
                    "enforce_generated_trade_ideas",
                    side_effect=lambda ideas, **kwargs: ideas,
                ):
                    records = trade_hub_engine.generate_trade_idea_records(
                        league_id="league-1",
                        my_roster_id=1,
                        players_df=players_df,
                        rosters=_rosters(),
                        league_settings=SETTINGS,
                        score_field="dynasty_score",
                        team_strategy="contender",
                        gm_target_player_ids=("opp-rb",),
                    )

    assert records[0]["landed_gm_target_player_ids"] == ["opp-rb"]
    assert records[1]["landed_gm_target_player_ids"] == []

    card = trade_hub_engine.project_trade_idea_card(records[0])
    assert card.landed_gm_target_player_ids == ("opp-rb",)


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
    # Non-headline: falls back to trade_hub_presentation.trade_hub_display_section's
    # classification. reasoning_tags=["Need-Based"] contains the substring
    # "need" (checked before the trade_confidence_label=="High" fallback
    # this test originally expected), so it's classified Need-Based first.
    assert payload["category"] == "Need-Based"


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


def test_project_trade_idea_card_tags_high_confidence_as_high_impact():
    card = trade_hub_engine.project_trade_idea_card(_fake_idea(trade_confidence_label="High"))
    assert card.to_dict()["impact_tag"] == "high_impact"


def test_project_trade_idea_card_tags_buy_low_from_receive_side_opportunity_label():
    idea = _fake_idea(
        trade_confidence_label="Low",
        receive_assets=[
            {"asset_type": "player", "player_id": "opp-rb", "name": "opp-rb", "opportunity_label": "Backup With Upside"}
        ],
    )
    card = trade_hub_engine.project_trade_idea_card(idea)
    assert card.to_dict()["impact_tag"] == "buy_low"


def test_project_trade_idea_card_tags_sell_high_from_send_side_opportunity_label():
    idea = _fake_idea(
        trade_confidence_label="Low",
        receive_assets=[{"asset_type": "player", "player_id": "opp-rb", "name": "opp-rb"}],
        send_assets=[
            {"asset_type": "player", "player_id": "my-rb", "name": "my-rb", "opportunity_label": "Starter At Risk"}
        ],
    )
    card = trade_hub_engine.project_trade_idea_card(idea)
    assert card.to_dict()["impact_tag"] == "sell_high"


def test_project_trade_idea_card_tags_sell_high_from_send_side_cooling_workload_trend():
    # Real gap this covers: a player can be mid-tier opportunity (not
    # "Starter At Risk") while workload_trend="Cooling" — rankings.py's
    # weekly-recency read already confirmed a real, multi-week usage
    # decline (not a one-bad-week blip; see compute_recency_features'
    # own confidence gating). Before _player_asset carried workload_trend
    # and _classify_impact_tag read it, shopping that player never got
    # flagged sell_high unless it also happened to carry "Starter At Risk".
    idea = _fake_idea(
        trade_confidence_label="Low",
        receive_assets=[{"asset_type": "player", "player_id": "opp-rb", "name": "opp-rb"}],
        send_assets=[
            {
                "asset_type": "player",
                "player_id": "my-wr",
                "name": "my-wr",
                "opportunity_label": "Elite Opportunity",
                "workload_trend": "Cooling",
            }
        ],
    )
    card = trade_hub_engine.project_trade_idea_card(idea)
    assert card.to_dict()["impact_tag"] == "sell_high"


def test_project_trade_idea_card_leaves_impact_tag_empty_with_no_matching_signal():
    idea = _fake_idea(
        trade_confidence_label="Low",
        receive_assets=[{"asset_type": "player", "player_id": "opp-rb", "name": "opp-rb"}],
    )
    card = trade_hub_engine.project_trade_idea_card(idea)
    assert card.to_dict()["impact_tag"] == ""


def test_project_trade_idea_card_forwards_full_untruncated_side_totals():
    # web-next's Trade Hub lean bar (value_edge_lean_bar_html) needs the real
    # my_score/their_score the idea's trade_gain is derived from, not a
    # re-sum of the (possibly truncated) package assets.
    idea = _fake_idea(my_score=1200, their_score=1800)
    card = trade_hub_engine.project_trade_idea_card(idea)
    payload = card.to_dict()
    assert payload["send_score"] == 1200
    assert payload["receive_score"] == 1800


def test_project_trade_idea_card_defaults_side_totals_to_zero_when_absent():
    card = trade_hub_engine.project_trade_idea_card(_fake_idea())
    payload = card.to_dict()
    assert payload["send_score"] == 0
    assert payload["receive_score"] == 0


def test_concurrent_requests_for_same_key_single_flight(monkeypatch):
    """Two concurrent cache misses for the same (league, roster, strategy,
    lens, ...) key must run the expensive search exactly once, not once per
    caller.

    This is now enforced by a Redis-backed distributed lock
    (modules.redis_cache.redis_single_flight_cache), not a per-process
    functools.lru_cache + threading.Lock pair — the old in-process pair
    only protected one uvicorn worker; under docker-compose.yml's multiple
    mobile-api workers each would get its own separate lock/cache, so the
    same search could still run once per worker. tests/conftest.py's
    autouse fakeredis fixture backs generate_trade_idea_records_cached with
    a real (fake) Redis here, so this test exercises the actual code path.
    """

    monkeypatch.setattr(sleeper, "get_league", lambda _league_id: {"league_id": "x", "settings": {}})
    monkeypatch.setattr(sleeper, "get_rosters", lambda _league_id: [])
    monkeypatch.setattr(
        rankings, "load_players", lambda _db_path: pd.DataFrame([{"player_id": "p1", "name": "P1"}])
    )
    monkeypatch.setattr(
        player_eligibility, "filter_current_fantasy_players", lambda df, **_kwargs: df
    )
    monkeypatch.setattr(league_value_settings, "apply_valuation_lens", lambda df, *_args, **_kwargs: df)
    monkeypatch.setattr(league_value_settings, "valuation_score_field", lambda _lens: "value_score")

    call_count = 0
    call_count_lock = threading.Lock()

    def _slow_stub(*, league_id, **_kwargs):
        nonlocal call_count
        with call_count_lock:
            call_count += 1
        time.sleep(0.2)
        return [{"league_id": league_id, "ok": True}]

    monkeypatch.setattr(trade_hub_engine, "generate_trade_idea_records", _slow_stub)

    league_id = "test-single-flight-league"
    results: list[list[dict]] = []
    results_lock = threading.Lock()

    def _call():
        result = trade_hub_engine.generate_trade_idea_records_cached(
            league_id=league_id,
            roster_id=1,
            strategy="retool",
            lens="Dynasty",
            players_db_path="unused.db",
        )
        with results_lock:
            results.append(result)

    threads = [threading.Thread(target=_call) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert call_count == 1, "concurrent misses for the same key must single-flight to one real computation"
    assert len(results) == 8
    assert all(r and r[0]["league_id"] == league_id for r in results)


def test_generate_trade_idea_records_forwards_trade_finder_pick_controls():
    players_df = pd.DataFrame(
        [_player("my-qb", "QB", value=80), _player("my-rb", "RB", value=40), _player("opp-rb", "RB", value=70), _player("opp-wr", "WR", value=60)]
    )

    with patch("modules.sleeper.get_rosters", return_value=_rosters()):
        with patch("modules.sleeper.get_users", return_value=_users()):
            with patch("modules.trade_ideas.build_trade_ideas", return_value=[]) as mock_build:
                trade_hub_engine.generate_trade_idea_records(
                    league_id="league-1",
                    my_roster_id=1,
                    players_df=players_df,
                    rosters=_rosters(),
                    league_settings=SETTINGS,
                    score_field="dynasty_score",
                    team_strategy="contender",
                    trade_block_pick_ids=("2027:1:1",),
                    require_receive_picks=True,
                )

    assert mock_build.call_args.kwargs["trade_block_pick_ids"] == ["2027:1:1"]
    assert mock_build.call_args.kwargs["require_receive_picks"] is True
    assert mock_build.call_args.kwargs["trade_block_names"] == []


def _keeper_players_df():
    return pd.DataFrame(
        [_player("my-qb", "QB", value=80), _player("my-rb", "RB", value=60), _player("opp-rb", "RB", value=70), _player("opp-wr", "WR", value=40)]
    )


def _run_with_keeper_context(keeper_context):
    summary = pd.DataFrame(
        [{"league_id": "league-1", "roster_id": 1, "owner_id": "u1", "team_name": "Mine", "total_score": 80}]
    )
    with patch("modules.trade_ideas.build_trade_ideas", return_value=[]) as mock_build:
        trade_hub_engine.generate_trade_idea_records(
            league_id="league-1",
            my_roster_id=1,
            players_df=_keeper_players_df(),
            rosters=_rosters(),
            league_settings=SETTINGS,
            score_field="dynasty_score",
            df_summary=summary,
            keeper_context=keeper_context,
        )
    return mock_build.call_args.kwargs["df_players"].set_index("player_id")["dynasty_score"]


def test_generate_trade_idea_records_applies_keeper_surplus_and_skips_unknown_cost():
    base = _run_with_keeper_context(None)
    adj = _run_with_keeper_context(
        {
            "num_teams": 2,
            "current_picks": [{"player_id": "my-rb", "round": 10, "is_keeper": True}],
            "previous_picks": [],
            "round_penalty": 0,
        }
    )
    assert adj["my-rb"] > base["my-rb"]
    for pid in ("my-qb", "opp-rb", "opp-wr"):
        assert adj[pid] == base[pid]


def test_keeper_context_failure_falls_back_silently():
    with patch("modules.keepers.keeper_adjusted_values", side_effect=RuntimeError("boom")):
        out = _run_with_keeper_context({"num_teams": 2, "current_picks": [], "previous_picks": []})
    assert out.to_dict() == _run_with_keeper_context(None).to_dict()


def test_cached_ideas_only_pass_keeper_context_for_keeper_leagues():
    for keeper_mode in (True, False):
        with patch("modules.sleeper.get_league", return_value={"league_id": "L"}), patch(
            "modules.sleeper.get_rosters", return_value=_rosters()
        ), patch(
            "modules.league_value_settings.detect_league_value_settings_from_payload",
            return_value={"_keeper_mode": keeper_mode},
        ), patch(
            "modules.league_value_settings.build_valued_players_frame_cached", return_value=_keeper_players_df()
        ), patch(
            "modules.league_rankings.build_league_summary_and_draft_capital_cached",
            return_value=(pd.DataFrame(), None),
        ), patch.object(
            trade_hub_engine, "_keeper_context_for_league", return_value={"num_teams": 12, "round_penalty": 2}
        ), patch.object(trade_hub_engine, "generate_trade_idea_records", return_value=[]) as gen:
            trade_hub_engine._generate_trade_idea_records_cached("L", 1, "retool", "dynasty", "x.db", (), (), 2, 0)
        assert (gen.call_args.kwargs["keeper_context"] is not None) is keeper_mode


# --- Hold verdict / posture sentence -------------------------------------

def _card(gain=500, conf="High", impact=""):
    return {"trade_gain": gain, "confidence_label": conf, "impact_tag": impact}


def test_hold_none_when_a_strong_idea_exists():
    assert trade_hub_engine.build_hold_verdict(
        [_card(900, "High", "high_impact")], strategy="contender", power_rank=1, team_count=12
    ) is None


def test_hold_when_no_ideas():
    hold = trade_hub_engine.build_hold_verdict([], strategy="retool", power_rank=5, team_count=12)
    assert hold["verdict"] == "hold" and hold["reason"] == "no_ideas"
    assert hold["ideas_optional"] is False
    assert {w["factor"] for w in hold["why"]} >= {"ideas", "competition"}


def test_hold_when_nothing_clears_quality_threshold():
    cards = [_card(trade_hub_engine.HOLD_MIN_ACTIONABLE_TRADE_GAIN - 1, "High"), _card(900, "Low")]
    hold = trade_hub_engine.build_hold_verdict(cards, strategy="retool")
    assert hold["reason"] == "none_clear_bar" and hold["ideas_optional"] is True
    assert trade_hub_engine.build_hold_verdict([_card(trade_hub_engine.HOLD_MIN_ACTIONABLE_TRADE_GAIN, "Medium")]) is None


def test_hold_for_top_third_contender_without_high_impact_only():
    kwargs = {"strategy": "contender", "power_rank": 3, "team_count": 12}
    assert trade_hub_engine.build_hold_verdict([_card(500, "Medium")], **kwargs)["reason"] == "contender_no_need"
    assert trade_hub_engine.build_hold_verdict([_card(500, "High", "high_impact")], **kwargs) is None
    # Not a contender, or not near the top: trading stays the answer.
    assert trade_hub_engine.build_hold_verdict([_card(500, "Medium")], strategy="rebuild", power_rank=3, team_count=12) is None
    assert trade_hub_engine.build_hold_verdict([_card(500, "Medium")], strategy="contender", power_rank=9, team_count=12) is None


def test_hold_small_in_season_sample():
    kw = {"strategy": "retool", "in_season": True}
    assert trade_hub_engine.build_hold_verdict([_card()], season_progress=0.07, **kw)["reason"] == "small_sample"
    assert trade_hub_engine.build_hold_verdict([_card()], season_progress=0.5, **kw) is None
    assert trade_hub_engine.build_hold_verdict([_card()], season_progress=0.0, **kw) is None


def test_hold_trade_deadline_closed_uses_league_calendar():
    from modules import league_calendar

    league = {"status": "in_season", "settings": {"trade_deadline": 11, "leg": 12}}
    hold = trade_hub_engine.build_hold_verdict([_card()], trade_window=league_calendar.trade_window(league))
    assert hold["reason"] == "trade_deadline_passed" and hold["ideas_optional"] is False
    assert "week 11" in hold["why"][0]["text"]


def test_posture_sentence_is_plain_and_covers_every_strategy():
    for key in ("contender", "fringe_contender", "retool", "rebuild", "tank"):
        sentence = trade_hub_engine.posture_sentence(key)
        assert sentence.startswith("You're") and "strategy" not in sentence.lower()
    assert trade_hub_engine.posture_sentence("nope") == ""


def test_finder_closest_options_go_through_the_same_trust_enforcement():
    """A near miss is only offered when Trust enforcement would also keep it;
    and enforcement only runs on near misses when nothing realistic survived."""

    from modules import trade_ideas as trade_ideas_module

    players_df = pd.DataFrame(
        [_player("my-qb", "QB", value=80), _player("my-rb", "RB", value=40), _player("opp-rb", "RB", value=70), _player("opp-wr", "WR", value=60)]
    )
    kept_idea = {"partner_team_name": "A", "send_assets": [], "receive_assets": []}
    dropped_idea = {"partner_team_name": "B", "send_assets": [], "receive_assets": []}
    calls = []

    def fake_enforce(ideas, **kwargs):
        calls.append(list(ideas))
        return [i for i in ideas if i["partner_team_name"] == "A"]

    def fake_build(**kwargs):
        trace = kwargs["finder_trace"]
        trace.offer("market", 1.0, lambda: dict(kept_idea))
        trace.offer("market", 2.0, lambda: dict(dropped_idea))
        return []

    trace = trade_ideas_module.FinderSearchTrace()
    with patch("modules.sleeper.get_rosters", return_value=_rosters()):
        with patch("modules.sleeper.get_users", return_value=_users()):
            with patch("modules.trade_ideas.build_trade_ideas", side_effect=fake_build):
                with patch("modules.trade_hub_engine.enforce_generated_trade_ideas", side_effect=fake_enforce):
                    result = trade_hub_engine.generate_trade_idea_records(
                        league_id="league-1",
                        my_roster_id=1,
                        players_df=players_df,
                        rosters=_rosters(),
                        league_settings=SETTINGS,
                        score_field="dynasty_score",
                        team_strategy="contender",
                        trade_block_pick_ids=("2027:1:1",),
                        finder_trace=trace,
                    )

    assert result == []
    assert [i["partner_team_name"] for i in trace.enforced_closest] == ["A"]
    assert len(calls) == 2  # real ideas, then the near misses
