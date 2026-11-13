"""``/v1/sim/games*`` routes (the GM game), registered from ``api.build_router``.

Same rules as the rest of the sim API: server-side Pro gate with a free preview
(draft + weeks 1-3), 200 + ``reason`` for not-ready/rule states, 404 for unknown
or other users' games, 422 for bad input, 503 when the sim's own compute pool is
full. Every mutating call loads the game (checkpoint + event tail), runs the
command through the pure engine, then appends the resulting events in one
insert; a lost write race is a 409 the client retries.
"""

from __future__ import annotations

import functools
from collections import OrderedDict
import json
import logging
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, replace
from typing import Any, Callable, ContextManager, Mapping

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from modules.sim import game_actions as act
from modules.sim import game_dynasty as dyn
from modules.sim import game_dynasty_view as dview
from modules.sim import game_draft as draft
from modules.sim import game_block as blockmod
from modules.sim import game_history as hist
from modules.sim import game_simto as simto
from modules.sim import game_home as home
from modules.sim import game_notifications as notif
from modules.sim import game_view as view
from modules.sim.game_ai import TradeDesk
from modules.sim.game_engine import advance, finish_draft, start_from_league
from modules.sim.game_eval import Evaluator
from modules.sim.game_result import _draft_from_state, build_result
from modules.sim.game_review import build_review
from modules.sim.game_scoring import default_model
from modules.sim.game_setup import (
    TEAM_NAMES, USER_TEAM_NAME_MAX, build_league_snapshot, build_snapshot, finalize_pool, league_settings,
    pick_random_team_name,
)
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_store import GameConflict, GameStore, public_game_row, row_version
from modules.sim.game_mode import DEFAULT_ROOKIE_ROUNDS, DEFAULT_SEASONS, PICK_YEARS, ROOKIE_ROUNDS, SEASON_CHOICES, mode_options
from modules.sim.game_types import (
    BENCH_RANGE,
    DEFAULT_BENCH,
    DEFAULT_SCORING,
    DEFAULT_TEAMS,
    DEFAULT_TIEBREAKER,
    DIFFICULTIES,
    DEFAULT_IR_SLOTS,
    DEFAULT_TAXI_SLOTS_DYNASTY,
    DEFAULT_TAXI_YEARS,
    DRAFT_SPARE_SPOTS,
    IR_SLOT_RANGE,
    START_FRESH,
    START_KINDS,
    START_LEAGUE,
    TE_PREMIUMS,
    TIEBREAKERS,
    headshot_id,
    GAME_ENGINE_VERSION,
    MAX_GAMES_FREE,
    MAX_GAMES_PRO,
    PREVIEW_PAYWALL_WEEK,
    SCORING_NAMES,
    SCORING_PRESETS,
    TAXI_SLOT_RANGE,
    TEAM_COUNTS,
    GameError,
    GameSettings,
    GameSnapshot,
)
from modules.sim.personas import PERSONAS
from modules.sim.rng import WorldRng
from modules.sim.store import SimStoreError
from modules.sim.team_roles import PROJ_CEIL, week_one_roles
from modules.sim.team_roles import soft_ceiling as tr_soft_ceiling
from modules.sim.types import FLEX_SLOTS, GAME_POSITIONS, POSITIONS, SimInputsError

_log = logging.getLogger(__name__)

POOL_TTL_SECONDS = 1800
_POOL_CACHE: dict[str, tuple[float, Any]] = {}
_POOL_LOCK = threading.Lock()
_STRIPES = [threading.Lock() for _ in range(64)]

UPSELL_GAME = {
    "title": "Keep your season going",
    "body": (
        "Fantasy Sim: the GM Game is a Pro feature. You played the free preview (the draft and "
        "weeks 1-3); upgrade to pick your season back up exactly where you left it."
    ),
}
UPSELL_MORE_GAMES = {
    "title": "Run more than one season",
    "body": "Free accounts get one Fantasy Sim save. Pro unlocks up to three games at once.",
}


@dataclass
class GameApiCtx:
    require_user: Callable[..., dict[str, Any]]
    is_pro: Callable[[dict[str, Any]], bool]
    store_for: Callable[[dict[str, Any]], GameStore]
    inputs: Any
    compute: Callable[[], ContextManager[bool]]  # bounded pool: yields False when full
    sleeper_username: Callable[[dict[str, Any]], str] | None = None  # for "start from one of my leagues"


class LineupSlotBody(BaseModel):
    slot: str
    player_id: str | None = None


class LineupBody(BaseModel):
    slots: list[LineupSlotBody] = Field(max_length=24)


class PickBody(BaseModel):
    player_id: str
    # The pick the client believes is on the clock (1-based). Optional so old
    # clients keep working; when sent, a stale value is a 409 `already_picked`
    # so a double tap can never draft two players.
    pick_no: int | None = None


class QueueBody(BaseModel):
    player_ids: list[str] = Field(max_length=60)


class WaiverBody(BaseModel):
    add: str
    drop: str | None = None
    start_slot: str | None = None


class CutBody(BaseModel):
    player_id: str


class TradeBody(BaseModel):
    partner: str
    give: list[str] = Field(max_length=12)
    get: list[str] = Field(max_length=12)


class MoveBody(BaseModel):
    player_id: str
    to: str


class RespondBody(BaseModel):
    action: str


class AdvanceBody(BaseModel):
    week: int | None = None


class SimToBody(BaseModel):
    target: str = "weeks"
    weeks: int = 1
    auto_set: bool = False
    force_first: bool = False


class UndoSimBody(BaseModel):
    from_seq: int


class BlockBody(BaseModel):
    asset_id: str
    on: bool = True
    looking_for: str | None = None


def seedof(row: Mapping[str, Any], state: GameState) -> int:
    """The RNG seed the game's current season plays under (season 1: the game's own seed)."""

    return dyn.season_seed(int(row["seed"]), state.view_no)


def default_start_year(today: Any = None) -> int:
    """The calendar label a fresh dynasty's season 1 plays under (the NFL season in
    progress or next up; Jan-Feb still belongs to the season just played)."""

    import datetime

    d = today or datetime.date.today()
    return d.year if d.month >= 3 else d.year - 1


def _fast_json(payload: Any) -> Any:
    """Serialize a plain-dict payload straight to JSON. Returning the dict would send it through
    FastAPI's recursive ``jsonable_encoder`` first, which is a quarter of the time of a 25 KB reply;
    the payloads here are already JSON types. Anything else still takes the framework's path."""

    if type(payload) is not dict:
        return payload
    try:
        return JSONResponse(content=payload)
    except (TypeError, ValueError):
        return payload


def _gid(raw: str) -> str:
    try:
        return str(uuid.UUID(raw))
    except ValueError:
        raise HTTPException(status_code=404, detail="Game not found.") from None


def _lock_for(game_id: str) -> threading.Lock:
    return _STRIPES[hash(game_id) % len(_STRIPES)]


