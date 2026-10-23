from dataclasses import FrozenInstanceError

import pytest

from modules import football_assets


def asset(**overrides):
    values = {
        "player_id": "player-1",
        "display_name": "A Player",
        "position": "WR",
        "team": "MIN",
        "prestige_label": "Starter",
        "prestige_level": "starter",
        "value_label": "Dynasty Score",
        "value": "82",
        "insight": "Reliable weekly role.",
        "age": "Age 24",
    }
    values.update(overrides)
    return football_assets.FootballPlayerAsset(**values)


def test_player_asset_is_frozen_and_rejects_unknown_prestige():
    model = asset()
    with pytest.raises(FrozenInstanceError):
        model.team = "CHI"
    with pytest.raises(ValueError):
        asset(prestige_level="page-specific")


@pytest.mark.parametrize("density", ("compact", "standard", "dense"))
def test_canonical_player_card_preserves_one_hierarchy_for_all_densities(density):
    html = football_assets.player_card_html(asset(), density=density)
    assert f"dg-football-asset--{density}" in html
    assert html.index("dg-football-asset__name") < html.index("dg-football-asset__meta")
    assert html.index("dg-football-asset__meta") < html.index("dg-football-asset__badges")
    assert html.index("dg-football-asset__badges") < html.index("dg-football-asset__insight")
    assert html.index("dg-football-asset__insight") < html.index("dg-football-asset__value")


def test_action_and_read_only_modes_have_distinct_accessibility_contracts():
    action_html = football_assets.player_card_html(asset(), mode="action-enabled")
    assert "role='button'" in action_html
    assert "tabindex='0'" in action_html
    assert "Open Player Quick View for A Player" in action_html
    assert "data-player-id='player-1'" in action_html

    read_only_html = football_assets.player_card_html(asset(), mode="read-only")
    assert "role='button'" not in read_only_html
    assert "tabindex='0'" not in read_only_html
    assert "data-player-id=" not in read_only_html


def test_compatibility_classes_are_not_duplicated():
    html = football_assets.player_card_html(
        asset(),
        extra_classes=("player-card-tappable", "legacy-player-card"),
    )
    opening_tag = html.split(">", 1)[0]
    assert opening_tag.count("player-card-tappable") == 1


def test_model_text_is_escaped_by_default():
    html = football_assets.player_card_html(
        asset(display_name="<script>alert(1)</script>", insight="<b>unsafe</b>")
    )
    assert "<script>" not in html
    assert "<b>unsafe</b>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;unsafe&lt;/b&gt;" in html


@pytest.mark.parametrize(
    ("status", "visible"),
    (("Q", "Ques"), ("O", "Out"), ("D", "Doubt"), ("IR", "IR"), ("PUP", "PUP"), ("SUSP", "SUSP")),
)
def test_injury_component_supports_existing_statuses(status, visible):
    html = football_assets.injury_badge_html(status)
    assert f">{visible}<" in html
    assert "aria-label='Player status:" in html
    assert "title='Player status:" in html
    assert "dg-football-injury" in html


def test_injury_component_recognizes_sleeper_real_suspension_spelling():
    """Injury-awareness audit finding (2026-10-19 valuation-system audit):
    this component already anticipated a "SUSPENDED" status (see the
    parametrized case above) but Sleeper's real `injury_status` feed sends
    the literal, shorter "Sus" (confirmed against data/sleeper_players.json
    — e.g. C.J. Gardner-Johnson). That real spelling fell through to a raw,
    neutral-toned "SUS" badge instead of the danger-toned "SUSP" shown for
    every other hard-out status (IR, PUP, ...).
    """

    html = football_assets.injury_badge_html("Sus")
    assert ">SUSP<" in html
    assert "dg-football-injury--danger" in html
    assert "dg-football-injury--neutral" not in html


def test_prestige_indicator_has_fixed_semantic_rail_and_accessible_text():
    html = football_assets.prestige_indicator_html("Elite", "elite")
    assert "dg-football-prestige--elite" in html
    assert "dg-football-prestige__rail" in html
    assert "aria-hidden='true'" in html
    assert "Premium status: Elite" in html


def test_football_asset_module_does_not_import_page_or_business_modules():
    source = __import__("inspect").getsource(football_assets)
    for forbidden in ("app", "trade_hub", "waivers", "rankings", "valuation", "streamlit"):
        assert f"import {forbidden}" not in source
