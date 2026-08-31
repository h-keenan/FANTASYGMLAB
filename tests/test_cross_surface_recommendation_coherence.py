"""Cross-surface primary-action coherence for Founder Beta trust.

UI wording may differ; Shop / Hold / Drop / Protect / neutral semantics must agree.
"""

from __future__ import annotations

from modules import canonical_recommendation_narrative as crn
from modules import player_quick_view
from modules import roster_primary_actions as rpa


def _candidate(
    player_id: str,
    name: str,
    *,
    bucket: str,
    reason: str,
    source: str = "roster",
    young_upside_flag: bool = False,
    protected_low_value_flag: bool = False,
    player_tier: str = "",
) -> dict:
    return {
        "player_id": player_id,
        "player_name": name,
        "name": name,
        "bucket": bucket,
        "reason": reason,
        "note": reason,
        "source": source,
        "young_upside_flag": young_upside_flag,
        "protected_low_value_flag": protected_low_value_flag,
        "player_tier": player_tier,
        "tier": player_tier,
        "priority": 1,
    }


def _pqv_decision_label(
    *,
    player_id: str,
    name: str,
    role: str = "",
    active_narrative: crn.CanonicalRecommendationNarrative | None = None,
) -> tuple[str, bool]:
    """Return (decision_label, is_active) using PQV authority rules."""

    if active_narrative is not None and active_narrative.is_active_recommendation:
        html = player_quick_view.recommendation_context_html(
            active_narrative.reason,
            active_narrative.risk,
            action=active_narrative.action,
            active_recommendation=True,
            recommendation_id=active_narrative.recommendation_id,
        )
        assert "player-dossier-neutral-context" not in html
        return active_narrative.action, True

    neutral = crn.build_neutral_player_narrative(
        {"player_id": player_id, "name": name, "opportunity_explanation": "Depth chart context."},
        league_id="league-x",
        analysis_note="No attached move.",
        roster_context=f"Current roster role: {role}" if role else "",
    )
    presentation = neutral.pqv_presentation()
    assert presentation["action"] == ""
    decision = role or "No active recommendation"
    html = player_quick_view.recommendation_context_html(
        presentation["summary"],
        presentation["context"],
        action=decision,
        active_recommendation=False,
    )
    assert "player-dossier-neutral-context" in html
    assert "Hold" not in html or decision.casefold() != "hold"
    for banned in ("Shop", "Drop", "Acquire", "Monitor"):
        if decision.casefold() != banned.casefold():
            assert f">{banned}</strong>" not in html
    return decision, False


def test_developmental_roster_asset_hold_agrees_across_surfaces():
    player_id = "dev-qb"
    hold = [
        _candidate(
            player_id,
            "Dev QB",
            bucket="keep",
            reason="Young developmental stash.",
            young_upside_flag=True,
            protected_low_value_flag=True,
            player_tier="Development",
        )
    ]
    shop = [
        _candidate(
            player_id,
            "Dev QB",
            bucket="trade",
            reason="Outgoing in headline package.",
            source="headline_trade",
            young_upside_flag=True,
            protected_low_value_flag=True,
            player_tier="Development",
        )
    ]
    reconciled = rpa.reconcile_primary_action_lists(
        trade_candidates=shop, keep_candidates=hold, drop_candidates=[]
    )
    my_team = rpa.primary_action_for_player(
        player_id, trade_candidates=shop, keep_candidates=hold, drop_candidates=[]
    )
    assert my_team == rpa.ACTION_HOLD
    assert reconciled[rpa.ACTION_SHOP] == []

    hold_narrative = crn.build_roster_decision_narrative(
        hold[0],
        action="Hold",
        league_id="league-x",
        source_surface="my_team_hold",
    )
    label, active = _pqv_decision_label(
        player_id=player_id,
        name="Dev QB",
        role="Bench",
        active_narrative=hold_narrative,
    )
    assert active is True
    assert "hold" in label.casefold()


def test_true_shop_candidate_agrees():
    shop = [_candidate("shop-1", "Surplus TE", bucket="trade", reason="Redundant TE.")]
    hold = [_candidate("shop-1", "Surplus TE", bucket="keep", reason="Still useful.")]
    assert (
        rpa.primary_action_for_player(
            "shop-1", trade_candidates=shop, keep_candidates=hold, drop_candidates=[]
        )
        == rpa.ACTION_SHOP
    )
    narrative = crn.build_roster_decision_narrative(
        shop[0],
        action="Trade Candidate",
        league_id="league-x",
        source_surface="my_team_trade_candidate",
    )
    label, active = _pqv_decision_label(
        player_id="shop-1",
        name="Surplus TE",
        active_narrative=narrative,
    )
    assert active is True
    assert "trade" in label.casefold() or "shop" in label.casefold() or "candidate" in label.casefold()


