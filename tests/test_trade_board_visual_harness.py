from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts" / "trade_board_visual_harness.py"


def test_trade_board_visual_harness_is_synthetic_and_production_isolated():
    source = HARNESS.read_text(encoding="utf-8")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "trade_board_visual_harness" not in app_source
    assert "Synthetic fixture only" in source
    assert "access_token" not in source
    assert "password" not in source.casefold()
    assert "auth_session" not in source


def test_trade_board_visual_harness_uses_production_summary_renderer():
    source = HARNESS.read_text(encoding="utf-8")
    assert "trade_hub_ui.render_trade_idea_card(" in source
    assert 'key_prefix="trade_board_visual_fixture"' in source
    assert source.count('"partner_roster_id"') == 2
    assert '"asset_type": "pick"' in source


def test_trade_board_visual_harness_runs_without_application_exception():
    application = AppTest.from_file(str(HARNESS), default_timeout=60).run()
    assert not application.exception
