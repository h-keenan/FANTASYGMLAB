from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts" / "football_asset_visual_harness.py"


def test_app_test_harness_renders_all_densities_and_states():
    application = AppTest.from_file(str(HARNESS), default_timeout=30).run()
    assert not application.exception
    html = "\n".join(item.value for item in application.markdown)
    for density in ("compact", "standard", "dense"):
        assert f"dg-football-asset--{density}" in html
    assert "Long Synthetic Player Name" in html
    assert "Synthetic Injured Player" in html
    assert "Synthetic Read Only Player" in html
    assert "dg-football-injury--danger" in html


def test_harness_contains_no_customer_or_runtime_data_dependencies():
    source = HARNESS.read_text(encoding="utf-8")
    for forbidden in ("supabase", "session_state", "league_id", "auth", "database"):
        assert forbidden not in source.lower()
