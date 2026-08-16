from __future__ import annotations

from pathlib import Path

from modules import premium
from modules import trade_hub_ui


def _ideas(count: int, *, tier: str = "primary") -> list[dict]:
    return [
        {
            "idea_id": f"{tier}-{index}",
            "trade_surface_tier": tier,
        }
        for index in range(count)
    ]


def test_premium_receives_every_approved_idea_in_original_order():
    primary = _ideas(5)
    secondary = _ideas(5, tier="secondary")

    presentation = trade_hub_ui.trade_hub_entitlement_presentation(
        primary,
        secondary,
        entitlement=premium.PREMIUM,
    )

    assert presentation["visible_ideas"] == primary + secondary
    assert presentation["approved_count"] == 10
    assert presentation["hidden_count"] == 0
    assert presentation["show_board_upgrade"] is False


def test_free_preview_is_two_primary_ideas_and_hides_remaining_approved_board():
    primary = _ideas(5)
    secondary = _ideas(5, tier="secondary")

    presentation = trade_hub_ui.trade_hub_entitlement_presentation(
        primary,
        secondary,
        entitlement=premium.FREE,
    )

    assert presentation["visible_ideas"] == primary[:2]
    assert presentation["approved_count"] == 10
    assert presentation["hidden_count"] == 8
    assert presentation["show_board_upgrade"] is True


def test_entitlement_matrix_for_zero_one_two_five_and_ten_approved_ideas():
    for count in (0, 1, 2, 5, 10):
        primary = _ideas(count)
        premium_state = trade_hub_ui.trade_hub_entitlement_presentation(
            primary,
            [],
            entitlement=premium.PREMIUM,
        )
        free_state = trade_hub_ui.trade_hub_entitlement_presentation(
            primary,
            [],
            entitlement=premium.FREE,
        )

        assert len(premium_state["visible_ideas"]) == count
        assert premium_state["hidden_count"] == 0
        assert premium_state["show_board_upgrade"] is False
        assert len(free_state["visible_ideas"]) == min(count, 2)
        assert free_state["hidden_count"] == max(0, count - 2)
        assert free_state["show_board_upgrade"] is (count > 2)


def test_no_upgrade_claim_when_trust_leaves_only_one_approved_idea():
    # The presentation boundary receives post-Trust recommendations. Raw ideas
    # rejected by Trust must never be described as entitlement-hidden.
    approved_after_trust = _ideas(1)

    presentation = trade_hub_ui.trade_hub_entitlement_presentation(
        approved_after_trust,
        [],
        entitlement=premium.FREE,
    )

    assert presentation["approved_count"] == 1
    assert presentation["hidden_count"] == 0
    assert presentation["show_board_upgrade"] is False


def test_missing_failed_and_malformed_entitlements_degrade_to_free_preview():
    for entitlement in (None, "", "unknown", True, False):
        presentation = trade_hub_ui.trade_hub_entitlement_presentation(
            _ideas(5),
            [],
            entitlement=entitlement,
        )

        assert presentation["is_premium"] is False
        assert len(presentation["visible_ideas"]) == 2
        assert presentation["show_board_upgrade"] is True


def test_premium_one_card_regression_explains_grouping_not_entitlement_gating():
    ideas = [
        {
            **_ideas(1)[0],
            "partner_roster_id": "fixture-roster",
            "my_player": "fixture-send",
            "their_player": "fixture-receive",
            "my_score": 100,
            "their_score": 105,
            "trade_confidence_label": "High",
            "market_realism_label": "Plausible",
            "trade_headline_ready": True,
            "tag": "Headline",
        },
        {
            **_ideas(1)[0],
            "idea_id": "primary-1",
            "partner_roster_id": "fixture-roster-2",
            "my_player": "fixture-send-2",
            "their_player": "fixture-receive-2",
            "my_score": 100,
            "their_score": 104,
            "trade_confidence_label": "Medium",
            "market_realism_label": "Plausible",
            "tag": "Rebuild value path",
        },
    ]
    presentation = trade_hub_ui.trade_hub_entitlement_presentation(
        ideas,
        [],
        entitlement=premium.PREMIUM,
    )
    grouped = trade_hub_ui.group_trade_hub_ideas(
        presentation["visible_ideas"],
        headline_idea=ideas[0],
    )

    assert len(grouped["Headline Recommendation"]) == 1
    assert sum(map(len, grouped.values())) == 2
    assert presentation["hidden_count"] == 0
    summary = trade_hub_ui.trade_hub_entitlement_summary(
        presentation,
        section_count=len(grouped),
    )
    assert "2 trade ideas in one ranked feed" in summary
    assert "2 categories" in summary


