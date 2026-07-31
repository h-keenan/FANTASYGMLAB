import re

from modules.app_styles import APP_CSS
from modules.design_tokens import DESIGN_TOKEN_CSS
from modules.ux_polish_styles import FOUNDER_BETA_UX_CSS


def _properties(css: str) -> dict[str, str]:
    return {
        name: value.strip()
        for name, value in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", css)
    }


def test_design_tokens_are_a_single_source_loaded_first_in_global_styles():
    assert "DynastyGM semantic design tokens" in DESIGN_TOKEN_CSS
    assert "<style" not in DESIGN_TOKEN_CSS
    assert APP_CSS.startswith("\n<style>\n" + DESIGN_TOKEN_CSS)
    assert APP_CSS.count("<style") == 1
    assert "dynastygm-design-tokens" not in FOUNDER_BETA_UX_CSS


def test_semantic_tokens_match_the_design_system_specification():
    tokens = _properties(DESIGN_TOKEN_CSS)
    expected = {
        "--color-bg": "#050607",
        "--color-shell": "#090a0c",
        "--color-surface-primary": "#0f1114",
        "--color-text-primary": "#f8fafc",
        "--color-text-secondary": "#e5e7eb",
        "--color-text-muted": "#a8adb7",
        "--color-border": "#2a2e35",
        "--color-accent": "#67e8f9",
        "--color-success": "#22c55e",
        "--color-opportunity": "#14b8a6",
        "--color-action": "#facc15",
        "--color-warning": "#f59e0b",
        "--color-danger": "#ef4444",
        "--color-premium": "#facc15",
        "--color-experimental": "#8b93ff",
        "--space-xs": "4px",
        "--space-sm": "8px",
        "--space-md": "12px",
        "--space-lg": "16px",
        "--space-xl": "24px",
        "--radius-sm": "0",
        "--radius-md": "0",
        "--radius-lg": "0",
        "--shadow-card": "0 3px 0 rgba(0, 0, 0, 0.34)",
        "--shadow-overlay": "0 8px 24px rgba(0, 0, 0, 0.46)",
        "--font-size-page-title": "1.5rem",
        "--font-size-card-title": "0.875rem",
        "--font-size-body": "0.875rem",
        "--font-size-caption": "0.75rem",
        "--focus-ring": "0 0 0 3px rgba(103, 232, 249, 0.34)",
        "--control-min-height": "44px",
        "--touch-target-min": "44px",
    }
    assert {name: tokens[name] for name in expected} == expected


def test_legacy_theme_aliases_resolve_to_identical_values():
    tokens = _properties(DESIGN_TOKEN_CSS)
    app_properties = _properties(APP_CSS.split(DESIGN_TOKEN_CSS, 1)[1])
    aliases = {
        "--dg-theme-bg": "--color-bg",
        "--dg-theme-shell": "--color-shell",
        "--dg-theme-surface-primary": "--color-surface-primary",
        "--dg-theme-surface-secondary": "--color-surface-secondary",
        "--dg-theme-surface-raised": "--color-surface-raised",
        "--dg-theme-surface-muted": "--color-surface-muted",
        "--dg-theme-text": "--color-text-primary",
        "--dg-theme-text-muted": "--color-text-muted",
        "--dg-theme-divider": "--color-border",
        "--dg-theme-accent-cyan": "--color-accent",
        "--dg-theme-accent-silver": "--color-text-secondary",
        "--dg-theme-success": "--color-success",
        "--dg-theme-opportunity": "--color-opportunity",
        "--dg-theme-action": "--color-action",
        "--dg-theme-caution": "--color-warning",
        "--dg-theme-danger": "--color-danger",
        "--dg-theme-diagnostic": "--color-diagnostic",
    }
    for legacy_name, token_name in aliases.items():
        assert app_properties[legacy_name] == f"var({token_name})"
        assert tokens[token_name]


def test_shared_ux_aliases_preserve_accessibility_values():
    properties = _properties(FOUNDER_BETA_UX_CSS)
    assert properties["--dg-ux-control-height"] == "var(--control-min-height)"
    assert properties["--dg-ux-focus-ring"] == "var(--focus-ring)"
    assert properties["--dg-ux-small-type"] == "var(--font-size-caption)"

    tokens = _properties(DESIGN_TOKEN_CSS)
    assert tokens["--control-min-height"] == "44px"
    assert tokens["--touch-target-min"] == "44px"
    assert tokens["--focus-ring"] == "0 0 0 3px rgba(103, 232, 249, 0.34)"
    assert tokens["--font-size-caption"] == "0.75rem"


def test_token_layer_defines_no_component_or_page_selectors():
    without_root = DESIGN_TOKEN_CSS.replace(":root", "")
    assert not re.search(r"\.[a-zA-Z_][\w-]*\s*[{,]", without_root)
    assert "[data-testid" not in DESIGN_TOKEN_CSS
    assert "@media" not in DESIGN_TOKEN_CSS
