"""Founder Beta experience-finish contracts for League Memory, grades, Trade Hub, PQV."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

from PIL import Image

from modules.app_styles import APP_CSS
from modules.compact_fantasy_assets import COMPACT_FANTASY_ASSET_CSS
from modules.league_history_styles import LEAGUE_HISTORY_CSS
from modules.league_recaps_styles import LEAGUE_RECAPS_CSS
from modules.player_awards import award_rows_for_player, build_player_awards, build_season_cache_index
from modules.player_quick_view_styles import PLAYER_QUICK_VIEW_CSS
from modules.portrait_normalization import SLEEPER_CARD_FOCUS_X, alpha_bbox, card_focus_x, sleeper_family_card_focus, subject_center_pct
from modules.recommendation_trust_ux import executive_trade_detail_html
from modules.trade_detail_styles import TRADE_DETAIL_CSS
from modules.trade_hub_ui import TRADE_SUMMARY_COMPONENT_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_recaps_auto_load_without_gate():
    ui = (ROOT / "modules" / "league_recaps_ui.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "Load league recaps" not in ui.casefold()
    assert "Recaps stay off until you open them" not in ui
    assert "render_section_gate" not in ui
    assert "mark_deferred_section_ready" in ui
    recaps_block = app.split('if current_page == "league_recaps":', 1)[1].split(
        "# WEEKLY LEAGUE REPORT", 1
    )[0]
    assert "Load league recaps" not in recaps_block.casefold()


def test_league_memory_destination_owns_recaps_history_storylines():
    ui = (ROOT / "modules" / "league_recaps_ui.py").read_text(encoding="utf-8")
    assert "MEMORY_VIEWS = (\"Recaps\", \"History\", \"Storylines\")" in ui
    assert "render_league_history_section(" in ui
    assert "include_header=False" in ui
    assert "include_storylines=False" in ui
    assert "render_storylines_panel(" in ui
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    rankings = app.split('if current_page in {"rankings"', 1)[1].split("# LEAGUE RECAPS", 1)[0]
    assert "render_league_history_section(" not in rankings
    assert "render_storylines_panel(" not in rankings
    assert "league_history_ui.render_league_history_section(" not in app


def test_history_renderer_is_reused_not_duplicated():
    ui = (ROOT / "modules" / "league_history_ui.py").read_text(encoding="utf-8")
    recaps = (ROOT / "modules" / "league_recaps_ui.py").read_text(encoding="utf-8")
    assert ui.count("def render_league_history_section(") == 1
    assert recaps.count("def render_league_history_section(") == 0
    assert recaps.count("league_history_ui.render_league_history_section(") == 1


def test_grade_engine_is_separate_from_history_records():
    history = (ROOT / "modules" / "league_history.py").read_text(encoding="utf-8")
    grades = (ROOT / "modules" / "transaction_grades.py").read_text(encoding="utf-8")
    assert "letter_from_ratio" not in history
    assert "grade_trade" in grades
    assert "Do not store" in grades or "immutable" in grades.casefold() or "computed from" in grades.casefold()


def test_trade_detail_has_no_supporting_expanders():
    html = executive_trade_detail_html(
        {
            "Reason": "You add future flexibility.",
            "Evidence": "Fringe contender · RB need",
            "Risk": "Strong fit, believable path.",
            "Expected outcome": "Favorable · Net +237",
            "Supporting metrics": "Low confidence · Plausible market",
        },
        verdict="Favorable",
        value_delta="+237",
        confidence="Low confidence",
    )
    assert "<details" not in html
    assert "Supporting evidence" not in html
    assert "Supporting metrics" not in html
    assert "tvl-cue--why" in html
    assert "tvl-cue--risk" in html
    assert "tvl-cue--evidence" in html
    assert "tvl-cue--market" in html
    assert "Expected outcome" not in html
    hub = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    assert "Load supporting metrics" not in hub
    assert "supporting_trade_detail_html" not in hub.split("def _trade_detail_dialog()", 1)[1][:4000]


def test_trade_hub_component_uses_full_board_width():
    css = TRADE_SUMMARY_COMPONENT_CSS.replace(" ", "")
    assert ".trade-summary-card{" in css
    assert "width:100%" in css
    assert "width:max-content" not in css.split(".trade-summary-card{", 1)[1][:400]
    assert "host.style.width = \"100%\"" in (ROOT / "modules" / "interaction_contract.py").read_text(
        encoding="utf-8"
    )
    host = TRADE_DETAIL_CSS.replace(" ", "")
    assert "st-key-trade_hub_headline" in host
    assert "iframe" in host
    assert "st-key-trade_hub_show_more" in host
    assert "max-width:min(76rem,100%)" in host


def test_no_per_player_portrait_offsets():
    blob = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "modules" / "app_styles.py",
            ROOT / "modules" / "portrait_normalization.py",
            ROOT / "modules" / "compact_fantasy_assets.py",
            ROOT / "modules" / "trade_hub_ui.py",
            ROOT / "modules" / "football_asset_styles.py",
        )
    )
    assert "tracy" not in blob.casefold()
    assert "11566" not in blob
    assert "[data-player-id" not in blob
    from modules.portrait_normalization import card_focus_x, load_family_focus

    focus = card_focus_x()
    payload = load_family_focus()
    assert payload.get("sample_count") == 5
    assert payload.get("method") == "rendered_face_plate_after_absolute_stack"
    assert focus == payload["focus_x"]
    assert f"--dg-headshot-focus-x: {focus}" in APP_CSS
    assert "--dg-headshot-focus-x: 50%" in APP_CSS.split(".dg-player-headshot--profile", 1)[1][:180]
    assert "heuristic" in str(payload.get("classification") or "").casefold()


def test_family_focus_cache_owns_production_css():
    from modules.portrait_normalization import FAMILY_HEADSHOT_IDS, card_focus_x, load_family_focus, measure_family

    payload = load_family_focus()
    focus = float(str(payload["focus_x"]).rstrip("%"))
    rows = measure_family(focus_x=focus)
    assert [row["player_id"] for row in rows] == list(FAMILY_HEADSHOT_IDS)
    assert payload["sample_count"] == 5
    for row in rows:
        assert row["image_box"][0] > 100
        assert row["alpha_bbox"]
        assert "painted_subject_center_before" in row
        assert "painted_subject_center_after" in row
        assert abs(row["center_delta_from_square_after"]) <= 3.0
    compact = (ROOT / "modules" / "compact_fantasy_assets.py").read_text(encoding="utf-8")
    assert "card_focus_x()" in compact or "FOCUS_X" in compact
    compact_css = COMPACT_FANTASY_ASSET_CSS
    assert "position:relative" in compact_css.split(".dg-compact-asset-avatar,.dg-compact-pick-plate{", 1)[1][:500]
    img_rule = compact_css.split(".dg-compact-asset-avatar img{", 1)[1].split("}", 1)[0]
    assert "position:absolute" in img_rule.replace(" ", "")
    assert "inset:0" in img_rule.replace(" ", "")
    fallback_rule = compact_css.split(".dg-compact-asset-avatar .dg-player-headshot-fallback{", 1)[1].split("}", 1)[0]
    assert "position:absolute" in fallback_rule.replace(" ", "")
    assert "inset:0" in fallback_rule.replace(" ", "")
    pqv = PLAYER_QUICK_VIEW_CSS
    assert "object-position:center var(--dg-headshot-focus, 22%) !important" in pqv.replace("\n", "")
    assert "transform-origin:center var(--dg-headshot-focus, 22%) !important" in pqv.replace("\n", "")
    assert "grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);" in TRADE_SUMMARY_COMPONENT_CSS
    assert "grid-template-columns: max-content auto max-content;" not in TRADE_SUMMARY_COMPONENT_CSS
    assert card_focus_x() in APP_CSS


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


def test_pqv_actions_sit_with_hero_not_between_career_and_details():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    pqv = app[
        app.index("def render_player_quick_view_content(") : app.index(
            "def render_player_detail_content("
        )
    ]
    assert pqv.index("current_season_summary_html(") < pqv.index("pqv_hero_html(")
    assert pqv.index("pqv_hero_html(") < pqv.index("recommendation_context_html(")
    assert pqv.index("recommendation_context_html(") < pqv.index("pqv_primary_workspace_html(")
    assert pqv.index("pqv_primary_workspace_html(") < pqv.index("pqv_actions_")
    assert pqv.index("Open in Trade Hub") < pqv.index("pqv_detail_nav_")
    actions = pqv.index("pqv_actions_")
    nav = pqv.index("pqv_detail_nav_")
    assert actions < nav


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


def test_css_caps_and_route_ownership():
    assert len(APP_CSS) < 390_000
    assert ".dg-lh-feed" not in APP_CSS
    assert ".dg-recap-edition" not in APP_CSS
    assert "max-width:min(68rem,100%)" in LEAGUE_HISTORY_CSS.replace(" ", "")
    assert ".dg-recap-grades" in LEAGUE_RECAPS_CSS
    compact = (ROOT / "modules" / "compact_fantasy_assets.py").read_text(encoding="utf-8")
    assert re.search(r"object-position[^;]*(tracy|hurts|mooney)", compact, re.I) is None


def test_no_new_explicit_rerun_in_memory_or_grades():
    for rel in (
        "modules/league_recaps_ui.py",
        "modules/league_history_ui.py",
        "modules/transaction_grades.py",
        "modules/portrait_normalization.py",
    ):
        source = (ROOT / rel).read_text(encoding="utf-8")
        assert "st.rerun" not in source
