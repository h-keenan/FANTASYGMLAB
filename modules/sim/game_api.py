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
import json
import secrets
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, ContextManager, Mapping

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from modules.sim import game_actions as act
from modules.sim import game_draft as draft
from modules.sim import game_view as view
from modules.sim.game_ai import TradeDesk
from modules.sim.game_engine import advance, finish_draft, start_from_league
from modules.sim.game_eval import Evaluator
from modules.sim.game_result import build_result
from modules.sim.game_scoring import default_model
from modules.sim.game_setup import build_league_snapshot, build_snapshot, finalize_pool, league_settings
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_store import GameConflict, GameStore, public_game_row
from modules.sim.game_mode import mode_options
from modules.sim.game_types import (
    BENCH_RANGE,
    DEFAULT_BENCH,
    DEFAULT_SCORING,
    DEFAULT_TEAMS,
    DEFAULT_TIEBREAKER,
    DIFFICULTIES,
    DRAFT_SPARE_SPOTS,
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
    TEAM_COUNTS,
    GameError,
    GameSettings,
    GameSnapshot,
)
from modules.sim.personas import PERSONAS
from modules.sim.rng import WorldRng
from modules.sim.store import SimStoreError
from modules.sim.types import GAME_POSITIONS, POSITIONS, SimInputsError

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


class RespondBody(BaseModel):
    action: str


