"""Founder Beta color-system cleanup: tokens own accents; leftover sky/blue is gone."""

from __future__ import annotations

from pathlib import Path

from modules.design_tokens import DESIGN_TOKEN_CSS


ROOT = Path(__file__).resolve().parents[1]

LEGACY_HEX = (
    "#38bdf8",
    "#7dd3fc",
    "#bae6fd",
    "#00c2ff",
    "#00d4ff",
    "#2563eb",
    "#050816",
    "#111827",
    "#e0f2fe",
    "#cffafe",
    "#0ea5e9",
    "#3b82f6",
    "#60a5fa",
)

LEGACY_RGB = (
    "56, 189, 248",
    "125, 211, 252",
    "14, 165, 233",
    "96, 165, 250",
    "37, 99, 235",
    "59, 130, 246",
)


def _lower(text: str) -> str:
    return text.lower()


def test_design_tokens_bridge_streamlit_theme_variables():
    assert "--primary-color: var(--color-accent-strong);" in DESIGN_TOKEN_CSS
    assert "--background-color: var(--color-bg);" in DESIGN_TOKEN_CSS
    assert "--color-accent: #67e8f9;" in DESIGN_TOKEN_CSS
    assert "--color-accent-strong: #22d3ee;" in DESIGN_TOKEN_CSS
    assert "--focus-ring: 0 0 0 3px rgba(103, 232, 249, 0.34);" in DESIGN_TOKEN_CSS


def test_intentional_brand_cyan_and_light_mark_contrast_are_retained():
    assert "--color-accent: #67e8f9;" in DESIGN_TOKEN_CSS
    assert "--color-brand-accent: #22d3ee;" in DESIGN_TOKEN_CSS
    # #0891B2 was a CSS light-surface contrast tweak for the retired FGL Arc
    # Monogram's cyan arc (drawn in pure CSS). The current mark is real PNG
    # artwork, not a CSS-colored shape, so light-surface contrast is now
    # handled by asset selection (a navy monochrome cut) rather than a CSS
    # hex — see modules/brand_identity.ASSET_PATHS["mark_mono_light"]. The
    # Founder Beta badge (removed with that positioning) was the last
    # BRAND_IDENTITY_CSS consumer of --color-brand-accent; the token itself
    # remains defined and used elsewhere via DESIGN_TOKEN_CSS.
    assert "--color-success: #22c55e;" in DESIGN_TOKEN_CSS
    assert "--color-warning: #f59e0b;" in DESIGN_TOKEN_CSS
    assert "--color-danger: #ef4444;" in DESIGN_TOKEN_CSS
    assert "--color-diagnostic: #8b93ff;" in DESIGN_TOKEN_CSS
