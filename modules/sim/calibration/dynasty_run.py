"""Headless multi-season dynasty distributions. Throwaway pool (real 2025 panel), never touches data/players.db."""
import sys, pickle
from collections import defaultdict, Counter
import numpy as np
from modules.sim import game_dynasty as dyn, game_scoring
from modules.sim.calibration import dataset, tail_report
from modules.sim.game_draft import DraftContext, auto_for_user
from modules.sim.game_engine import advance, finish_draft
from modules.sim.game_setup import build_snapshot
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import GameSettings
from modules.sim.game_actions import cut_player
from modules.sim.game_eval import Evaluator, USER_PARAMS


def run(seed, n_seasons, teams=12, flags=None, profiles=False):
    """``flags``: GameSettings overrides, e.g. ``{"incumbent_v": 0, "defense_v": 0}`` for a before/after run. ``profiles``: also record each skill
    player's hidden season profile (``prof``: projection, season multiplier, archetype, rookie flag) for the season-variance reports."""
    model_id = game_scoring.default_model().model_id
    pool, byes = tail_report.pool_from_panel(dataset.load_panel())
    base = GameSettings.parse({"mode": "dynasty", "teams": teams, "user_slot": 3, "start_year": 2026, "seasons": n_seasons, "rookie_rounds": 3, "scoring": "ppr"})
    if flags:
        from dataclasses import replace
        base = replace(base, **flags)
    root = build_snapshot(pool, byes, base, seed, scoring_model=model_id)
    state = GameState(root)
    em = Emitter(state, root)
    auto_for_user(DraftContext(root, state), em, seed)
    finish_draft(em, root, state, seed)
    out = []
    while True:
        snap = root.season_view(state.view_no)
        sd = dyn.season_seed(seed, state.view_no)
        em.snap = snap
        S = snap.settings
        slot_pts = defaultdict(list)
        weekly = []
        margins = []
        while state.status in ("in_season", "playoffs"):
            w = state.week
            advance(em, snap, state, sd)
            if state.week == w + 1 and w <= S.regular_weeks:
                for t in snap.tids:
                    tot = 0
                    for slot, pid in state.lineups[t]:
                        pts = state.points.get(pid, [])
                        v = pts[w - 1] if pid and len(pts) >= w and pts[w - 1] is not None else 0.0
                        slot_pts[slot].append(v)
                        tot += v
                    weekly.append(tot)
        for h in state.history:
            if h["kind"] == "regular":
                for g in h["games"]:
                    margins.append(abs(g["home_pts"] - g["away_pts"]))
        pl = {}
        for pid, hist in state.points.items():
            g = [x for x in hist[:S.regular_weeks] if x is not None]
            if len(g) >= 8 and pid in snap.players:
                pl[pid] = (snap.players[pid].pos, float(np.mean(g)), snap.players[pid].age, sum(g), len(g))
        prof = {}
        if profiles:
            from modules.sim.game_engine import session_for
            sess = session_for(snap, sd)
            for pid in snap.pids:
                pl_ = snap.players[pid]
                if pl_.pos in ("QB", "RB", "WR", "TE") and pl_.mean > 0:
                    pr = sess.profile(pid)
                    prof[pid] = dict(proj=pl_.mean, mult=float(pr.season_multiplier), arch=pr.archetype, rookie=bool(pr.rookie), age=pl_.age, pos=pl_.pos)
        team_val = {t: sum(snap.players[p].market for p in state.holdings(t) if p in snap.players) for t in snap.tids}
        team_age = {t: float(np.mean([snap.players[p].age for p in state.rosters[t] if p in snap.players])) for t in snap.tids}
        wins = {t: (state.stand[t]["w"] + 0.5 * state.stand[t]["t"]) / S.regular_weeks for t in snap.tids}
        pfs = {t: state.stand[t]["pf"] for t in snap.tids}
        comp = {t: dict(Counter(snap.players[p].pos for p in state.rosters[t] if p in snap.players)) for t in snap.tids}
        out.append(dict(prof=prof, season=state.season_no, champ=state.champion, user=snap.user_team.tid, weekly=weekly, margins=margins,
                        slot_pts={k: list(v) for k, v in slot_pts.items()}, pl=pl, team_val=team_val, team_age=team_age, wins=wins,
                        pfs=pfs, comp=comp, nplayers=len(snap.players),
                        nfl={pid: p.nfl_team for pid, p in snap.players.items()}, depth={pid: p.extra.get("depth_chart_order") for pid, p in snap.players.items()},
                        tot={pid: (snap.players[pid].pos, sum(x for x in h[:S.regular_weeks] if x is not None), len([x for x in h[:S.regular_weeks] if x is not None])) for pid, h in state.points.items() if pid in snap.players and any(x is not None for x in h[:S.regular_weeks])},
                        depth_events=[e for e in em.events if e["type"] == "depth_chart"] if hasattr(em, "events") else [],
                        top_market=sorted([p.market for p in snap.players.values()], reverse=True)[:30]))
        if state.status != "offseason":
            break
        snap = root.season_view(state.view_no)
        sd = dyn.season_seed(seed, state.view_no)
        em.snap = snap
        dyn.start_rookie_draft(em)
        dyn.run_ai_rookie_picks(em, sd)
        dyn.auto_rookie_draft(em, sd)
        user = snap.user_team.tid
        while len(state.rosters[user]) > snap.settings.roster_limit:
            ev = Evaluator(snap, state)
            cut_player(em, min(state.rosters[user], key=lambda p: (ev.worth(USER_PARAMS, p), p)))
        dyn.start_next_season(em, sd)
    return out


if __name__ == "__main__":
    ns = int(sys.argv[1])
    seed = int(sys.argv[2])
    r = run(seed, ns)
    print("seed", seed, "champs", [x["champ"] for x in r], flush=True)
    pickle.dump(r, open(sys.argv[3], "wb"))
