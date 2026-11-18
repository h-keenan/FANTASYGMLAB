"""Trade ideas must be acceptable to the PARTNER, not just flattering to the user.

Reproduces the owner-reported ideas: a young/aging TE sent for another team's
2027 R1 showed "+497 / +296, High confidence, You win by ~18% / ~11%".
"""

from types import SimpleNamespace

import pandas as pd

from modules import trade_ideas
from modules.trade_ideas import (
    _attach_trade_assessment_fields,
    evaluate_trade_market_realism,
    partner_acceptance_context,
    partner_reason_text,
)


def te(name, score, age):
    return {
        "asset_type": "player",
        "label": name,
        "name": name,
        "score": score,
        "age": age,
        "player_tier": "Starter",
        "role": "Flex",
        "position": "TE",
        "status": "Active",
        "injury_status": "",
    }


def r1(score, label="2027 Round 1"):
    return {"asset_type": "pick", "label": label, "score": score, "round": 1, "position": "PICK"}


MY_SHAPE = {"strategy": "retool", "mode": "competitive", "needs": [], "surplus": []}


def partner(strategy, needs=(), surplus_ids=None):
    return {
        "strategy": strategy,
        "mode": "competitive",
        "needs": list(needs),
        "surplus": [],
        "surplus_player_ids": surplus_ids or {},
    }


def _run(send, receive, partner_shape):
    market = evaluate_trade_market_realism(
        send_assets=send,
        receive_assets=receive,
        my_shape=MY_SHAPE,
        partner_shape=partner_shape,
        partner_name="Partner",
    )
    idea = {"reasoning_tags": ["Value Arbitrage"], "reasoning_summary": "x"}
    fit = {"score": 20, "my_score": 10, "partner_score": 8}
    _attach_trade_assessment_fields(idea, fit_context=fit, market_context=market)
    return market, idea


def test_darnell_washington_for_2027_r1_is_not_a_high_confidence_win():
    # 2,195 TE for a 2,692 R1: the user wins by +497, about 18% of what the partner gives up.
    for strategy in ("contender", "rebuild", "retool"):
        for needs in ((), ("TE",)):
            market, idea = _run([te("Darnell Washington", 2195, 25)], [r1(2692)], partner(strategy, needs))
            assert market["partner_acceptance"]["user_edge"] == 497
            assert market["hard_fail"], (strategy, needs)
            assert "partner_value_loss" in market["hard_fail_flags"]
            assert idea["trade_confidence_label"] != "High"
            assert idea["trade_confidence_label"] == "Low"
            assert idea["market_realism_hard_fail"] is True


def test_david_njoku_for_2027_r1_is_not_a_high_confidence_win_for_a_partner_without_te_need():
    # 2,396 TE (age 30) for the same R1: +296, about 11%.
    for strategy in ("contender", "rebuild"):
        market, idea = _run([te("David Njoku", 2396, 30)], [r1(2692)], partner(strategy, ()))
        assert market["partner_acceptance"]["user_edge"] == 296
        assert market["hard_fail"], strategy
        assert idea["trade_confidence_label"] != "High"


def test_even_a_need_hit_cannot_stretch_to_an_eighteen_percent_edge():
    market, _ = _run([te("Darnell Washington", 2195, 25)], [r1(2692)], partner("contender", ("TE",)))
    assert market["partner_acceptance"]["need_hits"] == ["TE"]
    assert market["partner_acceptance"]["edge_cap"] <= trade_ideas.PARTNER_EDGE_MAX_CAP
    assert market["partner_lopsided"] is True


def test_fair_trade_for_a_partner_who_needs_the_position_passes_without_the_lopsided_flag():
    send = [te("Starter TE", 2650, 26)]
    receive = [r1(2692)]
    market, idea = _run(send, receive, partner("contender", ("TE",)))
    assert "partner_value_loss" not in market["hard_fail_flags"]
    assert market["partner_lopsided"] is False
    assert idea["partner_fit_reason"] == "Fills their TE hole · they're contending"


