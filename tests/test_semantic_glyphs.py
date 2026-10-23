"""Canonical semantic glyph registry and GM Orb / Dashboard mapping."""

from __future__ import annotations

from pathlib import Path

from modules import ui_architecture
from modules.semantic_glyphs import (
    CONCEPTS,
    DESTINATION_CONCEPT,
    SEMANTIC_GLYPH_CSS,
    concept_for,
    concept_for_destination,
    concept_for_header,
    glyph_html,
    glyph_mask_data_uri,
    route_row_glyph_html,
    gm_orb_row_css,
    svg_markup,
)


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_concept_set_is_small_and_reusable():
    assert 8 <= len(CONCEPTS) <= 12
    for name in (
        "home",
        "roster",
        "trade",
        "waiver",
        "rankings",
        "draft",
        "league",
        "insights",
        "alerts",
        "history",
        "more",
    ):
        assert name in CONCEPTS


def test_every_visible_destination_has_a_glyph_concept():
    for page in ui_architecture.PLATFORM_DESTINATIONS:
        if page.category == "ARCHIVED":
            continue
        assert concept_for_destination(page.key) in CONCEPTS
        html = route_row_glyph_html(page.key)
        assert f"data-dg-glyph='{concept_for_destination(page.key)}'" in html
        assert "<svg" in html
        assert f"st-key-mobile_sheet_nav_{page.key}" in gm_orb_row_css()


def test_league_overview_does_not_share_the_rankings_bars_concept():
    assert "rankings" in CONCEPTS
    assert concept_for_destination("rankings") == "league"
    assert "data-dg-glyph='league'" in route_row_glyph_html("rankings")
    assert concept_for_destination("players") == "rankings"
    assert "data-dg-glyph='rankings'" in route_row_glyph_html("players")


def test_glyph_html_is_decorative_inline_svg_without_emoji_or_network():
    html = glyph_html("trade_hub", size="row")
    assert "aria-hidden='true'" in html
    assert "<svg" in html
    assert "data-dg-glyph='trade'" in html
    assert "http://" not in html
    assert "https://" not in html
    assert "emoji" not in html.casefold()
    joined = svg_markup("home") + svg_markup("alerts") + SEMANTIC_GLYPH_CSS
    assert "😀" not in joined
    assert "@fortawesome" not in joined
    assert "fontawesome" not in joined.casefold()
    assert "iconify" not in joined.casefold()


def test_no_external_icon_dependency_in_requirements():
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8").casefold()
    for blocked in ("fontawesome", "font-awesome", "iconify", "feather-icons", "material-icons"):
        assert blocked not in req


def test_visible_destination_labels_are_unique():
    labels = [
        page.label
        for page in ui_architecture.PLATFORM_DESTINATIONS
        if page.category != "ARCHIVED"
    ]
    assert labels
    assert len(labels) == len(set(labels))


def test_orb_row_css_puts_glyph_on_the_real_button():
    css = gm_orb_row_css()
    assert "button::before" in css
    assert '[data-testid="stElementContainer"]:has(.dg-gm-route-glyph)' not in css
    assert "max-height:0!important" not in css
    assert "dg-gm-route-glyph" not in css


def test_future_memory_concepts_reuse_history_glyph_and_add_recaps_route():
    assert concept_for("recap") == "history"
    assert concept_for("storylines") == "history"
    assert concept_for_destination("league_recaps") == "history"
    keys = {page.key for page in ui_architecture.PLATFORM_DESTINATIONS}
    assert "league_recaps" in keys
    assert "storylines" not in keys
    recaps = next(page for page in ui_architecture.PLATFORM_DESTINATIONS if page.key == "league_recaps")
    assert recaps.group == "LEAGUE"
    assert recaps.category == "CORE"
