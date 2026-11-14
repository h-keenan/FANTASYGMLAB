"""Long-dynasty equilibrium and cost report: does a 20-season GM game stay realistic and fast?

Plays whole multi-season dynasty games (pool built from the real 2025 panel, player-model-4) and records, per season:
the talent pool (size, ages of the NFL starters, best-player levels and scarcity by position, rookie class quality),
league-wide team scores and weekly-score tails, AI roster composition and transaction rates, and cost (wall time,
event-log and checkpoint size, phone payload sizes, peak memory).

    python -m modules.sim.calibration.dynasty_report [--seeds 2] [--seasons 20] [--json out.json]

Pure stdlib + numpy + modules.sim. Never touches data/players.db.
"""

from __future__ import annotations

import argparse
import json
import resource
import time
from collections import Counter
from dataclasses import replace
from typing import Any

import numpy as np

from modules.sim import game_dynasty as dyn
from modules.sim.calibration import dataset, tail_report
from modules.sim.game_actions import cut_player
from modules.sim.game_draft import DraftContext, auto_for_user
from modules.sim.game_engine import advance, finish_draft
from modules.sim.game_eval import USER_PARAMS, Evaluator
from modules.sim.game_setup import build_snapshot
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import GameSettings

CORE = ("QB", "RB", "WR", "TE")


def _rss_mb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / (1024 * 1024) if r > 1e7 else r / 1024  # macOS bytes, Linux KB


def pool_stats(snap, state) -> dict[str, Any]:
    pl = list(snap.players.values())
    teams = len(snap.teams)
    out: dict[str, Any] = {"pool_size": len(pl)}
    starters: list = []
    for pos in CORE + ("K",):
        group = sorted((p for p in pl if p.pos == pos), key=lambda p: (-p.mean, p.pid))
        n = len([s for s in snap.settings.slots if s == pos]) * teams
        out[f"{pos}_n"] = len(group)
        means = [p.mean for p in group]
        out[f"{pos}_bands"] = [round(float(np.mean(means[a:b])), 2) if means[a:b] else 0.0 for a, b in ((0, 12), (12, 24), (24, 36), (36, 60))]
        out[f"{pos}_top12_mean"] = round(float(np.mean([p.mean for p in group[:12]])), 2) if group else 0.0
        out[f"{pos}_rank24_mean"] = round(group[min(23, len(group) - 1)].mean, 2) if group else 0.0
        starters += group[: max(1, n)]
    out["starter_age_mean"] = round(float(np.mean([p.age for p in starters])), 2)
    out["starter_age_p90"] = round(float(np.percentile([p.age for p in starters], 90)), 1)
    out["starter_age_max"] = round(float(max(p.age for p in starters)), 1)
    out["pool_age_mean"] = round(float(np.mean([p.age for p in pl])), 2)
    out["pool_age_gt33"] = sum(1 for p in pl if p.age > 33)
    out["min_age"] = round(float(min(p.age for p in pl)), 1)
    out["market_top20_mean"] = round(float(np.mean(sorted((p.market for p in pl), reverse=True)[:20])), 1)
    rookies = sorted((p for p in pl if p.extra.get("is_rookie")), key=lambda p: -p.mean)
    out["rookie_n"] = len(rookies)
    out["rookie_top5_mean"] = round(float(np.mean([p.mean for p in rookies[:5]])), 2) if rookies else 0.0
    out["rookie_market_top5"] = round(float(np.mean([p.market for p in rookies[:5]])), 1) if rookies else 0.0
    out["max_mean"] = round(max(p.mean for p in pl), 1)
    return out


def cost_probe(root, snap, state, events) -> dict[str, Any]:
    """What a phone pays at this point of a long game: payload sizes and build times of the main views, the size of the saved
    state, and how long a cold replay of the whole event log takes."""

    from modules.sim import game_dynasty_view as dview
    from modules.sim import game_home, game_view
    from modules.sim.game_state import fold

    def timed(fn):
        t0 = time.time()
        out = fn()
        return round((time.time() - t0) * 1000, 1), len(json.dumps(out, default=str))

    probe: dict[str, Any] = {}
    probe["home_ms_bytes"] = timed(lambda: game_home.home_view(snap, state, 1))
    probe["league_ms_bytes"] = timed(lambda: game_view.league_view(snap, state))
    probe["players_ms_bytes"] = timed(lambda: game_view.players_page(snap, state))
    probe["summary_ms_bytes"] = timed(lambda: dview.summary_view(snap, state))
    probe["state_bytes"] = len(json.dumps(state.to_dict(), default=str))
    t0 = time.time()
    fold(snap.root, events)
    probe["replay_s"] = round(time.time() - t0, 2)
    probe["events"] = len(events)
    return probe


