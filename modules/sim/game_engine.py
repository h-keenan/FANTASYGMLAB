"""The weekly step engine: resolve ONE week from the current state.

``advance`` runs the user-visible Advance: validate, then ``run_week`` for the
current week (waivers in priority order, AI trades, lineups, scoring, injuries,
standings, playoff seeding/rounds, next week's AI offers), then, if the user is
out of the playoffs, the remaining playoff weeks in the same call. Every step
appends events through the ``Emitter``; the state is only ever changed by the
fold in ``game_state``, so a resumed game and a replayed game agree.

Engine events: ``waiver_result``, ``trade`` (source ``ai_ai``), ``drop``,
``lineup_set`` (AI teams, and the user's auto-fills), ``week_scored``,
``injury``, ``playoff_seeded``, ``inbox_offer``, ``season_complete``,
``week_advanced`` (carries the recap and always closes a week).
"""

from __future__ import annotations

from typing import Any, Sequence

from modules.sim import game_dynasty as dyn
from modules.sim.game_actions import ai_manage_reserves, execute_trade
from modules.sim.game_ai import (
    MAX_AI_TRADES_PER_WEEK,
    MAX_OFFERS_PER_WEEK,
    PARTNERS_PER_SEARCH,
    TradeDesk,
    ai_lineup,
    ai_waiver_claim,
    offer_message,
)
from modules.sim.game_draft import draft_recap
from modules.sim.game_eval import Evaluator, team_params
from modules.sim.game_scoring import PlayerWeek, ScoringModel, get_model
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import GameError, GameSnapshot, headshot_id, slot_positions
from modules.sim.lineup import pick_lineup
from modules.sim.rng import WorldRng
from modules.sim.types import is_pick_id

INJURY_SEASON_ENDING = 0.06
INJURY_SEASON_ENDING_WEEKS = 9


# ------------------------------------------------------------------ scoring


class ScoringSession:
    """Season profiles and weekly draws for one game, via the scoring adapter.
    Every draw comes from a stream keyed by (seed, week, player), so it never
    depends on call order or on who else was drawn."""

    def __init__(self, snap: GameSnapshot, seed: int, model: ScoringModel) -> None:
        self.snap = snap
        self.seed = seed
        self.model = model
        self.rng = WorldRng(seed)
        self.scoring = snap.settings.scoring_settings
        self._profiles: dict[str, Any] = {}
        self._maps: dict[str, dict[str, Any]] = {}

    def _mapping(self, pid: str) -> dict[str, Any]:
        if pid not in self._maps:
            m = self.snap.players[pid].model_mapping()
            m["bye_week"] = self.snap.bye_of(pid)  # the game's schedule is the truth (0 = none)
            self._maps[pid] = m
        return self._maps[pid]

    def profile(self, pid: str) -> Any:
        if pid not in self._profiles:
            rng = self.rng.stream(0, "gprofile", self.snap.index[pid])
            self._profiles[pid] = self.model.profile(self._mapping(pid), rng)
        return self._profiles[pid]

    def week(self, pid: str, week: int, role_mult: float | None = None) -> PlayerWeek:
        """``role_mult``: the team-level role multiplier for this week (``Evaluator.role_mult``), passed only
        for models that resolve team roles (player-model-3+); older models never see it."""

        rng = self.rng.stream(week, "gscore", self.snap.index[pid])
        if role_mult is not None and self.model.team_roles:
            return self.model.week(self._mapping(pid), self.profile(pid), week, rng, self.scoring, role_mult=role_mult)
        return self.model.week(self._mapping(pid), self.profile(pid), week, rng, self.scoring)

    def weeks_out(self, pid: str, week: int, res: PlayerWeek) -> int:
        """Injury length: the player model's own decision when it gives one; the legacy
        random draw only for the labelled FallbackModel (replay safety for old saves)."""

        return res.out_weeks if res.out_weeks is not None else self.injury_weeks(pid, week)

    def injury_weeks(self, pid: str, week: int) -> int:
        rng = self.rng.stream(week, "ginjury", self.snap.index[pid])
        weeks = 1 + int(float(rng.random()) * 5)
        if float(rng.random()) < INJURY_SEASON_ENDING:
            weeks = INJURY_SEASON_ENDING_WEEKS
        return weeks


