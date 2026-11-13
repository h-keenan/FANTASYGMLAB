"""Game state as a pure fold over the append-only event log.

``apply_event`` is the ONLY place state changes. The weekly engine, the user
commands, resume (checkpoint + tail events) and replay (all events from the
start) all go through it, so they cannot disagree. Events are plain dicts:

    {"seq": int, "week": int, "actor": "user"|"engine"|<team id>, "type": str, "payload": {...}}

Event types and payloads are documented next to the code that emits them
(game_draft, game_actions, game_engine); the fold below is the reference.
"""

from __future__ import annotations

import copy
import hashlib
import json
import marshal
from typing import Any, Iterable, Mapping

from modules.sim.game_types import GameSnapshot
from modules.sim.types import is_pick_id

STATUSES = ("drafting", "in_season", "playoffs", "offseason", "complete")
MAX_TRANSACTIONS = 200


def _dup(value: Any) -> Any:
    """An independent deep copy of plain data (dict/list/str/number/None). marshal round-trips it exactly,
    several times faster than ``copy.deepcopy``; anything it cannot carry takes the general path."""

    try:
        return marshal.loads(marshal.dumps(value))
    except ValueError:
        return copy.deepcopy(value)


class GameState:
    def __init__(self, snapshot: GameSnapshot) -> None:
        self.status = "drafting"
        self.week = 0  # week to be played next; 0 while drafting
        self.pick_index = 0  # next overall pick, 0-based
        self.picks: list[dict[str, Any]] = []
        self.queue: list[str] = []
        self.rosters: dict[str, list[str]] = {t.tid: [] for t in snapshot.teams}
        # Reserve squads: players here are owned but not on the active roster (no lineup, no roster-limit spot).
        self.ir: dict[str, list[str]] = {t.tid: [] for t in snapshot.teams}
        self.taxi: dict[str, list[str]] = {t.tid: [] for t in snapshot.teams}
        self.lineups: dict[str, list[list[Any]]] = {
            t.tid: [[s, None] for s in snapshot.settings.slots] for t in snapshot.teams
        }
        self.out: dict[str, int] = {
            p.pid: p.injury_weeks for p in snapshot.players.values() if p.injury_weeks > 0
        }
        self.stand: dict[str, dict[str, float]] = {
            t.tid: {"w": 0, "l": 0, "t": 0, "pf": 0.0, "pa": 0.0} for t in snapshot.teams
        }
        self.h2h: dict[str, dict[str, list[int]]] = {t.tid: {} for t in snapshot.teams}
        self.streak: dict[str, str] = {t.tid: "" for t in snapshot.teams}
        self.history: list[dict[str, Any]] = []  # one entry per played week
        self.points: dict[str, list[float | None]] = {}
        # player-model-4: the team role (scale, points) a player had in each game he played, {pid: {"week": [scale, add]}}.
        self.role_hist: dict[str, dict[str, list[float]]] = {}
        self.claims: list[dict[str, Any]] = []
        self.offers: list[dict[str, Any]] = []
        self.offer_keys: list[str] = []
        self.trades_made: dict[str, int] = {t.tid: 0 for t in snapshot.teams}
        self.transactions: list[dict[str, Any]] = []
        self.news: list[dict[str, Any]] = []
        self.playoff: dict[str, Any] | None = None
        self.champion = ""
        self.recaps: dict[str, dict[str, Any]] = {}
        self.seq = 0  # number of events applied
        self.boundary_seq = 0  # first seq of the current week's pending decisions
        # Dynasty (inert in every other mode; absent keys in an old checkpoint keep these defaults).
        self.season_no = 1  # the season in progress (or just finished, while in the offseason)
        self.pick_owner: dict[str, str] = {p.pid: p.owner for p in snapshot.start_picks}
        self.created_picks: list[str] = sorted(self.pick_owner)  # every pick ever made: the conservation ledger
        self.spent_picks: list[dict[str, Any]] = []  # picks used in a rookie draft
        self.seasons: list[dict[str, Any]] = []  # one archive per finished season
        self.offseason: dict[str, Any] | None = None  # stage, rookie-draft order and progress
        self.rookie_log: list[dict[str, Any]] = []  # completed rookie drafts
        self.retired: list[str] = []

    # --------------------------------------------------------------- views

    @property
    def view_no(self) -> int:
        """Which season's player pool applies: the offseason already shows next
        season's aged players and incoming rookies."""

        return self.season_no + (1 if self.status == "offseason" else 0)

    def picks_of(self, tid: str) -> list[str]:
        return sorted(pid for pid, owner in self.pick_owner.items() if owner == tid)

    def owner_map(self) -> dict[str, str]:
        out = {pid: tid for tid, roster in self.rosters.items() for pid in roster}
        for squads in (self.ir, self.taxi):
            for tid, pids in squads.items():
                for pid in pids:
                    out[pid] = tid
        return out

    def holdings(self, tid: str) -> list[str]:
        """Every player ``tid`` owns: active roster, IR and taxi."""

        return [*self.rosters[tid], *self.ir.get(tid, ()), *self.taxi.get(tid, ())]

    def where(self, tid: str, pid: str) -> str | None:
        if pid in self.rosters[tid]:
            return "roster"
        if pid in self.ir.get(tid, ()):
            return "ir"
        if pid in self.taxi.get(tid, ()):
            return "taxi"
        return None

    def _drop_everywhere(self, tid: str, pid: str) -> None:
        for squad in (self.rosters, self.ir, self.taxi):
            if pid in squad.get(tid, ()):
                squad[tid].remove(pid)

    def free_agents(self, snapshot: GameSnapshot) -> list[str]:
        owned = self.owner_map()
        return [p for p in snapshot.pids if p not in owned]

    def games_played(self, pid: str) -> list[float]:
        return [p for p in self.points.get(pid, ()) if p is not None]

    def last_points(self, pid: str) -> float | None:
        hist = self.points.get(pid)
        return hist[-1] if hist else None

    # --------------------------------------------------------------- (de)serialize

    def to_dict(self) -> dict[str, Any]:
        return _dup(self.__dict__)

    def clone(self) -> "GameState":
        """An independent copy, value-identical to ``to_dict`` + ``from_dict`` (the state is plain
        data, so marshal round-trips it exactly, several times faster than ``deepcopy``). The
        in-process state cache hands out one shared, never-mutated instance per game version;
        every command works on its own clone."""

        new = GameState.__new__(GameState)
        new.__dict__.update(_dup(self.__dict__))
        return new

    @classmethod
    def from_dict(cls, snapshot: GameSnapshot, raw: Mapping[str, Any]) -> "GameState":
        state = cls(snapshot)
        for key, value in raw.items():
            if key in state.__dict__:
                setattr(state, key, _dup(value))
        return state

    def digest(self) -> str:
        """Stable fingerprint for resume-vs-replay equality checks."""

        raw = self.to_dict()
        # Dynasty / reserve fields at their inert defaults are left out, so a game that never
        # uses them fingerprints exactly as it did before they existed.
        for key in ("ir", "taxi"):
            if not any(raw[key].values()):
                del raw[key]
        for key in ("pick_owner", "created_picks", "spent_picks", "seasons", "rookie_log", "retired", "role_hist"):
            if not raw[key]:
                del raw[key]
        if raw["season_no"] == 1:
            del raw["season_no"]
        if raw["offseason"] is None:
            del raw["offseason"]
        blob = json.dumps(raw, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(blob.encode()).hexdigest()


def make_event(state: GameState, week: int, actor: str, etype: str, /, **payload: Any) -> dict[str, Any]:
    """Build the next event for ``state`` (does NOT apply it)."""

    return {"seq": state.seq, "week": int(week), "actor": str(actor), "type": etype, "payload": payload}


# ----------------------------------------------------------------- the fold


def _remove_from_lineups(state: GameState, tid: str, pids: Iterable[str]) -> None:
    gone = set(pids)
    for row in state.lineups[tid]:
        if row[1] in gone:
            row[1] = None


def _tx(state: GameState, week: int, kind: str, **fields: Any) -> None:
    state.transactions.append({"week": week, "type": kind, **fields})
    if len(state.transactions) > MAX_TRANSACTIONS:
        del state.transactions[: len(state.transactions) - MAX_TRANSACTIONS]


def apply_event(state: GameState, snapshot: GameSnapshot, ev: Mapping[str, Any]) -> None:
    kind = ev["type"]
    p = ev["payload"]
    week = int(ev.get("week") or 0)
    handler = _HANDLERS.get(kind)
    if handler is None:
        raise ValueError(f"unknown event type: {kind}")
    snapshot = snapshot.season_view(state.view_no)  # a later dynasty season has its own pool
    handler(state, snapshot, week, p)
    state.seq = int(ev["seq"]) + 1


def _draft_pick(state, snap, week, p):
    state.rosters[p["team"]].append(p["pid"])
    state.picks.append({"n": p["n"], "round": p["round"], "team": p["team"], "pid": p["pid"], "auto": bool(p.get("auto"))})
    state.pick_index = int(p["n"]) + 1
    if p["pid"] in state.queue:
        state.queue.remove(p["pid"])


def _league_rosters(state, snap, week, p):
    """A game imported from a real league starts from the snapshot's frozen
    copy of every team's roster instead of a draft."""

    state.rosters = {t.tid: list(snap.start_rosters.get(t.tid, ())) for t in snap.teams}
    state.ir = {t.tid: list(snap.start_ir.get(t.tid, ())) for t in snap.teams}
    state.taxi = {t.tid: list(snap.start_taxi.get(t.tid, ())) for t in snap.teams}


def _draft_queue(state, snap, week, p):
    state.queue = [str(x) for x in p["pids"]]


def _draft_complete(state, snap, week, p):
    state.status = "in_season"
    state.week = 1
    state.queue = []
    state.boundary_seq = state.seq + 1


def _lineup_set(state, snap, week, p):
    state.lineups[p["team"]] = [[s, pid] for s, pid in p["slots"]]


def _waiver_claim(state, snap, week, p):
    state.claims.append(dict(p))


def _waiver_cancel(state, snap, week, p):
    state.claims = [c for c in state.claims if c["id"] != p["id"]]


def _waiver_result(state, snap, week, p):
    tid = p["team"]
    if p["ok"]:
        if p.get("drop"):
            state.rosters[tid].remove(p["drop"])
            _remove_from_lineups(state, tid, [p["drop"]])
        state.rosters[tid].append(p["add"])
        slot = p.get("start_slot")
        if slot:
            for row in state.lineups[tid]:
                if row[0] == slot:
                    row[1] = p["add"]
                    break
        _tx(state, week, "waiver", team=tid, add=p["add"], drop=p.get("drop"))


def _cut(state, snap, week, p):
    state._drop_everywhere(p["team"], p["pid"])
    _remove_from_lineups(state, p["team"], [p["pid"]])
    _tx(state, week, "drop", team=p["team"], pid=p["pid"], reason=p.get("reason", "cut"))


def _trade(state, snap, week, p):
    a, b = p["team_a"], p["team_b"]
    for pid in p["give"]:
        if is_pick_id(pid):
            state.pick_owner[pid] = b
            continue
        state._drop_everywhere(a, pid)
        state.rosters[b].append(pid)
    for pid in p["get"]:
        if is_pick_id(pid):
            state.pick_owner[pid] = a
            continue
        state._drop_everywhere(b, pid)
        state.rosters[a].append(pid)
    _remove_from_lineups(state, a, p["give"])
    _remove_from_lineups(state, b, p["get"])
    state.trades_made[a] += 1
    state.trades_made[b] += 1
    if p.get("key"):
        state.offer_keys.append(p["key"])
    _tx(state, week, "trade", team_a=a, team_b=b, give=list(p["give"]), get=list(p["get"]), source=p.get("source", ""))


def _slot_move(state, snap, week, p):
    """Move one of a team's players between its active roster, IR and taxi squad."""

    tid, pid = p["team"], p["pid"]
    state._drop_everywhere(tid, pid)
    dst = {"roster": state.rosters, "ir": state.ir, "taxi": state.taxi}[p["dst"]]
    dst[tid].append(pid)
    _remove_from_lineups(state, tid, [pid])
    _tx(state, week, "reserve", team=tid, pid=pid, src=p.get("src"), dst=p["dst"])


def _offer_key(state, snap, week, p):
    state.offer_keys.append(p["key"])


def _inbox_offer(state, snap, week, p):
    state.offers.append(dict(p))


def _inbox_response(state, snap, week, p):
    state.offers = [o for o in state.offers if o["id"] != p["id"]]


def _injury(state, snap, week, p):
    """``items`` is [[pid, weeks_out], ...]: weeks missed starting next week."""

    for pid, weeks in p["items"]:
        state.out[pid] = int(weeks)
        state.news.append({"week": week, "pid": pid, "weeks": int(weeks)})
    del state.news[:-150]


def _week_scored(state, snap, week, p):
    kind = p["kind"]
    games = p["games"]
    played = p["points"]
    state.week = week + 1  # next week to play (out-week counters tick below)
    for pid, ra in (p.get("roles") or {}).items():
        state.role_hist.setdefault(pid, {})[str(week)] = [float(ra[0]), float(ra[1])]
    for pid in snap.pids:
        hist = state.points.setdefault(pid, [])
        while len(hist) < week - 1:
            hist.append(None)
        hist.append(played.get(pid))
    for pid in list(state.out):
        state.out[pid] -= 1
        if state.out[pid] <= 0:
            del state.out[pid]
    if kind == "regular":
        for g in games:
            home, away = g["home"], g["away"]
            hs, aws = float(g["home_pts"]), float(g["away_pts"])
            sh, sa = state.stand[home], state.stand[away]
            sh["pf"] += hs
            sh["pa"] += aws
            sa["pf"] += aws
            sa["pa"] += hs
            res = _result(hs, aws)
            for me, opp, r in ((home, away, res), (away, home, {"w": "l", "l": "w", "t": "t"}[res])):
                state.stand[me][r] += 1
                rec = state.h2h[me].setdefault(opp, [0, 0, 0])
                rec["wlt".index(r)] += 1
                s = state.streak[me]
                state.streak[me] = (s[0] + str(int(s[1:] or 0) + 1)) if s and s[0] == r.upper() else r.upper() + "1"
    else:
        pl = state.playoff
        pl["alive"] = list(p["alive_next"])
        pl["rounds"].append({"round": p["round"], "week": week, "games": games})
        pl["results"].update(p["eliminated"])
    state.history.append({"week": week, "kind": kind, "round": p.get("round"), "games": games})


def _result(hs: float, aws: float) -> str:
    if abs(hs - aws) < 1e-9:
        return "t"
    return "w" if hs > aws else "l"


def _playoff_seeded(state, snap, week, p):
    state.playoff = {
        "seeds": list(p["seeds"]), "slots": list(p["slots"]), "alive": list(p["slots"]),
        "rounds": [], "results": {t: "lost_round_1" for t in p["seeds"]},
    }


def _season_complete(state, snap, week, p):
    state.champion = p["champion"]
    if state.playoff is not None and p["champion"]:
        state.playoff["results"][p["champion"]] = "champion"
    if not p.get("offseason"):
        state.status = "complete"
        if p.get("archive"):  # a dynasty's last season still archives itself
            state.seasons.append(copy.deepcopy(p["archive"]))
        return
    # Dynasty: archive the season, retire players, open the offseason. From here on
    # ``state.view_no`` is the next season, so the pool is next year's aged players.
    state.seasons.append(copy.deepcopy(p["archive"]))
    gone = {str(x) for x in p.get("retired", ())}
    for tid in state.rosters:
        for squad in (state.rosters, state.ir, state.taxi):
            squad[tid] = [pid for pid in squad.get(tid, ()) if pid not in gone]
        _remove_from_lineups(state, tid, gone)
    state.retired.extend(sorted(gone))
    state.status = "offseason"
    state.offseason = {"stage": "review", "year": int(p["year"]), "retired": list(p.get("retired", ())),
                       "order": [], "pick_index": 0, "slots": {}, "picks": [],
                       "retired_owner": dict(p.get("retired_owners", {}))}


def _rookie_draft_started(state, snap, week, p):
    off = state.offseason
    off["stage"] = "rookie_draft"
    off["order"] = list(p["order"])
    off["slots"] = {str(k): int(v) for k, v in p["slots"].items()}
    off["pick_index"] = 0
    off["picks"] = []


def _rookie_pick(state, snap, week, p):
    off = state.offseason
    pid_pick = p["pick"]
    owner = state.pick_owner.pop(pid_pick)
    state.rosters[p["team"]].append(p["pid"])
    entry = {"n": int(p["n"]), "round": int(p["round"]), "pick": pid_pick, "orig": p["orig"], "team": p["team"],
             "pid": p["pid"], "auto": bool(p.get("auto"))}
    off["picks"].append(entry)
    off["pick_index"] = int(p["n"]) + 1
    state.spent_picks.append({"pick": pid_pick, "team": p["team"], "was": owner, "n": int(p["n"]), "year": off["year"]})


def _rookie_draft_complete(state, snap, week, p):
    off = state.offseason
    off["stage"] = "cutdown"
    for raw in p.get("new_picks", ()):
        pick_id = f"pick:{int(raw['season'])}:{int(raw['round'])}:{raw['orig']}"
        state.pick_owner[pick_id] = str(raw["owner"])
        state.created_picks.append(pick_id)
    state.rookie_log.append({"year": off["year"], "picks": copy.deepcopy(off["picks"])})


def _season_started(state, snap, week, p):
    """The next dynasty season begins: every per-season record resets; rosters,
    picks, history (``seasons``) and the player pool carry over."""

    state.season_no = int(p["season_no"])
    state.status = "in_season"
    state.week = 1
    state.stand = {t.tid: {"w": 0, "l": 0, "t": 0, "pf": 0.0, "pa": 0.0} for t in snap.teams}
    state.h2h = {t.tid: {} for t in snap.teams}
    state.streak = {t.tid: "" for t in snap.teams}
    state.history = []
    state.points = {}
    state.role_hist = {}
    state.claims = []
    state.offers = []
    state.offer_keys = []
    state.trades_made = {t.tid: 0 for t in snap.teams}
    state.news = []
    state.playoff = None
    state.champion = ""
    state.recaps = {}
    state.out = {pid: pl.injury_weeks for pid, pl in snap.players.items() if pl.injury_weeks > 0 and pid in state.owner_map()}
    state.offseason = None
    state.boundary_seq = state.seq + 1


def _advance_requested(state, snap, week, p):
    """Marker only: the user tapped Advance (lets a replay re-issue it)."""


def _week_advanced(state, snap, week, p):
    state.recaps[str(p["week"])] = p["recap"]
    state.week = int(p["next_week"])
    state.claims = []
    state.offer_keys = []
    state.offers = [o for o in state.offers if int(o.get("expires_week", 0)) >= state.week]
    if state.status not in ("complete", "offseason"):
        state.status = "playoffs" if state.week > snap.settings.regular_weeks else "in_season"
    state.boundary_seq = state.seq + 1


_HANDLERS = {
    "draft_pick": _draft_pick, "draft_queue": _draft_queue, "draft_complete": _draft_complete,
    "league_rosters": _league_rosters, "league_start": _draft_complete,
    "lineup_set": _lineup_set, "waiver_claim": _waiver_claim, "waiver_cancel": _waiver_cancel,
    "waiver_result": _waiver_result, "cut": _cut, "drop": _cut, "trade": _trade,
    "trade_reject": _offer_key, "trade_counter": _offer_key, "inbox_offer": _inbox_offer,
    "inbox_response": _inbox_response, "injury": _injury, "week_scored": _week_scored,
    "playoff_seeded": _playoff_seeded, "season_complete": _season_complete,
    "week_advanced": _week_advanced, "advance": _advance_requested,
    "slot_move": _slot_move, "rookie_draft_started": _rookie_draft_started, "rookie_pick": _rookie_pick,
    "rookie_draft_complete": _rookie_draft_complete, "season_started": _season_started,
}


class Emitter:
    """Builds events, applies each to ``state`` immediately (so the next decision
    sees it) and collects them for persistence."""

    def __init__(self, state: GameState, snapshot: GameSnapshot) -> None:
        self.state = state
        self.snap = snapshot
        self.events: list[dict[str, Any]] = []

    def emit(self, week: int, actor: str, etype: str, /, **payload: Any) -> dict[str, Any]:
        ev = make_event(self.state, week, actor, etype, **payload)
        apply_event(self.state, self.snap, ev)
        self.events.append(ev)
        return ev


def fold(snapshot: GameSnapshot, events: Iterable[Mapping[str, Any]], state: GameState | None = None) -> GameState:
    """Fold ``events`` (ascending seq) onto ``state`` (a fresh one by default)."""

    state = state or GameState(snapshot)
    for ev in events:
        apply_event(state, snapshot, ev)
    return state


__all__ = ["GameState", "Emitter", "apply_event", "fold", "make_event", "STATUSES"]