def play(seed: int, seasons: int, model_id: str, rows, byes, teams: int = 12, probes: tuple[int, ...] = (), dynasty_v: int | None = None) -> dict[str, Any]:
    base = GameSettings.parse({"mode": "dynasty", "teams": teams, "user_slot": 3, "start_year": 2026, "seasons": 5, "rookie_rounds": 3, "scoring": "ppr"})
    settings = replace(base, seasons=seasons, **({} if dynasty_v is None else {"dynasty_v": dynasty_v}))
    root = build_snapshot(rows, byes, settings, seed, scoring_model=model_id)
    state = GameState(root)
    em = Emitter(state, root)
    auto_for_user(DraftContext(root, state), em, seed)
    finish_draft(em, root, state, seed)
    per: list[dict[str, Any]] = []
    events_bytes = 0
    n_events = 0
    t_game = time.time()
    while True:
        t0 = time.time()
        snap = root.season_view(state.view_no)
        t_view = time.time() - t0
        sd = dyn.season_seed(seed, state.view_no)
        em.snap = snap
        t0 = time.time()
        team_scores: list[float] = []
        wk_pts: list[float] = []
        adds = trades = 0
        ev0 = len(em.events)
        while state.status in ("in_season", "playoffs"):
            w = state.week
            advance(em, snap, state, sd)
        season_no = state.season_no
        t_play = time.time() - t0
        for rc in state.recaps.values():
            if rc.get("kind") == "regular":
                for g in rc["scores"]:
                    team_scores += [g["home_pts"], g["away_pts"]]
        for pid, hist in state.points.items():
            if snap.players[pid].pos in CORE:
                wk_pts += [x for x in hist[: snap.settings.regular_weeks] if x is not None]
        ro = Counter()
        for tid in snap.tids:
            if tid != snap.user_team.tid:
                for p in state.rosters[tid]:
                    ro[snap.players[p].pos] += 1
        n_ai = len(snap.tids) - 1
        row = {"season": season_no, **pool_stats(snap, state)}
        row.update({
            "team_score_mean": round(float(np.mean(team_scores)), 1) if team_scores else 0.0,
            "team_score_p99": round(float(np.percentile(team_scores, 99)), 1) if team_scores else 0.0,
            "wk_gt40": round(float(np.mean(np.array(wk_pts) > 40)), 5) if wk_pts else 0.0,
            "wk_max": round(float(max(wk_pts)), 1) if wk_pts else 0.0,
            "ai_roster_mean": round(sum(ro.values()) / n_ai, 2),
            "ai_pos_mean": {k: round(v / n_ai, 2) for k, v in sorted(ro.items())},
            "waivers": sum(1 for e in em.events[ev0:] if e["type"] == "waiver_result" and e["payload"].get("ok") and e["actor"] != "user" and not snap.team(e["payload"]["team"]).is_user),
            "trades": sum(1 for e in em.events[ev0:] if e["type"] == "trade" and e["payload"].get("source") == "ai_ai"),
            "t_view_s": round(t_view, 3), "t_play_s": round(t_play, 2),
            "events": len(em.events), "events_bytes": len(json.dumps(em.events[ev0:], default=str)),
        })
        if state.status != "offseason":
            per.append(row)
            break
        snap = root.season_view(state.view_no)
        sd = dyn.season_seed(seed, state.view_no)
        em.snap = snap
        t0 = time.time()
        dyn.start_rookie_draft(em)
        dyn.run_ai_rookie_picks(em, sd)
        dyn.auto_rookie_draft(em, sd)
        user = snap.user_team.tid
        while len(state.rosters[user]) > snap.settings.roster_limit:
            ev = Evaluator(snap, state)
            cut_player(em, min(state.rosters[user], key=lambda p: (ev.worth(USER_PARAMS, p), p)))
        dyn.start_next_season(em, sd)
        row["t_offseason_s"] = round(time.time() - t0, 2)
        if probes and season_no in probes:
            row["probe"] = cost_probe(root, snap, state, list(em.events))
        row["state_bytes"] = len(json.dumps(state.to_dict(), default=str))
        row["rss_mb"] = round(_rss_mb(), 1)
        per.append(row)
    out = {"seed": seed, "seasons": per, "wall_s": round(time.time() - t_game, 1)}
    if probes:  # a cold process rebuilding the last season's pool from the season-1 snapshot alone
        cold = build_snapshot(rows, byes, settings, seed, scoring_model=model_id)
        t0 = time.time()
        cold.season_view(seasons)
        out["cold_season_view_s"] = round(time.time() - t0, 2)
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--seasons", type=int, default=20)
    ap.add_argument("--probes", default="1,5,10,20", help="seasons at which to measure payload and replay cost ('' = none)")
    ap.add_argument("--dynasty-v", type=int, default=None, help="2 = the dynasty engine before the talent equilibrium (for before/after runs)")
    ap.add_argument("--json", default="")
    ap.add_argument("--world-v", type=int, default=None, help="0 = the NFL world before usage conservation (for before/after runs); default = the current WORLD_VERSION")
    args = ap.parse_args(argv)
    if args.world_v is not None:
        from modules.sim import game_types

        game_types.WORLD_VERSION = args.world_v
    from modules.sim import game_scoring

    model_id = game_scoring.default_model().model_id
    pool, byes = tail_report.pool_from_panel(dataset.load_panel())
    probes = tuple(int(x) for x in args.probes.split(",") if x)
    res = {"model": model_id, "games": [play(s, args.seasons, model_id, pool, byes, probes=probes, dynasty_v=args.dynasty_v) for s in range(1, args.seeds + 1)]}
    text = json.dumps(res, indent=1)
    if args.json:
        open(args.json, "w").write(text)
    print(text)


if __name__ == "__main__":
    main()
