"""Economy, draft, season-structure and exploit audit of the GM game (audit 3, 2026-11).

    python -m modules.sim.calibration.economy_audit season   [--seeds 40]           # playoffs, schedule, parity, score variance by shape
    python -m modules.sim.calibration.economy_audit draft    [--seeds 20]           # startup ADP adherence, runs, rookie classes and hit rates
    python -m modules.sim.calibration.economy_audit market   [--seeds 12]           # AI trade market: asks, overpay, injured stars, picks, volume
    python -m modules.sim.calibration.economy_audit wire     [--seeds 12]           # free-agent pool depth, waiver churn, streaming
    python -m modules.sim.calibration.economy_audit exploit  [--seeds 24] [--bots a,b,...] [--seasons 1]   # paired bots against a sensible baseline
    python -m modules.sim.calibration.economy_audit long     [--seeds 3] [--seasons 20]   # 20-season integrity: pool, ages, pick economy

Every run uses the real 2025 panel (never data/players.db) and is deterministic in the seed. Bots are paired: the same seed gives the same
snapshot, weekly dice and AI, so a bot and the baseline differ only by what the bot does (``--seeds`` x ``--seasons`` pairs, mean difference and
its standard error). ``--econ`` plays the same games with ``econ_v`` set (default: the current default settings).
Pure stdlib + numpy + modules.sim.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import replace
from multiprocessing import Pool
from typing import Any, Callable

import numpy as np

from modules.sim import game_actions as act
from modules.sim import game_dynasty as dyn
from modules.sim import game_scoring
from modules.sim.calibration import dataset, tail_report
from modules.sim.game_ai import TradeDesk
from modules.sim.game_draft import DraftContext, auto_for_user, run_ai_picks
from modules.sim.game_engine import advance, finish_draft, rank_teams
from modules.sim.game_eval import USER_PARAMS, Evaluator
from modules.sim.game_setup import build_snapshot
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import GameError, GameSettings

CORE = ("QB", "RB", "WR", "TE")
_POOL: tuple | None = None


def pool_byes():
    global _POOL
    if _POOL is None:
        _POOL = tail_report.pool_from_panel(dataset.load_panel())
    return _POOL


def se(a) -> float:
    a = np.asarray(a, dtype=float)
    return float(a.std(ddof=1) / np.sqrt(len(a))) if len(a) > 1 else float("nan")


# ----------------------------------------------------------------------------------------- driver


class Ctx:
    """What a bot sees: the season view, the live state and an emitter (the same calls the API makes)."""

    def __init__(self, root, snap, state, em, sd, seed):
        self.root, self.snap, self.state, self.em, self.sd, self.seed = root, snap, state, em, sd, seed
        self.user = root.user_team.tid

    def ev(self) -> Evaluator:
        return Evaluator(self.snap, self.state)


class Bot:
    """Baseline: the user's auto lineup every week and a hole-filling wire (the AI's own ai_v 1 cover logic), nothing else."""

    name = "baseline"
    cover = True

    def week(self, c: Ctx) -> None:
        pass

    def offseason(self, c: Ctx) -> None:
        pass

    def lineup(self, c: Ctx) -> None:
        act.auto_lineup(c.em)


def _cover(c: Ctx) -> None:
    """Sensible wire: only fill a hole this week or next and keep a backup, via the AI's emergency claim logic."""

    from modules.sim.game_ai_depth import ai_waiver_claims

    ev = c.ev()
    try:
        claims = ai_waiver_claims(ev, c.user, c.state.week, c.sd, (), emergency_only=True)
    except Exception:
        return
    for cl in claims[:2]:
        try:
            act.queue_claim(c.em, cl["add"], cl.get("drop"), None)
        except (GameError, ValueError):
            pass


def _trim(c: Ctx) -> None:
    over = len(c.state.rosters[c.user]) - c.snap.settings.roster_limit
    for _ in range(max(0, over)):
        ev = c.ev()
        act.cut_player(c.em, min(c.state.rosters[c.user], key=lambda p: (ev.worth(USER_PARAMS, p), p)))


