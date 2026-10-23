"""Contracts for product-wide UI design-system consolidation."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from modules.design_tokens import DESIGN_TOKEN_CSS


ROOT = Path(__file__).resolve().parents[1]


def _properties(css: str) -> dict[str, str]:
    return {
        name: value.strip()
        for name, value in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", css)
    }


def test_semantic_aliases_and_radius_scale_exist():
    tokens = _properties(DESIGN_TOKEN_CSS)
    for name in (
        "--surface-1",
        "--surface-2",
        "--surface-raised",
        "--surface-interactive",
        "--surface-selected",
        "--text-primary",
        "--text-muted",
        "--text-positive",
        "--text-negative",
        "--border-subtle",
        "--border-standard",
        "--border-strong",
        "--border-accent",
        "--radius-square",
        "--radius-control",
        "--radius-panel",
        "--radius-pill",
        "--radius-segment",
    ):
        assert name in tokens
    assert tokens["--radius-control"] == "0"
    assert tokens["--radius-panel"] == "0"
    assert tokens["--radius-pill"] == "2px"
    assert tokens["--radius-segment"] == "999px"
    assert tokens["--surface-1"] == "var(--color-surface-primary)"
