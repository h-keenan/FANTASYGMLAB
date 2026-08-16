"""Trade Hub featured ranking, diversity, and Free conversion contracts."""

from __future__ import annotations

from pathlib import Path

from modules import premium, trade_hub_ui


ROOT = Path(__file__).resolve().parents[1]


def _idea(**overrides) -> dict:
    idea = {
        "partner_roster_id": "p1",
        "partner_team_name": "Partner A",
        "tag": "Idea",
        "trade_headline_ready": False,
        "trade_surface_tier": "secondary",
        "trade_confidence_label": "Low",
        "market_realism_score": 40,
        "fit_score": 20,
        "partner_fit_score": 2,
        "strategy_fit_score": 10,
        "priority": 10,
        "trade_gain": 1000,
        "send_assets": [{"player_id": "gadsden", "asset_type": "player"}],
        "receive_assets": [{"player_id": "other", "asset_type": "player"}],
    }
    idea.update(overrides)
    return idea


def test_high_confidence_outranks_huge_low_confidence_gain():
    low = _idea(
        tag="Low huge delta",
        trade_gain=1001,
        trade_confidence_label="Low",
        trade_surface_tier="secondary",
        send_assets=[{"player_id": "gadsden", "asset_type": "player"}],
        receive_assets=[{"player_id": "washington", "asset_type": "player"}],
    )
    high = _idea(
        tag="High modest delta",
        trade_gain=120,
        trade_confidence_label="High",
        trade_headline_ready=True,
        trade_surface_tier="primary",
        market_realism_score=80,
        fit_score=70,
        partner_fit_score=8,
        partner_roster_id="p2",
        partner_team_name="Partner B",
        send_assets=[{"player_id": "other-send", "asset_type": "player"}],
        receive_assets=[{"player_id": "other-recv", "asset_type": "player"}],
    )
    ordered = trade_hub_ui.order_trade_hub_visible_ideas([low, high])
    assert [idea["tag"] for idea in ordered[:2]] == ["High modest delta", "Low huge delta"]
    free = trade_hub_ui.trade_hub_entitlement_presentation(
        [low, high],
        [],
        entitlement=premium.FREE,
    )
    assert free["visible_ideas"][0]["tag"] == "High modest delta"
    assert free["visible_count"] == 2


def test_featured_diversity_skips_repeat_centerpiece_when_equal_confidence_exists():
    first = _idea(
        tag="Gadsden A",
        trade_confidence_label="High",
        trade_headline_ready=True,
        trade_surface_tier="primary",
        market_realism_score=80,
        fit_score=70,
        partner_fit_score=8,
        trade_gain=200,
        partner_roster_id="p1",
        send_assets=[{"player_id": "gadsden", "asset_type": "player"}],
        receive_assets=[{"player_id": "dike", "asset_type": "player"}],
    )
    repeat = _idea(
        tag="Gadsden B",
        trade_confidence_label="High",
        trade_headline_ready=True,
        trade_surface_tier="primary",
        market_realism_score=78,
        fit_score=68,
        partner_fit_score=7,
        trade_gain=180,
        partner_roster_id="p2",
        partner_team_name="Partner B",
        send_assets=[{"player_id": "gadsden", "asset_type": "player"}],
        receive_assets=[{"player_id": "washington", "asset_type": "player"}],
    )
    diverse = _idea(
        tag="Different send",
        trade_confidence_label="High",
        trade_headline_ready=True,
        trade_surface_tier="primary",
        market_realism_score=76,
        fit_score=66,
        partner_fit_score=6,
        trade_gain=90,
        partner_roster_id="p3",
        partner_team_name="Partner C",
        send_assets=[{"player_id": "bowers", "asset_type": "player"}],
        receive_assets=[{"player_id": "pick", "asset_type": "pick"}],
    )
    ordered = trade_hub_ui.order_trade_hub_visible_ideas([repeat, diverse, first])
    assert [idea["tag"] for idea in ordered[:2]] == ["Gadsden A", "Different send"]
    assert ordered[2]["tag"] == "Gadsden B"


