"""Pick-glut caution (modules.trade_cautions): the owner's exact scenario and
the edges of the rule. Words plus a one-step softening; never the numbers."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from modules import trade_cautions, trade_offer_analyzer as toa, trade_posture

REBUILD = {"key": "rebuild", "group": "rebuild", "standing": "#11 of 12, 3-6"}
SEASONS = [2027, 2028]


def _pick(season, rnd, owner="1", score=3000):
    return {"asset_type": "pick", "season": season, "round": rnd, "owner_roster_id": owner,
            "label": f"{season} Round {rnd}", "score": score}


def _player(name, age, score, pos="WR"):
    return {"asset_type": "player", "name": name, "player_id": name, "age": age, "score": score, "position": pos}


def _held_five_firsts(open_spots=None):
    league = [_pick(2027, 1), _pick(2027, 1, score=2500), _pick(2027, 1, score=2400),
              _pick(2028, 1), _pick(2028, 1, score=2600), _pick(2027, 1, owner="2", score=2000)]
    return trade_cautions.build_pick_context(league, "1", open_roster_spots=open_spots)


OWNER_SEND = [_player("P. Washington", 24, 6037), _pick(2027, 3, score=150)]
OWNER_GET = [_player("Josh Downs", 25, 3921), _pick(2027, 1, owner="2", score=4100)]


def _fit(value_delta=1873, trade_score=1873, lineup_points=-19.0, posture=REBUILD):
    assessment = {"available": True, "lineup_points": lineup_points, "adjustment": 0}
    return {
        "available": True, "value_delta": value_delta, "trade_score": trade_score,
        "lineup_model": {"available": True, "confidence_label": "Moderate confidence", "confidence_pct": 75.0,
                         "explanation": "Costs about 19 lineup points over Weeks 10-17."},
        "posture": posture, "posture_assessment": assessment,
        "explanation": "Mixed: it adds a first-round pick, but it also costs lineup points.",
        "component_scores": {},
    }


def _verdict(send=OWNER_SEND, get=OWNER_GET, ctx=None, **kw):
    return toa.decide_offer_verdict(_fit(**kw), send_assets=send, receive_assets=get,
                                    pick_context=ctx if ctx is not None else _held_five_firsts())


def test_owner_scenario_tags_and_softens_one_step_without_touching_numbers():
    plain = toa.decide_offer_verdict(_fit(), send_assets=OWNER_SEND, receive_assets=OWNER_GET)
    assert plain.band == "SMASH ACCEPT" and plain.cautions == ()

    v = _verdict()
    assert v.band == "ACCEPT" and v.ui_verdict == "ACCEPT" and v.tone == "accept"
    assert v.score_band == "ACCEPT"
    # Numbers are exactly the same as without the caution.
    assert (v.value_delta, v.trade_score, v.confidence, v.confidence_pct) == (
        plain.value_delta, plain.trade_score, plain.confidence, plain.confidence_pct)
    (c,) = v.cautions
    assert c["code"] == "pick_glut" and c["tag"] == "Trading proven value for picks you may not need"
    assert c["softened"] is True and c["softened_from"] == "SMASH ACCEPT"
    assert c["facts"]["held_firsts"] == 5
    # Copy agrees with the label: no "win big" line under a plain ACCEPT.
    assert "big" not in v.value_summary.lower() and v.value_summary == "You win on value"
    assert v.to_public_dict()["cautions"][0]["tag"] == c["tag"]


def test_already_accept_keeps_label_but_shows_tag():
    v = _verdict(value_delta=900, trade_score=900)
    assert v.band == "ACCEPT" and v.cautions and v.cautions[0]["softened"] is False


def test_never_more_than_one_step_and_not_on_bad_verdicts():
    assert _verdict(value_delta=-800, trade_score=-800).cautions == ()
    assert _verdict(value_delta=3000, trade_score=3000).band == "ACCEPT"  # one step only


@pytest.mark.parametrize(
    "mutate",
    [
        lambda a: a.update(posture={"key": "contender", "group": "contender"}),  # direction
        lambda a: a.update(ctx=trade_cautions.build_pick_context(
            [_pick(2027, 1), _pick(2028, 1), _pick(2027, 1, "2")], "1")),  # holds few picks
        lambda a: a.update(get=[_player("Josh Downs", 25, 3921), _pick(2029, 1, "2")]),  # far-future pick
        lambda a: a.update(get=[_player("Josh Downs", 25, 6000), _pick(2027, 2, "2", score=300)]),  # picks are a sweetener
        lambda a: a.update(send=[_player("Vet WR", 31, 6037)]),  # classic aging sale
        lambda a: a.update(ctx=_held_five_firsts(open_spots=12)),  # plenty of roster room
    ],
)
def test_rule_stays_quiet_when_any_factor_is_missing(mutate):
    args = {"send": OWNER_SEND, "get": OWNER_GET, "ctx": _held_five_firsts()}
    posture = REBUILD
    mutate(args)
    posture = args.pop("posture", posture)
    v = toa.decide_offer_verdict(_fit(posture=posture), send_assets=args["send"], receive_assets=args["get"],
                                 pick_context=args["ctx"])
    assert v.cautions == () and v.band == "SMASH ACCEPT"


def test_no_current_value_out_no_caution():
    send = [_player("Bench WR", 24, 3000)]
    get = [_player("Downs", 25, 3000), _pick(2027, 1, "2")]
    v = toa.decide_offer_verdict(_fit(lineup_points=0.0), send_assets=send, receive_assets=get,
                                 pick_context=_held_five_firsts())
    assert v.cautions == ()


def test_lineup_loss_alone_counts_as_current_outflow_and_unknown_room_does_not_block():
    send = [_player("Starter", 25, 3000)]
    get = [_player("Prospect", 22, 2800, pos="RB"), _pick(2027, 1, "2", score=3500)]
    v = toa.decide_offer_verdict(_fit(lineup_points=-12.0), send_assets=send, receive_assets=get,
                                 pick_context=_held_five_firsts(open_spots=None))
    assert v.cautions


def test_multi_team_style_context_builder_ignores_other_owners_and_far_drafts():
    ctx = trade_cautions.build_pick_context(
        [_pick(2027, 1), _pick(2027, 2), _pick(2029, 1), _pick(2027, 1, "9")], "1")
    assert ctx["held_units"] == 2.5 and ctx["seasons"] == [2027, 2029] and ctx["held_firsts"] == 2


def test_explanation_wording_is_one_line_and_mirrors_the_web_twin():
    c = trade_cautions.pick_glut(REBUILD, OWNER_SEND, OWNER_GET, _held_five_firsts(), {"lineup_points": -19})
    assert "\n" not in c["explanation"] and c["explanation"].startswith("You already hold 5 first- and second-round")
    root = Path(__file__).resolve().parent.parent
    ts = (root / "web-next/src/lib/tradeCautions.ts").read_text()
    assert trade_cautions.PICK_GLUT_TAG in ts
    assert (root / "mobile/src/lib/tradeCautions.ts").read_bytes() == (root / "web-next/src/lib/tradeCautions.ts").read_bytes()


def test_share_card_keeps_true_numbers():
    v = _verdict()
    card = toa.build_offer_eval_share_card(v, send_assets=OWNER_SEND, receive_assets=OWNER_GET)
    assert card.send_total == 6037 + 150 and card.acquire_total == 3921 + 4100
    assert card.value_change and "1,873" in card.value_change.replace("+", "") or card.value_change
    assert card.action == "ACCEPT"