def _env(is_pro: bool, state: GameState | None, reason: str = "", **extra: Any) -> dict[str, Any]:
    return {
        "ok": True, "reason": reason, "is_premium": is_pro, "upsell": None,
        "preview": view.preview_block(is_pro, state), **extra,
    }


def _premium(state: GameState | None) -> dict[str, Any]:
    return {
        "ok": True, "reason": "premium_required", "is_premium": False, "upsell": UPSELL_GAME,
        "preview": view.preview_block(False, state) or {"weeks_left": 0, "paywall_week": PREVIEW_PAYWALL_WEEK, "paywalled": True},
    }


POOL_CACHE_MAX = 24
# Why "start of this season" rosters are not offered (see docs/fantasy-sim-api.md).
SEASON_START_UNAVAILABLE = "no_roster_history"


def _pool_for(inputs: Any, scoring: Mapping[str, float]):
    """The player pool is read once per scoring format per half hour; every new
    game freezes its own copy, so this cache never affects a saved game."""

    key = json.dumps(sorted((str(k), float(v)) for k, v in scoring.items()))
    now = time.monotonic()
    with _POOL_LOCK:
        hit = _POOL_CACHE.get(key)
        if hit and now - hit[0] < POOL_TTL_SECONDS:
            return hit[1]
    if not hasattr(inputs, "player_pool"):
        raise SimInputsError("players_unavailable")
    pool = inputs.player_pool(dict(scoring))
    with _POOL_LOCK:
        _POOL_CACHE[key] = (now, pool)
        while len(_POOL_CACHE) > POOL_CACHE_MAX:
            _POOL_CACHE.pop(min(_POOL_CACHE, key=lambda k: _POOL_CACHE[k][0]))
    return pool


def clear_pool_cache() -> None:
    with _POOL_LOCK:
        _POOL_CACHE.clear()