def test_true_drop_candidate_agrees():
    drop = [_candidate("drop-1", "Cut Candidate", bucket="drop", reason="Replacement-level.")]
    hold = [_candidate("drop-1", "Cut Candidate", bucket="keep", reason="Maybe stash.")]
    assert (
        rpa.primary_action_for_player(
            "drop-1", trade_candidates=[], keep_candidates=hold, drop_candidates=drop
        )
        == rpa.ACTION_DROP
    )


def test_manual_untouchable_agrees():
    shop = [
        _candidate(
            "core-1",
            "Cornerstone",
            bucket="trade",
            reason="Headline outgoing.",
            source="headline_trade",
        )
    ]
    assert (
        rpa.primary_action_for_player(
            "core-1",
            trade_candidates=shop,
            keep_candidates=[],
            drop_candidates=[],
            untouchable_player_ids=["core-1"],
            player_name="Cornerstone",
        )
        == rpa.ACTION_PROTECT
    )


def test_neutral_player_no_active_move_does_not_invent_hold():
    label, active = _pqv_decision_label(
        player_id="neutral-1",
        name="Bench Depth",
        role="Bench",
        active_narrative=None,
    )
    assert active is False
    assert label.casefold() != "hold"
    assert label in {"Bench", "No active recommendation"} or "bench" in label.casefold()


def test_headline_outgoing_developmental_not_shop_on_my_team_or_pqv():
    player_id = "headline-dev"
    hold = [
        _candidate(
            player_id,
            "Young Stash",
            bucket="keep",
            reason="Developmental succession plan.",
            young_upside_flag=True,
            player_tier="Development",
        )
    ]
    shop = [
        _candidate(
            player_id,
            "Young Stash",
            bucket="trade",
            reason="Package piece only.",
            source="headline_trade",
            young_upside_flag=True,
            player_tier="Development",
        )
    ]
    assert (
        rpa.primary_action_for_player(
            player_id, trade_candidates=shop, keep_candidates=hold, drop_candidates=[]
        )
        == rpa.ACTION_HOLD
    )
    # Without a bound Hold narrative, PQV stays neutral — never Shop.
    label, active = _pqv_decision_label(
        player_id=player_id,
        name="Young Stash",
        role="Bench",
        active_narrative=None,
    )
    assert active is False
    assert "shop" not in label.casefold()
    assert "trade" not in label.casefold()


def test_bound_recommendation_displays_on_pqv():
    narrative = crn.build_roster_decision_narrative(
        {"player_id": "bound-1", "name": "Bound Player", "reason": "Move before the limit."},
        action="Trade Candidate",
        league_id="league-x",
        source_surface="my_team_trade_candidate",
    )
    assert narrative.is_active_recommendation is True
    label, active = _pqv_decision_label(
        player_id="bound-1",
        name="Bound Player",
        active_narrative=narrative,
    )
    assert active is True
    assert label == "Trade Candidate"


def test_no_simultaneous_primary_sections_after_reconcile():
    shop = [
        _candidate("a", "A", bucket="trade", reason="Surplus.", source="headline_trade"),
        _candidate(
            "b",
            "B",
            bucket="trade",
            reason="Surplus.",
            source="roster",
        ),
    ]
    hold = [
        _candidate(
            "a",
            "A",
            bucket="keep",
            reason="Developmental.",
            young_upside_flag=True,
            player_tier="Development",
        ),
        _candidate("c", "C", bucket="keep", reason="Hold."),
    ]
    drop = [_candidate("d", "D", bucket="drop", reason="Replacement.")]
    reconciled = rpa.reconcile_primary_action_lists(
        trade_candidates=shop, keep_candidates=hold, drop_candidates=drop
    )
    assert rpa.conflicting_primary_player_ids(
        trade_candidates=reconciled[rpa.ACTION_SHOP],
        keep_candidates=reconciled[rpa.ACTION_HOLD],
        drop_candidates=reconciled[rpa.ACTION_DROP],
    ) == set()
