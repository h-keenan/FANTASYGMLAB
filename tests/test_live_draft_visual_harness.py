from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts" / "ui_validation_harness.py"


def test_live_draft_fixture_renders_read_only_decision_hierarchy():
    application = AppTest.from_file(str(HARNESS), default_timeout=30)
    application.query_params["surface"] = "live-draft"
    application.run()
    markup = "\n".join(str(element.value) for element in application.markdown)

    assert not application.exception
    assert "Who should I draft next?" in markup
    assert "Recommended pick" in markup
    assert markup.count("Alternative") >= 3
    assert "Value vs ADP" in markup
    assert "Roster impact" in markup
    assert "Your next picks: #12, #17, #36" in markup
    assert "Available Player Rankings" in markup
    assert "Live Team Rankings" in markup
    assert "Draft Board" in markup


def test_live_draft_fixture_uses_canonical_player_assets_and_hard_edges():
    application = AppTest.from_file(str(HARNESS), default_timeout=30)
    application.query_params["surface"] = "live-draft"
    application.run()
    markup = "\n".join(str(element.value) for element in application.markdown)
    styles = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")

    assert "dg-football-asset" in markup
    assert "player-card-tappable" in markup
    assert "live-draft-rec-card" in markup
    assert "border-radius: var(--radius-panel)" in styles
    assert "grid-template-columns: 1fr" in styles


def test_live_draft_harness_is_synthetic_and_not_imported_by_production():
    harness = HARNESS.read_text(encoding="utf-8")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "Fixture Quarterback" in harness
    assert "Synthetic fixture only" in harness
    assert "ui_validation_harness" not in app_source
    for secret in ("password", "access_token", "refresh_token"):
        assert secret not in harness.casefold()
