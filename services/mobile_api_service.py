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
  - GET  /v1/leagues/{id}/team-profiles  — team name/owner/avatar per roster
  - GET  /v1/leagues/{id}/team-rankings  — power/franchise/draft-capital rank + standings per roster
  - GET  /v1/leagues/{id}/draft-center   — draft posture + league-wide decision/partner cards
  - GET  /v1/leagues/{id}/draft-picks    — every draft pick asset, for the Trade Analyzer picks browser
  - GET  /v1/leagues/{id}/my-team        — your own roster's suggested starters vs. bench
  - GET  /v1/leagues/{id}/my-roster      — the signed-in user's own roster in this league
  - GET  /v1/players?ids=1,2,3           — minimal Sleeper player info by id
  - GET  /v1/leagues/{id}/rankings       — league-adjusted player rankings
  - GET  /v1/news                        — curated NFL fantasy news (injury/role/transaction/off-field)
  - POST /v1/leagues/{id}/trade-analyzer — real accept/decline/counter verdict for a proposed trade
  - GET  /v1/leagues/{id}/recap          — latest completed-week league recap
  - GET  /v1/leagues/{id}/alerts         — roster-relevant news alerts
  - POST /v1/leagues/{id}/alerts/read    — durably mark one alert read (RLS-scoped)
  - GET  /v1/players/{id}/quick-view     — season stats + bio for the player detail pop-up
  - GET  /v1/players/{id}/awards         — verified fantasy-performance badges (career history)
  - GET  /v1/leagues/{id}/gm-targets           — the caller's watchlist in this league
  - POST /v1/leagues/{id}/gm-targets           — add a player to the watchlist (cap-enforced)
  - DELETE /v1/leagues/{id}/gm-targets/{pid}   — remove a player from the watchlist
  - POST /v1/push/register    — upsert the caller's Expo push token
  - POST /v1/push/unregister  — remove one of the caller's tokens (sign-out)
  - POST /v1/push/test        — send a test push to all of the caller's tokens
  - GET  /v1/leagues/{id}/dashboard — the caller's "Next Move" briefing
  - GET  /v1/leagues/{id}/trade-hub — real trade ideas for the caller's roster
  - GET  /v1/leagues/{id}/waivers   — roster-need-aware free-agent pool + FAAB guidance

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
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
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
    player_awards,
    player_eligibility,
    player_quick_view,
    player_state_authority,
    push_tokens,
    push_triggers,
    rankings,
    sleeper,
    sleeper_leagues,
    trade_analyzer_fit,
    trade_hub_engine,
    trade_hub_ui,
    trade_ideas,
    trade_offer_analyzer,
    waivers_ui,
)
from modules.team_eval import refine_team_directions, suggest_optimal_lineup
from modules.trade_analyzer_assembly import pick_asset_from_mapping, player_asset_from_mapping


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


def _fetch_profile_fields(config: dict, user_id: str, access_token: str) -> dict[str, str]:
    """Read select `profiles` columns using the caller's own token (RLS-scoped)."""

    defaults = {"entitlement": "free", "sleeper_username": ""}
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
        }
    return defaults


