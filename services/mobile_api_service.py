"""Mobile app API service (Expo/React Native client).

Deployment topology (Render):
  - Service name: fantasygmlab-mobile-api
  - Entrypoint: uvicorn services.mobile_api_service:app --host 0.0.0.0 --port $PORT
  - GET  /health              — process liveness (no Supabase dependency)
  - GET  /ready               — Supabase config readiness (no secret values)
  - GET  /v1/me               — authenticated user + entitlement
  - GET  /v1/leagues/{id}                — Sleeper league metadata
  - GET  /v1/leagues/{id}/users          — Sleeper league members
  - GET  /v1/leagues/{id}/rosters        — Sleeper league rosters
  - GET  /v1/players?ids=1,2,3           — minimal Sleeper player info by id

Auth model: the mobile app signs the user in against Supabase directly
(same `auth.users` table as the web app) and sends the resulting access
token as `Authorization: Bearer <token>` on every request. This service
verifies that token against Supabase Auth (GoTrue `/auth/v1/user`) on each
request — it never sees a password and never holds the service-role key.
Profile/entitlement reads use the caller's own token so Postgres Row Level
Security (not this service) decides what they can see, matching the web
app's client-side Supabase usage.

This service intentionally contains no fantasy-analytics logic of its own —
it is a thin JSON wrapper around the existing `modules.sleeper` data access
so the web app and mobile app share one engine.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

import requests

from modules import auth_supabase, sleeper


SERVICE_NAME = "mobile-api"

app = FastAPI(
    title="FantasyGM Lab Mobile API",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.exception_handler(HTTPException)
async def _http_exception_handler(_request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": detail})


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(_request: Request, _exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"ok": False, "error": "Invalid request."})


@app.exception_handler(Exception)
async def _unhandled_exception_handler(_request: Request, _exc: Exception):
    return JSONResponse(status_code=500, content={"ok": False, "error": "Request failed."})


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": SERVICE_NAME,
        "health": "/health",
        "ready": "/ready",
        "me": "/v1/me",
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness only — must not depend on Supabase reachability."""

    return {"status": "ok"}


@app.get("/ready")
def ready() -> JSONResponse:
    """Readiness: Supabase client config present; never returns secret values."""

    config = auth_supabase.get_supabase_config()
    if not auth_supabase.is_configured(config):
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "issues": ["supabase_not_configured"]},
        )
    return JSONResponse(content={"status": "ready", "service": SERVICE_NAME})


def _bearer_token(authorization: str | None) -> str:
    value = (authorization or "").strip()
    if not value:
        raise HTTPException(status_code=401, detail="Missing Authorization header.")
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Authorization header must be a Bearer token.")
    return token.strip()


def require_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """Verify the caller's Supabase access token and return the auth user.

    Calls GoTrue `/auth/v1/user` on every request rather than verifying the
    JWT signature locally — this mirrors how the Streamlit app already
    treats Supabase as the source of truth for session validity (including
    revocation/expiry) and avoids holding a JWT secret in this service.
    """

    token = _bearer_token(authorization)
    config = auth_supabase.get_supabase_config()
    if not auth_supabase.is_configured(config):
        raise HTTPException(status_code=503, detail="Accounts are not configured.")
    user, error = auth_supabase.fetch_auth_user(config, token)
    if not user:
        raise HTTPException(status_code=401, detail=error or "Invalid or expired session.")
    normalized = auth_supabase.normalize_auth_user(user, access_token=token)
    normalized["_access_token"] = token
    return normalized


def _fetch_profile_entitlement(config: dict, user_id: str, access_token: str) -> str:
    """Read `profiles.entitlement` using the caller's own token (RLS-scoped)."""

    url = auth_supabase.rest_api_url(
        config,
        "profiles",
        f"select=entitlement&user_id=eq.{user_id}",
    )
    try:
        response = requests.get(
            url,
            headers=auth_supabase.auth_headers(config, access_token),
            timeout=15,
        )
    except Exception:
        return "free"
    if response.status_code >= 400:
        return "free"
    try:
        rows = response.json()
    except Exception:
        return "free"
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        entitlement = str(rows[0].get("entitlement") or "free").strip().lower()
        return entitlement if entitlement in {"free", "premium"} else "free"
    return "free"


@app.get("/v1/me")
def get_me(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    entitlement = "free"
    if user_id:
        entitlement = _fetch_profile_entitlement(config, user_id, str(user.get("_access_token") or ""))
    return {
        "ok": True,
        "user": {
            "id": user_id,
            "email": user.get("email") or "",
            "entitlement": entitlement,
        },
    }


@app.get("/v1/leagues/{league_id}")
def get_league(league_id: str, _user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")
    return {"ok": True, "league": league}


@app.get("/v1/leagues/{league_id}/users")
def get_league_users(league_id: str, _user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    return {"ok": True, "users": sleeper.get_users(league_id)}


@app.get("/v1/leagues/{league_id}/rosters")
def get_league_rosters(league_id: str, _user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    return {"ok": True, "rosters": sleeper.get_rosters(league_id)}


MAX_PLAYER_IDS_PER_REQUEST = 300

# Minimal, display-safe projection of Sleeper's player object — not the raw
# record (which also carries a dozen third-party IDs, scouting metadata,
# etc. nothing in this app needs).
_PLAYER_FIELDS = (
    "full_name",
    "first_name",
    "last_name",
    "position",
    "team",
    "status",
    "injury_status",
    "age",
    "number",
    "years_exp",
)


def _project_player(player: dict[str, Any]) -> dict[str, Any]:
    return {field: player.get(field) for field in _PLAYER_FIELDS}


@app.get("/v1/players")
def get_players(
    ids: str = "",
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    requested_ids = [part.strip() for part in ids.split(",") if part.strip()]
    if not requested_ids:
        raise HTTPException(status_code=422, detail="Provide at least one id in ?ids=.")
    if len(requested_ids) > MAX_PLAYER_IDS_PER_REQUEST:
        raise HTTPException(
            status_code=422,
            detail=f"Too many ids — max {MAX_PLAYER_IDS_PER_REQUEST} per request.",
        )

    all_players = sleeper.get_players()
    players = {
        player_id: _project_player(all_players[player_id])
        for player_id in requested_ids
        if player_id in all_players
    }
    return {"ok": True, "players": players}
