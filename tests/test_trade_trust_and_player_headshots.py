from pathlib import Path

import pandas as pd

from modules import trade_ideas


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


ONE_QB_DYNASTY = {
    "league_format": "Dynasty",
    "qb_format": "1QB",
    "league_size": 12,
    "qb_count": 1,
    "rb_count": 2,
    "wr_count": 3,
    "te_count": 1,
}


def player(label, score, position, *, role="Flex", tier="Starter", age=26):
    return {
        "asset_type": "player",
        "label": label,
        "score": score,
        "position": position,
        "role": role,
        "player_tier": tier,
        "age": age,
    }


def pick(label, score, round_num, season=2027):
    return {
        "asset_type": "pick",
        "label": label,
        "score": score,
        "position": "PICK",
        "round": round_num,
        "season": season,
    }


def neutral_shape(**overrides):
    shape = {
        "needs": [],
        "surplus": [],
        "strategy": "balanced",
        "mode": "balanced",
        "roster_over_limit": False,
        "roster_at_limit": False,
    }
    shape.update(overrides)
    return shape


def test_hurts_for_pearsall_and_2027_third_is_hard_rejected():
    hurts = player("Jalen Hurts", 5000, "QB", role="Core", tier="Core Starter", age=27)
    pearsall = player("Ricky Pearsall", 3837, "WR", tier="Starter", age=25)
    third = pick("2027 Round 3", 1400, 3)
    market = trade_ideas.evaluate_trade_market_realism(
        send_assets=[hurts],
        receive_assets=[pearsall, third],
        my_shape=neutral_shape(),
        partner_shape=neutral_shape(),
        partner_name="Partner",
        league_settings=ONE_QB_DYNASTY,
    )
    confidence = trade_ideas._trade_confidence_context(
        fit_context={"score": 30, "partner_score": 12},
        market_context=market,
        reasoning_tags=["Value Arbitrage"],
        reasoning_summary="Raw package delta is positive.",
    )
    assert market["value_delta"] == 237
    assert market["hard_fail"] is True
    assert "protected_outgoing" in market["hard_fail_flags"]
    assert "low_pick_quality_bridge" in market["hard_fail_flags"]
    assert confidence["label"] == "Low"
    assert confidence["headline_ready"] is False


def test_protected_assets_are_excluded_automatically_but_selectable_explicitly():
    core_qb = player("Elite QB", 6200, "QB", role="Core Starter", tier="Core Starter")
    assert trade_ideas._automatic_outgoing_asset_allowed(core_qb) is False
    assert (
        trade_ideas._automatic_outgoing_asset_allowed(
            core_qb,
            explicit_player_focus=True,
        )
        is True
    )


def test_roster_pressure_keeps_cornerstones_and_allows_depth_to_move():
    cornerstone = player("Cornerstone", 7000, "WR", role="Core", tier="Star", age=24)
    depth = player("Depth", 1400, "WR", role="Bench", tier="Depth", age=27)
    assert trade_ideas._automatic_outgoing_asset_allowed(cornerstone) is False
    assert trade_ideas._automatic_outgoing_asset_allowed(depth) is True


def test_one_qb_does_not_make_replacement_qbs_premium_or_core():
    replacement = player("Replacement QB", 2100, "QB", role="Bench", tier="Depth", age=29)
    elite = player("Elite QB", 6500, "QB", role="Core Starter", tier="Star", age=27)
    assert trade_ideas._is_premium_market_asset(replacement, ONE_QB_DYNASTY) is False
    assert trade_ideas._is_core_or_protected_starter(replacement) is False
    assert trade_ideas._is_core_or_protected_starter(elite) is True


