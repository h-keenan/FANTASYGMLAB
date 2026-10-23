"""My Team decision-first IA + Dashboard disclosure cleanup."""

from __future__ import annotations

from pathlib import Path

from modules import football_assets, player_tier_identity


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = (ROOT / "modules" / "dashboard_workflow.py").read_text(encoding="utf-8")


def test_queue_q_injury_badge_is_labeled():
    html = football_assets.injury_badge_html("Q")
    assert ">Ques<" in html
    assert "aria-label='Player status:" in html
    assert "title='Player status:" in html
    assert ">Q<" not in html


def test_player_tier_ladder_unchanged():
    assert [tier.tier_id for tier in player_tier_identity.PLAYER_TIER_LADDER] == [
        "generational",
        "elite",
        "impact_starter",
        "starter",
        "contributor",
        "committee_role",
        "depth_developmental",
    ]
