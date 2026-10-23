import re

from modules.design_tokens import DESIGN_TOKEN_CSS


def _properties(css: str) -> dict[str, str]:
    return {
        name: value.strip()
        for name, value in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", css)
    }


def test_semantic_tokens_match_the_design_system_specification():
    tokens = _properties(DESIGN_TOKEN_CSS)
    expected = {
        # FantasyDesk brand sheet (2026-10-17) — Midnight/Charcoal/Graphite
        # foundation, Bone text, Field/Touchdown accent. See
        # DESIGN_TOKEN_CSS's own inline comment for the contrast math.
        "--color-bg": "#000000",
        "--color-shell": "#000000",
        "--color-surface-primary": "#1f2226",
        "--color-text-primary": "#f7f8fa",
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
        "--primary-color": "var(--color-accent-strong)",
        "--background-color": "var(--color-bg)",
        "--secondary-background-color": "var(--color-surface-primary)",
        "--text-color": "var(--color-text-primary)",
    }
    assert {name: tokens[name] for name in expected} == expected


def test_token_layer_defines_no_component_or_page_selectors():
    without_root = DESIGN_TOKEN_CSS.replace(":root", "")
    assert not re.search(r"\.[a-zA-Z_][\w-]*\s*[{,]", without_root)
    assert "[data-testid" not in DESIGN_TOKEN_CSS
    assert "@media" not in DESIGN_TOKEN_CSS
