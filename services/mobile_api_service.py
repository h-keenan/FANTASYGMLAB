"""Mobile app API service (Expo/React Native client).

Deployment topology (Render):
  - Service name: fantasygmlab-mobile-api
  - Entrypoint: uvicorn services.mobile_api_service:app --host 0.0.0.0 --port $PORT
  - GET  /health              — process liveness (no Supabase dependency)
  - GET  /ready               — Supabase config readiness (no secret values)
  - GET  /v1/me               — authenticated user + entitlement + saved-league cap
  - GET  /v1/sleeper/leagues?username=x  — the Sleeper leagues behind a username (add-league picker)
  - POST /v1/leagues/save                — save a Sleeper league to the account (cap-enforced)
  - GET  /v1/leagues/{id}                — Sleeper league metadata
  - GET  /v1/leagues/{id}/users          — Sleeper league members
  - GET  /v1/leagues/{id}/rosters        — Sleeper league rosters
  - GET  /v1/leagues/{id}/team-profiles  — team name/owner/avatar per roster
  - GET  /v1/leagues/{id}/team-rankings  — power/franchise/draft-capital rank + standings per roster
  - GET  /v1/leagues/{id}/draft-center   — draft posture + league-wide decision/partner cards
  - GET  /v1/leagues/{id}/draft-picks    — every draft pick asset + its full valuation breakdown
  - GET  /v1/leagues/{id}/my-team        — your own roster's suggested starters vs. bench
  - GET  /v1/leagues/{id}/my-roster      — the signed-in user's own roster in this league
  - GET  /v1/players?ids=1,2,3           — minimal Sleeper player info by id
  - GET  /v1/leagues/{id}/rankings       — league-adjusted player rankings
  - GET  /v1/leagues/{id}/players/{id}/rank — one player's league-adjusted rank, looked up directly
  - GET  /v1/news                        — curated NFL fantasy news (injury/role/transaction/off-field)
  - GET  /v1/players/{id}/news           — recent news items matched to one player
  - POST /v1/leagues/{id}/trade-analyzer — real accept/decline/counter verdict for a proposed trade
  - GET  /v1/leagues/{id}/recap          — latest completed-week league recap
  - GET  /v1/leagues/{id}/alerts         — roster-relevant news alerts
  - POST /v1/leagues/{id}/alerts/read    — durably mark one alert read (RLS-scoped)
  - GET  /v1/players/{id}/quick-view     — season stats + bio for the player detail pop-up
  - GET  /v1/players/{id}/weekly-stats   — per-week fantasy points + snap share for one season
  - GET  /v1/players/{id}/career         — every verified season on record, not just current
  - GET  /v1/players/{id}/schedule       — real opponent/home-away/Vegas lines per week (context only)
  - GET  /v1/players/{id}/awards         — verified fantasy-performance badges (career history)
  - GET  /v1/leagues/{id}/gm-targets           — the caller's watchlist in this league
  - POST /v1/leagues/{id}/gm-targets           — add a player to the watchlist (cap-enforced)
  - DELETE /v1/leagues/{id}/gm-targets/{pid}   — remove a player from the watchlist
  - PATCH /v1/leagues/{id}/gm-targets/{pid}/untouchable — mark/unmark an existing target untouchable
  - POST /v1/push/register    — upsert the caller's Expo push token
  - POST /v1/push/unregister  — remove one of the caller's tokens (sign-out)
  - POST /v1/push/test        — send a test push to all of the caller's tokens
  - GET  /v1/leagues/{id}/dashboard — the caller's "Next Move" briefing
  - GET  /v1/leagues/{id}/trade-hub — real trade ideas for the caller's roster
  - GET  /v1/leagues/{id}/waivers   — roster-need-aware free-agent pool + FAAB guidance
  - POST /v1/leagues/{id}/trade-outcomes        — record a shared trade for later "did this happen?" follow-up
  - GET  /v1/trade-outcomes/pending             — this user's shared trades ready to be asked about
  - POST /v1/trade-outcomes/{id}/answer         — record yes/no/didnt_send, or snooze with still_pending
  - GET  /v1/preferences                        — cross-device display density + last-viewed league
  - POST /v1/preferences                        — partial update to those same preferences
  - GET  /v1/leagues/{id}/gm-stance             — the caller's remembered team strategy for this league
  - POST /v1/leagues/{id}/gm-stance             — set/update that stance (null strategy clears it)

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

import dataclasses
import hashlib
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field

import pandas as pd
import requests

from modules import (
    account_store,
    auth_supabase,
    canonical_player_ranking,
    dashboard_engine,
    draft_center_ui,
    faab,
    gm_targets,
    injury_ui,
    league_history,
    league_rankings,
    league_recaps,
    league_standings,
    league_value_settings,
    my_news,
    news as news_cache,
    news_signal,
    nfl_schedule,
    player_awards,
    player_eligibility,
    player_history,
    player_quick_view,
    player_state_authority,
    players_refresh_flight,
    push_tokens,
    push_triggers,
    rankings,
    saved_leagues,
    sleeper,
    sleeper_leagues,
    startup_cold_path,
    team_trade_history,
    trade_analyzer_fit,
    trade_hub_engine,
    trade_hub_ui,
    trade_ideas,
    trade_offer_analyzer,
    waivers_ui,
)
from modules.team_eval import normalize_team_strategy, refine_team_directions, suggest_optimal_lineup
from modules.trade_analyzer_assembly import pick_asset_from_mapping, player_asset_from_mapping


SERVICE_NAME = "mobile-api"

app = FastAPI(
    title="FantasyGM Lab Mobile API",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
# Full-league JSON payloads (rankings, draft-picks, trade-hub) are pandas-derived
# and can run into the hundreds of KB uncompressed — this app is consumed
# entirely over mobile networks, where that's real latency, not just bytes.
# 1KB minimum so tiny responses (health checks, single-player lookups)
# aren't paying gzip's per-request CPU cost for no bandwidth benefit.
app.add_middleware(GZipMiddleware, minimum_size=1024)


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
    """Liveness only — must not depend on Supabase reachability.

    Also piggybacks the same stale-while-revalidate players refresh
    require_user triggers for authenticated requests (see
    _maybe_schedule_players_refresh's docstring) — this endpoint needs no
    auth and is already pinged every 10 minutes by the keep-alive workflow
    (.github/workflows/keep-alive.yml), so it doubles as a reliable,
    traffic-independent freshness check: injury_status/score/rank no longer
    depend on a real user happening to hit an authenticated endpoint after
    the hourly Sleeper cache goes stale.
    """

    _maybe_schedule_players_refresh()
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


def _maybe_schedule_players_refresh() -> None:
    """Best-effort stale-while-revalidate refresh of data/players.db.

    Before this, the mobile API's own load pattern (`load_players` → build
    only if the file is missing/empty) never revalidated an existing file —
    a player's injury_status, score, and rank could go stale indefinitely as
    long as data/players.db existed at all. The web app already solved this
    exact problem with modules.players_refresh_flight/startup_cold_path
    (process-scoped single-flight, background thread, cooldown after
    failure), so this reuses that instead of inventing a second mechanism.

    Lives in require_user (every authenticated request depends on it, same
    as /v1/news's own per-request TTL check) rather than in each of the ~15
    individual endpoints that load PLAYERS_DB_PATH — one hook covers all of
    them. A fresh throwaway dict is passed as "session_state" each call:
    the real single-flight/cooldown guards are the module-level state
    inside players_refresh_flight, not this dict — reusing one dict across
    calls would behave like Streamlit's "only ever once per session"
    one-shot arming, which doesn't fit a long-lived API worker that should
    re-check every time the hourly Sleeper cache goes stale again.
    """

    # Never fire during tests: this would otherwise start a real background
    # thread making live requests.get calls (rankings.build_players_table
    # refreshing from Sleeper), colliding with every other test's
    # patch("requests.get", ...) mock sequence — same PYTEST_CURRENT_TEST /
    # DYNASTYGM_TEST_MODE gate modules.launch_analytics already uses for
    # this exact class of problem.
    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("DYNASTYGM_TEST_MODE"):
        return
    try:
        if not startup_cold_path.sleeper_players_cache_stale():
            return
        session_state: dict[str, Any] = {startup_cold_path.PLAYERS_REFRESH_PENDING_KEY: True}
        players_refresh_flight.schedule_deferred_players_refresh(
            db_path=PLAYERS_DB_PATH,
            build_players_table_fn=rankings.build_players_table,
            session_state=session_state,
            pending_key=startup_cold_path.PLAYERS_REFRESH_PENDING_KEY,
            background=True,
        )
    except Exception:
        pass


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
    _maybe_schedule_players_refresh()
    return normalized


def _fetch_profile_fields(config: dict, user_id: str, access_token: str) -> dict[str, str]:
    """Read select `profiles` columns using the caller's own token (RLS-scoped).

    Entitlement always fails closed to "free" on any error (network, HTTP,
    parse, RLS denial) — correct for revenue protection. But that default is
    indistinguishable from a genuine free user unless callers also check
    `status`: a transient Supabase error would otherwise make a paying user
    look and behave exactly like a free one, with no signal anything is
    wrong (mirrors the web app's `profile_status="error"` handling in
    modules/account_store.py).
    """

    defaults = {"entitlement": "free", "sleeper_username": "", "status": "error"}
    url = auth_supabase.rest_api_url(
        config,
        "profiles",
        f"select=entitlement,sleeper_username&user_id=eq.{user_id}",
    )
    try:
        response = requests.get(
            url,
            headers=auth_supabase.auth_headers(config, access_token),
            timeout=15,
        )
    except Exception:
        return defaults
    if response.status_code >= 400:
        return defaults
    try:
        rows = response.json()
    except Exception:
        return defaults
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        row = rows[0]
        entitlement = str(row.get("entitlement") or "free").strip().lower()
        return {
            "entitlement": entitlement if entitlement in {"free", "premium"} else "free",
            "sleeper_username": str(row.get("sleeper_username") or "").strip(),
            "status": "ok",
        }
    # No row found (e.g. profile bootstrap hasn't run yet) is a real, known
    # state — not an error — so a brand new user isn't shown a false alarm.
    return {"entitlement": "free", "sleeper_username": "", "status": "ok"}


@app.get("/v1/me")
def get_me(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    profile = {"entitlement": "free", "sleeper_username": "", "status": "ok"}
    if user_id:
        profile = _fetch_profile_fields(config, user_id, str(user.get("_access_token") or ""))
    return {
        "ok": True,
        "user": {
            "id": user_id,
            "email": user.get("email") or "",
            "entitlement": profile["entitlement"],
            "sleeper_username": profile["sleeper_username"],
            # "ok" | "error" — "error" means entitlement above is a fail-closed
            # default, not necessarily this user's real plan. See
            # _fetch_profile_fields.
            "profile_status": profile["status"],
            # How many leagues this plan may keep saved (modules.saved_leagues).
            # Sent so the client can show the Premium wall *before* someone
            # types a username and gets refused, without hardcoding the
            # number in two places.
            "league_cap": saved_leagues.max_leagues_for_entitlement(profile["entitlement"]),
        },
    }


# Every Supabase table that stores a row keyed to this user's own auth id,
# mirrored from docs/supabase_delete_account.sql's cascade list — kept in
# sync manually since deletion is a DB-level FK cascade with no single
# code list of its own. Add a table here whenever a new one gets added to
# that cascade.
_EXPORTABLE_USER_TABLES = (
    "profiles",
    "user_settings",
    "saved_leagues",
    "gm_targets",
    "mobile_alert_reads",
    "trade_outcomes",
    "push_tokens",
)


@app.get("/v1/me/export")
def export_my_data(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """GDPR/CCPA data-access request, self-service: every row this account
    owns across every Supabase table, as one JSON document. Uses the
    caller's own access token for every query (account_store.fetch_rows),
    the same RLS-scoped pattern _fetch_profile_fields already relies on —
    a user can only ever read rows RLS already lets them read, so this
    endpoint can't be tricked into returning another account's data.
    """

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    tables: dict[str, Any] = {}
    for table in _EXPORTABLE_USER_TABLES:
        rows, error = account_store.fetch_rows(config, access_token, table, user_id=user_id)
        tables[table] = rows if not error else {"error": error}
    return {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "user": {"id": user_id, "email": user.get("email") or ""},
        "tables": tables,
    }


@app.get("/v1/sleeper/leagues")
def lookup_sleeper_leagues(
    username: str = "",
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """The Sleeper leagues behind a username, for the add-league picker.

    Read-only Sleeper lookup (modules.sleeper_leagues, the same function
    web's onboarding import uses) — saves nothing. Falls back to the
    caller's linked `profiles.sleeper_username` when none is supplied so
    the app can pre-populate the picker.
    """

    clean = str(username or "").strip()
    if not clean:
        config = auth_supabase.get_supabase_config()
        user_id = str(user.get("id") or "")
        if user_id:
            profile = _fetch_profile_fields(config, user_id, str(user.get("_access_token") or ""))
            clean = profile.get("sleeper_username") or ""
    if not clean:
        return {"ok": False, "status": "empty_username", "leagues": [], "username": "", "message": sleeper_leagues.league_lookup_customer_message("empty_username")}

    result = sleeper_leagues.lookup_user_leagues(clean)
    return {
        "ok": result.status == "ok",
        "status": result.status,
        "username": clean,
        "leagues": [
            {
                "league_id": str(league.get("league_id") or ""),
                "name": str(league.get("name") or ""),
                "season": str(league.get("season") or ""),
                "total_rosters": int(league.get("total_rosters") or 0),
            }
            for league in result.leagues
            if str(league.get("league_id") or "")
        ],
        "message": sleeper_leagues.league_lookup_customer_message(result.status),
    }


class SaveLeagueRequest(BaseModel):
    league_id: str
    sleeper_username: str = ""
    league_name: str = ""
    make_default: bool = False


@app.post("/v1/leagues/save")
def save_league(
    payload: SaveLeagueRequest,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Save a Sleeper league to the caller's account (cap-enforced).

    Same `saved_leagues` rows, same cap, and same entitlement source as the
    web app's "Save league" button — modules.saved_leagues is the single
    authority, so the limit can't be sidestepped by switching surfaces.
    Free keeps MAX_LEAGUES_FREE; Premium keeps MAX_LEAGUES_PREMIUM.

    Re-saving a league already on the account is an update, never a refusal
    (it refreshes name/roster/default), matching the web persist path.
    """

    league_id = saved_leagues.normalize_league_id(payload.league_id)
    if not league_id:
        raise HTTPException(status_code=422, detail="league_id is required.")

    # Verify against Sleeper before writing: a typo'd or private league id
    # would otherwise become a permanent dead row on the user's Home screen.
    league = sleeper.get_league(league_id)
    if not league:
        return {"ok": False, "reason": "league_not_found", "cap": 0}

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    if not user_id:
        return {"ok": False, "reason": "not_available", "cap": 0}

    profile = _fetch_profile_fields(config, user_id, access_token)
    cap = saved_leagues.max_leagues_for_entitlement(profile.get("entitlement"))

    existing, error = account_store.fetch_rows(
        config,
        access_token,
        saved_leagues.LEAGUES_TABLE,
        user_id=user_id,
        extra_query="select=league_id",
    )
    if error:
        # Fail closed, same as add_gm_target: the write below targets the
        # same Supabase that just refused to be read, so an optimistic
        # "allow" would almost certainly fail anyway — and silently
        # un-capped.
        return {"ok": False, "reason": "not_available", "cap": cap}
    if saved_leagues.is_at_cap(existing, league_id=league_id, cap=cap):
        return {"ok": False, "reason": "at_cap", "cap": cap}

    username = str(payload.sleeper_username or "").strip() or profile.get("sleeper_username", "")
    roster_id = sleeper.get_user_roster_id(league_id, username) if username else None
    league_name = str(payload.league_name or "").strip() or str(league.get("name") or "")
    # First league saved becomes the default so Home has something to open.
    is_default = bool(payload.make_default) or not saved_leagues.saved_league_ids(existing)

    ok, _write_error = account_store.upsert_saved_league(
        config,
        access_token,
        account_store.build_saved_league_payload(
            user_id=user_id,
            sleeper_username=username,
            league_id=league_id,
            league_name=league_name,
            roster_id=roster_id,
            team_id=roster_id,
            is_default=is_default,
        ),
    )
    if not ok:
        return {"ok": False, "reason": "not_available", "cap": cap}
    return {
        "ok": True,
        "reason": "",
        "cap": cap,
        "league": {
            "league_id": league_id,
            "league_name": league_name,
            "is_default": is_default,
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


@app.get("/v1/leagues/{league_id}/team-profiles")
def get_league_team_profiles(league_id: str, _user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """Team identity per roster (name/owner/avatar), keyed by roster_id.

    Reuses modules.sleeper.get_league_roster_profiles verbatim — the same
    team_name/avatar fallback chain (roster metadata -> user metadata ->
    display name -> username) the web app's league workspace uses.
    """

    return {"ok": True, "profiles": sleeper.get_league_roster_profiles(league_id)}


@app.get("/v1/leagues/{league_id}/team-rankings")
def get_league_team_rankings(
    league_id: str,
    lens: str = "Dynasty",
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Power Rank / Franchise Rank / Draft Capital Rank / standings for every
    roster in the league.

    Shares the web app's real "Rankings" page computation
    (modules.league_rankings, ported from app.py's production chain — see
    that module's docstring) plus modules.league_standings for win-loss/
    points-for-against, which is already modules-based and independent of
    the rank computation (the two pieces are never merged into one frame on
    web either — see league_rankings.py). No caller-roster resolution
    needed: this is public league-wide data, same auth pattern as
    /team-profiles and /rosters.
    """

    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")

    # Player-data availability gate, kept for the specific "no_player_data"
    # reason mobile screens key off of — the same check
    # build_league_rankings_frame_cached repeats internally (cheaply, since
    # rankings.load_players is itself cached) before building the frame it
    # returns below.
    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    players_df = player_eligibility.filter_current_fantasy_players(
        players_df, surface="mobile_api_team_rankings", league=league
    )
    if players_df.empty:
        return {"ok": True, "teams": [], "reason": "no_player_data"}

    rankings_frame = league_rankings.build_league_rankings_frame_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
    )
    if rankings_frame.empty:
        return {"ok": True, "teams": [], "reason": "no_rankings_data"}

    # Archetype/strategy classification degrades gracefully without a full
    # league-intelligence frame (health/balance inputs default to neutral —
    # see modules.team_eval._rank_strength's fallback), so it's safe to run
    # directly on the cheap rankings_frame rather than needing the heavier
    # per-roster injury-summary pass web's cached_league_intelligence_frame
    # does. Manager tendencies (trading style, activity level) are NOT here —
    # those need a full-season Sleeper transaction scan that doesn't exist
    # in modules/ yet; a real, separate follow-up.
    rankings_frame = refine_team_directions(rankings_frame)

    rosters = sleeper.get_rosters(league_id)
    roster_profiles = sleeper.get_league_roster_profiles(league_id)
    standings_bundle = league_standings.build_league_standings_bundle(
        rosters=rosters,
        roster_profiles=roster_profiles,
        league=league,
        team_frame=rankings_frame,
    )
    standings_by_roster: dict[str, dict[str, Any]] = {}
    standings_frame = standings_bundle.get("frame")
    if isinstance(standings_frame, pd.DataFrame) and not standings_frame.empty:
        for _, row in standings_frame.iterrows():
            standings_by_roster[str(row.get("roster_id"))] = row.to_dict()

    # Real per-team buy/sell tendency read off actual Sleeper trade history
    # (modules.team_trade_history — the data half of "Decision Memory").
    # Best-effort: a scan failure (e.g. an offseason league with no
    # transactions endpoint data yet) just leaves every team "Neutral"
    # rather than failing team-rankings entirely.
    try:
        trade_tendencies = team_trade_history.league_trade_tendencies_cached(league_id, PLAYERS_DB_PATH)
    except Exception:
        trade_tendencies = {}

    teams: list[dict[str, Any]] = []
    for _, row in rankings_frame.iterrows():
        roster_id = str(row.get("roster_id"))
        standing = standings_by_roster.get(roster_id, {})
        try:
            tendency = trade_tendencies.get(int(roster_id), {})
        except (TypeError, ValueError):
            tendency = {}
        teams.append(
            {
                "roster_id": roster_id,
                "trade_tendency": tendency.get("tendency", team_trade_history.NEUTRAL),
                "trade_tendency_sell_count": int(tendency.get("sell_count") or 0),
                "trade_tendency_buy_count": int(tendency.get("buy_count") or 0),
                "team_name": _clean_json_value(row.get("team_name")),
                "owner_name": _clean_json_value(standing.get("owner_name") or row.get("owner_name")),
                "owner_username": _clean_json_value(standing.get("owner_username")),
                "avatar_url": _clean_json_value(standing.get("avatar_url") or row.get("avatar_url")),
                "wins": _clean_json_value(standing.get("wins")),
                "losses": _clean_json_value(standing.get("losses")),
                "ties": _clean_json_value(standing.get("ties")),
                "record_label": _clean_json_value(standing.get("record_label")),
                "points_for": _clean_json_value(standing.get("points_for")),
                "points_against": _clean_json_value(standing.get("points_against")),
                "power_rank": _clean_json_value(row.get("power_rank")),
                "franchise_rank": _clean_json_value(row.get("franchise_rank")),
                "draft_capital_rank": _clean_json_value(row.get("draft_capital_rank")),
                "starter_rank": _clean_json_value(row.get("starter_rank")),
                "bench_rank": _clean_json_value(row.get("bench_rank")),
                "age_rank": _clean_json_value(row.get("age_rank")),
                "average_age": _clean_json_value(row.get("avg_age")),
                "strategy": _clean_json_value(row.get("strategy")),
                "strategy_label": _clean_json_value(row.get("strategy_label")),
                "archetype": _clean_json_value(row.get("archetype")),
                "archetype_label": _clean_json_value(row.get("archetype_label")),
                "archetype_explanation": _clean_json_value(row.get("archetype_explanation")),
                "archetype_strengths": _as_string_list(row.get("archetype_strengths")),
                "archetype_risks": _as_string_list(row.get("archetype_risks")),
                "archetype_recommendations": _as_string_list(row.get("archetype_recommendations")),
            }
        )

    return {"ok": True, "teams": teams, "reason": ""}


@app.get("/v1/leagues/{league_id}/draft-center")
def get_league_draft_center(
    league_id: str,
    lens: str = "Dynasty",
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Draft Center Overview: your own draft posture (if your roster can be
    resolved) plus league-wide draft decision signals and partner discovery.

    Shares the web app's real computation chain: modules.league_rankings
    (build_league_summary_and_draft_capital, build_draft_workspace_frame —
    the latter ported verbatim from app.py, confirmed pure pandas with no
    Streamlit dependency) plus modules.draft_center_ui's already-pure
    build_draft_decision_cards / build_draft_partner_cards /
    draft_posture_profile.

    Manager-tendency fields (trading_style, roster_philosophy, asset_behavior,
    activity_level) are not threaded into df_intel here — those need a real
    full-season Sleeper transaction scan that doesn't exist in modules/ yet
    (same deferred scope noted in get_league_team_rankings). Everything
    build_draft_workspace_frame would otherwise read from those columns
    degrades to a neutral default when they're absent, same as every other
    graceful-degradation case in this file — strategy_display is threaded
    through explicitly (aliased from the archetype/strategy classification
    get_league_team_rankings already computes) since that one is cheap and
    already available.

    Decision/partner cards are public league-wide data and are always
    returned; posture is personal and can be null (see posture_reason) if
    the caller's own roster can't be resolved — the two don't need to gate
    each other.

    Only the "Overview" pane. Current Draft/History (live draft board
    tracking) and Scouting are real, separate, much bigger surfaces not
    covered here.
    """

    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")
    settings = league_value_settings.detect_league_value_settings_from_payload(league)

    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    players_df = player_eligibility.filter_current_fantasy_players(
        players_df, surface="mobile_api_draft_center", league=league
    )
    if players_df.empty:
        return {
            "ok": True,
            "reason": "no_player_data",
            "posture": None,
            "posture_reason": "",
            "decision_cards": [],
            "partner_cards": [],
        }

    valued = league_value_settings.apply_valuation_lens(players_df, lens, settings)
    score_field = league_value_settings.valuation_score_field(lens)

    df_summary, draft_capital_summary = league_rankings.build_league_summary_and_draft_capital(
        valued, league_id, score_field=score_field, league_settings=settings
    )
    if df_summary.empty or draft_capital_summary.empty:
        return {
            "ok": True,
            "reason": "no_rankings_data",
            "posture": None,
            "posture_reason": "",
            "decision_cards": [],
            "partner_cards": [],
        }

    intel_frame = league_rankings.add_league_detail_ranks(
        league_rankings.build_league_display_frame(df_summary, draft_capital_summary, include_picks=False)
    )
    intel_frame = refine_team_directions(intel_frame)
    intel_frame["strategy_display"] = intel_frame.get("strategy_label", "")

    draft_workspace = league_rankings.build_draft_workspace_frame(draft_capital_summary, intel_frame)
    if draft_workspace.empty:
        return {
            "ok": True,
            "reason": "no_rankings_data",
            "posture": None,
            "posture_reason": "",
            "decision_cards": [],
            "partner_cards": [],
        }

    decision_cards = draft_center_ui.build_draft_decision_cards(draft_workspace)
    partner_cards = draft_center_ui.build_draft_partner_cards(draft_workspace)

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    profile = _fetch_profile_fields(config, user_id, str(user.get("_access_token") or "")) if user_id else {}
    my_roster, roster_reason = _resolve_my_roster(user, league_id, profile=profile)

    posture: dict[str, Any] | None = None
    posture_reason = roster_reason
    if my_roster is not None:
        my_roster_id = str(my_roster.get("roster_id") or "")
        match = draft_workspace[draft_workspace["roster_id"].astype(str) == my_roster_id]
        if match.empty:
            posture_reason = "no_draft_capital_row"
        else:
            team_row = match.iloc[0]
            profile_posture = draft_center_ui.draft_posture_profile(team_row, len(draft_workspace))
            posture_reason = ""
            posture = {
                "label": profile_posture["label"],
                "note": profile_posture["note"],
                "tone": profile_posture["tone"],
                "draft_capital_rank": _clean_json_value(team_row.get("draft_capital_rank")),
                "draft_capital": _clean_json_value(team_row.get("draft_capital")),
                "future_draft_capital_rank": _clean_json_value(team_row.get("future_draft_capital_rank")),
                "future_draft_capital": _clean_json_value(team_row.get("future_draft_capital")),
                "strategy_display": _clean_json_value(team_row.get("strategy_display")),
                "power_rank": _clean_json_value(team_row.get("power_rank")),
                "franchise_rank": _clean_json_value(team_row.get("franchise_rank")),
                "first_rounders": _clean_json_value(team_row.get("first_rounders")),
                "pick_count": _clean_json_value(team_row.get("pick_count")),
            }

    return {
        "ok": True,
        "reason": "",
        "posture": posture,
        "posture_reason": posture_reason,
        "decision_cards": decision_cards,
        "partner_cards": partner_cards,
    }


@app.get("/v1/leagues/{league_id}/draft-picks")
def get_league_draft_picks(
    league_id: str,
    lens: str = "Dynasty",
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Every draft pick asset in the league, for the mobile Trade Analyzer's
    Players/Picks roster browser and the Draft Center's Pick Detail screen.

    Each pick gets a stable pick_id — f"{season}:{round}:{original_roster_id}"
    — the client sends back in POST /trade-analyzer's send_pick_ids/
    receive_pick_ids. (season, round, original_roster_id) is already a
    unique key for a pick asset regardless of its current owner (only one
    roster can hold a given original team's given-round pick in a given
    year at a time), so no separate id scheme is needed.

    Shares modules.trade_ideas.list_draft_pick_assets verbatim — the same
    per-pick valuation (round, expected range, class/prospect strength,
    team context) the web app's Draft Center and Trade Hub already use in
    modules/, via modules.league_rankings.build_league_summary_and_draft_capital
    for the df_summary it needs as an input.
    """

    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")
    settings = league_value_settings.detect_league_value_settings_from_payload(league)

    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    players_df = player_eligibility.filter_current_fantasy_players(
        players_df, surface="mobile_api_draft_picks", league=league
    )
    if players_df.empty:
        return {"ok": True, "picks": [], "reason": "no_player_data"}

    valued = league_value_settings.apply_valuation_lens(players_df, lens, settings)
    score_field = league_value_settings.valuation_score_field(lens)

    df_summary, _ = league_rankings.build_league_summary_and_draft_capital(
        valued, league_id, score_field=score_field, league_settings=settings
    )
    if df_summary.empty:
        return {"ok": True, "picks": [], "reason": "no_rankings_data"}

    picks = trade_ideas.list_draft_pick_assets(league_id, df_summary, league_settings=settings)
    projected = [
        {
            "pick_id": f"{pick.get('season')}:{pick.get('round')}:{pick.get('original_roster_id')}",
            "label": _clean_json_value(pick.get("label")),
            "score": _clean_json_value(pick.get("score")),
            "season": _clean_json_value(pick.get("season")),
            "round": _clean_json_value(pick.get("round")),
            "original_roster_id": str(pick.get("original_roster_id")),
            "owner_roster_id": str(pick.get("owner_roster_id")),
            "original_team_name": _clean_json_value(pick.get("original_team_name")),
            "owner_team_name": _clean_json_value(pick.get("owner_team_name")),
            "pick_tier": _clean_json_value(pick.get("pick_tier")),
            "projected_pick_range": _clean_json_value(pick.get("projected_pick_range")),
            # Full valuation breakdown, forwarded verbatim from
            # trade_ideas._pick_value_components — the mobile Pick Detail
            # ("PQV for a draft pick") screen shows the same multipliers and
            # projected-range distribution the model already computed, so
            # the client never re-derives or approximates any of it.
            "tier_bucket": _clean_json_value(pick.get("tier_bucket")),
            "base_score": _clean_json_value(pick.get("base_score")),
            "years_out": _clean_json_value(pick.get("years_out")),
            "future_discount": _clean_json_value(pick.get("future_discount")),
            "team_modifier": _clean_json_value(pick.get("team_modifier")),
            "format_multiplier": _clean_json_value(pick.get("format_multiplier")),
            "class_strength_multiplier": _clean_json_value(pick.get("class_strength_multiplier")),
            "prospect_strength_multiplier": _clean_json_value(pick.get("prospect_strength_multiplier")),
            "slot_percentile": _clean_json_value(pick.get("slot_percentile")),
            "projected_slot_percentile": _clean_json_value(pick.get("projected_slot_percentile")),
            "early_probability": _clean_json_value(pick.get("early_probability")),
            "mid_probability": _clean_json_value(pick.get("mid_probability")),
            "late_probability": _clean_json_value(pick.get("late_probability")),
            "projection_confidence": _clean_json_value(pick.get("projection_confidence")),
            "projection_source": _clean_json_value(pick.get("projection_source")),
            "is_current_year_pick": bool(pick.get("is_current_year_pick")),
        }
        for pick in picks
    ]
    return {"ok": True, "picks": projected, "reason": ""}


def _resolve_my_roster(
    user: dict[str, Any],
    league_id: str,
    *,
    profile: dict[str, str] | None = None,
) -> tuple[dict[str, Any] | None, str]:
    """Identify which of this league's rosters belongs to the signed-in user.

    Resolves via the Sleeper username linked on their profile (same
    profiles.sleeper_username the web app sets) -> Sleeper user_id -> the
    roster whose owner_id matches. All non-matches are expected, everyday
    states (not errors) — callers return 200 with the `reason` rather than
    an HTTP error status for any of them.

    `profile` lets a caller that already fetched the profile (e.g. for
    entitlement) pass it in instead of this function fetching it again —
    same Supabase round trip, not two.
    """

    if profile is None:
        config = auth_supabase.get_supabase_config()
        user_id = str(user.get("id") or "")
        profile = _fetch_profile_fields(config, user_id, str(user.get("_access_token") or "")) if user_id else {}
    sleeper_username = str(profile.get("sleeper_username") or "")
    if not sleeper_username:
        return None, "no_sleeper_username_linked"

    sleeper_user_id = sleeper_leagues.resolve_sleeper_user_id(sleeper_username)
    if not sleeper_user_id:
        return None, "sleeper_user_not_found"

    for roster in sleeper.get_rosters(league_id):
        if str(roster.get("owner_id") or "") == sleeper_user_id:
            return roster, ""

    return None, "not_a_member_of_league"


@app.get("/v1/leagues/{league_id}/my-roster")
def get_my_roster(league_id: str, user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """Identify which of this league's rosters belongs to the signed-in user.

    Always returns 200 with a `reason` the client can act on instead of
    parsing HTTP status semantics — see `_resolve_my_roster`.
    """

    roster, reason = _resolve_my_roster(user, league_id)
    return {"ok": True, "roster": roster, "reason": reason}


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


PLAYERS_DB_PATH = "data/players.db"
MAX_RANKINGS_LIMIT = 300
MAX_NEWS_LIMIT = 50

# Only actionable signal — a generic/off-topic headline (the RSS cache is a
# broad NFL feed, not fantasy-specific) classifies as EVENT_HEADLINE and is
# dropped, same taxonomy the web app's roster news feed uses.
_ACTIONABLE_NEWS_EVENTS = {
    news_signal.EVENT_INJURY,
    news_signal.EVENT_ROLE,
    news_signal.EVENT_TRANSACTION,
    news_signal.EVENT_OFF_FIELD,
}


def _clean_json_value(value: Any) -> Any:
    """Convert a pandas/numpy scalar to a plain JSON-safe value (NaN -> None)."""

    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (int, float, str, bool)):
        return value
    if hasattr(value, "item"):
        return value.item()
    return value


def _as_string_list(value: Any) -> list[str]:
    """A DataFrame cell holding a list-of-strings column, defensively —
    modules.team_eval._assign_team_archetype always builds these as real
    lists, but a pandas cell can surface as a bare float NaN if a row ever
    lacked one, and `nan or []` doesn't fall through to the default (NaN is
    truthy), so this checks the type explicitly instead."""

    return [str(item) for item in value] if isinstance(value, (list, tuple)) else []


def _project_usage_trend(row: pd.Series) -> dict[str, Any] | None:
    """The weekly-recency read already stored on every player row, in the
    exact shape the web app renders it from.

    rankings.recency_trend_display owns both the semantics and the display
    gate (>= 4 usable games and a >= 5% move, see its docstring) so mobile
    and web never disagree about when usage is "trending"; this is a pure
    projection, not a second opinion. ``None`` when the read is too thin to
    state, and the client simply renders nothing.
    """

    return rankings.recency_trend_display(row)


def _project_injury_impact_player(item: Any) -> dict[str, Any]:
    """One entry of modules.rankings.roster_injury_context's
    `top_injury_impact_players`, trimmed to what a mobile card renders."""

    if not isinstance(item, dict):
        return {}
    return {
        "player_id": str(item.get("player_id") or ""),
        "name": str(item.get("name") or "").strip(),
        "position": str(item.get("position") or "").strip().upper(),
        "team": str(item.get("team") or "").strip().upper(),
        # injury_status is Sleeper's raw status string ("Questionable"),
        # injury_level the engine's severity word ("major"/"moderate") —
        # same split PresentationAsset already carries on the trade side.
        "injury_status": str(item.get("injury_status") or "").strip(),
        "injury_level": str(item.get("injury_level") or "").strip(),
        "roster_relevance": str(item.get("roster_relevance") or "").strip(),
        "freshness_label": str(item.get("freshness_label") or "").strip(),
        "player_value_score": _clean_json_value(item.get("player_value_score")),
        "impact_contribution": _clean_json_value(item.get("impact_contribution")),
    }


def _project_team_injury_narrative(context: Any) -> dict[str, Any]:
    """The "why" behind a one-word health flag.

    modules.rankings.roster_injury_context already computes all of this for
    every roster; web renders it as the `Key injuries: ...` caption
    (modules.league_workspace_ui) and injury_ui.team_injury_display_note's
    impact summary. Mobile was forwarding only the flag itself, so this is
    a pure "stop dropping already-computed fields" projection — no new
    computation, no mobile-only rewording of the engine's own text.
    """

    context = injury_ui.resolve_team_injury_context(context)
    if not isinstance(context, dict):
        return {"key_injuries_summary": "", "top_injury_impact_summary": "", "top_injury_impact_players": []}

    # Web builds key_injuries_summary from the actionable subset first
    # (app.py's league-intelligence frame), falling back to the engine's
    # key_injuries list (app.py's dashboard briefing path) — same order here.
    actionable_names = [
        str(item.get("name") or "").strip()
        for item in (context.get("actionable_injury_players") or [])
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    key_injuries_summary = ", ".join(actionable_names) or ", ".join(
        str(entry).strip() for entry in (context.get("key_injuries") or []) if str(entry).strip()
    )

    players = [
        projected
        for projected in (
            _project_injury_impact_player(item)
            for item in (context.get("top_injury_impact_players") or [])
        )
        if projected.get("name")
    ]
    return {
        "key_injuries_summary": key_injuries_summary,
        "top_injury_impact_summary": str(context.get("top_injury_impact_summary") or "").strip(),
        "top_injury_impact_players": players,
    }


def _project_ranking_row(row: pd.Series, score_field: str) -> dict[str, Any]:
    overall_rank = row.get("canonical_overall_rank")
    if pd.isna(overall_rank):
        overall_rank = row.get("overall_rank")
    position_rank = row.get("canonical_position_rank")
    if pd.isna(position_rank):
        position_rank = row.get("position_rank")
    return {
        "player_id": _clean_json_value(row.get("player_id")),
        "name": _clean_json_value(row.get("name")),
        "position": _clean_json_value(row.get("position")),
        "team": _clean_json_value(row.get("team")),
        "age": _clean_json_value(row.get("age")),
        "status": _clean_json_value(row.get("status")),
        "injury_status": _clean_json_value(row.get("injury_status")),
        "tier": _clean_json_value(row.get("player_tier")),
        "score": _clean_json_value(row.get(score_field)),
        "overall_rank": _clean_json_value(overall_rank),
        "position_rank": _clean_json_value(position_rank),
        "rank_unavailable_reason": _clean_json_value(row.get("rank_unavailable_reason")),
        "opportunity_label": _clean_json_value(row.get("opportunity_label")),
        "usage_trend": _project_usage_trend(row),
    }


@app.get("/v1/leagues/{league_id}/rankings")
def get_league_rankings(
    league_id: str,
    lens: str = "Dynasty",
    limit: int = 100,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """League-adjusted player rankings — shares the exact same valuation
    engine as the web app (modules.league_value_settings, extracted from
    app.py so both apps use one copy; see that module's docstring). Does
    not invent a new ranking formula or retune anything for mobile.
    """

    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )
    if not 1 <= limit <= MAX_RANKINGS_LIMIT:
        raise HTTPException(status_code=422, detail=f"limit must be between 1 and {MAX_RANKINGS_LIMIT}.")

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")

    settings = league_value_settings.detect_league_value_settings_from_payload(league)

    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    players_df = player_eligibility.filter_current_fantasy_players(
        players_df, surface="mobile_api_rankings", league=league
    )
    if players_df.empty:
        return {"ok": True, "players": []}

    valued = league_value_settings.apply_valuation_lens(players_df, lens, settings)

    score_field = league_value_settings.valuation_score_field(lens)
    scoring_context = canonical_player_ranking.resolve_scoring_rank_context(settings)
    ranked = canonical_player_ranking.attach_canonical_ranks(
        valued,
        scoring_format=scoring_context.scoring_format,
        score_field=score_field,
        context=scoring_context,
    )

    ranked = ranked.sort_values(score_field, ascending=False).head(limit)
    players = [_project_ranking_row(row, score_field) for _, row in ranked.iterrows()]
    return {"ok": True, "players": players}


@app.get("/v1/leagues/{league_id}/players/{player_id}/rank")
def get_player_rank_in_league(
    league_id: str,
    player_id: str,
    lens: str = "Dynasty",
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """One player's league-adjusted rank, looked up directly instead of
    truncated out of a top-N /rankings list. Player Detail calls this itself
    so Overall/Position Rank are always populated regardless of which screen
    navigated here — several callers (Waivers, MyTeam, Trade Hub) only ever
    have a lean player shape with no rank fields to pass along.
    """

    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")

    settings = league_value_settings.detect_league_value_settings_from_payload(league)

    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    players_df = player_eligibility.filter_current_fantasy_players(
        players_df, surface="mobile_api_rankings", league=league
    )
    if players_df.empty:
        return {"ok": True, "player": None}

    valued = league_value_settings.apply_valuation_lens(players_df, lens, settings)
    score_field = league_value_settings.valuation_score_field(lens)
    scoring_context = canonical_player_ranking.resolve_scoring_rank_context(settings)
    ranked = canonical_player_ranking.attach_canonical_ranks(
        valued,
        scoring_format=scoring_context.scoring_format,
        score_field=score_field,
        context=scoring_context,
    )

    matches = ranked[ranked["player_id"] == player_id]
    if matches.empty:
        return {"ok": True, "player": None}
    return {"ok": True, "player": _project_ranking_row(matches.iloc[0], score_field)}


_NEWS_SOURCE_DISPLAY_NAMES = {
    "rotowire.com": "RotoWire",
    "espn.com": "ESPN",
    "cbssports.com": "CBS Sports",
    "sports.yahoo.com": "Yahoo Sports",
    "nbcsports.com": "Pro Football Talk",
}


def _friendly_news_source(raw_source: str) -> str:
    """The stored `source` is the raw feed URL (modules.news_signal's own
    source-quality classifier matches against that exact string) — this is
    a display-only transform, never fed back into classification.
    """

    lowered = str(raw_source or "").lower()
    for marker, display_name in _NEWS_SOURCE_DISPLAY_NAMES.items():
        if marker in lowered:
            return display_name
    match = re.search(r"https?://(?:www\.)?([^/]+)", str(raw_source or ""))
    return match.group(1) if match else str(raw_source or "")


def _project_news_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": _clean_json_value(item.get("title")),
        "link": _clean_json_value(item.get("link")),
        "source": _friendly_news_source(str(item.get("source") or "")),
        "summary": _clean_json_value(my_news.build_quick_news_summary(item)),
        "published_ts": _clean_json_value(item.get("published_ts")),
        "event_type": _clean_json_value(item.get("signal_primary_event")),
        "speculative": bool(item.get("signal_speculative")),
    }


@app.get("/v1/news")
def get_news(
    limit: int = 30,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Curated general NFL fantasy news (injury/role/transaction/off-field
    signal only — a generic headline is dropped). Not roster-scoped: this is
    a league-wide feed for anyone, not "your team's" news.

    Shares the same disk-cached pool and classification the web app uses
    (modules.news, modules.news_signal) and never triggers a live RSS fetch
    on this request path — schedule_news_cache_refresh only starts a
    background refresh when the on-disk cache is already stale.
    """

    if not 1 <= limit <= MAX_NEWS_LIMIT:
        raise HTTPException(status_code=422, detail=f"limit must be between 1 and {MAX_NEWS_LIMIT}.")

    news_cache.schedule_news_cache_refresh()
    enriched = news_cache.enriched_news_pool()

    actionable = [item for item in enriched if item.get("signal_primary_event") in _ACTIONABLE_NEWS_EVENTS]
    actionable.sort(key=my_news.news_timestamp, reverse=True)

    seen_links: set[str] = set()
    items: list[dict[str, Any]] = []
    for item in actionable:
        link = str(item.get("link") or "").strip().lower()
        if link and link in seen_links:
            continue
        if link:
            seen_links.add(link)
        items.append(_project_news_item(item))
        if len(items) >= limit:
            break

    return {"ok": True, "items": items}


MAX_PLAYER_NEWS_LIMIT = 10


@app.get("/v1/players/{player_id}/news")
def get_player_news(
    player_id: str,
    limit: int = 5,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Recent news items mentioning one player — powers Player Detail's
    "impacted by news" badge.

    The generic news pool /v1/news reads from is league-independent, so
    unlike the roster-aware Alerts/Dashboard path (news_intelligence's
    contextual_news_alert_from_article), items here never arrive with
    matched_player_id already resolved — there's no roster context to
    resolve names against. Since the caller already names a specific
    player, this matches that player's own name as a phrase against each
    article directly instead, which sidesteps needing that index.
    """

    if not 1 <= limit <= MAX_PLAYER_NEWS_LIMIT:
        raise HTTPException(status_code=422, detail=f"limit must be between 1 and {MAX_PLAYER_NEWS_LIMIT}.")

    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    row_matches = players_df[players_df["player_id"] == player_id] if not players_df.empty else players_df
    player_name = str(row_matches.iloc[0].get("name") or "").strip() if not row_matches.empty else ""
    if not player_name:
        return {"ok": True, "items": []}

    news_cache.schedule_news_cache_refresh()
    enriched = news_cache.enriched_news_pool()

    matches = [
        item
        for item in enriched
        if item.get("signal_primary_event") in _ACTIONABLE_NEWS_EVENTS
        and news_signal.contains_phrase(news_signal.article_text(item), player_name)
    ]
    matches.sort(key=my_news.news_timestamp, reverse=True)

    return {"ok": True, "items": [_project_news_item(item) for item in matches[:limit]]}


class TradeAnalyzerRequest(BaseModel):
    send_player_ids: list[str] = Field(default_factory=list)
    receive_player_ids: list[str] = Field(default_factory=list)
    # pick_id values from GET /v1/leagues/{id}/draft-picks
    # (f"{season}:{round}:{original_roster_id}").
    send_pick_ids: list[str] = Field(default_factory=list)
    receive_pick_ids: list[str] = Field(default_factory=list)
    # Any unrecognized value falls back to "retool" — see
    # modules.team_eval.normalize_team_strategy — so this is never rejected.
    strategy: str = "retool"
    lens: str = "Dynasty"
    # Optional: the proposing partner's roster_id. When given, verdict.counter_action
    # can suggest a specific verified partner asset to ask for instead of just
    # generic guidance text — see modules.trade_offer_analyzer.build_counter_guidance.
    partner_roster_id: str = ""


@app.post("/v1/leagues/{league_id}/trade-analyzer")
def post_trade_analyzer(
    league_id: str,
    body: TradeAnalyzerRequest,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Real accept/decline/counter verdict for a proposed trade package.

    Shares the exact same fit engine as the web app's Trade Analyzer
    (modules.trade_analyzer_fit, extracted from app.py) and the same
    verdict logic (modules.trade_offer_analyzer) — this does not invent a
    new scoring model. Roster-specific, so it needs the signed-in user's
    own roster in this league (see `_resolve_my_roster`); any of that
    resolution's non-match states, or an empty/invalid package, return 200
    with a `reason` rather than an HTTP error, since they're everyday
    states a client should handle gracefully (e.g. prompt to link Sleeper).

    Draft picks (send_pick_ids/receive_pick_ids, ids from GET
    .../draft-picks) are resolved and projected exactly like players and
    appended to the same send_assets/receive_assets lists —
    modules.trade_analyzer_fit already sums/counts asset_type == "pick"
    assets throughout the fit engine, so this needed no changes there,
    only wiring the ids through.
    """

    if body.lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )
    if (
        not body.send_player_ids
        and not body.receive_player_ids
        and not body.send_pick_ids
        and not body.receive_pick_ids
    ):
        raise HTTPException(status_code=422, detail="Provide at least one asset on either side of the trade.")

    my_roster, reason = _resolve_my_roster(user, league_id)
    if my_roster is None:
        return {"ok": True, "verdict": None, "reason": reason}

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")
    settings = league_value_settings.detect_league_value_settings_from_payload(league)

    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    players_df = player_eligibility.filter_current_fantasy_players(
        players_df, surface="mobile_api_trade_analyzer", league=league
    )
    if players_df.empty:
        return {"ok": True, "verdict": None, "reason": "no_player_data"}

    valued = league_value_settings.apply_valuation_lens(players_df, body.lens, settings)
    score_field = league_value_settings.valuation_score_field(body.lens)

    my_roster_ids = {str(pid) for pid in (my_roster.get("players") or [])}
    my_team_df = valued[valued["player_id"].astype(str).isin(my_roster_ids)].copy()
    if my_team_df.empty:
        return {"ok": True, "verdict": None, "reason": "empty_roster"}

    def build_assets(player_ids: list[str]) -> list[dict[str, Any]]:
        wanted = {str(pid) for pid in player_ids if pid}
        if not wanted:
            return []
        rows = valued[valued["player_id"].astype(str).isin(wanted)]
        return [player_asset_from_mapping(row, score_field=score_field) for _, row in rows.iterrows()]

    send_pick_assets: list[dict[str, Any]] = []
    receive_pick_assets: list[dict[str, Any]] = []
    if body.send_pick_ids or body.receive_pick_ids:
        pick_summary, _ = league_rankings.build_league_summary_and_draft_capital(
            valued, league_id, score_field=score_field, league_settings=settings
        )
        if not pick_summary.empty:
            all_picks = trade_ideas.list_draft_pick_assets(league_id, pick_summary, league_settings=settings)
            picks_by_id = {
                f"{pick.get('season')}:{pick.get('round')}:{pick.get('original_roster_id')}": pick
                for pick in all_picks
            }

            def resolve_picks(pick_ids: list[str]) -> list[dict[str, Any]]:
                return [
                    pick_asset_from_mapping(picks_by_id[pick_id])
                    for pick_id in pick_ids
                    if pick_id in picks_by_id
                ]

            send_pick_assets = resolve_picks(body.send_pick_ids)
            receive_pick_assets = resolve_picks(body.receive_pick_ids)

    send_assets = build_assets(body.send_player_ids) + send_pick_assets
    receive_assets = build_assets(body.receive_player_ids) + receive_pick_assets
    if not send_assets and not receive_assets:
        return {"ok": True, "verdict": None, "reason": "assets_not_found"}

    partner_assets: list[dict[str, Any]] = []
    if body.partner_roster_id:
        partner_player_ids = {
            str(pid)
            for roster in sleeper.get_rosters(league_id)
            if str(roster.get("roster_id")) == str(body.partner_roster_id)
            for pid in (roster.get("players") or [])
        }
        if partner_player_ids:
            partner_rows = valued[valued["player_id"].astype(str).isin(partner_player_ids)]
            partner_assets = [
                player_asset_from_mapping(
                    row,
                    score_field=score_field,
                    owner_info={"owner_roster_id": body.partner_roster_id},
                )
                for _, row in partner_rows.iterrows()
            ]

    fit = trade_analyzer_fit.evaluate_trade_analyzer_fit(
        my_team_df=my_team_df,
        all_players_df=valued,
        send_assets=send_assets,
        receive_assets=receive_assets,
        metrics=None,
        strategy=body.strategy,
        lineup_settings=settings,
        score_field=score_field,
    )
    if not fit or not fit.get("available"):
        return {"ok": True, "verdict": None, "reason": "fit_unavailable"}

    verdict = trade_offer_analyzer.decide_offer_verdict(
        fit,
        send_assets=send_assets,
        receive_assets=receive_assets,
        partner_assets=partner_assets,
    )
    return {"ok": True, "verdict": verdict.to_public_dict(), "reason": ""}


@app.get("/v1/leagues/{league_id}/recap")
def get_league_recap(
    league_id: str,
    week: int | None = None,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Weekly recap — shares the exact same builder as the web app's League
    Recaps page (modules.league_recaps.build_weekly_recap). Does not invent
    new stories, headline templates, or narrative logic. Movement (power-rank
    trend) and power_ranks are omitted, same as the web app's own call site
    when a league is first opened — build_weekly_recap simply skips the
    story categories that need them.

    Defaults to the latest completed week when `week` is omitted (original
    behavior, unchanged). Passing an explicit `week` lets the client browse
    recap history — `max_completed_week` is always returned so it can build
    a week picker without a second round trip.
    """

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")

    _, _, max_history_week = league_recaps.league_history_window(league)
    matchup_rows = league_recaps.build_matchup_history_rows(
        league_id, max_history_week, fetch_matchups=sleeper.get_matchups
    )
    completed_week = league_recaps.completed_recap_week(league, matchup_rows)
    if completed_week <= 0:
        return {"ok": True, "recap": None, "reason": "no_completed_week", "max_completed_week": 0}

    if week is None:
        week = completed_week
    elif week < 1 or week > completed_week:
        raise HTTPException(
            status_code=422, detail=f"week must be between 1 and {completed_week}"
        )

    profiles = sleeper.get_league_roster_profiles(league_id) or {}

    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    players_df = player_eligibility.filter_current_fantasy_players(
        players_df, surface="mobile_api_recap", league=league
    )
    lookup_rows: list[dict[str, Any]] = []
    if not players_df.empty:
        settings = league_value_settings.detect_league_value_settings_from_payload(league)
        valued = league_value_settings.apply_valuation_lens(players_df, "Dynasty", settings)
        cols = [c for c in ("player_id", "name", "position", "team", "value_score") if c in valued.columns]
        if cols:
            lookup_rows = valued[cols].to_dict("records")
    player_lookup = league_history.player_lookup_from_rows(lookup_rows)

    season = str(league.get("season") or "")
    raw_transactions = sleeper.get_transactions(league_id, week) or []
    transactions: list[dict[str, Any]] = []
    for raw in raw_transactions:
        normalized = league_history.normalize_transaction(
            raw,
            league_id=league_id,
            season=season,
            week=week,
            profiles=profiles,
            player_lookup=player_lookup,
        )
        if normalized:
            transactions.append(normalized)

    recap = league_recaps.build_weekly_recap(
        league_id=league_id,
        season=season,
        week=week,
        transactions=transactions,
        matchups=matchup_rows,
        profiles=profiles,
        movement=None,
        power_ranks=None,
    )
    return {"ok": True, "recap": recap, "reason": "", "max_completed_week": completed_week}


def _alert_key_for_link(link: str) -> str:
    """Stable, opaque identity for one alert item — a hash of its article
    link, never the raw URL or any football output (see
    docs/supabase_mobile_alert_reads.sql)."""

    return hashlib.sha256(str(link or "").encode("utf-8")).hexdigest()[:32]


def _fetch_read_alert_keys(
    config: dict, user_id: str, access_token: str, league_id: str
) -> set[str]:
    """Which alert_keys this user has already marked read in this league.

    Fails closed to "none read" (never crashes the alerts feed) — covers
    the pre-migration state where mobile_alert_reads doesn't exist yet.
    """

    if not user_id:
        return set()
    url = auth_supabase.rest_api_url(
        config,
        "mobile_alert_reads",
        f"select=alert_key&user_id=eq.{user_id}&league_id=eq.{league_id}",
    )
    try:
        response = requests.get(url, headers=auth_supabase.auth_headers(config, access_token), timeout=15)
    except Exception:
        return set()
    if response.status_code >= 400:
        return set()
    try:
        rows = response.json()
    except Exception:
        return set()
    if not isinstance(rows, list):
        return set()
    return {str(row.get("alert_key")) for row in rows if isinstance(row, dict) and row.get("alert_key")}


def _roster_relationship_map(roster: dict[str, Any]) -> dict[str, str]:
    """player_id -> "starter"|"bench"|"taxi"|"ir" for every rostered player.

    Sleeper's own roster payload already separates these (players/starters/
    taxi/reserve) — no lineup computation needed, this just reads the
    league's actual current state, not a suggested optimal lineup.
    """

    starters = {str(pid) for pid in (roster.get("starters") or []) if pid}
    taxi = {str(pid) for pid in (roster.get("taxi") or []) if pid}
    reserve = {str(pid) for pid in (roster.get("reserve") or []) if pid}
    players = {str(pid) for pid in (roster.get("players") or []) if pid}

    relationship: dict[str, str] = {}
    for player_id in players:
        if player_id in reserve:
            relationship[player_id] = "ir"
        elif player_id in taxi:
            relationship[player_id] = "taxi"
        elif player_id in starters:
            relationship[player_id] = "starter"
        else:
            relationship[player_id] = "bench"
    return relationship


def _project_alert_item(
    item: dict[str, Any],
    *,
    read_keys: set[str],
    player_ids_by_name: dict[str, str],
    roster_relationship: dict[str, str],
) -> dict[str, Any]:
    payload = _project_news_item(item)
    alert_key = _alert_key_for_link(str(item.get("link") or ""))
    payload["alert_key"] = alert_key
    payload["read"] = alert_key in read_keys
    matched_player = str(item.get("matched_player") or "")
    matched_player_id = player_ids_by_name.get(matched_player)
    payload["matched_player"] = _clean_json_value(item.get("matched_player"))
    payload["matched_player_id"] = matched_player_id
    payload["relevance_reason"] = _clean_json_value(item.get("relevance_reason"))
    payload["roster_relationship"] = roster_relationship.get(matched_player_id or "")
    return payload


@app.get("/v1/leagues/{league_id}/alerts")
def get_league_alerts(
    league_id: str,
    limit: int = 12,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Roster-relevant news alerts — "what happened that matters to me,"
    not a general feed (see GET /v1/news for that). Shares the exact same
    roster-news filtering and curation the web app uses
    (modules.my_news.filter_news_for_players / curate_player_news), scoped
    to the signed-in user's actual roster via the same my-roster resolution
    `/trade-analyzer` uses. Cross-league aggregation is not implemented —
    this is one league's feed, not the web app's full Alerts notification
    system, but read state is real (see POST .../alerts/read).
    """

    if not 1 <= limit <= MAX_NEWS_LIMIT:
        raise HTTPException(status_code=422, detail=f"limit must be between 1 and {MAX_NEWS_LIMIT}.")

    my_roster, reason = _resolve_my_roster(user, league_id)
    if my_roster is None:
        return {"ok": True, "items": [], "reason": reason}

    roster_ids = {str(pid) for pid in (my_roster.get("players") or [])}
    if not roster_ids:
        return {"ok": True, "items": [], "reason": "empty_roster"}

    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    if players_df.empty:
        return {"ok": True, "items": [], "reason": "no_player_data"}

    mine = players_df[players_df["player_id"].astype(str).isin(roster_ids)]
    player_names = [str(name) for name in mine.get("name", []) if str(name).strip()]
    roster_teams = sorted({str(team) for team in mine.get("team", []) if str(team).strip()})
    if not player_names:
        return {"ok": True, "items": [], "reason": "no_player_data"}
    player_ids_by_name = {
        str(row["name"]): str(row["player_id"])
        for _, row in mine.iterrows()
        if str(row.get("name") or "").strip()
    }

    news_cache.schedule_news_cache_refresh()
    pool = news_cache.load_cached_news_pool()
    filtered = my_news.filter_news_for_players(pool, player_names, roster_teams)
    curated = my_news.curate_player_news(filtered, max_items=limit)

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    read_keys = _fetch_read_alert_keys(config, user_id, str(user.get("_access_token") or ""), league_id)
    roster_relationship = _roster_relationship_map(my_roster)

    items = [
        _project_alert_item(
            item,
            read_keys=read_keys,
            player_ids_by_name=player_ids_by_name,
            roster_relationship=roster_relationship,
        )
        for item in curated
    ]
    return {"ok": True, "items": items, "reason": ""}


class MarkAlertReadRequest(BaseModel):
    alert_key: str


@app.post("/v1/leagues/{league_id}/alerts/read")
def mark_league_alert_read(
    league_id: str,
    body: MarkAlertReadRequest,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Durably mark one alert read (see docs/supabase_mobile_alert_reads.sql).
    Writes with the caller's own token — RLS (auth.uid() = user_id), not the
    service-role key, decides what's allowed. Fails closed (200, ok: False)
    rather than 500 when the table isn't migrated yet, so an older backend
    state never breaks the alerts feed itself.
    """

    alert_key = str(body.alert_key or "").strip()
    if not alert_key:
        raise HTTPException(status_code=422, detail="alert_key is required.")

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    if not user_id:
        return {"ok": False, "reason": "not_available"}

    url = auth_supabase.rest_api_url(config, "mobile_alert_reads")
    headers = auth_supabase.auth_headers(config, str(user.get("_access_token") or ""))
    headers["Prefer"] = "resolution=ignore-duplicates,return=minimal"
    try:
        response = requests.post(
            url,
            headers=headers,
            json={"user_id": user_id, "league_id": league_id, "alert_key": alert_key},
            timeout=15,
        )
    except Exception:
        return {"ok": False, "reason": "not_available"}
    if response.status_code >= 400:
        return {"ok": False, "reason": "not_available"}
    return {"ok": True, "reason": ""}


TRADE_OUTCOMES_TABLE = "trade_outcomes"
TRADE_OUTCOME_ANSWERS = {"yes", "no", "didnt_send"}
# Don't ask "did this happen?" the moment someone shares — give it roughly a
# day (matches modules/push_triggers.py's own copy of this same constant;
# the push-trigger sweep is a separate cron process so it can't import this
# module, hence the duplicated value rather than a shared import).
TRADE_OUTCOME_FOLLOWUP_DELAY_HOURS = 20
TRADE_OUTCOME_SNOOZE_HOURS = 20


class TradeOutcomeAssetSummary(BaseModel):
    name: str = ""
    position: str = ""


class RecordTradeShareRequest(BaseModel):
    partner_team_name: str = ""
    send: list[TradeOutcomeAssetSummary] = Field(default_factory=list)
    receive: list[TradeOutcomeAssetSummary] = Field(default_factory=list)
    value_edge_label: str = ""


@app.post("/v1/leagues/{league_id}/trade-outcomes")
def record_trade_share(
    league_id: str,
    body: RecordTradeShareRequest,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Record that a trade was shared, to ask "did this happen?" later.

    A snapshot, not a live reference — trade_summary is stored as-is so
    Trade History reads what was actually shared even if valuations move
    later (see docs/supabase_trade_outcomes.sql). Fails closed (ok: False)
    rather than 500 if the table isn't migrated yet.
    """

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    if not user_id:
        return {"ok": False, "reason": "not_available"}

    trade_summary = {
        "partner_team_name": body.partner_team_name.strip()[:120],
        "send": [
            {"name": asset.name.strip()[:80], "position": asset.position.strip()[:8]}
            for asset in body.send[:10]
        ],
        "receive": [
            {"name": asset.name.strip()[:80], "position": asset.position.strip()[:8]}
            for asset in body.receive[:10]
        ],
        "value_edge_label": body.value_edge_label.strip()[:40],
    }
    url = auth_supabase.rest_api_url(config, TRADE_OUTCOMES_TABLE)
    headers = auth_supabase.auth_headers(config, str(user.get("_access_token") or ""))
    headers["Prefer"] = "return=minimal"
    try:
        response = requests.post(
            url,
            headers=headers,
            json={
                "user_id": user_id,
                "league_id": league_id,
                "partner_team_name": trade_summary["partner_team_name"],
                "trade_summary": trade_summary,
            },
            timeout=15,
        )
    except Exception:
        return {"ok": False, "reason": "not_available"}
    if response.status_code >= 400:
        return {"ok": False, "reason": "not_available"}
    return {"ok": True, "reason": ""}


def _project_trade_outcome(row: dict[str, Any]) -> dict[str, Any]:
    summary = row.get("trade_summary") if isinstance(row.get("trade_summary"), dict) else {}
    return {
        "id": str(row.get("id") or ""),
        "league_id": str(row.get("league_id") or ""),
        "partner_team_name": str(row.get("partner_team_name") or ""),
        "trade_summary": summary,
        "shared_at": row.get("shared_at"),
    }


@app.get("/v1/trade-outcomes/pending")
def get_pending_trade_outcomes(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """Shared trades old enough to ask "did this happen?" about — powers
    both the in-app prompt and (indirectly, via the same table) the
    follow-up push. Not yet asked (or snoozed and the snooze has expired).
    """

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    if not user_id:
        return {"ok": True, "outcomes": []}

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=TRADE_OUTCOME_FOLLOWUP_DELAY_HOURS)).isoformat()
    now = datetime.now(timezone.utc).isoformat()
    query = (
        f"user_id=eq.{user_id}&outcome=eq.pending&shared_at=lte.{cutoff}"
        f"&or=(snoozed_until.is.null,snoozed_until.lte.{now})"
        "&select=id,league_id,partner_team_name,trade_summary,shared_at"
        "&order=shared_at.asc&limit=10"
    )
    url = auth_supabase.rest_api_url(config, TRADE_OUTCOMES_TABLE, query)
    try:
        response = requests.get(url, headers=auth_supabase.auth_headers(config, access_token), timeout=15)
    except Exception:
        return {"ok": True, "outcomes": []}
    if response.status_code >= 400:
        return {"ok": True, "outcomes": []}
    try:
        rows = response.json()
    except Exception:
        return {"ok": True, "outcomes": []}
    if not isinstance(rows, list):
        return {"ok": True, "outcomes": []}
    return {"ok": True, "outcomes": [_project_trade_outcome(row) for row in rows if isinstance(row, dict)]}


class AnswerTradeOutcomeRequest(BaseModel):
    outcome: str


@app.post("/v1/trade-outcomes/{outcome_id}/answer")
def answer_trade_outcome(
    outcome_id: str,
    body: AnswerTradeOutcomeRequest,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Record the user's answer, or snooze ("still pending") ~a day.

    "still_pending" never sets outcome_recorded_at — the row stays
    `outcome='pending'` and simply won't be asked about again until the
    snooze expires, so it keeps aging toward the push follow-up too.
    """

    answer = body.outcome.strip().lower()
    if answer not in TRADE_OUTCOME_ANSWERS and answer != "still_pending":
        raise HTTPException(status_code=422, detail="outcome must be yes, no, didnt_send, or still_pending.")

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    if not user_id:
        return {"ok": False, "reason": "not_available"}

    if answer == "still_pending":
        patch = {
            "snoozed_until": (
                datetime.now(timezone.utc) + timedelta(hours=TRADE_OUTCOME_SNOOZE_HOURS)
            ).isoformat(),
        }
    else:
        patch = {"outcome": answer, "outcome_recorded_at": datetime.now(timezone.utc).isoformat()}

    query = f"id=eq.{outcome_id}&user_id=eq.{user_id}"
    url = auth_supabase.rest_api_url(config, TRADE_OUTCOMES_TABLE, query)
    headers = auth_supabase.auth_headers(config, str(user.get("_access_token") or ""))
    headers["Prefer"] = "return=minimal"
    try:
        response = requests.patch(url, headers=headers, json=patch, timeout=15)
    except Exception:
        return {"ok": False, "reason": "not_available"}
    if response.status_code >= 400:
        return {"ok": False, "reason": "not_available"}
    return {"ok": True, "reason": ""}


def _stat_item_dict(item: player_quick_view.StatItem) -> dict[str, Any]:
    return {
        "label": item.label,
        "value": item.value,
        "note": item.note,
        "tone": item.tone,
        # Absent (null) whenever the position group was too small to rank
        # against — see player_quick_view.PERCENTILE_MIN_POOL.
        "percentile": _clean_json_value(item.percentile),
    }


def _season_stat_view_dict(season: player_quick_view.SeasonStatView) -> dict[str, Any]:
    return {
        "season": season.season,
        "season_type": season.season_type,
        "games": season.games,
        "complete": season.complete,
        "label": season.label,
        "key_stats": [_stat_item_dict(item) for item in season.key_stats],
        "fantasy": [_stat_item_dict(item) for item in season.fantasy],
        "efficiency": [_stat_item_dict(item) for item in season.efficiency],
        "usage": [_stat_item_dict(item) for item in season.usage],
    }


def _quick_view_stats_dict(stats: player_quick_view.PlayerQuickViewStats) -> dict[str, Any]:
    return {
        "seasons": [_season_stat_view_dict(season) for season in stats.seasons],
        "college": [_stat_item_dict(item) for item in stats.college],
        "college_available": stats.college_available,
        "career_totals_available": stats.career_totals_available,
        "position": stats.position,
        # 0-99 headline rating (the player's value_score percentile inside
        # their position). Absent (null) under the same pool gate as the
        # per-stat percentiles — see player_quick_view.PERCENTILE_MIN_POOL.
        "overall_rating": _clean_json_value(stats.overall_rating),
        # Position's dynasty prime-age window plus this player's status
        # relative to it (before/in/after) — see
        # modules.rankings.prime_window_status. Null for an unrecognized
        # position or missing age, never a guessed window.
        "prime_window": stats.prime_window,
    }


def _project_player_model(row: pd.Series, players_df: pd.DataFrame | None = None) -> dict[str, Any]:
    """The web dossier's "Model" grid — market/opportunity/scarcity/role/age/
    confidence/workload-trend — ported from app.py's player-card assembly
    (~app.py:4098-4110). Every field here is a plain column already present
    on the same row build_stats_view/build_executive_snapshot already read;
    this is a pure projection, not a new computation.

    age_score is a native per-player metric when present; some player rows
    only carry the coarser age_penalty (a lens-relative adjustment) instead
    — age_score_label tells the client which one it's showing, matching
    app.py's own "Age Score" vs. "Age Lens" distinction.

    usage_trend is the same weekly-recency read the web dossier now shows
    next to Opportunity, formatted by the one shared helper in
    modules.rankings (see _project_usage_trend) — null below its gate.

    decision_fit_narrative is the one new field here — a natural-language
    "why" sentence naming this player's real strongest/weakest composite
    inputs (modules.player_quick_view.decision_fit_narrative), not a new
    computation over the numbers already in this same dict.
    """

    age_score_raw = row.get("age_score") if "age_score" in row.index else None
    age_score_native = False
    if age_score_raw is not None:
        try:
            age_score_native = pd.notna(age_score_raw)
        except (TypeError, ValueError):
            age_score_native = False

    return {
        "market_score": _clean_json_value(row.get("market_score")),
        "opportunity_score": _clean_json_value(row.get("opportunity_score")),
        "scarcity_score": _clean_json_value(row.get("scarcity_score")),
        "role_score": _clean_json_value(row.get("role_score")),
        "age_score": _clean_json_value(age_score_raw if age_score_native else row.get("age_penalty")),
        "age_score_label": "Age Score" if age_score_native else "Age Lens",
        "opportunity_confidence": _clean_json_value(row.get("opportunity_confidence")),
        "workload_trend": _clean_json_value(row.get("workload_trend")),
        "usage_trend": _project_usage_trend(row),
        "decision_fit_narrative": player_quick_view.decision_fit_narrative(players_df, row),
    }


@app.get("/v1/players/{player_id}/quick-view")
def get_player_quick_view(
    player_id: str,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Player Quick View: season stats + bio + model breakdown for the
    player detail screen.

    Reuses modules.player_quick_view.build_stats_view/build_executive_snapshot
    verbatim — the same engine that renders the web app's player dossier
    pop-up (see that module's docstring). League-independent: the client
    already has valuation/rank context from /v1/leagues/{id}/rankings and
    combines both client-side.
    """

    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    matches = players_df[players_df["player_id"] == player_id]
    if matches.empty:
        return {"ok": True, "stats": None, "bio": None, "model": None, "reason": "not_found"}

    row = matches.iloc[0]
    # The full frame (not `matches`) is the percentile pool: build_stats_view
    # ranks this player against their position inside it.
    stats = player_quick_view.build_stats_view(row, players_df)
    bio = player_quick_view.build_executive_snapshot(row)
    return {
        "ok": True,
        "stats": _quick_view_stats_dict(stats),
        "bio": dataclasses.asdict(bio),
        "model": _project_player_model(row, players_df),
        "reason": "",
    }


MAX_WEEKLY_STATS_SEASONS_BACK = 3


@app.get("/v1/players/{player_id}/weekly-stats")
def get_player_weekly_stats(
    player_id: str,
    season: int | None = None,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Per-week fantasy points + snap share for one player in one season —
    powers Player Detail's points-by-week chart and snap% bar. Defaults to
    the current season; older seasons are fetched on demand rather than
    eagerly, since modules.sleeper only retains weekly rows for whichever
    season(s) a caller has actually asked to keep (see
    get_season_player_stats's `retain_weekly`).
    """

    target_season = int(season) if season is not None else sleeper.default_player_stats_season()
    oldest_allowed = sleeper.default_player_stats_season() - MAX_WEEKLY_STATS_SEASONS_BACK
    if target_season < oldest_allowed or target_season > sleeper.default_player_stats_season():
        raise HTTPException(
            status_code=422,
            detail=f"season must be between {oldest_allowed} and {sleeper.default_player_stats_season()}.",
        )

    season_stats = sleeper.get_season_player_stats(target_season, retain_weekly=True)
    player_stats = season_stats.get(str(player_id))
    weeks = player_stats.get("weekly") if isinstance(player_stats, dict) else None
    if not weeks:
        return {"ok": True, "season": target_season, "weeks": []}

    return {
        "ok": True,
        "season": target_season,
        "weeks": [
            {
                "week": int(row.get("week") or 0),
                "fantasy_points_ppr": _clean_json_value(row.get("fantasy_points_ppr")),
                "snap_share": _clean_json_value(row.get("snap_share")),
            }
            for row in weeks
        ],
    }


@app.get("/v1/players/{player_id}/schedule")
def get_player_schedule(
    player_id: str,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """This player's team's real regular-season schedule — opponent, home/
    away, and the published Vegas spread/total for each week (see
    modules.nfl_schedule's own docstring for the data source and why this
    is context only, never a scoring input). Empty when the player has no
    resolvable team (free agent / retired) or the schedule fetch fails —
    fails soft, same as every other enrichment endpoint here.
    """

    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    matches = players_df[players_df["player_id"] == player_id]
    if matches.empty:
        return {"ok": True, "team": None, "weeks": []}

    team = _clean_json_value(matches.iloc[0].get("team"))
    if not team:
        return {"ok": True, "team": None, "weeks": []}

    season = sleeper.default_player_stats_season()
    weeks = nfl_schedule.team_schedule(str(team), season)
    # Real points-allowed-based defense strength (see nfl_schedule's own
    # docstring) attached per week for display only — never a scoring
    # input, same "context only" contract as the rest of this schedule.
    defense_strength = nfl_schedule.team_defense_strength(season)
    for week in weeks:
        opponent = week.get("opponent")
        entry = defense_strength.get(str(opponent)) if opponent else None
        week["opponent_defense_tier"] = entry["tier"] if entry else None
    return {"ok": True, "team": str(team), "season": season, "weeks": weeks}


@app.get("/v1/players/{player_id}/career")
def get_player_career(
    player_id: str,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Every verified season this player has a cached Sleeper aggregate for
    — not just the current one. Player Quick View's own `stats.seasons`
    (GET /v1/players/{id}/quick-view) is deliberately a single-current-
    season tuple (see player_quick_view.py's docstring), the same
    limitation get_player_weekly_stats above already worked around for the
    Trends tab. This reuses modules.player_history.load_cached_career_resume
    — the same multi-season reader the web app's own Career tab already
    calls — instead of quick-view's engine.
    """

    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    matches = players_df[players_df["player_id"] == player_id]
    if matches.empty:
        return {"ok": True, "seasons": []}

    position_lookup: dict[str, str] = {}
    if "player_id" in players_df.columns:
        ids = players_df["player_id"].astype(str)
        positions = (
            players_df["position"].fillna("").astype(str)
            if "position" in players_df.columns
            else pd.Series("", index=players_df.index)
        )
        position_lookup = dict(zip(ids.tolist(), positions.tolist()))

    resume = player_history.load_cached_career_resume(
        player_id=player_id,
        current_row=matches.iloc[0].to_dict(),
        position_lookup=position_lookup,
    )
    return {
        "ok": True,
        "seasons": [
            {
                "season": season.season,
                "age": season.age,
                "games": season.games,
                "current_season": season.current_season,
                "key_stats": [
                    {"label": label, "value": value} for label, value in season.key_stats
                ],
            }
            for season in resume.seasons
        ],
    }


class AddGmTargetRequest(BaseModel):
    player_id: str
    source_surface: str = ""


def _project_gm_target(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "player_id": gm_targets.normalize_player_id(row.get("player_id")),
        "source_surface": str(row.get("source_surface") or ""),
        "created_at": row.get("created_at"),
        "untouchable": bool(row.get("untouchable")),
    }


def _fetch_gm_target_rows(
    config: dict[str, Any], user_id: str, access_token: str, league_id: str, *, select: str
) -> tuple[list[dict[str, Any]], str]:
    return account_store.fetch_rows(
        config,
        access_token,
        gm_targets.TARGETS_TABLE,
        user_id=user_id,
        extra_query=f"league_id=eq.{league_id}&select={select}&order=created_at.desc",
    )


def _fetch_gm_target_player_ids(
    config: dict[str, Any], user_id: str, access_token: str, league_id: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(all target player_ids, untouchable-only player_ids) for trade idea generation.

    Fails soft to (empty, empty) — a GM Targets outage must never block Trade
    Hub or the Dashboard trade tile from generating ideas.
    """

    if not user_id:
        return (), ()
    rows, error = _fetch_gm_target_rows(
        config, user_id, access_token, league_id, select="player_id,untouchable"
    )
    if error:
        return (), ()
    all_ids = tuple(
        sorted({gm_targets.normalize_player_id(row.get("player_id")) for row in rows if row.get("player_id")})
    )
    untouchable_ids = tuple(
        sorted(
            gm_targets.normalize_player_id(row.get("player_id"))
            for row in rows
            if row.get("player_id") and bool(row.get("untouchable"))
        )
    )
    return all_ids, untouchable_ids


@app.get("/v1/leagues/{league_id}/gm-targets")
def get_gm_targets(league_id: str, user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """The caller's durable watchlist for this league (GM Targets).

    Preference rows only, per modules.gm_targets' own contract (see
    docs/experimental-gm-targets-contract.md) — never stores name, rank, or
    valuation here; the mobile client enriches display info client-side via
    /v1/players and /v1/leagues/{id}/rankings, same separation the web app
    keeps. Fails soft to an empty list if the table isn't reachable rather
    than erroring the whole screen.
    """

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    if not user_id:
        return {"ok": True, "targets": []}

    rows, error = _fetch_gm_target_rows(
        config,
        user_id,
        access_token,
        league_id,
        select="player_id,source_surface,created_at,untouchable",
    )
    if error:
        return {"ok": True, "targets": []}
    return {"ok": True, "targets": [_project_gm_target(row) for row in rows]}


@app.post("/v1/leagues/{league_id}/gm-targets")
def add_gm_target(
    league_id: str,
    payload: AddGmTargetRequest,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Add a player to the caller's watchlist for this league.

    Idempotent (upsert on the same primary key modules.gm_targets uses) and
    cap-enforced server-side — Free up to MAX_TARGETS_FREE, Premium up to
    MAX_TARGETS_PREMIUM, matching the web app's entitlement.
    """

    player_id = gm_targets.normalize_player_id(payload.player_id)
    if not player_id:
        raise HTTPException(status_code=422, detail="player_id is required.")

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    profile = _fetch_profile_fields(config, user_id, access_token) if user_id else {"entitlement": "free"}
    cap = (
        gm_targets.MAX_TARGETS_PREMIUM
        if profile.get("entitlement") == "premium"
        else gm_targets.MAX_TARGETS_FREE
    )

    existing, error = _fetch_gm_target_rows(config, user_id, access_token, league_id, select="player_id")
    if error:
        return {"ok": False, "reason": "not_available"}
    existing_ids = {gm_targets.normalize_player_id(row.get("player_id")) for row in existing}
    if player_id not in existing_ids and len(existing_ids) >= cap:
        return {"ok": False, "reason": "at_cap", "cap": cap}

    ok, error = account_store.upsert_row(
        config,
        access_token,
        gm_targets.TARGETS_TABLE,
        {
            "user_id": user_id,
            "league_id": league_id,
            "player_id": player_id,
            "source_surface": payload.source_surface[:64],
        },
        on_conflict="user_id,league_id,player_id",
    )
    if not ok:
        return {"ok": False, "reason": "not_available"}
    return {"ok": True, "reason": ""}


@app.delete("/v1/leagues/{league_id}/gm-targets/{player_id}")
def remove_gm_target(
    league_id: str,
    player_id: str,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    pid = gm_targets.normalize_player_id(player_id)
    ok, error = account_store.delete_rows(
        config,
        access_token,
        gm_targets.TARGETS_TABLE,
        query=f"user_id=eq.{user_id}&league_id=eq.{league_id}&player_id=eq.{pid}",
    )
    if not ok:
        return {"ok": False, "reason": "not_available"}
    return {"ok": True, "reason": ""}


class SetGmTargetUntouchableRequest(BaseModel):
    untouchable: bool


@app.patch("/v1/leagues/{league_id}/gm-targets/{player_id}/untouchable")
def set_gm_target_untouchable(
    league_id: str,
    player_id: str,
    payload: SetGmTargetUntouchableRequest,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Mark/unmark an existing GM Target as untouchable.

    Requires the row to already exist (add it first) — never creates a
    target. An untouchable target is hard-blocked from every outgoing trade
    package the automated Trade Hub engine generates (see
    modules.trade_hub_engine.generate_trade_idea_records), the same
    protection a team's own core starters already get.
    """

    pid = gm_targets.normalize_player_id(player_id)
    if not pid:
        raise HTTPException(status_code=422, detail="player_id is required.")

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")

    existing, error = _fetch_gm_target_rows(
        config, user_id, access_token, league_id, select="player_id"
    )
    if error:
        return {"ok": False, "reason": "not_available"}
    existing_ids = {gm_targets.normalize_player_id(row.get("player_id")) for row in existing}
    if pid not in existing_ids:
        return {"ok": False, "reason": "not_found"}

    ok, error = account_store.upsert_row(
        config,
        access_token,
        gm_targets.TARGETS_TABLE,
        {
            "user_id": user_id,
            "league_id": league_id,
            "player_id": pid,
            "untouchable": bool(payload.untouchable),
        },
        on_conflict="user_id,league_id,player_id",
    )
    if not ok:
        return {"ok": False, "reason": "not_available"}
    return {"ok": True, "reason": ""}


def _project_award(badge: player_awards.PlayerBadge) -> dict[str, Any]:
    return {
        "badge_id": badge.badge_id,
        "category": badge.category,
        "title": badge.title,
        "short_label": badge.short_label,
        "tier": badge.tier,
        "season": badge.season,
        "rank": badge.rank,
        "metric_value": badge.metric_value,
        "description": badge.description,
        "occurrence_count": badge.occurrence_count,
    }


@app.get("/v1/players/{player_id}/awards")
def get_player_awards(
    player_id: str,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Verified fantasy-performance badges (modules.player_awards) — never
    invented, never AI-generated. Reads the same local season stat cache
    files the web app's career résumé uses; empty when a player has no
    qualifying seasons on file, not an error.
    """

    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    matches = players_df[players_df["player_id"] == player_id]
    if matches.empty:
        return {"ok": True, "awards": [], "reason": "not_found"}

    position = str(matches.iloc[0].get("position") or "")
    index = player_awards.build_season_cache_index()
    season_rows = player_awards.award_rows_for_player(index, player_id=player_id, position=position)
    badges = player_awards.build_player_awards(season_rows, position=position)
    display = player_awards.select_display_badges(badges)
    return {"ok": True, "awards": [_project_award(badge) for badge in display], "reason": ""}


class RegisterPushTokenRequest(BaseModel):
    expo_push_token: str
    platform: str = ""
    device_name: str = ""


class UnregisterPushTokenRequest(BaseModel):
    expo_push_token: str


@app.post("/v1/push/register")
def register_push_token(
    payload: RegisterPushTokenRequest,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Upsert the caller's Expo push token (docs/supabase_push_tokens.sql).

    Idempotent by design — the mobile app calls this on every app launch
    where a session exists, not just on first grant, since Expo push tokens
    can rotate.
    """

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    ok, error = push_tokens.register_token(
        config,
        access_token,
        user_id=user_id,
        expo_push_token=payload.expo_push_token,
        platform=payload.platform,
        device_name=payload.device_name,
    )
    if not ok:
        return {"ok": False, "reason": "not_available"}
    return {"ok": True, "reason": ""}


@app.post("/v1/push/unregister")
def unregister_push_token(
    payload: UnregisterPushTokenRequest,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Remove one of the caller's tokens — called on sign-out so a shared or
    reused device doesn't keep delivering pushes meant for this account.
    """

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    ok, error = push_tokens.unregister_token(
        config,
        access_token,
        user_id=user_id,
        expo_push_token=payload.expo_push_token,
    )
    if not ok:
        return {"ok": False, "reason": "not_available"}
    return {"ok": True, "reason": ""}


@app.post("/v1/push/test")
def send_test_push(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """Send a test push to every device the caller has registered — lets the
    app verify the whole pipeline (permission -> token -> backend -> Expo ->
    device) without waiting on a real alert to fire.
    """

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    tokens, error = push_tokens.fetch_tokens_for_user(config, access_token, user_id=user_id)
    if error:
        return {"ok": False, "reason": "not_available"}
    if not tokens:
        return {"ok": False, "reason": "no_registered_tokens"}
    result = push_tokens.send_expo_push_notifications(
        tokens,
        title="FantasyGM Lab",
        body="Push notifications are working — you'll hear from us when your roster needs attention.",
        data={"kind": "test"},
    )
    return {"ok": bool(result.get("ok")), "reason": "" if result.get("ok") else "delivery_failed", "sent": result.get("sent", 0)}


class UpdatePushPreferenceRequest(BaseModel):
    category: str
    enabled: bool


def _push_categories_from_settings(settings: dict[str, Any]) -> dict[str, bool]:
    stored = settings.get("push_categories") if isinstance(settings.get("push_categories"), dict) else {}
    return {category: bool(stored.get(category, True)) for category in push_triggers.TOGGLEABLE_PUSH_CATEGORIES}


@app.get("/v1/push/preferences")
def get_push_preferences(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """Per-category push toggles — same categories the automated push-trigger
    sweep sends (top_priority/watch/recap/injury). Backed by the existing
    user_settings table/RLS (auth.uid()=user_id) under a "push_categories"
    key, not a new table — the sweep (its own service-role process) reads
    this same key via modules.push_triggers.fetch_push_preferences.
    """

    config = auth_supabase.get_supabase_config()
    access_token = str(user.get("_access_token") or "")
    user_id = str(user.get("id") or "")
    settings, error = account_store.fetch_user_settings(config, access_token, user_id=user_id)
    if error:
        return {"ok": False, "categories": _push_categories_from_settings({})}
    return {"ok": True, "categories": _push_categories_from_settings(settings.get("settings") or {})}


@app.post("/v1/push/preferences")
def update_push_preference(
    body: UpdatePushPreferenceRequest,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    if body.category not in push_triggers.TOGGLEABLE_PUSH_CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail="category must be one of: " + ", ".join(push_triggers.TOGGLEABLE_PUSH_CATEGORIES),
        )

    config = auth_supabase.get_supabase_config()
    access_token = str(user.get("_access_token") or "")
    user_id = str(user.get("id") or "")
    current, error = account_store.fetch_user_settings(config, access_token, user_id=user_id)
    if error:
        return {"ok": False, "categories": _push_categories_from_settings({})}
    settings = dict(current.get("settings") or {})
    categories = _push_categories_from_settings(settings)
    categories[body.category] = body.enabled
    settings["push_categories"] = categories
    payload = account_store.build_user_settings_payload(user_id=user_id, settings=settings)
    ok, error = account_store.upsert_user_settings(config, access_token, payload)
    if not ok:
        return {"ok": False, "categories": categories}
    return {"ok": True, "categories": categories}


UI_DENSITY_VALUES = {"guided", "compact"}
THEME_MODE_VALUES = {"light", "dark", "auto"}


def _device_preferences_from_settings(settings: dict[str, Any]) -> dict[str, Any]:
    density = str(settings.get("ui_density") or "guided")
    if density not in UI_DENSITY_VALUES:
        density = "guided"
    theme_mode = str(settings.get("theme_mode") or "dark")
    if theme_mode not in THEME_MODE_VALUES:
        theme_mode = "dark"
    last_league_id = str(settings.get("last_league_id") or "")
    last_league_name = str(settings.get("last_league_name") or "")
    return {
        "ui_density": density,
        "theme_mode": theme_mode,
        "last_league": (
            {"league_id": last_league_id, "league_name": last_league_name} if last_league_id else None
        ),
    }


@app.get("/v1/preferences")
def get_device_preferences(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """Cross-device account preferences: display density (guided/compact)
    and the last league opened. Backed by the same user_settings blob as
    push preferences, under "ui_density"/"last_league_id"/"last_league_name"
    keys — not a new table. Mobile keeps its own AsyncStorage copy for
    instant reads; this is the durable source of truth a second device or
    reinstall reconciles against.
    """

    config = auth_supabase.get_supabase_config()
    access_token = str(user.get("_access_token") or "")
    user_id = str(user.get("id") or "")
    current, error = account_store.fetch_user_settings(config, access_token, user_id=user_id)
    if error:
        return {"ok": False, **_device_preferences_from_settings({})}
    return {"ok": True, **_device_preferences_from_settings(current.get("settings") or {})}


class UpdateDevicePreferencesRequest(BaseModel):
    ui_density: str | None = None
    theme_mode: str | None = None
    last_league_id: str | None = None
    last_league_name: str | None = None


@app.post("/v1/preferences")
def update_device_preferences(
    body: UpdateDevicePreferencesRequest,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Partial update — only the fields the caller actually sends are
    changed, matching update_push_preference's read-modify-write pattern
    (PostgREST upsert replaces the whole `settings` column, so a naive
    write would silently drop push_categories or the other preference).
    """

    if body.ui_density is not None and body.ui_density not in UI_DENSITY_VALUES:
        raise HTTPException(
            status_code=422,
            detail="ui_density must be one of: " + ", ".join(UI_DENSITY_VALUES),
        )
    if body.theme_mode is not None and body.theme_mode not in THEME_MODE_VALUES:
        raise HTTPException(
            status_code=422,
            detail="theme_mode must be one of: " + ", ".join(THEME_MODE_VALUES),
        )

    config = auth_supabase.get_supabase_config()
    access_token = str(user.get("_access_token") or "")
    user_id = str(user.get("id") or "")
    current, error = account_store.fetch_user_settings(config, access_token, user_id=user_id)
    if error:
        return {"ok": False, **_device_preferences_from_settings({})}
    settings = dict(current.get("settings") or {})
    if body.ui_density is not None:
        settings["ui_density"] = body.ui_density
    if body.theme_mode is not None:
        settings["theme_mode"] = body.theme_mode
    if body.last_league_id is not None:
        settings["last_league_id"] = body.last_league_id
    if body.last_league_name is not None:
        settings["last_league_name"] = body.last_league_name
    payload = account_store.build_user_settings_payload(user_id=user_id, settings=settings)
    ok, error = account_store.upsert_user_settings(config, access_token, payload)
    if not ok:
        return {"ok": False, **_device_preferences_from_settings(settings)}
    return {"ok": True, **_device_preferences_from_settings(settings)}


# Decision Memory v1 ("structured picks," per explicit product direction —
# not free text): a durable per-league GM stance, reusing the TeamStrategy
# values Trade Hub/Trade Analyzer already offer as an in-session-only picker
# (contender/fringe_contender/retool/rebuild/tank). Stored in the same
# user_settings blob under "team_strategy_by_league" (league_id -> strategy)
# rather than a new table — a GM's stance genuinely differs by league, so
# this can't be a single flat preference like ui_density.
TEAM_STRATEGY_VALUES = {"contender", "fringe_contender", "retool", "rebuild", "tank"}


def _fetch_gm_stance_with_set_flag(
    config: dict, access_token: str, *, user_id: str, league_id: str
) -> tuple[str, bool]:
    """Best-effort read — any failure just falls back to ("retool", False),
    the same default every strategy-consuming endpoint already used before
    this existed. `is_set` distinguishes "the user actually chose this" from
    "nothing chosen yet, showing the fallback" — used only by get_gm_stance
    to power the mobile in-app "not set yet" nudge; nothing else needs it.
    """

    current, error = account_store.fetch_user_settings(config, access_token, user_id=user_id)
    if error:
        return "retool", False
    by_league = (current.get("settings") or {}).get("team_strategy_by_league")
    stored = by_league.get(league_id) if isinstance(by_league, dict) else None
    if stored is None:
        return "retool", False
    return normalize_team_strategy(stored), True


def _fetch_stored_gm_stance(config: dict, access_token: str, *, user_id: str, league_id: str) -> str:
    strategy, _ = _fetch_gm_stance_with_set_flag(config, access_token, user_id=user_id, league_id=league_id)
    return strategy


@app.get("/v1/leagues/{league_id}/gm-stance")
def get_gm_stance(league_id: str, user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """The caller's remembered team strategy for this league, so Trade Hub,
    Trade Analyzer, and the Dashboard's trade tile don't all separately
    default to "retool" every visit and make the user re-declare their
    stance each time.
    """

    config = auth_supabase.get_supabase_config()
    access_token = str(user.get("_access_token") or "")
    user_id = str(user.get("id") or "")
    strategy, is_set = _fetch_gm_stance_with_set_flag(
        config, access_token, user_id=user_id, league_id=league_id
    )
    return {"ok": True, "strategy": strategy, "is_set": is_set}


class UpdateGmStanceRequest(BaseModel):
    # `null` (or an omitted field) clears the stance instead of setting one,
    # so a later GET reports is_set=False again and the app goes back to the
    # auto-picked "retool" fallback plus its "pick one" nudge. coridian_:
    # "there is no auto function to put it back to auto picked" — once a
    # stance was chosen there was no way out of it short of editing the
    # stored settings blob by hand.
    strategy: str | None = None


@app.post("/v1/leagues/{league_id}/gm-stance")
def update_gm_stance(
    league_id: str,
    body: UpdateGmStanceRequest,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    clearing = body.strategy is None
    if not clearing and body.strategy not in TEAM_STRATEGY_VALUES:
        raise HTTPException(
            status_code=422,
            detail="strategy must be one of: " + ", ".join(TEAM_STRATEGY_VALUES),
        )

    config = auth_supabase.get_supabase_config()
    access_token = str(user.get("_access_token") or "")
    user_id = str(user.get("id") or "")
    current, error = account_store.fetch_user_settings(config, access_token, user_id=user_id)
    if error:
        return {"ok": False, "strategy": "retool", "is_set": False}
    settings = dict(current.get("settings") or {})
    by_league = dict(settings.get("team_strategy_by_league") or {})
    if clearing:
        # Drop the key entirely rather than storing a null: _fetch_gm_stance_
        # with_set_flag treats a missing key as "never chosen", and leaving a
        # null behind would only be equivalent by accident.
        by_league.pop(league_id, None)
    else:
        by_league[league_id] = body.strategy
    settings["team_strategy_by_league"] = by_league
    resolved = "retool" if clearing else str(body.strategy)
    payload = account_store.build_user_settings_payload(user_id=user_id, settings=settings)
    ok, error = account_store.upsert_user_settings(config, access_token, payload)
    if not ok:
        return {"ok": False, "strategy": resolved, "is_set": not clearing}
    return {"ok": True, "strategy": resolved, "is_set": not clearing}


def _project_briefing_item(item: Any) -> dict[str, Any]:
    payload = item.to_dict()
    return {
        "category": payload.get("category"),
        "headline": payload.get("headline"),
        "reason": payload.get("reason"),
        "supporting_context": payload.get("supporting_context"),
        "destination": payload.get("destination"),
        "route_player_id": payload.get("route_player_id") or "",
        "recommendation_narrative": payload.get("recommendation_narrative"),
        "presentation": payload.get("presentation"),
        "recommendation_id": payload.get("recommendation_id") or "",
    }


# Matches web's app.py `visible_action_items = action_center_items if
# is_premium else action_center_items[:4]` — the free-tier cap on Today's
# Game Plan.
FREE_DASHBOARD_VISIBLE_ITEMS = 4


@app.get("/v1/leagues/{league_id}/dashboard")
def get_league_dashboard(
    league_id: str,
    lens: str = "Dynasty",
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """The caller's "Next Move" briefing for this league.

    Shares the same composition pipeline as the web app's Dashboard
    (modules.dashboard_workflow.organize_dashboard_items ->
    modules.daily_gm_briefing.compose_daily_gm_briefing) and the same
    underlying engines for each tile (modules.team_eval,
    modules.trade_analyzer_fit, modules.injury_ui, modules.waivers_ui) via
    modules.dashboard_engine — see that module's docstring for why it's a
    fresh composition rather than importing app.py directly (modules/ never
    imports app.py). Includes a Top Trade Opportunity tile fed by the same
    Trade Hub engine (modules.trade_hub_engine), using the caller's
    remembered GM stance for this league (see get_gm_stance) rather than a
    hardcoded default — falls back to "retool" only if nothing's been set.
    """

    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    profile = _fetch_profile_fields(config, user_id, str(user.get("_access_token") or "")) if user_id else {}

    my_roster, reason = _resolve_my_roster(user, league_id, profile=profile)
    if my_roster is None:
        return {"ok": True, "items": [], "quiet": True, "team_snapshot": None, "reason": reason}

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")
    settings = league_value_settings.detect_league_value_settings_from_payload(league)

    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    players_df = player_eligibility.filter_current_fantasy_players(
        players_df, surface="mobile_api_dashboard", league=league
    )
    if players_df.empty:
        return {"ok": True, "items": [], "quiet": True, "team_snapshot": None, "reason": "no_player_data"}

    valued = league_value_settings.apply_valuation_lens(players_df, lens, settings)
    score_field = league_value_settings.valuation_score_field(lens)

    roster_player_ids = {str(pid) for pid in (my_roster.get("players") or [])}
    if not roster_player_ids:
        return {"ok": True, "items": [], "quiet": True, "team_snapshot": None, "reason": "empty_roster"}

    rosters = sleeper.get_rosters(league_id)
    all_rostered_player_ids: set[str] = set()
    for roster in rosters:
        all_rostered_player_ids.update(str(pid) for pid in (roster.get("players") or []))

    team_strategy = _fetch_stored_gm_stance(
        config, str(user.get("_access_token") or ""), user_id=user_id, league_id=league_id
    )
    # Shares the exact same cached search Trade Hub's own endpoint uses
    # (trade_hub_engine.generate_trade_idea_records_cached) for this tile,
    # rather than letting compose_next_move_briefing recompute the identical
    # (league, roster, strategy, lens) search a user may have just triggered
    # moments earlier by opening Trade Hub.
    gm_target_ids, gm_untouchable_ids = _fetch_gm_target_player_ids(
        config, user_id, str(user.get("_access_token") or ""), league_id
    )
    trade_idea_records = None
    try:
        trade_idea_records = trade_hub_engine.generate_trade_idea_records_cached(
            league_id=league_id,
            roster_id=int(my_roster.get("roster_id")),
            strategy=team_strategy,
            lens=lens,
            players_db_path=PLAYERS_DB_PATH,
            untouchable_player_ids=gm_untouchable_ids,
            gm_target_player_ids=gm_target_ids,
        )
    except (TypeError, ValueError):
        pass

    # Computed once and threaded into compose_next_move_briefing below (as
    # an optional override, same pattern as trade_idea_records) *and* reused
    # here for Team Snapshot — this used to be two full suggest_optimal_lineup
    # passes over the identical roster on every dashboard load, one inside
    # compose_next_move_briefing and one recomputed right after it returned.
    roster_df = valued[valued["player_id"].astype(str).isin(roster_player_ids)].copy()
    lineup_df = suggest_optimal_lineup(roster_df, settings, score_field=score_field)
    injury_context = trade_analyzer_fit.roster_injury_context(roster_df, lineup_df)

    briefing = dashboard_engine.compose_next_move_briefing(
        league_id=league_id,
        roster_id=str(my_roster.get("roster_id") or ""),
        players_df=valued,
        roster_player_ids=roster_player_ids,
        all_rostered_player_ids=all_rostered_player_ids,
        league_settings=settings,
        score_field=score_field,
        entitlement=str(profile.get("entitlement") or "free"),
        rosters=rosters,
        team_strategy=team_strategy,
        trade_idea_records=trade_idea_records,
        roster_df=roster_df,
        lineup_df=lineup_df,
        injury_context=injury_context,
    )

    # Team Snapshot: record comes straight off the roster we already
    # fetched; health/average age reuse the roster_df/lineup_df/injury_context
    # computed once above. Power/franchise rank reuse modules.league_rankings
    # (ported out of app.py's add_league_detail_ranks/build_league_display_frame
    # in PR #520 for get_league_team_rankings) — the same league-wide frame
    # that endpoint already computes on demand.
    injury_display_context = injury_ui.resolve_team_injury_context(injury_context)
    health_flag = injury_ui.team_injury_display_label(injury_display_context, include_uncertainty=True) or "Stable"
    injury_narrative = _project_team_injury_narrative(injury_display_context)
    average_age = (
        float(roster_df["age"].mean())
        if not roster_df.empty and roster_df["age"].notna().any()
        else None
    )

    power_rank = None
    franchise_rank = None
    rankings_frame = league_rankings.build_league_rankings_frame_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
    )
    if not rankings_frame.empty:
        my_roster_id = str(my_roster.get("roster_id") or "")
        match = rankings_frame[rankings_frame["roster_id"].astype(str) == my_roster_id]
        if not match.empty:
            power_rank = _clean_json_value(match.iloc[0].get("power_rank"))
            franchise_rank = _clean_json_value(match.iloc[0].get("franchise_rank"))

    roster_settings = my_roster.get("settings") or {}
    team_snapshot = {
        "wins": roster_settings.get("wins"),
        "losses": roster_settings.get("losses"),
        "ties": roster_settings.get("ties"),
        "health_flag": health_flag,
        # The "why" behind health_flag — which injuries, and which players
        # are actually driving it. Already computed by the same
        # roster_injury_context call above and rendered on web; mobile used
        # to show the bare flag word with no supporting context.
        "key_injuries_summary": injury_narrative["key_injuries_summary"],
        "top_injury_impact_summary": injury_narrative["top_injury_impact_summary"],
        "top_injury_impact_players": injury_narrative["top_injury_impact_players"],
        # The real count driving health_flag — modules.rankings.summarize_team_injuries
        # already computes this exact number; top_injury_impact_players above is
        # trimmed to a couple of cards and undercounts if used as a total.
        "injured_starters": _clean_json_value(injury_display_context.get("injured_starters")),
        "average_age": round(average_age, 1) if average_age is not None else None,
        "power_rank": power_rank,
        "franchise_rank": franchise_rank,
    }

    # Free-tier cap matches the web app's own gate (app.py:
    # `visible_action_items = action_center_items if is_premium else
    # action_center_items[:4]`) — applied here to the already-composed,
    # priority-ordered Today's Game Plan list rather than the pre-
    # reorganization raw tile list web slices, since that's the exact
    # sequence this response actually displays.
    is_premium = str(profile.get("entitlement") or "free") == "premium"
    all_items = list(briefing.items)
    visible_items = all_items if is_premium else all_items[:FREE_DASHBOARD_VISIBLE_ITEMS]

    return {
        "ok": True,
        "items": [_project_briefing_item(item) for item in visible_items],
        "quiet": briefing.quiet,
        "quiet_reason": briefing.quiet_reason,
        "team_snapshot": team_snapshot,
        "reason": "",
        "entitlement": {
            "is_premium": is_premium,
            "visible_count": len(visible_items),
            "hidden_count": len(all_items) - len(visible_items),
        },
    }


# Display order for My Team's starters section — matches
# modules.team_eval.suggest_optimal_lineup's own slot-assignment order.
# Bench keeps the frame's existing sort_score-descending order untouched.
_LINEUP_SLOT_ORDER = ["QB", "RB", "WR", "TE", "FLEX", "SUPER_FLEX", "WR/RB", "K"]


def _project_lineup_row(row: pd.Series, score_field: str) -> dict[str, Any]:
    """One lineup row for the client.

    injury_label, not raw injury_status, is what a client renders as the
    injury tag: unavailability lives in EITHER Sleeper field — a weekly
    "Questionable"/"Out" arrives on `injury_status`, while IR/PUP/
    season-ending arrives on `status` with `injury_status` often blank — so
    a pill driven by injury_status alone silently drops exactly the players
    who are most unavailable. modules.rankings.injury_display_label is the
    one place that resolution lives (the web dossier reads the same
    injury_level severity behind it).
    """

    status = _clean_json_value(row.get("status"))
    injury_status = _clean_json_value(row.get("injury_status"))
    return {
        "player_id": _clean_json_value(row.get("player_id")),
        "name": _clean_json_value(row.get("name")),
        "position": _clean_json_value(row.get("position")),
        "team": _clean_json_value(row.get("team")),
        "age": _clean_json_value(row.get("age")),
        "status": status,
        "injury_status": injury_status,
        "injury_label": rankings.injury_display_label(str(status or ""), str(injury_status or "")),
        # The lineup builder's own availability call, so the client flags a
        # ruled-out starter (only ever slotted when nothing healthy could
        # fill the slot) instead of presenting him as a clean start.
        "ruled_out": bool(row.get("ruled_out")),
        "tier": _clean_json_value(row.get("player_tier")),
        "score": _clean_json_value(row.get(score_field)),
        "slot": _clean_json_value(row.get("slot")),
        "suggested_starter": bool(row.get("suggested_starter")),
        "opportunity_label": _clean_json_value(row.get("opportunity_label")),
    }


def _suggested_lineup_split(
    valued: pd.DataFrame,
    roster_player_ids: set[str],
    settings: dict[str, Any],
    score_field: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """One roster's suggested starters (slot-ordered) and bench.

    The single place /my-team and /matchup both run
    modules.team_eval.suggest_optimal_lineup and project its rows, so the
    two surfaces can never drift into showing different "best lineup"
    answers for the same roster.
    """

    roster_df = valued[valued["player_id"].astype(str).isin(roster_player_ids)].copy()
    lineup_df = suggest_optimal_lineup(roster_df, settings, score_field=score_field)

    players = [_project_lineup_row(row, score_field) for _, row in lineup_df.iterrows()]
    starters = [p for p in players if p["suggested_starter"]]
    starters.sort(
        key=lambda p: _LINEUP_SLOT_ORDER.index(p["slot"]) if p["slot"] in _LINEUP_SLOT_ORDER else len(_LINEUP_SLOT_ORDER)
    )
    bench = [p for p in players if not p["suggested_starter"]]
    return starters, bench


@app.get("/v1/leagues/{league_id}/my-team")
def get_league_my_team(
    league_id: str,
    lens: str = "Dynasty",
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Your own roster's suggested starting lineup vs. bench.

    Runs the exact same modules.team_eval.suggest_optimal_lineup computation
    get_league_dashboard already calls internally for its injury/health
    tiles, surfaced here directly as a real starters/bench breakdown instead
    of folded into a briefing summary.

    Lightweight scope: this is the lineup view only, not the web app's full
    My Team page (which also supports persisted untouchable-player tags and
    a manual strategy override). Those need new stateful product surface —
    a Supabase table and real UI for editing/persisting per-user roster
    state — not a port of existing pure logic, so they're an explicit,
    separate follow-up rather than silently reduced scope here.
    """

    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    profile = _fetch_profile_fields(config, user_id, str(user.get("_access_token") or "")) if user_id else {}
    my_roster, reason = _resolve_my_roster(user, league_id, profile=profile)
    if my_roster is None:
        return {"ok": True, "starters": [], "bench": [], "reason": reason}

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")
    settings = league_value_settings.detect_league_value_settings_from_payload(league)

    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    players_df = player_eligibility.filter_current_fantasy_players(
        players_df, surface="mobile_api_my_team", league=league
    )
    if players_df.empty:
        return {"ok": True, "starters": [], "bench": [], "reason": "no_player_data"}

    valued = league_value_settings.apply_valuation_lens(players_df, lens, settings)
    score_field = league_value_settings.valuation_score_field(lens)

    roster_player_ids = {str(pid) for pid in (my_roster.get("players") or [])}
    if not roster_player_ids:
        return {"ok": True, "starters": [], "bench": [], "reason": "empty_roster"}

    starters, bench = _suggested_lineup_split(valued, roster_player_ids, settings, score_field)

    return {
        "ok": True,
        "starters": starters,
        "bench": bench,
        "reason": "",
        "roster_id": str(my_roster.get("roster_id") or ""),
    }


# The one sentence every matchup surface (API, mobile headline, tests)
# points at for what this comparison actually measures. This app has NO
# weekly points-projection data source — nothing in modules/ produces one —
# so the matchup view ranks lineups by the same season-long value/
# opportunity signal the rest of the app already computes, and says so.
# Do not relabel this as "projected points" without a real weekly
# projection feed behind it.
SEASON_VALUE_BASIS = "season_value"
SEASON_VALUE_BASIS_LABEL = "Season-long value & opportunity signal — not a weekly points projection."

# Below this relative gap the two lineups are called even rather than
# implying a real edge — a season-value total is a coarse signal, and a
# sub-3% difference is well inside its noise.
_MATCHUP_EVEN_THRESHOLD = 0.03


def _matchup_starter_why(player: dict[str, Any], best_score_by_position: dict[str, float]) -> str:
    """Why this player is a suggested starter, in season-form terms only.

    Every clause comes from data that genuinely exists on the lineup row
    (tier, opportunity/workload label, season-value rank on this roster,
    injury tag). Deliberately says nothing about this week's opponent or
    expected points — no opponent-defense or weekly-projection data source
    exists in this codebase.
    """

    bits: list[str] = []
    tier = str(player.get("tier") or "").strip()
    if tier:
        bits.append(f"{tier} tier")
    opportunity = str(player.get("opportunity_label") or "").strip()
    if opportunity:
        bits.append(opportunity)

    position = str(player.get("position") or "").strip()
    score = player.get("score")
    if position and isinstance(score, (int, float)) and best_score_by_position.get(position) == float(score):
        bits.append(f"top {position} on this roster by season value")

    # injury_label (not raw injury_status) so an IR/PUP/season-ending
    # starter reads as injured here too — see _project_lineup_row.
    injury = str(player.get("injury_label") or "").strip()
    if injury:
        if player.get("ruled_out"):
            slot = str(player.get("slot") or "").strip() or "this"
            bits.append(f"{injury} — ruled out, and no available alternative for the {slot} slot")
        else:
            bits.append(f"{injury} — confirm status before kickoff")

    if not bits:
        slot = str(player.get("slot") or "").strip() or "this"
        return f"Best season-value option available for the {slot} slot."
    return " · ".join(bits)


def _matchup_side(
    roster_id: str,
    roster: dict[str, Any],
    profile: dict[str, Any],
    valued: pd.DataFrame,
    settings: dict[str, Any],
    score_field: str,
) -> dict[str, Any]:
    """One team's side of the matchup: identity, suggested starters, season-value total.

    Both sides run the SAME modules.team_eval.suggest_optimal_lineup pass
    (via _suggested_lineup_split), so the comparison is apples-to-apples.
    That also means the opponent side is their best available lineup, not
    necessarily the lineup they've actually set in Sleeper — stated in the
    response as `starters_basis` so the client can say so out loud.
    """

    roster_player_ids = {str(pid) for pid in (roster.get("players") or [])}
    starters, _bench = _suggested_lineup_split(valued, roster_player_ids, settings, score_field)

    best_score_by_position: dict[str, float] = {}
    for player in starters:
        position = str(player.get("position") or "").strip()
        score = player.get("score")
        if not position or not isinstance(score, (int, float)):
            continue
        best_score_by_position[position] = max(best_score_by_position.get(position, float("-inf")), float(score))

    for player in starters:
        player["why"] = _matchup_starter_why(player, best_score_by_position)

    season_value_total = round(
        sum(float(p["score"]) for p in starters if isinstance(p.get("score"), (int, float))), 1
    )
    roster_settings = roster.get("settings") or {}
    return {
        "roster_id": roster_id,
        "team_name": _clean_json_value(profile.get("team_name")) or f"Team {roster_id}",
        "owner_name": _clean_json_value(profile.get("owner_name")),
        "avatar_url": _clean_json_value(profile.get("avatar_url")),
        "wins": _clean_json_value(roster_settings.get("wins")),
        "losses": _clean_json_value(roster_settings.get("losses")),
        "ties": _clean_json_value(roster_settings.get("ties")),
        "starters": starters,
        "season_value_total": season_value_total,
        "starters_basis": "suggested_optimal_lineup",
    }


def _matchup_comparison(my_total: float, opponent_total: float) -> dict[str, Any]:
    margin = round(my_total - opponent_total, 1)
    scale = max(abs(my_total), abs(opponent_total), 1.0)
    if abs(margin) / scale < _MATCHUP_EVEN_THRESHOLD:
        edge = "even"
        headline = "Too close to call on season value"
    elif margin > 0:
        edge = "you"
        headline = "Your lineup carries the stronger season-long value"
    else:
        edge = "opponent"
        headline = "Your opponent's lineup carries the stronger season-long value"
    return {
        "my_season_value": my_total,
        "opponent_season_value": opponent_total,
        "margin": margin,
        "edge": edge,
        "headline": headline,
        "basis": SEASON_VALUE_BASIS,
        "basis_label": SEASON_VALUE_BASIS_LABEL,
    }


def _empty_matchup(reason: str, week: int | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "week": week,
        "my_team": None,
        "opponent": None,
        "comparison": None,
        "basis": SEASON_VALUE_BASIS,
        "basis_label": SEASON_VALUE_BASIS_LABEL,
        "reason": reason,
    }


@app.get("/v1/leagues/{league_id}/matchup")
def get_league_matchup(
    league_id: str,
    lens: str = "Dynasty",
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """This week's head-to-head: your suggested starters vs. your opponent's.

    Week comes from the league's own `settings.leg` (the same current-week
    field the mobile League screen already reads), and the pairing from
    modules.sleeper.get_matchups for that week — the live Sleeper endpoint,
    so this works during an in-progress week, not just completed ones.

    HONEST SCOPE — read before extending: this is NOT a points projection.
    No weekly-projection feed and no opponent-defense-strength data exist
    anywhere in this codebase, so both sides are ranked by the same
    season-long value/opportunity signal every other surface here uses
    (SEASON_VALUE_BASIS_LABEL), and each starter's `why` cites only real
    season-form fields (tier, workload/opportunity label, season-value rank
    on that roster, injury tag). A true weekly projection would be a new
    data source, not a relabel of this one.

    Not-ready states return 200 with a `reason` (same contract as /my-team
    and the other league endpoints) rather than an HTTP error: the
    roster-resolution reasons from `_resolve_my_roster`, plus
    no_current_week / no_matchup_data / roster_not_in_matchups / bye_week.
    """

    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    profile = _fetch_profile_fields(config, user_id, str(user.get("_access_token") or "")) if user_id else {}
    my_roster, reason = _resolve_my_roster(user, league_id, profile=profile)
    if my_roster is None:
        return _empty_matchup(reason)

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")
    settings = league_value_settings.detect_league_value_settings_from_payload(league)

    league_settings = league.get("settings") if isinstance(league.get("settings"), dict) else {}
    try:
        current_week = int((league_settings or {}).get("leg") or 0)
    except (TypeError, ValueError):
        current_week = 0
    if current_week <= 0:
        return _empty_matchup("no_current_week")

    matchups = sleeper.get_matchups(league_id, current_week)
    if not matchups:
        return _empty_matchup("no_matchup_data", week=current_week)

    my_roster_id = str(my_roster.get("roster_id") or "")
    my_entry = next((m for m in matchups if str(m.get("roster_id") or "") == my_roster_id), None)
    if my_entry is None:
        return _empty_matchup("roster_not_in_matchups", week=current_week)

    # A null matchup_id is Sleeper's own "this roster isn't paired this
    # week" (bye / odd team count), not a missing-data error.
    matchup_id = my_entry.get("matchup_id")
    opponent_entry = (
        next(
            (
                m
                for m in matchups
                if m.get("matchup_id") == matchup_id and str(m.get("roster_id") or "") != my_roster_id
            ),
            None,
        )
        if matchup_id is not None
        else None
    )
    if opponent_entry is None:
        return _empty_matchup("bye_week", week=current_week)

    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    players_df = player_eligibility.filter_current_fantasy_players(
        players_df, surface="mobile_api_matchup", league=league
    )
    if players_df.empty:
        return _empty_matchup("no_player_data", week=current_week)

    valued = league_value_settings.apply_valuation_lens(players_df, lens, settings)
    score_field = league_value_settings.valuation_score_field(lens)

    opponent_roster_id = str(opponent_entry.get("roster_id") or "")
    rosters_by_id = {str(r.get("roster_id") or ""): r for r in sleeper.get_rosters(league_id)}
    opponent_roster = rosters_by_id.get(opponent_roster_id)
    if opponent_roster is None:
        return _empty_matchup("opponent_roster_missing", week=current_week)

    profiles = sleeper.get_league_roster_profiles(league_id) or {}
    my_side = _matchup_side(
        my_roster_id, my_roster, profiles.get(my_roster_id) or {}, valued, settings, score_field
    )
    opponent_side = _matchup_side(
        opponent_roster_id,
        opponent_roster,
        profiles.get(opponent_roster_id) or {},
        valued,
        settings,
        score_field,
    )
    if not my_side["starters"] and not opponent_side["starters"]:
        return _empty_matchup("empty_roster", week=current_week)

    return {
        "ok": True,
        "week": current_week,
        "my_team": my_side,
        "opponent": opponent_side,
        "comparison": _matchup_comparison(
            my_side["season_value_total"], opponent_side["season_value_total"]
        ),
        "basis": SEASON_VALUE_BASIS,
        "basis_label": SEASON_VALUE_BASIS_LABEL,
        "reason": "",
    }


def _project_waiver_row(
    row: pd.Series, score_field: str, opponent_by_team: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    matchup = (opponent_by_team or {}).get(str(row.get("team") or ""))
    return {
        "player_id": _clean_json_value(row.get("player_id")),
        "name": _clean_json_value(row.get("name")),
        "position": _clean_json_value(row.get("position")),
        "team": _clean_json_value(row.get("team")),
        "age": _clean_json_value(row.get("age")),
        "status": _clean_json_value(row.get("status")),
        "injury_status": _clean_json_value(row.get("injury_status")),
        "tier": _clean_json_value(row.get("player_tier")),
        "opportunity_label": _clean_json_value(row.get("opportunity_label")),
        "score": _clean_json_value(row.get(score_field)),
        # This week's real opponent (modules.nfl_schedule) — context only,
        # same "never overweighted" contract as Player Detail's Schedule
        # tab: doesn't touch score/position_rank/overall_rank above.
        "opponent": matchup.get("opponent") if matchup else None,
        "opponent_is_home": matchup.get("is_home") if matchup else None,
        # Wire-relative ranks (rank among available free agents only), not the
        # league-global canonical_* ranks /rankings returns — deliberately
        # separate, matching the web app's waivers page (app.py comment:
        # "FA-relative ranks for waiver logic only; canonical_* stay
        # league-global").
        "position_rank": _clean_json_value(row.get("position_rank")),
        "overall_rank": _clean_json_value(row.get("overall_rank")),
        "stale_free_agent": bool(row.get("stale_free_agent") or False),
        "injury_replacement_fit": bool(row.get("injury_replacement_fit") or False),
        "injury_replacement_note": _clean_json_value(row.get("injury_replacement_note")) or "",
    }


def _project_priority_add(
    row: pd.Series,
    score_field: str,
    guidance: "faab.FaabGuidance",
    opponent_by_team: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    projected = _project_waiver_row(row, score_field, opponent_by_team)
    position_rank = int(row.get("position_rank") or 99) or 99
    label, tone = waivers_ui.waiver_recommendation_label(row, position_rank)
    projected["recommendation_label"] = label
    projected["recommendation_tone"] = tone
    projected["faab"] = {
        "low_bid": guidance.low_bid,
        "high_bid": guidance.high_bid,
        "pct_low": guidance.pct_low,
        "pct_high": guidance.pct_high,
        "remaining": guidance.remaining,
        "dollars_known": guidance.dollars_known,
        "label": guidance.as_label(),
    }
    return projected


@app.get("/v1/leagues/{league_id}/waivers")
def get_league_waivers(
    league_id: str,
    lens: str = "Dynasty",
    limit: int = 150,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Free-agent pool + roster-need-aware Priority Adds + FAAB guidance.

    Replaces the previous mobile approach (client-side filtering the full
    /rankings list to exclude rostered players, with no roster-need
    awareness at all) with the same server-side pipeline the web app's
    waivers page uses: modules.player_state_authority for the
    rostered-id exclusion, modules.rankings.is_probably_stale_free_agent
    for stale/retired detection, modules.trade_analyzer_fit for roster
    needs + injury-replacement context, modules.waivers_ui for the
    Priority Adds ranking, and modules.faab for bid guidance.
    """

    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    profile = _fetch_profile_fields(config, user_id, str(user.get("_access_token") or "")) if user_id else {}

    my_roster, reason = _resolve_my_roster(user, league_id, profile=profile)
    if my_roster is None:
        return {"ok": True, "players": [], "priority_adds": [], "needed_positions": [], "reason": reason}

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")
    settings = league_value_settings.detect_league_value_settings_from_payload(league)

    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    players_df = player_eligibility.filter_current_fantasy_players(
        players_df, surface="mobile_api_waivers", league=league
    )
    if players_df.empty:
        return {"ok": True, "players": [], "priority_adds": [], "needed_positions": [], "reason": "no_player_data"}

    valued = league_value_settings.apply_valuation_lens(players_df, lens, settings)
    score_field = league_value_settings.valuation_score_field(lens)

    rosters = sleeper.get_rosters(league_id)
    roster_player_map = {
        str(roster.get("roster_id")): tuple(
            str(pid) for pid in (roster.get("players") or []) if pid is not None
        )
        for roster in rosters
        if roster.get("roster_id") is not None
    }

    free_agents = player_state_authority.waiver_actionable_player_pool(
        valued, roster_player_map, surface="mobile_api_waivers"
    )
    if free_agents.empty:
        return {
            "ok": True,
            "players": [],
            "priority_adds": [],
            "needed_positions": [],
            "available_count": 0,
            "avg_wire_score": 0,
            "reason": "",
        }

    free_agents = free_agents.copy()
    free_agents["stale_free_agent"] = free_agents.apply(rankings.is_probably_stale_free_agent, axis=1)
    free_agents.loc[free_agents["stale_free_agent"], ["dynasty_score", "value_score"]] = 0
    free_agents = free_agents.sort_values(["stale_free_agent", score_field], ascending=[True, False])

    score_series = pd.to_numeric(free_agents.get(score_field, 0), errors="coerce").fillna(0)
    free_agents["position_rank"] = (
        free_agents.groupby("position")[score_field]
        .rank(method="first", ascending=False)
        .fillna(0)
        .astype(int)
    )
    free_agents["overall_rank"] = score_series.rank(method="first", ascending=False).fillna(0).astype(int)
    avg_wire_score = int(score_series.mean()) if len(score_series) else 0

    roster_id = str(my_roster.get("roster_id") or "")
    roster_player_ids = roster_player_map.get(roster_id, ())
    roster_df = valued[valued["player_id"].astype(str).isin(roster_player_ids)].copy()

    needed_positions: list[str] = []
    injury_positions: set[str] = set()
    if not roster_df.empty:
        lineup_df = suggest_optimal_lineup(roster_df, settings, score_field=score_field)
        team_needs = trade_analyzer_fit.build_team_needs_assessment(
            roster_df, None, settings, lineup_df=lineup_df, score_field=score_field
        )
        needed_positions = trade_analyzer_fit.get_needed_positions(
            roster_df, None, settings, include_fallback=False, assessment=team_needs
        )
        injury_context = trade_analyzer_fit.roster_injury_context(roster_df, lineup_df)
        injury_positions = {
            str(pos).upper()
            for pos in (injury_context.get("injury_need_positions") or set())
            if str(pos).upper() in {"QB", "RB", "WR", "TE", "K"}
        }

    if injury_positions:
        positions_upper = free_agents["position"].fillna("").astype(str).str.upper()
        fit_mask = positions_upper.isin(injury_positions) & (score_series > 0) & (~free_agents["stale_free_agent"])
        free_agents["injury_replacement_fit"] = fit_mask
        free_agents["injury_replacement_note"] = [
            f"Healthy cover for your injury-hit {pos} room." if fit else ""
            for pos, fit in zip(positions_upper, fit_mask)
        ]
    else:
        free_agents["injury_replacement_fit"] = False
        free_agents["injury_replacement_note"] = ""

    # This week's real opponent per team (modules.nfl_schedule) — context
    # only, per coridian_'s explicit "should not be overweighted": doesn't
    # touch score_field, position_rank, or overall_rank anywhere above,
    # same contract as Player Detail's Schedule tab. Best-effort: a league
    # with no current week (offseason/draft) or an unmapped team just
    # leaves "opponent" null rather than failing the whole request.
    opponent_by_team: dict[str, dict[str, Any]] = {}
    try:
        current_week = int((league.get("settings") or {}).get("leg") or 0)
    except (TypeError, ValueError):
        current_week = 0
    if current_week > 0:
        season = sleeper.default_player_stats_season()
        games_df = nfl_schedule.load_games()
        for team_code in {str(t) for t in free_agents["team"].dropna().unique() if str(t)}:
            matchup = nfl_schedule.team_matchup_for_week(team_code, current_week, season, games=games_df)
            if matchup:
                opponent_by_team[team_code] = matchup

    limited = free_agents.head(max(1, min(limit, 300)))
    players = [_project_waiver_row(row, score_field, opponent_by_team) for _, row in limited.iterrows()]

    priority_df = waivers_ui.rank_priority_add_candidates(
        free_agents,
        score_field=score_field,
        needed_positions=needed_positions,
        league_settings=settings,
        roster_df=roster_df,
        max_items=6,
    )
    faab_budget = faab.sleeper_faab_budget_context(league, rosters, roster_id=roster_id)
    needed_upper = {pos.upper() for pos in needed_positions}
    priority_adds: list[dict[str, Any]] = []
    for _, row in priority_df.iterrows():
        try:
            player_score = int(round(float(row.get(score_field) or 0)))
        except (TypeError, ValueError):
            player_score = 0
        guidance = faab.recommend_faab_guidance(
            player_score=player_score,
            position=str(row.get("position") or ""),
            budget=faab_budget.initial or 100,
            league_settings=settings,
            status=str(row.get("status") or ""),
            injury_status=str(row.get("injury_status") or ""),
            injury_need_match=bool(row.get("injury_replacement_fit")),
            remaining_budget=faab_budget.remaining,
            roster_need=str(row.get("position") or "").upper() in needed_upper,
        )
        priority_adds.append(_project_priority_add(row, score_field, guidance, opponent_by_team))

    # Secondary waiver board (Stash Candidates / Watchlist Depth / FAAB
    # Shortlist) — matches web's Premium-only gate (modules/waivers_ui.py:
    # "if not is_premium: render_premium_lock(...); return", app.py's
    # classification just above that call). Adapted, not a byte-for-byte
    # port: web dedupes against its own `featured_free_agents` presentation
    # slice, which isn't reproduced here — this dedupes against the same
    # Priority Adds list this endpoint already returns instead.
    is_premium = str(profile.get("entitlement") or "free") == "premium"
    stash_candidates: list[dict[str, Any]] = []
    watchlist_candidates: list[dict[str, Any]] = []
    faab_targets: list[dict[str, Any]] = []
    if is_premium and not free_agents.empty:
        priority_ids = {str(row.get("player_id")) for _, row in priority_df.iterrows()}
        age_numeric = pd.to_numeric(free_agents.get("age"), errors="coerce").fillna(99)
        upside_labels = {"Backup With Upside", "Starter At Risk", "Committee Back"}
        opportunity = free_agents.get("opportunity_label", pd.Series("", index=free_agents.index)).fillna("")
        stash_mask = (age_numeric <= 24) | opportunity.isin(upside_labels)
        stash_df = (
            free_agents[stash_mask & ~free_agents["player_id"].astype(str).isin(priority_ids)]
            .drop_duplicates(subset=["player_id"])
            .head(6)
        )
        seen_after_stash = priority_ids | set(stash_df["player_id"].astype(str))
        watchlist_df = free_agents[~free_agents["player_id"].astype(str).isin(seen_after_stash)].head(6)
        seen_after_watchlist = seen_after_stash | set(watchlist_df["player_id"].astype(str))
        faab_pool = free_agents[
            (~free_agents["stale_free_agent"])
            & (score_series > 0)
            & (~free_agents["player_id"].astype(str).isin(seen_after_watchlist))
        ]
        faab_df = faab_pool.sort_values(score_field, ascending=False).head(4)

        stash_candidates = [_project_waiver_row(row, score_field, opponent_by_team) for _, row in stash_df.iterrows()]
        watchlist_candidates = [_project_waiver_row(row, score_field, opponent_by_team) for _, row in watchlist_df.iterrows()]
        faab_targets = [_project_waiver_row(row, score_field, opponent_by_team) for _, row in faab_df.iterrows()]

    return {
        "ok": True,
        "players": players,
        "priority_adds": priority_adds,
        "needed_positions": needed_positions,
        "available_count": int(len(free_agents)),
        "avg_wire_score": avg_wire_score,
        "stash_candidates": stash_candidates,
        "watchlist_candidates": watchlist_candidates,
        "faab_targets": faab_targets,
        "entitlement": {"is_premium": is_premium},
        "reason": "",
    }


# Mobile-only reveal mechanic: watching a rewarded ad temporarily raises the
# Free-tier visible count above modules.trade_hub_ui.FREE_VISIBLE_IDEAS (2),
# same board/ranking as web. Web has no ad path, so this bonus is layered on
# top of the shared engine rather than added to trade_hub_ui itself.
AD_BONUS_IDEAS_PER_UNLOCK = 2
MAX_AD_UNLOCKS = 3


def _project_and_enrich_trade_idea_cards(
    records: list[dict[str, Any]], *, league_id: str, lens: str
) -> list[dict[str, Any]]:
    """Raw trade_hub_engine records -> ranked, mobile-card-shaped dicts with
    partner avatar/archetype/trade-tendency attached. Shared by Trade Hub's
    own board and Trade Finder — both project and enrich the exact same way,
    only how `records` was generated (passive board vs. a specific trade
    block search) differs between the two callers.
    """
    # Rank on the raw engine records (trade_confidence_label, tier, etc.) —
    # the same fields the web app's Trade Hub sorts on — then project only
    # the visible slice to the narrower mobile card shape.
    ranked_records = trade_hub_ui.order_trade_hub_visible_ideas(list(records))
    ranked = [
        trade_hub_engine.project_trade_idea_card(record, is_headline=(index == 0)).to_dict()
        for index, record in enumerate(ranked_records)
    ]
    # Trade Hub's own idea-generation engine never carries a roster_id
    # through to the projected card, only the partner's display name — so
    # this resolves an avatar by matching that name against the same
    # roster-profile lookup /v1/leagues/{id}/team-profiles already uses,
    # rather than threading a new field through modules.trade_ideas's deep
    # (and heavily-tested) idea pipeline. Best-effort: a name mismatch just
    # leaves the client's initial-letter fallback in place.
    avatar_by_team_name = {
        str(profile.get("team_name") or "").strip().lower(): profile.get("avatar_url")
        for profile in sleeper.get_league_roster_profiles(league_id).values()
    }
    for card in ranked:
        card["partner_team_avatar_url"] = avatar_by_team_name.get(
            str(card.get("partner_team_name") or "").strip().lower()
        )
    # Concept-sheet parity: each card names the partner's real archetype
    # ("Rebuilding", "Contending", etc.) under their team name — the exact
    # same archetype_label /v1/leagues/{id}/team-rankings already computes
    # for every roster (modules.team_eval), matched by team name like the
    # avatar lookup above rather than threading a new field through
    # modules.trade_ideas's idea pipeline. Best-effort: cached, so this
    # rarely costs a fresh computation on top of what Teams/My Team already
    # triggered.
    try:
        rankings_frame = league_rankings.build_league_rankings_frame_cached(
            league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
        )
        archetype_by_team_name = {
            str(row.get("team_name") or "").strip().lower(): _clean_json_value(row.get("archetype_label"))
            for _, row in rankings_frame.iterrows()
        }
    except Exception:
        archetype_by_team_name = {}
        rankings_frame = pd.DataFrame()
    # Decision Memory's data half: a partner with a real history of selling
    # (modules.team_trade_history, off actual Sleeper trade history) is
    # surfaced here too — same "context, not new scoring" contract as the
    # NFL schedule import: nothing below changes trade_gain/confidence/
    # category, it's presentation only until a separate, deliberate pass
    # decides how (or whether) to weight it in the engine itself.
    try:
        trade_tendencies = team_trade_history.league_trade_tendencies_cached(league_id, PLAYERS_DB_PATH)
        tendency_by_team_name = {
            str(row.get("team_name") or "").strip().lower(): trade_tendencies.get(int(row.get("roster_id") or 0), {})
            for _, row in rankings_frame.iterrows()
        }
    except Exception:
        tendency_by_team_name = {}
    for card in ranked:
        team_key = str(card.get("partner_team_name") or "").strip().lower()
        card["partner_team_archetype_label"] = archetype_by_team_name.get(team_key) or ""
        tendency = tendency_by_team_name.get(team_key, {})
        card["partner_trade_tendency"] = tendency.get("tendency", team_trade_history.NEUTRAL)
    return ranked


@app.get("/v1/leagues/{league_id}/trade-hub")
def get_trade_hub_ideas(
    league_id: str,
    strategy: str = "retool",
    lens: str = "Dynasty",
    ad_unlocks: int = 0,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Real trade ideas for the caller's roster in this league.

    Shares the exact same idea-generation engine as the web app's Trade Hub
    (modules.trade_ideas.build_trade_ideas) and the same production Trust
    enforcement boundary, via modules.trade_hub_engine — see that module's
    docstring for why it's a fresh composition rather than importing
    app.py directly (modules/ never imports app.py).

    Free-tier gating reuses the web app's own ranking and free-count
    contract (modules.trade_hub_ui.order_trade_hub_visible_ideas /
    FREE_VISIBLE_IDEAS) so the "first 2 ideas" a Free mobile user sees are
    identically chosen to the web app's. `ad_unlocks` (client-tracked,
    reset per session) temporarily raises that ceiling — a mobile-only
    reward mechanic, not part of the shared entitlement contract.
    """

    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    profile = _fetch_profile_fields(config, user_id, str(user.get("_access_token") or "")) if user_id else {}

    my_roster, reason = _resolve_my_roster(user, league_id, profile=profile)
    if my_roster is None:
        return {"ok": True, "ideas": [], "reason": reason}

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")

    roster_id = my_roster.get("roster_id")
    if roster_id is None:
        return {"ok": True, "ideas": [], "reason": "empty_roster"}

    gm_target_ids, gm_untouchable_ids = _fetch_gm_target_player_ids(
        config, user_id, str(user.get("_access_token") or ""), league_id
    )
    records = trade_hub_engine.generate_trade_idea_records_cached(
        league_id=league_id,
        roster_id=int(roster_id),
        strategy=strategy,
        lens=lens,
        players_db_path=PLAYERS_DB_PATH,
        untouchable_player_ids=gm_untouchable_ids,
        gm_target_player_ids=gm_target_ids,
    )

    is_premium = str(profile.get("entitlement") or "free") == "premium"
    ranked = _project_and_enrich_trade_idea_cards(records, league_id=league_id, lens=lens)
    approved_count = len(ranked)
    ad_unlocks_applied = max(0, min(int(ad_unlocks or 0), MAX_AD_UNLOCKS))
    effective_limit = (
        approved_count
        if is_premium
        else min(
            approved_count,
            trade_hub_ui.FREE_VISIBLE_IDEAS + AD_BONUS_IDEAS_PER_UNLOCK * ad_unlocks_applied,
        )
    )
    visible = ranked[:effective_limit]
    return {
        "ok": True,
        "ideas": visible,
        "reason": "",
        "entitlement": {
            "is_premium": is_premium,
            "approved_count": approved_count,
            "visible_count": len(visible),
            "hidden_count": approved_count - len(visible),
            "free_limit": trade_hub_ui.FREE_VISIBLE_IDEAS,
            "ad_bonus_per_unlock": AD_BONUS_IDEAS_PER_UNLOCK,
            "max_ad_unlocks": MAX_AD_UNLOCKS,
            "ad_unlocks_applied": ad_unlocks_applied,
        },
    }


@app.get("/v1/leagues/{league_id}/trade-finder")
def get_trade_finder_ideas(
    league_id: str,
    player_ids: str = "",
    strategy: str = "retool",
    lens: str = "Dynasty",
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Trade Finder — "select these specific players, find who'd want
    them," coridian_'s own trade-block request. Same engine, Trust
    enforcement, and card shape as /trade-hub (see
    trade_hub_engine.generate_trade_finder_records' own docstring), just
    restricted to a caller-chosen player selection instead of the passive
    board's normal "anything not protected" pool. `player_ids` is a
    comma-separated list of this league's own player_ids — an empty or
    all-invalid selection returns an empty idea list rather than silently
    falling back to the unrestricted board (a Trade Finder search that
    ignores what was actually selected would be worse than no result).
    """

    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )

    selected_ids = tuple(sorted({pid.strip() for pid in player_ids.split(",") if pid.strip()}))
    if not selected_ids:
        return {"ok": True, "ideas": [], "reason": "no_players_selected"}

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    profile = _fetch_profile_fields(config, user_id, str(user.get("_access_token") or "")) if user_id else {}

    my_roster, reason = _resolve_my_roster(user, league_id, profile=profile)
    if my_roster is None:
        return {"ok": True, "ideas": [], "reason": reason}

    roster_id = my_roster.get("roster_id")
    if roster_id is None:
        return {"ok": True, "ideas": [], "reason": "empty_roster"}

    gm_target_ids, gm_untouchable_ids = _fetch_gm_target_player_ids(
        config, user_id, str(user.get("_access_token") or ""), league_id
    )
    records = trade_hub_engine.generate_trade_finder_records(
        league_id=league_id,
        roster_id=int(roster_id),
        strategy=strategy,
        lens=lens,
        players_db_path=PLAYERS_DB_PATH,
        trade_block_player_ids=selected_ids,
        untouchable_player_ids=gm_untouchable_ids,
        gm_target_player_ids=gm_target_ids,
    )
    ranked = _project_and_enrich_trade_idea_cards(records, league_id=league_id, lens=lens)
    return {"ok": True, "ideas": ranked, "reason": ""}


@app.get("/v1/leagues/{league_id}/all-trades")
def get_league_all_trades(
    league_id: str,
    strategy: str = "retool",
    lens: str = "Dynasty",
    cursor: int = 0,
    page_size: int = 3,
    shown_count: int = 0,
    ad_unlocks: int = 0,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Browse trade ideas across every roster in the league, not just the
    caller's — the concept sheet's "All Trades" tab.

    Paginated by roster rather than generated all at once: each roster's
    ideas are real, non-trivial work (modules.trade_hub_engine.
    generate_trade_idea_records_cached, cached per (league, roster,
    strategy, lens) but still a cold pass the first time), so a 12-team
    league would mean 12x the compute of Trade Hub's own board if this ran
    eagerly. `cursor`/`page_size` walk rosters in a stable order; the
    client re-calls with the next cursor on "Load More" — no team is ever
    left out, it just isn't all generated up front.

    Same free-tier gating as /trade-hub (modules.trade_hub_ui.
    FREE_VISIBLE_IDEAS), applied cumulatively via `shown_count` (how many
    ideas the client has already been shown across prior pages) — a Free
    user's cap doesn't reset every time they tap Load More.
    """

    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    profile = _fetch_profile_fields(config, user_id, str(user.get("_access_token") or "")) if user_id else {}
    is_premium = str(profile.get("entitlement") or "free") == "premium"

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")

    my_roster, _reason = _resolve_my_roster(user, league_id, profile=profile)
    my_roster_id = int(my_roster.get("roster_id")) if my_roster and my_roster.get("roster_id") is not None else None

    rosters = sleeper.get_rosters(league_id)
    roster_ids = sorted({
        int(r["roster_id"]) for r in rosters if isinstance(r, dict) and r.get("roster_id") is not None
    })
    total_teams = len(roster_ids)
    cursor = max(0, cursor)
    page_size = max(1, min(page_size, 6))
    page_roster_ids = roster_ids[cursor : cursor + page_size]

    gm_target_ids, gm_untouchable_ids = _fetch_gm_target_player_ids(
        config, user_id, str(user.get("_access_token") or ""), league_id
    )
    roster_profiles = sleeper.get_league_roster_profiles(league_id)
    avatar_by_team_name = {
        str(p.get("team_name") or "").strip().lower(): p.get("avatar_url") for p in roster_profiles.values()
    }
    # roster_id -> team_name, so each card can say whose perspective it's
    # from ("Team A ↔ Team B") — partner_team_name alone is ambiguous once
    # a card isn't necessarily generated from the caller's own roster.
    team_name_by_roster_id = {
        str(roster_id): str(profile.get("team_name") or "") for roster_id, profile in roster_profiles.items()
    }
    try:
        rankings_frame = league_rankings.build_league_rankings_frame_cached(
            league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
        )
        archetype_by_team_name = {
            str(row.get("team_name") or "").strip().lower(): _clean_json_value(row.get("archetype_label"))
            for _, row in rankings_frame.iterrows()
        }
    except Exception:
        archetype_by_team_name = {}

    # Free-tier remaining budget carried in from prior pages — computed
    # once, up front, so a page never hands out more than a Free user has
    # left regardless of how many teams' ideas it touches.
    ad_unlocks_applied = max(0, min(int(ad_unlocks or 0), MAX_AD_UNLOCKS))
    free_cap = trade_hub_ui.FREE_VISIBLE_IDEAS + AD_BONUS_IDEAS_PER_UNLOCK * ad_unlocks_applied
    remaining_free = max(0, free_cap - max(0, int(shown_count or 0)))

    ideas: list[dict[str, Any]] = []
    for roster_id in page_roster_ids:
        if not is_premium and remaining_free <= 0:
            break
        is_my_roster = my_roster_id is not None and roster_id == my_roster_id
        try:
            records = trade_hub_engine.generate_trade_idea_records_cached(
                league_id=league_id,
                roster_id=roster_id,
                strategy=strategy,
                lens=lens,
                players_db_path=PLAYERS_DB_PATH,
                untouchable_player_ids=gm_untouchable_ids if is_my_roster else (),
                gm_target_player_ids=gm_target_ids if is_my_roster else (),
            )
        except Exception:
            continue
        ranked_records = trade_hub_ui.order_trade_hub_visible_ideas(list(records))
        # Cap per-team so one roster's board can't eat a whole page —
        # "All Trades" is meant to sample across the league, not repeat
        # Trade Hub's own full-depth board once per team.
        for record in ranked_records[:2]:
            if not is_premium and remaining_free <= 0:
                break
            card = trade_hub_engine.project_trade_idea_card(record, is_headline=False).to_dict()
            card["source_roster_id"] = str(roster_id)
            card["source_team_name"] = team_name_by_roster_id.get(str(roster_id), "")
            card["partner_team_avatar_url"] = avatar_by_team_name.get(
                str(card.get("partner_team_name") or "").strip().lower()
            )
            card["partner_team_archetype_label"] = archetype_by_team_name.get(
                str(card.get("partner_team_name") or "").strip().lower()
            ) or ""
            ideas.append(card)
            if not is_premium:
                remaining_free -= 1

    next_cursor = cursor + page_size
    return {
        "ok": True,
        "ideas": ideas,
        "has_more": next_cursor < total_teams and (is_premium or remaining_free > 0 or ad_unlocks_applied < MAX_AD_UNLOCKS),
        "next_cursor": next_cursor,
        "total_teams": total_teams,
        "entitlement": {
            "is_premium": is_premium,
            "free_limit": trade_hub_ui.FREE_VISIBLE_IDEAS,
            "ad_bonus_per_unlock": AD_BONUS_IDEAS_PER_UNLOCK,
            "max_ad_unlocks": MAX_AD_UNLOCKS,
            "ad_unlocks_applied": ad_unlocks_applied,
            "remaining_free": remaining_free,
        },
    }
