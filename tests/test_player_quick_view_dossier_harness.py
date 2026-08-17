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
        "Why we value him this way",
        "Current fantasy evidence",
        "Recent News",
    ):
        assert marker in html
    assert "Accolades" in html
    assert "pqv-accolade" in html
    assert "Recommendation Context" not in html
    assert "Career Timeline" not in html
    assert "Career Context" not in html
    assert "Value &amp; Health" not in html
    button_labels = [item.label for item in application.button]
    assert "More details" in button_labels
    assert "Open in Trade Hub" in button_labels
    assert button_labels.index("Open in Trade Hub") < button_labels.index("More details")
    assert "View full career resume" not in button_labels


def test_app_test_dossier_lower_priority_sections_are_collapsed_by_default():
    application = AppTest.from_file(str(HARNESS), default_timeout=30).run()
    assert not application.exception
    html = "\n".join(item.value for item in application.markdown)
    assert "Executive Summary" not in html
    assert "Complete Season Stats" not in html


def test_app_test_dossier_more_details_reveals_deep_material():
    application = AppTest.from_file(str(HARNESS), default_timeout=30).run()
    assert not application.exception
    more = next(item for item in application.button if item.label == "More details")
    more.click().run()
    html = "\n".join(item.value for item in application.markdown)
    assert "Complete Season Stats" in html or any(
        "Complete Season Stats" in str(item.value) for item in application.markdown
    )
    assert "Executive Summary" in html
    assert "Career Timeline" in html
    assert "Career Context" in html
    assert any(item.label == "Hide details" for item in application.button)
