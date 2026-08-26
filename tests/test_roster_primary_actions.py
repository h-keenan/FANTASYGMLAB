"""Mutually exclusive My Team primary actions (Shop / Hold / Drop / Protect)."""

from __future__ import annotations

from pathlib import Path

from modules import roster_primary_actions as rpa


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
TY = "ty-simpson-1"
HOLD_REASON = "Young developmental stash with enough upside to protect instead of forcing a bad cut."
SHOP_REASON = "Direct outgoing piece in the current headline trade path for a starter with this partner."


def _item(player_id: str, name: str, *, bucket: str, reason: str, source: str = "roster") -> dict:
    return {
        "player_id": player_id,
        "player_name": name,
        "name": name,
        "bucket": bucket,
        "reason": reason,
        "note": reason,
        "source": source,
        "priority": 1,
    }


def test_ty_simpson_style_headline_shop_is_not_also_hold():
    hold = [_item(TY, "Ty Simpson", bucket="keep", reason=HOLD_REASON)]
    shop = [
        _item(
            TY,
            "Ty Simpson",
            bucket="trade",
            reason=SHOP_REASON,
            source="headline_trade",
        )
    ]
    before = rpa.conflicting_primary_player_ids(
        trade_candidates=shop, keep_candidates=hold, drop_candidates=[]
    )
    assert before == {TY}
    reconciled = rpa.reconcile_primary_action_lists(
        trade_candidates=shop,
        keep_candidates=hold,
        drop_candidates=[],
    )
    after = rpa.conflicting_primary_player_ids(
        trade_candidates=reconciled[rpa.ACTION_SHOP],
        keep_candidates=reconciled[rpa.ACTION_HOLD],
        drop_candidates=reconciled[rpa.ACTION_DROP],
    )
    assert after == set()
    assert [item["player_id"] for item in reconciled[rpa.ACTION_SHOP]] == [TY]
    assert reconciled[rpa.ACTION_HOLD] == []
    assert rpa.primary_action_for_player(
        TY,
        trade_candidates=shop,
        keep_candidates=hold,
        drop_candidates=[],
        player_name="Ty Simpson",
    ) == rpa.ACTION_SHOP


def test_manual_untouchable_is_not_shop_hold_or_drop():
    player = _item("p-core", "Core Back", bucket="trade", reason="Surplus depth.")
    hold = [_item("p-core", "Core Back", bucket="keep", reason=HOLD_REASON)]
    drop = [_item("p-core", "Core Back", bucket="drop", reason="Replacement-level.")]
    reconciled = rpa.reconcile_primary_action_lists(
        trade_candidates=[player],
        keep_candidates=hold,
        drop_candidates=drop,
        untouchable_names=["Core Back"],
        untouchable_player_ids=["p-core"],
    )
    assert reconciled[rpa.ACTION_SHOP] == []
    assert reconciled[rpa.ACTION_HOLD] == []
    assert reconciled[rpa.ACTION_DROP] == []
    assert (
        rpa.primary_action_for_player(
            "p-core",
            trade_candidates=[player],
            keep_candidates=hold,
            drop_candidates=drop,
            untouchable_names=["Core Back"],
            player_name="Core Back",
        )
        == rpa.ACTION_PROTECT
    )


def test_legitimate_hold_is_not_shop_or_drop():
    hold = [_item("hold-1", "Stash Wideout", bucket="keep", reason=HOLD_REASON)]
    reconciled = rpa.reconcile_primary_action_lists(
        trade_candidates=[],
        keep_candidates=hold,
        drop_candidates=[],
    )
    assert [item["player_id"] for item in reconciled[rpa.ACTION_HOLD]] == ["hold-1"]
    assert reconciled[rpa.ACTION_SHOP] == []
    assert reconciled[rpa.ACTION_DROP] == []


def test_legitimate_drop_is_not_hold_or_shop():
    drop = [_item("drop-1", "Buried Vet", bucket="drop", reason="Replacement-level veteran.")]
    hold = [_item("drop-1", "Buried Vet", bucket="keep", reason=HOLD_REASON)]
    reconciled = rpa.reconcile_primary_action_lists(
        trade_candidates=[],
        keep_candidates=hold,
        drop_candidates=drop,
    )
    assert [item["player_id"] for item in reconciled[rpa.ACTION_DROP]] == ["drop-1"]
    assert reconciled[rpa.ACTION_HOLD] == []
    assert reconciled[rpa.ACTION_SHOP] == []


def test_replacement_drop_beats_generic_surplus_shop():
    shop = [_item("k-2", "Extra Kicker", bucket="trade", reason="Surplus kicker depth.")]
    drop = [_item("k-2", "Extra Kicker", bucket="drop", reason="Replaceable kicker surplus.")]
    reconciled = rpa.reconcile_primary_action_lists(
        trade_candidates=shop,
        keep_candidates=[],
        drop_candidates=drop,
    )
    assert [item["player_id"] for item in reconciled[rpa.ACTION_DROP]] == ["k-2"]
    assert reconciled[rpa.ACTION_SHOP] == []


