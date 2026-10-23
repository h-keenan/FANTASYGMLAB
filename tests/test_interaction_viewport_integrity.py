from __future__ import annotations

from pathlib import Path
from modules import trade_analyzer_builder as builder
from modules import trade_analyzer_assembly as assembly
from modules import trade_ideas
from modules import alerts_activity


ROOT = Path(__file__).resolve().parents[1]


def _player(player_id: str, name: str, owner: str, score: int = 1000) -> dict:
    return {
        "asset_type": "player",
        "player_id": player_id,
        "name": name,
        "label": name,
        "owner_roster_id": owner,
        "score": score,
        "value_score": score,
    }


def _pick(label: str, owner: str, season: int = 2027, round_no: int = 2) -> dict:
    return {
        "asset_type": "pick",
        "label": label,
        "name": label,
        "season": season,
        "round": round_no,
        "owner_roster_id": owner,
        "score": 1200,
    }


def test_analyze_contract_accepts_every_canonical_asset_family():
    parker = _player("parker-washington", "Parker Washington", "me")
    partner = _player("partner-player", "Partner Player", "partner")
    my_pick = _pick("2027 Round 2", "me")
    their_pick = _pick("2027 Round 2", "partner")
    packages = (
        ([parker], [their_pick]),
        ([parker], [partner]),
        ([my_pick], [their_pick]),
        ([parker, my_pick], [partner]),
        ([parker], [partner, their_pick]),
        ([parker, my_pick], [partner, their_pick]),
    )
    for send, receive in packages:
        assert builder.package_is_analyzable(send, receive)
    assert not builder.package_is_analyzable([], [their_pick])
    assert not builder.package_is_analyzable([parker], [])
    assert not builder.package_is_analyzable([{"asset_type": "player"}], [their_pick])


def test_real_add_and_remove_callback_mutates_canonical_state_on_first_call():
    state = {assembly.SEND_KEY: [], assembly.RECEIVE_KEY: []}
    parker = _player("parker-washington", "Parker Washington", "me")
    their_pick = _pick("2027 Round 2", "partner")
    added_send = assembly.mutate_package(
        state,
        asset=parker,
        package_key=assembly.SEND_KEY,
        action="add",
        my_roster_id="me",
        partner_roster_id="partner",
    )
    added_receive = assembly.mutate_package(
        state,
        asset=their_pick,
        package_key=assembly.RECEIVE_KEY,
        action="add",
        my_roster_id="me",
        partner_roster_id="partner",
    )
    assert added_send.ok and added_receive.ok
    assert builder.package_is_analyzable(
        state[assembly.SEND_KEY], state[assembly.RECEIVE_KEY]
    )
    removed = assembly.mutate_package(
        state,
        package_key=assembly.RECEIVE_KEY,
        action="remove",
        index=0,
    )
    assert removed.ok
    assert state[assembly.RECEIVE_KEY] == []


def test_shell_and_analyzer_contexts_do_not_alternate_package_reset():
    state = {
        "trade_asset_strategy_context": "ppr|fringe_contender",
        assembly.SEND_KEY: [],
        assembly.RECEIVE_KEY: [],
    }
    assert assembly.ensure_package_context(
        state, context_key="ppr|fringe-contender"
    )
    assembly.mutate_package(
        state,
        asset=_player("parker-washington", "Parker Washington", "me"),
        package_key=assembly.SEND_KEY,
        action="add",
        my_roster_id="me",
        partner_roster_id="partner",
    )
    assert not assembly.ensure_package_context(
        state, context_key="ppr|fringe-contender"
    )
    assert [asset["name"] for asset in state[assembly.SEND_KEY]] == [
        "Parker Washington"
    ]
    assert state["trade_asset_strategy_context"] == "ppr|fringe_contender"


def test_alerts_real_composer_populates_each_applicable_source_filter():
    session = {
        "_decision_memory_cache_events": [
            {
                "event_id": "decision-1",
                "league_id": "L1",
                "title": "Hold the current offer",
                "reason": "The value gap remains too wide.",
            }
        ]
    }
    events = [
        {
            "id": "news-1",
            "league_id": "L1",
            "category": "NEWS",
            "title": "League-wide injury update",
            "news_roster_relationship": "",
        },
        {
            "id": "roster-1",
            "league_id": "L1",
            "category": "ROSTER",
            "title": "Parker Washington role update",
            "news_roster_relationship": "MY_BENCH",
        },
        {
            "id": "league-1",
            "league_id": "L1",
            "category": "LEAGUE",
            "title": "Trade completed in your league",
        },
        {
            "id": "urgent-1",
            "league_id": "L1",
            "category": "URGENT",
            "title": "Starter ruled out",
            "news_roster_relationship": "MY_STARTER",
            "should_alert": True,
        },
    ]
    rows = alerts_activity.compose_activity_timeline(
        session=session,
        league_id="L1",
        entitlement="premium",
        news_events=events,
    )
    for tab in (
        alerts_activity.FILTER_IMPORTANT,
        alerts_activity.FILTER_MY_PLAYERS,
        alerts_activity.FILTER_NEWS,
        alerts_activity.FILTER_LEAGUE,
        alerts_activity.FILTER_DECISIONS,
    ):
        assert alerts_activity.filter_timeline(rows, tab), tab