def session_for(snap: GameSnapshot, seed: int) -> ScoringSession:
    """One session per (snapshot, seed): profiles are cached on the snapshot."""

    session = getattr(snap, "_session", None)
    if session is None or session.seed != seed:
        session = ScoringSession(snap, seed, get_model(snap.scoring_model))
        object.__setattr__(snap, "_session", session)
    return session


# ----------------------------------------------------------------- standings


def _pct(rec: dict[str, float]) -> float:
    games = rec["w"] + rec["l"] + rec["t"]
    return (rec["w"] + 0.5 * rec["t"]) / games if games else 0.0


def rank_teams(snap: GameSnapshot, state: GameState) -> list[str]:
    """Standings order (and playoff seeding): win pct first, then the game's
    ``tiebreaker``.

    ``points_for`` (default, like Sleeper): points for, then head-to-head among
    the tied group, then fewer points against, then the fixed coin.
    ``head_to_head`` (what saves from before the setting use): head-to-head
    among the tied group, then points for, then the coin."""

    pct = {t: round(_pct(state.stand[t]), 9) for t in snap.tids}
    groups: dict[float, list[str]] = {}
    for t in snap.tids:
        groups.setdefault(pct[t], []).append(t)

    def h2h(t: str, group: list[str]) -> float:
        if len(group) < 2:
            return 0.0
        wins = games = 0.0
        for opp in group:
            if opp == t:
                continue
            w, l, ties = state.h2h[t].get(opp, [0, 0, 0])
            wins += w + 0.5 * ties
            games += w + l + ties
        return wins / games if games else 0.0

    legacy = snap.settings.tiebreaker == "head_to_head"
    key = {}
    for group in groups.values():
        for t in group:
            rec = state.stand[t]
            if legacy:
                key[t] = (-pct[t], -h2h(t, group), -rec["pf"], snap.team(t).coin)
            else:
                key[t] = (-pct[t], -round(rec["pf"], 6), -h2h(t, group), round(rec["pa"], 6), snap.team(t).coin)
    return sorted(snap.tids, key=lambda t: key[t])


def waiver_order(snap: GameSnapshot, state: GameState) -> list[str]:
    """Worst record first (ties: fewer points, then the coin reversed)."""

    return sorted(
        snap.tids,
        key=lambda t: (_pct(state.stand[t]), state.stand[t]["pf"], -snap.team(t).coin),
    )


def bracket_slots(seeds: Sequence[str]) -> list[str | None]:
    size = 1
    while size < len(seeds):
        size *= 2
    order = [1]
    while len(order) < size:
        total = len(order) * 2 + 1
        order = [x for s in order for x in (s, total - s)]
    return [seeds[s - 1] if s <= len(seeds) else None for s in order]


def standing_rows(snap: GameSnapshot, state: GameState) -> list[dict[str, Any]]:
    order = rank_teams(snap, state)
    s = snap.settings
    seeded = state.playoff["seeds"] if state.playoff else []
    rows = []
    for i, tid in enumerate(order):
        rec = state.stand[tid]
        team = snap.team(tid)
        label = None
        if state.playoff:
            label = state.playoff["results"].get(tid, "missed")
        rows.append({
            "rank": i + 1, "team_id": tid, "name": team.name, "owner": team.owner, "is_you": team.is_user,
            "persona_id": team.persona_id, "wins": int(rec["w"]), "losses": int(rec["l"]), "ties": int(rec["t"]),
            "pf": round(rec["pf"], 1), "pa": round(rec["pa"], 1), "streak": state.streak[tid],
            "seed": (seeded.index(tid) + 1) if tid in seeded else None,
            "playoff_status": _playoff_status(state, tid, i + 1, s.playoff_teams, label),
        })
    return rows


def _playoff_status(state: GameState, tid: str, rank: int, spots: int, label: str | None) -> str:
    if state.playoff is not None:
        if label == "champion":
            return "champion"
        if label == "missed":
            return "out"
        return "alive" if tid in state.playoff["alive"] else "eliminated"
    return "in" if rank <= spots else "out"