def start_game(shape: dict, seed: int, n_seasons: int, econ: dict | None = None, user_draft: Callable | None = None):
    model_id = game_scoring.default_model().model_id
    pool, byes = pool_byes()
    raw = {"user_slot": 1 + seed % shape.get("teams", 12), "scoring": "ppr", **shape}
    if n_seasons > 1:
        raw.update(mode="dynasty", seasons=n_seasons, rookie_rounds=raw.get("rookie_rounds", 3), start_year=2026)
    settings = GameSettings.parse(raw)
    if econ:
        settings = replace(settings, **econ)
    root = build_snapshot(pool, byes, settings, seed, scoring_model=model_id)
    state = GameState(root)
    em = Emitter(state, root)
    if user_draft is None:
        auto_for_user(DraftContext(root, state), em, seed)
    else:
        user_draft(root, state, em, seed)
    finish_draft(em, root, state, seed)
    return root, state, em


def season_record(c: Ctx, bot_name: str) -> dict[str, Any]:
    snap, state = c.snap, c.state
    S = snap.settings
    games = S.regular_weeks
    tids = snap.tids
    st = state.stand
    pct = {t: (st[t]["w"] + 0.5 * st[t]["t"]) / games for t in tids}
    pf = {t: st[t]["pf"] for t in tids}
    pa = {t: st[t]["pa"] for t in tids}
    pl = state.playoff or {}
    seeds = pl.get("seeds") or []
    games_p = []
    for rd in pl.get("rounds", []):
        for g in rd["games"]:
            if g["home"] in seeds and g["away"] in seeds:
                hs, as_ = seeds.index(g["home"]) + 1, seeds.index(g["away"]) + 1
                hi, lo = (g["home"], g["away"]) if hs < as_ else (g["away"], g["home"])
                games_p.append({"round": rd["round"], "hi_seed": min(hs, as_), "lo_seed": max(hs, as_), "hi_won": g["winner"] == hi,
                                "margin": abs(g["home_pts"] - g["away_pts"])})
    # strength of schedule: mean final win% of the opponents each team faced in the regular season
    opp: dict[str, list[str]] = {t: [] for t in tids}
    dup: dict[str, int] = {}
    for wk in snap.schedule[:games]:
        for a, b in wk:
            opp[a].append(b)
            opp[b].append(a)
    pyth = {t: pf[t] ** 2.37 / max(1e-9, pf[t] ** 2.37 + pa[t] ** 2.37) for t in tids}
    pyth_pf = {t: pf[t] / max(1e-9, float(np.mean(list(pf.values())))) for t in tids}  # points-based strength, independent of who beat whom
    sos = {t: float(np.mean([pyth_pf[o] for o in opp[t]])) for t in tids}
    for t in tids:
        dup[t] = max(Counter(opp[t]).values())
    final = rank_teams(snap, state)
    me = c.user
    arch = state.seasons[-1] if state.seasons else {}
    return {
        "bot": bot_name, "season": state.season_no, "wins": st[me]["w"] + 0.5 * st[me]["t"], "pf": pf[me], "rank": final.index(me) + 1,
        "made": me in seeds, "title": state.champion == me, "pct": pct, "pf_all": pf, "pa_all": pa, "pyth": pyth, "sos": sos, "dup": dup,
        "po": games_p, "n_seeds": len(seeds), "champ_seed": (seeds.index(state.champion) + 1) if state.champion in seeds else None,
        "champion": state.champion, "archive_title": bool(arch.get("champion") and arch["champion"].get("is_you")),
    }


def play(shape: dict, seed: int, bot: Bot, n_seasons: int = 1, econ: dict | None = None, observe: Callable | None = None,
         user_draft: Callable | None = None) -> dict[str, Any]:
    """One whole game with ``bot`` as the user. Returns per-season records (+ whatever ``observe(ctx, phase, rec)`` adds)."""

    root, state, em = start_game(shape, seed, n_seasons, econ, user_draft)
    rows: list[dict[str, Any]] = []
    extra: list[Any] = []
    while True:
        snap = root.season_view(state.view_no) if n_seasons > 1 else root
        sd = dyn.season_seed(seed, state.view_no) if n_seasons > 1 else seed
        em.snap = snap
        c = Ctx(root, snap, state, em, sd, seed)
        if observe:
            observe(c, "season_start", None)
        while state.status in ("in_season", "playoffs"):
            if state.status == "in_season":
                if bot.cover:
                    _cover(c)
                bot.week(c)
                _trim(c)
                bot.lineup(c)
            advance(em, snap, state, sd)
            if observe:
                observe(c, "week", None)
        if state.status == "offseason":
            snap = root.season_view(state.view_no)
            em.snap = snap
            c = Ctx(root, snap, state, em, sd, seed)
        rec = season_record(c, bot.name)
        if observe:
            extra.append(observe(c, "season_end", rec))
        rows.append(rec)
        if state.status != "offseason":
            break
        sd = dyn.season_seed(seed, state.view_no)
        c = Ctx(root, snap, state, em, sd, seed)
        dyn.start_rookie_draft(em)
        dyn.run_ai_rookie_picks(em, sd)
        bot.offseason(c)
        dyn.auto_rookie_draft(em, sd)
        _trim(c)
        dyn.start_next_season(em, sd)
    return {"rows": rows, "extra": extra, "state": state, "root": root}


