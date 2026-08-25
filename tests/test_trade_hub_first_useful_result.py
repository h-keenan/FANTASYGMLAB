"""Contracts for Trade Hub first-useful-result performance (PR #154)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import session_integrity
from modules import trade_hub_first_useful
from modules import trade_hub_ui


ROOT = Path(__file__).resolve().parents[1]


def _sample_ideas():
    return [
        {
            "partner_roster_id": "2",
            "partner_team_name": "Partner A",
            "tag": "Need Path",
            "my_score": 8000,
            "their_score": 8100,
            "trade_gain": 100,
            "fit_score": 80,
            "partner_fit_score": 70,
            "strategy_fit_score": 60,
            "market_realism_score": 75,
            "trade_confidence_label": "High",
            "trade_headline_ready": True,
            "trade_surface_tier": "primary",
            "priority": 1,
            "send_assets": [{"asset_type": "player", "player_id": "1", "name": "A"}],
            "receive_assets": [{"asset_type": "player", "player_id": "2", "name": "B"}],
        },
        {
            "partner_roster_id": "3",
            "partner_team_name": "Partner B",
            "tag": "Depth Path",
            "my_score": 7000,
            "their_score": 7200,
            "trade_gain": 50,
            "fit_score": 50,
            "partner_fit_score": 40,
            "strategy_fit_score": 30,
            "market_realism_score": 55,
            "trade_confidence_label": "Medium",
            "trade_headline_ready": False,
            "trade_surface_tier": "secondary",
            "priority": 2,
            "send_assets": [{"asset_type": "player", "player_id": "3", "name": "C"}],
            "receive_assets": [{"asset_type": "player", "player_id": "4", "name": "D"}],
        },
    ]


def test_presentation_board_cache_hit_miss_and_mutation_isolation():
    state: dict = {}
    builds = {"n": 0}
    ideas = _sample_ideas()

    def builder():
        builds["n"] += 1
        ordered = trade_hub_ui.order_trade_hub_visible_ideas(ideas)
        return {
            "eligible_ideas": ordered,
            "presentation": {"is_premium": True, "visible_count": len(ordered)},
            "ranked_feed": ordered,
            "headline_idea": ordered[0],
            "board_inventory": {"section_count": 1, "accessible_count": len(ordered)},
            "equivalence_fingerprint": trade_hub_first_useful.idea_equivalence_fingerprint(
                ordered
            ),
        }

    signature = trade_hub_first_useful.build_presentation_board_signature(
        lifecycle_digest="abc",
        league_id="L1",
        roster_id="1",
        scoring_format="PPR",
        valuation_lens="dynasty_score",
        strategy="contender",
        entitlement="premium",
        frame_signature="frame",
        untouchables=("X",),
        role_items=(("1", "Core"),),
    )
    first, hit1 = trade_hub_first_useful.get_or_build_presentation_board(
        state, signature=signature, builder=builder
    )
    second, hit2 = trade_hub_first_useful.get_or_build_presentation_board(
        state, signature=signature, builder=builder
    )
    assert hit1 is False and hit2 is True
    assert builds["n"] == 1
    assert first["equivalence_fingerprint"] == second["equivalence_fingerprint"]
    second["eligible_ideas"][0]["my_score"] = 1
    third, hit3 = trade_hub_first_useful.get_or_build_presentation_board(
        state, signature=signature, builder=builder
    )
    assert hit3 is True
    assert int(third["eligible_ideas"][0]["my_score"]) == 8000


def test_presentation_board_process_cache_reuses_across_sessions():
    trade_hub_first_useful.clear_process_presentation_boards()
    builds = {"n": 0}

    def builder():
        builds["n"] += 1
        return {
            "eligible_ideas": _sample_ideas(),
            "equivalence_fingerprint": "fp",
        }

    signature = trade_hub_first_useful.build_presentation_board_signature(
        lifecycle_digest="proc",
        league_id="L9",
        roster_id="9",
        scoring_format="PPR",
        valuation_lens="dynasty_score",
        strategy="contender",
        entitlement="premium",
        frame_signature="frame-proc",
    )
    first, hit1 = trade_hub_first_useful.get_or_build_presentation_board(
        {}, signature=signature, builder=builder
    )
    second, hit2 = trade_hub_first_useful.get_or_build_presentation_board(
        {}, signature=signature, builder=builder
    )
    assert hit1 is False and hit2 is True
    assert builds["n"] == 1
    assert first["equivalence_fingerprint"] == second["equivalence_fingerprint"]
    trade_hub_first_useful.clear_process_presentation_boards()


def test_presentation_board_signature_fails_closed_on_material_dims():
    base = dict(
        lifecycle_digest="abc",
        league_id="L1",
        roster_id="1",
        scoring_format="PPR",
        valuation_lens="dynasty_score",
        strategy="contender",
        entitlement="free",
        frame_signature="frame",
    )
    a = trade_hub_first_useful.build_presentation_board_signature(**base)
    b = trade_hub_first_useful.build_presentation_board_signature(
        **{**base, "entitlement": "premium"}
    )
    c = trade_hub_first_useful.build_presentation_board_signature(
        **{**base, "strategy": "rebuild"}
    )
    d = trade_hub_first_useful.build_presentation_board_signature(
        **{**base, "scoring_format": "Half-PPR"}
    )
    assert a != b
    assert a != c
    assert a != d
    assert b != c and b != d and c != d
    assert len({a, b, c, d}) == 4


def test_presentation_only_visible_count_not_in_signature():
    """Opening Show more / PQV must not invalidate football board caches."""

    sig = trade_hub_first_useful.build_presentation_board_signature(
        lifecycle_digest="abc",
        league_id="L1",
        roster_id="1",
        strategy="contender",
        entitlement="premium",
    )
    # No visible_count / overlay args exist — contract is exclusion by absence.
    assert "visible" not in sig


def test_strategy_frame_memo_reuses_and_isolates():
    state: dict = {}
    builds = {"n": 0}

    def builder():
        builds["n"] += 1
        return pd.DataFrame({"player_id": ["1"], "dynasty_score": [100]})

    signature = trade_hub_first_useful.build_strategy_frame_signature(
        frame_signature="f",
        strategy="contender",
        score_field="dynasty_score",
    )
    first, hit1 = trade_hub_first_useful.get_or_build_strategy_frame(
        state, signature=signature, builder=builder
    )
    second, hit2 = trade_hub_first_useful.get_or_build_strategy_frame(
        state, signature=signature, builder=builder
    )
    assert hit1 is False and hit2 is True and builds["n"] == 1
    second.loc[0, "dynasty_score"] = 1
    third, _ = trade_hub_first_useful.get_or_build_strategy_frame(
        state, signature=signature, builder=builder
    )
    assert int(third.loc[0, "dynasty_score"]) == 100


def test_account_clear_drops_trade_hub_computation_caches():
    state = {
        trade_hub_first_useful.PRESENTATION_CACHE_KEY: {"k": {}},
        trade_hub_first_useful.STRATEGY_FRAME_CACHE_KEY: {"k": pd.DataFrame()},
    }
    session_integrity.clear_account_bound_transient_state(state)
    assert trade_hub_first_useful.PRESENTATION_CACHE_KEY not in state
    assert trade_hub_first_useful.STRATEGY_FRAME_CACHE_KEY not in state


def test_cache_hit_and_miss_equivalence_fingerprints_match():
    state: dict = {}
    ideas = _sample_ideas()
    ordered = trade_hub_ui.order_trade_hub_visible_ideas(ideas)
    fingerprint = trade_hub_first_useful.idea_equivalence_fingerprint(ordered)

    def builder():
        return {
            "eligible_ideas": ordered,
            "equivalence_fingerprint": fingerprint,
            "ranked_feed": ordered,
            "presentation": {"visible_count": len(ordered)},
            "headline_idea": ordered[0],
            "board_inventory": {"accessible_count": len(ordered), "section_count": 1},
        }

    signature = "sig"
    miss, _ = trade_hub_first_useful.get_or_build_presentation_board(
        state, signature=signature, builder=builder
    )
    hit, _ = trade_hub_first_useful.get_or_build_presentation_board(
        state, signature=signature, builder=builder
    )
    assert miss["equivalence_fingerprint"] == hit["equivalence_fingerprint"] == fingerprint
    assert trade_hub_first_useful.recommendation_one_identity(
        miss["eligible_ideas"]
    ) == trade_hub_first_useful.recommendation_one_identity(hit["eligible_ideas"])


def test_recommendation_one_requires_full_board_contract_documented():
    """#1 is presentation-first of the complete approved set — no early provisional #1."""

    source = (ROOT / "modules" / "trade_hub_first_useful.py").read_text(encoding="utf-8")
    assert "complete approved candidate set must be known" in source
    assert "does not invent provisional early-result semantics" in source
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    hub = app[
        app.index('if current_page == "trade_hub"') : app.index("# TRADE ANALYZER")
    ]
    assert "get_or_build_presentation_board(" in hub
    assert "order_trade_hub_visible_ideas(" in hub
    assert "include_intelligence=False" in hub
    assert "trade_hub_rec1_ready" in hub


def test_no_football_logic_modules_modified_for_this_pr():
    """Trade Hub first-useful presentation must not touch Trust engines.

    Valuation calibration audits may intentionally edit rankings / trade_ideas.
    """
    diff_names = {
        line.strip()
        for line in __import__("subprocess")
        .run(
            ["git", "diff", "--name-only", "main"],
            capture_output=True,
            text=True,
            check=False,
        )
        .stdout.splitlines()
        if line.strip()
    }
    forbidden = {
        "modules/trust_engine.py",
        "modules/trust_enforcement.py",
    }
    assert not diff_names.intersection(forbidden)


def test_free_premium_entitlement_signatures_isolated():
    free = trade_hub_first_useful.build_presentation_board_signature(
        league_id="L1", roster_id="1", entitlement="free", strategy="contender"
    )
    premium = trade_hub_first_useful.build_presentation_board_signature(
        league_id="L1", roster_id="1", entitlement="premium", strategy="contender"
    )
    assert free != premium