def user_alive(snap: GameSnapshot, state: GameState) -> bool:
    return bool(state.playoff) and snap.user_team.tid in state.playoff["alive"]


# --------------------------------------------------------------------- weeks


def _brief(snap: GameSnapshot, pid: str | None) -> dict[str, Any] | None:
    if not pid:
        return None
    if is_pick_id(pid):
        _, season, rnd, orig = pid.split(":", 3)
        return {"id": pid, "kind": "pick", "headshot_id": None, "name": f"{season} round {rnd} pick", "pos": "PICK",
                "team": snap.team(orig).name}
    p = snap.players[pid]
    return {"id": pid, "headshot_id": headshot_id(pid), "name": p.name, "pos": p.pos, "team": p.nfl_team}


def check_can_advance(snap: GameSnapshot, state: GameState) -> None:
    if state.status == "drafting":
        raise GameError("wrong_phase", "Finish the draft first.", phase="draft")
    if state.status == "complete":
        raise GameError("season_complete", "The season is over.")
    if state.status == "offseason":
        raise GameError("wrong_phase", "The season is over: finish the offseason first.", phase="offseason")
    over = len(state.rosters[snap.user_team.tid]) - snap.settings.roster_limit
    if over > 0:
        raise GameError("roster_over_limit", f"Cut {over} player(s) before advancing.", cuts_needed=over)


def fill_empty_slots(em: Emitter, ev: Evaluator, tid: str, week: int) -> list[str]:
    """Slots left empty (a starter was cut/dropped/traded) get the best eligible
    healthy bench player. Returns the slots filled."""

    state, snap = em.state, em.snap
    lineup = [list(r) for r in state.lineups[tid]]
    used = {pid for _, pid in lineup if pid}
    filled = []
    for row in lineup:
        if row[1] is not None:
            continue
        cands = sorted(
            (p for p in state.rosters[tid]
             if p not in used and snap.players[p].pos in slot_positions(row[0]) and ev.status(p, week) == "healthy"),
            key=lambda p: (-ev.ros_mean(p), p),
        )
        if cands:
            row[1] = cands[0]
            used.add(cands[0])
            filled.append(row[0])
    if filled:
        em.emit(week, "engine", "lineup_set", team=tid, slots=lineup, auto=True)
    return filled


def _resolve_waivers(em: Emitter, snap: GameSnapshot, state: GameState, seed: int, week: int) -> list[dict[str, Any]]:
    ev = Evaluator(snap, state)
    claims: dict[str, list[dict[str, Any]]] = {t: [] for t in snap.tids}
    for c in state.claims:
        claims[c["team"]].append(dict(c))
    claimed = {c["add"] for cs in claims.values() for c in cs}
    for tid in waiver_order(snap, state):
        if snap.team(tid).is_user:
            continue
        c = ai_waiver_claim(ev, tid, week, seed, claimed)
        if c is not None:
            claims[tid].append(c)
            claimed.add(c["add"])
    limit = snap.settings.roster_limit
    out = []
    for tid in waiver_order(snap, state):
        for c in claims[tid]:
            roster = state.rosters[tid]
            add, drop = c["add"], c.get("drop")
            reason = ""
            if add in state.owner_map():
                reason = "taken"
            elif drop is not None and drop not in roster:
                reason = "drop_not_owned"
            elif len(roster) - (1 if drop else 0) + 1 > limit:
                reason = "roster_full"
            start = c.get("start_slot")
            if start and snap.players[add].pos not in slot_positions(start):
                start = None
            em.emit(week, "user" if snap.team(tid).is_user else "engine", "waiver_result",
                    team=tid, add=add, drop=drop, ok=not reason, reason=reason,
                    start_slot=start if not reason else None, claim_id=c.get("id"))
            out.append({
                "team_id": tid, "name": snap.team(tid).name, "is_you": snap.team(tid).is_user,
                "add": _brief(snap, add), "drop": _brief(snap, drop), "ok": not reason, "reason": reason,
            })
    return out


