"""League-integrity stress harness: whole Fantasy Sim games under randomized league shapes, rule generations and user behaviour.

Where ``kicker_trade_stress`` hammers the trade desk, this one plays whole leagues (redraft, fresh dynasty up to 20 seasons, league
imports with 4-16 teams and odd playoff fields, mid-season starts) and checks the structural rules a league has to keep, at every
week and every offseason boundary:

* ownership: one owner per player, IR / taxi limits, AI roster limits, lineups only name rostered, position-eligible players once each
* stats: points finite and non-negative, standings arithmetic (games played, wins = losses, points for = points against, head-to-head
  symmetric, streak format), season totals equal the sum of the played games
* schedule: one game per team per week, no self games, opponent / home-away spread
* playoffs: seeds are the top of the standings, byes go to the top seeds, every game is between teams still alive, the higher seed wins a
  tie, one champion per completed season who actually won the final, results labels
* dynasty: pick ledger conserved, every future pick owned exactly once, rookie draft order and picks, retired players gone for good,
  ages move one year a season, rookie ages and contracts (taxi eligibility), pool values finite
* determinism: the event log folds back to the identical digest, a resume from a mid-game checkpoint reaches the same digest, redrafts
  replay command by command in strict mode
* behaviour: random lineups (including empty and ineligible), claims, cuts, IR / taxi moves, trades, block, Sim-to-N-weeks jumps with
  random stop toggles, and a mid-run Realism update

    python -m modules.sim.calibration.league_integrity_stress --seeds 24 --seasons 6 --workers 6
    python -m modules.sim.calibration.league_integrity_stress --seeds 6 --seasons 20 --workers 6 --stats

Pure stdlib + numpy + modules.sim; synthetic player pool only, never data/players.db.
"""

from __future__ import annotations

import argparse
import collections
import math
import multiprocessing as mp
import sys
import traceback
from typing import Any

import numpy as np

from modules.sim import game_actions as act
from modules.sim import game_dynasty as dyn
from modules.sim import game_simto as simto
from modules.sim.game_ai import TradeDesk
from modules.sim.game_draft import DraftContext, auto_for_user, run_ai_picks
from modules.sim.game_engine import advance, bracket_slots, finish_draft, rank_teams, start_from_league
from modules.sim.game_eval import Evaluator
from modules.sim.game_result import replay_game
from modules.sim.game_setup import build_league_snapshot, build_snapshot, league_settings
from modules.sim.game_state import Emitter, GameState, fold
from modules.sim.game_types import (
    SINGLETON_POSITIONS, GameError, GameSettings, ImportedTeam, LeagueImport, RealWeek, slot_positions,
)
from modules.sim.synthetic import build_synthetic_pool
from modules.sim.types import is_pick_id

ROWS, BYES = build_synthetic_pool(7)
MODEL = "player_model-player-model-5"
OLD_FLAGS = ("hint_v", "limit_v", "kd_v", "world_v", "aging_v", "names_v", "econ_v", "ai_v", "block_v")
RULE_CODES = {
    "singleton_limit", "roster_full", "picks_locked", "wrong_phase", "trades_closed", "trade_deadline_passed", "partner_trade_limit",
    "duplicate_offer", "ir_full", "taxi_full", "ir_ineligible", "taxi_ineligible", "reserves_unavailable", "roster_over_limit",
}
SLOT_RANGE = ("QB", "RB", "WR", "TE")


# ----------------------------------------------------------------------------- scenarios


def _imported(rng: np.random.Generator, teams: int, slots: tuple[str, ...], bench: int, *, mid: bool, playoff_teams: int, regular_weeks: int) -> LeagueImport:
    by_pos: dict[str, list[str]] = {}
    for r in sorted(ROWS, key=lambda r: -r["market"]):
        by_pos.setdefault(r["pos"], []).append(r["pid"])
    need = {"QB": 2, "RB": 4, "WR": 4, "TE": 2, "K": 1, "DEF": 1}
    rosters: dict[int, list[str]] = {i: [] for i in range(teams)}
    for pos, count in need.items():
        pool = by_pos.get(pos, [])
        for i in range(teams):
            rosters[i].extend(pool[i * count:(i + 1) * count])
    user = int(rng.integers(0, teams))
    tids = [str(100 + i) for i in range(teams)]
    cur = int(rng.integers(3, max(4, regular_weeks - 2))) if mid else 0
    results: list[RealWeek] = []
    records: dict[str, tuple[int, int, int, float, float]] = {t: (0, 0, 0, 0.0, 0.0) for t in tids}
    sched: list[tuple[tuple[str, str], ...]] = []
    for w in range(1, regular_weeks + 1):
        order = list(rng.permutation(teams))
        sched.append(tuple((tids[order[i]], tids[order[i + 1]]) for i in range(0, teams, 2)))
    if mid:
        for w in range(1, cur):
            games = []
            for a, b in sched[w - 1]:
                x, y = round(float(rng.uniform(60, 150)), 2), round(float(rng.uniform(60, 150)), 2)
                games.append((a, b, x, y))
                ra, rb = records[a], records[b]
                ra_w, rb_w = (1, 0) if x > y else (0, 1)
                records[a] = (ra[0] + ra_w, ra[1] + 1 - ra_w, ra[2], ra[3] + x, ra[4] + y)
                records[b] = (rb[0] + rb_w, rb[1] + 1 - rb_w, rb[2], rb[3] + y, rb[4] + x)
            results.append(RealWeek(week=w, games=tuple(games), points={}))
    return LeagueImport(
        league_id="L1", league_name="Stress League", season="2026",
        teams=tuple(ImportedTeam(tid=tids[i], name=f"Team {i}", owner=f"Owner {i}", is_user=i == user, roster=tuple(rosters[i])) for i in range(teams)),
        slots=slots, bench=bench, scoring_settings={"rec": float(rng.choice([0.0, 0.5, 1.0])), "pass_td": 4.0, "bonus_rec_te": float(rng.choice([0.0, 0.5]))},
        playoff_teams=playoff_teams, current_week=cur, regular_weeks=regular_weeks if mid else 0, trade_deadline=int(rng.integers(cur + 1, regular_weeks + 1)) if mid else 0,
        schedule=tuple(sched) if mid else (), results=tuple(results), records=records if mid else {},
        start_year=2026, rookie_rounds=int(rng.choice([2, 3])),
    )


