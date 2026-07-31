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
        "Snapshot",
        "Career Profile",
        "Current Season",
        "Professional Production",
        "Fantasy Production",
        "Usage",
        "News",
        "Recommendation Context",
    ):
        assert marker in html
    assert "Recent News" in [item.label for item in application.expander]
    assert "Advanced Details" in [item.label for item in application.expander]
    assert application.button[0].label == "Open in Trade Hub"


def test_app_test_dossier_lower_priority_sections_are_collapsed_by_default():
    application = AppTest.from_file(str(HARNESS), default_timeout=30).run()
    assert not application.exception
    assert all(not item.proto.expanded for item in application.expander)
