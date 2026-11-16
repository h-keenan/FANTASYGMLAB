"""An accept reason that names a position must agree with the Needs tag, the offer and the valuation (pos_v 1).

Report (Sim mock): partner tagged NEEDS WR / NEEDS K / DEEP RB / DEEP TE, user sends a WR and receives an RB, and the reason read "They need a RB and this
fills it." (a position the partner is deep at, on the side the partner is giving up). The real desk only ever said "They like how this fits their roster", and
the mock text was canned; the engine now names the position, from the same report as the tag, and only one the user sends."""

from __future__ import annotations

import numpy as np

from modules.sim.calibration.kicker_trade_stress import Stress, make_settings
from modules.sim.game_ai import TradeDesk
from modules.sim.game_eval import Evaluator
from modules.sim.game_need import position_report
from modules.sim.types import is_pick_id


def world(seed: int, pos_v: int):
    r = np.random.default_rng(seed)
    flags = {"limit_v": 1, "econ_v": 1, "hint_v": 1, "vorp_v": 1, "pos_v": pos_v}
    s = Stress(seed, make_settings(r, kd_v=1, dynasty=False, flags=flags), r)
    return s, s.view()


def accepted_offers(seed: int, pos_v: int):
    s, snap = world(seed, pos_v)
    st, user = s.state, snap.user_team.tid
    ev = Evaluator(snap, st)
    desk = TradeDesk(ev, seed, st.week)
    for ai in snap.tids:
        if ai == user:
            continue
        mine = [p for p in st.rosters[user] if not is_pick_id(p)]
        theirs = [p for p in st.rosters[ai] if not is_pick_id(p)]
        for give in mine:
            for get in theirs[:6]:
                if snap.players[give].pos == snap.players[get].pos:
                    continue
                v = desk.verdict(ai, [give], [get])
                if v.decision == "accept":
                    yield snap, ev, ai, give, get, v


def test_reason_names_only_a_needed_position_the_user_sends():
    named = generic = 0
    for seed in (3, 4, 5, 8, 11):
        for snap, ev, ai, give, get, v in accepted_offers(seed, 1):
            tags = {e["pos"]: e["level"] for e in position_report(snap, ev)[ai]}
            if v.reason.startswith("They need a "):
                pos = v.reason.split()[3]
                assert v.reason_code == "fits_need"
                assert tags[pos] == "need", (v.reason, tags)  # the Needs tag says so
                assert snap.players[give].pos == pos  # the user is sending it
                named += 1
            else:
                generic += 1
            for pos, level in tags.items():  # never a reason built on a position the partner is strong at
                if level == "strength":
                    assert f"They need a {pos}" not in v.reason
    assert named > 0 and generic > 0


def test_an_old_save_keeps_the_generic_wording():
    seen = 0
    for seed in (3, 4):
        for _snap, _ev, _ai, _give, _get, v in accepted_offers(seed, 0):
            seen += 1
            assert v.reason in ("They like how this fits their roster.", "They see this as a fair deal.")
    assert seen > 0