def test_premium_receives_secondary_heavy_board_and_free_can_feature_the_next_ranked_idea():
    """1 primary + N secondary: Free still shows the top two ranked ideas."""

    primary = _ideas(1)
    secondary = _ideas(4, tier="secondary")
    free_state = trade_hub_ui.trade_hub_entitlement_presentation(
        primary,
        secondary,
        entitlement=premium.FREE,
    )
    premium_state = trade_hub_ui.trade_hub_entitlement_presentation(
        primary,
        secondary,
        entitlement="Premium",  # casing must not free-gate
    )

    assert len(free_state["visible_ideas"]) == 2
    assert free_state["hidden_count"] == 3
    assert len(premium_state["visible_ideas"]) == 5
    assert premium_state["hidden_count"] == 0
    assert premium_state["is_premium"] is True


def test_category_badge_falls_back_to_display_section_without_annotation():
    idea = {
        "partner_roster_id": "p1",
        "tag": "Get Younger + Pick",
        "trade_confidence_label": "Medium",
        "market_realism_label": "Plausible",
        "my_score": 100,
        "their_score": 110,
        "trade_gain": 10,
        "send_assets": [],
        "receive_assets": [],
    }
    section = trade_hub_ui.trade_hub_display_section(idea)
    assert section == "Age Optimization"
    source = (Path(__file__).resolve().parents[1] / "modules" / "trade_hub_ui.py").read_text(
        encoding="utf-8"
    )
    assert "or trade_hub_display_section(idea)" in source
    assert '_safe_text(idea.get("_display_section"), "Trade Board")' not in source


def test_section_filter_helper_is_removed():
    source = (Path(__file__).resolve().parents[1] / "modules" / "trade_hub_ui.py").read_text(
        encoding="utf-8"
    )
    assert "def render_trade_hub_section_filter(" not in source
    assert "st.pills(" not in source


def test_free_summary_and_upgrade_contract_are_mobile_safe_plain_text():
    presentation = trade_hub_ui.trade_hub_entitlement_presentation(
        _ideas(5),
        [],
        entitlement=premium.FREE,
    )
    summary = trade_hub_ui.trade_hub_entitlement_summary(
        presentation,
        section_count=2,
    )

    assert summary == (
        "2 of 5 trade ideas. You're seeing the top recommendations."
    )
    assert "<" not in summary
    assert "\n" not in summary


def test_cached_and_uncached_approved_lists_have_identical_presentation():
    uncached = _ideas(5)
    cached = [dict(idea) for idea in uncached]

    assert trade_hub_ui.trade_hub_entitlement_presentation(
        uncached,
        [],
        entitlement=premium.PREMIUM,
    ) == trade_hub_ui.trade_hub_entitlement_presentation(
        cached,
        [],
        entitlement=premium.PREMIUM,
    )


def test_production_boundary_is_post_trust_pre_grouping_and_has_one_board_lock():
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("def render_top_trade_opportunities()")
    end = source.index("def render_search_around_player()", start)
    block = source[start:end]

    trust = block.index("ideas = enforce_cached_trade_ideas(")
    presentation = block.index("trade_hub_ui.trade_hub_entitlement_presentation(")
    grouping = block.index("trade_hub_ui.group_trade_hub_ideas(")
    rendering = block.index("ranked_feed[:local_visible]")

    assert trust < presentation < grouping < rendering
    assert block.count("TRADE_HUB_FREE_GATE_TITLE") == 1
    assert 'if trade_hub_presentation["show_board_upgrade"]:' in block
    assert "render_trade_hub_free_gate(" in block
    assert '"Secondary and thin-market ideas"' not in block
    assert '"Player return search"' not in block
    assert "def _trade_hub_visible_feed()" in block
