from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts" / "premium_visual_harness.py"


def _app() -> AppTest:
    return AppTest.from_file(str(HARNESS), default_timeout=30).run()


def test_harness_is_synthetic_and_not_wired_to_production():
    source = HARNESS.read_text(encoding="utf-8")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "premium_visual_harness" not in app_source
    assert "fixture-user" in source
    assert "create_checkout_session = _fixture_checkout_session" in source


def test_free_page_renders_two_direct_plan_cards_without_staged_cta():
    application = _app()
    markup = "\n".join(str(markdown.value) for markdown in application.markdown)
    assert "$3.99" in markup and "$19.99" in markup
    assert "Start Founder Premium checkout" not in markup
    assert "Continue to checkout" not in markup
    assert not application.exception


def test_existing_premium_subscriber_has_no_purchase_actions():
    application = _app()
    application.sidebar.radio[0].set_value("Premium").run()
    assert "Included now with Premium" in "\n".join(
        str(markdown.value) for markdown in application.markdown
    )
