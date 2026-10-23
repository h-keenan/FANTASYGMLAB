"""Player Quick View final UX: share owner, feedback, production hierarchy."""

from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from modules import canonical_recommendation_narrative as crn
from modules import player_quick_view
from modules import share_recommendation_cards as share


ROOT = Path(__file__).resolve().parents[1]


def _narrative(*, action: str, player_id: str = "p1", **overrides):
    values = {
        "recommendation_id": f"rec-{action.casefold()}-{player_id}",
        "kind": "player_action",
        "action": action,
        "target_label": "Fixture Player",
        "reason": f"{action} because the current role still supports the valuation.",
        "evidence": "Featured usage with stable PPR production.",
        "risk": "",
        "expected_outcome": "",
        "confidence_label": "High",
        "confidence_wording": "High confidence",
        "market_signal": "",
        "fit_signal": "",
        "league_id": "league-a",
        "roster_id": "1",
        "valuation_lens": "dynasty_score",
        "source_surface": "player_quick_view",
        "player_ids": (player_id,),
        "is_active_recommendation": True,
    }
    values.update(overrides)
    return crn.CanonicalRecommendationNarrative(**values)


def test_pqv_owned_narrative_survives_lens_mismatch_and_is_shareable():
    narrative = _narrative(action="HOLD")
    state = {}
    crn.bind_narrative(state, narrative)
    crn.bind_pqv_owned_narrative(state, narrative, player_id="p1")
    visible = crn.visible_recommendation_for_player(
        state,
        player_id="p1",
        league_id="league-a",
    )
    assert visible is not None
    assert visible.action == "HOLD"
    # Strict registry would drop this on a different page lens.
    assert (
        crn.resolve_narrative_for_player(
            state,
            player_id="p1",
            league_id="league-a",
            valuation_lens="value_score",
        )
        is None
    )
    card = share.build_player_share_card(
        display_name="Fixture Player",
        player_id="p1",
        narrative=visible,
    )
    assert card.is_shareable is True
    assert card.action == "HOLD"


def test_visible_recommendation_actions_are_shareable():
    for action in ("ADD", "HOLD", "BUY", "TARGET", "SELL", "DROP"):
        narrative = _narrative(action=action)
        card = share.build_player_share_card(
            display_name="Fixture Player",
            player_id="p1",
            narrative=narrative,
        )
        assert card.is_shareable, action
        assert card.action == action


def test_waiver_and_rostered_and_sparse_share_contracts():
    waiver = crn.build_waiver_narrative(
        {"player_id": "w1", "name": "Waiver Add", "position": "WR", "team": "CHI"},
        action="Add",
        reason="Immediate depth for an injured starter.",
        league_id="league-a",
        roster_id="1",
        valuation_lens="dynasty_score",
        source_surface="waivers",
    )
    waiver_card = share.build_player_share_card(
        display_name="Waiver Add",
        player_id="w1",
        narrative=waiver,
    )
    assert waiver_card.is_shareable
    assert waiver_card.action == "Add"

    rostered = _narrative(action="HOLD", player_id="r1")
    rostered_card = share.build_player_share_card(
        display_name="Rostered",
        player_id="r1",
        narrative=rostered,
    )
    assert rostered_card.is_shareable

    sparse = _narrative(
        action="HOLD",
        player_id="s1",
        evidence="",
        confidence_label="",
        reason="Limited evidence, but the current roster read is Hold.",
    )
    sparse_card = share.build_player_share_card(
        display_name="Sparse",
        player_id="s1",
        narrative=sparse,
    )
    assert sparse_card.is_shareable
    assert sparse_card.action == "HOLD"
