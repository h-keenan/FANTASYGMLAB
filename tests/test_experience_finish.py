"""Founder Beta experience-finish contracts for League Memory, grades, Trade Hub, PQV."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

from PIL import Image

from modules.compact_fantasy_assets import COMPACT_FANTASY_ASSET_CSS
from modules.player_awards import award_rows_for_player, build_player_awards, build_season_cache_index
from modules.portrait_normalization import SLEEPER_CARD_FOCUS_X, alpha_bbox, card_focus_x, sleeper_family_card_focus, subject_center_pct
from modules.recommendation_trust_ux import executive_trade_detail_html


ROOT = Path(__file__).resolve().parents[1]


def test_grade_engine_is_separate_from_history_records():
    history = (ROOT / "modules" / "league_history.py").read_text(encoding="utf-8")
    grades = (ROOT / "modules" / "transaction_grades.py").read_text(encoding="utf-8")
    assert "letter_from_ratio" not in history
    assert "grade_trade" in grades
    assert "Do not store" in grades or "immutable" in grades.casefold() or "computed from" in grades.casefold()


def test_alpha_family_focus_is_systemic():
    image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    pixels = image.load()
    for y in range(10, 90):
        for x in range(28, 82):
            pixels[x, y] = (200, 120, 80, 255)
    center = subject_center_pct(image)
    box = alpha_bbox(image)
    assert box == (28, 10, 82, 90)
    assert center["left_margin_pct"] > center["right_margin_pct"]
    family = sleeper_family_card_focus([center, center, center])
    assert family["focus_x"] == SLEEPER_CARD_FOCUS_X
    assert family["focus_x"] == card_focus_x()


def test_accolades_production_cache_path_has_real_rows():
    cache_dir = ROOT / "data"
    index = build_season_cache_index(cache_dir)
    assert index, "sleeper_player_stats season caches must exist for production accolades"
    players_path = cache_dir / "sleeper_players.json"
    assert players_path.exists(), "sleeper_players.json supplies positions for award finishes"
    import json

    directory = json.loads(players_path.read_text(encoding="utf-8"))
    lookup = {
        str(player_id): str(row.get("position") or "")
        for player_id, row in directory.items()
        if isinstance(row, Mapping) and str(row.get("position") or "")
    }
    found = None
    payload = index[0]["payload"]
    for player_id, row in payload.items():
        if not isinstance(row, dict) or row.get("fantasy_points_ppr") in (None, 0, 0.0):
            continue
        position = lookup.get(str(player_id), "")
        if position not in {"WR", "RB", "QB", "TE"}:
            continue
        rows = award_rows_for_player(
            index,
            player_id=str(player_id),
            current_row={"player_id": player_id, "position": position},
            position=position,
            position_lookup=lookup,
        )
        badges = build_player_awards(rows, position=position)
        if badges:
            found = badges
            break
    assert found is not None, "canonical season caches plus player directory should yield awards"
    assert all(item.season for item in found)