def make_scenario(seed: int, seasons: int) -> dict[str, Any]:
    """Everything random about one run, as plain data (so a failing seed prints a reproducible shape)."""

    r = np.random.default_rng(seed * 7919 + 11)
    kind = str(r.choice(["redraft", "dynasty", "dynasty", "league", "mid"], p=[0.2, 0.35, 0.15, 0.15, 0.15]))
    sc: dict[str, Any] = {"kind": kind, "seed": seed}
    sc["flags"] = {f: int(r.integers(0, 2)) for f in ("hint_v", "limit_v", "kd_v", "world_v", "econ_v", "ai_v", "block_v")}
    sc["aging_v"] = int(r.integers(0, 2))
    sc["upgrade_at"] = int(r.integers(1, 4)) if r.random() < 0.35 else None
    sc["raw"] = {
        "teams": int(r.choice([8, 10, 12, 14])), "user_slot": 1, "superflex": bool(r.random() < 0.3), "include_def": bool(r.random() < 0.5),
        "include_k": bool(r.random() < 0.85), "scoring": str(r.choice(["ppr", "half", "std"])), "te_premium": float(r.choice([0.0, 0.0, 0.5, 1.0])),
        "difficulty": str(r.choice(["easy", "normal", "hard"])), "bench": int(r.choice([4, 6, 8, 10])), "ir_slots": int(r.choice([0, 1, 2, 4])),
        "flex_type": str(r.choice(["flex", "rb_wr"])), "tiebreaker": str(r.choice(["points_for", "head_to_head"])), "auto_lineup": bool(r.random() < 0.3),
    }
    sc["raw"]["user_slot"] = int(r.integers(1, sc["raw"]["teams"] + 1))
    if kind in ("dynasty",):
        sc["raw"].update(mode="dynasty", seasons=seasons, start_year=2026, rookie_rounds=int(r.choice([2, 3, 4, 5])), taxi_slots=int(r.choice([0, 2, 4])), taxi_years=int(r.choice([1, 2, 3])))
    if kind in ("league", "mid"):
        sc["teams"] = int(r.choice([4, 6, 8, 10, 12, 14, 16]))
        sc["playoff_teams"] = int(r.integers(2, min(8, sc["teams"]) + 1))
        sc["regular_weeks"] = int(r.choice([13, 14, 15, 17]))
        sc["dynasty"] = bool(r.random() < 0.4)
        sc["slots_pick"] = int(r.integers(0, 4))
        sc["bench"] = int(r.choice([4, 6, 8]))
    sc["user_style"] = str(r.choice(["idle", "auto", "chaos", "simto"]))
    return sc


def make_game(sc: dict[str, Any], seasons: int):
    """Returns (root snapshot, label). League imports go through the same builders the API uses."""

    seed, r = sc["seed"], np.random.default_rng(seed_of(sc) + 1)
    if sc["kind"] in ("league", "mid"):
        slot_sets = [
            ("QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DEF"),
            ("QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "SUPER_FLEX", "K"),
            ("QB", "RB", "WR", "WR", "TE", "WRRB_FLEX"),
            ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "FLEX"),
        ]
        slots = slot_sets[sc["slots_pick"]]
        imp = _imported(r, sc["teams"], slots, sc["bench"], mid=sc["kind"] == "mid", playoff_teams=sc["playoff_teams"], regular_weeks=sc["regular_weeks"])
        st = league_settings(imp, difficulty="normal", auto_lineup=sc["raw"]["auto_lineup"], dynasty=sc["dynasty"], seasons=seasons, current=sc["kind"] == "mid", tiebreaker=sc["raw"]["tiebreaker"])
        d = st.to_dict()
        d = _apply_flags(d, sc)
        st = GameSettings.from_dict(d)
        root = build_league_snapshot(ROWS, BYES, imp, st, seed, scoring_model=MODEL)
        return root
    s = GameSettings.parse(sc["raw"])
    d = _apply_flags(s.to_dict(), sc)
    return build_snapshot(ROWS, BYES, GameSettings.from_dict(d), seed, scoring_model=MODEL)


def seed_of(sc: dict[str, Any]) -> int:
    return int(sc["seed"]) * 31 + 5


def _apply_flags(d: dict[str, Any], sc: dict[str, Any]) -> dict[str, Any]:
    for f in OLD_FLAGS:
        d.pop(f, None)
    for f, v in sc["flags"].items():
        if v:
            d[f] = 1
    if d.get("mode") == "dynasty" and sc.get("aging_v"):
        d["aging_v"] = 1
    # a dynasty save keeps its own format version; the flags above only roll back the optional rule generations
    return d


