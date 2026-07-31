from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts" / "league_intelligence_visual_harness.py"


def test_app_test_feed_renders_context_actions_assets_and_disclosures():
    application = AppTest.from_file(str(HARNESS), default_timeout=30).run()
    assert not application.exception
    html = "\n".join(item.value for item in application.markdown)
    assert "League Intelligence Harness" in application.title[0].value
    assert "Synthetic Owned Player limited at practice" in html
    assert "Synthetic Waiver Player earns a larger role" in html
    assert "Owned by you" in html
    assert "Available on waivers" in html
    assert "Injury Monitor" in html
    assert "Waiver Watch" in html
    assert "dg-football-asset" in html
    assert len(application.button) == 2
    assert all("Why this matters" in button.label for button in application.button)


def test_app_test_disclosure_expands_only_selected_item():
    application = AppTest.from_file(str(HARNESS), default_timeout=30).run()
    application.button[0].click().run()
    html = "\n".join(item.value for item in application.markdown)
    assert html.count("<div class='dg-intelligence-explanation'") == 1
    assert "League context: Owned by you." in html
    assert application.button[0].label.startswith("▾")
    assert application.button[1].label.startswith("▸")