def test_age_fit_and_need_move_the_cap():
    send_old = [te("Old TE", 2400, 30)]
    send_young = [te("Young TE", 2400, 24)]
    receive = [r1(2692)]
    rebuild_old = partner_acceptance_context(
        send_assets=send_old, receive_assets=receive, partner_shape=partner("rebuild", ()), send_score=2400, receive_score=2692
    )
    rebuild_young_need = partner_acceptance_context(
        send_assets=send_young, receive_assets=receive, partner_shape=partner("rebuild", ("TE",)), send_score=2400, receive_score=2692
    )
    contend_need = partner_acceptance_context(
        send_assets=send_old, receive_assets=receive, partner_shape=partner("contender", ("TE",)), send_score=2400, receive_score=2692
    )
    assert rebuild_old["edge_cap"] < contend_need["edge_cap"]
    assert rebuild_old["age_fit"] == "poor"
    assert rebuild_young_need["age_fit"] == "good"
    assert rebuild_old["edge_cap"] < rebuild_young_need["edge_cap"] + 0.0001 or rebuild_old["lopsided"]
    assert "older piece" in partner_reason_text(rebuild_old)
    assert partner_reason_text(rebuild_old).startswith("Light fit: no TE need")


def test_surplus_at_the_position_lowers_the_cap():
    send = [te("Spare TE", 2400, 27) | {"player_id": "te1"}]
    base = partner_acceptance_context(
        send_assets=send, receive_assets=[r1(2692)], partner_shape=partner("contender", ()), send_score=2400, receive_score=2692
    )
    surplus = partner_acceptance_context(
        send_assets=send,
        receive_assets=[r1(2692)],
        partner_shape=partner("contender", (), {"TE": ["te9"]}),
        send_score=2400,
        receive_score=2692,
    )
    assert surplus["edge_cap"] < base["edge_cap"]


def test_the_partner_reason_is_short_neutral_text():
    ctx = partner_acceptance_context(
        send_assets=[te("A", 2500, 26)],
        receive_assets=[r1(2692)],
        partner_shape=partner("contender", ("TE",)),
        send_score=2500,
        receive_score=2692,
    )
    reason = partner_reason_text(ctx)
    assert reason == "Fills their TE hole · they're contending"
    assert len(reason) < 60


# --- pick slot valuation by ORIGINAL owner -------------------------------------------------


def _league_picks(traded):
    summary = pd.DataFrame(
        {
            "roster_id": [1, 2, 3, 4],
            "team_name": ["Strong", "Good", "Weak", "Worst"],
            "total_score": [40000, 30000, 20000, 10000],
        }
    )
    rosters = [{"roster_id": i, "players": [], "settings": {}} for i in (1, 2, 3, 4)]
    adapter = SimpleNamespace(
        get_rosters=lambda _l: rosters,
        get_league=lambda _l: {"season": 2026, "settings": {"draft_rounds": 2, "type": 2}},
        get_traded_picks=lambda _l: traded,
        normalize_roster=lambda raw: raw,
    )
    settings = {"league_format": "Dynasty", "qb_format": "1QB", "league_size": 4}
    status = {"draft_year": 2026, "current_year_picks_active": False, "draft_completed": True}
    return trade_ideas._build_roster_pick_assets(
        "L", rosters, summary, league_settings=settings, draft_status=status, adapter=adapter
    )


def _find(built, owner, season, rnd, original):
    return next(
        p
        for p in built[owner]
        if p["season"] == season and p["round"] == rnd and p["original_roster_id"] == original
    )


def test_pick_value_follows_the_original_owners_projected_finish_not_the_holder():
    # Roster 1 (strongest) holds roster 4's (worst) 2027 R1 via trade; roster 1 also owns its own.
    traded = [{"season": 2027, "round": 1, "roster_id": 4, "owner_id": 1, "previous_owner_id": 4}]
    built = _league_picks(traded)
    from_worst = _find(built, 1, 2027, 1, 4)
    own = _find(built, 1, 2027, 1, 1)
    assert from_worst["owner_roster_id"] == 1
    assert from_worst["score"] > own["score"]
    assert from_worst["projected_slot_percentile"] > own["projected_slot_percentile"]
    # Worst team's pick is projected earlier in the round than the strongest team's.
    assert from_worst["projected_slot_number"] < own["projected_slot_number"]
    assert from_worst["projected_slot_label"].startswith("1.")
    assert len(from_worst["projected_slot_label"]) == 4


