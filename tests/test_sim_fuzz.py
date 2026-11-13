"""User-flow fuzzer for the GM game API: random legal and illegal command sequences against an in-memory game.

Asserts, after every request and every state change: no 5xx and a JSON body; no illegal state (roster limits, one owner per player,
legal lineups, IR/taxi capacity, pick conservation, asset conservation across trades); retries do not double-apply; replay from event 0
equals the live (checkpointed) state; and a stuck user always has a way out (over the roster limit => a cut works).

    python -m tests.test_sim_fuzz --seeds 40 --steps 400            # the deep run (the pytest below is a short smoke of the same thing)
"""

from __future__ import annotations

import argparse
import collections
import json
import sys

import numpy as np
import pytest
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from modules.sim import api as sim_api
from modules.sim import game_api
from modules.sim.game_store import GameStore
from modules.sim.game_types import slot_positions
from modules.sim.inputs import PlayerPool
from modules.sim.store import InMemoryBackend
from modules.sim.synthetic import build_synthetic_pool

ROWS, BYES = build_synthetic_pool(7)
UID = "pro"


class PoolInputs:
    def player_pool(self, scoring):
        return PlayerPool(ROWS, BYES)


def make_client():
    backend = InMemoryBackend()

    def require_user(authorization: str | None = Header(default=None)):
        if not authorization:
            raise HTTPException(status_code=401, detail="no")
        return {"id": authorization, "_access_token": "tok"}

    app = FastAPI()
    sim_api.mount(app, sim_api.SimApiDeps(
        require_user=require_user, is_pro=lambda u: True, sleeper_username=lambda u: "",
        backend_for=lambda u: backend, inputs=PoolInputs()), environ={"SIM_ENABLED": "1"})
    return TestClient(app, raise_server_exceptions=False), backend