def test_low_pick_cannot_mask_headline_asset_quality_downgrade():
    elite = player("Elite Asset", 6500, "QB", role="Flex", tier="Starter", age=27)
    middling = player("Middling Asset", 4100, "WR", role="Flex", tier="Starter", age=25)
    third = pick("2027 Round 3", 1400, 3)
    market = trade_ideas.evaluate_trade_market_realism(
        send_assets=[elite],
        receive_assets=[middling, third],
        my_shape=neutral_shape(),
        partner_shape=neutral_shape(),
        partner_name="Partner",
        league_settings=ONE_QB_DYNASTY,
    )
    assert market["hard_fail"] is True
    assert "asset_quality_downgrade" in market["hard_fail_flags"]
    assert "low_pick_quality_bridge" in market["hard_fail_flags"]


def test_protected_override_can_never_receive_high_confidence():
    confidence = trade_ideas._trade_confidence_context(
        fit_context={"score": 40, "partner_score": 20},
        market_context={
            "score": 100,
            "value_delta": 1800,
            "flags": ["protected_outgoing_override"],
            "hard_fail": False,
        },
        reasoning_tags=["Need-Based", "Value Arbitrage"],
        reasoning_summary="Exceptional explicit core-asset move.",
    )
    assert confidence["label"] != "High"


def test_third_round_pick_value_stays_low():
    details = trade_ideas._pick_value_components(
        2027,
        3,
        1,
        pd.DataFrame(),
        league_settings=ONE_QB_DYNASTY,
    )
    assert 900 <= details["score"] <= 1800
    assert details["score"] < trade_ideas.BASE_PICK_VALUES[2]


def test_displayed_and_evaluated_player_scores_use_same_field():
    row = pd.Series(
        {
            "name": "Test Player",
            "player_id": "p1",
            "position": "WR",
            "dynasty_score": 5100,
            "value_score": 3900,
            "player_tier": "Starter",
        }
    )
    asset = trade_ideas._player_asset(row, score_field="dynasty_score")
    idea = trade_ideas._make_idea(
        "Partner",
        [asset],
        [pick("2027 Round 3", 1400, 3)],
        "balanced",
        "balanced",
        "Test",
        "Test",
        1,
    )
    assert asset["score_field"] == "dynasty_score"
    assert asset["source_score"] == 5100
    assert asset["score"] == 5100
    assert idea["my_score"] == asset["score"]


def test_shared_headshot_helper_and_authoritative_containment_css():
    helper = source("modules/player_profile_ui.py")
    styles = source("modules/app_styles.py")
    assert "dg-player-headshot" in helper
    assert "dg-player-headshot-image" in helper
    canonical = styles.split("Shared player-headshot containment", 1)[1]
    assert "object-fit: contain !important" in canonical
    assert "object-position: center bottom !important" in canonical
    assert "transform: scale(var(--dg-headshot-scale)) !important" in canonical
    assert "height: 168%" not in styles
    assert "translateX(-50%) scale(1.12)" not in styles


def test_trade_compact_and_quick_view_images_all_use_shared_helper():
    trade_ui = source("modules/trade_hub_ui.py")
    cards = source("modules/player_cards.py")
    app = source("app.py")
    assert "css_class=f\"trade-avatar" in trade_ui
    assert "avatar_html(" in trade_ui
    assert 'avatar_class: str = "compact-player-avatar"' in cards
    assert "avatar_html(" in cards
    assert 'css_class="player-detail-avatar player-quick-view-avatar"' in app



def test_requested_routes_remain_registered_and_renderable_after_narrow_fix():
    from modules.ui_architecture import current_platform_destinations

    app = source("app.py")
    standard = {page.key for page in current_platform_destinations(False, show_experimental=True)}
    startup = {page.key for page in current_platform_destinations(True, show_experimental=True)}
    assert {"dashboard", "my_team", "trade_hub", "waivers", "live_draft", "premium"} <= standard
    assert {"dashboard", "trade_hub", "waivers", "live_draft", "premium"} <= startup
    for route in ("dashboard", "my_team", "trade_hub", "waivers", "live_draft", "premium"):
        assert f'current_page == "{route}"' in app or f'current_page in {{"{route}"' in app