def add_routes(router: APIRouter, ctx: GameApiCtx) -> None:
    require_user = ctx.require_user

    def unavailable(exc: SimStoreError | None = None) -> dict[str, Any]:
        out: dict[str, Any] = {"ok": True, "reason": "sim_storage_unavailable", "is_premium": True, "upsell": None, "preview": None}
        if exc is not None:
            out["detail"] = exc.code  # coarse code only; the full message is in the logs
            _log.warning("sim storage unavailable (%s): %s", exc.code, exc)
        return out

    def busy() -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "code": "server_busy", "reason": "sim_busy",
                     "error": "The simulator is busy. Try again in a moment."},
            headers={"Retry-After": "5"},
        )

    def guarded(fn: Callable[..., Any]) -> Callable[..., Any]:
        """Translate store/conflict/rule errors into the API's response shapes."""

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return _fast_json(fn(*args, **kwargs))
            except SimStoreError as exc:
                return unavailable(exc)
            except GameConflict:
                return JSONResponse(status_code=409, content={
                    "ok": False, "reason": "conflict", "error": "The game changed in another request. Reload and retry."})
            except GameError as exc:
                user = kwargs.get("user") or {}
                pro = bool(ctx.is_pro(user)) if user else True
                return {"ok": True, "reason": exc.code, "message": str(exc), "is_premium": pro,
                        "upsell": None, "preview": None, **exc.detail}
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from None

        return wrapper

    # ------------------------------------------------------------- helpers

    history_cache: "OrderedDict[tuple, dict[str, Any]]" = OrderedDict()
    history_lock = threading.Lock()

    def _history(store, uid: str, gid: str, row, kind: str, key: str, fold) -> dict[str, Any]:
        """A history fold is a pure function of the event log, and the row version (event count + save stamp, the same
        proof the state cache trusts) names exactly one log: reuse the result instead of re-reading and re-folding the
        whole log (a dynasty log is thousands of events). Bounded LRU; undo/redo changes the stamp so it misses."""

        ck = (uid, gid, row_version(row), kind, key)
        with history_lock:
            hit = history_cache.get(ck)
            if hit is not None:
                history_cache.move_to_end(ck)
                return hit
        out = fold(store.load_events(uid, gid))
        with history_lock:
            history_cache[ck] = out
            while len(history_cache) > 64:
                history_cache.popitem(last=False)
        return out

    def load(user: dict[str, Any], game_id: str, *, write: bool = False):
        """Row (the version check), frozen snapshot and folded state. The state is a shared read-only
        instance from the in-process cache; a caller that will change it passes ``write=True`` and gets
        its own copy (published back by ``commit`` once the events are written)."""

        uid = str(user.get("id") or "")
        store = ctx.store_for(user)
        row = store.get_game(uid, game_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Game not found.")
        snap, state = store.load_game(uid, game_id, row)
        if snap is None or state is None:
            raise HTTPException(status_code=404, detail="Game not found.")
        if write:
            state = state.clone()
        return store, uid, row, snap.season_view(state.view_no), state

    def commit(store: GameStore, uid: str, game_id: str, snap: GameSnapshot, state: GameState,
               em: Emitter, *, checkpoint: bool = False, defer: bool = False):
        """Persist ``em.events``. With ``defer`` the bookkeeping writes overlap the caller's response
        building and the caller must call ``.finish()`` on the returned handle before replying."""

        week = (state.season_no - 1) * 100 + state.week if checkpoint else None  # weeks restart each dynasty season
        pending = store.commit(
            uid, game_id, state, em.events, checkpoint_week=week,
            prev_checkpoint_week=store.cached_checkpoint_week(uid, game_id),
        )
        if defer:
            return pending
        pending.finish()
        return None

    def game_json(row, snap, state, pro):
        return view.game_view(row, snap, state, is_pro=pro)

    def heal_draft(store, uid, game_id, snap, state, seed) -> GameState:
        """A draft left with an AI team on the clock (a create interrupted after
        the game row was written) resumes on the next read. Returns the state to use: the
        given (shared, read-only) one when nothing needed doing, else a healed copy."""

        if state.status != "drafting":
            return state
        if snap.start_rosters:  # an imported league never drafts: finish its interrupted start
            state = state.clone()
            em = Emitter(state, snap)
            start_from_league(em, snap, state, seed)
            commit(store, uid, game_id, snap, state, em, checkpoint=True)
            return state
        dctx = draft.DraftContext(snap, state)
        if dctx.on_clock() is not None and dctx.on_clock() != snap.user_team.tid:
            state = state.clone()
            dctx = draft.DraftContext(snap, state)
            em = Emitter(state, snap)
            draft.run_ai_picks(dctx, em, seed)
            if state.pick_index >= dctx.total:
                finish_draft(em, snap, state, seed)
            commit(store, uid, game_id, snap, state, em, checkpoint=state.status != "drafting")
        return state

    # --------------------------------------------------------------- options

    @router.get("/games/options")
    def game_options(user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        s = GameSettings()
        return {
            **_env(pro, None), "engine_version": GAME_ENGINE_VERSION,
            "max_games": MAX_GAMES_PRO if pro else MAX_GAMES_FREE,
            # Quick start = every default below; everything else is "Advanced options".
            "options": {
                "mode": {"values": [m["id"] for m in mode_options() if m["available"]], "default": "redraft",
                         "modes": mode_options()},
                "teams": {"values": list(TEAM_COUNTS), "default": DEFAULT_TEAMS},
                "scoring": {"values": list(SCORING_NAMES), "default": DEFAULT_SCORING},
                "te_premium": {"values": list(TE_PREMIUMS), "default": 0.0},
                "superflex": {"default": False},
                "include_k": {"default": True},
                "include_def": {"default": False},
                "bench": {"min": BENCH_RANGE[0], "max": BENCH_RANGE[1], "default": DEFAULT_BENCH},
                "difficulty": {"values": list(DIFFICULTIES), "default": "normal"},
                "user_slot": {"min": 1, "max": max(TEAM_COUNTS), "default": None},
                "auto_lineup": {"default": False},
                "team_names": {"values": list(TEAM_NAMES), "max_length": USER_TEAM_NAME_MAX},
                "tiebreaker": {"values": list(TIEBREAKERS), "default": DEFAULT_TIEBREAKER},
                # IR and taxi squads (taxi defaults to 4 in dynasty, 0 in redraft; a league import reads its own).
                "ir_slots": {"min": IR_SLOT_RANGE[0], "max": IR_SLOT_RANGE[1], "default": DEFAULT_IR_SLOTS},
                "taxi_slots": {"min": TAXI_SLOT_RANGE[0], "max": TAXI_SLOT_RANGE[1], "default": 0,
                               "default_dynasty": DEFAULT_TAXI_SLOTS_DYNASTY},
                "taxi_years": {"values": [1, 2, 3, 4], "default": DEFAULT_TAXI_YEARS},
                # Dynasty only.
                "seasons": {"values": list(SEASON_CHOICES), "default": DEFAULT_SEASONS},
                "rookie_rounds": {"values": list(ROOKIE_ROUNDS), "default": DEFAULT_ROOKIE_ROUNDS},
            },
            "dynasty": {"pick_years": PICK_YEARS, "max_seasons": max(SEASON_CHOICES), "start_year": default_start_year()},
            # Draft rounds are derived: roster size minus the spots left for the wire.
            "layout": {"base_slots": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX"], "draft_spare_spots": DRAFT_SPARE_SPOTS},
            "start_modes": [
                {"id": START_FRESH, "available": True},
                {"id": START_LEAGUE, "available": hasattr(ctx.inputs, "league_import") and ctx.sleeper_username is not None},
                {"id": "season_start", "available": False, "reason": SEASON_START_UNAVAILABLE},
            ],
            "season": {
                "regular_weeks": s.regular_weeks, "playoff_weeks": s.playoff_weeks, "playoff_teams": s.playoff_teams,
                "trade_deadline_week": s.trade_deadline_week, "roster_limit": s.roster_limit,
                "draft_rounds": s.rounds, "slots": list(s.slots),
            },
            "personas": [
                {"id": p.pid, "label": p.label, "blurb": s.policy.blurbs.get(p.pid, p.blurb)}
                for p in PERSONAS.values()
            ],
        }

    # The real league's teams for the setup picker. Read-only, Sleeper only, and
    # declared before ``/games/{game_id}`` so the literal path wins.
    @router.get("/games/league-teams")
    @guarded
    def league_teams(league_id: str = "", user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        lid = str(league_id or "").strip()
        if not lid or len(lid) > 64:
            raise ValueError("league_id is required.")
        if not (hasattr(ctx.inputs, "league_teams") and ctx.sleeper_username is not None):
            return _env(pro, None, "league_unavailable")
        with ctx.compute() as ok:
            if not ok:
                return busy()
            try:
                found = ctx.inputs.league_teams(lid, username=ctx.sleeper_username(user))
            except SimInputsError as exc:
                return _env(pro, None, exc.code)
        return {
            **_env(pro, None), "league_id": found.league_id, "league_name": found.league_name, "season": found.season,
            "you_roster_id": found.you_roster_id or None,
            "teams": [{
                "roster_id": t.roster_id, "team_name": t.team_name, "owner_name": t.owner_name,
                "wins": t.wins, "losses": t.losses, "ties": t.ties, "points_for": t.points_for,
                "rank": t.rank, "is_you": t.is_you,
            } for t in found.teams],
        }

    # ----------------------------------------------------------- create/list

    @router.post("/games")
    @guarded
    def create_game(body: dict[str, Any] | None = Body(default=None), user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        uid = str(user.get("id") or "")
        raw = dict(body or {})
        team_name = " ".join(str(raw.pop("team_name", "") or "").split())
        random_name = raw.pop("random_team_name", False) is True
        if len(team_name) > USER_TEAM_NAME_MAX:
            raise ValueError("team_name must be at most 40 characters.")
        start = raw.pop("start", START_FRESH) or START_FRESH
        if start not in START_KINDS:
            raise ValueError("start must be one of: " + ", ".join(START_KINDS))
        league_id = str(raw.pop("league_id", "") or "").strip()
        roster_id = str(raw.pop("roster_id", "") or "").strip()
        seed = secrets.randbits(62)
        if start == START_LEAGUE:
            if not league_id or len(league_id) > 64:
                raise ValueError("league_id is required.")
            # Size, scoring and lineup come from the league; only these two are the player's choice.
            picked = GameSettings.parse({k: raw[k] for k in (
                "difficulty", "auto_lineup", "tiebreaker", "mode", "seasons", "rookie_rounds", "taxi_years",
            ) if k in raw})
            league_dynasty = picked.mode == "dynasty"
            ir_pick, taxi_pick = raw.get("ir_slots"), raw.get("taxi_slots")
            GameSettings.parse({k: v for k, v in (("ir_slots", ir_pick), ("taxi_slots", taxi_pick)) if v is not None})
        else:
            if raw.get("user_slot") is None:
                teams = raw.get("teams", DEFAULT_TEAMS)
                n = teams if isinstance(teams, int) and not isinstance(teams, bool) and teams in TEAM_COUNTS else DEFAULT_TEAMS
                raw["user_slot"] = int(WorldRng(seed).stream(0, "gsetup", 7).integers(1, n + 1))
            if raw.get("mode") == "dynasty" and not raw.get("start_year"):
                raw["start_year"] = default_start_year()
            settings = GameSettings.parse(raw)
        store = ctx.store_for(user)
        limit = MAX_GAMES_PRO if pro else MAX_GAMES_FREE
        if store.count_games(uid) >= limit:
            return {**_env(pro, None, "game_limit_reached", max_games=limit),
                    "upsell": None if pro else UPSELL_MORE_GAMES}
        if start == START_LEAGUE and not (hasattr(ctx.inputs, "league_import") and ctx.sleeper_username is not None):
            return _env(pro, None, "league_unavailable")
        with ctx.compute() as ok:
            if not ok:
                return busy()
            try:
                if start == START_LEAGUE:
                    extra_kw = {"dynasty": True} if league_dynasty else {}
                    imported = ctx.inputs.league_import(
                        league_id, username=ctx.sleeper_username(user), roster_id=roster_id, **extra_kw)
                    settings = league_settings(
                        imported, difficulty=picked.difficulty, auto_lineup=picked.auto_lineup, tiebreaker=picked.tiebreaker,
                        dynasty=league_dynasty, seasons=picked.seasons, ir_slots=ir_pick, taxi_slots=taxi_pick,
                    )
                    if league_dynasty and picked.rookie_rounds and not imported.rookie_rounds:
                        settings = replace(settings, rookie_rounds=picked.rookie_rounds)
                    pool = _pool_for(ctx.inputs, settings.scoring_settings)
                    snap = build_league_snapshot(
                        pool.rows, pool.bye_weeks, imported, settings, seed, user_team_name=team_name,
                        scoring_model=default_model().model_id, notes=pool.notes,
                    )
                else:
                    pool = _pool_for(ctx.inputs, settings.scoring_settings)
                    if random_name and not team_name:
                        team_name = pick_random_team_name(seed)
                    snap = build_snapshot(
                        pool.rows, pool.bye_weeks, settings, seed, user_team_name=team_name or "Your Team",
                        scoring_model=default_model().model_id, notes=pool.notes,
                    )
            except SimInputsError as exc:
                return _env(pro, None, exc.code)
        row = store.create_game(uid, snapshot=snap, seed=seed)
        state = GameState(snap)
        em = Emitter(state, snap)
        if start == START_LEAGUE:
            start_from_league(em, snap, state, seed)
            commit(store, uid, row["id"], snap, state, em, checkpoint=True)
            row = {**row, "status": state.status}
            return {**_env(pro, state), "game": game_json(row, snap, state, pro)}
        dctx = draft.DraftContext(snap, state)
        draft.run_ai_picks(dctx, em, seed)
        commit(store, uid, row["id"], snap, state, em)
        row = {**row, "status": state.status}
        return {**_env(pro, state), "game": game_json(row, snap, state, pro),
                **view.draft_view(snap, state, dctx, seed)}

    @router.get("/games")
    @guarded
    def list_games(user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        rows = ctx.store_for(user).list_games(str(user.get("id") or ""))
        return {**_env(pro, None), "games": [public_game_row(r) for r in rows],
                "max_games": MAX_GAMES_PRO if pro else MAX_GAMES_FREE}

    @router.get("/games/{game_id}")
    @guarded
    def get_game(game_id: str, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        gid = _gid(game_id)
        store, uid, row, snap, state = load(user, gid)
        state = heal_draft(store, uid, gid, snap, state, seedof(row, state))
        return {**_env(pro, state), "game": game_json(row, snap, state, pro)}

    @router.delete("/games/{game_id}")
    @guarded
    def delete_game(game_id: str, user: dict[str, Any] = Depends(require_user)):
        gid = _gid(game_id)
        ctx.store_for(user).delete_game(str(user.get("id") or ""), gid)
        return _env(ctx.is_pro(user), None)

    # ----------------------------------------------------------------- draft

    @router.get("/games/{game_id}/draft")
    @guarded
    def get_draft(
        game_id: str, page: int = 1, page_size: int = 40, pos: str = "", q: str = "",
        user: dict[str, Any] = Depends(require_user),
    ):
        pro = ctx.is_pro(user)
        gid = _gid(game_id)
        store, uid, row, snap, state = load(user, gid)
        seed = seedof(row, state)
        state = heal_draft(store, uid, gid, snap, state, seed)
        dctx = draft.DraftContext(snap, state)
        return {**_env(pro, state), **view.draft_view(snap, state, dctx, seed, page=page, page_size=page_size,
                                                      pos=pos.upper(), q=q)}

    def _finish_response(pro, row, snap, state, dctx, em, made, completed, recap, seed):
        owners = state.owner_map()
        ev = Evaluator(snap, state)
        return {
            **_env(pro, state),
            "picks": [view.pick_row(snap, state, ev, owners, p) for p in made],
            "draft": view.draft_view(snap, state, dctx, seed, full=False, page_size=1)["draft"],
            "completed": completed, "recap": recap, "game": game_json(row, snap, state, pro),
        }

    def _already_picked(state):
        return JSONResponse(status_code=409, content={
            "ok": False, "reason": "already_picked", "pick_no": min(state.pick_index + 1, 10_000),
            "error": "That pick was already made. Your draft board has been refreshed."})

    def _run_draft_command(user, game_id, command, expect_pick_no=None):
        pro = ctx.is_pro(user)
        gid = _gid(game_id)
        with _lock_for(gid):
            store, uid, row, snap, state = load(user, gid, write=True)
            if expect_pick_no is not None and state.status == "drafting" and expect_pick_no != state.pick_index + 1:
                return _already_picked(state)
            seed = seedof(row, state)
            state = heal_draft(store, uid, gid, snap, state, seed)
            dctx = draft.DraftContext(snap, state)
            em = Emitter(state, snap)
            with ctx.compute() as ok:
                if not ok:
                    return busy()
                made = command(dctx, em, seed)
                recap = None
                if state.pick_index >= dctx.total and state.status == "drafting":
                    recap = finish_draft(em, snap, state, seed)
            pending = commit(store, uid, gid, snap, state, em, checkpoint=recap is not None, defer=True)
            row = {**row, "status": state.status}
            out = _finish_response(pro, row, snap, state, dctx, em, made, recap is not None, recap, seed)
            pending.finish()
            return out

    @router.post("/games/{game_id}/draft/pick")
    @guarded
    def draft_pick(game_id: str, body: PickBody, user: dict[str, Any] = Depends(require_user)):
        return _run_draft_command(
            user, game_id, lambda dctx, em, seed: draft.user_pick(dctx, em, str(body.player_id), seed),
            expect_pick_no=body.pick_no,
        )

    @router.post("/games/{game_id}/draft/auto")
    @guarded
    def draft_auto(game_id: str, user: dict[str, Any] = Depends(require_user)):
        return _run_draft_command(user, game_id, lambda dctx, em, seed: draft.auto_for_user(dctx, em, seed))

    @router.put("/games/{game_id}/draft/queue")
    @guarded
    def draft_queue(game_id: str, body: QueueBody, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        gid = _gid(game_id)
        with _lock_for(gid):
            store, uid, row, snap, state = load(user, gid, write=True)
            if state.status != "drafting":
                raise GameError("wrong_phase", "The draft is over.", phase=state.status)
            em = Emitter(state, snap)
            draft.set_queue(draft.DraftContext(snap, state), em, body.player_ids)
            commit(store, uid, gid, snap, state, em)
            return {**_env(pro, state), "queue": list(state.queue)}

    # --------------------------------------------------------------- players

    @router.get("/games/{game_id}/players")
    @guarded
    def get_players(
        game_id: str, q: str = "", pos: str = "", status: str = "", team: str = "", sort: str = "projection",
        page: int = 1, page_size: int = 25, user: dict[str, Any] = Depends(require_user),
    ):
        pro = ctx.is_pro(user)
        _, _, row, snap, state = load(user, _gid(game_id))
        pos = pos.upper()
        if pos and pos not in GAME_POSITIONS and pos not in FLEX_SLOTS:
            raise ValueError("pos must be one of QB, RB, WR, TE, K, DEF, FLEX, REC_FLEX, SUPER_FLEX.")
        if status not in ("", "available", "rostered", "mine", "injured", "bye", "block"):
            raise ValueError("status must be available, rostered, mine, injured, bye or block.")
        if sort not in view.SORTS:
            raise ValueError("sort must be one of: " + ", ".join(view.SORTS))
        return {**_env(pro, state), **view.players_page(
            snap, state, q=q, pos=pos, status=status, team=team, sort=sort, page=page, page_size=page_size, seed=seedof(row, state))}

    @router.get("/games/{game_id}/players/{pid}")
    @guarded
    def get_player(game_id: str, pid: str, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        _, _, row, snap, state = load(user, _gid(game_id))
        if pid not in snap.players:
            raise HTTPException(status_code=404, detail="Player not found.")
        return {**_env(pro, state), **view.player_detail(snap, state, pid, seed=seedof(row, state))}

    @router.get("/games/{game_id}/players/{pid}/history")
    @guarded
    def get_player_history(game_id: str, pid: str, user: dict[str, Any] = Depends(require_user)):
        """Where a player came from and every move since, folded from the event log (fetched when the History tab opens)."""
        pro = ctx.is_pro(user)
        store, uid, row, snap, state = load(user, _gid(game_id))
        root = snap.root
        if not any(pid in root.season_view(n).players for n in range(1, max(1, int(root.settings.seasons)) + 1)):
            raise HTTPException(status_code=404, detail="Player not found.")
        return {**_env(pro, state), **_history(store, uid, _gid(game_id), row, "p", pid, lambda ev: hist.player_history(root, ev, pid))}

    @router.get("/games/{game_id}/teams/{team_id}/history")
    @guarded
    def get_team_history(game_id: str, team_id: str, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        store, uid, row, snap, state = load(user, _gid(game_id))
        if team_id not in snap.tids:
            raise HTTPException(status_code=404, detail="Team not found.")
        return {**_env(pro, state), **_history(store, uid, _gid(game_id), row, "t", team_id, lambda ev: hist.team_history(snap.root, ev, team_id))}

    @router.get("/games/{game_id}/teams/{team_id}")
    @guarded
    def get_team(game_id: str, team_id: str, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        _, _, row, snap, state = load(user, _gid(game_id))
        if team_id not in snap.tids:
            raise HTTPException(status_code=404, detail="Team not found.")
        return {**_env(pro, state), **home.team_detail(snap, state, team_id, seedof(row, state))}

    # ------------------------------------------------------------------ home

    @router.get("/games/{game_id}/home")
    @guarded
    def get_home(game_id: str, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        _, _, row, snap, state = load(user, _gid(game_id))
        if state.status not in ("in_season", "playoffs"):
            return {**_env(pro, state, "wrong_phase"),
                    "phase": {"drafting": "draft", "offseason": "offseason"}.get(state.status, "complete")}
        return {**_env(pro, state), **home.home_view(snap, state, seedof(row, state))}

    # ---------------------------------------------------------------- lineup

    @router.get("/games/{game_id}/lineup")
    @guarded
    def get_lineup(game_id: str, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        _, _, _, snap, state = load(user, _gid(game_id))
        if state.status == "drafting":
            return {**_env(pro, state, "wrong_phase"), "phase": "draft"}
        return {**_env(pro, state), **view.lineup_view(snap, state)}

    def _mutate(user, game_id, action, *, checkpoint=False, respond=None):
        """Load, gate, run ``action(em, snap, state, row, seed)``, persist, reply."""

        pro = ctx.is_pro(user)
        gid = _gid(game_id)
        with _lock_for(gid):
            store, uid, row, snap, state = load(user, gid, write=True)
            if view.paywalled(pro, state):
                return _premium(state)
            em = Emitter(state, snap)
            extra = action(em, snap, state, row, seedof(row, state))
            pending = commit(store, uid, gid, snap, state, em, checkpoint=checkpoint, defer=True)
            out = {**_env(pro, state), **(respond(snap, state) if respond else {}), **(extra or {}),
                   "delta": view.game_delta(snap, state)}
            pending.finish()
            return out

    def _lineup_resp(snap, state):
        return view.lineup_view(snap, state)

    @router.put("/games/{game_id}/lineup")
    @guarded
    def put_lineup(game_id: str, body: LineupBody, user: dict[str, Any] = Depends(require_user)):
        slots = [[s.slot, s.player_id] for s in body.slots]
        return _mutate(user, game_id, lambda em, *_: act.set_lineup(em, slots), respond=_lineup_resp)

    @router.post("/games/{game_id}/lineup/auto")
    @guarded
    def auto_lineup(game_id: str, user: dict[str, Any] = Depends(require_user)):
        return _mutate(user, game_id, lambda em, *_: act.auto_lineup(em), respond=_lineup_resp)

    # ------------------------------------------------------ waivers and cuts

    @router.post("/games/{game_id}/waivers")
    @guarded
    def post_waiver(game_id: str, body: WaiverBody, user: dict[str, Any] = Depends(require_user)):
        def run(em, snap, state, row, seed):
            claim = act.queue_claim(em, body.add, body.drop, body.start_slot)
            return {"claim_id": claim["id"]}

        def resp(snap, state):
            return {"claims": view.pending_claims(snap, state)}

        out = _mutate(user, game_id, run, respond=resp)
        if isinstance(out, dict) and out.get("reason") == "":
            out["claim"] = next((c for c in out["claims"] if c["id"] == out["claim_id"]), None)
        return out

    @router.delete("/games/{game_id}/waivers/{claim_id}")
    @guarded
    def delete_waiver(game_id: str, claim_id: str, user: dict[str, Any] = Depends(require_user)):
        return _mutate(user, game_id, lambda em, *_: act.cancel_claim(em, claim_id),
                       respond=lambda snap, state: {"claims": view.pending_claims(snap, state)})

    @router.post("/games/{game_id}/cut")
    @guarded
    def post_cut(game_id: str, body: CutBody, user: dict[str, Any] = Depends(require_user)):
        def resp(snap, state):
            return {"roster": view.team_roster(snap, state, snap.user_team.tid)["players"]}

        return _mutate(user, game_id, lambda em, *_: act.cut_player(em, body.player_id), respond=resp)

    # ---------------------------------------------------------------- trades

    @router.post("/games/{game_id}/trades/preview")
    @guarded
    def trade_preview(game_id: str, body: TradeBody, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        _, _, row, snap, state = load(user, _gid(game_id))
        desk = TradeDesk(Evaluator(snap, state), seedof(row, state))
        verdict = act.preview_trade(desk, body.partner, body.give, body.get)
        return {**_env(pro, state), "verdict": _verdict_json(snap, state, verdict), "executed": False, "trade": None}

    def _verdict_json(snap, state, verdict):
        out = verdict.to_dict()
        if verdict.counter:
            out["counter"] = {
                "give": view.players_for(snap, state, verdict.counter["give"]),
                "get": view.players_for(snap, state, verdict.counter["get"]),
            }
        return out

    @router.post("/games/{game_id}/trades")
    @guarded
    def trade_send(game_id: str, body: TradeBody, user: dict[str, Any] = Depends(require_user)):
        holder: dict[str, Any] = {}

        def run(em, snap, state, row, seed):
            desk = TradeDesk(Evaluator(snap, state), seed)
            verdict, trade = act.send_trade(em, desk, body.partner, body.give, body.get)
            holder["verdict"], holder["trade"] = verdict, trade
            if trade is not None:
                _resume_rookie_draft(em, state, seed)
            return None

        def resp(snap, state):
            verdict, trade = holder["verdict"], holder["trade"]
            return {
                "verdict": _verdict_json(snap, state, verdict), "executed": trade is not None, "trade": trade,
                "roster": view.team_roster(snap, state, snap.user_team.tid)["players"],
                "pending": {"roster_size": len(state.rosters[snap.user_team.tid]),
                            "roster_limit": snap.settings.roster_limit,
                            "cuts_needed": max(0, len(state.rosters[snap.user_team.tid]) - snap.settings.roster_limit)},
            }

        return _mutate(user, game_id, run, respond=resp)

    def _resume_rookie_draft(em, state, seed) -> None:
        """Picks change hands mid-draft: the order follows ownership, so if the pick on
        the clock is now an AI team's, it (and any AI picks after it) resolve now."""

        off = state.offseason
        if state.status == "offseason" and off and off.get("stage") == "rookie_draft":
            dyn.run_ai_rookie_picks(em, seed)

    # ----------------------------------------------------------------- inbox

    @router.get("/games/{game_id}/inbox")
    @guarded
    def get_inbox(game_id: str, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        _, _, _, snap, state = load(user, _gid(game_id))
        return {**_env(pro, state), "items": view.inbox_view(snap, state)}

    @router.get("/games/{game_id}/notifications")
    @guarded
    def get_notifications(game_id: str, since: int = 0, user: dict[str, Any] = Depends(require_user)):
        """The bell: items derived from the recent event log (see game_notifications), newest first, capped."""

        pro = ctx.is_pro(user)
        gid = _gid(game_id)
        store, uid, _, snap, state = load(user, gid)
        events = store.load_events(uid, gid, max(0, int(state.seq) - notif.EVENT_WINDOW))
        return {**_env(pro, state), **notif.derive(snap, state, events, max(0, int(since)))}

    @router.post("/games/{game_id}/inbox/{item_id}/respond")
    @guarded
    def respond_inbox(game_id: str, item_id: str, body: RespondBody, user: dict[str, Any] = Depends(require_user)):
        holder: dict[str, Any] = {}

        def run(em, snap, state, row, seed):
            holder["trade"] = act.respond_offer(em, TradeDesk(Evaluator(snap, state), seed), item_id, body.action)
            if holder["trade"] is not None:
                _resume_rookie_draft(em, state, seed)

        def resp(snap, state):
            return {"executed": holder["trade"] is not None, "trade": holder["trade"],
                    "items": view.inbox_view(snap, state)}

        return _mutate(user, game_id, run, respond=resp)

    # ------------------------------------------------------- advance / revert

    @router.post("/games/{game_id}/advance")
    @guarded
    def post_advance(game_id: str, body: AdvanceBody | None = Body(default=None),
                     user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        gid = _gid(game_id)
        want = body.week if body else None
        with _lock_for(gid):
            store, uid, row, snap, state = load(user, gid)
            if want is not None and want < state.week and str(want) in state.recaps:
                return {**_env(pro, state), "recap": state.recaps[str(want)], "also_played": [],
                        "replayed": True, "game": game_json(row, snap, state, pro)}
            if want is not None and want > state.week:
                raise GameError("week_mismatch", "That week has not started.", current_week=state.week)
            if view.paywalled(pro, state):
                return _premium(state)
            state = state.clone()
            em = Emitter(state, snap)
            with ctx.compute() as ok:
                if not ok:
                    return busy()
                recaps = advance(em, snap, state, seedof(row, state))
            pending = commit(store, uid, gid, snap, state, em, checkpoint=True, defer=True)
            snap = snap.season_view(state.view_no)  # the season may have ended into the offseason
            out = {**_env(pro, state), "recap": recaps[0], "also_played": recaps[1:], "replayed": False,
                   "game": game_json({**row, "status": state.status}, snap, state, pro)}
            pending.finish()
            return out

    @router.get("/games/{game_id}/sim-to/options")
    @guarded
    def sim_to_options(game_id: str, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        _, _, _, snap, state = load(user, _gid(game_id))
        return {**_env(pro, state), "options": simto.options_for(snap, state)}

    @router.post("/games/{game_id}/sim-to")
    @guarded
    def post_sim_to(game_id: str, body: SimToBody, user: dict[str, Any] = Depends(require_user)):
        """Play weeks in one request (see game_simto): the same Advance repeated, so the events are what that many
        Advances would write, one commit, one response. Stops early with a reason when you have something to decide."""
        pro = ctx.is_pro(user)
        gid = _gid(game_id)
        with _lock_for(gid):
            store, uid, row, snap, state = load(user, gid)
            if view.paywalled(pro, state):
                return _premium(state)
            state = state.clone()
            em = Emitter(state, snap)
            with ctx.compute() as ok:
                if not ok:
                    return busy()
                result = simto.run(em, snap, state, seedof(row, state), target=body.target, weeks=body.weeks, auto_set=body.auto_set,
                                   force_first=body.force_first, pro=pro, paywalled_fn=lambda s: view.paywalled(pro, s))
            if result["weeks_played"] == 0 and not em.events:
                return {**_env(pro, state), **{k: result[k] for k in ("target", "weeks_played", "stopped", "from_seq", "to_seq")},
                        "summary": None, "recap": None, "game": game_json(row, snap, state, pro)}
            pending = commit(store, uid, gid, snap, state, em, checkpoint=True, defer=True)
            snap = snap.season_view(state.view_no)
            out = {**_env(pro, state), **result, "game": game_json({**row, "status": state.status}, snap, state, pro)}
            pending.finish()
            return out

    @router.post("/games/{game_id}/undo-sim")
    @guarded
    def undo_sim(game_id: str, body: UndoSimBody, user: dict[str, Any] = Depends(require_user)):
        """Take back a 'Sim to...' (or any run of weeks): delete the events from ``from_seq``, which must be the start of an
        Advance (an ``advance`` event) the game has already played, and replay the rest. Same mechanism as revert-week,
        just back to an earlier week boundary."""
        pro = ctx.is_pro(user)
        gid = _gid(game_id)
        with _lock_for(gid):
            store, uid, row, snap, state = load(user, gid)
            if state.status == "drafting":
                raise GameError("wrong_phase", "Nothing to undo right now.", phase=state.status)
            if not 0 < body.from_seq <= state.seq:
                raise GameError("bad_seq", "That point is not in this game's history.")
            first = store.load_events(uid, gid, body.from_seq)[:1]
            if not first or first[0]["type"] not in ("advance", "lineup_set") or int(first[0]["seq"]) != body.from_seq:
                raise GameError("bad_seq", "You can only go back to the start of a week you simulated.")
            store.delete_checkpoints_after(uid, gid, body.from_seq)
            store.delete_events_from(uid, gid, body.from_seq)
            state = store.load_state(uid, gid, snap)
            store.touch(uid, gid, status=state.status, week=state.week, event_count=state.seq)
            snap = snap.season_view(state.view_no)
            return {**_env(pro, state), "undone": True, "game": game_json({**row, "status": state.status}, snap, state, pro)}

    @router.get("/games/{game_id}/block")
    @guarded
    def get_block(game_id: str, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        _, _, row, snap, state = load(user, _gid(game_id))
        if state.status == "drafting" and snap.settings.block:
            return {**_env(pro, state, "wrong_phase"), "phase": "draft"}
        return {**_env(pro, state), **home.block_view(snap, state, seedof(row, state))}

    @router.put("/games/{game_id}/block")
    @guarded
    def put_block(game_id: str, body: BlockBody, user: dict[str, Any] = Depends(require_user)):
        """Put an asset on (or take it off) your trade block, optionally with the position you are looking for."""

        def run(em, snap, state, row, seed):
            blockmod.set_block(em, body.asset_id, body.on, body.looking_for)
            return home.block_view(snap, state, seed)

        return _mutate(user, game_id, run)

    @router.post("/games/{game_id}/revert-week")
    @guarded
    def revert_week(game_id: str, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        gid = _gid(game_id)
        with _lock_for(gid):
            store, uid, row, snap, state = load(user, gid)
            if state.status in ("drafting", "complete", "offseason"):
                raise GameError("wrong_phase", "Nothing to revert right now.", phase=state.status)
            if view.paywalled(pro, state):
                return _premium(state)
            reverted = state.seq - state.boundary_seq
            if reverted > 0:
                # A checkpoint past the boundary (a sim-to that stopped at once still writes a marker event and a checkpoint)
                # would describe events that are about to be deleted: drop it first, as undo-sim does.
                store.delete_checkpoints_after(uid, gid, state.boundary_seq)
                store.delete_events_from(uid, gid, state.boundary_seq)
                state = store.load_state(uid, gid, snap)
                store.touch(uid, gid, status=state.status, week=state.week, event_count=state.seq)
            return {**_env(pro, state), "reverted": max(0, reverted), "game": game_json(row, snap, state, pro)}

    # ---------------------------------------------------- IR / taxi / picks

    @router.post("/games/{game_id}/roster/move")
    @guarded
    def roster_move(game_id: str, body: MoveBody, user: dict[str, Any] = Depends(require_user)):
        def resp(snap, state):
            return {**view.lineup_view(snap, state)}

        return _mutate(user, game_id, lambda em, *_: {"move": act.move_player(em, body.player_id, body.to)}, respond=resp)

    @router.get("/games/{game_id}/picks")
    @guarded
    def get_picks(game_id: str, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        _, _, _, snap, state = load(user, _gid(game_id))
        if not snap.settings.dynasty:
            return _env(pro, state, "not_dynasty")
        return {**_env(pro, state), **dview.picks_view(snap, state)}

    # --------------------------------------------------- dynasty offseason

    def _offseason_resp(pro, snap, state, row, **extra):
        snap = snap.season_view(state.view_no)
        return {**_env(pro, state), "game": game_json(row, snap, state, pro), "offseason": dview.offseason_view(snap, state), **extra}

    def _require_offseason(state):
        if state.status != "offseason":
            raise GameError("wrong_phase", "The offseason has not started.", phase=state.status)

    @router.get("/games/{game_id}/offseason")
    @guarded
    def get_offseason(game_id: str, pos: str = "", user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        _, _, row, snap, state = load(user, _gid(game_id))
        if not snap.settings.dynasty:
            return _env(pro, state, "not_dynasty")
        _require_offseason(state)
        return {**_env(pro, state), "game": game_json(row, snap, state, pro),
                "offseason": dview.offseason_view(snap, state, pos=pos.upper())}

    def _offseason_command(user, game_id, command):
        pro = ctx.is_pro(user)
        gid = _gid(game_id)
        with _lock_for(gid):
            store, uid, row, snap, state = load(user, gid, write=True)
            _require_offseason(state)
            em = Emitter(state, snap)
            with ctx.compute() as ok:
                if not ok:
                    return busy()
                made = command(em, snap, state, seedof(row, state))
            commit(store, uid, gid, snap, state, em, checkpoint=True)
            row = {**row, "status": state.status}
            return _offseason_resp(pro, snap, state, row, made=made or [])

    @router.post("/games/{game_id}/offseason/rookie-draft/start")
    @guarded
    def rookie_draft_start(game_id: str, user: dict[str, Any] = Depends(require_user)):
        def run(em, snap, state, seed):
            dyn.start_rookie_draft(em)
            return dyn.run_ai_rookie_picks(em, seed)

        return _offseason_command(user, game_id, run)

    @router.post("/games/{game_id}/offseason/rookie-draft/pick")
    @guarded
    def rookie_draft_pick(game_id: str, body: PickBody, user: dict[str, Any] = Depends(require_user)):
        return _offseason_command(user, game_id, lambda em, snap, state, seed: dyn.user_rookie_pick(em, str(body.player_id), seed))

    @router.post("/games/{game_id}/offseason/rookie-draft/auto")
    @guarded
    def rookie_draft_auto(game_id: str, user: dict[str, Any] = Depends(require_user)):
        return _offseason_command(user, game_id, lambda em, snap, state, seed: dyn.auto_rookie_draft(em, seed))

    @router.post("/games/{game_id}/offseason/start-season")
    @guarded
    def offseason_start_season(game_id: str, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        gid = _gid(game_id)
        with _lock_for(gid):
            store, uid, row, snap, state = load(user, gid, write=True)
            _require_offseason(state)
            em = Emitter(state, snap)
            with ctx.compute() as ok:
                if not ok:
                    return busy()
                dyn.start_next_season(em, seedof(row, state))
            commit(store, uid, gid, snap, state, em, checkpoint=True)
            return {**_env(pro, state), "game": game_json({**row, "status": state.status}, snap, state, pro)}

    @router.get("/games/{game_id}/dynasty")
    @guarded
    def get_dynasty(game_id: str, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        _, _, row, snap, state = load(user, _gid(game_id))
        if not snap.settings.dynasty:
            return _env(pro, state, "not_dynasty")
        return {**_env(pro, state), "dynasty": dview.summary_view(snap, state), "game": game_json(row, snap, state, pro)}

    # --------------------------------------------------------- league / result

    @router.get("/games/{game_id}/league")
    @guarded
    def get_league(game_id: str, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        _, _, _, snap, state = load(user, _gid(game_id))
        if state.status == "drafting":
            return {**_env(pro, state, "wrong_phase"), "phase": "draft"}
        return {**_env(pro, state), **view.league_view(snap, state)}

    @router.get("/games/{game_id}/league/rosters")
    @guarded
    def get_league_rosters(game_id: str, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        _, _, row, snap, state = load(user, _gid(game_id))
        if state.status == "drafting":
            return {**_env(pro, state, "wrong_phase"), "phase": "draft"}
        return {**_env(pro, state), **home.league_rosters(snap, state, seedof(row, state))}

    @router.get("/games/{game_id}/result")
    @guarded
    def get_result(game_id: str, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        gid = _gid(game_id)
        with _lock_for(gid):
            store, uid, row, snap, state = load(user, gid)
            if state.status != "complete":
                return {**_env(pro, state, "not_complete"), "game": game_json(row, snap, state, pro)}
            if snap.settings.dynasty:
                summary = dview.summary_view(snap, state)
                last = state.seasons[-1] if state.seasons else None
                result = {
                    "engine_version": GAME_ENGINE_VERSION, "seed": int(row["seed"]), "mode": "dynasty", "dynasty": summary,
                    "champion": last["champion"] if last else None, "final_standings": last["standings"] if last else [],
                    "grade": None, "decisions_that_mattered": [], "review": None, "weeks": [],
                }
                return {**_env(pro, state), "result": result, "game": game_json(row, snap, state, pro)}
            result = store.get_result(uid, gid)
            if result is None:
                with ctx.compute() as ok:
                    if not ok:
                        return busy()
                    events = store.load_events(uid, gid, 0)
                    try:
                        result = build_result(snap, seedof(row, state), events, state)
                        json.dumps(result, allow_nan=False)  # fail here, not inside the storage call
                    except (SimStoreError, GameConflict):
                        raise
                    except Exception:  # noqa: BLE001 - reported with a specific reason below
                        _log.exception("sim result build failed game=%s", gid)
                        return {**_env(pro, state, "result_build_failed"),
                                "message": "We could not grade this season. Your game is saved; try again shortly.",
                                "game": game_json(row, snap, state, pro)}
                try:
                    store.save_result(uid, gid, result, (result.get("grade") or {}).get("letter"))
                except SimStoreError:
                    # The grade is computed; serve it now and recompute next time rather than fail.
                    _log.warning("sim result could not be saved game=%s", gid, exc_info=True)
            if "review" not in result:
                # Stored before the Season in Review existed: add it now (read-only, no replays).
                try:
                    events = store.load_events(uid, gid, 0)
                    result = {**result, "review": build_review(snap, events, state, _draft_for_review(snap, events, state))}
                    store.save_result(uid, gid, result, (result.get("grade") or {}).get("letter"))
                except Exception:  # noqa: BLE001 - the grade still ships without it
                    _log.warning("sim review backfill failed game=%s", gid, exc_info=True)
            letter = (result.get("grade") or {}).get("letter")
            return {**_env(pro, state), "result": result, "game": game_json(
                {**row, "grade_letter": letter}, snap, state, pro)}


def _role_json(players, role) -> dict[str, Any] | None:
    if role is None or role.kind == "exempt":
        return None
    covering = players[role.covering].name if role.covering else None
    label = {"fill_in": f"Starting while {covering} is out", "backup": "Backup"}.get(role.kind)
    return {"kind": role.kind, "label": label, "covering": role.covering or None, "covering_name": covering}


def add_preview_route(router: APIRouter, ctx: GameApiCtx) -> None:
    """Signed-out browse: projections only, no state, no storage."""

    @router.get("/preview/players")
    def preview_players(
        q: str = "", pos: str = "", sort: str = "projection", page: int = 1, page_size: int = 25,
        scoring: str = "ppr",
    ):
        if scoring not in SCORING_NAMES:
            raise HTTPException(status_code=422, detail="scoring must be one of: " + ", ".join(SCORING_NAMES))
        pos = pos.upper()
        if pos and pos not in POSITIONS:
            raise HTTPException(status_code=422, detail="pos must be one of QB, RB, WR, TE, K.")
        if sort not in ("projection", "value", "adp", "age", "name"):
            raise HTTPException(status_code=422, detail="sort must be projection, value, adp, age or name.")
        with ctx.compute() as ok:
            if not ok:
                return JSONResponse(
                    status_code=503, headers={"Retry-After": "5"},
                    content={"ok": False, "code": "server_busy", "reason": "sim_busy", "error": "The simulator is busy."})
            try:
                pool = _pool_for(ctx.inputs, SCORING_PRESETS[scoring])
                players = finalize_pool(pool.rows, GameSettings.parse({"scoring": scoring}))
            except SimInputsError as exc:
                return {"ok": True, "reason": exc.code, "players": [], "total": 0, "page": 1, "page_size": 0, "scoring": scoring}
        needle = q.strip().lower()
        rows = [p for p in players.values() if (not pos or p.pos == pos) and (not needle or needle in p.name.lower())]
        # Team roles (what new games use): one fill-in per injured starter, other backups at their baseline.
        roles = week_one_roles(players)
        shown = {
            pid: round(tr_soft_ceiling(p.mean * (r.mult if (r := roles.get(pid)) else 1.0) + (r.add if r else 0.0), PROJ_CEIL.get(p.pos)), 1)
            for pid, p in players.items()
        }
        keys = {
            "projection": lambda p: (-shown[p.pid], p.pid), "value": lambda p: (-p.value, p.pid),
            "adp": lambda p: (p.adp, p.pid), "age": lambda p: (p.age, p.pid), "name": lambda p: (p.name.lower(), p.pid),
        }
        rows.sort(key=keys[sort])
        page_size = max(1, min(view.PAGE_MAX, page_size))
        page = max(1, page)
        chunk = rows[(page - 1) * page_size: page * page_size]
        return {
            "ok": True, "reason": "", "scoring": scoring, "total": len(rows), "page": page, "page_size": page_size,
            "players": [{
                "id": p.pid, "headshot_id": headshot_id(p.pid), "name": p.name, "pos": p.pos, "team": p.nfl_team,
                "age": p.age, "projection": shown[p.pid], "if_starts": p.mean,
                "role": _role_json(players, roles.get(p.pid)), "floor": round(max(0.0, p.mean - 0.8 * p.sd), 1),
                "ceiling": round(p.mean + 0.8 * p.sd, 1), "value": p.value, "adp": p.adp,
                "bye_week": pool.bye_weeks.get(p.nfl_team) or None,
            } for p in chunk],
        }


__all__ = ["GameApiCtx", "add_routes", "add_preview_route", "clear_pool_cache", "UPSELL_GAME"]


def _draft_for_review(snap, events, state):
    """The draft recap the grade used (event payload when present, else rebuilt from state)."""

    found = next((e["payload"]["recap"] for e in events if e["type"] in ("draft_complete", "league_start")), None)
    return found if found is not None else _draft_from_state(snap, state)