class Fuzz:
    def __init__(self, seed: int, settings: dict | None = None) -> None:
        game_api.clear_pool_cache()
        self.rng = np.random.default_rng(seed)
        self.client, self.backend = make_client()
        self.store = GameStore(self.backend)
        self.violations: list[str] = []
        self.reasons: collections.Counter = collections.Counter()
        self.calls = 0
        r = self.rng
        s = settings or {
            "teams": int(r.choice([8, 10, 12, 14])), "mode": str(r.choice(["redraft", "dynasty"])), "superflex": bool(r.random() < 0.25),
            "include_def": bool(r.random() < 0.3), "include_k": bool(r.random() < 0.8), "scoring": str(r.choice(["ppr", "half", "std"])),
            "user_slot": int(r.integers(1, 9)), "difficulty": str(r.choice(["easy", "normal", "hard"])),
            "bench": int(r.choice([4, 6, 10])), "ir_slots": int(r.choice([0, 1, 4])), "tiebreaker": str(r.choice(["points_for", "head_to_head"])),
            "te_premium": float(r.choice([0.0, 0.5, 1.0])), "auto_lineup": bool(r.random() < 0.25),
        }
        if s["mode"] == "dynasty":
            s.update(seasons=int(r.choice([3, 4])), rookie_rounds=int(r.choice([2, 3, 5])), taxi_slots=int(r.choice([0, 2, 8])), taxi_years=int(r.choice([1, 2, 4])))
        self.settings = s
        res = self.client.post("/v1/sim/games", json=s, headers={"Authorization": UID})
        if res.status_code != 200 or not res.json().get("game"):
            raise AssertionError(f"create failed {res.status_code} {res.text[:200]} {s}")
        self.gid = res.json()["game"]["id"]

    # ------------------------------------------------------------ plumbing
    def req(self, method: str, path: str, body=None, tag: str = ""):
        self.calls += 1
        res = self.client.request(method, f"/v1/sim/games/{self.gid}{path}", json=body, headers={"Authorization": UID})
        tag = tag or f"{method} {path.split('?')[0]}"
        if res.status_code >= 500:
            self.violations.append(f"5xx {res.status_code} {tag} {body} :: {res.text[:200]}")
            return res, {}
        try:
            data = res.json()
        except ValueError:
            self.violations.append(f"non-json {tag} {res.status_code}")
            return res, {}
        if res.status_code == 200 and isinstance(data, dict) and data.get("reason"):
            self.reasons[(tag, data["reason"])] += 1
        elif res.status_code != 200:
            self.reasons[(tag, res.status_code)] += 1
        return res, data

    def load(self):
        row = self.store.get_game(UID, self.gid)
        snap, state = self.store.load_game(UID, self.gid, row)
        return snap.season_view(state.view_no), state

    # ----------------------------------------------------------- invariants
    def check(self, where: str) -> None:
        snap, state = self.load()
        S = snap.settings
        bad = self.violations.append
        owners: dict[str, str] = {}
        for tid in snap.tids:
            squads = {"roster": state.rosters[tid], "ir": state.ir[tid], "taxi": state.taxi[tid]}
            for name, pids in squads.items():
                for p in pids:
                    if p in owners:
                        bad(f"{where}: {p} owned twice ({owners[p]} and {tid}/{name})")
                    owners[p] = tid
                    if p not in snap.players:
                        bad(f"{where}: {tid}/{name} holds unknown player {p}")
            if len(state.ir[tid]) > S.ir_slots and S.reserves:
                bad(f"{where}: {tid} IR over capacity")
            if len(state.taxi[tid]) > S.taxi_slots and S.reserves:
                bad(f"{where}: {tid} taxi over capacity")
            mid_offseason = state.status == "offseason" and (state.offseason or {}).get("stage") in ("review", "rookie_draft")
            if not snap.team(tid).is_user and len(state.rosters[tid]) > S.roster_limit and not mid_offseason:
                bad(f"{where}: AI team {tid} over the roster limit ({len(state.rosters[tid])})")
            lineup = state.lineups.get(tid, [])
            seen = set()
            for slot, pid in lineup:
                if pid is None:
                    continue
                if pid in seen:
                    bad(f"{where}: {tid} lineup repeats {pid}")
                seen.add(pid)
                if pid not in state.rosters[tid]:
                    bad(f"{where}: {tid} lineup holds {pid} who is not on his roster")
                elif snap.players[pid].pos not in slot_positions(slot):
                    bad(f"{where}: {tid} {pid} ({snap.players[pid].pos}) in a {slot} slot")
        if state.status in ("in_season", "playoffs") and len(state.rosters[snap.user_team.tid]) > S.roster_limit + 6:
            bad(f"{where}: user roster absurdly over the limit")
        if S.dynasty:
            held = set(state.pick_owner)
            spent = {s["pick"] for s in state.spent_picks}
            if held & spent or (held | spent) != set(state.created_picks) or len(state.created_picks) != len(set(state.created_picks)):
                bad(f"{where}: pick ledger broken (held {len(held)} spent {len(spent)} created {len(state.created_picks)})")
            for pk, tid in state.pick_owner.items():
                if tid not in snap.tids:
                    bad(f"{where}: pick {pk} owned by unknown team {tid}")
        for pid, w in state.out.items():
            if w < 0:
                bad(f"{where}: negative out weeks for {pid}")
        if not (0 <= state.week <= S.total_weeks + 1):
            bad(f"{where}: week {state.week} out of range")

    def check_replay(self, where: str) -> None:
        row = self.store.get_game(UID, self.gid)
        snap, _ = self.store.load_game(UID, self.gid, row)
        a = self.store.load_state(UID, self.gid, snap, use_checkpoint=True)
        b = self.store.load_state(UID, self.gid, snap, use_checkpoint=False)
        if a.digest() != b.digest():
            self.violations.append(f"{where}: resumed state != replayed state")

    # ------------------------------------------------------------- the ops
    def pick(self, seq):
        seq = list(seq)
        return seq[int(self.rng.integers(0, len(seq)))] if seq else None

    def junk_id(self):
        return self.pick(["nope", "", "0", "pick:1999:1:1", "g99999", "R2030-999", "DEF-ZZZ", "x" * 80])

    def op_views(self, *_):
        for path in ("", "/home", "/lineup", "/league", "/league/rosters", "/inbox", "/picks", "/dynasty", "/offseason", "/players?pos=RB&sort=value",
                     "/players?status=available&page=2", "/sim-to/options"):
            res, _ = self.req("GET", path)
            if res.status_code not in (200,):
                self.violations.append(f"GET {path} -> {res.status_code}")
        snap, state = self.load()
        pid = self.pick(snap.pids)
        if pid:
            self.req("GET", f"/players/{pid}")
            self.req("GET", f"/players/{pid}/history")
        tid = self.pick(snap.tids)
        self.req("GET", f"/teams/{tid}")
        self.req("GET", f"/teams/{tid}/history")
        self.req("GET", "/players/nope")
        self.req("GET", "/teams/zzz")
        self.check_block()

    def op_draft(self, snap, state):
        r = self.rng.random()
        if r < 0.5:
            owned = state.owner_map()
            pid = self.pick(p for p in snap.pids if p not in owned) if r < 0.45 else self.junk_id()
            body = {"player_id": pid}
            if self.rng.random() < 0.3:
                body["pick_no"] = int(self.rng.integers(0, state.pick_index + 4))
            self.req("POST", "/draft/pick", body)
        elif r < 0.6:
            self.req("PUT", "/draft/queue", {"player_ids": [self.pick(snap.pids) for _ in range(int(self.rng.integers(0, 6)))]})
        elif r < 0.7:
            self.req("POST", "/draft/auto")
        else:
            self.req("GET", "/draft")

    def op_lineup(self, snap, state):
        user = snap.user_team.tid
        roster = list(state.rosters[user])
        slots = [{"slot": s, "player_id": self.pick(roster + [None, self.junk_id()] if self.rng.random() < 0.4 else roster + [None])} for s in snap.settings.slots]
        self.req("PUT", "/lineup", {"slots": slots})
        if self.rng.random() < 0.3:
            self.req("POST", "/lineup/auto")

    def op_wire(self, snap, state):
        user = snap.user_team.tid
        owned = state.owner_map()
        free = [p for p in snap.pids if p not in owned]
        r = self.rng.random()
        if r < 0.55:
            add = self.pick(free) if self.rng.random() < 0.85 else self.junk_id()
            drop = self.pick(state.rosters[user] + [None, None]) if self.rng.random() < 0.8 else self.junk_id()
            slot = self.pick([None, None, *snap.settings.slots, "ZZ"])
            self.req("POST", "/waivers", {"add": add, "drop": drop, "start_slot": slot})
        elif r < 0.7 and state.claims:
            self.req("DELETE", f"/waivers/{self.pick(c['id'] for c in state.claims)}")
        elif r < 0.75:
            self.req("DELETE", "/waivers/nope")
        else:
            self.req("POST", "/cut", {"player_id": self.pick(state.rosters[user]) if self.rng.random() < 0.9 else self.junk_id()})

    def op_reserve(self, snap, state):
        user = snap.user_team.tid
        pool = state.rosters[user] + state.ir[user] + state.taxi[user]
        self.req("POST", "/roster/move", {"player_id": self.pick(pool) or "x", "to": self.pick(["ir", "taxi", "roster", "bench", "zz"])})

    def op_trade(self, snap, state):
        user = snap.user_team.tid
        partner = self.pick([t for t in snap.tids if t != user] + ([user, "99"] if self.rng.random() < 0.1 else []))
        mine = state.rosters[user] + [p for p, o in state.pick_owner.items() if o == user]
        theirs = (state.rosters.get(partner, []) if partner in state.rosters else []) + [p for p, o in state.pick_owner.items() if o == partner]
        give = [self.pick(mine) for _ in range(int(self.rng.integers(0, 4)))]
        get = [self.pick(theirs) for _ in range(int(self.rng.integers(0, 4)))]
        if self.rng.random() < 0.1:
            give.append(self.junk_id())
        give, get = [g for g in give if g], [g for g in get if g]
        if self.rng.random() < 0.4:
            self.req("POST", "/trades/preview", {"partner": partner, "give": give, "get": get})
            return
        res, data = self.req("POST", "/trades", {"partner": partner, "give": give, "get": get})
        if data.get("executed"):
            s2, st2 = self.load()
            own = {p: t for t, v in st2.rosters.items() for p in v}
            own.update({p: t for t, v in st2.ir.items() for p in v})
            own.update({p: t for t, v in st2.taxi.items() for p in v})
            own.update(st2.pick_owner)
            for g in give:
                if own.get(g) not in (partner, None):  # None: the partner cut him to get under the roster limit
                    self.violations.append(f"traded-away asset {g} is with {own.get(g)}, not {partner}")
            for g in get:
                if own.get(g) != snap.user_team.tid:
                    self.violations.append(f"received asset {g} is with {own.get(g)}, not the user")
            res2, data2 = self.req("POST", "/trades", {"partner": partner, "give": give, "get": get}, tag="POST /trades (retry)")
            if data2.get("executed"):
                self.violations.append("a retried trade executed twice")

    def op_block(self, snap, state):
        user = snap.user_team.tid
        mine = state.rosters[user] + state.ir[user] + state.taxi[user] + [p for p, o in state.pick_owner.items() if o == user]
        if self.rng.random() < 0.2:
            self.check_block()
            return
        asset = self.pick(mine) if self.rng.random() < 0.85 else self.junk_id()
        self.req("PUT", "/block", {"asset_id": asset or "x", "on": bool(self.rng.random() < 0.7),
                                   "looking_for": self.pick([None, None, "QB", "RB", "WR", "TE", "K", "zz"])})

    def check_block(self):
        """The block view only ever shows assets the user still holds (a stale entry in the state is filtered, by design) and AI items its owner holds."""

        res, data = self.req("GET", "/block")
        if not data.get("enabled"):
            return
        snap, state = self.load()
        user = snap.user_team.tid
        held = set(state.rosters[user]) | set(state.ir[user]) | set(state.taxi[user]) | {p for p, o in state.pick_owner.items() if o == user}
        for m in data["mine"]:
            if m["asset"]["id"] not in held:
                self.violations.append(f"block view shows {m['asset']['id']} which the user does not hold")
        if len(data["mine"]) > data["max_items"]:
            self.violations.append("the user's block is over its limit")
        for b in data["league"]:
            tid = b["team_id"]
            for item in b["items"]:
                aid = item["asset"]["id"]
                if aid in snap.players and aid not in (set(state.rosters[tid]) | set(state.ir[tid]) | set(state.taxi[tid])):
                    self.violations.append(f"AI team {tid} shops {aid} which it does not hold")
                if aid not in snap.players and state.pick_owner.get(aid) != tid:
                    self.violations.append(f"AI team {tid} shops pick {aid} which it does not hold")

    def op_inbox(self, snap, state):
        if state.offers and self.rng.random() < 0.8:
            offer = self.pick(state.offers)
            self.req("POST", f"/inbox/{offer['id']}/respond", {"action": self.pick(["accept", "decline", "counter", "zz"])})
        else:
            self.req("POST", "/inbox/nope/respond", {"action": "accept"})

    def op_advance(self, snap, state):
        r = self.rng.random()
        if r < 0.55:
            res, data = self.req("POST", "/advance")
        elif r < 0.7:
            week = state.week
            res, data = self.req("POST", "/advance", {"week": week})
            if data.get("recap") is not None and not data.get("replayed") and False:
                pass
        elif r < 0.8:
            self.req("POST", "/advance", {"week": state.week + 3})
            return
        else:
            opts = self.req("GET", "/sim-to/options")[1].get("options") or []
            if opts:
                o = self.pick(opts)
                self.req("POST", "/sim-to", {"target": o["id"], "weeks": int(o.get("weeks", 1)), "auto_set": bool(self.rng.random() < 0.5), "force_first": bool(self.rng.random() < 0.3)})
            else:
                self.req("POST", "/sim-to", {"target": "weeks", "weeks": 1})
            return
        # a stuck user must have a way out: over the limit => a cut works
        if data.get("reason") == "roster_over_limit":
            s2, st2 = self.load()
            user = s2.user_team.tid
            over = len(st2.rosters[user]) - s2.settings.roster_limit
            if over > 0:
                worst = self.pick(st2.rosters[user])
                res2, d2 = self.req("POST", "/cut", {"player_id": worst}, tag="POST /cut (to get under the limit)")
                if d2.get("reason"):
                    self.violations.append(f"dead end: over the limit by {over} and the cut was refused: {d2.get('reason')}")

    def op_history(self, snap, state):
        r = self.rng.random()
        if r < 0.4:
            self.req("POST", "/revert-week")
        else:
            seq = int(self.pick([state.boundary_seq, max(1, state.seq - 3), 0, 1, state.seq + 5, 99999]))
            self.req("POST", "/undo-sim", {"from_seq": seq})

    def op_offseason(self, snap, state):
        off = state.offseason or {}
        r = self.rng.random()
        if r < 0.2:
            self.req("POST", "/offseason/rookie-draft/start")
        elif r < 0.55:
            avail = [p for p, pl in snap.players.items() if pl.extra.get("is_rookie") and p not in state.owner_map()]
            self.req("POST", "/offseason/rookie-draft/pick", {"player_id": self.pick(avail) if avail and r < 0.5 else self.junk_id()})
        elif r < 0.65:
            self.req("POST", "/offseason/rookie-draft/auto")
        elif r < 0.8:
            user = snap.user_team.tid
            if state.rosters[user]:
                self.req("POST", "/cut", {"player_id": self.pick(state.rosters[user])})
        else:
            res, data = self.req("POST", "/offseason/start-season")
            if data.get("reason") == "roster_over_limit":
                user = snap.user_team.tid
                if len(state.rosters[user]) > snap.settings.roster_limit:
                    res2, d2 = self.req("POST", "/cut", {"player_id": self.pick(state.rosters[user])}, tag="POST /cut (offseason)")
                    if d2.get("reason"):
                        self.violations.append(f"dead end in the offseason: cut refused: {d2.get('reason')}")

    # ------------------------------------------------------------------ run
    def step(self):
        snap, state = self.load()
        status = state.status
        if status == "drafting":
            self.op_draft(snap, state)
            return
        if status == "complete":
            self.op_views()
            return
        if status == "offseason":
            (self.op_offseason if self.rng.random() < 0.85 else self.op_trade)(snap, state) if True else None
            return
        ops = [(self.op_advance, 22), (self.op_lineup, 10), (self.op_wire, 18), (self.op_trade, 14), (self.op_inbox, 6), (self.op_block, 6),
               (self.op_reserve, 8), (self.op_history, 3), (self.op_views, 3)]
        w = np.array([x[1] for x in ops], dtype=float)
        fn = ops[int(self.rng.choice(len(ops), p=w / w.sum()))][0]
        fn(snap, state)

    def run(self, steps: int) -> "Fuzz":
        for i in range(steps):
            self.step()
            if i % 7 == 0:
                self.check(f"step {i}")
            if i % 40 == 39:
                self.check_replay(f"step {i}")
            if len(self.violations) > 25:
                break
        self.check("end")
        self.check_replay("end")
        return self


