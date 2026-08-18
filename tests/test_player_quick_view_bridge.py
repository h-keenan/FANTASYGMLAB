from types import SimpleNamespace
from unittest.mock import patch

from modules import player_quick_view_bridge, trade_detail_navigation


def test_bridge_closes_matching_trade_and_returns_canonical_request():
    state = {}
    trade_detail_navigation.open_trade(state, "trade-17")
    result = SimpleNamespace(
        open={
            "player_id": "player-9",
            "trade_key": "trade-17",
            "source_label": "Trade Hub",
        }
    )
    with patch.object(
        player_quick_view_bridge,
        "PLAYER_QUICK_VIEW_BRIDGE_COMPONENT",
        return_value=result,
    ) as component:
        request = player_quick_view_bridge.consume_player_quick_view_request(state)

    assert request == {
        "player_id": "player-9",
        "trade_key": "trade-17",
        "source_label": "Trade Hub",
    }
    assert trade_detail_navigation.current(state).trade_key == ""
    assert component.call_args.kwargs["key"] == "player_quick_view_parent_bridge"


def test_bridge_ignores_empty_or_invalid_payloads_without_changing_trade():
    state = {}
    trade_detail_navigation.open_trade(state, "trade-17")
    with patch.object(
        player_quick_view_bridge,
        "PLAYER_QUICK_VIEW_BRIDGE_COMPONENT",
        return_value=SimpleNamespace(open={"player_id": ""}),
    ):
        assert player_quick_view_bridge.consume_player_quick_view_request(state) == {}
    assert trade_detail_navigation.current(state).trade_key == "trade-17"


def test_bridge_is_parent_owned_and_does_not_create_a_dialog_or_rerun():
    source = __import__("pathlib").Path(player_quick_view_bridge.__file__).read_text(
        encoding="utf-8"
    )
    assert "st.dialog" not in source
    assert "st.rerun" not in source
    assert player_quick_view_bridge.PLAYER_QUICK_VIEW_EVENT in source