@app.get("/v1/me")
def get_me(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    profile = {"entitlement": "free", "sleeper_username": ""}
    if user_id:
        profile = _fetch_profile_fields(config, user_id, str(user.get("_access_token") or ""))
    return {
        "ok": True,
        "user": {
            "id": user_id,
            "email": user.get("email") or "",
            "entitlement": profile["entitlement"],
            "sleeper_username": profile["sleeper_username"],
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
    settings = league_value_settings.detect_league_value_settings_from_payload(league)

    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    players_df = player_eligibility.filter_current_fantasy_players(
        players_df, surface="mobile_api_team_rankings"
    )
    if players_df.empty:
        return {"ok": True, "teams": [], "reason": "no_player_data"}

    valued = league_value_settings.apply_valuation_lens(players_df, lens, settings)
    score_field = league_value_settings.valuation_score_field(lens)

    rankings_frame = league_rankings.build_league_rankings_frame(
        valued, league_id, score_field=score_field, league_settings=settings
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

    teams: list[dict[str, Any]] = []
    for _, row in rankings_frame.iterrows():
        roster_id = str(row.get("roster_id"))
        standing = standings_by_roster.get(roster_id, {})
        teams.append(
            {
                "roster_id": roster_id,
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
    players_df = player_eligibility.filter_current_fantasy_players(players_df, surface="mobile_api_draft_center")
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
    Players/Picks roster browser.

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
    players_df = player_eligibility.filter_current_fantasy_players(players_df, surface="mobile_api_draft_picks")
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
        players_df, surface="mobile_api_rankings"
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


def _project_news_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": _clean_json_value(item.get("title")),
        "link": _clean_json_value(item.get("link")),
        "source": _clean_json_value(item.get("source")),
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
        players_df, surface="mobile_api_trade_analyzer"
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
    players_df = player_eligibility.filter_current_fantasy_players(players_df, surface="mobile_api_recap")
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


def _project_alert_item(
    item: dict[str, Any], *, read_keys: set[str], player_ids_by_name: dict[str, str]
) -> dict[str, Any]:
    payload = _project_news_item(item)
    alert_key = _alert_key_for_link(str(item.get("link") or ""))
    payload["alert_key"] = alert_key
    payload["read"] = alert_key in read_keys
    matched_player = str(item.get("matched_player") or "")
    payload["matched_player"] = _clean_json_value(item.get("matched_player"))
    payload["matched_player_id"] = player_ids_by_name.get(matched_player)
    payload["relevance_reason"] = _clean_json_value(item.get("relevance_reason"))
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

    items = [
        _project_alert_item(item, read_keys=read_keys, player_ids_by_name=player_ids_by_name)
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


def _stat_item_dict(item: player_quick_view.StatItem) -> dict[str, Any]:
    return {"label": item.label, "value": item.value, "note": item.note, "tone": item.tone}


def _season_stat_view_dict(season: player_quick_view.SeasonStatView) -> dict[str, Any]:
    return {
        "season": season.season,
        "season_type": season.season_type,
        "games": season.games,
        "complete": season.complete,
        "label": season.label,
        "key_stats": [_stat_item_dict(item) for item in season.key_stats],
        "fantasy": [_stat_item_dict(item) for item in season.fantasy],
        "usage": [_stat_item_dict(item) for item in season.usage],
    }


def _quick_view_stats_dict(stats: player_quick_view.PlayerQuickViewStats) -> dict[str, Any]:
    return {
        "seasons": [_season_stat_view_dict(season) for season in stats.seasons],
        "college": [_stat_item_dict(item) for item in stats.college],
        "college_available": stats.college_available,
        "career_totals_available": stats.career_totals_available,
        "position": stats.position,
    }


def _project_player_model(row: pd.Series) -> dict[str, Any]:
    """The web dossier's "Model" grid — market/opportunity/scarcity/role/age/
    confidence/workload-trend — ported from app.py's player-card assembly
    (~app.py:4098-4110). Every field here is a plain column already present
    on the same row build_stats_view/build_executive_snapshot already read;
    this is a pure projection, not a new computation.

    age_score is a native per-player metric when present; some player rows
    only carry the coarser age_penalty (a lens-relative adjustment) instead
    — age_score_label tells the client which one it's showing, matching
    app.py's own "Age Score" vs. "Age Lens" distinction.
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
    stats = player_quick_view.build_stats_view(row)
    bio = player_quick_view.build_executive_snapshot(row)
    return {
        "ok": True,
        "stats": _quick_view_stats_dict(stats),
        "bio": dataclasses.asdict(bio),
        "model": _project_player_model(row),
        "reason": "",
    }


class AddGmTargetRequest(BaseModel):
    player_id: str
    source_surface: str = ""


def _project_gm_target(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "player_id": gm_targets.normalize_player_id(row.get("player_id")),
        "source_surface": str(row.get("source_surface") or ""),
        "created_at": row.get("created_at"),
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
        config, user_id, access_token, league_id, select="player_id,source_surface,created_at"
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
    Trade Hub engine (modules.trade_hub_engine), defaulting to the "retool"
    strategy — the same default both the web app's dashboard and mobile's
    own Trade Hub screen fall back to.
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
        players_df, surface="mobile_api_dashboard"
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
    )

    # Team Snapshot: record comes straight off the roster we already
    # fetched, health/average age reuse the same roster_df + injury
    # pipeline dashboard_engine.compose_next_move_briefing already runs
    # internally (recomputed here rather than threaded through
    # DailyGmBriefing, which modules.push_triggers also constructs and
    # shouldn't need to change shape for a mobile-only display field).
    # Power/franchise rank now reuse modules.league_rankings (ported out of
    # app.py's add_league_detail_ranks/build_league_display_frame in PR
    # #520 for get_league_team_rankings) — the same league-wide frame that
    # endpoint already computes on demand, so this is no longer the
    # separate follow-up it once was.
    roster_df = valued[valued["player_id"].astype(str).isin(roster_player_ids)].copy()
    lineup_df = suggest_optimal_lineup(roster_df, settings, score_field=score_field)
    injury_context = trade_analyzer_fit.roster_injury_context(roster_df, lineup_df)
    injury_display_context = injury_ui.resolve_team_injury_context(injury_context)
    health_flag = injury_ui.team_injury_display_label(injury_display_context, include_uncertainty=True) or "Stable"
    average_age = (
        float(roster_df["age"].mean())
        if not roster_df.empty and roster_df["age"].notna().any()
        else None
    )

    power_rank = None
    franchise_rank = None
    rankings_frame = league_rankings.build_league_rankings_frame(
        valued, league_id, score_field=score_field, league_settings=settings
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
        "average_age": round(average_age, 1) if average_age is not None else None,
        "power_rank": power_rank,
        "franchise_rank": franchise_rank,
    }

    return {
        "ok": True,
        "items": [_project_briefing_item(item) for item in briefing.items],
        "quiet": briefing.quiet,
        "quiet_reason": briefing.quiet_reason,
        "team_snapshot": team_snapshot,
        "reason": "",
    }


# Display order for My Team's starters section — matches
# modules.team_eval.suggest_optimal_lineup's own slot-assignment order.
# Bench keeps the frame's existing sort_score-descending order untouched.
_LINEUP_SLOT_ORDER = ["QB", "RB", "WR", "TE", "FLEX", "SUPER_FLEX", "WR/RB", "K"]


def _project_lineup_row(row: pd.Series, score_field: str) -> dict[str, Any]:
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
        "slot": _clean_json_value(row.get("slot")),
        "suggested_starter": bool(row.get("suggested_starter")),
        "opportunity_label": _clean_json_value(row.get("opportunity_label")),
    }


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
    players_df = player_eligibility.filter_current_fantasy_players(players_df, surface="mobile_api_my_team")
    if players_df.empty:
        return {"ok": True, "starters": [], "bench": [], "reason": "no_player_data"}

    valued = league_value_settings.apply_valuation_lens(players_df, lens, settings)
    score_field = league_value_settings.valuation_score_field(lens)

    roster_player_ids = {str(pid) for pid in (my_roster.get("players") or [])}
    if not roster_player_ids:
        return {"ok": True, "starters": [], "bench": [], "reason": "empty_roster"}

    roster_df = valued[valued["player_id"].astype(str).isin(roster_player_ids)].copy()
    lineup_df = suggest_optimal_lineup(roster_df, settings, score_field=score_field)

    players = [_project_lineup_row(row, score_field) for _, row in lineup_df.iterrows()]
    starters = [p for p in players if p["suggested_starter"]]
    starters.sort(
        key=lambda p: _LINEUP_SLOT_ORDER.index(p["slot"]) if p["slot"] in _LINEUP_SLOT_ORDER else len(_LINEUP_SLOT_ORDER)
    )
    bench = [p for p in players if not p["suggested_starter"]]

    return {"ok": True, "starters": starters, "bench": bench, "reason": ""}


def _project_waiver_row(row: pd.Series, score_field: str) -> dict[str, Any]:
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
    row: pd.Series, score_field: str, guidance: "faab.FaabGuidance"
) -> dict[str, Any]:
    projected = _project_waiver_row(row, score_field)
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
        players_df, surface="mobile_api_waivers"
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

    limited = free_agents.head(max(1, min(limit, 300)))
    players = [_project_waiver_row(row, score_field) for _, row in limited.iterrows()]

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
        priority_adds.append(_project_priority_add(row, score_field, guidance))

    return {
        "ok": True,
        "players": players,
        "priority_adds": priority_adds,
        "needed_positions": needed_positions,
        "available_count": int(len(free_agents)),
        "avg_wire_score": avg_wire_score,
        "reason": "",
    }


# Mobile-only reveal mechanic: watching a rewarded ad temporarily raises the
# Free-tier visible count above modules.trade_hub_ui.FREE_VISIBLE_IDEAS (2),
# same board/ranking as web. Web has no ad path, so this bonus is layered on
# top of the shared engine rather than added to trade_hub_ui itself.
AD_BONUS_IDEAS_PER_UNLOCK = 2
MAX_AD_UNLOCKS = 3


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
    settings = league_value_settings.detect_league_value_settings_from_payload(league)

    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    players_df = player_eligibility.filter_current_fantasy_players(
        players_df, surface="mobile_api_trade_hub"
    )
    if players_df.empty:
        return {"ok": True, "ideas": [], "reason": "no_player_data"}

    valued = league_value_settings.apply_valuation_lens(players_df, lens, settings)
    score_field = league_value_settings.valuation_score_field(lens)

    roster_id = my_roster.get("roster_id")
    if roster_id is None:
        return {"ok": True, "ideas": [], "reason": "empty_roster"}

    rosters = sleeper.get_rosters(league_id)
    records = trade_hub_engine.generate_trade_idea_records(
        league_id=league_id,
        my_roster_id=int(roster_id),
        players_df=valued,
        rosters=rosters,
        league_settings=settings,
        score_field=score_field,
        team_strategy=strategy,
    )

    is_premium = str(profile.get("entitlement") or "free") == "premium"
    # Rank on the raw engine records (trade_confidence_label, tier, etc.) —
    # the same fields the web app's Trade Hub sorts on — then project only
    # the visible slice to the narrower mobile card shape.
    ranked_records = trade_hub_ui.order_trade_hub_visible_ideas(list(records))
    ranked = [
        trade_hub_engine.project_trade_idea_card(record, is_headline=(index == 0)).to_dict()
        for index, record in enumerate(ranked_records)
    ]
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
