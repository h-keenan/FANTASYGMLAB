"""Trade Hub featured ranking, diversity, and Free conversion contracts."""

from __future__ import annotations

from pathlib import Path

from modules import premium, trade_hub_presentation


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
    ordered = trade_hub_presentation.order_trade_hub_visible_ideas([repeat, diverse, first])
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
    ordered = trade_hub_presentation.order_trade_hub_visible_ideas(
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
    ordered = trade_hub_presentation.order_trade_hub_visible_ideas(
        [lead, same_player_medium, other_low]
    )
    assert [idea["tag"] for idea in ordered[:2]] == ["Lead", "Same player medium"]


def _identity(idea: dict) -> tuple:
    return (
        idea.get("tag"),
        idea.get("partner_roster_id"),
        tuple(
            (asset.get("asset_type"), asset.get("player_id"), asset.get("season"))
            for asset in (idea.get("send_assets") or []) + (idea.get("receive_assets") or [])
        ),
    )


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
        ordered = trade_hub_presentation.order_trade_hub_visible_ideas(pool(season))
        assert [idea["tag"] for idea in ordered] == ["High", "Low"]
        pick = (ordered[0]["receive_assets"] or [])[0]
        assert pick["season"] == season
        assert pick["name"].startswith(str(season))
