from __future__ import annotations

from pathlib import Path
from modules import trade_analyzer_builder as builder
from modules import trade_analyzer_assembly as assembly
from modules import trade_ideas
from modules import transaction_grades_ui
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


def test_analyzer_is_not_fragment_split_from_analyze_owner():
    ui = (ROOT / "modules" / "trade_analyzer_ui.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "@st.fragment" not in ui
    assert "package_is_analyzable(" in app
    assert 'data-dg-scroll-anchor="trade-analyzer-builder"' in app


def test_history_uses_one_why_and_one_future_pick_note():
    report = {
        "kind": "trade",
        "provisional": True,
        "sides": [
            {
                "team": "A",
                "letter": "A",
                "tone": "success",
                "confidence": "Low confidence",
                "why": "Received 2000 current value against 1500 sent. Future pick value is estimated until the selection is known.",
            },
            {
                "team": "B",
                "letter": "D",
                "tone": "risk",
                "confidence": "Low confidence",
                "why": "Received 1500 current value against 2000 sent. Future pick value is estimated until the selection is known.",
            },
        ],
    }
    html = transaction_grades_ui.trade_grade_html(report)
    assert html.count("<span>Why</span>") == 1
    assert html.count("Future pick value is estimated") == 1


def test_semantic_values_never_use_ellipsis_and_header_bridge_is_zero_layout():
    dense = (ROOT / "modules" / "dense_list_styles.py").read_text(encoding="utf-8")
    header = (ROOT / "modules" / "executive_command_header_styles.py").read_text(encoding="utf-8")
    assert "min-width:max-content" in dense
    assert "text-overflow:clip" in dense
    assert "st-key-player_quick_view_parent_bridge" in header
    assert "height: 0 !important" in header


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