def test_projected_slot_label_and_bounds():
    assert trade_ideas._projected_pick_slot(1, 1.0, 12) == (1, "1.01")
    assert trade_ideas._projected_pick_slot(1, 0.0, 12) == (12, "1.12")
    assert trade_ideas._projected_pick_slot(2, 0.5, 12)[1].startswith("2.")


def test_projected_slot_survives_pick_asset_and_presentation():
    from modules.compact_fantasy_assets import presentation_asset

    built = _league_picks([])
    raw = _find(built, 3, 2027, 1, 3)
    asset = trade_ideas._pick_asset(raw)
    assert asset["projected_slot_label"] == raw["projected_slot_label"]
    shown = presentation_asset(asset)
    assert shown["projected_slot_label"] == raw["projected_slot_label"]
    assert shown["projected_slot_number"] == raw["projected_slot_number"]


# --- partner-loss ceiling regression --------------------------------------------------------


def _rb(score, age):
    asset = te("RB Starter", score, age)
    asset["position"] = "RB"
    return asset


def test_screenshot_case_rb_2600_for_2027_r1_3220_is_rejected_in_every_posture():
    # Owner screenshot: "+620 / You win by ~19% / Medium". Partner loses 620 of 3,220 (19.25%).
    for strategy in ("contender", "fringe_contender", "rebuild", "retool"):
        for needs in (("RB",), ()):
            market, idea = _run([_rb(2600, 26)], [r1(3220)], partner(strategy, needs))
            pa = market["partner_acceptance"]
            assert pa["user_edge"] == 620
            assert pa["user_edge_ratio"] > 0.19
            assert pa["lopsided"] is True, (strategy, needs)
            assert "partner_value_loss" in market["hard_fail_flags"]
            assert idea["trade_confidence_label"] == "Low"


def test_no_adjustment_combination_lets_the_partner_lose_more_than_twelve_percent():
    ceiling = trade_ideas.PARTNER_EDGE_HARD_CEILING
    assert ceiling <= 0.12
    for receive in (600, 1000, 1500, 2692, 3220, 5000):
        for strategy in ("contender", "rebuild"):
            for needs in (("RB",), ()):
                for age in (23, 26, 30):
                    send_score = int(receive * 0.85)  # partner loses 15%
                    ctx = partner_acceptance_context(
                        send_assets=[_rb(send_score, age)],
                        receive_assets=[r1(receive)],
                        partner_shape=partner(strategy, needs),
                        send_score=send_score,
                        receive_score=receive,
                    )
                    assert ctx["lopsided"] is True, (receive, strategy, needs, age)
                    assert ctx["allowed_edge"] <= round(ceiling * receive)


def test_most_generous_cap_still_passes_a_small_loss_and_rejects_the_screenshot():
    gen = partner_acceptance_context(
        send_assets=[_rb(2600, 26)], receive_assets=[r1(3220)],
        partner_shape=partner("contender", ("RB",)), send_score=2600, receive_score=3220,
    )
    assert gen["edge_cap"] == trade_ideas.PARTNER_EDGE_MAX_CAP == 0.09
    ok = partner_acceptance_context(
        send_assets=[_rb(3000, 26)], receive_assets=[r1(3220)],
        partner_shape=partner("contender", ("RB",)), send_score=3000, receive_score=3220,
    )
    assert ok["lopsided"] is False  # 220 / 3,220 = 6.8%


def test_displayed_win_percent_uses_the_same_denominator_as_the_loss_cap():
    # UI tradeEdge() = (get - give) / max(give, get); when the user wins, get (what the partner
    # gives up) is the larger side, so this equals user_edge / receive_score used by the cap.
    ctx = partner_acceptance_context(
        send_assets=[_rb(3000, 26)], receive_assets=[r1(3220)],
        partner_shape=partner("contender", ("RB",)), send_score=3000, receive_score=3220,
    )
    assert ctx["user_edge_ratio"] == round((3220 - 3000) / max(3000, 3220), 4)
