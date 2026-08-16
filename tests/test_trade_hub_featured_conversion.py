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
    assert "league_format_context" in contract
    assert "must not recreate those rules" in contract
    assert "reintroduce" in contract
    assert "pick_is_actionable_capital" not in source
    assert "list_draft_pick_assets" not in source


def _identity(idea: dict) -> tuple:
    return (
        idea.get("tag"),
        idea.get("partner_roster_id"),
        tuple(
            (asset.get("asset_type"), asset.get("player_id"), asset.get("season"))
            for asset in (idea.get("send_assets") or []) + (idea.get("receive_assets") or [])
        ),
    )


def test_presentation_is_a_permutation_and_cannot_reintroduce_filtered_ideas():
    valid = [
        _idea(
            tag="Keep A",
            trade_confidence_label="High",
            trade_headline_ready=True,
            trade_surface_tier="primary",
            partner_roster_id="1",
            send_assets=[{"player_id": "alpha", "asset_type": "player"}],
            receive_assets=[{"player_id": "beta", "asset_type": "player"}],
        ),
        _idea(
            tag="Keep B",
            trade_confidence_label="Medium",
            trade_surface_tier="primary",
            partner_roster_id="2",
            send_assets=[{"player_id": "gamma", "asset_type": "player"}],
            receive_assets=[
                {"asset_type": "pick", "season": 2026, "player_id": "2026-1", "name": "2026 1st"}
            ],
        ),
    ]
    removed_expired = _idea(
        tag="Expired 2025",
        trade_gain=5000,
        trade_confidence_label="High",
        trade_headline_ready=True,
        trade_surface_tier="primary",
        partner_roster_id="3",
        send_assets=[{"player_id": "alpha", "asset_type": "player"}],
        receive_assets=[
            {"asset_type": "pick", "season": 2025, "player_id": "2025-1", "name": "2025 1st"}
        ],
    )
    # Upstream eligibility already dropped the expired idea before presentation.
    ordered = trade_hub_ui.order_trade_hub_visible_ideas(valid)
    assert {_identity(idea) for idea in ordered} == {_identity(idea) for idea in valid}
    assert all(idea["tag"] != "Expired 2025" for idea in ordered)
    free = trade_hub_ui.trade_hub_entitlement_presentation(
        valid, [], entitlement=premium.FREE
    )
    assert all(idea is not removed_expired for idea in free["visible_ideas"])
    assert "2025" not in repr(free["visible_ideas"])


def test_free_gate_is_silent_for_zero_one_and_two_valid_ideas():
    for count in (0, 1, 2):
        pool = [
            _idea(tag=str(index), partner_roster_id=str(index), trade_gain=index)
            for index in range(count)
        ]
        free = trade_hub_ui.trade_hub_entitlement_presentation(
            pool, [], entitlement=premium.FREE
        )
        assert free["visible_count"] == count
        assert free["hidden_count"] == 0
        assert free["show_board_upgrade"] is False
        assert trade_hub_ui.trade_hub_locked_preview_html(free["hidden_count"]) == ""
    three = [
        _idea(tag=str(index), partner_roster_id=str(index), trade_gain=index)
        for index in range(3)
    ]
    gated = trade_hub_ui.trade_hub_entitlement_presentation(
        three, [], entitlement=premium.FREE
    )
    assert gated["visible_count"] == 2
    assert gated["hidden_count"] == 1
    assert gated["show_board_upgrade"] is True
    assert "1 more idea behind Premium" in trade_hub_ui.trade_hub_locked_preview_html(1)


def test_ranking_is_format_agnostic_and_preserves_valid_pick_seasons():
    def pool(season: int) -> list[dict]:
        return [
            _idea(
                tag="High",
                trade_confidence_label="High",
                trade_headline_ready=True,
                trade_surface_tier="primary",
                market_realism_score=80,
                fit_score=70,
                partner_fit_score=8,
                partner_roster_id="p-high",
                send_assets=[{"player_id": "send-a", "asset_type": "player"}],
                receive_assets=[
                    {
                        "asset_type": "pick",
                        "season": season,
                        "player_id": f"{season}-1",
                        "name": f"{season} 1st",
                    }
                ],
            ),
            _idea(
                tag="Low",
                trade_confidence_label="Low",
                trade_gain=4000,
                partner_roster_id="p-low",
                send_assets=[{"player_id": "send-b", "asset_type": "player"}],
                receive_assets=[{"player_id": "recv-b", "asset_type": "player"}],
            ),
        ]

    for season, _format in ((2026, "Redraft"), (2027, "Keeper"), (2028, "Dynasty")):
        ordered = trade_hub_ui.order_trade_hub_visible_ideas(pool(season))
        assert [idea["tag"] for idea in ordered] == ["High", "Low"]
        pick = (ordered[0]["receive_assets"] or [])[0]
        assert pick["season"] == season
        assert pick["name"].startswith(str(season))


def test_first_session_loading_still_precedes_featured_ranking():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    hub = source[
        source.index('if current_page == "trade_hub"') : source.index("# TRADE ANALYZER")
    ]
    assert hub.index("trade_hub_pending") < hub.index("surface_pending_html(")
    assert hub.index("trade_hub_pending.empty()") < hub.index(
        "order_trade_hub_visible_ideas("
    )
    assert "LOADING_TRADE_IDEAS" in hub
    assert "bind_inspect_player(" in source


def test_dynasty_fixture_approved_pool_has_no_calendar_expired_picks():
    from scripts.profile_trade_hub import FixtureSpec, build_fixture, run_trade_hub

    approved = run_trade_hub(
        build_fixture(
            FixtureSpec("12-team-superflex-primary", 12, 28, "Superflex", te_premium=True)
        )
    )["approved"]
    as_of_year = 2026
    seasons = []
    for idea in approved:
        for asset in (idea.get("send_assets") or []) + (idea.get("receive_assets") or []):
            if str(asset.get("asset_type") or "").casefold() != "pick":
                continue
            season = int(asset.get("season") or 0)
            seasons.append(season)
            assert season >= as_of_year, asset
    ranked = trade_hub_ui.order_trade_hub_visible_ideas(approved)
    free = trade_hub_ui.trade_hub_entitlement_presentation(
        ranked, [], entitlement=premium.FREE
    )
    assert {_identity(idea) for idea in ranked} == {_identity(idea) for idea in approved}
    assert len(free["visible_ideas"]) == min(2, len(approved))
    if len(approved) <= 2:
        assert free["show_board_upgrade"] is False
    else:
        assert free["show_board_upgrade"] is True
        assert free["hidden_count"] == len(approved) - 2