# ----------------------------------------------------------------------------- the run


class Run:
    def __init__(self, sc: dict[str, Any], seasons: int, collect: bool = False) -> None:
        self.sc, self.seasons, self.collect = sc, seasons, collect
        self.seed = sc["seed"]
        self.rng = np.random.default_rng(self.seed * 104729 + 3)
        self.root = make_game(sc, seasons)
        self.S = self.root.settings
        self.state = GameState(self.root)
        self.em = Emitter(self.state, self.root)
        self.failures: list[str] = []
        self.stats: collections.Counter = collections.Counter()
        self.samples: dict[str, list[float]] = collections.defaultdict(list)
        self.complete_seasons = 0
        self.ages0: dict[str, float] = {}
        self.ever_retired: set[str] = set()
        self.label = (f"{sc['kind']} {self.S.teams}t pt={self.S.playoff_teams} rw={self.S.regular_weeks} {self.S.flex_type} sf={int(self.S.superflex)} "
                      f"k={int(self.S.include_k)} d={int(self.S.include_def)} {self.S.scoring} flags={sc['flags']} aging={sc['aging_v']} style={sc['user_style']}")

    # --------------------------------------------------------------- plumbing
    def fail(self, what: str, detail: str = "") -> None:
        msg = f"[{self.label} seed={self.seed} s{self.state.season_no} w{self.state.week} {self.state.status}] {what} {detail}"
        if msg not in self.failures:
            self.failures.append(msg)

    def view(self):
        snap = self.root.under(self.state.rules).season_view(self.state.view_no)
        self.em.snap = snap
        return snap

    def seed_now(self) -> int:
        return dyn.season_seed(self.seed, self.state.view_no) if self.S.dynasty else self.seed

    # ------------------------------------------------------------- invariants
    def check_static(self, snap) -> None:
        """Structure that must hold at any moment."""

        st, S = self.state, snap.settings
        seen: dict[str, str] = {}
        for tid in snap.tids:
            for pid in st.holdings(tid):
                if pid in seen:
                    self.fail("DUPLICATE_OWNER", f"{pid} on {seen[pid]} and {tid}")
                seen[pid] = tid
                if pid not in snap.players:
                    self.fail("OWNED_PLAYER_NOT_IN_POOL", f"{tid} {pid}")
            if len(st.ir[tid]) > max(S.ir_slots, 0) and S.reserves:
                self.fail("IR_OVER_SLOTS", f"{tid} {len(st.ir[tid])}/{S.ir_slots}")
            if len(st.taxi[tid]) > max(S.taxi_slots, 0) and S.reserves:
                self.fail("TAXI_OVER_SLOTS", f"{tid} {len(st.taxi[tid])}/{S.taxi_slots}")
            if not S.reserves and (st.ir[tid] or st.taxi[tid]):
                self.fail("RESERVES_IN_OLD_SAVE", tid)
            for pid in st.taxi[tid]:
                if pid in snap.players and snap.players[pid].pos in ("K", "DEF"):
                    self.fail("TAXI_HAS_K_DEF", f"{tid} {pid}")
            if not snap.team(tid).is_user and len(st.rosters[tid]) > S.roster_limit and st.status in ("in_season", "playoffs"):
                self.fail("AI_OVER_LIMIT", f"{tid} {len(st.rosters[tid])}/{S.roster_limit}")
            lineup = st.lineups.get(tid, [])
            if [s for s, _ in lineup] != list(S.slots):
                self.fail("LINEUP_SLOT_ORDER", f"{tid} {[s for s, _ in lineup]}")
            names = [p for _, p in lineup if p]
            if len(set(names)) != len(names):
                self.fail("LINEUP_DUPLICATE_PLAYER", tid)
            for slot, pid in lineup:
                if pid and pid not in st.rosters[tid]:
                    self.fail("LINEUP_NAMES_NON_ROSTER", f"{tid} {slot}:{pid}")
                elif pid and snap.players[pid].pos not in slot_positions(slot):
                    self.fail("LINEUP_INELIGIBLE_POSITION", f"{tid} {slot}:{pid} {snap.players[pid].pos}")
            for pos in SINGLETON_POSITIONS:
                n = sum(1 for p in st.holdings(tid) if p in snap.players and snap.players[p].pos == pos)
                if n > 1 and S.kd_v >= 1 and st.status in ("in_season", "playoffs"):
                    self.stats["second_singleton_" + pos] += 1
        # picks ledger
        if S.dynasty:
            owned = sorted(st.pick_owner)
            spent = sorted(p["pick"] for p in st.spent_picks)
            if sorted([*owned, *spent]) != sorted(st.created_picks):
                self.fail("PICK_LEDGER_BROKEN", f"owned={len(owned)} spent={len(spent)} created={len(st.created_picks)}")
            for pid, owner in st.pick_owner.items():
                if owner not in snap.tids:
                    self.fail("PICK_OWNER_UNKNOWN", f"{pid} -> {owner}")
        retired_back = {p for t in snap.tids for p in st.holdings(t)} & set(st.retired)
        if retired_back:
            self.fail("RETIRED_PLAYER_ON_ROSTER", str(sorted(retired_back)[:3]))

    def check_pool(self, snap) -> None:
        for pid, p in snap.players.items():
            for name in ("market", "mean", "age"):
                v = getattr(p, name)
                if v is None or not math.isfinite(float(v)):
                    self.fail("NONFINITE_PLAYER_FIELD", f"{pid}.{name}={v}")
                    return
            if p.market < 0 or p.mean < 0:
                self.fail("NEGATIVE_PLAYER_FIELD", f"{pid} market={p.market} mean={p.mean}")
                return
            if not 19 <= p.age <= 46:
                self.fail("AGE_OUT_OF_RANGE", f"{pid} {p.pos} age={p.age}")
                return

    def check_standings(self, snap) -> None:
        st, S = self.state, snap.settings
        tids = snap.tids
        reg_played = [h for h in st.history if h["kind"] == "regular"]
        mid_base = 0
        if S.mid_season and self.root.mid_start:
            mid_base = len(self.root.mid_start.get("weeks", ()))  # real weeks folded from the league import, with their own records
        tot_pf = tot_pa = 0.0
        w = l = t = 0
        for tid in tids:
            rec = st.stand[tid]
            for k in ("w", "l", "t", "pf", "pa"):
                if not math.isfinite(rec[k]) or rec[k] < -1e-9:
                    self.fail("BAD_STANDING_VALUE", f"{tid}.{k}={rec[k]}")
            tot_pf += rec["pf"]
            tot_pa += rec["pa"]
            w += rec["w"]
            l += rec["l"]
            t += rec["t"]
            games = rec["w"] + rec["l"] + rec["t"]
            if not (S.mid_season and self.root.mid_start and self.root.mid_start.get("stand")) and games != len(reg_played) + mid_base:
                self.fail("GAMES_PLAYED_MISMATCH", f"{tid} {games} vs weeks {len(reg_played)}+{mid_base}")
            s = st.streak[tid]
            if s and not (s[0] in "WLT" and s[1:].isdigit() and int(s[1:]) >= 1):
                self.fail("BAD_STREAK", f"{tid} {s!r}")
        if w != l or abs(tot_pf - tot_pa) > 1e-6:
            self.fail("STANDINGS_NOT_ZERO_SUM", f"w={w} l={l} pf={tot_pf:.2f} pa={tot_pa:.2f}")
        if len(tids) % 2 == 0 and t % 2:
            self.fail("ODD_TIE_COUNT", str(t))
        for a in tids:
            for b, rec in st.h2h[a].items():
                back = st.h2h[b].get(a)
                if back is None or [rec[0], rec[1], rec[2]] != [back[1], back[0], back[2]]:
                    self.fail("H2H_NOT_SYMMETRIC", f"{a} vs {b}: {rec} / {back}")
        order = rank_teams(snap, st)
        if sorted(order) != sorted(tids):
            self.fail("RANK_NOT_A_PERMUTATION")
        # sum of scored games equals totals (only for games that this run folded)
        pf_sum = collections.defaultdict(float)
        for h in reg_played:
            for g in h["games"]:
                pf_sum[g["home"]] += g["home_pts"]
                pf_sum[g["away"]] += g["away_pts"]
        if not mid_base:
            for tid in tids:
                if abs(pf_sum[tid] - st.stand[tid]["pf"]) > 1e-6:
                    self.fail("PF_NOT_SUM_OF_GAMES", f"{tid} {pf_sum[tid]:.3f} vs {st.stand[tid]['pf']:.3f}")

    def check_points(self, snap) -> None:
        for pid, hist in self.state.points.items():
            for v in hist:
                if v is not None and (not math.isfinite(v) or v < 0):
                    self.fail("BAD_PLAYER_POINTS", f"{pid} {v}")
                    return

    def check_schedule(self, snap) -> None:
        S = snap.settings
        if len(snap.schedule) != S.regular_weeks:
            self.fail("SCHEDULE_LENGTH", f"{len(snap.schedule)} vs {S.regular_weeks}")
        meet: collections.Counter = collections.Counter()
        home: collections.Counter = collections.Counter()
        for wk, games in enumerate(snap.schedule, 1):
            seen = [t for g in games for t in g]
            if S.mid_season and self.root.mid_start and wk < S.start_week and not games:
                continue
            if sorted(seen) != sorted(snap.tids):
                self.fail("SCHEDULE_WEEK_NOT_ONE_GAME_EACH", f"week {wk}: {len(seen)} slots, {len(set(seen))} unique of {len(snap.tids)}")
            for a, b in games:
                if a == b:
                    self.fail("SCHEDULE_SELF_GAME", f"week {wk} {a}")
                meet[frozenset((a, b))] += 1
                home[a] += 1
        if not S.mid_season and len(snap.tids) >= 2:
            n = len(snap.tids)
            counts = [meet.get(frozenset((a, b)), 0) for i, a in enumerate(snap.tids) for b in snap.tids[i + 1:]]
            if counts and max(counts) - min(counts) > 2 and S.regular_weeks <= 2 * (n - 1):
                self.fail("SCHEDULE_UNEVEN_OPPONENTS", f"min={min(counts)} max={max(counts)} (n={n}, weeks={S.regular_weeks})")
            hs = [home.get(t, 0) for t in snap.tids]
            if max(hs) - min(hs) > max(2, S.regular_weeks // 4):  # cosmetic only (a fantasy game has no home field): counted, not a failure
                self.stats["schedule_home_away_skew"] += 1

    def check_playoffs(self, snap) -> None:
        st, S = self.state, snap.settings
        pl = st.playoff
        if pl is None:
            return
        seeds = pl["seeds"]
        if len(seeds) != min(S.playoff_teams, len(snap.tids)) or len(set(seeds)) != len(seeds):
            self.fail("PLAYOFF_SEEDS_WRONG_SIZE", f"{len(seeds)} vs {S.playoff_teams}")
        if sorted(seeds, key=lambda t: seeds.index(t)) != seeds:
            self.fail("SEEDS_ORDER")
        slots = pl["slots"]
        if slots != bracket_slots(seeds):
            self.fail("BRACKET_SLOTS_MISMATCH")
        real = [s for s in slots if s]
        if sorted(real) != sorted(seeds):
            self.fail("BRACKET_DROPS_A_SEED")
        size = len(slots)
        byes = size - len(seeds)
        for i in range(0, size, 2):
            a, b = slots[i], slots[i + 1]
            if (a is None) == (b is None) is False and False:
                pass
            if a is None and b is None:
                self.fail("BRACKET_EMPTY_GAME")
            if (a is None or b is None) and byes:
                top = a or b
                if seeds.index(top) >= byes:
                    self.fail("BYE_GIVEN_TO_LOW_SEED", f"seed {seeds.index(top) + 1} of {len(seeds)} has a bye, byes={byes}")
        alive = list(slots)
        for rd in pl["rounds"]:
            nxt = []
            gi = 0
            for i in range(0, len(alive), 2):
                a, b = alive[i], alive[i + 1]
                if a is None or b is None:
                    nxt.append(a or b)
                    continue
                g = rd["games"][gi]
                gi += 1
                if {g["home"], g["away"]} != {a, b}:
                    self.fail("PLAYOFF_GAME_WRONG_TEAMS", f"round {rd['round']}: {g['home']}/{g['away']} vs {a}/{b}")
                hs, aws = g["home_pts"], g["away_pts"]
                want = a if (hs > aws or (hs == aws and seeds.index(a) < seeds.index(b))) else b
                if g["winner"] != want:
                    self.fail("PLAYOFF_WINNER_WRONG", f"round {rd['round']} {g}")
                nxt.append(g["winner"])
            if gi != len(rd["games"]):
                self.fail("PLAYOFF_GAME_COUNT", f"round {rd['round']}")
            alive = nxt
        if st.status in ("complete", "offseason") or st.champion:
            if len(alive) != 1 or alive[0] != st.champion:
                self.fail("CHAMPION_NOT_FINAL_WINNER", f"alive={alive} champion={st.champion}")
            if pl["results"].get(st.champion) != "champion":
                self.fail("CHAMPION_LABEL")
            labels = collections.Counter(pl["results"].values())
            if labels.get("champion") != 1 or labels.get("runner_up", 0) != 1:
                self.fail("PLAYOFF_LABEL_COUNTS", str(dict(labels)))
        if len(pl["rounds"]) > S.playoff_weeks:
            self.fail("TOO_MANY_PLAYOFF_ROUNDS", f"{len(pl['rounds'])} > {S.playoff_weeks}")
        if seeds != rank_teams_at_seeding(self, snap):
            self.fail("SEEDS_NOT_TOP_OF_STANDINGS_AT_SEEDING")

    def check_all(self, snap, *, deep: bool = False) -> None:
        self.check_static(snap)
        if deep:
            self.check_pool(snap)
            self.check_points(snap)
            self.check_standings(snap)
            self.check_playoffs(snap)

    # ------------------------------------------------------------ user behaviour
    def random_lineup(self, snap) -> None:
        st, user = self.state, snap.user_team.tid
        ev = Evaluator(snap, st)
        best, _ = ev.best_lineup(st.rosters[user], st.week)
        mode = self.rng.random()
        slots = [list(r) for r in best]
        if mode < 0.3:  # drop a few starters: empty slots must be auto-filled at kickoff
            for r in slots:
                if self.rng.random() < 0.4:
                    r[1] = None
        elif mode < 0.4:  # shuffle: ineligible placements must be refused with a ValueError, never accepted
            pids = [r[1] for r in slots]
            self.rng.shuffle(pids)
            slots = [[s[0], p] for s, p in zip(slots, pids)]
        try:
            act.set_lineup(self.em, slots)
            self.stats["lineup_set_ok"] += 1
        except (ValueError, GameError):
            self.stats["lineup_refused"] += 1
        except Exception:
            self.fail("SET_LINEUP_CRASH", traceback.format_exc(limit=4))

    def random_claims(self, snap) -> None:
        st, user = self.state, snap.user_team.tid
        free = st.free_agents(snap)
        if not free or not st.rosters[user]:
            return
        add = str(self.rng.choice(free))
        drop = str(self.rng.choice(st.rosters[user])) if self.rng.random() < 0.7 else None
        try:
            act.queue_claim(self.em, add, drop, None)
            self.stats["claims"] += 1
        except (ValueError, GameError):
            self.stats["claims_refused"] += 1
        except Exception:
            self.fail("QUEUE_CLAIM_CRASH", traceback.format_exc(limit=4))

    def random_reserve_move(self, snap) -> None:
        st, user = self.state, snap.user_team.tid
        pool = st.holdings(user)
        if not pool:
            return
        pid = str(self.rng.choice(pool))
        dst = str(self.rng.choice(["roster", "ir", "taxi"]))
        try:
            act.move_player(self.em, pid, dst)
            self.stats["moves"] += 1
        except (ValueError, GameError):
            self.stats["moves_refused"] += 1
        except Exception:
            self.fail("MOVE_PLAYER_CRASH", traceback.format_exc(limit=4))

    def random_trade(self, snap) -> None:
        st, user = self.state, snap.user_team.tid
        partner = str(self.rng.choice([t for t in snap.tids if t != user]))
        mine, theirs = st.holdings(user), st.holdings(partner)
        if not mine or not theirs:
            return
        give = [str(self.rng.choice(mine))]
        get = [str(self.rng.choice(theirs))]
        if S_dyn(snap) and self.rng.random() < 0.3 and st.picks_of(user):
            give.append(str(self.rng.choice(st.picks_of(user))))
        try:
            desk = TradeDesk(Evaluator(snap, st), self.seed_now())
            v = act.preview_trade(desk, partner, give, get)
            if v.decision == "accept":
                act.send_trade(self.em, desk, partner, give, get)
                self.stats["trades"] += 1
        except (ValueError, GameError):
            self.stats["trades_refused"] += 1
        except Exception:
            self.fail("TRADE_CRASH", traceback.format_exc(limit=5))

    def random_block(self, snap) -> None:
        from modules.sim.game_block import set_block

        st, user = self.state, snap.user_team.tid
        pool = [*st.holdings(user), *st.picks_of(user)]
        if not pool:
            return
        try:
            set_block(self.em, str(self.rng.choice(pool)), bool(self.rng.random() < 0.7), str(self.rng.choice(["QB", "RB", "WR", "TE"])) if self.rng.random() < 0.5 else None)
            self.stats["block_sets"] += 1
        except (ValueError, GameError):
            self.stats["block_refused"] += 1
        except Exception:
            self.fail("BLOCK_CRASH", traceback.format_exc(limit=4))

    def cut_to_limit(self, snap) -> None:
        user = snap.user_team.tid
        while len(self.state.rosters[user]) > snap.settings.roster_limit:
            ev = Evaluator(snap, self.state)
            pool = list(self.state.rosters[user])
            act.cut_player(self.em, str(min(pool, key=lambda p: (ev.worth_key(p) if hasattr(ev, "worth_key") else ev.ros_mean(p), p))))

    def user_turn(self, snap) -> None:
        style = self.sc["user_style"]
        if style == "idle":
            return
        if style in ("chaos", "simto"):
            n = int(self.rng.integers(0, 4))
            for _ in range(n):
                self.rng.choice([self.random_lineup, self.random_claims, self.random_reserve_move, self.random_trade, self.random_block])(snap)
                snap = self.view()
        if style == "auto" or self.rng.random() < 0.3:
            try:
                act.auto_lineup(self.em)
            except GameError:
                pass

    # ---------------------------------------------------------------- driving
    def step(self) -> None:
        snap = self.view()
        self.user_turn(snap)
        up = self.sc["upgrade_at"]
        if up is not None and self.state.season_no >= up and not self.state.rules and self.state.status == "in_season":
            act.upgrade_realism(self.em)
            self.stats["upgraded"] += 1
        snap = self.view()
        if not snap.settings.soft_limit:
            self.cut_to_limit(snap)
        try:
            if self.sc["user_style"] == "simto" and self.rng.random() < 0.5:
                target = str(self.rng.choice(["weeks", "weeks", "trade_deadline", "playoffs_start", "season_end"]))
                stops = simto.Stops(**{k: bool(self.rng.random() < 0.5) for k in ("offers", "injuries", "starters", "deadline", "roster")})
                try:
                    out = simto.run(self.em, snap, self.state, self.seed_now(), target=target, weeks=int(self.rng.integers(1, 6)), auto_set=bool(self.rng.random() < 0.5),
                                    force_first=bool(self.rng.random() < 0.5), pro=True, paywalled_fn=lambda s: False, stops=stops)
                    self.stats["simto_runs"] += 1
                    if out["weeks_played"] == 0 and not out["stopped"]:
                        self.fail("SIMTO_NO_PROGRESS_NO_REASON", target)
                    if out["stopped"] and out["stopped"]["code"] in ("roster_over_limit",):
                        self.cut_to_limit(self.view())
                        advance(self.em, self.view(), self.state, self.seed_now())
                    elif out["weeks_played"] == 0:
                        advance(self.em, self.view(), self.state, self.seed_now())
                except (ValueError, GameError):  # target already passed / nothing to run: a plain Advance instead
                    advance(self.em, snap, self.state, self.seed_now())
            else:
                advance(self.em, snap, self.state, self.seed_now())
        except GameError as exc:
            if exc.code == "roster_over_limit":
                self.cut_to_limit(self.view())
                advance(self.em, self.view(), self.state, self.seed_now())
            else:
                self.fail("ADVANCE_BLOCKED", f"{exc.code}: {exc}")
                raise
        snap = self.view()
        self.check_all(snap, deep=self.state.status in ("complete", "offseason") or self.state.week % 3 == 0)
        self.collect_week(snap)

    def collect_week(self, snap) -> None:
        if not self.collect or not self.state.history:
            return
        h = self.state.history[-1]
        if h["kind"] != "regular":
            return
        for g in h["games"]:
            self.samples["team_score"] += [g["home_pts"], g["away_pts"]]
            user = snap.user_team.tid
            self.samples["ai_team_score"] += [pts for tid, pts in ((g["home"], g["home_pts"]), (g["away"], g["away_pts"])) if tid != user]
            self.samples["user_team_score"] += [pts for tid, pts in ((g["home"], g["home_pts"]), (g["away"], g["away_pts"])) if tid == user]
            self.samples["margin"].append(abs(g["home_pts"] - g["away_pts"]))
        for t in snap.tids:
            self.samples["roster_size"].append(len(self.state.rosters[t]))

    def offseason(self) -> None:
        snap = self.view()
        user = snap.user_team.tid
        if self.sc["user_style"] in ("chaos", "simto"):
            for _ in range(int(self.rng.integers(0, 4))):
                self.rng.choice([self.random_claims, self.random_reserve_move, self.random_trade])(snap)
                snap = self.view()
        sd = self.seed_now()
        before_ret = set(self.state.retired)
        self.check_offseason_retire(snap)
        dyn.start_rookie_draft(self.em)
        snap = self.view()
        order = list(self.state.offseason["order"])
        if len(order) != self.S.teams * self.S.rookie_rounds:
            self.fail("ROOKIE_ORDER_LENGTH", f"{len(order)} vs {self.S.teams}x{self.S.rookie_rounds}")
        for tid in set(order):
            if order.count(tid) != self.S.rookie_rounds and not self.S.dynasty:
                self.fail("ROOKIE_ORDER_UNEVEN", tid)
        dyn.run_ai_rookie_picks(self.em, sd)
        dyn.auto_rookie_draft(self.em, sd)
        snap = self.view()
        picks = self.state.offseason["picks"]
        pids = [p["pid"] if isinstance(p, dict) else p for p in picks]
        if len(pids) != len(set(pids)):
            self.fail("ROOKIE_DRAFTED_TWICE")
        self.check_rookies(snap, pids)
        if not snap.settings.soft_limit:
            self.cut_to_limit(snap)
        dyn.start_next_season(self.em, sd)
        snap = self.view()
        self.check_all(snap, deep=True)
        self.check_pool(snap)
        self.check_ages(snap)
        self.check_picks_horizon(snap)
        self.stats["seasons_rolled"] += 1
        _ = before_ret

    def check_offseason_retire(self, snap) -> None:
        gone = set(self.state.retired)
        again = gone & self.ever_retired
        self.ever_retired |= gone
        if again - set():
            pass

    def check_rookies(self, snap, pids) -> None:
        for pid in pids:
            p = snap.players.get(pid)
            if p is None:
                self.fail("ROOKIE_NOT_IN_POOL", pid)
                continue
            if not 20 <= p.age <= 28:
                self.fail("ROOKIE_AGE_ODD", f"{pid} {p.pos} {p.age}")
            owners = [t for t in snap.tids if pid in self.state.holdings(t)]
            if len(owners) > 1:
                self.fail("ROOKIE_OWNERS", f"{pid} owned by {owners}")
            elif not owners:
                self.stats["rookie_dropped_at_draft"] += 1  # an AI team at its roster limit drafted him and cut the surplus

    def check_ages(self, snap) -> None:
        for pid, p in snap.players.items():
            old = self.ages0.get(pid)
            if old is not None and not (0.5 <= p.age - old <= 1.5):
                self.fail("AGE_JUMP", f"{pid} {old} -> {p.age}")
                break
        self.ages0 = {pid: p.age for pid, p in snap.players.items()}

    def check_picks_horizon(self, snap) -> None:
        S = snap.settings
        if not S.dynasty:
            return
        st = self.state
        years = collections.Counter(pid.split("-")[0] if "-" in pid else "?" for pid in st.pick_owner)
        owned_orig = collections.Counter()
        for pid in st.pick_owner:
            owned_orig[pid] += 1
        if max(owned_orig.values(), default=1) > 1:
            self.fail("PICK_DUPLICATED")
        _ = years

    def play(self) -> None:
        sc, root = self.sc, self.root
        if sc["kind"] in ("league", "mid"):
            em, state = self.em, self.state
            start_from_league(em, root.under(state.rules), state, self.seed)
        else:
            self.drive_draft()
        snap = self.view()
        self.check_all(snap, deep=True)
        self.check_pool(snap)
        self.check_schedule(snap)
        self.ages0 = {pid: p.age for pid, p in snap.players.items()}
        guard = 0
        while self.state.status != "complete":
            guard += 1
            if guard > 6000:
                self.fail("RUNAWAY")
                break
            if self.state.status in ("in_season", "playoffs"):
                self.step()
            elif self.state.status == "offseason":
                self.complete_seasons += 1
                self.offseason()
            else:
                self.fail("UNEXPECTED_STATUS", self.state.status)
                break
        if self.state.status == "complete":
            self.complete_seasons += 1
        self.final_checks()

    def drive_draft(self) -> None:
        from modules.sim.game_types import GameSnapshot  # noqa: F401
        ctx = DraftContext(self.root, self.state)
        run_ai_picks(ctx, self.em, self.seed)
        # the user drafts at random for some of the picks, auto for the rest
        auto_for_user(DraftContext(self.root, self.state), self.em, self.seed)
        finish_draft(self.em, self.root, self.state, self.seed)
        S = self.S
        picks = [p["pid"] for p in self.state.picks]
        if len(picks) != len(set(picks)):
            self.fail("DRAFT_PLAYER_TWICE")
        if len(picks) != S.rounds * S.teams:
            self.fail("DRAFT_PICK_COUNT", f"{len(picks)} vs {S.rounds}x{S.teams}")
        for tid in self.root.tids:
            if len(self.state.rosters[tid]) != S.rounds:
                self.fail("DRAFT_ROSTER_SIZE", f"{tid} {len(self.state.rosters[tid])} vs {S.rounds}")

    def final_checks(self) -> None:
        st = self.state
        S = self.S
        snap = self.view()
        self.check_all(snap, deep=True)
        if S.dynasty and S.multi_season:
            if len(st.seasons) != min(self.complete_seasons, S.seasons) and len(st.seasons) != S.seasons:
                self.fail("SEASON_ARCHIVE_COUNT", f"{len(st.seasons)} vs {self.complete_seasons}")
            champs = [a.get("champion") for a in st.seasons]
            if any(not c for c in champs):
                self.fail("SEASON_WITHOUT_CHAMPION", str(champs))
        digest = st.digest()
        if fold(self.root.under(st.rules) if False else self.root, self.em.events).digest() != digest:
            self.fail("FOLD_REPLAY_DIGEST_MISMATCH")
        # resume from a checkpoint in the middle of the log: serialize, rebuild, fold the rest
        if len(self.em.events) > 10:
            k = int(self.rng.integers(5, len(self.em.events) - 1))
            part = fold(self.root, self.em.events[:k])
            roundtrip = GameState.from_dict(self.root, part.to_dict())
            if roundtrip.digest() != part.digest():
                self.fail("CHECKPOINT_ROUNDTRIP_DIGEST", f"at {k}")
            fold(self.root, self.em.events[k:], roundtrip)
            if roundtrip.digest() != digest:
                self.fail("RESUME_DIGEST_MISMATCH", f"checkpoint at event {k}")
        if not S.multi_season and self.sc["kind"] in ("redraft",):
            try:
                if replay_game(self.root, self.seed, self.em.events, strict=True).digest() != digest:
                    self.fail("STRICT_REPLAY_DIGEST_MISMATCH")
            except Exception as exc:
                self.fail("STRICT_REPLAY_RAISED", f"{type(exc).__name__}: {exc}")
        self.check_schedule(snap)
        if not st.champion and S.mode:
            self.fail("NO_CHAMPION_AT_END")
        for tid in snap.tids:
            if tid not in st.stand:
                self.fail("TEAM_MISSING_FROM_STANDINGS", tid)


def rank_teams_at_seeding(run: Run, snap) -> list[str]:
    """The standings order the moment the regular season ended: replay the log up to the playoff_seeded event."""

    cache = getattr(run, "_seed_cache", None)
    if cache is not None and cache[0] == run.state.season_no:
        return cache[1]
    # find the last playoff_seeded event and fold up to it (cheap enough: only on checks of a seeded bracket, once a season)
    evs = run.em.events
    idx = max((i for i, e in enumerate(evs) if e["type"] == "playoff_seeded"), default=None)
    if idx is None:
        return run.state.playoff["seeds"]
    part = fold(run.root, evs[:idx])
    out = rank_teams(run.root.under(part.rules).season_view(part.view_no), part)[: len(run.state.playoff["seeds"])]
    run._seed_cache = (run.state.season_no, out)
    return out


def S_dyn(snap) -> bool:
    return snap.settings.policy.dynasty


# ----------------------------------------------------------------------------- orchestration


def run_seed(args: tuple[int, int, bool]) -> dict[str, Any]:
    seed, seasons, collect = args
    sc = make_scenario(seed, seasons)
    out: dict[str, Any] = {"seed": seed, "failures": [], "stats": {}, "samples": {}, "label": ""}
    run = None
    try:
        run = Run(sc, seasons, collect)
        out["label"] = run.label
        run.play()
    except Exception:
        if run is not None:
            run.fail("DRIVER_CRASH", traceback.format_exc(limit=10))
        else:
            out["failures"].append(f"[seed={seed} {sc['kind']}] SETUP_CRASH {traceback.format_exc(limit=10)}")
    if run is not None:
        out["failures"] += run.failures
        out["stats"] = dict(run.stats)
        out["samples"] = {k: v for k, v in run.samples.items()}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=12)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--seasons", type=int, default=3, help="seasons for dynasty scenarios (5, 10, 20 ... are the product's choices)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--stats", action="store_true", help="print realism summaries (team score, margin, roster sizes)")
    a = ap.parse_args(argv)
    jobs = [(s, a.seasons, a.stats) for s in range(a.start, a.start + a.seeds)]
    total: collections.Counter = collections.Counter()
    samples: dict[str, list[float]] = collections.defaultdict(list)
    bad = 0
    if a.workers > 1:
        with mp.get_context("spawn").Pool(a.workers) as pool:
            results = []
            for res in pool.imap_unordered(run_seed, jobs):  # progress as each seed finishes: a 20-season dynasty takes minutes
                results.append(res)
                print(f"  done seed {res['seed']} ({len(results)}/{len(jobs)}) failures={len(res['failures'])}", file=sys.stderr, flush=True)
    else:
        results = [run_seed(j) for j in jobs]
    kinds: dict[str, int] = collections.Counter()
    for res in sorted(results, key=lambda r: r["seed"]):
        total.update(res["stats"])
        for k, v in res["samples"].items():
            samples[k] += v
        for f in res["failures"]:
            bad += 1
            kind = f.split("] ", 1)[-1].split(" ", 1)[0]
            kinds[kind] += 1
            if kinds[kind] <= 3 or kind in ("DRIVER_CRASH", "SETUP_CRASH"):
                print("FAIL", f[:1500])
        print(f"seed {res['seed']}: {res['label']} failures={len(res['failures'])}", flush=True)
    print("TOTAL", dict(total))
    print("FAILURE KINDS", dict(kinds))
    if a.stats and samples:
        for k, v in samples.items():
            arr = np.array(v, dtype=float)
            print(f"  {k}: n={len(arr)} mean={arr.mean():.2f} p5={np.percentile(arr, 5):.2f} p50={np.percentile(arr, 50):.2f} p95={np.percentile(arr, 95):.2f}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