def _ai_trade_phase(em: Emitter, snap: GameSnapshot, state: GameState, seed: int, week: int) -> list[dict[str, Any]]:
    if week > snap.settings.trade_deadline_week or state.status != "in_season":
        return []
    rng = WorldRng(seed)
    n = len(snap.tids)
    order = rng.stream(week, "gtrade", 0).permutation(n)
    user = snap.user_team.tid
    done: set[str] = set()
    made: list[dict[str, Any]] = []
    for ti in order:
        if len(made) >= MAX_AI_TRADES_PER_WEEK:
            break
        tid = snap.tids[int(ti)]
        if tid == user or tid in done:
            continue
        params = team_params(snap, tid)
        if params.activity <= 0 or state.trades_made[tid] >= params.max_trades:
            continue
        r = rng.stream(week, "gtrade", 1 + int(ti))
        if r.random() > params.activity:
            continue
        partners = [
            snap.tids[int(j)] for j in r.permutation(n)
            if int(j) != int(ti) and snap.tids[int(j)] not in done and snap.tids[int(j)] != user
        ][:PARTNERS_PER_SEARCH]
        desk = TradeDesk(Evaluator(snap, state), seed, week)
        found = desk.find_deal(tid, partners)
        if found is None:
            continue
        partner, give, get, _, _ = found
        execute_trade(em, tid, partner, give, get, key="", source="ai_ai")
        done.update((tid, partner))
        made.append({
            "team_a": tid, "team_b": partner, "give": [_brief(snap, p) for p in give],
            "get": [_brief(snap, p) for p in get],
        })
    return made


def generate_offers(em: Emitter, snap: GameSnapshot, state: GameState, seed: int, week: int) -> int:
    """AI managers' offers to the user for ``week``: at most one per team and
    three league-wide, each one a deal the AI wants and the user is not robbed
    in. Unanswered offers expire at the next Advance."""

    s = snap.settings
    if week > s.regular_weeks or week > s.trade_deadline_week:
        return 0
    rng = WorldRng(seed)
    user = snap.user_team.tid
    n = len(snap.tids)
    order = rng.stream(week, "goffer", 0).permutation(n)
    desk = TradeDesk(Evaluator(snap, state), seed, week)
    found: list[tuple[float, str, list[str], list[str]]] = []
    for ti in order:
        tid = snap.tids[int(ti)]
        if tid == user:
            continue
        params = team_params(snap, tid)
        if params.activity <= 0 or state.trades_made[tid] >= params.max_trades:
            continue
        if rng.stream(week, "goffer", 1 + int(ti)).random() > 0.8 * params.activity:
            continue
        deal = desk.find_deal(tid, [user], to_user=True)
        if deal is not None:
            _, give, get, ui, uj = deal
            found.append((ui + uj, tid, give, get))
    found.sort(key=lambda f: (-f[0], f[1]))
    for _, tid, give, get in found[:MAX_OFFERS_PER_WEEK]:
        em.emit(week, "engine", "inbox_offer", id=f"o{state.seq}", team=tid, give=give, get=get,
                expires_week=week, message=offer_message(snap, tid))
    return min(len(found), MAX_OFFERS_PER_WEEK)


def _fill_holes(em: Emitter, ev: Evaluator, tid: str) -> list[str]:
    """Before a new dynasty season: give an AI team a free agent for every starting
    slot nobody on its roster can fill (retirements can leave holes)."""

    from modules.sim.game_state import GameState  # noqa: F401 - typing only

    snap, state = em.snap, em.state
    added: list[str] = []
    for _ in range(len(snap.settings.slots)):
        best, _total = ev.best_lineup(state.rosters[tid], 1)
        vacant = sorted({pos for slot, pid in best if not pid for pos in slot_positions(slot)})
        if not vacant or len(state.rosters[tid]) >= snap.settings.roster_limit:
            break
        owned = state.owner_map()
        cands = sorted(
            (p for p in snap.pids if p not in owned and snap.players[p].pos in vacant),
            key=lambda p: (-ev.ros_mean(p), p),
        )
        if not cands:
            break
        em.emit(1, "engine", "waiver_result", team=tid, add=cands[0], drop=None, ok=True, reason="",
                start_slot=None, claim_id=None)
        added.append(cands[0])
    return added