def test_featured_diversity_skips_repeat_partner_when_equal_confidence_exists():
    first = _idea(
        tag="Partner A first",
        trade_confidence_label="High",
        trade_headline_ready=True,
        trade_surface_tier="primary",
        market_realism_score=80,
        fit_score=70,
        partner_fit_score=8,
        partner_roster_id="same-manager",
        send_assets=[{"player_id": "alpha", "asset_type": "player"}],
    )
    repeat_partner = _idea(
        tag="Partner A again",
        trade_confidence_label="High",
        trade_headline_ready=True,
        trade_surface_tier="primary",
        market_realism_score=78,
        fit_score=68,
        partner_fit_score=7,
        partner_roster_id="same-manager",
        send_assets=[{"player_id": "beta", "asset_type": "player"}],
    )
    other_partner = _idea(
        tag="Partner B",
        trade_confidence_label="High",
        trade_headline_ready=True,
        trade_surface_tier="primary",
        market_realism_score=76,
        fit_score=66,
        partner_fit_score=6,
        partner_roster_id="other-manager",
        partner_team_name="Partner C",
        send_assets=[{"player_id": "gamma", "asset_type": "player"}],
    )
    ordered = trade_hub_ui.order_trade_hub_visible_ideas(
        [first, repeat_partner, other_partner]
    )
    assert [idea["tag"] for idea in ordered[:2]] == ["Partner A first", "Partner B"]
    assert ordered[2]["tag"] == "Partner A again"


def test_diversity_does_not_replace_medium_with_low():
    lead = _idea(
        tag="Lead",
        trade_confidence_label="High",
        trade_headline_ready=True,
        trade_surface_tier="primary",
        market_realism_score=80,
        fit_score=70,
        partner_fit_score=8,
        send_assets=[{"player_id": "gadsden", "asset_type": "player"}],
    )
    same_player_medium = _idea(
        tag="Same player medium",
        trade_confidence_label="Medium",
        trade_surface_tier="primary",
        market_realism_score=70,
        fit_score=50,
        partner_fit_score=5,
        trade_gain=400,
        partner_roster_id="p2",
        partner_team_name="Partner B",
        send_assets=[{"player_id": "gadsden", "asset_type": "player"}],
    )
    other_low = _idea(
        tag="Other low",
        trade_confidence_label="Low",
        trade_surface_tier="secondary",
        trade_gain=50,
        partner_roster_id="p3",
        partner_team_name="Partner C",
        send_assets=[{"player_id": "bowers", "asset_type": "player"}],
    )
    ordered = trade_hub_ui.order_trade_hub_visible_ideas(
        [lead, same_player_medium, other_low]
    )
    assert [idea["tag"] for idea in ordered[:2]] == ["Lead", "Same player medium"]


def test_only_low_confidence_pool_is_honest_and_still_shows_ideas():
    pool = [
        _idea(tag=f"Low {index}", partner_roster_id=str(index), trade_gain=100 * index)
        for index in range(4)
    ]
    presentation = trade_hub_ui.trade_hub_entitlement_presentation(
        pool,
        [],
        entitlement=premium.FREE,
    )
    assert presentation["visible_count"] == 2
    assert presentation["hidden_count"] == 2
    assert presentation["only_low_confidence"] is True
    assert presentation["show_board_upgrade"] is True
    summary = trade_hub_ui.trade_hub_entitlement_summary(presentation, section_count=1)
    assert "confidence is limited on this board" in summary
    assert all(
        idea["trade_confidence_label"] == "Low" for idea in presentation["visible_ideas"]
    )


