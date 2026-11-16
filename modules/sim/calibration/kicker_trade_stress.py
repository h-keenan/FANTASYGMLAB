"""Randomized stress harness for kickers and defenses in Fantasy Sim trades (kd_v), validate AND execute paths.

Plays whole dynasties (up to 20 seasons) and redrafts under many seeds and rule mixes (kd_v / limit_v / econ_v on and off, K and DEF in the
lineup or not, superflex, IR / taxi), and at every week and every offseason throws trade attempts at the desk, K/DEF-heavy ones included
(K for K, K for picks, K + picks for a star, a second K asked for, three-team style chains, injured / retired / bye-week kickers, over-limit
rosters). Counters the AI hands back are sent too, exactly as the "Take their counter" button does.

Asserts after every attempt: no exception other than a documented rule error; preview is read-only and deterministic; a counter is a deal
the user can actually send (it validates and fits the roster); after a trade no K/DEF count is pushed above one by the trade itself, every
player has one owner, AI rosters are within the limit, picks are conserved, lineups only name rostered players; and at the end the event
log folds back to the identical digest (and, for redrafts, replays command by command in strict mode). A save without kd_v must refuse
every K/DEF asset with the one documented error and never behave differently.

    python -m modules.sim.calibration.kicker_trade_stress --seeds 40 --seasons 20
"""

from __future__ import annotations

import argparse
import collections
import sys
import traceback
from dataclasses import replace
from typing import Any

import numpy as np

from modules.sim import game_actions as act
from modules.sim import game_dynasty as dyn
from modules.sim.game_ai import TradeDesk, validate_offer
from modules.sim.game_draft import DraftContext, auto_for_user, run_ai_picks
from modules.sim.game_engine import advance, finish_draft
from modules.sim.game_eval import USER_PARAMS, Evaluator
from modules.sim.game_result import replay_game
from modules.sim.game_setup import build_snapshot
from modules.sim.game_state import Emitter, GameState, fold
from modules.sim.game_types import SINGLETON_POSITIONS, GameError, GameSettings
from modules.sim.synthetic import build_synthetic_pool
from modules.sim.types import is_pick_id

ROWS, BYES = build_synthetic_pool(7)
MODEL = "player_model-player-model-5"
OLD_FLAGS = ("hint_v", "limit_v", "kd_v", "world_v", "aging_v", "names_v", "econ_v", "pos_v")
RULE_CODES = {"singleton_limit", "roster_full", "picks_locked", "wrong_phase", "trades_closed", "trade_deadline_passed", "partner_trade_limit", "duplicate_offer"}


def make_settings(rng: np.random.Generator, *, kd_v: int | None = None, seasons: int = 5, dynasty: bool = True, flags: dict[str, int] | None = None) -> GameSettings:
    raw: dict[str, Any] = {
        "teams": int(rng.choice([8, 10, 12])), "user_slot": int(rng.integers(1, 7)), "superflex": bool(rng.random() < 0.3),
        "include_def": bool(rng.random() < 0.5), "include_k": bool(rng.random() < 0.9), "scoring": str(rng.choice(["ppr", "half", "std"])),
        "difficulty": str(rng.choice(["easy", "normal", "hard"])), "bench": int(rng.choice([4, 6, 10])), "ir_slots": int(rng.choice([0, 2, 4])),
    }
    if dynasty:
        raw.update(mode="dynasty", seasons=seasons, start_year=2026, rookie_rounds=int(rng.choice([2, 3])), taxi_slots=int(rng.choice([0, 3])), taxi_years=2)
    s = GameSettings.parse(raw)
    d = s.to_dict()
    for f in OLD_FLAGS:  # start from a save made before every gate, then switch on the ones this run is about
        d.pop(f, None)
    for f, v in (flags or {}).items():
        d[f] = v
    if kd_v:
        d["kd_v"] = kd_v
    return GameSettings.from_dict(d)