class AdvanceBody(BaseModel):
    week: int | None = None


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

    def unavailable() -> dict[str, Any]:
        return {"ok": True, "reason": "sim_storage_unavailable", "is_premium": True, "upsell": None, "preview": None}

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
                return fn(*args, **kwargs)
            except SimStoreError:
                return unavailable()
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

    def load(user: dict[str, Any], game_id: str):
        uid = str(user.get("id") or "")
        store = ctx.store_for(user)
        row = store.get_game(uid, game_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Game not found.")
        snap = store.get_snapshot(uid, game_id)
        if snap is None:
            raise HTTPException(status_code=404, detail="Game not found.")
        state = store.load_state(uid, game_id, snap)
        return store, uid, row, snap, state

    def commit(store: GameStore, uid: str, game_id: str, snap: GameSnapshot, state: GameState,
               em: Emitter, *, checkpoint: bool = False) -> None:
        store.append_events(uid, game_id, em.events)
        store.touch(uid, game_id, status=state.status, week=state.week, event_count=state.seq)
        if checkpoint:
            try:
                store.save_checkpoint(uid, game_id, state, state.week)
            except SimStoreError:
                pass  # the checkpoint is only a cache; events are the truth

    def game_json(row, snap, state, pro):
        return view.game_view(row, snap, state, is_pro=pro)

    def heal_draft(store, uid, game_id, snap, state, seed) -> None:
        """A draft left with an AI team on the clock (a create interrupted after
        the game row was written) resumes on the next read."""

        if state.status != "drafting":
            return
        if snap.start_rosters:  # an imported league never drafts: finish its interrupted start
            em = Emitter(state, snap)
            start_from_league(em, snap, state, seed)
            commit(store, uid, game_id, snap, state, em, checkpoint=True)
            return
        dctx = draft.DraftContext(snap, state)
        if dctx.on_clock() is not None and dctx.on_clock() != snap.user_team.tid:
            em = Emitter(state, snap)
            draft.run_ai_picks(dctx, em, seed)
            if state.pick_index >= dctx.total:
                finish_draft(em, snap, state, seed)
            commit(store, uid, game_id, snap, state, em, checkpoint=state.status != "drafting")

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
                "tiebreaker": {"values": list(TIEBREAKERS), "default": DEFAULT_TIEBREAKER},
            },
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

    # ----------------------------------------------------------- create/list

    @router.post("/games")
    @guarded
    def create_game(body: dict[str, Any] | None = Body(default=None), user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        uid = str(user.get("id") or "")
        raw = dict(body or {})
        team_name = str(raw.pop("team_name", "") or "").strip()
        if len(team_name) > 40:
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
            picked = GameSettings.parse({k: raw[k] for k in ("difficulty", "auto_lineup", "tiebreaker") if k in raw})
        else:
            if raw.get("user_slot") is None:
                teams = raw.get("teams", DEFAULT_TEAMS)
                n = teams if isinstance(teams, int) and not isinstance(teams, bool) and teams in TEAM_COUNTS else DEFAULT_TEAMS
                raw["user_slot"] = int(WorldRng(seed).stream(0, "gsetup", 7).integers(1, n + 1))
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
                    imported = ctx.inputs.league_import(
                        league_id, username=ctx.sleeper_username(user), roster_id=roster_id)
                    settings = league_settings(imported, difficulty=picked.difficulty, auto_lineup=picked.auto_lineup, tiebreaker=picked.tiebreaker)
                    pool = _pool_for(ctx.inputs, settings.scoring_settings)
                    snap = build_league_snapshot(
                        pool.rows, pool.bye_weeks, imported, settings, seed, user_team_name=team_name,
                        scoring_model=default_model().model_id, notes=pool.notes,
                    )
                else:
                    pool = _pool_for(ctx.inputs, settings.scoring_settings)
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
        heal_draft(store, uid, gid, snap, state, int(row["seed"]))
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
        seed = int(row["seed"])
        heal_draft(store, uid, gid, snap, state, seed)
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

    def _run_draft_command(user, game_id, command):
        pro = ctx.is_pro(user)
        gid = _gid(game_id)
        with _lock_for(gid):
            store, uid, row, snap, state = load(user, gid)
            seed = int(row["seed"])
            heal_draft(store, uid, gid, snap, state, seed)
            dctx = draft.DraftContext(snap, state)
            em = Emitter(state, snap)
            with ctx.compute() as ok:
                if not ok:
                    return busy()
                made = command(dctx, em, seed)
                recap = None
                if state.pick_index >= dctx.total and state.status == "drafting":
                    recap = finish_draft(em, snap, state, seed)
            commit(store, uid, gid, snap, state, em, checkpoint=recap is not None)
            row = {**row, "status": state.status}
            return _finish_response(pro, row, snap, state, dctx, em, made, recap is not None, recap, seed)

    @router.post("/games/{game_id}/draft/pick")
    @guarded
    def draft_pick(game_id: str, body: PickBody, user: dict[str, Any] = Depends(require_user)):
        return _run_draft_command(
            user, game_id, lambda dctx, em, seed: draft.user_pick(dctx, em, str(body.player_id), seed)
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
            store, uid, row, snap, state = load(user, gid)
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
        _, _, _, snap, state = load(user, _gid(game_id))
        pos = pos.upper()
        if pos and pos not in GAME_POSITIONS:
            raise ValueError("pos must be one of QB, RB, WR, TE, K, DEF.")
        if status not in ("", "available", "rostered", "mine", "injured", "bye"):
            raise ValueError("status must be available, rostered, mine, injured or bye.")
        if sort not in view.SORTS:
            raise ValueError("sort must be one of: " + ", ".join(view.SORTS))
        return {**_env(pro, state), **view.players_page(
            snap, state, q=q, pos=pos, status=status, team=team, sort=sort, page=page, page_size=page_size)}

    @router.get("/games/{game_id}/players/{pid}")
    @guarded
    def get_player(game_id: str, pid: str, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        _, _, _, snap, state = load(user, _gid(game_id))
        if pid not in snap.players:
            raise HTTPException(status_code=404, detail="Player not found.")
        return {**_env(pro, state), **view.player_detail(snap, state, pid)}

    @router.get("/games/{game_id}/teams/{team_id}")
    @guarded
    def get_team(game_id: str, team_id: str, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        _, _, _, snap, state = load(user, _gid(game_id))
        if team_id not in snap.tids:
            raise HTTPException(status_code=404, detail="Team not found.")
        return {**_env(pro, state), **view.team_roster(snap, state, team_id)}

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
            store, uid, row, snap, state = load(user, gid)
            if view.paywalled(pro, state):
                return _premium(state)
            em = Emitter(state, snap)
            extra = action(em, snap, state, row, int(row["seed"]))
            commit(store, uid, gid, snap, state, em, checkpoint=checkpoint)
            return {**_env(pro, state), **(respond(snap, state) if respond else {}), **(extra or {})}

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
        desk = TradeDesk(Evaluator(snap, state), int(row["seed"]))
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

    # ----------------------------------------------------------------- inbox

    @router.get("/games/{game_id}/inbox")
    @guarded
    def get_inbox(game_id: str, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        _, _, _, snap, state = load(user, _gid(game_id))
        return {**_env(pro, state), "items": view.inbox_view(snap, state)}

    @router.post("/games/{game_id}/inbox/{item_id}/respond")
    @guarded
    def respond_inbox(game_id: str, item_id: str, body: RespondBody, user: dict[str, Any] = Depends(require_user)):
        holder: dict[str, Any] = {}

        def run(em, snap, state, row, seed):
            holder["trade"] = act.respond_offer(em, TradeDesk(Evaluator(snap, state), seed), item_id, body.action)

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
            em = Emitter(state, snap)
            with ctx.compute() as ok:
                if not ok:
                    return busy()
                recaps = advance(em, snap, state, int(row["seed"]))
            commit(store, uid, gid, snap, state, em, checkpoint=True)
            return {**_env(pro, state), "recap": recaps[0], "also_played": recaps[1:], "replayed": False,
                    "game": game_json({**row, "status": state.status}, snap, state, pro)}

    @router.post("/games/{game_id}/revert-week")
    @guarded
    def revert_week(game_id: str, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        gid = _gid(game_id)
        with _lock_for(gid):
            store, uid, row, snap, state = load(user, gid)
            if state.status in ("drafting", "complete"):
                raise GameError("wrong_phase", "Nothing to revert right now.", phase=state.status)
            if view.paywalled(pro, state):
                return _premium(state)
            reverted = state.seq - state.boundary_seq
            if reverted > 0:
                store.delete_events_from(uid, gid, state.boundary_seq)
                state = store.load_state(uid, gid, snap)
                store.touch(uid, gid, status=state.status, week=state.week, event_count=state.seq)
            return {**_env(pro, state), "reverted": max(0, reverted), "game": game_json(row, snap, state, pro)}

    # --------------------------------------------------------- league / result

    @router.get("/games/{game_id}/league")
    @guarded
    def get_league(game_id: str, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        _, _, _, snap, state = load(user, _gid(game_id))
        if state.status == "drafting":
            return {**_env(pro, state, "wrong_phase"), "phase": "draft"}
        return {**_env(pro, state), **view.league_view(snap, state)}

    @router.get("/games/{game_id}/result")
    @guarded
    def get_result(game_id: str, user: dict[str, Any] = Depends(require_user)):
        pro = ctx.is_pro(user)
        gid = _gid(game_id)
        with _lock_for(gid):
            store, uid, row, snap, state = load(user, gid)
            if state.status != "complete":
                return {**_env(pro, state, "not_complete"), "game": game_json(row, snap, state, pro)}
            result = store.get_result(uid, gid)
            if result is None:
                with ctx.compute() as ok:
                    if not ok:
                        return busy()
                    events = store.load_events(uid, gid, 0)
                    result = build_result(snap, int(row["seed"]), events, state)
                store.save_result(uid, gid, result, result["grade"]["letter"])
            return {**_env(pro, state), "result": result, "game": game_json(
                {**row, "grade_letter": result["grade"]["letter"]}, snap, state, pro)}


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
        keys = {
            "projection": lambda p: (-p.mean, p.pid), "value": lambda p: (-p.value, p.pid),
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
                "age": p.age, "projection": p.mean, "floor": round(max(0.0, p.mean - 0.8 * p.sd), 1),
                "ceiling": round(p.mean + 0.8 * p.sd, 1), "value": p.value, "adp": p.adp,
                "bye_week": pool.bye_weeks.get(p.nfl_team) or None,
            } for p in chunk],
        }


__all__ = ["GameApiCtx", "add_routes", "add_preview_route", "clear_pool_cache", "UPSELL_GAME"]
