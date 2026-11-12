"""``/v1/sim/*`` router, mounted only when ``SIM_ENABLED`` is on.

The router never imports the real service (no circular import, no reach into
real internals). The service hands it four callables through ``SimApiDeps``:
the auth dependency, a server-side Pro check, a Sleeper-username lookup and a
per-user storage backend factory. Pro gating follows the other Pro endpoints:
Free callers get HTTP 200 with ``reason: "premium_required"`` and an upsell,
and no sim work runs for them.
"""

from __future__ import annotations

import os
import secrets
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from modules.sim.analysis import run_world
from modules.sim import backend as sim_backend
from modules.sim import game_api
from modules.sim.game_store import GameStore
from modules.sim.version import ENGINE_VERSION
from modules.sim.inputs import MODES, RealSimInputs, SimInputs
from modules.sim.personas import PERSONAS
from modules.sim.store import (
    MAX_WORLDS_PER_USER,
    SimBackend,
    SimStore,
    SimStoreError,
    public_world,
)
from modules.sim.types import POSTURES, SimInputsError, Strategy

ENV_FLAG = "SIM_ENABLED"
MAX_CONCURRENT_COMPUTE = 2
_COMPUTE = threading.BoundedSemaphore(MAX_CONCURRENT_COMPUTE)
_COMPUTE_WAIT_SECONDS = 3.0

UPSELL = {
    "title": "Run a full season before it happens",
    "body": (
        "Season outlook is a Pro feature in your GM Plan: set a strategy for your real team and "
        "simulate the season against AI managers that trade and work the wire. "
        "Start your free trial to unlock it."
    ),
}


@contextmanager
def _compute_slot():
    """The sim's own bounded compute pool as a context manager: yields False
    (caller answers 503 server_busy) when it stays full."""

    acquired = _COMPUTE.acquire(timeout=_COMPUTE_WAIT_SECONDS)
    try:
        yield acquired
    finally:
        if acquired:
            _COMPUTE.release()


def sim_enabled(environ: Mapping[str, str] | None = None) -> bool:
    value = (environ if environ is not None else os.environ).get(ENV_FLAG, "")
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class SimApiDeps:
    require_user: Callable[..., dict[str, Any]]
    is_pro: Callable[[dict[str, Any]], bool]
    sleeper_username: Callable[[dict[str, Any]], str]
    # Supabase project config (the service's own getter); used to build the
    # per-user sim_* backend unless ``backend_for`` overrides it (tests).
    supabase_config: Callable[[], dict] | None = None
    backend_for: Callable[[dict[str, Any]], SimBackend] | None = None
    inputs: SimInputs | None = None


class CreateWorldRequest(BaseModel):
    league_id: str
    mode: str = "remaining"
    roster_id: str = ""
    strategy: dict[str, Any] | None = None


class StrategyRequest(BaseModel):
    strategy: dict[str, Any]


def _reason(reason: str, **extra: Any) -> dict[str, Any]:
    return {"ok": True, "reason": reason, "is_premium": True, "upsell": None, **extra}


def _premium_required() -> dict[str, Any]:
    return {"ok": True, "reason": "premium_required", "is_premium": False, "upsell": UPSELL}


def _busy() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"ok": False, "code": "server_busy", "reason": "sim_busy",
                 "error": "The simulator is busy. Try again in a moment."},
        headers={"Retry-After": "5"},
    )


def _world_id(raw: str) -> str:
    try:
        return str(uuid.UUID(raw))
    except ValueError:
        raise HTTPException(status_code=404, detail="World not found.") from None


