from pathlib import Path

from modules.design_tokens import DESIGN_TOKEN_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_geometry_tokens_are_rectilinear():
    for token in (
        "--radius-sm: 0",
        "--radius-md: 0",
        "--radius-lg: 0",
        "--radius-panel: 0",
    ):
        assert token in DESIGN_TOKEN_CSS
    assert "--radius-pill: 2px" in DESIGN_TOKEN_CSS


def test_monochrome_foundation_and_semantic_prestige_tokens_exist():
    for token in (
        "--color-bg: #000000",
        "--color-surface-primary: #1f2226",
        "--color-surface-secondary: #1f2226",
        "--color-prestige-elite",
        "--color-prestige-starter",
        "--color-prestige-contributor",
        "--color-prestige-development",
        "--color-prestige-depth",
        "--color-prestige-replacement",
        "--color-position-qb",
        "--color-position-wr",
    ):
        assert token in DESIGN_TOKEN_CSS