def test_headline_shop_beats_drop():
    shop = [
        _item(
            TY,
            "Ty Simpson",
            bucket="trade",
            reason=SHOP_REASON,
            source="headline_trade",
        )
    ]
    drop = [_item(TY, "Ty Simpson", bucket="drop", reason="Replacement-level.")]
    hold = [_item(TY, "Ty Simpson", bucket="keep", reason=HOLD_REASON)]
    reconciled = rpa.reconcile_primary_action_lists(
        trade_candidates=shop,
        keep_candidates=hold,
        drop_candidates=drop,
    )
    assert [item["player_id"] for item in reconciled[rpa.ACTION_SHOP]] == [TY]
    assert reconciled[rpa.ACTION_DROP] == []
    assert reconciled[rpa.ACTION_HOLD] == []


def test_trade_candidate_is_not_hold():
    shop = [_item("shop-1", "Movable Tight End", bucket="trade", reason="Redundant TE depth.")]
    hold = [_item("shop-1", "Movable Tight End", bucket="keep", reason=HOLD_REASON)]
    reconciled = rpa.reconcile_primary_action_lists(
        trade_candidates=shop,
        keep_candidates=hold,
        drop_candidates=[],
    )
    assert [item["player_id"] for item in reconciled[rpa.ACTION_SHOP]] == ["shop-1"]
    assert reconciled[rpa.ACTION_HOLD] == []


def test_different_players_can_occupy_different_sections():
    shop = [_item("shop-1", "Shop Player", bucket="trade", reason="Surplus.")]
    hold = [_item("hold-1", "Hold Player", bucket="keep", reason=HOLD_REASON)]
    drop = [_item("drop-1", "Drop Player", bucket="drop", reason="No NFL team.")]
    reconciled = rpa.reconcile_primary_action_lists(
        trade_candidates=shop,
        keep_candidates=hold,
        drop_candidates=drop,
    )
    assert [item["player_id"] for item in reconciled[rpa.ACTION_SHOP]] == ["shop-1"]
    assert [item["player_id"] for item in reconciled[rpa.ACTION_HOLD]] == ["hold-1"]
    assert [item["player_id"] for item in reconciled[rpa.ACTION_DROP]] == ["drop-1"]
    assert rpa.conflicting_primary_player_ids(
        trade_candidates=reconciled[rpa.ACTION_SHOP],
        keep_candidates=reconciled[rpa.ACTION_HOLD],
        drop_candidates=reconciled[rpa.ACTION_DROP],
    ) == set()


def test_roster_actions_shop_agrees_with_canonical_shop():
    from app import select_my_team_primary_recommendation

    shop = [
        _item(
            TY,
            "Ty Simpson",
            bucket="trade",
            reason=SHOP_REASON,
            source="headline_trade",
        )
    ]
    hold = [_item(TY, "Ty Simpson", bucket="keep", reason=HOLD_REASON)]
    reconciled = rpa.reconcile_primary_action_lists(
        trade_candidates=shop, keep_candidates=hold, drop_candidates=[]
    )
    rec = select_my_team_primary_recommendation(
        roster_limit_context={"over_limit": False},
        acute_injury_pressure=False,
        health_flag="Healthy",
        injured_starters=0,
        injury_alert_note="",
        headline_trade_idea={
            "their_player": "Target Back",
            "partner_team_name": "Partner",
            "send_assets": [{"asset_type": "player", "player_id": TY}],
        },
        trade_summary={
            "rationale": "Need a startable RB.",
            "buy_low": "Target Back",
            "partner": "Partner",
        },
        top_waiver=None,
        advice_items=[],
        major_needed_positions=["RB"],
        trade_candidates=reconciled[rpa.ACTION_SHOP],
        drop_candidates=[],
        move_candidates=[],
    )
    assert rec["value"] == "Shop Ty Simpson"
    assert rec["player_id"] == TY
    assert TY not in {item["player_id"] for item in reconciled[rpa.ACTION_HOLD]}


def test_headline_prioritize_then_reconcile_matches_my_team_owner():
    prioritize_at = APP.index("prioritize_trade_candidates_with_headline(")
    reconcile_block = APP.index(
        "reconciled_actions = roster_primary_actions.reconcile_primary_action_lists(",
        prioritize_at,
    )
    assert reconcile_block > prioritize_at
    assert "hold_candidates_structured" in APP[reconcile_block : reconcile_block + 1200]
    assert "roster_primary_actions.reconcile_primary_action_lists(" in APP


def test_no_new_provider_or_trade_hub_construction_in_owner():
    source = (ROOT / "modules" / "roster_primary_actions.py").read_text(encoding="utf-8")
    assert "sleeper" not in source.casefold()
    assert "requests." not in source
    assert "load_cached_news_pool" not in source
    assert "build_trade_ideas" not in source
    assert "st.rerun" not in source
