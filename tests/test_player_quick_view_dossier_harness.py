from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts" / "player_quick_view_dossier_harness.py"


def test_app_test_dossier_renders_executive_hierarchy_and_lazy_sections():
    application = AppTest.from_file(str(HARNESS), default_timeout=30).run()
    assert not application.exception
    html = "\n".join(item.value for item in application.markdown)
    for marker in (
        "Synthetic Player",
        "Recommendation",
        "Current Value",
        "Executive Summary",
        "Career Resume",
    ):
        assert marker in html
    assert "Recommendation Context" not in html
    assert "Career Timeline" not in html
    assert "Recent News" in [item.label for item in application.expander]
    assert "Advanced Details" in [item.label for item in application.expander]
    # Current Season lives inside Advanced Details (still present in AppTest markdown).
    assert "Current Season" in html
    assert application.button[0].label == "View full career resume"
    assert application.button[1].label == "Open in Trade Hub"


def test_app_test_dossier_lower_priority_sections_are_collapsed_by_default():
    application = AppTest.from_file(str(HARNESS), default_timeout=30).run()
    assert not application.exception
    assert all(not item.proto.expanded for item in application.expander)


def test_app_test_dossier_expands_full_history_deterministically():
    application = AppTest.from_file(str(HARNESS), default_timeout=30).run()
    application.button[0].click().run()
    assert not application.exception
    html = "\n".join(item.value for item in application.markdown)
    assert "2023" in html
    assert "WR4 fantasy finish" in html
    assert "Career Timeline" in html
    assert application.button[0].label == "Collapse career history"