def run_many(seeds, steps):
    out = []
    reasons: collections.Counter = collections.Counter()
    for seed in seeds:
        try:
            f = Fuzz(seed).run(steps)
            out.append((seed, f.settings, f.violations))
            reasons.update(f.reasons)
        except Exception as exc:  # noqa: BLE001 - a crash in the harness itself is a finding too
            import traceback

            out.append((seed, {}, [f"harness exception {type(exc).__name__}: {exc}", traceback.format_exc()[-1200:]]))
    return out, reasons


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_fuzzed_command_sequences_never_break_the_game(seed):
    f = Fuzz(seed).run(120)
    assert not f.violations, f.violations[:5]


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--first", type=int, default=100)
    ap.add_argument("--steps", type=int, default=300)
    args = ap.parse_args(argv)
    results, reasons = run_many(range(args.first, args.first + args.seeds), args.steps)
    bad = [(s, st, v) for s, st, v in results if v]
    print(json.dumps({"games": len(results), "games_with_violations": len(bad)}))
    for s, st, v in bad:
        print("SEED", s, st)
        for line in v[:6]:
            print("   ", line)
    print("most common refusals:")
    for (tag, why), n in reasons.most_common(25):
        print(f"  {n:5d} {tag} -> {why}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()


def test_revert_week_after_a_sim_to_that_stopped_at_once_keeps_the_log_and_state_consistent():
    """Regression (found by this fuzzer, seed 101): a 'sim-to' that plays nothing still writes a marker event and a checkpoint past the
    week boundary; 'revert-week' then deleted the events but left that checkpoint, so the live state described events that no longer
    existed (resume != replay, and the next commit left a gap in the log)."""
    f = Fuzz(101).run(60)
    assert not f.violations, f.violations[:5]