# ------------------------------------------------------------------------------------- bots


def _val(ev, snap, pid):
    return ev.base_value(pid) if pid in snap.players else ev.pick_value(pid)


def _assets(c: Ctx, tid: str | None = None) -> float:
    ev = c.ev()
    t = tid or c.user
    return sum(_val(ev, c.snap, p) for p in [*c.state.holdings(t), *c.state.picks_of(t)])


class Churn(Bot):
    name = "churn"

    def week(self, c):
        ev = c.ev()
        owned = c.state.owner_map()
        free = sorted((p for p in c.snap.pids if p not in owned and c.snap.players[p].pos in CORE and c.state.out.get(p, 0) == 0),
                      key=lambda p: -ev.ros_mean(p))[:6]
        lineup_ids = {pid for _, pid in ev.best_lineup(c.state.rosters[c.user], c.state.week)[0] if pid}
        bench = sorted((p for p in c.state.rosters[c.user] if p not in lineup_ids), key=lambda p: ev.ros_mean(p))
        for add, drop in zip(free[:3], bench[:3]):
            if ev.ros_mean(add) > ev.ros_mean(drop) + 0.3:
                try:
                    act.queue_claim(c.em, add, drop, None)
                except (GameError, ValueError):
                    pass


class Streamer(Bot):
    """K and DEF streaming: every week claim the best free kicker / defense by projection for the current one."""

    name = "streamer"

    def week(self, c):
        ev = c.ev()
        owned = c.state.owner_map()
        for pos in ("K", "DEF"):
            mine = [p for p in c.state.rosters[c.user] if c.snap.players[p].pos == pos]
            if not mine or pos not in {"K", "DEF"}:
                continue
            free = [p for p in c.snap.pids if p not in owned and c.snap.players[p].pos == pos and c.state.out.get(p, 0) == 0
                    and not ev.on_bye(p, c.state.week)]
            if not free:
                continue
            best = max(free, key=lambda p: (ev.next_proj(p, c.state.week), p))
            cur = max(mine, key=lambda p: ev.next_proj(p, c.state.week))
            if ev.next_proj(best, c.state.week) > ev.next_proj(cur, c.state.week) + 0.2:
                try:
                    act.queue_claim(c.em, best, cur, None)
                except (GameError, ValueError):
                    pass


