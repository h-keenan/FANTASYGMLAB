"""ai_v 1: AI managers plan depth around byes and injuries and use the wire proactively; ai_v 0 saves replay as they were."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from modules.sim import game_ai_depth as ad
from modules.sim import game_scoring
from modules.sim.calibration import ai_report, dataset, tail_report
from modules.sim.game_engine import _post_trade_cover, advance, waiver_order
from modules.sim.game_eval import Evaluator
from modules.sim.game_setup import build_snapshot
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import GameSettings
from modules.sim.game_view import _tx_text
from tests.test_sim_game_engine import BYES, ROWS, drafted
from tests.test_sim_game_model_versions import V4_ID, _play

# state digests after weeks 2..6 for seed 11 / user slot 4, ai_v 1 on player-model-4 (the first AI generation with depth planning)
GOLDEN_AI1_DIGESTS = {6: "34d37f5985aefc03182102e7cea6006c843e13b2bdc67681608f1f83f7bee1b0"}
# the same game with ai_v 0 (the AI as it was before depth planning)
GOLDEN_AI0_V4_DIGESTS = {
    2: "16845171ac1717edde30e2d51dc5043ac4269f9738f83c586c932d6f31de7c23",
    3: "d5afe24f87fafbd31afe2161b60b7f34cf6313b5701e20315ed682805595e303",
    4: "61b468d52d92989435eea5f2e37eb950927bef59ee620b46fd2c240a7e54b6b2",
    5: "9b1dc12e2bb67f44e9e29bcf614e14c777de55a39ea82f8aa07c199168010e4d",
    6: "28511111c0bc86d841b41b873d9b131561c9c28f0aa0af372159756c83326361",
}


def ai_team(snap, state):
    return next(t.tid for t in snap.teams if not t.is_user)


def pids_at(snap, pos, team=None):
    return [p for p in snap.pids if snap.players[p].pos == pos and (team is None or snap.players[p].nfl_team == team)]


def roster_of(snap, state, tid, spec):
    """Give ``tid`` exactly the roster ``spec`` ({pos: n}) from the best free or owned players, others untouched."""

    owned_elsewhere = {p for t, r in state.rosters.items() if t != tid for p in r}
    chosen = []
    for pos, n in spec.items():
        pool = [p for p in sorted(snap.pids, key=lambda p: (-snap.players[p].mean, p)) if snap.players[p].pos == pos and p not in owned_elsewhere]
        chosen += pool[:n]
    state.rosters[tid] = chosen
    state.lineups[tid] = [[s, None] for s in snap.settings.slots]
    return chosen


# ----------------------------------------------------------------- settings / gating


def test_new_games_carry_ai_v_and_old_saves_do_not():
    s = GameSettings.parse({})
    assert s.ai_v == 1 and s.ai_depth and s.to_dict()["ai_v"] == 1
    legacy = {k: v for k, v in s.to_dict().items() if k != "ai_v"}
    old = GameSettings.from_dict(legacy)
    assert old.ai_v == 0 and not old.ai_depth and "ai_v" not in old.to_dict()
    assert GameSettings.from_dict(s.to_dict()) == s


def test_ai_v0_games_still_use_the_original_waiver_path(monkeypatch):
    called = []
    monkeypatch.setattr(ad, "ai_waiver_claims", lambda *a, **k: called.append(1) or [])
    import modules.sim.game_engine as eng
    monkeypatch.setattr(eng, "ai_waiver_claims", ad.ai_waiver_claims)
    _play(V4_ID)  # builds with ai_v 0 settings
    assert not called


def test_ai_v0_game_replays_identically_and_ai_v1_is_pinned(monkeypatch):
    *_, digests0 = _play(V4_ID)
    assert digests0 == GOLDEN_AI0_V4_DIGESTS
    # the ai_v 1 game on player-model-4 (a model id pins the player model; the AI generation is the settings)
    monkeypatch.setattr(game_scoring, "default_model", lambda: game_scoring.get_model(V4_ID))
    snap, state, em = drafted(11)
    assert snap.settings.ai_v == 1 and snap.scoring_model == V4_ID
    for _ in range(5):
        advance(em, snap, state, 11)
    assert state.digest() == GOLDEN_AI1_DIGESTS[6]
    snap2, state2, em2 = drafted(11)
    for _ in range(5):
        advance(em2, snap2, state2, 11)
    assert state2.digest() == state.digest()


# ------------------------------------------------------------------ the planning


def test_a_kicker_on_bye_is_covered_before_the_week_is_played():
    snap, state, em = drafted(3)
    tid = ai_team(snap, state)
    state.week = 5
    roster_of(snap, state, tid, {"QB": 2, "RB": 4, "WR": 4, "TE": 2, "K": 1})
    k = next(p for p in state.rosters[tid] if snap.players[p].pos == "K")
    bye = snap.bye_of(k)
    state.week = bye
    ev = Evaluator(snap, state)
    assert any(slot == "K" for _, slot in ad.holes(ev, state.rosters[tid], bye))
    claims = ad.ai_waiver_claims(ev, tid, bye, 3)
    assert claims and snap.players[claims[0]["add"]].pos == "K" and claims[0]["why"] == "bye"
    assert not ev.on_bye(claims[0]["add"], bye)  # the cover actually plays


def test_several_holes_in_one_week_get_several_claims():
    snap, state, em = drafted(4)
    tid = ai_team(snap, state)
    state.week = 6
    roster_of(snap, state, tid, {"QB": 2, "RB": 4, "WR": 4, "TE": 1, "K": 1})
    for p in state.rosters[tid]:
        if snap.players[p].pos in ("TE", "K"):
            state.out[p] = 3
    ev = Evaluator(snap, state)
    claims = ad.ai_waiver_claims(ev, tid, 6, 4)
    assert {snap.players[c["add"]].pos for c in claims} >= {"TE", "K"}
    assert len({c["add"] for c in claims}) == len(claims)


def test_a_free_spot_with_no_backup_is_filled_but_a_position_is_never_hoarded():
    snap, state, em = drafted(5)
    tid = ai_team(snap, state)
    state.week = 3
    roster_of(snap, state, tid, {"QB": 1, "RB": 3, "WR": 4, "TE": 2, "K": 1})
    ev = Evaluator(snap, state)
    claims = ad.ai_waiver_claims(ev, tid, 3, 5)
    assert claims and snap.players[claims[0]["add"]].pos == "QB" and claims[0]["drop"] is None and claims[0]["why"] == "depth"
    # four quarterbacks already: no fifth, whatever his projection
    roster_of(snap, state, tid, {"QB": 4, "RB": 3, "WR": 4, "TE": 2, "K": 1})
    ev = Evaluator(snap, state)
    assert not [c for c in ad.ai_waiver_claims(ev, tid, 3, 5) if snap.players[c["add"]].pos == "QB"]
    counts = Counter(snap.players[p].pos for p in state.rosters[tid])
    assert counts["K"] == 1


def test_a_trade_that_opens_a_hole_is_covered_before_lineups():
    snap, state, em = drafted(6)
    tid = ai_team(snap, state)
    state.week = 4
    roster_of(snap, state, tid, {"QB": 2, "RB": 3, "WR": 3, "TE": 1, "K": 1})
    te = next(p for p in state.rosters[tid] if snap.players[p].pos == "TE")
    state.rosters[tid].remove(te)  # as if a trade just sent him away
    assert ad.holes(Evaluator(snap, state), state.rosters[tid], 4)
    _post_trade_cover(em, snap, state, 6, 4)
    assert not [h for h in ad.holes(Evaluator(snap, state), state.rosters[tid], 4) if h[0] == 4 and h[1] == "TE"]


def test_cut_order_never_offers_this_weeks_starters_or_the_only_kicker():
    snap, state, em = drafted(7)
    tid = ai_team(snap, state)
    ev = Evaluator(snap, state)
    order = ad.cut_order(ev, tid, state.rosters[tid], 1)
    starters = {p for _, p in ev.best_lineup(state.rosters[tid], 1)[0] if p}
    assert order and not (set(order) & starters)
    ks = [p for p in state.rosters[tid] if snap.players[p].pos == "K"]
    if len(ks) == 1:
        assert ks[0] not in order


def test_waiver_feed_says_why():
    snap, state, em = drafted(3)
    tid = ai_team(snap, state)
    pid = pids_at(snap, "K")[0]
    text = _tx_text(snap, {"type": "waiver", "team": tid, "add": pid, "drop": None, "why": "bye"})[1]
    assert "to cover a bye" in text
    assert "cover" not in _tx_text(snap, {"type": "waiver", "team": tid, "add": pid, "drop": None})[1]


def test_planning_is_deterministic_and_one_claim_per_free_agent():
    a = drafted(8)
    b = drafted(8)
    for snap, state, em in (a, b):
        for _ in range(4):
            advance(em, snap, state, 8)
    assert a[1].digest() == b[1].digest()
    adds = [t["add"] for t in a[1].transactions if t["type"] == "waiver"]
    # nobody is added twice in the same week
    per_week = Counter((t["week"], t["add"]) for t in a[1].transactions if t["type"] == "waiver")
    assert max(per_week.values()) == 1 and adds


# ----------------------------------------------------------------- harness numbers


def test_depth_planning_beats_the_old_ai_on_holes_and_cover_and_does_not_hoard():
    rows = dataset.load_panel()
    pool, byes = tail_report.pool_from_panel(rows)
    meters = {}
    for v in (0, 1):
        m = ai_report.Meter()
        for seed in (1, 2, 3):
            ai_report.play_redraft(pool, byes, V4_ID, seed, v, m)
        meters[v] = ai_report.summarize(m)
    old, new = meters[0], meters[1]
    assert new["empty_slot_rate"] < 0.6 * old["empty_slot_rate"]
    assert new["team_weeks_with_empty_slot"] < 0.5 * old["team_weeks_with_empty_slot"]
    assert new["depth_cover_rate"] > old["depth_cover_rate"] + 0.08
    assert new["hoard_team_weeks"] <= old["hoard_team_weeks"]
    assert new["empty_slot_rate"] < 0.004 and new["pos_count_max"]["QB"] <= 5 and new["pos_count_max"]["K"] <= 3
    assert 2.0 < new["adds_per_team_season"] < 12.0 and new["pingpong_adds"] <= old["pingpong_adds"] + 6