def test_zero_one_two_and_many_free_matrix():
    for count in (0, 1, 2, 8):
        pool = [_idea(tag=str(index), partner_roster_id=str(index)) for index in range(count)]
        free = trade_hub_ui.trade_hub_entitlement_presentation(
            pool, [], entitlement=premium.FREE
        )
        paid = trade_hub_ui.trade_hub_entitlement_presentation(
            pool, [], entitlement=premium.PREMIUM
        )
        assert len(paid["visible_ideas"]) == count
        assert paid["hidden_count"] == 0
        assert paid["show_board_upgrade"] is False
        assert len(free["visible_ideas"]) == min(count, 2)
        assert free["hidden_count"] == max(0, count - 2)
        assert free["show_board_upgrade"] is (count > 2)


def test_premium_keeps_repeat_ideas_after_featured_window():
    repeats = [
        _idea(
            tag=f"Repeat {index}",
            trade_confidence_label="High",
            trade_headline_ready=True,
            trade_surface_tier="primary",
            market_realism_score=80 - index,
            fit_score=70,
            partner_fit_score=8,
            partner_roster_id=str(index),
            send_assets=[{"player_id": "gadsden", "asset_type": "player"}],
        )
        for index in range(3)
    ]
    diverse = _idea(
        tag="Other",
        trade_confidence_label="High",
        trade_headline_ready=True,
        trade_surface_tier="primary",
        market_realism_score=70,
        fit_score=60,
        partner_fit_score=6,
        partner_roster_id="x",
        send_assets=[{"player_id": "bowers", "asset_type": "player"}],
    )
    paid = trade_hub_ui.trade_hub_entitlement_presentation(
        repeats + [diverse],
        [],
        entitlement=premium.PREMIUM,
    )
    assert len(paid["visible_ideas"]) == 4
    tags = [idea["tag"] for idea in paid["visible_ideas"]]
    assert tags[0].startswith("Repeat")
    assert "Other" in tags[:2]
    assert sum(tag.startswith("Repeat") for tag in tags) == 3


def test_locked_preview_does_not_leak_recommendation_data():
    html = trade_hub_ui.trade_hub_locked_preview_html(6)
    assert "6 more ideas behind Premium" in html
    assert "gadsden" not in html.casefold()
    assert "trade-hub-locked-row" in html
    assert trade_hub_ui.trade_hub_locked_preview_html(0) == ""


def test_free_gate_copy_matches_implemented_premium_depth():
    assert "Search Around" not in trade_hub_ui.TRADE_HUB_FREE_GATE_BODY
    assert "GM Targets" not in trade_hub_ui.TRADE_HUB_FREE_GATE_BODY
    assert "ranked board" in trade_hub_ui.TRADE_HUB_FREE_GATE_BODY
    assert "partners and packages" in trade_hub_ui.TRADE_HUB_FREE_GATE_BODY
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    board = source[
        source.index("def render_top_trade_opportunities()") : source.index(
            "def render_search_around_player()"
        )
    ]
    assert "render_trade_hub_free_gate(" in board
    assert board.index("render_trade_hub_free_gate(") < board.index(
        "render_soft_signup_prompt("
    )
    assert "TRADE_HUB_FREE_GATE_CTA" in board
    assert "st.rerun(" not in board


def test_low_confidence_note_is_on_cards_and_kept_on_mobile():
    source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    assert "trade-summary-confidence-note" in source
    assert "LOW_CONFIDENCE_USER_NOTE" in source
    assert "More dependent on partner preference and market fit." in source
    mobile = source.split("@media (max-width: 430px)", 1)[1].split("@media", 1)[0]
    assert "trade-summary-confidence-note" in mobile
    assert "display: none" not in mobile.split("trade-summary-confidence-note", 1)[1][:180]


def test_strategy_selector_compacts_auto_help_beside_control():
    source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    selector = source.split("def render_trade_strategy_selector", 1)[1].split(
        "\ndef ", 1
    )[0]
    assert "st.columns([4, 1]" in selector
    assert "render_auto_strategy_help" in selector


def test_expired_pick_boundary_is_documented_as_upstream():
    source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    contract = source[
        source.index("def trade_hub_entitlement_presentation(") : source.index(
            "def trade_hub_entitlement_summary("
        )
    ]
    assert "Temporal pick eligibility is owned upstream" in contract
    assert "invalid" in contract.casefold()