def _parse_strategy(raw: Mapping[str, Any] | None) -> Strategy:
    try:
        return Strategy.from_dict(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


def build_router(deps: SimApiDeps) -> APIRouter:
    router = APIRouter(prefix="/v1/sim", tags=["sim"])
    inputs = deps.inputs or RealSimInputs()

    def store_for(user: dict[str, Any]) -> SimStore:
        if deps.backend_for is not None:
            return SimStore(deps.backend_for(user))
        config = deps.supabase_config() if deps.supabase_config else {}
        return SimStore(sim_backend.backend_for(config, str(user.get("_access_token") or "")))

    def unavailable() -> dict[str, Any]:
        return _reason("sim_storage_unavailable")

    def game_store_for(user: dict[str, Any]) -> GameStore:
        if deps.backend_for is not None:
            return GameStore(deps.backend_for(user))
        config = deps.supabase_config() if deps.supabase_config else {}
        return GameStore(sim_backend.backend_for(config, str(user.get("_access_token") or "")))

    # The interactive GM game (/v1/sim/games*, /v1/sim/preview/players).
    game_ctx = game_api.GameApiCtx(
        require_user=deps.require_user, is_pro=deps.is_pro, store_for=game_store_for,
        inputs=inputs, compute=_compute_slot, sleeper_username=deps.sleeper_username,
    )
    game_api.add_routes(router, game_ctx)
    game_api.add_preview_route(router, game_ctx)

    @router.get("/status")
    def get_status(user: dict[str, Any] = Depends(deps.require_user)) -> dict[str, Any]:
        if not deps.is_pro(user):
            return _premium_required()
        # Probe storage so the client can tell "tables missing / Supabase down"
        # (sim_storage_unavailable) from a working sim, instead of opening the
        # setup page and failing on the first run.
        try:
            store_for(user).list_worlds(str(user.get("id") or ""))
        except SimStoreError:
            return {**unavailable(), "enabled": True}
        return {
            **_reason(""),
            "enabled": True,
            "engine_version": ENGINE_VERSION,
            "modes": list(MODES),
            "max_worlds": MAX_WORLDS_PER_USER,
            "strategy_options": {
                "posture": {"values": list(POSTURES), "default": "balanced"},
                "trade_aggressiveness": {"min": 0.0, "max": 1.0, "default": 0.5},
                "waiver_aggressiveness": {"min": 0.0, "max": 1.0, "default": 0.5},
                "lineup_auto_set": {"default": True},
                "protected_player_ids": {"max": 50, "default": []},
            },
            "personas": [
                {"id": p.pid, "label": p.label, "blurb": p.blurb} for p in PERSONAS.values()
            ],
        }

    @router.post("/worlds")
    def create_world(body: CreateWorldRequest, user: dict[str, Any] = Depends(deps.require_user)):
        if not deps.is_pro(user):
            return _premium_required()
        if body.mode not in MODES:
            raise HTTPException(status_code=422, detail="mode must be one of: " + ", ".join(MODES))
        league_id = body.league_id.strip()
        if not league_id or len(league_id) > 64:
            raise HTTPException(status_code=422, detail="league_id is required.")
        strategy = _parse_strategy(body.strategy)
        user_id = str(user.get("id") or "")
        store = store_for(user)
        try:
            if store.count_worlds(user_id) >= MAX_WORLDS_PER_USER:
                return _reason("world_limit_reached", max_worlds=MAX_WORLDS_PER_USER)
        except SimStoreError:
            return unavailable()
        if not _COMPUTE.acquire(timeout=_COMPUTE_WAIT_SECONDS):
            return _busy()
        try:
            try:
                snapshot = inputs.league_snapshot(
                    league_id, mode=body.mode, username=deps.sleeper_username(user), roster_id=body.roster_id
                )
            except SimInputsError as exc:
                return _reason(exc.code)
        finally:
            _COMPUTE.release()
        unknown = [p for p in strategy.protected_player_ids if p not in snapshot.user_team.roster]
        if unknown:
            raise HTTPException(status_code=422, detail="protected_player_ids must be on your roster.")
        try:
            world = store.create_world(
                user_id, league_id=league_id, snapshot=snapshot, strategy=strategy, seed=secrets.randbits(62)
            )
        except SimStoreError:
            return unavailable()
        return _reason(
            "", world=public_world(world), notes=list(snapshot.notes),
            team={"team_id": snapshot.user_team.tid, "name": snapshot.user_team.name},
        )

    @router.get("/worlds")
    def list_worlds(user: dict[str, Any] = Depends(deps.require_user)):
        if not deps.is_pro(user):
            return _premium_required()
        try:
            rows = store_for(user).list_worlds(str(user.get("id") or ""))
        except SimStoreError:
            return unavailable()
        return _reason("", worlds=[public_world(r) for r in rows], max_worlds=MAX_WORLDS_PER_USER)

    @router.get("/worlds/{world_id}")
    def get_world(world_id: str, user: dict[str, Any] = Depends(deps.require_user)):
        if not deps.is_pro(user):
            return _premium_required()
        wid = _world_id(world_id)
        try:
            row = store_for(user).get_world(str(user.get("id") or ""), wid)
        except SimStoreError:
            return unavailable()
        if row is None:
            raise HTTPException(status_code=404, detail="World not found.")
        return _reason("", world=public_world(row))

    @router.put("/worlds/{world_id}/strategy")
    def put_strategy(world_id: str, body: StrategyRequest, user: dict[str, Any] = Depends(deps.require_user)):
        if not deps.is_pro(user):
            return _premium_required()
        wid = _world_id(world_id)
        strategy = _parse_strategy(body.strategy)
        user_id = str(user.get("id") or "")
        store = store_for(user)
        try:
            if store.get_world(user_id, wid) is None:
                raise HTTPException(status_code=404, detail="World not found.")
            snapshot = store.get_snapshot(user_id, wid)
            if snapshot is not None:
                unknown = [p for p in strategy.protected_player_ids if p not in snapshot.user_team.roster]
                if unknown:
                    raise HTTPException(status_code=422, detail="protected_player_ids must be on your roster.")
            store.set_strategy(user_id, wid, strategy)
            row = store.get_world(user_id, wid)
        except SimStoreError:
            return unavailable()
        return _reason("", world=public_world(row or {}))

    @router.post("/worlds/{world_id}/run")
    def run(world_id: str, user: dict[str, Any] = Depends(deps.require_user)):
        if not deps.is_pro(user):
            return _premium_required()
        wid = _world_id(world_id)
        user_id = str(user.get("id") or "")
        store = store_for(user)
        try:
            row = store.get_world(user_id, wid)
            if row is None:
                raise HTTPException(status_code=404, detail="World not found.")
            if row.get("status") == "simulated":
                existing = store.get_result(user_id, wid)
                if existing is not None:
                    return _reason("", world=public_world(row), result=existing)
            snapshot = store.get_snapshot(user_id, wid)
        except SimStoreError:
            return unavailable()
        if snapshot is None:
            raise HTTPException(status_code=404, detail="World snapshot not found.")
        strategy = _parse_strategy(row.get("strategy"))
        if not _COMPUTE.acquire(timeout=_COMPUTE_WAIT_SECONDS):
            return _busy()
        try:
            result = run_world(snapshot, strategy, int(row["seed"]))
        finally:
            _COMPUTE.release()
        try:
            store.save_result(user_id, wid, result)
            row = store.get_world(user_id, wid) or row
        except SimStoreError:
            return unavailable()
        return _reason("", world=public_world(row), result=result)

    @router.get("/worlds/{world_id}/result")
    def get_result(world_id: str, user: dict[str, Any] = Depends(deps.require_user)):
        if not deps.is_pro(user):
            return _premium_required()
        wid = _world_id(world_id)
        user_id = str(user.get("id") or "")
        try:
            store = store_for(user)
            row = store.get_world(user_id, wid)
            if row is None:
                raise HTTPException(status_code=404, detail="World not found.")
            result = store.get_result(user_id, wid)
        except SimStoreError:
            return unavailable()
        if result is None:
            return _reason("not_simulated", world=public_world(row))
        return _reason("", world=public_world(row), result=result)

    @router.delete("/worlds/{world_id}")
    def delete_world(world_id: str, user: dict[str, Any] = Depends(deps.require_user)):
        if not deps.is_pro(user):
            return _premium_required()
        wid = _world_id(world_id)
        try:
            store_for(user).delete_world(str(user.get("id") or ""), wid)
        except SimStoreError:
            return unavailable()
        return _reason("")

    return router


def mount(app: Any, deps: SimApiDeps, environ: Mapping[str, str] | None = None) -> bool:
    """Include the sim router on ``app`` iff SIM_ENABLED is on. Returns whether it did."""

    if not sim_enabled(environ):
        return False
    app.include_router(build_router(deps))
    return True
