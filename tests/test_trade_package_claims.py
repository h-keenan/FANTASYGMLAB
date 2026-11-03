"""Every sentence about rooms ("moves from RB surplus", "gets TE help") must be
true of the assets actually in the package.

A coridian_ report: a trade idea said the other team was moving RBs out when
the package held only a TE and a pick. Room labels used to be team-level
("RB is a surplus room") and the copy attached them to any asset at that
position, so a room being surplus was enough to say a trade moved from it.
Now a surplus claim needs a player in the package whom the one need model
calls surplus, and the claim is made for the side that actually sends him.
"""

from __future__ import annotations

from modules.trade_ideas import (
    _is_surplus_asset,
    _team_fit_assessment,
    _trade_reasoning_context,
    evaluate_trade_market_realism,
)

ME = {
    "strategy": "retool", "mode": "competitive", "needs": ["WR"], "surplus": ["TE"],
    "surplus_player_ids": {"TE": ["te-spare"]}, "counts": {"TE": 3, "WR": 4}, "minimums": {"TE": 1, "WR": 3},
}
PARTNER = {
    "strategy": "retool", "mode": "competitive", "needs": ["TE"], "surplus": ["RB"],
    "surplus_player_ids": {"RB": ["rb-spare"]}, "counts": {"RB": 4, "TE": 1}, "minimums": {"RB": 2, "TE": 1},
}


def _player(pid, pos, score=3000):
    return {
        "asset_type": "player", "player_id": pid, "label": pid, "name": pid, "position": pos, "score": score,
        "age": 25, "player_tier": "Starter", "status": "Active", "injury_status": "",
    }


def _pick(label="2027 Round 3"):
    return {"asset_type": "pick", "label": label, "round": 3, "score": 800, "position": "PICK"}


def test_a_te_and_a_pick_for_a_wr_never_says_anyone_moves_rbs():
    send = [_player("te-spare", "TE"), _pick()]
    receive = [_player("wr-1", "WR")]

    fit = _team_fit_assessment_pair(send, receive)
    reasoning = _trade_reasoning_context(ME, PARTNER, send, receive, "Rival")
    text = " ".join([fit, reasoning["summary"]])

    assert "TE surplus" in text  # I really do move my spare TE
    assert "RB" not in text      # the partner's RB room is surplus, but no RB is in the package
    assert "Rival can move" not in reasoning["summary"]


def _team_fit_assessment_pair(send, receive):
    mine = _team_fit_assessment(ME, send, receive, team_label="You", is_you=True)
    theirs = _team_fit_assessment(PARTNER, receive, send, team_label="Rival", is_you=False)
    return " ".join([mine["summary"], theirs["summary"], *mine["positives"], *theirs["positives"]])


def test_the_partner_is_only_moving_from_surplus_when_it_sends_a_surplus_player():
    # Sends a surplus RB: the claim is made, for the partner.
    spare = [_player("rb-spare", "RB")]
    reasoning = _trade_reasoning_context(ME, PARTNER, [_player("wr-9", "WR")], spare, "Rival")
    assert "Rival can move from RB surplus" in reasoning["summary"]
    assert "Surplus-Based" in reasoning["tags"]

    # Sends the RB starter: same room, no claim.
    starter = [_player("rb-1", "RB")]
    reasoning = _trade_reasoning_context(ME, PARTNER, [_player("wr-9", "WR")], starter, "Rival")
    assert "surplus" not in reasoning["summary"]
    assert "Surplus-Based" not in reasoning["tags"]


def test_market_realism_gives_no_surplus_credit_for_a_starter_at_a_surplus_position():
    common = dict(my_shape=ME, partner_shape=PARTNER, partner_name="Rival", send_assets=[_player("wr-9", "WR")])
    spare = evaluate_trade_market_realism(receive_assets=[_player("rb-spare", "RB")], **common)
    starter = evaluate_trade_market_realism(receive_assets=[_player("rb-1", "RB")], **common)

    assert any("moving from RB surplus" in line for line in spare["positives"])
    assert not any("surplus" in line for line in starter["positives"])


def test_picks_and_other_positions_are_never_surplus_assets():
    assert _is_surplus_asset(PARTNER, _player("rb-spare", "RB"))
    assert not _is_surplus_asset(PARTNER, _player("rb-1", "RB"))
    assert not _is_surplus_asset(PARTNER, _player("rb-spare", "WR"))  # same id, wrong room
    assert not _is_surplus_asset(PARTNER, _pick())
