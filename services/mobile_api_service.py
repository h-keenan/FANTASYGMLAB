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
  - GET  /v1/leagues/{id}/my-roster      — the signed-in user's own roster in this league
  - GET  /v1/players?ids=1,2,3           — minimal Sleeper player info by id
  - GET  /v1/leagues/{id}/rankings       — league-adjusted player rankings
  - GET  /v1/news                        — curated NFL fantasy news (injury/role/transaction/off-field)
  - POST /v1/leagues/{id}/trade-analyzer — real accept/decline/counter verdict for a proposed trade
  - GET  /v1/leagues/{id}/recap          — latest completed-week league recap
  - GET  /v1/leagues/{id}/alerts         — roster-relevant news alerts
  - POST /v1/leagues/{id}/alerts/read    — durably mark one alert read (RLS-scoped)
  - GET  /v1/players/{id}/quick-view     — season stats + bio for the player detail pop-up

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
    auth_supabase,
    canonical_player_ranking,
    league_history,
    league_recaps,
    league_value_settings,
    my_news,
    news as news_cache,
    news_signal,
    player_eligibility,
    player_quick_view,
    rankings,
    sleeper,
    sleeper_leagues,
    trade_analyzer_fit,
    trade_offer_analyzer,
)
from modules.trade_analyzer_assembly import player_asset_from_mapping


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


def _resolve_my_roster(user: dict[str, Any], league_id: str) -> tuple[dict[str, Any] | None, str]:
    """Identify which of this league's rosters belongs to the signed-in user.

    Resolves via the Sleeper username linked on their profile (same
    profiles.sleeper_username the web app sets) -> Sleeper user_id -> the
    roster whose owner_id matches. All non-matches are expected, everyday
    states (not errors) — callers return 200 with the `reason` rather than
    an HTTP error status for any of them.
    """

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
    pool = news_cache.load_cached_news_pool()

    enriched = (news_signal.enrich_news_item(item) for item in pool if isinstance(item, dict))
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
    # Any unrecognized value falls back to "retool" — see
    # modules.team_eval.normalize_team_strategy — so this is never rejected.
    strategy: str = "retool"
    lens: str = "Dynasty"


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
    """

    if body.lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )
    if not body.send_player_ids and not body.receive_player_ids:
        raise HTTPException(status_code=422, detail="Provide at least one player on either side of the trade.")

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

    send_assets = build_assets(body.send_player_ids)
    receive_assets = build_assets(body.receive_player_ids)
    if not send_assets and not receive_assets:
        return {"ok": True, "verdict": None, "reason": "assets_not_found"}

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
    )
    return {"ok": True, "verdict": verdict.to_public_dict(), "reason": ""}


@app.get("/v1/leagues/{league_id}/recap")
def get_league_recap(league_id: str, _user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """Latest completed-week recap — shares the exact same builder as the web
    app's League Recaps page (modules.league_recaps.build_weekly_recap). Does
    not invent new stories, headline templates, or narrative logic. Movement
    (power-rank trend) and power_ranks are omitted, same as the web app's own
    call site when a league is first opened — build_weekly_recap simply
    skips the story categories that need them.
    """

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")

    _, _, max_history_week = league_recaps.league_history_window(league)
    matchup_rows = league_recaps.build_matchup_history_rows(
        league_id, max_history_week, fetch_matchups=sleeper.get_matchups
    )
    week = league_recaps.completed_recap_week(league, matchup_rows)
    if week <= 0:
        return {"ok": True, "recap": None, "reason": "no_completed_week"}

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
    return {"ok": True, "recap": recap, "reason": ""}


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


def _project_alert_item(item: dict[str, Any], *, read_keys: set[str]) -> dict[str, Any]:
    payload = _project_news_item(item)
    alert_key = _alert_key_for_link(str(item.get("link") or ""))
    payload["alert_key"] = alert_key
    payload["read"] = alert_key in read_keys
    payload["matched_player"] = _clean_json_value(item.get("matched_player"))
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

    news_cache.schedule_news_cache_refresh()
    pool = news_cache.load_cached_news_pool()
    filtered = my_news.filter_news_for_players(pool, player_names, roster_teams)
    curated = my_news.curate_player_news(filtered, max_items=limit)

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    read_keys = _fetch_read_alert_keys(config, user_id, str(user.get("_access_token") or ""), league_id)

    items = [_project_alert_item(item, read_keys=read_keys) for item in curated]
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


@app.get("/v1/players/{player_id}/quick-view")
def get_player_quick_view(
    player_id: str,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Player Quick View: season stats + bio for the player detail pop-up.

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
        return {"ok": True, "stats": None, "bio": None, "reason": "not_found"}

    row = matches.iloc[0]
    stats = player_quick_view.build_stats_view(row)
    bio = player_quick_view.build_executive_snapshot(row)
    return {
        "ok": True,
        "stats": _quick_view_stats_dict(stats),
        "bio": dataclasses.asdict(bio),
        "reason": "",
    }
