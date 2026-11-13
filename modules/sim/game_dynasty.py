"""Dynasty mode's multi-season machinery: the aged player pool of each later
season, the incoming rookie classes, the rookie draft and the season archive.

Pure and deterministic. A later season's pool (``season_snapshot``) is a pure
function of the season-1 snapshot (which carries the game's seed), so a game
resumed from a checkpoint and one replayed from event 0 see the same league.
Nothing the user does changes how players age or which rookies exist; it only
changes who owns them.

Events (see ``game_state`` for the fold): ``season_complete`` (with the
archive and the retirees), ``rookie_draft_started``, ``rookie_pick``,
``rookie_draft_complete``, ``season_started``.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, Mapping, Sequence

from modules.sim import aging
from modules.sim.game_eval import USER_PARAMS, Evaluator, team_params
from modules.sim.game_setup import value_pool
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import GamePlayer, GameSnapshot, headshot_id
from modules.sim.rng import WorldRng
from modules.sim.synthetic import round_robin
from modules.sim.types import SimPick

FIRST = (
    "Marcus", "Devon", "Tyrese", "Jalen", "Caleb", "Malik", "Brock", "Xavier", "Landon", "Darius", "Elijah", "Kendall",
    "Roman", "Trey", "Isaiah", "Cooper", "Jaylen", "Micah", "Nolan", "Omari", "Preston", "Quentin", "Rashad", "Silas",
    "Tobias", "Ulysses", "Vince", "Wyatt", "Zion", "Anders", "Beau", "Cade", "Declan", "Emmett", "Finn", "Gideon",
)
LAST = (
    "Hale", "Whitaker", "Okoro", "Briggs", "Castillo", "Doyle", "Ellison", "Fontaine", "Graves", "Holloway", "Ingram",
    "Jennings", "Kessler", "Lawson", "Monroe", "Nash", "Osei", "Prescott", "Quarles", "Rivers", "Sutton", "Thorne",
    "Underwood", "Vaughn", "Walker", "Yates", "Zimmer", "Abbott", "Boone", "Crawford", "Dixon", "Easton", "Forbes",
    "Garrett", "Hobbs", "Irvin", "Jolley", "Knox", "Lowe", "Mercer", "Nolan", "Oakes", "Pryor", "Reeves", "Sloan",
)
# Class shape: share of the class by position, then where the position's best rookie sits in the
# current pool (rank, then rank per further rookie): how good a class's best QB is *relative to
# the pool the game already froze*, so the scale follows the league's own scoring.
CLASS_SHARE = {"QB": 0.10, "RB": 0.28, "WR": 0.38, "TE": 0.14}
CLASS_TOP_RANK = {"QB": 7, "RB": 6, "WR": 7, "TE": 5}
CLASS_RANK_STEP = {"QB": 5.0, "RB": 4.2, "WR": 3.6, "TE": 4.0}
ROOKIE_MEAN_DISCOUNT = 0.82  # an unproven player projects below the established player of the same value
ROOKIE_MARKET_BOOST = 1.12  # ...but the dynasty market pays for his years
ROOKIE_AGES = (21.0, 22.0, 23.0)


def season_seed(seed: int, season: int) -> int:
    """The RNG seed season ``season`` plays under (season 1 is the game's own seed,
    so existing games are untouched; later seasons never repeat its dice)."""

    if season <= 1:
        return int(seed)
    return (int(seed) * 1000003 + int(season) * 7919) & ((1 << 62) - 1)


# ----------------------------------------------------------------- the pool


def _class_size(snap: GameSnapshot) -> int:
    s = snap.settings
    return s.rookie_rounds * s.teams + max(10, s.teams)


def rookie_class(
    base: GameSnapshot, vets: Mapping[str, Mapping[str, Any]], season: int
) -> list[dict[str, Any]]:
    """The incoming class for the draft that follows season ``season - 1``: raw
    pool rows (``is_rookie`` set), generated from the (aged) veteran pool's own
    scale. Deterministic in ``(seed, season)``."""

    s = base.settings
    n = _class_size(base)
    year = s.start_year + season - 1  # the draft after season ``season - 1``
    rng = WorldRng(base.seed)
    gen = rng.stream(season, "grookie", 0)
    by_pos: dict[str, list[Mapping[str, Any]]] = {}
    for row in vets.values():
        by_pos.setdefault(row["pos"], []).append(row)
    for pos in by_pos:
        by_pos[pos].sort(key=lambda r: (-r["mean"], r["pid"]))
    teams = sorted({r["nfl_team"] for rows in by_pos.values() for r in rows if r["nfl_team"] not in ("", "FA") and r["pos"] != "DEF"})
    counts = {pos: max(1, int(round(CLASS_SHARE[pos] * n))) for pos in CLASS_SHARE if pos in by_pos}
    used: set[str] = set()
    rows: list[dict[str, Any]] = []
    k = 0
    for pos in sorted(counts):
        pool = by_pos[pos]
        for j in range(counts[pos]):
            rank = min(len(pool) - 1, int(CLASS_TOP_RANK[pos] + CLASS_RANK_STEP[pos] * j))
            ref = pool[rank]
            z = float(gen.standard_normal())
            jitter = math.exp(0.12 * z)
            mean = max(1.5, ref["mean"] * ROOKIE_MEAN_DISCOUNT * jitter)
            market = max(1.0, min(97.0, ref["market"] * ROOKIE_MARKET_BOOST * jitter))
            while True:
                name = f"{FIRST[int(gen.integers(0, len(FIRST)))]} {LAST[int(gen.integers(0, len(LAST)))]}"
                if name not in used:
                    used.add(name)
                    break
            k += 1
            rows.append({
                "pid": f"R{year}-{k:03d}", "name": name, "pos": pos,
                "nfl_team": teams[int(gen.integers(0, len(teams)))] if teams else "FA",
                "age": ROOKIE_AGES[int(gen.choice(3, p=[0.3, 0.5, 0.2]))],
                "market": market, "mean": mean, "sd": max(2.0, mean * 0.5), "injury_weeks": 0,
                "extra": {"is_rookie": 1.0, "years_exp": 0.0, "draft_year": float(year)},
            })
    return rows


def season_snapshot(root: GameSnapshot, season: int) -> GameSnapshot:
    """Season ``season`` (>= 2) of a dynasty game: last season's pool aged one
    year, retirees gone, the new rookie class added, values and ADP recomputed,
    and a fresh schedule."""

    prev = root.season_view(season - 1)
    rng = WorldRng(root.seed)
    rows: dict[str, dict[str, Any]] = {}
    for pid in prev.pids:
        p = prev.players[pid]
        r = rng.stream(season - 1, "gage", aging.stable_key(pid))
        z, u = float(r.standard_normal()), float(r.random())
        age, mean, sd, market, retired = aging.progress(p.pos, p.age, p.mean, p.sd, p.market, z, u)
        if retired:
            continue
        extra = {k: v for k, v in p.extra.items() if k not in ("is_rookie",)}
        if "years_exp" in extra:
            extra["years_exp"] = extra["years_exp"] + 1.0
        elif p.extra.get("is_rookie"):
            extra["years_exp"] = 1.0
        rows[pid] = {
            "pid": pid, "name": p.name, "pos": p.pos, "nfl_team": p.nfl_team, "age": age, "market": market,
            "mean": mean, "sd": sd, "injury_weeks": 0, "extra": extra,
        }
    for row in rookie_class(root, rows, season):
        rows[row["pid"]] = row
    players = value_pool(list(rows.values()), root.settings)
    order = [t.tid for t in root.teams]
    perm = WorldRng(root.seed).stream(season, "gseason", 0).permutation(len(order))
    schedule = round_robin([order[int(i)] for i in perm], root.settings.regular_weeks)
    view = GameSnapshot(
        settings=root.settings, teams=root.teams, players=players, bye_weeks=root.bye_weeks, schedule=schedule,
        scoring_model=root.scoring_model, notes=root.notes, seed=root.seed, start_picks=root.start_picks,
    )
    object.__setattr__(view, "_root", root)
    return view


def retirees(snap: GameSnapshot, next_snap: GameSnapshot) -> list[str]:
    """Players in this season's pool who are gone from next season's."""

    return sorted(p for p in snap.players if p not in next_snap.players)


# ------------------------------------------------------------------ archive


def _pct(rec: Mapping[str, float]) -> float:
    g = rec["w"] + rec["l"] + rec["t"]
    return (rec["w"] + 0.5 * rec["t"]) / g if g else 0.0


def season_archive(snap: GameSnapshot, state: GameState, champion: str = "") -> dict[str, Any]:
    """One finished season in a few numbers (called right after the champion is
    known, before the offseason): the per-year row of the dynasty summary."""

    from modules.sim.game_engine import standing_rows  # lazy: game_engine imports this module

    user = snap.user_team.tid
    rows = standing_rows(snap, state)
    results = dict((state.playoff or {}).get("results", {}))
    champ = champion or state.champion
    if champ:
        results[champ] = "champion"
    me = next(r for r in rows if r["team_id"] == user)
    roster = state.rosters[user]
    scorers = sorted(((sum(state.games_played(p)), p) for p in roster if p in snap.players), reverse=True)[:3]
    ages = [snap.players[p].age for p in roster if p in snap.players]
    return {
        "season_no": state.season_no, "year": snap.settings.start_year + state.season_no - 1,
        "champion": {"team_id": champ, "name": snap.team(champ).name, "is_you": champ == user} if champ else None,
        "you": {
            "rank": me["rank"], "wins": me["wins"], "losses": me["losses"], "ties": me["ties"], "pf": me["pf"], "pa": me["pa"],
            "seed": me["seed"], "playoff_result": results.get(user, "missed"),
            "made_playoffs": bool(state.playoff and user in state.playoff["seeds"]),
            "avg_age": round(sum(ages) / len(ages), 1) if ages else None,
            "top_scorers": [{"id": p, "name": snap.players[p].name, "pos": snap.players[p].pos, "pts": round(pts, 1)} for pts, p in scorers],
        },
        "standings": [
            {"rank": r["rank"], "team_id": r["team_id"], "name": r["name"], "is_you": r["is_you"], "wins": r["wins"],
             "losses": r["losses"], "ties": r["ties"], "pf": r["pf"], "playoff_result": results.get(r["team_id"], "missed")}
            for r in rows
        ],
    }


def dynasty_summary(snap: GameSnapshot, state: GameState) -> dict[str, Any]:
    """The multi-year view: titles, finish by year, totals."""

    seasons = [dict(a) for a in state.seasons]
    titles = sum(1 for a in seasons if a["champion"] and a["champion"]["is_you"])
    finishes = [a["you"]["rank"] for a in seasons]
    wins = sum(a["you"]["wins"] for a in seasons)
    losses = sum(a["you"]["losses"] for a in seasons)
    best = min(seasons, key=lambda a: (a["you"]["rank"], -a["you"]["wins"]), default=None)
    S = snap.settings
    return {
        "mode": "dynasty", "seasons_total": S.seasons, "seasons_played": len(seasons), "start_year": S.start_year,
        "complete": state.status == "complete", "titles": titles, "playoff_trips": sum(1 for a in seasons if a["you"]["made_playoffs"]),
        "avg_finish": round(sum(finishes) / len(finishes), 2) if finishes else None, "wins": wins, "losses": losses,
        "best_season": {"year": best["year"], "rank": best["you"]["rank"], "record": f"{best['you']['wins']}-{best['you']['losses']}"} if best else None,
        "by_year": [{
            "season_no": a["season_no"], "year": a["year"], "rank": a["you"]["rank"], "record": f"{a['you']['wins']}-{a['you']['losses']}" + (f"-{a['you']['ties']}" if a["you"]["ties"] else ""),
            "pf": a["you"]["pf"], "playoff_result": a["you"]["playoff_result"], "champion": a["champion"], "avg_age": a["you"]["avg_age"],
            "top_scorers": a["you"]["top_scorers"], "standings": a["standings"],
        } for a in seasons],
        "rookie_drafts": [{"year": d["year"], "picks": [x for x in d["picks"] if x["team"] == snap.user_team.tid]} for d in state.rookie_log],
        "picks_held": len(state.picks_of(snap.user_team.tid)),
    }


# --------------------------------------------------------------- rookie draft

_TIER = {"missed": 0, "semifinal": 10, "runner_up": 11, "champion": 12}


def _tier(label: str) -> int:
    if label in _TIER:
        return _TIER[label]
    if label.startswith("lost_round_"):
        return int(label.rsplit("_", 1)[1])
    return 0


def rookie_order(snap: GameSnapshot, state: GameState, year: int) -> tuple[list[str], dict[str, int]]:
    """Pick ids in draft order and each original team's slot (1 = first pick).
    Teams that missed the playoffs pick first, worst record first, then playoff
    teams by how far they went, the champion last. Linear (non-snake) rounds."""

    results = (state.playoff or {}).get("results", {})
    order = sorted(
        snap.tids,
        key=lambda t: (_tier(results.get(t, "missed")), round(_pct(state.stand[t]), 9), round(state.stand[t]["pf"], 6), -snap.team(t).coin),
    )
    slots = {t: i + 1 for i, t in enumerate(order)}
    pick_ids = [f"pick:{year}:{r}:{t}" for r in range(1, snap.settings.rookie_rounds + 1) for t in order]
    return pick_ids, slots


def rookies_available(snap: GameSnapshot, state: GameState) -> list[str]:
    owned = state.owner_map()
    return sorted(
        (pid for pid, p in snap.players.items() if p.extra.get("is_rookie") and pid not in owned),
        key=lambda pid: (snap.players[pid].adp, pid),
    )


def start_rookie_draft(em: Emitter) -> None:
    state, snap = em.state, em.snap
    off = state.offseason
    if state.status != "offseason" or off is None or off["stage"] != "review":
        from modules.sim.game_types import GameError

        raise GameError("wrong_phase", "The rookie draft is not ready to start.", phase=state.status)
    order, slots = rookie_order(snap, state, off["year"])
    em.emit(state.week, "engine", "rookie_draft_started", order=order, slots=slots)


def choose_rookie(snap: GameSnapshot, state: GameState, ev: Evaluator, tid: str, n: int, seed: int, *, human: bool = False) -> str:
    """The rookie ``tid`` takes at pick ``n``: the best by the team's own worth
    (a contender leans on projection, a rebuilder on dynasty value and youth) plus
    a need bump and, for AI, taste noise sampled with Gumbel draws keyed by (seed, pick)."""

    avail = rookies_available(snap, state)
    if not avail:
        from modules.sim.game_types import GameError

        raise GameError("pool_exhausted", "No rookies left to draft.")
    params = USER_PARAMS if human else team_params(snap, tid)
    roster = [snap.players[p] for p in state.rosters[tid] if p in snap.players]
    starters = {pos: max(1, sum(1 for s in snap.settings.slots if s == pos)) for pos in ("QB", "RB", "WR", "TE")}
    starters["QB"] += snap.settings.slots.count("SUPER_FLEX")
    scored = []
    taste = WorldRng(seed).stream(0, "grdraft", 1000 + snap.tids.index(tid)).standard_normal(len(avail) + 8)
    for i, pid in enumerate(avail[:30]):
        p = snap.players[pid]
        have = sum(1 for r in roster if r.pos == p.pos)
        need = 4.0 * max(0.0, starters.get(p.pos, 1) + 1 - have) / (starters.get(p.pos, 1) + 1)
        noise = 0.0 if human else 1.0 * float(taste[i])
        scored.append((ev.worth(params, pid) + need + noise, pid))
    scored.sort(key=lambda t: (-t[0], t[1]))
    if human:
        return scored[0][1]
    top = scored[:4]
    g = WorldRng(seed).stream(0, "grdraft", n).gumbel(size=len(top))
    best = max(range(len(top)), key=lambda i: (top[i][0] / 2.5 + float(g[i]), -i))
    return top[best][1]


def run_ai_rookie_picks(em: Emitter, seed: int) -> list[dict[str, Any]]:
    """Resolve AI rookie picks until the user is on the clock (or the draft ends)."""

    state, snap = em.state, em.snap
    off = state.offseason
    user = snap.user_team.tid
    made: list[dict[str, Any]] = []
    while off["stage"] == "rookie_draft" and off["pick_index"] < len(off["order"]):
        n = off["pick_index"]
        pick = off["order"][n]
        tid = state.pick_owner[pick]
        if tid == user:
            break
        made.append(_emit_rookie(em, tid, choose_rookie(snap, state, Evaluator(snap, state), tid, n, seed), False))
    if off["stage"] == "rookie_draft" and off["pick_index"] >= len(off["order"]):
        finish_rookie_draft(em, seed)
    return made


def _emit_rookie(em: Emitter, tid: str, pid: str, auto: bool) -> dict[str, Any]:
    state = em.state
    off = state.offseason
    n = off["pick_index"]
    pick = off["order"][n]
    parts = pick.split(":")
    rnd, orig = int(parts[2]), parts[3]
    ev = em.emit(state.week, "user" if tid == em.snap.user_team.tid else tid, "rookie_pick",
                 n=n, round=rnd, pick=pick, orig=orig, team=tid, pid=pid, auto=auto)
    return ev["payload"]


def user_rookie_pick(em: Emitter, pid: str, seed: int, *, auto: bool = False) -> list[dict[str, Any]]:
    from modules.sim.game_types import GameError

    state, snap = em.state, em.snap
    off = state.offseason
    if state.status != "offseason" or off is None or off["stage"] != "rookie_draft" or off["pick_index"] >= len(off["order"]):
        raise GameError("wrong_phase", "The rookie draft is not in progress.", phase=state.status)
    user = snap.user_team.tid
    if state.pick_owner[off["order"][off["pick_index"]]] != user:
        raise GameError("not_your_turn", "An AI team is on the clock.")
    if pid not in snap.players or not snap.players[pid].extra.get("is_rookie"):
        raise ValueError("That is not a rookie in this class.")
    if pid in state.owner_map():
        raise GameError("player_taken", "That rookie has already been drafted.")
    made = [_emit_rookie(em, user, pid, auto)]
    made.extend(run_ai_rookie_picks(em, seed))
    return made


def auto_rookie_draft(em: Emitter, seed: int) -> list[dict[str, Any]]:
    state, snap = em.state, em.snap
    made = run_ai_rookie_picks(em, seed)
    off = state.offseason
    while off["stage"] == "rookie_draft":
        pid = choose_rookie(snap, state, Evaluator(snap, state), snap.user_team.tid, off["pick_index"], seed, human=True)
        made.extend(user_rookie_pick(em, pid, seed, auto=True))
    return made


def finish_rookie_draft(em: Emitter, seed: int) -> None:
    """The rookie draft is over: AI teams cut down to the roster limit, next
    draft's picks are created, and the user may trade and cut before the season."""

    from modules.sim.game_actions import enforce_roster_cap

    state, snap = em.state, em.snap
    S = snap.settings
    year = state.offseason["year"]
    new_year = year + S.pick_years
    new_picks = [
        {"season": new_year, "round": r, "orig": t, "owner": t}
        for r in range(1, S.rookie_rounds + 1) for t in sorted(snap.tids)
    ]
    em.emit(state.week, "engine", "rookie_draft_complete", year=year, new_picks=new_picks)
    ev = Evaluator(snap, state)
    for tid in snap.tids:
        enforce_roster_cap(em, ev, tid)


