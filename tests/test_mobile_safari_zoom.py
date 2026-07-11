from pathlib import Path

from modules.app_styles import APP_CSS


def test_mobile_form_controls_use_ios_safe_font_size():
    required_selectors = [
        'input[type="text"]',
        'input[type="number"]',
        'input[type="password"]',
        'input[type="email"]',
        "textarea",
        "select",
        '[role="combobox"]',
        '[data-testid="stTextInput"] input',
        '[data-testid="stNumberInput"] input',
        '[data-testid="stTextArea"] textarea',
        '[data-testid="stSelectbox"] [role="combobox"]',
        '[data-baseweb="select"] [role="combobox"]',
    ]
    for selector in required_selectors:
        assert selector in APP_CSS

    assert "@media (max-width: 900px)" in APP_CSS
    assert "font-size: 16px !important;" in APP_CSS


def test_mobile_zoom_accessibility_is_not_disabled():
    searchable_paths = [Path("app.py"), *Path("modules").glob("*.py")]
    combined = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in searchable_paths)
    lowered = combined.casefold()

    assert "user-scalable=no" not in lowered
    assert "user-scalable=0" not in lowered
    assert "maximum-scale=1" not in lowered
    assert "maximum-scale=1.0" not in lowered


def test_touch_action_manipulation_is_limited_to_controls():
    assert "touch-action: manipulation;" in APP_CSS
    for blocked_selector in (
        "body {\n        touch-action: manipulation",
        ".stApp {\n        touch-action: manipulation",
        "main {\n        touch-action: manipulation",
        ".block-container {\n        touch-action: manipulation",
    ):
        assert blocked_selector not in APP_CSS

    for control_selector in (
        "button",
        "[role=\"button\"]",
        "[data-testid=\"stRadio\"] label",
        "[data-testid=\"stCheckbox\"] label",
        "div[class*=\"st-key-mobile_gm_sheet_trigger_\"] button",
        "div[class*=\"st-key-global_feedback_\"] button",
    ):
        assert control_selector in APP_CSS
