from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


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
    _keyed_button(app, "toa_add_receive_player_partner_player").click().run(timeout=30)
    assert _keyed_button(app, "toa_add_receive_player_partner_player").disabled
    assert not _button(app, "Analyze Trade").disabled
    _button(app, "Analyze Trade").click().run(timeout=30)
    assert any(item.value == "Analysis complete" for item in app.success)
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
    assert not _button(app, "Analyze Trade").disabled
    _button(app, "Analyze Trade").click().run(timeout=30)
    assert any(item.value == "Analysis complete" for item in app.success)


def test_pick_for_pick_real_controls_enable_analyze():
    app = AppTest.from_file(
        str(ROOT / "scripts" / "interaction_integrity_harness.py")
    ).run(timeout=30)
    _keyed_radio(app, "toa_send_kind").set_value("Picks").run(timeout=30)
    _keyed_button(app, "toa_add_send_pick_2027_2_me").click().run(timeout=30)
    _keyed_radio(app, "toa_receive_kind").set_value("Picks").run(timeout=30)
    _keyed_button(app, "toa_add_receive_pick_2027_2_partner").click().run(timeout=30)
    assert not _button(app, "Analyze Trade").disabled
