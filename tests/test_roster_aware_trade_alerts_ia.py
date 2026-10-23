from __future__ import annotations

from pathlib import Path


from modules import alerts_activity, trade_ideas


def _player(name: str, position: str, score: int = 3000) -> dict:
    return {
        "asset_type": "player",
        "label": name,
        "name": name,
        "player_id": name.casefold().replace(" ", "-"),
        "position": position,
        "score": score,
        "age": 25,
        "role": "Flex",
    }


def _pick(label: str = "2027 Round 3", score: int = 500) -> dict:
    return {"asset_type": "pick", "label": label, "score": score, "round": 3}


def _shape(*, needs=(), surplus=(), strategy="retool", counts=None, minimums=None):
    return {
        "needs": list(needs),
        "surplus": list(surplus),
        "strategy": strategy,
        "mode": strategy,
        "counts": counts or {"QB": 2, "RB": 5, "WR": 7, "TE": 3},
        "minimums": minimums or {"QB": 2, "RB": 3, "WR": 4, "TE": 2},
        "room_coverage": {},
        "draft_capital_tier": "middle",
    }


def _assessed_idea(my_shape, partner_shape, send, receive, *, value_delta=500):
    fit = trade_ideas._trade_fit_context(
        my_shape, partner_shape, send, receive, "Partner"
    )
    market = {
        "score": 82,
        "label": "Likely",
        "value_delta": value_delta,
        "hard_fail": False,
    }
    idea = trade_ideas._make_idea(
        "Partner",
        send,
        receive,
        str(my_shape.get("mode")),
        str(partner_shape.get("mode")),
        "Roster-aware path",
        fit["rationale"],
        100,
        reasoning_tags=["Need-Based", "Value Arbitrage"],
        reasoning_summary=fit["rationale"],
    )
    return trade_ideas._attach_trade_assessment_fields(
        idea, fit_context=fit, market_context=market
    )


def test_value_arbitrage_can_justify_surplus_acquisition_without_hidden_harm():
    my_shape = _shape(surplus=("TE",))
    partner_shape = _shape(needs=("WR",), surplus=("TE",))
    idea = _assessed_idea(
        my_shape,
        partner_shape,
        [_player("Depth WR", "WR", 2000)],
        [_player("Premium TE", "TE", 3500)],
        value_delta=1500,
    )

    assert idea["my_fit_negatives"] == []
    assert idea["trade_headline_fit_exception"] is True
    assert idea["trade_headline_ready"] is True


def test_contender_rebuilder_and_pick_package_keep_final_package_perspective():
    for strategy in ("contender", "rebuild"):
        my_shape = _shape(needs=("RB",), surplus=("WR",), strategy=strategy)
        partner_shape = _shape(needs=("WR",), surplus=("RB",), strategy="retool")
        send = [_player("Outgoing WR", "WR"), _pick()]
        receive = [_player("Incoming RB", "RB", 3400)]
        fit = trade_ideas._trade_fit_context(
            my_shape, partner_shape, send, receive, "Partner"
        )
        assert "You get RB help" in fit["rationale"]
        assert "Partner" in fit["rationale"] and "gets WR help" in fit["rationale"]
        assert "You get WR help" not in fit["rationale"]


def test_shallow_and_deep_rosters_protect_depth_from_final_package():
    shallow = _shape(counts={"QB": 2, "RB": 3, "WR": 4, "TE": 2})
    deep = _shape(counts={"QB": 3, "RB": 7, "WR": 9, "TE": 4}, surplus=("QB",))
    partner = _shape(needs=("QB",))
    send = [_player("QB Depth", "QB")]
    receive = [_pick(score=1800)]

    shallow_fit = trade_ideas._trade_fit_context(shallow, partner, send, receive, "Partner")
    deep_fit = trade_ideas._trade_fit_context(deep, partner, send, receive, "Partner")
    assert shallow_fit["my_score"] < deep_fit["my_score"]
    assert "create a QB depth problem" in shallow_fit["my_negatives"]


def test_balanced_package_rationale_is_recomputed_from_mutated_final_assets():
    my_shape = _shape(needs=("TE",), surplus=("QB",))
    partner_shape = _shape(needs=("QB",), surplus=("TE",))
    original = trade_ideas._trade_fit_context(
        my_shape,
        partner_shape,
        [_player("QB", "QB")],
        [_player("TE", "TE")],
        "Partner",
    )
    final = trade_ideas._trade_fit_context(
        my_shape,
        partner_shape,
        [_player("WR", "WR"), _pick()],
        [_player("TE", "TE")],
        "Partner",
    )
    assert "Partner gets QB help" in original["rationale"]
    assert "Partner gets QB help" not in final["rationale"]
    assert "You get TE help" in final["rationale"]