class Stress:
    def __init__(self, seed: int, settings: GameSettings, rng: np.random.Generator, attempts: int = 6, upgrade_at: int | None = None, label: str = "") -> None:
        self.seed, self.rng, self.attempts, self.label, self.upgrade_at = seed, rng, attempts, label, upgrade_at
        self.root = build_snapshot(ROWS, BYES, settings, seed, scoring_model=MODEL)
        self.state = GameState(self.root)
        self.em = Emitter(self.state, self.root)
        run_ai_picks(DraftContext(self.root, self.state), self.em, seed)
        auto_for_user(DraftContext(self.root, self.state), self.em, seed)
        finish_draft(self.em, self.root, self.state, seed)
        self.failures: list[str] = []
        self.codes: collections.Counter = collections.Counter()
        self.stats: collections.Counter = collections.Counter()
        self.errtext: dict[str, str] = {}
        self.picks0 = None

    # ------------------------------------------------------------ plumbing
    def view(self):
        snap = self.root.under(self.state.rules).season_view(self.state.view_no)
        self.em.snap = snap
        return snap

    def seed_now(self) -> int:
        return dyn.season_seed(self.seed, self.state.view_no)

    def fail(self, what: str, detail: str = "") -> None:
        msg = f"[{self.label} seed={self.seed} s{self.state.season_no} w{self.state.week} {self.state.status}] {what} {detail}"
        if msg not in self.failures:
            self.failures.append(msg)

    # --------------------------------------------------------- invariants
    def invariants(self, snap, when: str, *, trade: dict | None = None, before_counts: dict | None = None) -> None:
        st = self.state
        seen: dict[str, str] = {}
        for tid in snap.tids:
            for pid in st.holdings(tid):
                if pid in seen:
                    self.fail("DUPLICATE_OWNER", f"{pid} on {seen[pid]} and {tid} ({when})")
                seen[pid] = tid
            for slot, pid in st.lineups.get(tid, ()):
                if pid and pid not in st.rosters[tid]:
                    self.fail("LINEUP_NAMES_NON_ROSTER", f"{tid} {slot}:{pid} ({when})")
            if not snap.team(tid).is_user and len(st.rosters[tid]) > snap.settings.roster_limit and st.status in ("in_season", "playoffs"):
                self.fail("AI_OVER_LIMIT", f"{tid} {len(st.rosters[tid])}/{snap.settings.roster_limit} ({when})")
        if trade is not None and before_counts is not None:
            for tid in (trade["team_a"], trade["team_b"]):
                for pos in SINGLETON_POSITIONS:
                    n = sum(1 for p in st.holdings(tid) if snap.players[p].pos == pos)
                    if n > 1 and n > before_counts.get((tid, pos), 0):
                        self.fail("TRADE_CAUSED_SECOND_" + pos, f"{tid} now holds {n} ({when}) give={trade['give']} get={trade['get']}")

    def counts(self, snap) -> dict:
        return {(tid, pos): sum(1 for p in self.state.holdings(tid) if snap.players[p].pos == pos) for tid in snap.tids for pos in SINGLETON_POSITIONS}

    # ------------------------------------------------------------- offers
    def random_offer(self, snap) -> tuple[str, list[str], list[str]]:
        r, st = self.rng, self.state
        user = snap.user_team.tid
        partner = str(r.choice([t for t in snap.tids if t != user]))
        mine, theirs = st.holdings(user), st.holdings(partner)
        if not mine or not theirs:
            self.stats["empty_roster_skip"] += 1  # the random trader dumped every player for picks: a legal (if silly) dynasty, nothing to offer
            return partner, [], []
        mine_k = [p for p in mine if snap.players[p].pos in SINGLETON_POSITIONS]
        their_k = [p for p in theirs if snap.players[p].pos in SINGLETON_POSITIONS]
        my_picks = [p for p in st.picks_of(user)] if snap.settings.policy.dynasty else []
        their_picks = [p for p in st.picks_of(partner)] if snap.settings.policy.dynasty else []
        side_max = snap.settings.policy.max_trade_side

        def pick_side(pool, kpool, picks):
            n = int(r.integers(1, side_max + 1))
            out: list[str] = []
            mode = r.random()
            if kpool and mode < 0.55:
                out.append(str(r.choice(kpool)))
                if mode < 0.12 and len(kpool) > 1:
                    out.append(str(r.choice(kpool)))  # two K/DEF at once
            rest = [p for p in pool if p not in out and p not in kpool]
            if picks and r.random() < 0.35:
                out.append(str(r.choice(picks)))
            while len(out) < n and rest:
                out.append(str(r.choice(rest)))
                rest = [p for p in rest if p not in out]
            return list(dict.fromkeys(out))[:side_max] or [str(r.choice(pool))]

        give = pick_side(mine, mine_k, my_picks)
        get = pick_side(theirs, their_k, their_picks)
        if r.random() < 0.5:  # the one legal shape for a K/DEF deal: swap one for one (same position), with up to two extras each way
            pos = str(r.choice(list(SINGLETON_POSITIONS)))
            a = [p for p in mine_k if snap.players[p].pos == pos]
            b = [p for p in their_k if snap.players[p].pos == pos]
            if a and b:
                give, get = [a[0]], [b[0]]
                for side, pool, picks in ((give, mine, my_picks), (get, theirs, their_picks)):
                    for _ in range(int(r.integers(0, min(3, side_max)))):
                        cand = [p for p in pool if p not in side and snap.players[p].pos not in SINGLETON_POSITIONS] + (picks if r.random() < 0.3 else [])
                        if cand and len(side) < side_max:
                            side.append(str(r.choice(cand)))
        if r.random() < 0.03:  # shape errors: a stranger's player, a duplicate, an unknown id
            give = [str(r.choice(theirs))] if r.random() < 0.5 else give + give[:1]
        return partner, give, get

    def expected_old_refusal(self, snap, give, get) -> bool:
        return any(p in snap.players and snap.players[p].pos in snap.settings.non_tradable for p in (*give, *get) if not is_pick_id(p))

    def attempt(self) -> None:
        snap = self.view()
        st = self.state
        user = snap.user_team.tid
        partner, give, get = self.random_offer(snap)
        if not give or not get:
            return
        desk = TradeDesk(Evaluator(snap, st), self.seed_now())
        digest0 = st.digest()
        seq0 = st.seq
        self.stats["attempts"] += 1
        try:
            verdict = act.preview_trade(desk, partner, give, get)
        except (ValueError, GameError) as exc:
            code = getattr(exc, "code", "ValueError")
            self.codes[code] += 1
            self.errtext.setdefault(code + ":" + str(exc)[:70], str(exc))
            if isinstance(exc, GameError) and code not in RULE_CODES:
                self.fail("UNEXPECTED_GAMEERROR", f"{code}: {exc}")
            if snap.settings.non_tradable and not isinstance(exc, GameError):
                pass
            if st.digest() != digest0 or st.seq != seq0:
                self.fail("PREVIEW_MUTATED_ON_ERROR")
            if self.expected_old_refusal(snap, give, get) and snap.settings.non_tradable:
                if not (isinstance(exc, ValueError) and not isinstance(exc, GameError)) and code != "roster_full":
                    self.fail("OLD_SAVE_WRONG_REFUSAL", f"{code}: {exc}")
            return
        except Exception:
            self.fail("PREVIEW_CRASH", f"partner={partner} give={give} get={get}\n{traceback.format_exc(limit=6)}")
            return
        if self.expected_old_refusal(snap, give, get) and snap.settings.non_tradable:
            self.fail("OLD_SAVE_ACCEPTED_KD", f"give={give} get={get}")
        if st.digest() != digest0 or st.seq != seq0:
            self.fail("PREVIEW_MUTATED")
        again = act.preview_trade(desk, partner, give, get)
        if again.to_dict() != verdict.to_dict():
            self.fail("PREVIEW_NOT_DETERMINISTIC")
        self.stats[verdict.decision] += 1
        if any(snap.players[p].pos in SINGLETON_POSITIONS for p in (*give, *get) if not is_pick_id(p)):
            self.stats["kd_" + verdict.decision] += 1
        sendable_give, sendable_get = give, get
        if verdict.decision == "counter":
            c = verdict.counter or {}
            cg, cr = list(c["give"]), list(c["get"])
            try:  # exactly what "Take their counter" does
                validate_offer(snap, st, partner, cg, cr)
                act.check_roster_room(snap, st, user, cg, cr)
            except (ValueError, GameError) as exc:
                code = getattr(exc, "code", "ValueError")
                self.fail("COUNTER_NOT_SENDABLE", f"{code}: {exc} | offer give={give} get={get} -> counter give={cg} get={cr}")
                self.errtext.setdefault("counter:" + code, str(exc))
                return
            if not desk.ai_accepts(partner, cg, cr)[0]:
                self.fail("COUNTER_NOT_ACCEPTED_BY_AI", f"counter give={cg} get={cr}")
            sendable_give, sendable_get = cg, cr
            if any(snap.players[p].pos in SINGLETON_POSITIONS for p in (*cg, *cr) if not is_pick_id(p) and p not in (*give, *get)):
                self.fail("COUNTER_ASKS_FOR_KD", f"counter give={cg} get={cr}")
        if verdict.decision == "accept" or (verdict.decision == "counter" and self.rng.random() < 0.7):
            before = self.counts(snap)
            kd_in = any(snap.players[p].pos in SINGLETON_POSITIONS for p in (*sendable_give, *sendable_get) if not is_pick_id(p))
            if kd_in:  # pricing probe: what the AI gives up in the league's neutral lens when a K/DEF is in the deal
                ev0 = Evaluator(snap, st)
                loss = sum(ev0.worth(USER_PARAMS, p) for p in sendable_get) - sum(ev0.worth(USER_PARAMS, p) for p in sendable_give)
                self.stats["kd_ai_loss_max_x10_e%d" % snap.settings.econ_v] = max(self.stats["kd_ai_loss_max_x10_e%d" % snap.settings.econ_v], int(loss * 10))
            picks_before = sorted(p for t in snap.tids for p in st.picks_of(t)) if snap.settings.policy.dynasty else []
            try:
                v2, trade = act.send_trade(self.em, desk, partner, sendable_give, sendable_get)
            except (ValueError, GameError) as exc:
                code = getattr(exc, "code", "ValueError")
                if code == "duplicate_offer":
                    return
                self.fail("SEND_FAILED_AFTER_PREVIEW_OK", f"{code}: {exc}")
                return
            except Exception:
                self.fail("SEND_CRASH", f"partner={partner} give={sendable_give} get={sendable_get}\n{traceback.format_exc(limit=6)}")
                return
            if verdict.decision == "accept" and (v2.decision != "accept" or trade is None):
                self.fail("SEND_VERDICT_DISAGREES_WITH_PREVIEW", f"{v2.decision}")
            if trade is not None:
                self.stats["executed"] += 1
                if any(snap.players[p].pos in SINGLETON_POSITIONS for p in (*sendable_give, *sendable_get) if not is_pick_id(p)):
                    self.stats["executed_kd"] += 1
                snap2 = self.view()
                self.invariants(snap2, "after trade", trade=trade, before_counts=before)
                picks_after = sorted(p for t in snap.tids for p in st.picks_of(t)) if snap.settings.policy.dynasty else []
                if picks_before != picks_after:
                    self.fail("PICKS_NOT_CONSERVED")

    # ------------------------------------------------------------- driving
    def cut_user_to_limit(self) -> None:
        snap = self.view()
        user = snap.user_team.tid
        while len(self.state.rosters[user]) > snap.settings.roster_limit:
            ev = Evaluator(snap, self.state)
            pool = list(self.state.rosters[user])
            pid = self.rng.choice(pool) if self.rng.random() < 0.2 else min(pool, key=lambda p: (ev.worth(USER_PARAMS, p), p))
            act.cut_player(self.em, str(pid))

    def round_of_attempts(self, n: int | None = None) -> None:
        for _ in range(self.attempts if n is None else n):
            self.attempt()

    def step_week(self) -> None:
        self.round_of_attempts()
        if self.upgrade_at is not None and self.state.season_no == self.upgrade_at and not self.state.rules and self.state.status == "in_season":
            self.view()
            act.upgrade_realism(self.em)
            self.stats["upgraded"] += 1
        self.cut_user_to_limit()
        snap = self.view()
        try:
            advance(self.em, snap, self.state, self.seed_now())
        except GameError as exc:
            self.fail("ADVANCE_BLOCKED", f"{exc.code}: {exc}")
            raise
        self.invariants(self.view(), "after advance")

    def play(self) -> None:
        guard = 0
        while True:
            guard += 1
            if guard > 4000:
                self.fail("RUNAWAY")
                return
            if self.state.status in ("in_season", "playoffs"):
                self.step_week()
            elif self.state.status == "offseason":
                snap = self.view()
                self.round_of_attempts(self.attempts * 2)  # trade season
                self.cut_user_to_limit()
                sd = self.seed_now()
                dyn.start_rookie_draft(self.em)
                snap = self.view()
                dyn.run_ai_rookie_picks(self.em, sd)
                self.round_of_attempts(self.attempts)  # mid-draft: picks change hands
                dyn.auto_rookie_draft(self.em, sd)
                self.cut_user_to_limit()
                dyn.start_next_season(self.em, sd)
                self.invariants(self.view(), "new season")
            else:
                break
        digest = self.state.digest()
        if fold(self.root, self.em.events).digest() != digest:
            self.fail("FOLD_REPLAY_DIGEST_MISMATCH")
        if not self.root.settings.multi_season:
            try:
                if replay_game(self.root, self.seed, self.em.events, strict=True).digest() != digest:
                    self.fail("STRICT_REPLAY_DIGEST_MISMATCH")
            except Exception as exc:
                self.fail("STRICT_REPLAY_RAISED", f"{type(exc).__name__}: {exc}")


