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
        "Dynasty value",
        "Why",
        "Current Season",
        "Career",
    ):
        assert marker in html
    assert "pqv-accolade" in html
    assert "Recent News" not in html
    assert "Recommendation Context" not in html
    assert "Career Timeline" not in html
    assert "Career Context" not in html
    assert "Value &amp; Health" not in html
    button_labels = [item.label for item in application.button]
    assert "STATS" in button_labels
    assert "Open in Trade Hub" in button_labels
    assert button_labels.index("Open in Trade Hub") < button_labels.index("STATS")
    assert "View full career resume" not in button_labels


def test_app_test_dossier_lower_priority_sections_are_collapsed_by_default():
    application = AppTest.from_file(str(HARNESS), default_timeout=30).run()
    assert not application.exception
    html = "\n".join(item.value for item in application.markdown)
    assert "Executive Summary" not in html
    assert "Complete Season Stats" not in html
    assert "Bio" not in html


def test_app_test_dossier_more_details_reveals_deep_material():
    application = AppTest.from_file(str(HARNESS), default_timeout=30).run()
    assert not application.exception
    more = next(item for item in application.button if item.label == "STATS")
    more.click().run()
    html = "\n".join(item.value for item in application.markdown)
    assert "Complete Season Stats" in html or any(
        "Complete Season Stats" in str(item.value) for item in application.markdown
    )
    assert "Executive Summary" not in html
    assert "Career Context" not in html
