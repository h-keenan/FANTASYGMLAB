from __future__ import annotations

from pathlib import Path

from modules import premium
from modules import trade_hub_presentation


def _ideas(count: int, *, tier: str = "primary") -> list[dict]:
    return [
        {
            "idea_id": f"{tier}-{index}",
            "trade_surface_tier": tier,
        }
        for index in range(count)
    ]


def test_section_filter_helper_is_removed():
    source = (Path(__file__).resolve().parents[1] / "modules" / "trade_hub_presentation.py").read_text(
        encoding="utf-8"
    )
    assert "def render_trade_hub_section_filter(" not in source
    assert "st.pills(" not in source