def scenarios(seed: int, seasons: int):
    r = np.random.default_rng(seed)
    dynasty = bool(r.random() < 0.75)
    kd = [None, 1][int(r.integers(0, 2))]
    flags = {"limit_v": int(r.integers(0, 2)), "econ_v": int(r.integers(0, 2)), "hint_v": int(r.integers(0, 2)), "world_v": int(r.integers(0, 2))}
    up = int(r.integers(2, 4)) if (kd is None and dynasty and r.random() < 0.4) else None
    return r, dict(kd_v=kd, flags=flags, dynasty=dynasty, seasons=seasons if dynasty else 1), up


def run_seed(seed: int, seasons: int = 5, attempts: int = 6) -> Stress:
    r, kw, up = scenarios(seed, seasons)
    s = Stress(seed, make_settings(r, **kw), r, attempts=attempts, upgrade_at=up, label=f"kd{kw['kd_v'] or 0} {'dyn' if kw['dynasty'] else 'red'} {kw['flags']}")
    try:
        s.play()
    except Exception:
        s.fail("DRIVER_CRASH", traceback.format_exc(limit=8))
    return s


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--seasons", type=int, default=5)
    ap.add_argument("--attempts", type=int, default=6)
    a = ap.parse_args(argv)
    total: collections.Counter = collections.Counter()
    codes: collections.Counter = collections.Counter()
    texts: dict[str, str] = {}
    bad = 0
    for seed in range(a.start, a.start + a.seeds):
        s = run_seed(seed, a.seasons, a.attempts)
        total.update(s.stats)
        codes.update(s.codes)
        texts.update(s.errtext)
        for f in s.failures:
            bad += 1
            print("FAIL", f)
        print(f"seed {seed}: {dict(s.stats)} failures={len(s.failures)}", flush=True)
    print("TOTAL", dict(total))
    print("ERROR CODES", dict(codes))
    for k, v in sorted(texts.items()):
        print("  ", k, "=>", v)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
