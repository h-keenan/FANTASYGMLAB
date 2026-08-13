from pathlib import Path

from modules.app_styles import APP_CSS


def test_supported_toolbar_mode_removes_developer_controls():
    config = Path(".streamlit/config.toml").read_text(encoding="utf-8")
    assert '[client]' in config
    assert 'toolbarMode = "minimal"' in config
    assert 'showErrorDetails = "none"' in config


def test_production_chrome_is_hidden_and_founder_navigation_remains():
    for selector in (
        '[data-testid="stHeader"]',
        '[data-testid="stToolbar"]',
        '[data-testid="stMainMenu"]',
        '[data-testid="stAppDeployButton"]',
        '[data-testid="stStatusWidget"]',
        '[data-testid="stDecoration"]',
        '[data-testid="stElementToolbar"]',
    ):
        assert selector in APP_CSS
    source = Path("app.py").read_text(encoding="utf-8")
    assert "render_mobile_navigation_shell(" in source
    assert "render_platform_topbar(" in source


def test_style_injection_uses_supported_non_layout_streamlit_api():
    source = Path("modules/html_rendering.py").read_text(encoding="utf-8")
    assert "st.html(normalized_style_block(css_or_style))" in source
    assert "st.markdown(normalized_style_block" not in source