def finish_draft(
    em: Emitter, snap: GameSnapshot, state: GameState, seed: int, *, closing: str = "draft_complete"
) -> dict[str, Any]:
    """Draft over: set every lineup, queue week-1 offers, start the season.
    (``closing`` is the event that starts week 1: a league import closes with
    ``league_start`` instead of ``draft_complete``; the fold treats both alike.)"""

    ev = Evaluator(snap, state)
    for tid in snap.tids:
        slots, _ = ev.best_lineup(state.rosters[tid], 1)
        em.emit(1, "engine", "lineup_set", team=tid, slots=slots, auto=True)
    recap = draft_recap(snap, state)
    generate_offers(em, snap, state, seed, 1)
    em.emit(1, "engine", closing, recap=recap)
    return recap


def start_from_league(em: Emitter, snap: GameSnapshot, state: GameState, seed: int) -> dict[str, Any]:
    """Begin a game imported from a real league: load the frozen rosters, then
    the same week-1 setup a finished draft gets."""

    em.emit(0, "engine", "league_rosters")
    return finish_draft(em, snap, state, seed, closing="league_start")


def _team_score(lineup: Sequence[Sequence[Any]], pts: dict[str, float]) -> float:
    return round(sum(pts.get(pid, 0.0) for _, pid in lineup if pid), 2)