def start_next_season(em: Emitter, seed: int) -> None:
    """Close the offseason: AI rosters are cut and holes filled, lineups set, week 1."""

    from modules.sim.game_actions import ai_manage_reserves
    from modules.sim.game_engine import _fill_holes, generate_offers
    from modules.sim.game_types import GameError

    state, snap = em.state, em.snap
    off = state.offseason
    if state.status != "offseason" or off is None or off["stage"] != "cutdown":
        raise GameError("wrong_phase", "The offseason is not ready to end.", phase=state.status)
    over = len(state.rosters[snap.user_team.tid]) - snap.settings.roster_limit
    if over > 0:
        raise GameError("roster_over_limit", f"Cut {over} player(s) before the season starts.", cuts_needed=over)
    ev = Evaluator(snap, state)
    for tid in snap.tids:
        if not snap.team(tid).is_user:
            _fill_holes(em, ev, tid)
            ai_manage_reserves(em, ev, tid)
    ev = Evaluator(snap, state)
    for tid in snap.tids:
        slots, _ = ev.best_lineup(state.rosters[tid], 1)
        em.emit(1, "engine", "lineup_set", team=tid, slots=slots, auto=True)
    em.emit(1, "engine", "season_started", season_no=state.season_no + 1, year=snap.settings.start_year + state.season_no)
    generate_offers(em, snap, state, seed, 1)


__all__ = [
    "season_seed", "season_snapshot", "rookie_class", "retirees", "season_archive", "dynasty_summary", "rookie_order",
    "rookies_available", "start_rookie_draft", "choose_rookie", "run_ai_rookie_picks", "user_rookie_pick",
    "auto_rookie_draft", "finish_rookie_draft", "start_next_season",
]