class TradeBot(Bot):
    """AI-accepted trades that raise neutral asset value (``stacker``), bring back picks (``hoarder``), raise the lineup (``lineup``),
    or both consolidate/spread (``farmer``). ``weeks`` early weeks, ``per_week`` trades a week."""

    cover = True

    def __init__(self, kind: str = "stacker", weeks: int = 4, per_week: int = 2):
        self.kind, self.weeks, self.per_week = kind, weeks, per_week
        self.name = kind

    def week(self, c):
        if c.state.week > self.weeks or c.state.week >= c.snap.settings.trade_deadline_week:
            return
        snap, state, user = c.snap, c.state, c.user
        for _ in range(self.per_week):
            ev = c.ev()
            desk = TradeDesk(ev, c.sd, state.week)
            best = None
            lineup0 = ev.lineup_total(state.rosters[user])
            mine = sorted(desk.tradable(user), key=lambda p: _val(ev, snap, p))[:8]
            for tid in snap.tids:
                if tid == user:
                    continue
                theirs = sorted(desk.tradable(tid), key=lambda p: -_val(ev, snap, p))[:8]
                if self.kind == "injured":
                    theirs = [p for p in desk.tradable(tid) if p in snap.players and state.out.get(p, 0) >= 5 and _val(ev, snap, p) >= 25]
                    mine = sorted(desk.tradable(user), key=lambda p: _val(ev, snap, p))
                if self.kind == "farmer":
                    for i in range(len(mine)):
                        for j in range(i + 1, len(mine)):
                            for get in theirs[:5]:
                                g2 = [mine[i], mine[j]]
                                if desk.ai_accepts(tid, g2, [get])[0]:
                                    gain = _val(ev, snap, get) - sum(_val(ev, snap, g) for g in g2)
                                    if best is None or gain > best[0]:
                                        best = (gain, tid, g2, [get])
                for give in mine:
                    for get in theirs:
                        if self.kind == "hoarder" and get in snap.players:
                            continue
                        if self.kind == "injured" and not (get in snap.players and state.out.get(get, 0) >= 5):
                            continue
                        if not desk.ai_accepts(tid, [give], [get])[0]:
                            continue
                        if self.kind == "lineup":
                            gain = ev.lineup_total([p for p in state.rosters[user] if p != give] + ([get] if get in snap.players else [])) - lineup0
                        else:
                            gain = _val(ev, snap, get) - _val(ev, snap, give)
                        if best is None or gain > best[0]:
                            best = (gain, tid, [give], [get])
            if best is None or best[0] <= (0.2 if self.kind == "lineup" else 0.5):
                return
            try:
                _, trade = act.send_trade(c.em, TradeDesk(c.ev(), c.sd, state.week), best[1], best[2], best[3])
            except (GameError, ValueError):
                return
            if trade is None:
                return


class CeilingLineup(Bot):
    """Always starts the highest-ceiling lineup (projection + band) instead of the highest projection."""

    name = "ceiling"

    def lineup(self, c):
        from modules.sim.lineup import pick_lineup

        ev = c.ev()
        week = c.state.week
        roster = c.state.rosters[c.user]
        ents = []
        for pid in roster:
            if ev.on_bye(pid, week) or ev.out_in(pid, week):
                continue
            lo, hi = ev.band(pid)
            ents.append((ev.proj(pid, week) + 0.5 * (hi - ev.proj(pid, week)), pid, c.snap.players[pid].pos))
        try:
            assign, _ = pick_lineup(ev.plan, ents)
            act.set_lineup(c.em, ev_to_slots(ev, assign))
        except Exception:
            act.auto_lineup(c.em)


def ev_to_slots(ev, assign):
    from modules.sim.game_eval import to_slot_order

    return to_slot_order(ev.snap.settings.slots, assign)


class SfQbHoard(Bot):
    """Superflex: after the draft, spend roster spots on every free QB worth claiming and buy QBs in 1-for-1 trades."""

    name = "qb_hoard"

    def week(self, c):
        ev = c.ev()
        owned = c.state.owner_map()
        mine = [p for p in c.state.rosters[c.user] if c.snap.players[p].pos == "QB"]
        if len(mine) >= 4:
            return
        free = sorted((p for p in c.snap.pids if p not in owned and c.snap.players[p].pos == "QB" and c.state.out.get(p, 0) == 0),
                      key=lambda p: -ev.ros_mean(p))
        lineup_ids = {pid for _, pid in ev.best_lineup(c.state.rosters[c.user], c.state.week)[0] if pid}
        bench = sorted((p for p in c.state.rosters[c.user] if p not in lineup_ids and c.snap.players[p].pos != "QB"), key=lambda p: ev.ros_mean(p))
        if free and bench:
            try:
                act.queue_claim(c.em, free[0], bench[0], None)
            except (GameError, ValueError):
                pass


class Tank(TradeBot):
    """Dynasty: seasons 1-2 sell every vet worth selling to AI teams for picks and play the worst legal lineup; from season 3 buy back (stacker)."""

    name = "tank"
    cover = False

    def __init__(self, tank_seasons: int = 2):
        super().__init__("hoarder", 17, 3)
        self.name = "tank"
        self.tank_seasons = tank_seasons

    def week(self, c):
        if c.state.season_no < self.tank_seasons:
            return TradeBot.week(self, c)
        self.weeks = 3
        self.kind = "stacker"
        TradeBot.week(self, c)

    def lineup(self, c):
        if c.state.season_no < self.tank_seasons:
            ev = c.ev()
            week = c.state.week
            from modules.sim.lineup import pick_lineup

            ents = [(-ev.proj(p, week), p, c.snap.players[p].pos) for p in c.state.rosters[c.user]
                    if not ev.on_bye(p, week) and not ev.out_in(p, week)]
            try:
                assign, _ = pick_lineup(ev.plan, ents)
                act.set_lineup(c.em, ev_to_slots(ev, assign))
                return
            except Exception:
                pass
        act.auto_lineup(c.em)