def _lineup_rows(
    snap: GameSnapshot, status_of: dict[str, str], lineup: Sequence[Sequence[Any]], roster: Sequence[str],
    played: dict[str, PlayerWeek], with_bench: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    def row(slot: str | None, pid: str) -> dict[str, Any]:
        pw = played.get(pid)
        status = status_of[pid]
        return {
            "slot": slot, "player": _brief(snap, pid), "pts": round(pw.points, 2) if pw else 0.0,
            "stats": dict(pw.stats) if pw and pw.stats else None,
            "flag": status if status != "healthy" else (None if pw else "inactive"),
        }

    starters = [row(slot, pid) if pid else {"slot": slot, "player": None, "pts": 0.0, "stats": None, "flag": "empty"}
                for slot, pid in lineup]
    started = {pid for _, pid in lineup if pid}
    bench = [row(None, pid) for pid in roster if pid not in started] if with_bench else []
    bench.sort(key=lambda r: (-r["pts"], r["player"]["id"]))
    return starters, bench


def _your_game(snap, ev, state, user, games, lineups, played, pts, status_of, ros_before, alive_before, kind, auto_filled):
    mine = next((g for g in games if user in (g["home"], g["away"])), None)
    starters, bench = _lineup_rows(snap, status_of, lineups[user], state.rosters[user], played, True)
    if mine is None:
        if kind == "playoff" and user in alive_before:
            return {"result": "bye", "starters": starters, "bench": bench[:10]}
        return None
    optimal = pick_lineup(ev.plan, [(pts.get(p, 0.0), p, snap.players[p].pos) for p in state.rosters[user]])[1]
    opp = mine["away"] if mine["home"] == user else mine["home"]
    you_pts = mine["home_pts"] if mine["home"] == user else mine["away_pts"]
    opp_pts = mine["away_pts"] if mine["home"] == user else mine["home_pts"]
    if mine["winner"] is not None:
        result = "win" if mine["winner"] == user else "loss"
    else:
        result = "win" if you_pts > opp_pts + 1e-9 else "loss" if you_pts < opp_pts - 1e-9 else "tie"
    o_starters, _ = _lineup_rows(snap, status_of, lineups[opp], state.rosters[opp], played, False)
    out = {
        "opponent_id": opp, "opponent_name": snap.team(opp).name, "your_pts": you_pts,
        "opp_pts": opp_pts, "result": result, "starters": starters, "bench": bench[:10],
        "opp_starters": o_starters, "optimal_pts": round(optimal, 2),
        "efficiency": round(you_pts / optimal, 4) if optimal > 0 else 1.0,
        "auto_filled_slots": auto_filled,
    }
    rows = [r for r in starters if r["player"]]
    if rows:
        top = max(rows, key=lambda r: (r["pts"], r["player"]["id"]))
        out["mvp"] = {"player": top["player"], "pts": top["pts"]}
        gaps = [(ros_before[r["player"]["id"]] - r["pts"], r) for r in rows if r["flag"] is None]
        if gaps:
            gap, worst = max(gaps, key=lambda g: (g[0], g[1]["player"]["id"]))
            out["bust"] = {"player": worst["player"], "pts": worst["pts"], "expected": round(gap + worst["pts"], 1)}
    return out


def run_week(em: Emitter, snap: GameSnapshot, state: GameState, seed: int) -> dict[str, Any]:
    """Resolve the week ``state.week`` and return its recap. Always ends with a
    ``week_advanced`` event."""

    S = snap.settings
    W = state.week
    user = snap.user_team.tid
    kind = "regular" if W <= S.regular_weeks else "playoff"
    rnd = None if kind == "regular" else W - S.regular_weeks

    # 1. the user's optional autopilot lineup
    if S.auto_lineup and state.lineups[user]:
        ev0 = Evaluator(snap, state)
        slots, _ = ev0.best_lineup(state.rosters[user], W)
        em.emit(W, "engine", "lineup_set", team=user, slots=slots, auto=True)

    # 2. waivers, worst record first
    waiver_rows = _resolve_waivers(em, snap, state, seed, W)

    # 3. AI-to-AI trades (before the deadline)
    ai_trades = _ai_trade_phase(em, snap, state, seed, W)

    # 4. lineups: AI sets its own, the user's empty slots are auto-filled
    ev = Evaluator(snap, state)
    for tid in snap.tids:
        if tid == user:
            continue
        if S.reserves:
            ai_manage_reserves(em, ev, tid)
        em.emit(W, tid, "lineup_set", team=tid, slots=ai_lineup(ev, tid, W, seed), auto=True)
    auto_filled = fill_empty_slots(em, ev, user, W)

    # 5. scoring
    session = session_for(snap, seed)
    played: dict[str, PlayerWeek] = {}
    hurt: list[list] = []
    for pid in snap.pids:
        if ev.status(pid, W) != "healthy":
            continue
        res = session.week(pid, W, ev.role_param(pid, W) if ev.roles_on else None)
        if not res.active:
            continue
        played[pid] = PlayerWeek(round(max(0.0, res.points), 2), res.stats, True, res.newly_injured)
        if res.newly_injured:
            weeks_out = session.weeks_out(pid, W, res)
            if weeks_out > 0:  # hurt in the last game of the season: nothing left to miss
                hurt.append([pid, weeks_out])
    pts = {pid: pw.points for pid, pw in played.items()}
    status_of = {pid: ev.status(pid, W) for pid in snap.pids}
    ros_before = {pid: ev.ros_mean(pid) for pid in state.rosters[user]}
    owners = state.owner_map()
    lineups = {tid: [list(r) for r in state.lineups[tid]] for tid in snap.tids}
    scores = {tid: _team_score(lineups[tid], pts) for tid in snap.tids}

    # 6. games and the user's box score (all from pre-fold data)
    games: list[dict[str, Any]] = []
    alive_next: list[str | None] = []
    eliminated: dict[str, str] = {}
    alive_before: list[str | None] = list(state.playoff["alive"]) if kind == "playoff" else []
    if kind == "regular":
        for home, away in snap.schedule[W - 1]:
            games.append({"home": home, "away": away, "home_pts": scores[home], "away_pts": scores[away], "winner": None})
    else:
        seeds = state.playoff["seeds"]
        total_rounds = S.playoff_weeks
        for i in range(0, len(alive_before), 2):
            a, b = alive_before[i], alive_before[i + 1]
            if a is None or b is None:
                alive_next.append(a or b)
                continue
            sa, sb = scores[a], scores[b]
            winner = a if (sa > sb or (sa == sb and seeds.index(a) < seeds.index(b))) else b
            loser = b if winner == a else a
            games.append({"home": a, "away": b, "home_pts": sa, "away_pts": sb, "winner": winner})
            alive_next.append(winner)
            eliminated[loser] = (
                "runner_up" if rnd == total_rounds else
                "semifinal" if rnd == total_rounds - 1 and total_rounds >= 2 else f"lost_round_{rnd}"
            )
    your_game = _your_game(snap, ev, state, user, games, lineups, played, pts, status_of, ros_before, alive_before, kind, auto_filled)
    injuries = [
        {"player": _brief(snap, pid), "weeks": weeks, "team_id": owners.get(pid), "is_yours": owners.get(pid) == user}
        for pid, weeks in hurt if pid in owners
    ]

    extra: dict[str, Any] = {}
    if ev.roles_on and ev.additive:  # the role behind each score, so his level can be read without it
        roles = {}
        for pid in played:
            scale, add = ev.role_param(pid, W)
            if abs(scale - 1.0) > 1e-9 or add > 1e-9:
                roles[pid] = [round(scale, 4), round(add, 4)]
        if roles:
            extra["roles"] = roles
    em.emit(W, "engine", "week_scored", kind=kind, round=rnd, games=games,
            points={pid: v for pid, v in pts.items()}, alive_next=alive_next, eliminated=eliminated, **extra)
    if hurt:
        em.emit(W, "engine", "injury", items=hurt)

    # 7. regular season over: seed the playoffs
    seeding = None
    if kind == "regular" and W == S.regular_weeks:
        seeds = rank_teams(snap, state)[: S.playoff_teams]
        slots = bracket_slots(seeds)
        em.emit(W, "engine", "playoff_seeded", seeds=seeds, slots=slots)
        seeding = {"seeds": seeds, "bracket": slots}
    champion = ""
    if kind == "playoff" and len(alive_next) == 1 and alive_next[0]:
        champion = alive_next[0]
        if S.dynasty:
            more = S.multi_season and state.season_no < S.seasons
            archive = dyn.season_archive(snap, state, champion)
            if more:
                nxt = snap.season_view(state.season_no + 1)
                gone = dyn.retirees(snap, nxt)
            else:
                gone = []
            em.emit(W, "engine", "season_complete", champion=champion, archive=archive, offseason=more,
                    retired=gone, retired_owners={p: owners[p] for p in gone if p in owners},
                    year=S.start_year + state.season_no)
        else:
            em.emit(W, "engine", "season_complete", champion=champion)

    recap = {
        "week": W, "kind": kind, "round": rnd, "your_game": your_game,
        "scores": [
            {"home": g["home"], "away": g["away"], "home_name": snap.team(g["home"]).name,
             "away_name": snap.team(g["away"]).name, "home_pts": g["home_pts"], "away_pts": g["away_pts"],
             "winner": g["winner"]} for g in games
        ],
        "standings": standing_rows(snap, state), "waivers": waiver_rows, "transactions": ai_trades,
        "injuries": injuries, "playoffs": seeding, "season_complete": state.status in ("complete", "offseason"),
        **({"offseason": True} if state.status == "offseason" else {}),
        "champion": champion or None, "next_week": W + 1,
    }
    # 9. next week's AI offers, then the boundary
    if state.status not in ("complete", "offseason"):
        generate_offers(em, snap, state, seed, W + 1)
    em.emit(W, "engine", "week_advanced", week=W, next_week=W + 1, recap=recap)
    return recap


def advance(em: Emitter, snap: GameSnapshot, state: GameState, seed: int) -> list[dict[str, Any]]:
    """One user-visible Advance. Returns the recaps played: the requested week,
    then (once the user is out of the playoffs) the remaining playoff weeks."""

    check_can_advance(snap, state)
    em.emit(state.week, "user", "advance", week=state.week)
    recaps = [run_week(em, snap, state, seed)]
    while state.status == "playoffs" and not user_alive(snap, state):
        recaps.append(run_week(em, snap, state, seed))
    return recaps


__all__ = [
    "advance", "run_week", "finish_draft", "start_from_league", "check_can_advance", "rank_teams", "standing_rows",
    "bracket_slots", "waiver_order", "user_alive", "session_for", "ScoringSession", "generate_offers",
    "fill_empty_slots",
]
