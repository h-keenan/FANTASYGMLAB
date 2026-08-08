from pathlib import Path

from streamlit.testing.v1 import AppTest

from modules import dashboard_orientation


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts" / "dashboard_visual_harness.py"


def _app() -> AppTest:
    return AppTest.from_file(str(HARNESS), default_timeout=60).run()


def _markdown_text(application: AppTest) -> str:
    return "\n".join(str(element.value) for element in application.markdown)


def _button(application: AppTest, label: str):
    return next(button for button in application.button if button.label == label)


def test_fixture_harness_isolated_from_production_entrypoint_and_uses_synthetic_data():
    source = HARNESS.read_text(encoding="utf-8")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "dashboard_visual_harness" not in app_source
    assert "Fixture Account" in source
    assert "visual-league-a" in source
    assert "auth_session" not in source
    assert "access_token" not in source
    assert "password" not in source.casefold()


def test_free_dashboard_first_render_has_orientation_game_plan_and_gated_pulse():
    application = _app()
    markup = _markdown_text(application)

    assert not application.exception
    assert dashboard_orientation.ORIENTATION_TITLE in markup
    assert '<ol class="dg-ui-card-list">' in markup
    assert markup.count('class="dg-ui-card-list-item"') == 4
    assert "Today&#x27;s Game Plan" in markup or "Today's Game Plan" in markup
    assert "Top Priority" in markup
    assert "dg-daily-briefing-item-primary" in markup
    assert "Your Next Move" not in markup
    assert "More next moves" in markup
    assert "Full League Pulse" in markup
    assert "Fixture Account" in markup
    assert "Synthetic fixture only" in "\n".join(
        str(caption.value) for caption in application.caption
    )


def test_premium_dashboard_shows_full_fixture_content_without_upgrade_prompts():
    application = _app()
    application.sidebar.radio[1].set_value("premium").run()
    markup = _markdown_text(application)

    assert not application.exception
    assert "Today&#x27;s Game Plan" in markup or "Today's Game Plan" in markup
    assert "Fixture Trade Partner" in markup
    assert "Biggest Contender" in markup
    assert "More next moves" not in markup
    assert "Full League Pulse" not in markup
    assert "Your Next Move" not in markup


def test_orientation_modal_opens_with_canonical_content():
    application = _app()
    _button(application, "How FantasyGM Lab works").click().run()

    assert not application.exception
    assert len(application.get("dialog")) == 1
    assert "Keep it current" in _markdown_text(application)


def test_dismissal_survives_rerun_and_applies_across_leagues_until_reset():
    application = _app()
    _button(application, "Don't show again").click().run()
    assert dashboard_orientation.ORIENTATION_TITLE not in _markdown_text(application)

    application.sidebar.selectbox[0].set_value("League B").run()
    assert dashboard_orientation.ORIENTATION_TITLE not in _markdown_text(application)

    _button(application, "Reset onboarding").click().run()
    assert dashboard_orientation.ORIENTATION_TITLE in _markdown_text(application)


def test_startup_shell_does_not_mount_dashboard_content():
    application = _app()
    application.sidebar.radio[0].set_value("Startup shell").run()
    markup = _markdown_text(application)

    assert not application.exception
    assert "Restoring your session" in markup
    assert dashboard_orientation.ORIENTATION_TITLE not in markup
    assert "Highest-priority roster" not in markup


def test_long_name_and_empty_recommendation_states_are_structurally_safe():
    application = _app()
    application.sidebar.checkbox[0].check().run()
    application.sidebar.radio[2].set_value("Empty").run()
    markup = _markdown_text(application)

    assert not application.exception
    assert "Extraordinarily Long Synthetic Dynasty League" in markup
    assert "No move needed right now" in markup
    assert "Your Next Move" not in markup


def test_harness_exposes_native_accessible_orientation_actions():
    application = _app()
    labels = [button.label for button in application.button]

    assert labels.index("Review My Team") < labels.index("How FantasyGM Lab works")
    assert labels.index("How FantasyGM Lab works") < labels.index(
        "Don't show again"
    )
    for label in (
        "Review My Team",
        "How FantasyGM Lab works",
        "Don't show again",
    ):
        button = _button(application, label)
        assert button.help
        assert button.key.startswith(
            dashboard_orientation.ORIENTATION_STATE_PREFIX
        )


def test_reduced_motion_touch_target_and_responsive_contracts_remain_token_backed():
    tokens = (ROOT / "modules" / "design_tokens.py").read_text(encoding="utf-8")
    primitive_css = (
        ROOT / "modules" / "ui_primitive_styles.py"
    ).read_text(encoding="utf-8")
    modal_css = (ROOT / "modules" / "ui_modal_styles.py").read_text(encoding="utf-8")
    polish_css = (ROOT / "modules" / "ux_polish_styles.py").read_text(encoding="utf-8")

    assert "--control-min-height: 44px" in tokens
    assert "@media (prefers-reduced-motion: reduce)" in primitive_css
    assert "@media (max-width: 640px)" in modal_css
    assert '[data-testid="stButton"] > button:focus-visible' in polish_css