BOTS: dict[str, Callable[[], Bot]] = {
    "baseline": Bot, "churn": Churn, "streamer": Streamer, "stacker": lambda: TradeBot("stacker"), "hoarder": lambda: TradeBot("hoarder"),
    "lineup_trader": lambda: TradeBot("lineup"), "farmer": lambda: TradeBot("farmer"), "ceiling": CeilingLineup, "qb_hoard": SfQbHoard, "tank": Tank, "injured": lambda: TradeBot("injured", 17, 2),
}

# ------------------------------------------------------------------------------------- season


def _season_job(args):
    shape, seed, econ = args
    scores: dict[int, list[float]] = defaultdict(list)

    def observe(c, phase, rec):
        st = c.state
        if phase == "week" and st.week - 1 <= c.snap.settings.regular_weeks and st.week >= 2:
            w = st.week - 1
            for tid in c.snap.tids:
                tot = 0.0
                for slot, pid in st.lineups.get(tid, []):
                    pts = st.points.get(pid, [])
                    tot += pts[w - 1] if pid and len(pts) >= w and pts[w - 1] is not None else 0.0
                scores[w].append(tot)

    r = play(shape, seed, Bot(), 1, econ, observe)
    row = r["rows"][0]
    row["week_scores"] = {w: v for w, v in scores.items() if w <= r["root"].settings.regular_weeks}
    return row


def season_audit(seeds: int, econ: dict | None = None) -> dict[str, Any]:
    shapes = {"12t ppr": {"teams": 12}, "8t": {"teams": 8}, "10t": {"teams": 10}, "14t": {"teams": 14},
              "12t sf": {"teams": 12, "superflex": True}, "12t half": {"teams": 12, "scoring": "half"}, "12t std": {"teams": 12, "scoring": "std"},
              "12t tep": {"teams": 12, "te_premium": 0.5}}
    out: dict[str, Any] = {}
    with Pool(6) as pool:
        for name, shape in shapes.items():
            rows = pool.map(_season_job, [(shape, s, econ) for s in range(1, seeds + 1)])
            out[name] = summarize_season(rows, shape)
    return out


def summarize_season(rows: list[dict], shape: dict) -> dict[str, Any]:
    po = [g for r in rows for g in r["po"]]
    by_round = defaultdict(list)
    by_pair = defaultdict(list)
    for g in po:
        by_round[g["round"]].append(g["hi_won"])
        by_pair[(g["hi_seed"], g["lo_seed"])].append(g["hi_won"])
    n = len(rows[0]["pct"])
    wins_sd = np.mean([np.std(list(r["pct"].values())) for r in rows])
    sos_sd = np.mean([np.std(list(r["sos"].values())) for r in rows])
    # luck: wins vs pythagorean
    luck = [abs(r["pct"][t] - r["pyth"][t]) for r in rows for t in r["pct"]]
    rho = []
    for r in rows:
        ts = list(r["pct"])
        rho.append(np.corrcoef([r["pct"][t] for t in ts], [r["pyth"][t] for t in ts])[0, 1])
    # does a better pyth/SoS-adjusted record predict? SoS effect: corr(sos, pct - pyth)
    sos_eff = []
    for r in rows:
        ts = list(r["pct"])
        sos_eff.append(np.corrcoef([r["sos"][t] for t in ts], [r["pct"][t] - r["pyth"][t] for t in ts])[0, 1])
    dups = [max(r["dup"].values()) for r in rows]
    champ = Counter(r["champ_seed"] for r in rows)
    return {
        "n": len(rows), "playoff_games": len(po), "hi_seed_win_rate": round(float(np.mean([g["hi_won"] for g in po])), 3) if po else None,
        "by_round": {k: [round(float(np.mean(v)), 3), len(v)] for k, v in sorted(by_round.items())},
        "by_pair": {f"{a}v{b}": [round(float(np.mean(v)), 3), len(v)] for (a, b), v in sorted(by_pair.items())},
        "win_pct_sd": round(float(wins_sd), 3), "sos_sd": round(float(sos_sd), 3), "sos_vs_luck_corr": round(float(np.mean(sos_eff)), 3),
        "pyth_corr": round(float(np.mean(rho)), 3), "mean_abs_luck": round(float(np.mean(luck)), 3), "max_repeat_opponent": Counter(dups),
        "champ_seed_dist": {str(k): v for k, v in sorted(champ.items(), key=lambda kv: (kv[0] is None, kv[0]))},
        "team_week_sd": round(float(np.mean([np.std(v) for r in rows for v in r["week_scores"].values()])), 1),
        "team_week_mean": round(float(np.mean([np.mean(v) for r in rows for v in r["week_scores"].values()])), 1),
        "week1_to_last": [round(float(np.mean([np.mean(r["week_scores"][1]) for r in rows])), 1), round(float(np.mean([np.mean(r["week_scores"][max(r["week_scores"])]) for r in rows])), 1)],
        "pf_mean": round(float(np.mean([np.mean(list(r["pf_all"].values())) for r in rows])), 1),
    }


