"""League leaderboard presentation modernization — structure only, no ranking math."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import league_display


ROOT = Path(__file__).resolve().parents[1]


def _ranked_row(rank: int) -> str:
    return league_display.ranked_leaderboard_row_html(
        rank_label=f"#{rank}",
        team_name=f"Team {rank}",
        owner_text="@manager",
        primary_metric="10-3",
        metric_label="Record",
        logo_html="<div class='dg-ranked-logo'>T</div>",
        top_three=rank <= 3,
        first_place=rank == 1,
    )


def test_dead_modules_removed():
    for relative in (
        "modules/app_header.py",
        "modules/executive_visual_finalization_styles.py",
        "modules/executive_info_compression_styles.py",
        "modules/age_model.py",
        "modules/news_factor.py",
    ):
        assert not (ROOT / relative).exists(), relative


def test_cleanup_doc_exists():
    doc = ROOT / "docs" / "league-leaderboards-and-repo-cleanup.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "ranked_leaderboard_row_html" in text
    assert "Dead-code audit" in text or "dead-code" in text.casefold()
