"""Realism P1 harness (docs/audits/2026-11-realism-advice-audit-2.md): before / after tables for ``wire_v`` (waiver contests), and the
later ``need_v`` / ``cap_v`` / ``posture_v`` tables as they are added.

    python -m modules.sim.calibration.realism_p1_report wire [--seeds 8] [--flags '{"wire_v": 0}']

Redraft games on the committed 2025 panel pool, 12 teams, the user rotating through draft slots. Never touches data/players.db.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import replace
from typing import Any

from modules.sim import game_scoring
from modules.sim.calibration import dataset, tail_report
from modules.sim.game_actions import queue_claim
from modules.sim.game_draft import DraftContext, auto_for_user, run_ai_picks
from modules.sim.game_engine import advance, finish_draft, waiver_order
from modules.sim.game_eval import USER_PARAMS, Evaluator
from modules.sim.game_setup import build_snapshot
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import GameSettings


def _pool():
    prows = dataset.load_panel()
    return tail_report.pool_from_panel(prows)


def _new_game(seed: int, flags: dict[str, int], extra: dict[str, Any] | None = None, events: list | None = None):
    pool, byes = _pool()
    raw = {"user_slot": 1 + (seed * 5) % 12, "scoring": "ppr", "teams": 12, **(extra or {})}
    settings = replace(GameSettings.parse(raw), **flags)
    model_id = game_scoring.default_model().model_id
    snap = build_snapshot(pool, byes, settings, seed, scoring_model=model_id)
    state = GameState(snap)
    em = Emitter(state, snap)
    ctx = DraftContext(snap, state)
    run_ai_picks(ctx, em, seed)
    auto_for_user(ctx, em, seed)
    finish_draft(em, snap, state, seed)
    if events is not None:  # the draft's events, for a replay check
        events.extend(em.events)
    return snap, state


def _user_queue_best(em: Emitter, snap, state) -> int:
    """The edge the audit describes: every week the user queues the three most valuable free agents against his three least valuable players."""

    user = snap.user_team.tid
    ev = Evaluator(snap, state)
    owned = state.owner_map()
    fas = sorted((p for p in snap.pids if p not in owned and state.out.get(p, 0) == 0), key=lambda p: (-ev.worth(USER_PARAMS, p), p))
    roster = sorted(state.rosters[user], key=lambda p: (ev.worth(USER_PARAMS, p), p))
    n = 0
    for add, drop in zip(fas[:3], roster[:3]):
        try:
            queue_claim(em, add, drop, None)
            n += 1
        except (ValueError, Exception):  # noqa: BLE001 - a rejected queue is just not counted
            pass
    return n


def wire_table(seeds: int, flags: dict[str, int]) -> dict[str, Any]:
    won = lost = 0
    by_pri = {"top": [0, 0], "bottom": [0, 0]}
    ai_claims = 0
    for seed in range(1, seeds + 1):
        snap, state = _new_game(seed, flags)
        user = snap.user_team.tid
        while state.status == "in_season":
            em = Emitter(state, snap)
            if state.week <= snap.settings.regular_weeks - 1:
                _user_queue_best(em, snap, state)
            order = waiver_order(snap, state)
            half = "top" if order.index(user) < len(order) // 2 else "bottom"
            seen = len(state.transactions)
            before = len(em.events) if hasattr(em, "events") else 0
            advance(em, snap, state, seed)
            for e in (em.events[before:] if hasattr(em, "events") else []):
                if e.get("type") != "waiver_result":
                    continue
                p = e["payload"] if "payload" in e else e
                if p.get("team") == user and p.get("claim_id"):
                    ok = bool(p.get("ok"))
                    if ok:
                        won += 1
                    elif p.get("reason") == "taken":
                        lost += 1
                    else:
                        continue
                    by_pri[half][0 if ok else 1] += 1
                elif p.get("team") != user:
                    ai_claims += 1
            del seen
    total = max(1, won + lost)
    rate = lambda a: round(a[0] / max(1, a[0] + a[1]), 3)  # noqa: E731
    return {
        "user_claims_contested_or_won": won + lost, "user_win_rate": round(won / total, 3),
        "win_rate_when_priority_top_half": rate(by_pri["top"]), "win_rate_when_priority_bottom_half": rate(by_pri["bottom"]),
        "ai_claims_per_game": round(ai_claims / seeds, 1),
    }


def need_table(seeds: int, flags: dict[str, int]) -> dict[str, Any]:
    """The Needs / Strength tags against real holes. Per format (one QB / superflex), every league-week from week 2 on:
    how many of the 12 teams carry a tag at each position, and what the tag predicts (the AI team's realized points from that position's starters
    that week against the league mean of the same position and week: a real need should score under 1.0, a strength over)."""

    from modules.sim.game_need import position_report

    out: dict[str, Any] = {}
    for fmt, extra in (("one_qb", {}), ("superflex", {"superflex": True})):
        counts: dict[str, list[int]] = {}
        str_counts: dict[str, list[int]] = {}
        realized: dict[str, dict[str, list[float]]] = {"need": {}, "ok": {}, "strength": {}}
        empty = {"need": [0, 0], "ok": [0, 0], "strength": [0, 0]}
        qb_need_sf = 0
        for seed in range(1, seeds + 1):
            snap, state = _new_game(seed, flags, extra)
            user = snap.user_team.tid
            while state.status == "in_season":
                w = state.week
                if w >= 2:
                    ev = Evaluator(snap, state)
                    rep = position_report(snap, ev)
                    for pos in {e["pos"] for e in rep[user]}:
                        counts.setdefault(pos, []).append(sum(1 for t in snap.tids if next(e for e in rep[t] if e["pos"] == pos)["level"] == "need"))
                        str_counts.setdefault(pos, []).append(sum(1 for t in snap.tids if next(e for e in rep[t] if e["pos"] == pos)["level"] == "strength"))
                    tags = {(t, e["pos"]): e["level"] for t in snap.tids for e in rep[t]}
                else:
                    tags = {}
                em = Emitter(state, snap)
                advance(em, snap, state, seed)
                if tags and state.week == w + 1:
                    byposweek: dict[str, dict[str, float]] = {}
                    for t in snap.tids:
                        if t == user:
                            continue
                        for pos in {p for (_, p) in tags}:
                            pts = 0.0
                            holes = 0
                            for slot, pid in state.lineups[t]:
                                if pid and snap.players[pid].pos == pos and slot == pos:
                                    v = state.points.get(pid, [])
                                    pts += v[w - 1] if len(v) >= w and v[w - 1] is not None else 0.0
                                elif not pid and slot == pos:
                                    holes += 1
                            byposweek.setdefault(pos, {})[t] = pts
                            empty[tags[(t, pos)]][0] += int(holes > 0)
                            empty[tags[(t, pos)]][1] += 1
                    for pos, d in byposweek.items():
                        mean = sum(d.values()) / max(1, len(d))
                        if mean <= 0:
                            continue
                        for t, v in d.items():
                            realized[tags[(t, pos)]].setdefault(pos, []).append(v / mean)
        out[fmt] = {
            "teams_tagged_need_per_league_week": {k: {"mean": round(sum(v) / len(v), 2), "min": min(v), "max": max(v)} for k, v in sorted(counts.items())},
            "teams_tagged_strength_per_league_week": {k: round(sum(v) / len(v), 2) for k, v in sorted(str_counts.items())},
            "realized_pts_vs_league_mean_by_tag": {tag: {k: round(sum(v) / len(v), 3) for k, v in sorted(d.items())} for tag, d in realized.items()},
            "empty_starting_slot_rate_by_tag": {k: round(a / max(1, b), 4) for k, (a, b) in empty.items()},
        }
    del qb_need_sf
    return out


def cap_table(seeds: int, flags: dict[str, int]) -> dict[str, Any]:
    """Position counts after the startup draft (AI teams, and the user's auto-pick) and at the end of the season (AI teams), per format."""

    out: dict[str, Any] = {}
    for fmt, extra in (("one_qb", {}), ("superflex", {"superflex": True})):
        draft_ai: dict[str, Counter] = {p: Counter() for p in ("QB", "RB", "WR", "TE")}
        draft_user: dict[str, Counter] = {p: Counter() for p in ("QB", "RB", "WR", "TE")}
        final_ai: dict[str, Counter] = {p: Counter() for p in ("QB", "RB", "WR", "TE")}
        for seed in range(1, seeds + 1):
            snap, state = _new_game(seed, flags, extra)
            user = snap.user_team.tid

            def tally(into, tids):
                for t in tids:
                    c = Counter(snap.players[p].pos for p in state.rosters[t])
                    for pos in into:
                        into[pos][c.get(pos, 0)] += 1

            tally(draft_ai, [t for t in snap.tids if t != user])
            tally(draft_user, [user])
            while state.status == "in_season":
                advance(Emitter(state, snap), snap, state, seed)
            tally(final_ai, [t for t in snap.tids if t != user])

        def share(cnt: Counter) -> dict[str, float]:
            n = sum(cnt.values()) or 1
            return {str(k): round(v / n, 3) for k, v in sorted(cnt.items())}

        out[fmt] = {
            "AI_after_draft": {p: share(c) for p, c in draft_ai.items()},
            "user_auto_after_draft": {p: share(c) for p, c in draft_user.items()},
            "AI_end_of_season": {p: share(c) for p, c in final_ai.items()},
        }
    return out


def _season_runs(seed: int, flags: dict[str, int], dynasty: bool, seasons: int):
    """Yield ``(snap, state, season_seed)`` at the start of each season; the caller plays it (``advance`` until the regular season ends), then asks for the next.
    Redraft: one season. Dynasty: ``seasons`` seasons on the synthetic pool with the rookie draft between them (user passive)."""

    if not dynasty:
        snap, state = _new_game(seed, flags)
        yield snap, state, seed
        return
    from modules.sim import game_dynasty as dyn
    from modules.sim.game_actions import cut_player
    from modules.sim.synthetic import build_synthetic_pool

    rows, byes = build_synthetic_pool(7)
    settings = replace(GameSettings.parse({"mode": "dynasty", "teams": 12, "user_slot": 1 + (seed * 5) % 12, "start_year": 2026, "seasons": seasons, "rookie_rounds": 3}), **flags)
    root = build_snapshot(rows, byes, settings, seed, scoring_model=game_scoring.default_model().model_id)
    state = GameState(root)
    em = Emitter(state, root)
    auto_for_user(DraftContext(root, state), em, seed)
    finish_draft(em, root, state, seed)
    while True:
        snap = root.season_view(state.view_no)
        sd = dyn.season_seed(seed, state.view_no)
        yield snap, state, sd
        if state.status != "offseason":
            return
        snap = root.season_view(state.view_no)
        sd = dyn.season_seed(seed, state.view_no)
        em = Emitter(state, snap)
        dyn.start_rookie_draft(em)
        dyn.run_ai_rookie_picks(em, sd)
        dyn.auto_rookie_draft(em, sd)
        user = snap.user_team.tid
        while len(state.rosters[user]) > snap.settings.roster_limit:
            ev = Evaluator(snap, state)
            cut_player(em, min(state.rosters[user], key=lambda p: (ev.worth(USER_PARAMS, p), p)))
        dyn.start_next_season(em, sd)


def posture_table(seeds: int, flags: dict[str, int], dynasty: bool = False, seasons: int = 3) -> dict[str, Any]:
    """AI trade and waiver behaviour by standing, and the stability of the posture. Each AI team-week from week 5 is placed in a tier by its playoff odds
    at the start of the week (win >= 65%, mid, out <= 15%); for every AI-AI trade the team's side is scored on what it took in against what it sent out
    (``prod``: rest-of-season weekly mean, a win-now measure; ``age``: years), and every waiver add on its production. Posture flips per team-season,
    and the flips a threshold-only rule (no hysteresis, no tenure) would have made on the same odds, are counted."""

    from modules.sim.game_posture import ENTER_BUY, ENTER_SELL, playoff_odds
    from modules.sim.types import is_pick_id

    tiers = ("in", "mid", "out")

    def tier(o: float) -> str:
        return "in" if o >= ENTER_BUY else "out" if o <= 0.15 else "mid"

    weeks = Counter()
    trade_sides = {t: Counter() for t in tiers}
    prod = {t: [] for t in tiers}
    age = {t: [] for t in tiers}
    add_prod = {t: [] for t in tiers}
    flips = []
    naive = []
    stance_weeks = {"made": Counter(), "missed": Counter()}
    persona_wins = {"high": [], "low": []}
    runs = ((seed, snap, state, sd) for seed in range(1, seeds + 1) for snap, state, sd in _season_runs(seed, flags, dynasty, seasons))
    for seed, snap, state, sd in runs:
        user = snap.user_team.tid
        series: dict[str, list[float]] = {t: [] for t in snap.tids}
        seen = len(state.transactions)
        last_stance: dict[str, str] = {}
        n_flips: Counter = Counter()
        weekly: list[tuple[int, dict[str, str]]] = []
        while state.status == "in_season":
            w = state.week
            odds = playoff_odds(snap, state) if w >= 5 else {}
            for t, o in odds.items():
                series[t].append(o)
            em = Emitter(state, snap)
            advance(em, snap, state, sd)
            if w >= 5:
                for t in snap.tids:
                    if t == user:
                        continue
                    weeks[tier(odds[t])] += 1
                    cur = (state.posture.get(t) or {}).get("stance", "")
                    if cur != last_stance.get(t, ""):
                        n_flips[t] += 1
                    last_stance[t] = cur
                weekly.append((w, {t: (state.posture.get(t) or {}).get("stance", "") for t in snap.tids}))
            ev = Evaluator(snap, state)
            for tx in state.transactions[seen:]:
                if tx["type"] == "trade" and tx.get("source") == "ai_ai" and w >= 5 and odds:
                    for me, sent, got in ((tx["team_a"], tx["give"], tx["get"]), (tx["team_b"], tx["get"], tx["give"])):
                        ps = [p for p in sent if not is_pick_id(p)]
                        pg = [p for p in got if not is_pick_id(p)]
                        if not ps or not pg:
                            continue
                        tr = tier(odds[me])
                        trade_sides[tr]["n"] += 1
                        prod[tr].append(sum(ev.ros_mean(p) for p in pg) - sum(ev.ros_mean(p) for p in ps))
                        age[tr].append(sum(snap.players[p].age for p in pg) / len(pg) - sum(snap.players[p].age for p in ps) / len(ps))
                elif tx["type"] == "waiver" and w >= 5 and odds and tx["team"] != user and tx["week"] == w:
                    add_prod[tier(odds[tx["team"]])].append(ev.ros_mean(tx["add"]))
            seen = len(state.transactions)
        order = sorted(snap.tids, key=lambda t: (-state.stand[t]["w"], -state.stand[t]["pf"]))
        made = set(order[: snap.settings.playoff_teams])
        for t in snap.tids:
            if t == user:
                continue
            flips.append(n_flips[t])
            sig = ""
            c = 0
            for o in series[t]:
                new = "buy" if o >= ENTER_BUY else "sell" if o <= ENTER_SELL else ""
                if new != sig:
                    c += 1
                sig = new
            naive.append(c)
            for _, st in weekly:
                stance_weeks["made" if t in made else "missed"][st[t] or "hold"] += 1
            base = snap.team(t).horizon
            persona_wins["high" if base >= 0.6 else "low"].append(state.stand[t]["w"])
        while state.status == "playoffs":  # finish the season so a dynasty can move on to its offseason
            advance(Emitter(state, snap), snap, state, sd)
    mean = lambda xs: round(sum(xs) / len(xs), 2) if xs else None  # noqa: E731
    share = lambda c: {k: round(v / max(1, sum(c.values())), 3) for k, v in sorted(c.items())}  # noqa: E731
    return {
        "ai_team_weeks_by_tier": dict(weeks),
        "trades_per_100_team_weeks": {t: round(100 * trade_sides[t]["n"] / max(1, weeks[t]), 2) for t in tiers},
        "trade_net_prod_taken_in": {t: mean(prod[t]) for t in tiers},
        "trade_age_change_years": {t: mean(age[t]) for t in tiers},
        "waiver_add_prod": {t: mean(add_prod[t]) for t in tiers},
        "posture_changes_per_team_season": mean(flips),
        "threshold_only_changes_per_team_season": mean(naive),
        "max_posture_changes_in_a_season": max(flips) if flips else 0,
        "stance_share_of_team_weeks_by_outcome": {k: share(v) for k, v in stance_weeks.items()},
        "avg_wins_by_persona_horizon": {k: mean(v) for k, v in persona_wins.items()},
    }


def posture_values(seeds: int, flags: dict[str, int]) -> dict[str, Any]:
    """The same AI managers' valuations under each posture (dynasty, week 8 of the first season): what a buyer, a team standing pat and a seller each pay, per
    market point, for a veteran (age 28+), a prime player (25-27) and a young player (24 or under) among the 150 players with the most market value, and for a
    healthy producer against a slow start with the same market value. Posture moves the AI's horizon by +0.25 / -0.30 (``game_posture``)."""

    from modules.sim.game_eval import team_params
    from modules.sim.game_posture import BUY, SELL, apply_posture

    rows: dict[str, dict[str, list[float]]] = {st: {"vet": [], "prime": [], "young": []} for st in ("hold", "buy", "sell")}
    for seed in range(1, seeds + 1):
        snap, state, sd = next(_season_runs(seed, flags, True, 3))
        while state.week < 8:
            advance(Emitter(state, snap), snap, state, sd)
        ev = Evaluator(snap, state)
        top = sorted(snap.pids, key=lambda p: -snap.players[p].market)[:150]
        for t in snap.teams:
            if t.is_user:
                continue
            base = team_params(snap, t.tid)
            for name, stance in (("hold", ""), ("buy", BUY), ("sell", SELL)):
                params = apply_posture(base, stance)
                for pid in top:
                    pl = snap.players[pid]
                    grp = "vet" if pl.age >= 28 else "young" if pl.age <= 24 else "prime"
                    rows[name][grp].append(ev.worth(params, pid) / max(1.0, pl.market))
    mean = lambda xs: round(sum(xs) / len(xs), 3) if xs else None  # noqa: E731
    return {name: {g: mean(v) for g, v in groups.items()} for name, groups in rows.items()}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("table", choices=["wire", "need", "cap", "posture", "values"])
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--dynasty", action="store_true", help="posture: a 3-season dynasty (age and the future matter) instead of a redraft season")
    ap.add_argument("--seasons", type=int, default=3)
    ap.add_argument("--flags", default="{}", help="JSON of GameSettings overrides, e.g. '{\"wire_v\": 0}'")
    args = ap.parse_args(argv)
    flags = {str(k): int(v) for k, v in json.loads(args.flags).items()}
    out = ({"posture": lambda n, f: posture_table(n, f, args.dynasty, args.seasons), "values": posture_values}.get(args.table) or {"wire": wire_table, "need": need_table, "cap": cap_table}[args.table])(args.seeds, flags)
    print(json.dumps(out, indent=1, separators=(",", ": ")) if args.table == "wire" else "\n".join(f"{k}: {json.dumps(v)}" for k, v in out.items()))


if __name__ == "__main__":
    main()
