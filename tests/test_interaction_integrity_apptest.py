from __future__ import annotations

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from streamlit.runtime.state.session_state_proxy import SessionStateProxy


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _restore_streamlit_session_proxy():
    """Some legacy tests replace the module proxy without restoring it."""

    st.session_state = SessionStateProxy()


def _button(app: AppTest, label: str, occurrence: int = 0):
    matches = [button for button in app.button if button.label == label]
    return matches[occurrence]


def _keyed_button(app: AppTest, prefix: str):
    return next(button for button in app.button if str(button.key or "").startswith(prefix))


def _keyed_radio(app: AppTest, key: str):
    return next(radio for radio in app.radio if radio.key == key)


def test_real_controls_add_first_tap_enable_analyze_and_remove_first_tap():
    app = AppTest.from_file(
        str(ROOT / "scripts" / "interaction_integrity_harness.py")
    ).run(timeout=30)
    assert not app.exception
    assert _button(app, "Analyze Trade").disabled

    _keyed_button(app, "toa_add_send_player_parker_washington").click().run(timeout=30)
    assert _keyed_button(app, "toa_add_send_player_parker_washington").disabled
    assert app.session_state["trade_send_assets"][0]["name"] == "Parker Washington"
    assert not any(
        "Nothing queued to send" in str(item.value) for item in app.markdown
    )
    _keyed_button(app, "toa_add_receive_player_partner_player").click().run(timeout=30)
    assert _keyed_button(app, "toa_add_receive_player_partner_player").disabled
    assert not _button(app, "Analyze Trade").disabled
    _button(app, "Analyze Trade").click().run(timeout=30)
    assert any(item.value == "Analysis complete" for item in app.success)
    assert app.session_state["fixture_evaluated_send"][0]["name"] == "Parker Washington"
    assert app.session_state["fixture_evaluated_receive"][0]["name"] == "Partner Player"
    _button(app, "×", 0).click().run(timeout=30)
    assert not _keyed_button(app, "toa_add_send_player_parker_washington").disabled
    assert _button(app, "Analyze Trade").disabled


def test_parker_washington_for_2027_round_2_real_controls_analyze():
    app = AppTest.from_file(
        str(ROOT / "scripts" / "interaction_integrity_harness.py")
    ).run(timeout=30)
    _keyed_button(app, "toa_add_send_player_parker_washington").click().run(timeout=30)
    _keyed_radio(app, "toa_receive_kind").set_value("Picks").run(timeout=30)
    _keyed_button(app, "toa_add_receive_pick_2027_2_partner").click().run(timeout=30)
    assert _keyed_button(app, "toa_add_send_player_parker_washington").disabled
    assert _keyed_button(app, "toa_add_receive_pick_2027_2_partner").disabled
    assert app.session_state["trade_receive_assets"][0]["label"] == "2027 Round 2"
    assert not _button(app, "Analyze Trade").disabled
    _button(app, "Analyze Trade").click().run(timeout=30)
    assert any(item.value == "Analysis complete" for item in app.success)
    assert app.session_state["fixture_evaluated_send"][0]["name"] == "Parker Washington"
    assert app.session_state["fixture_evaluated_receive"][0]["label"] == "2027 Round 2"


def test_reset_package_clears_the_same_canonical_owner():
    app = AppTest.from_file(
        str(ROOT / "scripts" / "interaction_integrity_harness.py")
    ).run(timeout=30)
    _keyed_button(app, "toa_add_send_player_parker_washington").click().run(timeout=30)
    _keyed_button(app, "toa_add_receive_player_partner_player").click().run(timeout=30)
    assert not _button(app, "Analyze Trade").disabled
    _button(app, "Reset package").click().run(timeout=30)
    assert app.session_state["trade_send_assets"] == []
    assert app.session_state["trade_receive_assets"] == []
    assert _button(app, "Analyze Trade").disabled


def test_pick_for_pick_real_controls_enable_analyze():
    app = AppTest.from_file(
        str(ROOT / "scripts" / "interaction_integrity_harness.py")
    ).run(timeout=30)
    _keyed_radio(app, "toa_send_kind").set_value("Picks").run(timeout=30)
    _keyed_button(app, "toa_add_send_pick_2027_2_me").click().run(timeout=30)
    _keyed_radio(app, "toa_receive_kind").set_value("Picks").run(timeout=30)
    _keyed_button(app, "toa_add_receive_pick_2027_2_partner").click().run(timeout=30)
    assert not _button(app, "Analyze Trade").disabled
    _button(app, "Analyze Trade").click().run(timeout=30)
    assert app.session_state["fixture_evaluated_send"][0]["label"] == "2027 Round 2"
    assert app.session_state["fixture_evaluated_receive"][0]["label"] == "2027 Round 2"


def test_mixed_multi_asset_real_controls_reach_evaluator_once_each():
    app = AppTest.from_file(
        str(ROOT / "scripts" / "interaction_integrity_harness.py")
    ).run(timeout=30)
    _keyed_button(app, "toa_add_send_player_parker_washington").click().run(timeout=30)
    _keyed_radio(app, "toa_send_kind").set_value("Picks").run(timeout=30)
    _keyed_button(app, "toa_add_send_pick_2027_2_me").click().run(timeout=30)
    _keyed_button(app, "toa_add_receive_player_partner_player").click().run(timeout=30)
    _button(app, "Analyze Trade").click().run(timeout=30)
    assert [asset.get("name") or asset.get("label") for asset in app.session_state["fixture_evaluated_send"]] == [
        "Parker Washington",
        "2027 Round 2",
    ]
    assert [asset.get("name") for asset in app.session_state["fixture_evaluated_receive"]] == [
        "Partner Player"
    ]