# ----------------------------------------------------------------------------------------- exploit


def _bot_job(args):
    shape, seed, name, n_seasons, econ = args
    bot = BOTS[name]()
    r = play(shape, seed, bot, n_seasons, econ)
    return name, seed, r["rows"]


def exploit(seeds: int, bots: list[str], n_seasons: int, shape: dict, econ: dict | None = None) -> dict[str, Any]:
    names = ["baseline"] + [b for b in bots if b != "baseline"]
    jobs = [(shape, s, n, n_seasons, econ) for s in range(1, seeds + 1) for n in names]
    with Pool(6) as pool:
        res = pool.map(_bot_job, jobs, chunksize=1)
    table: dict[str, dict[int, list[dict]]] = defaultdict(dict)
    for name, seed, rows in res:
        table[name][seed] = rows
    out: dict[str, Any] = {}
    for name in names:
        diffs, wins, titles, made, ranks = [], [], [], [], []
        for seed, rows in table[name].items():
            for i, r in enumerate(rows):
                b = table["baseline"][seed][i]
                diffs.append(r["wins"] - b["wins"])
                wins.append(r["wins"])
                titles.append(r["title"])
                made.append(r["made"])
                ranks.append(r["rank"])
        out[name] = {"n": len(wins), "wins": round(float(np.mean(wins)), 2), "wins_minus_baseline": round(float(np.mean(diffs)), 2), "se": round(se(diffs), 2),
                     "made_playoffs": round(float(np.mean(made)), 3), "titles": round(float(np.mean(titles)), 3), "mean_rank": round(float(np.mean(ranks)), 2)}
        if n_seasons > 1:
            bys = defaultdict(list)
            for seed, rows in table[name].items():
                for i, r in enumerate(rows):
                    bys[i // max(1, n_seasons // 4)].append(r["wins"] - table["baseline"][seed][i]["wins"])
            out[name]["diff_by_block"] = {str(k): round(float(np.mean(v)), 2) for k, v in sorted(bys.items())}
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["season", "exploit", "draft", "market", "wire", "long"])
    ap.add_argument("--seeds", type=int, default=12)
    ap.add_argument("--seasons", type=int, default=1)
    ap.add_argument("--bots", default="")
    ap.add_argument("--shape", default="{}")
    ap.add_argument("--econ", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args(argv)
    econ = json.loads(a.econ) if a.econ else None
    if a.cmd == "season":
        out = season_audit(a.seeds, econ)
    elif a.cmd == "exploit":
        out = exploit(a.seeds, [b for b in a.bots.split(",") if b], a.seasons, {"teams": 12, **json.loads(a.shape)}, econ)
    else:
        from modules.sim.calibration import economy_audit_more as more

        out = getattr(more, a.cmd)(a, econ)
    text = json.dumps(out, indent=1, default=str)
    if a.json:
        with open(a.json, "w") as f:
            f.write(text)
    print(text)


if __name__ == "__main__":
    main(sys.argv[1:])
